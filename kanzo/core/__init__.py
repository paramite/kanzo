# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


from .. import conf
from . import controller


def main(config_path, log_path=None, debug=False, work_dir=None):
    """This default main function can be used by project runner.
    Projects can have their own main function though.
    """
    conf.set_logging(log_file=log_path, log_level='DEBUG' if debug else 'INFO')
    cont = controller.Controller(config_path, work_dir=work_dir)
    # TO-DO
