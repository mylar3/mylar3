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
from mylar import logger, db, updater, helpers, parseit

nzbsu_APIID = "22451"
nzbsu_APIkey = mylar.NZBSU_APIKEY
dognzb_APIkey = mylar.DOGNZB_APIKEY

LOG = mylar.LOG_DIR

import feedparser
import urllib
import os, errno
import string
import sqlite3 as lite
import sys
import getopt
import re
import time
from datetime import datetime

def search_init(ComicName, IssueNumber, ComicYear, SeriesYear):
    #print ("ComicName:" + ComicName)
    #print ("Issue:" + str(IssueNumber))
    if ComicYear == None: ComicYear = '2012'
    else: ComicYear = str(ComicYear)[:4]
    #print ("ComicYear:" + str(ComicYear))
    #print ("SeriesYear:" + str(SeriesYear))
    ##nzb provider selection##
    ##'dognzb' or 'nzb.su'
    nzbprovider = []
    nzbp = 0
    if mylar.NZBSU == 1:
        nzbprovider.append('nzb.su')
        nzbp+=1
        #print ("nzb.su search activated")
    if mylar.DOGNZB == 1:
        nzbprovider.append('dognzb')
        nzbp+=1
        #print ("dognzb search activated")
    # -------- 
    #  Xperimental
    if mylar.EXPERIMENTAL == 1:
        nzbprovider.append('experimental')
        nzbp+=1
        #print ("Experimental raw search activated!")
    # --------
    nzbpr = nzbp-1
    while (nzbpr >= 0 ):
        if nzbprovider[nzbpr] == 'experimental':
        #this is for experimental
            nzbprov = 'experimental'
            #print ("engaging experimental search for " + str(ComicName) + " " + str(IssueNumber))
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr)
            if findit == 'yes':
                break
            else:
                nzbpr-=1

        if nzbprovider[nzbpr] == 'nzb.su':
        # ----
        # this is for nzb.su
            d = feedparser.parse("http://nzb.su/rss?t=7030&dl=1&i=" + str(nzbsu_APIID) + "&r=" + str(nzbsu_APIkey))
            #print ("before NZBSU rss search.")
            #--LATER ?search.rss_find = RSS_SEARCH(ComicName, IssueNumber)
            #print ("after..")
            #if rss_find == 0:
            nzbprov = 'nzb.su'
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr)
            if findit == 'yes':
                break
            else:
                nzbpr-=1
        # ----
       
        elif nzbprovider[nzbpr] == 'dognzb':
        # this is for dognzb.com
            d = feedparser.parse("http://dognzb.cr/rss.cfm?r=" + str(dognzb_APIkey) + "&t=7030&num=100")
            #print ("Before DOGNZB  RSS search")
            #RSS_SEARCH(ComicName, IssueNumber)
            #print (ComicName + " : " + str(IssueNumber))
            nzbprov = 'dognzb'
            findit = NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr)
            if findit == 'yes':
                break
            else:
                nzbpr-=1
        # ----
    return findit

def RSS_Search(ComicName, IssueNumber):
    #this all needs to be REDONE...#    
    loopd = int(w-1)
    ssab = []
    ssabcount = 0
    print ("--------RSS MATCHING-----------------")
    for entry in d['entries']:
        # test for comic name here
        print loopd, entry['title']
        #print kc[loopd]
        #while (loopd > -1):
        #    if str(kc[loopd]).lower() in str(entry['title'].lower()):
        #print entry['title']
            # more precision - let's see if it's a hit on issue as well
            # Experimental process
            # since we're comparing the watchlist titles to the rss feed (for more robust matching)

            # the results will be 2nd/3rd variants, MR's, and comics on the watchlist but not necessarily 'NEW' rele$
            # let's first compare watchlist to release list
        incloop = int (tot -1)
        while (incloop > -1):
            #print ("Comparing " + str(entry['title']) + " - for - " + str(watchfnd[incloop]))
            cleantitle = helpers.cleanName(entry['title'])
            if str(watchfnd[incloop]).lower() in str(cleantitle).lower():
                #print ("MATCHED - " + str(watchfnd[incloop]).lower())
                if str(watchfndextra[incloop]).lower() is not None:
                    if str(watchfndextra[incloop]).lower() not in str(cleantitle).lower():
                        #print ("no extra matching - not a match")
                        #print (watchfndextra[incloop].lower())
                        break
                # now we have a match on watchlist and on release list, let's check if the issue is the same
                # on the feed and the releaselist
                # we have to remove the # sign from the ki[array] field first
                ki[incloop] = re.sub("\D", "", str(ki[incloop]))
                if str(ki[incloop]) in str(cleantitle):
                    print ("MATCH FOR DOWNLOAD!!\n    WATCHLIST: " + str(watchfnd[incloop]) + "\n    RLSLIST: " + str(kc[incloop]) + " ISSUE# " + str(ki[incloop]) + "\n    RSS: " + str(cleantitle))
                        #let's do the DOWNLOAD and send to SABnzbd
                        #this is for nzb.su - API LIMIT :(
                    linkstart = os.path.splitext(entry['link'])[0]
                        #following is JUST for nzb.su
                    if nzbprov == 'nzb.su':
                        linkit = os.path.splitext(entry['link'])[1]
                        linkit = linkit.replace("&", "%26")
                        thislink = str(linkstart) + str(linkit)
                    else:
                        # this should work for every other provider
                        linkstart = linkstart.replace("&", "%26")
                        thislink = str(linkstart)
                    tmp = "http://192.168.2.2:8085/api?mode=addurl&name=" + str(thislink) + "&pp=3&cat=comics&apikey=" + str(SABAPI)
                    print tmp
                    ssab.append(str(watchfnd[incloop]))
                    ssabcount+=1
                    urllib.urlopen(tmp);
                    # time.sleep(5)
            incloop-=1
                # - End of Experimental Process
                #break
            #loopd-=1
    print ("snatched " + str(ssabcount) + " out of " + str(tot) + " comics via rss...")
    return ssabcount

def NZB_SEARCH(ComicName, IssueNumber, ComicYear, SeriesYear, nzbprov, nzbpr):
    logger.info(u"Shhh be very quiet...I'm looking for " + ComicName + " issue: " + str(IssueNumber) + " using " + str(nzbprov))
    if nzbprov == 'nzb.su':
        apikey = mylar.NZBSU_APIKEY
    elif nzbprov == 'dognzb':
        apikey = mylar.DOGNZB_APIKEY
    elif nzbprov == 'experimental':
        apikey = 'none'
    #print ("-------------------------")

    if mylar.PREFERRED_QUALITY == 0: filetype = ""
    elif mylar.PREFERRED_QUALITY == 1: filetype = ".cbr"
    elif mylar.PREFERRED_QUALITY == 2: filetype = ".cbz"
    # search dognzb via api!
    # http://dognzb.cr/api?t=search&apikey=3ef08672ffa5abacf6e32f8f79cfeb1b&q=winter%20soldier&o=xml&cat=7030

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
    cm = re.sub(" ", "%20", str(findcomic[findcount]))
    #print (cmi)
    #---issue problem
    # if issue is '011' instead of '11' in nzb search results, will not have same
    # results. '011' will return different than '11', as will '009' and '09'.
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
        #print (str(comsearch[findloop]))
        while (cmloopit >= 1 ):
                # here we account for issue pattern variations
            if cmloopit == 3:
                comsearch[findloop] = comsrc + "%2000" + isssearch[findloop] + "%20" + str(filetype)
                #print (comsearch[findloop])
            elif cmloopit == 2:
                comsearch[findloop] = comsrc + "%200" + isssearch[findloop] + "%20" + str(filetype)
                #print (comsearch[findloop])
            elif cmloopit == 1:
                comsearch[findloop] = comsrc + "%20" + isssearch[findloop] + "%20" + str(filetype)
                #print (comsearch[findloop])
            #print ("NZB Provider set to: " + nzbprov)
            if nzbprov != 'experimental':
                if nzbprov == 'dognzb':
                    #print ("dog-search.")
                    findurl = "http://dognzb.cr/api?t=search&apikey=" + str(apikey) + "&q=" + str(comsearch[findloop]) + "&o=xml&cat=7030"
                elif nzbprov == 'nzb.su':
                    #print ("nzb.su search")
                    findurl = "http://nzb.su/api?t=search&q=" + str(comsearch[findloop]) + "&apikey=" + str(apikey) + "&o=xml&cat=7030"
                bb = feedparser.parse(findurl)
                #print (findurl)
            elif nzbprov == 'experimental':
                #print ("experimental raw search")
                bb = parseit.MysterBinScrape(comsearch[findloop])
            done = False
            foundc = "no"
            if bb == "no results":               
                #print ("no results found...attempting alternate search")
                pass
            elif (len(bb['entries']) == 0):
                #print ("Nothing found for : " + str(findcomic[findloop]) + " Issue: #" + str(findcomiciss[findloop]))
                #print ("Will try search again in 60 minutes...")
                foundc = "no"
            else:
                #print ("Found for: " + str(findcomic[findloop]))
                for entry in bb['entries']:
                    #print str(entry['title'])
                    cleantitle = helpers.cleanName(str(entry['title']))
                    if done:
                        break
                    #print ("title: " + str(cleantitle))
                    #print ("link: " + entry['link'])
                #let's narrow search down - take out year (2010), (2011), etc
                #let's check for first occurance of '(' as generally indicates
                #that the 'title' has ended
                    comlen = str(cleantitle).find(' (')
                    comsub = str(cleantitle)[:comlen]
                #print("first bracket occurs at position: " + str(comlen))
                #print("actual name with iss: " + str(comsub))
                #we need to now determine the last position BEFORE the issue number
                #take length of findcomic (add 1 for space) and subtract comlen
                #will result in issue
                    comspos = comsub.rfind(" ")
                #print ("last space @ position: " + str(comspos) )
                #print ("COMLEN: " + str(comlen) )
                    comiss = comsub[comspos:comlen]
                # -- we need to change if there is no space after issue #
                # -- and bracket ie...star trek tng 1(c2c)(2012) etc
                # --
                #print ("the comic issue is actually: #" + str(comiss))
                    splitit = []
                    splitcomp = []
                    comyx = comsub[:comspos]
                #print ("comyx: " + str(comyx))
                    splitchk = comyx.replace(" - ", " ")
                    splitit = splitchk.split(None)
                #print (str(splitit))
                    splitcomp = findcomic[findloop].split(None)
                #print ( "split length:" + str(len(splitit)) )
                    if len(splitit) != len(splitcomp):
                        #print ("incorrect comic lengths...not a match")
                        if str(comyx[:3]).lower() == "the":
                            #print ("THE word detected...attempting to adjust pattern matching")
                            splitMOD = splitchk[4:]
                            splitit = splitMOD.split(None)
                    else:
                        #print ("length match..proceeding")
                        n = 0
                        scount = 0
                        while ( n <= (len(splitit)-1) ):
                            #print ("Comparing: " + splitcomp[n] + " .to. " + splitit[n] )
                            if str(splitcomp[n].lower()) in str(splitit[n].lower()):
                                #print ("word matched on : " + splitit[n])
                                scount+=1
                            elif ':' in splitit[n] or '-' in splitit[n]:
                                splitrep = splitit[n].replace('-', '')
                                #print ("non-character keyword...skipped on " + splitit[n])
                                pass
                            else:
                                #print ("non-match for: " + splitit[n])
                                pass
                            n+=1
                        spercent = ( scount/int(len(splitit)) ) * 100
                        #print (str(spercent) + "% match")
                        #if spercent >= 75: print ("it's a go captain...")
                        #if spercent < 75: print ("failure - we only got " + str(spercent) + "% right!")
                        #print ("this should be a match!")
                        #issue comparison now as well
                        #print ("comiss:" + str(comiss))
                        #print ("findcomiss:" + str(findcomiciss[findloop]))
                        if int(findcomiciss[findloop]) == int(comiss):
                            #print ("issues match!")
                            #check for 'extra's - ie. Year
                            comex = str(cleantitle)[comlen:]
                            comspl = comex.split()
                            LENcomspl = len(comspl)
                            n = 0
                            while (LENcomspl > n):
                                if str(comyear) not in comspl[n]:
                                    #print (str(comyear) + " - not right year baby!")
                                    yearmatch = "false"
                                    break
                                else:
                                    #print (str(comyear) + " - years match baby!")
                                    yearmatch = "true"
                                    break
                                n+=1
                            if yearmatch == "false": break
                        ## -- start.
                        ## -- start.

                        ## -- inherit issue. Comic year is non-standard. nzb year is the year
                        ## -- comic was printed, not the start year of the comic series and
                        ## -- thus the deciding component if matches are correct or not

                        ## -- check to see if directory exists for given comic
                        #splitcom = ComicName.replace(' ', '_')
                        # here we should decide if adding year or not and format
                        #comyear = '_(2012)'
                        #compath = '/mount/mediavg/Comics/Comics/' + str(splitcom) + str(comyear)
                        #print ("The directory should be: " + str(compath))
                        #if os.path.isdir(str(compath)):
                        #    print("Directory exists!")
                        #else:
                        #    print ("Directory doesn't exist!")
                        #    try:
                        #        os.makedirs(str(compath))
                        #        print ("Directory successfully created at: " + str(compath))
                        #    except OSError.e:
                        #        if e.errno != errno.EEXIST:
                        #            raise
                        ## -- end.
                            linkstart = os.path.splitext(entry['link'])[0]
                            #print ("linkstart:" + str(linkstart))
                        #following is JUST for nzb.su
                            if nzbprov == 'nzb.su':
                                linkit = os.path.splitext(entry['link'])[1]
                                #print ("linkit: " + str(linkit))
                                linkit = linkit.replace("&", "%26")
                                linkapi = str(linkstart) + str(linkit)
                            else:
                                # this should work for every other provider
                                linkstart = linkstart.replace("&", "%26")
                                linkapi = str(linkstart)
                           #here we distinguish between rename and not.
                            #print (str(mylar.RENAME_FILES))
                            #pause sab first because it downloads too quick (cbr's are small!)
                            pauseapi = str(mylar.SAB_HOST) + "/api?mode=pause&apikey=" + str(mylar.SAB_APIKEY)
                            urllib.urlopen(pauseapi);

                            if mylar.RENAME_FILES == 1:
                                #let's download the file to a temporary cache.
                                tmppath = "cache/"
                                if os.path.exists(tmppath):
                                    #print ("before the path..")
                                    filenamenzb = os.path.split(linkapi)[1]
                                    #print ("filenamenzb:" + str(filenamenzb))
                                    filenzb = os.path.join(tmppath,filenamenzb)
                                    #print ("filenzb:" + str(filenzb))
                                    if nzbprov == 'nzb.su':
                                        filenzb = linkstart[21:]
                                    if nzbprov == 'experimental':
                                        filenzb = filenamenzb[6:]
                                        savefile = str(mylar.PROG_DIR) + "/" + str(tmppath) + str(filenzb) + ".nzb"
                                    if nzbprov == 'dognzb':
                                        filenzb == str(filenamenzb)
                                        savefile = str(mylar.PROG_DIR) + "/" + str(filenzb) + ".nzb" 
                                    #print ("filenzb:" + str(filenzb))
                                    urllib.urlretrieve(linkapi, str(savefile))
                                    #print ("Retrieved file to: " + str(savefile))
                                tmpapi = str(mylar.SAB_HOST) + "/api?mode=addlocalfile&name=" + str(savefile) + "&pp=3&cat=" + str(mylar.SAB_CATEGORY) + "&script=ComicRN.py&apikey=" + str(mylar.SAB_APIKEY)
                            else:
                                tmpapi = str(mylar.SAB_HOST) + "/api?mode=addurl&name=" + str(linkapi) + "&pp=3&cat=" + str(mylar.SAB_CATEGORY) + "&script=ComicRN.py&apikey=" + str(mylar.SAB_APIKEY)
                            #print (str(tmpapi))
                            time.sleep(5)
                            urllib.urlopen(tmpapi);
                            if mylar.RENAME_FILES == 1:
                                #let's give it 5 extra seconds to retrieve the nzb data...

                                time.sleep(5)
                              
                                outqueue = str(mylar.SAB_HOST) + "/api?mode=queue&start=START&limit=LIMIT&output=xml&apikey=" + str(mylar.SAB_APIKEY)
                                #print ("outqueue line generated")
                                urllib.urlopen(outqueue);
                                time.sleep(5)
                                #print ("passed api request to SAB")
                                #<slots><slot><filename>.nzb filename
                                #chang nzbfilename to include series(SAB will auto rename based on this)
                                #api?mode=queue&name=rename&value=<filename_nzi22ks>&value2=NEWNAME
                                from xml.dom.minidom import parseString
                                import urllib2
                                file = urllib2.urlopen(outqueue);
                                data = file.read()
                                file.close()
                                dom = parseString(data)
                                queue_slots = dom.getElementsByTagName('filename')
                                queue_cnt = len(queue_slots)
                                #print ("there are " + str(queue_cnt) + " things in SABnzbd's queue")
                                que = 0
                                slotmatch = "no"
                                for queue in queue_slots:
                                #retrieve the first xml tag (<tag>data</tag>)
                                #that the parser finds with name tagName:
                                    queue_file = dom.getElementsByTagName('filename')[que].firstChild.wholeText
                                    while ('Trying to fetch NZB' in queue_file):
                                        #let's keep waiting until nzbname is resolved by SABnzbd
                                        time.sleep(5)
                                        file = urllib2.urlopen(outqueue);
                                        data = file.read()
                                        file.close()
                                        dom = parseString(data)
                                        queue_file = dom.getElementsByTagName('filename')[que].firstChild.wholeText
                                    #print (str(queue_file))
                                    #print (str(filenzb))                              
                                    queue_file = queue_file.replace("_", " ")
                                    if str(queue_file) in str(filenzb):
                                        #print ("matched")
                                        slotmatch = "yes"
                                        slot_nzoid = dom.getElementsByTagName('nzo_id')[que].firstChild.wholeText
                                        #print ("slot_nzoid: " + str(slot_nzoid))
                                        break
                                    que=+1
                                if slotmatch == "yes":
                                    renameit = str(ComicName.replace(' ', '_')) + "_" + str(IssueNumber) + "_(" + str(SeriesYear) + ")" + "_" + "(" + str(comyear) + ")"
                                    nzo_ren = str(mylar.SAB_HOST) + "/api?mode=queue&name=rename&apikey=" + str(mylar.SAB_APIKEY) + "&value=" + str(slot_nzoid) + "&value2=" + str(renameit)
                                    print ("attempting to rename queue to " + str(nzo_ren))
                                    urllib2.urlopen(nzo_ren);
                                    print ("renamed!")
                                    #delete the .nzb now.
                                    #delnzb = str(mylar.PROG_DIR) + "/" + str(filenzb) + ".nzb"
                                    #if mylar.PROG_DIR is not "/":
                                       #os.remove(delnzb)
                                       #we need to track nzo_id to make sure finished downloaded with SABnzbd.
                                       #controlValueDict = {"nzo_id":      str(slot_nzoid)}
                                       #newValueDict = {"ComicName":       str(ComicName),
                                       #                "ComicYEAR":       str(comyear),
                                       #                "ComicIssue":      str(IssueNumber),
                                       #                "name":            str(filenamenzb)}
                                       #print ("updating SABLOG")
                                       #myDB = db.DBConnection()
                                       #myDB.upsert("sablog", newValueDict, controlValueDict)
                                else: logger.info(u"Couldn't locate file in SAB - are you sure it's being downloaded?")
                            #let's unpause queue now that we did our jobs.
                            resumeapi = str(mylar.SAB_HOST) + "/api?mode=resume&apikey=" + str(mylar.SAB_APIKEY)
                            urllib.urlopen(resumeapi);
                            #raise an exception to break out of loop
                            foundc = "yes"
                            done = True
                            break
                        else:
                            #print ("issues don't match..")
                            foundc = "no"
                #else:
                    #print ("this probably isn't the right match as the titles don't match")
                    #foundcomic.append("no")
                    #foundc = "no"
                if done == True: break
            cmloopit-=1
        findloop+=1
        if foundc == "yes":
            foundcomic.append("yes")
            #print ("we just found Issue: " + str(IssueNumber) + " of " + str(ComicName) + "(" + str(comyear) + ")" )
            logger.info(u"Found :" + str(ComicName) + " (" + str(comyear) + ") issue: " + str(IssueNumber) + " using " + str(nzbprov))
            break
        elif foundc == "no" and nzbpr <> 0:
            logger.info(u"More than one search provider given - trying next one.")
            #print ("Couldn't find with " + str(nzbprov) + ". More than one search provider listed, trying next option" )
        elif foundc == "no" and nzbpr == 0:
            foundcomic.append("no")
            #print ("couldn't find Issue " + str(IssueNumber) + " of " + str(ComicName) + "(" + str(comyear) + ")" )
            logger.info(u"Couldn't find Issue " + str(IssueNumber) + " of " + str(ComicName) + "(" + str(comyear) + "). Status kept as wanted." )
            break
    #print (foundc)
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
            if result['IssueDate'] == None: 
                ComicYear = comic['ComicYear']
            else: 
                ComicYear = str(result['IssueDate'])[:4]

            if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL) and (mylar.SAB_HOST):
                    foundNZB = search_init(result['ComicName'], result['Issue_Number'], str(ComicYear), comic['ComicYear'])
                    if foundNZB == "yes": 
                        #print ("found!")
                        updater.foundsearch(result['ComicID'], result['IssueID'])
                    else:
                        pass 
                        #print ("not found!")
    else:
        #print ("attempting to configure search parameters...")
        result = myDB.action('SELECT * FROM issues where IssueID=?', [issueid]).fetchone()
        ComicID = result['ComicID']
        comic = myDB.action('SELECT * FROM comics where ComicID=?', [ComicID]).fetchone()
        SeriesYear = comic['ComicYear']
        if result['IssueDate'] == None:
            IssueYear = comic['ComicYear']
        else:
            IssueYear = str(result['IssueDate'])[:4]

        foundNZB = "none"
        if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL) and (mylar.SAB_HOST):
            #print ("entering search parameters...") 
            foundNZB = search_init(result['ComicName'], result['Issue_Number'], str(IssueYear), comic['ComicYear'])
            if foundNZB == "yes":
                #print ("found!")
                updater.foundsearch(ComicID=result['ComicID'], IssueID=result['IssueID'])
            else:
                pass 
                #print ("not found!")

