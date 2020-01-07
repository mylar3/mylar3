#!/usr/bin/python

"""ComicTagger CLI functions"""

# Copyright 2013 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import os
from pprint import pprint
import json
#import signal
#import traceback
#import time
#import platform
#import locale
#import codecs

filename_encoding = sys.getfilesystemencoding()

from .settings import ComicTaggerSettings
from .options import Options
from .comicarchive import ComicArchive, MetaDataStyle
from .issueidentifier import IssueIdentifier
from .genericmetadata import GenericMetadata
from .comicvinetalker import ComicVineTalker, ComicVineTalkerException
from .filerenamer import FileRenamer
from .cbltransformer import CBLTransformer
from . import utils


class MultipleMatch():

    def __init__(self, filename, match_list):
        self.filename = filename
        self.matches = match_list


class OnlineMatchResults():

    def __init__(self):
        self.goodMatches = []
        self.noMatches = []
        self.multipleMatches = []
        self.lowConfidenceMatches = []
        self.writeFailures = []
        self.fetchDataFailures = []

#-----------------------------


def actual_issue_data_fetch(match, settings, opts):

    # now get the particular issue data
    try:
        comicVine = ComicVineTalker()
        comicVine.wait_for_rate_limit = opts.wait_and_retry_on_rate_limit
        cv_md = comicVine.fetchIssueData(
            match['volume_id'], match['issue_number'], settings)
    except ComicVineTalkerException:
        print("Network error while getting issue details.  Save aborted", file=sys.stderr)
        return None

    if settings.apply_cbl_transform_on_cv_import:
        cv_md = CBLTransformer(cv_md, settings).apply()

    return cv_md


def actual_metadata_save(ca, opts, md):

    if not opts.dryrun:
        # write out the new data
        if not ca.writeMetadata(md, opts.data_style):
            print("The tag save seemed to fail!", file=sys.stderr)
            return False
        else:
            print("Save complete.", file=sys.stderr)
    else:
        if opts.terse:
            print("dry-run option was set, so nothing was written", file=sys.stderr)
        else:
            print("dry-run option was set, so nothing was written, but here is the final set of tags:", file=sys.stderr)
            print(("{0}".format(md)))
    return True


def display_match_set_for_choice(label, match_set, opts, settings):
    print(("{0} -- {1}:".format(match_set.filename, label)))

    # sort match list by year
    match_set.matches.sort(key=lambda k: k['year'])

    for (counter, m) in enumerate(match_set.matches):
        counter += 1
        print((
            "    {0}. {1} #{2} [{3}] ({4}/{5}) - {6}".format(
                counter,
                m['series'],
                m['issue_number'],
                m['publisher'],
                m['month'],
                m['year'],
                m['issue_title'])))
    if opts.interactive:
        while True:
            i = input("Choose a match #, or 's' to skip: ")
            if (i.isdigit() and int(i) in range(
                    1, len(match_set.matches) + 1)) or i == 's':
                break
        if i != 's':
            i = int(i) - 1
            # save the data!
            # we know at this point, that the file is all good to go
            ca = ComicArchive(
                match_set.filename,
                settings.rar_exe_path,
                ComicTaggerSettings.getGraphic('nocover.png'))
            md = create_local_metadata(
                opts, ca, ca.hasMetadata(opts.data_style))
            cv_md = actual_issue_data_fetch(
                match_set.matches[int(i)], settings, opts)
            md.overlay(cv_md)
            actual_metadata_save(ca, opts, md)


def post_process_matches(match_results, opts, settings):
    # now go through the match results
    if opts.show_save_summary:
        if len(match_results.goodMatches) > 0:
            print("\nSuccessful matches:\n------------------")
            for f in match_results.goodMatches:
                print(f)

        if len(match_results.noMatches) > 0:
            print("\nNo matches:\n------------------")
            for f in match_results.noMatches:
                print(f)

        if len(match_results.writeFailures) > 0:
            print("\nFile Write Failures:\n------------------")
            for f in match_results.writeFailures:
                print(f)

        if len(match_results.fetchDataFailures) > 0:
            print("\nNetwork Data Fetch Failures:\n------------------")
            for f in match_results.fetchDataFailures:
                print(f)

    if not opts.show_save_summary and not opts.interactive:
        # just quit if we're not interactive or showing the summary
        return

    if len(match_results.multipleMatches) > 0:
        print(
            "\nArchives with multiple high-confidence matches:\n------------------")
        for match_set in match_results.multipleMatches:
            display_match_set_for_choice(
                "Multiple high-confidence matches", match_set, opts, settings)

    if len(match_results.lowConfidenceMatches) > 0:
        print("\nArchives with low-confidence matches:\n------------------")
        for match_set in match_results.lowConfidenceMatches:
            if len(match_set.matches) == 1:
                label = "Single low-confidence match"
            else:
                label = "Multiple low-confidence matches"

            display_match_set_for_choice(label, match_set, opts, settings)


def cli_mode(opts, settings):
    if len(opts.file_list) < 1:
        print("You must specify at least one filename.  Use the -h option for more info", file=sys.stderr)
        return

    match_results = OnlineMatchResults()

    for f in opts.file_list:
        if isinstance(f, str):
            pass
        process_file_cli(f, opts, settings, match_results)
        sys.stdout.flush()

    post_process_matches(match_results, opts, settings)


def create_local_metadata(opts, ca, has_desired_tags):

    md = GenericMetadata()
    md.setDefaultPageList(ca.getNumberOfPages())

    if has_desired_tags:
        md = ca.readMetadata(opts.data_style)

    # now, overlay the parsed filename info
    if opts.parse_filename:
        md.overlay(ca.metadataFromFilename())

    # finally, use explicit stuff
    if opts.metadata is not None:
        md.overlay(opts.metadata)

    return md


def process_file_cli(filename, opts, settings, match_results):

    batch_mode = len(opts.file_list) > 1

    ca = ComicArchive(
        filename,
        settings.rar_exe_path,
        ComicTaggerSettings.getGraphic('nocover.png'))

    if not os.path.lexists(filename):
        print("Cannot find " + filename, file=sys.stderr)
        return

    if not ca.seemsToBeAComicArchive():
        print("Sorry, but " + \
            filename + "  is not a comic archive!", file=sys.stderr)
        return

    # if not ca.isWritableForStyle(opts.data_style) and (opts.delete_tags or
    # opts.save_tags or opts.rename_file):
    if not ca.isWritable() and (
            opts.delete_tags or opts.copy_tags or opts.save_tags or opts.rename_file):
        print("This archive is not writable for that tag type", file=sys.stderr)
        return

    has = [False, False, False]
    if ca.hasCIX():
        has[MetaDataStyle.CIX] = True
    if ca.hasCBI():
        has[MetaDataStyle.CBI] = True
    if ca.hasCoMet():
        has[MetaDataStyle.COMET] = True

    if opts.print_tags:

        if opts.data_style is None:
            page_count = ca.getNumberOfPages()

            brief = ""

            if batch_mode:
                brief = "{0}: ".format(filename)

            if ca.isZip():
                brief += "ZIP archive    "
            elif ca.isRar():
                brief += "RAR archive    "
            elif ca.isFolder():
                brief += "Folder archive "

            brief += "({0: >3} pages)".format(page_count)
            brief += "  tags:[ "

            if not (has[MetaDataStyle.CBI] or has[
                    MetaDataStyle.CIX] or has[MetaDataStyle.COMET]):
                brief += "none "
            else:
                if has[MetaDataStyle.CBI]:
                    brief += "CBL "
                if has[MetaDataStyle.CIX]:
                    brief += "CR "
                if has[MetaDataStyle.COMET]:
                    brief += "CoMet "
            brief += "]"

            print(brief)

        if opts.terse:
            return

        print()

        if opts.data_style is None or opts.data_style == MetaDataStyle.CIX:
            if has[MetaDataStyle.CIX]:
                print("--------- ComicRack tags ---------")
                if opts.raw:
                    print((
                        "{0}".format(
                            str(
                                ca.readRawCIX(),
                                errors='ignore'))))
                else:
                    print(("{0}".format(ca.readCIX())))

        if opts.data_style is None or opts.data_style == MetaDataStyle.CBI:
            if has[MetaDataStyle.CBI]:
                print("------- ComicBookLover tags -------")
                if opts.raw:
                    pprint(json.loads(ca.readRawCBI()))
                else:
                    print(("{0}".format(ca.readCBI())))

        if opts.data_style is None or opts.data_style == MetaDataStyle.COMET:
            if has[MetaDataStyle.COMET]:
                print("----------- CoMet tags -----------")
                if opts.raw:
                    print(("{0}".format(ca.readRawCoMet())))
                else:
                    print(("{0}".format(ca.readCoMet())))

    elif opts.delete_tags:
        style_name = MetaDataStyle.name[opts.data_style]
        if has[opts.data_style]:
            if not opts.dryrun:
                if not ca.removeMetadata(opts.data_style):
                    print(("{0}: Tag removal seemed to fail!".format(filename)))
                else:
                    print((
                        "{0}: Removed {1} tags.".format(filename, style_name)))
            else:
                print((
                    "{0}: dry-run. {1} tags not removed".format(filename, style_name)))
        else:
            print(("{0}: This archive doesn't have {1} tags to remove.".format(
                filename, style_name)))

    elif opts.copy_tags:
        dst_style_name = MetaDataStyle.name[opts.data_style]
        if opts.no_overwrite and has[opts.data_style]:
            print(("{0}: Already has {1} tags. Not overwriting.".format(
                filename, dst_style_name)))
            return
        if opts.copy_source == opts.data_style:
            print((
                "{0}: Destination and source are same: {1}. Nothing to do.".format(
                    filename,
                    dst_style_name)))
            return

        src_style_name = MetaDataStyle.name[opts.copy_source]
        if has[opts.copy_source]:
            if not opts.dryrun:
                md = ca.readMetadata(opts.copy_source)

                if settings.apply_cbl_transform_on_bulk_operation and opts.data_style == MetaDataStyle.CBI:
                    md = CBLTransformer(md, settings).apply()

                if not ca.writeMetadata(md, opts.data_style):
                    print(("{0}: Tag copy seemed to fail!".format(filename)))
                else:
                    print(("{0}: Copied {1} tags to {2} .".format(
                        filename, src_style_name, dst_style_name)))
            else:
                print((
                    "{0}: dry-run.  {1} tags not copied".format(filename, src_style_name)))
        else:
            print(("{0}: This archive doesn't have {1} tags to copy.".format(
                filename, src_style_name)))

    elif opts.save_tags:

        if opts.no_overwrite and has[opts.data_style]:
            print(("{0}: Already has {1} tags. Not overwriting.".format(
                filename, MetaDataStyle.name[opts.data_style])))
            return

        if batch_mode:
            print(("Processing {0}...".format(filename)))

        md = create_local_metadata(opts, ca, has[opts.data_style])
        if md.issue is None or md.issue == "":
            if opts.assume_issue_is_one_if_not_set:
                md.issue = "1"

        # now, search online
        if opts.search_online:
            if opts.issue_id is not None:
                # we were given the actual ID to search with
                try:
                    comicVine = ComicVineTalker()
                    comicVine.wait_for_rate_limit = opts.wait_and_retry_on_rate_limit
                    cv_md = comicVine.fetchIssueDataByIssueID(
                        opts.issue_id, settings)
                except ComicVineTalkerException:
                    print("Network error while getting issue details.  Save aborted", file=sys.stderr)
                    match_results.fetchDataFailures.append(filename)
                    return

                if cv_md is None:
                    print("No match for ID {0} was found.".format(
                        opts.issue_id), file=sys.stderr)
                    match_results.noMatches.append(filename)
                    return

                if settings.apply_cbl_transform_on_cv_import:
                    cv_md = CBLTransformer(cv_md, settings).apply()
            else:
                ii = IssueIdentifier(ca, settings)

                if md is None or md.isEmpty:
                    print("No metadata given to search online with!", file=sys.stderr)
                    match_results.noMatches.append(filename)
                    return

                def myoutput(text):
                    if opts.verbose:
                        IssueIdentifier.defaultWriteOutput(text)

                # use our overlayed MD struct to search
                ii.setAdditionalMetadata(md)
                ii.onlyUseAdditionalMetaData = True
                ii.waitAndRetryOnRateLimit = opts.wait_and_retry_on_rate_limit
                ii.setOutputFunction(myoutput)
                ii.cover_page_index = md.getCoverPageIndexList()[0]
                matches = ii.search()

                result = ii.search_result

                found_match = False
                choices = False
                low_confidence = False

                if result == ii.ResultNoMatches:
                    pass
                elif result == ii.ResultFoundMatchButBadCoverScore:
                    low_confidence = True
                    found_match = True
                elif result == ii.ResultFoundMatchButNotFirstPage:
                    found_match = True
                elif result == ii.ResultMultipleMatchesWithBadImageScores:
                    low_confidence = True
                    choices = True
                elif result == ii.ResultOneGoodMatch:
                    found_match = True
                elif result == ii.ResultMultipleGoodMatches:
                    choices = True

                if choices:
                    if low_confidence:
                        print("Online search: Multiple low confidence matches.  Save aborted", file=sys.stderr)
                        match_results.lowConfidenceMatches.append(
                            MultipleMatch(filename, matches))
                        return
                    else:
                        print("Online search: Multiple good matches.  Save aborted", file=sys.stderr)
                        match_results.multipleMatches.append(
                            MultipleMatch(filename, matches))
                        return
                if low_confidence and opts.abortOnLowConfidence:
                    print("Online search: Low confidence match.  Save aborted", file=sys.stderr)
                    match_results.lowConfidenceMatches.append(
                        MultipleMatch(filename, matches))
                    return
                if not found_match:
                    print("Online search: No match found.  Save aborted", file=sys.stderr)
                    match_results.noMatches.append(filename)
                    return

                # we got here, so we have a single match

                # now get the particular issue data
                cv_md = actual_issue_data_fetch(matches[0], settings, opts)
                if cv_md is None:
                    match_results.fetchDataFailures.append(filename)
                    return

            md.overlay(cv_md)

        # ok, done building our metadata. time to save
        if not actual_metadata_save(ca, opts, md):
            match_results.writeFailures.append(filename)
        else:
            match_results.goodMatches.append(filename)

    elif opts.rename_file:

        msg_hdr = ""
        if batch_mode:
            msg_hdr = "{0}: ".format(filename)

        if opts.data_style is not None:
            use_tags = has[opts.data_style]
        else:
            use_tags = False

        md = create_local_metadata(opts, ca, use_tags)

        if md.series is None:
            print(msg_hdr + "Can't rename without series name", file=sys.stderr)
            return

        new_ext = None  # default
        if settings.rename_extension_based_on_archive:
            if ca.isZip():
                new_ext = ".cbz"
            elif ca.isRar():
                new_ext = ".cbr"

        renamer = FileRenamer(md)
        renamer.setTemplate(settings.rename_template)
        renamer.setIssueZeroPadding(settings.rename_issue_number_padding)
        renamer.setSmartCleanup(settings.rename_use_smart_string_cleanup)

        new_name = renamer.determineName(filename, ext=new_ext)

        if new_name == os.path.basename(filename):
            print(msg_hdr + "Filename is already good!", file=sys.stderr)
            return

        folder = os.path.dirname(os.path.abspath(filename))
        new_abs_path = utils.unique_file(os.path.join(folder, new_name))

        suffix = ""
        if not opts.dryrun:
            # rename the file
            os.rename(filename, new_abs_path)
        else:
            suffix = " (dry-run, no change)"

        print((
            "renamed '{0}' -> '{1}' {2}".format(os.path.basename(filename), new_name, suffix)))

    elif opts.export_to_zip:
        msg_hdr = ""
        if batch_mode:
            msg_hdr = "{0}: ".format(filename)

        if not ca.isRar():
            print(msg_hdr + "Archive is not a RAR.", file=sys.stderr)
            return

        rar_file = os.path.abspath(os.path.abspath(filename))
        new_file = os.path.splitext(rar_file)[0] + ".cbz"

        if opts.abort_export_on_conflict and os.path.lexists(new_file):
            print(msg_hdr + "{0} already exists in the that folder.".format(os.path.split(new_file)[1]))
            return

        new_file = utils.unique_file(os.path.join(new_file))

        delete_success = False
        export_success = False
        if not opts.dryrun:
            if ca.exportAsZip(new_file):
                export_success = True
                if opts.delete_rar_after_export:
                    try:
                        os.unlink(rar_file)
                    except:
                        print(msg_hdr + \
                            "Error deleting original RAR after export", file=sys.stderr)
                        delete_success = False
                    else:
                        delete_success = True
            else:
                # last export failed, so remove the zip, if it exists
                if os.path.lexists(new_file):
                    os.remove(new_file)
        else:
            msg = msg_hdr + \
                "Dry-run:  Would try to create {0}".format(
                    os.path.split(new_file)[1])
            if opts.delete_rar_after_export:
                msg += " and delete orginal."
            print(msg)
            return

        msg = msg_hdr
        if export_success:
            msg += "Archive exported successfully to: {0}".format(
                os.path.split(new_file)[1])
            if opts.delete_rar_after_export and delete_success:
                msg += " (Original deleted) "
        else:
            msg += "Archive failed to export!"

        print(msg)
