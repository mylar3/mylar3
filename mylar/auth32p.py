import urllib2
import re
import time
import datetime
import os
import lib.requests as requests
from bs4 import BeautifulSoup
from cookielib import LWPCookieJar

from operator import itemgetter

import mylar
from mylar import logger, filechecker


class info32p(object):

    def __init__(self, reauthenticate=False, searchterm=None, test=False):

        self.module = '[32P-AUTHENTICATION]'
        self.url = 'https://32pag.es/user.php?action=notify'
        self.headers = {'Content-type': 'application/x-www-form-urlencoded',
                        'Accept-Charset': 'utf-8',
                        'User-Agent': 'Mozilla/5.0'}

        self.error = None
        self.method = None
        lses = self.LoginSession(mylar.USERNAME_32P, mylar.PASSWORD_32P)

        if not lses.login():
            if not self.test:
                logger.error(self.module + ' [LOGIN FAILED] Disabling 32P provider until login error(s) can be fixed in order to avoid temporary bans.')
                return "disable"
            else:
                if self.error:
                    return self.error #rtnmsg
                else:
                    return self.method
        else:
            logger.info(self.module + '[LOGIN SUCCESS] Now preparing for the use of 32P keyed authentication...')
            self.authkey = lses.authkey
            self.passkey = lses.passkey
            self.uid = lses.uid
         
        self.reauthenticate = reauthenticate
        self.searchterm = searchterm
        self.test = test
        self.publisher_list = {'Entertainment', 'Press', 'Comics', 'Publishing', 'Comix', 'Studios!'}

    def authenticate(self):

        feedinfo = []

        try:
            with requests.Session() as s:
                s.headers = self.headers
                cj = LWPCookieJar(os.path.join(mylar.CACHE_DIR, ".32p_cookies.dat"))
                cj.load()
                s.cookies = cj

                if mylar.VERIFY_32P == 1 or mylar.VERIFY_32P == True:
                    verify = True
                else:
                    verify = False

                logger.fdebug('[32P] Verify SSL set to : ' + str(verify))

                if not verify:
                #32P throws back an insecure warning because it can't validate against the CA. The below suppresses the message just for 32P instead of being displa$
                    from lib.requests.packages.urllib3.exceptions import InsecureRequestWarning
                    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

                # post to the login form
                r = s.post(self.url, verify=verify)

                #need a way to find response code (200=OK), but returns 200 for everything even failed signons (returns a blank page)
                #logger.info('[32P] response: ' + str(r.content))
                soup = BeautifulSoup(r.content)
                soup.prettify()

                if self.searchterm:
                    logger.info('[32P] Successfully authenticated. Initiating search for : ' + self.searchterm)
                    return self.search32p(s)

                logger.info('[32P] Successfully authenticated.')
                all_script = soup.find_all("script", {"src": False})
                all_script2 = soup.find_all("link", {"rel": "alternate"})

                authfound = False
                logger.info(self.module + ' Atttempting to integrate with all of your 32P Notification feeds.')

                #get inkdrop count ...
                #user_info = soup.find_all(attrs={"class": "stat"})
                #inkdrops = user_info[0]['title']
                #logger.info('INKDROPS: ' + str(inkdrops))

                for al in all_script2:
                    alurl = al['href']
                    if 'auth=' in alurl and 'torrents_notify' in alurl and not authfound:
                        f1 = alurl.find('auth=')
                        f2 = alurl.find('&', f1 + 1)
                        auth = alurl[f1 +5:f2]
                        authfound = True
                        #logger.fdebug(self.module + ' Auth:' + str(auth))
                        #p1 = alurl.find('passkey=')
                        #p2 = alurl.find('&', p1 + 1)
                        #passkey = alurl[p1 +8:p2]
                        #logger.fdebug(self.module + ' Passkey:' + str(passkey))
                        if self.reauthenticate: break

                    if 'torrents_notify' in alurl and ('torrents_notify_' + str(self.passkey)) not in alurl:
                        notifyname_st = alurl.find('name=')
                        notifyname_en = alurl.find('&', notifyname_st +1)
                        if notifyname_en == -1: notifyname_en = len(alurl)
                        notifyname = alurl[notifyname_st +5:notifyname_en]
                        notifynumber_st = alurl.find('torrents_notify_')
                        notifynumber_en = alurl.find('_', notifynumber_st +17)
                        notifynumber = alurl[notifynumber_st:notifynumber_en]
                        logger.fdebug(self.module + ' [NOTIFICATION: ' + str(notifyname) + '] Notification ID: ' + str(notifynumber))

                        #generate the rss-url here
                        feedinfo.append({'feed':     notifynumber + '_' + str(self.passkey),
                                         'feedname': notifyname,
                                         'user':     str(self.uid),
                                         'auth':     auth,
                                         'passkey':  str(self.passkey),
                                         'authkey':  str(self.authkey)})

        except (requests.exceptions.Timeout, EnvironmentError):
            logger.warn('Unable to retrieve information from 32Pages - either it is not responding/is down or something else is happening that is stopping me.')
            return

        #set the keys here that will be used to download.
        try:
            mylar.PASSKEY_32P = str(self.passkey)
            mylar.AUTHKEY_32P = str(self.authkey)  # probably not needed here.
            mylar.KEYS_32P = {}
            mylar.KEYS_32P = {"user": str(self.uid),
                              "auth": auth,
                              "passkey": str(self.passkey),
                              "authkey": str(self.authkey)}
        except NameError:
            logger.warn('Unable to retrieve information from 32Pages - either it is not responding/is down or something else is happening that is stopping me.')
            return
           
        if self.reauthenticate:
            return
        else:
            mylar.FEEDINFO_32P = feedinfo
            return feedinfo

    def searchit(self):
        with requests.Session() as s:
            #self.searchterm is a tuple containing series name, issue number, volume and publisher.
            series_search = self.searchterm['series']
            annualize = False
            if 'Annual' in series_search:
                series_search = re.sub(' Annual', '', series_search).strip()
                annualize = True
            issue_search = self.searchterm['issue']
            volume_search = self.searchterm['volume']
            publisher_search = self.searchterm['publisher']
            spl = [x for x in self.publisher_list if x in publisher_search]
            for x in spl:
                publisher_search = re.sub(x, '', publisher_search).strip()

            logger.info('publisher search set to : ' + publisher_search)
            #generate the dynamic name of the series here so we can match it up
            as_d = filechecker.FileChecker()
            as_dinfo = as_d.dynamic_replace(series_search)
            mod_series = as_dinfo['mod_seriesname']
            as_puinfo = as_d.dynamic_replace(publisher_search)
            pub_series = as_puinfo['mod_seriesname']

            logger.info('series_search: ' + series_search)

            if '/' in series_search:
                series_search = series_search[:series_search.find('/')]
            if ':' in series_search:
                series_search = series_search[:series_search.find(':')]
            if ',' in series_search:
                series_search = series_search[:series_search.find(',')]

            url = 'https://32pag.es/torrents.php' #?action=serieslist&filter=' + series_search #&filter=F
            params = {'action': 'serieslist', 'filter': series_search}
            s.headers = self.headers
            cj = LWPCookieJar(os.path.join(mylar.CACHE_DIR, ".32p_cookies.dat"))
            cj.load()
            s.cookies = cj
            time.sleep(1)  #just to make sure we don't hammer, 1s pause.
            t = s.get(url, params=params, verify=True)
            soup = BeautifulSoup(t.content)
            results = soup.find_all("a", {"class":"object-qtip"},{"data-type":"torrentgroup"})

            data = []
            pdata = []
            pubmatch = False

            for r in results:
                torrentid = r['data-id']
                torrentname = r.findNext(text=True)
                torrentname = torrentname.strip()
                as_d = filechecker.FileChecker()
                as_dinfo = as_d.dynamic_replace(torrentname)
                seriesresult = as_dinfo['mod_seriesname']
                logger.info('searchresult: ' + seriesresult + ' --- ' + mod_series + '[' + publisher_search + ']')
                if seriesresult == mod_series:
                    logger.info('[MATCH] ' + torrentname + ' [' + str(torrentid) + ']')
                    data.append({"id":      torrentid,
                                 "series":  torrentname})
                elif publisher_search in seriesresult:
                    tmp_torrentname = re.sub(publisher_search, '', seriesresult).strip()
                    as_t = filechecker.FileChecker()
                    as_tinfo = as_t.dynamic_replace(tmp_torrentname)
                    if as_tinfo['mod_seriesname'] == mod_series:
                        logger.info('[MATCH] ' + torrentname + ' [' + str(torrentid) + ']')
                        pdata.append({"id":      torrentid,
                                     "series":  torrentname})
                        pubmatch = True

            logger.info(str(len(data)) + ' series listed for searching that match.')

            if len(data) == 1 or len(pdata) == 1:
                logger.info(str(len(data)) + ' series match the title being search for')
                if len(pdata) == 1:
                    dataset = pdata[0]['id']
                else:
                    dataset = data[0]['id']

                payload = {'action': 'groupsearch',
                           'id':     dataset,
                           'issue':  issue_search}
                #in order to match up against 0-day stuff, volume has to be none at this point
                #when doing other searches tho, this should be allowed to go through
                #if all([volume_search != 'None', volume_search is not None]):
                #    payload.update({'volume': re.sub('v', '', volume_search).strip()})

                logger.info('payload: ' + str(payload))
                url = 'https://32pag.es/ajax.php'

                time.sleep(1)  #just to make sure we don't hammer, 1s pause.
                d = s.get(url, params=payload, verify=True)

                results32p = []
                resultlist = {}
                try:
                    searchResults = d.json()
                except:
                    searchResults = d.text
                if searchResults['status'] == 'success' and searchResults['count'] > 0:
                    logger.info('successfully retrieved ' + str(searchResults['count']) + ' search results.')
                    for a in searchResults['details']:
                        results32p.append({'link':      a['id'],
                                           'title':     self.searchterm['series'] + ' v' + a['volume'] + ' #' + a['issues'],
                                           'filesize':  a['size'],
                                           'issues':     a['issues'],
                                           'pack':      a['pack'],
                                           'format':    a['format'],
                                           'language':  a['language'],
                                           'seeders':   a['seeders'],
                                           'leechers':  a['leechers'],
                                           'scanner':   a['scanner'],
                                           'pubdate':   datetime.datetime.fromtimestamp(float(a['upload_time'])).strftime('%c')})
                    
                    resultlist['entries'] = sorted(results32p, key=itemgetter('pack','title'), reverse=False)
                else:
                    resultlist = 'no results'
            else:
                resultlist = 'no results'

        return resultlist

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
            self.ses = requests.Session()
            self.session_path = session_path if session_path is not None else os.path.join(mylar.CACHE_DIR, ".32p_cookies.dat")
            self.ses.cookies = LWPCookieJar(self.session_path)
            if not os.path.exists(self.session_path):
                logger.fdebug(self.module + ' Session cookie does not exist. Signing in and Creating.')
                self.ses.cookies.save()
            else:
                logger.fdebug(self.module + ' Session cookie found. Attempting to load...')
                self.ses.cookies.load(ignore_discard=True)
            self.un = un
            self.pw = pw
            self.authkey = None
            self.passkey = None
            self.uid = None

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
                logger.error("Got an exception trying to GET from to:" + u)
                self.error = {'status':'error', 'message':'exception trying to retrieve site'}
                return False

            if r.status_code != 200:
                if r.status_code == 302:
                    newloc = r.headers.get('location', '')
                    logger.warn("Got redirect from the POST-ajax action=login GET:" + newloc)
                    self.error = {'status':'redirect-error', 'message':'got redirect from POST-ajax login action : ' + newloc}
                else:
                    logger.error("Got bad status code in the POST-ajax action=login GET:" + str(r.status_code))
                    self.error = {'status':'bad status code', 'message':'bad status code received in the POST-ajax login action :' + str(r.status_code)}
                return False

            try:
                j = r.json()
            except:
                logger.warn("Error - response from session-based skey check was not JSON: %s",r.text)
                return False

            #logger.info(j)
            self.uid = j['response']['id']
            self.authkey = j['response']['authkey']
            self.passkey = pk = j['response']['passkey']
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
                r = self.ses.post(u, data=postdata, timeout=60, allow_redirects=False)
            except Exception as e:
                logger.error("Got an exception when trying to login to %s POST", u)
                self.error = {'status':'exception', 'message':'Exception when trying to login'}
                return False

            if r.status_code != 200:
                logger.warn("Got bad status code from login POST: %d\n%s\n%s", r.status_code, r.text, r.headers)
                self.error = {'status':'Bad Status code', 'message':(r.status_code, r.text, r.headers)}
                return False

            try:
                d = r.json()
            except:
                logger.error("The data returned by the login page was not JSON: %s", r.text)
                self.error = {'status':'JSON not returned', 'message':r.text}
                return False

            if d['status'] == 'success':
                return True

            logger.error("Got unexpected status result: %s", d)
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

            self.ses.cookies.save(ignore_discard=true)
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
                        logger.error("Bad error: The attempt to get your attributes after successful login failed!")
                        self.error = {'status': 'Bad error', 'message': 'Attempt to get attributes after successful login failed.'}
                        return False
                    return True

                logger.warn("Missing session cookie after successful login: %s", self.ses.cookies)
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
                logger.fdebug(self.module + ' Session key-based login was good.')
                self.method = 'Session Cookie retrieved OK.'
                return True

            if (self.test_login()):
                logger.fdebug(self.module + ' Credential-based login was good.')
                self.method = 'Session Cookie retrieved OK.'
                return True

            logger.warn(self.module + ' Both session key and credential-based logins failed.')
            self.method = 'Failed to retrieve Session Cookie.'
            return False


#if __name__ == '__main__':
#   ab = DoIt()
#    c = ab.loadit()

