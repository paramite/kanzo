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


#--------------------------- Hiera handling -----------------------------------
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
        self._content.setdefault(name, {}).update(content)

    def dump(self, name):
        """Returns hiera file content"""
        return yaml.dump(
            self._content[name],
            explicit_start=True,
            default_flow_style=False
        )

    def render(self, name, tmpdir=None):
        """Write hiera file to given temporary directory."""
        path = os.path.join(tmpdir, '{}.yaml'.format(name))
        with open(path, 'w') as manifest:
            manifest.write(self.dump(name))
        return path


_hieralib = HieraYAMLLibrary()
def update_hiera(name, content):
    """This function should be used to dynamicaly insert configuration
    in Hiera YAML files.
    """
    _hieralib.set_dict(name, content)


def update_hiera_single(name, variable, value):
    """This function should be used to dynamicaly insert configuration
    in Hiera YAML files.
    """
    _hieralib.set(name, variable, value)


def render_hiera(name, tmpdir=None):
    return _hieralib.render(name, tmpdir=tmpdir)


def render_whole_hiera(tmpdir=None):
    for name in _hieralib._content.keys():
        yield name, render_hiera(name, tmpdir)


#------------------------------ Manifest handling -----------------------------
class ManifestLibrary(object):
    """Objects of this class are used to glue single manifest template
    from small manifest templates. Resulting manifest template can be rendered
    to manifest file afterwards.
    """

    TMP_FRAGMENTS = os.path.join(project.PROJECT_RUN_TEMPDIR, 'tmp_fragments')

    def __init__(self):
        if not os.path.isdir(self.TMP_FRAGMENTS):
            os.makedirs(self.TMP_FRAGMENTS)
        self._manifests = {}
        template_dirs = project.PUPPET_MANIFEST_TEMPLATE_DIRS
        template_dirs.append(self.TMP_FRAGMENTS)
        loader = jinja2.FileSystemLoader(searchpath=template_dirs)
        self._env = jinja2.Environment(loader=loader)

    def add_fragment(self, name, path, context=None, hiera=None):
        """Append manifest template fragment given by path to file and context
        dictionary with which it will be rendered.
        """
        self._env.get_template(path)
        self._manifests.setdefault(name, []).append((path, context, hiera))

    def register_manifest_hiera(self, name):
        """Registers hiera data for given manifest."""
        hiera = {}
        for path, context, fragment_hiera in self._manifests[name]:
            hiera.update(fragment_hiera or {})
        _hieralib.set_dict(name, hiera)

    def dump(self, name, config=None):
        """Concatenates fragments of manifests, renders the resulting template
        with fragments' context and given config and returns rendered content.
        """
        content = ''
        for path, context, fragment_hiera in self._manifests[name]:
            context = context or {}
            context.update(config)
            template = self._env.get_template(path)
            content += template.render(**context)
        return content

    def render(self, name, tmpdir=None, config=None):
        """Renders manifest from all fragments and saves it to given temporary
        directory."""
        config = config or {}
        tmpdir = tmpdir or project.PROJECT_RUN_TEMPDIR
        # save content to manifest file
        path = os.path.join(tmpdir, '{}.pp'.format(name))
        with open(path, 'w') as manifest:
            manifest.write(self.dump(name, config=config))
        return path


_manifestlib = ManifestLibrary()
def update_manifest(name, path, context=None, hiera=None):
    """Dynamicaly concatenate manifest (name) from several fragments (path).
    When rendering fragments will be formatted with content of config
    dictionary and context dictionary.
    """
    _manifestlib.add_fragment(name, path, context=context, hiera=hiera)


def update_manifest_inline(name, content, context=None, hiera=None):
    """Dynamicaly concatenate manifest (name) from several fragments (content).
    When rendering fragments will be formatted with content of config
    dictionary and context dictionary.
    """
    fd, path = tempfile.mkstemp(dir=_manifestlib.TMP_FRAGMENTS)
    with os.fdopen(fd, mode='w') as fragment:
        fragment.write(content)
    _manifestlib.add_fragment(
        name, os.path.basename(path), context=context, hiera=hiera
    )


def render_manifest(name, tmpdir=None, config=None):
    _manifestlib.register_manifest_hiera(name)
    return _manifestlib.render(name, tmpdir=tmpdir, config=config)


def render_all_manifests(tmpdir=None, config=None):
    for name in _manifestlib._manifests.keys():
        yield name, render_manifest(name, tmpdir=tmpdir, config=config)
