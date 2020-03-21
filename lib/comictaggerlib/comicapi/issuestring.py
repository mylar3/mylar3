# coding=utf-8
"""Support for mixed digit/string type Issue field

Class for handling the odd permutations of an 'issue number' that the
comics industry throws at us.
  e.g.: "12", "12.1", "0", "-1", "5AU", "100-2"
"""

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

#import utils
#import math
#import re


class IssueString:

    def __init__(self, text):

        # break up the issue number string into 2 parts: the numeric and suffix string.
        # (assumes that the numeric portion is always first)

        self.num = None
        self.suffix = ""

        if text is None:
            return

        if isinstance(text, int):
            text = str(text)

        if len(text) == 0:
            return

        text = str(text)

        # skip the minus sign if it's first
        if text[0] == '-':
            start = 1
        else:
            start = 0

        # if it's still not numeric at start skip it
        if text[start].isdigit() or text[start] == ".":
            # walk through the string, look for split point (the first
            # non-numeric)
            decimal_count = 0
            for idx in range(start, len(text)):
                if text[idx] not in "0123456789.":
                    break
                # special case: also split on second "."
                if text[idx] == ".":
                    decimal_count += 1
                    if decimal_count > 1:
                        break
            else:
                idx = len(text)

            # move trailing numeric decimal to suffix
            # (only if there is other junk after )
            if text[idx - 1] == "." and len(text) != idx:
                idx = idx - 1

            # if there is no numeric after the minus, make the minus part of
            # the suffix
            if idx == 1 and start == 1:
                idx = 0

            part1 = text[0:idx]
            part2 = text[idx:len(text)]

            if part1 != "":
                self.num = float(part1)
            self.suffix = part2
        else:
            self.suffix = text

        # print "num: {0} suf: {1}".format(self.num, self.suffix)

    def asString(self, pad=0):
        # return the float, left side zero-padded, with suffix attached
        if self.num is None:
            return self.suffix

        negative = self.num < 0

        num_f = abs(self.num)

        num_int = int(num_f)
        num_s = str(num_int)
        if float(num_int) != num_f:
            num_s = str(num_f)

        num_s += self.suffix

        # create padding
        padding = ""
        l = len(str(num_int))
        if l < pad:
            padding = "0" * (pad - l)

        num_s = padding + num_s
        if negative:
            num_s = "-" + num_s

        return num_s

    def asFloat(self):
        # return the float, with no suffix
        if self.suffix == "½":
            if self.num is not None:
                return self.num + .5
            else:
                return .5
        return self.num

    def asInt(self):
        # return the int version of the float
        if self.num is None:
            return None
        return int(self.num)
