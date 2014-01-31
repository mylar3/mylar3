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

    #function for looping through nzbs/torrent feeds
    if mylar.ENABLE_TORRENTS:
        logger.fdebug("[RSS] Initiating Torrent RSS Check.")
        if mylar.ENABLE_KAT:
            logger.fdebug('[RSS] Initiating Torrent RSS Feed Check on KAT.')
            torrents(pickfeed='3')
        if mylar.ENABLE_CBT:
            logger.fdebug('[RSS] Initiating Torrent RSS Feed Check on CBT.')
            torrents(pickfeed='1')
            torrents(pickfeed='4')
    logger.fdebug('RSS] Initiating RSS Feed Check for NZB Providers.')
    nzbs()    
    logger.fdebug('[RSS] RSS Feed Check/Update Complete')
    logger.fdebug('[RSS] Watchlist Check for new Releases')
    #if mylar.ENABLE_TORRENTS:
    #    if mylar.ENABLE_KAT:
    #        search.searchforissue(rsscheck='yes')
    #    if mylar.ENABLE_CBT:    
    mylar.search.searchforissue(rsscheck='yes')
    #nzbcheck here
    #nzbs(rsscheck='yes')
    logger.fdebug('[RSS] Watchlist Check complete.')
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


    if pickfeed == "1":      # cbt rss feed based on followlist
        feed = "http://comicbt.com/rss.php?action=browse&passkey=" + str(passkey) + "&type=dl"
    elif pickfeed == "2" and srchterm is not None:    # kat.ph search
        feed = kat_url + "usearch/" + str(srchterm) + "%20category%3Acomics%20seeds%3A1/?rss=1"
    elif pickfeed == "3":    # kat.ph rss feed
        feed = kat_url + "usearch/category%3Acomics%20seeds%3A1/?rss=1"
    elif pickfeed == "4":    #cbt follow link
        feed = "http://comicbt.com/rss.php?action=follow&passkey=" + str(passkey) + "&type=dl"
    elif pickfeed == "5":    # cbt series link
#       seriespage = "http://comicbt.com/series.php?passkey=" + str(passkey)
        feed = "http://comicbt.com/rss.php?action=series&series=" + str(seriesno) + "&passkey=" + str(passkey)
    else:
        logger.error('invalid pickfeed denoted...')
        return

    title = []
    link = []
    description = []
    seriestitle = []

    if pickfeed == "5": # we need to get the series # first
        seriesSearch(seriespage, seriesname)

    feedme = feedparser.parse(feed)
    
    i = 0

    feeddata = []
    myDB = db.DBConnection()
    torthekat = []
    katinfo = {}

    for entry in feedme['entries']:
        if pickfeed == "3":
            tmpsz = feedme.entries[i].enclosures[0]
            feeddata.append({
                           'Site':     'KAT',
                           'Title':    feedme.entries[i].title,
                           'Link':     tmpsz['url'],
                           'Pubdate':  feedme.entries[i].updated,
                           'Size':     tmpsz['length']
                           })

        elif pickfeed == "2":
            tmpsz = feedme.entries[i].enclosures[0]
            torthekat.append({
                           'site':     'KAT',
                           'title':    feedme.entries[i].title,
                           'link':     tmpsz['url'],
                           'pubdate':  feedme.entries[i].updated,
                           'length':     tmpsz['length']
                           })

            #print ("Site: KAT")
            #print ("Title: " + str(feedme.entries[i].title))
            #print ("Link: " + str(tmpsz['url']))
            #print ("pubdate: " + str(feedme.entries[i].updated))
            #print ("size: " + str(tmpsz['length']))

        elif pickfeed == "1" or pickfeed == "4":
#            tmpsz = feedme.entries[i].enclosures[0]
            feeddata.append({
                           'Site':     'CBT',
                           'Title':    feedme.entries[i].title, 
                           'Link':     feedme.entries[i].link,
                           'Pubdate':  feedme.entries[i].updated
#                          'Size':     tmpsz['length']
                           })
            #print ("Site: CBT")
            #print ("Title: " + str(feeddata[i]['Title']))
            #print ("Link: " + str(feeddata[i]['Link']))
            #print ("pubdate: " + str(feeddata[i]['Pubdate']))
        i+=1
    logger.fdebug('there were ' + str(i) + ' results..')

    if not seriesname:
        rssdbupdate(feeddata,i,'torrent')
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
    logger.fdebug('there are : ' + str(providercount) + ' RSS search providers you have enabled.')
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
                    feed = newznab_host[1].rstrip() + '/rss?t=' + str(newznabcat) + '&dl=1&i=' + str(newznabuid) + '&r=' + newznab_host[2].rstrip()
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
                feed = 'http://nzb.su/rss?t=7030&dl=1&i=' + mylar.NZBSU_UID + '&r=' + mylar.NZBSU_APIKEY
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
        #i = 0

        for ft in feedthis:
            site = ft['site']
            #print str(site) + " now being updated..."
            for entry in ft['feed'].entries:
                #print "entry: " + str(entry)
                tmpsz = entry.enclosures[0]
                feeddata.append({
                           'Site':     site,
                           'Title':    entry.title,
                           'Link':     entry.link,
                           'Pubdate':  entry.updated,
                           'Size':     tmpsz['length']
                           })

#               print ("Site: " + str(feeddata[i]['Site']))
#               print ("Title: " + str(feeddata[i]['Title']))
#               print ("Link: " + str(feeddata[i]['Link']))
#               print ("pubdate: " + str(feeddata[i]['Pubdate']))
#               print ("size: " + str(feeddata[i]['Size']))
                i+=1
            logger.info(str(site) + ' : ' + str(i) + ' entries indexed.')

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
            newlink = dataval['Link'][:(dataval['Link'].find('&passkey'))]
            newVal = {"Link":      newlink,
                      "Pubdate":   dataval['Pubdate'],
                      "Site":      dataval['Site']}
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
        snm = myDB.action("SELECT * FROM comics WHERE comicid=?", [comicid]).fetchone()
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
    tsearch = tsearch_seriesname + "%"
    logger.fdebug('tsearch : ' + str(tsearch))
    AS_Alt = []
    tresults = []

    if mylar.ENABLE_CBT:
        tresults = myDB.action("SELECT * FROM rssdb WHERE Title like ? AND Site='CBT'", [tsearch]).fetchall()
    if mylar.ENABLE_KAT:
        tresults += myDB.action("SELECT * FROM rssdb WHERE Title like ? AND Site='KAT'", [tsearch]).fetchall()

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

            AS_Alternate += '%'

            if mylar.ENABLE_CBT:
                #print "AS_Alternate:" + str(AS_Alternate)
                tresults += myDB.action("SELECT * FROM rssdb WHERE Title like ? AND Site='CBT'", [AS_Alternate]).fetchall()
            if mylar.ENABLE_KAT:
                tresults += myDB.action("SELECT * FROM rssdb WHERE Title like ? AND Site='KAT'", [AS_Alternate]).fetchall()

    if tresults is None:
        logger.fdebug('torrent search returned no results for ' + seriesname)
        return "no results"

    extensions = ('cbr', 'cbz')
    tortheinfo = []
    torinfo = {}

    for tor in tresults:
        torsplit = tor['Title'].split('/')
        logger.fdebug('tor-Title: ' + tor['Title'])
        logger.fdebug('there are ' + str(len(torsplit)) + ' sections in this title')
        i=0
        #0 holds the title/issue and format-type.
        while (i < len(torsplit)):
            #we'll rebuild the string here so that it's formatted accordingly to be passed back to the parser.
            logger.fdebug('section(' + str(i) + '): ' + str(torsplit[i]))
            #remove extensions
            titletemp = torsplit[i]
            titletemp = re.sub('cbr', '', str(titletemp))
            titletemp = re.sub('cbz', '', str(titletemp))
            titletemp = re.sub('none', '', str(titletemp))
          
            if i == 0: 
                rebuiltline = str(titletemp)
            else:
                rebuiltline = rebuiltline + ' (' + str(titletemp) + ')'
            i+=1

        logger.fdebug('rebuiltline is :' + str(rebuiltline))

        seriesname_mod = seriesname
        foundname_mod = torsplit[0]
        seriesname_mod = re.sub("\\band\\b", " ", seriesname_mod.lower())
        foundname_mod = re.sub("\\band\\b", " ", foundname_mod.lower())
        seriesname_mod = re.sub("\\bthe\\b", " ", seriesname_mod.lower())
        foundname_mod = re.sub("\\bthe\\b", " ", foundname_mod.lower())

        seriesname_mod = re.sub('[\&]', ' ', seriesname_mod)
        foundname_mod = re.sub('[\&]', ' ', foundname_mod)

        formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\=\?\.\-]', '',seriesname_mod)
        formatrem_seriesname = re.sub('[\/]', '-', formatrem_seriesname)
        formatrem_seriesname = re.sub('\s+', ' ', formatrem_seriesname)
        if formatrem_seriesname[:1] == ' ': formatrem_seriesname = formatrem_seriesname[1:]

        formatrem_torsplit = re.sub('[\'\!\@\#\$\%\:\;\\=\?\.\-]', '',foundname_mod)
        formatrem_torsplit = re.sub('[\/]', '-', formatrem_torsplit)
        formatrem_torsplit = re.sub('\s+', ' ', formatrem_torsplit)
        logger.fdebug(str(len(formatrem_torsplit)) + ' - formatrem_torsplit : ' + formatrem_torsplit.lower())
        logger.fdebug(str(len(formatrem_seriesname)) + ' - formatrem_seriesname :' + formatrem_seriesname.lower())

        if formatrem_seriesname.lower() in formatrem_torsplit.lower() or any(x.lower() in formatrem_torsplit.lower() for x in AS_Alt):
            logger.fdebug('matched to : ' + tor['Title'])
            logger.fdebug('matched on series title: ' + seriesname)
            titleend = formatrem_torsplit[len(formatrem_seriesname):]
            titleend = re.sub('\-', '', titleend)   #remove the '-' which is unnecessary
            #remove extensions
            titleend = re.sub('cbr', '', str(titleend))
            titleend = re.sub('cbz', '', str(titleend))
            titleend = re.sub('none', '', str(titleend))
            logger.fdebug('titleend: ' + str(titleend))

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
        snm = myDB.action("SELECT * FROM comics WHERE comicid=?", [comicid]).fetchone()
        if snm is None:
            logger.info('Invalid ComicID of ' + str(comicid) + '. Aborting search.')
            return
        else:
            seriesname = snm['ComicName']
            seriesname_alt = snm['AlternateSearch']


    nsearch_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.\-\s]', '%',seriesname)
    formatrem_seriesname = re.sub('[\'\!\@\#\$\%\:\;\/\\=\?\.]', '',seriesname)
    nsearch = '%' + nsearch_seriesname + "%"
    nresults = myDB.action("SELECT * FROM rssdb WHERE Title like ? AND Site=?", [nsearch,nzbprov])
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
                nresults += myDB.action("SELECT * FROM rssdb WHERE Title like ? AND Site=?", [AS_Alternate,nzbprov])
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

        for results in nresults:
            title = results['Title']
            #logger.fdebug("titlesplit: " + str(title.split("\"")))
            splitTitle = title.split("\"")
            noYear = 'False'

            for subs in splitTitle:
                #logger.fdebug(subs)
                if len(subs) > 10 and not any(d in subs.lower() for d in except_list):
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
            logger.fdebug("entered info for " + nzb['Title'])


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

        if response.info().get('Content-Encoding') == 'gzip':
            buf = StringIO(response.read())
            f = gzip.GzipFile(fileobj=buf)
            torrent = f.read()
        else:
            torrent = response.read()

    except Exception, e:
        logger.warn('Error fetching data from %s: %s' % (site, e))
        return "fail"

    with open(filepath, 'wb') as the_file:
        the_file.write(torrent)

    logger.info("saved.")
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
