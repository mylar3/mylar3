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
from lxml import etree
import os
import urllib2
import cache
import imghdr
from operator import itemgetter
from cherrypy.lib.static import serve_file, serve_download
import datetime
from mylar.webserve import serve_template

cmd_list = ['root', 'Publishers', 'AllTitles']

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
                cherrypy.response.headers['Content-Type'] = "application/atom+xml"
                return serve_template(templatename="opds.html", title=self.data['title'], opds=self.data)
        else:
            return self.data

    def _error_with_message(self, message):
        feed = etree.Element("feed")

        error = etree.SubElement(feed,'error')
        error.text = message
        cherrypy.response.headers['Content-Type'] = "text/xml"
        return etree.tostring(feed)

    def _root(self, **kwargs):
        myDB = db.DBConnection()
        feed = {}
        feed['title'] = 'Mylar OPDS'
        feed['id'] = 'OPDSRoot'
        feed['updated'] = mylar.helpers.now()
        links = []
        entries=[]
        links.append({
                'href': '/opds',
                'type': 'application/atom+xml;profile=opds-catalog;kind=navigation',
                'rel': 'start',
                'title': 'Home'
            })
        links.append({
            'href': '/opds',
            'type': 'application/atom+xml;profile=opds-catalog;kind=navigation',
            'rel': 'self',
        })
        links.append({
            'href': '/opds?cmd=search',
            'type': 'application/opensearchdescription+xml',
            'rel': 'search',
            'title': 'Search',
        })
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
                    'kind': 'navigation'
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
                    'kind': 'navigation'
                }
            )
        feed['links'] = links
        feed['entries'] = entries
        self.data = feed
        return