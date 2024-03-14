
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
import datetime
import time
from pathlib import Path
from mega import Mega
import mylar
from mylar import db, helpers, logger

class MegaNZ(object):

    def __init__(self, query=None):
        # if query is None, it's downloading not searching.
        self.query = query
        self.dl_location = os.path.join(mylar.CONFIG.DDL_LOCATION, 'mega')
        self.wrote_tmp = False

    def ddl_download(self, link, filename, id, issueid=None, site=None):
        self.id = id
        if self.dl_location is not None and not os.path.isdir(
            self.dl_location
        ):
            checkdirectory = mylar.filechecker.validateAndCreateDirectory(
                self.dl_location, True
            )
            if not checkdirectory:
                logger.warn(
                    '[ABORTING] Error trying to validate/create DDL download'
                    ' directory: %s.' % self.dl_location
                )
                return {"success": False, "filename": filename, "path": None}


        logger.info('trying link: %s' % (link,))
        logger.info('dl_location: %s / filename: %s' % (self.dl_location, filename))

        mega = Mega()
        try:
            m = mega.login()
            # ddl -mega from gc filename isn't known until AFTER file begins downloading
            # try to get it using the pulic_url_info endpoint
            pui = m.get_public_url_info(link)
            if pui:
                filesize = pui['size']
                filename = pui['name']

                myDB = db.DBConnection()
                # write the filename to the db for tracking purposes...
                logger.info('[get-public-url-info resolved] Writing to db: %s [%s]' % (filename, filesize))
                myDB.upsert(
                    'ddl_info',
                    {'filename': str(filename), 'remote_filesize': str(filesize), 'size': helpers.human_size(str(filesize))},
                    {'id': self.id},
                )

            if filename is None:
                # so null filename now, and it'll be assigned in self.testing
                filename = m.download_url(link, self.dl_location, progress_hook=self.testing)
            else:
                filename = m.download_url(link, self.dl_location, filename, self.testing)
        except Exception as e:
            logger.warn('[MEGA][ERROR] %s' % e)
            if 'EBLOCKED' in str(e):
                logger.warn('Content has been removed - we should move on to the next one at this point.')
            return {"success": False, "filename": filename, "path": None, "link_type_failure": site}
        else:
            og_filepath = os.path.join(self.dl_location, filename) # just default
            if filename is not None:
                og_filepath = filename
                #filepath = filename.parent.absolute()
                file, ext = os.path.splitext(os.path.basename( filename ) )
                filename = '%s[__%s__]%s' % (file, issueid, ext)
                filepath = og_filepath.with_name(filename)
                try:
                    filepath = og_filepath.replace(filepath)
                except Exception as e:
                    logger.warn('unable to rename/replace %s with %s' % (og_filepath, filepath))
                else:
                    logger.info('ddl_linked - filename: %s' % filename)
                if ext == '.zip':
                    ggc = mylar.getcomics.GC()
                    return ggc.zip_zip(id, str(filepath), filename)
                else:
                    return {"success": True, "filename": filename, "path": str(filepath)}
            else:
                logger.warn('filename returned from download has a None value')
                return {"success": False, "filename": filename, "path": None, "link_type_failure": site}

    def testing(self, data):
        mth = ( data['current'] / data['total'] ) * 100

        if data['tmp_filename'] is not None and self.wrote_tmp is False:
            myDB = db.DBConnection()
            # write the filename to the db for tracking purposes...
            logger.info('writing to db: %s [%s][%s]' % (data['name'], data['total'], data['tmp_filename']))
            myDB.upsert(
                'ddl_info',
                {'tmp_filename': str(data['tmp_filename'])},  # tmp_filename should be all that's needed to be updated at this point...
                #{'filename': str(data['name']), 'tmp_filename': str(data['tmp_filename']), 'remote_filesize': str(data['total'])},
                {'id': self.id},
            )
            self.wrote_tmp = True

        #logger.info('%s%s' % (mth, '%'))
        #logger.info('data: %s' % (data,))

        if mth >= 100.0:
            logger.info('status: %s' % (data['status']))
            logger.info('successfully downloaded %s [%s bytes]' % (data['name'], data['total']))

if __name__ == '__main__':
    test = MegaNZ(sys.argv[1])
    test.ddl_search()

