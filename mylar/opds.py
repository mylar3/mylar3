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

cmd_list = ['root', 'Publishers', 'AllTitles', 'StoryArcs', 'ReadList', 'Comic', 'Publisher', 'Issue']

class OPDS(object):

    def __init__(self):
        self.cmd = None
        self.img = None
        self.file = None
        self.filename = None
        self.kwargs = None
        self.data = None

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
        links.append(getLink(href='/opds',type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='/opds',type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        links.append(getLink(href='/opds?cmd=search', type='application/opensearchdescription+xml',rel='search',title='Search'))
        publishers = myDB.select("SELECT ComicPublisher from comics GROUP BY ComicPublisher")
        if len(publishers) > 0:
            count = len(publishers)
            entries.append(
                {
                    'title': 'Publishers (%s)' % count,
                    'id': 'Publishers',
                    'updated': mylar.helpers.now(),
                    'content': 'List of Comic Publishers',
                    'href': '/opds?cmd=Publishers',
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
                    'href': '/opds?cmd=AllTitles',
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
                    'href': '/opds?cmd=StoryArcs',
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
                    'href': '/opds?cmd=ReadList',
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
        links.append(getLink(href='/opds',type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='/opds?cmd=Publishers',type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
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
                        'href': '/opds?cmd=Publisher&amp;pubid=%s' %  quote_plus(publisher['ComicPublisher']),
                        'kind': 'navigation',
                        'rel': 'subsection',
                    }
                )
        if len(entries) > (index + 30):
            links.append(
                getLink(href='/opds?cmd=Publishers&amp;index=%s' % (index+30), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= 30:
            links.append(
                getLink(href='/opds?cmd=Publishers&amp;index=%s' % (index-30), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries[index:(index+30)]
        self.data = feed
        return

    def _Publisher(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        if 'pubid' not in kwargs:
            self.data = _error_with_message('No Publisher Provided')
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
                        'href': '/opds?cmd=Comic&amp;comicid=%s' % quote_plus(comic['ComicID']),
                        'kind': 'navigation',
                        'rel': 'subsection',
                    }
                )
        feed = {}
        pubname = '%s (%s)' % (escape(kwargs['pubid']),len(entries))
        feed['title'] = 'Mylar OPDS - %s' % (pubname)
        feed['id'] = 'publisher:%s' % escape(kwargs['pubid'])
        feed['updated'] = mylar.helpers.now()
        links.append(getLink(href='/opds',type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='/opds?cmd=Publishers',type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        if len(entries) > (index + 30):
            links.append(
                getLink(href='/opds?cmd=Publisher&amp;pubid=%s&amp;index=%s' % (quote_plus(kwargs['pubid']),index+30), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= 30:
            links.append(
                getLink(href='/opds?cmd=Publisher&amp;pubid=%s&amp;index=%s' % (quote_plus(kwargs['pubid']),index-30), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries[index:(index+30)]
        self.data = feed
        return

    def _Comic(self, **kwargs):
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        if 'comicid' not in kwargs:
            self.data = _error_with_message('No ComicID Provided')
            return
        links = []
        entries=[]
        comic = myDB.selectone('SELECT * from comics where ComicID=?', (kwargs['comicid'],)).fetchone()
        if len(comic) == 0:
            self.data = _error_with_message('Comic Not Found')
            return
        issues = self._dic_from_query('SELECT * from issues WHERE ComicID="' + kwargs['comicid'] + '"order by Int_IssueNumber DESC')
        if mylar.CONFIG.ANNUALS_ON:
            annuals = self._dic_from_query('SELECT * FROM annuals WHERE ComicID="' + kwargs['comicid'] + '"')
        else:
            annuals = None
        for annual in annuals:
            issues.append(annual)
        issues = [x for x in issues if x['Location']]
        if index <= len(issues):
            subset = issues[index:(index+30)]
            for issue in subset:
                if issue['DateAdded']:
                    updated = issue['DateAdded']
                else:
                    updated = issue['ReleaseDate']
                fileloc = os.path.join(comic['ComicLocation'],issue['Location'])
                metainfo = mylar.helpers.IssueDetails(fileloc)
                if not metainfo:
                    metainfo = [{'writer': 'Unknown','summary': ''}]
                entries.append(
                    {
                        'title': escape('%s - %s' % (issue['Issue_Number'], issue['IssueName'])),
                        'id': escape('comic:%s - %s' % (issue['ComicName'], issue['Issue_Number'])),
                        'updated': updated,
                        'content': escape('%s' % (metainfo[0]['summary'])),
                        'href': '/opds?cmd=Issue&amp;issueid=%s&amp;file=%s' % (quote_plus(issue['IssueID']),quote_plus(issue['Location'])),
                        'kind': 'acquisition',
                        'rel': 'file',
                        'author': metainfo[0]['writer'],
                    }
                )

        feed = {}
        comicname = '%s' % (escape(comic['ComicName']))
        feed['title'] = 'Mylar OPDS - %s' % (comicname)
        feed['id'] = escape('comic:%s (%s)' % (comic['ComicName'], comic['ComicYear']))
        feed['updated'] = comic['DateAdded']
        links.append(getLink(href='/opds',type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='/opds?cmd=Comic&amp;comicid=%s' % quote_plus(kwargs['comicid']),type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        if len(issues) > (index + 30):
            links.append(
                getLink(href='/opds?cmd=Comic&amp;comicid=%s&amp;index=%s' % (quote_plus(kwargs['comicid']),index+30), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='next'))
        if index >= 30:
            links.append(
                getLink(href='/opds?cmd=Comic&amp;comicid=%s&amp;index=%s' % (quote_plus(kwargs['comicid']),index-30), type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='previous'))

        feed['links'] = links
        feed['entries'] = entries
        self.data = feed
        return

    def _Issue(self, **kwargs):
        if 'issueid' not in kwargs:
            self.data = _error_with_message('No ComicID Provided')
            return
        myDB = db.DBConnection()
        issue = myDB.selectone("SELECT * from issues WHERE IssueID=?", (kwargs['issueid'],)).fetchone()
        if len(issue) == 0:
            issue = myDB.selectone("SELECT * from annuals WHERE IssueID=?", (kwargs['issueid'],)).fetchone()
            if len(issue) == 0:
                self.data = _error_with_message('Issue Not Found')
                return
        comic = myDB.selectone("SELECT * from comics WHERE ComicID=?", (issue['ComicID'],)).fetchone()
        if len(comic) ==0:
            self.data = _error_with_message('Comic Not Found')
            return
        self.file = os.path.join(comic['ComicLocation'],issue['Location'])
        self.filename = issue['Location']
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
