# -*- coding: utf-8 -*-

import collections
import datetime
import greenlet
import logging
import os
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import uuid

from ..conf import project
from ..utils import shell
from ..utils import strings

from . import puppet


LOG = logging.getLogger('kanzo.backend')


class TarballTransfer(object):
    def __init__(self, host, remote_tmpdir, local_tmpdir):
        self._shell = shell.RemoteShell(host)
        self._remote_tmpdir = remote_tmpdir
        self._local_tmpdir = local_tmpdir

    def send(self, source, destination):
        """Packs given local source directory/file to tarball, transfers it and
        unpacks to given remote destination directory/file. Type of destination
        is always taken from type of source, eg. if souce is file then
        destination have to be file too.
        """
        # packing
        if not os.path.exists(source):
            raise ValueError(
                'Given local path does not exists: '
                '{source}'.format(**locals())
            )
        is_dir = os.path.isdir(source)
        tarball = self._pack_local(source, is_dir)
        # preparation
        tmpdir = self._check_remote_tmpdir()
        tmpfile = os.path.join(tmpdir, os.path.basename(tarball))
        # transfer and unpack
        try:
            self._transfer(tarball, tmpfile, is_dir, sourcetype='local')
            self._unpack_remote(tmpfile, destination, is_dir)
        finally:
            os.unlink(tarball)
            self._shell.execute('rm -f {tmpfile}'.format(**locals()))

    def receive(self, source, destination):
        """Packs given remote source directory/file to tarball, transfers it
        and unpacks to given local destination directory/file. Type of
        destination is always taken from type of source, eg. if source is file
        then destination have to be file too.
        """
        # packing
        rc, stdout, stderr = self._shell.execute(
            '[ -e "{source}" ]'.format(**locals()),
            can_fail=False
        )
        if rc:
            host = self._shell.host
            raise ValueError(
                'Given path on host {host} does not exists: '
                '{source}'.format(**locals())
            )
        rc, stdout, stderr = self._shell.execute(
            '[ -d "{source}" ]'.format(**locals()),
            can_fail=False
        )
        is_dir = not bool(rc)
        tarball = self._pack_remote(source, is_dir)
        # preparation
        tmpdir = self._check_local_tmpdir()
        tmpfile = os.path.join(tmpdir, os.path.basename(tarball))
        # transfer and unpack
        try:
            self._transfer(tarball, tmpfile, is_dir, sourcetype='remote')
            self._unpack_local(tmpfile, destination, is_dir)
        finally:
            os.unlink(tmpfile)
            self._shell.execute('rm -f {tarball}'.format(**locals()))

    def _transfer(self, source, destination, is_dir, sourcetype):
        try:
            sftp = self._shell._client.open_sftp()
            if sourcetype == 'local':
                direction = sftp.put
            else:
                direction = sftp.get
            direction(source, destination)
        finally:
            sftp.close()

    def _check_local_tmpdir(self):
        try:
            os.makedirs(self._local_tmpdir, mode=0o700)
        except OSError as ex:
            # check if the error is only because directory already exists
            if (getattr(ex, 'errno', 13) != 17 or
                'exists' not in str(ex).lower()):
                raise
        return self._local_tmpdir

    def _check_remote_tmpdir(self):
        tmpdir = self._remote_tmpdir
        self._shell.execute(
            'mkdir -p --mode=0700 {tmpdir}'.format(**locals())
        )
        return tmpdir

    def _pack_local(self, path, is_dir):
        tmpdir = self._check_local_tmpdir()
        packpath = os.path.join(
            tmpdir, 'transfer-{0}.tar.gz'.format(uuid.uuid4().hex[:8])
        )
        with tarfile.open(packpath, mode='w:gz') as pack:
            if is_dir:
                for fname in os.listdir(path):
                    src = os.path.join(path, fname)
                    pack.add(src, arcname=fname)
            else:
                pack.add(path, arcname=os.path.basename(path))
        os.chmod(packpath, stat.S_IRUSR | stat.S_IWUSR)
        return packpath

    def _pack_remote(self, path, is_dir):
        tmpdir = self._check_remote_tmpdir()
        packpath = os.path.join(
            tmpdir, 'transfer-{0}.tar.gz'.format(uuid.uuid4().hex[:8])
        )
        if is_dir:
            prefix = '-C {path}'.format(**locals())
            rc, stdout, stderr = self._shell.execute(
                'ls {path}'.format(**locals())
            )
            path = ' '.join([i.strip() for i in stdout.split() if i])
        else:
            prefix = '-C {0}'.format(os.path.dirname(path))
            path = os.path.basename(path)
        self._shell.execute(
            'tar {prefix} -cpzf {packpath} {path}'.format(**locals())
        )
        return packpath

    def _unpack_local(self, path, destination, is_dir):
        if not is_dir:
            base = os.path.basename(destination)
            destination = os.path.dirname(destination)
        with tarfile.open(path, mode='r') as pack:
            current = os.path.basename(pack.getnames()[0])
            pack.extractall(path=destination)
        if not is_dir:
            shutil.move(os.path.join(destination, current),
                        os.path.join(destination, base))

    def _unpack_remote(self, path, destination, is_dir):
        if not is_dir:
            destination = os.path.dirname(destination)
        self._shell.execute(
            'mkdir -p --mode=0700 {destination}'.format(**locals())
        )
        self._shell.execute(
            'tar -C {destination} -xpzf {path}'.format(**locals())
        )


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
        self._manifests = []

        self._config = config
        self._shell = shell.RemoteShell(host)

        # Initialize temporary directories and transfer between them
        work_dir = work_dir or project.PROJECT_TEMPDIR
        self._local_tmpdir = (
            local_tmpdir or
            tempfile.mkdtemp(prefix='host-%s-' % host, dir=work_dir)
        )
        self._remote_tmpdir = remote_tmpdir or self._local_tmpdir
        self._transfer = TarballTransfer(
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

    def configure(self):
        """Creates and saves configuration Puppet files."""
        # Puppet self._configuration
        for path, content in project.PUPPET_CONFIGURATION:
            # preparation
            conf_dict = {'host': self._shell.host}
            # formatting
            for key, value in project.PUPPET_CONFIGURATION_VALUES.items():
                conf_dict[key] = value.format(
                    host=self._shell.host, info=self.info, config=self._config,
                    tmpdir=self._remote_builddir
                )
            content = content.format(**conf_dict)
            # execution
            rc, stdout, stderr = self._shell.execute(
                'cat > {path} <<EOF{content}EOF'.format(**locals())
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
        path = puppet._manifestlib.render(
            name,
            tmpdir=os.path.join(self._local_builddir, 'manifests'),
            config=self._config
        )
        LOG.debug(
            'Registering manifest {name} ({path}) to drone '
            'of host {self._shell.host}'.format(**locals())
        )
        self._manifests.append(path)

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
        for subname in ('module', 'resource', 'manifest', 'log'):
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
        for name, content in puppet.render_hiera():
            path = os.path.join(builddir, 'hieradata', '{}.yaml'.format(name))
            with open(path, 'w') as hierafile:
                hierafile.write(content)

    def deploy(self, name, timeout=None, debug=False):
        """Applies Puppet manifest given by name."""
        # prepare variables for Puppet command
        debug = '--debug' if debug else ''
        tmpdir = self._remote_builddir
        host = self._shell.host
        log = (
            '{self._remote_builddir}/logs/{name}.log'.format(**locals())
        )
        manifest = (
            '{self._remote_builddir}/manifests/{name}'.format(**locals())
        )
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
            if timeout and (timeout >= time.time() - start_time):
                raise RuntimeError(
                    'Timeout reached while deploying manifest {name} '
                    'on {host}.'.format(**locals())
                )
            try:
                LOG.debug(
                    'Polling log {log} on host {host}.'.format(**locals())
                )
                self._transfer.receive(log, local_log)
            except ValueError:
                # log does not exists which means apply did not finish yet
                greenlet.getcurrent().parent.switch()
            else:
                return puppet.LogChecker.validate(local_log)

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
