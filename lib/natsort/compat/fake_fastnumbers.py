# -*- coding: utf-8 -*-
"""\
This module is intended to replicate some of the functionality
from the fastnumbers module in the event that module is not
installed.
"""
from __future__ import (
    print_function,
    division,
    unicode_literals,
    absolute_import
)

# Std. lib imports.
import unicodedata
from natsort.unicode_numbers import decimal_chars
from natsort.compat.py23 import PY_VERSION
if PY_VERSION >= 3:
    long = int


NAN_INF = ['INF', 'INf', 'Inf', 'inF', 'iNF', 'InF', 'inf', 'iNf',
           'NAN', 'nan', 'NaN', 'nAn', 'naN', 'NAn', 'nAN', 'Nan']
NAN_INF.extend(['+'+x[:2] for x in NAN_INF] + ['-'+x[:2] for x in NAN_INF])
NAN_INF = frozenset(NAN_INF)
ASCII_NUMS = '0123456789+-'


def fast_float(x, key=lambda x: x, nan=None,
               uni=unicodedata.numeric, nan_inf=NAN_INF,
               _first_char=frozenset(decimal_chars + list(ASCII_NUMS + '.'))):
    """\
    Convert a string to a float quickly, return input as-is if not possible.
    We don't need to accept all input that the real fast_int accepts because
    the input will be controlled by the splitting algorithm.
    """
    if x[0] in _first_char or x.lstrip()[:3] in nan_inf:
        try:
            x = float(x)
            return nan if nan is not None and x != x else x
        except ValueError:
            try:
                return uni(x, key(x)) if len(x) == 1 else key(x)
            except TypeError:  # pragma: no cover
                return key(x)
    else:
        try:
            return uni(x, key(x)) if len(x) == 1 else key(x)
        except TypeError:  # pragma: no cover
            return key(x)


def fast_int(x, key=lambda x: x, nan=None, uni=unicodedata.digit,
             _first_char=frozenset(decimal_chars + list(ASCII_NUMS))):
    """\
    Convert a string to a int quickly, return input as-is if not possible.
    We don't need to accept all input that the real fast_int accepts because
    the input will be controlled by the splitting algorithm.
    """
    if x[0] in _first_char:
        try:
            return long(x)
        except ValueError:
            try:
                return uni(x, key(x)) if len(x) == 1 else key(x)
            except TypeError:  # pragma: no cover
                return key(x)
    else:
        try:
            return uni(x, key(x)) if len(x) == 1 else key(x)
        except TypeError:  # pragma: no cover
            return key(x)
