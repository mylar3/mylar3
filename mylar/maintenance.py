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
import shutil
import glob

import mylar
from mylar import logger, importer, filechecker, helpers

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
        self.db_version = 0

    def sql_attachmylar(self):
        self.connectmylar = sqlite3.connect(self.dbfile)
        self.dbmylar = self.connectmylar.cursor()

    def sql_closemylar(self):
        self.connectmylar.commit()
        self.dbmylar.close()

    def sql_attach(self):
        self.conn = sqlite3.connect(self.maintenance_db)
        self.db = self.conn.cursor()
        if self.mode == 'db update':
            self.db.execute('CREATE TABLE IF NOT EXISTS update_db (version INT, mode TEXT PRIMARY KEY, status TEXT, total INT, current INT, last_run TEXT)')
        else:
            self.db.execute('CREATE TABLE IF NOT EXISTS maintenance (id TEXT, mode TEXT, status TEXT, progress TEXT, total TEXT, current TEXT, last_comicid TEXT, last_series TEXT, last_seriesyear TEXT)')
        self.conn.commit()

    def sql_close(self):
        self.conn.commit()
        self.db.close()

    def db_version_check(self, display=True):
        self.db_version = 0
        tmp_version = 0

        self.sql_attachmylar()
        self.dbmylar.execute('SELECT DatabaseVersion from mylar_info')
        tmp_version = self.dbmylar.fetchone()
        if not tmp_version:
            self.db_version = 0
        else:
            self.db_version = tmp_version[0]
        self.sql_closemylar()

        #self.sql_attach()
        #for vchk in self.db.execute('SELECT version, status from update_db'):
        #    if vchk[1] == 'complete':
        #        self.db_version = vchk[0]
        #    elif vchk[1] == 'incomplete':
        #        self.db_version = tmp_version
        #    tmp_version = vchk[0]
        #self.sql_close()

        if display:
            logger.fdebug('[DB_VERSION_CHECK] Database version is v%s' % (self.db_version))


    def db_update_check(self):
        # this is meant to hold all the updates that are required to be run against the dB at any given time.
        # if a dbupdate is required of any kind, it will be initiated and controlled from via direct code.

        self.db_version_check()

        if self.db_version < 1:

            # -- rssdb table - ComicName and Issue_Number added.
            # Values are generated based on existing data

            self.sql_attachmylar()
            try:
                self.dbmylar.execute('SELECT Issue_Number from rssdb')
            except sqlite3.OperationalError:
                self.dbmylar.execute('ALTER TABLE rssdb ADD COLUMN Issue_Number TEXT')
                if not any(d.get('mode', None) == 'rss update' for d in mylar.MAINTENANCE_UPDATE):
                    mylar.MAINTENANCE_UPDATE.append({'mode': 'rss update', 'resume': 0})

            try:
                self.dbmylar.execute('SELECT ComicName from rssdb')
            except sqlite3.OperationalError:
                self.dbmylar.execute('ALTER TABLE rssdb ADD COLUMN ComicName TEXT')
                if not any(d.get('mode', None) == 'rss update' for d in mylar.MAINTENANCE_UPDATE):
                    mylar.MAINTENANCE_UPDATE.append({'mode': 'rss update', 'resume': 0})


            if not any(d.get('mode', None) == 'rss update' for d in mylar.MAINTENANCE_UPDATE):
                try:
                    number_check = self.dbmylar.execute('SELECT rowid from rssdb WHERE Issue_Number is NULL AND ComicName is NULL ORDER BY rowid ASC LIMIT 10')
                    checked = number_check.fetchall()
                    if checked:
                        chk_cnt = 0
                        resume = []
                        for ck in checked:
                            if chk_cnt == 0:
                                lower = ck[0]
                                upper = ck[0]
                                chk_cnt += 1
                                continue
                            else:
                                upper = ck[0]
                            if lower+1 == upper:
                                resume.append(lower) # + 1)

                            lower = upper
                            chk_cnt += 1

                        if len(resume) > 3:
                            logger.info('[DB-CHECK-UPDATE] Tables are correct, but some data is possibly incorrect. Attempting to resume the RSS Update from record %s' % resume[0])
                            if not any(d.get('mode', None) == 'rss update' for d in mylar.MAINTENANCE_UPDATE):
                                mylar.MAINTENANCE_UPDATE.append({'mode': 'rss update', 'resume': resume[0]})
                    else:
                        if self.db_version == 0:
                            logger.info('Updating database to v1 as no data is present to update')
                            try:
                                self.dbmylar.execute("UPDATE mylar_info SET DatabaseVersion=? WHERE DatabaseVersion=?", (1, self.db_version))
                            except Exception as e:
                                print('error: %s' % e)
                            else:
                                self.db_version = 1
                except Exception as e:
                   logger.fdebug('[DB-CHECK-UPDATE] Checking DB for sequence containing NULL values did not complete. Ignoring this check.')

            self.sql_closemylar()
        else:
            if not mylar.MAINTENANCE_UPDATE:
                logger.fdebug('[DB-CHECK-UPDATE] Nothing needs updating within dB.')


    def check_failed_update(self):
        self.sql_attach()
        query = 'SELECT * FROM update_db'
        check_update = self.db.execute(query)
        checked = check_update.fetchone()
        if checked is not None:
            if checked[2] == 'incomplete':
                if not any(d.get('mode', None) == checked[1] for d in mylar.MAINTENANCE_UPDATE):
                    logger.info('[PREVIOUS_UPDATE_CHECK] Previous update of database did not complete. Let\'s do this again! (it is a requirement)')
                    mylar.MAINTENANCE_UPDATE.append({'mode': checked[1], 'resume': checked[4]})
        else:
            logger.info('checked is None')
        self.sql_close()

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

    def clear_provider_table(self):
        self.sql_attachmylar()
        # drop it
        self.dbmylar.execute("DROP TABLE provider_searches")
        # bring it back hot
        self.dbmylar.execute("CREATE TABLE IF NOT EXISTS provider_searches(id INTEGER UNIQUE, provider TEXT UNIQUE, type TEXT, lastrun INTEGER, active TEXT, hits INTEGER DEFAULT 0)")
        self.sql_closemylar()
        mylar.CONFIG.writeconfig(values={'clear_provider_table': False})
        logger.info('[MAINTENANCE-MODE][%s] Successfully cleared the provider_searches table' % (self.mode.upper()))

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

    def db_update_status(self, statusinfo):
        self.sql_attach()

        #if statusinfo['status'] == 'incomplete':
        #    query = "DELETE from update_db where status='incomplete'"
        #    self.db.execute(query)
        #    query = "INSERT INTO update_db(version, status, total, current, last_run, mode) VALUES (?,?,?,?,?,?)"
        #else:
        query = 'INSERT OR REPLACE INTO update_db(mode, version, status, total, current, last_run) VALUES(?,?,?,?,?,?)'

        try:
            args = (statusinfo['mode'], statusinfo['version'], statusinfo['status'], statusinfo['total'], statusinfo['current'], statusinfo['last_run'])
            self.db.execute(query, args)
        except Exception as e :
            print('error_writing: %s' % e)
        self.sql_close()
        if statusinfo['status'] == 'complete':
            try:
                self.sql_attachmylar()
                print('status_version: %s / db_version: %s' % (statusinfo['version'], self.db_version))
                self.dbmylar.execute("UPDATE mylar_info SET DatabaseVersion=? WHERE DatabaseVersion=?", (statusinfo['version'], self.db_version))
            except Exception as e:
                print('error: %s' % e)
            self.sql_closemylar()


    def toggle_logging(self, level):
        #force set logging to warning level only so the progress indicator can be displayed in console
        wc = mylar.webserve.WebInterface()
        wc.toggleVerbose(level=level)

    def backup_files(self, cfg=False, dbs=False, backupinfo=None):
        cfgloop = []
        if cfg is True:
            cfgloop.append('config.ini')
        if dbs is True:
            cfgloop.append('mylar database')
        rtn_message = []

        if backupinfo is None:
            location = mylar.CONFIG.BACKUP_LOCATION
            config_version = mylar.CONFIG.CONFIG_VERSION
            backup_retention = mylar.CONFIG.BACKUP_RETENTION
        else:
            location = backupinfo['location']
            config_version = backupinfo['config_version']
            backup_retention = backupinfo['backup_retention']

        if not os.path.exists(location):
            try:
                os.makedirs(location)
            except OSError:
                logger.error('[Backup Location Check] Could not create backup directory. Check permissions for creation of : %s' % location)

        for cf in cfgloop:
            logger.info('Attempting to backup %s...' % cf)
            if cf == 'mylar database':
                if location is None:
                    cback_path = os.path.join(mylar.DATA_DIR, 'mylar.db.backup')
                    root_path = mylar.DATA_DIR
                else:
                    cback_path = os.path.join(location, 'mylar.db.backup')
                    root_path = location
                cf_val = 'mylar.db.backup.???'
                source_file = self.dbfile
            else:
                if location is None:
                    cback_path = os.path.join(mylar.DATA_DIR, 'config.ini-v%s.backup' % (config_version))
                    root_path = mylar.DATA_DIR
                else:
                    cback_path = os.path.join(location, 'config.ini-v%s.backup' % (config_version))
                    root_path = location
                cf_val = 'config.ini-v%s.backup.???' % config_version
                source_file = mylar.CONFIG_FILE
            try:
                #start naming backup files as mylar.db.backup.xxx or config.ini-vXX.backup.xxx
                if os.path.exists(cback_path):
                    max_value = None
                    for f in sorted(glob.glob(os.path.join(root_path, cf_val)), reverse=True):
                        backup_num = f[-3:]
                        if backup_num.isdigit():
                            if backup_retention > int(backup_num):
                                bpath = cback_path + '.{:03d}'.format(int(backup_num)+1)
                                #logger.fdebug('[Rolling_Versioning %s-%s] copying %s to %s' % (int(backup_num), int(backup_num)+1, f, bpath))
                                shutil.copy2(f, bpath)

                    #logger.fdebug('[Rolling_Versioning %s-%s] copying %s to %s' % (int(backup_num), '0', cback_path, cback_path + '.000'))
                    shutil.copy2(cback_path, cback_path + '.000')

                    #logger.fdebug('[Rolling_Versioning %s-%s] copying %s to %s' % ('original', '.backup', source_file, cback_path))
                    shutil.copy2(source_file, cback_path)
                    db_backed = cback_path
                else:
                    #logger.fdebug('Backing up existing %s as %s' % (cf, cback_path))
                    shutil.copy2(source_file, cback_path)
                    db_backed = cback_path
            except Exception as e:
                logger.warn('[%s] Unable to make proper backup of %s in %s' % (e, cf, source_file))
                rtn_message.append({'status': 'failure', 'file': cf})
            else:
                if os.path.exists(db_backed):
                    logger.info('Successfully backed up %s to %s.' % (cf, db_backed))
                    rtn_message.append({'status': 'success', 'file': cf})
                else:
                    logger.warn('Unable to verify backup location of %s - backup of %s might not have been successful.' % (db_backed, cf))
                    rtn_message.append({'status': 'failure', 'file': cf})

        return rtn_message

    def update_db(self):

        # mylar.MAINTENANCE_UPDATE will indicate what's being updated in the db
        if mylar.MAINTENANCE_UPDATE:
            self.db_version_check(display=False)

            # backup mylar.db here
            self.backup_files(dbs=True)

            for dmode in mylar.MAINTENANCE_UPDATE:
                if dmode['mode'] == 'rss update':
                    logger.info('[MAINTENANCE-MODE][DB-CONVERSION] Updating dB due to RSS table conversion')
                    if dmode['resume'] > 0:
                        logger.info('[MAINTENANCE-MODE][DB-CONVERSION][DB-RECOVERY] Attempting to resume conversion from previous run (starting at record: %s)' % dmode['resume'])

                #force set logging to warning level only so the progress indicator can be displayed in console
                prev_log_level = mylar.LOG_LEVEL
                self.toggle_logging(level=0)

                if dmode['mode'] == 'rss update':
                    self.sql_attachmylar()

                    row_cnt = self.dbmylar.execute("SELECT COUNT(rowid) as count FROM rssdb")
                    rowcnt = row_cnt.fetchone()[0]
                    mylar.MAINTENANCE_DB_TOTAL = rowcnt

                    if dmode['resume'] > 0:
                        xt = self.dbmylar.execute("SELECT rowid, Title FROM rssdb WHERE rowid >= ? ORDER BY rowid ASC", [dmode['resume']])
                    else:
                        xt = self.dbmylar.execute("SELECT rowid, Title FROM rssdb ORDER BY rowid ASC")
                    xlist = xt.fetchall()

                    mylar.MAINTENANCE_DB_COUNT = 0

                    if xlist is None:
                        print('Nothing in the rssdb to update. Ignoring.')
                        return True

                    try:
                        if dmode['resume'] > 0 and xlist is not None:
                            logger.info('resume set at : %s' % (xlist[dmode['resume']],))
                            #xlist[dmode['resume']:]
                            mylar.MAINTENANCE_DB_COUNT = dmode['resume']
                    except Exception as e:
                        print('[ERROR:%s] - table resume location is not accureate. Starting from start, but this should go quick..' % e)
                        xt = self.dbmylar.execute("SELECT rowid, Title FROM rssdb ORDER BY rowid ASC")
                        xlist = xt.fetchall()
                        dmode['resume'] = 0

                    if xlist:
                        resultlist = []
                        delete_rows = []
                        for x in self.progressBar(xlist, prefix='Progress', suffix='Complete', length = 50, resume=dmode['resume']):

                            #signal capture here since we can't do it as per normal
                            if any([mylar.SIGNAL == 'shutdown', mylar.SIGNAL == 'restart']):
                                try:
                                    self.dbmylar.executemany("UPDATE rssdb SET Issue_Number=?, ComicName=? WHERE rowid=?", (resultlist))
                                    self.sql_closemylar()
                                except Exception as e:
                                    print('error: %s' % e)
                                else:
                                    send_it = {'mode': dmode['mode'],
                                               'version': self.db_version,
                                               'status': 'incomplete',
                                               'total': mylar.MAINTENANCE_DB_TOTAL,
                                               'current': mylar.MAINTENANCE_DB_COUNT,
                                               'last_run': helpers.utctimestamp()}
                                    self.db_update_status(send_it)

                                #toggle back the logging level to what it was originally.
                                self.toggle_logging(level=prev_log_level)

                                if mylar.SIGNAL == 'shutdown':
                                    logger.info('[MAINTENANCE-MODE][DB-CONVERSION][SHUTDOWN]Shutting Down...')
                                    return False
                                else:
                                    logger.info('[MAINTENANCE-MODE][DB-CONVERSION][RESTART]Restarting...')
                                    return True

                            mylar.MAINTENANCE_DB_COUNT +=1
                            if not x[1]:
                                logger.fdebug('[MAINTENANCE-MODE][DB-CONVERSION][JUNK-NAME] %s' % x[1])
                                delete_rows.append((x[0],))
                                continue
                            try:
                                if any(ext in x[1] for ext in ['yenc', '.pdf', '.rar', '.mp4', '.avi']):
                                    logger.fdebug('[MAINTENANCE-MODE][DB-CONVERSION][JUNK-NAME] %s' % x[1])
                                    delete_rows.append((x[0],))
                                    continue
                                else:
                                    flc = filechecker.FileChecker(file=x[1])
                                    filelist = flc.listFiles()
                            except Exception as e:
                                logger.fdebug('[MAINTENANCE-MODE][DB-CONVERSION][JUNK-NAME] %s' % x[1])
                                delete_rows.append((x[0],))
                                continue
                            else:
                                if all([filelist['series_name'] != '', filelist['series_name'] is not None]) and filelist['issue_number'] != '-':
                                    issuenumber = filelist['issue_number']
                                    seriesname = re.sub(r'[\u2014|\u2013|\u2e3a|\u2e3b]', '-', filelist['series_name']).strip()
                                    if seriesname.endswith('-') and '#' in seriesname[-6:]:
                                        ck1 = seriesname.rfind('#')
                                        ck2 = seriesname.rfind('-')
                                        if seriesname[ck1+1:ck2-1].strip().isdigit():
                                            issuenumber = '%s %s' % (seriesname[ck1:].strip(), issuenumber)
                                            seriesname = seriesname[:ck1 -1].strip()
                                            issuenumber.strip()
                                    resultlist.append((issuenumber, seriesname.strip(), x[0]))

                                if len(resultlist) > 500:
                                    # write it out every 5000 records.
                                    try:
                                        logger.fdebug('resultlist: %s' % (resultlist,))
                                        self.dbmylar.executemany("UPDATE rssdb SET Issue_Number=?, ComicName=? WHERE rowid=?", (resultlist))
                                        self.sql_closemylar()
                                        # update the update_db so if it has to resume it doesn't from the beginning or wrong point ( last 5000th write ).
                                        send_it = {'mode': dmode['mode'],
                                                   'version': self.db_version,
                                                   'status': 'incomplete',
                                                   'total': mylar.MAINTENANCE_DB_TOTAL,
                                                   'current': mylar.MAINTENANCE_DB_COUNT,
                                                   'last_run': helpers.utctimestamp()}
                                        self.db_update_status(send_it)

                                    except Exception as e:
                                        print('error: %s' % e)
                                        return False
                                    else:
                                        logger.fdebug('reattaching')
                                        self.sql_attachmylar()
                                        resultlist = []

                        try:
                            if len(resultlist) > 0:
                                self.dbmylar.executemany("UPDATE rssdb SET Issue_Number=?, ComicName=? WHERE rowid=?", (resultlist))
                                self.sql_closemylar()
                        except Exception as e:
                            print('error: %s' % e)
                            return False
                        else:
                            try:
                                send_it = {'mode': dmode['mode'],
                                           'version': 1,
                                           'status': 'complete',
                                           'total': mylar.MAINTENANCE_DB_TOTAL,
                                           'current': mylar.MAINTENANCE_DB_COUNT,
                                           'last_run': helpers.utctimestamp()}
                            except Exception as e:
                                print('error_sendit: %s' % e)
                            else:
                                self.db_update_status(send_it)

                            if delete_rows:
                                # only do this on completion, or else the rowids will be different and it will mess up a rerun
                                try:
                                    self.sql_attachmylar()
                                    print('[MAINTENANCE-MODE][DB-CONVERSION][CLEANUP] Removing %s invalid RSS entries from table...' % len(delete_rows))
                                    self.dbmylar.executemany("DELETE FROM rssdb WHERE rowid=?", (delete_rows))
                                    self.sql_closemylar()
                                except Exception as e:
                                    print('error: %s' % e)
                                else:
                                    self.sql_attachmylar()
                                    print('[MAINTENANCE-MODE][DB-CONVERSION][CLEANUP] Cleaning up...')
                                    self.dbmylar.execute("VACUUM");
                            else:
                                print('[MAINTENANCE-MODE][DB-CONVERSION][CLEANUP] Cleaning up...')
                                self.sql_attachmylar()
                                self.dbmylar.execute("VACUUM");

                            self.sql_closemylar()

                            #toggle back the logging level to what it was originally.
                            self.toggle_logging(level=prev_log_level)
                            logger.info('[MAINTENANCE-MODE][DB-CONVERSION] Updating dB complete! (%s / %s)' % (mylar.MAINTENANCE_DB_COUNT, mylar.MAINTENANCE_DB_TOTAL))
                            mylar.MAINTENANCE_UPDATE[:] = [x for x in mylar.MAINTENANCE_UPDATE if not ('rss update' == x.get('mode'))]

        else:
            mylar.MAINTENANCE_DB_COUNT = 0
            logger.info('[MAINTENANCE-MODE] Update DB set to start - but nothing was provided as to what. Returning to non-maintenance mode')
        return True

    def progressBar(self, iterable, prefix = '', suffix = '', decimals = 1, length = 100, resume=0, fill = '█', printEnd = "\r"):
        """
        Call in a loop to create terminal progress bar
        @params:
            iteration   - Required  : current iteration (Int)
            total       - Required  : total iterations (Int)
            prefix      - Optional  : prefix string (Str)
            suffix      - Optional  : suffix string (Str)
            decimals    - Optional  : positive number of decimals in percent complete (Int)
            length      - Optional  : character length of bar (Int)
            fill        - Optional  : bar fill character (Str)
            printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
        """
        total = len(iterable)
        # Progress Bar Printing Function
        def printProgressBar (iteration):
            percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
            filledLength = int(length * iteration // total)
            bar = fill * filledLength + '-' * (length - filledLength)
            print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
        # Initial Call
        printProgressBar(0)
        # Update Progress Bar
        for i, item in enumerate(iterable):
            yield item
            printProgressBar(resume + i + 1)
        # Print New Line on Complete
        print()
