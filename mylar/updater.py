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
from xml.dom.minidom import parseString
import urllib2
import shlex
import re 
import os

import mylar
from mylar import db, logger, helpers, filechecker

def dbUpdate():

    myDB = db.DBConnection()

    activecomics = myDB.select('SELECT ComicID, ComicName from comics WHERE Status="Active" or Status="Loading" order by LastUpdated ASC')

    logger.info('Starting update for %i active comics' % len(activecomics))
    
    for comic in activecomics:
    
        comicid = comic[0]
        mylar.importer.addComictoDB(comicid)
        
    logger.info('Update complete')


def latest_update(ComicID, LatestIssue, LatestDate):
    # here we add to comics.latest
    myDB = db.DBConnection()
    latestCTRLValueDict = {"ComicID":      ComicID}
    newlatestDict = {"LatestIssue":      str(LatestIssue),
                    "LatestDate":       str(LatestDate)}
    myDB.upsert("comics", newlatestDict, latestCTRLValueDict)

def upcoming_update(ComicID, ComicName, IssueNumber, IssueDate):
    # here we add to upcoming table...
    myDB = db.DBConnection()

    controlValue = {"ComicID":      ComicID}
    newValue = {"ComicName":        str(ComicName),
                "IssueNumber":      str(IssueNumber),
                "IssueDate":        str(IssueDate)}


    issuechk = myDB.action("SELECT * FROM issues WHERE ComicID=? AND Issue_Number=?", [ComicID, IssueNumber]).fetchone()
    if issuechk is None: pass
    else:
        #print ("checking..." + str(issuechk['ComicName']) + " Issue: " + str(issuechk['Issue_Number']))
        #print ("existing status: " + str(issuechk['Status']))
        control = {"IssueID":   issuechk['IssueID']}
        if mylar.AUTOWANT_UPCOMING:
            newValue['Status'] = "Wanted"
            values = { "Status":  "Wanted"}
        if issuechk['Status'] == "Snatched":
            values = { "Status":   "Snatched"}
            newValue['Status'] = "Snatched"
        elif issuechk['Status'] == "Downloaded":
            values = { "Status":    "Downloaded"}
            newValue['Status'] = "Downloaded"
        else:
            values = { "Status":    "Skipped"}
            newValue['Status'] = "Skipped"

        myDB.upsert("upcoming", newValue, controlValue)
        myDB.upsert("issues", values, control)


def weekly_update(ComicName):
    # here we update status of weekly table...
    myDB = db.DBConnection()
    controlValue = { "COMIC":         str(ComicName)}
    if mylar.AUTOWANT_UPCOMING:
        newValue = {"STATUS":             "Wanted"}
    else:
        newValue = {"STATUS":             "Skipped"}
    myDB.upsert("weekly", newValue, controlValue)

def newpullcheck():
    # When adding a new comic, let's check for new issues on this week's pullist and update.
    mylar.weeklypull.pullitcheck()
    return

def no_searchresults(ComicID):
    # when there's a mismatch between CV & GCD - let's change the status to
    # something other than 'Loaded'
    myDB = db.DBConnection()
    controlValue = { "ComicID":        ComicID}
    newValue = {"Status":       "Error"}    
    myDB.upsert("comics", newValue, controlValue)

def nzblog(IssueID, NZBName):
    myDB = db.DBConnection()
    controlValue = {"IssueID": IssueID}
    #print controlValue
    newValue = {"NZBName": NZBName}
    #print newValue
    myDB.upsert("nzblog", newValue, controlValue)

def foundsearch(ComicID, IssueID):
    myDB = db.DBConnection()
    #print ("Updater-ComicID: " + str(ComicID))
    #print ("Updater-IssueID: " + str(IssueID))
    comic = myDB.action('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
    issue = myDB.action('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
    #print ("comic location: " + comic['ComicLocation'])
    #this is too soon - file hasn't downloaded even yet.
    #fixed and addressed in search.py and follow-thru here!
    #check sab history for completion here :)
    CYear = issue['IssueDate'][:4]
    #print ("year:" + str(CYear))
    #slog = myDB.action('SELECT * FROM sablog WHERE ComicName=? AND ComicYEAR=?', [issue['ComicName'], str(CYear)]).fetchone()
    #this checks the active queue for downloading/non-existant jobs
    #--end queue check
    #this checks history for completed jobs...
    #---
    #-- end history check

    fc = filechecker.listFiles(comic['ComicLocation'], comic['ComicName'])
    HaveDict = {"ComicID": ComicID}
    newHave = { "Have":    fc['comiccount'] }
    myDB.upsert("comics", newHave, HaveDict)
    #---
    issue = myDB.action('SELECT * FROM issues WHERE IssueID=? AND ComicID=?', [IssueID, ComicID]).fetchone()
    #print ("updating status to snatched")
    controlValueDict = {"IssueID":  IssueID}
    newValueDict = {"Status": "Snatched"}
    #print ("updating snatched db.")
    myDB.upsert("issues", newValueDict, controlValueDict)
    snatchedupdate = {"IssueID":     IssueID}
    newsnatchValues = {"ComicName":       comic['ComicName'],
                       "ComicID":         ComicID,
                       "Issue_Number":    issue['Issue_Number'],
                       "DateAdded":       helpers.now(),
                       "Status":          "Snatched"
                       }
    myDB.upsert("snatched", newsnatchValues, snatchedupdate)
    #we need to update sablog now to mark the nzo_id row as being completed and not used again.
    #this becomes an issue with files downloaded x2 or same name...


    #print ("finished updating snatched db.")
    logger.info(u"Updating now complete for " + str(comic['ComicName']) + " issue: " + str(issue['Issue_Number']))
    return

def forceRescan(ComicID):
    myDB = db.DBConnection()
    # file check to see if issue exists
    rescan = myDB.action('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
    logger.info(u"Now checking files for " + str(rescan['ComicName']) + " (" + str(rescan['ComicYear']) + ") in " + str(rescan['ComicLocation']) )
    fc = filechecker.listFiles(dir=rescan['ComicLocation'], watchcomic=rescan['ComicName'])
    iscnt = rescan['Total']
    havefiles = 0
    fccnt = int(fc['comiccount'])
    issnum = 1
    fcnew = []
    fn = 0
    reissues = myDB.action('SELECT * FROM issues WHERE ComicID=?', [ComicID]).fetchall()
    # if filechecker returns 0 files (it doesn't find any), but some issues have a status of 'Archived'
    # the loop below won't work...let's adjust :)
    arcissues = myDB.select("SELECT * FROM issues WHERE ComicID=? and Status='Archived'", [ComicID])
    if len(arcissues) > 0:
        havefiles = len(arcissues)
        print "have count adjusted to:" + str(len(arcissues))
    while (fn < fccnt):  
        haveissue = "no"
        try:
            tmpfc = fc['comiclist'][fn]
        except IndexError:
            break
        temploc = tmpfc['ComicFilename'].replace('_', ' ')
        temploc = re.sub('[\#\']', '', temploc)
        if 'annual' not in temploc:
            fcnew = shlex.split(str(temploc))
            fcn = len(fcnew)
            n = 0
            while (n <= iscnt):
                som = 0
                try:
                    reiss = reissues[n]
                except IndexError:
                    break
                int_iss = reiss['Int_IssueNumber']
                issyear = reiss['IssueDate'][:4]
                old_status = reiss['Status']
                
                #print "integer_issue:" + str(int_iss) + " ... status: " + str(old_status)
                while (som < fcn):
                    #counts get buggered up when the issue is the last field in the filename - ie. '50.cbr'
                    #print ("checking word - " + str(fcnew[som]))
                    if ".cbr" in fcnew[som]:
                        fcnew[som] = fcnew[som].replace(".cbr", "")
                    elif ".cbz" in fcnew[som]:
                        fcnew[som] = fcnew[som].replace(".cbz", "")
                    if fcnew[som].isdigit():
                        #print ("digit detected")
                        if int(fcnew[som]) > 0:
                            # fcdigit = fcnew[som].lstrip('0')
                            fcdigit = str(int(fcnew[som]))
                        else: 
                            fcdigit = "0"
                        if int(fcdigit) == int_iss:
                            #if issyear in fcnew[som+1]: 
                            #    print "matched on year:" + str(issyear)
                            #print ("matched...issue: " + str(fcdigit) + " --- " + str(int_iss))
                            havefiles+=1
                            haveissue = "yes"
                            isslocation = str(tmpfc['ComicFilename'])
                            break
                            #else:
                            # if the issue # matches, but there is no year present - still match.
                            # determine a way to match on year if present, or no year (currently).
                    som+=1
                if haveissue == "yes": break
                n+=1
        #we have the # of comics, now let's update the db.
        #even if we couldn't find the physical issue, check the status.
        #if Archived, increase the 'Have' count.
        if haveissue == "no":
            isslocation = "None"
            if old_status == "Skipped":
                if mylar.AUTOWANT_ALL:
                    issStatus = "Wanted"
                else:
                    issStatus = "Skipped"
            elif old_status == "Archived":
                havefiles+=1
                issStatus = "Archived"
            elif old_status == "Downloaded":
                issStatus = "Archived"
                havefiles+=1
            elif old_status == "Wanted":
                issStatus = "Wanted"
            else:
                issStatus = "Skipped"
        elif haveissue == "yes":
            issStatus = "Downloaded"
        controlValueDict = {"IssueID":  reiss['IssueID']}
        newValueDict = {"Location":           isslocation,
                        "Status":             issStatus
                        }
        myDB.upsert("issues", newValueDict, controlValueDict)
        fn+=1

    #let's update the total count of comics that was found.
    controlValueStat = {"ComicID":     rescan['ComicID']}
    newValueStat = {"Have":            havefiles
                   }

    myDB.upsert("comics", newValueStat, controlValueStat)
    logger.info(u"I've found " + str(havefiles) + " / " + str(rescan['Total']) + " issues." )

    #now that we are finished...
    #adjust for issues that have been marked as Downloaded, but aren't found/don't exist.
    #do it here, because above loop only cycles though found comics using filechecker.
    downissues = myDB.action("SELECT * FROM issues WHERE ComicID=? and Status='Downloaded'", [ComicID]).fetchall()
    if downissues is None:
        pass
    else:
        for down in downissues:
            #print "downlocation:" + str(down['Location'])
            comicpath = os.path.join(rescan['ComicLocation'], down['Location'])
            if os.path.exists(comicpath):
                pass
                #print "Issue exists - no need to change status."
            else:
                #print "Changing status from Downloaded to Archived - cannot locate file"
                controlValue = {"IssueID":   down['IssueID']}
                newValue = {"Status":    "Archived"}
                myDB.upsert("issues", newValue, controlValue) 

    return
