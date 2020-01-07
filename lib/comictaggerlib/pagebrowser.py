"""A PyQT4 dialog to show pages of a comic archive"""

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
#import sys
#import os

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from .settings import ComicTaggerSettings
from .coverimagewidget import CoverImageWidget


class PageBrowserWindow(QtWidgets.QDialog):

    def __init__(self, parent, metadata):
        super(PageBrowserWindow, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.getUIFile('pagebrowser.ui'), self)

        self.pageWidget = CoverImageWidget(
            self.pageContainer, CoverImageWidget.ArchiveMode)
        gridlayout = QtWidgets.QGridLayout(self.pageContainer)
        gridlayout.addWidget(self.pageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)
        self.pageWidget.showControls = False

        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowSystemMenuHint |
                            QtCore.Qt.WindowMaximizeButtonHint)

        self.comic_archive = None
        self.page_count = 0
        self.current_page_num = 0
        self.metadata = metadata

        self.buttonBox.button(QtWidgets.QDialogButtonBox.Close).setDefault(True)
        if platform.system() == "Darwin":
            self.btnPrev.setText("<<")
            self.btnNext.setText(">>")
        else:
            self.btnPrev.setIcon(
                QtGui.QIcon(ComicTaggerSettings.getGraphic('left.png')))
            self.btnNext.setIcon(
                QtGui.QIcon(ComicTaggerSettings.getGraphic('right.png')))

        self.btnNext.clicked.connect(self.nextPage)
        self.btnPrev.clicked.connect(self.prevPage)
        self.show()

        self.btnNext.setEnabled(False)
        self.btnPrev.setEnabled(False)

    def reset(self):
        self.comic_archive = None
        self.page_count = 0
        self.current_page_num = 0
        self.metadata = None

        self.btnNext.setEnabled(False)
        self.btnPrev.setEnabled(False)
        self.pageWidget.clear()

    def setComicArchive(self, ca):

        self.comic_archive = ca
        self.page_count = ca.getNumberOfPages()
        self.current_page_num = 0
        self.pageWidget.setArchive(self.comic_archive)
        self.setPage()

        if self.page_count > 1:
            self.btnNext.setEnabled(True)
            self.btnPrev.setEnabled(True)

    def nextPage(self):

        if self.current_page_num + 1 < self.page_count:
            self.current_page_num += 1
        else:
            self.current_page_num = 0
        self.setPage()

    def prevPage(self):

        if self.current_page_num - 1 >= 0:
            self.current_page_num -= 1
        else:
            self.current_page_num = self.page_count - 1
        self.setPage()

    def setPage(self):
        if self.metadata is not None:
            archive_page_index = self.metadata.getArchivePageIndex(
                self.current_page_num)
        else:
            archive_page_index = self.current_page_num

        self.pageWidget.setPage(archive_page_index)
        self.setWindowTitle(
            "Page Browser - Page {0} (of {1}) ".format(self.current_page_num + 1, self.page_count))
