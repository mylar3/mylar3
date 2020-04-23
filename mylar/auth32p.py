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

import urllib.request, urllib.error, urllib.parse
import json
import re
import time
import math
import datetime
import os
import requests
from bs4 import BeautifulSoup
from http.cookiejar import LWPCookieJar
import cfscrape

from operator import itemgetter

import mylar
from mylar import db, logger, filechecker, helpers, cv


class info32p(object):

    def __init__(self, reauthenticate=False, searchterm=None, test=False, smode=None):

        self.module = '[32P-AUTHENTICATION]'
        self.url = 'https://32pag.es/user.php?action=notify'
        self.headers = {'Content-type': 'application/x-www-form-urlencoded',
                        'Accept-Charset': 'utf-8',
                        'User-Agent': 'Mozilla/5.0'}
        self.mode = smode

        if test:
            self.username_32p = test['username']
            self.password_32p = test['password']
            self.test = True
        else:
            self.username_32p = mylar.CONFIG.USERNAME_32P
            self.password_32p = mylar.CONFIG.PASSWORD_32P
            self.test = False

        self.error = None
        self.method = None
        self.status = False
        self.status_msg = None
        self.auth = None

        if any([mylar.CONFIG.MODE_32P is True, self.test is True]):
            lses = self.LoginSession(self.username_32p, self.password_32p)
            loginses = lses.login()
            #logger.fdebug('lses return: %s' % loginses)
            if not loginses:
                self.status = False #return "disable"
                mylar.INKDROPS_32P = None
                if not self.test:
                    logger.error('%s [LOGIN FAILED] Disabling 32P provider until login error(s) can be fixed in order to avoid temporary bans.' % self.module)
                    self.status_msg = "disable"
                else:
                    if self.error:
                        self.status = False
                        self.status_msg = self.error
                    else:
                        self.status = False
                        self.status_msg = self.method
            else:
                if loginses['status'] == True:
                    logger.fdebug('%s [LOGIN SUCCESS] Now preparing for the use of 32P keyed authentication...' % self.module)
                    self.authkey = lses.authkey
                    self.passkey = lses.passkey
                    self.session = lses.ses
                    self.uid = lses.uid
                    self.status = True
                    try:
                        mylar.INKDROPS_32P = int(math.floor(float(lses.inkdrops['results'][0]['inkdrops'])))
                    except:
                        mylar.INKDROPS_32P = lses.inkdrops['results'][0]['inkdrops']
                else:
                    logger.fdebug('self.error: %s / self.method: %s' % (loginses['error'], loginses['method']))
                    self.status = False
                    mylar.INKDROPS_32P = None
                    if not self.test:
                        logger.error('%s [LOGIN FAILED] Disabling 32P provider until login error(s) can be fixed in order to avoid temporary bans.' % self.module)
                        self.status_msg = "disable"
                        if loginses['error']['message'][0] == 405 or 'Not Allowed' in loginses['error']['message'][1]:
                            self.error = 'site is down'
                        else:
                            self.error = cv.drophtml(loginses['error']['message'])
                        #self.error = loginses.error
                    else:
                        if self.error:
                            self.status = False
                            self.status_msg = self.error
                        else:
                            self.status = False
                            self.status_msg = self.method
        else:
            self.status = True
            self.session = requests.Session()
        self.reauthenticate = reauthenticate
        self.searchterm = searchterm
        self.publisher_list = {'Entertainment', 'Press', 'Comics', 'Publishing', 'Comix', 'Studios!'}

    def authenticate(self):

        if self.status is False:
            return {'status': self.status, 'status_msg': self.status_msg, 'inkdrops': mylar.INKDROPS_32P, 'error': self.error}

        if self.test:
            return {'status': True, 'inkdrops': mylar.INKDROPS_32P}

        logger.info('uid:%s / authkey:%s / passkey:%s' % (self.uid, self.authkey, self.passkey))
        if mylar.KEYS_32P is None:
            mylar.KEYS_32P = {'user': str(self.uid),
                              'auth': self.auth,
                              'passkey': str(self.passkey),
                              'authkey': str(self.authkey)}
        if self.mode == 'RSS':
            return self.rssfeed()
        else:
            return {'status': self.status, 'status_msg': self.status_msg, 'inkdrops': mylar.INKDROPS_32P, 'error': self.error}

    def callthesearch(self):
        if self.searchterm:
            logger.info('[32P] Successfully authenticated. Initiating search for : %s' % self.searchterm)
            return self.search32p(s)

    def rssfeed(self):
        feedinfo = []

        #if we've authenticated already via lses, we have the uid,authkey, passkeys.
        #if using legacy mode, we've already parsed the info into Mylar.KEYS32P
        try:
            if mylar.CONFIG.MODE_32P is True:
                #if authmode is enabled, attempt to signon and retrieve any custom notification feeds.
                # post to the login form
                r = self.session.post(self.url, verify=mylar.CONFIG.VERIFY_32P, allow_redirects=True)
                soup = BeautifulSoup(r.content, 'html.parser')
                soup.prettify()

                #logger.info('[32P] Successfully authenticated.')
                all_script2 = soup.find_all("link", {"rel": "alternate"})

                authfound = False
                logger.info('%s Attempting to integrate with all of your 32P Notification feeds.' % self.module)

                for al in all_script2:
                    alurl = al['href']
                    if all(['auth=' in alurl, 'torrents_notify' in alurl]) and not authfound:
                        #first we make sure we get the correct auth and store it.
                        f1 = alurl.find('auth=')
                        f2 = alurl.find('&', f1 + 1)
                        self.auth = alurl[f1 +5:f2]
                        if mylar.KEYS_32P['auth'] is None:
                            mylar.KEYS_32P['auth'] = self.auth
                        authfound = True

                    if 'torrents_notify' in alurl and ('torrents_notify_' + str(self.passkey)) not in alurl:
                        notifyname_st = alurl.find('name=')
                        notifyname_en = alurl.find('&', notifyname_st +1)
                        if notifyname_en == -1: notifyname_en = len(alurl)
                        notifyname = alurl[notifyname_st +5:notifyname_en]
                        notifynumber_st = alurl.find('torrents_notify_')
                        notifynumber_en = alurl.find('_', notifynumber_st +17)
                        notifynumber = alurl[notifynumber_st:notifynumber_en]
                        logger.fdebug('%s [NOTIFICATION: %s] Notification ID: %s' % (self.module, notifyname,notifynumber))

                        #generate the rss-url here
                        feedinfo.append({'feed':     notifynumber + '_' + str(self.passkey),
                                         'feedname': notifyname,
                                         'user':     str(self.uid),
                                         'auth':     self.auth,
                                         'passkey':  str(self.passkey),
                                         'authkey':  str(self.authkey)})

        except (requests.exceptions.Timeout, EnvironmentError) as e:
            logger.warn('Unable to retrieve information from 32Pages - either it is not responding/is down or something else is happening that is stopping me.')
            return {'status': False, 'status_msg': e}

        #set the keys here that will be used to download.
        #try:
        #    mylar.CONFIG.PASSKEY_32P = str(self.passkey)
        #    mylar.AUTHKEY_32P = str(self.authkey)  # probably not needed here.
        #    mylar.KEYS_32P = {}
        #    mylar.KEYS_32P = {"user": str(self.uid),
        #                      "auth": auth,
        #                      "passkey": str(self.passkey),
        #                      "authkey": str(self.authkey)}

        except NameError as e:
            logger.warn('Unable to retrieve information from 32Pages - either it is not responding/is down or something else is happening that is stopping me.')
            return {'status': False, 'status_msg': e}


        if self.reauthenticate:
            return {'status': True, 'status_msg': None, 'feedinfo': feedinfo}
        else:
            mylar.FEEDINFO_32P = feedinfo
            return {'status': True, 'status_msg': None, 'feedinfo': feedinfo}

    def searchit(self):
        if self.status is False:
            return {'status': self.status, 'status_msg': self.status_msg, 'results': "no results", 'error': self.error}

        chk_id = None
        #logger.info('searchterm: %s' % self.searchterm)
        #self.searchterm is a tuple containing series name, issue number, volume and publisher.
        series_search = self.searchterm['series']
        issue_search = self.searchterm['issue']
        volume_search = self.searchterm['volume']

        if series_search.startswith('0-Day Comics Pack'):
            #issue = '21' = WED, #volume='2' = 2nd month
            torrentid = 22247 #2018
            publisher_search = None #'2'  #2nd month
            comic_id = None
        elif all([self.searchterm['torrentid_32p'] is not None, self.searchterm['torrentid_32p'] != 'None']):
            torrentid = self.searchterm['torrentid_32p']
            comic_id = self.searchterm['id']
            publisher_search = self.searchterm['publisher']
        else:
            torrentid = None
            comic_id = self.searchterm['id']

            annualize = False
            if 'annual' in series_search.lower():
                series_search = re.sub(' annual', '', series_search.lower()).strip()
                annualize = True
            publisher_search = self.searchterm['publisher']
            spl = [x for x in self.publisher_list if x in publisher_search]
            for x in spl:
                publisher_search = re.sub(x, '', publisher_search).strip()
            #logger.info('publisher search set to : %s' % publisher_search)

            # lookup the ComicID in the 32p sqlite3 table to pull the series_id to use.
            if comic_id:
                chk_id = helpers.checkthe_id(comic_id)

            if any([chk_id is None, mylar.CONFIG.DEEP_SEARCH_32P is True]):
                #generate the dynamic name of the series here so we can match it up
                as_d = filechecker.FileChecker()
                as_dinfo = as_d.dynamic_replace(series_search)
                mod_series = re.sub('\|','', as_dinfo['mod_seriesname']).strip()
                as_puinfo = as_d.dynamic_replace(publisher_search)
                pub_series = as_puinfo['mod_seriesname']

                logger.fdebug('series_search: %s' % series_search)

                if '/' in series_search:
                    series_search = series_search[:series_search.find('/')]
                if ':' in series_search:
                    series_search = series_search[:series_search.find(':')]
                if ',' in series_search:
                    series_search = series_search[:series_search.find(',')]

                logger.fdebug('config.search_32p: %s' % mylar.CONFIG.SEARCH_32P)
                if mylar.CONFIG.SEARCH_32P is False:
                    url = 'https://walksoftly.itsaninja.party/serieslist.php'
                    params = {'series': re.sub('\|','', mod_series.lower()).strip()} #series_search}
                    logger.fdebug('search query: %s' % re.sub('\|', '', mod_series.lower()).strip())
                    try:
                        t = requests.get(url, params=params, verify=True, headers={'USER-AGENT': mylar.USER_AGENT[:mylar.USER_AGENT.find('/')+7] + mylar.USER_AGENT[mylar.USER_AGENT.find('(')+1]})
                    except requests.exceptions.RequestException as e:
                        logger.warn(e)
                        return {'status': self.status, 'status_msg': self.status_msg, 'results': "no results", 'error': self.error}

                    if t.status_code == '619':
                        logger.warn('[%s] Unable to retrieve data from site.' % t.status_code)
                        return {'status': self.status, 'status_msg': self.status_msg, 'results': "no results", 'error': self.error}
                    elif t.status_code == '999':
                        logger.warn('[%s] No series title was provided to the search query.' % t.status_code)
                        return {'status': self.status, 'status_msg': self.status_msg, 'results': "no results", 'error': self.error}

                    try:
                        results = t.json()
                    except:
                        results = t.text

                    if len(results) == 0:
                        logger.warn('No results found for search on 32P.')
                        return {'status': self.status, 'status_msg': self.status_msg, 'results': "no results", 'error': self.error}

#        with cfscrape.create_scraper(delay=15) as s:
#            s.headers = self.headers
#            cj = LWPCookieJar(os.path.join(mylar.CONFIG.SECURE_DIR, ".32p_cookies.dat"))
#            cj.load()
#            s.cookies = cj
        data = []
        pdata = []
        pubmatch = False

        if any([series_search.startswith('0-Day Comics Pack'), torrentid is not None]):
            data.append({"id":      torrentid,
                         "series":  series_search})
        else:
            if any([not chk_id, mylar.CONFIG.DEEP_SEARCH_32P is True]):
                if mylar.CONFIG.SEARCH_32P is True:
                    url = 'https://32pag.es/torrents.php' #?action=serieslist&filter=' + series_search #&filter=F
                    params = {'action': 'serieslist', 'filter': series_search}
                    time.sleep(1)  #just to make sure we don't hammer, 1s pause.
                    t = self.session.get(url, params=params, verify=True, allow_redirects=True)
                    soup = BeautifulSoup(t.content, "html.parser")
                    results = soup.find_all("a", {"class":"object-qtip"},{"data-type":"torrentgroup"})

                for r in results:
                    if mylar.CONFIG.SEARCH_32P is True:
                        torrentid = r['data-id']
                        torrentname = r.findNext(text=True)
                        torrentname = torrentname.strip()
                    else:
                        torrentid = r['id']
                        torrentname = r['series']

                    as_d = filechecker.FileChecker()
                    as_dinfo = as_d.dynamic_replace(torrentname)
                    seriesresult = re.sub('\|','', as_dinfo['mod_seriesname']).strip()
                    logger.fdebug('searchresult: %s --- %s [%s]' % (seriesresult, mod_series, publisher_search))
                    if seriesresult.lower() == mod_series.lower():
                        logger.fdebug('[MATCH] %s [%s]' % (torrentname, torrentid))
                        data.append({"id":      torrentid,
                                     "series":  torrentname})
                    elif publisher_search.lower() in seriesresult.lower():
                        logger.fdebug('[MATCH] Publisher match.')
                        tmp_torrentname = re.sub(publisher_search.lower(), '', seriesresult.lower()).strip()
                        as_t = filechecker.FileChecker()
                        as_tinfo = as_t.dynamic_replace(tmp_torrentname)
                        if re.sub('\|', '', as_tinfo['mod_seriesname']).strip() == mod_series.lower():
                            logger.fdebug('[MATCH] %s [%s]' % (torrentname, torrentid))
                            pdata.append({"id":      torrentid,
                                          "series":  torrentname})
                            pubmatch = True

                logger.fdebug('%s series listed for searching that match.' % len(data))
            else:
                logger.fdebug('Exact series ID already discovered previously. Setting to : %s [%s]' % (chk_id['series'], chk_id['id']))
                pdata.append({"id":     chk_id['id'],
                              "series": chk_id['series']})
                pubmatch = True

        if all([len(data) == 0, len(pdata) == 0]):
            return {'status': self.status, 'status_msg': self.status_msg, 'results': "no results", 'error': self.error}
        else:
            dataset = []
            if len(data) > 0:
                dataset += data
            if len(pdata) > 0:
                dataset += pdata
            logger.fdebug(str(len(dataset)) + ' series match the tile being searched for on 32P...')

        if all([chk_id is None, not series_search.startswith('0-Day Comics Pack'), self.searchterm['torrentid_32p'] is not None, self.searchterm['torrentid_32p'] != 'None']) and any([len(data) == 1, len(pdata) == 1]):
            #update the 32p_reference so we avoid doing a url lookup next time
            helpers.checkthe_id(comic_id, dataset)
        else:
            if all([not series_search.startswith('0-Day Comics Pack'), self.searchterm['torrentid_32p'] is not None, self.searchterm['torrentid_32p'] != 'None']):
                pass
            else:
                logger.debug('Unable to properly verify reference on 32P - will update the 32P reference point once the issue has been successfully matched against.')

        results32p = []
        resultlist = {}

        for x in dataset:
            #for 0-day packs, issue=week#, volume=month, id=0-day year pack (ie.issue=21&volume=2 for feb.21st)
            payload = {"action": "groupsearch",
                       "id":     x['id'], #searchid,
                       "issue":  issue_search}
            #in order to match up against 0-day stuff, volume has to be none at this point
            #when doing other searches tho, this should be allowed to go through
            #if all([volume_search != 'None', volume_search is not None]):
            #    payload.update({'volume': re.sub('v', '', volume_search).strip()})
            if series_search.startswith('0-Day Comics Pack'):
                payload.update({"volume": volume_search})

            payload = json.dumps(payload)
            payload = json.loads(payload)

            logger.fdebug('payload: %s' % payload)
            url = 'https://32pag.es/ajax.php'
            time.sleep(1)  #just to make sure we don't hammer, 1s pause.
            try:
                d = self.session.get(url, params=payload, verify=True, allow_redirects=True)
            except Exception as e:
                logger.error('%s [%s] Could not POST URL %s' % (self.module, e, url))

            try:
                searchResults = d.json()
            except Exception as e:
                searchResults = d.text
                logger.debug('[%s] %s Search Result did not return valid JSON, falling back on text: %s' % (e, self.module, searchResults.text))
                return False

            if searchResults['status'] == 'success' and searchResults['count'] > 0:
                logger.fdebug('successfully retrieved %s search results' % searchResults['count'])
                for a in searchResults['details']:
                    if series_search.startswith('0-Day Comics Pack'):
                        title = series_search
                    else:
                        title = self.searchterm['series'] + ' v' + a['volume'] + ' #' + a['issues']
                    results32p.append({'link':      a['id'],
                                       'title':     title,
                                       'filesize':  a['size'],
                                       'issues':     a['issues'],
                                       'pack':      a['pack'],
                                       'format':    a['format'],
                                       'language':  a['language'],
                                       'seeders':   a['seeders'],
                                       'leechers':  a['leechers'],
                                       'scanner':   a['scanner'],
                                       'chkit':     {'id': x['id'], 'series': x['series']},
                                       'pubdate':   datetime.datetime.fromtimestamp(float(a['upload_time'])).strftime('%a, %d %b %Y %H:%M:%S'),
                                       'int_pubdate': float(a['upload_time'])})

            else:
                logger.fdebug('32P did not return any valid search results.')

        if len(results32p) > 0:
            resultlist['entries'] = sorted(results32p, key=itemgetter('pack','title'), reverse=False)
            logger.debug('%s Resultslist: %s' % (self.module, resultlist))
        else:
            resultlist = 'no results'

        return {'status': self.status, 'status_msg': self.status_msg, 'results': resultlist, 'error': self.error}

    def downloadfile(self, payload, filepath):
        if self.status is False:
            return {'status': self.status, 'status_msg': self.status_msg, 'download_bool': False, 'error': self.error}

        url = 'https://32pag.es/torrents.php'
        try:
            r = self.session.get(url, params=payload, verify=True, stream=True, allow_redirects=True)
        except Exception as e:
            logger.error('%s [%s] Could not POST URL %s' % ('[32P-DOWNLOADER]', e, url))
            return {'status': self.status, 'status_msg': self.status_msg, 'download_bool': False}

        if str(r.status_code) != '200':
            logger.warn('Unable to download torrent from 32P [Status Code returned: %s]' % r.status_code)
            if str(r.status_code) == '404':
                logger.warn('[32P-CACHED_ENTRY] Entry found in 32P cache - incorrect. Torrent has probably been merged into a pack, or another series id. Removing from cache.')
                self.delete_cache_entry(payload['id'])
            else:
                logger.fdebug('content: %s' % r.content)
            return {'status': self.status, 'status_msg': self.status_msg, 'download_bool': False, 'error': self.error}


        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()

        return {'status': True, 'status_msg': self.status_msg, 'download_bool': True }

    def delete_cache_entry(self, id):
        myDB = db.DBConnection()
        myDB.action("DELETE FROM rssdb WHERE link=? AND Site='32P'", [id])

    class LoginSession(object):
        def __init__(self, un, pw, session_path=None):
            '''
                Params:
                    un: account username (required)
                    pw: account password (required)
                    session_path: the path to the actual file you want to persist your cookies in
                                If blank, saves to $HOME/.32p_cookies.dat

            '''
            self.module = '[32P-AUTHENTICATION]'
            try:
                self.ses = cfscrape.create_scraper(delay=15)
            except Exception as e:
                logger.error('%s Can\'t create session with cfscrape' % self.module)

            self.session_path = session_path if session_path is not None else os.path.join(mylar.CONFIG.SECURE_DIR, ".32p_cookies.dat")
            self.ses.cookies = LWPCookieJar(self.session_path)
            if not os.path.exists(self.session_path):
                logger.fdebug('%s Session cookie does not exist. Signing in and Creating.' % self.module)
                self.ses.cookies.save()
            else:
                logger.fdebug('%s Session cookie found. Attempting to load...' % self.module)
                self.ses.cookies.load(ignore_discard=True)
            self.un = un
            self.pw = pw
            self.authkey = None
            self.passkey = None
            self.uid = None
            self.inkdrops = None
            self.error = None
            self.method = None

        def cookie_exists(self, name):
            '''
                Checks if cookie <name> exists in self.ses.cookies
                Beware - this doesn't match domain, so only use this method on one domain
            '''

            for ci in self.ses.cookies:
                if (ci.name == name):
                    return True
            return False

        def cookie_value(self, name, default=None):
            '''
                Returns the value of the cookie name, returning default if it doesn't exist.
                Beware - this doesn't match domain too, so only use this method on one domain
            '''
            for ci in self.ses.cookies:
                if (ci.name == name):
                    return ci.value

            return default

        def valid_skey_attempt(self, skey):
            '''
                Not generally the proper method to call - call test_key_valid()
                instead - which calls this method.

                Attempts to fetch data via an ajax method that will fail if not
                authorized.  The parameter skey should be set to the string
                value of the cookie named session.

                Returns: True on success, False on failure.  Side Effects: Sets
                self.uid, self,authkey and self.passkey
            '''

            u = '''https://32pag.es/ajax.php'''
            params = {'action': 'index'}
            testcookie = dict(session=skey)

            try:
                r = self.ses.get(u, params=params, timeout=60, allow_redirects=False, cookies=testcookie)
            except Exception as e:
                logger.error('Got an exception [%s] trying to GET to: %s' % (e,u))
                self.error = {'status':'error', 'message':'exception trying to retrieve site'}
                return False

            if r.status_code != 200:
                if r.status_code == 302:
                    newloc = r.headers.get('Location', '')
                    logger.warn('Got redirect from the POST-ajax action=login GET: %s' % newloc)
                    self.error = {'status':'redirect-error', 'message':'got redirect from POST-ajax login action : ' + newloc}
                else:
                    logger.error('Got bad status code in the POST-ajax action=login GET: %s' % r.status_code)
                    self.error = {'status':'bad status code', 'message':'bad status code received in the POST-ajax login action :' + str(r.status_code)}
                return False

            try:
                j = r.json()
            except:
                logger.warn('Error - response from session-based skey check was not JSON: %s' % r.text)
                return False

            self.uid = j['response']['id']
            self.authkey = j['response']['authkey']
            self.passkey = pk = j['response']['passkey']

            try:
                d = self.ses.get('https://32pag.es/ajax.php', params={'action': 'user_inkdrops'}, verify=True, allow_redirects=True)
            except Exception as e:
                logger.error('Unable to retreive Inkdrop total : %s' % e)
            else:
                try:
                    self.inkdrops = d.json()
                except:
                    logger.error('Inkdrop result did not return valid JSON, unable to verify response')
                else:
                    logger.fdebug('inkdrops: %s' % self.inkdrops)

            return True

        def valid_login_attempt(self, un, pw):
            '''
                Does the actual POST to the login.php method (using the ajax parameter, which is far more reliable
                than HTML parsing.

                Input: un: The username (usually would be self.un, but that's not a requirement
                       pw: The password (usually self.pw but not a requirement)

                Note: The underlying self.ses object will handle setting the session cookie from a valid login,
                but you'll need to call the save method if your cookies are being persisted.

                Returns: True (success) False (failure)

            '''

            postdata = {'username': un, 'password': pw, 'keeplogged': 1}
            u = 'https://32pag.es/login.php?ajax=1'

            try:
                r = self.ses.post(u, data=postdata, timeout=60, allow_redirects=True)
                logger.debug('%s Status Code: %s' % (self.module, r.status_code))
            except Exception as e:
                logger.error('%s Got an exception when trying to login: %s' % (self.module, e))
                self.error = {'status':'exception', 'message':'Exception when trying to login'}
                return False

            if r.status_code != 200:
                logger.warn('%s Got bad status code from login POST: %d\n%s\n%s' % (self.module, r.status_code, r.text, r.headers))
                logger.debug('%s Request URL: %s \n Content: %s \n History: %s' % (self.module, r.url ,r.text, r.history))
                self.error = {'status':'Bad Status code', 'message':(r.status_code, r.text, r.headers)}
                return False

            try:
                logger.debug('%s Trying to analyze login JSON reply from 32P: %s' % (self.module, r.text))
                d = r.json()
            except:
                logger.debug('%s Request URL: %s \n Content: %s \n History: %s' % (self.module, r.url ,r.text, r.history))
                logger.error('%s The data returned by the login page was not JSON: %s' % (self.module, r.text))
                self.error = {'status':'JSON not returned', 'message':r.text}
                return False

            if d['status'] == 'success':
                return True

            logger.error('%s Got unexpected status result: %s' % (self.module, d))
            logger.debug('%s Request URL: %s \n Content: %s \n History: %s \n Json: %s' % (self.module, r.url ,r.text, r.history, d))
            self.error = d
            return False

        def test_skey_valid(self, skey=None):
            '''
                You should call this method to test if the specified session key
                (skey) is still valid.  If skey is left out or None, it
                automatically gets the value of the session cookie currently
                set.


                Returns:  True (success) False (failure)
                          Side effects: Saves the cookies file.

            '''

            if skey is None:
                skey = self.cookie_value('session', '')

            if skey is None or skey == '':
                return False

            if (self.valid_skey_attempt(skey)):
                self.ses.cookies.save(ignore_discard=True)
                return True

            self.ses.cookies.save(ignore_discard=True)
            return False

        def test_login(self):
            '''
               This is the method to call if you JUST want to login using self.un & self.pw

                Note that this will generate a new session on 32pag.es every time you login successfully!
                This is why the "keeplogged" option is only for when you persist cookies to disk.

                Note that after a successful login, it will test the session key, which has the side effect of
                getting the authkey,passkey & uid

                Returns: True (login success) False (login failure)
                Side Effects: On success: Sets the authkey, uid, passkey and saves the cookies to disk
                         (on failure): clears the cookies and saves that to disk.
            '''
            if (self.valid_login_attempt(self.un, self.pw)):
                if self.cookie_exists('session'):
                    self.ses.cookies.save(ignore_discard=True)
                    if (not self.test_skey_valid()):
                        logger.error('Bad error: The attempt to get your attributes after successful login failed!')
                        self.error = {'status': 'Bad error', 'message': 'Attempt to get attributes after successful login failed.'}
                        return False
                    return True

                logger.warn('Missing session cookie after successful login: %s' % self.ses.cookies)
            self.ses.cookies.clear()
            self.ses.cookies.save()
            return False


        def login(self):
            '''
                This is generally the only method you'll want to call, as it handles testing test_skey_valid() before
                trying test_login().

                Returns: True (success) / False (failure)
                Side effects: Methods called will handle saving the cookies to disk, and setting
                              self.authkey, self.passkey, and self.uid
            '''
            if (self.test_skey_valid()):
                logger.fdebug('%s Session key-based login was good.' % self.module)
                self.method = 'Session Cookie retrieved OK.'
                return {'ses': self.ses,
                        'status': True,
                        'error': self.error,
                        'method': self.method,
                        'uid': self.uid,
                        'authkey': self.authkey,
                        'passkey': self.passkey}

            if (self.test_login()):
                logger.fdebug('%s Credential-based login was good.' % self.module)
                self.method = 'Credential-based login OK.'
                return {'ses': self.ses,
                        'status': True,
                        'error': self.error,
                        'method': self.method,
                        'uid': self.uid,
                        'authkey': self.authkey,
                        'passkey': self.passkey}

            logger.warn('%s Both session key and credential-based logins failed.' % self.module)
            self.method = 'Both session key & credential login failed.'
            return {'ses': self.ses,
                    'status': False,
                    'error': self.error,
                    'method': self.method,
                    'uid': self.uid,
                    'authkey': self.authkey,
                    'passkey': self.passkey}



#if __name__ == '__main__':
#   ab = DoIt()
#    c = ab.loadit()

