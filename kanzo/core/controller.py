# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import logging
from collections import namedtuple

from ..conf import project, get_hosts
from .drones import Drone, DroneObserver


logger = logging.getLogger('kanzo.backend')

# named tuple for dependency index
MarkerDep = namedtuple('MarkerDep', ['depends_on', 'required_by'])


class Controller(object):
    """Master class which is driving the installation process."""
    def __init__(self, config, plugins, remote_tmpdir=None, local_tmpdir=None,
                 work_dir=None):
        # create drone for each host
        observer = DroneObserver()
        self._drone_idx = {}
        self._drone_nfo = {}
        for i in get_hosts(config):
            self._drone_idx[i] = Drone(i, config, observer,
                                       remote_tmpdir=remote_tmpdir,
                                       local_tmpdir=local_tmpdir,
                                       work_dir=work_dir)
            self._drone_nfo[i] = self._drone_idx[i].info
            # register default modules
            for mod in project.PUPPET_DEFAULT_MODULES:
                self._drone_idx[i].add_module(mod)
        # load all relevant information from plugins
        self._messages = []
        self._initial = []
        self._cleanup = []
        self._dep_idx = {}
        for plg in plugins:
            # register initialization and cleanup steps from plugin
            self._initial.extend(getattr(plg, 'INITIALIZATION', []))
            self._cleanup.extend(getattr(plg, 'CLEANUP', []))
            # register manifests and create dependency graph
            plugin_drones = set()
            for factory in getattr(plg, 'FACTORIES', []):
                result = factory(config=config, drones_info=self._drone_nfo,
                                 messages=self._messages)
                if not result:
                    # factory function did not return manifest info dict
                    continue
                if 'host' not in result or 'path' not in result:
                    raise ValueError('Manifest factory function result has to '
                                     'contain "host" and "path" value.')
                if result['host'] in self._drone_idx:
                    raise ValueError('Manifest cannot be applied to host %s. '
                                     'Given host is not contained in config '
                                     'file.' % result['host'])
                plugin_drones.add(self._drone_idx[result['host']])
                marker = self._drone_idx[result['host']]\
                                .add_manifest(result['path'],
                                              marker=result.get('marker'))
                dep_idx = self._dep_idx.setdefault(marker, MarkerDep([], []))
                dep_idx.depends_on.extend(result.get('dependency', []))
                for i in result.get('dependency', []):
                    dep_idx = self._dep_idx.setdefault(i, MarkerDep([], []))
                    dep_idx.required_by.append(marker)
            # register plugin specific modules and resources
            for drone in plugin_drones:
                for mod in plg.MODULES:
                    drone.add_module(mod)
                for res in plg.RESOURCES:
                    drone.add_resource(res)
        self._config = config

    def run_install(self):
        """Run configured installation on all hosts."""
