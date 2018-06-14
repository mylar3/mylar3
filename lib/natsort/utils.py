# -*- coding: utf-8 -*-
"""
Utilities and definitions for natsort, mostly all used to define
the _natsort_key function.

SOME CONVENTIONS USED IN THIS FILE.

1 - Factory Functions

Most of the logic of natsort revolves around factory functions
that create branchless transformation functions. For example, rather
than making a string transformation function that has an if
statement to determine whether or not to perform .lowercase() at
runtime for each element to transform, there is a string transformation
factory function that will return a function that either calls
.lowercase() or does nothing. In this way, all the branches and
decisions are taken care of once, up front. In addition to a slight
speed improvement, this provides a more extensible infrastructure.

Each of these factory functions will end with the suffix "_factory"
to indicate that they themselves return a function.

2 - Keyword Parameters For Local Scope

Many of the closures that are created by the factory functions
have signatures similar to the following

    >>> def factory(parameter):
    ...     val = 'yes' if parameter else 'no'
    ...     def closure(x, val=val):
    ...          return '{} {}'.format(val, x)
    ...     return closure
    ...

The variable value is passed as the default to a keyword argument.
This is a micro-optimization
that ensures "val" is a local variable instead of global variable
and thus has a slightly improved performance at runtime.

"""
from __future__ import (
    print_function,
    division,
    unicode_literals,
    absolute_import
)

# Std. lib imports.
import re
from warnings import warn
from os import curdir as os_curdir, pardir as os_pardir
from os.path import split as path_split, splitext as path_splitext
from itertools import chain as ichain
from collections import deque
from functools import partial, reduce
from operator import methodcaller
from unicodedata import normalize

# Local imports.
from natsort.ns_enum import ns
from natsort.unicode_numbers import numeric_no_decimals, digits_no_decimals
from natsort.compat.pathlib import PurePath, has_pathlib
from natsort.compat.locale import (
    get_strxfrm,
    get_thousands_sep,
    get_decimal_point,
)
from natsort.compat.py23 import (
    py23_str,
    py23_map,
    py23_filter,
    PY_VERSION,
    NEWPY,
)
from natsort.compat.fastnumbers import (
    fast_float,
    fast_int,
)
if PY_VERSION >= 3:
    long = int

# The regex that locates floats - include Unicode numerals.
_nnd = numeric_no_decimals
_exp = r'(?:[eE][-+]?\d+)?'
_num = r'(?:\d+\.?\d*|\.\d+)'
_float_sign_exp_re = r'([-+]?{0}{1}|[{2}])'
_float_sign_exp_re = _float_sign_exp_re.format(_num, _exp, _nnd)
_float_sign_exp_re = re.compile(_float_sign_exp_re, flags=re.U)
_float_nosign_exp_re = r'({0}{1}|[{2}])'
_float_nosign_exp_re = _float_nosign_exp_re.format(_num, _exp, _nnd)
_float_nosign_exp_re = re.compile(_float_nosign_exp_re, flags=re.U)
_float_sign_noexp_re = r'([-+]?{0}|[{1}])'
_float_sign_noexp_re = _float_sign_noexp_re.format(_num, _nnd)
_float_sign_noexp_re = re.compile(_float_sign_noexp_re, flags=re.U)
_float_nosign_noexp_re = r'({0}|[{1}])'
_float_nosign_noexp_re = _float_nosign_noexp_re.format(_num, _nnd)
_float_nosign_noexp_re = re.compile(_float_nosign_noexp_re, flags=re.U)

# Integer regexes - include Unicode digits.
_int_nosign_re = r'(\d+|[{0}])'.format(digits_no_decimals)
_int_nosign_re = re.compile(_int_nosign_re, flags=re.U)
_int_sign_re = r'([-+]?\d+|[{0}])'.format(digits_no_decimals)
_int_sign_re = re.compile(_int_sign_re, flags=re.U)

# This dict will help select the correct regex and number conversion function.
_regex_chooser = {
    (ns.F | ns.S):        _float_sign_exp_re,
    (ns.F | ns.S | ns.N): _float_sign_noexp_re,
    (ns.F | ns.U):        _float_nosign_exp_re,
    (ns.F | ns.U | ns.N): _float_nosign_noexp_re,
    (ns.I | ns.S):        _int_sign_re,
    (ns.I | ns.S | ns.N): _int_sign_re,
    (ns.I | ns.U):        _int_nosign_re,
    (ns.I | ns.U | ns.N): _int_nosign_re,
}


def _no_op(x):
    """A function that does nothing."""
    return x


def _normalize_input_factory(alg):
    """Create a function that will normalize unicode input data."""
    normalization_form = 'NFKD' if alg & ns.COMPATIBILITYNORMALIZE else 'NFD'

    if NEWPY:
        return partial(normalize, normalization_form)
    else:
        def func(x):
            """Normalize unicode input."""
            if isinstance(x, py23_str):  # unicode
                return normalize(normalization_form, x)
            else:
                return x
        return func


def _natsort_key(val, key, string_func, bytes_func, num_func):
    """\
    Key to sort strings and numbers naturally.

    It works by separating out the numbers from the strings. This function for
    internal use only. See the natsort_keygen documentation for details of each
    parameter.

    Parameters
    ----------
    val : str | unicode
    key : callable | None
    string_func : callable
    bytes_func : callable
    num_func : callable

    Returns
    -------
    out : tuple
        The modified value with numbers extracted.

    """

    # Apply key if needed
    if key is not None:
        val = key(val)

    # Assume the input are strings, which is the most common case
    try:
        return string_func(val)
    except (TypeError, AttributeError):

        # If bytes type, use the bytes_func
        if type(val) in (bytes,):
            return bytes_func(val)

        # Otherwise, assume it is an iterable that must be parses recursively.
        # Do not apply the key recursively.
        try:
            return tuple(_natsort_key(
                x, None, string_func, bytes_func, num_func
            ) for x in val)

        # If that failed, it must be a number.
        except TypeError:
            return num_func(val)


def _parse_bytes_factory(alg):
    """Create a function that will format a bytes string in a tuple."""
    # We don't worry about ns.UNGROUPLETTERS | ns.LOCALEALPHA because
    # bytes cannot be compared to strings.
    if alg & ns.PATH and alg & ns.IGNORECASE:
        return lambda x: ((x.lower(),),)
    elif alg & ns.PATH:
        return lambda x: ((x,),)
    elif alg & ns.IGNORECASE:
        return lambda x: (x.lower(),)
    else:
        return lambda x: (x,)


def _parse_number_factory(alg, sep, pre_sep):
    """Create a function that will properly format a number in a tuple."""
    nan_replace = float('+inf') if alg & ns.NANLAST else float('-inf')

    def func(val, nan_replace=nan_replace, sep=sep):
        """Given a number, place it in a tuple with a leading null string."""
        return sep, nan_replace if val != val else val

    # Return the function, possibly wrapping in tuple if PATH is selected.
    if alg & ns.PATH and alg & ns.UNGROUPLETTERS and alg & ns.LOCALEALPHA:
        return lambda x: (((pre_sep,), func(x)),)
    elif alg & ns.UNGROUPLETTERS and alg & ns.LOCALEALPHA:
        return lambda x: ((pre_sep,), func(x))
    elif alg & ns.PATH:
        return lambda x: (func(x),)
    else:
        return func


def _parse_string_factory(alg, sep, splitter,
                          input_transform,
                          component_transform,
                          final_transform):
    """Create a function that will properly split and format a string."""
    # Sometimes we store the "original" input before transformation,
    # sometimes after.
    orig_after_xfrm = not (alg & ns._DUMB and alg & ns.LOCALEALPHA)
    original_func = input_transform if orig_after_xfrm else _no_op
    normalize_input = _normalize_input_factory(alg)

    def func(x):
        # Apply string input transformation function and return to x.
        # Original function is usually a no-op, but some algorithms require it
        # to also be the transformation function.
        x = normalize_input(x)
        x, original = input_transform(x), original_func(x)
        x = splitter(x)                       # Split string into components.
        x = py23_filter(None, x)              # Remove empty strings.
        x = py23_map(component_transform, x)  # Apply transform on components.
        x = _sep_inserter(x, sep)             # Insert '' between numbers.
        return final_transform(x, original)   # Apply the final transform.

    return func


def _parse_path_factory(str_split):
    """Create a function that will properly split and format a path."""
    return lambda x: tuple(py23_map(str_split, _path_splitter(x)))


def _sep_inserter(iterable, sep):
    """Insert '' between numbers."""

    # Get the first element. If StopIteration is raised, that's OK.
    # Since we are controlling the types of the input, 'type' is used
    # instead of 'isinstance' for the small speed advantage it offers.
    try:
        types = (int, float, long)
        first = next(iterable)
        if type(first) in types:
            yield sep
        yield first

        # Now, check if pair of elements are both numbers. If so, add ''.
        second = next(iterable)
        if type(first) in types and type(second) in types:
            yield sep
        yield second

        # Now repeat in a loop.
        for x in iterable:
            first, second = second, x
            if type(first) in types and type(second) in types:
                yield sep
            yield second
    except StopIteration:
        # Catch StopIteration per deprecation in PEP 479:
        # "Change StopIteration handling inside generators"
        return


def _input_string_transform_factory(alg):
    """
    Given a set of natsort algorithms, return the function to operate
    on the pre-split input string according to the user's request.
    """
    # Shortcuts.
    lowfirst = alg & ns.LOWERCASEFIRST
    dumb = alg & ns._DUMB

    # Build the chain of functions to execute in order.
    function_chain = []
    if (dumb and not lowfirst) or (lowfirst and not dumb):
        function_chain.append(methodcaller('swapcase'))

    if alg & ns.IGNORECASE:
        if NEWPY:
            function_chain.append(methodcaller('casefold'))
        else:
            function_chain.append(methodcaller('lower'))

    if alg & ns.LOCALENUM:
        # Create a regular expression that will remove thousands separators.
        strip_thousands = r'''
            (?<=[0-9]{{1}})  # At least 1 number
            (?<![0-9]{{4}})  # No more than 3 numbers
            {nodecimal}      # Cannot follow decimal
            {thou}           # The thousands separator
            (?=[0-9]{{3}}    # Three numbers must follow
             ([^0-9]|$)      # But a non-number after that
            )
        '''
        nodecimal = r''
        if alg & ns.FLOAT:
            # Make a regular expression component that will ensure no
            # separators are removed after a decimal point.
            d = get_decimal_point()
            d = r'\.' if d == r'.' else d
            nodecimal += r'(?<!' + d + r'[0-9])'
            nodecimal += r'(?<!' + d + r'[0-9]{2})'
            nodecimal += r'(?<!' + d + r'[0-9]{3})'
        strip_thousands = strip_thousands.format(thou=get_thousands_sep(),
                                                 nodecimal=nodecimal)
        strip_thousands = re.compile(strip_thousands, flags=re.VERBOSE)
        function_chain.append(partial(strip_thousands.sub, ''))

        # Create a regular expression that will change the decimal point to
        # a period if not already a period.
        decimal = get_decimal_point()
        if alg & ns.FLOAT and decimal != '.':
            switch_decimal = r'(?<=[0-9]){decimal}|{decimal}(?=[0-9])'
            switch_decimal = switch_decimal.format(decimal=decimal)
            switch_decimal = re.compile(switch_decimal)
            function_chain.append(partial(switch_decimal.sub, '.'))

    # Return the chained functions.
    return chain_functions(function_chain)


def _string_component_transform_factory(alg):
    """
    Given a set of natsort algorithms, return the function to operate
    on the post-split strings according to the user's request.
    """
    # Shortcuts.
    use_locale = alg & ns.LOCALEALPHA
    dumb = alg & ns._DUMB
    group_letters = (alg & ns.GROUPLETTERS) or (use_locale and dumb)
    nan_val = float('+inf') if alg & ns.NANLAST else float('-inf')

    # Build the chain of functions to execute in order.
    func_chain = []
    if group_letters:
        func_chain.append(_groupletters)
    if use_locale:
        func_chain.append(get_strxfrm())
    kwargs = {'key': chain_functions(func_chain)} if func_chain else {}

    # Return the correct chained functions.
    if alg & ns.FLOAT:
        kwargs['nan'] = nan_val
        return partial(fast_float, **kwargs)
    else:
        return partial(fast_int, **kwargs)


def _final_data_transform_factory(alg, sep, pre_sep):
    """
    Given a set of natsort algorithms, return the function to operate
    on the post-parsed strings according to the user's request.
    """
    if alg & ns.UNGROUPLETTERS and alg & ns.LOCALEALPHA:
        swap = alg & ns._DUMB and alg & ns.LOWERCASEFIRST
        transform = methodcaller('swapcase') if swap else _no_op

        def func(split_val, val, transform=transform):
            """
            Return a tuple with the first character of the first element
            of the return value as the first element, and the return value
            as the second element. This will be used to perform gross sorting
            by the first letter.
            """
            split_val = tuple(split_val)
            if not split_val:
                return (), ()
            elif split_val[0] == sep:
                return (pre_sep,), split_val
            else:
                return (transform(val[0]),), split_val
        return func
    else:
        return lambda split_val, val: tuple(split_val)


def _groupletters(x, _low=methodcaller('casefold' if NEWPY else 'lower')):
    """Double all characters, making doubled letters lowercase."""
    return ''.join(ichain.from_iterable((_low(y), y) for y in x))


def chain_functions(functions):
    """
    Chain a list of single-argument functions together and return.

    The functions are applied in list order, and the output of the
    previous functions is passed to the next function.

    Parameters
    ----------
    functions : list
        A list of single-argument functions to chain together.

    Returns
    -------
    A single argument function.

    Examples
    --------
    Chain several functions together!

        >>> funcs = [lambda x: x * 4, len, lambda x: x + 5]
        >>> func = chain_functions(funcs)
        >>> func('hey')
        17

    """
    functions = list(functions)
    if not functions:
        return _no_op
    elif len(functions) == 1:
        return functions[0]
    else:
        # See https://stackoverflow.com/a/39123400/1399279
        return partial(reduce, lambda res, f: f(res), functions)


def _do_decoding(s, encoding):
    """A function to decode a bytes string, or return the object as-is."""
    try:
        return s.decode(encoding)
    except UnicodeError:
        raise
    except (AttributeError, TypeError):
        return s


def _path_splitter(s, _d_match=re.compile(r'\.\d').match):
    """Split a string into its path components. Assumes a string is a path."""
    # If a PathLib Object, use it's functionality to perform the split.
    if has_pathlib and isinstance(s, PurePath):
        s = py23_str(s)
    path_parts = deque()
    p_appendleft = path_parts.appendleft
    # Continue splitting the path from the back until we have reached
    # '..' or '.', or until there is nothing left to split.
    path_location = s
    while path_location != os_curdir and path_location != os_pardir:
        parent_path = path_location
        path_location, child_path = path_split(parent_path)
        if path_location == parent_path:
            break
        p_appendleft(child_path)

    # This last append is the base path.
    # Only append if the string is non-empty.
    if path_location:
        p_appendleft(path_location)

    # Now, split off the file extensions using a similar method to above.
    # Continue splitting off file extensions until we reach a decimal number
    # or there are no more extensions.
    # We are not using built-in functionality of PathLib here because of
    # the recursive splitting up to a decimal.
    base = path_parts.pop()
    base_parts = deque()
    b_appendleft = base_parts.appendleft
    while True:
        front = base
        base, ext = path_splitext(front)
        if _d_match(ext) or not ext:
            # Reset base to before the split if the split is invalid.
            base = front
            break
        b_appendleft(ext)
    b_appendleft(base)

    # Return the split parent paths and then the split basename.
    return ichain(path_parts, base_parts)


def _args_to_enum(**kwargs):
    """A function to convert input booleans to an enum-type argument."""
    alg = 0
    keys = ('number_type', 'signed', 'exp', 'as_path', 'py3_safe')
    if any(x not in keys for x in kwargs):
        x = set(kwargs) - set(keys)
        raise TypeError('Invalid argument(s): ' + ', '.join(x))
    if 'number_type' in kwargs and kwargs['number_type'] is not int:
        msg = "The 'number_type' argument is deprecated as of 3.5.0, "
        msg += "please use 'alg=ns.FLOAT', 'alg=ns.INT', or 'alg=ns.VERSION'"
        warn(msg, DeprecationWarning)
        alg |= (ns.FLOAT * bool(kwargs['number_type'] is float))
        alg |= (ns.INT * bool(kwargs['number_type'] in (int, None)))
        alg |= (ns.SIGNED * (kwargs['number_type'] not in (float, None)))
    if 'signed' in kwargs and kwargs['signed'] is not None:
        msg = "The 'signed' argument is deprecated as of 3.5.0, "
        msg += "please use 'alg=ns.SIGNED'."
        warn(msg, DeprecationWarning)
        alg |= (ns.SIGNED * bool(kwargs['signed']))
    if 'exp' in kwargs and kwargs['exp'] is not None:
        msg = "The 'exp' argument is deprecated as of 3.5.0, "
        msg += "please use 'alg=ns.NOEXP'."
        warn(msg, DeprecationWarning)
        alg |= (ns.NOEXP * (not kwargs['exp']))
    if 'as_path' in kwargs and kwargs['as_path'] is not None:
        msg = "The 'as_path' argument is deprecated as of 3.5.0, "
        msg += "please use 'alg=ns.PATH'."
        warn(msg, DeprecationWarning)
        alg |= (ns.PATH * kwargs['as_path'])
    return alg
