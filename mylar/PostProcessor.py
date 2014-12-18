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
import sqlite3
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

#    IGNORED_FILESTRINGS = [ "" ]

    NZB_NAME = 1
    FOLDER_NAME = 2
    FILE_NAME = 3

    def __init__(self, nzb_name, nzb_folder, module=None, queue=None):
        """
        Creates a new post processor with the given file path and optionally an NZB name.

        file_path: The path to the file to be processed
        nzb_name: The name of the NZB which resulted in this file being downloaded (optional)
        """
        # absolute path to the folder that is being processed
        #self.folder_path = ek.ek(os.path.dirname, ek.ek(os.path.abspath, file_path))

        # full path to file
        #self.file_path = file_path

        # file name only
        #self.file_name = ek.ek(os.path.basename, file_path)

        # the name of the folder only
        #self.folder_name = ek.ek(os.path.basename, self.folder_path)

        # name of the NZB that resulted in this folder
        self.nzb_name = nzb_name
        self.nzb_folder = nzb_folder
        if module is not None:
            self.module = module + '[POST-PROCESSING]'
        else:
            self.module = '[POST-PROCESSING]'
        if queue: self.queue = queue
        #self.in_history = False
        #self.release_group = None
        #self.is_proper = False
        self.valreturn = []
        self.log = ''

    def _log(self, message, level=logger.message):  #level=logger.MESSAGE):
        """
        A wrapper for the internal logger which also keeps track of messages and saves them to a string for $

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
        self._log("initiating pre script detection.")
        self._log("mylar.PRE_SCRIPTS : " + mylar.PRE_SCRIPTS)
#        for currentScriptName in mylar.PRE_SCRIPTS:
        currentScriptName = str(mylar.PRE_SCRIPTS).decode("string_escape")
        self._log("pre script detected...enabling: " + str(currentScriptName))
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(currentScriptName, posix=False) + [str(nzb_name), str(nzb_folder), str(seriesmetadata)]
        self._log("cmd to be executed: " + str(script_cmd))

            # use subprocess to run the command and capture output
        self._log(u"Executing command "+str(script_cmd))
        self._log(u"Absolute path to script: "+script_cmd[0])
        try:
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
            out, err = p.communicate() #@UnusedVariable
            self._log(u"Script result: " + out)
        except OSError, e:
           self._log(u"Unable to run pre_script: " + str(script_cmd))

    def _run_extra_scripts(self, nzb_name, nzb_folder, filen, folderp, seriesmetadata):
        """
        Executes any extra scripts defined in the config.

        ep_obj: The object to use when calling the extra script
        """
        self._log("initiating extra script detection.")
        self._log("mylar.EXTRA_SCRIPTS : " + mylar.EXTRA_SCRIPTS)
#        for curScriptName in mylar.EXTRA_SCRIPTS:
        curScriptName = str(mylar.EXTRA_SCRIPTS).decode("string_escape")
        self._log("extra script detected...enabling: " + str(curScriptName))
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(curScriptName) + [str(nzb_name), str(nzb_folder), str(filen), str(folderp), str(seriesmetadata)]
        self._log("cmd to be executed: " + str(script_cmd))

            # use subprocess to run the command and capture output
        self._log(u"Executing command "+str(script_cmd))
        self._log(u"Absolute path to script: "+script_cmd[0])
        try:
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
            out, err = p.communicate() #@UnusedVariable
            self._log(u"Script result: " + out)
        except OSError, e:
            self._log(u"Unable to run extra_script: " + str(script_cmd))


    def Process(self):
            module = self.module           
            self._log("nzb name: " + str(self.nzb_name))
            self._log("nzb folder: " + str(self.nzb_folder))
            logger.fdebug(module + ' nzb name: ' + str(self.nzb_name))
            logger.fdebug(module + ' nzb folder: ' + str(self.nzb_folder))
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
                    logger.error(module + ' No Series in Watchlist - aborting Manual Post Processing. Maybe you should be running Import?')
                    return
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

                        #logger.fdebug('Checking ' + wv['ComicName'] + ' [' + str(wv['ComicYear']) + '] -- ' + str(wv['ComicID']))

                        #force it to use the Publication Date of the latest issue instead of the Latest Date (which could be anything)
                        latestdate = myDB.select('SELECT IssueDate from issues WHERE ComicID=? order by ReleaseDate DESC', [wv['ComicID']])
                        if latestdate:
                            latestdate = latestdate[0][0]
                        else:
                            latestdate = wv['LatestDate']

                        watchvals.append({"ComicName":       wv_comicname,
                                          "ComicPublisher":  wv_comicpublisher,
                                          "AlternateSearch": wv_alternatesearch,
                                          "ComicID":         wv_comicid,
                                          "WatchValues" : {"SeriesYear":   wv_seriesyear,
                                                           "LatestDate":   latestdate,
                                                           "ComicVersion": wv_comicversion,
                                                           "Publisher":    wv_publisher,
                                                           "Total":        wv_total,
                                                           "ComicID":      wv_comicid}
                                         })

                    ccnt=0
                    nm=0
                    for cs in watchvals:
                        watchmatch = filechecker.listFiles(self.nzb_folder,cs['ComicName'],cs['ComicPublisher'],cs['AlternateSearch'], manual=cs['WatchValues'])
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
                                except IndexError,KeyError:
                                    break
                                temploc= tmpfc['JusttheDigits'].replace('_', ' ')
                                temploc = re.sub('[\#\']', '', temploc)

                                if 'annual' in temploc.lower():
                                    biannchk = re.sub('-', '', temploc.lower()).strip()
                                    if 'biannual' in biannchk:
                                        logger.info(module + ' Bi-Annual detected.')
                                        fcdigit = helpers.issuedigits(re.sub('biannual', '', str(biannchk)).strip())
                                    else:
                                        logger.info(module + ' Annual detected.')
                                        fcdigit = helpers.issuedigits(re.sub('annual', '', str(temploc.lower())).strip())
                                    annchk = "yes"
                                    issuechk = myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=?", [cs['ComicID'],fcdigit]).fetchone()
                                else:
                                    fcdigit = helpers.issuedigits(temploc)
                                    issuechk = myDB.selectone("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [cs['ComicID'],fcdigit]).fetchone()

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
                

            else:
                nzbname = self.nzb_name
                #remove extensions from nzb_name if they somehow got through (Experimental most likely)
                extensions = ('.cbr', '.cbz')

                if nzbname.lower().endswith(extensions):
                    fd, ext = os.path.splitext(nzbname)
                    self._log("Removed extension from nzb: " + ext)
                    nzbname = re.sub(str(ext), '', str(nzbname))

                #replace spaces
                nzbname = re.sub(' ', '.', str(nzbname))
                nzbname = re.sub('[\,\:\?]', '', str(nzbname))
                nzbname = re.sub('[\&]', 'and', str(nzbname))

                logger.fdebug(module + ' After conversions, nzbname is : ' + str(nzbname))
#                if mylar.USE_NZBGET==1:
#                    nzbname=self.nzb_name
                self._log("nzbname: " + str(nzbname))
   
                nzbiss = myDB.selectone("SELECT * from nzblog WHERE nzbname=?", [nzbname]).fetchone()

                if nzbiss is None:
                    self._log("Failure - could not initially locate nzbfile in my database to rename.")
                    logger.fdebug(module + ' Failure - could not locate nzbfile initially')
                    # if failed on spaces, change it all to decimals and try again.
                    nzbname = re.sub('_', '.', str(nzbname))
                    self._log("trying again with this nzbname: " + str(nzbname))
                    logger.fdebug(module + ' Trying to locate nzbfile again with nzbname of : ' + str(nzbname))
                    nzbiss = myDB.selectone("SELECT * from nzblog WHERE nzbname=?", [nzbname]).fetchone()
                    if nzbiss is None:
                        logger.error(module + ' Unable to locate downloaded file to rename. PostProcessing aborted.')
                        self._log('Unable to locate downloaded file to rename. PostProcessing aborted.')
                        self.valreturn.append({"self.log" : self.log,
                                               "mode"     : 'stop'})
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
                if helpers.is_number(sandwich):
                    if sandwich < 900000:
                        # if sandwich is less than 900000 it's a normal watchlist download. Bypass.
                        pass
                else:
                    if issuenzb is None or 'S' in sandwich or int(sandwich) >= 900000:
                        # this has no issueID, therefore it's a one-off or a manual post-proc.
                        # At this point, let's just drop it into the Comic Location folder and forget about it..
                        if 'S' in sandwich:
                            self._log("One-off STORYARC mode enabled for Post-Processing for " + str(sarc))
                            logger.info(module + 'One-off STORYARC mode enabled for Post-Processing for ' + str(sarc))
                            if mylar.STORYARCDIR:
                                storyarcd = os.path.join(mylar.DESTINATION_DIR, "StoryArcs", sarc)
                                self._log("StoryArc Directory set to : " + storyarcd)
                            else:
                                self._log("Grab-Bag Directory set to : " + mylar.GRABBAG_DIR)
   
                        else:
                            self._log("One-off mode enabled for Post-Processing. All I'm doing is moving the file untouched into the Grab-bag directory.")
                            logger.info(module + ' One-off mode enabled for Post-Processing. Will move into Grab-bag directory.')
                            self._log("Grab-Bag Directory set to : " + mylar.GRABBAG_DIR)

                        odir = None
                        for root, dirnames, filenames in os.walk(self.nzb_folder):
                            for filename in filenames:
                                if filename.lower().endswith(extensions):
                                    odir = root
                                    ofilename = filename
                                    path, ext = os.path.splitext(ofilename)

                        if odir is None:
                            odir = self.nzb_folder     

                        issuearcid = re.sub('S', '', issueid)
                        logger.fdebug(module + ' issuearcid:' + str(issuearcid))
                        arcdata = myDB.selectone("SELECT * FROM readinglist WHERE IssueArcID=?",[issuearcid]).fetchone()

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
                                logger.fdebug(module + ' Unable to write metadata successfully - check mylar.log file.')
                            elif metaresponse == "unrar error":
                                logger.error(module + ' This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and retrying it.')
                                #launch failed download handling here.
                            else:
                                ofilename = os.path.split(metaresponse)[1]
                                logger.info(module + ' Sucessfully wrote metadata to .cbz (' + ofilename + ') - Continuing..')
                                self._log('Sucessfully wrote metadata to .cbz (' + ofilename + ') - proceeding...')

                        if 'S' in sandwich:
                            if mylar.STORYARCDIR:
                                grdst = storyarcd
                            else:
                                grdst = mylar.DESTINATION_DIR
                        else:
                            if mylar.GRABBAG_DIR:
                                grdst = mylar.GRABBAG_DIR
                            else:
                                grdst = mylar.DESTINATION_DIR
   
                        filechecker.validateAndCreateDirectory(grdst, True, module=module)
    
                        if 'S' in sandwich:
                            #if from a StoryArc, check to see if we're appending the ReadingOrder to the filename
                            if mylar.READ2FILENAME:
                                logger.fdebug(module + ' readingorder#: ' + str(arcdata['ReadingOrder']))
                                if int(arcdata['ReadingOrder']) < 10: readord = "00" + str(arcdata['ReadingOrder'])
                                elif int(arcdata['ReadingOrder']) > 10 and int(arcdata['ReadingOrder']) < 99: readord = "0" + str(arcdata['ReadingOrder'])
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

                        logger.info(module + ' Moving ' + str(ofilename) + ' into directory : ' + str(grdst))

                        try:
                            shutil.move(grab_src, grab_dst)
                        except (OSError, IOError):
                            self._log("Failed to move directory - check directories and manually re-run.")
                            logger.debug(module + ' Failed to move directory - check directories and manually re-run.')
                            return
                        #tidyup old path
                        try:
                            shutil.rmtree(self.nzb_folder)
                        except (OSError, IOError):
                            self._log("Failed to remove temporary directory.")
                            logger.debug(module + ' Failed to remove temporary directory - check directory and manually re-run.')
                            return

                        logger.debug(module + ' Removed temporary directory : ' + str(self.nzb_folder))
                        self._log("Removed temporary directory : " + self.nzb_folder)
                        #delete entry from nzblog table
                        myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])

                        if 'S' in issueid:
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

                        self.valreturn.append({"self.log" : self.log,
                                               "mode"     : 'stop'})
                        return self.queue.put(self.valreturn)


            if self.nzb_name == 'Manual Run':
                #loop through the hits here.
                if len(manual_list) == 0:
                    logger.info(module + ' No matches for Manual Run ... exiting.')
                    return

                for ml in manual_list:
                    comicid = ml['ComicID']
                    issueid = ml['IssueID']
                    issuenumOG = ml['IssueNumber']
                    dupthis = helpers.duplicate_filecheck(ml['ComicLocation'], ComicID=comicid, IssueID=issueid)
                    if dupthis == "write":
                        self.Process_next(comicid,issueid,issuenumOG,ml)
                        dupthis = None
                logger.info(module + ' Manual post-processing completed.')
                return
            else:
                comicid = issuenzb['ComicID']
                issuenumOG = issuenzb['Issue_Number']
                #the self.nzb_folder should contain only the existing filename
                dupthis = helpers.duplicate_filecheck(self.nzb_folder, ComicID=comicid, IssueID=issueid)
                if dupthis == "write":
                    return self.Process_next(comicid,issueid,issuenumOG)
                else:
                    self.valreturn.append({"self.log" : self.log,
                                           "mode"     : 'stop',
                                           "issueid"  : issueid,
                                           "comicid"  : comicid})

                    return self.queue.put(self.valreturn)


    def Process_next(self,comicid,issueid,issuenumOG,ml=None):
            module = self.module
            annchk = "no"
            extensions = ('.cbr', '.cbz')
            snatchedtorrent = False
            myDB = db.DBConnection()
            comicnzb = myDB.selectone("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
            issuenzb = myDB.selectone("SELECT * from issues WHERE issueid=? AND comicid=? AND ComicName NOT NULL", [issueid,comicid]).fetchone()
            if ml is not None and mylar.SNATCHEDTORRENT_NOTIFY:
                snatchnzb = myDB.selectone("SELECT * from snatched WHERE IssueID=? AND ComicID=? AND (provider=? OR provider=?) AND Status='Snatched'", [issueid,comicid,'KAT','CBT']).fetchone() 
                if snatchnzb is None:
                    logger.fdebug(module + ' Was not downloaded with Mylar and the usage of torrents. Disabling torrent manual post-processing completion notification.')
                else:
                    logger.fdebug(module + ' Was downloaded from ' + snatchnzb['Provider'] + '. Enabling torrent manual post-processing completion notification.')
                    snatchedtorrent = True

            if issuenzb is None:
                issuenzb = myDB.selectone("SELECT * from annuals WHERE issueid=? and comicid=?", [issueid,comicid]).fetchone()
                annchk = "yes"
            if annchk == "no":
                logger.info(module + ' Starting Post-Processing for ' + issuenzb['ComicName'] + ' issue: ' + str(issuenzb['Issue_Number']))
            else:
                logger.info(module + ' Starting Post-Processing for ' + issuenzb['ReleaseComicName'] + ' issue: ' + str(issuenzb['Issue_Number']))
            logger.fdebug(module + ' issueid: ' + str(issueid))
            logger.fdebug(module + ' issuenumOG: ' + str(issuenumOG))

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

            if '.' in issuenum:
                iss_find = issuenum.find('.')
                iss_b4dec = issuenum[:iss_find]
                iss_decval = issuenum[iss_find+1:]
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
                issueno = str(iss)

            # issue zero-suppression here
            if mylar.ZERO_LEVEL == "0": 
                zeroadd = ""
            else:
                if mylar.ZERO_LEVEL_N  == "none": zeroadd = ""
                elif mylar.ZERO_LEVEL_N == "0x": zeroadd = "0"
                elif mylar.ZERO_LEVEL_N == "00x": zeroadd = "00"

            logger.fdebug(module + ' Zero Suppression set to : ' + str(mylar.ZERO_LEVEL_N))

            if str(len(issueno)) > 1:
                if issueno.isalpha():
                    self._log('issue detected as an alpha.')
                    prettycomiss = str(issueno)
                elif int(issueno) < 0:
                    self._log("issue detected is a negative")
                    prettycomiss = '-' + str(zeroadd) + str(abs(issueno))
                elif int(issueno) < 10:
                    self._log("issue detected less than 10")
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
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss))
                elif int(issueno) >= 10 and int(issueno) < 100:
                    self._log("issue detected greater than 10, but less than 100")
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
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ".Issue will be set as : " + str(prettycomiss))
                else:
                    self._log("issue detected greater than 100")
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                    prettycomiss = str(issueno)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss))
            else:
                prettycomiss = str(issueno)
                self._log("issue length error - cannot determine length. Defaulting to None:  " + str(prettycomiss))

            if annchk == "yes":
                self._log("Annual detected.")
            logger.fdebug(module + ' Pretty Comic Issue is : ' + str(prettycomiss))
            issueyear = issuenzb['IssueDate'][:4]
            self._log("Issue Year: " + str(issueyear))
            logger.fdebug(module + ' Issue Year : ' + str(issueyear))
            month = issuenzb['IssueDate'][5:7].replace('-','').strip()
            month_name = helpers.fullmonth(month)
#            comicnzb= myDB.action("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
            publisher = comicnzb['ComicPublisher']
            self._log("Publisher: " + publisher)
            logger.fdebug(module + ' Publisher: ' + str(publisher))
            #we need to un-unicode this to make sure we can write the filenames properly for spec.chars
            series = comicnzb['ComicName'].encode('ascii', 'ignore').strip()
            self._log("Series: " + series)
            logger.fdebug(module + ' Series: ' + str(series))
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
                chunk_f_f = re.sub('\$VolumeN','',mylar.FILE_FORMAT)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                self._log("No version # found for series - tag will not be available for renaming.")
                logger.fdebug(module + ' No version # found for series, removing from filename')
                logger.fdebug(module + ' New format is now: ' + str(chunk_file_format))
            else:
                chunk_file_format = mylar.FILE_FORMAT

            if annchk == "no":
                chunk_f_f = re.sub('\$Annual','',chunk_file_format)
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
                        pcheck = cmtagmylar.run(self.nzb_folder, issueid=issueid)
                    else:
                        pcheck = cmtagmylar.run(self.nzb_folder, issueid=issueid, manual="yes", filename=ml['ComicLocation'])

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
                else:
                    otofilename = pcheck
                    self._log("Sucessfully wrote metadata to .cbz - Continuing..")
                    logger.info(module + ' Sucessfully wrote metadata to .cbz (' + os.path.split(otofilename)[1] + ') - Continuing..')
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
                self._run_pre_scripts(nzbn, nzbf, seriesmetadata )

        #rename file and move to new path
        #nfilename = series + " " + issueno + " (" + seriesyear + ")"

            file_values = {'$Series':    series,
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
            if ml is None:
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
                logger.fdebug(module + ' odir: ' + str(odir))
                logger.fdebug(module + ' ofilename: ' + str(ofilename))

            else:
                if pcheck == "fail":
                    otofilename = ml['ComicLocation']
                logger.fdebug(module + ' otofilename:' + str(otofilename))
                odir, ofilename = os.path.split(otofilename)
                logger.fdebug(module + ' odir: ' + str(odir))
                logger.fdebug(module + ' ofilename: ' + str(ofilename))
                path, ext = os.path.splitext(ofilename)
                logger.fdebug(module + ' path: ' + str(path))
                logger.fdebug(module + ' ext:' + str(ext))

            if ofilename is None:
                logger.error(module + ' Aborting PostProcessing - the filename does not exist in the location given. Make sure that ' + str(self.nzb_folder) + ' exists and is the correct location.')
                self.valreturn.append({"self.log" : self.log,
                                       "mode"     : 'stop'})
                return self.queue.put(self.valreturn)
            self._log("Original Filename: " + ofilename)
            self._log("Original Extension: " + ext)
            logger.fdebug(module + ' Original Filname: ' + str(ofilename))
            logger.fdebug(module + ' Original Extension: ' + str(ext))

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
            filechecker.validateAndCreateDirectory(comlocation, True, module=module)

            if mylar.LOWERCASE_FILENAMES:
                dst = os.path.join(comlocation, (nfilename + ext).lower())
            else:
                dst = os.path.join(comlocation, (nfilename + ext.lower()))
            self._log("Source:" + src)
            self._log("Destination:" +  dst)
            logger.fdebug(module + ' Source: ' + str(src))
            logger.fdebug(module + ' Destination: ' + str(dst))

            if ml is None:
                #downtype = for use with updater on history table to set status to 'Downloaded'
                downtype = 'True'
                #non-manual run moving/deleting...
                logger.fdebug(module + ' self.nzb_folder: ' + self.nzb_folder)
                logger.fdebug(module + ' odir: ' + str(odir))
                logger.fdebug(module + ' ofilename:' + str(ofilename))
                logger.fdebug(module + ' nfilename:' + str(nfilename + ext))
                if mylar.RENAME_FILES:
                    if str(ofilename) != str(nfilename + ext):
                        logger.fdebug(module + ' Renaming ' + os.path.join(odir, str(ofilename)) + ' ..to.. ' + os.path.join(odir,str(nfilename + ext)))
                        os.rename(os.path.join(odir, str(ofilename)), os.path.join(odir,str(nfilename + ext)))
                    else:
                        logger.fdebug(module + ' Filename is identical as original, not renaming.')

                #src = os.path.join(self.nzb_folder, str(nfilename + ext))
                src = os.path.join(odir, str(nfilename + ext))
                try:
                    shutil.move(src, dst)
                except (OSError, IOError):
                    self._log("Failed to move directory - check directories and manually re-run.")
                    self._log("Post-Processing ABORTED.")
                    logger.warn(module + ' Failed to move directory : ' + src + ' to ' + dst + ' - check directory and manually re-run')
                    logger.warn(module + ' Post-Processing ABORTED')
                    self.valreturn.append({"self.log" : self.log,
                                           "mode"     : 'stop'})
                    return self.queue.put(self.valreturn)

                #tidyup old path
                try:
                    shutil.rmtree(self.nzb_folder)
                except (OSError, IOError):
                    self._log("Failed to remove temporary directory - check directory and manually re-run.")
                    self._log("Post-Processing ABORTED.")
                    logger.warn(module + ' Failed to remove temporary directory : ' + self.nzb_folder)
                    logger.warn(module + ' Post-Processing ABORTED')
                    self.valreturn.append({"self.log" : self.log,
                                           "mode"     : 'stop'})
                    return self.queue.put(self.valreturn)
                self._log("Removed temporary directory : " + str(self.nzb_folder))
                logger.fdebug(module + ' Removed temporary directory : ' + self.nzb_folder)
            else:
                #downtype = for use with updater on history table to set status to 'Post-Processed'
                downtype = 'PP'
                #Manual Run, this is the portion.
                if mylar.RENAME_FILES:
                    if str(ofilename) != str(nfilename + ext):
                        logger.fdebug(module + ' Renaming ' + os.path.join(odir, str(ofilename)) + ' ..to.. ' + os.path.join(odir, self.nzb_folder,str(nfilename + ext)))
                        os.rename(os.path.join(odir, str(ofilename)), os.path.join(odir ,str(nfilename + ext)))
                    else:
                        logger.fdebug(module + ' Filename is identical as original, not renaming.')
                src = os.path.join(odir, str(nfilename + ext))
                logger.fdebug(module + ' odir src : ' + os.path.join(odir, str(nfilename + ext)))
                logger.fdebug(module + ' Moving ' + src + ' ... to ... ' + dst)
                try:
                    shutil.move(src, dst)
                except (OSError, IOError):
                    logger.fdebug(module + ' Failed to move directory - check directories and manually re-run.')
                    logger.fdebug(module + ' Post-Processing ABORTED.')

                    self.valreturn.append({"self.log" : self.log,
                                           "mode"     : 'stop'})
                    return self.queue.put(self.valreturn)
                logger.fdebug(module + ' Successfully moved to : ' + dst)

                #tidyup old path
                try:
                    if os.path.isdir(odir) and odir != self.nzb_folder:
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
            try:
                permission = int(mylar.CHMOD_FILE, 8)
                os.umask(0)
                os.chmod(dst.rstrip(), permission)
            except OSError:
                logger.error(module + ' Failed to change file permissions. Ensure that the user running Mylar has proper permissions to change permissions in : ' + dst)
                logger.fdebug(module + ' Continuing post-processing but unable to change file permissions in ' + dst)
                    #delete entry from nzblog table
            myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])
                    #update snatched table to change status to Downloaded
            
            if annchk == "no":
                updater.foundsearch(comicid, issueid, down=downtype, module=module)
                dispiss = 'issue: ' + str(issuenumOG)
            else:
                updater.foundsearch(comicid, issueid, mode='want_ann', down=downtype, module=module)
                if 'annual' not in series.lower():
                    dispiss = 'annual issue: ' + str(issuenumOG)
                else:
                    dispiss = str(issuenumOG)

            #force rescan of files
            updater.forceRescan(comicid,module=module)

            if mylar.WEEKFOLDER:
                #if enabled, will *copy* the post-processed file to the weeklypull list folder for the given week.
                weeklypull.weekly_singlecopy(comicid,issuenum,str(nfilename+ext),dst,module=module)

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
                self._run_extra_scripts(nzbn, self.nzb_folder, filen, folderp, seriesmetadata )

            if ml is not None:
                #we only need to return self.log if it's a manual run and it's not a snatched torrent
                if snatchedtorrent: 
                    #manual run + snatched torrent
                    pass
                else:
                    #manual run + not snatched torrent (or normal manual-run)
                    logger.info(module + ' Post-Processing completed for: ' + series + ' ' + dispiss )
                    self._log(u"Post Processing SUCCESSFUL! ")
                    self.valreturn.append({"self.log" : self.log,
                                           "mode"     : 'stop',
                                           "issueid"  : issueid,
                                           "comicid"  : comicid})

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
                prowl.notify(pushmessage,"Download and Postprocessing completed", module=module)
    
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
             
            logger.info(module + ' Post-Processing completed for: ' + series + ' ' + dispiss )
            self._log(u"Post Processing SUCCESSFUL! ")

            self.valreturn.append({"self.log" : self.log,
                                   "mode"     : 'stop',
                                   "issueid"  : issueid,
                                   "comicid"  : comicid})

            return self.queue.put(self.valreturn)



class FolderCheck():

    def run(self):
        module = '[FOLDER-CHECK]'
        import PostProcessor, logger
        #monitor a selected folder for 'snatched' files that haven't been processed
        logger.info(module + ' Checking folder ' + mylar.CHECK_FOLDER + ' for newly snatched downloads')
        PostProcess = PostProcessor.PostProcessor('Manual Run', mylar.CHECK_FOLDER)
        result = PostProcess.Process()
        logger.info(module + ' Finished checking for newly snatched downloads')

