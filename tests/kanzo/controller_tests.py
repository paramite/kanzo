# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import sys

from kanzo.core.controller import Controller
from kanzo.utils import PYTHON, shell

from ..plugins import sql
from . import _KANZO_PATH, register_execute, check_history
from . import BaseTestCase


PUPPET_CONFIG = '''
\[main\]
basemodulepath={moduledir}
logdir={logdir}
'''

HIERA_CONFIG = '''
---
:backends:
  - yaml
:yaml:
  :datadir: {datadir}
:hierarchy:
  - "%{{::type}}/%{{::fqdn}}"
  - "%{{::type}}/common"
  - common
'''

class ControllerTestCase(BaseTestCase):
    def setUp(self):
        if PYTHON == 2:
            super(ControllerTestCase, self).setUp()
        else:
            super().setUp()
        self._path = os.path.join(_KANZO_PATH, 'kanzo/tests/test_config.txt')
        self._controller = Controller(self._path, work_dir=self._tmpdir)

    def test_controller_init(self):
        """[Controller] Test initialization."""
        confmeta = {
            'datadir': os.path.join(self._controller._tmpdir, 'data'),
            'moduledir': os.path.join(self._controller._tmpdir, 'modules'),
            'logdir': os.path.join(self._controller._tmpdir, 'log')
        }
        puppet_conf = PUPPET_CONFIG.format(**confmeta)
        hiera_conf = HIERA_CONFIG.format(**confmeta)
