# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import gevent
import logging
import os
import shutil
import stat
import tarfile
import tempfile
import uuid

from ..conf import project
from ..utils.shell import RemoteShell
from ..utils.strings import state_message

from . import puppet


logger = logging.getLogger('kanzo.backend')


class TarballTransfer(object):
    def __init__(self, host, remote_tmpdir, local_tmpdir):
        self._shell = RemoteShell(host)
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
            raise ValueError('Given local path does not exists: %(source)s'
                             % locals())
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
            self._shell.execute('rm -f %(tmpfile)s' % locals())

    def receive(self, source, destination):
        """Packs given remote source directory/file to tarball, transfers it
        and unpacks to given local destination directory/file. Type of
        destination is always taken from type of source, eg. if souce is file
        then destination have to be file too.
        """
        # packing
        rc, stdout, stderr = self._shell.execute(
                                '[ -e "%(source)s" ]' % locals(),
                                can_fail=False)
        if rc:
            host = self._shell.node
            raise ValueError('Given path on host %(host)s does not exists: '
                             '%(source)s' % locals())
        rc, stdout, stderr = self._shell.execute(
                                '[ -d "%(source)s" ]' % locals(),
                                can_fail=False)
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
            self._shell.execute('rm -f %(tarball)s' % locals())

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
            os.makedirs(self._local_tmpdir, mode=0700)
        except OSError as ex:
            # check if the error is only because directory already exists
            if (getattr(ex, 'errno', 13) != 17 or
                'exists' not in str(ex).lower()):
                raise
        return self._local_tmpdir

    def _check_remote_tmpdir(self):
        tmpdir = self._remote_tmpdir
        self._shell.execute('mkdir -p --mode=0700 %(tmpdir)s' % locals())
        return tmpdir

    def _pack_local(self, path, is_dir):
        tmpdir = self._check_local_tmpdir()
        packpath = os.path.join(tmpdir,
                                'transfer-%s.tar.gz' % uuid.uuid4().hex[:8])
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
        packpath = os.path.join(tmpdir,
                                'transfer-%s.tar.gz' % uuid.uuid4().hex[:8])
        if is_dir:
            prefix = '-C %s' % path
            rc, stdout, stderr = self._shell.execute('ls %(path)s' % locals())
            path = ' '.join([i.strip() for i in stdout.split() if i])
        else:
            prefix = '-C %s' % os.path.dirname(path)
            path = os.path.basename(path)
        self._shell.execute('tar %(prefix)s -cpzf %(packpath)s %(path)s'
                            % locals())
        return packpath

    def _unpack_local(self, path, destination, is_dir):
        if not is_dir:
            destination = os.path.dirname(destination)
        with tarfile.open(path, mode='r') as pack:
            pack.extractall(path=destination)

    def _unpack_remote(self, path, destination, is_dir):
        if not is_dir:
            destination = os.path.dirname(destination)
        self._shell.execute('mkdir -p --mode=0700 %(destination)s' % locals())
        self._shell.execute('tar -C %(destination)s -xpzf %(path)s'
                            % locals())


class Drone(object):
    """Drone class is the Puppet worker for single host. It manages
    initialization, manifest application and cleanup."""

    def __init__(self, config, node, observer, remote_tmpdir=None,
                 local_tmpdir=None, work_dir=None):
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
        self._observer = observer
        self._checker = puppet.LogChecker()

        # Initialize node for manipulation:
        # 1. Creates temporary directories and tranfer
        work_dir = work_dir or project.PROJECT_TEMPDIR
        self._local_tmpdir = local_tmpdir or tempfile.mkdtemp(
                                                    prefix='host-%s-' % node,
                                                    dir=work_dir)
        self._remote_tmpdir = remote_tmpdir or self._local_tmpdir
        self._transfer = TarballTransfer(node, self._remote_tmpdir,
                                         self._local_tmpdir)

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


    def setup(self):
        """Builds manifests from template and copies them together with modules
        and resources to host.
        """

        self._logdir = os.path.join(self._local_tmpdir, 'logs')
        build_dir = os.path.join(self._local_tmpdir,
                                 'build-%s' % uuid.uuid4().hex[:8])
        os.mkdir(build_dir, mode=0700)
        os.mkdir(self._logdir, mode=0700)
        # create Puppet build which will be used for installation on host
        for subdir in ('manifests', 'modules', 'resources', 'logs'):
            os.mkdir(os.path.join(build_dir, subdir), mode=0700)

        manifest_dir = os.path.join(build_dir, 'manifests')
        for marker, templates in self._manifests.items():
            logger.debug('Building manifest templates with marker %(marker)s '
                         'to directory %(manifest_dir)s.' % locals())
            for tmplt in templates:
                logger.debug('Building manifest from template %s' % tmplt.path)
                tmplt.render(manifest_dir)

        module_dir = os.path.join(build_dir, 'modules')
        for module in self._modules:
            logger.debug('Adding module %(module)s to host %(node)s build.'
                         % locals())
            shutil.copytree(module,
                            os.path.join(module_dir, os.path.basename(module)))

        resource_dir = os.path.join(build_dir, 'resources')
        for resource in self._resources:
            logger.debug('Adding resource %(resource)s to host %(node)s build.'
                         % locals())
            if os.path.isdir(resource):
                dest = os.path.join(resource_dir, os.path.basename(resource))
                shutil.copytree(resource, dest)
            else:
                shutil.copy(resource, resource_dir)
        # transfer build
        self._build_dir = os.path.join(self._remote_tmpdir,
                                       os.path.basename(build_dir))
        self._transfer.send(build_dir, self._build_dir)

    def cleanup(self, local=True, remote=True):
        """Removes all remote files created by this drone."""
        if local:
            shutil.rmtree(self._local_tmpdir)
        if remote:
            self._shell.execute('rm -fr %s' % self._remote_tmpdir,
                                can_fail=False)

    def add_manifest(self, path, context=None, marker=None):
        """Registers manifest templates for application on node. Manifests will
        be applied in order the templates were registered to drone. Multiple
        manifests can be applied in paralel if they have same marker. Parameter
        context can be a dict with additional variables which meant to be
        used in manifest template.
        """
        marker = marker or uuid.uuid4().hex[:8]
        template = puppet.ManifestTemplate(path, self._config, context=context)
        self._manifests.setdefault(marker, []).append(template)
        return marker

    def add_module(self, path):
        """Registers Puppet module."""
        if not os.path.isdir(path):
            raise ValueError('Module %s does not exist.' % path)
        expect = set(['lib', 'manifests', 'templates'])
        real = set(os.listdir(path))
        if not (real and expect):
            raise ValueError('Module is not a valid Puppet module.' % path)
        self._modules.append(path)

    def add_resource(self, path):
        """Registers Puppet resource."""
        if not os.path.exists(path):
            raise ValueError('Resource %s does not exist.' % path)
        self._resources.append(path)

    def configure(self, marker=None, name=None, skip=None):
        """Applies all registered manifests on node. If marker is specified,
        only manifest(s) with given marker are applied. If name is specified
        only manifest with given name is applied. Skips manifests with names
        given in list parameter skip.
        """
        skip = skip or []
        lastmarker = None
        for mark, manifests in self._manifests.items():
            if marker and marker != mark:
                logger.debug('Skipping manifests with marker %s for host %s.' %
                             (mark, self._shell.host))
                continue
            for manifest in manifests:
                base = os.path.basename(manifest)
                if (name and name != base) or base in skip:
                    logger.debug('Skipping manifest %s on host %s.' %
                                 (recipe, self._shell.host))
                    continue

                # If the marker has changed then we don't want to proceed
                # until all of the previous puppet runs have finished
                if lastmarker and lastmarker != mark:
                    self._wait()
                lastmarker = mark

                manifest_path = os.path.join(self._build_dir, 'manifests',
                                             base)
                self._observer.applying(self, manifest_path)
                self._apply(manifest_path)
        self._wait()

    def _apply(self, manifest):
        """Applies single manifest given by name."""
        base = os.path.basename(manifest)
        running = os.path.join(self._build_dir, 'logs', '%s.running' % base)
        finished = os.path.join(self._build_dir, 'logs', '%s.finished' % base)
        self._shell.execute('touch %s' % running)
        self._shell.execute('chmod 600 %s' % running)

        loglevel = logger.level <= logging.DEBUG and '--debug' or ''
        module_dir = os.path.join(self._build_dir, 'modules')
        resource_dir = os.path.join(self._build_dir, 'resources')
        self._running.add(manifest)
        self._shell.execute(
            "( flock %(resource_dir)s/ps.lock "
                 "puppet apply %(loglevel)s --modulepath %(module_dir)s "
                 "%(manifest)s > %(running)s 2>&1 < /dev/null; "
               "mv %(running)s %(finished)s ) "
            "> /dev/null 2>&1 < /dev/null &" % locals())

    def _wait(self):
        """Waits until all started applications of manifests will be finished.
        """
        while self._running:
            _run = list(self._running)
            for manifest in _run:
                self._observer.checking(self, manifest)
                if self._finished(manifest):
                    self._applied.add(manifest)
                    self._running.remove(manifest)
            gevent.sleep(3)

    def _finished(self, manifest):
        base = os.path.basename(manifest)
        finished = os.path.join(self._build_dir, 'logs', '%s.finished' % base)
        log = os.path.join(self._logdir, '%s.%s' % (base, 'log'))
        try:
            self._transfer.receive(finished, log)
        except ValueError:
            # Puppet run did not finish yet.
            return False
        else:
            self._observer.finished(self, manifest, log)
            return True


class DroneObserver(object):
    """Class for listening messages from drones."""
    def __init__(self):
        self._ignore = project.PUPPET_FINISH_ON_ERROR
        self._checker = puppet.LogChecker()

    def applying(self, drone, manifest):
        """Drone is calling this method when it starts applying manifest."""
        msg = ('Applying manifest %s on node %s'
               % (os.path.basename(manifest), drone._shell.node))
        logger.debug(msg)
        print(msg)

    def checking(self, drone, manifest):
        """Drone is calling this method when it starts checking if manifest
        has been applied.
        """
        msg = ('Checking manifest %s application on node %s'
               % (os.path.basename(manifest), drone._shell.node))
        logger.debug(msg)

    def finished(self, drone, manifest, log):
        """Drone is calling this method when it's finished with manifest
        application.
        """
        title = ('[%s] Manifest %s application'
                 % (drone._shell.node, os.path.basename(manifest)))
        try:
            self._checker.validate(log)
            print(state_message(title, 'DONE', 'green'))
        except RuntimeError:
            logger.warning('Manifest %s application on node %s failed. '
                           'You will find full Puppet log at %s'
                            % (os.path.basename(manifest),
                               drone._shell.node, log))
            print(state_message(title, 'FAIL', 'red'))
            if not self._ignore:
                raise
