"""A PyQT4 dialog to edit credits"""

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


class CreditEditorWindow(QtWidgets.QDialog):

    ModeEdit = 0
    ModeNew = 1

    def __init__(self, parent, mode, role, name, primary):
        super(CreditEditorWindow, self).__init__(parent)

        uic.loadUi(
            ComicTaggerSettings.getUIFile('crediteditorwindow.ui'), self)

        self.mode = mode

        if self.mode == self.ModeEdit:
            self.setWindowTitle("Edit Credit")
        else:
            self.setWindowTitle("New Credit")

        # Add the entries to the role combobox
        self.cbRole.addItem("")
        self.cbRole.addItem("Writer")
        self.cbRole.addItem("Artist")
        self.cbRole.addItem("Penciller")
        self.cbRole.addItem("Inker")
        self.cbRole.addItem("Colorist")
        self.cbRole.addItem("Letterer")
        self.cbRole.addItem("Cover Artist")
        self.cbRole.addItem("Editor")
        self.cbRole.addItem("Other")
        self.cbRole.addItem("Plotter")
        self.cbRole.addItem("Scripter")

        self.leName.setText(name)

        if role is not None and role != "":
            i = self.cbRole.findText(role)
            if i == -1:
                self.cbRole.setEditText(role)
            else:
                self.cbRole.setCurrentIndex(i)

        if primary:
            self.cbPrimary.setCheckState(QtCore.Qt.Checked)

        self.cbRole.currentIndexChanged.connect(self.roleChanged)
        self.cbRole.editTextChanged.connect(self.roleChanged)

        self.updatePrimaryButton()

    def updatePrimaryButton(self):
        enabled = self.currentRoleCanBePrimary()
        self.cbPrimary.setEnabled(enabled)

    def currentRoleCanBePrimary(self):
        role = self.cbRole.currentText()
        if str(role).lower() == "writer" or str(role).lower() == "artist":
            return True
        else:
            return False

    def roleChanged(self, s):
        self.updatePrimaryButton()

    def getCredits(self):
        primary = self.currentRoleCanBePrimary() and self.cbPrimary.isChecked()
        return self.cbRole.currentText(), self.leName.text(), primary

    def accept(self):
        if self.cbRole.currentText() == "" or self.leName.text() == "":
            QtWidgets.QMessageBox.warning(self, self.tr("Whoops"), self.tr(
                "You need to enter both role and name for a credit."))
        else:
            QtWidgets.QDialog.accept(self)
