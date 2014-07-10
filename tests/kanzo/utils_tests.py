# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import grp
import os
import paramiko
import pwd
import subprocess
import types
from unittest import TestCase
try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

from kanzo.utils.decorators import retry
from kanzo.utils.shell import RemoteShell, execute
from kanzo.utils.shortcuts import get_current_user, get_current_username
from kanzo.utils.strings import color_text, mask_string, state_message


OUTFMT = '---- %s ----'
STR_MASK = '*' * 8


cnt = 0
@retry(count=3, delay=0, retry_on=ValueError)
def run_sum():
    global cnt
    cnt += 1
    raise ValueError


# Mock paramiko.SSHClient for testing RemoteShell
class FakeChannel(object):
    def __init__(self):
        self.exit_code = 0

    def recv_exit_status(self):
        return self.exit_code


class FakeChannelFile(object):
    def __init__(self):
        self.output = []
        self.channel = FakeChannel()

    def __iter__(self):
        return iter(self.output)


class FakeSSHClient(object):
    def connect(self, host, port, username, key_filename):
        pass

    def set_missing_host_key_policy(self, policy):
        pass

    def set_log_channel(self, channel):
        pass

    def close(self):
        pass

    def exec_command(self, cmd):
        chf = FakeChannelFile()
        if cmd == 'pass':
            chf.output = ['passed']
        else:
            chf.channel.exit_code = 1
            chf.output = ['failed']
        return chf, chf, chf


# Mock subprocess.Popen for testing RemoteShell and execute
class FakePopen(object):
    '''The FakePopen class replaces subprocess.Popen. Instead of actually
    executing commands, it permits the caller to register a list of
    commands the output to produce using the FakePopen.register and
    FakePopen.register_as_script method.  By default, FakePopen will return
    empty stdout and stderr and a successful (0) returncode.
    '''
    def __init__(self, cmd, cwd=None, close_fds=True, shell=False, stdin=None,
                 stdout=None, stderr=None):
        self.returncode = 0
        self.cmd = cmd
        # test connecting command
        print (cmd)
        if isinstance(cmd, types.ListType):
            assert cmd[0] == 'ssh' and cmd[-1] == 'bash -x'

    def communicate(self, input=None):
        lines = input.split('\n') if input else []
        # test script prefix
        if lines:
            assert lines[0] == 'function script_trap(){ exit $? ; }'
            assert lines[1] == 'trap script_trap ERR'
        if not lines or lines[2] == 'pass':
            passing = True
        else:
            passing = False

        if passing:
            out = err = 'passed'
        else:
            self.returncode = 1
            out = err = 'failed'
        return out, err


class UtilsTestCase(TestCase):
    def setUp(self):
        self.real_getpwnam = pwd.getpwnam
        self.real_getpwuid = pwd.getpwuid
        self.real_getgrgid = grp.getgrgid
        pwd.getpwnam = lambda name: Mock(pw_uid=666, pw_gid=666)
        pwd.getpwuid = lambda uid: Mock(pw_name='test_usr')
        grp.getgrgid = lambda gid: Mock(gr_name='test_grp')
        self.real_getuid = os.getuid
        self.real_getgid = os.getgid
        os.getuid = lambda: 666
        os.getgid = lambda: 666
        self.real_sshclient = paramiko.SSHClient
        self.real_popen = subprocess.Popen
        paramiko.SSHClient = FakeSSHClient
        subprocess.Popen = FakePopen

    def tearDown(self):
        pwd.getpwnam = self.real_getpwnam
        pwd.getpwuid = self.real_getpwuid
        grp.getgrgid = self.real_getgrgid
        os.getuid = self.real_getuid
        os.getgid = self.real_getgid
        paramiko.SSHClient = self.real_sshclient
        subprocess.Popen = self.real_popen

    def test_decorators(self):
        """[Utils] Test decorators"""
        global cnt
        cnt = 0
        try:
            run_sum()
        except ValueError:
            pass
        self.assertEqual(cnt, 4)
        self.assertRaises(ValueError, run_sum)

    def test_strings(self):
        """[Utils] Test strings"""
        # test color_test
        self.assertEqual(color_text('test text', 'red'),
                        '\033[0;31mtest text\033[0m')
        # test mask_string
        self.assertEqual(mask_string('test text', mask_list=['text']),
                         'test %s' % STR_MASK)
        masked = mask_string("test '\\''text'\\''",
                             mask_list=["'text'"],
                             replace_list=[("'", "'\\''")])
        self.assertEqual(masked, 'test %s' % STR_MASK)
        # test state_message
        msg = 'test'
        state = 'DONE'
        space = 70 - len(msg)
        color_state = '[ \033[0;31mDONE\033[0m ]'
        self.assertEqual(state_message(msg, state, 'red'),
                         '{0}{1}'.format(msg, color_state.rjust(space)))

    def test_shortcuts(self):
        """[Utils] Test shortcuts"""
        self.assertEqual(get_current_user(), (666, 666))

    def test_shell(self):
        """[Utils] Test shell"""
        # We need to override _register method
        RemoteShell._connections['127.0.0.1'] = FakeSSHClient()
        shell = RemoteShell('127.0.0.1')
        # Test passing cmd execution
        rc, out, err = shell.execute('pass')
        self.assertEqual(rc, 0)
        self.assertEqual(out, 'passed')
        self.assertEqual(err, 'passed')
        # Test failing cmd execution
        rc, out, err = shell.execute('fail', can_fail=False)
        self.assertEqual(rc, 1)
        self.assertEqual(out, 'failed')
        self.assertEqual(err, 'failed')
        self.assertRaises(RuntimeError, shell.execute, 'fail')
        # Test passing script execution
        rc, out, err = shell.run_script(['pass'])
        self.assertEqual(rc, 0)
        self.assertEqual(out, 'passed')
        self.assertEqual(err, 'passed')
        # Test failing script execution
        rc, out, err = shell.run_script(['fail'], can_fail=False)
        self.assertEqual(rc, 1)
        self.assertEqual(out, 'failed')
        self.assertEqual(err, 'failed')
        self.assertRaises(RuntimeError, shell.run_script, ['fail'])
        # Test masking
        mask_list = ['masked']
        try:
            shell.execute('fail masked string', mask_list=mask_list)
        except RuntimeError as ex:
            self.assertEqual(str(ex), 'Failed to run following command '
                                      'on host 127.0.0.1: fail %s string'
                                      % STR_MASK)
        chout = FakeChannelFile()
        chout.output = ['This is masked', 'This should be also masked']
        stdout, solog = shell._process_output('stdout', chout,
                                              mask_list, [])
        self.assertEqual(solog, '%s\nThis is %s\nThis should be also %s'
                                % (OUTFMT % 'stdout', STR_MASK, STR_MASK))
        # Test execute
        rc, out, err = execute('foo bar')
        self.assertEqual(out, 'passed')
        rc, out, err = execute(['ssh', 'bash -x'])
        self.assertEqual(out, 'passed')
