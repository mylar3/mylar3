#!/usr/bin/python

import os, sys
import re
import lib.feedparser as feedparser
import lib.requests as requests
import ftpsshup
import datetime
import gzip
from StringIO import StringIO

import mylar
from mylar import db, logger, ftpsshup, helpers, auth32p


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

    if mylar.KAT_PROXY:
        if mylar.KAT_PROXY.endswith('/'):
            kat_url = mylar.KAT_PROXY
        else:
            kat_url = mylar.KAT_PROXY + '/'
    else:
        #switched to https.
        kat_url = 'https://kat.cr/'

    if pickfeed == 'KAT':
        #we need to cycle through both categories (comics & other) - so we loop.
        loopit = 2
    else:
        loopit = 1

    lp = 0
    totalcount = 0

    title = []
    link = []
    description = []
    seriestitle = []

    feeddata = []
    myDB = db.DBConnection()
    torthekat = []
    torthe32p = []
    torinfo = {}

    while (lp < loopit):
        if lp == 0 and loopit == 2:
            pickfeed = '2'
        elif lp == 1 and loopit == 2:
            pickfeed = '5'

        feedtype = None

        if pickfeed == "1" and mylar.ENABLE_32P:  # 32pages new releases feed.
            feed = 'https://32pag.es/feeds.php?feed=torrents_all&user=' + feedinfo['user'] + '&auth=' + feedinfo['auth'] + '&passkey=' + feedinfo['passkey'] + '&authkey=' + feedinfo['authkey']
            feedtype = ' from the New Releases RSS Feed for comics'
            verify = bool(mylar.VERIFY_32P)
        elif pickfeed == "2" and srchterm is not None:    # kat.ph search
            feed = kat_url + "usearch/" + str(srchterm) + "%20category%3Acomics%20seeds%3A" + str(mylar.MINSEEDS) + "/?rss=1"
            verify = bool(mylar.KAT_VERIFY)
        elif pickfeed == "3":    # kat.ph rss feed
            feed = kat_url + "usearch/category%3Acomics%20seeds%3A" + str(mylar.MINSEEDS) + "/?rss=1"
            feedtype = ' from the New Releases RSS Feed for comics'
            verify = bool(mylar.KAT_VERIFY)
        elif pickfeed == "4":    #32p search
            if any([mylar.USERNAME_32P is None, mylar.USERNAME_32P == '', mylar.PASSWORD_32P is None, mylar.PASSWORD_32P == '']):
                logger.error('[RSS] Warning - you NEED to enter in your 32P Username and Password to use this option.')
                lp=+1
                continue
            if mylar.MODE_32P == 0:
                logger.warn('[32P] Searching is not available in 32p Legacy mode. Switch to Auth mode to use the search functionality.')
                lp=+1
                continue
            return
        elif pickfeed == "5" and srchterm is not None:  # kat.ph search (category:other since some 0-day comics initially get thrown there until categorized)
            feed = kat_url + "usearch/" + str(srchterm) + "%20category%3Aother%20seeds%3A1/?rss=1"
            verify = bool(mylar.KAT_VERIFY)
        elif pickfeed == "6":    # kat.ph rss feed (category:other so that we can get them quicker if need-be)
            feed = kat_url + "usearch/.cbr%20category%3Aother%20seeds%3A" + str(mylar.MINSEEDS) + "/?rss=1"
            feedtype = ' from the New Releases for category Other RSS Feed that contain comics'
            verify = bool(mylar.KAT_VERIFY)
        elif int(pickfeed) >= 7 and feedinfo is not None:
            #personal 32P notification feeds.
            #get the info here
            feed = 'https://32pag.es/feeds.php?feed=' + feedinfo['feed'] + '&user=' + feedinfo['user'] + '&auth=' + feedinfo['auth'] + '&passkey=' + feedinfo['passkey'] + '&authkey=' + feedinfo['authkey'] + '&name=' + feedinfo['feedname']
            feedtype = ' from your Personal Notification Feed : ' + feedinfo['feedname']
            verify = bool(mylar.VERIFY_32P)
        else:
            logger.error('invalid pickfeed denoted...')
            return

        if pickfeed == "3" or pickfeed == "6" or pickfeed == "2" or pickfeed == "5":
            picksite = 'KAT'
        elif pickfeed == "1" or pickfeed == "4" or int(pickfeed) > 7:
            picksite = '32P'

        if pickfeed != '4':
            payload = None

            try:
                r = requests.get(feed, params=payload, verify=verify)
            except Exception, e:
                logger.warn('Error fetching RSS Feed Data from %s: %s' % (picksite, e))
                return

            feedme = feedparser.parse(r.content)
            #feedme = feedparser.parse(feed)


        i = 0

        if pickfeed == '4':
            for entry in searchresults['entries']:
                justdigits = entry['file_size'] #size not available in follow-list rss feed
                seeddigits = entry['seeders']  #number of seeders not available in follow-list rss feed

                if int(seeddigits) >= int(mylar.MINSEEDS):
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
        else:
            for entry in feedme['entries']:
                if any([pickfeed == "3", pickfeed == "6"]):
                    tmpsz = feedme.entries[i].enclosures[0]
                    feeddata.append({
                                    'site':     picksite,
                                    'title':    feedme.entries[i].title,
                                    'link':     tmpsz['url'],
                                    'pubdate':  feedme.entries[i].updated,
                                    'size':     tmpsz['length']
                                    })
                elif any([pickfeed == "2", pickfeed == "5"]):
                    tmpsz = feedme.entries[i].enclosures[0]
                    torthekat.append({
                                    'site':     picksite,
                                    'title':    feedme.entries[i].title,
                                    'link':     tmpsz['url'],
                                    'pubdate':  feedme.entries[i].updated,
                                    'size':     tmpsz['length']
                                    })
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

                    #break it down to get the Size since it's available on THIS 32P feed only so far.
                    #when it becomes available in the new feeds, this will be working, for now it just nulls out.
                    sizestart = tmpdesc.find('Size:')
                    justdigits = 0
                    if sizestart >= 0:
                        sizeend = tmpdesc.find('Leechers:')
                        sizestart +=5  # to get to the end of the word 'Size:'
                        tmpsize = tmpdesc[sizestart:sizeend].strip()
                        fdigits = re.sub("[^0123456789\.]", "", tmpsize).strip()
                        if '.' in fdigits:
                            decfind = fdigits.find('.')
                            wholenum = fdigits[:decfind]
                            decnum = fdigits[decfind +1:]
                        else:
                            wholenum = fdigits
                        decnum = 0
                        if 'MB' in tmpsize:
                            wholebytes = int(wholenum) * 1048576
                            wholedecimal = (int(decnum) * 1048576) / 100
                            justdigits = wholebytes + wholedecimal
                        else:
                            #it's 'GB' then
                            wholebytes = (int(wholenum) * 1024) * 1048576
                            wholedecimal = ((int(decnum) * 1024) * 1048576) / 100
                            justdigits = wholebytes + wholedecimal
                    #this is not currently working for 32p
                    #Get the # of seeders.
                    #seedstart = tmpdesc.find('Seeders:')
                    #seedend = tmpdesc.find('Added:')
                    #seedstart +=8  # to get to the end of the word 'Seeders:'
                    #tmpseed = tmpdesc[seedstart:seedend].strip()
                    #seeddigits = re.sub("[^0123456789\.]", "", tmpseed).strip()
                    seeddigits = 0

                    if int(mylar.MINSEEDS) >= int(seeddigits):
                        link = feedme.entries[i].link
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
            torinfo['entries'] = torthekat
        return torinfo
    return


def nzbs(provider=None, forcerss=False):

    feedthis = []

    def _parse_feed(site, url, verify):
        logger.fdebug('[RSS] Fetching items from ' + site)
        payload = None
        headers = {'User-Agent':      str(mylar.USER_AGENT)}

        try:
            r = requests.get(url, params=payload, verify=verify, headers=headers)
        except Exception, e:
            logger.warn('Error fetching RSS Feed Data from %s: %s' % (site, e))
            return

        feedme = feedparser.parse(r.content)

        feedthis.append({"site": site,
                         "feed": feedme})

    newznab_hosts = []

    if mylar.NEWZNAB == 1:
        for newznab_host in mylar.EXTRA_NEWZNABS:
            logger.fdebug('[RSS] newznab name: ' + str(newznab_host[0]) + ' - enabled: ' + str(newznab_host[5]))
            if str(newznab_host[5]) == '1':
                newznab_hosts.append(newznab_host)

    providercount = len(newznab_hosts) + int(mylar.EXPERIMENTAL == 1) + int(mylar.NZBSU == 1) + int(mylar.DOGNZB == 1)
    logger.fdebug('[RSS] You have enabled ' + str(providercount) + ' NZB RSS search providers.')

    if mylar.EXPERIMENTAL == 1:
        max_entries = "250" if forcerss else "50"
        _parse_feed('experimental', 'http://nzbindex.nl/rss/alt.binaries.comics.dcp/?sort=agedesc&max=' + max_entries + '&more=1', False)

    if mylar.NZBSU == 1:
        num_items = "&num=100" if forcerss else ""  # default is 25
        _parse_feed('nzb.su', 'http://api.nzb.su/rss?t=7030&dl=1&i=' + (mylar.NZBSU_UID or '1') + '&r=' + mylar.NZBSU_APIKEY + num_items, bool(mylar.NZBSU_VERIFY))

    if mylar.DOGNZB == 1:
        num_items = "&num=100" if forcerss else ""  # default is 25
        _parse_feed('dognzb', 'https://dognzb.cr/rss.cfm?r=' + mylar.DOGNZB_APIKEY + '&t=7030' + num_items, bool(mylar.DOGNZB_VERIFY))

    for newznab_host in newznab_hosts:
        site = newznab_host[0].rstrip()
        (newznabuid, _, newznabcat) = (newznab_host[4] or '').partition('#')
        newznabuid = newznabuid or '1'
        newznabcat = newznabcat or '7030'

        # 11-21-2014: added &num=100 to return 100 results (or maximum) - unsure of cross-reliablity
        _parse_feed(site, newznab_host[1].rstrip() + '/rss?t=' + str(newznabcat) + '&dl=1&i=' + str(newznabuid) + '&num=100&r=' + newznab_host[3].rstrip(), bool(newznab_host[2]))

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
                    link = re.sub(mylar.DOGNZB_APIKEY, '', link).strip()
                else:
                    link = link[:link.find('&i=')].strip()

            feeddata.append({'Site': site,
                             'Title': entry.title,
                             'Link': link,
                             'Pubdate': entry.updated,
                             'Size': size})

            # logger.fdebug("    Site: " + site)
            # logger.fdebug("    Title: " + entry.title)
            # logger.fdebug("    Link: " + link)
            # logger.fdebug("    pubdate: " + entry.updated)
            # logger.fdebug("    size: " + size)

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
            if dataval['site'] == '32P':
                newlink = dataval['link']
            else:
                #store the hash/id from KAT
                newlink = os.path.basename(re.sub('.torrent', '', dataval['link'][:dataval['link'].find('?title')]))

            newVal = {"Link":      newlink,
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

    logger.fdebug('Completed adding new data to RSS DB. Next add in ' + str(mylar.RSS_CHECKINTERVAL) + ' minutes')
    return


def torrentdbsearch(seriesname, issue, comicid=None, nzbprov=None):
    myDB = db.DBConnection()
    seriesname_alt = None
    if comicid is None or comicid == 'None':
        pass
    else:
        logger.fdebug('ComicID: ' + str(comicid))
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
    tsearch_seriesname = re.sub('[\'\!\@\#\$\%\:\-\;\/\\=\?\&\.\s]', '%', tsearch_removed)
    if mylar.PREFERRED_QUALITY == 0:
        tsearch = tsearch_seriesname + "%"
    elif mylar.PREFERRED_QUALITY == 1:
        tsearch = tsearch_seriesname + "%cbr%"
    elif mylar.PREFERRED_QUALITY == 2:
        tsearch = tsearch_seriesname + "%cbz%"
    else:
        tsearch = tsearch_seriesname + "%"

    logger.fdebug('tsearch : ' + tsearch)
    AS_Alt = []
    tresults = []
    tsearch = '%' + tsearch

    if mylar.ENABLE_32P:
        tresults = myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='32P'", [tsearch])
    if mylar.ENABLE_KAT:
        tresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='KAT'", [tsearch])

    logger.fdebug('seriesname_alt:' + str(seriesname_alt))
    if seriesname_alt is None or seriesname_alt == 'None':
        if tresults is None:
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
            AS_formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.]', '', AS_Altrem_mod)
            AS_formatrem_seriesname = re.sub('\s+', ' ', AS_formatrem_seriesname)
            if AS_formatrem_seriesname[:1] == ' ': AS_formatrem_seriesname = AS_formatrem_seriesname[1:]
            AS_Alt.append(AS_formatrem_seriesname)

            if mylar.PREFERRED_QUALITY == 0:
                 AS_Alternate += "%"
            elif mylar.PREFERRED_QUALITY == 1:
                 AS_Alternate += "%cbr%"
            elif mylar.PREFERRED_QUALITY == 2:
                 AS_Alternate += "%cbz%"
            else:
                 AS_Alternate += "%"

            AS_Alternate = '%' + AS_Alternate
            if mylar.ENABLE_32P:
                tresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='32P'", [AS_Alternate])
            if mylar.ENABLE_KAT:
                tresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='KAT'", [AS_Alternate])

    if tresults is None:
        logger.fdebug('torrent search returned no results for ' + seriesname)
        return "no results"

    extensions = ('cbr', 'cbz')
    tortheinfo = []
    torinfo = {}

    for tor in tresults:
        #&amp; have been brought into the title field incorretly occassionally - patched now, but to include those entries already in the 
        #cache db that have the incorrect entry, we'll adjust.
        torTITLE = re.sub('&amp;', '&', tor['Title']).strip()

        torsplit = torTITLE.split('/')
        if mylar.PREFERRED_QUALITY == 1:
            if 'cbr' in torTITLE:
                logger.fdebug('Quality restriction enforced [ cbr only ]. Accepting result.')
            else:
                logger.fdebug('Quality restriction enforced [ cbr only ]. Rejecting result.')
        elif mylar.PREFERRED_QUALITY == 2:
            if 'cbz' in torTITLE:
                logger.fdebug('Quality restriction enforced [ cbz only ]. Accepting result.')
            else:
                logger.fdebug('Quality restriction enforced [ cbz only ]. Rejecting result.')

        logger.fdebug('tor-Title: ' + torTITLE)
        logger.fdebug('there are ' + str(len(torsplit)) + ' sections in this title')
        i=0
        if nzbprov is not None:
            if nzbprov != tor['Site']:
                logger.fdebug('this is a result from ' + str(tor['Site']) + ', not the site I am looking for of ' + str(nzbprov))
                continue
        #0 holds the title/issue and format-type.
        ext_check = True   # extension checker to enforce cbr/cbz filetype restrictions.
        while (i < len(torsplit)):
            #we'll rebuild the string here so that it's formatted accordingly to be passed back to the parser.
            logger.fdebug('section(' + str(i) + '): ' + torsplit[i])
            #remove extensions
            titletemp = torsplit[i]
            titletemp = re.sub('cbr', '', titletemp)
            titletemp = re.sub('cbz', '', titletemp)
            titletemp = re.sub('none', '', titletemp)

            if i == 0:
                rebuiltline = titletemp
            else:
                rebuiltline = rebuiltline + ' (' + titletemp + ')'
            i+=1

        if ext_check == False:
            continue
        logger.fdebug('rebuiltline is :' + rebuiltline)

        seriesname_mod = seriesname
        foundname_mod = torsplit[0]
        seriesname_mod = re.sub("\\band\\b", " ", seriesname_mod.lower())
        foundname_mod = re.sub("\\band\\b", " ", foundname_mod.lower())
        seriesname_mod = re.sub("\\bthe\\b", " ", seriesname_mod.lower())
        foundname_mod = re.sub("\\bthe\\b", " ", foundname_mod.lower())

        seriesname_mod = re.sub('[\&]', ' ', seriesname_mod)
        foundname_mod = re.sub('[\&]', ' ', foundname_mod)

        formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\=\?\.]', '', seriesname_mod)
        formatrem_seriesname = re.sub('[\-]', ' ', formatrem_seriesname)
        formatrem_seriesname = re.sub('[\/]', ' ', formatrem_seriesname)  #not necessary since seriesname in a torrent file won't have /
        formatrem_seriesname = re.sub('\s+', ' ', formatrem_seriesname)
        if formatrem_seriesname[:1] == ' ': formatrem_seriesname = formatrem_seriesname[1:]

        formatrem_torsplit = re.sub('[\'\!\@\#\$\%\:\;\\=\?\.]', '', foundname_mod)
        formatrem_torsplit = re.sub('[\-]', ' ', formatrem_torsplit)  #we replace the - with space so we'll get hits if differnces
        formatrem_torsplit = re.sub('[\/]', ' ', formatrem_torsplit)  #not necessary since if has a /, should be removed in above line
        formatrem_torsplit = re.sub('\s+', ' ', formatrem_torsplit)
        logger.fdebug(str(len(formatrem_torsplit)) + ' - formatrem_torsplit : ' + formatrem_torsplit.lower())
        logger.fdebug(str(len(formatrem_seriesname)) + ' - formatrem_seriesname :' + formatrem_seriesname.lower())

        if formatrem_seriesname.lower() in formatrem_torsplit.lower() or any(x.lower() in formatrem_torsplit.lower() for x in AS_Alt):
            logger.fdebug('matched to : ' + torTITLE)
            logger.fdebug('matched on series title: ' + seriesname)
            titleend = formatrem_torsplit[len(formatrem_seriesname):]
            titleend = re.sub('\-', '', titleend)   #remove the '-' which is unnecessary
            #remove extensions
            titleend = re.sub('cbr', '', titleend)
            titleend = re.sub('cbz', '', titleend)
            titleend = re.sub('none', '', titleend)
            logger.fdebug('titleend: ' + titleend)

            sptitle = titleend.split()
            extra = ''

            #the title on 32P has a mix-mash of crap...ignore everything after cbz/cbr to cleanit
            ctitle = torTITLE.find('cbr')
            if ctitle == 0:
                ctitle = torTITLE.find('cbz')
                if ctitle == 0:
                    ctitle = torTITLE.find('none')
                    if ctitle == 0:
                        logger.fdebug('cannot determine title properly - ignoring for now.')
                        continue
            cttitle = torTITLE[:ctitle]

            if tor['Site'] == '32P':
                st_pub = rebuiltline.find('(')
                if st_pub < 2 and st_pub != -1:
                    st_end = rebuiltline.find(')')
                    rebuiltline = rebuiltline[st_end +1:]

            tortheinfo.append({
                          'title':   rebuiltline, #cttitle,
                          'link':    tor['Link'],
                          'pubdate': tor['Pubdate'],
                          'site':    tor['Site'],
                          'length':  tor['Size']
                          })

    torinfo['entries'] = tortheinfo

    return torinfo

def nzbdbsearch(seriesname, issue, comicid=None, nzbprov=None, searchYear=None, ComicVersion=None):
    myDB = db.DBConnection()
    seriesname_alt = None
    if comicid is None or comicid == 'None':
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
        if mylar.PREFERRED_QUALITY == 1: filetype = 'cbr'
        elif mylar.PREFERRED_QUALITY == 2: filetype = 'cbz'

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

def torsend2client(seriesname, issue, seriesyear, linkit, site):
    logger.info('matched on ' + seriesname)
    filename = helpers.filesafe(seriesname)
    filename = re.sub(' ', '_', filename)
    filename += "_" + str(issue) + "_" + str(seriesyear)

    if linkit[-7:] != "torrent": # and site != "KAT":
        filename += ".torrent"

    if mylar.TORRENT_LOCAL and mylar.LOCAL_WATCHDIR is not None:

        filepath = os.path.join(mylar.LOCAL_WATCHDIR, filename)
        logger.fdebug('filename for torrent set to : ' + filepath)
    elif mylar.TORRENT_SEEDBOX and mylar.SEEDBOX_WATCHDIR is not None:
        filepath = os.path.join(mylar.CACHE_DIR, filename)
        logger.fdebug('filename for torrent set to : ' + filepath)
    else:
        logger.error('No Local Watch Directory or Seedbox Watch Directory specified. Set it and try again.')
        return "fail"

    if site == '32P':
        url = 'https://32pag.es/torrents.php'

        if mylar.VERIFY_32P == 1 or mylar.VERIFY_32P == True:
            verify = True
        else:
            verify = False

        logger.fdebug('[32P] Verify SSL set to : ' + str(verify))
        if mylar.MODE_32P == 0:
            if mylar.KEYS_32P is None or mylar.PASSKEY_32P is None:
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
            if any([mylar.USERNAME_32P is None, mylar.USERNAME_32P == '', mylar.PASSWORD_32P is None, mylar.PASSWORD_32P == '']):
                logger.error('[RSS] Unable to sign-on to 32P to validate settings and initiate download sequence. Please enter/check your username password in the configuration.')
                return "fail"
            elif mylar.PASSKEY_32P is None or mylar.AUTHKEY_32P is None or mylar.KEYS_32P is None:
                logger.fdebug('[32P-AUTHENTICATION] 32P (Auth Mode) Authentication enabled. Keys have not been established yet, attempting to gather.')
                feed32p = auth32p.info32p(reauthenticate=True)
                feedinfo = feed32p.authenticate()
                if feedinfo == "disable":
                    mylar.ENABLE_32P = 0
                    mylar.config_write()
                    return "fail"
                if mylar.PASSKEY_32P is None or mylar.AUTHKEY_32P is None or mylar.KEYS_32P is None:
                    logger.error('[RSS] Unable to sign-on to 32P to validate settings and initiate download sequence. Please enter/check your username password in the configuration.')
                    return "fail"
            else:
                logger.fdebug('[32P-AUTHENTICATION] 32P (Auth Mode) Authentication already done. Attempting to use existing keys.')

        payload = {'action':       'download',
                   'torrent_pass': mylar.PASSKEY_32P,
                   'authkey':      mylar.AUTHKEY_32P,
                   'id':           linkit}

        headers = None #{'Accept-encoding': 'gzip',
                       # 'User-Agent':      str(mylar.USER_AGENT)}

    elif site == 'KAT':
        #stfind = linkit.find('?')
        #if stfind == -1:
        #    kat_referrer = helpers.torrent_create('KAT', linkit)
        #else:
        #    kat_referrer = linkit[:stfind]

        url = helpers.torrent_create('KAT', linkit)

        if url.startswith('https'):
            kat_referrer = 'https://torcache.net/'
        else:
            kat_referrer = 'http://torcache.net/'

        #logger.fdebug('KAT Referer set to :' + kat_referrer)

        headers = {'Accept-encoding': 'gzip',
                   'User-Agent':      str(mylar.USER_AGENT),
                   'Referer':         kat_referrer}

        logger.fdebug('Grabbing torrent from url:' + str(url))

        payload = None
        verify = False

    else:
        headers = {'Accept-encoding': 'gzip',
                   'User-Agent':      str(mylar.USER_AGENT)}
                   #'Referer': kat_referrer}

        url = linkit #helpers.torrent_create('TOR', linkit)

        payload = None
        verify = False

    if not verify:
        #32P throws back an insecure warning because it can't validate against the CA. The below suppresses the message just for 32P instead of being displayed.
        #disable SSL warnings - too many 'warning' messages about invalid certificates
        try:
            from lib.requests.packages.urllib3 import disable_warnings
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
        r = requests.get(url, params=payload, verify=verify, stream=True, headers=headers)

    except Exception, e:
        logger.warn('Error fetching data from %s: %s' % (site, e))
        if site == '32P':
            if mylar.MODE_32P == 1:
                logger.info('Attempting to re-authenticate against 32P and poll new keys as required.')
                feed32p = auth32p.info32p(reauthenticate=True)
                feedinfo = feed32p.authenticate()
                if feedinfo == "disable":
                    mylar.ENABLE_32P = 0
                    mylar.config_write()
                    return "fail"
                try:
                    r = requests.get(url, params=payload, verify=verify, stream=True, headers=headers)
                except Exception, e:
                    logger.warn('Error fetching data from %s: %s' % (site, e))
                    return "fail"
            else:
                logger.warn('[32P] Unable to authenticate using existing RSS Feed given. Make sure that you have provided a CURRENT feed from 32P')
                return "fail"
        else:
            return "fail"

    if str(r.status_code) == '403':
        #retry with the alternate torrent link.
        url = helpers.torrent_create('KAT', linkit, True)
        try:
            r = requests.get(url, params=payload, verify=verify, stream=True, headers=headers)

        except Exception, e:
            return "fail"

    if str(r.status_code) != '200':
        logger.warn('Unable to download torrent from ' + site + ' [Status Code returned: ' + str(r.status_code) + ']')
        return "fail"

    if site == 'KAT':
        if r.headers.get('Content-Encoding') == 'gzip':
            buf = StringIO(r.content)
            f = gzip.GzipFile(fileobj=buf)

    with open(filepath, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()

    logger.fdebug('[' + site + '] Saved torrent file to : ' + filepath)

    if mylar.TORRENT_LOCAL:
        return "pass"

    elif mylar.TORRENT_SEEDBOX:
        tssh = ftpsshup.putfile(filepath, filename)
        return tssh


if __name__ == '__main__':
    #torrents(sys.argv[1])
    #torrentdbsearch(sys.argv[1], sys.argv[2], sys.argv[3])
    nzbs(provider=sys.argv[1])
