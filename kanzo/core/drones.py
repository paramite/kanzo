# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import logging
import os
import shutil
import stat
import tarfile
import tempfile
import uuid

from ..conf import project
from ..utils.shell import RemoteShell

from .puppet import ManifestTemplate


logger = logging.getLogger('kanzo.backend')


class TarballTransfer(object):
    def __init__(self, host, remote_tmpdir):
        self._host = host
        self._tmpdir = remote_tmpdir

    def transfer(self, source, destination):
        """Packs given source directory to tarball, transfers it and unpacks
        to detination directory. Destination has to be in format 'host:/path'.
        If destination directory does not exist it is created
        """
        # packing
        tarball = self._pack(source)
        # preparation
        tmpdir = self._tmpdir
        shell = RemoteShell(self._host)
        shell.execute('mkdir -p --mode=0700 %(tmpdir)s' % locals())
        shell.execute('mkdir -p --mode=0700 %(destination)s' % locals())
        # transfer
        tmpfile = os.path.join(tmpdir, os.path.basename(tarball))
        try:
            sftp = shell._client.open_sftp()
            sftp.put(tarball, tmpfile)
            shell.execute('tar -C %(destination)s -xpzf %(tmpfile)s'
                          % locals())
        finally:
            os.unlink(tarball)
            shell.execute('rm -f %(tmpfile)s' % locals())

    def _pack(self, path):
        packpath = os.path.join(project.PROJECT_TEMPDIR,
                                'transfer-%s.tar.gz' % uuid.uuid4().hex[:8])
        with tarfile.open(packpath, mode='w:gz') as pack:
            for fname in os.listdir(path):
                src = os.path.join(path, fname)
                pack.add(src, arcname=fname)
        os.chmod(packpath, stat.S_IRUSR | stat.S_IWUSR)
        return packpath


class Drone(object):

    def __init__(self, config, node, remote_tmpdir=None, local_tmpdir=None,
                 work_dir=None):
        """Initializes drone and host for manifest application. Parameters
        remote_tmpdir and local_tmpdir are overrides. Usually it's enough
        to set work_dir which is the local base directory for drone and rest
        is created automatically.
        """
        self._manifests = utils.SortedDict()
        self._modules = []
        self._resources = []

        self._applied = set()
        self._running = set()

        self._config = config
        self._shell = RemoteShell(node)

        # Initialize node for manipulation:
        # 1. Creates temporary directories
        work_dir = work_dir or project.PROJECT_TEMPDIR
        self._local_tmpdir = local_tmpdir or tempfile.mkdtemp(
                                                    prefix='host-%s-' % node,
                                                    dir=work_dir)
        self._remote_tmpdir = remote_tmpdir or self._local_tmpdir

        # 2. Installs Puppet
        for cmd in project.PUPPET_INSTALLATION_COMMANDS:
            rc, stdout, stderr = self._shell.execute(cmd, can_fail=True)
            if rc == 0:
                logger.debug('Installed Puppet on host %(node)s via command '
                             '"%(cmd)s"' % locals())
                break
        else:
            raise RuntimeError('Failed to install Puppet on host %s. '
                               'None of the installation commands worked: %s'
                               % (node, project.PUPPET_INSTALLATION_COMMANDS))

        # 3. Discover host info
        # Facter is installed as Puppet dependency, so we let it do the work
        self.info = {}
        rc, stdout, stderr = self._shell.execute('facter -p')
        for line in stdout.split('\n'):
            try:
                key, value = line.split('=>', 1)
            except ValueError:
                # this line is probably some warning, so let's skip it
                continue
            else:
                self.info[key.strip()] = value.strip()

    def prepare(self):
        """Builds manifests from template and copies them together with modules
        and resources to host.
        """
        # create Puppet build which will be used for installation on host
        for subdir in ('manifests', 'modules', 'resources', 'logs'):
            os.mkdir(os.path.join(self._local_tmpdir, subdir), mode=0700)

        manifest_dir = os.path.join(self._local_tmpdir, 'manifests')
        for marker, templates in self._manifests.items():
            logger.debug('Building manifest templates with marker %(marker)s '
                         'to directory %(manifest_dir)s.' % locals())
            for tmplt in templates:
                logger.debug('Building manifest from template %s' % tmplt.path)
                tmplt.render(manifest_dir)

        module_dir = os.path.join(self._local_tmpdir, 'modules')
        for module in self._modules:
            logger.debug('Adding module %(module)s to host %(node)s build.'
                         % locals())
            shutil.copytree(module,
                            os.path.join(module_dir, os.path.basename(module)))

        resource_dir = os.path.join(self._local_tmpdir, 'resources')
        for resource in self._resources:
            logger.debug('Adding resource %(resource)s to host %(node)s build.'
                         % locals())
            if os.path.isdir(resource)
                dest = os.path.join(resource_dir, os.path.basename(resource))
                shutil.copytree(resource, dest)
            else:
                shutil.copy(resource, resource_dir)

        # transfer build
        transfer = TarballTransfer(self._shell.host, self._remote_tmpdir)
        transfer.transfer(self._local_tmpdir, self._remote_tmpdir)

    def add_manifest(self, path, context=None, marker=None):
        """Registers manifest templates for application on node. Manifests will
        be applied in order the templates were registered to drone. Multiple
        manifests can be applied in paralel if they have same marker. Parameter
        context can be a dict with additional variables which meant to be
        used in manifest template.
        """
        marker = marker or uuid.uuid4().hex[:8]
        template = ManifestTemplate(path, self._config, context=context)
        self._manifests.setdefault(marker, []).append(template)
        return marker

    def add_module(self, path):
        """Registers Puppet module."""
        if not os.path.isdir(path):
            raise ValueError('Module %s does not exist.' % path)
        expect = set(['lib', 'manifests', 'templates'])
        real = set(os.listdir(path))
        if not (real and expect):
            raise ValueError('Module or is not a valid Puppet module.' % path)
        self._modules.append(path)

    def add_resource(self, path):
        """Registers Puppet resource."""
        if not os.path.exists(path):
            raise ValueError('Resource %s does not exist.' % path)
        self._resources.append(path)

    def _wait(self):
        """Waits until all started applications of manifests will be finished.
        """

    def apply(self, marker=None, name=None, skip=None):
        """Applies manifests on node. If marker is specified, only manifest(s)
        with given marker are applied. If name is specified only manifest
        with given name is applied. Skips manifests with names given in list
        parameter skip.
        """

    def cleanup(self, local=True, remote=True):
        """Removes all remote files created by this drone."""
        if local:
            shutil.rmtree(self._local_tmpdir)
        if remote:
            self._shell.execute('rm -fr %s' % , can_fail=True)
