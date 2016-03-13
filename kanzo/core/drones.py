# -*- coding: utf-8 -*-

import collections
import datetime
import greenlet
import logging
import os
import shutil
import sys
import tempfile
import time

from ..conf import project
from .. import utils

from . import puppet


LOG = logging.getLogger('kanzo.backend')


class Drone(object):
    """Drone manages host where Puppet agent has to run. It prepares
    environment on host and registers it to Puppet master which is managed
    by class kanzo.core.Controller
    """

    def __init__(self, host, config, messages,
                 work_dir=None, remote_tmpdir=None, local_tmpdir=None):
        """Initializes drone and host's environment

        Parameters remote_tmpdir and local_tmpdir are overrides of parameter
        work_dir. Usually it's enough to set work_dir which is the local base
        directory for drone and rest is created automatically.
        """
        self.info = {}
        self._modules = set()
        self._resources = set()
        self._hiera = set()
        self._manifests = []

        self._config = config
        self._shell = utils.shell.RemoteShell(host)

        # Initialize temporary directories and transfer between them
        work_dir = work_dir or project.PROJECT_TEMPDIR
        self._local_tmpdir = (
            local_tmpdir or
            tempfile.mkdtemp(prefix='host-%s-' % host, dir=work_dir)
        )
        self._remote_tmpdir = remote_tmpdir or self._local_tmpdir
        self._transfer = utils.shell.SFTPTransfer(
            host, self._remote_tmpdir, self._local_tmpdir
        )
        builddir = 'build-{}'.format(
            datetime.datetime.now().strftime(project.TIMESTAMP_FORMAT)
        )
        self._local_builddir = os.path.join(self._local_tmpdir, builddir)
        self._remote_builddir = os.path.join(self._remote_tmpdir, builddir)
        os.mkdir(self._local_builddir, 0o700)
        for subdir in (
                'modules', 'resources', 'manifests', 'logs', 'hieradata'
            ):
            os.mkdir(os.path.join(self._local_builddir, subdir), 0o700)

    def init_host(self):
        """Installs Puppet and other dependencies required for installation"""
        for cmd in project.PUPPET_INSTALLATION_COMMANDS:
            rc, stdout, stderr = self._shell.execute(cmd, can_fail=False)
            if rc == 0:
                LOG.debug(
                    'Installed Puppet on host {self._shell.host} via command '
                    '"{cmd}"'.format(**locals())
                )
                break
        else:
            raise RuntimeError(
                'Failed to install Puppet on host {self._shell.host}. '
                'None of the installation commands worked: '
                '{project.PUPPET_INSTALLATION_COMMANDS}'.format(**locals())
            )
        for cmd in project.PUPPET_DEPENDENCY_COMMANDS:
            rc, stdout, stderr = self._shell.execute(cmd, can_fail=False)
            if rc == 0:
                LOG.debug(
                    'Installed Puppet dependencies on host {self._shell.host} '
                    'via command "{cmd}"'.format(**locals())
                )
                break
        else:
            raise RuntimeError(
                'Failed to install Puppet dependencies on host {self._shell.host}. '
                'None of the installation commands worked: '
                '{project.PUPPET_DEPENDENCY_COMMANDS}'.format(**locals())
            )

    def discover(self):
        """Load information about the host."""
        # Host self.info discovery
        # Facter is installed as Puppet dependency, so we let it do the work
        rc, stdout, stderr = self._shell.execute('facter -p')
        for line in stdout.split('\n'):
            try:
                key, value = line.split('=>', 1)
            except ValueError:
                # this line is probably some warning, so let's skip it
                continue
            else:
                self.info[key.strip()] = value.strip()
        return self.info

    def _create_remote_file(self, path, content):
        content = '\n' + content.strip('\n') +'\n'
        rc, stdout, stderr = self._shell.execute(
            'cat > {path} <<EOF{content}EOF'.format(**locals())
        )

    def _get_configuration_context(self):
        conf_dict = {'host': self._shell.host}
        for key, value in project.PUPPET_CONFIGURATION_VALUES.items():
            conf_dict[key] = value.format(
                host=self._shell.host, info=self.info, config=self._config,
                tmpdir=self._remote_builddir
            )
        return conf_dict

    def configure(self):
        """Creates and saves Puppet configuration files."""
        for path, content in project.PUPPET_CONFIGURATION:
            self._create_remote_file(
                path, content.format(**self._get_configuration_context())
            )

    def add_module(self, path):
        """Registers Puppet module."""
        if not os.path.isdir(path):
            raise ValueError('Module {} does not exist.'.format(path))
        expect = set(['lib', 'manifests', 'templates'])
        real = set(os.listdir(path))
        if not (real and expect):
            raise ValueError(
                'Module {} is not a valid Puppet module.'.format(path)
            )
        LOG.debug(
            'Registering module {path} to drone '
            'of host {self._shell.host}'.format(**locals())
        )
        self._modules.add(path)

    def add_resource(self, path):
        """Registers Puppet resource."""
        if not os.path.exists(path):
            raise ValueError('Resource {} does not exist.'.format(path))
        LOG.debug(
            'Registering resource {path} to drone '
            'of host {self._shell.host}'.format(**locals())
        )
        self._resources.add(path)

    def add_manifest(self, name):
        """Renders manifest right into the build."""
        path = puppet.render_manifest(
            name,
            tmpdir=os.path.join(self._local_builddir, 'manifests'),
            config=self._config
        )
        LOG.debug(
            'Registering manifest {name} ({path}) to drone '
            'of host {self._shell.host}'.format(**locals())
        )
        self._manifests.append(path)

    def add_hiera(self, name):
        """Renders hiera file right into the build."""
        path = puppet.render_hiera(
            name,
            tmpdir=os.path.join(self._local_builddir, 'hieradata'),
        )
        LOG.debug(
            'Registering hiera {name} ({path}) to drone '
            'of host {self._shell.host}'.format(**locals())
        )
        self._hiera.add(path)

    def make_build(self):
        """Creates and transfers deployment build to remote temporary
        directory.
        """
        parent = greenlet.getcurrent().parent
        LOG.debug('Creating build {self._local_builddir}.'.format(**locals()))
        self._create_build(self._local_builddir)
        parent.switch()
        LOG.debug(
            'Transferring build {self._local_builddir} for host '
            '{self._shell.host}.'.format(**locals())
        )
        self._transfer.send(self._local_builddir, self._remote_builddir)

    def _create_build(self, builddir):
        """Creates deployment resources build."""
        host = self._shell.host
        # create build which will be used for installation on host
        LOG.debug(
            'Creating host %(host)s build in directory '
            '%(builddir)s.'% locals()
        )
        # copy yet only registered resources
        for subname in ('module', 'resource'):
            subdir = os.path.join(builddir, '{}s'.format(subname))
            key = '_{}s'.format(subname)
            if key not in self.__dict__:
                continue
            for build_file in self.__dict__[key]:
                LOG.debug(
                    'Adding {subname} {build_file} to build '
                    'of host {host}.'.format(**locals())
                )
                if os.path.isdir(build_file):
                    dest = os.path.join(subdir, os.path.basename(build_file))
                    shutil.copytree(build_file, dest)
                else:
                    shutil.copy(build_file, subdir)

    def _create_manifest_hiera(self, name):
        # update hiera.yaml config
        conf_dict = self._get_configuration_context()
        conf_dict['manifest_name'] = name
        self._create_remote_file(
            project.PUPPET_CONFIGURATION_VALUES['hiera_config'],
            project.HIERA_CONFIG.format(**conf_dict)
        )
        # create <manifest_name>.yaml data file
        self._create_remote_file(
            os.path.join(
                self._remote_builddir, 'hieradata', '{}.yaml'.format(name)
            ),
            puppet._hieralib.dump(name),
        )

    def deploy(self, name, timeout=None, debug=False):
        """Applies Puppet manifest given by name."""
        debug = '--debug' if debug else ''
        tmpdir = self._remote_builddir
        host = self._shell.host
        log = (
            '{self._remote_builddir}/logs/{name}.log'.format(**locals())
        )
        manifest = (
            '{self._remote_builddir}/manifests/{name}'.format(**locals())
        )
        # prepare manifest specific hiera file
        self._create_manifest_hiera(name)
        # spawn Puppet process
        LOG.debug(
            'Applying manifest "{name}" (remote path: {manifest}) on host '
            '{self._shell.host}.'.format(**locals())
        )
        cmd = project.PUPPET_APPLY_COMMAND.format(**locals())
        LOG.debug(
            'Running command {cmd} on host {host}.'.format(**locals())
        )
        self._shell.execute(cmd)
        # wait till Puppet process finishes
        local_log = '{self._local_builddir}/logs/{name}.log'.format(
            **locals()
        )
        start_time = time.time()
        while True:
            if timeout and (timeout <= (time.time() - start_time)):
                raise RuntimeError(
                    'Timeout reached while deploying manifest {name} '
                    'on {host}.'.format(**locals())
                )
            try:
                LOG.debug(
                    'Polling log {log} on host {host}.'.format(**locals())
                )
                self._transfer.receive(log, os.path.dirname(local_log))
            except ValueError:
                # log does not exists which means apply did not finish yet
                greenlet.getcurrent().parent.switch()
            else:
                return puppet.LogChecker().validate(local_log)

    def clean(self):
        """Removes all temporary files."""
        LOG.debug(
            'Removing temporary directory {self._remote_tmpdir} on host '
            '{self._shell.host}.'.format(**locals())
        )
        self._shell.execute(
            'rm -fr {}'.format(self._remote_tmpdir),
            can_fail=False
        )
        LOG.debug(
            'Removing local temporary directory '
            '{self._local_builddir}'.format(**locals())
        )
        shutil.rmtree(self._local_builddir, ignore_errors=True)
