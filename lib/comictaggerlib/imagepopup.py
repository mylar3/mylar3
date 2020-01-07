"""A PyQT4 widget to display a popup image"""

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


class ImagePopup(QtWidgets.QDialog):

    def __init__(self, parent, image_pixmap):
        super(ImagePopup, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.getUIFile('imagepopup.ui'), self)

        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.WaitCursor))

        # self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowFlags(QtCore.Qt.Popup)
        self.setWindowState(QtCore.Qt.WindowFullScreen)

        self.imagePixmap = image_pixmap

        screen_size = QtWidgets.QDesktopWidget().screenGeometry()
        self.resize(screen_size.width(), screen_size.height())
        self.move(0, 0)

        # This is a total hack.  Uses a snapshot of the desktop, and overlays a
        # translucent screen over it.  Probably can do it better by setting opacity of a
        # widget
        screen = QtWidgets.QApplication.primaryScreen()
        self.desktopBg = screen.grabWindow(
            QtWidgets.QApplication.desktop().winId(),
            0,
            0,
            screen_size.width(),
            screen_size.height())
        bg = QtGui.QPixmap(ComicTaggerSettings.getGraphic('popup_bg.png'))
        self.clientBgPixmap = bg.scaled(
            screen_size.width(), screen_size.height())
        self.setMask(self.clientBgPixmap.mask())

        self.applyImagePixmap()
        self.showFullScreen()
        self.raise_()
        QtWidgets.QApplication.restoreOverrideCursor()

    def paintEvent(self, event):
        self.painter = QtGui.QPainter(self)
        self.painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.painter.drawPixmap(0, 0, self.desktopBg)
        self.painter.drawPixmap(0, 0, self.clientBgPixmap)
        self.painter.end()

    def applyImagePixmap(self):
        win_h = self.height()
        win_w = self.width()

        if self.imagePixmap.width(
        ) > win_w or self.imagePixmap.height() > win_h:
            # scale the pixmap to fit in the frame
            display_pixmap = self.imagePixmap.scaled(
                win_w, win_h, QtCore.Qt.KeepAspectRatio)
            self.lblImage.setPixmap(display_pixmap)
        else:
            display_pixmap = self.imagePixmap
        self.lblImage.setPixmap(display_pixmap)

        # move and resize the label to be centered in the fame
        img_w = display_pixmap.width()
        img_h = display_pixmap.height()
        self.lblImage.resize(img_w, img_h)
        self.lblImage.move((win_w - img_w) / 2, (win_h - img_h) / 2)

    def mousePressEvent(self, event):
        self.close()
