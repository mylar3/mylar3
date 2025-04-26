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
import xmlrpc.client
from base64 import standard_b64encode
from xml.dom.minidom import parseString
import xmlrpc.client
import http.client
import os
import sys
import re
import time
import mylar
from mylar import logger, cdh_mapping

class NZBGet(object):
    def __init__(self):

        if mylar.CONFIG.NZBGET_HOST[:5] == 'https':
            protocol = "https"
            nzbget_host = mylar.CONFIG.NZBGET_HOST[8:]
        elif mylar.CONFIG.NZBGET_HOST[:4] == 'http':
            protocol = "http"
            nzbget_host = mylar.CONFIG.NZBGET_HOST[7:]
        else:
            logger.warn('[NZB-GET] You need to specify the protocol for your nzbget instance (ie. http:// or https://). You provided: %s' % (mylar.CONFIG.NZBGET_HOST))
            return {'status': False}
        url = '%s://%s:%s'
        val = (protocol,nzbget_host,mylar.CONFIG.NZBGET_PORT)
        if mylar.CONFIG.NZBGET_SUB is not None:
            if not mylar.CONFIG.NZBGET_SUB.startswith('/'):
                mylar.CONFIG.NZBGET_SUB = '/' + mylar.CONFIG.NZBGET_SUB
            if mylar.CONFIG.NZBGET_SUB.endswith('/'):
                mylar.CONFIG.NZBGET_SUB = mylar.CONFIG.NZBGET_SUB[:-1]
            url = '%s://%s:%s%s'
            val = val + (mylar.CONFIG.NZBGET_SUB,)

        logon_info = ''
        if mylar.CONFIG.NZBGET_USERNAME is not None:
            logon_info = '%s:'
            val = val + (mylar.CONFIG.NZBGET_USERNAME,)
        if mylar.CONFIG.NZBGET_PASSWORD is not None:
            if logon_info == '':
                logon_info = ':%s'
            else:
                logon_info += '%s'
            val = val + (mylar.CONFIG.NZBGET_PASSWORD,)
        if logon_info != '':
            url = url + '/' + logon_info
        url = url + '/xmlrpc'

        if mylar.CONFIG.NZBGET_SUB is not None:
            self.display_url = '%s://%s:%s%s/xmlrpc' % (protocol, nzbget_host, mylar.CONFIG.NZBGET_PORT, mylar.CONFIG.NZBGET_SUB)
        else:
            self.display_url = '%s://%s:%s/xmlrpc' % (protocol, nzbget_host, mylar.CONFIG.NZBGET_PORT)

        self.nzb_url = (url % val)

        self.server = xmlrpc.client.ServerProxy(self.nzb_url) #,allow_none=True)

    def sender(self, filename, test=False):
        if mylar.CONFIG.NZBGET_PRIORITY:
            if any([mylar.CONFIG.NZBGET_PRIORITY == 'Default', mylar.CONFIG.NZBGET_PRIORITY == 'Normal']):
                nzbgetpriority = 0
            elif mylar.CONFIG.NZBGET_PRIORITY == 'Low':
                nzbgetpriority = -50
            elif mylar.CONFIG.NZBGET_PRIORITY == 'High':
                nzbgetpriority = 50
            elif mylar.CONFIG.NZBGET_PRIORITY == 'Very High':
                nzbgetpriority = 100
            elif mylar.CONFIG.NZBGET_PRIORITY == 'Force':
                nzbgetpriority = 900
            #there's no priority for "paused", so set "Very Low" and deal with that later...
            elif mylar.CONFIG.NZBGET_PRIORITY == 'Paused':
                nzbgetpriority = -100
        else:
            #if nzbget priority isn't selected, default to Normal (0)
            nzbgetpriority = 0


        with open(filename, 'rb') as in_file:
            nzbcontent = in_file.read()
            nzbcontent64 = standard_b64encode(nzbcontent).decode('utf-8')

        try:
            logger.fdebug('sending now to %s' % self.display_url)
            if mylar.CONFIG.NZBGET_CATEGORY is None:
                nzb_category = ''
            else:
                nzb_category = mylar.CONFIG.NZBGET_CATEGORY
            sendresponse = self.server.append(filename, nzbcontent64, nzb_category, nzbgetpriority, False, False, '', 0, 'SCORE')
        except http.client.socket.error as e:
            nzb_url = re.sub(mylar.CONFIG.NZBGET_PASSWORD, 'REDACTED', str(e))
            logger.error('Please check your NZBget host and port (if it is running). Tested against: %s' % nzb_url)
            return {'status': False}
        except xmlrpc.client.ProtocolError as e:
            logger.info(e,)
            if e.errmsg == "Unauthorized":
                err = re.sub(mylar.CONFIG.NZBGET_PASSWORD, 'REDACTED', e.errmsg)
                logger.error('Unauthorized username / password provided: %s' % err)
                return {'status': False}
            else:
                err = "Protocol Error: %s" % re.sub(mylar.CONFIG.NZBGET_PASSWORD, 'REDACTED', e.errmsg)
                logger.error('Protocol error returned: %s' % err)
                return {'status': False}
        except Exception as e:
            logger.warn('uh-oh: %s' % re.sub(mylar.CONFIG.NZBGET_PASSWORD, 'REDACTED', str(e)))
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
                logger.warn('Unable to locate NZBID %s in active queue. Could it be finished already ?' % nzbid)
                return self.historycheck(nzbinfo)

            stat = False
            double_pp = False
            double_type = None
            while stat is False:
                time.sleep(10)
                queueinfo = self.server.listgroups()
                queuedl = [qu for qu in queueinfo if qu['NZBID'] == nzbid]
                if len(queuedl) == 0:
                    logger.fdebug('Item is no longer in active queue. It should be finished by my calculations')
                    stat = True
                else:
                    if 'comicrn' in queuedl[0]['PostInfoText'].lower():
                        double_pp = True
                        double_type = 'ComicRN'
                    elif 'nzbtomylar' in queuedl[0]['PostInfoText'].lower():
                        double_pp = True
                        double_type = 'nzbToMylar'

                    if all([len(queuedl[0]['ScriptStatuses']) > 0, double_pp is False]):
                        for x in queuedl[0]['ScriptStatuses']:
                            if 'comicrn' in x['Name'].lower():
                                double_pp = True
                                double_type = 'ComicRN'
                                break
                            elif 'nzbtomylar' in x['Name'].lower():
                                double_pp = True
                                double_type = 'nzbToMylar'
                                break

                    if all([len(queuedl[0]['Parameters']) > 0, double_pp is False]):
                        for x in queuedl[0]['Parameters']:
                            if all(['comicrn' in x['Name'].lower(), x['Value'] == 'yes']):
                                double_pp = True
                                double_type = 'ComicRN'
                                break
                            elif all(['nzbtomylar' in x['Name'].lower(), x['Value'] == 'yes']):
                                double_pp = True
                                double_type = 'nzbToMylar'
                                break


                    if double_pp is True:
                        logger.warn('%s has been detected as being active for this category & download. Completed Download Handling will NOT be performed due to this.' % double_type)
                        logger.warn('Either disable Completed Download Handling for NZBGet within Mylar, or remove %s from your category script in NZBGet.' % double_type)
                        return {'status': 'double-pp', 'failed': False}

                    logger.fdebug('status: %s' % queuedl[0]['Status'])
                    logger.fdebug('name: %s' % queuedl[0]['NZBName'])
                    logger.fdebug('FileSize: %sMB' % queuedl[0]['FileSizeMB'])
                    logger.fdebug('Download Left: %sMB' % queuedl[0]['RemainingSizeMB'])
                    logger.fdebug('health: %s' % (queuedl[0]['Health']/10))
                    logger.fdebug('destination: %s' % queuedl[0]['DestDir'])

            logger.fdebug('File has now downloaded!')
            time.sleep(5)  #wait some seconds so shit can get written to history properly
            return self.historycheck(nzbinfo)

    def historycheck(self, nzbinfo):
        nzbid = nzbinfo['NZBID']
        history = self.server.history(True)
        found = False
        destdir = None
        double_pp = False
        hq = [hs for hs in history if hs['NZBID'] == nzbid] # and ('SUCCESS' in hs['Status'] or ('COPY' in hs['Status']))]
        if len(hq) > 0:
            logger.fdebug('found matching completed item in history. Job has a status of %s' % hq[0]['Status'])
            if len(hq[0]['ScriptStatuses']) > 0:
                for x in hq[0]['ScriptStatuses']:
                    if 'comicrn' in x['Name'].lower():
                        double_pp = True
                        break

            if all([len(hq[0]['Parameters']) > 0, double_pp is False]):
                for x in hq[0]['Parameters']:
                    if all(['comicrn' in x['Name'].lower(), x['Value'] == 'yes']):
                        double_pp = True
                        break

            if double_pp is True:
                logger.warn('ComicRN has been detected as being active for this category & download. Completed Download Handling will NOT be performed due to this.')
                logger.warn('Either disable Completed Download Handling for NZBGet within Mylar, or remove ComicRN from your category script in NZBGet.')
                return {'status': 'double-pp', 'failed': False}

            if all(['SUCCESS' in hq[0]['Status'], (hq[0]['FileSizeMB']*.95) <= hq[0]['DownloadedSizeMB'] <= (hq[0]['FileSizeMB']*1.05)]):
                logger.fdebug('%s has final file size of %sMB' % (hq[0]['Name'], hq[0]['DownloadedSizeMB']))
                if os.path.isdir(hq[0]['DestDir']):
                    destdir = hq[0]['DestDir']
                    logger.fdebug('location found @ %s' % destdir)
                elif mylar.CONFIG.NZBGET_DIRECTORY is None:
                    logger.fdebug('Unable to locate path (%s) on the machine that is running Mylar. If Mylar and nzbget are on separate machines, you need to set a directory location that is accessible to both' % hq[0]['DestDir'])
                    return {'status': 'file not found', 'failed': False}

            elif all(['COPY' in hq[0]['Status'], int(hq[0]['FileSizeMB']) > 0, hq[0]['DeleteStatus'] == 'COPY']):
                if hq[0]['Deleted'] is False:
                    config = self.server.config()
                    cDestDir = None
                    for x in config:
                        if x['Name'] == 'TempDir':
                            cTempDir = x['Value']
                        elif x['Name'] == 'DestDir':
                            cDestDir = x['Value']
                        if cDestDir is not None:
                            break

                    if cTempDir in hq[0]['DestDir']:
                        destdir2 = re.sub(cTempDir, cDestDir, hq[0]['DestDir']).strip()
                        if not destdir2.endswith(os.sep):
                            destdir2 = destdir2 + os.sep
                        destdir = os.path.join(destdir2, hq[0]['Name'])
                        logger.fdebug('NZBGET Destination dir set to: %s' % destdir)
                else:
                    history_del = self.server.editqueue('HistoryMarkBad', '', hq[0]['NZBID'])
                    if history_del is False:
                        logger.fdebug('[NZBGET] Unable to delete item (%s)from history so I can redownload a clean copy.' % hq[0]['NZBName'])
                        return {'status': 'failure', 'failed': False}
                    else:
                        logger.fdebug('[NZBGET] Successfully removed prior item (%s) from history. Attempting to get another version.' % hq[0]['NZBName'])
                        return {'status':   True,
                                'name':     re.sub('.nzb', '', hq[0]['NZBName']).strip(),
                                'location': os.path.abspath(os.path.join(hq[0]['DestDir'], os.pardir)),
                                'failed':   True,
                                'issueid':  nzbinfo['issueid'],
                                'comicid':  nzbinfo['comicid'],
                                'apicall':  True,
                                'ddl':      False,
                                'download_info': nzbinfo['download_info']}
            elif 'FAILURE' in hq[0]['Status']:
                logger.warn('item is in a %s status. Considering this a FAILED attempted download for NZBID %s - %s' % (hq[0]['Status'], hq[0]['NZBID'], hq[0]['NZBName']))
                return {'status':   True,
                        'name':     re.sub('.nzb', '', hq[0]['NZBName']).strip(),
                        'location': os.path.abspath(os.path.join(hq[0]['DestDir'], os.pardir)),
                        'failed':   True,
                        'issueid':  nzbinfo['issueid'],
                        'comicid':  nzbinfo['comicid'],
                        'apicall':  True,
                        'ddl':      False,
                        'download_info': nzbinfo['download_info']}
            else:
                logger.warn('no file found where it should be @ %s - is there another script that moves things after completion ?' % hq[0]['DestDir'])
                return {'status': 'file not found', 'failed': False}

            if mylar.CONFIG.NZBGET_DIRECTORY is not None:
                logger.fdebug('DestDir being passed to cdh conversion is: %s' % hq[0]['DestDir'])
                cdh = cdh_mapping.CDH_MAP(hq[0]['DestDir'], nzbget=True, nzbget_server=self.server)
                destdir = cdh.the_sequence()
                if destdir is not None:
                    logger.fdebug('NZBGet Destination folder Successfully set via config to: %s' % destdir)
                else:
                    logger.fdebug('Unable to locate path (%s) on the machine that is running Mylar. If Mylar and nzbget are on separate machines, you need to set a directory location that is accessible to both' % hq[0]['DestDir'])
                    return {'status': 'file not found', 'failed': False}

            if destdir is not None:
                return {'status':   True,
                       'name':     re.sub('.nzb', '', hq[0]['Name']).strip(),
                       'location': destdir,
                       'failed':   False,
                       'issueid':  nzbinfo['issueid'],
                       'comicid':  nzbinfo['comicid'],
                       'apicall':  True,
                       'ddl':      False,
                       'download_info': nzbinfo['download_info']}
        else:
            logger.warn('Could not find completed NZBID %s in history' % nzbid)
            return {'status': False}
