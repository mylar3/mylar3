#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  This file is part of Mylar.
#
#  Mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mylar is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement

import os, sys, subprocess

import threading
import datetime
import webbrowser
import sqlite3
import itertools
import csv
import shutil
import Queue
import platform
import locale
import re
from threading import Lock, Thread

from lib.apscheduler.scheduler import Scheduler
from lib.configobj import ConfigObj

import cherrypy

from mylar import logger, versioncheckit, rsscheckit, searchit, weeklypullit, dbupdater, PostProcessor, helpers, scheduler #versioncheck, rsscheck, search, PostProcessor, weeklypull, helpers, scheduler

FULL_PATH = None
PROG_DIR = None

ARGS = None
SIGNAL = None

SYS_ENCODING = None
OS_DETECT = platform.system()

VERBOSE = False
DAEMON = False
PIDFILE= None
CREATEPID = False
SAFESTART = False
AUTO_UPDATE = False

SCHED = Scheduler()

INIT_LOCK = threading.Lock()
__INITIALIZED__ = False
started = False
WRITELOCK = False
LOGTYPE = None
IMPORTLOCK = False

## for use with updated scheduler (not working atm)
INIT_LOCK = Lock()
dbUpdateScheduler = None
searchScheduler = None
RSSScheduler = None
WeeklyScheduler = None
VersionScheduler = None
FolderMonitorScheduler = None

QUEUE = Queue.Queue()

DATA_DIR = None
DBLOCK = False

UMASK = None

CONFIG_FILE = None
CFG = None
CONFIG_VERSION = None

DB_FILE = None
DBCHOICE = None

#these are used depending on dbchoice.
DBUSER = None
DBPASS = None
DBNAME = None

LOG_DIR = None
LOG_LIST = []
MAX_LOGSIZE = None
QUIET = False

CACHE_DIR = None
SYNO_FIX = False
IMPORTBUTTON = False
DONATEBUTTON = True

PULLNEW = None
ALT_PULL = False

LOCAL_IP = None
EXT_IP = None
HTTP_PORT = None
HTTP_HOST = None
HTTP_USERNAME = None
HTTP_PASSWORD = None
HTTP_ROOT = None
ENABLE_HTTPS = False
HTTPS_CERT = None
HTTPS_KEY = None
HTTPS_FORCE_ON = False
HOST_RETURN = None
API_ENABLED = False
API_KEY = None
DOWNLOAD_APIKEY = None
LAUNCH_BROWSER = False
GIT_PATH = None
INSTALL_TYPE = None
CURRENT_VERSION = None
LATEST_VERSION = None
COMMITS_BEHIND = None
GIT_USER = 'evilhero'
GIT_BRANCH = None
USER_AGENT = None
SEARCH_DELAY = 1

COMICVINE_API = None
DEFAULT_CVAPI = '583939a3df0a25fc4e8b7a29934a13078002dc27'
CVAPI_RATE = 2
CV_HEADERS = None

CHECK_GITHUB = False
CHECK_GITHUB_ON_STARTUP = False
CHECK_GITHUB_INTERVAL = None

DESTINATION_DIR = None   #if M_D_D_ is enabled, this will be the DEFAULT for writing
MULTIPLE_DEST_DIRS = None  #Nothing will ever get written to these dirs - just for scanning, unless it's metatagging/renaming.
CHMOD_DIR = None
CHMOD_FILE = None
CHOWNER = None
CHGROUP = None
USENET_RETENTION = None
CREATE_FOLDERS = True
DELETE_REMOVE_DIR = False

ADD_COMICS = False
COMIC_DIR = None
IMP_MOVE = False
IMP_RENAME = False
IMP_METADATA = True  # should default to False - this is enabled for testing only.

SEARCH_INTERVAL = 360
NZB_STARTUP_SEARCH = False
DOWNLOAD_SCAN_INTERVAL = 5
FOLDER_SCAN_LOG_VERBOSE = 0
CHECK_FOLDER = None
ENABLE_CHECK_FOLDER = False
INTERFACE = None
DUPECONSTRAINT = None
DDUMP = 0
DUPLICATE_DUMP = None
PREFERRED_QUALITY = 0
CORRECT_METADATA = False
MOVE_FILES = False
RENAME_FILES = False
FOLDER_FORMAT = None
FILE_FORMAT = None
REPLACE_SPACES = False
REPLACE_CHAR = None
ZERO_LEVEL = False
ZERO_LEVEL_N = None
LOWERCASE_FILENAME = False
IGNORE_HAVETOTAL = False
SNATCHED_HAVETOTAL = False
USE_MINSIZE = False
MINSIZE = 10
USE_MAXSIZE = False
MAXSIZE = 60
AUTOWANT_UPCOMING = True
AUTOWANT_ALL = False
COMIC_COVER_LOCAL = False
ADD_TO_CSV = True
PROWL_ENABLED = False
PROWL_PRIORITY = 1
PROWL_KEYS = None
PROWL_ONSNATCH = False
NMA_ENABLED = False
NMA_APIKEY = None
NMA_PRIORITY = None
NMA_ONSNATCH = False
PUSHOVER_ENABLED = False
PUSHOVER_PRIORITY = 1
PUSHOVER_APIKEY = None
PUSHOVER_USERKEY = None
PUSHOVER_ONSNATCH = False
BOXCAR_ENABLED = False
BOXCAR_ONSNATCH = False
BOXCAR_TOKEN = None
PUSHBULLET_ENABLED = False
PUSHBULLET_APIKEY = None
PUSHBULLET_DEVICEID = None
PUSHBULLET_ONSNATCH = False

SKIPPED2WANTED = False
CVINFO = False
LOG_LEVEL = None
POST_PROCESSING = 1
POST_PROCESSING_SCRIPT = None
FILE_OPTS = None

NZB_DOWNLOADER = None  #0 = sabnzbd, #1 = nzbget, #2 = blackhole

USE_SABNZBD = False
SAB_HOST = None
SAB_USERNAME = None
SAB_PASSWORD = None
SAB_APIKEY = None
SAB_CATEGORY = None
SAB_PRIORITY = None
SAB_TO_MYLAR = False
SAB_DIRECTORY = None

USE_NZBGET = False
NZBGET_HOST = None
NZBGET_PORT = None
NZBGET_USERNAME = None
NZBGET_PASSWORD = None
NZBGET_PRIORITY = None
NZBGET_CATEGORY = None
NZBGET_DIRECTORY = None

USE_BLACKHOLE = False
BLACKHOLE_DIR = None

PROVIDER_ORDER = None

NZBSU = False
NZBSU_UID = None
NZBSU_APIKEY = None
NZBSU_VERIFY = True

DOGNZB = False
DOGNZB_APIKEY = None
DOGNZB_VERIFY = True

NEWZNAB = False
NEWZNAB_NAME = None
NEWZNAB_HOST = None
NEWZNAB_APIKEY = None
NEWZNAB_VERIFY = True
NEWZNAB_UID = None
NEWZNAB_ENABLED = False
EXTRA_NEWZNABS = []
NEWZNAB_EXTRA = None

ENABLE_TORZNAB = False
TORZNAB_NAME = None
TORZNAB_HOST = None
TORZNAB_APIKEY = None
TORZNAB_CATEGORY = None
TORZNAB_VERIFY = False

EXPERIMENTAL = False
ALTEXPERIMENTAL = False

COMIC_LOCATION = None
QUAL_ALTVERS = None
QUAL_SCANNER = None
QUAL_TYPE = None
QUAL_QUALITY = None

ENABLE_EXTRA_SCRIPTS = 1
EXTRA_SCRIPTS = None

ENABLE_PRE_SCRIPTS = 1
PRE_SCRIPTS = None

COUNT_COMICS = 0
COUNT_ISSUES = 0
COUNT_HAVES = 0

COMICSORT = None
ANNUALS_ON = 0
CV_ONLY = 1
CV_ONETIMER = 1
GRABBAG_DIR = None
HIGHCOUNT = 0
READ2FILENAME = 0
SEND2READ = 0
TAB_ENABLE = 0
TAB_HOST = None
TAB_USER = None
TAB_PASS = None
TAB_DIRECTORY = None
STORYARCDIR = 0
COPY2ARCDIR = 0

CVURL = None
WEEKFOLDER = 0
WEEKFOLDER_LOC = None
LOCMOVE = 0
NEWCOM_DIR = None
FFTONEWCOM_DIR = 0
OLDCONFIG_VERSION = None
UPDATE_ENDED = 0

INDIE_PUB = 75
BIGGIE_PUB = 55

ENABLE_META = 0
CMTAGGER_PATH = None
CBR2CBZ_ONLY = 0
CT_TAG_CR = 1
CT_TAG_CBL = 1
CT_CBZ_OVERWRITE = 0
UNRAR_CMD = None
CT_SETTINGSPATH = None

UPCOMING_SNATCHED = 1

ENABLE_RSS = 0
RSS_CHECKINTERVAL = 20
RSS_LASTRUN = None

#these are used to set the comparison against the post-processing scripts
STATIC_COMICRN_VERSION = "1.01"
STATIC_APC_VERSION = "1.0"

FAILED_DOWNLOAD_HANDLING = 0
FAILED_AUTO = 0

ENABLE_TORRENTS = 0
MINSEEDS = 0
TORRENT_LOCAL = 0
LOCAL_WATCHDIR = None
TORRENT_SEEDBOX = 0
SEEDBOX_HOST = None
SEEDBOX_PORT = None
SEEDBOX_USER = None
SEEDBOX_PASS = None
SEEDBOX_WATCHDIR = None

ENABLE_TORRENT_SEARCH = 0
ENABLE_KAT = 0
KAT_PROXY = None
KAT_VERIFY = True

ENABLE_32P = 0
MODE_32P = None  #0 = legacymode, #1 = authmode
KEYS_32P = None
RSSFEED_32P = None
PASSKEY_32P = None
USERNAME_32P = None
PASSWORD_32P = None
AUTHKEY_32P = None
FEEDINFO_32P = None
VERIFY_32P = 1
SNATCHEDTORRENT_NOTIFY = 0

def CheckSection(sec):
    """ Check if INI section exists, if not create it """
    try:
        CFG[sec]
        return True
    except:
        CFG[sec] = {}
        return False

################################################################################
# Check_setting_int                                                            #
################################################################################
def check_setting_int(config, cfg_name, item_name, def_val):
    try:
        my_val = int(config[cfg_name][item_name])
    except:
        my_val = def_val
        try:
            config[cfg_name][item_name] = my_val
        except:
            config[cfg_name] = {}
            config[cfg_name][item_name] = my_val
    logger.debug(item_name + " -> " + str(my_val))
    return my_val

################################################################################
# Check_setting_str                                                            #
################################################################################
def check_setting_str(config, cfg_name, item_name, def_val, log=True):
    try:
        my_val = config[cfg_name][item_name]
    except:
        my_val = def_val
        try:
            config[cfg_name][item_name] = my_val
        except:
            config[cfg_name] = {}
            config[cfg_name][item_name] = my_val

    if log:
        logger.debug(item_name + " -> " + my_val)
    else:
        logger.debug(item_name + " -> ******")
    return my_val


def initialize():

    with INIT_LOCK:
        global __INITIALIZED__, DBCHOICE, DBUSER, DBPASS, DBNAME, COMICVINE_API, DEFAULT_CVAPI, CVAPI_RATE, CV_HEADERS, FULL_PATH, PROG_DIR, VERBOSE, DAEMON, UPCOMING_SNATCHED, COMICSORT, DATA_DIR, CONFIG_FILE, CFG, CONFIG_VERSION, LOG_DIR, CACHE_DIR, MAX_LOGSIZE, OLDCONFIG_VERSION, OS_DETECT, \
                queue, LOCAL_IP, EXT_IP, HTTP_PORT, HTTP_HOST, HTTP_USERNAME, HTTP_PASSWORD, HTTP_ROOT, ENABLE_HTTPS, HTTPS_CERT, HTTPS_KEY, HTTPS_FORCE_ON, HOST_RETURN, API_ENABLED, API_KEY, DOWNLOAD_APIKEY, LAUNCH_BROWSER, GIT_PATH, SAFESTART, AUTO_UPDATE, \
                CURRENT_VERSION, LATEST_VERSION, CHECK_GITHUB, CHECK_GITHUB_ON_STARTUP, CHECK_GITHUB_INTERVAL, GIT_USER, GIT_BRANCH, USER_AGENT, DESTINATION_DIR, MULTIPLE_DEST_DIRS, CREATE_FOLDERS, DELETE_REMOVE_DIR, \
                DOWNLOAD_DIR, USENET_RETENTION, SEARCH_INTERVAL, NZB_STARTUP_SEARCH, INTERFACE, DUPECONSTRAINT, DDUMP, DUPLICATE_DUMP, AUTOWANT_ALL, AUTOWANT_UPCOMING, ZERO_LEVEL, ZERO_LEVEL_N, COMIC_COVER_LOCAL, HIGHCOUNT, \
                DOWNLOAD_SCAN_INTERVAL, FOLDER_SCAN_LOG_VERBOSE, IMPORTLOCK, NZB_DOWNLOADER, USE_SABNZBD, SAB_HOST, SAB_USERNAME, SAB_PASSWORD, SAB_APIKEY, SAB_CATEGORY, SAB_PRIORITY, SAB_TO_MYLAR, SAB_DIRECTORY, USE_BLACKHOLE, BLACKHOLE_DIR, ADD_COMICS, COMIC_DIR, IMP_MOVE, IMP_RENAME, IMP_METADATA, \
                USE_NZBGET, NZBGET_HOST, NZBGET_PORT, NZBGET_USERNAME, NZBGET_PASSWORD, NZBGET_CATEGORY, NZBGET_PRIORITY, NZBGET_DIRECTORY, NZBSU, NZBSU_UID, NZBSU_APIKEY, NZBSU_VERIFY, DOGNZB, DOGNZB_APIKEY, DOGNZB_VERIFY, \
                NEWZNAB, NEWZNAB_NAME, NEWZNAB_HOST, NEWZNAB_APIKEY, NEWZNAB_VERIFY, NEWZNAB_UID, NEWZNAB_ENABLED, EXTRA_NEWZNABS, NEWZNAB_EXTRA, \
                ENABLE_TORZNAB, TORZNAB_NAME, TORZNAB_HOST, TORZNAB_APIKEY, TORZNAB_CATEGORY, TORZNAB_VERIFY, \
                EXPERIMENTAL, ALTEXPERIMENTAL, \
                ENABLE_META, CMTAGGER_PATH, CBR2CBZ_ONLY, CT_TAG_CR, CT_TAG_CBL, CT_CBZ_OVERWRITE, UNRAR_CMD, CT_SETTINGSPATH, UPDATE_ENDED, INDIE_PUB, BIGGIE_PUB, IGNORE_HAVETOTAL, SNATCHED_HAVETOTAL, PROVIDER_ORDER, \
                dbUpdateScheduler, searchScheduler, RSSScheduler, WeeklyScheduler, VersionScheduler, FolderMonitorScheduler, \
                ENABLE_TORRENTS, MINSEEDS, TORRENT_LOCAL, LOCAL_WATCHDIR, TORRENT_SEEDBOX, SEEDBOX_HOST, SEEDBOX_PORT, SEEDBOX_USER, SEEDBOX_PASS, SEEDBOX_WATCHDIR, \
                ENABLE_RSS, RSS_CHECKINTERVAL, RSS_LASTRUN, FAILED_DOWNLOAD_HANDLING, FAILED_AUTO, ENABLE_TORRENT_SEARCH, ENABLE_KAT, KAT_PROXY, KAT_VERIFY, ENABLE_32P, MODE_32P, KEYS_32P, RSSFEED_32P, USERNAME_32P, PASSWORD_32P, AUTHKEY_32P, PASSKEY_32P, FEEDINFO_32P, VERIFY_32P, SNATCHEDTORRENT_NOTIFY, \
                PROWL_ENABLED, PROWL_PRIORITY, PROWL_KEYS, PROWL_ONSNATCH, NMA_ENABLED, NMA_APIKEY, NMA_PRIORITY, NMA_ONSNATCH, PUSHOVER_ENABLED, PUSHOVER_PRIORITY, PUSHOVER_APIKEY, PUSHOVER_USERKEY, PUSHOVER_ONSNATCH, BOXCAR_ENABLED, BOXCAR_ONSNATCH, BOXCAR_TOKEN, \
                PUSHBULLET_ENABLED, PUSHBULLET_APIKEY, PUSHBULLET_DEVICEID, PUSHBULLET_ONSNATCH, LOCMOVE, NEWCOM_DIR, FFTONEWCOM_DIR, \
                PREFERRED_QUALITY, MOVE_FILES, RENAME_FILES, LOWERCASE_FILENAMES, USE_MINSIZE, MINSIZE, USE_MAXSIZE, MAXSIZE, CORRECT_METADATA, FOLDER_FORMAT, FILE_FORMAT, REPLACE_CHAR, REPLACE_SPACES, ADD_TO_CSV, CVINFO, LOG_LEVEL, POST_PROCESSING, POST_PROCESSING_SCRIPT, FILE_OPTS, SEARCH_DELAY, GRABBAG_DIR, READ2FILENAME, SEND2READ, TAB_ENABLE, TAB_HOST, TAB_USER, TAB_PASS, TAB_DIRECTORY, STORYARCDIR, COPY2ARCDIR, CVURL, CHECK_FOLDER, ENABLE_CHECK_FOLDER, \
                COMIC_LOCATION, QUAL_ALTVERS, QUAL_SCANNER, QUAL_TYPE, QUAL_QUALITY, ENABLE_EXTRA_SCRIPTS, EXTRA_SCRIPTS, ENABLE_PRE_SCRIPTS, PRE_SCRIPTS, PULLNEW, ALT_PULL, COUNT_ISSUES, COUNT_HAVES, COUNT_COMICS, SYNO_FIX, CHMOD_FILE, CHMOD_DIR, CHOWNER, CHGROUP, ANNUALS_ON, CV_ONLY, CV_ONETIMER, WEEKFOLDER, WEEKFOLDER_LOC, UMASK

        if __INITIALIZED__:
            return False

        # Make sure all the config sections exist
        CheckSection('General')
        CheckSection('SABnzbd')
        CheckSection('NZBGet')
        CheckSection('NZBsu')
        CheckSection('DOGnzb')
        CheckSection('Experimental')
        CheckSection('Newznab')
        CheckSection('Torznab')
        CheckSection('Torrents')
        # Set global variables based on config file or use defaults
        try:
            HTTP_PORT = check_setting_int(CFG, 'General', 'http_port', 8090)
        except:
            HTTP_PORT = 8090

        if HTTP_PORT < 21 or HTTP_PORT > 65535:
            HTTP_PORT = 8090

        if HTTPS_CERT == '':
            HTTPS_CERT = os.path.join(DATA_DIR, 'server.crt')
        if HTTPS_KEY == '':
            HTTPS_KEY = os.path.join(DATA_DIR, 'server.key')

        CONFIG_VERSION = check_setting_str(CFG, 'General', 'config_version', '')
        DBCHOICE = check_setting_str(CFG, 'General', 'dbchoice', 'sqlite3')
        DBUSER = check_setting_str(CFG, 'General', 'dbuser', '')
        DBPASS = check_setting_str(CFG, 'General', 'dbpass', '')
        DBNAME = check_setting_str(CFG, 'General', 'dbname', '')

        COMICVINE_API = check_setting_str(CFG, 'General', 'comicvine_api', '')
        if not COMICVINE_API:
            COMICVINE_API = None
        CVAPI_RATE = check_setting_int(CFG, 'General', 'cvapi_rate', 2)
        HTTP_HOST = check_setting_str(CFG, 'General', 'http_host', '0.0.0.0')
        HTTP_USERNAME = check_setting_str(CFG, 'General', 'http_username', '')
        HTTP_PASSWORD = check_setting_str(CFG, 'General', 'http_password', '')
        HTTP_ROOT = check_setting_str(CFG, 'General', 'http_root', '/')
        ENABLE_HTTPS = bool(check_setting_int(CFG, 'General', 'enable_https', 0))
        HTTPS_CERT = check_setting_str(CFG, 'General', 'https_cert', '')
        HTTPS_KEY = check_setting_str(CFG, 'General', 'https_key', '')
        HTTPS_FORCE_ON = bool(check_setting_int(CFG, 'General', 'https_force_on', 0))
        HOST_RETURN = check_setting_str(CFG, 'General', 'host_return', '')
        API_ENABLED = bool(check_setting_int(CFG, 'General', 'api_enabled', 0))
        API_KEY = check_setting_str(CFG, 'General', 'api_key', '')
        LAUNCH_BROWSER = bool(check_setting_int(CFG, 'General', 'launch_browser', 1))
        AUTO_UPDATE = bool(check_setting_int(CFG, 'General', 'auto_update', 0))
        MAX_LOGSIZE = check_setting_int(CFG, 'General', 'max_logsize', 1000000)
        if not MAX_LOGSIZE:
            MAX_LOGSIZE = 1000000
        GIT_PATH = check_setting_str(CFG, 'General', 'git_path', '')
        LOG_DIR = check_setting_str(CFG, 'General', 'log_dir', '')
        CACHE_DIR = check_setting_str(CFG, 'General', 'cache_dir', '')

        CHECK_GITHUB = bool(check_setting_int(CFG, 'General', 'check_github', 1))
        CHECK_GITHUB_ON_STARTUP = bool(check_setting_int(CFG, 'General', 'check_github_on_startup', 1))
        CHECK_GITHUB_INTERVAL = check_setting_int(CFG, 'General', 'check_github_interval', 360)
        GIT_USER = check_setting_str(CFG, 'General', 'git_user', 'evilhero')

        DESTINATION_DIR = check_setting_str(CFG, 'General', 'destination_dir', '')
        MULTIPLE_DEST_DIRS = check_setting_str(CFG, 'General', 'multiple_dest_dirs', '')
        CREATE_FOLDERS = bool(check_setting_int(CFG, 'General', 'create_folders', 1))
        DELETE_REMOVE_DIR = bool(check_setting_int(CFG, 'General', 'delete_remove_dir', 0))
        CHMOD_DIR = check_setting_str(CFG, 'General', 'chmod_dir', '0777')
        CHMOD_FILE = check_setting_str(CFG, 'General', 'chmod_file', '0660')
        CHOWNER = check_setting_str(CFG, 'General', 'chowner', '')
        CHGROUP = check_setting_str(CFG, 'General', 'chgroup', '')
        USENET_RETENTION = check_setting_int(CFG, 'General', 'usenet_retention', '1500')
        ALT_PULL = bool(check_setting_int(CFG, 'General', 'alt_pull', 0))
        SEARCH_INTERVAL = check_setting_int(CFG, 'General', 'search_interval', 360)
        NZB_STARTUP_SEARCH = bool(check_setting_int(CFG, 'General', 'nzb_startup_search', 0))
        ADD_COMICS = bool(check_setting_int(CFG, 'General', 'add_comics', 0))
        COMIC_DIR = check_setting_str(CFG, 'General', 'comic_dir', '')
        IMP_MOVE = bool(check_setting_int(CFG, 'General', 'imp_move', 0))
        IMP_RENAME = bool(check_setting_int(CFG, 'General', 'imp_rename', 0))
        IMP_METADATA = bool(check_setting_int(CFG, 'General', 'imp_metadata', 0))
        DOWNLOAD_SCAN_INTERVAL = check_setting_int(CFG, 'General', 'download_scan_interval', 5)
        FOLDER_SCAN_LOG_VERBOSE = check_setting_int(CFG, 'General', 'folder_scan_log_verbose', 0)
        CHECK_FOLDER = check_setting_str(CFG, 'General', 'check_folder', '')
        ENABLE_CHECK_FOLDER = bool(check_setting_int(CFG, 'General', 'enable_check_folder', 0))
        INTERFACE = check_setting_str(CFG, 'General', 'interface', 'default')
        DUPECONSTRAINT = check_setting_str(CFG, 'General', 'dupeconstraint', 'filesize')
        DDUMP = bool(check_setting_int(CFG, 'General', 'ddump', 0))
        DUPLICATE_DUMP = check_setting_str(CFG, 'General', 'duplicate_dump', '')
        AUTOWANT_ALL = bool(check_setting_int(CFG, 'General', 'autowant_all', 0))
        AUTOWANT_UPCOMING = bool(check_setting_int(CFG, 'General', 'autowant_upcoming', 1))
        COMIC_COVER_LOCAL = bool(check_setting_int(CFG, 'General', 'comic_cover_local', 0))
        PREFERRED_QUALITY = check_setting_int(CFG, 'General', 'preferred_quality', 0)
        CORRECT_METADATA = bool(check_setting_int(CFG, 'General', 'correct_metadata', 0))
        MOVE_FILES = bool(check_setting_int(CFG, 'General', 'move_files', 0))
        RENAME_FILES = bool(check_setting_int(CFG, 'General', 'rename_files', 0))
        FOLDER_FORMAT = check_setting_str(CFG, 'General', 'folder_format', '$Series ($Year)')
        FILE_FORMAT = check_setting_str(CFG, 'General', 'file_format', '$Series $Issue ($Year)')
        USE_BLACKHOLE = bool(check_setting_int(CFG, 'General', 'use_blackhole', 0))
        BLACKHOLE_DIR = check_setting_str(CFG, 'General', 'blackhole_dir', '')
        REPLACE_SPACES = bool(check_setting_int(CFG, 'General', 'replace_spaces', 0))
        REPLACE_CHAR = check_setting_str(CFG, 'General', 'replace_char', '')
        ZERO_LEVEL = bool(check_setting_int(CFG, 'General', 'zero_level', 0))
        ZERO_LEVEL_N = check_setting_str(CFG, 'General', 'zero_level_n', '')
        LOWERCASE_FILENAMES = bool(check_setting_int(CFG, 'General', 'lowercase_filenames', 0))
        IGNORE_HAVETOTAL = bool(check_setting_int(CFG, 'General', 'ignore_havetotal', 0))
        SNATCHED_HAVETOTAL = bool(check_setting_int(CFG, 'General', 'snatched_havetotal', 0))
        SYNO_FIX = bool(check_setting_int(CFG, 'General', 'syno_fix', 0))
        SEARCH_DELAY = check_setting_int(CFG, 'General', 'search_delay', 1)
        GRABBAG_DIR = check_setting_str(CFG, 'General', 'grabbag_dir', '')
        if not GRABBAG_DIR:
            #default to ComicLocation
            GRABBAG_DIR = DESTINATION_DIR
        WEEKFOLDER = bool(check_setting_int(CFG, 'General', 'weekfolder', 0))
        WEEKFOLDER_LOC = check_setting_str(CFG, 'General', 'weekfolder_loc', '')
        LOCMOVE = bool(check_setting_int(CFG, 'General', 'locmove', 0))
        if LOCMOVE is None:
            LOCMOVE = 0
        NEWCOM_DIR = check_setting_str(CFG, 'General', 'newcom_dir', '')
        FFTONEWCOM_DIR = bool(check_setting_int(CFG, 'General', 'fftonewcom_dir', 0))
        if FFTONEWCOM_DIR is None:
            FFTONEWCOM_DIR = 0
        HIGHCOUNT = check_setting_str(CFG, 'General', 'highcount', '')
        if not HIGHCOUNT: HIGHCOUNT = 0
        READ2FILENAME = bool(check_setting_int(CFG, 'General', 'read2filename', 0))
        SEND2READ = bool(check_setting_int(CFG, 'General', 'send2read', 0))
        TAB_ENABLE = bool(check_setting_int(CFG, 'General', 'tab_enable', 0))
        TAB_HOST = check_setting_str(CFG, 'General', 'tab_host', '')
        TAB_USER = check_setting_str(CFG, 'General', 'tab_user', '')
        TAB_PASS = check_setting_str(CFG, 'General', 'tab_pass', '')
        TAB_DIRECTORY = check_setting_str(CFG, 'General', 'tab_directory', '')
        STORYARCDIR = bool(check_setting_int(CFG, 'General', 'storyarcdir', 0))
        COPY2ARCDIR = bool(check_setting_int(CFG, 'General', 'copy2arcdir', 0))
        PROWL_ENABLED = bool(check_setting_int(CFG, 'Prowl', 'prowl_enabled', 0))
        PROWL_KEYS = check_setting_str(CFG, 'Prowl', 'prowl_keys', '')
        PROWL_ONSNATCH = bool(check_setting_int(CFG, 'Prowl', 'prowl_onsnatch', 0))
        PROWL_PRIORITY = check_setting_int(CFG, 'Prowl', 'prowl_priority', 0)

        NMA_ENABLED = bool(check_setting_int(CFG, 'NMA', 'nma_enabled', 0))
        NMA_APIKEY = check_setting_str(CFG, 'NMA', 'nma_apikey', '')
        NMA_PRIORITY = check_setting_int(CFG, 'NMA', 'nma_priority', 0)
        NMA_ONSNATCH = bool(check_setting_int(CFG, 'NMA', 'nma_onsnatch', 0))

        PUSHOVER_ENABLED = bool(check_setting_int(CFG, 'PUSHOVER', 'pushover_enabled', 0))
        PUSHOVER_APIKEY = check_setting_str(CFG, 'PUSHOVER', 'pushover_apikey', '')
        PUSHOVER_USERKEY = check_setting_str(CFG, 'PUSHOVER', 'pushover_userkey', '')
        PUSHOVER_PRIORITY = check_setting_int(CFG, 'PUSHOVER', 'pushover_priority', 0)
        PUSHOVER_ONSNATCH = bool(check_setting_int(CFG, 'PUSHOVER', 'pushover_onsnatch', 0))

        BOXCAR_ENABLED = bool(check_setting_int(CFG, 'BOXCAR', 'boxcar_enabled', 0))
        BOXCAR_ONSNATCH = bool(check_setting_int(CFG, 'BOXCAR', 'boxcar_onsnatch', 0))
        BOXCAR_TOKEN = check_setting_str(CFG, 'BOXCAR', 'boxcar_token', '')

        PUSHBULLET_ENABLED = bool(check_setting_int(CFG, 'PUSHBULLET', 'pushbullet_enabled', 0))
        PUSHBULLET_APIKEY = check_setting_str(CFG, 'PUSHBULLET', 'pushbullet_apikey', '')
        PUSHBULLET_DEVICEID = check_setting_str(CFG, 'PUSHBULLET', 'pushbullet_deviceid', '')
        PUSHBULLET_ONSNATCH = bool(check_setting_int(CFG, 'PUSHBULLET', 'pushbullet_onsnatch', 0))

        USE_MINSIZE = bool(check_setting_int(CFG, 'General', 'use_minsize', 0))
        MINSIZE = check_setting_str(CFG, 'General', 'minsize', '')
        USE_MAXSIZE = bool(check_setting_int(CFG, 'General', 'use_maxsize', 0))
        MAXSIZE = check_setting_str(CFG, 'General', 'maxsize', '')
        ADD_TO_CSV = bool(check_setting_int(CFG, 'General', 'add_to_csv', 1))
        CVINFO = bool(check_setting_int(CFG, 'General', 'cvinfo', 0))
        ANNUALS_ON = bool(check_setting_int(CFG, 'General', 'annuals_on', 0))
        if not ANNUALS_ON:
            #default to on
            ANNUALS_ON = 0
        CV_ONLY = bool(check_setting_int(CFG, 'General', 'cv_only', 1))
        if not CV_ONLY:
            #default to on
            CV_ONLY = 1
        CV_ONETIMER = bool(check_setting_int(CFG, 'General', 'cv_onetimer', 1))
        if not CV_ONETIMER:
            CV_ONETIMER = 1
        LOG_LEVEL = check_setting_str(CFG, 'General', 'log_level', '')
        ENABLE_EXTRA_SCRIPTS = bool(check_setting_int(CFG, 'General', 'enable_extra_scripts', 0))
        EXTRA_SCRIPTS = check_setting_str(CFG, 'General', 'extra_scripts', '')

        ENABLE_PRE_SCRIPTS = bool(check_setting_int(CFG, 'General', 'enable_pre_scripts', 0))
        PRE_SCRIPTS = check_setting_str(CFG, 'General', 'pre_scripts', '')
        POST_PROCESSING = bool(check_setting_int(CFG, 'General', 'post_processing', 1))
        POST_PROCESSING_SCRIPT = check_setting_str(CFG, 'General', 'post_processing_script', '')
        FILE_OPTS = check_setting_str(CFG, 'General', 'file_opts', 'move')
        ENABLE_META = bool(check_setting_int(CFG, 'General', 'enable_meta', 0))
        CBR2CBZ_ONLY = bool(check_setting_int(CFG, 'General', 'cbr2cbz_only', 0))
        CT_TAG_CR = bool(check_setting_int(CFG, 'General', 'ct_tag_cr', 1))
        CT_TAG_CBL = bool(check_setting_int(CFG, 'General', 'ct_tag_cbl', 1))
        CT_CBZ_OVERWRITE = bool(check_setting_int(CFG, 'General', 'ct_cbz_overwrite', 0))
        UNRAR_CMD = check_setting_str(CFG, 'General', 'unrar_cmd', '')

        UPCOMING_SNATCHED = bool(check_setting_int(CFG, 'General', 'upcoming_snatched', 1))
        UPDATE_ENDED = bool(check_setting_int(CFG, 'General', 'update_ended', 0))
        INDIE_PUB = check_setting_str(CFG, 'General', 'indie_pub', '75')
        BIGGIE_PUB = check_setting_str(CFG, 'General', 'biggie_pub', '55')

        ENABLE_RSS = bool(check_setting_int(CFG, 'General', 'enable_rss', 1))
        RSS_CHECKINTERVAL = check_setting_str(CFG, 'General', 'rss_checkinterval', '20')
        RSS_LASTRUN = check_setting_str(CFG, 'General', 'rss_lastrun', '')

        FAILED_DOWNLOAD_HANDLING = bool(check_setting_int(CFG, 'General', 'failed_download_handling', 0))
        FAILED_AUTO = bool(check_setting_int(CFG, 'General', 'failed_auto', 0))
        ENABLE_TORRENTS = bool(check_setting_int(CFG, 'Torrents', 'enable_torrents', 0))
        MINSEEDS = check_setting_str(CFG, 'Torrents', 'minseeds', '0')
        TORRENT_LOCAL = bool(check_setting_int(CFG, 'Torrents', 'torrent_local', 0))
        LOCAL_WATCHDIR = check_setting_str(CFG, 'Torrents', 'local_watchdir', '')
        TORRENT_SEEDBOX = bool(check_setting_int(CFG, 'Torrents', 'torrent_seedbox', 0))
        SEEDBOX_HOST = check_setting_str(CFG, 'Torrents', 'seedbox_host', '')
        SEEDBOX_PORT = check_setting_str(CFG, 'Torrents', 'seedbox_port', '')
        SEEDBOX_USER = check_setting_str(CFG, 'Torrents', 'seedbox_user', '')
        SEEDBOX_PASS = check_setting_str(CFG, 'Torrents', 'seedbox_pass', '')
        SEEDBOX_WATCHDIR = check_setting_str(CFG, 'Torrents', 'seedbox_watchdir', '')

        ENABLE_TORRENT_SEARCH = bool(check_setting_int(CFG, 'Torrents', 'enable_torrent_search', 0))
        ENABLE_KAT = bool(check_setting_int(CFG, 'Torrents', 'enable_kat', 0))
        KAT_PROXY = check_setting_str(CFG, 'Torrents', 'kat_proxy', '')
        KAT_VERIFY = bool(check_setting_int(CFG, 'Torrents', 'kat_verify', 1))

        ENABLE_CBT = check_setting_str(CFG, 'Torrents', 'enable_cbt', '-1')
        if ENABLE_CBT != '-1':
            ENABLE_32P = bool(check_setting_int(CFG, 'Torrents', 'enable_cbt', 0))
            print 'Converting CBT settings to 32P - ENABLE_32P: ' + str(ENABLE_32P)
        else:
            ENABLE_32P = bool(check_setting_int(CFG, 'Torrents', 'enable_32p', 0))

        MODE_32P = check_setting_int(CFG, 'Torrents', 'mode_32p', 0)
        #legacy support of older config - reload into old values for consistency.
        try:
            if MODE_32P != 0 and MODE_32P != 1:
                #default to Legacy mode
                MODE_32P = 0
        except:
            MODE_32P = 0

        RSSFEED_32P = check_setting_str(CFG, 'Torrents', 'rssfeed_32p', '')
        PASSKEY_32P = check_setting_str(CFG, 'Torrents', 'passkey_32p', '')

        if MODE_32P == 0 and RSSFEED_32P is not None:
            #parse out the keys.
            KEYS_32P = helpers.parse_32pfeed(RSSFEED_32P)

        USERNAME_32P = check_setting_str(CFG, 'Torrents', 'username_32p', '')
        PASSWORD_32P = check_setting_str(CFG, 'Torrents', 'password_32p', '')
        VERIFY_32P = bool(check_setting_int(CFG, 'Torrents', 'verify_32p', 1))
        SNATCHEDTORRENT_NOTIFY = bool(check_setting_int(CFG, 'Torrents', 'snatchedtorrent_notify', 0))

        #this needs to have it's own category - for now General will do.
        NZB_DOWNLOADER = check_setting_int(CFG, 'General', 'nzb_downloader', 0)
        #legacy support of older config - reload into old values for consistency.
        if NZB_DOWNLOADER == 0: USE_SABNZBD = True
        elif NZB_DOWNLOADER == 1: USE_NZBGET = True
        elif NZB_DOWNLOADER == 2: USE_BLACKHOLE = True
        else:
            #default to SABnzbd
            NZB_DOWNLOADER = 0
            USE_SABNZBD = True
        #USE_SABNZBD = bool(check_setting_int(CFG, 'SABnzbd', 'use_sabnzbd', 0))
        SAB_HOST = check_setting_str(CFG, 'SABnzbd', 'sab_host', '')
        SAB_USERNAME = check_setting_str(CFG, 'SABnzbd', 'sab_username', '')
        SAB_PASSWORD = check_setting_str(CFG, 'SABnzbd', 'sab_password', '')
        SAB_APIKEY = check_setting_str(CFG, 'SABnzbd', 'sab_apikey', '')
        SAB_CATEGORY = check_setting_str(CFG, 'SABnzbd', 'sab_category', '')
        SAB_TO_MYLAR = bool(check_setting_int(CFG, 'SABnzbd', 'sab_to_mylar', 0))
        SAB_DIRECTORY = check_setting_str(CFG, 'SABnzbd', 'sab_directory', '')
        SAB_PRIORITY = check_setting_str(CFG, 'SABnzbd', 'sab_priority', '')
        if SAB_PRIORITY.isdigit():
            if SAB_PRIORITY == "0": SAB_PRIORITY = "Default"
            elif SAB_PRIORITY == "1": SAB_PRIORITY = "Low"
            elif SAB_PRIORITY == "2": SAB_PRIORITY = "Normal"
            elif SAB_PRIORITY == "3": SAB_PRIORITY = "High"
            elif SAB_PRIORITY == "4": SAB_PRIORITY = "Paused"
            else: SAB_PRIORITY = "Default"

        #USE_NZBGET = bool(check_setting_int(CFG, 'NZBGet', 'use_nzbget', 0))
        NZBGET_HOST = check_setting_str(CFG, 'NZBGet', 'nzbget_host', '')
        NZBGET_PORT = check_setting_str(CFG, 'NZBGet', 'nzbget_port', '')
        NZBGET_USERNAME = check_setting_str(CFG, 'NZBGet', 'nzbget_username', '')
        NZBGET_PASSWORD = check_setting_str(CFG, 'NZBGet', 'nzbget_password', '')
        NZBGET_CATEGORY = check_setting_str(CFG, 'NZBGet', 'nzbget_category', '')
        NZBGET_PRIORITY = check_setting_str(CFG, 'NZBGet', 'nzbget_priority', '')
        NZBGET_DIRECTORY = check_setting_str(CFG, 'NZBGet', 'nzbget_directory', '')

        #USE_BLACKHOLE = bool(check_setting_int(CFG, 'General', 'use_blackhole', 0))
        BLACKHOLE_DIR = check_setting_str(CFG, 'General', 'blackhole_dir', '')

        PR_NUM = 0  # provider counter here (used for provider orders)
        PR = []

        #add torrents to provider counter.
        if ENABLE_TORRENT_SEARCH:
            if ENABLE_32P:
                PR.append('32p')
                PR_NUM +=1
            if ENABLE_KAT:
                PR.append('kat')
                PR_NUM +=1


        NZBSU = bool(check_setting_int(CFG, 'NZBsu', 'nzbsu', 0))
        NZBSU_UID = check_setting_str(CFG, 'NZBsu', 'nzbsu_uid', '')
        NZBSU_APIKEY = check_setting_str(CFG, 'NZBsu', 'nzbsu_apikey', '')
        NZBSU_VERIFY = bool(check_setting_int(CFG, 'NZBsu', 'nzbsu_verify', 1))
        if NZBSU:
            PR.append('nzb.su')
            PR_NUM +=1

        DOGNZB = bool(check_setting_int(CFG, 'DOGnzb', 'dognzb', 0))
        DOGNZB_APIKEY = check_setting_str(CFG, 'DOGnzb', 'dognzb_apikey', '')
        DOGNZB_VERIFY = bool(check_setting_int(CFG, 'DOGnzb', 'dognzb_verify', 1))
        if DOGNZB:
            PR.append('dognzb')
            PR_NUM +=1

        EXPERIMENTAL = bool(check_setting_int(CFG, 'Experimental', 'experimental', 0))
        ALTEXPERIMENTAL = bool(check_setting_int(CFG, 'Experimental', 'altexperimental', 1))
        if EXPERIMENTAL:
            PR.append('Experimental')
            PR_NUM +=1

        ENABLE_TORZNAB = bool(check_setting_int(CFG, 'Torznab', 'enable_torznab', 0))
        TORZNAB_NAME = check_setting_str(CFG, 'Torznab', 'torznab_name', '')
        TORZNAB_HOST = check_setting_str(CFG, 'Torznab', 'torznab_host', '')
        TORZNAB_APIKEY = check_setting_str(CFG, 'Torznab', 'torznab_apikey', '')
        TORZNAB_VERIFY = bool(check_setting_int(CFG, 'Torznab', 'torznab_verify', 0))

        TORZNAB_CATEGORY = check_setting_str(CFG, 'Torznab', 'torznab_category', '')
        if ENABLE_TORZNAB:
            PR.append('Torznab')
            PR_NUM +=1

        #print 'PR_NUM::' + str(PR_NUM)

        NEWZNAB = bool(check_setting_int(CFG, 'Newznab', 'newznab', 0))

        if CONFIG_VERSION:
            NEWZNAB_HOST = check_setting_str(CFG, 'Newznab', 'newznab_host', '')
            NEWZNAB_APIKEY = check_setting_str(CFG, 'Newznab', 'newznab_apikey', '')
            NEWZNAB_UID = 1
            NEWZNAB_ENABLED = bool(check_setting_int(CFG, 'Newznab', 'newznab_enabled', 1))
            NEWZNAB_NAME = NEWZNAB_HOST
        if CONFIG_VERSION == '4':
            NEWZNAB_NAME = check_setting_str(CFG, 'Newznab', 'newznab_name', '')
        elif CONFIG_VERSION == '5':
            NEWZNAB_UID = check_setting_str(CFG, 'Newznab', 'newznab_uid', '')
            NEWZNAB_NAME = check_setting_str(CFG, 'Newznab', 'newznab_name', '')
        elif CONFIG_VERSION == '6':
            NEWZNAB_VERIFY = bool(check_setting_int(CFG, 'Newznab', 'newznab_verify', 0))

        # this gets nasty
        # if configv is != 4, then the NewznabName doesn't exist so we need to create and add it and
        #    then rewrite
        # if configv == 4, Newznab name exists and let it go through....

        # Need to pack the extra newznabs back into a list of tuples
        flattened_newznabs = check_setting_str(CFG, 'Newznab', 'extra_newznabs', [], log=False)
        if CONFIG_VERSION == '4':
            EN_NUM = 4   #EN_NUM is the number of iterations of itertools to use
        elif CONFIG_VERSION == '5':
            EN_NUM = 5   #addition of Newznab UID
        elif CONFIG_VERSION == '6':
            EN_NUM = 6
        else:
            EN_NUM = 3

        EXTRA_NEWZNABS = list(itertools.izip(*[itertools.islice(flattened_newznabs, i, None, EN_NUM) for i in range(EN_NUM)]))

        #if ConfigV3 add the nzb_name to it..
        if CONFIG_VERSION != '6':   #just bump it up to V6 and throw in the VERIFY too.
            ENABS = []
            for en in EXTRA_NEWZNABS:
                #set newznabname to newznab address initially so doesn't bomb.
                if CONFIG_VERSION == '4':
                    ENABS.append((en[0], en[1], '0', en[2], '1', en[3]))  #0=name,1=host,2=api,3=enabled/disabled
                elif CONFIG_VERSION == '5':
                    ENABS.append((en[0], en[1], '0', en[2], en[3], en[4]))  #0=name,1=host,2=api,3=enabled/disabled
                else:
                    ENABS.append((en[0], en[0], '0', en[1], '1', en[2]))  #0=name,1=host,2=api,3=uid,4=enabled/disabled
            #now we hammer the EXTRA_NEWZNABS with the corrected version
            EXTRA_NEWZNABS = ENABS
            #update the configV and write the config.
            CONFIG_VERSION = '6'
            config_write()

        #to counteract the loss of the 1st newznab entry because of a switch, let's rewrite to the tuple
        if NEWZNAB_HOST and CONFIG_VERSION:
            EXTRA_NEWZNABS.append((NEWZNAB_NAME, NEWZNAB_HOST, NEWZNAB_VERIFY, NEWZNAB_APIKEY, NEWZNAB_UID, int(NEWZNAB_ENABLED)))
            #PR_NUM +=1
            # Need to rewrite config here and bump up config version
            CONFIG_VERSION = '6'
            config_write()

        #print 'PR_NUM:' + str(PR_NUM)
        if NEWZNAB:
            for ens in EXTRA_NEWZNABS:
                #print ens[0]
                #print 'enabled:' + str(ens[4])
                if ens[5] == '1': # if newznabs are enabled
                    if ens[0] == "":
                        PR.append(ens[1])
                    else:
                        PR.append(ens[0])
                    PR_NUM +=1


        #print('Provider Number count: ' + str(PR_NUM))

        flattened_provider_order = check_setting_str(CFG, 'General', 'provider_order', [], log=False)
        PROVIDER_ORDER = list(itertools.izip(*[itertools.islice(flattened_provider_order, i, None, 2) for i in range(2)]))

        if len(flattened_provider_order) == 0:
            #priority provider sequence in order#, ProviderName
            #print('creating provider sequence order now...')
            TMPPR_NUM = 0
            PROV_ORDER = []
            while TMPPR_NUM < PR_NUM:
                PROV_ORDER.append({"order_seq":  TMPPR_NUM,
                                   "provider":   str(PR[TMPPR_NUM])})
                TMPPR_NUM +=1
            PROVIDER_ORDER = PROV_ORDER

        else:
            #if provider order exists already, load it and then append to end any NEW entries.
            TMPPR_NUM = 0
            PROV_ORDER = []
            for PRO in PROVIDER_ORDER:
                PROV_ORDER.append({"order_seq":  PRO[0],
                                   "provider":   str(PRO[1])})
                #print 'Provider is : ' + str(PRO)
                TMPPR_NUM +=1

            if PR_NUM != TMPPR_NUM:
#                print 'existing Order count does not match New Order count'
#                if PR_NUM > TMPPR_NUM:
#                    print 'New entries exist, appending to end as default ordering'
                TMPPR_NUM = 0
                while (TMPPR_NUM < PR_NUM):
                    #print 'checking entry #' + str(TMPPR_NUM) + ': ' + str(PR[TMPPR_NUM])
                    if not any(d.get("provider", None) == str(PR[TMPPR_NUM]) for d in PROV_ORDER):
                        new_order_seqnum = len(PROV_ORDER)
                        #print 'new provider should be : ' + str(new_order_seqnum) + ' -- ' + str(PR[TMPPR_NUM])
                        PROV_ORDER.append({"order_seq":  str(new_order_seqnum),
                                           "provider":   str(PR[TMPPR_NUM])})
                    #else:
                    #    print 'provider already exists at : ' + str(new_order_seqnum) + ' -- ' + str(PR[TMPPR_NUM])
                    TMPPR_NUM +=1


        #print 'Provider Order is:' + str(PROV_ORDER)

        if PROV_ORDER is None:
            flatt_providers = None
        else:
            flatt_providers = []
            for pro in PROV_ORDER:
                try:
                    provider_seq = re.sub('cbt', '32p', pro['provider'])
                    flatt_providers.extend([pro['order_seq'], provider_seq])
                except TypeError:
                    #if the value is None (no Name specified for Newznab entry), break out now
                    continue

        PROVIDER_ORDER = list(itertools.izip(*[itertools.islice(flatt_providers, i, None, 2) for i in range(2)]))
#       config_write()

        # update folder formats in the config & bump up config version
        if CONFIG_VERSION == '0':
            from mylar.helpers import replace_all
            file_values = {'issue':  'Issue', 'title': 'Title', 'series': 'Series', 'year': 'Year'}
            folder_values = {'series': 'Series', 'publisher': 'Publisher', 'year': 'Year', 'first': 'First', 'lowerfirst': 'first'}
            FILE_FORMAT = replace_all(FILE_FORMAT, file_values)
            FOLDER_FORMAT = replace_all(FOLDER_FORMAT, folder_values)

            CONFIG_VERSION = '1'

        if CONFIG_VERSION == '1':

            from mylar.helpers import replace_all

            file_values = {'Issue':        '$Issue',
                            'Title':        '$Title',
                            'Series':       '$Series',
                            'Year':         '$Year',
                            'title':        '$title',
                            'series':       '$series',
                            'year':         '$year'
                            }
            folder_values = {'Series':       '$Series',
                                'Publisher':    '$Publisher',
                                'Year':         '$Year',
                                'First':        '$First',
                                'series':       '$series',
                                'publisher':    '$publisher',
                                'year':         '$year',
                                'first':        '$first'
                            }
            FILE_FORMAT = replace_all(FILE_FORMAT, file_values)
            FOLDER_FORMAT = replace_all(FOLDER_FORMAT, folder_values)

            CONFIG_VERSION = '2'

        if 'http://' not in SAB_HOST[:7] and 'https://' not in SAB_HOST[:8]:
            SAB_HOST = 'http://' + SAB_HOST

        if not LOG_DIR:
            LOG_DIR = os.path.join(DATA_DIR, 'logs')

        if not os.path.exists(LOG_DIR):
            try:
                os.makedirs(LOG_DIR)
            except OSError:
                if not QUIET:
                    print 'Unable to create the log directory. Logging to screen only.'

        # Start the logger, silence console logging if we need to
        logger.initLogger(console=not QUIET, log_dir=LOG_DIR, verbose=VERBOSE) #logger.mylar_log.initLogger(verbose=VERBOSE)

        #try to get the local IP using socket. Get this on every startup so it's at least current for existing session.
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            LOCAL_IP = s.getsockname()[0]
            s.close()
            logger.info('Successfully discovered local IP and locking it in as : ' + str(LOCAL_IP))
        except:
            logger.warn('Unable to determine local IP - this might cause problems when downloading (maybe use host_return in the config.ini)')
            LOCAL_IP = HTTP_HOST


        # verbatim back the logger being used since it's now started.
        if LOGTYPE == 'clog':
            logprog = 'Concurrent Rotational Log Handler'
        else:
            logprog = 'Rotational Log Handler (default)'

        logger.fdebug('Logger set to use : ' + logprog)
        if LOGTYPE == 'log' and OS_DETECT == 'Windows':
            logger.fdebug('ConcurrentLogHandler package not installed. Using builtin log handler for Rotational logs (default)')
            logger.fdebug('[Windows Users] If you are experiencing log file locking and want this auto-enabled, you need to install Python Extensions for Windows ( http://sourceforge.net/projects/pywin32/ )')

        # Get the currently installed version - returns None, 'win32' or the git hash
        # Also sets INSTALL_TYPE variable to 'win', 'git' or 'source'
        CURRENT_VERSION, GIT_BRANCH = versioncheck.getVersion()
        config_write()

        if CURRENT_VERSION is not None:
            hash = CURRENT_VERSION[:7]
        else:
            hash = "unknown"

        if GIT_BRANCH == 'master':
            vers = 'M'
        elif GIT_BRANCH == 'development':
           vers = 'D'
        else:
           vers = 'NONE'

        USER_AGENT = 'Mylar/' +str(hash) +'(' +vers +') +http://www.github.com/evilhero/mylar/'

        CV_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1'}

        # verbatim DB module.
        logger.info('[DB Module] Loading : ' + DBCHOICE + ' as the database module to use.')

        logger.info('[Cache Check] Cache directory currently set to : ' + CACHE_DIR)
        # Put the cache dir in the data dir for now
        if not CACHE_DIR:
            CACHE_DIR = os.path.join(str(DATA_DIR), 'cache')
            logger.info('[Cache Check] Cache directory not found in configuration. Defaulting location to : ' + CACHE_DIR)

        if not os.path.exists(CACHE_DIR):
            try:
               os.makedirs(CACHE_DIR)
            except OSError:
                logger.error('[Cache Check] Could not create cache dir. Check permissions of datadir: ' + DATA_DIR)

        #ComicVine API Check
        if COMICVINE_API is None or COMICVINE_API == '':
            logger.error('No User Comicvine API key specified. I will not work very well due to api limits - http://api.comicvine.com/ and get your own free key.')

        # Sanity check for search interval. Set it to at least 6 hours
        if SEARCH_INTERVAL < 360:
            logger.info('Search interval too low. Resetting to 6 hour minimum')
            SEARCH_INTERVAL = 360


        # Initialize the database
        logger.info('Checking to see if the database has all tables....')
        try:
            dbcheck()
        except Exception, e:
            logger.error('Cannot connect to the database: %s' % e)

        # Check for new versions (autoupdate)
        if CHECK_GITHUB_ON_STARTUP:
            try:
                LATEST_VERSION = versioncheck.checkGithub()
            except:
                LATEST_VERSION = CURRENT_VERSION
        else:
            LATEST_VERSION = CURRENT_VERSION
#
        if AUTO_UPDATE:
            if CURRENT_VERSION != LATEST_VERSION and INSTALL_TYPE != 'win' and COMMITS_BEHIND > 0:
                logger.info('Auto-updating has been enabled. Attempting to auto-update.')
#                SIGNAL = 'update'

        #check for syno_fix here
        if SYNO_FIX:
            parsepath = os.path.join(DATA_DIR, 'bs4', 'builder', '_lxml.py')
            if os.path.isfile(parsepath):
                print ("found bs4...renaming appropriate file.")
                src = os.path.join(parsepath)
                dst = os.path.join(DATA_DIR, 'bs4', 'builder', 'lxml.py')
                try:
                    shutil.move(src, dst)
                except (OSError, IOError):
                    logger.error('Unable to rename file...shutdown Mylar and go to ' + src.encode('utf-8') + ' and rename the _lxml.py file to lxml.py')
                    logger.error('NOT doing this will result in errors when adding / refreshing a series')
            else:
                logger.info('Synology Parsing Fix already implemented. No changes required at this time.')

        #set the default URL for ComicVine API here.
        CVURL = 'http://comicvine.gamespot.com/api/'

        #comictagger - force to use included version if option is enabled.
        if ENABLE_META:
            CMTAGGER_PATH = PROG_DIR
            #we need to make sure the default folder setting for the comictagger settings exists so things don't error out
            CT_SETTINGSPATH = os.path.join(PROG_DIR, 'lib', 'comictaggerlib', 'ct_settings')
            logger.info('Setting ComicTagger settings default path to : ' + CT_SETTINGSPATH)

            if os.path.exists(CT_SETTINGSPATH):
                logger.info('ComicTagger settings location exists.')
            else:
                try:
                    os.mkdir(CT_SETTINGSPATH)
                except OSError,e:
                    if e.errno != errno.EEXIST:
                        logger.error('Unable to create setting directory for ComicTagger. This WILL cause problems when tagging.')
                else:
                    logger.info('Successfully created ComicTagger Settings location.')

        if LOCMOVE:
            helpers.updateComicLocation()

        #logger.fdebug('platform detected as : ' + OS_DETECT)

        #Ordering comics here
        logger.info('Remapping the sorting to allow for new additions.')
        COMICSORT = helpers.ComicSort(sequence='startup')

        #initialize the scheduler threads here.
        dbUpdateScheduler = scheduler.Scheduler(action=dbupdater.dbUpdate(),
                                                cycleTime=datetime.timedelta(hours=48),
                                                runImmediately=False,
                                                threadName="DBUPDATE")

        if NZB_STARTUP_SEARCH:
            searchrunmode = True
        else:
            searchrunmode = False

        searchScheduler = scheduler.Scheduler(searchit.CurrentSearcher(),
                                              cycleTime=datetime.timedelta(minutes=SEARCH_INTERVAL),
                                              threadName="SEARCH",
                                              runImmediately=searchrunmode)

        RSSScheduler = scheduler.Scheduler(rsscheckit.tehMain(),
                                           cycleTime=datetime.timedelta(minutes=int(RSS_CHECKINTERVAL)),
                                           threadName="RSSCHECK",
                                           runImmediately=True,
                                           delay=30)

        WeeklyScheduler = scheduler.Scheduler(weeklypullit.Weekly(),
                                              cycleTime=datetime.timedelta(hours=24),
                                              threadName="WEEKLYCHECK",
                                              runImmediately=True,
                                              delay=10)

        VersionScheduler = scheduler.Scheduler(versioncheckit.CheckVersion(),
                                               cycleTime=datetime.timedelta(minutes=CHECK_GITHUB_INTERVAL),
                                               threadName="VERSIONCHECK",
                                               runImmediately=False)


        FolderMonitorScheduler = scheduler.Scheduler(PostProcessor.FolderCheck(),
                                                     cycleTime=datetime.timedelta(minutes=int(DOWNLOAD_SCAN_INTERVAL)),
                                                     threadName="FOLDERMONITOR",
                                                     runImmediately=True,
                                                     delay=60)

        # Store the original umask
        UMASK = os.umask(0)
        os.umask(UMASK)

        __INITIALIZED__ = True
        return True

def daemonize():

    if threading.activeCount() != 1:
        logger.warn('There are %r active threads. Daemonizing may cause \
                        strange behavior.' % threading.enumerate())

    sys.stdout.flush()
    sys.stderr.flush()

    # Do first fork
    try:
        pid = os.fork()
        if pid == 0:
            pass
        else:
            # Exit the parent process
            logger.debug('Forking once...')
            os._exit(0)
    except OSError, e:
        sys.exit("1st fork failed: %s [%d]" % (e.strerror, e.errno))

    os.setsid()

    # Make sure I can read my own files and shut out others
    prev = os.umask(0)  # @UndefinedVariable - only available in UNIX
    os.umask(prev and int('077', 8))

    # Do second fork
    try:
        pid = os.fork()
        if pid > 0:
            logger.debug('Forking twice...')
            os._exit(0) # Exit second parent process
    except OSError, e:
        sys.exit("2nd fork failed: %s [%d]" % (e.strerror, e.errno))

    dev_null = file('/dev/null', 'r')
    os.dup2(dev_null.fileno(), sys.stdin.fileno())

    si = open('/dev/null', "r")
    so = open('/dev/null', "a+")
    se = open('/dev/null', "a+")

    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    pid = os.getpid()
    logger.info('Daemonized to PID: %s' % pid)
    if CREATEPID:
        logger.info("Writing PID %d to %s", pid, PIDFILE)
        with file(PIDFILE, 'w') as fp:
            fp.write("%s\n" % pid)

def launch_browser(host, port, root):

    if host == '0.0.0.0':
        host = 'localhost'

    try:
        webbrowser.open('http://%s:%i%s' % (host, port, root))
    except Exception, e:
        logger.error('Could not launch browser: %s' % e)

def config_write():
    new_config = ConfigObj()
    new_config.filename = CONFIG_FILE

    new_config.encoding = 'UTF8'
    new_config['General'] = {}
    new_config['General']['config_version'] = CONFIG_VERSION
    new_config['General']['dbchoice'] = DBCHOICE
    new_config['General']['dbuser'] = DBUSER
    new_config['General']['dbpass'] = DBPASS
    new_config['General']['dbname'] = DBNAME

    if COMICVINE_API is None or COMICVINE_API == '':
        new_config['General']['comicvine_api'] = COMICVINE_API
    else:
        new_config['General']['comicvine_api'] = COMICVINE_API.strip()

    new_config['General']['cvapi_rate'] = CVAPI_RATE
    new_config['General']['http_port'] = HTTP_PORT
    new_config['General']['http_host'] = HTTP_HOST
    new_config['General']['http_username'] = HTTP_USERNAME
    new_config['General']['http_password'] = HTTP_PASSWORD
    new_config['General']['http_root'] = HTTP_ROOT
    new_config['General']['enable_https'] = int(ENABLE_HTTPS)
    new_config['General']['https_cert'] = HTTPS_CERT
    new_config['General']['https_key'] = HTTPS_KEY
    new_config['General']['https_force_on'] = int(HTTPS_FORCE_ON)
    new_config['General']['host_return'] = HOST_RETURN
    new_config['General']['api_enabled'] = int(API_ENABLED)
    new_config['General']['api_key'] = API_KEY
    new_config['General']['launch_browser'] = int(LAUNCH_BROWSER)
    new_config['General']['auto_update'] = int(AUTO_UPDATE)
    new_config['General']['log_dir'] = LOG_DIR
    new_config['General']['max_logsize'] = MAX_LOGSIZE
    new_config['General']['git_path'] = GIT_PATH
    new_config['General']['cache_dir'] = CACHE_DIR
    new_config['General']['annuals_on'] = int(ANNUALS_ON)
    new_config['General']['cv_only'] = int(CV_ONLY)
    new_config['General']['cv_onetimer'] = int(CV_ONETIMER)
    new_config['General']['check_github'] = int(CHECK_GITHUB)
    new_config['General']['check_github_on_startup'] = int(CHECK_GITHUB_ON_STARTUP)
    new_config['General']['check_github_interval'] = CHECK_GITHUB_INTERVAL
    new_config['General']['git_user'] = GIT_USER
    new_config['General']['git_branch'] = GIT_BRANCH
    new_config['General']['destination_dir'] = DESTINATION_DIR
    new_config['General']['multiple_dest_dirs'] = MULTIPLE_DEST_DIRS
    new_config['General']['create_folders'] = int(CREATE_FOLDERS)
    new_config['General']['delete_remove_dir'] = int(DELETE_REMOVE_DIR)
    new_config['General']['chmod_dir'] = CHMOD_DIR
    new_config['General']['chmod_file'] = CHMOD_FILE
    new_config['General']['chowner'] = CHOWNER
    new_config['General']['chgroup'] = CHGROUP
    new_config['General']['usenet_retention'] = USENET_RETENTION
    new_config['General']['alt_pull'] = int(ALT_PULL)
    new_config['General']['search_interval'] = SEARCH_INTERVAL
    new_config['General']['nzb_startup_search'] = int(NZB_STARTUP_SEARCH)
    new_config['General']['add_comics'] = int(ADD_COMICS)
    new_config['General']['comic_dir'] = COMIC_DIR
    new_config['General']['imp_move'] = int(IMP_MOVE)
    new_config['General']['imp_rename'] = int(IMP_RENAME)
    new_config['General']['imp_metadata'] = int(IMP_METADATA)
    new_config['General']['enable_check_folder'] = int(ENABLE_CHECK_FOLDER)
    new_config['General']['download_scan_interval'] = DOWNLOAD_SCAN_INTERVAL
    new_config['General']['folder_scan_log_verbose'] = FOLDER_SCAN_LOG_VERBOSE
    new_config['General']['check_folder'] = CHECK_FOLDER
    new_config['General']['interface'] = INTERFACE
    new_config['General']['dupeconstraint'] = DUPECONSTRAINT
    new_config['General']['ddump'] = DDUMP
    new_config['General']['duplicate_dump'] = DUPLICATE_DUMP
    new_config['General']['autowant_all'] = int(AUTOWANT_ALL)
    new_config['General']['autowant_upcoming'] = int(AUTOWANT_UPCOMING)
    new_config['General']['preferred_quality'] = int(PREFERRED_QUALITY)
    new_config['General']['comic_cover_local'] = int(COMIC_COVER_LOCAL)
    new_config['General']['correct_metadata'] = int(CORRECT_METADATA)
    new_config['General']['move_files'] = int(MOVE_FILES)
    new_config['General']['rename_files'] = int(RENAME_FILES)
    new_config['General']['folder_format'] = FOLDER_FORMAT
    new_config['General']['file_format'] = FILE_FORMAT
    #new_config['General']['use_blackhole'] = int(USE_BLACKHOLE)
    new_config['General']['blackhole_dir'] = BLACKHOLE_DIR
    new_config['General']['replace_spaces'] = int(REPLACE_SPACES)
    new_config['General']['replace_char'] = REPLACE_CHAR
    new_config['General']['zero_level'] = int(ZERO_LEVEL)
    new_config['General']['zero_level_n'] = ZERO_LEVEL_N
    new_config['General']['lowercase_filenames'] = int(LOWERCASE_FILENAMES)
    new_config['General']['ignore_havetotal'] = int(IGNORE_HAVETOTAL)
    new_config['General']['snatched_havetotal'] = int(SNATCHED_HAVETOTAL)
    new_config['General']['syno_fix'] = int(SYNO_FIX)
    new_config['General']['search_delay'] = SEARCH_DELAY
    new_config['General']['grabbag_dir'] = GRABBAG_DIR
    new_config['General']['highcount'] = HIGHCOUNT
    new_config['General']['read2filename'] = int(READ2FILENAME)
    new_config['General']['send2read'] = int(SEND2READ)
    new_config['General']['tab_enable'] = int(TAB_ENABLE)
    new_config['General']['tab_host'] = TAB_HOST
    new_config['General']['tab_user'] = TAB_USER
    new_config['General']['tab_pass'] = TAB_PASS
    new_config['General']['tab_directory'] = TAB_DIRECTORY
    new_config['General']['storyarcdir'] = int(STORYARCDIR)
    new_config['General']['copy2arcdir'] = int(COPY2ARCDIR)
    new_config['General']['use_minsize'] = int(USE_MINSIZE)
    new_config['General']['minsize'] = MINSIZE
    new_config['General']['use_maxsize'] = int(USE_MAXSIZE)
    new_config['General']['maxsize'] = MAXSIZE
    new_config['General']['add_to_csv'] = int(ADD_TO_CSV)
    new_config['General']['cvinfo'] = int(CVINFO)
    new_config['General']['log_level'] = LOG_LEVEL
    new_config['General']['enable_extra_scripts'] = int(ENABLE_EXTRA_SCRIPTS)
    new_config['General']['extra_scripts'] = EXTRA_SCRIPTS
    new_config['General']['enable_pre_scripts'] = int(ENABLE_PRE_SCRIPTS)
    new_config['General']['pre_scripts'] = PRE_SCRIPTS
    new_config['General']['post_processing'] = int(POST_PROCESSING)
    new_config['General']['post_processing_script'] = POST_PROCESSING_SCRIPT
    new_config['General']['file_opts'] = FILE_OPTS
    new_config['General']['weekfolder'] = int(WEEKFOLDER)
    new_config['General']['weekfolder_loc'] = WEEKFOLDER_LOC
    new_config['General']['locmove'] = int(LOCMOVE)
    new_config['General']['newcom_dir'] = NEWCOM_DIR
    new_config['General']['fftonewcom_dir'] = int(FFTONEWCOM_DIR)
    new_config['General']['enable_meta'] = int(ENABLE_META)
    new_config['General']['cbr2cbz_only'] = int(CBR2CBZ_ONLY)
    new_config['General']['ct_tag_cr'] = int(CT_TAG_CR)
    new_config['General']['ct_tag_cbl'] = int(CT_TAG_CBL)
    new_config['General']['ct_cbz_overwrite'] = int(CT_CBZ_OVERWRITE)
    new_config['General']['unrar_cmd'] = UNRAR_CMD
    new_config['General']['update_ended'] = int(UPDATE_ENDED)
    new_config['General']['indie_pub'] = INDIE_PUB
    new_config['General']['biggie_pub'] = BIGGIE_PUB
    new_config['General']['upcoming_snatched'] = int(UPCOMING_SNATCHED)
    new_config['General']['enable_rss'] = int(ENABLE_RSS)
    new_config['General']['rss_checkinterval'] = RSS_CHECKINTERVAL
    new_config['General']['rss_lastrun'] = RSS_LASTRUN
    new_config['General']['failed_download_handling'] = int(FAILED_DOWNLOAD_HANDLING)
    new_config['General']['failed_auto'] = int(FAILED_AUTO)

    # Need to unpack the providers for saving in config.ini
    if PROVIDER_ORDER is None:
        flattened_providers = None
    else:
        flattened_providers = []
        for pro in PROVIDER_ORDER:
            #for key, value in pro.items():
            for item in pro:
                flattened_providers.append(str(item))
                #flattened_providers.append(str(value))

    new_config['General']['provider_order'] = flattened_providers
    new_config['General']['nzb_downloader'] = int(NZB_DOWNLOADER)

    new_config['Torrents'] = {}
    new_config['Torrents']['enable_torrents'] = int(ENABLE_TORRENTS)
    new_config['Torrents']['minseeds'] = int(MINSEEDS)
    new_config['Torrents']['torrent_local'] = int(TORRENT_LOCAL)
    new_config['Torrents']['local_watchdir'] = LOCAL_WATCHDIR
    new_config['Torrents']['torrent_seedbox'] = int(TORRENT_SEEDBOX)
    new_config['Torrents']['seedbox_host'] = SEEDBOX_HOST
    new_config['Torrents']['seedbox_port'] = SEEDBOX_PORT
    new_config['Torrents']['seedbox_user'] = SEEDBOX_USER
    new_config['Torrents']['seedbox_pass'] = SEEDBOX_PASS
    new_config['Torrents']['seedbox_watchdir'] = SEEDBOX_WATCHDIR

    new_config['Torrents']['enable_torrent_search'] = int(ENABLE_TORRENT_SEARCH)
    new_config['Torrents']['enable_kat'] = int(ENABLE_KAT)
    new_config['Torrents']['kat_proxy'] = KAT_PROXY
    new_config['Torrents']['kat_verify'] = KAT_VERIFY
    new_config['Torrents']['enable_32p'] = int(ENABLE_32P)
    new_config['Torrents']['mode_32p'] = int(MODE_32P)
    new_config['Torrents']['passkey_32p'] = PASSKEY_32P
    new_config['Torrents']['rssfeed_32p'] = RSSFEED_32P
    new_config['Torrents']['username_32p'] = USERNAME_32P
    new_config['Torrents']['password_32p'] = PASSWORD_32P
    new_config['Torrents']['verify_32p'] = int(VERIFY_32P)
    new_config['Torrents']['snatchedtorrent_notify'] = int(SNATCHEDTORRENT_NOTIFY)
    new_config['SABnzbd'] = {}
    #new_config['SABnzbd']['use_sabnzbd'] = int(USE_SABNZBD)
    new_config['SABnzbd']['sab_host'] = SAB_HOST
    new_config['SABnzbd']['sab_username'] = SAB_USERNAME
    new_config['SABnzbd']['sab_password'] = SAB_PASSWORD
    new_config['SABnzbd']['sab_apikey'] = SAB_APIKEY
    new_config['SABnzbd']['sab_category'] = SAB_CATEGORY
    new_config['SABnzbd']['sab_priority'] = SAB_PRIORITY
    new_config['SABnzbd']['sab_to_mylar'] = int(SAB_TO_MYLAR)
    new_config['SABnzbd']['sab_directory'] = SAB_DIRECTORY

    new_config['NZBGet'] = {}
    #new_config['NZBGet']['use_nzbget'] = int(USE_NZBGET)
    new_config['NZBGet']['nzbget_host'] = NZBGET_HOST
    new_config['NZBGet']['nzbget_port'] = NZBGET_PORT
    new_config['NZBGet']['nzbget_username'] = NZBGET_USERNAME
    new_config['NZBGet']['nzbget_password'] = NZBGET_PASSWORD
    new_config['NZBGet']['nzbget_category'] = NZBGET_CATEGORY
    new_config['NZBGet']['nzbget_priority'] = NZBGET_PRIORITY
    new_config['NZBGet']['nzbget_directory'] = NZBGET_DIRECTORY

    new_config['NZBsu'] = {}
    new_config['NZBsu']['nzbsu'] = int(NZBSU)
    new_config['NZBsu']['nzbsu_uid'] = NZBSU_UID
    new_config['NZBsu']['nzbsu_apikey'] = NZBSU_APIKEY
    new_config['NZBsu']['nzbsu_verify'] = NZBSU_VERIFY

    new_config['DOGnzb'] = {}
    new_config['DOGnzb']['dognzb'] = int(DOGNZB)
    new_config['DOGnzb']['dognzb_apikey'] = DOGNZB_APIKEY
    new_config['DOGnzb']['dognzb_verify'] = DOGNZB_VERIFY

    new_config['Experimental'] = {}
    new_config['Experimental']['experimental'] = int(EXPERIMENTAL)
    new_config['Experimental']['altexperimental'] = int(ALTEXPERIMENTAL)

    new_config['Torznab'] = {}
    new_config['Torznab']['enable_torznab'] = int(ENABLE_TORZNAB)
    new_config['Torznab']['torznab_name'] = TORZNAB_NAME
    new_config['Torznab']['torznab_host'] = TORZNAB_HOST
    new_config['Torznab']['torznab_apikey'] = TORZNAB_APIKEY
    new_config['Torznab']['torznab_category'] = TORZNAB_CATEGORY
    new_config['Torznab']['torznab_verify'] = TORZNAB_VERIFY

    new_config['Newznab'] = {}
    new_config['Newznab']['newznab'] = int(NEWZNAB)

    # Need to unpack the extra newznabs for saving in config.ini
    flattened_newznabs = []
    for newznab in EXTRA_NEWZNABS:
        for item in newznab:
            flattened_newznabs.append(item)

    new_config['Newznab']['extra_newznabs'] = flattened_newznabs

    new_config['Prowl'] = {}
    new_config['Prowl']['prowl_enabled'] = int(PROWL_ENABLED)
    new_config['Prowl']['prowl_keys'] = PROWL_KEYS
    new_config['Prowl']['prowl_onsnatch'] = int(PROWL_ONSNATCH)
    new_config['Prowl']['prowl_priority'] = int(PROWL_PRIORITY)

    new_config['NMA'] = {}
    new_config['NMA']['nma_enabled'] = int(NMA_ENABLED)
    new_config['NMA']['nma_apikey'] = NMA_APIKEY
    new_config['NMA']['nma_priority'] = NMA_PRIORITY
    new_config['NMA']['nma_onsnatch'] = int(NMA_ONSNATCH)

    new_config['PUSHOVER'] = {}
    new_config['PUSHOVER']['pushover_enabled'] = int(PUSHOVER_ENABLED)
    new_config['PUSHOVER']['pushover_apikey'] = PUSHOVER_APIKEY
    new_config['PUSHOVER']['pushover_userkey'] = PUSHOVER_USERKEY
    new_config['PUSHOVER']['pushover_priority'] = PUSHOVER_PRIORITY
    new_config['PUSHOVER']['pushover_onsnatch'] = int(PUSHOVER_ONSNATCH)

    new_config['BOXCAR'] = {}
    new_config['BOXCAR']['boxcar_enabled'] = int(BOXCAR_ENABLED)
    new_config['BOXCAR']['boxcar_onsnatch'] = int(BOXCAR_ONSNATCH)
    new_config['BOXCAR']['boxcar_token'] = BOXCAR_TOKEN

    new_config['PUSHBULLET'] = {}
    new_config['PUSHBULLET']['pushbullet_enabled'] = int(PUSHBULLET_ENABLED)
    new_config['PUSHBULLET']['pushbullet_apikey'] = PUSHBULLET_APIKEY
    new_config['PUSHBULLET']['pushbullet_deviceid'] = PUSHBULLET_DEVICEID
    new_config['PUSHBULLET']['pushbullet_onsnatch'] = int(PUSHBULLET_ONSNATCH)

    new_config.write()

def start():

    global __INITIALIZED__, started, \
        dbUpdateScheduler, searchScheduler, RSSScheduler, \
        WeeklyScheduler, VersionScheduler, FolderMonitorScheduler

    with INIT_LOCK:

        if __INITIALIZED__:

            # Start our scheduled background tasks
            #from mylar import updater, search, PostProcessor


            #SCHED.add_interval_job(updater.dbUpdate, hours=48)
            #SCHED.add_interval_job(search.searchforissue, minutes=SEARCH_INTERVAL)

            #start the db updater scheduler
            logger.info('Initializing the DB Updater.')
            dbUpdateScheduler.thread.start()

            #start the search scheduler
            searchScheduler.thread.start()

            helpers.latestdate_fix()

            #initiate startup rss feeds for torrents/nzbs here...
            if ENABLE_RSS:
                #SCHED.add_interval_job(rsscheck.tehMain, minutes=int(RSS_CHECKINTERVAL))
                RSSScheduler.thread.start()
                logger.info('Initiating startup-RSS feed checks.')
                #rsscheck.tehMain()

            #weekly pull list gets messed up if it's not populated first, so let's populate it then set the scheduler.
            logger.info('Checking for existance of Weekly Comic listing...')
            #PULLNEW = 'no'  #reset the indicator here.
            #threading.Thread(target=weeklypull.pullit).start()
            #now the scheduler (check every 24 hours)
            #SCHED.add_interval_job(weeklypull.pullit, hours=24)
            WeeklyScheduler.thread.start()

            #let's do a run at the Wanted issues here (on startup) if enabled.
            #if NZB_STARTUP_SEARCH:
            #    threading.Thread(target=search.searchforissue).start()

            if CHECK_GITHUB:
                VersionScheduler.thread.start()
                #SCHED.add_interval_job(versioncheck.checkGithub, minutes=CHECK_GITHUB_INTERVAL)

            #run checkFolder every X minutes (basically Manual Run Post-Processing)
            if ENABLE_CHECK_FOLDER:
                if DOWNLOAD_SCAN_INTERVAL >0:
                    logger.info('Enabling folder monitor for : ' + str(CHECK_FOLDER) + ' every ' + str(DOWNLOAD_SCAN_INTERVAL) + ' minutes.')
                    FolderMonitorScheduler.thread.start()
                    #SCHED.add_interval_job(helpers.checkFolder, minutes=int(DOWNLOAD_SCAN_INTERVAL))
                else:
                    logger.error('You need to specify a monitoring time for the check folder option to work')
            SCHED.start()

        started = True

def dbcheck():
    #if DBCHOICE == 'postgresql':
    #    import psycopg2
    #    conn = psycopg2.connect(database=DBNAME, user=DBUSER, password=DBPASS)
    #    c_error = 'psycopg2.DatabaseError'
    #else:

    conn = sqlite3.connect(DB_FILE)
    c_error = 'sqlite3.OperationalError'
    c=conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS comics (ComicID TEXT UNIQUE, ComicName TEXT, ComicSortName TEXT, ComicYear TEXT, DateAdded TEXT, Status TEXT, IncludeExtras INTEGER, Have INTEGER, Total INTEGER, ComicImage TEXT, ComicPublisher TEXT, ComicLocation TEXT, ComicPublished TEXT, NewPublish TEXT, LatestIssue TEXT, LatestDate TEXT, Description TEXT, QUALalt_vers TEXT, QUALtype TEXT, QUALscanner TEXT, QUALquality TEXT, LastUpdated TEXT, AlternateSearch TEXT, UseFuzzy TEXT, ComicVersion TEXT, SortOrder INTEGER, DetailURL TEXT, ForceContinuing INTEGER, ComicName_Filesafe TEXT, AlternateFileName TEXT, ComicImageURL TEXT, ComicImageALTURL TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS issues (IssueID TEXT, ComicName TEXT, IssueName TEXT, Issue_Number TEXT, DateAdded TEXT, Status TEXT, Type TEXT, ComicID TEXT, ArtworkURL Text, ReleaseDate TEXT, Location TEXT, IssueDate TEXT, Int_IssueNumber INT, ComicSize TEXT, AltIssueNumber TEXT, IssueDate_Edit TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS snatched (IssueID TEXT, ComicName TEXT, Issue_Number TEXT, Size INTEGER, DateAdded TEXT, Status TEXT, FolderName TEXT, ComicID TEXT, Provider TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS upcoming (ComicName TEXT, IssueNumber TEXT, ComicID TEXT, IssueID TEXT, IssueDate TEXT, Status TEXT, DisplayComicName TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS nzblog (IssueID TEXT, NZBName TEXT, SARC TEXT, PROVIDER TEXT, ID TEXT, AltNZBName TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS weekly (SHIPDATE TEXT, PUBLISHER TEXT, ISSUE TEXT, COMIC VARCHAR(150), EXTRA TEXT, STATUS TEXT, ComicID TEXT, IssueID TEXT)')
#    c.execute('CREATE TABLE IF NOT EXISTS sablog (nzo_id TEXT, ComicName TEXT, ComicYEAR TEXT, ComicIssue TEXT, name TEXT, nzo_complete TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS importresults (impID TEXT, ComicName TEXT, ComicYear TEXT, Status TEXT, ImportDate TEXT, ComicFilename TEXT, ComicLocation TEXT, WatchMatch TEXT, DisplayName TEXT, SRID TEXT, ComicID TEXT, IssueID TEXT, Volume TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS readlist (IssueID TEXT, ComicName TEXT, Issue_Number TEXT, Status TEXT, DateAdded TEXT, Location TEXT, inCacheDir TEXT, SeriesYear TEXT, ComicID TEXT, StatusChange TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS readinglist(StoryArcID TEXT, ComicName TEXT, IssueNumber TEXT, SeriesYear TEXT, IssueYEAR TEXT, StoryArc TEXT, TotalIssues TEXT, Status TEXT, inCacheDir TEXT, Location TEXT, IssueArcID TEXT, ReadingOrder INT, IssueID TEXT, ComicID TEXT, StoreDate TEXT, IssueDate TEXT, Publisher TEXT, IssuePublisher TEXT, IssueName TEXT, CV_ArcID TEXT, Int_IssueNumber INT)')
    c.execute('CREATE TABLE IF NOT EXISTS annuals (IssueID TEXT, Issue_Number TEXT, IssueName TEXT, IssueDate TEXT, Status TEXT, ComicID TEXT, GCDComicID TEXT, Location TEXT, ComicSize TEXT, Int_IssueNumber INT, ComicName TEXT, ReleaseDate TEXT, ReleaseComicID TEXT, ReleaseComicName TEXT, IssueDate_Edit TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS rssdb (Title TEXT UNIQUE, Link TEXT, Pubdate TEXT, Site TEXT, Size TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS futureupcoming (ComicName TEXT, IssueNumber TEXT, ComicID TEXT, IssueID TEXT, IssueDate TEXT, Publisher TEXT, Status TEXT, DisplayComicName TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS failed (ID TEXT, Status TEXT, ComicID TEXT, IssueID TEXT, Provider TEXT, ComicName TEXT, Issue_Number TEXT, NZBName TEXT, DateFailed TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS searchresults (SRID TEXT, results Numeric, Series TEXT, publisher TEXT, haveit TEXT, name TEXT, deck TEXT, url TEXT, description TEXT, comicid TEXT, comicimage TEXT, issues TEXT, comicyear TEXT, ogcname TEXT)')
    conn.commit
    c.close
    #new

    csv_load()


    #add in the late players to the game....
    # -- Comics Table --

    try:
        c.execute('SELECT LastUpdated from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN LastUpdated TEXT')

    try:
        c.execute('SELECT QUALalt_vers from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN QUALalt_vers TEXT')

    try:
        c.execute('SELECT QUALtype from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN QUALtype TEXT')

    try:
        c.execute('SELECT QUALscanner from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN QUALscanner TEXT')

    try:
        c.execute('SELECT QUALquality from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN QUALquality TEXT')

    try:
        c.execute('SELECT AlternateSearch from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN AlternateSearch TEXT')

    try:
        c.execute('SELECT ComicVersion from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ComicVersion TEXT')

    try:
        c.execute('SELECT SortOrder from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN SortOrder INTEGER')

    try:
        c.execute('SELECT UseFuzzy from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN UseFuzzy TEXT')

    try:
        c.execute('SELECT DetailURL from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN DetailURL TEXT')

    try:
        c.execute('SELECT ForceContinuing from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ForceContinuing INTEGER')

    try:
        c.execute('SELECT ComicName_Filesafe from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ComicName_Filesafe TEXT')

    try:
        c.execute('SELECT AlternateFileName from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN AlternateFileName TEXT')

    try:
        c.execute('SELECT ComicImageURL from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ComicImageURL TEXT')

    try:
        c.execute('SELECT ComicImageALTURL from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ComicImageALTURL TEXT')

    try:
        c.execute('SELECT NewPublish from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN NewPublish TEXT')

    # -- Issues Table --

    try:
        c.execute('SELECT ComicSize from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN ComicSize TEXT')

    try:
        c.execute('SELECT inCacheDir from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN inCacheDIR TEXT')

    try:
        c.execute('SELECT AltIssueNumber from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN AltIssueNumber TEXT')

    try:
        c.execute('SELECT IssueDate_Edit from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN IssueDate_Edit TEXT')


    ## -- ImportResults Table --

    try:
        c.execute('SELECT WatchMatch from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN WatchMatch TEXT')

    try:
        c.execute('SELECT IssueCount from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN IssueCount TEXT')

    try:
        c.execute('SELECT ComicLocation from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN ComicLocation TEXT')

    try:
        c.execute('SELECT ComicFilename from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN ComicFilename TEXT')

    try:
        c.execute('SELECT impID from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN impID TEXT')

    try:
        c.execute('SELECT implog from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN implog TEXT')

    try:
        c.execute('SELECT DisplayName from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN DisplayName TEXT')

    try:
        c.execute('SELECT SRID from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN SRID TEXT')

    try:
        c.execute('SELECT ComicID from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN ComicID TEXT')

    try:
        c.execute('SELECT IssueID from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN IssueID TEXT')

    try:
        c.execute('SELECT Volume from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN Volume TEXT')
    ## -- Readlist Table --

    try:
        c.execute('SELECT inCacheDIR from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN inCacheDIR TEXT')

    try:
        c.execute('SELECT Location from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN Location TEXT')

    try:
        c.execute('SELECT IssueDate from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN IssueDate TEXT')

    try:
        c.execute('SELECT SeriesYear from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN SeriesYear TEXT')

    try:
        c.execute('SELECT ComicID from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN ComicID TEXT')

    try:
        c.execute('SELECT StatusChange from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN StatusChange TEXT')

    ## -- Weekly Table --

    try:
        c.execute('SELECT ComicID from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN ComicID TEXT')

    try:
        c.execute('SELECT IssueID from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN IssueID TEXT')

    ## -- Nzblog Table --

    try:
        c.execute('SELECT SARC from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN SARC TEXT')

    try:
        c.execute('SELECT PROVIDER from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN PROVIDER TEXT')

    try:
        c.execute('SELECT ID from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN ID TEXT')

    try:
        c.execute('SELECT AltNZBName from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN AltNZBName TEXT')

    ## -- Annuals Table --

    try:
        c.execute('SELECT Location from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN Location TEXT')

    try:
        c.execute('SELECT ComicSize from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ComicSize TEXT')

    try:
        c.execute('SELECT Int_IssueNumber from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN Int_IssueNumber INT')

    try:
        c.execute('SELECT ComicName from annuals')
        annual_update = "no"
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ComicName TEXT')
        annual_update = "yes"

    if annual_update == "yes":
        logger.info("Updating Annuals table for new fields - one-time update.")
        helpers.annual_update()

    try:
        c.execute('SELECT ReleaseDate from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ReleaseDate TEXT')

    try:
        c.execute('SELECT ReleaseComicID from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ReleaseComicID TEXT')

    try:
        c.execute('SELECT ReleaseComicName from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ReleaseComicName TEXT')

    try:
        c.execute('SELECT IssueDate_Edit from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN IssueDate_Edit TEXT')


    ## -- Snatched Table --

    try:
        c.execute('SELECT Provider from snatched')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE snatched ADD COLUMN Provider TEXT')


    ## -- Upcoming Table --

    try:
        c.execute('SELECT DisplayComicName from upcoming')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE upcoming ADD COLUMN DisplayComicName TEXT')


    ## -- Readinglist Table --

    try:
        c.execute('SELECT ComicID from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN ComicID TEXT')

    try:
        c.execute('SELECT StoreDate from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN StoreDate TEXT')

    try:
        c.execute('SELECT IssueDate from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN IssueDate TEXT')

    try:
        c.execute('SELECT Publisher from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN Publisher TEXT')

    try:
        c.execute('SELECT IssuePublisher from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN IssuePublisher TEXT')

    try:
        c.execute('SELECT IssueName from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN IssueName TEXT')

    try:
        c.execute('SELECT CV_ArcID from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN CV_ArcID TEXT')

    try:
        c.execute('SELECT Int_IssueNumber from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN Int_IssueNumber INT')

    ## -- searchresults Table --
    try:
        c.execute('SELECT SRID from searchresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE searchresults ADD COLUMN SRID TEXT')

    try:
        c.execute('SELECT Series from searchresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE searchresults ADD COLUMN Series TEXT')

    try:
        c.execute('SELECT sresults from searchresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE searchresults ADD COLUMN sresults TEXT')

    try:
        c.execute('SELECT ogcname from searchresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE searchresults ADD COLUMN ogcname TEXT')

    ## -- Failed Table --
    try:
        c.execute('SELECT DateFailed from Failed')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE Failed ADD COLUMN DateFailed TEXT')

    #if it's prior to Wednesday, the issue counts will be inflated by one as the online db's everywhere
    #prepare for the next 'new' release of a series. It's caught in updater.py, so let's just store the
    #value in the sql so we can display it in the details screen for everyone to wonder at.
    try:
        c.execute('SELECT not_updated_db from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN not_updated_db TEXT')

# -- not implemented just yet ;)

    # for metadata...
    # MetaData_Present will be true/false if metadata is present
    # MetaData will hold the MetaData itself in tuple format
#    try:
#        c.execute('SELECT MetaData_Present from comics')
#    except sqlite3.OperationalError:
#        c.execute('ALTER TABLE importresults ADD COLUMN MetaData_Present TEXT')

#    try:
#        c.execute('SELECT MetaData from importresults')
#    except sqlite3.OperationalError:
#        c.execute('ALTER TABLE importresults ADD COLUMN MetaData TEXT')

    #let's delete errant comics that are stranded (ie. Comicname = Comic ID: )
    c.execute("DELETE from comics WHERE ComicName='None' OR ComicName LIKE 'Comic ID%' OR ComicName is NULL")
    c.execute("DELETE from issues WHERE ComicName='None' OR ComicName LIKE 'Comic ID%' OR ComicName is NULL")
    c.execute("DELETE from annuals WHERE ComicName='None' OR ComicName is NULL or Issue_Number is NULL")
    c.execute("DELETE from upcoming WHERE ComicName='None' OR ComicName is NULL or IssueNumber is NULL")
    c.execute("DELETE from importresults WHERE ComicName='None' OR ComicName is NULL")
    logger.info('Ensuring DB integrity - Removing all Erroneous Comics (ie. named None)')

    logger.info('Correcting Null entries that make the main page break on startup.')
    c.execute("UPDATE Comics SET LatestDate='Unknown' WHERE LatestDate='None' or LatestDate is NULL")

    conn.commit()
    c.close()

def csv_load():
    # for redudant module calls..include this.
    conn = sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute('DROP TABLE IF EXISTS exceptions')

    c.execute('CREATE TABLE IF NOT EXISTS exceptions (variloop TEXT, ComicID TEXT, NewComicID TEXT, GComicID TEXT)')

    # for Mylar-based Exception Updates....
    i = 0
    EXCEPTIONS = []
    EXCEPTIONS.append('exceptions.csv')
    EXCEPTIONS.append('custom_exceptions.csv')

    while (i <= 1):
    #EXCEPTIONS_FILE = os.path.join(DATA_DIR, 'exceptions.csv')
        EXCEPTIONS_FILE = os.path.join(DATA_DIR, EXCEPTIONS[i])

        if not os.path.exists(EXCEPTIONS_FILE):
            try:
                csvfile = open(str(EXCEPTIONS_FILE), "rb")
            except (OSError, IOError):
                if i == 1:
                    logger.info('No Custom Exceptions found - Using base exceptions only. Creating blank custom_exceptions for your personal use.')
                    try:
                        shutil.copy(os.path.join(DATA_DIR, "custom_exceptions_sample.csv"), EXCEPTIONS_FILE)
                    except (OSError, IOError):
                        logger.error('Cannot create custom_exceptions.csv in ' + str(DATA_DIR) + '. Make sure _sample.csv is present and/or check permissions.')
                        return
                else:
                    logger.error('Could not locate ' + str(EXCEPTIONS[i]) + ' file. Make sure it is in datadir: ' + DATA_DIR)
                break
        else:
            csvfile = open(str(EXCEPTIONS_FILE), "rb")
        if i == 0:
            logger.info('Populating Base Exception listings into Mylar....')
        elif i == 1:
            logger.info('Populating Custom Exception listings into Mylar....')

        creader = csv.reader(csvfile, delimiter=',')

        for row in creader:
            try:
                #print row.split(',')
                c.execute("INSERT INTO exceptions VALUES (?,?,?,?)", row)
            except Exception, e:
                #print ("Error - invald arguments...-skipping")
                pass
        csvfile.close()
        i+=1

    conn.commit()
    c.close()

def halt():
    global __INITIALIZED__, dbUpdateScheduler, seachScheduler, RSSScheduler, WeeklyScheduler, \
        VersionScheduler, FolderMonitorScheduler, started

    with INIT_LOCK:

        if __INITIALIZED__:

            logger.info(u"Aborting all threads")

            # abort all the threads

            dbUpdateScheduler.abort = True
            logger.info(u"Waiting for the DB UPDATE thread to exit")
            try:
                dbUpdateScheduler.thread.join(10)
            except:
                pass

            searchScheduler.abort = True
            logger.info(u"Waiting for the SEARCH thread to exit")
            try:
                searchScheduler.thread.join(10)
            except:
                pass

            RSSScheduler.abort = True
            logger.info(u"Waiting for the RSS CHECK thread to exit")
            try:
                RSSScheduler.thread.join(10)
            except:
                pass

            WeeklyScheduler.abort = True
            logger.info(u"Waiting for the WEEKLY CHECK thread to exit")
            try:
                WeeklyScheduler.thread.join(10)
            except:
                pass

            VersionScheduler.abort = True
            logger.info(u"Waiting for the VERSION CHECK thread to exit")
            try:
                VersionScheduler.thread.join(10)
            except:
                pass

            FolderMonitorScheduler.abort = True
            logger.info(u"Waiting for the FOLDER MONITOR thread to exit")
            try:
                FolderMonitorScheduler.thread.join(10)
            except:
                pass

            __INITIALIZED__ = False

def shutdown(restart=False, update=False):

    halt()

    cherrypy.engine.exit()

    SCHED.shutdown(wait=False)

    config_write()

    if not restart and not update:
        logger.info('Mylar is shutting down...')
    if update:
        logger.info('Mylar is updating...')
        try:
            versioncheck.update()
        except Exception, e:
            logger.warn('Mylar failed to update: %s. Restarting.' % e)

    if CREATEPID:
        logger.info('Removing pidfile %s' % PIDFILE)
        os.remove(PIDFILE)

    if restart:
        logger.info('Mylar is restarting...')
        popen_list = [sys.executable, FULL_PATH]
        popen_list += ARGS
        if '--nolaunch' not in popen_list:
            popen_list += ['--nolaunch']
        logger.info('Restarting Mylar with ' + str(popen_list))
        subprocess.Popen(popen_list, cwd=os.getcwd())

    os._exit(0)
