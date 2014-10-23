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
import time
import threading
import signal

from lib.configobj import ConfigObj

import mylar

from mylar import webstart, logger, filechecker, versioncheck

try:
    import argparse
except ImportError:
    import lib.argparse as argparse

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
    
    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(description='Comic Book add-on for SABnzbd+')

    parser.add_argument('-v', '--verbose', action='store_true', help='Increase console logging verbosity')
    parser.add_argument('-q', '--quiet', action='store_true', help='Turn off console logging')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument('-p', '--port', type=int, help='Force mylar to run on a specified port')
    parser.add_argument('--datadir', help='Specify a directory where to store your data files')
    parser.add_argument('--config', help='Specify a config file to use')
    parser.add_argument('--nolaunch', action='store_true', help='Prevent browser from launching on startup')
    parser.add_argument('--pidfile', help='Create a pid file (only relevant when running as a daemon)')
    parser.add_argument('--safe', action='store_true', help='redirect the startup page to point to the Manage Comics screen on startup')
    #parser.add_argument('-u', '--update', action='store_true', help='force mylar to perform an update as if in GUI')
    
    args = parser.parse_args()

    if args.verbose:
        mylar.VERBOSE = 2
    elif args.quiet:
        mylar.VERBOSE = 0
    
    #if args.update:
    #    print('Attempting to update Mylar so things can work again...')
    #    try:
    #        versioncheck.update()
    #    except Exception, e:
    #        sys.exit('Mylar failed to update.')


    if args.daemon:
        if sys.platform == 'win32':
            print "Daemonize not supported under Windows, starting normally"
        else:
            mylar.DAEMON=True
            mylar.VERBOSE=0

    if args.pidfile :
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
            logger.warn("Not running in daemon mode. PID file creation disabled.")


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

    # Try to create the DATA_DIR if it doesn't exist
    #if not os.path.exists(mylar.DATA_DIR):
    #    try:
    #        os.makedirs(mylar.DATA_DIR)
    #    except OSError:
    #        raise SystemExit('Could not create data directory: ' + mylar.DATA_DIR + '. Exiting....')

    filechecker.validateAndCreateDirectory(mylar.DATA_DIR, True)
    
    # Make sure the DATA_DIR is writeable
    if not os.access(mylar.DATA_DIR, os.W_OK):
        raise SystemExit('Cannot write to the data directory: ' + mylar.DATA_DIR + '. Exiting...')
    
    # Put the database in the DATA_DIR
    mylar.DB_FILE = os.path.join(mylar.DATA_DIR, 'mylar.db')
    
    mylar.CFG = ConfigObj(mylar.CONFIG_FILE, encoding='utf-8')

    # Rename the main thread
    threading.currentThread().name = "MAIN"
    
    # Read config & start logging
    mylar.initialize()
        
    if mylar.DAEMON:
        mylar.daemonize()

    # Force the http port if neccessary
    if args.port:
        http_port = args.port
        logger.info('Starting Mylar on foced port: %i' % http_port)
    else:
        http_port = int(mylar.HTTP_PORT)
        
    # Try to start the server. 
    webstart.initialize({
                    'http_port':        http_port,
                    'http_host':        mylar.HTTP_HOST,
                    'http_root':        mylar.HTTP_ROOT,
                    'http_username':    mylar.HTTP_USERNAME,
                    'http_password':    mylar.HTTP_PASSWORD,
            })
    
    logger.info('Starting Mylar on port: %i' % http_port)
    
    if mylar.LAUNCH_BROWSER and not args.nolaunch:
        mylar.launch_browser(mylar.HTTP_HOST, http_port, mylar.HTTP_ROOT)
        
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
