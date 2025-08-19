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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mylar. If not, see <http://www.gnu.org/licenses/>.

import requests
import urllib.parse
import os
import sys
import traceback
import errno
import re
import time
import datetime
import json
import mylar
from mylar import db, logger, helpers, search_filer


class AirDCPP(object):
    def __init__(self, query=None, issueid=None, comicid=None, oneoff=False, provider_stat=None):
        self.query = query
        self.issueid = issueid
        self.comicid = comicid
        self.oneoff = oneoff
        self.provider_stat = provider_stat
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36'}

        self.current_search_instance_id = None

        self.api_url = mylar.CONFIG.AIRDCPP_HOST
        if not self.api_url.endswith('/'):
            self.api_url += '/'
        self.api_url += 'api/v1'

        if mylar.CONFIG.AIRDCPP_USERNAME and mylar.CONFIG.AIRDCPP_PASSWORD:
            self.session.auth = (mylar.CONFIG.AIRDCPP_USERNAME, mylar.CONFIG.AIRDCPP_PASSWORD)

        self.search_format = ['%s %s %s', '%s %s', '%s']
        self.comic_extensions = ["cbr", "cbz"]

    def search(self, is_info=None):
        """
        Search AirDC++ for comics matching the query

        Parameters:
        is_info (dict): Information about the comic to search for

        Returns:
        list: List of verified matches or 'no results' if none found
        """
        try:
            for sf in self.search_format:
                verified_matches = []
                sf_issue = self.query['issue']

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

                logger.fdebug('[AIRDCPP-QUERY] Query set to: %s' % queryline)
                result_generator = self.perform_search_queries(queryline)

                sfs = search_filer.search_check()
                match = sfs.check_for_first_result(
                    result_generator, is_info, prefer_pack=mylar.CONFIG.PACK_PRIORITY
                )

                if match is not None:
                    verified_matches = [match]
                    logger.fdebug('verified_matches: %s' % (verified_matches,))
                    break

                # reuse the DDL query delay
                logger.fdebug('sleep...%s%s' % (mylar.CONFIG.DDL_QUERY_DELAY, 's'))
                time.sleep(mylar.CONFIG.DDL_QUERY_DELAY)

            return verified_matches if verified_matches else 'no results'

        except requests.exceptions.Timeout as e:
            logger.warn('Timeout occurred fetching data from AirDC++: %s' % e)
            return 'no results'
        except requests.exceptions.ConnectionError as e:
            logger.warn('[WARNING] Connection refused to AirDC++. Error returned as: %s' % e)
            if any([errno.ETIMEDOUT, errno.ECONNREFUSED, errno.EHOSTDOWN, errno.EHOSTUNREACH]):
                helpers.disable_provider('AirDCPP', 'Connection Refused.')
            return 'no results'
        except Exception as err:
            logger.warn('[WARNING] Unable to connect to AirDC++. Error returned as: %s' % err)
            exc_type, exc_value, exc_tb = sys.exc_info()
            filename, line_num, func_name, err_text = traceback.extract_tb(exc_tb)[-1]
            logger.error('[ERROR] %s line %s in %s: %s' % (filename, line_num, func_name, err_text))
            return 'no results'

    def create_search_instance(self):
        """
        Create a search instance in AirDC++

        Returns:
        int: The search instance ID or None if failed
        """
        try:
            url = f"{self.api_url}/search"

            response = self.session.post(
                url,
                headers=self.headers,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                logger.fdebug(f"[AIRDCPP] Created search instance: {data}")
                return data.get('id')
            else:
                logger.warn(f"[AIRDCPP] Failed to create search instance: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"[AIRDCPP] Error creating search instance: {e}")
            return None

    def search_hub(self, search_instance_id, queryline, file_type="file"):
        """
        Search hubs with the given query

        Parameters:
        search_instance_id (int): The search instance ID
        queryline (str): The search query

        Returns:
        str: The search ID or None if failed
        """
        try:
            # Prepare the search query payload
            payload = {
                "query": {
                    "pattern": queryline,
                    "file_type": file_type,
                    "extensions": self.comic_extensions
                },
                "priority": 3
            }
            if len(mylar.CONFIG.AIRDCPP_HUBS) > 0:
                payload["hub_urls"] = mylar.CONFIG.AIRDCPP_HUBS.split(',')
            time.sleep(45)
            response = self.session.post(
                f"{self.api_url}/search/{search_instance_id}/hub_search",
                json=payload,
                headers=self.headers,
                timeout=30
            )
            logger.fdebug(f"[AIRDCPP] Hub search payload prepared: {payload}")

            if response.status_code == 200:
                data = response.json()
                logger.fdebug(f"[AIRDCPP] Hub search initiated: {data}")
                return data.get('search_id')
            else:
                logger.warn(f"[AIRDCPP] Failed to search hub: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"[AIRDCPP] Error searching hub: {e}")
            return None

    def get_search_results(self, search_instance_id, start=0, count=50):
        """
        Get search results from AirDC++

        Parameters:
        search_instance_id (int): The search instance ID
        start (int): The start index for pagination
        count (int): The number of results to return

        Returns:
        list: The search results or empty list if failed
        """
        try:
            response = self.session.get(
                f"{self.api_url}/search/{search_instance_id}/results/{start}/{count}",
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"[AIRDCPP] Got {len(data)} search results")
                return data
            else:
                logger.warn(f"[AIRDCPP] Failed to get search results: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"[AIRDCPP] Error getting search results: {e}")
            return []

    def perform_search_queries(self, queryline):
        """
        Perform the actual search query to AirDC++ API

        Parameters:
        queryline (str): The formatted search query

        Yields:
        dict: Search result entries
        """
        search_instance_id = self.create_search_instance()
        if not search_instance_id:
            logger.error("[AIRDCPP] Failed to create search instance")
            return

        # Store the search instance ID - this is needed for downloads
        self.current_search_instance_id = search_instance_id
        search_id = self.search_hub(search_instance_id, queryline)
        if not search_id:
            logger.error("[AIRDCPP] Failed to search hub")
            return
        logger.fdebug("[AIRDCPP] Waiting for search to be sent to hubs...")

        # Wait for results - usually 10-15 seconds is enough
        time.sleep(45)
        results = self.get_search_results(search_instance_id)

        if not results:
            logger.fdebug("[AIRDCPP] No results found")
            return

        logger.fdebug(f"[AIRDCPP] Processing {len(results)} search results")

        for result in results:
            # Skip directories
            if result.get('type', {}).get('id') == 'directory':
                logger.fdebug(f"[AIRDCPP] Skipping directory: {result.get('name')}")
                continue

            # Only process CBR/CBZ files
            file_extension = result.get('type', {}).get('str', '').lower()
            if file_extension not in self.comic_extensions:
                logger.fdebug(f"[AIRDCPP] Skipping non-comic file: {result.get('name')} ({file_extension})")
                continue

            size_bytes = result.get('size', 0)
            if isinstance(size_bytes, (int, float)):
                # Convert to MB and format as string like "25.5 MB"
                size_mb = size_bytes / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB"
            else:
                size_str = str(size_bytes)

            # Format the result for search_filer
            formatted_result = {
                'title': result.get('name', ''),
                'link': result.get('id', ''),  # Using ID as the link
                'size': size_str,
                'size_bytes': size_bytes,
                'pubdate': None,  # AirDC++ results done have dates
                'site': 'AirDCPP',
                'mode': 'direct',
                'pack': False,
                'issues': None,
                'filename': result.get('name', ''),
                'download': result.get('id', ''),  # Using ID for download
                'id': result.get('id', ''),
                # Add additional info that might be useful
                'free_slots': result.get('slots', {}).get('free', 0),
                'total_slots': result.get('slots', {}).get('total', 0),
                'hits': result.get('hits', 0),
                'search_instance_id': search_instance_id
            }

            logger.info(f"[AIRDCPP] Yielding result: {formatted_result['title']} "
                        f"(size: {formatted_result['size']}, "
                        f"slots: {formatted_result['free_slots']}/{formatted_result['total_slots']}, "
                        f"hits: {formatted_result['hits']})")

            yield formatted_result

    def check_download_complete(self, bundle_id, filename, max_wait=1800, check_interval=5):
        """
        Check if a download is complete by monitoring the bundle status

        Parameters:
        bundle_id (int): The bundle ID from the download response
        filename (str): The filename to check
        max_wait (int): Maximum time to wait in seconds
        check_interval (int): Time between checks in seconds

        Returns:
        bool: True if download is complete, False otherwise
        """
        if mylar.CONFIG.AIRDCPP_DOWNLOAD_DIR:
            dl_location = mylar.CONFIG.AIRDCPP_DOWNLOAD_DIR
        else:
            dl_location = os.path.join(mylar.CONFIG.DDL_LOCATION, 'airdcc')

        filepath = os.path.join(dl_location, filename)
        start_time = time.time()

        logger.info(f"[AIRDCPP] Checking download status for {filename}")

        while time.time() - start_time < max_wait:
            try:
                response = self.session.get(
                    f"{self.api_url}/queue/bundles/{bundle_id}",
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code == 200:
                    bundle_data = response.json()
                    status = bundle_data.get('status', {})
                    if status.get('completed', False):
                        logger.info(f"[AIRDCPP] Download reported as completed by API")
                        if os.path.exists(filepath):
                            final_size = os.path.getsize(filepath)
                            logger.info(f"[AIRDCPP] Download complete: {filename} ({final_size / (1024 * 1024):.2f} MB)")
                            return True
                        else:
                            logger.warn(f"[AIRDCPP] Download completed but file not found: {filepath}")
                            return False

                    downloaded = bundle_data.get('downloaded_bytes', 0)
                    total = bundle_data.get('size', 0)
                    if total > 0:
                        percentage = (downloaded / total) * 100
                        logger.info(f"[AIRDCPP] Download progress: {percentage:.2f}% ({downloaded / (1024 * 1024):.2f}/{total / (1024 * 1024):.2f} MB)")

                else:
                    logger.warn(f"[AIRDCPP] Failed to get bundle status: {response.status_code}")

            except Exception as e:
                logger.warn(f"[AIRDCPP] Error checking download status via API: {e}")

            time.sleep(check_interval)

        logger.warn(f"[AIRDCPP] Download timeout for {filename} after {max_wait/60:.2f} minutes")
        return False

    def download(self, link, filename, id, issueid=None, site=None, search_instance_id=None):
        """
        Download a comic from AirDC++

        Parameters:
        link (str): The download link (TTH hash)
        filename (str): The filename to save as
        id (str): The ID of the comic
        issueid (str, optional): The issue ID
        site (str, optional): The site name
        search_instance_id (str, optional): The search instance ID to use

        Returns:
        dict: Status of the download
        """
        logger.info(f"[AIRDCPP] Attempting to download {filename} with TTH: {link}")

        if mylar.CONFIG.AIRDCPP_DOWNLOAD_DIR:
            dl_location = mylar.CONFIG.AIRDCPP_DOWNLOAD_DIR
        else:
            dl_location = os.path.join(mylar.CONFIG.DDL_LOCATION, 'airdcpp')

        dl_location = dl_location.replace('\\', '/')  # Convert Windows backslashes to forward slashes
        if not dl_location.endswith('/'):
            dl_location += '/'

        if not os.path.isdir(dl_location):
            checkdirectory = mylar.filechecker.validateAndCreateDirectory(dl_location, True)
            if not checkdirectory:
                logger.warn('[ABORTING] Error trying to validate/create AirDC++ download directory: %s.' % dl_location)
                return {"success": False, "filename": filename, "path": None}

        try:
            # Use the previous search instance ID - mandatory because we need to get the TTH from the previous search
            if search_instance_id is None:
                search_instance_id = self.current_search_instance_id

            payload = {
                "target_directory": dl_location,
                "target_name": filename,
                "priority": 4
            }

            # Send the download request with the search instance and TTH as result_id
            # The TTH hash is used directly as the result_id
            response = self.session.post(
                f"{self.api_url}/search/{search_instance_id}/results/{link}/download",
                json=payload,
                headers=self.headers,
                timeout=30
            )
            logger.info(
                f"[AIRDCPP] Initiating download with URL: {self.api_url}/search/{search_instance_id}/results/{link}/download")
            logger.info(f"[AIRDCPP] Download request payload: {payload}")

            if response.status_code != 200:
                logger.error(f"[AIRDCPP] Failed to initiate download: {response.status_code} - {response.text}")
                return {"success": False, "filename": filename, "path": None}

            # Get the download response and extract bundle ID
            download_data = response.json()
            logger.info(f"[AIRDCPP] Download initiated: {download_data}")

            bundle_id = download_data.get('bundle_info', {}).get('id')
            if not bundle_id:
                logger.error("[AIRDCPP] No bundle ID in download response")
                return {"success": False, "filename": filename, "path": None}

            # Check for download completion using bundle ID
            download_complete = self.check_download_complete(bundle_id, filename)

            if download_complete:
                filepath = os.path.join(dl_location, filename)
                if os.path.exists(filepath):
                    # If the file exists, the download was successful
                    logger.info(f"[AIRDCPP] Download completed successfully: {filepath}")

                    # If issueid is provided, rename the file to include it
                    if issueid:
                        file, ext = os.path.splitext(filename)
                        new_filename = f"{file}[__{issueid}__]{ext}"
                        new_filepath = os.path.join(dl_location, new_filename)
                        try:
                            os.rename(filepath, new_filepath)
                            filepath = new_filepath
                            filename = new_filename
                            logger.info(f"[AIRDCPP] File renamed to include issue ID: {new_filepath}")
                        except Exception as e:
                            logger.warn(f"[AIRDCPP] Unable to rename file: {e}")

                    return {"success": True, "filename": filename, "path": filepath}
                else:
                    logger.error(f"[AIRDCPP] Download completed but file not found: {filepath}")
                    return {"success": False, "filename": filename, "path": None}
            else:
                logger.error(f"[AIRDCPP] Download did not complete within the timeout period")
                return {"success": False, "filename": filename, "path": None}

        except Exception as e:
            logger.error(f"[AIRDCPP] Error downloading file: {e}")
            return {"success": False, "filename": filename, "path": None, "link_type_failure": site}

    def rss_download(self, tth_hash, filename, issueid=None):
        """
        Download a file from AirDC++ using TTH hash from RSS
        This bypasses the search and goes straight to download
        """
        logger.info(f"[AIRDCPP][RSS] Starting RSS download for TTH: {tth_hash}")

        # Create search instance for the download
        search_instance_id = self.create_search_instance()
        if not search_instance_id:
            logger.error("[AIRDCPP][RSS] Failed to create search instance")
            return {"success": False, "filename": filename, "path": None}

        # Store the search instance ID
        self.current_search_instance_id = search_instance_id

        # Search for the TTH hash using TTH file type
        search_query = tth_hash
        logger.info(f"[AIRDCPP][RSS] Searching for TTH: {search_query}")

        # Search for the specific TTH with file_type="tth"
        search_id = self.search_hub(search_instance_id, search_query, file_type="tth")
        if not search_id:
            logger.error("[AIRDCPP][RSS] Failed to initiate TTH search")
            return {"success": False, "filename": filename, "path": None}

        # Wait for search results (shorter wait since we're looking for specific TTH)
        logger.info("[AIRDCPP][RSS] Waiting for TTH search results...")
        time.sleep(15)  # Shorter wait for TTH search

        # Get search results
        results = self.get_search_results(search_instance_id)

        if not results:
            logger.warn(f"[AIRDCPP][RSS] No results found for TTH: {tth_hash}")
            return {"success": False, "filename": filename, "path": None}

        logger.info(f"[AIRDCPP][RSS] Found {len(results)} results for TTH search")

        # Since we searched by TTH, any result is a match - just take the first one
        if len(results) > 0:
            result = results[0]
            target_result_id = result.get('id', '')
            result_name = result.get('name', '')

            logger.info(f"[AIRDCPP][RSS] Using TTH search result: {result_name} (ID: {target_result_id})")

            # Download using the found result ID
            download_result = self.download(
                link=target_result_id,
                filename=result_name,
                id=tth_hash,
                issueid=issueid,
                site='AirDCPP',
                search_instance_id=search_instance_id
            )

            if download_result and download_result.get('success'):
                logger.info(f"[AIRDCPP][RSS] Successfully downloaded via RSS: {filename}")
                return download_result
            else:
                error_info = download_result.get('link_type_failure',
                                                 'Unknown error') if download_result else 'No response'
                logger.error(f"[AIRDCPP][RSS] Download failed: {error_info}")
                return {"success": False, "filename": filename, "path": None}
        else:
            logger.error(f"[AIRDCPP][RSS] No results returned for TTH search: {tth_hash}")
            return {"success": False, "filename": filename, "path": None}


if __name__ == '__main__':
    test = AirDCPP(query={'comicname': 'Batman', 'issue': '1', 'year': '2020'})
    results = test.search()
    print(f"Search results: {results}")
