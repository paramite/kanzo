# -*- coding: utf-8 -*-

import sys

from ..utils import set_logging
from .controller import Controller

print('test')

def simple_reporter(unit_type, unit_name, unit_status, additional=None):
    """Prints status to stdout"""
    unit_name = unit_name.replace('_', ' ').capitalize()
    sys.stdout.write(
        '[{unit_type}] {unit_name}: {unit_status}\n'.format(**locals())
    )


def main(config_path, log_path=None, debug=False, timeout=None,
         reporter=simple_reporter, work_dir=None, remote_tmpdir=None,
         local_tmpdir=None):
    """This default main function can be used by project runner."""
    set_logging(logfile=log_path, loglevel='DEBUG' if debug else 'INFO')
    ctrl = Controller(config_path,
        work_dir=work_dir,
        local_tmpdir=local_tmpdir,
        remote_tmpdir=remote_tmpdir
    )
    ctrl.register_status_callback(reporter)
    ctrl.run_init(debug=debug, timeout=timeout)
    ctrl.run_deployment(debug=debug, timeout=timeout)
    ctrl.run_cleanup()
