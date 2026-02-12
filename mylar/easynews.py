# -*- coding: utf-8 -*-
# This file is part of Mylar.
#
# Mylar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mylar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mylar.  If not, see <http://www.gnu.org/licenses/>.


import requests
import os
import re
import time
import datetime
import zipfile
import mylar
from mylar import db, logger, helpers, search_filer


class Easynews(object):

    def __init__(self, query=None, issueid=None, comicid=None, oneoff=False, provider_stat=None):

        self.session = requests.Session()
        self.session.auth = (mylar.CONFIG.EASYNEWS_USERNAME or '', mylar.CONFIG.EASYNEWS_PASSWORD or '')

        if mylar.CONFIG.ENABLE_PROXY:
            self.session.proxies.update({
                'http':  mylar.CONFIG.HTTP_PROXY,
                'https': mylar.CONFIG.HTTPS_PROXY
            })

        self.base_url = 'https://members.easynews.com/2.0/search/solr-search/advanced'
        self.file_extensions = 'cbr,cbz,cb7,pdf'

        self.query = query  # {'comicname', 'issue', 'year'}
        self.comicid = comicid
        self.issueid = issueid
        self.oneoff = oneoff
        self.provider_stat = provider_stat

        self.search_format = ['"%s #%s (%s)"', '%s #%s (%s)', '%s #%s', '%s %s']

    def search(self, is_info=None):
        try:
            if is_info is not None:
                if is_info['chktpb'] == 0:
                    logger.debug('[DDL(Easynews)] removing query from loop that accounts for no issue number')
                else:
                    self.search_format.insert(0, self.query['comicname'])
                    logger.debug('[DDL(Easynews)] setting no issue number query to be first due to no issue number')

            for sf in self.search_format:
                verified_matches = []
                sf_issue = self.query['issue']

                if is_info['chktpb'] == 1 and self.query['comicname'] == sf:
                    comicname = re.sub(r'[\&\:\?\,\/\-]', '', self.query['comicname'])
                    comicname = re.sub("\\band\\b", '', comicname, flags=re.I)
                    comicname = re.sub("\\bthe\\b", '', comicname, flags=re.I)
                    queryline = re.sub(r'\s+', ' ', comicname)
                else:
                    if any([self.query['issue'] == 'None', self.query['issue'] is None]):
                        sf_issue = None
                    if sf.count('%s') == 3:
                        if sf_issue is None:
                            splits = sf.split(' ')
                            splits.pop(1)
                            queryline = ' '.join(splits) % (self.query['comicname'], self.query['year'])
                        else:
                            queryline = sf % (self.query['comicname'], sf_issue, self.query['year'])
                    else:
                        sf_count = len([m.start() for m in re.finditer('(?=%s)', sf)])
                        if sf_count == 0:
                            queryline = sf
                        elif sf_count == 2:
                            queryline = sf % (self.query['comicname'], sf_issue)
                        elif sf_count == 3:
                            queryline = sf % (self.query['comicname'], sf_issue, self.query['year'])
                        else:
                            queryline = sf % (self.query['comicname'])

                if not queryline:
                    continue

                logger.fdebug('[DDL(Easynews)-QUERY] Query set to: %s' % queryline)

                result_generator = self.perform_search_queries(queryline)
                sfs = search_filer.search_check()
                match = sfs.check_for_first_result(
                    result_generator, is_info, prefer_pack=False
                )
                if match is not None:
                    verified_matches = [match]
                    logger.fdebug('[DDL(Easynews)] verified_matches: %s' % (verified_matches,))
                    break
                logger.fdebug('[DDL(Easynews)] sleep...%s%s' % (mylar.CONFIG.DDL_QUERY_DELAY, 's'))
                time.sleep(mylar.CONFIG.DDL_QUERY_DELAY)

        except requests.exceptions.Timeout as e:
            logger.warn('[DDL(Easynews)] Timeout occured fetching data: %s' % e)
            return 'no results'
        except requests.exceptions.ConnectionError as e:
            logger.warn('[DDL(Easynews)] Connection error: %s' % e)
            return 'no results'
        except Exception as err:
            logger.warn('[DDL(Easynews)] Error during search: %s' % err)
            return 'no results'
        else:
            return verified_matches if verified_matches else 'no results'

    def perform_search_queries(self, queryline):
        page_number = 1
        per_page = 250

        while True:
            pause_the_search = mylar.CONFIG.DDL_QUERY_DELAY
            diff = mylar.search.check_time(self.provider_stat['lastrun'])
            if diff < pause_the_search:
                logger.warn('[PROVIDER-SEARCH-DELAY][DDL(Easynews)] Waiting %s seconds before next search...' % (pause_the_search - int(diff)))
                time.sleep(pause_the_search - int(diff))
            else:
                logger.fdebug('[PROVIDER-SEARCH-DELAY][DDL(Easynews)] Last search took place %s seconds ago. We\'re clear...' % (int(diff)))

            params = {
                'gps': queryline,
                'fex': self.file_extensions,
                'pby': per_page,
                'pno': page_number,
                's1': 'dsize',
                's1d': '-',
                'spamf': 1,
                'st': 'adv',
                'sb': 1,
            }

            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=(30, 30)
                )
            except Exception as e:
                logger.warn('[DDL(Easynews)] Error fetching search page %s: %s' % (page_number, e))
                break

            if response.status_code != 200:
                logger.warn('[DDL(Easynews)] Search returned status %s' % response.status_code)
                if response.status_code == 401:
                    logger.warn('[DDL(Easynews)] Authentication failed. Check username/password.')
                break

            write_time = time.time()
            mylar.search.last_run_check(write={'DDL(Easynews)': {'id': 202, 'active': True, 'lastrun': write_time, 'type': 'DDL', 'hits': self.provider_stat['hits']+1}})
            self.provider_stat['lastrun'] = write_time

            try:
                data = response.json()
            except Exception as e:
                logger.warn('[DDL(Easynews)] Failed to parse JSON response: %s' % e)
                break

            dl_farm = data.get('dlFarm')
            dl_port = data.get('dlPort')
            results = data.get('data', [])

            if not results:
                logger.fdebug('[DDL(Easynews)] No results on page %s' % page_number)
                break

            logger.info('[DDL(Easynews)] Found %s results on page %s' % (len(results), page_number))

            for item in results:
                normalized = self._normalize_result(item, dl_farm, dl_port)
                if normalized is not None:
                    yield normalized

            if len(results) < per_page:
                break

            page_number += 1

    def _normalize_result(self, item, dl_farm, dl_port):
        # Skip password protected or virus-flagged files
        if item.get('passwd') or item.get('virus'):
            return None

        file_hash = item.get('0', '')
        extension = item.get('2', '')
        rawsize = item.get('rawSize', item.get('4', 0))
        date_str = item.get('5', '')
        filename = item.get('10', '')

        if not file_hash or not filename:
            return None

        # Build the download URL
        download_url = 'https://members.easynews.com/%s/%s/%s%s/%s%s' % (
            dl_farm, dl_port, file_hash, extension, filename, extension
        )

        # Format file size for display
        try:
            size_bytes = int(rawsize)
            if size_bytes >= 1073741824:
                size_display = '%.1f GB' % (size_bytes / 1073741824.0)
            elif size_bytes >= 1048576:
                size_display = '%.1f MB' % (size_bytes / 1048576.0)
            elif size_bytes >= 1024:
                size_display = '%.1f KB' % (size_bytes / 1024.0)
            else:
                size_display = '%s B' % size_bytes
        except (ValueError, TypeError):
            size_display = '0 MB'

        # Format date
        try:
            pubdate = datetime.datetime.strptime(date_str[:10], '%Y-%m-%d').strftime('%a, %d %b %Y %H:%M:%S')
        except Exception:
            pubdate = datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S')

        # Strip extension from filename for title
        title = os.path.splitext(filename)[0]

        return {
            "title": title,
            "pubdate": pubdate,
            "filename": filename,
            "size": size_display,
            "pack": False,
            "series": None,
            "link": download_url,
            "year": None,
            "id": file_hash,
            "site": "DDL(Easynews)",
        }

    def downloadit(self, id, link, issueid, remote_filesize=0):
        myDB = db.DBConnection()

        if mylar.DDL_LOCK is True:
            logger.fdebug('[DDL(Easynews)] Download is locked - another download is in progress...')
            return {"success": False, "filename": None, "path": None}

        mylar.DDL_LOCK = True
        filename = None

        try:
            # Extract filename from URL path
            url_filename = link.rsplit('/', 1)[-1] if '/' in link else None
            if url_filename:
                filename = requests.utils.unquote(url_filename)
            else:
                filename = 'easynews_%s' % id

            # Add issueid tag to filename
            file_base, file_ext = os.path.splitext(filename)
            filename = '%s[__%s__]%s' % (file_base, issueid, file_ext)

            # Write tracking info to db
            myDB.upsert(
                'ddl_info',
                {'filename': filename, 'remote_filesize': remote_filesize},
                {'id': id},
            )

            if mylar.CONFIG.DDL_LOCATION is not None and not os.path.isdir(
                mylar.CONFIG.DDL_LOCATION
            ):
                checkdirectory = mylar.filechecker.validateAndCreateDirectory(
                    mylar.CONFIG.DDL_LOCATION, True
                )
                if not checkdirectory:
                    logger.warn(
                        '[DDL(Easynews)] [ABORTING] Error trying to validate/create DDL download'
                        ' directory: %s.' % mylar.CONFIG.DDL_LOCATION
                    )
                    mylar.DDL_LOCK = False
                    return {"success": False, "filename": filename, "path": None}

            dst_path = os.path.join(mylar.CONFIG.DDL_LOCATION, filename)

            logger.info('[DDL(Easynews)] Downloading %s to %s' % (filename, dst_path))

            t = self.session.get(link, stream=True, timeout=(30, 300))

            if t.status_code == 401:
                logger.warn('[DDL(Easynews)] Authentication failed during download. Check credentials.')
                mylar.DDL_LOCK = False
                return {"success": False, "filename": filename, "path": None}

            if t.status_code != 200:
                logger.warn('[DDL(Easynews)] Download returned status %s' % t.status_code)
                mylar.DDL_LOCK = False
                return {"success": False, "filename": filename, "path": None}

            t.headers['Accept-encoding'] = 'gzip'

            if os.path.exists(dst_path):
                logger.fdebug('[DDL(Easynews)] %s already exists - removing' % dst_path)
                try:
                    os.remove(dst_path)
                except Exception as e:
                    file_base, file_ext = os.path.splitext(filename)
                    filename = '%s.1%s' % (file_base, file_ext)
                    dst_path = os.path.join(mylar.CONFIG.DDL_LOCATION, filename)
                    logger.warn(
                        '[DDL(Easynews)] [ERROR: %s] Unable to remove existing file.'
                        ' Creating tmp file @%s' % (e, filename)
                    )

            with open(dst_path, 'wb') as f:
                for chunk in t.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        f.flush()

        except requests.exceptions.Timeout as e:
            logger.error('[DDL(Easynews)] Download timed out: %s' % e)
            mylar.DDL_LOCK = False
            return {"success": False, "filename": filename, "path": None}

        except Exception as e:
            logger.error('[DDL(Easynews)] Download error: %s' % e)
            mylar.DDL_LOCK = False
            return {"success": False, "filename": filename, "path": None}
        else:
            mylar.DDL_LOCK = False
            return self._zip_check(id, dst_path, filename)

    def _zip_check(self, id, dst_path, filename):
        if os.path.isfile(dst_path):
            if dst_path.endswith('.zip'):
                new_path = os.path.join(
                    mylar.CONFIG.DDL_LOCATION, re.sub('.zip', '', filename).strip()
                )
                logger.info(
                    '[DDL(Easynews)] Zip file detected.'
                    ' Unzipping into: %s' % new_path
                )
                try:
                    zip_f = zipfile.ZipFile(dst_path, 'r')
                    zip_f.extractall(new_path)
                    zip_f.close()
                except Exception as e:
                    logger.warn(
                        '[DDL(Easynews)] [ERROR: %s] Unable to extract zip file: %s' % (e, new_path)
                    )
                    return {"success": False, "filename": filename, "path": None}
                else:
                    try:
                        os.remove(dst_path)
                    except Exception as e:
                        logger.warn(
                            '[DDL(Easynews)] [ERROR: %s] Unable to remove zip file from %s after'
                            ' extraction.' % (e, dst_path)
                        )
                    filename = None
            else:
                new_path = dst_path
            return {"success": True, "filename": filename, "path": new_path}

        mylar.DDL_LOCK = False
        return {"success": False, "filename": filename, "path": None}
