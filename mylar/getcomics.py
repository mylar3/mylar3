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


import requests
import urllib.parse
import os
import sys
import traceback
import errno
import re
import time
import datetime
from bs4 import BeautifulSoup
import requests
import zipfile
import json
import mylar
from operator import itemgetter
from mylar import db, logger, helpers, search_filer

class GC(object):

    def cookie_receipt(self, main_url=None):
        #self.session_path = self.session_path if self.session_path is not None else os.path.join(mylar.CONFIG.SECURE_DIR, ".gc_cookies.dat")

        # if main_url is not None, it's being passed via the test on the config page.
        flare_test = False
        if main_url is None:
            if mylar.CONFIG.ENABLE_FLARESOLVERR:
                # (ie. http://192.168.2.2:8191/v1 )
                main_url = mylar.CONFIG.FLARESOLVERR_URL
            else:
                main_url = mylar.GC_URL
        else:
            flare_test = True

        test_success = False
        if not os.path.exists(self.session_path):

            if any([mylar.CONFIG.ENABLE_FLARESOLVERR, flare_test is True]):
                logger.fdebug('[GC_Cookie_Creator] GetComics Session cookie does not exist. Attempting to create.')
                #get the coookies here for use down-below
                get_cookies = self.session.post(
                              main_url,
                              json={'url': mylar.GC_URL, 'cmd': 'request.get'},
                              verify=False,
                              headers=self.flare_headers,
                              timeout=30,
                              )
                if get_cookies.status_code == 200:
                    try:
                        gc_json = get_cookies.json()
                        gc_cookie = gc_json['solution']['cookies']
                        with open(self.session_path, 'w') as f:
                            json.dump(gc_cookie, f)
                    except Exception as e:
                        logger.warn('[GC_Cookie_Saver] Unable to save cookie to file - will try to recreate later.')
                    else:
                        logger.fdebug('[GC_Cookie_Saver] Successfully saved cookie to file.')
                        for c in gc_cookie:
                           self.session.cookies.set(name=c['name'], value=c['value'])
                        test_success = True
            else:
                # if flaresolverr isn't used and the cookies file doesn't already exist
                #  - no need to store cookies since they're empty normally.
                #  - if GC starts to send it with the headers, then we can enable this
                pass
                #get_cookies = self.session.get(
                #              main_url,
                #              verify=True,
                #              headers=self.headers,
                #              timeout=30,
                #              )
                #if get_cookies.status_code == 200:
                #    try:
                #        gc_cookie = get_cookies.cookies.get_dict()
                #        with open(self.session_path, 'w') as f:
                #            json.dump(gc_cookie, f)
                #    except Exception as e:
                #        logger.warn('[GC_Cookie_Saver] Unable to save cookie to file - will try to recreate later. Error: %s' % e)
                #        if os.path.isfile(self.session_path):
                #            os.remove(self.session_path)
                #    else:
                #        if gc_cookie is not None:
                #            logger.fdebug('[GC_Cookie_Saver] Successfully saved cookie to file.')
                #            for c in gc_cookie:
                #               self.session.cookies.set(name=c['name'], value=c['value'])
                #        test_success = True

        else:
            logger.fdebug('[GC_Cookie_Loader] GetComics Session cookie found. Attempting to load...')
            try:
                with open(self.session_path, 'r') as f:
                    gc_load = json.load(f)
                    for c in gc_load:
                       self.session.cookies.set(name=c['name'], value=c['value'])
            except Exception as e:
                #logger.warn('[GC_Cookie_Loader] Unable to load cookie from file - will recreate. Error: %s' % e)
                if os.path.isfile(self.session_path):
                    os.remove(self.session_path)
            else:
                logger.fdebug('[GC_Cookie_Loader] Successfully loaded cookie from file.')
                test_success = True

        if flare_test is True:
            return test_success


    def __init__(self, query=None, issueid=None, comicid=None, oneoff=False, session_path=None, provider_stat=None):

        self.valreturn = []

        self.flare_headers = {
            'Content-type': 'application/json'
        }

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1',
            'Referer': mylar.GC_URL,
        }

        self.session = requests.Session()

        if mylar.CONFIG.ENABLE_PROXY:
            self.session.proxies.update({
                'http':  mylar.CONFIG.HTTP_PROXY,
                'https': mylar.CONFIG.HTTPS_PROXY
            })

        self.session_path = session_path if session_path is not None else os.path.join(mylar.CONFIG.SECURE_DIR, ".gc_cookies.dat")

        self.url = mylar.GC_URL

        self.query = query  #{'comicname', 'issue', year'}

        self.comicid = comicid

        self.issueid = issueid

        self.oneoff = oneoff

        self.search_format = ['"%s #%s (%s)"', '%s #%s (%s)', '%s #%s', '%s %s']

        self.pack_receipts = ['+ TPBs', '+TPBs', '+ TPB', '+TPB', 'TPB', '+ Deluxe Books', '+ Annuals', '+Annuals', ' & ']

        self.provider_stat = provider_stat

    def search(self,is_info=None):

        self.cookie_receipt()

        try:
            reversed_order = True
            if is_info is not None:
                if is_info['chktpb'] == 0:
                    logger.debug('removing query from loop that accounts for no issue number')
                else:
                    self.search_format.insert(0, self.query['comicname'])
                    logger.debug('setting no issue number query to be first due to no issue number')

            if mylar.CONFIG.PACK_PRIORITY:
                #t_sf = self.search_format.pop(len(self.search_format)-1) #pop the last search query ('%s %s')
                #add it in 1st so that packs will get searched for (hopefully first)
                self.search_format.insert(0, '%s %s' % (self.query['comicname'], self.query['year']))

            for sf in self.search_format:
                verified_matches = []
                sf_issue = self.query['issue']
                if is_info['chktpb'] == 1 and self.query['comicname'] == sf:
                    comicname = re.sub(r'[\&\:\?\,\/\-]', '', self.query['comicname'])
                    comicname = re.sub("\\band\\b", '', comicname, flags=re.I)
                    comicname = re.sub("\\bthe\\b", '', comicname, flags=re.I)
                    queryline = re.sub(r'\s+', ' ', comicname)
                else:
                    if any([self.query['issue'] == 'None', self.query['issue'] is None]):
                        sf_issue = None
                    if sf.count('%s') == 3:
                        if sf == self.search_format[1]:
                            #don't modify the specific query that is around quotation marks.
                            if any([r'/' in self.query['comicname'], r':' in self.query['comicname']]):
                                self.query['comicname'] = re.sub(r'[/|:]', ' ', self.query['comicname'])
                                self.query['comicname'] = re.sub(r'\s+', ' ', self.query['comicname'])
                        if sf_issue is None:
                            splits = sf.split(' ')
                            splits.pop(1)
                            queryline = ' '.join(splits) % (self.query['comicname'], self.query['year'])
                        else:
                            queryline = sf % (self.query['comicname'], sf_issue, self.query['year'])
                    else:
                        #logger.fdebug('[%s] self.search_format: %s' % (len(self.search_format), sf))
                        if len(self.search_format) == 5 and sf == self.search_format[4]:
                            splits = sf.split(' ')
                            splits.pop(1)
                            queryline = ' '.join(splits) % (self.query['comicname'])
                        else:
                            sf_count = len([m.start() for m in re.finditer('(?=%s)', sf)])
                            if sf_count == 0:
                                # this is the injected search format above that's already replaced values
                                queryline = sf
                            elif sf_count == 2:
                                queryline = sf % (self.query['comicname'], sf_issue)
                            elif sf_count == 3:
                                queryline = sf % (self.query['comicname'], sf_issue, self.query['year'])
                            else:
                                queryline = sf % (self.query['comicname'])

                if not queryline:
                    continue

                logger.fdebug('[DDL-QUERY] Query set to: %s' % queryline)

                result_generator = self.perform_search_queries(queryline)
                sfs = search_filer.search_check()
                match = sfs.check_for_first_result(
                    result_generator, is_info, prefer_pack=mylar.CONFIG.PACK_PRIORITY
                )
                if match is not None:
                    verified_matches = [match]
                    logger.fdebug('verified_matches: %s' % (verified_matches,))
                    break
                logger.fdebug('sleep...%s%s' % (mylar.CONFIG.DDL_QUERY_DELAY, 's'))
                time.sleep(mylar.CONFIG.DDL_QUERY_DELAY)

        except requests.exceptions.Timeout as e:
            logger.warn(
                'Timeout occured fetching data from DDL: %s' % e
            )
            return 'no results'
        except requests.exceptions.ConnectionError as e:
            logger.warn(
                '[WARNING] Connection refused to DDL site, stopped by a small tank.'
                ' Error returned as : %s' % e
            )
            if any(
                [
                    errno.ETIMEDOUT,
                    errno.ECONNREFUSED,
                    errno.EHOSTDOWN,
                    errno.EHOSTUNREACH,
                ]
            ):
                helpers.disable_provider('DDL', 'Connection Refused.')
            return 'no results'
        except Exception as err:
            logger.warn(
                '[WARNING] Unable to scrape remote site, stopped by a small tank.'
                ' Error returned as : %s' % err
            )
            if 'Unable to identify Cloudflare IUAM' in str(err):
                helpers.disable_provider(
                    'DDL', 'Unable to identify Cloudflare IUAM Javascript on website'
                )

            # since we're capturing exceptions here, searches from the search module
            # won't get capture. So we need to do this so they get tracked.
            exc_type, exc_value, exc_tb = sys.exc_info()
            filename, line_num, func_name, err_text = traceback.extract_tb(
                exc_tb
            )[-1]
            tracebackline = traceback.format_exc()

            except_line = {
                'exc_type': exc_type,
                'exc_value': exc_value,
                'exc_tb': exc_tb,
                'filename': filename,
                'line_num': line_num,
                'func_name': func_name,
                'err': str(err),
                'err_text': err_text,
                'traceback': tracebackline,
                'comicname': None,
                'issuenumber': None,
                'seriesyear': None,
                'issueid': self.issueid,
                'comicid': self.comicid,
                'mode': None,
                'booktype': None,
            }

            helpers.log_that_exception(except_line)

            return 'no results'
        else:
            if mylar.CONFIG.PACK_PRIORITY is True:
                #logger.fdebug('[PACK_PRIORITY:True] %s' % (sorted(verified_matches, key=itemgetter('pack'), reverse=True)))
                return sorted(verified_matches, key=itemgetter('pack'), reverse=True)
            else:
                #logger.fdebug('[PACK_PRIORITY:False] %s' % (sorted(verified_matches, key=itemgetter('pack'), reverse=False)))
                return sorted(verified_matches, key=itemgetter('pack'), reverse=False)

    def loadsite(self, id, link):

        title = os.path.join(mylar.CONFIG.CACHE_DIR, 'html_cache', 'getcomics-' + id)
        logger.fdebug('now loading info from local html to resolve via url: %s' % link)

        self.cookie_receipt()
        #logger.fdebug('session cookies: %s' % (self.session.cookies,))
        t = self.session.get(
            link,
            verify=True,
            headers=self.headers,
            stream=True,
           timeout=(30,30)
        )

        with open(title + '.html', 'wb') as f:
            for chunk in t.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()

    def perform_search_queries(self, queryline):
        next_url = self.url
        seen_urls = set()
        while next_url is not None:
            pause_the_search = mylar.CONFIG.DDL_QUERY_DELAY
            diff = mylar.search.check_time(self.provider_stat['lastrun']) # only limit the search queries - the other calls should be direct and not as intensive
            if diff < pause_the_search:
                logger.warn('[PROVIDER-SEARCH-DELAY][DDL] Waiting %s seconds before we fetch a search page again...' % (pause_the_search - int(diff)))
                time.sleep(pause_the_search - int(diff))
            else:
                logger.fdebug('[PROVIDER-SEARCH-DELAY][DDL] Last search page fetch took place %s seconds ago. We\'re clear...' % (int(diff)))

            gc_page = self.session.get(
                next_url + '/',
                params={'s': queryline},
                verify=True,
                headers=self.headers,
                timeout=(30,30)
            )

            # Either comms problems with the page, dead link, or a cloudflare issue
            if gc_page.status_code != 200:
                logger.warn(f"Search request not returned by GetComics (Code:{gc_page.status_code}).  This may be a CloudFlare block.")
                break
            
            page_html = gc_page.text

            write_time = time.time()
            mylar.search.last_run_check(write={'DDL(GetComics)': {'id': 200, 'active': True, 'lastrun': write_time, 'type': 'DDL', 'hits': self.provider_stat['hits']+1}})
            self.provider_stat['lastrun'] = write_time
            page_results, next_url = self.parse_search_result(page_html, gc_page.status_code)

            #logger.fdebug('page_results: %s' % page_results)
            possible_choices = []
            for result in page_results:
                if 'Weekly' not in self.query.get('comicname', "") and 'Weekly' in result.get('title', ""):
                    continue
                if result["link"] in seen_urls:
                    continue
                seen_urls.add(result["link"])
                #if not mylar.CONFIG.PACK_PRIORITY:
                #    possible_choices.append(result)
                #else:
                yield result

            #if not mylar.CONFIG.PACK_PRIORITY and possible_choices:
            #    logger.info('[pack-last choices] possible choices to check before page-loading next page..: %s' % possible_choices)
            #    yield possible_choices

    def parse_search_result(self, page_html, status_code):
        resultlist = []
        soup = BeautifulSoup(page_html, 'html.parser')

        articles = soup.findAll("article")
        page_list = soup.find("ul", {"class": "page-numbers"})
        # A single-page result has "NO MORE ARTICLES" instead of numbers
        page_no = total_pages = "1"
        if page_list is not None:
            page_numbers = page_list.find_all("li")
            if len(page_numbers):
                total_pages = page_numbers[-1].text
            current_page_span = page_list.find("span", class_="current")
            if current_page_span is not None:
                page_no = current_page_span.text

        logger.info(f'There are {len(articles)} results on page {page_no} (of {total_pages}) [Status Code: {status_code}]')

        for f in articles:
            id = f['id']
            lk = f.find('a')
            link = lk['href']
            titlefind = f.find("h1", {"class": "post-title"})
            title = titlefind.get_text(strip=True)
            title = re.sub('\u2013', '-', title).strip()

            pack_checker = self.check_for_pack(title, issue_in_pack=self.query['issue'])
            if pack_checker:
                issues = pack_checker['issues']
                gc_booktype = pack_checker['gc_booktype']
                pack = pack_checker['pack']
                series = pack_checker['series']
                title = pack_checker['title']
                filename = pack_checker['filename']
                year = pack_checker['year']
            else:
                if any(
                    [
                        'Marvel Week+' in title,
                        'INDIE Week+' in title,
                        'Image Week' in title,
                        'DC Week+' in title,
                    ]
                ):
                    continue
                else:
                    pack = False
                    issues = None
                    filename = series = title = None

            needle_style = "text-align: center;"
            option_find = f.find("p", {"style": needle_style})
            i = 0
            if option_find is None:
                # Some search results have the "option_find" HTML as escaped
                # text instead of actual HTML: try to salvage a option_find in
                # that case
                excerpt = f.find("p", class_="post-excerpt")
                if excerpt is not None and needle_style in excerpt.text:
                    option_find = BeautifulSoup(excerpt.text, "html.parser").find("p", {"style": needle_style})
                else:
                    continue
            while i <= 2 and option_find is not None:
                option_find = option_find.findNext(text=True)
                if 'Year' in option_find:
                    year = option_find.findNext(text=True)
                    year = re.sub(r'\|', '', year).strip()
                    if pack is True:
                        title = re.sub(r'\(' + year + r'\)', '', title).strip()
                else:
                    size = option_find.findNext(text=True)
                    if all(
                        [
                            re.sub(':', '', size).strip() != 'Size',
                            len(re.sub(r'[^0-9]', '', size).strip()) > 0,
                        ]
                    ):
                        if all(
                                  [
                                      '-' in size,
                                      re.sub(r'[^0-9]', '', size).strip() == '',
                                  ]
                        ):
                            size = None
                        if 'MB' in size:
                            size = re.sub('MB', 'M', size).strip()
                        if 'GB' in size:
                            size = re.sub('GB', 'G', size).strip()
                        if '//' in size:
                            nwsize = size.find('//')
                            size = re.sub(r'\[', '', size[:nwsize]).strip()
                        elif '/' in size:
                            nwsize = size.find('/')
                            size = re.sub(r'\[', '', size[:nwsize]).strip()
                        if '-' in size:
                            size = None
                    else:
                        size = '0M'
                i += 1
            dateline = f.find('time')
            datefull = dateline['datetime']
            datestamp = time.mktime(time.strptime(datefull, "%Y-%m-%d"))
            resultlist.append(
                {
                    "title": title,
                    "pubdate": datetime.datetime.fromtimestamp(
                        float(datestamp)
                    ).strftime('%a, %d %b %Y %H:%M:%S'),
                    "filename": filename,
                    "size": re.sub(' ', '', size).strip(),
                    "pack": pack,
                    "series": series,
                    "gc_booktype": gc_booktype,
                    "issues": issues,
                    "link": link,
                    "year": year,
                    "id": re.sub('post-', '', id).strip(),
                    "site": 'DDL(GetComics)',
                }
            )
            if pack:
                pck = 'yes'
                fname = filename
            else:
                pck = 'no'
                fname = title
            logger.fdebug('%s [%s] [PACK: %s]' % (fname, size, pck))

        older_posts_a = soup.find("a", class_="pagination-older")
        next_page = None
        if older_posts_a is not None:
            next_page = older_posts_a.get("href")

        return resultlist, next_page

    def parse_downloadresults(self, id, mainlink, comicinfo=None, packinfo=None, link_type_failure=None):
        try:
            booktype = comicinfo[0]['booktype']
        except Exception:
            booktype = None

        pack = pack_numbers = pack_issuelist = None
        logger.fdebug('packinfo: %s' % (packinfo,))

        if packinfo is not None:
            pack = packinfo['pack']
            pack_numbers = packinfo['pack_numbers']
            pack_issuelist = packinfo['pack_issuelist']
        else:
            try:
                pack = comicinfo[0]['pack']
            except Exception as e:
                pack = False

        myDB = db.DBConnection()
        series = None
        year = None
        size = None
        title = os.path.join(mylar.CONFIG.CACHE_DIR, 'html_cache', 'getcomics-' + id)

        if not os.path.exists(title):
            logger.fdebug('Unable to locate local cached html file - attempting to retrieve page results again..')
            self.loadsite(id, mainlink)

        soup = BeautifulSoup(open(title + '.html', encoding='utf-8'), 'html.parser')

        i = 0
        possible_more = None
        valid_links = {}
        multiple_links = None
        gather_links = []
        count_bees = 0
        looped_thru_once = True

        beeswax = soup.findAll("p", {"style": "text-align: center;"})
        logger.info('[DDL-GATHERER-OF-LINKAGE] Now compiling release information & available links...')
        while True:
            #logger.fdebug('count_bees: %s' % count_bees)
            try:
                f = beeswax[count_bees]
                option_find = beeswax[count_bees]
                linkage = f.find("div", {"class": "aio-pulse"})
            except Exception as e:
                if looped_thru_once is False:
                    valid_links[multiple_links].update({'links': gather_links})
                break

            #logger.fdebug('linkage: %s' % linkage)
            if not linkage:
                linkage_test = f.text.strip()
                if 'support and donation' in linkage_test:
                    if looped_thru_once is False:
                        valid_links[multiple_links].update({'links': gather_links})
                    #logger.fdebug('detected end of links - breaking out here...')
                    break

                if looped_thru_once and all(
                    [
                     'Language' in linkage_test,
                     'Year' in linkage_test,
                     'Size' in linkage_test,
                    ]
                ):
                    #logger.fdebug('detected headers of title - ignoring this portion...')
                    while True:
                        prev_option = option_find
                        option_find = option_find.findNext(text=True)
                        if (i == 0 and series is None):
                            series = option_find
                            #logger.fdebug('series: %s' % series)
                            if 'upscaled' in series.lower():
                                valid_links['HD-Upscaled'] = {'series': re.sub('(hd-upscaled)', '', series, re.IGNORECASE).strip()}
                                multiple_links = 'HD-Upscaled'
                            elif 'sd-digital' in series.lower():
                                valid_links['SD-Digital'] = {'series': re.sub('(sd-digital)', '', series, re.IGNORECASE).strip()}
                                multiple_links = 'SD-Digital'
                            elif 'hd-digital' in series.lower():
                                valid_links['HD-Digital'] = {'series': re.sub('(hd-digital)', '', series, re.IGNORECASE).strip()}
                                multiple_links = 'HD-Digital'
                            else:
                                # if no distinction btwn HD/SD and it's just one section...
                                valid_links['normal'] = {'series': series}
                                multiple_links = 'normal'
                            #logger.fdebug('valid_links : %s' % (valid_links))
                        elif 'Year' in option_find:
                            year = option_find.findNext(text=True)
                            year = re.sub(r'\|', '', year).strip()
                            if any(
                                    [
                                        multiple_links == 'HD-Upscaled',
                                        multiple_links == 'SD-Digital',
                                        multiple_links == 'HD-Digital'
                                    ]
                            ):
                                valid_links[multiple_links].update({'year': year})
                                #logger.fdebug('valid_links [%s] : %s' % (multiple_links, valid_links))
                        else:
                            if 'Size' in prev_option:
                                size = option_find  # .findNext(text=True)
                                possible_more = f.next_sibling
                                if any(
                                        [
                                            multiple_links == 'HD-Upscaled',
                                            multiple_links == 'SD-Digital',
                                            multiple_links == 'HD-Digital'
                                        ]
                                ):
                                    valid_links[multiple_links].update({'size': size})
                                    #logger.fdebug('valid_links [%s] : %s' % (multiple_links, valid_links))

                                looped_thru_once = False
                                break
                        i += 1

            else:
                lk = f.find('a')
                #logger.fdebug('lk: %s' % lk)
                #logger.fdebug('looped_thru_once: %s / lk[title]: %s' % (looped_thru_once, lk['title']))
                if looped_thru_once is False and lk['title'] == 'Read Online':
                    #logger.fdebug('read online section discovered...bypassing and ignoring...')
                    valid_links[multiple_links].update({'links': gather_links})
                    looped_thru_once = True
                    gather_links = []
                    i = 0
                    series = None
                else:
                    t_site = re.sub('link', '', lk['title'].lower()).strip()
                    ltf = False
                    if link_type_failure is not None:
                        if [
                            True
                            for tst in link_type_failure
                            if t_site[:4].lower() in tst.lower()
                            or all(["main" in tst.lower(), "download" in t_site.lower()])
                            or all(["mirror" in tst.lower(), "mirror" in t_site.lower()])
                        ]:
                            logger.fdebug('[REDO-FAILURE-DETECTION] detected previous invalid link for %s - ignoring this result'
                                        ' and seeing if anything else can be downloaded.' % t_site)
                            ltf = True

                    if not ltf:
                        if 'sh.st' not in lk['href']:
                            gather_links.append({
                                 "series": series,
                                 "site": t_site,
                                 "year": year,
                                 "issues": None,
                                 "size": size,
                                 "links": lk['href'],
                                 "pack": pack
                            })
                            #logger.fdebug('gather_links so far: %s' % gather_links)
            count_bees +=1

        #logger.fdebug('final valid_links: %s' % (valid_links))
        tmp_links = []
        tmp_sites = []
        site_position = {}
        cntr = 0
        link = None

        for k,y in valid_links.items():
           for a in y['links']:
               if k != 'normal':
                   # if it's HD-Upscaled / SD-Digital it needs to be handled differently than a straight DL link
                   if any([a['site'].lower() == 'download now', a['site'].lower() == 'mirror download']):
                       d_site = '%s:%s' % (k, a['site'].lower())
                       tmp_a = a
                       tmp_a['site_type'] = d_site
                       tmp_links.append(tmp_a)
                       tmp_sites.append(d_site)
                       site_position[d_site] = cntr
                       logger.fdebug('%s -- %s' % (d_site, a['series']))
                       cntr +=1
                   elif any(['mega' in a['site'].lower(), 'pixel' in a['site'].lower(), 'mediafire' in a['site'].lower()]):
                       if 'mega' in a['site'].lower():
                           d_site = '%s:%s' % (k, 'mega')
                       elif 'pixel' in a['site'].lower():
                           d_site = '%s:%s' % (k, 'pixeldrain')
                       else:
                           d_site = '%s:%s' % (k, 'mediafire')
                       tmp_a = a
                       tmp_a['site_type'] = d_site
                       tmp_links.append(tmp_a)
                       tmp_sites.append(d_site)
                       site_position[d_site] = cntr
                       logger.fdebug('%s -- %s' % (d_site, a['series']))
                       cntr +=1
               else:
                   if any(
                             [
                                 a['site'].lower() == 'download now',
                                 a['site'].lower() == 'mirror download',
                                 'mega' in a['site'].lower(),
                                 'pixel' in a['site'].lower(),
                                 'mediafire' in a['site'].lower()
                             ]
                       ):
                       t_site = a['site'].lower()
                       if 'mega' in a['site'].lower():
                           t_site = 'mega'
                       elif 'pixel' in a['site'].lower():
                           t_site = 'pixeldrain'
                       elif 'mediafire' in a['site'].lower():
                           t_site = 'mediafire'
                       d_site = '%s:%s' % (k, t_site)
                       tmp_a = a
                       tmp_a['site_type'] = d_site
                       tmp_links.append(tmp_a)
                       tmp_sites.append(d_site)
                       site_position[d_site] = cntr
                       logger.fdebug('%s -- %s' % (d_site, a['series']))
                       cntr +=1


        #logger.fdebug('tmp_links: %s' % (tmp_links))
        logger.fdebug('tmp_sites: %s' % (tmp_sites))
        logger.fdebug('site_position: %s' % (site_position))
        link_types = ('HD-Upscaled', 'SD-Digital', 'HD-Digital')
        link_matched = False
        if len(tmp_links) == 1:
            link = tmp_links[0]
            series = link['series']
            logger.info('only one available item that can be downloaded via %s - %s. Let\'s do this..' % (link['site'], series))
            link_matched = True
        elif len(tmp_links) > 1:
            logger.info('Multiple available download options (%s) - checking configuration to see which to grab...' % (" ,".join(tmp_sites)))
            site_check = [y for x in link_types for y in tmp_sites if x in y]
            for ddlp in mylar.CONFIG.DDL_PRIORITY_ORDER:
                force_title = False
                site_lp = ddlp
                logger.fdebug('priority ddl enabled - checking %s' % site_lp)
                if site_check: #any([('HD-Upscaled', 'SD-Digital', 'HD-Digital') in tmp_sites]):
                    if mylar.CONFIG.DDL_PREFER_UPSCALED:
                        if not link_matched and site_lp == 'mega':
                            sub_site_chk = [y for y in tmp_sites if 'mega' in y]
                            if sub_site_chk:
                                if any('HD-Upscaled' in ssc for ssc in sub_site_chk):
                                    kk = tmp_links[site_position['HD-Upscaled:mega']]
                                    logger.info('[MEGA] HD-Upscaled preference detected...attempting %s' % kk['series'])
                                    link_matched = True
                                elif any('HD-Digital' in ssc for ssc in sub_site_chk):
                                    kk = tmp_links[site_position['HD-Digital:mega']]
                                    logger.info('[MEGA] HD-Digital preference detected...attempting %s' % kk['series'])
                                    link_matched = True

                        elif not link_matched and site_lp == 'pixeldrain':
                            sub_site_chk = [y for y in tmp_sites if 'pixel' in y]
                            if sub_site_chk:
                                if any('HD-Upscaled' in ssc for ssc in sub_site_chk):
                                    kk = tmp_links[site_position['HD-Upscaled:pixeldrain']]
                                    logger.info('[PixelDrain] HD-Upscaled preference detected...attempting %s' % kk['series'])
                                    link_matched = True
                                elif any('HD-Digital' in ssc for ssc in sub_site_chk):
                                    kk = tmp_links[site_position['HD-Digital:pixeldrain']]
                                    logger.info('[PixelDrain] HD-Digital preference detected...attempting %s' % kk['series'])
                                    link_matched = True

                        elif not link_matched and site_lp == 'mediafire':
                            sub_site_chk = [y for y in tmp_sites if 'mediafire' in y]
                            if sub_site_chk:
                                if any('HD-Upscaled' in ssc for ssc in sub_site_chk):
                                    kk = tmp_links[site_position['HD-Upscaled:mediafire']]
                                    logger.info('[mediafire] HD-Upscaled preference detected...attempting %s' % kk['series'])
                                    link_matched = True
                                elif any('HD-Digital' in ssc for ssc in sub_site_chk):
                                    kk = tmp_links[site_position['HD-Digital:mediafire']]
                                    logger.info('[mediafire] HD-Digital preference detected...attempting %s' % kk['series'])
                                    link_matched = True

                        elif not link_matched and site_lp == 'main':
                            sub_site_chk = [y for y in tmp_sites if 'download now' in y]
                            if any('HD-Upscaled' in ssc for ssc in sub_site_chk):
                                kk = tmp_links[site_position['HD-Upscaled:download now']]
                                logger.info('[MAIN-SERVER] HD-Upscaled preference detected...attempting %s' % kk['series'])
                                link_matched = True
                            elif any('HD-Digital' in ssc for ssc in sub_site_chk):
                                kk = tmp_links[site_position['HD-Digital:download now']]
                                logger.info('[MAIN-SERVER] HD-Digital preference detected...attempting %s' % kk['series'])
                                link_matched = True

                    if not link_matched and site_lp == 'mega':
                        sub_site_chk = [y for y in tmp_sites if 'mega' in y]
                        if sub_site_chk:
                            try:
                               kk = tmp_links[site_position['SD-Digital:mega']]
                               logger.info('[MEGA] SD-Digital preference detected...attempting %s' % kk['series'])
                               link_matched = True
                            except KeyError:
                                kk = tmp_links[site_position['normal:mega']]
                                logger.info('[MEGA] mega preference detected...attempting %s' % kk['series'])
                                link_matched = True

                    elif not link_matched and site_lp == 'pixeldrain':
                        sub_site_chk = [y for y in tmp_sites if 'pixel' in y]
                        if sub_site_chk:
                            try:
                                kk = tmp_links[site_position['SD-Digital:pixeldrain']]
                                logger.info('[PixelDrain] SD-Digital preference detected...attempting %s' % kk['series'])
                                link_matched = True
                            except KeyError:
                                kk = tmp_links[site_position['normal:pixeldrain']]
                                logger.info('[PixelDrain] PixelDrain preference detected...attempting %s' % kk['series'])
                                link_matched = True

                    elif not link_matched and site_lp == 'mediafire':
                        sub_site_chk = [y for y in tmp_sites if 'mediafire' in y]
                        if sub_site_chk:
                            try:
                                kk = tmp_links[site_position['SD-Digital:mediafire']]
                                logger.info('[mediafire] SD-Digital preference detected...attempting %s' % kk['series'])
                                link_matched = True
                            except KeyError:
                                kk = tmp_links[site_position['normal:mediafire']]
                                logger.info('[mediafire] mediafire preference detected...attempting %s' % kk['series'])
                                link_matched = True

                    elif not link_matched and site_lp == 'main':
                        try:
                            kk = tmp_links[site_position['SD-Digital:download now']]
                            logger.info('[MAIN-SERVER] SD-Digital preference detected...attempting %s' % kk['series'])
                            link_matched = True
                        except Exception as e:
                            try:
                                kk = tmp_links[site_position['SD-Digital:mirror download']]
                                logger.info('[MIRROR-SERVER] SD-Digital preference detected...attempting %s' % kk['series'])
                                link_matched = True
                            except KeyError:
                                try:
                                    kk = tmp_links[site_position['normal:download now']]
                                    logger.info('[MAIN-SERVER] main preference detected...attempting %s' % kk['series'])
                                    link_matched = True
                                except KeyError:
                                    kk = tmp_links[site_position['normal:mirror download']]
                                    logger.info('[MIRROR-SERVER] main-mirror preference detected...attempting %s' % kk['series'])
                                    link_matched = True

                    if link_matched:
                        link = kk
                        series = link['series']
                        #logger.fdebug('link: %s' % link)
                else:
                   if not link_matched and site_lp == 'mega':
                       sub_site_chk = [y for y in tmp_sites if 'mega' in y]
                       if sub_site_chk:
                           try:
                               link = tmp_links[site_position['normal:mega']]
                               link_matched = True
                           except Exception as e:
                               link = tmp_links[site_position['normal:mega link']]
                               link_matched = True
                   elif not link_matched and site_lp == 'pixeldrain':
                       sub_site_chk = [y for y in tmp_sites if 'pixel' in y]
                       if sub_site_chk:
                           try:
                               link = tmp_links[site_position['normal:pixeldrain']]
                               link_matched = True
                           except Exception as e:
                               logger.info('[PIXELDRAIN] Unable to attain proper link...')
                               link_matched = False
                   elif not link_matched and site_lp == 'mediafire':
                       sub_site_chk = [y for y in tmp_sites if 'mediafire' in y]
                       if sub_site_chk:
                           try:
                               link = tmp_links[site_position['normal:mediafire']]
                               link_matched = True
                           except Exception as e:
                               logger.info('[mediafire] Unable to attain proper link...')
                               link_matched = False
                   elif not link_matched and site_lp == 'main':
                       if 'download now' in tmp_sites:
                           link = tmp_links[site_position['normal:download now']]
                       elif 'mirror download' in tmp_sites:
                           link = tmp_links[site_position['normal:mirror download']]
                       else:
                           link = tmp_links[0]
                           force_title = True
                       if 'sh.st' in link:
                           logger.fdebug('[Paywall-link detected] this is not a valid link')
                           link_matched = False
                       else:
                           if force_title:
                               series = link['series']
                           link_matched = True

        else:
            logger.info('No valid items available that I am able to download from. Not downloading...')
            return {'success': False, 'links_exhausted': link_type_failure}

        dl_selection = link['site']

        logger.fdebug(
            '[%s] Now downloading: %s [%s] / %s ... this can take a while'
            ' (go get some take-out)...' % (dl_selection, series, year, size)
        )

        tmp_filename = '%s (%s)' % (series, year)

        links = []

        if link is None and possible_more.name == 'ul':
            try:
                bb = possible_more.findAll('li')
            except Exception:
                pass
            else:
                for x in bb:
                    linkline = x.find('a')
                    try:
                        tmp = linkline['href']
                    except Exception:
                        continue

                    site = linkline.findNext(text=True)
                    #logger.fdebug('servertype: %s' % (site))

                    if tmp:
                        if any(
                            [
                                'run.php' in linkline['href'],
                                'go.php' in linkline['href'],
                                'comicfiles.ru' in linkline['href'],
                                ('links.php' in linkline['href'] and site == 'Main Server'),
                            ]
                        ):
                            volume = x.findNext(text=True)
                            if '\u2013' in volume:
                                volume = re.sub(r'\u2013', '-', volume)
                            # volume label contains series, issue(s), year(s), and size
                            series_st = volume.find('(')
                            issues_st = volume.find('#')
                            series = volume[:series_st]
                            if any([issues_st == -1, series_st == -1]):
                                issues = None
                            else:
                                series = volume[:issues_st].strip()
                                issues = volume[issues_st + 1 : series_st].strip()
                                ver_check = self.pack_check(issues, packinfo)
                                if ver_check is False:
                                    #logger.fdebug('ver_check is False - ignoring')
                                    continue

                            if issues is None and any([booktype == 'Print', booktype is None, booktype == 'Digital']):
                                continue
                            year_end = volume.find(')', series_st + 1)
                            year = re.sub(
                                r'[\(\)]', '', volume[series_st + 1 : year_end]
                            ).strip()
                            size_end = volume.find(')', year_end + 1)
                            size = re.sub(
                                r'[\(\)]', '', volume[year_end + 1 : size_end]
                            ).strip()
                            linked = linkline['href']
                            #site = linkline.findNext(text=True)
                            if site == 'Main Server':
                                links.append(
                                    {
                                        "series": series,
                                        "site": site,
                                        "year": year,
                                        "issues": issues,
                                        "size": size,
                                        "links": linked,
                                        "pack": pack
                                    }
                                )
        else:
            if booktype != 'TPB' and pack is False:
                logger.fdebug('Extra links detected, possibly different booktypes - but booktype set to %s' % booktype)
            else:
                check_extras = soup.findAll("h3")
                for sb in check_extras:
                    header = sb.findNext(text=True)
                    if header == 'TPBs' and bookype == 'TPB':
                        nxt = sb.next_sibling
                        if nxt.name == 'ul':
                            bb = nxt.findAll('li')
                            for x in bb:
                                volume = x.findNext(text=True)
                                if '\u2013' in volume:
                                    volume = re.sub(r'\u2013', '-', volume)
                                series_st = volume.find('(')
                                issues_st = volume.find('#')
                                series = volume[:issues_st].strip()
                                issues = volume[issues_st:series_st].strip()
                                year_end = volume.find(')', series_st + 1)
                                year = re.sub(
                                    r'[\(\)\|]', '', volume[series_st + 1 : year_end]
                                ).strip()
                                size_end = volume.find(')', year_end + 1)
                                size = re.sub(
                                    r'[\(\)\|]', '', volume[year_end + 1 : size_end]
                                ).strip()
                                linkline = x.find('a')
                                linked = linkline['href']
                                site = linkline.findNext(text=True)
                                links.append(
                                    {
                                        "series": series,
                                        "volume": volume,
                                        "site": site,
                                        "year": year,
                                        "issues": issues,
                                        "size": size,
                                        "links": linked,
                                        "pack": pack
                                    }
                                )

        if all([link is None, len(links) == 0]):
            logger.warn(
                'Unable to retrieve any valid immediate download links.'
                ' They might not exist.'
            )
            return {'success': False, 'links_exhausted': link_type_failure}
        if all([link is not None, len(links) == 0]):
            logger.info(
                'Only one item discovered, changing queue length to accomodate: %s [%s]'
                % (link, type(link))
            )
            links = [link]
        elif len(links) > 0:
            if link is not None:
                links.append(link)
                logger.fdebug(
                    '[DDL-QUEUE] Making sure we download the original item in addition'
                    ' to the extra packs.'
                )
            if len(links) > 1:
                logger.fdebug(
                    '[DDL-QUEUER] This pack has been broken up into %s separate packs -'
                    ' queueing each in sequence for your enjoyment.' % len(links)
                )
        cnt = 1
        for x in links:
            if len(links) == 1:
                mod_id = id
            else:
                mod_id = id + '-' + str(cnt)

            lt_site = x['site'].lower()
            if any([lt_site == 'main server', lt_site == 'download now']):
                link_type = 'GC-Main'
            elif lt_site == 'mirror download':
                link_type = 'GC-Mirror'
            elif lt_site == 'mega':
                link_type = 'GC-Mega'
            elif lt_site == 'mediafire':
                link_type = 'GC-Media'
            elif lt_site == 'pixeldrain':
                link_type = 'GC-Pixel'
            else:
                logger.warn('[GC-Site-Unknown] Unknown site detected...%s' % lt_site)
                link_type = 'Unknown'

            if self.issueid is None:
                self.issueid = comicinfo[0]['IssueID']
            if self.comicid is None:
                self.comicid = comicinfo[0]['ComicID']
            if self.oneoff is None:
                self.oneoff = comicinfo[0]['oneoff']

            ctrlval = {'id': mod_id}
            vals = {
                'series': x['series'],
                'year': x['year'],
                'size': x['size'],
                'issues': x['issues'],
                'issueid': self.issueid,
                'comicid': self.comicid,
                'link': x['links'],
                'mainlink': mainlink,
                'site': 'DDL(GetComics)',
                'pack': x['pack'],
                'link_type': link_type,
                'updated_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                'status': 'Queued',
            }
            myDB.upsert('ddl_info', vals, ctrlval)

            #tmp_filename = None
            #if any([link_type == 'Mega', link_type == 'Mega Link']):
                # this is needed so that we assign some tmp filename
                # (it will get renamed upon completion anyways)
                #tmp_filename = comicinfo[0]['nzbtitle']

            mylar.DDL_QUEUE.put(
                {
                    'link': x['links'],
                    'mainlink': mainlink,
                    'series': x['series'],
                    'year': x['year'],
                    'size': x['size'],
                    'comicid': self.comicid,
                    'issueid': self.issueid,
                    'oneoff': self.oneoff,
                    'id': mod_id,
                    'link_type': link_type,
                    'filename': tmp_filename,
                    'comicinfo': comicinfo,
                    'packinfo': packinfo,
                    'site': 'DDL(GetComics)',
                    'remote_filesize': 0,
                    'resume': None,
                }
            )
            cnt += 1

        return {'success': True, 'site': link_type}

    def downloadit(self, id, link, mainlink, resume=None, issueid=None, remote_filesize=0, link_type=None):
        #logger.fdebug('[%s] %s -- mainlink: %s' % (id, link, mainlink))
        if 'sh.st' in link:
            logger.fdebug('[Paywall-link detected] This is not a valid link, this should be requeued to search to gather all available links')
            return {
               "success": False,
               "link_type": link_type}

        if mylar.DDL_LOCK is True:
            logger.fdebug(
                '[DDL] Another item is currently downloading via DDL. Only one item can'
                ' be downloaded at a time using DDL. Patience.'
            )
            return
        else:
            mylar.DDL_LOCK = True

        myDB = db.DBConnection()
        mylar.DDL_QUEUED.append(id)
        filename = None
        self.cookie_receipt()
        try:
            with requests.Session() as s:
                if resume is not None:
                    logger.info(
                        '[DDL-RESUME] Attempting to resume from: %s bytes' % resume
                    )
                    self.headers['Range'] = 'bytes=%d-' % resume

                t = self.session.get(
                    link,
                    verify=True,
                    headers=self.headers,
                    stream=True,
                    timeout=(30,30)
                )

                filename = os.path.basename(
                    urllib.parse.unquote(t.url)
                )
                if 'GetComics.INFO' in filename:
                    filename = re.sub('GetComics.INFO', '', filename, re.I).strip()

                if filename is not None:
                    file, ext = os.path.splitext(filename)
                    filename = '%s[__%s__]%s' % (file, issueid, ext)

                logger.fdebug('filename: %s' % filename)

                if remote_filesize == 0:
                    try:
                        remote_filesize = int(t.headers['Content-length'])
                        logger.fdebug('remote filesize: %s' % remote_filesize)
                    except Exception as e:
                        if 'run.php-urls' not in link:
                            link = re.sub('run.php-url=', 'run.php-urls', link)
                            link = re.sub('go.php-url=', 'run.php-urls', link)
                            t = self.session.get(
                                link,
                                verify=True,
                                headers=self.headers,
                                stream=True,
                                timeout=(30,30)
                            )
                            filename = os.path.basename(
                                urllib.parse.unquote(t.url)
                            )
                            if 'GetComics.INFO' in filename:
                                filename = re.sub(
                                    'GetComics.INFO', '', filename, re.I
                                ).strip()
                            try:
                                remote_filesize = int(t.headers['Content-length'])
                                logger.fdebug('remote filesize: %s' % remote_filesize)
                            except Exception as e:
                                logger.warn(
                                    '[WARNING] Unable to retrieve remote file size - this'
                                    ' is usually due to the page being behind a different'
                                    ' click-bait/ad page. Error returned as : %s' % e
                                )
                                logger.warn(
                                    '[WARNING] Considering this particular download as'
                                    ' invalid and will ignore this result.'
                                )
                                remote_filesize = 0
                                mylar.DDL_LOCK = False
                                return {
                                    "success": False,
                                    "filename": filename,
                                    "path": None,
                                    "link_type": link_type,
                                }

                        else:
                            logger.warn(
                                '[WARNING] Unable to retrieve remote file size - this is'
                                ' usually due to the page being behind a different'
                                ' click-bait/ad page. Error returned as : %s' % e
                            )
                            logger.warn(
                                '[WARNING] Considering this particular download as invalid'
                                ' and will ignore this result.'
                            )
                            remote_filesize = 0
                            mylar.DDL_LOCK = False
                            return {
                                "success": False,
                                "filename": filename,
                                "path": None,
                                "link_type": link_type}

                # write the filename to the db for tracking purposes...
                myDB.upsert(
                    'ddl_info',
                    {'filename': filename, 'remote_filesize': remote_filesize},
                    {'id': id},
                )

                if mylar.CONFIG.DDL_LOCATION is not None and not os.path.isdir(
                    mylar.CONFIG.DDL_LOCATION
                ):
                    checkdirectory = mylar.filechecker.validateAndCreateDirectory(
                        mylar.CONFIG.DDL_LOCATION, True
                    )
                    if not checkdirectory:
                        logger.warn(
                            '[ABORTING] Error trying to validate/create DDL download'
                            ' directory: %s.' % mylar.CONFIG.DDL_LOCATION
                        )
                        return {
                           "success": False,
                           "filename": filename,
                           "path": None,
                           "link_type": link_type}

                dst_path = os.path.join(mylar.CONFIG.DDL_LOCATION, filename)

                t.headers['Accept-encoding'] = 'gzip'
                if resume is not None:
                    with open(dst_path, 'ab') as f:
                        for chunk in t.iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)
                                f.flush()

                else:
                    if os.path.exists(dst_path):
                        logger.fdebug('%s already exists - resume not enabled - let us hammer thine' % dst_path)
                        try:
                            os.remove(dst_path)
                        except Exception as e:
                            file, ext = os.path.splitext(filename)
                            filename = '%s.1%s' % (file, ext)
                            dst_path = os.path.join(mylar.CONFIG.DDL_LOCATION, filename)
                            logger.warn(
                                '[ERROR: %s] Unable to remove already existing file.'
                                ' Creating tmp file @%s so it can download.' % (e, filename)
                            )

                    with open(dst_path, 'wb') as f:
                        for chunk in t.iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)
                                f.flush()

        except requests.exceptions.Timeout as e:
            logger.error('[ERROR] download has timed out due to inactivity...: %s', e)
            mylar.DDL_LOCK = False
            return {
               "success": False,
               "filename": filename,
               "path": None,
               "link_type": link_type}

        except Exception as e:
            logger.error('[ERROR] %s' % e)
            mylar.DDL_LOCK = False
            return {
               "success": False,
               "filename": filename,
               "path": None,
               "link_type": link_type}
        else:
            mylar.DDL_LOCK = False
            return self.zip_zip(id, dst_path, filename)


    def zip_zip(self, id, dst_path, filename):
        if os.path.isfile(dst_path):
            if dst_path.endswith('.zip'):
                new_path = os.path.join(
                    mylar.CONFIG.DDL_LOCATION, re.sub('.zip', '', filename).strip()
                )
                logger.info(
                    'Zip file detected.'
                    ' Unzipping into new modified path location: %s' % new_path
                )
                try:
                    zip_f = zipfile.ZipFile(dst_path, 'r')
                    zip_f.extractall(new_path)
                    zip_f.close()
                except Exception as e:
                    logger.warn(
                        '[ERROR: %s] Unable to extract zip file: %s' % (e, new_path)
                    )
                    return {"success": False, "filename": filename, "path": None}
                else:
                    try:
                        os.remove(dst_path)
                    except Exception as e:
                        logger.warn(
                            '[ERROR: %s] Unable to remove zip file from %s after'
                            ' extraction.' % (e, dst_path)
                        )
                    filename = None
            else:
                new_path = dst_path
            return {"success": True, "filename": filename, "path": new_path}

        mylar.DDL_LOCK = False
        return {"success": False, "filename": filename, "path": None}

    def check_for_pack(self, title, issue_in_pack=None):

        og_title = title

        volume_label = None
        annuals = False
        issues = None
        pack = False

        filename = series = title

        #logger.fdebug('pack: %s' % pack)
        tpb = False
        gc_booktype = None
        # see if it's a pack type

        volume_issues = None
        title_length = len(title)

        # find the year
        year_check = re.search(r'(\d{4}-\d{4})', title, flags=re.I)
        if not year_check:
            year_check = re.findall(r'(\d{4})', title, flags=re.I)
            if year_check:
                for yc in year_check:
                    if title[title.find(yc)-1] != '#':
                        if yc.startswith('19') or yc.startswith('20'):
                            year = yc
                            logger.fdebug('year: %s' % year)
                            break
            else:
                #logger.fdebug('no year found within name...')
                year = None
        else:
            year = year_check.group()
            #logger.fdebug('year range: %s' % year)

        if year is not None:
            title = re.sub(year, '', title).strip()
            title = re.sub('\(\)', '', title).strip()

        issfind_st = title.find('#')
        #logger.fdebug('issfind_st: %s' % issfind_st)
        if issfind_st != -1:
            issfind_en = title.find('-', issfind_st)
        else:
           # if it's -1, odds are it's a range, so need to work back
            issfind_en = title.find('-')
            #logger.fdebug('issfind_en: %s' % issfind_en)
            #logger.fdebug('issfind_en-2: %s' % issfind_en -2)
            if title[issfind_en -2].isdigit():
                issfind_st = issfind_en -2
                #logger.fdebug('issfind_st: %s' % issfind_st)
            #logger.fdebug('rfind: %s' % title.lower().rfind('vol'))
            if title.lower().rfind('vol') != -1:
                #logger.fdebug('yes')
                vol_find = title.lower().rfind('vol')
                logger.fdebug('vol_find: %s' % vol_find)
                if vol_find+2 == issfind_st:  #vol 1 - 5
                    issfind_st = vol_find+3
                if vol_find+3 == issfind_st:  #vol. 1 - 5
                    issfind_st = vol_find+4

        #logger.fdebug('issfind_en: %s' % issfind_en)
        if issfind_en != -1:
            if all([title[issfind_en + 1] == ' ', title[issfind_en + 2].isdigit()]):
                iss_en = title.find(' ', issfind_en + 2)
                #logger.info('iss_en: %s [%s]' % (iss_en, title[iss_en +2]))
                if iss_en == -1:
                    iss_en = len(title)
                if iss_en != -1:
                    #logger.info('issfind_st: %s' % issfind_st)
                    issues = title[issfind_st : iss_en]
                    if title.lower().rfind('vol') == issfind_st -5 or title.lower().rfind('vol') == issfind_st -4:
                        series = '%s %s' % (title[:title.lower().rfind('vol')].strip(), title[iss_en:].strip())
                        logger.info('new series: %s' % series)
                        volume_issues = issues
                        if len(title) - 6 > title.lower().rfind('tpb') > 1:
                            gc_booktype = 'TPB'
                        elif len(title) - 6 > title.lower().rfind('gn') > 1:
                            gc_booktype = 'GN'
                        elif len(title) - 6 > title.lower().rfind('hc') > 1:
                            gc_booktype = 'HC'
                        elif len(title) - 6 > title.lower().rfind('one-shot') > 1:
                            gc_booktype = 'One-Shot'
                        else:
                            gc_booktype = 'TPB/GN/HC/One-Shot'
                        tpb = True
                    #else:
                    t1 = title.lower().rfind('volume')
                    vcheck = 'volume'
                    if t1 == -1:
                        t1 = title.lower().rfind('vol.')
                        vcheck = 'vol.'
                        if t1 == -1:
                            t1 = title.lower().rfind('vol')
                            vcheck = 'vol'
                    if t1 != -1:
                        #logger.fdebug('vcheck: %s' % (len(vcheck)))
                        #logger.fdebug('title.find: %s' % title.lower().find(' ', t1))
                        vv = title.lower().find(' ', title.lower().find(' ', t1)+1)
                        #logger.fdebug('vv: %s' % vv)
                        if tpb:
                            volume_label = title[t1:t1+len(vcheck)].strip()
                        else:
                            volume_label = title[t1:vv].strip()
                        logger.fdebug('volume discovered: %s' % volume_label)

                    pack = True
                    logger.fdebug('issues: %s' % issues)
            elif title[issfind_en + 1].isdigit():
                iss_en = title.find(' ', issfind_en + 1)
                if iss_en != -1:
                    issues = title[issfind_st + 1 : iss_en]
                    pack = True


        # to handle packs that are denoted without a # sign being present.
        # if there's a dash, check to see if both sides of the dash are numeric.
        logger.fdebug('pack: [%s] %s' % (type(pack),pack))
        if not pack and title.find('-') != -1:
            #logger.fdebug('title: %s' % title)
            #logger.fdebug('title[issfind_en+1]: %s' % title[issfind_en +1])
            #logger.fdebug('title[issfind_en+2]: %s' % title[issfind_en +2])
            #logger.fdebug('title[issfind_en-1]: %s' % title[issfind_en -1])
            if all(
                   [
                       title[issfind_en + 1] == ' ',
                       title[issfind_en + 2].isdigit(),
                   ]
            ) and all(
                   [
                       title[issfind_en -1] == ' ',
                   ]
            ):
                spaces = [m.start() for m in re.finditer(' ', title)]
                dashfind = title.find('–')
                space_beforedash = title.find(' ', dashfind - 1)
                space_afterdash = title.find(' ', dashfind + 1)
                if not title[space_afterdash+1].isdigit():
                    pass
                else:
                    iss_end = title.find(' ', space_afterdash + 1)
                    if iss_end == -1:
                        iss_end = len(title)
                    set_sp = None
                    for sp in spaces:
                        if sp < space_beforedash:
                            prior_sp = sp
                        else:
                            set_sp = prior_sp
                            break
                    if title[set_sp:space_beforedash].strip().isdigit():
                        issues = title[set_sp:iss_end].strip()
                        pack = True
        # if it's a pack - remove the issue-range and the possible issue years
        # (cause it most likely will span) and pass thru as separate items
        if series is None:
            series = title
        if pack is True or pack is False:
            #f_iss = series.find('#')
            #if f_iss != -1:
            #    series = '%s%s'.strip() % (title[:f_iss-1], title[f_iss+1:])
            #series = re.sub(issues, '', series).strip()
            # kill any brackets in the issue line here.
            #issgggggggues = re.sub(r'[\(\)\[\]]', '', issues).strip()
            #if series.endswith('#'):
            #    series = series[:-1].strip()
            #title += ' #1'  # we add this dummy value back in so the parser won't choke as we have the issue range stored already

            #if year is not None:
            #    title += ' (%s)' % year
            logger.fdebug('pack_check: %s/ title: %s' % (pack, title))
            og_series = series
            if pack is False:
                f_iss = title.find('#')
                #logger.fdebug('f_iss: %s' % f_iss)
                if f_iss != -1:
                    series = '%s'.strip() % (title[:f_iss-1])
                    #logger.fdebug('changed_title: %s' % series)
            #logger.fdebug('title: %s' % title)
            issues = r'%s' % issues
            title = re.sub(issues, '', title).strip()
            # kill any brackets in the issue line here.
            #logger.fdebug('issues-before: %s' % issues)
            issues = re.sub(r'[\(\)\[\]]', '', issues).strip()
            #logger.fdebug('issues-after: %s' % issues)
            if series.endswith('#'):
                series = series[:-1].strip()

            og_series = series

            crap = re.findall(r"\(.*?\)", title)
            for c in crap:
                title = re.sub(c, '', title).strip()
            if crap:
                title= re.sub(r'[\(\)\[\]]', '', title).strip()

            pr = [x for x in self.pack_receipts if x in title]
            nott = title
            for x in pr:
                #logger.fdebug('removing %s from %s' % (x, title))
                try:
                    if x == 'TPB':
                        if gc_booktype is None:
                            gc_booktype = 'TPB'
                        tpb = True
                    # may have to put HC/GN/One_shot in here as well...
                    if 'Annual' in x:
                        annuals = True
                    if ' &' in x and title.rfind(x) <= len(title) + 3:
                        x = title[title.rfind(x):]
                    nt = nott.replace(x, '').strip()
                    #logger.fdebug('[%s] new nott: %s' % (x, nott))
                except Exception as e:
                    #logger.warn('error: %s' % e)
                    pass
                else:
                    nott = nt

            #logger.fdebug('title: %s' % title)
            #logger.fdebug('final nott: %s' % nott)
            if nott != title:
                series = re.sub('\s+', ' ', nott).strip()
                series = re.sub(r'[\(\)\[\]]', '', series).strip()
                title = re.sub('\s+', ' ', nott).strip()
                title = re.sub(r'[\(\)\[\]]', '', title).strip()
            else:
                series = re.sub('\s+', ' ', nott).strip()

            if pack is True:
                if year is not None:
                    title += ' (%s)' % year
                else:
                    title = '%s #%s (%s)' % (title, self.query['issue'], self.query['year'])
            else:
                title = series = filename
                #if all([year is not None, year not in title]):
                #    title += ' (%s)' % year
            #logger.fdebug('final title: %s' % (title))

            if volume_label:
                series = re.sub(volume_label, '', series, flags=re.I).strip()
                volume_label = re.sub('[^0-9]', '', volume_label).strip()

            if tpb and gc_booktype is None:
                gc_booktype = 'TPB'
            else:
                if gc_booktype is None:
                    gc_booktype = 'issue'

            logger.fdebug('title: %s' % title)
            logger.fdebug('series: %s' % series)
            logger.fdebug('filename: %s' % filename)
            logger.fdebug('year: %s' % year)
            logger.fdebug('pack: %s' % pack)
            logger.fdebug('tpb/gn/hc: %s' % tpb)
            if all([pack, tpb]):
                logger.fdebug('volumes: %s' % volume_issues)
            else:
                if volume_label:
                    logger.fdebug('volume: %s' % volume_label)
                if annuals:
                    logger.fdebug('annuals: %s' % annuals)
                logger.fdebug('issues: %s' % issues)

            return {'title': title,
                    'filename': filename,
                    'series': series,
                    'year': year,
                    'pack': pack,
                    'volume': volume_label,
                    'annuals': annuals,
                    'gc_booktype': gc_booktype,
                    'issues': issues}
        else:
            return None

    def pack_check(self, issues, packinfo):
        try:
            pack_numbers = packinfo['pack_numbers']
            issue_range = packinfo['pack_issuelist']['issue_range']
            ist = re.sub('#', '', issues).strip()
            iss = ist.find('-')
            first_iss = issues[:iss].strip()
            last_iss = issues[iss+1:].strip()
            if all([int(first_iss) in issue_range, int(last_iss) in issue_range]):
                logger.fdebug('first issue(%s) and last issue (%s) of ddl link fall within pack range of %s' % (first_iss, last_iss, pack_numbers))
                return True
        except Exception as e:
            pass

        return False

    def issue_list(self, pack):
        # packlist = [x.strip() for x in pack.split(',)]
        packlist = pack.replace('+', ' ').replace(',', ' ').split()
        #logger.fdebug(packlist)
        plist = []
        pack_issues = []
        for pl in packlist:
            if '-' in pl:
                plist.append(
                    list(
                        range(int(pl[: pl.find('-')]), int(pl[pl.find('-') + 1 :]) + 1)
                    )
                )
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
        logger.fdebug("pack_issues: %s" % pack_issues)


# if __name__ == '__main__':
#    ab = GC(sys.argv[1]) #'justice league aquaman') #sys.argv[0])
#    #c = ab.search()
#    b = ab.loadsite('test', sys.argv[2])
#    c = ab.parse_downloadresults('test', '60MB')
#    #c = ab.issue_list(sys.argv[2])
