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
from mylar import logger, db, updater, helpers, parseit, findcomicfeed

nzbsu_APIkey = mylar.NZBSU_APIKEY
dognzb_APIkey = mylar.DOGNZB_APIKEY

LOG = mylar.LOG_DIR

import pickle
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

def search_init(ComicName, IssueNumber, ComicYear, SeriesYear, IssueDate, IssueID, AlternateSearch=None):
    if ComicYear == None: ComicYear = '2013'
    else: ComicYear = str(ComicYear)[:4]
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
    if mylar.NEWZNAB == 1:
        newznab_hosts = [(mylar.NEWZNAB_HOST, mylar.NEWZNAB_APIKEY, mylar.NEWZNAB_ENABLED)]
        if mylar.NEWZNAB_ENABLED:
            nzbprovider.append('newznab')
            nzbp+=1
        #newznabs = 0

        for newznab_host in mylar.EXTRA_NEWZNABS:
            if newznab_host[2] == '1' or newznab_host[2] == 1:
                newznab_hosts.append(newznab_host)              
                newznabs = newznabs + 1

        #categories = "7030"

        #for newznab_host in newznab_hosts:
        #    mylar.NEWZNAB_APIKEY = newznab_host[1]
        #    mylar.NEWZNAB_HOST = newznab_host[0]

    # --------
    logger.fdebug("there are : " + str(nzbp) + " search providers you have selected.")
    nzbpr = nzbp-1
    findit = 'no'

    #fix for issue dates between Nov-Dec/Jan
    IssDt = str(IssueDate)[5:7]
    if IssDt == "12" or IssDt == "11":
         IssDateFix = "yes"
    else:
         IssDateFix = "no"

    while (nzbpr >= 0 ):
    
        if nzbprovider[nzbpr] == 'newznab':
        #this is for newznab
            nzbprov = 'newznab'
            for newznab_host in newznab_hosts:
                logger.fdebug("newnzb_host: " + str(newznab_host))
                findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, newznab_host)
                if findit == 'yes':
                    logger.fdebug("findit = found!")
                    continue
                else:
                    if AlternateSearch is not None:
                        logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AlternateSearch) + " " + str(ComicYear))
                        findit = NZB_SEARCH(AlternateSearch, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, newznab_host)
                        if findit == 'yes':
                            break
               #     if IssDateFix == "yes":
               #         logger.info(u"Hang on - this issue was published between Nov/Dec of " + str(ComicYear) + "...adjusting to " + str(ComicYearFix) + " and retrying...")
               #         findit = NZB_SEARCH(ComicName, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, newznab_host)
               #         if findit == 'yes':
               #             break
               #         elif AlternateSearch is not None:
               #             logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AlternateSearch) + " " + str(ComicYearFix))
               #             findit = NZB_SEARCH(AlternateSearch, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, newznab_host)
               #             if findit == 'yes':
               #                 break

            nzbpr-=1

        elif nzbprovider[nzbpr] == 'experimental':
        #this is for experimental
            nzbprov = 'experimental'
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
            if findit == 'yes':
                logger.fdebug("findit = found!")
                continue
            else:
                if AlternateSearch is not None:
                    logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AlternateSearch) + str(ComicYear))
                    findit = NZB_SEARCH(AlternateSearch, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                    if findit == 'yes':
                        break
               # if IssDateFix == "yes":
               #     logger.info(u"Hang on - this issue was published between Nov/Dec of " + str(ComicYear) + "...adjusting to " + str(ComicYearFix) + " and retrying...")
               #     findit = NZB_SEARCH(ComicName, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
               #     if findit == 'yes':
               #         break
               #     elif AlternateSearch is not None:
               #         logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AlternateSearch) + str(ComicYearFix))
               #         findit = NZB_SEARCH(AlternateSearch, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
               #         if findit == 'yes':
               #             break

            nzbpr-=1

        elif nzbprovider[nzbpr] == 'nzb.su':
        # ----
        # this is for nzb.su
            #d = feedparser.parse("http://nzb.su/rss?t=7030&dl=1&i=" + str(nzbsu_APIID) + "&r=" + str(nzbsu_APIkey))
            #--LATER ?search.rss_find = RSS_SEARCH(ComicName, IssueNumber)
            #if rss_find == 0:
            nzbprov = 'nzb.su'
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
            if findit == 'yes':
                logger.fdebug("findit = found!")
                continue
            else:
                if AlternateSearch is not None:
                    logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AlternateSearch) + str(ComicYear))
                    findit = NZB_SEARCH(AlternateSearch, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                    if findit == 'yes':
                        break
                #if IssDateFix == "yes":
                #    logger.info(u"Hang on - this issue was published between Nov/Dec of " + str(ComicYear) + "...adjusting to " + str(ComicYearFix) + " and retrying...")
                #    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                #    if findit == 'yes':
                #        break
                #    elif AlternateSearch is not None:
                #        logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AlternateSearch) + str(ComicYearFix))
                #        findit = NZB_SEARCH(AlternateSearch, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                #        if findit == 'yes':
                #            break

            nzbpr-=1

        # ----
       
        elif nzbprovider[nzbpr] == 'dognzb':
        # this is for dognzb.com
            #d = feedparser.parse("http://dognzb.cr/rss.cfm?r=" + str(dognzb_APIkey) + "&t=7030&num=100")
            #RSS_SEARCH(ComicName, IssueNumber)
            nzbprov = 'dognzb'
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)

            if findit == 'yes':
                logger.fdebug("findit = found!")
                continue
            else:
                if AlternateSearch is not None:
                    logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AlternateSearch) + str(ComicYear))
                    findit = NZB_SEARCH(AlternateSearch, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                    if findit == 'yes':
                        break
                #if IssDateFix == "yes":
                #    logger.info(u"Hang on - this issue was published between Nov/Dec of " + str(ComicYear) + "...adjusting to " + str(ComicYearFix) + " and retrying...")
                #    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                #    if findit == 'yes':
                #        break
                #    elif AlternateSearch is not None:
                #        logger.info(u"Alternate Search pattern detected...re-adjusting to : " + str(AlternateSearch) + str(ComicYearFix))
                #        findit = NZB_SEARCH(AlternateSearch, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                #        if findit == 'yes':
                #            break

            nzbpr-=1

        if nzbpr >= 0 and findit != 'yes':
            logger.info(u"More than one search provider given - trying next one.")
        # ----
        if findit == 'yes': return findit
    return findit

def NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, newznab_host=None):
    logger.info(u"Shhh be very quiet...I'm looking for " + ComicName + " issue: " + str(IssueNumber) + "(" + str(ComicYear) + ") using " + str(nzbprov))
    if nzbprov == 'nzb.su':
        apikey = mylar.NZBSU_APIKEY
    elif nzbprov == 'dognzb':
        apikey = mylar.DOGNZB_APIKEY
    elif nzbprov == 'experimental':
        apikey = 'none'
    elif nzbprov == 'newznab':
        host_newznab = newznab_host[0]
        apikey = newznab_host[1]
        logger.fdebug("using Newznab host of : " + str(host_newznab))

    if mylar.PREFERRED_QUALITY == 0: filetype = ""
    elif mylar.PREFERRED_QUALITY == 1: filetype = ".cbr"
    elif mylar.PREFERRED_QUALITY == 2: filetype = ".cbz"

    if mylar.SAB_PRIORITY:
        if mylar.SAB_PRIORITY == 1: sabpriority = "-100"
        elif mylar.SAB_PRIORITY == 2: sabpriority = "-1"
        elif mylar.SAB_PRIORITY == 3: sabpriority = "0"
        elif mylar.SAB_PRIORITY == 4: sabpriority = "1"
        elif mylar.SAB_PRIORITY == 5: sabpriority = "-2"
    else:
        #if sab priority isn't selected, default to Normal (0)
        sabpriority = "0"

    # figure out what was missed via rss feeds and do a manual search via api
    #tsc = int(tot-1)
    findcomic = []
    findcomiciss = []
    findcount = 0
    ci = ""
    comsearch = []
    isssearch = []
    comyear = str(ComicYear)

    #print ("-------SEARCH FOR MISSING------------------")
    findcomic.append(str(ComicName))
    # this should be called elsewhere..redudant code.
    if '.' in IssueNumber:
        isschk_find = IssueNumber.find('.')
        isschk_b4dec = IssueNumber[:isschk_find]
        isschk_decval = IssueNumber[isschk_find+1:]
        logger.fdebug("IssueNumber: " + str(IssueNumber))
        logger.fdebug("..before decimal: " + str(isschk_b4dec))
        logger.fdebug("...after decimal: " + str(isschk_decval))
    #--let's make sure we don't wipe out decimal issues ;)
        if int(isschk_decval) == 0:
            iss = isschk_b4dec
            intdec = int(isschk_decval)
        else:
            if len(isschk_decval) == 1:
                iss = isschk_b4dec + "." + isschk_decval
                intdec = int(isschk_decval) * 10
            else:
                iss = isschk_b4dec + "." + isschk_decval.rstrip('0')
                intdec = int(isschk_decval.rstrip('0')) * 10
 
        logger.fdebug("let's search with this issue value: " + str(iss))
    #Issue_Number = carry-over with decimals
    #iss = clean issue number (no decimals)
    intIss = (int(isschk_b4dec) * 1000) + intdec
    logger.fdebug("int.issue :" + str(intIss))
    logger.fdebug("int.issue_b4: " + str(isschk_b4dec))
    logger.fdebug("int.issue_dec: " + str(intdec))
    IssueNumber = iss
    #issue_decimal = re.compile(r'[^\d.]+')
    #issue = issue_decimal.sub('', str(IssueNumber))
    findcomiciss.append(iss)

    #print ("we need : " + str(findcomic[findcount]) + " issue: #" + str(findcomiciss[findcount]))
    # replace whitespace in comic name with %20 for api search
    cm1 = re.sub(" ", "%20", str(findcomic[findcount]))
    cm = re.sub("\&", "%26", str(cm1))
    #print (cmi)
    if '.' in findcomiciss[findcount]:
        if len(str(isschk_b4dec)) == 3:
            cmloopit = 1
        elif len(str(isschk_b4dec)) == 2:
            cmloopit = 2
        elif len(str(isschk_b4dec)) == 1:
            cmloopit = 3
    else:
        if len(str(findcomiciss[findcount])) == 1:
            cmloopit = 3
        elif len(str(findcomiciss[findcount])) == 2:
            cmloopit = 2
        else:
            cmloopit = 1
    isssearch.append(str(findcomiciss[findcount]))
    comsearch.append(cm)
    findcount+=1

    # ----

    #print ("------RESULTS OF SEARCH-------------------")
    findloop = 0
    foundcomic = []
    done = False
    #---issue problem
    # if issue is '011' instead of '11' in nzb search results, will not have same
    # results. '011' will return different than '11', as will '009' and '09'.

    while (findloop < (findcount) ):
        comsrc = comsearch[findloop]
        while (cmloopit >= 1 ):
            if done is True:
                logger.fdebug("we should break out now - sucessful search previous")
                findloop == 99
                break
                # here we account for issue pattern variations
            if cmloopit == 3:
                comsearch[findloop] = comsrc + "%2000" + isssearch[findloop] + "%20" + str(filetype)
            elif cmloopit == 2:
                comsearch[findloop] = comsrc + "%200" + isssearch[findloop] + "%20" + str(filetype)
            elif cmloopit == 1:
                comsearch[findloop] = comsrc + "%20" + isssearch[findloop] + "%20" + str(filetype)
            logger.fdebug("comsearch: " + str(comsearch))
            logger.fdebug("cmloopit: " + str(cmloopit))
            logger.fdebug("done: " + str(done))
            if nzbprov != 'experimental':
                if nzbprov == 'dognzb':
                    findurl = "http://dognzb.cr/api?t=search&apikey=" + str(apikey) + "&q=" + str(comsearch[findloop]) + "&o=xml&cat=7030"
                elif nzbprov == 'nzb.su':
                    findurl = "http://www.nzb.su/api?t=search&q=" + str(comsearch[findloop]) + "&apikey=" + str(apikey) + "&o=xml&cat=7030"
                elif nzbprov == 'newznab':
                    findurl = str(host_newznab) + "api?t=search&q=" + str(comsearch[findloop]) + "&apikey=" + str(apikey) + "&o=xml&cat=7030"
                    logger.fdebug("search-url: " + str(findurl))
                bb = feedparser.parse(findurl)
            elif nzbprov == 'experimental':
                #bb = parseit.MysterBinScrape(comsearch[findloop], comyear)
                bb = findcomicfeed.Startit(cm, isssearch[findloop], comyear)
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
                    logger.fdebug("checking search result: " + str(entry['title']))
                    thisentry = str(entry['title'])
                    logger.fdebug("Entry: " + str(thisentry))
                    cleantitle = re.sub('[_/.]', ' ', str(entry['title']))
                    cleantitle = helpers.cleanName(str(cleantitle))
                    nzbname = cleantitle

                    logger.fdebug("Cleantitle: " + str(cleantitle))
                    if len(re.findall('[^()]+', cleantitle)) == 1: cleantitle = "abcdefghijk 0 (1901).cbz"                      
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
                        if m[cnt][:-2] == '19' or m[cnt][:-2] == '20': 
                            logger.fdebug("year detected: " + str(m[cnt]))
                            result_comyear = m[cnt]
                            if str(comyear) in result_comyear:
                                logger.fdebug(str(comyear) + " - right years match baby!")
                                yearmatch = "true"
                            else:
                                logger.fdebug(str(comyear) + " - not right - years do not match")
                                yearmatch = "false"
                                #let's do this hear and save a few extra loops ;)
                                #fix for issue dates between Nov-Dec/Jan
                                if IssDateFix == "yes":
                                    ComicYearFix = int(ComicYear) + 1
                                    if str(ComicYearFix) in result_comyear:
                                        logger.fdebug("further analysis reveals this was published inbetween Nov-Jan, incrementing year to " + str(ComicYearFix) + " has resulted in a match!")
                                        yearmatch = "true"

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
                    comic_iss_b4 = re.sub('[\-\:\,]', ' ', str(comic_andiss))
                    comic_iss = comic_iss_b4.replace('.',' ')
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
                            if chg_comic.upper() == findcomic[findloop].upper():
                                logger.fdebug("series contains numerics...adjusting..")
                            else:
                                changeup = "." + splitit[(len(splitit)-1)]
                                logger.fdebug("changeup to decimal: " + str(changeup))
                                comic_iss = splitit[(len(splitit)-2)] + "." + comic_iss
                                splitst = len(splitit) - 2

                    logger.fdebug("adjusting from: " + str(comic_iss_b4) + " to: " + str(comic_iss))
                    #bmm = re.findall('v\d', comic_iss)
                    #if len(bmm) > 0: splitst = len(splitit) - 2
                    #else: splitst = len(splitit) - 1

                    # make sure that things like - in watchcomic are accounted for when comparing to nzb.
                    watchcomic_split = re.sub('[\-\:\,]', ' ', findcomic[findloop]).split(None)
                     
                    logger.fdebug(str(splitit) + " nzb series word count: " + str(splitst))
                    logger.fdebug(str(watchcomic_split) + " watchlist word count: " + str(len(watchcomic_split)))
                    if (splitst) != len(watchcomic_split):
                        logger.fdebug("incorrect comic lengths...not a match")
                        if str(splitit[0]).lower() == "the":
                            logger.fdebug("THE word detected...attempting to adjust pattern matching")
                            splitit[0] = splitit[4:]
                    else:
                        logger.fdebug("length match..proceeding")
                        n = 0
                        scount = 0
                        logger.fdebug("search-length: " + str(len(splitit)))
                        logger.fdebug("Watchlist-length: " + str(len(watchcomic_split)))
                        while ( n <= len(splitit)-1 ):
                            logger.fdebug("splitit: " + str(splitit[n]))
                            if n < len(splitit)-1 and n < len(watchcomic_split):
                                logger.fdebug(str(n) + " Comparing: " + str(watchcomic_split[n]) + " .to. " + str(splitit[n]))
                                if str(watchcomic_split[n].lower()) in str(splitit[n].lower()):
                                    logger.fdebug("word matched on : " + str(splitit[n]))
                                    scount+=1
                                #elif ':' in splitit[n] or '-' in splitit[n]:
                                #    splitrep = splitit[n].replace('-', '')
                                #    print ("non-character keyword...skipped on " + splitit[n])
                            elif str(splitit[n].lower()).startswith('v'):
                                logger.fdebug("possible verisoning..checking")
                                #we hit a versioning # - account for it
                                if splitit[n][1:].isdigit():
                                    comicversion = str(splitit[n])
                                    logger.fdebug("version found: " + str(comicversion))
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
                        totalcnt = int(len(splitit)-1)
                        logger.fdebug("splitit-len:" + str(totalcnt))
                        spercent = (wordcnt/totalcnt) * 100
                        logger.fdebug("we got " + str(spercent) + " percent.")
                        if int(spercent) >= 80:
                            logger.fdebug("it's a go captain... - we matched " + str(spercent) + "%!")
                        if int(spercent) < 80:
                            logger.fdebug("failure - we only got " + str(spercent) + "% right!")
                            continue
                        logger.fdebug("this should be a match!")
                        logger.fdebug("issue we are looking for is : " + str(findcomiciss[findloop]))
                        logger.fdebug("integer value of issue we are looking for : " + str(intIss))

                        #redudant code - should be called elsewhere...
                        if '.' in comic_iss:
                            comisschk_find = comic_iss.find('.')
                            comisschk_b4dec = comic_iss[:comisschk_find]
                            comisschk_decval = comic_iss[comisschk_find+1:]
                            logger.fdebug("Found IssueNumber: " + str(comic_iss))
                            logger.fdebug("..before decimal: " + str(comisschk_b4dec))
                            logger.fdebug("...after decimal: " + str(comisschk_decval))
                            #--let's make sure we don't wipe out decimal issues ;)
                            if int(comisschk_decval) == 0:
                                ciss = comisschk_b4dec
                                cintdec = int(comisschk_decval)
                            else:
                                if len(comisschk_decval) == 1:
                                    ciss = comisschk_b4dec + "." + comisschk_decval
                                    cintdec = int(comisschk_decval) * 10
                                else:
                                    ciss = comisschk_b4dec + "." + comisschk_decval.rstrip('0')
                                    cintdec = int(comisschk_decval.rstrip('0')) * 10
                            comintIss = (int(comisschk_b4dec) * 1000) + cintdec
                        else:
                            comintIss = int(comic_iss) * 1000
                        logger.fdebug("issue we found for is : " + str(comic_iss))
                        logger.fdebug("integer value of issue we are found : " + str(comintIss))

                        #issue comparison now as well
                        if int(intIss) == int(comintIss):
                            logger.fdebug('issues match!')
                            logger.info(u"Found " + str(ComicName) + " (" + str(comyear) + ") issue: " + str(IssueNumber) + " using " + str(nzbprov) )
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
                            logger.fdebug("link: " + str(linkstart))
                            logger.fdebug("linkforapi: " + str(linkapi))
                            #here we distinguish between rename and not.
                            #blackhole functinality---
                            #let's download the file to a temporary cache.

                            if mylar.BLACKHOLE:
                                logger.fdebug("using blackhole directory at : " + str(mylar.BLACKHOLE_DIR))
                                if os.path.exists(mylar.BLACKHOLE_DIR):
                                    filenamenzb = str(ComicName) + " " + str(IssueNumber) + " (" + str(comyear) + ").nzb"
                                    urllib.urlretrieve(linkapi, str(mylar.BLACKHOLE_DIR) + str(filenamenzb))
                                    logger.fdebug("filename saved to your blackhole as : " + str(filenamenzb))
                                    logger.info(u"Successfully sent .nzb to your Blackhole directory : " + str(mylar.BLACKHOLE_DIR) + str(filenamenzb) )
                                    nzbname = str(filenamenzb)
                            #end blackhole

                            else:
                                if nzbprov != 'nzb.su':
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

                                    filenamenzb = os.path.split(linkapi)[1]
                                    #filenzb = os.path.join(tmppath,filenamenzb)
                                    logger.fdebug("unalterted nzb name: " + str(filenamenzb))
                                    #let's send a clean copy to SAB because the names are random characters and/or could be stupid.
                                    ComicName = re.sub('[\:\,]', '', ComicName)
                                    filenzb = str(ComicName.replace(' ', '_')) + "_" + str(IssueNumber) + "_(" + str(comyear) + ")"
                                    logger.fdebug("prettified nzb name: " + str(filenzb))

                                    if mylar.RENAME_FILES == 1:
                                        logger.fdebug("Rename Files enabled..")
                                        filenzb = str(ComicName.replace(' ', '_')) + "_" + str(IssueNumber) + "_(" + str(comyear) + ")"
                                        logger.fdebug("this should be the same as prettified nzb name:" + str(filenzb))
                                        if mylar.REPLACE_SPACES:
                                            logger.fdebug("Replace spaces option enabled")
                                            logger.fdebug("replace character: " + str(mylar.REPLACE_CHAR))
                                            repchar = mylar.REPLACE_CHAR
                                            repurlchar = mylar.REPLACE_CHAR
                                        else:
                                            logger.fdebug("Replace spaces option NOT enabled")
                                            repchar = ' '
                                            repurlchar = "%20"
                                        #let's make sure there's no crap in the ComicName since it's O.G.
                                        logger.fdebug("original Name of comic: " + str(ComicName))
                                        ComicNM = re.sub('[\:\,]', '', str(ComicName))
                                        logger.fdebug("altered Name of comic: " + str(ComicNM))
                                        renameit = str(ComicNM) + " " + str(IssueNumber) + " (" + str(SeriesYear) + ")" + " " + "(" + str(comyear) + ")"
                                        logger.fdebug("altered Name with additional info: " + str(renameit))
                                        renamethis = renameit.replace(' ', repchar)
                                        logger.fdebug("...with replace spaces: " + str(renamethis))
                                        renamer1 = renameit.replace(' ', repurlchar)
                                        renamer = re.sub("\&", "%26", str(renamer1))
                                        logger.fdebug("...adjusting for url restrictions: " + str(renamer))

                                    filenext = str(filenzb) + ".nzb"
                                    savefile = os.path.join(tmppath, filenext)
                                    logger.fdebug("nzb file to be saved: " + str(savefile))

                                    try:
                                        urllib.urlretrieve(linkapi, str(savefile))                                
                                    except urllib.URLError:
                                        logger.fdebug(u"Unable to retrieve nzb using link: " + str(linkapi))
                                        logger.fdebug(u"Possibly unable to save nzb: " + str(savefile))
                                        logger.error(u"Unable to retrieve nzb file.")
                                        return

                                    if os.path.getsize(str(savefile)) == 0:
                                        logger.error(u"nzb size detected as zero bytes.")
                                        continue

                                    logger.info(u"Sucessfully retrieved nzb file using " + str(nzbprov))
                                    nzbname = str(filenzb)

                                elif nzbprov == 'nzb.su':
                                    logger.fdebug("NZB.SU - linkapi:" + str(linkapi))
                                    nzbname = re.sub(" ", "_", str(entry['title']))

                                logger.fdebug("nzbname used for post-processing:" + str(nzbname))

                                # let's build the send-to-SAB string now:
                                tmpapi = str(mylar.SAB_HOST)
                                logger.fdebug("send-to-SAB host string: " + str(tmpapi))
                                # nzb.su only works with direct links for some reason...
                                if nzbprov == 'nzb.su':
                                    SABtype = "/api?mode=addurl&name="
                                    savefileURL = str(linkapi)
                                else:
                                    SABtype = "/api?mode=addlocalfile&name="
                                    # if the savefile location has spaces in the path, could cause problems.
                                    # if the savefile has a &, escape it otherwise will botch up send-to-SAB link
                                    # let's adjust.
                                    saveF = re.sub("\&", "%26", str(savefile))
                                    savefileURL = re.sub(" ","%20", str(saveF))
                                tmpapi = tmpapi + str(SABtype)
                                logger.fdebug("...selecting API type: " + str(tmpapi))
                                tmpapi = tmpapi + str(savefileURL)
                                logger.fdebug("...attaching nzbfile: " + str(tmpapi))
                                # determine SAB priority
                                if mylar.SAB_PRIORITY:
                                    tmpapi = tmpapi + "&priority=" + str(sabpriority)
                                    logger.fdebug("...setting priority: " + str(tmpapi))
                                # if category is blank, let's adjust
                                if mylar.SAB_CATEGORY:
                                    tmpapi = tmpapi + "&cat=" + str(mylar.SAB_CATEGORY)
                                    logger.fdebug("...attaching category: " + str(tmpapi))
                                if mylar.RENAME_FILES == 1:
                                    tmpapi = tmpapi + "&script=ComicRN.py"
                                    logger.fdebug("...attaching rename script: " + str(tmpapi))
                                #final build of send-to-SAB    
                                tmpapi = tmpapi + "&apikey=" + str(mylar.SAB_APIKEY)

                                logger.fdebug("Completed send-to-SAB link: " + str(tmpapi))

                                try:
                                    urllib2.urlopen(tmpapi)
                                except urllib2.URLError:
                                    logger.error(u"Unable to send nzb file to SABnzbd")
                                    return

                                logger.info(u"Successfully sent nzb file to SABnzbd")
                                #delete the .nzb now.
                                if mylar.PROG_DIR is not "/" and nzbprov != 'nzb.su':
                                    logger.fdebug("preparing to remove temporary nzb file at: " + str(savefile))
                                    os.remove(savefile)
                                    logger.info(u"Removed temporary save file")
                            #raise an exception to break out of loop
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
        findloop+=1
        if foundc == "yes":
            foundcomic.append("yes")
            logger.fdebug("Found matching comic...preparing to send to Updater with IssueID: " + str(IssueID) + " and nzbname: " + str(nzbname))
            updater.nzblog(IssueID, nzbname)
            nzbpr == 0
            break
        elif foundc == "no" and nzbpr == 0:
            foundcomic.append("no")
            logger.fdebug("couldn't find a matching comic")
            if IssDateFix == "no":
                logger.info(u"Couldn't find Issue " + str(IssueNumber) + " of " + str(ComicName) + "(" + str(comyear) + "). Status kept as wanted." )
                break
    return foundc

def searchforissue(issueid=None, new=False):
    myDB = db.DBConnection()

    if not issueid:

        myDB = db.DBConnection()

        results = myDB.select('SELECT * from issues WHERE Status="Wanted"')
       
        new = True

        for result in results:
            comic = myDB.action('SELECT * from comics WHERE ComicID=?', [result['ComicID']]).fetchone()
            foundNZB = "none"
            SeriesYear = comic['ComicYear']
            IssueDate = result['IssueDate']
            if result['IssueDate'] == None: 
                ComicYear = comic['ComicYear']
            else: 
                ComicYear = str(result['IssueDate'])[:4]

            if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL) and (mylar.SAB_HOST):
                    foundNZB = search_init(result['ComicName'], result['Issue_Number'], str(ComicYear), comic['ComicYear'], IssueDate, result['IssueID'])
                    if foundNZB == "yes": 
                        #print ("found!")
                        updater.foundsearch(result['ComicID'], result['IssueID'])
                    else:
                        pass 
                        #print ("not found!")
    else:
        result = myDB.action('SELECT * FROM issues where IssueID=?', [issueid]).fetchone()
        ComicID = result['ComicID']
        comic = myDB.action('SELECT * FROM comics where ComicID=?', [ComicID]).fetchone()
        SeriesYear = comic['ComicYear']
        IssueDate = result['IssueDate']
        if result['IssueDate'] == None:
            IssueYear = comic['ComicYear']
        else:
            IssueYear = str(result['IssueDate'])[:4]

        foundNZB = "none"
        if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL) and (mylar.SAB_HOST):
            foundNZB = search_init(result['ComicName'], result['Issue_Number'], str(IssueYear), comic['ComicYear'], IssueDate, result['IssueID'])
            if foundNZB == "yes":
                #print ("found!")
                updater.foundsearch(ComicID=result['ComicID'], IssueID=result['IssueID'])
            else:
                pass 
                #print ("not found!")

def searchIssueIDList(issuelist):
    myDB = db.DBConnection()
    for issueid in issuelist:
        issue = myDB.action('SELECT * from issues WHERE IssueID=?', [issueid]).fetchone()
        comic = myDB.action('SELECT * from comics WHERE ComicID=?', [issue['ComicID']]).fetchone()
        print ("Checking for issue: " + str(issue['Issue_Number']))
        foundNZB = "none"
        SeriesYear = comic['ComicYear']
        if issue['IssueDate'] == None:
            ComicYear = comic['ComicYear']
        else:
            ComicYear = str(issue['IssueDate'])[:4]
        if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL) and (mylar.SAB_HOST):
                foundNZB = search_init(comic['ComicName'], issue['Issue_Number'], str(ComicYear), comic['ComicYear'], issue['IssueDate'], issue['IssueID'])
                if foundNZB == "yes":
                    #print ("found!")
                    updater.foundsearch(ComicID=issue['ComicID'], IssueID=issue['IssueID'])
                else:
                    pass
                    #print ("not found!")

