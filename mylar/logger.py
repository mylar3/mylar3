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
import inspect
import traceback
import threading
import platform
import locale
import mylar
from mylar import helpers
import logging
from logging import getLogger, WARN, ERROR, INFO, DEBUG, StreamHandler, Formatter, Handler
from lib.six import PY2

#setup logger for non-english (this doesnt carry thru, so check here too)
try:
    localeinfo = locale.getdefaultlocale()
    language = localeinfo[0]
    charset = localeinfo[1]
    if any([language is None, charset is None]):
        raise AttributeError
except AttributeError:
    #if it's set to None (ie. dockerized) - default to en_US.UTF-8.
    if language is None:
        language = 'en_US'
    if charset is None:
        charset = 'UTF-8'

LOG_LANG = language
LOG_CHARSET = charset

if not LOG_LANG.startswith('en'):
    # Simple rotating log handler that uses RotatingFileHandler
    class RotatingLogger(object):

        def __init__(self, filename):

            self.filename = filename
            self.filehandler = None
            self.consolehandler = None

        def stopLogger(self):
            lg = logging.getLogger('mylar')
            lg.removeHandler(self.filehandler)
            lg.removeHandler(self.consolehandler)

        def handle_exception(self, exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logger.exception('Uncaught Exception', excinfo=(exc_type, exc_value, exc_traceback))
            sys.__excepthook__(exc_type, exc_value, None)
            return

        def initLogger(self, loglevel=1, log_dir=None, max_logsize=None, max_logfiles=None):
            import sys
            sys.excepthook = RotatingLogger.handle_exception

            logging.getLogger('apscheduler.scheduler').setLevel(logging.WARN)
            logging.getLogger('apscheduler.threadpool').setLevel(logging.WARN)
            logging.getLogger('apscheduler.scheduler').propagate = False
            logging.getLogger('apscheduler.threadpool').propagate = False
            lg = logging.getLogger('mylar')
            lg.setLevel(logging.DEBUG)

            self.filename = os.path.join(log_dir, self.filename)

            #concurrentLogHandler/0.8.7 (to deal with windows locks)
            #since this only happens on windows boxes, if it's nix/mac use the default logger.
            if mylar.OS_DETECT == 'Windows':
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

            filehandler = RFHandler(
                self.filename,
                maxBytes=max_logsize,
                backupCount=max_logfiles)

            filehandler.setLevel(logging.DEBUG)

            fileformatter = logging.Formatter('%(asctime)s - %(levelname)-7s :: %(message)s', '%d-%b-%Y %H:%M:%S')

            filehandler.setFormatter(fileformatter)
            lg.addHandler(filehandler)
            self.filehandler = filehandler

            if loglevel:
                consolehandler = logging.StreamHandler()
                if loglevel == 1:
                    consolehandler.setLevel(logging.INFO)
                if loglevel >= 2:
                    consolehandler.setLevel(logging.DEBUG)
                consoleformatter = logging.Formatter('%(asctime)s - %(levelname)s :: %(message)s', '%d-%b-%Y %H:%M:%S')
                consolehandler.setFormatter(consoleformatter)
                lg.addHandler(consolehandler)
                self.consolehandler = consolehandler

        @staticmethod
        def log(message, level):
            logger = logging.getLogger('mylar')

            threadname = threading.currentThread().getName()

            # Get the frame data of the method that made the original logger call
            if len(inspect.stack()) > 2:
                frame = inspect.getframeinfo(inspect.stack()[2][0])
                program = os.path.basename(frame.filename)
                method = frame.function
                lineno = frame.lineno
            else:
                program = ""
                method = ""
                lineno = ""

            if PY2:
                message = safe_unicode(message)
                message = message.encode(mylar.SYS_ENCODING)
            if level != 'DEBUG' or mylar.LOG_LEVEL >= 2:
                mylar.LOGLIST.insert(0, (helpers.now(), message, level, threadname))
                if len(mylar.LOGLIST) > 2500:
                    del mylar.LOGLIST[-1]

            message = "%s : %s:%s:%s : %s" % (threadname, program, method, lineno, message)
            if level == 'DEBUG':
                logger.debug(message)
            elif level == 'INFO':
                logger.info(message)
            elif level == 'WARNING':
                logger.warning(message)
            else:
                logger.error(message)

    mylar_log = RotatingLogger('mylar.log')
    filename = 'mylar.log'

    def debug(message):
        if mylar.LOG_LEVEL > 1:
            mylar_log.log(message, level='DEBUG')

    def fdebug(message):
        if mylar.LOG_LEVEL > 1:
            mylar_log.log(message, level='DEBUG')

    def info(message):
        if mylar.LOG_LEVEL > 0:
            mylar_log.log(message, level='INFO')

    def warn(message):
        mylar_log.log(message, level='WARNING')

    def error(message):
        mylar_log.log(message, level='ERROR')

    def safe_unicode(obj, *args):
        """ return the unicode representation of obj """
        if not PY2:
            return str(obj, *args)
        try:
            return unicode(obj, *args)
        except UnicodeDecodeError:
            ascii_text = str(obj).encode('string_escape')
            return unicode(ascii_text)

else:
    # Mylar logger
    logger = logging.getLogger('mylar')

    class LogListHandler(logging.Handler):
        """
        Log handler for Web UI.
        """

        def emit(self, record):
            message = self.format(record)
            message = message.replace("\n", "<br />")
            mylar.LOGLIST.insert(0, (helpers.now(), message, record.levelname, record.threadName))

    def initLogger(console=False, log_dir=False, init=False, loglevel=1, max_logsize=None, max_logfiles=5):
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

        if all([init is True, max_logsize is None]):
            max_logsize = 1000000 #1 MB
        else:
            if max_logsize is None:
                max_logsize = 1000000 # 1 MB

        """
        Setup logging for Mylar. It uses the logger instance with the name
        'mylar'. Three log handlers are added:

        * RotatingFileHandler: for the file Mylar.log
        * LogListHandler: for Web UI
        * StreamHandler: for console
        """

        logging.getLogger('apscheduler.scheduler').setLevel(logging.WARN)
        logging.getLogger('apscheduler.threadpool').setLevel(logging.WARN)
        logging.getLogger('apscheduler.scheduler').propagate = False
        logging.getLogger('apscheduler.threadpool').propagate = False


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

        if init is True:
            logger.setLevel(logging.INFO)
        else:
            if loglevel == 1:  #normal
                logger.setLevel(logging.INFO)
            elif loglevel >= 2:   #verbose
                logger.setLevel(logging.DEBUG)

        # Add list logger
        loglist_handler = LogListHandler()
        loglist_handler.setLevel(logging.DEBUG)
        logger.addHandler(loglist_handler)

        # Setup file logger
        if log_dir:
            filename = os.path.join(log_dir, 'mylar.log')
            file_formatter = Formatter('%(asctime)s - %(levelname)-7s :: %(name)s.%(funcName)s.%(lineno)s : %(threadName)s : %(message)s', '%d-%b-%Y %H:%M:%S')
            file_handler = RFHandler(filename, "a", maxBytes=max_logsize, backupCount=max_logfiles)
            if loglevel == 1:  #normal
                file_handler.setLevel(logging.INFO)
            elif loglevel >= 2:   #verbose
                file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)

            logger.addHandler(file_handler)

        # Setup console logger
        if console:
            console_formatter = logging.Formatter('%(asctime)s - %(levelname)s :: %(name)s.%(funcName)s.%(lineno)s : %(threadName)s : %(message)s', '%d-%b-%Y %H:%M:%S')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(console_formatter)
            if loglevel == 1:  #normal
                console_handler.setLevel(logging.INFO)
            elif loglevel >= 2:   #verbose
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
