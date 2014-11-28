# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import re
import sys

from kanzo.core.drones import TarballTransfer, Drone
from kanzo.utils import PYTHON, shell

from . import BaseTestCase


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


    def _test_history(self, history, commands):
        last = 0
        for searched in commands:
            index = 0
            found = False
            for cmd in history:
                found = re.match(searched, cmd.cmd)
                if found and index < last:
                    raise AssertionError(
                        'Found command "{0}" in history, but command '
                        'order is invalid.\nOrder: {1}\n'
                        'History: {2}'.format(
                            searched, commands, [i.cmd for i in history]
                        ))
                if found:
                    break
            else:
                raise AssertionError('Command "{0}" was not found '
                                     'in history: {1}'.format(
                                        searched, [i.cmd for i in history]
                                     ))
        if len(history) != len(commands):
            raise AssertionError(
                'Count of commands submitted does not match count of executed'
                ' commands.\nsubmitted:\n{0}\nexecuted:\n{1}'.format(
                    commands, [i.cmd for i in history]
                )
            )

    def test_local_remote_file_transfer(self):
        """[TarballTransfer] Test local->remote file transfer"""
        host = '10.66.66.01'
        transfer = TarballTransfer(host, '/foo', self._tmpdir)
        transfer.send(self.testfile, '/foo/file1.foo')
        # test transfer on remote side
        self._test_history(shell.RemoteShell.history[host], [
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
        self._test_history(shell.RemoteShell.history[host], [
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
        self._test_history(shell.RemoteShell.history[host], [
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
        self._test_history(shell.RemoteShell.history[host], [
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
