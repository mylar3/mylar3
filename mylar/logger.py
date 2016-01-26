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
import platform
import mylar

from logging import getLogger, INFO, DEBUG, StreamHandler, Formatter, Handler

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

def initLogger(console=False, log_dir=False, verbose=False):
    #concurrentLogHandler/0.8.7 (to deal with windows locks)
    #since this only happens on windows boxes, if it's nix/mac use the default logger.
    if platform.system() == 'Windows':
        #set the path to the lib here - just to make sure it can detect cloghandler & portalocker.
        import sys
        sys.path.append(os.path.join(mylar.PROG_DIR, 'lib'))

        try:
            from ConcurrentLogHandler.cloghandler import ConcurrentRotatingFileHandler as RFHandler
            mylar.LOGTYPE = 'clog'
        except ImportError:
            mylar.LOGTYPE = 'log'
            from logging.handlers import RotatingFileHandler as RFHandler
    else:
        mylar.LOGTYPE = 'log'
        from logging.handlers import RotatingFileHandler as RFHandler


    if mylar.MAX_LOGSIZE:
        MAX_SIZE = mylar.MAX_LOGSIZE
    else:
        MAX_SIZE = 1000000 # 1 MB

    """
    Setup logging for Mylar. It uses the logger instance with the name
    'mylar'. Three log handlers are added:

    * RotatingFileHandler: for the file Mylar.log
    * LogListHandler: for Web UI
    * StreamHandler: for console
    """

    # Close and remove old handlers. This is required to reinit the loggers
    # at runtime
    for handler in logger.handlers[:]:
        # Just make sure it is cleaned up.
        if isinstance(handler, RFHandler):
            handler.close()
        elif isinstance(handler, logging.StreamHandler):
            handler.flush()

        logger.removeHandler(handler)

    # Configure the logger to accept all messages
    logger.propagate = False
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Add list logger
    loglist_handler = LogListHandler()
    loglist_handler.setLevel(logging.DEBUG)
    logger.addHandler(loglist_handler)

    # Setup file logger
    if log_dir:
        filename = os.path.join(mylar.LOG_DIR, FILENAME)
        file_formatter = Formatter('%(asctime)s - %(levelname)-7s :: %(threadName)s : %(message)s', '%d-%b-%Y %H:%M:%S')
        file_handler = RFHandler(filename, "a", maxBytes=MAX_SIZE, backupCount=MAX_FILES)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)

        logger.addHandler(file_handler)

    # Setup console logger
    if console:
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s :: %(threadName)s : %(message)s', '%d-%b-%Y %H:%M:%S')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.DEBUG)

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
