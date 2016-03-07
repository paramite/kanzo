# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import sys

from kanzo.conf import Config
from kanzo.core.drones import Drone
from kanzo.core.plugins import meta_builder
from kanzo.utils import shell

from ..plugins import sql, nosql
from . import _KANZO_PATH
from . import BaseTestCase


def init_step(host, config, messages):
    sh = shell.RemoteShell(host)
    sh.execute('echo "initialization"')


def prepare_step(host, config, info, messages):
    if not ('domain' in info and 'osfamily' in info and 'uptime' in info):
        raise AssertionError('Invalid host info passed to preparation step')
    sh = shell.RemoteShell(host)
    sh.execute('echo "preparation"')


PUPPET_CONFIG = '''
\[main\]
basemodulepath={moduledir}
logdir={logdir}
hiera_config=/etc/puppet/hiera.yaml
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

class DroneTestCase(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._path = os.path.join(_KANZO_PATH, 'kanzo/tests/test_config.txt')
        meta = meta_builder([sql])
        self._messages = []
        self._config = Config(self._path, meta)
        self._drone1 = Drone(
            '10.0.0.1', self._config, self._messages, work_dir=self._tmpdir
        )
        self._drone2 = Drone(
            '10.0.0.2', self._config, self._messages, work_dir=self._tmpdir
        )
        self._drone3 = Drone(
            '10.0.0.3', self._config, self._messages, work_dir=self._tmpdir
        )

    def test_drone_init(self):
        """[Drone] Test Drone initialization"""
        host = '10.0.0.1'
        shell.RemoteShell.register_execute(
            host,
            'facter -p',
            0,
            'domain => redhat.com\nosfamily => RedHat\nuptime => 11 days',
            ''
        )
        self._drone1.init_host()
        info = self._drone1.discover()
        self._drone1.configure()

        confmeta = {
            'datadir': os.path.join(self._drone1._remote_builddir, 'hieradata'),
            'moduledir': os.path.join(self._drone1._remote_builddir, 'modules'),
            'logdir': os.path.join(self._drone1._remote_builddir, 'logs')
        }
        puppet_conf = PUPPET_CONFIG.format(**confmeta)
        self.check_history(host, [
            'rpm -q puppet || yum install -y puppet',
            'rpm -q tar || yum install -y tar',
            'facter -p',
            'cat > /etc/puppet/puppet.conf <<EOF{}EOF'.format(puppet_conf),
        ])
        self.assertIn('domain', info)
        self.assertEquals(info['domain'], 'redhat.com')
        self.assertIn('osfamily', info)
        self.assertEquals(info['osfamily'], 'RedHat')
        self.assertIn('uptime', info)
        self.assertEquals(info['uptime'], '11 days')

    def test_drone_build(self):
        """[Drone] Test Drone build register and transfer"""
        host = '10.0.0.3'
        module_path = os.path.join(self._tmpdir, 'module_test')
        manifests_path = os.path.join(module_path, 'manifests', )
        os.makedirs(manifests_path)
        with open(os.path.join(manifests_path, 'init.pp'), 'w') as res:
            res.write('class test {}')
        resource_path = os.path.join(self._tmpdir, 'resource_test.pem')
        with open(resource_path, 'w') as res:
            res.write('test')
        self._drone3.add_resource(resource_path)
        self._drone3.add_module(module_path)
        self._drone3.make_build()

        self.assertEquals({resource_path}, self._drone3._resources)
        self.assertEquals({module_path}, self._drone3._modules)
        _locals = locals()
        self.check_history(host, [
            ('mkdir -p --mode=0700 {self._tmpdir}/'
                'host-10.0.0.3-\w{{8}}'.format(**_locals)),
            ('mkdir -p --mode=0700 '
                '{self._tmpdir}/host-10.0.0.3-\w{{8}}/build-\d{{8}}-\d{{6}} && '
             'tar -C {self._tmpdir}/host-10.0.0.3-\w{{8}}/build-\d{{8}}-\d{{6}}'
                ' -xpzf {self._tmpdir}/host-10.0.0.3-\w{{8}}/'
                'transfer-\w{{8}}.tar.gz'.format(**_locals)),
            ('rm -f {self._tmpdir}/host-10.0.0.3-\w{{8}}/'
                'transfer-\w{{8}}.tar.gz'.format(**_locals))
        ])
