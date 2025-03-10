# -*- coding: utf-8 -*-

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
import json
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import shutil
import imghdr
import sqlite3
import cherrypy
import requests
import threading

import mylar
from mylar import logger, filers, helpers, db, mb, cv, parseit, filechecker, search, updater, moveit, comicbookdb, series_metadata


def is_exists(comicid):

    myDB = db.DBConnection()

    # See if the artist is already in the database
    comiclist = myDB.select('SELECT ComicID, ComicName from comics WHERE ComicID=?', [comicid])

    if any(comicid in x for x in comiclist):
        logger.info(comiclist[0][1] + ' is already in the database.')
        return False
    else:
        return False

def addvialist(queue):
    while True:
        if queue.qsize() >= 1:
            time.sleep(3)
            item = queue.get(True)
            if item == 'exit':
                break
            if item['comicname'] is not None:
                if item['seriesyear'] is not None:
                    logger.info('[MASS-ADD][1/%s] Now adding %s (%s) [%s] ' % (queue.qsize()+1, item['comicname'], item['seriesyear'], item['comicid']))
                    mylar.GLOBAL_MESSAGES = {'status': 'success', 'event': 'addbyid', 'comicname': item['comicname'], 'seriesyear': item['seriesyear'], 'comicid': item['comicid'], 'tables': 'None', 'message': 'Now adding %s (%s)' % (urllib.parse.unquote_plus(item['comicname']), item['seriesyear'])}
                else:
                    logger.info('[MASS-ADD][1/%s] Now adding %s [%s] ' % (queue.qsize()+1, item['comicname'], item['comicid']))
                    mylar.GLOBAL_MESSAGES = {'status': 'success', 'event': 'addbyid', 'comicname': item['comicname'], 'seriesyear': item['seriesyear'], 'comicid': item['comicid'], 'tables': 'None', 'message': 'Now adding %s' % (urllib.parse.unquote_plus(item['comicname']))}
            else:
                logger.info('[MASS-ADD][1/%s] Now adding ComicID: %s ' % (queue.qsize()+1, item['comicid']))
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'event': 'addbyid', 'comicname': item['comicname'], 'seriesyear': item['seriesyear'], 'comicid': item['comicid'], 'tables': 'None', 'message': 'Now adding via ComicID %s' % (item['comicid'])}

            addComictoDB(item['comicid'])
        else:
            mylar.ADD_LIST.put('exit')
    return False

def addComictoDB(comicid, mismatch=None, pullupd=None, imported=None, ogcname=None, calledfrom=None, annload=None, chkwant=None, issuechk=None, issuetype=None, latestissueinfo=None, csyear=None, fixed_type=None):
    myDB = db.DBConnection()

    controlValueDict = {"ComicID":     comicid}

    dbcomic = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [comicid]).fetchone()
    bypass = True
    if dbcomic is not None:
        if chkwant is not None:
            logger.fdebug('ComicID: ' + str(comicid) + ' already exists. Not adding from the future pull list at this time.')
            return 'Exists'
        if dbcomic['Status'] == 'Active':
            series_status = 'Active'
        elif dbcomic['Status'] == 'Paused':
            series_status = 'Paused'
        else:
            series_status = 'Loading'

        newValueDict = {"Status":   "Loading"}
        comlocation = dbcomic['ComicLocation']
        if comlocation is None:
            bypass = False
        else:
            lastissueid = dbcomic['LatestIssueID']
            serieslast_updated = dbcomic['LastUpdated']
            aliases = dbcomic['AlternateSearch']
            logger.info('aliases currently: %s' % aliases)
            old_description = dbcomic['DescriptionEdit']

            FirstImageSize = dbcomic['FirstImageSize']

            if not latestissueinfo:
                latestissueinfo = []
                latestissueinfo.append({"latestiss": dbcomic['LatestIssue'],
                                        "latestdate":  dbcomic['LatestDate']})

            if mylar.CONFIG.CREATE_FOLDERS is True:
                checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True)
                if not checkdirectory:
                    logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                    return {'status': 'incomplete'}
            oldcomversion = dbcomic['ComicVersion'] #store the comicversion and chk if it exists before hammering.
            db_check_values = {'comicname': dbcomic['ComicName'],
                               'comicyear': dbcomic['ComicYear'],
                               'publisher': dbcomic['ComicPublisher'],
                               'detailurl': dbcomic['DetailURL'],
                               'total_count': dbcomic['Total']}

    if dbcomic is None or bypass is False:
        newValueDict = {"ComicName":   "Comic ID: %s" % (comicid),
                "Status":   "Loading"}
        if all([imported is not None, imported != 'None', mylar.CONFIG.IMP_PATHS is True]):
            try:
                comlocation = os.path.dirname(imported['filelisting'][0]['comiclocation'])
            except Exception as e:
                comlocation = None
        else:
            comlocation = None
        oldcomversion = None
        series_status = 'Loading'
        serieslast_updated = None
        lastissueid = None
        aliases = None
        FirstImageSize = 0
        old_description = None
        db_check_values = None

    myDB.upsert("comics", newValueDict, controlValueDict)

    #run the re-sortorder here in order to properly display the page
    if all([pullupd is None, calledfrom != 'maintenance']):
        helpers.ComicSort(comicorder=mylar.COMICSORT, imported=comicid)

    # we need to lookup the info for the requested ComicID in full now
    comic = cv.getComic(comicid, 'comic', series=True)

    if not comic:
        logger.warn('Error fetching comic. ID for : ' + comicid)
        if dbcomic is None:
            newValueDict = {"ComicName":   "Fetch failed, try refreshing. (%s)" % (comicid),
                    "Status":   "Active"}
        else:
            if series_status == 'Active' or series_status == 'Loading':
                newValueDict = {"Status":   "Active"}
            else:
                newValueDict = {"Status":   "Paused"}
        myDB.upsert("comics", newValueDict, controlValueDict)
        return {'status': 'incomplete'}

    if comic['ComicName'].startswith('The '):
        sortname = comic['ComicName'][4:]
    else:
        sortname = comic['ComicName']

    if db_check_values is not None:
        if comic['ComicURL'] != db_check_values['detailurl']:
            logger.warn('[CORRUPT-COMICID-DETECTION-ENABLED] ComicID may have been removed from CV'
                        ' and replaced with an entirely different series/volume. Checking some values'
                        ' to make sure before proceeding...'
            )
            i_choose_violence = cv.check_that_biatch(comicid, db_check_values, comic)
            if i_choose_violence:
                myDB.upsert("comics", {'Status': 'Paused', 'cv_removed': 1}, {'ComicID': comicid})
                return {'status': 'incomplete'}

    comic['Corrected_Type'] = fixed_type
    if fixed_type is not None and fixed_type != comic['Type']:
        logger.info('Forced Comic Type to : %s' % comic['Corrected_Type'])

    logger.info('Now adding/updating: ' + comic['ComicName'])
    #--Now that we know ComicName, let's try some scraping
    #--Start
    # gcd will return issue details (most importantly publishing date)
    if not mylar.CONFIG.CV_ONLY:
        if mismatch == "no" or mismatch is None:
            gcdinfo=parseit.GCDScraper(comic['ComicName'], comic['ComicYear'], comic['ComicIssues'], comicid)
            #print ("gcdinfo: " + str(gcdinfo))
            mismatch_com = "no"
            if gcdinfo == "No Match":
                updater.no_searchresults(comicid)
                nomatch = "true"
                logger.info('There was an error when trying to add ' + comic['ComicName'] + ' (' + comic['ComicYear'] + ')')
                return nomatch
            else:
                mismatch_com = "yes"
                #print ("gcdinfo:" + str(gcdinfo))

        elif mismatch == "yes":
            CV_EXcomicid = myDB.selectone("SELECT * from exceptions WHERE ComicID=?", [comicid])
            if CV_EXcomicid['variloop'] is None: pass
            else:
                vari_loop = CV_EXcomicid['variloop']
                NewComicID = CV_EXcomicid['NewComicID']
                gcomicid = CV_EXcomicid['GComicID']
                resultURL = "/series/" + str(NewComicID) + "/"
                #print ("variloop" + str(CV_EXcomicid['variloop']))
                #if vari_loop == '99':
                gcdinfo = parseit.GCDdetails(comseries=None, resultURL=resultURL, vari_loop=0, ComicID=comicid, TotalIssues=0, issvariation="no", resultPublished=None)

    # print ("Series Published" + parseit.resultPublished)

    CV_NoYearGiven = "no"
    #if the SeriesYear returned by CV is blank or none (0000), let's use the gcd one.
    if any([comic['ComicYear'] is None, comic['ComicYear'] == '0000', comic['ComicYear'][-1:] == '-', comic['ComicYear'] == '2099']):
        if mylar.CONFIG.CV_ONLY:
            #we'll defer this until later when we grab all the issues and then figure it out
            logger.info('Uh-oh. I cannot find a Series Year for this series. I am going to try analyzing deeper.')
            SeriesYear = cv.getComic(comicid, 'firstissue', comic['FirstIssueID'])
            if not SeriesYear or SeriesYear == '2099':
                try:
                    if int(comic['ComicYear']) == 2099:
                        logger.fdebug('Incorrect Series year detected (%s) ...'
                                      ' Correcting to current year as this is probably a new series' % (comic['ComicYear'])
                        )
                        SeriesYear = str(datetime.datetime.now().year)
                except Exception as e:
                    return
            if SeriesYear == '0000':
                logger.info('Ok - I could not find a Series Year at all. Loading in the issue data now and will figure out the Series Year.')
                CV_NoYearGiven = "yes"
                issued = cv.getComic(comicid, 'issue')
                if not issued:
                    return
                SeriesYear = issued['firstdate'][:4]
        else:
            SeriesYear = gcdinfo['SeriesYear']
    else:
        SeriesYear = comic['ComicYear']

    if any([int(SeriesYear) > int(datetime.datetime.now().year) + 1, int(SeriesYear) == 2099]) and csyear is not None:
        logger.info('Corrected year of ' + str(SeriesYear) + ' to corrected year for series that was manually entered previously of ' + str(csyear))
        SeriesYear = csyear

    logger.info('Sucessfully retrieved details for ' + comic['ComicName'])

    #since the weekly issue check could return either annuals or issues, let's initialize it here so it carries through properly.
    weeklyissue_check = []

    if oldcomversion is not None:
        if re.sub(r'[^0-9]', '', oldcomversion).strip() == comic['incorrect_volume']:
            # if we mistakingly got the incorrect volume previously, we wipe out the existing volume so we can put the new one
            # if it was changed manually, that value will still over-ride this and won't be in this check.
            oldcomversion = None
    if any([oldcomversion is None, oldcomversion == "None"]):
        logger.info('Previous version detected as None - seeing if update required')
        if comic['ComicVersion'].isdigit():
            comicVol = 'v' + comic['ComicVersion']
            logger.info('Updated version to :' + str(comicVol))
            if all([mylar.CONFIG.SETDEFAULTVOLUME is False, comicVol == 'v1']):
                comicVol = None
        else:
            if mylar.CONFIG.SETDEFAULTVOLUME is True:
                comicVol = 'v1'
            else:
                comicVol = None
    else:
        comicVol = oldcomversion
        if all([mylar.CONFIG.SETDEFAULTVOLUME is True, comicVol is None]):
            comicVol = 'v1'

    #try to account for CV not updating new issues as fast as GCD
    #seems CV doesn't update total counts
    #comicIssues = gcdinfo['totalissues']
    comicIssues = comic['ComicIssues']

    logger.fdebug('comicIssues: %s' % comicIssues)
    logger.fdebug('seriesyear: %s / currentyear: %s' % (SeriesYear, helpers.today()[:4]))
    logger.fdebug('comicType: %s' % comic['Type'])
    if all([int(comicIssues) == 1, SeriesYear < helpers.today()[:4], comic['Type'] != 'One-Shot', comic['Type'] != 'TPB', comic['Type'] != 'HC', comic['Type'] != 'GN']):
        logger.info('Determined to be a one-shot issue. Forcing Edition to One-Shot')
        booktype = 'One-Shot'
    else:
        if comic['Type'] == 'None':
            booktype = None
        else:
            booktype = comic['Type']

    # setup default location here
    u_comicnm = comic['ComicName']
    # let's remove the non-standard characters here that will break filenaming / searching.
    comicname_filesafe = helpers.filesafe(u_comicnm)

    dir_rename = False

    if comlocation is None:

        comic_values = {'ComicName':        comic['ComicName'],
                        'ComicPublisher':   comic['ComicPublisher'],
                        'PublisherImprint': comic['PublisherImprint'],
                        'ComicYear':        SeriesYear,
                        'ComicVersion':     comicVol,
                        'Type':             booktype,
                        'Corrected_Type':   comic['Corrected_Type']}

        dothedew = filers.FileHandlers(comic=comic_values)
        comvalues = dothedew.folder_create()
        comlocation = comvalues['comlocation']
        comsubpath = comvalues['subpath']

        sck = filers.FileHandlers(comic=comic_values)
        scheck = sck.series_folder_collision_detection(comlocation, comicid, booktype, SeriesYear, comicVol)
        if scheck is not None:
            comlocation = scheck['comlocation']
    else:
        comsubpath = comlocation.replace(mylar.CONFIG.DESTINATION_DIR, '').strip()

        #check for year change and rename the folder to the corrected year...
        if comic['ComicYear'] == '2099' and SeriesYear:
            badyears = [i.start() for i in re.finditer('2099', comlocation)]
            num_bad = len(badyears)
            if num_bad == 1:
                new_location = re.sub('2099', SeriesYear, comlocation)
                dir_rename = True
            elif num_bad > 1:
                #assume right-most is the year cause anything else isn't very smart anyways...
                new_location = comlocation[:badyears[num_bad-1]] + SeriesYear + comlocation[badyears[num_bad-1]+1:]
                dir_rename = True

        if dir_rename and all([new_location != comlocation, os.path.isdir(comlocation)]):
            logger.fdebug('Attempting to rename existing location [%s]' % (comlocation))
            try:
                # make sure 2 levels up in strucure exist
                if not os.path.exists(os.path.split ( os.path.split(new_location)[0] ) [0] ):
                    logger.fdebug('making directory: %s' % os.path.split(os.path.split(new_location)[0])[0])
                    os.mkdir(os.path.split(os.path.split(new_location)[0])[0])
                # make sure parent directory exists
                if not os.path.exists(os.path.split(new_location)[0]):
                    logger.fdebug('making directory: %s' % os.path.split(new_location)[0])
                    os.mkdir(os.path.split(new_location)[0])
                logger.info('Renaming directory: %s --> %s' % (comlocation,new_location))
                shutil.move(comlocation, new_location)
            except Exception as e:
                if 'No such file or directory' in e:
                    if mylar.CONFIG.CREATE_FOLDERS:
                        checkdirectory = filechecker.validateAndCreateDirectory(new_location, True)
                        if not checkdirectory:
                            logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                else:
                    logger.warn('Unable to rename existing directory: %s' % e)

    #moved this out of the above loop so it will chk for existance of comlocation in case moved
    #if it doesn't exist - create it (otherwise will bugger up later on)
    if not dir_rename and comlocation is not None:
        if os.path.isdir(comlocation):
            logger.info('Directory (' + comlocation + ') already exists! Continuing...')
        else:
            if mylar.CONFIG.CREATE_FOLDERS is True:
                checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True)
                if not checkdirectory:
                    logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                    return {'status': 'incomplete'}
    else:
        logger.warn('Comic Location path has not been specified as required in your configuration. Aborting this process at this time.')
        return {'status': 'incomplete'}

    if not mylar.CONFIG.CV_ONLY:
        if gcdinfo['gcdvariation'] == "cv":
            comicIssues = str(int(comic['ComicIssues']) + 1)

    cimage = os.path.join(mylar.CONFIG.CACHE_DIR, str(comicid) + '.jpg')
    if mylar.CONFIG.ALTERNATE_LATEST_SERIES_COVERS is False or not os.path.isfile(cimage):
        cimage = os.path.join(mylar.CONFIG.CACHE_DIR, str(comicid) + '.jpg')
        PRComicImage = os.path.join('cache', str(comicid) + ".jpg")
        ComicImage = helpers.replacetheslash(PRComicImage)
        coversize = 0
        if os.path.isfile(cimage):
            statinfo = os.stat(cimage)
            coversize = statinfo.st_size

        if FirstImageSize != 0 and (os.path.isfile(cimage) is True and FirstImageSize == coversize):
            logger.fdebug('Cover already exists for series. Not redownloading.')
        else:
            covercheck = helpers.getImage(comicid, comic['ComicImage'])
            FirstImageSize = covercheck['coversize']
            if covercheck['status'] == 'retry':
                logger.info('Attempting to retrieve alternate comic image for the series.')
                covercheck = helpers.getImage(comicid, comic['ComicImageALT'])

        #if the comic cover local is checked, save a cover.jpg to the series folder.
        if mylar.CONFIG.COMIC_COVER_LOCAL is True:
            cloc_it = []
            if comlocation is not None and all([os.path.isdir(comlocation) is True, os.path.isfile(os.path.join(comlocation, 'cover.jpg')) is False]):
                cloc_it.append(comlocation)

            if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                if all([os.path.isdir(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comlocation))) is True, os.path.isfile(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comlocation), 'cover.jpg')) is False]):
                    cloc_it.append(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comlocation)))
                else:
                    ff = mylar.filers.FileHandlers(comic=comic)
                    cloc = ff.secondary_folders(comlocation)
                    if os.path.isfile(os.path.join(cloc, 'cover.jpg')) is False:
                        cloc_it.append(cloc)

            for clocit in cloc_it:
                try:
                    comiclocal = os.path.join(clocit, 'cover.jpg')
                    shutil.copyfile(cimage, comiclocal)
                    if mylar.CONFIG.ENFORCE_PERMS:
                        filechecker.setperms(comiclocal)
                except IOError as e:
                    if 'No such file or directory' not in str(e):
                        logger.error('[%s] Unable to save cover (%s) into series directory (%s) at this time.' % (e, cimage, comiclocal))

    else:
        ComicImage = None

    # store the cover for the series as a thumbnail as folder.jpg if option is enabled.
    if mylar.CONFIG.COVER_FOLDER_LOCAL is True:
        if comic['ComicImageThumbnail'] != 'None':
            if not os.path.exists(os.path.join(comlocation, 'folder.jpg')):
                th_check = helpers.getImage(comicid, comic['ComicImageThumbnail'], thumbnail_path=os.path.join(comlocation, 'folder.jpg'))
                if th_check['status'] == 'success':
                    logger.fdebug('Thumbnail image successfully stored as %s' % os.path.join(comlocation, 'folder.jpg'))
        else:
            logger.fdebug('Thumbnail not present on CV. Not storing locallly.')

    #dynamic-name generation here.
    as_d = filechecker.FileChecker(watchcomic=comic['ComicName'])
    as_dinfo = as_d.dynamic_replace(comic['ComicName'])
    tmpseriesname = as_dinfo['mod_seriesname']
    dynamic_seriesname = re.sub('[\|\s]','', tmpseriesname.lower()).strip()

    if comic['Issue_List'] != 'None':
        issue_list = json.dumps(comic['Issue_List'])
    else:
        issue_list = None

    if comic['Aliases'] != 'None':
        if all([aliases is not None, aliases != 'None']):
            for x in aliases.split('##'):
                aliaschk = [x for y in comic['Aliases'].split('##') if y == x]
                if aliaschk and x not in aliases.split('##'):
                    aliases += '##' + ''.join(x)
                else:
                    if x not in aliases.split('##'):
                        aliases += '##' + x
        else:
            aliases = comic['Aliases']
    else:
        aliases = aliases

    #for description ...
    #Cdesc = helpers.cleanhtml(comic['ComicDescription'])
    Cdesc = comic['ComicDescription']
    if Cdesc != 'None':
        cdes_find = Cdesc.find('Collected')
        cdes_removed = Cdesc[:cdes_find]
    else:
        cdes_removed = None

    #logger.fdebug('description: ' + cdes_removed)

    controlValueDict = {"ComicID":        comicid}
    newValueDict = {"ComicName":          comic['ComicName'],
                    "ComicSortName":      sortname,
                    "ComicName_Filesafe": comicname_filesafe,
                    "DynamicComicName":   dynamic_seriesname,
                    "ComicYear":          SeriesYear,
                    "ComicImage":         ComicImage,
                    "FirstImageSize":     FirstImageSize,
                    "ComicImageURL":      comic.get("ComicImage", ""),
                    "ComicImageALTURL":   comic.get("ComicImageALT", ""),
                    "Total":              comicIssues,
                    "ComicVersion":       comicVol,
                    "ComicLocation":      comlocation,
                    "ComicPublisher":     comic['ComicPublisher'],
                    "Description":        cdes_removed,
                    "DescriptionEdit":    old_description,
                    "PublisherImprint":   comic['PublisherImprint'],
                    "DetailURL":          comic['ComicURL'],
                    "AlternateSearch":    aliases,
#                    "ComicPublished":    gcdinfo['resultPublished'],
                    "ComicPublished":     None, #"Unknown",
                    "Type":               booktype,
                    "Corrected_Type":     comic['Corrected_Type'],
                    "Collects":           issue_list,
                    "DateAdded":          helpers.today(),
                    "Status":             "Loading"}

    myDB.upsert("comics", newValueDict, controlValueDict)

    mylar.GLOBAL_MESSAGES = {'status': 'mid-message-event', 'event': 'addbyid', 'comicname': comic['ComicName'], 'seriesyear': SeriesYear, 'comicid': comicid, 'tables': 'None', 'message': 'mid-message-event'}

    #comicsort here...
    #run the re-sortorder here in order to properly display the page
    if all([pullupd is None, calledfrom != 'maintenance']):
        helpers.ComicSort(sequence='update')

    if CV_NoYearGiven == 'no':
        #if set to 'no' then we haven't pulled down the issues, otherwise we did it already
        issued = cv.getComic(comicid, 'issue')
        if issued is None:
            logger.warn('Unable to retrieve data from ComicVine. Get your own API key already!')
            return {'status': 'incomplete'}
    logger.info('Sucessfully retrieved issue details for ' + comic['ComicName'])

    #move to own function so can call independently to only refresh issue data
    #issued is from cv.getComic, comic['ComicName'] & comicid would both be already known to do independent call.
    updateddata = updateissuedata(comicid, comic['ComicName'], issued, comicIssues, calledfrom, SeriesYear=SeriesYear, latestissueinfo=latestissueinfo, serieslast_updated=serieslast_updated, series_status=series_status)
    try:
        if updateddata['status'] == 'failure':
            logger.warn('Unable to properly retrieve issue details - this is usually due to either irregular issue numbering, or problems with CV')
            return {'status': 'incomplete'}
    except Exception:
        pass

    issuedata = updateddata['issuedata']
    anndata = updateddata['annualchk']
    nostatus = updateddata['nostatus']
    json_updated = updateddata['json_updated']
    importantdates = updateddata['importantdates']
    if issuedata is None:
        logger.warn('Unable to complete Refreshing / Adding issue data - this WILL create future problems if not addressed.')
        return {'status': 'incomplete'}

    if any([calledfrom is None, calledfrom == 'maintenance']):
        issue_collection(issuedata, nostatus='False', serieslast_updated=serieslast_updated)
        #need to update annuals at this point too....
        if anndata:
            manualAnnual(annchk=anndata,series_status=series_status)

    if mylar.CONFIG.ALTERNATE_LATEST_SERIES_COVERS is True: #, lastissueid != importantdates['LatestIssueID']]):
        cimage = os.path.join(mylar.CONFIG.CACHE_DIR, comicid + '.jpg')
        coversize = 0
        if os.path.isfile(cimage):
            statinfo = os.stat(cimage)
            coversize = statinfo.st_size

        if os.path.isfile(cimage) and all([FirstImageSize != 0, FirstImageSize == coversize]):
            logger.fdebug('Cover already exists for series. Not redownloading.')
        else:
            image_it(comicid, importantdates['LatestIssueID'], comlocation, comic['ComicImage'])
    else:
        logger.fdebug('no update required - lastissueid [%s] = latestissueid [%s]' % (lastissueid, importantdates['LatestIssueID']))

    if (mylar.CONFIG.CVINFO or (mylar.CONFIG.CV_ONLY and mylar.CONFIG.CVINFO)) and os.path.isdir(comlocation):
        if os.path.isfile(os.path.join(comlocation, "cvinfo")) is False:
            with open(os.path.join(comlocation, "cvinfo"), "w") as text_file:
                text_file.write(str(comic['ComicURL']))


    if calledfrom == 'weekly':
        logger.info('Successfully refreshed ' + comic['ComicName'] + ' (' + str(SeriesYear) + '). Returning to Weekly issue comparison.')
        logger.info('Update issuedata for ' + str(issuechk) + ' of : ' + str(weeklyissue_check))
        return {'status': 'complete',
                'issuedata': issuedata} # this should be the weeklyissue_check data from updateissuedata function

    elif calledfrom == 'dbupdate':
        logger.info('returning to dbupdate module')
        return {'status': 'complete',
                'issuedata': issuedata,
                'anndata': anndata } # this should be the issuedata data from updateissuedata function

    elif calledfrom == 'weeklycheck':
        logger.info('Successfully refreshed ' + comic['ComicName'] + ' (' + str(SeriesYear) + '). Returning to Weekly issue update.')
        return  #no need to return any data here.


    logger.info('Updating complete for: ' + comic['ComicName'])

    #if it made it here, then the issuedata contains dates, let's pull the data now.
    latestiss = importantdates['LatestIssue']
    latestdate = importantdates['LatestDate']
    lastpubdate = importantdates['LastPubDate']
    series_status = importantdates['SeriesStatus']
    #move the files...if imported is not empty & not futurecheck (meaning it's not from the mass importer.)
    #logger.info('imported is : ' + str(imported))
    if imported is None or imported == 'None' or imported == 'futurecheck':
        pass
    else:
        if mylar.CONFIG.IMP_MOVE:
            logger.info('Mass import - Move files')
            moveit.movefiles(comicid, comlocation, imported)
        else:
            logger.info('Mass import - Moving not Enabled. Setting Archived Status for import.')
            moveit.archivefiles(comicid, comlocation, imported)

    #check for existing files...
    statbefore = myDB.selectone("SELECT Status FROM issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issuedigits(latestiss)]).fetchone()
    logger.fdebug('issue: ' + latestiss + ' status before chk :' + str(statbefore['Status']))
    updater.forceRescan(comicid)

    #series.json updater here (after all data written out)
    if not json_updated and mylar.CONFIG.SERIES_METADATA_LOCAL is True:
        sm = series_metadata.metadata_Series(comicid, bulk=False, api=False)
        sm.update_metadata()

    statafter = myDB.selectone("SELECT Status FROM issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issuedigits(latestiss)]).fetchone()
    logger.fdebug('issue: ' + latestiss + ' status after chk :' + str(statafter['Status']))

    logger.fdebug('pullupd: ' + str(pullupd))
    logger.fdebug('lastpubdate: ' + str(lastpubdate))
    logger.fdebug('series_status: ' + str(series_status))
    if pullupd is None:
    # lets' check the pullist for anything at this time as well since we're here.
    # do this for only Present comics....
        if mylar.CONFIG.AUTOWANT_UPCOMING and lastpubdate == 'Present' and series_status == 'Active': #and 'Present' in gcdinfo['resultPublished']:
            logger.fdebug('latestissue: #' + str(latestiss))
            chkstats = myDB.selectone("SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issuedigits(latestiss)]).fetchone()
            if chkstats is None:
                if mylar.CONFIG.ANNUALS_ON:
                    chkstats = myDB.selectone("SELECT * FROM annuals WHERE ComicID=? AND Int_IssueNumber=? AND NOT Deleted", [comicid, helpers.issuedigits(latestiss)]).fetchone()

            if chkstats:
                logger.fdebug('latestissue status: ' + chkstats['Status'])
                if chkstats['Status'] == 'Skipped' or chkstats['Status'] == 'Wanted' or chkstats['Status'] == 'Snatched':
                    logger.info('Checking this week pullist for new issues of ' + comic['ComicName'])
                    if comic['ComicName'] != comicname_filesafe:
                        cn_pull = comicname_filesafe
                    else:
                        cn_pull = comic['ComicName']
                    updater.newpullcheck(ComicName=cn_pull, ComicID=comicid, issue=latestiss)

            #here we grab issues that have been marked as wanted above...
                if calledfrom != 'maintenance':
                    results = []
                    issresults = myDB.select("SELECT * FROM issues where ComicID=? AND Status='Wanted'", [comicid])
                    if issresults:
                        for issr in issresults:
                            results.append({'IssueID':       issr['IssueID'],
                                            'Issue_Number':  issr['Issue_Number'],
                                            'Status':        issr['Status']
                                           })
                    if mylar.CONFIG.ANNUALS_ON:
                        an_results = myDB.select("SELECT * FROM annuals WHERE ComicID=? AND Status='Wanted' AND NOT Deleted", [comicid])
                        if an_results:
                            for ar in an_results:
                                results.append({'IssueID':       ar['IssueID'],
                                                'Issue_Number':  ar['Issue_Number'],
                                                'Status':        ar['Status']
                                               })


                    if results:
                        logger.info('Attempting to grab wanted issues for : '  + comic['ComicName'])
                        search_list = []
                        for result in results:
                            logger.fdebug('Searching for : ' + str(result['Issue_Number']))
                            logger.fdebug('Status of : ' + str(result['Status']))
                            search_list.append(result['IssueID'])
                        if len(search_list) > 0:
                            threading.Thread(target=search.searchIssueIDList, args=[search_list]).start()
                    else: logger.info('No issues marked as wanted for ' + comic['ComicName'])

                    logger.info('Finished grabbing what I could.')
                else:
                    logger.info('Already have the latest issue : #' + str(latestiss))

    if chkwant is not None:
        #if this isn't None, this is being called from the futureupcoming list
        #a new series was added automagically, but it has more than 1 issue (probably because it was a back-dated issue)
        #the chkwant is a tuple containing all the data for the given series' issues that were marked as Wanted for futureupcoming dates.
        chkresults = myDB.select("SELECT * FROM issues WHERE ComicID=? AND Status='Skipped'", [comicid])
        if chkresults:
            logger.info('[FROM THE FUTURE CHECKLIST] Attempting to grab wanted issues for : ' + comic['ComicName'])
            for result in chkresults:
                for chkit in chkwant:
                    logger.fdebug('checking ' + chkit['IssueNumber'] + ' against ' + result['Issue_Number'])
                    if chkit['IssueNumber'] == result['Issue_Number']:
                        logger.fdebug('Searching for : ' + result['Issue_Number'])
                        logger.fdebug('Status of : ' + str(result['Status']))
                        search.searchforissue(result['IssueID'])
        else: logger.info('No issues marked as wanted for ' + comic['ComicName'])

        logger.info('Finished grabbing what I could.')

    if imported == 'futurecheck':
        logger.info('Returning to Future-Check module to complete the add & remove entry.')
        return
    elif all([imported is not None, imported != 'None']):
        logger.info('Successfully imported : ' + comic['ComicName'])
        return

    if calledfrom == 'addbyid':
        mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': comic['ComicName'], 'seriesyear': SeriesYear, 'comicid': comicid, 'tables': 'both', 'message': 'Successfully added %s (%s)!' % (comic['ComicName'], SeriesYear)}
        logger.info('Sucessfully added %s (%s) to the watchlist by directly using the ComicVine ID' % (comic['ComicName'], SeriesYear))
        return {'status': 'complete'}
    elif calledfrom == 'maintenance':
        logger.info('Sucessfully added %s (%s) to the watchlist' % (comic['ComicName'], SeriesYear))
        return {'status':    'complete',
                'comicname': comic['ComicName'],
                'year':      SeriesYear}
    else:
        mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': comic['ComicName'], 'seriesyear': SeriesYear, 'comicid': comicid, 'tables': 'both', 'message': 'Successfully added %s (%s)!' % (comic['ComicName'], SeriesYear)}
        logger.info('Sucessfully added %s (%s) to the watchlist' % (comic['ComicName'], SeriesYear))
        return {'status': 'complete'}

#        if imported['Volume'] is None or imported['Volume'] == 'None':
#            results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume IS NULL",[imported['DynamicName']])
#        else:
#            if not imported['Volume'].lower().startswith('v'):
#                volume = 'v' + str(imported['Volume'])
#            results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume=?",[imported['DynamicName'],imported['Volume']])
#
#        if results is not None:
#            for result in results:
#                controlValue = {"DynamicName":  imported['DynamicName'],
#                                "Volume":       imported['Volume']}
#                newValue = {"Status":           "Imported",
#                            "SRID":             result['SRID'],
#                            "ComicID":          comicid}
#                myDB.upsert("importresults", newValue, controlValue)


def GCDimport(gcomicid, pullupd=None, imported=None, ogcname=None):
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

    comic = myDB.selectone('SELECT ComicName, ComicYear, Total, ComicPublished, ComicImage, ComicLocation, ComicPublisher FROM comics WHERE ComicID=?', [gcomicid]).fetchone()
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
        logger.warn('Error fetching comic. ID for : ' + gcdcomicid)
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


    logger.info("Now adding/updating: " + ComicName)
    #--Now that we know ComicName, let's try some scraping
    #--Start
    # gcd will return issue details (most importantly publishing date)
    comicid = gcomicid[1:]
    resultURL = "/series/" + str(comicid) + "/"
    gcdinfo=parseit.GCDdetails(comseries=None, resultURL=resultURL, vari_loop=0, ComicID=gcdcomicid, TotalIssues=ComicIssues, issvariation=None, resultPublished=None)
    if gcdinfo == "No Match":
        logger.warn("No matching result found for " + ComicName + " (" + ComicYear + ")")
        updater.no_searchresults(gcomicid)
        nomatch = "true"
        return nomatch
    logger.info("Sucessfully retrieved details for " + ComicName)
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
                comicdir = comicdir.replace(':', '')
            if '/' in comicdir:
                comicdir = comicdir.replace('/', '-')
            if ',' in comicdir:
                comicdir = comicdir.replace(',', '')
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

        if mylar.CONFIG.FOLDER_FORMAT == '':
            comlocation = mylar.CONFIG.DESTINATION_DIR + "/" + comicdir + " (" + comic['ComicYear'] + ")"
        else:
            comlocation = mylar.CONFIG.DESTINATION_DIR + "/" + helpers.replace_all(mylar.CONFIG.FOLDER_FORMAT, values)

        #comlocation = mylar.CONFIG.DESTINATION_DIR + "/" + comicdir + " (" + ComicYear + ")"
        if mylar.CONFIG.DESTINATION_DIR == "":
            logger.error("There is no general directory specified - please specify in Config/Post-Processing.")
            return
        if mylar.CONFIG.REPLACE_SPACES:
            #mylar.CONFIG.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
            comlocation = comlocation.replace(' ', mylar.CONFIG.REPLACE_CHAR)

    #if it doesn't exist - create it (otherwise will bugger up later on)
    if os.path.isdir(comlocation):
        logger.info("Directory (" + comlocation + ") already exists! Continuing...")
    else:
        if mylar.CONFIG.CREATE_FOLDERS is True:
            checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True)
            if not checkdirectory:
                logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                return

    comicIssues = gcdinfo['totalissues']

    #let's download the image...
    if os.path.exists(mylar.CONFIG.CACHE_DIR): pass
    else:
        #let's make the dir.
        try:
            os.makedirs(str(mylar.CONFIG.CACHE_DIR))
            logger.info("Cache Directory successfully created at: " + str(mylar.CONFIG.CACHE_DIR))

        except OSError:
            logger.error("Could not create cache dir : " + str(mylar.CONFIG.CACHE_DIR))

    coverfile = os.path.join(mylar.CONFIG.CACHE_DIR, str(gcomicid) + ".jpg")

    #new CV API restriction - one api request / second.
    if mylar.CONFIG.CVAPI_RATE is None or mylar.CONFIG.CVAPI_RATE < 2:
        time.sleep(2)
    else:
        time.sleep(mylar.CONFIG.CVAPI_RATE)

    urllib.request.urlretrieve(str(ComicImage), str(coverfile))
    try:
        with open(str(coverfile)) as f:
            ComicImage = os.path.join('cache', str(gcomicid) + ".jpg")

            #this is for Firefox when outside the LAN...it works, but I don't know how to implement it
            #without breaking the normal flow for inside the LAN (above)
            #ComicImage = "http://" + str(mylar.CONFIG.HTTP_HOST) + ":" + str(mylar.CONFIG.HTTP_PORT) + "/cache/" + str(comi$

            logger.info("Sucessfully retrieved cover for " + ComicName)
            #if the comic cover local is checked, save a cover.jpg to the series folder.
            if mylar.CONFIG.COMIC_COVER_LOCAL and os.path.isdir(comlocation):
                comiclocal = os.path.join(comlocation, 'cover.jpg')
                shutil.copy(ComicImage, comiclocal)
    except IOError as e:
        logger.error("Unable to save cover locally at this time.")

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
                    "ComicImageURL":    comic.get('ComicImage', ''),
                    "ComicImageALTURL": comic.get('ComicImageALT', ''),
                    #"ComicPublisher":   comic['ComicPublisher'],
                    #"ComicPublished":   comicPublished,
                    "DateAdded":        helpers.today(),
                    "Status":           "Loading"}

    myDB.upsert("comics", newValueDict, controlValueDict)

    #comicsort here...
    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(sequence='update')

    logger.info("Sucessfully retrieved issue details for " + ComicName)
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
    logger.info("Now adding/updating issues for " + ComicName)
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
                int_issnum =  int (issis / 1000)
            break
        if 'nn' in str(gcdval['GCDIssue']):
            #no number detected - GN, TP or the like
            logger.warn("Non Series detected (Graphic Novel, etc) - cannot proceed at this time.")
            updater.no_searchresults(comicid)
            return
        elif '.' in str(gcdval['GCDIssue']):
            issst = str(gcdval['GCDIssue']).find('.')
            issb4dec = str(gcdval['GCDIssue'])[:issst]
            #if the length of decimal is only 1 digit, assume it's a tenth
            decis = str(gcdval['GCDIssue'])[issst +1:]
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
        int_issnum = int(gcdis / 1000)
        issdate = str(gcdval['GCDDate'])
        issid = "G" + str(gcdval['IssueID'])
        if gcdval['GCDDate'] > latestdate:
            latestiss = str(gcd_issue)
            latestdate = str(gcdval['GCDDate'])
        #print("(" + str(bb) + ") IssueID: " + str(issid) + " IssueNo: " + str(gcd_issue) + " Date" + str(issdate) )
        #---END.NEW.

        # check if the issue already exists
        iss_exists = myDB.selectone('SELECT * from issues WHERE IssueID=?', [issid]).fetchone()


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

        if mylar.CONFIG.AUTOWANT_ALL:
            newValueDict['Status'] = "Wanted"
        elif issdate > helpers.today() and mylar.CONFIG.AUTOWANT_UPCOMING:
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

    if mylar.CONFIG.CVINFO and os.path.isdir(comlocation):
        if not os.path.exists(comlocation + "/cvinfo"):
            with open(comlocation + "/cvinfo", "w") as text_file:
                text_file.write("http://comicvine.gamespot.com/volume/49-" + str(comicid))

    logger.info("Updating complete for: " + ComicName)

    #move the files...if imported is not empty (meaning it's not from the mass importer.)
    if imported is None or imported == 'None':
        pass
    else:
        if mylar.CONFIG.IMP_MOVE:
            logger.info("Mass import - Move files")
            moveit.movefiles(gcomicid, comlocation, ogcname)
        else:
            logger.info("Mass import - Moving not Enabled. Setting Archived Status for import.")
            moveit.archivefiles(gcomicid, ogcname)

    #check for existing files...
    updater.forceRescan(gcomicid)


    if pullupd is None:
        # lets' check the pullist for anyting at this time as well since we're here.
        if mylar.CONFIG.AUTOWANT_UPCOMING and 'Present' in ComicPublished:
            logger.info("Checking this week's pullist for new issues of " + ComicName)
            updater.newpullcheck(comic['ComicName'], gcomicid)

        #here we grab issues that have been marked as wanted above...

        results = myDB.select("SELECT * FROM issues where ComicID=? AND Status='Wanted'", [gcomicid])
        if results:
            logger.info("Attempting to grab wanted issues for : "  + ComicName)

            for result in results:
                foundNZB = "none"
                if (mylar.CONFIG.NZBSU or mylar.CONFIG.DOGNZB or mylar.CONFIG.EXPERIMENTAL or mylar.CONFIG.NEWZNAB) and (mylar.CONFIG.SAB_HOST):
                    foundNZB = search.searchforissue(result['IssueID'])
                    if foundNZB == "yes":
                        updater.foundsearch(result['ComicID'], result['IssueID'])
        else: logger.info("No issues marked as wanted for " + ComicName)

        logger.info("Finished grabbing what I could.")


def issue_collection(issuedata, nostatus, serieslast_updated=None):
    #make sure serieslast_updated is in the correct format
    try:
        serieslast_updated = datetime.datetime.strptime(serieslast_updated, "%Y-%m-%d %H:%M:%S").strftime('%Y-%m-%d')
    except Exception:
        pass

    logger.info('nostatus: %s' % nostatus)
    logger.info('issuedata: %s' % (issuedata))

    myDB = db.DBConnection()
    nowdate = datetime.datetime.now()
    now_week = datetime.datetime.strftime(nowdate, "%Y%U")

    if issuedata:
        isslastdate = myDB.selectone('SELECT IssueDate, ReleaseDate from issues where ComicID=? ORDER BY IssueDate DESC LIMIT 1', [issuedata[0]['ComicID']]).fetchone()
        if not isslastdate:
            lastchkdate = '0000-00-00'  # set it to make sure every new issue gets autowanted if enabled.
        else:
            lastchkdate = isslastdate['IssueDate']
            if any([lastchkdate is None, lastchkdate == '0000-00-00']):
                lastchkdate = isslastdate['ReleaseDate']

        for issue in issuedata:


            controlValueDict = {"IssueID":  issue['IssueID']}
            newValueDict = {"ComicID":            issue['ComicID'],
                            "ComicName":          issue['ComicName'],
                            "IssueName":          issue['IssueName'],
                            "Issue_Number":       issue['Issue_Number'],
                            "IssueDate":          issue['IssueDate'],
                            "ReleaseDate":        issue['ReleaseDate'],
                            "DigitalDate":        issue['DigitalDate'],
                            "Int_IssueNumber":    issue['Int_IssueNumber'],
                            "AltIssueNumber":     issue['AltIssueNumber'],
                            "ImageURL":           issue['ImageURL'],
                            "ImageURL_ALT":       issue['ImageURL_ALT']
                            #"Status":             "Skipped"  #set this to Skipped by default to avoid NULL entries.
                            }

            # check if the issue already exists
            iss_exists = myDB.selectone('SELECT * from issues WHERE IssueID=?', [issue['IssueID']]).fetchone()
            dbwrite = "issues"

            #if iss_exists is None:
            #    iss_exists = myDB.selectone('SELECT * from annuals WHERE IssueID=?', [issue['IssueID']]).fetchone()
            #    if iss_exists:
            #        dbwrite = "annuals"

            if nostatus == 'False':
                #logger.info('checking issue #%s' % issue['Issue_Number'])
                # Only change the status & add DateAdded if the issue is already in the database
                if iss_exists is None:
                    newValueDict['DateAdded'] = helpers.today()
                    if issue['ReleaseDate'] == '0000-00-00':
                        dk = re.sub('-', '', issue['IssueDate']).strip()
                    else:
                        dk = re.sub('-', '', issue['ReleaseDate']).strip() # converts date to 20140718 format
                    if dk == '00000000':
                        logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % issue['Issue_Number'])
                        newValueDict['Status'] = "Skipped"
                    else:
                        datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                        issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                        #logger.info('issue_week: %s' % issue_week)
                        if issue['SeriesStatus'] == 'Paused':
                            newValueDict['Status'] = "Skipped"
                            logger.fdebug('[PAUSE-CHECK-ISSUE-STATUS] Series is paused, setting status for new issue #%s to Skipped' % (issue['Issue_Number']))
                        else:
                            if mylar.CONFIG.AUTOWANT_ALL:
                                newValueDict['Status'] = "Wanted"
                            elif serieslast_updated is None:
                                #logger.fdebug('serieslast_update is None. Setting to Skipped')
                                newValueDict['Status'] = "Skipped"
                            elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING:
                                logger.fdebug('[Marking as Wanted] week %s >= week %s' % (now_week, issue_week))
                                newValueDict['Status'] = "Wanted"
                            elif all([int(re.sub('-', '', serieslast_updated).strip()) < int(dk), mylar.CONFIG.AUTOWANT_UPCOMING is True]):
                                logger.info('Autowant upcoming triggered for issue #%s' % issue['Issue_Number'])
                                newValueDict['Status'] = "Wanted"
                            else:
                                newValueDict['Status'] = "Skipped"
                        #logger.fdebug('status is : %s' % (newValueDict,))
                else:
                    #logger.fdebug('Existing status for issue #%s : %s' % (issue['Issue_Number'], iss_exists['Status']))
                    if any([iss_exists['Status'] is None, iss_exists['Status'] == 'None']):
                        is_status = 'Skipped'
                    else:
                        is_status = iss_exists['Status']
                    newValueDict['Status'] = is_status

            else:
                #logger.fdebug("Not changing the status at this time - reverting to previous module after to re-append existing status")
                pass #newValueDict['Status'] = "Skipped"

            #logger.fdebug('issue_collection results: [%s] %s' % (controlValueDict, newValueDict))
            try:
                myDB.upsert(dbwrite, newValueDict, controlValueDict)
            except sqlite3.InterfaceError as e:
                #raise sqlite3.InterfaceError(e)
                logger.error('Something went wrong - I cannot add the issue information into my DB.')
                myDB.action("DELETE FROM comics WHERE ComicID=?", [issue['ComicID']])
                return


def manualAnnual(manual_comicid=None, comicname=None, comicyear=None, comicid=None, annchk=None, manualupd=False, deleted=False, forceadd=False, serieslast_updated=None, series_status=None):
        #called when importing/refreshing an annual that was manually added.

    #make sure serieslast_updated is in the correct format
    try:
        serieslast_updated = datetime.datetime.strptime(serieslast_updated, "%Y-%m-%d %H:%M:%S").strftime('%Y-%m-%d')
    except Exception:
        pass

    myDB = db.DBConnection()

    if annchk is None:
        nowdate = datetime.datetime.now()
        now_week = datetime.datetime.strftime(nowdate, "%Y%U")
        annchk = []
        issueid = manual_comicid
        logger.fdebug(str(issueid) + ' added to series list as an Annual')
        sr = cv.getComic(manual_comicid, 'comic')
        if sr is None and forceadd is False:
            return
        logger.fdebug('Attempting to integrate ' + sr['ComicName'] + ' (' + str(issueid) + ') to the existing series of ' + comicname + '(' + str(comicyear) + ')')
        if len(sr) == 0:
            logger.fdebug('Could not find any information on the series indicated : ' + str(manual_comicid))
            return
        else:
            n = 0
            issued = cv.getComic(re.sub('4050-', '', manual_comicid).strip(), 'issue')
            if not issued:
                return
            if int(sr['ComicIssues']) == 0 and len(issued['issuechoice']) == 1:
                noissues = 1
            else:
                noissues = sr['ComicIssues']
            logger.fdebug('there are ' + str(noissues) + ' annuals within this series.')
            while (n < int(noissues)):
                try:
                    firstval = issued['issuechoice'][n]
                except IndexError:
                    break
                try:
                    cleanname = firstval['Issue_Name'] #helpers.cleanName(firstval['Issue_Name'])
                except:
                    cleanname = 'None'

                if firstval['Store_Date'] == '0000-00-00':
                    dk = re.sub('-', '', firstval['Issue_Date']).strip()
                else:
                    dk = re.sub('-', '', firstval['Store_Date']).strip() # converts date to 20140718 format
                if dk == '00000000':
                    logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % firstval['Issue_Number'])
                    astatus = "Skipped"
                else:
                    datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                    issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                    if series_status == 'Paused':
                        astatus = "Skipped"
                    else:
                        if mylar.CONFIG.AUTOWANT_ALL:
                            astatus = "Wanted"
                        elif serieslast_updated is None:
                            #logger.fdebug('serieslast_update is None. Setting to Skipped')
                            astatus = "Skipped"
                        elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING:
                            logger.fdebug('[Marking as Wanted] week %s >= week %s' % (now_week, issue_week))
                            astatus = "Wanted"
                        elif all([int(re.sub('-', '', serieslast_updated).strip()) < int(dk), mylar.CONFIG.AUTOWANT_UPCOMING is True]):
                            logger.info('Autowant upcoming triggered for issue #%s' % firstval['Issue_Number'])
                            astatus = "Wanted"
                        else:
                            astatus = "Skipped"

                annchk.append({'IssueID':          str(firstval['Issue_ID']),
                               'ComicID':          comicid,
                               'ReleaseComicID':   re.sub('4050-', '', manual_comicid).strip(),
                               'ComicName':        comicname,
                               'Issue_Number':     str(firstval['Issue_Number']),
                               'IssueName':        cleanname,
                               'IssueDate':        str(firstval['Issue_Date']),
                               'ReleaseDate':      str(firstval['Store_Date']),
                               'DigitalDate':      str(firstval['Digital_Date']),
                               'Status':           astatus,
                               'ReleaseComicName': sr['ComicName'],
                               'Deleted':          deleted})
                n+=1

        if manualupd is True:
            return annchk

    for ann in annchk:
        newCtrl = {"IssueID": ann['IssueID']}
        newVals = {"Issue_Number":     ann['Issue_Number'],
                   "Int_IssueNumber":  helpers.issuedigits(ann['Issue_Number']),
                   "IssueDate":        ann['IssueDate'],
                   "ReleaseDate":      ann['ReleaseDate'],
                   "DigitalDate":      ann['DigitalDate'],
                   "IssueName":        ann['IssueName'],
                   "ComicID":          ann['ComicID'],   #this is the series ID
                   "ReleaseComicID":   ann['ReleaseComicID'],  #this is the series ID for the annual(s)
                   "ComicName":        ann['ComicName'], #series ComicName
                   "ReleaseComicName": ann['ReleaseComicName'], #series ComicName for the manual_comicid
                   "Status":           ann['Status'],
                   "Deleted":          ann['Deleted']}
                   #need to add in the values for the new series to be added.
                   #"M_ComicName":    sr['ComicName'],
                   #"M_ComicID":      manual_comicid}
        myDB.upsert("annuals", newVals, newCtrl)
    if len(annchk) > 0:
        logger.info('Successfully integrated ' + str(len(annchk)) + ' annuals into the series: ' + annchk[0]['ComicName'])
    return


def updateissuedata(comicid, comicname=None, issued=None, comicIssues=None, calledfrom=None, issuechk=None, issuetype=None, SeriesYear=None, latestissueinfo=None, serieslast_updated=None, series_status=None):
    annualchk = []
    weeklyissue_check = []
    db_already_open = False

    logger.fdebug('issuedata call references...')
    logger.fdebug('comicid: %s' % comicid)
    logger.fdebug('comicname: %s' % comicname)
    logger.fdebug('comicissues: %s' % comicIssues)
    logger.fdebug('calledfrom: %s' % calledfrom)
    logger.fdebug('issuechk: %s' % issuechk)
    logger.fdebug('latestissueinfo: %s' % latestissueinfo)
    logger.fdebug('issuetype: %s' % issuetype)

    if series_status is None and comicid is not None:
       db_already_open = True
       myDB = db.DBConnection()
       chk_series_status = myDB.selectone('SELECT Status from comics where ComicID=?', [comicid]).fetchone()
       if chk_series_status is not None:
           series_status = chk_series_status['Status']
       else:
           series_status = 'Active'

    #to facilitate independent calls to updateissuedata ONLY, account for data not available and get it.
    #chkType comes from the weeklypulllist - either 'annual' or not to distinguish annuals vs. issues
    if comicIssues is None:
        comic = cv.getComic(comicid, 'comic', series=True)
        if comic is None:
            logger.warn('Error retrieving from ComicVine - either the site is down or you are not using your own CV API key')
            return {'status': 'failure'}

        if comicIssues is None:
            comicIssues = comic['ComicIssues']
        if SeriesYear is None:
            SeriesYear = comic['ComicYear']
        if comicname is None:
            comicname = comic['ComicName']
    if issued is None:
        issued = cv.getComic(comicid, 'issue')
        if issued is None:
            logger.warn('Error retrieving from ComicVine - either the site is down or you are not using your own CV API key')
            return {'status': 'failure'}

    # poll against annuals here - to make sure annuals are uptodate.
    annualchk = annual_check(comicname, SeriesYear, comicid, issuetype, issuechk, annualchk, series_status)
    if annualchk is None:
        annualchk = []
    logger.fdebug('Finished Annual checking.')

    n = 0
    iscnt = int(comicIssues)
    issid = []
    issnum = []
    issname = []
    issdate = []
    issuedata = []
    # Start looking for the latest issue ID very low to accomodate series with only negative issues
    latestiss = "-999999999"
    latestdate = "0000-00-00"
    latest_stdate = "0000-00-00"
    latestissueid = None
    firstiss = "10000000"
    firstdate = "2099-00-00"
    legacy_num = None
    #print ("total issues:" + str(iscnt))
    logger.info('Now adding/updating issues for ' + comicname)

    if iscnt > 0: #if a series is brand new, it wont have any issues/details yet so skip this part
        while (n <= iscnt):
            try:
                firstval = issued['issuechoice'][n]
            except IndexError:
                break
            except Exception as e:
                logger.warn('Unable to parse issue details for series - ComicVine is probably having problems.')
                return {'status': 'failure'}
            try:
                cleanname = firstval['Issue_Name'] #helpers.cleanName(firstval['Issue_Name'])
            except:
                cleanname = 'None'
            issid = str(firstval['Issue_ID'])
            issnum = firstval['Issue_Number']
            issname = cleanname
            issdate = str(firstval['Issue_Date'])
            storedate = str(firstval['Store_Date'])
            digitaldate = str(firstval['Digital_Date'])
            int_issnum = None
            if issnum.isdigit():
                int_issnum = int(issnum) * 1000
            else:
                if 'a.i.' in issnum.lower() or 'ai' in issnum.lower():
                    issnum = re.sub('\.', '', issnum)
                    #int_issnum = (int(issnum[:-2]) * 1000) + ord('a') + ord('i')
                if 'au' in issnum.lower():
                    int_issnum = (int(issnum[:-2]) * 1000) + ord('a') + ord('u')
                elif 'inh' in issnum.lower():
                    int_issnum = (int(issnum[:-4]) * 1000) + ord('i') + ord('n') + ord('h')
                elif 'now' in issnum.lower():
                    int_issnum = (int(issnum[:-4]) * 1000) + ord('n') + ord('o') + ord('w')
                elif 'bey' in issnum.lower():
                    int_issnum = (int(issnum[:-4]) * 1000) + ord('b') + ord('e') + ord('y')
                elif 'mu' in issnum.lower():
                    int_issnum = (int(issnum[:-3]) * 1000) + ord('m') + ord('u')
                elif 'lr' in issnum.lower():
                    int_issnum = (int(issnum[:-3]) * 1000) + ord('l') + ord('r')
                elif 'hu' in issnum.lower():
                    int_issnum = (int(issnum[:-3]) * 1000) + ord('h') + ord('u')
                elif 'deaths' in issnum.lower():
                    int_issnum = (int(issnum[:-7]) * 1000) + ord('d') + ord('e') + ord('a') + ord('t') + ord('h') + ord('s')
                elif '\xbd' in issnum:
                    tmpiss = re.sub('[^0-9]', '', issnum).strip()
                    if len(tmpiss) > 0:
                        int_issnum = (int(tmpiss) + .5) * 1000
                    else:
                        int_issnum = .5 * 1000
                    logger.fdebug('1/2 issue detected :' + issnum + ' === ' + str(int_issnum))
                elif '\xbc' in issnum:
                    int_issnum = .25 * 1000
                elif '\xbe' in issnum:
                    int_issnum = .75 * 1000
                elif '\u221e' in issnum:
                    #issnum = utf-8 will encode the infinity symbol without any help
                    int_issnum = 9999999999 * 1000  # set 9999999999 for integer value of issue
                elif '.' in issnum or ',' in issnum:
                    if ',' in issnum: issnum = re.sub(',', '.', issnum)
                    issst = str(issnum).find('.')
                    #logger.fdebug("issst:" + str(issst))
                    if issst == 0:
                        issb4dec = 0
                    else:
                        issb4dec = str(issnum)[:issst]
                    #logger.fdebug("issb4dec:" + str(issb4dec))
                    #if the length of decimal is only 1 digit, assume it's a tenth
                    decis = str(issnum)[issst +1:]
                    #logger.fdebug("decis:" + str(decis))
                    if len(decis) == 1:
                        decisval = int(decis) * 10
                        issaftdec = str(decisval)
                    elif len(decis) == 2:
                        decisval = int(decis)
                        issaftdec = str(decisval)
                    else:
                        decisval = decis
                        issaftdec = str(decisval)
                    #if there's a trailing decimal (ie. 1.50.) and it's either intentional or not, blow it away.
                    if issaftdec[-1:] == '.':
                        logger.fdebug('Trailing decimal located within issue number. Irrelevant to numbering. Obliterating.')
                        issaftdec = issaftdec[:-1]
                    try:
                        #int_issnum = str(issnum)
                        int_issnum = (int(issb4dec) * 1000) + (int(issaftdec) * 10)
                    except ValueError:
                        try:
                            ordtot = 0
                            if any(ext == issaftdec.upper() for ext in mylar.ISSUE_EXCEPTIONS):
                                logger.fdebug('issue_exception detected..')
                                inu = 0
                                while (inu < len(issaftdec)):
                                    ordtot += ord(issaftdec[inu].lower())  #lower-case the letters for simplicty
                                    inu+=1
                                int_issnum = (int(issb4dec) * 1000) + ordtot
                        except Exception as e:
                                logger.warn('error: %s' % e)
                                ordtot = 0
                        if ordtot == 0:
                            logger.error('This has no issue # for me to get - Either a Graphic Novel or one-shot.')
                            updater.no_searchresults(comicid)
                            return {'status': 'failure'}
                elif all([ '[' in issnum, ']' in issnum ]):
                    issnum_tmp = issnum.find('[')
                    int_issnum = int(issnum[:issnum_tmp].strip()) * 1000
                    legacy_num = issnum[issnum_tmp+1:issnum.find(']')]
                else:
                    try:
                        x = float(issnum)
                        #validity check
                        if x < 0:
                            logger.fdebug('I have encountered a negative issue #: ' + str(issnum) + '. Trying to accomodate.')
                            logger.fdebug('value of x is : ' + str(x))
                            int_issnum = (int(x) *1000) - 1
                        else: raise ValueError
                    except ValueError as e:
                        x = 0
                        tstord = None
                        issno = None
                        invchk = "false"
                        if issnum.lower() != 'preview':
                            while (x < len(issnum)):
                                if issnum[x].isalpha():
                                    #take first occurance of alpha in string and carry it through
                                    tstord = issnum[x:].rstrip()
                                    tstord = re.sub('[\-\,\.\+]', '', tstord).rstrip()
                                    issno = issnum[:x].rstrip()
                                    issno = re.sub('[\-\,\.\+]', '', issno).rstrip()
                                    try:
                                        isschk = float(issno)
                                    except ValueError as e:
                                        if len(issnum) == 1 and issnum.isalpha():
                                            logger.fdebug('detected lone alpha issue. Attempting to figure this out.')
                                            break
                                        logger.fdebug('[' + issno + '] invalid numeric for issue - cannot be found. Ignoring.')
                                        issno = None
                                        tstord = None
                                        invchk = "true"
                                    break
                                x+=1

                        if all([tstord is not None, issno is not None, int_issnum is None]):
                            a = 0
                            ordtot = 0
                            if len(issnum) == 1 and issnum.isalpha():
                                int_issnum = ord(tstord.lower())
                            else:
                                while (a < len(tstord)):
                                    ordtot += ord(tstord[a].lower())  #lower-case the letters for simplicty
                                    a+=1
                                int_issnum = (int(issno) * 1000) + ordtot
                        elif invchk == "true":
                            if any([issnum.lower() == 'omega', issnum.lower() == 'alpha', issnum.lower() == 'fall 2005', issnum.lower() == 'spring 2005', issnum.lower() == 'summer 2006', issnum.lower() == 'winter 2009']):
                                issnum = re.sub('[0-9]+', '', issnum).strip()
                                inu = 0
                                ordtot = 0
                                while (inu < len(issnum)):
                                    ordtot += ord(issnum[inu].lower())  #lower-case the letters for simplicty
                                    inu+=1
                                int_issnum = ordtot
                            else:
                                logger.fdebug('this does not have an issue # that I can parse properly.')
                                return {'status': 'failure'}
                        else:
                            # Matches "number -&/\ number"
                            match = re.match(r"(?P<first>\d+)\s?[-&/\\]\s?(?P<last>\d+)", issnum)
                            if int_issnum is not None:
                                pass
                            elif match:
                                first_num, last_num = map(int, match.groups())
                                if last_num > first_num:
                                    int_issnum = (first_num * 1000) + int(((last_num - first_num) * .5) * 1000)
                                else:
                                    int_issnum = (first_num * 1000) + (.5 * 1000)
                            elif issnum == '9-5':
                                issnum = '9\xbd'
                                logger.fdebug('issue: 9-5 is an invalid entry. Correcting to : ' + issnum)
                                int_issnum = (9 * 1000) + (.5 * 1000)
                            elif issnum == '2 & 3':
                                logger.fdebug('issue: 2 & 3 is an invalid entry. Ensuring things match up')
                                int_issnum = (2 * 1000) + (.5 * 1000)
                            elif issnum == '4 & 5':
                                logger.fdebug('issue: 4 & 5 is an invalid entry. Ensuring things match up')
                                int_issnum = (4 * 1000) + (.5 * 1000)
                            elif issnum == '112/113':
                                int_issnum = (112 * 1000) + (.5 * 1000)
                            elif issnum == '14-16':
                                int_issnum = (15 * 1000) + (.5 * 1000)
                            elif issnum == '380/381':
                                int_issnum = (380 * 1000) + (.5 * 1000)
                            elif issnum.lower() == 'preview':
                                inu = 0
                                ordtot = 0
                                while (inu < len(issnum)):
                                    ordtot += ord(issnum[inu].lower())  #lower-case the letters for simplicty
                                    inu+=1
                                int_issnum = ordtot
                            else:
                                logger.error(issnum + ' this has an alpha-numeric in the issue # which I cannot account for.')
                                return {'status': 'failure'}
            #get the latest issue / date using the date.
            #logger.fdebug('issue : ' + str(issnum))
            #logger.fdebug('latest date: ' + str(latestdate))
            #logger.fdebug('first date: ' + str(firstdate))
            #logger.fdebug('issue date: ' + str(firstval['Issue_Date']))
            #logger.fdebug('issue date: ' + storedate)
            if any([firstval['Issue_Date'] >= latestdate, storedate >= latestdate]):
                #logger.fdebug('date check hit for issue date > latestdate')
                if int_issnum > helpers.issuedigits(latestiss):
                    #logger.fdebug('assigning latest issue to : ' + str(issnum))
                    latestiss = issnum
                    latestissueid = issid
                if firstval['Issue_Date'] != '0000-00-00':
                    latestdate = str(firstval['Issue_Date'])
                    latest_stdate = storedate
                else:
                    latestdate = storedate
                    latest_stdate = storedate

            if firstval['Issue_Date'] < firstdate and firstval['Issue_Date'] != '0000-00-00':
                firstiss = issnum
                firstdate = str(firstval['Issue_Date'])

            if issuechk is not None and issuetype == 'series':
                logger.fdebug('comparing ' + str(issuechk) + ' .. to .. ' + str(int_issnum))
                if issuechk == int_issnum:
                    weeklyissue_check.append({"Int_IssueNumber":    int_issnum,
                                              "Issue_Number":       issnum,
                                              "IssueDate":          issdate,
                                              "ReleaseDate":        storedate,
                                              "ComicID":            comicid,
                                              "IssueID":            issid})

            issuedata.append({"ComicID":            comicid,
                              "SeriesStatus":       series_status,
                              "IssueID":            issid,
                              "ComicName":          comicname,
                              "IssueName":          issname,
                              "Issue_Number":       issnum,
                              "IssueDate":          issdate,
                              "ReleaseDate":        storedate,
                              "DigitalDate":        digitaldate,
                              "Int_IssueNumber":    int_issnum,
                              "AltIssueNumber":     legacy_num,
                              "ImageURL":           firstval['Image'],
                              "ImageURL_ALT":       firstval['ImageALT']})

            n+=1

    if calledfrom == 'futurecheck' and len(issuedata) == 0:
        logger.fdebug('This is a NEW series with no issue data - skipping issue updating for now, and assigning generic information so things don\'t break')
        latestdate = latestissueinfo[0]['latestdate']   # if it's from futurecheck, issuechk holds the latestdate for the given issue
        latestiss = latestissueinfo[0]['latestiss']
        lastpubdate = 'Present'
        publishfigure = str(SeriesYear) + ' - ' + str(lastpubdate)
    else:
        #if calledfrom == 'weeklycheck':
        if len(issuedata) >= 1 and not calledfrom  == 'dbupdate':
            logger.fdebug('initiating issue updating - info & status')
            issue_collection(issuedata, nostatus='False', serieslast_updated=serieslast_updated)
        else:
            logger.fdebug('initiating issue updating - just the info')
            issue_collection(issuedata, nostatus='True', serieslast_updated=serieslast_updated)

        styear = str(SeriesYear)
        if firstdate is not None:
            if SeriesYear != firstdate[:4]:
                if firstdate[:4] == '2099':
                    logger.fdebug('Series start date (%s) differs from First Issue start date as First Issue date is unknown - assuming Series Year as Start Year (even though CV might say previous year - it\'s all gravy).' % (SeriesYear))
                else:
                    logger.fdebug('Series start date (%s) cannot be properly determined and/or it might cross over into different year (%s) - assuming store date of first issue (%s) as Start Year (even though CV might say previous year - it\'s all gravy).' % (SeriesYear, firstdate[:4], firstdate))
                if firstdate == '2099-00-00':
                    firstdate = '%s-01-01' % SeriesYear
                styear = str(firstdate[:4])

        if firstdate[5:7] == '00':
            stmonth = "?"
        else:
            stmonth = helpers.fullmonth(firstdate[5:7])

        #if the store date exists and is newer than the pub date - use the store date for ended calcs.
        if all([latest_stdate is not None, latest_stdate != '0000-00-00']):
            p_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), 1)
            s_date = datetime.date(int(latest_stdate[:4]), int(latest_stdate[5:7]), 1)
            if s_date > p_date:
               latestdate = latest_stdate

        ltyear = re.sub('/s', '', latestdate[:4])
        if latestdate[5:7] == '00':
            ltmonth = "?"
        else:
            ltmonth = helpers.fullmonth(latestdate[5:7])

        #try to determine if it's an 'actively' published comic from above dates
        #threshold is if it's within a month (<55 days) let's assume it's recent.
        try:
            c_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), 1)
        except:
            logger.error('Cannot determine Latest Date for given series. This is most likely due to an issue having a date of : 0000-00-00')
            latestdate = str(SeriesYear) + '-01-01'
            logger.error('Setting Latest Date to be ' + str(latestdate) + '. You should inform CV that the issue data is stale.')
            c_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), 1)

        n_date = datetime.date.today()
        recentchk = (n_date - c_date).days

        if recentchk <= helpers.checkthepub(comicid):
            lastpubdate = 'Present'
        else:
            if ltmonth == '?':
                if ltyear == '0000':
                    lastpubdate = '?'
                else:
                    lastpubdate = str(ltyear)
            elif ltyear == '0000':
                lastpubdate = '?'
            else:
                lastpubdate = str(ltmonth) + ' ' + str(ltyear)

        if stmonth == '?' and ('?' in lastpubdate and '0000' in lastpubdate):
            lastpubdate = 'Present'
            newpublish = True
            publishfigure = str(styear) + ' - ' + str(lastpubdate)
        else:
            newpublish = False
            if lastpubdate == '%s %s' % (stmonth, styear):
                publishfigure = '%s %s' % (stmonth, styear)
            else:
                publishfigure = '%s %s - %s' % (stmonth, styear, lastpubdate)

        if stmonth == '?' and styear == '?' and lastpubdate =='0000' and comicIssues == '0':
            logger.info('No available issue data - I believe this is a NEW series.')
            latestdate = latestissueinfo[0]['latestdate']
            latestiss = latestissueinfo[0]['latestiss']
            lastpubdate = 'Present'
            publishfigure = str(SeriesYear) + ' - ' + str(lastpubdate)


    if series_status == 'Loading':
        #if we're done loading and it's not Paused, set it Active again
        series_status = 'Active'

    controlValueStat = {"ComicID":     comicid}

    newValueStat = {"Status":          series_status,
                    "Total":           comicIssues,
                    "ComicPublished":  publishfigure,
                    "NewPublish":      newpublish,
                    "LatestIssue":     latestiss,
                    "intLatestIssue":  helpers.issuedigits(latestiss),
                    "LatestIssueID":   latestissueid,
                    "LatestDate":      latestdate,
                    "LastUpdated":     helpers.now()
                   }
    if not db_already_open:
        myDB = db.DBConnection()
    myDB.upsert("comics", newValueStat, controlValueStat)

    importantdates = {}
    importantdates['LatestIssue'] = latestiss
    importantdates['LatestIssueID'] = latestissueid
    importantdates['LatestDate'] = latestdate
    importantdates['LatestStoreDate'] = latest_stdate
    importantdates['LastPubDate'] = lastpubdate
    importantdates['SeriesStatus'] = series_status
    importantdates['ComicPublished'] = publishfigure
    importantdates['NewPublish'] = newpublish

    #series.json updater here (after all data written out)
    if mylar.CONFIG.SERIES_METADATA_LOCAL is True:
        sm = series_metadata.metadata_Series(comicid, bulk=False, api=False)
        sm.update_metadata()

    if calledfrom == 'weeklycheck':
        return weeklyissue_check

    elif len(issuedata) >= 1 and not calledfrom  == 'dbupdate':
        return {'issuedata': issuedata,
                'annualchk': annualchk,
                'importantdates': importantdates,
                'json_updated': True,
                'nostatus':  False}

    elif calledfrom == 'dbupdate':
        return {'issuedata': issuedata,
                'annualchk': annualchk,
                'importantdates': importantdates,
                'json_updated': True,
                'nostatus':  True}

    else:
        return importantdates

def annual_check(ComicName, SeriesYear, comicid, issuetype, issuechk, annualslist, series_status):
        annualids = []   #to be used to make sure an ID isn't double-loaded
        annload = []
        anncnt = 0

        nowdate = datetime.datetime.now()
        now_week = datetime.datetime.strftime(nowdate, "%Y%U")

        myDB = db.DBConnection()

        annual_load = myDB.select('SELECT * FROM annuals WHERE ComicID=?', [comicid])
        logger.fdebug('checking annual db')
        for annthis in annual_load:
            if not any(d['ReleaseComicID'] == annthis['ReleaseComicID'] for d in annload):
                #print 'matched on annual'
                 annload.append({
                     'ReleaseComicID':   annthis['ReleaseComicID'],
                     'ReleaseComicName': annthis['ReleaseComicName'],
                     'ComicID':          annthis['ComicID'],
                     'ComicName':        annthis['ComicName'],
                     'Deleted':          bool(annthis['Deleted'])
                     })

        if annload is None:
            pass
        else:
            for manchk in annload:
                if manchk['ReleaseComicID'] is not None or manchk['ReleaseComicID'] is not None:  #if it exists, then it's a pre-existing add
                    #print str(manchk['ReleaseComicID']), comic['ComicName'], str(SeriesYear), str(comicid)
                    tmp_the_annuals = manualAnnual(manchk['ReleaseComicID'], ComicName, SeriesYear, comicid, manualupd=True, deleted=manchk['Deleted'], series_status=series_status)
                    if tmp_the_annuals:
                        annualslist += tmp_the_annuals
                annualids.append(manchk['ReleaseComicID'])

        annualcomicname = re.sub('[\,\:]', '', ComicName)

        if annualcomicname.lower().startswith('the'):
            annComicName = annualcomicname[4:] + ' annual'
        else:
            annComicName = annualcomicname + ' annual'
        mode = 'series'

        annualyear = SeriesYear  # no matter what, the year won't be less than this.
        logger.fdebug('[IMPORTER-ANNUAL] - Annual Year:' + str(annualyear))
        sresults = mb.findComic(annComicName, mode, issue=None, annual_check=True)
        if not sresults:
            return

        annual_types_ignore = {'paperback', 'collecting', 'reprinting', 'reprints', 'collected edition', 'print edition', 'hardcover', 'hc', 'tpb', 'gn', 'graphic novel', 'available in print', 'collects'}

        if len(sresults) > 0:
            logger.fdebug('[IMPORTER-ANNUAL] - there are ' + str(len(sresults)) + ' results.')
            num_res = 0
            while (num_res < len(sresults)):
                sr = sresults[num_res]
                #logger.fdebug('description:%s' % sr['description'])
                for x in annual_types_ignore:
                    if x in sr['description'].lower():
                        test_id_position = sr['description'].find(comicid)
                        if test_id_position >= sr['description'].lower().find(x) or test_id_position == -1:
                            logger.fdebug('[IMPORTER-ANNUAL] - tradeback/collected edition detected - skipping ' + str(sr['comicid']))
                            continue

                if comicid in sr['description']:
                    logger.fdebug('[IMPORTER-ANNUAL] - ' + str(comicid) + ' found. Assuming it is part of the greater collection.')
                    issueid = sr['comicid']
                    logger.fdebug('[IMPORTER-ANNUAL] - ' + str(issueid) + ' added to series list as an Annual')
                    if issueid in annualids:
                        logger.fdebug('[IMPORTER-ANNUAL] - ' + str(issueid) + ' already exists within current annual list for series.')
                        num_res+=1 # need to manually increment since not a for-next loop
                        continue
                    issued = cv.getComic(issueid, 'issue')
                    if issued is None or len(issued) == 0:
                        logger.fdebug('[IMPORTER-ANNUAL] - Could not find any annual information...')
                        pass
                    else:
                        n = 0
                        if int(sr['issues']) == 0 and len(issued['issuechoice']) == 1:
                            sr_issues = 1
                        else:
                            if int(sr['issues']) != len(issued['issuechoice']):
                                sr_issues = len(issued['issuechoice'])
                            else:
                                sr_issues = sr['issues']
                        logger.fdebug('[IMPORTER-ANNUAL] - There are ' + str(sr_issues) + ' annuals in this series.')
                        while (n < int(sr_issues)):
                            try:
                               firstval = issued['issuechoice'][n]
                            except IndexError:
                               break
                            try:
                                cleanname = firstval['Issue_Name'] #helpers.cleanName(firstval['Issue_Name'])
                            except:
                                cleanname = 'None'
                            issid = str(firstval['Issue_ID'])
                            issnum = str(firstval['Issue_Number'])
                            issname = cleanname
                            issdate = str(firstval['Issue_Date'])
                            stdate = str(firstval['Store_Date'])
                            digdate = str(firstval['Digital_Date'])
                            int_issnum = helpers.issuedigits(issnum)

                            iss_exists = myDB.selectone('SELECT * from annuals WHERE IssueID=?', [issid]).fetchone()
                            if iss_exists is None:
                                if stdate == '0000-00-00':
                                    dk = re.sub('-', '', issdate).strip()
                                else:
                                    dk = re.sub('-', '', stdate).strip() # converts date to 20140718 format
                                if dk == '00000000':
                                     logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % firstval['Issue_Number'])
                                     astatus = "Skipped"
                                else:
                                    datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                                    issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                                    if series_status == 'Paused':
                                        astatus = "Skipped"
                                    else:
                                        if mylar.CONFIG.AUTOWANT_ALL:
                                            astatus = "Wanted"
                                        elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING is True:
                                            astatus = "Wanted"
                                        else:
                                            astatus = "Skipped"
                            else:
                                astatus = iss_exists['Status']

                            annualslist.append({"Issue_Number":     issnum,
                                                "Int_IssueNumber":  int_issnum,
                                                "IssueDate":        issdate,
                                                "ReleaseDate":      stdate,
                                                "DigitalDate":      digdate,
                                                "IssueName":        issname,
                                                "ComicID":          comicid,
                                                "IssueID":          issid,
                                                "ComicName":        ComicName,
                                                "ReleaseComicID":   re.sub('4050-', '', firstval['Comic_ID']).strip(),
                                                "ReleaseComicName": sr['name'],
                                                "Deleted":          False,
                                                "Status":           astatus})

                            #myDB.upsert("annuals", newVals, newCtrl)

                            # --- don't think this does anything since the value isn't returned in this module
                            #if issuechk is not None and issuetype == 'annual':
                            #    #logger.fdebug('[IMPORTER-ANNUAL] - Comparing annual ' + str(issuechk) + ' .. to .. ' + str(int_issnum))
                            #    if issuechk == int_issnum:
                            #        weeklyissue_check.append({"Int_IssueNumber":    int_issnum,
                            #                                  "Issue_Number":       issnum,
                            #                                  "IssueDate":          issdate,
                            #                                  "ReleaseDate":        stdate})

                            n+=1
                num_res+=1
            manualAnnual(annchk=annualslist,series_status=series_status)
            return annualslist

        elif sresults is None or len(sresults) == 0:
            logger.fdebug('[IMPORTER-ANNUAL] - No results, removing the year from the agenda and re-querying.')
            sresults = mb.findComic(annComicName, mode, issue=None, annual_check=True)
            if not sresults:
                return
            elif len(sresults) == 1:
                sr = sresults[0]
                logger.fdebug('[IMPORTER-ANNUAL] - ' + str(comicid) + ' found. Assuming it is part of the greater collection.')
            else:
                resultset = 0
        else:
            logger.fdebug('[IMPORTER-ANNUAL] - Returning results to screen - more than one possibility')
            for sr in sresults:
                if annualyear < sr['comicyear']:
                    logger.fdebug('[IMPORTER-ANNUAL] - ' + str(annualyear) + ' is less than ' + str(sr['comicyear']))
                if int(sr['issues']) > (2013 - int(sr['comicyear'])):
                    logger.fdebug('[IMPORTER-ANNUAL] - Issue count is wrong')

         #if this is called from the importer module, return the weeklyissue_check

def image_it(comicid, latestissueid, comlocation, ComicImage):
    #alternate series covers download latest image...

    cimage = os.path.join(mylar.CONFIG.CACHE_DIR, str(comicid) + '.jpg')
    imageurl = mylar.cv.getComic(comicid, 'image', issueid=latestissueid)
    if imageurl is None:
        return
    covercheck = helpers.getImage(comicid, imageurl['image'])
    if covercheck['status'] == 'retry':
        logger.fdebug('Attempting to retrieve a different comic image for this particular issue.')
        if imageurl['image_alt'] is not None:
            covercheck = helpers.getImage(comicid, imageurl['image_alt'])
        else:
            if not os.path.isfile(cimage):
                logger.fdebug('Failed to retrieve issue image, possibly because not available. Reverting back to series image.')
                covercheck = helpers.getImage(comicid, ComicImage)
    PRComicImage = os.path.join('cache', str(comicid) + ".jpg")
    ComicImage = helpers.replacetheslash(PRComicImage)

    #if the comic cover local is checked, save a cover.jpg to the series folder.
    if mylar.CONFIG.COMIC_COVER_LOCAL is True:
        cloc_it = []
        if (comlocation is not None and all([os.path.isdir(comlocation) is True, os.path.isfile(os.path.join(comlocation, 'cover.jpg')) is False])):
            cloc_it.append(comlocation)
        elif all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
            if all([os.path.isdir(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comlocation))) is True, os.path.isfile(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comlocation), 'cover.jpg')) is False]):
                cloc_it.append(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comlocation)))
            else:
                ff = mylar.filers.FileHandlers(ComicID=comicid)
                cloc = ff.secondary_folders(comlocation)
                if os.path.isfile(os.path.join(cloc, 'cover.jpg')) is False:
                    cloc_it.append(cloc)

        for clocit in cloc_it:
            try:
                comiclocal = os.path.join(clocit, 'cover.jpg')
                shutil.copyfile(cimage, comiclocal)
                if mylar.CONFIG.ENFORCE_PERMS:
                    filechecker.setperms(comiclocal)
            except IOError as e:
                if 'No such file or directory' not in str(e):
                    logger.error('[%s] Error saving cover (%s) into series directory (%s) at this time' % (e, cimage, comiclocal))

    myDB = db.DBConnection()
    myDB.upsert('comics', {'ComicImage': ComicImage}, {'ComicID': comicid})

def importer_thread(serieslist):
    # importer thread to queue up series to be added to the watchlist
    # serieslist = [{'comicid': '2828991', 'series': 'Some Comic', 'seriesyear': 1999}]

    if type(serieslist) != list:
        serieslist  = [(serieslist)]

    threaded_call = True

    list(map(mylar.ADD_LIST.put, serieslist))

    try:
        if mylar.MASS_ADD.is_alive():
            logger.info('[MASS-ADD] MASS_ADD thread already running. Adding an additional %s items to existing queue' % len(serieslist))
            threaded_call = False
    except Exception:
        pass

    if threaded_call is True:
        logger.info('[MASS-ADD] MASS_ADD thread not started. Started & submitting.')
        mylar.MASS_ADD = threading.Thread(target=addvialist, args=(mylar.ADD_LIST,), name="mass-add")
        mylar.MASS_ADD.start()
        if not mylar.MASS_ADD:
            mylar.MASS_ADD.join(5)


def refresh_thread(serieslist):
    # refresh thread to queue up series to be refreshed
    # serieslist = (28991, 38391, 93810)

    if type(serieslist) != list:
        serieslist  = [(serieslist)]

    threaded_call = True

    list(map(mylar.REFRESH_QUEUE.put, serieslist))

    try:
        if mylar.MASS_REFRESH.is_alive():
            logger.info('[MASS-REFRESH] MASS_REFRESH thread already running. Adding an additional %s items to existing queue' % len(serieslist))
            threaded_call = False
    except Exception:
        pass

    if threaded_call is True:
        logger.info('[MASS-REFRESH] MASS_REFRESH thread not started. Started & submitting.')
        mylar.MASS_REFRESH = threading.Thread(target=updater.addvialist, args=(mylar.REFRESH_QUEUE,), name="mass-refresh")
        mylar.MASS_REFRESH.start()
        if not mylar.MASS_REFRESH:
            mylar.MASS_REFRESH.join(5)

