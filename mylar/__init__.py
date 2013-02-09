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
import webbrowser
import sqlite3
import itertools
import csv
import shutil

from lib.apscheduler.scheduler import Scheduler
from lib.configobj import ConfigObj

import cherrypy

from mylar import versioncheck, logger, version
from mylar.common import *

FULL_PATH = None
PROG_DIR = None

ARGS = None
SIGNAL = None

SYS_ENCODING = None

VERBOSE = 1
DAEMON = False
PIDFILE= None

SCHED = Scheduler()

INIT_LOCK = threading.Lock()
__INITIALIZED__ = False
started = False

DATA_DIR = None

CONFIG_FILE = None
CFG = None
CONFIG_VERSION = None

DB_FILE = None

LOG_DIR = None
LOG_LIST = []

CACHE_DIR = None

HTTP_PORT = None
HTTP_HOST = None
HTTP_USERNAME = None
HTTP_PASSWORD = None
HTTP_ROOT = None
LAUNCH_BROWSER = False
LOGVERBOSE = 1
GIT_PATH = None
INSTALL_TYPE = None
CURRENT_VERSION = None
LATEST_VERSION = None
COMMITS_BEHIND = None

CHECK_GITHUB = False
CHECK_GITHUB_ON_STARTUP = False
CHECK_GITHUB_INTERVAL = None

DESTINATION_DIR = None
USENET_RETENTION = None

ADD_COMICS = False
COMIC_DIR = None
LIBRARYSCAN = False
IMP_MOVE = False
IMP_RENAME = False
IMP_METADATA = False

SEARCH_INTERVAL = 360
NZB_STARTUP_SEARCH = False
LIBRARYSCAN_INTERVAL = 300
DOWNLOAD_SCAN_INTERVAL = 5
INTERFACE = None

PREFERRED_QUALITY = None
PREFERRED_CBR = None
PREFERRED_CBZ = None
PREFERRED_WE = None
CORRECT_METADATA = False
MOVE_FILES = False
RENAME_FILES = False
BLACKHOLE = False
BLACKHOLE_DIR = None
FOLDER_FORMAT = None
FILE_FORMAT = None
REPLACE_SPACES = False
REPLACE_CHAR = None
ZERO_LEVEL = False
ZERO_LEVEL_N = None
LOWERCASE_FILENAME = False
USE_MINSIZE = False
MINSIZE = 10
USE_MAXSIZE = False
MAXSIZE = 60
AUTOWANT_UPCOMING = True
AUTOWANT_ALL = False
COMIC_COVER_LOCAL = False
ADD_TO_CSV = True
SKIPPED2WANTED = False
CVINFO = False
LOG_LEVEL = None

SAB_HOST = None
SAB_USERNAME = None
SAB_PASSWORD = None
SAB_APIKEY = None
SAB_CATEGORY = None
SAB_PRIORITY = None
SAB_DIRECTORY = None

NZBSU = False
NZBSU_APIKEY = None

DOGNZB = False
DOGNZB_APIKEY = None

NZBX = False

NEWZNAB = False
NEWZNAB_HOST = None
NEWZNAB_APIKEY = None
NEWZNAB_ENABLED = False
EXTRA_NEWZNABS = []

RAW = False
RAW_PROVIDER = None
RAW_USERNAME = None
RAW_PASSWORD = None
RAW_GROUPS = None

EXPERIMENTAL = False

COMIC_LOCATION = None
QUAL_ALTVERS = None
QUAL_SCANNER = None
QUAL_TYPE = None
QUAL_QUALITY = None

ENABLE_EXTRA_SCRIPTS = 1
EXTRA_SCRIPTS = None

ENABLE_PRE_SCRIPTS = 1
PRE_SCRIPTS = None

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
    
        global __INITIALIZED__, FULL_PATH, PROG_DIR, VERBOSE, DAEMON, DATA_DIR, CONFIG_FILE, CFG, CONFIG_VERSION, LOG_DIR, CACHE_DIR, LOGVERBOSE, \
                HTTP_PORT, HTTP_HOST, HTTP_USERNAME, HTTP_PASSWORD, HTTP_ROOT, LAUNCH_BROWSER, GIT_PATH, \
                CURRENT_VERSION, LATEST_VERSION, CHECK_GITHUB, CHECK_GITHUB_ON_STARTUP, CHECK_GITHUB_INTERVAL, MUSIC_DIR, DESTINATION_DIR, \
                DOWNLOAD_DIR, USENET_RETENTION, SEARCH_INTERVAL, NZB_STARTUP_SEARCH, INTERFACE, AUTOWANT_ALL, AUTOWANT_UPCOMING, ZERO_LEVEL, ZERO_LEVEL_N, COMIC_COVER_LOCAL, \
                LIBRARYSCAN, LIBRARYSCAN_INTERVAL, DOWNLOAD_SCAN_INTERVAL, SAB_HOST, SAB_USERNAME, SAB_PASSWORD, SAB_APIKEY, SAB_CATEGORY, SAB_PRIORITY, SAB_DIRECTORY, BLACKHOLE, BLACKHOLE_DIR, ADD_COMICS, COMIC_DIR, IMP_MOVE, IMP_RENAME, IMP_METADATA, \
                NZBSU, NZBSU_APIKEY, DOGNZB, DOGNZB_APIKEY, NZBX,\
                NEWZNAB, NEWZNAB_HOST, NEWZNAB_APIKEY, NEWZNAB_ENABLED, EXTRA_NEWZNABS,\
                RAW, RAW_PROVIDER, RAW_USERNAME, RAW_PASSWORD, RAW_GROUPS, EXPERIMENTAL, \
                PREFERRED_QUALITY, MOVE_FILES, RENAME_FILES, LOWERCASE_FILENAMES, USE_MINSIZE, MINSIZE, USE_MAXSIZE, MAXSIZE, CORRECT_METADATA, FOLDER_FORMAT, FILE_FORMAT, REPLACE_CHAR, REPLACE_SPACES, ADD_TO_CSV, CVINFO, LOG_LEVEL, \
                COMIC_LOCATION, QUAL_ALTVERS, QUAL_SCANNER, QUAL_TYPE, QUAL_QUALITY, ENABLE_EXTRA_SCRIPTS, EXTRA_SCRIPTS, ENABLE_PRE_SCRIPTS, PRE_SCRIPTS
                
        if __INITIALIZED__:
            return False

        # Make sure all the config sections exist
        CheckSection('General')
        CheckSection('SABnzbd')
        CheckSection('NZBsu')
        CheckSection('DOGnzb')
        CheckSection('Raw')
        CheckSection('Experimental')        
        CheckSection('Newznab')
        # Set global variables based on config file or use defaults
        try:
            HTTP_PORT = check_setting_int(CFG, 'General', 'http_port', 8090)
        except:
            HTTP_PORT = 8090
            
        if HTTP_PORT < 21 or HTTP_PORT > 65535:
            HTTP_PORT = 8090
            
#        CONFIG_VERSION = check_setting_str(CFG, 'General', 'config_version', '')
        HTTP_HOST = check_setting_str(CFG, 'General', 'http_host', '0.0.0.0')
        HTTP_USERNAME = check_setting_str(CFG, 'General', 'http_username', '')
        HTTP_PASSWORD = check_setting_str(CFG, 'General', 'http_password', '')
        HTTP_ROOT = check_setting_str(CFG, 'General', 'http_root', '/')
        LAUNCH_BROWSER = bool(check_setting_int(CFG, 'General', 'launch_browser', 1))
        LOGVERBOSE = bool(check_setting_int(CFG, 'General', 'logverbose', 1))
        GIT_PATH = check_setting_str(CFG, 'General', 'git_path', '')
        LOG_DIR = check_setting_str(CFG, 'General', 'log_dir', '')
        if not CACHE_DIR:
            CACHE_DIR = check_setting_str(CFG, 'General', 'cache_dir', '')
        
        CHECK_GITHUB = bool(check_setting_int(CFG, 'General', 'check_github', 1))
        CHECK_GITHUB_ON_STARTUP = bool(check_setting_int(CFG, 'General', 'check_github_on_startup', 1))
        CHECK_GITHUB_INTERVAL = check_setting_int(CFG, 'General', 'check_github_interval', 360)
        
        DESTINATION_DIR = check_setting_str(CFG, 'General', 'destination_dir', '')
        USENET_RETENTION = check_setting_int(CFG, 'General', 'usenet_retention', '1500')
        
        SEARCH_INTERVAL = check_setting_int(CFG, 'General', 'search_interval', 360)
        NZB_STARTUP_SEARCH = bool(check_setting_int(CFG, 'General', 'nzb_startup_search', 0))
        LIBRARYSCAN = bool(check_setting_int(CFG, 'General', 'libraryscan', 1))
        LIBRARYSCAN_INTERVAL = check_setting_int(CFG, 'General', 'libraryscan_interval', 300)
        ADD_COMICS = bool(check_setting_int(CFG, 'General', 'add_comics', 0))
        COMIC_DIR = check_setting_str(CFG, 'General', 'comic_dir', '')
        IMP_MOVE = bool(check_setting_int(CFG, 'General', 'imp_move', 0))
        IMP_RENAME = bool(check_setting_int(CFG, 'General', 'imp_rename', 0))
        IMP_METADATA = bool(check_setting_int(CFG, 'General', 'imp_metadata', 0))
        DOWNLOAD_SCAN_INTERVAL = check_setting_int(CFG, 'General', 'download_scan_interval', 5)
        INTERFACE = check_setting_str(CFG, 'General', 'interface', 'default')
        AUTOWANT_ALL = bool(check_setting_int(CFG, 'General', 'autowant_all', 0))
        AUTOWANT_UPCOMING = bool(check_setting_int(CFG, 'General', 'autowant_upcoming', 1))
        COMIC_COVER_LOCAL = bool(check_setting_int(CFG, 'General', 'comic_cover_local', 0))
        PREFERRED_QUALITY = bool(check_setting_int(CFG, 'General', 'preferred_quality', 0))
        CORRECT_METADATA = bool(check_setting_int(CFG, 'General', 'correct_metadata', 0))
        MOVE_FILES = bool(check_setting_int(CFG, 'General', 'move_files', 0))
        RENAME_FILES = bool(check_setting_int(CFG, 'General', 'rename_files', 0))
        FOLDER_FORMAT = check_setting_str(CFG, 'General', 'folder_format', '$Series-($Year)')
        FILE_FORMAT = check_setting_str(CFG, 'General', 'file_format', '$Series $Issue ($Year)')
        BLACKHOLE = bool(check_setting_int(CFG, 'General', 'blackhole', 0))
        BLACKHOLE_DIR = check_setting_str(CFG, 'General', 'blackhole_dir', '')
        REPLACE_SPACES = bool(check_setting_int(CFG, 'General', 'replace_spaces', 0))
        REPLACE_CHAR = check_setting_str(CFG, 'General', 'replace_char', '')
        ZERO_LEVEL = bool(check_setting_int(CFG, 'General', 'zero_level', 0))
        ZERO_LEVEL_N = check_setting_str(CFG, 'General', 'zero_level_n', '')
        LOWERCASE_FILENAMES = bool(check_setting_int(CFG, 'General', 'lowercase_filenames', 0))
        USE_MINSIZE = bool(check_setting_int(CFG, 'General', 'use_minsize', 0))
        MINSIZE = check_setting_str(CFG, 'General', 'minsize', '')
        USE_MAXSIZE = bool(check_setting_int(CFG, 'General', 'use_maxsize', 0))
        MAXSIZE = check_setting_str(CFG, 'General', 'maxsize', '')
        ADD_TO_CSV = bool(check_setting_int(CFG, 'General', 'add_to_csv', 1))
        CVINFO = bool(check_setting_int(CFG, 'General', 'cvinfo', 0))
        LOG_LEVEL = check_setting_str(CFG, 'General', 'log_level', '')
        ENABLE_EXTRA_SCRIPTS = bool(check_setting_int(CFG, 'General', 'enable_extra_scripts', 0))
        EXTRA_SCRIPTS = check_setting_str(CFG, 'General', 'extra_scripts', '')

        ENABLE_PRE_SCRIPTS = bool(check_setting_int(CFG, 'General', 'enable_pre_scripts', 0))
        PRE_SCRIPTS = check_setting_str(CFG, 'General', 'pre_scripts', '')

        SAB_HOST = check_setting_str(CFG, 'SABnzbd', 'sab_host', '')
        SAB_USERNAME = check_setting_str(CFG, 'SABnzbd', 'sab_username', '')
        SAB_PASSWORD = check_setting_str(CFG, 'SABnzbd', 'sab_password', '')
        SAB_APIKEY = check_setting_str(CFG, 'SABnzbd', 'sab_apikey', '')
        SAB_CATEGORY = check_setting_str(CFG, 'SABnzbd', 'sab_category', '')
        SAB_DIRECTORY = check_setting_str(CFG, 'SABnzbd', 'sab_directory', '')
        SAB_PRIORITY = check_setting_str(CFG, 'SABnzbd', 'sab_priority', '')
        if SAB_PRIORITY.isdigit():
            if SAB_PRIORITY == "0": SAB_PRIORITY = "Default"
            elif SAB_PRIORITY == "1": SAB_PRIORITY = "Low"
            elif SAB_PRIORITY == "2": SAB_PRIORITY = "Normal"
            elif SAB_PRIORITY == "3": SAB_PRIORITY = "High"
            elif SAB_PRIORITY == "4": SAB_PRIORITY = "Paused"
            else: SAB_PRIORITY = "Default"
        NZBSU = bool(check_setting_int(CFG, 'NZBsu', 'nzbsu', 0))
        NZBSU_APIKEY = check_setting_str(CFG, 'NZBsu', 'nzbsu_apikey', '')

        DOGNZB = bool(check_setting_int(CFG, 'DOGnzb', 'dognzb', 0))
        DOGNZB_APIKEY = check_setting_str(CFG, 'DOGnzb', 'dognzb_apikey', '')

        NZBX = bool(check_setting_int(CFG, 'nzbx', 'nzbx', 0))

        RAW = bool(check_setting_int(CFG, 'Raw', 'raw', 0))
        RAW_PROVIDER = check_setting_str(CFG, 'Raw', 'raw_provider', '')
        RAW_USERNAME = check_setting_str(CFG, 'Raw', 'raw_username', '')
        RAW_PASSWORD  = check_setting_str(CFG, 'Raw', 'raw_password', '')
        RAW_GROUPS = check_setting_str(CFG, 'Raw', 'raw_groups', '')

        EXPERIMENTAL = bool(check_setting_int(CFG, 'Experimental', 'experimental', 0))

        NEWZNAB = bool(check_setting_int(CFG, 'Newznab', 'newznab', 0))
        NEWZNAB_HOST = check_setting_str(CFG, 'Newznab', 'newznab_host', '')
        NEWZNAB_APIKEY = check_setting_str(CFG, 'Newznab', 'newznab_apikey', '')
        NEWZNAB_ENABLED = bool(check_setting_int(CFG, 'Newznab', 'newznab_enabled', 1))

        # Need to pack the extra newznabs back into a list of tuples
        flattened_newznabs = check_setting_str(CFG, 'Newznab', 'extra_newznabs', [], log=False)
        EXTRA_NEWZNABS = list(itertools.izip(*[itertools.islice(flattened_newznabs, i, None, 3) for i in range(3)]))

        
        # update folder formats in the config & bump up config version
        if CONFIG_VERSION == '0':
            from mylar.helpers import replace_all
            file_values = { 'issue':  'Issue', 'title': 'Title', 'series' : 'Series', 'year' : 'Year' }
            folder_values = { 'series' : 'Series', 'publisher':'Publisher', 'year' : 'Year', 'first' : 'First', 'lowerfirst' : 'first' }
            FILE_FORMAT = replace_all(FILE_FORMAT, file_values)
            FOLDER_FORMAT = replace_all(FOLDER_FORMAT, folder_values)
            
            CONFIG_VERSION = '1'
            
        if CONFIG_VERSION == '1':

            from mylar.helpers import replace_all

            file_values = { 'Issue':        '$Issue',
                            'Title':        '$Title',
                            'Series':       '$Series',
                            'Year':         '$Year',
                            'title':        '$title',
                            'series':       '$series',
                            'year':         '$year'
                            }
            folder_values = {   'Series':       '$Series',
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
            #print ("SAB_HOST:" + SAB_HOST)

        if not LOG_DIR:
            LOG_DIR = os.path.join(DATA_DIR, 'logs')

        if not os.path.exists(LOG_DIR):
            try:
                os.makedirs(LOG_DIR)
            except OSError:
                if VERBOSE:
                    print 'Unable to create the log directory. Logging to screen only.'

        # Start the logger, silence console logging if we need to
        logger.mylar_log.initLogger(verbose=VERBOSE)

        # Put the cache dir in the data dir for now
        if not CACHE_DIR:
            CACHE_DIR = os.path.join(str(DATA_DIR), 'cache')
        logger.info("cache set to : " + str(CACHE_DIR))
        if not os.path.exists(CACHE_DIR):
            try:
               os.makedirs(CACHE_DIR)
            except OSError:
                logger.error('Could not create cache dir. Check permissions of datadir: ' + DATA_DIR)

        # Sanity check for search interval. Set it to at least 6 hours
        if SEARCH_INTERVAL < 360:
            logger.info("Search interval too low. Resetting to 6 hour minimum")
            SEARCH_INTERVAL = 360


        # Initialize the database
        logger.info('Checking to see if the database has all tables....')
        try:
            dbcheck()
        except Exception, e:
            logger.error("Can't connect to the database: %s" % e)

        # Get the currently installed version - returns None, 'win32' or the git hash
        # Also sets INSTALL_TYPE variable to 'win', 'git' or 'source'
        CURRENT_VERSION = versioncheck.getVersion()

        # Check for new versions
        if CHECK_GITHUB_ON_STARTUP:
            try:
                LATEST_VERSION = versioncheck.checkGithub()
            except:
                LATEST_VERSION = CURRENT_VERSION
        else:
            LATEST_VERSION = CURRENT_VERSION

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

    # Do second fork
    try:
        pid = os.fork()
        if pid > 0:
            logger.debug('Forking twice...')
            os._exit(0) # Exit second parent process
    except OSError, e:
        sys.exit("2nd fork failed: %s [%d]" % (e.strerror, e.errno))

    os.chdir("/")
    os.umask(0)
    
    si = open('/dev/null', "r")
    so = open('/dev/null', "a+")
    se = open('/dev/null', "a+")
    
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    pid = os.getpid()
    logger.info('Daemonized to PID: %s' % pid)
    if PIDFILE:
        logger.info('Writing PID %s to %s' % (pid, PIDFILE))
        file(PIDFILE, 'w').write("%s\n" % pid)

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

    new_config['General'] = {}
    new_config['General']['config_version'] = CONFIG_VERSION
    new_config['General']['http_port'] = HTTP_PORT
    new_config['General']['http_host'] = HTTP_HOST
    new_config['General']['http_username'] = HTTP_USERNAME
    new_config['General']['http_password'] = HTTP_PASSWORD
    new_config['General']['http_root'] = HTTP_ROOT
    new_config['General']['launch_browser'] = int(LAUNCH_BROWSER)
    new_config['General']['log_dir'] = LOG_DIR
    new_config['General']['logverbose'] = int(LOGVERBOSE)
    new_config['General']['git_path'] = GIT_PATH
    new_config['General']['cache_dir'] = CACHE_DIR
    
    new_config['General']['check_github'] = int(CHECK_GITHUB)
    new_config['General']['check_github_on_startup'] = int(CHECK_GITHUB_ON_STARTUP)
    new_config['General']['check_github_interval'] = CHECK_GITHUB_INTERVAL

    new_config['General']['destination_dir'] = DESTINATION_DIR
    new_config['General']['usenet_retention'] = USENET_RETENTION

    new_config['General']['search_interval'] = SEARCH_INTERVAL
    new_config['General']['nzb_startup_search'] = int(NZB_STARTUP_SEARCH)
    new_config['General']['libraryscan'] = int(LIBRARYSCAN)
    new_config['General']['libraryscan_interval'] = LIBRARYSCAN_INTERVAL
    new_config['General']['add_comics'] = int(ADD_COMICS)
    new_config['General']['comic_dir'] = COMIC_DIR
    new_config['General']['imp_move'] = int(IMP_MOVE)
    new_config['General']['imp_rename'] = int(IMP_RENAME)
    new_config['General']['imp_metadata'] = int(IMP_METADATA)
    new_config['General']['download_scan_interval'] = DOWNLOAD_SCAN_INTERVAL
    new_config['General']['interface'] = INTERFACE
    new_config['General']['autowant_all'] = int(AUTOWANT_ALL)
    new_config['General']['autowant_upcoming'] = int(AUTOWANT_UPCOMING)
    new_config['General']['preferred_quality'] = int(PREFERRED_QUALITY)
    new_config['General']['comic_cover_local'] = int(COMIC_COVER_LOCAL)
    new_config['General']['correct_metadata'] = int(CORRECT_METADATA)
    new_config['General']['move_files'] = int(MOVE_FILES)
    new_config['General']['rename_files'] = int(RENAME_FILES)
    new_config['General']['folder_format'] = FOLDER_FORMAT
    new_config['General']['file_format'] = FILE_FORMAT
    new_config['General']['blackhole'] = int(BLACKHOLE)
    new_config['General']['blackhole_dir'] = BLACKHOLE_DIR
    new_config['General']['replace_spaces'] = int(REPLACE_SPACES)
    new_config['General']['replace_char'] = REPLACE_CHAR
    new_config['General']['zero_level'] = int(ZERO_LEVEL)
    new_config['General']['zero_level_n'] = ZERO_LEVEL_N
    new_config['General']['lowercase_filenames'] = LOWERCASE_FILENAMES
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

    new_config['SABnzbd'] = {}
    new_config['SABnzbd']['sab_host'] = SAB_HOST
    new_config['SABnzbd']['sab_username'] = SAB_USERNAME
    new_config['SABnzbd']['sab_password'] = SAB_PASSWORD
    new_config['SABnzbd']['sab_apikey'] = SAB_APIKEY
    new_config['SABnzbd']['sab_category'] = SAB_CATEGORY
    new_config['SABnzbd']['sab_priority'] = SAB_PRIORITY
    new_config['SABnzbd']['sab_directory'] = SAB_DIRECTORY

    new_config['NZBsu'] = {}
    new_config['NZBsu']['nzbsu'] = int(NZBSU)
    new_config['NZBsu']['nzbsu_apikey'] = NZBSU_APIKEY

    new_config['DOGnzb'] = {}
    new_config['DOGnzb']['dognzb'] = int(DOGNZB)
    new_config['DOGnzb']['dognzb_apikey'] = DOGNZB_APIKEY

    new_config['nzbx'] = {}
    new_config['nzbx']['nzbx'] = int(NZBX)

    new_config['Experimental'] = {}
    new_config['Experimental']['experimental'] = int(EXPERIMENTAL)

    new_config['Newznab'] = {}
    new_config['Newznab']['newznab'] = int(NEWZNAB)
    new_config['Newznab']['newznab_host'] = NEWZNAB_HOST
    new_config['Newznab']['newznab_apikey'] = NEWZNAB_APIKEY
    new_config['Newznab']['newznab_enabled'] = int(NEWZNAB_ENABLED)
    # Need to unpack the extra newznabs for saving in config.ini
    flattened_newznabs = []
    for newznab in EXTRA_NEWZNABS:
        for item in newznab:
            flattened_newznabs.append(item)

    new_config['Newznab']['extra_newznabs'] = flattened_newznabs

    new_config['Raw'] = {}
    new_config['Raw']['raw'] = int(RAW)
    new_config['Raw']['raw_provider'] = RAW_PROVIDER
    new_config['Raw']['raw_username'] = RAW_USERNAME
    new_config['Raw']['raw_password'] = RAW_PASSWORD
    new_config['Raw']['raw_groups'] = RAW_GROUPS

    new_config.write()
    
def start():
    
    global __INITIALIZED__, started
    
    if __INITIALIZED__:
    
        # Start our scheduled background tasks
        #from mylar import updater, searcher, librarysync, postprocessor

        from mylar import updater, search, weeklypull

        SCHED.add_interval_job(updater.dbUpdate, hours=48)
        SCHED.add_interval_job(search.searchforissue, minutes=SEARCH_INTERVAL)
        #SCHED.add_interval_job(librarysync.libraryScan, minutes=LIBRARYSCAN_INTERVAL)
        
        #weekly pull list gets messed up if it's not populated first, so let's populate it then set the scheduler.
        logger.info("Checking for existance of Weekly Comic listing...")
        threading.Thread(target=weeklypull.pullit).start()
        #now the scheduler (check every 24 hours)
        SCHED.add_interval_job(weeklypull.pullit, hours=24)
        
        #let's do a run at the Wanted issues here (on startup) if enabled.
        if NZB_STARTUP_SEARCH:
            threading.Thread(target=search.searchforissue).start()

        if CHECK_GITHUB:
            SCHED.add_interval_job(versioncheck.checkGithub, minutes=CHECK_GITHUB_INTERVAL)
        
        #SCHED.add_interval_job(postprocessor.checkFolder, minutes=DOWNLOAD_SCAN_INTERVAL)

        SCHED.start()
        
        started = True
    
def dbcheck():

    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS comics (ComicID TEXT UNIQUE, ComicName TEXT, ComicSortName TEXT, ComicYear TEXT, DateAdded TEXT, Status TEXT, IncludeExtras INTEGER, Have INTEGER, Total INTEGER, ComicImage TEXT, ComicPublisher TEXT, ComicLocation TEXT, ComicPublished TEXT, LatestIssue TEXT, LatestDate TEXT, Description TEXT, QUALalt_vers TEXT, QUALtype TEXT, QUALscanner TEXT, QUALquality TEXT, LastUpdated TEXT, AlternateSearch TEXT, UseFuzzy TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS issues (IssueID TEXT, ComicName TEXT, IssueName TEXT, Issue_Number TEXT, DateAdded TEXT, Status TEXT, Type TEXT, ComicID, ArtworkURL Text, ReleaseDate TEXT, Location TEXT, IssueDate TEXT, Int_IssueNumber INT, ComicSize TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS snatched (IssueID TEXT, ComicName TEXT, Issue_Number TEXT, Size INTEGER, DateAdded TEXT, Status TEXT, FolderName TEXT, ComicID TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS upcoming (ComicName TEXT, IssueNumber TEXT, ComicID TEXT, IssueID TEXT, IssueDate TEXT, Status TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS nzblog (IssueID TEXT, NZBName TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS weekly (SHIPDATE text, PUBLISHER text, ISSUE text, COMIC VARCHAR(150), EXTRA text, STATUS text)')
#    c.execute('CREATE TABLE IF NOT EXISTS sablog (nzo_id TEXT, ComicName TEXT, ComicYEAR TEXT, ComicIssue TEXT, name TEXT, nzo_complete TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS importresults (impID TEXT, ComicName TEXT, ComicYear TEXT, Status TEXT, ImportDate TEXT, ComicFilename TEXT, ComicLocation TEXT)')
    conn.commit
    c.close
    #new

    csv_load()

    
    #add in the late players to the game....
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
        c.execute('SELECT ComicSize from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN ComicSize TEXT')

    try:
        c.execute('SELECT UseFuzzy from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN UseFuzzy TEXT')
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
    c.execute("DELETE from COMICS WHERE ComicName='None' OR ComicName LIKE 'Comic ID%'")
    logger.info(u"Ensuring DB integrity - Removing all Erroneous Comics (ie. named None)")

    conn.commit()
    c.close()


def csv_load():
    # for redudant module calls..include this.
    conn=sqlite3.connect(DB_FILE)
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
            except (OSError,IOError):
                if i == 1:
                    logger.info("No Custom Exceptions found - Using base exceptions only. Creating blank custom_exceptions for your personal use.")
                    try:
                        shutil.copy(os.path.join(DATA_DIR,"custom_exceptions_sample.csv"), EXCEPTIONS_FILE)
                    except (OSError,IOError):
                        logger.error("Cannot create custom_exceptions.csv in " + str(DATA_DIR) + ". Make sure _sample.csv is present and/or check permissions.")
                        return  
                else:
                    logger.error("Could not locate " + str(EXCEPTIONS[i]) + " file. Make sure it's in datadir: " + DATA_DIR)
                break
        else:
            csvfile = open(str(EXCEPTIONS_FILE), "rb")
        if i == 0:
            logger.info(u"Populating Base Exception listings into Mylar....")
        elif i == 1:
            logger.info(u"Populating Custom Exception listings into Mylar....")

        creader = csv.reader(csvfile, delimiter=',')

        for row in creader:
            try:
                c.execute("INSERT INTO exceptions VALUES (?,?,?,?);", row)
            except Exception, e:
                #print ("Error - invald arguments...-skipping")
                pass
                pass
        csvfile.close()
        i+=1

    conn.commit()
    c.close()    

def shutdown(restart=False, update=False):

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

    if PIDFILE :
        logger.info ('Removing pidfile %s' % PIDFILE)
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
