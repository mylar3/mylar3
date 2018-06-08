#!/usr/bin/python
#  This file is part of Harpoon.
#
#  Harpoon is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Harpoon is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Harpoon.  If not, see <http://www.gnu.org/licenses/>.

import optparse
import xmlrpclib
from base64 import standard_b64encode
from xml.dom.minidom import parseString
import os
import sys
import re
import time
import mylar
import logger

class NZBGet(object):
    def __init__(self):

        if mylar.CONFIG.NZBGET_HOST[:5] == 'https':
            protocol = "https"
            nzbget_host = mylar.CONFIG.NZBGET_HOST[8:]
        elif mylar.CONFIG.NZBGET_HOST[:4] == 'http':
            protocol = "http"
            nzbget_host = mylar.CONFIG.NZBGET_HOST[7:]
        url = '%s://'
        val = (protocol,)
        if mylar.CONFIG.NZBGET_USERNAME is not None:
            url = url + '%s:'
            val = val + (mylar.CONFIG.NZBGET_USERNAME,)
        if mylar.CONFIG.NZBGET_PASSWORD is not None:
            url = url + '%s'
            val = val + (mylar.CONFIG.NZBGET_PASSWORD,)
        if any([mylar.CONFIG.NZBGET_USERNAME, mylar.CONFIG.NZBGET_PASSWORD]):
            url = url + '@%s:%s/xmlrpc'
        else:
            url = url + '%s:%s/xmlrpc'
        val = val + (nzbget_host,mylar.CONFIG.NZBGET_PORT,)
        self.nzb_url = (url % val)
        self.server = xmlrpclib.ServerProxy(self.nzb_url) #,allow_none=True)

    def sender(self, filename, test=False):
        if mylar.CONFIG.NZBGET_PRIORITY:
            if any([mylar.CONFIG.NZBGET_PRIORITY == 'Default', mylar.CONFIG.NZBGET_PRIORITY == 'Normal']):
                nzbgetpriority = 0
            elif mylar.CONFIG.NZBGET_PRIORITY == 'Low':
                nzbgetpriority = -50
            elif mylar.CONFIG.NZBGET_PRIORITY == 'High':
                nzbgetpriority = 50
            #there's no priority for "paused", so set "Very Low" and deal with that later...
            elif mylar.CONFIG.NZBGET_PRIORITY == 'Paused':
                nzbgetpriority = -100
        else:
            #if nzbget priority isn't selected, default to Normal (0)
            nzbgetpriority = 0


        in_file = open(filename, 'r')
        nzbcontent = in_file.read()
        in_file.close()
        nzbcontent64 = standard_b64encode(nzbcontent)
        try:
            logger.fdebug('sending now to %s' % self.nzb_url)
            if mylar.CONFIG.NZBGET_CATEGORY is None:
                nzb_category = ''
            else:
                nzb_category = mylar.CONFIG.NZBGET_CATEGORY
            sendresponse = self.server.append(filename, nzbcontent64, nzb_category, nzbgetpriority, False, False, '', 0, 'SCORE')
        except Exception as e:
            logger.warn('uh-oh: %s' % e)
            return {'status': False}
        else:
            if sendresponse <= 0:
                logger.warn('Invalid response received after sending to NZBGet: %s' % sendresponse)
                return {'status': False}
            else:
                #sendresponse is the NZBID that we use to track the progress....
                return {'status': True,
                        'NZBID':  sendresponse}


    def processor(self, nzbinfo):
        nzbid = nzbinfo['NZBID']
        try:
            logger.fdebug('Now checking the active queue of nzbget for the download')
            queueinfo = self.server.listgroups()
        except Exception as e:
            logger.warn('Error attempting to retrieve active queue listing: %s' % e)
            return {'status': False}
        else:
            logger.fdebug('valid queue result returned. Analyzing...')
            queuedl = [qu for qu in queueinfo if qu['NZBID'] == nzbid]
            if len(queuedl) == 0:
                logger.warn('Unable to locate item in active queue. Could it be finished already ?')
                return self.historycheck(nzbid)

            stat = False
            while stat is False:
                time.sleep(10)
                queueinfo = self.server.listgroups()
                queuedl = [qu for qu in queueinfo if qu['NZBID'] == nzbid]
                if len(queuedl) == 0:
                    logger.fdebug('Item is no longer in active queue. It should be finished by my calculations')
                    stat = True
                else:
                    logger.fdebug('status: %s' % queuedl[0]['Status'])
                    logger.fdebug('name: %s' % queuedl[0]['NZBName'])
                    logger.fdebug('FileSize: %sMB' % queuedl[0]['FileSizeMB'])
                    logger.fdebug('Download Left: %sMB' % queuedl[0]['RemainingSizeMB'])
                    logger.fdebug('health: %s' % (queuedl[0]['Health']/10))
                    logger.fdebug('destination: %s' % queuedl[0]['DestDir'])

            logger.fdebug('File has now downloaded!')
            time.sleep(5)  #wait some seconds so shit can get written to history properly
            return self.historycheck(nzbid)

    def historycheck(self, nzbid):
        history = self.server.history()
        found = False
        hq = [hs for hs in history if hs['NZBID'] == nzbid and 'SUCCESS' in hs['Status']]
        if len(hq) > 0:
            logger.fdebug('found matching completed item in history. Job has a status of %s' % hq[0]['Status'])
            if hq[0]['DownloadedSizeMB'] == hq[0]['FileSizeMB']:
                logger.fdebug('%s has final file size of %sMB' % (hq[0]['Name'], hq[0]['DownloadedSizeMB']))
                if os.path.isdir(hq[0]['DestDir']):
                    logger.fdebug('location found @ %s' % hq[0]['DestDir'])
                    return {'status':   True,
                            'name':     re.sub('.nzb', '', hq[0]['NZBName']).strip(),
                            'location': hq[0]['DestDir'],
                            'failed':   False}

                else:
                    logger.warn('no file found where it should be @ %s - is there another script that moves things after completion ?' % hq[0]['DestDir'])
                    return {'status': False}
        else:
            logger.warn('Could not find completed item in history')
            return {'status': False}
