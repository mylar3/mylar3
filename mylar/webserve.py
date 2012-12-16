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

import os
import cherrypy

from mako.template import Template
from mako.lookup import TemplateLookup
from mako import exceptions

import time
import threading

import mylar

from mylar import logger, db, importer, mb, search, filechecker, helpers, updater, parseit, weeklypull, PostProcessor
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
        else:
            # make sure comic dir exists..
            comlocation = comic['ComicLocation']
            if os.path.isdir(str(comlocation)): pass
                #logger.info(u"Directory (" + str(comlocation) + ") already exists! Continuing...")
            else:
                print ("Directory doesn't exist!")
                try:
                    os.makedirs(str(comlocation))
                    logger.info(u"No directory found - So I created one at: " + str(comlocation))
                except OSError:
                    logger.error(u"Could not create directory for comic : " + str(comlocation))

        comicConfig = {
                    "comiclocation" : mylar.COMIC_LOCATION
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
        return serve_template(templatename="searchresults.html", title='Search Results for: "' + name + '"', searchresults=searchresults, type=type)
    searchit.exposed = True

    def addComic(self, comicid, comicname=None, comicyear=None, comicissues=None):
        myDB = db.DBConnection()
        sresults = []
        mismatch = "no"
        #here we test for exception matches (ie. comics spanning more than one volume, known mismatches, etc).
        CV_EXcomicid = myDB.action("SELECT * from exceptions WHERE ComicID=?", [comicid]).fetchone()
        if CV_EXcomicid is None: pass
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
        threading.Thread(target=importer.addComictoDB, args=[comicid,mismatch]).start()
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % comicid)
    addComic.exposed = True

    def GCDaddComic(self, comicid, comicname=None, comicyear=None, comicissues=None, comiccover=None, comicpublisher=None):
        #since we already know most of the info, let's add it to the db so we can reference it later.
        myDB = db.DBConnection()
        gcomicid = "G" + str(comicid)
        comicyear_len = comicyear.find(' ', 2)
        comyear = comicyear[comicyear_len+1:comicyear_len+5]
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
        result = PostProcessor.PostProcess(nzb_name, nzb_folder)
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
            if ComicYear == '': ComicYear = "2012"
            logger.info(u"Marking " + ComicName + " " + ComicIssue + " as wanted...")
            foundcom = search.search_init(ComicName=ComicName, IssueNumber=ComicIssue, ComicYear=ComicYear, SeriesYear=None, IssueDate=cyear['SHIPDATE'], IssueID=IssueID)
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
        miyr = myDB.action("SELECT ComicYear FROM comics WHERE ComicID=?", [ComicID]).fetchone()
        SeriesYear = miyr['ComicYear']
        foundcom = search.search_init(ComicName, ComicIssue, ComicYear, SeriesYear, issues['IssueDate'], IssueID)
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
        popit = myDB.select("SELECT * FROM sqlite_master WHERE name='weekly' and type='table'")
        if popit:
            weeklyresults = myDB.select("SELECT * from weekly")        
            pulldate = myDB.action("SELECT * from weekly").fetchone()
            if pulldate is None:
                return self.manualpull()
                #raise cherrypy.HTTPRedirect("home")
        else:
            return self.manualpull()
        return serve_template(templatename="weeklypull.html", title="Weekly Pull", weeklyresults=weeklyresults, pulldate=pulldate['SHIPDATE'],pullfilter=False)
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
        upcoming = myDB.select("SELECT * from upcoming WHERE IssueDate > date('now') order by IssueDate DESC")
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
        return serve_template(templatename="logs.html", title="Log", lineList=mylar.LOG_LIST)
    logs.exposed = True
    
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
    
    def config(self):
    
        interface_dir = os.path.join(mylar.PROG_DIR, 'data/interfaces/')
        interface_list = [ name for name in os.listdir(interface_dir) if os.path.isdir(os.path.join(interface_dir, name)) ]

        config = { 
                    "http_host" : mylar.HTTP_HOST,
                    "http_user" : mylar.HTTP_USERNAME,
                    "http_port" : mylar.HTTP_PORT,
                    "http_pass" : mylar.HTTP_PASSWORD,
                    "launch_browser" : helpers.checked(mylar.LAUNCH_BROWSER),
                    "download_scan_interval" : mylar.DOWNLOAD_SCAN_INTERVAL,
                    "nzb_search_interval" : mylar.SEARCH_INTERVAL,
                    "libraryscan_interval" : mylar.LIBRARYSCAN_INTERVAL,
                    "sab_host" : mylar.SAB_HOST,
                    "sab_user" : mylar.SAB_USERNAME,
                    "sab_api" : mylar.SAB_APIKEY,
                    "sab_pass" : mylar.SAB_PASSWORD,
                    "sab_cat" : mylar.SAB_CATEGORY,
                    "sab_priority_1" : helpers.radio(mylar.SAB_PRIORITY, 1),
                    "sab_priority_2" : helpers.radio(mylar.SAB_PRIORITY, 2),
                    "sab_priority_3" : helpers.radio(mylar.SAB_PRIORITY, 3),
                    "sab_priority_4" : helpers.radio(mylar.SAB_PRIORITY, 4),
                    "sab_priority_5" : helpers.radio(mylar.SAB_PRIORITY, 5),
                    "use_blackhole" : helpers.checked(mylar.BLACKHOLE),
                    "blackhole_dir" : mylar.BLACKHOLE_DIR,
                    "usenet_retention" : mylar.USENET_RETENTION,
                    "use_nzbsu" : helpers.checked(mylar.NZBSU),
                    "nzbsu_api" : mylar.NZBSU_APIKEY,
                    "use_dognzb" : helpers.checked(mylar.DOGNZB),
                    "dognzb_api" : mylar.DOGNZB_APIKEY,
                    "use_experimental" : helpers.checked(mylar.EXPERIMENTAL),
                    "use_newznab" : helpers.checked(mylar.NEWZNAB),
                    "newznab_host" : mylar.NEWZNAB_HOST,
                    "newznab_api" : mylar.NEWZNAB_APIKEY,
                    "newznab_enabled" : helpers.checked(mylar.NEWZNAB_ENABLED),
                    "extra_newznabs" : mylar.EXTRA_NEWZNABS,
                    "destination_dir" : mylar.DESTINATION_DIR,
                    "replace_spaces" : helpers.checked(mylar.REPLACE_SPACES),
                    "replace_char" : mylar.REPLACE_CHAR,
                    "interface_list" : interface_list,
                    "autowant_all" : helpers.checked(mylar.AUTOWANT_ALL),
                    "autowant_upcoming" : helpers.checked(mylar.AUTOWANT_UPCOMING),
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
                    "log_dir" : mylar.LOG_DIR
               }
        return serve_template(templatename="config.html", title="Settings", config=config)  
    config.exposed = True
    
    def comic_config(self, com_location, ComicID):
        myDB = db.DBConnection()
        controlValueDict = {'ComicID': ComicID}
        newValues = {"ComicLocation":        com_location }
                     #"QUALalt_vers":         qual_altvers,
                     #"QUALScanner":          qual_scanner,
                     #"QUALtype":             qual_type,
                     #"QUALquality":          qual_quality
                     #}
        myDB.upsert("comics", newValues, controlValueDict)
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
    comic_config.exposed = True
    
    def configUpdate(self, http_host='0.0.0.0', http_username=None, http_port=8090, http_password=None, launch_browser=0, download_scan_interval=None, nzb_search_interval=None, libraryscan_interval=None,
        sab_host=None, sab_username=None, sab_apikey=None, sab_password=None, sab_category=None, sab_priority=0, log_dir=None, blackhole=0, blackhole_dir=None,
        usenet_retention=None, nzbsu=0, nzbsu_apikey=None, dognzb=0, dognzb_apikey=None, newznab=0, newznab_host=None, newznab_apikey=None, newznab_enabled=0,
        raw=0, raw_provider=None, raw_username=None, raw_password=None, raw_groups=None, experimental=0, 
        preferred_quality=0, move_files=0, rename_files=0, folder_format=None, file_format=None,
        destination_dir=None, replace_spaces=0, replace_char=None, autowant_all=0, autowant_upcoming=0, zero_level=0, zero_level_n=None, interface=None, **kwargs):
        mylar.HTTP_HOST = http_host
        mylar.HTTP_PORT = http_port
        mylar.HTTP_USERNAME = http_username
        mylar.HTTP_PASSWORD = http_password
        mylar.LAUNCH_BROWSER = launch_browser
        mylar.DOWNLOAD_SCAN_INTERVAL = download_scan_interval
        mylar.SEARCH_INTERVAL = nzb_search_interval
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
        mylar.FOLDER_FORMAT = folder_format
        mylar.FILE_FORMAT = file_format
        mylar.DESTINATION_DIR = destination_dir
        mylar.AUTOWANT_ALL = autowant_all
        mylar.AUTOWANT_UPCOMING = autowant_upcoming
        mylar.INTERFACE = interface
        mylar.LOG_DIR = log_dir

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
    
