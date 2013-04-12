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

from mylar import logger, db, helpers, updater, notifiers

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

    def __init__(self, nzb_name, nzb_folder):
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
        #self.in_history = False
        #self.release_group = None
        #self.is_proper = False

        self.log = ''

    def _log(self, message, level=logger.MESSAGE):
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
        self._log("initiating pre script detection.", logger.DEBUG)
        self._log("mylar.PRE_SCRIPTS : " + mylar.PRE_SCRIPTS, logger.DEBUG)
#        for currentScriptName in mylar.PRE_SCRIPTS:
        currentScriptName = str(mylar.PRE_SCRIPTS).decode("string_escape")
        self._log("pre script detected...enabling: " + str(currentScriptName), logger.DEBUG)
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(currentScriptName, posix=False) + [str(nzb_name), str(nzb_folder), str(seriesmetadata)]
        self._log("cmd to be executed: " + str(script_cmd), logger.DEBUG)

            # use subprocess to run the command and capture output
        self._log(u"Executing command "+str(script_cmd))
        self._log(u"Absolute path to script: "+script_cmd[0], logger.DEBUG)
        try:
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
            out, err = p.communicate() #@UnusedVariable
            self._log(u"Script result: "+str(out), logger.DEBUG)
        except OSError, e:
           self._log(u"Unable to run pre_script: " + str(script_cmd))

    def _run_extra_scripts(self, nzb_name, nzb_folder, filen, folderp, seriesmetadata):
        """
        Executes any extra scripts defined in the config.

        ep_obj: The object to use when calling the extra script
        """
        self._log("initiating extra script detection.", logger.DEBUG)
        self._log("mylar.EXTRA_SCRIPTS : " + mylar.EXTRA_SCRIPTS, logger.DEBUG)
#        for curScriptName in mylar.EXTRA_SCRIPTS:
        curScriptName = str(mylar.EXTRA_SCRIPTS).decode("string_escape")
        self._log("extra script detected...enabling: " + str(curScriptName), logger.DEBUG)
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(curScriptName) + [str(nzb_name), str(nzb_folder), str(filen), str(folderp), str(seriesmetadata)]
        self._log("cmd to be executed: " + str(script_cmd), logger.DEBUG)

            # use subprocess to run the command and capture output
        self._log(u"Executing command "+str(script_cmd))
        self._log(u"Absolute path to script: "+script_cmd[0], logger.DEBUG)
        try:
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
            out, err = p.communicate() #@UnusedVariable
            self._log(u"Script result: "+str(out), logger.DEBUG)
        except OSError, e:
            self._log(u"Unable to run extra_script: " + str(script_cmd))


    def Process(self):
            self._log("nzb name: " + str(self.nzb_name), logger.DEBUG)
            self._log("nzb folder: " + str(self.nzb_folder), logger.DEBUG)
            logger.fdebug("nzb name: " + str(self.nzb_name))
            logger.fdebug("nzb folder: " + str(self.nzb_folder))
            if mylar.USE_SABNZBD==0:
                logger.fdebug("Not using SABNzbd")
            else:
                # if the SAB Directory option is enabled, let's use that folder name and append the jobname.
                if mylar.SAB_DIRECTORY is not None and mylar.SAB_DIRECTORY is not 'None' and len(mylar.SAB_DIRECTORY) > 4:
                    self.nzb_folder = os.path.join(mylar.SAB_DIRECTORY, self.nzb_name).encode(mylar.SYS_ENCODING)
    
                #lookup nzb_name in nzblog table to get issueid
    
                #query SAB to find out if Replace Spaces enabled / not as well as Replace Decimals
                #http://localhost:8080/sabnzbd/api?mode=set_config&section=misc&keyword=dirscan_speed&value=5
                querysab = str(mylar.SAB_HOST) + "/api?mode=get_config&section=misc&output=xml&apikey=" + str(mylar.SAB_APIKEY)
                #logger.info("querysab_string:" + str(querysab))
                file = urllib2.urlopen(querysab)
                data = file.read()
                file.close()
                dom = parseString(data)
    
                sabreps = dom.getElementsByTagName('replace_spaces')[0].firstChild.wholeText
                sabrepd = dom.getElementsByTagName('replace_dots')[0].firstChild.wholeText
                logger.fdebug("SAB Replace Spaces: " + str(sabreps))
                logger.fdebug("SAB Replace Dots: " + str(sabrepd))
            if mylar.USE_NZBGET==1:
                logger.fdebug("Using NZBGET")
                logger.fdebug("NZB name as passed from NZBGet: " + self.nzb_name)
            myDB = db.DBConnection()

            nzbname = self.nzb_name
            #remove extensions from nzb_name if they somehow got through (Experimental most likely)
            extensions = ('.cbr', '.cbz')

            if nzbname.lower().endswith(extensions):
                fd, ext = os.path.splitext(nzbname)
                self._log("Removed extension from nzb: " + ext, logger.DEBUG)
                nzbname = re.sub(str(ext), '', str(nzbname))

            #replace spaces
            nzbname = re.sub(' ', '.', str(nzbname))
            nzbname = re.sub('[\,\:\?]', '', str(nzbname))
            nzbname = re.sub('[\&]', 'and', str(nzbname))

            logger.fdebug("After conversions, nzbname is : " + str(nzbname))
#            if mylar.USE_NZBGET==1:
#                nzbname=self.nzb_name
            self._log("nzbname: " + str(nzbname), logger.DEBUG)

            nzbiss = myDB.action("SELECT * from nzblog WHERE nzbname=?", [nzbname]).fetchone()

            if nzbiss is None:
                self._log("Failure - could not initially locate nzbfile in my database to rename.", logger.DEBUG)
                logger.fdebug("Failure - could not locate nzbfile initially.")
                # if failed on spaces, change it all to decimals and try again.
                nzbname = re.sub('_', '.', str(nzbname))
                self._log("trying again with this nzbname: " + str(nzbname), logger.DEBUG)
                logger.fdebug("trying again with nzbname of : " + str(nzbname))
                nzbiss = myDB.action("SELECT * from nzblog WHERE nzbname=?", [nzbname]).fetchone()
                if nzbiss is None:
                    logger.error(u"Unable to locate downloaded file to rename. PostProcessing aborted.")
                    return
                else:
                    self._log("I corrected and found the nzb as : " + str(nzbname))
                    logger.fdebug("auto-corrected and found the nzb as : " + str(nzbname))
                    issueid = nzbiss['IssueID']
            else: 
                issueid = nzbiss['IssueID']
                print "issueid:" + str(issueid)
                #use issueid to get publisher, series, year, issue number
            issuenzb = myDB.action("SELECT * from issues WHERE issueid=?", [issueid]).fetchone()
            if issuenzb is None or int(issuenzb['IssueID']) >= '900000':
                # this has no issueID, therefore it's a one-off or a manual post-proc.
                # At this point, let's just drop it into the Comic Location folder and forget about it..
                self._log("One-off mode enabled for Post-Processing. All I'm doing is moving the file untouched into the Grab-bag directory.", logger.DEBUG)
                logger.info("One-off mode enabled for Post-Processing. Will move into Grab-bag directory.")
                self._log("Grab-Bag Directory set to : " + mylar.GRABBAG_DIR, logger.DEBUG)
                for root, dirnames, filenames in os.walk(self.nzb_folder):
                    for filename in filenames:
                        if filename.lower().endswith(extensions):
                            ofilename = filename
                            path, ext = os.path.splitext(ofilename)

                if mylar.GRABBAG_DIR:
                    grdst = mylar.GRABBAG_DIR
                else:
                    grdst = mylar.DESTINATION_DIR

                grab_dst = os.path.join(grdst, ofilename)
                self._log("Destination Path : " + grab_dst, logger.DEBUG)
                grab_src = os.path.join(self.nzb_folder, ofilename)
                self._log("Source Path : " + grab_src, logger.DEBUG)
                logger.info("Moving " + str(ofilename) + " into grab-bag directory : " + str(grdst))

                try:
                    shutil.move(grab_src, grab_dst)
                except (OSError, IOError):
                    self.log("Failed to move directory - check directories and manually re-run.", logger.DEBUG)
                    logger.debug("Failed to move directory - check directories and manually re-run.")
                    return self.log
                #tidyup old path
                try:
                    shutil.rmtree(self.nzb_folder)
                except (OSError, IOError):
                    self._log("Failed to remove temporary directory.", logger.DEBUG)
                    logger.debug("Failed to remove temporary directory - check directory and manually re-run.")
                    return self.log

                logger.debug("Removed temporary directory : " + str(self.nzb_folder))
                self._log("Removed temporary directory : " + self.nzb_folder, logger.DEBUG)
                #delete entry from nzblog table
                myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])
                return self.log

            comicid = issuenzb['ComicID']
            issuenumOG = issuenzb['Issue_Number']
            #issueno = str(issuenum).split('.')[0]
            #new CV API - removed all decimals...here we go AGAIN!
            issuenum = issuenumOG
            issue_except = 'None'
            if 'au' in issuenum.lower():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = ' AU'
            if '.' in issuenum:
                iss_find = issuenum.find('.')
                iss_b4dec = issuenum[:iss_find]
                iss_decval = issuenum[iss_find+1:]
                if int(iss_decval) == 0:
                    iss = iss_b4dec
                    issdec = int(iss_decval)
                    issueno = str(iss)
                    self._log("Issue Number: " + str(issueno), logger.DEBUG)
                    logger.fdebug("Issue Number: " + str(issueno))
                else:
                    if len(iss_decval) == 1:
                        iss = iss_b4dec + "." + iss_decval
                        issdec = int(iss_decval) * 10
                    else:
                        iss = iss_b4dec + "." + iss_decval.rstrip('0')
                        issdec = int(iss_decval.rstrip('0')) * 10
                    issueno = iss_b4dec
                    self._log("Issue Number: " + str(iss), logger.DEBUG)
                    logger.fdebug("Issue Number: " + str(iss))
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

            logger.fdebug("Zero Suppression set to : " + str(mylar.ZERO_LEVEL_N))

            if str(len(issueno)) > 1:
                if int(issueno) < 10:
                    self._log("issue detected less than 10", logger.DEBUG)
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
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss), logger.DEBUG)
                elif int(issueno) >= 10 and int(issueno) < 100:
                    self._log("issue detected greater than 10, but less than 100", logger.DEBUG)
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
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ".Issue will be set as : " + str(prettycomiss), logger.DEBUG)
                else:
                    self._log("issue detected greater than 100", logger.DEBUG)
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                    prettycomiss = str(issueno)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss), logger.DEBUG)
            else:
                prettycomiss = str(issueno)
                self._log("issue length error - cannot determine length. Defaulting to None:  " + str(prettycomiss), logger.DEBUG)

            logger.fdebug("Pretty Comic Issue is : " + str(prettycomiss))
            issueyear = issuenzb['IssueDate'][:4]
            self._log("Issue Year: " + str(issueyear), logger.DEBUG)
            logger.fdebug("Issue Year : " + str(issueyear))
            comicnzb= myDB.action("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
            publisher = comicnzb['ComicPublisher']
            self._log("Publisher: " + publisher, logger.DEBUG)
            logger.fdebug("Publisher: " + str(publisher))
            #we need to un-unicode this to make sure we can write the filenames properly for spec.chars
            series = comicnzb['ComicName'].encode('ascii', 'ignore').strip()
            self._log("Series: " + series, logger.DEBUG)
            logger.fdebug("Series: " + str(series))
            seriesyear = comicnzb['ComicYear']
            self._log("Year: " + seriesyear, logger.DEBUG)
            logger.fdebug("Year: "  + str(seriesyear))
            comlocation = comicnzb['ComicLocation']
            self._log("Comic Location: " + comlocation, logger.DEBUG)
            logger.fdebug("Comic Location: " + str(comlocation))
            comversion = comicnzb['ComicVersion']
            self._log("Comic Version: " + str(comversion), logger.DEBUG)
            logger.fdebug("Comic Version: " + str(comversion))
            if comversion is None:
                comversion = 'None'
            #if comversion is None, remove it so it doesn't populate with 'None'
            if comversion == 'None':
                chunk_f_f = re.sub('\$VolumeN','',mylar.FILE_FORMAT)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                self._log("No version # found for series - tag will not be available for renaming.", logger.DEBUG)
                logger.fdebug("No version # found for series, removing from filename")
                logger.fdebug("new format is now: " + str(chunk_file_format))
            else:
                chunk_file_format = mylar.FILE_FORMAT
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
                           '$VolumeN':   comversion
                          }

            for root, dirnames, filenames in os.walk(self.nzb_folder):
                for filename in filenames:
                    if filename.lower().endswith(extensions):
                        ofilename = filename
                        path, ext = os.path.splitext(ofilename)
            self._log("Original Filename: " + ofilename, logger.DEBUG)
            self._log("Original Extension: " + ext, logger.DEBUG)
            logger.fdebug("Original Filname: " + str(ofilename))
            logger.fdebug("Original Extension: " + str(ext))

            if mylar.FILE_FORMAT == '' or not mylar.RENAME_FILES:
                self._log("Rename Files isn't enabled...keeping original filename.", logger.DEBUG)
                logger.fdebug("Rename Files isn't enabled - keeping original filename.")
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
            self._log("New Filename: " + nfilename, logger.DEBUG)
            logger.fdebug("New Filename: " + str(nfilename))

            src = os.path.join(self.nzb_folder, ofilename)
            if mylar.LOWERCASE_FILENAMES:
                dst = (comlocation + "/" + nfilename + ext).lower()
            else:
                dst = comlocation + "/" + nfilename + ext.lower()    
            self._log("Source:" + src, logger.DEBUG)
            self._log("Destination:" +  dst, logger.DEBUG)
            logger.fdebug("Source: " + str(src))
            logger.fdebug("Destination: " + str(dst))

            os.rename(os.path.join(self.nzb_folder, str(ofilename)), os.path.join(self.nzb_folder,str(nfilename + ext)))
            src = os.path.join(self.nzb_folder, str(nfilename + ext))
            try:
                shutil.move(src, dst)
            except (OSError, IOError):
                self._log("Failed to move directory - check directories and manually re-run.", logger.DEBUG)
                self._log("Post-Processing ABORTED.", logger.DEBUG)
                return
            #tidyup old path
            try:
                shutil.rmtree(self.nzb_folder)
            except (OSError, IOError):
                self._log("Failed to remove temporary directory - check directory and manually re-run.", logger.DEBUG)
                self._log("Post-Processing ABORTED.", logger.DEBUG)
                return

            self._log("Removed temporary directory : " + str(self.nzb_folder), logger.DEBUG)
                    #delete entry from nzblog table
            myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])
                    #force rescan of files
            updater.forceRescan(comicid)
            logger.info(u"Post-Processing completed for: " + series + " issue: " + str(issuenumOG) )
            self._log(u"Post Processing SUCCESSFULL! ", logger.DEBUG)

            if mylar.PROWL_ENABLED:
                pushmessage = series + '(' + issueyear + ') - issue #' + issuenumOG
                logger.info(u"Prowl request")
                prowl = notifiers.PROWL()
                prowl.notify(pushmessage,"Download and Postprocessing completed")

            if mylar.NMA_ENABLED:
                nma = notifiers.NMA()
                nma.notify(series, str(issueyear), str(issuenumOG))

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
                self._run_extra_scripts(nzbname, self.nzb_folder, filen, folderp, seriesmetadata )

            return self.log

