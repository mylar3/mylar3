"""Torrent monitor queue worker."""

import os
import time

import mylar
from .. import logger, helpers


def worker_main(queue):
    while True:
        if queue.qsize() >= 1:
            item = queue.get(True)
            logger.info('Now loading from queue: %s' % item)
            if item == 'exit':
                logger.info('Cleaning up workers for shutdown')
                break
            snstat = helpers.torrentinfo(torrent_hash=item['hash'], download=True)
            if snstat['snatch_status'] == 'IN PROGRESS':
                logger.info('Still downloading in client....let us try again momentarily.')
                time.sleep(30)
                mylar.SNATCHED_QUEUE.put(item)
            elif any([
                snstat['snatch_status'] == 'MONITOR FAIL',
                snstat['snatch_status'] == 'MONITOR COMPLETE',
            ]):
                logger.info('File copied for post-processing - submitting as a direct pp.')
                mylar.PP_QUEUE.put({
                    'nzb_name':     os.path.basename(snstat['copied_filepath']),
                    'nzb_folder':   snstat['copied_filepath'],
                    'failed':       False,
                    'issueid':      item['issueid'],
                    'comicid':      item['comicid'],
                    'apicall':      True,
                    'ddl':          False,
                    'download_info': None,
                })
        else:
            time.sleep(15)
