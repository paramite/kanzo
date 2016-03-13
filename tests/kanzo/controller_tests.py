# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import sys

from kanzo.core.controller import Controller
from kanzo.utils import shell

from ..plugins import sql
from . import _KANZO_PATH, register_execute, check_history
from . import BaseTestCase


class ControllerTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._path = os.path.join(_KANZO_PATH, 'kanzo/tests/test_config.txt')
        self._controller = Controller(self._path, work_dir=self._tmpdir)

    def tearDown(self):
        for drone in self._controller._drones.values():
            drone.clean()

    def test_controller_init(self):
        """[Controller] Test initialization."""
