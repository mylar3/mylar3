# -*- coding: utf-8 -*-
from __future__ import (
    print_function,
    division,
    unicode_literals,
    absolute_import
)

# Std. lib imports.
import sys

# Local imports.
from natsort.natsort import natsorted, ns
from natsort.utils import _regex_chooser
from natsort._version import __version__
from natsort.compat.py23 import py23_str


def main():
    """\
    Performs a natural sort on entries given on the command-line.
    A natural sort sorts numerically then alphabetically, and will sort
    by numbers in the middle of an entry.
    """

    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    from textwrap import dedent
    parser = ArgumentParser(description=dedent(main.__doc__),
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('--version', action='version',
                        version='%(prog)s {0}'.format(__version__))
    parser.add_argument(
        '-p', '--paths', default=False, action='store_true',
        help='Interpret the input as file paths.  This is not '
             'strictly necessary to sort all file paths, but in cases '
             'where there are OS-generated file paths like "Folder/" '
             'and "Folder (1)/", this option is needed to make the '
             'paths sorted in the order you expect ("Folder/" before '
             '"Folder (1)/").')
    parser.add_argument(
        '-f', '--filter', nargs=2, type=float, metavar=('LOW', 'HIGH'),
        action='append',
        help='Used for keeping only the entries that have a number '
             'falling in the given range.')
    parser.add_argument(
        '-F', '--reverse-filter', nargs=2, type=float,
        metavar=('LOW', 'HIGH'), action='append', dest='reverse_filter',
        help='Used for excluding the entries that have a number '
             'falling in the given range.')
    parser.add_argument(
        '-e', '--exclude', type=float, action='append',
        help='Used to exclude an entry that contains a specific number.')
    parser.add_argument(
        '-r', '--reverse', action='store_true', default=False,
        help='Returns in reversed order.')
    parser.add_argument(
        '-t', '--number-type', '--number_type', dest='number_type',
        choices=('digit', 'int', 'float', 'version', 'ver',
                 'real', 'f', 'i', 'r', 'd'),
        default='int',
        help='Choose the type of number to search for. "float" will search '
             'for floating-point numbers.  "int" will only search for '
             'integers. "digit", "version", and "ver" are synonyms for "int".'
             '"real" is a shortcut for "float" with --sign. '
             '"i" and "d" are synonyms for "int", "f" is a synonym for '
             '"float", and "r" is a synonym for "real".'
             'The default is %(default)s.')
    parser.add_argument(
        '--nosign', default=False, action='store_false', dest='signed',
        help='Do not consider "+" or "-" as part of a number, i.e. do not '
             'take sign into consideration. This is the default.')
    parser.add_argument(
        '-s', '--sign', default=False, action='store_true', dest='signed',
        help='Consider "+" or "-" as part of a number, i.e. '
             'take sign into consideration. The default is unsigned.')
    parser.add_argument(
        '--noexp', default=True, action='store_false', dest='exp',
        help='Do not consider an exponential as part of a number, i.e. 1e4, '
             'would be considered as 1, "e", and 4, not as 10000.  This only '
             'effects the --number-type=float.')
    parser.add_argument(
        '-l', '--locale', action='store_true', default=False,
        help='Causes natsort to use locale-aware sorting. You will get the '
             'best results if you install PyICU.')
    parser.add_argument(
        'entries', nargs='*', default=sys.stdin,
        help='The entries to sort. Taken from stdin if nothing is given on '
             'the command line.', )
    args = parser.parse_args()

    # Make sure the filter range is given properly. Does nothing if no filter
    args.filter = check_filter(args.filter)
    args.reverse_filter = check_filter(args.reverse_filter)

    # Remove trailing whitespace from all the entries
    entries = [e.strip() for e in args.entries]

    # Sort by directory then by file within directory and print.
    sort_and_print_entries(entries, args)


def range_check(low, high):
    """\
    Verifies that that given range has a low lower than the high.
    If the condition is not met, a ValueError is raised.
    Otherwise the input is returned as-is.
    """
    if low >= high:
        raise ValueError('low >= high')
    else:
        return low, high


def check_filter(filt):
    """\
    Check that the low value of the filter is lower than the high.
    If there is to be no filter, return 'None'.
    If the condition is not met, a ValueError is raised.
    Otherwise, the values are returned as-is.
    """
    # Quick return if no filter.
    if not filt:
        return None
    try:
        return [range_check(f[0], f[1]) for f in filt]
    except ValueError as a:
        raise ValueError('Error in --filter: '+py23_str(a))


def keep_entry_range(entry, lows, highs, converter, regex):
    """\
    Boolean function to determine if an entry should be kept out
    based on if any numbers are in a given range.

    Returns True if it should be kept (i.e. falls in the range),
    and False if it is not in the range and should not be kept.
    """
    return any(low <= converter(num) <= high
               for num in regex.findall(entry)
               for low, high in zip(lows, highs))


def exclude_entry(entry, values, converter, regex):
    """\
    Boolean function to determine if an entry should be kept out
    based on if it contains a specific number.

    Returns True if it should be kept (i.e. does not match),
    and False if it matches and should not be kept.
    """
    return not any(converter(num) in values for num in regex.findall(entry))


def sort_and_print_entries(entries, args):
    """Sort the entries, applying the filters first if necessary."""

    # Extract the proper number type.
    is_float = args.number_type in ('float', 'real', 'f', 'r')
    signed = args.signed or args.number_type in ('real', 'r')
    alg = (ns.FLOAT * is_float |
           ns.SIGNED * signed |
           ns.NOEXP * (not args.exp) |
           ns.PATH * args.paths |
           ns.LOCALE * args.locale)

    # Pre-remove entries that don't pass the filtering criteria
    # Make sure we use the same searching algorithm for filtering
    # as for sorting.
    do_filter = args.filter is not None or args.reverse_filter is not None
    if do_filter or args.exclude:
        inp_options = (ns.FLOAT * is_float |
                       ns.SIGNED * signed |
                       ns.NOEXP * (not args.exp)
                       )
        regex = _regex_chooser[inp_options]
        if args.filter is not None:
            lows, highs = ([f[0] for f in args.filter],
                           [f[1] for f in args.filter])
            entries = [entry for entry in entries
                       if keep_entry_range(entry, lows, highs,
                                           float, regex)]
        if args.reverse_filter is not None:
            lows, highs = ([f[0] for f in args.reverse_filter],
                           [f[1] for f in args.reverse_filter])
            entries = [entry for entry in entries
                       if not keep_entry_range(entry, lows, highs,
                                               float, regex)]
        if args.exclude:
            exclude = set(args.exclude)
            entries = [entry for entry in entries
                       if exclude_entry(entry, exclude,
                                        float, regex)]

    # Print off the sorted results
    for entry in natsorted(entries, reverse=args.reverse, alg=alg):
        print(entry)


if __name__ == '__main__':
    try:
        main()
    except ValueError as a:
        sys.exit(py23_str(a))
    except KeyboardInterrupt:
        sys.exit(1)
