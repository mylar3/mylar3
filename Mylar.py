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

import os, sys, locale
import argparse
import errno
import shutil
import time
import re
import threading
import signal

sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'lib'))

import mylar

from mylar import webstart, logger, filechecker, versioncheck, maintenance, maintenance_webstart

import argparse


if ( sys.platform == 'win32' and sys.executable.split( '\\' )[-1] == 'pythonw.exe'):
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

def handler_sigterm(signum, frame):
    mylar.SIGNAL = 'shutdown'

def check_stale_pidfile(pidfile):
    ''' Return True if pidfile doesn't hold a numeric value, or it
        does, but it doesn't correspond with a valid currently used PID.
        Only supports linux /proc fs way of getting cmdlinee by PID.
        Returns:  Unsupported, assume it's not stale (False)
                  pidfile contents aren't numeric, return True
                  On linux, if the /proc/{pid}/cmdline file doesn't
                  exist: True (this is definitive)
                  Otherwise return True if python isn't in the cmdline
    '''

    if sys.platform != 'linux' or not os.path.exists('/proc'):
        return False

    with open(pidfile, 'rt', encoding='utf-8') as fd:
        sval = fd.read()

    if not sval.isdigit():
        return True

    checkpid = int(sval, 10)
    cmdlinepath = f'/proc/{checkpid}/cmdline'
    if not os.path.exists(cmdlinepath):
        return True

# We'll simplify the check here and only verify that the word python is part
# of the commandline

    with open(cmdlinepath, 'rt', encoding='utf-8') as fd:
        cmdline = fd.read().replace('\0')

# If pytohn is in the cmdline, then we assume it's not stale.
    return ('python' not in cmdline)

def main():

    # Fixed paths to mylar
    if hasattr(sys, 'frozen'):
        mylar.FULL_PATH = os.path.abspath(sys.executable)
    else:
        mylar.FULL_PATH = os.path.abspath(__file__)

    mylar.PROG_DIR = os.path.dirname(mylar.FULL_PATH)
    mylar.ARGS = sys.argv[1:]

    # From sickbeard
    mylar.SYS_ENCODING = None

    try:
        locale.setlocale(locale.LC_ALL, "")
        mylar.SYS_ENCODING = locale.getpreferredencoding()
    except (locale.Error, IOError):
        pass

    # for OSes that are poorly configured I'll just force UTF-8
    if not mylar.SYS_ENCODING or mylar.SYS_ENCODING in ('ANSI_X3.4-1968', 'US-ASCII', 'ASCII'):
        mylar.SYS_ENCODING = 'UTF-8'

    if not logger.LOG_LANG.startswith('en'):
        print('language detected as non-English (%s). Forcing specific logging module - errors WILL NOT be captured in the logs' % logger.LOG_LANG)
    else:
        print('log language set to %s' % logger.LOG_LANG)

    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(description='Automated Comic Book Downloader')
    subparsers = parser.add_subparsers(title='Subcommands', dest='maintenance')

    #main parser
    parser.add_argument('-v', '--verbose', action='store_true', help='Increase console logging verbosity')
    parser.add_argument('-q', '--quiet', action='store_true', help='Turn off console logging')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument('-p', '--port', type=int, help='Force mylar to run on a specified port')
    parser.add_argument('-b', '--backup', nargs='?', const='both', help='Will automatically backup & keep the last 4 rolling copies.')
    parser.add_argument('-w', '--noweekly', action='store_true', help='Turn off weekly pull list check on startup (quicker boot sequence)')
    parser.add_argument('-iu', '--ignoreupdate', action='store_true', help='Do not update db if required (for problem bypass)')
    parser.add_argument('--datadir', help='Specify a directory where to store your data files')
    parser.add_argument('--config', help='Specify a config file to use')
    parser.add_argument('--nolaunch', action='store_true', help='Prevent browser from launching on startup')
    parser.add_argument('--pidfile', help='Create a pid file (only relevant when running as a daemon)')
    parser.add_argument('--safe', action='store_true', help='redirect the startup page to point to the Manage Comics screen on startup')

    parser_maintenance = subparsers.add_parser('maintenance', help='Enter maintenance mode (no GUI). Additional commands are available (maintenance --help)')
    parser_maintenance.add_argument('-xj', '--exportjson', action='store', help='Export existing mylar.db to json file', default=argparse.SUPPRESS)
    parser_maintenance.add_argument('-id', '--importdatabase', action='store', help='Import a mylar.db into current db', default=argparse.SUPPRESS)
    parser_maintenance.add_argument('-ij', '--importjson', action='store', help='Import a specified json file containing just {"ComicID": "XXXXX"} into current db', default=argparse.SUPPRESS)
    parser_maintenance.add_argument('-st', '--importstatus', action='store_true', help='Provide current maintenance status', default=argparse.SUPPRESS)
    parser_maintenance.add_argument('-u', '--update', action='store_true', help='force mylar to perform an update as if in GUI', default=argparse.SUPPRESS)
    parser_maintenance.add_argument('-fs', '--fixslashes', action='store_true', help='remove double-slashes from within paths in db', default=argparse.SUPPRESS)
    #parser_maintenance.add_argument('-it', '--importtext', action='store', help='Import a specified text file into current db')

    args = parser.parse_args()

    #these need to be set for things to register
    args_exportjson = None
    args_importdatabase = None
    args_importjson = None
    args_importstatus = False
    args_update = False
    args_fixslashes = False

    if 'exportjson' in args:
        args_exportjson = args.exportjson
    if 'importdatabase' in args:
        args_importdatabase = args.importdatabase
    if 'importjson' in args:
        args_importjson = args.importjson
    if 'importstatus' in args:
        args_importstatus = True
    if 'update'in args:
        args_update = True
    if 'fixslashes' in args:
        args_fixslashes = True

    if args.maintenance:
        if all([args_exportjson is None, args_importdatabase is None, args_importjson is None, args_importstatus is False, args_update is False, args_fixslashes is False]):
            print('Expecting subcommand with the maintenance positional argumeent')
            sys.exit()
        mylar.MAINTENANCE = True
    else:
        mylar.MAINTENANCE = False

    if args.verbose:
        print('Verbose/Debugging mode enabled...')
        mylar.LOG_LEVEL = 2
    elif args.quiet:
        mylar.QUIET = True
        print('Quiet logging mode enabled...')
        mylar.LOG_LEVEL = 0
    else:
        mylar.LOG_LEVEL = None

    if args.ignoreupdate:
        mylar.MAINTENANCE = False

    if args.daemon:
        if sys.platform == 'win32':
            print("Daemonize not supported under Windows, starting normally")
        else:
            mylar.DAEMON = True

    if args.pidfile:
        mylar.PIDFILE = str(args.pidfile)

        # If the pidfile already exists, mylar may still be running, so exit
        if os.path.exists(mylar.PIDFILE):
            if check_stale_pidfile(mylar.PIDFILE):
                os.unlink(mylar.PIDFILE)
            else:
                sys.exit("PID file '" + mylar.PIDFILE + "' already exists. Exiting.")

        # The pidfile is only useful in daemon mode, make sure we can write the file properly
        if mylar.DAEMON:
            mylar.CREATEPID = True
            curpid = os.getpid()
            try:
                open(mylar.PIDFILE, 'w').write(f"{curpid}\n")
            except IOError as e:
                raise SystemExit("Unable to write PID file: %s [%d]" % (e.strerror, e.errno))
        else:
            print("Not running in daemon mode. PID file creation disabled.")

    if args.datadir:
        mylar.DATA_DIR = args.datadir
    else:
        mylar.DATA_DIR = mylar.PROG_DIR

    if args.config:
        mylar.CONFIG_FILE = args.config
    else:
        mylar.CONFIG_FILE = os.path.join(mylar.DATA_DIR, 'config.ini')

    if args.safe:
        mylar.SAFESTART = True
    else:
        mylar.SAFESTART = False

    if args.noweekly:
        mylar.NOWEEKLY = True
    else:
        mylar.NOWEEKLY = False

    try:
        backup = False
        backup_db = False
        backup_cfg = False
        if 'backup' in args:
            backup = True
            if args.backup == 'ini':
                backup_cfg = True
            elif args.backup == 'db':
                backup_db = True
            elif args.backup == 'both':
                backup_cfg = True
                backup_db = True
            else:
                backup = False
    except Exception as e:
        backup = False

    # Put the database in the DATA_DIR
    mylar.DB_FILE = os.path.join(mylar.DATA_DIR, 'mylar.db')

    # Read config and start logging
    if mylar.MAINTENANCE is False:
        print('Initializing startup sequence....')

    #try:
    mylar.initialize(mylar.CONFIG_FILE)
    #except Exception as e:
    #    print e
    #    raise SystemExit('FATAL ERROR')

    if mylar.MAINTENANCE is False:
        filechecker.validateAndCreateDirectory(mylar.DATA_DIR, True)

        # Make sure the DATA_DIR is writeable
        if not os.access(mylar.DATA_DIR, os.W_OK):
            raise SystemExit('Cannot write to the data directory: ' + mylar.DATA_DIR + '. Exiting...')

    # backup the db and configs before they load.
    if (backup is True and any([backup_cfg is True, backup_db is True])) or mylar.CONFIG.BACKUP_ON_START:
        if mylar.CONFIG.BACKUP_ON_START:
            backup_cfg = True
            backup_db = True
        if mylar.CONFIG.BACKUP_ON_START or all([backup_cfg is True, backup_db is True]):
            logger.info('[AUTO-BACKUP] Backing up mylar.db & config.ini files for safety.')
        elif backup_cfg is True:
            logger.info('[AUTO-BACKUP] Backing up config.ini file for safety.')
        elif backup_db is True:
            logger.info('[AUTO-BACKUP] Backing up mylar.db file for safety.')

        mm = maintenance.Maintenance('backup')
        back_check = mm.backup_files(cfg=backup_cfg, dbs=backup_db)
        failures = [re.sub('mylar database', 'mylar.db', x['file']) for x in back_check if x['status'] == 'failure']
        successes = [re.sub('mylar database', 'mylar.db', x['file']) for x in back_check if x['status'] == 'success']
        if failures:
            logger.warn('[AUTO-BACKUP] Failure backing up %s files [%s]' % (len(failures), failures))
        if successes:
            logger.info('[AUTO-BACKUP] Successful backup of %s files [%s]' % (len(successes), successes))

    # Rename the main thread
    threading.current_thread().name = "MAIN"

    if mylar.DAEMON:
        mylar.daemonize()

    #print('mylar.MAINTENANCE: %s'%  mylar.MAINTENANCE)
    #print('mylar.MAINTENANCE_TOTAL: %s'%  mylar.MAINTENANCE_DB_TOTAL)
    if mylar.MAINTENANCE is True and (mylar.MAINTENANCE_UPDATE or any([args_exportjson, args_importjson, args_update is True, args_importstatus is True, args_fixslashes is True])):
        # Start up a temporary maintenance server for GUI display only.
        maint_config = {
            'http_port': int(mylar.CONFIG.HTTP_PORT),
            'http_host': mylar.CONFIG.HTTP_HOST,
            'http_root': mylar.CONFIG.HTTP_ROOT,
            'enable_https': mylar.CONFIG.ENABLE_HTTPS,
            'https_cert': mylar.CONFIG.HTTPS_CERT,
            'https_key': mylar.CONFIG.HTTPS_KEY,
            'https_chain': mylar.CONFIG.HTTPS_CHAIN,
            'http_username': mylar.CONFIG.HTTP_USERNAME,
            'http_password': mylar.CONFIG.HTTP_PASSWORD,
            'authentication': mylar.CONFIG.AUTHENTICATION,
            'login_timeout': mylar.CONFIG.LOGIN_TIMEOUT
        }

        # Try to start the server.
        maintenance_webstart.initialize(maint_config)
        versioncheck.versionload()
        print("started")
        loggermode = '[MAINTENANCE-MODE]'

        restart_method = True  #True will restart, False will shutdown.

        if mylar.MAINTENANCE_UPDATE:
            ur = maintenance.Maintenance('db update')
            restart_method = ur.update_db()
            if restart_method is None:
                restart_method = True

        elif args_importstatus:
            cs = maintenance.Maintenance('status')
            cstat = cs.check_status()
        else:
            logger.info('%s Initializing maintenance mode' % loggermode)

            if args_update is True:
                logger.info('%s Attempting to update Mylar so things can work again...' % loggermode)
                try:
                    mylar.shutdown(restart=True, update=True, maintenance=True)
                except Exception as e:
                    sys.exit('%s Mylar failed to update: %s' % (loggermode, e))

            elif args_importdatabase:
                #for attempted db import.
                maintenance_path = args_importdatabase
                logger.info('%s db path accepted as %s' % (loggermode, maintenance_path))
                di = maintenance.Maintenance('database-import', file=maintenance_path)
                d = di.database_import()
            elif args_importjson:
                #for attempted file re-import (json format)
                maintenance_path = args_importjson
                logger.info('%s file indicated as being in json format - path accepted as %s' % (loggermode, maintenance_path))
                ij = maintenance.Maintenance('json-import', file=maintenance_path)
                j = ij.json_import()
            #elif args.importtext:
            #    #for attempted file re-import (list format)
            #    maintenance_path = args.importtext
            #    logger.info('%s file indicated as being in list format - path accepted as %s' % (loggermode, maintenance_path))
            #    it = maintenance.Maintenance('list-import', file=maintenance_path)
            #    t = it.list_import()
            elif args_exportjson:
                #for export of db comicid's in json format
                maintenance_path = args_exportjson
                logger.info('%s file indicated as being written to json format - destination accepted as %s' % (loggermode, maintenance_path))
                ej = maintenance.Maintenance('json-export', output=maintenance_path)
                j = ej.json_export()
            elif args_fixslashes:
                #for running the fix slashes on the db manually
                logger.info('%s method indicated as fix slashes' % loggermode)
                fs = maintenance.Maintenance('fixslashes')
                j = fs.fix_slashes()
            else:
                logger.info('%s Not a valid command: %s' % (loggermode, args.maintenance))
                sys.exit()
            logger.info('%s Exiting Maintenance mode' % (loggermode))

        #restart automatically after maintenance has completed...

        maintenance_webstart.shutdown()
        logger.info('%s Maintenance webserver has been shut down.'% (loggermode))
        mylar.shutdown(restart=restart_method, maintenance=True)

    # Force the http port if neccessary
    if args.port:
        http_port = args.port
        logger.info('Starting Mylar on forced port: %i' % http_port)
    else:
        http_port = int(mylar.CONFIG.HTTP_PORT)

    # Check if pyOpenSSL is installed. It is required for certificate generation
    # and for cherrypy.
    if mylar.CONFIG.ENABLE_HTTPS:
        try:
            import OpenSSL
        except ImportError:
            logger.warn("The pyOpenSSL module is missing. Install this " \
                "module to enable HTTPS. HTTPS will be disabled.")
            mylar.CONFIG.ENABLE_HTTPS = False

    # Try to start the server. Will exit here is address is already in use.
    web_config = {
        'http_port': http_port,
        'http_host': mylar.CONFIG.HTTP_HOST,
        'http_root': mylar.CONFIG.HTTP_ROOT,
        'enable_https': mylar.CONFIG.ENABLE_HTTPS,
        'https_cert': mylar.CONFIG.HTTPS_CERT,
        'https_key': mylar.CONFIG.HTTPS_KEY,
        'https_chain': mylar.CONFIG.HTTPS_CHAIN,
        'http_username': mylar.CONFIG.HTTP_USERNAME,
        'http_password': mylar.CONFIG.HTTP_PASSWORD,
        'authentication': mylar.CONFIG.AUTHENTICATION,
        'login_timeout': mylar.CONFIG.LOGIN_TIMEOUT,
        'cherrypy_logging': mylar.CONFIG.CHERRYPY_LOGGING,
        'opds_enable': mylar.CONFIG.OPDS_ENABLE,
        'opds_authentication': mylar.CONFIG.OPDS_AUTHENTICATION,
        'opds_username': mylar.CONFIG.OPDS_USERNAME,
        'opds_password': mylar.CONFIG.OPDS_PASSWORD,
        'opds_pagesize': mylar.CONFIG.OPDS_PAGESIZE,
    }

    # Try to start the server.
    webstart.initialize(web_config)

    #check for version here after web server initialized so it doesn't try to repeatidly hit github
    #for version info if it's already running
    versioncheck.versionload()

    if mylar.CONFIG.LAUNCH_BROWSER and not args.nolaunch:
        mylar.launch_browser(mylar.CONFIG.HTTP_HOST, http_port, mylar.CONFIG.HTTP_ROOT)

    # Start the background threads
    mylar.start()

    signal.signal(signal.SIGTERM, handler_sigterm)

    while True:
        if not mylar.SIGNAL:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'event': 'shutdown', 'message': 'Now shutting down system.'}
                time.sleep(1)
                mylar.SIGNAL = 'shutdown'
        else:
            logger.info('Received signal: ' + mylar.SIGNAL)
            if mylar.SIGNAL == 'shutdown':
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'event': 'shutdown', 'message': 'Now shutting down system.'}
                time.sleep(2)
                mylar.shutdown()
            elif mylar.SIGNAL == 'restart':
                mylar.shutdown(restart=True)
            else:
                mylar.shutdown(restart=True, update=True)

            mylar.SIGNAL = None

    return

if __name__ == "__main__":
    main()
