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

from __future__ import division

import mylar
from mylar import logger, db, updater, helpers, parseit, findcomicfeed, notifiers, rsscheck, Failed, filechecker

import lib.feedparser as feedparser
import lib.requests as requests
import urllib
import os, errno
import string
import sys
import getopt
import re
import time
import urlparse
from urlparse import urljoin
from xml.dom.minidom import parseString
import urllib2
import email.utils
import datetime
import shutil
from wsgiref.handlers import format_date_time

def search_init(ComicName, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, IssueID, AlternateSearch=None, UseFuzzy=None, ComicVersion=None, SARC=None, IssueArcID=None, mode=None, rsscheck=None, ComicID=None, manualsearch=None, filesafe=None):
    unaltered_ComicName = None
    if filesafe:
        if filesafe != ComicName and mode != 'want_ann':
            logger.info('[SEARCH] Special Characters exist within Series Title. Enabling search-safe Name : ' + filesafe)
            if AlternateSearch is None or AlternateSearch == 'None':
                AlternateSearch = filesafe
            else:
                AlternateSearch += '##' + filesafe
            unaltered_ComicName = ComicName
            #ComicName = filesafe
            #logger.info('AlternateSearch is : ' + AlternateSearch)
    if ComicYear == None:
        ComicYear = str(datetime.datetime.now().year)
    else:
        ComicYear = str(ComicYear)[:4]
    if Publisher:
        if Publisher == 'IDW Publishing':
            Publisher = 'IDW'
        logger.fdebug('Publisher is : ' + Publisher)
    issuetitle = helpers.get_issue_title(IssueID)
    if issuetitle:
        logger.info('Issue Title given as : ' + issuetitle)
    else:
        logger.fdebug('Issue Title not found. Setting to None.')

    if mode == 'want_ann':
        logger.info("Annual issue search detected. Appending to issue #")
        #anything for mode other than None indicates an annual.
        if 'annual' not in ComicName.lower():
            ComicName = ComicName + " annual"
        if AlternateSearch is not None and AlternateSearch != "None":
            AlternateSearch = AlternateSearch + " annual"

    if IssueID is None:
        #one-off the download.
        logger.fdebug('One-Off Search parameters:')
        logger.fdebug("ComicName: " + ComicName)
        logger.fdebug("Issue: " + str(IssueNumber))
        logger.fdebug("Year: " + str(ComicYear))
        logger.fdebug("IssueDate:" + str(IssueDate))
    if SARC:
        logger.fdebug("Story-ARC Search parameters:")
        logger.fdebug("Story-ARC: " + str(SARC))
        logger.fdebug("IssueArcID: " + str(IssueArcID))

    torprovider = []
    torp = 0
    logger.fdebug("Checking for torrent enabled.")
    if mylar.ENABLE_TORRENT_SEARCH: #and mylar.ENABLE_TORRENTS:
        if mylar.ENABLE_32P:
            torprovider.append('32p')
            torp+=1
            #print torprovider[0]
        if mylar.ENABLE_KAT:
            torprovider.append('kat')
            torp+=1
        if mylar.ENABLE_TORZNAB:
            torprovider.append('torznab')
            torp+=1
    ##nzb provider selection##
    ##'dognzb' or 'nzb.su' or 'experimental'
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
    #if len(mylar.EXTRA_NEWZNABS > 0):
        for newznab_host in mylar.EXTRA_NEWZNABS:
            if newznab_host[5] == '1' or newznab_host[5] == 1:
                newznab_hosts.append(newznab_host)
                #if newznab_host[0] == newznab_host[1]:
                #    nzbprovider.append('newznab')
                #else:
                nzbprovider.append('newznab:' + str(newznab_host[0]))
                newznabs+=1
                logger.fdebug("newznab name:" + str(newznab_host[0]) + " @ " + str(newznab_host[1]))

    #logger.fdebug('newznab hosts: ' + str(newznab_hosts))
    logger.fdebug('nzbprovider(s): ' + str(nzbprovider))
    # --------
    logger.fdebug("there are : " + str(torp) + " torrent providers you have selected.")
    torpr = torp - 1
    if torpr < 0:
        torpr = -1
    providercount = int(nzbp + newznabs)
    logger.fdebug("there are : " + str(providercount) + " nzb providers you have selected.")
    logger.fdebug("Usenet Retention : " + str(mylar.USENET_RETENTION) + " days")
    #nzbpr = providercount - 1
    #if nzbpr < 0:
    #    nzbpr == 0
    findit = 'no'

    totalproviders = providercount + torp

    if totalproviders == 0:
        logger.error('[WARNING] You have ' + str(totalproviders) + ' search providers enabled. I need at least ONE provider to work. Aborting search.')
        findit = "no"
        nzbprov = None
        return findit, nzbprov

    prov_order, newznab_info = provider_sequence(nzbprovider, torprovider, newznab_hosts)
    # end provider order sequencing
    logger.info('search provider order is ' + str(prov_order))

    #fix for issue dates between Nov-Dec/(Jan-Feb-Mar)
    IssDt = str(IssueDate)[5:7]
    if IssDt == "12" or IssDt == "11" or IssDt == "01" or IssDt == "02" or IssDt == "03":
         IssDateFix = IssDt
    else:
         IssDateFix = "no"

    searchcnt = 0
    i = 1

    if rsscheck:
        if mylar.ENABLE_RSS:
            searchcnt = 1  # rss-only
        else:
            searchcnt = 0  # if it's not enabled, don't even bother.
    else:
        if mylar.ENABLE_RSS:
            searchcnt = 2 # rss first, then api on non-matches
        else:
            searchcnt = 2  #set the searchcnt to 2 (api)
            i = 2          #start the counter at api, so it will exit without running RSS

    while (i <= searchcnt):
        #searchmodes:
        # rss - will run through the built-cached db of entries
        # api - will run through the providers via api (or non-api in the case of Experimental)
        # the trick is if the search is done during an rss compare, it needs to exit when done.
        # otherwise, the order of operations is rss feed check first, followed by api on non-results.

        if i == 1: searchmode = 'rss'  #order of ops - this will be used first.
        elif i == 2: searchmode = 'api'

        if findit == 'yes':
            logger.fdebug('Found result on first run, exiting search module now.')
            break

        logger.fdebug("Initiating Search via : " + str(searchmode))

        #torprtmp = 0 # torprtmp = torpr
        prov_count = 0

        if len(prov_order) == 1:
            tmp_prov_count = 1
        else:
            tmp_prov_count = len(prov_order)

        while (prov_count < tmp_prov_count): #len(prov_order) -1):
            send_prov_count = tmp_prov_count - prov_count
            newznab_host = None
            if prov_order[prov_count] == '32p':
                searchprov = '32P'
            elif prov_order[prov_count] == 'kat':
                searchprov = 'KAT'
            elif prov_order[prov_count] == 'torznab':
                searchprov = 'Torznab'
            elif 'newznab' in prov_order[prov_count]:
            #this is for newznab
                searchprov = 'newznab'
                for nninfo in newznab_info:
                    if nninfo['provider'] == prov_order[prov_count]:
                        newznab_host = nninfo['info']
                if newznab_host is None:
                    logger.fdebug('there was an error - newznab information was blank and it should not be.')
            else:
                newznab_host = None
                searchprov = prov_order[prov_count].lower()

            if searchprov == 'dognzb' and mylar.DOGNZB == 0:
                #since dognzb could hit the 50 daily api limit during the middle of a search run, check here on each pass to make
                #sure it's not disabled (it gets auto-disabled on maxing out the API hits)
                prov_count+=1
                continue
            if searchmode == 'rss':
                findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, searchprov, send_prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID, issuetitle=issuetitle, unaltered_ComicName=unaltered_ComicName)
                if findit == 'yes':
                    logger.fdebug("findit = found!")
                    break
                else:
                    if AlternateSearch is not None and AlternateSearch != "None":
                        chkthealt = AlternateSearch.split('##')
                        if chkthealt == 0:
                            AS_Alternate = AlternateSearch
                        loopit = len(chkthealt)
                        for calt in chkthealt:
                            AS_Alternate = re.sub('##', '', calt)
                            logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate) + " " + str(ComicYear))
                            findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, searchprov, send_prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID, issuetitle=issuetitle, unaltered_ComicName=AS_Alternate)
                            if findit == 'yes':
                                break
                        if findit == 'yes': break

            else:
                if searchprov == '32P':
                    logger.fdebug('32P backlog searching is not currently supported.')
                else:
                    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, searchprov, send_prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, ComicID=ComicID, issuetitle=issuetitle, unaltered_ComicName=unaltered_ComicName)
                    if findit == 'yes':
                        logger.fdebug("findit = found!")
                        break
                    else:
                        if AlternateSearch is not None and AlternateSearch != "None":
                            chkthealt = AlternateSearch.split('##')
                            if chkthealt == 0:
                                AS_Alternate = AlternateSearch
                            loopit = len(chkthealt)
                            for calt in chkthealt:
                                AS_Alternate = re.sub('##', '', calt)
                                logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate) + " " + str(ComicYear))
                                findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, searchprov, send_prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, ComicID=ComicID, issuetitle=issuetitle, unaltered_ComicName=unaltered_ComicName)
                                if findit == 'yes':
                                    break
                            if findit == 'yes': break

            if searchprov == 'newznab':
                searchprov = newznab_host[0].rstrip()
            logger.info('Could not find Issue ' + IssueNumber + ' of ' + ComicName + '(' + str(SeriesYear) + ') using ' + str(searchprov) + ' [' + str(searchmode) + ']')
            prov_count+=1
            #torprtmp+=1  #torprtmp-=1

        if findit == 'yes':
            #check for snatched_havetotal being enabled here and adjust counts now.
            #IssueID being the catch/check for one-offs as they won't exist on the watchlist and error out otherwise.
            if mylar.SNATCHED_HAVETOTAL and IssueID is not None:
                logger.fdebug('Adding this to the HAVE total for the series.')
                helpers.incr_snatched(ComicID)
            return findit, searchprov
        else:
            if searchprov == '32P':
                pass
            elif manualsearch is None:
                logger.info('Finished searching via :' + str(searchmode) + '. Issue not found - status kept as Wanted.')
            else:
                logger.fdebug('Could not find issue doing a manual search via : ' + str(searchmode))
            i+=1

    return findit, 'None'

def NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, nzbprov, prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host=None, ComicVersion=None, SARC=None, IssueArcID=None, RSS=None, ComicID=None, issuetitle=None, unaltered_ComicName=None):

    if nzbprov == 'nzb.su':
        apikey = mylar.NZBSU_APIKEY
        verify = bool(mylar.NZBSU_VERIFY)
    elif nzbprov == 'dognzb':
        apikey = mylar.DOGNZB_APIKEY
        verify = bool(mylar.DOGNZB_VERIFY)
    elif nzbprov == 'experimental':
        apikey = 'none'
        verify = False
    elif nzbprov == 'newznab':
        #updated to include Newznab Name now
        name_newznab = newznab_host[0].rstrip()
        host_newznab = newznab_host[1].rstrip()
        apikey = newznab_host[3].rstrip()
        verify = bool(newznab_host[2].rstrip())
        if '#' in newznab_host[4].rstrip():
            catstart = newznab_host[4].find('#')
            category_newznab = newznab_host[4][catstart +1:]
            logger.fdebug('non-default Newznab category set to :' + str(category_newznab))
        else:
            category_newznab = '7030'
        logger.fdebug("using Newznab host of : " + str(name_newznab))

    if RSS == "yes":
        if 'newznab' in nzbprov:
            tmpprov = name_newznab + '(' + nzbprov + ')' + ' [RSS]'
        else:
            tmpprov = str(nzbprov) + " [RSS]"
    else:
        if 'newznab' in nzbprov:
            tmpprov = name_newznab + ' (' + nzbprov + ')'
        else:
            tmpprov = nzbprov
    logger.info(u"Shhh be very quiet...I'm looking for " + ComicName + " issue: " + IssueNumber + " (" + str(ComicYear) + ") using " + str(tmpprov))

    #load in do not download db here for given series
    #myDB = db.DBConnection()
    #nodown = myDB.action('SELECT * FROM nzblog')

    #this will completely render the api search results empty. Needs to get fixed.
    if mylar.PREFERRED_QUALITY == 0: filetype = ""
    elif mylar.PREFERRED_QUALITY == 1: filetype = ".cbr"
    elif mylar.PREFERRED_QUALITY == 2: filetype = ".cbz"

    #UseFuzzy == 0: Normal
    #UseFuzzy == 1: Remove Year
    #UseFuzzy == 2: Fuzzy Year
    # figure out what was missed via rss feeds and do a manual search via api
    #tsc = int(tot-1)

#    findcomic = []
#    findcomiciss = []
#    findcount = 0
    ci = ""
    comsearch = []
    isssearch = []
    comyear = str(ComicYear)

    #print ("-------SEARCH FOR MISSING------------------")
    #ComicName is unicode - let's unicode and ascii it cause we'll be comparing filenames against it.
    u_ComicName = ComicName.encode('ascii', 'ignore').strip()
    findcomic = u_ComicName
    # this should be called elsewhere..redudant code.

#    elif 'au' in IssueNumber.lower():
#        iss = re.sub("[^0-9]", "", IssueNumber) # get just the digits
#        intIss = int(iss) * 1000
#        issue_except = 'AU'  # if it contains AU, mark it as an exception (future dict possibly)
#    elif 'ai' in IssueNumber.lower():
#        iss = re.sub("[^0-9]", "", IssueNumber) # get just the digits
#        intIss = int(iss) * 1000
#        issue_except = 'AI'  # if it contains AI, mark it as an exception (future dict possibly)
#    else:
#        iss = IssueNumber
#        intIss = int(iss) * 1000
#    #issue_decimal = re.compile(r'[^\d.]+')
#    #issue = issue_decimal.sub('', str(IssueNumber))
   #NEW ---
    intIss = helpers.issuedigits(IssueNumber)
    iss = IssueNumber
    if u'\xbd' in IssueNumber:
        findcomiciss = '0.5'
    elif u'\xbc' in IssueNumber:
        findcomiciss = '0.25'
    elif u'\xbe' in IssueNumber:
        findcomiciss = '0.75'
    elif u'\u221e' in IssueNumber:
        #issnum = utf-8 will encode the infinity symbol without any help
        findcomiciss = 'infinity'  # set 9999999999 for integer value of issue
    else:
        findcomiciss = iss

    #print ("we need : " + str(findcomic[findcount]) + " issue: #" + str(findcomiciss[findcount]))
    cm1 = re.sub("[\/]", " ", findcomic)
    # replace whitespace in comic name with %20 for api search
    #cm = re.sub("\&", "%26", str(cm1))
    cm = re.sub("\\band\\b", "", cm1.lower()) # remove 'and' & '&' from the search pattern entirely (broader results, will filter out later)
    cm = re.sub("\\bthe\\b", "", cm.lower()) # remove 'the' from the search pattern to accomodate naming differences
    cm = re.sub(" ", "%20", str(cm))
    cm = re.sub("[\&\:\?\,]", "", str(cm))

    #determine the amount of loops here
    i = 0
    c_alpha = None
    dsp_c_alpha = None
    c_number = None
    c_num_a4 = None
    while i < len(findcomiciss):
        #take first occurance of alpha in string and carry it through
        if findcomiciss[i].isalpha():
            c_alpha = findcomiciss[i:].rstrip()
            c_number = findcomiciss[:i].rstrip()
            break
        elif '.' in findcomiciss[i]:
            c_number = findcomiciss[:i].rstrip()
            c_num_a4 = findcomiciss[i+1:].rstrip()
            #if decimal seperates numeric from alpha (ie - 7.INH)
            #don't give calpha a value or else will seperate with a space further down
            #assign it to dsp_c_alpha so that it can be displayed for debugging.
            if not c_num_a4.isdigit():
                dsp_c_alpha = c_num_a4
            else:
                c_number = str(c_number) + '.' + str(c_num_a4)
            break
        i+=1
    logger.fdebug("calpha/cnumber: " + str(dsp_c_alpha) + " / " + str(c_number))

    if c_number is None:
        c_number = findcomiciss # if it's None, means no special alphas or decimals

    if '.' in c_number:
        decst = c_number.find('.')
        c_number = c_number[:decst].rstrip()
        #logger.fdebug('setting cmloopit to: ' + str(c_number))

    if len(c_number) == 1:
        cmloopit = 3
    elif len(c_number) == 2:
        cmloopit = 2
    else:
        cmloopit = 1

    isssearch = str(findcomiciss)
    comsearch = cm
    origcmloopit = cmloopit
    findcount = 1  # this could be a loop in the future possibly

    # ----

    #print ("------RESULTS OF SEARCH-------------------")
    findloop = 0
    foundcomic = []
    done = False
    seperatealpha = "no"
    #---issue problem
    # if issue is '011' instead of '11' in nzb search results, will not have same
    # results. '011' will return different than '11', as will '009' and '09'.

    while (findloop < findcount):
        #logger.fdebug('findloop: ' + str(findloop) + ' / findcount: ' + str(findcount))
        comsrc = comsearch
        if nzbprov == 'dognzb' and not mylar.DOGNZB:
            foundc = "no"
            done = True
            break
        while (cmloopit >= 1):
            #if issue_except is None: issue_exc = ''
            #else: issue_exc = issue_except
            if done is True and seperatealpha == "no":
                logger.fdebug("we should break out now - sucessful search previous")
                findloop == 99
                break
                # here we account for issue pattern variations
            if seperatealpha == "yes":
                isssearch = str(c_number) + "%20" + str(c_alpha)

            if cmloopit == 3:
                comsearch = comsrc + "%2000" + str(isssearch) #+ "%20" + str(filetype)
                issdig = '00'
            elif cmloopit == 2:
                comsearch = comsrc + "%200" + str(isssearch) #+ "%20" + str(filetype)
                issdig = '0'
            elif cmloopit == 1:
                comsearch = comsrc + "%20" + str(isssearch) #+ "%20" + str(filetype)
                issdig = ''

            mod_isssearch = str(issdig) + str(isssearch)

            #--- this is basically for RSS Feeds ---
            logger.fdebug('RSS Check: ' + str(RSS))
            logger.fdebug('nzbprov: ' + str(nzbprov))
            logger.fdebug('comicid: ' + str(ComicID))
            if RSS == "yes" or nzbprov == '32P':
                if nzbprov == '32P' or nzbprov == 'KAT':
                    cmname = re.sub("%20", " ", str(comsrc))
                    logger.fdebug("Sending request to [" + str(nzbprov) + "] RSS for " + str(findcomic) + " : " + str(mod_isssearch))
                    bb = rsscheck.torrentdbsearch(findcomic, mod_isssearch, ComicID, nzbprov)
                    rss = "yes"
                    #if bb is not None: logger.fdebug("bb results: " + str(bb))
                else:
                    cmname = re.sub("%20", " ", str(comsrc))
                    logger.fdebug("Sending request to RSS for " + str(findcomic) + " : " + str(mod_isssearch) + " (" + str(ComicYear) + ")")
                    if nzbprov == 'newznab':
                        nzbprov_fix = name_newznab
                    else: nzbprov_fix = nzbprov
                    bb = rsscheck.nzbdbsearch(findcomic, mod_isssearch, ComicID, nzbprov_fix, ComicYear, ComicVersion)
                    rss = "yes"
                    #if bb is not None: logger.fdebug("bb results: " +  str(bb))
            #this is the API calls
            else:
                #32P is redudant now since only RSS works
                # - just getting it ready for when it's not redudant :)
                if nzbprov == '' or nzbprov == '32P':
                    bb = "no results"
                    rss = "no"
                elif nzbprov == 'KAT':
                    cmname = re.sub("%20", " ", str(comsrc))
                    logger.fdebug("Sending request to [KAT] for " + str(cmname) + " : " + str(mod_isssearch))
                    bb = rsscheck.torrents(pickfeed='KAT', seriesname=cmname, issue=mod_isssearch)#cmname,issue=mod_isssearch)
                    rss = "no"
                    #if bb is not None: logger.fdebug("results: " + str(bb))
                elif nzbprov != 'experimental':
                    if nzbprov == 'dognzb':
                        findurl = "https://api.dognzb.cr/api?t=search&q=" + str(comsearch) + "&o=xml&cat=7030"
                    elif nzbprov == 'nzb.su':
                        findurl = "https://api.nzb.su/api?t=search&q=" + str(comsearch) + "&o=xml&cat=7030"
                    elif nzbprov == 'newznab':
                        #let's make sure the host has a '/' at the end, if not add it.
                        if host_newznab[len(host_newznab) -1:len(host_newznab)] != '/':
                            host_newznab_fix = str(host_newznab) + "/"
                        else: host_newznab_fix = host_newznab
                        findurl = str(host_newznab_fix) + "api?t=search&q=" + str(comsearch) + "&o=xml&cat=" + str(category_newznab)
                    elif nzbprov == 'Torznab':
                        if mylar.TORZNAB_HOST.endswith('/'):
                            #http://localhost:9117/api/iptorrents
                            torznab_fix = mylar.TORZNAB_HOST[:-1]
                        else:
                            torznab_fix = mylar.TORZNAB_HOST
                        findurl = str(torznab_fix) + "?t=search&q=" + str(comsearch) + "&o=xml&cat=" + str(mylar.TORZNAB_CATEGORY)
                        apikey = mylar.TORZNAB_APIKEY
                    if nzbprov != 'nzbx':
                        # helper function to replace apikey here so we avoid logging it ;)
                        findurl = findurl + "&apikey=" + str(apikey)
                        logsearch = helpers.apiremove(str(findurl), 'nzb')

                        ### IF USENET_RETENTION is set, honour it
                        ### For newznab sites, that means appending "&maxage=<whatever>" on the URL
                        if mylar.USENET_RETENTION != None and nzbprov != 'torznab':
                            findurl = findurl + "&maxage=" + str(mylar.USENET_RETENTION)

                        #set a delay between searches here. Default is for 60 seconds...
                        #changing this to lower could result in a ban from your nzb source due to hammering.
                        if mylar.SEARCH_DELAY == 'None' or mylar.SEARCH_DELAY is None:
                            pause_the_search = 60   # (it's in seconds)
                        elif str(mylar.SEARCH_DELAY).isdigit():
                            pause_the_search = int(mylar.SEARCH_DELAY) * 60
                        else:
                            logger.info("Check Search Delay - invalid numerical given. Force-setting to 1 minute.")
                            pause_the_search = 60

                        #bypass for local newznabs
                        #remove the protocol string (http/https)
                        localbypass = False
                        if nzbprov == 'newznab':
                            if host_newznab_fix.startswith('http'):
                                hnc = host_newznab_fix.replace('http://', '')
                            elif host_newznab_fix.startswith('https'):
                                hnc = host_newznab_fix.replace('https://', '')
                            else:
                                hnc = host_newznab_fix

                            if hnc[:3] == '10.' or hnc[:4] == '172.' or hnc[:4] == '192.' or hnc.startswith('localhost'):
                                localbypass = True

                        if localbypass == False:
                            logger.info("pausing for " + str(pause_the_search) + " seconds before continuing to avoid hammering")
                            time.sleep(pause_the_search)

                        # Add a user-agent
                        headers = {'User-Agent':   str(mylar.USER_AGENT)}
                        payload = None

                        if findurl.startswith('https:') and verify == False:
                            try:
                                from lib.requests.packages.urllib3 import disable_warnings
                                disable_warnings()
                            except:
                                logger.warn('Unable to disable https warnings. Expect some spam if using https nzb providers.')

                        elif findurl.startswith('http:') and verify == True:
                            verify = False

                        #logger.fdebug('[SSL: ' + str(verify) + '] Search URL: ' + findurl)
                        logger.fdebug('[SSL: ' + str(verify) + '] Search URL: ' + str(logsearch))

                        try:
                            r = requests.get(findurl, params=payload, verify=verify, headers=headers)
                        except Exception, e:
                            logger.warn('Error fetching data from %s: %s' % (nzbprov, e))
                            if 'HTTP Error 503' in e:
                                logger.warn('Aborting search due to Provider unavailability')
                                foundc = "no"
                                break
                            data = False

                        logger.info('status code: ' + str(r.status_code))

                        if str(r.status_code) != '200':
                            logger.warn('Unable to retrieve search results from ' + tmpprov + ' [Status Code returned: ' + str(r.status_code) + ']')
                            data = False
                        else:
                            data = r.content

                        if data:
                            bb = feedparser.parse(data)
                        else:
                            bb = "no results"

                        #logger.info('Search results:' + str(bb))
                        try:
                            if bb['feed']['error']:
                                logger.error('[ERROR CODE: ' + str(bb['feed']['error']['code']) + '] ' + str(bb['feed']['error']['description']))
                                if bb['feed']['error']['code'] == '910':
                                    logger.warn('DAILY API limit reached. Disabling provider usage until 12:01am')
                                    mylar.DOGNZB = 0
                                    foundc = False
                                    done = True
                                break
                        except:
                            #logger.info('no errors on data retrieval...proceeding')
                            pass
                elif nzbprov == 'experimental':
                    #bb = parseit.MysterBinScrape(comsearch[findloop], comyear)
                    bb = findcomicfeed.Startit(u_ComicName, isssearch, comyear, ComicVersion, IssDateFix)
                    # since the regexs in findcomicfeed do the 3 loops, lets force the exit after
                    #cmloopit == 1

            done = False
            foundc = "no"
            log2file = ""
            if bb == "no results":
                pass
                foundc = "no"
            else:
                for entry in bb['entries']:
                    logger.fdebug("checking search result: " + entry['title'])
                    #some nzbsites feel that comics don't deserve a nice regex to strip the crap from the header, the end result is that we're
                    #dealing with the actual raw header which causes incorrect matches below.
                    #this is a temporary cut from the experimental search option (findcomicfeed) as it does this part well usually.
                    except_list=['releases', 'gold line', 'distribution', '0-day', '0 day']
                    splitTitle = entry['title'].split("\"")
                    _digits = re.compile('\d')

                    ComicTitle = entry['title']
                    for subs in splitTitle:
                        logger.fdebug('sub:' + subs)
                        regExCount = 0
                        if len(subs) >= len(ComicName.split()) and not any(d in subs.lower() for d in except_list) and bool(_digits.search(subs)) is True:
                            if subs.lower().startswith('for'):
                                if ComicName.lower().startswith('for'):
                                    pass
                                else:
                                    #this is the crap we ignore. Continue (commented else, as it spams the logs)
                                    #logger.fdebug('this starts with FOR : ' + str(subs) + '. This is not present in the series - ignoring.')
                                    continue
                            logger.fdebug('Detected crap within header. Ignoring this portion of the result in order to see if it\'s a valid match.')
                            ComicTitle = subs
                            break

                    if nzbprov != "dognzb":
                        #rss for experimental doesn't have the size constraints embedded. So we do it here.
                        if RSS == "yes":
                            if nzbprov == '32P':
                                comsize_b = None
                            else:
                                comsize_b = entry['length']
                        else:
                            #Experimental already has size constraints done.
                            if nzbprov == '32P':
                                comsize_b = None #entry['length']
                            elif nzbprov == 'KAT':
                                comsize_b = entry['size']
                            elif nzbprov == 'experimental':
                                comsize_b = entry['length']  # we only want the size from the rss - the search/api has it already.
                            else:
                                tmpsz = entry.enclosures[0]
                                comsize_b = tmpsz['length']

                        #file restriction limitation here
                        #only works with KAT (done here) & 32P (done in rsscheck) & Experimental (has it embeded in search and rss checks)
                        if nzbprov == 'KAT':
                            if mylar.PREFERRED_QUALITY == 1:
                                if 'cbr' in entry['title']:
                                    logger.fdebug('Quality restriction enforced [ .cbr only ]. Accepting result.')
                                else:
                                    logger.fdebug('Quality restriction enforced [ .cbr only ]. Rejecting this result.')
                                    continue
                            elif mylar.PREFERRED_QUALITY == 2:
                                if 'cbz' in entry['title']:
                                    logger.fdebug('Quality restriction enforced [ .cbz only ]. Accepting result.')
                                else:
                                    logger.fdebug('Quality restriction enforced [ .cbz only ]. Rejecting this result.')
                                    continue

                        if comsize_b is None:
                            logger.fdebug('Size of file cannot be retrieved. Ignoring size-comparison and continuing.')
                            #comsize_b = 0
                        else:
                            comsize_m = helpers.human_size(comsize_b)
                            logger.fdebug("size given as: " + str(comsize_m))
                            #----size constraints.
                            #if it's not within size constaints - dump it now and save some time.
                            if mylar.USE_MINSIZE:
                                conv_minsize = helpers.human2bytes(mylar.MINSIZE + "M")
                                logger.fdebug("comparing Min threshold " + str(conv_minsize) + " .. to .. nzb " + str(comsize_b))
                                if int(conv_minsize) > int(comsize_b):
                                    logger.fdebug("Failure to meet the Minimum size threshold - skipping")
                                    continue
                            if mylar.USE_MAXSIZE:
                                conv_maxsize = helpers.human2bytes(mylar.MAXSIZE + "M")
                                logger.fdebug("comparing Max threshold " + str(conv_maxsize) + " .. to .. nzb " + str(comsize_b))
                                if int(comsize_b) > int(conv_maxsize):
                                    logger.fdebug("Failure to meet the Maximium size threshold - skipping")
                                    continue

#---- date constaints.
                    # if the posting date is prior to the publication date, dump it and save the time.
                    #logger.info('entry' + str(entry))
                    if nzbprov == 'experimental' or nzbprov =='32P':
                        pubdate = entry['pubdate']
                    else:
                        try:
                            pubdate = entry['updated']
                        except:
                            try:
                                pubdate = entry['pubdate']
                            except:
                                logger.fdebug('invalid date found. Unable to continue - skipping result.')
                                continue

                    if UseFuzzy == "1":
                        logger.fdebug('Year has been fuzzied for this series, ignoring store date comparison entirely.')
                        postdate_int = None
                        issuedate_int = None
                    else:

                        #use store date instead of publication date for comparisons since publication date is usually +2 months
                        if StoreDate is None or StoreDate == '0000-00-00':
                            if IssueDate is None or IssueDate == '0000-00-00':
                                logger.fdebug('Invalid store date & issue date detected - you probably should refresh the series or wait for CV to correct the data')
                                continue
                            else:
                                stdate = IssueDate
                        else:
                            stdate = StoreDate
                        # convert it to a tuple
                        dateconv = email.utils.parsedate_tz(pubdate)
                        # convert it to a numeric time, then subtract the timezone difference (+/- GMT)
                        if dateconv[-1] is not None:
                            postdate_int = time.mktime(dateconv[:len(dateconv) -1]) - dateconv[-1]
                        else:
                            postdate_int = time.mktime(dateconv[:len(dateconv) -1])
                        #convert it to a Thu, 06 Feb 2014 00:00:00 format
                        issue_convert = datetime.datetime.strptime(stdate.rstrip(), '%Y-%m-%d')
                        # to get past different locale's os-dependent dates, let's convert it to a generic datetime format
                        try:
                            stamp = time.mktime(issue_convert.timetuple())
                            issconv = format_date_time(stamp)
                        except OverflowError:
                            logger.fdebug('Error attempting to convert the timestamp into a generic format. Probably due to the epoch limiation.')
                            issconv = issue_convert.strftime('%a, %d %b %Y %H:%M:%S')
                        #convert it to a tuple
                        econv = email.utils.parsedate_tz(issconv)
                        #convert it to a numeric and drop the GMT/Timezone
                        try:
                            issuedate_int = time.mktime(econv[:len(econv) -1])
                        except OverflowError:
                            logger.fdebug('Unable to convert timestamp to integer format. Forcing things through.')
                            isyear = econv[1]
                            epochyr = '1970'
                            if int(isyear) <= int(epochyr):
                                tm = datetime.datetime(1970, 1, 1)
                                issuedate_int = int(time.mktime(tm.timetuple()))
                            else:
                                continue
                        if postdate_int < issuedate_int:
                            logger.fdebug(str(pubdate) + ' is before store date of ' + str(stdate) + '. Ignoring search result as this is not the right issue.')
                            continue
                        else:
                            logger.fdebug(str(pubdate) + ' is after store date of ' + str(stdate))

# -- end size constaints.

                    if '(digital first)' in ComicTitle.lower(): #entry['title'].lower():
                        dig_moving = re.sub('\(digital first\)', '', ComicTitle.lower()).strip() #entry['title'].lower()).strip()
                        dig_moving = re.sub('[\s+]', ' ', dig_moving)
                        dig_mov_end = dig_moving + ' (Digital First)'
                        thisentry = dig_mov_end
                    else:
                        thisentry = ComicTitle #entry['title']

                    logger.fdebug("Entry: " + thisentry)
                    cleantitle = thisentry

                    #remove the extension.
                    extensions = ('.cbr', '.cbz')
                    if cleantitle.lower().endswith(extensions):
                        fd, ext = os.path.splitext(cleantitle)
                        logger.fdebug("Removed extension from filename: " + ext)
                        #name = re.sub(str(ext), '', str(subname))
                        cleantitle = fd

                    if 'mixed format' in cleantitle.lower():
                        cleantitle = re.sub('mixed format', '', cleantitle).strip()
                        logger.fdebug('removed extra information after issue # that is not necessary: ' + str(cleantitle))

                    cleantitle = re.sub('[\_\.]', ' ', cleantitle)
                    cleantitle = helpers.cleanName(cleantitle)
                    # this is new - if title contains a '&' in the title it will assume the filename has ended at that point
                    # which causes false positives (ie. wolverine & the x-men becomes the x-men, which matches on x-men.
                    # 'the' is removed for comparisons later on
                    if '&' in cleantitle: cleantitle = re.sub('[\&]', 'and', cleantitle)

                    nzbname = cleantitle

                    # if it's coming from 32P, remove the ' -' at the end as it screws it up.
                    if nzbprov == '32P':
                        if cleantitle.endswith(' - '):
                            cleantitle = cleantitle[:-3]
                            logger.fdebug("cleaned up title to : " + str(cleantitle))

                    #adjust for covers only by removing them entirely...
                    logger.fdebug("Cleantitle: " + str(cleantitle))
                    vers4year = "no"
                    vers4vol = "no"
                    versionfound = "no"

                    if any(['cover only' in cleantitle.lower(), 'variant' in cleantitle.lower()]):
                        logger.fdebug("Ignoring title as Cover/Variant Only detected.")
                        cleantitle = "abcdefghijk 0 (1901).cbz"
                        continue

                    if ComicVersion:
                       ComVersChk = re.sub("[^0-9]", "", ComicVersion)
                       if ComVersChk == '' or ComVersChk == '1':
                            ComVersChk = 0
                    else:
                       ComVersChk = 0

                    ctchk = cleantitle.split()
                    ctchk_indexes = []
                    volfound = False
                    vol_nono = []
                    new_cleantitle = []

                    fndcomicversion = None
                    for ct in ctchk:
                        if any([ct.lower().startswith('v') and ct[1:].isdigit(), ct.lower()[:3] == 'vol', volfound == True]):
                            if volfound == True:
                                logger.fdebug('Split Volume label detected [' + ct + '] - ie. Vol 4. Attempting to adust.')
                                if ct.isdigit():
                                    vol_nono.append(ctchk.index(ct))
                                    #recreate the cleantitle, with the volume label completely removed (but stored for comparison later)
                                    ct = 'v' + str(ct)
                                    ctchk_indexes.extend(range(0, len(ctchk)))
                                    logger.info(ctchk_indexes)
                                    for i in ctchk_indexes:
                                        if i not in vol_nono:
                                            new_cleantitle.append(ctchk[i])
                                    cleantitle = ' '.join(new_cleantitle)
                                    logger.fdebug('Newly finished reformed cleantitle (with NO volume label): ' + cleantitle)
                                    volfound == False
                            tmpsplit = ct
                            if tmpsplit.lower().startswith('vol'):
                                logger.fdebug('volume detected - stripping and re-analzying for volume label.')
                                if '.' in tmpsplit:
                                    tmpsplit = re.sub('.', '', tmpsplit).strip()
                                tmpsplit = re.sub('vol', '', tmpsplit.lower()).strip()
                                #if vol label set as 'Vol 4' it will obliterate the Vol, but pass over the '4' - set
                                #volfound to True so that it can loop back around.
                                if not tmpsplit.isdigit():
                                    #vol_label = ct  #store the wording of how the Vol is defined so we can skip it later on.
                                    vol_nono.append(ctchk.index(ct))
                                    volfound = True
                                    continue

                            if len(tmpsplit[1:]) == 4 and tmpsplit[1:].isdigit():  #v2013
                                logger.fdebug("[Vxxxx] Version detected as " + str(tmpsplit))
                                vers4year = "yes" #re.sub("[^0-9]", " ", str(ct)) #remove the v
                                fndcomicversion = str(tmpsplit)
                            elif len(tmpsplit[1:]) == 1 and tmpsplit[1:].isdigit():  #v2
                                logger.fdebug("[Vx] Version detected as " + str(tmpsplit))
                                vers4vol = str(tmpsplit)
                                fndcomicversion = str(tmpsplit)
                            elif tmpsplit[1:].isdigit() and len(tmpsplit) < 4:
                                logger.fdebug('[Vxxx] Version detected as ' +str(tmpsplit))
                                vers4vol = str(tmpsplit)
                                fndcomicversion = str(tmpsplit)
                            elif tmpsplit.isdigit() and len(tmpsplit) <=4:
                                # this stuff is necessary for 32P volume manipulation
                                if len(tmpsplit) == 4:
                                    vers4year = "yes"
                                    fndcomicversion = str(tmpsplit)
                                elif len(tmpsplit) == 1:
                                    vers4vol = str(tmpsplit)
                                    fndcomicversion = str(tmpsplit)
                                elif len(tmpsplit) < 4:
                                    vers4vol = str(tmpsplit)
                                    fndcomicversion = str(tmpsplit)
                                else:
                                    logger.fdebug("error - unknown length for : " + str(tmpsplit))
                                    continue
                            else:
                                logger.fdebug("error - unknown length for : " + str(tmpsplit))
                                continue

                        if fndcomicversion:
                            versionfound = "yes"                            
                            break

                    if len(re.findall('[^()]+', cleantitle)) == 1 or 'cover only' in cleantitle.lower():
                        #some sites don't have (2013) or whatever..just v2 / v2013. Let's adjust:
                        #this handles when there is NO YEAR present in the title, otherwise versioning is way below.
                        if vers4year == "no" and vers4vol == "no":
                            # if the series is a v1, let's remove the requirements for year and volume label
                            # even if it's a v1, the nzbname might not contain a valid year format (20xx) or v3,
                            # and since it's already known that there is no (year) or vYEAR given
                            # let's push it through (and edit out the following if constraint)...

                            #if ComVersChk != 0:
                                # if there are no () in the string, try to add them if it looks like a year (19xx or 20xx)
                            if len(re.findall('[^()]+', cleantitle)):
                                logger.fdebug("detected invalid nzb filename - attempting to detect year to continue")
                                cleantitle = re.sub('(.*)\s+(19\d{2}|20\d{2})(.*)', '\\1 (\\2) \\3', cleantitle)
                            else:
                                logger.fdebug("invalid nzb and/or cover only - skipping.")
                                cleantitle = "abcdefghijk 0 (1901).cbz"
                                continue

                    #adjust for covers only by removing them entirely...
                    logger.fdebug("Cleantitle: " + str(cleantitle))


                    if done:
                        break
                #let's narrow search down - take out year (2010), (2011), etc
                #let's check for first occurance of '(' as generally indicates
                #that the 'title' has ended

                    ripperlist=['digital-',
                                'empire',
                                'dcp']
                    #this takes care of the brackets :)
                    m = re.findall('[^()]+', cleantitle)
                    lenm = len(m)

                    #print ("there are " + str(lenm) + " words.")
                    cnt = 0
                    yearmatch = "false"
                    pub_removed = None

                    while (cnt < lenm):
                        #print 'm[cnt]: ' + str(m[cnt])
                        if m[cnt] is None: break
                        if m[cnt] == ' ':
                            pass
                        else:
                            logger.fdebug(str(cnt) + ". Bracket Word: " + str(m[cnt]))
                        if cnt == 0:
                            comic_andiss = m[cnt]
                            if 'mixed format' in comic_andiss.lower():
                                comic_andiss = re.sub('mixed format', '', comic_andiss).strip()
                                logger.fdebug('removed extra information after issue # that is not necessary: ' + str(comic_andiss))
                            logger.fdebug("Comic: " + str(comic_andiss))
                            logger.fdebug("UseFuzzy is  : " + str(UseFuzzy))
                            logger.fdebug('ComVersChk : ' + str(ComVersChk))
                            if vers4vol != "no" or vers4year != "no":
                                logger.fdebug("Year not given properly formatted but Version detected.Bypassing Year Match.")
                                yearmatch = "true"
                            elif ComVersChk == 0:
                                logger.fdebug("Series version detected as V1 (only series in existance with that title). Bypassing Year/Volume check")
                                yearmatch = "true"
                        elif UseFuzzy == "0" or UseFuzzy == "2" or UseFuzzy is None or IssDateFix != "no":
                            if m[cnt][:-2] == '19' or m[cnt][:-2] == '20':
                                logger.fdebug('year detected: ' + str(m[cnt]))
                                result_comyear = m[cnt]
                                logger.fdebug('year looking for: ' + str(comyear))
                                if str(comyear) in result_comyear:
                                    logger.fdebug(str(comyear) + " - right years match baby!")
                                    yearmatch = "true"
                                else:
                                    logger.fdebug(str(comyear) + " - not right - years do not match")
                                    yearmatch = "false"
                                    if UseFuzzy == "2":
                                        #Fuzzy the year +1 and -1
                                        ComUp = int(ComicYear) + 1
                                        ComDwn = int(ComicYear) - 1
                                        if str(ComUp) in result_comyear or str(ComDwn) in result_comyear:
                                            logger.fdebug("Fuzzy Logic'd the Year and got a match with a year of " + str(result_comyear))
                                            yearmatch = "true"
                                        else:
                                            logger.fdebug(str(comyear) + "Fuzzy logic'd the Year and year still didn't match.")
                                #let's do this here and save a few extra loops ;)
                                #fix for issue dates between Nov-Dec/Jan
                                    if IssDateFix != "no" and UseFuzzy is not "2":
                                        if IssDateFix == "01" or IssDateFix == "02" or IssDateFix == "03":
                                            ComicYearFix = int(ComicYear) - 1
                                            if str(ComicYearFix) in result_comyear:
                                                logger.fdebug("further analysis reveals this was published inbetween Nov-Jan, decreasing year to " + str(ComicYearFix) + " has resulted in a match!")
                                                yearmatch = "true"
                                            else:
                                                logger.fdebug(str(comyear) + " - not the right year.")
                                        else:
                                            ComicYearFix = int(ComicYear) + 1
                                            if str(ComicYearFix) in result_comyear:
                                                logger.fdebug("further analysis reveals this was published inbetween Nov-Jan, incrementing year to " + str(ComicYearFix) + " has resulted in a match!")
                                                yearmatch = "true"
                                            else:
                                                logger.fdebug(str(comyear) + " - not the right year.")

                        elif UseFuzzy == "1": yearmatch = "true"
                        if Publisher is not None:
                            if Publisher.lower() in m[cnt].lower() and cnt >= 1:
                                #if the Publisher is given within the title or filename even (for some reason, some people
                                #have this to distinguish different titles), let's remove it entirely.
                                logger.fdebug('Publisher detected within title : ' + str(m[cnt]))
                                logger.fdebug('cnt is : ' + str(cnt) + ' --- Publisher is: ' + Publisher)
                                pub_removed = m[cnt]
                                #-strip publisher if exists here-
                                logger.fdebug('removing publisher from title')
                                cleantitle_pubremoved = re.sub(pub_removed, '', cleantitle)
                                logger.fdebug('pubremoved : ' + str(cleantitle_pubremoved))
                                cleantitle_pubremoved = re.sub('\(\)', '', cleantitle_pubremoved) #remove empty brackets
                                cleantitle_pubremoved = re.sub('\s+', ' ', cleantitle_pubremoved) #remove spaces > 1
                                logger.fdebug('blank brackets removed: ' + str(cleantitle_pubremoved))
                                #reset the values to initial without the publisher in the title
                                m = re.findall('[^()]+', cleantitle_pubremoved)
                                lenm = len(m)
                                cnt = 0
                                yearmatch = "false"
                                continue
                        if 'digital' in m[cnt] and len(m[cnt]) == 7:
                            logger.fdebug("digital edition detected")
                            pass
                        if ' of ' in m[cnt]:
                            logger.fdebug("mini-series detected : " + str(m[cnt]))
                            result_of = m[cnt]
                        if 'cover' in m[cnt]:
                            logger.fdebug("covers detected: " + str(m[cnt]))
                            result_comcovers = m[cnt]
                        for ripper in ripperlist:
                            if ripper in m[cnt]:
                                logger.fdebug("Scanner detected: " + str(m[cnt]))
                                result_comscanner = m[cnt]
                        cnt+=1
                    if yearmatch == "false": continue

                    splitit = []
                    watchcomic_split = []
                    logger.fdebug("original nzb comic and issue: " + str(comic_andiss))
                    #scan the returned name to see if it contains a '-', which typically denotes the start of an issuetitle
                    #if the series doesn't have a '-' within it.
                    hyphensplit = None
                    hyphenfail = False
                    issue_firstword = None
                    if unaltered_ComicName is not None:
                        ComicName = unaltered_ComicName
                    for m in re.finditer('[-/:]', comic_andiss):
                        #sometimes the : within a series title is replaced with a -, since filenames can't contain :
                        logger.fdebug('[' + ComicName + '] I have found a ' + str(m.group()) + '  within the nzbname @ position: ' + str(m.start()))
                        if str(m.group()) in ComicName: # and m.start() <= len(ComicName) + 2:
                            logger.fdebug('There is a ' + str(m.group()) + ' present in the series title. Ignoring position: ' + str(m.start()))
                            continue
                        else:
                            logger.fdebug('There is no hyphen present in the series title.')
                            logger.fdebug('Assuming position start is : ' + str(m.start()))
                            hyphensplit = comic_andiss[m.start():].split()
                            try:
                                issue_firstword = hyphensplit[1]
                                logger.fdebug('First word of issue stored as : ' + str(issue_firstword))
                            except:
                                if m.start() + 2 > len(comic_andiss.strip()):
                                    issue_firstword = None
                                else:
                                    logger.fdebug('Unable to parse title due to no space between hyphen. Ignoring this result.')
                                    hyphenfail = True
                            break

                    if hyphenfail == True:
                        continue

                    #changed this from '' to ' '
                    comic_iss_b4 = re.sub('[\-\:\,\?\!]', ' ', comic_andiss)
                    comic_iss_b4 = re.sub('\'', '', comic_iss_b4)
                    comic_iss = comic_iss_b4.replace('.', ' ')
                    #if issue_except: comic_iss = re.sub(issue_except.lower(), '', comic_iss)
                    logger.fdebug("adjusted nzb comic and issue: " + comic_iss)

                    splitit = comic_iss.split(None)
                    #something happened to dognzb searches or results...added a '.' in place of spaces
                    #screwed up most search results with dognzb. Let's try to adjust.
                    #watchcomic_split = findcomic[findloop].split(None)

                    if splitit[(len(splitit) -1)].isdigit():
                        #compares - if the last digit and second last digit are #'s seperated by spaces assume decimal
                        comic_iss = splitit[(len(splitit) -1)]
                        splitst = len(splitit) - 1
                        if splitit[(len(splitit) -2)].isdigit():
                            # for series that have a digit at the end, it screws up the logistics.
                            i = 1
                            chg_comic = splitit[0]
                            while (i < (len(splitit) -1)):
                                chg_comic = chg_comic + " " + splitit[i]
                                i+=1
                            logger.fdebug("chg_comic:" + str(chg_comic))
                            findcomic_chksplit = re.sub('[\-\:\,\.\?]', ' ', findcomic)
                            findcomic_chksplit = re.sub('[\&]', 'and', findcomic_chksplit)
                            findcomic_chksplit = re.sub('[\s]', '', findcomic_chksplit)
                            chg_comic = re.sub('[\-\:\,\.\?]', ' ', chg_comic)
                            chg_comic = re.sub('[\&]', 'and', chg_comic)
                            chg_comic = re.sub('[\s]', '', chg_comic)
                            logger.fdebug('chg_comic: ' + chg_comic.upper())
                            logger.fdebug('findcomic_chksplit: ' + findcomic_chksplit.upper())
                            if chg_comic.upper() in findcomic_chksplit.upper():
                                logger.fdebug("series contains numerics...adjusting..")
                            else:
                                changeup = "." + splitit[(len(splitit) -1)]
                                logger.fdebug("changeup to decimal: " + str(changeup))
                                comic_iss = splitit[(len(splitit) -2)] + "." + comic_iss
                                splitst = len(splitit) - 2
                    else:
                        #if the issue is alphanumeric (ie. 15AU, 12A) it'll error.
                        tmpiss = splitit[(len(splitit) -1)]
                        if not tmpiss.isdigit():
                            findstart = thisentry.find(splitit[(len(splitit) -1)])
                            #tmpiss = splitit[(len(splitit) -2)] + splitit[(len(splitit) -1)]
                            if thisentry[findstart -1] == '.':
                                comic_iss = splitit[(len(splitit) -2)] + '.' + splitit[(len(splitit) -1)]
                            else:
                                comic_iss = splitit[(len(splitit) -2)] + splitit[(len(splitit) -1)]
                            logger.fdebug('comic_iss is : ' + str(comic_iss))
                            splitst = len(splitit) - 2
                            logger.fdebug('issue number seperated. Rejoining to complete comparison properly to : ' + tmpiss)
                        else:
                            i = 0
                            alphas = None
                            a_issno = None
                            while (i < len(tmpiss)):
                                if tmpiss[i].isalpha():
                                #take first occurance of alpha in string and carry it through
                                    alphas = tmpiss[i:].rstrip()
                                    a_issno = tmpiss[:i +1].rstrip()
                                    break
                                i+=1
                            logger.fdebug("alphas: " + str(alphas))
                            logger.fdebug("a_issno: " + str(a_issno))
                            if alphas is None:
                                # if the nzb name doesn't follow the series-issue-year format even closely..ignore nzb
                                logger.fdebug("invalid naming format of nzb detected - cannot properly determine issue")
                                continue
                            else:
                                if a_issno == '' and alphas is not None:
                                    #if there' a space between the issue & alpha, join them.
                                    findstart = thisentry.find(splitit[(len(splitit) -1)])
                                    if thisentry[findstart -1] == '.':
                                        comic_iss = splitit[(len(splitit) -2)] + '.' + splitit[(len(splitit) -1)]
                                    else:
                                        comic_iss = splitit[(len(splitit) -2)] + splitit[(len(splitit) -1)]
                                    logger.fdebug('comic_iss is : ' + str(comic_iss))
                                    splitst = len(splitit) - 2
                                else:
                                    comic_iss = tmpiss
                                    splitst = len(splitit) - 1
                    logger.fdebug("adjusting from: " + str(comic_iss_b4) + " to: " + str(comic_iss))

                    # make sure that things like - in watchcomic are accounted for when comparing to nzb.
                    findcomic = re.sub('[\/]', ' ', findcomic)
                    watchcomic_split = helpers.cleanName(str(findcomic))
                    if '&' in watchcomic_split: watchcomic_split = re.sub('[/&]', 'and', watchcomic_split)
                    watchcomic_nonsplit = re.sub('[\-\:\,\.\?]', ' ', watchcomic_split)
                    watchcomic_nonsplit = re.sub('\'', '', watchcomic_nonsplit)
                    watchcomic_split = watchcomic_nonsplit.split(None)

                    logger.fdebug(str(splitit) + " nzb series word count: " + str(splitst))
                    logger.fdebug(str(watchcomic_split) + " watchlist word count: " + str(len(watchcomic_split)))
                    #account for possible version inclusion here and annual inclusions.
                    cvers = "false"
                    annualize = "false"
                    scount = 0

                    if 'annual' in ComicName.lower():
                        logger.fdebug("IssueID of : " + str(IssueID) + " - This is an annual...let's adjust.")
                        annualize = "true"
                        #splitst = splitst - 1

                    if versionfound == "yes":
#                        volfound = False
#                        vol_label = None
#                        for tstsplit in splitit:
#                            logger.fdebug('comparing ' + str(tstsplit))
#                            if volfound == True:
#                                logger.fdebug('Split Volume label detected - ie. Vol 4. Attempting to adust.')
#                                if tstsplit.isdigit():
#                                    vol_label = vol_label + ' ' + str(tstsplit)
#                                    tstsplit = 'v' + str(tstsplit)
#                                    volfound == False
#                            if tstsplit.lower().startswith('v'): #tstsplit[1:].isdigit():
#                                logger.fdebug("this has a version #...let's adjust")
#                                tmpsplit = tstsplit
#                                if tmpsplit.lower().startswith('vol'):
#                                    logger.fdebug('volume detected - stripping and re-analzying for volume label.')
#                                    if '.' in tmpsplit:
#                                        tmpsplit = re.sub('.', '', tmpsplit).strip()
#                                    tmpsplit = re.sub('vol', '', tmpsplit.lower()).strip()
#                                    #if vol label set as 'Vol 4' it will obliterate the Vol, but pass over the '4' - set
#                                    #volfound to True so that it can loop back around.
#                                    if not tmpsplit.isdigit():
#                                        vol_label = tstsplit  #store the wording of how the Vol is defined so we can skip it later on.
#                                        volfound = True
#                                        continue
#                                if len(tmpsplit[1:]) == 4 and tmpsplit[1:].isdigit():  #v2013
#                                    logger.fdebug("[Vxxxx] Version detected as " + str(tmpsplit))
#                                    vers4year = "yes" #re.sub("[^0-9]", " ", str(ct)) #remove the v
#                                elif len(tmpsplit[1:]) == 1 and tmpsplit[1:].isdigit():  #v2
#                                    logger.fdebug("[Vx] Version detected as " + str(tmpsplit))
#                                    vers4vol = str(tmpsplit)
#                                elif tmpsplit[1:].isdigit() and len(tmpsplit) < 4:
#                                    logger.fdebug('[Vxxx] Version detected as ' +str(tmpsplit))
#                                    vers4vol = str(tmpsplit)
#                                elif tmpsplit.isdigit() and len(tmpsplit) <=4:
#                                    # this stuff is necessary for 32P volume manipulation
#                                    if len(tmpsplit) == 4:
#                                        vers4year = "yes"
#                                    elif len(tmpsplit) == 1:
#                                        vers4vol = str(tmpsplit)
#                                    elif len(tmpsplit) < 4:
#                                        vers4vol = str(tmpsplit)
#                                    else:
#                                        logger.fdebug("error - unknown length for : " + str(tmpsplit))
#                                        continue
#                                else:
#                                    logger.fdebug("error - unknown length for : " + str(tmpsplit))
#                                    continue

                        logger.fdebug("volume detection commencing - adjusting length.")

                        logger.fdebug("watch comicversion is " + str(ComicVersion))
                        logger.fdebug("version found: " + str(fndcomicversion))
                        logger.fdebug("vers4year: " + str(vers4year))
                        logger.fdebug("vers4vol: " + str(vers4vol))

                        if vers4year is not "no" or vers4vol is not "no":

                            #if the volume is None, assume it's a V1 to increase % hits
                            if ComVersChk == 0:
                                D_ComicVersion = 1
                            else:
                                D_ComicVersion = ComVersChk

                        #if this is a one-off, SeriesYear will be None and cause errors.
                        if SeriesYear is None:
                            S_ComicVersion = 0
                        else:
                            S_ComicVersion = str(SeriesYear)

                        F_ComicVersion = re.sub("[^0-9]", "", fndcomicversion)
                        #if the found volume is a vol.0, up it to vol.1 (since there is no V0)
                        if F_ComicVersion == '0':
                            #need to convert dates to just be yyyy-mm-dd and do comparison, time operator in the below calc as well which probably throws off some accuracy.
                            F_ComicVersion = '1'
                            if postdate_int is not None:
                                if postdate_int >= issuedate_int and nzbprov == '32P':
                                    logger.fdebug('32P torrent discovery. Store date (' + str(stdate) + ') is before posting date (' + str(pubdate) + '), forcing volume label to be the same as series label (0-Day Enforcement): v' + str(F_ComicVersion) + ' --> v' + str(S_ComicVersion))
                                    F_ComicVersion = D_ComicVersion

                        logger.fdebug("FCVersion: " + str(F_ComicVersion))
                        logger.fdebug("DCVersion: " + str(D_ComicVersion))
                        logger.fdebug("SCVersion: " + str(S_ComicVersion))

                        #here's the catch, sometimes annuals get posted as the Pub Year
                        # instead of the Series they belong to (V2012 vs V2013)
                        if annualize == "true" and int(ComicYear) == int(F_ComicVersion):
                            logger.fdebug("We matched on versions for annuals " + str(fndcomicversion))
                            #scount+=1
                            #cvers = "true"

                        elif int(F_ComicVersion) == int(D_ComicVersion) or int(F_ComicVersion) == int(S_ComicVersion):
                            logger.fdebug("We matched on versions..." + str(fndcomicversion))
                            #scount+=1
                            #cvers = "true"

                        else:
                            logger.fdebug("Versions wrong. Ignoring possible match.")
                            #scount = 0
                            #cvers = "false"

                        #if cvers == "true":
                            #since we matched on versions, let's remove it entirely to improve matching.
                            #logger.fdebug('Removing versioning [' + fndcomicversion + '] from nzb filename to improve matching algorithims.')
                            #cissb4vers = re.sub(fndcomicversion, "", comic_iss_b4).strip()
                            #logger.fdebug('New b4split : ' + str(cissb4vers))
                            #splitit = cissb4vers.split(None)
                            #splitst -=1

                    #do an initial check
                    initialchk = 'ok'
                    isstitle_chk = False
                    if (splitst) != len(watchcomic_split):

                        if issue_firstword:
                            vals = IssueTitleCheck(issuetitle, watchcomic_split, splitit, splitst, issue_firstword, hyphensplit, orignzb=ComicTitle) #entry['title'])

                            if vals is not None:
                                if vals[0]['status'] == 'continue':
                                    continue
                                else:
                                    if vals[0]['status'] == 'ok':
                                        logger.fdebug('Issue title matched.')  # will either be OK or pass.
                                        splitst = vals[0]['splitst']
                                        splitit = vals[0]['splitit']
                                        issue_title_remove = vals[0]['isstitle_removal']
                                        logger.info('removing: ' + str(issue_title_remove))
                                        splitit_tmp = []
                                        for item in (x for x in splitit if x not in issue_title_remove):
                                            splitit_tmp.append(item)

                                        if splitit_tmp is not None:
                                            splitit = splitit_tmp
                                        if vals[0]['isstitle_chk'] == True:
                                            isstitle_chk = True
                                            possibleissue_num = vals[0]['possibleissue_num']

                                        logger.info('final name: ' + str(splitit))

                            else:
                                logger.fdebug('No issue title.')

                        for tstsplit in splitit:
                            if tstsplit.lower() == 'the':
                                logger.fdebug("THE word detected in found comic...attempting to adjust pattern matching")
                                #print comic_iss_b4
                                #print comic_iss_b4[4:]
                                #splitit = comic_iss_b4[4:].split(None)
                                if cvers == "true":
                                    use_this = cissb4vers
                                else:
                                    use_this = comic_iss_b4
                                logger.fdebug('Use_This is : ' + str(use_this))
                                cissb4this = re.sub("\\bthe\\b", "", use_this) #comic_iss_b4)
                                splitit = cissb4this.split(None)
                                splitst = splitst - 1 #remove 'the' from start
                                logger.fdebug("comic is now : " + str(splitit))#str(comic_iss[4:]))
                                #if str(watchcomic_split[0]).lower() == "the":

                        for tstsplit in watchcomic_split:
                            if tstsplit.lower() == 'the':
                                logger.fdebug("THE word detected in watchcomic - attempting to adjust match.")
                                #wtstart = watchcomic_nonsplit[4:]
                                #watchcomic_split = wtstart.split(None)
                                wtstart = re.sub("\\bthe\\b", "", watchcomic_nonsplit)
                                watchcomic_split = wtstart.split(None)
                                logger.fdebug("new watchcomic string:" + str(watchcomic_split))
                        initialchk = 'no'
                    else:
                        initialchk = 'ok'

                    logger.fdebug("splitst : " + str(splitst))
                    logger.fdebug("len-watchcomic : " + str(len(watchcomic_split)))
                    if (splitst) != len(watchcomic_split) and initialchk == 'no':
                        logger.fdebug("incorrect comic lengths after removal...not a match.")
                    else:
                        logger.fdebug("length match..proceeding")
                        n = 0
                        logger.fdebug("search-length: " + str(splitst))
                        logger.fdebug("Watchlist-length: " + str(len(watchcomic_split)))
                        if cvers == "true": splitst = splitst + 1
                        while (n <= (splitst) -1):
                            logger.fdebug("splitit: " + str(splitit[n]))
                            logger.fdebug("scount : " + str(scount))
                            if n < (splitst) and n < len(watchcomic_split):
                                logger.fdebug(str(n) + " Comparing: " + str(watchcomic_split[n]) + " .to. " + str(splitit[n]))
                                if '+' in watchcomic_split[n]:
                                    watchcomic_split[n] = re.sub('+', '', str(watchcomic_split[n]))
                                if str(watchcomic_split[n].lower()) in str(splitit[n].lower()) and len(watchcomic_split[n]) >= len(splitit[n]):
                                    logger.fdebug("word matched on : " + str(splitit[n]))
                                    scount+=1
                                #elif ':' in splitit[n] or '-' in splitit[n]:
                                #    splitrep = splitit[n].replace('-', '')
                                #    print ("non-character keyword...skipped on " + splitit[n])

                            else:
                                logger.fdebug("Comic / Issue section")
                                if splitit[n].isdigit():
                                    logger.fdebug("issue detected")
                                    #comiss = splitit[n]
                                    comicNAMER = n - 1
                                    comNAME = splitit[0]
                                    cmnam = 1
                                    while (cmnam <= comicNAMER):
                                        comNAME = str(comNAME) + " " + str(splitit[cmnam])
                                        cmnam+=1
                                    logger.fdebug("comic: " + str(comNAME))
                                else:
                                    logger.fdebug("non-match for: "+ str(splitit[n]))
                                    pass
                            n+=1
                        #set the match threshold to 80% (for now)
                        # if it's less than 80% consider it a non-match and discard.
                        #splitit has to splitit-1 because last position is issue.
                        wordcnt = int(scount)
                        logger.fdebug("scount:" + str(wordcnt))
                        totalcnt = int(splitst)
                        logger.fdebug("splitit-len:" + str(totalcnt))
                        try:
                            spercent = (wordcnt /totalcnt) * 100
                        except ZeroDivisionError:
                            spercent = 0
                        logger.fdebug("Match to series : " + str(spercent) + " %.")

                        #series match comparison - use mylar.PERCENTAGE_MATCH for user-defined threshold for matching comparison.
                        if int(spercent) >= 80:
                            logger.fdebug("it's a go captain... - we matched " + str(spercent) + "%!")
                        if int(spercent) < 80:
                            logger.fdebug("failure - we only got " + str(spercent) + "% right!")
                            continue
                        logger.fdebug("this should be a match!")
                        logger.fdebug("issue we are looking for is : " + str(findcomiciss))
                        logger.fdebug("integer value of issue we are looking for : " + str(intIss))

                        fnd_iss_except = None
                        #if the issue title was present and it contained a numeric, it will pull that as the issue incorrectly
                        if isstitle_chk == True:
                            comic_iss = possibleissue_num
                        logger.fdebug("issue we found for is : " + str(comic_iss))
                        comintIss = helpers.issuedigits(comic_iss)
                        logger.fdebug("integer value of issue we have found : " + str(comintIss))

                        #issue comparison now as well
                        if int(intIss) == int(comintIss):

                            #modify the name for annualization to be displayed properly
                            if annualize == True:
                                modcomicname = ComicName + ' Annual'
                            else:
                                modcomicname = ComicName


                            comicinfo = []
                            comicinfo.append({"ComicName":     ComicName,
                                              "IssueNumber":   IssueNumber,
                                              "comyear":       comyear,
                                              "modcomicname":  modcomicname})

                            #generate nzbname
                            nzbname = nzbname_create(nzbprov, info=comicinfo, title=ComicTitle) #entry['title'])

                            #generate the send-to and actually send the nzb / torrent.
                            searchresult = searcher(nzbprov, nzbname, comicinfo, entry['link'], IssueID, ComicID, tmpprov, newznab=newznab_host)

                            if searchresult == 'downloadchk-fail':
                                continue
                            elif searchresult == 'torrent-fail' or searchresult == 'nzbget-fail' or searchresult == 'sab-fail' or searchresult == 'blackhole-fail':
                                return
                            else:
                                #nzbid, nzbname, sent_to
                                nzbid = searchresult[0]['nzbid']
                                nzbname = searchresult[0]['nzbname']
                                sent_to = searchresult[0]['sent_to']
                                alt_nzbname = searchresult[0]['alt_nzbname']
                            foundc = "yes"
                            done = True
                            break
                        else:
                            log2file = log2file + "issues don't match.." + "\n"
                            foundc = "no"
                    if done == True:
                        cmloopit == 1 #let's make sure it STOPS searching after a sucessful match.
                        break
            cmloopit-=1
            if cmloopit < 1 and c_alpha is not None and seperatealpha == "no" and foundc == "no":
                logger.info("Alphanumerics detected within IssueNumber. Seperating from Issue # and re-trying.")
                cmloopit = origcmloopit
                seperatealpha = "yes"

        findloop+=1
        if foundc == "yes":
            foundcomic.append("yes")
            if alt_nzbname is None or alt_nzbname == '':
                logger.fdebug("Found matching comic...preparing to send to Updater with IssueID: " + str(IssueID) + " and nzbname: " + str(nzbname))
                if '[RSS]' in tmpprov: tmpprov = re.sub('\[RSS\]', '', tmpprov).strip()
                updater.nzblog(IssueID, nzbname, ComicName, SARC=SARC, IssueArcID=IssueArcID, id=nzbid, prov=tmpprov)
            else:
                logger.fdebug("Found matching comic...preparing to send to Updater with IssueID: " + str(IssueID) + " and nzbname: " + str(nzbname) + '[' + alt_nzbname + ']')
                if '[RSS]' in tmpprov: tmpprov = re.sub('\[RSS\]', '', tmpprov).strip()
                updater.nzblog(IssueID, nzbname, ComicName, SARC=SARC, IssueArcID=IssueArcID, id=nzbid, prov=tmpprov, alt_nzbname=alt_nzbname)
#            #send out the notifications for the snatch.
            notify_snatch(nzbname, sent_to, helpers.filesafe(modcomicname), comyear, IssueNumber, nzbprov)
            prov_count == 0
            #break
            return foundc

        if foundc == "no":# and prov_count == 0:
            #logger.fdebug('prov_count: ' + str(prov_count))
            foundcomic.append("no")
            if IssDateFix == "no":
                #logger.info('Could not find Issue ' + str(IssueNumber) + ' of ' + ComicName + '(' + str(comyear) + ') using ' + str(tmpprov) + '. Status kept as wanted.' )
                break
    return foundc

def searchforissue(issueid=None, new=False, rsscheck=None):
    myDB = db.DBConnection()

    if not issueid or rsscheck:

        if rsscheck:
            logger.info(u"Initiating Search Scan at scheduled interval of " + str(mylar.RSS_CHECKINTERVAL) + " minutes.")
        else:
            logger.info(u"Initiating Search scan at requested interval of " + str(mylar.SEARCH_INTERVAL) + " minutes.")

        myDB = db.DBConnection()

        stloop = 1
        results = []

        if mylar.ANNUALS_ON:
            stloop+=1
        while (stloop > 0):
            if stloop == 1:
                if mylar.FAILED_DOWNLOAD_HANDLING and mylar.FAILED_AUTO:
                    issues_1 = myDB.select('SELECT * from issues WHERE Status="Wanted" OR Status="Failed"')
                else:
                    issues_1 = myDB.select('SELECT * from issues WHERE Status="Wanted"')
                for iss in issues_1:
                    results.append({'ComicID':       iss['ComicID'],
                                    'IssueID':       iss['IssueID'],
                                    'Issue_Number':  iss['Issue_Number'],
                                    'IssueDate':     iss['IssueDate'],
                                    'StoreDate':     iss['ReleaseDate'],
                                    'mode':          'want'
                                   })
            elif stloop == 2:
                if mylar.FAILED_DOWNLOAD_HANDLING and mylar.FAILED_AUTO:
                    issues_2 = myDB.select('SELECT * from annuals WHERE Status="Wanted" OR Status="Failed"')
                else:
                    issues_2 = myDB.select('SELECT * from annuals WHERE Status="Wanted"')
                for iss in issues_2:
                    results.append({'ComicID':       iss['ComicID'],
                                    'IssueID':       iss['IssueID'],
                                    'Issue_Number':  iss['Issue_Number'],
                                    'IssueDate':     iss['IssueDate'],
                                    'StoreDate':     iss['ReleaseDate'],   #need to replace with Store date
                                    'mode':          'want_ann'
                                   })
            stloop-=1

        new = True

        #to-do: re-order the results list so it's most recent to least recent.

        for result in results:
            comic = myDB.selectone("SELECT * from comics WHERE ComicID=? AND ComicName != 'None'", [result['ComicID']]).fetchone()
            if comic is None:
                logger.fdebug(str(result['ComicID']) + ' has no associated comic information. Skipping searching for this series.')
                continue
            if result['StoreDate'] == '0000-00-00' or result['StoreDate'] is None:
                if result['IssueDate'] is None or result['IssueDate'] == '0000-00-00':
                    logger.fdebug('ComicID: ' + str(result['ComicID']) + ' has invalid Date data. Skipping searching for this series.')
                    continue
            foundNZB = "none"
            SeriesYear = comic['ComicYear']
            Publisher = comic['ComicPublisher']
            AlternateSearch = comic['AlternateSearch']
            IssueDate = result['IssueDate']
            StoreDate = result['StoreDate']
            UseFuzzy = comic['UseFuzzy']
            ComicVersion = comic['ComicVersion']
            if result['IssueDate'] == None:
                ComicYear = comic['ComicYear']
            else:
                ComicYear = str(result['IssueDate'])[:4]
            mode = result['mode']
            if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL or mylar.NEWZNAB or mylar.ENABLE_KAT or mylar.ENABLE_32P) and (mylar.USE_SABNZBD or mylar.USE_NZBGET or mylar.ENABLE_TORRENTS or mylar.USE_BLACKHOLE):
                    foundNZB, prov = search_init(comic['ComicName'], result['Issue_Number'], str(ComicYear), comic['ComicYear'], Publisher, IssueDate, StoreDate, result['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, SARC=None, IssueArcID=None, mode=mode, rsscheck=rsscheck, ComicID=result['ComicID'], filesafe=comic['ComicName_Filesafe'])
                    if foundNZB == "yes":
                        #print ("found!")
                        updater.foundsearch(result['ComicID'], result['IssueID'], mode=mode, provider=prov)
                    else:
                        pass
                        #print ("not found!")

        if rsscheck:
            logger.info('Completed RSS Search scan')
        else:
            logger.info('Completed NZB Search scan')


    else:
        result = myDB.selectone('SELECT * FROM issues where IssueID=?', [issueid]).fetchone()
        mode = 'want'
        if result is None:
            result = myDB.selectone('SELECT * FROM annuals where IssueID=?', [issueid]).fetchone()
            mode = 'want_ann'
            if result is None:
                logger.fdebug("Unable to locate IssueID - you probably should delete/refresh the series.")
                return
        ComicID = result['ComicID']
        comic = myDB.selectone('SELECT * FROM comics where ComicID=?', [ComicID]).fetchone()
        SeriesYear = comic['ComicYear']
        Publisher = comic['ComicPublisher']
        AlternateSearch = comic['AlternateSearch']
        IssueDate = result['IssueDate']
        StoreDate = result['ReleaseDate']
        UseFuzzy = comic['UseFuzzy']
        ComicVersion = comic['ComicVersion']
        if result['IssueDate'] == None:
            IssueYear = comic['ComicYear']
        else:
            IssueYear = str(result['IssueDate'])[:4]

        foundNZB = "none"
        if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL or mylar.NEWZNAB or mylar.ENABLE_KAT or mylar.ENABLE_32P) and (mylar.USE_SABNZBD or mylar.USE_NZBGET or mylar.ENABLE_TORRENTS or mylar.USE_BLACKHOLE):
            foundNZB, prov = search_init(comic['ComicName'], result['Issue_Number'], str(IssueYear), comic['ComicYear'], Publisher, IssueDate, StoreDate, result['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, SARC=None, IssueArcID=None, mode=mode, rsscheck=rsscheck, ComicID=result['ComicID'], filesafe=comic['ComicName_Filesafe'])
            if foundNZB == "yes":
                logger.fdebug("I found " + comic['ComicName'] + ' #:' + str(result['Issue_Number']))
                updater.foundsearch(ComicID=result['ComicID'], IssueID=result['IssueID'], mode=mode, provider=prov)
            else:
                pass
                #print ("not found!")
    return

def searchIssueIDList(issuelist):
    myDB = db.DBConnection()
    for issueid in issuelist:
        issue = myDB.selectone('SELECT * from issues WHERE IssueID=?', [issueid]).fetchone()
        mode = 'want'
        if issue is None:
            issue = myDB.selectone('SELECT * from annuals WHERE IssueID=?', [issueid]).fetchone()
            mode = 'want_ann'
            if issue is None:
                logger.info("unable to determine IssueID - perhaps you need to delete/refresh series?")
                break
        comic = myDB.selectone('SELECT * from comics WHERE ComicID=?', [issue['ComicID']]).fetchone()
        print ("Checking for issue: " + str(issue['Issue_Number']))
        foundNZB = "none"
        SeriesYear = comic['ComicYear']
        AlternateSearch = comic['AlternateSearch']
        Publisher = comic['ComicPublisher']
        UseFuzzy = comic['UseFuzzy']
        ComicVersion = comic['ComicVersion']
        if issue['IssueDate'] == None:
            IssueYear = comic['ComicYear']
        else:
            IssueYear = str(issue['IssueDate'])[:4]
        if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL or mylar.NEWZNAB or mylar.ENABLE_32P or mylar.ENABLE_KAT) and (mylar.USE_SABNZBD or mylar.USE_NZBGET or mylar.ENABLE_TORRENTS or mylar.USE_BLACKHOLE):
                foundNZB, prov = search_init(comic['ComicName'], issue['Issue_Number'], str(IssueYear), comic['ComicYear'], Publisher, issue['IssueDate'], issue['ReleaseDate'], issue['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, SARC=None, IssueArcID=None, mode=mode, ComicID=issue['ComicID'], filesafe=comic['ComicName_Filesafe'])
                if foundNZB == "yes":
                    #print ("found!")
                    updater.foundsearch(ComicID=issue['ComicID'], IssueID=issue['IssueID'], mode=mode, provider=prov)
                else:
                    pass
                    #print ("not found!")



def provider_sequence(nzbprovider, torprovider, newznab_hosts):
    #provider order sequencing here.
    newznab_info = []
    prov_order = []

    nzbproviders_lower = [x.lower() for x in nzbprovider]

    if len(mylar.PROVIDER_ORDER) > 0:
        for pr_order in mylar.PROVIDER_ORDER:
            #logger.fdebug('looking for ' + str(pr_order[1]).lower())
            #logger.fdebug('nzbproviders ' + str(nzbproviders_lower))
            #logger.fdebug('torproviders ' + str(torprovider))
            if (pr_order[1].lower() in torprovider) or any(pr_order[1].lower() in x for x in nzbproviders_lower):
                logger.fdebug('found provider in existing enabled providers.')
                if any(pr_order[1].lower() in x for x in nzbproviders_lower):
                    # this is for nzb providers
                    for np in nzbprovider:
                        logger.fdebug('checking against nzb provider: ' + str(np))
                        if all(['newznab' in np, pr_order[1].lower() in np.lower()]):
                            logger.fdebug('newznab match against: ' + str(np))
                            for newznab_host in newznab_hosts:
                                #logger.fdebug('comparing ' + str(pr_order[1]).lower() + ' against: ' + str(newznab_host[0]).lower())
                                if newznab_host[0].lower() == pr_order[1].lower():
                                    logger.fdebug('sucessfully matched - appending to provider.order sequence')
                                    prov_order.append(np) #newznab_host)
                                    newznab_info.append({"provider":     np,
                                                         "info": newznab_host})
                                    break
                                else:
                                    if newznab_host[0] == "":
                                        if newznab_host[1].lower() == pr_order[1].lower():
                                            prov_order.append(np) #newznab_host)
                                            newznab_info.append({"provider":     np,
                                                                 "info": newznab_host})
                                            break
                        elif pr_order[1].lower() in np.lower():
                            prov_order.append(pr_order[1])
                            break
                else:
                    for tp in torprovider:
                        logger.fdebug('checking against torrent provider: ' + str(tp))
                        if (pr_order[1].lower() in tp.lower()):
                            logger.fdebug('torrent provider found: ' + str(tp))
                            prov_order.append(tp) #torrent provider
                            break

                logger.fdebug('provider order sequence is now to start with ' + pr_order[1] + ' at spot #' + str(pr_order[0]))

    return prov_order, newznab_info

def nzbname_create(provider, title=None, info=None):
    #the nzbname here is used when post-processing
    # it searches nzblog which contains the nzbname to pull out the IssueID and start the post-processing
    # it is also used to keep the hashinfo for the nzbname in case it fails downloading, it will get put into the failed db for future exclusions

    if mylar.USE_BLACKHOLE and provider != '32P' and provider != 'KAT':
        if os.path.exists(mylar.BLACKHOLE_DIR):
            #load in the required info to generate the nzb names when required (blackhole only)
            ComicName = info[0]['ComicName']
            IssueNumber = info[0]['IssueNumber']
            comyear = info[0]['comyear']
            #pretty this biatch up.
            BComicName = re.sub('[\:\,\/\?\']', '', str(ComicName))
            Bl_ComicName = re.sub('[\&]', 'and', str(BComicName))
            if u'\xbd' in IssueNumber:
                str_IssueNumber = '0.5'
            elif u'\xbc' in IssueNumber:
                str_IssueNumber = '0.25'
            elif u'\xbe' in IssueNumber:
                str_IssueNumber = '0.75'
            elif u'\u221e' in IssueNumber:
                str_IssueNumber = 'infinity'
            else:
                str_IssueNumber = IssueNumber
            nzbname = str(re.sub(" ", ".", str(Bl_ComicName))) + "." + str(str_IssueNumber) + ".(" + str(comyear) + ")"

            logger.fdebug("nzb name to be used for post-processing is : " + str(nzbname))

    elif provider == '32P' or provider == 'KAT':
        #filesafe the name cause people are idiots when they post sometimes.
        nzbname = re.sub('\s{2,}', ' ', helpers.filesafe(title)).strip()
        #let's change all space to decimals for simplicity
        nzbname = re.sub(" ", ".", nzbname)
        #gotta replace & or escape it
        nzbname = re.sub("\&", 'and', nzbname)
        nzbname = re.sub('[\,\:\?\']', '', nzbname)
        if nzbname.lower().endswith('.torrent'):
            nzbname = re.sub('.torrent', '', nzbname)

    else:
        # let's change all space to decimals for simplicity
        logger.fdebug('[SEARCHER] entry[title]: ' + title)
        #gotta replace & or escape it
        nzbname = re.sub("\&", 'and', title)
        nzbname = re.sub('[\,\:\?\'\+]', '', nzbname)
        nzbname = re.sub('[\(\)]', ' ', nzbname)
        logger.fdebug('[SEARCHER] nzbname (remove chars): ' + nzbname)
        nzbname = re.sub('.cbr', '', nzbname).strip()
        nzbname = re.sub('.cbz', '', nzbname).strip()
        nzbname = re.sub('[\.\_]', ' ', nzbname).strip()
        nzbname = re.sub('\s+', ' ', nzbname)  #make sure we remove the extra spaces.
        logger.fdebug('[SEARCHER] nzbname (\s): ' + nzbname)
        nzbname = re.sub(' ', '.', nzbname)
        #remove the [1/9] parts or whatever kinda crap (usually in experimental results)
        pattern = re.compile(r'\W\d{1,3}\/\d{1,3}\W')
        match = pattern.search(nzbname)
        if match:
            nzbname = re.sub(match.group(), '', nzbname).strip()
        logger.fdebug('[SEARCHER] end nzbname: ' + nzbname)

    logger.fdebug("nzbname used for post-processing:" + nzbname)
    return nzbname

def searcher(nzbprov, nzbname, comicinfo, link, IssueID, ComicID, tmpprov, directsend=None, newznab=None):
    alt_nzbname = None

    #load in the details of the issue from the tuple.
    ComicName = comicinfo[0]['ComicName']
    IssueNumber = comicinfo[0]['IssueNumber']
    comyear = comicinfo[0]['comyear']
    modcomicname = comicinfo[0]['modcomicname']

    #setup the priorities.
    if mylar.SAB_PRIORITY:
        if mylar.SAB_PRIORITY == "Default": sabpriority = "-100"
        elif mylar.SAB_PRIORITY == "Low": sabpriority = "-1"
        elif mylar.SAB_PRIORITY == "Normal": sabpriority = "0"
        elif mylar.SAB_PRIORITY == "High": sabpriority = "1"
        elif mylar.SAB_PRIORITY == "Paused": sabpriority = "-2"
    else:
        #if sab priority isn't selected, default to Normal (0)
        sabpriority = "0"

    if mylar.NZBGET_PRIORITY:
        if mylar.NZBGET_PRIORITY == "Default": nzbgetpriority = "0"
        elif mylar.NZBGET_PRIORITY == "Low": nzbgetpriority = "-50"
        elif mylar.NZBGET_PRIORITY == "Normal": nzbgetpriority = "0"
        elif mylar.NZBGET_PRIORITY == "High": nzbgetpriority = "50"
        #there's no priority for "paused", so set "Very Low" and deal with that later...
        elif mylar.NZBGET_PRIORITY == "Paused": nzbgetpriority = "-100"
    else:
        #if sab priority isn't selected, default to Normal (0)
        nzbgetpriority = "0"

    nzbid = generate_id(nzbprov, link)

    if link and (nzbprov != 'KAT' and nzbprov != '32P' and nzbprov != 'Torznab'):

        #generate nzbid here.

        nzo_info = {}
        filen = None
        nzbmega = False
        payload = None
        headers = {'User-Agent': str(mylar.USER_AGENT)}
        #link doesn't have the apikey - add it and use ?t=get for newznab based.

        if nzbprov == 'newznab' or nzbprov == 'nzb.su':
            #need to basename the link so it just has the id/hash.
            #rss doesn't store apikey, have to put it back.
            if nzbprov == 'newznab':
                name_newznab = newznab[0].rstrip()
                host_newznab = newznab[1].rstrip()
                if host_newznab[len(host_newznab) -1:len(host_newznab)] != '/':
                    host_newznab_fix = str(host_newznab) + "/"
                else:
                    host_newznab_fix = host_newznab

                #account for nzbmegasearch & nzbhydra
                if 'warp?x=' in link or 'indexerguid' in link:
                    logger.fdebug('NZBMegaSearch / NZBHydra url detected. Adjusting...')
                    nzbmega = True
                else:
                    apikey = newznab[3].rstrip()
                    down_url = host_newznab_fix + 'api'
                    verify = bool(newznab[2])
            else:
                down_url = 'https://api.nzb.su/api'
                apikey = mylar.NZBSU_APIKEY
                verify = bool(mylar.NZBSU_VERIFY)

            if nzbmega == True:
                down_url = link
                verify = False               
            else:
                payload = {'t': 'get',
                           'id': str(nzbid),
                           'apikey': str(apikey)}

            logger.fdebug('payload:' + str(payload))

        elif nzbprov == 'dognzb':
            #dognzb - need to add back in the dog apikey
            down_url = urljoin(link, str(mylar.DOGNZB_APIKEY))
            verify = bool(mylar.DOGNZB_VERIFY)

        else:
            #experimental - direct link.
            down_url = link
            headers = None
            verify = False

        if payload is None:
            logger.info('Download URL: ' + str(down_url) + ' [VerifySSL:' + str(verify) + ']')
        else:
            logger.info('Download URL: ' + down_url + '?' + urllib.urlencode(payload) + ' [VerifySSL:' + str(verify) + ']')


        if down_url.startswith('https'):
            try:
                from lib.requests.packages.urllib3 import disable_warnings
                disable_warnings()
            except:
                logger.warn('Unable to disable https warnings. Expect some spam if using https nzb providers.')

        try:
            r = requests.get(down_url, params=payload, verify=verify, headers=headers)

        except Exception, e:
            logger.warn('Error fetching data from %s: %s' % (tmpprov, e))
            return "sab-fail"

        try:
            nzo_info['filename'] = r.headers['x-dnzb-name']
            filen = r.headers['x-dnzb-name']
        except KeyError:
            filen = None
        try:
            nzo_info['propername'] = r.headers['x-dnzb-propername']
        except KeyError:
            pass
        try:
            nzo_info['failure'] = r.headers['x-dnzb-failure']
        except KeyError:
            pass
        try:
            nzo_info['details'] = r.headers['x-dnzb-details']
        except KeyError:
            pass

        if filen is None:
            try:
                filen = r.headers['content-disposition'][r.headers['content-disposition'].index("filename=") + 9:].strip(';').strip('"')
            except:
                pass

        if filen is None:
            if payload is None:
                logger.error('Unable to download nzb from link: ' + str(down_url) + ' [' + link + ']')
            else:
                errorlink = down_url + '?' + urllib.urlencode(payload)
                logger.error('Unable to download nzb from link: ' + str(errorlink) + ' [' + link + ']')
        else:
            #convert to a generic type of format to help with post-processing.
            filen = re.sub("\&", 'and', filen)
            filen = re.sub('[\,\:\?\']', '', filen)
            filen = re.sub('[\(\)]', ' ', filen)
            logger.fdebug('[FILENAME] filename (remove chars): ' + filen)
            filen = re.sub('.cbr', '', filen).strip()
            filen = re.sub('.cbz', '', filen).strip()
            filen = re.sub('\s+', ' ', filen)  #make sure we remove the extra spaces.
            logger.fdebug('[FILENAME] nzbname (\s): ' + filen)
            filen = re.sub(' ', '.', filen)
            logger.fdebug('[FILENAME] end nzbname: ' + filen)

            if re.sub('.nzb', '', filen.lower()).strip() != re.sub('.nzb', '', nzbname.lower()).strip():
                alt_nzbname = re.sub('.nzb', '', filen).strip()
                alt_nzbname = re.sub('[\s+]', ' ', alt_nzbname)
                alt_nzbname = re.sub('[\s\_]', '.', alt_nzbname)
                logger.info('filen: ' + alt_nzbname + ' -- nzbname: ' + nzbname + ' are not identical. Storing extra value as : ' + alt_nzbname)

            #make sure the cache directory exists - if not, create it (used for storing nzbs).
            if os.path.exists(mylar.CACHE_DIR):
                logger.fdebug("Cache Directory successfully found at : " + mylar.CACHE_DIR + ". Ensuring proper permissions.")
                #enforce the permissions here to ensure the lower portion writes successfully
                filechecker.setperms(mylar.CACHE_DIR, True)
            else:
                #let's make the dir.
                logger.fdebug("Could not locate Cache Directory, attempting to create at : " + mylar.CACHE_DIR)
                try:
                    filechecker.validateAndCreateDirectory(mylar.CACHE_DIR, True)
                    logger.info("Temporary NZB Download Directory successfully created at: " + mylar.CACHE_DIR)
                except OSError:
                    raise

            #save the nzb grabbed, so we can bypass all the 'send-url' crap.
            if not nzbname.endswith('.nzb'):
                nzbname = nzbname + '.nzb'
            nzbpath = os.path.join(mylar.CACHE_DIR, nzbname)

            with open(nzbpath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()

    if mylar.FAILED_DOWNLOAD_HANDLING:
        if nzbid is not None:
            try:
                # only nzb providers will have a filen, try it and pass exception
                if filen is None:
                    if IssueID is None:
                        logger.fdebug('One-off mode was initiated - Failed Download handling for : ' + ComicName + ' #' + str(IssueNumber))
                        comicinfo = {"ComicName":   ComicName,
                                     "IssueNumber": IssueNumber}
                        return FailedMark(ComicID=ComicID, IssueID=IssueID, id=nzbid, nzbname=nzbname, prov=nzbprov, oneoffinfo=comicinfo)
            except:
                pass
            call_the_fail = Failed.FailedProcessor(nzb_name=nzbname, id=nzbid, issueid=IssueID, comicid=ComicID, prov=tmpprov)
            check_the_fail = call_the_fail.failed_check()
            if check_the_fail == 'Failed':
                logger.fdebug('[FAILED_DOWNLOAD_CHECKER] [' + str(tmpprov) + '] Marked as a bad download : ' + str(nzbid))
                return "downloadchk-fail"
                #continue
            elif check_the_fail == 'Good':
                logger.fdebug('[FAILED_DOWNLOAD_CHECKER] This is not in the failed downloads list. Will continue with the download.')
    else:
        try:
            # only nzb providers will have a filen, try it and pass exception
            if filen is None:
                return "sab-fail"
        except:
            pass

    logger.fdebug('issues match!')
    logger.info(u"Found " + ComicName + " (" + str(comyear) + ") issue: " + IssueNumber + " using " + str(tmpprov))

    logger.fdebug("link given by: " + str(nzbprov))

    #blackhole
    sent_to = None
    if mylar.USE_BLACKHOLE and nzbprov != '32P' and nzbprov != 'KAT' and nzbprov != 'Torznab':
        logger.fdebug("using blackhole directory at : " + str(mylar.BLACKHOLE_DIR))
        if os.path.exists(mylar.BLACKHOLE_DIR):
            #copy the nzb from nzbpath to blackhole dir.
            try:
                shutil.move(nzbpath, os.path.join(mylar.BLACKHOLE_DIR, nzbname))
            except (OSError, IOError):
                logger.warn('Failed to move nzb into blackhole directory - check blackhole directory and/or permissions.')
                return "blackhole-fail"
            logger.fdebug("filename saved to your blackhole as : " + nzbname)
            logger.info(u"Successfully sent .nzb to your Blackhole directory : " + os.path.join(mylar.BLACKHOLE_DIR, nzbname))
            sent_to = "your Blackhole Directory"
    #end blackhole

    #torrents (32P & KAT)
    elif nzbprov == '32P' or nzbprov == 'KAT' or nzbprov == 'Torznab':
        logger.fdebug("sending .torrent to watchdir.")
        logger.fdebug("ComicName:" + ComicName)
        logger.fdebug("link:" + link)
        logger.fdebug("Torrent Provider:" + nzbprov)
        foundc = "yes"


        rcheck = rsscheck.torsend2client(ComicName, IssueNumber, comyear, link, nzbprov)
        if rcheck == "fail":
            if mylar.FAILED_DOWNLOAD_HANDLING:
                logger.error('Unable to send torrent to client. Assuming incomplete link - sending to Failed Handler and continuing search.')
                if IssueID is None:
                    logger.fdebug('One-off mode was initiated - Failed Download handling for : ' + ComicName + ' #' + str(IssueNumber))
                    comicinfo = {"ComicName":   ComicName,
                                 "IssueNumber": IssueNumber}
                else:
                    comicinfo_temp = {"ComicName":     comicinfo[0]['ComicName'],
                                      "modcomicname":  comicinfo[0]['modcomicname'],
                                      "IssueNumber":   comicinfo[0]['IssueNumber'],
                                      "comyear":       comicinfo[0]['comyear']}
                    comicinfo = comicinfo_temp
                return FailedMark(ComicID=ComicID, IssueID=IssueID, id=nzbid, nzbname=nzbname, prov=nzbprov, oneoffinfo=comicinfo)
            else:
                logger.error('Unable to send torrent - check logs and settings (this would be marked as a BAD torrent if Failed Handling was enabled)')
                return "torrent-fail"
        if mylar.TORRENT_LOCAL:
            sent_to = "your local Watch folder"
        else:
            sent_to = "your seedbox Watch folder"
    #end torrents

    else:
        #SABnzbd / NZBGet

        #logger.fdebug("link to retrieve via api:" + str(helpers.apiremove(linkapi,'$')))

        #nzb.get
        if mylar.USE_NZBGET:
            from xmlrpclib import ServerProxy
            if mylar.NZBGET_HOST[:4] == 'http':
                tmpapi = "http://"
                nzbget_host = mylar.NZBGET_HOST[7:]
            elif mylar.NZBGET_HOST[:5] == 'https':
                tmpapi = "https://"
                nzbget_host = mylar.NZBGET_HOST[8:]
            else:
                logger.error("You have an invalid nzbget hostname specified. Exiting")
                return "nzbget-fail"

            in_file = open(nzbpath, "r")
            nzbcontent = in_file.read()
            in_file.close()
            from base64 import standard_b64encode
            nzbcontent64 = standard_b64encode(nzbcontent)

            tmpapi = str(tmpapi) + str(mylar.NZBGET_USERNAME) + ":" + str(mylar.NZBGET_PASSWORD)
            tmpapi = str(tmpapi) + "@" + str(nzbget_host) + ":" + str(mylar.NZBGET_PORT) + "/xmlrpc"
            server = ServerProxy(tmpapi)
            send_to_nzbget = server.append(nzbpath, str(mylar.NZBGET_CATEGORY), int(nzbgetpriority), True, nzbcontent64)
            sent_to = "NZBGet"
            if send_to_nzbget is True:
                logger.info("Successfully sent nzb to NZBGet!")
            else:
                logger.info("Unable to send nzb to NZBGet - check your configs.")
                return "nzbget-fail"
        #end nzb.get

        elif mylar.USE_SABNZBD:
            # let's build the send-to-SAB string now:
            # changed to just work with direct links now...
            tmpapi = mylar.SAB_HOST + "/api?apikey=" + mylar.SAB_APIKEY

            logger.fdebug("send-to-SAB host &api initiation string : " + str(helpers.apiremove(tmpapi, '&')))

            SABtype = "&mode=addurl&name="
            #generate the api key to download here and then kill it immediately after.
            if mylar.DOWNLOAD_APIKEY is None:
                import hashlib, random
                mylar.DOWNLOAD_APIKEY = hashlib.sha224(str(random.getrandbits(256))).hexdigest()[0:32]

            #generate the mylar host address if applicable.
            if mylar.ENABLE_HTTPS:
                proto = 'https://'
            else:
                proto = 'http://'

            if mylar.HTTP_ROOT is None:
                hroot = '/'
            elif mylar.HTTP_ROOT.endswith('/'):
                hroot = mylar.HTTP_ROOT
            else:
                if mylar.HTTP_ROOT != '/':
                    hroot = mylar.HTTP_ROOT + '/'
                else:
                    hroot = mylar.HTTP_ROOT

            if mylar.LOCAL_IP is None:
                #if mylar's local, get the local IP using socket.
                try:
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(('8.8.8.8', 80))
                    mylar.LOCAL_IP = s.getsockname()[0]
                    s.close()
                except:
                    logger.warn('Unable to determine local IP. Defaulting to host address for Mylar provided as : ' + str(mylar.HTTP_HOST))

            if mylar.HOST_RETURN:
                #mylar has the return value already provided (easier and will work if it's right)
                if mylar.HOST_RETURN.endswith('/'):
                    mylar_host = mylar.HOST_RETURN
                else:
                    mylar_host = mylar.HOST_RETURN + '/'

            elif mylar.SAB_TO_MYLAR:
                #if sab & mylar are on different machines, check to see if they are local or external IP's provided for host.
                if mylar.HTTP_HOST == 'localhost' or mylar.HTTP_HOST == '0.0.0.0' or mylar.HTTP_HOST.startswith('10.') or mylar.HTTP_HOST.startswith('192.') or mylar.HTTP_HOST.startswith('172.'):
                    #if mylar's local, use the local IP already assigned to LOCAL_IP.
                    mylar_host = proto + str(mylar.LOCAL_IP) + ':' + str(mylar.HTTP_PORT) + hroot
                else:
                    if mylar.EXT_IP is None:
                        #if mylar isn't local, get the external IP using pystun.
                        import lib.pystun as stun
                        sip = mylar.HTTP_HOST
                        port = int(mylar.HTTP_PORT)
                        try:
                            nat_type, ext_ip, ext_port = stun.get_ip_info(sip,port)
                            mylar_host = proto + str(ext_ip) + ':' + str(mylar.HTTP_PORT) + hroot
                            mylar.EXT_IP = ext_ip
                        except:
                            logger.warn('Unable to retrieve External IP - try using the host_return option in the config.ini.')
                            mylar_host = proto + str(mylar.HTTP_HOST) + ':' + str(mylar.HTTP_PORT) + hroot
                    else:
                        mylar_host = proto + str(mylar.EXT_IP) + ':' + str(mylar.HTTP_PORT) + hroot

            else:
                #if all else fails, drop it back to the basic host:port and try that.
                if mylar.LOCAL_IP is None:
                    tmp_host = mylar.HTTP_HOST
                else:
                    tmp_host = mylar.LOCAL_IP
                mylar_host = proto + str(tmp_host) + ':' + str(mylar.HTTP_PORT) + hroot

                    
            fileURL = mylar_host + 'api?apikey=' + mylar.DOWNLOAD_APIKEY + '&cmd=downloadNZB&nzbname=' + nzbname

            tmpapi = tmpapi + SABtype
            logger.fdebug("...selecting API type: " + str(tmpapi))

            
            tmpapi = tmpapi + urllib.quote_plus(fileURL)

            logger.fdebug("...attaching nzb via internal Mylar API: " + str(helpers.apiremove(tmpapi, '$')))
            # determine SAB priority
            if mylar.SAB_PRIORITY:
                tmpapi = tmpapi + "&priority=" + sabpriority
                logger.fdebug("...setting priority: " + str(helpers.apiremove(tmpapi, '&')))
            # if category is blank, let's adjust
            if mylar.SAB_CATEGORY:
                tmpapi = tmpapi + "&cat=" + mylar.SAB_CATEGORY
                logger.fdebug("...attaching category: " + str(helpers.apiremove(tmpapi, '&')))
            if mylar.POST_PROCESSING: #or mylar.RENAME_FILES:
                if mylar.POST_PROCESSING_SCRIPT:
                    #this is relative to the SABnzbd script directory (ie. no path)
                    tmpapi = tmpapi + "&script=" + mylar.POST_PROCESSING_SCRIPT
                else:
                    tmpapi = tmpapi + "&script=ComicRN.py"
                logger.fdebug("...attaching rename script: " + str(helpers.apiremove(tmpapi, '&')))
            #final build of send-to-SAB
            logger.fdebug("Completed send-to-SAB link: " + str(helpers.apiremove(tmpapi, '&')))

            logger.fdebug('sab-to-send:' + str(tmpapi))

            try:
                from lib.requests.packages.urllib3 import disable_warnings
                disable_warnings()
            except:
                logger.warn('Unable to disable https warnings. Expect some spam if using https nzb providers.')

            try:
                requests.put(tmpapi, verify=False)
            except:
                logger.error('Unable to send nzb file to SABnzbd')
                mylar.DOWNLOAD_APIKEY = None
                return "sab-fail"

#         this works for non-http sends to sab (when both sab AND provider are non-https)
#            try:
#                urllib2.urlopen(tmpapi)
#            except urllib2.URLError:
#                logger.error(u"Unable to send nzb file to SABnzbd")
#                return "sab-fail"

            sent_to = "SABnzbd+"
            logger.info(u"Successfully sent nzb file to SABnzbd")

    #nzbid, nzbname, sent_to
    nzbname = re.sub('.nzb', '', nzbname).strip()

    return_val = []
    return_val.append({"nzbid":       nzbid,
                       "nzbname":     nzbname,
                       "sent_to":     sent_to,
                       "alt_nzbname": alt_nzbname})

    #if it's a directsend link (ie. via a retry).
    if directsend is None:
        return return_val
    else:
        #update the db on the snatch.
        if alt_nzbname is None or alt_nzbname == '':
            logger.fdebug("Found matching comic...preparing to send to Updater with IssueID: " + str(IssueID) + " and nzbname: " + str(nzbname))
            if '[RSS]' in tmpprov: tmpprov = re.sub('\[RSS\]', '', tmpprov).strip()
            updater.nzblog(IssueID, nzbname, ComicName, SARC=None, IssueArcID=None, id=nzbid, prov=tmpprov)
        else:
            logger.fdebug("Found matching comic...preparing to send to Updater with IssueID: " + str(IssueID) + " and nzbname: " + str(nzbname) + ' [' + alt_nzbname + ']')
            if '[RSS]' in tmpprov: tmpprov = re.sub('\[RSS\]', '', tmpprov).strip()
            updater.nzblog(IssueID, nzbname, ComicName, SARC=None, IssueArcID=None, id=nzbid, prov=tmpprov, alt_nzbname=alt_nzbname)
        #send out notifications for on snatch after the updater incase notification fails (it would bugger up the updater/pp scripts)
        notify_snatch(nzbname, sent_to, helpers.filesafe(modcomicname), comyear, IssueNumber, nzbprov)
        return

def notify_snatch(nzbname, sent_to, modcomicname, comyear, IssueNumber, nzbprov):

    snline = modcomicname + ' (' + comyear + ') - Issue #' + IssueNumber + ' snatched!'

    if mylar.PROWL_ENABLED and mylar.PROWL_ONSNATCH:
        logger.info(u"Sending Prowl notification")
        prowl = notifiers.PROWL()
        prowl.notify(nzbname, "Download started using " + sent_to)
    if mylar.NMA_ENABLED and mylar.NMA_ONSNATCH:
        logger.info(u"Sending NMA notification")
        nma = notifiers.NMA()
        nma.notify(snline=snline, snatched_nzb=nzbname, sent_to=sent_to, prov=nzbprov)
    if mylar.PUSHOVER_ENABLED and mylar.PUSHOVER_ONSNATCH:
        logger.info(u"Sending Pushover notification")
        thisline = 'Mylar has snatched: ' + nzbname + ' from ' + nzbprov + ' and has sent it to ' + sent_to
        pushover = notifiers.PUSHOVER()
        pushover.notify(thisline, snline)
    if mylar.BOXCAR_ENABLED and mylar.BOXCAR_ONSNATCH:
        logger.info(u"Sending Boxcar notification")
        boxcar = notifiers.BOXCAR()
        boxcar.notify(snatched_nzb=nzbname, sent_to=sent_to, snline=snline)
    if mylar.PUSHBULLET_ENABLED and mylar.PUSHBULLET_ONSNATCH:
        logger.info(u"Sending Pushbullet notification")
        pushbullet = notifiers.PUSHBULLET()
        pushbullet.notify(snline=snline, snatched=nzbname, sent_to=sent_to, prov=nzbprov, method='POST')

    return

def FailedMark(IssueID, ComicID, id, nzbname, prov, oneoffinfo=None):
        # Used to pass a failed attempt at sending a download to a client, to the failed handler, and then back again to continue searching.

        from mylar import Failed

        FailProcess = Failed.FailedProcessor(issueid=IssueID, comicid=ComicID, id=id, nzb_name=nzbname, prov=prov, oneoffinfo=oneoffinfo)
        Markit = FailProcess.markFailed()

        if prov == '32P' or prov == 'KAT': return "torrent-fail"
        else: return "downloadchk-fail"

def IssueTitleCheck(issuetitle, watchcomic_split, splitit, splitst, issue_firstword, hyphensplit, orignzb=None):
        vals = []
        initialchk = 'ok'
        isstitle_chk = False

        logger.fdebug("incorrect comic lengths...not a match")

        issuetitle = re.sub('[\-\:\,\?\.]', ' ', str(issuetitle))
        issuetitle_words = issuetitle.split(None)
        #issue title comparison here:
        logger.fdebug('there are ' + str(len(issuetitle_words)) + ' words in the issue title of : ' + str(issuetitle))
        # we minus 1 the splitst since the issue # is included in there.
        if (splitst - 1) > len(watchcomic_split):
            logger.fdebug('splitit:' + str(splitit))
            logger.fdebug('splitst:' + str(splitst))
            logger.fdebug('len-watchcomic:' + str(len(watchcomic_split)))
            possibleissue_num = splitit[len(watchcomic_split)] #[splitst]
            logger.fdebug('possible issue number of : ' + str(possibleissue_num))
            extra_words = splitst - len(watchcomic_split)
            logger.fdebug('there are ' + str(extra_words) + ' left over after we remove the series title.')
            wordcount = 1
            #remove the series title here so we just have the 'hopefully' issue title
            for word in splitit:
                #logger.info('word: ' + str(word))
                if wordcount > len(watchcomic_split):
                    #logger.info('wordcount: ' + str(wordcount))
                    #logger.info('watchcomic_split: ' + str(len(watchcomic_split)))
                    if wordcount - len(watchcomic_split) == 1:
                        search_issue_title = word
                        possibleissue_num = word
                    else:
                        search_issue_title += ' ' + word
                wordcount +=1

            decit = search_issue_title.split(None)
            if decit[0].isdigit() and decit[1].isdigit():
                logger.fdebug('possible decimal - referencing position from original title.')
                chkme = orignzb.find(decit[0])
                chkend = orignzb.find(decit[1], chkme + len(decit[0]))
                chkspot = orignzb[chkme:chkend +1]
                print chkme, chkend
                print chkspot
                # we add +1 to decit totals in order to account for the '.' that's missing and we assume is there.
                if len(chkspot) == (len(decit[0]) + len(decit[1]) + 1):
                    logger.fdebug('lengths match for possible decimal issue.')
                    if '.' in chkspot:
                        logger.fdebug('decimal located within : ' + str(chkspot))
                        possibleissue_num = chkspot
                        splitst = splitst -1  #remove the second numeric as it's a decimal and would add an extra char to

            logger.fdebug('search_issue_title is : ' + str(search_issue_title))
            logger.fdebug('possible issue number of : ' + str(possibleissue_num))

            if hyphensplit is not None:
                logger.fdebug('hypen split detected.')
                try:
                    issue_start = search_issue_title.find(issue_firstword)
                    logger.fdebug('located first word of : ' + str(issue_firstword) + ' at position : ' + str(issue_start))
                    search_issue_title = search_issue_title[issue_start:]
                    logger.fdebug('corrected search_issue_title is now : ' + str(search_issue_title))
                except TypeError:
                    logger.fdebug('invalid parsing detection. Ignoring this result.')
                    return vals.append({"splitit":  splitit,
                                        "splitst":  splitst,
                                        "isstitle_chk": isstitle_chk,
                                        "status":   "continue"})
            #now we have the nzb issue title (if it exists), let's break it down further.
            sit_split = search_issue_title.split(None)
            watch_split_count = len(issuetitle_words)
            isstitle_removal = []
            isstitle_match = 0   #counter to tally % match
            misword = 0 # counter to tally words that probably don't need to be an 'exact' match.
            for wsplit in issuetitle_words:
                of_chk = False
                if wsplit.lower() == 'part' or wsplit.lower() == 'of':
                    if wsplit.lower() == 'of':
                        of_chk = True
                    logger.fdebug('not worrying about this word : ' + str(wsplit))
                    misword +=1
                    continue
                if wsplit.isdigit() and of_chk == True:
                    logger.fdebug('of ' + str(wsplit) + ' detected. Ignoring for matching.')
                    of_chk = False
                    continue

                for sit in sit_split:
                    logger.fdebug('looking at : ' + str(sit.lower()) + ' -TO- ' + str(wsplit.lower()))
                    if sit.lower() == 'part':
                        logger.fdebug('not worrying about this word : ' + str(sit))
                        misword +=1
                        isstitle_removal.append(sit)
                        break
                    elif sit.lower() == wsplit.lower():
                        logger.fdebug('word match: ' + str(sit))
                        isstitle_match +=1
                        isstitle_removal.append(sit)
                        break
                    else:
                        try:
                            if int(sit) == int(wsplit):
                                logger.fdebug('found matching numeric: ' + str(wsplit))
                                isstitle_match +=1
                                isstitle_removal.append(sit)
                                break
                        except:
                            pass

            logger.fdebug('isstitle_match count : ' + str(isstitle_match))
            if isstitle_match > 0:
                iss_calc = ((isstitle_match + misword) / watch_split_count) * 100
                logger.fdebug('iss_calc: ' + str(iss_calc) + ' % with ' + str(misword) + ' unaccounted for words')
            else:
                iss_calc = 0
                logger.fdebug('0 words matched on issue title.')
            if iss_calc >= 80:    #mylar.ISSUE_TITLEMATCH - user-defined percentage to match against for issue name comparisons.
                logger.fdebug('>80% match on issue name. If this were implemented, this would be considered a match.')
                logger.fdebug('we should remove ' + str(len(isstitle_removal)) + ' words : ' + str(isstitle_removal))
                logger.fdebug('Removing issue title from nzb filename to improve matching algorithims.')
                splitst = splitst - len(isstitle_removal)
                isstitle_chk = True
                vals.append({"splitit":  splitit,
                             "splitst":  splitst,
                             "isstitle_chk": isstitle_chk,
                             "possibleissue_num": possibleissue_num,
                             "isstitle_removal": isstitle_removal,
                             "status":   'ok'})
                return vals
        return

def generate_id(nzbprov, link):
    logger.fdebug('[' + nzbprov + '] link: ' + str(link))
    if nzbprov == 'experimental':
        #id is located after the /download/ portion
        url_parts = urlparse.urlparse(link)
        path_parts = url_parts[2].rpartition('/')
        nzbtempid = path_parts[0].rpartition('/')
        nzblen = len(nzbtempid)
        nzbid = nzbtempid[nzblen -1]
    elif nzbprov == '32P':
        #32P just has the torrent id stored.
        nzbid = link
    elif nzbprov == 'KAT':
        if 'http' not in link:
            nzbid = link
        else:
            #for users that already have the cache in place.
            url_parts = urlparse.urlparse(link)
            path_parts = url_parts[2].rpartition('/')
            nzbtempid = path_parts[2]
            nzbid = re.sub('.torrent', '', nzbtempid).rstrip()
    elif nzbprov == 'nzb.su':
        nzbid = os.path.splitext(link)[0].rsplit('/', 1)[1]
    elif nzbprov == 'dognzb':
        url_parts = urlparse.urlparse(link)
        path_parts = url_parts[2].rpartition('/')
        nzbid = path_parts[0].rsplit('/', 1)[1]
    elif nzbprov == 'newznab':      
        #if in format of http://newznab/getnzb/<id>.nzb&i=1&r=apikey
        tmpid = urlparse.urlparse(link)[4]  #param 4 is the query string from the url.
        if 'warp' in urlparse.urlparse(link)[2] and 'x=' in tmpid:
            nzbid = os.path.splitext(link)[0].rsplit('x=',1)[1]
        elif tmpid == '' or tmpid is None:
            nzbid = os.path.splitext(link)[0].rsplit('/', 1)[1]
        else:
            # for the geek in all of us...
            st = tmpid.find('&id')
            end = tmpid.find('&', st +1)
            if end == -1: 
                end = len(tmpid)
            nzbid = re.sub('&id=', '', tmpid[st:end]).strip()
    elif nzbprov == 'Torznab':
        if mylar.TORZNAB_HOST.endswith('/'):
            tmphost = mylar.TORZNAB_HOST + 'download/'
        else:
            tmphost = mylar.TORZNAB_HOST + '/download/'
        tmpline = re.sub(tmphost, '', tmphost).strip()
        tmpidend = tmpline.find('/')
        nzbid = tmpline[:tmpidend]

    return nzbid
