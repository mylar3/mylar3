import urllib2
import lib.requests as requests
import re
from bs4 import BeautifulSoup
import mylar
from mylar import logger


class info32p(object):

    def __init__(self, reauthenticate=False, searchterm=None):

        self.module = '[32P-AUTHENTICATION]'
        self.url = 'https://32pag.es/login.php'
        self.payload = {'username': mylar.USERNAME_32P,
                        'password': mylar.PASSWORD_32P}
        self.headers = {'Content-type': 'application/x-www-form-urlencoded',
                        'Accept-Charset': 'utf-8',
                        'User-Agent': 'Mozilla/5.0'}
        self.reauthenticate = reauthenticate
        self.searchterm = searchterm

    def authenticate(self):

        feedinfo = []

        try:
            with requests.session() as s:
                if mylar.VERIFY_32P == 1 or mylar.VERIFY_32P == True:
                    verify = True
                else:
                    verify = False

                logger.fdebug('[32P] Verify SSL set to : ' + str(verify))

                if not verify:
                #32P throws back an insecure warning because it can't validate against the CA. The below suppresses the message just for 32P instead of being displa$
                    from lib.requests.packages.urllib3.exceptions import InsecureRequestWarning
                    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


                # fetch the login page

                s.headers = self.headers
                try:
                    s.get(self.url, verify=verify, timeout=30)
                except (requests.exceptions.SSLError, requests.exceptions.Timeout) as e:
                    logger.error(self.module + ' Unable to establish connection to 32P: ' + str(e))
                    return
                    
                # post to the login form
                r = s.post(self.url, data=self.payload, verify=verify)

                #need a way to find response code (200=OK), but returns 200 for everything even failed signons (returns a blank page)
                #logger.info('[32P] response: ' + str(r.content))
                soup = BeautifulSoup(r.content)
                soup.prettify()
                #check for invalid username/password and if it's invalid - disable provider so we don't autoban (manual intervention is required after).
                chk_login = soup.find_all("form", {"id":"loginform"})
                for ck in chk_login:
                    errorlog = ck.find("span", {"id":"formerror"})
                    loginerror = " ".join(list(errorlog.stripped_strings)) #login_error.findNext(text=True)
                    errornot = ck.find("span", {"class":"notice"})
                    noticeerror = " ".join(list(errornot.stripped_strings)) #notice_error.findNext(text=True)
                    logger.error(self.module + ' Error: ' + loginerror)
                    if noticeerror:
                        logger.error(self.module + ' Warning: ' + noticeerror)
                    logger.error(self.module + ' Disabling 32P provider until username/password can be corrected / verified.')
                    return "disable"


                if not self.searchterm:
                    logger.info('[32P] Successfully authenticated. Verifying authentication & passkeys for usage.')
                else:
                    logger.info('[32P] Successfully authenticated. Initiating search for : ' + self.searchterm)
                    return self.search32p(s)
                
                all_script = soup.find_all("script", {"src": False})
                all_script2 = soup.find_all("link", {"rel": "alternate"})

                for ind_s in all_script:
                    all_value = str(ind_s)
                    all_items = all_value.split()
                    auth_found = False
                    user_found = False
                    for al in all_items:
                        if al == 'authkey':
                            auth_found = True
                        elif auth_found == True and al != '=':
                            authkey = re.sub('["/;]', '', al).strip()
                            auth_found = False
                            logger.fdebug(self.module + ' Authkey found: ' + str(authkey))
                        if al == 'userid':
                            user_found = True
                        elif user_found == True and al != '=':
                            userid = re.sub('["/;]', '', al).strip()
                            user_found = False
                            logger.fdebug(self.module + ' Userid found: ' + str(userid))

                authfound = False
                logger.info(self.module + ' Atttempting to integrate with all of your 32P Notification feeds.')

                for al in all_script2:
                    alurl = al['href']
                    if 'auth=' in alurl and 'torrents_notify' in alurl and not authfound:
                        f1 = alurl.find('auth=')
                        f2 = alurl.find('&', f1 + 1)
                        auth = alurl[f1 +5:f2]
                        logger.fdebug(self.module + ' Auth:' + str(auth))
                        authfound = True
                        p1 = alurl.find('passkey=')
                        p2 = alurl.find('&', p1 + 1)
                        passkey = alurl[p1 +8:p2]
                        logger.fdebug(self.module + ' Passkey:' + str(passkey))
                        if self.reauthenticate: break

                    if 'torrents_notify' in alurl and ('torrents_notify_' + str(passkey)) not in alurl:
                        notifyname_st = alurl.find('name=')
                        notifyname_en = alurl.find('&', notifyname_st +1)
                        if notifyname_en == -1: notifyname_en = len(alurl)
                        notifyname = alurl[notifyname_st +5:notifyname_en]
                        notifynumber_st = alurl.find('torrents_notify_')
                        notifynumber_en = alurl.find('_', notifynumber_st +17)
                        notifynumber = alurl[notifynumber_st:notifynumber_en]
                        logger.fdebug(self.module + ' [NOTIFICATION: ' + str(notifyname) + '] Notification ID: ' + str(notifynumber))

                        #generate the rss-url here
                        feedinfo.append({'feed':     notifynumber + '_' + str(passkey),
                                         'feedname': notifyname,
                                         'user':     userid,
                                         'auth':     auth,
                                         'passkey':  passkey,
                                         'authkey':  authkey})
        except (requests.exceptions.Timeout, EnvironmentError):
            logger.warn('Unable to retrieve information from 32Pages - either it is not responding/is down or something else is happening that is stopping me.')
            return

        #set the keys here that will be used to download.
        try:
            mylar.PASSKEY_32P = passkey
            mylar.AUTHKEY_32P = authkey  # probably not needed here.
            mylar.KEYS_32P = {}
            mylar.KEYS_32P = {"user": userid,
                              "auth": auth,
                              "passkey": passkey,
                              "authkey": authkey}
        except NameError:
            logger.warn('Unable to retrieve information from 32Pages - either it is not responding/is down or something else is happening that is stopping me.')
            return
           
        if self.reauthenticate:
            return
        else:
            mylar.FEEDINFO_32P = feedinfo
            return feedinfo
