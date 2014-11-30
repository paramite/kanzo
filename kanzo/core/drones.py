# -*- coding: utf-8 -*-

import collections
import greenlet
import logging
import os
import shutil
import stat
import sys
import tarfile
import tempfile
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


def initialize_host(sh, config, messages,
                    init_steps=None, prepare_steps=None):
    """Installs Puppet and other dependencies required for installation.
    Discovers and returns dict which contains host information.

    In case init_steps list is given all steps are run before Puppet
    installation.

    In case prepare_steps list is given all steps are run after Puppet
    and it's dependencies are installed and initialized.

    init_step items have to be callables accepting parameters
    (host, config, messages).
    prepare_step items have to be callables accepting parameters
    (host, config, info, messages).

    host - str containing hostname or IP
    config - kanzo.conf.Config instance
    info - dict containing host information
    messages - list containing output messages
    """
    init_steps = init_steps or []
    prepare_steps = prepare_steps or []
    for step in init_steps:
        step(
            host=sh.host,
            config=config,
            messages=messages
        )

    for cmd in project.PUPPET_INSTALLATION_COMMANDS:
        rc, stdout, stderr = sh.execute(cmd, can_fail=False)
        if rc == 0:
            LOG.debug(
                'Installed Puppet on host {sh.host} via command '
                '"{cmd}"'.format(**locals())
            )
            break
    else:
        raise RuntimeError(
            'Failed to install Puppet on host {sh.host}. '
            'None of the installation commands worked: '
            '{project.PUPPET_INSTALLATION_COMMANDS}'.format(**locals())
        )
    for cmd in project.PUPPET_DEPENDENCY_COMMANDS:
        rc, stdout, stderr = sh.execute(cmd, can_fail=False)
        if rc == 0:
            LOG.debug(
                'Installed Puppet dependencies on host {sh.host} '
                'via command "{cmd}"'.format(**locals())
            )
            break
    else:
        raise RuntimeError(
            'Failed to install Puppet dependencies on host {sh.host}. '
            'None of the installation commands worked: '
            '{project.PUPPET_DEPENDENCY_COMMANDS}'.format(**locals())
        )
    # Facter is installed as Puppet dependency, so we let it do the work
    info = {}
    rc, stdout, stderr = sh.execute('facter -p')
    for line in stdout.split('\n'):
        try:
            key, value = line.split('=>', 1)
        except ValueError:
            # this line is probably some warning, so let's skip it
            continue
        else:
            info[key.strip()] = value.strip()

    for step in prepare_steps:
        step(
            host=sh.host,
            config=config,
            info=info,
            messages=messages
        )
    return info


class Drone(object):
    """Drone manages host where Puppet agent has to run. It prepares
    environment on host and registers it to Puppet master which is managed
    by class kanzo.core.Controller
    """

    def __init__(self, host, config, work_dir=None,
                 remote_tmpdir=None, local_tmpdir=None):
        """Initializes drone and host's environment. Parameters
        remote_tmpdir and local_tmpdir are overrides of parameter work_dir.
        Usually it's enough to set work_dir which is the local base directory
        for drone and rest is created automatically.
        """
        self._modules = set()
        self._resources = set()

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

    def prepare_and_discover(self, messages, init_steps=None,
                             prepare_steps=None):
        self.info = initialize_host(
            self._shell, self._config, messages,
            init_steps=init_steps,
            prepare_steps=prepare_steps
        )
        return self.info

    def cleanup(self, local=True, remote=True):
        """Removes all remote files created by this drone."""
        if local:
            shutil.rmtree(self._local_tmpdir, ignore_errors=True)
        if remote:
            self._shell.execute('rm -fr %s' % self._remote_tmpdir,
                                can_fail=False)

    def add_module(self, path):
        """Registers Puppet module."""
        if not os.path.isdir(path):
            raise ValueError('Module %s does not exist.' % path)
        expect = set(['lib', 'manifests', 'templates'])
        real = set(os.listdir(path))
        if not (real and expect):
            raise ValueError('Module is not a valid Puppet module.' % path)
        self._modules.add(path)

    def add_resource(self, path):
        """Registers Puppet resource."""
        if not os.path.exists(path):
            raise ValueError('Resource %s does not exist.' % path)
        self._resources.add(path)

    def make_build(self):
        """Copies modules and resources to remote temporary directory."""
        builddir = 'build-%s' % uuid.uuid4().hex[:8]
        self._local_builddir = os.path.join(self._local_tmpdir, builddir)
        self._remote_builddir = os.path.join(self._remote_tmpdir, builddir)

        self._create_build(self._local_builddir)
        self._transfer.send(self._local_builddir, self._remote_builddir)

    def _create_build(self, builddir):
        """Creates deployment resources build and transfers it to remote
        temporary directory.
        """
        host = self._shell.host

        os.mkdir(builddir, 0o700)
        # create build which will be used for installation on host
        LOG.debug(
            'Creating host %(host)s build in directory '
            '%(builddir)s.'% locals()
        )
        for subdir in ('modules', 'resources'):
            os.mkdir(os.path.join(builddir, subdir), 0o700)

        module_dir = os.path.join(builddir, 'modules')
        for module in self._modules:
            LOG.debug(
                'Adding module %(module)s to host %(host)s build.'% locals()
            )
            shutil.copytree(
                module, os.path.join(module_dir, os.path.basename(module))
            )

        resource_dir = os.path.join(builddir, 'resources')
        for resource in self._resources:
            LOG.debug(
                'Adding resource %(resource)s to host %(host)s '
                'build.'% locals()
            )
            if os.path.isdir(resource):
                dest = os.path.join(resource_dir, os.path.basename(resource))
                shutil.copytree(resource, dest)
            else:
                shutil.copy(resource, resource_dir)

    def register(self, master):
        """Registers host as Puppet agent."""
        result = getattr(self, '_puppet_fingerprint', None)
        if not result:
            rc, stdout, stderr = self._shell.execute(
                'puppet agent --test --server={master}'.format(**locals())
            )
            self._puppet_fingerprint = puppet.parse_crf(stdout)
        return self._puppet_fingerprint
