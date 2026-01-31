"""JD2 queue worker."""

import datetime
import os
import time

import mylar
from .. import logger
from mylar import db
from mylar.downloaders.jdownloader2 import JDownloader2


def jd2_queue_monitor(queue):
    jd2_client = JDownloader2()
    myDB = db.DBConnection()
    while True:
        if queue.qsize() >= 1:
            item = queue.get(True)
            if item == 'exit':
                logger.info('[JD2-QUEUE] Cleaning up workers for shutdown')
                break
            if item == 'startup':
                try:
                    pending_jd2 = myDB.select(
                        "SELECT * FROM ddl_info WHERE jd2_job_id IS NOT NULL AND status = 'Queued'"
                    )

                except Exception as err:
                    logger.warn('[JD2-QUEUE] Unable to repopulate JD2 monitor queue: %s', err)
                else:
                    logger.info('[JD2-QUEUE] Repopulating JD2 monitor queue')
                    for job in pending_jd2 or []:
                        job_data = dict(job)
                        job_id = job_data.get('jd2_job_id')
                        record_id = job_data.get('ID') or job_data.get('id')
                        series = job_data.get('series')
                        year = job_data.get('year')
                        filename = job_data.get('tmp_filename') or job_data.get('filename')
                        if not filename:
                            if series and year:
                                filename = f"{series} ({year}) - {record_id}"
                            elif series:
                                filename = series
                            elif record_id:
                                filename = str(record_id)
                        queue_payload = {
                            'link': job_data.get('link'),
                            'mainlink': job_data.get('mainlink'),
                            'series': series,
                            'year': year,
                            'size': job_data.get('size'),
                            'comicid': job_data.get('comicid'),
                            'issueid': job_data.get('issueid'),
                            'oneoff': job_data.get('oneoff'),
                            'id': record_id,
                            'link_type': job_data.get('link_type'),
                            'filename': filename,
                            'comicinfo': job_data.get('comicinfo'),
                            'packinfo': job_data.get('packinfo'),
                            'site': job_data.get('site') or 'DDL(GetComics)',
                            'remote_filesize': job_data.get('remote_filesize') or 0,
                            'resume': None,
                            'jd2_job_id': job_id,
                        }
                        queue.put(queue_payload)
                continue

            if item.get('jd2_job_id') == 0:
                jd2_priority_links = item.get('jd2_priority_links')
                queue_payload = dict(item)
                queue_payload.pop('jd2_job_id', None)
                queue_payload.pop('jd2_priority_links', None)
                if not jd2_priority_links:
                    logger.warn('Priority links don\'t exist; cannot process JD2 job. Falling back to DDL queue.')
                    mylar.DDL_QUEUE.put(queue_payload)
                    continue
                record_id = item.get('id') or item.get('ID')
                package_name = '%s (%s) - %s' % (item.get('series'), item.get('year'), record_id)
                submit_result = jd2_client.submit(jd2_priority_links, package_name, record_id)

                if not submit_result.get('status'):
                    logger.warn('[JD2] Submission failed for %s; falling back to DDL queue. Details: %s', package_name, submit_result)
                    mylar.DDL_QUEUE.put(queue_payload)
                else:
                    logger.debug('[JD2] Submission response for %s: %s', package_name, submit_result)
                    job_id = submit_result.get('jobid')
                    if not job_id:
                        mylar.DDL_QUEUE.put(queue_payload)
                        continue
                    queue_payload['jd2_job_id'] = job_id
                    mylar.JD2_QUEUE.put(queue_payload)
                    logger.info('[JD2] JD2 job %s submitted for %s', job_id, package_name)
                    time.sleep(10)
                    continue

            logger.info('[JD2-QUEUE] Now loading from queue: %s' % item)
            record_id = item.get('ID') or item.get('id')
            job_id = item.get('jd2_job_id')
            series = item.get('series')
            year = item.get('year')

            job_filename = None

            if jd2_client is not None and job_id:
                try:
                    status_payload = jd2_client.status(job_id)
                except Exception as err:
                    logger.warn('[JD2-QUEUE] Error polling job %s: %s', job_id, err)
                else:
                    logger.info('[JD2-QUEUE] status update for job %s (record %s): %s', job_id, record_id, status_payload)
                    job_status = (status_payload or {}).get('status')
                    job_found = (status_payload or {}).get('found')

                    completed_states = {'FINISHED', 'Finished', 'finished', 'DONE', 'Done', 'Extraction OK', '[SHA256] CRC OK', 'Finished(Mirror)'}
                    failed_states = {'ERROR', 'FAILED', 'Error', 'Failed'}

                    if not job_found:
                        stale = False
                        try:
                            row = myDB.selectone("SELECT updated_date FROM ddl_info WHERE id=?", [record_id]).fetchone()
                        except Exception as err:
                            logger.warning('JD2 stale check failed for record %s: %s', record_id, err)
                            updated_str = None
                        else:
                            if row is None:
                                logger.info('[JD2-QUEUE] No ddl_info entry found for id %s; dropping job %s from monitoring.', record_id, job_id)
                                continue
                            updated_str = row['updated_date']

                        if updated_str:
                            try:
                                updated_dt = datetime.datetime.strptime(updated_str, '%Y-%m-%d %H:%M')
                            except Exception:
                                stale = False
                            else:
                                stale = (datetime.datetime.now() - updated_dt) >= datetime.timedelta(minutes=3)

                        if stale:
                            if myDB is not None:
                                myDB.upsert(
                                    'ddl_info',
                                    {
                                        'status': 'Failed',
                                        'updated_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                                    },
                                    {'id': record_id},
                                )
                            continue

                        queue.put(item)
                        time.sleep(10)
                        continue

                    if job_status in completed_states:
                        myDB.upsert(
                                'ddl_info',
                                {
                                    'status': 'Completed',
                                    'updated_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                                },
                                {'id': record_id},
                            )
                        logger.info('[JD2-QUEUE] Download for %s completed; status marked as Completed.', record_id)

                        job_filename = ((status_payload or {}).get('data') or {}).get('name')

                        if not isinstance(item, dict):
                            logger.warn('[JD2-QUEUE] Unexpected item type %s for job %s; skipping post-processing.', type(item), job_id)
                            continue
                        if mylar.CONFIG.POST_PROCESSING is True:
                            dest_root = getattr(mylar.CONFIG, 'JD2_DEST_DIR', None) or None
                            folder_name = (
                                "%s - %s" % (item.get('filename'), record_id)
                                if item.get('filename')
                                else "%s (%s) - %s" % (series, year, record_id)
                            )
                            nzb_folder = os.path.join(dest_root, folder_name)

                            if nzb_folder:
                                try:
                                    mylar.PP_QUEUE.put({
                                        'nzb_name': job_filename or 'Manual Run',
                                        'nzb_folder': nzb_folder,
                                        'failed': False,
                                        'issueid': item.get('issueid'),
                                        'comicid': item.get('comicid'),
                                        'apicall': True,
                                        'ddl': True,
                                        'download_info': {'provider': 'JD2', 'id': record_id, 'job_id': job_id},
                                    })
                                    logger.info('[JD2-QUEUE] Submitted %s for post-processing (folder: %s).', job_filename, nzb_folder)
                                except Exception as err:
                                    logger.warn('[JD2-QUEUE] Unable to enqueue %s for post-processing: %s', job_filename, err)
                            else:
                                logger.warn('[JD2-QUEUE] JD2 destination is not configured; skipping post-processing enqueue for %s.', job_filename)
                        else:
                            logger.info('[JD2-QUEUE] Post-processing disabled, please manually handle your files.')
                        continue

                    if job_status in failed_states:
                        myDB.upsert(
                                'ddl_info',
                                {
                                    'status': 'Failed',
                                    'updated_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                                },
                                {'id': record_id},
                            )
                        logger.warn('[JD2-QUEUE] Download %s reported failure state (%s).', job_filename, job_status)
                        continue

                    if job_status not in completed_states:
                        time.sleep(10)
                        queue.put(item)
                        continue
            else:
                logger.warn('[JD2-QUEUE] Missing JD2 client or job id for item: %s', item)
        else:
            time.sleep(10)
