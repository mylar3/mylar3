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

def search_init(ComicName, IssueNumber, ComicYear, SeriesYear, IssueDate, IssueID):
    if ComicYear == None: ComicYear = '2012'
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
        nzbprovider.append('newznab')
        nzbp+=1
        #newznabs = 0
        newznab_hosts = [(mylar.NEWZNAB_HOST, mylar.NEWZNAB_APIKEY, mylar.NEWZNAB_ENABLED)]

        for newznab_host in mylar.EXTRA_NEWZNABS:
            if newznab_host[2] == '1' or newznab_host[2] == 1:
                newznab_hosts.append(newznab_host)              
                newznabs = newznabs + 1

        #categories = "7030"

        #for newznab_host in newznab_hosts:
        #    mylar.NEWZNAB_APIKEY = newznab_host[1]
        #    mylar.NEWZNAB_HOST = newznab_host[0]

    # --------
    nzbpr = nzbp-1
    findit = 'no'

    #fix for issue dates between Nov-Dec/Jan
    IssDt = str(IssueDate)[5:7]
    if IssDt == "12" or IssDt == "11":
         ComicYearFix = str(int(ComicYear) + 1)
         IssDateFix = "yes"
    else:
         IssDateFix = "no"

    while (nzbpr >= 0 ):
    
        if nzbprovider[nzbpr] == 'newznab':
        #this is for newznab
            nzbprov = 'newznab'
            for newznab_host in newznab_hosts:
                findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, newznab_host)
                if findit == 'yes':
                    break
                else:
                    if IssDateFix == "yes":
                        logger.info(u"Hang on - this issue was published between Nov/Dec of " + str(ComicYear) + "...adjusting to " + str(ComicYearFix) + " and retrying...")
                        findit = NZB_SEARCH(ComicName, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID, newznab_host)
                        if findit == 'yes':
                            break
            nzbpr-=1

        if nzbprovider[nzbpr] == 'experimental':
        #this is for experimental
            nzbprov = 'experimental'
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
            if findit == 'yes':
                break
            else:
                if IssDateFix == "yes":
                    logger.info(u"Hang on - this issue was published between Nov/Dec of " + str(ComicYear) + "...adjusting to " + str(ComicYearFix) + " and retrying...")
                    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                    if findit == 'yes':
                        break
            nzbpr-=1

        if nzbprovider[nzbpr] == 'nzb.su':
        # ----
        # this is for nzb.su
            #d = feedparser.parse("http://nzb.su/rss?t=7030&dl=1&i=" + str(nzbsu_APIID) + "&r=" + str(nzbsu_APIkey))
            #--LATER ?search.rss_find = RSS_SEARCH(ComicName, IssueNumber)
            #if rss_find == 0:
            nzbprov = 'nzb.su'
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
            if findit == 'yes':
                break
            else:
                if IssDateFix == "yes":
                    logger.info(u"Hang on - this issue was published between Nov/Dec of " + str(ComicYear) + "...adjusting to " + str(ComicYearFix) + " and retrying...")
                    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                    if findit == 'yes':
                        break

            nzbpr-=1

        # ----
       
        elif nzbprovider[nzbpr] == 'dognzb':
        # this is for dognzb.com
            #d = feedparser.parse("http://dognzb.cr/rss.cfm?r=" + str(dognzb_APIkey) + "&t=7030&num=100")
            #RSS_SEARCH(ComicName, IssueNumber)
            nzbprov = 'dognzb'
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
            if findit == 'yes':
                break
            else:
                if IssDateFix == "yes":
                    logger.info(u"Hang on - this issue was published between Dec/Jan of " + str(ComicYear) + "...adjusting to " + str(ComicYearFix) + " and retrying...")
                    findit = NZB_SEARCH(ComicName, IssueNumber, ComicYearFix, SeriesYear, nzbprov, nzbpr, IssDateFix, IssueID)
                    if findit == 'yes':
                        break

            nzbpr-=1

        # ----
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
        print ("using Newznab of : " + str(host_newznab))

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
    IssueNumber = str(re.sub("\.00", "", str(IssueNumber)))
    #print ("issueNumber" + str(IssueNumber))
    findcomiciss.append(str(re.sub("\D", "", str(IssueNumber))))
    
    #print ("we need : " + str(findcomic[findcount]) + " issue: #" + str(findcomiciss[findcount]))
    # replace whitespace in comic name with %20 for api search
    cm1 = re.sub(" ", "%20", str(findcomic[findcount]))
    cm = re.sub("\&", "%26", str(cm1))
    #print (cmi)
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

    #---issue problem
    # if issue is '011' instead of '11' in nzb search results, will not have same
    # results. '011' will return different than '11', as will '009' and '09'.

    while (findloop < (findcount) ):
        comsrc = comsearch[findloop]
        while (cmloopit >= 1 ):
                # here we account for issue pattern variations
            if cmloopit == 3:
                comsearch[findloop] = comsrc + "%2000" + isssearch[findloop] + "%20" + str(filetype)
            elif cmloopit == 2:
                comsearch[findloop] = comsrc + "%200" + isssearch[findloop] + "%20" + str(filetype)
            elif cmloopit == 1:
                comsearch[findloop] = comsrc + "%20" + isssearch[findloop] + "%20" + str(filetype)
            if nzbprov != 'experimental':
                if nzbprov == 'dognzb':
                    findurl = "http://dognzb.cr/api?t=search&apikey=" + str(apikey) + "&q=" + str(comsearch[findloop]) + "&o=xml&cat=7030"
                elif nzbprov == 'nzb.su':
                    findurl = "http://nzb.su/api?t=search&q=" + str(comsearch[findloop]) + "&apikey=" + str(apikey) + "&o=xml&cat=7030"
                elif nzbprov == 'newznab':
                    findurl = str(host_newznab) + "/api?t=search&q=" + str(comsearch[findloop]) + "&apikey=" + str(apikey) + "&o=xml&cat=7030"
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
                    thisentry = str(entry['title'])
                    logger.fdebug("Entry: " + str(thisentry))
                    cleantitle = re.sub('_', ' ', str(entry['title']))
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
                        if 'digital' in m[cnt] and len(m[cnt]) == 7: 
                            pass
                            #print ("digital edition")
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
                    comic_iss_b4 = re.sub('[\-\:\,]', '', str(comic_andiss))
                    logger.fdebug("original nzb comic and issue: " + str(comic_iss_b4))
                    #log2file = log2file + "o.g.comic: " + str(comic_iss_b4) + "\n"
                    comic_iss = comic_iss_b4.replace('.',' ')
                    logger.fdebug("adjusted nzb comic and issue: " + str(comic_iss))
                    splitit = comic_iss.split(None)
                    #something happened to dognzb searches or results...added a '.' in place of spaces
                    #screwed up most search results with dognzb. Let's try to adjust.
                    watchcomic_split = findcomic[findloop].split(None)
                    #log2file = log2file + "adjusting from: " + str(comic_iss_b4) + " to: " + str(comic_iss) + "\n"
                    bmm = re.findall('v\d', comic_iss)
                    if len(bmm) > 0: splitst = len(splitit) - 2
                    else: splitst = len(splitit) - 1
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
                                logger.fdebug("issue section")
                                if splitit[n].isdigit():
                                    logger.fdebug("issue detected")
                                    comiss = splitit[n]
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
                        spercent = ( scount/int(len(splitit)) ) * 100
                        logger.fdebug(str(spercent) + "% match")
                        #if spercent >= 80:
                        #    logger.fdebug("it's a go captain... - we matched " + str(spercent) + "%!")
                        #if spercent < 80:
                        #    logger.fdebug("failure - we only got " + str(spercent) + "% right!")
                        #    continue
                        logger.fdebug("this should be a match!")
                        #issue comparison now as well
                        if int(findcomiciss[findloop]) == int(comiss):
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
                            #here we distinguish between rename and not.
                            #blackhole functinality---
                            #let's download the file to a temporary cache.

                            if mylar.BLACKHOLE:
                                if os.path.exists(mylar.BLACKHOLE_DIR):
                                    filenamenzb = str(ComicName) + " " + str(IssueNumber) + " (" + str(comyear) + ").nzb"
                                    urllib.urlretrieve(linkapi, str(mylar.BLACKHOLE_DIR) + str(filenamenzb))
                                    logger.info(u"Successfully sent .nzb to your Blackhole directory : " + str(mylar.BLACKHOLE_DIR) + str(filenamenzb) )
                            #end blackhole

                            else:
                                tmppath = mylar.CACHE_DIR
                                if os.path.exists(tmppath):
                                    pass
                                else:
                                #let's make the dir.
                                    try:
                                        os.makedirs(str(mylar.CACHE_DIR))
                                        logger.info(u"Cache Directory successfully created at: " + str(mylar.CACHE_DIR))

                                    except OSError.e:
                                        if e.errno != errno.EEXIST:
                                            raise

                                filenamenzb = os.path.split(linkapi)[1]
                                #filenzb = os.path.join(tmppath,filenamenzb)
                                if nzbprov == 'nzb.su' or nzbprov == 'newznab' or nzbprov == 'experimental':
                                    #filenzb = linkstart[21:]
                                #elif nzbprov == 'experimental':
                                    #let's send a clean copy to SAB because the name could be stupid.
                                    filenzb = str(ComicName.replace(' ', '_')) + "_" + str(IssueNumber) + "_(" + str(comyear) + ")"
                                    #filenzb = str(filenamenzb)
                                elif nzbprov == 'dognzb':
                                    filenzb = str(filenamenzb)

                                if mylar.RENAME_FILES == 1:
                                    filenzb = str(ComicName.replace(' ', '_')) + "_" + str(IssueNumber) + "_(" + str(comyear) + ")"
                                    if mylar.REPLACE_SPACES:
                                        repchar = mylar.REPLACE_CHAR
                                        repurlchar = mylar.REPLACE_CHAR
                                    else:
                                        repchar = ' '
                                        repurlchar = "%20"
                                    #let's make sure there's no crap in the ComicName since it's O.G.
                                    ComicNM = re.sub('[\:\,]', '', str(ComicName))
                                    renameit = str(ComicNM) + " " + str(IssueNumber) + " (" + str(SeriesYear) + ")" + " " + "(" + str(comyear) + ")"
                                    renamethis = renameit.replace(' ', repchar)
                                    renamer1 = renameit.replace(' ', repurlchar)
                                    renamer = re.sub("\&", "%26", str(renamer1))

                                savefile = str(tmppath) + "/" + str(filenzb) + ".nzb"
                                print "savefile:" + str(savefile)

                                try:
                                    urllib.urlretrieve(linkapi, str(savefile))                                
                                except urllib.URLError:
                                    logger.error(u"Unable to retrieve nzb file.")
                                    return

                                if os.path.getsize(str(savefile)) == 0:
                                    logger.error(u"nzb size detected as zero bytes.")
                                    continue

                                logger.info(u"Sucessfully retrieved nzb file using " + str(nzbprov))
                                nzbname = str(filenzb)
                                print "nzbname:" + str(nzbname)
# NOT NEEDED ANYMORE.
								#print (str(mylar.RENAME_FILES))
								
								#check sab for current pause status
#                                sabqstatusapi = str(mylar.SAB_HOST) + "/api?mode=qstatus&output=xml&apikey=" + str(mylar.SAB_APIKEY)
#                                file = urllib2.urlopen(sabqstatusapi);
#                                data = file.read()
#                                file.close()
#                                dom = parseString(data)
#                                for node in dom.getElementsByTagName('paused'):
#									pausestatus = node.firstChild.wholeText
									#print pausestatus
#                                if pausestatus != 'True':
									#pause sab first because it downloads too quick (cbr's are small!)
#                                    pauseapi = str(mylar.SAB_HOST) + "/api?mode=pause&apikey=" + str(mylar.SAB_APIKEY)
#                                    urllib2.urlopen(pauseapi);
                                    #print "Queue paused"
                                #else:
                                    #print "Queue already paused"
# END OF NOT NEEDED.                                
#redudant.                       if mylar.RENAME_FILES == 1:
                                tmpapi = str(mylar.SAB_HOST) + "/api?mode=addlocalfile&name=" + str(savefile) + "&pp=3&cat=" + str(mylar.SAB_CATEGORY) + "&script=ComicRN.py&apikey=" + str(mylar.SAB_APIKEY)
#outdated...
#                                else:
#                                    tmpapi = str(mylar.SAB_HOST) + "/api?mode=addurl&name=" + str(linkapi) + "&pp=3&cat=" + str(mylar.SAB_CATEGORY) + "&script=ComicRN.py&apikey=" + str(mylar.SAB_APIKEY)
#                               time.sleep(5)
#end outdated.
                                print "send-to-SAB:" + str(tmpapi)
                                try:
                                    urllib2.urlopen(tmpapi)
                                except urllib2.URLError:
                                    logger.error(u"Unable to send nzb file to SABnzbd")
                                    return

                                logger.info(u"Successfully sent nzb file to SABnzbd")
#---NOT NEEDED ANYMORE.
#                                if mylar.RENAME_FILES == 1:
                                    #let's give it 5 extra seconds to retrieve the nzb data...

#                                    time.sleep(5)
                              
#                                    outqueue = str(mylar.SAB_HOST) + "/api?mode=queue&start=START&limit=LIMIT&output=xml&apikey=" + str(mylar.SAB_APIKEY)
#                                    urllib2.urlopen(outqueue);
#                                    time.sleep(5)
                                #<slots><slot><filename>.nzb filename
                                #chang nzbfilename to include series(SAB will auto rename based on this)
                                #api?mode=queue&name=rename&value=<filename_nzi22ks>&value2=NEWNAME
#                                    file = urllib2.urlopen(outqueue);
#                                    data = file.read()
#                                    file.close()
#                                    dom = parseString(data)
#                                    queue_slots = dom.getElementsByTagName('filename')
#                                    queue_cnt = len(queue_slots)
                                    #print ("there are " + str(queue_cnt) + " things in SABnzbd's queue")
#                                    que = 0
#                                    slotmatch = "no"
#                                    for queue in queue_slots:
                                    #retrieve the first xml tag (<tag>data</tag>)
                                    #that the parser finds with name tagName:
#                                        queue_file = dom.getElementsByTagName('filename')[que].firstChild.wholeText
#                                        while ('Trying to fetch NZB' in queue_file):
                                            #let's keep waiting until nzbname is resolved by SABnzbd
#                                            time.sleep(5)
#                                            file = urllib2.urlopen(outqueue);
#                                            data = file.read()
#                                            file.close()
#                                            dom = parseString(data)
#                                            queue_file = dom.getElementsByTagName('filename')[que].firstChild.wholeText
                                        #print ("queuefile:" + str(queue_file))
                                        #print ("filenzb:" + str(filenzb))                              
#                                        queue_file = queue_file.replace("_", " ")
#                                        if str(queue_file) in str(filenzb):
                                            #print ("matched")
#                                            slotmatch = "yes"
#                                            slot_nzoid = dom.getElementsByTagName('nzo_id')[que].firstChild.wholeText
                                            #print ("slot_nzoid: " + str(slot_nzoid))
#                                            break
#                                        que+=1
#                                    if slotmatch == "yes":
#--start - this is now broken - SAB Priority.
#
#                                        nzo_prio = str(mylar.SAB_HOST) + "/api?mode=queue&name=priority&apikey=" + str(mylar.SAB_APIKEY) + "&value=" + str(slot_nzoid) + "&value2=" + str(sabpriority)
#                                        urllib2.urlopen(nzo_prio);
#
#--end
#                                        nzo_ren = str(mylar.SAB_HOST) + "/api?mode=queue&name=rename&apikey=" + str(mylar.SAB_APIKEY) + "&value=" + str(slot_nzoid) + "&value2=" + str(renamer)
#                                        urllib2.urlopen(nzo_ren);
#                                        logger.info(u"Renamed nzb file in SABnzbd queue to : " + str(renamethis))
#---END OF NOT NEEDED.
                                        #delete the .nzb now.
                                if mylar.PROG_DIR is not "/":
                                    os.remove(savefile)
                                    logger.info(u"Removed temporary save file")
#--- NOT NEEDED.
                                            #we need to track nzo_id to make sure finished downloaded with SABnzbd.
                                            #controlValueDict = {"nzo_id":      str(slot_nzoid)}
                                            #newValueDict = {"ComicName":       str(ComicName),
                                            #                "ComicYEAR":       str(comyear),
                                            #                "ComicIssue":      str(IssueNumber),
                                            #                "name":            str(filenamenzb)}
                                            #print ("updating SABLOG")
                                            #myDB = db.DBConnection()
                                            #myDB.upsert("sablog", newValueDict, controlValueDict)
#                                    else: logger.info(u"Couldn't locate file in SAB - are you sure it's being downloaded?")
                                #resume sab if it was running before we started
#                                if pausestatus != 'True':
                                    #let's unpause queue now that we did our jobs.
#                                    resumeapi = str(mylar.SAB_HOST) + "/api?mode=resume&apikey=" + str(mylar.SAB_APIKEY)
#                                    urllib2.urlopen(resumeapi);
                                #else:
									#print "Queue already paused"
#--- END OF NOT NEEDED.
                            #raise an exception to break out of loop
                            foundc = "yes"
                            done = True
                            break
                        else:
                            log2file = log2file + "issues don't match.." + "\n"
                            foundc = "no"
                    # write the log to file now so it logs / file found.
                    #newlog = mylar.CACHE_DIR + "/searchlog.txt"
                    #local_file = open(newlog, "a")
                    #pickle.dump(str(log2file), local_file)
                    #local_file.write(log2file)
                    #local_file.close
                    #log2file = ""
                if done == True: break
            cmloopit-=1
        findloop+=1
        if foundc == "yes":
            print ("found-yes")
            foundcomic.append("yes")
            updater.nzblog(IssueID, nzbname)
            nzbpr == 0
            break
        elif foundc == "no" and nzbpr <> 0:
            logger.info(u"More than one search provider given - trying next one.")
        elif foundc == "no" and nzbpr == 0:
            foundcomic.append("no")
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

