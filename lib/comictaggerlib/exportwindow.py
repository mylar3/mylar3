"""A PyQT4 dialog to confirm and set options for export to zip"""

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

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from .settings import ComicTaggerSettings
#from settingswindow import SettingsWindow
#from filerenamer import FileRenamer
#import utils


class ExportConflictOpts:
    dontCreate = 1
    overwrite = 2
    createUnique = 3


class ExportWindow(QtWidgets.QDialog):

    def __init__(self, parent, settings, msg):
        super(ExportWindow, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.getUIFile('exportwindow.ui'), self)
        self.label.setText(msg)

        self.setWindowFlags(self.windowFlags() &
                            ~QtCore.Qt.WindowContextHelpButtonHint)

        self.settings = settings

        self.cbxDeleteOriginal.setCheckState(QtCore.Qt.Unchecked)
        self.cbxAddToList.setCheckState(QtCore.Qt.Checked)
        self.radioDontCreate.setChecked(True)

        self.deleteOriginal = False
        self.addToList = True
        self.fileConflictBehavior = ExportConflictOpts.dontCreate

    def accept(self):
        QtWidgets.QDialog.accept(self)

        self.deleteOriginal = self.cbxDeleteOriginal.isChecked()
        self.addToList = self.cbxAddToList.isChecked()
        if self.radioDontCreate.isChecked():
            self.fileConflictBehavior = ExportConflictOpts.dontCreate
        elif self.radioCreateNew.isChecked():
            self.fileConflictBehavior = ExportConflictOpts.createUnique
        # else:
        #    self.fileConflictBehavior = ExportConflictOpts.overwrite
