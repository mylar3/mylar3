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

import requests
import sys
import os
import time
from operator import itemgetter
from pathlib import Path
import urllib

import mylar
from mylar import db, helpers, logger, search, search_filer

class PixelDrain(object):

    def __init__(self):
        self.dl_location = mylar.CONFIG.DDL_LOCATION
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1',
            'Referer': 'https://pixeldrain.com',
        }
        self.session = requests.Session()

    def ddl_download(self, link, id, issueid):
        self.id = id
        self.url = link
        if self.dl_location is not None and not os.path.isdir(
            self.dl_location
        ):
            checkdirectory = mylar.filechecker.validateAndCreateDirectory(
                self.dl_location, True
            )
            if not checkdirectory:
                logger.warn(
                    '[PixelDrain][ABORTING] Error trying to validate/create DDL download'
                    ' directory: %s.' % self.dl_location
                )
                return {"success": False, "filename": filename, "path": None, "link_type_failure": 'GC-Pixel'}


        t = self.session.get(
                self.url,
                verify=True,
                headers=self.headers,
                stream=True,
                timeout=(30,30)
            )

        file_id = os.path.basename(
            urllib.parse.unquote(t.url)
        )  # .decode('utf-8'))
        logger.fdebug(t.url)
        logger.fdebug(t)
        logger.fdebug('[PixelDrain] file_id: %s' % file_id)

        logger.fdebug('[PixelDrain] retrieving info for file_id: %s' % file_id)
        f_info = self.session.get(f"https://pixeldrain.com/api/file/{file_id}/info", verify=True, headers=self.headers,stream=True)
        if f_info.status_code == 200:
            info = f_info.json()
            logger.fdebug('[PixelDrain] pixeldrain_info_response: %s' % info)
            file_info = {'filename': info['name'],
                         'filesize': info['size'],
                         'avail': info['availability'],
                         'can_dl': info['can_download']}
        else:
            # should return null here - unobtainable link.
            file_info = None

        myDB = db.DBConnection()
        # write the filename to the db for tracking purposes...
        logger.info('[PixelDrain] Writing to db: %s [%s]' % (file_info['filename'], file_info['filesize']))
        myDB.upsert(
            'ddl_info',
            {'filename': str(file_info['filename']), 'remote_filesize': str(file_info['filesize']), 'size': helpers.human_size(file_info['filesize'])},
            {'id': self.id},
        )
        logger.fdebug(file_info)

        logger.fdebug('[PixelDrain] now threading the send')
        return self.pixel_ddl(file_id, file_info, issueid)

    def pixel_ddl(self, file_id, fileinfo, issueid):
        filename = fileinfo['filename']
        file, ext = os.path.splitext(os.path.basename( filename ) )
        filename = '%s[__%s__]%s' % (file, issueid, ext)

        filesize = fileinfo['filesize']
        filepath = os.path.join(self.dl_location, filename)

        myDB = db.DBConnection()
        myDB.upsert(
            'ddl_info',
            {'tmp_filename': filename},  # tmp_filename should be all that's needed to be updated at this point...
            {'id': self.id},
        )

        try:
            response = self.session.get(
                    'https://pixeldrain.com/api/file/'+file_id,
                    verify=True,
                    headers=self.headers,
                    stream=True,
                    timeout=(30,30)
                )

            logger.fdebug('[PixelDrain] now writing....')
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        f.flush()

        except Exception as e:
            logger.warn('[PixelDrain][ERROR] %s' % e)
            if 'EBLOCKED' in str(e):
                logger.warn('[PixelDrain] Content has been removed - we should move on to the next one at this point.')
            return {"success": False, "filename": filename, "path": None, "link_type_failure": 'GC-Pixel'}

        logger.fdebug('[PixelDrain] download completed - donwloaded %s / %s' % (os.stat(filepath).st_size, filesize))

        logger.info('[PixelDrain] ddl_linked - filename: %s' % filename)

        if ext == '.zip':
            ggc = mylar.getcomics.GC()
            return ggc.zip_zip(self.id, str(filepath), filename)
        else:
            return {"success": True, "filename": filename, "path": str(filepath)}

if __name__ == '__main__':
    test = PixelDrain()
    test.ddl_down()

