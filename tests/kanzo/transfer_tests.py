# -*- coding: utf-8 -*-

import os

from kanzo.utils import shell

from . import BaseTestCase


class SFTPTransferTestCase(BaseTestCase):

    def setUp(self):
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
        transfer = shell.SFTPTransfer(host, '/foo', self._tmpdir)
        transfer.send(self.testfile, '/foo/foodir')
        # test transfer on remote side
        self.check_history(host, [
            'mkdir \-p \-\-mode=0700 /foo',
            (
                'mkdir -p --mode=0700 /foo/foodir && '
                'tar \-C /foo/foodir \-xpzf /foo/transfer\-\w{8}\.tar\.gz'
            ),
            'rm \-f /foo/transfer\-\w{8}\.tar\.gz',
        ])

    def test_local_remote_dir_transfer(self):
        """[TarballTransfer] Test local->remote directory transfer"""
        host = '20.66.66.02'
        transfer = shell.SFTPTransfer(host, '/foo', self._tmpdir)
        transfer.send(self.testdir, '/foo/foodir')
        # test transfer on remote side
        self.check_history(host, [
            'mkdir \-p \-\-mode=0700 /foo',
            (
                'mkdir \-p \-\-mode=0700 /foo/foodir && '
                'tar \-C /foo/foodir \-xpzf /foo/transfer\-\w{8}\.tar\.gz'
            ),
            'rm \-f /foo/transfer\-\w{8}\.tar\.gz',
        ])

    def test_remote_local_file_transfer(self):
        """[TarballTransfer] Test remote->local file transfer"""
        host = '30.66.66.03'
        transfer = shell.SFTPTransfer(host, '/bar', self._tmpdir)
        shell.RemoteShell.register_execute(
            host, '[ -e "/path/to/file2.bar" ]',
            0, '', ''
        )
        try:
            transfer.receive('/path/to/file2.bar', self._tmpdir)
        except Exception:
            # transfer will fail because no file was actually
            # transferfed, so we just ignore it
            pass
        # test transfer on remote side
        self.check_history(host, [
            '\[ \-e "/path/to/file2\.bar" \]',
            'mkdir \-p \-\-mode=0700 /bar',
            ('tar \-C /path/to \-cpzf /bar/transfer\-\w{8}\.tar\.gz '
                'file2.bar'),
            'rm -fr /bar/transfer\-\w{8}\.tar\.gz'
        ])

    def test_remote_local_dir_transfer(self):
        """[TarballTransfer] Test remote->local directory transfer"""
        host = '40.66.66.04'
        transfer = shell.SFTPTransfer(host, '/bar', self._tmpdir)
        shell.RemoteShell.register_execute(
            host, '[ -e "/path/to/foodir" ]',
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
            'mkdir \-p \-\-mode=0700 /bar',
            'tar \-C /path/to \-cpzf /bar/transfer\-\w{8}\.tar\.gz foodir',
            'rm -fr /bar/transfer\-\w{8}\.tar\.gz'
        ])
