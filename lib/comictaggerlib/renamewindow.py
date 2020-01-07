"""A PyQT4 dialog to confirm rename"""

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

import os

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from .settings import ComicTaggerSettings
from .settingswindow import SettingsWindow
from .filerenamer import FileRenamer
from .comicarchive import MetaDataStyle
from comictaggerlib.ui.qtutils import  centerWindowOnParent
from . import utils


class RenameWindow(QtWidgets.QDialog):

    def __init__(self, parent, comic_archive_list, data_style, settings):
        super(RenameWindow, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.getUIFile('renamewindow.ui'), self)
        self.label.setText(
            "Preview (based on {0} tags):".format(
                MetaDataStyle.name[data_style]))

        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowSystemMenuHint |
                            QtCore.Qt.WindowMaximizeButtonHint)

        self.settings = settings
        self.comic_archive_list = comic_archive_list
        self.data_style = data_style

        self.btnSettings.clicked.connect(self.modifySettings)
        self.configRenamer()
        self.doPreview()

    def configRenamer(self):
        self.renamer = FileRenamer(None)
        self.renamer.setTemplate(self.settings.rename_template)
        self.renamer.setIssueZeroPadding(
            self.settings.rename_issue_number_padding)
        self.renamer.setSmartCleanup(
            self.settings.rename_use_smart_string_cleanup)

    def doPreview(self):
        self.rename_list = []
        while self.twList.rowCount() > 0:
            self.twList.removeRow(0)

        self.twList.setSortingEnabled(False)

        for ca in self.comic_archive_list:

            new_ext = None  # default
            if self.settings.rename_extension_based_on_archive:
                if ca.isZip():
                    new_ext = ".cbz"
                elif ca.isRar():
                    new_ext = ".cbr"

            md = ca.readMetadata(self.data_style)
            if md.isEmpty:
                md = ca.metadataFromFilename(self.settings.parse_scan_info)
            self.renamer.setMetadata(md)
            new_name = self.renamer.determineName(ca.path, ext=new_ext)

            row = self.twList.rowCount()
            self.twList.insertRow(row)
            folder_item = QtWidgets.QTableWidgetItem()
            old_name_item = QtWidgets.QTableWidgetItem()
            new_name_item = QtWidgets.QTableWidgetItem()

            item_text = os.path.split(ca.path)[0]
            folder_item.setFlags(
                QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 0, folder_item)
            folder_item.setText(item_text)
            folder_item.setData(QtCore.Qt.ToolTipRole, item_text)

            item_text = os.path.split(ca.path)[1]
            old_name_item.setFlags(
                QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 1, old_name_item)
            old_name_item.setText(item_text)
            old_name_item.setData(QtCore.Qt.ToolTipRole, item_text)

            new_name_item.setFlags(
                QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.twList.setItem(row, 2, new_name_item)
            new_name_item.setText(new_name)
            new_name_item.setData(QtCore.Qt.ToolTipRole, new_name)

            dict_item = dict()
            dict_item['archive'] = ca
            dict_item['new_name'] = new_name
            self.rename_list.append(dict_item)

        # Adjust column sizes
        self.twList.setVisible(False)
        self.twList.resizeColumnsToContents()
        self.twList.setVisible(True)
        if self.twList.columnWidth(0) > 200:
            self.twList.setColumnWidth(0, 200)

        self.twList.setSortingEnabled(True)

    def modifySettings(self):
        settingswin = SettingsWindow(self, self.settings)
        settingswin.setModal(True)
        settingswin.showRenameTab()
        settingswin.exec_()
        if settingswin.result():
            self.configRenamer()
            self.doPreview()

    def accept(self):

        progdialog = QtWidgets.QProgressDialog(
            "", "Cancel", 0, len(self.rename_list), self)
        progdialog.setWindowTitle("Renaming Archives")
        progdialog.setWindowModality(QtCore.Qt.WindowModal)
        progdialog.setMinimumDuration(100)
        centerWindowOnParent(progdialog)
        #progdialog.show()
        QtCore.QCoreApplication.processEvents()

        for idx, item in enumerate(self.rename_list):

            QtCore.QCoreApplication.processEvents()
            if progdialog.wasCanceled():
                break
            idx += 1
            progdialog.setValue(idx)
            progdialog.setLabelText(item['new_name'])
            centerWindowOnParent(progdialog)
            QtCore.QCoreApplication.processEvents()

            if item['new_name'] == os.path.basename(item['archive'].path):
                print(item['new_name'], "Filename is already good!")
                continue

            if not item['archive'].isWritable(check_rar_status=False):
                continue

            folder = os.path.dirname(os.path.abspath(item['archive'].path))
            new_abs_path = utils.unique_file(
                os.path.join(folder, item['new_name']))

            os.rename(item['archive'].path, new_abs_path)

            item['archive'].rename(new_abs_path)

        progdialog.hide()
        QtCore.QCoreApplication.processEvents()

        QtWidgets.QDialog.accept(self)
