# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import collections
import logging

from ..conf import project, get_hosts
from .drones import Drone


logger = logging.getLogger('kanzo.backend')

# named tuple for dependency index
MarkerDep = collections.namedtuple('MarkerDep', ['depends_on', 'required_by'])


class Controller(object):
    """Master class which is driving the installation process."""
    def __init__(self, config, plugins, work_dir=None,
                 remote_tmpdir=None, local_tmpdir=None):
        self._config = config

        # create drone for each host
        self._drones = {}
        for ip_or_hostname in get_hosts(config):
            self._drones[ip_or_hostname] = Drone(
                ip_or_hostname, config,
                work_dir=work_dir,
                remote_tmpdir=remote_tmpdir,
                local_tmpdir=local_tmpdir,
            )

        # load all relevant information from plugins
        for plg in plugins:
            pass

    def run_install(self):
        """Run configured installation on all hosts."""
