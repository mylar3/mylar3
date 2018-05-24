#!/usr/bin/python
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

import urllib
import requests
import os
import sys
import re
import time
import logger
import mylar

class SABnzbd(object):
    def __init__(self, params):
        #self.sab_url = sab_host + '/api'
        #self.sab_apikey = 'e90f54f4f757447a20a4fa89089a83ed'
        self.sab_url = mylar.CONFIG.SAB_HOST + '/api'
        self.params = params

    def sender(self):
        try:
            from requests.packages.urllib3 import disable_warnings
            disable_warnings()
        except:
            logger.info('Unable to disable https warnings. Expect some spam if using https nzb providers.')

        try:
            logger.info('parameters set to %s' % self.params)
            logger.info('sending now to %s' % self.sab_url)
            sendit = requests.post(self.sab_url, data=self.params, verify=False)
        except:
            logger.info('Failed to send to client.')
            return {'status': False}
        else:
            sendresponse = sendit.json()
            logger.info(sendresponse)
            if sendresponse['status'] is True:
                queue_params = {'status': True,
                                'nzo_id': ''.join(sendresponse['nzo_ids']),
                                'queue':  {'mode':   'queue',
                                           'search':  ''.join(sendresponse['nzo_ids']),
                                           'output':  'json',
                                           'apikey':  mylar.CONFIG.SAB_APIKEY}}

            else:
                queue_params = {'status': False}

            return queue_params

    def processor(self):
        sendresponse = self.params['nzo_id']
        try:
            logger.info('sending now to %s' % self.sab_url)
            logger.info('parameters set to %s' % self.params)
            time.sleep(5)   #pause 5 seconds before monitoring just so it hits the queue
            h = requests.get(self.sab_url, params=self.params['queue'], verify=False)
        except Exception as e:
            logger.info('uh-oh: %s' % e)
            return self.historycheck(sendresponse)
        else:
            queueresponse = h.json()
            logger.info('successfully queried the queue for status')
            try:
                queueinfo = queueresponse['queue']
                logger.info('queue: %s' % queueresponse)
                logger.info('Queue status : %s' % queueinfo['status'])
                logger.info('Queue mbleft : %s' % queueinfo['mbleft'])
                while any([str(queueinfo['status']) == 'Downloading', str(queueinfo['status']) == 'Idle']) and float(queueinfo['mbleft']) > 0:
                    logger.info('queue_params: %s' % self.params['queue'])
                    queue_resp = requests.get(self.sab_url, params=self.params['queue'], verify=False)
                    queueresp = queue_resp.json()
                    queueinfo = queueresp['queue']
                    logger.info('status: %s' % queueinfo['status'])
                    logger.info('mbleft: %s' % queueinfo['mbleft'])
                    logger.info('timeleft: %s' % queueinfo['timeleft'])
                    logger.info('eta: %s' % queueinfo['eta'])
                    time.sleep(5)
            except Exception as e:
                logger.warn('error: %s' % e)

            logger.info('File has now downloaded!')
            return self.historycheck(sendresponse)

    def historycheck(self, sendresponse):
        hist_params = {'mode':      'history',
                       'category':  mylar.CONFIG.SAB_CATEGORY,
                       'failed':    0,
                       'output':    'json',
                       'apikey':    mylar.CONFIG.SAB_APIKEY}
        hist = requests.get(self.sab_url, params=hist_params, verify=False)
        historyresponse = hist.json()
        #logger.info(historyresponse)
        histqueue = historyresponse['history']
        found = {'status': False}
        while found['status'] is False:
            try:
                for hq in histqueue['slots']:
                    #logger.info('nzo_id: %s --- %s [%s]' % (hq['nzo_id'], sendresponse, hq['status']))
                    if hq['nzo_id'] == sendresponse and hq['status'] == 'Completed':
                        logger.info('found matching completed item in history. Job has a status of %s' % hq['status'])
                        if os.path.isfile(hq['storage']):
                            logger.info('location found @ %s' % hq['storage'])
                            found = {'status':   True,
                                     'name':     re.sub('.nzb', '', hq['nzb_name']).strip(),
                                     'location': os.path.abspath(os.path.join(hq['storage'], os.pardir)),
                                     'failed':   False}
                            break
                        else:
                            logger.info('no file found where it should be @ %s - is there another script that moves things after completion ?' % hq['storage'])
                            break
                    elif hq['nzo_id'] == sendresponse and hq['status'] == 'Failed':
                        #get the stage / error message and see what we can do
                        stage = hq['stage_log']
                        for x in stage[0]:
                            if 'Failed' in x['actions'] and any([x['name'] == 'Unpack', x['name'] == 'Repair']):
                                if 'moving' in x['actions']:
                                    logger.warn('There was a failure in SABnzbd during the unpack/repair phase that caused a failure: %s' % x['actions'])
                                else:
                                    logger.warn('Failure occured during the Unpack/Repair phase of SABnzbd. This is probably a bad file: %s' % x['actions'])
                                    if mylar.FAILED_DOWNLOAD_HANDLING is True:
                                        found = {'status':   True,
                                                 'name':     re.sub('.nzb', '', hq['nzb_name']).strip(),
                                                 'location': os.path.abspath(os.path.join(hq['storage'], os.pardir)),
                                                 'failed':   True}
                                break
                        break
            except Exception as e:
                logger.warn('error %s' % e)
                break

        return found
