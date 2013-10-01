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
import threading
import logging
import unicodedata  # for non-english locales
from logging import handlers

import mylar
from mylar import helpers

MAX_SIZE = 1000000 # 1mb
MAX_FILES = 5

ERROR = logging.ERROR
WARNING = logging.WARNING
MESSAGE = logging.INFO
DEBUG = logging.DEBUG
FDEBUG = logging.DEBUG

# Simple rotating log handler that uses RotatingFileHandler
class RotatingLogger(object):

    def __init__(self, filename, max_size, max_files):
    
        self.filename = filename
        self.max_size = max_size
        self.max_files = max_files
        
        
    def initLogger(self, verbose=1):
    
        l = logging.getLogger('mylar')
        l.setLevel(logging.DEBUG)
        
        self.filename = os.path.join(mylar.LOG_DIR, self.filename)
        
        filehandler = handlers.RotatingFileHandler(self.filename, maxBytes=self.max_size, backupCount=self.max_files)
        filehandler.setLevel(logging.DEBUG)
        
        fileformatter = logging.Formatter('%(asctime)s - %(levelname)-7s :: %(message)s', '%d-%b-%Y %H:%M:%S')
        
        filehandler.setFormatter(fileformatter)
        l.addHandler(filehandler)
        
        if verbose:
            consolehandler = logging.StreamHandler()
            if verbose == 1:
                consolehandler.setLevel(logging.INFO)
            if verbose == 2:
                consolehandler.setLevel(logging.DEBUG)
            consoleformatter = logging.Formatter('%(asctime)s - %(levelname)s :: %(message)s', '%d-%b-%Y %H:%M:%S')
            consolehandler.setFormatter(consoleformatter)
            l.addHandler(consolehandler)    
        
    def log(self, message, level):

        logger = logging.getLogger('mylar')
        
        threadname = threading.currentThread().getName()
        
        if level != 'DEBUG':
            if mylar.OS_DETECT == "Windows" and mylar.OS_ENCODING is not "utf-8":
                tmpthedate = unicodedata.normalize('NFKD', helpers.now().decode(mylar.OS_ENCODING, "replace"))
            else:
                tmpthedate = helpers.now()
            mylar.LOG_LIST.insert(0, (tmpthedate, message, level, threadname))
        
        message = threadname + ' : ' + message

        if level == 'DEBUG':
            logger.debug(message)
        elif level == 'INFO':
            logger.info(message)
        elif level == 'WARNING':
            logger.warn(message)
        elif level == 'FDEBUG':
            logger.debug(message)
        else:
            logger.error(message)

mylar_log = RotatingLogger('mylar.log', MAX_SIZE, MAX_FILES)

def debug(message):
    mylar_log.log(message, level='DEBUG')

def info(message):
    mylar_log.log(message, level='INFO')
    
def warn(message):
    mylar_log.log(message, level='WARNING')
    
def error(message):
    mylar_log.log(message, level='ERROR')

def fdebug(message):
    #if mylar.LOGVERBOSE == 1:
    mylar_log.log(message, level='DEBUG')
    #else:
    #    mylar_log.log(message, level='DEBUG')
    
