#-# -*- coding: utf-8 -*-
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

import mylar
from mylar import db, mb, importer, search, process, versioncheck, logger, webserve, helpers, encrypted, series_metadata
import json
import cherrypy
import random
import os
import re
import shutil
import urllib.request, urllib.error, urllib.parse
from . import cache
import imghdr
from operator import itemgetter
from cherrypy.lib.static import serve_file, serve_download
import datetime

cmd_list = ['getIndex', 'getComic', 'getUpcoming', 'getWanted', 'getHistory',
            'getLogs', 'getAPI', 'clearLogs','findComic', 'addComic', 'delComic',
            'pauseComic', 'resumeComic', 'refreshComic', 'addIssue', 'recheckFiles',
            'queueIssue', 'unqueueIssue', 'forceSearch', 'forceProcess', 'changeStatus',
            'getVersion', 'checkGithub','shutdown', 'restart', 'update', 'changeBookType',
            'getComicInfo', 'getIssueInfo', 'getArt', 'downloadIssue',
            'refreshSeriesjson', 'seriesjsonListing', 'checkGlobalMessages',
            'listProviders', 'changeProvider', 'addProvider', 'delProvider',
            'downloadNZB', 'getReadList', 'getStoryArc', 'addStoryArc']

class Api(object):

    API_ERROR_CODE_DEFAULT = 460

    def __init__(self):
        self.apikey = None
        self.cmd = None
        self.id = None
        self.img = None
        self.file = None
        self.filename = None
        self.kwargs = None
        self.data = None
        self.callback = None
        self.apitype = None
        self.comicrn = False
        self.headers = "application/json"

    def _failureResponse(self, errorMessage, code = API_ERROR_CODE_DEFAULT):
        response = {
            'success': False,
            'error': {
                'code': code,
                'message': errorMessage
            }
        }
        cherrypy.response.headers['Content-Type'] = self.headers
        return json.dumps(response)

    def _eventStreamResponse(self, results):
        #data = 'retry: 200\ndata: ' + str( self.prog_output) + '\n\n'
        #response = {
        #    'success': True,
        #    'data': results
        #}
        #{'status': mylar.GLOBAL_MESSAGES['status'], 'comicid': mylar.GLOBAL_MESSAGES['comicid'], 'tables': mylar.GLOBAL_MESSAGES['tables'], 'message': mylar.GLOBAL_MESSAGES['message']}
        #logger.info('global_message: %s' % (results,))
        if results['status'] is not None:
            if results['event'] == 'addbyid':
                try:
                    if results['seriesyear']:
                        data = '\nevent: addbyid\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "comicid": "' + results['comicid']+ '",\ndata: "message": "' + results['message'] + '",\ndata: "tables": "' + results['tables'] + '",\ndata: "comicname": "' + results['comicname'] + '",\ndata: "seriesyear": "' + results['seriesyear'] + '"\ndata: }\n\n'
                    else:
                        data = '\nevent: addbyid\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "comicid": "' + results['comicid']+ '",\ndata: "message": "' + results['message'] + '",\ndata: "tables": "' + results['tables'] + '",\ndata: "comicname": "' + results['comicname'] + '",\ndata: "seriesyear": "' + results['seriesyear'] + '"\ndata: }\n\n'
                except Exception as e:
                    #logger.warn('error: %s' % e)
                    data = '\nevent: addbyid\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "comicid": "' + results['comicid']+ '",\ndata: "message": "' + results['message'] + '",\ndata: "tables": "' + results['tables'] + '"\ndata: }\n\n'
            elif results['event'] == 'scheduler_message':
                try:
                    data = '\nevent: scheduler_message\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "message": "' + results['message'] + '"\ndata: }\n\n'
                except Exception:
                    data = '\nevent: scheduler_message\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "message": "' + results['message'] + '"\ndata: }\n\n'
            elif results['event'] == 'shutdown':
                try:
                    data = '\nevent: shutdown\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "message": "' + results['message'] + '"\ndata: }\n\n'
                except Exception:
                    data = '\nevent: shutdown\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "message": "' + results['message'] + '"\ndata: }\n\n'
            else:
                try:
                    data = '\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "comicid": "' + results['comicid']+ '",\ndata: "message": "' + results['message'] + '",\ndata: "tables": "' + results['tables'] + '",\ndata: "comicname": "' + results['comicname'] + '",\ndata: "seriesyear": "' + results['seriesyear'] + '"\ndata: }\n\n'
                except Exception as e:
                    #logger.warn('data_error: %s' % e)
                    data = '\ndata: {\ndata: "status": "' + results['status'] + '",\ndata: "comicid": "' + results['comicid']+ '",\ndata: "message": "' + results['message'] + '",\ndata: "tables": "' + results['tables'] + '"\ndata: }\n\n'

            #data = 'retry: 5000\ndata: '+str(results['message'])+'\n\n' # + str(results['message']) + '\n\n'
        else:
            data = '\ndata: \n\n' #'data: END-OF-STREAM\n\n'
        cherrypy.response.headers['Content-Type'] = 'text/event-stream'
        cherrypy.response.headers['Cache-Control'] = 'no-cache'
        cherrypy.response.headers['Connection'] = 'keep-alive'
        return data

    def _successResponse(self, results):
        response = {
            'success': True,
            'data': results
        }
        cherrypy.response.headers['Content-Type'] = self.headers
        return json.dumps(response)

    def _resultsFromQuery(self, query):
        myDB = db.DBConnection()
        rows = myDB.select(query)

        results = []

        for row in rows:
            results.append(dict(list(zip(list(row.keys()), row))))

        return results

    def checkParams(self, *args, **kwargs):

        if 'cmd' not in kwargs:
            self.data = self._failureResponse('Missing parameter: cmd')
            return

        if 'apikey' not in kwargs and ('apikey' not in kwargs and kwargs['cmd'] != 'getAPI'):
            self.data = self._failureResponse('Missing API key')
            return
        elif kwargs['cmd'] == 'getAPI':
            self.apitype = 'normal'
        else:
            if not mylar.CONFIG.API_ENABLED:
                if kwargs['apikey'] != mylar.DOWNLOAD_APIKEY and kwargs['apikey'] != mylar.SSE_KEY:
                    self.data = self._failureResponse('API not enabled')
                    return

            if kwargs['apikey'] != mylar.CONFIG.API_KEY and all([kwargs['apikey'] != mylar.SSE_KEY, kwargs['apikey'] != mylar.DOWNLOAD_APIKEY, mylar.DOWNLOAD_APIKEY != None]):
                self.data = self._failureResponse('Incorrect API key')
                return
            else:
                if kwargs['apikey'] == mylar.CONFIG.API_KEY:
                    self.apitype = 'normal'
                elif kwargs['apikey'] == mylar.DOWNLOAD_APIKEY:
                    self.apitype = 'download'
                elif kwargs['apikey'] == mylar.SSE_KEY:
                    self.apitype = 'sse'
                self.apikey = kwargs.pop('apikey')

            if not([mylar.CONFIG.API_KEY, mylar.DOWNLOAD_APIKEY, mylar.SSE_KEY]):
                self.data = self._failureResponse('API key not generated')
                return

            if self.apitype:
                if self.apitype == 'normal' and len(mylar.CONFIG.API_KEY) != 32:
                    self.data = self._failureResponse('API key not generated correctly')
                    return
                if self.apitype == 'download' and len(mylar.DOWNLOAD_APIKEY) != 32:
                    self.data = self._failureResponse('Download API key not generated correctly')
                    return
                if self.apitype == 'sse' and len(mylar.SSE_KEY) != 32:
                    self.data = self._failureResponse('SSE-API key not generated correctly')
                    return

            else:
                self.data = self._failureResponse('API key not generated correctly')
                return

        if kwargs['cmd'] not in cmd_list or (kwargs['cmd'] == 'checkGlobalMessags' and all([kwargs['apikey'] != mylar.SSE_KEY, self.apiktype != 'sse'])):
            self.data = self._failureResponse('Unknown command: %s' % kwargs['cmd'])
            return
        else:
            self.cmd = kwargs.pop('cmd')

        self.kwargs = kwargs
        self.data = 'OK'

    def fetchData(self):

        if self.data == 'OK':
            if self.cmd != 'checkGlobalMessages':
                logger.fdebug('Received API command: ' + self.cmd)
            methodToCall = getattr(self, "_" + self.cmd)
            result = methodToCall(**self.kwargs)
            if 'callback' not in self.kwargs:
                if self.img:
                    return serve_file(path=self.img, content_type='image/jpeg')
                if self.file and self.filename:
                    return serve_download(path=self.file, name=self.filename)
                if isinstance(self.data, str):
                    return self.data
                else:
                    if self.comicrn is True:
                        return self.data
                    else:
                        cherrypy.response.headers['Content-Type'] = "application/json"
                        return json.dumps(self.data)
            else:
                self.callback = self.kwargs['callback']
                self.data = json.dumps(self.data)
                self.data = self.callback + '(' + self.data + ');'
                cherrypy.response.headers['Content-Type'] = "application/javascript"
                return self.data
        else:
            return self.data

    def _selectForComics(self):
        return 'SELECT \
            ComicID as id,\
            ComicName as name,\
            ComicImageURL as imageURL,\
            Status as status,\
            ComicPublisher as publisher,\
            ComicYear as year,\
            LatestIssue as latestIssue,\
            Total as totalIssues,\
            DetailURL as detailsURL\
        FROM comics'

    def _selectForIssues(self):
        return 'SELECT \
            IssueID as id,\
            IssueName as name,\
            ImageURL as imageURL,\
            Issue_Number as number,\
            ReleaseDate as releaseDate,\
            IssueDate as issueDate,\
            Status as status,\
            ComicName as comicName\
        FROM issues'

    def _selectForAnnuals(self):
        return 'SELECT \
            IssueID as id,\
            IssueName as name,\
            Issue_Number as number,\
            ReleaseDate as releaseDate,\
            IssueDate as issueDate,\
            Status as status,\
            ComicName as comicName\
        FROM annuals'

    def _selectForReadList(self):
        return 'SELECT \
            IssueID as id,\
            Issue_Number as number,\
            IssueDate as issueDate,\
            Status as status,\
            ComicName as comicName\
        FROM readlist'

    def _getAPI(self, **kwargs):
        if 'username' not in kwargs:
           self.data = self._failureResponse('Missing parameter: username & password MUST be enabled.')
           return
        else:
            username = kwargs['username']

        if 'password' not in kwargs:
           self.data = self._failureResponse('Missing parameter: username & password MUST be enabled.')
           return
        else:
            password = kwargs['password']

        if any([mylar.CONFIG.HTTP_USERNAME is None, mylar.CONFIG.HTTP_PASSWORD is None]):
            self.data = self._failureResponse('Unable to use this command - username & password MUST be enabled.')
            return

        ht_user = mylar.CONFIG.HTTP_USERNAME
        edc = encrypted.Encryptor(mylar.CONFIG.HTTP_PASSWORD)
        ed_chk = edc.decrypt_it()
        if mylar.CONFIG.ENCRYPT_PASSWORDS is True:
            if username == ht_user and all([ed_chk['status'] is True, ed_chk['password'] == password]):
                self.data = self._successResponse(
                    {'apikey': mylar.CONFIG.API_KEY}
                )
            else:
                self.data = self._failureResponse('Incorrect username or password.')
        else:
            if username == ht_user and password == mylar.CONFIG.HTTP_PASSWORD:
                self.data = self._successResponse(
                    {'apikey': mylar.CONFIG.API_KEY}
                )
            else:
                self.data = self._failureResponse('Incorrect username or password.')

    def _getIndex(self, **kwargs):

        query = '{select} ORDER BY ComicSortName COLLATE NOCASE'.format(
            select = self._selectForComics()
        )

        self.data = self._successResponse(
            self._resultsFromQuery(query)
        )

        return

    def _getReadList(self, **kwargs):

        readListQuery = '{select} ORDER BY IssueDate ASC'.format(
            select = self._selectForReadList()
        )

        self.data = self._successResponse(
            self._resultsFromQuery(readListQuery)
        )

        return

    def _getComic(self, **kwargs):

        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        comicQuery = '{select} WHERE ComicID="{id}" ORDER BY ComicSortName COLLATE NOCASE'.format(
            select = self._selectForComics(),
            id = self.id
        )
        comic = self._resultsFromQuery(comicQuery)

        issuesQuery = '{select} WHERE ComicID="{id}" ORDER BY Int_IssueNumber DESC'.format(
            select = self._selectForIssues(),
            id = self.id
        )
        issues = self._resultsFromQuery(issuesQuery)

        if mylar.CONFIG.ANNUALS_ON:
            annualsQuery = '{select} WHERE ComicID="{id}"'.format(
                select = self._selectForAnnuals(),
                id = self.id
            )
            annuals = self._resultsFromQuery(annualsQuery)
        else:
            annuals = []

        self.data = self._successResponse({
            'comic': comic,
            'issues': issues,
            'annuals': annuals
        })

        return

    def _getHistory(self, **kwargs):
        self.data = self._successResponse(
            self._resultsFromQuery('SELECT * from snatched order by DateAdded DESC')
        )
        return

    def _getUpcoming(self, **kwargs):
        if 'include_downloaded_issues' in kwargs and kwargs['include_downloaded_issues'].upper() == 'Y':
            select_status_clause = "w.STATUS IN ('Wanted', 'Snatched', 'Downloaded')"
        else:
            select_status_clause = "w.STATUS = 'Wanted'"

        # Days in a new year that precede the first Sunday will look to the previous Sunday for week and year.
        today = datetime.date.today()
        if today.strftime('%U') == '00':
            weekday = 0 if today.isoweekday() == 7 else today.isoweekday()
            sunday = today - datetime.timedelta(days=weekday)
            week = sunday.strftime('%U')
            year = sunday.strftime('%Y')
        else:
            week = today.strftime('%U')
            year = today.strftime('%Y')

        self.data = self._resultsFromQuery(
            "SELECT w.COMIC AS ComicName, w.ISSUE AS IssueNumber, w.ComicID, w.IssueID, w.SHIPDATE AS IssueDate, w.STATUS AS Status, c.ComicName AS DisplayComicName \
            FROM weekly w JOIN comics c ON w.ComicID = c.ComicID WHERE w.COMIC IS NOT NULL AND w.ISSUE IS NOT NULL AND \
            SUBSTR('0' || w.weeknumber, -2) = '" + week + "' AND w.year = '" + year + "' AND " + select_status_clause + " ORDER BY c.ComicSortName")
        return

    def _getWanted(self, **kwargs):
        self.data = self._resultsFromQuery("SELECT * from issues WHERE Status='Wanted'")
        return

    def _getLogs(self, **kwargs):
        self.data = mylar.LOG_LIST
        return

    def _clearLogs(self, **kwargs):
        mylar.LOG_LIST = []
        self.data = 'Cleared log'
        return

    def _delComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']
            if self.id.startswith('4050-'):
                self.id = re.sub('4050-', '', self.id).strip()

        directory_del = False
        if 'directory' in kwargs:
            directory_del = kwargs['directory']
            if all([directory_del != 'true', directory_del != 'false']):
               self.data = self._failureResponse('directory value incorrect (valid: true / false)')
               return

            if any([directory_del == 'False', directory_del == 'false']):
               directory_del = False
            elif any([directory_del == 'True', directory_del == 'true']):
               directory_del = True
            else:
               directory_del = False  #safeguard anything else here.

        try:
            myDB = db.DBConnection()
            delchk = myDB.selectone('SELECT ComicName, ComicYear, ComicLocation FROM comics where ComicID="' + self.id + '"').fetchone()
            if not delchk:
                logger.error('ComicID %s not found in watchlist.' %  self.id)
                self.data = self._failureResponse('ComicID %s not found in watchlist.' % self.id)
                return
            logger.fdebug('Deletion request received for %s (%s) [%s]' % (delchk['ComicName'], delchk['ComicYear'], self.id))
            myDB.action('DELETE from comics WHERE ComicID="' + self.id + '"')
            myDB.action('DELETE from issues WHERE ComicID="' + self.id + '"')
            myDB.action('DELETE from upcoming WHERE ComicID="' + self.id + '"')
            if directory_del is True:
                if os.path.exists(delchk['ComicLocation']):
                    shutil.rmtree(delchk['ComicLocation'])
                    logger.fdebug('[API-delComic] Comic Location (%s) successfully deleted' % delchk['ComicLocation'])
                else:
                    logger.fdebug('[API-delComic] Comic Location (%s) does not exist - cannot delete' % delchk['ComicLocation'])

        except Exception as e:
            logger.error('Unable to delete ComicID: %s. Error returned: %s' % (self.id, e))
            self.data = self._failureResponse('Unable to delete ComicID: %s' % self.id)
        else:
            logger.fdebug('[API-delComic] Successfully deleted %s (%s) [%s]' % (delchk['ComicName'], delchk['ComicYear'], self.id))
            self.data = self._successResponse('Successfully deleted %s (%s) [%s]' % (delchk['ComicName'], delchk['ComicYear'], self.id))

    def _pauseComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        myDB = db.DBConnection()
        controlValueDict = {'ComicID': self.id}
        newValueDict = {'Status': 'Paused'}
        myDB.upsert("comics", newValueDict, controlValueDict)

    def _resumeComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        myDB = db.DBConnection()
        controlValueDict = {'ComicID': self.id}
        newValueDict = {'Status': 'Active'}
        myDB.upsert("comics", newValueDict, controlValueDict)

    def _refreshComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']
            id_list = []
            if ',' in self.id:
                id_list = self.id.split(',')

            else:
                id_list.append(self.id)

        watch = []
        already_added = []
        notfound = []
        myDB = db.DBConnection()
        for comicid in id_list:
            if comicid.startswith('4050-'):
                comicid = re.sub('4050-', '', comicid).strip()

            chkdb = myDB.selectone('SELECT ComicName, ComicYear FROM comics WHERE ComicID="' + comicid + '"').fetchone()
            if not chkdb:
                notfound.append({'comicid': comicid})
            else:
                if comicid not in mylar.REFRESH_QUEUE.queue: #if not any(ext['comicid'] == comicid for ext in mylar.REFRESH_LIST):
                    watch.append({"comicid": comicid, "comicname": chkdb['ComicName']})
                else:
                    already_added.append({'comicid': comicid, 'comicname': chkdb['ComicName']})

        if len(notfound) > 0:
            logger.info('Unable to locate the following requested ID\'s for Refreshing: %s' % (notfound,))
            self.data = self._successResponse('Unable to locate the following ID\'s for Refreshing (%s)' % (notfound,))
        if len(already_added) == 1:
            self.data = self._successResponse('[%s] %s has already been queued for refresh in a queue of %s items.' % (already_added[0]['comicid'], already_added[0]['comicname'], mylar.REFRESH_QUEUE.qsize()))
        elif len(already_added) > 1:
            self.data = self._successResponse('%s items (%s) have already been queued for refresh in a queue of % items.' % (len(already_added), already_added, mylar.REFRESH_QUEUE.qsize()))

        if len(watch) == 1:
            logger.info('[SHIZZLE-WHIZZLE] Now queueing to refresh %s %s' % (chkdb['ComicName'], chkdb['ComicYear']))
        elif len(watch) > 1:
            logger.info('[SHIZZLE-WHIZZLE] Now queueing to refresh %s items (%s)' % (len(watch), watch))
        else:
            return

        try:
            refred = importer.refresh_thread(watch)
        except Exception as e:
            logger.warn('[API-refreshComic] Unable to refresh ComicID %s. Error returned: %s' % (self.id, e))
            return
        else:
            if len(watch) == 1:
                ref_line = 'for ComicID %s' % (self.id)
            else:
                ref_line = 'for %s items (%s)' % (len(watch), watch)

            logger.warn('[API-refreshComic] Successfully background submitted refresh %s' % (ref_line))
            self.data = self._successResponse('Refresh successfully submitted %s.' % (self.id, ref_line))

        return

    def _changeBookType(self, **kwargs):
        #change booktype of series
        #id = comicid
        #booktype = specified booktype to force to (Print, Digital, TPB, GN, HC, One-Shot)
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing ComicID (field: id)')
            return
        self.id = kwargs['id']

        if 'booktype' not in kwargs:
            self.data = self._failureResponse('Missing BookType (field: booktype)')
            return
        booktype = kwargs['booktype']

        if booktype.lower() not in ['hc','gn','tpb','print','one-shot','digital']:
            self.data = self._failureResponse('Missing BookType format (allowed values: TPB, GN, HC, Print, One-Shot, Digital)')
            return
        else:
            booktype = booktype.lower()

        myDB = db.DBConnection()
        btresp = myDB.selectone('SELECT ComicName, ComicYear, Type, Corrected_Type FROM Comics WHERE ComicID="' + self.id +'"').fetchone()
        if not btresp:
            self.data = self._failureResponse('Unable to locate ComicID %s within watchlist' % self.id)
            return
        else:
            if btresp['Corrected_Type'] is not None:
                if btresp['Corrected_Type'].lower() == booktype:
                    self.data = self._successResponse('[%s] Forced Booktype is already set as %s.' % (self.id, booktype))
                    return
                if btresp['Type'].lower() == booktype and btresp['Corrected_Type'] == booktype:
                    self.data = self._successResponse('[%s] Booktype is already set as %s.' % (self.id, booktype))
                    return

            for bt in ['HC', 'GN', 'TPB', 'One-Shot', 'Digital', 'Print']:
                if bt.lower() == booktype:
                    booktype = bt
                    break

            try:
                newValue = {'Corrected_Type': booktype}
                newWrite = {'ComicID': self.id}
                myDB.upsert("comics", newValue, newWrite)
            except Exception as e:
                self.data = self._failureResponse('[%s] Unable to update Booktype for ComicID: %s. Error returned: %s' % (self.id, e))
                return
            else:
                self.data = self._successResponse('[%s] Updated Booktype to %s.' % (self.id, booktype))
                return

    def _changeStatus(self, **kwargs):
        #change status_from of every issue in series to specified status_to
        #if no comicid specified will mark ALL issues in EVERY series from status_from to specific status_to
        #required fields: status_to, status_from. Optional: id  (which is the ComicID if applicable)
        if all(['status_to' not in kwargs, 'status_from' not in kwargs]):
            self.data = self._failureResponse('Missing Status')
            return
        else:
            self.status_to = kwargs['status_to']
            self.status_from = kwargs['status_from']

        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing ComicID (field: id)')
            return
        else:
            self.id = kwargs['id']
            if self.id == 'All':
                bulk = True
            else:
                bulk = False
                self.id = kwargs['id']
                if type(self.id) is list:
                    bulk = True

        logger.info('[BULK:%s] [%s --> %s] ComicIDs to Change Status: %s' % (bulk, self.status_from, self.status_to, self.id))

        try:
            self.data = helpers.statusChange(self.status_from, self.status_to, self.id, bulk=bulk, api=True)
        except Exception as e:
            logger.error('[ERROR] %s' % e)
            self.data = e

        return

    def _recheckFiles(self, **kwargs):
        #allow either individual / bulk recheck Files based on ComiciD
        #multiples are allowed as long as in a list: {'id': ['100101', '101010', '20181', '47101']}
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing ComicID')
            return
        else:
            self.id = kwargs['id']

        if type(self.id) != list:
            bulk = False
        else:
            bulk = True

        logger.info('[BULK:%s] ComicIDs to ReCheck: %s' % (bulk, self.id))

        try:
            fc = webserve.WebInterface()
            self.data = fc.forceRescan(ComicID=self.id, bulk=bulk, api=True)
        except Exception as e:
            self.data = e

        return

    def _addComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        try:
            ac = webserve.WebInterface()
            ac.addbyid(self.id, calledby=True, nothread=False)
            #importer.addComictoDB(self.id)
        except Exception as e:
            self.data = e
        else:
            self.data = self._successResponse("Successfully queued up addding id: %s" % self.id)
        return

    def _queueIssue(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        myDB = db.DBConnection()
        controlValueDict = {'IssueID': self.id}
        newValueDict = {'Status': 'Wanted'}
        myDB.upsert("issues", newValueDict, controlValueDict)
        search.searchforissue(self.id)

    def _unqueueIssue(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        myDB = db.DBConnection()
        controlValueDict = {'IssueID': self.id}
        newValueDict = {'Status': 'Skipped'}
        myDB.upsert("issues", newValueDict, controlValueDict)

    def _seriesjsonListing(self, **kwargs):
        if 'missing' in kwargs:
            json_present = "WHERE seriesjsonPresent = 0 OR seriesjsonPresent is NULL"
        else:
            json_present = None
        myDB = db.DBConnection()
        msj_query = 'SELECT comicid, ComicLocation FROM comics {json_present}'.format(
            json_present=json_present
        )
        results = self._resultsFromQuery(msj_query)
        if len(results) > 0:
            self.data = self._successResponse(
                results
            )
        else:
            self.data = self._failureResponse('no data returned from seriesjson query')

    def _refreshSeriesjson(self, **kwargs):
        # comicid = [list, comicid, 'missing', 'all', 'refresh-missing']
        if 'comicid' not in kwargs:
            self.data = self._failureResponse('Missing comicid')
            return
        else:
            missing = False
            refresh_missing = False
            self.id = kwargs['comicid']
            if any([self.id == 'missing', self.id == 'all', self.id == 'refresh-missing']):
                bulk = True
                if any([self.id == 'missing', self.id == 'refresh-missing']):
                    if self.id == 'refresh-missing':
                        refresh_missing = True
                    missing = True
                    self._seriesjsonListing(missing=True)
                else:
                    self._seriesjsonListing()
                toqy = json.loads(self.data)
                if toqy['success'] is True:
                    toquery = []
                    for x in toqy['data']:
                        toquery.append(x['ComicID'])
                else:
                    self.data = self._failureResponse('No seriesjson data returned from query.')
                    return
            else:
                bulk = False
                if type(self.id) is list:
                    bulk = True
                toquery = self.id

        logger.info('[API][Refresh-Series.json][BULK:%s][Only_Missing:%s] ComicIDs to refresh series.json files: %s' % (bulk, missing, len(toquery)))

        try:
            sm = series_metadata.metadata_Series(comicidlist=toquery, bulk=bulk, api=True, refreshSeries=refresh_missing)
            sm.update_metadata_thread()
        except Exception as e:
            logger.error('[ERROR] %s' % e)
            self.data = e

        return


    def _forceSearch(self, **kwargs):
        search.searchforissue()

    def _issueProcess(self, **kwargs):
        if 'comicid' not in kwargs:
            self.data = self._failureResponse('Missing parameter: comicid')
            return
        else:
            self.comicid = kwargs['comicid']

        if 'issueid' not in kwargs:
            self.issueid = None
        else:
            self.issueid = kwargs['issueid']

        if 'folder' not in kwargs:
            self.data = self._failureResponse('Missing parameter: folder')
            return
        else:
            self.folder = kwargs['folder']


        fp = process.Process(self.comicid, self.folder, self.issueid)
        self.data = fp.post_process()
        return

    def _forceProcess(self, **kwargs):

        if 'nzb_name' not in kwargs:
            self.data = self._failureResponse('Missing parameter: nzb_name')
            return
        else:
            self.nzb_name = kwargs['nzb_name']

        if 'nzb_folder' not in kwargs:
            self.data = self._failureResponse('Missing parameter: nzb_folder')
            return
        else:
            self.nzb_folder = kwargs['nzb_folder']

        if 'failed' not in kwargs:
            failed = False
        else:
            failed = kwargs['failed']

        if 'issueid' not in kwargs:
            issueid = None
        else:
            issueid = kwargs['issueid']

        if 'comicid' not in kwargs:
            comicid = None
        else:
            comicid = kwargs['comicid']

        if 'ddl' not in kwargs:
            ddl = False
        else:
            ddl = True

        if 'oneoff' not in kwargs:
            oneoff = False
        else:
            if kwargs['oneoff'] == 'True':
                oneoff = True
            else:
                oneoff = False


        if 'apc_version' not in kwargs:
            logger.info('Received API Request for PostProcessing %s [%s]. Queueing...' % (self.nzb_name, self.nzb_folder))
            mylar.PP_QUEUE.put({'nzb_name':    self.nzb_name,
                                'nzb_folder':  self.nzb_folder,
                                'issueid':     issueid,
                                'failed':      failed,
                                'oneoff':      oneoff,
                                'comicid':     comicid,
                                'apicall':     True,
                                'ddl':         ddl})
            self.data = 'Successfully submitted request for post-processing for %s' % self.nzb_name
            #fp = process.Process(self.nzb_name, self.nzb_folder, issueid=issueid, failed=failed, comicid=comicid, apicall=True)
            #self.data = fp.post_process()
        else:
            logger.info('[API] Api Call from ComicRN detected - initiating script post-processing.')
            fp = webserve.WebInterface()
            self.data = fp.post_process(self.nzb_name, self.nzb_folder, failed=failed, apc_version=kwargs['apc_version'], comicrn_version=kwargs['comicrn_version'])
            self.comicrn = True
        return

    def _getVersion(self, **kwargs):
        self.data = self._successResponse({
            'git_path': mylar.CONFIG.GIT_PATH,
            'install_type': mylar.INSTALL_TYPE,
            'current_version': mylar.CURRENT_VERSION,
            'latest_version': mylar.LATEST_VERSION,
            'commits_behind': mylar.COMMITS_BEHIND,
        })

    def _checkGithub(self, **kwargs):
        versioncheck.checkGithub()
        self._getVersion()

    def _shutdown(self, **kwargs):
        mylar.SIGNAL = 'shutdown'

    def _restart(self, **kwargs):
        mylar.SIGNAL = 'restart'

    def _update(self, **kwargs):
        mylar.SIGNAL = 'update'

    def _getArtistArt(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        self.data = cache.getArtwork(ComicID=self.id)

    def _getIssueArt(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        self.data = cache.getArtwork(IssueID=self.id)

    def _getComicInfo(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        query = '{select} WHERE ComicID = {comic_id}'.format(
            select=self._selectForComics(),
            comic_id=self.id
        )
        results = self._resultsFromQuery(query)
        if len(results) == 1:
            self.data = self._successResponse(
                results
            )
        else:
            self.data = self._failureResponse('No comic found with that ID')

    def _getIssueInfo(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        query = '{select} WHERE IssueID = {issue_id}'.format(
            select=self._selectForIssues(),
            issue_id=self.id
        )
        results = self._resultsFromQuery(query)
        if len(results) == 1:
            self.data = self._successResponse(
                results
            )
        else:
            self.data = self._failureResponse('No issue found with that ID')

    def _getArt(self, **kwargs):
        if 'id' not in kwargs:
            self.data = self._failureResponse('Missing parameter: id')
            return
        else:
            self.id = kwargs['id']

        img = None
        image_path = os.path.join(mylar.CONFIG.CACHE_DIR, str(self.id) + '.jpg')

        # Checks if its a valid path and file
        if os.path.isfile(image_path):
            # check if its a valid img
            if imghdr.what(image_path):
                self.img = image_path
                return
        else:
            # If we cant find the image, lets check the db for a url.
            comic = self._resultsFromQuery('SELECT * from comics WHERE ComicID="' + self.id + '"')

            # Try every img url in the db
            try:
                img = urllib.request.urlopen(comic[0]['ComicImageURL']).read()
            except:
                try:
                    img = urllib.request.urlopen(comic[0]['ComicImageALTURL']).read()
                except:
                    pass

            if img:
                # verify the img stream
                if imghdr.what(None, img):
                    with open(image_path, 'wb') as f:
                        f.write(img)
                    self.img = image_path
                    return
                else:
                    self.data = self._failureResponse('Failed return a image')
            else:
                self.data = self._failureResponse('Failed to return a image')

    def _findComic(self, name, issue=None, type_=None, mode=None, serinfo=None):
        # set defaults
        if type_ is None:
            type_ = 'comic'
        if mode is None:
            mode = 'series'

        # Dont do shit if name is missing
        if len(name) == 0:
            self.data = self._failureResponse('Missing a Comic name')
            return

        if type_ == 'comic' and mode == 'series':
            searchresults = mb.findComic(name, mode, issue=issue)
        elif type_ == 'comic' and mode == 'pullseries':
            searchresults = mb.findComic(name, mode, issue=issue)
        elif type_ == 'comic' and mode == 'want':
            searchresults = mb.findComic(name, mode, issue=issue)
        elif type_ == 'story_arc':
            searchresults = mb.findComic(name, mode, issue=None, search_type='story_arc')

        searchresults = sorted(searchresults, key=itemgetter('comicyear', 'issues'), reverse=True)
        self.data = searchresults

    def _downloadIssue(self, id):
        if not id:
            self.data = self._failureResponse('You need to provide a issueid')
            return

        self.id = id
        # Fetch a list of dicts from issues table
        i = self._resultsFromQuery('SELECT * from issues WHERE issueID="' + self.id + '"')

        if not len(i):
            self.data = self._failureResponse('Couldnt find a issue with issueID %s' % self.id)
            return

        # issueid is unique so it should one dict in the list
        issue = i[0]

        issuelocation = issue.get('Location', None)

        # Check the issue is downloaded
        if issuelocation is not None:
            # Find the comic location
            comic = self._resultsFromQuery('SELECT * from comics WHERE comicID="' + issue['ComicID'] + '"')[0]
            comiclocation = comic.get('ComicLocation')
            f = os.path.join(comiclocation, issuelocation)
            if not os.path.isfile(f):
                try:
                    if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                        if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comiclocation))):
                            secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comiclocation))
                        else:
                            ff = mylar.filers.FileHandlers(ComicID=issue['ComicID'])
                            secondary_folders = ff.secondary_folders(comiclocation)

                        f = os.path.join(secondary_folders, issuelocation)
                        self.file = f
                        self.filename = issuelocation

                except Exception:
                    pass
            else:
                self.file = f
                self.filename = issuelocation
        else:
            self.data = self._failureResponse('You need to download that issue first')
            return

    def _downloadNZB(self, nzbname):
        if not nzbname:
            self.data = self._failureResponse('You need to provide a nzbname')
            return

        self.nzbname = nzbname
        f = os.path.join(mylar.CONFIG.CACHE_DIR, nzbname)
        if os.path.isfile(f):
            self.file = f
            self.filename = nzbname
        else:
            self.data = self._failureResponse('NZBname does not exist within the cache directory. Unable to retrieve.')
            return

    def _getStoryArc(self, **kwargs):
        if not 'id' in kwargs:
            if 'customOnly' in kwargs and kwargs['customOnly']:
                self.data = self._resultsFromQuery('SELECT StoryArcID, StoryArc, MAX(ReadingOrder) AS HighestOrder from storyarcs WHERE StoryArcID LIKE "C%" GROUP BY StoryArcID ORDER BY StoryArc')
            else:
                self.data = self._resultsFromQuery('SELECT StoryArcID, StoryArc, MAX(ReadingOrder) AS HighestOrder from storyarcs GROUP BY StoryArcID ORDER BY StoryArc')
        else:
            self.id = kwargs['id']
            self.data = self._resultsFromQuery('SELECT StoryArc, ReadingOrder, ComicID, ComicName, IssueNumber, IssueID, \
                                            IssueDate, IssueName, IssuePublisher from storyarcs WHERE StoryArcID="' + self.id + '" ORDER BY ReadingOrder')
        return

    def _addStoryArc(self, **kwargs):
        issuecount = 0
        if not 'id' in kwargs:
            self.id = 'C%04d' % random.randint(1, 9999)
            if not 'storyarcname' in kwargs:
                self.data = self._failureResponse('You need to provide either id or storyarcname')
                return
            else:
                storyarcname = kwargs.pop('storyarcname')
        else:
            self.id = kwargs.pop('id')
            arc = self._resultsFromQuery('SELECT * from storyarcs WHERE StoryArcID="' + self.id + '" ORDER by ReadingOrder')
            storyarcname = arc[0]['StoryArc']
            issuecount = len(arc)
        if not 'issues' in kwargs and not 'arclist' in kwargs:
            self.data = self._failureResponse('No issues specified')
            return
        else:
            arclist = ""
            if 'issues' in kwargs:
                issuelist = kwargs.pop('issues').split(",")
                index = 0
                for issue in issuelist:
                    arclist += "%s,%s" % (issue, issuecount + 1)
                    index += 1
                    issuecount += 1
                    if index < len(issuelist):
                        arclist += "|"
            if 'arclist' in kwargs:
                cvlist = kwargs.pop('arclist')
                issuelist = cvlist.split("|")
                index = 0
                for issue in issuelist:
                    arclist += "%s,%s" % (issue.split(",")[0],issuecount + 1)
                    index += 1
                    issuecount += 1
                    if index < len(issuelist):
                        arclist += "|"
        wi = webserve.WebInterface()
        logger.info("arclist: %s - arcid: %s - storyarcname: %s - storyarcissues: %s" % (arclist, self.id, storyarcname, issuecount))
        wi.addStoryArc_thread(arcid=self.id, storyarcname=storyarcname, storyarcissues=issuecount, arclist=arclist, **kwargs)
        return

    def _checkGlobalMessages(self, **kwargs):
        the_message = {'status': None, 'event': None, 'comicname': None, 'seriesyear': None, 'comicid': None, 'tables': None, 'message': None}
        if mylar.GLOBAL_MESSAGES is not None:
            try:
                event = mylar.GLOBAL_MESSAGES['event']
            except Exception:
                event = None

            if event is not None and event == 'shutdown':
                the_message = {'status': mylar.GLOBAL_MESSAGES['status'], 'event': event, 'message': mylar.GLOBAL_MESSAGES['message']}
            else:
                the_message = {'status': mylar.GLOBAL_MESSAGES['status'], 'event': event, 'comicid': mylar.GLOBAL_MESSAGES['comicid'], 'tables': mylar.GLOBAL_MESSAGES['tables'], 'message': mylar.GLOBAL_MESSAGES['message']}
                try:
                    the_fields = {'comicname': mylar.GLOBAL_MESSAGES['comicname'], 'seriesyear': mylar.GLOBAL_MESSAGES['seriesyear']}
                    the_message = dict(the_message, **the_fields)
                except Exception as e:
                    logger.warn('error: %s' % e)
            #logger.fdebug('the_message added: %s' % (the_message,))
            if mylar.GLOBAL_MESSAGES['status'] != 'mid-message-event':
                myDB = db.DBConnection()
                tmp_message = dict(the_message, **{'session_id': mylar.SESSION_ID})
                tmp_message.pop('tables')
                the_tmp_message = tmp_message.pop('message')
                the_real_message = re.sub(r'\r\n|\n|</br>', '', the_tmp_message)
                tmp_message = dict(tmp_message, **{'message': the_real_message})
                #logger.fdebug('the_message re-added: %s' % (tmp_message,))
                myDB.upsert( "notifs", tmp_message, {'date': helpers.now()} )
            mylar.GLOBAL_MESSAGES = None
        self.data = self._eventStreamResponse(the_message)

    def _listProviders(self, **kwargs):
        try:
            newznabs = []
            for nz in mylar.CONFIG.EXTRA_NEWZNABS:
                uid = nz[4]
                if '#' in nz[4]:
                    cats = re.sub('#', ',', nz[4][nz[4].find('#')+1:].strip()).strip()
                    uid = nz[4][:nz[4].find('#')].strip()
                else:
                    cats = None
                newznabs.append({'name': nz[0],
                                 'host': nz[1],
                                 'apikey': nz[3],
                                 'categories': cats,
                                 'uid': uid,
                                 'enabled': bool(int(nz[5])),
                                 'id': int(nz[6])})
            torznabs= []
            for nz in mylar.CONFIG.EXTRA_TORZNABS:
                cats = nz[4]
                if '#' in nz[4]:
                    cats = re.sub('#', ',', nz[4]).strip()
                torznabs.append({'name': nz[0],
                                 'host': nz[1],
                                 'apikey': nz[3],
                                 'categories': nz[4],
                                 'enabled': bool(int(nz[5])),
                                 'id': int(nz[6])})

            providers = {'newznabs': newznabs, 'torznabs': torznabs}
        except Exception as e:
            self.data = self._failureResponse(e)
        else:
            self.data = self._successResponse(providers)
        return

    def _addProvider(self, **kwargs):
        if 'providertype' not in kwargs:
            self.data = self._failureResponse('No provider type provided')
            logger.fdebug('[API][addProvider] %s' % (self.data,))
            return
        else:
            providertype = kwargs['providertype']
            if all([providertype != 'newznab', providertype != 'torznab']):
                self.data = self._failureResponse('providertype indicated %s is not a valid option. Options are `newznab` or `torznab`.' % providertype)
                logger.fdebug('[API][addProvider] %s' % (self.data,))
                return

        if any(['host' not in kwargs, 'name' not in kwargs, 'prov_apikey' not in kwargs, 'enabled' not in kwargs]):
            if providertype == 'newznab':
                self.data = self._failureResponse('Missing arguement. Required arguements are: `name`, `host`, `prov_apikey`, `enabled`. `categories` & `uid` is optional but `uid` is required for RSS.')
            elif providertype == 'torznab':
                self.data = self._failureResponse('Missing arguement. Required arguements are: `name`, `host`, `prov_apikey`, `categories`, `enabled.`')
                logger.fdebug('[API][addProvider] %s' % (self.data,))
            return

        if providertype == 'newznab':
            if 'name' in kwargs:
                newznab_name = kwargs['name']
                if any([newznab_name is None, newznab_name.strip() == '']):
                    self.data = self._failureResponse('name given for provider cannot be None or blank')
                    logger.fdebug('[API][addProvider] %s' % (self.data,))
                    return
                for x in mylar.CONFIG.EXTRA_NEWZNABS:
                    if x[0].lower() == newznab_name.lower():
                        self.data = self._failureResponse('%s already exists as a provider.' % newznab_name)
                        logger.fdebug('[API][addProvider] %s' % (self.data,))
                        return

            if 'host' in kwargs:
                newznab_host = kwargs['host']
                if not newznab_host.startswith('http'):
                    self.data = self._failureResponse('protocol is required for % host entry' % providertype)
                    logger.fdebug('[API][addProvider] %s' % (self.data,))
                    return
                if newznab_host.startswith('https'):
                    newznab_verify = '1'
                else:
                    newznab_verify = '0'
            if 'prov_apikey' in kwargs:
                newznab_apikey = kwargs['prov_apikey']

            newznab_enabled = '0' # set the default to disabled.
            if 'enabled' in kwargs:
                newznab_enabled = '1'
            if 'uid' in kwargs:
                newznab_uid = kwargs['uid']
            else:
                newznab_uid = None

            if 'categories' in kwargs:
                newznab_categories = kwargs['categories']
                if newznab_uid is not None:
                    newznab_uid += '%s%s'.strip() % ('#', re.sub(',', '#', newznab_categories))
                else:
                    newznab_uid = '%s%s'.strip() % ('#', re.sub(',', '#', newznab_categories))

            #prov_id assignment here
            prov_id = mylar.PROVIDER_START_ID + 1

            prov_line = (newznab_name, newznab_host, newznab_verify, newznab_apikey, newznab_uid, newznab_enabled, prov_id)
            if prov_line not in mylar.CONFIG.EXTRA_NEWZNABS:
                mylar.CONFIG.EXTRA_NEWZNABS.append(prov_line)
            else:
                self.data = self._failureResponse('exact details belong to another provider id already [%]. Maybe you should be using changeProvider' % prov_id)
                logger.fdebug('[API][addProvider] %s' % (self.data,))
                return

            p_name = newznab_name

        elif providertype == 'torznab':
            if 'name' in kwargs:
                torznab_name = kwargs['name']
                if any([torznab_name is None, torznab_name.strip() == '']):
                    self.data = self._failureResponse('name given for provider cannot be None or blank')
                    logger.fdebug('[API][addProvider] %s' % (self.data,))
                    return
                for x in mylar.CONFIG.EXTRA_TORZNABS:
                    if x[0].lower() == torznab_name.lower():
                        self.data = self._failureResponse('%s already exists as a provider.' % torznab_name)
                        logger.fdebug('[API][addProvider] %s' % (self.data,))
                        return

            if 'host' in kwargs:
                torznab_host = kwargs['host']
                if not torznab_host.startswith('http'):
                    self.data = self._failureResponse('protocol is required for % host entry' % providertype)
                    logger.fdebug('[API][addProvider] %s' % (self.data,))
                    return
                if torznab_host.startswith('https'):
                    torznab_verify = '1'
                else:
                    torznab_verify = '0'
            if 'prov_apikey' in kwargs:
                torznab_apikey = kwargs['prov_apikey']
            torznab_enabled = '0'
            if 'enabled' in kwargs:
                torznab_enabled = '1'
            if 'categories' in kwargs:
                torznab_categories = kwargs['categories']
                if ',' in torznab_categories:
                    tc = torznab_categories.split(',')
                    torznab_categories = '#'.join(tc).strip()

            #prov_id assignment here
            prov_id = mylar.PROVIDER_START_ID + 1

            prov_line = (torznab_name, torznab_host, torznab_verify, torznab_apikey, torznab_categories, torznab_enabled, prov_id)
            if prov_line not in mylar.CONFIG.EXTRA_TORZNABS:
                mylar.CONFIG.EXTRA_TORZNABS.append(prov_line)
            else:
                self.data = self._failureResponse('exact details belong to another provider id already [%]. Maybe you should be using changeProvider' % prov_id)
                logger.fdebug('[API][addProvider] %s' % (self.data,))
                return

            p_name = torznab_name

        try:
            mylar.CONFIG.writeconfig()
        except Exception as e:
            logger.error('[API][ADD_PROVIDER][%s] error returned : %s' % (providertype, e))
            self.data = self._failureResponse('Unable to add %s provider %s to the provider list. Check the logs.' % (providertype, p_name))
        else:
            self.data = self._successResponse('Successfully added %s provider %s to the provider list [prov_id: %s]' % (providertype, p_name, prov_id))
        return

    def _delProvider(self, **kwargs):
        providername = None
        prov_id = None
        if 'name' in kwargs:
            providername = kwargs['name'].strip()

        if 'prov_id' in kwargs:
            prov_id = int(kwargs['prov_id'])

        if any([providername is None, providername == '']) and prov_id is None:
            self.data = self._failureResponse('at least one of prov_id or name must be provided (cannot be blank)')
            logger.fdebug('[API][delProvider] %s' % (self.data,))
            return

        providertype = None
        if 'providertype' in kwargs:
            providertype = kwargs['providertype'].strip()
        else:
            self.data = self._failureResponse('No provider type provided')
            logger.fdebug('[API][addProvider] %s' % (self.data,))
            return

        if any([providertype is None, providertype == '']) or all([providertype != 'torznab', providertype != 'newznab']):
            if any([providertype is None, providertype == '']):
                self.data = self._failureResponse('`providertype` cannot be None or blank (either `torznab` or `newznab`)')
            elif all([providertype != 'torznab', providertype != 'newznab']):
                self.data = self._failureResponse('`providertype` provided not recognized. Must be either `torznab` or `newznab`)')
            logger.fdebug('[API][delProvider] %s' % (self.data,))
            return

        del_match = False
        newznabs = []
        if providertype == 'newznab':
            if prov_id is not None:
                prov_match = 'id'
            else:
                prov_match = 'name'
            for nz in mylar.CONFIG.EXTRA_NEWZNABS:
                if prov_match == 'id':
                    if prov_id == nz[6]:
                        del_match = True
                        providername = nz[0]
                        continue
                    else:
                        newznabs.append(nz)
                else:
                    if providername.lower() == nz[0]:
                        del_match = True
                        prov_id = nz[6]
                        continue
                    else:
                        newznabs.append(nz)

            if del_match is True:
                mylar.CONFIG.EXTRA_NEWZNABS = ((newznabs))
        else:
            torznabs= []
            if prov_id is not None:
                prov_match = 'id'
            else:
                prov_match = 'name'
            for nz in mylar.CONFIG.EXTRA_TORZNABS:
                if prov_match == 'id':
                    if prov_id == nz[6]:
                        del_match = True
                        providername = nz[0]
                        continue
                    else:
                        torznabs.append(nz)
                else:
                    if providername.lower() == nz[0]:
                        del_match = True
                        prov_id = nz[6]
                        continue
                    else:
                        torznabs.append(nz)

            if del_match is True:
                mylar.CONFIG.EXTRA_TORZNABS = ((torznabs))

        if del_match is False:
            self.data = self._failureResponse('Cannot remove %s as a provider, as it does not exist as a %s provider' % (providername, providertype))
            logger.fdebug('[API][delProvider] %s' % self.data)
            return
        else:
            try:
                mylar.CONFIG.writeconfig()
            except Exception as e:
                logger.error('[API][ADD_PROVIDER][%s] error returned : %s' % (providertype, e))
                self.data = self._failureResponse('Unable to save config of deleted %s provider %s. Check the logs.' % (providertype, providername))
            else:
                self.data = self._successResponse('Successfully removed %s provider %s [prov_id:%s]' % (providertype, providername, prov_id))
                logger.fdebug('[API][delProvider] %s' % self.data)
        return

    def _changeProvider(self, **kwargs):
        providername = None
        changename = None
        prov_id = None
        if 'altername' in kwargs:
            changename = kwargs.pop('altername').strip()
            if any([changename is None, changename == '']):
                self.data = self._failureResponse('altered name given for provider cannot be None or blank')
                logger.fdebug('[API][changeProvider] %s' % (self.data,))
                return

        if 'prov_id' in kwargs:
            prov_id = int(kwargs['prov_id'])

        if 'name' not in kwargs:
            if prov_id is None:
                self.data = self._failureResponse('provider id (`prov_id`) or provider name (`name`) not given. One must be supplied.')
                logger.fdebug('[API][changeProvider] %s' % (self.data,))
                return
        else:
            providername = kwargs['name'].strip()
            if all([providername is None, providername == '']):
                self.data = self._failureResponse('name given for provider cannot be None or blank')
                logger.fdebug('[API][changeProvider] %s' % (self.data,))
                return

        providertype = None
        if 'providertype' not in kwargs:
            self.data = self._failureResponse('No provider type provided')
            logger.fdebug('[API][changeProvider] %s' % (self.data,))
            return
        else:
            providertype = kwargs['providertype'].strip()
            if all([providertype != 'newznab', providertype != 'torznab']):
                self.data = self._failureResponse('providertype indicated %s is not a valid option. Options are `newznab` or `torznab`.' % providertype)
                logger.fdebug('[API][changerovider] %s' % (self.data,))
                return

        # find the values to change.
        if 'host' in kwargs:
            providerhost = kwargs['host']
            if providerhost.startswith('http'):
                if providerhost.startswith('https'):
                    prov_verify = '1'
                else:
                    prov_verify = '0'
            else:
                self.data = self._failureResponse('protocol is required for % host entry' % providertype)
                logger.fdebug('[API][changeProvider] %s' % (self.data,))
                return
        else:
            providerhost = None
            prov_verify = None

        if 'prov_apikey' in kwargs:
            prov_apikey = kwargs['prov_apikey']
        else:
            prov_apikey = None

        if 'enabled' in kwargs:
            tmp_enable = kwargs['enabled']
            prov_enabled = '1'
            if tmp_enable == 'true':
                prov_enabled = '1'
            elif any([tmp_enable == 'false', tmp_enable is None, tmp_enable == '']):
                prov_enabled = '0'
            else:
                self.data = self._failureResponse('`enabled` value must be `true`, `false` or not declared')
                logger.fdebug('[API][changeProvider] %s' % (self.data,))
                return

        elif 'disabled' in kwargs:
            tmp_enable = kwargs['disabled']
            prov_enabled = '0'
            if tmp_enable == 'true':
                prov_enabled = '0'
            elif any([tmp_enable == 'false', tmp_enable is None, tmp_enable == '']):
                prov_enabled = '1'
            else:
                self.data = self._failureResponse('`disabled` value must be `true`, `false` or not declared')
                logger.fdebug('[API][changeProvider] %s' % (self.data,))
                return
        else:
            prov_enabled = None

        torznab_categories = None
        if 'categories' in kwargs and providertype == 'torznab':
            torznab_categories = kwargs['categories']
            if ',' in torznab_categories:
                tc = torznab_categories.split(',')
                torznab_categories = '#'.join(tc).strip()

        if 'uid' in kwargs and providertype == 'newznab':
            newznab_uid = kwargs['uid']
        else:
            newznab_uid = None

        newznab_categories = None
        if 'categories' in kwargs and providertype == 'newznab':
            newznab_categories = kwargs['categories']
            if newznab_uid is not None:
                newznab_uid += '%s%s'.strip() % ('#', re.sub(',', '#', newznab_categories))
            else:
                newznab_uid = '%s%s'.strip() % ('#', re.sub(',', '#', newznab_categories))

        newznabs = []
        change_match = []
        if providertype == 'newznab':
            if prov_id is not None:
                prov_match = 'id'
            else:
                prov_match = 'name'
            for nz in mylar.CONFIG.EXTRA_NEWZNABS:
                if prov_match == 'id':
                    if nz[6] != prov_id:
                        newznabs.append(nz)
                        continue
                else:
                    if providername.lower() != nz[0].lower():
                        newznabs.append(nz)
                        continue
                if not prov_id:
                    # cannot alter prov_id via changeProvider method
                    prov_id = nz[6]
                if changename is not None:
                    if providername is None:
                        providername = changename
                        change_match.append('name')
                    elif providername.lower() != changename.lower():
                        providername = changename
                        change_match.append('name')
                else:
                    if providername is None:
                        providername = nz[0]
                    else:
                        change_match.append('name')
                p_host = nz[1]
                if providerhost is not None:
                    if p_host.lower() != providerhost.lower():
                        p_host = providerhost
                        change_match.append('host')
                p_verify = nz[2]
                if prov_verify is not None:
                    if p_verify != prov_verify:
                        p_verify = prov_verify
                        change_match.append('verify')
                p_apikey = nz[3]
                if prov_apikey is not None:
                    if p_apikey != prov_apikey:
                        p_apikey = prov_apikey
                        change_match.append('apikey')
                p_uid = nz[4]
                if newznab_uid is not None:
                    if p_uid != newznab_uid:
                        p_uid = newznab_uid
                        change_match.append('uid')
                p_enabled = nz[5]
                if p_enabled != prov_enabled and prov_enabled is not None:
                    p_enabled = prov_enabled
                    change_match.append('enabled')
                newznabs.append((providername, p_host, p_verify, p_apikey, p_uid, p_enabled, prov_id))

            if len(change_match) > 0:
                mylar.CONFIG.EXTRA_NEWZNABS = ((newznabs))
        else:
            torznabs= []
            if prov_id is not None:
                prov_match = 'id'
            else:
                prov_match = 'name'
            for nt in mylar.CONFIG.EXTRA_TORZNABS:
                if prov_match == 'id':
                    if nt[6] != prov_id:
                        torznabs.append(nt)
                        continue
                else:
                    if providername.lower() != nt[0].lower():
                        torznabs.append(nt)
                        continue
                if not prov_id:
                    # cannot alter prov_id via changeProvider method
                    prov_id = nt[6]
                if changename is not None:
                    if providername is None:
                        providername = changename
                        change_match.append('name')
                    elif providername.lower() != changename.lower():
                        providername = changename
                        change_match.append('name')
                else:
                    if providername is None:
                        providername = nt[0]
                    else:
                        change_match.append('name')
                p_host = nt[1]
                if providerhost is not None:
                    if p_host.lower() != providerhost.lower():
                        p_host = providerhost
                        change_match.append('host')
                p_verify = nt[2]
                if p_verify != prov_verify and prov_verify is not None:
                    p_verify = prov_verify
                    change_match.append('verify')
                p_apikey = nt[3]
                if prov_apikey is not None:
                    if p_apikey != prov_apikey:
                        p_apikey = prov_apikey
                        change_match.append('apikey')
                p_categories = nt[4]
                if torznab_categories is not None:
                    if p_categories != torznab_categories:
                        p_categories = torznab_categories
                        change_match.append('categories')
                p_enabled = nt[5]
                if p_enabled != prov_enabled and prov_enabled is not None:
                    p_enabled = prov_enabled
                    change_match.append('enabled')
                torznabs.append((providername, p_host, p_verify, p_apikey, p_categories, p_enabled, prov_id))

            if len(change_match) > 0:
                mylar.CONFIG.EXTRA_TORZNABS = ((torznabs))

        if len(change_match) == 0:
            self.data = self._failureResponse('Nothing to change for %s provider %s. It does not exist as a %s provider or nothing to change' % (providertype, providername, providertype))
            logger.fdebug('[API][changeProvider] %s' % self.data)
            return
        else:
            try:
                mylar.CONFIG.writeconfig()
            except Exception as e:
                logger.error('[API][ADD_PROVIDER][%s] error returned : %s' % (providertype, e))
            else:
                self.data = self._successResponse('Successfully changed %s for %s provider %s [prov_id:%s]' % (change_match, providertype, providername, prov_id))
                logger.fdebug('[API][changeProvider] %s' % self.data)
        return

class REST(object):

    def __init__(self):
        pass

    class verify_api(object):
        def __init__(self):
            pass

        def validate(self):
            logger.info('attempting to validate...')
            req = cherrypy.request.headers
            logger.info('thekey: %s' % req)
            logger.info('url: %s' % cherrypy.url())
            logger.info('mylar.apikey: %s [%s]' % (mylar.CONFIG.API_KEY, type(mylar.CONFIG.API_KEY)))
            logger.info('submitted.apikey: %s [%s]' % (req['Api-Key'], type(req['Api-Key'])))
            if 'Api-Key' not in req or req['Api-Key'] != str(mylar.CONFIG.API_KEY): #str(mylar.API_KEY) or mylar.API_KEY not in cherrypy.url():
                logger.info('wrong APIKEY')
                return 'api-key provided was either not present in auth header, or was incorrect.'
            else:
                return True

    class Watchlist(object):
        exposed = True
        def __init__(self):
            pass

        def GET(self):
            va = REST.verify_api()
            vchk = va.validate()
            if vchk is not True:
                return('api-key provided was either not present in auth header, or was incorrect.')
            #rows_as_dic = []

            #for row in rows:
            #    row_as_dic = dict(zip(row.keys(), row))
            #    rows_as_dic.append(row_as_dic)

            #return rows_as_dic
            some = helpers.havetotals()
            return json.dumps(some)

    class Comics(object):
        exposed = True
        def __init__(self):
            pass

        def _dic_from_query(self, query):
            myDB = db.DBConnection()
            rows = myDB.select(query)

            rows_as_dic = []

            for row in rows:
                row_as_dic = dict(list(zip(list(row.keys()), row)))
                rows_as_dic.append(row_as_dic)

            return rows_as_dic

        def GET(self):
            va = REST.verify_api()
            vchk = va.validate()
            if vchk is not True:
                return('api-key provided was either not present in auth header, or was incorrect.')
            #req = cherrypy.request.headers
            #logger.info('thekey: %s' % req)
            #if 'api-key' not in req or req['api-key'] != 'hello':
            #    logger.info('wrong APIKEY')
            #    return('api-key provided was either not present in auth header, or was incorrect.')

            self.comics = self._dic_from_query('SELECT * from comics order by ComicSortName COLLATE NOCASE')
            return('Here are all the comics we have: %s' % self.comics)

    @cherrypy.popargs('comic_id','issuemode','issue_id')
    class Comic(object):
        exposed = True

        def __init__(self):
            pass

        def _dic_from_query(self, query):
            myDB = db.DBConnection()
            rows = myDB.select(query)

            rows_as_dic = []

            for row in rows:
                row_as_dic = dict(list(zip(list(row.keys()), row)))
                rows_as_dic.append(row_as_dic)

            return rows_as_dic

        def GET(self, comic_id=None, issuemode=None, issue_id=None):
            va = REST.verify_api()
            vchk = va.validate()
            if vchk is not True:
                return('api-key provided was either not present in auth header, or was incorrect.')

            #req = cherrypy.request.headers
            #logger.info('thekey: %s' % req)
            #if 'api-key' not in req or req['api-key'] != 'hello':
            #    logger.info('wrong APIKEY')
            #    return('api-key provided was either not present in auth header, or was incorrect.')

            self.comics = self._dic_from_query('SELECT * from comics order by ComicSortName COLLATE NOCASE')

            if comic_id is None:
                return('No valid ComicID entered')
            else:
                if issuemode is None:
                    match = [c for c in self.comics if comic_id == c['ComicID']]
                    if match:
                        return json.dumps(match,ensure_ascii=False)
                    else:
                        return('No Comic with the ID %s :-(' % comic_id)
                elif issuemode == 'issues':
                    self.issues = self._dic_from_query('SELECT * from issues where comicid="' + comic_id + '"')
                    return json.dumps(self.issues, ensure_ascii=False)
                elif issuemode == 'issue' and issue_id is not None:
                    self.issues = self._dic_from_query('SELECT * from issues where comicid="' + comic_id + '" and issueid="' + issue_id + '"')
                    return json.dumps(self.issues, ensure_ascii=False)
                else:
                    return('Nothing to do.')

