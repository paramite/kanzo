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

\[master\]
certname={master}
dns_alt_names={master_dnsnames}
ssl_client_header=SSL_CLIENT_S_DN
ssl_client_verify_header=SSL_CLIENT_VERIFY

\[agent\]
certname={host}
server={master}
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

        reg_cmd = (
            'rm -f /var/lib/puppet/ssl/certificate_requests/* &>/dev/null && '
            'puppet agent --test &>/dev/null && '
            'puppet agent --fingerprint'
        )
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
            reg_cmd,
            0,
            '(SHA256) AA:A6:66:AA:AA',
            ''
        )
        shell.RemoteShell.register_execute(
            '192.168.6.67',
            reg_cmd,
            0,
            '(SHA256) BB:B6:66:BB:BB',
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

        confmeta = {
            'host': 'master.kanzo.org',
            'master': 'master.kanzo.org',
            'master_dnsnames': 'master.kanzo.org,localhost,master',
            'datadir': os.path.join(self._controller._tmpdir, 'data'),
            'moduledir': os.path.join(self._controller._tmpdir, 'modules'),
            'logdir': os.path.join(self._controller._tmpdir, 'log')
        }
        puppet_conf = PUPPET_CONFIG.format(**confmeta)
        hiera_conf = HIERA_CONFIG.format(**confmeta)

        self.check_history('master.kanzo.org', [
            # Master startup
            'yum install -y puppet puppet-server',
            'yum install -y tar',
            'facter -p',

            # Puppet configuration
            'cat > /etc/puppet/puppet.conf <<EOF{}EOF'.format(puppet_conf),
            'cat > /etc/puppet/hiera.yaml <<EOF{}EOF'.format(hiera_conf),
            ('systemctl start puppetmaster.service && '
                'systemctl status puppetmaster.service'),

            # Request signing
            'rm -f /var/lib/puppet/ssl/ca/requests/*',
            'puppet cert list',
            'puppet cert sign 192.168.6.66',
            'puppet cert sign 192.168.6.67'
        ])
