#!/usr/bin/env python
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

import lib.requests as requests
from bs4 import BeautifulSoup, UnicodeDammit
import urlparse
import re
import time
import sys
import datetime
from datetime import timedelta


import mylar
from mylar import logger, helpers

class wwt(object):

    def __init__(self, name, issue):
        self.url = 'https://worldwidetorrents.me/'
        self.query = name + ' ' + str(int(issue)) #'Batman White Knight'
        logger.info('query set to : %s' % self.query)
        pass

    def wwt_connect(self):
        resultlist = None
        params = {'c50': 1,
                  'search': self.query,
                  'cat': 132,
                  'incldead': 0,
                  'lang': 0}

        with requests.Session() as s:
            newurl = self.url + 'torrents-search.php'
            r = s.get(newurl, params=params, verify=True)

            if not r.status_code == 200:
                return
            logger.info('status code: %s' % r.status_code)
            soup = BeautifulSoup(r.content, "html5lib") 

            resultpages = soup.find("p", {"align": "center"})
            try:
                pagelist = resultpages.findAll("a")
            except:
                logger.info('No results found for %s' % self.query)
                return

            pages = []
            for p in pagelist:
                if p['href'] not in pages:
                    logger.fdebug('page: %s' % p['href'])
                    pages.append(p['href'])
            logger.fdebug('pages: %s' % (len(pages) + 1))

            resultlist = self.wwt_data(soup)
            if pages:
                for p in pages:
                    time.sleep(5)  #5s delay btwn requests
                    newurl = self.url + str(p)
                    r = s.get(newurl, params=params, verify=True)
                    if not r.status_code == 200:
                        continue
                    soup = BeautifulSoup(r.content, "html5lib")
                    resultlist += self.wwt_data(soup)

            logger.fdebug('%s results: %s' % (len(resultlist), resultlist))

        res = {}
        if len(resultlist) >= 1:
            res['entries'] = resultlist
        return res

    def wwt_data(self, data):

            resultw = data.find("table", {"class": "w3-table w3-striped w3-bordered w3-card-4"})
            resultp = resultw.findAll("tr")

            #final = []
            results = []
            for res in resultp:
                if res.findNext(text=True) == 'Torrents Name':
                    continue
                title = res.find('a')
                torrent = title['title']
                try:
                    for link in res.find_all('a', href=True):
                        if link['href'].startswith('download.php'):
                            linkurl = urlparse.parse_qs(urlparse.urlparse(link['href']).query)['id']
                            #results = {'torrent':  torrent,
                            #           'link':     link['href']}
                            break
                    for td in res.findAll('td'):
                        try:
                            seed = td.find("font", {"color": "green"})
                            leech = td.find("font", {"color": "#ff0000"})
                            value = td.findNext(text=True)
                            if any(['MB' in value, 'GB' in value]):
                                if 'MB' in value:
                                    szform = 'MB'
                                    sz = 'M'
                                else:
                                    szform = 'GB'
                                    sz = 'G'
                                size = helpers.human2bytes(str(re.sub(szform, '', value)).strip() + sz)
                            elif seed is not None:
                                seeders = value
                                #results['seeders'] = seeders
                            elif leech is not None:
                                leechers = value
                                #results['leechers'] = leechers
                            else:
                                age = value
                                #results['age'] = age
                        except Exception as e:
                            logger.warn('exception: %s' % e)

                    logger.info('age: %s' % age)
                    results.append({'title':    torrent,
                                    'link':     ''.join(linkurl),
                                    'pubdate':  self.string_to_delta(age),
                                    'size':     size,
                                    'site':     'WWT'})
                    logger.info('results: %s' % results)
                except Exception as e:
                    logger.warn('Error: %s' % e)
                    continue
                #else:
                #    final.append(results)

            return results

    def string_to_delta(self, relative):
        #using simplistic year (no leap months are 30 days long.
        #WARNING: 12 months != 1 year
        logger.info('trying to remap date from %s' % relative)
        unit_mapping = [('mic', 'microseconds', 1),
                        ('millis', 'microseconds', 1000),
                        ('sec', 'seconds', 1),
                        ('mins', 'seconds', 60),
                        ('hrs', 'seconds', 3600),
                        ('day', 'days', 1),
                        ('wk', 'days', 7),
                        ('mon', 'days', 30),
                        ('year', 'days', 365)]
        try:
            tokens = relative.lower().split(' ')
            past = False
            if tokens[-1] == 'ago':
                past = True
                tokens =  tokens[:-1]
            elif tokens[0] == 'in':
                tokens = tokens[1:]

            units = dict(days = 0, seconds = 0, microseconds = 0)
            #we should always get pairs, if not we let this die and throw an exception
            while len(tokens) > 0:
                value = tokens.pop(0)
                if value == 'and':    #just skip this token
                    continue
                else:
                    value = float(value)

                unit = tokens.pop(0)
                for match, time_unit, time_constant in unit_mapping:
                    if unit.startswith(match):
                        units[time_unit] += value * time_constant
            #print datetime.timedelta(**units), past
            val = datetime.datetime.now() - datetime.timedelta(**units)
            return datetime.datetime.strftime(val, '%a, %d %b %Y %H:%M:%S')
        except Exception as e:
            raise ValueError("Don't know how to parse %s: %s" % (relative, e))

