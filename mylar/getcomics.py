# -*- coding: utf-8 -*-
# This file is part of Mylar.
#
# Mylar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mylar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

from StringIO import StringIO
import urllib
from threading import Thread
import os
import sys
import re
import gzip
import time
import datetime
import json
from bs4 import BeautifulSoup
import requests
import cfscrape
import zipfile
import logger
import mylar
from mylar import db

class GC(object):

    def __init__(self, query=None, issueid=None, comicid=None):

        self.valreturn = []

        self.url = 'https://getcomics.info'

        self.query = query

        self.comicid = comicid
 
        self.issueid = issueid

        self.local_filename = os.path.join(mylar.CONFIG.CACHE_DIR, "getcomics.html")

        self.headers = {'Accept-encoding': 'gzip', 'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1', 'Referer': 'https://getcomics.info/'}

    def search(self):

        with cfscrape.create_scraper() as s:
            cf_cookievalue, cf_user_agent = s.get_tokens(self.url, headers=self.headers)

            t = s.get(self.url+'/', params={'s': self.query}, verify=True, cookies=cf_cookievalue, headers=self.headers, stream=True)

            with open(self.local_filename, 'wb') as f:
                for chunk in t.iter_content(chunk_size=1024):
                   if chunk: # filter out keep-alive new chunks
                       f.write(chunk)
                       f.flush()

        return self.search_results()

    def loadsite(self, id, link):
        title = os.path.join(mylar.CONFIG.CACHE_DIR, 'getcomics-' + id)
        with cfscrape.create_scraper() as s:
            self.cf_cookievalue, cf_user_agent = s.get_tokens(link, headers=self.headers)

            t = s.get(link, verify=True, cookies=self.cf_cookievalue, headers=self.headers, stream=True)

            with open(title+'.html', 'wb') as f:
                for chunk in t.iter_content(chunk_size=1024):
                   if chunk: # filter out keep-alive new chunks
                       f.write(chunk)
                       f.flush()

    def search_results(self):
        results = {}
        resultlist = []
        soup = BeautifulSoup(open(self.local_filename), 'html.parser')

        resultline = soup.find("span", {"class": "cover-article-count"}).get_text(strip=True)
        logger.info('There are %s results' % re.sub('Articles', '', resultline).strip())

        for f in soup.findAll("article"):
            id = f['id']
            lk = f.find('a')
            link = lk['href']
            titlefind = f.find("h1", {"class": "post-title"})
            title = titlefind.get_text(strip=True)
            title = re.sub(u'\u2013', '-', title).strip()
            filename = title
            issues = None
            pack = False
            #see if it's a pack type
            issfind_st = title.find('#')
            issfind_en = title.find('-', issfind_st)
            if issfind_en != -1:
                if all([title[issfind_en+1] == ' ', title[issfind_en+2].isdigit()]):
                    iss_en = title.find(' ', issfind_en+2)
                    if iss_en != -1:
                        issues = title[issfind_st+1:iss_en]
                        pack = True
                if title[issfind_en+1].isdigit():
                    iss_en = title.find(' ', issfind_en+1)
                    if iss_en != -1:
                        issues = title[issfind_st+1:iss_en]
                        pack = True

            # if it's a pack - remove the issue-range and the possible issue years (cause it most likely will span) and pass thru as separate items
            if pack is True:
                title = re.sub(issues, '', title).strip()
                if title.endswith('#'):
                    title = title[:-1].strip()

            option_find = f.find("p", {"style": "text-align: center;"})
            i = 0
            while i <= 2:
                option_find = option_find.findNext(text=True)
                if 'Year' in option_find:
                    year = option_find.findNext(text=True)
                    year = re.sub('\|', '', year).strip()
                    if pack is True and '-' in year:
                        title = re.sub('\('+year+'\)', '', title).strip()
                else:
                    size = option_find.findNext(text=True)
                    if all([re.sub(':', '', size).strip() != 'Size', len(re.sub('[^0-9]', '', size).strip()) > 0]):
                        if 'MB' in size:
                            size = re.sub('MB', 'M', size).strip()
                        elif 'GB' in size:
                            size = re.sub('GB', 'G', size).strip()
                        if '//' in size:
                            nwsize = size.find('//')
                            size = re.sub('\[', '', size[:nwsize]).strip()
                    else:
                        size = '0 M'
                i+=1
            dateline = f.find('time')
            datefull = dateline['datetime']
            datestamp = time.mktime(time.strptime(datefull, "%Y-%m-%d"))
            resultlist.append({"title":    title,
                               "pubdate":  datetime.datetime.fromtimestamp(float(datestamp)).strftime('%a, %d %b %Y %H:%M:%S'),
                               "filename": filename,
                               "size":     re.sub(' ', '', size).strip(),
                               "pack":     pack,
                               "issues":   issues,
                               "link":     link,
                               "year":     year,
                               "id":       re.sub('post-', '', id).strip(),
                               "site":     'DDL'})

            logger.fdebug('%s [%s]' % (title, size))

        results['entries'] = resultlist

        return results

    def parse_downloadresults(self, id, mainlink):
        myDB = db.DBConnection()
        title = os.path.join(mylar.CONFIG.CACHE_DIR, 'getcomics-' + id)
        soup = BeautifulSoup(open(title+'.html'), 'html.parser')
        orig_find = soup.find("p", {"style": "text-align: center;"})
        i = 0
        option_find = orig_find
        while True: #i <= 10:
            prev_option = option_find
            option_find = option_find.findNext(text=True)
            if i == 0:
                series = option_find
            elif 'Year' in option_find:
                year = option_find.findNext(text=True)
                year = re.sub('\|', '', year).strip()
            else:
                if 'Size' in prev_option:
                    size = option_find #.findNext(text=True)
                    possible_more = orig_find.next_sibling
                    break
            i+=1

        logger.fdebug('Now downloading: %s [%s] / %s ... this can take a while (go get some take-out)...' % (series, year, size))

        link = None
        for f in soup.findAll("div", {"class": "aio-pulse"}):
            lk = f.find('a')
            if lk['title'] == 'Download Now':
                link = lk['href']
                site = lk['title']
                break #get the first link just to test

        if link is None:
            logger.warn('Unable to retrieve any valid immediate download links. They might not exist.')
            return

        links = []

        if possible_more.name == 'ul':
            bb = possible_more.findAll('li')
            for x in bb:
                volume = x.findNext(text=True)
                if u'\u2013' in volume:
                    volume = re.sub(u'\u2013', '-', volume)
                linkline = x.find('a')
                link = linkline['href']
                site = linkline.findNext(text=True)
                links.append({"volume": volume,
                              "site": site,
                              "link": link})
        else:
            check_extras = soup.findAll("h3")
            for sb in check_extras:
                header = sb.findNext(text=True)
                if header == 'TPBs':
                    nxt = sb.next_sibling
                    if nxt.name == 'ul':
                        bb = nxt.findAll('li')
                        for x in bb:
                            volume = x.findNext(text=True)
                            if u'\u2013' in volume:
                                volume = re.sub(u'\u2013', '-', volume)
                            linkline = x.find('a')
                            link = linkline['href']
                            site = linkline.findNext(text=True)
                            links.append({"volume": volume,
                                          "site": site,
                                          "link": link})

        if link is None:
            logger.warn('Unable to retrieve any valid immediate download links. They might not exist.')
            return {'success':  False}

        for x in links:
            logger.fdebug('[%s] %s - %s' % (x['site'], x['volume'], x['link']))

        ctrlval = {'id':   id}
        vals = {'series':  series,
                'year':    year,
                'size':    size,
                'issueid': self.issueid,
                'comicid': self.comicid,
                'link':    link,
                'status':  'Queued'}
        myDB.upsert('ddl_info', vals, ctrlval)

        mylar.DDL_QUEUE.put({'link':     link,
                             'mainlink': mainlink,
                             'series':   series,
                             'year':     year,
                             'size':     size,
                             'comicid':  self.comicid,
                             'issueid':  self.issueid,
                             'id':       id})

        return {'success': True}

    def downloadit(self, id, link, mainlink):
        if mylar.DDL_LOCK is True:
            logger.fdebug('[DDL] Another item is currently downloading via DDL. Only one item can be downloaded at a time using DDL. Patience.')
            return
        else:
            mylar.DDL_LOCK = True

        myDB = db.DBConnection()
        filename = None
        try:
            with cfscrape.create_scraper() as s:
                cf_cookievalue, cf_user_agent = s.get_tokens(mainlink, headers=self.headers)
                t = s.get(link, verify=True, cookies=cf_cookievalue, headers=self.headers, stream=True)

                filename = os.path.basename(urllib.unquote(t.url).decode('utf-8'))

                path = os.path.join(mylar.CONFIG.DDL_LOCATION, filename)

                #write the filename to the db for tracking purposes...
                myDB.upsert('ddl_info', {'filename': filename}, {'id': id})

                if t.headers.get('content-encoding') == 'gzip': #.get('Content-Encoding') == 'gzip':
                    buf = StringIO(t.content)
                    f = gzip.GzipFile(fileobj=buf)

                with open(path, 'wb') as f:
                    for chunk in t.iter_content(chunk_size=1024):
                        if chunk: # filter out keep-alive new chunks
                            f.write(chunk)
                            f.flush()

        except Exception as e:
            logger.error('[ERROR] %s' % e)
            mylar.DDL_LOCK = False
            return ({"success":  False,
                     "filename": filename,
                     "path":     None})

        else:
            mylar.DDL_LOCK = False
            if os.path.isfile(path):
                if path.endswith('.zip'):
                    new_path = os.path.join(mylar.CONFIG.DDL_LOCATION, re.sub('.zip', '', filename).strip())
                    logger.info('Zip file detected. Unzipping into new modified path location: %s' % new_path)
                    try:
                        zip_f = zipfile.ZipFile(path, 'r')
                        zip_f.extractall(new_path)
                        zip_f.close()
                    except Exception as e:
                        logger.warn('[ERROR: %s] Unable to extract zip file: %s' % (e, new_path))
                        return ({"success":  False,
                                 "filename": filename,
                                 "path":     None})
                    else:
                        try:
                            os.remove(path)
                        except Exception as e:
                            logger.warn('[ERROR: %s] Unable to remove zip file from %s after extraction.' % (e, path))
                        filename = None
                else:
                    new_path = path
                return ({"success":  True,
                         "filename": filename,
                         "path":     new_path})

    def issue_list(self, pack):
        #packlist = [x.strip() for x in pack.split(',)]
        packlist = pack.replace('+', ' ').replace(',', ' ').split()
        print packlist
        plist = []
        pack_issues = []
        for pl in packlist:
            if '-' in pl:
                plist.append(range(int(pl[:pl.find('-')]),int(pl[pl.find('-')+1:])+1))
            else:
                if 'TPBs' not in pl:
                    plist.append(int(pl))
                else:
                    plist.append('TPBs')

        for pi in plist:
            if type(pi) == list:
                for x in pi:
                    pack_issues.append(x)
            else:
                pack_issues.append(pi)

        pack_issues.sort()
        print "pack_issues: %s" % pack_issues

#if __name__ == '__main__':
#    ab = GC(sys.argv[1]) #'justice league aquaman') #sys.argv[0])
#    #c = ab.search()
#    b = ab.loadsite('test', sys.argv[2])
#    c = ab.parse_downloadresults('test', '60MB')
#    #c = ab.issue_list(sys.argv[2])
