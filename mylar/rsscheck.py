#!/usr/bin/python

import os, sys
import re
import lib.feedparser as feedparser
import urllib2
import ftpsshup
import datetime
import gzip
from StringIO import StringIO

import mylar
from mylar import db, logger, ftpsshup, helpers

def tehMain(forcerss=None):
    logger.info('RSS Feed Check was last run at : ' + str(mylar.RSS_LASTRUN))
    firstrun = "no"
    #check the last run of rss to make sure it's not hammering.
    if mylar.RSS_LASTRUN is None or mylar.RSS_LASTRUN == '' or mylar.RSS_LASTRUN == '0' or forcerss == True:
        logger.info('RSS Feed Check First Ever Run.')
        firstrun = "yes"
        mins = 0
    else:
        c_obj_date = datetime.datetime.strptime(mylar.RSS_LASTRUN, "%Y-%m-%d %H:%M:%S")
        n_date = datetime.datetime.now()
        absdiff = abs(n_date - c_obj_date)
        mins = (absdiff.days * 24 * 60 * 60 + absdiff.seconds) / 60.0  #3600 is for hours.

    if firstrun == "no" and mins < int(mylar.RSS_CHECKINTERVAL):
        logger.fdebug('RSS Check has taken place less than the threshold - not initiating at this time.')
        return

    mylar.RSS_LASTRUN = helpers.now()
    logger.fdebug('Updating RSS Run time to : ' + str(mylar.RSS_LASTRUN))
    mylar.config_write()

    #function for looping through nzbs/torrent feed
    if mylar.ENABLE_TORRENT_SEARCH: #and mylar.ENABLE_TORRENTS:
        logger.info('[RSS] Initiating Torrent RSS Check.')
        if mylar.ENABLE_KAT:
            logger.info('[RSS] Initiating Torrent RSS Feed Check on KAT.')
            torrents(pickfeed='3')
            torrents(pickfeed='6')
        if mylar.ENABLE_CBT:
            logger.info('[RSS] Initiating Torrent RSS Feed Check on CBT.')
            torrents(pickfeed='1')
            torrents(pickfeed='4')
    logger.info('[RSS] Initiating RSS Feed Check for NZB Providers.')
    nzbs()    
    logger.info('[RSS] RSS Feed Check/Update Complete')
    logger.info('[RSS] Watchlist Check for new Releases')
    mylar.search.searchforissue(rsscheck='yes')
    logger.info('[RSS] Watchlist Check complete.')
    if forcerss:
        logger.info('Successfully ran RSS Force Check.')

    return

def torrents(pickfeed=None,seriesname=None,issue=None):
    if pickfeed is None:
        pickfeed = 1
    #else:
    #    print "pickfeed is " + str(pickfeed)
    passkey = mylar.CBT_PASSKEY 
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
        kat_url = 'http://kat.ph/'

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
    katinfo = {}

    while (lp < loopit):
        if lp == 0 and loopit == 2: 
            pickfeed = '2'
        elif lp == 1 and loopit == 2: 
            pickfeed = '5'    

        feedtype = None

        if pickfeed == "1":      # cbt rss feed based on followlist
            feed = "http://comicbt.com/rss.php?action=browse&passkey=" + str(passkey) + "&type=dl"
            feedtype = ' from the New Releases RSS Feed for comics'
        elif pickfeed == "2" and srchterm is not None:    # kat.ph search
            feed = kat_url + "usearch/" + str(srchterm) + "%20category%3Acomics%20seeds%3A" + str(mylar.MINSEEDS) + "/?rss=1"
        elif pickfeed == "3":    # kat.ph rss feed
            feed = kat_url + "usearch/category%3Acomics%20seeds%3A" + str(mylar.MINSEEDS) + "/?rss=1"
            feedtype = ' from the New Releases RSS Feed for comics'
        elif pickfeed == "4":    #cbt follow link
            feed = "http://comicbt.com/rss.php?action=follow&passkey=" + str(passkey) + "&type=dl"
            feedtype = ' from your CBT Followlist RSS Feed'
        elif pickfeed == "5" and srchterm is not None:    # kat.ph search (category:other since some 0-day comics initially get thrown there until categorized)
            feed = kat_url + "usearch/" + str(srchterm) + "%20category%3Aother%20seeds%3A1/?rss=1"
        elif pickfeed == "6":    # kat.ph rss feed (category:other so that we can get them quicker if need-be)
            feed = kat_url + "usearch/.cbr%20category%3Aother%20seeds%3A" + str(mylar.MINSEEDS) + "/?rss=1"
            feedtype = ' from the New Releases for category Other RSS Feed that contain comics' 
        elif pickfeed == "7":    # cbt series link
#           seriespage = "http://comicbt.com/series.php?passkey=" + str(passkey)
            feed = "http://comicbt.com/rss.php?action=series&series=" + str(seriesno) + "&passkey=" + str(passkey)
        else:
            logger.error('invalid pickfeed denoted...')
            return

        #print 'feed URL: ' + str(feed)
  
        if pickfeed == "7": # we need to get the series # first
            seriesSearch(seriespage, seriesname)

        feedme = feedparser.parse(feed)

        if pickfeed == "3" or pickfeed == "6" or pickfeed == "2" or pickfeed == "5":
            picksite = 'KAT'
        elif pickfeed == "1" or pickfeed == "4":
            picksite = 'CBT'

        i = 0
    
        for entry in feedme['entries']:
            if pickfeed == "3" or pickfeed == "6":
                tmpsz = feedme.entries[i].enclosures[0]
                feeddata.append({
                               'site':     picksite,
                               'title':    feedme.entries[i].title,
                               'link':     tmpsz['url'],
                               'pubdate':  feedme.entries[i].updated,
                               'size':     tmpsz['length']
                               })

                #print ("Site: KAT")
                #print ("Title: " + str(feedme.entries[i].title))
                #print ("Link: " + str(tmpsz['url']))
                #print ("pubdate: " + str(feedme.entries[i].updated))
                #print ("size: " + str(tmpsz['length']))


            elif pickfeed == "2" or pickfeed == "5":
                tmpsz = feedme.entries[i].enclosures[0]
                torthekat.append({
                               'site':     picksite,
                               'title':    feedme.entries[i].title,
                               'link':     tmpsz['url'],
                               'pubdate':  feedme.entries[i].updated,
                               'size':     tmpsz['length']
                               })
  
               # print ("Site: KAT")
               # print ("Title: " + feedme.entries[i].title)
               # print ("Link: " + tmpsz['url'])
               # print ("pubdate: " + feedme.entries[i].updated)
               # print ("size: " + str(tmpsz['length']))
               # print ("filename: " + feedme.entries[i].torrent_filename)

            elif pickfeed == "1" or pickfeed == "4":
                if pickfeed == "1":
                    tmpdesc = feedme.entries[i].description
                    #break it down to get the Size since it's available on THIS CBT feed only.
                    sizestart = tmpdesc.find('Size:')
                    sizeend = tmpdesc.find('Leechers:')
                    sizestart +=5  # to get to the end of the word 'Size:'
                    tmpsize = tmpdesc[sizestart:sizeend].strip()
                    fdigits = re.sub("[^0123456789\.]", "", tmpsize).strip()
                    if '.' in fdigits:
                        decfind = fdigits.find('.')
                        wholenum = fdigits[:decfind]
                        decnum = fdigits[decfind+1:]
                    else:
                        wholenum = fdigits
                        decnum = 0
                    if 'MB' in tmpsize:
                        wholebytes = int(wholenum) * 1048576
                        wholedecimal = ( int(decnum) * 1048576 ) / 100
                        justdigits = wholebytes + wholedecimal
                    else:
                        #it's 'GB' then
                        wholebytes = ( int(wholenum) * 1024 ) * 1048576 
                        wholedecimal = ( ( int(decnum) * 1024 ) * 1048576 ) / 100
                        justdigits = wholebytes + wholedecimal 
                    #Get the # of seeders.                  
                    seedstart = tmpdesc.find('Seeders:')
                    seedend = tmpdesc.find('Added:')
                    seedstart +=8  # to get to the end of the word 'Seeders:'
                    tmpseed = tmpdesc[seedstart:seedend].strip()
                    seeddigits = re.sub("[^0123456789\.]", "", tmpseed).strip()
                    
                else:
                    justdigits = None #size not available in follow-list rss feed
                    seeddigits = 0  #number of seeders not available in follow-list rss feed

                if int(mylar.MINSEEDS) >= int(seeddigits):
                    feeddata.append({
                                   'site':     picksite,
                                   'title':    feedme.entries[i].title, 
                                   'link':     feedme.entries[i].link,
                                   'pubdate':  feedme.entries[i].updated,
                                   'size':     justdigits
                                   })
                #print ("Site: CBT")
                #print ("Title: " + str(feeddata[i]['Title']))
                #print ("Link: " + str(feeddata[i]['Link']))
                #print ("pubdate: " + str(feeddata[i]['Pubdate']))


            i+=1

        if feedtype is None:
            logger.fdebug('[' + picksite + '] there were ' + str(i) + ' results..')
        else:
            logger.fdebug('[' + picksite + '] there were ' + str(i) + ' results ' + feedtype)

        totalcount += i
        lp +=1


    if not seriesname:
        rssdbupdate(feeddata,totalcount,'torrent')
    else:
        katinfo['entries'] = torthekat
        return katinfo
    return

def nzbs(provider=None):
    nzbprovider = []
    nzbp = 0
    if mylar.NZBSU == 1:
        nzbprovider.append('nzb.su')
        nzbp+=1
    if mylar.DOGNZB == 1:
        nzbprovider.append('dognzb')
        nzbp+=1
    # --------
    #  Xperimental
    if mylar.EXPERIMENTAL == 1:
        nzbprovider.append('experimental')
        nzbp+=1

    newznabs = 0

    newznab_hosts = []

    if mylar.NEWZNAB == 1:

        for newznab_host in mylar.EXTRA_NEWZNABS:
            if newznab_host[4] == '1' or newznab_host[4] == 1:
                newznab_hosts.append(newznab_host)
                nzbprovider.append('newznab')
                newznabs+=1
                logger.fdebug('newznab name:' + str(newznab_host[0]) + ' - enabled: ' + str(newznab_host[4]))

    # --------
    providercount = int(nzbp + newznabs)
    logger.fdebug('there are : ' + str(providercount) + ' nzb RSS search providers you have enabled.')
    nzbpr = providercount - 1
    if nzbpr < 0:
        nzbpr == 0

    feeddata = []
    feedthis = []
    ft = 0
    totNum = 0
    nonexp = "no"
   
    while (nzbpr >= 0 ):
        if nzbprovider[nzbpr] == 'experimental':
            feed = feedparser.parse("http://nzbindex.nl/rss/alt.binaries.comics.dcp/?sort=agedesc&max=50&more=1")

            totNum = len(feed.entries)
            site = 'experimental'
            keyPair = {}
            regList = []
            entries = []
            mres = {}
            countUp = 0

            i = 0
            for entry in feed['entries']:
                tmpsz = feed.entries[i].enclosures[0]
                feeddata.append({
                               'Site':     site,
                               'Title':    feed.entries[i].title,
                               'Link':     tmpsz['url'],  #feed.entries[i].link,
                               'Pubdate':  feed.entries[i].updated,
                               'Size':     tmpsz['length']
                               })
#                print ("Site:" + str(site))
#                print ("Title:" + str(feed.entries[i].title))
#                print ("Link:" + str(feed.entries[i].link))
#                print ("Pubdate:" + str(feed.entries[i].updated))
#                print ("Size:" + str(tmpsz['length']))
                i+=1
            logger.info(str(i) + ' results from Experimental feed indexed.')
            nzbpr-=1
        else:
            if nzbprovider[nzbpr] == 'newznab':
                for newznab_host in newznab_hosts:
                    if newznab_host[3] is None:
                        newznabuid = '1'
                        newznabcat = '7030'
                    else:
                        if '#' not in newznab_host[3]:
                            newznabuid = newznab_host[3]
                            newznabcat = '7030'
                        else:
                            newzst = newznab_host[3].find('#')
                            newznabuid = newznab_host[3][:newzst]
                            newznabcat = newznab_host[3][newzst+1:]
                    # 11-21-2014: added &num=100 to return 100 results (or maximum) - unsure of cross-reliablity
                    feed = newznab_host[1].rstrip() + '/rss?t=' + str(newznabcat) + '&dl=1&i=' + str(newznabuid) + '&num=100&&r=' + newznab_host[2].rstrip()
                    feedme = feedparser.parse(feed)
                    site = newznab_host[0].rstrip()
                    feedthis.append({"feed":     feedme,
                                     "site":     site})
                    totNum+=len(feedme.entries)
                    ft+=1
                    nonexp = "yes"
                    nzbpr-=1
            elif nzbprovider[nzbpr] == 'nzb.su':
                if mylar.NZBSU_UID is None:
                    mylar.NZBSU_UID = '1'
                feed = 'http://api.nzb.su/rss?t=7030&dl=1&i=' + mylar.NZBSU_UID + '&r=' + mylar.NZBSU_APIKEY
                feedme = feedparser.parse(feed)
                site = nzbprovider[nzbpr]
                feedthis.append({"feed":   feedme,
                                 "site":   site })
                totNum+=len(feedme.entries)
                ft+=1
                nonexp = "yes"
                nzbpr-=1
            elif nzbprovider[nzbpr] == 'dognzb':
                if mylar.DOGNZB_UID is None:
                    mylar.DOGNZB_UID = '1'
                feed = 'https://dognzb.cr/rss.cfm?r=' + mylar.DOGNZB_APIKEY + '&t=7030'
                feedme = feedparser.parse(feed)
                site = nzbprovider[nzbpr]
                ft+=1
                nonexp = "yes"
                feedthis.append({"feed":   feedme,
                                 "site":   site })
                totNum+=len(feedme.entries)
                nzbpr-=1

    i = 0
    if nonexp == "yes":
        #print str(ft) + " sites checked. There are " + str(totNum) + " entries to be updated."
        #print feedme

        for ft in feedthis:
            sitei = 0
            site = ft['site']
            logger.fdebug(str(site) + " now being updated...")
            #logger.fdebug('feedthis:' + str(ft))
            for entry in ft['feed'].entries:
                if site == 'dognzb':
                    #because the rss of dog doesn't carry the enclosure item, we'll use the newznab size value
                    tmpsz = 0
                    #for attr in entry['newznab:attrib']:
                    #    if attr('@name') == 'size':
                    #        tmpsz = attr['@value']
                    #        logger.fdebug('size retrieved as ' + str(tmpsz))
                    #        break
                    feeddata.append({
                               'Site':     site,
                               'Title':    entry.title,    #ft['feed'].entries[i].title,
                               'Link':     entry.link,     #ft['feed'].entries[i].link,
                               'Pubdate':  entry.updated,  #ft['feed'].entries[i].updated,
                               'Size':     tmpsz
                               })
                else:
                    #this should work for all newznabs (nzb.su included)
                    #only difference is the size of the file between this and above (which is probably the same)
                    tmpsz = entry.enclosures[0]  #ft['feed'].entries[i].enclosures[0]
                    feeddata.append({
                               'Site':     site,
                               'Title':    entry.title,   #ft['feed'].entries[i].title,
                               'Link':     entry.link,    #ft['feed'].entries[i].link,
                               'Pubdate':  entry.updated, #ft['feed'].entries[i].updated,
                               'Size':     tmpsz['length']
                               })

                #logger.fdebug("Site: " + str(feeddata[i]['Site']))
                #logger.fdebug("Title: " + str(feeddata[i]['Title']))
                #logger.fdebug("Link: " + str(feeddata[i]['Link']))
                #logger.fdebug("pubdate: " + str(feeddata[i]['Pubdate']))
                #logger.fdebug("size: " + str(feeddata[i]['Size']))
                sitei+=1
            logger.info('[' + str(site) + '] ' + str(sitei) + ' entries indexed.')
            i+=sitei
    if i > 0: 
        logger.info('[RSS] ' + str(i) + ' entries have been indexed and are now going to be stored for caching.')
        rssdbupdate(feeddata,i,'usenet')
    return

def rssdbupdate(feeddata,i,type):
    rsschktime = 15
    myDB = db.DBConnection()

    #let's add the entries into the db so as to save on searches
    #also to build up the ID's ;)
    x = 1
    while x <= i:
        try:
            dataval = feeddata[x]
        except IndexError:
            logger.fdebug('reached the end of populating. Exiting the process.')
            break
        #print "populating : " + str(dataval)
        #remove passkey so it doesn't end up in db
        if type == 'torrent':
            newlink = dataval['link'][:(dataval['link'].find('&passkey'))]
            newVal = {"Link":      newlink,
                      "Pubdate":   dataval['pubdate'],
                      "Site":      dataval['site'],
                      "Size":      dataval['size']}
            ctrlVal = {"Title":    dataval['title']}
#            if dataval['Site'] == 'KAT':
#                newVal['Size'] =  dataval['Size']
        else:
            newlink = dataval['Link']
            newVal = {"Link":      newlink,
                      "Pubdate":   dataval['Pubdate'],
                      "Site":      dataval['Site'],
                      "Size":      dataval['Size']}
            ctrlVal = {"Title":    dataval['Title']}

        myDB.upsert("rssdb", newVal,ctrlVal)

        x+=1

    logger.fdebug('Completed adding new data to RSS DB. Next add in ' + str(mylar.RSS_CHECKINTERVAL) + ' minutes')
    return

def torrentdbsearch(seriesname,issue,comicid=None,nzbprov=None):
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
    tsearch_seriesname = re.sub('[\'\!\@\#\$\%\:\-\;\/\\=\?\&\.\s]', '%',tsearch_removed)
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

    if mylar.ENABLE_CBT:
        tresults = myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='CBT'", [tsearch])
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
            AS_Alter = re.sub('##','',calt)
            u_altsearchcomic = AS_Alter.encode('ascii', 'ignore').strip()
            AS_Altrem = re.sub("\\band\\b", "", u_altsearchcomic.lower())
            AS_Altrem = re.sub("\\bthe\\b", "", AS_Altrem.lower())

            AS_Alternate = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\+\'\&\?\@\s]', '%', AS_Altrem)

            AS_Altrem_mod = re.sub('[\&]', ' ', AS_Altrem)
            AS_formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.]', '',AS_Altrem_mod)
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

            if mylar.ENABLE_CBT:
                #print "AS_Alternate:" + str(AS_Alternate)
                tresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='CBT'", [AS_Alternate])
            if mylar.ENABLE_KAT:
                tresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site='KAT'", [AS_Alternate])

    if tresults is None:
        logger.fdebug('torrent search returned no results for ' + seriesname)
        return "no results"

    extensions = ('cbr', 'cbz')
    tortheinfo = []
    torinfo = {}

    for tor in tresults:
        torsplit = tor['Title'].split('/')
        if mylar.PREFERRED_QUALITY == 1:
            if 'cbr' in tor['Title']:
                logger.fdebug('Quality restriction enforced [ cbr only ]. Accepting result.')
            else:
                logger.fdebug('Quality restriction enforced [ cbr only ]. Rejecting result.')
        elif mylar.PREFERRED_QUALITY == 2:
            if 'cbz' in tor['Title']:
                logger.fdebug('Quality restriction enforced [ cbz only ]. Accepting result.')
            else:
                logger.fdebug('Quality restriction enforced [ cbz only ]. Rejecting result.')

        logger.fdebug('tor-Title: ' + tor['Title'])
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

        formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\=\?\.]', '',seriesname_mod)
        formatrem_seriesname = re.sub('[\-]', ' ',formatrem_seriesname)
        formatrem_seriesname = re.sub('[\/]', ' ', formatrem_seriesname)  #not necessary since seriesname in a torrent file won't have /
        formatrem_seriesname = re.sub('\s+', ' ', formatrem_seriesname)
        if formatrem_seriesname[:1] == ' ': formatrem_seriesname = formatrem_seriesname[1:]

        formatrem_torsplit = re.sub('[\'\!\@\#\$\%\:\;\\=\?\.]', '',foundname_mod)
        formatrem_torsplit = re.sub('[\-]', ' ',formatrem_torsplit)  #we replace the - with space so we'll get hits if differnces
        formatrem_torsplit = re.sub('[\/]', ' ', formatrem_torsplit)  #not necessary since if has a /, should be removed in above line
        formatrem_torsplit = re.sub('\s+', ' ', formatrem_torsplit)
        logger.fdebug(str(len(formatrem_torsplit)) + ' - formatrem_torsplit : ' + formatrem_torsplit.lower())
        logger.fdebug(str(len(formatrem_seriesname)) + ' - formatrem_seriesname :' + formatrem_seriesname.lower())

        if formatrem_seriesname.lower() in formatrem_torsplit.lower() or any(x.lower() in formatrem_torsplit.lower() for x in AS_Alt):
            logger.fdebug('matched to : ' + tor['Title'])
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
#            for sp in sptitle:
#                if 'v' in sp.lower() and sp[1:].isdigit():
#                    volumeadd = sp
#                elif 'vol' in sp.lower() and sp[3:].isdigit():
#                    volumeadd = sp
#                #if sp.isdigit():
#                    #print("issue # detected : " + str(issue))
#                elif helpers.issuedigits(issue.rstrip()) == helpers.issuedigits(sp.rstrip()):
#                    logger.fdebug("Issue matched for : " + str(issue))
            #the title on CBT has a mix-mash of crap...ignore everything after cbz/cbr to cleanit
            ctitle = tor['Title'].find('cbr')
            if ctitle == 0:
                ctitle = tor['Title'].find('cbz')
                if ctitle == 0:
                    ctitle = tor['Title'].find('none')
                    if ctitle == 0:               
                        logger.fdebug('cannot determine title properly - ignoring for now.')
                        continue
            cttitle = tor['Title'][:ctitle]
            #print("change title to : " + str(cttitle))
#           if extra == '':
            tortheinfo.append({
                          'title':   rebuiltline, #cttitle,
                          'link':    tor['Link'],
                          'pubdate': tor['Pubdate'],
                          'site':    tor['Site'],
                          'length':  tor['Size']
                          })
#                    continue
#                        #torsend2client(formatrem_seriesname,tor['Link'])
#                    else:
#                        logger.fdebug("extra info given as :" + str(extra))
#                        logger.fdebug("extra information confirmed as a match")
#                        logger.fdebug("queuing link: " + str(tor['Link']))
#                        tortheinfo.append({
#                                      'title':   cttitle, #tor['Title'],
#                                      'link':    tor['Link'],
#                                      'pubdate': tor['Pubdate'],
#                                      'site':    tor['Site'],
#                                      'length':    tor['Size']
#                                      })
#                        logger.fdebug("entered info.")
#                        continue
                            #torsend2client(formatrem_seriesname,tor['Link'])
                #else:
                #    logger.fdebug("invalid issue#: " + str(sp))
                #    #extra = str(extra) + " " + str(sp) 
#                else:
#                    logger.fdebug("word detected - assuming continuation of title: " + str(sp))
#                    extra = str(extra) + " " + str(sp)

    torinfo['entries'] = tortheinfo

    return torinfo

def nzbdbsearch(seriesname,issue,comicid=None,nzbprov=None,searchYear=None,ComicVersion=None):
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

    nsearch_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.\-\s]', '%',seriesname)
    formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.]', '',seriesname)

    nsearch = '%' + nsearch_seriesname + "%"

    nresults = myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site=?", [nsearch,nzbprov])
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
                AS_Alternate = re.sub('##','',calt)
                AS_Alternate = '%' + AS_Alternate + "%"
                nresults += myDB.select("SELECT * FROM rssdb WHERE Title like ? AND Site=?", [AS_Alternate,nzbprov])
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
    logger.info('matched on ' + str(seriesname))
    filename = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.]', '',seriesname)
    filename = re.sub(' ', '_', filename)
    filename += "_" + str(issue) + "_" + str(seriesyear)
    if site == 'CBT':
        logger.info(linkit)
        linkit = str(linkit) + '&passkey=' + str(mylar.CBT_PASSKEY)

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

    try:
        request = urllib2.Request(linkit)
        #request.add_header('User-Agent', str(mylar.USER_AGENT))
        request.add_header('Accept-encoding', 'gzip')

        if site == 'KAT':
            stfind = linkit.find('?')
            kat_referrer = linkit[:stfind]
            request.add_header('Referer', kat_referrer)
            logger.fdebug('KAT Referer set to :' + kat_referrer)


#        response = helpers.urlretrieve(urllib2.urlopen(request), filepath)
        response = urllib2.urlopen(request)
        logger.fdebug('retrieved response.')

        if site == 'KAT':
            if response.info()['content-encoding'] == 'gzip':#.get('Content-Encoding') == 'gzip':
                logger.fdebug('gzip detected')
                buf = StringIO(response.read())
                logger.fdebug('gzip buffered')
                f = gzip.GzipFile(fileobj=buf)
                logger.fdebug('gzip filed.')
                torrent = f.read()
                logger.fdebug('gzip read.')
        else:
            torrent = response.read()

    except Exception, e:
        logger.warn('Error fetching data from %s: %s' % (site, e))
        return "fail"

    with open(filepath, 'wb') as the_file:
        the_file.write(torrent)

    logger.fdebug("saved.")
    #logger.fdebug('torrent file saved as : ' + str(filepath))
    if mylar.TORRENT_LOCAL:
        return "pass"
    #remote_file = urllib2.urlopen(linkit)
    #if linkit[-7:] != "torrent":
    #    filename += ".torrent"

    #local_file = open('%s' % (os.path.join(mylar.CACHE_DIR,filename)), 'w')
    #local_file.write(remote_file.read())
    #local_file.close()
    #remote_file.close()
    elif mylar.TORRENT_SEEDBOX:
        tssh = ftpsshup.putfile(filepath,filename)
        return tssh


if __name__ == '__main__':
    #torrents(sys.argv[1])
    #torrentdbsearch(sys.argv[1], sys.argv[2], sys.argv[3])
    nzbs(sys.argv[1])
