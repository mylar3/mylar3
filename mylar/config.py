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

import itertools
from collections import OrderedDict
from operator import itemgetter

import os
import errno
import glob
import json
import codecs
import shutil
import re
import configparser
from pathlib import Path
import mylar
from mylar import logger, helpers, encrypted, filechecker, db, maintenance

config = configparser.ConfigParser()

_CONFIG_DEFINITIONS = OrderedDict({
     #keyname, type, section, default
    'CONFIG_VERSION': (int, 'General', 6),
    'MINIMAL_INI': (bool, 'General', False),
    'AUTO_UPDATE': (bool, 'General', False),
    'CACHE_DIR': (str, 'General', None),
    'DYNAMIC_UPDATE': (int, 'General', 0),
    'REFRESH_CACHE': (int, 'General', 7),
    'ANNUALS_ON': (bool, 'General', False),
    'SYNO_FIX': (bool, 'General', False),
    'LAUNCH_BROWSER' : (bool, 'General', False),
    'WANTED_TAB_OFF': (bool, 'General', False),
    'ENABLE_RSS': (bool, 'General', False),
    'SEARCH_DELAY' : (int, 'General', 1),
    'GRABBAG_DIR': (str, 'General', None),
    'HIGHCOUNT': (int, 'General', 0),
    'MAINTAINSERIESFOLDER': (bool, 'General', False),
    'DESTINATION_DIR': (str, 'General', None),   #if M_D_D_ is enabled, this will be the DEFAULT for writing
    'MULTIPLE_DEST_DIRS': (str, 'General', None), #Nothing will ever get written to these dirs - just for scanning, unless it's metatagging/renaming.
    'CREATE_FOLDERS': (bool, 'General', True),
    'DELETE_REMOVE_DIR': (bool, 'General', False),
    'UPCOMING_SNATCHED': (bool, 'General', True),
    'UPDATE_ENDED': (bool, 'General', False),
    'NEWCOM_DIR': (str, 'General', None),
    'FFTONEWCOM_DIR': (bool, 'General', False),
    'FOLDER_SCAN_LOG_VERBOSE': (bool, 'General', False),
    'INTERFACE': (str, 'General', 'carbon'),
    'CORRECT_METADATA': (bool, 'General', False),
    'MOVE_FILES': (bool, 'General', False),
    'RENAME_FILES': (bool, 'General', False),
    'FOLDER_FORMAT': (str, 'General', '$Series ($Year)'),
    'FILE_FORMAT': (str, 'General', '$Series $Annual $Issue ($Year)'),
    'REPLACE_SPACES': (bool, 'General', False),
    'REPLACE_CHAR': (str, 'General', None),
    'ZERO_LEVEL': (bool, 'General', False),
    'ZERO_LEVEL_N': (str, 'General', None),
    'LOWERCASE_FILENAMES': (bool, 'General', False),
    'IGNORE_HAVETOTAL': (bool, 'General', False),
    'IGNORE_TOTAL': (bool, 'General', False),
    'IGNORE_COVERS': (bool, 'General', True),
    'SNATCHED_HAVETOTAL': (bool, 'General', False),
    'FAILED_DOWNLOAD_HANDLING': (bool, 'General', False),
    'FAILED_AUTO': (bool, 'General',False),
    'PREFERRED_QUALITY': (int, 'General', 0),
    'IGNORE_SEARCH_WORDS': (str, 'General', []),
    'USE_MINSIZE': (bool, 'General', False),
    'MINSIZE': (str, 'General', None),
    'USE_MAXSIZE': (bool, 'General', False),
    'MAXSIZE': (str, 'General', None),
    'AUTOWANT_UPCOMING': (bool, 'General', True),
    'AUTOWANT_ALL': (bool, 'General', False),
    'COMIC_COVER_LOCAL': (bool, 'General', False),
    'SERIES_METADATA_LOCAL': (bool, 'General', False),
    'SERIESJSON_FILE_PRIORITY': (bool, 'General', False),
    'COVER_FOLDER_LOCAL': (bool, 'General', False),
    'ADD_TO_CSV': (bool, 'General', True),
    'SKIPPED2WANTED': (bool, 'General', False),
    'READ2FILENAME': (bool, 'General', False),
    'SEND2READ': (bool, 'General', False),
    'NZB_STARTUP_SEARCH': (bool, 'General', False),
    'UNICODE_ISSUENUMBER': (bool, 'General', False),
    'CREATE_FOLDERS': (bool, 'General', True),
    'ALTERNATE_LATEST_SERIES_COVERS': (bool, 'General', False),
    'SHOW_ICONS': (bool, 'General', False),
    'FORMAT_BOOKTYPE': (bool, 'General', True),
    'CLEANUP_CACHE': (bool, 'General', True),
    'CLEANUP_STRAYS': (bool, 'General', False),
    'SECURE_DIR': (str, 'General', None),
    'ENCRYPT_PASSWORDS': (bool, 'General', False),
    'BACKUP_ON_START': (bool, 'General', False),
    'BACKUP_LOCATION': (str, 'General', None),
    'BACKUP_RETENTION': (int, 'General', 4),
    'BACKFILL_LENGTH': (int, 'General', 8),  # weeks
    'BACKFILL_TIMESPAN': (int, 'General', 10),   # minutes
    'PROBLEM_DATES': (str, 'General', []),
    'PROBLEM_DATES_SECONDS': (int, 'General', 60),
    'DEFAULT_DATES': (str, 'General', 'store_date'),
    'FOLDER_CACHE_LOCATION': (str, 'General', None),
    'SCAN_ON_SERIES_CHANGES': (bool, 'General', True),
    'CLEAR_PROVIDER_TABLE': (bool, 'General', False),
    'SEARCH_TIER_CUTOFF': (int, 'General', 14), # days
    'CUSTOM_ISSUE_EXCEPTIONS': (str, 'General', []),

    'RSS_CHECKINTERVAL': (int, 'Scheduler', 20),
    'SEARCH_INTERVAL': (int, 'Scheduler', 1440),
    'DOWNLOAD_SCAN_INTERVAL': (int, 'Scheduler', 5),
    'CHECK_GITHUB_INTERVAL' : (int, 'Scheduler', 360),
    'BLOCKLIST_TIMER': (int, 'Scheduler', 3600),

    'ALT_PULL' : (int, 'Weekly', 2),
    'PULL_REFRESH': (str, 'Weekly', None),
    'WEEKFOLDER': (bool, 'Weekly', False),
    'WEEKFOLDER_LOC': (str, 'Weekly', None),
    'WEEKFOLDER_FORMAT': (int, 'Weekly', 0),
    'INDIE_PUB': (int, 'Weekly', 75),
    'BIGGIE_PUB': (int, 'Weekly', 55),
    'PACK_0DAY_WATCHLIST_ONLY': (bool, 'Weekly', True),
    'RESET_PULLIST_PAGINATION': (bool, 'Weekly', True),
    'MASS_PUBLISHERS': (str, 'Weekly', []),
    'AUTO_MASS_ADD': (bool, 'Weekly', False),

    'HTTP_PORT' : (int, 'Interface', 8090),
    'HTTP_HOST' : (str, 'Interface', '0.0.0.0'),
    'HTTP_USERNAME' : (str, 'Interface', None),
    'HTTP_PASSWORD' : (str, 'Interface', None),
    'HTTP_ROOT' : (str, 'Interface', '/'),
    'ENABLE_HTTPS' : (bool, 'Interface', False),
    'HTTPS_CERT' : (str, 'Interface', None),
    'HTTPS_KEY' : (str, 'Interface', None),
    'HTTPS_CHAIN' : (str, 'Interface', None),
    'HTTPS_FORCE_ON' : (bool, 'Interface', False),
    'HOST_RETURN' : (str, 'Interface', None),
    'AUTHENTICATION' : (int, 'Interface', 0),
    'LOGIN_TIMEOUT': (int, 'Interface', 43800),
    'ALPHAINDEX': (bool, 'Interface', True),
    'CHERRYPY_LOGGING': (bool, 'Interface', False),
    'INSTANCE_NAME': (str, 'Interface', None),

    'API_ENABLED' : (bool, 'API', False),
    'API_KEY' : (str, 'API', None),

    'CVAPI_RATE' : (int, 'CV', 2),
    'COMICVINE_API': (str, 'CV', None),
    'IGNORED_PUBLISHERS' : (str, 'CV', ""),
    'CV_VERIFY': (bool, 'CV', True),
    'CV_ONLY': (bool, 'CV', True),
    'CV_ONETIMER': (bool, 'CV', True),
    'CVINFO': (bool, 'CV', False),
    'CV_USER_AGENT': (str, 'CV', 'comictagger image fetcher'),
    'IMPRINT_MAPPING_TYPE': (str, 'CV', 'CV'),  # either 'CV' for ComicVine or 'JSON' for imprints.json to choose which naming to use for imprints

    'LOG_DIR' : (str, 'Logs', None),
    'MAX_LOGSIZE' : (int, 'Logs', 10000000),
    'MAX_LOGFILES': (int, 'Logs', 5),
    'LOG_LEVEL': (int, 'Logs', 1),

    'GIT_PATH' : (str, 'Git', None),
    'GIT_USER' : (str, 'Git', 'mylar3'),
    'GIT_TOKEN' : (str, 'Git', None),
    'GIT_BRANCH' : (str, 'Git', None),
    'CHECK_GITHUB' : (bool, 'Git', False),
    'CHECK_GITHUB_ON_STARTUP' : (bool, 'Git', False),

    'ENFORCE_PERMS': (bool, 'Perms', False),
    'CHMOD_DIR': (str, 'Perms', '0777'),
    'CHMOD_FILE': (str, 'Perms', '0660'),
    'CHOWNER': (str, 'Perms', None),
    'CHGROUP': (str, 'Perms', None),

    'ADD_COMICS': (bool, 'Import', False),
    'COMIC_DIR': (str, 'Import', None),
    'IMP_MOVE': (bool, 'Import', False),
    'IMP_PATHS': (bool, 'Import', False),
    'IMP_RENAME': (bool, 'Import', False),
    'IMP_METADATA': (bool, 'Import', False),  # should default to False - this is enabled for testing only.
    'IMP_SERIESFOLDERS': (bool, 'Import', True),

    'DUPECONSTRAINT': (str, 'Duplicates', None),
    'DDUMP': (bool, 'Duplicates', False),
    'DUPLICATE_DUMP': (str, 'Duplicates', None),
    'DUPLICATE_DATED_FOLDERS': (bool, 'Duplicates', False),

    'PROWL_ENABLED': (bool, 'Prowl', False),
    'PROWL_PRIORITY': (int, 'Prowl', 0),
    'PROWL_KEYS': (str, 'Prowl', None),
    'PROWL_ONSNATCH': (bool, 'Prowl', False),

    'PUSHOVER_ENABLED': (bool, 'PUSHOVER', False),
    'PUSHOVER_PRIORITY': (int, 'PUSHOVER', 0),
    'PUSHOVER_APIKEY': (str, 'PUSHOVER', None),
    'PUSHOVER_DEVICE': (str, 'PUSHOVER', None),
    'PUSHOVER_USERKEY': (str, 'PUSHOVER', None),
    'PUSHOVER_ONSNATCH': (bool, 'PUSHOVER', False),
    'PUSHOVER_IMAGE': (bool, 'PUSHOVER', False),

    'BOXCAR_ENABLED': (bool, 'BOXCAR', False),
    'BOXCAR_ONSNATCH': (bool, 'BOXCAR', False),
    'BOXCAR_TOKEN': (str, 'BOXCAR', None),

    'PUSHBULLET_ENABLED': (bool, 'PUSHBULLET', False),
    'PUSHBULLET_APIKEY': (str, 'PUSHBULLET', None),
    'PUSHBULLET_DEVICEID': (str, 'PUSHBULLET', None),
    'PUSHBULLET_CHANNEL_TAG': (str, 'PUSHBULLET', None),
    'PUSHBULLET_ONSNATCH': (bool, 'PUSHBULLET', False),

    'TELEGRAM_ENABLED': (bool, 'TELEGRAM', False),
    'TELEGRAM_TOKEN': (str, 'TELEGRAM', None),
    'TELEGRAM_USERID': (str, 'TELEGRAM', None),
    'TELEGRAM_ONSNATCH': (bool, 'TELEGRAM', False),
    'TELEGRAM_IMAGE': (bool, 'TELEGRAM', False),

    'SLACK_ENABLED': (bool, 'SLACK', False),
    'SLACK_WEBHOOK_URL': (str, 'SLACK', None),
    'SLACK_ONSNATCH': (bool, 'SLACK', False),

    'MATTERMOST_ENABLED': (bool, 'MATTERMOST', False),
    'MATTERMOST_WEBHOOK_URL': (str, 'MATTERMOST', None),
    'MATTERMOST_ONSNATCH': (bool, 'MATTERMOST', False),

    'DISCORD_ENABLED': (bool, 'DISCORD', False),
    'DISCORD_WEBHOOK_URL': (str, 'DISCORD', None),
    'DISCORD_ONSNATCH': (bool, 'DISCORD', False),

    'EMAIL_ENABLED': (bool, 'Email', False),
    'EMAIL_FROM': (str, 'Email', ''),
    'EMAIL_TO': (str, 'Email', ''),
    'EMAIL_SERVER': (str, 'Email', ''),
    'EMAIL_USER': (str, 'Email', ''),
    'EMAIL_PASSWORD': (str, 'Email', ''),
    'EMAIL_PORT': (int, 'Email', 25),
    'EMAIL_ENC': (int, 'Email', 0),
    'EMAIL_ONGRAB': (bool, 'Email', True),
    'EMAIL_ONPOST': (bool, 'Email', True),

    'GOTIFY_ENABLED': (bool, 'GOTIFY', False),
    'GOTIFY_SERVER_URL': (str, 'GOTIFY', None),
    'GOTIFY_TOKEN': (str, 'GOTIFY', None),
    'GOTIFY_ONSNATCH': (bool, 'GOTIFY', False),

    'POST_PROCESSING': (bool, 'PostProcess', True),
    'FILE_OPTS': (str, 'PostProcess', 'move'),
    'SNATCHEDTORRENT_NOTIFY': (bool, 'PostProcess', False),
    'LOCAL_TORRENT_PP': (bool, 'PostProcess', False),
    'POST_PROCESSING_SCRIPT': (str, 'PostProcess', None),
    'PP_SHELL_LOCATION': (str, 'PostProcess', None),
    'ENABLE_EXTRA_SCRIPTS': (bool, 'PostProcess', False),
    'ES_SHELL_LOCATION': (str, 'PostProcess', None),
    'EXTRA_SCRIPTS': (str, 'PostProcess', None),
    'ENABLE_SNATCH_SCRIPT': (bool, 'PostProcess', False),
    'SNATCH_SHELL_LOCATION': (str, 'PostProcess', None),
    'SNATCH_SCRIPT': (str, 'PostProcess', None),
    'ENABLE_PRE_SCRIPTS': (bool, 'PostProcess', False),
    'PRE_SHELL_LOCATION': (str, 'PostProcess', None),
    'PRE_SCRIPTS': (str, 'PostProcess', None),
    'ENABLE_CHECK_FOLDER':  (bool, 'PostProcess', False),
    'CHECK_FOLDER': (str, 'PostProcess', None),
    'MANUAL_PP_FOLDER': (str, 'PostProcess', None),
    'FOLDER_CACHE_LOCATION': (str, 'PostProcess', None),

    'PROVIDER_ORDER': (str, 'Providers', None),
    'USENET_RETENTION': (int, 'Providers', 3500),

    'NZB_DOWNLOADER': (int, 'Client', 3),  #0': sabnzbd, #1': nzbget, #2': blackhole, #3': none(default)
    'TORRENT_DOWNLOADER': (int, 'Client', 0),  #0': watchfolder, #1': uTorrent, #2': rTorrent, #3': transmission, #4': deluge, #5': qbittorrent

    'SAB_HOST': (str, 'SABnzbd', None),
    'SAB_USERNAME': (str, 'SABnzbd', None),
    'SAB_PASSWORD': (str, 'SABnzbd', None),
    'SAB_APIKEY': (str, 'SABnzbd', None),
    'SAB_CATEGORY': (str, 'SABnzbd', None),
    'SAB_PRIORITY': (str, 'SABnzbd', "Default"),
    'SAB_TO_MYLAR': (bool, 'SABnzbd', False),
    'SAB_DIRECTORY': (str, 'SABnzbd', None),
    'SAB_VERSION': (str, 'SABnzbd', None),
    'SAB_MOVING_DELAY': (int, 'SABnzbd', 5),
    'SAB_CLIENT_POST_PROCESSING': (bool, 'SABnzbd', False),   #0/False: ComicRN.py, #1/True: Completed Download Handling
    'SAB_REMOVE_COMPLETED': (bool, 'SABnzbd', False),
    'SAB_REMOVE_FAILED': (bool, 'SABnzbd', False),


    'NZBGET_HOST': (str, 'NZBGet', None),
    'NZBGET_SUB': (str, 'NZBGet', None),
    'NZBGET_PORT': (str, 'NZBGet', None),
    'NZBGET_USERNAME': (str, 'NZBGet', None),
    'NZBGET_PASSWORD': (str, 'NZBGet', None),
    'NZBGET_PRIORITY': (str, 'NZBGet', None),
    'NZBGET_CATEGORY': (str, 'NZBGet', None),
    'NZBGET_DIRECTORY': (str, 'NZBGet', None),
    'NZBGET_CLIENT_POST_PROCESSING': (bool, 'NZBGet', False),   #0/False: ComicRN.py, #1/True: Completed Download Handling

    'BLACKHOLE_DIR': (str, 'Blackhole', None),

    'NEWZNAB': (bool, 'Newznab', False),
    'EXTRA_NEWZNABS': (str, 'Newznab', ""),

    'ENABLE_TORZNAB': (bool, 'Torznab', False),
    'EXTRA_TORZNABS': (str, 'Torznab', ""),
    'TORZNAB_NAME': (str, 'Torznab', None),
    'TORZNAB_HOST': (str, 'Torznab', None),
    'TORZNAB_APIKEY': (str, 'Torznab', None),
    'TORZNAB_CATEGORY': (str, 'Torznab', None),
    'TORZNAB_VERIFY': (bool, 'Torznab', False),

    'EXPERIMENTAL': (bool, 'Experimental', False),
    'ALTEXPERIMENTAL': (bool, 'Experimental', False),

    'TAB_ENABLE': (bool, 'Tablet', False),
    'TAB_HOST': (str, 'Tablet', None),
    'TAB_USER': (str, 'Tablet', None),
    'TAB_PASS': (str, 'Tablet', None),
    'TAB_DIRECTORY': (str, 'Tablet', None),

    'STORYARCDIR': (bool, 'StoryArc', False),
    'STORYARC_LOCATION': (str, 'StoryArc', None),
    'COPY2ARCDIR': (bool, 'StoryArc', False),
    'ARC_FOLDERFORMAT': (str, 'StoryArc', '$arc ($spanyears)'),
    'ARC_FILEOPS': (str, 'StoryArc', 'copy'),
    'ARC_FILEOPS_SOFTLINK_RELATIVE': (bool, 'StoryArc', False),
    'UPCOMING_STORYARCS': (bool, 'StoryArc', False),
    'SEARCH_STORYARCS': (bool, 'StoryArc', False),

    'LOCMOVE': (bool, 'Update', False),
    'NEWCOM_DIR': (str, 'Update', None),
    'FFTONEWCOM_DIR': (bool, 'Update', False),

    'ENABLE_META': (bool, 'Metatagging', False),
    'CMTAGGER_PATH': (str, 'Metatagging', None),
    'CBR2CBZ_ONLY': (bool, 'Metatagging', False),
    'CT_TAG_CR': (bool, 'Metatagging', True),
    'CT_TAG_CBL': (bool, 'Metatagging', False),
    'CT_CBZ_OVERWRITE': (bool, 'Metatagging', False),
    'UNRAR_CMD': (str, 'Metatagging', None),
    'CT_NOTES_FORMAT': (str, 'Metatagging', 'Issue ID'),
    'CT_SETTINGSPATH': (str, 'Metatagging', None),
    'CMTAG_VOLUME': (bool, 'Metatagging', True),
    'CMTAG_START_YEAR_AS_VOLUME': (bool, 'Metatagging', True),
    'SETDEFAULTVOLUME': (bool, 'Metatagging', False),
    'CV_BATCH_LIMIT_PROTECTION': (bool, 'Metatagging', True),
    'CV_BATCH_LIMIT_THRESHOLD': (int, 'Metatagging', 200),


    'ENABLE_TORRENTS': (bool, 'Torrents', False),
    'ENABLE_TORRENT_SEARCH': (bool, 'Torrents', False),
    'MINSEEDS': (int, 'Torrents', 0),
    'ENABLE_PUBLIC': (bool, 'Torrents', False),
    'PUBLIC_VERIFY': (bool, 'Torrents', True),

    'ENABLE_DDL': (bool, 'DDL', False),
    'ENABLE_GETCOMICS': (bool, 'DDL', False),
    'ENABLE_EXTERNAL_SERVER': (bool, 'DDL', False),
    'EXTERNAL_SERVER': (str, 'DDL', None),
    'EXTERNAL_USERNAME': (str, 'DDL', None),
    'EXTERNAL_APIKEY': (str, 'DDL', None),
    'PACK_PRIORITY': (bool, 'DDL', False),
    'DDL_QUERY_DELAY': (int, 'DDL', 15),
    'DDL_LOCATION': (str, 'DDL', None),
    'DDL_AUTORESUME': (bool, 'DDL', True),
    'DDL_PREFER_UPSCALED': (bool, 'DDL', True),
    'DDL_PRIORITY_ORDER': (str, 'DDL', []),
    'ENABLE_FLARESOLVERR': (bool, 'DDL', False),
    'FLARESOLVERR_URL': (str, 'DDL', None),
    'ENABLE_PROXY': (bool, 'DDL', False),
    'HTTP_PROXY': (str, 'DDL', None),
    'HTTPS_PROXY': (str, 'DDL', None),

    'ENABLE_AIRDCPP': (bool, 'DCPP', False),
    'AIRDCPP_HOST': (str, 'DCPP', ""),
    'AIRDCPP_USERNAME': (str, 'DCPP', ""),
    'AIRDCPP_PASSWORD': (str, 'DCPP', ""),
    'AIRDCPP_DOWNLOAD_DIR': (str, 'DCPP', ""),
    'AIRDCPP_HUBS': (str, 'DCPP', ""),
    'AIRDCPP_VERSION': (str, 'DCPP', ""),
    'AIRDCPP_ANNOUNCE_HUB': (str, 'DCPP', ""),
    'AIRDCPP_ANNOUNCE_BOTS': (str, 'DCPP', ""),

    'AUTO_SNATCH': (bool, 'AutoSnatch', False),
    'AUTO_SNATCH_SCRIPT': (str, 'AutoSnatch', None),
    'PP_SSHHOST': (str, 'AutoSnatch', None),
    'PP_SSHPORT': (str, 'AutoSnatch', 22),
    'PP_SSHUSER': (str, 'AutoSnatch', None),
    'PP_SSHPASSWD': (str, 'AutoSnatch', None),
    'PP_SSHLOCALCD': (str, 'AutoSnatch', None),
    'PP_SSHKEYFILE': (str, 'AutoSnatch', None),

    'TORRENT_LOCAL': (bool, 'Watchdir', False),
    'LOCAL_WATCHDIR': (str, 'Watchdir', None),
    'TORRENT_SEEDBOX': (bool, 'Seedbox', False),
    'SEEDBOX_HOST': (str, 'Seedbox', None),
    'SEEDBOX_PORT': (str, 'Seedbox', None),
    'SEEDBOX_USER': (str, 'Seedbox', None),
    'SEEDBOX_PASS': (str, 'Seedbox', None),
    'SEEDBOX_WATCHDIR': (str, 'Seedbox', None),

    'ENABLE_32P': (bool, '32P', False),
    'SEARCH_32P': (bool, '32P', False),   #0': use WS to grab torrent groupings, #1': use 32P to grab torrent groupings
    'DEEP_SEARCH_32P': (bool, '32P', False),  #0': do not take multiple search series results & use ref32p if available, #1=  search each search series result for valid $
    'MODE_32P': (bool, '32P', False),  #0': legacymode, #1': authmode
    'RSSFEED_32P': (str, '32P', None),
    'PASSKEY_32P': (str, '32P', None),
    'USERNAME_32P': (str, '32P', None),
    'PASSWORD_32P': (str, '32P', None),
    'VERIFY_32P': (bool, '32P', True),

    'RTORRENT_HOST': (str, 'Rtorrent', None),
    'RTORRENT_AUTHENTICATION': (str, 'Rtorrent', 'basic'),
    'RTORRENT_RPC_URL': (str, 'Rtorrent', None),
    'RTORRENT_SSL': (bool, 'Rtorrent', False),
    'RTORRENT_VERIFY': (bool, 'Rtorrent', False),
    'RTORRENT_CA_BUNDLE': (str, 'Rtorrent', None),
    'RTORRENT_USERNAME': (str, 'Rtorrent', None),
    'RTORRENT_PASSWORD': (str, 'Rtorrent', None),
    'RTORRENT_STARTONLOAD': (bool, 'Rtorrent', False),
    'RTORRENT_LABEL': (str, 'Rtorrent', None),
    'RTORRENT_DIRECTORY': (str, 'Rtorrent', None),

    'UTORRENT_HOST': (str, 'uTorrent', None),
    'UTORRENT_USERNAME': (str, 'uTorrent', None),
    'UTORRENT_PASSWORD': (str, 'uTorrent', None),
    'UTORRENT_LABEL': (str, 'uTorrent', None),

    'TRANSMISSION_HOST': (str, 'Transmission', None),
    'TRANSMISSION_USERNAME': (str, 'Transmission', None),
    'TRANSMISSION_PASSWORD': (str, 'Transmission', None),
    'TRANSMISSION_DIRECTORY': (str, 'Transmission', None),

    'DELUGE_HOST': (str, 'Deluge', None),
    'DELUGE_USERNAME': (str, 'Deluge', None),
    'DELUGE_PASSWORD': (str, 'Deluge', None),
    'DELUGE_LABEL': (str, 'Deluge', None),
    'DELUGE_PAUSE': (bool, 'Deluge', False),
    'DELUGE_DOWNLOAD_DIRECTORY': (str, 'Deluge', ""),
    'DELUGE_DONE_DIRECTORY': (str, 'Deluge', ""),

    'QBITTORRENT_HOST': (str, 'qBittorrent', None),
    'QBITTORRENT_USERNAME': (str, 'qBittorrent', None),
    'QBITTORRENT_PASSWORD': (str, 'qBittorrent', None),
    'QBITTORRENT_LABEL': (str, 'qBittorrent', None),
    'QBITTORRENT_FOLDER': (str, 'qBittorrent', None),
    'QBITTORRENT_LOADACTION': (str, 'qBittorrent', 'default'),   #default, force_start, paused

    'OPDS_ENABLE': (bool, 'OPDS', False),
    'OPDS_AUTHENTICATION': (bool, 'OPDS', False),
    'OPDS_ENDPOINT': (str, 'OPDS', 'opds'),
    'OPDS_USERNAME': (str, 'OPDS', None),
    'OPDS_PASSWORD': (str, 'OPDS', None),
    'OPDS_METAINFO': (bool, 'OPDS', False),
    'OPDS_PAGESIZE': (int, 'OPDS', 30),

    'CBL_IMPORT_ISSUESONLY' : (bool, 'CBLImport', True),
    'CBL_IMPORT_IGNOREARCHIVED' : (bool, 'CBLImport', False),

})

_BAD_DEFINITIONS = OrderedDict({
     #for those items that were in wrong sections previously, or sections that are no longer present...
     #using this method, old values are able to be transfered to the new config items properly.
     #keyname, section, oldkeyname
     #ie. 'TEST_VALUE': ('TEST', 'TESTVALUE')
    'SAB_CLIENT_POST_PROCESSING': ('SABnbzd', None),
    'ENABLE_PUBLIC': ('Torrents', 'ENABLE_TPSE'),
    'PUBLIC_VERIFY': ('Torrents', 'TPSE_VERIFY'),
    'IGNORED_PUBLISHERS': ('CV', 'BLACKLISTED_PUBLISHERS'),
    'NZBSU': ('NZBsu', 'nzbsu', bool, None),
    'NZBSU_UID': ('NZBsu', 'nzbsu_uid', str, None),
    'NZBSU_APIKEY': ('NZBsu', 'nzbsu_apikey', str, None),
    'NZBSU_VERIFY': ('NZBsu', 'nzbsu_verify', bool, None),
    'DOGNZB': ('DOGnzb', 'dognzb', bool, None),
    'DOGNZB_APIKEY': ('DOGnzb', 'dognzb_apikey', str, None),
    'DOGNZB_VERIFY': ('DOGnzb', 'dognzb_verify', bool, None),
    'ENABLE_AIRDCPP': ('DDL', 'enable_airdcpp', bool, None),
    'AIRDCPP_HOST': ('DDL', 'airdcpp_host', str, None),
    'AIRDCPP_USERNAME': ('DDL', 'airdcpp_username', str, None),
    'AIRDCPP_PASSWORD': ('DDL', 'airdcpp_password', str, None),
    'AIRDCPP_DOWNLOAD_DIR': ('DDL', 'airdcpp_download_dir', str, None),
    'AIRDCPP_HUBS': ('DDL', 'airdcpp_hubs', str, None),
    'AIRDCPP_VERSION': ('DDL', 'airdcpp_version', str, None),
    'AIRDCPP_ANNOUNCE_HUB': ('DDL', 'airdcpp_announce_hub', str, None),
    'AIRDCPP_ANNOUNCE_BOTS': ('DDL', 'airdcpp_announce_bots', str, None),
})

class Config(object):

    def __init__(self, config_file):
        # initalize the config...
        self._config_file = config_file
        self.WRITE_THE_CONFIG = False

    def config_vals(self, update=False):
        if update is False:
            if os.path.isfile(self._config_file):
                self.config = config.read_file(codecs.open(self._config_file, 'r', 'utf8')) #read(self._config_file)
                #check for empty config / new config
                count = sum(1 for line in open(self._config_file))
            else:
                count = 0

            #this is the current version at this particular point in time.
            self.newconfig = 15

            OLDCONFIG_VERSION = 0
            if count == 0:
                CONFIG_VERSION = 0
                MINIMALINI = False
            else:
                # get the config version first, since we need to know.
                try:
                    CONFIG_VERSION = config.getint('General', 'config_version')
                    OLDCONFIG_VERSION = CONFIG_VERSION
                except:
                    CONFIG_VERSION = 0
                    OLDCONFIG_VERSION = 0
                try:
                    MINIMALINI = config.getboolean('General', 'minimal_ini')
                except:
                    MINIMALINI = False

        setattr(self, 'CONFIG_VERSION', CONFIG_VERSION)
        setattr(self, 'OLDCONFIG_VERSION', OLDCONFIG_VERSION)
        setattr(self, 'MINIMAL_INI', MINIMALINI)

        config_values = []

        #this section retains values of variables that are no longer being saved to the ini
        #in case they are needed prior to wiping out things
        self.OLD_VALUES = {}
        for b, bv in _BAD_DEFINITIONS.items():
            if len(bv) == 4:  #removal of option...
                if bv[1] not in self.OLD_VALUES:
                    try:
                        if bv[2] == bool:
                             self.OLD_VALUES[bv[1]] = config.getboolean(bv[0], bv[1])
                        elif bv[2] == str:
                             self.OLD_VALUES[bv[1]] = config.get(bv[0], bv[1])
                        elif bv[2] == int:
                             self.OLD_VALUES[bv[1]] = config.getint(bv[0], bv[1])
                    except (configparser.NoSectionError, configparser.NoOptionError) as e:
                        pass

        for k,v in _CONFIG_DEFINITIONS.items():
            xv = []
            xv.append(k)
            for x in v:
                if x is None:
                    x = 'None'
                xv.append(x)
            value = self.check_setting(xv)

            for b, bv in _BAD_DEFINITIONS.items():
                try:
                    if all([config.has_section(bv[0]), any([b == k, bv[1] is None])]) and not config.has_option(xv[2],xv[0]):
                        cvs = xv
                        if bv[1] is None:
                            ckey = k
                        else:
                            ckey = bv[1]
                        corevalues = [ckey if x == 0 else x for x in cvs]
                        corevalues = [bv[1] if x == b else x for x in cvs]
                        value = self.check_setting(corevalues)
                        if config.has_section(bv[0]):
                            if bv[1] is None:
                                config.remove_option(bv[0], ckey.lower())
                                config.remove_section(bv[0])
                            else:
                                config.remove_option(bv[0], bv[1].lower())
                            self.WRITE_THE_CONFIG = True
                        break
                except:
                    pass

            if all([k != 'CONFIG_VERSION', k != 'MINIMAL_INI']):
                try:
                    if v[0] == str and any([value == "", value is None, len(value) == 0, value == 'None']):
                        value = v[2]
                except:
                    value = v[2]

                try:
                    if v[0] == bool:
                        value = self.argToBool(value)
                except:
                    value = self.argToBool(v[2])
                try:

                    if all([v[0] == int, str(value).isdigit()]):
                        value = int(value)
                except:
                    value = v[2]

                setattr(self, k, value)

                try:
                    #make sure interpolation isn't being used, so we can just escape the % character
                    if v[0] == str:
                        value = value.replace('%', '%%')
                except Exception as e:
                    pass

                #just to ensure defaults are properly set...
                if any([value is None, value == 'None']):
                    value = v[0](v[2])

                if all([self.MINIMAL_INI is True, str(value) != str(v[2])]) or self.MINIMAL_INI is False:
                    try:
                        config.add_section(v[1])
                    except configparser.DuplicateSectionError:
                        pass
                else:
                    try:
                        if config.has_section(v[1]):
                            config.remove_option(v[1], k.lower())
                    except configparser.NoSectionError:
                        continue

                if all([config.has_section(v[1]), self.MINIMAL_INI is False]) or all([self.MINIMAL_INI is True, str(value) != str(v[2]), config.has_section(v[1])]):
                    config.set(v[1], k.lower(), str(value))
                else:
                    try:
                        if config.has_section(v[1]):
                            config.remove_option(v[1], k.lower())
                        if len(dict(config.items(v[1]))) == 0:
                            config.remove_section(v[1])
                    except configparser.NoSectionError:
                        continue
            else:
                if self.CONFIG_VERSION != 0:
                    if k == 'CONFIG_VERSION':
                        config.remove_option('General', 'dbuser')
                        config.remove_option('General', 'dbpass')
                        config.remove_option('General', 'dbchoice')
                        config.remove_option('General', 'dbname')
                    elif k == 'MINIMAL_INI':
                        config.set(v[1], k.lower(), str(self.MINIMAL_INI))

    def read(self, startup=False):
        self.config_vals()

        if startup is True:
            if self.LOG_DIR is None:
                self.LOG_DIR = os.path.join(mylar.DATA_DIR, 'logs')

            if not os.path.exists(self.LOG_DIR):
                try:
                    os.makedirs(self.LOG_DIR)
                except OSError:
                    if not mylar.QUIET:
                        self.LOG_DIR = None
                        print('Unable to create the log directory. Logging to screen only.')

            # Start the logger, silence console logging if we need to
            # quick check to make sure log_level isn't just blank in the config
            if self.LOG_LEVEL is None:
                self.LOG_LEVEL = 1  #default it to INFO level (1) if not set.

            log_level = self.LOG_LEVEL
            if mylar.LOG_LEVEL is not None:
                log_level = mylar.LOG_LEVEL
                print('Logging level in config over-ridden by startup value. Logging level set to : %s' % (log_level))

            mylar.LOG_LEVEL = log_level # set this to the calculated log_leve value so that logs display fine in the GUI
            if logger.LOG_LANG.startswith('en'):
                logger.initLogger(console=not mylar.QUIET, log_dir=self.LOG_DIR, max_logsize=self.MAX_LOGSIZE, max_logfiles=self.MAX_LOGFILES, loglevel=log_level)
            else:
                logger.mylar_log.initLogger(loglevel=log_level, log_dir=self.LOG_DIR, max_logsize=self.MAX_LOGSIZE, max_logfiles=self.MAX_LOGFILES)

        if any([self.CONFIG_VERSION == 0, self.CONFIG_VERSION < self.newconfig]):
            if not self.BACKUP_LOCATION:
                # this is needed here since the configuration hasn't run to check the location value yet.
                self.BACKUP_LOCATION = os.path.join(mylar.DATA_DIR, 'backup')

            backupinfo = {'location': self.BACKUP_LOCATION,
                          'config_version': self.CONFIG_VERSION,
                          'backup_retention': self.BACKUP_RETENTION}
            cc = maintenance.Maintenance('backup')
            bcheck = cc.backup_files(cfg=True, dbs=False, backupinfo=backupinfo)

            if self.CONFIG_VERSION < 15:
                print('Attempting to update configuration..')
                #8-torznab multiple entries merged into extra_torznabs value
                #9-remote rtorrent ssl option
                #10-encryption of all keys/passwords.
                #11-provider ids
                #12-ddl seperation into multiple providers, new keys, update tables
                #13-remove dognzb and nzbsu as independent options (throw them under newznabs if present)
                #14-put airdcpp variables into it's own section (DCPP) instead of under the DDL section
                self.config_update()
            setattr(self, 'OLDCONFIG_VERSION', str(self.CONFIG_VERSION))
            setattr(self, 'CONFIG_VERSION', self.newconfig)
            config.set('General', 'CONFIG_VERSION', str(self.newconfig))
            self.writeconfig(startup=startup)
        else:
            if self.OLDCONFIG_VERSION != self.CONFIG_VERSION:
                setattr(self, 'OLDCONFIG_VERSION', str(self.CONFIG_VERSION))

        extra_newznabs, extra_torznabs = self.get_extras()
        setattr(self, 'EXTRA_NEWZNABS', extra_newznabs)
        setattr(self, 'EXTRA_TORZNABS', extra_torznabs)
        setattr(self, 'IGNORED_PUBLISHERS', self.get_ignored_pubs())

        if startup is False:
            # need to do provider sequence AFTER db check
            self.provider_sequence()
        self.configure(startup=startup)
        if self.WRITE_THE_CONFIG is True or startup is True:
            self.writeconfig(startup=startup)
        return self

    def config_update(self):
        logger.info('Updating Configuration from %s to %s' % (self.CONFIG_VERSION, self.newconfig))
        if self.CONFIG_VERSION < 8:
            logger.info('Checking for existing torznab configuration...')
            if not any([self.TORZNAB_NAME is None, self.TORZNAB_HOST is None, self.TORZNAB_APIKEY is None, self.TORZNAB_CATEGORY is None]):
                torznabs =[(self.TORZNAB_NAME, self.TORZNAB_HOST, self.TORZNAB_VERIFY, self.TORZNAB_APIKEY, self.TORZNAB_CATEGORY, str(int(self.ENABLE_TORZNAB)))]
                setattr(self, 'EXTRA_TORZNABS', torznabs)
                config.set('Torznab', 'EXTRA_TORZNABS', str(torznabs))
                logger.info('Successfully converted existing torznab for multiple configuration allowance. Removing old references.')
            else:
                logger.info('No existing torznab configuration found. Just removing old config references at this point..')
            config.remove_option('Torznab', 'torznab_name')
            config.remove_option('Torznab', 'torznab_host')
            config.remove_option('Torznab', 'torznab_verify')
            config.remove_option('Torznab', 'torznab_apikey')
            config.remove_option('Torznab', 'torznab_category')
            config.remove_option('Torznab', 'torznab_verify')
            logger.info('Successfully removed outdated config entries.')
        if self.newconfig < 9:
            #rejig rtorrent settings due to change.
            try:
                if all([self.RTORRENT_SSL is True, not self.RTORRENT_HOST.startswith('http')]):
                    self.RTORRENT_HOST = 'https://' + self.RTORRENT_HOST
                    config.set('Rtorrent', 'rtorrent_host', self.RTORRENT_HOST)
            except:
                pass
            config.remove_option('Rtorrent', 'rtorrent_ssl')
            logger.info('Successfully removed oudated config entries.')
        if self.newconfig < 10:
            #encrypt all passwords / apikeys / usernames in ini file.
            #leave non-ini items (ie. memory) as un-encrypted items.
            try:
                if self.ENCRYPT_PASSWORDS is True:
                    self.encrypt_items(mode='encrypt', updateconfig=True)
            except Exception as e:
                logger.error('Error: %s' % e)
            logger.info('Successfully updated config to version 10 ( password / apikey - .ini encryption )')
        #if self.CONFIG_VERSION < 11:
            #add ID to all providers as a way to better identify them
            #tmp_newznabs = self.EXTRA_NEWZNABS
            #n_cnt = 0
            #a_list = []
            #if len(tmp_newznabs) > 0:
            #    for i in tmp_newznabs:
            #        tmp_i = list(i)
            #        tmp_i.append(n_cnt)
            #        a_list.append(tuple(tmp_i))
            #        n_cnt +=1
            #setattr(self, 'EXTRA_NEWZNABS', a_list)
            #tmp_torznabs = self.EXTRA_TORZNABS
            #b_cnt = 0
            #b_list = []
            #if len(tmp_torznabs) > 0:
            #    for i in tmp_torznabs:
            #        tmp_i = list(i)
            #        tmp_i.append(b_cnt)
            #        b_list.append(tuple(tmp_i))
            #        b_cnt +=1
            #setattr(self, 'EXTRA_TORZNABS', b_list)

        if self.newconfig < 12:
            #change enable_ddl to be a true/false for multiple ddl providers
            #set enable_getcomics to True by default if that's the case.
            if self.ENABLE_DDL is True:
                self.ENABLE_GETCOMICS = True
                config.set('DDL', 'enable_getcomics', self.ENABLE_GETCOMICS)
            #tables will be updated by checking the OLDCONFIG_VERSION in __init__
            logger.info('Successfully updated config to version 12 ( multiple DDL provider option )')
        if self.newconfig < 15:
            # remove nzbsu and dognzb as individual options
            # if data exists already, add them as newznab options (if not already there or via Prowlarr)
            try:
                for chk_e in [self.OLD_VALUES['nzbsu_apikey'], self.OLD_VALUES['dognzb_apikey']]:
                    if chk_e is not None:
                        if chk_e[:5] == '^~$z$':
                            nz = encrypted.Encryptor(chk_e)
                            nz_stat = nz.decrypt_it()
                            if nz_stat['status'] is True:
                                if chk_e == self.OLD_VALUES['nzbsu_apikey']:
                                    self.OLD_VALUES['nzbsu_apikey'] = nz_stat['password']
                                else:
                                    self.OLD_VALUES['dognzb_apikey'] = nz_stat['password']
            except Exception as e:
                pass

            extra_newznabs, extra_torznabs = self.get_extras()
            enz = []
            dogs = []
            nzbsus = []
            try:
                ncnt = 0
                for en in extra_newznabs:
                    dognzb_found = nzbsu_found = False
                    ben = list(en)
                    if ben[1] is not None:
                        n_name = ben[0].lower()
                        if n_name is None:
                            n_name = ''
                        if ben[3][:5] == '^~$z$':
                            nz = encrypted.Encryptor(ben[3])
                            nz_stat = nz.decrypt_it()
                            if nz_stat['status'] is True:
                                ben[3] = nz_stat['password']

                        # prowlarr's url does not contain the actual url, hope the name contains it...
                        if 'nzb.su' in ben[1].lower() or (any(['nzb.su' in n_name.lower(), 'nzbsu' in re.sub(r'\s', '', n_name).lower()]) and 'prowlarr' in n_name.lower()):
                            nzbsus.append(tuple(ben))
                            nzbsu_found = True
                        elif 'dognzb' in ben[1].lower() or all(['dognzb' in re.sub(r'\s', '', n_name).lower(), 'prowlarr' in n_name.lower()]):
                            dogs.append(tuple(ben))
                            dognzb_found = True
                        if not any([dognzb_found, nzbsu_found]):
                            enz.append(tuple(ben))
                    ncnt +=1
            except Exception as e:
                logger.warn('error: %s' % e)

            try:
                if self.OLD_VALUES['nzbsu']:
                    mylar.PROVIDER_START_ID+=1
                    tsnzbsu = '' if self.OLD_VALUES['nzbsu_uid'] is None else self.OLD_VALUES['nzbsu_uid']
                    nzbsus.append(('nzb.su', 'https://api.nzb.su', '1', self.OLD_VALUES['nzbsu_apikey'], tsnzbsu, str(int(self.OLD_VALUES['nzbsu'])), mylar.PROVIDER_START_ID))
            except Exception as e:
                pass

            try:
                if self.OLD_VALUES['dognzb']:
                    mylar.PROVIDER_START_ID+=1
                    dogs.append(('DOGnzb', 'https://api.dognzb.cr', '1', self.OLD_VALUES['dognzb_apikey'], '', str(int(self.OLD_VALUES['dognzb'])), mylar.PROVIDER_START_ID))
            except Exception as e:
                pass

            #loop thru nzbsus and dogs entries and only keep one (in order of priority): Enabled, Prowlarr, newznab
            keep_nzbsu = None
            keep_dognzb = None
            keep_it = None
            kcnt = 0
            for ggg in [nzbsus, dogs]:
                for gg in sorted(ggg, key=itemgetter(5), reverse=True):
                    try:
                        if gg[5] == '1':
                            if gg[0] is not None:
                                if 'Prowlarr' in gg[0]:
                                    keep_it = gg
                        if keep_it is None and gg[0] is not None:
                            if 'Prowlarr' in gg[0]:
                                keep_it = gg
                        if keep_it is None:
                            keep_it = gg
                    except Exception as e:
                        logger.error('error: %s' % e)

                if kcnt == 0 and keep_it is not None:
                    enz.append(keep_it)
                    keep_nzbsu = keep_it
                elif kcnt == 1 and keep_it is not None:
                    enz.append(keep_it)
                    keep_dognzb = keep_it
                keep_it = None
                kcnt+=1

            try:
                config.remove_option('NZBsu', 'nzbsu')
                config.remove_option('NZBsu', 'nzbsu_uid')
                config.remove_option('NZBsu', 'nzbsu_apikey')
                config.remove_option('NZBsu', 'nzbsu_verify')
            except configparser.NoSectionError:
                pass
            else:
                config.remove_section('NZBsu')
            try:
                config.remove_option('DOGnzb', 'dognzb')
                config.remove_option('DOGnzb', 'dognzb_verify')
                config.remove_option('DOGnzb', 'dognzb_apikey')
            except configparser.NoSectionError:
                pass
            else:
                config.remove_section('DOGnzb')

            setattr(self, 'EXTRA_NEWZNABS', enz)
            setattr(self, 'EXTRA_TORZNABS', extra_torznabs)
            myDB = db.DBConnection()
            try:
                ccd = myDB.select("PRAGMA table_info(provider_searches)")
                if ccd:
                    chk_tbl = myDB.action("DELETE FROM provider_searches where id=102 or id=103")
            except Exception as e:
                #if the table doesn't exist yet, it'll get created after the config loads on new installs.
                pass

        if self.newconfig < 16:
            # move aircdpp settings into it's own section since it's technically not ddl
            dcpp_migrate_list = [('ENABLE_AIRDCPP', 'enable_airdcpp'),
                ('AIRDCPP_HOST', 'airdcpp_host'),
                ('AIRDCPP_USERNAME', 'airdcpp_username'),
                ('AIRDCPP_PASSWORD', 'airdcpp_password'),
                ('AIRDCPP_DOWNLOAD_DIR', 'airdcpp_download_dir'),
                ('AIRDCPP_HUBS', 'airdcpp_hubs'),
                ('AIRDCPP_VERSION', 'airdcpp_version'),
                ('AIRDCPP_ANNOUNCE_HUB', 'airdcpp_announce_hub'),
                ('AIRDCPP_ANNOUNCE_BOTS', 'airdcpp_announce_bots')]

            for dcp_attr, dcp_key in dcpp_migrate_list:
                if dcp_key in self.OLD_VALUES.keys():
                    setattr(self, dcp_attr, self.OLD_VALUES[dcp_key])
                    config.set('DCPP', dcp_key, str(getattr(self, dcp_attr)))

        logger.info('Configuration upgraded to version %s' % self.newconfig)

    def check_section(self, section, key):
        """ Check if INI section exists, if not create it """
        if config.has_section(section):
            return True
        else:
            return False

    def argToBool(self, argument):
        _arg = argument.strip().lower() if isinstance(argument, str) else argument
        if _arg in (1, '1', 'on', 'true', True):
            return True
        elif _arg in (0, '0', 'off', 'false', False):
            return False
        return argument

    def check_setting(self, key):
        """ Cast any value in the config to the right type or use the default """
        keyname = key[0].upper()
        inikey = key[0].lower()
        definition_type = key[1]
        section = key[2]
        default = key[3]
        myval = self.check_config(definition_type, section, inikey, default)
        if myval['status'] is False:
            if self.CONFIG_VERSION == 6 or (config.has_section('Torrents') and any([inikey == 'auto_snatch', inikey == 'auto_snatch_script'])):
                chkstatus = False
                if config.has_section('Torrents'):
                    myval = self.check_config(definition_type, 'Torrents', inikey, default)
                    if myval['status'] is True:
                        chkstatus = True
                        try:
                            config.remove_option('Torrents', inikey)
                        except configparser.NoSectionError:
                            pass
                if all([chkstatus is False, config.has_section('General')]):
                    myval = self.check_config(definition_type, 'General', inikey, default)
                    if myval['status'] is True:
                        config.remove_option('General', inikey)

                    else:
                        #print 'no key found in ini - setting to default value of %s' % definition_type(default)
                        #myval = {'value': definition_type(default)}
                        pass
            else:
                myval = {'value': definition_type(default)}
        #if all([myval['value'] is not None, myval['value'] != '', myval['value'] != 'None']):
           #if default != myval['value']:
           #    print '%s : %s' % (keyname, myval['value'])
           #else:
           #    print 'NEW CONFIGURATION SETTING %s : %s' % (keyname, myval['value'])
        return myval['value']

    def check_config(self, definition_type, section, inikey, default):
        try:
            if definition_type == str:
                myval = {'status': True, 'value': config.get(section, inikey)}
            elif definition_type == int:
                myval = {'status': True, 'value': config.getint(section, inikey)}
            elif definition_type == bool:
                myval = {'status': True, 'value': config.getboolean(section, inikey)}
        except Exception:
            if definition_type == str:
                try:
                    myval = {'status': True, 'value': config.get(section, inikey, raw=True)}
                except (configparser.NoSectionError, configparser.NoOptionError):
                    myval = {'status': False, 'value': None}
            else:
                myval = {'status': False, 'value': None}
        return myval

    def _define(self, name):
        key = name.upper()
        ini_key = name.lower()
        definition = _CONFIG_DEFINITIONS[key]
        if len(definition) == 3:
            definition_type, section, default = definition
        elif len(definition) == 4:
            definition_type, section, _, default = definition
        return key, definition_type, section, ini_key, default


    def process_kwargs(self, kwargs):
        """
        Given a big bunch of key value pairs, apply them to the ini.
        """
        for name, value in list(kwargs.items()):
            if not any([(name.startswith('newznab') and name[-1].isdigit()), name.startswith('torznab') and name[-1].isdigit(), name == 'ignore_search_words[]']):
                key, definition_type, section, ini_key, default = self._define(name)
                if definition_type == str:
                    try:
                        if any([value == "", value is None, len(value) == 0]):
                            value = default
                        else:
                            value = str(value)
                    except:
                        value = default
                try:
                    if definition_type == bool:
                        value = self.argToBool(value)
                except:
                    value = self.argToBool(default)
                try:
                    if all([definition_type == int, str(value).isdigit()]):
                        value = int(value)
                except:
                    value = default

                #just to ensure defaults are properly set...
                if any([value is None, value == 'None']):
                    value = definition_type(default)

                if key != 'MINIMAL_INI':
                    if value == 'None': nv = None
                    else: nv = definition_type(value)
                    setattr(self, key, nv)

                    #print('writing config value...[%s][%s] key: %s / ini_key: %s / value: %s [%s]' % (definition_type, section, key, ini_key, value, default))
                    if all([self.MINIMAL_INI is True, definition_type(value) != definition_type(default)]) or self.MINIMAL_INI is False:
                        try:
                            config.add_section(section)
                        except configparser.DuplicateSectionError:
                            pass
                    else:
                        try:
                            if config.has_section(section):
                                config.remove_option(section, ini_key)
                            if len(dict(config.items(section))) == 0:
                                config.remove_section(section)
                        except configparser.NoSectionError:
                            continue

                    if any([value is None, value == ""]):
                        value = definition_type(default)
                    if config.has_section(section) and (all([self.MINIMAL_INI is True, definition_type(value) != definition_type(default)]) or self.MINIMAL_INI is False):
                        try:
                            if definition_type == str:
                                value = value.replace('%', '%%')
                        except Exception as e:
                            pass
                        config.set(section, ini_key, str(value))
                else:
                    config.set(section, ini_key, str(self.MINIMAL_INI))

            else:
                pass

        if self.ENCRYPT_PASSWORDS is True:
            self.encrypt_items(mode='encrypt')


    def writeconfig(self, values=None, startup=False):
        logger.fdebug("Writing configuration to file")
        config.set('Newznab', 'extra_newznabs', ', '.join(self.write_extras(self.EXTRA_NEWZNABS)))
        tmp_torz = self.write_extras(self.EXTRA_TORZNABS)
        config.set('Torznab', 'extra_torznabs', ', '.join(tmp_torz))

        # this needs to revert from , to # so that it is stored properly (multiple categories)
        extra_newznabs, extra_torznabs = self.get_extras()
        setattr(self, 'EXTRA_NEWZNABS', extra_newznabs)
        setattr(self, 'EXTRA_TORZNABS', extra_torznabs)

        if startup is False:
            self.provider_sequence()

        ###this should be moved elsewhere...
        if type(self.IGNORED_PUBLISHERS) != list:
            if self.IGNORED_PUBLISHERS is None:
                bp = 'None'
            else:
                if ',,' in self.IGNORED_PUBLISHERS:
                    bp = 'None'
                else:
                    bp = ', '.join(self.IGNORED_PUBLISHERS)
            config.set('CV', 'ignored_publishers', bp)
        else:
            config.set('CV', 'ignored_publishers', ', '.join(self.IGNORED_PUBLISHERS))
        ###
        config.set('General', 'dynamic_update', str(self.DYNAMIC_UPDATE))

        if values is not None:
            self.process_kwargs(values)

        try:
            with codecs.open(self._config_file, encoding='utf8', mode='w+') as configfile:
                config.write(configfile)
            logger.fdebug('Configuration written to disk.')
        except IOError as e:
            logger.warn("Error writing configuration file: %s", e)


    def encrypt_items(self, mode='encrypt', updateconfig=False):
        encryption_list = OrderedDict({
                               #key                      section         key            value
                            'HTTP_PASSWORD':         ('Interface', 'http_password', self.HTTP_PASSWORD),
                            'SAB_PASSWORD':          ('SABnzbd', 'sab_password', self.SAB_PASSWORD),
                            'SAB_APIKEY':            ('SABnzbd', 'sab_apikey', self.SAB_APIKEY),
                            'NZBGET_PASSWORD':       ('NZBGet', 'nzbget_password', self.NZBGET_PASSWORD),
                            'UTORRENT_PASSWORD':     ('uTorrent', 'utorrent_password', self.UTORRENT_PASSWORD),
                            'TRANSMISSION_PASSWORD': ('Transmission', 'transmission_password', self.TRANSMISSION_PASSWORD),
                            'DELUGE_PASSWORD':       ('Deluge', 'deluge_password', self.DELUGE_PASSWORD),
                            'QBITTORRENT_PASSWORD':  ('qBittorrent', 'qbittorrent_password', self.QBITTORRENT_PASSWORD),
                            'RTORRENT_PASSWORD':     ('Rtorrent', 'rtorrent_password', self.RTORRENT_PASSWORD),
                            'PROWL_KEYS':            ('Prowl', 'prowl_keys', self.PROWL_KEYS),
                            'PUSHOVER_APIKEY':       ('PUSHOVER', 'pushover_apikey', self.PUSHOVER_APIKEY),
                            'PUSHOVER_USERKEY':      ('PUSHOVER', 'pushover_userkey', self.PUSHOVER_USERKEY),
                            'BOXCAR_TOKEN':          ('BOXCAR', 'boxcar_token', self.BOXCAR_TOKEN),
                            'PUSHBULLET_APIKEY':     ('PUSHBULLET', 'pushbullet_apikey', self.PUSHBULLET_APIKEY),
                            'TELEGRAM_TOKEN':        ('TELEGRAM', 'telegram_token', self.TELEGRAM_TOKEN),
                            'COMICVINE_API':         ('CV', 'comicvine_api', self.COMICVINE_API),
                            'PASSWORD_32P':          ('32P', 'password_32p', self.PASSWORD_32P),
                            'PASSKEY_32P':           ('32P', 'passkey_32p', self.PASSKEY_32P),
                            'USERNAME_32P':          ('32P', 'username_32p', self.USERNAME_32P),
                            'SEEDBOX_PASS':          ('Seedbox', 'seedbox_pass', self.SEEDBOX_PASS),
                            'TAB_PASS':              ('Tablet', 'tab_pass', self.TAB_PASS),
                            'API_KEY':               ('API', 'api_key', self.API_KEY),
                            'OPDS_PASSWORD':         ('OPDS', 'opds_password', self.OPDS_PASSWORD),
                            'PP_SSHPASSWD':          ('AutoSnatch', 'pp_sshpasswd', self.PP_SSHPASSWD),
                            'EMAIL_PASSWORD':        ('Email','email_password', self.EMAIL_PASSWORD),
                            })

        new_encrypted = 0
        for k,v in encryption_list.items():
            value = []
            for x in v:
                value.append(x)

            if value[2] is not None:
                if value[2][:5] == '^~$z$':
                    if mode == 'decrypt':
                        hp = encrypted.Encryptor(value[2])
                        decrypted_password = hp.decrypt_it()
                        if decrypted_password['status'] is False:
                            logger.warn('Password unable to decrypt - you might have to manually edit the ini for %s to reset the value' % value[1])
                        else:
                            if k != 'HTTP_PASSWORD':
                                setattr(self, k, decrypted_password['password'])
                            if updateconfig is True:
                                config.set(value[0], value[1], decrypted_password['password'])
                    else:
                        if k == 'HTTP_PASSWORD':
                            hp = encrypted.Encryptor(value[2])
                            decrypted_password = hp.decrypt_it()
                            if decrypted_password['status'] is False:
                                logger.warn('Password unable to decrypt - you might have to manually edit the ini for %s to reset the value' % value[1])
                            else:
                                setattr(self, k, decrypted_password['password'])
                else:
                    hp = encrypted.Encryptor(value[2])
                    encrypted_password = hp.encrypt_it()
                    if encrypted_password['status'] is False:
                        logger.warn('Unable to encrypt password for %s - it has not been encrypted. Keeping it as it is.' % value[1])
                    else:
                        if k == 'HTTP_PASSWORD':
                            #make sure we set the http_password for signon to the encrypted value otherwise won't match
                            setattr(self, k, encrypted_password['password'])
                        config.set(value[0], value[1], encrypted_password['password'])
                        new_encrypted+=1

        if new_encrypted > 0:
            self.WRITE_THE_CONFIG = True

    def configure(self, update=False, startup=False):

        if all([self.CLEAR_PROVIDER_TABLE is True, startup is True]):
            mylar.MAINTENANCE = True

        #force alt_pull = 2 on restarts regardless of settings
        if self.ALT_PULL != 2:
            self.ALT_PULL = 2
            config.set('Weekly', 'alt_pull', str(self.ALT_PULL))

        #force off public torrents usage as currently broken.
        self.ENABLE_PUBLIC = False

        if self.GIT_TOKEN:
            self.GIT_TOKEN = (self.GIT_TOKEN, 'x-oauth-basic')
            #logger.info('git_token set to %s' % (self.GIT_TOKEN,))

        try:
            if not any([self.SAB_HOST is None, self.SAB_HOST == '', 'http://' in self.SAB_HOST[:7], 'https://' in self.SAB_HOST[:8]]):
                self.SAB_HOST = 'http://' + self.SAB_HOST
            if self.SAB_HOST.endswith('/'):
                logger.fdebug("Auto-correcting trailing slash in SABnzbd url (not required)")
                self.SAB_HOST = self.SAB_HOST[:-1]
        except:
            pass

        if any([self.HTTP_ROOT is None, self.HTTP_ROOT == '/']):
            self.HTTP_ROOT = '/'
        else:
            if not self.HTTP_ROOT.endswith('/'):
                self.HTTP_ROOT += '/'

        if not update:
           logger.fdebug('Log dir: %s' % self.LOG_DIR)

        if self.LOG_DIR is None:
            self.LOG_DIR = os.path.join(mylar.DATA_DIR, 'logs')

        if not os.path.exists(self.LOG_DIR):
            try:
                os.makedirs(self.LOG_DIR)
            except OSError:
                if not mylar.QUIET:
                    logger.warn('Unable to create the log directory. Logging to screen only.')

        # if not update:
        #     logger.fdebug('[Cache Check] Cache directory currently set to : ' + self.CACHE_DIR)

        # Put the cache dir in the data dir for now
        if not self.CACHE_DIR:
            self.CACHE_DIR = os.path.join(str(mylar.DATA_DIR), 'cache')
            if not update:
                logger.fdebug('[Cache Check] Cache directory not found in configuration. Defaulting location to : ' + self.CACHE_DIR)

        if not os.path.exists(self.CACHE_DIR):
            try:
               os.makedirs(self.CACHE_DIR)
            except OSError:
                logger.error('[Cache Check] Could not create cache dir. Check permissions of datadir: %s' % mylar.DATA_DIR)


        if not self.SECURE_DIR:
            self.SECURE_DIR = os.path.join(mylar.DATA_DIR, '.secure')

        if not os.path.exists(self.SECURE_DIR):
            try:
               os.makedirs(self.SECURE_DIR)
            except OSError:
                logger.error('[Secure DIR Check] Could not create secure directory. Check permissions of datadir: %s' % mylar.DATA_DIR)

        if not self.BACKUP_LOCATION:
            self.BACKUP_LOCATION = os.path.join(mylar.DATA_DIR, 'backup')

        if not os.path.exists(self.BACKUP_LOCATION):
            try:
                os.makedirs(self.BACKUP_LOCATION)
            except OSError:
                logger.error('[Backup Location Check] Could not create backup directory. Check permissions for creation of : %s' % self.BACKUP_LOCATION)


        if all([self.STORYARCDIR is True, self.DESTINATION_DIR is not None]):
            if os.path.exists(self.DESTINATION_DIR):
                if not self.STORYARC_LOCATION:
                    self.STORYARC_LOCATION = os.path.join(self.DESTINATION_DIR, 'StoryArcs')

                if not os.path.exists(self.STORYARC_LOCATION):
                    try:
                        os.makedirs(self.STORYARC_LOCATION)
                    except OSError as e:
                        logger.error('[STORYARC LOCATION] Could not create storyarcs directory @ %s. Error returned: %s' % (self.STORYARC_LOCATION, e))

                logger.info('[STORYARC LOCATION] Storyarc Base directory location set to: %s' % (self.STORYARC_LOCATION))

        #make sure the cookies.dat file is not in cache
        for f in glob.glob(os.path.join(self.CACHE_DIR, '.32p_cookies.dat')):
             try:
                 if os.path.isfile(f):
                     shutil.move(f, os.path.join(self.SECURE_DIR, '.32p_cookies.dat'))
             except Exception as e:
                 logger.error('SECURE-DIR-MOVE] Unable to move cookies file into secure location. This is a fatal error.')
                 sys.exit()

        if self.CLEANUP_CACHE:
            logger.fdebug('[Cache Cleanup] Cache Cleanup initiated. Will delete items from cache that are no longer needed.')
            cache_types = ['*.nzb', '*.torrent', '*.html', 'mylar_*', 'html_cache']
            dir_locations = []
            dir_locations.append(self.CACHE_DIR)
            if self.CLEANUP_STRAYS:
                logger.fdebug('[Cache Cleanup] cbr/cbz cache cleanup option detected. Will remove any detected cbr & cbz files from cache/ddl location.')
                cache_types.extend(('*.zip', '*.cbr', '*.cbz', '[__*__]'))
                if all(
                         [
                           self.DDL_LOCATION is not None,
                           self.DESTINATION_DIR is not None,
                           self.CACHE_DIR != self.DDL_LOCATION,
                           self.DDL_LOCATION != self.DESTINATION_DIR
                         ]
                ):
                    dir_locations.append(self.DDL_LOCATION)
            cntr = 0
            pathlimiter = '**'
            for y in dir_locations:
                for x in cache_types:
                    tmp_path = os.path.join(y, pathlimiter, x)
                    if x == '[__*__]':
                        tmp_path = os.path.join(y, pathlimiter, '*' + glob.escape('[__') + '*' + glob.escape('__]'))
                    for f in glob.glob(tmp_path, recursive=True):
                        ff = Path(f)
                        try:
                            if os.path.isdir(f):
                                if all([ff.stem != 'html_cache', ff.stem != 'mega']):
                                    shutil.rmtree(f)
                            else:
                                os.remove(f)
                        except Exception as e:
                            logger.warn('[ERROR] Unable to remove %s from cache. [%s]' % (f, e))
                        cntr+=1

            if cntr > 1:
                logger.fdebug('[Cache Cleanup] Cache Cleanup finished. Cleaned %s items' % cntr)
            else:
                logger.fdebug('[Cache Cleanup] Cache Cleanup finished. Nothing to clean!')

        d_path = '/proc/self/cgroup'
        if os.path.exists('/.dockerenv') or 'KUBERNETES_SERVICE_HOST' in os.environ or os.path.isfile(d_path) and any('docker' in line for line in open(d_path)):
            logger.info('[DOCKER-AWARE] Docker installation detected.')
            mylar.INSTALL_TYPE = 'docker'
            if any([self.DESTINATION_DIR is None, self.DESTINATION_DIR == '']):
                logger.info('[DOCKER-AWARE] Setting default comic location path to /comics')
                self.DESTINATION_DIR = '/comics'
            if all([self.NZB_DOWNLOADER == 0, self.SAB_DIRECTORY is None, self.SAB_TO_MYLAR is False]):
                logger.info('[DOCKER-AWARE] Setting default sabnzbd download directory location to /downloads')
                self.SAB_TO_MYLAR = True
                self.SAB_DIRECTORY = '/downloads'

        if all([self.GRABBAG_DIR is None, self.DESTINATION_DIR is not None]):
            self.GRABBAG_DIR = os.path.join(self.DESTINATION_DIR, 'Grabbag')
            logger.fdebug('[Grabbag Directory] Setting One-Off directory to default location: %s' % self.GRABBAG_DIR)

        if self.ARC_FOLDERFORMAT is None:
            self.ARC_FOLDERFORMAT = '$arc ($spanyears)'

        ## Sanity checking
        if any([self.COMICVINE_API is None, self.COMICVINE_API == 'None', self.COMICVINE_API == '']):
            logger.error('No User Comicvine API key specified. I will not work very well due to api limits - http://api.comicvine.com/ and get your own free key.')
            self.COMICVINE_API = None
        # Check if Comicvine API key starts with None, thus making it invalid
        elif self.COMICVINE_API[:4] == 'None':
            # Notify user of what's going on
            logger.warn('Comicvine API key starts with a None, working around for now, please fix')
            # Set the actual API key, so mylar does not appear broken from the start
            self.COMICVINE_API = self.COMICVINE_API[4:]

        if self.SEARCH_INTERVAL < 360:
            logger.fdebug('Search interval too low. Resetting to 6 hour minimum')
            self.SEARCH_INTERVAL = 360

        if self.SEARCH_DELAY < 1:
            logger.fdebug("Minimum search delay set for 1 minute to avoid hammering.")
            self.SEARCH_DELAY = 1

        if self.RSS_CHECKINTERVAL < 20:
            logger.fdebug("Minimum RSS Interval Check delay set for 20 minutes to avoid hammering.")
            self.RSS_CHECKINTERVAL = 20

        if self.ENABLE_RSS is True and mylar.RSS_STATUS == 'Paused':
            mylar.RSS_STATUS = 'Waiting'
        elif self.ENABLE_RSS is False and mylar.RSS_STATUS == 'Waiting':
            mylar.RSS_STATUS = 'Paused'

        if self.ENABLE_CHECK_FOLDER is True and mylar.MONITOR_STATUS == 'Paused':
            mylar.MONITOR_STATUS = 'Waiting'
        elif self.ENABLE_CHECK_FOLDER is False and mylar.MONITOR_STATUS == 'Waiting':
            mylar.MONITOR_STATUS = 'Paused'

        if self.DUPECONSTRAINT is None:
            #default dupecontraint to filesize
            setattr(self, 'DUPECONSTRAINT', 'filesize')
            config.set('Duplicates', 'dupeconstraint', 'filesize')

        if self.MINSIZE is not None:
            self.MINSIZE = re.sub(r'[^0-9]', '', self.MINSIZE).strip()

        if self.MAXSIZE is not None:
            self.MAXSIZE = re.sub(r'[^0-9]', '', self.MAXSIZE).strip()

        if not helpers.is_number(self.CHMOD_DIR):
            logger.fdebug("CHMOD Directory value is not a valid numeric - please correct. Defaulting to 0777")
            self.CHMOD_DIR = '0777'

        if not helpers.is_number(self.CHMOD_FILE):
            logger.fdebug("CHMOD File value is not a valid numeric - please correct. Defaulting to 0660")
            self.CHMOD_FILE = '0660'

        if self.FILE_OPTS is None:
            self.FILE_OPTS = 'move'

        if any([self.FILE_OPTS == 'hardlink', self.FILE_OPTS == 'softlink']):
            #we can't have metatagging enabled with hard/soft linking. Forcibly disable it here just in case it's set on load.
            self.ENABLE_META = False

        if all([self.IGNORED_PUBLISHERS is not None, self.IGNORED_PUBLISHERS != '']):
            logger.info('Ignored Publishers: %s' % self.IGNORED_PUBLISHERS)
            if type(self.IGNORED_PUBLISHERS) == str:
                setattr(self, 'ignored_PUBLISHERS', self.IGNORED_PUBLISHERS.split(', '))

        if all([self.AUTHENTICATION == 0, self.HTTP_USERNAME is not None, self.HTTP_PASSWORD is not None]):
            #set it to the default login prompt if nothing selected.
            self.AUTHENTICATION = 1
        elif all([self.HTTP_USERNAME is None, self.HTTP_PASSWORD is None]):
            self.AUTHENTICATION = 0

        if self.ENCRYPT_PASSWORDS is True:
            self.encrypt_items(mode='decrypt')
        if all([self.IGNORE_TOTAL is True, self.IGNORE_HAVETOTAL is True]):
            self.IGNORE_TOTAL = False
            self.IGNORE_HAVETOTAL = False
            logger.warn('You cannot have both ignore_total and ignore_havetotal enabled in the config.ini at the same time. Set only ONE to true - disabling both until this is resolved.')

        if len(self.MASS_PUBLISHERS) > 0 and self.MASS_PUBLISHERS != '[]':
            if type(self.MASS_PUBLISHERS) != list:
                try:
                    self.MASS_PUBLISHERS = json.loads(self.MASS_PUBLISHERS)
                except Exception as e:
                    try:
                        tmp_publishers = json.dumps(self.MASS_PUBLISHERS)
                        self.MASS_PUBLISHERS = json.loads(tmp_publishers)
                    except Exception as e:
                        logger.warn('[MASS_PUBLISHERS] Unable to convert publishers [%s]. Error returned: %s' % (self.MASS_PUBLISHERS, e))
        logger.info('[MASS_PUBLISHERS] Auto-add for weekly publishers set to: %s' % (self.MASS_PUBLISHERS,))

        if len(self.CUSTOM_ISSUE_EXCEPTIONS) > 0 and self.CUSTOM_ISSUE_EXCEPTIONS != '[]':
            if type(self.CUSTOM_ISSUE_EXCEPTIONS) != list:
                try:
                    self.CUSTOM_ISSUE_EXCEPTIONS = json.loads(self.CUSTOM_ISSUE_EXCEPTIONS)
                except Exception as e:
                    logger.warn(f'unable to load custom issue exceptions {self.CUSTOM_ISSUE_EXCEPTIONS}, resetting to empty string')
                    self.CUSTOM_ISSUE_EXCEPTIONS = []

            # Clean up the exceptions in config if any new ones now overlap from hard coded list (either exact match, or pattern matched)
            inbuilt_patterns = [x[0] for x in mylar.INBUILT_ISSUE_EXCEPTIONS if x[1] == 'Pattern']
            inbuilt_exact = [x[0].lower() for x in mylar.INBUILT_ISSUE_EXCEPTIONS if x[1] == 'Exact']

            custom_patterns = [x[0] for x in self.CUSTOM_ISSUE_EXCEPTIONS if x[1] == 'Pattern']
            custom_exact = [x[0] for x in self.CUSTOM_ISSUE_EXCEPTIONS if x[1] == 'Exact']

            self.CUSTOM_ISSUE_EXCEPTIONS = [[x, "Exact"] for x in custom_exact if (not x.lower() in inbuilt_exact) and (not any([re.fullmatch(pattern, x, re.IGNORECASE) for pattern in inbuilt_patterns]))] + \
                                            [[x, "Pattern"] for x in custom_patterns if x not in inbuilt_patterns]
        else:
            setattr(self, 'CUSTOM_ISSUE_EXCEPTIONS', [])
            config.set('General', 'custom_issue_exceptions', json.dumps(self.CUSTOM_ISSUE_EXCEPTIONS))

        logger.fdebug('[CUSTOM_ISSUE_EXCEPTIONS] Custom patterns for issue number exceptions: %s' % (self.CUSTOM_ISSUE_EXCEPTIONS,))

        if len(self.IGNORE_SEARCH_WORDS) > 0 and self.IGNORE_SEARCH_WORDS != '[]':
            if type(self.IGNORE_SEARCH_WORDS) != list:
                try:
                    self.IGNORE_SEARCH_WORDS = json.loads(self.IGNORE_SEARCH_WORDS)
                except Exception as e:
                    logger.warn('unable to load ignored search words')
        else:
            setattr(self, 'IGNORE_SEARCH_WORDS', [".exe", ".iso", "pdf-xpost", "pdf", "ebook"])
            config.set('General', 'ignore_search_words', json.dumps(self.IGNORE_SEARCH_WORDS))

        logger.fdebug('[IGNORE_SEARCH_WORDS] Words to flag search result as invalid: %s' % (self.IGNORE_SEARCH_WORDS,))

        if len(self.PROBLEM_DATES) > 0 and self.PROBLEM_DATES != '[]':
            if type(self.PROBLEM_DATES) != list:
                try:
                    self.PROBLEM_DATES = json.loads(self.PROBLEM_DATES)
                except Exception as e:
                    logger.warn('unable to load problem dates')
        else:
            setattr(self, 'PROBLEM_DATES', ['2021-07-14 04:00:34'])
            config.set('General', 'problem_dates', json.dumps(self.PROBLEM_DATES))

        logger.info('[PROBLEM_DATES] Problem dates loaded: %s' % (self.PROBLEM_DATES,))

        #default opds endpoint check
        if any([self.OPDS_ENDPOINT is None, len(self.OPDS_ENDPOINT) == 0]):
            self.OPDS_ENDPOINT = 'opds'
        else:
            if self.OPDS_ENDPOINT.startswith('/'):
                self.OPDS_ENDPOINT = self.OPDS_ENDPOINT[1:]
            elif self.OPDS_ENDPOINT.endswith('/'):
                self.OPDS_ENDPOINT = self.OPDS_ENDPOINT[:-1]
            config.set('OPDS', 'opds_endpoint', self.OPDS_ENDPOINT.strip())

        #comictagger - force to use included version if option is enabled.
        import comictaggerlib.ctversion as ctversion
        logger.info('[COMICTAGGER] Version detected: %s' % ctversion.version)
        #if any([self.ENABLE_META, self.CBR2CBZ_ONLY]):
        mylar.CMTAGGER_PATH = mylar.PROG_DIR

        if not ([self.CT_NOTES_FORMAT == 'CVDB', self.CT_NOTES_FORMAT == 'Issue ID']):
            setattr(self, 'CT_NOTES_FORMAT', 'Issue ID')
            config.set('Metatagging', 'ct_notes_format', self.CT_NOTES_FORMAT)

        #we need to make sure the default folder setting for the comictagger settings exists so things don't error out
        if self.CT_SETTINGSPATH is None:
            chkpass = False

            #windows won't be able to create in ~, so force it to DATA_DIR
            if mylar.OS_DETECT == 'Windows':
                ct_path = mylar.DATA_DIR
                chkpass = True
            else:
                ct_path = str(Path(os.path.expanduser("~")))
                try:
                    os.mkdir(os.path.join(ct_path, '.ComicTagger'))
                    chkpass = True
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        logger.error('Unable to create .ComicTagger directory in %s. Setting up to default location of %s' % (ct_path, os.path.join(mylar.DATA_DIR, '.ComicTagger')))
                        ct_path = mylar.DATA_DIR
                        chkpass = True
                    elif e.errno == 17: #file_already_exists
                        chkpass = True
                except exception as e:
                    logger.error('Unable to create setting directory for ComicTagger. This WILL cause problems when tagging.')
                    ct_path = mylar.DATA_DIR
                    chkpass = True

            if chkpass is True:
                setattr(self, 'CT_SETTINGSPATH', os.path.join(ct_path, '.ComicTagger'))
                config.set('Metatagging', 'ct_settingspath', self.CT_SETTINGSPATH)

        if not update:
            logger.fdebug('[COMICTAGGER] Setting ComicTagger settings default path to : %s' % self.CT_SETTINGSPATH)

        if not os.path.exists(self.CT_SETTINGSPATH):
            try:
                os.mkdir(self.CT_SETTINGSPATH)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    logger.error('Unable to create setting directory for ComicTagger. This WILL cause problems when tagging.')
            else:
                logger.fdebug('Successfully created ComicTagger Settings location.')

        #make sure the user_agent is running a current version and write it to the .ComicTagger file for use with CT
        if '42.0.2311.135' in self.CV_USER_AGENT:
            self.CV_USER_AGENT = 'comictagger image fetcher'
        if '122.0.0.0' in self.CV_USER_AGENT:
            self.CV_USER_AGENT = 'comictagger image fetcher'

        ct_settingsfile = os.path.join(self.CT_SETTINGSPATH, 'settings')
        if os.path.exists(ct_settingsfile):
            ct_config = configparser.ConfigParser()
            def readline_generator(f):
                line = f.readline()
                while line:
                    yield line
                    line = f.readline()

            ct_config.read_file(
                readline_generator(codecs.open(ct_settingsfile, "r", "utf8")))

            tmp_agent = None
            if ct_config.has_option('comicvine', 'cv_user_agent'):
                tmp_agent = ct_config.get('comicvine', 'cv_user_agent')

            if tmp_agent != self.CV_USER_AGENT:
                #update
                try:
                    with codecs.open(ct_settingsfile, 'r', 'utf8') as ct_read:
                        ct_lines = ct_read.readlines()

                    process_next = False
                    cv_line = 'cv_user_agent = %s' % self.CV_USER_AGENT
                    with codecs.open(ct_settingsfile, encoding='utf8', mode='w+') as ct_file:
                        for line in ct_lines:
                            if 'cv_user_agent' in line:
                                line = cv_line

                            elif '[comicvine]' not in line and process_next:
                                ct_file.write(cv_line+'\n')
                                process_next = False

                            if tmp_agent is None and '[comicvine]' in line:
                                process_next = True

                            ct_file.write(line)

                    logger.fdebug('Updated CT Settings with new CV user agent string.')
                except IOError as e:
                    logger.warn("Error writing configuration file: %s" % e)
            else:
                logger.info('[CV_USER_AGENT] Agent already identical in comictagger session.')

        #make sure queues are running here...
        if startup is False:
            if self.POST_PROCESSING is True and ( all([self.NZB_DOWNLOADER == 0, self.SAB_CLIENT_POST_PROCESSING is True]) or all([self.NZB_DOWNLOADER == 1, self.NZBGET_CLIENT_POST_PROCESSING is True]) ):
                mylar.queue_schedule('nzb_queue', 'start')
            elif self.POST_PROCESSING is True and ( all([self.NZB_DOWNLOADER == 0, self.SAB_CLIENT_POST_PROCESSING is False]) or all([self.NZB_DOWNLOADER == 1, self.NZBGET_CLIENT_POST_PROCESSING is False]) or self.NZB_DOWNLOADER == 3):
                mylar.queue_schedule('nzb_queue', 'stop')

            if self.ENABLE_DDL is True:
                mylar.queue_schedule('ddl_queue', 'start')
            elif self.ENABLE_DDL is False:
                mylar.queue_schedule('ddl_queue', 'stop')

        if self.FOLDER_FORMAT is None:
            setattr(self, 'FOLDER_FORMAT', '$Series ($Year)')

        if '$Annual' in self.FOLDER_FORMAT:
            logger.fdebug('$Annual has been depreciated as a folder format option. Auto-removing from your folder format scheme.')
            ann_removed = re.sub(r'\$annual', '', self.FOLDER_FORMAT, flags=re.I).strip()
            ann_remove = re.sub(r'\s+', ' ', ann_removed).strip()
            setattr(self, 'FOLDER_FORMAT', ann_remove)
            config.set('General', 'folder_format', ann_remove)

        if len(self.DDL_PRIORITY_ORDER) > 0 and self.DDL_PRIORITY_ORDER != '[]':
            if type(self.DDL_PRIORITY_ORDER) != list:
                try:
                    self.DDL_PRIORITY_ORDER = json.loads(self.DDL_PRIORITY_ORDER)
                except Exception as e:
                    logger.warn('[DDL PRIORITY ORDER] Unable to load DDL priority order from setting to default')
                    setattr(self, 'DDL_PRIORITY_ORDER', ["mega", "mediafire", "pixeldrain", "main"])

            # validate entries
            ddl_pros = ['mega', 'mediafire', 'pixeldrain', 'main']
            for dpo in self.DDL_PRIORITY_ORDER:
                if dpo.lower() not in ddl_pros:
                    logger.warn('[DDL PRIORITY ORDER] Invalid value detected - removing %s' % dpo)
                    self.DDL_PRIORITY_ORDER.pop(self.DDL_PRIORITY_ORDER.index(dpo))

        else:
            setattr(self, 'DDL_PRIORITY_ORDER', ["mega", "mediafire", "pixeldrain", "main"])  #default order
            config.set('DDL', 'ddl_priority_order', json.dumps(self.DDL_PRIORITY_ORDER))

        logger.info('[DDL PRIORITY ORDER] DDL will attempt to use the following 3rd party sites in this specific download order: %s' % self.DDL_PRIORITY_ORDER)

        if self.SEARCH_TIER_CUTOFF is None:
            self.SEARCH_TIER_CUTOFF = 14
            config.set('General', 'search_tier_cutoff', str(self.SEARCH_TIER_CUTOFF))
        else:
            if not str(self.SEARCH_TIER_CUTOFF).isdigit():
                self.SEARCH_TIER_CUTOFF = 14
                config.set('General', 'search_tier_cutoff', str(self.SEARCH_TIER_CUTOFF))
        logger.info('[Search Tier Cutoff] Setting Tier-1 cutoff point to %s days' % self.SEARCH_TIER_CUTOFF)

        if all([self.GOTIFY_ENABLED, self.GOTIFY_SERVER_URL is not None]):
            if not self.GOTIFY_SERVER_URL.endswith('/'):
                self.GOTIFY_SERVER_URL += '/'
                config.set('GOTIFY', 'gotify_server_url', self.GOTIFY_SERVER_URL)

        if self.MODE_32P is False and self.RSSFEED_32P is not None:
            mylar.KEYS_32P = self.parse_32pfeed(self.RSSFEED_32P)

        if self.AUTO_SNATCH is True and self.AUTO_SNATCH_SCRIPT is None:
            setattr(self, 'AUTO_SNATCH_SCRIPT', os.path.join(mylar.PROG_DIR, 'post-processing', 'torrent-auto-snatch', 'getlftp.sh'))
            config.set('AutoSnatch', 'auto_snatch_script', self.AUTO_SNATCH_SCRIPT)
        mylar.USE_SABNZBD = False
        mylar.USE_NZBGET = False
        mylar.USE_BLACKHOLE = False

        if all([self.NZB_DOWNLOADER ==0, self.SAB_HOST is None]) or all([self.NZB_DOWNLOADER ==1, self.NZBGET_HOST is None]) or all([self.NZB_DOWNLOADER==2, self.BLACKHOLE_DIR is None]):
            logger.info('NZB Downloader detected as invalid entry - defaulting to None')
            self.NZB_DOWNLOADER = 3

        if self.NZB_DOWNLOADER == 0:
            mylar.USE_SABNZBD = True
        elif self.NZB_DOWNLOADER == 1:
            mylar.USE_NZBGET = True
        elif self.NZB_DOWNLOADER == 2:
            mylar.USE_BLACKHOLE = True

        if self.SAB_PRIORITY.isdigit():
            if self.SAB_PRIORITY == "0": self.SAB_PRIORITY = "Default"
            elif self.SAB_PRIORITY == "1": self.SAB_PRIORITY = "Low"
            elif self.SAB_PRIORITY == "2": self.SAB_PRIORITY = "Normal"
            elif self.SAB_PRIORITY == "3": self.SAB_PRIORITY = "High"
            elif self.SAB_PRIORITY == "4": self.SAB_PRIORITY = "Paused"
            else: self.SAB_PRIORITY = "Default"

        mylar.USE_WATCHDIR = False
        mylar.USE_UTORRENT = False
        mylar.USE_RTORRENT = False
        mylar.USE_TRANSMISSION = False
        mylar.USE_DELUGE = False
        mylar.USE_QBITTORRENT = False
        if self.TORRENT_DOWNLOADER == 0:
            mylar.USE_WATCHDIR = True
        elif self.TORRENT_DOWNLOADER == 1:
            mylar.USE_UTORRENT = True
        elif self.TORRENT_DOWNLOADER == 2:
            mylar.USE_RTORRENT = True
        elif self.TORRENT_DOWNLOADER == 3:
            mylar.USE_TRANSMISSION = True
        elif self.TORRENT_DOWNLOADER == 4:
            mylar.USE_DELUGE = True
        elif self.TORRENT_DOWNLOADER == 5:
            mylar.USE_QBITTORRENT = True
        else:
            self.TORRENT_DOWNLOADER = 0
            mylar.USE_WATCHDIR = True

    def parse_32pfeed(self, rssfeedline):
        KEYS_32P = {}
        if self.ENABLE_32P and len(rssfeedline) > 1:
            userid_st = rssfeedline.find('&user')
            userid_en = rssfeedline.find('&', userid_st +1)
            if userid_en == -1:
                userid_32p = rssfeedline[userid_st +6:]
            else:
                userid_32p = rssfeedline[userid_st +6:userid_en]

            auth_st = rssfeedline.find('&auth')
            auth_en = rssfeedline.find('&', auth_st +1)
            if auth_en == -1:
                auth_32p = rssfeedline[auth_st +6:]
            else:
                auth_32p = rssfeedline[auth_st +6:auth_en]

            authkey_st = rssfeedline.find('&authkey')
            authkey_en = rssfeedline.find('&', authkey_st +1)
            if authkey_en == -1:
                authkey_32p = rssfeedline[authkey_st +9:]
            else:
                authkey_32p = rssfeedline[authkey_st +9:authkey_en]

            KEYS_32P = {"user":    userid_32p,
                        "auth":    auth_32p,
                        "authkey": authkey_32p,
                        "passkey": self.PASSKEY_32P}

        return KEYS_32P

    def get_extras(self):
        cnt=0
        while (cnt < 2):
            if cnt == 0:
                ex = self.EXTRA_NEWZNABS
            else:
                ex = self.EXTRA_TORZNABS

            if type(ex) != list:
                if self.CONFIG_VERSION < 11:
                    if cnt == 0:
                        extra_newznabs = list(zip(*[iter(ex.split(', '))]*6))
                    else:
                        extra_torznabs = list(zip(*[iter(ex.split(', '))]*6))
                else:
                    if cnt == 0:
                        extra_newznabs = list(zip(*[iter(ex.split(', '))]*7))
                    else:
                        extra_torznabs = list(zip(*[iter(ex.split(', '))]*7))
            else:
               if cnt == 0:
                   extra_newznabs = ex
               else:
                   extra_torznabs = ex
            cnt+=1

        x_newzcat = []
        x_torzcat = []
        cnt = 0
        while (cnt < 2):
            if cnt == 0:
                ex = extra_newznabs
            else:
                ex = extra_torznabs

            for x in ex:
                x_cat = x[4]
                if x_cat:
                    if '#' in x_cat:
                        x_t = x[4].split('#')
                        x_cat = ','.join(x_t)
                        if x_cat[0] == ',':
                            x_cat = re.sub(',', '#', x_cat, 1)
                try:
                    if cnt == 0:
                        x_newzcat.append((x[0],x[1],x[2],x[3],x_cat,x[5],int(x[6])))
                    else:
                        x_torzcat.append((x[0],x[1],x[2],x[3],x_cat,x[5],int(x[6])))
                    if int(x[6]) > mylar.PROVIDER_START_ID:
                        mylar.PROVIDER_START_ID = int(x[6])
                except Exception as e:
                    if cnt == 0:
                        x_newzcat.append((x[0],x[1],x[2],x[3],x_cat,x[5]))
                    else:
                        x_torzcat.append((x[0],x[1],x[2],x[3],x_cat,x[5]))
            cnt +=1

        # had to loop thru entire set above in order to get the highest id to start at
        xx_newzcat = []
        xx_torzcat = []
        cnt = 0
        while (cnt < 2):
            if cnt == 0:
                ex = x_newzcat
            else:
                ex = x_torzcat

            for xn in ex:
                try:
                    if cnt == 0:
                        xx_newzcat.append((xn[0],xn[1],xn[2],xn[3],xn[4],xn[5],xn[6]))
                    else:
                        xx_torzcat.append((xn[0],xn[1],xn[2],xn[3],xn[4],xn[5],xn[6]))
                except Exception as e:
                    mylar.PROVIDER_START_ID += 1
                    if cnt == 0:
                        xx_newzcat.append((xn[0],xn[1],xn[2],xn[3],xn[4],xn[5],mylar.PROVIDER_START_ID))
                    else:
                        xx_torzcat.append((xn[0],xn[1],xn[2],xn[3],xn[4],xn[5],mylar.PROVIDER_START_ID))
            cnt +=1
        #logger.fdebug('xx_newzcat: %s' % (xx_newzcat,))
        #logger.fdebug('xx_torzcat: %s' % (xx_torzcat,))
        return xx_newzcat, xx_torzcat

    def get_extra_torznabs(self):
        extra_torznabs = self.EXTRA_TORZNABS
        if type(extra_torznabs) != list:
            if self.CONFIG_VERSION < 11:
                extra_torznabs = list(zip(*[iter(extra_torznabs.split(', '))]*6))
            else:
                extra_torznabs = list(zip(*[iter(extra_torznabs.split(', '))]*7))
        x_torcat = []
        for x in extra_torznabs:
            x_cat = x[4]
            if '#' in x_cat:
                x_t = x[4].split('#')
                x_cat = ','.join(x_t)
            try:
                x_torcat.append((x[0],x[1],x[2],x[3],x_cat,x[5],int(x[6])))
                if int(x[6]) > mylar.PROVIDER_START_ID:
                    mylar.PROVIDER_START_ID = int(x[6])
            except Exception as e:
                x_torcat.append((x[0],x[1],x[2],x[3],x_cat,x[5]))

        # had to loop thru entire set above in order to get the highest id to start at
        xx_torcat = []
        for xn in x_torcat:
            try:
                xx_torcat.append((xn[0],xn[1],xn[2],xn[3],xn[4],xn[5],xn[6]))
            except Exception as e:
                mylar.PROVIDER_START_ID += 1
                xx_torcat.append((xn[0],xn[1],xn[2],xn[3],xn[4],xn[5],mylar.PROVIDER_START_ID))

        extra_torznabs = xx_torcat
        return extra_torznabs

    def get_ignored_pubs(self):
        if all([self.IGNORED_PUBLISHERS is not None, self.IGNORED_PUBLISHERS != '', len(self.IGNORED_PUBLISHERS) != 0]):
            if not ',,' in self.IGNORED_PUBLISHERS:
                ignored_pubs = [x.strip() for x in self.IGNORED_PUBLISHERS.split(',')]
            else:
                ignored_pubs = []
        else:
            ignored_pubs = []
        return ignored_pubs

    def provider_sequence(self):
        PR = []
        PR_NUM = 0
        if self.ENABLE_TORRENT_SEARCH:
            if self.ENABLE_32P:
                PR.append('32p')
                PR_NUM +=1
            #if self.ENABLE_PUBLIC:
            #    PR.append('public torrents')
            #    PR_NUM +=1
        if self.EXPERIMENTAL:
            PR.append('Experimental')
            PR_NUM +=1

        if self.ENABLE_DDL:
            if self.ENABLE_GETCOMICS:
                PR.append('DDL(GetComics)')
                PR_NUM +=1
            if self.ENABLE_EXTERNAL_SERVER:
                PR.append('DDL(External)')
                PR_NUM +=1
        if self.ENABLE_AIRDCPP:
            PR.append('AirDCPP')
            PR_NUM += 1

        PPR = ['Experimental', 'DDL(GetComics)', 'DDL(External)', 'AirDCPP']
        if self.NEWZNAB:
            for ens in self.EXTRA_NEWZNABS:
                if str(ens[5]) == '1': # if newznabs are enabled
                    if ens[0] == "":
                        en_name = ens[1]
                    else:
                        en_name = ens[0]
                    if en_name.endswith("\""):
                        en_name = re.sub("\"", "", str(en_name)).strip()
                    PR.append(en_name)
                    PPR.append(en_name)
                    PR_NUM +=1

        if self.ENABLE_TORZNAB and self.ENABLE_TORRENT_SEARCH:
            for ets in self.EXTRA_TORZNABS:
                if str(ets[5]) == '1': # if torznabs are enabled
                    if ets[0] == "":
                        et_name = ets[1]
                    else:
                        et_name = ets[0]
                    if et_name.endswith("\""):
                        et_name = re.sub("\"", "", str(et_name)).strip()
                    PR.append(et_name)
                    PPR.append(et_name)
                    PR_NUM +=1

        if self.PROVIDER_ORDER is not None:
            try:
                PRO_ORDER = list(zip(*[iter(self.PROVIDER_ORDER.split(', '))]*2))
            except:
                PO = []
                for k, v in self.PROVIDER_ORDER.items():
                    PO.append(k)
                    PO.append(v)
                POR = ', '.join(PO)
                PRO_ORDER = list(zip(*[iter(POR.split(', '))]*2))

            logger.fdebug("Original provider_order sequence: %s" % self.PROVIDER_ORDER)

            #if provider order exists already, load it and then append to end any NEW entries.
            logger.fdebug('Provider sequence already pre-exists. Re-loading and adding/remove any new entries')
            TMPPR_NUM = 0
            PROV_ORDER = []
            #load original sequence
            for PRO in PRO_ORDER:
                PROV_ORDER.append({"order_seq":  PRO[0],
                                   "provider":   str(PRO[1])})
                TMPPR_NUM +=1

            #calculate original sequence to current sequence for discrepancies
            #print('TMPPR_NUM: %s --- PR_NUM: %s' % (TMPPR_NUM, PR_NUM))
            if PR_NUM != TMPPR_NUM:
                logger.fdebug('existing Order count does not match New Order count')
                if PR_NUM > TMPPR_NUM:
                    logger.fdebug('%s New entries exist, appending to end as default ordering' % (PR_NUM - TMPPR_NUM))
                    TOTALPR = (TMPPR_NUM + PR_NUM)
                else:
                    logger.fdebug('%s Disabled entries exist, removing from ordering sequence' % (TMPPR_NUM - PR_NUM))
                    TOTALPR = TMPPR_NUM
                if PR_NUM > 0:
                    logger.fdebug('%s entries are enabled.' % PR_NUM)

            NEW_PROV_ORDER = []
            i = len(PR)-1
            #this should loop over ALL possible entries
            while i >= 0:
                found = False
                for d in PPR:
                    #logger.fdebug('checking entry %s against %s' % (PR[i], d) #d['provider'])
                    if d == PR[i]:
                        x = [p['order_seq'] for p in PROV_ORDER if p['provider'].lower() == PR[i].lower()]
                        if x:
                            ord = x[0]
                        else:
                            #if x isn't found, the provider was not in the OG list. So we add it to the end.
                            ord = len(PR)
                        found = {'provider': PR[i],
                                 'order':    ord}
                        break
                    else:
                        found = False

                if found is not False:
                    new_order_seqnum = len(NEW_PROV_ORDER)
                    if new_order_seqnum != int(found['order']):
                        seqnum = int(found['order'])
                    else:
                        seqnum = new_order_seqnum
                    NEW_PROV_ORDER.append({"order_seq":  int(seqnum),
                                           "provider":   found['provider'],
                                           "orig_seq":   int(seqnum)})
                i-=1

            #now we reorder based on priority of orig_seq, but use a new_order seq
            xa = 0
            NPROV = []
            for x in sorted(NEW_PROV_ORDER, key=itemgetter('orig_seq'), reverse=False):
                NPROV.append(str(xa))
                NPROV.append(x['provider'])
                xa+=1
            PROVIDER_ORDER = NPROV

        else:
            #priority provider sequence in order#, ProviderName
            logger.fdebug('creating provider sequence order now...')
            TMPPR_NUM = 0
            PROV_ORDER = []
            while TMPPR_NUM < PR_NUM:
                PROV_ORDER.append(str(TMPPR_NUM))
                PROV_ORDER.append(PR[TMPPR_NUM])
                                   #{"order_seq":  TMPPR_NUM,
                                   #"provider":   str(PR[TMPPR_NUM])})
                TMPPR_NUM +=1
            PROVIDER_ORDER = PROV_ORDER

        ll = ', '.join(PROVIDER_ORDER)
        if not config.has_section('Providers'):
            config.add_section('Providers')
        config.set('Providers', 'PROVIDER_ORDER', ll)

        PROVIDER_ORDER = dict(list(zip(*[PROVIDER_ORDER[i::2] for i in range(2)])))
        setattr(self, 'PROVIDER_ORDER', PROVIDER_ORDER)
        logger.fdebug('Provider Order is now set : %s ' % self.PROVIDER_ORDER)

        self.write_out_provider_searches()

    def write_extras(self, value):
        flattened = []
        for item in value:
            for i in item:
                try:
                    if value.index(i) == 4:
                        ib = i
                        if ',' in ib:
                            ib = re.sub(',', '#', ib).strip()
                    elif "\"" in i and " \"" in i:
                        ib = str(i).replace("\"", "").strip()
                    else:
                        ib = i
                except:
                    ib = i
                flattened.append(str(ib))
        return flattened

    def write_out_provider_searches(self):
       # this is needed for rss to work since the provider table isn't written to
       # until a search is performed
       myDB = db.DBConnection()
       chk = myDB.select("SELECT * FROM provider_searches")
       p_list = {}
       write = False
       if chk:
           for ck in chk:
               ck_hits = ck['hits']
               if ck_hits is None:
                   ck_hits = 0
               t_id = ck['id']
               prov_t = ck['provider']
               if t_id == 'Experimental':
                   prov_t = 'experimental'
               #logger.fdebug('[%s] t_id: %s' % (ck['provider'], t_id))
               if any([t_id == 0, t_id is None]):
                   # id of 0 means it hasn't been assigned - so we need to assign it before we build out the dict
                   if 'DDL(GetComics)' in prov_t:
                       t_id = 200
                   if 'DDL(External)' in prov_t:
                       t_id = 201
                   elif any(['experimental' in prov_t, 'Experimental' in prov_t]):
                       t_id = 101
                   else:
                       nnf = False
                       if self.EXTRA_NEWZNABS:
                           for n in self.EXTRA_NEWZNABS:
                               if n[0] == prov_t:
                                   t_id = n[6]
                                   nnf = True
                                   break
                       if nnf is False and self.EXTRA_TORZNABS:
                           for n in self.EXTRA_TORZNABS:
                               if n[0] == prov_t:
                                   t_id = n[6]
                                   nnf = True
                                   break

                   t_ctrl = {'id': t_id, 'provider': prov_t}
                   t_vals = {'active': ck['active'], 'lastrun': ck['lastrun'], 'type': ck['type'], 'hits': ck_hits}
                   writeout = myDB.upsert("provider_searches", t_vals, t_ctrl)
               p_list[prov_t] = {'id': t_id, 'active': ck['active'], 'lastrun': ck['lastrun'], 'type': ck['type'], 'hits': ck_hits}

       #logger.fdebug('p_list: %s' % (p_list,))
       for k, v in self.PROVIDER_ORDER.items():
           tmp_prov = v
           if not any(p.lower() == tmp_prov.lower() for p, pv in p_list.items()):
               write = True
               #logger.fdebug('%s was not found in search db. Writing it..' % v)
               if 'DDL(GetComics)' in tmp_prov:
                   t_type = 'DDL'
                   t_id = 200
               if 'DDL(External)' in tmp_prov:
                   t_type = 'DDL(External)'
                   t_id = 201
               if 'AirDCPP' in tmp_prov:
                   t_type = 'AirDCPP'
                   t_id = 202
               elif any(['experimental' in tmp_prov, 'Experimental' in tmp_prov]):
                   tmp_prov = 'experimental'
                   t_type = 'experimental'
                   t_id = 101
               else:
                   nnf = False
                   if self.EXTRA_NEWZNABS:
                       for n in self.EXTRA_NEWZNABS:
                           if n[0] == tmp_prov:
                               t_type = 'newznab'
                               t_id = n[6]
                               nnf = True
                               break
                   if nnf is False and self.EXTRA_TORZNABS:
                       for n in self.EXTRA_TORZNABS:
                           if n[0] == tmp_prov:
                               t_type = 'torznab'
                               t_id = n[6]
                               nnf = True
                               break
               ctrls = {'id': t_id}
               vals = {'provider': tmp_prov, 'active': False, 'lastrun': 0, 'type': t_type, 'hits': 0}
           else:
               try:
                   tprov = [p_list[x] for x, y in p_list.items() if x.lower() == tmp_prov.lower()][0]
               except Exception:
                   tprov = None

               if tprov:
                   if tmp_prov == 'Experimental':
                       # needed to ensure the type is set properly for this provider
                       ptype = tprov['type']
                       if tmp_prov == 'Experimental':
                           myDB.action("DELETE FROM provider_searches where id=101")
                           tmp_prov = 'experimental'
                       ctrls = {'id': tprov['id']}
                       vals = {'provider': tmp_prov, 'active': tprov['active'], 'lastrun': tprov['lastrun'], 'type': ptype, 'hits': tprov['hits']}
                       write = True

           if write is True:
               logger.fdebug('writing: keys - %s: vals - %s' % (vals, ctrls))
               writeout = myDB.upsert("provider_searches", vals, ctrls)

def ddl_creations():
    if not mylar.CONFIG.DDL_LOCATION:
        mylar.CONFIG.DDL_LOCATION = mylar.CONFIG.CACHE_DIR
        if mylar.CONFIG.ENABLE_DDL is True:
            logger.info('Setting DDL Location set to : %s' % mylar.CONFIG.DDL_LOCATION)
    else:
        dcreate = filechecker.validateAndCreateDirectory(mylar.CONFIG.DDL_LOCATION, create=True, dmode='ddl location')
        if all([dcreate is False, mylar.CONFIG.ENABLE_DDL is True]):
            logger.warn('Unable to create ddl_location specified in config: %s. Reverting to default cache location.' % mylar.CONFIG.DDL_LOCATION)
            mylar.CONFIG.DDL_LOCATION = mylar.CONFIG.CACHE_DIR

    if mylar.CONFIG.ENABLE_DDL:
        #make sure directory for mega downloads is created...
        mega_ddl_path = os.path.join(mylar.CONFIG.DDL_LOCATION, 'mega')
        html_cache_path = os.path.join(mylar.CONFIG.CACHE_DIR, 'html_cache')
        mdp_create = filechecker.validateAndCreateDirectory(mega_ddl_path, create=True, dmode='ddl-mega location')
        if mdp_create is False:
            logger.error('Unable to create temp download directory [%s] for DDL-External. You will not be able to view the progress of the download.' % mega_ddl_path)

        hcp_create = filechecker.validateAndCreateDirectory(html_cache_path, create=True, dmode='html cache')
        if hcp_create is False:
            logger.error('Unable to create html_cache folder within the cache folder location [%s]. DDL will not work until this is corrected.' % html_cache_path)
