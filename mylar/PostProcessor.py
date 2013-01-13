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

from mylar import logger, db, helpers, updater

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

    def _run_extra_scripts(self, nzb_name, nzb_folder, filen, folderp, seriesmetadata):
        """
        Executes any extra scripts defined in the config.

        ep_obj: The object to use when calling the extra script
        """
        self._log("initiating extra script detection.", logger.DEBUG)
        self._log("mylar.EXTRA_SCRIPTS : " + mylar.EXTRA_SCRIPTS, logger.DEBUG)
#        for curScriptName in mylar.EXTRA_SCRIPTS:
        curScriptName = mylar.EXTRA_SCRIPTS
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


#    def PostProcess(nzb_name, nzb_folder):
    def Process(self):
            self._log("nzb name: " + str(self.nzb_name), logger.DEBUG)
            self._log("nzb folder: " + str(self.nzb_folder), logger.DEBUG)
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
            #logger.fdebug("sabreps:" + str(sabreps))

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
            nzbname = re.sub('[\,\:]', '', str(nzbname))

            self._log("nzbname: " + str(nzbname), logger.DEBUG)

            nzbiss = myDB.action("SELECT * from nzblog WHERE nzbname=?", [nzbname]).fetchone()

            if nzbiss is None:
                self._log("Failure - could not initially locate nzbfile in my database to rename.", logger.DEBUG)
                # if failed on spaces, change it all to decimals and try again.
                nzbname = re.sub('_', '.', str(nzbname))
                self._log("trying again with this nzbname: " + str(nzbname), logger.DEBUG)
                nzbiss = myDB.action("SELECT * from nzblog WHERE nzbname=?", [nzbname]).fetchone()
                if nzbiss is None:
                    logger.error(u"Unable to locate downloaded file to rename. PostProcessing aborted.")
                    return
                else:
                    self._log("I corrected and found the nzb as : " + str(nzbname))
                    issueid = nzbiss['IssueID']
            else: 
                issueid = nzbiss['IssueID']
                #use issueid to get publisher, series, year, issue number
            issuenzb = myDB.action("SELECT * from issues WHERE issueid=?", [issueid]).fetchone()
            comicid = issuenzb['ComicID']
            issuenum = issuenzb['Issue_Number']
            #issueno = str(issuenum).split('.')[0]

            iss_find = issuenum.find('.')
            iss_b4dec = issuenum[:iss_find]
            iss_decval = issuenum[iss_find+1:]
            if int(iss_decval) == 0:
                iss = iss_b4dec
                issdec = int(iss_decval)
                issueno = str(iss)
                self._log("Issue Number: " + str(issueno), logger.DEBUG)
            else:
                if len(iss_decval) == 1:
                    iss = iss_b4dec + "." + iss_decval
                    issdec = int(iss_decval) * 10
                else:
                    iss = iss_b4dec + "." + iss_decval.rstrip('0')
                    issdec = int(iss_decval.rstrip('0')) * 10
                issueno = iss_b4dec
                self._log("Issue Number: " + str(iss), logger.DEBUG)

            # issue zero-suppression here
            if mylar.ZERO_LEVEL == "0": 
                zeroadd = ""
            else:
                if mylar.ZERO_LEVEL_N  == "none": zeroadd = ""
                elif mylar.ZERO_LEVEL_N == "0x": zeroadd = "0"
                elif mylar.ZERO_LEVEL_N == "00x": zeroadd = "00"

            if str(len(issueno)) > 1:
                if int(issueno) < 10:
                    self._log("issue detected less than 10", logger.DEBUG)
                    if int(iss_decval) > 0:
                        issueno = str(iss)
                        prettycomiss = str(zeroadd) + str(iss)
                    else:
                        prettycomiss = str(zeroadd) + str(int(issueno))
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss), logger.DEBUG)
                elif int(issueno) >= 10 and int(issueno) < 100:
                    self._log("issue detected greater than 10, but less than 100", logger.DEBUG)
                    if mylar.ZERO_LEVEL_N == "none":
                        zeroadd = ""
                    else:
                        zeroadd = "0"
                    if int(iss_decval) > 0:
                        issueno = str(iss)
                        prettycomiss = str(zeroadd) + str(iss)
                    else:
                        prettycomiss = str(zeroadd) + str(int(issueno))
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ".Issue will be set as : " + str(prettycomiss), logger.DEBUG)
                else:
                    self._log("issue detected greater than 100", logger.DEBUG)
                    if int(iss_decval) > 0:
                        issueno = str(iss)
                    prettycomiss = str(issueno)
                    self._log("Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss), logger.DEBUG)
            else:
                prettycomiss = str(issueno)
                self._log("issue length error - cannot determine length. Defaulting to None:  " + str(prettycomiss), logger.DEBUG)

            issueyear = issuenzb['IssueDate'][:4]
            self._log("Issue Year: " + str(issueyear), logger.DEBUG)
            comicnzb= myDB.action("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
            publisher = comicnzb['ComicPublisher']
            self._log("Publisher: " + publisher, logger.DEBUG)
            series = comicnzb['ComicName']
            self._log("Series: " + series, logger.DEBUG)
            seriesyear = comicnzb['ComicYear']
            self._log("Year: " + seriesyear, logger.DEBUG)
            comlocation = comicnzb['ComicLocation']
            self._log("Comic Location: " + comlocation, logger.DEBUG)
        #rename file and move to new path
        #nfilename = series + " " + issueno + " (" + seriesyear + ")"
            file_values = {'$Series':    series,
                           '$Issue':     prettycomiss,
                           '$Year':      issueyear
                          }

            for root, dirnames, filenames in os.walk(self.nzb_folder):
                for filename in filenames:
                    if filename.lower().endswith(extensions):
                        ofilename = filename
                        path, ext = os.path.splitext(ofilename)
            self._log("Original Filename: " + ofilename, logger.DEBUG)
            self._log("Original Extension: " + ext, logger.DEBUG)
            if mylar.FILE_FORMAT == '':
                self._log("Rename Files isn't enabled...keeping original filename.", logger.DEBUG)
                #check if extension is in nzb_name - will screw up otherwise
                if ofilename.lower().endswith(extensions):
                    nfilename = ofilename[:-4]
                else:
                    nfilename = ofilename
            else:
                nfilename = helpers.replace_all(mylar.FILE_FORMAT, file_values)
                if mylar.REPLACE_SPACES:
                    #mylar.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                    nfilename = nfilename.replace(' ', mylar.REPLACE_CHAR)
            nfilename = re.sub('[\,\:]', '', nfilename)
            self._log("New Filename: " + nfilename, logger.DEBUG)

            src = self.nzb_folder + "/" + ofilename
            dst = comlocation + "/" + nfilename + ext
            self._log("Source:" + src, logger.DEBUG)
            self._log("Destination:" +  dst, logger.DEBUG)
            os.rename(self.nzb_folder + "/" + ofilename, self.nzb_folder + "/" + nfilename + ext)
            src = self.nzb_folder + "/" + nfilename + ext
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
            logger.info(u"Post-Processing completed for: " + series + " issue: " + str(issuenum) )
            self._log(u"Post Processing SUCCESSFULL! ", logger.DEBUG)

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

