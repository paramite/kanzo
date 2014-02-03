# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import copy

try:
    from collections import OrderedDict
except ImportError:
    # taken OrderedDict from Django.utils.datastructures and renamed
    # this is used for Python 2.6, fixed to be future compliant
    class OrderedDict(dict):
        """A dictionary that keeps it's keys in the order in which they're
        inserted.
        """
        def __init__(self, data=None):
            self.key_order = []

            if data is None or isinstance(data, dict):
                data = data or []
                super().__init__(data)
                self.key_order = list(data) if data else []
            else:
                super().__init__()
                super_set = super().__setitem__
                for key, value in data:
                    # Take the ordering from first key
                    if key not in self:
                        self.key_order.append(key)
                    # But override with last value in data (dict() does this)
                    super_set(key, value)

        def __deepcopy__(self, memo):
            return self.__class__([(key, copy.deepcopy(value, memo))
                                   for key, value in self.items()])

        def __setitem__(self, key, value):
            if key not in self:
                self.key_order.append(key)
            super().__setitem__(key, value)

        def __delitem__(self, key):
            super().__delitem__(key)
            self.key_order.remove(key)

        def __iter__(self):
            return iter(self.key_order)

        def __reversed__(self):
            return reversed(self.key_order)

        def pop(self, k, *args):
            result = super().pop(k, *args)
            try:
                self.key_order.remove(k)
            except ValueError:
                # Key wasn't in the dictionary in the first place. No problem.
                pass
            return result

        def popitem(self):
            result = super().popitem()
            self.key_order.remove(result[0])
            return result

        def items(self):
            return zip(self.key_order, list(self.values()))

        def keys(self):
            return iter(self.key_order)

        def values(self):
            for key in self.key_order:
                yield self[key]

        def update(self, dict_):
            for k, v in dict_.items():
                self[k] = v

        def setdefault(self, key, default):
            if key not in self:
                self.key_order.append(key)
            return super().setdefault(key, default)

        def value_for_index(self, index):
            """Returns the value of the item at the given zero-based index."""
            return self[self.key_order[index]]

        def insert(self, index, key, value):
            """Inserts the key, value pair before the item with the given
            index."""
            if key in self.key_order:
                n = self.key_order.index(key)
                del self.key_order[n]
                if n < index:
                    index -= 1
            self.key_order.insert(index, key)
            super().__setitem__(key, value)

        def copy(self):
            """Returns a copy of this object."""
            # This way of initializing the copy means it works for subclasses
            obj = self.__class__(self)
            obj.key_order = self.key_order[:]
            return obj

        def __repr__(self):
            """Replaces the normal dict.__repr__ with a version that returns
            the keys in their sorted order.
            """
            return '{%s}' % ', '.join(['%r: %r' % (k, v)
                                      for k, v in self.items()])

        def clear(self):
            super().clear()
            self.key_order = []


__all__ = ('OrderedDict')
