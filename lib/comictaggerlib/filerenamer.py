"""Functions for renaming files based on metadata"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import datetime

from . import utils
from .issuestring import IssueString


class FileRenamer:

    def __init__(self, metadata):
        self.setMetadata(metadata)
        self.setTemplate(
            "%series% v%volume% #%issue% (of %issuecount%) (%year%)")
        self.smart_cleanup = True
        self.issue_zero_padding = 3

    def setMetadata(self, metadata):
        self.metdata = metadata

    def setIssueZeroPadding(self, count):
        self.issue_zero_padding = count

    def setSmartCleanup(self, on):
        self.smart_cleanup = on

    def setTemplate(self, template):
        self.template = template

    def replaceToken(self, text, value, token):
        # helper func
        def isToken(word):
            return (word[0] == "%" and word[-1:] == "%")

        if value is not None:
            return text.replace(token, str(value))
        else:
            if self.smart_cleanup:
                # smart cleanup means we want to remove anything appended to token if it's empty
                # (e.g "#%issue%"  or "v%volume%")
                # (TODO: This could fail if there is more than one token appended together, I guess)
                text_list = text.split()

                # special case for issuecount, remove preceding non-token word,
                # as in "...(of %issuecount%)..."
                if token == '%issuecount%':
                    for idx, word in enumerate(text_list):
                        if token in word and not isToken(text_list[idx - 1]):
                            text_list[idx - 1] = ""

                text_list = [x for x in text_list if token not in x]
                return " ".join(text_list)
            else:
                return text.replace(token, "")

    def determineName(self, filename, ext=None):

        md = self.metdata
        new_name = self.template
        preferred_encoding = utils.get_actual_preferred_encoding()

        # print(u"{0}".format(md))

        new_name = self.replaceToken(new_name, md.series, '%series%')
        new_name = self.replaceToken(new_name, md.volume, '%volume%')

        if md.issue is not None:
            issue_str = "{0}".format(
                IssueString(md.issue).asString(pad=self.issue_zero_padding))
        else:
            issue_str = None
        new_name = self.replaceToken(new_name, issue_str, '%issue%')

        new_name = self.replaceToken(new_name, md.issueCount, '%issuecount%')
        new_name = self.replaceToken(new_name, md.year, '%year%')
        new_name = self.replaceToken(new_name, md.publisher, '%publisher%')
        new_name = self.replaceToken(new_name, md.title, '%title%')
        new_name = self.replaceToken(new_name, md.month, '%month%')
        month_name = None
        if md.month is not None:
            if (isinstance(md.month, str) and md.month.isdigit()) or isinstance(
                    md.month, int):
                if int(md.month) in range(1, 13):
                    dt = datetime.datetime(1970, int(md.month), 1, 0, 0)
                    #month_name = dt.strftime("%B".encode(preferred_encoding)).decode(preferred_encoding)
                    month_name = dt.strftime("%B")
        new_name = self.replaceToken(new_name, month_name, '%month_name%')

        new_name = self.replaceToken(new_name, md.genre, '%genre%')
        new_name = self.replaceToken(new_name, md.language, '%language_code%')
        new_name = self.replaceToken(
            new_name, md.criticalRating, '%criticalrating%')
        new_name = self.replaceToken(
            new_name, md.alternateSeries, '%alternateseries%')
        new_name = self.replaceToken(
            new_name, md.alternateNumber, '%alternatenumber%')
        new_name = self.replaceToken(
            new_name, md.alternateCount, '%alternatecount%')
        new_name = self.replaceToken(new_name, md.imprint, '%imprint%')
        new_name = self.replaceToken(new_name, md.format, '%format%')
        new_name = self.replaceToken(
            new_name, md.maturityRating, '%maturityrating%')
        new_name = self.replaceToken(new_name, md.storyArc, '%storyarc%')
        new_name = self.replaceToken(new_name, md.seriesGroup, '%seriesgroup%')
        new_name = self.replaceToken(new_name, md.scanInfo, '%scaninfo%')

        if self.smart_cleanup:

            # remove empty braces,brackets, parentheses
            new_name = re.sub("\(\s*[-:]*\s*\)", "", new_name)
            new_name = re.sub("\[\s*[-:]*\s*\]", "", new_name)
            new_name = re.sub("\{\s*[-:]*\s*\}", "", new_name)

            # remove duplicate spaces
            new_name = " ".join(new_name.split())

            # remove remove duplicate -, _,
            new_name = re.sub("[-_]{2,}\s+", "-- ", new_name)
            new_name = re.sub("(\s--)+", " --", new_name)
            new_name = re.sub("(\s-)+", " -", new_name)

            # remove dash or double dash at end of line
            new_name = re.sub("[-]{1,2}\s*$", "", new_name)

            # remove duplicate spaces (again!)
            new_name = " ".join(new_name.split())

        if ext is None:
            ext = os.path.splitext(filename)[1]

        new_name += ext

        # some tweaks to keep various filesystems happy
        new_name = new_name.replace("/", "-")
        new_name = new_name.replace(" :", " -")
        new_name = new_name.replace(": ", " - ")
        new_name = new_name.replace(":", "-")
        new_name = new_name.replace("?", "")

        return new_name
