# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import os
import sys

_KANZO_PATH = os.path.dirname(__file__)
for i in range(3): # get rid of 'kanzo/tests/kanzo/conf
    _KANZO_PATH = os.path.dirname(_KANZO_PATH)
sys.path.insert(0, _KANZO_PATH)

from unittest import TestCase

from kanzo.conf import project, defaultproject


class ProjectTestCase(TestCase):

    def test_default_parameters(self):
        """[Project] Test project default parameters"""
        for key in defaultproject.__dict__.keys():
            if key.isupper():
                assert hasattr(project, key)

    def test_parameter_values(self):
        """[Project] Test correct parameter values"""
        proj_path = os.path.dirname(os.environ.get('KANZO_PROJECT', __file__))
        plug_path = [os.path.join(proj_path, 'plugins')]

        self.assertEquals(getattr(project, 'TESTS_ABS_PATH', None), proj_path)
        self.assertEquals(getattr(project, 'PLUGIN_PATHS', None), plug_path)
        self.assertEquals(getattr(project, 'PLUGINS', None), ['sql'])
