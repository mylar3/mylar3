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

import time
import os
import sys
import shlex
import datetime
import re

import mylar
from mylar import logger, helpers, db, mb, albumart, cv, parseit, filechecker, search, updater

       
def is_exists(comicid):

    myDB = db.DBConnection()
    
    # See if the artist is already in the database
    comiclist = myDB.select('SELECT ComicID, ComicName from comics WHERE ComicID=?', [comicid])

    if any(comicid in x for x in comiclist):
        logger.info(comiclist[0][1] + u" is already in the database.")
        return False
    else:
        return False


def addComictoDB(comicid):
    
    # Putting this here to get around the circular import. Will try to use this to update images at later date.
    from mylar import cache
    
    myDB = db.DBConnection()
    
    # We need the current minimal info in the database instantly
    # so we don't throw a 500 error when we redirect to the artistPage

    controlValueDict = {"ComicID":     comicid}

    dbcomic = myDB.action('SELECT * FROM comics WHERE ComicID=?', [comicid]).fetchone()
    if dbcomic is None:
        newValueDict = {"ComicName":   "Comic ID: %s" % (comicid),
                "Status":   "Loading"}
    else:
        newValueDict = {"Status":   "Loading"}

    myDB.upsert("comics", newValueDict, controlValueDict)

    # we need to lookup the info for the requested ComicID in full now        
    comic = cv.getComic(comicid,'comic')

    if not comic:
        logger.warn("Error fetching comic. ID for : " + comicid)
        if dbcomic is None:
            newValueDict = {"ComicName":   "Fetch failed, try refreshing. (%s)" % (comicid),
                    "Status":   "Active"}
        else:
            newValueDict = {"Status":   "Active"}
        myDB.upsert("comics", newValueDict, controlValueDict)
        return
    
    if comic['ComicName'].startswith('The '):
        sortname = comic['ComicName'][4:]
    else:
        sortname = comic['ComicName']
        

    logger.info(u"Now adding/updating: " + comic['ComicName'])
    #--Now that we know ComicName, let's try some scraping
    #--Start
    # gcd will return issue details (most importantly publishing date)
    gcdinfo=parseit.GCDScraper(comic['ComicName'], comic['ComicYear'], comic['ComicIssues'], comicid) 
    if gcdinfo == "No Match":
        logger.warn("No matching result found for " + comic['ComicName'] + " (" + comic['ComicYear'] + ")" )
        updater.no_searchresults(comicid)
        nomatch = "true"
        return nomatch
    logger.info(u"Sucessfully retrieved details for " + comic['ComicName'] )
    # print ("Series Published" + parseit.resultPublished)
    #--End

    #comic book location on machine
    # setup default location here
    if ':' in comic['ComicName']: 
        comicdir = comic['ComicName'].replace(':','')
    else: comicdir = comic['ComicName']
    comlocation = mylar.DESTINATION_DIR + "/" + comicdir + " (" + comic['ComicYear'] + ")"
    if mylar.DESTINATION_DIR == "":
        logger.error(u"There is no general directory specified - please specify in Config/Post-Processing.")
        return
    if mylar.REPLACE_SPACES:
        #mylar.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
        comlocation = comlocation.replace(' ', mylar.REPLACE_CHAR)
    #if it doesn't exist - create it (otherwise will bugger up later on)
    if os.path.isdir(str(comlocation)):
        logger.info(u"Directory (" + str(comlocation) + ") already exists! Continuing...")
    else:
        #print ("Directory doesn't exist!")
        try:
            os.makedirs(str(comlocation))
            logger.info(u"Directory successfully created at: " + str(comlocation))
        except OSError.e:
            if e.errno != errno.EEXIST:
                raise

    #try to account for CV not updating new issues as fast as GCD
    #seems CV doesn't update total counts
    #comicIssues = gcdinfo['totalissues']
    if gcdinfo['gcdvariation'] == "cv":
        comicIssues = str(int(comic['ComicIssues']) + 1)
    else:
        comicIssues = comic['ComicIssues']

    controlValueDict = {"ComicID":      comicid}
    newValueDict = {"ComicName":        comic['ComicName'],
                    "ComicSortName":    sortname,
                    "ComicYear":        comic['ComicYear'],
                    "ComicImage":       comic['ComicImage'],
                    "Total":            comicIssues,
                    "ComicLocation":    comlocation,
                    "ComicPublisher":   comic['ComicPublisher'],
                    "ComicPublished":   parseit.resultPublished,
                    "DateAdded":        helpers.today(),
                    "Status":           "Loading"}
    
    myDB.upsert("comics", newValueDict, controlValueDict)
    
    issued = cv.getComic(comicid,'issue')
    logger.info(u"Sucessfully retrieved issue details for " + comic['ComicName'] )
    n = 0
    iscnt = int(comicIssues)
    issid = []
    issnum = []
    issname = []
    issdate = []
    int_issnum = []
    #let's start issue #'s at 0 -- thanks to DC for the new 52 reboot! :)
    latestiss = "0"
    latestdate = "0000-00-00"
    #print ("total issues:" + str(iscnt))
    #---removed NEW code here---
    logger.info(u"Now adding/updating issues for" + comic['ComicName'])

    # file check to see if issue exists
    logger.info(u"Checking directory for existing issues.")
    #fc = filechecker.listFiles(dir=comlocation, watchcomic=comic['ComicName'])
    #havefiles = 0

    #fccnt = int(fc['comiccount'])
    #logger.info(u"Found " + str(fccnt) + "/" + str(iscnt) + " issues of " + comic['ComicName'] + "...verifying")
    #fcnew = []

    while (n <= iscnt):
        #---NEW.code
        try:
            firstval = issued['issuechoice'][n]
        except IndexError:
            break
        cleanname = helpers.cleanName(firstval['Issue_Name'])
        issid = str(firstval['Issue_ID'])
        issnum = str(firstval['Issue_Number'])
        issname = cleanname
        if '.' in str(issnum):
            issn_st = str(issnum).find('.')
            issn_b4dec = str(issnum)[:issn_st]
            #if the length of decimal is only 1 digit, assume it's a tenth
            dec_is = str(issnum)[issn_st + 1:]
            if len(dec_is) == 1:
                dec_nisval = int(dec_is) * 10
                iss_naftdec = str(dec_nisval)
            if len(dec_is) == 2:
                dec_nisval = int(dec_is)
                iss_naftdec = str(dec_nisval)
            iss_issue = issn_b4dec + "." + iss_naftdec
            issis = (int(issn_b4dec) * 1000) + dec_nisval
        else: issis = int(issnum) * 1000

        bb = 0
        while (bb <= iscnt):
            try: 
                gcdval = gcdinfo['gcdchoice'][bb]
            except IndexError:
                #account for gcd variation here
                if gcdinfo['gcdvariation'] == 'gcd':
                    #print ("gcd-variation accounted for.")
                    issdate = '0000-00-00'
                    int_issnum =  int ( issis / 1000 )
                break
            if 'nn' in str(gcdval['GCDIssue']):
                #no number detected - GN, TP or the like
                logger.warn(u"Non Series detected (Graphic Novel, etc) - cannot proceed at this time.")
                updater.no_searchresults(comicid)
                return
            elif '.' in str(gcdval['GCDIssue']):
                issst = str(gcdval['GCDIssue']).find('.')
                issb4dec = str(gcdval['GCDIssue'])[:issst]
                #if the length of decimal is only 1 digit, assume it's a tenth
                decis = str(gcdval['GCDIssue'])[issst+1:]
                if len(decis) == 1:
                    decisval = int(decis) * 10
                    issaftdec = str(decisval)
                if len(decis) == 2:
                    decisval = int(decis)
                    issaftdec = str(decisval)
                gcd_issue = issb4dec + "." + issaftdec
                gcdis = (int(issb4dec) * 1000) + decisval
            else:
                gcdis = int(str(gcdval['GCDIssue'])) * 1000
            if gcdis == issis:
                issdate = str(gcdval['GCDDate'])
                int_issnum = int( gcdis / 1000 )
                #get the latest issue / date using the date.
                if gcdval['GCDDate'] > latestdate:
                    latestiss = str(issnum)
                    latestdate = str(gcdval['GCDDate'])
                    break
                #bb = iscnt
            bb+=1
        #print("(" + str(n) + ") IssueID: " + str(issid) + " IssueNo: " + str(issnum) + " Date" + str(issdate))
        #---END.NEW.

        # check if the issue already exists
        iss_exists = myDB.select('SELECT * from issues WHERE IssueID=?', [issid])

        # Only change the status & add DateAdded if the issue is not already in the database
        if not len(iss_exists):
            newValueDict['DateAdded'] = helpers.today()

        controlValueDict = {"IssueID":  issid}
        newValueDict = {"ComicID":            comicid,
                        "ComicName":          comic['ComicName'],
                        "IssueName":          issname,
                        "Issue_Number":       issnum,
                        "IssueDate":          issdate,
                        "Int_IssueNumber":    int_issnum
                        }        
        if mylar.AUTOWANT_ALL:
            newValueDict['Status'] = "Wanted"
            #elif release_dict['releasedate'] > helpers.today() and mylar.AUTOWANT_UPCOMING:
            #    newValueDict['Status'] = "Wanted"
        else:
            newValueDict['Status'] = "Skipped"

        myDB.upsert("issues", newValueDict, controlValueDict)
        n+=1

#        logger.debug(u"Updating comic cache for " + comic['ComicName'])
#        cache.getThumb(ComicID=issue['issueid'])
            
#        logger.debug(u"Updating cache for: " + comic['ComicName'])
#        cache.getThumb(ComicIDcomicid)

    #check for existing files...
    updater.forceRescan(comicid)

    controlValueStat = {"ComicID":     comicid}
    newValueStat = {"Status":          "Active",
                    "LatestIssue":     latestiss,
                    "LatestDate":      latestdate
                   }

    myDB.upsert("comics", newValueStat, controlValueStat)
  
    logger.info(u"Updating complete for: " + comic['ComicName'])
    
    # lets' check the pullist for anyting at this time as well since we're here.
    #if mylar.AUTOWANT_UPCOMING:
    #    logger.info(u"Checking this week's pullist for new issues of " + str(comic['ComicName']))
    #    updater.newpullcheck()

    #here we grab issues that have been marked as wanted above...
  
    results = myDB.select("SELECT * FROM issues where ComicID=? AND Status='Wanted'", [comicid])    
    if results:
        logger.info(u"Attempting to grab wanted issues for : "  + comic['ComicName'])

        for result in results:
            foundNZB = "none"
            if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL) and (mylar.SAB_HOST):
                foundNZB = search.searchforissue(result['IssueID'])
                if foundNZB == "yes":
                    updater.foundsearch(result['ComicID'], result['IssueID'])
    else: logger.info(u"No issues marked as wanted for " + comic['ComicName'])

    logger.info(u"Finished grabbing what I could.")
