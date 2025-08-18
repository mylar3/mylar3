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

import urllib.request, urllib.parse, urllib.error
import requests
import ntpath
import pathlib
import os
import sys
import re
import time
from packaging.version import parse as parse_version
import mylar
from mylar import logger, cdh_mapping

class SABnzbd(object):
    def __init__(self, params):
        self.sab_url = mylar.CONFIG.SAB_HOST + '/api'
        self.params = params

    def sender(self, chkstatus=False):
        try:
            from requests.packages.urllib3 import disable_warnings
            disable_warnings()
        except:
            logger.warn('Unable to disable https warnings. Expect some spam if using https nzb providers.')

        try:
            if chkstatus is True:
                sendit = requests.get(self.sab_url, params=self.params, verify=False)
            else:
                tmp_apikey = self.params.pop('apikey')
                logger.fdebug('parameters set to %s' % self.params)
                self.params['apikey'] = tmp_apikey
                logger.fdebug('sending now to %s' % self.sab_url)
                sendit = requests.post(self.sab_url, data=self.params, verify=False)
        except Exception as e:
            logger.warn('Failed to send to client. Error returned: %s' % e)
            return {'status': False}
        else:
            sendresponse = sendit.json()
            if chkstatus is True:
                queueinfo = sendresponse['queue']
                if str(queueinfo['status']).lower() == 'paused':
                    #logger.info('queue IS paused')
                    return {'status': True}
                else:
                    #logger.info('queue NOT paused')
                    return {'status': False}

            #logger.fdebug(sendresponse)
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
            logger.fdebug('sending now to %s' % self.sab_url)
            tmp_apikey = self.params['queue'].pop('apikey')
            self.params['queue'].pop('search')
            self.params['queue']['nzo_ids'] = self.params['nzo_id']
            if mylar.CONFIG.SAB_CATEGORY is not None:
                self.params['queue']['category'] = mylar.CONFIG.SAB_CATEGORY
            logger.fdebug('[SAB-QUEUE] parameters set to %s' % self.params)
            self.params['queue']['apikey'] = tmp_apikey
            time.sleep(5)   #pause 5 seconds before monitoring just so it hits the queue
            h = requests.get(self.sab_url, params=self.params['queue'], verify=False)
        except Exception as e:
            logger.fdebug('uh-oh: %s' % e)
            return self.historycheck(self.params)
        else:
            queueresponse = h.json()
            logger.fdebug('successfully queried the queue for status')
            try:
                if queueresponse['noofslots'] == 1: # 1 means it matched to one instance
                    queueinfo = queueresponse['queue']['slots'][0]
                    logger.info('monitoring ... detected download - %s [%s]' % (queueinfo['filename'], queueinfo['status']))
            except Exception as e:
                logger.warn('Unable to locate item within sabnzbd active queue - it could be finished already?')
                queueinfo = queueresponse['queue']
            try:
                logger.fdebug('SABnzbd Queued item status : %s' % queueinfo['status'])
                logger.fdebug('SABnzbd Queued item mbleft : %s' % queueinfo['mbleft'])
                if str(queueinfo['status']) == 'Paused':
                    logger.warn('[WARNING] SABnzbd has the active queue Paused. CDH will not work in this state.')
                    return {'status': 'queue_paused', 'failed': False}
                while any([str(queueinfo['status']) == 'Downloading', str(queueinfo['status']) == 'Idle', str(queueinfo['status']) == 'Queued']) and float(queueinfo['mbleft']) > 0:
                    #if 'comicrn' in queueinfo['script'].lower():
                    #    logger.warn('ComicRN has been detected as being active for this category & download. Completed Download Handling will NOT be performed due to this.')
                    #    logger.warn('Either disable Completed Download Handling for SABnzbd within Mylar, or remove ComicRN from your category script in SABnzbd.')
                    #    return {'status': 'double-pp', 'failed': False}
                    no_findie = False
                    tmp_queue = self.params['queue']
                    try:
                        tmp_queue.pop('nzo_ids')
                    except Exception as e:
                        # if this triggers than nzo_id is no longer in the active queue and we can assume it's finished
                        logger.fdebug('unable to pop nzo_id - possibly already done/finished/does not exist')
                        no_findie = True
                    tmp_queue['nzo_ids'] = self.params['nzo_id'] # if it pops, still there - make sure we put it back
                    queue_resp = requests.get(self.sab_url, params=tmp_queue, verify=False)
                    queueresponse = queue_resp.json()
                    try:
                        queueinfo = queueresponse['queue']['slots'][0]
                    except Exception as e:
                        try:
                            tmp_queue.pop('nzo_ids')
                        except Exception as e:
                            #logger.fdebug('unable to pop nzo_id - possibly already done/finished/does not exist')
                            no_findie = True
                        else:
                            tmp_queue['nzo_ids'] = self.params['nzo_id']
                            queueinfo = queueresponse['queue']

                    logger.fdebug('status: %s -- mb_left: %s -- time_left: %s' % (queueinfo['status'], queueinfo['mbleft'], queueinfo['timeleft']))
                    time.sleep(5)
                    if no_findie:
                        break
            except Exception as e:
                logger.warn('error: %s' % e)

            logger.info('File has now downloaded!')
            return self.historycheck(self.params)

    def historycheck(self, nzbinfo, roundtwo=False, extract_counter=1):
        sendresponse = nzbinfo['nzo_id']
        hist_params = {'mode':      'history',
                       'failed':    0,
                       'output':    'json',
                       'apikey':    mylar.CONFIG.SAB_APIKEY}

        if mylar.CONFIG.SAB_CATEGORY is not None:
            hist_params['category'] = mylar.CONFIG.SAB_CATEGORY

        sab_check = None
        if mylar.CONFIG.SAB_VERSION is None:
            sab_check = self.sab_versioncheck()

        if sab_check == 'some value':
            hist_params['limit'] = 200
        else:
            #set min_sab to 3.2.0 since 3.2.0 beta 1 has the api call for history search by nzo_id
            try:
                min_sab = '3.2.0'
                sab_vers = mylar.CONFIG.SAB_VERSION
                if parse_version(sab_vers) >= parse_version(min_sab):
                    logger.fdebug('SABnzbd version is higher than 3.2.0. Querying history based on nzo_id directly.')
                    hist_params['nzo_ids'] = sendresponse
                else:
                    logger.fdebug('SABnzbd version is less than 3.2.0. Querying history based on history size of 200.')
                    hist_params['limit'] = 200
            except Exception as e:
                logger.warn('[SABNZBD-VERSION-CHECK] Exception encountered trying to compare installed version [%s] to [%s]. Setting history length to last 200 items. (error: %s)' % (mylar.CONFIG.SAB_VERSION, min_sab ,e))
                hist_params['limit'] = 200

        hist = requests.get(self.sab_url, params=hist_params, verify=False)
        historyresponse = hist.json()
        #logger.info(historyresponse)
        histqueue = historyresponse['history']
        found = {'status': False}
        nzo_exists = False

        try:
            for hq in histqueue['slots']:
                logger.fdebug('nzo_id: %s --- %s [%s]' % (hq['nzo_id'], sendresponse, hq['status']))
                # Additional guard on hq['script'] as it can be returned as a null value from SAB
                if hq['nzo_id'] == sendresponse and any([hq['status'] == 'Completed', hq['status'] == 'Running', (hq['script'] is not None and 'comicrn' in hq['script'].lower())]):
                    # A rare occurrence from SAB has it returning two history entries for this nzo, one of which has an empty storage entry.  If hitting this
                    # assume that it will condense back into one entry on subsequent re-check
                    if hq['storage'] == '' and not roundtwo:
                        logger.fdebug(f"[{hq['status']}] Storage entry was empty for Completed job.  Sleeping for {mylar.CONFIG.SAB_MOVING_DELAY}s to allow the process to fully finish before trying again.")
                        time.sleep(mylar.CONFIG.SAB_MOVING_DELAY)
                        return self.historycheck(nzbinfo, roundtwo=True)
                    
                    nzo_exists = True
                    logger.info('found matching completed item in history. Job has a status of %s' % hq['status'])
                    if hq['script'] is not None and 'comicrn' in hq['script'].lower():
                        logger.warn('ComicRN has been detected as being active for this category & download. Completed Download Handling will NOT be performed due to this.')
                        logger.warn('Either disable Completed Download Handling for SABnzbd within Mylar, or remove ComicRN from your category script in SABnzbd.')
                        self.remove_history(hq['nzo_id'], hq['status'])
                        return {'status': 'double-pp', 'failed': False}

                    if os.path.isfile(hq['storage']):
                        logger.fdebug('location found @ %s' % hq['storage'])
                        found = {'status':   True,
                                 'name':     ntpath.basename(hq['storage']), #os.pathre.sub('.nzb', '', hq['nzb_name']).strip(),
                                 'location': os.path.abspath(os.path.join(hq['storage'], os.pardir)),
                                 'failed':   False,
                                 'issueid':  nzbinfo['issueid'],
                                 'comicid':  nzbinfo['comicid'],
                                 'apicall':  True,
                                 'ddl':      False,
                                 'download_info': nzbinfo['download_info']}
                        self.remove_history(hq['nzo_id'], hq['status'])
                        break

                    elif all([mylar.CONFIG.SAB_TO_MYLAR, mylar.CONFIG.SAB_DIRECTORY is not None, mylar.CONFIG.SAB_DIRECTORY != 'None']):
                        try:
                            np = cdh_mapping.CDH_MAP(hq['storage'], sab=True)
                            new_path = np.the_sequence()
                        except Exception as e:
                            logger.warn('[ERROR] error returned during attempt to map [%s] --> root dir:[%s]. Error: %s' % (hq['storage'], mylar.CONFIG.SAB_DIRECTORY, e))
                            self.remove_history(hq['nzo_id'], hq['status'])
                            return {'status': 'file not found', 'failed': False}
                        else:
                            if new_path is None:
                                logger.warn('[ERROR] Unable to remap the directory from SAB to Mylar\'s configuration.')
                                self.remove_history(hq['nzo_id'], hq['status'])
                                return {'status': 'file not found', 'failed': False}
                            elif not os.path.isfile(new_path):
                                logger.fdebug('[ERROR] Unable to locate path (%s) on the machine that is running Mylar. If Mylar and sabnzbd are on separate machines, you need to set a directory location that is accessible to both' % (new_path))
                                self.remove_history(hq['nzo_id'], hq['status'])
                                return {'status': 'file not found', 'failed': False}

                        logger.fdebug('location found @ %s' % new_path)
                        found = {'status':   True,
                                 'name':     ntpath.basename(new_path),
                                 'location': os.path.abspath(os.path.join(new_path, os.pardir)),
                                 'failed':   False,
                                 'issueid':  nzbinfo['issueid'],
                                 'comicid':  nzbinfo['comicid'],
                                 'apicall':  True,
                                 'ddl':      False,
                                 'download_info': nzbinfo['download_info']}
                        self.remove_history(hq['nzo_id'], hq['status'])
                        break

                    else:
                        logger.error('no file found where it should be @ %s - is there another script that moves things after completion ?' % hq['storage'])
                        self.remove_history(hq['nzo_id'], hq['status'])
                        return {'status': 'file not found', 'failed': False}

                elif hq['nzo_id'] == sendresponse and hq['status'] == 'Failed':
                    nzo_exists = True
                    #get the stage / error message and see what we can do
                    stage = hq['stage_log']
                    logger.fdebug('stage: %s' % (stage,))
                    for x in stage:
                        if 'Failed' in x['actions'] and any([x['name'] == 'Unpack', x['name'] == 'Repair']):
                            if 'moving' in x['actions']:
                                logger.warn('There was a failure in SABnzbd during the unpack/repair phase that caused a failure: %s' % x['actions'])
                            else:
                                logger.warn('Failure occured during the Unpack/Repair phase of SABnzbd. This is probably a bad file: %s' % x['actions'])
                                if mylar.FAILED_DOWNLOAD_HANDLING is True:
                                    found = {'status':   True,
                                             'name':     re.sub('.nzb', '', hq['nzb_name']).strip(),
                                             'location': os.path.abspath(os.path.join(hq['storage'], os.pardir)),
                                             'failed':   True,
                                             'issueid':  nzbinfo['issueid'],
                                             'comicid':  nzbinfo['comicid'],
                                             'apicall':  True,
                                             'ddl':      False,
                                             'download_info': nzbinfo['download_info']}
                            self.remove_history(hq['nzo_id'], hq['status'])
                            break
                    if found['status'] is False:
                        self.remove_history(hq['nzo_id'], hq['status'])
                        return {'status': 'failed_in_sab', 'failed': False}
                    else:
                        break
                elif hq['nzo_id'] == sendresponse:
                    nzo_exists = True
                    logger.fdebug('nzo_id: %s found while processing queue in an unhandled status: %s' % (hq['nzo_id'], hq['status']))
                    if hq['status'] in ['Queued', 'Moving', 'Extracting', 'QuickCheck', 'Repairing', 'Verifying'] and not roundtwo:
                        logger.fdebug('[%s(%s)] sleeping for %ss to allow the process to finish before trying again..' % (hq['status'], extract_counter, mylar.CONFIG.SAB_MOVING_DELAY))
                        time.sleep(mylar.CONFIG.SAB_MOVING_DELAY)
                        if hq['status'] == 'Extracting':
                            try:
                                to_delay = int(int(hq['bytes']) / 25000000) + 2  #for every 25mb add another retry pause as a precaution
                            except Exception:
                                to_delay = 4

                            if extract_counter < to_delay:
                                extract_counter +=1
                                return self.historycheck(nzbinfo, roundtwo=False, extract_counter=extract_counter)
                        return self.historycheck(nzbinfo, roundtwo=True)
                    else:
                        self.remove_history(hq['nzo_id'], hq['status'])
                        return {'failed': False, 'status': 'unhandled status of: %s' %( hq['status'])}

            if not nzo_exists:
                logger.error('Cannot find nzb %s in the queue.  Was it removed?' % sendresponse)
                logger.fdebug('sleeping for %ss to allow the process to finish before trying again..' % (mylar.CONFIG.SAB_MOVING_DELAY))
                time.sleep(mylar.CONFIG.SAB_MOVING_DELAY)
                if roundtwo is False:
                    return self.historycheck(nzbinfo, roundtwo=True)
                else:
                    return {'status': 'nzb removed', 'failed': False}
        except Exception as e:
            logger.warn('error %s' % (e,))
            self.remove_history(hq['nzo_id'], hq['status'])
            return {'status': False, 'failed': False}

        return found

    def remove_history(self, nzo_id, status):
        logger.info('[Sabnzbd Completed History Removal] Download is complete - removing item from history..')
        if all([status == 'Failed', mylar.CONFIG.SAB_REMOVE_FAILED]) or mylar.CONFIG.SAB_REMOVE_COMPLETED:
            hist_params = {'mode': 'history',
                           'name': 'delete',
                           'value': nzo_id,
                           'output': 'json',
                           'apikey': mylar.CONFIG.SAB_APIKEY}

            if mylar.CONFIG.SAB_REMOVE_FAILED:
                hist_params['del_files'] = 1

            try:
                rh = requests.get(self.sab_url, params=hist_params, verify=False)
                rhistory = rh.json()
            except Exception as e:
                logger.warn('[Sabnzbd Completed History Removal] Unable to remove item - error returned: %s' % e)
            else:
                if rhistory['status'] is True:
                    logger.info('[Sabnzbd Completed History Removal] Item successfully removed from history..')
                else:
                    logger.warn('[Sabnzbd Completed History Removal] Unable to remove item from history..')

    def sab_versioncheck(self):
        try:
            sc = mylar.webserve.WebInterface()
            sab_check = sc.SABtest(sabhost=mylar.CONFIG.SAB_HOST, sabusername=mylar.CONFIG.SAB_USERNAME, sabpassword=mylar.CONFIG.SAB_PASSWORD, sabapikey=mylar.CONFIG.SAB_APIKEY)
        except Exception as e:
            logger.warn('[SABNZBD-VERSION-TEST] Exception encountered trying to retrieve SABnzbd version: %s. Setting history length to last 200 items.' % e)
            sab_check = 'some value'
        else:
            sab_check = None

        return sab_check
