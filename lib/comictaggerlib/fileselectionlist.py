# coding=utf-8
"""A PyQt5 widget for managing list of comic archive files"""

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

import platform
import os
#import os
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal

from .settings import ComicTaggerSettings
from .comicarchive import ComicArchive
from .optionalmsgdialog import OptionalMessageDialog
from comictaggerlib.ui.qtutils import reduceWidgetFontSize, centerWindowOnParent
from . import utils
#from comicarchive import MetaDataStyle
#from genericmetadata import GenericMetadata, PageType


class FileTableWidgetItem(QTableWidgetItem):

    def __lt__(self, other):
        #return (self.data(Qt.UserRole).toBool() <
        #        other.data(Qt.UserRole).toBool())
        return (self.data(Qt.UserRole) <
                other.data(Qt.UserRole))


class FileInfo():

    def __init__(self, ca):
        self.ca = ca


class FileSelectionList(QWidget):

    selectionChanged = pyqtSignal(QVariant)
    listCleared = pyqtSignal()

    fileColNum = 0
    CRFlagColNum = 1
    CBLFlagColNum = 2
    typeColNum = 3
    readonlyColNum = 4
    folderColNum = 5
    dataColNum = fileColNum

    def __init__(self, parent, settings):
        super(FileSelectionList, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.getUIFile('fileselectionlist.ui'), self)

        self.settings = settings

        reduceWidgetFontSize(self.twList)

        self.twList.setColumnCount(6)
        #self.twlist.setHorizontalHeaderLabels (["File", "Folder", "CR", "CBL", ""])
        # self.twList.horizontalHeader().setStretchLastSection(True)
        self.twList.currentItemChanged.connect(self.currentItemChangedCB)

        self.currentItem = None
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.modifiedFlag = False

        selectAllAction = QAction("Select All", self)
        removeAction = QAction("Remove Selected Items", self)
        self.separator = QAction("", self)
        self.separator.setSeparator(True)

        selectAllAction.setShortcut('Ctrl+A')
        removeAction.setShortcut('Ctrl+X')

        selectAllAction.triggered.connect(self.selectAll)
        removeAction.triggered.connect(self.removeSelection)

        self.addAction(selectAllAction)
        self.addAction(removeAction)
        self.addAction(self.separator)

    def getSorting(self):
        col = self.twList.horizontalHeader().sortIndicatorSection()
        order = self.twList.horizontalHeader().sortIndicatorOrder()
        return col, order

    def setSorting(self, col, order):
        col = self.twList.horizontalHeader().setSortIndicator(col, order)

    def addAppAction(self, action):
        self.insertAction(None, action)

    def setModifiedFlag(self, modified):
        self.modifiedFlag = modified

    def selectAll(self):
        self.twList.setRangeSelected(
            QTableWidgetSelectionRange(
                0,
                0,
                self.twList.rowCount() -
                1,
                5),
            True)

    def deselectAll(self):
        self.twList.setRangeSelected(
            QTableWidgetSelectionRange(
                0,
                0,
                self.twList.rowCount() -
                1,
                5),
            False)

    def removeArchiveList(self, ca_list):
        self.twList.setSortingEnabled(False)
        for ca in ca_list:
            for row in range(self.twList.rowCount()):
                row_ca = self.getArchiveByRow(row)
                if row_ca == ca:
                    self.twList.removeRow(row)
                    break
        self.twList.setSortingEnabled(True)

    def getArchiveByRow(self, row):
        fi = self.twList.item(row, FileSelectionList.dataColNum).data(
            Qt.UserRole)
        return fi.ca

    def getCurrentArchive(self):
        return self.getArchiveByRow(self.twList.currentRow())

    def removeSelection(self):
        row_list = []
        for item in self.twList.selectedItems():
            if item.column() == 0:
                row_list.append(item.row())

        if len(row_list) == 0:
            return

        if self.twList.currentRow() in row_list:
            if not self.modifiedFlagVerification(
                    "Remove Archive",
                    "If you close this archive, data in the form will be lost.  Are you sure?"):
                return

        row_list.sort()
        row_list.reverse()

        self.twList.currentItemChanged.disconnect(self.currentItemChangedCB)
        self.twList.setSortingEnabled(False)

        for i in row_list:
            self.twList.removeRow(i)

        self.twList.setSortingEnabled(True)
        self.twList.currentItemChanged.connect(self.currentItemChangedCB)

        if self.twList.rowCount() > 0:
            # since on a removal, we select row 0, make sure callback occurs if
            # we're already there
            if self.twList.currentRow() == 0:
                self.currentItemChangedCB(self.twList.currentItem(), None)
            self.twList.selectRow(0)
        else:
            self.listCleared.emit()

    def addPathList(self, pathlist):

        filelist = utils.get_recursive_filelist(pathlist)
        # we now have a list of files to add

        # Prog dialog on Linux flakes out for small range, so scale up
        progdialog = QProgressDialog("", "Cancel", 0, len(filelist), parent=self)
        progdialog.setWindowTitle("Adding Files")
        progdialog.setWindowModality(Qt.ApplicationModal)
        progdialog.setMinimumDuration(300)
        centerWindowOnParent(progdialog)
        #QCoreApplication.processEvents()
        #progdialog.show()
        
        QCoreApplication.processEvents()
        firstAdded = None
        self.twList.setSortingEnabled(False)
        for idx, f in enumerate(filelist):
            QCoreApplication.processEvents()
            if progdialog.wasCanceled():
                break
            progdialog.setValue(idx+1)
            progdialog.setLabelText(f)
            centerWindowOnParent(progdialog)
            QCoreApplication.processEvents()
            row = self.addPathItem(f)
            if firstAdded is None and row is not None:
                firstAdded = row
 
        progdialog.hide()
        QCoreApplication.processEvents()

        if firstAdded is not None:
            self.twList.selectRow(firstAdded)
        else:
            if len(pathlist) == 1 and os.path.isfile(pathlist[0]):
                QMessageBox.information(self, self.tr("File Open"), self.tr(
                    "Selected file doesn't seem to be a comic archive."))
            else:
                QMessageBox.information(
                    self,
                    self.tr("File/Folder Open"),
                    self.tr("No readable comic archives were found."))

        self.twList.setSortingEnabled(True)

        # Adjust column size
        self.twList.resizeColumnsToContents()
        self.twList.setColumnWidth(FileSelectionList.CRFlagColNum, 35)
        self.twList.setColumnWidth(FileSelectionList.CBLFlagColNum, 35)
        self.twList.setColumnWidth(FileSelectionList.readonlyColNum, 35)
        self.twList.setColumnWidth(FileSelectionList.typeColNum, 45)
        if self.twList.columnWidth(FileSelectionList.fileColNum) > 250:
            self.twList.setColumnWidth(FileSelectionList.fileColNum, 250)
        if self.twList.columnWidth(FileSelectionList.folderColNum) > 200:
            self.twList.setColumnWidth(FileSelectionList.folderColNum, 200)

    def isListDupe(self, path):
        r = 0
        while r < self.twList.rowCount():
            ca = self.getArchiveByRow(r)
            if ca.path == path:
                return True
            r = r + 1

        return False

    def getCurrentListRow(self, path):
        r = 0
        while r < self.twList.rowCount():
            ca = self.getArchiveByRow(r)
            if ca.path == path:
                return r
            r = r + 1

        return -1

    def addPathItem(self, path):
        path = str(path)
        path = os.path.abspath(path)
        # print "processing", path

        if self.isListDupe(path):
            return self.getCurrentListRow(path)

        ca = ComicArchive(
            path,
            self.settings.rar_exe_path,
            ComicTaggerSettings.getGraphic('nocover.png'))

        if ca.seemsToBeAComicArchive():
            row = self.twList.rowCount()
            self.twList.insertRow(row)

            fi = FileInfo(ca)

            filename_item = QTableWidgetItem()
            folder_item = QTableWidgetItem()
            cix_item = FileTableWidgetItem()
            cbi_item = FileTableWidgetItem()
            readonly_item = FileTableWidgetItem()
            type_item = QTableWidgetItem()

            filename_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            filename_item.setData(Qt.UserRole, fi)
            self.twList.setItem(
                row, FileSelectionList.fileColNum, filename_item)

            folder_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.twList.setItem(
                row, FileSelectionList.folderColNum, folder_item)

            type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.twList.setItem(row, FileSelectionList.typeColNum, type_item)

            cix_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            cix_item.setTextAlignment(Qt.AlignHCenter)
            self.twList.setItem(row, FileSelectionList.CRFlagColNum, cix_item)

            cbi_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            cbi_item.setTextAlignment(Qt.AlignHCenter)
            self.twList.setItem(row, FileSelectionList.CBLFlagColNum, cbi_item)

            readonly_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            readonly_item.setTextAlignment(Qt.AlignHCenter)
            self.twList.setItem(
                row, FileSelectionList.readonlyColNum, readonly_item)

            self.updateRow(row)

            return row

    def updateRow(self, row):
        fi = self.twList.item(row, FileSelectionList.dataColNum).data(
            Qt.UserRole) #.toPyObject()

        filename_item = self.twList.item(row, FileSelectionList.fileColNum)
        folder_item = self.twList.item(row, FileSelectionList.folderColNum)
        cix_item = self.twList.item(row, FileSelectionList.CRFlagColNum)
        cbi_item = self.twList.item(row, FileSelectionList.CBLFlagColNum)
        type_item = self.twList.item(row, FileSelectionList.typeColNum)
        readonly_item = self.twList.item(row, FileSelectionList.readonlyColNum)

        item_text = os.path.split(fi.ca.path)[0]
        folder_item.setText(item_text)
        folder_item.setData(Qt.ToolTipRole, item_text)

        item_text = os.path.split(fi.ca.path)[1]
        filename_item.setText(item_text)
        filename_item.setData(Qt.ToolTipRole, item_text)

        if fi.ca.isZip():
            item_text = "ZIP"
        elif fi.ca.isRar():
            item_text = "RAR"
        else:
            item_text = ""
        type_item.setText(item_text)
        type_item.setData(Qt.ToolTipRole, item_text)

        if fi.ca.hasCIX():
            cix_item.setCheckState(Qt.Checked)
            cix_item.setData(Qt.UserRole, True)
        else:
            cix_item.setData(Qt.UserRole, False)
            cix_item.setCheckState(Qt.Unchecked)

        if fi.ca.hasCBI():
            cbi_item.setCheckState(Qt.Checked)
            cbi_item.setData(Qt.UserRole, True)
        else:
            cbi_item.setData(Qt.UserRole, False)
            cbi_item.setCheckState(Qt.Unchecked)

        if not fi.ca.isWritable():
            readonly_item.setCheckState(Qt.Checked)
            readonly_item.setData(Qt.UserRole, True)
        else:
            readonly_item.setData(Qt.UserRole, False)
            readonly_item.setCheckState(Qt.Unchecked)

        # Reading these will force them into the ComicArchive's cache
        fi.ca.readCIX()
        fi.ca.hasCBI()

    def getSelectedArchiveList(self):
        ca_list = []
        for r in range(self.twList.rowCount()):
            item = self.twList.item(r, FileSelectionList.dataColNum)
            if item.isSelected():
                fi = item.data(Qt.UserRole)
                ca_list.append(fi.ca)

        return ca_list

    def updateCurrentRow(self):
        self.updateRow(self.twList.currentRow())

    def updateSelectedRows(self):
        self.twList.setSortingEnabled(False)
        for r in range(self.twList.rowCount()):
            item = self.twList.item(r, FileSelectionList.dataColNum)
            if item.isSelected():
                self.updateRow(r)
        self.twList.setSortingEnabled(True)

    def currentItemChangedCB(self, curr, prev):

        new_idx = curr.row()
        old_idx = -1
        if prev is not None:
            old_idx = prev.row()
        #print("old {0} new {1}".format(old_idx, new_idx))

        if old_idx == new_idx:
            return

        # don't allow change if modified
        if prev is not None and new_idx != old_idx:
            if not self.modifiedFlagVerification(
                    "Change Archive",
                    "If you change archives now, data in the form will be lost.  Are you sure?"):
                self.twList.currentItemChanged.disconnect(
                    self.currentItemChangedCB)
                self.twList.setCurrentItem(prev)
                self.twList.currentItemChanged.connect(
                    self.currentItemChangedCB)
                # Need to defer this revert selection, for some reason
                QTimer.singleShot(1, self.revertSelection)
                return

        fi = self.twList.item(new_idx, FileSelectionList.dataColNum).data(
            Qt.UserRole) #.toPyObject()
        self.selectionChanged.emit(QVariant(fi))

    def revertSelection(self):
        self.twList.selectRow(self.twList.currentRow())

    def modifiedFlagVerification(self, title, desc):
        if self.modifiedFlag:
            reply = QMessageBox.question(self,
                                         self.tr(title),
                                         self.tr(desc),
                                         QMessageBox.Yes, QMessageBox.No)

            if reply != QMessageBox.Yes:
                return False
        return True


# Attempt to use a special checkbox widget in the cell.
# Couldn't figure out how to disable it with "enabled" colors
#w = QWidget()
#cb = QCheckBox(w)
# cb.setCheckState(Qt.Checked)
#layout = QHBoxLayout()
# layout.addWidget(cb)
# layout.setAlignment(Qt.AlignHCenter)
# layout.setMargin(2)
# w.setLayout(layout)
#self.twList.setCellWidget(row, 2, w)
