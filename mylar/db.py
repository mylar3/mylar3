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

#####################################
## Stolen from Sick-Beard's db.py  ##
#####################################



import os
import sqlite3
import threading
import time
import queue
import re

import mylar
from . import logger

db_lock = threading.Lock()
mylarQueue = queue.Queue()

def dbFilename(filename="mylar.db"):

    return os.path.join(mylar.DATA_DIR, filename)

class WriteOnly:

    def __init__(self):
        t = threading.Thread(target=self.worker, name="DB-WRITER")
        t.daemon = True
        t.start()
        logger.fdebug('Thread WriteOnly initialized.')

    def worker(self):
        myDB = DBConnection()
        #this should be in it's own thread somewhere, constantly polling the queue and sending them to the writer.
        logger.fdebug('worker started.')
        while True:
            thisthread = threading.current_thread().name
            if not mylarQueue.empty():
    # Rename the main thread
                logger.fdebug('[' + str(thisthread) + '] queue is not empty yet...')
                (QtableName, QvalueDict, QkeyDict) = mylarQueue.get(block=True, timeout=None)
                logger.fdebug('[REQUEUE] Table: ' + str(QtableName) + ' values: ' + str(QvalueDict) + ' keys: ' + str(QkeyDict))
                sqlResult = myDB.upsert(QtableName, QvalueDict, QkeyDict)
                if sqlResult:
                    mylarQueue.task_done()
                    return sqlResult
            else:
                time.sleep(1)
                #logger.fdebug('[' + str(thisthread) + '] sleeping until active.')

def _sqlite_regexp(exp, item):
    if exp is None or item is None:
        return False
    rex = re.compile(exp)
    return rex.search(item) is not None

class DBConnection:

    def __init__(self, filename="mylar.db"):

        self.filename = filename
        self.connection = sqlite3.connect(dbFilename(filename), timeout=20)
        self.connection.row_factory = sqlite3.Row
        self.queue = mylarQueue

        # Support REGEXP in SQLITE queries
        self.connection.create_function("REGEXP", 2, _sqlite_regexp, deterministic= True)

    def fetch(self, query, args=None):

        with db_lock:

            if query == None:
                return

            sqlResult = None
            attempt = 0

            while attempt < 5:
                try:
                    if args == None:
                        #logger.fdebug("[FETCH] : " + query)
                        cursor = self.connection.cursor()
                        sqlResult = cursor.execute(query)
                    else:
                        #logger.fdebug("[FETCH] : " + query + " with args " + str(args))
                        cursor = self.connection.cursor()
                        sqlResult = cursor.execute(query, args)
                    # get out of the connection attempt loop since we were successful
                    break
                except sqlite3.OperationalError as e:
                    if any(['unable to open database file' in e.args[0], 'database is locked' in e.args[0]]):
                        logger.warn('Database Error: %s' % e)
                        attempt += 1
                        time.sleep(1)
                    else:
                        logger.warn('DB error: %s' % e)
                        raise
                except sqlite3.DatabaseError as e:
                    logger.error('Fatal error executing query: %s' % e)
                    raise

            return sqlResult



    def action(self, query, args=None, executemany=False):

        with db_lock:
            if query == None:
                return

            sqlResult = None
            attempt = 0

            while attempt < 5:
                try:
                    if args == None:
                        if executemany is False:
                            sqlResult = self.connection.execute(query)
                        else:
                            sqlResult = self.connection.executemany(query)
                    else:
                        if executemany is False:
                            sqlResult = self.connection.execute(query, args)
                        else:
                            sqlResult = self.connection.executemany(query, args)
                    self.connection.commit()
                    break
                except sqlite3.OperationalError as e:
                    if any(['unable to open database file' in e.args[0], 'database is locked' in e.args[0]]):
                        logger.warn('Database Error: %s' % e)
                        logger.warn('sqlresult: %s' %  query)
                        attempt += 1
                        time.sleep(1)
                    else:
                        logger.error('Database error executing %s :: %s' % (query, e))
                        raise
            return sqlResult

    def select(self, query, args=None):

        sqlResults = self.fetch(query, args).fetchall()

        if sqlResults == None:
            return []

        return sqlResults

    def selectone(self, query, args=None):
        sqlResults = self.fetch(query, args)

        if sqlResults == None:
            return []

        return sqlResults


    def upsert(self, tableName, valueDict, keyDict):
        thisthread = threading.current_thread().name

        changesBefore = self.connection.total_changes

        genParams = lambda myDict: [x + " = ?" for x in list(myDict.keys())]

        query = "UPDATE " + tableName + " SET " + ", ".join(genParams(valueDict)) + " WHERE " + " AND ".join(genParams(keyDict))

        self.action(query, list(valueDict.values()) + list(keyDict.values()))

        if self.connection.total_changes == changesBefore:
            query = "INSERT INTO " +tableName +" (" + ", ".join(list(valueDict.keys()) + list(keyDict.keys())) + ")" + \
                        " VALUES (" + ", ".join(["?"] * len(list(valueDict.keys()) + list(keyDict.keys()))) + ")"
            self.action(query, list(valueDict.values()) + list(keyDict.values()))


        #else:
        #    logger.info('[' + str(thisthread) + '] db is currently locked for writing. Queuing this action until it is free')
        #    logger.info('Table: ' + str(tableName) + ' Values: ' + str(valueDict) + ' Keys: ' + str(keyDict))
        #    self.queue.put( (tableName, valueDict, keyDict) )
        #    #assuming this is coming in from a seperate thread, so loop it until it's free to write.
        #    #self.queuesend()


