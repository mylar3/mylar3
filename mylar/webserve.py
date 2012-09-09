#  This file is part of Headphones.
#
#  Headphones is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Headphones is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Headphones.  If not, see <http://www.gnu.org/licenses/>.

import os
import cherrypy

from mako.template import Template
from mako.lookup import TemplateLookup
from mako import exceptions

import time
import threading

import mylar

from mylar import logger, db, importer, mb, search, filechecker, helpers, updater, parseit, weeklypull
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
        return serve_template(templatename="artistredone.html", title=comic['ComicName'], comic=comic, issues=issues)
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
        #else:
            #searchresults = mb.findRelease(name)
        searchresults = sorted(searchresults, key=itemgetter('comicyear','issues'), reverse=True)            
        print ("Results: " + str(searchresults))
        return serve_template(templatename="searchresults.html", title='Search Results for: "' + name + '"', searchresults=searchresults, type=type)
    searchit.exposed = True

    def addComic(self, comicid):
        threading.Thread(target=importer.addComictoDB, args=[comicid]).start()
        raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % comicid)
    addComic.exposed = True
    
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
        logger.info(u"Deleting all traces of Comic: " + comic['ComicName'])
        myDB.action('DELETE from comics WHERE ComicID=?', [ComicID])
        myDB.action('DELETE from issues WHERE ComicID=?', [ComicID])
        raise cherrypy.HTTPRedirect("home")
    deleteArtist.exposed = True
    
    def refreshArtist(self, ComicID):
        importer.addComictoDB(ComicID)    
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
        if action == 'WantedNew':
            newaction = 'Wanted'
        else:
            newaction = action
        for IssueID in args:
            if IssueID is None: break
            print("IssueID:" + IssueID)
            mi = myDB.action("SELECT * FROM issues WHERE IssueID=?",[IssueID]).fetchone()
            miyr = myDB.action("SELECT ComicYear FROM comics WHERE ComicID=?", [mi['ComicID']]).fetchone()
            logger.info(u"Marking %s %s as %s" % (mi['ComicName'], mi['Issue_Number'], newaction))
            controlValueDict = {"IssueID": mbid}
            newValueDict = {"Status": newaction}
            myDB.upsert("issues", newValueDict, controlValueDict)
            if action == 'Skipped': pass
            elif action == 'Wanted':
                foundcoms = search.search_init(mi['ComicName'], mi['Issue_Number'], mi['IssueDate'][:4], miyr['ComicYear'])
                #searcher.searchforissue(mbid, new=False)
            elif action == 'WantedNew':
                foundcoms = search.search_init(mi['ComicName'], mi['Issue_Number'], mi['IssueDate'][:4], miyr['ComicYear'])
                #searcher.searchforissue(mbid, new=True)
            if foundcoms  == "yes":
                logger.info(u"Found " + mi['ComicName'] + " issue: " + mi['Issue_Number'] + " ! Marking as Snatched...")
                # file check to see if issue exists and update 'have' count
                if IssueID is not None:
                    ComicID = mi['ComicID']
                    print ("ComicID: " + str(ComicID))
                    comic =  myDB.action('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
                    print ("comic location: " + comic['ComicLocation'])
                    #fc = filechecker.listFiles(comic['ComicLocation'], mi['ComicName'])
                    #HaveDict = {'ComicID': ComicID}
                    #newHave = { 'Have':     fc['comiccount'] }
                    #myDB.upsert("comics", newHave, HaveDict)
                    controlValueDict = {'IssueID':  IssueID}
                    newValueDict = {'Status': 'Snatched'}
                    myDB.upsert("issues", newValueDict, controlValueDict)
                    snatchedupdate = {"IssueID":     IssueID}
                    newsnatchValues = {"ComicName":       mi['ComicName'],
                                       "ComicID":         ComicID,
                                       "Issue_Number":    mi['Issue_Number'],
                                       "DateAdded":       helpers.today(),
                                       "Status":          "Snatched"
                                       }
                    myDB.upsert("snatched", newsnatchValues, snatchedupdate)
            else:
                logger.info(u"Couldn't find " + mi['ComicName'] + " issue: " + mi['Issue_Number'] + " ! Status still wanted...")

        if ComicID:
            raise cherrypy.HTTPRedirect("artistPage?ComicID=%s" % ComicID)
        else:
            raise cherrypy.HTTPRedirect("upcoming")
    markissues.exposed = True
    
    def addArtists(self, **args):
        threading.Thread(target=importer.artistlist_to_mbids, args=[args, True]).start()
        raise cherrypy.HTTPRedirect("home")
    addArtists.exposed = True
    
    def queueissue(self, ComicName, mode, ComicID=None, ComicYear=None, ComicIssue=None, IssueID=None, new=False, redirect=None):                   
        #mode dictates type of queue - either 'want' for individual comics, or 'series' for series watchlist.
        if ComicID is None and mode == 'series':
            print (ComicName)
            issue = None
            raise cherrypy.HTTPRedirect("searchit?name=%s&issue=%s&mode=%s" % (ComicName, 'None', 'series'))
        elif ComicID is None and mode == 'pullseries':
            # we can limit the search by including the issue # and searching for
            # comics that have X many issues
            raise cherrypy.HTTPRedirect("searchit?name=%s&issue=%s&mode=%s" % (ComicName, 'None', 'pullseries'))
        #elif ComicID is None and mode == 'pullwant':          
            #this is for marking individual comics from the pullist to be downloaded.
            #because ComicID and IssueID will both be None due to pullist, it's probably
            #better to set both to some generic #, and then filter out later...
        elif mode == 'want':
            logger.info(u"Marking " + ComicName + " issue: " + ComicIssue + " as wanted...")
        #---
        #this should be on it's own somewhere
        if IssueID is not None:
            myDB = db.DBConnection()
            controlValueDict = {"IssueID": IssueID}
            newStatus = {"Status": "Wanted"}
            myDB.upsert("issues", newStatus, controlValueDict)
        print ("ComicYear:" + str(ComicYear))
        #for future reference, the year should default to current year (.datetime)
        if ComicYear == None:
            issues = myDB.action("SELECT IssueDate FROM issues WHERE IssueID=?", [IssueID]).fetchone()
            ComicYear = str(issues['IssueDate'])[:4]
        miyr = myDB.action("SELECT ComicYear FROM comics WHERE ComicID=?", [ComicID]).fetchone()
        SeriesYear = miyr['ComicYear']
        foundcom = search.search_init(ComicName, ComicIssue, ComicYear, SeriesYear)
        print ("foundcom:" + str(foundcom))
        if foundcom  == "yes":
            # file check to see if issue exists and update 'have' count
            if IssueID is not None:
                print ("ComicID:" + str(ComicID))
                print ("IssueID:" + str(IssueID))
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
            #imgstuff = parseit.PW()
            if pulldate is None:
                raise cherrypy.HTTPRedirect("home")
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
        #mvupcome = myDB.select("SELECT * from upcoming WHERE IssueDate < date('now') order by IssueDate DESC")
        #mvcontroldict = {"ComicID":    mvupcome['ComicID']}
        return serve_template(templatename="upcoming.html", title="Upcoming", upcoming=upcoming, issues=issues)
    upcoming.exposed = True
    
    def manage(self):
        return serve_template(templatename="manage.html", title="Manage")
    manage.exposed = True
    
    def manageArtists(self):
        myDB = db.DBConnection()
        comics = myDB.select('SELECT * from comics order by ComicSortName COLLATE NOCASE')
        return serve_template(templatename="manageartists.html", title="Manage Comics", comics=comics)
    manageArtists.exposed = True
    
    def manageAlbums(self):
        myDB = db.DBConnection()
        issues = myDB.select('SELECT * from issues')
        return serve_template(templatename="managealbums.html", title="Manage Issues", issues=issues)
    manageAlbums.exposed = True
    
    def manageNew(self):
        myDB = db.DBConnection()
        newcomics = myDB.select('SELECT * from newartists')
        return serve_template(templatename="managenew.html", title="Manage New Artists", newcomics=newcomics)
    manageNew.exposed = True    
    
    def markArtists(self, action=None, **args):
        myDB = db.DBConnection()
        artistsToAdd = []
        for ArtistID in args:
            if action == 'delete':
                myDB.action('DELETE from artists WHERE ArtistID=?', [ArtistID])
                myDB.action('DELETE from albums WHERE ArtistID=?', [ArtistID])
                myDB.action('DELETE from tracks WHERE ArtistID=?', [ArtistID])
                myDB.action('INSERT OR REPLACE into blacklist VALUES (?)', [ArtistID])
            elif action == 'pause':
                controlValueDict = {'ArtistID': ArtistID}
                newValueDict = {'Status': 'Paused'}
                myDB.upsert("artists", newValueDict, controlValueDict)
            elif action == 'resume':
                controlValueDict = {'ArtistID': ArtistID}
                newValueDict = {'Status': 'Active'}
                myDB.upsert("artists", newValueDict, controlValueDict)              
            else:
                artistsToAdd.append(ArtistID)
        if len(artistsToAdd) > 0:
            logger.debug("Refreshing artists: %s" % artistsToAdd)
            threading.Thread(target=importer.addArtistIDListToDB, args=[artistsToAdd]).start()
        raise cherrypy.HTTPRedirect("home")
    markArtists.exposed = True
    
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
        myDB = db.DBConnection()
        comic = myDB.action('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
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
                    "launch_browser" : mylar.LAUNCH_BROWSER,
                    "download_scan_interval" : mylar.DOWNLOAD_SCAN_INTERVAL,
                    "nzb_search_interval" : mylar.SEARCH_INTERVAL,
                    "libraryscan_interval" : mylar.LIBRARYSCAN_INTERVAL,
                    "sab_host" : mylar.SAB_HOST,
                    "sab_user" : mylar.SAB_USERNAME,
                    "sab_api" : mylar.SAB_APIKEY,
                    "sab_pass" : mylar.SAB_PASSWORD,
                    "sab_cat" : mylar.SAB_CATEGORY,
                    "use_blackhole" : helpers.checked(mylar.BLACKHOLE),
                    "blackhole_dir" : mylar.BLACKHOLE_DIR,
                    "usenet_retention" : mylar.USENET_RETENTION,
                    "use_nzbsu" : helpers.checked(mylar.NZBSU),
                    "nzbsu_api" : mylar.NZBSU_APIKEY,
                    "use_dognzb" : helpers.checked(mylar.DOGNZB),
                    "dognzb_api" : mylar.DOGNZB_APIKEY,
                    "use_experimental" : helpers.checked(mylar.EXPERIMENTAL),
                    "destination_dir" : mylar.DESTINATION_DIR,
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
                    "log_dir" : mylar.LOG_DIR
               }
        return serve_template(templatename="config.html", title="Settings", config=config)  
    config.exposed = True
    
    def comic_configUpdate(self, comic_location, qual_altvers, qual_scanner, qual_type, qual_quality):
        print ("YO")
        mylar.COMIC_LOCATION = comic_location
        mylar.QUAL_ALTVERS = qual_altvers
        mylar.QUAL_SCANNER = qual_scanner
        mylar.QUAL_TYPE = qual_type
        mylar.QUAL_QUALITY = qual_quality
        print ("ComicID:" + ComicID)
        print ("LOC:" + str(comic_location))
        print ("ALT:" + str(qual_altvers))
        myDB = db.DBConnection()
        controlValueDict = {'ComicID': ComicID}
        newValues = {"ComicLocation":        comic_location,
                     "QUALalt_vers":         qual_altvers,
                     "QUALScanner":          qual_scanner,
                     "QUALtype":             qual_type,
                     "QUALquality":          qual_quality
                     }
        myDB.upsert("comics", newValues, controlValueDict)
    comic_configUpdate.exposed = True
    
    def configUpdate(self, http_host='0.0.0.0', http_username=None, http_port=8181, http_password=None, launch_browser=0, download_scan_interval=None, nzb_search_interval=None, libraryscan_interval=None,
        sab_host=None, sab_username=None, sab_apikey=None, sab_password=None, sab_category=None, log_dir=None, blackhole=0, blackhole_dir=None,
        usenet_retention=None, nzbsu=0, nzbsu_apikey=None, dognzb=0, dognzb_apikey=None,
        raw=0, raw_provider=None, raw_username=None, raw_password=None, raw_groups=None, experimental=0, 
        preferred_quality=0, move_files=0, rename_files=0, folder_format=None, file_format=None,
        destination_dir=None, autowant_all=0, autowant_upcoming=0, interface=None):
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
        mylar.PREFERRED_QUALITY = int(preferred_quality)
        mylar.MOVE_FILES = move_files
        mylar.RENAME_FILES = rename_files
        mylar.FOLDER_FORMAT = folder_format
        mylar.FILE_FORMAT = file_format
        mylar.DESTINATION_DIR = destination_dir
        mylar.AUTOWANT_ALL = autowant_all
        mylar.AUTOWANT_UPCOMING = autowant_upcoming
        mylar.INTERFACE = interface
        mylar.LOG_DIR = log_dir
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
        message = 'Updating...'
        return serve_template(templatename="shutdown.html", title="Updating", message=message, timer=120)
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
    
