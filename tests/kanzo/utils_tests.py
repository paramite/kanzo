# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import os
import pwd
import grp
from unittest import TestCase
try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

from kanzo.utils.decorators import retry
from kanzo.utils.strings import color_text, mask_string, state_message
from kanzo.utils.shortcuts import get_current_user, get_current_username


STR_MASK = '*' * 8


cnt = 0
@retry(count=3, delay=0, retry_on=ValueError)
def run_sum():
    global cnt
    cnt += 1
    raise ValueError


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

    def tearDown(self):
        pwd.getpwnam = self.real_getpwnam
        pwd.getpwuid = self.real_getpwuid
        grp.getgrgid = self.real_getgrgid
        os.getuid = self.real_getuid
        os.getgid = self.real_getgid

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
