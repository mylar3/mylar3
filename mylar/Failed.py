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

from __future__ import division

import mylar
from mylar import logger, db, updater, helpers, parseit, findcomicfeed, notifiers, rsscheck

import lib.feedparser as feedparser
import urllib
import os, errno
import string
import sys
import getopt
import re
import time
import urlparse
from xml.dom.minidom import parseString
import urllib2
import email.utils
import datetime

class FailedProcessor(object):
    """ Handles Failed downloads that are passed from SABnzbd thus far """

    def __init__(self, nzb_name=None, nzb_folder=None, id=None, issueid=None, comicid=None, prov=None, queue=None, oneoffinfo=None):
        """
        nzb_name : Full name of the nzb file that has returned as a fail.
        nzb_folder: Full path to the folder of the failed download.
        """
        self.nzb_name = nzb_name
        self.nzb_folder = nzb_folder
        #if nzb_folder: self.nzb_folder = nzb_folder

        self.log = ""

        self.id = id
        if issueid:
            self.issueid = issueid
        else:
            self.issueid = None
        if comicid:
            self.comicid = comicid
        else:
            self.comicid = None

        if oneoffinfo:
            self.oneoffinfo = oneoffinfo
        else:
            self.oneoffinfo = None

        self.prov = prov
        if queue: self.queue = queue
        self.valreturn = []

    def _log(self, message, level=logger.message):
        """
        A wrapper for the internal logger which also keeps track of messages and saves them to a string

        message: The string to log (unicode)
        level: The log level to use (optional)
        """
        self.log += message + '\n'

    def Process(self):
        module = '[FAILED-DOWNLOAD]'

        myDB = db.DBConnection()

        if self.nzb_name and self.nzb_folder:
            self._log('Failed download has been detected: ' + self.nzb_name + ' in ' + self.nzb_folder)

            #since this has already been passed through the search module, which holds the IssueID in the nzblog,
            #let's find the matching nzbname and pass it the IssueID in order to mark it as Failed and then return
            #to the search module and continue trucking along.

            nzbname = self.nzb_name
            #remove extensions from nzb_name if they somehow got through (Experimental most likely)
            extensions = ('.cbr', '.cbz')

            if nzbname.lower().endswith(extensions):
                fd, ext = os.path.splitext(nzbname)
                self._log("Removed extension from nzb: " + ext)
                nzbname = re.sub(str(ext), '', str(nzbname))

            #replace spaces
            nzbname = re.sub(' ', '.', str(nzbname))
            nzbname = re.sub('[\,\:\?\'\(\)]', '', str(nzbname))
            nzbname = re.sub('[\&]', 'and', str(nzbname))
            nzbname = re.sub('_', '.', str(nzbname))

            logger.fdebug(module + ' After conversions, nzbname is : ' + str(nzbname))
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

        else:
            issueid = self.issueid
            nzbiss = myDB.selectone("SELECT * from nzblog WHERE IssueID=?", [issueid]).fetchone()
            if nzbiss is None:
                logger.info(module + ' Cannot locate corresponding record in download history. This will be implemented soon.')
                self.valreturn.append({"self.log": self.log,
                                       "mode": 'stop'})
                return self.queue.put(self.valreturn)

            nzbname = nzbiss['NZBName']

        # find the provider.
        self.prov = nzbiss['PROVIDER']
        logger.info(module + ' Provider: ' + self.prov)

        # grab the id.
        self.id = nzbiss['ID']
        logger.info(module + ' ID: ' + self.id)
        annchk = "no"

        if 'annual' in nzbname.lower():
            logger.info(module + ' Annual detected.')
            annchk = "yes"
            issuenzb = myDB.selectone("SELECT * from annuals WHERE IssueID=? AND ComicName NOT NULL", [issueid]).fetchone()
        else:
            issuenzb = myDB.selectone("SELECT * from issues WHERE IssueID=? AND ComicName NOT NULL", [issueid]).fetchone()

        if issuenzb is not None:
            logger.info(module + ' issuenzb found.')
            if helpers.is_number(issueid):
                sandwich = int(issuenzb['IssueID'])
        else:
            logger.info(module + ' issuenzb not found.')
            #if it's non-numeric, it contains a 'G' at the beginning indicating it's a multi-volume
            #using GCD data. Set sandwich to 1 so it will bypass and continue post-processing.
            if 'S' in issueid:
                sandwich = issueid
            elif 'G' in issueid or '-' in issueid:
                sandwich = 1
        if helpers.is_number(sandwich):
            if sandwich < 900000:
            # if sandwich is less than 900000 it's a normal watchlist download. Bypass.
                pass
        else:
            logger.info('Failed download handling for story-arcs and one-off\'s are not supported yet. Be patient!')
            self._log(' Unable to locate downloaded file to rename. PostProcessing aborted.')
            self.valreturn.append({"self.log": self.log,
                                   "mode": 'stop'})

            return self.queue.put(self.valreturn)

        comicid = issuenzb['ComicID']
        issuenumOG = issuenzb['Issue_Number']
        logger.info(module + ' Successfully detected as : ' + issuenzb['ComicName'] + ' issue: ' + str(issuenzb['Issue_Number']) + ' that was downloaded using ' + self.prov)
        self._log('Successfully detected as : ' + issuenzb['ComicName'] + ' issue: ' + str(issuenzb['Issue_Number']) + ' downloaded using ' + self.prov)

        logger.info(module + ' Marking as a Failed Download.')
        self._log('Marking as a Failed Download.')

        ctrlVal = {"IssueID": issueid}
        Vals = {"Status":    'Failed'}
        myDB.upsert("issues", Vals, ctrlVal)

        ctrlVal = {"ID":       self.id,
                   "Provider": self.prov,
                   "NZBName":  nzbname}
        Vals = {"Status":       'Failed',
                "ComicName":    issuenzb['ComicName'],
                "Issue_Number": issuenzb['Issue_Number'],
                "IssueID":      issueid,
                "ComicID":      comicid,
                "DateFailed":   helpers.now()}
        myDB.upsert("failed", Vals, ctrlVal)

        logger.info(module + ' Successfully marked as Failed.')
        self._log('Successfully marked as Failed.')

        if mylar.FAILED_AUTO:
            logger.info(module + ' Sending back to search to see if we can find something that will not fail.')
            self._log('Sending back to search to see if we can find something better that will not fail.')
            self.valreturn.append({"self.log":    self.log,
                                   "mode":        'retry',
                                   "issueid":     issueid,
                                   "comicid":     comicid,
                                   "comicname":   issuenzb['ComicName'],
                                   "issuenumber": issuenzb['Issue_Number'],
                                   "annchk":      annchk})

            return self.queue.put(self.valreturn)
        else:
            logger.info(module + ' Stopping search here as automatic handling of failed downloads is not enabled *hint*')
            self._log('Stopping search here as automatic handling of failed downloads is not enabled *hint*')
            self.valreturn.append({"self.log": self.log,
                                   "mode": 'stop'})
            return self.queue.put(self.valreturn)


    def failed_check(self):
        #issueid = self.issueid
        #comicid = self.comicid

        # ID = ID passed by search upon a match upon preparing to send it to client to download.
        #     ID is provider dependent, so the same file should be different for every provider.
        module = '[FAILED_DOWNLOAD_CHECKER]'

        myDB = db.DBConnection()
        # Querying on NZBName alone will result in all downloads regardless of provider.
        # This will make sure that the files being downloaded are different regardless of provider.
        # Perhaps later improvement might be to break it down by provider so that Mylar will attempt to
        # download same issues on different providers (albeit it shouldn't matter, if it's broke it's broke).
        logger.info('prov  : ' + str(self.prov) + '[' + str(self.id) + ']')
        # if this is from nzbhydra, we need to rejig the id line so that the searchid is removed since it's always unique to the search.
        if 'indexerguid' in self.id:
            st = self.id.find('searchid:')
            end = self.id.find(',',st)
            self.id = '%' + self.id[:st] + '%' + self.id[end+1:len(self.id)-1] + '%'
            chk_fail = myDB.selectone('SELECT * FROM failed WHERE ID LIKE ?', [self.id]).fetchone()
        else:
            chk_fail = myDB.selectone('SELECT * FROM failed WHERE ID=?', [self.id]).fetchone()

        if chk_fail is None:
            logger.info(module + ' Successfully marked this download as Good for downloadable content')
            return 'Good'
        else:
            if chk_fail['status'] == 'Good':
                logger.info(module + ' result has a status of GOOD - which means it does not currently exist in the failed download list.')
                return chk_fail['status']
            elif chk_fail['status'] == 'Failed':
                logger.info(module + ' result has a status of FAIL which indicates it is not a good choice to download.')
                logger.info(module + ' continuing search for another download.')
                return chk_fail['status']
            elif chk_fail['status'] == 'Retry':
                logger.info(module + ' result has a status of RETRY which indicates it was a failed download that retried .')
                return chk_fail['status']
            elif chk_fail['status'] == 'Retrysame':
                logger.info(module + ' result has a status of RETRYSAME which indicates it was a failed download that retried the initial download.')
                return chk_fail['status']
            else:
                logger.info(module + ' result has a status of ' + chk_fail['status'] + '. I am not sure what to do now.')
                return "nope"

    def markFailed(self):
        #use this to forcibly mark a single issue as being Failed (ie. if a search result is sent to a client, but the result
        #ends up passing in a 404 or something that makes it so that the download can't be initiated).
        module = '[FAILED-DOWNLOAD]'

        myDB = db.DBConnection()

        logger.info(module + ' Marking as a Failed Download.')

        logger.fdebug(module + 'nzb_name: ' + self.nzb_name)
        logger.fdebug(module + 'issueid: ' + str(self.issueid))
        logger.fdebug(module + 'nzb_id: ' + str(self.id))
        logger.fdebug(module + 'prov: ' + self.prov)

        logger.fdebug('oneoffinfo: ' + str(self.oneoffinfo))
        if self.oneoffinfo:
            ComicName = self.oneoffinfo['ComicName']
            IssueNumber = self.oneoffinfo['IssueNumber']

        else:
            if 'annual' in self.nzb_name.lower():
                logger.info(module + ' Annual detected.')
                annchk = "yes"
                issuenzb = myDB.selectone("SELECT * from annuals WHERE IssueID=? AND ComicName NOT NULL", [self.issueid]).fetchone()
            else:
                issuenzb = myDB.selectone("SELECT * from issues WHERE IssueID=? AND ComicName NOT NULL", [self.issueid]).fetchone()

            ctrlVal = {"IssueID": self.issueid}
            Vals = {"Status":    'Failed'}
            myDB.upsert("issues", Vals, ctrlVal)
            ComicName = issuenzb['ComicName']
            IssueNumber = issuenzb['Issue_Number']

        ctrlVal = {"ID":       self.id,
                   "Provider": self.prov,
                   "NZBName":  self.nzb_name}
        Vals = {"Status":       'Failed',
                "ComicName":    ComicName,
                "Issue_Number": IssueNumber,
                "IssueID":      self.issueid,
                "ComicID":      self.comicid,
                "DateFailed":   helpers.now()}
        myDB.upsert("failed", Vals, ctrlVal)

        logger.info(module + ' Successfully marked as Failed.')
