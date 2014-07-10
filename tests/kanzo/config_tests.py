# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import os
import sys

_KANZO_PATH = os.path.dirname(__file__)
for i in range(3): # get rid of 'kanzo/tests/kanzo/conf
    _KANZO_PATH = os.path.dirname(_KANZO_PATH)
sys.path.insert(0, _KANZO_PATH)

from unittest import TestCase

from kanzo.conf import Config, iter_hosts, get_hosts, validators
from kanzo.core.plugins import meta_builder

from ..plugins import sql


def change_processor(value, key, config):
    assert key == 'default_test/test3'
    if value == 'changeme':
        return 'changedvalue'
    return value


def invalid_validator(value, key, config):
    if value == 'invalid':
        raise ValueError('Value is invalid')


class ConfigTestCase(TestCase):
    def setUp(self):
        self._path = os.path.join(_KANZO_PATH, 'kanzo/tests/test_config.txt')
        meta = meta_builder([sql])
        meta['nosection/test1'] = {'name': 'nosection/test1',
                                   'default': 'test1'}
        meta['default_test/test2'] = {'name': 'default_test/test2',
                                      'default': 'test2'}
        meta['default_test/test3'] = {'name': 'default_test/test3',
                                      'processors': [change_processor]}
        self._config = Config(self._path, meta)

    def test_defaults(self):
        """[Config] Test default values behaviour"""
        self.assertEquals(self._config['nosection/test1'], 'test1')
        self.assertEquals(self._config['default_test/test2'], 'test2')

    def test_values(self):
        """[Config] Test value fetching from file"""
        self.assertEquals(self._config['sql/host'], '127.0.0.1')
        self.assertEquals(self._config['sql/backend'], 'mysql')
        self.assertEquals(self._config['sql/admin_user'], 'test')
        self.assertEquals(self._config['sql/admin_password'], 'testtest')

    def test_processor(self):
        """[Config] Test parameter processor calling"""
        self.assertEquals(self._config['default_test/test3'], 'changedvalue')

    def test_validator(self):
        """[Config] Test parameter validator calling"""
        meta = {'default_test/test4': {'name': 'default_test/test4',
                                       'validators': [invalid_validator]}}
        self.assertRaises(ValueError, Config, self._path, meta)

        meta = {'default_test/test5': {'name': 'default_test/test5',
                                       'validators': [invalid_validator]}}
        config = Config(self._path, meta)
        self.assertEquals(config['default_test/test5'], 'valid')

    def test_iterhost(self):
        """[Config] Test host generator"""
        meta = meta_builder([sql])
        meta['foo/test1_host'] =  {'name': 'foo/test1_host',
                                   'default': '1.2.3.4'}
        meta['foo/test2_host'] =  {'name': 'foo/test2_host',
                                   'default': '5.6.7.8'}


class ValidatorsTestCase(TestCase):

    def test_validators(self):
        """[Config] Test parameter validators"""
        validators.validate_not_empty('foo')
        self.assertRaises(ValueError, validators.validate_not_empty, '')

        validators.validate_integer('3')
        self.assertRaises(ValueError, validators.validate_integer, '3.3')
        self.assertRaises(ValueError, validators.validate_integer, 'foo')

        validators.validate_float('3.3')
        validators.validate_float('3')
        self.assertRaises(ValueError, validators.validate_float, 'foo')

        conf = {'test': {'regexps': ['^foo.*bar$', '.*baz.*']}}
        validators.validate_regexp('foobazbar', key='test', config=conf)
        validators.validate_regexp('bazooka', key='test', config=conf)
        self.assertRaises(ValueError, validators.validate_regexp, 'foo',
                          key='test', config=conf)

        validators.validate_ip('127.0.0.1')
        validators.validate_ip('::0')
        self.assertRaises(ValueError, validators.validate_ip, '666.0.0.666')
        self.assertRaises(ValueError, validators.validate_ip, 'AE:CD:24:34')

        validators.validate_port('22')
        self.assertRaises(ValueError, validators.validate_port, '-2')
        self.assertRaises(ValueError, validators.validate_port, '1000000')
