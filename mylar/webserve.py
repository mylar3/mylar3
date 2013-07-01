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

from __future__ import with_statement

import os
import cherrypy
import datetime
import re

from mako.template import Template
from mako.lookup import TemplateLookup
from mako import exceptions

import time
import threading
import csv
import platform
import urllib
import shutil

import mylar

from mylar import logger, db, importer, mb, search, filechecker, helpers, updater, parseit, weeklypull, PostProcessor, version, librarysync, moveit #,rsscheck
#from mylar.helpers import checked, radio, today

import lib.simplejson as simplejson

from operator import itemgetter

def serve_template(templatename, **kwargs):

    interface_dir = os.path.join(str(mylar.PROG_DIR), 'data/interfaces/')
    template_dir = os.path.join(str(interface_dir), mylar.INTERFACE)

    _hplookup = TemplateLookup(directories=[template_dir])
    
    try:
        template = _hplookup.get_template(templatename)
        return template.render(**kwargs)
    except:
        return exceptions.html_error_template().render()
    
class WebInterface(object):
    
    def index(self):
        raise cherrypy.HTTPRedirect("home")
    index.exposed=True

    def home(self):
        myDB = db.DBConnection()
        comics = myDB.select('SELECT * from comics order by ComicSortName COLLATE NOCASE')
        return serve_template(templatename="index.html", title="Home", comics=comics)
    home.exposed = True

    def artistPage(self, ComicID):
        myDB = db.DBConnection()
        comic = myDB.action('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
        if comic is None:
            raise cherrypy.HTTPRedirect("home")
        #let's cheat. :)
        #comicskip = myDB.select('SELECT * from comics order by ComicSortName COLLATE NOCASE')
        skipno = len(mylar.COMICSORT['SortOrder'])
        lastno = mylar.COMICSORT['LastOrderNo']
        lastid = mylar.COMICSORT['LastOrderID']
        series = {}
        if skipno == 0:
            #it's a blank db, let's just null the values and go.
            series['Current'] = None
            series['Previous'] = None
            series['Next'] = None
        i = 0
        while (i < skipno):
            cskip = mylar.COMICSORT['SortOrder'][i]
            if cskip['ComicID'] == ComicID:
                cursortnum = cskip['ComicOrder']
                series['Current'] = cskip['ComicID']
                if cursortnum == 0:
                    # if first record, set the Previous record to the LAST record.
                    previous = lastid
                else:
                    previous = mylar.COMICSORT['SortOrder'][i-1]['ComicID']

                # if last record, set the Next record to the FIRST record.
                if cursortnum == lastno:
                    next = mylar.COMICSORT['SortOrder'][0]['ComicID']
                else:
                    next = mylar.COMICSORT['SortOrder'][i+1]['ComicID']
                series['Previous'] = previous
                series['Next'] = next
                break
            i+=1

        issues = myDB.select('SELECT * FROM issues WHERE ComicID=? order by Int_IssueNumber DESC', [ComicID])
        isCounts = {}
        isCounts[1] = 0   #1 skipped
        isCounts[2] = 0   #2 wanted
        isCounts[3] = 0   #3 archived
        isCounts[4] = 0   #4 downloaded
        isCounts[5] = 0   #5 read

        for curResult in issues:
            baseissues = {'skipped':1,'wanted':2,'archived':3,'downloaded':4}
            for seas in baseissues:
                if seas in curResult['Status'].lower():
                    sconv = baseissues[seas]
                    isCounts[sconv]+=1
                    continue
        isCounts = {
                 "Skipped" : str(isCounts[1]),
                 "Wanted" : str(isCounts[2]),
                 "Archived" : str(isCounts[3]),
                 "Downloaded" : str(isCounts[4])
               }
        usethefuzzy = comic['UseFuzzy']
        skipped2wanted = "0"
        if usethefuzzy is None: usethefuzzy = "0"
        comicConfig = {
                    "comiclocation" : mylar.COMIC_LOCATION,
                    "fuzzy_year0" : helpers.radio(int(usethefuzzy), 0),
                    "fuzzy_year1" : helpers.radio(int(usethefuzzy), 1),
                    "fuzzy_year2" : helpers.radio(int(usethefuzzy), 2),
                    "skipped2wanted" : helpers.checked(skipped2wanted)
               }
        if mylar.ANNUALS_ON:
            annuals = myDB.select("SELECT * FROM annuals WHERE ComicID=?", [ComicID])
        else: annuals = None

        return serve_template(templatename="artistredone.html", title=comic['ComicName'], comic=comic, issues=issues, comicConfig=comicConfig, isCounts=isCounts, series=series, annuals=annuals)
    artistPage.exposed = True

    def searchit(self, name, issue=None, mode=None, type=None):
        if type is None: type = 'comic'  # let's default this to comic search only for the time being (will add story arc, characters, etc later)
        else: print (str(type) + " mode enabled.")
        #mode dictates type of search:
        # --series     ...  search for comicname displaying all results
        # --pullseries ...  search for comicname displaying a limited # of results based on issue
        # --want       ...  individual comics
        if mode is None: mode = 'series'
        if len(name) == 0:
            raise cherrypy.HTTPRedirect("home")
        if type == 'comic' and mode == 'pullseries':
            searchresults = mb.findComic(name, mode, issue=issue)
        elif type == 'comic' and mode == 'series':
            searchresults = mb.findComic(name, mode, issue=None)
        elif type == 'comic' and mode == 'want':
            searchresults = mb.findComic(name, mode, issue)
        elif type == 'storyarc':
            searchresults = mb.findComic(name, mode, issue=None, storyarc='yes')

        searchresults = sorted(searchresults, key=itemgetter('comicyear','issues'), reverse=True)
        #print ("Results: " + str(searchresults))
        return serve_template(templatename="searchresults.html", title='Search Results for: "' + name + '"', searchresults=searchresults, type=type, imported=None, ogcname=None)
    searchit.exposed = True

    def addComic(self, comicid, comicname=None, comicyear=None, comicimage=None, comicissues=None, comicpublisher=None, imported=None, ogcname=None):
        myDB = db.DBConnection()
        if imported == "confirm":
            # if it's coming from the importer and it's just for confirmation, record the right selection and break.
            # if it's 'confirmed' coming in as the value for imported
            # the ogcname will be the original comicid that is either correct/incorrect (doesn't matter which)
            #confirmedid is the selected series (comicid) with the letter C at the beginning to denote Confirmed.
            # then sql the original comicid which will hit on all the results for the given series.
            # iterate through, and overwrite the existing watchmatch with the new chosen 'C' + comicid value
            
            confirmedid = "C" + str(comicid)
            confirms = myDB.action("SELECT * FROM importresults WHERE WatchMatch=?", [ogcname])
            if confirms is None:
                logger.Error("There are no results that match...this is an ERROR.")
            else:
                for confirm in confirms:
                    controlValue = {"impID":    confirm['impID']}
                    newValue = {"WatchMatch":   str(confirmedid)}
                    myDB.upsert("importresults", newValue, controlValue)
                self.importResults()            
            return
        sresults = []
        cresults = []
        mismatch = "no"
        #print ("comicid: " + str(comicid))
        #print ("comicname: " + str(comicname))
        #print ("comicyear: " + str(comicyear))
        #print ("comicissues: " + str(comicissues))
        #print ("comicimage: " + str(comicimage))
        if not mylar.CV_ONLY:
        #here we test for exception matches (ie. comics spanning more than one volume, known mismatches, etc).
            CV_EXcomicid = myDB.action("SELECT * from exceptions WHERE ComicID=?", [comicid]).fetchone()
            if CV_EXcomicid is None: # pass #
                gcdinfo=parseit.GCDScraper(comicname, comicyear, comicissues, comicid, quickmatch="yes")
                if gcdinfo == "No Match":
                #when it no matches, the image will always be blank...let's fix it.
                    cvdata = mylar.cv.getComic(comicid,'comic')
                    comicimage = cvdata['ComicImage']
                    updater.no_searchresults(comicid)
                    nomatch = "true"
                    u_comicname = comicname.encode('utf-8').strip()
                    logger.info("I couldn't find an exact match for " + u_comicname + " (" + str(comicyear) + ") - gathering data for Error-Checking screen (this could take a minute)..." )
                    i = 0
                    loopie, cnt = parseit.ComChk(comicname, comicyear, comicpublisher, comicissues, comicid)
                    logger.info("total count : " + str(cnt))
                    while (i < cnt):
                        try:
                            stoopie = loopie['comchkchoice'][i]
                        except (IndexError, TypeError):
                            break
                        cresults.append({
                               'ComicID'   :   stoopie['ComicID'],
                               'ComicName' :   stoopie['ComicName'].decode('utf-8', 'replace'),
                               'ComicYear' :   stoopie['ComicYear'],
                               'ComicIssues' : stoopie['ComicIssues'],
                               'ComicURL' :    stoopie['ComicURL'],
                               'ComicPublisher' : stoopie['ComicPublisher'].decode('utf-8', 'replace'),
                               'GCDID' : stoopie['GCDID']
                               })
                        i+=1
                    if imported != 'None':
                    #if it's from an import and it has to go through the UEC, return the values
                    #to the calling function and have that return the template
                        return cresults
                    else:
                        return serve_template(templatename="searchfix.html", title="Error Check", comicname=comicname, comicid=comicid, comicyear=comicyear, comicimage=comicimage, comicissues=comicissues, cresults=cresults,imported=None,ogcname=None)
                else:
                    nomatch = "false"
                    logger.info(u"Quick match success..continuing.")  
            else:
                if CV_EXcomicid['variloop'] == '99':
                    logger.info(u"mismatched name...autocorrecting to correct GID and auto-adding.")
                    mismatch = "yes"
                if CV_EXcomicid['NewComicID'] == 'none':
                    logger.info(u"multi-volume series detected")         
                    testspx = CV_EXcomicid['GComicID'].split('/')
                    for exc in testspx:
                        fakeit = parseit.GCDAdd(testspx)
                        howmany = int(CV_EXcomicid['variloop'])
                        t = 0
                        while (t <= howmany):
                            try:
                                sres = fakeit['serieschoice'][t]
                            except IndexError:
                                break
                            sresults.append({
                                   'ComicID'   :   sres['ComicID'],
                                   'ComicName' :   sres['ComicName'],
                                   'ComicYear' :   sres['ComicYear'],
                                   'ComicIssues' : sres['ComicIssues'],
                                   'ComicPublisher' : sres['ComicPublisher'],
                                   'ComicCover' :    sres['ComicCover']
                                   })
                            t+=1
                        #searchfix(-1).html is for misnamed comics and wrong years.
                        #searchfix-2.html is for comics that span multiple volumes.
                        return serve_template(templatename="searchfix-2.html", title="In-Depth Results", sresults=sresults)
        #print ("imported is: " + str(imported))
        threading.Thread(target=importer.addComictoDB, args=[comicid,mismatch,None,imported,ogcname]).start()
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % comicid)
    addComic.exposed = True

    def from_Exceptions(self, comicid, gcdid, comicname=None, comicyear=None, comicissues=None, comicpublisher=None, imported=None, ogcname=None):
        import unicodedata
        mismatch = "yes"
        #write it to the custom_exceptions.csv and reload it so that importer will pick it up and do it's thing :)
        #custom_exceptions in this format...
        #99, (comicid), (gcdid), none
        logger.info("saving new information into custom_exceptions.csv...")
        except_info = "none #" + str(comicname) + "-(" + str(comicyear) + ")\n"
        except_file = os.path.join(mylar.DATA_DIR,"custom_exceptions.csv")
        if not os.path.exists(except_file):
            try:
                 csvfile = open(str(except_file), 'rb')
                 csvfile.close()
            except (OSError,IOError):
                logger.error("Could not locate " + str(except_file) + " file. Make sure it's in datadir: " + mylar.DATA_DIR + " with proper permissions.")
                return
        exceptln = "99," + str(comicid) + "," + str(gcdid) + "," + str(except_info)
        exceptline = exceptln.decode('utf-8','ignore')

        with open(str(except_file), 'a') as f:
           #f.write('%s,%s,%s,%s\n' % ("99", comicid, gcdid, except_info)
            f.write('%s\n' % (exceptline.encode('ascii','replace').strip()))
        logger.info("re-loading csv file so it's all nice and current.")
        mylar.csv_load()
        if imported:
            threading.Thread(target=importer.addComictoDB, args=[comicid,mismatch,None,imported,ogcname]).start()
        else:
            threading.Thread(target=importer.addComictoDB, args=[comicid,mismatch]).start()
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % comicid)
    from_Exceptions.exposed = True

    def GCDaddComic(self, comicid, comicname=None, comicyear=None, comicissues=None, comiccover=None, comicpublisher=None):
        #since we already know most of the info, let's add it to the db so we can reference it later.
        myDB = db.DBConnection()
        gcomicid = "G" + str(comicid)
        comicyear_len = comicyear.find(' ', 2)
        comyear = comicyear[comicyear_len+1:comicyear_len+5]
        if comyear.isdigit():
            logger.fdebug("Series year set to : " + str(comyear))
        else:
            logger.fdebug("Invalid Series year detected - trying to adjust from " + str(comyear))
            #comicyear_len above will trap wrong year if it's 10 October 2010 - etc ( 2000 AD)...
            find_comicyear = comicyear.split()
            for i in find_comicyear:
                if len(i) == 4:
                    logger.fdebug("Series year detected as : " + str(i))
                    comyear = str(i)
                    continue

            logger.fdebug("Series year set to: " + str(comyear))
            
        controlValueDict = { 'ComicID': gcomicid }
        newValueDict = {'ComicName': comicname,
                        'ComicYear': comyear,
                        'ComicPublished': comicyear,
                        'ComicPublisher': comicpublisher,
                        'ComicImage': comiccover,
                        'Total' : comicissues }
        myDB.upsert("comics", newValueDict, controlValueDict)
        threading.Thread(target=importer.GCDimport, args=[gcomicid]).start()
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % gcomicid)
    GCDaddComic.exposed = True

    def post_process(self, nzb_name, nzb_folder):
        logger.info(u"Starting postprocessing for : " + str(nzb_name) )
        PostProcess = PostProcessor.PostProcessor(nzb_name, nzb_folder)
        result = PostProcess.Process()
        #result = post_results.replace("\n","<br />\n")
        return result
        #log2screen = threading.Thread(target=PostProcessor.PostProcess, args=[nzb_name,nzb_folder]).start()
        #return serve_template(templatename="postprocess.html", title="postprocess")
        #raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % comicid)
    post_process.exposed = True

    def pauseArtist(self, ComicID):
        logger.info(u"Pausing comic: " + ComicID)
        myDB = db.DBConnection()
        controlValueDict = {'ComicID': ComicID}
        newValueDict = {'Status': 'Paused'}
        myDB.upsert("comics", newValueDict, controlValueDict)
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    pauseArtist.exposed = True
    
    def resumeArtist(self, ComicID):
        logger.info(u"Resuming comic: " + ComicID)
        myDB = db.DBConnection()
        controlValueDict = {'ComicID': ComicID}
        newValueDict = {'Status': 'Active'}
        myDB.upsert("comics", newValueDict, controlValueDict)
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    resumeArtist.exposed = True
    
    def deleteArtist(self, ComicID):
        myDB = db.DBConnection()
        comic = myDB.action('SELECT * from comics WHERE ComicID=?', [ComicID]).fetchone()
        if comic['ComicName'] is None: ComicName = "None"
        else: ComicName = comic['ComicName']
        logger.info(u"Deleting all traces of Comic: " + ComicName)
        myDB.action('DELETE from comics WHERE ComicID=?', [ComicID])
        myDB.action('DELETE from issues WHERE ComicID=?', [ComicID])
        myDB.action('DELETE from upcoming WHERE ComicID=?', [ComicID])
        helpers.ComicSort(sequence='update')
        raise cherrypy.HTTPRedirect("home")
    deleteArtist.exposed = True
    
    def refreshArtist(self, ComicID):
        myDB = db.DBConnection()
        mismatch = "no"
        if not mylar.CV_ONLY or ComicID[:1] == "G":

            CV_EXcomicid = myDB.action("SELECT * from exceptions WHERE ComicID=?", [ComicID]).fetchone()
            if CV_EXcomicid is None: pass
            else:
                if CV_EXcomicid['variloop'] == '99':
                    mismatch = "yes"
            if ComicID[:1] == "G": threading.Thread(target=importer.GCDimport, args=[ComicID]).start()
            else: threading.Thread(target=importer.addComictoDB, args=[ComicID,mismatch]).start()    
        else:
            if mylar.CV_ONETIMER == 1:
                logger.fdebug("CV_OneTimer option enabled...")
                #in order to update to JUST CV_ONLY, we need to delete the issues for a given series so it's a clea$
                logger.fdebug("Gathering the status of all issues for the series.")
                issues = myDB.select('SELECT * FROM issues WHERE ComicID=?', [ComicID])
                #store the issues' status for a given comicid, after deleting and readding, flip the status back to$
                logger.fdebug("Deleting all issue data.")
                myDB.select('DELETE FROM issues WHERE ComicID=?', [ComicID])
                logger.fdebug("Refreshing the series and pulling in new data using only CV.")
                mylar.importer.addComictoDB(ComicID,mismatch)
                issues_new = myDB.select('SELECT * FROM issues WHERE ComicID=?', [ComicID])
                logger.fdebug("Attempting to put the Status' back how they were.")
                icount = 0
                for issue in issues:
                    for issuenew in issues_new:
                        if issuenew['IssueID'] == issue['IssueID'] and issuenew['Status'] != issue['Status']:
                            #change the status to the previous status
                            ctrlVAL = {'IssueID':  issue['IssueID']}
                            newVAL = {'Status':  issue['Status']}
                            myDB.upsert("Issues", newVAL, ctrlVAL)
                            icount+=1
                            break
                logger.info("In the process of converting the data to CV, I changed the status of " + str(icount) + " issues.")
            else:
                mylar.importer.addComictoDB(ComicID,mismatch)

        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    refreshArtist.exposed=True  

    def editIssue(self, ComicID):
        myDB = db.DBConnection()
        comic = myDB.action('SELECT * from comics WHERE ComicID=?', [ComicID]).fetchone()
        title = 'Now Editing ' + comic['ComicName']
        return serve_template(templatename="editcomic.html", title=title, comic=comic)
        #raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" & ComicID)   
    editIssue.exposed=True
 
    #def chkTorrents(self, ComicName, pickfeed):
    #    chktorrent = rsscheck.torrents(ComicName,pickfeed)
    #    if chktorrent:
    #        print ("Torrent Check completed.")

    #    raise cherrypy.HTTPRedirect("home")

    #chkTorrents.exposed = True


    def markissues(self, action=None, **args):
        myDB = db.DBConnection()
        issuesToAdd = []
        issuestoArchive = []
        if action == 'WantedNew':
            newaction = 'Wanted'
        else:
            newaction = action
        for IssueID in args:
            #print ("issueID: " + str(IssueID) + "... " + str(newaction))
            if IssueID is None or 'issue_table' in IssueID:
                continue
            else:
                mi = myDB.action("SELECT * FROM issues WHERE IssueID=?",[IssueID]).fetchone()
                miyr = myDB.action("SELECT ComicYear FROM comics WHERE ComicID=?", [mi['ComicID']]).fetchone()
                if action == 'Downloaded':
                    if mi['Status'] == "Skipped" or mi['Status'] == "Wanted":
                        logger.info(u"Cannot change status to %s as comic is not Snatched or Downloaded" % (newaction))
#                        continue
                elif action == 'Archived':
                    logger.info(u"Marking %s %s as %s" % (mi['ComicName'], mi['Issue_Number'], newaction))
                    #updater.forceRescan(mi['ComicID'])
                    issuestoArchive.append(IssueID)
                elif action == 'Wanted':
                    logger.info(u"Marking %s %s as %s" % (mi['ComicName'], mi['Issue_Number'], newaction))
                    issuesToAdd.append(IssueID)
                elif action == 'Skipped':
                    logger.info(u"Marking " + str(IssueID) + " as Skipped")
                controlValueDict = {"IssueID": IssueID}
                newValueDict = {"Status": newaction}
                myDB.upsert("issues", newValueDict, controlValueDict)
        if len(issuestoArchive) > 0:
            updater.forceRescan(mi['ComicID'])
        if len(issuesToAdd) > 0:
            logger.debug("Marking issues: %s as Wanted" % (issuesToAdd))
            threading.Thread(target=search.searchIssueIDList, args=[issuesToAdd]).start()
        #if IssueID:
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % mi['ComicID'])
        #else:
        #    raise cherrypy.HTTPRedirect("upcoming")
    markissues.exposed = True
    
    def addArtists(self, **args):
        threading.Thread(target=importer.artistlist_to_mbids, args=[args, True]).start()
        raise cherrypy.HTTPRedirect("home")
    addArtists.exposed = True
    
    def queueissue(self, mode, ComicName=None, ComicID=None, ComicYear=None, ComicIssue=None, IssueID=None, new=False, redirect=None, SeriesYear=None, SARC=None, IssueArcID=None):
        print "ComicID:" + str(ComicID)
        print "mode:" + str(mode)
        now = datetime.datetime.now()
        myDB = db.DBConnection()
        #mode dictates type of queue - either 'want' for individual comics, or 'series' for series watchlist.
        if ComicID is None and mode == 'series':
            issue = None
            raise cherrypy.HTTPRedirect("searchit?name=%s&issue=%s&mode=%s" % (ComicName, 'None', 'series'))
        elif ComicID is None and mode == 'pullseries':
            # we can limit the search by including the issue # and searching for
            # comics that have X many issues
            raise cherrypy.HTTPRedirect("searchit?name=%s&issue=%s&mode=%s" % (ComicName, 'None', 'pullseries'))
        elif ComicID is None and mode == 'readlist':
            print "blahblah"
            # this is for marking individual comics from a readlist to be downloaded.
            # Because there is no associated ComicID or IssueID, follow same pattern as in 'pullwant'
            # except we know the Year
            if SARC is None:
                # it's just a readlist queue (no storyarc mode enabled)
                SARC = True
                IssueArcID = None
            else:
                logger.info(u"Story Arc : " + str(SARC) + " queueing selected issue...")
                logger.info(u"IssueArcID : " + str(IssueArcID))
            if ComicYear is None: ComicYear = SeriesYear
            logger.info(u"Marking " + ComicName + " " + ComicIssue + " as wanted...")
            controlValueDict = {"IssueArcID": IssueArcID}
            newStatus = {"Status": "Wanted"}
            myDB.upsert("readinglist", newStatus, controlValueDict)
            foundcom = search.search_init(ComicName=ComicName, IssueNumber=ComicIssue, ComicYear=ComicYear, SeriesYear=None, IssueDate=None, IssueID=None, AlternateSearch=None, UseFuzzy=None, ComicVersion=None, SARC=SARC, IssueArcID=IssueArcID)
            if foundcom  == "yes":
                logger.info(u"Downloaded " + ComicName + " #" + ComicIssue + " (" + str(ComicYear) + ")")
            #raise cherrypy.HTTPRedirect("readlist")
            return foundcom

        elif ComicID is None and mode == 'pullwant':          
            #this is for marking individual comics from the pullist to be downloaded.
            #because ComicID and IssueID will both be None due to pullist, it's probably
            #better to set both to some generic #, and then filter out later...
            cyear = myDB.action("SELECT SHIPDATE FROM weekly").fetchone()
            ComicYear = str(cyear['SHIPDATE'])[:4]
            if ComicYear == '': ComicYear = now.year
            logger.info(u"Marking " + ComicName + " " + ComicIssue + " as wanted...")
            foundcom = search.search_init(ComicName=ComicName, IssueNumber=ComicIssue, ComicYear=ComicYear, SeriesYear=None, IssueDate=cyear['SHIPDATE'], IssueID=None, AlternateSearch=None, UseFuzzy=None, ComicVersion=None)
            if foundcom  == "yes":
                logger.info(u"Downloaded " + ComicName + " " + ComicIssue )  
            raise cherrypy.HTTPRedirect("pullist")
            #return
        elif mode == 'want' or mode == 'want_ann':
            cdname = myDB.action("SELECT ComicName from comics where ComicID=?", [ComicID]).fetchone()
            ComicName = cdname['ComicName']
            controlValueDict = {"IssueID": IssueID}
            newStatus = {"Status": "Wanted"}
            if mode == 'want':
                logger.info(u"Marking " + ComicName + " issue: " + ComicIssue + " as wanted...")
                myDB.upsert("issues", newStatus, controlValueDict)
            else:
                logger.info(u"Marking " + ComicName + " Annual: " + ComicIssue + " as wanted...")
                myDB.upsert("annuals", newStatus, controlValueDict)
        #---
        #this should be on it's own somewhere
        #if IssueID is not None:
        #    controlValueDict = {"IssueID": IssueID}
        #    newStatus = {"Status": "Wanted"}
        #    myDB.upsert("issues", newStatus, controlValueDict)
        #for future reference, the year should default to current year (.datetime)
        if mode == 'want':
            issues = myDB.action("SELECT IssueDate FROM issues WHERE IssueID=?", [IssueID]).fetchone()
        elif mode == 'want_ann':
            issues = myDB.action("SELECT IssueDate FROM annuals WHERE IssueID=?", [IssueID]).fetchone()
        if ComicYear == None:
            ComicYear = str(issues['IssueDate'])[:4]
        miy = myDB.action("SELECT * FROM comics WHERE ComicID=?", [ComicID]).fetchone()
        SeriesYear = miy['ComicYear']
        AlternateSearch = miy['AlternateSearch']
        UseAFuzzy = miy['UseFuzzy']
        ComicVersion = miy['ComicVersion']
        foundcom = search.search_init(ComicName, ComicIssue, ComicYear, SeriesYear, issues['IssueDate'], IssueID, AlternateSearch, UseAFuzzy, ComicVersion, mode=mode)
        if foundcom  == "yes":
            # file check to see if issue exists and update 'have' count
            if IssueID is not None:
                logger.info("passing to updater.")
                return updater.foundsearch(ComicID, IssueID, mode) 
        if ComicID:
            raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
        else:
            raise cherrypy.HTTPRedirect(redirect)
    queueissue.exposed = True

    def unqueueissue(self, IssueID, ComicID):
        myDB = db.DBConnection()
        issue = myDB.action('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
        logger.info(u"Marking " + issue['ComicName'] + " issue # " + issue['Issue_Number']  + " as skipped...")
        controlValueDict = {'IssueID': IssueID}
        newValueDict = {'Status': 'Skipped'}
        myDB.upsert("issues", newValueDict, controlValueDict)
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    unqueueissue.exposed = True
    
    def archiveissue(self, IssueID):
        myDB = db.DBConnection()
        issue = myDB.action('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
        logger.info(u"Marking " + issue['ComicName'] + " issue # " + issue['Issue_Number']  + " as archived...")
        controlValueDict = {'IssueID': IssueID}
        newValueDict = {'Status': 'Archived'}
        myDB.upsert("issues", newValueDict, controlValueDict)
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % issue['ComicID'])
    archiveissue.exposed = True


    def pullist(self):
        myDB = db.DBConnection()
        weeklyresults = []
        popit = myDB.select("SELECT * FROM sqlite_master WHERE name='weekly' and type='table'")
        if popit:
            w_results = myDB.select("SELECT PUBLISHER, ISSUE, COMIC, STATUS from weekly")
            for weekly in w_results:
                if weekly['ISSUE'].isdigit() or 'au' in weekly['ISSUE'].lower() or 'ai' in weekly['ISSUE'].lower():
                    weeklyresults.append({
                                           "PUBLISHER"  : weekly['PUBLISHER'],
                                           "ISSUE"      : weekly['ISSUE'],
                                           "COMIC"      : weekly['COMIC'],
                                           "STATUS"     : weekly['STATUS']
                                         })
            weeklyresults = sorted(weeklyresults, key=itemgetter('PUBLISHER','COMIC'), reverse=False)
            pulldate = myDB.action("SELECT * from weekly").fetchone()
            if pulldate is None:
                return self.manualpull()
                #raise cherrypy.HTTPRedirect("home")
        else:
            return self.manualpull()
        weekfold = os.path.join(mylar.DESTINATION_DIR, pulldate['SHIPDATE'])
        return serve_template(templatename="weeklypull.html", title="Weekly Pull", weeklyresults=weeklyresults, pulldate=pulldate['SHIPDATE'], pullfilter=True, weekfold=weekfold)
    pullist.exposed = True   

    def filterpull(self):
        myDB = db.DBConnection()
        weeklyresults = myDB.select("SELECT * from weekly")
        pulldate = myDB.action("SELECT * from weekly").fetchone()
        if pulldate is None:
            raise cherrypy.HTTPRedirect("home")
        return serve_template(templatename="weeklypull.html", title="Weekly Pull", weeklyresults=weeklyresults, pulldate=pulldate['SHIPDATE'], pullfilter=True)
    filterpull.exposed = True

    def manualpull(self):
        from mylar import weeklypull
        threading.Thread(target=weeklypull.pullit()).start()
        raise cherrypy.HTTPRedirect("pullist")
    manualpull.exposed = True

    def pullrecreate(self):
        from mylar import weeklypull
        myDB = db.DBConnection()
        myDB.action("DROP TABLE weekly")
        mylar.dbcheck()
        logger.info("Deleted existed pull-list data. Recreating Pull-list...")
        threading.Thread(target=weeklypull.pullit(forcecheck='yes')).start()
        raise cherrypy.HTTPRedirect("pullist")
    pullrecreate.exposed = True

    def upcoming(self):
        myDB = db.DBConnection()
        #upcoming = myDB.select("SELECT * from issues WHERE ReleaseDate > date('now') order by ReleaseDate DESC")
        upcoming = myDB.select("SELECT * from upcoming WHERE IssueDate > date('now') AND IssueID is NULL order by IssueDate DESC")
        issues = myDB.select("SELECT * from issues WHERE Status='Wanted'")
        #let's move any items from the upcoming table into the wanted table if the date has already passed.
        #gather the list...
        mvupcome = myDB.select("SELECT * from upcoming WHERE IssueDate < date('now') order by IssueDate DESC")
        #get the issue ID's
        for mvup in mvupcome:
            myissue = myDB.action("SELECT * FROM issues WHERE IssueID=?", [mvup['IssueID']]).fetchone()
            #myissue =  myDB.action("SELECT * FROM issues WHERE Issue_Number=?", [mvup['IssueNumber']]).fetchone()

            if myissue is None: pass
            else:
                logger.fdebug("--Updating Status of issues table because of Upcoming status--")
                logger.fdebug("ComicName: " + str(myissue['ComicName']))
                logger.fdebug("Issue number : " + str(myissue['Issue_Number']) )
 
                mvcontroldict = {"IssueID":    myissue['IssueID']}
                mvvalues = {"ComicID":         myissue['ComicID'],
                            "Status":          "Wanted"}
                myDB.upsert("issues", mvvalues, mvcontroldict)

                #remove old entry from upcoming so it won't try to continually download again.
                deleteit = myDB.action("DELETE from upcoming WHERE ComicName=? AND IssueNumber=?", [mvup['ComicName'],mvup['IssueNumber']])                                


        return serve_template(templatename="upcoming.html", title="Upcoming", upcoming=upcoming, issues=issues)
    upcoming.exposed = True

    def skipped2wanted(self, comicid):
        # change all issues for a given ComicID that are Skipped, into Wanted.
        issuestowanted = []
        issuesnumwant = []
        myDB = db.DBConnection()
        skipped2 = myDB.select("SELECT * from issues WHERE ComicID=? AND Status='Skipped'", [comicid])
        for skippy in skipped2:
            mvcontroldict = {"IssueID":    skippy['IssueID']}
            mvvalues = {"Status":         "Wanted"}
            #print ("Changing issue " + str(skippy['Issue_Number']) + " to Wanted.")
            myDB.upsert("issues", mvvalues, mvcontroldict)
            issuestowanted.append(skippy['IssueID'])
            issuesnumwant.append(skippy['Issue_Number'])
        if len(issuestowanted) > 0 :
            logger.info("Marking issues: %s as Wanted" % issuesnumwant)
            threading.Thread(target=search.searchIssueIDList, args=[issuestowanted]).start()
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % [comicid])
    skipped2wanted.exposed = True

    def manualRename(self, comicid):
        if mylar.FILE_FORMAT == '':
            logger.error("You haven't specified a File Format in Configuration/Advanced")
            logger.error("Cannot rename files.")
            return

        myDB = db.DBConnection()
        comic = myDB.action("SELECT * FROM comics WHERE ComicID=?", [comicid]).fetchone()
        comicdir = comic['ComicLocation']
        comicname = comic['ComicName']
        extensions = ('.cbr', '.cbz')
        issues = myDB.action("SELECT * FROM issues WHERE ComicID=?", [comicid]).fetchall()
        comfiles = []
        filefind = 0
        for root, dirnames, filenames in os.walk(comicdir):
            for filename in filenames:
                if filename.lower().endswith(extensions):
                    #logger.info("filename being checked is : " + str(filename))
                    for issue in issues:
                        if issue['Location'] == filename:
                            #logger.error("matched " + str(filename) + " to DB file " + str(issue['Location']))
                            renameiss = helpers.rename_param(comicid, comicname, issue['Issue_Number'], filename, comicyear=None, issueid=None)
                            nfilename = renameiss['nfilename']
                            srciss = os.path.join(comicdir,filename)
                            if mylar.LOWERCASE_FILENAMES:
                                dstiss = os.path.join(comicdir,nfilename).lower()
                            else:
                                dstiss = os.path.join(comicdir,nfilename)
                            if filename != nfilename:
                                logger.info("Renaming " + str(filename) + " ... to ... " + str(nfilename))
                                try:
                                    shutil.move(srciss, dstiss)
                                except (OSError, IOError):
                                    logger.error("Failed to move files - check directories and manually re-run.")
                                    return
                                filefind+=1
                            else:
                                logger.info("Not renaming " + str(filename) + " as it is in desired format already.")
                            #continue
            logger.info("I have renamed " + str(filefind) + " issues of " + comicname)
            updater.forceRescan(comicid)
    manualRename.exposed = True

    def searchScan(self, name):
        return serve_template(templatename="searchfix.html", title="Manage", name=name)
    searchScan.exposed = True
    
    def manage(self):
        return serve_template(templatename="manage.html", title="Manage")
    manage.exposed = True
    
    def manageComics(self):
        myDB = db.DBConnection()
        comics = myDB.select('SELECT * from comics order by ComicSortName COLLATE NOCASE')
        return serve_template(templatename="managecomics.html", title="Manage Comics", comics=comics)
    manageComics.exposed = True
    
    def manageIssues(self):
        myDB = db.DBConnection()
        issues = myDB.select('SELECT * from issues')
        return serve_template(templatename="manageissues.html", title="Manage Issues", issues=issues)
    manageIssues.exposed = True
    
    def manageNew(self):
        myDB = db.DBConnection()
        newcomics = myDB.select('SELECT * from newartists')
        return serve_template(templatename="managenew.html", title="Manage New Artists", newcomics=newcomics)
    manageNew.exposed = True    

    def flushImports(self):
        myDB = db.DBConnection()
        myDB.action('DELETE from importresults')
        logger.info("Flushing all Import Results and clearing the tables")
        raise cherrypy.HTTPRedirect("importResults")
    flushImports.exposed = True

    def markImports(self, action=None, **args):
        myDB = db.DBConnection()
        comicstoimport = []
        for ComicName in args:
           if action == 'massimport':
               logger.info("initiating mass import mode for " + ComicName)
               cid = ComicName.decode('utf-8', 'replace')
               comicstoimport.append(cid)
           elif action == 'removeimport':
               logger.info("removing " + ComicName + " from the Import list")
               myDB.action('DELETE from importresults WHERE ComicName=?', [ComicName])

        if len(comicstoimport) > 0:
            logger.debug("Mass importing the following series: %s" % comicstoimport)
            threading.Thread(target=self.preSearchit, args=[None, comicstoimport, len(comicstoimport)]).start()
        raise cherrypy.HTTPRedirect("importResults")

    markImports.exposed = True
    
    def markComics(self, action=None, **args):
        myDB = db.DBConnection()
        comicsToAdd = []
        for ComicID in args:
            if action == 'delete':
                myDB.action('DELETE from comics WHERE ComicID=?', [ComicID])
                myDB.action('DELETE from issues WHERE ComicID=?', [ComicID])
            elif action == 'pause':
                controlValueDict = {'ComicID': ComicID}
                newValueDict = {'Status': 'Paused'}
                myDB.upsert("comics", newValueDict, controlValueDict)
            elif action == 'resume':
                controlValueDict = {'ComicID': ComicID}
                newValueDict = {'Status': 'Active'}
                myDB.upsert("comics", newValueDict, controlValueDict)              
            else:
                comicsToAdd.append(ComicID)
        if len(comicsToAdd) > 0:
            logger.debug("Refreshing comics: %s" % comicsToAdd)
            #threading.Thread(target=importer.addComicIDListToDB, args=[comicsToAdd]).start()
            threading.Thread(target=updater.dbUpdate, args=[comicsToAdd]).start()
        raise cherrypy.HTTPRedirect("home")
    markComics.exposed = True
    
    def forceUpdate(self):
        from mylar import updater
        threading.Thread(target=updater.dbUpdate).start()
        raise cherrypy.HTTPRedirect("home")
    forceUpdate.exposed = True
    
    def forceSearch(self):
        from mylar import search
        threading.Thread(target=search.searchforissue).start()
        raise cherrypy.HTTPRedirect("home")
    forceSearch.exposed = True

    def forceRescan(self, ComicID):
        threading.Thread(target=updater.forceRescan, args=[ComicID]).start()
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    forceRescan.exposed = True
    
    def checkGithub(self):
        from mylar import versioncheck
        versioncheck.checkGithub()
        raise cherrypy.HTTPRedirect("home")
    checkGithub.exposed = True
    
    def history(self):
        myDB = db.DBConnection()
        history = myDB.select('''SELECT * from snatched order by DateAdded DESC''')
        return serve_template(templatename="history.html", title="History", history=history)
        return page
    history.exposed = True

    def reOrder(request):
        print ("I have reached the re-order!!!")
        return serve_template(templatename="reorder.html", title="ReoRdered!", reorder=request)
    reOrder.exposed = True

    def readlist(self):
        myDB = db.DBConnection()
        readlist = myDB.select("SELECT * from readinglist group by StoryArcID COLLATE NOCASE")
        issuelist = myDB.select("SELECT * from readlist")
        readConfig = {
                    "read2filename" : helpers.checked(mylar.READ2FILENAME),
                    "storyarcdir" : helpers.checked(mylar.STORYARCDIR)
               }
        return serve_template(templatename="readinglist.html", title="Readlist", readlist=readlist, issuelist=issuelist,readConfig=readConfig)
        return page
    readlist.exposed = True

    def detailReadlist(self,StoryArcID, StoryArcName):
        myDB = db.DBConnection()
        readlist = myDB.select("SELECT * from readinglist WHERE StoryArcID=? order by ReadingOrder ASC", [StoryArcID])
        readConfig = {
                    "read2filename" : helpers.checked(mylar.READ2FILENAME),
                    "storyarcdir" : helpers.checked(mylar.STORYARCDIR)
                     }
        return serve_template(templatename="readlist.html", title="Detailed Arc list", readlist=readlist, storyarcname=StoryArcName, storyarcid=StoryArcID, readConfig=readConfig)
    detailReadlist.exposed = True

    def removefromreadlist(self, IssueID=None, StoryArcID=None, IssueArcID=None, AllRead=None):
        myDB = db.DBConnection()
        if IssueID:
            myDB.action('DELETE from readlist WHERE IssueID=?', [IssueID])
            logger.info("Removed " + str(IssueID) + " from Reading List")
        elif StoryArcID:
            myDB.action('DELETE from readinglist WHERE StoryArcID=?', [StoryArcID])
            logger.info("Removed " + str(StoryArcID) + " from Story Arcs.")
        elif IssueArcID:
            myDB.action('DELETE from readinglist WHERE IssueArcID=?', [IssueArcID])
            logger.info("Removed " + str(IssueArcID) + " from the Story Arc.")
        elif AllRead:
            myDB.action("DELETE from readlist WHERE Status='Read'")
            logger.info("Removed All issues that have been marked as Read from Reading List")
    removefromreadlist.exposed = True

    def markasRead(self, IssueID=None, IssueArcID=None):
        myDB = db.DBConnection()
        if IssueID:
            issue = myDB.action('SELECT * from readlist WHERE IssueID=?', [IssueID]).fetchone()
            if issue['Status'] == 'Read':
                NewVal = {"Status":  "Added"}
            else:
                NewVal = {"Status":    "Read"}
            CtrlVal = {"IssueID":  IssueID}
            myDB.upsert("readlist", NewVal, CtrlVal)
            logger.info("Marked " + str(issue['ComicName']) + " #" + str(issue['Issue_Number']) + " as Read.")
        elif IssueArcID:
            issue = myDB.action('SELECT * from readinglist WHERE IssueArcID=?', [IssueArcID]).fetchone()
            if issue['Status'] == 'Read':
                NewVal = {"Status":    "Added"}
            else:
                NewVal = {"Status":    "Read"}
            CtrlVal = {"IssueArcID":  IssueArcID}
            myDB.upsert("readinglist", NewVal, CtrlVal)
            logger.info("Marked " +  str(issue['ComicName']) + " #" + str(issue['IssueNumber']) + " as Read.")
    markasRead.exposed = True

    def addtoreadlist(self, IssueID):
        myDB = db.DBConnection()
        readlist = myDB.action("SELECT * from issues where IssueID=?", [IssueID]).fetchone()
        comicinfo = myDB.action("SELECT * from comics where ComicID=?", [readlist['ComicID']]).fetchone()
        if readlist is None:
            logger.error("Cannot locate IssueID - aborting..")
        else:
            logger.info("attempting to add..issueid " + readlist['IssueID'])
            ctrlval = {"IssueID":       IssueID}
            newval = {"DateAdded":      helpers.today(),
                      "Status":         "added",
                      "ComicID":        readlist['ComicID'],
                      "Issue_Number":   readlist['Issue_Number'],
                      "IssueDate":      readlist['IssueDate'],
                      "SeriesYear":     comicinfo['ComicYear'],
                      "ComicName":      comicinfo['ComicName']}
            myDB.upsert("readlist", newval, ctrlval)
            logger.info("Added " + str(readlist['ComicName']) + " # " + str(readlist['Issue_Number']) + " to the Reading list.")
 
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % readlist['ComicID'])
    addtoreadlist.exposed = True

    def importReadlist(self,filename):
        from xml.dom.minidom import parseString, Element
        import random
        myDB = db.DBConnection()
  
        file = open(str(filename))
        data = file.read()
        file.close()

        dom = parseString(data)
        # of results
        storyarc = dom.getElementsByTagName('Name')[0].firstChild.wholeText
        tracks = dom.getElementsByTagName('Book')
        i = 1
        node = dom.documentElement
        print ("there are " + str(len(tracks)) + " issues in the story-arc: " + str(storyarc))
        #generate a random number for the ID, and tack on the total issue count to the end as a str :)
        storyarcid = str(random.randint(1000,9999)) + str(len(tracks))
        i = 1
        for book_element in tracks:
            st_issueid = str(storyarcid) + "_" + str(random.randint(1000,9999))
            comicname = book_element.getAttribute('Series')
            print ("comic: " + comicname)
            comicnumber = book_element.getAttribute('Number')
            print ("number: " + str(comicnumber))
            comicvolume = book_element.getAttribute('Volume')
            print ("volume: " + str(comicvolume))
            comicyear = book_element.getAttribute('Year')
            print ("year: " + str(comicyear))
            CtrlVal = {"IssueArcID": st_issueid}
            NewVals = {"StoryArcID":  storyarcid,
                       "ComicName":   comicname,
                       "IssueNumber": comicnumber,
                       "SeriesYear":  comicvolume,
                       "IssueYear":   comicyear,
                       "StoryArc":    storyarc,
                       "ReadingOrder": i,
                       "TotalIssues": len(tracks)}
            myDB.upsert("readinglist", NewVals, CtrlVal)
            i+=1
        raise cherrypy.HTTPRedirect("detailReadlist?StoryArcID=%s&StoryArcName=%s" % (storyarcid, storyarc))
    importReadlist.exposed = True

    #Story Arc Ascension...welcome to the next level :)
    def ArcWatchlist(self,StoryArcID=None):
        myDB = db.DBConnection()
        if StoryArcID:
            ArcWatch = myDB.select("SELECT * FROM readinglist WHERE StoryArcID=?", [StoryArcID])
        else:
            ArcWatch = myDB.select("SELECT * FROM readinglist")
        if ArcWatch is None: logger.info("No Story Arcs to search")
        else:
            Comics = myDB.select("SELECT * FROM comics")

            arc_match = []
            wantedlist = []

            showonreadlist = 1 # 0 won't show storyarcissues on readinglist main page, 1 will show 

            for arc in ArcWatch:
                logger.fdebug("arc: " + arc['storyarc'] + " : " + arc['ComicName'] + " : " + arc['IssueNumber'])
                #cycle through the story arcs here for matches on the watchlist
                mod_arc = re.sub('[\:/,\'\/\-\&\%\$\#\@\!\*\+\.]', '', arc['ComicName'])
                mod_arc = re.sub('\\bthe\\b', '', mod_arc.lower())
                mod_arc = re.sub('\\band\\b', '', mod_arc.lower())
                mod_arc = re.sub(r'\s', '', mod_arc)                    
                matcheroso = "no"
                for comic in Comics:
                    logger.fdebug("comic: " + comic['ComicName'])
                    mod_watch = re.sub('[\:\,\'\/\-\&\%\$\#\@\!\*\+\.]', '', comic['ComicName'])
                    mod_watch = re.sub('\\bthe\\b', '', mod_watch.lower())
                    mod_watch = re.sub('\\band\\b', '', mod_watch.lower())
                    mod_watch = re.sub(r'\s', '', mod_watch)
                    if mod_watch == mod_arc:# and arc['SeriesYear'] == comic['ComicYear']:
                        logger.fdebug("initial name match - confirming issue # is present in series")
                        if comic['ComicID'][:1] == 'G':                        
                            # if it's a multi-volume series, it's decimalized - let's get rid of the decimal.
                            GCDissue, whocares = helpers.decimal_issue(arc['IssueNumber'])
                            GCDissue = int(GCDissue) / 1000
                            if '.' not in str(GCDissue): GCDissue = str(GCDissue) + ".00"
                            logger.fdebug("issue converted to " + str(GCDissue))
                            isschk = myDB.action("SELECT * FROM issues WHERE ComicName=? AND Issue_Number=?", [comic['ComicName'], str(GCDissue)]).fetchone()
                        else:
                            isschk = myDB.action("SELECT * FROM issues WHERE ComicName=? AND Issue_Number=?", [comic['ComicName'], arc['IssueNumber']]).fetchone()               
                        if isschk is None:
                            logger.fdebug("we matched on name, but issue " + str(arc['IssueNumber']) + " doesn't exist for " + comic['ComicName'])
                        else:
                            #this gets ugly - if the name matches and the issue, it could still be wrong series
                            #use series year to break it down further.
                            if int(comic['ComicYear']) != int(arc['SeriesYear']):
                                logger.fdebug("Series years are different - discarding match. " + str(comic['ComicYear']) + " != " + str(arc['SeriesYear']))
                                break
                            logger.fdebug("issue #: " + str(arc['IssueNumber']) + " is present!")
                            print isschk
                            print ("Comicname: " + arc['ComicName'])
                            #print ("ComicID: " + str(isschk['ComicID']))
                            print ("Issue: " + arc['IssueNumber'])
                            print ("IssueArcID: " + arc['IssueArcID'])
                            #gather the matches now.
                            arc_match.append({ 
                                "match_name":          arc['ComicName'],
                                "match_id":            isschk['ComicID'],
                                "match_issue":         arc['IssueNumber'],
                                "match_issuearcid":    arc['IssueArcID'],
                                "match_seriesyear":    comic['ComicYear']})
                            matcheroso = "yes"
                if matcheroso == "no":
                    logger.fdebug("Unable to find a match for " + arc['ComicName'] + " :#" + str(arc['IssueNumber']))
                    wantedlist.append({
                         "ComicName":      arc['ComicName'],
                         "IssueNumber":    arc['IssueNumber'],
                         "IssueYear":      arc['IssueYear']})

            logger.fdebug("we matched on " + str(len(arc_match)) + " issues")

            for m_arc in arc_match:
                #now we cycle through the issues looking for a match.
                issue = myDB.action("SELECT * FROM issues where ComicID=? and Issue_Number=?", [m_arc['match_id'],m_arc['match_issue']]).fetchone()
                if issue is None: pass
                else:
                    logger.fdebug("issue: " + str(issue['Issue_Number']) + "..." + str(m_arc['match_issue']))
#                   if helpers.decimal_issue(issuechk['Issue_Number']) == helpers.decimal_issue(m_arc['match_issue']):
                    if issue['Issue_Number'] == m_arc['match_issue']:
                        logger.fdebug("we matched on " + str(issue['Issue_Number']) + " for " + str(m_arc['match_name']))
                        if issue['Status'] == 'Downloaded' or issue['Status'] == 'Archived':
                            ctrlVal = {"IssueArcID":  m_arc['match_issuearcid'] }
                            newVal = {"Status":   issue['Status'],
                                      "IssueID":  issue['IssueID']}
                            if showonreadlist:
                                showctrlVal = {"IssueID":       issue['IssueID']}
                                shownewVal = {"ComicName":      issue['ComicName'],
                                              "Issue_Number":    issue['Issue_Number'],
                                              "IssueDate":      issue['IssueDate'],
                                              "SeriesYear":     m_arc['match_seriesyear'],
                                              "ComicID":        m_arc['match_id']}
                                myDB.upsert("readlist", shownewVal, showctrlVal)

                            myDB.upsert("readinglist",newVal,ctrlVal)
                            logger.info("Already have " + issue['ComicName'] + " :# " + str(issue['Issue_Number']))
                        else:
                            logger.fdebug("We don't have " + issue['ComicName'] + " :# " + str(issue['Issue_Number']))
                            ctrlVal = {"IssueArcID":  m_arc['match_issuearcid'] }
                            newVal = {"Status":  "Wanted",
                                      "IssueID": issue['IssueID']}
                            myDB.upsert("readinglist",newVal,ctrlVal)
                            logger.info("Marked " + issue['ComicName'] + " :# " + str(issue['Issue_Number']) + " as Wanted.")
               

    ArcWatchlist.exposed = True

    def ReadGetWanted(self, StoryArcID):
        # this will queue up (ie. make 'Wanted') issues in a given Story Arc that are 'Not Watched'
        print StoryArcID
        stupdate = []
        myDB = db.DBConnection()
        wantedlist = myDB.select("SELECT * FROM readinglist WHERE StoryArcID=? AND Status is Null", [StoryArcID])
        if wantedlist is not None:
            for want in wantedlist:
                print want
                issuechk = myDB.action("SELECT * FROM issues WHERE IssueID=?", [want['IssueArcID']]).fetchone()
                SARC = want['StoryArc']
                IssueArcID = want['IssueArcID']
                if issuechk is None:
                    # none means it's not a 'watched' series
                    logger.fdebug("-- NOT a watched series queue.")
                    logger.fdebug(want['ComicName'] + " -- #" + str(want['IssueNumber']))
                    logger.info(u"Story Arc : " + str(SARC) + " queueing selected issue...")
                    logger.info(u"IssueArcID : " + str(IssueArcID))
                    foundcom = search.search_init(ComicName=want['ComicName'], IssueNumber=want['IssueNumber'], ComicYear=want['IssueYear'], SeriesYear=want['SeriesYear'], IssueDate=None, IssueID=None, AlternateSearch=None, UseFuzzy=None, ComicVersion=None, SARC=SARC, IssueArcID=IssueArcID)
                else:
                    # it's a watched series
                    logger.fdebug("-- watched series queue.")
                    logger.fdebug(issuechk['ComicName'] + " -- #" + str(issuechk['Issue_Number']))
                    foundcom = search.search_init(ComicName=issuechk['ComicName'], IssueNumber=issuechk['Issue_Number'], ComicYear=issuechk['IssueYear'], SeriesYear=issuechk['SeriesYear'], IssueDate=None, IssueID=issuechk['IssueID'], AlternateSearch=None, UseFuzzy=None, ComicVersion=None, SARC=SARC, IssueArcID=IssueArcID)
                if foundcom == "yes":
                    print "sucessfully found."
                else:
                    print "not sucessfully found."
                    stupdate.append({"Status":     "Wanted",
                                     "IssueArcID": IssueArcID,
                                     "IssueID":    "None"})

        watchlistchk = myDB.select("SELECT * FROM readinglist WHERE StoryArcID=? AND Status='Wanted'", [StoryArcID])
        if watchlistchk is not None:
            for watchchk in watchlistchk:
                print "Watchlist hit - " + str(watchchk)
                issuechk = myDB.action("SELECT * FROM issues WHERE IssueID=?", [watchchk['IssueArcID']]).fetchone()
                SARC = watchchk['StoryArc']
                IssueArcID = watchchk['IssueArcID']
                if issuechk is None:
                    # none means it's not a 'watched' series
                    logger.fdebug("-- NOT a watched series queue.")
                    logger.fdebug(watchchk['ComicName'] + " -- #" + str(want['IssueNumber']))
                    logger.info(u"Story Arc : " + str(SARC) + " queueing selected issue...")
                    logger.info(u"IssueArcID : " + str(IssueArcID))
                    foundcom = search.search_init(ComicName=watchchk['ComicName'], IssueNumber=watchchk['IssueNumber'], ComicYear=want['IssueYear'], SeriesYear=want['SeriesYear'], IssueDate=None, IssueID=None, AlternateSearch=None, UseFuzzy=None, ComicVersion=None, SARC=SARC, IssueArcID=IssueArcID)
                else:
                    # it's a watched series
                    logger.fdebug("-- watched series queue.")
                    logger.fdebug(issuechk['ComicName'] + " -- #" + str(issuechk['Issue_Number']))
                    foundcom = search.search_init(ComicName=issuechk['ComicName'], IssueNumber=issuechk['Issue_Number'], ComicYear=issuechk['IssueYear'], SeriesYear=issuechk['SeriesYear'], IssueDate=None, IssueID=issuechk['IssueID'], AlternateSearch=None, UseFuzzy=None, ComicVersion=None, SARC=SARC, IssueArcID=IssueArcID)
                if foundcom == "yes":
                    print "sucessfully found."
                else:
                    print "Watchlist issue not sucessfully found."
                    print "issuearcid: " + str(IssueArcID)
                    print "issueid: " + str(IssueID)
                    stupdate.append({"Status":     "Wanted",
                                     "IssueArcID": IssueArcID,
                                     "IssueID":    issuechk['IssueID']})

        if len(stupdate) > 0:
            print str(len(stupdate)) + " issues need to get updated to Wanted Status"
            for st in stupdate:
                ctrlVal = {'IssueArcID':  st['IssueArcID']}
                newVal = {'Status':   st['Status']}
                if st['IssueID']:
                    print "issueid:" + str(st['IssueID'])
                    newVal['IssueID'] = st['IssueID']
                myDB.upsert("readinglist", newVal, ctrlVal)
    ReadGetWanted.exposed = True


    def ReadMassCopy(self, StoryArcID, StoryArcName):
        #this copies entire story arcs into the /cache/<storyarc> folder
        #alternatively, it will copy the issues individually directly to a 3rd party device (ie.tablet)

        myDB = db.DBConnection()       
        copylist = myDB.select("SELECT * FROM readlist WHERE StoryArcID=? AND Status='Downloaded'", [StoryArcID])
        if copylist is None:
            logger.fdebug("You don't have any issues from " + StoryArcName + ". Aborting Mass Copy.")
            return
        else:
            dst = os.path.join(mylar.CACHE, StoryArcName)
            for files in copylist:
                
                copyloc = files['Location']

    ReadMassCopy.exposed = True

    def importLog(self, ComicName):
        myDB = db.DBConnection()
        impchk = myDB.action("SELECT * FROM importresults WHERE ComicName=?", [ComicName]).fetchone()
        if impchk is None:
            logger.error(u"No associated log found for this import : " + ComicName)
            return

        implog = impchk['implog'].replace("\n","<br />\n")
        return implog
       # return serve_template(templatename="importlog.html", title="Log", implog=implog)
    importLog.exposed = True

    def logs(self):
        if mylar.LOG_LEVEL is None or mylar.LOG_LEVEL == '':
            mylar.LOG_LEVEL = 'INFO'
        return serve_template(templatename="logs.html", title="Log", lineList=mylar.LOG_LIST, log_level=mylar.LOG_LEVEL)
    logs.exposed = True

    def log_change(self, loglevel):
        if log_level is not None:
            print ("changing logger to " + str(log_level))
            LOGGER.setLevel(log_level)
        return serve_template(templatename="logs.html", title="Log", lineList=mylar.LOG_LIST, log_level=log_level)
    log_change.exposed = True
    
    def clearhistory(self, type=None):
        myDB = db.DBConnection()
        if type == 'all':
            logger.info(u"Clearing all history")
            myDB.action('DELETE from snatched')
        else:
            logger.info(u"Clearing history where status is %s" % type)
            myDB.action('DELETE from snatched WHERE Status=?', [type])
        raise cherrypy.HTTPRedirect("history")
    clearhistory.exposed = True

    def downloadLocal(self, IssueID=None, IssueArcID=None, ReadOrder=None, dir=None):
        myDB = db.DBConnection()
        issueDL = myDB.action("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
        comicid = issueDL['ComicID']
        #print ("comicid: " + str(comicid))
        comic = myDB.action("SELECT * FROM comics WHERE ComicID=?", [comicid]).fetchone()
        #---issue info
        comicname = comic['ComicName']
        issuenum = issueDL['Issue_Number']
        issuedate = issueDL['IssueDate']
        seriesyear = comic['ComicYear']
        #---
        issueLOC = comic['ComicLocation']
        #print ("IssueLOC: " + str(issueLOC))
        issueFILE = issueDL['Location']
        #print ("IssueFILE: "+ str(issueFILE))
        issuePATH = os.path.join(issueLOC,issueFILE)
        #print ("IssuePATH: " + str(issuePATH))

        # if dir is None, it's a normal copy to cache kinda thing.
        # if dir is a path, then it's coming from the pullist as the location to put all the weekly comics
        if dir is not None:
            dstPATH = dir
        else:
            dstPATH = os.path.join(mylar.CACHE_DIR, issueFILE)
        #print ("dstPATH: " + str(dstPATH))
        if IssueID:
            ISnewValueDict = {'inCacheDIR':  'True',
                            'Location':    issueFILE}

        if IssueArcID:
            if mylar.READ2FILENAME: 
                #if it's coming from a StoryArc, check to see if we're appending the ReadingOrder to the filename
                ARCissueFILE = ReadOrder + "-" + issueFILE                
                dstPATH = os.path.join(mylar.CACHE_DIR, ARCissueFILE)        
                ISnewValueDict = {'inCacheDIR': 'True',
                                'Location':   issueFILE}

#            issueDL = myDB.action("SELECT * FROM readinglist WHERE IssueArcID=?", [IssueArcID]).fetchone()
#            storyarcid = issueDL['StoryArcID']
#            #print ("comicid: " + str(comicid))
#            issueLOC = mylar.DESTINATION_DIR
#            #print ("IssueLOC: " + str(issueLOC))
#            issueFILE = issueDL['Location']
#            #print ("IssueFILE: "+ str(issueFILE))
#            issuePATH = os.path.join(issueLOC,issueFILE)
#            #print ("IssuePATH: " + str(issuePATH))
#            dstPATH = os.path.join(mylar.CACHE_DIR, issueFILE)
#            #print ("dstPATH: " + str(dstPATH))

        try:
            shutil.copy2(issuePATH, dstPATH)
        except IOError as e:
            logger.error("Could not copy " + str(issuePATH) + " to " + str(dstPATH) + ". Copy to Cache terminated.")
            raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % comicid)
        logger.debug("sucessfully copied to cache...Enabling Download link")

        controlValueDict = {'IssueID': IssueID}
        RLnewValueDict = {'inCacheDIR':  'True',
                          'Location':    issueFILE,
                          'ComicID':     comicid,
                          'ComicName':   comicname,
                          'Issue_Number': issuenum,
                          'SeriesYear':  seriesyear,
                          'IssueDate':   issuedate}
        myDB.upsert("readlist", RLnewValueDict, controlValueDict)
        myDB.upsert("issues", ISnewValueDict, controlValueDict)
        if IssueArcID:
            controlValueD = {'IssueArcID':  IssueArcID}
            newValueDict = {'inCacheDIR': 'True',
                            'Location':   ARCissueFILE}
            myDB.upsert("readinglist", newValueDict, controlValueD)
        #print("DB updated - Download link now enabled.")

    downloadLocal.exposed = True

    def MassWeeklyDownload(self, pulldate, weekfolder=0):
        mylar.WEEKFOLDER = int(weekfolder)
        mylar.config_write()

        # this will download all downloaded comics from the weekly pull list and throw them
        # into a 'weekly' pull folder for those wanting to transfer directly to a 3rd party device.
        myDB = db.DBConnection()            
        if mylar.WEEKFOLDER:
            desdir = os.path.join(mylar.DESTINATION_DIR, pulldate)
            if os.path.isdir(desdir):
                logger.info(u"Directory (" + desdir + ") already exists! Continuing...")
            else:
                logger.info("Directory doesn't exist!")
                try:
                    os.makedirs(desdir)
                    logger.info(u"Directory successfully created at: " + desdir)
                except OSError:
                    logger.error(u"Could not create comicdir : " + desdir)
                    logger.error(u"Defaulting to : " + mylar.DESTINATION_DIR)
                    desdir = mylar.DESTINATION_DIR

        else:
            desdir = mylar.GRABBAG_DIR
        
        clist = myDB.select("SELECT * FROM Weekly WHERE Status='Downloaded'")
        if clist is None:   # nothing on the list, just go go gone
            logger.info("There aren't any issues downloaded from this week yet.")
        else:
            iscount = 0
            for cl in clist:
                isslist = myDB.select("SELECT * FROM Issues WHERE ComicID=? AND Status='Downloaded'", [cl['ComicID']])
                if isslist is None: pass # no issues found for comicid - boo/boo
                else:
                    for iss in isslist:
                        #go through issues downloaded until found one we want.
                        if iss['Issue_Number'] == cl['ISSUE']:
                            self.downloadLocal(iss['IssueID'], dir=desdir)
                            logger.info("Copied " + iss['ComicName'] + " #" + str(iss['Issue_Number']) + " to " + desdir.encode('utf-8').strip() )
                            iscount+=1
                            break
            logger.info("I have copied " + str(iscount) + " issues from this Week's pullist as requested.")
        raise cherrypy.HTTPRedirect("pullist")
    MassWeeklyDownload.exposed = True
    
    #for testing.
    def idirectory(self):    
        return serve_template(templatename="idirectory.html", title="Import a Directory")
    idirectory.exposed = True

    def confirmResult(self,comicname,comicid):
        #print ("here.")
        mode='series'
        sresults = mb.findComic(comicname, mode, None)
        #print sresults
        type='comic'
        return serve_template(templatename="searchresults.html", title='Import Results for: "' + comicname + '"',searchresults=sresults, type=type, imported='confirm', ogcname=comicid)
    confirmResult.exposed = True

    def comicScan(self, path, scan=0, redirect=None, autoadd=0, libraryscan=0, imp_move=0, imp_rename=0, imp_metadata=0):
        mylar.LIBRARYSCAN = libraryscan
        mylar.ADD_COMICS = autoadd
        mylar.COMIC_DIR = path
        mylar.IMP_MOVE = imp_move
        mylar.IMP_RENAME = imp_rename
        mylar.IMP_METADATA = imp_metadata
        mylar.config_write()
        if scan:
            try:
                soma,noids = librarysync.libraryScan()
            except Exception, e:
                logger.error('Unable to complete the scan: %s' % e)
                return
            if soma == "Completed":
                print ("sucessfully completed import.")
            else:
                logger.info(u"Starting mass importing..." + str(noids) + " records.")
                #this is what it should do...
                #store soma (the list of comic_details from importing) into sql table so import can be whenever
                #display webpage showing results
                #allow user to select comic to add (one at a time)
                #call addComic off of the webpage to initiate the add.
                #return to result page to finish or continue adding.
                #....
                #threading.Thread(target=self.searchit).start()
                #threadthis = threadit.ThreadUrl()
                #result = threadthis.main(soma)
                myDB = db.DBConnection()
                sl = 0
                print ("number of records: " + str(noids))
                while (sl < int(noids)):
                    soma_sl = soma['comic_info'][sl]
                    print ("soma_sl: " + str(soma_sl))
                    print ("comicname: " + soma_sl['comicname'].encode('utf-8'))
                    print ("filename: " + soma_sl['comfilename'].encode('utf-8'))
                    controlValue = {"impID":    soma_sl['impid']}
                    newValue = {"ComicYear":        soma_sl['comicyear'],
                                "Status":           "Not Imported",
                                "ComicName":        soma_sl['comicname'].encode('utf-8'),
                                "ComicFilename":    soma_sl['comfilename'].encode('utf-8'),
                                "ComicLocation":    soma_sl['comlocation'].encode('utf-8'),
                                "ImportDate":       helpers.today(),
                                "WatchMatch":       soma_sl['watchmatch']}      
                    myDB.upsert("importresults", newValue, controlValue)
                    sl+=1
                # because we could be adding volumes/series that span years, we need to account for this
                # add the year to the db under the term, valid-years
                # add the issue to the db under the term, min-issue
                
                #locate metadata here.
                # unzip -z filename.cbz will show the comment field of the zip which contains the metadata.

                # unzip -z filename.cbz < /dev/null  will remove the comment field, and thus the metadata.

                    
                #self.importResults()
                raise cherrypy.HTTPRedirect("importResults")
        if redirect:
            raise cherrypy.HTTPRedirect(redirect)
        else:
            raise cherrypy.HTTPRedirect("home")
    comicScan.exposed = True

    def importResults(self):
        myDB = db.DBConnection()
        results = myDB.select("SELECT * FROM importresults WHERE WatchMatch is Null OR WatchMatch LIKE 'C%' group by ComicName COLLATE NOCASE")
        #this is to get the count of issues;
        for result in results:
            countthis = myDB.action("SELECT count(*) FROM importresults WHERE ComicName=?", [result['ComicName']]).fetchall()
            countit = countthis[0][0]
            ctrlVal = {"ComicName":  result['ComicName']}
            newVal = {"IssueCount":       countit}
            myDB.upsert("importresults", newVal, ctrlVal)
            #logger.info("counted " + str(countit) + " issues for " + str(result['ComicName']))
        #need to reload results now
        results = myDB.select("SELECT * FROM importresults WHERE WatchMatch is Null OR WatchMatch LIKE 'C%' group by ComicName COLLATE NOCASE")
        watchresults = myDB.select("SELECT * FROM importresults WHERE WatchMatch is not Null AND WatchMatch NOT LIKE 'C%' group by ComicName COLLATE NOCASE")
        return serve_template(templatename="importresults.html", title="Import Results", results=results, watchresults=watchresults)
    importResults.exposed = True

    def deleteimport(self, ComicName):
        myDB = db.DBConnection()
        logger.info("Removing import data for Comic: " + ComicName)
        myDB.action('DELETE from importresults WHERE ComicName=?', [ComicName])
        raise cherrypy.HTTPRedirect("importResults")
    deleteimport.exposed = True

    def preSearchit(self, ComicName, comiclist=None, mimp=0):
        implog = ''
        implog = implog + "imp_rename:" + str(imp_rename) + "\n"
        implog = implog + "imp_move:" + str(imp_move) + "\n"
        if mimp == 0:
            comiclist = []
            comiclist.append(ComicName) 
        for cl in comiclist:
            ComicName = cl
            implog = implog + "comicName: " + str(ComicName) + "\n"
            myDB = db.DBConnection()
            results = myDB.action("SELECT * FROM importresults WHERE ComicName=?", [ComicName])
            #if results > 0:
            #    print ("There are " + str(results[7]) + " issues to import of " + str(ComicName))
            #build the valid year ranges and the minimum issue# here to pass to search.
            yearRANGE = []
            yearTOP = 0
            minISSUE = 0
            startISSUE = 10000000
            comicstoIMP = []

            movealreadyonlist = "no"
            movedata = []

            for result in results:
                if result is None:
                    break

                if result['WatchMatch']:
                    watchmatched = result['WatchMatch']
                else:
                    watchmatched = ''

                if watchmatched.startswith('C'):
                    implog = implog + "Confirmed. ComicID already provided - initiating auto-magik mode for import.\n"
                    comicid = result['WatchMatch'][1:]
                    implog = implog + result['WatchMatch'] + " .to. " + str(comicid) + "\n"
                    #since it's already in the watchlist, we just need to move the files and re-run the filechecker.
                    #self.refreshArtist(comicid=comicid,imported='yes')
                    if mylar.IMP_MOVE:
                        implog = implog + "Mass import - Move files\n"
                        comloc = myDB.action("SELECT * FROM comics WHERE ComicID=?", [comicid]).fetchone()

                        movedata_comicid = comicid
                        movedata_comiclocation = comloc['ComicLocation']
                        movedata_comicname = ComicName
                        movealreadyonlist = "yes"
                        #mylar.moveit.movefiles(comicid,comloc['ComicLocation'],ComicName)
                        #check for existing files... (this is already called after move files in importer)
                        #updater.forceRescan(comicid)
                    else:
                        implog = implog + "nothing to do if I'm not moving.\n"
                        raise cherrypy.HTTPRedirect("importResults")
                else:
                    comicstoIMP.append(result['ComicLocation'].decode(mylar.SYS_ENCODING, 'replace'))
                    getiss = result['impID'].rfind('-')
                    getiss = result['impID'][getiss+1:]
                    imlog = implog + "figured issue is : " + str(getiss) + "\n"
                    if (result['ComicYear'] not in yearRANGE) or (yearRANGE is None):
                        if result['ComicYear'] <> "0000":
                            implog = implog + "adding..." + str(result['ComicYear']) + "\n"
                            yearRANGE.append(result['ComicYear'])
                            yearTOP = str(result['ComicYear'])
                    if int(getiss) > int(minISSUE):
                        implog = implog + "issue now set to : " + str(getiss) + " ... it was : " + str(minISSUE) + "\n"
                        minISSUE = str(getiss)
                    if int(getiss) < int(startISSUE):
                        implog = implog + "issue now set to : " + str(getiss) + " ... it was : " + str(startISSUE) + "\n"
                        startISSUE = str(getiss)
     
            #taking this outside of the transaction in an attempt to stop db locking.
            if mylar.IMP_MOVE and movealreadyonlist == "yes":
#                 for md in movedata:
                 mylar.moveit.movefiles(movedata_comicid, movedata_comiclocation, movedata_comicname)
                 updater.forceRescan(comicid)

                 raise cherrypy.HTTPRedirect("importResults")

            #figure out # of issues and the year range allowable
            if yearTOP > 0:
                maxyear = int(yearTOP) - (int(minISSUE) / 12)
                yearRANGE.append(str(maxyear))
                implog = implog + "there is a " + str(maxyear) + " year variation based on the 12 issues/year\n"
            else:
                implog = implog + "no year detected in any issues...Nulling the value\n"
                yearRANGE = None
            #determine a best-guess to # of issues in series
            #this needs to be reworked / refined ALOT more.
            #minISSUE = highest issue #, startISSUE = lowest issue #
            numissues = int(minISSUE) - int(startISSUE)
            #normally minissue would work if the issue #'s started at #1.
            implog = implog + "the years involved are : " + str(yearRANGE) + "\n"
            implog = implog + "highest issue # is : " + str(minISSUE) + "\n"
            implog = implog + "lowest issue # is : " + str(startISSUE) + "\n"
            implog = implog + "approximate number of issues : " + str(numissues) + "\n"
            implog = implog + "issues present on system : " + str(len(comicstoIMP)) + "\n"
            implog = implog + "versioning checking on filenames: \n"
            cnsplit = ComicName.split()
            #cnwords = len(cnsplit)
            #cnvers = cnsplit[cnwords-1]
            ogcname = ComicName
            for splitt in cnsplit:
                print ("split")
                if 'v' in str(splitt):
                    implog = implog + "possible versioning detected.\n"
                    if splitt[1:].isdigit():
                        implog = implog + splitt + "  - assuming versioning. Removing from initial search pattern.\n"
                        ComicName = re.sub(str(splitt), '', ComicName)
                        implog = implog + "new comicname is : " + ComicName + "\n"
            # we need to pass the original comicname here into the entire importer module
            # so that we can reference the correct issues later.
        
            mode='series'
            if yearRANGE is None:
                sresults = mb.findComic(ComicName, mode, issue=numissues)
            else:
                sresults = mb.findComic(ComicName, mode, issue=numissues, limityear=yearRANGE)
            type='comic'

            if len(sresults) == 1:
                sr = sresults[0]
                implog = implog + "only one result...automagik-mode enabled for " + ComicName + " :: " + str(sr['comicid']) + "\n"
                resultset = 1
#            #need to move the files here.
            elif len(sresults) == 0 or len(sresults) is None:
                implog = implog + "no results, removing the year from the agenda and re-querying.\n"
                sresults = mb.findComic(ComicName, mode, issue=numissues)
                if len(sresults) == 1:
                    sr = sresults[0]
                    implog = implog + "only one result...automagik-mode enabled for " + ComicName + " :: " + str(sr['comicid']) + "\n"
                    resultset = 1
                else: 
                    resultset = 0
            else:
                implog = implog + "returning results to screen - more than one possibility.\n"
                resultset = 0

            #write implog to db here.
            print "Writing import log to db for viewing pleasure."
            ctrlVal = {"ComicName":  ComicName}
            newVal = {"implog":       implog}
            myDB.upsert("importresults", newVal, ctrlVal)

            if resultset == 1:
                #implog = implog + "ogcname -- " + str(ogcname) + "\n"
                cresults = self.addComic(comicid=sr['comicid'],comicname=sr['name'],comicyear=sr['comicyear'],comicpublisher=sr['publisher'],comicimage=sr['comicimage'],comicissues=sr['issues'],imported='yes',ogcname=ogcname)  #imported=comicstoIMP,ogcname=ogcname)
                return serve_template(templatename="searchfix.html", title="Error Check", comicname=sr['name'], comicid=sr['comicid'], comicyear=sr['comicyear'], comicimage=sr['comicimage'], comicissues=sr['issues'], cresults=cresults, imported='yes', ogcname=str(ogcname))
            else:
                return serve_template(templatename="searchresults.html", title='Import Results for: "' + ComicName + '"',searchresults=sresults, type=type, imported='yes', ogcname=ogcname) #imported=comicstoIMP, ogcname=ogcname)
    preSearchit.exposed = True

    #---
    def config(self):
    
        interface_dir = os.path.join(mylar.PROG_DIR, 'data/interfaces/')
        interface_list = [ name for name in os.listdir(interface_dir) if os.path.isdir(os.path.join(interface_dir, name)) ]

#        branch_history, err = mylar.versioncheck.runGit("log --oneline --pretty=format:'%h - %ar - %s' -n 4")
#        br_hist = branch_history.replace("\n", "<br />\n")
        myDB = db.DBConnection()
        CCOMICS = myDB.action("SELECT COUNT(*) FROM comics").fetchall()
        CHAVES = myDB.action("SELECT COUNT(*) FROM issues WHERE Status='Downloaded' OR Status='Archived'").fetchall()
        CISSUES = myDB.action("SELECT COUNT(*) FROM issues").fetchall()
        CSIZE = myDB.action("select SUM(ComicSize) from issues where Status='Downloaded' or Status='Archived'").fetchall()
        COUNT_COMICS = CCOMICS[0][0]
        COUNT_HAVES = CHAVES[0][0]
        COUNT_ISSUES = CISSUES[0][0]
        COUNT_SIZE = helpers.human_size(CSIZE[0][0])
        comicinfo = { "COUNT_COMICS" : COUNT_COMICS,
                      "COUNT_HAVES" : COUNT_HAVES,
                      "COUNT_ISSUES" : COUNT_ISSUES,
                      "COUNT_SIZE" : COUNT_SIZE }

        config = { 
                    "http_host" : mylar.HTTP_HOST,
                    "http_user" : mylar.HTTP_USERNAME,
                    "http_port" : mylar.HTTP_PORT,
                    "http_pass" : mylar.HTTP_PASSWORD,
                    "launch_browser" : helpers.checked(mylar.LAUNCH_BROWSER),
                    "logverbose" : helpers.checked(mylar.LOGVERBOSE),
                    "download_scan_interval" : mylar.DOWNLOAD_SCAN_INTERVAL,
                    "nzb_search_interval" : mylar.SEARCH_INTERVAL,
                    "nzb_startup_search" : helpers.checked(mylar.NZB_STARTUP_SEARCH),
                    "libraryscan_interval" : mylar.LIBRARYSCAN_INTERVAL,
                    "search_delay" : mylar.SEARCH_DELAY,
                    "use_sabnzbd" : helpers.checked(mylar.USE_SABNZBD),
                    "sab_host" : mylar.SAB_HOST,
                    "sab_user" : mylar.SAB_USERNAME,
                    "sab_api" : mylar.SAB_APIKEY,
                    "sab_pass" : mylar.SAB_PASSWORD,
                    "sab_cat" : mylar.SAB_CATEGORY,
                    "sab_priority" : mylar.SAB_PRIORITY,
                    "sab_directory" : mylar.SAB_DIRECTORY,
                    "use_nzbget" : helpers.checked(mylar.USE_NZBGET),
                    "nzbget_host" : mylar.NZBGET_HOST,
                    "nzbget_port" : mylar.NZBGET_PORT,
                    "nzbget_user" : mylar.NZBGET_USERNAME,
                    "nzbget_pass" : mylar.NZBGET_PASSWORD,
                    "nzbget_cat" : mylar.NZBGET_CATEGORY,
                    "nzbget_priority" : mylar.NZBGET_PRIORITY,
                    "use_blackhole" : helpers.checked(mylar.BLACKHOLE),
                    "blackhole_dir" : mylar.BLACKHOLE_DIR,
                    "usenet_retention" : mylar.USENET_RETENTION,
                    "use_nzbsu" : helpers.checked(mylar.NZBSU),
                    "nzbsu_api" : mylar.NZBSU_APIKEY,
                    "use_dognzb" : helpers.checked(mylar.DOGNZB),
                    "dognzb_api" : mylar.DOGNZB_APIKEY,
                    "use_nzbx" : helpers.checked(mylar.NZBX),
                    "use_experimental" : helpers.checked(mylar.EXPERIMENTAL),
                    "use_newznab" : helpers.checked(mylar.NEWZNAB),
                    "newznab_host" : mylar.NEWZNAB_HOST,
                    "newznab_api" : mylar.NEWZNAB_APIKEY,
                    "newznab_enabled" : helpers.checked(mylar.NEWZNAB_ENABLED),
                    "extra_newznabs" : mylar.EXTRA_NEWZNABS,
                    "destination_dir" : mylar.DESTINATION_DIR,
                    "chmod_dir" : mylar.CHMOD_DIR,
                    "chmod_file" : mylar.CHMOD_FILE,
                    "replace_spaces" : helpers.checked(mylar.REPLACE_SPACES),
                    "replace_char" : mylar.REPLACE_CHAR,
                    "use_minsize" : helpers.checked(mylar.USE_MINSIZE),
                    "minsize" : mylar.MINSIZE,
                    "use_maxsize" : helpers.checked(mylar.USE_MAXSIZE),
                    "maxsize" : mylar.MAXSIZE,
                    "interface_list" : interface_list,
                    "autowant_all" : helpers.checked(mylar.AUTOWANT_ALL),
                    "autowant_upcoming" : helpers.checked(mylar.AUTOWANT_UPCOMING),
                    "comic_cover_local" : helpers.checked(mylar.COMIC_COVER_LOCAL),
                    "pref_qual_0" : helpers.radio(mylar.PREFERRED_QUALITY, 0),
                    "pref_qual_1" : helpers.radio(mylar.PREFERRED_QUALITY, 1),
                    "pref_qual_3" : helpers.radio(mylar.PREFERRED_QUALITY, 3),
                    "pref_qual_2" : helpers.radio(mylar.PREFERRED_QUALITY, 2),
                    "move_files" : helpers.checked(mylar.MOVE_FILES),
                    "rename_files" : helpers.checked(mylar.RENAME_FILES),
                    "folder_format" : mylar.FOLDER_FORMAT,
                    "file_format" : mylar.FILE_FORMAT,
                    "zero_level" : helpers.checked(mylar.ZERO_LEVEL),
                    "zero_level_n" : mylar.ZERO_LEVEL_N,
                    "add_to_csv" : helpers.checked(mylar.ADD_TO_CSV),
                    "cvinfo" : helpers.checked(mylar.CVINFO),
                    "lowercase_filenames" : helpers.checked(mylar.LOWERCASE_FILENAMES),
                    "syno_fix" : helpers.checked(mylar.SYNO_FIX),
                    "cvapifix" : helpers.checked(mylar.CVAPIFIX),
                    "prowl_enabled": helpers.checked(mylar.PROWL_ENABLED),
                    "prowl_onsnatch": helpers.checked(mylar.PROWL_ONSNATCH),
                    "prowl_keys": mylar.PROWL_KEYS,
                    "prowl_priority": mylar.PROWL_PRIORITY,
                    "nma_enabled": helpers.checked(mylar.NMA_ENABLED),
                    "nma_apikey": mylar.NMA_APIKEY,
                    "nma_priority": int(mylar.NMA_PRIORITY),
                    "nma_onsnatch": helpers.checked(mylar.NMA_ONSNATCH),
                    "pushover_enabled": helpers.checked(mylar.PUSHOVER_ENABLED),
                    "pushover_onsnatch": helpers.checked(mylar.PUSHOVER_ONSNATCH),
                    "pushover_apikey": mylar.PUSHOVER_APIKEY,
                    "pushover_userkey": mylar.PUSHOVER_USERKEY,
                    "pushover_priority": mylar.PUSHOVER_PRIORITY,
                    "enable_extra_scripts" : helpers.checked(mylar.ENABLE_EXTRA_SCRIPTS),
                    "extra_scripts" : mylar.EXTRA_SCRIPTS,
                    "post_processing" : helpers.checked(mylar.POST_PROCESSING),
                    "enable_meta" : helpers.checked(mylar.ENABLE_META),
                    "cmtagger_path" : mylar.CMTAGGER_PATH,
                    "branch" : version.MYLAR_VERSION,
                    "br_type" : mylar.INSTALL_TYPE,
                    "br_version" : mylar.versioncheck.getVersion(),
                    "py_version" : platform.python_version(),
                    "data_dir" : mylar.DATA_DIR,
                    "prog_dir" : mylar.PROG_DIR,
                    "cache_dir" : mylar.CACHE_DIR,
                    "config_file" : mylar.CONFIG_FILE,
#                    "branch_history" : br_hist
                    "enable_pre_scripts" : helpers.checked(mylar.ENABLE_PRE_SCRIPTS),
                    "pre_scripts" : mylar.PRE_SCRIPTS,
                    "log_dir" : mylar.LOG_DIR
               }
        return serve_template(templatename="config.html", title="Settings", config=config, comicinfo=comicinfo)  
    config.exposed = True

    def error_change(self, comicid, errorgcd, comicname, comicyear, imported=None, mogcname=None):
        # if comicname contains a "," it will break the exceptions import.
        import urllib
        b = urllib.unquote_plus(comicname)
#        cname = b.decode("utf-8")
        cname = b.encode('utf-8')
        cname = re.sub("\,", "", cname)

        if mogcname != None:
            c = urllib.unquote_plus(mogcname)
            ogcname = c.encode('utf-8')
        else:
            ogcname = None

        if errorgcd[:5].isdigit():
            logger.info("GCD-ID detected : " + str(errorgcd)[:5])
            logger.info("ogcname: " + str(ogcname))
            logger.info("I'm assuming you know what you're doing - going to force-match for " + cname)
            self.from_Exceptions(comicid=comicid,gcdid=errorgcd,comicname=cname,comicyear=comicyear,imported=imported,ogcname=ogcname)
        else:
            logger.info("Assuming rewording of Comic - adjusting to : " + str(errorgcd))
            Err_Info = mylar.cv.getComic(comicid,'comic')
            self.addComic(comicid=comicid,comicname=str(errorgcd), comicyear=Err_Info['ComicYear'], comicissues=Err_Info['ComicIssues'], comicpublisher=Err_Info['ComicPublisher'])

    error_change.exposed = True

    def comic_config(self, com_location, ComicID, alt_search=None, fuzzy_year=None, comic_version=None):
        myDB = db.DBConnection()
#--- this is for multipe search terms............
#--- works, just need to redo search.py to accomodate multiple search terms
#        ffs_alt = []
#        if '+' in alt_search:
            #find first +
#            ffs = alt_search.find('+')
#            ffs_alt.append(alt_search[:ffs])
#            ffs_alt_st = str(ffs_alt[0])
#            print("ffs_alt: " + str(ffs_alt[0]))

            # split the entire string by the delimter + 
#            ffs_test = alt_search.split('+')
#            if len(ffs_test) > 0:
#                print("ffs_test names: " + str(len(ffs_test)))
#                ffs_count = len(ffs_test)
#                n=1
#                while (n < ffs_count):
#                    ffs_alt.append(ffs_test[n])
#                    print("adding : " + str(ffs_test[n]))
                    #print("ffs_alt : " + str(ffs_alt))
#                    ffs_alt_st = str(ffs_alt_st) + "..." + str(ffs_test[n])
#                    n+=1
#            asearch = ffs_alt
#        else:
#            asearch = alt_search
        asearch = str(alt_search)

        controlValueDict = {'ComicID': ComicID}
        newValues = {"ComicLocation":        com_location }
                     #"QUALalt_vers":         qual_altvers,
                     #"QUALScanner":          qual_scanner,
                     #"QUALtype":             qual_type,
                     #"QUALquality":          qual_quality
                     #}
        if asearch is not None:
            if re.sub(r'\s', '',asearch) == '':
                newValues['AlternateSearch'] = "None"
            else:
                newValues['AlternateSearch'] = str(asearch)
        else:
            newValues['AlternateSearch'] = "None"

        if fuzzy_year is None:
            newValues['UseFuzzy'] = "0"
        else:
            newValues['UseFuzzy'] = str(fuzzy_year)
        
        if comic_version is None or comic_version == 'None':
            newValues['ComicVersion'] = "None"
        else:
            if comic_version[1:].isdigit() and comic_version[:1].lower() == 'v':
                newValues['ComicVersion'] = str(comic_version)
            else:
                logger.info("Invalid Versioning entered - it must be in the format of v#")
                newValues['ComicVersion'] = "None"

        #force the check/creation of directory com_location here
        if os.path.isdir(str(com_location)):
            logger.info(u"Validating Directory (" + str(com_location) + "). Already exists! Continuing...")
        else:
            logger.fdebug("Updated Directory doesn't exist! - attempting to create now.")
            #try:
            #    os.makedirs(str(com_location))
            #    logger.info(u"Directory successfully created at: " + str(com_location))
            #except OSError:
            #    logger.error(u"Could not create comicdir : " + str(com_location))
            filechecker.validateAndCreateDirectory(com_location, True)

        myDB.upsert("comics", newValues, controlValueDict)
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    comic_config.exposed = True

    def readOptions(self, read2filename, storyarcdir):
        mylar.READ2FILENAME = int(read2filename)
        mylar.STORYARCDIR = int(storyarcdir)
        mylar.config_write()

        #force the check/creation of directory com_location here
        if mylar.STORYARCDIR:
            arcdir = os.path.join(mylar.DESTINATION_DIR, 'StoryArcs')
            if os.path.isdir(str(arcdir)):
                logger.info(u"Validating Directory (" + str(arcdir) + "). Already exists! Continuing...")
            else:
                logger.fdebug("Updated Directory doesn't exist! - attempting to create now.")
                filechecker.validateAndCreateDirectory(arcdir, True)
    readOptions.exposed = True

    
    def configUpdate(self, http_host='0.0.0.0', http_username=None, http_port=8090, http_password=None, launch_browser=0, logverbose=0, download_scan_interval=None, nzb_search_interval=None, nzb_startup_search=0, libraryscan_interval=None,
        use_sabnzbd=0, sab_host=None, sab_username=None, sab_apikey=None, sab_password=None, sab_category=None, sab_priority=None, sab_directory=None, log_dir=None, log_level=0, blackhole=0, blackhole_dir=None,
        use_nzbget=0, nzbget_host=None, nzbget_port=None, nzbget_username=None, nzbget_password=None, nzbget_category=None, nzbget_priority=None,
        usenet_retention=None, nzbsu=0, nzbsu_apikey=None, dognzb=0, dognzb_apikey=None, nzbx=0, newznab=0, newznab_host=None, newznab_apikey=None, newznab_enabled=0,
        raw=0, raw_provider=None, raw_username=None, raw_password=None, raw_groups=None, experimental=0,
        enable_meta=0, cmtagger_path=None, 
        prowl_enabled=0, prowl_onsnatch=0, prowl_keys=None, prowl_priority=None, nma_enabled=0, nma_apikey=None, nma_priority=0, nma_onsnatch=0, pushover_enabled=0, pushover_onsnatch=0, pushover_apikey=None, pushover_userkey=None, pushover_priority=None,
        preferred_quality=0, move_files=0, rename_files=0, add_to_csv=1, cvinfo=0, lowercase_filenames=0, folder_format=None, file_format=None, enable_extra_scripts=0, extra_scripts=None, enable_pre_scripts=0, pre_scripts=None, post_processing=0, syno_fix=0, search_delay=None, chmod_dir=0777, chmod_file=0660, cvapifix=0,
        destination_dir=None, replace_spaces=0, replace_char=None, use_minsize=0, minsize=None, use_maxsize=0, maxsize=None, autowant_all=0, autowant_upcoming=0, comic_cover_local=0, zero_level=0, zero_level_n=None, interface=None, **kwargs):
        mylar.HTTP_HOST = http_host
        mylar.HTTP_PORT = http_port
        mylar.HTTP_USERNAME = http_username
        mylar.HTTP_PASSWORD = http_password
        mylar.LAUNCH_BROWSER = launch_browser
        mylar.LOGVERBOSE = logverbose
        mylar.DOWNLOAD_SCAN_INTERVAL = download_scan_interval
        mylar.SEARCH_INTERVAL = nzb_search_interval
        mylar.NZB_STARTUP_SEARCH = nzb_startup_search
        mylar.LIBRARYSCAN_INTERVAL = libraryscan_interval
        mylar.SEARCH_DELAY = search_delay
        mylar.USE_SABNZBD = use_sabnzbd
        mylar.SAB_HOST = sab_host
        mylar.SAB_USERNAME = sab_username
        mylar.SAB_PASSWORD = sab_password      
        mylar.SAB_APIKEY = sab_apikey
        mylar.SAB_CATEGORY = sab_category
        mylar.SAB_PRIORITY = sab_priority
        mylar.SAB_DIRECTORY = sab_directory
        mylar.USE_NZBGET = use_nzbget
        mylar.NZBGET_HOST = nzbget_host
        mylar.NZBGET_USERNAME = nzbget_username
        mylar.NZBGET_PASSWORD = nzbget_password
        mylar.NZBGET_PORT = nzbget_port
        mylar.NZBGET_CATEGORY = nzbget_category
        mylar.NZBGET_PRIORITY = nzbget_priority
        mylar.BLACKHOLE = blackhole
        mylar.BLACKHOLE_DIR = blackhole_dir
        mylar.USENET_RETENTION = usenet_retention
        mylar.NZBSU = nzbsu
        mylar.NZBSU_APIKEY = nzbsu_apikey
        mylar.DOGNZB = dognzb
        mylar.DOGNZB_APIKEY = dognzb_apikey
        mylar.NZBX = nzbx
        mylar.RAW = raw
        mylar.RAW_PROVIDER = raw_provider
        mylar.RAW_USERNAME = raw_username
        mylar.RAW_PASSWORD = raw_password
        mylar.RAW_GROUPS = raw_groups
        mylar.EXPERIMENTAL = experimental
        mylar.NEWZNAB = newznab
        #mylar.NEWZNAB_HOST = newznab_host
        #mylar.NEWZNAB_APIKEY = newznab_apikey
        #mylar.NEWZNAB_ENABLED = newznab_enabled
        mylar.PREFERRED_QUALITY = int(preferred_quality)
        mylar.MOVE_FILES = move_files
        mylar.RENAME_FILES = rename_files
        mylar.REPLACE_SPACES = replace_spaces
        mylar.REPLACE_CHAR = replace_char
        mylar.ZERO_LEVEL = zero_level
        mylar.ZERO_LEVEL_N = zero_level_n
        mylar.ADD_TO_CSV = add_to_csv
        mylar.CVINFO = cvinfo
        mylar.LOWERCASE_FILENAMES = lowercase_filenames
        mylar.SYNO_FIX = syno_fix
        mylar.CVAPIFIX = cvapifix
        mylar.PROWL_ENABLED = prowl_enabled
        mylar.PROWL_ONSNATCH = prowl_onsnatch
        mylar.PROWL_KEYS = prowl_keys
        mylar.PROWL_PRIORITY = prowl_priority
        mylar.NMA_ENABLED = nma_enabled
        mylar.NMA_APIKEY = nma_apikey
        mylar.NMA_PRIORITY = nma_priority
        mylar.NMA_ONSNATCH = nma_onsnatch
        mylar.PUSHOVER_ENABLED = pushover_enabled
        mylar.PUSHOVER_APIKEY = pushover_apikey
        mylar.PUSHOVER_USERKEY = pushover_userkey
        mylar.PUSHOVER_PRIORITY = pushover_priority
        mylar.PUSHOVER_ONSNATCH = pushover_onsnatch
        mylar.USE_MINSIZE = use_minsize
        mylar.MINSIZE = minsize
        mylar.USE_MAXSIZE = use_maxsize
        mylar.MAXSIZE = maxsize
        mylar.FOLDER_FORMAT = folder_format
        mylar.FILE_FORMAT = file_format
        mylar.DESTINATION_DIR = destination_dir
        mylar.AUTOWANT_ALL = autowant_all
        mylar.AUTOWANT_UPCOMING = autowant_upcoming
        mylar.COMIC_COVER_LOCAL = comic_cover_local
        mylar.INTERFACE = interface
        mylar.ENABLE_EXTRA_SCRIPTS = enable_extra_scripts
        mylar.EXTRA_SCRIPTS = extra_scripts
        mylar.ENABLE_PRE_SCRIPTS = enable_pre_scripts
        mylar.POST_PROCESSING = post_processing
        mylar.PRE_SCRIPTS = pre_scripts
        mylar.ENABLE_META = enable_meta
        mylar.CMTAGGER_PATH = cmtagger_path
        mylar.LOG_DIR = log_dir
        mylar.LOG_LEVEL = log_level
        mylar.CHMOD_DIR = chmod_dir
        mylar.CHMOD_FILE = chmod_file
        # Handle the variable config options. Note - keys with False values aren't getting passed

        mylar.EXTRA_NEWZNABS = []
        #changing this for simplicty - adding all newznabs into extra_newznabs
        if newznab_host is not None:
            #this
            mylar.EXTRA_NEWZNABS.append((newznab_host, newznab_apikey, int(newznab_enabled)))

        for kwarg in kwargs:
            if kwarg.startswith('newznab_host'):
                newznab_number = kwarg[12:]
                newznab_host = kwargs['newznab_host' + newznab_number]
                newznab_api = kwargs['newznab_api' + newznab_number]
                try:
                    newznab_enabled = int(kwargs['newznab_enabled' + newznab_number])
                except KeyError:
                    newznab_enabled = 0

                mylar.EXTRA_NEWZNABS.append((newznab_host, newznab_api, newznab_enabled))

        # Sanity checking
        if mylar.SEARCH_INTERVAL < 360:
            logger.info("Search interval too low. Resetting to 6 hour minimum")
            mylar.SEARCH_INTERVAL = 360

        if mylar.SEARCH_DELAY < 1:
            logger.info("Minimum search delay set for 1 minute to avoid hammering.")
            mylar.SEARCH_DELAY = 1

        if not helpers.is_number(mylar.CHMOD_DIR):
            logger.info("CHMOD Directory value is not a valid numeric - please correct. Defaulting to 0777")
            mylar.CHMOD_DIR = '0777'

        if not helpers.is_number(mylar.CHMOD_FILE):
            logger.info("CHMOD File value is not a valid numeric - please correct. Defaulting to 0660")
            mylar.CHMOD_FILE = '0660'

        if mylar.ENABLE_META:
            if mylar.CMTAGGER_PATH is None or mylar.CMTAGGER_PATH == '':
                logger.info("ComicTagger Path not set - defaulting to Mylar Program Directory : " + mylar.PROG_DIR)
                mylar.CMTAGGER_PATH = mylar.PROG_DIR

        # Write the config
        mylar.config_write()

        raise cherrypy.HTTPRedirect("config")
        
    configUpdate.exposed = True

    def shutdown(self):
        mylar.SIGNAL = 'shutdown'
        message = 'Shutting Down...'
        return serve_template(templatename="shutdown.html", title="Shutting Down", message=message, timer=15)
        return page

    shutdown.exposed = True

    def restart(self):
        mylar.SIGNAL = 'restart'
        message = 'Restarting...'
        return serve_template(templatename="shutdown.html", title="Restarting", message=message, timer=30)
    restart.exposed = True
    
    def update(self):
        mylar.SIGNAL = 'update'
        message = 'Updating...<br/><small>Main screen will appear in 60s</small>'
        return serve_template(templatename="shutdown.html", title="Updating", message=message, timer=30)
        return page
    update.exposed = True
        
    def getInfo(self, ComicID=None, IssueID=None):
        
        from mylar import cache
        info_dict = cache.getInfo(ComicID, IssueID)
        
        return simplejson.dumps(info_dict)
        
    getInfo.exposed = True
    
    def getComicArtwork(self, ComicID=None, imageURL=None):
        
        from mylar import cache
        logger.info(u"Retrieving image for : " + comicID)
        return cache.getArtwork(ComicID, imageURL)
        
    getComicArtwork.exposed = True
    
