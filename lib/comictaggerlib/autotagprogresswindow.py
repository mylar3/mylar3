"""A PyQT4 dialog to show ID log and progress"""

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

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from .settings import ComicTaggerSettings
from .coverimagewidget import CoverImageWidget
from comictaggerlib.ui.qtutils import reduceWidgetFontSize
#import utils


class AutoTagProgressWindow(QtWidgets.QDialog):

    def __init__(self, parent):
        super(AutoTagProgressWindow, self).__init__(parent)

        uic.loadUi(
            ComicTaggerSettings.getUIFile('autotagprogresswindow.ui'), self)

        self.archiveCoverWidget = CoverImageWidget(
            self.archiveCoverContainer, CoverImageWidget.DataMode, False)
        gridlayout = QtWidgets.QGridLayout(self.archiveCoverContainer)
        gridlayout.addWidget(self.archiveCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.testCoverWidget = CoverImageWidget(
            self.testCoverContainer, CoverImageWidget.DataMode, False)
        gridlayout = QtWidgets.QGridLayout(self.testCoverContainer)
        gridlayout.addWidget(self.testCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.isdone = False

        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowSystemMenuHint |
                            QtCore.Qt.WindowMaximizeButtonHint)

        reduceWidgetFontSize(self.textEdit)

    def setArchiveImage(self, img_data):
        self.setCoverImage(img_data, self.archiveCoverWidget)

    def setTestImage(self, img_data):
        self.setCoverImage(img_data, self.testCoverWidget)

    def setCoverImage(self, img_data, widget):
        widget.setImageData(img_data)
        QtCore.QCoreApplication.processEvents()
        QtCore.QCoreApplication.processEvents()

    def reject(self):
        QtWidgets.QDialog.reject(self)
        self.isdone = True
