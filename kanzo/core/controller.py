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


PluginData = collections.namedtuple(
    'PluginData', [
        'name',
        'modules',
        'resources',
        'init_steps',
        'prep_steps',
        'deployment',
        'cleanup',
    ]
)


class Controller(object):
    """Master class which is driving the installation process."""
    def __init__(self, config, work_dir=None, remote_tmpdir=None,
                 local_tmpdir=None):
        self._messages = []
        self._tmpdir = tempfile.mkdtemp(prefix='master-', dir=work_dir)

        # loads config file
        self._plugin_modules = plugins.load_all_plugins()
        self._config = Config(
            config, plugins.meta_builder(self._plugin_modules)
        )
        # load all relevant information from plugins
        deploy_hosts = get_hosts(self._config)
        self._plugins = []
        init_steps = []
        prep_steps = []
        cleanup = []
        for plug in self._plugin_modules:
            # load plugin data
            data = PluginData(
                name=plug.__name__,
                modules=getattr(plug, 'MODULES', []),
                resources=getattr(plug, 'RESOURCES', []),
                init_steps=getattr(plug, 'INITIALIZATION', []),
                prep_steps=getattr(plug, 'PREPARATION', []),
                deployment=getattr(plug, 'DEPLOYMENT', []),
                cleanup=getattr(plug, 'CLEANUP', []),
            )
            init_steps.extend(data.init_steps)
            prep_steps.extend(data.prep_steps)
            cleanup.extend(data.cleanup)
            self._plugins.append(data)
            LOG.debug('Loaded plugin {0}'.format(plug))
        # creates drone for each deploy host
        self._drones = {}
        self._info = {}
        for host in deploy_hosts:
            # connect to host to solve ssh keys as first step
            shell.RemoteShell(host)
            drone = drones.Drone(
                host, self._config,
                work_dir=work_dir,
                remote_tmpdir=remote_tmpdir,
                local_tmpdir=local_tmpdir,
            )
            self._info[host] = drone.initialize_host(
                self._messages,
                init_steps=init_steps,
                prep_steps=prep_steps,
                cleanup=cleanup
            )
            self._drones[host] = drone
        # plans Puppet deployment steps and registers resources to drones
        for plug in self._plugins:
            plug_hosts = set()
            for step in plug.deployment:
                records = step(self._config, self._info, self._messages)
                for host, manifest, marker, prereqs in records:
                    plug_hosts.add(host)
                    self._drones[host].add_manifest(manifest, marker, prereqs)
            for host in plug_hosts:
                drone = self._drones[host]
                for resource in plug.resources:
                    drone.add_resource(resource)
                for module in plug.modules:
                    drone.add_module(module)
        # prepare deployment builds
        for drone in self._drones.values:
            drone.make_build()

    def run_install(self):
        """Run configured installation on all hosts."""

    def cleanup(self):
        for drone in self._drones.values():
            drone.clean()
