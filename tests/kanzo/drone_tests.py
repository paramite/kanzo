# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import sys

from kanzo.conf import Config
from kanzo.core.drones import TarballTransfer, Drone
from kanzo.core.plugins import meta_builder
from kanzo.utils import PYTHON, shell

from ..plugins import sql, nosql
from . import _KANZO_PATH
from . import BaseTestCase


def init_step(host, config, messages):
    sh = shell.RemoteShell(host)
    sh.execute('echo "initialization"')


def prepare_step(host, config, info, messages):
    if not ('domain' in info and 'osfamily' in info and 'uptime' in info):
        raise AssertionError('Invalid host info passed to preparation step')
    sh = shell.RemoteShell(host)
    sh.execute('echo "preparation"')


class TarballTransferTestCase(BaseTestCase):

    def setUp(self):
        if PYTHON == 2:
            super(TarballTransferTestCase, self).setUp()
        else:
            super().setUp()
        # test file
        self.testfile = os.path.join(self._tmpdir, 'file1.foo')
        with open(self.testfile, 'w') as foo:
            foo.write('test')
        # test directory
        self.testdir = os.path.join(self._tmpdir, 'foodir')
        os.mkdir(self.testdir)
        with open(os.path.join(self.testdir, 'file2.foo'), 'w') as foo:
            foo.write('test')

    def test_local_remote_file_transfer(self):
        """[TarballTransfer] Test local->remote file transfer"""
        host = '10.66.66.01'
        transfer = TarballTransfer(host, '/foo', self._tmpdir)
        transfer.send(self.testfile, '/foo/file1.foo')
        # test transfer on remote side
        self.check_history(host, [
            'mkdir \-p \-\-mode=0700 /foo',
            'mkdir \-p \-\-mode=0700 /foo',
            'tar \-C /foo \-xpzf /foo/transfer\-\w{8}\.tar\.gz',
            'rm \-f /foo/transfer\-\w{8}\.tar\.gz',
        ])

    def test_local_remote_dir_transfer(self):
        """[TarballTransfer] Test local->remote directory transfer"""
        host = '20.66.66.02'
        transfer = TarballTransfer(host, '/foo', self._tmpdir)
        transfer.send(self.testdir, '/foo/foodir')
        # test transfer on remote side
        self.check_history(host, [
            'mkdir \-p \-\-mode=0700 /foo',
            'mkdir \-p \-\-mode=0700 /foo/foodir',
            'tar \-C /foo/foodir \-xpzf /foo/transfer\-\w{8}\.tar\.gz',
            'rm \-f /foo/transfer\-\w{8}\.tar\.gz',
        ])

    def test_remote_local_file_transfer(self):
        """[TarballTransfer] Test remote->local file transfer"""
        host = '30.66.66.03'
        transfer = TarballTransfer(host, '/bar', self._tmpdir)
        shell.RemoteShell.register_execute(
            host, '[ -e "/path/to/file2.bar" ]',
            0, '', ''
        )
        shell.RemoteShell.register_execute(
            host, '[ -d "/path/to/file2.bar" ]',
            -1, '', ''
        )
        try:
            transfer.receive('/path/to/file2.bar', self.testfile)
        except Exception:
            # transfer will fail because no file was actually
            # transferfed, so we just ignore it
            pass
        # test transfer on remote side
        self.check_history(host, [
            '\[ \-e "/path/to/file2\.bar" \]',
            '\[ \-d "/path/to/file2\.bar" \]',
            'mkdir \-p \-\-mode=0700 /bar',
            ('tar \-C /path/to \-cpzf /bar/transfer\-\w{8}\.tar\.gz '
                'file2.bar'),
        ])

    def test_remote_local_dir_transfer(self):
        """[TarballTransfer] Test remote->local directory transfer"""
        host = '40.66.66.04'
        transfer = TarballTransfer(host, '/bar', self._tmpdir)
        shell.RemoteShell.register_execute(
            host, '[ -e "/path/to/foodir" ]',
            0, '', ''
        )
        shell.RemoteShell.register_execute(
            host, '[ -d "/path/to/foodir" ]',
            0, '', ''
        )
        try:
            transfer.receive('/path/to/foodir', self.testdir)
        except Exception:
            # transfer will fail because no directory was actually
            # transferfed, so we just ignore it
            pass
        # test transfer on remote side
        self.check_history(host, [
            '\[ \-e "/path/to/foodir" \]',
            '\[ \-d "/path/to/foodir" \]',
            'mkdir \-p \-\-mode=0700 /bar',
            'ls /path/to/foodir',
            'tar \-C /path/to/foodir \-cpzf /bar/transfer\-\w{8}\.tar\.gz',
        ])

class DroneTestCase(BaseTestCase):

    def setUp(self):
        if PYTHON == 2:
            super(DroneTestCase, self).setUp()
        else:
            super().setUp()
        self._path = os.path.join(_KANZO_PATH, 'kanzo/tests/test_config.txt')
        meta = meta_builder([sql])
        self._config = Config(self._path, meta)
        self._drone1 = Drone('10.0.0.1', self._config, work_dir=self._tmpdir)
        self._drone2 = Drone('10.0.0.2', self._config, work_dir=self._tmpdir)
        self._drone3 = Drone('10.0.0.3', self._config, work_dir=self._tmpdir)

    def test_drone_init(self):
        """[Drone] Test Drone initialization"""
        host = '10.0.0.1'
        shell.RemoteShell.register_execute(
            host,
            'facter -p',
            0,
            'domain => redhat.com\nosfamily => RedHat\nuptime => 11 days',
            ''
        )
        info = self._drone1.prepare_and_discover(
            ['test message'],
            init_steps=[init_step],
            prepare_steps=[prepare_step]
        )
        self.check_history(host, [
            'echo "initialization"',
            'yum install -y puppet puppet-server',
            'yum install -y tar ',
            'facter -p',
            'echo "preparation"'
        ])
        self.assertIn('domain', info)
        self.assertEquals(info['domain'], 'redhat.com')
        self.assertIn('osfamily', info)
        self.assertEquals(info['osfamily'], 'RedHat')
        self.assertIn('uptime', info)
        self.assertEquals(info['uptime'], '11 days')

    def test_drone_register(self):
        """[Drone] Test Puppet agent registering"""
        host = '10.0.0.2'
        shell.RemoteShell.register_execute(
            host,
            'puppet agent --fingerprint',
            0,
            '(SHA256) AA:A6:66:AA:AA',
            ''
        )
        fingerprint = self._drone2.register(host)
        self.assertEquals(('SHA256', 'AA:A6:66:AA:AA'), fingerprint)

    def test_drone_build(self):
        """[Drone] Test Drone build register and transfer"""
        host = '10.0.0.3'
        module_path = os.path.join(self._tmpdir, 'module_test')
        manifests_path = os.path.join(module_path, 'manifests', )
        os.makedirs(manifests_path)
        with open(os.path.join(manifests_path, 'init.pp'), 'w') as res:
            res.write('class test {}')
        resource_path = os.path.join(self._tmpdir, 'resource_test.pem')
        with open(resource_path, 'w') as res:
            res.write('test')
        self._drone3.add_resource(resource_path)
        self._drone3.add_module(module_path)
        self._drone3.make_build()

        self.assertEquals({resource_path}, self._drone3._resources)
        self.assertEquals({module_path}, self._drone3._modules)
        _locals = locals()
        self.check_history(host, [
            ('mkdir -p --mode=0700 {self._tmpdir}/'
                'host-10.0.0.3-\w{{6}}'.format(**_locals)),
            ('mkdir -p --mode=0700 {self._tmpdir}/'
                'host-10.0.0.3-\w{{6}}/build-\w{{8}}'.format(**_locals)),
            ('tar -C {self._tmpdir}/host-10.0.0.3-\w{{6}}/build-\w{{8}} '
                '-xpzf {self._tmpdir}/host-10.0.0.3-\w{{6}}/'
                'transfer-\w{{8}}.tar.gz'.format(**_locals)),
            ('rm -f {self._tmpdir}/host-10.0.0.3-\w{{6}}/'
                'transfer-\w{{8}}.tar.gz'.format(**_locals))
        ])
