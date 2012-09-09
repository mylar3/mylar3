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

import mylar
from mylar import db, logger, helpers, filechecker

def dbUpdate():

    myDB = db.DBConnection()

    activecomics = myDB.select('SELECT ComicID, ComicName from comics WHERE Status="Active" or Status="Loading" order by LastUpdated ASC')

    logger.info('Starting update for %i active comics' % len(activecomicss))
    
    for comic in activecomics:
    
        comicid = comic[0]
        importer.addComictoDB(comicid)
        
    logger.info('Update complete')


def latest_update(ComicID, LatestIssue, LatestDate):
    # here we add to comics.latest
    myDB = db.DBConnection()
    controlValueDict = {"ComicID":      ComicID}
    newValueDict = {"LatestIssue":      LatestIssue,
                    "LatestDate":       LatestDate}
    myDB.upsert("comics", newValueDict, controlValueDict)

def upcoming_update(ComicID, ComicName, IssueNumber, IssueDate):
    # here we add to upcoming table...
    myDB = db.DBConnection()
    controlValue = {"ComicID":      ComicID}
    newValue = {"ComicName":        ComicName,
                "IssueNumber":      IssueNumber,
                "IssueDate":        IssueDate}
    if mylar.AUTOWANT_UPCOMING:
        newValue = {"STATUS":             "Wanted"}
    else:
        newValue = {"STATUS":             "Skipped"}
    myDB.upsert("upcoming", newValue, controlValue)

def weekly_update(ComicName):
    # here we update status of weekly table...
    myDB = db.DBConnection()
    controlValue = { "COMIC":         ComicName}
    if mylar.AUTOWANT_UPCOMING:
        newValue = {"STATUS":             "Wanted"}
    else:
        newValue = {"STATUS":             "Skipped"}
    myDB.upsert("weekly", newValue, controlValue)

def foundsearch(ComicID, IssueID):
    myDB = db.DBConnection()
    print ("Updater-ComicID: " + str(ComicID))
    print ("Updater-IssueID: " + str(IssueID))
    comic = myDB.action('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
    issue = myDB.action('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
    print ("comic location: " + comic['ComicLocation'])
    #this is too soon - file hasn't downloaded even yet.
    #fixed and addressed in search.py and follow-thru here!
    #check sab history for completion here :)
    CYear = issue['IssueDate'][:4]
    print ("year:" + str(CYear))
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
    print ("updating status to snatched")
    controlValueDict = {"IssueID":  IssueID}
    newValueDict = {"Status": "Snatched"}
    print ("updating snatched db.")
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


    print ("finished updating snatched db.")
    logger.info(u"Updating now complete for " + str(comic['ComicName']) + " issue: " + str(issue['Issue_Number']))
    return

def forceRescan(ComicID):
    myDB = db.DBConnection()
    # file check to see if issue exists
    rescan = myDB.action('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
   
    fc = filechecker.listFiles(dir=rescan['ComicLocation'], watchcomic=rescan['ComicName'])
    iscnt = rescan['Total']
    havefiles = 0
    mylar.AUTOWANT_ALL = 0
    fccnt = int(fc['comiccount'])
    issnum = 1
    fcnew = []
    n = 0
    while (n < iscnt):
        fn = 0
        haveissue = "no"
        
        print ("on issue " + str(int(n+1)) + " of " + str(iscnt) + " issues")
        print ("checking issue: " + str(issnum))
        # stupid way to do this, but check each issue against file-list in fc.
        while (fn < fccnt):
            tmpfc = fc['comiclist'][fn]
            print (str(issnum) + "against ... " + str(tmpfc['ComicFilename']))
            temploc = tmpfc['ComicFilename'].replace('_', ' ')
            fcnew = shlex.split(str(temploc))
            fcn = len(fcnew)
            som = 0
            #   this loop searches each word in the filename for a match.
            while (som < fcn):
                print (fcnew[som])
                #counts get buggered up when the issue is the last field in the filename - ie. '50.cbr'
                if ".cbr" in fcnew[som]:
                    fcnew[som] = fcnew[som].replace(".cbr", "")
                elif ".cbz" in fcnew[som]:
                    fcnew[som] = fcnew[som].replace(".cbz", "")
                if fcnew[som].isdigit():
                    print ("digit detected")
                    fcdigit = fcnew[som].lstrip('0')
                    print ( "filename:" + str(int(fcnew[som])) + " - issue: " + str(issnum) )
                    #fcdigit = fcnew[som].lstrip('0') + ".00"
                    if int(fcdigit) == int(issnum):
                        print ("matched")
                        print ("We have this issue - " + str(issnum) + " at " + tmpfc['ComicFilename'] )
                        havefiles+=1
                        haveissue = "yes"
                        isslocation = str(tmpfc['ComicFilename'])
                        break
                print ("failed word match on:" + str(fcnew[som]) + "..continuing next word")
                som+=1
            print (str(temploc) + " doesn't match anything...moving to next file.")
            fn+=1
            issnum+=1
    print ("you have " + str(havefiles) + " comics!")
    return
