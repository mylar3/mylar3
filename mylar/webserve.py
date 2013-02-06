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
import Queue
import urllib
import shutil

import mylar

from mylar import logger, db, importer, mb, search, filechecker, helpers, updater, parseit, weeklypull, PostProcessor, version, librarysync
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
        issues = myDB.select('SELECT * from issues WHERE ComicID=? order by Int_IssueNumber DESC', [ComicID])
        if comic is None:
            raise cherrypy.HTTPRedirect("home")
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
        return serve_template(templatename="artistredone.html", title=comic['ComicName'], comic=comic, issues=issues, comicConfig=comicConfig)
    artistPage.exposed = True
    
    def searchit(self, name, issue=None, mode=None):
        type = 'comic'  # let's default this to comic search only for the time being (will add story arc, characters, etc later)
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

        searchresults = sorted(searchresults, key=itemgetter('comicyear','issues'), reverse=True)            
        #print ("Results: " + str(searchresults))
        return serve_template(templatename="searchresults.html", title='Search Results for: "' + name + '"', searchresults=searchresults, type=type, imported=None)
    searchit.exposed = True

    def addComic(self, comicid, comicname=None, comicyear=None, comicimage=None, comicissues=None, comicpublisher=None, imported=None):
        myDB = db.DBConnection()
        sresults = []
        cresults = []
        mismatch = "no"
        print ("comicid: " + str(comicid))
        print ("comicname: " + str(comicname))
        print ("comicyear: " + str(comicyear))
        print ("comicissues: " + str(comicissues))
        print ("comicimage: " + str(comicimage))
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
                logger.info(u"I couldn't find an exact match for " + str(comicname) + " (" + str(comicyear) + ") - gathering data for Error-Checking screen (this could take a minute)..." )
                i = 0
                loopie, cnt = parseit.ComChk(comicname, comicyear, comicpublisher, comicissues, comicid)
                print ("total count : " + str(cnt))
                while (i < cnt):
                    try:
                        stoopie = loopie['comchkchoice'][i]
                    except (IndexError, TypeError):
                        break
                    cresults.append({
                           'ComicID'   :   stoopie['ComicID'],
                           'ComicName' :   stoopie['ComicName'],
                           'ComicYear' :   stoopie['ComicYear'],
                           'ComicIssues' : stoopie['ComicIssues'],
                           'ComicURL' :    stoopie['ComicURL'],
                           'ComicPublisher' : stoopie['ComicPublisher'],
                           'GCDID' : stoopie['GCDID']
                           })
                    i+=1
                return serve_template(templatename="searchfix.html", title="Error Check", comicname=comicname, comicid=comicid, comicyear=comicyear, comicimage=comicimage, comicissues=comicissues, cresults=cresults)
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
        print ("imported is: " + str(imported))
        threading.Thread(target=importer.addComictoDB, args=[comicid,mismatch,None,imported]).start()
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % comicid)
    addComic.exposed = True

    def from_Exceptions(self, comicid, gcdid, comicname=None, comicyear=None, comicissues=None, comicpublisher=None):
        mismatch = "yes"
        #print ("gcdid:" + str(gcdid))
        #write it to the custom_exceptions.csv and reload it so that importer will pick it up and do it's thing :)
        #custom_exceptions in this format...
        #99, (comicid), (gcdid), none
        logger.info("saving new information into custom_exceptions.csv...")
        except_info = "none #" + str(comicname) + "-(" + str(comicyear) + ")"
        except_file = os.path.join(mylar.DATA_DIR,"custom_exceptions.csv")
        if not os.path.exists(except_file):
            try:
                 csvfile = open(str(except_file), 'rb')
                 csvfile.close()
            except (OSError,IOError):
                logger.error("Could not locate " + str(except_file) + " file. Make sure it's in datadir: " + mylar.DATA_DIR + " with proper permissions.")
                return

        with open(str(except_file), 'a') as f:
            f.write('%s,%s,%s,%s\n' % ("99", str(comicid), str(gcdid), str(except_info)) )
        logger.info("re-loading csv file so it's all nice and current.")
        mylar.csv_load()
       
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
        logger.info(u"Deleting all traces of Comic: " + str(ComicName))
        myDB.action('DELETE from comics WHERE ComicID=?', [ComicID])
        myDB.action('DELETE from issues WHERE ComicID=?', [ComicID])
        myDB.action('DELETE from upcoming WHERE ComicID=?', [ComicID])
        raise cherrypy.HTTPRedirect("home")
    deleteArtist.exposed = True
    
    def refreshArtist(self, ComicID):
        myDB = db.DBConnection()
        mismatch = "no"
        CV_EXcomicid = myDB.action("SELECT * from exceptions WHERE ComicID=?", [ComicID]).fetchone()
        if CV_EXcomicid is None: pass
        else:
            if CV_EXcomicid['variloop'] == '99':
                mismatch = "yes"
        if ComicID[:1] == "G": threading.Thread(target=importer.GCDimport, args=[ComicID]).start()
        else: threading.Thread(target=importer.addComictoDB, args=[ComicID,mismatch]).start()    
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    refreshArtist.exposed=True  

    def editIssue(self, ComicID):
        myDB = db.DBConnection()
        comic = myDB.action('SELECT * from comics WHERE ComicID=?', [ComicID]).fetchone()
        title = 'Now Editing ' + comic['ComicName']
        return serve_template(templatename="editcomic.html", title=title, comic=comic)
        #raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" & ComicID)   
    editIssue.exposed=True
 
    def markissues(self, action=None, **args):
        myDB = db.DBConnection()
        issuesToAdd = []
        issuestoArchive = []
        if action == 'WantedNew':
            newaction = 'Wanted'
        else:
            newaction = action
        for IssueID in args:
            if IssueID is None: continue
            else:
                mi = myDB.action("SELECT * FROM issues WHERE IssueID=?",[IssueID]).fetchone()
                miyr = myDB.action("SELECT ComicYear FROM comics WHERE ComicID=?", [mi['ComicID']]).fetchone()
                if action == 'Downloaded':
                    if mi['Status'] == "Skipped" or mi['Status'] == "Wanted":
                        logger.info(u"Cannot change status to %s as comic is not Snatched or Downloaded" % (newaction))
                        continue
                elif action == 'Archived':
                    logger.info(u"Marking %s %s as %s" % (mi['ComicName'], mi['Issue_Number'], newaction))
                    #updater.forceRescan(mi['ComicID'])
                    issuestoArchive.append(IssueID)
                elif action == 'Wanted':
                    logger.info(u"Marking %s %s as %s" % (mi['ComicName'], mi['Issue_Number'], newaction))
                    issuesToAdd.append(IssueID)

                controlValueDict = {"IssueID": IssueID}
                newValueDict = {"Status": newaction}
                myDB.upsert("issues", newValueDict, controlValueDict)
        if len(issuestoArchive) > 0:
            updater.forceRescan(mi['ComicID'])
        if len(issuesToAdd) > 0:
            logger.debug("Marking issues: %s as Wanted" % issuesToAdd)
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
    
    def queueissue(self, mode, ComicName=None, ComicID=None, ComicYear=None, ComicIssue=None, IssueID=None, new=False, redirect=None):                   
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
        elif ComicID is None and mode == 'pullwant':          
            #this is for marking individual comics from the pullist to be downloaded.
            #because ComicID and IssueID will both be None due to pullist, it's probably
            #better to set both to some generic #, and then filter out later...
            cyear = myDB.action("SELECT SHIPDATE FROM weekly").fetchone()
            ComicYear = str(cyear['SHIPDATE'])[:4]
            if ComicYear == '': ComicYear = now.year
            logger.info(u"Marking " + ComicName + " " + ComicIssue + " as wanted...")
            foundcom = search.search_init(ComicName=ComicName, IssueNumber=ComicIssue, ComicYear=ComicYear, SeriesYear=None, IssueDate=cyear['SHIPDATE'], IssueID=IssueID, AlternateSearch=None, UseFuzzy=None)
            if foundcom  == "yes":
                logger.info(u"Downloaded " + ComicName + " " + ComicIssue )  
            return
        elif mode == 'want':
            cdname = myDB.action("SELECT ComicName from comics where ComicID=?", [ComicID]).fetchone()
            ComicName = cdname['ComicName']
            logger.info(u"Marking " + ComicName + " issue: " + ComicIssue + " as wanted...")
        #---
        #this should be on it's own somewhere
        if IssueID is not None:
            controlValueDict = {"IssueID": IssueID}
            newStatus = {"Status": "Wanted"}
            myDB.upsert("issues", newStatus, controlValueDict)
        #for future reference, the year should default to current year (.datetime)
        issues = myDB.action("SELECT IssueDate FROM issues WHERE IssueID=?", [IssueID]).fetchone()
        if ComicYear == None:
            ComicYear = str(issues['IssueDate'])[:4]
        miy = myDB.action("SELECT * FROM comics WHERE ComicID=?", [ComicID]).fetchone()
        SeriesYear = miy['ComicYear']
        AlternateSearch = miy['AlternateSearch']
        UseAFuzzy = miy['UseFuzzy']
        foundcom = search.search_init(ComicName, ComicIssue, ComicYear, SeriesYear, issues['IssueDate'], IssueID, AlternateSearch, UseAFuzzy)
        if foundcom  == "yes":
            # file check to see if issue exists and update 'have' count
            if IssueID is not None:
                return updater.foundsearch(ComicID, IssueID) 
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
    
    def pullist(self):
        myDB = db.DBConnection()
        weeklyresults = []
        popit = myDB.select("SELECT * FROM sqlite_master WHERE name='weekly' and type='table'")
        if popit:
            w_results = myDB.select("SELECT PUBLISHER, ISSUE, COMIC, STATUS from weekly")
            for weekly in w_results:
                if weekly['ISSUE'].isdigit():
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
        return serve_template(templatename="weeklypull.html", title="Weekly Pull", weeklyresults=weeklyresults, pulldate=pulldate['SHIPDATE'], pullfilter=True)
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
            myissue = myDB.action("SELECT * FROM issues WHERE Issue_Number=?", [mvup['IssueNumber']]).fetchone()
            if myissue is None: pass
            else:
                #print ("ComicName: " + str(myissue['ComicName']))
                #print ("Issue number : " + str(myissue['Issue_Number']) )
 

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

    def ManualRename(self):
        print ("hello")
    ManualRename.exposed = True

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
            threading.Thread(target=importer.addComicIDListToDB, args=[comicsToAdd]).start()
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
    
    def logs(self):
        if mylar.LOG_LEVEL is None or mylar.LOG_LEVEL == '':
            mylar.LOG_LEVEL = 'info'
        return serve_template(templatename="logs.html", title="Log", lineList=mylar.LOG_LIST, log_level=mylar.LOG_LEVEL)
    logs.exposed = True

    def log_change(self, **args):
        print ("here: " + str(args))
        for loglevel in args:
            if loglevel is None: continue
            else:
                print ("changing logger to " + str(loglevel))
                LOGGER.setLevel(loglevel)
        return serve_template(templatename="logs.html", title="Log", lineList=mylar.LOG_LIST)
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

    def downloadLocal(self, IssueID):
        print ("issueid: " + str(IssueID))
        myDB = db.DBConnection()
        issueDL = myDB.action("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
        comicid = issueDL['ComicID']
        print ("comicid: " + str(comicid))
        comic = myDB.action("SELECT * FROM comics WHERE ComicID=?", [comicid]).fetchone()
        issueLOC = comic['ComicLocation']
        print ("IssueLOC: " + str(issueLOC))
        issueFILE = issueDL['Location']
        print ("IssueFILE: "+ str(issueFILE))
        issuePATH = os.path.join(issueLOC,issueFILE)
        print ("IssuePATH: " + str(issuePATH))
        dstPATH = os.path.join(mylar.CACHE_DIR, issueFILE)
        print ("dstPATH: " + str(dstPATH))
        shutil.copy2(issuePATH, dstPATH)
        print ("copied to cache...")
        #issueURL = urllib.quote_plus(issueFILE)
        #print ("issueURL:" + str(issueURL))
        filepath = urllib.quote_plus(issueFILE)
        return serve_file(filepath, "application/x-download", "attachment")

    downloadLocal.exposed = True
    
    #for testing.
    def idirectory(self):    
        return serve_template(templatename="idirectory.html", title="Import a Directory")
    idirectory.exposed = True

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
                    print ("comicname: " + soma_sl['comicname'])
                    print ("filename: " + soma_sl['comfilename'])
                    controlValue = {"impID":    soma_sl['impid']}
                    newValue = {"ComicYear":        soma_sl['comicyear'],
                                "Status":           "Not Imported",
                                "ComicName":        soma_sl['comicname'],
                                "ComicFilename":    soma_sl['comfilename'],
                                "ComicLocation":    soma_sl['comlocation'].encode('utf-8'),
                                "ImportDate":       helpers.today()}      
                    myDB.upsert("importresults", newValue, controlValue)
                    sl+=1
                # because we could be adding volumes/series that span years, we need to account for this
                # add the year to the db under the term, valid-years
                # add the issue to the db under the term, min-issue
                
                #locate metadata here.
                # unzip -z filename.cbz will show the comment field of the zip which contains the metadata.

                # unzip -z filename.cbz < /dev/null  will remove the comment field, and thus the metadata.

                    
                self.importResults()

        if redirect:
            raise cherrypy.HTTPRedirect(redirect)
        else:
            raise cherrypy.HTTPRedirect("home")
    comicScan.exposed = True

    def importResults(self):
        myDB = db.DBConnection()
        results = myDB.select("SELECT * FROM importresults group by ComicName COLLATE NOCASE")
        return serve_template(templatename="importresults.html", title="Import Results", results=results)
    importResults.exposed = True

    def preSearchit(self, ComicName, imp_rename, imp_move):
        print ("imp_rename:" + str(imp_rename))
        print ("imp_move:" + str(imp_move))
        myDB = db.DBConnection()
        results = myDB.action("SELECT * FROM importresults WHERE ComicName=?", [ComicName])
        #if results > 0:
        #    print ("There are " + str(results[7]) + " issues to import of " + str(ComicName))
        #build the valid year ranges and the minimum issue# here to pass to search.
        yearRANGE = []
        yearTOP = 0
        minISSUE = 0
        comicstoIMP = []
        for result in results:
            if result is None:
                break
            else:
                comicstoIMP.append(result['ComicLocation'].decode(mylar.SYS_ENCODING, 'replace'))
                getiss = result['impID'].rfind('-')
                getiss = result['impID'][getiss+1:]
                print("figured issue is : " + str(getiss))
                if (result['ComicYear'] not in yearRANGE) or (yearRANGE is None):
                    if result['ComicYear'] <> "0000":
                        print ("adding..." + str(result['ComicYear']))
                        yearRANGE.append(result['ComicYear'])
                        yearTOP = str(result['ComicYear'])
                if int(getiss) > (minISSUE):
                    print ("issue now set to : " + str(getiss) + " ... it was : " + str(minISSUE))
                    minISSUE = str(getiss)
        #figure out # of issues and the year range allowable
        maxyear = int(yearTOP) - (int(minISSUE) / 12)
        yearRANGE.append(str(maxyear))
        print ("there is a " + str(maxyear) + " year variation based on the 12 issues/year")
        print ("the years involved are : " + str(yearRANGE))
        print ("minimum issue level is : " + str(minISSUE))
        mode='series'
        sresults = mb.findComic(ComicName, mode, issue=minISSUE, limityear=yearRANGE)
        type='comic'
        if len(sresults) == 1:
            sr = sresults[0]
            print ("only one result...automagik-mode enabled for " + str(sr['comicid']))
            self.addComic(comicid=sr['comicid'],comicname=sr['name'],comicyear=sr['comicyear'],comicpublisher=sr['publisher'],comicimage=sr['comicimage'],comicissues=sr['issues'],imported=comicstoIMP)
            #need to move the files here.
        if len(sresults) == 0 or len(sresults) is None:
            print ("no results, removing the year from the agenda and re-querying.")
            sresults = mb.findComic(ComicName, mode, issue=minISSUE)
        return serve_template(templatename="searchresults.html", title='Search Results for: "' + ComicName + '"',searchresults=sresults, type=type, imported=comicstoIMP)
    preSearchit.exposed = True

    #---
    def config(self):
    
        interface_dir = os.path.join(mylar.PROG_DIR, 'data/interfaces/')
        interface_list = [ name for name in os.listdir(interface_dir) if os.path.isdir(os.path.join(interface_dir, name)) ]

#        branch_history, err = mylar.versioncheck.runGit("log --oneline --pretty=format:'%h - %ar - %s' -n 4")
#        br_hist = branch_history.replace("\n", "<br />\n")

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
                    "sab_host" : mylar.SAB_HOST,
                    "sab_user" : mylar.SAB_USERNAME,
                    "sab_api" : mylar.SAB_APIKEY,
                    "sab_pass" : mylar.SAB_PASSWORD,
                    "sab_cat" : mylar.SAB_CATEGORY,
                    "sab_priority" : mylar.SAB_PRIORITY,
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
                    "enable_extra_scripts" : helpers.checked(mylar.ENABLE_EXTRA_SCRIPTS),
                    "extra_scripts" : mylar.EXTRA_SCRIPTS,
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
        return serve_template(templatename="config.html", title="Settings", config=config)  
    config.exposed = True

    def error_change(self, comicid, errorgcd, comicname):
        # if comicname contains a "," it will break the exceptions import.
        import urllib
        b = urllib.unquote_plus(comicname)
        cname = b.decode("utf-8")
        cname = re.sub("\,", "", cname)

        if errorgcd[:5].isdigit():
            print ("GCD-ID detected : " + str(errorgcd)[:5])
            print ("I'm assuming you know what you're doing - going to force-match for " + cname.encode("utf-8"))
            self.from_Exceptions(comicid=comicid,gcdid=errorgcd,comicname=cname)
        else:
            print ("Assuming rewording of Comic - adjusting to : " + str(errorgcd))
            Err_Info = mylar.cv.getComic(comicid,'comic')
            self.addComic(comicid=comicid,comicname=str(errorgcd), comicyear=Err_Info['ComicYear'], comicissues=Err_Info['ComicIssues'], comicpublisher=Err_Info['ComicPublisher'])

    error_change.exposed = True

    
    def comic_config(self, com_location, ComicID, alt_search=None, fuzzy_year=None):
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

        #force the check/creation of directory com_location here
        if os.path.isdir(str(com_location)):
            logger.info(u"Validating Directory (" + str(com_location) + "). Already exists! Continuing...")
        else:
            logger.fdebug("Updated Directory doesn't exist! - attempting to create now.")
            try:
                os.makedirs(str(com_location))
                logger.info(u"Directory successfully created at: " + str(com_location))
            except OSError:
                logger.error(u"Could not create comicdir : " + str(com_location))

        myDB.upsert("comics", newValues, controlValueDict)
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    comic_config.exposed = True
    
    def configUpdate(self, http_host='0.0.0.0', http_username=None, http_port=8090, http_password=None, launch_browser=0, logverbose=0, download_scan_interval=None, nzb_search_interval=None, nzb_startup_search=0, libraryscan_interval=None,
        sab_host=None, sab_username=None, sab_apikey=None, sab_password=None, sab_category=None, sab_priority=None, log_dir=None, log_level=0, blackhole=0, blackhole_dir=None,
        usenet_retention=None, nzbsu=0, nzbsu_apikey=None, dognzb=0, dognzb_apikey=None, nzbx=0, newznab=0, newznab_host=None, newznab_apikey=None, newznab_enabled=0,
        raw=0, raw_provider=None, raw_username=None, raw_password=None, raw_groups=None, experimental=0, 
        preferred_quality=0, move_files=0, rename_files=0, add_to_csv=1, cvinfo=0, lowercase_filenames=0, folder_format=None, file_format=None, enable_extra_scripts=0, extra_scripts=None, enable_pre_scripts=0, pre_scripts=None,
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
        mylar.SAB_HOST = sab_host
        mylar.SAB_USERNAME = sab_username
        mylar.SAB_PASSWORD = sab_password      
        mylar.SAB_APIKEY = sab_apikey
        mylar.SAB_CATEGORY = sab_category
        mylar.SAB_PRIORITY = sab_priority
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
        mylar.NEWZNAB_HOST = newznab_host
        mylar.NEWZNAB_APIKEY = newznab_apikey
        mylar.NEWZNAB_ENABLED = newznab_enabled
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
        mylar.PRE_SCRIPTS = pre_scripts
        mylar.LOG_DIR = log_dir
        mylar.LOG_LEVEL = log_level
        # Handle the variable config options. Note - keys with False values aren't getting passed

        mylar.EXTRA_NEWZNABS = []

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
    
