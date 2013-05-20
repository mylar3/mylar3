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
import os, errno
import sys
import shlex
import datetime
import re
import urllib
import shutil
import sqlite3
import cherrypy

import mylar
from mylar import logger, helpers, db, mb, albumart, cv, parseit, filechecker, search, updater, moveit, comicbookdb

       
def is_exists(comicid):

    myDB = db.DBConnection()
    
    # See if the artist is already in the database
    comiclist = myDB.select('SELECT ComicID, ComicName from comics WHERE ComicID=?', [comicid])

    if any(comicid in x for x in comiclist):
        logger.info(comiclist[0][1] + u" is already in the database.")
        return False
    else:
        return False


def addComictoDB(comicid,mismatch=None,pullupd=None,imported=None,ogcname=None):
    # Putting this here to get around the circular import. Will try to use this to update images at later date.
#    from mylar import cache
    
    myDB = db.DBConnection()
    
    # We need the current minimal info in the database instantly
    # so we don't throw a 500 error when we redirect to the artistPage

    controlValueDict = {"ComicID":     comicid}

    dbcomic = myDB.action('SELECT * FROM comics WHERE ComicID=?', [comicid]).fetchone()
    if dbcomic is None:
        newValueDict = {"ComicName":   "Comic ID: %s" % (comicid),
                "Status":   "Loading"}
        comlocation = None
    else:
        newValueDict = {"Status":   "Loading"}
        comlocation = dbcomic['ComicLocation']
        filechecker.validateAndCreateDirectory(comlocation, True)

    myDB.upsert("comics", newValueDict, controlValueDict)

    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(comicorder=mylar.COMICSORT, imported=comicid)

    # we need to lookup the info for the requested ComicID in full now        
    comic = cv.getComic(comicid,'comic')
    #comic = myDB.action('SELECT * FROM comics WHERE ComicID=?', [comicid]).fetchone()
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
    if not mylar.CV_ONLY:
        if mismatch == "no" or mismatch is None:
            gcdinfo=parseit.GCDScraper(comic['ComicName'], comic['ComicYear'], comic['ComicIssues'], comicid) 
            #print ("gcdinfo: " + str(gcdinfo))
            mismatch_com = "no"
            if gcdinfo == "No Match":
                updater.no_searchresults(comicid)
                nomatch = "true"
                logger.info(u"There was an error when trying to add " + comic['ComicName'] + " (" + comic['ComicYear'] + ")" )
                return nomatch
            else:
                mismatch_com = "yes"
                #print ("gcdinfo:" + str(gcdinfo))

        elif mismatch == "yes":
            CV_EXcomicid = myDB.action("SELECT * from exceptions WHERE ComicID=?", [comicid]).fetchone()
            if CV_EXcomicid['variloop'] is None: pass
            else:
                vari_loop = CV_EXcomicid['variloop']
                NewComicID = CV_EXcomicid['NewComicID']
                gcomicid = CV_EXcomicid['GComicID']
                resultURL = "/series/" + str(NewComicID) + "/"
                #print ("variloop" + str(CV_EXcomicid['variloop']))
                #if vari_loop == '99':
                gcdinfo = parseit.GCDdetails(comseries=None, resultURL=resultURL, vari_loop=0, ComicID=comicid, TotalIssues=0, issvariation="no", resultPublished=None)

    logger.info(u"Sucessfully retrieved details for " + comic['ComicName'] )
    # print ("Series Published" + parseit.resultPublished)

    CV_NoYearGiven = "no"
    #if the SeriesYear returned by CV is blank or none (0000), let's use the gcd one.
    if comic['ComicYear'] is None or comic['ComicYear'] == '0000':
        if mylar.CV_ONLY:
            #we'll defer this until later when we grab all the issues and then figure it out
            logger.info("Uh-oh. I can't find a Series Year for this series. I'm going to try analyzing deeper.")
            SeriesYear = cv.getComic(comicid,'firstissue',comic['FirstIssueID'])
            if SeriesYear == '0000':
                logger.info("Ok - I couldn't find a Series Year at all. Loading in the issue data now and will figure out the Series Year.")
                CV_NoYearGiven = "yes"
                issued = cv.getComic(comicid,'issue')
                SeriesYear = issued['firstdate'][:4]
        else:
            SeriesYear = gcdinfo['SeriesYear']
    else:
        SeriesYear = comic['ComicYear']

    #let's do the Annual check here.
    if mylar.ANNUALS_ON:
        annualcomicname = re.sub('[\,\:]', '', comic['ComicName'])
        annuals = comicbookdb.cbdb(annualcomicname, SeriesYear)
        print ("Number of Annuals returned: " + str(annuals['totalissues']))
        nb = 0
        while (nb <= int(annuals['totalissues'])):
            try:
                annualval = annuals['annualslist'][nb]
            except IndexError:
                break
            newCtrl = {"IssueID": str(annualval['AnnualIssue'] + annualval['AnnualDate'])}
            newVals = {"Issue_Number":  annualval['AnnualIssue'],
                       "IssueDate":     annualval['AnnualDate'],
                       "IssueName":    annualval['AnnualTitle'],
                       "ComicID":       comicid,
                       "Status":        "Skipped"}
            myDB.upsert("annuals", newVals, newCtrl)
            nb+=1

    #parseit.annualCheck(gcomicid=gcdinfo['GCDComicID'], comicid=comicid, comicname=comic['ComicName'], comicyear=SeriesYear)
    #comic book location on machine
    # setup default location here

    if comlocation is None:
        # let's remove the non-standard characters here.
        u_comicnm = comic['ComicName']
        u_comicname = u_comicnm.encode('ascii', 'ignore').strip()
        if ':' in u_comicname or '/' in u_comicname or ',' in u_comicname or '?' in u_comicname:
            comicdir = u_comicname
            if ':' in comicdir:
                comicdir = comicdir.replace(':','')
            if '/' in comicdir:
                comicdir = comicdir.replace('/','-')
            if ',' in comicdir:
                comicdir = comicdir.replace(',','')
            if '?' in comicdir:
                comicdir = comicdir.replace('?','')
        else: comicdir = u_comicname

        series = comicdir
        publisher = comic['ComicPublisher']
        year = SeriesYear

        #do work to generate folder path

        values = {'$Series':        series,
                  '$Publisher':     publisher,
                  '$Year':          year,
                  '$series':        series.lower(),
                  '$publisher':     publisher.lower(),
                  '$Volume':        year
                  }

        #print mylar.FOLDER_FORMAT
        #print 'working dir:'
        #print helpers.replace_all(mylar.FOLDER_FORMAT, values)

        if mylar.FOLDER_FORMAT == '':
            comlocation = mylar.DESTINATION_DIR + "/" + comicdir + " (" + SeriesYear + ")"
        else:
            comlocation = mylar.DESTINATION_DIR + "/" + helpers.replace_all(mylar.FOLDER_FORMAT, values)


        #comlocation = mylar.DESTINATION_DIR + "/" + comicdir + " (" + comic['ComicYear'] + ")"
        if mylar.DESTINATION_DIR == "":
            logger.error(u"There is no general directory specified - please specify in Config/Post-Processing.")
            return
        if mylar.REPLACE_SPACES:
            #mylar.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
            comlocation = comlocation.replace(' ', mylar.REPLACE_CHAR)

    #moved this out of the above loop so it will chk for existance of comlocation in case moved
    #if it doesn't exist - create it (otherwise will bugger up later on)
    if os.path.isdir(str(comlocation)):
        logger.info(u"Directory (" + str(comlocation) + ") already exists! Continuing...")
    else:
        #print ("Directory doesn't exist!")
        #try:
        #    os.makedirs(str(comlocation))
        #    logger.info(u"Directory successfully created at: " + str(comlocation))
        #except OSError:
        #    logger.error(u"Could not create comicdir : " + str(comlocation))
        filechecker.validateAndCreateDirectory(comlocation, True)

    #try to account for CV not updating new issues as fast as GCD
    #seems CV doesn't update total counts
    #comicIssues = gcdinfo['totalissues']
    comicIssues = comic['ComicIssues']

    if not mylar.CV_ONLY:
        if gcdinfo['gcdvariation'] == "cv":
            comicIssues = str(int(comic['ComicIssues']) + 1)

    #let's download the image...
    if os.path.exists(mylar.CACHE_DIR):pass
    else:
        #let's make the dir.
        try:
            os.makedirs(str(mylar.CACHE_DIR))
            logger.info(u"Cache Directory successfully created at: " + str(mylar.CACHE_DIR))

        except OSError:
            logger.error('Could not create cache dir. Check permissions of cache dir: ' + str(mylar.CACHE_DIR))

    coverfile = os.path.join(mylar.CACHE_DIR,  str(comicid) + ".jpg")

    #try:
    urllib.urlretrieve(str(comic['ComicImage']), str(coverfile))
    try:
        with open(str(coverfile)) as f:
            ComicImage = os.path.join('cache',str(comicid) + ".jpg")

            #this is for Firefox when outside the LAN...it works, but I don't know how to implement it
            #without breaking the normal flow for inside the LAN (above)
            #ComicImage = "http://" + str(mylar.HTTP_HOST) + ":" + str(mylar.HTTP_PORT) + "/cache/" + str(comicid) + ".jpg"

            logger.info(u"Sucessfully retrieved cover for " + comic['ComicName'])
            #if the comic cover local is checked, save a cover.jpg to the series folder.
            if mylar.COMIC_COVER_LOCAL:
                comiclocal = os.path.join(str(comlocation) + "/cover.jpg")
                shutil.copy(ComicImage,comiclocal)
    except IOError as e:
        logger.error(u"Unable to save cover locally at this time.")

    if comic['ComicVersion'].isdigit():
        comicVol = "v" + comic['ComicVersion']
    else:
        comicVol = None

    #for description ...
    #Cdesc = helpers.cleanhtml(comic['ComicDescription'])
    #cdes_find = Cdesc.find("Collected")
    #cdes_removed = Cdesc[:cdes_find]
    #print cdes_removed

    controlValueDict = {"ComicID":      comicid}
    newValueDict = {"ComicName":        comic['ComicName'],
                    "ComicSortName":    sortname,
                    "ComicYear":        SeriesYear,
                    "ComicImage":       ComicImage,
                    "Total":            comicIssues,
                    "ComicVersion":     comicVol,
                    "ComicLocation":    comlocation,
                    "ComicPublisher":   comic['ComicPublisher'],
                    #"Description":      Cdesc.decode('utf-8', 'replace'),
                    "DetailURL":        comic['ComicURL'],
#                    "ComicPublished":   gcdinfo['resultPublished'],
                    "ComicPublished":   'Unknown',
                    "DateAdded":        helpers.today(),
                    "Status":           "Loading"}
    
    myDB.upsert("comics", newValueDict, controlValueDict)

    #comicsort here...
    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(sequence='update')

    if CV_NoYearGiven == 'no':
        #if set to 'no' then we haven't pulled down the issues, otherwise we did it already
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
    firstiss = "10000000"
    firstdate = "2099-00-00"
    #print ("total issues:" + str(iscnt))
    #---removed NEW code here---
    logger.info(u"Now adding/updating issues for " + comic['ComicName'])

    if not mylar.CV_ONLY:
        #fccnt = int(fc['comiccount'])
        #logger.info(u"Found " + str(fccnt) + "/" + str(iscnt) + " issues of " + comic['ComicName'] + "...verifying")
        #fcnew = []
        if iscnt > 0: #if a series is brand new, it wont have any issues/details yet so skip this part
            while (n <= iscnt):
            #---NEW.code
                try:
                    firstval = issued['issuechoice'][n]
                except IndexError:
                    break
                cleanname = helpers.cleanName(firstval['Issue_Name'])
                issid = str(firstval['Issue_ID'])
                issnum = str(firstval['Issue_Number'])
                #print ("issnum: " + str(issnum))
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
                elif 'au' in issnum.lower():
                    print ("au detected")
                    stau = issnum.lower().find('au')
                    issnum_au = issnum[:stau] 
                    print ("issnum_au: " + str(issnum_au))
                    #account for Age of Ultron mucked up numbering
                    issis = str(int(issnum_au) * 1000) + 'AU'
                else: issis = int(issnum) * 1000

                bb = 0
                while (bb <= iscnt):
                    try: 
                        gcdval = gcdinfo['gcdchoice'][bb]
                        #print ("gcdval: " + str(gcdval))
                    except IndexError:
                        #account for gcd variation here
                        if gcdinfo['gcdvariation'] == 'gcd':
                            #logger.fdebug("gcd-variation accounted for.")
                            issdate = '0000-00-00'
                            int_issnum =  int ( issis / 1000 )
                        break
                    if 'nn' in str(gcdval['GCDIssue']):
                        #no number detected - GN, TP or the like
                        logger.warn(u"Non Series detected (Graphic Novel, etc) - cannot proceed at this time.")
                        updater.no_searchresults(comicid)
                        return
                    elif 'au' in gcdval['GCDIssue'].lower():
                        #account for Age of Ultron mucked up numbering - this is in format of 5AU.00
                        gstau = gcdval['GCDIssue'].lower().find('au')
                        gcdis_au = gcdval['GCDIssue'][:gstau]
                        gcdis = str(int(gcdis_au) * 1000) + 'AU'
                    elif '.' in str(gcdval['GCDIssue']):
                        #logger.fdebug("g-issue:" + str(gcdval['GCDIssue']))
                        issst = str(gcdval['GCDIssue']).find('.')
                        #logger.fdebug("issst:" + str(issst))
                        issb4dec = str(gcdval['GCDIssue'])[:issst]
                        #logger.fdebug("issb4dec:" + str(issb4dec))
                        #if the length of decimal is only 1 digit, assume it's a tenth
                        decis = str(gcdval['GCDIssue'])[issst+1:]
                        #logger.fdebug("decis:" + str(decis))
                        if len(decis) == 1:
                            decisval = int(decis) * 10
                            issaftdec = str(decisval)
                        if len(decis) == 2:
                            decisval = int(decis)
                            issaftdec = str(decisval)
                        gcd_issue = issb4dec + "." + issaftdec
                        #logger.fdebug("gcd_issue:" + str(gcd_issue))
                        try:
                            gcdis = (int(issb4dec) * 1000) + decisval
                        except ValueError:
                            logger.error("This has no issue #'s for me to get - Either a Graphic Novel or one-shot. This feature to allow these will be added in the near future.")
                            updater.no_searchresults(comicid)
                            return
                    else:
                        gcdis = int(str(gcdval['GCDIssue'])) * 1000
                    if gcdis == issis:
                        issdate = str(gcdval['GCDDate'])
                        if str(issis).isdigit():
                            int_issnum = int( gcdis / 1000 )
                        else:
                            if 'au' in issis.lower():
                                int_issnum = str(int(gcdis[:-2]) / 1000) + 'AU'
                            else:
                                logger.error("this has an alpha-numeric in the issue # which I cannot account for. Get on github and log the issue for evilhero.")
                                return
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
                iss_exists = myDB.action('SELECT * from issues WHERE IssueID=?', [issid]).fetchone()

                # Only change the status & add DateAdded if the issue is already in the database
                if iss_exists is None:
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
                elif issdate > helpers.today() and mylar.AUTOWANT_UPCOMING:
                    newValueDict['Status'] = "Wanted"
                else:
                    newValueDict['Status'] = "Skipped"

                if iss_exists:
                    #print ("Existing status : " + str(iss_exists['Status']))
                    newValueDict['Status'] = iss_exists['Status']     
            
                try:     
                    myDB.upsert("issues", newValueDict, controlValueDict)
                except sqlite3.InterfaceError, e:
                    #raise sqlite3.InterfaceError(e)
                    logger.error("MAJOR error trying to get issue data, this is most likey a MULTI-VOLUME series and you need to use the custom_exceptions.csv file.")
                    myDB.action("DELETE FROM comics WHERE ComicID=?", [comicid])
                    return
                n+=1

#        logger.debug(u"Updating comic cache for " + comic['ComicName'])
#        cache.getThumb(ComicID=issue['issueid'])
            
#        logger.debug(u"Updating cache for: " + comic['ComicName'])
#        cache.getThumb(ComicIDcomicid)
    else:
       if iscnt > 0: #if a series is brand new, it wont have any issues/details yet so skip this part
            while (n <= iscnt):
            #---NEW.code
                try:
                    firstval = issued['issuechoice'][n]
                except IndexError:
                    break
                cleanname = helpers.cleanName(firstval['Issue_Name'])
                issid = str(firstval['Issue_ID'])
                issnum = firstval['Issue_Number']
                #print ("issnum: " + str(issnum))
                issname = cleanname
                issdate = str(firstval['Issue_Date'])
                if issnum.isdigit():
                    int_issnum = int( issnum )
                else:
                    if 'au' in issnum.lower():
                        int_issnum = str(int(issnum[:-2])) + 'AU'
                    elif u'\xbd' in issnum:
                        issnum = .5
                        int_issnum = .5
                    elif '.' in issnum or ',' in issnum:
                        if ',' in issnum: issnum = re.sub(',','.', issnum)
                        issst = str(issnum).find('.')
                        #logger.fdebug("issst:" + str(issst))
                        issb4dec = str(issnum)[:issst]
                        #logger.fdebug("issb4dec:" + str(issb4dec))
                        #if the length of decimal is only 1 digit, assume it's a tenth
                        decis = str(issnum)[issst+1:]
                        #logger.fdebug("decis:" + str(decis))
                        if len(decis) == 1:
                            decisval = int(decis) * 10
                            issaftdec = str(decisval)
                        if len(decis) == 2:
                            decisval = int(decis)
                            issaftdec = str(decisval)
                        try:
                            int_issnum = str(issnum)
                        except ValueError:
                            logger.error("This has no issue #'s for me to get - Either a Graphic Novel or one-shot.")
                            updater.no_searchresults(comicid)
                            return
                    else:
                        try:
                            x = float(issnum)
                            #validity check
                            if x < 0:
                                logger.info("I've encountered a negative issue #: " + str(issnum) + ". Trying to accomodate.")
                                int_issnum = str(issnum)
                            else: raise ValueError
                        except ValueError, e:
                            logger.error(str(issnum) + "this has an alpha-numeric in the issue # which I cannot account for.")
                            return    
                        #get the latest issue / date using the date.
                if firstval['Issue_Date'] > latestdate:
                    latestiss = issnum
                    latestdate = str(firstval['Issue_Date'])
                if firstval['Issue_Date'] < firstdate:
                    firstiss = issnum
                    firstdate = str(firstval['Issue_Date'])
                # check if the issue already exists
                iss_exists = myDB.action('SELECT * from issues WHERE IssueID=?', [issid]).fetchone()

                # Only change the status & add DateAdded if the issue is already in the database
                if iss_exists is None:
                    newValueDict['DateAdded'] = helpers.today()

                controlValueDict = {"IssueID":  issid}
                newValueDict = {"ComicID":            comicid,
                                "ComicName":          comic['ComicName'],
                                "IssueName":          issname,
                                "Issue_Number":       issnum,
                                "IssueDate":          issdate,
                                "Int_IssueNumber":    int_issnum
                                }

                if iss_exists:
                    #print ("Existing status : " + str(iss_exists['Status']))
                    newValueDict['Status'] = iss_exists['Status']
                else:
                    if mylar.AUTOWANT_ALL:
                        newValueDict['Status'] = "Wanted"
                    elif issdate > helpers.today() and mylar.AUTOWANT_UPCOMING:
                        newValueDict['Status'] = "Wanted"
                    else:
                        newValueDict['Status'] = "Skipped"

                try:
                    myDB.upsert("issues", newValueDict, controlValueDict)
                except sqlite3.InterfaceError, e:
                    #raise sqlite3.InterfaceError(e)
                    logger.error("Something went wrong - I can't add the issue information into my DB.")
                    myDB.action("DELETE FROM comics WHERE ComicID=?", [comicid])
                    return
                n+=1

    #figure publish dates here...
    styear = str(SeriesYear)
    #if SeriesYear == '0000':
    #    styear = firstdate[:4]        
    if firstdate[5:7] == '00': 
        stmonth = "?"
    else:
        stmonth = helpers.fullmonth(firstdate[5:7])
    ltyear = re.sub('/s','', latestdate[:4])
    if latestdate[5:7] == '00':
        ltmonth = "?"
    else:
        ltmonth = helpers.fullmonth(latestdate[5:7])

    #try to determine if it's an 'actively' published comic from above dates
    #threshold is if it's within a month (<45 days) let's assume it's recent.
    c_date = datetime.date(int(latestdate[:4]),int(latestdate[5:7]),1)
    n_date = datetime.date.today()
    recentchk = (n_date - c_date).days
    #print ("recentchk: " + str(recentchk))
    if recentchk <= 55:
        lastpubdate = 'Present'
    else:
        lastpubdate = str(ltmonth) + ' ' + str(ltyear)

    publishfigure = str(stmonth) + ' ' + str(styear) + ' - ' + str(lastpubdate)

    controlValueStat = {"ComicID":     comicid}
    
    newValueStat = {"Status":          "Active",
                    "LatestIssue":     latestiss,
                    "LatestDate":      latestdate,
                    "ComicPublished":  publishfigure,
                    "LastUpdated":     helpers.now()
                   }

    myDB.upsert("comics", newValueStat, controlValueStat)

    if mylar.CVINFO or (mylar.CV_ONLY and mylar.CVINFO):
        if not os.path.exists(os.path.join(comlocation,"cvinfo")) or mylar.CV_ONETIMER:
            with open(os.path.join(comlocation,"cvinfo"),"w") as text_file:
                text_file.write(str(comic['ComicURL']))
  
    logger.info(u"Updating complete for: " + comic['ComicName'])

    #move the files...if imported is not empty (meaning it's not from the mass importer.)
    if imported is None or imported == 'None':
        pass
    else:
        if mylar.IMP_MOVE:
            logger.info("Mass import - Move files")
            moveit.movefiles(comicid,comlocation,ogcname)
        else:
            logger.info("Mass import - Moving not Enabled. Setting Archived Status for import.")
            moveit.archivefiles(comicid,ogcname)

    #check for existing files...
    updater.forceRescan(comicid)

    if pullupd is None:
    # lets' check the pullist for anything at this time as well since we're here.
    # do this for only Present comics....
        if mylar.AUTOWANT_UPCOMING and lastpubdate == 'Present': #and 'Present' in gcdinfo['resultPublished']:
            print ("latestissue: #" + str(latestiss))
            chkstats = myDB.action("SELECT * FROM issues WHERE ComicID=? AND Issue_Number=?", [comicid,str(latestiss)]).fetchone()
            print chkstats['Status']
            if chkstats['Status'] == 'Skipped' or chkstats['Status'] == 'Wanted' or chkstats['Status'] == 'Snatched':
                logger.info(u"Checking this week's pullist for new issues of " + comic['ComicName'])
                updater.newpullcheck(comic['ComicName'], comicid)

        #here we grab issues that have been marked as wanted above...
  
                results = myDB.select("SELECT * FROM issues where ComicID=? AND Status='Wanted'", [comicid])
                if results:
                    logger.info(u"Attempting to grab wanted issues for : "  + comic['ComicName'])
    
                    for result in results:
                        search.searchforissue(result['IssueID'])
                else: logger.info(u"No issues marked as wanted for " + comic['ComicName'])

                logger.info(u"Finished grabbing what I could.")
            else:
                logger.info(u"Already have the latest issue : #" + str(latestiss))


def GCDimport(gcomicid, pullupd=None,imported=None,ogcname=None):
    # this is for importing via GCD only and not using CV.
    # used when volume spanning is discovered for a Comic (and can't be added using CV).
    # Issue Counts are wrong (and can't be added).

    # because Comicvine ComicID and GCD ComicID could be identical at some random point, let's distinguish.
    # CV = comicid, GCD = gcomicid :) (ie. CV=2740, GCD=G3719)
    
    gcdcomicid = gcomicid
    myDB = db.DBConnection()

    # We need the current minimal info in the database instantly
    # so we don't throw a 500 error when we redirect to the artistPage

    controlValueDict = {"ComicID":     gcdcomicid}

    comic = myDB.action('SELECT ComicName, ComicYear, Total, ComicPublished, ComicImage, ComicLocation, ComicPublisher FROM comics WHERE ComicID=?', [gcomicid]).fetchone()
    ComicName = comic[0]
    ComicYear = comic[1]
    ComicIssues = comic[2]
    ComicPublished = comic[3]
    comlocation = comic[5]
    ComicPublisher = comic[6]
    #ComicImage = comic[4]
    #print ("Comic:" + str(ComicName))

    newValueDict = {"Status":   "Loading"}
    myDB.upsert("comics", newValueDict, controlValueDict)

    # we need to lookup the info for the requested ComicID in full now
    #comic = cv.getComic(comicid,'comic')

    if not comic:
        logger.warn("Error fetching comic. ID for : " + gcdcomicid)
        if dbcomic is None:
            newValueDict = {"ComicName":   "Fetch failed, try refreshing. (%s)" % (gcdcomicid),
                    "Status":   "Active"}
        else:
            newValueDict = {"Status":   "Active"}
        myDB.upsert("comics", newValueDict, controlValueDict)
        return

    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(comicorder=mylar.COMICSORT, imported=gcomicid)

    if ComicName.startswith('The '):
        sortname = ComicName[4:]
    else:
        sortname = ComicName


    logger.info(u"Now adding/updating: " + ComicName)
    #--Now that we know ComicName, let's try some scraping
    #--Start
    # gcd will return issue details (most importantly publishing date)
    comicid = gcomicid[1:]
    resultURL = "/series/" + str(comicid) + "/"
    gcdinfo=parseit.GCDdetails(comseries=None, resultURL=resultURL, vari_loop=0, ComicID=gcdcomicid, TotalIssues=ComicIssues, issvariation=None, resultPublished=None)
    if gcdinfo == "No Match":
        logger.warn("No matching result found for " + ComicName + " (" + ComicYear + ")" )
        updater.no_searchresults(gcomicid)
        nomatch = "true"
        return nomatch
    logger.info(u"Sucessfully retrieved details for " + ComicName )
    # print ("Series Published" + parseit.resultPublished)
    #--End
    
    ComicImage = gcdinfo['ComicImage']

    #comic book location on machine
    # setup default location here
    if comlocation is None:
        # let's remove the non-standard characters here.
        u_comicnm = ComicName
        u_comicname = u_comicnm.encode('ascii', 'ignore').strip()
        if ':' in u_comicname or '/' in u_comicname or ',' in u_comicname:
            comicdir = u_comicname
            if ':' in comicdir:
                comicdir = comicdir.replace(':','')
            if '/' in comicdir:
                comicdir = comicdir.replace('/','-')
            if ',' in comicdir:
                comicdir = comicdir.replace(',','')            
        else: comicdir = u_comicname

        series = comicdir
        publisher = ComicPublisher
        year = ComicYear

        #do work to generate folder path
        values = {'$Series':        series,
                  '$Publisher':     publisher,
                  '$Year':          year,
                  '$series':        series.lower(),
                  '$publisher':     publisher.lower(),
                  '$Volume':        year
                  }

        if mylar.FOLDER_FORMAT == '':
            comlocation = mylar.DESTINATION_DIR + "/" + comicdir + " (" + comic['ComicYear'] + ")"
        else:
            comlocation = mylar.DESTINATION_DIR + "/" + helpers.replace_all(mylar.FOLDER_FORMAT, values)

        #comlocation = mylar.DESTINATION_DIR + "/" + comicdir + " (" + ComicYear + ")"
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
        #try:
        #    os.makedirs(str(comlocation))
        #    logger.info(u"Directory successfully created at: " + str(comlocation))
        #except OSError:
        #    logger.error(u"Could not create comicdir : " + str(comlocation))
        filechecker.validateAndCreateDirectory(comlocation, True)

    comicIssues = gcdinfo['totalissues']

    #let's download the image...
    if os.path.exists(mylar.CACHE_DIR):pass
    else:
        #let's make the dir.
        try:
            os.makedirs(str(mylar.CACHE_DIR))
            logger.info(u"Cache Directory successfully created at: " + str(mylar.CACHE_DIR))

        except OSError:
            logger.error(u"Could not create cache dir : " + str(mylar.CACHE_DIR))

    coverfile = os.path.join(mylar.CACHE_DIR, str(gcomicid) + ".jpg")

    #try:
    urllib.urlretrieve(str(ComicImage), str(coverfile))
    try:
        with open(str(coverfile)) as f:
            ComicImage = os.path.join('cache',str(gcomicid) + ".jpg")

            #this is for Firefox when outside the LAN...it works, but I don't know how to implement it
            #without breaking the normal flow for inside the LAN (above)
            #ComicImage = "http://" + str(mylar.HTTP_HOST) + ":" + str(mylar.HTTP_PORT) + "/cache/" + str(comi$

            logger.info(u"Sucessfully retrieved cover for " + ComicName)
            #if the comic cover local is checked, save a cover.jpg to the series folder.
            if mylar.COMIC_COVER_LOCAL:
                comiclocal = os.path.join(str(comlocation) + "/cover.jpg")
                shutil.copy(ComicImage,comiclocal)
    except IOError as e:
        logger.error(u"Unable to save cover locally at this time.")
        
    #if comic['ComicVersion'].isdigit():
    #    comicVol = "v" + comic['ComicVersion']
    #else:
    #    comicVol = None


    controlValueDict = {"ComicID":      gcomicid}
    newValueDict = {"ComicName":        ComicName,
                    "ComicSortName":    sortname,
                    "ComicYear":        ComicYear,
                    "Total":            comicIssues,
                    "ComicLocation":    comlocation,
                    #"ComicVersion":     comicVol,
                    "ComicImage":       ComicImage,
                    #"ComicPublisher":   comic['ComicPublisher'],
                    #"ComicPublished":   comicPublished,
                    "DateAdded":        helpers.today(),
                    "Status":           "Loading"}

    myDB.upsert("comics", newValueDict, controlValueDict)

    #comicsort here...
    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(sequence='update')

    logger.info(u"Sucessfully retrieved issue details for " + ComicName )
    n = 0
    iscnt = int(comicIssues)
    issnum = []
    issname = []
    issdate = []
    int_issnum = []
    #let's start issue #'s at 0 -- thanks to DC for the new 52 reboot! :)
    latestiss = "0"
    latestdate = "0000-00-00"
    #print ("total issues:" + str(iscnt))
    #---removed NEW code here---
    logger.info(u"Now adding/updating issues for " + ComicName)
    bb = 0
    while (bb <= iscnt):
        #---NEW.code
        try:
            gcdval = gcdinfo['gcdchoice'][bb]
            #print ("gcdval: " + str(gcdval))
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
            if int(issaftdec) == 0: issaftdec = "00"
            gcd_issue = issb4dec + "." + issaftdec
            gcdis = (int(issb4dec) * 1000) + decisval
        else:
            gcdis = int(str(gcdval['GCDIssue'])) * 1000
            gcd_issue = str(gcdval['GCDIssue'])
        #get the latest issue / date using the date.
        int_issnum = int( gcdis / 1000 )
        issdate = str(gcdval['GCDDate'])
        issid = "G" + str(gcdval['IssueID'])
        if gcdval['GCDDate'] > latestdate:
            latestiss = str(gcd_issue)
            latestdate = str(gcdval['GCDDate'])
        #print("(" + str(bb) + ") IssueID: " + str(issid) + " IssueNo: " + str(gcd_issue) + " Date" + str(issdate) )
        #---END.NEW.

        # check if the issue already exists
        iss_exists = myDB.action('SELECT * from issues WHERE IssueID=?', [issid]).fetchone()


        # Only change the status & add DateAdded if the issue is not already in the database
        if iss_exists is None:
            newValueDict['DateAdded'] = helpers.today()

        #adjust for inconsistencies in GCD date format - some dates have ? which borks up things.
        if "?" in str(issdate):
            issdate = "0000-00-00"             

        controlValueDict = {"IssueID":  issid}
        newValueDict = {"ComicID":            gcomicid,
                        "ComicName":          ComicName,
                        "Issue_Number":       gcd_issue,
                        "IssueDate":          issdate,
                        "Int_IssueNumber":    int_issnum
                        }

        #print ("issueid:" + str(controlValueDict))
        #print ("values:" + str(newValueDict))

        if mylar.AUTOWANT_ALL:
            newValueDict['Status'] = "Wanted"
        elif issdate > helpers.today() and mylar.AUTOWANT_UPCOMING:
            newValueDict['Status'] = "Wanted"
        else:
            newValueDict['Status'] = "Skipped"

        if iss_exists:
            #print ("Existing status : " + str(iss_exists['Status']))
            newValueDict['Status'] = iss_exists['Status']


        myDB.upsert("issues", newValueDict, controlValueDict)
        bb+=1

#        logger.debug(u"Updating comic cache for " + ComicName)
#        cache.getThumb(ComicID=issue['issueid'])

#        logger.debug(u"Updating cache for: " + ComicName)
#        cache.getThumb(ComicIDcomicid)


    controlValueStat = {"ComicID":     gcomicid}
    newValueStat = {"Status":          "Active",
                    "LatestIssue":     latestiss,
                    "LatestDate":      latestdate,
                    "LastUpdated":     helpers.now()
                   }

    myDB.upsert("comics", newValueStat, controlValueStat)

    if mylar.CVINFO:
        if not os.path.exists(comlocation + "/cvinfo"):
            with open(comlocation + "/cvinfo","w") as text_file:
                text_file.write("http://www.comicvine.com/volume/49-" + str(comicid))

    logger.info(u"Updating complete for: " + ComicName)

    #move the files...if imported is not empty (meaning it's not from the mass importer.)
    if imported is None or imported == 'None':
        pass
    else:
        if mylar.IMP_MOVE:
            logger.info("Mass import - Move files")
            moveit.movefiles(gcomicid,comlocation,ogcname)
        else:
            logger.info("Mass import - Moving not Enabled. Setting Archived Status for import.")
            moveit.archivefiles(gcomicid,ogcname)

    #check for existing files...
    updater.forceRescan(gcomicid)


    if pullupd is None:
        # lets' check the pullist for anyting at this time as well since we're here.
        if mylar.AUTOWANT_UPCOMING and 'Present' in ComicPublished:
            logger.info(u"Checking this week's pullist for new issues of " + ComicName)
            updater.newpullcheck(comic['ComicName'], gcomicid)

        #here we grab issues that have been marked as wanted above...

        results = myDB.select("SELECT * FROM issues where ComicID=? AND Status='Wanted'", [gcomicid])
        if results:
            logger.info(u"Attempting to grab wanted issues for : "  + ComicName)

            for result in results:
                foundNZB = "none"
                if (mylar.NZBSU or mylar.DOGNZB or mylar.EXPERIMENTAL or mylar.NEWZNAB or mylar.NZBX) and (mylar.SAB_HOST):
                    foundNZB = search.searchforissue(result['IssueID'])
                    if foundNZB == "yes":
                        updater.foundsearch(result['ComicID'], result['IssueID'])
        else: logger.info(u"No issues marked as wanted for " + ComicName)

        logger.info(u"Finished grabbing what I could.")

