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
import pathlib
import re
import mylar
from mylar import logger

class CDH_MAP(object):

    def __init__(self, filepath, sab=False, nzbget=False, nzbget_server=None):
        self.sab = sab
        self.nzbget = nzbget
        if self.sab is True:
            self.sab_url = mylar.CONFIG.SAB_HOST + '/api'
            self.apikey = mylar.CONFIG.SAB_APIKEY
            dst_dir = mylar.CONFIG.SAB_DIRECTORY
        else:
            dst_dir = mylar.CONFIG.NZBGET_DIRECTORY
            self.server = nzbget_server

        if mylar.OS_DETECT == 'Windows':
            if pathlib.Path(dst_dir).is_absolute():
                self.sab_dir = pathlib.PureWindowsPath(dst_dir)
            else:
                self.sab_dir = pathlib.PurePosixPath(dst_dir)
            if pathlib.Path(filepath).is_absolute():
                logger.fdebug('[CDH MAPPING] path is LOCAL to system')
                self.storage = pathlib.PureWindowsPath(filepath)
            else:
                logger.fdebug('[CDH MAPPING] path is NOT LOCAL to system')
                self.storage = pathlib.PurePosixPath(filepath)
        else:
            if pathlib.Path(dst_dir).is_absolute():
                self.sab_dir = pathlib.PurePosixPath(dst_dir)
            else:
                self.sab_dir = pathlib.PureWindowsPath(dst_dir)
            if pathlib.Path(filepath).is_absolute():
                logger.fdebug('[CDH MAPPING] path is LOCAL to system')
                self.storage = pathlib.PurePosixPath(filepath)
            else:
                logger.fdebug('[CDH MAPPING] path is NOT LOCAL to system')
                self.storage = pathlib.PureWindowsPath(filepath)

        self.basedir = None
        self.subdir = False
        try:
            from requests.packages.urllib3 import disable_warnings
            disable_warnings()
        except:
            pass

    def the_sequence(self):
        if self.sab is True:
            self.completedir()
            self.cats()
            cat_dir = self.cat['dir']
            cat_name = self.cat['name']

            if cat_dir is None:
                logger.fdebug('[CDH MAPPING] No category defined - using %s as the base download folder with no job folder creation' % self.cdir)
                self.basedir = self.cdir
            else:
                if cat_dir.endswith('*'):
                    logger.fdebug('[CDH MAPPING][%s] category defined - no job folder creation defined - using %s as base download folder' % (cat_name, cat_dir))
                    self.basedir = cat_dir[:-1]
                else:
                    logger.fdebug('[CDH MAPPING][%s] category defined - job folder creation defined - using %s as based download folder with sub folder creation' % (cat_name, cat_dir))
                    self.basedir = cat_dir
                    self.subdir = True

        else:
            #query nzbget for categories and if path is different
            self.send_nzbget()
            cat_dir = self.cat['dir']
            cat_name = self.cat['name']
            if cat_dir is None:
                logger.fdebug('[CDH MAPPING] No category defined - using %s as the base download folder with no job folder creation' % self.cdir)
                self.basedir = self.cdir
            else:
                if self.subdir is False:
                    logger.fdebug('[CDH MAPPING][%s] category defined - no job folder creation defined - using %s as base download folder' % (cat_name, self.cdir))
                    self.basedir = self.cdir
                else:
                    logger.fdebug('[CDH MAPPING][%s] category defined - job folder creation defined - using %s as based download folder with sub folder creation' % (cat_name, cat_dir))
                    self.basedir = cat_dir

        logger.fdebug('[CDH MAPPING] Base directory for downloads set to: %s' % (self.basedir))
        logger.fdebug('[CDH MAPPING] Downloaded file @: %s' % self.storage)
        logger.fdebug('[CDH MAPPING] Destination root directory @: %s' % (self.sab_dir))

        if self.subdir is False:
            maindir = self.storage.parents[0]
            file = self.storage.name
        else:
            maindir = self.storage.parents[1]
            file = self.storage.relative_to(maindir)
        final_dst = self.sab_dir.joinpath(file)
        return final_dst

    def sendsab(self, params):
        response = requests.get(self.sab_url, params=params, verify=False)
        response = response.json()
        return response

    def completedir(self):
        params = {'mode': 'fullstatus',
                  'apikey': self.apikey,
                  'output': 'json'}

        self.cdir = self.sendsab(params)['status']['completedir']
        logger.fdebug(self.cdir)

    def cats(self):
        params =  {'mode': 'get_config',
                  'section': 'categories',
                   'keyword': 'comics',
                   'apikey': self.apikey,
                   'output': 'json'}
        cats = self.sendsab(params)['config']['categories']
        cat_dir = None
        cat_name= None
        self.subdir = False
        for x in cats:
            if x['name'] == 'comics':
                cat_dir = x['dir']
                cat_name = x['name']
                logger.fdebug(cat_dir)
                break

        self.cat = {'name': cat_name,
                    'dir': cat_dir}

    def send_nzbget(self):
        cinfo = self.server.config()
        cat_number = None
        cat_name = None
        cat_dir = None
        self.subdir = False
        set_cat = mylar.CONFIG.NZBGET_CATEGORY
        for item in cinfo:
            if item['Name'] == 'DestDir':
                self.cdir = item['Value']
            if item['Name'] == 'AppendCategoryDir':
                if item['Value'] == 'yes':
                    self.subdir = True
                else:
                    self.subdir = False

            if 'Category' in item['Name'] and set_cat is not None:
                if item['Value'].lower() == set_cat.lower():
                    cat_number = re.sub(r'[^0-9]', '', item['Name']).strip()
                    cat_name = item['Value']

                if cat_number is not None:
                    tmpcat = 'Category%s.DestDir' % cat_number
                    if item['Name'] == tmpcat:
                        cat_dir = item['Value']
                        break
                    else:
                        cat_number = None

        self.cat = {'name': cat_name,
                    'dir': cat_dir}
