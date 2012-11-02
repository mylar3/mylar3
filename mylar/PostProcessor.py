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
import shutil

import time

import mylar

from mylar import logger, db, helpers, updater

def PostProcess(nzb_name, nzb_folder):
        log2screen = ""
        log2screen = log2screen + "Nzb Name:" + nzb_name + "\n"
        log2screen = log2screen + "Nzb Folder:"  + nzb_folder + "\n"
                #lookup nzb_name in nzblog table to get issueid
        myDB = db.DBConnection()
        nzbiss = myDB.action("SELECT * from nzblog WHERE nzbname=?", [nzb_name]).fetchone()
        if nzbiss is None:
            log2screen = log2screen + "Epic failure - could not locate file to rename." + "\n"
            logger.error(u"Unable to locate downloaded file to rename. PostProcessing aborted.")
            return
        else: 
            issueid = nzbiss['IssueID']
        #log2screen = log2screen + "IssueID: " + issueid + "\n"
                #use issueid to get publisher, series, year, issue number
        issuenzb = myDB.action("SELECT * from issues WHERE issueid=?", [issueid]).fetchone()
        comicid = issuenzb['ComicID']
        #log2screen = log2screen + "ComicID: " + comicid + "\n"
        issuenum = issuenzb['Issue_Number']
        issueno = str(issuenum).split('.')[0]
        log2screen = log2screen + "Issue Number: " + str(issueno) + "\n"
        # issue zero-suppression here
        if mylar.ZERO_LEVEL == "0": 
            zeroadd = ""
        else:
            if mylar.ZERO_LEVEL_N  == "none": zeroadd = ""
            elif mylar.ZERO_LEVEL_N == "0x": zeroadd = "0"
            elif mylar.ZERO_LEVEL_N == "00x": zeroadd = "00"


        if str(len(issueno)) > 1:
            if int(issueno) < 10:
                log2screen = log2screen + "issue detected less than 10" + "\n"
                prettycomiss = str(zeroadd) + str(int(issueno))
                log2screen = log2screen + "Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss) + "\n"
            elif int(issueno) >= 10 and int(issueno) < 100:
                log2screen = log2screen + "issue detected greater than 10, but less than 100" + "\n"
                if mylar.ZERO_LEVEL_N == "none":
                    zeroadd = ""
                else:
                    zeroadd = "0"
                prettycomiss = str(zeroadd) + str(int(issueno))
                log2screen = log2screen + "Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ".Issue will be set as : " + str(prettycomiss) + "\n"
            else:
                log2screen = log2screen + "issue detected greater than 100" + "\n"
                prettycomiss = str(issueno)
                log2screen = log2screen + "Zero level supplement set to " + str(mylar.ZERO_LEVEL_N) + ". Issue will be set as : " + str(prettycomiss) + "\n"
        else:
            prettycomiss = str(issueno)
            log2screen = log2screen + "issue length error - cannot determine length. Defaulting to None:  " + str(prettycomiss) + "\n"

        issueyear = issuenzb['IssueDate'][:4]
        log2screen = log2screen + "Issue Year: " + str(issueyear) + "\n"
        comicnzb= myDB.action("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
        publisher = comicnzb['ComicPublisher']
        log2screen = log2screen + "Publisher: " + publisher + "\n"
        series = comicnzb['ComicName']
        log2screen = log2screen + "Series: " + series + "\n"
        seriesyear = comicnzb['ComicYear']
        log2screen = log2screen + "Year: " + seriesyear + "\n"
        comlocation = comicnzb['ComicLocation']
        log2screen = log2screen + "Comic Location: " + comlocation + "\n"
#---move to importer.py
                #get output path format
#        if ':' in series:
#            series = series.replace(':','')
                #do work to generate folder path
#        values = {'$Series':    series,
#              '$Publisher': publisher,
#              '$Year':      seriesyear
#              }
#        comlocation = mylar.DESTINATION_DIR + "/" + helpers.replace_all(mylar.FOLDER_FORMAT, values)
            #last perform space replace
#        if mylar.REPLACE_SPACES:
            #mylar.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
#            comlocation = comlocation.replace(' ', mylar.REPLACE_CHAR)
#        log2screen = log2screen + "Final Location: " + comlocation + "\n"
#---
        #rename file and move to new path
        #nfilename = series + " " + issueno + " (" + seriesyear + ")"
        file_values = {'$Series':    series,
                       '$Issue':     prettycomiss,
                       '$Year':      issueyear
                      }

        extensions = ('.cbr', '.cbz')

        for root, dirnames, filenames in os.walk(nzb_folder):
            for filename in filenames:
                if filename.lower().endswith(extensions):
                    ofilename = filename
                    path, ext = os.path.splitext(ofilename)
        log2screen = log2screen + "Original Filename: " + ofilename + "\n"
        log2screen = log2screen + "Original Extension: " + ext + "\n"
        if mylar.FILE_FORMAT == '':
            log2screen = log2screen + "Rename Files isn't enabled...keeping original filename." + "\n"
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
        #TODO - sort issue numbering 12.00 should be 12
        log2screen = log2screen + "New Filename: " + nfilename + "\n"

        src = nzb_folder + "/" + ofilename
        dst = comlocation + "/" + nfilename + ext
        log2screen = log2screen + "Source:" + src + "\n"
        log2screen = log2screen + "Destination:" +  dst + "\n"
        os.rename(nzb_folder + "/" + ofilename, nzb_folder + "/" + nfilename + ext)
        src = nzb_folder + "/" + nfilename + ext
        try:
            shutil.move(src, dst)
        except (OSError, IOError):
            log2screen = log2screen + "Failed to move directory - check directories and manually re-run." + "\n"
            log2screen = log2screen + "Post-Processing ABORTED." + "\n"
            return log2screen
        #tidyup old path
        try:
            shutil.rmtree(nzb_folder)
        except (OSError, IOError):
            log2screen = log2screen + "Failed to remove temporary directory - check directory and manually re-run." + "\n"
            log2screen = log2screen + "Post-Processing ABORTED." + "\n"
            return log2screen

        log2screen = log2screen + "Removed temporary directory : " + str(nzb_folder) + "\n"
                #delete entry from nzblog table
        myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])
                #force rescan of files
        updater.forceRescan(comicid)
        logger.info(u"Post-Processing completed for: " + series + " issue: " + str(issuenum) )
        log2screen = log2screen + "Post Processing SUCCESSFULL!" + "\n"
        #print log2screen
        return log2screen

