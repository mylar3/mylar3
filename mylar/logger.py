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

import os
import sys
import logging
import traceback
import threading
import mylar

from logging import handlers

from mylar import helpers

# These settings are for file logging only
FILENAME = 'mylar.log'
MAX_FILES = 5

# Mylar logger
logger = logging.getLogger('mylar')

class LogListHandler(logging.Handler):
    """
    Log handler for Web UI.
    """

    def emit(self, record):
        message = self.format(record)
        message = message.replace("\n", "<br />")
        mylar.LOG_LIST.insert(0, (helpers.now(), message, record.levelname, record.threadName))

def initLogger(verbose=1):
    if mylar.MAX_LOGSIZE:
        MAX_SIZE = mylar.MAX_LOGSIZE
    else:
        MAX_SIZE = 1000000 # 1 MB

    """
    Setup logging for Mylar. It uses the logger instance with the name
    'mylar'. Three log handlers are added:

    * RotatingFileHandler: for the file Mylar.log
    * LogListHandler: for Web UI
    * StreamHandler: for console (if verbose > 0)
    """

    # Configure the logger to accept all messages
    logger.propagate = False
    logger.setLevel(logging.DEBUG)# if verbose == 2 else logging.INFO)

    # Setup file logger
    filename = os.path.join(mylar.LOG_DIR, FILENAME)

    file_formatter = logging.Formatter('%(asctime)s - %(levelname)-7s :: %(threadName)s : %(message)s', '%d-%b-%Y %H:%M:%S')
    file_handler = handlers.RotatingFileHandler(filename, maxBytes=MAX_SIZE, backupCount=MAX_FILES)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    logger.addHandler(file_handler)

    # Add list logger
    loglist_handler = LogListHandler()
    #-- this needs to get enabled and logging changed everywhere so the accessing the log GUI won't hang the system.
    #-- right now leave it set to INFO only, everything else will still get logged to the mylar.log file.
    #if verbose == 2:
    #    loglist_handler.setLevel(logging.DEBUG)
    #else:
    #    loglist_handler.setLevel(logging.INFO)
    #--
    loglist_handler.setLevel(logging.INFO)
    logger.addHandler(loglist_handler)

    # Setup console logger
    if verbose:
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s :: %(threadName)s : %(message)s', '%d-%b-%Y %H:%M:%S')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        #print 'verbose is ' + str(verbose)        
        #if verbose == 2:
        #    console_handler.setLevel(logging.DEBUG)
        #else:
        #    console_handler.setLevel(logging.INFO)
        console_handler.setLevel(logging.INFO)

        logger.addHandler(console_handler)

    # Install exception hooks
    initHooks()

def initHooks(global_exceptions=True, thread_exceptions=True, pass_original=True):
    """
    This method installs exception catching mechanisms. Any exception caught
    will pass through the exception hook, and will be logged to the logger as
    an error. Additionally, a traceback is provided.

    This is very useful for crashing threads and any other bugs, that may not
    be exposed when running as daemon.

    The default exception hook is still considered, if pass_original is True.
    """

    def excepthook(*exception_info):
        # We should always catch this to prevent loops!
        try:
            message = "".join(traceback.format_exception(*exception_info))
            logger.error("Uncaught exception: %s", message)
        except:
            pass

        # Original excepthook
        if pass_original:
            sys.__excepthook__(*exception_info)

    # Global exception hook
    if global_exceptions:
        sys.excepthook = excepthook

    # Thread exception hook
    if thread_exceptions:
        old_init = threading.Thread.__init__

        def new_init(self, *args, **kwargs):
            old_init(self, *args, **kwargs)
            old_run = self.run

            def new_run(*args, **kwargs):
                try:
                    old_run(*args, **kwargs)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    excepthook(*sys.exc_info())
            self.run = new_run

        # Monkey patch the run() by monkey patching the __init__ method
        threading.Thread.__init__ = new_init

# Expose logger methods
info = logger.info
warn = logger.warn
error = logger.error
debug = logger.debug
warning = logger.warning
message = logger.info
exception = logger.exception
fdebug = logger.debug
