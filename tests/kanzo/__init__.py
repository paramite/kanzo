# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import re
import sys

_KANZO_PATH = os.path.dirname(__file__)
for i in range(3): # get rid of 'kanzo/tests/kanzo/conf
    _KANZO_PATH = os.path.dirname(_KANZO_PATH)
sys.path.insert(0, _KANZO_PATH)

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

import collections
import shutil
import tempfile

from unittest import TestCase

from kanzo.utils import shell


Execution = collections.namedtuple('Execution', [
    'cmd',
    'can_fail',
    'mask_list',
    'log'
])

ReturnVal = collections.namedtuple('ReturnVal', [
    'rc',
    'stdout',
    'stderr',
])


_execute_history = None
def fake_execute(cmd, workdir=None, can_fail=True, mask_list=None,
            use_shell=False, log=True):
    """Fake execute function used for testing only. This function can
    be used only within BaseTestCase sublass methods.
    """
    _execute_history.append(Execution(cmd, can_fail, mask_list, log))
    return 0, '', ''


class FakeRemoteShell(object):
    """Fake RemoteShell class used for testing only"""
    history = {}
    return_vals = {}
    _default_return = ReturnVal(0, '', '')

    def __init__(self, host):
        self.host = host
        self._client = Mock(
            open_sftp=lambda: Mock(
                put=lambda src, dest: None,
                get=lambda src, dest: None,
                close=lambda: None,
            )
        )

    @classmethod
    def register_execute(cls, host, cmd, rc, stdout, stderr):
        register = cls.return_vals.setdefault(host, {})
        register[cmd] = ReturnVal(rc, stdout, stderr)

    @classmethod
    def register_run_script(cls, host, script, rc, stdout, stderr):
        register = cls.return_vals.setdefault(host, {})
        script_cmd = '\n'.join(script)
        register[script_cmd] = ReturnVal(rc, stdout, stderr)

    def reconnect(self):
        pass

    def execute(self, cmd, can_fail=True, mask_list=None, log=True):
        hist = self.history.setdefault(self.host, [])
        hist.append(Execution(cmd, can_fail, mask_list, log))

        register = self.return_vals.setdefault(self.host, {})
        if cmd in register:
            rv = register[cmd]
            return rv.rc, rv.stdout, rv.stderr

        return (
            self._default_return.rc,
            self._default_return.stdout,
            self._default_return.stderr
        )

    def run_script(self, script, can_fail=True, mask_list=None,
                   log=True, description=None):
        hist = self.history.setdefault(self.host, [])
        for cmd in script:
            hist.append(Execution(cmd, can_fail, mask_list, log))

        script_cmd = '\n'.join(script)
        register = self.return_vals.setdefault(self.host, {})
        if script_cmd in register:
            rv = register[script_cmd]
            return rv.rc, rv.stdout, rv.stderr

        return (
            self._default_return.rc,
            self._default_return.stdout,
            self._default_return.stderr
        )

    def close(self):
        del self.history[self.host]


class BaseTestCase(TestCase):

    def setUp(self):
        """Prepare temporary files and fakes for shell interfaces
        (kanzo.core.utils.shell.RemoteShell and
        kanzo.core.utils.shell.execute).
        """
        global _execute_history
        self._tmpdir = tempfile.mkdtemp(prefix='kanzo-test')

        self._orig_remoteshell = shell.RemoteShell
        shell.RemoteShell = FakeRemoteShell

        _execute_history = []
        self._execute_history = _execute_history
        self._orig_execute = shell.execute
        shell.execute = fake_execute

    def tearDown(self):
        global _execute_history
        shutil.rmtree(self._tmpdir)
        shell.RemoteShell = self._orig_remoteshell
        shell.execute = self._orig_execute
        _execute_history = None

    def check_history(self, host, commands):
        last = 0
        for searched in commands:
            index = 0
            found = False
            for cmd in FakeRemoteShell.history[host]:
                found = re.match(searched, cmd.cmd)
                if found and index < last:
                    raise AssertionError(
                        'Found command "{0}" in history, but command '
                        'order is invalid.\nOrder: {1}\n'
                        'History: {2}'.format(
                            searched, commands,
                            [i.cmd for i in FakeRemoteShell.history[host]]
                        ))
                if found:
                    break
            else:
                raise AssertionError(
                        'Command "{0}" was not found in history: {1}'.format(
                            searched,
                            [i.cmd for i in FakeRemoteShell.history[host]]
                        )
                )
        if len(FakeRemoteShell.history[host]) != len(commands):
            raise AssertionError(
                'Count of commands submitted does not match count of executed'
                ' commands.\nsubmitted:\n{0}\nexecuted:\n{1}'.format(
                    commands, [i.cmd for i in FakeRemoteShell.history[host]]
                )
            )
