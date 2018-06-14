# -*- coding: utf-8 -*-
from __future__ import (
    print_function,
    division,
    unicode_literals,
    absolute_import
)

# Local imports.
import sys

from natsort.utils import chain_functions
from natsort._version import __version__

from natsort.natsort import (
    natsort_key,
    natsort_keygen,
    natsorted,
    versorted,
    humansorted,
    realsorted,
    index_natsorted,
    index_versorted,
    index_humansorted,
    index_realsorted,
    order_by_index,
    decoder,
    as_ascii,
    as_utf8,
    ns,
)

if float(sys.version[:3]) < 3:
    from natsort.natsort import natcmp

__all__ = [
    'natsort_key',
    'natsort_keygen',
    'natsorted',
    'versorted',
    'humansorted',
    'realsorted',
    'index_natsorted',
    'index_versorted',
    'index_humansorted',
    'index_realsorted',
    'order_by_index',
    'decoder',
    'natcmp',
    'as_ascii',
    'as_utf8',
    'ns',
    'chain_functions',
]

# Add the ns keys to this namespace for convenience.
globals().update(
    dict((k, v) for k, v in vars(ns).items() if not k.startswith('_'))
)
