#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from mylar import db, mb, importer, search, PostProcessor, versioncheck, logger
import lib.simplejson as simplejson
import cherrypy
import os
import urllib2
import cache
import imghdr
from operator import itemgetter
from cherrypy.lib.static import serve_file, serve_download

cmd_list = ['getIndex', 'getComic', 'getUpcoming', 'getWanted', 'getHistory', 'getLogs', 'clearLogs',
            'findComic', 'addComic', 'delComic', 'pauseComic', 'resumeComic', 'refreshComic',
            'addIssue', 'queueIssue', 'unqueueIssue', 'forceSearch', 'forceProcess', 'getVersion', 'checkGithub',
            'shutdown', 'restart', 'update', 'getComicInfo', 'getIssueInfo', 'getArt', 'downloadIssue', 'downloadNZB']


class Api(object):

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

    def checkParams(self, *args, **kwargs):

        if 'apikey' not in kwargs:
            self.data = 'Missing api key'
            return

        if 'cmd' not in kwargs:
            self.data = 'Missing parameter: cmd'
            return

        if not mylar.API_ENABLED:
            if kwargs['apikey'] != mylar.DOWNLOAD_APIKEY:
               self.data = 'API not enabled'
               return

        if kwargs['apikey'] != mylar.API_KEY and all([kwargs['apikey'] != mylar.DOWNLOAD_APIKEY, mylar.DOWNLOAD_APIKEY != None]):
            self.data = 'Incorrect API key'
            return
        else:
            if kwargs['apikey'] == mylar.API_KEY:
                self.apitype = 'normal'
            elif kwargs['apikey'] == mylar.DOWNLOAD_APIKEY:
                self.apitype = 'download'
            logger.fdebug('Matched to key. Api set to : ' + self.apitype + ' mode.')
            self.apikey = kwargs.pop('apikey')

        if not([mylar.API_KEY, mylar.DOWNLOAD_APIKEY]):
            self.data = 'API key not generated'
            return

        if self.apitype:
            if self.apitype == 'normal' and len(mylar.API_KEY) != 32:
                self.data = 'API key not generated correctly'
                return
            if self.apitype == 'download' and len(mylar.DOWNLOAD_APIKEY) != 32:
                self.data = 'Download API key not generated correctly'
                return
        else:
            self.data = 'API key not generated correctly'
            return

        if kwargs['cmd'] not in cmd_list:
            self.data = 'Unknown command: %s' % kwargs['cmd']
            return
        else:
            self.cmd = kwargs.pop('cmd')

        self.kwargs = kwargs
        self.data = 'OK'

    def fetchData(self):

        if self.data == 'OK':
            logger.fdebug('Recieved API command: ' + self.cmd)
            methodToCall = getattr(self, "_" + self.cmd)
            result = methodToCall(**self.kwargs)
            if 'callback' not in self.kwargs:
                if self.img:
                    return serve_file(path=self.img, content_type='image/jpeg')
                if self.file and self.filename:
                    return serve_download(path=self.file, name=self.filename)
                if isinstance(self.data, basestring):
                    return self.data
                else:
                    cherrypy.response.headers['Content-Type'] = "application/json"
                    return simplejson.dumps(self.data)
            else:
                self.callback = self.kwargs['callback']
                self.data = simplejson.dumps(self.data)
                self.data = self.callback + '(' + self.data + ');'
                cherrypy.response.headers['Content-Type'] = "application/javascript"
                return self.data
        else:
            return self.data

    def _dic_from_query(self, query):
        myDB = db.DBConnection()
        rows = myDB.select(query)

        rows_as_dic = []

        for row in rows:
            row_as_dic = dict(zip(row.keys(), row))
            rows_as_dic.append(row_as_dic)

        return rows_as_dic

    def _getIndex(self, **kwargs):
        self.data = self._dic_from_query('SELECT * from comics order by ComicSortName COLLATE NOCASE')
        return

    def _getComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        comic = self._dic_from_query('SELECT * from comics WHERE ComicID="' + self.id + '"')
        issues = self._dic_from_query('SELECT * from issues WHERE ComicID="' + self.id + '"order by Int_IssueNumber DESC')
        if mylar.ANNUALS_ON:
            annuals = self._dic_from_query('SELECT * FROM annuals WHERE ComicID="' + self.id + '"')
        else:
            annuals = None

        self.data = {'comic': comic, 'issues': issues, 'annuals': annuals}
        return

    def _getHistory(self, **kwargs):
        self.data = self._dic_from_query('SELECT * from snatched order by DateAdded DESC')
        return

    def _getUpcoming(self, **kwargs):
        self.data = self._dic_from_query("SELECT * from upcoming WHERE IssueID is NULL order by IssueDate DESC")
        return

    def _getWanted(self, **kwargs):
        self.data = self._dic_from_query("SELECT * from issues WHERE Status='Wanted'")
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
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        myDB = db.DBConnection()
        myDB.action('DELETE from comics WHERE ComicID="' + self.id + '"')
        myDB.action('DELETE from issues WHERE ComicID="' + self.id + '"')
        myDB.action('DELETE from upcoming WHERE ComicID="' + self.id + '"')

    def _pauseComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        myDB = db.DBConnection()
        controlValueDict = {'ComicID': self.id}
        newValueDict = {'Status': 'Paused'}
        myDB.upsert("comics", newValueDict, controlValueDict)

    def _resumeComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        myDB = db.DBConnection()
        controlValueDict = {'ComicID': self.id}
        newValueDict = {'Status': 'Active'}
        myDB.upsert("comics", newValueDict, controlValueDict)

    def _refreshComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        try:
            importer.addComictoDB(self.id)
        except Exception, e:
            self.data = e

        return

    def _addComic(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        try:
            importer.addComictoDB(self.id)
        except Exception, e:
            self.data = e

        return

    def _queueIssue(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
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
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        myDB = db.DBConnection()
        controlValueDict = {'IssueID': self.id}
        newValueDict = {'Status': 'Skipped'}
        myDB.upsert("issues", newValueDict, controlValueDict)

    def _forceSearch(self, **kwargs):
        search.searchforissue()

    def _forceProcess(self, **kwargs):
        if 'nzb_name' not in kwargs:
            self.data = 'Missing parameter: nzb_name'
            return
        else:
            self.nzb_name = kwargs['nzb_name']

        if 'nzb_folder' not in kwargs:
            self.data = 'Missing parameter: nzb_folder'
            return
        else:
            self.nzb_folder = kwargs['nzb_folder']

        forceProcess = PostProcessor.PostProcessor(self.nzb_name, self.nzb_folder)
        forceProcess.Process()

    def _getVersion(self, **kwargs):
        self.data = {
            'git_path': mylar.GIT_PATH,
            'install_type': mylar.INSTALL_TYPE,
            'current_version': mylar.CURRENT_VERSION,
            'latest_version': mylar.LATEST_VERSION,
            'commits_behind': mylar.COMMITS_BEHIND,
        }

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
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        self.data = cache.getArtwork(ComicID=self.id)

    def _getIssueArt(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        self.data = cache.getArtwork(IssueID=self.id)

    def _getComicInfo(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        self.data = cache.getInfo(ComicID=self.id)

    def _getIssueInfo(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        self.data = cache.getInfo(IssueID=self.id)

    def _getArt(self, **kwargs):
        if 'id' not in kwargs:
            self.data = 'Missing parameter: id'
            return
        else:
            self.id = kwargs['id']

        img = None
        image_path = os.path.join(mylar.CACHE_DIR, str(self.id) + '.jpg')

        # Checks if its a valid path and file
        if os.path.isfile(image_path):
            # check if its a valid img
            if imghdr.what(image_path):
                self.img = image_path
                return
        else:
            # If we cant find the image, lets check the db for a url.
            comic = self._dic_from_query('SELECT * from comics WHERE ComicID="' + self.id + '"')

            # Try every img url in the db
            try:
                img = urllib2.urlopen(comic[0]['ComicImageURL']).read()
            except:
                try:
                    img = urllib2.urlopen(comic[0]['ComicImageALTURL']).read()
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
                    self.data = 'Failed return a image'
            else:
                self.data = 'Failed to return a image'

    def _findComic(self, name, issue=None, type_=None, mode=None, explisit=None, serinfo=None):
        # set defaults
        if type_ is None:
            type_ = 'comic'
        if mode is None:
            mode = 'series'

        # Dont do shit if name is missing
        if len(name) == 0:
            self.data = 'Missing a Comic name'
            return

        if type_ == 'comic' and mode == 'series':
            searchresults, explisit = mb.findComic(name, mode, issue=issue)
        elif type_ == 'comic' and mode == 'pullseries':
            pass
        elif type_ == 'comic' and mode == 'want':
            searchresults, explisit = mb.findComic(name, mode, issue)
        elif type_ == 'story_arc':
            searchresults, explisit = mb.findComic(name, mode, issue=None, explisit='explisit', type='story_arc')

        searchresults = sorted(searchresults, key=itemgetter('comicyear', 'issues'), reverse=True)
        self.data = searchresults

    def _downloadIssue(self, id):
        if not id:
            self.data = 'You need to provide a issueid'
            return

        self.id = id
        # Fetch a list of dicts from issues table
        i = self._dic_from_query('SELECT * from issues WHERE issueID="' + self.id + '"')

        if not len(i):
            self.data = 'Couldnt find a issue with issueID %s' % self.id
            return

        # issueid is unique so it should one dict in the list
        issue = i[0]

        issuelocation = issue.get('Location', None)

        # Check the issue is downloaded
        if issuelocation is not None:
            # Find the comic location
            comic = self._dic_from_query('SELECT * from comics WHERE comicID="' + issue['ComicID'] + '"')[0]
            comiclocation = comic.get('ComicLocation')
            f = os.path.join(comiclocation, issuelocation)
            if not os.path.isfile(f):
                if mylar.MULTIPLE_DEST_DIRS is not None and mylar.MULTIPLE_DEST_DIRS != 'None':
                    pathdir = os.path.join(mylar.MULTIPLE_DEST_DIRS, os.path.basename(comiclocation))
                    f = os.path.join(pathdir, issuelocation)
                    self.file = f
                    self.filename = issuelocation
            else:
                self.file = f
                self.filename = issuelocation
        else:
            self.data = 'You need to download that issue first'
            return

    def _downloadNZB(self, nzbname):
        if not nzbname:
            self.data = 'You need to provide a nzbname'
            return

        self.nzbname = nzbname
        f = os.path.join(mylar.CACHE_DIR, nzbname)
        if os.path.isfile(f):
            self.file = f
            self.filename = nzbname
        else:
            self.data = 'NZBname does not exist within the cache directory. Unable to retrieve.'
            return

