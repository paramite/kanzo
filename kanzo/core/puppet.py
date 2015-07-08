# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import collections
import jinja2
import logging
import os
import re
import tempfile
import yaml

from ..conf import project, Config


LOG = logging.getLogger('kanzo.backend')


#---------------------------- log handling ------------------------------------
class LogChecker(object):
    color = re.compile('\x1b.*?\d\dm')
    errors = re.compile('|'.join(project.PUPPET_ERRORS))
    ignore = [re.compile(i)
              for i in project.PUPPET_ERROR_IGNORE]
    surrogates = [(re.compile(i[0]), i[1])
                  for i in project.PUPPET_ERROR_SURROGATES]

    def _preproces(self, line):
        return self.color.sub('', line.strip())  # remove colors

    def _check_ignore(self, line):
        skip = False
        for ign in self.ignore:
            if ign.search(line):
                LOG.debug('Ignoring expected Puppet: %s' % line)
                skip = True
                break
        return skip

    def _check_surrogates(self, line):
        for regex, surrogate in self.surrogates:
            match = regex.search(line)
            if match is None:
                continue

            args = {}
            num = 1
            while True:
                try:
                    args['arg%d' % num] = match.group(num)
                    num += 1
                except IndexError:
                    break
            return surrogate % args
        return line

    def validate(self, path):
        """Check given Puppet log file for errors and raise RuntimeError
        if there is any error.
        """
        with open(path) as logfile:
            for line in logfile:
                line = self._preproces(line)
                if self.errors.search(line) is None:
                    continue
                if self._check_ignore(line):
                    continue
                raise RuntimeError(self._check_surrogates(line))

#--------------------------- hiera handling -----------------------------------
class HieraYAMLLibrary(object):
    """Holds content of Hiera YAML files."""
    def __init__(self):
        self._content = {}

    def set(self, name, key, value):
        """Adds hiera setting (key, value) to file 'name'."""
        self._content.setdefault(name, {})[key] = value

    def get(self, name, key):
        """Returns hiera setting (key) in file 'name'."""
        self._content[name][key]

    def set_dict(self, name, content):
        """Adds hiera settings (content) dictonary to file 'name'."""
        self._content[name] = content

    def render(self, name):
        return yaml.dump(
            self._content[name],
            explicit_start=True,
            default_flow_style=False
        )


_hieralib = HieraYAMLLibrary()
def update_hiera(name, variable, value):
    """This function should be used to dynamicaly insert configuration
    in Hiera YAML files.
    """
    _hieralib.set(name, variable, value)

def render_hiera():
    for name in _hieralib._content.keys():
        yield name, _hieralib.render(name)


#------------------------------ Manifest handling -----------------------------
class ManifestLibrary(object):
    """Objects of this class are used to glue single manifest template
    from small manifest templates. Resulting manifest template can be rendered
    to manifest file afterwards.
    """
    def __init__(self):
        self._manifests = {}
        loader = jinja2.FileSystemLoader(
            searchpath=project.PUPPET_MANIFEST_TEMPLATE_DIRS,
        )
        self._env = jinja2.Environment(loader=loader)

    def add_fragment(self, name, path, context=None):
        """Append manifest template fragment given by path to file and context
        dictionary with which it will be rendered.
        """
        if not os.path.isfile(path):
            raise ValueError(
                'Given manifest fragment does not exist: {}'.format(path)
            )
        self._manifests.setdefault(name, []).append((path, context))

    def render(self, name, tmpdir=None, config=None):
        """Returns rendered manifest from all added fragments"""
        config = config or {}
        tmpdir = tmpdir or project.PROJECT_RUN_TEMPDIR
        # generate manifest content
        content = ''
        for path, context in self._manifests[name]:
            context = context or {}
            context.update(config)
            template = self._env.get_template(path)
            content += template.render(**context)
        # save content to manifest file
        path = os.path.join(tmpdir, '{}.pp'.format(name))
        with open(path, 'w') as manifest:
            manifest.write(content)
        return path


_manifestlib = ManifestLibrary()
def update_manifest(name, path, context=None):
    """Dynamicaly concatenate manifest (name) from several fragments (path).
    When rendering fragments will be formatted with content of config
    dictionary and context dictionary.
    """
    _manifestlib.add_fragment(name, path, context=context)

def update_manifest_inline(name, content, context=None):
    """Dynamicaly concatenate manifest (name) from several fragments (content).
    When rendering fragments will be formatted with content of config
    dictionary and context dictionary.
    """
    tmpdir = os.path.join(project.PROJECT_RUN_TEMPDIR, 'fragments')
    if not os.path.isdir(tmpdir):
        os.makedirs(tmpdir)
    fd, path = tempfile.mkstemp(dir=tmpdir)
    with fdopen(fd, 'w') as fragment:
        fragment.write(content)
    _manifestlib.add_fragment(name, path, context=context)

def render_manifests(config=None):
    for name in _manifestlib._manifests.keys():
        yield name, _manifestlib.render(name, config=config)
