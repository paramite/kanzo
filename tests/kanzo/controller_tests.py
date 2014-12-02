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


class ControllerTestCase(BaseTestCase):
    def setUp(self):
        if PYTHON == 2:
            super(ControllerTestCase, self).setUp()
        else:
            super().setUp()
        self._path = os.path.join(_KANZO_PATH, 'kanzo/tests/test_config.txt')

        register_execute(
            'hostname -f',
            0,
            'master.kanzo.org\n',
            ''
        )
        register_execute(
            'hostname -A',
            0,
            'localhost master master.kanzo.org\n',
            ''
        )
        shell.RemoteShell.register_execute(
            '192.168.6.66',
            'puppet agent --test --server=master.kanzo.org',
            0,
            '''Info: Creating a new SSL key for 192.168.6.66
Info: Caching certificate for ca
Info: Creating a new SSL certificate request for 192.168.6.66
Info: Certificate Request fingerprint (SHA256): AA:A6:66:AA:AA
Exiting; no certificate found and waitforcert is disabled''',
            ''
        )
        shell.RemoteShell.register_execute(
            '192.168.6.67',
            'puppet agent --test --server=master.kanzo.org',
            0,
            '''Info: Creating a new SSL key for 192.168.6.67
Info: Caching certificate for ca
Info: Creating a new SSL certificate request for 192.168.6.67
Info: Certificate Request fingerprint (SHA256): BB:B6:66:BB:BB
Exiting; no certificate found and waitforcert is disabled''',
            ''
        )
        shell.RemoteShell.register_execute(
            'master.kanzo.org',
            'puppet cert list',
            0,
            '''"192.168.6.66" (SHA256) AA:A6:66:AA:AA
"192.168.6.67" (SHA256) BB:B6:66:BB:BB''',
            ''
        )
        shell.RemoteShell.register_execute(
            '192.168.6.66',
            'service puppet start',
            0,
            '',
            ''
        )
        shell.RemoteShell.register_execute(
            '192.168.6.67',
            'service puppet start',
            0,
            '',
            ''
        )
        self._controller = Controller(self._path, work_dir=self._tmpdir)

    def test_controller_init(self):
        """[Controller] Test initialization."""
        check_history([
            'hostname -f',
            'hostname -A'
        ])

        self.check_history('master.kanzo.org', [
            'yum install -y puppet puppet-server',
            'yum install -y tar ',
            'facter -p',
            'systemctl start puppetmaster.service',
            'puppet cert list',
            'puppet cert sign 192.168.6.66',
            'puppet cert sign 192.168.6.67'
        ])
