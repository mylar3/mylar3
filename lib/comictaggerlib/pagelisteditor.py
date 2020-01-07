"""A PyQt5 widget for editing the page list info"""

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

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic

from .settings import ComicTaggerSettings
from .genericmetadata import GenericMetadata, PageType
from .comicarchive import MetaDataStyle
from .coverimagewidget import CoverImageWidget
#from pageloader import PageLoader


def itemMoveEvents(widget):

    class Filter(QObject):

        mysignal = pyqtSignal(str)

        def eventFilter(self, obj, event):

            if obj == widget:
                # print(event.type())
                if event.type() == QEvent.ChildRemoved:
                    # print("ChildRemoved")
                    self.mysignal.emit("finish")
                if event.type() == QEvent.ChildAdded:
                    # print("ChildAdded")
                    self.mysignal.emit("start")
                    return True

            return False

    filter = Filter(widget)
    widget.installEventFilter(filter)
    return filter.mysignal


class PageListEditor(QWidget):

    firstFrontCoverChanged = pyqtSignal(int)
    listOrderChanged = pyqtSignal()
    modified = pyqtSignal()

    pageTypeNames = {
        PageType.FrontCover: "Front Cover",
        PageType.InnerCover: "Inner Cover",
        PageType.Advertisement: "Advertisement",
        PageType.Roundup: "Roundup",
        PageType.Story: "Story",
        PageType.Editorial: "Editorial",
        PageType.Letters: "Letters",
        PageType.Preview: "Preview",
        PageType.BackCover: "Back Cover",
        PageType.Other: "Other",
        PageType.Deleted: "Deleted",
    }

    def __init__(self, parent):
        super(PageListEditor, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.getUIFile('pagelisteditor.ui'), self)

        self.pageWidget = CoverImageWidget(
            self.pageContainer, CoverImageWidget.ArchiveMode)
        gridlayout = QGridLayout(self.pageContainer)
        gridlayout.addWidget(self.pageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)
        self.pageWidget.showControls = False

        self.resetPage()

        # Add the entries to the manga combobox
        self.comboBox.addItem("", "")
        self.comboBox.addItem(
            self.pageTypeNames[PageType.FrontCover], PageType.FrontCover)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.InnerCover], PageType.InnerCover)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.Advertisement], PageType.Advertisement)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.Roundup], PageType.Roundup)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.Story], PageType.Story)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.Editorial], PageType.Editorial)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.Letters], PageType.Letters)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.Preview], PageType.Preview)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.BackCover], PageType.BackCover)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.Other], PageType.Other)
        self.comboBox.addItem(
            self.pageTypeNames[PageType.Deleted], PageType.Deleted)

        self.listWidget.itemSelectionChanged.connect(self.changePage)
        itemMoveEvents(self.listWidget).connect(self.itemMoveEvent)
        self.comboBox.activated.connect(self.changePageType)
        self.btnUp.clicked.connect(self.moveCurrentUp)
        self.btnDown.clicked.connect(self.moveCurrentDown)
        self.pre_move_row = -1
        self.first_front_page = None

    def resetPage(self):
        self.pageWidget.clear()
        self.comboBox.setDisabled(True)
        self.comic_archive = None
        self.pages_list = None

    def moveCurrentUp(self):
        row = self.listWidget.currentRow()
        if row > 0:
            item = self.listWidget.takeItem(row)
            self.listWidget.insertItem(row - 1, item)
            self.listWidget.setCurrentRow(row - 1)
            self.listOrderChanged.emit()
            self.emitFrontCoverChange()
            self.modified.emit()

    def moveCurrentDown(self):
        row = self.listWidget.currentRow()
        if row < self.listWidget.count() - 1:
            item = self.listWidget.takeItem(row)
            self.listWidget.insertItem(row + 1, item)
            self.listWidget.setCurrentRow(row + 1)
            self.listOrderChanged.emit()
            self.emitFrontCoverChange()
            self.modified.emit()

    def itemMoveEvent(self, s):
        # print "move event: ", s, self.listWidget.currentRow()
        if s == "start":
            self.pre_move_row = self.listWidget.currentRow()
        if s == "finish":
            if self.pre_move_row != self.listWidget.currentRow():
                self.listOrderChanged.emit()
                self.emitFrontCoverChange()
                self.modified.emit()

    def changePageType(self, i):
        new_type = self.comboBox.itemData(i).toString()
        if self.getCurrentPageType() != new_type:
            self.setCurrentPageType(new_type)
            self.emitFrontCoverChange()
            self.modified.emit()

    def changePage(self):
        row = self.listWidget.currentRow()
        pagetype = self.getCurrentPageType()

        i = self.comboBox.findData(pagetype)
        self.comboBox.setCurrentIndex(i)

        #idx = int(str (self.listWidget.item(row).text()))
        idx = int(self.listWidget.item(row).data(
            Qt.UserRole)[0]['Image'])

        if self.comic_archive is not None:
            self.pageWidget.setArchive(self.comic_archive, idx)

    def getFirstFrontCover(self):
        frontCover = 0
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            page_dict = item.data(Qt.UserRole)[0] #.toPyObject()[0]
            if 'Type' in page_dict and page_dict[
                    'Type'] == PageType.FrontCover:
                frontCover = int(page_dict['Image'])
                break
        return frontCover

    def getCurrentPageType(self):
        row = self.listWidget.currentRow()
        page_dict = self.listWidget.item(row).data(Qt.UserRole)[0] #.toPyObject()[0]
        if 'Type' in page_dict:
            return page_dict['Type']
        else:
            return ""

    def setCurrentPageType(self, t):
        row = self.listWidget.currentRow()
        page_dict = self.listWidget.item(row).data(Qt.UserRole)[0] #.toPyObject()[0]

        if t == "":
            if 'Type' in page_dict:
                del(page_dict['Type'])
        else:
            page_dict['Type'] = str(t)

        item = self.listWidget.item(row)
        # wrap the dict in a tuple to keep from being converted to QStrings
        item.setData(Qt.UserRole, (page_dict,))
        item.setText(self.listEntryText(page_dict))

    def setData(self, comic_archive, pages_list):
        self.comic_archive = comic_archive
        self.pages_list = pages_list
        if pages_list is not None and len(pages_list) > 0:
            self.comboBox.setDisabled(False)

        self.listWidget.itemSelectionChanged.disconnect(self.changePage)

        self.listWidget.clear()
        for p in pages_list:
            item = QListWidgetItem(self.listEntryText(p))
            # wrap the dict in a tuple to keep from being converted to QStrings
            item.setData(Qt.UserRole, (p,))

            self.listWidget.addItem(item)
        self.first_front_page = self.getFirstFrontCover()
        self.listWidget.itemSelectionChanged.connect(self.changePage)
        self.listWidget.setCurrentRow(0)

    def listEntryText(self, page_dict):
        text = str(int(page_dict['Image']) + 1)
        if 'Type' in page_dict:
            text += " (" + self.pageTypeNames[page_dict['Type']] + ")"
        return text

    def getPageList(self):
        page_list = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            page_list.append(item.data(Qt.UserRole)[0]) #.toPyObject()[0]
        return page_list

    def emitFrontCoverChange(self):
        if self.first_front_page != self.getFirstFrontCover():
            self.first_front_page = self.getFirstFrontCover()
            self.firstFrontCoverChanged.emit(self.first_front_page)

    def setMetadataStyle(self, data_style):

        # depending on the current data style, certain fields are disabled

        inactive_color = QColor(255, 170, 150)
        active_palette = self.comboBox.palette()

        inactive_palette3 = self.comboBox.palette()
        inactive_palette3.setColor(QPalette.Base, inactive_color)

        if data_style == MetaDataStyle.CIX:
            self.btnUp.setEnabled(True)
            self.btnDown.setEnabled(True)
            self.comboBox.setEnabled(True)
            self.listWidget.setEnabled(True)

            self.listWidget.setPalette(active_palette)

        elif data_style == MetaDataStyle.CBI:
            self.btnUp.setEnabled(False)
            self.btnDown.setEnabled(False)
            self.comboBox.setEnabled(False)
            self.listWidget.setEnabled(False)

            self.listWidget.setPalette(inactive_palette3)

        elif data_style == MetaDataStyle.CoMet:
            pass

        # make sure combo is disabled when no list
        if self.comic_archive is None:
            self.comboBox.setEnabled(False)
