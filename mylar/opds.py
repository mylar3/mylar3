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
from mylar import db, mb, importer, search, PostProcessor, versioncheck, logger, readinglist
import simplejson as simplejson
import cherrypy
from xml.sax.saxutils import escape
import os
import urllib2
from urllib import urlencode, quote_plus
import cache
import imghdr
from operator import itemgetter
from cherrypy.lib.static import serve_file, serve_download
import datetime
from mylar.webserve import serve_template

cmd_list = ['root', 'Publishers', 'AllTitles', 'StoryArcs', 'ReadList', 'Comic', 'Publisher', 'Issue', 'StoryArc', 'Recent']

class OPDS(object):

    def __init__(self):
        self.cmd = None
        self.PAGE_SIZE=30
        self.img = None
        self.issue_id = None
        self.file = None
        self.filename = None
        self.kwargs = None
        self.data = None
        if mylar.CONFIG.HTTP_ROOT is None:
            self.opdsroot = '/opds'
        elif mylar.CONFIG.HTTP_ROOT.endswith('/'):
            self.opdsroot = mylar.CONFIG.HTTP_ROOT + 'opds'
        else:
            if mylar.CONFIG.HTTP_ROOT != '/':
                self.opdsroot = mylar.CONFIG.HTTP_ROOT + '/opds'
            else:
                self.opdsroot = mylar.CONFIG.HTTP_ROOT + 'opds'

    def checkParams(self, *args, **kwargs):


        if 'cmd' not in kwargs:
            self.cmd = 'root'

        if not mylar.CONFIG.OPDS_ENABLE:
               self.data = self._error_with_message('OPDS not enabled')
               return

        if not self.cmd:
            if kwargs['cmd'] not in cmd_list:
                self.data = self._error_with_message('Unknown command: %s' % kwargs['cmd'])
                return
            else:
                self.cmd = kwargs.pop('cmd')

        self.kwargs = kwargs
        self.data = 'OK'

    def fetchData(self):

        if self.data == 'OK':
            logger.fdebug('Recieved OPDS command: ' + self.cmd)
            methodToCall = getattr(self, "_" + self.cmd)
            result = methodToCall(**self.kwargs)
            if self.img:
                return serve_file(path=self.img, content_type='image/jpeg')
            if self.file and self.filename:
                if self.issue_id:
                    readinglist.Readinglist(IssueID=self.issue_id).markasRead()
                return serve_download(path=self.file, name=self.filename)
            if isinstance(self.data, basestring):
                return self.data
            else:
                cherrypy.response.headers['Content-Type'] = "text/xml"
                return serve_template(templatename="opds.html", title=self.data['title'], opds=self.data)
        else:
            return self.data

    def _error_with_message(self, message):
        error = '<feed><error>%s</error></feed>' % message
        cherrypy.response.headers['Content-Type'] = "text/xml"
        return error

    def _dic_from_query(self, query):
        myDB = db.DBConnection()
        rows = myDB.select(query)

        rows_as_dic = []

        for row in rows:
            row_as_dic = dict(zip(row.keys(), row))
            rows_as_dic.append(row_as_dic)

        return rows_as_dic


    def _root(self, **kwargs):
        myDB = db.DBConnection()
        feed = {}
        feed['title'] = 'Mylar OPDS'
        feed['id'] = 'OPDSRoot'
        feed['updated'] = mylar.helpers.now()
        links = []
        entries=[]
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        links.append(getLink(href='%s?cmd=search' % self.opdsroot, type='application/opensearchdescription+xml',rel='search',title='Search'))
        publishers = myDB.select("SELECT ComicPublisher from comics GROUP BY ComicPublisher")
        entries.append(
            {
                'title': 'Recent Additions',
                'id': 'Recent',
                'updated': mylar.helpers.now(),
                'content': 'Recently Added Issues',
                'href': '%s?cmd=Recent' % self.opdsroot,
                'kind': 'acquisition',
                'rel': 'subsection',
            }
        )
        if len(publishers) > 0:
            count = len(publishers)
            entries.append(
                {
                    'title': 'Publishers (%s)' % count,
                    'id': 'Publishers',
                    'updated': mylar.helpers.now(),
                    'content': 'List of Comic Publishers',
                    'href': '%s?cmd=Publishers' %self.opdsroot,
                    'kind': 'navigation',
                    'rel': 'subsection',
                }
            )
        comics = mylar.helpers.havetotals()
        count = 0
        for comic in comics:
            if comic['haveissues'] > 0:
                count += 1
        if count > -1:
            entries.append(
                {
                    'title': 'All Titles (%s)' % count,
                    'id': 'AllTitles',
                    'updated': mylar.helpers.now(),
                    'content': 'List of All Comics',
                    'href': '%s?cmd=AllTitles' % self.opdsroot,
                    'kind': 'navigation',
                    'rel': 'subsection',
            }
            )
        storyArcs = mylar.helpers.listStoryArcs()
        logger.debug(storyArcs)
        if len(storyArcs) > 0:
            entries.append(
                {
                    'title': 'Story Arcs (%s)' % len(storyArcs),
                    'id': 'StoryArcs',
                    'updated': mylar.helpers.now(),
                    'content': 'List of Story Arcs',
                    'href': '%s?cmd=StoryArcs' % self.opdsroot,
                    'kind': 'navigation',
                    'rel': 'subsection',

            }
            )
        readList = myDB.select("SELECT * from readlist")
        if len(readList) > 0:
            entries.append(
                {
                    'title': 'Read List (%s)' % len(readList),
                    'id': 'ReadList',
                    'updated': mylar.helpers.now(),
                    'content': 'Current Read List',
                    'href': '%s?cmd=ReadList' % self.opdsroot,
                    'kind': 'navigation',
                    'rel': 'subsection',
                }
            )

        feed['links'] = links
        feed['entries'] = entries
        self.data = feed
        return

    def _Publishers(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        feed = {}
        feed['title'] = 'Mylar OPDS - Publishers'
        feed['id'] = 'Publishers'
        feed['updated'] = mylar.helpers.now()
        links = []
        entries=[]
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='%s?cmd=Publishers' % self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        publishers = myDB.select("SELECT ComicPublisher from comics GROUP BY ComicPublisher")
        comics = mylar.helpers.havetotals()
        for publisher in publishers:
            lastupdated = '0000-00-00'
            totaltitles = 0
            for comic in comics:
                if comic['ComicPublisher'] == publisher['ComicPublisher'] and comic['haveissues'] > 0:
                    totaltitles += 1
                    if comic['DateAdded'] > lastupdated:
                        lastupdated = comic['DateAdded']
            if totaltitles > 0:
                entries.append(
                    {
                        'title': escape('%s (%s)' % (publisher['ComicPublisher'], totaltitles)),
                        'id': escape('publisher:%s' % publisher['ComicPublisher']),
                        'updated': lastupdated,
                        'content': escape('%s (%s)' % (publisher['ComicPublisher'], totaltitles)),
                        'href': '%s?cmd=Publisher&amp;pubid=%s' %  (self.opdsroot, quote_plus(publisher['ComicPublisher'])),
                        'kind': 'navigation',
                        'rel': 'subsection',
                    }
                )
        if len(entries) > (index + self.PAGE_SIZE):
            links.append(
                getLink(href='%s?cmd=AllTitles&amp;index=%s' % (self.opdsroot, index+self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= self.PAGE_SIZE:
            links.append(
                getLink(href='%s?cmd=AllTitles&amp;index=%s' % (self.opdsroot, index-self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries[index:(index+self.PAGE_SIZE)]
        self.data = feed
        return

    def _AllTitles(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        feed = {}
        feed['title'] = 'Mylar OPDS - All Titles'
        feed['id'] = 'AllTitles'
        feed['updated'] = mylar.helpers.now()
        links = []
        entries=[]
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='%s?cmd=AllTitles' % self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        comics = mylar.helpers.havetotals()
        for comic in comics:
            if comic['haveissues'] > 0:
                entries.append(
                    {
                        'title': escape('%s (%s) (%s)' % (comic['ComicName'], comic['ComicYear'], comic['haveissues'])),
                        'id': escape('comic:%s (%s)' % (comic['ComicName'], comic['ComicYear'])),
                        'updated': comic['DateAdded'],
                        'content': escape('%s (%s) (%s)' % (comic['ComicName'], comic['ComicYear'], comic['haveissues'])),
                        'href': '%s?cmd=Comic&amp;comicid=%s' % (self.opdsroot, quote_plus(comic['ComicID'])),
                        'kind': 'acquisition',
                        'rel': 'subsection',
                    }
                )
        if len(entries) > (index + self.PAGE_SIZE):
            links.append(
                getLink(href='%s?cmd=AllTitles&amp;index=%s' % (self.opdsroot, index+self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= self.PAGE_SIZE:
            links.append(
                getLink(href='%s?cmd=AllTitles&amp;index=%s' % (self.opdsroot, index-self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries[index:(index+self.PAGE_SIZE)]
        self.data = feed
        return


    def _Publisher(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        if 'pubid' not in kwargs:
            self.data =self._error_with_message('No Publisher Provided')
            return
        links = []
        entries=[]
        allcomics = mylar.helpers.havetotals()
        for comic in allcomics:
            if comic['ComicPublisher'] == kwargs['pubid'] and comic['haveissues'] > 0:
                entries.append(
                    {
                        'title': escape('%s (%s) (%s)' % (comic['ComicName'], comic['ComicYear'], comic['haveissues'])),
                        'id': escape('comic:%s (%s)' % (comic['ComicName'], comic['ComicYear'])),
                        'updated': comic['DateAdded'],
                        'content': escape('%s (%s) (%s)' % (comic['ComicName'], comic['ComicYear'], comic['haveissues'])),
                        'href': '%s?cmd=Comic&amp;comicid=%s' % (self.opdsroot, quote_plus(comic['ComicID'])),
                        'kind': 'acquisition',
                        'rel': 'subsection',
                    }
                )
        feed = {}
        pubname = '%s (%s)' % (escape(kwargs['pubid']),len(entries))
        feed['title'] = 'Mylar OPDS - %s' % (pubname)
        feed['id'] = 'publisher:%s' % escape(kwargs['pubid'])
        feed['updated'] = mylar.helpers.now()
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='%s?cmd=Publishers' % self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        if len(entries) > (index + self.PAGE_SIZE):
            links.append(
                getLink(href='%s?cmd=Publisher&amp;pubid=%s&amp;index=%s' % (self.opdsroot, quote_plus(kwargs['pubid']),index+self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= self.PAGE_SIZE:
            links.append(
                getLink(href='%s?cmd=Publisher&amp;pubid=%s&amp;index=%s' % (self.opdsroot, quote_plus(kwargs['pubid']),index-self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries[index:(index+self.PAGE_SIZE)]
        self.data = feed
        return


    def _Comic(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        if 'comicid' not in kwargs:
            self.data =self._error_with_message('No ComicID Provided')
            return
        links = []
        entries=[]
        comic = myDB.selectone('SELECT * from comics where ComicID=?', (kwargs['comicid'],)).fetchone()
        if not comic:
            self.data = self._error_with_message('Comic Not Found')
            return
        issues = self._dic_from_query('SELECT * from issues WHERE ComicID="' + kwargs['comicid'] + '"order by Int_IssueNumber DESC')
        if mylar.CONFIG.ANNUALS_ON:
            annuals = self._dic_from_query('SELECT * FROM annuals WHERE ComicID="' + kwargs['comicid'] + '"')
        else:
            annuals = []
        for annual in annuals:
            issues.append(annual)
        issues = [x for x in issues if x['Location']]
        if index <= len(issues):
            subset = issues[index:(index+self.PAGE_SIZE)]
            for issue in subset:
                if 'DateAdded' in issue and issue['DateAdded']:
                    updated = issue['DateAdded']
                else:
                    updated = issue['ReleaseDate']
                image = None
                thumbnail = None
                if 'DateAdded' in issue:
                    title = escape('%s - %s' % (issue['Issue_Number'], issue['IssueName']))
                    image = issue['ImageURL_ALT']
                    thumbnail = issue['ImageURL']
                else:
                    title = escape('Annual %s - %s' % (issue['Issue_Number'], issue['IssueName']))

                fileloc = os.path.join(comic['ComicLocation'],issue['Location'])
                if not os.path.isfile(fileloc):
                    logger.debug("Missing File: %s" % (fileloc))
                    continue
                metainfo = None
                if mylar.CONFIG.OPDS_METAINFO:
                    metainfo = mylar.helpers.IssueDetails(fileloc)
                if not metainfo:
                    metainfo = [{'writer': None,'summary': ''}]
                entries.append(
                    {
                        'title': title,
                        'id': escape('comic:%s - %s' % (issue['ComicName'], issue['Issue_Number'])),
                        'updated': updated,
                        'content': escape('%s' % (metainfo[0]['summary'])),
                        'href': '%s?cmd=Issue&amp;issueid=%s&amp;file=%s' % (self.opdsroot, quote_plus(issue['IssueID']),quote_plus(issue['Location'].encode('utf-8'))),
                        'kind': 'acquisition',
                        'rel': 'file',
                        'author': metainfo[0]['writer'],
                        'image': image,
                        'thumbnail': thumbnail,
                    }
                )

        feed = {}
        comicname = '%s' % (escape(comic['ComicName']))
        feed['title'] = 'Mylar OPDS - %s' % (comicname)
        feed['id'] = escape('comic:%s (%s)' % (comic['ComicName'], comic['ComicYear']))
        feed['updated'] = comic['DateAdded']
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='%s?cmd=Comic&amp;comicid=%s' % (self.opdsroot, quote_plus(kwargs['comicid'])),type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        if len(issues) > (index + self.PAGE_SIZE):
            links.append(
                getLink(href='%s?cmd=Comic&amp;comicid=%s&amp;index=%s' % (self.opdsroot, quote_plus(kwargs['comicid']),index+self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= self.PAGE_SIZE:
            links.append(
                getLink(href='%s?cmd=Comic&amp;comicid=%s&amp;index=%s' % (self.opdsroot, quote_plus(kwargs['comicid']),index-self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries
        self.data = feed
        return


    def _Recent(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        links = []
        entries=[]
        recents = self._dic_from_query('SELECT * from snatched WHERE Status = "Post-Processed" OR Status = "Downloaded" order by DateAdded DESC LIMIT 120')
        if index <= len(recents):
            number = 1
            subset = recents[index:(index+self.PAGE_SIZE)]
            for issue in subset:
                issuebook = myDB.fetch('SELECT * from issues WHERE IssueID = ?', (issue['IssueID'],)).fetchone()
                if not issuebook:
                    issuebook = myDB.fetch('SELECT * from annuals WHERE IssueID = ?', (issue['IssueID'],)).fetchone()
                comic = myDB.fetch('SELECT * from comics WHERE ComicID = ?', (issue['ComicID'],)).fetchone()
                updated = issue['DateAdded']
                image = None
                thumbnail = None
                if issuebook:
                    if 'DateAdded' in issuebook.keys():
                        if issuebook['DateAdded'] is None:
                            title = escape('%03d: %s #%s - %s (In stores %s)' % (index + number, issuebook['ComicName'], issuebook['Issue_Number'], issuebook['IssueName'], issuebook['ReleaseDate']))
                            image = issuebook['ImageURL_ALT']
                            thumbnail = issuebook['ImageURL']
                        else:
                            title = escape('%03d: %s #%s - %s (Added to Mylar %s, in stores %s)' % (index + number, issuebook['ComicName'], issuebook['Issue_Number'], issuebook['IssueName'], issuebook['DateAdded'], issuebook['ReleaseDate']))
                            image = issuebook['ImageURL_ALT']
                            thumbnail = issuebook['ImageURL']
                    else:
                        title = escape('%03d: %s Annual %s - %s (In stores %s)' % (index + number, issuebook['ComicName'], issuebook['Issue_Number'], issuebook['IssueName'], issuebook['ReleaseDate']))
                    # logger.info("%s - %s" % (comic['ComicLocation'], issuebook['Location']))
                    number +=1
                    if not issuebook['Location']:
                        continue
                    location = issuebook['Location'].encode('utf-8')
                    fileloc = os.path.join(comic['ComicLocation'],issuebook['Location'])
                    metainfo = None
                    if mylar.CONFIG.OPDS_METAINFO:
                        metainfo = mylar.helpers.IssueDetails(fileloc)
                    if not metainfo:
                        metainfo = [{'writer': None,'summary': ''}]
                    entries.append(
                        {
                            'title': title,
                            'id': escape('comic:%s - %s' % (issuebook['ComicName'], issuebook['Issue_Number'])),
                            'updated': updated,
                            'content': escape('%s' % (metainfo[0]['summary'])),
                            'href': '%s?cmd=Issue&amp;issueid=%s&amp;file=%s' % (self.opdsroot, quote_plus(issuebook['IssueID']),quote_plus(location)),
                            'kind': 'acquisition',
                            'rel': 'file',
                            'author': metainfo[0]['writer'],
                            'image': image,
                            'thumbnail': thumbnail,
                        }
                    )
        feed = {}
        feed['title'] = 'Mylar OPDS - New Arrivals'
        feed['id'] = escape('New Arrivals')
        feed['updated'] = mylar.helpers.now()
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='%s?cmd=Recent' % (self.opdsroot),type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        if len(recents) > (index + self.PAGE_SIZE):
            links.append(
                getLink(href='%s?cmd=Recent&amp;index=%s' % (self.opdsroot,index+self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= self.PAGE_SIZE:
            links.append(
                getLink(href='%s?cmd=Recent&amp;index=%s' % (self.opdsroot,index-self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries
        self.data = feed
        return



    def _Issue(self, **kwargs):
        if 'issueid' not in kwargs:
            self.data = self._error_with_message('No ComicID Provided')
            return
        myDB = db.DBConnection()
        issuetype = 0
        issue = myDB.selectone("SELECT * from storyarcs WHERE IssueID=? and Location IS NOT NULL",
                               (kwargs['issueid'],)).fetchone()
        if not issue:
            issue = myDB.selectone("SELECT * from issues WHERE IssueID=?", (kwargs['issueid'],)).fetchone()
            if not issue:
                issue = myDB.selectone("SELECT * from annuals WHERE IssueID=?", (kwargs['issueid'],)).fetchone()
                if not issue:
                    self.data = self._error_with_message('Issue Not Found')
                    return
            comic = myDB.selectone("SELECT * from comics WHERE ComicID=?", (issue['ComicID'],)).fetchone()
            if not comic:
                self.data = self._error_with_message('Comic Not Found in Watchlist')
                return
            self.issue_id = issue['IssueID']
            self.file = os.path.join(comic['ComicLocation'],issue['Location'])
            self.filename = issue['Location']
        else:
            self.issue_id = issue['IssueID']
            self.file = issue['Location']
            self.filename = os.path.split(issue['Location'])[1]
        return

    def _StoryArcs(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        links = []
        entries=[]
        arcs = []
        storyArcs = mylar.helpers.listStoryArcs()
        for arc in storyArcs:
            issuecount = 0
            arcname = ''
            updated = '0000-00-00'
            arclist = myDB.select("SELECT * from storyarcs WHERE StoryArcID=?", (arc,))
            for issue in arclist:
                if issue['Status'] == 'Downloaded':
                    issuecount += 1
                    arcname = issue['StoryArc']
                    if issue['IssueDate'] > updated:
                        updated = issue['IssueDate']
            if issuecount > 0:
                arcs.append({'StoryArcName': arcname, 'StoryArcID': arc, 'IssueCount': issuecount, 'updated': updated})
        newlist = sorted(arcs, key=itemgetter('StoryArcName'))
        subset = newlist[index:(index + self.PAGE_SIZE)]
        for arc in subset:
            entries.append(
                {
                    'title': '%s (%s)' % (arc['StoryArcName'],arc['IssueCount']),
                    'id': escape('storyarc:%s' % (arc['StoryArcID'])),
                    'updated': arc['updated'],
                    'content': '%s (%s)' % (arc['StoryArcName'],arc['IssueCount']),
                    'href': '%s?cmd=StoryArc&amp;arcid=%s' % (self.opdsroot, quote_plus(arc['StoryArcID'])),
                    'kind': 'acquisition',
                    'rel': 'subsection',
                }
            )
        feed = {}
        feed['title'] = 'Mylar OPDS - Story Arcs'
        feed['id'] = 'StoryArcs'
        feed['updated'] = mylar.helpers.now()
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='%s?cmd=StoryArcs' % self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        if len(arcs) > (index + self.PAGE_SIZE):
            links.append(
                getLink(href='%s?cmd=StoryArcs&amp;index=%s' % (self.opdsroot, index+self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= self.PAGE_SIZE:
            links.append(
                getLink(href='%s?cmd=StoryArcs&amp;index=%s' % (self.opdsroot, index-self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries
        self.data = feed
        return

    def _ReadList(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        links = []
        entries = []
        rlist = self._dic_from_query("SELECT * from readlist where status!='Read'")
        readlist = []
        for book in rlist:
            fileexists = False
            issue = {}
            issue['Title'] = '%s #%s' % (book['ComicName'], book['Issue_Number'])
            issue['IssueID'] = book['IssueID']
            comic = myDB.selectone("SELECT * from comics WHERE ComicID=?", (book['ComicID'],)).fetchone()
            bookentry = myDB.selectone("SELECT * from issues WHERE IssueID=?", (book['IssueID'],)).fetchone()
            if bookentry:
                if bookentry['Location']:
                    fileexists = True
                    issue['fileloc'] = os.path.join(comic['ComicLocation'], bookentry['Location'])
                    issue['filename'] = bookentry['Location'].encode('utf-8')
                    issue['image'] =  bookentry['ImageURL_ALT']
                    issue['thumbnail'] =  bookentry['ImageURL']
                if  bookentry['DateAdded']:
                    issue['updated'] =  bookentry['DateAdded']
                else:
                    issue['updated'] =  bookentry['IssueDate']
            else:
                annualentry = myDB.selectone("SELECT * from annuals WHERE IssueID=?", (book['IssueID'],)).fetchone()
                if annualentry:
                    if annualentry['Location']:
                        fileexists = True
                        issue['fileloc'] = os.path.join(comic['ComicLocation'],  annualentry['Location'])
                        issue['filename'] = annualentry['Location'].encode('utf-8')
                        issue['image'] = None
                        issue['thumbnail'] = None
                        issue['updated'] =  annualentry['IssueDate']
            if not os.path.isfile(issue['fileloc']):
                fileexists = False
            if fileexists:
                readlist.append(issue)
        if len(readlist) > 0:
            if index <= len(readlist):
                subset = readlist[index:(index + self.PAGE_SIZE)]
                for issue in subset:
                    metainfo = None
                    if mylar.CONFIG.OPDS_METAINFO:
                        metainfo = mylar.helpers.IssueDetails(issue['fileloc'])
                    if not metainfo:
                        metainfo = [{'writer': None,'summary': ''}]
                    entries.append(
                        {
                            'title': escape(issue['Title']),
                            'id': escape('comic:%s' % issue['IssueID']),
                            'updated': issue['updated'],
                            'content': escape('%s' % (metainfo[0]['summary'])),
                            'href': '%s?cmd=Issue&amp;issueid=%s&amp;file=%s' % (self.opdsroot, quote_plus(issue['IssueID']),quote_plus(issue['filename'])),
                            'kind': 'acquisition',
                            'rel': 'file',
                            'author': metainfo[0]['writer'],
                            'image': issue['image'],
                            'thumbnail': issue['thumbnail'],
                        }
                    )

            feed = {}
            feed['title'] = 'Mylar OPDS - ReadList'
            feed['id'] = escape('ReadList')
            feed['updated'] = mylar.helpers.now()
            links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
            links.append(getLink(href='%s?cmd=ReadList' % self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
            if len(readlist) > (index + self.PAGE_SIZE):
                links.append(
                    getLink(href='%s?cmd=ReadList&amp;index=%s' % (self.opdsroot, index+self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
            if index >= self.PAGE_SIZE:
                links.append(
                    getLink(href='%s?cmd=Read&amp;index=%s' % (self.opdsroot, index-self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

            feed['links'] = links
            feed['entries'] = entries
            self.data = feed
            return


    def _StoryArc(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        if 'arcid' not in kwargs:
            self.data =self._error_with_message('No ArcID Provided')
            return
        links = []
        entries=[]
        arclist = self._dic_from_query("SELECT * from storyarcs WHERE StoryArcID='" + kwargs['arcid'] + "' ORDER BY ReadingOrder")
        newarclist = []
        arcname = ''
        for book in arclist:
            arcname = book['StoryArc']
            fileexists = False
            issue = {}
            issue['ReadingOrder'] = book['ReadingOrder']
            issue['Title'] = '%s #%s' % (book['ComicName'],book['IssueNumber'])
            issue['IssueID'] = book['IssueID']
            issue['fileloc'] = ''
            if book['Location']:
                issue['fileloc'] = book['Location']
                fileexists = True
                issue['filename'] = os.path.split(book['Location'])[1].encode('utf-8')
                issue['image'] = None
                issue['thumbnail'] = None
                issue['updated'] = book['IssueDate']
            else:
                bookentry = myDB.selectone("SELECT * from issues WHERE IssueID=?", (book['IssueID'],)).fetchone()
                if bookentry:
                    if bookentry['Location']:
                        comic = myDB.selectone("SELECT * from comics WHERE ComicID=?", ( bookentry['ComicID'],)).fetchone()
                        fileexists = True
                        issue['fileloc'] = os.path.join(comic['ComicLocation'], bookentry['Location'])
                        issue['filename'] = bookentry['Location'].encode('utf-8')
                        issue['image'] =  bookentry['ImageURL_ALT']
                        issue['thumbnail'] =  bookentry['ImageURL']
                    if  bookentry['DateAdded']:
                        issue['updated'] =  bookentry['DateAdded']
                    else:
                        issue['updated'] =  bookentry['IssueDate']
                else:
                    annualentry = myDB.selectone("SELECT * from annuals WHERE IssueID=?", (book['IssueID'],)).fetchone()
                    if annualentry:
                        if annualentry['Location']:
                            comic = myDB.selectone("SELECT * from comics WHERE ComicID=?", ( annualentry['ComicID'],))
                            fileexists = True
                            issue['fileloc'] = os.path.join(comic['ComicLocation'],  annualentry['Location'])
                            issue['filename'] = annualentry['Location'].encode('utf-8')
                            issue['image'] = None
                            issue['thumbnail'] = None
                            issue['updated'] =  annualentry['IssueDate']
                        else:
                            if book['Location']:
                                fileexists = True
                                issue['fileloc'] = book['Location']
                                issue['filename'] = os.path.split(book['Location'])[1].encode('utf-8')
                                issue['image'] = None
                                issue['thumbnail'] = None
                                issue['updated'] = book['IssueDate']
            if not os.path.isfile(issue['fileloc']):
                fileexists = False
            if fileexists:
                newarclist.append(issue)
        if len(newarclist) > 0:
            if index <= len(newarclist):
                subset = newarclist[index:(index + self.PAGE_SIZE)]
                for issue in subset:
                    metainfo = None
                    if mylar.CONFIG.OPDS_METAINFO:
                        metainfo = mylar.helpers.IssueDetails(issue['fileloc'])
                    if not metainfo:
                        metainfo = [{'writer': None,'summary': ''}]
                    entries.append(
                        {
                            'title': escape('%s - %s' % (issue['ReadingOrder'], issue['Title'])),
                            'id': escape('comic:%s' % issue['IssueID']),
                            'updated': issue['updated'],
                            'content': escape('%s' % (metainfo[0]['summary'])),
                            'href': '%s?cmd=Issue&amp;issueid=%s&amp;file=%s' % (self.opdsroot, quote_plus(issue['IssueID']),quote_plus(issue['filename'])),
                            'kind': 'acquisition',
                            'rel': 'file',
                            'author': metainfo[0]['writer'],
                            'image': issue['image'],
                            'thumbnail': issue['thumbnail'],
                        }
                    )

        feed = {}
        feed['title'] = 'Mylar OPDS - %s' % escape(arcname)
        feed['id'] = escape('storyarc:%s' % kwargs['arcid'])
        feed['updated'] = mylar.helpers.now()
        links.append(getLink(href=self.opdsroot,type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='%s?cmd=StoryArc&amp;arcid=%s' % (self.opdsroot, quote_plus(kwargs['arcid'])),type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        if len(newarclist) > (index + self.PAGE_SIZE):
            links.append(
                getLink(href='%s?cmd=StoryArc&amp;arcid=%s&amp;index=%s' % (self.opdsroot, quote_plus(kwargs['arcid']),index+self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= self.PAGE_SIZE:
            links.append(
                getLink(href='%s?cmd=StoryArc&amp;arcid=%s&amp;index=%s' % (self.opdsroot, quote_plus(kwargs['arcid']),index-self.PAGE_SIZE), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries
        self.data = feed
        return



def getLink(href=None, type=None, rel=None, title=None):
    link = {}
    if href:
        link['href'] = href
    if type:
        link['type'] = type
    if rel:
        link['rel'] = rel
    if title:
        link['title'] = title
    return link
