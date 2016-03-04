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
import shutil
import re
import shlex
import time
import logging
import mylar
import subprocess
import urllib2
import sys
from xml.dom.minidom import parseString


from mylar import logger, db, helpers, updater, notifiers, filechecker, weeklypull

class PostProcessor(object):
    """
    A class which will process a media file according to the post processing settings in the config.
    """

    EXISTS_LARGER = 1
    EXISTS_SAME = 2
    EXISTS_SMALLER = 3
    DOESNT_EXIST = 4

    NZB_NAME = 1
    FOLDER_NAME = 2
    FILE_NAME = 3

    def __init__(self, nzb_name, nzb_folder, module=None, queue=None):
        """
        Creates a new post processor with the given file path and optionally an NZB name.

        file_path: The path to the file to be processed
        nzb_name: The name of the NZB which resulted in this file being downloaded (optional)
        """
        # name of the NZB that resulted in this folder
        self.nzb_name = nzb_name
        self.nzb_folder = nzb_folder
        if module is not None:
            self.module = module + '[POST-PROCESSING]'
        else:
            self.module = '[POST-PROCESSING]'

        if queue: 
            self.queue = queue

        if mylar.FILE_OPTS == 'copy':
            self.fileop = shutil.copy
        else:
            self.fileop = shutil.move

        self.valreturn = []
        self.log = ''

    def _log(self, message, level=logger.message):  #level=logger.MESSAGE):
        """
        A wrapper for the internal logger which also keeps track of messages and saves them to a string for sabnzbd post-processing logging functions.

        message: The string to log (unicode)
        level: The log level to use (optional)
        """
#        logger.log(message, level)
        self.log += message + '\n'

    def _run_pre_scripts(self, nzb_name, nzb_folder, seriesmetadata):
        """
        Executes any pre scripts defined in the config.

        ep_obj: The object to use when calling the pre script
        """
        logger.fdebug("initiating pre script detection.")
        self._log("initiating pre script detection.")
        logger.fdebug("mylar.PRE_SCRIPTS : " + mylar.PRE_SCRIPTS)
        self._log("mylar.PRE_SCRIPTS : " + mylar.PRE_SCRIPTS)
#        for currentScriptName in mylar.PRE_SCRIPTS:
        with open(mylar.PRE_SCRIPTS, 'r') as f:
            first_line = f.readline()

        if mylar.PRE_SCRIPTS.endswith('.sh'):
            shell_cmd = re.sub('#!', '', first_line).strip()
            if shell_cmd == '' or shell_cmd is None:
                shell_cmd = '/bin/bash'
        else:
            #forces mylar to use the executable that it was run with to run the extra script.
            shell_cmd = sys.executable

        currentScriptName = shell_cmd + ' ' + str(mylar.PRE_SCRIPTS).decode("string_escape")
        logger.fdebug("pre script detected...enabling: " + str(currentScriptName))
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(currentScriptName, posix=False) + [str(nzb_name), str(nzb_folder), str(seriesmetadata)]
        logger.fdebug("cmd to be executed: " + str(script_cmd))
        self._log("cmd to be executed: " + str(script_cmd))

            # use subprocess to run the command and capture output
        logger.fdebug(u"Executing command " +str(script_cmd))
        logger.fdebug(u"Absolute path to script: " +script_cmd[0])
        try:
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
            out, err = p.communicate() #@UnusedVariable
            logger.fdebug(u"Script result: " + out)
            self._log(u"Script result: " + out)
        except OSError, e:
           logger.warn(u"Unable to run pre_script: " + str(script_cmd))
           self._log(u"Unable to run pre_script: " + str(script_cmd))

    def _run_extra_scripts(self, nzb_name, nzb_folder, filen, folderp, seriesmetadata):
        """
        Executes any extra scripts defined in the config.

        ep_obj: The object to use when calling the extra script
        """
        logger.fdebug("initiating extra script detection.")
        self._log("initiating extra script detection.")
        logger.fdebug("mylar.EXTRA_SCRIPTS : " + mylar.EXTRA_SCRIPTS)
        self._log("mylar.EXTRA_SCRIPTS : " + mylar.EXTRA_SCRIPTS)
#        for curScriptName in mylar.EXTRA_SCRIPTS:
        with open(mylar.EXTRA_SCRIPTS, 'r') as f:
            first_line = f.readline()

        if mylar.EXTRA_SCRIPTS.endswith('.sh'):
            shell_cmd = re.sub('#!', '', first_line)
            if shell_cmd == '' or shell_cmd is None:
                shell_cmd = '/bin/bash'
        else:
            #forces mylar to use the executable that it was run with to run the extra script.
            shell_cmd = sys.executable

        curScriptName = shell_cmd + ' ' + str(mylar.EXTRA_SCRIPTS).decode("string_escape")
        logger.fdebug("extra script detected...enabling: " + str(curScriptName))
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(curScriptName) + [str(nzb_name), str(nzb_folder), str(filen), str(folderp), str(seriesmetadata)]
        logger.fdebug("cmd to be executed: " + str(script_cmd))
        self._log("cmd to be executed: " + str(script_cmd))

            # use subprocess to run the command and capture output
        logger.fdebug(u"Executing command " +str(script_cmd))
        logger.fdebug(u"Absolute path to script: " +script_cmd[0])
        try:
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
            out, err = p.communicate() #@UnusedVariable
            logger.fdebug(u"Script result: " + out)
            self._log(u"Script result: " + out)
        except OSError, e:
            logger.warn(u"Unable to run extra_script: " + str(script_cmd))
            self._log(u"Unable to run extra_script: " + str(script_cmd))


    def duplicate_process(self, dupeinfo):
            #path to move 'should' be the entire path to the given file
            path_to_move = dupeinfo[0]['to_dupe']
            file_to_move = os.path.split(path_to_move)[1]

            if dupeinfo[0]['action'] == 'dupe_src':
                logger.info('[DUPLICATE-CLEANUP] New File will be post-processed. Moving duplicate [' + path_to_move + '] to Duplicate Dump Folder for manual intervention.')
            else:
                logger.info('[DUPLICATE-CLEANUP] New File will not be post-processed. Moving duplicate [' + path_to_move + '] to Duplicate Dump Folder for manual intervention.')

            #check to make sure duplicate_dump directory exists:
            checkdirectory = filechecker.validateAndCreateDirectory(mylar.DUPLICATE_DUMP, True, module='[DUPLICATE-CLEANUP]')

            #this gets tricky depending on if it's the new filename or the existing filename, and whether or not 'copy' or 'move' has been selected.
            try:
                shutil.move(path_to_move, os.path.join(mylar.DUPLICATE_DUMP, file_to_move))
            except (OSError, IOError):
                logger.warn('[DUPLICATE-CLEANUP] Failed to move ' + path_to_move + ' ... to ... ' + os.path.join(mylar.DUPLICATE_DUMP, file_to_move))
                return False

            logger.warn('[DUPLICATE-CLEANUP] Successfully moved ' + path_to_move + ' ... to ... ' + os.path.join(mylar.DUPLICATE_DUMP, file_to_move))
            return True

    def Process(self):
            module = self.module
            self._log("nzb name: " + self.nzb_name)
            self._log("nzb folder: " + self.nzb_folder)
            logger.fdebug(module + ' nzb name: ' + self.nzb_name)
            logger.fdebug(module + ' nzb folder: ' + self.nzb_folder)
            if mylar.USE_SABNZBD==0:
                logger.fdebug(module + ' Not using SABnzbd')
            elif mylar.USE_SABNZBD != 0 and self.nzb_name == 'Manual Run':
                logger.fdebug(module + ' Not using SABnzbd : Manual Run')
            else:
                # if the SAB Directory option is enabled, let's use that folder name and append the jobname.
                if mylar.SAB_DIRECTORY is not None and mylar.SAB_DIRECTORY is not 'None' and len(mylar.SAB_DIRECTORY) > 4:
                    self.nzb_folder = os.path.join(mylar.SAB_DIRECTORY, self.nzb_name).encode(mylar.SYS_ENCODING)
                    logger.fdebug(module + ' SABnzbd Download folder option enabled. Directory set to : ' + self.nzb_folder)

      # -- start. not used.
                #query SAB to find out if Replace Spaces enabled / not as well as Replace Decimals
                #http://localhost:8080/sabnzbd/api?mode=set_config&section=misc&keyword=dirscan_speed&value=5
                #querysab = str(mylar.SAB_HOST) + "/api?mode=get_config&section=misc&output=xml&apikey=" + str(mylar.SAB_APIKEY)
                #logger.info("querysab_string:" + str(querysab))
                #file = urllib2.urlopen(querysab)
                #data = file.read()
                #file.close()
                #dom = parseString(data)

                #try:
                #    sabreps = dom.getElementsByTagName('replace_spaces')[0].firstChild.wholeText
                #except:
                #    errorm = dom.getElementsByTagName('error')[0].firstChild.wholeText
                #    logger.error(u"Error detected attempting to retrieve SAB data : " + errorm)
                #    return
                #sabrepd = dom.getElementsByTagName('replace_dots')[0].firstChild.wholeText
                #logger.fdebug("SAB Replace Spaces: " + str(sabreps))
                #logger.fdebug("SAB Replace Dots: " + str(sabrepd))
         # -- end. not used.

            if mylar.USE_NZBGET==1:
                if self.nzb_name != 'Manual Run':
                    logger.fdebug(module + ' Using NZBGET')
                logger.fdebug(module + ' NZB name as passed from NZBGet: ' + self.nzb_name)
                # if the NZBGet Directory option is enabled, let's use that folder name and append the jobname.
                if self.nzb_name == 'Manual Run':
                    logger.fdebug(module + ' Manual Run Post-Processing enabled.')
                elif mylar.NZBGET_DIRECTORY is not None and mylar.NZBGET_DIRECTORY is not 'None' and len(mylar.NZBGET_DIRECTORY) > 4:
                    self.nzb_folder = os.path.join(mylar.NZBGET_DIRECTORY, self.nzb_name).encode(mylar.SYS_ENCODING)
                    logger.fdebug(module + ' NZBGET Download folder option enabled. Directory set to : ' + self.nzb_folder)
            myDB = db.DBConnection()

            if self.nzb_name == 'Manual Run':
                logger.fdebug (module + ' Manual Run initiated')
                #Manual postprocessing on a folder.
                #use the nzb_folder to determine every file
                #walk the dir,
                #once a series name and issue are matched,
                #write the series/issue/filename to a tuple
                #when all done, iterate over the tuple until completion...
                comicseries = myDB.select("SELECT * FROM comics")
                manual_list = []
                if comicseries is None:
                    logger.error(module + ' No Series in Watchlist - checking against Story Arcs (just in case). If I do not find anything, maybe you should be running Import?')
                else:
                    watchvals = []
                    for wv in comicseries:

                        wv_comicname = wv['ComicName']
                        wv_comicpublisher = wv['ComicPublisher']
                        wv_alternatesearch = wv['AlternateSearch']
                        wv_comicid = wv['ComicID']

                        wv_seriesyear = wv['ComicYear']
                        wv_comicversion = wv['ComicVersion']
                        wv_publisher = wv['ComicPublisher']
                        wv_total = wv['Total']
                        if mylar.FOLDER_SCAN_LOG_VERBOSE:
                            logger.fdebug('Checking ' + wv['ComicName'] + ' [' + str(wv['ComicYear']) + '] -- ' + str(wv['ComicID']))

                        #force it to use the Publication Date of the latest issue instead of the Latest Date (which could be anything)
                        latestdate = myDB.select('SELECT IssueDate from issues WHERE ComicID=? order by ReleaseDate DESC', [wv['ComicID']])
                        if latestdate:
                            tmplatestdate = latestdate[0][0]
                            if tmplatestdate[:4] != wv['LatestDate'][:4]:
                                if tmplatestdate[:4] > wv['LatestDate'][:4]:
                                    latestdate = tmplatestdate
                                else:
                                    latestdate = wv['LatestDate']
                            else:
                                latestdate = tmplatestdate
                        else:
                            latestdate = wv['LatestDate']

                        if latestdate == '0000-00-00' or latestdate == 'None' or latestdate is None:
                            logger.fdebug('Forcing a refresh of series: ' + wv_comicname + ' as it appears to have incomplete issue dates.')
                            updater.dbUpdate([wv_comicid])
                            logger.fdebug('Refresh complete for ' + wv_comicname + '. Rechecking issue dates for completion.')
                            latestdate = myDB.select('SELECT IssueDate from issues WHERE ComicID=? order by ReleaseDate DESC', [wv['ComicID']])
                            if latestdate:
                                tmplatestdate = latestdate[0][0]
                                if tmplatestdate[:4] != wv['LatestDate'][:4]:
                                    if tmplatestdate[:4] > wv['LatestDate'][:4]:
                                        latestdate = tmplatestdate
                                    else:
                                        latestdate = wv['LatestDate']
                                else:
                                    latestdate = tmplatestdate
                            else:
                                latestdate = wv['LatestDate']

                            logger.fdebug('Latest Date (after forced refresh) set to :' + str(latestdate))

                            if latestdate == '0000-00-00' or latestdate == 'None' or latestdate is None:
                                logger.fdebug('Unable to properly attain the Latest Date for series: ' + wv_comicname + '. Cannot check against this series for post-processing.')
                                continue 

                        watchvals.append({"ComicName":       wv_comicname,
                                          "ComicPublisher":  wv_comicpublisher,
                                          "AlternateSearch": wv_alternatesearch,
                                          "ComicID":         wv_comicid,
                                          "WatchValues": {"SeriesYear":   wv_seriesyear,
                                                           "LatestDate":   latestdate,
                                                           "ComicVersion": wv_comicversion,
                                                           "Publisher":    wv_publisher,
                                                           "Total":        wv_total,
                                                           "ComicID":      wv_comicid,
                                                           "IsArc":        False}
                                         })

                    ccnt=0
                    nm=0
                    for cs in watchvals:
                        watchmatch = filechecker.listFiles(self.nzb_folder, cs['ComicName'], cs['ComicPublisher'], cs['AlternateSearch'], manual=cs['WatchValues'])
                        if watchmatch['comiccount'] == 0: # is None:
                            nm+=1
                            continue
                        else:
                            fn = 0
                            fccnt = int(watchmatch['comiccount'])
                            if len(watchmatch) == 1: continue
                            while (fn < fccnt):
                                try:
                                    tmpfc = watchmatch['comiclist'][fn]
                                except IndexError, KeyError:
                                    break
                                temploc= tmpfc['JusttheDigits'].replace('_', ' ')
                                temploc = re.sub('[\#\']', '', temploc)

                                if 'annual' in temploc.lower():
                                    biannchk = re.sub('-', '', temploc.lower()).strip()
                                    if 'biannual' in biannchk:
                                        logger.fdebug(module + ' Bi-Annual detected.')
                                        fcdigit = helpers.issuedigits(re.sub('biannual', '', str(biannchk)).strip())
                                    else:
                                        fcdigit = helpers.issuedigits(re.sub('annual', '', str(temploc.lower())).strip())
                                        logger.fdebug(module + ' Annual detected [' + str(fcdigit) +']. ComicID assigned as ' + str(cs['ComicID']))
                                    annchk = "yes"
                                    issuechk = myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=?", [cs['ComicID'], fcdigit]).fetchone()
                                else:
                                    fcdigit = helpers.issuedigits(temploc)
                                    issuechk = myDB.selectone("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [cs['ComicID'], fcdigit]).fetchone()

                                if issuechk is None:
                                    logger.fdebug(module + ' No corresponding issue # found for ' + str(cs['ComicID']))
                                else:
                                    datematch = "True"
                                    if len(watchmatch) >= 1 and tmpfc['ComicYear'] is not None:
                                        #if the # of matches is more than 1, we need to make sure we get the right series
                                        #compare the ReleaseDate for the issue, to the found issue date in the filename.
                                        #if ReleaseDate doesn't exist, use IssueDate
                                        #if no issue date was found, then ignore.
                                        issyr = None
                                        #logger.fdebug('issuedate:' + str(issuechk['IssueDate']))
                                        #logger.fdebug('issuechk: ' + str(issuechk['IssueDate'][5:7]))

                                        #logger.info('ReleaseDate: ' + str(issuechk['ReleaseDate']))
                                        #logger.info('IssueDate: ' + str(issuechk['IssueDate']))
                                        if issuechk['ReleaseDate'] is not None and issuechk['ReleaseDate'] != '0000-00-00':
                                            monthval = issuechk['ReleaseDate']
                                            if int(issuechk['ReleaseDate'][:4]) < int(tmpfc['ComicYear']):
                                                logger.fdebug(module + ' ' + str(issuechk['ReleaseDate']) + ' is before the issue year of ' + str(tmpfc['ComicYear']) + ' that was discovered in the filename')
                                                datematch = "False"

                                        else:
                                            monthval = issuechk['IssueDate']
                                            if int(issuechk['IssueDate'][:4]) < int(tmpfc['ComicYear']):
                                                logger.fdebug(module + ' ' + str(issuechk['IssueDate']) + ' is before the issue year ' + str(tmpfc['ComicYear']) + ' that was discovered in the filename')
                                                datematch = "False"

                                        if int(monthval[5:7]) == 11 or int(monthval[5:7]) == 12:
                                            issyr = int(monthval[:4]) + 1
                                            logger.fdebug(module + ' IssueYear (issyr) is ' + str(issyr))
                                        elif int(monthval[5:7]) == 1 or int(monthval[5:7]) == 2 or int(monthval[5:7]) == 3:
                                            issyr = int(monthval[:4]) - 1



                                        if datematch == "False" and issyr is not None:
                                            logger.fdebug(module + ' ' + str(issyr) + ' comparing to ' + str(tmpfc['ComicYear']) + ' : rechecking by month-check versus year.')
                                            datematch = "True"
                                            if int(issyr) != int(tmpfc['ComicYear']):
                                                logger.fdebug(module + '[.:FAIL:.] Issue is before the modified issue year of ' + str(issyr))
                                                datematch = "False"

                                    else:
                                        logger.info(module + ' Found matching issue # ' + str(fcdigit) + ' for ComicID: ' + str(cs['ComicID']) + ' / IssueID: ' + str(issuechk['IssueID']))

                                    if datematch == "True":
                                        manual_list.append({"ComicLocation":   tmpfc['ComicLocation'],
                                                            "ComicID":         cs['ComicID'],
                                                            "IssueID":         issuechk['IssueID'],
                                                            "IssueNumber":     issuechk['Issue_Number'],
                                                            "ComicName":       cs['ComicName']})
                                    else:
                                        logger.fdebug(module + ' Incorrect series - not populating..continuing post-processing')
                                    #ccnt+=1

                                fn+=1
                    logger.fdebug(module + ' There are ' + str(len(manual_list)) + ' files found that match on your watchlist, ' + str(nm) + ' do not match anything and will be ignored.')

                #we should setup for manual post-processing of story-arc issues here
                arc_series = myDB.select("SELECT * FROM readinglist order by ComicName") # by StoryArcID")
                manual_arclist = []
                if arc_series is None:
                    logger.error(module + ' No Story Arcs in Watchlist - aborting Manual Post Processing. Maybe you should be running Import?')
                    return
                else:
                    arcvals = []
                    for av in arc_series:
                        arcvals.append({"ComicName":       av['ComicName'],
                                        "ArcValues":       {"StoryArc":        av['StoryArc'],
                                                            "StoryArcID":      av['StoryArcID'],
                                                            "IssueArcID":      av['IssueArcID'],
                                                            "ComicName":       av['ComicName'],
                                                            "ComicPublisher":  av['IssuePublisher'],
                                                            "IssueID":         av['IssueID'],
                                                            "IssueNumber":     av['IssueNumber'],
                                                            "IssueYear":       av['IssueYear'],   #for some reason this is empty 
                                                            "ReadingOrder":    av['ReadingOrder'],
                                                            "IssueDate":       av['IssueDate'],
                                                            "Status":          av['Status'],
                                                            "Location":        av['Location']},
                                        "WatchValues":     {"SeriesYear":   av['SeriesYear'],
                                                            "LatestDate":   av['IssueDate'],
                                                            "ComicVersion": 'v' + str(av['SeriesYear']),
                                                            "Publisher":    av['IssuePublisher'],
                                                            "Total":        av['TotalIssues'],   # this will return the total issues in the arc (not needed for this)
                                                            "ComicID":      av['ComicID'],
                                                            "IsArc":        True}
                                        })

                    ccnt=0
                    nm=0
                    from collections import defaultdict
                    res = defaultdict(list)
                    for acv in arcvals:
                        res[acv['ComicName']].append({"ArcValues":     acv['ArcValues'],
                                                      "WatchValues":   acv['WatchValues']})

                    for k,v in res.items():
                        i = 0
                        while i < len(v):
                            #k is ComicName
                            #v is ArcValues and WatchValues
                            if k is None or k == 'None':
                                pass
                            else:
                                arcmatch = filechecker.listFiles(self.nzb_folder, k, v[i]['ArcValues']['ComicPublisher'], manual=v[i]['WatchValues'])
                                if arcmatch['comiccount'] == 0:
                                    pass
                                else:
                                    fn = 0
                                    fccnt = int(arcmatch['comiccount'])
                                    if len(arcmatch) == 1: break
                                    while (fn < fccnt):
                                        try:
                                            tmpfc = arcmatch['comiclist'][fn]
                                        except IndexError, KeyError:
                                            break
                                        temploc= tmpfc['JusttheDigits'].replace('_', ' ')
                                        temploc = re.sub('[\#\']', '', temploc)

                                        if 'annual' in temploc.lower():
                                            biannchk = re.sub('-', '', temploc.lower()).strip()
                                            if 'biannual' in biannchk:
                                                logger.fdebug(module + ' Bi-Annual detected.')
                                                fcdigit = helpers.issuedigits(re.sub('biannual', '', str(biannchk)).strip())
                                            else:
                                                logger.fdebug(module + ' Annual detected.')
                                                fcdigit = helpers.issuedigits(re.sub('annual', '', str(temploc.lower())).strip())
                                            annchk = "yes"
                                            issuechk = myDB.selectone("SELECT * from readinglist WHERE ComicID=? AND Int_IssueNumber=?", [v[i]['WatchValues']['ComicID'], fcdigit]).fetchone()
                                        else:
                                            fcdigit = helpers.issuedigits(temploc)
                                            issuechk = myDB.selectone("SELECT * from readinglist WHERE ComicID=? AND Int_IssueNumber=?", [v[i]['WatchValues']['ComicID'], fcdigit]).fetchone()

                                        if issuechk is None:
                                            logger.fdebug(module + ' No corresponding issue # found for ' + str(v[i]['WatchValues']['ComicID']))
                                        else:
                                            datematch = "True"
                                            if len(arcmatch) >= 1 and tmpfc['ComicYear'] is not None:
                                                #if the # of matches is more than 1, we need to make sure we get the right series
                                                #compare the ReleaseDate for the issue, to the found issue date in the filename.
                                                #if ReleaseDate doesn't exist, use IssueDate
                                                #if no issue date was found, then ignore.
                                                issyr = None
                                                logger.fdebug('issuedate:' + str(issuechk['IssueDate']))
                                                logger.fdebug('issuechk: ' + str(issuechk['IssueDate'][5:7]))

                                                logger.info('ReleaseDate: ' + str(issuechk['StoreDate']))
                                                logger.info('IssueDate: ' + str(issuechk['IssueDate']))
                                                if issuechk['StoreDate'] is not None and issuechk['StoreDate'] != '0000-00-00':
                                                    monthval = issuechk['StoreDate']
                                                    if int(issuechk['StoreDate'][:4]) < int(tmpfc['ComicYear']):
                                                        logger.fdebug(module + ' ' + str(issuechk['StoreDate']) + ' is before the issue year of ' + str(tmpfc['ComicYear']) + ' that was discovered in the filename')
                                                        datematch = "False"
   
                                                else:
                                                    monthval = issuechk['IssueDate']
                                                    if int(issuechk['IssueDate'][:4]) < int(tmpfc['ComicYear']):
                                                        logger.fdebug(module + ' ' + str(issuechk['IssueDate']) + ' is before the issue year ' + str(tmpfc['ComicYear']) + ' that was discovered in the filename')
                                                        datematch = "False"

                                                if int(monthval[5:7]) == 11 or int(monthval[5:7]) == 12:
                                                    issyr = int(monthval[:4]) + 1
                                                    logger.fdebug(module + ' IssueYear (issyr) is ' + str(issyr))
                                                elif int(monthval[5:7]) == 1 or int(monthval[5:7]) == 2 or int(monthval[5:7]) == 3:
                                                    issyr = int(monthval[:4]) - 1

                                                if datematch == "False" and issyr is not None:
                                                    logger.fdebug(module + ' ' + str(issyr) + ' comparing to ' + str(tmpfc['ComicYear']) + ' : rechecking by month-check versus year.')
                                                    datematch = "True"
                                                    if int(issyr) != int(tmpfc['ComicYear']):
                                                        logger.fdebug(module + '[.:FAIL:.] Issue is before the modified issue year of ' + str(issyr))
                                                        datematch = "False"

                                            else:
                                                logger.info(module + ' Found matching issue # ' + str(fcdigit) + ' for ComicID: ' + str(v[i]['WatchValues']['ComicID']) + ' / IssueID: ' + str(issuechk['IssueID']))

                                            if datematch == "True" and helpers.issuedigits(temploc) == helpers.issuedigits(v[i]['ArcValues']['IssueNumber']):
                                                passit = False
                                                if len(manual_list) > 0:
                                                    if any([ v[i]['ArcValues']['IssueID'] == x['IssueID'] for x in manual_list ]):
                                                        logger.info('[STORY-ARC POST-PROCESSING] IssueID ' + str(v[i]['ArcValues']['IssueID']) + ' exists in your watchlist. Bypassing Story-Arc post-processing performed later.')
                                                        #add in the storyarcid into the manual list so it will perform story-arc functions after normal manual PP is finished.
                                                        for a in manual_list:
                                                            if a['IssueID'] == v[i]['ArcValues']['IssueID']:
                                                                a['IssueArcID'] = v[i]['ArcValues']['IssueArcID']
                                                                break
                                                        passit = True
                                                if passit == False:
                                                    logger.info('[' + k + ' #' + str(issuechk['IssueNumber']) + '] MATCH: ' + tmpfc['ComicLocation'] + ' / ' + str(issuechk['IssueID']) + ' / ' + str(v[i]['ArcValues']['IssueID']))
                                                    manual_arclist.append({"ComicLocation":   tmpfc['ComicLocation'],
                                                                        "ComicID":         v[i]['WatchValues']['ComicID'],
                                                                        "IssueID":         v[i]['ArcValues']['IssueID'],
                                                                        "IssueNumber":     v[i]['ArcValues']['IssueNumber'],
                                                                        "StoryArc":        v[i]['ArcValues']['StoryArc'],
                                                                        "IssueArcID":      v[i]['ArcValues']['IssueArcID'],
                                                                        "ReadingOrder":    v[i]['ArcValues']['ReadingOrder'],
                                                                        "ComicName":       k})
                                            else:
                                                logger.fdebug(module + ' Incorrect series - not populating..continuing post-processing')
                                        fn+=1
                            i+=1

                    if len(manual_arclist) > 0:
                        logger.info('[STORY-ARC MANUAL POST-PROCESSING] I have found ' + str(len(manual_arclist)) + ' issues that belong to Story Arcs. Flinging them into the correct directories.')
                        for ml in manual_arclist:
                            issueid = ml['IssueID']
                            ofilename = ml['ComicLocation']
                            logger.info('[STORY-ARC POST-PROCESSING] Enabled for ' + ml['StoryArc'])
                            arcdir = helpers.filesafe(ml['StoryArc'])
                            if mylar.REPLACE_SPACES:
                               arcdir = arcdir.replace(' ', mylar.REPLACE_CHAR)

                            if mylar.STORYARCDIR:
                                storyarcd = os.path.join(mylar.DESTINATION_DIR, "StoryArcs", arcdir)
                                logger.fdebug(module + ' Story Arc Directory set to : ' + storyarcd)
                                grdst = storyarcd
                            else:
                                logger.fdebug(module + ' Story Arc Directory set to : ' + mylar.GRABBAG_DIR)
                                storyarcd = os.path.join(mylar.DESTINATION_DIR, mylar.GRABBAG_DIR)
                                grdst = storyarcd

                            #tag the meta.
                            if mylar.ENABLE_META:
                                logger.info('[STORY-ARC POST-PROCESSING] Metatagging enabled - proceeding...')
                                try:
                                    import cmtagmylar
                                    metaresponse = cmtagmylar.run(self.nzb_folder, issueid=issueid, filename=ofilename)
                                except ImportError:
                                    logger.warn(module + ' comictaggerlib not found on system. Ensure the ENTIRE lib directory is located within mylar/lib/comictaggerlib/')
                                    metaresponse = "fail"

                                if metaresponse == "fail":
                                    logger.fdebug(module + ' Unable to write metadata successfully - check mylar.log file. Attempting to continue without metatagging...')
                                elif metaresponse == "unrar error":
                                    logger.error(module + ' This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and retrying it.')
                                    continue
                                    #launch failed download handling here.
                                elif metaresponse.startswith('file not found'):
                                    filename_in_error = os.path.split(metaresponse, '||')[1]
                                    self._log("The file cannot be found in the location provided for metatagging to be used [" + filename_in_error + "]. Please verify it exists, and re-run if necessary. Attempting to continue without metatagging...")
                                    logger.error(module + ' The file cannot be found in the location provided for metatagging to be used [' + filename_in_error + ']. Please verify it exists, and re-run if necessary. Attempting to continue without metatagging...')
                                else:
                                    odir = os.path.split(metaresponse)[0]
                                    ofilename = os.path.split(metaresponse)[1]
                                    ext = os.path.splitext(metaresponse)[1]
                                    logger.info(module + ' Sucessfully wrote metadata to .cbz (' + ofilename + ') - Continuing..')
                                    self._log('Sucessfully wrote metadata to .cbz (' + ofilename + ') - proceeding...')

                            checkdirectory = filechecker.validateAndCreateDirectory(grdst, True, module=module)
                            if not checkdirectory:
                                logger.warn(module + ' Error trying to validate/create directory. Aborting this process at this time.')
                                self.valreturn.append({"self.log": self.log,
                                                       "mode": 'stop'})
                                return self.queue.put(self.valreturn)


                            dfilename = ofilename

                            #send to renamer here if valid.
                            if mylar.RENAME_FILES:
                                renamed_file = helpers.rename_param(ml['ComicID'], ml['ComicName'], ml['IssueNumber'], ofilename, issueid=ml['IssueID'], arc=ml['StoryArc'])
                                if renamed_file:
                                    dfilename = renamed_file['nfilename']
                                    logger.fdebug(module + ' Renaming file to conform to configuration: ' + ofilename)
                   
                            #if from a StoryArc, check to see if we're appending the ReadingOrder to the filename
                            if mylar.READ2FILENAME:
                                                              
                                logger.fdebug(module + ' readingorder#: ' + str(ml['ReadingOrder']))
                                if int(ml['ReadingOrder']) < 10: readord = "00" + str(ml['ReadingOrder'])
                                elif int(ml['ReadingOrder']) >= 10 and int(ml['ReadingOrder']) <= 99: readord = "0" + str(ml['ReadingOrder'])
                                else: readord = str(ml['ReadingOrder'])
                                dfilename = str(readord) + "-" + dfilename
                            else:
                                dfilename = dfilename

                            grab_dst = os.path.join(grdst, dfilename)

                            logger.fdebug(module + ' Destination Path : ' + grab_dst)
                            grab_src = os.path.join(self.nzb_folder, ofilename)
                            logger.fdebug(module + ' Source Path : ' + grab_src)

                            logger.info(module + ' ' + mylar.FILE_OPTS + 'ing ' + str(ofilename) + ' into directory : ' + str(grab_dst))
                            try:
                                self.fileop(grab_src, grab_dst)
                            except (OSError, IOError):
                                logger.warn(module + ' Failed to ' + mylar.FILE_OPTS + ' directory - check directories and manually re-run.')
                                return

                            #tidyup old path
                            try:
                                pass
                                #shutil.rmtree(self.nzb_folder)
                            except (OSError, IOError):
                                logger.warn(module + ' Failed to remove temporary directory - check directory and manually re-run.')
                                return

                            logger.fdebug(module + ' Removed temporary directory : ' + self.nzb_folder)

                            #delete entry from nzblog table
                            #if it was downloaded via mylar from the storyarc section, it will have an 'S' in the nzblog
                            #if it was downloaded outside of mylar and/or not from the storyarc section, it will be a normal issueid in the nzblog
                            #IssArcID = 'S' + str(ml['IssueArcID'])
                            myDB.action('DELETE from nzblog WHERE IssueID=? AND SARC=?', ['S' + str(ml['IssueArcID']),ml['StoryArc']])
                            myDB.action('DELETE from nzblog WHERE IssueID=? AND SARC=?', [ml['IssueArcID'],ml['StoryArc']])
                            
                            logger.fdebug(module + ' IssueArcID: ' + str(ml['IssueArcID']))
                            ctrlVal = {"IssueArcID":  ml['IssueArcID']}
                            newVal = {"Status":       "Downloaded",
                                      "Location":     grab_dst}
                            logger.fdebug('writing: ' + str(newVal) + ' -- ' + str(ctrlVal))
                            myDB.upsert("readinglist", newVal, ctrlVal)

                            logger.fdebug(module + ' [' + ml['StoryArc'] + '] Post-Processing completed for: ' + grab_dst)

            else:
                nzbname = self.nzb_name
                #remove extensions from nzb_name if they somehow got through (Experimental most likely)
                extensions = ('.cbr', '.cbz')

                if nzbname.lower().endswith(extensions):
                    fd, ext = os.path.splitext(nzbname)
                    self._log("Removed extension from nzb: " + ext)
                    nzbname = re.sub(str(ext), '', str(nzbname))

                #replace spaces
                # let's change all space to decimals for simplicity
                logger.fdebug('[NZBNAME]: ' + nzbname)
                #gotta replace & or escape it
                nzbname = re.sub("\&", 'and', nzbname)
                nzbname = re.sub('[\,\:\?\'\+]', '', nzbname)
                nzbname = re.sub('[\(\)]', ' ', nzbname)
                logger.fdebug('[NZBNAME] nzbname (remove chars): ' + nzbname)
                nzbname = re.sub('.cbr', '', nzbname).strip()
                nzbname = re.sub('.cbz', '', nzbname).strip()
                nzbname = re.sub('[\.\_]', ' ', nzbname).strip()
                nzbname = re.sub('\s+', ' ', nzbname)  #make sure we remove the extra spaces.
                logger.fdebug('[NZBNAME] nzbname (remove extensions, double spaces, convert underscores to spaces): ' + nzbname)
                nzbname = re.sub('\s', '.', nzbname)

                logger.fdebug(module + ' After conversions, nzbname is : ' + str(nzbname))
#                if mylar.USE_NZBGET==1:
#                    nzbname=self.nzb_name
                self._log("nzbname: " + str(nzbname))

                nzbiss = myDB.selectone("SELECT * from nzblog WHERE nzbname=? or altnzbname=?", [nzbname, nzbname]).fetchone()

                if nzbiss is None:
                    self._log("Failure - could not initially locate nzbfile in my database to rename.")
                    logger.fdebug(module + ' Failure - could not locate nzbfile initially')
                    # if failed on spaces, change it all to decimals and try again.
                    nzbname = re.sub('[\(\)]', '', str(nzbname))
                    self._log("trying again with this nzbname: " + str(nzbname))
                    logger.fdebug(module + ' Trying to locate nzbfile again with nzbname of : ' + str(nzbname))
                    nzbiss = myDB.selectone("SELECT * from nzblog WHERE nzbname=? or altnzbname=?", [nzbname, nzbname]).fetchone()
                    if nzbiss is None:
                        logger.error(module + ' Unable to locate downloaded file to rename. PostProcessing aborted.')
                        self._log('Unable to locate downloaded file to rename. PostProcessing aborted.')
                        self.valreturn.append({"self.log": self.log,
                                               "mode": 'stop'})
                        return self.queue.put(self.valreturn)
                    else:
                        self._log("I corrected and found the nzb as : " + str(nzbname))
                        logger.fdebug(module + ' Auto-corrected and found the nzb as : ' + str(nzbname))
                        issueid = nzbiss['IssueID']
                else:
                    issueid = nzbiss['IssueID']
                    logger.fdebug(module + ' Issueid: ' + str(issueid))
                    sarc = nzbiss['SARC']
                    #use issueid to get publisher, series, year, issue number

                annchk = "no"
#                if 'annual' in nzbname.lower():
#                    logger.info(module + ' Annual detected.')
#                    annchk = "yes"
#                    issuenzb = myDB.selectone("SELECT * from annuals WHERE IssueID=? AND ComicName NOT NULL", [issueid]).fetchone()
#                else:
#                    issuenzb = myDB.selectone("SELECT * from issues WHERE IssueID=? AND ComicName NOT NULL", [issueid]).fetchone()

                issuenzb = myDB.selectone("SELECT * from issues WHERE IssueID=? AND ComicName NOT NULL", [issueid]).fetchone()
                if issuenzb is None:
                    logger.info(module + ' Could not detect as a standard issue - checking against annuals.')
                    issuenzb = myDB.selectone("SELECT * from annuals WHERE IssueID=? AND ComicName NOT NULL", [issueid]).fetchone()
                    if issuenzb is None:
                        logger.info(module + ' issuenzb not found.')
                        #if it's non-numeric, it contains a 'G' at the beginning indicating it's a multi-volume
                        #using GCD data. Set sandwich to 1 so it will bypass and continue post-processing.
                        if 'S' in issueid:
                            sandwich = issueid
                        elif 'G' in issueid or '-' in issueid:
                            sandwich = 1
                        elif issueid == '1':
                            logger.info(module + ' [ONE-OFF POST-PROCESSING] One-off download detected. Post-processing as a non-watchlist item.')
                            sandwich = None #arbitrarily set it to None just to force one-off downloading below.
                        else:
                            logger.error(module + ' Download not detected as being initiated via Mylar. Unable to continue post-processing said item. Either download the issue with Mylar, or use manual post-processing to post-process.')
                            self.valreturn.append({"self.log": self.log,
                                                   "mode": 'stop'})
                            return self.queue.put(self.valreturn)                            
                    else:
                        logger.info(module + ' Successfully located issue as an annual. Continuing.')
                        annchk = "yes"

                if issuenzb is not None:
                    logger.info(module + ' issuenzb found.')
                    if helpers.is_number(issueid):
                        sandwich = int(issuenzb['IssueID'])
#                else:
#                    logger.info(module + ' issuenzb not found.')
#                    #if it's non-numeric, it contains a 'G' at the beginning indicating it's a multi-volume
#                    #using GCD data. Set sandwich to 1 so it will bypass and continue post-processing.
#                    if 'S' in issueid:
#                        sandwich = issueid
#                    elif 'G' in issueid or '-' in issueid:
#                        sandwich = 1
                if sandwich is not None and helpers.is_number(sandwich):
                    if sandwich < 900000:
                        # if sandwich is less than 900000 it's a normal watchlist download. Bypass.
                        pass
                else:
                    if issuenzb is None or 'S' in sandwich or int(sandwich) >= 900000:
                        # this has no issueID, therefore it's a one-off or a manual post-proc.
                        # At this point, let's just drop it into the Comic Location folder and forget about it..
                        if sandwich is not None and 'S' in sandwich:
                            self._log("One-off STORYARC mode enabled for Post-Processing for " + str(sarc))
                            logger.info(module + ' One-off STORYARC mode enabled for Post-Processing for ' + str(sarc))
                            arcdir = helpers.filesafe(sarc)
                            if mylar.REPLACE_SPACES:
                               arcdir = arcdir.replace(' ', mylar.REPLACE_CHAR)
                            if mylar.STORYARCDIR:
                                storyarcd = os.path.join(mylar.DESTINATION_DIR, "StoryArcs", arcdir)
                                self._log("StoryArc Directory set to : " + storyarcd)
                                logger.info(module + ' Story Arc Directory set to : ' + storyarcd)
                            else:
                                self._log("Grab-Bag Directory set to : " + mylar.GRABBAG_DIR)
                                logger.info(module + ' Story Arc Directory set to : ' + mylar.GRABBAG_DIR)

                        else:
                            self._log("One-off mode enabled for Post-Processing. All I'm doing is moving the file untouched into the Grab-bag directory.")
                            logger.info(module + ' One-off mode enabled for Post-Processing. Will move into Grab-bag directory.')
                            self._log("Grab-Bag Directory set to : " + mylar.GRABBAG_DIR)

                        odir = None
                        ofilename = None
                        for root, dirnames, filenames in os.walk(self.nzb_folder):
                            for filename in filenames:
                                if filename.lower().endswith(extensions):
                                    odir = root
                                    ofilename = filename
                                    path, ext = os.path.splitext(ofilename)

                        if ofilename is None:
                            logger.error(module + ' Unable to post-process file as it is not in a valid cbr/cbz format. PostProcessing aborted.')
                            self._log('Unable to locate downloaded file to rename. PostProcessing aborted.')
                            self.valreturn.append({"self.log": self.log,
                                                   "mode": 'stop'})
                            return self.queue.put(self.valreturn)

                        if odir is None:
                            odir = self.nzb_folder

                        if sandwich is not None and 'S' in sandwich:
                            issuearcid = re.sub('S', '', issueid)
                            logger.fdebug(module + ' issuearcid:' + str(issuearcid))
                            arcdata = myDB.selectone("SELECT * FROM readinglist WHERE IssueArcID=?", [issuearcid]).fetchone()

                            issueid = arcdata['IssueID']
                        #tag the meta.
                        if mylar.ENABLE_META:
                            self._log("Metatagging enabled - proceeding...")
                            try:
                                import cmtagmylar
                                metaresponse = cmtagmylar.run(self.nzb_folder, issueid=issueid, filename=ofilename)
                            except ImportError:
                                logger.warn(module + ' comictaggerlib not found on system. Ensure the ENTIRE lib directory is located within mylar/lib/comictaggerlib/')
                                metaresponse = "fail"

                            if metaresponse == "fail":
                                logger.fdebug(module + ' Unable to write metadata successfully - check mylar.log file. Attempting to continue without metatagging...')
                            elif metaresponse == "unrar error":
                                logger.error(module + ' This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and retrying it.')
                                #launch failed download handling here.
                            elif metaresponse.startswith('file not found'):
                                filename_in_error = os.path.split(metaresponse, '||')[1]
                                self._log("The file cannot be found in the location provided for metatagging [" + filename_in_error + "]. Please verify it exists, and re-run if necessary. Attempting to continue without metatagging...")
                                logger.error(module + ' The file cannot be found in the location provided for metagging [' + filename_in_error + ']. Please verify it exists, and re-run if necessary. Attempting to continue without metatagging...')
                            else:
                                odir = os.path.split(metaresponse)[0]
                                ofilename = os.path.split(metaresponse)[1]
                                ext = os.path.splitext(metaresponse)[1]
                                logger.info(module + ' Sucessfully wrote metadata to .cbz (' + ofilename + ') - Continuing..')
                                self._log('Sucessfully wrote metadata to .cbz (' + ofilename + ') - proceeding...')

                        if sandwich is not None and 'S' in sandwich:
                            if mylar.STORYARCDIR:
                                grdst = storyarcd
                            else:
                                grdst = mylar.DESTINATION_DIR
                        else:
                            if mylar.GRABBAG_DIR:
                                grdst = mylar.GRABBAG_DIR
                            else:
                                grdst = mylar.DESTINATION_DIR

                        checkdirectory = filechecker.validateAndCreateDirectory(grdst, True, module=module)
                        if not checkdirectory:
                            logger.warn(module + ' Error trying to validate/create directory. Aborting this process at this time.')
                            self.valreturn.append({"self.log": self.log,
                                                   "mode": 'stop'})
                            return self.queue.put(self.valreturn)

                        if sandwich is not None and 'S' in sandwich:
                            #if from a StoryArc, check to see if we're appending the ReadingOrder to the filename
                            if mylar.READ2FILENAME:
                                logger.fdebug(module + ' readingorder#: ' + str(arcdata['ReadingOrder']))
                                if int(arcdata['ReadingOrder']) < 10: readord = "00" + str(arcdata['ReadingOrder'])
                                elif int(arcdata['ReadingOrder']) >= 10 and int(arcdata['ReadingOrder']) <= 99: readord = "0" + str(arcdata['ReadingOrder'])
                                else: readord = str(arcdata['ReadingOrder'])
                                dfilename = str(readord) + "-" + ofilename
                            else:
                                dfilename = ofilename
                            grab_dst = os.path.join(grdst, dfilename)
                        else:
                            grab_dst = os.path.join(grdst, ofilename)

                        self._log("Destination Path : " + grab_dst)

                        logger.info(module + ' Destination Path : ' + grab_dst)
                        grab_src = os.path.join(self.nzb_folder, ofilename)
                        self._log("Source Path : " + grab_src)
                        logger.info(module + ' Source Path : ' + grab_src)

                        logger.info(module + ' ' + mylar.FILE_OPTS + 'ing ' + str(ofilename) + ' into directory : ' + str(grab_dst))

                        try:
                            self.fileop(grab_src, grab_dst)
                        except (OSError, IOError):
                            self._log("Failed to " + mylar.FILE_OPTS + " directory - check directories and manually re-run.")
                            logger.debug(module + ' Failed to ' + mylar.FILE_OPTS + ' directory - check directories and manually re-run.')
                            return

                        #tidyup old path
                        if mylar.FILE_OPTS == 'move':
                            try:
                                shutil.rmtree(self.nzb_folder)
                            except (OSError, IOError):
                                self._log("Failed to remove temporary directory.")
                                logger.debug(module + ' Failed to remove temporary directory - check directory and manually re-run.')
                                return

                            logger.debug(module + ' Removed temporary directory : ' + self.nzb_folder)
                            self._log("Removed temporary directory : " + self.nzb_folder)
                        #delete entry from nzblog table
                        myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])

                        if sandwich is not None and 'S' in sandwich:
                            #issuearcid = re.sub('S', '', issueid)
                            logger.info(module + ' IssueArcID is : ' + str(issuearcid))
                            ctrlVal = {"IssueArcID":  issuearcid}
                            newVal = {"Status":       "Downloaded",
                                      "Location":     grab_dst}
                            logger.info('writing: ' + str(newVal) + ' -- ' + str(ctrlVal))
                            myDB.upsert("readinglist", newVal, ctrlVal)
                            logger.info('wrote.')
                            logger.info(module + ' Updated status to Downloaded')

                            logger.info(module + ' Post-Processing completed for: [' + sarc + '] ' + grab_dst)
                            self._log(u"Post Processing SUCCESSFUL! ")

                        self.valreturn.append({"self.log": self.log,
                                               "mode": 'stop'})
                        return self.queue.put(self.valreturn)


            if self.nzb_name == 'Manual Run':
                #loop through the hits here.
                if len(manual_list) == 0 and len(manual_arclist) == 0:
                    logger.info(module + ' No matches for Manual Run ... exiting.')
                    return
                elif len(manual_arclist) > 0 and len(manual_list) == 0:
                    logger.info(module + ' Manual post-processing completed for ' + str(len(manual_arclist)) + ' story-arc issues.')
                    return
                elif len(manual_arclist) > 0:
                    logger.info(module + ' Manual post-processing completed for ' + str(len(manual_arclist)) + ' story-arc issues.')
  
                i = 0
                for ml in manual_list:
                    i+=1
                    comicid = ml['ComicID']
                    issueid = ml['IssueID']
                    issuenumOG = ml['IssueNumber']
                    #check to see if file is still being written to.
                    while True:
                        waiting = False
                        try:
                            ctime = max(os.path.getctime(ml['ComicLocation']), os.path.getmtime(ml['ComicLocation']))
                            if time.time() > ctime > time.time() - 15:
                                time.sleep(max(time.time() - ctime, 0))
                                waiting = True
                            else:
                                break
                        except:
                            #file is no longer present in location / can't be accessed.
                            break

                    dupthis = helpers.duplicate_filecheck(ml['ComicLocation'], ComicID=comicid, IssueID=issueid)
                    if dupthis[0]['action'] == 'dupe_src' or dupthis[0]['action'] == 'dupe_file':
                        #check if duplicate dump folder is enabled and if so move duplicate file in there for manual intervention.
                        #'dupe_file' - do not write new file as existing file is better quality
                        #'dupe_src' - write new file, as existing file is a lesser quality (dupe)
                        if mylar.DUPLICATE_DUMP:
                            dupchkit = self.duplicate_process(dupthis)
                            if dupchkit == False:
                                logger.warn('Unable to move duplicate file - skipping post-processing of this file.')
                                continue


                    if dupthis[0]['action'] == "write" or dupthis[0]['action'] == 'dupe_src':
                        stat = ' [' + str(i) + '/' + str(len(manual_list)) + ']'
                        self.Process_next(comicid, issueid, issuenumOG, ml, stat)
                        dupthis = None

                logger.info(module + ' Manual post-processing completed for ' + str(i) + ' issues.')
                return
            else:
                comicid = issuenzb['ComicID']
                issuenumOG = issuenzb['Issue_Number']
                #the self.nzb_folder should contain only the existing filename
                dupthis = helpers.duplicate_filecheck(self.nzb_folder, ComicID=comicid, IssueID=issueid)
                if dupthis[0]['action'] == 'dupe_src' or dupthis[0]['action'] == 'dupe_file':
                    #check if duplicate dump folder is enabled and if so move duplicate file in there for manual intervention.
                    #'dupe_file' - do not write new file as existing file is better quality
                    #'dupe_src' - write new file, as existing file is a lesser quality (dupe)
                    if mylar.DUPLICATE_DUMP:
                        dupchkit = self.duplicate_process(dupthis)
                        if dupchkit == False:
                            logger.warn('Unable to move duplicate file - skipping post-processing of this file.')
                            self.valreturn.append({"self.log": self.log,
                                                   "mode": 'stop',
                                                   "issueid": issueid,
                                                   "comicid": comicid})

                            return self.queue.put(self.valreturn)
 
                if dupthis[0]['action'] == "write" or dupthis[0]['action'] == 'dupe_src':
                    return self.Process_next(comicid, issueid, issuenumOG)
                else:
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop',
                                           "issueid": issueid,
                                           "comicid": comicid})

                    return self.queue.put(self.valreturn)

    def Process_next(self, comicid, issueid, issuenumOG, ml=None, stat=None):
            if stat is None: stat = ' [1/1]'
            module = self.module
            annchk = "no"
            extensions = ('.cbr', '.cbz')
            snatchedtorrent = False
            myDB = db.DBConnection()
            comicnzb = myDB.selectone("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
            issuenzb = myDB.selectone("SELECT * from issues WHERE issueid=? AND comicid=? AND ComicName NOT NULL", [issueid, comicid]).fetchone()
            if ml is not None and mylar.SNATCHEDTORRENT_NOTIFY:
                snatchnzb = myDB.selectone("SELECT * from snatched WHERE IssueID=? AND ComicID=? AND (provider=? OR provider=?) AND Status='Snatched'", [issueid, comicid, 'KAT', '32P']).fetchone()
                if snatchnzb is None:
                    logger.fdebug(module + ' Was not downloaded with Mylar and the usage of torrents. Disabling torrent manual post-processing completion notification.')
                else:
                    logger.fdebug(module + ' Was downloaded from ' + snatchnzb['Provider'] + '. Enabling torrent manual post-processing completion notification.')
                    snatchedtorrent = True

            if issuenzb is None:
                issuenzb = myDB.selectone("SELECT * from annuals WHERE issueid=? and comicid=?", [issueid, comicid]).fetchone()
                annchk = "yes"
            if annchk == "no":
                logger.info(module + stat + ' Starting Post-Processing for ' + issuenzb['ComicName'] + ' issue: ' + issuenzb['Issue_Number'])
            else:
                logger.info(module + stat + ' Starting Post-Processing for ' + issuenzb['ReleaseComicName'] + ' issue: ' + issuenzb['Issue_Number'])
            logger.fdebug(module + ' issueid: ' + str(issueid))
            logger.fdebug(module + ' issuenumOG: ' + issuenumOG)
            #issueno = str(issuenum).split('.')[0]
            #new CV API - removed all decimals...here we go AGAIN!
            issuenum = issuenzb['Issue_Number']
            issue_except = 'None'

            if 'au' in issuenum.lower() and issuenum[:1].isdigit():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = ' AU'
            elif 'ai' in issuenum.lower() and issuenum[:1].isdigit():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = ' AI'
            elif 'inh' in issuenum.lower() and issuenum[:1].isdigit():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = '.INH'
            elif 'now' in issuenum.lower() and issuenum[:1].isdigit():
                if '!' in issuenum: issuenum = re.sub('\!', '', issuenum)
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = '.NOW'

            elif u'\xbd' in issuenum:
                issuenum = '0.5'
            elif u'\xbc' in issuenum:
                issuenum = '0.25'
            elif u'\xbe' in issuenum:
                issuenum = '0.75'
            elif u'\u221e' in issuenum:
                #issnum = utf-8 will encode the infinity symbol without any help
                issuenum = 'infinity'
            else:
                issue_exceptions = ['A',
                                    'B',
                                    'C',
                                    'X',
                                    'O']

                exceptionmatch = [x for x in issue_exceptions if x.lower() in issuenum.lower()]
                if exceptionmatch:
                    logger.fdebug('[FILECHECKER] We matched on : ' + str(exceptionmatch))
                    for x in exceptionmatch:
                        issuenum = re.sub("[^0-9]", "", issuenum)
                        issue_except = x

            if '.' in issuenum:
                iss_find = issuenum.find('.')
                iss_b4dec = issuenum[:iss_find]
                if iss_b4dec == '':
                    iss_b4dec = '0'
                iss_decval = issuenum[iss_find +1:]
                if iss_decval.endswith('.'): iss_decval = iss_decval[:-1]
                if int(iss_decval) == 0:
                    iss = iss_b4dec
                    issdec = int(iss_decval)
                    issueno = str(iss)
                    self._log("Issue Number: " + str(issueno))
                    logger.fdebug(module + 'Issue Number: ' + str(issueno))
                else:
                    if len(iss_decval) == 1:
                        iss = iss_b4dec + "." + iss_decval
                        issdec = int(iss_decval) * 10
                    else:
                        iss = iss_b4dec + "." + iss_decval.rstrip('0')
                        issdec = int(iss_decval.rstrip('0')) * 10
                    issueno = iss_b4dec
                    self._log("Issue Number: " + str(iss))
                    logger.fdebug(module + ' Issue Number: ' + str(iss))
            else:
                iss = issuenum
                issueno = iss

            # issue zero-suppression here
            if mylar.ZERO_LEVEL == "0":
                zeroadd = ""
            else:
                if mylar.ZERO_LEVEL_N  == "none": zeroadd = ""
                elif mylar.ZERO_LEVEL_N == "0x": zeroadd = "0"
                elif mylar.ZERO_LEVEL_N == "00x": zeroadd = "00"

            logger.fdebug(module + ' Zero Suppression set to : ' + str(mylar.ZERO_LEVEL_N))

            prettycomiss = None

            if issueno.isalpha():
                logger.fdebug('issue detected as an alpha.')
                prettycomiss = str(issueno)
            else:
                try:
                    x = float(issueno)
                    #validity check
                    if x < 0:
                        logger.info('I\'ve encountered a negative issue #: ' + str(issueno) + '. Trying to accomodate.')
                        prettycomiss = '-' + str(zeroadd) + str(issueno[1:])
                    elif x >= 0:
                        pass
                    else:
                        raise ValueError
                except ValueError, e:
                    logger.warn('Unable to properly determine issue number [' + str(issueno) + '] - you should probably log this on github for help.')
                    return

            if prettycomiss is None and len(str(issueno)) > 0:
                #if int(issueno) < 0:
                #    self._log("issue detected is a negative")
                #    prettycomiss = '-' + str(zeroadd) + str(abs(issueno))
                if int(issueno) < 10:
                    logger.fdebug('issue detected less than 10')
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                            prettycomiss = str(zeroadd) + str(iss)
                        else:
                            prettycomiss = str(zeroadd) + str(int(issueno))
                    else:
                        prettycomiss = str(zeroadd) + str(iss)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('Zero level supplement set to ' + str(mylar.ZERO_LEVEL_N) + '. Issue will be set as : ' + str(prettycomiss))
                elif int(issueno) >= 10 and int(issueno) < 100:
                    logger.fdebug('issue detected greater than 10, but less than 100')
                    if mylar.ZERO_LEVEL_N == "none":
                        zeroadd = ""
                    else:
                        zeroadd = "0"
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                            prettycomiss = str(zeroadd) + str(iss)
                        else:
                           prettycomiss = str(zeroadd) + str(int(issueno))
                    else:
                        prettycomiss = str(zeroadd) + str(iss)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('Zero level supplement set to ' + str(mylar.ZERO_LEVEL_N) + '.Issue will be set as : ' + str(prettycomiss))
                else:
                    logger.fdebug('issue detected greater than 100')
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                    prettycomiss = str(issueno)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('Zero level supplement set to ' + str(mylar.ZERO_LEVEL_N) + '. Issue will be set as : ' + str(prettycomiss))

            elif len(str(issueno)) == 0:
                prettycomiss = str(issueno)
                logger.fdebug('issue length error - cannot determine length. Defaulting to None:  ' + str(prettycomiss))

#start outdated?
#            if str(len(issueno)) > 1:
#                if issueno.isalpha():
#                    self._log('issue detected as an alpha.')
#                    prettycomiss = str(issueno)

#                elif int(issueno) < 0:
#                    self._log("issue detected is a negative")
#                    prettycomiss = '-' + str(zeroadd) + str(abs(issueno))
#                elif int(issueno) < 10:
#                    self._log("issue detected less than 10")
#                    if '.' in iss:
#                        if int(iss_decval) > 0:
#                            issueno = str(iss)
#                            prettycomiss = str(zeroadd) + str(iss)
#                        else:
#                            prettycomiss = str(zeroadd) + str(int(issueno))
#                    else:
#                        prettycomiss = str(zeroadd) + str(iss)
#                    if issue_except != 'None':
#                        prettycomiss = str(prettycomiss) + issue_except
#                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss))
#                elif int(issueno) >= 10 and int(issueno) < 100:
#                    self._log("issue detected greater than 10, but less than 100")
#                    if mylar.ZERO_LEVEL_N == "none":
#                        zeroadd = ""
#                    else:
#                        zeroadd = "0"
#                    if '.' in iss:
#                        if int(iss_decval) > 0:
#                            issueno = str(iss)
#                            prettycomiss = str(zeroadd) + str(iss)
#                        else:
#                           prettycomiss = str(zeroadd) + str(int(issueno))
#                    else:
#                        prettycomiss = str(zeroadd) + str(iss)
#                    if issue_except != 'None':
#                        prettycomiss = str(prettycomiss) + issue_except
#                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ".Issue will be set as : " + str(prettycomiss))
#                else:
#                    self._log("issue detected greater than 100")
#                    if '.' in iss:
#                        if int(iss_decval) > 0:
#                            issueno = str(iss)
#                    prettycomiss = str(issueno)
#                    if issue_except != 'None':
#                        prettycomiss = str(prettycomiss) + issue_except
#                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss))
#            else:
#                prettycomiss = str(issueno)
#                self._log("issue length error - cannot determine length. Defaulting to None:  " + str(prettycomiss))
#--end outdated?

            if annchk == "yes":
                self._log("Annual detected.")
            logger.fdebug(module + ' Pretty Comic Issue is : ' + str(prettycomiss))
            issueyear = issuenzb['IssueDate'][:4]
            self._log("Issue Year: " + str(issueyear))
            logger.fdebug(module + ' Issue Year : ' + str(issueyear))
            month = issuenzb['IssueDate'][5:7].replace('-', '').strip()
            month_name = helpers.fullmonth(month)
#            comicnzb= myDB.action("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
            publisher = comicnzb['ComicPublisher']
            self._log("Publisher: " + publisher)
            logger.fdebug(module + ' Publisher: ' + publisher)
            #we need to un-unicode this to make sure we can write the filenames properly for spec.chars
            series = comicnzb['ComicName'].encode('ascii', 'ignore').strip()
            self._log("Series: " + series)
            logger.fdebug(module + ' Series: ' + str(series))
            if comicnzb['AlternateFileName'] is None or comicnzb['AlternateFileName'] == 'None':
                seriesfilename = series
            else:
                seriesfilename = comicnzb['AlternateFileName'].encode('ascii', 'ignore').strip()
                logger.fdebug(module + ' Alternate File Naming has been enabled for this series. Will rename series to : ' + seriesfilename)
            seriesyear = comicnzb['ComicYear']
            self._log("Year: " + seriesyear)
            logger.fdebug(module + ' Year: '  + str(seriesyear))
            comlocation = comicnzb['ComicLocation']
            self._log("Comic Location: " + comlocation)
            logger.fdebug(module + ' Comic Location: ' + str(comlocation))
            comversion = comicnzb['ComicVersion']
            self._log("Comic Version: " + str(comversion))
            logger.fdebug(module + ' Comic Version: ' + str(comversion))
            if comversion is None:
                comversion = 'None'
            #if comversion is None, remove it so it doesn't populate with 'None'
            if comversion == 'None':
                chunk_f_f = re.sub('\$VolumeN', '', mylar.FILE_FORMAT)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                self._log("No version # found for series - tag will not be available for renaming.")
                logger.fdebug(module + ' No version # found for series, removing from filename')
                logger.fdebug(module + ' New format is now: ' + str(chunk_file_format))
            else:
                chunk_file_format = mylar.FILE_FORMAT

            if annchk == "no":
                chunk_f_f = re.sub('\$Annual', '', chunk_file_format)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug(module + ' Not an annual - removing from filename parameters')
                logger.fdebug(module + ' New format: ' + str(chunk_file_format))

            else:
                logger.fdebug(module + ' Chunk_file_format is: ' + str(chunk_file_format))
                if '$Annual' not in chunk_file_format:
                #if it's an annual, but $Annual isn't specified in file_format, we need to
                #force it in there, by default in the format of $Annual $Issue
                    prettycomiss = "Annual " + str(prettycomiss)
                    logger.fdebug(module + ' prettycomiss: ' + str(prettycomiss))


            ofilename = None

            #if it's a Manual Run, use the ml['ComicLocation'] for the exact filename.
            if ml is None:
                ofilename = None
                for root, dirnames, filenames in os.walk(self.nzb_folder, followlinks=True):
                    for filename in filenames:
                        if filename.lower().endswith(extensions):
                            odir = root
                            logger.fdebug(module + ' odir (root): ' + odir)
                            ofilename = filename
                            logger.fdebug(module + ' ofilename: ' + ofilename)
                            path, ext = os.path.splitext(ofilename)
                try:
                    if odir is None:
                        logger.fdebug(module + ' No root folder set.')
                        odir = self.nzb_folder
                except:
                    logger.error(module + ' unable to set root folder. Forcing it due to some error above most likely.')
                    odir = self.nzb_folder

                if ofilename is None:
                    self._log("Unable to locate a valid cbr/cbz file. Aborting post-processing for this filename.")
                    logger.error(module + ' unable to locate a valid cbr/cbz file. Aborting post-processing for this filename.')
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)
                logger.fdebug(module + ' odir: ' + odir)
                logger.fdebug(module + ' ofilename: ' + ofilename)


            #if meta-tagging is not enabled, we need to declare the check as being fail
            #if meta-tagging is enabled, it gets changed just below to a default of pass
            pcheck = "fail"

            #tag the meta.
            if mylar.ENABLE_META:

                self._log("Metatagging enabled - proceeding...")
                logger.fdebug(module + ' Metatagging enabled - proceeding...')
                pcheck = "pass"
                try:
                    import cmtagmylar
                    if ml is None:
                        pcheck = cmtagmylar.run(self.nzb_folder, issueid=issueid, comversion=comversion, filename=os.path.join(odir, ofilename))
                    else:
                        pcheck = cmtagmylar.run(self.nzb_folder, issueid=issueid, comversion=comversion, manual="yes", filename=ml['ComicLocation'])

                except ImportError:
                    logger.fdebug(module + ' comictaggerlib not found on system. Ensure the ENTIRE lib directory is located within mylar/lib/comictaggerlib/')
                    logger.fdebug(module + ' continuing with PostProcessing, but I am not using metadata.')
                    pcheck = "fail"

                if pcheck == "fail":
                    self._log("Unable to write metadata successfully - check mylar.log file. Attempting to continue without tagging...")
                    logger.fdebug(module + ' Unable to write metadata successfully - check mylar.log file. Attempting to continue without tagging...')
                    #we need to set this to the cbz file since not doing it will result in nothing getting moved.
                    #not sure how to do this atm
                elif pcheck == "unrar error":
                    self._log("This is a corrupt archive - whether CRC errors or it's incomplete. Marking as BAD, and retrying a different copy.")
                    logger.error(module + ' This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and retrying a different copy.')
                    self.valreturn.append({"self.log":    self.log,
                                           "mode":        'fail',
                                           "issueid":     issueid,
                                           "comicid":     comicid,
                                           "comicname":   comicnzb['ComicName'],
                                           "issuenumber": issuenzb['Issue_Number'],
                                           "annchk":      annchk})
                    return self.queue.put(self.valreturn)
                elif pcheck.startswith('file not found'):
                    filename_in_error = os.path.split(pcheck, '||')[1]
                    self._log("The file cannot be found in the location provided [" + filename_in_error + "]. Please verify it exists, and re-run if necessary. Aborting.")
                    logger.error(module + ' The file cannot be found in the location provided [' + filename_in_error + ']. Please verify it exists, and re-run if necessary. Aborting')
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)

                else:
                    #need to set the filename source as the new name of the file returned from comictagger.
                    odir = os.path.split(pcheck)[0]
                    ofilename = os.path.split(pcheck)[1]
                    ext = os.path.splitext(ofilename)[1]
                    self._log("Sucessfully wrote metadata to .cbz - Continuing..")
                    logger.info(module + ' Sucessfully wrote metadata to .cbz (' + ofilename + ') - Continuing..')
                    #if this is successful, and we're copying to dst then set the file op to move this cbz so we 
                    #don't leave a cbr/cbz in the origianl directory.
                    #self.fileop = shutil.move
            #Run Pre-script

            if mylar.ENABLE_PRE_SCRIPTS:
                nzbn = self.nzb_name #original nzb name
                nzbf = self.nzb_folder #original nzb folder
                #name, comicyear, comicid , issueid, issueyear, issue, publisher
                #create the dic and send it.
                seriesmeta = []
                seriesmetadata = {}
                seriesmeta.append({
                            'name':                 series,
                            'comicyear':            seriesyear,
                            'comicid':              comicid,
                            'issueid':              issueid,
                            'issueyear':            issueyear,
                            'issue':                issuenum,
                            'publisher':            publisher
                            })
                seriesmetadata['seriesmeta'] = seriesmeta
                self._run_pre_scripts(nzbn, nzbf, seriesmetadata)

        #rename file and move to new path
        #nfilename = series + " " + issueno + " (" + seriesyear + ")"

            file_values = {'$Series':    seriesfilename,
                           '$Issue':     prettycomiss,
                           '$Year':      issueyear,
                           '$series':    series.lower(),
                           '$Publisher': publisher,
                           '$publisher': publisher.lower(),
                           '$VolumeY':   'V' + str(seriesyear),
                           '$VolumeN':   comversion,
                           '$monthname': month_name,
                           '$month':     month,
                           '$Annual':    'Annual'
                          }


            #if it's a Manual Run, use the ml['ComicLocation'] for the exact filename.
#            if ml is None:
#                ofilename = None
#                for root, dirnames, filenames in os.walk(self.nzb_folder, followlinks=True):
#                    for filename in filenames:
#                        if filename.lower().endswith(extensions):
#                            odir = root
#                            logger.fdebug(module + ' odir (root): ' + odir)
#                            ofilename = filename
#                            logger.fdebug(module + ' ofilename: ' + ofilename)
#                            path, ext = os.path.splitext(ofilename)
#                try:
#                    if odir is None:
#                        logger.fdebug(module + ' No root folder set.')
#                        odir = self.nzb_folder
#                except:
#                    logger.error(module + ' unable to set root folder. Forcing it due to some error above most likely.')
#                    odir = self.nzb_folde
#
#                if ofilename is None:
#                    self._log("Unable to locate a valid cbr/cbz file. Aborting post-processing for this filename.")
#                    logger.error(module + ' unable to locate a valid cbr/cbz file. Aborting post-processing for this filename.')
#                    self.valreturn.append({"self.log": self.log,
#                                           "mode": 'stop'})
#                    return self.queue.put(self.valreturn)
#                logger.fdebug(module + ' odir: ' + odir)
#                logger.fdebug(module + ' ofilename: ' + ofilename)

            if ml:
#            else:
                if pcheck == "fail":
                    odir, ofilename = os.path.split(ml['ComicLocation'])
                elif pcheck:
                    #odir, ofilename already set. Carry it through.
                    pass
                else:
                    odir = os.path.split(ml['ComicLocation'])[0]
                logger.fdebug(module + ' ofilename:' + ofilename)
                #ofilename = otofilename
                if any([ofilename == odir, ofilename == odir[:-1], ofilename == '']):
                    self._log("There was a problem deciphering the filename/directory - please verify that the filename : [" + ofilename + "] exists in location [" + odir + "]. Aborting.")
                    logger.error(module + ' There was a problem deciphering the filename/directory - please verify that the filename : [' + ofilename + '] exists in location [' + odir + ']. Aborting.')
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)
                logger.fdebug(module + ' odir: ' + odir)
                logger.fdebug(module + ' ofilename: ' + ofilename)
                ext = os.path.splitext(ofilename)[1]
                logger.fdebug(module + ' ext:' + ext)

            if ofilename is None or ofilename == '':
                logger.error(module + ' Aborting PostProcessing - the filename does not exist in the location given. Make sure that ' + self.nzb_folder + ' exists and is the correct location.')
                self.valreturn.append({"self.log": self.log,
                                       "mode": 'stop'})
                return self.queue.put(self.valreturn)
            self._log("Original Filename: " + ofilename)
            self._log("Original Extension: " + ext)
            logger.fdebug(module + ' Original Filename: ' + ofilename)
            logger.fdebug(module + ' Original Extension: ' + ext)

            if mylar.FILE_FORMAT == '' or not mylar.RENAME_FILES:
                self._log("Rename Files isn't enabled...keeping original filename.")
                logger.fdebug(module + ' Rename Files is not enabled - keeping original filename.')
                #check if extension is in nzb_name - will screw up otherwise
                if ofilename.lower().endswith(extensions):
                    nfilename = ofilename[:-4]
                else:
                    nfilename = ofilename
            else:
                nfilename = helpers.replace_all(chunk_file_format, file_values)
                if mylar.REPLACE_SPACES:
                    #mylar.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                    nfilename = nfilename.replace(' ', mylar.REPLACE_CHAR)
            nfilename = re.sub('[\,\:\?]', '', nfilename)
            nfilename = re.sub('[\/]', '-', nfilename)
            self._log("New Filename: " + nfilename)
            logger.fdebug(module + ' New Filename: ' + str(nfilename))

            #src = os.path.join(self.nzb_folder, ofilename)
            src = os.path.join(odir, ofilename)
            checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True, module=module)
            if not checkdirectory:
                logger.warn(module + ' Error trying to validate/create directory. Aborting this process at this time.')
                self.valreturn.append({"self.log": self.log,
                                       "mode": 'stop'})
                return self.queue.put(self.valreturn)


            if mylar.LOWERCASE_FILENAMES:
                dst = os.path.join(comlocation, (nfilename + ext).lower())
            else:
                dst = os.path.join(comlocation, (nfilename + ext.lower()))
            self._log("Source:" + src)
            self._log("Destination:" +  dst)
            logger.fdebug(module + ' Source: ' + src)
            logger.fdebug(module + ' Destination: ' + dst)

            if ml is None:
                #downtype = for use with updater on history table to set status to 'Downloaded'
                downtype = 'True'
                #non-manual run moving/deleting...
                logger.fdebug(module + ' self.nzb_folder: ' + self.nzb_folder)
                logger.fdebug(module + ' odir: ' + odir)
                logger.fdebug(module + ' ofilename:' + ofilename)
                logger.fdebug(module + ' nfilename:' + nfilename + ext)
                if mylar.RENAME_FILES:
                    if str(ofilename) != str(nfilename + ext):
                        logger.fdebug(module + ' Renaming ' + os.path.join(odir, ofilename) + ' ..to.. ' + os.path.join(odir, nfilename + ext))
                        #if mylar.FILE_OPTS == 'move':
                        #    os.rename(os.path.join(odir, ofilename), os.path.join(odir, nfilename + ext))
                        # else:
                        #    self.fileop(os.path.join(odir, ofilename), os.path.join(odir, nfilename + ext))
                    else:
                        logger.fdebug(module + ' Filename is identical as original, not renaming.')

                #src = os.path.join(self.nzb_folder, str(nfilename + ext))
                src = os.path.join(odir, ofilename)
                try:
                    self.fileop(src, dst)
                except (OSError, IOError):
                    self._log("Failed to " + mylar.FILE_OPTS + " directory - check directories and manually re-run.")
                    self._log("Post-Processing ABORTED.")
                    logger.warn(module + ' Failed to ' + mylar.FILE_OPTS + ' directory : ' + src + ' to ' + dst + ' - check directory and manually re-run')
                    logger.warn(module + ' Post-Processing ABORTED')
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)

                #tidyup old path
                if mylar.FILE_OPTS == 'move':
                    try:
                        shutil.rmtree(self.nzb_folder)
                    except (OSError, IOError):
                        self._log("Failed to remove temporary directory - check directory and manually re-run.")
                        self._log("Post-Processing ABORTED.")
                        logger.warn(module + ' Failed to remove temporary directory : ' + self.nzb_folder)
                        logger.warn(module + ' Post-Processing ABORTED')
                        self.valreturn.append({"self.log": self.log,
                                               "mode": 'stop'})
                        return self.queue.put(self.valreturn)
                    self._log("Removed temporary directory : " + self.nzb_folder)
                    logger.fdebug(module + ' Removed temporary directory : ' + self.nzb_folder)
            else:
                #downtype = for use with updater on history table to set status to 'Post-Processed'
                downtype = 'PP'
                #Manual Run, this is the portion.
                src = os.path.join(odir, ofilename)
                if mylar.RENAME_FILES:
                    if str(ofilename) != str(nfilename + ext):
                        logger.fdebug(module + ' Renaming ' + os.path.join(odir, str(ofilename))) #' ..to.. ' + os.path.join(odir, self.nzb_folder, str(nfilename + ext)))
                        #os.rename(os.path.join(odir, str(ofilename)), os.path.join(odir, str(nfilename + ext)))
                        #src = os.path.join(odir, str(nfilename + ext))
                    else:
                        logger.fdebug(module + ' Filename is identical as original, not renaming.')

                logger.fdebug(module + ' odir src : ' + src)
                logger.fdebug(module + ' ' + mylar.FILE_OPTS + 'ing ' + src + ' ... to ... ' + dst)
                try:
                    self.fileop(src, dst)
                except (OSError, IOError):
                    logger.fdebug(module + ' Failed to ' + mylar.FILE_OPTS + ' directory - check directories and manually re-run.')
                    logger.fdebug(module + ' Post-Processing ABORTED.')

                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)
                logger.info(module + ' ' + mylar.FILE_OPTS + ' successful to : ' + dst)

                if mylar.FILE_OPTS == 'move':
                    #tidyup old path
                    try:
                        if os.path.isdir(odir) and odir != self.nzb_folder:
                            logger.fdebug(module + ' self.nzb_folder: ' + self.nzb_folder)
                            # check to see if the directory is empty or not.
                            if not os.listdir(odir):
                                logger.fdebug(module + ' Tidying up. Deleting folder : ' + odir)
                                shutil.rmtree(odir)
                            else:
                                raise OSError(module + ' ' + odir + ' not empty. Skipping removal of directory - this will either be caught in further post-processing or it will have to be removed manually.')
                        else:
                            raise OSError(module + ' ' + odir + ' unable to remove at this time.')
                    except (OSError, IOError):
                        logger.fdebug(module + ' Failed to remove temporary directory (' + odir + ') - Processing will continue, but manual removal is necessary')

            #Hopefully set permissions on downloaded file
            if mylar.OS_DETECT != 'windows':
                filechecker.setperms(dst.rstrip())
            else:
                try:
                    permission = int(mylar.CHMOD_FILE, 8)
                    os.umask(0)
                    os.chmod(dst.rstrip(), permission)
                except OSError:
                    logger.error(module + ' Failed to change file permissions. Ensure that the user running Mylar has proper permissions to change permissions in : ' + dst)
                    logger.fdebug(module + ' Continuing post-processing but unable to change file permissions in ' + dst)

            #let's reset the fileop to the original setting just in case it's a manual pp run
            if mylar.FILE_OPTS == 'copy':
                self.fileop = shutil.copy
            else:
                self.fileop = shutil.move

            #delete entry from nzblog table
            myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])

            #update snatched table to change status to Downloaded
            if annchk == "no":
                updater.foundsearch(comicid, issueid, down=downtype, module=module)
                dispiss = 'issue: ' + issuenumOG
            else:
                updater.foundsearch(comicid, issueid, mode='want_ann', down=downtype, module=module)
                if 'annual' not in series.lower():
                    dispiss = 'annual issue: ' + issuenumOG
                else:
                    dispiss = issuenumOG

            #force rescan of files
            updater.forceRescan(comicid, module=module)

            try:
                if ml['IssueArcID']:
                    logger.info('Watchlist Story Arc match detected.')
                    arcinfo = myDB.selectone('SELECT * FROM readinglist where IssueArcID=?', [ml['IssueArcID']]).fetchone()
                    if arcinfo is None:
                        logger.warn('Unable to locate IssueID within givin Story Arc. Ensure everything is up-to-date (refreshed) for the Arc.')
                    else:
                        arcdir = helpers.filesafe(arcinfo['StoryArc'])
                        if mylar.REPLACE_SPACES:
                           arcdir = arcdir.replace(' ', mylar.REPLACE_CHAR)

                        if mylar.STORYARCDIR:
                            storyarcd = os.path.join(mylar.DESTINATION_DIR, "StoryArcs", arcdir)
                            logger.fdebug(module + ' Story Arc Directory set to : ' + storyarcd)
                            grdst = storyarcd
                        else:
                            logger.fdebug(module + ' Story Arc Directory set to : ' + mylar.GRABBAG_DIR)
                            storyarcd = os.path.join(mylar.DESTINATION_DIR, mylar.GRABBAG_DIR)
                            grdst = mylar.DESTINATION_DIR

                        checkdirectory = filechecker.validateAndCreateDirectory(grdst, True, module=module)
                        if not checkdirectory:
                            logger.warn(module + ' Error trying to validate/create directory. Aborting this process at this time.')
                            self.valreturn.append({"self.log": self.log,
                                                   "mode": 'stop'})
                            return self.queue.put(self.valreturn)


                        if mylar.READ2FILENAME:

                            logger.fdebug(module + ' readingorder#: ' + str(arcinfo['ReadingOrder']))
                            if int(arcinfo['ReadingOrder']) < 10: readord = "00" + str(arcinfo['ReadingOrder'])
                            elif int(arcinfo['ReadingOrder']) >= 10 and int(arcinfo['ReadingOrder']) <= 99: readord = "0" + str(arcinfo['ReadingOrder'])
                            else: readord = str(arcinfo['ReadingOrder'])
                            dfilename = str(readord) + "-" + os.path.split(dst)[1]
                        else:
                            dfilename = os.path.split(dst)[1]

                        grab_dst = os.path.join(grdst, dfilename)

                        logger.fdebug(module + ' Destination Path : ' + grab_dst)
                        grab_src = dst
                        logger.fdebug(module + ' Source Path : ' + grab_src)                        
                        logger.info(module + ' Copying ' + str(dst) + ' into directory : ' + str(grab_dst))

                        try:
                            shutil.copy(grab_src, grab_dst)
                        except (OSError, IOError):
                            logger.warn(module + ' Failed to move directory - check directories and manually re-run.')
                            return

                        #delete entry from nzblog table in case it was forced via the Story Arc Page
                        IssArcID = 'S' + str(ml['IssueArcID'])
                        myDB.action('DELETE from nzblog WHERE IssueID=? AND SARC=?', [IssArcID,arcinfo['StoryArc']])

                        logger.fdebug(module + ' IssueArcID: ' + str(ml['IssueArcID']))
                        ctrlVal = {"IssueArcID":  ml['IssueArcID']}
                        newVal = {"Status":       "Downloaded",
                                  "Location":     grab_dst}
                        logger.fdebug('writing: ' + str(newVal) + ' -- ' + str(ctrlVal))
                        myDB.upsert("readinglist", newVal, ctrlVal)
                        logger.fdebug(module + ' [' + arcinfo['StoryArc'] + '] Post-Processing completed for: ' + grab_dst)

            except:
                pass

            if mylar.WEEKFOLDER or mylar.SEND2READ:
                #mylar.WEEKFOLDER = will *copy* the post-processed file to the weeklypull list folder for the given week.
                #mylar.SEND2READ = will add the post-processed file to the readinglits
                weeklypull.weekly_check(comicid, issuenum, file=str(nfilename +ext), path=dst, module=module, issueid=issueid)

            # retrieve/create the corresponding comic objects
            if mylar.ENABLE_EXTRA_SCRIPTS:
                folderp = str(dst) #folder location after move/rename
                nzbn = self.nzb_name #original nzb name
                filen = str(nfilename + ext) #new filename
                #name, comicyear, comicid , issueid, issueyear, issue, publisher
                #create the dic and send it.
                seriesmeta = []
                seriesmetadata = {}
                seriesmeta.append({
                            'name':                 series,
                            'comicyear':            seriesyear,
                            'comicid':              comicid,
                            'issueid':              issueid,
                            'issueyear':            issueyear,
                            'issue':                issuenum,
                            'publisher':            publisher
                            })
                seriesmetadata['seriesmeta'] = seriesmeta
                self._run_extra_scripts(nzbn, self.nzb_folder, filen, folderp, seriesmetadata)

            if ml is not None:
                #we only need to return self.log if it's a manual run and it's not a snatched torrent
                if snatchedtorrent:
                    #manual run + snatched torrent
                    pass
                else:
                    #manual run + not snatched torrent (or normal manual-run)
                    logger.info(module + ' Post-Processing completed for: ' + series + ' ' + dispiss)
                    self._log(u"Post Processing SUCCESSFUL! ")
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop',
                                           "issueid": issueid,
                                           "comicid": comicid})

                    return self.queue.put(self.valreturn)

            if annchk == "no":
                prline = series + '(' + issueyear + ') - issue #' + issuenumOG
            else:
                if 'annual' not in series.lower():
                    prline = series + ' Annual (' + issueyear + ') - issue #' + issuenumOG
                else:
                    prline = series + ' (' + issueyear + ') - issue #' + issuenumOG

            prline2 = 'Mylar has downloaded and post-processed: ' + prline

            if mylar.PROWL_ENABLED:
                pushmessage = prline
                prowl = notifiers.PROWL()
                prowl.notify(pushmessage, "Download and Postprocessing completed", module=module)

            if mylar.NMA_ENABLED:
                nma = notifiers.NMA()
                nma.notify(prline=prline, prline2=prline2, module=module)

            if mylar.PUSHOVER_ENABLED:
                pushover = notifiers.PUSHOVER()
                pushover.notify(prline, "Download and Post-Processing completed", module=module)

            if mylar.BOXCAR_ENABLED:
                boxcar = notifiers.BOXCAR()
                boxcar.notify(prline=prline, prline2=prline2, module=module)

            if mylar.PUSHBULLET_ENABLED:
                pushbullet = notifiers.PUSHBULLET()
                pushbullet.notify(prline=prline, prline2=prline2, module=module)

            logger.info(module + ' Post-Processing completed for: ' + series + ' ' + dispiss)
            self._log(u"Post Processing SUCCESSFUL! ")

            self.valreturn.append({"self.log": self.log,
                                   "mode": 'stop',
                                   "issueid": issueid,
                                   "comicid": comicid})

            return self.queue.put(self.valreturn)



class FolderCheck():

    def __init__(self):
        import Queue
        import PostProcessor, logger

        self.module = '[FOLDER-CHECK]'
        self.queue = Queue.Queue()

    def run(self):
        if mylar.IMPORTLOCK:
            logger.info('There is an import currently running. In order to ensure successful import - deferring this until the import is finished.')
            return
        #monitor a selected folder for 'snatched' files that haven't been processed
        #junk the queue as it's not needed for folder monitoring, but needed for post-processing to run without error.
        logger.info(self.module + ' Checking folder ' + mylar.CHECK_FOLDER + ' for newly snatched downloads')
        PostProcess = PostProcessor('Manual Run', mylar.CHECK_FOLDER, queue=self.queue)
        result = PostProcess.Process()
        logger.info(self.module + ' Finished checking for newly snatched downloads')

