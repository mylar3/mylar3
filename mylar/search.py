
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
from mylar import logger, db, updater, helpers, parseit, findcomicfeed, prov_nzbx, notifiers, rsscheck

nzbsu_APIkey = mylar.NZBSU_APIKEY
dognzb_APIkey = mylar.DOGNZB_APIKEY

LOG = mylar.LOG_DIR

import lib.feedparser as feedparser
import urllib
import os, errno
import string
import sqlite3 as lite
import sys
import getopt
import re
import time
from xml.dom.minidom import parseString
import urllib2
from datetime import datetime

def search_init(ComicName, IssueNumber, ComicYear, SeriesYear, IssueDate, IssueID, AlternateSearch=None, UseFuzzy=None, ComicVersion=None, SARC=None, IssueArcID=None, mode=None, rsscheck=None, ComicID=None):
    if ComicYear == None: ComicYear = '2013'
    else: ComicYear = str(ComicYear)[:4]

    if mode == 'want_ann':
        logger.info("Annual issue search detected. Appending to issue #")
        #anything for mode other than None indicates an annual.
        ComicName = ComicName + " annual"
        if AlternateSearch is not None and AlternateSearch != "None":
            AlternateSearch = AlternateSearch + " annual"

    if IssueID is None:
        #one-off the download.
        print ("ComicName: " + ComicName)
        print ("Issue: " + str(IssueNumber))        
        print ("Year: " + str(ComicYear))
        print ("IssueDate:" + str(IssueDate))
    if SARC:
        print ("Story-ARC issue!")
        print ("Story-ARC: " + str(SARC))
        print ("IssueArcID: " + str(IssueArcID))

    torprovider = []
    torp = 0
    logger.fdebug("Checking for torrent enabled.")
    if mylar.ENABLE_TORRENTS and mylar.ENABLE_TORRENT_SEARCH:
        if mylar.ENABLE_CBT:
            torprovider.append('cbt')        
            torp+=1
            #print torprovider[0]
        elif mylar.ENABLE_KAT:
            torprovider.append('kat')
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
    if mylar.NZBX == 1:
        nzbprovider.append('nzbx')
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
                if newznab_host[0] == newznab_host[1]:
                    nzbprovider.append('newznab')
                else:
                    nzbprovider.append('newznab:' + str(newznab_host[0]))
#                except:
#                    nzbprovider.append('newznab')
#                    logger.error("newznab name not given for " + str(newznab_host[0]) + ". Defaulting name to newznab.")

                newznabs+=1
                logger.fdebug("newznab name:" + str(newznab_host[0]) + " @ " + str(newznab_host[1]))


    # --------
    logger.fdebug("there are : " + str(torp) + " torrent providers you have selected.")
    torpr = torp - 1
    if torpr < 0:
        torpr = -1
    providercount = int(nzbp + newznabs)
    logger.fdebug("there are : " + str(providercount) + " search providers you have selected.")
    logger.fdebug("Usenet Retention : " + str(mylar.USENET_RETENTION) + " days")
    nzbpr = providercount - 1
    if nzbpr < 0: 
        nzbpr == 0
    findit = 'no'

    #fix for issue dates between Nov-Dec/Jan
    IssDt = str(IssueDate)[5:7]
    if IssDt == "12" or IssDt == "11" or IssDt == "01":
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

    while ( i <= searchcnt ):
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

        torprtmp = torpr

        while (torprtmp >=0 ):
            if torprovider[torprtmp] == 'cbt':
                # CBT
                torprov = 'CBT'
            elif torprovider[torprtmp] == 'kat':
                torprov = 'KAT'

            if searchmode == 'rss':
                findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, torprov, torpr, IssDateFix, IssueID, UseFuzzy, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID)
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
                            AS_Alternate = re.sub('##','',calt)
                            logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate) + " " + str(ComicYear))
                            findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, torprov, torp, IssDateFix, IssueID, UseFuzzy, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID)
                            if findit == 'yes':
                                break

            else:
                findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, torprov, torpr, IssDateFix, IssueID, UseFuzzy, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, ComicID=ComicID)
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
                            AS_Alternate = re.sub('##','',calt)
                            logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate) + " " + str(ComicYear))
                            findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, torprov, torp, IssDateFix, IssueID, UseFuzzy, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, ComicID=ComicID)
                            if findit == 'yes':
                                break

            torprtmp-=1

        i+=1
    
    if findit == 'yes': return findit, torprov        

    searchcnt = 0
    nzbprov = None

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

    nzbsrchproviders = nzbpr

    while ( i <= searchcnt ):
        #searchmodes:
        # rss - will run through the built-cached db of entries
        # api - will run through the providers via api (or non-api in the case of Experimental)
        # the trick is if the search is done during an rss compare, it needs to exit when done.
        # otherwise, the order of operations is rss feed check first, followed by api on non-results.

        if i == 1: searchmode = 'rss'  #order of ops - this will be used first.
        elif i == 2: searchmode = 'api'

        nzbpr = nzbsrchproviders
        logger.fdebug("Initiating Search via : " + str(searchmode))

        while (nzbpr >= 0 ):
            if 'newznab' in nzbprovider[nzbpr]:
            #this is for newznab
                nzbprov = 'newznab'
                for newznab_host in newznab_hosts:
                    #if it's rss - search both seriesname/alternates via rss then return.
                    if searchmode == 'rss':
                        if mylar.ENABLE_RSS:
                            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID)
                            if findit == 'yes': 
                                logger.fdebug("Found via RSS.")
                                break
                            #findit = altdefine(AlternateSearch, searchmode='rss')
                            if AlternateSearch is not None and AlternateSearch != "None":
                                chkthealt = AlternateSearch.split('##')
                                if chkthealt == 0:
                                    AS_Alternate = AlternateSearch
                                loopit = len(chkthealt)
                                for calt in chkthealt:
                                    AS_Alternate = re.sub('##','',calt)
                                    logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate) + " " + str(ComicYear))
                                    findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID)
                                    if findit == 'yes':
                                        break
                                if findit == 'yes':
                                    logger.fdebug("Found via RSS Alternate Naming.")
                                    break
                        else:
                            logger.fdebug("RSS search not enabled - using API only (Enable in the Configuration)")
                            break
                    else:
                        #normal api-search here.
                        findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, ComicID=ComicID)
                        if findit == 'yes':
                            logger.fdebug("Found via API.")
                            break
                        if AlternateSearch is not None and AlternateSearch != "None":
                            chkthealt = AlternateSearch.split('##')
                            if chkthealt == 0:
                                AS_Alternate = AlternateSearch
                            loopit = len(chkthealt)
                            for calt in chkthealt:
                                AS_Alternate = re.sub('##','',calt)
                                logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate) + " " + str(ComicYear))
                                findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, ComicID=ComicID)
                                if findit == 'yes':
                                    break
                            if findit == 'yes':
                                logger.fdebug("Found via API Alternate Naming.")
                                break
                    nzbpr-=1
                if nzbpr >= 0 and findit != 'yes':
                    logger.info(u"More than one search provider given - trying next one.")
                else:
                    break
            else:
                newznab_host = None
                nzbprov = nzbprovider[nzbpr]
                if searchmode == 'rss':
                    if mylar.ENABLE_RSS:
                        findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS='yes', ComicID=ComicID)
                        if findit == 'yes':
                            logger.fdebug("Found via RSS on " + nzbprov)
                            break
                        if AlternateSearch is not None and AlternateSearch != "None":
                            chkthealt = AlternateSearch.split('##')
                            if chkthealt == 0:
                                AS_Alternate = AlternateSearch
                            loopit = len(chkthealt)
                            for calt in chkthealt:
                                AS_Alternate = re.sub('##','',calt)
                                logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate) + " " + str(ComicYear))
                                findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID)
                                if findit == 'yes':
                                    logger.fdebug("Found via RSS Alternate Naming on " + nzbprov)
                                    break
                    else:
                        logger.fdebug("RSS search not enabled - using API only (Enable in the Configuration)")
                        break
                else:
                    #normal api-search here.
                    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, ComicID=ComicID)
                    if findit == 'yes':
                        logger.fdebug("Found via API on " + nzbprov)
                        break
                    if AlternateSearch is not None and AlternateSearch != "None":
                        chkthealt = AlternateSearch.split('##')
                        if chkthealt == 0:
                            AS_Alternate = AlternateSearch
                        for calt in chkthealt:
                            AS_Alternate = re.sub('##','',calt)
                            logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate))
                            findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, ComicID=ComicID)
                            if findit == 'yes':
                                break
                        if findit == 'yes':
                            logger.fdebug("Found via API Alternate Naming on " + nzbprov)
                            break
                nzbpr-=1
                if nzbpr >= 0 and findit != 'yes':
                    logger.info(u"More than one search provider given - trying next one.")
                else:
                    break
        if findit == 'yes': return findit, nzbprov
        else:
            logger.fdebug("Finished searching via : " + str(searchmode))
            i+=1

    return findit, nzbprov

def NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, UseFuzzy, newznab_host=None, ComicVersion=None, SARC=None, IssueArcID=None, RSS=None, ComicID=None):

    if nzbprov == 'nzb.su':
        apikey = mylar.NZBSU_APIKEY
    elif nzbprov == 'dognzb':
        apikey = mylar.DOGNZB_APIKEY
    elif nzbprov == 'nzbx':
        apikey = 'none'
    elif nzbprov == 'experimental':
        apikey = 'none'
    elif nzbprov == 'newznab':
        #updated to include Newznab Name now
        name_newznab = newznab_host[0].rstrip()
        host_newznab = newznab_host[1].rstrip()
        apikey = newznab_host[2].rstrip()
        if '#' in newznab_host[3].rstrip():
            catstart = newznab_host[3].find('#')
            category_newznab = newznab_host[3][catstart+1:]
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
    logger.info(u"Shhh be very quiet...I'm looking for " + ComicName + " issue: " + str(IssueNumber) + " (" + str(ComicYear) + ") using " + str(tmpprov))


    if mylar.PREFERRED_QUALITY == 0: filetype = ""
    elif mylar.PREFERRED_QUALITY == 1: filetype = ".cbr"
    elif mylar.PREFERRED_QUALITY == 2: filetype = ".cbz"

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
    c_number = None
    c_num_a4 = None
    while i < len(findcomiciss):
        #take first occurance of alpha in string and carry it through
        if findcomiciss[i].isalpha():
            c_alpha = findcomiciss[i:].rstrip()
            c_number = findcomiciss[:i].rstrip()
            break
        elif '.' in findcomiciss[i]:
            c_number = findcomiciss[i:].rstrip()
            c_num_a4 = findcomiciss[:i+1].rstrip()
            break
        i+=1
    logger.fdebug("calpha/cnumber: " + str(c_alpha) + " / " + str(c_number))

    if c_number is None:  
        c_number = findcomiciss # if it's None, means no special alphas or decimals
         
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

    while (findloop < findcount ):
        comsrc = comsearch
        while (cmloopit >= 1 ):
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
                comsearch = comsrc + "%2000" + str(isssearch) + "%20" + str(filetype)
                issdig = '00'
            elif cmloopit == 2:
                comsearch = comsrc + "%200" + str(isssearch) + "%20" + str(filetype)
                issdig = '0'
            elif cmloopit == 1:
                comsearch = comsrc + "%20" + str(isssearch) + "%20" + str(filetype)
                issdig = ''

            mod_isssearch = str(issdig) + str(isssearch)


            #--- this is basically for RSS Feeds ---
            logger.fdebug('RSS Check: ' + str(RSS))
            logger.fdebug('nzbprov: ' + str(nzbprov))
            logger.fdebug('comicid: ' + str(ComicID))
            if RSS == "yes" or nzbprov == 'CBT':
                if nzbprov == 'CBT' or nzbprov == 'KAT':
                    cmname = re.sub("%20", " ", str(comsrc))
                    logger.fdebug("Sending request to [" + str(nzbprov) + "] RSS for " + str(findcomic) + " : " + str(mod_isssearch))
                    bb = rsscheck.torrentdbsearch(findcomic,mod_isssearch,ComicID,nzbprov)
                    rss = "yes"
                    if bb is not None: logger.fdebug("bb results: " + str(bb))
                else:
                    cmname = re.sub("%20", " ", str(comsrc))
                    logger.fdebug("Sending request to RSS for " + str(findcomic) + " : " + str(mod_isssearch))
                    bb = rsscheck.nzbdbsearch(findcomic,mod_isssearch,ComicID,nzbprov)
                    rss = "yes"
                    if bb is not None: logger.fdebug("bb results: " +  str(bb))
            #this is the API calls
            else:
                #CBT is redudant now since only RSS works 
                # - just getting it ready for when it's not redudant :)
                if nzbprov == 'CBT':
                #    cmname = re.sub("%20", " ", str(comsrc))
                #    logger.fdebug("Sending request to [CBT] RSS for " + str(cmname) + " : " + str(mod_isssearch))
                #    bb = rsscheck.torrentdbsearch(cmname,mod_isssearch,ComicID)
                #    rss = "yes"
                #    if bb is not None: logger.fdebug("results: " + str(bb))
                    bb = "no results"
                elif nzbprov == 'KAT':
                    cmname = re.sub("%20", " ", str(comsrc))
                    logger.fdebug("Sending request to [KAT] for " + str(cmname) + " : " + str(mod_isssearch))
                    bb = rsscheck.torrents(pickfeed='2',seriesname=cmname,issue=mod_isssearch)
                    rss = "no"
                    #if bb is not None: logger.fdebug("results: " + str(bb))
                elif nzbprov != 'experimental':
                    if nzbprov == 'dognzb':
                        findurl = "http://dognzb.cr/api?t=search&q=" + str(comsearch) + "&o=xml&cat=7030"
                    elif nzbprov == 'nzb.su':
                        findurl = "https://nzb.su/api?t=search&q=" + str(comsearch) + "&o=xml&cat=7030"
                    elif nzbprov == 'newznab':
                        #let's make sure the host has a '/' at the end, if not add it.
                        if host_newznab[len(host_newznab)-1:len(host_newznab)] != '/':
                            host_newznab_fix = str(host_newznab) + "/"
                        else: host_newznab_fix = host_newznab
                        findurl = str(host_newznab_fix) + "api?t=search&q=" + str(comsearch) + "&o=xml&cat=" + str(category_newznab)
                    elif nzbprov == 'nzbx':
                        bb = prov_nzbx.searchit(comsearch)
                    if nzbprov != 'nzbx':
                        # helper function to replace apikey here so we avoid logging it ;)
                        findurl = findurl + "&apikey=" + str(apikey)
                        logsearch = helpers.apiremove(str(findurl),'nzb')
                        logger.fdebug("search-url: " + str(logsearch))

                        ### IF USENET_RETENTION is set, honour it
                        ### For newznab sites, that means appending "&maxage=<whatever>" on the URL
                        if mylar.USENET_RETENTION != None:
                            findurl = findurl + "&maxage=" + str(mylar.USENET_RETENTION)

                        # Add a user-agent
                        #print ("user-agent:" + str(mylar.USER_AGENT))
                        request = urllib2.Request(findurl)
                        request.add_header('User-Agent', str(mylar.USER_AGENT))
                        opener = urllib2.build_opener()

                        #set a delay between searches here. Default is for 30 seconds...
                        if mylar.SEARCH_DELAY == 'None' or mylar.SEARCH_DELAY is None:
                            pause_the_search = 1 * 60   # (it's in seconds)
                        elif str(mylar.SEARCH_DELAY).isdigit():
                            pause_the_search = mylar.SEARCH_DELAY * 60
                        else:
                            logger.info("Check Search Delay - invalid numerical given. Force-setting to 1 minute.")
                            pause_the_search = 1 * 60

                        #bypass for local newznabs
                        if nzbprov == 'newznab' and (host_newznab_fix[:3] == '10.' or host_newznab_fix[:4] == '172.' or host_newznab_fix[:4] == '192.' or 'localhost' in str(host_newznab_fix)):
                                pass
                        else:
                            logger.info("pausing for " + str(pause_the_search) + " seconds before continuing to avoid hammering")
                            time.sleep(pause_the_search)

                        try:
                            data = opener.open(request).read()
                        except Exception, e:
                            logger.warn('Error fetching data from %s: %s' % (nzbprov, e))
                            data = False

                        if data:
                            bb = feedparser.parse(data)
                        else:
                            bb = "no results"

                elif nzbprov == 'experimental':
                    #bb = parseit.MysterBinScrape(comsearch[findloop], comyear)
                    bb = findcomicfeed.Startit(u_ComicName, isssearch, comyear, ComicVersion)
                    # since the regexs in findcomicfeed do the 3 loops, lets force the exit after
                    cmloopit == 1

            done = False
            foundc = "no"
            log2file = ""
            if bb == "no results":               
                pass
                foundc = "no"
            else:
                for entry in bb['entries']:
                    logger.fdebug("checking search result: " + entry['title'])
                    if nzbprov != "experimental" and nzbprov != "CBT":
                        if RSS == "yes":
                            comsize_b = entry['length']
                        else:
                            #Experimental already has size constraints done.
                            if nzbprov == 'CBT':
                                comsize_b = 0   #CBT rss doesn't have sizes
                            elif nzbprov == 'KAT':
                                comsize_b = entry['length']
                            else:
                                tmpsz = entry.enclosures[0]
                                comsize_b = tmpsz['length']
                        if comsize_b is None: comsize_b = 0
                        comsize_m = helpers.human_size(comsize_b)
                        logger.fdebug("size given as: " + str(comsize_m))
#----size constraints.
                        #if it's not within size constaints - dump it now and save some time.
                        logger.fdebug("size : " + str(comsize_m))
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

# -- end size constaints.

                    thisentry = entry['title']
                    logger.fdebug("Entry: " + thisentry)
                    cleantitle = re.sub('[_/.]', ' ', entry['title'])
                    cleantitle = helpers.cleanName(cleantitle)
                    # this is new - if title contains a '&' in the title it will assume the filename has ended at that point
                    # which causes false positives (ie. wolverine & the x-men becomes the x-men, which matches on x-men.
                    # 'the' is removed for comparisons later on
                    if '&' in cleantitle: cleantitle = re.sub('[/&]','and', cleantitle) 

                    nzbname = cleantitle

                    # if it's coming from CBT, remove the ' -' at the end as it screws it up.
                    if nzbprov == 'CBT':
                        if cleantitle.endswith(' - '):
                            cleantitle = cleantitle[:-3]
                            logger.fdebug("cleaned up title to : " + str(cleantitle))

                    #adjust for covers only by removing them entirely...
                    logger.fdebug("Cleantitle: " + str(cleantitle))
                    vers4year = "no"
                    vers4vol = "no"

                    if 'cover only' in cleantitle.lower():
                        logger.fdebug("Ignoring title as Cover Only detected.")
                        cleantitle = "abcdefghijk 0 (1901).cbz"
                        continue

                    if ComicVersion:
                       ComVersChk = re.sub("[^0-9]", "", ComicVersion)
                       if ComVersChk == '':
                            ComVersChk = 0
                    else:
                       ComVersChk = 0
                     
                    if len(re.findall('[^()]+', cleantitle)) == 1 or 'cover only' in cleantitle.lower(): 
                        #some sites don't have (2013) or whatever..just v2 / v2013. Let's adjust:
                        #this handles when there is NO YEAR present in the title, otherwise versioning is way below.
                        ctchk = cleantitle.split()
                        for ct in ctchk:
                            if ct.lower().startswith('v') and ct[1:].isdigit():
                                logger.fdebug("possible versioning..checking")
                                #we hit a versioning # - account for it
                                if ct[1:].isdigit():
                                    if len(ct[1:]) == 4:  #v2013
                                        logger.fdebug("Version detected as " + str(ct))
                                        vers4year = "yes" #re.sub("[^0-9]", " ", str(ct)) #remove the v
                                        #cleantitle = re.sub(ct, "(" + str(vers4year) + ")", cleantitle)
                                        #logger.fdebug("volumized cleantitle : " + cleantitle)
                                        break
                                    else:
                                        if len(ct) < 4:
                                            logger.fdebug("Version detected as " + str(ct))
                                            vers4vol = str(ct)
                                            break
                                logger.fdebug("false version detection..ignoring.")

                        if vers4year == "no" and vers4vol == "no":
                            # if the series is a v1, let's remove the requirements for year and volume label
                            if ComVersChk != 0:
                                # if there are no () in the string, try to add them if it looks like a year (19xx or 20xx)
                                if len(re.findall('[^()]+', cleantitle)):
                                    logger.fdebug("detected invalid nzb filename - attempting to detect year to continue")
                                    cleantitle = re.sub('(.*)\s+(19\d{2}|20\d{2})(.*)', '\\1 (\\2) \\3', cleantitle)
                                    continue
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

                    while (cnt < lenm):
                        if m[cnt] is None: break
                        if m[cnt] == ' ': 
                            pass
                        else: 
                            logger.fdebug(str(cnt) + ". Bracket Word: " + str(m[cnt]))
                        if cnt == 0:
                            comic_andiss = m[cnt]
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
                                        if IssDateFix == "01": ComicYearFix = int(ComicYear) - 1
                                        else: ComicYearFix = int(ComicYear) + 1
                                        if str(ComicYearFix) in result_comyear:
                                            logger.fdebug("further analysis reveals this was published inbetween Nov-Jan, incrementing year to " + str(ComicYearFix) + " has resulted in a match!")
                                            yearmatch = "true"
                                        else:
                                            logger.fdebug(str(comyear) + " - not the right year.")

                        elif UseFuzzy == "1": yearmatch = "true"

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
                    #changed this from '' to ' '
                    comic_iss_b4 = re.sub('[\-\:\,\?]', ' ', str(comic_andiss))
                    comic_iss = comic_iss_b4.replace('.',' ')
                    #if issue_except: comic_iss = re.sub(issue_except.lower(), '', comic_iss)
                    logger.fdebug("adjusted nzb comic and issue: " + str(comic_iss))
                    splitit = comic_iss.split(None)
                    #something happened to dognzb searches or results...added a '.' in place of spaces
                    #screwed up most search results with dognzb. Let's try to adjust.
                    #watchcomic_split = findcomic[findloop].split(None)
                    
                    if splitit[(len(splitit)-1)].isdigit():
                        #compares - if the last digit and second last digit are #'s seperated by spaces assume decimal
                        comic_iss = splitit[(len(splitit)-1)]
                        splitst = len(splitit) - 1
                        if splitit[(len(splitit)-2)].isdigit():
                            # for series that have a digit at the end, it screws up the logistics.
                            i = 1
                            chg_comic = splitit[0]
                            while (i < (len(splitit)-1)):
                                chg_comic = chg_comic + " " + splitit[i]
                                i+=1
                            logger.fdebug("chg_comic:" + str(chg_comic))
                            findcomic_chksplit = re.sub('[\-\:\,\.\?]', ' ', findcomic)
                            chg_comic = re.sub('[\s]', '', chg_comic)
                            findcomic_chksplit = re.sub('[\s]', '', findcomic_chksplit)
                            #print chg_comic.upper()
                            #print findcomic_chksplit.upper()
                            if chg_comic.upper() == findcomic_chksplit.upper():
                                logger.fdebug("series contains numerics...adjusting..")
                            else:
                                changeup = "." + splitit[(len(splitit)-1)]
                                logger.fdebug("changeup to decimal: " + str(changeup))
                                comic_iss = splitit[(len(splitit)-2)] + "." + comic_iss
                                splitst = len(splitit) - 2
                    else:
                        #if the issue is alphanumeric (ie. 15AU, 12A) it'll error.
                        tmpiss = splitit[(len(splitit)-1)]     
                        i = 0
                        alphas = None
                        a_issno = None
                        while (i < len(tmpiss)):
                            if tmpiss[i].isalpha():
                            #take first occurance of alpha in string and carry it through
                                alphas = tmpiss[i:].rstrip()
                                a_issno = tmpiss[:i].rstrip()
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
                                comic_iss = splitit[(len(splitit)-2)] + splitit[(len(splitit)-1)]
                                splitst = len(splitit) - 2
                            else:
                                comic_iss = tmpiss
                                splitst = len(splitit) - 1
                    logger.fdebug("adjusting from: " + str(comic_iss_b4) + " to: " + str(comic_iss))
                    #bmm = re.findall('v\d', comic_iss)
                    #if len(bmm) > 0: splitst = len(splitit) - 2
                    #else: splitst = len(splitit) - 1

                    # make sure that things like - in watchcomic are accounted for when comparing to nzb.
                    findcomic = re.sub('[\/]', ' ', findcomic)
                    watchcomic_split = helpers.cleanName(str(findcomic))
                    if '&' in watchcomic_split: watchcomic_split = re.sub('[/&]','and', watchcomic_split)
                    watchcomic_nonsplit = re.sub('[\-\:\,\.\?]', ' ', watchcomic_split)
                    watchcomic_split = watchcomic_nonsplit.split(None)
                      
                    logger.fdebug(str(splitit) + " nzb series word count: " + str(splitst))
                    logger.fdebug(str(watchcomic_split) + " watchlist word count: " + str(len(watchcomic_split)))
                    #account for possible version inclusion here and annual inclusions.
                    cvers = "false"
                    annualize = "false"
                    if 'annual' in ComicName.lower():
                        logger.fdebug("IssueID of : " + str(IssueID) + " - This is an annual...let's adjust.")
                        annualize = "true"
                        #splitst = splitst - 1

                    for tstsplit in splitit:
                        if tstsplit.lower().startswith('v') and tstsplit[1:].isdigit():
                            logger.fdebug("this has a version #...let's adjust")
                            if len(tstsplit[1:]) == 4:  #v2013
                                logger.fdebug("Version detected as " + str(tstsplit))
                                vers4year = "yes" #re.sub("[^0-9]", " ", str(ct)) #remove the v
                            elif len(tstsplit[1:]) == 1:  #v2
                                logger.fdebug("Version detected as " + str(tstsplit))
                                vers4vol = str(tstsplit)
                            elif tstsplit[1:].isdigit() and len(tstsplit) < 4:
                                logger.fdebug('Version detected as ' +str(tstsplit))
                                vers4vol = str(tstsplit)
                            else:
                                logger.fdebug("error - unknown length for : " + str(tstsplit))
                            logger.fdebug("volume detection commencing - adjusting length.")
                            cvers = "true"
                            splitst = splitst - 1
                            break

                    #do an initial check
                    initialchk = 'ok'
                    if (splitst) != len(watchcomic_split):
                        logger.fdebug("incorrect comic lengths...not a match")
                        #because the word 'the' can appear anywhere and really mess up matches...
#                        if str(splitit[0]).lower() == "the" or str(watchcomic_split[0]).lower() == "the":
#                            if str(splitit[0]).lower() == "the":
                        for tstsplit in splitit:
                            if tstsplit.lower() == 'the':
                                logger.fdebug("THE word detected in found comic...attempting to adjust pattern matching")
                                #print comic_iss_b4
                                #print comic_iss_b4[4:]
                                #splitit = comic_iss_b4[4:].split(None)
                                cissb4this = re.sub("\\bthe\\b", "", comic_iss_b4)
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
                        scount = 0
                        logger.fdebug("search-length: " + str(splitst))
                        logger.fdebug("Watchlist-length: " + str(len(watchcomic_split)))
                        if cvers == "true": splitst = splitst + 1
                        while ( n <= (splitst)-1 ):
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
                            elif str(splitit[n].lower()).startswith('v'):
                                logger.fdebug("possible versioning..checking")
                                #we hit a versioning # - account for it
                                if splitit[n][1:].isdigit():
                                    logger.fdebug("watch comicversion is " + str(ComicVersion))
                                    fndcomicversion = str(splitit[n])
                                    logger.fdebug("version found: " + str(fndcomicversion))
                                    logger.fdebug("vers4year: " + str(vers4year))
                                    logger.fdebug("vers4vol: " + str(vers4vol))
                                    if vers4year is not "no" or vers4vol is not "no":

                                        #if the volume is None, assume it's a V1 to increase % hits
                                        if ComVersChk == 0:
                                            D_ComicVersion = 1
                                        else:
                                            D_ComicVersion = ComVersChk

                                        F_ComicVersion = re.sub("[^0-9]", "", fndcomicversion)
                                        S_ComicVersion = str(SeriesYear)
                                        logger.fdebug("FCVersion: " + str(F_ComicVersion))
                                        logger.fdebug("DCVersion: " + str(D_ComicVersion))
                                        logger.fdebug("SCVersion: " + str(S_ComicVersion))

                                        #here's the catch, sometimes annuals get posted as the Pub Year
                                        # instead of the Series they belong to (V2012 vs V2013)
                                        if annualize == "true" and int(ComicYear) == int(F_ComicVersion):
                                            logger.fdebug("We matched on versions for annuals " + str(fndcomicversion))
                                            scount+=1

                                        elif int(F_ComicVersion) == int(D_ComicVersion) or int(F_ComicVersion) == int(S_ComicVersion):
                                            logger.fdebug("We matched on versions..." + str(fndcomicversion))
                                            scount+=1
                                        else:
                                            logger.fdebug("Versions wrong. Ignoring possible match.")
                                            scount = 0
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
                            spercent = (wordcnt/totalcnt) * 100
                        except ZeroDivisionError:
                            spercent = 0
                        logger.fdebug("we got " + str(spercent) + " percent.")
                        if int(spercent) >= 80:
                            logger.fdebug("it's a go captain... - we matched " + str(spercent) + "%!")
                        if int(spercent) < 80:
                            logger.fdebug("failure - we only got " + str(spercent) + "% right!")
                            continue
                        logger.fdebug("this should be a match!")
                        logger.fdebug("issue we are looking for is : " + str(findcomiciss))
                        logger.fdebug("integer value of issue we are looking for : " + str(intIss))

                        fnd_iss_except = None
                        comintIss = helpers.issuedigits(comic_iss)
                        logger.fdebug("issue we found for is : " + str(comic_iss))
                        logger.fdebug("integer value of issue we are found : " + str(comintIss))
                        
                        #issue comparison now as well
                        if int(intIss) == int(comintIss):
                            logger.fdebug('issues match!')
                            logger.info(u"Found " + ComicName + " (" + str(comyear) + ") issue: " + str(IssueNumber) + " using " + str(tmpprov) )
                        ## -- inherit issue. Comic year is non-standard. nzb year is the year
                        ## -- comic was printed, not the start year of the comic series and
                        ## -- thus the deciding component if matches are correct or not
                            linkstart = os.path.splitext(entry['link'])[0]
                        #following is JUST for nzb.su
                            if nzbprov == 'nzb.su' or nzbprov == 'newznab':
                                linkit = os.path.splitext(entry['link'])[1]
                                linkit = linkit.replace("&", "%26")
                                linkapi = str(linkstart) + str(linkit)
                            else:
                                # this should work for every other provider
                                linkstart = linkstart.replace("&", "%26")
                                linkapi = str(linkstart)
                            logger.fdebug("link given by: " + str(nzbprov))
                            #logger.fdebug("link: " + str(linkstart))
                            #logger.fdebug("linkforapi: " + str(linkapi))
                            #here we distinguish between rename and not.
                            #blackhole functinality---
                            #let's download the file to a temporary cache.
                            sent_to = None
                            if mylar.BLACKHOLE and nzbprov != 'CBT' and nzbprov != 'KAT':
                                logger.fdebug("using blackhole directory at : " + str(mylar.BLACKHOLE_DIR))
                                if os.path.exists(mylar.BLACKHOLE_DIR):
                                    #pretty this biatch up.
                                    BComicName = re.sub('[\:\,\/\?]', '', str(ComicName))
                                    Bl_ComicName = re.sub('[\&]', 'and', str(BComicName))
                                    filenamenzb = str(re.sub(" ", ".", str(Bl_ComicName))) + "." + str(IssueNumber) + ".(" + str(comyear) + ").nzb"
                                    # Add a user-agent
                                    request = urllib2.Request(linkapi) #(str(mylar.BLACKHOLE_DIR) + str(filenamenzb))
                                    request.add_header('User-Agent', str(mylar.USER_AGENT))
                                    try: 
                                        opener = helpers.urlretrieve(urllib2.urlopen(request), str(mylar.BLACKHOLE_DIR) + str(filenamenzb))
                                    except Exception, e:
                                         logger.warn('Error fetching data from %s: %s' % (nzbprov, e))
                                         return
                                    logger.fdebug("filename saved to your blackhole as : " + str(filenamenzb))
                                    logger.info(u"Successfully sent .nzb to your Blackhole directory : " + str(mylar.BLACKHOLE_DIR) + str(filenamenzb) )
                                    extensions = ('.cbr', '.cbz')

                                    if filenamenzb.lower().endswith(extensions):
                                        fd, ext = os.path.splitext(filenamenzb)
                                        logger.fdebug("Removed extension from nzb: " + ext)
                                        nzbname = re.sub(str(ext), '', str(filenamenzb))
                                    logger.fdebug("nzb name to be used for post-processing is : " + str(nzbname))
                                    sent_to = "your Blackhole Directory"
                            #end blackhole
                            elif nzbprov == 'CBT' or nzbprov == 'KAT':
                                logger.fdebug("sending .torrent to watchdir.")
                                logger.fdebug("ComicName:" + ComicName)
                                logger.fdebug("link:" + entry['link'])
                                logger.fdebug("Torrent Provider:" + nzbprov)
                                foundc = "yes"

                                #let's change all space to decimals for simplicity
                                nzbname = re.sub(" ", ".", str(entry['title']))
                                #gotta replace & or escape it
                                nzbname = re.sub("\&", 'and', str(nzbname))
                                nzbname = re.sub('[\,\:\?]', '', str(nzbname))
                                if nzbname.lower().endswith('.torrent'):
                                    nzbname = re.sub('.torrent', '', nzbname)
                                rcheck = rsscheck.torsend2client(ComicName, IssueNumber, comyear, entry['link'], nzbprov)
                                if rcheck == "fail":
                                    logger.error("Unable to send torrent - check logs and settings.")
                                    return
                                if mylar.TORRENT_LOCAL:
                                    sent_to = "your local Watch folder"
                                else:
                                    sent_to = "your seedbox Watch folder"
                            else:
                                tmppath = mylar.CACHE_DIR
                                if os.path.exists(tmppath):
                                   logger.fdebug("cache directory successfully found at : " + str(tmppath))
                                   pass
                                else:
                                #let's make the dir.
                                    logger.fdebug("couldn't locate cache directory, attempting to create at : " + str(mylar.CACHE_DIR))
                                    try:
                                        os.makedirs(str(mylar.CACHE_DIR))
                                        logger.info(u"Cache Directory successfully created at: " + str(mylar.CACHE_DIR))

                                    except OSError.e:
                                        if e.errno != errno.EEXIST:
                                            raise
                                logger.fdebug("link to retrieve via api:" + str(helpers.apiremove(linkapi,'$')))
                           
                                #let's change all space to decimals for simplicity
                                nzbname = re.sub(" ", ".", str(entry['title']))
                                #gotta replace & or escape it
                                nzbname = re.sub("\&", 'and', str(nzbname))
                                nzbname = re.sub('[\,\:\?]', '', str(nzbname))
                                extensions = ('.cbr', '.cbz')

                                if nzbname.lower().endswith(extensions):
                                    fd, ext = os.path.splitext(nzbname)
                                    logger.fdebug("Removed extension from nzb: " + ext)
                                    nzbname = re.sub(str(ext), '', str(nzbname))

                                logger.fdebug("nzbname used for post-processing:" + str(nzbname))

                                #we need to change the nzbx string now to allow for the nzbname rename.
                                if nzbprov == 'nzbx':
                                    nzbxlink_st = linkapi.find("*|*")
                                    linkapi = linkapi[:(nzbxlink_st + 3)] + str(nzbname)
                                    logger.fdebug("new linkapi (this should =nzbname) :" + str(linkapi))

#                               #test nzb.get
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
                                        return
                                    tmpapi = str(tmpapi) + str(mylar.NZBGET_USERNAME) + ":" + str(mylar.NZBGET_PASSWORD)
                                    tmpapi = str(tmpapi) + "@" + str(nzbget_host) + ":" + str(mylar.NZBGET_PORT) + "/xmlrpc"
                                    server = ServerProxy(tmpapi)
                                    send_to_nzbget = server.appendurl(nzbname + ".nzb", str(mylar.NZBGET_CATEGORY), int(nzbgetpriority), True, linkapi)
                                    sent_to = "NZBGet"
                                    if send_to_nzbget is True:
                                        logger.info("Successfully sent nzb to NZBGet!")
                                    else:
                                        logger.info("Unable to send nzb to NZBGet - check your configs.")
#                                #end nzb.get test
               
                                elif mylar.USE_SABNZBD:
                                    # let's build the send-to-SAB string now:
                                    tmpapi = str(mylar.SAB_HOST)
                                    logger.fdebug("send-to-SAB host string: " + str(tmpapi))
                                    # changed to just work with direct links now...
                                    SABtype = "/api?mode=addurl&name="
                                    fileURL = str(linkapi)
                                    tmpapi = tmpapi + str(SABtype)
                                    logger.fdebug("...selecting API type: " + str(tmpapi))
                                    tmpapi = tmpapi + str(fileURL)
                                    
                                    logger.fdebug("...attaching nzb provider link: " + str(helpers.apiremove(tmpapi,'$')))
                                    # determine SAB priority
                                    if mylar.SAB_PRIORITY:
                                        tmpapi = tmpapi + "&priority=" + str(sabpriority)
                                        logger.fdebug("...setting priority: " + str(helpers.apiremove(tmpapi,'&')))
                                    # if category is blank, let's adjust
                                    if mylar.SAB_CATEGORY:
                                        tmpapi = tmpapi + "&cat=" + str(mylar.SAB_CATEGORY)
                                        logger.fdebug("...attaching category: " + str(helpers.apiremove(tmpapi,'&')))
                                    if mylar.RENAME_FILES or mylar.POST_PROCESSING:
                                        tmpapi = tmpapi + "&script=ComicRN.py"
                                        logger.fdebug("...attaching rename script: " + str(helpers.apiremove(tmpapi,'&')))
                                    #final build of send-to-SAB    
                                    tmpapi = tmpapi + "&apikey=" + str(mylar.SAB_APIKEY)

                                    logger.fdebug("Completed send-to-SAB link: " + str(helpers.apiremove(tmpapi,'&')))

                                    try:
                                        urllib2.urlopen(tmpapi)
                                    except urllib2.URLError:
                                        logger.error(u"Unable to send nzb file to SABnzbd")
                                        return
 
                                    sent_to = "SABnzbd+"
                                    logger.info(u"Successfully sent nzb file to SABnzbd")

                            if mylar.PROWL_ENABLED and mylar.PROWL_ONSNATCH:
                                logger.info(u"Sending Prowl notification")
                                prowl = notifiers.PROWL()
                                prowl.notify(nzbname,"Download started using " + sent_to)
                            if mylar.NMA_ENABLED and mylar.NMA_ONSNATCH:
                                logger.info(u"Sending NMA notification")
                                nma = notifiers.NMA()
                                nma.notify(snatched_nzb=nzbname,sent_to=sent_to)
                            if mylar.PUSHOVER_ENABLED and mylar.PUSHOVER_ONSNATCH:
                                logger.info(u"Sending Pushover notification")
                                pushover = notifiers.PUSHOVER()
                                pushover.notify(nzbname,"Download started using " + sent_to)
                            if mylar.BOXCAR_ENABLED and mylar.BOXCAR_ONSNATCH:
                                logger.info(u"Sending Boxcar notification")
                                boxcar = notifiers.BOXCAR()
                                boxcar.notify(snatched_nzb=nzbname,sent_to=sent_to)

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
            logger.fdebug("Found matching comic...preparing to send to Updater with IssueID: " + str(IssueID) + " and nzbname: " + str(nzbname))
            updater.nzblog(IssueID, nzbname, ComicName, SARC, IssueArcID)
            nzbpr == 0
            #break
            return foundc
        elif foundc == "no" and nzbpr == 0:
            foundcomic.append("no")
            logger.fdebug("couldn't find a matching comic using " + str(tmpprov))
            if IssDateFix == "no":
                logger.info(u"Couldn't find Issue " + str(IssueNumber) + " of " + ComicName + "(" + str(comyear) + "). Status kept as wanted." )
                break
    return foundc

def searchforissue(issueid=None, new=False, rsscheck=None):
    myDB = db.DBConnection()

    if not issueid or rsscheck:

        if rsscheck:
            logger.info(u"Initiating RSS Search Scan at scheduled interval of " + str(mylar.RSS_CHECKINTERVAL) + " minutes.")
        else:
            logger.info(u"Initiating NZB Search scan at requested interval of " + str(mylar.SEARCH_INTERVAL) + " minutes.")

        myDB = db.DBConnection()

        stloop = 1
        results = []

        if mylar.ANNUALS_ON:
            stloop+=1
        while (stloop > 0):
            if stloop == 1:
                issues_1 = myDB.select('SELECT * from issues WHERE Status="Wanted"')
                for iss in issues_1:
                    results.append({'ComicID':       iss['ComicID'],
                                    'IssueID':       iss['IssueID'],
                                    'Issue_Number':  iss['Issue_Number'],
                                    'IssueDate':     iss['IssueDate'],
                                    'mode':          'want'
                                   })
            elif stloop == 2:
                issues_2 = myDB.select('SELECT * from annuals WHERE Status="Wanted"')
                for iss in issues_2:
                    results.append({'ComicID':       iss['ComicID'],
                                    'IssueID':       iss['IssueID'],
                                    'Issue_Number':  iss['Issue_Number'],
                                    'IssueDate':     iss['IssueDate'],
                                    'mode':          'want_ann'
                                   })
            stloop-=1

        new = True

        for result in results:
            comic = myDB.action("SELECT * from comics WHERE ComicID=? AND ComicName != 'None'", [result['ComicID']]).fetchone()
            foundNZB = "none"
            SeriesYear = comic['ComicYear']
            AlternateSearch = comic['AlternateSearch']
            IssueDate = result['IssueDate']
            UseFuzzy = comic['UseFuzzy']
            ComicVersion = comic['ComicVersion']
            if result['IssueDate'] == None: 
                ComicYear = comic['ComicYear']
            else: 
                ComicYear = str(result['IssueDate'])[:4]
            mode = result['mode']
            if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL or mylar.NEWZNAB or mylar.NZBX or mylar.ENABLE_KAT or mylar.ENABLE_CBT) and (mylar.USE_SABNZBD or mylar.USE_NZBGET or mylar.ENABLE_TORRENTS):
                    foundNZB, prov = search_init(comic['ComicName'], result['Issue_Number'], str(ComicYear), comic['ComicYear'], IssueDate, result['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, SARC=None, IssueArcID=None, mode=mode, rsscheck=rsscheck, ComicID=result['ComicID'])
                    if foundNZB == "yes": 
                        #print ("found!")
                        updater.foundsearch(result['ComicID'], result['IssueID'], mode=mode, provider=prov)
                    else:
                        pass 
                        #print ("not found!")
    else:
        result = myDB.action('SELECT * FROM issues where IssueID=?', [issueid]).fetchone()
        mode = 'want'
        if result is None:
            result = myDB.action('SELECT * FROM annuals where IssueID=?', [issueid]).fetchone()
            mode = 'want_ann'
            if result is None:
                logger.info("Unable to locate IssueID - you probably should delete/refresh the series.")
                return
        ComicID = result['ComicID']
        comic = myDB.action('SELECT * FROM comics where ComicID=?', [ComicID]).fetchone()
        SeriesYear = comic['ComicYear']
        AlternateSearch = comic['AlternateSearch']
        IssueDate = result['IssueDate']
        UseFuzzy = comic['UseFuzzy']
        ComicVersion = comic['ComicVersion']
        if result['IssueDate'] == None:
            IssueYear = comic['ComicYear']
        else:
            IssueYear = str(result['IssueDate'])[:4]

        foundNZB = "none"
        if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL or mylar.NEWZNAB or mylar.NZBX) and (mylar.USE_SABNZBD or mylar.USE_NZBGET):
            foundNZB, prov = search_init(result['ComicName'], result['Issue_Number'], str(IssueYear), comic['ComicYear'], IssueDate, result['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, mode=mode, ComicID=ComicID)
            if foundNZB == "yes":
                logger.fdebug("I found " + result['ComicName'] + ' #:' + str(result['Issue_Number']))
                updater.foundsearch(ComicID=result['ComicID'], IssueID=result['IssueID'], mode=mode, provider=prov)
            else:
                pass 
                #print ("not found!")
    return

def searchIssueIDList(issuelist):
    myDB = db.DBConnection()
    for issueid in issuelist:
        issue = myDB.action('SELECT * from issues WHERE IssueID=?', [issueid]).fetchone()
        mode = 'want'
        if issue is None:
            issue = myDB.action('SELECT * from annuals WHERE IssueID=?', [issueid]).fetchone()
            mode = 'want_ann'
            if issue is None:
                logger.info("unable to determine IssueID - perhaps you need to delete/refresh series?")
                break
        comic = myDB.action('SELECT * from comics WHERE ComicID=?', [issue['ComicID']]).fetchone()
        print ("Checking for issue: " + str(issue['Issue_Number']))
        foundNZB = "none"
        SeriesYear = comic['ComicYear']
        AlternateSearch = comic['AlternateSearch']
        UseFuzzy = comic['UseFuzzy']
        ComicVersion = comic['ComicVersion']
        if issue['IssueDate'] == None:
            IssueYear = comic['ComicYear']
        else:
            IssueYear = str(issue['IssueDate'])[:4]
        if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL or mylar.NEWZNAB or mylar.NZBX or mylar.ENABLE_CBT or mylar.ENABLE_KAT) and (mylar.USE_SABNZBD or mylar.USE_NZBGET or mylar.ENABLE_TORRENTS):
                foundNZB, prov = search_init(comic['ComicName'], issue['Issue_Number'], str(IssueYear), comic['ComicYear'], issue['IssueDate'], issue['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, SARC=None, IssueArcID=None, mode=mode, ComicID=issue['ComicID'])
                if foundNZB == "yes":
                    #print ("found!")
                    updater.foundsearch(ComicID=issue['ComicID'], IssueID=issue['IssueID'], mode=mode, provider=prov)
                else:
                    pass
                    #print ("not found!")

