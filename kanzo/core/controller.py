# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import collections
import logging

from ..conf import Config, project, get_hosts
from ..utils import shell

from . import drones
from . import plugins
from . import puppet


LOCALHOST = {
    '127.0.0.1', 'localhost', 'localhost.localdomain', 'localhost4',
    'localhost4.localdomain4', '::1', 'localhost6', 'localhost6.localdomain6',
}
LOG = logging.getLogger('kanzo.backend')


class Controller(object):
    """Master class which is driving the installation process."""
    def __init__(self, config, work_dir=None, remote_tmpdir=None,
                 local_tmpdir=None):
        self._messages = []

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
            modules.update(set(plug.MODULES))
            resources.update(set(plug.RESOURCES))
            init_steps.extend(plug.INITIALIZATION)
            prepare_steps.extend(plug.PREPARATION)
            self._deployment.extend(plug.DEPLOYMENT)
            self._cleanup.extend(plug.CLEANUP)

        # get all possible local hostnames
        rc, master, err = shell.execute('hostname -f', use_shell=True)
        master = master.strip()
        rc, out, err = shell.execute('hostname -A', use_shell=True)
        for name in out.split():
            name = name.strip()
            if name:
                LOCALHOST.add(name)
        # connect to local installation machine
        for local in [master] + list(LOCALHOST):
            try:
                self._shell = shell.RemoteShell(local)
                LOG.debug(
                    'Connected to master host via {local}.'.format(**locals())
                )
                break
            except RuntimeError:
                LOG.warning(
                    'Could not connect to master host via '
                    '{local}.'.format(**locals())
                )
                continue
        else:
            raise RuntimeError(
                'Failed to connect to installation host. Tried to connect '
                'via: {0}'.format(LOCALHOST)
            )

        # initialize and run Puppet master on installation host
        drones.initialize_host(
            self._shell, self._config, self._messages,
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
            if host not in LOCALHOST:
                # we don't need to initialize local drone's host again
                drone.prepare_and_discover(
                    self._messages,
                    init_steps=init_steps,
                    prepare_steps=prepare_steps
                )
            fingerprints[host] = drone.register(master)
            self._drones[host] = drone
        self._start_agents(fingerprints)

    def _start_master(self):
        for cmd in project.PUPPET_MASTER_STARTUP_COMMANDS:
            rc, out, err = self._shell.execute(cmd, can_fail=False)
            if rc == 0:
                LOG.debug(
                    'Started Puppet master on host {self._shell.host} '
                    'via command "{cmd}"'.format(**locals())
                )
                break
        else:
            raise RuntimeError(
                'Failed to start Puppet master on host {self._shell.host}.'
                'None of the startup commands worked: '
                '{project.PUPPET_MASTER_STARTUP_COMMANDS}'.format(**locals())
            )

    def _start_agents(self, fingerprints):
        # sign certificates and start agents
        started = set()
        rc, out, err = self._shell.execute('puppet cert list')
        for item in out.split('\n'):
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
            # start Puppet agent on agent
            for cmd in project.PUPPET_AGENT_STARTUP_COMMANDS:
                rc, out, err = self._drones[host]._shell.execute(
                    cmd, can_fail=False
                )
                if rc == 0:
                    started.add(host)
                    LOG.debug(
                        'Started Puppet agent on host {host} '
                        'via command "{cmd}"'.format(**locals())
                    )
                    break
            else:
                raise RuntimeError(
                    'Failed to start Puppet agent on host {host}.'
                    'None of the startup commands worked.'.format(**locals())
                )

        not_started = set(self._drones.keys()) - started
        if not_started:
            raise RuntimeError(
                'Agent startup failed. Following hosts did not submit '
                'certificate request fingerprint or they submitted it '
                'with different hostname: {not_started}'.format(**locals())
            )

    def run_install(self):
        """Run configured installation on all hosts."""

    def cleanup(self):
        for host, drone in self._drones.items():
            pass
