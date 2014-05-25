# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

from ..conf import Config
from .controller import Controller
from .plugins import load_all_plugins, meta_builder


def main(config_path, remote_tmpdir=None, local_tmpdir=None, work_dir=None):
    """Main function should be used by project runner."""
    plugins = load_all_plugins()
    config_metadata = meta_builder(plugins)
    config = Config(config_path, config_metadata)

    controller = Controller(config, plugins, remote_tmpdir=remote_tmpdir,
                            local_tmpdir=local_tmpdir, work_dir=work_dir)
    controller.run_install()
