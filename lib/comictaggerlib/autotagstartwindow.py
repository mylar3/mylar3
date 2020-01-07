"""A PyQT4 dialog to confirm and set options for auto-tag"""

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


class AutoTagStartWindow(QtWidgets.QDialog):

    def __init__(self, parent, settings, msg):
        super(AutoTagStartWindow, self).__init__(parent)

        uic.loadUi(
            ComicTaggerSettings.getUIFile('autotagstartwindow.ui'), self)
        self.label.setText(msg)

        self.setWindowFlags(self.windowFlags() &
                            ~QtCore.Qt.WindowContextHelpButtonHint)

        self.settings = settings

        self.cbxSaveOnLowConfidence.setCheckState(QtCore.Qt.Unchecked)
        self.cbxDontUseYear.setCheckState(QtCore.Qt.Unchecked)
        self.cbxAssumeIssueOne.setCheckState(QtCore.Qt.Unchecked)
        self.cbxIgnoreLeadingDigitsInFilename.setCheckState(
            QtCore.Qt.Unchecked)
        self.cbxRemoveAfterSuccess.setCheckState(QtCore.Qt.Unchecked)
        self.cbxSpecifySearchString.setCheckState(QtCore.Qt.Unchecked)
        self.leNameLengthMatchTolerance.setText(
            str(self.settings.id_length_delta_thresh))
        self.leSearchString.setEnabled(False)

        if self.settings.save_on_low_confidence:
            self.cbxSaveOnLowConfidence.setCheckState(QtCore.Qt.Checked)
        if self.settings.dont_use_year_when_identifying:
            self.cbxDontUseYear.setCheckState(QtCore.Qt.Checked)
        if self.settings.assume_1_if_no_issue_num:
            self.cbxAssumeIssueOne.setCheckState(QtCore.Qt.Checked)
        if self.settings.ignore_leading_numbers_in_filename:
            self.cbxIgnoreLeadingDigitsInFilename.setCheckState(
                QtCore.Qt.Checked)
        if self.settings.remove_archive_after_successful_match:
            self.cbxRemoveAfterSuccess.setCheckState(QtCore.Qt.Checked)
        if self.settings.wait_and_retry_on_rate_limit:
            self.cbxWaitForRateLimit.setCheckState(QtCore.Qt.Checked)

        nlmtTip = (
            """ <html>The <b>Name Length Match Tolerance</b> is for eliminating automatic
                search matches that are too long compared to your series name search. The higher
                it is, the more likely to have a good match, but each search will take longer and
                use more bandwidth. Too low, and only the very closest lexical matches will be
                explored.</html>""")

        self.leNameLengthMatchTolerance.setToolTip(nlmtTip)

        ssTip = (
            """<html>
            The <b>series search string</b> specifies the search string to be used for all selected archives.
            Use this when trying to match archives with hard-to-parse or incorrect filenames.  All archives selected
            should be from the same series.
            </html>"""
        )
        self.leSearchString.setToolTip(ssTip)
        self.cbxSpecifySearchString.setToolTip(ssTip)

        validator = QtGui.QIntValidator(0, 99, self)
        self.leNameLengthMatchTolerance.setValidator(validator)

        self.cbxSpecifySearchString.stateChanged.connect(
            self.searchStringToggle)

        self.autoSaveOnLow = False
        self.dontUseYear = False
        self.assumeIssueOne = False
        self.ignoreLeadingDigitsInFilename = False
        self.removeAfterSuccess = False
        self.waitAndRetryOnRateLimit = False
        self.searchString = None
        self.nameLengthMatchTolerance = self.settings.id_length_delta_thresh

    def searchStringToggle(self):
        enable = self.cbxSpecifySearchString.isChecked()
        self.leSearchString.setEnabled(enable)

    def accept(self):
        QtWidgets.QDialog.accept(self)

        self.autoSaveOnLow = self.cbxSaveOnLowConfidence.isChecked()
        self.dontUseYear = self.cbxDontUseYear.isChecked()
        self.assumeIssueOne = self.cbxAssumeIssueOne.isChecked()
        self.ignoreLeadingDigitsInFilename = self.cbxIgnoreLeadingDigitsInFilename.isChecked()
        self.removeAfterSuccess = self.cbxRemoveAfterSuccess.isChecked()
        self.nameLengthMatchTolerance = int(
            self.leNameLengthMatchTolerance.text())
        self.waitAndRetryOnRateLimit = self.cbxWaitForRateLimit.isChecked()

        # persist some settings
        self.settings.save_on_low_confidence = self.autoSaveOnLow
        self.settings.dont_use_year_when_identifying = self.dontUseYear
        self.settings.assume_1_if_no_issue_num = self.assumeIssueOne
        self.settings.ignore_leading_numbers_in_filename = self.ignoreLeadingDigitsInFilename
        self.settings.remove_archive_after_successful_match = self.removeAfterSuccess
        self.settings.wait_and_retry_on_rate_limit = self.waitAndRetryOnRateLimit

        if self.cbxSpecifySearchString.isChecked():
            self.searchString = str(self.leSearchString.text())
            if len(self.searchString) == 0:
                self.searchString = None
