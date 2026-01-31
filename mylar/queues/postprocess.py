"""Post-processing queue worker."""

import time

import mylar
from .. import logger
from mylar import process


def postprocess_main(queue):
    while True:
        if mylar.APILOCK is True:
            time.sleep(5)

        elif mylar.APILOCK is False and queue.qsize() >= 1:
            pp = None
            item = queue.get(True)
            logger.info('Now loading from post-processing queue: %s' % item)
            if item == 'exit':
                logger.info('Cleaning up workers for shutdown')
                break

            if mylar.APILOCK is False:
                try:
                    pprocess = process.Process(
                        item['nzb_name'],
                        item['nzb_folder'],
                        item['failed'],
                        item['issueid'],
                        item['comicid'],
                        item['apicall'],
                        item['ddl'],
                        item['download_info'],
                    )
                except Exception:
                    pprocess = process.Process(
                        item['nzb_name'],
                        item['nzb_folder'],
                        item['failed'],
                        item['issueid'],
                        item['comicid'],
                        item['apicall'],
                    )
                pp = pprocess.post_process()
                time.sleep(5)

            if pp is not None and pp.get('mode') == 'stop':
                mylar.APILOCK = False

            if mylar.APILOCK is True:
                logger.info('Another item is post-processing still...')
                time.sleep(15)
        else:
            time.sleep(5)
