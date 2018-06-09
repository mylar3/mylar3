#  This file is part of Mylar.
# -*- coding: utf-8 -*-
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
import re
import threading
import sqlite3
import json

import mylar
from mylar import logger, importer

class Maintenance(object):

    def __init__(self, mode, file=None, output=None):
        self.mode = mode
        self.maintenance_db = os.path.join(mylar.DATA_DIR, '.mylar_maintenance.db')
        if self.mode == 'database-import':
            self.dbfile = file
        else:
            self.dbfile = mylar.DB_FILE
        self.file = file
        self.outputfile = output
        self.comiclist = []
        self.maintenance_success = []
        self.maintenance_fail = []

    def sql_attachmylar(self):
        self.connectmylar = sqlite3.connect(self.dbfile)
        self.dbmylar = self.connectmylar.cursor()

    def sql_closemylar(self):
        self.connectmylar.commit()
        self.dbmylar.close()

    def sql_attach(self):
        self.conn = sqlite3.connect(self.maintenance_db)
        self.db = self.conn.cursor()
        self.db.execute('CREATE TABLE IF NOT EXISTS maintenance (id TEXT, mode TEXT, status TEXT, progress TEXT, total TEXT, current TEXT, last_comicid TEXT, last_series TEXT, last_seriesyear TEXT)')

    def sql_close(self):
        self.conn.commit()
        self.db.close()

    def database_import(self):
        self.sql_attachmylar()

        comicidlist = self.dbmylar.execute('SELECT * FROM comics')
        for i in comicidlist:
            self.comiclist.append(i['ComicID'])

        self.sql_closemylar()

        self.importIT()

    def json_import(self):
        self.comiclist = json.load(open(self.file))
        logger.info('[MAINTENANCE-MODE][JSON-IMPORT] Found %s series within json listing. Preparing to mass import to existing db.' % (len(self.comiclist)))
        self.importIT()

    def json_export(self):
        self.sql_attachmylar()

        for i in self.dbmylar.execute('SELECT ComicID FROM comics'):
            self.comiclist.append({'ComicID': i[0]})

        self.sql_closemylar()

        with open(self.outputfile, 'wb') as outfile:
            json.dump(self.comiclist, outfile)

        logger.info('[MAINTENANCE-MODE][%s] Successfully exported %s ComicID\'s to json file: %s' % (self.mode.upper(), len(self.comiclist), self.outputfile))

    def fix_slashes(self):
        self.sql_attachmylar()

        for ct in self.dbmylar.execute("SELECT ComicID, ComicLocation FROM comics WHERE ComicLocation like ?", ['%' + os.sep.encode('unicode-escape') + os.sep.encode('unicode-escape') + '%']):
            st = ct[1].find(os.sep.encode('unicode-escape')+os.sep.encode('unicode-escape'))
            if st != -1:
                rootloc = ct[1][:st]
                clocation = ct[1][st+2:]
                if clocation[0] != os.sep.encode('unicode-escape'):
                    new_path = os.path.join(rootloc, clocation)
                    logger.info('[Incorrect slashes in path detected for OS] %s' % os.path.join(rootloc, ct[1]))
                    logger.info('[PATH CORRECTION] %s' % new_path)
                    self.comiclist.append({'ComicLocation': new_path,
                                           'ComicID': ct[0]})

        for cm in self.comiclist:
            try:
                self.dbmylar.execute("UPDATE comics SET ComicLocation=? WHERE ComicID=?", (cm['ComicLocation'], cm['ComicID']))
            except Exception as e:
                logger.warn('Unable to correct entry: [ComicID:%s] %s [%e]' % (cm['ComicLocation'], cm['ComicID'],e))

        self.sql_closemylar()

        if len(self.comiclist) >0:
            logger.info('[MAINTENANCE-MODE][%s] Successfully fixed the path slashes for %s series' % (self.mode.upper(), len(self.comiclist)))
        else:
            logger.info('[MAINTENANCE-MODE][%s] No series found with incorrect slashes in the path' % self.mode.upper())

    def check_status(self):
        try:
            found = False
            self.sql_attach()
            checkm = self.db.execute('SELECT * FROM maintenance')
            for cm in checkm:
                found = True
                if 'import' in cm[1]:
                    logger.info('[MAINTENANCE-MODE][STATUS] Current Progress: %s [%s / %s]' % (cm[2].upper(), cm[3], cm[4]))
                    if cm[2] == 'running':
                        try:
                            logger.info('[MAINTENANCE-MODE][STATUS] Current Import: %s' % (cm[5]))
                            if cm[6] is not None:
                                logger.info('[MAINTENANCE-MODE][STATUS] Last Successful Import: %s [%s]' % (cm[7], cm[6]))
                        except:
                            pass
                    elif cm[2] == 'completed':
                        logger.info('[MAINTENANCE-MODE][STATUS] Last Successful Import: %s [%s]' % (cm[7], cm[6]))
                else:
                    logger.info('[MAINTENANCE-MODE][STATUS] Current Progress: %s [mode: %s]' % (cm[2].upper(), cm[1]))
            if found is False:
                raise Error
        except Exception as e:
            logger.info('[MAINTENANCE-MODE][STATUS] Nothing is currently running')

        self.sql_close()

    def importIT(self):
        #set startup...
        if len(self.comiclist) > 0:
            self.sql_attach()
            query = "DELETE FROM maintenance"
            self.db.execute(query)
            query = "INSERT INTO maintenance (id, mode, total, status) VALUES (%s,'%s',%s,'%s')" % ('1', self.mode, len(self.comiclist), "running")
            self.db.execute(query)
            self.sql_close()
            logger.info('[MAINTENANCE-MODE][%s] Found %s series in previous db. Preparing to migrate into existing db.' % (self.mode.upper(), len(self.comiclist)))
            count = 1
            for x in self.comiclist:
                logger.info('[MAINTENANCE-MODE][%s] [%s/%s] now attempting to add %s to watchlist...' % (self.mode.upper(), count, len(self.comiclist), x['ComicID']))
                try:
                    self.sql_attach()
                    self.db.execute("UPDATE maintenance SET progress=?, total=?, current=? WHERE id='1'", (count, len(self.comiclist), re.sub('4050-', '', x['ComicID'].strip())))
                    self.sql_close()
                except Exception as e:
                    logger.warn('[ERROR] %s' % e)
                maintenance_info = importer.addComictoDB(re.sub('4050-', '', x['ComicID']).strip(), calledfrom='maintenance')
                try:
                    logger.info('MAINTENANCE: %s' % maintenance_info)
                    if maintenance_info['status'] == 'complete':
                        logger.fdebug('[MAINTENANCE-MODE][%s] Successfully added %s [%s] to watchlist.' % (self.mode.upper(), maintenance_info['comicname'], maintenance_info['year']))
                    else:
                        logger.fdebug('[MAINTENANCE-MODE][%s] Unable to add %s [%s] to watchlist.' % (self.mode.upper(), maintenance_info['comicname'], maintenance_info['year']))
                        raise IOError
                    self.maintenance_success.append(x)

                    try:
                        self.sql_attach()
                        self.db.execute("UPDATE maintenance SET progress=?, last_comicid=?, last_series=?, last_seriesyear=? WHERE id='1'", (count, re.sub('4050-', '', x['ComicID'].strip()), maintenance_info['comicname'], maintenance_info['year']))
                        self.sql_close()
                    except Exception as e:
                        logger.warn('[ERROR] %s' % e)


                except IOError as e:
                    logger.warn('[MAINTENANCE-MODE][%s] Unable to add series to watchlist: %s' % (self.mode.upper(), e))
                    self.maintenance_fail.append(x)

                count+=1
        else:
            logger.warn('[MAINTENANCE-MODE][%s] Unable to locate any series in db. This is probably a FATAL error and an unrecoverable db.' % self.mode.upper())
            return

        logger.info('[MAINTENANCE-MODE][%s] Successfully imported %s series into existing db.' % (self.mode.upper(), len(self.maintenance_success)))
        if len(self.maintenance_fail) > 0:
            logger.info('[MAINTENANCE-MODE][%s] Failed to import %s series into existing db: %s' % (self.mode.upper(), len(self.maintenance_success), self.maintenance_fail))
        try:
            self.sql_attach()
            self.db.execute("UPDATE maintenance SET status=? WHERE id='1'", ["completed"])
            self.sql_close()
        except Exception as e:
            logger.warn('[ERROR] %s' % e)

