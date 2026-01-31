"""Search queue worker."""

import time
from pathlib import Path

import mylar
from .. import logger, helpers


def search_queue(queue):
    while True:
        if mylar.SEARCHLOCK is True:
            time.sleep(5)

        elif mylar.SEARCHLOCK is False and queue.qsize() >= 1:
            item = queue.get(True)
            if item == 'exit':
                logger.info('[SEARCH-QUEUE] Cleaning up workers for shutdown')
                break

            gumbo_line = True
            if item['issueid'] in mylar.PACK_ISSUEIDS_DONT_QUEUE:
                if mylar.PACK_ISSUEIDS_DONT_QUEUE[item['issueid']] in mylar.DDL_QUEUED:
                    logger.fdebug('[SEARCH-QUEUE-PACK-DETECTION] %s already queued to download via pack...Ignoring' % item['issueid'])
                    gumbo_line = False

            if gumbo_line:
                logger.fdebug('[SEARCH-QUEUE] Now loading item from search queue: %s' % item)
                if mylar.SEARCHLOCK is False:
                    arcid = None
                    comicid = item['comicid']
                    issueid = item['issueid']
                    if issueid is not None and '_' in issueid:
                        arcid = issueid
                        comicid = None
                        issueid = None
                    mofo = mylar.filers.FileHandlers(ComicID=comicid, IssueID=issueid, arcID=arcid)
                    local_check = mofo.walk_the_walk()

                    if local_check['status']:
                        fullpath = Path(local_check['filepath']) / local_check['filename']
                        filecondition = helpers.check_file_condition(fullpath)
                        if not filecondition['status']:
                            logger.warn(f"CRC Check: File {fullpath} failed condition check ({filecondition['quality']}).  Ignoring.")
                            local_check['status'] = False

                    if local_check['status'] is True:
                        mylar.PP_QUEUE.put({
                            'nzb_name':     local_check['filename'],
                            'nzb_folder':   local_check['filepath'],
                            'failed':       False,
                            'issueid':      item['issueid'],
                            'comicid':      item['comicid'],
                            'apicall':      True,
                            'ddl':          False,
                            'download_info': None,
                        })
                    else:
                        try:
                            manual = item['manual']
                        except Exception:
                            manual = False
                        mylar.search.searchforissue(item['issueid'], manual=manual)
                    time.sleep(5)

            if mylar.SEARCHLOCK is True:
                logger.fdebug('[SEARCH-QUEUE] Another item is currently being searched....')
                time.sleep(15)
        else:
            time.sleep(5)
