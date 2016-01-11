# -*- coding: utf-8 -*-

import logging

from ..conf import project

from . import config
from . import decorators
from . import shell
from . import shortcuts
from . import strings


LOG = logging.getLogger('kanzo.backend')


def set_logging(logfile=None, loglevel=None):
    """Sets logging if it is required by project or if the function was called
    with parameters.
    """
    if not logfile and not loglevel and not project.SET_LOGGING:
        return
    logfile = logfile or project.LOG_FILE
    loglevel = loglevel or project.LOG_LEVEL
    handler = logging.FileHandler(filename=logfile, mode='a')
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s [%(levelname)s]: %(message)s',
            '%Y-%m-%d %H:%M:%S'
        )
    )
    LOG.addHandler(handler)
    LOG.setLevel(getattr(logging, loglevel))
