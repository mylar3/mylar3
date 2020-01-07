"""A PyQT4 dialog to select specific issue from list"""

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

#import sys
#import os
#import re

from PyQt5 import QtCore, QtGui, QtWidgets, uic
#from PyQt5.QtCore import QUrl, pyqtSignal, QByteArray
#from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from .comicvinetalker import ComicVineTalker, ComicVineTalkerException
from .settings import ComicTaggerSettings
from .issuestring import IssueString
from .coverimagewidget import CoverImageWidget
from comictaggerlib.ui.qtutils import reduceWidgetFontSize
#from imagefetcher import ImageFetcher
#import utils


class IssueNumberTableWidgetItem(QtWidgets.QTableWidgetItem):

    def __lt__(self, other):
        selfStr = self.data(QtCore.Qt.DisplayRole)
        otherStr = other.data(QtCore.Qt.DisplayRole)
        return (IssueString(selfStr).asFloat() <
                IssueString(otherStr).asFloat())


class IssueSelectionWindow(QtWidgets.QDialog):

    volume_id = 0

    def __init__(self, parent, settings, series_id, issue_number):
        super(IssueSelectionWindow, self).__init__(parent)

        uic.loadUi(
            ComicTaggerSettings.getUIFile('issueselectionwindow.ui'), self)

        self.coverWidget = CoverImageWidget(
            self.coverImageContainer, CoverImageWidget.AltCoverMode)
        gridlayout = QtWidgets.QGridLayout(self.coverImageContainer)
        gridlayout.addWidget(self.coverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        reduceWidgetFontSize(self.twList)
        reduceWidgetFontSize(self.teDescription, 1)

        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowSystemMenuHint |
                            QtCore.Qt.WindowMaximizeButtonHint)

        self.series_id = series_id
        self.settings = settings
        self.url_fetch_thread = None

        if issue_number is None or issue_number == "":
            self.issue_number = 1
        else:
            self.issue_number = issue_number

        self.initial_id = None
        self.performQuery()

        self.twList.resizeColumnsToContents()
        self.twList.currentItemChanged.connect(self.currentItemChanged)
        self.twList.cellDoubleClicked.connect(self.cellDoubleClicked)

        # now that the list has been sorted, find the initial record, and
        # select it
        if self.initial_id is None:
            self.twList.selectRow(0)
        else:
            for r in range(0, self.twList.rowCount()):
                issue_id = self.twList.item(r, 0).data(QtCore.Qt.UserRole)
                if (issue_id == self.initial_id):
                    self.twList.selectRow(r)
                    break

    def performQuery(self):

        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.WaitCursor))

        try:
            comicVine = ComicVineTalker()
            volume_data = comicVine.fetchVolumeData(self.series_id)
            self.issue_list = comicVine.fetchIssuesByVolume(self.series_id)
        except ComicVineTalkerException as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            if e.code == ComicVineTalkerException.RateLimit:
                QtWidgets.QMessageBox.critical(
                    self,
                    self.tr("Comic Vine Error"),
                    ComicVineTalker.getRateLimitMessage())
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    self.tr("Network Issue"),
                    self.tr("Could not connect to Comic Vine to list issues!"))
            return

        while self.twList.rowCount() > 0:
            self.twList.removeRow(0)

        self.twList.setSortingEnabled(False)

        row = 0
        for record in self.issue_list:
            self.twList.insertRow(row)

            item_text = record['issue_number']
            item = IssueNumberTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ToolTipRole, item_text)
            item.setData(QtCore.Qt.UserRole, record['id'])
            item.setData(QtCore.Qt.DisplayRole, item_text)
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 0, item)

            item_text = record['cover_date']
            if item_text is None:
                item_text = ""
            # remove the day of "YYYY-MM-DD"
            parts = item_text.split("-")
            if len(parts) > 1:
                item_text = parts[0] + "-" + parts[1]

            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 1, item)

            item_text = record['name']
            if item_text is None:
                item_text = ""
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 2, item)

            if IssueString(
                    record['issue_number']).asString().lower() == IssueString(
                    self.issue_number).asString().lower():
                self.initial_id = record['id']

            row += 1

        self.twList.setSortingEnabled(True)
        self.twList.sortItems(0, QtCore.Qt.AscendingOrder)

        QtWidgets.QApplication.restoreOverrideCursor()

    def cellDoubleClicked(self, r, c):
        self.accept()

    def currentItemChanged(self, curr, prev):

        if curr is None:
            return
        if prev is not None and prev.row() == curr.row():
            return

        self.issue_id = self.twList.item(curr.row(), 0).data(QtCore.Qt.UserRole)

        # list selection was changed, update the the issue cover
        for record in self.issue_list:
            if record['id'] == self.issue_id:
                self.issue_number = record['issue_number']
                self.coverWidget.setIssueID(int(self.issue_id))
                if record['description'] is None:
                    self.teDescription.setText("")
                else:
                    self.teDescription.setText(record['description'])

                break
