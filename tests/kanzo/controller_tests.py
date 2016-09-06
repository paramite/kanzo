# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import sys

from kanzo.core.controller import Controller
from kanzo.core.main import simple_reporter
from kanzo.utils import shell

from ..plugins import sql
from . import _KANZO_PATH, register_execute, check_history
from . import BaseTestCase


PUPPET_CONFIG = '''
\[main\]
basemodulepath={moduledir}
logdir={logdir}
hiera_config=/etc/puppet/hiera.yaml
'''


class ControllerTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._path = os.path.join(_KANZO_PATH, 'kanzo/tests/test_config.txt')
        self._controller = Controller(self._path, work_dir=self._tmpdir)
        self._controller.register_status_callback(simple_reporter)
        # Note: All tested steps below are implemented in a test plugins:
        #       ../plugins/(no)sql.py

    def tearDown(self):
        for drone in self._controller._drones.values():
            drone.clean()

    def test_controller_init(self):
        """[Controller] Test initialization."""
        self.clear_history('192.168.6.66')
        self._controller.run_init(debug=True)
        basedir = (
            '/var/tmp/kanzo/\d{8}-\d{6}/build-\d{8}-\d{6}-192.168.6.66'
        )
        confmeta = {
            'datadir': os.path.join(basedir, 'hieradata'),
            'moduledir': os.path.join(basedir, 'modules'),
            'logdir': os.path.join(basedir, 'logs')
        }
        puppet_conf = PUPPET_CONFIG.format(**confmeta)
        self.check_history('192.168.6.66', [
            '# Running initialization steps here',
            'rpm -q puppet \|\| yum install -y puppet',
            'rpm -q tar \|\| yum install -y tar',
            'facter -p',
            'cat > /etc/puppet/puppet.conf <<EOF{}EOF'.format(puppet_conf),
            '# Running preparation steps here',
            '# Running deployment planning here',
            'mkdir -p --mode=0700 /var/tmp/kanzo/\d{8}-\d{6}',
            (
                'mkdir -p --mode=0700 /var/tmp/kanzo/\d{8}-\d{6}/'
                    'build-\d{8}-\d{6}-192.168.6.66 && '
                'tar -C /var/tmp/kanzo/\d{8}-\d{6}/'
                    'build-\d{8}-\d{6}-192.168.6.66 -xpzf /var/tmp/kanzo/'
                    '\d{8}-\d{6}/transfer-\w{8}.tar.gz'
            ),
            'rm -f /var/tmp/kanzo/\d{8}-\d{6}/transfer-\w{8}.tar.gz'
        ])

    def test_controller_planning(self):
        """[Controller] Test deployment planning."""
        self._controller.run_init(debug=True)
        # test order of markers
        self.assertEqual(
            list(self._controller._plan['manifests'].keys()),
            ['prerequisite_1', 'final', 'prerequisite_2']
        )
        # test manifest registered for each marker
        self.assertEqual(
            self._controller._plan['manifests']['prerequisite_1'],
            [('192.168.6.66', 'prerequisite_1')]
        )
        self.assertEqual(
            self._controller._plan['manifests']['prerequisite_2'],
            [('192.168.6.67', 'prerequisite_2')]
        )
        self.assertEqual(
            self._controller._plan['manifests']['final'],
            [('192.168.6.66', 'final')]
        )
        # test marker dependency
        self.assertEqual(
            self._controller._plan['dependency']['prerequisite_1'], set()
        )
        self.assertEqual(
            self._controller._plan['dependency']['prerequisite_2'], set()
        )
        self.assertEqual(
            self._controller._plan['dependency']['final'],
            {'prerequisite_1', 'prerequisite_2'}
        )

    def test_controller_deployment(self):
        """[Controller] Test deployment execution."""
        self._controller.run_init(debug=True)
        self._controller.run_deployment(debug=True)
