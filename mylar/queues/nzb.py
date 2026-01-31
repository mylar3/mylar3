"""NZB queue worker and helpers."""

import time
from pathlib import Path

import mylar
from .. import logger, helpers
from mylar import sabnzbd, nzbget


def nzb_monitor(queue):
    while True:
        if mylar.RETURN_THE_NZBQUEUE.qsize() >= 1:
            if mylar.USE_SABNZBD is True:
                sab_params = {
                    'apikey': mylar.CONFIG.SAB_APIKEY,
                    'mode': 'queue',
                    'start': 0,
                    'limit': 5,
                    'search': None,
                    'output': 'json',
                }
                s = sabnzbd.SABnzbd(params=sab_params)
                sabresponse = s.sender(chkstatus=True)
                if sabresponse['status'] is False:
                    while True:
                        if mylar.RETURN_THE_NZBQUEUE.qsize() >= 1:
                            qu_retrieve = mylar.RETURN_THE_NZBQUEUE.get(True)
                            try:
                                nzstat = s.historycheck(qu_retrieve)
                                cdh_monitor(queue, qu_retrieve, nzstat, readd=True)
                            except Exception as e:
                                logger.error('Exception occured trying to re-add %s to queue: %s' % (qu_retrieve, e))
                            time.sleep(5)
                        else:
                            break

        if queue.qsize() >= 1:
            item = queue.get(True)
            if item == 'exit':
                logger.info('Cleaning up workers for shutdown')
                break
            try:
                tmp_apikey = item['queue'].pop('apikey')
                logger.info('Now loading from queue: %s' % item)
            except Exception:
                logger.info('Now loading from queue: %s' % item)
            else:
                item['queue']['apikey'] = tmp_apikey
            if all([mylar.USE_SABNZBD is True, mylar.CONFIG.SAB_CLIENT_POST_PROCESSING is True]):
                nz = sabnzbd.SABnzbd(item)
                nzstat = nz.processor()
            elif all([mylar.USE_NZBGET is True, mylar.CONFIG.NZBGET_CLIENT_POST_PROCESSING is True]):
                nz = nzbget.NZBGet()
                nzstat = nz.processor(item)
            else:
                logger.warn('There are no NZB Completed Download handlers enabled. Not sending item to completed download handling...')
                break
            cdh_monitor(queue, item, nzstat)
        else:
            time.sleep(5)


def cdh_monitor(queue, item, nzstat, readd=False):
    known_nzb_id = item['nzo_id'] if (mylar.USE_SABNZBD is True) else item['NZBID']
    if any([nzstat['status'] == 'file not found', nzstat['status'] == 'double-pp']):
        logger.warn('Unable to complete post-processing call due to not finding file in the location provided. [%s]' % item)
    elif nzstat['status'] == 'nzb removed' or 'unhandled status' in str(nzstat['status']).lower():
        if readd is True:
            logger.warn('NZB seems to have been in a staging process within SABnzbd during attempt. Will requeue: %s.' % known_nzb_id)
            mylar.RETURN_THE_NZBQUEUE.put(item)
        else:
            logger.warn('NZB seems to have been removed from queue: %s' % known_nzb_id)
    elif nzstat['status'] == 'failed_in_sab':
        logger.warn('Failure returned from SAB for %s for some reason. You should probably check your SABnzbd logs' % known_nzb_id)
    elif nzstat['status'] == 'queue_paused':
        if mylar.USE_SABNZBD is True:
            logger.info('[PAUSED_SAB_QUEUE] adding %s to a temporary queue that will fire off when SABnzbd is unpaused' % item)
            mylar.RETURN_THE_NZBQUEUE.put(item)
    elif nzstat['status'] is False:
        logger.info('Download %s failed. Requeue NZB to check later...' % known_nzb_id)
        time.sleep(5)
        if item not in queue.queue:
            mylar.NZB_QUEUE.put(item)
    elif nzstat['status'] is True:
        if nzstat['failed'] is False and mylar.USE_SABNZBD is True:
            fullpath = Path(nzstat['location']) / nzstat['name']
            filecondition = helpers.check_file_condition(fullpath)
            if not filecondition['status']:
                logger.warn(f"CRC Check: File {fullpath} failed condition check ({filecondition['quality']}).  Marking as failed.")
                nzstat['failed'] = True

        if nzstat['failed'] is False:
            logger.info('File successfully downloaded - now initiating completed downloading handling.')
        else:
            logger.info('File failed either due to being corrupt or incomplete - now initiating completed failed downloading handling.')
        try:
            mylar.PP_QUEUE.put({
                'nzb_name':     nzstat['name'],
                'nzb_folder':   nzstat['location'],
                'failed':       nzstat['failed'],
                'issueid':      nzstat['issueid'],
                'comicid':      nzstat['comicid'],
                'apicall':      nzstat['apicall'],
                'ddl':          False,
                'download_info': nzstat['download_info'],
            })
        except Exception as e:
            logger.error('process error: %s' % e)
    return
