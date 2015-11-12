# -*- coding: utf-8 -*-

import sys

from .. import conf
from . import controller


def simple_reporter(unit_type, unit_name, unit_status, additional=None):
    """Prints status to stdout"""
    unit_name = unit_name.replace('_', ' ').capitalize()
    sys.stdout.write('[{unit_type}] {unit_name}: {unit_status}')


def main(config_path, log_path=None, debug=False, timeout=None,
         work_dir=None, remote_tmpdir=None, local_tmpdir=None):
    """This default main function can be used by project runner."""
    conf.set_logging(log_file=log_path, log_level='DEBUG' if debug else 'INFO')
    ctrl = controller.Controller(config_path,
        work_dir=work_dir,
        local_tmpdir=local_tmpdir,
        remote_tmpdir=remote_tmpdir
    )
    ctrl.register_status_callback(simple_reporter)
    ctrl.run_init(debug=debug, timeout=timeout)
    ctrl.run_deployment(debug=debug, timeout=timeout)
    ctrl.run_cleanup()
