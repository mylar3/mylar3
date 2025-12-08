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



import os
import glob
import re
import shutil
import random
import traceback

import mylar
from mylar import db, logger, helpers, importer, updater, filechecker

# You can scan a single directory and append it to the current library by specifying append=True
def libraryScan(dir=None, append=False, ComicID=None, ComicName=None, cron=None, queue=None):

    if cron and not mylar.LIBRARYSCAN:
        return

    if not dir:
        dir = mylar.CONFIG.COMIC_DIR

    if not os.path.isdir(dir):
        logger.warn('Cannot find directory: %s. Not scanning' % dir)
        return "Fail"


    logger.info('Scanning comic directory: %s' % dir)

    basedir = dir

    comic_list = []
    failure_list = []
    utter_failure_list = []
    comiccnt = 0
    extensions = ('cbr','cbz')
    cv_location = []
    cbz_retry = 0

    mylar.IMPORT_STATUS = 'Now attempting to parse files for additional information'
    myDB = db.DBConnection()
    #mylar.IMPORT_PARSED_COUNT #used to count what #/totalfiles the filename parser is currently on
    for r, d, f in os.walk(dir):
        for files in f:
            mylar.IMPORT_FILES +=1
            if any(files.lower().endswith('.' + x.lower()) for x in extensions):
                comicpath = os.path.join(r, files)
                if mylar.CONFIG.IMP_PATHS is True:
                    if myDB.select("SELECT * FROM comics JOIN issues WHERE issues.Status='Downloaded' AND ComicLocation=? AND issues.Location=?", [r, files]):
                        logger.info('Skipped known issue path: %s' % comicpath)
                        continue

                comic = files
                if not os.path.exists(comicpath):
                    logger.fdebug(f'''Comic: {comic} doesn't actually exist - assuming it is a symlink to a nonexistant path.''')
                    continue

                comicsize = os.path.getsize(comicpath)
                logger.fdebug('Comic: ' + comic + ' [' + comicpath + '] - ' + str(comicsize) + ' bytes')

                try:
                    t = filechecker.FileChecker(dir=r, file=comic)
                    results = t.listFiles()

                    #logger.info(results)
                    #'type':           re.sub('\.','', filetype).strip(),
                    #'sub':            path_list,
                    #'volume':         volume,
                    #'match_type':     match_type,
                    #'comicfilename':  filename,
                    #'comiclocation':  clocation,
                    #'series_name':    series_name,
                    #'series_volume':  issue_volume,
                    #'series_year':    issue_year,
                    #'justthedigits':  issue_number,
                    #'annualcomicid':  annual_comicid,
                    #'scangroup':      scangroup}


                    if results:
                        resultline = '[PARSE-' + results['parse_status'].upper() + ']'
                        resultline += '[SERIES: ' + results['series_name'] + ']'
                        if results['series_volume'] is not None:
                            resultline += '[VOLUME: ' + results['series_volume'] + ']'
                        if results['issue_year'] is not None:
                            resultline += '[ISSUE YEAR: ' + str(results['issue_year']) + ']'
                        if results['issue_number'] is not None:
                            resultline += '[ISSUE #: ' + results['issue_number'] + ']'
                        logger.fdebug(resultline)
                    else:
                        logger.fdebug('[PARSED] FAILURE.')
                        continue

                    # We need the unicode path to use for logging, inserting into database
                    unicode_comic_path = comicpath

                    if results['parse_status'] == 'success':
                        comic_list.append({'ComicFilename':           comic,
                                           'ComicLocation':           comicpath,
                                           'ComicSize':               comicsize,
                                           'Unicode_ComicLocation':   unicode_comic_path,
                                           'parsedinfo':              {'series_name':    results['series_name'],
                                                                       'series_volume':  results['series_volume'],
                                                                       'issue_year':     results['issue_year'],
                                                                       'issue_number':   results['issue_number']}
                                           })
                        comiccnt +=1
                        mylar.IMPORT_PARSED_COUNT +=1
                    else:
                        failure_list.append({'ComicFilename':           comic,
                                             'ComicLocation':           comicpath,
                                             'ComicSize':               comicsize,
                                             'Unicode_ComicLocation':   unicode_comic_path,
                                             'parsedinfo':              {'series_name':    results['series_name'],
                                                                         'series_volume':  results['series_volume'],
                                                                         'issue_year':     results['issue_year'],
                                                                         'issue_number':   results['issue_number']}
                                           })
                        mylar.IMPORT_FAILURE_COUNT +=1
                        if comic.endswith('.cbz'):
                            cbz_retry +=1

                except Exception as e:
                    logger.info('bang')
                    utter_failure_list.append({'ComicFilename':           comic,
                                               'ComicLocation':           comicpath,
                                               'ComicSize':               comicsize,
                                               'Unicode_ComicLocation':   unicode_comic_path,
                                               'parsedinfo':              None,
                                               'error':                   e
                                             })
                    logger.info('[' + str(e) + '] FAILURE encountered. Logging the error for ' + comic + ' and continuing...')
                    mylar.IMPORT_FAILURE_COUNT +=1
                    if comic.endswith('.cbz'):
                        cbz_retry +=1
                    continue

            if 'cvinfo' in files:
                cv_location.append(r)
                logger.fdebug('CVINFO found: ' + os.path.join(r))

    mylar.IMPORT_TOTALFILES = comiccnt
    logger.info('I have successfully discovered & parsed a total of ' + str(comiccnt) + ' files....analyzing now')
    logger.info('I have not been able to determine what ' + str(len(failure_list)) + ' files are')
    logger.info('However, ' + str(cbz_retry) + ' out of the ' + str(len(failure_list)) + ' files are in a cbz format, which may contain metadata.')
    logger.info('[ERRORS] I have encountered ' + str(len(utter_failure_list)) + ' file-scanning errors during the scan, but have recorded the necessary information.')
    mylar.IMPORT_STATUS = 'Successfully parsed ' + str(comiccnt) + ' files'
    #return queue.put(valreturn)

    if len(utter_failure_list) > 0:
        logger.fdebug('Failure list: %s' % utter_failure_list)

    #let's load in the watchlist to see if we have any matches.
    logger.info("loading in the watchlist to see if a series is being watched already...")
    watchlist = myDB.select("SELECT * from comics")
    ComicName = []
    DisplayName = []
    ComicYear = []
    ComicPublisher = []
    ComicTotal = []
    ComicID = []
    ComicLocation = []

    AltName = []
    watchcnt = 0

    watch_kchoice = []
    watchchoice = {}
    import_by_comicids = []
    import_comicids = {}

    for watch in watchlist:
        #use the comicname_filesafe to start
        watchdisplaycomic = watch['ComicName']
        # let's clean up the name, just in case for comparison purposes...
        try:
            watchcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]', '', watch['ComicName_Filesafe'])
        except Exception as e:
            logger.warn('[IMPORT] Unable to properly retrieve series name from watchlist.'
                        ' This is due most likely to previous problems refreshing/adding the seriess %s [error: %s]'
                         % (watch['ComicName_Filesafe'], e)
            )
            continue
        #watchcomic = re.sub('\s+', ' ', str(watchcomic)).strip()

        if ' the ' in watchcomic.lower():
            #drop the 'the' from the watchcomic title for proper comparisons.
            watchcomic = watchcomic[-4:]

        alt_chk = "no" # alt-checker flag (default to no)

        # account for alternate names as well
        if watch['AlternateSearch'] is not None and watch['AlternateSearch'] != 'None':
            altcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]', '', watch['AlternateSearch'])
            #altcomic = re.sub('\s+', ' ', str(altcomic)).strip()
            AltName.append(altcomic)
            alt_chk = "yes"  # alt-checker flag

        ComicName.append(watchcomic)
        DisplayName.append(watchdisplaycomic)
        ComicYear.append(watch['ComicYear'])
        ComicPublisher.append(watch['ComicPublisher'])
        ComicTotal.append(watch['Total'])
        ComicID.append(watch['ComicID'])
        ComicLocation.append(watch['ComicLocation'])
        watchcnt+=1

    logger.info("Successfully loaded " + str(watchcnt) + " series from your watchlist.")

    ripperlist=['digital-',
                'empire',
                'dcp']

    watchfound = 0

    datelist = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
#    datemonth = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':$
#    #search for number as text, and change to numeric
#    for numbs in basnumbs:
#        #logger.fdebug("numbs:" + str(numbs))
#        if numbs in ComicName.lower():
#            numconv = basnumbs[numbs]
#            #logger.fdebug("numconv: " + str(numconv))

    issueid_list = []
    cvscanned_loc = None
    cvinfo_CID = None
    cnt = 0
    mylar.IMPORT_STATUS = '[0%] Now parsing individual filenames for metadata if available'

    for i in comic_list:
        mylar.IMPORT_STATUS = '[' + str(cnt) + '/' + str(comiccnt) + '] Now parsing individual filenames for metadata if available'
        logger.fdebug('Analyzing : ' + i['ComicFilename'])
        comfilename = i['ComicFilename']
        comlocation = i['ComicLocation']
        issueinfo = None
        #probably need to zero these issue-related metadata to None so we can pick the best option
        issuevolume = None

        #Make sure cvinfo is checked for FIRST (so that CID can be attached to all files properly thereafter as they're scanned in)
        if os.path.dirname(comlocation) in cv_location and os.path.dirname(comlocation) != cvscanned_loc:

        #if comfilename == 'cvinfo':
            logger.info('comfilename: ' + comfilename)
            logger.info('cvscanned_loc: ' + str(cv_location))
            logger.info('comlocation: ' + os.path.dirname(comlocation))
            #if cvscanned_loc != comlocation:
            try:
                with open(os.path.join(os.path.dirname(comlocation), 'cvinfo')) as f:
                    urllink = f.readline()

                if urllink:
                    cid = urllink.strip()
                    pattern = re.compile(r"^.*?\b(49|4050)-(?P<num>\d{2,})\b.*$", re.I)
                    match = pattern.match(cid)
                    if match:
                        cvinfo_CID = match.group("num")
                        logger.info('CVINFO file located within directory. Attaching everything in directory that is valid to ComicID: ' + str(cvinfo_CID))
                        #store the location of the cvinfo so it's applied to the correct directory (since we're scanning multile direcorties usually)
                        cvscanned_loc = os.path.dirname(comlocation)
                else:
                    logger.error("Could not read cvinfo file properly (or it does not contain any data)")
            except (OSError, IOError):
                logger.error("Could not read cvinfo file properly (or it does not contain any data)")
        #else:
        #    don't scan in it again if it's already been done initially
        #    continue

        if mylar.CONFIG.IMP_METADATA:
            #if read tags is enabled during import, check here.
            if i['ComicLocation'].endswith('.cbz'):
                logger.fdebug('[IMPORT-CBZ] Metatagging checking enabled.')
                logger.info('[IMPORT-CBZ} Attempting to read tags present in filename: ' + i['ComicLocation'])
                try:
                    issueinfo = helpers.IssueDetails(i['ComicLocation'], justinfo=True)
                except:
                    logger.fdebug('[IMPORT-CBZ] Unable to retrieve metadata - possibly doesn\'t exist. Ignoring meta-retrieval')
                    pass
                else:
                    logger.info('issueinfo: ' + str(issueinfo))

                    if issueinfo is None or issueinfo['metadata'] is None:
                        logger.fdebug('[IMPORT-CBZ] No valid metadata contained within filename. Dropping down to parsing the filename itself.')
                        pass
                    else:
                        issuenotes_id = None
                        logger.info('[IMPORT-CBZ] Successfully retrieved some tags. Lets see what I can figure out.')
                        comicname = issueinfo['metadata']['series']
                        if comicname is not None:
                            logger.fdebug('[IMPORT-CBZ] Series Name: ' + comicname)
                            as_d = filechecker.FileChecker()
                            as_dyninfo = as_d.dynamic_replace(comicname)
                            logger.fdebug('Dynamic-ComicName: ' + as_dyninfo['mod_seriesname'])
                        else:
                            logger.fdebug('[IMPORT-CBZ] No series name found within metadata. This is bunk - dropping down to file parsing for usable information.')
                            issueinfo = None
                            issue_number = None

                        if issueinfo is not None:
                            try:
                                issueyear = issueinfo['metadata']['year']
                            except:
                                issueyear = None

                            #if the issue number is a non-numeric unicode string, this will screw up along with impID
                            issue_number = issueinfo['metadata']['issue_number']
                            if issue_number is not None:
                                logger.fdebug('[IMPORT-CBZ] Issue Number: ' + issue_number)
                            else:
                                issue_number = i['parsed']['issue_number']

                            if 'annual' in comicname.lower() or 'annual' in comfilename.lower():
                                if issue_number is None or issue_number == 'None':
                                    logger.info('Annual detected with no issue number present within metadata. Assuming year as issue.')
                                    try:
                                        issue_number = 'Annual ' + str(issueyear)
                                    except:
                                        issue_number = 'Annual ' + i['parsed']['issue_year']
                                else:
                                    logger.info('Annual detected with issue number present within metadata.')
                                    if 'annual' not in issue_number.lower():
                                        issue_number = 'Annual ' + issue_number
                                mod_series = re.sub('annual', '', comicname, flags=re.I).strip()
                            else:
                                mod_series = comicname

                            logger.fdebug('issue number SHOULD Be: ' + issue_number)

                            try:
                                issuetitle = issueinfo['metadata']['title']
                            except:
                                issuetitle = None
                            try:
                                issueyear = issueinfo['metadata']['year']
                            except:
                                issueyear = None
                            try:
                                issuevolume = str(issueinfo['metadata']['volume'])
                                if all([issuevolume is not None, issuevolume != 'None', not issuevolume.lower().startswith('v')]):
                                    issuevolume = 'v' + str(issuevolume)
                                if any([issuevolume is None, issuevolume == 'None']):
                                    logger.info('EXCEPT] issue volume is NONE')
                                    issuevolume = None
                                else:
                                    logger.fdebug('[TRY]issue volume is: ' + str(issuevolume))
                            except:
                                logger.fdebug('[EXCEPT]issue volume is: ' + str(issuevolume))
                                issuevolume = None

                            if any([comicname is None, comicname == 'None', issue_number is None, issue_number == 'None']):
                                logger.fdebug('[IMPORT-CBZ] Improperly tagged file as the metatagging is invalid. Ignoring meta and just parsing the filename.')
                                issueinfo = None
                                pass
                            else:
                                # if used by ComicTagger, Notes field will have the IssueID.
                                issuenotes = issueinfo['metadata']['notes']
                                logger.fdebug('[IMPORT-CBZ] Notes: ' + issuenotes)
                                # Attempt to parse the first set of consecutive numbers after either CVDB or Issue ID
                                if issuenotes is not None and issuenotes != 'None':
                                    issue_id = re.search("(CVDB|Issue ID)[^0-9]*([0-9]*)", issuenotes)
                                    if issue_id:
                                        if issue_id.groups()[1].isdigit():
                                            issuenotes_id = issue_id.groups()[1]
                                            logger.fdebug('[IMPORT-CBZ] Successfully retrieved CV IssueID for ' + comicname + ' #' + issue_number + ' [' + str(issuenotes_id) + ']')
                                    else:
                                        logger.fdebug('[IMPORT-CBZ] Unable to retrieve IssueID from meta-tagging. If there is other metadata present I will use that.')

                                # If this doesn't work, we can fall back to try and parse from the webpage
                                webpage = issueinfo['metadata']['webpage']
                                logger.fdebug('[IMPORT-CBZ] Webpage: ' + webpage)
                                if webpage is not None and webpage != 'None' and 'comicvine.gamespot.com' in webpage and issuenotes_id is None:
                                    issue_id = webpage.strip('/').split('/')[-1].split('-')[-1]
                                    if issue_id:
                                        issuenotes_id = issue_id
                                        logger.fdebug('[IMPORT-CBZ] Successfully retrieved CV IssueID for ' + comicname + ' #' + issue_number + ' [' + str(issuenotes_id) + ']')
                                    else:
                                        logger.fdebug('[IMPORT-CBZ] Unable to retrieve IssueID from meta-tagging. If there is other metadata present I will use that.')

                                logger.fdebug('[IMPORT-CBZ] Adding ' + comicname + ' to the import-queue!')
                                #impid = comicname + '-' + str(issueyear) + '-' + str(issue_number) #com_NAME + "-" + str(result_comyear) + "-" + str(comiss)
                                impid = str(random.randint(1000000,99999999))
                                logger.fdebug('[IMPORT-CBZ] impid: ' + str(impid))
                                #make sure we only add in those issueid's which don't already have a comicid attached via the cvinfo scan above (this is for reverse-lookup of issueids)
                                issuepopulated = False
                                if cvinfo_CID is None:
                                    if issuenotes_id is None:
                                        logger.info('[IMPORT-CBZ] No ComicID detected where it should be. Bypassing this metadata entry and going the parsing route [' + comfilename + ']')
                                    else:
                                        #we need to store the impid here as well so we can look it up.
                                        issueid_list.append({'issueid':    issuenotes_id,
                                                             'importinfo': {'impid':       impid,
                                                                            'comicid':     None,
                                                                            'comicname':   comicname,
                                                                            'dynamicname': as_dyninfo['mod_seriesname'],
                                                                            'comicyear':   issueyear,
                                                                            'issuenumber': issue_number,
                                                                            'volume':      issuevolume,
                                                                            'comfilename': comfilename,
                                                                            'comlocation': comlocation}
                                                           })
                                        mylar.IMPORT_CID_COUNT +=1
                                        issuepopulated = True

                                if issuepopulated == False:
                                    if cvscanned_loc == os.path.dirname(comlocation):
                                        cv_cid = cvinfo_CID
                                        logger.fdebug('[IMPORT-CBZ] CVINFO_COMICID attached : ' + str(cv_cid))
                                    else:
                                        cv_cid = None
                                    import_by_comicids.append({
                                        "impid": impid,
                                        "comicid": cv_cid,
                                        "watchmatch": None,
                                        "displayname": mod_series,
                                        "comicname": comicname,
                                        "dynamicname": as_dyninfo['mod_seriesname'],
                                        "comicyear": issueyear,
                                        "issuenumber": issue_number,
                                        "volume": issuevolume,
                                        "issueid": issuenotes_id,
                                        "comfilename": comfilename,
                                        "comlocation": comlocation
                                                       })

                                    mylar.IMPORT_CID_COUNT +=1
                        else:
                            pass
                            #logger.fdebug(i['ComicFilename'] + ' is not in a metatagged format (cbz). Bypassing reading of the metatags')

        if issueinfo is None:
            if i['parsedinfo']['issue_number'] is None:
                if 'annual' in i['parsedinfo']['series_name'].lower():
                    logger.fdebug('Annual detected with no issue number present. Assuming year as issue.')##1 issue')
                    if i['parsedinfo']['issue_year'] is not None:
                        issuenumber = 'Annual ' + str(i['parsedinfo']['issue_year'])
                    else:
                        issuenumber = 'Annual 1'
            else:
                issuenumber = i['parsedinfo']['issue_number']

            if 'annual' in i['parsedinfo']['series_name'].lower():
                mod_series = re.sub('annual', '', i['parsedinfo']['series_name'], flags=re.I).strip()
                logger.fdebug('Annual detected with no issue number present. Assuming year as issue.')##1 issue')
                if i['parsedinfo']['issue_number'] is not None:
                    issuenumber = 'Annual ' + str(i['parsedinfo']['issue_number'])
                else:
                    if i['parsedinfo']['issue_year'] is not None:
                        issuenumber = 'Annual ' + str(i['parsedinfo']['issue_year'])
                    else:
                        issuenumber = 'Annual 1'
            else:
                mod_series = i['parsedinfo']['series_name']
                issuenumber = i['parsedinfo']['issue_number']


            logger.fdebug('[' + mod_series + '] Adding to the import-queue!')
            isd = filechecker.FileChecker()
            is_dyninfo = isd.dynamic_replace(mod_series) #helpers.conversion(mod_series))
            logger.fdebug('Dynamic-ComicName: ' + is_dyninfo['mod_seriesname'])

            #impid = dispname + '-' + str(result_comyear) + '-' + str(comiss) #com_NAME + "-" + str(result_comyear) + "-" + str(comiss)
            impid = str(random.randint(1000000,99999999))
            logger.fdebug("impid: " + str(impid))
            if cvscanned_loc == os.path.dirname(comlocation):
                cv_cid = cvinfo_CID
                logger.fdebug('CVINFO_COMICID attached : ' + str(cv_cid))
            else:
                cv_cid = None

            if issuevolume is None:
                logger.fdebug('issue volume is : ' + str(issuevolume))
                if i['parsedinfo']['series_volume'] is None:
                    issuevolume = None
                else:
                    if str(i['parsedinfo']['series_volume'].lower()).startswith('v'):
                        issuevolume = i['parsedinfo']['series_volume']
                    else:
                        issuevolume = 'v' + str(i['parsedinfo']['series_volume'])
            else:
                logger.fdebug('issue volume not none : ' + str(issuevolume))
                if issuevolume.lower().startswith('v'):
                    issuevolume = issuevolume
                else:
                    issuevolume = 'v' + str(issuevolume)

            logger.fdebug('IssueVolume is : ' + str(issuevolume))

            import_by_comicids.append({
                "impid": impid,
                "comicid": cv_cid,
                "issueid": None,
                "watchmatch": None, #watchmatch (should be true/false if it already exists on watchlist)
                "displayname": mod_series,
                "comicname": i['parsedinfo']['series_name'],
                "dynamicname": is_dyninfo['mod_seriesname'].lower(),
                "comicyear": i['parsedinfo']['issue_year'],
                "issuenumber": issuenumber, #issuenumber,
                "volume": issuevolume,
                "comfilename": comfilename,
                "comlocation": comlocation #helpers.conversion(comlocation)
                                      })
        cnt+=1
    #logger.fdebug('import_by_ids: ' + str(import_by_comicids))

    #reverse lookup all of the gathered IssueID's in order to get the related ComicID
    reverse_issueids = []
    for x in issueid_list:
        reverse_issueids.append(x['issueid'])

    vals = []
    if len(reverse_issueids) > 0:
        mylar.IMPORT_STATUS = 'Now Reverse looking up ' + str(len(reverse_issueids)) + ' IssueIDs to get the ComicIDs'
        vals = mylar.cv.getComic(None, 'import', comicidlist=reverse_issueids)
        #logger.fdebug('vals returned:' + str(vals))

    if len(watch_kchoice) > 0:
        watchchoice['watchlist'] = watch_kchoice
        #logger.fdebug("watchchoice: " + str(watchchoice))

        logger.info("I have found " + str(watchfound) + " out of " + str(comiccnt) + " comics for series that are being watched.")
        wat = 0
        comicids = []

        if watchfound > 0:
            if mylar.CONFIG.IMP_MOVE:
                logger.info('You checked off Move Files...so that\'s what I am going to do') 
                #check to see if Move Files is enabled.
                #if not being moved, set the archive bit.
                logger.fdebug('Moving files into appropriate directory')
                while (wat < watchfound): 
                    watch_the_list = watchchoice['watchlist'][wat]
                    watch_comlocation = watch_the_list['ComicLocation']
                    watch_comicid = watch_the_list['ComicID']
                    watch_comicname = watch_the_list['ComicName']
                    watch_comicyear = watch_the_list['ComicYear']
                    watch_comiciss = watch_the_list['ComicIssue']
                    logger.fdebug('ComicLocation: ' + watch_comlocation)
                    orig_comlocation = watch_the_list['OriginalLocation']
                    orig_filename = watch_the_list['OriginalFilename'] 
                    logger.fdebug('Orig. Location: ' + orig_comlocation)
                    logger.fdebug('Orig. Filename: ' + orig_filename)
                    #before moving check to see if Rename to Mylar structure is enabled.
                    if mylar.CONFIG.IMP_RENAME:
                        logger.fdebug('Renaming files according to configuration details : ' + str(mylar.CONFIG.FILE_FORMAT))
                        renameit = helpers.rename_param(watch_comicid, watch_comicname, watch_comicyear, watch_comiciss)
                        nfilename = renameit['nfilename']

                        dst_path = os.path.join(watch_comlocation, nfilename)
                        if str(watch_comicid) not in comicids:
                            comicids.append(watch_comicid)
                    else:
                        logger.fdebug('Renaming files not enabled, keeping original filename(s)')
                        dst_path = os.path.join(watch_comlocation, orig_filename)

                    #os.rename(os.path.join(self.nzb_folder, str(ofilename)), os.path.join(self.nzb_folder,str(nfilename + ext)))
                    #src = os.path.join(, str(nfilename + ext))
                    logger.fdebug('I am going to move ' + orig_comlocation + ' to ' + dst_path)
                    try:
                        shutil.move(orig_comlocation, dst_path)
                    except (OSError, IOError):
                        logger.info("Failed to move directory - check directories and manually re-run.")
                    wat+=1
            else:
                # if move files isn't enabled, let's set all found comics to Archive status :)
                while (wat < watchfound):
                    watch_the_list = watchchoice['watchlist'][wat]
                    watch_comicid = watch_the_list['ComicID']
                    watch_issue = watch_the_list['ComicIssue']
                    logger.fdebug('ComicID: ' + str(watch_comicid))
                    logger.fdebug('Issue#: ' + str(watch_issue))
                    issuechk = myDB.selectone("SELECT * from issues where ComicID=? AND INT_IssueNumber=?", [watch_comicid, watch_issue]).fetchone()
                    if issuechk is None:
                        logger.fdebug('No matching issues for this comic#')
                    else:
                        logger.fdebug('...Existing status: ' + str(issuechk['Status']))
                        control = {"IssueID":   issuechk['IssueID']}
                        values = {"Status":   "Archived"}
                        logger.fdebug('...changing status of ' + str(issuechk['Issue_Number']) + ' to Archived ')
                        myDB.upsert("issues", values, control)
                        if str(watch_comicid) not in comicids:
                            comicids.append(watch_comicid)
                    wat+=1
            if comicids is None: pass
            else:
                c_upd = len(comicids)
                c = 0
                while (c < c_upd ):
                    logger.fdebug('Rescanning.. ' + str(c))
                    updater.forceRescan(c) 
        if not len(import_by_comicids):
            return "Completed"

    if len(import_by_comicids) > 0 or len(vals) > 0:
        #import_comicids['comic_info'] = import_by_comicids
        #if vals:
        #    import_comicids['issueid_info'] = vals
        #else:
        #    import_comicids['issueid_info'] = None
        if vals:
             cvimport_comicids = vals
             import_cv_ids = len(vals)
        else:
             cvimport_comicids = None
             import_cv_ids = 0
    else:
        import_cv_ids = 0
        cvimport_comicids = None
                    
    return {'import_by_comicids':  import_by_comicids, 
            'import_count':        len(import_by_comicids),
            'CV_import_comicids':  cvimport_comicids,
            'import_cv_ids':       import_cv_ids,
            'issueid_list':        issueid_list,
            'failure_list':        failure_list,
            'utter_failure_list':  utter_failure_list}


def scanLibrary(scan=None, queue=None):
    mylar.IMPORT_FILES = 0
    mylar.IMPORT_PARSED_COUNT = 0
    valreturn = []
    if scan:
        try:
            soma = libraryScan(queue=queue)
        except Exception as e:
            logger.error('[IMPORT] Unable to complete the scan: %s' % e)
            logger.error(traceback.format_exc())
            mylar.IMPORT_STATUS = None
            valreturn.append({"somevalue":  'self.ie',
                              "result":     'error'})
            return queue.put(valreturn)
        if soma == "Completed":
            logger.info('[IMPORT] Sucessfully completed import.')
        elif soma == "Fail":
            mylar.IMPORT_STATUS = 'Failure'
            valreturn.append({"somevalue":  'self.ie',
                              "result":     'error'})
            return queue.put(valreturn)
        else:
            mylar.IMPORT_STATUS = 'Now adding the completed results to the DB.'
            logger.info('[IMPORT] Parsing/Reading of files completed!')
            logger.info('[IMPORT] Attempting to import ' + str(int(soma['import_cv_ids'] + soma['import_count'])) + ' files into your watchlist.')
            logger.info('[IMPORT-BREAKDOWN] Files with ComicIDs successfully extracted: ' + str(soma['import_cv_ids']))
            logger.info('[IMPORT-BREAKDOWN] Files that had to be parsed: ' + str(soma['import_count']))
            logger.info('[IMPORT-BREAKDOWN] Files that were unable to be parsed: ' + str(len(soma['failure_list'])))
            logger.info('[IMPORT-BREAKDOWN] Files that caused errors during the import: ' + str(len(soma['utter_failure_list'])))
            #logger.info('[IMPORT-BREAKDOWN] Failure Files: ' + str(soma['failure_list']))
      
            myDB = db.DBConnection()

            #first we do the CV ones.
            if int(soma['import_cv_ids']) > 0:
                for i in soma['CV_import_comicids']:
                    #we need to find the impid in the issueid_list as that holds the impid + other info
                    abc = [x for x in soma['issueid_list'] if x['issueid'] == i['IssueID']]
                    ghi = abc[0]['importinfo']

                    nspace_dynamicname = re.sub('[\|\s]', '', ghi['dynamicname'].lower()).strip()                   
                    #these all have related ComicID/IssueID's...just add them as is.
                    controlValue = {"impID":        ghi['impid']}
                    newValue = {"Status":           "Not Imported",
                                "ComicName":        i['ComicName'], #helpers.conversion(i['ComicName']),
                                "DisplayName":      i['ComicName'], #helpers.conversion(i['ComicName']),
                                "DynamicName":      nspace_dynamicname, #helpers.conversion(nspace_dynamicname),
                                "ComicID":          i['ComicID'],
                                "IssueID":          i['IssueID'],
                                "IssueNumber":      i['Issue_Number'], #helpers.conversion(i['Issue_Number']),
                                "Volume":           ghi['volume'],
                                "ComicYear":        ghi['comicyear'],
                                "ComicFilename":    ghi['comfilename'], #helpers.conversion(ghi['comfilename']),
                                "ComicLocation":    ghi['comlocation'], #helpers.conversion(ghi['comlocation']),
                                "ImportDate":       helpers.today(),
                                "WatchMatch":       None} #i['watchmatch']}
                    myDB.upsert("importresults", newValue, controlValue)
                
            if int(soma['import_count']) > 0:
                for ss in soma['import_by_comicids']:

                    nspace_dynamicname = re.sub('[\|\s]', '', ss['dynamicname'].lower()).strip()                   

                    controlValue = {"impID":        ss['impid']}
                    newValue = {"ComicYear":        ss['comicyear'],
                                "Status":           "Not Imported",
                                "ComicName":        ss['comicname'], #helpers.conversion(ss['comicname']),
                                "DisplayName":      ss['displayname'], #helpers.conversion(ss['displayname']),
                                "DynamicName":      nspace_dynamicname, #helpers.conversion(nspace_dynamicname),
                                "ComicID":          ss['comicid'],  #if it's been scanned in for cvinfo, this will be the CID - otherwise it's None
                                "IssueID":          None,
                                "Volume":           ss['volume'],
                                "IssueNumber":      ss['issuenumber'], #helpers.conversion(ss['issuenumber']),
                                "ComicFilename":    ss['comfilename'], #helpers.conversion(ss['comfilename']),
                                "ComicLocation":    ss['comlocation'], #helpers.conversion(ss['comlocation']),
                                "ImportDate":       helpers.today(),
                                "WatchMatch":       ss['watchmatch']}
                    myDB.upsert("importresults", newValue, controlValue)

            # because we could be adding volumes/series that span years, we need to account for this
            # add the year to the db under the term, valid-years
            # add the issue to the db under the term, min-issue

            #locate metadata here.
            # unzip -z filename.cbz will show the comment field of the zip which contains the metadata.

        #self.importResults()
        mylar.IMPORT_STATUS = 'Import completed.'
        valreturn.append({"somevalue":  'self.ie',
                          "result":     'success'})
        return queue.put(valreturn)
