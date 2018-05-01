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
from mylar import logger, db, updater, helpers, parseit, findcomicfeed, notifiers, rsscheck, Failed, filechecker, auth32p, sabnzbd, nzbget, wwt

import feedparser
import requests
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
from base64 import b16encode, b32decode
from operator import itemgetter
from wsgiref.handlers import format_date_time

def search_init(ComicName, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, IssueID, AlternateSearch=None, UseFuzzy=None, ComicVersion=None, SARC=None, IssueArcID=None, mode=None, rsscheck=None, ComicID=None, manualsearch=None, filesafe=None, allow_packs=None, oneoff=False, manual=False, torrentid_32p=None):

    mylar.COMICINFO = []
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

    if IssueArcID and not IssueID:
        issuetitle = helpers.get_issue_title(IssueArcID)
    else:
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

    if mode == 'pullwant' or IssueID is None:
        #one-off the download.
        logger.fdebug('One-Off Search parameters:')
        logger.fdebug('ComicName: %s' % ComicName)
        logger.fdebug('Issue: %s' % IssueNumber)
        logger.fdebug('Year: %s' %ComicYear)
        logger.fdebug('IssueDate: %s' % IssueDate)
        oneoff = True
    if SARC:
        logger.fdebug("Story-ARC Search parameters:")
        logger.fdebug("Story-ARC: " + str(SARC))
        logger.fdebug("IssueArcID: " + str(IssueArcID))

    torprovider = []
    torp = 0
    torznabs = 0
    torznab_hosts = []

    logger.fdebug("Checking for torrent enabled.")
    checked_once = False
    if mylar.CONFIG.ENABLE_TORRENT_SEARCH: #and mylar.CONFIG.ENABLE_TORRENTS:
        if mylar.CONFIG.ENABLE_32P:
            torprovider.append('32p')
            torp+=1
        if mylar.CONFIG.ENABLE_PUBLIC:
            torprovider.append('public torrents')
            torp+=1
        if mylar.CONFIG.ENABLE_TORZNAB is True:
            for torznab_host in mylar.CONFIG.EXTRA_TORZNABS:
                if torznab_host[4] == '1' or torznab_host[4] == 1:
                    torznab_hosts.append(torznab_host)
                    torprovider.append('torznab:' + str(torznab_host[0]))
                    torznabs+=1

    ##nzb provider selection##
    ##'dognzb' or 'nzb.su' or 'experimental'
    nzbprovider = []
    nzbp = 0
    if mylar.CONFIG.NZBSU == True:
        nzbprovider.append('nzb.su')
        nzbp+=1
    if mylar.CONFIG.DOGNZB == True:
        nzbprovider.append('dognzb')
        nzbp+=1

    # --------
    #  Xperimental
    if mylar.CONFIG.EXPERIMENTAL == True:
        nzbprovider.append('experimental')
        nzbp+=1

    newznabs = 0

    newznab_hosts = []

    if mylar.CONFIG.NEWZNAB is True:
        for newznab_host in mylar.CONFIG.EXTRA_NEWZNABS:
            if newznab_host[5] == '1' or newznab_host[5] == 1:
                newznab_hosts.append(newznab_host)
                nzbprovider.append('newznab:' + str(newznab_host[0]))
                newznabs+=1

    logger.fdebug('nzbprovider(s): ' + str(nzbprovider))
    # --------
    torproviders = torp + torznabs
    logger.fdebug('There are %s torrent providers you have selected.' % torproviders)
    torpr = torproviders - 1
    if torpr < 0:
        torpr = -1
    providercount = int(nzbp + newznabs)
    logger.fdebug("there are : " + str(providercount) + " nzb providers you have selected.")
    if providercount > 0:
        logger.fdebug("Usenet Retention : " + str(mylar.CONFIG.USENET_RETENTION) + " days")
    findit = {}
    findit['status'] = False

    totalproviders = providercount + torproviders

    if totalproviders == 0:
        logger.error('[WARNING] You have ' + str(totalproviders) + ' search providers enabled. I need at least ONE provider to work. Aborting search.')
        findit['status'] = False
        nzbprov = None
        return findit, nzbprov

    prov_order, torznab_info, newznab_info = provider_sequence(nzbprovider, torprovider, newznab_hosts, torznab_hosts)
    # end provider order sequencing
    logger.info('search provider order is ' + str(prov_order))

    #fix for issue dates between Nov-Dec/(Jan-Feb-Mar)
    IssDt = str(IssueDate)[5:7]
    if IssDt == "12" or IssDt == "11" or IssDt == "01" or IssDt == "02" or IssDt == "03":
         IssDateFix = IssDt
    else:
         IssDateFix = "no"

    searchcnt = 0
    srchloop = 1

    if rsscheck:
        if mylar.CONFIG.ENABLE_RSS:
            searchcnt = 1  # rss-only
        else:
            searchcnt = 0  # if it's not enabled, don't even bother.
    else:
        if mylar.CONFIG.ENABLE_RSS:
            searchcnt = 2 # rss first, then api on non-matches
        else:
            searchcnt = 2  #set the searchcnt to 2 (api)
            srchloop = 2   #start the counter at api, so it will exit without running RSS

    if IssueNumber is not None:
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

        #determine the amount of loops here
        fcs = 0
        c_alpha = None
        dsp_c_alpha = None
        c_number = None
        c_num_a4 = None
        while fcs < len(findcomiciss):
            #take first occurance of alpha in string and carry it through
            if findcomiciss[fcs].isalpha():
                c_alpha = findcomiciss[fcs:].rstrip()
                c_number = findcomiciss[:fcs].rstrip()
                break
            elif '.' in findcomiciss[fcs]:
                c_number = findcomiciss[:fcs].rstrip()
                c_num_a4 = findcomiciss[fcs+1:].rstrip()
                #if decimal seperates numeric from alpha (ie - 7.INH)
                #don't give calpha a value or else will seperate with a space further down
                #assign it to dsp_c_alpha so that it can be displayed for debugging.
                if not c_num_a4.isdigit():
                    dsp_c_alpha = c_num_a4
                else:
                    c_number = str(c_number) + '.' + str(c_num_a4)
                break
            fcs+=1
        logger.fdebug("calpha/cnumber: " + str(dsp_c_alpha) + " / " + str(c_number))

        if c_number is None:
            c_number = findcomiciss # if it's None, means no special alphas or decimals

        if '.' in c_number:
            decst = c_number.find('.')
            c_number = c_number[:decst].rstrip()

    while (srchloop <= searchcnt):
        logger.fdebug('srchloop: %s' % srchloop)
        #searchmodes:
        # rss - will run through the built-cached db of entries
        # api - will run through the providers via api (or non-api in the case of Experimental)
        # the trick is if the search is done during an rss compare, it needs to exit when done.
        # otherwise, the order of operations is rss feed check first, followed by api on non-results.

        if srchloop == 1: searchmode = 'rss'  #order of ops - this will be used first.
        elif srchloop == 2: searchmode = 'api'

        if '0-Day' in ComicName:
            cmloopit = 1
        else:
            if len(c_number) == 1:
                cmloopit = 3
            elif len(c_number) == 2:
                cmloopit = 2
            else:
                cmloopit = 1


        if findit['status'] is True:
            logger.fdebug('Found result on first run, exiting search module now.')
            break

        logger.fdebug("Initiating Search via : " + str(searchmode))

        while (cmloopit >= 1):
            prov_count = 0
            if len(prov_order) == 1:
                tmp_prov_count = 1
            else:
                tmp_prov_count = len(prov_order)

            searchprov = None

            while (tmp_prov_count > prov_count):
                send_prov_count = tmp_prov_count - prov_count
                newznab_host = None
                torznab_host = None
                if prov_order[prov_count] == '32p':
                    searchprov = '32P'
                elif prov_order[prov_count] == 'public torrents':
                    searchprov = 'Public Torrents'
                elif 'torznab' in prov_order[prov_count]:
                    searchprov = 'torznab'
                    for nninfo in torznab_info:
                        if nninfo['provider'] == prov_order[prov_count]:
                            torznab_host = nninfo['info']
                    if torznab_host is None:
                        logger.fdebug('there was an error - torznab information was blank and it should not be.')
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
                    torznab_host = None
                    searchprov = prov_order[prov_count].lower()

                if searchprov == 'dognzb' and mylar.CONFIG.DOGNZB == 0:
                    #since dognzb could hit the 50 daily api limit during the middle of a search run, check here on each pass to make
                    #sure it's not disabled (it gets auto-disabled on maxing out the API hits)
                    prov_count+=1
                    continue
                elif all([searchprov == '32P', checked_once is True]) or all ([searchprov == 'Public Torrents', checked_once is True]) or all([searchprov == 'experimental', checked_once is True]):
                    prov_count+=1
                    continue
                if searchmode == 'rss':
                    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, searchprov, send_prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID, issuetitle=issuetitle, unaltered_ComicName=unaltered_ComicName, oneoff=oneoff, cmloopit=cmloopit, manual=manual, torznab_host=torznab_host)
                    if findit['status'] is False:
                        if AlternateSearch is not None and AlternateSearch != "None":
                            chkthealt = AlternateSearch.split('##')
                            if chkthealt == 0:
                                AS_Alternate = AlternateSearch
                            loopit = len(chkthealt)
                            for calt in chkthealt:
                                AS_Alternate = re.sub('##', '', calt)
                                logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate))
                                findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, searchprov, send_prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="yes", ComicID=ComicID, issuetitle=issuetitle, unaltered_ComicName=AS_Alternate, allow_packs=allow_packs, oneoff=oneoff, cmloopit=cmloopit, manual=manual, torznab_host=torznab_host)
                                if findit['status'] is True:
                                    break
                            if findit['status'] is True:
                                break
                    else:
                        logger.fdebug("findit = found!")
                        break

                else:
                    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, searchprov, send_prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="no", ComicID=ComicID, issuetitle=issuetitle, unaltered_ComicName=unaltered_ComicName, allow_packs=allow_packs, oneoff=oneoff, cmloopit=cmloopit, manual=manual, torznab_host=torznab_host, torrentid_32p=torrentid_32p)
                    if all([searchprov == '32P', checked_once is False]) or all([searchprov == 'Public Torrents', checked_once is False]):
                        checked_once = True
                    if findit['status'] is False:
                        if AlternateSearch is not None and AlternateSearch != "None":
                            chkthealt = AlternateSearch.split('##')
                            if chkthealt == 0:
                                AS_Alternate = AlternateSearch
                            loopit = len(chkthealt)
                            for calt in chkthealt:
                                AS_Alternate = re.sub('##', '', calt)
                                logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AS_Alternate))
                                findit = NZB_SEARCH(AS_Alternate, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, searchprov, send_prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host, ComicVersion=ComicVersion, SARC=SARC, IssueArcID=IssueArcID, RSS="no", ComicID=ComicID, issuetitle=issuetitle, unaltered_ComicName=unaltered_ComicName, allow_packs=allow_packs, oneoff=oneoff, cmloopit=cmloopit, manual=manual, torznab_host=torznab_host, torrentid_32p=torrentid_32p)
                                if findit['status'] is True:
                                    break
                            if findit['status'] is True:
                                break
                    else:
                        logger.fdebug("findit = found!")
                        break

                if searchprov == 'newznab':
                    searchprov = newznab_host[0].rstrip()
                elif searchprov == 'torznab':
                    searchprov = torznab_host[0].rstrip()
                if manual is not True:
                    if IssueNumber is not None:
                        issuedisplay = IssueNumber
                    else:
                        issuedisplay = StoreDate[5:]
                    logger.info('Could not find Issue %s of %s (%s) using %s [%s]' % (issuedisplay, ComicName, SeriesYear, searchprov, searchmode))
                prov_count+=1

            if findit['status'] is True:
                srchloop = 4 
                break
            elif srchloop == 2 and (cmloopit -1 >= 1):
                time.sleep(30)  #pause for 30s to not hammmer api's

            cmloopit-=1

        srchloop+=1

    if manual is True:
        logger.info('I have matched %s files: %s' % (len(mylar.COMICINFO), mylar.COMICINFO))
        return mylar.COMICINFO, 'None'

    if findit['status'] is True:
        #check for snatched_havetotal being enabled here and adjust counts now.
        #IssueID being the catch/check for one-offs as they won't exist on the watchlist and error out otherwise.
        if mylar.CONFIG.SNATCHED_HAVETOTAL and any([oneoff is False, IssueID is not None]):
            logger.fdebug('Adding this to the HAVE total for the series.')
            helpers.incr_snatched(ComicID)
        if searchprov == 'Public Torrents' and mylar.TMP_PROV != searchprov:
            searchprov = mylar.TMP_PROV
        return findit, searchprov
    else:
        logger.info('findit: %s' % findit)
        #if searchprov == '32P':
        #    pass
        if manualsearch is None:
            logger.info('Finished searching via :' + str(searchmode) + '. Issue not found - status kept as Wanted.')
        else:
            logger.fdebug('Could not find issue doing a manual search via : ' + str(searchmode))
        if searchprov == '32P':
            if mylar.CONFIG.MODE_32P == 0:
                return findit, 'None'
            elif mylar.CONFIG.MODE_32P == 1 and searchmode == 'api':
                return findit, 'None'

    return findit, 'None'

def NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, nzbprov, prov_count, IssDateFix, IssueID, UseFuzzy, newznab_host=None, ComicVersion=None, SARC=None, IssueArcID=None, RSS=None, ComicID=None, issuetitle=None, unaltered_ComicName=None, allow_packs=None, oneoff=False, cmloopit=None, manual=False, torznab_host=None, torrentid_32p=None):

    if any([allow_packs is None, allow_packs == 'None', allow_packs == 0, allow_packs == '0']) and all([mylar.CONFIG.ENABLE_TORRENT_SEARCH, mylar.CONFIG.ENABLE_32P]):
        allow_packs = False
    elif any([allow_packs == 1, allow_packs == '1']) and all([mylar.CONFIG.ENABLE_TORRENT_SEARCH, mylar.CONFIG.ENABLE_32P]):
        allow_packs = True

    newznab_local = False

    if nzbprov == 'nzb.su':
        apikey = mylar.CONFIG.NZBSU_APIKEY
        verify = bool(mylar.CONFIG.NZBSU_VERIFY)
    elif nzbprov == 'dognzb':
        apikey = mylar.CONFIG.DOGNZB_APIKEY
        verify = bool(mylar.CONFIG.DOGNZB_VERIFY)
    elif nzbprov == 'experimental':
        apikey = 'none'
        verify = False
    elif nzbprov == 'torznab':
        name_torznab = torznab_host[0].rstrip()
        host_torznab = torznab_host[1].rstrip()
        apikey = torznab_host[2].rstrip()
        verify = False
        category_torznab = torznab_host[3]
        if any([category_torznab is None, category_torznab == 'None']):
            category_torznab = '8020'
        logger.fdebug("using Torznab host of : " + str(name_torznab))
    elif nzbprov == 'newznab':
        #updated to include Newznab Name now
        name_newznab = newznab_host[0].rstrip()
        host_newznab = newznab_host[1].rstrip()
        if name_newznab[-7:] == '[local]':
            name_newznab = name_newznab[:-7].strip()
            newznab_local = True
        elif name_newznab[-10:] == '[nzbhydra]':
            name_newznab = name_newznab[:-10].strip()
            newznab_local = False
        apikey = newznab_host[3].rstrip()
        verify = bool(newznab_host[2])
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
        elif 'torznab' in nzbprov:
            tmpprov = name_torznab + '(' + nzbprov + ')' + ' [RSS]'
        else:
            tmpprov = str(nzbprov) + " [RSS]"
    else:
        if 'newznab' in nzbprov:
            tmpprov = name_newznab + ' (' + nzbprov + ')'
        elif 'torznab' in nzbprov:
            tmpprov = name_torznab + ' (' + nzbprov + ')'
        else:
            tmpprov = nzbprov
    if IssueNumber is not None:
        issuedisplay = IssueNumber
    else:
        issuedisplay = StoreDate[5:]

    if '0-Day Comics Pack' in ComicName:
        logger.info('Shhh be very quiet...I\'m looking for %s using %s.' % (ComicName, tmpprov))
    else:
        logger.info('Shhh be very quiet...I\'m looking for %s issue: %s (%s) using %s.' % (ComicName, issuedisplay, ComicYear, tmpprov))


    #this will completely render the api search results empty. Needs to get fixed.
    if mylar.CONFIG.PREFERRED_QUALITY == 0: filetype = ""
    elif mylar.CONFIG.PREFERRED_QUALITY == 1: filetype = ".cbr"
    elif mylar.CONFIG.PREFERRED_QUALITY == 2: filetype = ".cbz"

    ci = ""
    comsearch = []
    isssearch = []
    comyear = str(ComicYear)

    #print ("-------SEARCH FOR MISSING------------------")
    #ComicName is unicode - let's unicode and ascii it cause we'll be comparing filenames against it.
    u_ComicName = ComicName.encode('ascii', 'replace').strip()
    findcomic = u_ComicName

    cm1 = re.sub("[\/\-]", " ", findcomic)
    # replace whitespace in comic name with %20 for api search
    #cm = re.sub("\&", "%26", str(cm1))
    cm = re.sub("\\band\\b", "", cm1.lower()) # remove 'and' & '&' from the search pattern entirely (broader results, will filter out later)
    cm = re.sub("\\bthe\\b", "", cm.lower()) # remove 'the' from the search pattern to accomodate naming differences
    cm = re.sub("[\&\:\?\,]", "", str(cm))
    cm = re.sub('\s+', ' ', cm)
    cm = re.sub(" ", "%20", str(cm))

    if IssueNumber is not None:
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

        isssearch = str(findcomiciss)
    else:
        isssearch = None

    comsearch = cm
    #origcmloopit = cmloopit
    findcount = 1  # this could be a loop in the future possibly

    findloop = 0
    foundcomic = []
    foundc = {}
    foundc['status'] = False
    done = False
    seperatealpha = "no"
    #---issue problem
    # if issue is '011' instead of '11' in nzb search results, will not have same
    # results. '011' will return different than '11', as will '009' and '09'.

    while (findloop < findcount):
        logger.fdebug('findloop: ' + str(findloop) + ' / findcount: ' + str(findcount))
        comsrc = comsearch
        if nzbprov == 'dognzb' and not mylar.CONFIG.DOGNZB:
            foundc['status'] = False
            done = True
            break
        if any([nzbprov == '32P', nzbprov == 'Public Torrents']):
            #because 32p directly stores the exact issue, no need to worry about iterating over variations of the issue number.
            findloop == 99

        if done is True and seperatealpha == "no":
            logger.fdebug("we should break out now - sucessful search previous")
            findloop == 99
            break

                # here we account for issue pattern variations
        if IssueNumber is not None:
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
            else:
                foundc['status'] = False
                done = True
                break
            mod_isssearch = str(issdig) + str(isssearch)
        else:
            comsearch = StoreDate
            mod_isssearch = StoreDate

        #--- this is basically for RSS Feeds ---
        #logger.fdebug('RSS Check: %s' % RSS)
        #logger.fdebug('nzbprov: %s' % nzbprov)
        #logger.fdebug('comicid: %s' % ComicID)
        if RSS == "yes":
            if nzbprov == '32P' or nzbprov == 'Public Torrents':
                cmname = re.sub("%20", " ", str(comsrc))
                logger.fdebug("Sending request to [" + str(nzbprov) + "] RSS for " + ComicName + " : " + str(mod_isssearch))
                bb = rsscheck.torrentdbsearch(ComicName, mod_isssearch, ComicID, nzbprov, oneoff)
            else:
                cmname = re.sub("%20", " ", str(comsrc))
                logger.fdebug("Sending request to RSS for " + str(findcomic) + " : " + str(mod_isssearch) + " (" + str(ComicYear) + ")")
                if nzbprov == 'newznab':
                    nzbprov_fix = name_newznab
                elif nzbprov == 'torznab':
                    nzbprov_fix = name_torznab
                else: nzbprov_fix = nzbprov
                bb = rsscheck.nzbdbsearch(findcomic, mod_isssearch, ComicID, nzbprov_fix, ComicYear, ComicVersion, oneoff)
            if bb is None:
                bb = 'no results'
        #this is the API calls
        else:
            #32P is redudant now since only RSS works
            # - just getting it ready for when it's not redudant :)
            if nzbprov == '':
                bb = "no results"
            if nzbprov == '32P':
                if all([mylar.CONFIG.MODE_32P == 1, mylar.CONFIG.ENABLE_32P is True]):
                    if ComicName[:17] == '0-Day Comics Pack':
                        searchterm = {'series': ComicName, 'issue': StoreDate[8:10], 'volume': StoreDate[5:7]}
                    else:
                        searchterm = {'series': ComicName, 'id': ComicID, 'issue': findcomiciss, 'volume': ComicVersion, 'publisher': Publisher, 'torrentid_32p': torrentid_32p}
                    #first we find the id on the serieslist of 32P
                    #then we call the ajax against the id and issue# and volume (if exists)
                    a = auth32p.info32p(searchterm=searchterm)
                    bb = a.searchit()
                    if bb is None:
                        bb = 'no results'
                else:
                    bb = "no results"
            elif nzbprov == 'Public Torrents':
                cmname = re.sub("%20", " ", str(comsrc))
                logger.fdebug("Sending request to [WWT-SEARCH] for " + str(cmname) + " : " + str(mod_isssearch))
                ww = wwt.wwt(cmname, mod_isssearch)
                bb = ww.wwt_connect()
                #bb = rsscheck.torrents(pickfeed='TPSE-SEARCH', seriesname=cmname, issue=mod_isssearch)#cmname,issue=mod_isssearch)
                if bb is None:
                    bb = 'no results'
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
                elif nzbprov == 'torznab':
                    if host_torznab[len(host_torznab)-1:len(host_torznab)] == '/':
                        torznab_fix = host_torznab[:-1]
                    else:
                        torznab_fix = host.torznab
                    findurl = str(torznab_fix) + "?t=search&q=" + str(comsearch)
                    if category_torznab is not None:
                        findurl += "&cat=" + str(category_torznab)
                else:
                    logger.warn('You have a blank newznab entry within your configuration. Remove it, save the config and restart mylar to fix things. Skipping this blank provider until fixed.')
                    findurl = None
                    bb = "noresults"

                if findurl:
                    # helper function to replace apikey here so we avoid logging it ;)
                    findurl = findurl + "&apikey=" + str(apikey)
                    logsearch = helpers.apiremove(str(findurl), 'nzb')

                    ### IF USENET_RETENTION is set, honour it
                    ### For newznab sites, that means appending "&maxage=<whatever>" on the URL
                    if mylar.CONFIG.USENET_RETENTION != None and nzbprov != 'torznab':
                        findurl = findurl + "&maxage=" + str(mylar.CONFIG.USENET_RETENTION)

                    #set a delay between searches here. Default is for 30 seconds...
                    #changing this to lower could result in a ban from your nzb source due to hammering.
                    if mylar.CONFIG.SEARCH_DELAY == 'None' or mylar.CONFIG.SEARCH_DELAY is None:
                        pause_the_search = 30   # (it's in seconds)
                    elif str(mylar.CONFIG.SEARCH_DELAY).isdigit() and manual is False:
                        pause_the_search = int(mylar.CONFIG.SEARCH_DELAY) * 60
                    else:
                        logger.info("Check Search Delay - invalid numerical given. Force-setting to 30 seconds.")
                        pause_the_search = 30

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

                        if any([hnc[:3] == '10.', hnc[:4] == '172.', hnc[:4] == '192.', hnc.startswith('localhost'), newznab_local is True]) and newznab_local != False:
                            logger.info('local domain bypass for ' + name_newznab + ' is active.')
                            localbypass = True

                    if localbypass == False:
                        logger.info("pausing for " + str(pause_the_search) + " seconds before continuing to avoid hammering")
                        #time.sleep(pause_the_search)

                    # Add a user-agent
                    headers = {'User-Agent':   str(mylar.USER_AGENT)}
                    payload = None

                    if findurl.startswith('https:') and verify == False:
                        try:
                            from requests.packages.urllib3 import disable_warnings
                            disable_warnings()
                        except:
                            logger.warn('Unable to disable https warnings. Expect some spam if using https nzb providers.')

                    elif findurl.startswith('http:') and verify == True:
                        verify = False

                    #logger.fdebug('[SSL: ' + str(verify) + '] Search URL: ' + findurl)
                    logger.fdebug('[SSL: ' + str(verify) + '] Search URL: ' + str(logsearch))

                    try:
                        r = requests.get(findurl, params=payload, verify=verify, headers=headers)
                    except requests.exceptions.Timeout as e:
                        logger.warn('Timeout occured fetching data from %s: %s' % (nzbprov, e))
                        foundc['status'] = False
                        break
                    except requests.exceptions.ConnectionError as e:
                        logger.warn('Connection error trying to retrieve data from %s: %s' % (nzbprov, e))
                        foundc['status'] = False
                        break
                    except requests.exceptions.RequestException as e:
                        logger.warn('General Error fetching data from %s: %s' % (nzbprov, e))
                        if e.r.status_code == 503: 
                            #HTTP Error 503
                            logger.warn('Aborting search due to Provider unavailability')
                            foundc['status'] = False
                        break

                    try:
                        if str(r.status_code) != '200':
                            logger.warn('Unable to retrieve search results from ' + tmpprov + ' [Status Code returned: ' + str(r.status_code) + ']')
                            if str(r.status_code) == '503':
                                logger.warn('Unavailable indexer detected. Disabling for a short duration and will try again.')
                                helpers.disable_provider(tmpprov)
                            data = False
                        else:
                            data = r.content
                    except:
                        data = False

                    if data:
                        bb = feedparser.parse(data)
                    else:
                        bb = "no results"

                    try:
                        if bb == 'no results':
                            logger.fdebug('No results for search query from %s' % tmprov)
                            break
                        elif bb['feed']['error']:
                            logger.error('[ERROR CODE: ' + str(bb['feed']['error']['code']) + '] ' + str(bb['feed']['error']['description']))
                            if bb['feed']['error']['code'] == '910':
                                logger.warn('DAILY API limit reached. Disabling provider usage until 12:01am')
                                mylar.CONFIG.DOGNZB = 0
                                foundc['status'] = False
                                done = True
                            else:
                                logger.warn('API Error. Check the error message and take action if required.')
                                foundc['status'] = False
                                done = True
                            break
                    except:
                        logger.info('no errors on data retrieval...proceeding')
                        pass
            elif nzbprov == 'experimental':
                #bb = parseit.MysterBinScrape(comsearch[findloop], comyear)
                bb = findcomicfeed.Startit(u_ComicName, isssearch, comyear, ComicVersion, IssDateFix)
                # since the regexs in findcomicfeed do the 3 loops, lets force the exit after
                #cmloopit == 1

        done = False
        log2file = ""
        pack0day = False
        if not bb == "no results":
            for entry in bb['entries']:
                #logger.fdebug('entry: %s' % entry)  #<--- uncomment this to see what the search result(s) are
                #brief match here against 32p since it returns the direct issue number
                if nzbprov == '32P' and entry['title'][:17] == '0-Day Comics Pack':
                    logger.info('[32P-0DAY] 0-Day Comics Pack Discovered. Analyzing the pack info...')
                    if len(bb['entries']) == 1 or pack0day is True:
                        logger.info('[32P-0DAY] Only one pack for the week available. Selecting this by default.')
                    else:
                        logger.info('[32P-0DAY] More than one pack for the week is available...')
                        logger.info('bb-entries: %s' % bb['entries'])
                        if bb['entries'][1]['int_pubdate'] >= bb['int_pubdate']:
                            logger.info('[32P-0DAY] 2nd Pack is newest. Snatching that...')
                            pack0day = True
                            continue
                elif nzbprov == '32P' and RSS == 'no':
                    if entry['pack'] == '0':
                        if helpers.issuedigits(entry['issues']) == intIss:
                            logger.fdebug('32P direct match to issue # : ' + str(entry['issues']))
                        else:
                            logger.fdebug('The search result issue [' + str(entry['issues']) + '] does not match up for some reason to our search result [' + findcomiciss + ']')
                            continue

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
                    try:
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
                    except:
                        break

                comsize_m = 0
                if nzbprov != "dognzb":
                    #rss for experimental doesn't have the size constraints embedded. So we do it here.
                    if RSS == "yes":
                        if nzbprov == '32P':
                            try:
                                #newer rss feeds will now return filesize from 32p. Safe-guard it incase it's an older result
                                comsize_b = entry['length']
                            except:
                                comsize_b = None 
                        elif nzbprov == 'Public Torrents':
                            comsize_b = entry['length']
                        else:
                            comsize_b = entry['length']
                    else:
                        #Experimental already has size constraints done.
                        if nzbprov == '32P':
                            comsize_b = entry['filesize'] #None
                        elif nzbprov == 'Public Torrents':
                            comsize_b = entry['size']
                        elif nzbprov == 'experimental':
                            comsize_b = entry['length']  # we only want the size from the rss - the search/api has it already.
                        else:
                            try:
                                if entry['site'] == 'WWT':
                                    comsize_b = entry['size']
                            except:
                                tmpsz = entry.enclosures[0]
                                comsize_b = tmpsz['length']

                    logger.fdebug('comsize_b: %s' % comsize_b)
                    #file restriction limitation here
                    #only works with TPSE (done here) & 32P (done in rsscheck) & Experimental (has it embeded in search and rss checks)
                    if nzbprov == 'Public Torrents' or (nzbprov == '32P' and RSS == 'no' and entry['title'][:17] != '0-Day Comics Pack'):
                        if nzbprov == 'Public Torrents':
                            if 'cbr' in entry['title'].lower():
                                format_type = 'cbr'
                            elif 'cbz' in entry['title'].lower():
                                format_type = 'cbz'
                            else:
                                format_type = 'unknown'
                        else:
                            if 'cbr' in entry['format']:
                                format_type = 'cbr'
                            elif 'cbz' in entry['format']:
                                format_type = 'cbz'
                            else:
                                format_type = 'unknown'
                        if mylar.CONFIG.PREFERRED_QUALITY == 1:
                            if format_type == 'cbr':
                                logger.fdebug('Quality restriction enforced [ .cbr only ]. Accepting result.')
                            else:
                                logger.fdebug('Quality restriction enforced [ .cbr only ]. Rejecting this result.')
                                continue
                        elif mylar.CONFIG.PREFERRED_QUALITY == 2:
                            if format_type == 'cbz':
                                logger.fdebug('Quality restriction enforced [ .cbz only ]. Accepting result.')
                            else:
                                logger.fdebug('Quality restriction enforced [ .cbz only ]. Rejecting this result.')
                                continue

                    if comsize_b is None or comsize_b == '0':
                        logger.fdebug('Size of file cannot be retrieved. Ignoring size-comparison and continuing.')
                        #comsize_b = 0
                    else:
                        if entry['title'][:17] != '0-Day Comics Pack':
                            comsize_m = helpers.human_size(comsize_b)
                            logger.fdebug("size given as: " + str(comsize_m))
                            #----size constraints.
                            #if it's not within size constaints - dump it now and save some time.
                            if mylar.CONFIG.USE_MINSIZE:
                                conv_minsize = helpers.human2bytes(mylar.CONFIG.MINSIZE + "M")
                                logger.fdebug("comparing Min threshold " + str(conv_minsize) + " .. to .. nzb " + str(comsize_b))
                                if int(conv_minsize) > int(comsize_b):
                                    logger.fdebug("Failure to meet the Minimum size threshold - skipping")
                                    continue
                            if mylar.CONFIG.USE_MAXSIZE:
                                conv_maxsize = helpers.human2bytes(mylar.CONFIG.MAXSIZE + "M")
                                logger.fdebug("comparing Max threshold " + str(conv_maxsize) + " .. to .. nzb " + str(comsize_b))
                                if int(comsize_b) > int(conv_maxsize):
                                    logger.fdebug("Failure to meet the Maximium size threshold - skipping")
                                    continue

#---- date constaints.
                # if the posting date is prior to the publication date, dump it and save the time.
                #logger.fdebug('entry: %s' % entry)
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

                    postdate_int = None
                    if nzbprov == '32P' and RSS == 'no':
                        postdate_int = pubdate
                    if any([postdate_int is None, type(postdate_int) != int]) or not all([nzbprov == '32P', RSS == 'no']):
                        # convert it to a tuple
                        dateconv = email.utils.parsedate_tz(pubdate)
                        if all([nzbprov == '32P', dateconv is None, RSS == 'no']):
                            try:
                                pubdate = email.utils.formatdate(entry['int_pubdate'], localtime=True, usegmt=False)
                            except:
                                logger.warn('Unable to parsedate to a long-date that I can undestand : %s' % entry['int_pubdate'])
                            else:
                                logger.fdebug('Successfully converted to : %s' % pubdate)
                                dateconv = email.utils.parsedate_tz(pubdate)

                        try:
                            dateconv2 = datetime.datetime(*dateconv[:6])
                        except TypeError as e:
                            logger.warn('Unable to convert timestamp from : %s [%s]' % ((dateconv,), e))
                        try:
                            # convert it to a numeric time, then subtract the timezone difference (+/- GMT)
                            if dateconv[-1] is not None:
                                postdate_int = time.mktime(dateconv[:len(dateconv) -1]) - dateconv[-1]
                            else:
                                postdate_int = time.mktime(dateconv[:len(dateconv) -1])
                        except:
                            logger.warn('Unable to parse posting date from provider result set for :' + entry['title'])
                            continue

                    #convert it to a Thu, 06 Feb 2014 00:00:00 format
                    issue_converted = datetime.datetime.strptime(stdate.rstrip(), '%Y-%m-%d')
                    issue_convert = issue_converted + datetime.timedelta(days=-1)
                    # to get past different locale's os-dependent dates, let's convert it to a generic datetime format
                    try:
                        stamp = time.mktime(issue_convert.timetuple())
                        issconv = format_date_time(stamp)
                    except OverflowError:
                        logger.fdebug('Error attempting to convert the timestamp into a generic format. Probably due to the epoch limiation.')
                        issconv = issue_convert.strftime('%a, %d %b %Y %H:%M:%S')
                    #convert it to a tuple
                    econv = email.utils.parsedate_tz(issconv)
                    econv2 = datetime.datetime(*econv[:6])
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
                    try:
                        #try new method to get around issues populating in a diff timezone thereby putting them in a different day.
                        if dateconv2.date() < econv2.date():
                            logger.fdebug('[CONV]pubdate: %s  < storedate: %s' % (dateconv2.date(), econv2.date()))
                            logger.fdebug(str(pubdate) + ' is before store date of ' + str(stdate) + '. Ignoring search result as this is not the right issue.')
                            continue
                        else:
                            logger.fdebug(str(pubdate) + ' is after store date of ' + str(stdate))
                    except:
                        #if the above fails, drop down to the integer compare method as a failsafe.
                        if postdate_int < issuedate_int:
                            logger.fdebug('[INT]pubdate: %s  < storedate: %s' % (postdate_int, issuedate_int))
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
                # handle escaped and/or possibly double escaped ampersands as well.
                # 'the' is removed for comparisons later on
                if '&' in cleantitle: cleantitle = re.sub('\&amp;(amp;)?|\&', 'and', cleantitle)

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
                origvol = None
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
                                for i in ctchk_indexes:
                                    if i not in vol_nono:
                                        new_cleantitle.append(ctchk[i])
                                cleantitle = ' '.join(new_cleantitle)
                                logger.fdebug('Newly finished reformed cleantitle (with NO volume label): ' + cleantitle)
                                volfound == False
                        tmpsplit = ct
                        if tmpsplit.lower().startswith('vol'):
                            logger.fdebug('volume detected - stripping and re-analzying for volume label.')
                            origvol = tmpsplit
                            if '.' in tmpsplit:
                                tmpsplit = re.sub('.', '', tmpsplit).strip()
                            tmpsplit = re.sub('vol', '', tmpsplit.lower()).strip()
                            #if vol label set as 'Vol 4' it will obliterate the Vol, but pass over the '4' - set
                            #volfound to True so that it can loop back around.
                            if not tmpsplit.isdigit():
                                #vol_label = ct  #store the wording of how the Vol is defined so we can skip it later on.
                                vol_nono.append(ctchk.index(ct))
                                volfound = True
                                origvol = None
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
                        if origvol:
                            cleantitle = re.sub(origvol, '', cleantitle).strip()
                        else:
                            cleantitle = re.sub(fndcomicversion, '', cleantitle).strip()
                        logger.fdebug('Newly finished reformed cleantitle (with NO volume label): ' + cleantitle)
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
                        publisher_search = Publisher
                        publisher_removelist = {'Entertainment', 'Press', 'Comics', 'Publishing', 'Comix', 'Studios!'}
                        spl = [x for x in publisher_removelist if x in publisher_search]
                        for x in spl:
                            publisher_search = re.sub(x, '', publisher_search).strip()

                        if publisher_search.lower() in m[cnt].lower() and cnt >= 1:
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

                annualize = "false"
                if 'annual' in ComicName.lower():
                    logger.fdebug("IssueID of : " + str(IssueID) + " - This is an annual...let's adjust.")
                    annualize = "true"
                if versionfound == "yes":
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
                       #need to convert dates to just be yyyy-mm-dd and do comparison, time operator in the below calc as well which probably throws off$
                        F_ComicVersion = '1'
                        if postdate_int is not None:
                            if postdate_int >= issuedate_int and nzbprov == '32P':
                                logger.fdebug('32P torrent discovery. Posting date (' + str(pubdate) + ') is after store date (' + str(stdate) + '), forcing volume label to be the same as series label (0-Day Enforcement): v' + str(F_ComicVersion) + ' --> v' + str(S_ComicVersion))
                                F_ComicVersion = D_ComicVersion

                    logger.fdebug("FCVersion: " + str(F_ComicVersion))
                    logger.fdebug("DCVersion: " + str(D_ComicVersion))
                    logger.fdebug("SCVersion: " + str(S_ComicVersion))

                    #here's the catch, sometimes annuals get posted as the Pub Year
                    # instead of the Series they belong to (V2012 vs V2013)
                    if annualize == "true" and int(ComicYear) == int(F_ComicVersion):
                        logger.fdebug("We matched on versions for annuals " + str(fndcomicversion))
                    elif int(F_ComicVersion) == int(D_ComicVersion) or int(F_ComicVersion) == int(S_ComicVersion):
                        logger.fdebug("We matched on versions..." + str(fndcomicversion))
                    else:
                        logger.fdebug("Versions wrong. Ignoring possible match.")
                        continue

                downloadit = False
#-------------------------------------fix this!
                if nzbprov == 'Public Torrents' and any([entry['site'] == 'WWT', entry['site'] == 'DEM']):
                    if entry['site'] == 'WWT':
                        nzbprov = 'WWT'
                    else:
                        nzbprov = 'DEM'

                if all([nzbprov == '32P', allow_packs == True, RSS == 'no']):
                    logger.fdebug('pack:' + entry['pack'])
                if all([nzbprov == '32P', RSS == 'no', allow_packs == True]) and any([entry['pack'] == '1', entry['pack'] == '2']):
                    if nzbprov == '32P':
                        if entry['pack'] == '2':
                            logger.fdebug('[PACK-QUEUE] Diamond FreeLeech Pack detected.')
                        elif entry['pack'] == '1':
                            logger.fdebug('[PACK-QUEUE] Normal Pack detected. Checking available inkdrops prior to downloading.')
                        else:
                            logger.fdebug('[PACK-QUEUE] Invalid Pack.')

                        #find the pack range.
                        pack_issuelist = None
                        issueid_info = None
                        if not entry['title'].startswith('0-Day Comics Pack'):
                            pack_issuelist = entry['issues']
                            issueid_info = helpers.issue_find_ids(ComicName, ComicID, pack_issuelist, IssueNumber)
                            if issueid_info['valid'] == True:
                                logger.info('Issue Number ' + IssueNumber + ' exists within pack. Continuing.')
                            else:
                                logger.fdebug('Issue Number ' + IssueNumber + ' does NOT exist within this pack. Skipping')
                                continue
                    #pack support.
                    nowrite = False
                    nzbid = generate_id(nzbprov, entry['link'])
                    if manual is not True:
                        downloadit = True
                    else:
                        for x in mylar.COMICINFO:
                            if all([x['link'] == entry['link'], x['tmpprov'] == tmpprov]) or all([x['nzbid'] == nzbid, x['newznab'] == newznab_host]) or all([x['nzbid'] == nzbid, x['torznab'] == torznab_host]):
                                nowrite = True
                                break

                    if nowrite is False:
                        if any([nzbprov == 'dognzb', nzbprov == 'nzb.su', nzbprov == 'experimental', 'newznab' in nzbprov]):
                            tprov = nzbprov
                            kind = 'usenet'
                            if newznab_host is not None:
                                tprov = newznab_host[0]
                        else:
                            tprov = nzbprov
                            kind = 'torrent'
                            if torznab_host is not None:
                                tprov = torznab_host[0]
                        mylar.COMICINFO.append({"ComicName":       ComicName,
                                          "ComicID":         ComicID,
                                          "IssueID":         IssueID,
                                          "ComicVolume":     ComicVersion,
                                          "IssueNumber":     IssueNumber,
                                          "IssueDate":       IssueDate,
                                          "comyear":         comyear,
                                          "pack":            True,
                                          "pack_numbers":    pack_issuelist,
                                          "pack_issuelist":  issueid_info,
                                          "modcomicname":    entry['title'],
                                          "oneoff":          oneoff,
                                          "nzbprov":         nzbprov,
                                          "nzbtitle":        entry['title'],
                                          "nzbid":           nzbid,
                                          "provider":        tprov,
                                          "link":            entry['link'],
                                          "size":            comsize_m,
                                          "tmpprov":         tmpprov,
                                          "kind":            kind,
                                          "SARC":            SARC,
                                          "IssueArcID":      IssueArcID,
                                          "newznab":         newznab_host,
                                          "torznab":         torznab_host})


                else:
                    splitit = []
                    watchcomic_split = []
                    logger.fdebug("original nzb comic and issue: " + str(comic_andiss))
                    #scan the returned name to see if it contains a '-', which typically denotes the start of an issuetitle
                    #if the series doesn't have a '-' within it.
                    hyphensplit = None
                    hyphenfail = False
                    issue_firstword = None
                    #issue_pack = None
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
                                #test for packs here as they will be like #1-20, #1-7.3, 1-20+Annuals
                                #thisentry = Fear Itself vol0 #1-7.3
                                #if '#' in thisentry:
                                #    issue_pack_startpos = thisentry.find('#') + 1 #(take first digit after dash)
                                #    issue_pack_dash = hyphensplit[1] #this should be the end of the pack sequence
                                #    issue_pack_endpos = thisentry.find('-', issue_pack_startpos)
                                #    issue_pack_start = thisentry[issue_pack_startpos:issue_pack_endpos]
                                #    if thisentry.find(' ', issue_pack_endpos) == -1:
                                #        endit = len(thisentry)
                                #    else:
                                #        endit = thisentry.find(' ', issue_pack_endpos)
                                #    issue_pack_end = thisentry[issue_pack_endpos+1:endit].strip()
                                #    if issue_pack_start.isdigit():
                                #        logger.fdebug('first position prior to hyphen is digit [' + str(issue_pack_start) + ']')
                                #        try:
                                #            float(issue_pack_end)
                                #        except:
                                #            pass
                                #        else:
                                #            issue_pack = str(issue_pack_start) + '-' + str(issue_pack_end)
                                #            logger.info('This should be a pack: ' + issue_pack)

                                #if issue_pack is None:
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

                    if comic_iss is None or comic_iss == '':
                        continue

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
                    scount = 0

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
                            nowrite = False
                            if nzbprov == 'torznab' and 'worldwidetorrents' in entry['link']:
                                nzbid = generate_id(nzbprov, entry['id'])
                            else:
                                nzbid = generate_id(nzbprov, entry['link'])
                            if manual is not True:
                                downloadit = True
                            else:
                                for x in mylar.COMICINFO:
                                    if all([x['link'] == entry['link'], x['tmpprov'] == tmpprov]) or all([x['nzbid'] == nzbid, x['newznab'] == newznab_host]) or all([x['nzbid'] == nzbid, x['torznab'] == torznab_host]):
                                        nowrite = True
                                        break

                            #modify the name for annualization to be displayed properly
                            if annualize == True:
                                modcomicname = ComicName + ' Annual'
                            else:
                                modcomicname = ComicName


                            #comicinfo = []
                            if IssueID is None:
                                cyear = ComicYear
                            else:
                                cyear = comyear

                            if nowrite is False:
                                if any([nzbprov == 'dognzb', nzbprov == 'nzb.su', nzbprov == 'experimental', 'newznab' in nzbprov]):
                                    tprov = nzbprov
                                    kind = 'usenet'
                                    if newznab_host is not None:
                                        tprov = newznab_host[0]
                                else:
                                    kind = 'torrent'
                                    tprov = nzbprov
                                    if torznab_host is not None:
                                        tprov = torznab_host[0]

                                mylar.COMICINFO.append({"ComicName":      ComicName,
                                                  "ComicID":        ComicID,
                                                  "IssueID":        IssueID,
                                                  "ComicVolume":    ComicVersion,
                                                  "IssueNumber":    IssueNumber,
                                                  "IssueDate":      IssueDate,
                                                  "comyear":        cyear,
                                                  "pack":           False,
                                                  "pack_numbers":   None,
                                                  "pack_issuelist": None,
                                                  "modcomicname":   modcomicname,
                                                  "oneoff":         oneoff,
                                                  "nzbprov":        nzbprov,
                                                  "provider":       tprov,
                                                  "nzbtitle":       entry['title'],
                                                  "nzbid":          nzbid,
                                                  "link":           entry['link'],
                                                  "size":           comsize_m,
                                                  "tmpprov":        tmpprov,
                                                  "kind":           kind,
                                                  "SARC":           SARC,
                                                  "IssueArcID":     IssueArcID,
                                                  "newznab":        newznab_host,
                                                  "torznab":        torznab_host})
                        else:
                            log2file = log2file + "issues don't match.." + "\n"
                            downloadit = False
                            foundc['status'] = False

                if downloadit:
                    try:
                        if entry['chkit']:
                            helpers.checkthe_id(ComicID, entry['chkit'])
                    except:
                        pass

                    #generate nzbname
                    nzbname = nzbname_create(nzbprov, info=mylar.COMICINFO, title=ComicTitle) #entry['title'])
                    if nzbname is None:
                        logger.error('[NZBPROVIDER = NONE] Encountered an error using given provider with requested information: ' + mylar.COMICINFO + '. You have a blank entry most likely in your newznabs, fix it & restart Mylar')
                        continue
                    #generate the send-to and actually send the nzb / torrent.
                    #logger.info('entry: %s' % entry)
                    try:
                        links = {'id': entry['id'],
                                 'link': entry['link']}
                    except:
                        links = entry['link']
                    searchresult = searcher(nzbprov, nzbname, mylar.COMICINFO, links, IssueID, ComicID, tmpprov, newznab=newznab_host, torznab=torznab_host)

                    if searchresult == 'downloadchk-fail':
                        foundc['status'] = False
                        continue
                    elif searchresult == 'torrent-fail' or searchresult == 'nzbget-fail' or searchresult == 'sab-fail' or searchresult == 'blackhole-fail':
                        foundc['status'] = False
                        return foundc

                    #nzbid, nzbname, sent_to
                    nzbid = searchresult['nzbid']
                    nzbname = searchresult['nzbname']
                    sent_to = searchresult['sent_to']
                    alt_nzbname = searchresult['alt_nzbname']
                    t_hash = searchresult['t_hash']
                    if searchresult['SARC'] is not None:
                        SARC = searchresult['SARC']
                    foundc['info'] = searchresult
                    foundc['status'] = True
                    done = True
                    break

                if done == True:
                    #cmloopit == 1 #let's make sure it STOPS searching after a sucessful match.
                    break
        #cmloopit-=1
        #if cmloopit < 1 and c_alpha is not None and seperatealpha == "no" and foundc['status'] is False:
        #    logger.info("Alphanumerics detected within IssueNumber. Seperating from Issue # and re-trying.")
        #    cmloopit = origcmloopit
        #    seperatealpha = "yes"

        findloop+=1

    if foundc['status'] is True:
        if 'Public Torrents' in tmpprov and any([nzbprov == 'WWT', nzbprov == 'DEM']):
            tmpprov = re.sub('Public Torrents', nzbprov, tmpprov)
        foundcomic.append("yes")
        if mylar.COMICINFO[0]['pack']:
            issinfo = mylar.COMICINFO[0]['pack_issuelist']
            if issinfo is not None:
                #we need to get EVERY issue ID within the pack and update the log to reflect that they're being downloaded via a pack.
                logger.fdebug("Found matching comic within pack...preparing to send to Updater with IssueIDs: " + str(issueid_info) + " and nzbname of " + str(nzbname))
                #because packs need to have every issue that's not already Downloaded in a Snatched status, throw it to the updater here as well.
                for isid in issinfo['issues']:
                    updater.nzblog(isid['issueid'], nzbname, ComicName, SARC=SARC, IssueArcID=IssueArcID, id=nzbid, prov=tmpprov, oneoff=oneoff)
                    updater.foundsearch(ComicID, isid['issueid'], mode='series', provider=tmpprov)
                notify_snatch(nzbname, sent_to, mylar.COMICINFO[0]['modcomicname'], mylar.COMICINFO[0]['comyear'], mylar.COMICINFO[0]['pack_numbers'], nzbprov)
            else:
                notify_snatch(nzbname, sent_to, mylar.COMICINFO[0]['modcomicname'], mylar.COMICINFO[0]['comyear'], None, nzbprov)

        else:
            if alt_nzbname is None or alt_nzbname == '':
                logger.fdebug("Found matching comic...preparing to send to Updater with IssueID: " + str(IssueID) + " and nzbname: " + str(nzbname))
                if '[RSS]' in tmpprov: tmpprov = re.sub('\[RSS\]', '', tmpprov).strip()
                updater.nzblog(IssueID, nzbname, ComicName, SARC=SARC, IssueArcID=IssueArcID, id=nzbid, prov=tmpprov, oneoff=oneoff)
            else:
                logger.fdebug("Found matching comic...preparing to send to Updater with IssueID: " + str(IssueID) + " and nzbname: " + str(nzbname) + '[' + alt_nzbname + ']')
                if '[RSS]' in tmpprov: tmpprov = re.sub('\[RSS\]', '', tmpprov).strip()
                updater.nzblog(IssueID, nzbname, ComicName, SARC=SARC, IssueArcID=IssueArcID, id=nzbid, prov=tmpprov, alt_nzbname=alt_nzbname, oneoff=oneoff)
            #send out the notifications for the snatch.
            if any([oneoff is True, IssueID is None]):
                cyear = ComicYear
            else:
                cyear = comyear
            notify_snatch(nzbname, sent_to, helpers.filesafe(modcomicname), cyear, IssueNumber, nzbprov)
        prov_count == 0
        mylar.TMP_PROV = nzbprov

        #if mylar.SAB_PARAMS is not None:
        #    #should be threaded....
        #    ss = sabnzbd.SABnzbd(mylar.SAB_PARAMS)
        #    sendtosab = ss.sender()
        #    if all([sendtosab['status'] is True, mylar.CONFIG.SAB_CLIENT_POST_PROCESSING is True]):
        #        mylar.NZB_QUEUE.put(sendtosab)
        return foundc

    else:
        #logger.fdebug('prov_count: ' + str(prov_count))
        foundcomic.append("no")
        #if IssDateFix == "no":
            #logger.info('Could not find Issue ' + str(IssueNumber) + ' of ' + ComicName + '(' + str(comyear) + ') using ' + str(tmpprov) + '. Status kept as wanted.' )
            #break
    return foundc

def searchforissue(issueid=None, new=False, rsscheck=None, manual=False):

    myDB = db.DBConnection()

    ens = [x for x in mylar.CONFIG.EXTRA_NEWZNABS if x[5] == '1']
    ets = [x for x in mylar.CONFIG.EXTRA_TORZNABS if x[4] == '1']
    if (any([mylar.CONFIG.NZBSU is True, mylar.CONFIG.DOGNZB is True, mylar.CONFIG.EXPERIMENTAL is True]) or all([mylar.CONFIG.NEWZNAB is True, len(ens) > 0]) and any([mylar.USE_SABNZBD is True, mylar.USE_NZBGET is True, mylar.USE_BLACKHOLE is True])) or (all([mylar.CONFIG.ENABLE_TORRENT_SEARCH is True, mylar.CONFIG.ENABLE_TORRENTS is True]) and (any([mylar.CONFIG.ENABLE_PUBLIC is True, mylar.CONFIG.ENABLE_32P is True]) or all([mylar.CONFIG.ENABLE_TORZNAB is True, len(ets) > 0]))):
        if not issueid or rsscheck:

            if rsscheck:
                logger.info(u"Initiating RSS Search Scan at the scheduled interval of " + str(mylar.CONFIG.RSS_CHECKINTERVAL) + " minutes.")
            else:
                logger.info(u"Initiating Search scan at the scheduled interval of " + str(mylar.CONFIG.SEARCH_INTERVAL) + " minutes.")

            myDB = db.DBConnection()

            stloop = 2   # 2 levels - one for issues, one for storyarcs - additional for annuals below if enabled
            results = []

            if mylar.CONFIG.ANNUALS_ON:
                stloop+=1
            while (stloop > 0):
                if stloop == 1:
                    if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING and mylar.CONFIG.FAILED_AUTO:
                        issues_1 = myDB.select('SELECT * from issues WHERE Status="Wanted" OR Status="Failed"')
                    else:
                        issues_1 = myDB.select('SELECT * from issues WHERE Status="Wanted"')
                    for iss in issues_1:
                        results.append({'ComicID':       iss['ComicID'],
                                        'IssueID':       iss['IssueID'],
                                        'Issue_Number':  iss['Issue_Number'],
                                        'IssueDate':     iss['IssueDate'],
                                        'StoreDate':     iss['ReleaseDate'],
                                        'SARC':          None,
                                        'StoryArcID':    None,
                                        'IssueArcID':    None,
                                        'mode':          'want'
                                       })
                elif stloop == 2:
                    if mylar.CONFIG.SEARCH_STORYARCS is True or rsscheck:
                        if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING and mylar.CONFIG.FAILED_AUTO:
                           issues_2 = myDB.select('SELECT * from storyarcs WHERE Status="Wanted" OR Status="Failed"')
                        else:
                           issues_2 = myDB.select('SELECT * from storyarcs WHERE Status="Wanted"')
                        cnt=0
                        for iss in issues_2:
                            results.append({'ComicID':       iss['ComicID'],
                                            'IssueID':       iss['IssueID'],
                                            'Issue_Number':  iss['IssueNumber'],
                                            'IssueDate':     iss['IssueDate'],
                                            'StoreDate':     iss['ReleaseDate'],
                                            'SARC':          iss['StoryArc'],
                                            'StoryArcID':    iss['StoryArcID'],
                                            'IssueArcID':    iss['IssueArcID'],
                                            'mode':          'story_arc'
                                           })
                            cnt+=1
                        logger.info('Storyarcs to be searched for : %s' % cnt)
                elif stloop == 3:
                    if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING and mylar.CONFIG.FAILED_AUTO:
                        issues_3 = myDB.select('SELECT * from annuals WHERE Status="Wanted" OR Status="Failed"')
                    else:
                        issues_3 = myDB.select('SELECT * from annuals WHERE Status="Wanted"')
                    for iss in issues_3:
                        results.append({'ComicID':       iss['ComicID'],
                                        'IssueID':       iss['IssueID'],
                                        'Issue_Number':  iss['Issue_Number'],
                                        'IssueDate':     iss['IssueDate'],
                                        'StoreDate':     iss['ReleaseDate'],   #need to replace with Store date
                                        'SARC':          None,
                                        'StoryArcID':    None,
                                        'IssueArcID':    None,
                                        'mode':          'want_ann'
                                       })
                stloop-=1

            new = True
            #to-do: re-order the results list so it's most recent to least recent.

            for result in sorted(results, key=itemgetter('StoreDate'), reverse=True):
                logger.info('result: %s' % result)
                OneOff = False
                storyarc_watchlist = False
                comic = myDB.selectone("SELECT * from comics WHERE ComicID=? AND ComicName != 'None'", [result['ComicID']]).fetchone()
                if all([comic is None, result['mode'] == 'story_arc']):
                    comic = myDB.selectone("SELECT * from storyarcs WHERE StoryArcID=? AND IssueArcID=?", [result['StoryArcID'],result['IssueArcID']]).fetchone() 
                    if comic is None:
                        logger.fdebug(str(result['ComicID']) + ' has no associated comic information in the Arc. Skipping searching for this series.')
                        continue
                    else:
                        logger.info('comic: %s' % comic)
                        OneOff = True
                elif comic is None:
                    logger.fdebug(str(result['ComicID']) + ' has no associated comic information in the Arc. Skipping searching for this series.')
                    continue
                else:
                    storyarc_watchlist = True
                if result['StoreDate'] == '0000-00-00' or result['StoreDate'] is None:
                    if result['IssueDate'] is None or result['IssueDate'] == '0000-00-00':
                        logger.fdebug('ComicID: ' + str(result['ComicID']) + ' has invalid Date data. Skipping searching for this series.')
                        continue

                #status issue check - check status to see if it's Downloaded / Snatched already due to concurrent searches possible.
                if result['IssueID'] is not None:
                    if result['mode'] == 'story_arc':
                        isscheck = helpers.issue_status(result['IssueArcID'])
                    else:
                        isscheck = helpers.issue_status(result['IssueID'])
                    #isscheck will return True if already Downloaded / Snatched, False if it's still in a Wanted status.
                    if isscheck is True:
                        logger.fdebug('Issue is already in a Downloaded / Snatched status.')
                        continue
                else:
                    logger.warn('Unable to locate valid IssueID. Ignoring search request at this time...')
                    continue

                foundNZB = "none"
                AllowPacks = False
                if all([result['mode'] == 'story_arc', storyarc_watchlist is False]):
                    Comicname_filesafe = helpers.filesafe(comic['ComicName'])
                    SeriesYear = comic['SeriesYear']
                    Publisher = comic['Publisher']
                    AlternateSearch = None
                    UseFuzzy = None
                    ComicVersion = comic['Volume']
                    TorrentID_32p = None
                else:
                    Comicname_filesafe = comic['ComicName_Filesafe']
                    SeriesYear = comic['ComicYear']
                    Publisher = comic['ComicPublisher']
                    AlternateSearch = comic['AlternateSearch']
                    UseFuzzy = comic['UseFuzzy']
                    ComicVersion = comic['ComicVersion']
                    TorrentID_32p = comic['TorrentID_32P']
                    if any([comic['AllowPacks'] == 1, comic['AllowPacks'] == '1']):
                        AllowPacks = True

                IssueDate = result['IssueDate']
                StoreDate = result['StoreDate']

                if result['IssueDate'] is None:
                    ComicYear = SeriesYear
                else:
                    ComicYear = str(result['IssueDate'])[:4]

                mode = result['mode']
                foundNZB, prov = search_init(comic['ComicName'], result['Issue_Number'], str(ComicYear), SeriesYear, Publisher, IssueDate, StoreDate, result['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, SARC=result['SARC'], IssueArcID=result['IssueArcID'], mode=mode, rsscheck=rsscheck, ComicID=result['ComicID'], filesafe=Comicname_filesafe, allow_packs=AllowPacks, oneoff=OneOff, torrentid_32p=TorrentID_32p)
                if foundNZB['status'] is True:
                    #logger.info(foundNZB)
                    updater.foundsearch(result['ComicID'], result['IssueID'], mode=mode, provider=prov, SARC=result['SARC'], IssueArcID=result['IssueArcID'], hash=foundNZB['info']['t_hash'])

            if rsscheck:
                logger.info('Completed RSS Search scan')
            else:
                logger.info('Completed API Search scan')


        else:
            result = myDB.selectone('SELECT * FROM issues where IssueID=?', [issueid]).fetchone()
            mode = 'want'
            oneoff = False
            if result is None:
                result = myDB.selectone('SELECT * FROM annuals where IssueID=?', [issueid]).fetchone()
                mode = 'want_ann'
                if result is None:
                    result = myDB.selectone('SELECT * FROM storyarcs where IssueArcID=?', [issueid]).fetchone()
                    mode = 'story_arc'
                    oneoff = True
                    if result is None:
                        logger.fdebug("Unable to locate IssueID - you probably should delete/refresh the series.")
                        return

            allow_packs = False
            ComicID = result['ComicID']
            if mode == 'story_arc':
                    ComicName = result['ComicName']
                    Comicname_filesafe = helpers.filesafe(ComicName)
                    SeriesYear = result['SeriesYear']
                    IssueNumber = result['IssueNumber']
                    Publisher = result['Publisher']
                    AlternateSearch = None
                    UseFuzzy = None
                    ComicVersion = result['Volume']
                    SARC = result['StoryArc']
                    IssueArcID = issueid
                    actissueid = None
                    TorrentID_32p = None
            else:
                comic = myDB.selectone('SELECT * FROM comics where ComicID=?', [ComicID]).fetchone()
                Comicname_filesafe = comic['ComicName_Filesafe']
                ComicName = comic['ComicName']
                SeriesYear = comic['ComicYear']
                IssueNumber = result['Issue_Number']
                Publisher = comic['ComicPublisher']
                AlternateSearch = comic['AlternateSearch']
                UseFuzzy = comic['UseFuzzy']
                ComicVersion = comic['ComicVersion']
                SARC = None
                IssueArcID = None
                actissueid = issueid
                TorrentID_32p = comic['TorrentID_32P']
                if any([comic['AllowPacks'] == 1, comic['AllowPacks'] == '1']):
                    allow_packs = True

            IssueDate = result['IssueDate']
            StoreDate = result['ReleaseDate']

            if result['IssueDate'] == None:
                IssueYear = SeriesYear
            else:
                IssueYear = str(result['IssueDate'])[:4]

            foundNZB, prov = search_init(ComicName, IssueNumber, str(IssueYear), SeriesYear, Publisher, IssueDate, StoreDate, actissueid, AlternateSearch, UseFuzzy, ComicVersion, SARC=SARC, IssueArcID=IssueArcID, mode=mode, rsscheck=rsscheck, ComicID=ComicID, filesafe=Comicname_filesafe, allow_packs=allow_packs, oneoff=oneoff, manual=manual, torrentid_32p=TorrentID_32p)
            if manual is True:
                return foundNZB
            if foundNZB['status'] is True:
                logger.fdebug("I found " + comic['ComicName'] + ' #:' + str(result['Issue_Number']))
                updater.foundsearch(result['ComicID'], result['IssueID'], mode=mode, provider=prov, SARC=result['SARC'], IssueArcID=result['IssueArcID'], hash=foundNZB['info']['t_hash'])

    else:
        if rsscheck:
            logger.warn('There are no search providers enabled atm - not performing an RSS check for obvious reasons')
        else:
            logger.warn('There are no search providers enabled atm - not performing an Force Check for obvious reasons')
    return

def searchIssueIDList(issuelist):
    myDB = db.DBConnection()
    ens = [x for x in mylar.CONFIG.EXTRA_NEWZNABS if x[5] == '1']
    ets = [x for x in mylar.CONFIG.EXTRA_TORZNABS if x[4] == '1']
    if (any([mylar.CONFIG.NZBSU is True, mylar.CONFIG.DOGNZB is True, mylar.CONFIG.EXPERIMENTAL is True]) or all([mylar.CONFIG.NEWZNAB is True, len(ens) > 0]) and any([mylar.USE_SABNZBD is True, mylar.USE_NZBGET is True, mylar.USE_BLACKHOLE is True])) or (all([mylar.CONFIG.ENABLE_TORRENT_SEARCH is True, mylar.CONFIG.ENABLE_TORRENTS is True]) and (any([mylar.CONFIG.ENABLE_PUBLIC is True, mylar.CONFIG.ENABLE_32P is True]) or all([mylar.CONFIG.NEWZNAB is True, len(ets) > 0]))):
        for issueid in issuelist:
            logger.info('searching for issueid: %s' % issueid)
            issue = myDB.selectone('SELECT * from issues WHERE IssueID=?', [issueid]).fetchone()
            mode = 'want'
            if issue is None:
                issue = myDB.selectone('SELECT * from annuals WHERE IssueID=?', [issueid]).fetchone()
                mode = 'want_ann'
                if issue is None:
                    logger.warn('unable to determine IssueID - perhaps you need to delete/refresh series? Skipping this entry: ' + issueid)
                    continue

            if any([issue['Status'] == 'Downloaded', issue['Status'] == 'Snatched']):
                logger.fdebug('Issue is already in a Downloaded / Snatched status.')
                continue

            comic = myDB.selectone('SELECT * from comics WHERE ComicID=?', [issue['ComicID']]).fetchone()
            foundNZB = "none"
            SeriesYear = comic['ComicYear']
            AlternateSearch = comic['AlternateSearch']
            Publisher = comic['ComicPublisher']
            UseFuzzy = comic['UseFuzzy']
            ComicVersion = comic['ComicVersion']
            TorrentID_32p = comic['TorrentID_32P']
            if issue['IssueDate'] == None:
                IssueYear = comic['ComicYear']
            else:
                IssueYear = str(issue['IssueDate'])[:4]
            if any([comic['AllowPacks'] == 1, comic['AllowPacks'] == '1']):
                AllowPacks = True
            else:
                AllowPacks = False

            foundNZB, prov = search_init(comic['ComicName'], issue['Issue_Number'], str(IssueYear), comic['ComicYear'], Publisher, issue['IssueDate'], issue['ReleaseDate'], issue['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, SARC=None, IssueArcID=None, mode=mode, ComicID=issue['ComicID'], filesafe=comic['ComicName_Filesafe'], allow_packs=AllowPacks, torrentid_32p=TorrentID_32p)
            if foundNZB['status'] is True:
                updater.foundsearch(ComicID=issue['ComicID'], IssueID=issue['IssueID'], mode=mode, provider=prov, hash=foundNZB['info']['t_hash'])
        logger.info('Completed search request.')
    else:
        logger.warn('There are no search providers enabled atm - not performing the requested search for obvious reasons')


def provider_sequence(nzbprovider, torprovider, newznab_hosts, torznab_hosts):
    #provider order sequencing here.
    newznab_info = []
    torznab_info = []
    prov_order = []

    nzbproviders_lower = [x.lower() for x in nzbprovider]
    torproviders_lower = [y.lower() for y in torprovider]

    if len(mylar.CONFIG.PROVIDER_ORDER) > 0:
        for pr_order in sorted(mylar.CONFIG.PROVIDER_ORDER.items(), key=itemgetter(0), reverse=False):
            if any(pr_order[1].lower() in y for y in torproviders_lower) or any(pr_order[1].lower() in x for x in nzbproviders_lower):
                if any(pr_order[1].lower() in x for x in nzbproviders_lower):
                    # this is for nzb providers
                    for np in nzbprovider:
                        if all(['newznab' in np, pr_order[1].lower() in np.lower()]):
                            for newznab_host in newznab_hosts:
                                if newznab_host[0].lower() == pr_order[1].lower():
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
                elif any(pr_order[1].lower() in y for y in torproviders_lower):
                    for tp in torprovider:
                        if all(['torznab' in tp, pr_order[1].lower() in tp.lower()]):
                            for torznab_host in torznab_hosts:
                                if torznab_host[0].lower() == pr_order[1].lower():
                                    prov_order.append(tp)
                                    torznab_info.append({"provider":     tp,
                                                         "info": torznab_host})
                                    break
                                else:
                                    if torznab_host[0] == "":
                                        if torznab_host[1].lower() == pr_order[1].lower():
                                            prov_order.append(tp)
                                            torznab_info.append({"provider":     tp,
                                                                 "info": torznab_host})
                                            break
                        elif (pr_order[1].lower() in tp.lower()):
                            prov_order.append(pr_order[1])
                            break

    return prov_order, torznab_info, newznab_info

def nzbname_create(provider, title=None, info=None):
    #the nzbname here is used when post-processing
    # it searches nzblog which contains the nzbname to pull out the IssueID and start the post-processing
    # it is also used to keep the hashinfo for the nzbname in case it fails downloading, it will get put into the failed db for future exclusions
    nzbname = None

    if mylar.USE_BLACKHOLE and all([provider != '32P', provider != 'WWT', provider != 'DEM']):
        if os.path.exists(mylar.CONFIG.BLACKHOLE_DIR):
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

    elif any([provider == '32P', provider == 'WWT', provider == 'DEM']):
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
        nzbname = re.sub('\&amp;(amp;)?|\&', 'and', title)
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

    if nzbname is None:
        return None
    else:
        logger.fdebug("nzbname used for post-processing:" + nzbname)
        return nzbname

def searcher(nzbprov, nzbname, comicinfo, link, IssueID, ComicID, tmpprov, directsend=None, newznab=None, torznab=None):
    alt_nzbname = None
    #load in the details of the issue from the tuple.
    ComicName = comicinfo[0]['ComicName']
    IssueNumber = comicinfo[0]['IssueNumber']
    comyear = comicinfo[0]['comyear']
    modcomicname = comicinfo[0]['modcomicname']
    oneoff = comicinfo[0]['oneoff']
    try:
       SARC = comicinfo[0]['SARC']
    except:
       SARC = None
    try:
       IssueArcID = comicinfo[0]['IssueArcID']
    except:
       IssueArcID = None

    #setup the priorities.
    if mylar.CONFIG.SAB_PRIORITY:
        if mylar.CONFIG.SAB_PRIORITY == "Default": sabpriority = "-100"
        elif mylar.CONFIG.SAB_PRIORITY == "Low": sabpriority = "-1"
        elif mylar.CONFIG.SAB_PRIORITY == "Normal": sabpriority = "0"
        elif mylar.CONFIG.SAB_PRIORITY == "High": sabpriority = "1"
        elif mylar.CONFIG.SAB_PRIORITY == "Paused": sabpriority = "-2"
    else:
        #if sab priority isn't selected, default to Normal (0)
        sabpriority = "0"

    if mylar.CONFIG.NZBGET_PRIORITY:
        if mylar.CONFIG.NZBGET_PRIORITY == "Default": nzbgetpriority = "0"
        elif mylar.CONFIG.NZBGET_PRIORITY == "Low": nzbgetpriority = "-50"
        elif mylar.CONFIG.NZBGET_PRIORITY == "Normal": nzbgetpriority = "0"
        elif mylar.CONFIG.NZBGET_PRIORITY == "High": nzbgetpriority = "50"
        #there's no priority for "paused", so set "Very Low" and deal with that later...
        elif mylar.CONFIG.NZBGET_PRIORITY == "Paused": nzbgetpriority = "-100"
    else:
        #if sab priority isn't selected, default to Normal (0)
        nzbgetpriority = "0"

    if nzbprov == 'torznab':
        nzbid = generate_id(nzbprov, link['id'])
        link = link['link']
    else:
        try:
            link = link['link']
        except:
            link = link
        nzbid = generate_id(nzbprov, link)

    logger.fdebug('issues match!')
    if 'Public Torrents' in tmpprov and any([nzbprov == 'WWT', nzbprov == 'DEM']):
        tmpprov = re.sub('Public Torrents', nzbprov, tmpprov)

    if comicinfo[0]['pack'] == True:
        if '0-Day Comics Pack' not in comicinfo[0]['ComicName']:
            logger.info('Found %s (%s) issue: %s using %s within a pack containing issues %s' % (ComicName, comyear, IssueNumber, tmpprov, comicinfo[0]['pack_numbers']))
        else:
            logger.info('Found %s using %s for %s' % (ComicName, tmpprov, comicinfo[0]['IssueDate']))
    else:
        if any([oneoff is True, IssueID is None]):
            #one-off information
            logger.fdebug("ComicName: " + ComicName)
            logger.fdebug("Issue: " + str(IssueNumber))
            logger.fdebug("Year: " + str(comyear))
            logger.fdebug("IssueDate: " + comicinfo[0]['IssueDate'])
        logger.info(u"Found " + ComicName + " (" + str(comyear) + ") issue: " + IssueNumber + " using " + str(tmpprov))

    logger.fdebug("link given by: " + str(nzbprov))

    if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING:
        logger.info('nzbid: %s' % nzbid)
        logger.info('IssueID: %s' % IssueID)
        logger.info('oneoff: %s' % oneoff)
        if all([nzbid is not None, IssueID is not None, oneoff is False]):
            # --- this causes any possible snatch to get marked as a Failed download when doing a one-off search...
            #try:
            #    # only nzb providers will have a filen, try it and pass exception
            #    if IssueID is None:
            #        logger.fdebug('One-off mode was initiated - Failed Download handling for : ' + ComicName + ' #' + str(IssueNumber))
            #        comicinfo = {"ComicName":   ComicName,
            #                     "IssueNumber": IssueNumber}
            #        return FailedMark(ComicID=ComicID, IssueID=IssueID, id=nzbid, nzbname=nzbname, prov=nzbprov, oneoffinfo=comicinfo)
            #except:
            #    pass
            call_the_fail = Failed.FailedProcessor(nzb_name=nzbname, id=nzbid, issueid=IssueID, comicid=ComicID, prov=tmpprov)
            check_the_fail = call_the_fail.failed_check()
            if check_the_fail == 'Failed':
                logger.fdebug('[FAILED_DOWNLOAD_CHECKER] [' + str(tmpprov) + '] Marked as a bad download : ' + str(nzbid))
                return "downloadchk-fail"
            elif check_the_fail == 'Good':
                logger.fdebug('[FAILED_DOWNLOAD_CHECKER] This is not in the failed downloads list. Will continue with the download.')
        else:
            logger.fdebug('[FAILED_DOWNLOAD_CHECKER] Failed download checking is not available for one-off downloads atm. Fixed soon!')
 
    if link and all([nzbprov != 'WWT', nzbprov != 'DEM', nzbprov != '32P', nzbprov != 'torznab']):

        #generate nzbid here.

        nzo_info = {}
        filen = None
        nzbhydra = False
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
                if 'searchresultid' in link:
                    logger.fdebug('NZBHydra V1 url detected. Adjusting...')
                    nzbhydra = True
                else:
                    apikey = newznab[3].rstrip()
                    verify = bool(newznab[2])
            else:
                down_url = 'https://api.nzb.su/api'
                apikey = mylar.CONFIG.NZBSU_APIKEY
                verify = bool(mylar.CONFIG.NZBSU_VERIFY)

            if nzbhydra is True:
                down_url = link
                verify = False
            elif 'https://cdn.' in link:
                down_url = host_newznab_fix + 'api'
                logger.fdebug('Re-routing incorrect RSS URL response for NZBGeek to correct API')
                payload = {'t': 'get',
                           'id': str(nzbid),
                           'apikey': str(apikey)}
            else:
                down_url = link

        elif nzbprov == 'dognzb':
            #dognzb - need to add back in the dog apikey
            down_url = urljoin(link, str(mylar.CONFIG.DOGNZB_APIKEY))
            verify = bool(mylar.CONFIG.DOGNZB_VERIFY)

        else:
            #experimental - direct link.
            down_url = link
            headers = None
            verify = False

        if payload is None:
            tmp_url = down_url
            tmp_url_st = tmp_url.find('apikey=')
            if tmp_url_st is -1:
                tmp_url_st = tmp_url.find('r=')
                tmp_line = tmp_url[:tmp_url_st+2]
            else:
                tmp_line = tmp_url[:tmp_url_st+7]
            tmp_line += 'xYOUDONTNEEDTOKNOWTHISx'
            tmp_url_en = tmp_url.find('&', tmp_url_st)
            if tmp_url_en is -1:
                tmp_url_en = len(tmp_url)
            tmp_line += tmp_url[tmp_url_en:]
            #tmp_url = helpers.apiremove(down_url.copy(), '&') 
            logger.fdebug('[PAYLOAD-NONE]Download URL: ' + str(tmp_line) + ' [VerifySSL:' + str(verify) + ']')
        else:
            tmppay = payload.copy()
            tmppay['apikey'] = 'YOUDONTNEEDTOKNOWTHIS'
            logger.fdebug('[PAYLOAD] Download URL: ' + down_url + '?' + urllib.urlencode(tmppay) + ' [VerifySSL:' + str(verify) + ']')

        if down_url.startswith('https') and verify == False:
            try:
                from requests.packages.urllib3 import disable_warnings
                disable_warnings()
            except:
                logger.warn('Unable to disable https warnings. Expect some spam if using https nzb providers.')

        try:
            r = requests.get(down_url, params=payload, verify=verify, headers=headers)

        except Exception, e:
            logger.warn('Error fetching data from %s: %s' % (tmpprov, e))
            return "sab-fail"

        logger.fdebug('Status code returned: %s' % r.status_code)
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
                logger.fdebug('filename within nzb: %s' % filen)
            except:
                pass

        if filen is None:
            if payload is None:
                logger.error('[PAYLOAD:NONE] Unable to download nzb from link: ' + str(down_url) + ' [' + link + ']')
            else:
                errorlink = down_url + '?' + urllib.urlencode(payload)
                logger.error('[PAYLOAD:PRESENT] Unable to download nzb from link: ' + str(errorlink) + ' [' + link + ']')
            return "sab-fail"
        else:
            #convert to a generic type of format to help with post-processing.
            filen = re.sub("\&", 'and', filen)
            filen = re.sub('[\,\:\?\']', '', filen)
            filen = re.sub('[\(\)]', ' ', filen)
            filen = re.sub('[\s\s+]', '', filen)  #make sure we remove the extra spaces.
            logger.fdebug('[FILENAME] filename (remove chars): ' + filen)
            filen = re.sub('.cbr', '', filen).strip()
            filen = re.sub('.cbz', '', filen).strip()
            logger.fdebug('[FILENAME] nzbname (\s): ' + filen)
            #filen = re.sub('\s', '.', filen)
            logger.fdebug('[FILENAME] end nzbname: ' + filen)

            if re.sub('.nzb', '', filen.lower()).strip() != re.sub('.nzb', '', nzbname.lower()).strip():
                alt_nzbname = re.sub('.nzb', '', filen).strip()
                alt_nzbname = re.sub('[\s+]', ' ', alt_nzbname)
                alt_nzbname = re.sub('[\s\_]', '.', alt_nzbname)
                logger.info('filen: ' + filen + ' -- nzbname: ' + nzbname + ' are not identical. Storing extra value as : ' + alt_nzbname)

            #make sure the cache directory exists - if not, create it (used for storing nzbs).
            if os.path.exists(mylar.CONFIG.CACHE_DIR):
                if mylar.CONFIG.ENFORCE_PERMS:
                    logger.fdebug("Cache Directory successfully found at : " + mylar.CONFIG.CACHE_DIR + ". Ensuring proper permissions.")
                    #enforce the permissions here to ensure the lower portion writes successfully
                    filechecker.setperms(mylar.CONFIG.CACHE_DIR, True)
                else:
                    logger.fdebug("Cache Directory successfully found at : " + mylar.CONFIG.CACHE_DIR)
            else:
                #let's make the dir.
                logger.fdebug("Could not locate Cache Directory, attempting to create at : " + mylar.CONFIG.CACHE_DIR)
                try:
                    filechecker.validateAndCreateDirectory(mylar.CONFIG.CACHE_DIR, True)
                    logger.info("Temporary NZB Download Directory successfully created at: " + mylar.CONFIG.CACHE_DIR)
                except OSError:
                    raise

            #save the nzb grabbed, so we can bypass all the 'send-url' crap.
            if not nzbname.endswith('.nzb'):
                nzbname = nzbname + '.nzb'
            nzbpath = os.path.join(mylar.CONFIG.CACHE_DIR, nzbname)

            with open(nzbpath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()

    #blackhole
    sent_to = None
    t_hash = None
    if mylar.USE_BLACKHOLE and all([nzbprov != '32P', nzbprov != 'WWT', nzbprov != 'DEM', nzbprov != 'torznab']):
        logger.fdebug("using blackhole directory at : " + str(mylar.CONFIG.BLACKHOLE_DIR))
        if os.path.exists(mylar.CONFIG.BLACKHOLE_DIR):
            #copy the nzb from nzbpath to blackhole dir.
            try:
                shutil.move(nzbpath, os.path.join(mylar.CONFIG.BLACKHOLE_DIR, nzbname))
            except (OSError, IOError):
                logger.warn('Failed to move nzb into blackhole directory - check blackhole directory and/or permissions.')
                return "blackhole-fail"
            logger.fdebug("filename saved to your blackhole as : " + nzbname)
            logger.info(u"Successfully sent .nzb to your Blackhole directory : " + os.path.join(mylar.CONFIG.BLACKHOLE_DIR, nzbname))
            sent_to = "your Blackhole Directory"

            if mylar.CONFIG.ENABLE_SNATCH_SCRIPT:
                if comicinfo[0]['pack'] is False:
                    pnumbers = None
                    plist = None
                else:
                    pnumbers = '|'.join(comicinfo[0]['pack_numbers'])
                    plist= '|'.join(comicinfo[0]['pack_issuelist'])
                snatch_vars = {'nzbinfo':       {'link':           link,
                                                 'id':             nzbid,
                                                 'nzbname':        nzbname,
                                                 'nzbpath':        nzbpath,
                                                 'blackhole':      mylar.CONFIG.BLACKHOLE_DIR},
                               'comicinfo':     {'comicname':      ComicName,
                                                'volume':         comicinfo[0]['ComicVolume'],
                                                 'comicid':        ComicID,
                                                 'issueid':        IssueID,
                                                 'issuenumber':    IssueNumber,
                                                 'issuedate':      comicinfo[0]['IssueDate'],
                                                 'seriesyear':     comyear},
                               'pack':           comicinfo[0]['pack'],
                               'pack_numbers':   pnumbers,
                               'pack_issuelist': plist,
                               'provider':       nzbprov,
                               'method':         'nzb',
                               'clientmode':     'blackhole'}
                snatchitup = helpers.script_env('on-snatch',snatch_vars)
                if snatchitup is True:
                    logger.info('Successfully submitted on-grab script as requested.')
                else:
                    logger.info('Could not Successfully submit on-grab script as requested. Please check logs...')
    #end blackhole

    #torrents (32P & DEM)
    elif any([nzbprov == '32P', nzbprov == 'WWT', nzbprov == 'DEM', nzbprov == 'torznab']):
        logger.fdebug("ComicName:" + ComicName)
        logger.fdebug("link:" + link)
        logger.fdebug("Torrent Provider:" + nzbprov)

        rcheck = rsscheck.torsend2client(ComicName, IssueNumber, comyear, link, nzbprov, nzbid)  #nzbid = hash for usage with public torrents
        if rcheck == "fail":
            if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING:
                logger.error('Unable to send torrent to client. Assuming incomplete link - sending to Failed Handler and continuing search.')
                if any([oneoff is True, IssueID is None]):
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
        else:
            #start the auto-snatch segway here (if rcheck isn't False, it contains the info of the torrent)
            #since this is torrentspecific snatch, the vars will be different than nzb snatches.
            #torrent_info{'folder','name',['total_filesize','label','hash','files','time_started'}
            t_hash = rcheck['hash']
            rcheck.update({'torrent_filename': nzbname})

            if any([mylar.USE_RTORRENT, mylar.USE_DELUGE]) and mylar.CONFIG.AUTO_SNATCH:
                mylar.SNATCHED_QUEUE.put(rcheck['hash'])
            elif any([mylar.USE_RTORRENT, mylar.USE_DELUGE]) and mylar.CONFIG.LOCAL_TORRENT_PP:
                mylar.SNATCHED_QUEUE.put(rcheck['hash'])
            else:
                if mylar.CONFIG.ENABLE_SNATCH_SCRIPT:
                    try:
                        if comicinfo[0]['pack'] is False:
                            pnumbers = None
                            plist = None
                        else:
                            if '0-Day Comics Pack' in ComicName:
                                helpers.lookupthebitches(rcheck['files'], rcheck['folder'], nzbname, nzbid, nzbprov, t_hash, comicinfo[0]['IssueDate'])
                                pnumbers = None
                                plist = None
                            else:
                                pnumbers = '|'.join(comicinfo[0]['pack_numbers'])
                                plist = '|'.join(comicinfo[0]['pack_issuelist'])
                        snatch_vars = {'comicinfo':       {'comicname':        ComicName,
                                                           'volume':           comicinfo[0]['ComicVolume'],
                                                           'issuenumber':      IssueNumber,
                                                           'issuedate':        comicinfo[0]['IssueDate'],
                                                           'seriesyear':       comyear,
                                                           'comicid':          ComicID,
                                                           'issueid':          IssueID},
                                       'pack':             comicinfo[0]['pack'],
                                       'pack_numbers':     pnumbers,
                                       'pack_issuelist':   plist,
                                       'provider':         nzbprov,
                                       'method':           'torrent',
                                       'clientmode':       rcheck['clientmode'],
                                       'torrentinfo':      rcheck}

                        snatchitup = helpers.script_env('on-snatch',snatch_vars)
                        if snatchitup is True:
                            logger.info('Successfully submitted on-grab script as requested.')
                        else:
                            logger.info('Could not Successfully submit on-grab script as requested. Please check logs...')
                    except Exception as e:
                        logger.warn('error: %s' % e)

        if mylar.USE_WATCHDIR is True:
            if mylar.CONFIG.TORRENT_LOCAL is True:
                sent_to = "your local Watch folder"
            else:
                sent_to = "your seedbox Watch folder"
        elif mylar.USE_UTORRENT is True:
            sent_to = "your uTorrent client"
        elif mylar.USE_RTORRENT is True:
            sent_to = "your rTorrent client"
        elif mylar.USE_TRANSMISSION is True:
            sent_to = "your Transmission client"
        elif mylar.USE_DELUGE is True:
            sent_to = "your Deluge client"
        elif mylar.USE_QBITTORRENT is True:
            sent_to = "your qBittorrent client"
    #end torrents

    else:
        #SABnzbd / NZBGet

        #logger.fdebug("link to retrieve via api:" + str(helpers.apiremove(linkapi,'$')))

        #nzb.get
        if mylar.USE_NZBGET:
            ss = nzbget.NZBGet()
            send_to_nzbget = ss.sender(nzbpath)
            if send_to_nzbget['status'] is True:
                if mylar.CONFIG.NZBGET_CLIENT_POST_PROCESSING is True:
                    mylar.NZB_QUEUE.put(send_to_nzbget)
            else:
                logger.warn('Unable to send nzb file to NZBGet. There was a parameter error as there are no values present: %s' % nzbget_params)
                return "nzbget-fail"

            if send_to_nzbget['status'] is True:
                logger.info("Successfully sent nzb to NZBGet!")
            else:
                logger.info("Unable to send nzb to NZBGet - check your configs.")
                return "nzbget-fail"
            sent_to = "NZBGet"

        #end nzb.get

        elif mylar.USE_SABNZBD:
            sab_params = None
            # let's build the send-to-SAB string now:
            # changed to just work with direct links now...

            #generate the api key to download here and then kill it immediately after.
            if mylar.DOWNLOAD_APIKEY is None:
                import hashlib, random
                mylar.DOWNLOAD_APIKEY = hashlib.sha224(str(random.getrandbits(256))).hexdigest()[0:32]

            #generate the mylar host address if applicable.
            if mylar.CONFIG.ENABLE_HTTPS:
                proto = 'https://'
            else:
                proto = 'http://'

            if mylar.CONFIG.HTTP_ROOT is None:
                hroot = '/'
            elif mylar.CONFIG.HTTP_ROOT.endswith('/'):
                hroot = mylar.CONFIG.HTTP_ROOT
            else:
                if mylar.CONFIG.HTTP_ROOT != '/':
                    hroot = mylar.CONFIG.HTTP_ROOT + '/'
                else:
                    hroot = mylar.CONFIG.HTTP_ROOT

            if mylar.LOCAL_IP is None:
                #if mylar's local, get the local IP using socket.
                try:
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(('8.8.8.8', 80))
                    mylar.LOCAL_IP = s.getsockname()[0]
                    s.close()
                except:
                    logger.warn('Unable to determine local IP. Defaulting to host address for Mylar provided as : ' + str(mylar.CONFIG.HTTP_HOST))

            if mylar.CONFIG.HOST_RETURN:
                #mylar has the return value already provided (easier and will work if it's right)
                if mylar.CONFIG.HOST_RETURN.endswith('/'):
                    mylar_host = mylar.CONFIG.HOST_RETURN
                else:
                    mylar_host = mylar.CONFIG.HOST_RETURN + '/'

            elif mylar.CONFIG.SAB_TO_MYLAR:
                #if sab & mylar are on different machines, check to see if they are local or external IP's provided for host.
                if mylar.CONFIG.HTTP_HOST == 'localhost' or mylar.CONFIG.HTTP_HOST == '0.0.0.0' or mylar.CONFIG.HTTP_HOST.startswith('10.') or mylar.CONFIG.HTTP_HOST.startswith('192.') or mylar.CONFIG.HTTP_HOST.startswith('172.'):
                    #if mylar's local, use the local IP already assigned to LOCAL_IP.
                    mylar_host = proto + str(mylar.LOCAL_IP) + ':' + str(mylar.CONFIG.HTTP_PORT) + hroot
                else:
                    if mylar.EXT_IP is None:
                        #if mylar isn't local, get the external IP using pystun.
                        import stun
                        sip = mylar.CONFIG.HTTP_HOST
                        port = int(mylar.CONFIG.HTTP_PORT)
                        try:
                            nat_type, ext_ip, ext_port = stun.get_ip_info(sip,port)
                            mylar_host = proto + str(ext_ip) + ':' + str(mylar.CONFIG.HTTP_PORT) + hroot
                            mylar.EXT_IP = ext_ip
                        except:
                            logger.warn('Unable to retrieve External IP - try using the host_return option in the config.ini.')
                            mylar_host = proto + str(mylar.CONFIG.HTTP_HOST) + ':' + str(mylar.CONFIG.HTTP_PORT) + hroot
                    else:
                        mylar_host = proto + str(mylar.EXT_IP) + ':' + str(mylar.CONFIG.HTTP_PORT) + hroot

            else:
                #if all else fails, drop it back to the basic host:port and try that.
                if mylar.LOCAL_IP is None:
                    tmp_host = mylar.CONFIG.HTTP_HOST
                else:
                    tmp_host = mylar.LOCAL_IP
                mylar_host = proto + str(tmp_host) + ':' + str(mylar.CONFIG.HTTP_PORT) + hroot


            fileURL = mylar_host + 'api?apikey=' + mylar.DOWNLOAD_APIKEY + '&cmd=downloadNZB&nzbname=' + nzbname

            sab_params = {'apikey':     mylar.CONFIG.SAB_APIKEY,
                          'mode':       'addurl',
                          'name':       fileURL,
                          'cmd':        'downloadNZB',
                          'nzbname':    nzbname,
                          'output':     'json'}

            # determine SAB priority
            if mylar.CONFIG.SAB_PRIORITY:
                #setup the priorities.
                if mylar.CONFIG.SAB_PRIORITY == "Default": sabpriority = "-100"
                elif mylar.CONFIG.SAB_PRIORITY == "Low": sabpriority = "-1"
                elif mylar.CONFIG.SAB_PRIORITY == "Normal": sabpriority = "0"
                elif mylar.CONFIG.SAB_PRIORITY == "High": sabpriority = "1"
                elif mylar.CONFIG.SAB_PRIORITY == "Paused": sabpriority = "-2"
            else:
                #if sab priority isn't selected, default to Normal (0)
                sabpriority = "0"

            sab_params['priority'] = sabpriority

            # if category is blank, let's adjust
            if mylar.CONFIG.SAB_CATEGORY:
                sab_params['cat'] = mylar.CONFIG.SAB_CATEGORY
            #if mylar.CONFIG.POST_PROCESSING: #or mylar.CONFIG.RENAME_FILES:
            #    if mylar.CONFIG.POST_PROCESSING_SCRIPT:
            #        #this is relative to the SABnzbd script directory (ie. no path)
            #        tmpapi = tmpapi + "&script=" + mylar.CONFIG.POST_PROCESSING_SCRIPT
            #    else:
            #        tmpapi = tmpapi + "&script=ComicRN.py"
            #    logger.fdebug("...attaching rename script: " + str(helpers.apiremove(tmpapi, '&')))
            #final build of send-to-SAB
            #logger.fdebug("Completed send-to-SAB link: " + str(helpers.apiremove(tmpapi, '&')))

            if sab_params is not None:
                ss = sabnzbd.SABnzbd(sab_params)
                sendtosab = ss.sender()
                if all([sendtosab['status'] is True, mylar.CONFIG.SAB_CLIENT_POST_PROCESSING is True]):
                    mylar.NZB_QUEUE.put(sendtosab)
            else:
                logger.warn('Unable to send nzb file to SABnzbd. There was a parameter error as there are no values present: %s' % sab_params)
                mylar.DOWNLOAD_APIKEY = None
                return "sab-fail"

            sent_to = "SABnzbd+"
            logger.info(u"Successfully sent nzb file to SABnzbd")

        if mylar.CONFIG.ENABLE_SNATCH_SCRIPT:
            if mylar.USE_NZBGET:
                clientmode = 'nzbget'
                client_id = None
            elif mylar.USE_SABNZBD:
                clientmode = 'sabnzbd'
                client_id = sendtosab['nzo_id']

            if comicinfo[0]['pack'] is False:
                pnumbers = None
                plist = None
            else:
                pnumbers = '|'.join(comicinfo[0]['pack_numbers'])
                plist= '|'.join(comicinfo[0]['pack_issuelist'])
            snatch_vars = {'nzbinfo':        {'link':           link,
                                              'id':             nzbid,
                                              'client_id':      client_id,
                                              'nzbname':        nzbname,
                                              'nzbpath':        nzbpath},
                           'comicinfo':      {'comicname':      comicinfo[0]['ComicName'],
                                              'volume':         comicinfo[0]['ComicVolume'],
                                              'comicid':        ComicID,
                                              'issueid':        IssueID,
                                              'issuenumber':    IssueNumber,
                                              'issuedate':      comicinfo[0]['IssueDate'],
                                              'seriesyear':     comyear},
                           'pack':            comicinfo[0]['pack'],
                           'pack_numbers':    pnumbers,
                           'pack_issuelist':  plist,
                           'provider':        nzbprov,
                           'method':          'nzb',
                           'clientmode':      clientmode}

            snatchitup = helpers.script_env('on-snatch',snatch_vars)
            if snatchitup is True:
                logger.info('Successfully submitted on-grab script as requested.')
            else:
                logger.info('Could not Successfully submit on-grab script as requested. Please check logs...')

    #nzbid, nzbname, sent_to
    nzbname = re.sub('.nzb', '', nzbname).strip()

    return_val = {}
    return_val = {"nzbid":       nzbid,
                  "nzbname":     nzbname,
                  "sent_to":     sent_to,
                  "SARC":        SARC,
                  "alt_nzbname": alt_nzbname,
                  "t_hash":      t_hash}

    #if it's a directsend link (ie. via a retry).
    if directsend is None:
        return return_val
    else:
        if 'Public Torrents' in tmpprov and any([nzbprov == 'WWT', nzbprov == 'DEM']):
            tmpprov = re.sub('Public Torrents', nzbprov, tmpprov)
        #update the db on the snatch.
        if alt_nzbname is None or alt_nzbname == '':
            logger.fdebug("Found matching comic...preparing to send to Updater with IssueID %s and nzbname of %s [Oneoff:%s]" % (IssueID, nzbname, oneoff))
            if '[RSS]' in tmpprov: tmpprov = re.sub('\[RSS\]', '', tmpprov).strip()
            updater.nzblog(IssueID, nzbname, ComicName, SARC=SARC, IssueArcID=IssueArcID, id=nzbid, prov=tmpprov, oneoff=oneoff)
        else:
            logger.fdebug("Found matching comic...preparing to send to Updater with IssueID %s and nzbname of %s [ALTNZBNAME:%s][OneOff:%s]" % (IssueID, nzbname, alt_nzbname, oneoff))
            if '[RSS]' in tmpprov: tmpprov = re.sub('\[RSS\]', '', tmpprov).strip()
            updater.nzblog(IssueID, nzbname, ComicName, SARC=SARC, IssueArcID=IssueArcID, id=nzbid, prov=tmpprov, alt_nzbname=alt_nzbname, oneoff=oneoff)
        #send out notifications for on snatch after the updater incase notification fails (it would bugger up the updater/pp scripts)
        notify_snatch(nzbname, sent_to, helpers.filesafe(modcomicname), comyear, IssueNumber, nzbprov)
        mylar.TMP_PROV = nzbprov
        return return_val

def notify_snatch(nzbname, sent_to, modcomicname, comyear, IssueNumber, nzbprov):

    if IssueNumber is not None:
        snline = modcomicname + ' (' + comyear + ') - Issue #' + IssueNumber + ' snatched!'
    else:
        snline = modcomicname + ' (' + comyear + ') snatched!'

    if mylar.CONFIG.PROWL_ENABLED and mylar.CONFIG.PROWL_ONSNATCH:
        logger.info(u"Sending Prowl notification")
        prowl = notifiers.PROWL()
        prowl.notify(nzbname, "Download started using " + sent_to)
    if mylar.CONFIG.NMA_ENABLED and mylar.CONFIG.NMA_ONSNATCH:
        logger.info(u"Sending NMA notification")
        nma = notifiers.NMA()
        nma.notify(snline=snline, snatched_nzb=nzbname, sent_to=sent_to, prov=nzbprov)
    if mylar.CONFIG.PUSHOVER_ENABLED and mylar.CONFIG.PUSHOVER_ONSNATCH:
        logger.info(u"Sending Pushover notification")
        pushover = notifiers.PUSHOVER()
        pushover.notify(snline, snatched_nzb=nzbname, sent_to=sent_to, prov=nzbprov)
    if mylar.CONFIG.BOXCAR_ENABLED and mylar.CONFIG.BOXCAR_ONSNATCH:
        logger.info(u"Sending Boxcar notification")
        boxcar = notifiers.BOXCAR()
        boxcar.notify(snatched_nzb=nzbname, sent_to=sent_to, snline=snline)
    if mylar.CONFIG.PUSHBULLET_ENABLED and mylar.CONFIG.PUSHBULLET_ONSNATCH:
        logger.info(u"Sending Pushbullet notification")
        pushbullet = notifiers.PUSHBULLET()
        pushbullet.notify(snline=snline, snatched=nzbname, sent_to=sent_to, prov=nzbprov, method='POST')
    if mylar.CONFIG.TELEGRAM_ENABLED and mylar.CONFIG.TELEGRAM_ONSNATCH:
        logger.info(u"Sending Telegram notification")
        telegram = notifiers.TELEGRAM()
        telegram.notify(snline, nzbname)
    if mylar.CONFIG.SLACK_ENABLED and mylar.CONFIG.SLACK_ONSNATCH:
        logger.info(u"Sending Slack notification")
        slack = notifiers.SLACK()
        slack.notify("Snatched", snline)

    return

def FailedMark(IssueID, ComicID, id, nzbname, prov, oneoffinfo=None):
        # Used to pass a failed attempt at sending a download to a client, to the failed handler, and then back again to continue searching.

        from mylar import Failed

        FailProcess = Failed.FailedProcessor(issueid=IssueID, comicid=ComicID, id=id, nzb_name=nzbname, prov=prov, oneoffinfo=oneoffinfo)
        Markit = FailProcess.markFailed()

        if prov == '32P' or prov == 'Public Torrents': return "torrent-fail"
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
    #logger.fdebug('[%s] generate_id - link: %s' % (nzbprov, link))
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
    elif any([nzbprov == 'WWT', nzbprov == 'DEM']):
        #if nzbprov == 'TPSE':
        #    #TPSE is magnet links only.
        #    info_hash = re.findall("urn:btih:([\w]{32,40})", link)[0]
        #    if len(info_hash) == 32:
        #        info_hash = b16encode(b32decode(info_hash))
        #    nzbid = info_hash.upper()
        #else:
        if 'http' not in link and any([nzbprov == 'WWT', nzbprov == 'DEM']):
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
    elif 'newznab' in nzbprov:
        #if in format of http://newznab/getnzb/<id>.nzb&i=1&r=apikey
        tmpid = urlparse.urlparse(link)[4]  #param 4 is the query string from the url.
        if 'searchresultid' in tmpid:
            nzbid = os.path.splitext(link)[0].rsplit('searchresultid=',1)[1]
        elif tmpid == '' or tmpid is None:
            nzbid = os.path.splitext(link)[0].rsplit('/', 1)[1]
        else:
            nzbinfo = urlparse.parse_qs(link)
            nzbid = nzbinfo.get('id', None)
            if nzbid is not None:
                nzbid = ''.join(nzbid)
        if nzbid is None:
            #if apikey is passed in as a parameter and the id is in the path
            findend = tmpid.find('&')
            if findend == -1:
                findend = len(tmpid)
                nzbid = tmpid[findend+1:].strip()
            else:
                findend = tmpid.find('apikey=', findend)
                nzbid = tmpid[findend+1:].strip()
            if '&id' not in tmpid or nzbid == '':
                tmpid = urlparse.urlparse(link)[2]
                nzbid = tmpid.rsplit('/', 1)[1]
    elif nzbprov == 'torznab':
        idtmp = urlparse.urlparse(link)[4]
        idpos = idtmp.find('&')
        nzbid = re.sub('id=', '', idtmp[:idpos]).strip()
    return nzbid
