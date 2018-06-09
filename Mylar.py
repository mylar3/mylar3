#!/usr/bin/env python
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
import errno
import shutil
import time
import threading
import signal

sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'lib'))

import mylar

from mylar import webstart, logger, filechecker, versioncheck, maintenance

import argparse


if ( sys.platform == 'win32' and sys.executable.split( '\\' )[-1] == 'pythonw.exe'):
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

def handler_sigterm(signum, frame):
    mylar.SIGNAL = 'shutdown'


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
        print 'language detected as non-English (%s). Forcing specific logging module - errors WILL NOT be captured in the logs' % logger.LOG_LANG
    else:
        print 'log language set to %s' % logger.LOG_LANG

    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(description='Automated Comic Book Downloader')
    subparsers = parser.add_subparsers(title='Subcommands', dest='maintenance')
    parser_maintenance = subparsers.add_parser('maintenance', help='Enter maintenance mode (no GUI). Additional commands are available (maintenance --help)')

    #main parser
    parser.add_argument('-v', '--verbose', action='store_true', help='Increase console logging verbosity')
    parser.add_argument('-q', '--quiet', action='store_true', help='Turn off console logging')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument('-p', '--port', type=int, help='Force mylar to run on a specified port')
    parser.add_argument('-b', '--backup', action='store_true', help='Will automatically backup & keep the last 2 copies of the .db & ini files prior to startup')
    parser.add_argument('-w', '--noweekly', action='store_true', help='Turn off weekly pull list check on startup (quicker boot sequence)')
    parser.add_argument('--datadir', help='Specify a directory where to store your data files')
    parser.add_argument('--config', help='Specify a config file to use')
    parser.add_argument('--nolaunch', action='store_true', help='Prevent browser from launching on startup')
    parser.add_argument('--pidfile', help='Create a pid file (only relevant when running as a daemon)')
    parser.add_argument('--safe', action='store_true', help='redirect the startup page to point to the Manage Comics screen on startup')
    parser_maintenance.add_argument('-xj', '--exportjson', action='store', help='Export existing mylar.db to json file')
    parser_maintenance.add_argument('-id', '--importdatabase', action='store', help='Import a mylar.db into current db')
    parser_maintenance.add_argument('-ij', '--importjson', action='store', help='Import a specified json file containing just {"ComicID": "XXXXX"} into current db')
    parser_maintenance.add_argument('-st', '--importstatus', action='store_true', help='Provide current maintenance status')
    parser_maintenance.add_argument('-u', '--update', action='store_true', help='force mylar to perform an update as if in GUI')
    parser_maintenance.add_argument('-fs', '--fixslashes', action='store_true', help='remove double-slashes from within paths in db')
    #parser_maintenance.add_argument('-it', '--importtext', action='store', help='Import a specified text file into current db')

    args = parser.parse_args()

    if args.maintenance:
        if all([args.exportjson is None, args.importdatabase is None, args.importjson is None, args.importstatus is False, args.update is False, args.fixslashes is False]):
            print 'Expecting subcommand with the maintenance positional argumeent'
            sys.exit()
        mylar.MAINTENANCE = True
    else:
        mylar.MAINTENANCE = False

    if args.verbose:
        print 'Verbose/Debugging mode enabled...'
        mylar.LOG_LEVEL = 2
    elif args.quiet:
        mylar.QUIET = True
        print 'Quiet logging mode enabled...'
        mylar.LOG_LEVEL = 0
    else:
        mylar.LOG_LEVEL = 1

    if args.daemon:
        if sys.platform == 'win32':
            print "Daemonize not supported under Windows, starting normally"
        else:
            mylar.DAEMON = True

    if args.pidfile:
        mylar.PIDFILE = str(args.pidfile)

        # If the pidfile already exists, mylar may still be running, so exit
        if os.path.exists(mylar.PIDFILE):
            sys.exit("PID file '" + mylar.PIDFILE + "' already exists. Exiting.")

        # The pidfile is only useful in daemon mode, make sure we can write the file properly
        if mylar.DAEMON:
            mylar.CREATEPID = True
            try:
                file(mylar.PIDFILE, 'w').write("pid\n")
            except IOError, e:
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
    if args.backup:
        print '[AUTO-BACKUP] Backing up .db and config.ini files for safety.'
        backupdir = os.path.join(mylar.DATA_DIR, 'backup')

        try:
            os.makedirs(backupdir)
            print '[AUTO-BACKUP] Directory does not exist for backup - creating : ' + backupdir
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                print '[AUTO-BACKUP] Directory already exists.'
                raise

        i = 0
        while (i < 2):
            if i == 0:
                ogfile = mylar.DB_FILE
                back = os.path.join(backupdir, 'mylar.db')
                back_1 = os.path.join(backupdir, 'mylar.db.1')
            else:
                ogfile = mylar.CONFIG_FILE
                back = os.path.join(backupdir, 'config.ini')
                back_1 = os.path.join(backupdir, 'config.ini.1')

            try:
                print '[AUTO-BACKUP] Now Backing up mylar.db file'
                if os.path.isfile(back_1):
                    print '[AUTO-BACKUP] ' + back_1 + ' exists. Deleting and keeping new.'
                    os.remove(back_1)
                if os.path.isfile(back):
                    print '[AUTO-BACKUP] Now renaming ' + back + ' to ' + back_1
                    shutil.move(back, back_1)
                print '[AUTO-BACKUP] Now copying db file to ' + back
                shutil.copy(ogfile, back)

            except OSError as exception:
                if exception.errno != errno.EXIST:
                    raise

            i += 1

    # Rename the main thread
    threading.currentThread().name = "MAIN"

    if mylar.DAEMON:
        mylar.daemonize()

    if mylar.MAINTENANCE is True and any([args.exportjson, args.importjson, args.update is True, args.importstatus is True, args.fixslashes is True]):
        loggermode = '[MAINTENANCE-MODE]'
        if args.importstatus: #mylar.MAINTENANCE is True:
            cs = maintenance.Maintenance('status')
            cstat = cs.check_status()
        else:
            logger.info('%s Initializing maintenance mode' % loggermode)

            if args.update is True:
                logger.info('%s Attempting to update Mylar so things can work again...' % loggermode)
                try:
                    mylar.shutdown(restart=True, update=True, maintenance=True)
                except Exception as e:
                    sys.exit('%s Mylar failed to update: %s' % (loggermode, e))

            elif args.importdatabase:
                #for attempted db import.
                maintenance_path = args.importdatabase
                logger.info('%s db path accepted as %s' % (loggermode, maintenance_path))
                di = maintenance.Maintenance('database-import', file=maintenance_path)
                d = di.database_import()
            elif args.importjson:
                #for attempted file re-import (json format)
                maintenance_path = args.importjson
                logger.info('%s file indicated as being in json format - path accepted as %s' % (loggermode, maintenance_path))
                ij = maintenance.Maintenance('json-import', file=maintenance_path)
                j = ij.json_import()
            #elif args.importtext:
            #    #for attempted file re-import (list format)
            #    maintenance_path = args.importtext
            #    logger.info('%s file indicated as being in list format - path accepted as %s' % (loggermode, maintenance_path))
            #    it = maintenance.Maintenance('list-import', file=maintenance_path)
            #    t = it.list_import()
            elif args.exportjson:
                #for export of db comicid's in json format
                maintenance_path = args.exportjson
                logger.info('%s file indicated as being written to json format - destination accepted as %s' % (loggermode, maintenance_path))
                ej = maintenance.Maintenance('json-export', output=maintenance_path)
                j = ej.json_export()
            elif args.fixslashes:
                #for running the fix slashes on the db manually
                logger.info('%s method indicated as fix slashes' % loggermode)
                fs = maintenance.Maintenance('fixslashes')
                j = fs.fix_slashes()
            else:
                logger.info('%s Not a valid command: %s' % (loggermode, maintenance_info))
                sys.exit()
            logger.info('%s Exiting Maintenance mode' % (loggermode))

        #possible option to restart automatically after maintenance has completed...
        sys.exit()

    # Force the http port if neccessary
    if args.port:
        http_port = args.port
        logger.info('Starting Mylar on forced port: %i' % http_port)
    else:
        http_port = int(mylar.CONFIG.HTTP_PORT)

    # Check if pyOpenSSL is installed. It is required for certificate generation
    # and for CherryPy.
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
        'opds_enable': mylar.CONFIG.OPDS_ENABLE,
        'opds_authentication': mylar.CONFIG.OPDS_AUTHENTICATION,
        'opds_username': mylar.CONFIG.OPDS_USERNAME,
        'opds_password': mylar.CONFIG.OPDS_PASSWORD,
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
                mylar.SIGNAL = 'shutdown'
        else:
            logger.info('Received signal: ' + mylar.SIGNAL)
            if mylar.SIGNAL == 'shutdown':
                mylar.shutdown()
            elif mylar.SIGNAL == 'restart':
                mylar.shutdown(restart=True)
            else:
                mylar.shutdown(restart=True, update=True)

            mylar.SIGNAL = None

    return

if __name__ == "__main__":
    main()
