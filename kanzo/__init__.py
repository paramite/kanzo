# -*- coding: utf-8 -*-

"""
Kanzo: Simple framework for creating CLI installers using Puppet.
"""

__version__ = '0.0.1'
__author__  = 'Martin Mágr'
__license__ = 'LGPL'

from gevent import monkey
monkey.patch_all()

from .conf import project
