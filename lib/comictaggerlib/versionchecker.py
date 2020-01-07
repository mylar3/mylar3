"""Version checker"""

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
import platform
import urllib.request, urllib.error, urllib.parse
#import os
#import urllib

try:
    from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
    from PyQt5.QtCore import QUrl, pyqtSignal, QObject, QByteArray
except ImportError:
    # No Qt, so define a few dummy QObjects to help us compile
    class QObject():

        def __init__(self, *args):
            pass

    class pyqtSignal():

        def __init__(self, *args):
            pass

        def emit(a, b, c):
            pass

from . import ctversion


class VersionChecker(QObject):

    def getRequestUrl(self, uuid, use_stats):

        base_url = "http://comictagger1.appspot.com/latest"
        args = ""

        if use_stats:
            if platform.system() == "Windows":
                plat = "win"
            elif platform.system() == "Linux":
                plat = "lin"
            elif platform.system() == "Darwin":
                plat = "mac"
            else:
                plat = "other"
            args = "?uuid={0}&platform={1}&version={2}".format(
                uuid, plat, ctversion.version)
            if not getattr(sys, 'frozen', None):
                args += "&src=T"

        return base_url + args

    def getLatestVersion(self, uuid, use_stats=True):

        try:
            resp = urllib.request.urlopen(self.getRequestUrl(uuid, use_stats))
            new_version = resp.read()
        except Exception as e:
            return None

        if new_version is None or new_version == "":
            return None
        return new_version.strip()

    versionRequestComplete = pyqtSignal(str)

    def asyncGetLatestVersion(self, uuid, use_stats):

        url = self.getRequestUrl(uuid, use_stats)

        self.nam = QNetworkAccessManager()
        self.nam.finished.connect(self.asyncGetLatestVersionComplete)
        self.nam.get(QNetworkRequest(QUrl(str(url))))

    def asyncGetLatestVersionComplete(self, reply):
        if (reply.error() != QNetworkReply.NoError):
            return

        # read in the response
        new_version = str(reply.readAll())

        if new_version is None or new_version == "":
            return

        self.versionRequestComplete.emit(new_version.strip())
