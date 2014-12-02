# -*- coding: utf-8 -*-

import os


TESTS_ABS_PATH = os.path.dirname(os.environ.get('KANZO_PROJECT', __file__))

PLUGIN_PATHS = [os.path.join(TESTS_ABS_PATH, 'plugins')]
PLUGINS = ['sql', 'nosql']
