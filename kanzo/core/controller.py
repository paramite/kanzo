# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import collections
import logging
import tempfile

from ..conf import Config, project, get_hosts
from ..utils import shell, decorators

from . import drones
from . import plugins
from . import puppet


LOG = logging.getLogger('kanzo.backend')


class Controller(object):
    """Master class which is driving the installation process."""
    def __init__(self, config, work_dir=None, remote_tmpdir=None,
                 local_tmpdir=None):
        self._messages = []
        self._tmpdir = tempfile.mkdtemp(prefix='master-', dir=work_dir)

        # load all relevant information from plugins and create config
        self._plugins = plugins.load_all_plugins()
        self._config = Config(config, plugins.meta_builder(self._plugins))

        modules = set()
        resources = set()
        init_steps = []
        prepare_steps = []
        self._deployment = []
        self._cleanup = []
        for plug in self._plugins:
            modules.update(set(getattr(plug, 'MODULES', [])))
            resources.update(set(getattr(plug, 'RESOURCES', [])))
            init_steps.extend(getattr(plug, 'INITIALIZATION', []))
            prepare_steps.extend(getattr(plug, 'PREPARATION', []))
            self._deployment.extend(getattr(plug, 'DEPLOYMENT', []))
            self._cleanup.extend(getattr(plug, 'CLEANUP', []))
            LOG.debug('Loaded plugin {0}'.format(plug))

        # get all possible local hostnames
        rc, master, err = shell.execute('hostname -f', use_shell=True)
        master = master.strip()
        rc, out, err = shell.execute('hostname -A', use_shell=True)
        master_names = [master]
        for name in out.split():
            name = name.strip()
            if name and name not in master_names:
                master_names.append(name)
        # connect to local installation machine
        self._shell = shell.RemoteShell(master)

        # connect to all other hosts to solve ssh keys as first step
        for host in get_hosts(self._config):
            shell.RemoteShell(host)

        # initialize and run Puppet master on installation host
        drones.initialize_host(
            self._shell, self._config, self._messages, self._tmpdir,
            master, master_names,
            init_steps=init_steps,
            prepare_steps=prepare_steps
        )
        self._start_master()

        # create Drone for each host and register them as Puppet clients
        # and sign their certificates
        fingerprints = {}
        self._drones = {}
        for host in get_hosts(self._config):
            drone = drones.Drone(
                host, self._config,
                work_dir=work_dir,
                remote_tmpdir=remote_tmpdir,
                local_tmpdir=local_tmpdir,
            )
            if host not in master_names:
                # we don't need to initialize local drone's host again
                drone.initialize_host(
                    self._messages,
                    master, master_names,
                    init_steps=init_steps,
                    prepare_steps=prepare_steps
                )
            fingerprints[host] = drone.register()
            self._drones[host] = drone
        self._sign_certs(master, fingerprints)

    def _start_master(self):
        # https://tickets.puppetlabs.com/browse/PUP-1271
        # In certain cases master fails to create ssl cert correctly and
        # so fails to start. Solution is to remove ssl dir and try again
        @decorators.retry(count=1, retry_on=RuntimeError)
        def start():
            for cmd in project.PUPPET_MASTER_STARTUP_COMMANDS:
                rc, out, err = self._shell.execute(cmd, can_fail=False)
                if rc == 0:
                    LOG.debug(
                        'Started Puppet master on host {self._shell.host} '
                        'via command "{cmd}"'.format(**locals())
                    )
                    break
            else:
                rc, out, err = self._shell.execute(
                    'rm -fr /var/lib/puppet/ssl', can_fail=False
                )
                raise RuntimeError(
                    'Failed to start Puppet master on host {self._shell.host}.'
                    'None of the startup commands worked: '
                    '{project.PUPPET_MASTER_STARTUP_COMMANDS}'.format(
                        **locals()
                    )
                )
        start()
        # delete old certificate sign requests from possible previous runs
        rc, out, err = self._shell.execute(
            'rm -f /var/lib/puppet/ssl/ca/requests/*'
        )

    def _sign_certs(self, master, fingerprints):
        signed = set()
        rc, out, err = self._shell.execute('puppet cert list')
        for item in out.split('\n'):
            item = item.strip()
            if not item:
                continue
            host, method, master_fp = puppet.parse_crf(item)
            agent_fp = fingerprints[host][1]
            if host.strip() not in self._drones.keys():
                LOG.warning(
                    'Unknown host submitted certificate request '
                    'fingerprint: {host}'.format(**locals())
                )
                continue
            if master_fp != agent_fp:
                LOG.error(
                    'Fingerprint check failed. Agent {host} submitted '
                    '"{agent_fp}" but Master sees '
                    '"{master_fp}".'.format(**locals())
                )
                raise RuntimeError(
                    'Fingerprint check failed for host '
                    '{host}.'.format(**locals())
                )
            # sign certificate on master
            rc, out, err = self._shell.execute(
                'puppet cert sign {host}'.format(**locals())
            )
            signed.add(host)

        signed.add(master)
        not_signed = set(self._drones.keys()) - signed
        if not_signed:
            raise RuntimeError(
                'Certificate signing process failed. Following hosts did not '
                'submit certificate request fingerprint or used different '
                'hostname: {not_signed}'.format(**locals())
            )

    def run_install(self):
        """Run configured installation on all hosts."""

    def cleanup(self):
        for host, drone in self._drones.items():
            pass
