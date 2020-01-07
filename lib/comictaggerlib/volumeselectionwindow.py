"""A PyQT4 dialog to select specific series/volume from list"""

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
#import time
#import os

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QUrl, pyqtSignal
#from PyQt4.QtCore import QObject
#from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest

from .comicvinetalker import ComicVineTalker, ComicVineTalkerException
from .issueselectionwindow import IssueSelectionWindow
from .issueidentifier import IssueIdentifier
from .genericmetadata import GenericMetadata
from .progresswindow import IDProgressWindow
from .settings import ComicTaggerSettings
from .matchselectionwindow import MatchSelectionWindow
from .coverimagewidget import CoverImageWidget
from comictaggerlib.ui.qtutils import reduceWidgetFontSize, centerWindowOnParent
#from imagefetcher import ImageFetcher
#import utils


class SearchThread(QtCore.QThread):

    searchComplete = pyqtSignal()
    progressUpdate = pyqtSignal(int, int)

    def __init__(self, series_name, refresh):
        QtCore.QThread.__init__(self)
        self.series_name = series_name
        self.refresh = refresh
        self.error_code = None

    def run(self):
        comicVine = ComicVineTalker()
        try:
            self.cv_error = False
            self.cv_search_results = comicVine.searchForSeries(
                self.series_name,
                callback=self.prog_callback,
                refresh_cache=self.refresh)
        except ComicVineTalkerException as e:
            self.cv_search_results = []
            self.cv_error = True
            self.error_code = e.code

        finally:
            self.searchComplete.emit()

    def prog_callback(self, current, total):
        self.progressUpdate.emit(current, total)


class IdentifyThread(QtCore.QThread):

    identifyComplete = pyqtSignal()
    identifyLogMsg = pyqtSignal(str)
    identifyProgress = pyqtSignal(int, int)

    def __init__(self, identifier):
        QtCore.QThread.__init__(self)
        self.identifier = identifier
        self.identifier.setOutputFunction(self.logOutput)
        self.identifier.setProgressCallback(self.progressCallback)

    def logOutput(self, text):
        self.identifyLogMsg.emit(text)

    def progressCallback(self, cur, total):
        self.identifyProgress.emit(cur, total)

    def run(self):
        matches = self.identifier.search()
        self.identifyComplete.emit()


class VolumeSelectionWindow(QtWidgets.QDialog):

    def __init__(self, parent, series_name, issue_number, year, issue_count,
                 cover_index_list, comic_archive, settings, autoselect=False):
        super(VolumeSelectionWindow, self).__init__(parent)

        uic.loadUi(
            ComicTaggerSettings.getUIFile('volumeselectionwindow.ui'), self)

        self.imageWidget = CoverImageWidget(
            self.imageContainer, CoverImageWidget.URLMode)
        gridlayout = QtWidgets.QGridLayout(self.imageContainer)
        gridlayout.addWidget(self.imageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        reduceWidgetFontSize(self.teDetails, 1)
        reduceWidgetFontSize(self.twList)

        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowSystemMenuHint |
                            QtCore.Qt.WindowMaximizeButtonHint)

        self.settings = settings
        self.parent = parent
        self.series_name = series_name
        self.issue_number = issue_number
        self.year = year
        self.issue_count = issue_count
        self.volume_id = 0
        self.comic_archive = comic_archive
        self.immediate_autoselect = autoselect
        self.cover_index_list = cover_index_list
        self.cv_search_results = None

        self.twList.resizeColumnsToContents()
        self.twList.currentItemChanged.connect(self.currentItemChanged)
        self.twList.cellDoubleClicked.connect(self.cellDoubleClicked)
        self.btnRequery.clicked.connect(self.requery)
        self.btnIssues.clicked.connect(self.showIssues)
        self.btnAutoSelect.clicked.connect(self.autoSelect)

        self.updateButtons()
        self.performQuery()
        self.twList.selectRow(0)

    def updateButtons(self):
        if self.cv_search_results is not None and len(
                self.cv_search_results) > 0:
            enabled = True
        else:
            enabled = False

        self.btnRequery.setEnabled(enabled)
        self.btnIssues.setEnabled(enabled)
        self.btnAutoSelect.setEnabled(enabled)
        self.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(enabled)

    def requery(self,):
        self.performQuery(refresh=True)
        self.twList.selectRow(0)

    def autoSelect(self):

        if self.comic_archive is None:
            QtWidgets.QMessageBox.information(
                self, "Auto-Select", "You need to load a comic first!")
            return

        if self.issue_number is None or self.issue_number == "":
            QtWidgets.QMessageBox.information(
                self,
                "Auto-Select",
                "Can't auto-select without an issue number (yet!)")
            return

        self.iddialog = IDProgressWindow(self)
        self.iddialog.setModal(True)
        self.iddialog.rejected.connect(self.identifyCancel)
        self.iddialog.show()

        self.ii = IssueIdentifier(self.comic_archive, self.settings)

        md = GenericMetadata()
        md.series = self.series_name
        md.issue = self.issue_number
        md.year = self.year
        md.issueCount = self.issue_count

        self.ii.setAdditionalMetadata(md)
        self.ii.onlyUseAdditionalMetaData = True

        self.ii.cover_page_index = int(self.cover_index_list[0])

        self.id_thread = IdentifyThread(self.ii)
        self.id_thread.identifyComplete.connect(self.identifyComplete)
        self.id_thread.identifyLogMsg.connect(self.logIDOutput)
        self.id_thread.identifyProgress.connect(self.identifyProgress)

        self.id_thread.start()

        self.iddialog.exec_()

    def logIDOutput(self, text):
        print(str(text), end=' ')
        self.iddialog.textEdit.ensureCursorVisible()
        self.iddialog.textEdit.insertPlainText(text)

    def identifyProgress(self, cur, total):
        self.iddialog.progressBar.setMaximum(total)
        self.iddialog.progressBar.setValue(cur)

    def identifyCancel(self):
        self.ii.cancel = True

    def identifyComplete(self):

        matches = self.ii.match_list
        result = self.ii.search_result
        match_index = 0

        found_match = None
        choices = False
        if result == self.ii.ResultNoMatches:
            QtWidgets.QMessageBox.information(
                self, "Auto-Select Result", " No matches found :-(")
        elif result == self.ii.ResultFoundMatchButBadCoverScore:
            QtWidgets.QMessageBox.information(
                self,
                "Auto-Select Result",
                " Found a match, but cover doesn't seem the same.  Verify before commiting!")
            found_match = matches[0]
        elif result == self.ii.ResultFoundMatchButNotFirstPage:
            QtWidgets.QMessageBox.information(
                self,
                "Auto-Select Result",
                " Found a match, but not with the first page of the archive.")
            found_match = matches[0]
        elif result == self.ii.ResultMultipleMatchesWithBadImageScores:
            QtWidgets.QMessageBox.information(
                self,
                "Auto-Select Result",
                " Found some possibilities, but no confidence. Proceed manually.")
            choices = True
        elif result == self.ii.ResultOneGoodMatch:
            found_match = matches[0]
        elif result == self.ii.ResultMultipleGoodMatches:
            QtWidgets.QMessageBox.information(
                self,
                "Auto-Select Result",
                " Found multiple likely matches.  Please select.")
            choices = True

        if choices:
            selector = MatchSelectionWindow(self, matches, self.comic_archive)
            selector.setModal(True)
            selector.exec_()
            if selector.result():
                # we should now have a list index
                found_match = selector.currentMatch()

        if found_match is not None:
            self.iddialog.accept()

            self.volume_id = found_match['volume_id']
            self.issue_number = found_match['issue_number']
            self.selectByID()
            self.showIssues()

    def showIssues(self):
        selector = IssueSelectionWindow(
            self, self.settings, self.volume_id, self.issue_number)
        title = ""
        for record in self.cv_search_results:
            if record['id'] == self.volume_id:
                title = record['name']
                title += " (" + str(record['start_year']) + ")"
                title += " - "
                break

        selector.setWindowTitle(title + "Select Issue")
        selector.setModal(True)
        selector.exec_()
        if selector.result():
            # we should now have a volume ID
            self.issue_number = selector.issue_number
            self.accept()
        return

    def selectByID(self):
        for r in range(0, self.twList.rowCount()):
            volume_id = self.twList.item(r, 0).data(QtCore.Qt.UserRole)
            if (volume_id == self.volume_id):
                self.twList.selectRow(r)
                break

    def performQuery(self, refresh=False):

        self.progdialog = QtWidgets.QProgressDialog(
            "Searching Online", "Cancel", 0, 100, self)
        self.progdialog.setWindowTitle("Online Search")
        self.progdialog.canceled.connect(self.searchCanceled)
        self.progdialog.setModal(True)
        self.progdialog.setMinimumDuration(300)
        QtCore.QCoreApplication.processEvents()        
        self.search_thread = SearchThread(self.series_name, refresh)
        self.search_thread.searchComplete.connect(self.searchComplete)
        self.search_thread.progressUpdate.connect(self.searchProgressUpdate)
        self.search_thread.start()
        self.progdialog.exec_()

    def searchCanceled(self):
        print("query cancelled")
        self.search_thread.searchComplete.disconnect(self.searchComplete)
        self.search_thread.progressUpdate.disconnect(self.searchProgressUpdate)
        self.progdialog.canceled.disconnect(self.searchCanceled)
        self.progdialog.reject()
        QtCore.QTimer.singleShot(200, self.closeMe)

    def closeMe(self):
        print("closeme")
        self.reject()

    def searchProgressUpdate(self, current, total):
        self.progdialog.setMaximum(total)
        self.progdialog.setValue(current+1)

    def searchComplete(self):
        self.progdialog.accept()
        del self.progdialog
        QtCore.QCoreApplication.processEvents()
        if self.search_thread.cv_error:
            if self.search_thread.error_code == ComicVineTalkerException.RateLimit:
                QtWidgets.QMessageBox.critical(
                    self,
                    self.tr("Comic Vine Error"),
                    ComicVineTalker.getRateLimitMessage())
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    self.tr("Network Issue"),
                    self.tr("Could not connect to Comic Vine to search for series!"))
            return

        self.cv_search_results = self.search_thread.cv_search_results
        self.updateButtons()

        self.twList.setSortingEnabled(False)

        while self.twList.rowCount() > 0:
            self.twList.removeRow(0)

        row = 0
        for record in self.cv_search_results:
            self.twList.insertRow(row)

            item_text = record['name']
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ToolTipRole, item_text)
            item.setData(QtCore.Qt.UserRole, record['id'])
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 0, item)

            item_text = str(record['start_year'])
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 1, item)

            item_text = record['count_of_issues']
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ToolTipRole, item_text)
            item.setData(QtCore.Qt.DisplayRole, record['count_of_issues'])
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 2, item)

            if record['publisher'] is not None:
                item_text = record['publisher']['name']
                item.setData(QtCore.Qt.ToolTipRole, item_text)
                item = QtWidgets.QTableWidgetItem(item_text)
                item.setFlags(
                    QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                self.twList.setItem(row, 3, item)

            row += 1

        self.twList.resizeColumnsToContents()
        self.twList.setSortingEnabled(True)
        self.twList.sortItems(2, QtCore.Qt.DescendingOrder)
        self.twList.selectRow(0)
        self.twList.resizeColumnsToContents()

        if len(self.cv_search_results) == 0:
            QtCore.QCoreApplication.processEvents()
            QtWidgets.QMessageBox.information(
                self, "Search Result", "No matches found!")

        if self.immediate_autoselect and len(self.cv_search_results) > 0:
            # defer the immediate autoselect so this dialog has time to pop up
            QtCore.QCoreApplication.processEvents()
            QtCore.QTimer.singleShot(10, self.doImmediateAutoselect)

    def doImmediateAutoselect(self):
        self.immediate_autoselect = False
        self.autoSelect()

    def cellDoubleClicked(self, r, c):
        self.showIssues()

    def currentItemChanged(self, curr, prev):

        if curr is None:
            return
        if prev is not None and prev.row() == curr.row():
            return

        self.volume_id = self.twList.item(curr.row(), 0).data(QtCore.Qt.UserRole)
             
        # list selection was changed, update the info on the volume
        for record in self.cv_search_results:
            if record['id'] == self.volume_id:
                if record['description'] is None:
                    self.teDetails.setText("")
                else:
                    self.teDetails.setText(record['description'])
                self.imageWidget.setURL(record['image']['super_url'])
                break
