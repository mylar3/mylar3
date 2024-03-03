# -*- coding: utf-8 -*-

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

import os
import os.path as osp
import urllib
import re
import shutil
import sys
import requests
import mylar
from mylar import db, helpers, logger, search, search_filer

class MediaFire(object):

    def __init__(self):
        self.dl_location = os.path.join(mylar.CONFIG.DDL_LOCATION)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.178 Safari/537.36"
        }
        self.session = requests.Session()

    def extractDownloadLink(self, contents):
        for line in contents.splitlines():
            m = re.search(r'href="((http|https)://download[^"]+)', line)
            if m:
                return m.groups()[0]

    def ddl_download(self, url, id, issueid):
        url_origin = url

        while True:
            t = self.session.get(
                    url,
                    verify=True,
                    headers=self.headers,
                    stream=True,
                    timeout=(30,30)
                )

            if 'Content-Disposition' in t.headers:
                # This is the file
                break

            # Need to redirect with confiramtion
            url = self.extractDownloadLink(t.text)

            if url is None:
                #link no longer valid
                return {"success": False, "filename": None, "path": None, "link_type_failure": 'GC-Media'}

        m = re.search(
            'filename="(.*)"', t.headers['Content-Disposition']
        )
        filename = m.groups()[0]
        filename = filename.encode('iso8859').decode('utf-8')

        file, ext = os.path.splitext(filename)
        filename = '%s[__%s__]%s' % (file, issueid, ext)

        try:
            filesize = int(t.headers['Content-Length'])
        except Exception:
            filesize = 0

        fileinfo = {'filename': filename,
                    'filesize': filesize}

        logger.fdebug('Downloading...')
        logger.fdebug('%s [%s bytes]' % (filename, filesize))
        logger.fdebug('From: %s' % url_origin)
        logger.fdebug('To: %s' % os.path.join(self.dl_location, filename))

        myDB = db.DBConnection()
        ## write the filename to the db for tracking purposes...
        logger.fdebug('[Writing to db: %s' % (filename))
        myDB.upsert(
            'ddl_info',
            {'filename': str(filename), 'remote_filesize': str(filesize), 'size': helpers.human_size(filesize)},
            {'id': id},
        )
        return self.mediafire_dl(url, id, fileinfo, issueid)

    def mediafire_dl(self, url, id, fileinfo, issueid):
        filepath = os.path.join(self.dl_location, fileinfo['filename'])

        myDB = db.DBConnection()
        myDB.upsert(
            'ddl_info',
            {'tmp_filename': fileinfo['filename']},  # tmp_filename should be all that's needed to be updated at this point...
            {'id': id},
        )

        try:
            response = self.session.get(
                    url,
                    verify=True,
                    headers=self.headers,
                    stream=True,
                    timeout=(30,30)
                )

            logger.fdebug('[MediaFire] now writing....')
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
                        f.flush()

        except Exception as e:
            logger.fdebug('[MediaFire][ERROR] %s' % e)
            if 'EBLOCKED' in str(e):
                logger.fdebug('[MediaFire] Content has been removed - we should move on to the next one at this point.')
            return {"success": False, "filename": None, "path": None, "link_type_failure": 'GC-Media'}

        try:
            filesize = os.stat(filepath).st_size
        except FileNotFoundError:
            return {"success": false, "filenme": None, "path": None}
        else:
            logger.fdebug('[MediaFire] download completed - downloaded %s / %s' % (filesize, fileinfo['filesize']))

        logger.fdebug('[MediaFire] ddl_linked - filename: %s' % fileinfo['filename'])

        file, ext = os.path.splitext(fileinfo['filename'])
        if ext == '.zip':
            ggc = mylar.getcomics.GC()
            return ggc.zip_zip(id, str(filepath), fileinfo['filename'])
        else:
            return {"success": True, "filename": fileinfo['filename'], "path": str(filepath)}

