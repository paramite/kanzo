#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


setup(
    name='kanzo',
    version='0.0.1',
    author='Martin Magr',
    author_email='martin.magr@gmail.com',
    description=(
        'Kanzo is a simple framework for implementing command line installer.'
    ),
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'paramiko',
        'greenlet',
        'jinja2',
        'pyyaml',
    ],
)
