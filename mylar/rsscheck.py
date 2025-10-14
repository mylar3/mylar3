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
import urllib.parse
from . import ftpsshup
from datetime import datetime, timedelta
import gzip
import time
import random
from bs4 import BeautifulSoup
from io import StringIO
from packaging.version import parse as parse_version

import mylar
from mylar import db, logger, ftpsshup, helpers, auth32p, utorrent, helpers, filechecker
from mylar.torrent.clients import transmission
from mylar.torrent.clients import  deluge as deluge
from mylar.torrent.clients import qbittorrent as qbittorrent

REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)

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

if parse_version(feedparser.__version__) < parse_version('6.0.0'):
    feedparser._FeedParserMixin._start_newznab_attr = _start_newznab_attr
else:
    feedparser.mixin._FeedParserMixin._start_newznab_attr = _start_newznab_attr

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
            except Exception as e:
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
                linkwwt = urllib.parse.parse_qs(urllib.parse.urlparse(entry.link).query)['id']
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
                                    'link':     str(re.sub('genid=', '', urllib.parse.urlparse(feedme.entries[i].link)[4]).strip()),
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
        r = requests.get(ddl_feed, verify=True, headers=headers, timeout=30)
    except Exception as e:
        #need to handle timeouts / downtime here
        logger.warn('Error fetching RSS Feed Data from DDL: %s' % (e))
        return False
    else:
        if r.status_code != 200:
            #typically 403 will not return results, but just catch anything other than a 200
            if r.status_code == 503:
                logger.warn('[ERROR - Cloudflare is probably active] Status code returned: %s' % r.status_code)
            else:
                logger.warn('[ERROR] Status code returned: %s' % r.status_code)
            return False

    feedme = feedparser.parse(r.content)
    results = []
    for entry in feedme.entries:
        soup = BeautifulSoup(entry.summary, 'html.parser')
        orig_find = soup.find("p", {"style": "text-align: center;"})

        # Non-comic posts don't have the centered header of data so can be skipped
        if orig_find is None:
            continue

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
                        'Site':    'DDL(GetComics)',
                        'Pubdate': updated})

    logger.info('[DDL][RSS-RESULTS] %s' % (results,))
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
        except Exception as e:
            logger.warn('Error fetching RSS Feed Data from %s: %s' % (site, e))
            return False

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
                    return False

        feedme = feedparser.parse(r.content)

        feedthis.append({"site": site,
                         "feed": feedme})
        
        return True

    newznab_hosts = []

    if mylar.CONFIG.NEWZNAB is True:
        for newznab_host in mylar.CONFIG.EXTRA_NEWZNABS:
            if str(newznab_host[5]) == '1':
                newznab_hosts.append(newznab_host)

    dcpp_enabled = (mylar.CONFIG.ENABLE_AIRDCPP and
                    hasattr(mylar.CONFIG, 'AIRDCPP_ANNOUNCE_HUB') and
                    len(mylar.CONFIG.AIRDCPP_ANNOUNCE_HUB) > 0)

    providercount = len(newznab_hosts) + int(mylar.CONFIG.EXPERIMENTAL is True) + int(dcpp_enabled)
    logger.fdebug('[RSS] You have enabled ' + str(providercount) + ' NZB RSS search providers.')

    if providercount > 0:
        if mylar.CONFIG.EXPERIMENTAL is True:
            max_entries = "250" if forcerss else "50"
            params = {'sort': 'agedesc',
                      'max':   max_entries,
                      'more':  '1',
                      'q': None,
                      'minage:': 0,
                      'maxage': 0,
                      'hidespam': 1,
                      'hidepassword': 1,
                      'minsize': 0,
                      'maxsize': 0,
                      'complete': 0,
                      'hidecross': 0,
                      'hasNFO': 0,
                      'poster': None,
                      'g[]': 85}
            check = _parse_feed('experimental', 'https://nzbindex.nl/search/rss', True, params)
            if check == 'disable':
                helpers.disable_provider('experimental')

        # DC++ Hub monitoring
        if dcpp_enabled:
            try:
                logger.fdebug('[RSS] Processing DC++ hub announcements...')
                dcpp_result = dcpp_hub_monitor(forcerss)
                if not dcpp_result:
                    logger.warn('[RSS] DC++ hub monitoring failed or returned no results')
            except Exception as e:
                logger.warn('[RSS] Error processing DC++ hub: %s' % e)
                import traceback
                logger.fdebug('[RSS] DC++ error traceback: %s' % traceback.format_exc())

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
                check = _parse_feed(site, url, bool(int(newznab_host[2])), params)
            else:
                url = newznab_host[1].rstrip() + '/rss'
                params = {'t':         str(newznabcat),
                          'dl':        '1',
                          'i':         str(newznabuid),
                          'r':         newznab_host[3].rstrip(),
                          'num':       '100'}

                check = _parse_feed(site, url, bool(int(newznab_host[2])), params)
                
                if check is not True:
                    logger.fdebug('RSS url returning error code. Attempting to use API to get most recent items in lieu of RSS feed')
                    url = newznab_host[1].rstrip() + '/api'
                    params = {'t':         'search',
                              'cat':       str(newznabcat),
                              'dl':        '1',
                              'apikey':    newznab_host[3].rstrip(),
                              'num':       '100'}
                    
                    check = _parse_feed(site, url, bool(int(newznab_host[2])), params)
                if check == 'disable':
                    helpers.disable_provider(site)

        feeddata = []

        for ft in feedthis:
            site = ft['site']
            logger.fdebug('[RSS] (' + site + ') now being updated...')
            for entry in ft['feed'].entries:
                if site == 'experimental':
                    size = entry.enclosures[0]['length']
                    link = entry.enclosures[0]['url']
                    titlename = experimental_cleaner(entry.title_detail['value'])
                    if titlename is None:
                        logger.fdebug('[EXPERIMENTAL][RSS_FEED] Not adding to rss entries. Cannot properly parse :%s' % entry.title)
                        continue
                else:
                    titlename = entry.title
                    size = 0
                    try:
                        # experimental, newznab
                        size = entry.enclosures[0]['length']
                    except Exception as e:
                        if 'newznab' in entry and 'size' in entry['newznab']:
                            size = entry['newznab']['size']

                    # Link
                    link = entry.link

                    #Remove the API keys from the url to allow for possible api key changes
                    filter_patterns = ['&i=[0-9a-zA-Z]+', '&r=[0-9a-zA-Z]+']
                    for pattern in filter_patterns:
                        link = re.sub(pattern, '', link).strip()

                feeddata.append({'Site': site,
                                 'Title': titlename,
                                 'Link': link,
                                 'Pubdate': entry.updated,
                                 'Size': size})

            logger.info('[RSS] (' + site + ') ' + str(len(ft['feed'].entries)) + ' entries indexed.')

        i = len(feeddata)
        if i:
            logger.info('[RSS] ' + str(i) + ' entries have been indexed and are now going to be stored for caching.')
            rssdbupdate(feeddata, i, 'usenet')

    return

def experimental_cleaner(rls):
    except_list=['releases', 'gold line', 'distribution', '0-day', '0 day', '0day', 'o-day', '.jpg', '.pdf']
    block_regex = r"\[\d{1,3}\/\d{1,3}\]"
    splitTitle = rls.split("\"")
    _digits = re.compile('\d')
    subcnt = 0
    filename = None
    for subs in splitTitle:
        if not (any(d in subs.lower() for d in except_list) or re.search(block_regex, subs)) and bool(_digits.search(subs)) is True:
            p = re.compile(r'\d{4}\-(0?[1-9]|1[012])\-(0?[1-9]|[12][0-9]|3[01])*')
            d = p.match(subs)
            if d:
                dtchk = d.group()
                if any(['2019' in dtchk, '2020' in dtchk, '2021' in dtchk, '2022' in dtchk]) and subcnt == 0:
                    subcnt += 1
                    continue
            filename = subs
            break
        subcnt+=1

    return filename

def rssdbupdate(feeddata, i, type):
    rsschktime = 15
    myDB = db.DBConnection()

    #let's add the entries into the db so as to save on searches
    #also to build up the ID's ;)

    for dataval in feeddata:

        if type == 'torrent':
            #we just store the torrent ID's now.

            newVal = {"Link": dataval['link'],
                      "Pubdate": dataval['pubdate'],
                      "Site": dataval['site'],
                      "Size": dataval['size']}
            ctrlVal = {"Title": dataval['title']}
            tmp_title = dataval['title']

        else:
            newlink = dataval['Link']
            newVal = {"Link": newlink,
                      "Pubdate": dataval['Pubdate'],
                      "Site": dataval['Site'],
                      "Size": dataval['Size']}
            ctrlVal = {"Title": dataval['Title']}
            tmp_title = dataval['Title']

        seriesname = None
        issuenumber = None
        flc = filechecker.FileChecker(file=tmp_title)
        filelist = flc.listFiles()
        if all([filelist['series_name'] != '', filelist['series_name'] is not None]) and filelist['issue_number'] != '-':
            issuenumber = filelist['issue_number']
            seriesname = re.sub(r'[\u2014|\u2013|\u2e3a|\u2e3b]', '-', filelist['series_name']).strip()
            if seriesname.endswith('-') and '#' in seriesname[-6:]:
                ck1 = seriesname.rfind('#')
                ck2 = seriesname.rfind('-')
                if seriesname[ck1+1:ck2-1].strip().isdigit():
                    issuenumber = '%s %s' % (seriesname[ck1:].strip(), issuenumber)
                    seriesname = seriesname[:ck1 -1].strip()
                    issuenumber.strip()

        newVal['ComicName'] = seriesname
        newVal['Issue_Number'] = issuenumber

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
    dresults = myDB.select("SELECT * FROM rssdb WHERE ComicName like ? COLLATE NOCASE AND Site='DDL(GetComics)'", [dsearch])
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
    logger.fdebug('[DDL][RSS][DB-QUERY] results: %s' % (ddltheinfo,))
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
            u_altsearchcomic = AS_Alter #.encode('ascii', 'ignore').strip()
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

def nzbdbsearch(seriesname, issue, comicid=None, nzbprov=None, searchYear=None, ComicVersion=None, oneoff=False, rsslist=None, provider_list=None):
    extensions = ('cbr', 'cbz')
    nzbtheinfo = []
    nzbinfo = {}

    myDB = db.DBConnection()
    seriesname_alt = None
    if any([comicid is None, comicid == 'None', oneoff is True ,rsslist is not None]):
        pass
    else:
        snm = myDB.selectone("SELECT * FROM comics WHERE comicid=?", [comicid]).fetchone()
        if snm is None:
            logger.info('Invalid ComicID of ' + str(comicid) + '. Aborting search.')
            return
        else:
            seriesname = snm['ComicName']
            seriesname_alt = snm['AlternateSearch']

    if rsslist is not None:
        conn = mylar.sql_db()
        cur = conn.cursor()
        logger.info('cur returned. db attached.')
        try:
            # if the VariableTable doesn't exist yet, this will fail. Let's go.
            cur.execute('DROP TABLE VariableTable')
        except Exception:
            pass
        else:
            logger.info('dropped previous rss dataset to ensure we have a clean slate.')
        cur.execute("CREATE TABLE IF NOT EXISTS VariableTable (ComicName TEXT, SQLquery_name TEXT collate nocase, Issue_Number TEXT, ComicYear TEXT, SeriesYear TEXT, Publisher TEXT, IssueDate TEXT, StoreDate TEXT, IssueID TEXT NOT NULL UNIQUE, AlternateSearch TEXT collate nocase, UseFuzzy TEXT, ComicVersion TEXT, SARC TEXT, IssueArcID TEXT, searchmode TEXT, RSS TEXT, ComicID TEXT, ComicName_Filesafe TEXT, AllowPacks TEXT, OneOff INT, TorrentID_32P TEXT, DigitalDate TEXT, BookType TEXT, Ignore_Booktype TEXT)")
        #logger.info('rsslist: %s' % (rsslist))

        #curline = "INSERT INTO VariableTable (Variable) VALUES ({seq})".format(seq=','.join(['?'] *(len(rsslist))))
        try:
            cur.executemany("INSERT OR IGNORE INTO VariableTable (ComicName, SQLquery_name, Issue_Number, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, IssueID, AlternateSearch, UseFuzzy, ComicVersion, SARC, IssueArcID, searchmode, RSS, ComicID, ComicName_Filesafe, AllowPacks, OneOff, TorrentID_32P, DigitalDate, booktype, ignore_booktype) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rsslist)
            #cur.executemany(curline, rsslist)
            conn.commit()
            cur.close()
        except Exception as e:
            logger.warn('error: %s' % e)
            cur.close()
        else:
            logger.info('executed insert...now attempting to select')

        #wanted_check = myDB.select("SELECT ComicName, SQLQuery_name, Issue_Number FROM VariableTable LIMIT 10")
        #for w in wanted_check:
        #    print(f"WANTED: '{w['ComicName']}' (SQLQuery: '{w['SQLQuery_name']}') #{w['Issue_Number']}")

        tcnt = myDB.select("SELECT COUNT(*) as count FROM rssdb")
        totalcnt = tcnt[0][0]
        cnt = 0

        #debug_matches = myDB.select("SELECT DISTINCT r.ComicName as RSS_ComicName, r.Issue_Number as RSS_IssueNumber, r.Title, r.Site, v.ComicName as WANTED_ComicName, v.SQLQuery_name, v.Issue_Number as WANTED_Issue FROM rssdb r join VariableTable v on r.Title like '%' || v.SQLQuery_name || '%' WHERE (r.ComicName like '%' || v.SQLQuery_name || '%' and v.SQLQuery_name is not NULL) AND (v.Issue_Number = r.Issue_Number OR CAST(v.Issue_Number AS INTEGER) = CAST(r.Issue_Number AS INTEGER))")
        #for match in debug_matches:
            #print(f"MATCH: Wanted='{match['WANTED_ComicName']}' (SQLQuery='{match['SQLQuery_name']}') #{match['WANTED_Issue']} <-> RSS='{match['RSS_ComicName']}' #{match['RSS_IssueNumber']} [{match['Site']}] Title='{match['Title']}'")
        #print(f"Total matches found: {len(debug_matches)}")

        for nzb in myDB.select("SELECT DISTINCT r.ComicName as RSS_ComicName, r.Issue_Number as RSS_IssueNumber, r.Title, r.Link, r.Pubdate, r.Size, r.Site, v.* FROM rssdb r join VariableTable v on r.Title like '%' || v.SQLQuery_name || '%' WHERE (r.ComicName like '%' || v.SQLQuery_name || '%' and v.SQLQuery_name is not NULL) AND (v.Issue_Number = r.Issue_Number OR CAST(v.Issue_Number AS INTEGER) = CAST(r.Issue_Number AS INTEGER))"):
            cnt+=1
            nzbTITLE = re.sub('&amp;', '&', nzb['Title']).strip()
            nzbTITLE = re.sub('&#39;', '\'', nzbTITLE).strip()
            #logger.info('tor[Title]: %s' % tor['Title'])
            if mylar.CONFIG.PREFERRED_QUALITY == 1:
                if 'cbr' not in nzbTITLE:
                    logger.fdebug('Quality restriction enforced [ cbr only ]. Rejecting result.')
                    continue
            elif mylar.CONFIG.PREFERRED_QUALITY == 2:
                if 'cbz' not in nzbTITLE:
                    logger.fdebug('Quality restriction enforced [ cbz only ]. Rejecting result.')
                    continue
            i=0
            if provider_list is not None:
                if not any(nzb['Site'] in olist for olist in provider_list['prov_order']) or helpers.block_provider_check(nzb['Site']):
                    continue

            else:
                if nzbprov is not None:
                    if nzbprov != nzb['Site'] or not mylar.CONFIG.ENABLE_NEWZNABS:
                        #logger.fdebug('this is a result from ' + str(tor['Site']) + ', not the site I am looking for of ' + str(nzbprov))
                        continue

            #0 holds the title/issue and format-type.
            fmod = mylar.filechecker.FileChecker()
            formatrem_seriesname = fmod.dynamic_replace(nzb['ComicName'])['mod_seriesname']
            formatrem_nzbsplit = fmod.dynamic_replace(nzbTITLE)['mod_seriesname']
            if formatrem_seriesname.lower() in formatrem_nzbsplit.lower(): # or any(x.lower() in formatrem_torsplit.lower() for x in AS_Alt):
                #logger.fdebug('matched to : %s' % nzbTITLE)
                #logger.fdebug('matched on series title: %s' % nzb['ComicName'])
                titleend = formatrem_nzbsplit[len(formatrem_seriesname):]
                titleend = re.sub('\-', '', titleend)   #remove the '-' which is unnecessary
                #remove extensions
                titleend = re.sub('cbr', '', titleend)
                titleend = re.sub('cbz', '', titleend)
                titleend = re.sub('none', '', titleend)
                #logger.fdebug('titleend: ' + titleend)

                sptitle = titleend.split()
                extra = ''

                issues = None
                pack = False
                if nzb['Site'] == 'DDL(GetComics)':
                    # see if it's a pack type
                    ddl_check = ddlrss_pack_detect(nzbTITLE, nzb['Link'])
                    if ddl_check is not None:
                        nzbTITLE = ddl_check['title']
                        issues = ddl_check['issues']
                        pack = ddl_check['pack']

                nzbtheinfo.append({
                              'title':   nzbTITLE, #cttitle,
                              'link':    nzb['Link'],
                              'pubdate': nzb['Pubdate'],
                              'site':    nzb['Site'],
                              'length':  nzb['Size'],
                              'issues':  issues,
                              'pack':    pack,
                              'info':    {'ComicName': nzb['ComicName'],
                                          'Issue_Number': nzb['Issue_Number'],
                                          'ComicYear': nzb['ComicYear'],
                                          'SeriesYear': nzb['SeriesYear'],
                                          'Publisher': nzb['Publisher'],
                                          'IssueDate': nzb['IssueDate'],
                                          'StoreDate': nzb['StoreDate'],
                                          'IssueID': nzb['IssueID'],
                                          'AlternateSearch': nzb['AlternateSearch'],
                                          'UseFuzzy': nzb['UseFuzzy'],
                                          'ComicVersion': nzb['ComicVersion'],
                                          'SARC': nzb['SARC'],
                                          'IssueArcID': nzb['IssueARCID'],
                                          'searchmode': nzb['searchmode'],
                                          'RSS': nzb['RSS'],
                                          'ComicID': nzb['ComicID'],
                                          'ComicName_Filesafe': nzb['ComicName_Filesafe'],
                                          'AllowPacks': bool(nzb['AllowPacks']),
                                          'OneOff': bool(nzb['OneOff']),
                                          'TorrentID_32P': nzb['TorrentID_32P'],
                                          'DigitalDate': nzb['DigitalDate'],
                                          'booktype': nzb['booktype'],
                                          'ignore_booktype': bool(nzb['ignore_booktype'])},
                              })
        #logger.info('nzbinfo: %s' % nzbtheinfo)
        logger.info('[RSS-QUERY] Searched through RSSDB looking for %s Wanted items in %s RSS entries. Rough matching to %s items.' % (len(rsslist), totalcnt, len(nzbtheinfo)))
    else:
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

    # Sort results by provider order if available so that results can be taken in priority order
    # TODO Would prefer to do this using the passed provider_list but it has the prov_order with additional string manipulation.
    # Ideally loop back at some point to add a raw order to the generator function
    if mylar.CONFIG.PROVIDER_ORDER is not None and isinstance(mylar.CONFIG.PROVIDER_ORDER, dict):
        nzbtheinfo = sorted(nzbtheinfo,
                            key=lambda x:
                                list(mylar.CONFIG.PROVIDER_ORDER.values()).index(x['site'])
                                if x['site'] in mylar.CONFIG.PROVIDER_ORDER.values()
                                else 99999)
    
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
            elif mylar.KEYS_32P is None:
                logger.fdebug('[32P-AUTHENTICATION] 32P (Auth Mode) Authentication enabled. Keys have not been established yet, attempting to gather.')
                feed32p = auth32p.info32p(reauthenticate=True)
                feedinfo = feed32p.authenticate()
                if feedinfo['status'] is False or feedinfo['status_msg'] == "disable":
                    helpers.disable_provider('32P')
                    return "fail"
                if mylar.KEYS_32P is None:
                    logger.error('[RSS] Unable to sign-on to 32P to validate settings and initiate download sequence. Please enter/check your username password in the configuration.')
                    return "fail"
            else:
                logger.fdebug('[32P-AUTHENTICATION] 32P (Auth Mode) Authentication already done. Attempting to use existing keys.')

        if mylar.KEYS_32P:
            #keys_32p will be set for auth mode
            auth_key = mylar.KEYS_32P['auth']
            pass_key = mylar.KEYS_32P['passkey']
        else:
            #authkey_32p & passkey_32p are set for legacy mode
            auth_key = mylar.AUTHKEY_32P
            pass_key = mylar.CONFIG.PASSKEY_32P
        payload = {'action':       'download',
                   'torrent_pass': pass_key,
                   'authkey':      auth_key,
                   'id':           linkit}

        dfile = auth32p.info32p()
        file_download = dfile.downloadfile(payload, filepath)
        if file_download['status'] is False:
            helpers.disable_provider('32P')

        if file_download['download_bool'] is False:
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
                    cf_cookievalue, cf_user_agent = scraper.get_tokens(url, user_agent=mylar.CV_HEADERS['User-Agent'])
                    mylar.WWT_CF_COOKIEVALUE = cf_cookievalue
                r = scraper.get(url, params=payload, cookies=mylar.WWT_CF_COOKIEVALUE, verify=verify, stream=True, headers=headers)
            else:
                if url.startswith('magnet'):
                    logger.info("Magnet url do not scrape.")
                    linkit = filepath = url
                    logger.fdebug('Grabbed magnet link: %s' + linkit)
                else:
                    r = scraper.get(url, params=payload, verify=verify, stream=True, headers=headers, allow_redirects=False)
                    if r.status_code in REDIRECT_STATUS_CODES:
                        redir_url = r.headers['Location']
                        if redir_url.startswith('magnet'):
                            logger.info("Got a magnet url from redirect.")
                            linkit = filepath = redir_url
                            logger.fdebug('Grabbed magnet link: %s' + linkit)
                        else:
                            r = scraper.get(redir_url, stream=True)
        except Exception as e:
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

        if not filepath.startswith('magnet:'):
            if any([site == 'DEM', site == 'WWT']) and any([str(r.status_code) == '403', str(r.status_code) == '404', str(r.status_code) == '503']):
                if str(r.status_code) != '503':
                    logger.warn('Unable to download from ' + site + ' [' + str(r.status_code) + ']')
                    #retry with the alternate torrent link.
                    url = helpers.torrent_create(site, linkit, True)
                    logger.fdebug('Trying alternate url: ' + str(url))
                    try:
                        r = requests.get(url, params=payload, verify=verify, stream=True, headers=headers)

                    except Exception as e:
                        return "fail"
                else:
                    logger.warn('Cloudflare protection online for ' + site + '. Attempting to bypass...')
                    try:
                        scraper = cfscrape.create_scraper()
                        cf_cookievalue, cf_user_agent = cfscrape.get_cookie_string(url)
                        headers = {'Accept-encoding': 'gzip',
                                'User-Agent':       cf_user_agent}

                        r = scraper.get(url, verify=verify, cookies=cf_cookievalue, stream=True, headers=headers)
                    except Exception as e:
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
        if linkit.startswith('magnet'):
            logger.fdebug('Sending magnet to uTorrent: %s' % linkit)
            ti = uTC.addurl(linkit)
        else:
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
        from . import test
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

def ddlrss_pack_detect(title, link):
    issues = None
    pack = False
    issfind_st = title.find('#')
    issfind_en = title.find('-', issfind_st)
    if issfind_en != -1:
        if all([title[issfind_en + 1] == ' ', title[issfind_en + 2].isdigit()]):
            iss_en = title.find(' ', issfind_en + 2)
            if iss_en != -1:
                 issues = title[issfind_st + 1 : iss_en]
                 pack = True
        if title[issfind_en + 1].isdigit():
            iss_en = title.find(' ', issfind_en + 1)
            if iss_en != -1:
                issues = title[issfind_st + 1 : iss_en]
                pack = True

    # to handle packs that are denoted without a # sign being present.
    # if there's a dash, check to see if both sides of the dash are numeric.
    if pack is False and title.find('-') != -1:
        issfind_en = title.find('-')
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
            dashfind = title.find('-')
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
    if pack is True:
        try:
            title = re.sub(issues, '', title).strip()
        # kill any brackets in the issue line here.
            issues = re.sub(r'[\(\)\[\]]', '', issues).strip()
        except Exception as e:
            return
        else:
            if title.endswith('#'):
                title = title[:-1].strip()

        return {'title': title, 'issues': issues, 'pack': pack, 'link': link}
    else:
        return

def dcpp_get_hub_session_id(session, api_url, headers, hub_address):
    """
    Get the session ID for a specific hub
    """
    try:
        logger.fdebug('[AIRDCPP][RSS] Looking for hub session ID for: %s' % hub_address)
        response = session.get(f"{api_url}/hubs", headers=headers, timeout=30)
        if response.status_code == 200:
            hubs = response.json()
            logger.fdebug('[AIRDCPP][RSS] Found %s active hub sessions' % len(hubs))

            for hub in hubs:
                hub_url = hub.get('hub_url', '')
                hub_name = hub.get('identity', {}).get('name', '')
                hub_id = hub.get('id')

                logger.fdebug('[AIRDCPP][RSS] Checking hub: %s (name: %s, id: %s)' % (hub_url, hub_name, hub_id))

                # Match either by hub_url or hub name
                if hub_url == hub_address or hub_name == hub_address:
                    logger.fdebug('[AIRDCPP][RSS] Found matching hub session: %s' % hub_id)
                    return hub_id

            logger.warn('[AIRDCPP][RSS] No matching hub found for: %s' % hub_address)
        else:
            logger.warn('[AIRDCPP][RSS] Failed to get hub list: %s - %s' % (response.status_code, response.text))
        return None
    except Exception as e:
        logger.warn('[AIRDCPP][RSS] Error getting hub session ID: %s' % e)
        return None

def dcpp_hub_monitor(forcerss=False):
    """
    Monitor DC++ hub messages for comic announcements, similar to RSS feeds
    """

    if not hasattr(mylar.CONFIG, 'AIRDCPP_ANNOUNCE_HUB') or not mylar.CONFIG.AIRDCPP_ANNOUNCE_HUB:
        logger.error('[AIRDCPP][RSS] No announce hub configured for monitoring')
        return False

    if not hasattr(mylar.CONFIG, 'AIRDCPP_ANNOUNCE_BOTS') or not mylar.CONFIG.AIRDCPP_ANNOUNCE_BOTS:
        logger.fdebug('[AIRDCPP][RSS] No announce bots configured for monitoring')
        return False

    logger.info('[AIRDCPP][RSS] Monitoring hub messages for comic announcements...')

    # Set up session similar to AirDCPP class
    session = requests.Session()
    headers = {'User-Agent': mylar.USER_AGENT}

    api_url = mylar.CONFIG.AIRDCPP_HOST
    if not api_url.endswith('/'):
        api_url += '/'
    api_url += 'api/v1'

    if mylar.CONFIG.AIRDCPP_USERNAME and mylar.CONFIG.AIRDCPP_PASSWORD:
        session.auth = (mylar.CONFIG.AIRDCPP_USERNAME, mylar.CONFIG.AIRDCPP_PASSWORD)

    try:
        # Get hub session ID first
        session_id = dcpp_get_hub_session_id(session, api_url, headers, mylar.CONFIG.AIRDCPP_ANNOUNCE_HUB)

        if not session_id:
            logger.warn(
                '[AIRDCPP][RSS] Could not get session ID for announce hub: %s' % mylar.CONFIG.AIRDCPP_ANNOUNCE_HUB)
            return False

        logger.info(
            '[AIRDCPP][RSS] Found hub session ID: %s for hub: %s' % (session_id, mylar.CONFIG.AIRDCPP_ANNOUNCE_HUB))

        # Get recent messages from the hub
        max_count = "100" if forcerss else "50"
        url = f"{api_url}/hubs/{session_id}/messages/{max_count}"

        logger.fdebug('[AIRDCPP][RSS] Fetching messages from: %s' % url)
        response = session.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            logger.warn('[AIRDCPP][RSS] Failed to get hub messages: %s - %s' % (response.status_code, response.text))
            return False

        # Handle both list and direct dict responses
        messages = response.json()
        if isinstance(messages, list):
            msg_list = messages
        else:
            msg_list = [messages]

        logger.info('[AIRDCPP][RSS] Retrieved %s messages from hub' % len(msg_list))

        comic_announcements = []
        announce_bots = [bot.strip() for bot in mylar.CONFIG.AIRDCPP_ANNOUNCE_BOTS.split(',')]

        chat_messages = 0
        log_messages = 0
        bot_messages = 0

        for message in msg_list:
            if 'chat_message' in message:
                chat_messages += 1
                sender = message['chat_message'].get('from', {}).get('nick', 'Unknown')
                if sender in announce_bots:
                    bot_messages += 1
                    logger.fdebug('[AIRDCPP][RSS] Found message from announce bot %s: %s' % (sender, message['chat_message'].get('text', '')[:200]))
                    parsed_announcement = dcpp_parse_hub_message(message)
                    if parsed_announcement:
                        comic_announcements.append(parsed_announcement)
                        logger.fdebug('[AIRDCPP][RSS] Parsed comic announcement: %s' % parsed_announcement['Title'])
            elif 'log_message' in message:
                log_messages += 1

        logger.info('[AIRDCPP][RSS] Message summary: %s total, %s chat, %s log, %s from bots, %s comic announcements' %
                    (len(msg_list), chat_messages, log_messages, bot_messages, len(comic_announcements)))

        if comic_announcements:
            logger.info(
                '[AIRDCPP][RSS] Found %s comic announcements, storing in RSS database' % len(comic_announcements))
            rssdbupdate(comic_announcements, len(comic_announcements), 'dcpp')
        else:
            logger.fdebug('[AIRDCPP][RSS] No comic announcements found in recent messages')

        return True

    except Exception as e:
        logger.warn('[AIRDCPP][RSS] Error monitoring hub messages: %s' % e)
        import traceback
        logger.fdebug('[AIRDCPP][RSS] Full error traceback: %s' % traceback.format_exc())
        return False

def dcpp_parse_hub_message(message):
    """
    Parse a hub message to extract comic information
    Similar to how RSS entries are parsed
    """
    try:
        # Skip log messages, only process chat messages
        if 'log_message' in message:
            return None

        if 'chat_message' not in message:
            return None

        chat_msg = message['chat_message']
        text = chat_msg.get('text', '')
        sender = chat_msg.get('from', {}).get('nick', 'Unknown')
        timestamp = chat_msg.get('time', 0)

        # Only process messages from configured announce bots if present
        announce_bots = [bot.strip() for bot in mylar.CONFIG.AIRDCPP_ANNOUNCE_BOTS.split(',')]
        if sender not in announce_bots:
            logger.fdebug('[AIRDCPP][RSS] Skipping message from %s (not in announce bots list)' % sender)
            return None

        logger.fdebug('[AIRDCPP][RSS] Processing message from announce bot: %s' % sender)

        # Convert timestamp to proper date format
        try:
            msg_date = datetime.fromtimestamp(timestamp).strftime('%a, %d %b %Y %H:%M:%S GMT')
        except:
            msg_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')

        # Check if message contains comic file extensions
        if not any(ext in text.lower() for ext in ['.cbr', '.cbz']):
            logger.fdebug('[AIRDCPP][RSS] Message does not contain comic file extensions')
            return None

        # Extract magnet link and filename from highlights if available
        magnet_link = None
        filename = None
        size_bytes = 0
        category = None

        # First try to get magnet link from highlights (most reliable)
        highlights = chat_msg.get('highlights', [])
        for highlight in highlights:
            if highlight.get('tag') in ['magnet', 'url']:
                magnet_link = highlight.get('text', '')
                logger.fdebug('[AIRDCPP][RSS] Found magnet link in highlights: %s' % magnet_link[:100])
                break

        # If no magnet in highlights, try to extract from text
        if not magnet_link:
            magnet_match = re.search(r'(magnet:\?[^\s]+)', text)
            if magnet_match:
                magnet_link = magnet_match.group(1)
                logger.fdebug('[AIRDCPP][RSS] Found magnet link in text: %s' % magnet_link[:100])

        if magnet_link:
            # Extract filename from magnet link dn parameter
            dn_match = re.search(r'&dn=([^&]+)', magnet_link)
            if dn_match:
                filename = urllib.parse.unquote_plus(dn_match.group(1))
                logger.fdebug('[AIRDCPP][RSS] Extracted filename: %s' % filename)

            # Extract size from xl parameter (exact length in bytes)
            xl_match = re.search(r'&xl=(\d+)', magnet_link)
            if xl_match:
                size_bytes = int(xl_match.group(1))
                logger.fdebug('[AIRDCPP][RSS] Extracted size: %s bytes' % size_bytes)

        # Extract category from message text [Category]
        category_match = re.match(r'\[([^\]]+)\]', text)
        if category_match:
            category = category_match.group(1)
            logger.fdebug('[AIRDCPP][RSS] Extracted category: %s' % category)

        if not filename:
            logger.warn('[AIRDCPP][RSS] Could not extract filename from message: %s' % text)
            return None

        # Parse filename using existing FileChecker
        try:
            flc = filechecker.FileChecker(file=filename)
            filelist = flc.listFiles()
            logger.fdebug('[AIRDCPP][RSS] FileChecker results: %s' % filelist)
        except Exception as e:
            logger.warn('[AIRDCPP][RSS] FileChecker failed for %s: %s' % (filename, e))
            # Create a basic filelist if FileChecker fails
            filelist = {
                'series_name': None,
                'issue_number': None
            }

        # Create a unique link/ID for this announcement using magnet hash
        if magnet_link:
            # Extract TTH hash from magnet link for unique ID
            tth_match = re.search(r'urn:tree:tiger:([A-Z0-9]+)', magnet_link)
            if tth_match:
                link_id = tth_match.group(1)  # Use TTH hash as unique ID
            else:
                import hashlib
                link_id = hashlib.md5(f"{sender}_{timestamp}_{filename}".encode()).hexdigest()
        else:
            import hashlib
            link_id = hashlib.md5(f"{sender}_{timestamp}_{filename}".encode()).hexdigest()

        announcement = {
            'Title': filename,
            'Link': link_id,  # TTH hash or unique identifier
            'Pubdate': msg_date,
            'Site': 'AirDCPP',
            'Size': size_bytes,
            'ComicName': filelist.get('series_name'),
            'Issue_Number': filelist.get('issue_number'),
            'Hub_Sender': sender,
            'Hub_Message': text,
            'Hub_Category': category,
            'Magnet_Link': magnet_link,
            'Original_Filename': filename
        }

        logger.fdebug('[AIRDCPP][RSS] Successfully parsed comic: %s (Category: %s, Size: %s bytes)' % (filename, category, size_bytes))

        return announcement

    except Exception as e:
        logger.fdebug('[AIRDCPP][RSS] Error parsing hub message: %s' % e)
        import traceback
        logger.fdebug('[AIRDCPP][RSS] Full error traceback: %s' % traceback.format_exc())
        return None