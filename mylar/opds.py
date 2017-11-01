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

cmd_list = ['root', 'Publishers', 'AllTitles', 'StoryArcs', 'ReadList', 'Comic', 'Publisher']

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
        hp = HTMLParser.HTMLParser()
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
            totaltitles = 0
            for comic in comics:
                if comic['ComicPublisher'] == publisher['ComicPublisher'] and comic['haveissues'] > 0:
                    totaltitles += 1
            if totaltitles > 0:
                entries.append(
                    {
                        'title': escape('%s (%s)' % (publisher['ComicPublisher'], totaltitles)),
                        'id': escape('publisher:%s' % publisher['ComicPublisher']),
                        'updated': mylar.helpers.now(),
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
        hp = HTMLParser.HTMLParser()
        index = 0
        if 'index' in kwargs:
            index = int(kwargs['index'])
        myDB = db.DBConnection()
        if 'pubid' not in kwargs:
            self.data = _error_with_message('No Publisher Provided')

        feed = {}
        feed['title'] = 'Mylar OPDS - Publishers'
        feed['id'] = 'Publishers'
        feed['updated'] = mylar.helpers.now()
        links = []
        entries=[]
        links.append(getLink(href='/opds',type='application/atom+xml; profile=opds-catalog; kind=navigation', rel='start', title='Home'))
        links.append(getLink(href='/opds?cmd=Publishers',type='application/atom+xml; profile=opds-catalog; kind=navigation',rel='self'))
        allcomics = mylar.helpers.havetotals()
        for comic in allcomics:
            if comic['ComicPublisher'] == kwargs['pubid'] and comic['haveissues'] > 0:
                entries.append(
                    {
                        'title': escape('%s (%s) (%s)' % (comic['ComicName'], comic['ComicYear'], comic['haveissues'])),
                        'id': escape('comic:%s (%s)' % (comic['ComicName'], comic['ComicYear'])),
                        'updated': mylar.helpers.now(),
                        'content': escape('%s (%s) (%s)' % (comic['ComicName'], comic['ComicYear'], comic['haveissues'])),
                        'href': '/opds?cmd=Comic&amp;comicid=%s' % quote_plus(comic['ComicID']),
                        'kind': 'navigation',
                        'rel': 'subsection',
                    }
                )
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
