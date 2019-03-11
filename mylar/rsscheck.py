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

import os, sys
import re
import feedparser
import requests
import cfscrape
import urlparse
import ftpsshup
from datetime import datetime, timedelta
import gzip
import time
import random
from bs4 import BeautifulSoup
from StringIO import StringIO

import mylar
from mylar import db, logger, ftpsshup, helpers, auth32p, utorrent, helpers
import torrent.clients.transmission as transmission
import torrent.clients.deluge as deluge
import torrent.clients.qbittorrent as qbittorrent

def _start_newznab_attr(self, attrsD):
    context = self._getContext()

    context.setdefault('newznab', feedparser.FeedParserDict())
    context['newznab'].setdefault('tags', feedparser.FeedParserDict())

    name = attrsD.get('name')
    value = attrsD.get('value')

    if name == 'category':
        context['newznab'].setdefault('categories', []).append(value)
    else:
        context['newznab'][name] = value

feedparser._FeedParserMixin._start_newznab_attr = _start_newznab_attr

def torrents(pickfeed=None, seriesname=None, issue=None, feedinfo=None):
    if pickfeed is None:
        return

    srchterm = None

    if seriesname:
        srchterm = re.sub(' ', '%20', seriesname)
    if issue:
        srchterm += '%20' + str(issue)

    #this is for the public trackers included thus far in order to properly cycle throught the correct ones depending on the search request
    # DEM = rss feed
    # WWT = rss feed
    #if pickfeed == 'TPSE-SEARCH':
    #    pickfeed = '2'
    #    loopit = 1
    loopit = 1

    if pickfeed == 'Public':
        pickfeed = '999'
    #    since DEM is dead, just remove the loop entirely
    #    #we need to cycle through both DEM + WWT feeds
    #    loopit = 2

    lp = 0
    totalcount = 0

    title = []
    link = []
    description = []
    seriestitle = []

    feeddata = []
    myDB = db.DBConnection()
    torthetpse = []
    torthe32p = []
    torinfo = {}

    while (lp < loopit):
        if lp == 0 and loopit == 2:
            pickfeed = '6'  #DEM RSS
        elif lp == 1 and loopit == 2:
            pickfeed = '999'  #WWT RSS

        feedtype = None

        if pickfeed == "1" and mylar.CONFIG.ENABLE_32P is True:  # 32pages new releases feed.
            feed = 'https://32pag.es/feeds.php?feed=torrents_all&user=' + feedinfo['user'] + '&auth=' + feedinfo['auth'] + '&passkey=' + feedinfo['passkey'] + '&authkey=' + feedinfo['authkey']
            feedtype = ' from the New Releases RSS Feed for comics'
            verify = bool(mylar.CONFIG.VERIFY_32P)
        elif pickfeed == "2" and srchterm is not None:    # TP.SE search / RSS
            lp+=1
            continue
            #feed = tpse_url + 'rss/' + str(srchterm) + '/'
            #verify = bool(mylar.CONFIG.TPSE_VERIFY)
        elif pickfeed == "3":    # TP.SE rss feed (3101 = comics category) / non-RSS
            lp+=1
            continue
            #feed = tpse_url + '?hl=en&safe=off&num=50&start=0&orderby=best&s=&filter=3101'
            #feedtype = ' from the New Releases RSS Feed for comics from TP.SE'
            #verify = bool(mylar.CONFIG.TPSE_VERIFY)
        elif pickfeed == "4":    #32p search
            if any([mylar.CONFIG.USERNAME_32P is None, mylar.CONFIG.USERNAME_32P == '', mylar.CONFIG.PASSWORD_32P is None, mylar.CONFIG.PASSWORD_32P == '']):
                logger.error('[RSS] Warning - you NEED to enter in your 32P Username and Password to use this option.')
                lp=+1
                continue
            if mylar.CONFIG.MODE_32P is False:
                logger.warn('[32P] Searching is not available in 32p Legacy mode. Switch to Auth mode to use the search functionality.')
                lp=+1
                continue
            return
        elif pickfeed == "5" and srchterm is not None:  # demonoid search / non-RSS
            feed = mylar.DEMURL + "files/?category=10&subcategory=All&language=0&seeded=2&external=2&query=" + str(srchterm) + "&uid=0&out=rss"
            verify = bool(mylar.CONFIG.PUBLIC_VERIFY)
        elif pickfeed == "6":    # demonoid rss feed 
            feed = mylar.DEMURL + 'rss/10.xml'
            feedtype = ' from the New Releases RSS Feed from Demonoid'
            verify = bool(mylar.CONFIG.PUBLIC_VERIFY)
        elif pickfeed == "999":    #WWT rss feed
            feed = mylar.WWTURL + 'rss.php?cat=132,50'
            feedtype = ' from the New Releases RSS Feed from WorldWideTorrents'
            verify = bool(mylar.CONFIG.PUBLIC_VERIFY)
        elif int(pickfeed) >= 7 and feedinfo is not None and mylar.CONFIG.ENABLE_32P is True:
            #personal 32P notification feeds.
            #get the info here
            feed = 'https://32pag.es/feeds.php?feed=' + feedinfo['feed'] + '&user=' + feedinfo['user'] + '&auth=' + feedinfo['auth'] + '&passkey=' + feedinfo['passkey'] + '&authkey=' + feedinfo['authkey'] + '&name=' + feedinfo['feedname']
            feedtype = ' from your Personal Notification Feed : ' + feedinfo['feedname']
            verify = bool(mylar.CONFIG.VERIFY_32P)
        else:
            logger.error('invalid pickfeed denoted...')
            return

        #if pickfeed == '2' or pickfeed == '3':
        #    picksite = 'TPSE'
            #if pickfeed == '2':
            #    feedme = tpse.
        if pickfeed == '5' or pickfeed == '6':
            picksite = 'DEM'
        elif pickfeed == '999':
            picksite = 'WWT'
        elif pickfeed == '1' or pickfeed == '4' or int(pickfeed) > 7:
            picksite = '32P'

        if all([pickfeed != '4', pickfeed != '3', pickfeed != '5']):
            payload = None

            ddos_protection = round(random.uniform(0,15),2)
            time.sleep(ddos_protection)

            logger.info('Now retrieving feed from %s' % picksite)
            try:
                headers = {'Accept-encoding': 'gzip',
                           'User-Agent':       mylar.CV_HEADERS['User-Agent']}
                cf_cookievalue = None
                scraper = cfscrape.create_scraper()
                if pickfeed == '999':
                    if all([pickfeed == '999', mylar.WWT_CF_COOKIEVALUE is None]):
                        try:
                            cf_cookievalue, cf_user_agent = scraper.get_tokens(feed, user_agent=mylar.CV_HEADERS['User-Agent'])
                        except Exception as e:
                            logger.warn('[WWT-RSSFEED] Unable to retrieve RSS properly: %s' % e)
                            lp+=1
                            continue
                        else:
                            mylar.WWT_CF_COOKIEVALUE = cf_cookievalue
                            cookievalue = cf_cookievalue
                    elif pickfeed == '999':
                        cookievalue = mylar.WWT_CF_COOKIEVALUE

                    r = scraper.get(feed, verify=verify, cookies=cookievalue, headers=headers)
                else:
                    r = scraper.get(feed, verify=verify, headers=headers)
            except Exception, e:
                logger.warn('Error fetching RSS Feed Data from %s: %s' % (picksite, e))
                lp+=1
                continue

            feedme = feedparser.parse(r.content)
            #logger.info(feedme)   #<-- uncomment this to see what Mylar is retrieving from the feed

        i = 0

        if pickfeed == '4':
            for entry in searchresults['entries']:
                justdigits = entry['file_size'] #size not available in follow-list rss feed
                seeddigits = entry['seeders']  #number of seeders not available in follow-list rss feed

                if int(seeddigits) >= int(mylar.CONFIG.MINSEEDS):
                    torthe32p.append({
                                    'site':     picksite,
                                    'title':    entry['torrent_seriesname'].lstrip() + ' ' + entry['torrent_seriesvol'] + ' #' + entry['torrent_seriesiss'],
                                    'volume':   entry['torrent_seriesvol'],      # not stored by mylar yet.
                                    'issue':    entry['torrent_seriesiss'],    # not stored by mylar yet.
                                    'link':     entry['torrent_id'],  #just the id for the torrent
                                    'pubdate':  entry['pubdate'],
                                    'size':     entry['file_size'],
                                    'seeders':  entry['seeders'],
                                    'files':    entry['num_files']
                                    })
                i += 1
        elif pickfeed == '3':
            #TP.SE RSS FEED (parse)
            pass
        elif pickfeed == '5':
            #DEMONOID SEARCH RESULT (parse)
            pass
        elif pickfeed == "999":
            #try:
            #    feedme = feedparser.parse(feed)
            #except Exception, e:
            #    logger.warn('Error fetching RSS Feed Data from %s: %s' % (picksite, e))
            #    lp+=1
            #    continue

            #WWT / FEED
            for entry in feedme.entries:
                tmpsz = entry.description
                tmpsz_st = tmpsz.find('Size:') + 6
                if 'GB' in tmpsz[tmpsz_st:]:
                    szform = 'GB'
                    sz = 'G'
                elif 'MB' in tmpsz[tmpsz_st:]:
                    szform = 'MB'
                    sz = 'M'
                linkwwt = urlparse.parse_qs(urlparse.urlparse(entry.link).query)['id']
                feeddata.append({
                                'site':     picksite,
                                'title':    entry.title,
                                'link':     ''.join(linkwwt),
                                'pubdate':  entry.updated,
                                'size':     helpers.human2bytes(str(tmpsz[tmpsz_st:tmpsz.find(szform, tmpsz_st) -1]) + str(sz))   #+ 2 is for the length of the MB/GB in the size.
                                })
                i+=1
        else:
            for entry in feedme['entries']:
                #DEMONOID / FEED
                if pickfeed == "6":
                    tmpsz = feedme.entries[i].description
                    tmpsz_st = tmpsz.find('Size')
                    if tmpsz_st != -1:
                        tmpsize = tmpsz[tmpsz_st:tmpsz_st+14]
                        if any(['GB' in tmpsize, 'MB' in tmpsize, 'KB' in tmpsize, 'TB' in tmpsize]):
                            tmp1 = tmpsz.find('MB', tmpsz_st)
                            if tmp1 == -1:
                                tmp1 = tmpsz.find('GB', tmpsz_st)
                                if tmp1 == -1:
                                    tmp1 = tmpsz.find('TB', tmpsz_st)
                                    if tmp1 == -1:
                                        tmp1 = tmpsz.find('KB', tmpsz_st)
                            tmpsz_end = tmp1 + 2
                            tmpsz_st += 7
                    else:
                        tmpsz = tmpsz[:80]  #limit it to the first 80 so it doesn't pick up alt covers mistakingly
                        tmpsz_st = tmpsz.rfind('|')
                        if tmpsz_st != -1:
                            tmpsz_end = tmpsz.find('<br />', tmpsz_st)
                            tmpsize = tmpsz[tmpsz_st:tmpsz_end] #st+14]
                            if any(['GB' in tmpsize, 'MB' in tmpsize, 'KB' in tmpsize, 'TB' in tmpsize]):
                                tmp1 = tmpsz.find('MB', tmpsz_st)
                                if tmp1 == -1:
                                    tmp1 = tmpsz.find('GB', tmpsz_st)
                                    if tmp1 == -1:
                                        tmp1 = tmpsz.find('TB', tmpsz_st)
                                        if tmp1 == -1:
                                            tmp1 = tmpsz.find('KB', tmpsz_st)

                            tmpsz_end = tmp1 + 2
                            tmpsz_st += 2

                    if 'KB' in tmpsz[tmpsz_st:tmpsz_end]:
                        szform = 'KB'
                        sz = 'K'
                    elif 'GB' in tmpsz[tmpsz_st:tmpsz_end]:
                        szform = 'GB'
                        sz = 'G'
                    elif 'MB' in tmpsz[tmpsz_st:tmpsz_end]:
                        szform = 'MB'
                        sz = 'M'
                    elif 'TB' in tmpsz[tmpsz_st:tmpsz_end]:
                        szform = 'TB'
                        sz = 'T'
                    tsize = helpers.human2bytes(str(tmpsz[tmpsz_st:tmpsz.find(szform, tmpsz_st) -1]) + str(sz))

                    #timestamp is in YYYY-MM-DDTHH:MM:SS+TZ :/
                    dt = feedme.entries[i].updated
                    try:
                        pd = datetime.strptime(dt[0:19], '%Y-%m-%dT%H:%M:%S')
                        pdate = pd.strftime('%a, %d %b %Y %H:%M:%S') + ' ' + re.sub(':', '', dt[19:]).strip()
                        #if dt[19]=='+':
                        #    pdate+=timedelta(hours=int(dt[20:22]), minutes=int(dt[23:]))
                        #elif dt[19]=='-':
                        #    pdate-=timedelta(hours=int(dt[20:22]), minutes=int(dt[23:]))
                    except:
                        pdate = feedme.entries[i].updated

                    feeddata.append({
                                    'site':     picksite,
                                    'title':    feedme.entries[i].title,
                                    'link':     str(re.sub('genid=', '', urlparse.urlparse(feedme.entries[i].link)[4]).strip()),
                                    #'link':     str(urlparse.urlparse(feedme.entries[i].link)[2].rpartition('/')[0].rsplit('/',2)[2]),
                                    'pubdate':  pdate,
                                    'size':     tsize
                                    })

                #32p / FEEDS
                elif pickfeed == "1" or int(pickfeed) > 7:
                    tmpdesc = feedme.entries[i].description
                    st_pub = feedme.entries[i].title.find('(')
                    st_end = feedme.entries[i].title.find(')')
                    pub = feedme.entries[i].title[st_pub +1:st_end] # +1 to not include (
                    #logger.fdebug('publisher: ' + re.sub("'",'', pub).strip())  #publisher sometimes is given within quotes for some reason, strip 'em.
                    vol_find = feedme.entries[i].title.find('vol.')
                    series = feedme.entries[i].title[st_end +1:vol_find].strip()
                    series = re.sub('&amp;', '&', series).strip()
                    #logger.fdebug('series title: ' + series)
                    iss_st = feedme.entries[i].title.find(' - ', vol_find)
                    vol = re.sub('\.', '', feedme.entries[i].title[vol_find:iss_st]).strip()
                    #logger.fdebug('volume #: ' + str(vol))
                    issue = feedme.entries[i].title[iss_st +3:].strip()
                    #logger.fdebug('issue # : ' + str(issue))

                    try:
                        justdigits = feedme.entries[i].torrent_contentlength
                    except:
                        justdigits = '0'

                    seeddigits = 0

                    #if '0-Day Comics Pack' in series:
                    #    logger.info('Comic Pack detected : ' + series)
                    #    itd = True


                    if int(mylar.CONFIG.MINSEEDS) >= int(seeddigits):
                        #new releases has it as '&id', notification feeds have it as %ampid (possibly even &amp;id
                        link = feedme.entries[i].link
                        link = re.sub('&amp','&', link)
                        link = re.sub('&amp;','&', link)
                        linkst = link.find('&id')
                        linken = link.find('&', linkst +1)
                        if linken == -1:
                            linken = len(link)
                        newlink = re.sub('&id=', '', link[linkst:linken]).strip()
                        feeddata.append({
                                       'site':     picksite,
                                       'title':    series.lstrip() + ' ' + vol + ' #' + issue,
                                       'volume':   vol,      # not stored by mylar yet.
                                       'issue':    issue,    # not stored by mylar yet.
                                       'link':     newlink,  #just the id for the torrent
                                       'pubdate':  feedme.entries[i].updated,
                                       'size':     justdigits
                                       })

                i += 1

        if feedtype is None:
            logger.info('[' + picksite + '] there were ' + str(i) + ' results..')
        else:
            logger.info('[' + picksite + '] there were ' + str(i) + ' results' + feedtype)

        totalcount += i
        lp += 1

    if not seriesname:
        #rss search results
        rssdbupdate(feeddata, totalcount, 'torrent')
    else:
        #backlog (parsing) search results
        if pickfeed == '4':
            torinfo['entries'] = torthe32p
        else:
            torinfo['entries'] = torthetpse
        return torinfo
    return

def ddl(forcerss=False):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1'}
    ddl_feed = 'https://getcomics.info/feed/'
    try:
        r = requests.get(ddl_feed, verify=True, headers=headers)
    except Exception, e:
        logger.warn('Error fetching RSS Feed Data from DDL: %s' % (e))
        return False
    else:
        if r.status_code != 200:
            #typically 403 will not return results, but just catch anything other than a 200
            if r.status_code == 403:
                logger.warn('ERROR - status code:%s' % r.status_code)
                return False
            else:
                logger.warn('[%s] Status code returned: %s' % (r.status_code))
                return False

        feedme = feedparser.parse(r.content)
        results = []
        for entry in feedme.entries:
            soup = BeautifulSoup(entry.summary, 'html.parser')
            orig_find = soup.find("p", {"style": "text-align: center;"})
            i = 0
            option_find = orig_find
            while True: #i <= 10:
                prev_option = option_find
                option_find = option_find.findNext(text=True)
                if 'Year' in option_find:
                    year = option_find.findNext(text=True)
                    year = re.sub('\|', '', year).strip()
                else:
                   if 'Size' in prev_option:
                        size = option_find #.findNext(text=True)
                        if '- MB' in size: size = '0 MB'
                        possible_more = orig_find.next_sibling
                        break
            i+=1

            link = entry.link
            title = entry.title
            updated = entry.updated
            if updated.endswith('+0000'):
                updated = updated[:-5].strip()
            tmpid = entry.id
            id = tmpid[tmpid.find('=')+1:]
            if 'KB' in size:
                szform = 'KB'
                sz = 'K'
            elif 'GB' in size:
                szform = 'GB'
                sz = 'G'
            elif 'MB' in size:
                szform = 'MB'
                sz = 'M'
            elif 'TB' in size:
                szform = 'TB'
                sz = 'T'
            tsize = helpers.human2bytes(re.sub('[^0-9]', '', size).strip() + sz)

            #link can be referenced with the ?p=id url
            results.append({'Title':   title,
                            'Size':    tsize,
                            'Link':    id,
                            'Site':    'DDL',
                            'Pubdate': updated})

        if len(results) >0:
            logger.info('[RSS][DDL] %s entries have been indexed and are now going to be stored for caching.' % len(results))
            rssdbupdate(results, len(results), 'ddl')

    return

def nzbs(provider=None, forcerss=False):

    feedthis = []

    def _parse_feed(site, url, verify, payload=None):
        logger.fdebug('[RSS] Fetching items from ' + site)
        headers = {'User-Agent':      str(mylar.USER_AGENT)}

        try:
            r = requests.get(url, params=payload, verify=verify, headers=headers)
        except Exception, e:
            logger.warn('Error fetching RSS Feed Data from %s: %s' % (site, e))
            return

        if r.status_code != 200:
            #typically 403 will not return results, but just catch anything other than a 200
            if r.status_code == 403:
                return False
            else:
                logger.warn('[%s] Status code returned: %s' % (site, r.status_code))
                if r.status_code == 503:
                    logger.warn('[%s] Site appears unresponsive/down. Disabling...' % (site))
                    return 'disable'
                else:
                    return

        feedme = feedparser.parse(r.content)

        feedthis.append({"site": site,
                         "feed": feedme})

    newznab_hosts = []

    if mylar.CONFIG.NEWZNAB is True:
        for newznab_host in mylar.CONFIG.EXTRA_NEWZNABS:
            if str(newznab_host[5]) == '1':
                newznab_hosts.append(newznab_host)

    providercount = len(newznab_hosts) + int(mylar.CONFIG.EXPERIMENTAL is True) + int(mylar.CONFIG.NZBSU is True) + int(mylar.CONFIG.DOGNZB is True)
    logger.fdebug('[RSS] You have enabled ' + str(providercount) + ' NZB RSS search providers.')

    if providercount > 0:
        if mylar.CONFIG.EXPERIMENTAL == 1:
            max_entries = "250" if forcerss else "50"
            params = {'sort': 'agedesc',
                      'max':   max_entries,
                      'more':  '1'}
            check = _parse_feed('experimental', 'http://nzbindex.nl/rss/alt.binaries.comics.dcp', False, params)
            if check == 'disable':
                helpers.disable_provider(site)

        if mylar.CONFIG.NZBSU == 1:
            num_items = "&num=100" if forcerss else ""  # default is 25
            params = {'t':        '7030',
                      'dl':        '1', 
                      'i':         mylar.CONFIG.NZBSU_UID,
                      'r':         mylar.CONFIG.NZBSU_APIKEY,
                      'num_items': num_items}
            check = _parse_feed('nzb.su', 'https://api.nzb.su/rss', mylar.CONFIG.NZBSU_VERIFY, params)
            if check == 'disable':
                helpers.disable_provider(site)

        if mylar.CONFIG.DOGNZB == 1:
            num_items = "&num=100" if forcerss else ""  # default is 25
            params = {'t':        '7030',
                      'r':         mylar.CONFIG.DOGNZB_APIKEY,
                      'num_items': num_items}

            check = _parse_feed('dognzb', 'https://dognzb.cr/rss.cfm', mylar.CONFIG.DOGNZB_VERIFY, params)
            if check == 'disable':
                helpers.disable_provider(site)

        for newznab_host in newznab_hosts:
            site = newznab_host[0].rstrip()
            (newznabuid, _, newznabcat) = (newznab_host[4] or '').partition('#')
            newznabuid = newznabuid or '1'
            newznabcat = newznabcat or '7030'

            if site[-10:] == '[nzbhydra]':
                #to allow nzbhydra to do category search by most recent (ie. rss)
                url = newznab_host[1].rstrip() + '/api'
                params = {'t':         'search',
                          'cat':       str(newznabcat),
                          'dl':        '1',
                          'apikey':    newznab_host[3].rstrip(),
                          'num':       '100'}
                check = _parse_feed(site, url, bool(newznab_host[2]), params)
            else:
                url = newznab_host[1].rstrip() + '/rss'
                params = {'t':         str(newznabcat),
                          'dl':        '1',
                          'i':         str(newznabuid),
                          'r':         newznab_host[3].rstrip(),
                          'num':       '100'}

                check = _parse_feed(site, url, bool(newznab_host[2]), params)
                if check is False and 'rss' in url[-3:]:
                    logger.fdebug('RSS url returning 403 error. Attempting to use API to get most recent items in lieu of RSS feed')
                    url = newznab_host[1].rstrip() + '/api'
                    params = {'t':         'search',
                              'cat':       str(newznabcat),
                              'dl':        '1',
                              'apikey':    newznab_host[3].rstrip(),
                              'num':       '100'}
                    check = _parse_feed(site, url, bool(newznab_host[2]), params)
                if check == 'disable':
                    helpers.disable_provider(site, newznab=True)

        feeddata = []

        for ft in feedthis:
            site = ft['site']
            logger.fdebug('[RSS] (' + site + ') now being updated...')

            for entry in ft['feed'].entries:

                if site == 'dognzb':
                    #because the rss of dog doesn't carry the enclosure item, we'll use the newznab size value
                    size = 0
                    if 'newznab' in entry and 'size' in entry['newznab']:
                        size = entry['newznab']['size']
                else:
                    # experimental, nzb.su, newznab
                    size = entry.enclosures[0]['length']

                # Link
                if site == 'experimental':
                    link = entry.enclosures[0]['url']
                else:
                    # dognzb, nzb.su, newznab
                    link = entry.link

                   #Remove the API keys from the url to allow for possible api key changes
                    if site == 'dognzb':
                        link = re.sub(mylar.CONFIG.DOGNZB_APIKEY, '', link).strip()
                    else:
                        link = link[:link.find('&i=')].strip()

                feeddata.append({'Site': site,
                                 'Title': entry.title,
                                 'Link': link,
                                 'Pubdate': entry.updated,
                                 'Size': size})

            logger.info('[RSS] (' + site + ') ' + str(len(ft['feed'].entries)) + ' entries indexed.')

        i = len(feeddata)
        if i:
            logger.info('[RSS] ' + str(i) + ' entries have been indexed and are now going to be stored for caching.')
            rssdbupdate(feeddata, i, 'usenet')

    return

def rssdbupdate(feeddata, i, type):
    rsschktime = 15
    myDB = db.DBConnection()

    #let's add the entries into the db so as to save on searches
    #also to build up the ID's ;)

    for dataval in feeddata:

        if type == 'torrent':
            #we just store the torrent ID's now.

            newVal = {"Link":      dataval['link'],
                      "Pubdate":   dataval['pubdate'],
                      "Site":      dataval['site'],
                      "Size":      dataval['size']}
            ctrlVal = {"Title":    dataval['title']}

        else:
            newlink = dataval['Link']
            newVal = {"Link":      newlink,
                      "Pubdate":   dataval['Pubdate'],
                      "Site":      dataval['Site'],
                      "Size":      dataval['Size']}
            ctrlVal = {"Title":    dataval['Title']}

        myDB.upsert("rssdb", newVal, ctrlVal)

    logger.fdebug('Completed adding new data to RSS DB. Next add in ' + str(mylar.CONFIG.RSS_CHECKINTERVAL) + ' minutes')
    return

def ddl_dbsearch(seriesname, issue, comicid=None, nzbprov=None, oneoff=False):
    myDB = db.DBConnection()
    seriesname_alt = None
    if any([comicid is None, comicid == 'None', oneoff is True]):
        pass
    else:
        snm = myDB.selectone("SELECT * FROM comics WHERE comicid=?", [comicid]).fetchone()
        if snm is None:
            logger.fdebug('Invalid ComicID of %s. Aborting search' % comicid)
            return "no results"
        else:
            seriesname = snm['ComicName']
            seriesname_alt = snm['AlternateSearch']

    dsearch_rem1 = re.sub("\\band\\b", "%", seriesname.lower())
    dsearch_rem2 = re.sub("\\bthe\\b", "%", dsearch_rem1.lower())
    dsearch_removed = re.sub('\s+', ' ', dsearch_rem2)
    dsearch_seriesname = re.sub('[\'\!\@\#\$\%\:\-\;\/\\=\?\&\.\s\,]', '%', dsearch_removed)
    dsearch = '%' + dsearch_seriesname + '%'
    dresults = myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='DDL'", [dsearch])
    ddltheinfo = []
    ddlinfo = {}
    if not dresults:
        return "no results"
    else:
        for dl in dresults:
            ddltheinfo.append({
                          'title':   dl['Title'],
                          'link':    dl['Link'],
                          'pubdate': dl['Pubdate'],
                          'site':    dl['Site'],
                          'length':  dl['Size']
                          })

    ddlinfo['entries'] = ddltheinfo

    return ddlinfo

def torrentdbsearch(seriesname, issue, comicid=None, nzbprov=None, oneoff=False):
    myDB = db.DBConnection()
    seriesname_alt = None
    if any([comicid is None, comicid == 'None', oneoff is True]):
        pass
    else:
        #logger.fdebug('ComicID: ' + str(comicid))
        snm = myDB.selectone("SELECT * FROM comics WHERE comicid=?", [comicid]).fetchone()
        if snm is None:
            logger.fdebug('Invalid ComicID of ' + str(comicid) + '. Aborting search.')
            return
        else:
            seriesname = snm['ComicName']
            seriesname_alt = snm['AlternateSearch']

    #remove 'and' and 'the':
    tsearch_rem1 = re.sub("\\band\\b", "%", seriesname.lower())
    tsearch_rem2 = re.sub("\\bthe\\b", "%", tsearch_rem1.lower())
    tsearch_removed = re.sub('\s+', ' ', tsearch_rem2)
    tsearch_seriesname = re.sub('[\'\!\@\#\$\%\:\-\;\/\\=\?\&\.\s\,]', '%', tsearch_removed)
    if mylar.CONFIG.PREFERRED_QUALITY == 0:
        tsearch = tsearch_seriesname + "%"
    elif mylar.CONFIG.PREFERRED_QUALITY == 1:
        tsearch = tsearch_seriesname + "%cbr%"
    elif mylar.CONFIG.PREFERRED_QUALITY == 2:
        tsearch = tsearch_seriesname + "%cbz%"
    else:
        tsearch = tsearch_seriesname + "%"

    if seriesname == '0-Day Comics Pack - %s' % (issue[:4]):
        #call the helper to get the month
        tsearch += 'vol%s' % issue[5:7]
        tsearch += '%'
        tsearch += '#%s' % issue[8:10]
        tsearch += '%'
    #logger.fdebug('tsearch : ' + tsearch)
    AS_Alt = []
    tresults = []
    tsearch = '%' + tsearch

    if mylar.CONFIG.ENABLE_32P and nzbprov == '32P':
        tresults = myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='32P'", [tsearch])
    if mylar.CONFIG.ENABLE_PUBLIC and nzbprov == 'Public Torrents':
        tresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND (Site='DEM' OR Site='WWT')", [tsearch])

    #logger.fdebug('seriesname_alt:' + str(seriesname_alt))
    if seriesname_alt is None or seriesname_alt == 'None':
        if not tresults:
            logger.fdebug('no Alternate name given. Aborting search.')
            return "no results"
    else:
        chkthealt = seriesname_alt.split('##')
        if chkthealt == 0:
            AS_Alternate = seriesname_alt
            AS_Alt.append(seriesname_alt)
        for calt in chkthealt:
            AS_Alter = re.sub('##', '', calt)
            u_altsearchcomic = AS_Alter.encode('ascii', 'ignore').strip()
            AS_Altrem = re.sub("\\band\\b", "", u_altsearchcomic.lower())
            AS_Altrem = re.sub("\\bthe\\b", "", AS_Altrem.lower())

            AS_Alternate = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\+\'\&\?\@\s]', '%', AS_Altrem)

            AS_Altrem_mod = re.sub('[\&]', ' ', AS_Altrem)
            AS_formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.\,]', '', AS_Altrem_mod)
            AS_formatrem_seriesname = re.sub('\s+', ' ', AS_formatrem_seriesname)
            if AS_formatrem_seriesname[:1] == ' ': AS_formatrem_seriesname = AS_formatrem_seriesname[1:]
            AS_Alt.append(AS_formatrem_seriesname)

            if mylar.CONFIG.PREFERRED_QUALITY == 0:
                 AS_Alternate += "%"
            elif mylar.CONFIG.PREFERRED_QUALITY == 1:
                 AS_Alternate += "%cbr%"
            elif mylar.CONFIG.PREFERRED_QUALITY == 2:
                 AS_Alternate += "%cbz%"
            else:
                 AS_Alternate += "%"

            AS_Alternate = '%' + AS_Alternate
            if mylar.CONFIG.ENABLE_32P and nzbprov == '32P':
                tresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='32P'", [AS_Alternate])
            if mylar.CONFIG.ENABLE_PUBLIC and nzbprov == 'Public Torrents':
                tresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND (Site='DEM' OR Site='WWT')", [AS_Alternate])

    if not tresults:
        logger.fdebug('torrent search returned no results for %s' % seriesname)
        return "no results"

    extensions = ('cbr', 'cbz')
    tortheinfo = []
    torinfo = {}

    for tor in tresults:
        #&amp; have been brought into the title field incorretly occassionally - patched now, but to include those entries already in the 
        #cache db that have the incorrect entry, we'll adjust.
        torTITLE = re.sub('&amp;', '&', tor['Title']).strip()

        #torsplit = torTITLE.split(' ')
        if mylar.CONFIG.PREFERRED_QUALITY == 1:
            if 'cbr' not in torTITLE:
                #logger.fdebug('Quality restriction enforced [ cbr only ]. Rejecting result.')
                continue
        elif mylar.CONFIG.PREFERRED_QUALITY == 2:
            if 'cbz' not in torTITLE:
                #logger.fdebug('Quality restriction enforced [ cbz only ]. Rejecting result.')
                continue
        #logger.fdebug('tor-Title: ' + torTITLE)
        #logger.fdebug('there are ' + str(len(torsplit)) + ' sections in this title')
        i=0
        if nzbprov is not None:
            if nzbprov != tor['Site'] and not any([mylar.CONFIG.ENABLE_PUBLIC, tor['Site'] != 'WWT', tor['Site'] != 'DEM']):
                #logger.fdebug('this is a result from ' + str(tor['Site']) + ', not the site I am looking for of ' + str(nzbprov))
                continue
        #0 holds the title/issue and format-type.

        seriesname_mod = seriesname
        foundname_mod = torTITLE #torsplit[0]
        seriesname_mod = re.sub("\\band\\b", " ", seriesname_mod.lower())
        foundname_mod = re.sub("\\band\\b", " ", foundname_mod.lower())
        seriesname_mod = re.sub("\\bthe\\b", " ", seriesname_mod.lower())
        foundname_mod = re.sub("\\bthe\\b", " ", foundname_mod.lower())

        seriesname_mod = re.sub('[\&]', ' ', seriesname_mod)
        foundname_mod = re.sub('[\&]', ' ', foundname_mod)

        formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\=\?\.\,]', '', seriesname_mod)
        formatrem_seriesname = re.sub('[\-]', ' ', formatrem_seriesname)
        formatrem_seriesname = re.sub('[\/]', ' ', formatrem_seriesname)  #not necessary since seriesname in a torrent file won't have /
        formatrem_seriesname = re.sub('\s+', ' ', formatrem_seriesname)
        if formatrem_seriesname[:1] == ' ': formatrem_seriesname = formatrem_seriesname[1:]

        formatrem_torsplit = re.sub('[\'\!\@\#\$\%\:\;\\=\?\.\,]', '', foundname_mod)
        formatrem_torsplit = re.sub('[\-]', ' ', formatrem_torsplit)  #we replace the - with space so we'll get hits if differnces
        formatrem_torsplit = re.sub('[\/]', ' ', formatrem_torsplit)  #not necessary since if has a /, should be removed in above line
        formatrem_torsplit = re.sub('\s+', ' ', formatrem_torsplit)
        #logger.fdebug(str(len(formatrem_torsplit)) + ' - formatrem_torsplit : ' + formatrem_torsplit.lower())
        #logger.fdebug(str(len(formatrem_seriesname)) + ' - formatrem_seriesname :' + formatrem_seriesname.lower())

        if formatrem_seriesname.lower() in formatrem_torsplit.lower() or any(x.lower() in formatrem_torsplit.lower() for x in AS_Alt):
            #logger.fdebug('matched to : ' + torTITLE)
            #logger.fdebug('matched on series title: ' + seriesname)
            titleend = formatrem_torsplit[len(formatrem_seriesname):]
            titleend = re.sub('\-', '', titleend)   #remove the '-' which is unnecessary
            #remove extensions
            titleend = re.sub('cbr', '', titleend)
            titleend = re.sub('cbz', '', titleend)
            titleend = re.sub('none', '', titleend)
            #logger.fdebug('titleend: ' + titleend)

            sptitle = titleend.split()
            extra = ''

            tortheinfo.append({
                          'title':   torTITLE, #cttitle,
                          'link':    tor['Link'],
                          'pubdate': tor['Pubdate'],
                          'site':    tor['Site'],
                          'length':  tor['Size']
                          })

    torinfo['entries'] = tortheinfo

    return torinfo

def nzbdbsearch(seriesname, issue, comicid=None, nzbprov=None, searchYear=None, ComicVersion=None, oneoff=False):
    myDB = db.DBConnection()
    seriesname_alt = None
    if any([comicid is None, comicid == 'None', oneoff is True]):
        pass
    else:
        snm = myDB.selectone("SELECT * FROM comics WHERE comicid=?", [comicid]).fetchone()
        if snm is None:
            logger.info('Invalid ComicID of ' + str(comicid) + '. Aborting search.')
            return
        else:
            seriesname = snm['ComicName']
            seriesname_alt = snm['AlternateSearch']

    nsearch_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.\-\s]', '%', seriesname)
    formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.]', '', seriesname)

    nsearch = '%' + nsearch_seriesname + "%"

    nresults = myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site=?", [nsearch, nzbprov])
    if nresults is None:
        logger.fdebug('nzb search returned no results for ' + seriesname)
        if seriesname_alt is None:
            logger.fdebug('no nzb Alternate name given. Aborting search.')
            return "no results"
        else:
            chkthealt = seriesname_alt.split('##')
            if chkthealt == 0:
                AS_Alternate = AlternateSearch
            for calt in chkthealt:
                AS_Alternate = re.sub('##', '', calt)
                AS_Alternate = '%' + AS_Alternate + "%"
                nresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site=?", [AS_Alternate, nzbprov])
            if nresults is None:
                logger.fdebug('nzb alternate name search returned no results.')
                return "no results"

    nzbtheinfo = []
    nzbinfo = {}

    if nzbprov == 'experimental':
        except_list=['releases', 'gold line', 'distribution', '0-day', '0 day']

        if ComicVersion:
            ComVersChk = re.sub("[^0-9]", "", ComicVersion)
            if ComVersChk == '':
                ComVersChk = 0
            else:
                ComVersChk = 0
        else:
            ComVersChk = 0

        filetype = None
        if mylar.CONFIG.PREFERRED_QUALITY == 1: filetype = 'cbr'
        elif mylar.CONFIG.PREFERRED_QUALITY == 2: filetype = 'cbz'

        for results in nresults:
            title = results['Title']
            #logger.fdebug("titlesplit: " + str(title.split("\"")))
            splitTitle = title.split("\"")
            noYear = 'False'
            _digits = re.compile('\d')
            for subs in splitTitle:
                #logger.fdebug(subs)
                if len(subs) >= len(seriesname) and not any(d in subs.lower() for d in except_list) and bool(_digits.search(subs)) is True:
                    if subs.lower().startswith('for'):
                         # need to filter down alternate names in here at some point...
                        if seriesname.lower().startswith('for'):
                            pass
                        else:
                            #this is the crap we ignore. Continue
                            logger.fdebug('this starts with FOR : ' + str(subs) + '. This is not present in the series - ignoring.')
                            continue

                    if ComVersChk == 0:
                        noYear = 'False'

                    if ComVersChk != 0 and searchYear not in subs:
                        noYear = 'True'
                        noYearline = subs

                    if searchYear in subs and noYear == 'True':
                        #this would occur on the next check in the line, if year exists and
                        #the noYear check in the first check came back valid append it
                        subs = noYearline + ' (' + searchYear + ')'
                        noYear = 'False'

                    if noYear == 'False':

                        if filetype is not None:
                            if filetype not in subs.lower():
                                continue

                        nzbtheinfo.append({
                                  'title':   subs,
                                  'link':    re.sub('\/release\/', '/download/', results['Link']),
                                  'pubdate': str(results['PubDate']),
                                  'site':    str(results['Site']),
                                  'length':  str(results['Size'])})

    else:
        for nzb in nresults:
            # no need to parse here, just compile and throw it back ....
            nzbtheinfo.append({
                             'title':   nzb['Title'],
                             'link':    nzb['Link'],
                             'pubdate': nzb['Pubdate'],
                             'site':    nzb['Site'],
                             'length':    nzb['Size']
                             })
            #logger.fdebug("entered info for " + nzb['Title'])


    nzbinfo['entries'] = nzbtheinfo
    return nzbinfo

def torsend2client(seriesname, issue, seriesyear, linkit, site, pubhash=None):
    logger.info('matched on ' + seriesname)
    filename = helpers.filesafe(seriesname)
    filename = re.sub(' ', '_', filename)
    filename += "_" + str(issue) + "_" + str(seriesyear)

    if linkit[-7:] != "torrent":
        filename += ".torrent"
    if any([mylar.USE_UTORRENT, mylar.USE_RTORRENT, mylar.USE_TRANSMISSION, mylar.USE_DELUGE, mylar.USE_QBITTORRENT]):
        filepath = os.path.join(mylar.CONFIG.CACHE_DIR, filename)
        logger.fdebug('filename for torrent set to : ' + filepath)

    elif mylar.USE_WATCHDIR:
        if mylar.CONFIG.TORRENT_LOCAL and mylar.CONFIG.LOCAL_WATCHDIR is not None:
            filepath = os.path.join(mylar.CONFIG.LOCAL_WATCHDIR, filename)
            logger.fdebug('filename for torrent set to : ' + filepath)
        elif mylar.CONFIG.TORRENT_SEEDBOX and mylar.CONFIG.SEEDBOX_WATCHDIR is not None:
            filepath = os.path.join(mylar.CONFIG.CACHE_DIR, filename)
            logger.fdebug('filename for torrent set to : ' + filepath)
        else:
            logger.error('No Local Watch Directory or Seedbox Watch Directory specified. Set it and try again.')
            return "fail"

    cf_cookievalue = None
    if site == '32P':
        url = 'https://32pag.es/torrents.php'

        if mylar.CONFIG.ENABLE_32P is False:
            return "fail"

        if mylar.CONFIG.VERIFY_32P == 1 or mylar.CONFIG.VERIFY_32P == True:
            verify = True
        else:
            verify = False

        logger.fdebug('[32P] Verify SSL set to : ' + str(verify))
        if mylar.CONFIG.MODE_32P is False:
            if mylar.KEYS_32P is None or mylar.CONFIG.PASSKEY_32P is None:
                logger.warn('[32P] Unable to retrieve keys from provided RSS Feed. Make sure you have provided a CURRENT RSS Feed from 32P')
                mylar.KEYS_32P = helpers.parse_32pfeed(mylar.FEED_32P)
                if mylar.KEYS_32P is None or mylar.KEYS_32P == '':
                    return "fail"
                else:
                    logger.fdebug('[32P-AUTHENTICATION] 32P (Legacy) Authentication Successful. Re-establishing keys.')
                    mylar.AUTHKEY_32P = mylar.KEYS_32P['authkey']
            else:
                logger.fdebug('[32P-AUTHENTICATION] 32P (Legacy) Authentication already done. Attempting to use existing keys.')
                mylar.AUTHKEY_32P = mylar.KEYS_32P['authkey']
        else:
            if any([mylar.CONFIG.USERNAME_32P is None, mylar.CONFIG.USERNAME_32P == '', mylar.CONFIG.PASSWORD_32P is None, mylar.CONFIG.PASSWORD_32P == '']):
                logger.error('[RSS] Unable to sign-on to 32P to validate settings and initiate download sequence. Please enter/check your username password in the configuration.')
                return "fail"
            elif mylar.CONFIG.PASSKEY_32P is None or mylar.AUTHKEY_32P is None or mylar.KEYS_32P is None:
                logger.fdebug('[32P-AUTHENTICATION] 32P (Auth Mode) Authentication enabled. Keys have not been established yet, attempting to gather.')
                feed32p = auth32p.info32p(reauthenticate=True)
                feedinfo = feed32p.authenticate()
                if feedinfo == "disable":
                    helpers.disable_provider('32P')
                    return "fail"
                if mylar.CONFIG.PASSKEY_32P is None or mylar.AUTHKEY_32P is None or mylar.KEYS_32P is None:
                    logger.error('[RSS] Unable to sign-on to 32P to validate settings and initiate download sequence. Please enter/check your username password in the configuration.')
                    return "fail"
            else:
                logger.fdebug('[32P-AUTHENTICATION] 32P (Auth Mode) Authentication already done. Attempting to use existing keys.')

        payload = {'action':       'download',
                   'torrent_pass': mylar.CONFIG.PASSKEY_32P,
                   'authkey':      mylar.AUTHKEY_32P,
                   'id':           linkit}

        dfile = auth32p.info32p()
        file_download = dfile.downloadfile(payload, filepath)
        if file_download is False:
            return "fail"

        logger.fdebug('[%s] Saved torrent file to : %s' % (site, filepath))

    elif site == 'DEM':
        url = helpers.torrent_create('DEM', linkit)

        if url.startswith('https'):
            dem_referrer = mylar.DEMURL + 'files/download/'
        else:
            dem_referrer = 'http' + mylar.DEMURL[5:] + 'files/download/'

        headers = {'Accept-encoding': 'gzip',
                   'User-Agent':      str(mylar.USER_AGENT),
                   'Referer':         dem_referrer}

        logger.fdebug('Grabbing torrent from url:' + str(url))

        payload = None
        verify = False

    elif site == 'WWT':
        url = helpers.torrent_create('WWT', linkit)

        if url.startswith('https'):
            wwt_referrer = mylar.WWTURL
        else:
            wwt_referrer = 'http' + mylar.WWTURL[5:]

        headers = {'Accept-encoding': 'gzip',
                   'User-Agent':      mylar.CV_HEADERS['User-Agent'],
                   'Referer':         wwt_referrer}

        logger.fdebug('Grabbing torrent [id:' + str(linkit) + '] from url:' + str(url))

        payload = {'id':   linkit}
        verify = False

    else:
        headers = {'Accept-encoding': 'gzip',
                   'User-Agent':      str(mylar.USER_AGENT)}

        url = linkit

        payload = None
        verify = False

    if site != 'Public Torrents' and site != '32P':
        if not verify:
            #32P throws back an insecure warning because it can't validate against the CA. The below suppresses the message just for 32P instead of being displayed.
            #disable SSL warnings - too many 'warning' messages about invalid certificates
            try:
                from requests.packages.urllib3 import disable_warnings
                disable_warnings()
            except ImportError:
                #this is probably not necessary and redudant, but leaving in for the time being.
                from requests.packages.urllib3.exceptions import InsecureRequestWarning
                requests.packages.urllib3.disable_warnings()
                try:
                    from urllib3.exceptions import InsecureRequestWarning
                    urllib3.disable_warnings()
                except ImportError:
                    logger.warn('[EPIC FAILURE] Cannot load the requests module')
                    return "fail"

        try:
            scraper = cfscrape.create_scraper()
            if site == 'WWT':
                if mylar.WWT_CF_COOKIEVALUE is None:
                    cf_cookievalue, cf_user_agent = scraper.get_tokens(newurl, user_agent=mylar.CV_HEADERS['User-Agent'])
                    mylar.WWT_CF_COOKIEVALUE = cf_cookievalue
                r = scraper.get(url, params=payload, cookies=mylar.WWT_CF_COOKIEVALUE, verify=verify, stream=True, headers=headers)
            else:
                r = scraper.get(url, params=payload, verify=verify, stream=True, headers=headers)
            #r = requests.get(url, params=payload, verify=verify, stream=True, headers=headers)
        except Exception, e:
            logger.warn('Error fetching data from %s (%s): %s' % (site, url, e))
        #    if site == '32P':
        #        logger.info('[TOR2CLIENT-32P] Retrying with 32P')
        #        if mylar.CONFIG.MODE_32P == 1:

        #            logger.info('[TOR2CLIENT-32P] Attempting to re-authenticate against 32P and poll new keys as required.')
        #            feed32p = auth32p.info32p(reauthenticate=True)
        #            feedinfo = feed32p.authenticate()

        #            if feedinfo == "disable":
        #                helpers.disable_provider('32P')
        #                return "fail"

        #            logger.debug('[TOR2CLIENT-32P] Creating CF Scraper')
        #            scraper = cfscrape.create_scraper()

        #            try:
        #                r = scraper.get(url, params=payload, verify=verify, allow_redirects=True)
        #            except Exception, e:
        #                logger.warn('[TOR2CLIENT-32P] Unable to GET %s (%s): %s' % (site, url, e))
        #                return "fail"
        #        else:
        #            logger.warn('[TOR2CLIENT-32P] Unable to authenticate using existing RSS Feed given. Make sure that you have provided a CURRENT feed from 32P')
        #            return "fail"
        #    else:
        #        return "fail"

        if any([site == 'DEM', site == 'WWT']) and any([str(r.status_code) == '403', str(r.status_code) == '404', str(r.status_code) == '503']):
            if str(r.status_code) != '503':
                logger.warn('Unable to download from ' + site + ' [' + str(r.status_code) + ']')
                #retry with the alternate torrent link.
                url = helpers.torrent_create(site, linkit, True)
                logger.fdebug('Trying alternate url: ' + str(url))
                try:
                    r = requests.get(url, params=payload, verify=verify, stream=True, headers=headers)

                except Exception, e:
                    return "fail"
            else:
                logger.warn('Cloudflare protection online for ' + site + '. Attempting to bypass...')
                try:
                    scraper = cfscrape.create_scraper()
                    cf_cookievalue, cf_user_agent = cfscrape.get_cookie_string(url)
                    headers = {'Accept-encoding': 'gzip',
                               'User-Agent':       cf_user_agent}

                    r = scraper.get(url, verify=verify, cookies=cf_cookievalue, stream=True, headers=headers)
                except Exception, e:
                    return "fail"

        if any([site == 'DEM', site == 'WWT']):
            if r.headers.get('Content-Encoding') == 'gzip':
                buf = StringIO(r.content)
                f = gzip.GzipFile(fileobj=buf)

        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()

        logger.fdebug('[' + site + '] Saved torrent file to : ' + filepath)
    else:
       if site != '32P':
           #tpse is magnet links only...
           filepath = linkit

    if mylar.USE_UTORRENT:
        uTC = utorrent.utorrentclient()
        #if site == 'TPSE':
        #    ti = uTC.addurl(linkit)
        #else:
        ti = uTC.addfile(filepath, filename)
        if ti == 'fail':
            return ti
        else:
            #if ti is value, it will return the hash
            torrent_info = {}
            torrent_info['hash'] = ti
            torrent_info['clientmode'] = 'utorrent'
            torrent_info['link'] = linkit
            return torrent_info

    elif mylar.USE_RTORRENT:
        import test
        rp = test.RTorrent()

        torrent_info = rp.main(filepath=filepath)

        if torrent_info:
            torrent_info['clientmode'] = 'rtorrent'
            torrent_info['link'] = linkit
            return torrent_info
        else:
            return 'fail'
    elif mylar.USE_TRANSMISSION:
        try:
            rpc = transmission.TorrentClient()
            if not rpc.connect(mylar.CONFIG.TRANSMISSION_HOST, mylar.CONFIG.TRANSMISSION_USERNAME, mylar.CONFIG.TRANSMISSION_PASSWORD):
                return "fail"
            torrent_info = rpc.load_torrent(filepath)
            if torrent_info:
                torrent_info['clientmode'] = 'transmission'
                torrent_info['link'] = linkit
                return torrent_info
            else:
                return "fail"
        except Exception as e:
            logger.error(e)
            return "fail"

    elif mylar.USE_DELUGE:
        try:
            dc = deluge.TorrentClient()
            if not dc.connect(mylar.CONFIG.DELUGE_HOST, mylar.CONFIG.DELUGE_USERNAME, mylar.CONFIG.DELUGE_PASSWORD):
                logger.info('Not connected to Deluge!')
                return "fail"
            else:
                logger.info('Connected to Deluge! Will try to add torrent now!')
            torrent_info = dc.load_torrent(filepath)

            if torrent_info:
                torrent_info['clientmode'] = 'deluge'
                torrent_info['link'] = linkit
                return torrent_info
            else:
                return "fail"
                logger.info('Unable to connect to Deluge!')
        except Exception as e:
            logger.error(e)
            return "fail"

    elif mylar.USE_QBITTORRENT:
        try:
            qc = qbittorrent.TorrentClient()
            if not qc.connect(mylar.CONFIG.QBITTORRENT_HOST, mylar.CONFIG.QBITTORRENT_USERNAME, mylar.CONFIG.QBITTORRENT_PASSWORD):
                logger.info('Not connected to qBittorrent - Make sure the Web UI is enabled and the port is correct!')
                return "fail"
            else:
                logger.info('Connected to qBittorrent! Will try to add torrent now!')
            torrent_info = qc.load_torrent(filepath)

            if torrent_info['status'] is True:
                torrent_info['clientmode'] = 'qbittorrent'
                torrent_info['link'] = linkit
                return torrent_info
            else:
                logger.info('Unable to add torrent to qBittorrent')
                return "fail"
        except Exception as e:
            logger.error(e)
            return "fail"

    elif mylar.USE_WATCHDIR:
        if mylar.CONFIG.TORRENT_LOCAL:
            #if site == 'TPSE':
            #    torrent_info = {'hash': pubhash}
            #else:
            #    #get the hash so it doesn't mess up...
            torrent_info = helpers.get_the_hash(filepath)
            torrent_info['clientmode'] = 'watchdir'
            torrent_info['link'] = linkit
            torrent_info['filepath'] = filepath
            return torrent_info
        else:
            tssh = ftpsshup.putfile(filepath, filename)
            return tssh

def delete_cache_entry(id):
    myDB = db.DBConnection()
    myDB.action("DELETE FROM rssdb WHERE link=? AND Site='32P'", [id])

if __name__ == '__main__':
    #torrents(sys.argv[1])
    #torrentdbsearch(sys.argv[1], sys.argv[2], sys.argv[3])
    nzbs(provider=sys.argv[1])
