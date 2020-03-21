# -*- coding: utf-8 -*-
from __future__ import (
    print_function,
    division,
    unicode_literals,
    absolute_import
)

try:
    from pathlib import PurePath  # PurePath is the base object for Paths.
except ImportError:  # pragma: no cover
    PurePath = object  # To avoid NameErrors.
    has_pathlib = False
else:
    has_pathlib = True
