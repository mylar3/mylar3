"""A class to manage modifying metadata specifically for CBL/CBI"""

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

#import os

#import utils


class CBLTransformer:

    def __init__(self, metadata, settings):
        self.metadata = metadata
        self.settings = settings

    def apply(self):
        # helper funcs
        def append_to_tags_if_unique(item):
            if item.lower() not in (tag.lower() for tag in self.metadata.tags):
                self.metadata.tags.append(item)

        def add_string_list_to_tags(str_list):
            if str_list is not None and str_list != "":
                items = [s.strip() for s in str_list.split(',')]
                for item in items:
                    append_to_tags_if_unique(item)

        if self.settings.assume_lone_credit_is_primary:

            # helper
            def setLonePrimary(role_list):
                lone_credit = None
                count = 0
                for c in self.metadata.credits:
                    if c['role'].lower() in role_list:
                        count += 1
                        lone_credit = c
                    if count > 1:
                        lone_credit = None
                        break
                if lone_credit is not None:
                    lone_credit['primary'] = True
                return lone_credit, count

            # need to loop three times, once for 'writer', 'artist', and then
            # 'penciler' if no artist
            setLonePrimary(['writer'])
            c, count = setLonePrimary(['artist'])
            if c is None and count == 0:
                c, count = setLonePrimary(['penciler', 'penciller'])
                if c is not None:
                    c['primary'] = False
                    self.metadata.addCredit(c['person'], 'Artist', True)

        if self.settings.copy_characters_to_tags:
            add_string_list_to_tags(self.metadata.characters)

        if self.settings.copy_teams_to_tags:
            add_string_list_to_tags(self.metadata.teams)

        if self.settings.copy_locations_to_tags:
            add_string_list_to_tags(self.metadata.locations)

        if self.settings.copy_storyarcs_to_tags:
            add_string_list_to_tags(self.metadata.storyArc)

        if self.settings.copy_notes_to_comments:
            if self.metadata.notes is not None:
                if self.metadata.comments is None:
                    self.metadata.comments = ""
                else:
                    self.metadata.comments += "\n\n"
                if self.metadata.notes not in self.metadata.comments:
                    self.metadata.comments += self.metadata.notes

        if self.settings.copy_weblink_to_comments:
            if self.metadata.webLink is not None:
                if self.metadata.comments is None:
                    self.metadata.comments = ""
                else:
                    self.metadata.comments += "\n\n"
                if self.metadata.webLink not in self.metadata.comments:
                    self.metadata.comments += self.metadata.webLink

        return self.metadata
