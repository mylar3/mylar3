#  This file is part of Mylar.
# -*- coding: utf-8 -*-
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

import Queue
import threading
import mylar
import logger

class Process(object):

    def __init__(self, nzb_name, nzb_folder, failed=False, issueid=None, comicid=None, apicall=False):
        self.nzb_name = nzb_name
        self.nzb_folder = nzb_folder
        self.failed = failed
        self.issueid = issueid
        self.comicid = comicid
        self.apicall = apicall

    def post_process(self):
        if self.failed == '0':
            self.failed = False
        elif self.failed == '1':
            self.failed = True

        queue = Queue.Queue()
        retry_outside = False

        if self.failed is False:
            PostProcess = mylar.PostProcessor.PostProcessor(self.nzb_name, self.nzb_folder, self.issueid, queue=queue, comicid=self.comicid, apicall=self.apicall)
            if any([self.nzb_name == 'Manual Run', self.nzb_name == 'Manual+Run', self.apicall is True, self.issueid is not None]):
                threading.Thread(target=PostProcess.Process).start()
            else:
                thread_ = threading.Thread(target=PostProcess.Process, name="Post-Processing")
                thread_.start()
                thread_.join()
                chk = queue.get()
                while True:
                    if chk[0]['mode'] == 'fail':
                        logger.info('Initiating Failed Download handling')
                        if chk[0]['annchk'] == 'no':
                            mode = 'want'
                        else:
                            mode = 'want_ann'
                        self.failed = True
                        break
                    elif chk[0]['mode'] == 'stop':
                        break
                    elif chk[0]['mode'] == 'outside':
                        retry_outside = True
                        break
                    else:
                        logger.error('mode is unsupported: ' + chk[0]['mode'])
                        break

        if self.failed is True:
            if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING is True:
                #drop the if-else continuation so we can drop down to this from the above if statement.
                logger.info('Initiating Failed Download handling for this download.')
                FailProcess = mylar.Failed.FailedProcessor(nzb_name=self.nzb_name, nzb_folder=self.nzb_folder, queue=queue)
                thread_ = threading.Thread(target=FailProcess.Process, name="FAILED Post-Processing")
                thread_.start()
                thread_.join()
                failchk = queue.get()
                if failchk[0]['mode'] == 'retry':
                    logger.info('Attempting to return to search module with ' + str(failchk[0]['issueid']))
                    if failchk[0]['annchk'] == 'no':
                        mode = 'want'
                    else:
                        mode = 'want_ann'
                    qq = mylar.webserve.WebInterface()
                    qt = qq.queueit(mode=mode, ComicName=failchk[0]['comicname'], ComicIssue=failchk[0]['issuenumber'], ComicID=failchk[0]['comicid'], IssueID=failchk[0]['issueid'], manualsearch=True)
                elif failchk[0]['mode'] == 'stop':
                    pass
                else:
                    logger.error('mode is unsupported: ' + failchk[0]['mode'])
            else:
                logger.warn('Failed Download Handling is not enabled. Leaving Failed Download as-is.')

        if retry_outside:
            PostProcess = mylar.PostProcessor.PostProcessor('Manual Run', self.nzb_folder, queue=queue)
            thread_ = threading.Thread(target=PostProcess.Process, name="Post-Processing")
            thread_.start()
            thread_.join()
            chk = queue.get()
            while True:
                if chk[0]['mode'] == 'fail':
                    logger.info('Initiating Failed Download handling')
                    if chk[0]['annchk'] == 'no':
                        mode = 'want'
                    else:
                        mode = 'want_ann'
                    self.failed = True
                    break
                elif chk[0]['mode'] == 'stop':
                    break
                else:
                    logger.error('mode is unsupported: ' + chk[0]['mode'])
                    break
        return
