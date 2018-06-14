# -*- coding: utf-8 -*-
from __future__ import (
    print_function,
    division,
    unicode_literals,
    absolute_import
)

import functools
import sys

# These functions are used to make the doctests compatible between
# python2 and python3, and also provide uniform functionality between
# the two versions.  This code is pretty much lifted from the iPython
# project's py3compat.py file.  Credit to the iPython devs.

# Numeric form of version
PY_VERSION = float(sys.version[:3])
NEWPY = PY_VERSION >= 3.3

# Assume all strings are Unicode in Python 2
py23_str = str if sys.version[0] == '3' else unicode

# Use the range iterator always
py23_range = range if sys.version[0] == '3' else xrange

# Uniform base string type
py23_basestring = str if sys.version[0] == '3' else basestring

# unichr function
py23_unichr = chr if sys.version[0] == '3' else unichr


def _py23_cmp(a, b):
    return (a > b) - (a < b)


py23_cmp = _py23_cmp if sys.version[0] == '3' else cmp

# zip as an iterator
if sys.version[0] == '3':
    py23_zip = zip
    py23_map = map
    py23_filter = filter
else:
    import itertools
    py23_zip = itertools.izip
    py23_map = itertools.imap
    py23_filter = itertools.ifilter


# cmp_to_key was not created till 2.7, so require this for 2.6
try:
    from functools import cmp_to_key
except ImportError:  # pragma: no cover
    def cmp_to_key(mycmp):
        """Convert a cmp= function into a key= function"""
        class K(object):
            __slots__ = ['obj']

            def __init__(self, obj):
                self.obj = obj

            def __lt__(self, other):
                return mycmp(self.obj, other.obj) < 0

            def __gt__(self, other):
                return mycmp(self.obj, other.obj) > 0

            def __eq__(self, other):
                return mycmp(self.obj, other.obj) == 0

            def __le__(self, other):
                return mycmp(self.obj, other.obj) <= 0

            def __ge__(self, other):
                return mycmp(self.obj, other.obj) >= 0

            def __ne__(self, other):
                return mycmp(self.obj, other.obj) != 0

            def __hash__(self):
                raise TypeError('hash not implemented')

        return K


# This function is intended to decorate other functions that will modify
# either a string directly, or a function's docstring.
def _modify_str_or_docstring(str_change_func):
    @functools.wraps(str_change_func)
    def wrapper(func_or_str):
        if isinstance(func_or_str, py23_basestring):
            func = None
            doc = func_or_str
        else:
            func = func_or_str
            doc = func.__doc__

        if doc is not None:
            doc = str_change_func(doc)

        if func:
            func.__doc__ = doc
            return func
        return doc
    return wrapper


# Properly modify a doctstring to either have the unicode literal or not.
if sys.version[0] == '3':
    # Abstract u'abc' syntax:
    @_modify_str_or_docstring
    def u_format(s):
        """"{u}'abc'" --> "'abc'" (Python 3)

        Accepts a string or a function, so it can be used as a decorator."""
        return s.format(u='')
else:
    # Abstract u'abc' syntax:
    @_modify_str_or_docstring
    def u_format(s):
        """"{u}'abc'" --> "u'abc'" (Python 2)

        Accepts a string or a function, so it can be used as a decorator."""
        return s.format(u='u')
