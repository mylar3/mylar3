"""A PyQT4 dialog to enter app settings"""

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

from PyQt4 import QtCore, QtGui, uic

from settings import ComicTaggerSettings
from comicvinecacher import ComicVineCacher
from comicvinetalker import ComicVineTalker
from imagefetcher import ImageFetcher
import utils


windowsRarHelp = """
                 <html><head/><body><p>In order to write to CBR/RAR archives,
                 you will need to have the tools from
                 <a href="http://www.win-rar.com/download.html">
                 <span style=" text-decoration: underline; color:#0000ff;">WinRAR</span>
                 </a> installed. </p></body></html>
                """

linuxRarHelp = """
               <html><head/><body><p>In order to read/write to CBR/RAR archives,
               you will need to have the shareware tools from WinRar installed.
               Your package manager should have unrar, and probably rar.
               If not, download them <a href="http://www.win-rar.com/download.html">
               <span style=" text-decoration: underline; color:#0000ff;">here</span>
               </a>, and install in your path. </p></body></html>
               """
macRarHelp = """
                 <html><head/><body><p>In order to read/write to CBR/RAR archives,
                 you will need the shareware tools from
                 <a href="http://www.win-rar.com/download.html">
                 <span style=" text-decoration: underline; color:#0000ff;">WinRAR</span>
                 </a>. </p></body></html>
                """


class SettingsWindow(QtGui.QDialog):

    def __init__(self, parent, settings):
        super(SettingsWindow, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.getUIFile('settingswindow.ui'), self)

        self.setWindowFlags(self.windowFlags() &
                            ~QtCore.Qt.WindowContextHelpButtonHint)

        self.settings = settings
        self.name = "Settings"

        if platform.system() == "Windows":
            self.lblUnrar.hide()
            self.leUnrarExePath.hide()
            self.btnBrowseUnrar.hide()
            self.lblRarHelp.setText(windowsRarHelp)

        elif platform.system() == "Linux":
            self.lblRarHelp.setText(linuxRarHelp)

        elif platform.system() == "Darwin":
            self.lblRarHelp.setText(macRarHelp)
            self.name = "Preferences"

        self.setWindowTitle("ComicTagger " + self.name)
        self.lblDefaultSettings.setText(
            "Revert to default " + self.name.lower())
        self.btnResetSettings.setText("Default " + self.name)

        nldtTip = (
            """<html>The <b>Default Name Length Match Tolerance</b> is for eliminating automatic
                search matches that are too long compared to your series name search. The higher
                it is, the more likely to have a good match, but each search will take longer and
                use more bandwidth. Too low, and only the very closest lexical matches will be
                explored.</html>""")

        self.leNameLengthDeltaThresh.setToolTip(nldtTip)

        pblTip = (
            """<html>
            The <b>Publisher Blacklist</b> is for eliminating automatic matches to certain publishers
            that you know are incorrect. Useful for avoiding international re-prints with same
            covers or series names. Enter publisher names separated by commas.
            </html>"""
        )
        self.tePublisherBlacklist.setToolTip(pblTip)

        validator = QtGui.QIntValidator(1, 4, self)
        self.leIssueNumPadding.setValidator(validator)

        validator = QtGui.QIntValidator(0, 99, self)
        self.leNameLengthDeltaThresh.setValidator(validator)

        self.settingsToForm()

        self.btnBrowseRar.clicked.connect(self.selectRar)
        self.btnBrowseUnrar.clicked.connect(self.selectUnrar)
        self.btnClearCache.clicked.connect(self.clearCache)
        self.btnResetSettings.clicked.connect(self.resetSettings)
        self.btnTestKey.clicked.connect(self.testAPIKey)

    def settingsToForm(self):

        # Copy values from settings to form
        self.leRarExePath.setText(self.settings.rar_exe_path)
        self.leUnrarExePath.setText(self.settings.unrar_exe_path)
        self.leNameLengthDeltaThresh.setText(
            str(self.settings.id_length_delta_thresh))
        self.tePublisherBlacklist.setPlainText(
            self.settings.id_publisher_blacklist)

        if self.settings.check_for_new_version:
            self.cbxCheckForNewVersion.setCheckState(QtCore.Qt.Checked)

        if self.settings.parse_scan_info:
            self.cbxParseScanInfo.setCheckState(QtCore.Qt.Checked)

        if self.settings.use_series_start_as_volume:
            self.cbxUseSeriesStartAsVolume.setCheckState(QtCore.Qt.Checked)
        if self.settings.clear_form_before_populating_from_cv:
            self.cbxClearFormBeforePopulating.setCheckState(QtCore.Qt.Checked)
        if self.settings.remove_html_tables:
            self.cbxRemoveHtmlTables.setCheckState(QtCore.Qt.Checked)
        self.leKey.setText(str(self.settings.cv_api_key))

        if self.settings.assume_lone_credit_is_primary:
            self.cbxAssumeLoneCreditIsPrimary.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_characters_to_tags:
            self.cbxCopyCharactersToTags.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_teams_to_tags:
            self.cbxCopyTeamsToTags.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_locations_to_tags:
            self.cbxCopyLocationsToTags.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_storyarcs_to_tags:
            self.cbxCopyStoryArcsToTags.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_notes_to_comments:
            self.cbxCopyNotesToComments.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_weblink_to_comments:
            self.cbxCopyWebLinkToComments.setCheckState(QtCore.Qt.Checked)
        if self.settings.apply_cbl_transform_on_cv_import:
            self.cbxApplyCBLTransformOnCVIMport.setCheckState(
                QtCore.Qt.Checked)
        if self.settings.apply_cbl_transform_on_bulk_operation:
            self.cbxApplyCBLTransformOnBatchOperation.setCheckState(
                QtCore.Qt.Checked)

        self.leRenameTemplate.setText(self.settings.rename_template)
        self.leIssueNumPadding.setText(
            str(self.settings.rename_issue_number_padding))
        if self.settings.rename_use_smart_string_cleanup:
            self.cbxSmartCleanup.setCheckState(QtCore.Qt.Checked)
        if self.settings.rename_extension_based_on_archive:
            self.cbxChangeExtension.setCheckState(QtCore.Qt.Checked)

    def accept(self):

        # Copy values from form to settings and save
        self.settings.rar_exe_path = str(self.leRarExePath.text())
        self.settings.unrar_exe_path = str(self.leUnrarExePath.text())

        # make sure unrar/rar program is now in the path for the UnRAR class
        utils.addtopath(os.path.dirname(self.settings.unrar_exe_path))
        utils.addtopath(os.path.dirname(self.settings.rar_exe_path))

        if not str(self.leNameLengthDeltaThresh.text()).isdigit():
            self.leNameLengthDeltaThresh.setText("0")

        if not str(self.leIssueNumPadding.text()).isdigit():
            self.leIssueNumPadding.setText("0")

        self.settings.check_for_new_version = self.cbxCheckForNewVersion.isChecked()

        self.settings.id_length_delta_thresh = int(
            self.leNameLengthDeltaThresh.text())
        self.settings.id_publisher_blacklist = str(
            self.tePublisherBlacklist.toPlainText())

        self.settings.parse_scan_info = self.cbxParseScanInfo.isChecked()

        self.settings.use_series_start_as_volume = self.cbxUseSeriesStartAsVolume.isChecked()
        self.settings.clear_form_before_populating_from_cv = self.cbxClearFormBeforePopulating.isChecked()
        self.settings.remove_html_tables = self.cbxRemoveHtmlTables.isChecked()
        self.settings.cv_api_key = unicode(self.leKey.text())
        ComicVineTalker.api_key = self.settings.cv_api_key
        self.settings.assume_lone_credit_is_primary = self.cbxAssumeLoneCreditIsPrimary.isChecked()
        self.settings.copy_characters_to_tags = self.cbxCopyCharactersToTags.isChecked()
        self.settings.copy_teams_to_tags = self.cbxCopyTeamsToTags.isChecked()
        self.settings.copy_locations_to_tags = self.cbxCopyLocationsToTags.isChecked()
        self.settings.copy_storyarcs_to_tags = self.cbxCopyStoryArcsToTags.isChecked()
        self.settings.copy_notes_to_comments = self.cbxCopyNotesToComments.isChecked()
        self.settings.copy_weblink_to_comments = self.cbxCopyWebLinkToComments.isChecked()
        self.settings.apply_cbl_transform_on_cv_import = self.cbxApplyCBLTransformOnCVIMport.isChecked()
        self.settings.apply_cbl_transform_on_bulk_operation = self.cbxApplyCBLTransformOnBatchOperation.isChecked()

        self.settings.rename_template = str(self.leRenameTemplate.text())
        self.settings.rename_issue_number_padding = int(
            self.leIssueNumPadding.text())
        self.settings.rename_use_smart_string_cleanup = self.cbxSmartCleanup.isChecked()
        self.settings.rename_extension_based_on_archive = self.cbxChangeExtension.isChecked()

        self.settings.save()
        QtGui.QDialog.accept(self)

    def selectRar(self):
        self.selectFile(self.leRarExePath, "RAR")

    def selectUnrar(self):
        self.selectFile(self.leUnrarExePath, "UnRAR")

    def clearCache(self):
        ImageFetcher().clearCache()
        ComicVineCacher().clearCache()
        QtGui.QMessageBox.information(
            self, self.name, "Cache has been cleared.")

    def testAPIKey(self):
        if ComicVineTalker().testKey(unicode(self.leKey.text())):
            QtGui.QMessageBox.information(
                self, "API Key Test", "Key is valid!")
        else:
            QtGui.QMessageBox.warning(
                self, "API Key Test", "Key is NOT valid.")

    def resetSettings(self):
        self.settings.reset()
        self.settingsToForm()
        QtGui.QMessageBox.information(
            self,
            self.name,
            self.name +
            " have been returned to default values.")

    def selectFile(self, control, name):

        dialog = QtGui.QFileDialog(self)
        dialog.setFileMode(QtGui.QFileDialog.ExistingFile)

        if platform.system() == "Windows":
            if name == "RAR":
                filter = self.tr("Rar Program (Rar.exe)")
            else:
                filter = self.tr("Programs (*.exe)")
            dialog.setNameFilter(filter)
        else:
            # QtCore.QDir.Executable | QtCore.QDir.Files)
            dialog.setFilter(QtCore.QDir.Files)
            pass

        dialog.setDirectory(os.path.dirname(str(control.text())))
        dialog.setWindowTitle("Find " + name + " program")

        if (dialog.exec_()):
            fileList = dialog.selectedFiles()
            control.setText(str(fileList[0]))

    def showRenameTab(self):
        self.tabWidget.setCurrentIndex(5)
