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
            'getVersion', 'checkGithub','shutdown', 'restart', 'update',
            'getComicInfo', 'getIssueInfo', 'getArt', 'downloadIssue',
            'refreshSeriesjson', 'seriesjsonListing',
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

    def _failureResponse(self, errorMessage, code = API_ERROR_CODE_DEFAULT):
        response = {
            'success': False,
            'error': {
                'code': code,
                'message': errorMessage
            }
        }
        cherrypy.response.headers['Content-Type'] = "application/json"
        return json.dumps(response)

    def _successResponse(self, results):
        response = {
            'success': True,
            'data': results
        }
        cherrypy.response.headers['Content-Type'] = "application/json"
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
                if kwargs['apikey'] != mylar.DOWNLOAD_APIKEY:
                    self.data = self._failureResponse('API not enabled')
                    return

            if kwargs['apikey'] != mylar.CONFIG.API_KEY and all([kwargs['apikey'] != mylar.DOWNLOAD_APIKEY, mylar.DOWNLOAD_APIKEY != None]):
                self.data = self._failureResponse('Incorrect API key')
                return
            else:
                if kwargs['apikey'] == mylar.CONFIG.API_KEY:
                    self.apitype = 'normal'
                elif kwargs['apikey'] == mylar.DOWNLOAD_APIKEY:
                    self.apitype = 'download'
                logger.fdebug('Matched to key. Api set to : ' + self.apitype + ' mode.')
                self.apikey = kwargs.pop('apikey')

            if not([mylar.CONFIG.API_KEY, mylar.DOWNLOAD_APIKEY]):
                self.data = self._failureResponse('API key not generated')
                return

            if self.apitype:
                if self.apitype == 'normal' and len(mylar.CONFIG.API_KEY) != 32:
                    self.data = self._failureResponse('API key not generated correctly')
                    return
                if self.apitype == 'download' and len(mylar.DOWNLOAD_APIKEY) != 32:
                    self.data = self._failureResponse('Download API key not generated correctly')
                    return
            else:
                self.data = self._failureResponse('API key not generated correctly')
                return

        if kwargs['cmd'] not in cmd_list:
            self.data = self._failureResponse('Unknown command: %s' % kwargs['cmd'])
            return
        else:
            self.cmd = kwargs.pop('cmd')

        self.kwargs = kwargs
        self.data = 'OK'

    def fetchData(self):

        if self.data == 'OK':
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
           self.data = self._failureResponse('Missing parameter: username')
           return
        else:
            username = kwargs['username']

        if 'password' not in kwargs:
           self.data = self._failureResponse('Missing parameter: password')
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

        myDB = db.DBConnection()
        myDB.action('DELETE from comics WHERE ComicID="' + self.id + '"')
        myDB.action('DELETE from issues WHERE ComicID="' + self.id + '"')
        myDB.action('DELETE from upcoming WHERE ComicID="' + self.id + '"')

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

        try:
            importer.addComictoDB(self.id)
        except Exception as e:
            self.data = e

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
            self.data = self._failureResponse('Missing Status')
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
            self.data= fc.forceRescan(ComicID=self.id, bulk=bulk, api=True)
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
            importer.addComictoDB(self.id)
        except Exception as e:
            self.data = e

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
            sm = series_metadata.metadata_Series(comicidlist=toquery, bulk=bulk, api=True, refreshSeries=refresh_series)
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

    def _findComic(self, name, issue=None, type_=None, mode=None, explisit=None, serinfo=None):
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
            searchresults, explisit = mb.findComic(name, mode, issue=issue)
        elif type_ == 'comic' and mode == 'pullseries':
            pass
        elif type_ == 'comic' and mode == 'want':
            searchresults, explisit = mb.findComic(name, mode, issue)
        elif type_ == 'story_arc':
            searchresults, explisit = mb.findComic(name, mode, issue=None, explisit='explisit', search_type='story_arc')

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
                if mylar.CONFIG.MULTIPLE_DEST_DIRS is not None and mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None':
                    pathdir = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comiclocation))
                    f = os.path.join(pathdir, issuelocation)
                    self.file = f
                    self.filename = issuelocation
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

