"""Settings class for ComicTagger app"""

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
import sys
import platform
import codecs
import uuid
import utils

try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        if config_path not in sys.path:
            sys.path.append(config_path)
        from configobj import ConfigObj
except ImportError:
        print "Unable to use configobj module. This is a CRITICAL error and ComicTagger cannot proceed. Exiting."

class ComicTaggerSettings:

    @staticmethod
    def getSettingsFolder():
        filename_encoding = sys.getfilesystemencoding()
        folder = os.path.join(ComicTaggerSettings.baseDir(), 'ct_settings')
        if folder is not None:
            folder = folder.decode(filename_encoding)
        return folder

    frozen_win_exe_path = None

    @staticmethod
    def baseDir():
        if getattr(sys, 'frozen', None):
            if platform.system() == "Darwin":
                return sys._MEIPASS
            else:  # Windows
                # Preserve this value, in case sys.argv gets changed importing
                # a plugin script
                if ComicTaggerSettings.frozen_win_exe_path is None:
                    ComicTaggerSettings.frozen_win_exe_path = os.path.dirname(
                        os.path.abspath(sys.argv[0]))
                return ComicTaggerSettings.frozen_win_exe_path
        else:
            return os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def getGraphic(filename):
        graphic_folder = os.path.join(
            ComicTaggerSettings.baseDir(), 'graphics')
        return os.path.join(graphic_folder, filename)

    @staticmethod
    def getUIFile(filename):
        ui_folder = os.path.join(ComicTaggerSettings.baseDir(), 'ui')
        return os.path.join(ui_folder, filename)

    def setDefaultValues(self):

        # General Settings
        self.rar_exe_path = ""
        self.unrar_exe_path = ""
        self.allow_cbi_in_rar = True
        self.check_for_new_version = True
        self.send_usage_stats = False

        # automatic settings
        self.install_id = uuid.uuid4().hex
        self.last_selected_save_data_style = 0
        self.last_selected_load_data_style = 0
        self.last_opened_folder = ""
        self.last_main_window_width = 0
        self.last_main_window_height = 0
        self.last_main_window_x = 0
        self.last_main_window_y = 0
        self.last_form_side_width = -1
        self.last_list_side_width = -1
        self.last_filelist_sorted_column = -1
        self.last_filelist_sorted_order = 0

        # identifier settings
        self.id_length_delta_thresh = 5
        self.id_publisher_blacklist = "Panini Comics, Abril, Planeta DeAgostini, Editorial Televisa"

        # Show/ask dialog flags
        self.ask_about_cbi_in_rar = True
        self.show_disclaimer = True
        self.dont_notify_about_this_version = ""
        self.ask_about_usage_stats = True
        self.show_no_unrar_warning = True

        # filename parsing settings
        self.parse_scan_info = True

        # Comic Vine settings
        self.use_series_start_as_volume = False
        self.clear_form_before_populating_from_cv = False
        self.remove_html_tables = False
        self.cv_api_key = ""

        # CBL Tranform settings

        self.assume_lone_credit_is_primary = False
        self.copy_characters_to_tags = False
        self.copy_teams_to_tags = False
        self.copy_locations_to_tags = False
        self.copy_storyarcs_to_tags = False
        self.copy_notes_to_comments = False
        self.copy_weblink_to_comments = False
        self.apply_cbl_transform_on_cv_import = False
        self.apply_cbl_transform_on_bulk_operation = False

        # Rename settings
        self.rename_template = "%series% #%issue% (%year%)"
        self.rename_issue_number_padding = 3
        self.rename_use_smart_string_cleanup = True
        self.rename_extension_based_on_archive = True

        # Auto-tag stickies
        self.save_on_low_confidence = False
        self.dont_use_year_when_identifying = False
        self.assume_1_if_no_issue_num = False
        self.ignore_leading_numbers_in_filename = False
        self.remove_archive_after_successful_match = False
        self.wait_and_retry_on_rate_limit = False

    def __init__(self):

        self.settings_file = ""
        self.folder = ""
        self.setDefaultValues()

        self.folder = ComicTaggerSettings.getSettingsFolder()

        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

        self.settings_file = os.path.join(self.folder, "settings.ini")
        self.CFG = ConfigObj(self.settings_file, encoding='utf-8')

        # if config file doesn't exist, write one out
        if not os.path.exists(self.settings_file):
            self.save()
        else:
            self.load()

        # take a crack at finding rar exes, if not set already
        if self.rar_exe_path == "":
            if platform.system() == "Windows":
                # look in some likely places for Windows machines
                if os.path.exists("C:\Program Files\WinRAR\Rar.exe"):
                    self.rar_exe_path = "C:\Program Files\WinRAR\Rar.exe"
                elif os.path.exists("C:\Program Files (x86)\WinRAR\Rar.exe"):
                    self.rar_exe_path = "C:\Program Files (x86)\WinRAR\Rar.exe"
            else:
                # see if it's in the path of unix user
                if utils.which("rar") is not None:
                    self.rar_exe_path = utils.which("rar")
            if self.rar_exe_path != "":
                self.save()

        if self.unrar_exe_path == "":
            if platform.system() != "Windows":
                # see if it's in the path of unix user
                if utils.which("unrar") is not None:
                    self.unrar_exe_path = utils.which("unrar")
            if self.unrar_exe_path != "":
                self.save()

        # make sure unrar/rar programs are now in the path for the UnRAR class to
        # use
        utils.addtopath(os.path.dirname(self.unrar_exe_path))
        utils.addtopath(os.path.dirname(self.rar_exe_path))

    def reset(self):
        os.unlink(self.settings_file)
        self.__init__()

    def CheckSection(self, sec):
        """ Check if INI section exists, if not create it """
        try:
            self.CFG[sec]
            return True
        except:
            self.CFG[sec] = {}
            return False

    ################################################################################
    # Check_setting_int                                                            #
    ################################################################################
    def check_setting_int(self, config, cfg_name, item_name, def_val):
        try:
            my_val = int(config[cfg_name][item_name])
        except:
            my_val = def_val
            try:
                config[cfg_name][item_name] = my_val
            except:
                config[cfg_name] = {}
                config[cfg_name][item_name] = my_val
        return my_val

    ################################################################################
    # Check_setting_str                                                            #
    ################################################################################
    def check_setting_str(self, config, cfg_name, item_name, def_val, log=True):
        try:
            my_val = config[cfg_name][item_name]
        except:
            my_val = def_val
            try:
                config[cfg_name][item_name] = my_val
            except:
                config[cfg_name] = {}
                config[cfg_name][item_name] = my_val

        return my_val

    def load(self):

        self.rar_exe_path = self.check_setting_str(self.CFG, 'settings', 'rar_exe_path', '')
        self.unrar_exe_path = self.check_setting_str(self.CFG, 'settings', 'unurar_exe_path', '')
        self.check_for_new_version = bool(self.check_setting_int(self.CFG, 'settings', 'check_for_new_version', 0))
	self.send_usage_stats = bool(self.check_setting_int(self.CFG, 'settings', 'send_usage_stats', 0))
	self.install_id = self.check_setting_str(self.CFG, 'auto', 'install_id', '')
	self.last_selected_load_data_style = self.check_setting_str(self.CFG, 'auto', 'last_selected_load_data_style', '')
	self.last_selected_save_data_style = self.check_setting_str(self.CFG, 'auto', 'last_selected_save_data_style', '')
	self.last_selected_save_data_style = self.check_setting_str(self.CFG, 'auto', 'last_selected_save_data_style', '')
	self.last_opened_folder = self.check_setting_str(self.CFG, 'auto', 'last_opened_folder', '')
	self.last_main_window_width = self.check_setting_str(self.CFG, 'auto', 'last_main_window_width', '')
	self.last_main_window_height = self.check_setting_str(self.CFG, 'auto', 'last_main_window_height', '')
	self.last_form_side_width = self.check_setting_str(self.CFG, 'auto', 'last_form_side_width', '')
	self.last_list_side_width = self.check_setting_str(self.CFG, 'auto', 'last_list_side_width', '')
	self.last_filelist_sorted_column = self.check_setting_str(self.CFG, 'auto', 'last_filelist_sorted_column', '')
	self.last_filelist_sorted_order = self.check_setting_str(self.CFG, 'auto', 'last_filelist_sorted_order', '')
	self.last_main_window_x = self.check_setting_str(self.CFG, 'auto', 'last_main_window_x', '')
	self.last_main_window_y = self.check_setting_str(self.CFG, 'auto', 'last_main_window_y','')
	self.last_form_side_width = self.check_setting_str(self.CFG, 'auto', 'last_form_side_width','')
	self.last_list_side_width = self.check_setting_str(self.CFG, 'auto', 'last_list_side_width','')
	self.id_length_delta_thresh = self.check_setting_str(self.CFG, 'identifier', 'id_length_delta_thresh', '')
	self.id_publisher_blacklist = self.check_setting_str(self.CFG, 'identifier', 'id_publisher_blacklist', '')

	self.parse_scan_info = bool(self.check_setting_int(self.CFG, 'filenameparser', 'parse_scan_info', 0))

	self.ask_about_cbi_in_rar = bool(self.check_setting_int(self.CFG,  'dialogflags', 'ask_about_cbi_in_rar', 0))
	self.show_disclaimer = bool(self.check_setting_int(self.CFG, 'dialogflags', 'show_disclaimer', 0))
	self.dont_notify_about_this_version = self.check_setting_str(self.CFG, 'dialogflags', 'dont_notify_about_this_version', '')
	self.ask_about_usage_stats = bool(self.check_setting_int(self.CFG, 'dialogflags', 'ask_about_usage_stats', 0))
	self.show_no_unrar_warning = bool(self.check_setting_int(self.CFG, 'dialogflags', 'show_no_unrar_warning', 0))

	self.use_series_start_as_volume = bool(self.check_setting_int(self.CFG, 'comicvine', 'use_series_start_as_volume', 0))
	self.clear_form_before_populating_from_cv = bool(self.check_setting_int(self.CFG, 'comicvine', 'clear_form_before_populating_from_cv', 0))
	self.remove_html_tables = bool(self.check_setting_int(self.CFG, 'comicvine', 'remove_html_tables', 0))
	self.cv_api_key = self.check_setting_str(self.CFG, 'comicvine', 'cv_api_key', '')

	self.assume_lone_credit_is_primary = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'assume_lone_credit_is_primary', 0))
	self.copy_characters_to_tags = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'copy_characters_to_tags', 0))
	self.copy_teams_to_tags = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'copy_teams_to_tags', 0))
	self.copy_locations_to_tags = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'copy_locations_to_tags', 0))
	self.copy_notes_to_comments = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'copy_notes_to_comments', 0))
	self.copy_storyarcs_to_tags = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'copy_storyarcs_to_tags', 0))
	self.copy_weblink_to_comments = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'copy_weblink_to_comments', 0))
	self.apply_cbl_transform_on_cv_import = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'apply_cbl_transform_on_cv_import', 0))
	self.apply_cbl_transform_on_bulk_operation = bool(self.check_setting_int(self.CFG, 'cbl_transform', 'apply_cbl_transform_on_bulk_operation', 0))

	self.rename_template = bool(self.check_setting_int(self.CFG, 'rename', 'rename_template', 0))
	self.rename_issue_number_padding = self.check_setting_str(self.CFG, 'rename', 'rename_issue_number_padding', '')
	self.rename_use_smart_string_cleanup = bool(self.check_setting_int(self.CFG, 'rename', 'rename_use_smart_string_cleanup', 0))
	self.rename_extension_based_on_archive = bool(self.check_setting_int(self.CFG, 'rename', 'rename_extension_based_on_archive', 0))

	self.save_on_low_confidence = bool(self.check_setting_int(self.CFG, 'autotag', 'save_on_low_confidence', 0))
	self.dont_use_year_when_identifying = bool(self.check_setting_int(self.CFG, 'autotag', 'dont_use_year_when_identifying', 0))
	self.assume_1_if_no_issue_num = bool(self.check_setting_int(self.CFG, 'autotag', 'assume_1_if_no_issue_num', 0))
	self.ignore_leading_numbers_in_filename = bool(self.check_setting_int(self.CFG, 'autotag', 'ignore_leading_numbers_in_filename', 0))
	self.remove_archive_after_successful_match = bool(self.check_setting_int(self.CFG, 'autotag', 'remove_archive_after_successful_match', 0))
	self.wait_and_retry_on_rate_limit = bool(self.check_setting_int(self.CFG, 'autotag', 'wait_and_retry_on_rate_limit', 0))

    def save(self):

        new_config = ConfigObj()
        new_config.filename = self.settings_file

        new_config.encoding = 'UTF8'
        new_config['settings'] = {}
        new_config['settings']['check_for_new_version'] = self.check_for_new_version
        new_config['settings']['rar_exe_path'] = self.rar_exe_path
        new_config['settings']['unrar_exe_path'] = self.unrar_exe_path
        new_config['settings']['send_usage_stats'] = self.send_usage_stats

        new_config.write()
        new_config['auto'] = {}
        new_config['auto']['install_id'] = self.install_id
        new_config['auto']['last_selected_load_data_style'] = self.last_selected_load_data_style
        new_config['auto']['last_selected_save_data_style'] = self.last_selected_save_data_style
        new_config['auto']['last_opened_folder'] = self.last_opened_folder
        new_config['auto']['last_main_window_width'] = self.last_main_window_width
        new_config['auto']['last_main_window_height'] = self.last_main_window_height
        new_config['auto']['last_main_window_x'] = self.last_main_window_x
        new_config['auto']['last_main_window_y'] = self.last_main_window_y
        new_config['auto']['last_form_side_width'] = self.last_form_side_width
        new_config['auto']['last_list_side_width'] = self.last_list_side_width
        new_config['auto']['last_filelist_sorted_column'] = self.last_filelist_sorted_column
        new_config['auto']['last_filelist_sorted_order'] = self.last_filelist_sorted_order

        new_config['identifier'] = {}
        new_config['identifier']['id_length_delta_thresh'] = self.id_length_delta_thresh
        new_config['identifier']['id_publisher_blacklist'] = self.id_publisher_blacklist

        new_config['dialogflags'] = {}
        new_config['dialogflags']['ask_about_cbi_in_rar'] = self.ask_about_cbi_in_rar
        new_config['dialogflags']['show_disclaimer'] = self.show_disclaimer
        new_config['dialogflags']['dont_notify_about_this_version'] = self.dont_notify_about_this_version
        new_config['dialogflags']['ask_about_usage_stats'] = self.ask_about_usage_stats
        new_config['dialogflags']['show_no_unrar_warning'] = self.show_no_unrar_warning

        new_config['filenameparser'] = {}
        new_config['filenameparser']['parse_scan_info'] = self.parse_scan_info

        new_config['comicvine'] = {}
        new_config['comicvine']['use_series_start_as_volume'] = self.use_series_start_as_volume
        new_config['comicvine']['clear_form_before_populating_from_cv'] = self.clear_form_before_populating_from_cv
        new_config['comicvine']['remove_html_tables'] = self.remove_html_tables
        new_config['comicvine']['cv_api_key'] = self.cv_api_key

        new_config['cbl_transform'] = {}
        new_config['cbl_transform']['assume_lone_credit_is_primary'] = self.assume_lone_credit_is_primary
        new_config['cbl_transform']['copy_characters_to_tags'] = self.copy_characters_to_tags
        new_config['cbl_transform']['copy_teams_to_tags'] = self.copy_teams_to_tags
        new_config['cbl_transform']['copy_locations_to_tags'] = self.copy_locations_to_tags
        new_config['cbl_transform']['copy_storyarcs_to_tags'] = self.copy_storyarcs_to_tags
        new_config['cbl_transform']['copy_notes_to_comments'] = self.copy_notes_to_comments
        new_config['cbl_transform']['copy_weblink_to_comments'] = self.copy_weblink_to_comments
        new_config['cbl_transform']['apply_cbl_transform_on_cv_import'] = self.apply_cbl_transform_on_cv_import
        new_config['cbl_transform']['apply_cbl_transform_on_bulk_operation'] = self.apply_cbl_transform_on_bulk_operation

        new_config['rename'] = {}
        new_config['rename']['rename_template'] = self.rename_template
        new_config['rename']['rename_issue_number_padding'] = self.rename_issue_number_padding
        new_config['rename']['rename_use_smart_string_cleanup'] = self.rename_use_smart_string_cleanup
        new_config['rename']['rename_extension_based_on_archive'] = self.rename_extension_based_on_archive

        new_config['autotag'] = {}
        new_config['autotag']['save_on_low_confidence'] = self.save_on_low_confidence
        new_config['autotag']['dont_use_year_when_identifying'] = self.dont_use_year_when_identifying
        new_config['autotag']['assume_1_if_no_issue_num'] = self.assume_1_if_no_issue_num
        new_config['autotag']['ignore_leading_numbers_in_filename'] = self.ignore_leading_numbers_in_filename
        new_config['autotag']['remove_archive_after_successful_match'] = self.remove_archive_after_successful_match
        new_config['autotag']['wait_and_retry_on_rate_limit'] = self.wait_and_retry_on_rate_limit

# make sure the basedir is cached, in case we're on Windows running a
# script from frozen binary
ComicTaggerSettings.baseDir()
