# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import os
import sys

from unittest import TestCase

from kanzo.conf import Config, iter_hosts, get_hosts, validators
from kanzo.core.plugins import meta_builder

from ..plugins import sql
from . import _KANZO_PATH


def change_processor(value, key, config):
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
        meta.update({
            'default1/var': {'default': '3'},
            'default2/arr': {'default': '1,2,3', 'is_multi': True},
            'test/var': {'default': '3'},
            'test/arr': {'default': '1,2,3', 'is_multi': True},
            'test/processor': {'processors': [change_processor]},
            'test/processor_multi': {
                'processors': [change_processor], 'is_multi': True
            },
        })
        self._config = Config(self._path, meta)

    def test_defaults(self):
        """[Config] Test default value behaviour"""
        self.assertEquals(self._config['default1/var'], '3')
        self.assertEquals(self._config['default2/arr'], ['1', '2', '3'])

    def test_values(self):
        """[Config] Test value fetching from file"""
        self.assertEquals(self._config['sql/host'], '127.0.0.1')
        self.assertEquals(self._config['sql/backend'], 'mysql')
        self.assertEquals(self._config['sql/admin_user'], 'test')
        self.assertEquals(self._config['sql/admin_password'], 'testtest')
        self.assertEquals(self._config['test/var'], 'a')
        self.assertEquals(self._config['test/arr'], ['a', 'b', 'c'])

    def test_processor(self):
        """[Config] Test parameter processor calling"""
        self.assertEquals(self._config['test/processor'], 'changedvalue')
        self.assertEquals(
            self._config['test/processor_multi'],
            ['original', 'changedvalue', 'unchanged']
        )

    def test_validator(self):
        """[Config] Test parameter validator calling"""
        meta = {'test/validator1': {'validators': [invalid_validator]}}
        self.assertRaises(ValueError, Config, self._path, meta)

        meta = {'test/validator2': {'validators': [invalid_validator]}}
        config = Config(self._path, meta)
        self.assertEquals(config['test/validator2'], 'valid')

        meta = {
            'test/validator3': {
                'validators': [invalid_validator],
                'is_multi': True
            }
        }
        self.assertRaises(ValueError, Config, self._path, meta)

        meta = {
            'test/validator4': {
                'validators': [invalid_validator],
                'is_multi': True
            }
        }
        config = Config(self._path, meta)
        self.assertEquals(config['test/validator4'], ['all', 'valid'])

    def test_options(self):
        """[Config] Test options"""
        meta = {'test/options1': {'options': ['1', '2', '3']}}
        config = Config(self._path, meta)
        self.assertEquals(config['test/options1'], '2')

        meta = {'test/options2': {'options': ['1', '2', '3']}}
        self.assertRaises(ValueError, Config, self._path, meta)

        meta = {
            'test/options3': {
                'options': ['1', '2', '3'],
                'is_multi': True
                }
        }
        config = Config(self._path, meta)
        self.assertEquals(config['test/options3'], ['2', '3'])

        meta = {
            'test/options4': {
                'options': ['1', '2', '3'],
                'is_multi': True
                }
        }
        self.assertRaises(ValueError, Config, self._path, meta)


class ValidatorsTestCase(TestCase):

    def test_validators(self):
        """[Config] Test built-in parameter validators"""
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
