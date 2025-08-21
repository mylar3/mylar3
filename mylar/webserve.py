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
import io
import sys
import cherrypy
import requests
import datetime
from datetime import timedelta, date
from collections import OrderedDict
import re
import json
import copy
import stat
import ntpath
from pathlib import Path
from packaging.version import parse as parse_version

from mako.template import Template
from mako.lookup import TemplateLookup
from mako import exceptions

import traceback

import time
import random
import threading
import csv
import platform
import urllib.request, urllib.parse, urllib.error
import shutil
import fnmatch
import simplejson as simplejson
from operator import itemgetter

import xml.etree.ElementTree as ET

from string import ascii_lowercase

import mylar
from mylar import (
    carepackage,
    config,
    db,
    Failed,
    filechecker,
    helpers,
    importer,
    librarysync,
    logger,
    mb,
    moveit,
    notifiers,
    parseit,
    PostProcessor,
    readinglist,
    req_test,
    sabparse,
    search,
    series_metadata,
    updater,
    weeklypull,
)
from mylar.auth import (
    AuthController,
    require,
)

def serve_template(templatename, **kwargs):
    interface_dir = os.path.join(str(mylar.PROG_DIR), 'data/interfaces/')
    if any([mylar.CONFIG.INTERFACE == 'default', mylar.CONFIG.INTERFACE is None]):
        tmper_dir = 'default'
    else:
        tmper_dir = mylar.CONFIG.INTERFACE

    icons = []
    if mylar.CONFIG.INTERFACE == 'default':
        icons = {'icon_gear': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'icon_gear.png'),
                 'icon_upcoming': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'icon_upcoming.png'),
                 'icon_wanted': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'icon_wanted.png'),
                 'icon_search': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'icon_search.png'),
                 'discord-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'discord-icon.png'),
                 'github-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'github-icon.png'),
                 'forum-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'forum-icon.png'),
                 'irc-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'irc-icon.png'),
                 'listview_icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'listview_icon.png'),
                 'delete_icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'delete_icon.png'),
                 'deleteall_icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'deleteall_icon.png'),
                 'prowl_logo': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'prowl_logo.png'),
                 'ReadingList-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'ReadingList-icon.png'),
                 'next': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'next.gif'),
                 'prev': os.path.join(mylar.CONFIG.HTTP_ROOT, 'images', 'prev.gif')}
    else:
        icons = {'icon_gear': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'icon_gear.png'),
                 'icon_upcoming': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'icon_upcoming.png'),
                 'icon_wanted': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'icon_wanted.png'),
                 'icon_search': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'icon_search.png'),
                 'discord-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'discord-icon-carbon.png'),
                 'github-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'github-icon-carbon.png'),
                 'forum-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'forum-icon-carbon.png'),
                 'irc-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'irc-icon-carbon.png'),
                 'listview_icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'listview_icon.png'),
                 'delete_icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'delete_icon.png'),
                 'deleteall_icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'deleteall_icon.png'),
                 'prowl_logo': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'prowl_logo.png'),
                 'ReadingList-icon': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'ReadingList-icon.png'),
                 'next': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'next.gif'),
                 'prev': os.path.join(mylar.CONFIG.HTTP_ROOT, 'interfaces', 'carbon', 'images', 'prev.gif')}

    template_dir = os.path.join(str(interface_dir), tmper_dir)
    _hplookup = TemplateLookup(directories=[template_dir])
    try:
        template = _hplookup.get_template(templatename)
        return template.render(http_root=mylar.CONFIG.HTTP_ROOT, interface=mylar.CONFIG.INTERFACE, icons=icons, gl_messages=mylar.GLOBAL_MESSAGES, sse_key=mylar.SSE_KEY, pre_update=mylar.UPDATE_VALUE, **kwargs)
    except Exception as e:
        #default to base in case the html hasn't been changed in new interface.
        template_dir = os.path.join(str(interface_dir), 'default')
        _hplookup = TemplateLookup(directories=[template_dir])
        try:
            template = _hplookup.get_template(templatename)
            return template.render(http_root=mylar.CONFIG.HTTP_ROOT, interface=mylar.CONFIG.INTERFACE, icons=icons, gl_messages=mylar.GLOBAL_MESSAGES, sse_key=mylar.SSE_KEY, pre_update=mylar.UPDATE_VALUE, **kwargs)
        except Exception:
            return exceptions.html_error_template().render()


class WebMaintenance(object):

    auth = AuthController()

    def default(self, attr='abc'):
        raise cherrypy.HTTPRedirect("maintenance_mode")
    default.exposed = True

    def maintenance_mode(self):
        return serve_template(templatename='maintenance_mode.html', title='Maintenance Mode!')
    maintenance_mode.exposed = True

    def check_ActiveMaintenance(self):
        if mylar.MAINTENANCE_DB_COUNT >= mylar.MAINTENANCE_DB_TOTAL:
            status = 'Completed!'
            message = 'completed.'
            updatetype = '.:[RSS table update]:.'
            percent = 0
        else:
            updatetype = '.:[RSS table update]:.'
            status = 'Updating'
            message = 'Currently updating database'
            secondary_msg = '( %s / %s )' % (mylar.MAINTENANCE_DB_COUNT, mylar.MAINTENANCE_DB_TOTAL)
            m_math = int( (mylar.MAINTENANCE_DB_COUNT *100) / (mylar.MAINTENANCE_DB_TOTAL *100) * 100 )
            percent = '%s%s' % (m_math, '%')
        return json.dumps(
                     {
                         'status': status,
                         'percent': percent,
                         'message': message,
                         'secondary_msg': secondary_msg,
                         'updatetype': updatetype
                     }
        )
    check_ActiveMaintenance.exposed = True

    def restart(self):
        logger.info('[RESTART] Now Restarting Mylar...')
        mylar.SIGNAL = 'restart'
        message = 'Restarting...'
        return serve_template(templatename="shutdown.html", title="Restarting", message=message, timer=5)
    restart.exposed = True

    def shutdown(self):
        logger.info('[SHUTDOWN] Now Shutting down Mylar...')
        mylar.SIGNAL = 'shutdown'
        message = 'Shutting Down...'
        return serve_template(templatename="shutdown.html", title="Shutting Down", message=message, timer=5)
    shutdown.exposed = True


class WebInterface(object):

    auth = AuthController()

    def index(self):
        if mylar.SAFESTART:
            raise cherrypy.HTTPRedirect("manageComics")
        else:
            raise cherrypy.HTTPRedirect("home")
    index.exposed=True

    def check_ActiveMaintenance(self):
        # this is just here to return 100% on completion so the reload can occur properly.
        return json.dumps(
                     {
                           'status': 'Completed!',
                           'percent': '100%',
                           'message': 'RSS Update completed!',
                           'secondary_msg': 'Please wait...</br>Disabling Maintenance mode',
                           'updatetype': '.:[RSS table update]:.'
                     }
        )
    check_ActiveMaintenance.exposed = True

    def config_check(self):
        c_msg = '<center>Successfully passed all inital configuration checks..</center>'
        c_status = 'failure'
        if mylar.CONFIG.DESTINATION_DIR is None:
            c_msg = ("<center>Comic Location is not set - this needs to be set and created prior to usage</br>"
                     "go <a href='/config'>Configuration page/Web Interface/Comic Location</a></center>"
                     )
        elif not os.path.exists(mylar.CONFIG.DESTINATION_DIR):
            c_msg = ('<center>Comic Location cannot be accessed - the user running mylar needs full access to this directory.</br>'
                    )
        elif os.path.exists(mylar.CONFIG.DESTINATION_DIR):
            test_file = os.path.join(mylar.CONFIG.CACHE_DIR, '.test_file')
            test_path = os.path.join(mylar.CONFIG.DESTINATION_DIR, '.zzz_check')

            if os.path.exists(test_path):
                try:
                    shutil.remove(test_path)
                except Exception:
                    return

            dir_check = filechecker.validateAndCreateDirectory(test_path, True, dmode='test_check')
            if not dir_check:
                logger.warn('[COMIC-LOCATION-CHECK] Cannot create under %s. This is a critical error and is usually due to incorrect permissions whether owner/group or attributes.'
                            % (mylar.CONFIG.DESTINATION_DIR)
                )
                c_msg = ('<center>Cannot create subdirectories beneath Comic Location path of:</br> %s</br>'
                         'This is a critical error and is usually due to incorrect permissions or owner/group</center>' % mylar.CONFIG.DESTINATION_DIR
                         )
            else:
                logger.fdebug('[COMIC-LOCATION-CHECK] %s is writable...' % mylar.CONFIG.DESTINATION_DIR)
                c_status = 'success'
                if 'windows' not in mylar.OS_DETECT.lower():
                    #test permissions if enabled.
                    if mylar.CONFIG.ENFORCE_PERMS:
                        enperms = filechecker.setperms(test_path, True)
                        if not enperms:
                            logger.warn('[COMIC-LOCATION-CHECK] Unable to properly set permissions with provided permissions')
                            c_msg = ('<center>Cannot set permissions for Comic Location with provided information:</br>'
                                     'owner: %s</br>'
                                     'group: %s</br>'
                                     'directory: %s</br>'
                                     'file: %s</center>' % (mylar.CONFIG.CHOWNER, mylar.CONFIG.CHGROUP, mylar.CONFIG.CHMOD_DIR, mylar.CONFIG.CHMOD_FILE)
                                     )
                            c_status = 'failure'

                # to - do
                # test copying from cache to comic location path
                #try:
                #    fileoperation = helpers.file_ops(test_file, os.path.join(test_path, '.test_file'))
                #    if not fileoperation:
                #        raise OSError
                #except Exception as e:
                #    logger.warn('[COMIC-LOCATION-CHECK] Cannot copy from cache location to comic location. This is an error: %s' % e)
                #    c_msg = 'Unable to copy from cache to comic location. This is an error'
                #else:
                #    logger.info('[COMIC-LOCATION-CHECK] Copying from cache to series directory successful (for metadata writing)')
                #    c_status = 'success'

        #only display a popup on error
        mylar.START_UP = False

        if c_status == 'failure':
            mylar.GLOBAL_MESSAGES = {'event': 'config_check', 'status': c_status, 'message': c_msg}

    def home(self, **kwargs):
        if mylar.START_UP is True:
            self.config_check()
        # pass the proper table colors here
        if mylar.CONFIG.INTERFACE == 'default':
            legend_colors = {'paused': '#f9cbe6',
                             'removed': '#ddd',
                             'loading': '#ebf5ff',
                             'failed': '#ffdddd'}
        else:
            legend_colors = {'paused': '#bd915a',
                             'removed': '#382f64',
                             'loading': '#1c5188',
                             'failed': '#641716'}

        return serve_template(templatename="index.html", title="Home", alphaindex=mylar.CONFIG.ALPHAINDEX, legend_colors=legend_colors)
    home.exposed = True

    def alpha_volume_counts(self, as_json = True, **kwargs):
        # Convert if calling from params
        if as_json == 'true':
            as_json = True
        elif as_json == 'false':
            as_json = False

        alphabet_lengths = dict.fromkeys(['All','#'] + list(ascii_lowercase), 0)
        # Saving this regexp version but I can't see how it's performant compared to using in-built functions
        #letter_query = "SELECT lower(substr(c.ComicName,1,1)) AS 'Character', Count(c.ComicID) AS 'Count' FROM Comics c WHERE c.ComicName REGEXP '^[a-zA-Z]' GROUP BY 1 UNION SELECT '#' AS 'Character', Count(c.ComicID) AS 'Count' FROM Comics c WHERE c.ComicName REGEXP '^[^a-zA-Z]' GROUP BY 1"
        letter_query = "SELECT lower(substr(c.ComicName,1,1)) as 'Character', COUNT(c.ComicID) as 'Count' FROM Comics c WHERE hex(lower(substr(c.ComicName,1,1))) BETWEEN '61' AND '7A' GROUP BY 1 UNION SELECT '#' as 'Character', COUNT(c.ComicID) as 'Count' FROM Comics c WHERE NOT hex(lower(substr(c.ComicName,1,1))) BETWEEN '61' AND '7A' GROUP BY 1;"
        myDB = db.DBConnection()
        result = myDB.select(letter_query)
        for letter_count in result:
            alphabet_lengths['All'] += letter_count['Count']
            alphabet_lengths[letter_count['Character']] += letter_count['Count']

        if as_json:
            return json.dumps(alphabet_lengths)
        else:
            return alphabet_lengths
    alpha_volume_counts.exposed = True


    def loadhome(self, **kwargs):
        iDisplayStart = int(kwargs['start'])
        iDisplayLength = int(kwargs['length'])
        
        if not 'selected' in kwargs.keys() or kwargs['selected'] == 'All':
            resultlist = helpers.havetotals()
        else:
            resultlist = helpers.havetotals(start_char_filter=kwargs['selected'])

        sSearch = kwargs['search[value]']        
        filtered = []

        if sSearch == "" or sSearch == None:
            filtered = resultlist
        else:
            ignore_terms = []
            tsearch = sSearch

            filter_terms = [match.start() for match in re.finditer(r'\:\-', sSearch)]
            for its in filter_terms:
                filterval = sSearch[its:sSearch.find(' ', its)].strip()
                ignore_terms.append( re.sub(r'\:\-', '', filterval) )
                tsearch = re.sub(filterval, '', tsearch)

            if ignore_terms:
                sSearch = tsearch

            searchname = sSearch.split()
            searchname = '*'.join(searchname)
            searchname = re.sub('[\:\-\%\$\#\@\!\.\,\;\/\(\)\+\=\?]','*', sSearch.lower())
            searchpattern = '*%s*' % re.sub('\s','*', searchname.lower())
            fields_to_check = ['ComicName', 'ComicPublisher', 'ComicYear', 'recentstatus', 'displaytype']

            for row in resultlist:
                try:
                    fields_chk = []
                    for ftc in fields_to_check:
                        if row[str(ftc)]:
                            fields_chk.append(row[str(ftc)].lower())
                    if [x for x in ignore_terms for y in fields_chk if x.lower() in y.lower()]:
                        continue
                    else:
                        lat_iss = row['LatestIssue']
                        if lat_iss is None:
                            lat_iss = ''
                        searchname = fnmatch.fnmatch(row['ComicName'].lower(), searchpattern)
                        if any(
                                [
                                  sSearch.lower() in row['ComicPublisher'].lower(),
                                  searchname is True,
                                  sSearch.lower() in row['ComicYear'],
                                  sSearch.lower() in lat_iss,
                                  sSearch.lower() in row['recentstatus'].lower()
                                ]
                        ):
                            filtered.append(row)
                        elif row['displaytype'] is not None and sSearch.lower() in row['displaytype'].lower():
                            filtered.append(row)
                except Exception as e:
                    pass

        # Multisort by using the stable nature of sort in reverse order
        # We have to work out the number of columns based on kwargs keys
        sort_columns = 0        
        while f"order[{sort_columns}][column]" in kwargs.keys():
            sort_columns += 1

        for sort_pos in range(sort_columns, 0, -1):
            iSortCol = kwargs[f'order[{sort_pos-1}][column]']
            sSortDir = kwargs[f'order[{sort_pos-1}][dir]']
        
            if iSortCol == '0':
                sortcolumn = 'ComicPublisher'
            elif iSortCol == '1':
                sortcolumn = 'ComicName'
            elif iSortCol == '2':
                sortcolumn = 'ComicYear'
            elif iSortCol == '3':
                sortcolumn = 'LatestIssue'
            elif iSortCol == '4':
                sortcolumn = 'LatestDate'
            elif iSortCol == '5':
                sortcolumn = 'percent'
            elif iSortCol == '6':
                sortcolumn = 'recentstatus'
            elif iSortCol == '7':
                sortcolumn = 'Status'
            else:
                sortcolumn = 'ComicPublisher'

            if sortcolumn == 'percent':
                filtered.sort(key=lambda x: (x['totalissues'] is None, x['totalissues'] == '', x['totalissues'] == '?', x['totalissues']), reverse=sSortDir == "asc")
                filtered.sort(key=lambda x: (x['percent'] is None, x['percent'] == '', x['percent']), reverse=sSortDir == "desc")
                filtered.sort(key=lambda x: (x['haveissues'] is None, x['haveissues'] == '', x['haveissues']), reverse=sSortDir == "desc")
                filtered.sort(key=lambda x: (x['percent'] is None, x['percent'] == '', x['percent']), reverse=sSortDir == "desc")
            elif sortcolumn == 'LatestIssue':
                filtered.sort(key=lambda x: (x['IntLatestIssue'] is None, x['IntLatestIssue'] == '', x['IntLatestIssue']), reverse=sSortDir == "asc")
            else:
                filtered.sort(key=lambda x: (x[sortcolumn] is None, x[sortcolumn] == '', x[sortcolumn]), reverse=sSortDir == "desc")


        if iDisplayLength != -1:
            rows = filtered[iDisplayStart:(iDisplayStart + iDisplayLength)]
        else:
            rows = filtered
        rows = [[row['ComicPublisher'], row['ComicName'], row['ComicYear'], row['LatestIssue'], row['LatestDate'], row['recentstatus'], row['Status'], row['percent'], row['haveissues'], row['totalissues'], row['ComicID'], row['displaytype'], row['ComicVolume'], row['cv_removed']] for row in rows]
        
        return json.dumps({
            'recordsFiltered': len(filtered),
            'recordsTotal': len(resultlist),
            'data': rows,
        })
    loadhome.exposed = True

    def comicDetails(self, ComicID, addbyid=0, **kwargs):
        myDB = db.DBConnection()
        comic = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
        if comic is None and bool(addbyid) is False:
            raise cherrypy.HTTPRedirect("home")
        elif comic is None and bool(addbyid) is True:
            # blank all the values here so it'll load
            comicname = None
            comic_year = None
            usethefuzzy = "0"
            skipped2wanted = "0"
            force_continuing = 0
            ignore_type = None
            force_type = None
            age_rating = None
            allowpacks = "0"
            corrected_seriesyear = None
            torrentid_32p = None
            totalissues = '?'
            haveissues = 0
            percent = 0
            comicpublisher = helpers.publisherImages(None)
            description = None
            issues_list = None
            secondary_folders = None
            comicImage = "data:image/gif;base64,%s" % mylar.getimage.load_image(os.path.join(mylar.PROG_DIR, 'data', 'images', 'blank.gif'),263)
            comic_status = 'Loading'
            ImageTime = None
            comic = {'ComicID': ComicID,
                     'ComicName': comicname,
                     'Status': 'Loading',
                     'ComicYear': None,
                     'Corrected_SeriesYear': None,
                     'ComicVersion': None,
                     'ComicPublished': None,
                     'ComicPublisher': None,
                     'PublisherImprint': None,
                     'Type': None,
                     'Corrected_Type': None,
                     'AgeRating': None,
                     'Total': 0,
                     'LastUpdated': None,
                     'ComicLocation': None,
                     'AlternateSearch': None,
                     'AlternateFileName': None,
                     'cv_removed': 0,
                     'DetailURL': 'https://comicvine.com/volume/4050-%s' % ComicID}
        else:
            secondary_folders = None
            if mylar.CONFIG.MULTIPLE_DEST_DIRS:
                try:
                    if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comic['ComicLocation']))):
                        secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comic['ComicLocation']))
                    else:
                        # when loading a new series initially the publisher value might not be written out the db yet.
                        # pass this all on the initial load if it's not  - it'll catch it when the page finishes loading.
                        ff = mylar.filers.FileHandlers(ComicID=ComicID)
                        secondary_folders = ff.secondary_folders(comic['ComicLocation'])
                except Exception:
                    pass

            if ComicID is not None:
                comic_ext = ('.cbr','.cbz','.cb7')
                run_them_down = False
            if comic['FilesUpdated']:
                filesupdated = datetime.datetime.strptime(comic['FilesUpdated'], '%Y-%m-%d %H:%M:%S')
            else:
                run_them_down = True

            if all([run_them_down is False, comic['ComicLocation'] is not None, mylar.CONFIG.SCAN_ON_SERIES_CHANGES is True]):
                if os.path.exists(comic['ComicLocation']):
                    if run_them_down is False:
                        file_listing = []
                        filepaths = [comic['ComicLocation']]
                        if secondary_folders is not None:
                            if os.path.exists(secondary_folders):
                                filepaths.append(secondary_folders)

                        for rootpaths in filepaths:
                            if os.stat(rootpaths)[stat.ST_MTIME] > filesupdated.timestamp():
                                # this will pick up any file deletions, renames, additions
                                logger.info('Detected root directory changes @ %s - running them down' % rootpaths)
                                run_them_down = True
                                break
                            for root,dir,files in os.walk(rootpaths):
                                for dr in dir:
                                    if rootpaths == ''.join(dr):
                                        direc = None
                                    else:
                                        direc = ''.join(dr)
                                        if os.stat(os.path.join(root, direc))[stat.ST_MTIME] > filesupdated.timestamp():
                                            logger.info('detected sub-directory changes in %s - running them down' % direc)
                                            run_them_down = True
                                            break
                                for file in files:
                                    if run_them_down is True:
                                        break
                                    if file.startswith('._'):
                                        continue
                                    if file.endswith(tuple(['cbr', 'cbz', 'cb7'])):
                                        mtime = os.path.getmtime(os.path.join(root, file))
                                        if mylar.OS_DETECT == 'Windows':
                                            ctime = os.path.getctime(os.path.join(root, file))
                                        else:
                                            ctime = 0
                                        if mtime > ctime:
                                            the_time = mtime
                                        else:
                                            the_time = ctime
                                        if the_time > filesupdated.timestamp():
                                            logger.info('NEW FILE DETECTED: %s - running them down' % file)
                                            run_them_down = True
                                            break
                            if run_them_down is True:
                                break

                if run_them_down is True:
                    updater.forceRescan(ComicID)
                    comic = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()

            totalissues = comic['Total']
            haveissues = comic['Have']
            if not haveissues:
                haveissues = 0
            try:
                percent = (haveissues *100.0) /totalissues
                if percent > 100:
                    percent = 101
            except (ZeroDivisionError, TypeError):
                percent = 0
                totalissues = '?'

            usethefuzzy = comic['UseFuzzy']
            allowpacks = comic['AllowPacks']
            skipped2wanted = "0"
            if usethefuzzy is None:
                usethefuzzy = "0"
            force_continuing = comic['ForceContinuing']
            if force_continuing is None:
                force_continuing = 0
            if mylar.CONFIG.DELETE_REMOVE_DIR is None:
                mylar.CONFIG.DELETE_REMOVE_DIR = 0
            if allowpacks is None:
                allowpacks = "0"
            if all([comic['Corrected_SeriesYear'] is not None, comic['Corrected_SeriesYear'] != '', comic['Corrected_SeriesYear'] != 'None']):
                if comic['Corrected_SeriesYear'] != comic['ComicYear']:
                    comic['ComicYear'] = comic['Corrected_SeriesYear']

            comicImage = None
            if comic['ComicImage'] is not None:
                coverimage = os.path.join(mylar.CONFIG.CACHE_DIR, os.path.basename(comic['ComicImage']))
                if os.path.exists(coverimage):
                    comicImage = "data:image/webp;base64,%s" % mylar.getimage.load_image(coverimage, 263)
            if not comicImage:
                if os.path.exists(os.path.join(mylar.CONFIG.CACHE_DIR, ComicID + '.jpg')):
                    comicImage = "data:image/webp;base64,%s" % mylar.getimage.load_image(os.path.join(mylar.CONFIG.CACHE_DIR, ComicID + '.jpg'), 263)
                elif os.path.exists(os.path.join(mylar.CONFIG.CACHE_DIR, ComicID + '.png')):
                    comicImage = "data:image/webp;base64,%s" % mylar.getimage.load_image(os.path.join(mylar.CONFIG.CACHE_DIR, ComicID + '.png'), 263)
                else:
                    comicImage = "data:image/gif;base64,%s" % mylar.getimage.load_image(os.path.join(mylar.PROG_DIR, 'data', 'images', 'blank.gif'),263)

            comicpublisher = helpers.publisherImages(comic['ComicPublisher'])

            if mylar.CONFIG.SERIES_METADATA_LOCAL is True:
                description_load = None
                if comic['ComicLocation'] is not None:
                    if os.path.exists(os.path.join(comic['ComicLocation'], 'series.json')):
                        try:
                            with open(os.path.join(comic['ComicLocation'], 'series.json')) as j_file:
                                metainfo = json.load(j_file)
                            try:
                                # series.json 1.0.1
                                description_load = metainfo['metadata']['description_text']
                            except Exception as e:
                                try:
                                    # series.json 1.0
                                    description_load = metainfo['metadata'][0]['description_text']
                                except Exception as e:
                                    description_load = metainfo['metadata'][0]['description']
                        except Exception as e:
                            try:
                                # series.json 1.0.1
                                description_load = metainfo['metadata']['description_formatted']
                            except Exception as e:
                                try:
                                    # series.json 1.0
                                    description_load = metainfo['metadata'][0]['description_formatted']
                                except Exception as e:
                                    logger.info('No description found within series.json. Reloading from dB if available.[error: %s]' % e)

                if mylar.CONFIG.SERIESJSON_FILE_PRIORITY is True:
                    if description_load is not None:
                        description = description_load
                    elif comic['DescriptionEdit'] is not None:
                        description = comic['DescriptionEdit']
                    else:
                        description = comic['Description']
                else:
                    if comic['DescriptionEdit'] is not None:
                        description = comic['DescriptionEdit']
                    elif description_load is not None:
                        description = description_load
                    else:
                        description = comic['Description']
            else:
                description = comic['Description']

            if comic['Collects'] is not None:
                issues_list = json.loads(comic['Collects'])
            else:
                issues_list = None

            if comic['Corrected_Type'] == comic['Type']:
                force_type = None
            else:
                if comic['Corrected_Type'] == 'TPB':
                   force_type = 'TPB'
                elif comic['Corrected_Type'] == 'GN':
                    force_type = 'GN'
                elif comic['Corrected_Type'] == 'HC':
                    force_type = 'HC'
                elif comic['Corrected_Type'] == 'Digital':
                    force_type = 'Digital'
                elif comic['Corrected_Type'] == 'One-Shot':
                    force_type = 'One-Shot'
                elif comic['Corrected_Type'] == 'Print' or comic['Corrected_Type'] is None:
                    if comic['Type'] is None:
                        force_type = 'Print'
                    elif comic['Corrected_Type'] is None:
                        force_type = None
                    else:
                        force_type = comic['Corrected_Type']

            comicname = comic['ComicName']
            ignore_type = comic['IgnoreType']
            age_rating = comic['AgeRating']
            comic_status = comic['Status']
            comic_year = comic['ComicYear']
            secondary_folders = None

            if mylar.CONFIG.MULTIPLE_DEST_DIRS:
                try:
                    if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comic['ComicLocation']))):
                        secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comic['ComicLocation']))
                    else:
                        # when loading a new series initially the publisher value might not be written out the db yet.
                        # pass this all on the initial load if it's not  - it'll catch it when the page finishes loading.
                        ff = mylar.filers.FileHandlers(ComicID=ComicID)
                        secondary_folders = ff.secondary_folders(comic['ComicLocation'])
                except Exception:
                    pass


        #let's cheat. :)
        #comicskip = myDB.select('SELECT * from comics order by ComicSortName COLLATE NOCASE')
        skipno = len(mylar.COMICSORT['SortOrder'])
        lastno = mylar.COMICSORT['LastOrderNo']
        lastid = mylar.COMICSORT['LastOrderID']
        series = {}

        if skipno == 0:
            #it's a blank db, let's just null the values and go.
            series['Current'] = None
            series['Previous'] = None
            series['Next'] = None
        i = 0
        try:
            cskip = mylar.COMICSORT['SortOrder'][0]
        except Exception:
            series['Current'] = None
            series['Previous'] = None
            series['Next'] = None
        else:
            while (i < skipno):
                cskip = mylar.COMICSORT['SortOrder'][i]
                if cskip['ComicID'] == ComicID:
                    cursortnum = cskip['ComicOrder']
                    series['Current'] = cskip['ComicID']
                    if cursortnum == 0:
                        # if first record, set the Previous record to the LAST record.
                        previous = lastid
                    else:
                        previous = mylar.COMICSORT['SortOrder'][i -1]['ComicID']

                    # if last record, set the Next record to the FIRST record.
                    if cursortnum == lastno:
                        next = mylar.COMICSORT['SortOrder'][0]['ComicID']
                    else:
                        next = mylar.COMICSORT['SortOrder'][i +1]['ComicID']
                    series['Previous'] = previous
                    series['Next'] = next
                    break
                i+=1

        if mylar.CONFIG.DEFAULT_DATES == 'store_date':
            default_dates = 'Show Store Date'
        else:
            default_dates = 'Show Cover Date'

        comicConfig = {
                    "fuzzy_year0":                    helpers.radio(int(usethefuzzy), 0),
                    "fuzzy_year1":                    helpers.radio(int(usethefuzzy), 1),
                    "fuzzy_year2":                    helpers.radio(int(usethefuzzy), 2),
                    "skipped2wanted":                 helpers.checked(skipped2wanted),
                    "force_continuing":               helpers.checked(force_continuing),
                    "ignore_type":                    helpers.checked(ignore_type),
                    "force_type":                     force_type,
                    "age_rating":                     age_rating,
                    "delete_dir":                     helpers.checked(mylar.CONFIG.DELETE_REMOVE_DIR),
                    "allow_packs":                    helpers.checked(int(allowpacks)),
                    "corrected_seriesyear":           comic_year,
                    "torrentid_32p":                  None,
                    "totalissues":                    totalissues,
                    "haveissues":                     haveissues,
                    "percent":                        percent,
                    "publisher_image":                comicpublisher['publisher_image'],
                    "publisher_image_alt":            comicpublisher['publisher_image_alt'],
                    "publisher_imageH":               comicpublisher['publisher_imageH'],
                    "publisher_imageW":               comicpublisher['publisher_imageW'],
                    "description":                    description,
                    "issue_list":                     issues_list,
                    "secondary_folders":              secondary_folders,
                    "ComicImage":                     comicImage,
                    "Status":                         comic_status,
                    "ImageTime":                      '?' + datetime.datetime.now().strftime('%y-%m-%d %H:%M:%S')
               }

        return serve_template(templatename="comicdetails_update.html", title=comicname, comic=comic, comicConfig=comicConfig, series=series, default_dates=default_dates)
    comicDetails.exposed = True

    def update_series_filters(self, comicid):
        isCounts = {}
        isCounts[1] = 0   #1 skipped
        isCounts[2] = 0   #2 wanted
        isCounts[3] = 0   #3 archived
        isCounts[4] = 0   #4 downloaded
        isCounts[5] = 0   #5 ignored
        isCounts[6] = 0   #6 failed
        isCounts[7] = 0   #7 snatched
        #isCounts[8] = 0   #8 read

        myDB = db.DBConnection()
        issues = myDB.select('SELECT Status FROM issues WHERE ComicID=? ORDER BY Int_IssueNumber DESC', [comicid])
        if mylar.CONFIG.ANNUALS_ON:
            issues += myDB.select('SELECT Status FROM annuals WHERE ComicID=? AND NOT DELETED ORDER BY Int_IssueNumber DESC', [comicid])
        for curResult in issues:
            baseissues = {'skipped': 1, 'wanted': 2, 'archived': 3, 'downloaded': 4, 'ignored': 5, 'failed': 6, 'snatched': 7}
            for seas in baseissues:
                if curResult['Status'] is None:
                   continue
                else:
                    if seas in curResult['Status'].lower():
                        sconv = baseissues[seas]
                        isCounts[sconv]+=1
                        continue

        isCounts = {
                 "skipped": str(isCounts[1]),
                 "wanted": str(isCounts[2]),
                 "archived": str(isCounts[3]),
                 "downloaded": str(isCounts[4]),
                 "ignored": str(isCounts[5]),
                 "failed": str(isCounts[6]),
                 "snatched": str(isCounts[7])
               }
        return json.dumps({'status': 'success', 'filters': isCounts})
    update_series_filters.exposed = True

    def loadIssueDetails(self, ComicID=None, iDisplayStart=0, iDisplayLength=25, iSortCol_0='1', sSortDir_0="desc", sSearch="", **kwargs):
        if ComicID is None:
            ComicID = kwargs['Paging_ComicID']
            #logger.fdebug('issue paging ID: %s' % ComicID)

        try:
            filters = json.loads(kwargs.get('filters'))
        except Exception as e:
            filters = []

        myDB = db.DBConnection()
        sortcolumn = 'b.Int_IssueNumber %s' % sSortDir_0
        if iSortCol_0 == '1':
            sortcolumn = 'b.Int_IssueNumber %s' % sSortDir_0
        elif iSortCol_0 == '2':
            sortcolumn = 'b.IssueName %s' % sSortDir_0
        elif iSortCol_0 == '3':
            sortcolumn = 'b.ReleaseDate %s' % sSortDir_0
        elif iSortCol_0 == '4':
            sortcolumn = 'b.Status %s' % sSortDir_0

        #logger.info('sortcolumn: %s' % sortcolumn)
        queryline = 'SELECT a.ComicLocation as ComicLocation, b.* FROM comics a LEFT JOIN issues b ON a.ComicID = b.ComicID WHERE a.ComicID=? ORDER BY %s' % sortcolumn
        issueslist = myDB.select(queryline, [ComicID])
        issues = []

        secondary_folders = None
        if mylar.CONFIG.MULTIPLE_DEST_DIRS:
            try:
                if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(issueslist[0]['ComicLocation']))):
                    secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(issueslist[0]['ComicLocation']))
                else:
                    # when loading a new series initially the publisher value might not be written out the db yet.
                    # pass this all on the initial load if it's not  - it'll catch it when the page finishes loading.
                    ff = mylar.filers.FileHandlers(ComicID=ComicID)
                    secondary_folders = ff.secondary_folders(issueslist[0]['ComicLocation'])
            except Exception:
                pass


        for x in issueslist:
            # catch false entries here
            if all([x['Int_IssueNumber'] is None, x['Issue_Number'] is None, x['IssueID'] is None]):
                continue
            comicsize= '0MB'
            issue_location = x['Location']
            secondary = False
            if any([x['Status'] == 'Downloaded', x['Status'] == 'Archived']):
                if x['Location'] is not None:
                    if not os.path.exists(os.path.join(x['ComicLocation'], x['Location'])):
                        if secondary_folders is not None:
                            if os.path.exists(os.path.join(secondary_folders, x['Location'])):
                                issue_location = x['Location']
                                secondary = 'secondary'
                comicsize = helpers.human_size(x['ComicSize'])

            foundfilter = False
            for filter in filters:
                if filter['name'] == x['Status']:
                    if filter['value'] is False:
                        foundfilter = True
                        break
            if foundfilter:
                continue

            issues.append({'IssueID': x['IssueID'],
                           'Location': issue_location,
                           'Secondary': secondary,
                           'Issue_Number': x['Issue_Number'],
                           'AltIssueNumber': x['AltIssueNumber'],
                           'IssueDate': x['IssueDate'],
                           'DigitalDate': x['DigitalDate'],
                           'ReleaseDate': x['ReleaseDate'],
                           'IssueName': x['IssueName'],
                           'Status': x['Status'],
                           'ComicSize': comicsize,
                           'ComicID': x['ComicID'],
                           'ComicName': x['ComicName']})

        #logger.info('issues: %s' % (issues,))
        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        filtered = []
        if len(issues) > 0:
            if sSearch == "" or sSearch is None:
                filtered = issues[::]
            else:
                for row in issues:
                    try:
                        issname = row['IssueName']
                        if issname is None:
                            issname = ''
                        if any([sSearch.lower() in issname.lower(), sSearch.lower() in row['Issue_Number'].lower(), sSearch.lower() in row['Status'], sSearch.lower() in row['IssueDate'].lower()]):
                            filtered.append(row)
                    except Exception as e:
                        pass

            if iDisplayLength != -1:
                rows = filtered[iDisplayStart:(iDisplayStart + iDisplayLength)]
            else:
                rows = filtered
            rows = [[row['Issue_Number'], row['IssueName'], row['IssueDate'], row['Status'], row['IssueID'], row['Location'], row['ComicSize'], row['ComicID'], row['ComicName'], row['DigitalDate'], row['ReleaseDate'], row['Secondary'], row['AltIssueNumber']] for row in rows]
        else:
            rows = []

        return json.dumps({
            'iTotalDisplayRecords': len(filtered),
            'iTotalRecords': len(issues),
            'aaData': rows,
        })
    loadIssueDetails.exposed = True

    def loadAnnualDetails(self, ComicID=None, iDisplayStart=0, iDisplayLength=25, iSortCol_0=0, sSortDir_0="desc", sSearch="", **kwargs):
        #logger.info('comicid: %s' % ComicID)
        if ComicID is None:
            ComicID = kwargs['Paging_ComicID']
            #logger.info('Annual paging ID: %s' % ComicID)

        try:
            filters = json.loads(kwargs.get('filters'))
        except Exception as e:
            filters = []

        myDB = db.DBConnection()
        annuals = []
        if mylar.CONFIG.ANNUALS_ON:
            annualslist = myDB.select("SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted ORDER BY ReleaseDate ASC, Int_IssueNumber DESC", [ComicID])
        #    #we need to load in the annual['ReleaseComicName'] and annual['ReleaseComicID']
        #    #then group by ReleaseComicID, in an attempt to create seperate tables for each different annual series.
        #    #this should allow for annuals, specials, one-shots, etc all to be included if desired.
            aName = []
            annualinfo = {}
            prevcomicid = None
            start_date = None
            span = None
            for ann in sorted(annualslist, key=itemgetter('ReleaseComicID', 'ComicID', 'Int_IssueNumber', 'ReleaseDate'), reverse=False):
                foundfilter = False
                for filter in filters:
                    if filter['name'] == ann['Status']:
                        if filter['value'] is False:
                            foundfilter = True
                            break
                if foundfilter:
                    continue
                if not any(d.get('annualComicID', None) == str(ann['ReleaseComicID']) for d in aName):
                    if start_date is not None:
                        end_date = previssdate
                        if end_date[:4] == start_date[:4]:
                            spanline = start_date[:4]
                        else:
                            spanline = '%s - %s' % (start_date[:4], end_date[:4])
                        span = {'span':     spanline,
                                'comicid':  prevcomicid}
                        start_date = ann['IssueDate']
                        if start_date == '0000-00-00':
                            start_date = ann['ReleaseDate']
                        end_date = None
                    else:
                        if ann['IssueDate'] == '0000-00-00':
                            start_date = ann['ReleaseDate']
                        else:
                            start_date = ann['IssueDate']

                    if len(aName) > 0 and span is not None:
                        cnt = 0
                        for f in aName:
                            if f['annualComicID'] == span['comicid']:
                                aName[cnt]['span'] = span['span']
                                break
                            cnt+=1
                        span = None

                    aName.append({"annualComicName":   ann['ReleaseComicName'],
                                  "annualComicID":     ann['ReleaseComicID']})

                issuename = ann['IssueName']
                if ann['IssueName'] is not None:
                    if len(ann['IssueName']) > 75:
                        issuename = '%s...' % ann['IssueName'][:75]

                if ann['ReleaseDate'] == '0000-00-00':
                    sort_date = int(re.sub('[^0-9]', '', ann['IssueDate']).strip())
                else:
                    sort_date = int(re.sub('[^0-9]', '', ann['ReleaseDate']).strip())
                annuals.append({"Issue_Number":      ann['Issue_Number'],
                                "Int_IssueNumber":   ann['Int_IssueNumber'],
                                "IssueName":         issuename,
                                "IssueDate":         ann['IssueDate'],
                                "ReleaseDate":       ann['ReleaseDate'],
                                "DigitalDate":       ann['DigitalDate'],
                                "SortDate":          sort_date,
                                "Status":            ann['Status'],
                                "Location":          ann['Location'],
                                "ComicID":           ann['ComicID'],
                                "IssueID":           ann['IssueID'],
                                "ReleaseComicID":    ann['ReleaseComicID'],
                                "ComicName":         ann['ComicName'],
                                "ComicSize":         helpers.human_size(ann['ComicSize']),
                                "ReleaseComicName":  ann['ReleaseComicName'],
                                "PrevComicID":       prevcomicid})

                prevcomicid = ann['ReleaseComicID']
                if ann['IssueDate'] == '0000-00-00':
                    previssdate = ann['ReleaseDate']
                else:
                    previssdate = ann['IssueDate']

            if len(aName) > 0: # and span is not None:
                end_date = previssdate  #make sure to take the last looped value as the last issue date
                if end_date[:4] == start_date[:4]:
                    spanline = start_date[:4]
                else:
                    spanline = '%s - %s' % (start_date[:4], end_date[:4])
                cnt = 0
                for f in aName:
                    if f['annualComicID'] == prevcomicid:
                        aName[cnt]['span'] = spanline
                        break
                    cnt+=1
            #now we loop through the annual_list matching up to aName and appending the grouped display name for easier displaying in the GUI.
            for f in aName:
                cnt = 0
                for ab in annuals:
                    if f['annualComicID'] == ab['ReleaseComicID']:
                        annuals[cnt]['GroupName'] = '%s [%s]' % (ab['ReleaseComicName'],f['span'])
                        annuals[cnt]['annualComicID'] = str(f['annualComicID'])
                    cnt+=1

            annualinfo = aName
        else:
            annuals = None

        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        filtered = 0
        rows = []
        if annuals is not None:
            if len(annuals) > 0:
                #final_list = sorted(annuals, key=itemgetter('ReleaseComicID', 'SortDate', 'Int_IssueNumber'))
                final_list = sorted(annuals, key=lambda k: (-k['SortDate'], k['Int_IssueNumber']))
                rows = [[row['Issue_Number'], row['IssueName'], row['IssueDate'], row['Status'], row['IssueID'], row['Location'], row['ComicSize'], row['ComicID'], row['ReleaseComicName'], row['ReleaseComicID'], row['GroupName'], row['annualComicID'], row['ReleaseDate'], row['DigitalDate']] for row in final_list]
                filtered = len(rows)

        return json.dumps({
            'iTotalDisplayRecords': filtered,
            'iTotalRecords': len(rows),
            'aaData': rows,
        })
    loadAnnualDetails.exposed = True

    def loadSearchResults(self, query=None, iDisplayStart=0, iDisplayLength=25, iSortCol_0='1', sSortDir_0="desc", sSearch="", **kwargs):

        logger.fdebug('query: %s' % query)
        if query is None:
            query = kwargs['search_query']
            logger.fdebug('search_query: %s' % query)

        myDB = db.DBConnection()
        queryline = "SELECT * FROM tmp_searches WHERE query_id=?" # ORDER BY %s" % sortcolumn
        db_results = myDB.select(queryline, [query])
        if not db_results:
            try:
                results = mb.findComic(query, None, issue=None)
            except Exception as e:
                logger.error('[%s] Unable to perform required search for : [name: %s]' % (e, query))
                return json.dumps({
                    'iTotalDisplayRecords': 0,
                    'iTotalRecords': 0,
                    'aaData': [],
                })
        else:
            results = []
            for rt in db_results:
                results.append({'comicname': rt['comicname'],
                                'publisher': rt['publisher'],
                                'comicid':   rt['comicid'],
                                'comicyear': rt['comicyear'],
                                'volume': rt['volume'],
                                'issues': int(rt['issues']),
                                'deck': rt['deck'],
                                'url': rt['url'],
                                'type': rt['type'],
                                'description': rt['description'],
                                'haveit': rt['haveit'],
                                'query_id': rt['query_id']})

        if not results:
            return json.dumps({
                'iTotalDisplayRecords': 0,
                'iTotalRecords': 0,
                'aaData': [],
            })
        if sSearch == "" or sSearch == None:
            filtered = results[::]
        else:
            filtered = []
            ignore_terms = []

            filter_terms = [match.start() for match in re.finditer(r'\:\-', sSearch)]
            tsearch = sSearch
            for its in filter_terms:
                filterval = sSearch[its:sSearch.find(' ', its)].strip()
                ignore_terms.append( re.sub(r'\:\-', '', filterval) )
                tsearch = re.sub(filterval, '', tsearch)

            if ignore_terms:
                sSearch = tsearch

            searchname = sSearch.split()
            searchname = '*'.join(searchname)

            searchname = re.sub('[\:\-\%\$\#\@\!\.\,\;\/\(\)\+\=\?]','*', sSearch.lower())
            searchpattern = '*%s*' % re.sub('\s','*', searchname.lower())
            fields_to_check = ['comicname', 'volume', 'type', 'publisher', 'comicyear']
            for row in results:
                try:
                    fields_chk = []
                    for ftc in fields_to_check:
                        if row[str(ftc)]:
                            fields_chk.append(row[str(ftc)].lower())
                    if [x for x in ignore_terms for y in fields_chk if x.lower() in y.lower()]:
                        continue
                    else:
                        searchname = fnmatch.fnmatch(row['comicname'].lower(), searchpattern)
                        if any(
                               [
                                 sSearch.lower() in row['publisher'].lower(),
                                 searchname is True,
                                 sSearch.lower() in row['comicyear']
                               ]
                        ):
                            filtered.append(row)
                except Exception as e:
                    pass

        sortcolumn = 'comicname'
        if iSortCol_0 == '1':
            sortcolumn = 'comicname'
        elif iSortCol_0 == '2':
            sortcolumn = 'publisher'
        elif iSortCol_0 == '3':
            sortcolumn = 'comicyear'
        elif iSortCol_0 == '4':
            sortcolumn = 'issues'

        if sortcolumn == 'issues':
            filtered.sort(key=lambda x: (x[sortcolumn] is None, x[sortcolumn] == '', x[sortcolumn]), reverse=sSortDir_0 == "desc")
        else:
            filtered.sort(key=lambda x: (x[sortcolumn] is None, x[sortcolumn] == '', x[sortcolumn]), reverse=sSortDir_0 == "desc")

        logger.info('# of results: %s' % len(filtered))
        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        # -1 is used for "All" in DataTables filters
        if iDisplayLength > 0:
            filtered = filtered[iDisplayStart:(iDisplayStart + iDisplayLength)]
        rows = [[row['comicid'], row['comicname'], row['publisher'], row['comicyear'], row['issues'], row['deck'], row['url'], row['type'], row['description'], row['haveit'], row['query_id']] for row in filtered]

        return json.dumps({
            'iTotalDisplayRecords': len(results), #len(filtered),
            'iTotalRecords': len(results),
            'aaData': rows,
        })
    loadSearchResults.exposed = True

    def searchit(self, name, issue=None, smode=None, search_type=None, serinfo=None):
        if search_type is None: search_type = 'comic'  # let's default this to comic search only for the time being (will add story arc, characters, etc later)
        else: logger.fdebug(str(search_type) + " mode enabled.")
        #mode dictates type of search:
        # --series     ...  search for comicname displaying all results
        # --pullseries ...  search for comicname displaying a limited # of results based on issue
        # --want       ...  individual comics
        if smode is None: smode = 'series'
        if len(name) == 0:
            raise cherrypy.HTTPRedirect("home")
        if search_type == 'comic' and smode == 'pullseries':
            if issue == 0:
                #if it's an issue 0, CV doesn't have any data populated yet - so bump it up one to at least get the current results.
                issue = 1
            try:
                searchresults = mb.findComic(name, smode, issue=issue)
                searchline = {'findComic': True, 'name': name, 'mode': smode, 'issue': issue, 'searchtype': 'comic'}
            except TypeError as e:
                logger.error('[%s] Unable to perform required pull-list search for : [name: %s][issue: %s][mode:%s]' % (e, name, issue, smode))
                return
        elif search_type == 'comic' and smode == 'series':
            if name.startswith('4050-'):
                mismatch = "no"
                comicid = re.sub('4050-', '', name)
                logger.info('Attempting to add directly by ComicVineID: ' + str(comicid) + '. I sure hope you know what you are doing.')
                self.addbyid(comicid, calledby=False, nothread=False)
                #threading.Thread(target=importer.addComictoDB, args=[comicid, mismatch, None]).start()
                #raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % comicid)
            try:
                searchresults = mb.findComic(name, smode, issue=None)
                searchline = {'findComic': True, 'name': name, 'mode': smode, 'issue': None, 'searchtype': 'comic'}
            except TypeError as e:
                logger.error('[%s] Unable to perform required search for : [name: %s][mode:%s]' % (e, name, smode))
                return
        elif search_type == 'comic' and smode == 'want':
            try:
                searchresults = mb.findComic(name, smode, issue)
                searchline = {'findComic': True, 'name': name, 'mode': smode, 'issue': issue, 'search_type': 'want'}
            except TypeError as e:
                logger.error('[%s] Unable to perform required one-off pull-list search for : [name: %s][issue: %s][mode: %s]' % (e, name, issue, mode))
                return
        elif search_type == 'story_arc':
            try:
                searchresults = mb.findComic(name, mode=None, issue=None, search_type='story_arc')
                searchline = {'findComic': True, 'name': name, 'mode': None, 'issue': issue, 'search_type': 'story_arc'}
            except TypeError as e:
                logger.error('[%s] Unable to perform required story-arc search for : [arc: %s][mode: %s]' % (e, name, smode))
                return

        try:
            searchresults = sorted(searchresults, key=itemgetter('comicyear', 'issues'), reverse=True)
        except Exception as e:
            searchresults = None
            query_id = None
            logger.error('Unable to retrieve results from ComicVine: %s' % e)
            if mylar.CONFIG.COMICVINE_API is None:
                logger.error('You NEED to set a ComicVine API key prior to adding anything. It\'s Free - Go get one!')
                return
        else:
            query_id = random.randint(1,999999)
            # write it to temporary db here - so we don't have to continually poll CV
            myDB = db.DBConnection()
            for x in searchresults:
                ctrlid = {'query_id': query_id,
                          'comicid': int(x['comicid'])}

                if x['haveit'] != "No":
                    haveit = "Yes"
                else:
                   haveit = "No"
                vals = {'comicname': x['name'],
                        'publisher': x['publisher'],
                        'comicyear': x['comicyear'],
                        'issues': x['issues'],
                        'deck': x['deck'],
                        'url': x['url'],
                        'comicimage': x['comicimage'],
                        'thumbimage': x['comicthumb'],
                        'description': x['description'],
                        'haveit': haveit,
                        'mode': smode,
                        'searchtype': search_type}
                if search_type == 'story_arc':
                    vals['cvarcid'] = x['cvarcid']
                    vals['arclist'] = x['arclist']
                else:
                    vals['volume'] = x['volume']
                    vals['publisherimprint'] = x['imprint']
                    vals['type'] =  x['type']
                myDB.upsert("tmp_searches", vals, ctrlid)

        return serve_template(templatename="searchresults.html", title='Search Results for: "' + name + '"', query_id=query_id, query=name, search_type=search_type)
        # searchresults=searchresults, search_type=search_type, imported=None, ogcname=None, name=name, serinfo=serinfo)
    searchit.exposed = True

    def searchit_old(self, name, issue=None, mode=None, search_type=None, serinfo=None):
        if search_type is None: search_type = 'comic'  # let's default this to comic search only for the time being (will add story arc, characters, etc later)
        else: logger.fdebug(str(search_type) + " mode enabled.")
        #mode dictates type of search:
        # --series     ...  search for comicname displaying all results
        # --pullseries ...  search for comicname displaying a limited # of results based on issue
        # --want       ...  individual comics
        if mode is None: mode = 'series'
        if len(name) == 0:
            raise cherrypy.HTTPRedirect("home")
        if search_type == 'comic' and mode == 'pullseries':
            if issue == 0:
                #if it's an issue 0, CV doesn't have any data populated yet - so bump it up one to at least get the current results.
                issue = 1
            try:
                searchresults = mb.findComic(name, mode, issue=issue)
            except TypeError:
                logger.error('Unable to perform required pull-list search for : [name: ' + name + '][issue: ' + issue + '][mode: ' + mode + ']')
                return
        elif search_type == 'comic' and mode == 'series':
            if name.startswith('4050-'):
                mismatch = "no"
                tmp_comicid = re.sub('4050-', '', name)
                logger.info('Attempting to add directly by ComicVineID: ' + str(tmp_comicid) + '. I sure hope you know what you are doing.')
                self.addbyid(name, calledby=False, nothread=False)
                #threading.Thread(target=importer.addComictoDB, args=[comicid, mismatch, None]).start()
                #raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % comicid)
            try:
                searchresults = mb.findComic(name, mode, issue=None)
            except TypeError:
                logger.error('Unable to perform required search for : [name: ' + name + '][mode: ' + mode + ']')
                return
        elif search_type == 'comic' and mode == 'want':
            try:
                searchresults = mb.findComic(name, mode, issue)
            except TypeError:
                logger.error('Unable to perform required one-off pull-list search for : [name: ' + name + '][issue: ' + issue + '][mode: ' + mode + ']')
                return
        elif search_type == 'story_arc':
            try:
                searchresults = mb.findComic(name, mode=None, issue=None, search_type='story_arc')
            except TypeError:
                logger.error('Unable to perform required story-arc search for : [arc: ' + name + '][mode: ' + mode + ']')
                return

        try:
            searchresults = sorted(searchresults, key=itemgetter('comicyear', 'issues'), reverse=True)
        except Exception as e:
            logger.error('Unable to retrieve results from ComicVine: %s' % e)
            if mylar.CONFIG.COMICVINE_API is None:
                logger.error('You NEED to set a ComicVine API key prior to adding anything. It\'s Free - Go get one!')
                return
        return serve_template(templatename="searchresults.html", title='Search Results for: "' + name + '"', searchresults=searchresults, search_type=search_type, imported=None, ogcname=None, name=name, serinfo=serinfo)
    searchit_old.exposed = True

    def addComic(self, comicid, comicname=None, comicyear=None, comicimage=None, comicissues=None, comicpublisher=None, imported=None, ogcname=None, serinfo=None):
        myDB = db.DBConnection()
        if imported == "confirm":
            # if it's coming from the importer and it's just for confirmation, record the right selection and break.
            # if it's 'confirmed' coming in as the value for imported
            # the ogcname will be the original comicid that is either correct/incorrect (doesn't matter which)
            #confirmedid is the selected series (comicid) with the letter C at the beginning to denote Confirmed.
            # then sql the original comicid which will hit on all the results for the given series.
            # iterate through, and overwrite the existing watchmatch with the new chosen 'C' + comicid value

            confirmedid = "C" + str(comicid)
            confirms = myDB.select("SELECT * FROM importresults WHERE WatchMatch=?", [ogcname])
            if confirms is None:
                logger.Error("There are no results that match...this is an ERROR.")
            else:
                for confirm in confirms:
                    controlValue = {"impID":    confirm['impID']}
                    newValue = {"WatchMatch":   str(confirmedid)}
                    myDB.upsert("importresults", newValue, controlValue)
                self.importResults()
            return
        elif imported == 'futurecheck':
            print('serinfo:' + str(serinfo))
            logger.info('selected comicid of : ' + str(comicid) + ' [ ' + comicname + ' (' + str(comicyear) + ') ]')
            ser = []
            ser.append({"comicname": comicname,
                        "comicyear": comicyear,
                        "comicissues": comicissues,
                        "comicpublisher": comicpublisher,
                        "IssueDate": serinfo[0]['IssueDate'],
                        "IssueNumber": serinfo[0]['IssueNumber']})
            weeklypull.future_check_add(comicid, ser)
        sresults = []
        cresults = []
        mismatch = "no"
        #print ("comicid: " + str(comicid))
        #print ("comicname: " + str(comicname))
        #print ("comicyear: " + str(comicyear))
        #print ("comicissues: " + str(comicissues))
        #print ("comicimage: " + str(comicimage))
        if not mylar.CONFIG.CV_ONLY:
        #here we test for exception matches (ie. comics spanning more than one volume, known mismatches, etc).
            CV_EXcomicid = myDB.selectone("SELECT * from exceptions WHERE ComicID=?", [comicid]).fetchone()
            if CV_EXcomicid is None: # pass #
                gcdinfo=parseit.GCDScraper(comicname, comicyear, comicissues, comicid, quickmatch="yes")
                if gcdinfo == "No Match":
                #when it no matches, the image will always be blank...let's fix it.
                    cvdata = mylar.cv.getComic(comicid, 'comic')
                    comicimage = cvdata['ComicImage']
                    updater.no_searchresults(comicid)
                    nomatch = "true"
                    u_comicname = comicname.encode('utf-8').strip()
                    logger.info("I couldn't find an exact match for " + u_comicname + " (" + str(comicyear) + ") - gathering data for Error-Checking screen (this could take a minute)...")
                    i = 0
                    loopie, cnt = parseit.ComChk(comicname, comicyear, comicpublisher, comicissues, comicid)
                    logger.info("total count : " + str(cnt))
                    while (i < cnt):
                        try:
                            stoopie = loopie['comchkchoice'][i]
                        except (IndexError, TypeError):
                            break
                        cresults.append({
                               'ComicID':   stoopie['ComicID'],
                               'ComicName':   stoopie['ComicName'].decode('utf-8', 'replace'),
                               'ComicYear':   stoopie['ComicYear'],
                               'ComicIssues': stoopie['ComicIssues'],
                               'ComicURL':    stoopie['ComicURL'],
                               'ComicPublisher': stoopie['ComicPublisher'].decode('utf-8', 'replace'),
                               'GCDID': stoopie['GCDID']
                               })
                        i+=1
                    if imported != 'None':
                    #if it's from an import and it has to go through the UEC, return the values
                    #to the calling function and have that return the template
                        return cresults
                    else:
                        return serve_template(templatename="searchfix.html", title="Error Check", comicname=comicname, comicid=comicid, comicyear=comicyear, comicimage=comicimage, comicissues=comicissues, cresults=cresults, imported=None, ogcname=None)
                else:
                    nomatch = "false"
                    logger.info("Quick match success..continuing.")
            else:
                if CV_EXcomicid['variloop'] == '99':
                    logger.info("mismatched name...autocorrecting to correct GID and auto-adding.")
                    mismatch = "yes"
                if CV_EXcomicid['NewComicID'] == 'none':
                    logger.info("multi-volume series detected")
                    testspx = CV_EXcomicid['GComicID'].split('/')
                    for exc in testspx:
                        fakeit = parseit.GCDAdd(testspx)
                        howmany = int(CV_EXcomicid['variloop'])
                        t = 0
                        while (t <= howmany):
                            try:
                                sres = fakeit['serieschoice'][t]
                            except IndexError:
                                break
                            sresults.append({
                                   'ComicID':   sres['ComicID'],
                                   'ComicName':   sres['ComicName'],
                                   'ComicYear':   sres['ComicYear'],
                                   'ComicIssues': sres['ComicIssues'],
                                   'ComicPublisher': sres['ComicPublisher'],
                                   'ComicCover':    sres['ComicCover']
                                   })
                            t+=1
                        #searchfix(-1).html is for misnamed comics and wrong years.
                        #searchfix-2.html is for comics that span multiple volumes.
                        return serve_template(templatename="searchfix-2.html", title="In-Depth Results", sresults=sresults)
        #print ("imported is: " + str(imported))
        threading.Thread(target=importer.addComictoDB, args=[comicid, mismatch, None, imported, ogcname]).start()
        time.sleep(5) #wait 5s so the db can be populated enough to display the page - otherwise will return to home page if not enough info is loaded.
        raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % comicid)
    addComic.exposed = True

    def addbyid(self, comicid, calledby=None, imported=None, ogcname=None, nothread=False, seriesyear=None, query_id=None, com_location=None, booktype=None, markupcoming=None, markall=None, suppress_addall=None):
        mismatch = "no"
        if com_location == 'null':
            com_location = None
        if booktype == 'null':
            booktype = None
        logger.info('com_location: %s' % com_location)

        writeit = False
        if markupcoming:
            autoup = False
            if markupcoming == 'true':
                autoup = True
            if autoup != mylar.CONFIG.AUTOWANT_UPCOMING:
                mylar.CONFIG.AUTOWANT_UPCOMING = autoup
                writeit = True
        if markall:
            autoall = False
            if markall == 'true':
                autoall = True
            if autoall != mylar.CONFIG.AUTOWANT_ALL:
                mylar.CONFIG.AUTOWANT_ALL = autoall
                writeit = True
        if writeit:
            mylar.CONFIG.writeconfig(values={'autowant_all': mylar.CONFIG.AUTOWANT_ALL, 'autowant_upcoming': mylar.CONFIG.AUTOWANT_UPCOMING})

        if query_id is not None:
           myDB = db.DBConnection()
           query_chk = myDB.selectone("SELECT * FROM tmp_searches where query_id=? AND comicid=?", [query_id, comicid]).fetchone()
           if query_chk:
               if query_chk['searchtype'] == 'story_arc':
                   logger.info('query_id storyarc match to : %s' % (query_id))
                   #storyarcid = str(random.randint(1000,9999)) + str(query_chk['issues'])
                   #arc_info = {'StoryArc': query_chk['comicname'],
                   #            'CV_ArcID': query_chk['cvarcid'],
                   #            'Publisher': query_chk['publisher'],
                   #            'TotalIssues': query_chk['issues'],
                   #            #'storyarcyear': query_chk['comicyear'],
                   #            #'arclist': query_chk['arclist'],
                   #            #'description': query_chk['description'],
                   #            'ArcImage': query_chk['comicimage']}
                   #myDB.upsert("storyarcs", arc_info, {'StoryArcID': storyarcid})
                   response = self.addStoryArc(arcid=query_chk['comicid'], cvarcid=query_chk['cvarcid'], storyarcname=query_chk['comicname'],
                                    storyarcyear=query_chk['comicyear'], storyarcpublisher=query_chk['publisher'], storyarcissues=query_chk['issues'],
                                    arclist=query_chk['arclist'], desc=query_chk['description'], image=query_chk['comicimage'])
                   return response
                   #raise cherrypy.HTTPRedirect("detailStoryArc?StoryArcID=%s&StoryArcName=%s&CV_ArcID=%s" % (None, query_chk['comicname'], query_chk['cvarcid']))
                   #return json.dumps({'status': 'success', 'StoryArcName': query_chk['comicname'], 'CV_ArcID': query_chk['cvarcid'], 'StoryArcID': None})
               else:
                   logger.info('query_id match to : %s' % (query_id))
                   ogcname = query_chk['comicname']
                   calledby = True
                   log_the_line = 'Attempting to add %s' % ogcname
                   if com_location is not None:
                       log_the_line += ' [location:%s]' % com_location
                   if booktype is not None:
                       log_the_line += ' [booktype:%s]' % booktype
                   else:
                       booktype = query_chk['type']
                   logger.info(log_the_line)
                   vals = {'ComicName': query_chk['comicname'],
                           'ComicPublisher': query_chk['publisher'],
                           'ComicYear': query_chk['comicyear'],
                           'ComicLocation': com_location,
                           'DetailURL': query_chk['url'],
                           'Description': query_chk['description'],
                           'Type': booktype,
                           'Total': query_chk['issues']}
                   myDB.upsert( "comics", vals, {'ComicID': comicid} )
        else:
            logger.info('Attempting to add directly by ComicVineID: ' + str(comicid))
            if comicid.startswith('4050-'):
                comicid = re.sub('4050-', '', comicid)
                s_start = datetime.datetime.now()
                comicinfo = mylar.cv.getComic(comicid, 'comic')
                logger.info('[CV-QUICK-HIT] took: %s' % (datetime.datetime.now() - s_start))
                logger.info('comicinfo returned: %s' % (comicinfo,))
                if comicinfo and ogcname is None:
                    ogcname = comicinfo['ComicName']
                    seriesyear = comicinfo['ComicYear']
                    #write some values to tmp db so they populate with page already loaded so it's not all None
                    myDB = db.DBConnection()
                    vals = {'ComicName': comicinfo['ComicName'],
                            'ComicPublisher': comicinfo['ComicPublisher'],
                            'ComicYear': comicinfo['ComicYear'],
                            'DetailURL': comicinfo['ComicURL'],
                            'Description': comicinfo['ComicDescription'],
                            'Type': comicinfo['Type'],
                            'Total': comicinfo['ComicIssues']}
                    myDB.upsert( "comics", vals, {'ComicID': comicid} )

        if nothread is False:
            watch = []
            #if not any(ext['comicid'] == ComicID for ext in mylar.REFRESH_LIST):
            if not {"comicid": comicid, "comicname": ogcname} in mylar.ADD_LIST.queue:
                comic_request = {"comicid": comicid, "comicname": ogcname, "seriesyear": seriesyear}
                if suppress_addall:
                    comic_request['suppress_addall'] = suppress_addall
                watch.append(comic_request)

            if len(watch) > 0:
                if all([ogcname != 'None', ogcname is not None]):
                    og_line = '%s [%s]' % (ogcname, comicid)
                else:
                    og_line = '%s' % comicid
                logger.info('[SHIZZLE-WHIZZLE] Now queueing to add %s' % (og_line))
                try:
                    importer.importer_thread(watch)
                except Exception:
                    pass

            #threading.Thread(target=importer.addComictoDB, args=[comicid, mismatch, None, imported, ogcname]).start()
        else:
            return importer.addComictoDB(comicid, mismatch, None, imported, ogcname)

        if calledby is True or calledby == 'True':
           return
        elif calledby == 'web-import':
           raise cherrypy.HTTPRedirect("importResults")
        else:
           raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s&addbyid=1" % comicid)
    addbyid.exposed = True

    def addStoryArc_thread(self, **kwargs):
        threading.Thread(target=self.addStoryArc, kwargs=kwargs).start()
    addStoryArc_thread.exposed = True

    def addStoryArc(self, arcid, arcrefresh=False, cvarcid=None, arclist=None, storyarcname=None, storyarcyear=None, storyarcpublisher=None, storyarcissues=None, desc=None, image=None):
        # used when a choice is selected to 'add story arc' via the searchresults screen (via the story arc search).
        # arclist contains ALL the issueid's in sequence, along with the issue titles.
        # call the function within cv.py to grab all the issueid's and return all the issue data
        module = '[STORY ARC]'
        myDB = db.DBConnection()
        #check if it already exists.
        if cvarcid is None:
            arc_chk = myDB.select('SELECT * FROM storyarcs WHERE StoryArcID=?', [arcid])
        else:
            arc_chk = myDB.select('SELECT * FROM storyarcs WHERE CV_ArcID=?', [cvarcid])
        if arc_chk is None:
            if arcrefresh:
                logger.warn(module + ' Unable to retrieve Story Arc ComicVine ID from the db. Unable to refresh Story Arc at this time. You probably have to delete/readd the story arc this one time for Refreshing to work properly.')
                return
            else:
                logger.fdebug(module + ' No match in db based on ComicVine ID. Making sure and checking against Story Arc Name.')
                arc_chk = myDB.select('SELECT * FROM storyarcs WHERE StoryArc=?', [storyarcname])
                if arc_chk is None:
                    logger.warn(module + ' ' + storyarcname + ' already exists on your Story Arc Watchlist!')
                    raise cherrypy.HTTPRedirect("readlist")
        else:
            if arcrefresh: #cvarcid must be present here as well..
                logger.info(module + '[' + str(arcid) + '] Successfully found Story Arc ComicVine ID [4045-' + str(cvarcid) + '] within db. Preparing to refresh Story Arc.')
                # we need to store the existing arc values that are in the db, so we don't create duplicate entries or mess up items.
                iss_arcids = []
                for issarc in arc_chk:
                    iss_arcids.append({"IssueArcID":  issarc['IssueArcID'],
                                       "IssueID":     issarc['IssueID'],
                                       "Manual":      issarc['Manual']})
                arcinfo = mb.storyarcinfo(cvarcid)
                if len(arcinfo) > 1:
                    arclist = arcinfo['arclist']
                else:
                    logger.warn(module + ' Unable to retrieve issue details at this time. Something is probably wrong.')
                    return
#               else:
#                   logger.warn(module + ' ' + storyarcname + ' already exists on your Story Arc Watchlist.')
#                   raise cherrypy.HTTPRedirect("readlist")

        #check to makes sure storyarcs dir is present in cache in order to save the images...
        if not os.path.isdir(os.path.join(mylar.CONFIG.CACHE_DIR, 'storyarcs')):
            checkdirectory = filechecker.validateAndCreateDirectory(os.path.join(mylar.CONFIG.CACHE_DIR, 'storyarcs'), True)
            if not checkdirectory:
                logger.warn('Error trying to validate/create cache storyarc directory. Aborting this process at this time.')
                return


        coverfile = os.path.join(mylar.CONFIG.CACHE_DIR,  'storyarcs', str(cvarcid) + "-banner.jpg")

        if mylar.CONFIG.CVAPI_RATE is None or mylar.CONFIG.CVAPI_RATE < 2:
            time.sleep(2)
        else:
            time.sleep(mylar.CONFIG.CVAPI_RATE)

        logger.info('Attempting to retrieve the comic image for series')
        if arcrefresh:
            imageurl = arcinfo['comicimage']
        else:
            imageurl = image

        logger.info('imageurl: %s' % imageurl)
        if imageurl and imageurl.startswith('http'):
            try:
                r = requests.get(imageurl, params=None, stream=True, verify=mylar.CONFIG.CV_VERIFY, headers=mylar.CV_HEADERS)
            except Exception as e:
                logger.warn('Unable to download image from CV URL link - possibly no arc picture is present: %s' % imageurl)
            else:
                logger.fdebug('comic image retrieval status code: %s' % r.status_code)

                if str(r.status_code) != '200':
                    logger.warn('Unable to download image from CV URL link: %s [Status Code returned: %s]' % (imageurl, r.status_code))
                else:
                    if r.headers.get('Content-Encoding') == 'gzip':
                        import gzip
                        from io import BytesIO
                        buf = BytesIO(r.content)
                        f = gzip.GzipFile(fileobj=buf)

                    with open(coverfile, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024):
                            if chunk: # filter out keep-alive new chunks
                                f.write(chunk)
                                f.flush()

        arc_results = mylar.cv.getComic(comicid=None, rtype='issue', arcid=arcid, arclist=arclist)
        logger.fdebug('%s Arcresults: %s' % (module, arc_results))
        logger.fdebug('%s Arclist: %s' % (module, arclist))
        if len(arc_results) > 0:
            issuedata = []
            if storyarcissues is None:
                storyarcissues = len(arc_results['issuechoice'])
            if arcid is None:
                storyarcid = str(random.randint(1000,9999)) + str(storyarcissues)
            else:
                storyarcid = arcid
            n = 0
            cidlist = ''
            iscnt = int(storyarcissues)
            while (n <= iscnt):
                try:
                    arcval = arc_results['issuechoice'][n]
                except IndexError:
                    break
                comicname = arcval['ComicName']
                st_d = mylar.filechecker.FileChecker(watchcomic=comicname)
                st_dyninfo = st_d.dynamic_replace(comicname)
                dynamic_name = re.sub('[\|\s]','', st_dyninfo['mod_seriesname'].lower()).strip()

                issname = arcval['Issue_Name']
                issid = str(arcval['IssueID'])
                comicid = str(arcval['ComicID'])
                #--- this needs to get changed so comicid within a comicid doesn't exist (ie. 3092 is IN 33092)
                cid_count = cidlist.count(comicid) +1
                a_end = 0
                i = 0
                while i < cid_count:
                    a = cidlist.find(comicid, a_end)
                    a_end = cidlist.find('|',a)
                    if a_end == -1: a_end = len(cidlist)
                    a_length = cidlist[a:a_end-1]

                    if a == -1 and len(a_length) != len(comicid):
                        if n == 0:
                            cidlist += str(comicid)
                        else:
                            cidlist += '|' + str(comicid)
                        break
                    i+=1

                #don't recreate the st_issueid if it's a refresh and the issueid already exists (will create duplicates otherwise)
                st_issueid = None
                manual_mod = None
                if arcrefresh:
                    for aid in iss_arcids:
                        if aid['IssueID'] == issid:
                            st_issueid = aid['IssueArcID']
                            manual_mod = aid['Manual']
                            break

                if st_issueid is None:
                    st_issueid = str(storyarcid) + "_" + str(random.randint(1000,9999))
                issnum = arcval['Issue_Number']
                issdate = str(arcval['Issue_Date'])
                digitaldate = str(arcval['Digital_Date'])
                storedate = str(arcval['Store_Date'])

                int_issnum = helpers.issue_number_parser(issnum).asInt

                #verify the reading order if present.
                findorder = arclist.find(issid)
                if findorder != -1:
                    ros = arclist.find('|',findorder+1)
                    if ros != -1:
                        roslen = arclist[findorder:ros]
                    else:
                        #last entry doesn't have a trailling '|'
                        roslen = arclist[findorder:]
                    rosre = re.sub(issid,'', roslen)
                    readingorder = int(re.sub('[\,\|]','', rosre).strip())
                else:
                    readingorder = 0
                logger.fdebug('[%s] issueid: %s - findorder#: %s' % (readingorder, issid, findorder))

                issuedata.append({"ComicID":            comicid,
                                  "IssueID":            issid,
                                  "StoryArcID":         storyarcid,
                                  "IssueArcID":         st_issueid,
                                  "ComicName":          comicname,
                                  "DynamicName":        dynamic_name,
                                  "IssueName":          issname,
                                  "Issue_Number":       issnum,
                                  "IssueDate":          issdate,
                                  "ReleaseDate":        storedate,
                                  "DigitalDate":        digitaldate,
                                  "ReadingOrder":       readingorder, #n +1,
                                  "Int_IssueNumber":    int_issnum,
                                  "Manual":             manual_mod})
                n+=1
            comicid_results = mylar.cv.getComic(comicid=None, rtype='comicyears', comicidlist=cidlist)
            logger.fdebug('%s Initiating issue updating - just the info' % module)

            for AD in issuedata:
                seriesYear = 'None'
                issuePublisher = 'None'
                seriesVolume = 'None'

                if AD['IssueName'] is None:
                    IssueName = 'None'
                else:
                    IssueName = AD['IssueName'][:70]

                for cid in comicid_results:
                    if cid['ComicID'] == AD['ComicID']:
                        seriesYear = cid['SeriesYear']
                        issuePublisher = cid['Publisher']
                        seriesVolume = cid['Volume']
                        bookType = cid['Type']
                        seriesAliases = cid['Aliases']
                        if storyarcpublisher is None:
                            #assume that the arc is the same
                            storyarcpublisher = issuePublisher
                        break

                newCtrl = {"IssueID":           AD['IssueID'],
                           "StoryArcID":        AD['StoryArcID']}
                newVals = {"ComicID":           AD['ComicID'],
                           "IssueArcID":        AD['IssueArcID'],
                           "StoryArc":          storyarcname,
                           "ComicName":         AD['ComicName'],
                           "Volume":            seriesVolume,
                           "DynamicComicName":  AD['DynamicName'],
                           "IssueName":         IssueName,
                           "IssueNumber":       AD['Issue_Number'],
                           "Publisher":         storyarcpublisher,
                           "TotalIssues":       storyarcissues,
                           "ReadingOrder":      AD['ReadingOrder'],
                           "IssueDate":         AD['IssueDate'],
                           "ReleaseDate":       AD['ReleaseDate'],
                           "DigitalDate":       AD['DigitalDate'],
                           "SeriesYear":        seriesYear,
                           "IssuePublisher":    issuePublisher,
                           "CV_ArcID":          arcid,
                           "Int_IssueNumber":   AD['Int_IssueNumber'],
                           "Type":              bookType,
                           "Aliases":           seriesAliases,
                           "Manual":            AD['Manual']}

                myDB.upsert("storyarcs", newVals, newCtrl)

        #run the Search for Watchlist matches now.
        logger.fdebug(module + ' Now searching your watchlist for matches belonging to this story arc.')
        self.ArcWatchlist(storyarcid)
        if arcrefresh:
            logger.info('%s Successfully Refreshed %s' % (module, storyarcname))
            return
        else:
            logger.info('%s Successfully Added %s' % (module, storyarcname))
            return json.dumps({'status': 'success', 'StoryArcName': storyarcname, 'StoryArcID': storyarcid})
            #raise cherrypy.HTTPRedirect("detailStoryArc?StoryArcID=%s&StoryArcName=%s" % (storyarcid, storyarcname))
    addStoryArc.exposed = True

    def wanted_Export(self,mode):
        myDB = db.DBConnection()
        wantlist = myDB.select("select b.ComicName, b.ComicYear, a.Issue_Number, a.IssueDate, a.ComicID, a.IssueID from issues a inner join comics b on a.ComicID=b.ComicID where a.status=? and b.ComicName is not NULL", [mode])
        if wantlist is None:
            logger.info("There aren't any issues marked as " + mode + ". Aborting Export.")
            return

        #write out a wanted_list.csv
        logger.info("gathered data - writing to csv...")
        wanted_file = os.path.join(mylar.DATA_DIR, str(mode) + "_list.csv")
        if os.path.exists(wanted_file):
            try:
                os.remove(wanted_file)
            except (OSError, IOError):
                wanted_file_new = os.path.join(mylar.DATA_DIR, str(mode) + '_list-1.csv')
                logger.warn('%s already exists. Writing to: %s' % (wanted_file, wanted_file_new))
                wanted_file = wanted_file_new

        wcount=0
        with open(wanted_file, 'w+') as f:
            try:
                fieldnames = ['SeriesName','SeriesYear','IssueNumber','IssueDate','ComicID','IssueID']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for want in wantlist:
                    writer.writerow({'SeriesName':   want['ComicName'],
                                     'SeriesYear':   want['ComicYear'],
                                     'IssueNumber':  want['Issue_Number'],
                                     'IssueDate':    want['IssueDate'],
                                     'ComicID':      want['ComicID'],
                                     'IssueID':      want['IssueID']})
                    wcount += 1
            except IOError as Argument:
                logger.info("Error writing value to {}.  {}".format(wanted_file, Argument))
            except Exception as Argument:
                logger.info("Unknown error: {}".format(Argument))
        if wcount > 0:
            logger.info('Successfully wrote to csv file %s entries from your %s list.' % (wcount, mode))
        else:
            logger.info('Nothing written to csv file for your %s list.' % mode)

        raise cherrypy.HTTPRedirect("home")
    wanted_Export.exposed = True

    def from_Exceptions(self, comicid, gcdid, comicname=None, comicyear=None, comicissues=None, comicpublisher=None, imported=None, ogcname=None):
        import unicodedata
        mismatch = "yes"
        #write it to the custom_exceptions.csv and reload it so that importer will pick it up and do it's thing :)
        #custom_exceptions in this format...
        #99, (comicid), (gcdid), none
        logger.info("saving new information into custom_exceptions.csv...")
        except_info = "none #" + str(comicname) + "-(" + str(comicyear) + ")\n"
        except_file = os.path.join(mylar.DATA_DIR, "custom_exceptions.csv")
        if not os.path.exists(except_file):
            try:
                 csvfile = open(str(except_file), 'rb')
                 csvfile.close()
            except (OSError, IOError):
                logger.error("Could not locate " + str(except_file) + " file. Make sure it's in datadir: " + mylar.DATA_DIR + " with proper permissions.")
                return
        exceptln = "99," + str(comicid) + "," + str(gcdid) + "," + str(except_info)
        exceptline = exceptln.decode('utf-8', 'ignore')

        with open(str(except_file), 'a') as f:
           #f.write('%s,%s,%s,%s\n' % ("99", comicid, gcdid, except_info)
            f.write('%s\n' % (exceptline.encode('ascii', 'replace').strip()))
        logger.info("re-loading csv file so it's all nice and current.")
        mylar.csv_load()
        if imported:
            threading.Thread(target=importer.addComictoDB, args=[comicid, mismatch, None, imported, ogcname]).start()
        else:
            threading.Thread(target=importer.addComictoDB, args=[comicid, mismatch]).start()
        raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % comicid)
    from_Exceptions.exposed = True

    def GCDaddComic(self, comicid, comicname=None, comicyear=None, comicissues=None, comiccover=None, comicpublisher=None):
        #since we already know most of the info, let's add it to the db so we can reference it later.
        myDB = db.DBConnection()
        gcomicid = "G" + str(comicid)
        comicyear_len = comicyear.find(' ', 2)
        comyear = comicyear[comicyear_len +1:comicyear_len +5]
        if comyear.isdigit():
            logger.fdebug("Series year set to : " + str(comyear))
        else:
            logger.fdebug("Invalid Series year detected - trying to adjust from " + str(comyear))
            #comicyear_len above will trap wrong year if it's 10 October 2010 - etc ( 2000 AD)...
            find_comicyear = comicyear.split()
            for i in find_comicyear:
                if len(i) == 4:
                    logger.fdebug("Series year detected as : " + str(i))
                    comyear = str(i)
                    continue

            logger.fdebug("Series year set to: " + str(comyear))

        controlValueDict = {'ComicID': gcomicid}
        newValueDict = {'ComicName': comicname,
                        'ComicYear': comyear,
                        'ComicPublished': comicyear,
                        'ComicPublisher': comicpublisher,
                        'ComicImage': comiccover,
                        'Total': comicissues}
        myDB.upsert("comics", newValueDict, controlValueDict)
        threading.Thread(target=importer.GCDimport, args=[gcomicid]).start()
        raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % gcomicid)
    GCDaddComic.exposed = True

    def post_process(self, nzb_name, nzb_folder, failed=False, apc_version=None, comicrn_version=None):
        pp_fail = False
        if all([nzb_name != 'Manual Run', nzb_name != 'Manual+Run']):
            if comicrn_version is None and apc_version is None:
                logger.warn('ComicRN should be v' + str(mylar.STATIC_COMICRN_VERSION) + ' and autoProcessComics.py should be v' + str(mylar.STATIC_APC_VERSION) + ', but they are not and are out of date. Post-Processing may or may not work.')
            elif comicrn_version is None or comicrn_version != mylar.STATIC_COMICRN_VERSION:
                if comicrn_version == 'None':
                    comicrn_version = "0"
                logger.warn('Your ComicRN.py script should be v' + str(mylar.STATIC_COMICRN_VERSION) + ', but is v' + str(comicrn_version) + ' and is out of date. Things may still work - but you are taking your chances.')
            elif apc_version is None or apc_version != mylar.STATIC_APC_VERSION:
                if apc_version == 'None':
                    apc_version = "0"
                if mylar.CONFIG.AUTHENTICATION == 2:
                    logger.warn('YOU NEED TO UPDATE YOUR autoProcessComics.py file in order to use this option with the Forms Login enabled due to security.')
                    yield json.dumps({'status': 'fail', 'message': 'YOU NEED TO UPDATE YOUR autoProcessComics.py file in order to use this option with Forms Login enabled.'})
                    pp_fail = True
                logger.warn('Your autoProcessComics.py script should be v' + str(mylar.STATIC_APC_VERSION) + ', but is v' + str(apc_version) + ' and is out of date. Odds are something is gonna fail - you should update it.')
            else:
                logger.info('ComicRN.py version: ' + str(comicrn_version) + ' -- autoProcessComics.py version: ' + str(apc_version))

        else:
             if not os.path.exists(nzb_folder):
                 yield json.dumps({'status': 'fail', 'message': '%s does not exist - please verify!' % (nzb_folder)})
                 pp_fail = True
             else:
                 if nzb_folder.lower() == mylar.CONFIG.DESTINATION_DIR.lower():
                     try:
                         yield json.dumps({'status': 'fail', 'message': '%s is identical to your Comic Location path. You CANNOT post-process from this location.' % (nzb_folder)})
                         pp_fail = True
                     except Exception as e:
                         logger.warn('error: %s' % e)
                         pp_fail = True
                 else:
                     if mylar.CONFIG.MANUAL_PP_FOLDER != nzb_folder:
                         mylar.CONFIG.MANUAL_PP_FOLDER = nzb_folder
                         mylar.CONFIG.configure(update=True)
                         # Write the config
                         logger.info('Now updating config...')
                         mylar.CONFIG.writeconfig(values={'manual_pp_folder': mylar.CONFIG.MANUAL_PP_FOLDER})
                     yield json.dumps({'status': 'success', 'message': 'Successfully submitted %s for manual post-processing...' % (nzb_folder)})

        if pp_fail is True:
            return

        import queue
        logger.info('Starting postprocessing for : ' + nzb_name)
        if failed == '0':
            failed = False
        elif failed == '1':
            failed = True

        queue = queue.Queue()
        retry_outside = False
        if not failed:
            PostProcess = PostProcessor.PostProcessor(nzb_name, nzb_folder, queue=queue)
            if nzb_name == 'Manual Run' or nzb_name == 'Manual+Run':
                threading.Thread(target=PostProcess.Process).start()
            else:
                thread_ = threading.Thread(target=PostProcess.Process, name="Post-Processing")
                thread_.start()
                thread_.join()
                chk = queue.get()
                while True:
                    if chk[0]['mode'] == 'fail':
                        yield chk[0]['self.log']
                        logger.info('Initiating Failed Download handling')
                        if chk[0]['annchk'] == 'no': mode = 'want'
                        else: mode = 'want_ann'
                        failed = True
                        break
                    elif chk[0]['mode'] == 'stop':
                        yield chk[0]['self.log']
                        break
                    elif chk[0]['mode'] == 'outside':
                        yield chk[0]['self.log']
                        retry_outside = True
                        break
                    else:
                        logger.error('mode is unsupported: ' + chk[0]['mode'])
                        yield chk[0]['self.log']
                        break

        if failed:
            if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING is True:
                #drop the if-else continuation so we can drop down to this from the above if statement.
                logger.info('Initiating Failed Download handling for this download.')
                FailProcess = Failed.FailedProcessor(nzb_name=nzb_name, nzb_folder=nzb_folder, queue=queue)
                thread_ = threading.Thread(target=FailProcess.Process, name="FAILED Post-Processing")
                thread_.start()
                thread_.join()
                failchk = queue.get()
                if failchk[0]['mode'] == 'retry':
                    yield failchk[0]['self.log']
                    logger.info('Attempting to return to search module with ' + str(failchk[0]['issueid']))
                    if failchk[0]['annchk'] == 'no': mode = 'want'
                    else: mode = 'want_ann'
                    self.queueit(mode=mode, ComicName=failchk[0]['comicname'], ComicIssue=failchk[0]['issuenumber'], ComicID=failchk[0]['comicid'], IssueID=failchk[0]['issueid'], manualsearch=True)
                elif failchk[0]['mode'] == 'stop':
                    yield failchk[0]['self.log']
                else:
                    logger.error('mode is unsupported: ' + failchk[0]['mode'])
                    yield failchk[0]['self.log']
            else:
                logger.warn('Failed Download Handling is not enabled. Leaving Failed Download as-is.')

        if retry_outside:
            PostProcess = PostProcessor.PostProcessor('Manual Run', nzb_folder, queue=queue)
            thread_ = threading.Thread(target=PostProcess.Process, name="Post-Processing")
            thread_.start()
            thread_.join()
            chk = queue.get()
            while True:
                if chk[0]['mode'] == 'fail':
                    yield chk[0]['self.log']
                    logger.info('Initiating Failed Download handling')
                    if chk[0]['annchk'] == 'no': mode = 'want'
                    else: mode = 'want_ann'
                    failed = True
                    break
                elif chk[0]['mode'] == 'stop':
                    yield chk[0]['self.log']
                    break
                else:
                    logger.error('mode is unsupported: ' + chk[0]['mode'])
                    yield chk[0]['self.log']
                    break
        return
    post_process.exposed = True

    def pauseSeries(self, ComicID):
        logger.info("Pausing comic: " + ComicID)
        myDB = db.DBConnection()
        controlValueDict = {'ComicID': ComicID}
        newValueDict = {'Status': 'Paused'}
        myDB.upsert("comics", newValueDict, controlValueDict)
        raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % ComicID)
    pauseSeries.exposed = True

    def resumeSeries(self, ComicID):
        logger.info("Resuming comic: " + ComicID)
        myDB = db.DBConnection()
        controlValueDict = {'ComicID': ComicID}
        newValueDict = {'Status': 'Active'}
        myDB.upsert("comics", newValueDict, controlValueDict)
        raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % ComicID)
    resumeSeries.exposed = True

    def deleteSeries(self, ComicID, delete_dir=None):
        myDB = db.DBConnection()
        comic = myDB.selectone('SELECT * from comics WHERE ComicID=?', [ComicID]).fetchone()
        try:
            if comic['ComicName'] is None:
                ComicName = 'None'
            else:
                ComicName = comic['ComicName']
        except Exception as e:
            logger.warn('Unable to reference ID in database - was ComicID: %s already deleted? Error returned: %s' % (ComicID, e))
        else:
            seriesdir = comic['ComicLocation']
            seriesyear = comic['ComicYear']
            seriesvol = comic['ComicVersion']
            logger.info("Deleting all traces of Comic: " + ComicName)
            myDB.action('DELETE from comics WHERE ComicID=?', [ComicID])
            myDB.action('DELETE from issues WHERE ComicID=?', [ComicID])

            if mylar.CONFIG.ANNUALS_ON:
                myDB.action('DELETE from annuals WHERE ComicID=?', [ComicID])
            myDB.action('DELETE from upcoming WHERE ComicID=?', [ComicID])
            myDB.action('DELETE from readlist WHERE ComicID=?', [ComicID])
            myDB.action("UPDATE weekly SET Status='Skipped' WHERE ComicID=? AND Status='Wanted'", [ComicID])
            if delete_dir: #mylar.CONFIG.DELETE_REMOVE_DIR:
                logger.fdebug('Remove directory on series removal enabled.')
                if seriesdir is not None:
                    if os.path.exists(seriesdir):
                        logger.fdebug('Attempting to remove the directory and contents of : ' + seriesdir)
                        try:
                            shutil.rmtree(seriesdir)
                        except:
                            logger.warn('Unable to remove directory after removing series from Mylar.')
                        else:
                            logger.info('Successfully removed directory: %s' % (seriesdir))
                    else:
                        logger.warn('Unable to remove directory as it does not exist in : ' + seriesdir)
                else:
                    logger.warn('Unable to remove directory as it does not exist.')
            if seriesvol is None:
                dspline = '%s (%s)' % (ComicName, seriesyear)
            else:
                dspline = '%s %s (%s)' % (ComicName, seriesvol, seriesyear)
            logger.info('Successful deletion of %s from your watchlist' % (dspline))
            helpers.ComicSort(sequence='update')
        raise cherrypy.HTTPRedirect("home")
    deleteSeries.exposed = True

    def wipenzblog(self, ComicID=None, IssueID=None):
        myDB = db.DBConnection()
        if ComicID is None:
            logger.fdebug("Wiping NZBLOG in it's entirety. You should NOT be downloading while doing this or else you'll lose the log for the download.")
            myDB.action('DROP table nzblog')
            logger.fdebug("Deleted nzblog table.")
            myDB.action('CREATE TABLE IF NOT EXISTS nzblog (IssueID TEXT, NZBName TEXT, SARC TEXT, PROVIDER TEXT, ID TEXT, AltNZBName TEXT, OneOff TEXT)')
            logger.fdebug("Re-created nzblog table.")
            raise cherrypy.HTTPRedirect("history")
        if IssueID:
            logger.fdebug('Removing all download history for the given IssueID. This should allow post-processing to finish for the given IssueID.')
            myDB.action('DELETE FROM nzblog WHERE IssueID=?', [IssueID])
            logger.fdebug('Successfully removed all entries in the download log for IssueID: ' + str(IssueID))
            raise cherrypy.HTTPRedirect("history")
    wipenzblog.exposed = True

    def refreshSeries(self, ComicID):
        watch = []
        myDB = db.DBConnection()
        chkdb = myDB.selectone("SELECT ComicName, ComicYear FROM comics WHERE ComicID=?", [ComicID]).fetchone()
        #if not any(ext['comicid'] == ComicID for ext in mylar.REFRESH_LIST):
        if not {"comicid": ComicID, "comicname": chkdb['ComicName']} in mylar.REFRESH_QUEUE.queue:
            watch.append({"comicid": ComicID, "comicname": chkdb['ComicName'], "seriesyear": chkdb['ComicYear']})

        if len(watch) > 0:
            logger.info('[SHIZZLE-WHIZZLE] Now queueing to refresh %s (%s)' % (chkdb['ComicName'], chkdb['ComicYear']))
            try:
                importer.refresh_thread(watch)
            except Exception:
                pass

        return json.dumps({'status': 'success'})
    refreshSeries.exposed = True

    def description_edit(self, id, value):
        comicid = id[1:]
        myDB = db.DBConnection()
        serieschk = myDB.selectone('SELECT * from comics WHERE ComicID=?', [comicid]).fetchone()
        if serieschk is None:
            logger.error('Cannot edit this for some reason - something is wrong.')
            return
        cv_description = serieschk['Description']
        if any([cv_description == value, serieschk['DescriptionEdit'] == value]) and len(value) > 0:
            # only update it if it's different than the original value.
            return value
        if len(value) == 0:
            logger.info('Edit set to None. Refresh the series to get the original description')
            value = None
        comicname = serieschk['ComicName']
        newVal = {"DescriptionEdit": value}
        ctrlVal = {"ComicID": comicid}
        myDB.upsert("comics", newVal, ctrlVal)
        logger.info('Updated Description for %s [%s]' % (comicname, comicid))
        return value

    description_edit.exposed = True

    def issue_edit(self, id, value):
        #logger.fdebug('id: ' + str(id))
        logger.fdebug('value: ' + str(value))
        first_id = id.find('.')
        comicid = id[:first_id]
        logger.fdebug('comicid:' + str(comicid))
        second_id = id.find('.', first_id+1)
        issueid = id[first_id+1:second_id]
        logger.fdebug('issueid:' + str(issueid))
        issue_type = id[second_id+1:]
        logger.fdebug('issue_type: %s' % issue_type)
        myDB = db.DBConnection()
        comicchk = myDB.selectone('SELECT ComicYear FROM comics WHERE ComicID=?', [comicid]).fetchone()
        issuechk = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [issueid]).fetchone()
        if issuechk is None:
            logger.error('Cannot edit this for some reason - something is wrong.')
            return
        if issue_type == 'store':
            oldissuedate = issuechk['ReleaseDate']
            issue_field = 'ReleaseDate'
        else:
            oldissuedate = issuechk['IssueDate']
            issue_field = 'IssueDate'
        seriesyear = comicchk['ComicYear']
        issuenumber = issuechk['Issue_Number']

        #check if the new date is in the correct format of yyyy-mm-dd
        if value == '0000-00-00':
            logger.fdebug('Reverting issue date to 0000-00-00 to allow for possible CV update.')
        else:
            try:
                valid_date = time.strptime(value, '%Y-%m-%d')
            except ValueError:
                logger.error('invalid date provided. Rejecting edit.')
                return oldissuedate
            else:
                #if the new issue year is less than the series year - reject it.
                if value[:4] < seriesyear:
                    logger.error('Series year of ' + str(seriesyear) + ' is less than new issue date of ' + str(value[:4]))
                    return oldissuedate

        newVal = {issue_field: value,
                  "IssueDate_Edit": '%s.%s' % (oldissuedate, issue_type[0])}  #store = s, cover = c
        ctrlVal = {"IssueID": issueid}
        myDB.upsert("issues", newVal, ctrlVal)
        logger.info('Updated %s Issue Date for issue #%s' % (issue_type, issuenumber))
        return value

    issue_edit.exposed=True

    def force_rss(self):
        logger.info('Attempting to run RSS Check Forcibly')
        forcethis = mylar.rsscheckit.tehMain()
        threading.Thread(target=forcethis.run, args=[True]).start()
    force_rss.exposed = True

    def markseries(self, action=None, **args):
        if action is None:
            action = 'Add'

        serieslist = []
        for k,v in list(args.items()):
            if k == 'serieslist[]':
                serieslist = v
                if type(serieslist) != list:
                    serieslist = [serieslist]
            elif k == 'query_id':
                query_id = v
            elif k == 'serieslist':
                serieslist.append(v)

        myDB = db.DBConnection()
        tmp_chk = myDB.select('SELECT * FROM tmp_searches where query_id = ?', [query_id])
        the_list = {}
        for tc in tmp_chk:
            the_list[str(tc['comicid'])] = {'comicname': tc['comicname'],
                                            'seriesyear': tc['comicyear']}
        watch = []
        logger.info('the_list: %s' % (the_list,))
        logger.info('serieslist: %s' % (serieslist,))
        for thekey in serieslist:
            logger.info('thekey: %s' % thekey)
            if (thekey in the_list) and not {"comicid": thekey, "comicname": the_list[thekey]['comicname']} in mylar.ADD_LIST.queue:
            #if not {"comicid": tt['comicid'], "comicname": tt['comicname']} in mylar.ADD_LIST.queue:
                watch.append({"comicid": thekey, "comicname": the_list[thekey]['comicname'], "seriesyear": the_list[thekey]['seriesyear']})
                logger.info('[SHIZZLE-WHIZZLE] Now queueing to add [%s] %s (%s)' % (thekey, the_list[thekey]['comicname'], the_list[thekey]['seriesyear']))

        if len(watch) > 0:
            try:
                importer.importer_thread(watch)
            except Exception:
                pass
            else:
                return json.dumps({'status': 'success', 'message': 'Successfully queued %s series to add to your watchlist' % len(watch)})
        else:
                return json.dumps({'status': 'failure', 'message': 'No series were able to be queued - please check the logs'})

    markseries.exposed = True

    def markannuals(self, ann_action=None, **args):
        self.markissues(ann_action, **args)
    markannuals.exposed = True

    def markissues(self, action=None, **args):
        myDB = db.DBConnection()
        issuesToAdd = []
        issuestoArchive = []
        tier1_cnt = 0
        tier2_cnt = 0
        if action == 'WantedNew':
            newaction = 'Wanted'
        else:
            newaction = action

        issuelist = []

        comicid = None
        for k,v in list(args.items()):
            if k == 'issueids[]':
                issuelist = v
                if type(issuelist) != list:
                    issuelist = [issuelist]
            if k == 'comicid':
                comicid = v
            if k == 'comicname':
                comicname = v
            if k == 'comicyear':
                comicyear = v

        if len(issuelist) > 0:
            args = issuelist

        for IssueID in args:
            if any([IssueID is None, 'issue_table' in IssueID, 'history_table' in IssueID, 'manage_issues' in IssueID, 'issue_table_length' in IssueID, 'issues' in IssueID, 'annuals' in IssueID, 'annual_table_length' in IssueID]):
                continue
            else:
                mi = myDB.selectone("SELECT a.ComicYear, b.* FROM issues b LEFT JOIN comics a ON a.ComicID=b.ComicID WHERE b.IssueID=?", [IssueID]).fetchone()
                arcs = False
                annchk = 'no'
                seriesyear = None
                if mi is None:
                    if mylar.CONFIG.ANNUALS_ON:
                        mi = myDB.selectone("SELECT a.ComicYear, b.* FROM annuals b LEFT JOIN comics a ON a.ComicID=b.ComicID WHERE b.IssueID=? AND NOT b.Deleted", [IssueID]).fetchone()
                        if mi is not None:
                            comicname = mi['ReleaseComicName']
                            issuenumber = mi['Issue_Number']
                            annchk = 'yes'
                            comicid = mi['ComicID']
                            seriesyear = mi['ComicYear']
                        else:
                            mi = myDB.selectone("SELECT * FROM storyarcs WHERE IssueArcID=?", [IssueID]).fetchone()
                            if mi is not None:
                                arcs = True
                                comicname = mi['ComicName']
                                issuenumber = mi['IssueNumber']
                                comicid = mi['ComicID']
                            else:
                                logger.warn('unable to reference issueid: %s' % IssueID)
                                continue
                else:
                    comicname = mi['ComicName']
                    issuenumber = mi['Issue_Number']
                    comicid = mi['ComicID']
                    seriesyear = mi['ComicYear']

                if action == 'OppositeTier':
                    try:
                        if mi['DateAdded'] <= mylar.SEARCH_TIER_DATE:
                            date_added = helpers.today() #tier = "2nd"
                            tier1_cnt +=1
                        else:
                            dt = datetime.datetime.strptime(mylar.SEARCH_TIER_DATE, '%Y-%m-%d')
                            dt-=datetime.timedelta(days=2)
                            new_tier_date = datetime.datetime.strftime(dt, '%Y-%m-%d')
                            date_added = new_tier_date #tier = "1st [%s]" % mi['DateAdded']
                            tier2_cnt +=1
                    except:
                        date_added = mylar.SEARCH_TIER_DATE #"1st [%s]" % mi['DateAdded']
                        tier2_cnt +=1

                    newValueDict = {'DateAdded': date_added}

                elif action == 'Downloaded':
                    if mi['Status'] == "Skipped" or mi['Status'] == "Wanted":
                        logger.fdebug("Cannot change status to %s as comic is not Snatched or Downloaded" % (newaction))
                        continue
                elif action == 'Archived':
                    logger.fdebug("Marking %s %s as %s" % (comicname, issuenumber, newaction))
                    #updater.forceRescan(mi['ComicID'])
                    issuestoArchive.append(IssueID)
                elif action == 'Wanted' or action == 'Retry':
                    if mi['Status'] == 'Wanted':
                        logger.fdebug('Issue already set to Wanted status - no need to change it again.')
                        continue
                    if action == 'Retry': newaction = 'Wanted'
                    logger.fdebug("Marking %s %s as %s" % (comicname, issuenumber, newaction))
                    issuesToAdd.append(IssueID)
                elif action == 'Skipped':
                    logger.fdebug("Marking " + str(IssueID) + " as Skipped")
                elif action == 'Clear':
                    myDB.action("DELETE FROM snatched WHERE IssueID=?", [IssueID])
                elif action == 'Failed' and mylar.CONFIG.FAILED_DOWNLOAD_HANDLING:
                    logger.fdebug('Marking [' + comicname + '] : ' + str(IssueID) + ' as Failed. Sending to failed download handler.')
                    failedcomicid = mi['ComicID']
                    failedissueid = IssueID
                    break
                if arcs is False:
                    controlValueDict = {"IssueID": IssueID}
                else:
                    controlValueDict = {"IssueArcID": IssueID}

                if action != 'OppositeTier':
                    newValueDict = {"Status": newaction}

                if annchk == 'yes':
                    myDB.upsert("annuals", newValueDict, controlValueDict)
                elif arcs is True:
                    myDB.upsert("storyarcs", newValueDict, controlValueDict)
                else:
                    myDB.upsert("issues", newValueDict, controlValueDict)

        if action == 'OppositeTier':
            tierline = 'Now changing '
            if tier2_cnt > 0:
                tierline += '%s Tier1 items to Tier 2' % tier2_cnt
            if tier1_cnt > 0:
                if tier2_cnt > 0:
                    tierline += ' and '
                tierline += '%s Tier2 items to Tier 1' % tier1_cnt
            logger.info('[TIER-REARRANGER] %s' % tierline)
        if action == 'Failed' and mylar.CONFIG.FAILED_DOWNLOAD_HANDLING:
            self.failed_handling(failedcomicid, failedissueid)
        elif len(issuestoArchive) > 0:
            updater.forceRescan(mi['ComicID'])
        elif len(issuesToAdd) > 0:
            logger.fdebug("Marking issues: %s as Wanted" % (issuesToAdd))
            threading.Thread(target=search.searchIssueIDList, args=[issuesToAdd]).start()
        else:
            updater.forceRescan(mi['ComicID'])
        mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': comicname, 'seriesyear': seriesyear, 'comicid': comicid, 'tables': 'both', 'message': 'Successfully changed status of %s issues to %s' % (len(issuelist), action)}
        return json.dumps({'status': 'success'})
    markissues.exposed = True

    def markentries(self, action=None, **args):
        myDB = db.DBConnection()
        cnt = 0
        for ID in args:
            if any([ID is None, 'manage_failed_length' in ID]):
                continue
            else:
                if '##' in ID:
                    f = ID.split('##')
                    myDB.action("DELETE FROM Failed WHERE IssueID=? AND Provider=? AND NZBName=? AND DateFailed=?", [f[0],f[1],f[2],f[3]])
                else:
                    myDB.action("DELETE FROM Failed WHERE ID=?", [ID])
                cnt+=1
        logger.info('[DB FAILED CLEANSING] Cleared ' + str(cnt) + ' entries from the Failed DB so they will now be downloaded if available/working.')
    markentries.exposed = True

    def retryit(self, **kwargs):
        threading.Thread(target=self.retryissue, kwargs=kwargs).start()
    retryit.exposed = True

    def retryissue(self, IssueID, ComicID, ComicName=None, IssueNumber=None, ReleaseComicID=None, ComicYear=None, redirect=None):

        # mode = either series or annual (want vs. want_ann)
        #To retry the exact download again - we already have the nzb/torrent name stored in the nzblog.
        #0 - Change status to Retrying.
        #1 - we need to search the snatched table for the relevant information (since it HAS to be in snatched status)
        #2 - we need to reference the ID from the snatched table to the nzblog table
        #  - if it doesn't match, then it's an invalid retry.
        #  - if it does match, we get the nzbname/torrent name and provider info
        #3 - if it's an nzb - we recreate the sab/nzbget url and resubmit it directly.
        #  - if it's a torrent - we redownload the torrent and flip it to the watchdir on the local / seedbox.
        #4 - Change status to Snatched.
        myDB = db.DBConnection()
        chk_snatch = myDB.select('SELECT * FROM snatched WHERE IssueID=?', [IssueID])
        if chk_snatch is None:
            logger.info('Unable to locate how issue was downloaded (name, provider). Cannot continue.')
            return json.dumps({'status': 'failure', 'message': 'Unable to locate how issue was downloaded. Cannot retry.'})

        providers_snatched = []
        confirmedsnatch = False
        for cs in chk_snatch:
            if cs['Provider'] == 'CBT' or cs['Provider'] == 'KAT':
                logger.info('Invalid provider attached to download (' + cs['Provider'] + '). I cannot find this on 32P, so ignoring this result.')
            elif cs['Status'] == 'Snatched':
                logger.info('Located snatched download:')
                logger.info('--Referencing : ' + cs['Provider'] + ' @ ' + str(cs['DateAdded']))
                providers_snatched.append({'Provider':    cs['Provider'],
                                           'DateAdded':   cs['DateAdded']})
                confirmedsnatch = True
            elif (cs['Status'] == 'Post-Processed' or cs['Status'] == 'Downloaded') and confirmedsnatch == True:
                logger.info('Issue has already been Snatched, Downloaded & Post-Processed.')
                logger.info('You should be using Manual Search or Mark Wanted - not retry the same download.')
                return json.dumps({'status': 'failure', 'message': 'Issue has already been Post-Processed. You should mark as Wanted / Manual Search'})

        if len(providers_snatched) == 0:
            return json.dumps({'status': 'failure', 'message': 'No providers are enabled to try the redownload'})

        chk_logresults = []
        for ps in sorted(providers_snatched, key=itemgetter('DateAdded', 'Provider'), reverse=True):
            try:
                Provider_sql = '%' + ps['Provider'] + '%'
                chk_the_log = myDB.selectone('SELECT * FROM nzblog WHERE IssueID=? OR IssueID=? AND Provider like (?)', [IssueID, 'S'+IssueID, Provider_sql]).fetchone()
            except:
                logger.warn('Unable to locate provider reference for attempted Retry. Will see if I can just get the last attempted download.')
                chk_the_log = myDB.selectone('SELECT * FROM nzblog WHERE IssueID=? and Provider != "CBT" and Provider != "KAT"', [IssueID]).fetchone()

            if chk_the_log is None:
                if len(providers_snatched) == 1:
                    logger.info('Unable to locate provider information ' + ps['Provider'] + ' from nzblog - if you wiped the log, you have to search/download as per normal')
                    return json.dumps({'status': 'failure', 'message': 'Cannot locate provider information for issue'})
                else:
                    logger.info('Unable to locate provider information ' + ps['Provider'] + ' from nzblog. Checking additional providers that came back as being used to download this issue')
                    continue
            else:
                chk_logresults.append({'NZBName':   chk_the_log['NZBName'],
                                       'ID':        chk_the_log['ID'],
                                       'PROVIDER':  chk_the_log['PROVIDER']})


        if all([ComicYear is not None, ComicYear != 'None']) and all([IssueID is not None, IssueID != 'None']):
            getYear = myDB.selectone('SELECT IssueDate, ReleaseDate FROM Issues WHERE IssueID=?', [IssueID]).fetchone()
            if getYear is None:
                logger.warn('Unable to retrieve any valid date for Issue (Try to refresh the series and then try again.')
                return json.dumps({'status': 'failure', 'message': 'Invalid Issue Date for issue (refresh the series maybe)'})
            if getYear['IssueDate'][:4] == '0000':
                if getYear['ReleaseDate'][:4] == '0000':
                    logger.warn('Unable to retrieve valid Issue/Release Date for Retry of Issue (Try to refresh the series and then try again.')
                    return json.dumps({'status': 'failure', 'message': 'Invalid Issue/Release Date for issue (refresh the series maybe)'})
                else:
                    ComicYear = getYear['ReleaseDate'][:4]
            else:
                ComicYear = getYear['IssueDate'][:4]

        retried = False
        for chk_log in chk_logresults:
            nzbname = chk_log['NZBName']
            id = chk_log['ID']
            fullprov = chk_log['PROVIDER'] #the full newznab name if it exists will appear here as 'sitename (newznab)'

            #now we break it down by provider to recreate the link.
            #torrents first.
            if any([fullprov == '32P', fullprov == 'WWT', fullprov == 'DEM']):
                if not mylar.CONFIG.ENABLE_TORRENT_SEARCH:
                   logger.error('Torrent Providers are not enabled - unable to process retry request until provider is re-enabled.')
                   continue

                if fullprov == '32P':
                    if not mylar.CONFIG.ENABLE_32P:
                        logger.error('32P is not enabled - unable to process retry request until provider is re-enabled.')
                        continue

                elif any([fullprov == 'WWT', fullprov == 'DEM']):
                    if not mylar.CONFIG.ENABLE_PUBLIC:
                        logger.error('Public Torrents are not enabled - unable to process retry request until provider is re-enabled.')
                        continue

                logger.fdebug("sending .torrent to watchdir.")
                logger.fdebug("ComicName:" + ComicName)
                logger.fdebug("Torrent Provider:" + fullprov)
                logger.fdebug("Torrent ID:" + str(id))

                rcheck = mylar.rsscheck.torsend2client(ComicName, IssueNumber, ComicYear, id, fullprov)
                if rcheck == "fail":
                   logger.error("Unable to send torrent - check logs and settings.")
                   continue
                else:
                    if any([mylar.USE_RTORRENT, mylar.USE_DELUGE]) and mylar.CONFIG.AUTO_SNATCH:
                        mylar.SNATCHED_QUEUE.put(rcheck['hash'])
                    elif mylar.CONFIG.ENABLE_SNATCH_SCRIPT:
                        #packs not supported on retry atm - Volume and Issuedate also not included due to limitations...
                        snatch_vars = {'comicinfo':       {'comicname':        ComicName,
                                                           'issuenumber':      IssueNumber,
                                                           'seriesyear':       ComicYear,
                                                           'comicid':          ComicID,
                                                           'issueid':          IssueID},
                                       'pack':             False,
                                       'pack_numbers':     None,
                                       'pack_issuelist':   None,
                                       'provider':         fullprov,
                                       'method':           'torrent',
                                       'clientmode':       rcheck['clientmode'],
                                       'torrentinfo':      rcheck}

                        snatchitup = helpers.script_env('on-snatch',snatch_vars)
                        if snatchitup is True:
                            logger.info('Successfully submitted on-grab script as requested.')
                        else:
                            logger.info('Could not Successfully submit on-grab script as requested. Please check logs...')

                logger.info('Successfully retried issue.')
                break
            else:
                oneoff = False
                chkthis = myDB.selectone('SELECT a.ComicID, a.ComicName, a.ComicVersion, a.ComicYear, b.IssueID, b.Issue_Number, b.IssueDate FROM comics as a INNER JOIN annuals as b ON a.ComicID = b.ComicID WHERE IssueID=? AND NOT b.Deleted', [IssueID]).fetchone()
                if chkthis is None:
                    chkthis = myDB.selectone('SELECT a.ComicID, a.ComicName, a.ComicVersion, a.ComicYear, b.IssueID, b.Issue_Number, b.IssueDate FROM comics as a INNER JOIN issues as b ON a.ComicID = b.ComicID WHERE IssueID=?', [IssueID]).fetchone()
                    if chkthis is None:
                        chkthis = myDB.selectone('SELECT ComicID, ComicName, year as ComicYear, IssueID, IssueNumber as Issue_Number, weeknumber, year from oneoffhistory WHERE IssueID=?', [IssueID]).fetchone()
                        if chkthis is None:
                            if any(['_' in IssueID, IssueID.startswith('S')]):
                                chkthis = myDB.selectone('SELECT ComicID, ComicName, seriesyear as ComicYear, IssueID, IssueNumber as Issue_Number, IssueDate, Volume as ComicVersion from storyarcs WHERE IssueArcID=?', [IssueID]).fetchone()
                            else:
                                chkthis = myDB.selectone('SELECT ComicID, ComicName, seriesyear as ComicYear, IssueID, IssueNumber as Issue_Number, IssueDate, Volume as ComicVersion from storyarcs WHERE IssueID=?', [IssueID]).fetchone()
                            if chkthis is None:
                                logger.warn('Unable to locate previous snatch details (checked issues/annuals/one-offs/storyarcs). Retrying the snatch for this issue is unavailable.')
                                continue
                        else:
                            logger.fdebug('Successfully located issue as a one-off download initiated via pull-list. Let\'s do this....')
                            oneoff = True
                    modcomicname = chkthis['ComicName']
                else:
                    modcomicname = chkthis['ComicName'] + ' Annual'

                if oneoff is True:
                    weekchk = helpers.weekly_info(chkthis['weeknumber'], chkthis['year'])
                    IssueDate = weekchk['midweek']
                    ComicVersion = None
                else:
                    IssueDate = chkthis['IssueDate']
                    ComicVersion = chkthis['ComicVersion']
                comicinfo = [{"ComicName":     chkthis['ComicName'],
                              "ComicVolume":   ComicVersion,
                              "IssueNumber":   chkthis['Issue_Number'],
                              "comyear":       chkthis['ComicYear'],
                              "IssueDate":     IssueDate,
                              "pack":          False,
                              "modcomicname":  modcomicname,
                              "oneoff":        oneoff}]

                newznabinfo = None
                link = None

                #if fullprov == 'nzb.su':
                #    if not mylar.CONFIG.NZBSU:
                #        logger.error('nzb.su is not enabled - unable to process retry request until provider is re-enabled.')
                #        continue
                #    # http://nzb.su/getnzb/ea1befdeee0affd663735b2b09010140.nzb&i=<uid>&r=<passkey>
                #    link = 'http://nzb.su/getnzb/' + str(id) + '.nzb&i=' + str(mylar.CONFIG.NZBSU_UID) + '&r=' + str(mylar.CONFIG.NZBSU_APIKEY)
                #    logger.info('fetched via nzb.su. Retrying the send : ' + str(link))
                #    retried = True
                #elif fullprov == 'dognzb':
                #    if not mylar.CONFIG.DOGNZB:
                #        logger.error('Dognzb is not enabled - unable to process retry request until provider is re-enabled.')
                #        continue
                #    # https://dognzb.cr/fetch/5931874bf7381b274f647712b796f0ac/<passkey>
                #    link = 'https://dognzb.cr/fetch/' + str(id) + '/' + str(mylar.CONFIG.DOGNZB_APIKEY)
                #    logger.info('fetched via dognzb. Retrying the send : ' + str(link))
                #    retried = True
                if fullprov == 'experimental':
                    if not mylar.CONFIG.EXPERIMENTAL:
                        logger.error('Experimental is not enabled - unable to process retry request until provider is re-enabled.')
                        continue
                    # http://nzbindex.nl/download/110818178
                    link = 'http://nzbindex.nl/download/' + str(id)
                    logger.info('fetched via experimental. Retrying the send : ' + str(link))
                    retried = True
                elif 'newznab' in fullprov:
                    if not mylar.CONFIG.NEWZNAB:
                        logger.error('Newznabs are not enabled - unable to process retry request until provider is re-enabled.')
                        continue

                    # http://192.168.2.2/getnzb/4323f9c567c260e3d9fc48e09462946c.nzb&i=<uid>&r=<passkey>
                    # trickier - we have to scroll through all the newznabs until we find a match.
                    logger.info('fetched via newnzab. Retrying the send.')
                    m = re.findall('[^()]+', fullprov)
                    tmpprov = m[0].strip()

                    for newznab_info in mylar.CONFIG.EXTRA_NEWZNABS:
                        if tmpprov.lower() in newznab_info[0].lower():
                            if (newznab_info[5] == '1' or newznab_info[5] == 1):
                                if newznab_info[1].endswith('/'):
                                    newznab_host = newznab_info[1]
                                else:
                                    newznab_host = newznab_info[1] + '/'
                                newznab_api = newznab_info[3]
                                newznab_uid = newznab_info[4]
                                link = str(newznab_host) + '/api?apikey=' + str(newznab_api) + '&t=get&id=' + str(id)
                                logger.info('newznab detected as : ' + str(newznab_info[0]) + ' @ ' + str(newznab_host))
                                logger.info('link : ' + str(link))
                                newznabinfo = (newznab_info[0], newznab_info[1], newznab_info[2], newznab_info[3], newznab_info[4])
                                retried = True
                            else:
                                logger.error(str(newznab_info[0]) + ' is not enabled - unable to process retry request until provider is re-enabled.')
                            break
                elif 'DDL' in fullprov:
                    get_id = myDB.selectone('SELECT id, mainlink FROM ddl_info WHERE IssueID=?', [IssueID]).fetchone()
                    if get_id:
                        link = {'id': get_id[0], 'link': get_id[1]}
                        retried = True

                if link is not None:
                    sendit = search.searcher(fullprov, nzbname, comicinfo, link=link, IssueID=IssueID, ComicID=ComicID, tmpprov=fullprov, directsend=True, newznab=newznabinfo)
                    break

        if retried is True:
            retry_status = 'success'
            if comicinfo is not None:
                cinfo = comicinfo[0]
                if cinfo['IssueNumber'] is not None:
                    retry_message = 'Successfully submitted retry for %s (%s) #%s' % (cinfo['ComicName'], cinfo['comyear'], cinfo['IssueNumber'])
                else:
                    retry_message = 'Successfully submitted retry for %s (%s)' % (cinfo['ComicName'], cinfo['comyear'])
            else:
                retry_message = 'Successfully submitted retry'
        else:
            retry_status = 'failure'
            retry_message = 'Unable to retry issue - please check the logs for more information.'

        return json.dumps({'status': retry_status, 'message': retry_message})

    retryissue.exposed = True

    def queueit(self, **kwargs):
        threading.Thread(target=self.queueissue, kwargs=kwargs).start()
    queueit.exposed = True

    def queueissue(self, mode, ComicName=None, ComicID=None, ComicYear=None, ComicIssue=None, IssueID=None, new=False, redirect=None, SeriesYear=None, SARC=None, IssueArcID=None, manualsearch=None, Publisher=None, pullinfo=None, pullweek=None, pullyear=None, manual=False, ComicVersion=None, BookType=None):
        logger.fdebug('ComicID: %s' % ComicID)
        logger.fdebug('mode: %s' % mode)
        now = datetime.datetime.now()
        myDB = db.DBConnection()
        #mode dictates type of queue - either 'want' for individual comics, or 'series' for series watchlist.
        if ComicID is None and mode == 'series':
            issue = None
            raise cherrypy.HTTPRedirect("searchit?name=%s&issue=%s&mode=%s" % (ComicName, 'None', 'series'))
        elif ComicID is None and mode == 'pullseries':
            # we can limit the search by including the issue # and searching for
            # comics that have X many issues
            raise cherrypy.HTTPRedirect("searchit?name=%s&issue=%s&mode=%s" % (ComicName, 'None', 'pullseries'))
        elif ComicID is None and mode == 'readlist':
            # this is for marking individual comics from a readlist to be downloaded.
            # Because there is no associated ComicID or IssueID, follow same pattern as in 'pullwant'
            # except we know the Year
            if len(ComicYear) > 4:
                ComicYear = ComicYear[:4]
            if SARC is None:
                # it's just a readlist queue (no storyarc mode enabled)
                SARC = True
                IssueArcID = None
            else:
                logger.info('Story Arc : %s queueing selected issue...' % SARC)
                logger.fdebug('IssueArcID : %s' % IssueArcID)
                #try to load the issue dates - can now sideload issue details.
                dateload = myDB.selectone('SELECT * FROM storyarcs WHERE IssueArcID=?', [IssueArcID]).fetchone()
                if dateload is None:
                    IssueDate = None
                    ReleaseDate = None
                    Publisher = None
                    SeriesYear = None
                else:
                    IssueDate = dateload['IssueDate']
                    ReleaseDate = dateload['ReleaseDate']
                    Publisher = dateload['IssuePublisher']
                    SeriesYear = dateload['SeriesYear']
                    BookType = dateload['Type']

            if ComicYear is None: ComicYear = SeriesYear
            if dateload['Volume'] is None:
                logger.info('Marking %s #%s as wanted...' % (ComicName, ComicIssue))
            else:
                logger.info('Marking %s (%s) #%s as wanted...' % (ComicName, dateload['Volume'], ComicIssue))
            logger.fdebug('publisher: %s' % Publisher)
            controlValueDict = {"IssueArcID": IssueArcID}
            newStatus = {"Status": "Wanted"}
            myDB.upsert("storyarcs", newStatus, controlValueDict)
            moduletype = '[STORY-ARCS]'
            passinfo = {'issueid':     IssueArcID,
                        'comicname':   ComicName,
                        'seriesyear':  SeriesYear,
                        'comicid':     ComicID,
                        'issuenumber': ComicIssue,
                        'booktype':    BookType}

        elif mode == 'pullwant':  #and ComicID is None
            #this is for marking individual comics from the pullist to be downloaded.
            #--comicid & issueid may both be known (or either) at any given point if alt_pull = 2
            #because ComicID and IssueID will both be None due to pullist, it's probably
            #better to set both to some generic #, and then filter out later...
            IssueDate = pullinfo
            try:
                SeriesYear = IssueDate[:4]
            except:
                SeriesYear == now.year
            if Publisher == 'COMICS': Publisher = None
            moduletype = '[PULL-LIST]'
            passinfo = {'issueid':     IssueID,
                        'comicname':   ComicName,
                        'seriesyear':  SeriesYear,
                        'comicid':     ComicID,
                        'issuenumber': ComicIssue,
                        'booktype':    BookType}

        elif mode == 'want' or mode == 'want_ann' or manualsearch:
            cdname = myDB.selectone("SELECT * from comics where ComicID=?", [ComicID]).fetchone()
            if ComicName is None:
                ComicName = cdname['ComicName']
            ComicName_Filesafe = cdname['ComicName_Filesafe']
            SeriesYear = cdname['ComicYear']
            AlternateSearch = cdname['AlternateSearch']
            Publisher = cdname['ComicPublisher']
            UseAFuzzy = cdname['UseFuzzy']
            AllowPacks= cdname['AllowPacks']
            ComicVersion = cdname['ComicVersion']
            ComicName = cdname['ComicName']
            TorrentID_32p = cdname['TorrentID_32P']
            BookType = cdname['Type']
            if cdname['Corrected_Type'] is not None:
                BookType = cdname['Corrected_Type']
            controlValueDict = {"IssueID": IssueID}
            newStatus = {"Status": "Wanted"}
            if mode == 'want':
                if manualsearch:
                    logger.info('Initiating manual search for %s issue: %s' % (ComicName, ComicIssue))
                else:
                    logger.info('Marking %s issue: %s as wanted...' % (ComicName, ComicIssue))
                    myDB.upsert("issues", newStatus, controlValueDict)
            else:
                annual_name = myDB.selectone("SELECT * FROM annuals WHERE ComicID=? and IssueID=? AND NOT Deleted", [ComicID, IssueID]).fetchone()
                if annual_name is None:
                    logger.fdebug('Unable to locate.')
                else:
                    ComicName = annual_name['ReleaseComicName']

                if manualsearch:
                    logger.info('Initiating manual search for %s : %s' % (ComicName, ComicIssue))
                else:
                    logger.info('Marking %s : %s as wanted...' % (ComicName, ComicIssue))
                    myDB.upsert("annuals", newStatus, controlValueDict)
            moduletype = '[WANTED-SEARCH]'
            passinfo = {'issueid': IssueID,
                        'comicname': ComicName,
                        'seriesyear': SeriesYear,
                        'comicid': ComicID,
                        'issuenumber': ComicIssue,
                        'booktype': BookType,
                        'manual': manualsearch}


            if mode == 'want':
                issues = myDB.selectone("SELECT IssueDate, ReleaseDate FROM issues WHERE IssueID=?", [IssueID]).fetchone()
            elif mode == 'want_ann':
                issues = myDB.selectone("SELECT IssueDate, ReleaseDate FROM annuals WHERE IssueID=? AND NOT Deleted", [IssueID]).fetchone()
            if ComicYear == None:
                ComicYear = str(issues['IssueDate'])[:4]
            if issues['ReleaseDate'] is None or issues['ReleaseDate'] == '0000-00-00':
                logger.info('No Store Date found for given issue. This is probably due to not Refreshing the Series beforehand.')
                logger.info('I Will assume IssueDate as Store Date, but you should probably Refresh the Series and try again if required.')
                storedate = issues['IssueDate']
            else:
                storedate = issues['ReleaseDate']

        if any([BookType == 'TPB', BookType == 'HC', BookType == 'GN']):
            logger.info('%s[%s] Now Queueing %s (%s) for search' % (moduletype, BookType, ComicName, SeriesYear))
        elif ComicIssue is None:
            logger.info('%s Now Queueing %s (%s) for search' % (moduletype, ComicName, SeriesYear))
        else:
            logger.info('%s Now Queueing %s (%s) #%s for search' % (moduletype, ComicName, SeriesYear, ComicIssue))

        #s = mylar.SEARCH_QUEUE.put({'issueid': IssueID, 'comicname': ComicName, 'seriesyear': SeriesYear, 'comicid': ComicID, 'issuenumber': ComicIssue, 'booktype': BookType})
        s = mylar.SEARCH_QUEUE.put(passinfo)
        #if manualsearch:
        #    # if it's a manual search, return to null here so the thread will die and not cause http redirect errors.
        #    return
        if ComicID:
            return json.dumps({'status': 'success', 'comicid': ComicID, 'comicname': ComicName, 'seriesyear': SeriesYear, 'tables': 'table', 'message': 'Successfully submitted search for %s #%s...' % (ComicName, ComicIssue)})
        else:
            return
    queueissue.exposed = True

    def unqueueissue(self, IssueID, ComicID, ComicName=None, Issue=None, smode=None, ReleaseComicID=None):
        myDB = db.DBConnection()
        if ReleaseComicID == 'null':
            ReleaseComicID = None
        if ComicName is None:
            if ReleaseComicID is None:  #ReleaseComicID is used for annuals.
                issue = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
            else:
                issue = None
            annchk = 'no'
            if issue is None:
                if mylar.CONFIG.ANNUALS_ON:
                    if ReleaseComicID is None:
                        issann = myDB.selectone('SELECT * FROM annuals WHERE IssueID=? AND NOT Deleted', [IssueID]).fetchone()
                    else:
                        issann = myDB.selectone('SELECT * FROM annuals WHERE IssueID=? AND ReleaseComicID=? AND NOT Deleted', [IssueID, ReleaseComicID]).fetchone()
                    ComicName = issann['ReleaseComicName']
                    IssueNumber = issann['Issue_Number']
                    annchk = 'yes'
                    ComicID = issann['ComicID']
                    ReleaseComicID = issann['ReleaseComicID']
            else:
                ComicName = issue['ComicName']
                IssueNumber = issue['Issue_Number']

            controlValueDict = {"IssueID": IssueID}
            if smode == 'failed' and mylar.CONFIG.FAILED_DOWNLOAD_HANDLING:
                logger.info("Marking " + ComicName + " issue # " + IssueNumber + " as Failed...")
                newValueDict = {"Status": "Failed"}
                myDB.upsert("failed", newValueDict, controlValueDict)
                if annchk == 'yes':
                   myDB.upsert("annuals", newValueDict, controlValueDict)
                else:
                   myDB.upsert("issues", newValueDict, controlValueDict)
                self.failed_handling(ComicID=ComicID, IssueID=IssueID)
            else:
                logger.info("Marking " + ComicName + " issue # " + IssueNumber + " as Skipped...")
                newValueDict = {"Status": "Skipped"}
                if annchk == 'yes':
                   myDB.upsert("annuals", newValueDict, controlValueDict)
                else:
                   myDB.upsert("issues", newValueDict, controlValueDict)
        return json.dumps({'status': 'success', 'message': 'Successfully changed status of %s #%s to %s' % (ComicName, IssueNumber, smode)})
    unqueueissue.exposed = True

    def failed_handling(self, ComicID, IssueID):
        import queue
        queue = queue.Queue()

        FailProcess = Failed.FailedProcessor(issueid=IssueID, comicid=ComicID, queue=queue)
        thread_ = threading.Thread(target=FailProcess.Process, name="FAILED Post-Processing")
        thread_.start()
        thread_.join()
        failchk = queue.get()
        if failchk[0]['mode'] == 'retry':
            logger.info('Attempting to return to search module with ' + str(failchk[0]['issueid']))
            if failchk[0]['annchk'] == 'no': mode = 'want'
            else: mode = 'want_ann'
            self.queueit(mode=mode, ComicName=failchk[0]['comicname'], ComicIssue=failchk[0]['issuenumber'], ComicID=failchk[0]['comicid'], IssueID=failchk[0]['issueid'], manualsearch=True)
        elif failchk[0]['mode'] == 'stop':
            pass
        else:
            logger.error('mode is unsupported: ' + failchk[0]['mode'])

    failed_handling.exposed = True

    def archiveissue(self, IssueID, comicid):
        myDB = db.DBConnection()
        issue = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
        annchk = 'no'
        if issue is None:
            if mylar.CONFIG.ANNUALS_ON:
                issann = myDB.selectone('SELECT * FROM annuals WHERE IssueID=? AND NOT Deleted', [IssueID]).fetchone()
                comicname = issann['ReleaseComicName']
                issue = issann['Issue_Number']
                annchk = 'yes'
                comicid = issann['ComicID']
        else:
            comicname = issue['ComicName']
            issue = issue['Issue_Number']
        logger.info("Marking " + comicname + " issue # " + str(issue) + " as archived...")
        controlValueDict = {'IssueID': IssueID}
        newValueDict = {'Status': 'Archived'}
        if annchk == 'yes':
            myDB.upsert("annuals", newValueDict, controlValueDict)
        else:
            myDB.upsert("issues", newValueDict, controlValueDict)
        raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % comicid)
    archiveissue.exposed = True

    def pullSearch(self, week, year):
        myDB = db.DBConnection()
        #retrieve a list of all the issues that are in a Wanted state from the pull that we can search for.
        ps = myDB.select("SELECT * from weekly WHERE Status='Wanted' AND weeknumber=? AND year=?", [int(week), year])
        if ps is None:
            logger.info('No items are marked as Wanted on the pullist to be searched for at this time')
            return
        issuesToSearch = []
        for p in ps:
            if p['IssueID'] is not None:
                issuesToSearch.append(p['IssueID'])

        if len(issuesToSearch) > 0:
            logger.info('Now force searching for ' + str(len(issuesToSearch)) + ' issues from the pullist for week ' + str(week))
            threading.Thread(target=search.searchIssueIDList, args=[issuesToSearch]).start()
        else:
            logger.info('Issues are marked as Wanted, but no issue information is available yet so I cannot search for anything. Try Recreating the pullist if you think this is error.')
            return
    pullSearch.exposed = True

    def pullist(self, **args): #week=None, year=None, generateonly=False, current=None):
        week = None
        year = None
        generateonly = False
        current = None
        for k,v in list(args.items()):
            if k == 'week':
                week = v
            elif k == 'year':
                year = v
            elif k == 'generateonly':
                generateonly = v
            elif k == 'current':
                current = v

        myDB = db.DBConnection()
        autowant = []
        if generateonly is False:
            autowants = myDB.select("SELECT * FROM futureupcoming WHERE Status='Wanted'")
            if autowants:
                for aw in autowants:
                    autowant.append({"ComicName":        aw['ComicName'],
                                     "IssueNumber":      aw['IssueNumber'],
                                     "Publisher":        aw['Publisher'],
                                     "Status":           aw['Status'],
                                     "DisplayComicName": aw['DisplayComicName']})
        weeklyresults = []
        wantedcount = 0
        weekinfo = helpers.weekly_info(week, year, current)
        popit = myDB.select("SELECT * FROM sqlite_master WHERE name='weekly' and type='table'")
        if popit:
            w_results = myDB.select("SELECT * from weekly WHERE weeknumber=? AND year=?", [int(weekinfo['weeknumber']),weekinfo['year']])
            if len(w_results) == 0:
                logger.info('trying to repopulate to week: ' + str(weekinfo['weeknumber']) + '-' + str(weekinfo['year']))
                repoll = self.pullrecreate(weeknumber=weekinfo['weeknumber'],year=weekinfo['year'])
                if repoll['status'] == 'success':
                    w_results = myDB.select("SELECT * from weekly WHERE weeknumber=? AND year=?", [int(weekinfo['weeknumber']),weekinfo['year']])
                else:
                    logger.warn('Problem repopulating the pullist for week ' + str(weekinfo['weeknumber']) + ', ' + str(weekinfo['year']))
                    if mylar.CONFIG.ALT_PULL == 2:
                        logger.warn('Attempting to repoll against legacy pullist in order to have some kind of updated listing for the week.')
                        repoll = self.manualpull()
                        if repoll['status'] == 'success':
                            w_results = myDB.select("SELECT * from weekly WHERE weeknumber=? AND year=?", [int(weekinfo['weeknumber']),weekinfo['year']])
                        else:
                            logger.warn('Unable to populate the pull-list. Not continuing at this time (will try again in abit)')

            if all([w_results is None, generateonly is False]):
                return serve_template(templatename="weeklypull.html", title="Weekly Pull", weeklyresults=weeklyresults, pullfilter=True, weekfold=weekinfo['week_folder'], wantedcount=0, weekinfo=weekinfo)

            watchlibrary = helpers.listLibrary()
            issueLibrary = helpers.listIssues(weekinfo['weeknumber'], weekinfo['year'])
            oneofflist = helpers.listoneoffs(weekinfo['weeknumber'], weekinfo['year'])
            chklist = []

            for weekly in w_results:
                xfound = False
                tmp_status = weekly['Status']
                if weekly['ComicID'] in watchlibrary and all([tmp_status != 'Mismatched', tmp_status != 'Incomplete']):
                    haveit = watchlibrary[weekly['ComicID']]['comicid']

                    if weekinfo['weeknumber']:
                        if watchlibrary[weekly['ComicID']]['status'] == 'Paused':
                            tmp_status = 'Paused'
                        elif (week is None or all([week is not None, int(week) >= int(weekinfo['weeknumber'])])) and all([mylar.CONFIG.AUTOWANT_UPCOMING, tmp_status == 'Skipped']):
                            tmp_status = 'Wanted'
                    for x in issueLibrary:
                        if weekly['IssueID'] == x['IssueID'] and tmp_status != 'Paused':
                            xfound = True
                            tmp_status = x['Status']
                            break

                else:
                    xlist = [x['Status'] for x in oneofflist if x['IssueID'] == weekly['IssueID'] and weekly['IssueID'] is not None]
                    if xlist:
                        haveit = 'OneOff'
                        tmp_status = xlist[0]
                    else:
                        haveit = "No"

                linkit = None
                if all([weekly['ComicID'] is not None, weekly['ComicID'] != '', haveit == 'No']) or haveit == 'OneOff':
                    linkit = 'http://comicvine.gamespot.com/volume/4050-' + str(weekly['ComicID'])
                else:
                    if any([weekly['Status'] == 'Mismatched', weekly['Status'] == 'Incomplete']) and all([haveit == 'No', weekly['IssueID'] is not None]):
                        linkit = 'http://comicvine.gamespot.com/volume/4000-' + str(weekly['IssueID'])
                    elif any([weekly['Status'] == 'Mismatched', weekly['Status'] == 'Incomplete']) and all([haveit == 'Yes', weekly['ComicID'] is not None]):
                        linkit = 'http://comicvine.gamespot.com/volume/4050-' + str(weekly['ComicID'])
                    else:
                    #setting it here will force it to set the link to the right comicid regardless of annuals or not
                        linkit = haveit

                x = None
                try:
                    x = float(weekly['ISSUE'])
                except ValueError as e:
                    if helpers.issueExceptionCheck(weekly['ISSUE'], full_match=False):
                        x = weekly['ISSUE']

                if x is not None:
                    if not autowant:
                        weeklyresults.append({
                                           "PUBLISHER": weekly['PUBLISHER'],
                                           "ISSUE": weekly['ISSUE'],
                                           "COMIC": weekly['COMIC'],
                                           "STATUS":  tmp_status,
                                           "COMICID": weekly['ComicID'],
                                           "ISSUEID": weekly['IssueID'],
                                           "VOLUME":  weekly['volume'],
                                           "SERIESYEAR": weekly['seriesyear'],
                                           "HAVEIT":  haveit,
                                           "LINK":    linkit,
                                           "HASH":    None,
                                           "AUTOWANT": False,
                                           "FORMAT":   weekly['format']
                                         })
                    else:
                        if any(x['ComicName'].lower() == weekly['COMIC'].lower() for x in autowant):
                            weeklyresults.append({
                                           "PUBLISHER": weekly['PUBLISHER'],
                                           "ISSUE": weekly['ISSUE'],
                                           "COMIC": weekly['COMIC'],
                                           "STATUS":  tmp_status,
                                           "COMICID": weekly['ComicID'],
                                           "ISSUEID": weekly['IssueID'],
                                           "VOLUME":  weekly['volume'],
                                           "SERIESYEAR": weekly['seriesyear'],
                                           "HAVEIT":  haveit,
                                           "LINK":    linkit,
                                           "HASH":    None,
                                           "AUTOWANT": True,
                                           "FORMAT":   weekly['format']
                                         })
                        else:
                            weeklyresults.append({
                                           "PUBLISHER": weekly['PUBLISHER'],
                                           "ISSUE": weekly['ISSUE'],
                                           "COMIC": weekly['COMIC'],
                                           "STATUS":  tmp_status,
                                           "COMICID": weekly['ComicID'],
                                           "ISSUEID": weekly['IssueID'],
                                           "VOLUME":  weekly['volume'],
                                           "SERIESYEAR": weekly['seriesyear'],
                                           "HAVEIT":  haveit,
                                           "LINK":    linkit,
                                           "HASH":    None,
                                           "AUTOWANT": False,
                                           "FORMAT":   weekly['format']
                                         })

                    if tmp_status == 'Wanted':
                        wantedcount +=1
                    elif tmp_status == 'Snatched':
                        chklist.append(str(weekly['IssueID']))

            weeklyresults = sorted(weeklyresults, key=itemgetter('PUBLISHER', 'COMIC'), reverse=False)
        else:
            self.manualpull()

        if generateonly is True:
            return weeklyresults, weekinfo
        else:
            endresults = []
            if len(chklist) > 0:
                for genlist in helpers.chunker(chklist, 200):
                    tmpsql = "SELECT * FROM snatched where Status='Snatched' and status != 'Post-Processed' and (provider='32P' or Provider='WWT' or Provider='DEM') AND IssueID in ({seq})".format(seq=','.join(['?'] *(len(genlist))))
                    chkthis = myDB.select(tmpsql, genlist)
                    if chkthis is None:
                        continue
                    else:
                        for w in weeklyresults:
                            weekit = w
                            snatchit = [x['hash'] for x in chkthis if w['ISSUEID'] == x['IssueID']]
                            try:
                                if snatchit:
                                    logger.fdebug('[%s] Discovered previously snatched torrent not downloaded. Marking for manual auto-snatch retrieval: %s' % (w['COMIC'], ''.join(snatchit)))
                                    weekit['HASH'] = ''.join(snatchit)
                                else:
                                    weekit['HASH'] = None
                            except:
                                weekit['HASH'] = None
                            endresults.append(weekit)
                        weeklyresults = endresults

            if week:
                return serve_template(templatename="weeklypull.html", title="Weekly Pull", weeklyresults=weeklyresults, pullfilter=True, weekfold=weekinfo['week_folder'], wantedcount=wantedcount, weekinfo=weekinfo, auto_mass_add=helpers.checked(mylar.CONFIG.AUTO_MASS_ADD))
            else:
                return serve_template(templatename="weeklypull.html", title="Weekly Pull", weeklyresults=weeklyresults, pullfilter=True, weekfold=weekinfo['week_folder'], wantedcount=wantedcount, weekinfo=weekinfo, auto_mass_add=helpers.checked(mylar.CONFIG.AUTO_MASS_ADD))
    pullist.exposed = True

    def removeautowant(self, comicname, release):
        myDB = db.DBConnection()
        logger.fdebug('Removing ' + comicname + ' from the auto-want list.')
        myDB.action("DELETE FROM futureupcoming WHERE ComicName=? AND IssueDate=? AND Status='Wanted'", [comicname, release])
    removeautowant.exposed = True

    def add2futurewatchlist(self, ComicName, Issue, Publisher, ShipDate, weeknumber, year):
        #ShipDate is just weekinfo['midweek'] #a tuple ('weeknumber','startweek','midweek','endweek','year')
        myDB = db.DBConnection()
        logger.info(ShipDate)

        chkfuture = myDB.selectone('SELECT * FROM futureupcoming WHERE ComicName=? AND IssueNumber=? AND weeknumber=? AND year=?', [ComicName, Issue, weeknumber, year]).fetchone()
        if chkfuture is not None:
            logger.info('Already on Future Upcoming list - not adding at this time.')
            return

        logger.info('Adding ' + ComicName + ' # ' + str(Issue) + ' [' + Publisher + '] to future upcoming watchlist')
        newCtrl = {"ComicName":   ComicName,
                   "IssueNumber": Issue,
                   "Publisher":   Publisher}

        newVal = {"Status":       "Wanted",
                  "IssueDate":    ShipDate,
                  "weeknumber":   weeknumber,
                  "year":         year}

        myDB.upsert("futureupcoming", newVal, newCtrl)

    add2futurewatchlist.exposed = True

    def future_check(self):
        weeklypull.future_check()
        raise cherrypy.HTTPRedirect("upcoming")
    future_check.exposed = True

    def filterpull(self):
        myDB = db.DBConnection()
        weeklyresults = myDB.select("SELECT * from weekly")
        pulldate = myDB.selectone("SELECT * from weekly").fetchone()
        if pulldate is None:
            raise cherrypy.HTTPRedirect("home")
        return serve_template(templatename="weeklypull.html", title="Weekly Pull", weeklyresults=weeklyresults, pulldate=pulldate['SHIPDATE'], pullfilter=True)
    filterpull.exposed = True

    def manualpull(self,weeknumber=None,year=None):
        logger.info('ALT_PULL: ' + str(mylar.CONFIG.ALT_PULL) + ' PULLBYFILE: ' + str(mylar.PULLBYFILE) + ' week: ' + str(weeknumber) + ' year: ' + str(year))
        if all([mylar.CONFIG.ALT_PULL == 2, mylar.PULLBYFILE is False]) and weeknumber:
            return mylar.locg.locg(weeknumber=weeknumber,year=year)
        else:
            return {'status' : 'failure'}
    manualpull.exposed = True

    def pullrecreate(self, weeknumber=None, year=None):
        if mylar.BACKENDSTATUS_WS != 'up':
            logger.warn('[PULL-LIST] Cannot re-create pull-list as walksoftly is currently offline. Retaining existing pull-data until it\'s back online')
            return {'status': 'failure'}

        myDB = db.DBConnection()
        forcecheck = 'yes'
        #if weeknumber is None:
        #    myDB.action("DROP TABLE weekly")
        #    mylar.dbcheck()
        #    logger.info("Deleted existing pull-list data. Recreating Pull-list...")
        #else:
        #    myDB.action('DELETE FROM weekly WHERE weeknumber=? and year=?', [int(weeknumber), int(year)])
        #    logger.info("Deleted existing pull-list data for week %s, %s. Now Recreating the Pull-list..." % (weeknumber, year))
        logger.info("[PULL-LIST] Now Recreating the Pull-list for week %s, %s..." % (weeknumber, year))
        statchk = weeklypull.pullit(forcecheck, weeknumber, year)
        if statchk:
            if statchk['status'] == 'success':
                weekinfo = helpers.weekly_info(weeknumber, year)
                tmpcurrent = '%s%s' % (weekinfo['year'],weekinfo['current_weeknumber'])
                tmppull = '%s%s' % (year, weeknumber)
                if int(tmppull) <= int(tmpcurrent):
                    weeklypull.future_check()
                return {'status': 'success'}
        return {'status': 'failure'}
    pullrecreate.exposed = True

    def fly_me_to_the_moon(self):
        todaydate = datetime.datetime.today()
        weekinfo = helpers.weekly_info()

        weeknumber = weekinfo['current_weeknumber']
        weekyear = weekinfo['year']
        startweek = weekinfo['startweek']
        midweek = weekinfo['midweek']
        endweek = weekinfo['endweek']

        myDB = db.DBConnection()
        logger.info('weeknumber: %s' % weeknumber)
        upcomingdata = myDB.select("SELECT * from weekly WHERE Issue is not NULL AND Comic is not NULL and CAST(weeknumber as numeric) >= ? and CAST(year as numeric) >= ? order by weeknumber DESC", [weeknumber, weekyear])
        if upcomingdata is None:
            logger.info('No upcoming data as of yet...')
        else:
            futureupcoming = []
            upcoming = []
            upcoming_count = 0
            futureupcoming_count = 0
            for upc in upcomingdata:
                mylar.WANTED_TAB_OFF = False
                try:
                    ab = int(upc['weeknumber'])
                    bc = int(upc['year'])
                except TypeError:
                    logger.warn('Weekly Pull hasn\'t finished being generated as of yet (or has yet to initialize). Try to wait up to a minute to accomodate processing.')
                    mylar.WANTED_TAB_OFF = True
                    myDB.action("DROP TABLE weekly")
                    mylar.dbcheck()
                    logger.info("Deleted existed pull-list data. Recreating Pull-list...")
                    forcecheck = 'yes'
                    return threading.Thread(target=weeklypull.pullit, args=[forcecheck]).start()

                if int(upc['weeknumber']) == int(weeknumber) and int(upc['year']) == int(weekyear):
                    if all([upc['Status'] == 'Wanted', upc['IssueID'] is None]) or all([upc['Status'] == 'Incomplete', upc['IssueID'] is not None]):
                        upcoming_count +=1
                        upcoming.append({"ComicName":    upc['Comic'],
                                         "IssueNumber":  upc['Issue'],
                                         "IssueDate":    upc['ShipDate'],
                                         "ComicID":      upc['ComicID'],
                                         "IssueID":      upc['IssueID'],
                                         "Status":       upc['Status'],
                                         "WeekNumber":   upc['weeknumber'],
                                         "DynamicName":  upc['DynamicName']})

                else:
                    if int(upc['weeknumber']) > int(weeknumber) and any([upc['Status'] == 'Wanted', upc['Status'] == 'Incomplete']):
                        futureupcoming_count +=1
                        futureupcoming.append({"ComicName":    upc['Comic'],
                                               "IssueNumber":  upc['Issue'],
                                               "IssueDate":    upc['ShipDate'],
                                               "ComicID":      upc['ComicID'],
                                               "IssueID":      upc['IssueID'],
                                               "Status":       upc['Status'],
                                               "WeekNumber":   upc['weeknumber'],
                                               "DynamicName":  upc['DynamicName']})

        fup1 = sorted(futureupcoming, key=lambda x: x if isinstance(itemgetter('IssueDate'), str) else "", reverse=True)
        fup2 = sorted(fup1, key=itemgetter('ComicName'), reverse=True)
        futureupcoming = sorted(fup2, key=lambda x: x if isinstance(itemgetter('IssueNumber'), str) else "", reverse=True)

        #fix None DateAdded points here
        helpers.DateAddedFix()
        #let's straightload the series that have no issue data associated as of yet (ie. new series) from the futurepulllist
        future_nodata_upcoming = myDB.select("SELECT * FROM futureupcoming WHERE IssueNumber='1' OR IssueNumber='0'")

        #let's move any items from the upcoming table into the wanted table if the date has already passed.
        #gather the list...
        mvupcome = myDB.select("SELECT * from upcoming WHERE IssueDate < date('now') order by IssueDate DESC")
        #get the issue ID's
        for mvup in mvupcome:
            myissue = myDB.selectone("SELECT ComicName, Issue_Number, IssueID, ComicID FROM issues WHERE IssueID=?", [mvup['IssueID']]).fetchone()
            #myissue =  myDB.action("SELECT * FROM issues WHERE Issue_Number=?", [mvup['IssueNumber']]).fetchone()

            if myissue is None: pass
            else:
                logger.fdebug("--Updating Status of issues table because of Upcoming status--")
                logger.fdebug("ComicName: " + str(myissue['ComicName']))
                logger.fdebug("Issue number : " + str(myissue['Issue_Number']))

                mvcontroldict = {"IssueID":    myissue['IssueID']}
                mvvalues = {"ComicID":         myissue['ComicID'],
                            "Status":          "Wanted"}
                myDB.upsert("issues", mvvalues, mvcontroldict)

                #remove old entry from upcoming so it won't try to continually download again.
                logger.fdebug('[DELETE] - ' + mvup['ComicName'] + ' issue #: ' + str(mvup['IssueNumber']))
                deleteit = myDB.action("DELETE from upcoming WHERE ComicName=? AND IssueNumber=?", [mvup['ComicName'], mvup['IssueNumber']])

        mism = myDB.select("SELECT c.Type as BookType, c.ComicYear, c.ComicVersion, a.IssueDate, a.ReleaseDate, b.* FROM Comics as c LEFT JOIN Issues as a ON a.Comicid=c.ComicID INNER JOIN Weekly as b ON a.IssueID=b.IssueID WHERE b.Status='Mismatched' OR b.Status='Incomplete'")
        mismatched = []
        for mm in mism:
            mismatch_type = None
            if mm['Status'] == 'Mismatched':
                if mm['ShipDate'] != mm['IssueDate']:
                   mismatch_type = 'Incorrect Dates (%s - %s)' % (mm['IssueDate'], mm['ShipDate'])
                elif mm['Booktype'] != mm['Format']:
                    if all([mm['Booktype'] is not None, mm['Format'] is not None]):
                        mismatch_type = 'Incorrect BookTypes (%s - %s)' % (mm['BookType'], mm['Format'])
                if mismatch_type is None:
                     if mm['ComicYear'] != mm['SeriesYear']:
                        mismatch_type = 'Wrong BookType (%s - %s)' % (mm['ComicYear'], mm['SeriesYear'])
                     elif mm['ComicVersion'] != mm['Volume']:
                        mismatch_type = 'Wrong Volume (%s - %s)' % (mm['ComicVersion'], mm['Volume'])

            mismatched.append({'comicname': mm['Comic'],
                               'issuenumber': mm['Issue'],
                               'comicid': mm['ComicID'],
                               'status': mm['Status'],
                               'releasedate': mm['ShipDate'],
                               'mismatch_type': mismatch_type,
                               'pullyear': mm['year'],
                               'pullweek': mm['weeknumber']})
        logger.info('mismatched: %s' % (mismatched,))

        return {'upcoming': upcoming,
                'futureupcoming': futureupcoming,
                'future_nodata_upcoming': future_nodata_upcoming,
                'futureupcoming_count':futureupcoming_count,
                'upcoming_count': upcoming_count,
                'mismatched_count': len(mismatched),
                'mismatched': mismatched}
    fly_me_to_the_moon.exposed = True

    def upcoming(self):
        upcomingdata = self.fly_me_to_the_moon()
        return serve_template(templatename="upcoming.html", title="Upcoming", upcoming=upcomingdata['upcoming'], upcoming_count=upcomingdata['upcoming_count'], future_nodata_upcoming=upcomingdata['future_nodata_upcoming'], mismatched=upcomingdata['mismatched'], mismatched_count=upcomingdata['mismatched_count'])
    upcoming.exposed = True

    def update_upcoming_filters(self):
        myDB = db.DBConnection()

        statline = "Status='Wanted'"
        if mylar.CONFIG.UPCOMING_SNATCHED is True:
            statline += " OR Status='Snatched'"
        if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING is True:
            statline += " OR Status='Failed'"

        iss_query = "SELECT ComicName, Status, ComicID, IssueID, DateAdded from issues WHERE %s" % statline
        issues = myDB.select(iss_query)

        arcs = {}
        if mylar.CONFIG.UPCOMING_STORYARCS is True:
            arcs_query = "SELECT Storyarc, StoryArcID, IssueArcID, ComicName, Status, ComicID, IssueID, DateAdded from storyarcs WHERE %s" % statline
            arclist = myDB.select(arcs_query)
            for arc in arclist:
                arcs[arc['IssueID']] = {'storyarc': arc['Storyarc'],
                                        'storyarcid': arc['StoryArcID'],
                                        'issuearcid': arc['IssueArcID'],
                                        'comicid': arc['ComicID'],
                                        'comicname': arc['ComicName'],
                                        'status': arc['Status'],
                                        'dateadded': arc['DateAdded']}
        #logger.fdebug('# arcs: %s' % (len(arcs)))
        isCounts = {}
        isCounts[1] = 0   #1 wanted
        isCounts[2] = 0   #2 snatched
        isCounts[3] = 0   #3 failed
        isCounts[4] = 0   #4 tier1
        isCounts[5] = 0   #5 tier2

        ann_list = []

        ann_cnt = 0
        issues_list = []
        ann_failed = []

        if mylar.CONFIG.ANNUALS_ON:
            #let's add the annuals to the wanted table so people can see them
            #ComicName wasn't present in db initially - added on startup chk now.
            annuals_query = "SELECT * FROM annuals WHERE NOT Deleted AND %s" % statline
            annuals_list = myDB.select(annuals_query)

            issues += annuals_list

            for isse in issues:
                found_iss = False
                for d in ann_list:
                    if d['IssueID'] == str(isse['IssueID']):
                        found_iss = True
                        ann_failed.append({'issueid': isse['IssueID'],
                                           'comicid': isse['ComicID'],
                                           'comicname': isse['ComicName']})
                        break
                if found_iss:
                    pass
                else:
                    issues_list.append(isse)

            if len(ann_failed) > 0:
                logger.warn('[ANNUAL-DUPLICATION] There are duplicate issues in the Wanted list that are in both annuals and issues.')
                logger.warn('[ANNUAL-DUPLICATION] This is due to having annual integration enabled, while also having the annuals listed as a separate entry in your watchlist.')
                logger.fdebug('[ANNUAL-DUPLICATION] Duplicate entries (status of Wanted): %s' % (ann_failed,))

            issues = issues_list
            issues += ann_list

        for curResult in issues:
            baseissues = {'wanted': 1, 'snatched': 2, 'failed': 3}
            for seas in baseissues:
                if curResult['Status'] is None:
                   continue
                else:
                    if seas in curResult['Status'].lower():
                        sconv = baseissues[seas]
                        if curResult['Status'] == 'Wanted':
                            if curResult['DateAdded'] is not None and curResult['DateAdded'] <= mylar.SEARCH_TIER_DATE:
                                isCounts[4]+=1  #tier2
                            elif curResult['DateAdded'] is not None and curResult['DateAdded'] > mylar.SEARCH_TIER_DATE:
                                isCounts[5]+=1  #tier1
                        else:
                            isCounts[sconv]+=1  #everything else

                if curResult['IssueID'] in arcs:
                    arcs.pop(curResult['IssueID'])

        isCounts = {"wanted": str(isCounts[1]),
                    "snatched": str(isCounts[2]),
                    "failed": str(isCounts[3]),
                    #"storyarcs": str(len(arcs)),
                    "tier1": str(isCounts[5]),
                    "tier2": str(isCounts[4])}

        return json.dumps({'status': 'success', 'filters': isCounts})
    update_upcoming_filters.exposed = True

    def loadupcoming(self, iDisplayStart=0, iDisplayLength=100, iSortCol_0=5, sSortDir_0="desc", sSearch="", **kwargs):
        try:
            filters = json.loads(kwargs.get('filters'))
        except Exception as e:
            filters = []
        #logger.fdebug('filters: %s' % (filters,))

        myDB = db.DBConnection()
        if sSortDir_0 == 'desc':
            reverse_order = True
        else:
            reverse_order = False

        statline = "Status='Wanted'"
        if mylar.CONFIG.UPCOMING_SNATCHED is True:
            statline += " OR Status='Snatched'"
        if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING is True:
            statline += " OR Status='Failed'"

        iss_query = "SELECT ComicName, Issue_Number, Int_IssueNumber, ReleaseDate, Status, ComicID, IssueID, DateAdded from issues WHERE %s" % statline
        issues = myDB.select(iss_query)
        arcs = {}
        if mylar.CONFIG.UPCOMING_STORYARCS is True:
            arcs_query = "SELECT Storyarc, StoryArcID, IssueArcID, ComicName, IssueNumber, Int_IssueNumber, ReleaseDate, Status, ComicID, IssueID, DateAdded from storyarcs WHERE %s" % statline
            arclist = myDB.select(arcs_query)
            for arc in arclist:
                arc_int_number = arc['Int_IssueNumber']
                if arc_int_number is None:
                    arc_int_number = 0
                arcs[arc['IssueID']] = {'storyarc': arc['Storyarc'],
                                        'storyarcid': arc['StoryArcID'],
                                        'issuearcid': arc['IssueArcID'],
                                        'comicid': arc['ComicID'],
                                        'comicname': arc['ComicName'],
                                        'issuenumber': arc['IssueNumber'],
                                        'int_issuenumber': arc_int_number,
                                        'releasedate': arc['ReleaseDate'],
                                        'status': arc['Status'],
                                        'dateadded': arc['DateAdded']}

        if mylar.CONFIG.ANNUALS_ON:
            annuals_query = "SELECT ReleaseComicName as ComicName, Issue_Number as Issue_Number, Int_IssueNumber, ReleaseDate, Status, ComicID, IssueID, DateAdded FROM annuals WHERE NOT Deleted AND %s" % statline
            annuals_list = myDB.select(annuals_query)

            issues += annuals_list

        resultlist = issues
        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        filtered = []
        tier = None
        dollars = []
        bills = []
        for row in resultlist:
            matched = False
            if row['Status'] == 'Wanted':
                try:
                    if row['DateAdded'] <= mylar.SEARCH_TIER_DATE:
                        tier = '2nd'
                        if sSearch.lower() in tier.lower():
                            matched = True
                    else:
                        tier = '1st [%s]' % row['DateAdded']
                        if sSearch.lower() in tier.lower():
                            matched = True
                except:
                    tier = '1st [%s]' % row['DateAdded']
                    if sSearch.lower() in tier.lower():
                        matched = True
            else:
                tier = ''

            foundfilter = False
            for filter in filters:
                if filter['name'] == 'StoryArc' or filter['name'] == row['Status'] or all(['Tier1' in filter['name'], row['Status'] == 'Wanted', '1st' in tier]) or all(['Tier2' in filter['name'], row['Status'] == 'Wanted', '2nd' in tier]):
                    if filter['value'] is False:
                        foundfilter = True
                        break

            if foundfilter:
                continue

            if row['ComicName'] is not None and sSearch.lower() in row['ComicName'].lower():
                matched = True
            elif row['Status'] is not None and sSearch.lower() in row['Status'].lower():
                matched = True
            elif row['DateAdded'] is not None and sSearch in row['DateAdded']:
                matched = True
            elif row['ReleaseDate'] is not None and sSearch in row['ReleaseDate']:
                matched = True
            elif tier != '' and sSearch in tier.lower():
                matched = True
            elif row['IssueID'] in arcs:
                if sSearch.lower() in arcs[row['IssueID']]['storyarc'].lower():
                    matched = True
            else:
                if sSearch.lower() in row['Issue_Number']:
                    matched = True

            if matched is True:
                storyarc = None
                storyarcid = None
                issuearcid = None
                if row['IssueID'] in arcs and all([row['IssueID'] not in bills, row['IssueID'] not in dollars]):
                    storyarc = arcs[row['IssueID']]['storyarc']
                    storyarcid = arcs[row['IssueID']]['storyarcid']
                    issuearcid = arcs[row['IssueID']]['issuearcid']
                    bills.append(row['IssueID'])
                    arcs.pop(row['IssueID'])
                    watcharc = "both"
                else:
                    dollars.append(row['IssueID'])
                    watcharc = None

                try:
                    filtered.append([row['ComicName'], row['Issue_Number'], row['ReleaseDate'], row['IssueID'], tier, row['ComicID'], row['Status'], storyarc, storyarcid, issuearcid, watcharc, row['Int_IssueNumber']])
                except Exception as e:
                    #logger.warn('danger Wil Robinson: %s' % (e,))
                    filtered.append([row['ComicName'], row['Issue_Number'], row['ReleaseDate'], row['IssueID'], tier, row['ComicID'], row['Status'], None, None, None, watcharc, row['Int_IssueNumber']])

        if mylar.CONFIG.UPCOMING_STORYARCS is True:
            for key, ark in arcs.items():
                matched = False
                if ark['status'] == 'Wanted':
                    try:
                        if ark['dateadded'] <= mylar.SEARCH_TIER_DATE:
                            tier = '2nd'
                            if sSearch.lower() in tier.lower():
                                matched = True
                        else:
                            tier = '1st [%s]' % ark['dateadded']
                            if sSearch.lower() in tier.lower():
                                matched = True
                    except:
                        tier = '1st [%s]' % ark['dateadded']
                        if sSearch.lower() in tier.lower():
                            matched = True
                else:
                    tier = ''

                foundfilter = False
                for filter in filters:
                    if filter['name'] == 'StoryArc' or filter['name'] == ark['status'] or all(['Tier1' in filter['name'], ark['status'] == 'Wanted', '1st' in tier]) or all(['Tier2' in filter['name'], ark['status'] == 'Wanted', '2nd' in tier]):
                        if filter['value'] is False:
                            foundfilter = True
                            break

                if foundfilter:
                    continue

                if ark['comicname'] is not None and sSearch.lower() in ark['comicname'].lower():
                    matched = True
                elif ark['status'] is not None and sSearch.lower() in ark['status'].lower():
                    matched = True
                elif ark['dateadded'] is not None and sSearch in ark['dateadded']:
                    matched = True
                elif ark['releasedate'] is not None and sSearch in ark['releasedate']:
                    matched = True
                elif tier != '' and sSearch in tier.lower():
                    matched = True
                elif ark['storyarc'] is not None and sSearch.lower() in ark['storyarc'].lower():
                    matched = True
                else:
                    if sSearch.lower() in ark['issuenumber']:
                        matched = True

                if matched is True:
                    filtered.append([ark['comicname'], ark['issuenumber'], ark['releasedate'], key, tier, ark['comicid'], ark['status'], ark['storyarc'], ark['storyarcid'], ark['issuearcid'], "oneoff", ark['int_issuenumber']])

        #logger.fdebug('[%s] one-off arcs: %s' % (len(arcs), arcs,))

        #logger.fdebug('sort_column: %s: sort_directioN: %s' % (iSortCol_0,sSortDir_0))
        sortcolumn = 2 #'releasedate'
        if iSortCol_0 == '1':
            sortcolumn = 0 #'comicame'
        elif iSortCol_0 == '2':
            sortcolumn = 11 #'issuenumber'
        elif iSortCol_0 == '3':
            sortcolumn = 2 #'releasedate'
        elif iSortCol_0 == '4':
            sortcolumn = 6 #'status'
        elif iSortCol_0 == '5':
            sortcolumn = 4 #'tier'

        if sSortDir_0 == 'desc':
            reverse_order = True
        else:
            reverse_order = False

        try:
            final_filtered = sorted(filtered, key=itemgetter(sortcolumn), reverse=reverse_order)
        except Exception as e:
            final_filtered = sorted(filtered, key=itemgetter(0), reverse=reverse_order)

        if iDisplayLength == -1:
            rows = final_filtered
        else:
            rows = final_filtered[iDisplayStart:(iDisplayStart + iDisplayLength)]

        return json.dumps({
            'iTotalDisplayRecords': len(final_filtered),
            'iTotalRecords': len(filtered),
            'aaData': rows
        })

    loadupcoming.exposed = True

    def searchformissing(self, ComicID):
        #search for 'missing' issues for a given series without marking them as Wanted (issues that are in a Skipped or Wanted state).
        myDB = db.DBConnection()
        missing = myDB.select("SELECT a.ComicName, a.ComicYear, b.* FROM comics a join issues b on a.comicid=b.comicid WHERE a.ComicID=? AND (b.Status ='Skipped' or b.Status='Wanted' or b.Status = 'Snatched')", [ComicID])
        if mylar.CONFIG.ANNUALS_ON:
            missing += myDB.select("SELECT a.ComicName, a.ComicYear, b.* FROM comics a join annuals b on a.comicid=b.comicid WHERE a.ComicID=? AND (b.Status ='Skipped' or b.Status='Wanted' or b.Status ='Snatched')", [ComicID])
        missinglist = []
        comicname = None
        comicyear = None
        for mis in missing:
            if comicname is None:
                comicname = mis['ComicName']
                comicyear = mis['ComicYear']
            missinglist.append(mis['IssueID'])
        if missinglist:
            threading.Thread(target=search.searchIssueIDList, args=[missinglist]).start()
            logger.info('[SEARCH-FOR-MISSING] Queued up %s issues to search for' % (len(missinglist)))
            mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': comicname, 'seriesyear': comicyear, 'comicid': ComicID, 'tables': 'None', 'message': 'Successfully queued up %s issues of %s (%s)to search for' % (len(missinglist), comicname, comicyear)}
        else:
            logger.info('[SEARCH-FOR-MISSING] Nothing to queue up')
            mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': None, 'seriesyear': None, 'comicid': ComicID, 'tables': 'None', 'message': 'Nothing to queue up'}

    searchformissing.exposed = True

    def skipped2wanted(self, comicid, fromupdate=None):
        # change all issues for a given ComicID that are Skipped, into Wanted.
        issuestowanted = []
        issuesnumwant = 0
        annsnumwant = 0
        mvvalues = {"Status": "Wanted"}
        myDB = db.DBConnection()
        skipped2 = myDB.select("SELECT issueid, 0 as type from issues WHERE ComicID=? AND Status='Skipped'", [comicid])
        if mylar.CONFIG.ANNUALS_ON:
            skipped2 += myDB.select("SELECT issueid, 1 as type from annuals WHERE ComicID=? AND Status='Skipped'", [comicid])
        for skippy in skipped2:
            mvcontroldict = {"IssueID": skippy['IssueID']}
            if skippy['type'] == 1:
                skip_table = 'annuals'
                annsnumwant +=1
            else:
                skip_table = 'issues'
                issuesnumwant +=1
            myDB.upsert(skip_table, mvvalues, mvcontroldict)
            issuestowanted.append(skippy['issueid'])
        if (issuesnumwant + annsnumwant) > 0:
            num_line = '%s issues' % issuesnumwant
            if annsnumwant > 0:
                num_line += ' and %s annuals' % annsnumwant
            if fromupdate is None:
                logger.info("Marking %s as Wanted" % num_line)
                threading.Thread(target=search.searchIssueIDList, args=[issuestowanted]).start()
                line_message = 'Successfully changed %s from Skipped 2 Wanted' % num_line
                line_status = 'success'
            else:
                logger.info('Marking %s as Wanted' % num_line)
                logger.info('These will be searched for on next Search Scan / Force Check')
                return
        else:
            line_message = 'No issues are marked as Skipped'
            line_status = 'failure'
        return json.dumps({'status': line_status, 'message': line_message})
    skipped2wanted.exposed = True

    def annualDelete(self, comicid, ReleaseComicID=None):
        if 'delete_' in comicid:
            comicid = re.sub('delete_', '', comicid).strip()
        myDB = db.DBConnection()
        if ReleaseComicID is None:
            myDB.action("UPDATE annuals set Deleted=1 WHERE ComicID=?", [comicid])
            logger.fdebug("Deleted all annuals from DB for ComicID of " + str(comicid))
        else:
            myDB.action("UPDATE annuals set Deleted=1 WHERE ReleaseComicID=?", [ReleaseComicID])
            logger.fdebug("Deleted selected annual from DB with a ComicID of " + str(ReleaseComicID))
        return json.dumps({'status': 'success', 'message': 'Successfully removed annuals'})

    annualDelete.exposed = True

    def ddl_requeue(self, mode, id=None, issueid=None):
        logger.info('id: %s / mode: %s / issueid: %s' % (id, mode, issueid))
        myDB = db.DBConnection()
        if mode == 'clear_queue':
            chk = myDB.selectone("SELECT count(*) AS count FROM ddl_info WHERE status = 'Queued'").fetchone()
            countchk = 0
            if chk:
                countchk = chk['count']

            if countchk == 0:
                return json.dumps({'status': True, 'message': 'Queue already cleared - there was nothing to clear from the Queue'})

            myDB.action("DELETE FROM ddl_info WHERE status = 'Queued'")
            return json.dumps({'status': True, 'message': 'Successfully cleared %s items from the Queue' % countchk})

        if id is None:
            items = myDB.select("SELECT * FROM ddl_info WHERE status = 'Queued' ORDER BY updated_date DESC")
        else:
            oneitem = myDB.selectone("SELECT * FROM DDL_INFO WHERE ID=?", [id]).fetchone()
            items = [oneitem]

        itemlist = []
        for x in items:
            OneOff = False
            comic = myDB.selectone(
                "SELECT * from comics WHERE ComicID=? AND ComicName != 'None'",
                [x['comicid']],
            ).fetchone()
            if comic is None:
                comic = myDB.selectone(
                    "SELECT * from storyarcs WHERE IssueID=?",
                    [x['issueid']],
                ).fetchone()
                if comic is None:
                    OneOff = True

            itemlist.append({'link': x['link'],
                             'mainlink': x['mainlink'],
                             'series': x['series'],
                             'status': x['status'],
                             'year': x['year'],
                             'size': x['size'],
                             'link_type': x['link_type'],
                             'pack': x['pack'],
                             'oneoff': OneOff,
                             'filename': x['filename'],
                             'remote_filesize': x['remote_filesize'],
                             'comicid': x['comicid'],
                             'issueid': x['issueid'],
                             'site': x['site'],
                             'id': x['id']})

        if itemlist is not None:
            for item in itemlist:
                seriesname = item['series']
                seriessize = item['size']
                if any(
                        [
                            item['link_type'] is None,
                            item['link_type'] == 'GC-Main',
                            item['link_type'] == 'GC-Mirror'
                        ]
                    ) and all(
                        [
                            mylar.CONFIG.DDL_AUTORESUME is True,
                            mode == 'resume',
                            item['status'] != 'Completed'
                        ]
                    ):
                    logger.fdebug('Attempting to resume....')
                    try:
                        filesize = os.stat(os.path.join(mylar.CONFIG.DDL_LOCATION, item['filename'])).st_size
                    except Exception as e:
                        logger.warn('[DDL-REQUEUE] Unable to retrieve previous filesize (file was deleted/moved maybe).'
                                    ' Resume unavailable - will restart download.')
                        filesize = 0
                    logger.fdebug('resume set to resume at: %s bytes' % filesize)
                    resume = filesize
                elif mode == 'abort':
                    myDB.upsert("ddl_info", {'Status': 'Failed'}, {'id': id}) #DELETE FROM ddl_info where ID=?', [id])
                    continue
                elif mode == 'remove':
                    myDB.action('DELETE FROM ddl_info where ID=?', [id])
                    continue
                else:
                    resume = None
                mylar.DDL_QUEUE.put({'link': item['link'],
                                     'mainlink': item['mainlink'],
                                     'series': item['series'],
                                     'year': item['year'],
                                     'size': item['size'],
                                     'comicid': item['comicid'],
                                     'issueid': item['issueid'],
                                     'oneoff': item['oneoff'],
                                     'id': item['id'],
                                     'link_type': item['link_type'],
                                     'filename': item['filename'],
                                     'comicinfo': None,
                                     'packinfo': None,
                                     'site': item['site'],
                                     'remote_filesize': item['remote_filesize'],
                                     'resume': resume})

                linemessage = '%s successful for %s' % (mode, item['series'])

            if mode == 'restart_queue':
                logger.info('[DDL-RESTART-QUEUE] DDL Queue successfully restarted. Put %s items back into the queue for downloading..' % len(itemlist))
                linemessage = 'Successfully restarted Queue'
            elif mode == 'restart':
                logger.info('[DDL-RESTART] Successfully restarted %s [%s] for downloading..' % (seriesname, seriessize))
                linemessage = 'Successfully restarted %s [%s]' % (seriesname, seriessize)
            elif mode == 'requeue':
                logger.info('[DDL-REQUEUE] Successfully requeued %s [%s] for downloading..' % (seriesname, seriessize))
                linemessage = 'Successfully requeued %s [%s]' % (seriesname, seriessize)
            elif mode == 'abort':
                logger.info('[DDL-ABORT] Successfully aborted downloading of %s [%s]..' % (seriesname, seriessize))
                linemessage = 'Successfully aborted downloading %s [%s]' % (seriesname, seriessize)
            elif mode == 'remove':
                logger.info('[DDL-REMOVE] Successfully removed %s [%s]..' % (seriesname, seriessize))
                linemessage = 'Successfully removed %s [%s] from queue/history' % (seriesname, seriessize)
        else:
            linemessage = "No items to requeue"
        return json.dumps({'status': True, 'message': linemessage})
    ddl_requeue.exposed = True

    def queueManage(self): # **args):
        myDB = db.DBConnection()

        resultlist = 'There are currently no items waiting in the Direct Download (DDL) Queue for processing.'
        s_info = myDB.select("SELECT a.ComicName, a.ComicVersion, a.ComicID, a.ComicYear, b.Issue_Number, b.IssueID, c.series as filename, c.size, c.status, c.id, c.updated_date, c.issues, c.year, c.pack FROM comics as a INNER JOIN issues as b ON a.ComicID = b.ComicID INNER JOIN ddl_info as c ON b.IssueID = c.IssueID") # WHERE c.status != 'Downloading'")
        o_info = myDB.select("Select a.ComicName, b.Issue_Number, a.IssueID, a.ComicID, c.series as filename, c.size, c.status, c.id, c.updated_date, c.issues, c.year, c.pack from oneoffhistory a join snatched b on a.issueid=b.issueid join ddl_info c on b.issueid=c.issueid where b.provider like 'DDL%'")
        tmp_list = {}
        if s_info:
            resultlist = []
            for si in s_info:
                if si['issues'] is None:
                    issue = si['Issue_Number']
                    year = si['ComicYear']
                    if issue is not None:
                        issue = '#%s' % issue
                else:
                    year = si['year']
                    issue = '#%s' % si['issues']

                if si['pack']:
                    series = si['filename']
                else:
                    series = si['ComicName']

                if si['status'] == 'Completed':
                    si_status = '100%'
                else:
                    si_status = ''
                resultlist.append({'series':       series,
                                   'issue':        issue,
                                   'id':           si['id'],
                                   'volume':       si['ComicVersion'],
                                   'year':         year,
                                   'size':         si['size'].strip(),
                                   'comicid':      si['ComicID'],
                                   'issueid':      si['IssueID'],
                                   'status':       si['status'],
                                   'updated_date': si['updated_date'],
                                   'progress':     si_status})
                tmp_list[si['id']] = {
                                     'comicid': si['comicid'],
                                     'issueid': si['issueid'],
                                     'updated_date': si['updated_date']
                                     }
            #logger.info('s_info: %s' % (resultlist))
        if o_info:
            if type(resultlist) is str:
                resultlist = []

            for oi in o_info:
                if oi['id'] in tmp_list:
                    continue

                if oi['issues'] is None:
                    issue = oi['Issue_Number']
                    year = oi['year']
                    if issue is not None:
                        issue = '#%s' % issue
                else:
                    year = oi['year']
                    issue = '#%s' % oi['issues']

                if oi['pack']:
                    series = oi['filename']
                else:
                    series = oi['ComicName']

                if oi['status'] == 'Completed':
                    oi_status = '100%'
                else:
                    oi_status = ''

                resultlist.append({'series':       series,
                                   'issue':        issue,
                                   'id':           oi['id'],
                                   'volume':       None,
                                   'year':         year,
                                   'size':         oi['size'].strip(),
                                   'comicid':      oi['ComicID'],
                                   'issueid':      oi['IssueID'],
                                   'status':       oi['status'],
                                   'updated_date': oi['updated_date'],
                                   'progress':     oi_status})

            #logger.info('o_info: %s' % (resultlist))

        return serve_template(templatename="queue_management.html", title="Queue Management", resultlist=resultlist) #activelist=activelist, resultlist=resultlist)
    queueManage.exposed = True

    def queueManageIt(self, iDisplayStart=0, iDisplayLength=100, iSortCol_0=5, sSortDir_0="desc", sSearch="", **kwargs):
        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        filtered = []

        myDB = db.DBConnection()
        resultlist = 'There are currently no items waiting in the Direct Download (DDL) Queue for processing.'
        s_info = myDB.select("SELECT a.ComicName, a.ComicVersion, a.ComicID, a.ComicYear, b.Issue_Number, b.IssueID, c.series as filename, c.size, c.status, c.id, c.updated_date, c.issues, c.year, c.pack, c.link_type FROM comics as a INNER JOIN issues as b ON a.ComicID = b.ComicID INNER JOIN ddl_info as c ON b.IssueID = c.IssueID") # WHERE c.status != 'Downloading'")
        o_info = myDB.select("Select a.ComicName, b.Issue_Number, a.IssueID, a.ComicID, c.series as filename, c.size, c.status, c.id, c.updated_date, c.issues, c.year, c.pack, c.link_type from oneoffhistory a join snatched b on a.issueid=b.issueid join ddl_info c on b.issueid=c.issueid where b.provider like 'DDL%'")
        tmp_list = {}
        if s_info:
            resultlist = []
            for si in s_info:
                if si['issues'] is None:
                    issue = si['Issue_Number']
                    year = si['ComicYear']
                    if issue is not None:
                        issue = '#%s' % issue
                else:
                    year = si['year']
                    issue = '#%s' % si['issues']

                if si['status'] == 'Completed':
                    si_status = '100%'
                else:
                    si_status = ''

                if si['pack']:
                    if si['year'] is not None and si['year'] not in si['filename']:
                        series = '%s (%s)' % (si['filename'], si['year'])
                    else:
                        series = si['filename']
                else:
                    if issue is not None:
                        if si['ComicVersion'] is not None:
                            series = '%s %s %s (%s)' % (si['ComicName'], si['ComicVersion'], issue, year)
                        else:
                            series = '%s %s (%s)' % (si['ComicName'], issue, year)
                    else:
                        if si['ComicVersion'] is not None:
                            series = '%s %s (%s)' % (si['ComicName'], si['ComicVersion'], year)
                        else:
                            series = '%s (%s)' % (si['ComicName'], year)

                resultlist.append({'series':       series, #i['ComicName'],
                                   'issue':        issue,
                                   'queueid':      si['id'],
                                   'linktype':     si['link_type'],
                                   'volume':       si['ComicVersion'],
                                   'year':         year,
                                   'size':         si['size'].strip(),
                                   'comicid':      si['ComicID'],
                                   'issueid':      si['IssueID'],
                                   'status':       si['status'],
                                   'updated_date': si['updated_date'],
                                   'progress':     si_status})
                tmp_list[si['id']] = {
                                     'comicid': si['comicid'],
                                     'issueid': si['issueid'],
                                     'updated_date': si['updated_date']
                                     }
            #logger.info('s_info: %s' % (resultlist))
        if o_info:
            if type(resultlist) is str:
                resultlist = []

            for oi in o_info:
                if oi['id'] in tmp_list:
                    #logger.fdebug('duplicate entry: %s' % (oi,))
                    continue

                if oi['issues'] is None:
                    issue = oi['Issue_Number']
                    year = oi['year']
                    if issue is not None:
                        issue = '#%s' % issue
                else:
                    year = oi['year']
                    issue = '#%s' % oi['issues']

                if oi['status'] == 'Completed':
                    oi_status = '100%'
                else:
                    oi_status = ''

                if oi['pack']:
                    if oi['year'] not in oi['filename']:
                        series = '%s (%s)' % (oi['filename'], oi['year'])
                    else:
                        series = oi['filename']
                else:
                    if issue is not None:
                        series = '%s %s (%s)' % (oi['ComicName'], issue, year)
                    else:
                        series = '%s (%s)' % (oi['ComicName'], year)

                resultlist.append({'series':       series,
                                   'issue':        issue,
                                   'queueid':      oi['id'],
                                   'volume':       None,
                                   'linktype':     oi['link_type'],
                                   'year':         year,
                                   'size':         oi['size'].strip(),
                                   'comicid':      oi['ComicID'],
                                   'issueid':      oi['IssueID'],
                                   'status':       oi['status'],
                                   'updated_date': oi['updated_date'],
                                   'progress':     oi_status})

            #logger.info('o_info: %s' % (resultlist))

        if sSearch == "" or sSearch == None:
            filtered = resultlist[::]
        else:
            filtered = [row for row in resultlist if any([sSearch.lower() in row['series'].lower(), sSearch.lower() in row['status'].lower()])]
        sortcolumn = 'series'
        if iSortCol_0 == '1':
            sortcolumn = 'series'
        elif iSortCol_0 == '2':
            sortcolumn = 'size'
        elif iSortCol_0 == '3':
            sortcolumn = 'progress'
        elif iSortCol_0 == '4':
            sortcolumn = 'status'
        elif iSortCol_0 == '5':
            sortcolumn = 'updated_date'
        filtered.sort(key=lambda x: (x[sortcolumn] is None, x[sortcolumn] == '', x[sortcolumn]), reverse=sSortDir_0 == "desc")
        if iDisplayLength != -1:
            rows = filtered[iDisplayStart:(iDisplayStart + iDisplayLength)]
        else:
            rows = filtered
        rows = [[row['series'], row['size'], row['progress'], row['status'], row['updated_date'], row['queueid'], row['issueid'], row['comicid'], row['linktype']] for row in rows]
        #rows = [{'comicid': row['comicid'], 'series': row['series'], 'size': row['size'], 'progress': row['progress'], 'status': row['status'], 'updated_date': row['updated_date']} for row in rows]
        #logger.info('rows: %s' % rows)
        return json.dumps({
            'iTotalDisplayRecords': len(filtered),
            'iTotalRecords': len(resultlist),
            'aaData': rows,
        })

    queueManageIt.exposed = True

    def previewRename(self, **args): #comicid=None, comicidlist=None):
        file_format = mylar.CONFIG.FILE_FORMAT
        myDB = db.DBConnection()
        resultlist = []
        for k,v in list(args.items()):
            if any([k == 'x', k == 'y']):
                continue
            elif 'file_format' in k:
                file_format = str(v)
            elif 'comicid' in k:
                if type(v) is list:
                    comicid = str(' '.join(v))
                elif type(v) is str:
                    comicid = re.sub('[\]\[\']', '', v) #v.decode('utf-8').encode('ascii')).strip()
                else:
                    comicid = v

        if comicid is not None and type(comicid) is not list:
            comicidlist = []
            comicidlist.append(comicid)
        for cid in comicidlist:
            comic = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [cid]).fetchone()
            comicdir = comic['ComicLocation']
            comicname = comic['ComicName']
            issuelist = myDB.select("SELECT * FROM issues WHERE ComicID=? AND Location is not NULL ORDER BY ReleaseDate", [str(cid)])
            if issuelist:
                for issue in issuelist:
                    if 'annual' in issue['Location'].lower():
                        annualize = 'yes'
                    else:
                        annualize = None
                    from . import filers
                    rniss = filers.FileHandlers(ComicID=str(cid), IssueID=issue['IssueID'])
                    renameiss = rniss.rename_file(issue['Location'], annualize=annualize, file_format=file_format)
                    #renameiss = helpers.rename_param(comicid, comicname, issue['Issue_Number'], issue['Location'], comicyear=None, issueid=issue['IssueID'], annualize=annualize)
                    resultlist.append({'issueid':    renameiss['issueid'],
                                       'comicid':    renameiss['comicid'],
                                       'original':   issue['Location'],
                                       'new':        renameiss['nfilename']})

            logger.info('resultlist: %s' % resultlist)
        return serve_template(templatename="previewrename.html", title="Preview Renamer", resultlist=resultlist, file_format=file_format, comicid=comicidlist)
    previewRename.exposed = True

    def manualRename(self, comicid):
        if mylar.CONFIG.FILE_FORMAT == '':
            logger.error("You haven't specified a File Format in Configuration/Advanced")
            logger.error("Cannot rename files.")
            return

        if type(comicid) is not str:
            comiclist = comicid
        else:
            comiclist = []
            comiclist.append(comicid)
        myDB = db.DBConnection()
        for cid in comiclist:
            filefind = 0
            comic = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [cid]).fetchone()
            comicdir = comic['ComicLocation']
            comicname = comic['ComicName']
            comicyear = comic['ComicYear']
            extensions = ('.cbr', '.cbz', '.cb7')
            issues = myDB.select("SELECT * FROM issues WHERE ComicID=?", [cid])
            if mylar.CONFIG.ANNUALS_ON:
                issues += myDB.select("SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted", [cid])
            try:
                if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                    if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comicdir))):
                        secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(comicdir))
                    else:
                        ff = mylar.filers.FileHandlers(ComicID=cid)
                        secondary_folders = ff.secondary_folders(comicdir)
            except:
                pass

            for root, dirnames, filenames in os.walk(comicdir):
                for filename in filenames:
                    if filename.lower().endswith(extensions):
                        #logger.info("filename being checked is : " + str(filename))
                        for issue in issues:
                            if issue['Location'] == filename:
                                #logger.error("matched " + str(filename) + " to DB file " + str(issue['Location']))
                                if 'annual' in issue['Location'].lower():
                                    annualize = 'yes'
                                else:
                                    annualize = None
                                renameiss = helpers.rename_param(cid, comicname, issue['Issue_Number'], filename, comicyear=comicyear, issueid=issue['IssueID'], annualize=annualize)
                                nfilename = renameiss['nfilename']
                                srciss = os.path.join(comicdir, filename)
                                if filename != nfilename:
                                    logger.info('Renaming ' + filename + ' ... to ... ' + renameiss['nfilename'])
                                    try:
                                        shutil.move(srciss, renameiss['destination_dir'])
                                    except (OSError, IOError):
                                        logger.error('Failed to move files - check directories and manually re-run.')
                                        return
                                    filefind+=1
                                else:
                                    logger.info('Not renaming ' + filename + ' as it is in desired format already.')
                                #continue
            logger.info('I have renamed ' + str(filefind) + ' issues of ' + comicname)
            updater.forceRescan(cid)
        if len(comiclist) > 1:
            logger.info('[RENAMER] %s series have been renamed.' % len(comiclist))
        return json.dumps({'status': 'success'})
    manualRename.exposed = True

    def searchScan(self, name):
        return serve_template(templatename="searchfix.html", title="Manage", name=name)
    searchScan.exposed = True

    def manage(self):
        scan_info = {'autoadd': helpers.checked(mylar.CONFIG.ADD_COMICS),
                     'path': mylar.CONFIG.COMIC_DIR,
                     'imp_move': helpers.checked(mylar.CONFIG.IMP_MOVE),
                     'imp_rename': helpers.checked(mylar.CONFIG.IMP_RENAME),
                     'imp_metadata': helpers.checked(mylar.CONFIG.IMP_METADATA),
                     'imp_paths': helpers.checked(mylar.CONFIG.IMP_PATHS),
                     'imp_seriesfolders': helpers.checked(mylar.CONFIG.IMP_SERIESFOLDERS)}

        mylarRoot = mylar.CONFIG.DESTINATION_DIR
        myDB = db.DBConnection()
        jobresults = myDB.select('SELECT DISTINCT * FROM jobhistory')
        if jobresults is not None:
            tmp = []
            for jb in jobresults:
                if jb['prev_run_datetime'] is not None:
                    try:
                        pr = (datetime.datetime.strptime(jb['prev_run_datetime'][:19], '%Y-%m-%d %H:%M:%S') - datetime.datetime.utcfromtimestamp(0)).total_seconds()
                    except ValueError:
                        pr = (datetime.datetime.strptime(jb['prev_run_datetime'], '%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.utcfromtimestamp(0)).total_seconds()
                    prev_run = datetime.datetime.fromtimestamp(pr)
                else:
                    prev_run = None
                if jb['next_run_datetime'] is not None:
                    try:
                        nr = (datetime.datetime.strptime(jb['next_run_datetime'][:19], '%Y-%m-%d %H:%M:%S') - datetime.datetime.utcfromtimestamp(0)).total_seconds()
                    except ValueError:
                        nr = (datetime.datetime.strptime(jb['next_run_datetime'], '%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.utcfromtimestamp(0)).total_seconds()
                    next_run = datetime.datetime.fromtimestamp(nr)
                else:
                    next_run = None
                if 'rss' in jb['JobName'].lower():
                    #logger.fdebug('rss - job update. RSS_STATUS: %s / db: %s' % (mylar.RSS_STATUS, jb['Status']))
                    status = mylar.RSS_STATUS
                    interval = str(mylar.CONFIG.RSS_CHECKINTERVAL) + ' mins'
                elif 'weekly' in jb['JobName'].lower():
                    #logger.fdebug('weekly - job update. WEEKLY_STATUS: %s / db: %s' % (mylar.WEEKLY_STATUS, jb['Status']))
                    status = mylar.WEEKLY_STATUS
                    if mylar.CONFIG.ALT_PULL == 2:
                        interval = '4 hrs'
                    else:
                        interval = '24 hrs'
                elif 'search' in jb['JobName'].lower():
                    #logger.fdebug('search - job update. SEARCH_STATUS: %s / db: %s' % (mylar.SEARCH_STATUS, jb['Status']))
                    status = mylar.SEARCH_STATUS
                    interval = str(mylar.CONFIG.SEARCH_INTERVAL) + ' mins'
                elif 'updater' in jb['JobName'].lower():
                    #logger.fdebug('updater - job update. UPDATER_STATUS: %s / db: %s' % (mylar.UPDATER_STATUS, jb['Status']))
                    status = mylar.UPDATER_STATUS
                    interval = str(int(mylar.DBUPDATE_INTERVAL)) + ' mins'
                elif 'folder' in jb['JobName'].lower():
                    #logger.fdebug('monitor - job update. MONITOR_STATUS: %s / db: %s' % (mylar.MONITOR_STATUS, jb['Status']))
                    status = mylar.MONITOR_STATUS
                    interval = str(mylar.CONFIG.DOWNLOAD_SCAN_INTERVAL) + ' mins'
                elif 'version' in jb['JobName'].lower():
                    #logger.fdebug('version - job update. VERSION_STATUS: %s / db: %s' % (mylar.VERSION_STATUS, jb['Status']))
                    status = mylar.VERSION_STATUS
                    interval = str(mylar.CONFIG.CHECK_GITHUB_INTERVAL) + ' mins'

                if prev_run is None:
                    prev_run = '-----'
                if any([next_run is None, status == 'Paused']):
                    next_run = '-----'

                tmp.append({'prev_run_datetime':  prev_run,
                            'next_run_datetime': next_run,
                            'interval': interval,
                            'jobname': jb['JobName'],
                            'status': status})
            jobresults = tmp
        queues = helpers.queue_info()
        return serve_template(templatename="manage.html", title="Manage", mylarRoot=mylarRoot, jobs=jobresults, queues=queues, scan_info=scan_info)
    manage.exposed = True

    def jobmanage(self, job, mode):
        #logger.fdebug('%s : %s' % (job, mode))
        jobid = None
        job_id_map = {'DB Updater': 'dbupdater', 'Auto-Search': 'search', 'RSS Feeds': 'rss', 'Weekly Pullist': 'weekly', 'Check Version': 'version', 'Folder Monitor': 'monitor'}
        for k,v in job_id_map.items():
            if k == job:
                jobid = v
                break
        #logger.fdebug('jobid: %s' % jobid)
        if jobid is not None:
            myDB = db.DBConnection()
            if mode == 'pause':
                try:
                    mylar.SCHED.pause_job(jobid)
                except:
                    pass
                logger.info('[%s] Paused scheduled runtime.' % job)
                ctrl = {'JobName': job}
                val = {'Status': 'Paused'}
                if jobid == 'rss':
                    mylar.CONFIG.ENABLE_RSS = False
                    mylar.RSS_STATUS = 'Paused'
                elif jobid == 'monitor':
                    mylar.CONFIG.ENABLE_CHECK_FOLDER = False
                    mylar.MONITOR_STATUS = 'Paused'
                elif jobid == 'version':
                    mylar.CONFIG.CHECK_GITHUB = False
                    mylar.VERSION_STATUS = 'Paused'
                elif jobid == 'updater':
                    mylar.UPDATER_STATUS = 'Paused'
                elif jobid == 'search':
                    mylar.SEARCH_STATUS = 'Paused'
                elif jobid == 'weekly':
                    mylar.WEEKLY_STATUS = 'Paused'
                myDB.upsert('jobhistory', val, ctrl)
            elif mode == 'resume':
                try:
                    mylar.SCHED.resume_job(jobid)
                except:
                     pass
                logger.info('[%s] Resumed scheduled runtime.' % job)
                ctrl = {'JobName': job}
                val = {'Status': 'Waiting'}
                myDB.upsert('jobhistory', val, ctrl)
                if jobid == 'rss':
                    mylar.CONFIG.ENABLE_RSS = True
                    mylar.RSS_STATUS = 'Waiting'
                elif jobid == 'monitor':
                    mylar.CONFIG.ENABLE_CHECK_FOLDER = True
                    mylar.MONITOR_STATUS = 'Waiting'
                elif jobid == 'version':
                    mylar.CONFIG.CHECK_GITHUB = True
                    mylar.VERSION_STATUS = 'Waiting'
                elif jobid == 'updater':
                    mylar.UPDATER_STATUS = 'Waiting'
                elif jobid == 'search':
                    mylar.SEARCH_STATUS = 'Waiting'
                elif jobid == 'weekly':
                    mylar.WEEKLY_STATUS = 'Waiting'

            helpers.job_management(write=True)
        else:
            logger.warn('%s cannot be matched against any scheduled jobs - maybe you should restart?' % job)
    jobmanage.exposed = True

    def schedulerForceCheck(self, jobid):
        from apscheduler.triggers.date import DateTrigger
        for jb in mylar.SCHED.get_jobs():
            if jobid.lower() in str(jb).lower():
                logger.info('[%s] Now force submitting job for jobid %s' % (jb, jobid))
                if any([jobid == 'rss', jobid == 'weekly', jobid =='search', jobid == 'version', jobid == 'updater', jobid == 'monitor']):
                    if jobid == 'rss':
                        mylar.FORCE_STATUS['rss'] = mylar.RSS_STATUS
                        #mylar.RSS_STATUS = 'Running'
                    elif jobid == 'weekly':
                        mylar.FORCE_STATUS['weekly'] = mylar.WEEKLY_STATUS
                        #mylar.WEEKLY_STATUS = 'Running'
                    elif jobid == 'search':
                        mylar.FORCE_STATUS['search'] = mylar.SEARCH_STATUS
                        #mylar.SEARCH_STATUS = 'Running'
                    elif jobid == 'version':
                        mylar.FORCE_STATUS['version'] = mylar.VERSION_STATUS
                        #mylar.VERSION_STATUS = 'Running'
                    elif jobid == 'updater':
                        mylar.FORCE_STATUS['updater'] = mylar.UPDATER_STATUS
                        #mylar.UPDATER_STATUS = 'Running'
                    elif jobid == 'monitor':
                        mylar.FORCE_STATUS['monitor'] = mylar.MONITOR_STATUS
                        #mylar.MONITOR_STATUS = 'Running'
                    jb.modify(next_run_time=datetime.datetime.utcnow())
                    break
    schedulerForceCheck.exposed = True

    def manageComics(self):
        comics = helpers.havetotals()
        return serve_template(templatename="managecomics.html", title="Manage Comics", comics=comics)
    manageComics.exposed = True

    def manageIssues(self, **kwargs):
        status = kwargs['status']
        myDB = db.DBConnection()
        if mylar.CONFIG.ANNUALS_ON:
            issues = myDB.select("SELECT * from issues WHERE Status=? AND ComicName NOT LIKE '%Annual%'", [status])
            issues += myDB.select("SELECT * from annuals WHERE Status=? AND NOT Deleted", [status])
        else:
            issues = myDB.select("SELECT * from issues WHERE Status=?", [status])
        return serve_template(templatename="manageissues.html", title="Manage " + str(status) + " Issues", issues=issues, status=status)
    manageIssues.exposed = True

    def manageFailed(self):
        results = []
        myDB = db.DBConnection()
        failedlist = myDB.select('SELECT * from Failed')
        for f in failedlist:
            if f['Provider'] == 'Public Torrents':
                link = helpers.torrent_create(f['Provider'], f['ID'])
            else:
                link = f['ID']

            if f['DateFailed'] is None:
                datefailed = '0000-00-0000'
            else:
                datefailed = f['DateFailed']

            results.append({"Series":        f['ComicName'],
                            "ComicID":       f['ComicID'],
                            "IssueID":       f['IssueID'],
                            "Issue_Number":  f['Issue_Number'],
                            "Provider":      f['Provider'],
                            "Link":          link,
                            "ID":            f['ID'],
                            "FileName":      f['NZBName'],
                            "DateFailed":    datefailed})

        return serve_template(templatename="managefailed.html", title="Failed DB Management", failed=results)
    manageFailed.exposed = True

    def cblimport(self):
        return serve_template(templatename="cblimport.html", title="CBL Import")
    cblimport.exposed = True

    def flushImports(self):
        myDB = db.DBConnection()
        myDB.action('DELETE from importresults')
        logger.info("Flushing all Import Results and clearing the tables")
    flushImports.exposed = True

    def markImports(self, action=None, **args):
        import unicodedata
        myDB = db.DBConnection()
        comicstoimport = []
        if action == 'massimport':
            logger.info('Initiating mass import.')
            cnames = myDB.select("SELECT ComicName, ComicID, Volume, DynamicName from importresults WHERE Status='Not Imported' GROUP BY DynamicName, Volume")
            for cname in cnames:
                if cname['ComicID']:
                    comicid = cname['ComicID']
                else:
                    comicid = None
                try:
                    comicstoimport.append({'ComicName':   unicodedata.normalize('NFKD', cname['ComicName']), #.encode('utf-8', 'ignore').decode('utf-8', 'ignore'),
                                           'DynamicName': cname['DynamicName'],
                                           'Volume':      cname['Volume'],
                                           'ComicID':     comicid})
                except Exception as e:
                    logger.warn('[ERROR] There was a problem attempting to queue %s %s [%s] to import (ignoring): %s' % (cname['ComicName'],cname['Volume'],comicid, e))

            logger.info(str(len(comicstoimport)) + ' series will be attempted to be imported.')
        else:
            if action == 'importselected':
                logger.info('importing selected series.')
                for k,v in list(args.items()):
                    #k = Comicname[Volume]|ComicID
                    #v = DynamicName
                    Volst = k.find('[')
                    comicid_st = k.find('|')
                    if comicid_st == -1:
                        comicid = None
                        volume = re.sub('[\[\]]', '', k[Volst:]).strip()
                    else:
                        comicid = k[comicid_st+1:]
                        if comicid == 'None':
                            comicid = None
                        volume = re.sub('[\[\]]', '', k[Volst:comicid_st]).strip()
                    ComicName = k[:Volst].strip()
                    DynamicName = v
                    cid = ComicName
                    comicstoimport.append({'ComicName': cid,
                                           'DynamicName': DynamicName,
                                           'Volume':    volume,
                                           'ComicID':   comicid})

            elif action == 'removeimport':
                for k,v in list(args.items()):
                    Volst = k.find('[')
                    comicid_st = k.find('|')
                    if comicid_st == -1:
                        comicid = None
                        volume = re.sub('[\[\]]', '', k[Volst:]).strip()
                    else:
                        comicid = k[comicid_st+1:]
                        if comicid == 'None':
                            comicid = None
                        volume = re.sub('[\[\]]', '', k[Volst:comicid_st]).strip()
                    ComicName = k[:Volst].strip()
                    DynamicName = v
                    if volume is None or volume == 'None':
                        logger.info('Removing ' + ComicName + ' from the Import list')
                        myDB.action("DELETE from importresults WHERE DynamicName=? AND (Volume is NULL OR Volume='None')", [DynamicName])
                    else:
                        logger.info('Removing ' + ComicName + ' [' + str(volume) + '] from the Import list')
                        myDB.action('DELETE from importresults WHERE DynamicName=? AND Volume=?', [DynamicName, volume])

            if len(comicstoimport) > 0:
                logger.info('Initiating selected import mode for ' + str(len(comicstoimport)) + ' series.')

        if len(comicstoimport) > 0:
            logger.debug('The following series will now be attempted to be imported: %s' % comicstoimport)
            threading.Thread(target=self.preSearchit, args=[None, comicstoimport, len(comicstoimport)]).start()
        raise cherrypy.HTTPRedirect("importResults")

    markImports.exposed = True

    def markComics(self, action=None, **args):
        myDB = db.DBConnection()
        comicsToAdd = []
        clist = []
        for k,v in list(args.items()):
            if k == 'manage_comic_length':
                continue
            #k = Comicname[ComicYear]
            #v = ComicID
            comyr = k.find('[')
            ComicYear = re.sub('[\[\]]', '', k[comyr:]).strip()
            ComicName = k[:comyr].strip()
            if isinstance(v, list):
                #because multiple items can have the same comicname & year, we need to make sure they're all unique entries
                for x in v:
                    clist.append({'ComicName':  ComicName,
                                  'ComicYear':  ComicYear,
                                  'ComicID':    x})
            else:
                clist.append({'ComicName':  ComicName,
                              'ComicYear':  ComicYear,
                              'ComicID':    v})

        for cl in clist:
            if action == 'delete':
                logger.info('[MANAGE COMICS][DELETION] Now deleting ' + cl['ComicName'] + ' (' + str(cl['ComicYear']) + ') [' + str(cl['ComicID']) + '] form the DB.')
                myDB.action('DELETE from comics WHERE ComicID=?', [cl['ComicID']])
                myDB.action('DELETE from issues WHERE ComicID=?', [cl['ComicID']])
                if mylar.CONFIG.ANNUALS_ON:
                    myDB.action('DELETE from annuals WHERE ComicID=?', [cl['ComicID']])
                logger.info('[MANAGE COMICS][DELETION] Successfully deleted ' + cl['ComicName'] + '(' + str(cl['ComicYear']) + ')')
            elif action == 'pause':
                controlValueDict = {'ComicID': cl['ComicID']}
                newValueDict = {'Status': 'Paused'}
                myDB.upsert("comics", newValueDict, controlValueDict)
                logger.info('[MANAGE COMICS][PAUSE] ' + cl['ComicName'] + ' has now been put into a Paused State.')
            elif action == 'resume':
                controlValueDict = {'ComicID': cl['ComicID']}
                newValueDict = {'Status': 'Active'}
                myDB.upsert("comics", newValueDict, controlValueDict)
                logger.info('[MANAGE COMICS][RESUME] ' + cl['ComicName'] + ' has now been put into a Resumed State.')
            elif action == 'recheck' or action == 'metatag':
                comicsToAdd.append({'ComicID':   cl['ComicID'],
                                    'ComicName': cl['ComicName'],
                                    'ComicYear': cl['ComicYear']})
            else:
                comicsToAdd.append(cl['ComicID'])

        if len(comicsToAdd) > 0:
            if action == 'recheck':
                logger.info('[MANAGE COMICS][RECHECK-FILES] Rechecking Files for  ' + str(len(comicsToAdd)) + ' series')
                threading.Thread(target=self.forceRescan, args=[comicsToAdd,True,'recheck']).start()
            elif action == 'metatag':
                logger.info('[MANAGE COMICS][MASS METATAGGING] Now Metatagging Files for  ' + str(len(comicsToAdd)) + ' series')
                threading.Thread(target=self.forceRescan, args=[comicsToAdd,True,'metatag']).start()
            elif action == 'rename':
                logger.info('[MANAGE COMICS][MASS RENAMING] Now Renaming Files for  ' + str(len(comicsToAdd)) + ' series')
                threading.Thread(target=self.manualRename, args=[comicsToAdd]).start()
            else:
                logger.info('[MANAGE COMICS][REFRESH] Refreshing ' + str(len(comicsToAdd)) + ' series')
                threading.Thread(target=updater.dbUpdate, args=[comicsToAdd]).start()
    markComics.exposed = True

    def forceUpdate(self):
        from mylar import updater
        threading.Thread(target=updater.dbUpdate).start()
        raise cherrypy.HTTPRedirect("home")
    forceUpdate.exposed = True

    def forceSearch(self, issueIds = None):
        #from mylar import search
        #threading.Thread(target=search.searchforissue).start()
        #raise cherrypy.HTTPRedirect("home")
        if issueIds is None:
            self.schedulerForceCheck(jobid='search')
        else:
            myDB = db.DBConnection()

            if not isinstance(issueIds, list):
                issueIds = [issueIds]

            for issueId in issueIds:
                issue_data = myDB.selectone("SELECT C.Type, C.ComicYear, I.ComicName, I.Issue_Number, I.ComicID, I.IssueID FROM comics as C INNER JOIN issues as I on C.ComicID = I.ComicID WHERE I.IssueID=?", [issueId]).fetchone()
                passInfo = {'issueid': issueId,
                            'comicname': issue_data['ComicName'],
                            'seriesyear': issue_data['ComicYear'],
                            'comicid': issue_data['ComicID'],
                            'issuenumber': issue_data['Issue_Number'],
                            'booktype': issue_data['Type'],
                            'manual': False}
                logger.fdebug(f"Adding issue {issue_data['ComicName']} #{issue_data['Issue_Number']} [{issueId}] to search queue")
                s = mylar.SEARCH_QUEUE.put(passInfo)

        return json.dumps({'status': 'success'})
    forceSearch.exposed = True

    def forceRescan(self, ComicID, bulk=False, action='recheck', api=False):
        if bulk:
            cnt = 1
            if action == 'recheck':
                for cid in ComicID:
                    if api is False:
                        logger.info('[MASS BATCH][RECHECK-FILES][' + str(cnt) + '/' + str(len(ComicID)) + '] Rechecking ' + cid['ComicName'] + '(' + str(cid['ComicYear']) + ')')
                        updater.forceRescan(cid['ComicID'])
                    else:
                        logger.info('[MASS BATCH][RECHECK-FILES][' + str(cnt) + '/' + str(len(ComicID)) + '] Rechecking ComicID ' + str(cid))
                        updater.forceRescan(cid)
                    cnt+=1
                logger.info('[MASS BATCH][RECHECK-FILES] I have completed rechecking files for ' + str(len(ComicID)) + ' series.')
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicid': None, 'tables': None, 'message': 'Finished Rechecking files for %s series' % (len(ComicID))}
            else:
                for cid in ComicID:
                    logger.info('[MASS BATCH][METATAGGING-FILES][' + str(cnt) + '/' + str(len(ComicID)) + '] Now Preparing to metatag series for ' + cid['ComicName'] + '(' + str(cid['ComicYear']) + ')')
                    self.group_metatag(ComicID=cid['ComicID'], threaded=True)
                    cnt+=1
                logger.info('[MASS BATCH][METATAGGING-FILES] I have completed metatagging files for ' + str(len(ComicID)) + ' series.')
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicid': None, 'tables': 'both', 'message': 'Finished complete series (re)tagging of %s of %s (%s)' % (str(len(ComicID)), comicinfo['ComicName'], comicinfo['ComicYear'])}
        else:
            myDB = db.DBConnection()
            cline = myDB.selectone("SELECT ComicName, ComicYear FROM comics WHERE ComicID=?", [ComicID]).fetchone()
            if cline:
                updater.forceRescan(ComicID)
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': cline['ComicName'], 'seriesyear': cline['ComicYear'], 'comicid': ComicID, 'tables': 'both', 'message': 'Recheck Files completed for %s (%s)' % (cline['ComicName'], cline['ComicYear'])}

    forceRescan.exposed = True

    def checkGithub(self):
        from mylar import versioncheck
        cc_json = versioncheck.checkGithub()
    checkGithub.exposed = True

    def history(self):
        return serve_template(templatename="history.html", title="History")
    history.exposed = True

    def loadhistory(self, iDisplayStart=0, iDisplayLength=100, iSortCol_0=5, sSortDir_0="desc", sSearch="", **kwargs):
        myDB = db.DBConnection()
        r_list = myDB.select("select b.StoryArcID, b.StoryArc, b.IssueArcID, a.*, c.weeknumber, c.year from snatched a left join storyarcs b on b.issueid=a.issueid left join oneoffhistory c on a.issueid=c.issueid order by DateAdded DESC")
        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        resultlist = []
        watchlist = helpers.listLibrary()
        for rt in r_list:
            tmplist = {'StoryArc': rt['StoryArc'],
                       'StoryArcID': rt['StoryArcID'],
                       'IssueArcID': rt['IssueArcID'],
                       'ComicName': rt['ComicName'],
                       'Issue_Number': rt['Issue_Number'],
                       'Status': rt['Status'],
                       'DateAdded': rt['DateAdded'],
                       'Provider': rt['Provider'],
                       'IssueID': rt['IssueID'],
                       'ComicID': rt['ComicID'],
                       'weeknumber': rt['weeknumber'],
                       'weekyear': rt['year'],
                       'Oneoff':  None}

            if rt['IssueID'] is not None and all(['_' in rt['IssueID'], rt['StoryArc'] is None]):
                tmp = myDB.selectone("Select StoryArc FROM storyarcs where IssueArcID=?", [re.sub('S', '', rt['IssueID'])]).fetchone()
                if tmp:
                    tmplist['StoryArc'] = tmp['StoryArc']

            resultlist.append(tmplist)

        filtered = []
        if sSearch == "" or sSearch == None:
            filtered = resultlist[::]
        else:
            searchname = sSearch.split()
            searchname = '*'.join(searchname)
            searchname = re.sub('[\:\-\%\$\#\@\!\.\,\;\/\(\)\+\=\?]','*', sSearch.lower())
            searchpattern = '*%s*' % re.sub('\s','*', searchname.lower())
            for row in resultlist:
                searchname = fnmatch.fnmatch(row['ComicName'].lower(), searchpattern)
                if row['StoryArc'] is not None:
                    if not searchname:
                        searchname = fnmatch.fnmatch(row['StoryArc'].lower(), searchpattern)
                    if any([searchname is True, sSearch.lower() in row['Status'].lower(), sSearch.lower() in row['DateAdded'], sSearch.lower() in row['Issue_Number']]):
                        filtered.append(row)
                else:
                    if any([searchname is True, sSearch.lower() in row['Status'].lower(), sSearch.lower() in row['DateAdded'], sSearch.lower() in row['Issue_Number']]):
                        filtered.append(row)

        sortcolumn = 'DateAdded'
        if iSortCol_0 == '1':
            sortcolumn = 'DateAdded'
        if iSortCol_0 == '2':
            sortcolumn = 'ComicName'
        elif iSortCol_0 == '3':
            sortcolumn = 'Issue_Number'
        elif iSortCol_0 == '4':
            sortcolumn = 'Status'
        #below sort is for multi-sort columns, maybe make them user configurable - not sure how to pass mutli-sort thru otherwise
        #filtered.sort(key= itemgetter(sortcolumn2, sortcolumn), reverse=sSortDir_0 == "desc")

        filtered.sort(key=lambda x: (x[sortcolumn] is None, x[sortcolumn] == '', x[sortcolumn]), reverse=sSortDir_0 == "asc")
        if iDisplayLength != -1:
            trows = filtered[iDisplayStart:(iDisplayStart + iDisplayLength)]
        else:
            trows = filtered
        rows = []
        for r in trows:
            tmpr = r
            if all([r['ComicID'] not in watchlist, r['weeknumber'] is not None, r['StoryArc'] is None]):
                tmpr['Oneoff'] = '%s-%s' % (r['weeknumber'], r['weekyear'])
            rows.append(tmpr)

        rows = [[row['DateAdded'], row['ComicName'], row['Issue_Number'], row['Status'], row['IssueID'], row['ComicID'], row['Provider'], row['StoryArc'], row['IssueArcID'], row['StoryArcID'], row['Oneoff']] for row in rows]
        return json.dumps({
            'iTotalDisplayRecords': len(filtered),
            'iTotalRecords': len(resultlist),
            'aaData': rows,
        })
    loadhistory.exposed = True

    def reOrder(request):
        return request
#        return serve_template(templatename="reorder.html", title="ReoRdered!", reorder=request)
    reOrder.exposed = True

    def readlist(self):
        myDB = db.DBConnection()
        issuelist = myDB.select("SELECT * from readlist")
        #tuple this
        readlist = []
        counts = []
        c_added = 0  #count of issues that have been added to the readlist and remain in that status ( meaning not sent / read )
        c_sent = 0   #count of issues that have been sent to a third-party device ( auto-marked after a successful send completion )
        c_read = 0   #count of issues that have been marked as read ( manually marked as read - future: read state from xml )
        for iss in issuelist:
            if iss['Status'] == 'Added':
                statuschange = iss['DateAdded']
                c_added +=1
            else:
                if iss['Status'] == 'Read':
                    c_read +=1
                elif iss['Status'] == 'Downloaded':
                    c_sent +=1
                statuschange = iss['StatusChange']

            readlist.append({"ComicID":       iss['ComicID'],
                             "ComicName":     iss['ComicName'],
                             "SeriesYear":    iss['SeriesYear'],
                             "Issue_Number":  iss['Issue_Number'],
                             "IssueDate":     iss['IssueDate'],
                             "Status":        iss['Status'],
                             "StatusChange":  statuschange,
                             "inCacheDIR":    iss['inCacheDIR'],
                             "Location":      iss['Location'],
                             "IssueID":       iss['IssueID']})

        counts = {"added": c_added,
                   "read":  c_read,
                   "sent":  c_sent,
                   "total": (c_added + c_read + c_sent)}

        return serve_template(templatename="readinglist.html", title="Reading Lists", issuelist=readlist, counts=counts)
    readlist.exposed = True

    def clear_arcstatus(self, issuearcid=None):
        myDB = db.DBConnection()
        myDB.upsert('storyarcs', {'Status': 'Skipped'}, {'IssueArcID': issuearcid})
        logger.info('Status set to Skipped.')
    clear_arcstatus.exposed = True

    def storyarc_main(self, arcid=None, **kwargs):
        myDB = db.DBConnection()
        arclist = []
        if arcid is None:
            alist = myDB.select("SELECT * from storyarcs WHERE ComicName is not Null GROUP BY StoryArcID") #COLLATE NOCASE")
        else:
            alist = myDB.select("SELECT * from storyarcs WHERE ComicName is not Null AND StoryArcID=? GROUP BY StoryArcID", [arcid]) #COLLATE NOCASE")

        for al in alist:
            totalissues = myDB.select("SELECT COUNT(*) as count from storyarcs WHERE StoryARcID=? AND NOT Manual is 'deleted'", [al['StoryArcID']])

            havecnt = myDB.select("SELECT COUNT(*) as count FROM storyarcs WHERE StoryArcID=? AND (Status='Downloaded' or Status='Archived')", [al['StoryArcID']])
            havearc = havecnt[0][0]
            totalarc = totalissues[0][0]
            if not havearc:
                 havearc = 0
            try:
                 percent = (havearc *100.0) /totalarc
                 if percent > 100:
                     percent = 101
            except (ZeroDivisionError, TypeError):
                 percent = 0
                 totalarc = '?'


            arclist.append({"StoryArcID":       al['StoryArcID'],
                            "StoryArc":         al['StoryArc'],
                            "TotalIssues":      al['TotalIssues'],
                            "SeriesYear":       al['SeriesYear'],
                            "StoryArcDir":      al['StoryArc'],
                            "Status":           al['Status'],
                            "percent":          percent,
                            "Have":             havearc,
                            "SpanYears":        helpers.spantheyears(al['StoryArcID']),
                            "Total":            totalarc,
                            "CV_ArcID":         al['CV_ArcID']})
        if arcid is None:
            return serve_template(templatename="storyarc.html", title="Story Arcs", arclist=arclist, delete_type=0)
        else:
            return arclist[0]
    storyarc_main.exposed = True

    def detailStoryArc(self, StoryArcID, StoryArcName=None, CV_ArcID=None, **kwargs):
        myDB = db.DBConnection()
        if StoryArcID is None and CV_ArcID is not None:
            arcinfo = myDB.select("SELECT * from storyarcs WHERE CV_ArcID=? and NOT Manual IS 'deleted' order by ReadingOrder ASC", [CV_ArcID])
        else:
            arcinfo = myDB.select("SELECT * from storyarcs WHERE StoryArcID=? and NOT Manual IS 'deleted' order by ReadingOrder ASC", [StoryArcID])
        issref = []
        try:
            cvarcid = arcinfo[0]['CV_ArcID']
            arcpub = arcinfo[0]['Publisher']
            if StoryArcID is None:
                StoryArcID = arcinfo[0]['StoryArcID']
            #if StoryArcName is None:
            StoryArcName = arcinfo[0]['StoryArc']
            for la in arcinfo:
                if all([la['Status'] == 'Downloaded', la['Location'] is None]):
                    issref.append({'IssueID':         la['IssueID'],
                                   'ComicID':         la['ComicID'],
                                   'IssuePublisher':  la['IssuePublisher'],
                                   'Publisher':       la['Publisher'],
                                   'StoryArc':        la['StoryArc'],
                                   'StoryArcID':      la['StoryArcID'],
                                   'ComicName':       la['ComicName'],
                                   'IssueNumber':     la['IssueNumber'],
                                   'ReadingOrder':    la['ReadingOrder']})

            spanyears = helpers.spantheyears(StoryArcID)
            sdir = helpers.arcformat(StoryArcName, spanyears, arcpub)

        except:
            cvarcid = None
            sdir = mylar.CONFIG.GRABBAG_DIR

        if len(issref) > 0:
            helpers.updatearc_locs(StoryArcID, issref)
            arcinfo = myDB.select("SELECT * from storyarcs WHERE StoryArcID=? AND NOT Manual IS 'deleted' order by ReadingOrder ASC", [StoryArcID])

        template = 'storyarc_detail.html'

        if arcinfo:
            arcdetail = self.storyarc_main(arcid=arcinfo[0]['CV_ArcID'])
            storyarcbanner = None
            filepath = None
            if arcinfo[0]['ArcImage'] is not None:
                sb = 'cache/storyarcs/%s' % arcinfo[0]['ArcImage']
                arcimage = True
            else:
                sb = 'cache/storyarcs/%s-banner' % arcinfo[0]['CV_ArcID']
                arcimage = False
            storyarc_imagepath = os.path.join(mylar.CONFIG.CACHE_DIR, 'storyarcs')
            if not os.path.exists(storyarc_imagepath):
                try:
                    os.mkdir(storyarc_imagepath)
                except:
                    logger.warn('Unable to create storyarc image directory @ %s' % storyarc_imagepath)

            if os.path.exists(storyarc_imagepath):
                if arcimage is True:
                    storyarcbanner = sb + '?' + datetime.datetime.now().strftime('%y-%m-%d %H:%M:%S')
                    filepath = os.path.join(storyarc_imagepath, arcinfo[0]['ArcImage'])
                else:
                    dir = os.listdir(storyarc_imagepath)
                    for fname in dir:
                        if str(arcinfo[0]['CV_ArcID']) in fname:
                            storyarcbanner = sb
                            filepath = os.path.join(storyarc_imagepath, fname)
                            storyarcbanner += os.path.splitext(fname)[1] + '?' + datetime.datetime.now().strftime('%y-%m-%d %H:%M:%S')
                            break
           #            if any(['H' in fname, 'W' in fname]):
           #                if 'H' in fname:
           #                    bannerheight = int(fname[fname.find('H')+1:fname.find('.')])
           #                elif 'W' in fname:
           #                    bannerwidth = int(fname[fname.find('W')+1:fname.find('.')])

           #                if any([bannerwidth != 263, 'W' in fname]):
           #                    #accomodate poster size
           #                    storyarcbanner += 'W' + str(bannerheight)
           #                else:
           #                    #for actual banner width (ie. 960x280)
           #                    storyarcbanner += 'H' + str(bannerheight)
            #logger.fdebug('storyarcbanner: %s' % (storyarcbanner,))
            if filepath is not None:
                fname = os.path.basename(filepath)
                if any(['H' in fname, 'W' in fname]):
                   if 'H' in fname:
                       bannerwidth = 263
                       bannerheight = int(fname[fname.find('H')+1:fname.find('.')])
                       template = 'storyarc_detail.html'
                   elif 'W' in fname:
                       bannerheight = 400
                       bannerwidth = int(fname[fname.find('W')+1:fname.find('.')])
                       template = 'storyarc_detail.poster.html'

                #if any([bannerwidth != 263, 'W' in fname]):
                #    #accomodate poster size
                #    storyarcbanner += 'W' + str(bannerheight)
                #else:
                #    #for actual banner width (ie. 960x280)
                #    storyarcbanner += 'H' + str(bannerheight)
                else:
                    import get_image_size
                    image = get_image_size.get_image_metadata(filepath)
                    imageinfo = json.loads(get_image_size.Image.to_str_json(image))
                    logger.fdebug('imageinfo: %s' % imageinfo)
                    if imageinfo['width'] > imageinfo['height']:
                        template = 'storyarc_detail.html'
                        bannerheight = '280'
                        bannerwidth = '960'
                    else:
                        template = 'storyarc_detail.poster.html'
                        bannerwidth = '263'
                        bannerheight = '400'
            else:
                bannerheight = '280'
                bannerwidth = '960'
        else:
            arcdetail = {}
            arcdetail['percent'] = 0
            arcdetail['Have'] = 0
            arcdetail['Total'] = 0
            storyarcbanner = 'images/blank.gif'
            bannerwidth = '960'
            bannerheight= '280'
            spanyears = None

        return serve_template(templatename=template, title="Detailed Arc list", readlist=arcinfo, storyarcname=StoryArcName, storyarcid=StoryArcID, cvarcid=cvarcid, sdir=sdir, arcdetail=arcdetail, storyarcbanner=storyarcbanner, bannerheight=bannerheight, bannerwidth=bannerwidth, spanyears=spanyears)
    detailStoryArc.exposed = True

    def order_edit(self, **kwargs): #id, value):
        for k, v in kwargs.items():
            if 'id' in k:
                id = v
            elif 'value' in k:
                value = v

        storyarcid = id[:id.find('.')]
        issuearcid = id[id.find('.') +1:]
        readingorder = value
        #readingorder = value
        valid_readingorder = None
        #validate input here for reading order.
        try:
            if int(readingorder) >= 0:
                valid_readingorder = int(readingorder)
            if valid_readingorder == 0:
                valid_readingorder = 1
        except ValueError:
            logger.error('Non-Numeric/Negative readingorder submitted. Rejecting due to sequencing error.')
            return

        if valid_readingorder is None:
            logger.error('invalid readingorder supplied. Rejecting due to sequencing error')
            return

        myDB = db.DBConnection()
        readchk = myDB.select("SELECT * FROM storyarcs WHERE StoryArcID=? AND NOT Manual is 'deleted' ORDER BY ReadingOrder", [storyarcid])
        if readchk is None:
            logger.error('Cannot edit this for some reason (Cannot locate Storyarc) - something is wrong.')
            return

        new_readorder = []
        oldreading_seq = None
        logger.fdebug('[%s] Issue to renumber sequence from : %s' % (issuearcid, valid_readingorder))
        reading_seq = 1
        for rc in sorted(readchk, key=itemgetter('ReadingOrder'), reverse=False):
            filename = None
            if rc['Location'] is not None:
                filename = ntpath.basename(rc['Location'])
            if str(issuearcid) == str(rc['IssueArcID']):
                logger.fdebug('new order sequence detected at #: %s' % valid_readingorder)
                if valid_readingorder > int(rc['ReadingOrder']):
                    oldreading_seq = int(rc['ReadingOrder'])
                else:
                    oldreading_seq = int(rc['ReadingOrder']) + 1
                reading_seq = valid_readingorder
                issueid = rc['IssueID']
                IssueArcID = issuearcid
            elif int(rc['ReadingOrder']) < valid_readingorder:
                logger.fdebug('keeping issue sequence of order #: %s' % rc['ReadingOrder'])
                reading_seq = int(rc['ReadingOrder'])
                issueid = rc['IssueID']
                IssueArcID = rc['IssueArcID']
            elif int(rc['ReadingOrder']) >= valid_readingorder:
                if oldreading_seq is not None:
                    if valid_readingorder <= len(readchk):
                        reading_seq = int(rc['ReadingOrder'])
                        #reading_seq = oldreading_seq
                    else:
                        #valid_readingorder
                        if valid_readingorder < old_reading_seq:
                            reading_seq = int(rc['ReadingOrder'])
                        else:
                            reading_seq = oldreading_seq +1
                    logger.fdebug('old sequence discovered at %s to %s' % (oldreading_seq, reading_seq))
                    oldreading_seq = None
                elif int(rc['ReadingOrder']) == valid_readingorder:
                    reading_seq = valid_readingorder +1
                else:
                    reading_seq +=1 #valid_readingorder + (int(rc['ReadingOrder']) - valid_readingorder) +1
                issueid = rc['IssueID']
                IssueArcID = rc['IssueArcID']
                logger.fdebug('reordering existing sequence as lower sequence has changed. Altering from %s to %s' % (rc['ReadingOrder'], reading_seq))
            new_readorder.append({'IssueArcID':   IssueArcID,
                                  'IssueID':      issueid,
                                  'ReadingOrder': reading_seq,
                                  'filename':     filename})

        #we resequence in the following way:
        #  everything before the new reading number stays the same
        #  everything after the new reading order gets incremented
        #  add in the new reading order at the desired sequence
        #  check for empty spaces (missing numbers in sequence) and fill them in.
        logger.fdebug('new reading order: %s' % new_readorder)
        #newrl = 0
        for rl in sorted(new_readorder, key=itemgetter('ReadingOrder'), reverse=False):
            try:
                if rl['filename'] is not None:
                    if int(rl['ReadingOrder']) != int(rl['filename'][:rl['filename'].find('-')]) and mylar.CONFIG.READ2FILENAME is True:
                        logger.fdebug('Order-Change: %s TO %s' % (int(rl['filename'][:rl['filename'].find('-')]), int(rl['ReadingOrder'])))
                    logger.fdebug('%s to %s' % (rl['filename'], helpers.renamefile_readingorder(rl['ReadingOrder']) + '-' + rl['filename'][rl['filename'].find('-')+1:]))

                rl_ctrl = {"IssueID":           rl['IssueID'],
                           "IssueArcID":        rl['IssueArcID'],
                           "StoryArcID":        storyarcid}

                r1_new = {"ReadingOrder":       rl['ReadingOrder']}

                myDB.upsert("storyarcs", r1_new, rl_ctrl)
            except Exception as e:
                logger.warn('error: %s' % (e,))

        logger.info('Successfully changed reading order sequence')
        return value

    order_edit.exposed = True

    def manual_arc_add(self, manual_issueid, manual_readingorder, storyarcid, x=None, y=None):

        logger.fdebug('IssueID to be attached : ' + str(manual_issueid))
        logger.fdebug('StoryArcID : ' + str(storyarcid))
        logger.fdebug('Reading Order # : ' + str(manual_readingorder))

        threading.Thread(target=helpers.manualArc, args=[manual_issueid, manual_readingorder, storyarcid]).start()

        raise cherrypy.HTTPRedirect("detailStoryArc?StoryArcID=%s" % storyarcid)
    manual_arc_add.exposed = True


    def markreads(self, action=None, **args):
        sendtablet_queue = []
        myDB = db.DBConnection()
        for IssueID in args:
            if IssueID is None or 'issue_table' in IssueID or 'issue_table_length' in IssueID:
                continue
            else:
                mi = myDB.selectone("SELECT * FROM readlist WHERE IssueID=?", [IssueID]).fetchone()
                if mi is None:
                    continue
                else:
                    comicname = mi['ComicName']

                if action == 'Downloaded':
                    logger.fdebug("Marking %s #%s as %s" % (comicname, mi['Issue_Number'], action))
                    read = readinglist.Readinglist(IssueID)
                    read.addtoreadlist()
                elif action == 'Read':
                    logger.fdebug("Marking %s #%s as %s" % (comicname, mi['Issue_Number'], action))
                    markasRead(IssueID)
                elif action == 'Added':
                    logger.fdebug("Marking %s #%s as %s" % (comicname, mi['Issue_Number'], action))
                    read = readinglist.Readinglist(IssueID=IssueID)
                    read.addtoreadlist()
                elif action == 'Remove':
                    logger.fdebug('Deleting %s #%s' % (comicname, mi['Issue_Number']))
                    myDB.action('DELETE from readlist WHERE IssueID=?', [IssueID])
                elif action == 'Send':
                    logger.fdebug('Queuing ' + mi['Location'] + ' to send to tablet.')
                    sendtablet_queue.append({"filepath": mi['Location'],
                                             "issueid":  IssueID,
                                             "comicid":  mi['ComicID']})
        if len(sendtablet_queue) > 0:
            read = readinglist.Readinglist(sendtablet_queue)
            threading.Thread(target=read.syncreading).start()

    markreads.exposed = True

    def removefromreadlist(self, IssueID=None, StoryArcID=None, IssueArcID=None, AllRead=None, ArcName=None, delete_type=None, manual=None):
        myDB = db.DBConnection()
        if IssueID:
            myDB.action('DELETE from readlist WHERE IssueID=?', [IssueID])
            logger.info("[DELETE-READ-ISSUE] Removed " + str(IssueID) + " from Reading List")
        elif StoryArcID:
            logger.info('[DELETE-ARC] Removing ' + ArcName + ' from your Story Arc Watchlist')
            myDB.action('DELETE from storyarcs WHERE StoryArcID=?', [StoryArcID])
            #ArcName should be an optional flag so that it doesn't remove arcs that have identical naming (ie. Secret Wars)
            if delete_type:
                if ArcName:
                    logger.info('[DELETE-STRAGGLERS-OPTION] Removing all traces of arcs with the name of : ' + ArcName)
                    myDB.action('DELETE from storyarcs WHERE StoryArc=?', [ArcName])
                else:
                    logger.warn('[DELETE-STRAGGLERS-OPTION] No ArcName provided - just deleting by Story Arc ID')
            stid = 'S' + str(StoryArcID) + '_%'
            #delete from the nzblog so it will always find the most current downloads. Nzblog has issueid, but starts with ArcID
            myDB.action('DELETE from nzblog WHERE IssueID LIKE ?', [stid])
            logger.info("[DELETE-ARC] Removed " + str(StoryArcID) + " from Story Arcs.")
        elif IssueArcID:
            if manual == 'added':
                myDB.action('DELETE from storyarcs WHERE IssueArcID=?', [IssueArcID])
            else:
                myDB.upsert("storyarcs", {"Manual": 'deleted'}, {"IssueArcID": IssueArcID})
            #myDB.action('DELETE from storyarcs WHERE IssueArcID=?', [IssueArcID])
            logger.info("[DELETE-ARC] Removed " + str(IssueArcID) + " from the Story Arc.")
        elif AllRead:
            myDB.action("DELETE from readlist WHERE Status='Read'")
            logger.info("[DELETE-ALL-READ] Removed All issues that have been marked as Read from Reading List")
    removefromreadlist.exposed = True

    def markasRead(self, IssueID=None, IssueArcID=None):
        read = readinglist.Readinglist(IssueID, IssueArcID)
        read.markasRead(IssueID, IssueArcID)
    markasRead.exposed = True

    def addtoreadlist(self, IssueID):
        read = readinglist.Readinglist(IssueID=IssueID)
        chkreturn = read.addtoreadlist()
        if chkreturn is not None:
            return json.dumps({'status': chkreturn['status'], 'message': chkreturn['message']})
        else:
            return
        #raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % readlist['ComicID'])
    addtoreadlist.exposed = True

    def importReadlist(self, filename):
        from xml.dom.minidom import parseString, Element
        myDB = db.DBConnection()

        file = open(filename)
        data = file.read()
        file.close()

        dom = parseString(data)
        # of results
        storyarc = dom.getElementsByTagName('Name')[0].firstChild.wholeText
        tracks = dom.getElementsByTagName('Book')
        i = 1
        node = dom.documentElement
        logger.fdebug("there are " + str(len(tracks)) + " issues in the story-arc: " + str(storyarc))
        #generate a random number for the ID, and tack on the total issue count to the end as a str :)
        storyarcid = str(random.randint(1000, 9999)) + str(len(tracks))
        i = 1
        for book_element in tracks:
            st_issueid = str(storyarcid) + "_" + str(random.randint(1000, 9999))
            comicname = book_element.getAttribute('Series')
            logger.fdebug("comic: " + comicname)
            comicnumber = book_element.getAttribute('Number')
            logger.fdebug("number: " + str(comicnumber))
            comicvolume = book_element.getAttribute('Volume')
            logger.fdebug("volume: " + str(comicvolume))
            comicyear = book_element.getAttribute('Year')
            logger.fdebug("year: " + str(comicyear))
            CtrlVal = {"IssueArcID": st_issueid}
            NewVals = {"StoryArcID":  storyarcid,
                       "ComicName":   comicname,
                       "IssueNumber": comicnumber,
                       "SeriesYear":  comicvolume,
                       "IssueYear":   comicyear,
                       "StoryArc":    storyarc,
                       "ReadingOrder": i,
                       "TotalIssues": len(tracks)}
            myDB.upsert("storyarcs", NewVals, CtrlVal)
            i+=1

        # Now we either load in all of the issue data for series' already on the watchlist,
        # or we dynamically load them from CV and write to the db.

        #this loads in all the series' that have multiple entries in the current story arc.
        Arc_MultipleSeries = myDB.select("SELECT * FROM storyarcs WHERE StoryArcID=? AND IssueID is NULL GROUP BY ComicName HAVING (COUNT(ComicName) > 1)", [storyarcid])

        if Arc_MultipleSeries is None:
            logger.info('Detected 0 series that have multiple entries in this Story Arc. Continuing.')

        else:
            AMS = []
            for Arc_MS in Arc_MultipleSeries:
                print(Arc_MS)
                #the purpose of this loop is to loop through the multiple entries, pulling out the lowest & highest issue numbers
                #along with the publication years in order to help the auto-detector attempt to figure out what the series is on CV.
                #.schema storyarcs
                #(StoryArcID TEXT, ComicName TEXT, IssueNumber TEXT, SeriesYear TEXT, IssueYEAR TEXT, StoryArc TEXT, TotalIssues TEXT,
                # Status TEXT, inCacheDir TEXT, Location TEXT, IssueArcID TEXT, ReadingOrder INT, IssueID TEXT);
                AMS.append({"StoryArcID":  Arc_MS['StoryArcID'],
                            "ComicName":   Arc_MS['ComicName'],
                            "SeriesYear":  Arc_MS['SeriesYear'],
                            "IssueYear":   Arc_MS['IssueYear'],
                            "IssueID":     Arc_MS['IssueID'],
                            "highvalue":   '0',
                            "lowvalue":    '9999',
                            "yearRANGE":   [str(Arc_MS['SeriesYear'])]}) #Arc_MS['SeriesYear']})

            for MSCheck in AMS:
                thischk = myDB.select('SELECT * FROM storyarcs WHERE ComicName=? AND SeriesYear=?', [MSCheck['ComicName'], MSCheck['SeriesYear']])
                for tchk in thischk:
                    issueNumber_asInt = helpers.issue_number_parser(tchk['IssueNumber']).asInt

                    if issueNumber_asInt > helpers.issue_number_parser(MSCheck['highvalue']).asInt:
                        for key in list(MSCheck.keys()):
                            if key == "highvalue":
                                MSCheck[key] = tchk['IssueNumber']

                    if issueNumber_asInt < helpers.issue_number_parser(MSCheck['lowvalue']).asInt:
                        for key in list(MSCheck.keys()):
                            if key == "lowvalue":
                                MSCheck[key] = tchk['IssueNumber']

                    logger.fdebug(str(tchk['IssueYear']))
                    logger.fdebug(MSCheck['yearRANGE'])
                    if str(tchk['IssueYear']) not in str(MSCheck['yearRANGE']):
                        for key in list(MSCheck.keys()):
                            if key == "yearRANGE":
                                MSCheck[key].append(str(tchk['IssueYear']))

                #write out here
                #logger.fdebug(str(MSCheck))

        #now we load in the list without the multiple entries (ie. series that appear only once in the cbl and don't have an IssueID)
        Arc_Issues = myDB.select("SELECT * FROM storyarcs WHERE StoryArcID=? AND IssueID is NULL GROUP BY ComicName HAVING (COUNT(ComicName) = 1)", [storyarcid])
        if Arc_Issues is None:
            logger.fdebug('No individual series detected within the Reading list (series that only appear once).')
        else:
            logger.fdebug('Detected series that occur only once in the Reading List.')
            for AI in Arc_Issues:
                logger.fdebug('Detected ' + AI['ComicName'] + ' (' + AI['SeriesYear'] + ') #' + AI['IssueNumber'])
                AMS.append({"StoryArcID":  AI['StoryArcID'],
                            "ComicName":   AI['ComicName'],
                            "SeriesYear":  AI['SeriesYear'],
                            "IssueYear":   AI['IssueYear'],
                            "IssueID":     AI['IssueID'],
                            "highvalue":   AI['IssueNumber'],
                            "lowvalue":    AI['IssueNumber'],
                            "yearRANGE":   AI['IssueYear']})

        logger.fdebug('AMS:' + str(AMS))
        logger.fdebug('I need to now try to populate ' + str(len(AMS)) + ' series.')

        Arc_Data = []

        for duh in AMS:
            mode='series'
            sresults = mb.findComic(duh['ComicName'], mode, issue=duh['highvalue'], limityear=duh['yearRANGE'])
            type='comic'

            if len(sresults) == 1:
                sr = sresults[0]
                logger.info('Only one result...automagik-mode enabled for ' + duh['ComicName'] + ' :: ' + str(sr['comicid']) + ' :: Publisher : ' + str(sr['publisher']))
                issues = mylar.cv.getComic(sr['comicid'], 'issue')
                isscnt = len(issues['issuechoice'])
                logger.info('isscnt : ' + str(isscnt))
                chklist = myDB.select('SELECT * FROM storyarcs WHERE StoryArcID=? AND ComicName=? AND SeriesYear=?', [duh['StoryArcID'], duh['ComicName'], duh['SeriesYear']])
                if chklist is None:
                    logger.error('I did not find anything in the Story Arc. Something is probably wrong.')
                    continue
                else:
                    n = 0
                    while (n <= isscnt):
                        try:
                            islval = issues['issuechoice'][n]
                        except IndexError:
                            break

                        for d in chklist:
                            if islval['Issue_Number'] == d['IssueNumber']:
                                logger.info('[' + str(islval['Issue_ID']) + '] matched on Issue Number for ' + duh['ComicName'] + ' #' + str(d['IssueNumber']))
                                logger.info('I should write these dates: ' + islval['Issue_Date'] + ' -- ' + islval['Store_Date'])
                                Arc_Data.append({"StoryArcID":    duh['StoryArcID'],
                                                 "IssueArcID":    d['IssueArcID'],
                                                 "ComicID":       islval['Comic_ID'],
                                                 "IssueID":       islval['Issue_ID'],
                                                 "Issue_Number":  islval['Issue_Number'],
                                                 "Issue_Date":    islval['Issue_Date'],
                                                 "Publisher":     sr['publisher'],
                                                 "Store_Date":    islval['Store_Date']})
                                break
                        n+=1
                #the below cresults will auto-add and cycle through until all are added to watchlist
                #cresults = importer.addComictoDB(sr['comicid'],"no",None)

            else:
                logger.fdebug('Returning results to screen - more than one possibility.')
                resultset = 0

        logger.info('I need to update ' + str(len(Arc_Data)) + ' issues in this Reading List with CV Issue Data.')
        if len(Arc_Data) > 0:
            for AD in Arc_Data:
                newCtrl = {"IssueArcID":    AD['IssueArcID']}
                newVals = {"ComicID":       AD['ComicID'],
                           "IssueID":       AD['IssueID'],
                           "Publisher":     AD['Publisher'],
                           "IssueDate":     AD['Issue_Date'],
                           "ReleaseDate":   AD['Store_Date']}

                myDB.upsert("storyarcs", newVals, newCtrl)


        raise cherrypy.HTTPRedirect("detailStoryArc?StoryArcID=%s&StoryArcName=%s" % (storyarcid, storyarc))
    importReadlist.exposed = True

    def ArcWatchlist(self,StoryArcID=None):
        myDB = db.DBConnection()
        if StoryArcID:
            ArcWatch = myDB.select("SELECT * FROM storyarcs WHERE StoryArcID=?", [StoryArcID])
        else:
            ArcWatch = myDB.select("SELECT * FROM storyarcs")

        if ArcWatch is None:
            logger.info("No Story Arcs to search")
        else:
            #cycle through the story arcs here for matches on the watchlist
            arcname = ArcWatch[0]['StoryArc']
            arcdir = helpers.filesafe(arcname)
            if StoryArcID is None:
                StoryArcID = ArcWatch[0]['StoryArcID']
            arcpub = ArcWatch[0]['Publisher']
            if arcpub is None:
                arcpub = ArcWatch[0]['IssuePublisher']

            logger.info('arcpub: %s' % arcpub)
            dstloc = helpers.arcformat(arcdir, helpers.spantheyears(StoryArcID), arcpub)
            filelist = None

            if dstloc is not None:
                if not os.path.isdir(dstloc):
                    if mylar.CONFIG.STORYARCDIR:
                        logger.info('Story Arc Directory [%s] does not exist! - attempting to create now.' % dstloc)
                    else:
                        logger.info('Story Arc Grab-Bag Directory [%s] does not exist! - attempting to create now.' % dstloc)
                    checkdirectory = filechecker.validateAndCreateDirectory(dstloc, True)
                    if not checkdirectory:
                        logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                        return

                if all([mylar.CONFIG.CVINFO, mylar.CONFIG.STORYARCDIR]):
                    if not os.path.isfile(os.path.join(dstloc, "cvinfo")) or mylar.CONFIG.CV_ONETIMER:
                        logger.fdebug('Generating cvinfo file for story-arc.')
                        with open(os.path.join(dstloc, "cvinfo"), "w") as text_file:
                            if any([ArcWatch[0]['StoryArcID'] == ArcWatch[0]['CV_ArcID'], ArcWatch[0]['CV_ArcID'] is None]):
                                cvinfo_arcid = ArcWatch[0]['StoryArcID']
                            else:
                                cvinfo_arcid = ArcWatch[0]['CV_ArcID']

                            text_file.write('https://comicvine.gamespot.com/storyarc/4045-' + str(cvinfo_arcid))
                        if mylar.CONFIG.ENFORCE_PERMS:
                            filechecker.setperms(os.path.join(dstloc, 'cvinfo'))

                #get the list of files within the storyarc directory, if any.
                if mylar.CONFIG.STORYARCDIR:
                    fchk = filechecker.FileChecker(dir=dstloc, watchcomic=None, Publisher=None, sarc='true', justparse=True)
                    filechk = fchk.listFiles()
                    fccnt = filechk['comiccount']
                    logger.fdebug('[STORY ARC DIRECTORY] %s files exist within this directory.' % fccnt)
                    if fccnt > 0:
                        filelist = filechk['comiclist']
                    logger.info(filechk)

            arc_match = []
            wantedlist = []

            sarc_title = None
            showonreadlist = 1 # 0 won't show storyarcissues on storyarcs main page, 1 will show
            for arc in ArcWatch:

                newStatus = 'Skipped'

                if arc['Manual'] == 'deleted':
                    continue

                sarc_title = arc['StoryArc']
                logger.fdebug('[%s] %s : %s' % (arc['StoryArc'], arc['ComicName'], arc['IssueNumber']))

                matcheroso = "no"

                dyn_name = arc['DynamicComicName']
                dyn_name = re.sub('[\|\s]','', dyn_name.lower()).strip()
                if mylar.CONFIG.ANNUALS_ON:
                    dyn_name = re.sub('2021annual', '', dyn_name).strip()
                    dyn_name = re.sub('annual', '', dyn_name).strip()
                comics = myDB.select("SELECT * FROM comics WHERE DynamicComicName IN (?) COLLATE NOCASE",[dyn_name])

                for comic in comics:
                    mod_watch = comic['DynamicComicName'] #is from the comics db
                    mod_watch = re.sub('[\|\s]','', mod_watch.lower()).strip()
                    if mylar.CONFIG.ANNUALS_ON:
                        tmp_chkr = re.sub('[\|\s]', '', re.sub('2021annual', '', mod_watch)).strip()
                        mod_watch = re.sub('[\|\s]', '', re.sub('annual', '', tmp_chkr)).strip()
                    logger.fdebug('mod_watch: %s' % re.sub('[\|\s]', '', mod_watch.lower()).strip())
                    if mod_watch == dyn_name:
                        logger.fdebug("initial name match - confirming issue # is present in series")
                        if comic['ComicID'][:1] == 'G':
                            # if it's a multi-volume series, it's decimalized - let's get rid of the decimal.
                            GCDissue, whocares = helpers.decimal_issue(arc['IssueNumber'])
                            GCDissue = int(GCDissue) / 1000
                            if '.' not in str(GCDissue):
                                GCDissue = '%s.00' % GCDissue
                            logger.fdebug("issue converted to %s" % GCDissue)
                            isschk = myDB.selectone("SELECT * FROM issues WHERE Issue_Number=? AND ComicID=?", [str(GCDissue), comic['ComicID']]).fetchone()
                        else:
                            issue_int = helpers.issue_number_parser(arc['IssueNumber']).asInt
                            logger.fdebug('int_issue = %s' % issue_int)
                            if mylar.CONFIG.ANNUALS_ON and 'annual' in arc['ComicName'].lower():
                                logger.fdebug('annual checking: %s -- %s' % (issue_int, comic['ComicID']))
                                isschk = myDB.select("SELECT ComicID, IssueID, IssueDate, ReleaseDate, ReleaseComicName FROM annuals WHERE Int_IssueNumber=? AND ComicID=?", [issue_int, comic['ComicID']])
                                match_annual = True
                            else:
                                isschk = myDB.select("SELECT ComicID, IssueID, IssueDate, ReleaseDate, ComicName FROM issues WHERE Int_IssueNumber=? AND ComicID=?", [issue_int, comic['ComicID']]) #AND STATUS !='Snatched'", [issue_int, comic['ComicID']]).fetchone()
                                match_annual = False
                        if isschk is None:
                            logger.fdebug('We matched on name, but issue %s doesn\'t exist for %s' % (arc['IssueNumber'], comic['ComicName']))
                        else:
                            for isk in isschk:
                                #this gets ugly - if the name matches and the issue, it could still be wrong series
                                #use series year to break it down further.
                                logger.fdebug('COMIC-comicyear: %s' % comic['ComicYear'])
                                logger.fdebug('B4-ARC-seriesyear: %s' % arc['SeriesYear'])
                                if any([arc['SeriesYear'] is None, arc['SeriesYear'] == 'None']):
                                    vy = '2099-00-00'
                                    if any([isk['IssueDate'] is None, isk['IssueDate'] == '0000-00-00']):
                                        sy = isk['ReleaseDate']
                                        if any([sy is None, sy == '0000-00-00']):
                                            continue
                                    else:
                                        sy = isk['IssueDate']
                                    if sy < vy:
                                        v_seriesyear = sy
                                    seriesyear = v_seriesyear
                                    logger.fdebug('No Series year set. Discovered & set to %s' % seriesyear)
                                else:
                                    seriesyear = arc['SeriesYear']
                                logger.fdebug('ARC-seriesyear: %s' % seriesyear)
                                logger.fdebug('[SAFETY-CHECK] Checking issue dates between arc & series to make sure we match the right volume')
                                if all([arc['IssueDate'] is not None, arc['IssueDate'] != '0000-00-00']):
                                    tmpdate_chk = arc['IssueDate']
                                elif all([arc['ReleaseDate'] is not None, arc['ReleaseDate'] != '0000-00-00']):
                                    tmpdate_chk = arc['ReleaseDate']
                                if any([isk['IssueDate'] is None, isk['IssueDate'] == '0000-00-00']):
                                    sy = isk['ReleaseDate']
                                    if any([sy is None, sy == '0000-00-00']):
                                        logger.fdebug('No valid dates present for %s %s [%s]' % (arc['ComicName'], arc['IssueNumber'], isk['ComicID']))
                                        continue
                                    else:
                                        iss_tmpchk = sy
                                else:
                                    iss_tmpchk = isk['IssueDate']

                                if re.sub('-', '', tmpdate_chk).strip() != re.sub('-', '', iss_tmpchk).strip():
                                    logger.fdebug('Issue Dates are different (issue:%s / arc:%s) - this is probably attempting to hit the wrong volume of the series. Ignoring this result.' % (tmpdate_chk, iss_tmpchk))
                                    continue
                                logger.fdebug('issue #: %s is present!' % arc['IssueNumber'])
                                logger.fdebug('Comicname: %s' % arc['ComicName'])
                                logger.fdebug('ComicID: %s [IssueID: %s]' % (isk['ComicID'], isk['IssueID']))
                                logger.fdebug('Issue: %s' % arc['IssueNumber'])
                                logger.fdebug('IssueArcID: %s' % arc['IssueArcID'])
                                #gather the matches now.
                                arc_match.append({
                                    "match_storyarc":          arc['StoryArc'],
                                    "match_annual":            match_annual,
                                    "match_name":              arc['ComicName'],
                                    "match_id":                isk['ComicID'],
                                    "match_issueid":           isk['IssueID'],
                                    "match_issue":             arc['IssueNumber'],
                                    "match_issuearcid":        arc['IssueArcID'],
                                    "match_seriesyear":        comic['ComicYear'],
                                    "match_readingorder":      arc['ReadingOrder'],
                                    "match_filedirectory":     comic['ComicLocation'],   #series directory path
                                    "destination_location":    dstloc})                  #path to given storyarc / grab-bag directory
                                matcheroso = "yes"
                                break
                    if matcheroso == "yes":
                        break

                if matcheroso == "no":
                    logger.fdebug('[NO WATCHLIST MATCH] Unable to find a match for %s :#%s' % (arc['ComicName'], arc['IssueNumber']))
                    wantedlist.append({
                         "ComicName":      arc['ComicName'],
                         "IssueNumber":    arc['IssueNumber'],
                         "IssueYear":      arc['IssueYear']})

                if filelist is not None and mylar.CONFIG.STORYARCDIR:
                    logger.fdebug('[NO WATCHLIST MATCH] Checking against local Arc directory for given issue.')
                    fn = 0
                    valids = [x for x in filelist if re.sub('[\|\s]','', x['dynamic_name'].lower()).strip() == re.sub('[\|\s]','', arc['DynamicComicName'].lower()).strip()]
                    logger.fdebug('valids: %s' % valids)
                    if len(valids) > 0:
                        for tmpfc in valids: #filelist:
                            haveissue = "no"
                            issuedupe = "no"
                            temploc = tmpfc['issue_number']
                            if temploc:
                                temploc = temploc.replace('_', ' ')
                            else:
                                logger.debug('could not parse issue number: %r', tmpfc)                                
                            fcdigit = helpers.issue_number_parser(arc['IssueNumber']).asInt
                            int_iss = helpers.issue_number_parser(temploc).asInt
                            if int_iss == fcdigit:
                                logger.fdebug('%s Issue #%s already present in StoryArc directory' % (arc['ComicName'], arc['IssueNumber']))
                                #update storyarcs db to reflect status.
                                rr_rename = False
                                if mylar.CONFIG.READ2FILENAME:
                                    readorder = helpers.renamefile_readingorder(arc['ReadingOrder'])
                                    if all([tmpfc['reading_order'] is not None, int(readorder) != int(tmpfc['reading_order']['reading_sequence'])]):
                                        logger.warn('reading order sequence has changed for this issue from %s to %s' % (tmpfc['reading_order']['reading_sequence'], readorder))
                                        rr_rename = True
                                        dfilename = '%s-%s' % (readorder, tmpfc['reading_order']['filename'])
                                    elif tmpfc['reading_order'] is None:
                                        dfilename = '%s-%s' % (readorder, tmpfc['comicfilename'])
                                    else:
                                        dfilename = '%s-%s' % (readorder, tmpfc['reading_order']['filename'])
                                else:
                                    dfilename = tmpfc['comicfilename']

                                if all([tmpfc['sub'] is not None, tmpfc['sub'] != 'None']):
                                    loc_path = os.path.join(tmpfc['comiclocation'], tmpfc['sub'], dfilename)
                                else:
                                    loc_path = os.path.join(tmpfc['comiclocation'], dfilename)

                                if rr_rename:
                                    logger.fdebug('Now re-sequencing file to : %s' % dfilename)
                                    os.rename(os.path.join(tmpfc['comiclocation'],tmpfc['comicfilename']), loc_path)

                                newStatus = 'Downloaded'
                                newVal = {"Status":   newStatus,
                                          "Location": loc_path}    #dfilename}
                                ctrlVal = {"IssueArcID":  arc['IssueArcID']}
                                myDB.upsert("storyarcs", newVal, ctrlVal)
                                break
                            else:
                                newStatus = 'Skipped'
                            fn+=1
                        if newStatus == 'Skipped':
                            #this will set all None Status' to Skipped (at least initially)
                            newVal = {"Status":   "Skipped"}
                            ctrlVal = {"IssueArcID":  arc['IssueArcID']}
                            myDB.upsert("storyarcs", newVal, ctrlVal)
                        continue

                newVal = {"Status":   "Skipped"}
                ctrlVal = {"IssueArcID":  arc['IssueArcID']}
                myDB.upsert("storyarcs", newVal, ctrlVal)

            logger.fdebug('%s issues currently exist on your watchlist that are within this arc. Analyzing...' % len(arc_match))
            for m_arc in arc_match:
                #now we cycle through the issues looking for a match.
                if m_arc['match_annual']:
                    issue = myDB.selectone("SELECT a.Issue_Number, a.Status, a.IssueID, a.ComicName, a.IssueDate, a.Location, b.readingorder FROM annuals AS a INNER JOIN storyarcs AS b ON a.releasecomicid = b.comicid where a.comicid=? and a.issue_number=? and a.issueid=?", [m_arc['match_id'], m_arc['match_issue'], m_arc['match_issueid']]).fetchone()
                else:
                    issue = myDB.selectone("SELECT a.Issue_Number, a.Status, a.IssueID, a.ComicName, a.IssueDate, a.Location, b.readingorder FROM issues AS a INNER JOIN storyarcs AS b ON a.comicid = b.comicid where a.comicid=? and a.issue_number=?", [m_arc['match_id'], m_arc['match_issue']]).fetchone()
                if issue is None: pass
                else:
                    logger.fdebug('[m_arc:%s][%s]issue: %s ... %s' % (m_arc['match_id'], issue['IssueID'], issue['Issue_Number'], m_arc['match_issue']))
                    if issue['Issue_Number'] == m_arc['match_issue']:
                        logger.fdebug('We matched on %s for %s' % (issue['Issue_Number'], m_arc['match_name']))
                        if issue['Status'] == 'Downloaded' or issue['Status'] == 'Archived' or issue['Status'] == 'Snatched':
                            if showonreadlist:
                                showctrlVal = {"IssueID":       issue['IssueID']}
                                shownewVal = {"ComicName":      issue['ComicName'],
                                              "Issue_Number":    issue['Issue_Number'],
                                              "IssueDate":      issue['IssueDate'],
                                              "SeriesYear":     m_arc['match_seriesyear'],
                                              "ComicID":        m_arc['match_id']}
                                myDB.upsert("readlist", shownewVal, showctrlVal)

                            logger.fdebug('Already have %s : #%s' % (issue['ComicName'], issue['Issue_Number']))
                            if issue['Location'] is not None:
                                issloc = os.path.join(m_arc['match_filedirectory'], issue['Location'])
                            else:
                                issloc = None
                            location_path = issloc

                            if issue['Status'] == 'Downloaded':
                                #check multiple destination directory usage here.
                                if not os.path.isfile(issloc):
                                    try:
                                        if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                                            if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(m_arc['match_filedirectory']))):
                                                secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(m_arc['match_filedirectory']))
                                            else:
                                                ff = mylar.filers.FileHandlers(ComicID=m_arc['match_id'])
                                                secondary_folders = ff.secondary_folders(m_arc['match_filedirectory'])

                                            issloc = os.path.join(secondary_folders, issue['Location'])
                                            if not os.path.isfile(issloc):
                                                logger.warn('Source file cannot be located. Please do a Recheck for the specific series to ensure everything is correct.')
                                                continue
                                    except:
                                        pass
                                logger.fdebug('source location set to  : %s' % issloc)

                                if all([mylar.CONFIG.STORYARCDIR, mylar.CONFIG.COPY2ARCDIR]):
                                    logger.fdebug('Destination location set to  : %s' % m_arc['destination_location'])
                                    logger.fdebug('Attempting to copy into StoryArc directory')
                                    #copy into StoryArc directory...

                                 #need to make sure the file being copied over isn't already present in the directory either with a different filename,
                                 #or different reading order.
                                    rr_rename = False
                                    if mylar.CONFIG.READ2FILENAME:
                                        readorder = helpers.renamefile_readingorder(m_arc['match_readingorder'])
                                        if all([m_arc['match_readingorder'] is not None, int(readorder) != int(m_arc['match_readingorder'])]):
                                            logger.warn('Reading order sequence has changed for this issue from %s to %s' % (m_arc['match_reading_order'], readorder))
                                            rr_rename = True
                                            dfilename = '%s-%s' % (readorder, issue['Location'])
                                        elif m_arc['match_readingorder'] is None:
                                            dfilename = '%s-%s' % (readorder, issue['Location'])
                                        else:
                                            dfilename = '%s-%s' % (readorder, issue['Location'])
                                    else:
                                        dfilename = issue['Location']

                                        #dfilename = str(readorder) + "-" + issue['Location']
                                    #else:
                                        #dfilename = issue['Location']

                                    dstloc = os.path.join(m_arc['destination_location'], dfilename)

                                    if rr_rename:
                                        logger.fdebug('Now re-sequencing COPIED file to : %s' % dfilename)
                                        os.rename(issloc, dstloc)


                                    if not os.path.isfile(dstloc):
                                        logger.fdebug('Copying %s to %s' % (issloc, dstloc))
                                        try:
                                           fileoperation = helpers.file_ops(issloc, dstloc, arc=True)
                                           if not fileoperation:
                                               raise OSError
                                        except (OSError, IOError):
                                            logger.error('Failed to %s %s - check directories and manually re-run.' % (mylar.CONFIG.FILE_OPTS, issloc))
                                            continue
                                    else:
                                        logger.fdebug('Destination file exists: %s' % dstloc)
                                    location_path = dstloc
                                else:
                                    location_path = issloc

                            ctrlVal = {"IssueArcID":  m_arc['match_issuearcid']}
                            newVal = {'Status':   issue['Status'],
                                      'IssueID':  issue['IssueID'],
                                      'Location': location_path}

                            myDB.upsert("storyarcs",newVal,ctrlVal)

                        else:
                            logger.fdebug('We don\'t have %s : #%s' % (issue['ComicName'], issue['Issue_Number']))
                            ctrlVal = {"IssueArcID":  m_arc['match_issuearcid']}
                            newVal = {"Status":  issue['Status'], #"Wanted",
                                      "IssueID": issue['IssueID']}
                            myDB.upsert("storyarcs", newVal, ctrlVal)
                            logger.info('Marked %s :#%s as %s' % (issue['ComicName'], issue['Issue_Number'], issue['Status']))

            arcstats = self.storyarc_main(StoryArcID)
            logger.info('[STORY-ARCS] Completed Missing/Recheck Files for %s [%s / %s]' % (arcname, arcstats['Have'], arcstats['TotalIssues']))
            return

    ArcWatchlist.exposed = True

    def SearchArcIssues(self, **kwargs):
        threading.Thread(target=self.ReadGetWanted, kwargs=kwargs).start()
    SearchArcIssues.exposed = True

    def ReadGetWanted(self, StoryArcID):
        # this will queue up (ie. make 'Wanted') issues in a given Story Arc that are 'Not Watched'
        stupdate = []
        add_to_search_queue = []
        mode = 'story_arc'
        myDB = db.DBConnection()
        wantedlist = myDB.select("SELECT * FROM storyarcs WHERE StoryArcID=? AND Status != 'Downloaded' AND Status !='Archived' AND Status !='Snatched'", [StoryArcID])
        if wantedlist is not None:
            for want in wantedlist:
                print(want)
                issuechk = myDB.selectone("SELECT a.Type, a.ComicYear, b.ComicName, b.Issue_Number, b.ComicID, b.IssueID FROM comics as a INNER JOIN issues as b on a.ComicID = b.ComicID WHERE b.IssueID=?", [want['IssueArcID']]).fetchone()
                SARC = want['StoryArc']
                IssueArcID = want['IssueArcID']
                Publisher = want['Publisher']
                if issuechk is None:
                    # none means it's not a 'watched' series
                    s_comicid = want['ComicID'] #None
                    s_issueid = want['IssueArcID'] #None
                    actual_issueid = None
                    BookType = want['Type']
                    stdate = want['ReleaseDate']
                    issdate = want['IssueDate']
                    logger.fdebug("-- NOT a watched series queue.")
                    logger.fdebug('%s -- #%s' % (want['ComicName'], want['IssueNumber']))
                    logger.fdebug('Story Arc %s : queueing the selected issue...' % SARC)
                    logger.fdebug('IssueArcID : %s' % IssueArcID)
                    logger.fdebug('ComicID: %s --- IssueID: %s' % (s_comicid, s_issueid))  # no comicid in issues table.
                    logger.fdebug('ReleaseDate: %s --- IssueDate: %s' % (stdate, issdate))
                    issueyear = want['IssueYEAR']
                    logger.fdebug('IssueYear: %s' % issueyear)
                    if issueyear is None or issueyear == 'None':
                        try:
                            logger.fdebug('issdate:' + str(issdate))
                            issueyear = issdate[:4]
                            if not issueyear.startswith('19') and not issueyear.startswith('20'):
                                issueyear = stdate[:4]
                        except:
                            issueyear = stdate[:4]

                    seriesyear = want['SeriesYear']
                    comicname = want['ComicName']
                    issuenumber = want['IssueNumber']

                    logger.fdebug('ComicYear: %s' % want['SeriesYear'])
                    passinfo = {'issueid': s_issueid,
                                'comicname': want['ComicName'],
                                'seriesyear': want['SeriesYear'],
                                'comicid': s_comicid,
                                'issuenumber': want['IssueNumber'],
                                'booktype': BookType}
                                #oneoff = True ?
                else:
                    # it's a watched series
                    s_comicid = issuechk['ComicID']
                    s_issueid = issuechk['IssueID']
                    actual_issueid = want['IssueID']
                    logger.fdebug("-- watched series queue.")
                    logger.fdebug('%s --- #%s' % (issuechk['ComicName'], issuechk['Issue_Number']))
                    seriesyear = issuechk['SeriesYear']
                    comicname = issuechk['ComicName']
                    issuenumber = issuechk['Issue_Number']
                    passinfo = {'issueid':     s_issueid,
                                'comicname':   issuechk['ComicName'],
                                'seriesyear':  issuechk['SeriesYear'],
                                'comicid':     s_comicid,
                                'issuenumber': issuechk['Issue_Number'],
                                'booktype':    issuechk['Type']}

                add_to_search_queue.append(passinfo)

                logger.fdebug('Marking %s #%s (%s) as Wanted for future searches.' % (comicname, issuenumber, seriesyear))
                stupdate.append({"Status":     "Wanted",
                                 "IssueArcID": IssueArcID,
                                 "IssueID":    actual_issueid})

        watchlistchk = myDB.select("SELECT * FROM storyarcs WHERE StoryArcID=? AND Status='Wanted'", [StoryArcID])
        if watchlistchk is not None:
            for watchchk in watchlistchk:
                logger.fdebug('Watchlist hit - %s' % watchchk['ComicName'])
                issuechk = myDB.selectone("SELECT a.Type, a.ComicYear, b.ComicName, b.Issue_Number, b.ComicID, b.IssueID FROM comics as a INNER JOIN issues as b on a.ComicID = b.ComicID WHERE b.IssueID=?", [watchchk['IssueArcID']]).fetchone()
                SARC = watchchk['StoryArc']
                IssueArcID = watchchk['IssueArcID']
                if issuechk is None:
                    # none means it's not a 'watched' series
                    try:
                        s_comicid = watchchk['ComicID']
                    except:
                        s_comicid = None

                    try:
                        s_issueid = watchchk['IssueArcID']
                    except:
                        s_issueid = None

                    actual_issueid = None
                    logger.fdebug("-- NOT a watched series queue.")
                    logger.fdebug('%s -- #%s' % (watchchk['ComicName'], watchchk['IssueNumber']))
                    logger.fdebug('Story Arc : %s queueing up the selected issue...' % SARC)
                    logger.fdebug('IssueArcID : %s' % IssueArcID)
                    try:
                        issueyear = watchchk['IssueYEAR']
                        logger.fdebug('issueYEAR : %s' % issueyear)
                    except:
                        try:
                            issueyear = watchchk['IssueDate'][:4]
                        except:
                            issueyear = watchchk['ReleaseDate'][:4]

                    stdate = watchchk['ReleaseDate']
                    issdate = watchchk['IssueDate']
                    logger.fdebug('issueyear : %s' % issueyear)
                    logger.fdebug('comicname : %s' % watchchk['ComicName'])
                    logger.fdebug('issuenumber : %s' % watchchk['IssueNumber'])
                    logger.fdebug('comicyear : %s' % watchchk['SeriesYear'])
                    #logger.info('publisher : ' + watchchk['IssuePublisher']) <-- no publisher in table
                    logger.fdebug('SARC : %s' % SARC)
                    logger.fdebug('IssueArcID : %s' % IssueArcID)
                    passinfo = {'issueid':     s_issueid,
                                'comicname':   watchchk['ComicName'],
                                'seriesyear':  watchchk['SeriesYear'],
                                'comicid':     s_comicid,
                                'issuenumber': watchchk['IssueNumber'],
                                'booktype':    watchchk['Type']}

                else:
                    # it's a watched series
                    s_comicid = issuechk['ComicID']
                    s_issueid = issuechk['IssueID']
                    actual_issueid = issuechk['IssueID']
                    logger.fdebug('-- watched series queue.')
                    logger.fdebug('%s -- #%s' % (issuechk['ComicName'], issuechk['Issue_Number']))
                    passinfo = {'issueid':     s_issueid,
                                'comicname':   issuechk['ComicName'],
                                'seriesyear':  issuechk['SeriesYear'],
                                'comicid':     s_comicid,
                                'issuenumber': issuechk['Issue_Number'],
                                'booktype':    issuechk['Type']}

                add_to_search_queue.append(passinfo)

                stupdate.append({"Status":     "Wanted",
                                 "IssueArcID": IssueArcID,
                                 "IssueID":    actual_issueid})


        if len(stupdate) > 0:
            logger.fdebug('%s issues need to get updated to Wanted Status' % len(stupdate))
            for st in stupdate:
                ctrlVal = {'IssueArcID': st['IssueArcID']}
                newVal = {'Status': st['Status']}
                myDB.upsert("storyarcs", newVal, ctrlVal)
                if st['IssueID']:
                    ctrlVal = {'IssueID': st['IssueID']}
                    myDB.upsert("issues", newVal, ctrlVal)
        mylar.SEARCH_QUEUE.put((passinfo))

    ReadGetWanted.exposed = True


    def ReadMassCopy(self, StoryArcID, StoryArcName):
        #this copies entire story arcs into the /cache/<storyarc> folder
        #alternatively, it will copy the issues individually directly to a 3rd party device (ie.tablet)

        myDB = db.DBConnection()
        copylist = myDB.select("SELECT * FROM readlist WHERE StoryArcID=? AND Status='Downloaded'", [StoryArcID])
        if copylist is None:
            logger.fdebug("You don't have any issues from " + StoryArcName + ". Aborting Mass Copy.")
            return
        else:
            dst = os.path.join(mylar.CONFIG.CACHE_DIR, StoryArcName)
            for files in copylist:

                copyloc = files['Location']

    ReadMassCopy.exposed = True

    def logs(self, **kwargs):
        return serve_template(templatename="logs.html", title="Log", lineList=mylar.LOGLIST, log_level=mylar.LOG_LEVEL)
    logs.exposed = True

    def config_dump(self):
        return serve_template(templatename="config_dump.html", title="Config Listing", lineList=mylar.CONFIG)
    config_dump.exposed = True

    def clearLogs(self):
        mylar.LOGLIST = []
        logger.info("Web logs cleared")
        raise cherrypy.HTTPRedirect("logs")
    clearLogs.exposed = True

    def toggleVerbose(self, level=None):
        if level is None:
            if mylar.LOG_LEVEL != 2:
                mylar.LOG_LEVEL = 2
            else:
                mylar.LOG_LEVEL = 1
        else:
            mylar.LOG_LEVEL = level

        if logger.LOG_LANG.startswith('en'):
            if level == 0:
                logger.initLogger(console=mylar.QUIET, log_dir=mylar.CONFIG.LOG_DIR, max_logsize=mylar.CONFIG.MAX_LOGSIZE, max_logfiles=mylar.CONFIG.MAX_LOGFILES, loglevel=level)
            else:
                logger.initLogger(console=not mylar.QUIET, log_dir=mylar.CONFIG.LOG_DIR, max_logsize=mylar.CONFIG.MAX_LOGSIZE, max_logfiles=mylar.CONFIG.MAX_LOGFILES, loglevel=mylar.LOG_LEVEL)
        else:
            logger.mylar_log.stopLogger()
            logger.mylar_log.initLogger(loglevel=mylar.LOG_LEVEL, log_dir=mylar.CONFIG.LOG_DIR, max_logsize=mylar.CONFIG.MAX_LOGSIZE, max_logfiles=mylar.CONFIG.MAX_LOGFILES)

        if level is not None:
            # this is for maintenance mode so that it returns without notice.
            return
        elif mylar.LOG_LEVEL == 2:
            logger.info("Verbose (DEBUG) logging is enabled")
            logger.debug("If you can read this message, debug logging is now working")
        else:
            logger.info("normal (INFO) logging is now enabled")
        logger.info('config file has been loaded from: %s' % mylar.CONFIG_FILE)
        raise cherrypy.HTTPRedirect("logs")
    toggleVerbose.exposed = True

    def getLog(self, iDisplayStart=0, iDisplayLength=100, iSortCol_0=0, sSortDir_0="desc", sSearch="", **kwargs):
        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        filtered = []
        if sSearch == "" or sSearch == None:
            filtered = mylar.LOGLIST[::]
        else:
            filtered = [row for row in mylar.LOGLIST for column in row if sSearch.lower() in column.lower()]
        sortcolumn = 0
        if iSortCol_0 == '1':
            sortcolumn = 2
        elif iSortCol_0 == '2':
            sortcolumn = 1
        filtered.sort(key=lambda x: x[sortcolumn], reverse=sSortDir_0 == "desc")
        if iDisplayLength != -1:
            rows = filtered[iDisplayStart:(iDisplayStart + iDisplayLength)]
        else:
            rows = filtered
        rows = [[row[0], row[2], row[1]] for row in rows]
        return json.dumps({
            'iTotalDisplayRecords': len(filtered),
            'iTotalRecords': len(mylar.LOGLIST),
            'aaData': rows,
        })
    getLog.exposed = True

    def getConfig(self, iDisplayStart=0, iDisplayLength=100, iSortCol_0=0, sSortDir_0="desc", sSearch="", **kwargs):
        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        unfiltered = []
        for each_section in mylar.config.config.sections():
            for k,v in mylar.config.config.items(each_section):
                unfiltered.insert( 0, (k, v) )

        if sSearch == "" or sSearch == None:
            logger.info('getConfig: No search terms.')
            filtered = unfiltered
        else:
            logger.info('getConfig: Searching for ' + sSearch)
            dSearch = {sSearch: '.'}
            filtered = [row for row in unfiltered for column in row if sSearch.lower() in column.lower()]
        sortcolumn = 0
        if iSortCol_0 == '1':
            sortcolumn = 2
        elif iSortCol_0 == '2':
            sortcolumn = 1
        filtered.sort(key=lambda x: x[sortcolumn], reverse=sSortDir_0 == "desc")
        rows = filtered[iDisplayStart:(iDisplayStart + iDisplayLength)]
        return json.dumps({
            'iTotalDisplayRecords': len(filtered),
            'iTotalRecords': len(unfiltered),
            'aaData': rows,
        })
    getConfig.exposed = True

    def clearhistory(self, status_type=None):
        myDB = db.DBConnection()
        if status_type == 'all':
            logger.info("Clearing all history")
            myDB.action('DELETE from snatched')
        else:
            logger.info("Clearing history where status is %s" % status_type)
            myDB.action('DELETE from snatched WHERE Status=?', [status_type])
            if status_type == 'Processed':
                myDB.action("DELETE from snatched WHERE Status='Post-Processed'")
        raise cherrypy.HTTPRedirect("history")
    clearhistory.exposed = True

    def downloadLocal(self, IssueID=None, IssueArcID=None, ReadOrder=None, dir=None):
        myDB = db.DBConnection()
        issueDL = myDB.selectone("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
        comicid = issueDL['ComicID']
        #print ("comicid: " + str(comicid))
        comic = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [comicid]).fetchone()
        #---issue info
        comicname = comic['ComicName']
        issuenum = issueDL['Issue_Number']
        issuedate = issueDL['IssueDate']
        seriesyear = comic['ComicYear']
        #---
        issueLOC = comic['ComicLocation']
        #print ("IssueLOC: " + str(issueLOC))
        issueFILE = issueDL['Location']
        #print ("IssueFILE: "+ str(issueFILE))
        issuePATH = os.path.join(issueLOC, issueFILE)
        #print ("IssuePATH: " + str(issuePATH))

        # if dir is None, it's a normal copy to cache kinda thing.
        # if dir is a path, then it's coming from the pullist as the location to put all the weekly comics
        if dir is not None:
            dstPATH = dir
        else:
            dstPATH = os.path.join(mylar.CONFIG.CACHE_DIR, issueFILE)
        #print ("dstPATH: " + str(dstPATH))
        if IssueID:
            ISnewValueDict = {'inCacheDIR':  'True',
                            'Location':    issueFILE}

        if IssueArcID:
            if mylar.CONFIG.READ2FILENAME:
                #if it's coming from a StoryArc, check to see if we're appending the ReadingOrder to the filename
                ARCissueFILE = ReadOrder + "-" + issueFILE
                dstPATH = os.path.join(mylar.CONFIG.CACHE_DIR, ARCissueFILE)
                ISnewValueDict = {'inCacheDIR': 'True',
                                'Location':   issueFILE}

#            issueDL = myDB.action("SELECT * FROM storyarcs WHERE IssueArcID=?", [IssueArcID]).fetchone()
#            storyarcid = issueDL['StoryArcID']
#            #print ("comicid: " + str(comicid))
#            issueLOC = mylar.CONFIG.DESTINATION_DIR
#            #print ("IssueLOC: " + str(issueLOC))
#            issueFILE = issueDL['Location']
#            #print ("IssueFILE: "+ str(issueFILE))
#            issuePATH = os.path.join(issueLOC,issueFILE)
#            #print ("IssuePATH: " + str(issuePATH))
#            dstPATH = os.path.join(mylar.CONFIG.CACHE_DIR, issueFILE)
#            #print ("dstPATH: " + str(dstPATH))

        try:
            shutil.copy2(issuePATH, dstPATH)
        except IOError as e:
            logger.error("Could not copy " + str(issuePATH) + " to " + str(dstPATH) + ". Copy to Cache terminated.")
            raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % comicid)

        #logger.debug("sucessfully copied to cache...Enabling Download link")

        controlValueDict = {'IssueID': IssueID}
        RLnewValueDict = {'inCacheDIR':  'True',
                          'Location':    issueFILE,
                          'ComicID':     comicid,
                          'ComicName':   comicname,
                          'Issue_Number': issuenum,
                          'SeriesYear':  seriesyear,
                          'IssueDate':   issuedate}
        myDB.upsert("readlist", RLnewValueDict, controlValueDict)
        myDB.upsert("issues", ISnewValueDict, controlValueDict)
        if IssueArcID:
            controlValueD = {'IssueArcID':  IssueArcID}
            newValueDict = {'inCacheDIR': 'True',
                            'Location':   ARCissueFILE}
            myDB.upsert("storyarcs", newValueDict, controlValueD)
        #print("DB updated - Download link now enabled.")

    downloadLocal.exposed = True

    def MassWeeklyDownload(self, weeknumber=None, year=None, midweek=None, weekfolder=0, filename=None):
        if filename is None:
            mylar.CONFIG.WEEKFOLDER = bool(int(weekfolder))
            mylar.CONFIG.writeconfig(values={'weekfolder': mylar.CONFIG.WEEKFOLDER})
            raise cherrypy.HTTPRedirect("pullist")

        # this will download all downloaded comics from the weekly pull list and throw them
        # into a 'weekly' pull folder for those wanting to transfer directly to a 3rd party device.
        myDB = db.DBConnection()

        if mylar.CONFIG.WEEKFOLDER:
            if mylar.CONFIG.WEEKFOLDER_LOC:
                dstdir = mylar.CONFIG.WEEKFOLDER_LOC
            else:
                dstdir = mylar.CONFIG.DESTINATION_DIR
            if mylar.CONFIG.WEEKFOLDER_FORMAT == 0:
                #0 = YYYY-mm
                desdir = os.path.join(dstdir, str(year) + '-' + str(weeknumber))
            elif mylar.CONFIG.WEEKFOLDER_FORMAT == 1:
                #1 = YYYY-mm-dd (midweek)
                desdir = os.path.join(dstdir, str(midweek))

            chkdir = filechecker.validateAndCreateDirectory(desdir, create=True, module='WEEKLY-FOLDER')
            if not chkdir:
                logger.warn('Unable to create weekly directory. Check location & permissions. Aborting Copy.')
                return
        else:
            desdir = mylar.CONFIG.GRABBAG_DIR

        issuelist = helpers.listIssues(weeknumber,year)
        if issuelist is None:   # nothing on the list, just go go gone
            logger.info("There aren't any issues downloaded from this week yet.")
        else:
            iscount = 0
            for issue in issuelist:
                #logger.fdebug('Checking status of ' + issue['ComicName'] + ' #' + str(issue['Issue_Number']))
                if issue['Status'] == 'Downloaded':
                    logger.info('Status Downloaded.')
                    self.downloadLocal(issue['IssueID'], dir=desdir)
                    logger.info("Copied " + issue['ComicName'] + " #" + str(issue['Issue_Number']) + " to " + desdir) #.encode('utf-8').strip())
                    iscount+=1

            logger.info('I have copied ' + str(iscount) + ' issues from week #' + str(weeknumber) + ' pullist as requested.')
        raise cherrypy.HTTPRedirect("pullist?week=%s&year=%s" % (weeknumber, year))
    MassWeeklyDownload.exposed = True

    def idirectory(self):
        return serve_template(templatename="idirectory.html", title="Import a Directory")
    idirectory.exposed = True

    def confirmResult(self, comicname, comicid):
        mode='series'
        sresults = mb.findComic(comicname, mode, None)
        type='comic'
        return serve_template(templatename="searchresults.html", title='Import Results for: "' + comicname + '"', searchresults=sresults, type=type, imported='confirm', ogcname=comicid)
    confirmResult.exposed = True

    def Check_ImportStatus(self):
        #logger.info('import_status: ' + mylar.IMPORT_STATUS)
        return mylar.IMPORT_STATUS
    Check_ImportStatus.exposed = True

    def comicScan(self, path, scan=0, libraryscan=0, redirect=None, autoadd=0, imp_move=0, imp_paths=0, imp_rename=0, imp_metadata=0, imp_seriesfolders=0, forcescan=0):
        import queue
        queue = queue.Queue()

        importoptions = {'comic_dir':              path,
                         'imp_move':               bool(imp_move),
                         'imp_rename':             bool(imp_rename),
                         'imp_metadata':           bool(imp_metadata),
                         'imp_paths':              bool(imp_paths),
                         'imp_seriesfolders':      bool(imp_seriesfolders),
                         'add_comics':             bool(autoadd)}

        mylar.CONFIG.configure(update=True)
        # Write the config
        logger.info('Now updating config...')
        mylar.CONFIG.writeconfig(values=importoptions)

        if mylar.IMPORTLOCK and bool(forcescan) is True:
            logger.info('Removing Current lock on import - if you do this AND another process is legitimately running, your causing your own problems.')
            mylar.IMPORTLOCK = False

        #thread the scan.
        if bool(scan) is True:
            scan = True
            mylar.IMPORT_STATUS = 'Now starting the import'
            return self.ThreadcomicScan(scan, queue)
        else:
            scan = False
            return
    comicScan.exposed = True

    def ThreadcomicScan(self, scan, queue):
        thread_ = threading.Thread(target=librarysync.scanLibrary, name="LibraryScan", args=[scan, queue])
        thread_.start()
        thread_.join()
        chk = queue.get()
        while True:
            if chk[0]['result'] == 'success':
                yield chk[0]['result']
                logger.info('Successfully scanned in directory. Enabling the importResults button now.')
                mylar.IMPORTBUTTON = True   #globally set it to ON after the scan so that it will be picked up.
                mylar.IMPORT_STATUS = 'Import completed.'
                break
            else:
                yield chk[0]['result']
                mylar.IMPORTBUTTON = False
                break
        return
    ThreadcomicScan.exposed = True

    def importResults(self):
        myDB = db.DBConnection()
        results = myDB.select("SELECT * FROM importresults WHERE WatchMatch is Null OR WatchMatch LIKE 'C%' group by DynamicName, Volume, Status COLLATE NOCASE")
        #this is to get the count of issues;
        res = []
        countit = []
        ann_cnt = 0
        for result in results:
            res.append(result)
        for x in res:
            if x['Volume']:
                #because Volume gets stored as NULL in the db, we need to account for it coming into here as a possible None value.
                countthis = myDB.select("SELECT count(*) FROM importresults WHERE DynamicName=? AND Volume=? AND Status=?", [x['DynamicName'],x['Volume'],x['Status']])
                countannuals = myDB.select("SELECT count(*) FROM importresults WHERE DynamicName=? AND Volume=? AND IssueNumber LIKE 'Annual%' AND Status=?", [x['DynamicName'],x['Volume'],x['Status']])
            else:
                countthis = myDB.select("SELECT count(*) FROM importresults WHERE DynamicName=? AND Volume IS NULL AND Status=?", [x['DynamicName'],x['Status']])
                countannuals = myDB.select("SELECT count(*) FROM importresults WHERE DynamicName=? AND Volume IS NULL AND IssueNumber LIKE 'Annual%' AND Status=?", [x['DynamicName'],x['Status']])
            countit.append({"DynamicName":  x['DynamicName'],
                            "Volume":       x['Volume'],
                            "IssueCount":   countthis[0][0],
                            "AnnualCount":  countannuals[0][0],
                            "ComicName":    x['ComicName'],
                            "DisplayName":  x['DisplayName'],
                            "Volume":       x['Volume'],
                            "ComicYear":    x['ComicYear'],
                            "Status":       x['Status'],
                            "ComicID":      x['ComicID'],
                            "WatchMatch":   x['WatchMatch'],
                            "ImportDate":   x['ImportDate'],
                            "SRID":         x['SRID']})

        return serve_template(templatename="importresults.html", title="Import Results", results=countit) #results, watchresults=watchresults)
    importResults.exposed = True

    def ImportFilelisting(self, comicname, dynamicname, volume):
        comicname = urllib.parse.unquote_plus(comicname)
        dynamicname = urllib.parse.unquote_plus(dynamicname) #urllib.unquote(dynamicname).decode('utf-8')
        myDB = db.DBConnection()
        if volume is None or volume == 'None':
            results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume IS NULL",[dynamicname])
        else:
            if not volume.lower().startswith('v'):
                volume = 'v' + str(volume)
            results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume=?",[dynamicname,volume])

        filelisting = '<table width="500"><tr><td>'
        filelisting += '<center><b>Files that have been scanned in for:</b></center>'
        if volume is None or volume == 'None':
            filelisting += '<center><b>' + comicname + '</b></center></td></tr><tr><td>'
        else:
            filelisting += '<center><b>' + comicname + ' [' + str(volume) + ']</b></center></td></tr><tr><td>'
        #filelisting += '<div style="height:300px;overflow:scroll;overflow-x:hidden;">'
        filelisting += '<div style="display:inline-block;overflow-y:auto:overflow-x:hidden;">'
        cnt = 0
        for result in results:
            filelisting += result['ComicFilename'] + '</br>'
        filelisting += '</div></td></tr>'
        filelisting += '<tr><td align="right">' + str(len(results)) + ' Files.</td></tr>'
        filelisting += '</table>'
        return filelisting
    ImportFilelisting.exposed = True

    def deleteimport(self, ComicName, volume, DynamicName, Status):
        myDB = db.DBConnection()
        if volume is None or volume == 'None':
            logname = ComicName
        else:
            logname = ComicName + '[' + str(volume) + ']'
        logger.info("Removing import data for Comic: " + logname)
        if volume is None or volume == 'None':
            myDB.action("DELETE from importresults WHERE DynamicName=? AND Status=? AND (Volume is NULL OR Volume='None')", [DynamicName, Status])
        else:
            myDB.action('DELETE from importresults WHERE DynamicName=? AND Volume=? AND Status=?', [DynamicName, volume, Status])
        raise cherrypy.HTTPRedirect("importResults")
    deleteimport.exposed = True

    def preSearchit(self, ComicName, comiclist=None, mimp=0, volume=None, displaycomic=None, comicid=None, dynamicname=None, displayline=None):
        if mylar.IMPORTLOCK:
            logger.info('[IMPORT] There is an import already running. Please wait for it to finish, and then you can resubmit this import.')
            return
        importlock = threading.Lock()
        myDB = db.DBConnection()

        if mimp == 0:
            comiclist = []
            comiclist.append({"ComicName":   ComicName,
                              "DynamicName": dynamicname,
                              "Volume":      volume,
                              "ComicID":     comicid})

        with importlock:
            #set the global importlock here so that nothing runs and tries to refresh things simultaneously...
            mylar.IMPORTLOCK = True
            #do imports that have the comicID already present (ie. metatagging has returned valid hits).
            #if a comicID is present along with an IssueID - then we have valid metadata.
            #otherwise, comicID present by itself indicates a watch match that already exists and is done below this sequence.
            RemoveIDS = []
            for comicinfo in comiclist:
                logger.fdebug('[IMPORT] Checking for any valid ComicID\'s already present within filenames.')
                logger.fdebug('[IMPORT] %s:' % comicinfo)
                if comicinfo['ComicID'] is None or comicinfo['ComicID'] == 'None':
                    continue
                else:
                    results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND ComicID=?", [comicinfo['ComicID']])
                    files = []
                    for result in results:
                        files.append({'comicfilename': result['ComicFilename'],
                                      'comiclocation': result['ComicLocation'],
                                      'issuenumber':   result['IssueNumber'],
                                      'import_id':     result['impID']})

                    SRID = str(random.randint(100000, 999999))

                    logger.info('[IMPORT] Issues found with valid ComicID information for : %s [%s]' % (comicinfo['ComicName'], comicinfo['ComicID']))
                    imported = {'ComicName':     comicinfo['ComicName'],
                                'DynamicName':   comicinfo['DynamicName'],
                                'Volume':        comicinfo['Volume'],
                                'filelisting':   files,
                                'srid':          SRID}
                    self.addbyid(comicinfo['ComicID'], calledby=True, imported=imported, ogcname=comicinfo['ComicName'], nothread=True)

                    #if move files wasn't used - we need to update status at this point.
                    #if mylar.CONFIG.IMP_MOVE is False:
                    #    #status update.
                    #    for f in files:
                    #        ctrlVal = {"ComicID":     comicinfo['ComicID'],
                    #                   "impID":       f['import_id']}
                    #        newVal = {"Status":            'Imported',
                    #                  "SRID":              SRID,
                    #                  "ComicFilename":     f['comicfilename'],
                    #                  "ComicLocation":     f['comiclocation'],
                    #                  "Volume":            comicinfo['Volume'],
                    #                  "IssueNumber":       comicinfo['IssueNumber'],
                    #                  "ComicName":         comicinfo['ComicName'],
                    #                  "DynamicName":       comicinfo['DynamicName']}
                    #        myDB.upsert("importresults", newVal, ctrlVal)
                    logger.info('[IMPORT] Successfully verified import sequence data for : %s. Currently adding to your watchlist.' % comicinfo['ComicName'])
                    RemoveIDS.append(comicinfo['ComicID'])

            #we need to remove these items from the comiclist now, so they don't get processed again
            if len(RemoveIDS) > 0:
                for RID in RemoveIDS:
                    newlist = [k for k in comiclist if k['ComicID'] != RID]
                    comiclist = newlist

            for cl in comiclist:
                ComicName = cl['ComicName']
                volume = cl['Volume']
                DynamicName = cl['DynamicName']
                #logger.fdebug('comicname: ' + ComicName)
                #logger.fdebug('dyn: ' + DynamicName)

                if volume is None or volume == 'None':
                    comic_and_vol = ComicName
                else:
                    comic_and_vol = '%s (%s)' % (ComicName, volume)
                logger.info('[IMPORT][%s] Now preparing to import. First I need to determine the highest issue, and possible year(s) of the series.' % comic_and_vol)
                if volume is None or volume == 'None':
                    logger.fdebug('[IMPORT] [none] dynamicname: %s' % DynamicName)
                    logger.fdebug('[IMPORT] [none] volume: None')

                    results = myDB.select("SELECT * FROM importresults WHERE DynamicName=? AND Volume IS NULL AND Status='Not Imported'", [DynamicName])
                else:
                    logger.fdebug('[IMPORT] [!none] dynamicname: %s' % DynamicName)
                    logger.fdebug('[IMPORT] [!none] volume: %s' % volume)
                    results = myDB.select("SELECT * FROM importresults WHERE DynamicName=? AND Volume=? AND Status='Not Imported'", [DynamicName,volume])

                if not results:
                    logger.fdebug('[IMPORT] I cannot find any results for the given series. I should remove this from the list.')
                    continue
                #if results > 0:
                #    print ("There are " + str(results[7]) + " issues to import of " + str(ComicName))
                #build the valid year ranges and the minimum issue# here to pass to search.
                yearRANGE = []
                yearTOP = 0
                minISSUE = 0
                startISSUE = 10000000
                starttheyear = None
                comicstoIMP = []

                movealreadyonlist = "no"
                movedata = []

                for result in results:
                    if result is None or result == 'None':
                       logger.info('[IMPORT] Ultron gave me bad information, this issue wont import correctly: %s' & DynamicName)
                       break

                    if result['WatchMatch']:
                        watchmatched = result['WatchMatch']
                    else:
                        watchmatched = ''

                    if watchmatched.startswith('C'):
                        comicid = result['WatchMatch'][1:]
                        #since it's already in the watchlist, we just need to move the files and re-run the filechecker.
                        #self.refreshArtist(comicid=comicid,imported='yes')
                        if mylar.CONFIG.IMP_MOVE:
                            comloc = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [comicid]).fetchone()

                            movedata_comicid = comicid
                            movedata_comiclocation = comloc['ComicLocation']
                            movedata_comicname = ComicName
                            movealreadyonlist = "yes"
                            #mylar.moveit.movefiles(comicid,comloc['ComicLocation'],ComicName)
                            #check for existing files... (this is already called after move files in importer)
                            #updater.forceRescan(comicid)
                        else:
                            raise cherrypy.HTTPRedirect("importResults")
                    else:
                        #logger.fdebug('result: %s' % result)
                        comicstoIMP.append(result['ComicLocation']) #.decode(mylar.SYS_ENCODING, 'replace'))
                        getiss = result['IssueNumber']
                        #logger.fdebug('getiss: %s' % getiss)
                        if getiss is None:
                            logger.fdebug('[IMPORT] Unable to determine a valid issue number. The import process will currrently only work'
                                          'with filenames that have an issue number in it. Ignoring this filename for import (you should'
                                          'probably move it manually. [%s]' % result['ComicLocation'])
                            continue
                        else:
                            if 'annual' in getiss.lower():
                                tmpiss = re.sub('[^0-9]','', getiss).strip()
                                if any([tmpiss.startswith('19'), tmpiss.startswith('20')]) and len(tmpiss) == 4:
                                    logger.fdebug('[IMPORT] annual detected with no issue [%s]. Skipping this entry for determining series length.' % getiss)
                                    continue
                            else:
                                if (result['ComicYear'] not in yearRANGE) or all([yearRANGE is None, yearRANGE == 'None']):
                                    if result['ComicYear'] != "0000" and result['ComicYear'] is not None:
                                        yearRANGE.append(str(result['ComicYear']))
                                        yearTOP = str(result['ComicYear'])
                                getiss_num = helpers.issue_number_parser(getiss).asInt
                                miniss_num = helpers.issue_number_parser(minISSUE).asInt
                                startiss_num = helpers.issue_number_parser(startISSUE).asInt
                                if int(getiss_num) > int(miniss_num):
                                    logger.fdebug('Minimum issue now set to : %s - it was %s' % (getiss, minISSUE))
                                    minISSUE = getiss
                                if int(getiss_num) < int(startiss_num):
                                    logger.fdebug('Start issue now set to : %s - it was %s' % (getiss, startISSUE))
                                    startISSUE = str(getiss)
                                    if helpers.issue_number_parser(startISSUE).asInt == helpers.issue_number_to_int(1,None) and result['ComicYear'] is not None:  # if it's an issue #1, get the year and assume that's the start.
                                        startyear = result['ComicYear']

                #taking this outside of the transaction in an attempt to stop db locking.
                if mylar.CONFIG.IMP_MOVE and movealreadyonlist == "yes":
                     mylar.moveit.movefiles(movedata_comicid, movedata_comiclocation, movedata_comicname)
                     updater.forceRescan(comicid)
                     raise cherrypy.HTTPRedirect("importResults")

                #figure out # of issues and the year range allowable
                logger.fdebug('[IMPORT] yearTOP: %s' % yearTOP)
                logger.fdebug('[IMPORT] yearRANGE: %s' % yearRANGE)
                if starttheyear is None:
                    if all([yearTOP != None, yearTOP != 'None']):
                        if int(str(yearTOP)) > 0:
                            minni = helpers.issue_number_parser(minISSUE).asInt
                            #logger.info(minni)
                            if minni < 1 or minni > 999999999:
                                maxyear = int(str(yearTOP))
                            else:
                                maxyear = int(str(yearTOP)) - ( (minni/1000) / 12 )
                            if str(maxyear) not in yearRANGE:
                                #logger.info('maxyear:' + str(maxyear))
                                #logger.info('yeartop:' + str(yearTOP))
                                for i in range(int(maxyear), int(yearTOP),1):
                                    if not any(int(x) == int(i) for x in yearRANGE):
                                        yearRANGE.append(str(i))
                        else:
                            yearRANGE = None
                    else:
                        yearRANGE = None
                else:
                    yearRANGE.append(starttheyear)

                if yearRANGE is not None:
                    yearRANGE = sorted(yearRANGE, reverse=True)
                #determine a best-guess to # of issues in series
                #this needs to be reworked / refined ALOT more.
                #minISSUE = highest issue #, startISSUE = lowest issue #
                numissues = len(comicstoIMP)
                logger.fdebug('[IMPORT] number of issues: %s' % numissues)
                ogcname = ComicName

                mode='series'
                displaycomic = helpers.filesafe(ComicName)
                if 'one-shot' not in displaycomic.lower():
                    displaycomic = re.sub('[\-]','', displaycomic).strip()
                displaycomic = re.sub('\s+', ' ', displaycomic).strip()
                logger.fdebug('[IMPORT] displaycomic : %s' % displaycomic)
                logger.fdebug('[IMPORT] comicname : %s' % ComicName)
                searchterm = '"' + displaycomic + '"'
                try:
                    if yearRANGE is None:
                        sresults = mb.findComic(searchterm, mode, issue=numissues) #ogcname, mode, issue=numissues, explicit='all') #ComicName, mode, issue=numissues)
                    else:
                        sresults = mb.findComic(searchterm, mode, issue=numissues, limityear=yearRANGE) #ogcname, mode, issue=numissues, limityear=yearRANGE, explicit='all') #ComicName, mode, issue=numissues, limityear=yearRANGE)
                except TypeError:
                    logger.warn('[IMPORT] Comicvine API limit has been reached, and/or the comicvine website is not responding. Aborting process at this time, try again in an ~ hr when the api limit is reset.')
                    break
                else:
                    if sresults is False:
                        sresults = []

                #we now need to cycle through the results until we get a hit on both dynamicname AND year (~count of issues possibly).
                logger.fdebug('[IMPORT] [%s] search results' % len(sresults))
                search_matches = []
                for results in sresults:
                    rsn = filechecker.FileChecker()
                    rsn_run = rsn.dynamic_replace(results['name'])
                    result_name = rsn_run['mod_seriesname']
                    result_comicid = results['comicid']
                    result_year = results['comicyear']
                    if float(int(results['issues']) / 12):
                        totalissues = (int(results['issues']) / 12) + 1
                    else:
                        totalissues = int(results['issues']) / 12

                    totalyear_range = int(result_year) + totalissues    #2000 + (101 / 12) 2000 +8.4 = 2008
                    logger.fdebug('[IMPORT] [%s] Comparing: %s - TO - %s' % (totalyear_range, re.sub('[\|\s]', '', DynamicName.lower()).strip(), re.sub('[\|\s]', '', result_name.lower()).strip()))
                    if any([str(totalyear_range) in results['seriesrange'], result_year in results['seriesrange']]):
                        logger.fdebug('[IMPORT] LastIssueID: %s' % results['lastissueid'])
                        if re.sub('[\|\s]', '', DynamicName.lower()).strip() ==  re.sub('[\|\s]', '', result_name.lower()).strip():
                            logger.fdebug('[IMPORT MATCH] %s (%s)' % (result_name, result_comicid))
                            search_matches.append({'comicid':       results['comicid'],
                                                   'series':        results['name'],
                                                   'dynamicseries': result_name,
                                                   'seriesyear':    result_year,
                                                   'publisher':     results['publisher'],
                                                   'haveit':        results['haveit'],
                                                   'name':          results['name'],
                                                   'deck':          results['deck'],
                                                   'url':           results['url'],
                                                   'description':   results['description'],
                                                   'comicimage':    results['comicimage'],
                                                   'issues':        results['issues'],
                                                   'ogcname':       ogcname,
                                                   'comicyear':     results['comicyear']})

                if len(search_matches) == 1:
                    sr = search_matches[0]
                    logger.info('[IMPORT] There is only one result...automagik-mode enabled for %s :: %s' % (sr['series'], sr['comicid']))
                    resultset = 1
                else:
                    if len(search_matches) == 0 or len(search_matches) is None:
                        logger.fdebug("[IMPORT] no results, removing the year from the agenda and re-querying.")
                        sresults = mb.findComic(searchterm, mode, issue=numissues) #ComicName, mode, issue=numissues)
                        logger.fdebug('[IMPORT] [%s] search results' % len(sresults))
                        for results in sresults:
                            rsn = filechecker.FileChecker()
                            rsn_run = rsn.dynamic_replace(results['name'])
                            result_name = rsn_run['mod_seriesname']
                            result_comicid = results['comicid']
                            result_year = results['comicyear']
                            if float(int(results['issues']) / 12):
                                totalissues = (int(results['issues']) / 12) + 1
                            else:
                                totalissues = int(results['issues']) / 12

                            totalyear_range = int(result_year) + totalissues    #2000 + (101 / 12) 2000 +8.4 = 2008
                            logger.fdebug('[IMPORT][%s] Comparing: %s - TO - %s' % (totalyear_range, re.sub('[\|\s]', '', DynamicName.lower()).strip(), re.sub('[\|\s]', '', result_name.lower()).strip()))
                            if any([str(totalyear_range) in results['seriesrange'], result_year in results['seriesrange']]):
                                if re.sub('[\|\s]', '', DynamicName.lower()).strip() ==  re.sub('[\|\s]', '', result_name.lower()).strip():
                                    logger.fdebug('[IMPORT MATCH] %s (%s)' % (result_name, result_comicid))
                                    search_matches.append({'comicid':       results['comicid'],
                                                           'series':        results['name'],
                                                           'dynamicseries': result_name,
                                                           'seriesyear':    result_year,
                                                           'publisher':     results['publisher'],
                                                           'haveit':        results['haveit'],
                                                           'name':          results['name'],
                                                           'deck':          results['deck'],
                                                           'url':           results['url'],
                                                           'description':   results['description'],
                                                           'comicimage':    results['comicimage'],
                                                           'issues':        results['issues'],
                                                           'ogcname':       ogcname,
                                                           'comicyear':     results['comicyear']})

                        if len(search_matches) == 1:
                            sr = search_matches[0]
                            logger.info('[IMPORT] There is only one result...automagik-mode enabled for %s :: %s' % (sr['series'], sr['comicid']))
                            resultset = 1
                        else:
                            resultset = 0
                    else:
                        logger.info('[IMPORT] Returning results to Select option - there are %s possibilities, manual intervention required.' % len(search_matches))
                        resultset = 0

                #generate random Search Results ID to allow for easier access for viewing logs / search results.

                SRID = str(random.randint(100000, 999999))

                    #link the SRID to the series that was just imported so that it can reference the search results when requested.

                if volume is None or volume == 'None':
                    ctrlVal = {"DynamicName": DynamicName}
                else:
                    ctrlVal = {"DynamicName": DynamicName,
                               "Volume":      volume}

                if len(sresults) > 1 or len(search_matches) > 1:
                    newVal = {"SRID":         SRID,
                              "Status":       'Manual Intervention',
                              "ComicName":    ComicName}
                else:
                    newVal = {"SRID":         SRID,
                              "Status":       'Importing',
                              "ComicName":    ComicName}
                myDB.upsert("importresults", newVal, ctrlVal)

                if resultset == 0:
                    if len(search_matches) > 1:
                       # if we matched on more than one series above, just save those results instead of the entire search result set.
                        for sres in search_matches:
                            try:
                                if type(sres['haveit']) is dict:
                                    imp_cid = sres['haveit']['comicid']
                                else:
                                    imp_cid = sres['haveit']
                            except Exception as e:
                                imp_cid = sres['haveit']

                            cVal = {"SRID":        SRID,
                                    "comicid":     sres['comicid']}
                            #should store ogcname in here somewhere to account for naming conversions above.
                            nVal = {"Series":      ComicName,
                                    "results":     len(search_matches),
                                    "publisher":   sres['publisher'],
                                    "haveit":      imp_cid,
                                    "name":        sres['name'],
                                    "deck":        sres['deck'],
                                    "url":         sres['url'],
                                    "description":  sres['description'],
                                    "comicimage":  sres['comicimage'],
                                    "issues":      sres['issues'],
                                    "ogcname":     ogcname,
                                    "comicyear":   sres['comicyear']}
                            logger.fdebug('search_values: [%s]/%s' % (cVal, nVal))
                            myDB.upsert("searchresults", nVal, cVal)
                        logger.info('[IMPORT] There is more than one result that might be valid - normally this is due to the filename(s) not having enough information for me to use (ie. no volume label/year). Manual intervention is required.')
                        #force the status here just in case
                        newVal = {'SRID':     SRID,
                                  'Status':   'Manual Intervention'}
                        myDB.upsert("importresults", newVal, ctrlVal)

                    elif len(sresults) > 1:
                        # store the search results for series that returned more than one result for user to select later / when they want.
                        # should probably assign some random numeric for an id to reference back at some point.
                        for sres in sresults:
                            try:
                                if type(sres['haveit']) == dict:
                                    imp_cid = sres['haveit']['comicid']
                                else:
                                    imp_cid = sres['haveit']
                            except Exception as e:
                                imp_cid = sres['haveit']

                            cVal = {"SRID":        SRID,
                                    "comicid":     sres['comicid']}
                            #should store ogcname in here somewhere to account for naming conversions above.
                            nVal = {"Series":      ComicName,
                                    "results":     len(sresults),
                                    "publisher":   sres['publisher'],
                                    "haveit":      imp_cid,
                                    "name":        sres['name'],
                                    "deck":        sres['deck'],
                                    "url":         sres['url'],
                                    "description":  sres['description'],
                                    "comicimage":  sres['comicimage'],
                                    "issues":      sres['issues'],
                                    "ogcname":     ogcname,
                                    "comicyear":   sres['comicyear']}
                            myDB.upsert("searchresults", nVal, cVal)
                        logger.info('[IMPORT] There is more than one result that might be valid - normally this is due to the filename(s) not having enough information for me to use (ie. no volume label/year). Manual intervention is required.')
                        #force the status here just in case
                        newVal = {'SRID':     SRID,
                                  'Status':   'Manual Intervention'}
                        myDB.upsert("importresults", newVal, ctrlVal)
                    else:
                        logger.info('[IMPORT] Could not find any matching results against CV. Check the logs and perhaps rename the attempted file(s)')
                        newVal = {'SRID':     SRID,
                                  'Status':   'No Results'}
                        myDB.upsert("importresults", newVal, ctrlVal)

                else:
                    logger.info('[IMPORT] Now adding %s...' % ComicName)

                    if volume is None or volume == 'None':
                        results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume IS NULL",[DynamicName])
                    else:
                        if not volume.lower().startswith('v'):
                            volume = 'v' + str(volume)
                        results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume=?",[DynamicName,volume])
                    files = []
                    for result in results:
                        files.append({'comicfilename': result['ComicFilename'],
                                      'comiclocation': result['ComicLocation'],
                                      'issuenumber':   result['IssueNumber'],
                                      'import_id':     result['impID']})

                    imported = {'ComicName':     ComicName,
                                'DynamicName':   DynamicName,
                                'Volume':        volume,
                                'filelisting':   files,
                                'srid':          SRID}

                    self.addbyid(sr['comicid'], calledby=True, imported=imported, ogcname=ogcname, nothread=True)

        mylar.IMPORTLOCK = False
        logger.info('[IMPORT] Import completed.')

    preSearchit.exposed = True

    def importresults_popup(self, SRID, ComicName, imported=None, ogcname=None, DynamicName=None, Volume=None):
        myDB = db.DBConnection()
        resultset = myDB.select("SELECT * FROM searchresults WHERE SRID=?", [SRID])
        if not resultset:
            logger.warn('There are no search results to view for this entry ' + ComicName + ' [' + str(SRID) + ']. Something is probably wrong.')
            raise cherrypy.HTTPRedirect("importResults")

        searchresults = resultset
        if any([Volume is None, Volume == 'None']):
            results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume IS NULL",[DynamicName])
        else:
            if not Volume.lower().startswith('v'):
                volume = 'v' + str(Volume)
            else:
                volume = Volume
            results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume=?",[DynamicName,volume])
        files = []
        for result in results:
            files.append({'comicfilename': urllib.parse.quote(result['ComicFilename']),
                          'comiclocation': urllib.parse.quote(result['ComicLocation']),
                          'issuenumber':   result['IssueNumber'],
                          'import_id':     result['impID']})

        imported = {'ComicName':     ComicName,
                    'DynamicName':   DynamicName,
                    'Volume':        Volume,
                    'filelisting':   files,
                    'srid':          SRID}

        return serve_template(templatename="importresults_popup.html", title="results", searchtext=ComicName, searchresults=searchresults, imported=imported)

    importresults_popup.exposed = True

    def pretty_git(self, br_history):
        #in order to 'prettify' the history log for display, we need to break it down so it's line by line.
        br_split = br_history.split("\n")  #split it on each commit
        commit = []
        for br in br_split:
            commit_st = br.find('-')
            commitno = br[:commit_st].strip()
            time_end = br.find('-',commit_st+1)
            time = br[commit_st+1:time_end].strip()
            author_end = br.find('-', time_end+1)
            author = br[time_end+1:author_end].strip()
            desc = br[author_end+1:].strip()
            if len(desc) > 103:
                desc = '<span title="%s">%s...</span>' % (desc, desc[:103])
            if author != 'mylar3':
                pr_tag = True
                dspline = '[%s][PR] %s {<span style="font-size:11px">%s/%s</span>}'
            else:
                pr_tag = False
                dspline = '[%s] %s {<span style="font-size:11px">%s/%s</span>}'
            commit.append(dspline % ("<a href='https://github.com/mylar3/mylar3/commit/" + commitno + "'>"+commitno+"</a>", desc, time, author))

        return '<br />\n'.join(commit)

    pretty_git.exposed = True
    #---
    def config(self):
        interface_dir = os.path.join(mylar.PROG_DIR, 'data', 'interfaces')
        interface_list = [name for name in os.listdir(interface_dir) if os.path.isdir(os.path.join(interface_dir, name))]
#----
# to be implemented in the future.
        br_hist = 'This would be a nice place to see revision history...'
        if mylar.INSTALL_TYPE == 'git':
            try:
                branch_history = mylar.versioncheck.runGit('log --encoding=UTF-8 --pretty=format:"%h - %cr - %an - %s" -n 5')
                #here we pass the branch_history to the pretty_git module to break it down
                if branch_history:
                    br_hist = self.pretty_git(branch_history)
                    try:
                        br_hist = "" + br_hist.decode('utf-8')
                    except:
                        br_hist = br_hist
            except Exception as e:
                logger.fdebug('[ERROR] Unable to retrieve git revision history for some reason: %s' % e)
                br_hist = 'This would be a nice place to see revision history...'
#----
        myDB = db.DBConnection()
        CCOMICS = myDB.select("SELECT COUNT(*) FROM comics")
        CHAVES = myDB.select("SELECT COUNT(*) FROM issues WHERE Status='Downloaded' OR Status='Archived'")
        CISSUES = myDB.select("SELECT COUNT(*) FROM issues")
        CSIZE = myDB.select("select SUM(ComicSize) from issues where Status='Downloaded' or Status='Archived'")
        COUNT_COMICS = CCOMICS[0][0]
        COUNT_HAVES = CHAVES[0][0]
        COUNT_ISSUES = CISSUES[0][0]
        COUNT_SIZE = helpers.human_size(CSIZE[0][0])
        CCONTCOUNT = 0
        cti = helpers.havetotals()
        for cchk in cti:
            if cchk['recentstatus'] == 'Continuing':
                CCONTCOUNT += 1
        comicinfo = {"COUNT_COMICS": COUNT_COMICS,
                      "COUNT_HAVES": COUNT_HAVES,
                      "COUNT_ISSUES": COUNT_ISSUES,
                      "COUNT_SIZE": COUNT_SIZE,
                      "CCONTCOUNT": CCONTCOUNT}
        DLPROVSTATS = myDB.select("SELECT Provider, COUNT(Provider) AS Frequency FROM Snatched WHERE Status = 'Snatched' AND Provider is NOT NULL GROUP BY Provider ORDER BY Frequency DESC")
        freq = dict()
        freq_tot = 0
        for row in DLPROVSTATS:
            if any(['CBT' in row['Provider'], '32P' in row['Provider'], 'ComicBT' in row['Provider']]):
                try:
                    tmpval = freq['32P']
                    freq.update({'32P': tmpval + row['Frequency']})
                except:
                    freq.update({'32P': row['Frequency']})
            elif 'KAT' in row['Provider']:
                try:
                    tmpval = freq['KAT']
                    freq.update({'KAT': tmpval + row['Frequency']})
                except:
                    freq.update({'KAT': row['Frequency']})
            elif 'experimental' in row['Provider']:
                try:
                    tmpval = freq['Experimental']
                    freq.update({'Experimental': tmpval + row['Frequency']})
                except:
                    freq.update({'Experimental': row['Frequency']})


            elif [True for x in freq if re.sub("\(newznab\)", "", str(row['Provider'])).strip() in x]:
                try:
                    tmpval = freq[re.sub("\(newznab\)", "", row['Provider']).strip()]
                    freq.update({re.sub("\(newznab\)", "", row['Provider']).strip(): tmpval + row['Frequency']})
                except:
                    freq.update({re.sub("\(newznab\)", "", row['Provider']).strip(): row['Frequency']})
            else:
                freq.update({re.sub("\(newznab\)", "", row['Provider']).strip(): row['Frequency']})

            freq_tot += row['Frequency']

        dlprovstats = sorted(iter(freq.items()), key=itemgetter(1), reverse=True)

        if mylar.SCHED_RSS_LAST is None:
            rss_sclast = 'Unknown'
        else:
            rss_sclast = datetime.datetime.fromtimestamp(mylar.SCHED_RSS_LAST).replace(microsecond=0)

        py_check_pass = True
        chk_py_version = platform.python_version()
        if parse_version(chk_py_version) < parse_version(mylar.MINIMUM_PY_VERSION):
            py_check_pass = False

        config = {
                    "comicvine_api": mylar.CONFIG.COMICVINE_API,
                    "http_host": mylar.CONFIG.HTTP_HOST,
                    "http_user": mylar.CONFIG.HTTP_USERNAME,
                    "http_port": mylar.CONFIG.HTTP_PORT,
                    "http_root": mylar.CONFIG.HTTP_ROOT,
                    "http_pass": mylar.CONFIG.HTTP_PASSWORD,
                    "instance_name" : mylar.CONFIG.INSTANCE_NAME,
                    "host_return" : mylar.CONFIG.HOST_RETURN,
                    "enable_https": helpers.checked(mylar.CONFIG.ENABLE_HTTPS),
                    "https_cert": mylar.CONFIG.HTTPS_CERT,
                    "https_key": mylar.CONFIG.HTTPS_KEY,
                    "authentication": int(mylar.CONFIG.AUTHENTICATION),
                    "api_enabled": helpers.checked(mylar.CONFIG.API_ENABLED),
                    "api_key": mylar.CONFIG.API_KEY,
                    "launch_browser": helpers.checked(mylar.CONFIG.LAUNCH_BROWSER),
                    "auto_update": helpers.checked(mylar.CONFIG.AUTO_UPDATE),
                    "max_logsize": mylar.CONFIG.MAX_LOGSIZE,
                    "annuals_on": helpers.checked(mylar.CONFIG.ANNUALS_ON),
                    "enable_check_folder": helpers.checked(mylar.CONFIG.ENABLE_CHECK_FOLDER),
                    "check_folder": mylar.CONFIG.CHECK_FOLDER,
                    "download_scan_interval": mylar.CONFIG.DOWNLOAD_SCAN_INTERVAL,
                    "search_interval": mylar.CONFIG.SEARCH_INTERVAL,
                    "nzb_startup_search": helpers.checked(mylar.CONFIG.NZB_STARTUP_SEARCH),
                    "search_delay": mylar.CONFIG.SEARCH_DELAY,
                    "nzb_downloader_sabnzbd": helpers.radio(mylar.CONFIG.NZB_DOWNLOADER, 0),
                    "nzb_downloader_nzbget": helpers.radio(mylar.CONFIG.NZB_DOWNLOADER, 1),
                    "nzb_downloader_blackhole": helpers.radio(mylar.CONFIG.NZB_DOWNLOADER, 2),
                    "nzb_downloader_none": helpers.radio(mylar.CONFIG.NZB_DOWNLOADER, 3),
                    "sab_host": mylar.CONFIG.SAB_HOST,
                    "sab_user": mylar.CONFIG.SAB_USERNAME,
                    "sab_api": mylar.CONFIG.SAB_APIKEY,
                    "sab_pass": mylar.CONFIG.SAB_PASSWORD,
                    "sab_cat": mylar.CONFIG.SAB_CATEGORY,
                    "sab_priority": mylar.CONFIG.SAB_PRIORITY,
                    "sab_directory": mylar.CONFIG.SAB_DIRECTORY,
                    "sab_to_mylar": helpers.checked(mylar.CONFIG.SAB_TO_MYLAR),
                    "sab_version": mylar.CONFIG.SAB_VERSION,
                    "sab_client_post_processing": helpers.checked(mylar.CONFIG.SAB_CLIENT_POST_PROCESSING),
                    "sab_remove_completed": helpers.checked(mylar.CONFIG.SAB_REMOVE_COMPLETED),
                    "sab_remove_failed": helpers.checked(mylar.CONFIG.SAB_REMOVE_FAILED),
                    "nzbget_host": mylar.CONFIG.NZBGET_HOST,
                    "nzbget_sub": mylar.CONFIG.NZBGET_SUB,
                    "nzbget_port": mylar.CONFIG.NZBGET_PORT,
                    "nzbget_user": mylar.CONFIG.NZBGET_USERNAME,
                    "nzbget_pass": mylar.CONFIG.NZBGET_PASSWORD,
                    "nzbget_cat": mylar.CONFIG.NZBGET_CATEGORY,
                    "nzbget_priority": mylar.CONFIG.NZBGET_PRIORITY,
                    "nzbget_directory": mylar.CONFIG.NZBGET_DIRECTORY,
                    "nzbget_client_post_processing": helpers.checked(mylar.CONFIG.NZBGET_CLIENT_POST_PROCESSING),
                    "torrent_downloader_watchlist": helpers.radio(int(mylar.CONFIG.TORRENT_DOWNLOADER), 0),
                    "torrent_downloader_utorrent": helpers.radio(int(mylar.CONFIG.TORRENT_DOWNLOADER), 1),
                    "torrent_downloader_rtorrent": helpers.radio(int(mylar.CONFIG.TORRENT_DOWNLOADER), 2),
                    "torrent_downloader_transmission": helpers.radio(int(mylar.CONFIG.TORRENT_DOWNLOADER), 3),
                    "torrent_downloader_deluge": helpers.radio(int(mylar.CONFIG.TORRENT_DOWNLOADER), 4),
                    "torrent_downloader_qbittorrent": helpers.radio(int(mylar.CONFIG.TORRENT_DOWNLOADER), 5),
                    "utorrent_host": mylar.CONFIG.UTORRENT_HOST,
                    "utorrent_username": mylar.CONFIG.UTORRENT_USERNAME,
                    "utorrent_password": mylar.CONFIG.UTORRENT_PASSWORD,
                    "utorrent_label": mylar.CONFIG.UTORRENT_LABEL,
                    "rtorrent_host": mylar.CONFIG.RTORRENT_HOST,
                    "rtorrent_rpc_url": mylar.CONFIG.RTORRENT_RPC_URL,
                    "rtorrent_authentication": mylar.CONFIG.RTORRENT_AUTHENTICATION,
                    "rtorrent_ssl": helpers.checked(mylar.CONFIG.RTORRENT_SSL),
                    "rtorrent_verify": helpers.checked(mylar.CONFIG.RTORRENT_VERIFY),
                    "rtorrent_username": mylar.CONFIG.RTORRENT_USERNAME,
                    "rtorrent_password": mylar.CONFIG.RTORRENT_PASSWORD,
                    "rtorrent_directory": mylar.CONFIG.RTORRENT_DIRECTORY,
                    "rtorrent_label": mylar.CONFIG.RTORRENT_LABEL,
                    "rtorrent_startonload": helpers.checked(mylar.CONFIG.RTORRENT_STARTONLOAD),
                    "transmission_host": mylar.CONFIG.TRANSMISSION_HOST,
                    "transmission_username": mylar.CONFIG.TRANSMISSION_USERNAME,
                    "transmission_password": mylar.CONFIG.TRANSMISSION_PASSWORD,
                    "transmission_directory": mylar.CONFIG.TRANSMISSION_DIRECTORY,
                    "deluge_host": mylar.CONFIG.DELUGE_HOST,
                    "deluge_username": mylar.CONFIG.DELUGE_USERNAME,
                    "deluge_password": mylar.CONFIG.DELUGE_PASSWORD,
                    "deluge_label": mylar.CONFIG.DELUGE_LABEL,
                    "deluge_pause": helpers.checked(mylar.CONFIG.DELUGE_PAUSE),
                    "deluge_download_directory": mylar.CONFIG.DELUGE_DOWNLOAD_DIRECTORY,
                    "deluge_done_directory": mylar.CONFIG.DELUGE_DONE_DIRECTORY,
                    "qbittorrent_host": mylar.CONFIG.QBITTORRENT_HOST,
                    "qbittorrent_username": mylar.CONFIG.QBITTORRENT_USERNAME,
                    "qbittorrent_password": mylar.CONFIG.QBITTORRENT_PASSWORD,
                    "qbittorrent_label": mylar.CONFIG.QBITTORRENT_LABEL,
                    "qbittorrent_folder": mylar.CONFIG.QBITTORRENT_FOLDER,
                    "qbittorrent_loadaction": mylar.CONFIG.QBITTORRENT_LOADACTION,
                    "blackhole_dir": mylar.CONFIG.BLACKHOLE_DIR,
                    "usenet_retention": mylar.CONFIG.USENET_RETENTION,
                    "experimental": helpers.checked(mylar.CONFIG.EXPERIMENTAL),
                    "enable_torznab": helpers.checked(mylar.CONFIG.ENABLE_TORZNAB),
                    "extra_torznabs": sorted(mylar.CONFIG.EXTRA_TORZNABS, key=itemgetter(5), reverse=True),
                    "newznab": helpers.checked(mylar.CONFIG.NEWZNAB),
                    "extra_newznabs": sorted(mylar.CONFIG.EXTRA_NEWZNABS, key=itemgetter(5), reverse=True),
                    "enable_ddl": helpers.checked(mylar.CONFIG.ENABLE_DDL),
                    "enable_getcomics": helpers.checked(mylar.CONFIG.ENABLE_GETCOMICS),
                    "enable_airdcpp": helpers.checked(mylar.CONFIG.ENABLE_AIRDCPP),
                    "airdcpp_host": mylar.CONFIG.AIRDCPP_HOST,
                    "airdcpp_username": mylar.CONFIG.AIRDCPP_USERNAME,
                    "airdcpp_password": mylar.CONFIG.AIRDCPP_PASSWORD,
                    "airdcpp_download_dir": mylar.CONFIG.AIRDCPP_DOWNLOAD_DIR,
                    "airdcpp_hubs": mylar.CONFIG.AIRDCPP_HUBS,
                    "airdcpp_announce_hub": mylar.CONFIG.AIRDCPP_ANNOUNCE_HUB,
                    "airdcpp_announce_bots": mylar.CONFIG.AIRDCPP_ANNOUNCE_BOTS,
                    "ddl_prefer_upscaled": helpers.checked(mylar.CONFIG.DDL_PREFER_UPSCALED),
                    "enable_external_server": helpers.checked(mylar.CONFIG.ENABLE_EXTERNAL_SERVER),
                    "external_server": mylar.CONFIG.EXTERNAL_SERVER,
                    "external_username": mylar.CONFIG.EXTERNAL_USERNAME,
                    "external_apikey": mylar.CONFIG.EXTERNAL_APIKEY,
                    "enable_rss": helpers.checked(mylar.CONFIG.ENABLE_RSS),
                    "rss_checkinterval": mylar.CONFIG.RSS_CHECKINTERVAL,
                    "rss_last": rss_sclast,
                    "provider_order": mylar.CONFIG.PROVIDER_ORDER,
                    "enable_torrents": helpers.checked(mylar.CONFIG.ENABLE_TORRENTS),
                    "minseeds": mylar.CONFIG.MINSEEDS,
                    "torrent_local": helpers.checked(mylar.CONFIG.TORRENT_LOCAL),
                    "local_watchdir": mylar.CONFIG.LOCAL_WATCHDIR,
                    "torrent_seedbox": helpers.checked(mylar.CONFIG.TORRENT_SEEDBOX),
                    "seedbox_watchdir": mylar.CONFIG.SEEDBOX_WATCHDIR,
                    "seedbox_host": mylar.CONFIG.SEEDBOX_HOST,
                    "seedbox_port": mylar.CONFIG.SEEDBOX_PORT,
                    "seedbox_user": mylar.CONFIG.SEEDBOX_USER,
                    "seedbox_pass": mylar.CONFIG.SEEDBOX_PASS,
                    "enable_torrent_search": helpers.checked(mylar.CONFIG.ENABLE_TORRENT_SEARCH),
                    "enable_public": helpers.checked(mylar.CONFIG.ENABLE_PUBLIC),
                    "enable_32p": helpers.checked(mylar.CONFIG.ENABLE_32P),
                    "legacymode_32p": helpers.radio(mylar.CONFIG.MODE_32P, 0),
                    "authmode_32p": helpers.radio(mylar.CONFIG.MODE_32P, 1),
                    "rssfeed_32p": mylar.CONFIG.RSSFEED_32P,
                    "passkey_32p": mylar.CONFIG.PASSKEY_32P,
                    "username_32p": mylar.CONFIG.USERNAME_32P,
                    "password_32p": mylar.CONFIG.PASSWORD_32P,
                    "snatchedtorrent_notify": helpers.checked(mylar.CONFIG.SNATCHEDTORRENT_NOTIFY),
                    "destination_dir": mylar.CONFIG.DESTINATION_DIR,
                    "create_folders": helpers.checked(mylar.CONFIG.CREATE_FOLDERS),
                    "enforce_perms": helpers.checked(mylar.CONFIG.ENFORCE_PERMS),
                    "chmod_dir": mylar.CONFIG.CHMOD_DIR,
                    "chmod_file": mylar.CONFIG.CHMOD_FILE,
                    "chowner": mylar.CONFIG.CHOWNER,
                    "chgroup": mylar.CONFIG.CHGROUP,
                    "replace_spaces": helpers.checked(mylar.CONFIG.REPLACE_SPACES),
                    "replace_char": mylar.CONFIG.REPLACE_CHAR,
                    "use_minsize": helpers.checked(mylar.CONFIG.USE_MINSIZE),
                    "minsize": mylar.CONFIG.MINSIZE,
                    "use_maxsize": helpers.checked(mylar.CONFIG.USE_MAXSIZE),
                    "maxsize": mylar.CONFIG.MAXSIZE,
                    "interface_list": interface_list,
                    "dupeconstraint": mylar.CONFIG.DUPECONSTRAINT,
                    "ddump": helpers.checked(mylar.CONFIG.DDUMP),
                    "duplicate_dump": mylar.CONFIG.DUPLICATE_DUMP,
                    "autowant_all": helpers.checked(mylar.CONFIG.AUTOWANT_ALL),
                    "autowant_upcoming": helpers.checked(mylar.CONFIG.AUTOWANT_UPCOMING),
                    "comic_cover_local": helpers.checked(mylar.CONFIG.COMIC_COVER_LOCAL),
                    "cover_folder_local": helpers.checked(mylar.CONFIG.COVER_FOLDER_LOCAL),
                    "series_metadata_local": helpers.checked(mylar.CONFIG.SERIES_METADATA_LOCAL),
                    "alternate_latest_series_covers": helpers.checked(mylar.CONFIG.ALTERNATE_LATEST_SERIES_COVERS),
                    "pref_qual_0": helpers.radio(int(mylar.CONFIG.PREFERRED_QUALITY), 0),
                    "pref_qual_1": helpers.radio(int(mylar.CONFIG.PREFERRED_QUALITY), 1),
                    "pref_qual_2": helpers.radio(int(mylar.CONFIG.PREFERRED_QUALITY), 2),
                    "move_files": helpers.checked(mylar.CONFIG.MOVE_FILES),
                    "rename_files": helpers.checked(mylar.CONFIG.RENAME_FILES),
                    "folder_format": mylar.CONFIG.FOLDER_FORMAT,
                    "file_format": mylar.CONFIG.FILE_FORMAT,
                    "zero_level": helpers.checked(mylar.CONFIG.ZERO_LEVEL),
                    "zero_level_n": mylar.CONFIG.ZERO_LEVEL_N,
                    "add_to_csv": helpers.checked(mylar.CONFIG.ADD_TO_CSV),
                    "cvinfo": helpers.checked(mylar.CONFIG.CVINFO),
                    "lowercase_filenames": helpers.checked(mylar.CONFIG.LOWERCASE_FILENAMES),
                    "syno_fix": helpers.checked(mylar.CONFIG.SYNO_FIX),
                    "prowl_enabled": helpers.checked(mylar.CONFIG.PROWL_ENABLED),
                    "prowl_onsnatch": helpers.checked(mylar.CONFIG.PROWL_ONSNATCH),
                    "prowl_keys": mylar.CONFIG.PROWL_KEYS,
                    "prowl_priority": mylar.CONFIG.PROWL_PRIORITY,
                    "pushover_enabled": helpers.checked(mylar.CONFIG.PUSHOVER_ENABLED),
                    "pushover_onsnatch": helpers.checked(mylar.CONFIG.PUSHOVER_ONSNATCH),
                    "pushover_image": helpers.checked(mylar.CONFIG.PUSHOVER_IMAGE),
                    "pushover_apikey": mylar.CONFIG.PUSHOVER_APIKEY,
                    "pushover_userkey": mylar.CONFIG.PUSHOVER_USERKEY,
                    "pushover_device": mylar.CONFIG.PUSHOVER_DEVICE,
                    "pushover_priority": mylar.CONFIG.PUSHOVER_PRIORITY,
                    "boxcar_enabled": helpers.checked(mylar.CONFIG.BOXCAR_ENABLED),
                    "boxcar_onsnatch": helpers.checked(mylar.CONFIG.BOXCAR_ONSNATCH),
                    "boxcar_token": mylar.CONFIG.BOXCAR_TOKEN,
                    "pushbullet_enabled": helpers.checked(mylar.CONFIG.PUSHBULLET_ENABLED),
                    "pushbullet_onsnatch": helpers.checked(mylar.CONFIG.PUSHBULLET_ONSNATCH),
                    "pushbullet_apikey": mylar.CONFIG.PUSHBULLET_APIKEY,
                    "pushbullet_deviceid": mylar.CONFIG.PUSHBULLET_DEVICEID,
                    "pushbullet_channel_tag": mylar.CONFIG.PUSHBULLET_CHANNEL_TAG,
                    "telegram_enabled": helpers.checked(mylar.CONFIG.TELEGRAM_ENABLED),
                    "telegram_onsnatch": helpers.checked(mylar.CONFIG.TELEGRAM_ONSNATCH),
                    "telegram_image": helpers.checked(mylar.CONFIG.TELEGRAM_IMAGE),
                    "telegram_token": mylar.CONFIG.TELEGRAM_TOKEN,
                    "telegram_userid": mylar.CONFIG.TELEGRAM_USERID,
                    "slack_enabled": helpers.checked(mylar.CONFIG.SLACK_ENABLED),
                    "slack_webhook_url": mylar.CONFIG.SLACK_WEBHOOK_URL,
                    "slack_onsnatch": helpers.checked(mylar.CONFIG.SLACK_ONSNATCH),
                    "mattermost_enabled": helpers.checked(mylar.CONFIG.MATTERMOST_ENABLED),
                    "mattermost_webhook_url": mylar.CONFIG.MATTERMOST_WEBHOOK_URL,
                    "mattermost_onsnatch": helpers.checked(mylar.CONFIG.MATTERMOST_ONSNATCH),
                    "discord_enabled": helpers.checked(mylar.CONFIG.DISCORD_ENABLED),
                    "discord_webhook_url": mylar.CONFIG.DISCORD_WEBHOOK_URL,
                    "discord_onsnatch": helpers.checked(mylar.CONFIG.DISCORD_ONSNATCH),
                    "email_enabled": helpers.checked(mylar.CONFIG.EMAIL_ENABLED),
                    "email_from": mylar.CONFIG.EMAIL_FROM,
                    "email_to": mylar.CONFIG.EMAIL_TO,
                    "email_server": mylar.CONFIG.EMAIL_SERVER,
                    "email_user": mylar.CONFIG.EMAIL_USER,
                    "email_password": mylar.CONFIG.EMAIL_PASSWORD,
                    "email_port": int(mylar.CONFIG.EMAIL_PORT),
                    "email_raw": helpers.radio(int(mylar.CONFIG.EMAIL_ENC), 0),
                    "email_ssl": helpers.radio(int(mylar.CONFIG.EMAIL_ENC), 1),
                    "email_tls": helpers.radio(int(mylar.CONFIG.EMAIL_ENC), 2),
                    "email_ongrab": helpers.checked(mylar.CONFIG.EMAIL_ONGRAB),
                    "email_onpost": helpers.checked(mylar.CONFIG.EMAIL_ONPOST),
                    "gotify_enabled": helpers.checked(mylar.CONFIG.GOTIFY_ENABLED),
                    "gotify_server_url": mylar.CONFIG.GOTIFY_SERVER_URL,
                    "gotify_token": mylar.CONFIG.GOTIFY_TOKEN,
                    "gotify_onsnatch": helpers.checked(mylar.CONFIG.GOTIFY_ONSNATCH),
                    "enable_extra_scripts": helpers.checked(mylar.CONFIG.ENABLE_EXTRA_SCRIPTS),
                    "extra_scripts": mylar.CONFIG.EXTRA_SCRIPTS,
                    "enable_snatch_script": helpers.checked(mylar.CONFIG.ENABLE_SNATCH_SCRIPT),
                    "snatch_script": mylar.CONFIG.SNATCH_SCRIPT,
                    "enable_pre_scripts": helpers.checked(mylar.CONFIG.ENABLE_PRE_SCRIPTS),
                    "pre_scripts": mylar.CONFIG.PRE_SCRIPTS,
                    "post_processing": helpers.checked(mylar.CONFIG.POST_PROCESSING),
                    "file_opts": mylar.CONFIG.FILE_OPTS,
                    "enable_meta": helpers.checked(mylar.CONFIG.ENABLE_META),
                    "cbr2cbz_only": helpers.checked(mylar.CONFIG.CBR2CBZ_ONLY),
                    "cmtag_start_year_as_volume": helpers.checked(mylar.CONFIG.CMTAG_START_YEAR_AS_VOLUME),
                    "setdefaultvolume": helpers.checked(mylar.CONFIG.SETDEFAULTVOLUME),
                    "cmtagger_path": mylar.CONFIG.CMTAGGER_PATH,
                    "ct_tag_cr": helpers.checked(mylar.CONFIG.CT_TAG_CR),
                    "ct_tag_cbl": helpers.checked(mylar.CONFIG.CT_TAG_CBL),
                    "ct_cbz_overwrite": helpers.checked(mylar.CONFIG.CT_CBZ_OVERWRITE),
                    "cmtag_volume": helpers.checked(mylar.CONFIG.CMTAG_VOLUME),
                    "ct_notes_format": mylar.CONFIG.CT_NOTES_FORMAT,
                    "unrar_cmd": mylar.CONFIG.UNRAR_CMD,
                    "failed_download_handling": helpers.checked(mylar.CONFIG.FAILED_DOWNLOAD_HANDLING),
                    "failed_auto": helpers.checked(mylar.CONFIG.FAILED_AUTO),
                    "branch": mylar.CONFIG.GIT_BRANCH,
                    "br_type": mylar.INSTALL_TYPE,
                    "br_version": mylar.CURRENT_VERSION,
                    "br_version_name": mylar.CURRENT_VERSION_NAME,
                    "br_release_name": mylar.CURRENT_RELEASE_NAME,
                    "py_version": chk_py_version,
                    "py_check_pass": py_check_pass,
                    "data_dir": mylar.DATA_DIR,
                    "prog_dir": mylar.PROG_DIR,
                    "cache_dir": mylar.CONFIG.CACHE_DIR,
                    "config_file": mylar.CONFIG_FILE,
                    "lang": '%s.%s' % (logger.LOG_LANG,logger.LOG_CHARSET),
                    "branch_history" : br_hist,
                    "log_dir": mylar.CONFIG.LOG_DIR,
                    "opds_enable": helpers.checked(mylar.CONFIG.OPDS_ENABLE),
                    "opds_endpoint": mylar.CONFIG.OPDS_ENDPOINT,
                    "opds_authentication": helpers.checked(mylar.CONFIG.OPDS_AUTHENTICATION),
                    "opds_username": mylar.CONFIG.OPDS_USERNAME,
                    "opds_password": mylar.CONFIG.OPDS_PASSWORD,
                    "opds_metainfo": helpers.checked(mylar.CONFIG.OPDS_METAINFO),
                    "opds_pagesize": mylar.CONFIG.OPDS_PAGESIZE,
                    "dlstats": dlprovstats,
                    "dltotals": freq_tot,
                    "alphaindex": mylar.CONFIG.ALPHAINDEX,
                    "backup_on_start": helpers.checked(mylar.CONFIG.BACKUP_ON_START),
               }
        return serve_template(templatename="config.html", title="Settings", config=config, comicinfo=comicinfo)
    config.exposed = True

    def error_change(self, comicid, errorgcd, comicname, comicyear, imported=None, mogcname=None):
        # if comicname contains a "," it will break the exceptions import.
        import urllib.request, urllib.parse, urllib.error
        b = urllib.parse.unquote_plus(comicname)
#        cname = b.decode("utf-8")
        cname = b #.encode('utf-8')
        cname = re.sub("\,", "", cname)

        if mogcname != None:
            c = urllib.parse.unquote_plus(mogcname)
            ogcname = c #.encode('utf-8')
        else:
            ogcname = None

        if errorgcd[:5].isdigit():
            logger.info("GCD-ID detected : " + str(errorgcd)[:5])
            logger.info("ogcname: " + str(ogcname))
            logger.info("I'm assuming you know what you're doing - going to force-match for " + cname)
            self.from_Exceptions(comicid=comicid, gcdid=errorgcd, comicname=cname, comicyear=comicyear, imported=imported, ogcname=ogcname)
        else:
            logger.info("Assuming rewording of Comic - adjusting to : " + str(errorgcd))
            Err_Info = mylar.cv.getComic(comicid, 'comic')
            self.addComic(comicid=comicid, comicname=str(errorgcd), comicyear=Err_Info['ComicYear'], comicissues=Err_Info['ComicIssues'], comicpublisher=Err_Info['ComicPublisher'])

    error_change.exposed = True

    def manual_annual_add(self, manual_comicid, comicname, comicyear, comicid, x=None, y=None):
        import urllib.request, urllib.parse, urllib.error
        b = urllib.parse.unquote_plus(comicname)
        cname = b #.encode('utf-8')

        logger.fdebug('comicid to be attached : ' + str(manual_comicid))
        logger.fdebug('comicname : ' + str(cname))
        logger.fdebug('comicyear : ' + str(comicyear))
        logger.fdebug('comicid : ' + str(comicid))
        issueid = manual_comicid
        logger.fdebug('I will be adding ' + str(issueid) + ' to the Annual list for this series.')
        threading.Thread(target=importer.manualAnnual, args=[manual_comicid, cname, comicyear, comicid]).start()

        raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % comicid)
    manual_annual_add.exposed = True

    def comic_config(self, com_location, ComicID, alt_search=None, fuzzy_year=None, comic_version=None, force_continuing=None, force_type=None, alt_filename=None, allow_packs=None, corrected_seriesyear=None, torrentid_32p=None, ignore_type=None, age_rating=None, publisher_imprint=None):
        myDB = db.DBConnection()
        chk1 = myDB.selectone('SELECT ComicLocation, Type, Corrected_Type, PublisherImprint FROM comics WHERE ComicID=?', [ComicID]).fetchone()

        if chk1[0] is None:
            orig_location = com_location
        else:
            orig_location = chk1[0]

        if chk1[1] is None:
            orig_type = None
        else:
            orig_type = chk1[1]

        if chk1[2] is None:
            orig_corr_type = None
        else:
            orig_corr_type = chk1[2]

        if chk1[3] is None:
            orig_imprint = None
        else:
            orig_imprint = chk1[3]

#--- this is for multiple search terms............
#--- works, just need to redo search.py to accomodate multiple search terms
        ffs_alt = []
        if '##' in alt_search:
            ffs = alt_search.find('##')
            ffs_alt.append(alt_search[:ffs])
            ffs_alt_st = str(ffs_alt[0])

        ffs_test = alt_search.split('##')
        if len(ffs_test) > 0:
            ffs_count = len(ffs_test)
            n=1
            while (n < ffs_count):
                ffs_alt.append(ffs_test[n])
                ffs_alt_st = str(ffs_alt_st) + "..." + str(ffs_test[n])
                n+=1
            asearch = ffs_alt
        else:
            asearch = alt_search

        asearch = str(alt_search)

        controlValueDict = {'ComicID': ComicID}
        newValues = {}
        if asearch is not None:
            if re.sub(r'\s', '', asearch) == '':
                newValues['AlternateSearch'] = "None"
            else:
                newValues['AlternateSearch'] = str(asearch)
        else:
            newValues['AlternateSearch'] = "None"

        if fuzzy_year is None:
            newValues['UseFuzzy'] = "0"
        else:
            newValues['UseFuzzy'] = str(fuzzy_year)

        if corrected_seriesyear is not None:
            newValues['Corrected_SeriesYear'] = str(corrected_seriesyear)
            newValues['ComicYear'] = str(corrected_seriesyear)

        if comic_version is None or comic_version == 'None':
            newValues['ComicVersion'] = None
        else:
            if comic_version[1:].isdigit() and comic_version[:1].lower() == 'v':
                newValues['ComicVersion'] = str(comic_version)
            else:
                logger.info("Invalid Versioning entered - it must be in the format of v#")
                newValues['ComicVersion'] = None

        if force_continuing is None:
            newValues['ForceContinuing'] = 0
        else:
            newValues['ForceContinuing'] = 1

        if force_type == 'TPB':
            newValues['Corrected_Type'] = 'TPB'
        elif force_type == 'GN':
            newValues['Corrected_Type'] = 'GN'
        elif force_type == 'HC':
            newValues['Corrected_Type'] = 'HC'
        elif force_type == 'Digital':
            newValues['Corrected_Type'] = 'Digital'
        elif force_type == 'One-Shot':
            newValues['Corrected_Type'] = 'One-Shot'
        elif force_type == 'Print':
            newValues['Corrected_Type'] = 'Print'
        else:
            if orig_corr_type is not None:
                newValues['Corrected_Type'] = orig_corr_type
            else:
                newValues['Corrected_Type'] = None

        if any([ignore_type == '0', ignore_type is None, ignore_type == 'None']):
            newValues['IgnoreType'] = 0
        else:
            newValues['IgnoreType'] = 1

        if age_rating is not None:
            logger.info('AgeRating: %s' % age_rating)
            newValues['AgeRating'] = age_rating

        if all([publisher_imprint is not None, publisher_imprint != 'None', publisher_imprint != '']):
            if re.sub(r'\s', '', publisher_imprint) == '':
                newValues['PublisherImprint'] = 'None'
            else:
                newValues['PublisherImprint'] = publisher_imprint
        else:
            newValues['PublisherImprint'] = 'None'

        #logger.fdebug('orig_type:%s -- force_type: %s' % (orig_type, force_type))
        #logger.fdebug('orig_corr_type: %s-- corrected_type: %s' % (orig_corr_type, newValues['Corrected_Type']))
        #logger.fdebug('config_folder_format:%s' % (mylar.CONFIG.FOLDER_FORMAT))
        #logger.fdebug('config_format_booktype:%s' % (mylar.CONFIG.FORMAT_BOOKTYPE))
        #logger.fdebug('com_location:%s -- orig_location: %s' % (com_location, orig_location))
        #logger.fdebug('orig_imprint:%s -- publisher_imprint: %s' % (orig_imprint, newValues['PublisherImprint']))
        if orig_corr_type != newValues['Corrected_Type'] or (orig_imprint != newValues['PublisherImprint'] and all(
            [
                orig_imprint != newValues['PublisherImprint'],
                newValues['PublisherImprint'] is not None,
                newValues['PublisherImprint'] != 'None',
            ]
        ) or all(
            [
                orig_imprint != newValues['PublisherImprint'],
                orig_imprint is not None,
                orig_imprint != 'None',
                orig_imprint != '',
            ]
        )):
            mod_booktype = orig_corr_type
            mod_imprint = orig_imprint
            if all(['$Type' in mylar.CONFIG.FOLDER_FORMAT, com_location == orig_location, mylar.CONFIG.FORMAT_BOOKTYPE is True]):
                mod_booktype = newValues['Corrected_Type']
            if all(['$Imprint' in mylar.CONFIG.FOLDER_FORMAT, com_location == orig_location]):
                mod_imprint = newValues['PublisherImprint']

            #rename folder if the $Type is in folder format to accomodate new forced format.
            from . import filers
            x = filers.FileHandlers(ComicID=ComicID)
            newcom_location = x.folder_create(booktype=mod_booktype, imprint=mod_imprint)
            if all([newcom_location['comlocation'] is not None, com_location != orig_location]):
                com_location = newcom_location['comlocation']
            else:
                logger.fdebug('Not renaming as Comic Location path has not changed...')

        if allow_packs is None:
            newValues['AllowPacks'] = 0
        else:
            newValues['AllowPacks'] = 1

        newValues['TorrentID_32P'] = torrentid_32p

        if alt_filename is not None:
            if re.sub(r'\s', '', alt_filename) == '':
                newValues['AlternateFileName'] = "None"
            else:
                newValues['AlternateFileName'] = str(alt_filename)
        else:
            newValues['AlternateFileName'] = "None"

        #force the check/creation of directory com_location here
        updatedir = True
        if any([mylar.CONFIG.CREATE_FOLDERS is True, os.path.isdir(orig_location)]):
            if os.path.isdir(str(com_location)):
                logger.info("Validating Directory (" + str(com_location) + "). Already exists! Continuing...")
            else:
                if orig_location != com_location and os.path.isdir(orig_location) is True:
                    logger.fdebug('Attempting to rename existing location [%s]' % (orig_location))
                    try:
                        # make sure 2 levels up in strucure exist
                        if not os.path.exists(os.path.split ( os.path.split(com_location)[0] ) [0] ):
                            logger.fdebug('making directory: %s' % os.path.split(os.path.split(com_location)[0])[0])
                            os.mkdir(os.path.split(os.path.split(com_location)[0])[0])
                        # make sure parent directory exists
                        if not os.path.exists(os.path.split(com_location)[0]):
                            logger.fdebug('making directory: %s' % os.path.split(com_location)[0])
                            os.mkdir(os.path.split(com_location)[0])
                        logger.info('Renaming directory: %s --> %s' % (orig_location,com_location))
                        shutil.move(orig_location, com_location)
                    except Exception as e:
                        if 'No such file or directory' in e:
                            checkdirectory = filechecker.validateAndCreateDirectory(com_location, True)
                            if not checkdirectory:
                                logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                                updatedir = False
                        else:
                            logger.warn('Unable to rename existing directory: %s' % e)
                            updatedir = False
                else:
                    if orig_location != com_location and os.path.isdir(orig_location) is False:
                        logger.fdebug("Original Directory (%s) doesn't exist! - attempting to create new directory (%s)" % (orig_location, com_location))
                    else:
                        logger.fdebug("Updated Directory doesn't exist! - attempting to create now.")
                    checkdirectory = filechecker.validateAndCreateDirectory(com_location, True)
                    if not checkdirectory:
                        logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                        updatedir = False
        else:
            logger.info('[Create directories False] Not creating physical directory, but updating series location in dB to: %s' % com_location)

        if updatedir is True:
            newValues['ComicLocation'] = com_location
            myDB.upsert("comics", newValues, controlValueDict)
            logger.fdebug('Updated Series options!')

        raise cherrypy.HTTPRedirect("comicDetails?ComicID=%s" % ComicID)
    comic_config.exposed = True

    def readlistOptions(self, send2read=0, tab_enable=0, tab_host=None, tab_user=None, tab_pass=None, tab_directory=None, maintainseriesfolder=0):
        mylar.CONFIG.SEND2READ = bool(int(send2read))
        mylar.CONFIG.MAINTAINSERIESFOLDER = bool(int(maintainseriesfolder))
        mylar.CONFIG.TAB_ENABLE = bool(int(tab_enable))
        mylar.CONFIG.TAB_HOST = tab_host
        mylar.CONFIG.TAB_USER = tab_user
        mylar.CONFIG.TAB_PASS = tab_pass
        mylar.CONFIG.TAB_DIRECTORY = tab_directory
        readoptions = {'send2read':              mylar.CONFIG.SEND2READ,
                       'maintainseriesfolder':   mylar.CONFIG.MAINTAINSERIESFOLDER,
                       'tab_enable':             mylar.CONFIG.TAB_ENABLE,
                       'tab_host':               mylar.CONFIG.TAB_HOST,
                       'tab_user':               mylar.CONFIG.TAB_USER,
                       'tab_pass':               mylar.CONFIG.TAB_PASS,
                       'tab_directory':          mylar.CONFIG.TAB_DIRECTORY}
        mylar.CONFIG.writeconfig(values=readoptions)

        raise cherrypy.HTTPRedirect("readlist")

    readlistOptions.exposed = True

    def arcOptions(self, StoryArcID=None, StoryArcName=None, read2filename=0, storyarcdir=0, arc_folderformat=None, copy2arcdir=0, arc_fileops='copy', arc_fileops_softlink_relative=0):
        mylar.CONFIG.READ2FILENAME = bool(int(read2filename))
        mylar.CONFIG.STORYARCDIR = bool(int(storyarcdir))
        if arc_folderformat is None:
            mylar.CONFIG.ARC_FOLDERFORMAT = "($arc) ($spanyears)"
        else:
            mylar.CONFIG.ARC_FOLDERFORMAT = arc_folderformat
        mylar.CONFIG.COPY2ARCDIR = bool(int(copy2arcdir))
        mylar.CONFIG.ARC_FILEOPS = arc_fileops
        mylar.CONFIG.ARC_FILEOPS_SOFTLINK_RELATIVE = bool(int(arc_fileops_softlink_relative))
        options = {'read2filename':                 mylar.CONFIG.READ2FILENAME,
                   'storyarcdir':                   mylar.CONFIG.STORYARCDIR,
                   'arc_folderformat':              mylar.CONFIG.ARC_FOLDERFORMAT,
                   'copy2arcdir':                   mylar.CONFIG.COPY2ARCDIR,
                   'arc_fileops':                   mylar.CONFIG.ARC_FILEOPS,
                   'arc_fileops_softlink_relative': mylar.CONFIG.ARC_FILEOPS_SOFTLINK_RELATIVE}
        mylar.CONFIG.writeconfig(values=options)

        #force the check/creation of directory com_location here
        if mylar.CONFIG.STORYARCDIR is True:
            if mylar.CONFIG.STORYARC_LOCATION is not None:
                arcdir = mylar.CONFIG.STORYARC_LOCATION
            else:
                arcdir = os.path.join(mylar.CONFIG.DESTINATION_DIR, 'StoryArcs')
            if os.path.isdir(arcdir):
                logger.info('Validating Directory (%s). Already exists! Continuing...' % arcdir)
            else:
                logger.fdebug('Storyarc Directory doesn\'t exist! Attempting to create now.')
                checkdirectory = filechecker.validateAndCreateDirectory(arcdir, True)
                if not checkdirectory:
                    logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                    return
        if StoryArcID is not None:
            raise cherrypy.HTTPRedirect("detailStoryArc?StoryArcID=%s&StoryArcName=%s" % (StoryArcID, StoryArcName))
        else:
            raise cherrypy.HTTPRedirect("storyarc_main")
    arcOptions.exposed = True


    def configUpdate(self, **kwargs):
        checked_configs = ['enable_https', 'launch_browser', 'backup_on_start', 'syno_fix', 'auto_update', 'annuals_on', 'api_enabled', 'nzb_startup_search',
                           'enforce_perms', 'sab_to_mylar', 'torrent_local', 'torrent_seedbox', 'rtorrent_ssl', 'rtorrent_verify', 'rtorrent_startonload',
                           'enable_torrents', 'enable_rss', 'experimental', 'enable_torrent_search', 'enable_32p', 'enable_torznab',
                           'newznab', 'use_minsize', 'use_maxsize', 'ddump', 'failed_download_handling', 'sab_client_post_processing', 'nzbget_client_post_processing',
                           'failed_auto', 'post_processing', 'enable_check_folder', 'enable_pre_scripts', 'enable_snatch_script', 'enable_extra_scripts',
                           'enable_meta', 'cbr2cbz_only', 'ct_tag_cr', 'ct_tag_cbl', 'ct_cbz_overwrite', 'cmtag_start_year_as_volume', 'cmtag_volume', 'setdefaultvolume',
                           'rename_files', 'replace_spaces', 'zero_level', 'sab_remove_completed', 'sab_remove_failed',
                           'lowercase_filenames', 'autowant_upcoming', 'autowant_all', 'comic_cover_local', 'cover_folder_local', 'series_metadata_local', 'alternate_latest_series_covers', 'cvinfo', 'snatchedtorrent_notify',
                           'prowl_enabled', 'prowl_onsnatch', 'pushover_enabled', 'pushover_onsnatch', 'pushover_image', 'mattermost_enabled', 'mattermost_onsnatch', 'boxcar_enabled',
                           'boxcar_onsnatch', 'pushbullet_enabled', 'pushbullet_onsnatch', 'telegram_enabled', 'telegram_onsnatch', 'telegram_image', 'discord_enabled', 'discord_onsnatch', 'slack_enabled', 'slack_onsnatch',
                           'email_enabled', 'email_enc', 'email_ongrab', 'email_onpost', 'gotify_enabled', 'gotify_server_url', 'gotify_token', 'gotify_onsnatch', 'opds_enable', 'opds_authentication', 'opds_metainfo', 'opds_pagesize', 'enable_ddl',
                           'enable_getcomics', 'enable_airdcpp', 'enable_external_server', 'ddl_prefer_upscaled', 'deluge_pause'] #enable_public

        for checked_config in checked_configs:
            if checked_config not in kwargs:
                kwargs[checked_config] = False

        for k, v in kwargs.items():
            try:
                _conf = mylar.CONFIG._define(k)
            except KeyError:
                continue

        mylar.CONFIG.EXTRA_NEWZNABS = []

        for kwarg in [x for x in kwargs if x.startswith('newznab_name')]:
            if kwarg.startswith('newznab_name'):
                newznab_number = kwarg[12:]
                newznab_name = kwargs['newznab_name' + newznab_number]
                if newznab_name == "":
                    newznab_name = kwargs['newznab_host' + newznab_number]
                    if newznab_name == "":
                        continue
                newznab_host = helpers.clean_url(kwargs['newznab_host' + newznab_number])
                try:
                    newznab_verify = kwargs['newznab_verify' + newznab_number]
                except:
                    newznab_verify = 0
                newznab_apikey = kwargs['newznab_apikey' + newznab_number]
                newznab_uid = kwargs['newznab_uid' + newznab_number]
                if ',' in newznab_uid:
                    newznab_uid = re.sub(',', '#', newznab_uid).strip()
                try:
                    newznab_enabled = str(kwargs['newznab_enabled' + newznab_number])
                except KeyError:
                    newznab_enabled = '0'

                del kwargs[kwarg]

                if newznab_number.startswith('_'):
                    mylar.PROVIDER_START_ID +=1
                    newznab_number = str(mylar.PROVIDER_START_ID)

                mylar.CONFIG.EXTRA_NEWZNABS.append((newznab_name, newznab_host, newznab_verify, newznab_apikey, newznab_uid, newznab_enabled, int(newznab_number)))

        mylar.CONFIG.EXTRA_TORZNABS = []

        for kwarg in [x for x in kwargs if x.startswith('torznab_name')]:
            if kwarg.startswith('torznab_name'):
                torznab_number = kwarg[12:]
                torznab_name = kwargs['torznab_name' + torznab_number]
                if torznab_name == "":
                    torznab_name = kwargs['torznab_host' + torznab_number]
                    if torznab_name == "":
                        continue
                torznab_host = helpers.clean_url(kwargs['torznab_host' + torznab_number])
                try:
                    torznab_verify = kwargs['torznab_verify' + torznab_number]
                except:
                    torznab_verify = 0
                torznab_api = kwargs['torznab_apikey' + torznab_number]
                torznab_category = kwargs['torznab_category' + torznab_number]
                if ',' in torznab_category:
                    torznab_category = re.sub(',', '#', torznab_category).strip()

                try:
                    torznab_enabled = str(kwargs['torznab_enabled' + torznab_number])
                except KeyError:
                    torznab_enabled = '0'

                del kwargs[kwarg]

                if torznab_number.startswith('_'):
                    mylar.PROVIDER_START_ID +=1
                    torznab_number = str(mylar.PROVIDER_START_ID)

                mylar.CONFIG.EXTRA_TORZNABS.append((torznab_name, torznab_host, torznab_verify, torznab_api, torznab_category, torznab_enabled, int(torznab_number)))

        mylar.CONFIG.process_kwargs(kwargs)

        #this makes sure things are set to the default values if they're not appropriately set.
        mylar.CONFIG.configure(update=True, startup=False)

        # Write the config
        logger.info('Now saving config...')
        mylar.CONFIG.writeconfig()

    configUpdate.exposed = True

    def SABtest(self, sabhost=None, sabusername=None, sabpassword=None, sabapikey=None):
        if sabhost is None:
            sabhost = mylar.CONFIG.SAB_HOST
        if sabusername is None:
            sabusername = mylar.CONFIG.SAB_USERNAME
        if sabpassword is None:
            sabpassword = mylar.CONFIG.SAB_PASSWORD
        if sabapikey is None:
            sabapikey = mylar.CONFIG.SAB_APIKEY
        logger.fdebug('Now attempting to test SABnzbd connection')

        logger.fdebug('testing connection to SABnzbd @ ' + sabhost)
        if sabhost.endswith('/'):
            sabhost = sabhost
        else:
            sabhost = sabhost + '/'

        querysab = sabhost + 'api'
        payload = {'mode':    'get_config',
                   'section': 'misc',
                   'output':  'json',
                   'keyword': 'api_key',
                   'apikey':   sabapikey}

        if sabhost.startswith('https'):
            verify = True
        else:
            verify = False

        version = 'Unknown'
        try:
            v = requests.get(querysab, params={'mode': 'version'}, verify=verify)
            if str(v.status_code) == '200':
                try:
                    version = v.json()['version']
                except Exception as e:
                    version = v.text.strip()
                logger.fdebug('sabnzbd version: %s' % version)
            r = requests.get(querysab, params=payload, verify=verify)
        except Exception as e:
            logger.warn('Error fetching data from %s: %s' % (querysab, e))
            if requests.exceptions.SSLError:
                logger.warn('Cannot verify ssl certificate. Attempting to authenticate with no ssl-certificate verification.')
                try:
                    from requests.packages.urllib3 import disable_warnings
                    disable_warnings()
                except:
                    logger.warn('Unable to disable https warnings. Expect some spam if using https nzb providers.')

                verify = False

                try:
                    v = requests.get(querysab, params={'mode': 'version'}, verify=verify)
                    if str(v.status_code) == '200':
                        try:
                            version = v.json()['version']
                        except Exception as e:
                            version = v.text.strip()
                        logger.fdebug('sabnzbd version: %s' % version)
                    r = requests.get(querysab, params=payload, verify=verify)
                except Exception as e:
                    logger.warn('Error fetching data from %s: %s' % (sabhost, e))
                    return json.dumps({"status": False, "message": "Unable to retrieve data from SABnzbd.", "version": str(version)})
            else:
                return json.dumps({"status": False, "message": "Unable to retrieve data from SABnzbd.", "version": str(version)})


        logger.fdebug('status code: ' + str(r.status_code))

        if str(r.status_code) != '200':
            logger.warn('Unable to properly query SABnzbd @' + sabhost + ' [Status Code returned: ' + str(r.status_code) + ']')
            data = False
        else:
            data = r.json()

        try:
            q_apikey = data['config']['misc']['api_key']
        except:
            logger.error('Error detected attempting to retrieve SAB data using FULL API Key')
            return json.dumps({"status": False, "message": "Invalid API Key provided.", "version": str(version)})

        mylar.CONFIG.SAB_APIKEY = q_apikey
        logger.info('APIKey provided is the FULL API Key which is the correct key.')
        logger.info('Connection to SABnzbd tested sucessfully')
        mylar.CONFIG.SAB_VERSION = version
        mylar.CONFIG.writeconfig(values={'sab_version': version, 'sab_apikey': q_apikey})
        return json.dumps({"status": True, "message": "Successfully verified API Key.", "version": str(version)})

    SABtest.exposed = True

    def AirDCPPtest(self, airdcpphost=None, airdcppusername=None, airdcpppassword=None):
        if airdcpphost is None:
            airdcpphost = mylar.CONFIG.AIRDCPP_HOST
        if airdcppusername is None:
            airdcppusername = mylar.CONFIG.AIRDCPP_USERNAME
        if airdcpppassword is None:
            airdcpppassword = mylar.CONFIG.AIRDCPP_PASSWORD

        logger.fdebug('Now attempting to test AirDC++ connection')
        logger.fdebug('testing connection to AirDC++ @ ' + airdcpphost)

        if not airdcpphost.endswith('/'):
            airdcpphost = airdcpphost + '/'

        api_url = airdcpphost
        if not api_url.endswith('api/v1'):
            api_url += 'api/v1'

        query_url = f"{api_url}/system/system_info"

        if airdcpphost.startswith('https'):
            verify = True
        else:
            verify = False

        version = 'Unknown'
        try:
            session = requests.Session()
            if airdcppusername and airdcpppassword:
                session.auth = (airdcppusername, airdcpppassword)

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36'
            }

            r = session.get(query_url, headers=headers, verify=verify, timeout=30)
        except Exception as e:
            logger.warn('Error fetching data from %s: %s' % (query_url, e))
            if requests.exceptions.SSLError:
                logger.warn(
                    'Cannot verify ssl certificate. Attempting to authenticate with no ssl-certificate verification.')
                try:
                    from requests.packages.urllib3 import disable_warnings
                    disable_warnings()
                except:
                    logger.warn('Unable to disable https warnings. Expect some spam if using https providers.')

                verify = False

                try:
                    session = requests.Session()
                    if airdcppusername and airdcpppassword:
                        session.auth = (airdcppusername, airdcpppassword)

                    r = session.get(query_url, headers=headers, verify=verify, timeout=30)
                except Exception as e:
                    logger.warn('Error fetching data from %s: %s' % (airdcpphost, e))
                    return json.dumps(
                        {"status": False, "message": "Unable to retrieve data from AirDC++.", "version": str(version)})
            else:
                return json.dumps(
                    {"status": False, "message": "Unable to retrieve data from AirDC++.", "version": str(version)})

        logger.fdebug('status code: ' + str(r.status_code))

        if str(r.status_code) != '200':
            logger.warn('Unable to properly query AirDC++ @' + airdcpphost + ' [Status Code returned: ' + str(
                r.status_code) + ']')
            return json.dumps(
                {"status": False, "message": "Invalid credentials or connection error.", "version": str(version)})
        else:
            data = r.json()
            try:
                # Try to extract version from the response
                version = data.get('client_version', 'Unknown')
                logger.info('AirDC++ version: %s' % version)

                # Save the version to config
                mylar.CONFIG.AIRDCPP_VERSION = version
                mylar.CONFIG.writeconfig(values={'airdcpp_version': version})

                return json.dumps(
                    {"status": True, "message": "Successfully connected to AirDC++.", "version": str(version)})
            except Exception as e:
                logger.error('Error parsing AirDC++ response: %s' % e)
                return json.dumps(
                    {"status": False, "message": "Error parsing AirDC++ response.", "version": str(version)})

    AirDCPPtest.exposed = True

    def NZBGet_test(self, nzbhost=None, nzbport=None, nzbusername=None, nzbpassword=None, nzbsub=None):
        if any([nzbhost is None, nzbhost == 'None']):
            nzbhost = mylar.CONFIG.NZBGET_HOST
        if any([nzbport is None, nzbport == 'None']):
            nzbport = mylar.CONFIG.NZBGET_PORT
        if any([nzbusername is None, nzbusername == 'None']):
            nzbusername = mylar.CONFIG.NZBGET_USERNAME
        if any([nzbpassword is None, nzbpassword == 'None']):
            nzbpassword = mylar.CONFIG.NZBGET_PASSWORD
        if any([nzbsub is None, nzbsub == 'None']):
            nzbsub = mylar.CONFIG.NZBGET_SUB

        logger.fdebug('Now attempting to test NZBGet connection')

        logger.info('Now testing connection to NZBGet @ %s:%s' % (nzbhost, nzbport))
        if nzbhost[:5] == 'https':
            protocol = 'https'
            nzbgethost = nzbhost[8:]
        elif nzbhost[:4] == 'http':
            protocol = 'http'
            nzbgethost = nzbhost[7:]

        url = '%s://%s:%s'
        nzbparams = (protocol,nzbgethost,nzbport)
        if nzbsub:
            if not nzbsub.startswith('/'):
                nzbsub = '/' + nzbsub
            if nzbsub.endswith('/'):
                nzbsub = nzbsub[:-1]
            url = '%s://%s:%s%s'
            nzbparams = nzbparams + (nzbsub,)

        logon_info = ''
        if all([nzbusername is not None, nzbpassword is not None]):
            logon_info = '%s:%s'
            nzbparams = nzbparams + (nzbusername, nzbpassword,)
        elif nzbusername is not None:
            logon_info = '%s:'
            nzbparams = nzbparams + (nzbusername,)
        if logon_info != '':
            url = url + '/' + logon_info
        url = url + '/xmlrpc'
        nzb_url = (url % nzbparams)

        import xmlrpc.client, http.client, socket
        nzbserver = xmlrpc.client.ServerProxy(nzb_url)
        socket.setdefaulttimeout(5)

        try:
            r = nzbserver.status()
            socket.setdefaulttimeout(None)
        except http.client.socket.error as e:
            #err = re.sub(nzbpassword, 'REDACTED', str(e))
            logger.error('Please check your NZBget host and port (if it is running). Error returned: %s' % e)
            return 'Invalid NZBGET host / port'
        except xmlrpc.client.ProtocolError as e:
            logger.info(e,)
            err = re.sub(nzbpassword, 'REDACTED', e.errmsg)
            if e.errmsg == "Unauthorized":
                logger.error('Unauthorized username / password provided: %s' % err)
                return 'NZBGet username/password is incorrect'
            else:
                logger.error('Protocol Error: %s' % re.sub(nzbpassword, 'REDACTED', err))
                return 'NZBGet protocol error'
        except Exception as e:
            #err = re.sub(nzbpassword, 'REDACTED', str(e))
            logger.error('Unable to retrieve data from nzbget. Error returned: %s' % e)
            return 'NZBGet protocol error'
        else:
            logger.info('Successfully verified connection to NZBGet')
            return "Successfully verified connection to NZBGet"
    NZBGet_test.exposed = True

    def carepackage(self):
        cp = carepackage.carePackage()
        file_to_care = cp.loaders()
        from cherrypy.lib.static import serve_download
        return serve_download(file_to_care['carepackage'])
    carepackage.exposed = True

    def shutdown(self):
        mylar.SIGNAL = 'shutdown'
        message = 'Shutting Down...'
        return serve_template(templatename="shutdown.html", title="Shutting Down", message=message, timer=15)
        return page
    shutdown.exposed = True

    def restart(self):
        mylar.SIGNAL = 'restart'
        message = 'Restarting...'
        return serve_template(templatename="shutdown.html", title="Restarting", message=message, timer=30)
    restart.exposed = True

    def update(self):
        mylar.SIGNAL = 'update'
        message = 'Updating...<br/><small>Main screen will appear in 60s</small>'
        return serve_template(templatename="shutdown.html", title="Updating", message=message, timer=30)
    update.exposed = True

    def getInfo(self, ComicID=None, IssueID=None):

        from mylar import cache
        info_dict = cache.getInfo(ComicID, IssueID)

        return simplejson.dumps(info_dict)

    getInfo.exposed = True

    def getComicArtwork(self, ComicID=None, imageURL=None):

        from mylar import cache
        logger.info("Retrieving image for : " + comicID)
        return cache.getArtwork(ComicID, imageURL)

    getComicArtwork.exposed = True

    def findsabAPI(self, sabhost=None, sabusername=None, sabpassword=None):
        sp = sabparse.sabnzbd(sabhost, sabusername, sabpassword)
        sabapi = sp.sab_get()
        logger.info('SAB API Key found as : ' + str(sabapi) + '. You still have to save the config to retain this setting.')
        mylar.CONFIG.SAB_APIKEY = sabapi
        return sabapi

    findsabAPI.exposed = True

    def generateAPI(self):

        import hashlib

        apikey = hashlib.sha256(str(random.getrandbits(256)).encode('utf-8')).hexdigest()[0:32]
        logger.info("New API generated")
        mylar.CONFIG.API_KEY = apikey
        return apikey

    generateAPI.exposed = True

    def api(self, *args, **kwargs):

        from mylar.api import Api

        a = Api()

        a.checkParams(*args, **kwargs)

        data = a.fetchData()

        return data

    api.exposed = True

    def prometheus_metrics(self):
        logger.debug("Responding to Prometheus metrics request")
        cherrypy.response.headers['Content-Type'] = "text/plain"
        q_metrics = {name: {} for name in ["alive", "size", "started"]}
        for q in helpers.queue_info():
            normalised_name = q.name.replace("-", "_")

            q_metrics["size"][normalised_name] = q.size
            q_metrics["started"][normalised_name] = "1" if q.is_alive is not None else "0"
            q_metrics["alive"][normalised_name] = "1" if q.is_alive else "0"

        response = ""
        for metric, items in q_metrics.items():
            full_metric = f"mylar_queue_{metric}"
            response += f"# TYPE {full_metric} gauge\n"
            for name, value in items.items():
                response += '%s{queue="%s"} %s\n' % (full_metric, name, value)
            response += "\n"
        return response

    prometheus_metrics.exposed = True

    def opds(self, *args, **kwargs):
        from mylar.opds import OPDS

        op = OPDS()

        op.checkParams(*args, **kwargs)

        data = op.fetchData()

        return data


    opds.exposed = True

    def downloadthis(self, issueid):
        myDB = db.DBConnection()
        issue = myDB.selectone('SELECT a.ComicLocation, b.* FROM comics a LEFT JOIN issues b ON a.comicid = b.comicid WHERE b.issueid=?', [issueid]).fetchone()
        if issue:
            secondary_folders = None
            if mylar.CONFIG.MULTIPLE_DEST_DIRS:
                try:
                    if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(issue['ComicLocation']))):
                        secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(issue['ComicLocation']))
                    else:
                        # when loading a new series initially the publisher value might not be written out the db yet.
                        # pass this all on the initial load if it's not  - it'll catch it when the page finishes loading.
                        ff = mylar.filers.FileHandlers(ComicID=issue['ComicID'])
                        secondary_folders = ff.secondary_folders(issue['ComicLocation'])
                except Exception:
                    pass
        else:
            return json.dumps({'status': 'failure', 'message': 'Unable to locate selected issue in database'})

        pathfile = None
        if all([issue['Location'] is not None, issue['ComicLocation'] is not None]):
            if os.path.exists(os.path.join(issue['ComicLocation'], issue['Location'])):
                pathfile = os.path.join(issue['ComicLocation'], issue['Location'])
            elif secondary_folders is not None:
                if os.path.exists(os.path.join(secondary_folders, issue['Location'])):
                    pathfile = os.path.join(secondary_folders, issue['Location'])

        if pathfile is None:
            return json.dumps({'status': 'failure', 'message': 'Unable to find issue - you might want to ReCheck Files'})
        else:
            dspline = 'Now downloading issue #%s of %s' % (issue['Issue_Number'], issue['ComicName'])
            return cherrypy.lib.static.serve_download( pathfile )
    downloadthis.exposed = True

    def IssueInfo(self, issueid): #filelocation, comicname=None, issue=None, date=None, title=None, issueid=None):
        myDB = db.DBConnection()
        metadata_db = myDB.selectone('SELECT a.ComicLocation, b.* FROM comics a LEFT JOIN issues b ON a.comicid=b.comicid where b.IssueID=?', [issueid]).fetchone()
        if metadata_db is None:
            metadata_db = myDB.selectone('SELECT a.ComicLocation, b.* FROM comics a LEFT JOIN annuals b ON a.comicid=b.comicid where b.IssueID=? AND NOT b.Deleted', [issueid]).fetchone()
            if not metadata_db:
                metadata_db = None

        filepath = None
        if metadata_db:
            filelocation = metadata_db['Location']
            if filelocation is not None:
                tmpfilepath = os.path.join(metadata_db['ComicLocation'],filelocation)
                if not os.path.isfile(tmpfilepath):
                    if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                        if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(metadata_db['ComicLocation']))):
                            secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(metadata_db['ComicLocation']))
                        else:
                            ff = mylar.filers.FileHandlers(ComicID=metadata_db['ComicID'])
                            secondary_folders = ff.secondary_folders(metadata_db['ComicLocation'])
                        filepath = os.path.join(secondary_folders, filelocation)
                else:
                    filepath = tmpfilepath

        issuedetails = helpers.IssueDetails(filepath, IssueID=issueid)

        issuewriter = []
        issuepenciller = []
        issueletterer = []
        issueeditor = []
        issueinker = []
        issuecolorist = []
        issuecoverartist = []
        seriestitle = None
        meta_data = issuedetails['metadata']
        if issuedetails['datamode'] == 'single_issue':
            seriestitle = meta_data['series']
            issuenumber = meta_data['issue_number']
            issuetitle = meta_data['title']
            issuesummary = meta_data['description']
            issue_rls = meta_data['storedate']
            if issue_rls is None:
                issue_rls = meta_data['coverdate']
            if issue_rls is None:
                issueday = '00'
                issuemonth = '00'
                issueyear = '0000'
            else:
                issueday = issue_rls[8:10]
                issuemonth = issue_rls[5:7]
                issueyear = issue_rls[:4]
            for xi in meta_data['credits']:
                if xi['role'] == 'writer':
                    issuewriter.append(xi['name'])
                if xi['role'] == 'penciller':
                    issuepenciller.append(xi['name'])
                if xi['role'] == 'inker':
                    issueinker.append(xi['name'])
                if xi['role'] == 'colorist':
                    issuecolorist.append(xi['name'])
                if xi['role'] == 'letterer':
                    issueletterer.append(xi['name'])
                if xi['role'] == 'editor':
                    issueeditor.append(xi['name'])
                if xi['role'] == 'cover artist':
                    issuecoverartist.append(xi['name'])
            pagecount = None
        elif all([seriestitle is None, meta_data is None]): # and 'series' not in meta_data:
            myDB = db.DBConnection()
            logger.info('issueid: %s' % (issueid))
            meta_data = myDB.selectone('SELECT * FROM issues where IssueID=?', [issueid]).fetchone()
            if meta_data is None:
                meta_data = myDB.selectone('SELECT * FROM annuals where IssueID=? AND NOT Deleted', [issueid]).fetchone()
            seriestitle = meta_data['ComicName']
            issuenumber = meta_data['Issue_Number']
            try:
                issuetitle = meta_data['IssueName'].decode('utf-8')
            except:
                issuetitle = meta_data['IssueName']
            issue_rls = meta_data['IssueDate']
            if issue_rls is None:
                issue_rls = meta_data['StoreDate']
            pagecount = None
            issueday = issue_rls[8:10]
            issuemonth = issue_rls[5:7]
            issueyear = issue_rls[:4]
            issuesummary = None
        else:
            logger.info('meta_data: %s' % (meta_data,))
            myDB = db.DBConnection()
            metadata_db = myDB.selectone('SELECT * FROM issues where IssueID=?', [issueid]).fetchone()
            if metadata_db is None:
                metadata_db = myDB.selectone('SELECT * FROM annuals where IssueID=? AND NOT Deleted', [issueid]).fetchone()
                if not metadata_db:
                    metadata_db = None
            seriestitle = meta_data['series']
            if any([seriestitle == 'None', seriestitle is None]) and metadata_db is not None:
                seriestitle = metadata_db['ComicName']

            issuenumber = meta_data['issue_number']
            if any([issuenumber == 'None', issuenumber is None]) and metadata_db is not None:
                issuenumber = metadata_db['Issue_Number']

            issuetitle = meta_data['title']
            if any([issuetitle == 'None', issuetitle is None]) and metadata_db is not None:
                issuetitle = metadata_db['IssueName']
            else:
                issuetitle = issuetitle
            try:
                pagecount = meta_data['pagecount']
            except:
                pagecount = None
            issueday = meta_data['day']
            issuemonth = meta_data['month']
            issueyear = meta_data['year']

            if meta_data['writer'] is not None:
                issuewriter = meta_data['writer']
            if meta_data['penciller'] is not None:
                issuepenciller = meta_data['penciller']
            if meta_data['inker'] is not None:
                issueinker = meta_data['inker']
            if meta_data['colorist'] is not None:
                issuecolorist = meta_data['colorist']
            if meta_data['letterer'] is not None:
                issueletterer = meta_data['letterer']
            if meta_data['editor'] is not None:
                issueeditor = meta_data['editor']
            if meta_data['cover_artist'] is not None:
                issuecoverartist = meta_data['cover_artist']
            issuesummary = meta_data['summary']
        if meta_data is not None:
            iss_filename = None
            if filelocation is not None:
                iss_filename = os.path.split(filelocation)[1]

            if all([issueday is None, issuemonth is None, issueyear is None]):
                iss_date = date
            else:
                iss_date = '%s-%s-%s' % (issueyear, issuemonth, issueday)

            if issuetitle == 'None':
                issuetitle = None
            writers = None
            pencillers = None
            inkers = None
            colorists = None
            letterers = None
            editors = None
            coverartists = None
            if len(issuewriter) > 0:
                writers = issuewriter
                if type(issuewriter) == list:
                    writers = ', '.join(issuewriter).strip()
            if len(issuepenciller) > 0:
                pencillers = issuepenciller
                if type(issuepenciller) == list:
                    pencillers = ', '.join(issuepenciller).strip()
            if len(issueinker) > 0:
                inkers = issueinker
                if type(issueinker) == list:
                    inkers = ', '.join(issueinker).strip()
            if len(issuecolorist) > 0:
                colorists = issuecolorist
                if type(issuecolorist) == list:
                    colorists = ', '.join(issuecolorist).strip()
            if len(issueletterer) > 0:
                letterers = issueletterer
                if type(issueletterer) == list:
                    letterers = ', '.join(issueletterer).strip()
            if len(issueeditor) > 0:
                editors = issueeditor
                if type(issueeditor) == list:
                    editors = ', '.join(issueeditor).strip()
            if len(issuecoverartist) > 0:
                coverartists = issuecoverartist
                if type(issuecoverartist) == list:
                    coverartists = ', '.join(issuecoverartist).strip()

            issuesumm = None
            if any([issuesummary == 'None', issuesummary is None]):
                issuesumm = 'No summary available within metatagging.'
            else:
                if len(issuesummary) > 1000:
                    issuesumm = issuesummary[:1000] + '...'
                else:
                    issuesumm = issuesummary

            meta_success = 'success'

            issue_meta = {'series': seriestitle,
                          'issue_number': issuenumber,
                          'issue_title': issuetitle,
                          'pagecount': pagecount,
                          'issuedate': iss_date,
                          'filename': iss_filename,
                          'summary': issuesumm,
                          'writers': writers,
                          'pencillers': pencillers,
                          'inkers': inkers,
                          'colorists': colorists,
                          'letterers': letterers,
                          'editors': editors,
                          'cover_artists': coverartists,
                          'metadata_source': issuedetails['metadata_source']['metadata_source'],
                          'metadata_type': issuedetails['metadata_source']['metadata_type']}
        else:
            meta_success = 'failure'
            issue_meta = {'series': seriestitle,
                          'issue_number': issuenumber,
                          'filename': iss_filename}

        return json.dumps({'status': meta_success, 'metadata': issue_meta, 'IssueImage': issuedetails['IssueImage']})

    IssueInfo.exposed = True

    def manual_metatag(self, issueid, comicid=None, group=False): #dirName, issueid, filename, comicid, comversion, seriesyear=None, group=False, agerating=None):
        module = '[MANUAL META-TAGGING]'
        try:
            myDB = db.DBConnection()
            issuedata = myDB.selectone('SELECT a.ComicVersion, a.ComicLocation, a.ComicYear, a.AgeRating, b.* FROM comics a LEFT JOIN issues b ON a.ComicID=b.ComicID WHERE b.IssueID=?', [issueid]).fetchone()
            if not issuedata:
                issuedata = myDB.selectone('SELECT a.ComicVersion, a.ComicLocation, a.ComicYear, a.AgeRating, b.* FROM comics a LEFT JOIN annuals b ON a.ComicID=b.ComicID WHERE b.IssueID=? AND NOT b.Deleted', [issueid]).fetchone()
                if not issuedata:
                    mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': None, 'seriesyear': None, 'comicid': comicid, 'tables': 'both', 'message': 'Unable to locate corresponding issueid: %s' % issueid}
                    return

            comversion = issuedata['ComicVersion']
            dirName = issuedata['ComicLocation']
            filename = os.path.join(dirName, issuedata['Location'])
            if not os.path.exists(filename):
                file_check = list(Path(dirName).rglob('*'+issuedata['Location']))
                if len(file_check) > 0:
                    filename = str(file_check[0])
                    dirName = str(Path(filename).parent.absolute())

            if not os.path.exists(filename):
                if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                    if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(dirName))):
                        secondary_folder = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(dirName))
                    else:
                        ff = mylar.filers.FileHandlers(ComicID=issuedata['ComicID'])
                        secondary_folder = ff.secondary_folders(dirName)

                    if os.path.join(secondary_folder, os.path.basename(filename)):
                        dirName = secondary_folder
                        filename = os.path.join(secondary_folder, os.path.basename(filename))
                        if not os.path.exists(filename):
                            file_check = list(Path(dirName).rglob('*'+issuedata['Location']))
                            if len(file_check) > 0:
                                filename = str(file_check[0])
                                dirName = str(Path(filename).parent.absolute())

            if not os.path.exists(filename):
                logger.warn('%s %s does not exist in the given location. Cannot metatag this filename due to this.' % (module, filename))
                mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': None, 'seriesyear': None, 'comicid': comicid, 'tables': 'both', 'message': 'Unable to locate corresponding filename: %s' % filename}
                return

            comicid = issuedata['ComicID']
            seriesyear = issuedata['ComicYear']
            agerating = issuedata['AgeRating']
            comicname = issuedata['ComicName']

            from . import cmtagmylar
            if mylar.CONFIG.CMTAG_START_YEAR_AS_VOLUME:
                if all([seriesyear is not None, seriesyear != 'None']):
                    vol_label = seriesyear
                else:
                    logger.warn('Cannot populate the year for the series for some reason. Dropping down to numeric volume label.')
                    vol_label = comversion
            else:
                vol_label = comversion

            if all([issueid is not None, comicid is not None]):
                roders = myDB.select('SELECT StoryArc, ReadingOrder from storyarcs WHERE ComicID=? AND IssueID=?', [comicid, issueid])
                readingorder = None
                if roders is not None:
                    readingorder = []
                    for rd in roders:
                        readingorder.append((rd['StoryArc'], rd['ReadingOrder']))
                    logger.fdebug('readingorder: %s' % (readingorder))

            metaresponse = cmtagmylar.run(dirName, issueid=issueid, filename=filename, comversion=vol_label, manualmeta=True, readingorder=readingorder, agerating=agerating)
        except ImportError:
            logger.warn(module + ' comictaggerlib not found on system. Ensure the ENTIRE lib directory is located within mylar/lib/comictaggerlib/ directory.')
            metaresponse = "fail"

        if metaresponse == "fail":
            logger.fdebug(module + ' Unable to write metadata successfully - check mylar.log file.')
            mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': comicname, 'seriesyear': seriesyear, 'comicid': comicid, 'tables': 'both', 'message': 'Unable to write metadata - there were errors. Check the log files'}
            return
        elif metaresponse == "unrar error":
            logger.error(module + ' This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and retrying a different copy.')
            mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': comicname, 'seriesyear': seriesyear, 'comicid': comicid, 'tables': 'both', 'message': '%s is a corrupt archive.' % dst_filename}
            return
            #launch failed download handling here.
        else:
            dst_filename = os.path.split(metaresponse)[1]
            dst = os.path.join(dirName, dst_filename)
            fail = False
            try:
                shutil.copy(metaresponse, dst)
                logger.info('%s Sucessfully wrote metadata to .cbz (%s) - Continuing..' % (module, dst_filename))
            except Exception as e:
                if str(e.errno) == '2':
                    try:
                        if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                            if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(dirName))):
                                secondary_folder = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(dirName))
                            else:
                                ff = mylar.filers.FileHandlers(ComicID=comicid)
                                secondary_folder = ff.secondary_folders(dirName)

                            shutil.copy(metaresponse, secondary_folder)
                            logger.info('%s Sucessfully wrote metadata to .cbz (%s) - Continuing..' % (module, dst_filename))
                    except Exception as e:
                        logger.warn('%s [%s] Unable to complete metatagging : %s [%s]' % (module, secondary_folder, e, e.errno))
                        fail = True
                else:
                    logger.warn('%s [%s] Unable to complete metatagging : %s [%s]' % (module, dst, e, e.errno))
                    fail = True
            if not fail:
                cache_dir = os.path.split(metaresponse)[0]
                if os.path.isfile(metaresponse):
                    try:
                        os.remove(metaresponse)
                    except OSError:
                        pass

                if not os.listdir(cache_dir):
                    logger.fdebug('%s Tidying up. Deleting temporary cache directory: %s' % (module, cache_dir))
                    try:
                        shutil.rmtree(cache_dir)
                    except Exception as e:
                        logger.warn(module + ' Unable to remove temporary directory: %s' % cache_dir)
                else:
                    logger.fdebug('Failed to remove temporary directory: %s' % cache_dir)

                if filename is not None:
                    if os.path.isfile(filename) and os.path.split(filename)[1].lower() != dst_filename.lower():
                        try:
                            logger.fdebug('%s Removing original filename: %s' % (module, filename))
                            os.remove(filename)
                        except OSError:
                            pass

        if all([group is False, fail is False]):
            updater.forceRescan(comicid)
            if group is False:
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': comicname, 'seriesyear': seriesyear, 'comicid': comicid, 'tables': 'both', 'message': 'Successfully meta-tagged %s' % dst_filename}
        elif all([group is False, fail is True]):
            mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': comicname, 'seriesyear': seriesyear, 'comicid': comicid, 'tables': 'both', 'message': 'Metatagging was not successful for %s' % dst_filename}

    manual_metatag.exposed = True

    def bulk_metatag(self, ComicID, IssueIDs, threaded=False):
        myDB = db.DBConnection()
        cinfo = myDB.selectone('SELECT ComicLocation, ComicVersion, ComicYear, ComicName, AgeRating FROM comics WHERE ComicID=?', [ComicID]).fetchone()

        comicinfo = {'ComicID': ComicID,
                     'ComicName': cinfo['ComicName'],
                     'ComicYear': cinfo['ComicYear'],
                     'ComicVersion': cinfo['ComicVersion'],
                     'AgeRating': cinfo['AgeRating'],
                     'meta_dir': cinfo['ComicLocation']}
        
        if not isinstance(IssueIDs, list):
            IssueIDs = [IssueIDs]
        
        issueList = ', '.join(IssueIDs)
        groupinfo = myDB.select(f'SELECT IssueID, Location FROM issues WHERE ComicID={ComicID} and IssueID IN ({issueList}) and Location is not NULL')
        if mylar.CONFIG.ANNUALS_ON:
            groupinfo += myDB.select(f'SELECT IssueID, Location FROM annuals WHERE ComicID={ComicID} and IssueID IN ({issueList}) and Location is not NULL')

        if len(groupinfo) == 0:
            logger.warn('No issues physically exist for me to (re)-tag.')
            return
        
        if mylar.CONFIG.CV_BATCH_LIMIT_PROTECTION and len(groupinfo) > mylar.CONFIG.CV_BATCH_LIMIT_THRESHOLD:
            warningMessage = f"CV Batch Limit Protection ({mylar.CONFIG.CV_BATCH_LIMIT_THRESHOLD}) has been triggered trying to tag {len(groupinfo)} issues.  This will likely breach ComicVine API Limits."
            logger.warn(f"[SERIES-METATAGGER][{comicinfo['ComicName']} ({comicinfo['ComicYear']})] {warningMessage}")
            mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': cinfo['ComicName'], 'seriesyear': cinfo['ComicYear'], 'comicid': ComicID, 'tables': 'both', 'message': warningMessage}
            return
        
        issueinfo = []
        for ginfo in groupinfo:
            issueinfo.append({'IssueID': ginfo['IssueID'],
                              'Location': ginfo['Location']})        

        if threaded is False:
            threading.Thread(target=self.thread_that_bulk_meta, args=[comicinfo, issueinfo]).start()
            return json.dumps({'status': 'success'})
        else:
            self.thread_that_bulk_meta(comicinfo, issueinfo)
            return json.dumps({'status': 'success'})        
    bulk_metatag.exposed = True

    def thread_that_bulk_meta(self, comicinfo, issueinfo):
        for ginfo in issueinfo:
            #if multiple_dest_dirs is in effect, metadir will be pointing to the wrong location and cause a 'Unable to create temporary cache location' error message
            self.manual_metatag(ginfo['IssueID'], group=True)
        updater.forceRescan(comicinfo['ComicID'])
        logger.info('[SERIES-METATAGGER][%s (%s)] Finished (re)tagging of metadata for selected issues.' % (comicinfo['ComicName'], comicinfo['ComicYear']))
        issueline = '%s issues' % len(issueinfo)
        if len(issueinfo) == 1:
            issueline = '1 issue'
        mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': comicinfo['ComicName'], 'seriesyear': comicinfo['ComicYear'], 'comicid': comicinfo['ComicID'], 'tables': 'both', 'message': 'Finished (re)tagging of %s of %s (%s)' % (issueline, comicinfo['ComicName'], comicinfo['ComicYear'])}
    thread_that_bulk_meta.exposed = True

    def group_metatag(self, ComicID, threaded=False):
        myDB = db.DBConnection()
        cinfo = myDB.selectone('SELECT ComicLocation, ComicVersion, ComicYear, ComicName, AgeRating FROM comics WHERE ComicID=?', [ComicID]).fetchone()

        comicinfo = {'ComicID': ComicID,
                     'ComicName': cinfo['ComicName'],
                     'ComicYear': cinfo['ComicYear'],
                     'ComicVersion': cinfo['ComicVersion'],
                     'AgeRating': cinfo['AgeRating'],
                     'meta_dir': cinfo['ComicLocation']}

        groupinfo = myDB.select('SELECT IssueID, Location FROM issues WHERE ComicID=? and Location is not NULL', [ComicID])
        if mylar.CONFIG.ANNUALS_ON:
            groupinfo += myDB.select('SELECT IssueID, Location FROM annuals WHERE ComicID=? and Location is not NULL', [ComicID])

        if len(groupinfo) == 0:
            logger.warn('No issues physically exist within the series directory for me to (re)-tag.')
            return

        if mylar.CONFIG.CV_BATCH_LIMIT_PROTECTION and len(groupinfo) > mylar.CONFIG.CV_BATCH_LIMIT_THRESHOLD:
            warningMessage = f"CV Batch Limit Protection ({mylar.CONFIG.CV_BATCH_LIMIT_THRESHOLD}) has been triggered trying to tag {len(groupinfo)} issues.  This will likely breach ComicVine API Limits."
            logger.warn(f"[SERIES-METATAGGER][{comicinfo['ComicName']} ({comicinfo['ComicYear']})] {warningMessage}")
            mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': cinfo['ComicName'], 'seriesyear': cinfo['ComicYear'], 'comicid': ComicID, 'tables': 'both', 'message': warningMessage}
            return

        issueinfo = []
        for ginfo in groupinfo:
            issueinfo.append({'IssueID': ginfo['IssueID'],
                              'Location': ginfo['Location']})

        if threaded is False:
            threading.Thread(target=self.thread_that_meta, args=[comicinfo, issueinfo]).start()
            return json.dumps({'status': 'success'})
        else:
            self.thread_that_meta(comicinfo, issueinfo)
            return json.dumps({'status': 'success'})
    group_metatag.exposed = True

    def thread_that_meta(self, comicinfo, issueinfo):
        for ginfo in issueinfo:
            #if multiple_dest_dirs is in effect, metadir will be pointing to the wrong location and cause a 'Unable to create temporary cache location' error message
            self.manual_metatag(ginfo['IssueID'], group=True)
        updater.forceRescan(comicinfo['ComicID'])
        logger.info('[SERIES-METATAGGER][%s (%s)] Finished complete series (re)tagging of metadata.' % (comicinfo['ComicName'], comicinfo['ComicYear']))
        issueline = '%s issues' % len(issueinfo)
        if len(issueinfo) == 1:
            issueline = '1 issue'
        mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': comicinfo['ComicName'], 'seriesyear': comicinfo['ComicYear'], 'comicid': comicinfo['ComicID'], 'tables': 'both', 'message': 'Finished complete series (re)tagging of %s of %s (%s)' % (issueline, comicinfo['ComicName'], comicinfo['ComicYear'])}
    thread_that_meta.exposed = True

    def CreateFolders(self, createfolders=None):
        if createfolders:
            mylar.CONFIG.CREATE_FOLDERS = int(createfolders)
            #mylar.config_write()

    CreateFolders.exposed = True

    def getPushbulletDevices(self, api=None):
        notifythis = notifiers.PUSHBULLET(test_apikey=api)
        result = notifythis.get_devices()
        if result:
            return json.dumps(result)
        else:
            return 'Error sending Pushbullet notifications.'
    getPushbulletDevices.exposed = True

    def syncfiles(self):
        #3 status' exist for the readlist.
        # Added (Not Read) - Issue is added to the readlist and is awaiting to be 'sent' to your reading client.
        # Read - Issue has been read
        # Not Read - Issue has been downloaded to your reading client after the syncfiles has taken place.
        read = readinglist.Readinglist()
        threading.Thread(target=read.syncreading).start()
    syncfiles.exposed = True

    def search_32p(self, search=None):
        return mylar.rsscheck.torrents(pickfeed='4', seriesname=search)
    search_32p.exposed = True

    def testprowl(self):
        prowl = notifiers.prowl()
        result = prowl.test_notify()
        if result:
            return "Successfully sent Prowl test -  check to make sure it worked"
        else:
            return "Error sending test message to Prowl"
    testprowl.exposed = True

    def testboxcar(self):
        boxcar = notifiers.boxcar()
        result = boxcar.test_notify()
        if result:
            return "Successfully sent Boxcar test -  check to make sure it worked"
        else:
            return "Error sending test message to Boxcar"
    testboxcar.exposed = True

    def testpushover(self, apikey, userkey, device):
        pushover = notifiers.PUSHOVER(test_apikey=apikey, test_userkey=userkey, test_device=device)
        result = pushover.test_notify()
        if result == True:
            return "Successfully sent PushOver test -  check to make sure it worked"
        else:
            logger.warn('Last six characters of the test variables used [APIKEY: %s][USERKEY: %s]' % (apikey[-6:], userkey[-6:]))
            return "Error sending test message to Pushover"
    testpushover.exposed = True

    def testpushbullet(self, apikey, channel):
        pushbullet = notifiers.PUSHBULLET(test_apikey=apikey, channel=channel)
        result = pushbullet.test_notify()
        if result['status'] == True:
            return "Successfully sent Pushbullet test -  check to make sure it worked"
        else:
            logger.warn('Last six characters of the test variables used [APIKEY: %s][CHANNEL: %s]' % (apikey[-6:], channel[-6:]))
            return "Error sending test message to Pushbullet"
    testpushbullet.exposed = True

    def testtelegram(self, userid, token):
        telegram = notifiers.TELEGRAM(test_userid=userid, test_token=token)
        result = telegram.test_notify()
        if result == True:
            return "Successfully sent Telegram test -  check to make sure it worked"
        else:
            logger.warn('Test variables used [USERID: %s][TOKEN: %s]' % (userid, token))
            return "Error sending test message to Telegram"
    testtelegram.exposed = True

    def testslack(self, webhook_url):
        slack = notifiers.SLACK(test_webhook_url=webhook_url)
        result = slack.test_notify()

        if result == True:
            return "Successfully sent Slack test -  check to make sure it worked"
        else:
            logger.warn('Test variables used [WEBHOOK_URL: %s][USERNAME: %s]' % (webhook_url, username))
            return "Error sending test message to Slack"
    testslack.exposed = True

    def testmattermost(self, webhook_url):
        mattermost = notifiers.MATTERMOST(test_webhook_url=webhook_url)
        result = mattermost.test_notify()

        if result == True:
            return "Successfully sent Mattermost test -  check to make sure it worked"
        else:
            logger.warn('Test variables used [WEBHOOK_URL: %s][USERNAME: %s]' % (webhook_url, username))
            return "Error sending test message to Mattermost"
    testmattermost.exposed = True

    def testdiscord(self, webhook_url):
        discord = notifiers.DISCORD(test_webhook_url=webhook_url)
        result = discord.test_notify()

        if result == True:
            return "Successfully sent Discord test -  check to make sure it worked"
        else:
            logger.warn('Test variables used [WEBHOOK_URL: %s]' % (webhook_url))
            return "Error sending test message to Discord"
    testdiscord.exposed = True

    def testemail(self, emailfrom, emailto, emailsvr, emailport, emailuser, emailpass, emailenc):
        email = notifiers.EMAIL(test_emailfrom=emailfrom, test_emailto=emailto, test_emailsvr=emailsvr, test_emailport=emailport, test_emailuser=emailuser, test_emailpass=emailpass, test_emailenc=emailenc)
        result = email.test_notify()

        if result == True:
            return "Successfully sent email. Check your mailbox."
        else:
            logger.warn('Email test has gone horribly wrong. Variables used were [FROM: %s] [TO: %s] [SERVER: %s] [PORT: %s] [USER: %s] [PASSWORD: ********] [ENCRYPTION: %s]' % (emailfrom, emailto, emailsvr, emailport, emailuser, emailenc))
            return "Error sending test message via email"
    testemail.exposed = True

    def testgotify(self, webhook_url):
        gotify = notifiers.GOTIFY(test_webhook_url=webhook_url)
        result = gotify.test_notify()

        if result == True:
            return "Successfully sent Gotify test -  check to make sure it worked"
        else:
            logger.warn('Test variables used [WEBHOOK_URL: %s][USERNAME: %s]' % (webhook_url, username))
            return "Error sending test message to Gotify"
    testgotify.exposed = True

    def testrtorrent(self, host, username, password, auth, verify, rpc_url):
        if verify == 'true':
            verify = True
        elif verify == 'false':
            verify = False
        from mylar.torrent.clients import rtorrent as TorClient
        client = TorClient.TorrentClient()
        ca_bundle = None
        if mylar.CONFIG.RTORRENT_CA_BUNDLE is not None:
            ca_bundle = mylar.CONFIG.RTORRENT_CA_BUNDLE
        rclient = client.connect(host, username, password, auth, verify, rpc_url, ca_bundle, test=True)
        if not rclient:
            logger.warn('Could not establish connection to %s' % host)
            return '[rTorrent] Error establishing connection to Rtorrent'
        else:
            if rclient['status'] is False:
                logger.warn('[rTorrent] Could not establish connection to %s. Error returned: %s' % (host, rclient['error']))
                return 'Error establishing connection to rTorrent'
            else:
                logger.info('[rTorrent] Successfully validated connection to %s [v%s]' % (host, rclient['version']))
                return 'Successfully validated rTorrent connection'
    testrtorrent.exposed = True

    def testqbit(self, host, username, password):
        from mylar.torrent.clients import qbittorrent as QbitClient
        qc = QbitClient.TorrentClient()
        qclient = qc.connect(host, username, password, True)
        if not qclient:
            logger.warn('[qBittorrent] Could not establish connection to %s' % host)
            return 'Error establishing connection to Qbittorrent'
        else:
            if qclient['status'] is False:
                logger.warn('[qBittorrent] Could not establish connection to %s. Error returned: %s' % (host, qclient['error']))
                return 'Error establishing connection to Qbittorrent'
            else:
                logger.info('[qBittorrent] Successfully validated connection to %s [v%s]' % (host, qclient['version']))
                return 'Successfully validated qBittorrent connection'
    testqbit.exposed = True

    def testdeluge(self, host, username, password):
        from mylar.torrent.clients import deluge as DelugeClient
        client = DelugeClient.TorrentClient()
        dclient = client.connect(host, username, password, True)
        if not dclient:
            logger.warn('[Deluge] Could not establish connection to %s' % host)
            return 'Error establishing connection to Deluge'
        else:
            if dclient['status'] is False:
                logger.warn('[Deluge] Could not establish connection to %s. Error returned: %s' % (host, dclient['error']))
                return 'Error establishing connection to Deluge'
            else:
                logger.info('[Deluge] Successfully validated connection to %s [daemon v%s; libtorrent v%s]' % (host, dclient['daemon_version'], dclient['libtorrent_version']))
                return 'Successfully validated Deluge connection'
    testdeluge.exposed = True

    def testnewznab(self, name, host, ssl, apikey):
        logger.fdebug('ssl/verify: %s' % ssl)
        if ssl == '0' or ssl == '1':
            ssl = bool(int(ssl))
        else:
            if ssl == 'false':
                ssl = False
            else:
                ssl = True
        result = helpers.newznab_test(name, host, ssl, apikey)
        if result is True:
            logger.info('Successfully tested %s [%s] - valid api response received' % (name, host))
            return 'Successfully tested %s!' % name
        else:
            logger.warn('Testing failed to %s [HOST:%s][SSL:%s]' % (name, host, bool(ssl)))
            return 'Error - failed running test for %s' % name
    testnewznab.exposed = True

    def testtorznab(self, name, host, ssl, apikey):
        logger.fdebug('ssl/verify: %s' % ssl)
        if ssl == '0' or ssl == '1':
            ssl = bool(int(ssl))
        else:
            if ssl == 'false':
                ssl = False
            else:
                ssl = True
        result = helpers.torznab_test(name, host, ssl, apikey)
        if result is True:
            logger.info('Successfully tested %s [%s] - valid api response received' % (name, host))
            return 'Successfully tested %s!' % name
        else:
            logger.warn('Testing failed to %s [HOST:%s][SSL:%s]' % (name, host, bool(ssl)))
            return 'Error - failed running test for %s' % name
    testtorznab.exposed = True

    def orderThis(self, **kwargs):
        return
    orderThis.exposed = True

    def torrentit(self, issueid=None, torrent_hash=None, download=False):
        #make sure it's bool'd here.
        if download == 'True':
            download = True
        else:
            download = False

        if mylar.CONFIG.AUTO_SNATCH is False:
            logger.warn('Auto-Snatch is not enabled - this will ONLY work with auto-snatch enabled and configured. Aborting request.')
            return  'Unable to complete request - please enable auto-snatch if required'

        torrent_info = helpers.torrentinfo(issueid, torrent_hash, download)

        if torrent_info:
            torrent_name = torrent_info['name']
            torrent_info['filesize'] = helpers.human_size(torrent_info['total_filesize'])
            torrent_info['download'] = helpers.human_size(torrent_info['download_total'])
            torrent_info['upload'] = helpers.human_size(torrent_info['upload_total'])
            torrent_info['seedtime'] = helpers.humanize_time(amount=int(time.time()) - torrent_info['time_started'])

            logger.info("Client: %s", mylar.CONFIG.RTORRENT_HOST)
            logger.info("Directory: %s", torrent_info['folder'])
            logger.info("Name: %s", torrent_info['name'])
            logger.info("Hash: %s", torrent_info['hash'])
            logger.info("FileSize: %s", torrent_info['filesize'])
            logger.info("Completed: %s", torrent_info['completed'])
            logger.info("Downloaded: %s", torrent_info['download'])
            logger.info("Uploaded: %s", torrent_info['upload'])
            logger.info("Ratio: %s", torrent_info['ratio'])
            logger.info("Seeding Time: %s", torrent_info['seedtime'])

            if torrent_info['label']:
                logger.info("Torrent Label: %s", torrent_info['label'])

            ti = '<table><tr><td>'
            ti += '<center><b>' + torrent_name + '</b></center></br>'
            if torrent_info['completed'] and download is True:
                ti += '<br><center><tr><td>AUTO-SNATCH ENABLED: ' + torrent_info['snatch_status'] + '</center></td></tr>'
            ti += '<tr><td><center>Hash: ' + torrent_info['hash'] + '</center></td></tr>'
            ti += '<tr><td><center>Location: ' + os.path.join(torrent_info['folder'], torrent_name) + '</center></td></tr></br>'
            ti += '<tr><td><center>Filesize: ' + torrent_info['filesize'] + '</center></td></tr>'
            ti += '<tr><td><center>' + torrent_info['download'] + ' DOWN / ' + torrent_info['upload'] + ' UP</center></td></tr>'
            ti += '<tr><td><center>Ratio: ' + str(torrent_info['ratio']) + '</center></td></tr>'
            ti += '<tr><td><center>Seedtime: ' + torrent_info['seedtime'] + '</center></td</tr>'
            ti += '</table>'

            logger.info('torrent_info:%s' % torrent_info)
            #commenting out the next 2 lines will return the torrent information to the screen
            #fp = mylar.process.Process(torrent_info['filepath'], torrent_info['dst_folder'], issueid=torrent_info['issueid'], failed=failed)
            #fp.post_process()

        else:
            torrent_name = 'Not Found'
            ti = 'Torrent not found (' + str(torrent_hash)

        return ti

    torrentit.exposed = True

    def get_the_hash(self, filepath):
        import hashlib, io
        import rtorrent.lib.bencode as bencode

        # Open torrent file
        torrent_file = open(os.path.join('/home/hero/mylar/cache', filepath), "rb")
        metainfo = bencode.decode(torrent_file.read())
        info = metainfo['info']
        thehash = hashlib.sha1(bencode.encode(info)).hexdigest().upper()
        logger.info('Hash: ' + thehash)

    get_the_hash.exposed = True

    def download_0day(self, week):
        logger.info('Now attempting to search for 0-day pack for week: %s' % week)
        #week contains weekinfo['midweek'] = YYYY-mm-dd of Wednesday of the given week's pull
        foundcom, prov = search.search_init('%s.%s.%s Weekly Pack' % (week[:4],week[5:7],week[8:]), None, week[:4], None, None, week, week, None, allow_packs=True, oneoff=True)

    download_0day.exposed = True

    def blockProviders(self):
        provider_list = []
        for x in mylar.PROVIDER_BLOCKLIST:
            provider_list.append({'provider': x['site'],
                                  'resume': str(datetime.datetime.utcfromtimestamp(x['resume']).replace(tzinfo=datetime.timezone.utc).strftime('%Y-%m-%d %-I:%M:%S %p')),
                                  'reason': x['reason']})
        return json.dumps(provider_list)
    blockProviders.exposed = True

    def viewSpecificLog(self, log_id):
        logger.info('log_id: %s' % log_id)
        log_file = 'specific_%s.log' % log_id
        # because log_id = rowid, we don't need to check the db - just loo at the file.
        with open(os.path.join(mylar.CONFIG.LOG_DIR, log_file)) as f:
            loglines = f.read()
            loglines = loglines.replace('\n', '</br>')
        return loglines
    viewSpecificLog.exposed = True

    def deleteSpecificLog(self, log_id=None, allspecific=None):
        myDB = db.DBConnection()
        if all([allspecific is not None, log_id is None]):
            chk_specific = myDB.select("SELECT rowid FROM exceptions_log")
            cnt = 0
            if chk_specific:
                for csc in chk_specific:
                    try:
                        log_file = 'specific_%s.log' % csc['rowid']
                        os.remove(os.path.join(mylar.CONFIG.LOG_DIR, log_file))
                        cnt+=1
                    except Exception as e:
                        logger.warn(
                            '[EXCEPTION-LOG-DELETION] Cannot find %s in the logs directory of'
                            ' %s. Error returned: %s' % (log_file, mylar.CONFIG.LOG_DIR, e)
                        )
                    try:
                        myDB.action('DELETE from exceptions_log WHERE rowid=?', [csc['rowid']])
                    except Exception as e:
                        pass

            return json.dumps({'status': 'success', 'message':'Succesfully removed %s specific log files' % cnt})

        elif allspecific != log_id:
            # for group entries
            reflines = myDB.selectone(
                           'SELECT error, func_name, filename, line_num'
                           ' FROM exceptions_log WHERE rowid=?', [log_id]
                       ).fetchone()
            # get the actual matching components
            error = reflines['error']
            func_name = reflines['func_name']
            filename = reflines['filename']
            line_num = reflines['line_num']
            # get all the ids in the db that match the components
            morelines = myDB.select(
                            'SELECT rowid from exceptions_log WHERE error=? AND'
                            ' func_name=? AND filename=? AND line_num=?',
                            [error, func_name, filename, line_num]
                        )
            errors_happened = False
            for mn in morelines:
                # remove the specific log file if present.
                log_file = 'specific_%s.log' % mn['rowid']
                try:
                    os.remove(os.path.join(mylar.CONFIG.LOG_DIR, log_file))
                except Exception as e:
                    logger.warn(
                        '[EXCEPTION-LOG-DELETION] Cannot find %s in the logs directory'
                        ' of %s. Error returned: %s'
                        % (log_file, mylar.CONFIG.LOG_DIR, e)
                    )
                try:
                    # remove the specific log entry from the dB.
                    myDB.action(
                        'DELETE FROM exceptions_log WHERE rowid=?', [mn['rowid']]
                    )
                except Exception as e:
                    errors_happened = True

            if errors_happened:
                return json.dumps({"status": "error"})
            else:
                return json.dumps({"status": "success"})

        else:
            # for specific entry
            myDB.action('DELETE from exceptions_log WHERE rowid=?', [log_id])
            log_file = 'specific_%s.log' % log_id
            try:
                os.remove(os.path.join(mylar.CONFIG.LOG_DIR, log_file))
            except Exception as e:
                logger.warn(
                    '[EXCEPTION-LOG-DELETION] Cannot find %s in the logs directory of'
                    ' %s. Error returned: %s' % (log_file, mylar.CONFIG.LOG_DIR, e)
                )
                return json.dumps({"status": "error"})
            else:
                logger.info('successfully deleted entry: %s' % log_id)
                return json.dumps({"status": "success"})
    deleteSpecificLog.exposed = True

    def manageExceptions(self, **kwargs):
        exception_list = []
        myDB = db.DBConnection()
        elist = myDB.select(
            'SELECT count(*) as count, rowid, * FROM exceptions_log group by error,'
            ' func_name, filename, line_num order by date DESC'
            )
        for et in elist:
            countline = et['count']
            if et['count'] == 1:
                countline = ''
            fileline = re.sub('.py', '', os.path.basename(et['filename'])).strip()
            exception_list.append({'id':   et['rowid'],
                                   'count': countline,
                                   'date': et['date'],
                                   'error': et['error'],
                                   'error_text': et['error_text'],
                                   'line_num': et['line_num'],
                                   'func_name': et['func_name'],
                                   'filename': fileline,
                                   'traceback': et['traceback']})
        return json.dumps(exception_list)
    manageExceptions.exposed = True

    def unblock_provider(self, site, simple=True):
        logger.info('unblocking..')
        if simple == 'false':
            simple = False
        chk = helpers.block_provider_check(site, simple, force=True)
        logger.info('chk: %s' % chk)
        if chk is False:
            if simple is True:
                return json.dumps({"status": "Successfully removed %s from provider blocklist" % site})
            else:
                return json.dumps({"status": "Successfully removed %s from provider blocklist" % site, 'remain': chk['remain']})
        else:
            if simple is True:
                return json.dumps({"status": "Could not remove %s from provider blocklist" % site})
            else:
                return json.dumps({"status": "Could not remove %s from provider blocklist" % site, 'remain': chk['remain']})

    unblock_provider.exposed = True

    def test_32p(self, username, password):
        block_32p = helpers.block_provider_check('32P')
        from . import auth32p
        tmp = auth32p.info32p(test={'username': username, 'password': password})
        rtnvalues = tmp.authenticate()
        if rtnvalues['status'] is True:
            return json.dumps({"status": "Successfully Authenticated.", "inkdrops": mylar.INKDROPS_32P, 'blocked': block_32p})
        else:
            return json.dumps({"status": "Could not Authenticate.", "inkdrops": mylar.INKDROPS_32P, 'blocked': block_32p})

    test_32p.exposed = True

    def check_ActiveDDL(self):
         myDB = db.DBConnection()
         active = myDB.selectone("SELECT * FROM DDL_INFO WHERE STATUS = 'Downloading'").fetchone()
         if active is None:
             return json.dumps({'status':   'There are no active downloads currently being attended to',
                                'percent':   0,
                                'a_series':  None,
                                'a_year':  None,
                                'a_filename':  None,
                                'a_size':  None,
                                'a_id':  None,
                                'a_issueid': None})
         else:
             filelocation = None
             if active['filename'] is not None:
                 # if this is resumed, we need to use the resume value which holds the filesize of the resume
                 filelocation = os.path.join(mylar.CONFIG.DDL_LOCATION, active['filename'])
                 #logger.fdebug('b4-checking file existance: %s' % filelocation)
                 if all(['External' in active['site'], active['link_type'] == 'DDL-Ext']):
                     filelocation = active['tmp_filename']
                 elif 'DDL' in active['site'] and any([active['link_type'] == 'GC-Mega', active['link_type'] == 'GC-Pixel']):
                     filelocation = active['tmp_filename']
                 else:
                     filelocation = os.path.join(mylar.CONFIG.DDL_LOCATION, active['filename'])
                 #logger.fdebug('after-checking file existance: %s' % filelocation)
                 if os.path.exists(filelocation) is True:
                     filesize = os.stat(filelocation).st_size
                     #logger.fdebug('filesize: %s / remote: %s' % (filesize, active['remote_filesize']))
                     remote_filesize = active['remote_filesize']
                     cmath = int(float(filesize*100)/int(int(remote_filesize)*100) * 100)
                     if filesize > int(remote_filesize) and cmath > 102:
                         logger.fdebug('size calc is incorrect ... correcting...')
                         remote_filesize = helpers.human2bytes(re.sub('/s', '', active['size'][:-1]).strip())
                         cmath = int(float(filesize*100)/int(int(remote_filesize)*100) * 100)
                     #logger.fdebug('remote_filesize: %s' % (remote_filesize))
                     #logger.fdebug('ACTIVE DDL: %s  %s%s  [%s]' % (active['filename'], cmath, '%', 'Downloading'))
                     #logger.fdebug('size: %s' % active['size'])
                     return json.dumps({'status':      'Downloading',
                                        'percent':     "%s%s" % (cmath, '%'),
                                        'a_series':    active['series'],
                                        'a_year':      active['year'],
                                        'a_filename':  active['filename'],
                                        'a_size':      active['size'],
                                        'a_id':        active['id']})
                 statline = '%s does not exist.</br> This probably needs to be restarted (use the option in the GUI)' % filelocation
             else:
                 infoline = '%s (%s)' % (active['series'], active['year'])
                 statline = 'No filename assigned for %s.</br> This was probably never started successfully - you should restart the download (use the option in the GUI)' % infoline
             return json.dumps({'a_id': active['id'], 'status': statline, 'percent': 0})

    check_ActiveDDL.exposed = True

    def create_readlist(self, list=None, weeknumber=None, year=None):
        #                                 ({
        #                                   "PUBLISHER": weekly['PUBLISHER'],
        #                                   "ISSUE": weekly['ISSUE'],
        #                                   "COMIC": weekly['COMIC'],
        #                                   "STATUS":  tmp_status,
        #                                   "COMICID": weekly['ComicID'],
        #                                   "ISSUEID": weekly['IssueID'],
        #                                   "HAVEIT":  haveit,
        #                                   "LINK":    linkit,
        #                                   "AUTOWANT": False
        #                                 })
        issuelist = []
        logger.info('weeknumber: %s' % weeknumber)
        logger.info('year: %s' % year)
        weeklyresults = []
        if weeknumber is not None:
            myDB = db.DBConnection()
            w_results = myDB.select("SELECT * from weekly WHERE weeknumber=? AND year=?", [int(weeknumber),int(year)])
            watchlibrary = helpers.listLibrary()
            issueLibrary = helpers.listIssues(weeknumber, year)
            oneofflist = helpers.listoneoffs(weeknumber, year)
            for weekly in w_results:
                xfound = False
                tmp_status = weekly['Status']
                issdate = None
                if weekly['ComicID'] in watchlibrary:
                    haveit = watchlibrary[weekly['ComicID']]

                    if all([mylar.CONFIG.AUTOWANT_UPCOMING, tmp_status == 'Skipped']):
                        tmp_status = 'Wanted'

                    for x in issueLibrary:
                        if weekly['IssueID'] == x['IssueID']:
                            xfound = True
                            tmp_status = x['Status']
                            issdate = x['IssueYear']
                            break

                else:
                    xlist = [x['Status'] for x in oneofflist if x['IssueID'] == weekly['IssueID']]
                    if xlist:
                        haveit = 'OneOff'
                        tmp_status = xlist[0]
                        issdate = None
                    else:
                        haveit = "No"

                x = None
                try:
                    x = float(weekly['ISSUE'])
                except ValueError as e:
                    if helpers.issueExceptionCheck(weekly['ISSUE'], full_match=False):
                        x = weekly['ISSUE']

                if x is not None:
                    weeklyresults.append({
                                           "PUBLISHER": weekly['PUBLISHER'],
                                           "ISSUE": weekly['ISSUE'],
                                           "COMIC": weekly['COMIC'],
                                           "STATUS":  tmp_status,
                                           "COMICID": weekly['ComicID'],
                                           "ISSUEID": weekly['IssueID'],
                                           "HAVEIT":  haveit,
                                           "ISSUEDATE": issdate
                                         })
            weeklylist = sorted(weeklyresults, key=itemgetter('PUBLISHER', 'COMIC'), reverse=False)
            for ab in weeklylist:
                if ab['HAVEIT'] == ab['COMICID']:
                    lb = myDB.selectone('SELECT ComicVersion, Type, ComicYear from comics WHERE ComicID=?', [ab['COMICID']]).fetchone()
                    issuelist.append({'IssueNumber':    ab['ISSUE'],
                                      'ComicName':      ab['COMIC'],
                                      'ComicID':        ab['COMICID'],
                                      'IssueID':        ab['ISSUEID'],
                                      'Status':         ab['STATUS'],
                                      'Publisher':      ab['PUBLISHER'],
                                      'ComicVolume':    lb['ComicVersion'],
                                      'ComicYear':      lb['ComicYear'],
                                      'ComicType':      lb['Type'],
                                      'IssueYear':      ab['ISSUEDATE']})

        from mylar import cbl
        ab = cbl.dict2xml(issuelist)
        #a = cbl.CreateList(issuelist)
        #ab = a.createComicRackReadlist()
        logger.info('returned.')
        logger.info(ab)
    create_readlist.exposed = True

    def downloadBanner(self, **kwargs):
        storyarcid = kwargs['storyarcid']
        url = kwargs['url']
        storyarcname = kwargs['storyarcname']

        logger.info('storyarcid: %s' % storyarcid)
        logger.info('url: %s' % url)
        ext = url[-4:]
        for i in ['.jpg', '.png', '.jpeg']:
            if i in url:
                ext = i
                break
        banner = os.path.join(mylar.CONFIG.CACHE_DIR, 'storyarcs', (str(storyarcid) + '-banner' + ext))

        r = requests.get(url, stream=True)

        if str(r.status_code) != '200':
            logger.warn('Unable to download image from URL: %s [Status Code returned:%s]' % (url, r.status_code))
        else:
            if r.headers.get('Content-Encoding') == 'gzip':
                import gzip
                from io import StringIO
                buf = StringIO(r.content)
                f = gzip.GzipFile(fileobj=buf)

            with open(banner, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()
            logger.info('Successfully wrote image to cache directory: %s' % banner)

        import get_image_size
        image = get_image_size.get_image_metadata(banner)
        imageinfo = json.loads(get_image_size.Image.to_str_json(image))
        logger.info('imageinfo: %s' % imageinfo)

        raise cherrypy.HTTPRedirect("detailStoryArc?StoryArcID=%s&StoryArcName=%s" % (storyarcid, storyarcname))

    downloadBanner.exposed = True

    def manageBanner(self, comicid, action, height=None, width=None):
        rootpath = os.path.join(mylar.CONFIG.CACHE_DIR, 'storyarcs')
        if action == 'delete':
            deleted = False
            ext = ['.jpg', '.png', '.jpeg']
            loc = os.path.join(rootpath, str(comicid) + '-banner')
            customs = 0
            for root, dir, file in os.walk(rootpath):
                for f in file:
                    if any(ext in f for ext in ['.jpg', '.png', '.jpeg']):
                        if comicid in f and any(['H' in f, 'W' in f]):
                            customs+=1
                            os.remove(os.path.join(root, f))
                            deleted = True

            if customs == 0:
                # delete the o.g. if no custom covers present.
                os.remove(loc)
                deleted = True

            if deleted is True:
                if customs > 0:
                    delmessage = '%s custom banner size images' % customs
                else:
                    delmessage = 'banner image'
                logger.info('Successfully deleted %s for the given storyarc.' % delmessage)
            else:
                logger.warn('Unable to located banner image in cache folder...')
        elif action == 'save':
            filename = None
            dir = os.listdir(rootpath)
            for fname in dir:
                if str(comicid) in fname:
                    ext = os.path.splitext(fname)[1]
                    filepath = os.path.join(rootpath, fname)
                    break
                    #if 'H' in fname:
                    #    bannerheight = fname[fname.find('H')+1:fname.find('.')]
                    #    logger.info('bannerheight found at : %s' % bannerheight)

            #ext = ['.jpg', '.png', '.jpeg']
            #ext = None
            #loc = os.path.join(mylar.CONFIG.CACHE_DIR, 'storyarcs', str(comicid) + '-banner')
            #for x in ['.jpg', '.png', '.jpeg']:
            #    if os.path.isfile(loc +x):
            #        ext = x
            #        break
            if filepath is not None:
                new_imagename = str(comicid) + '-bannerH' + str(height) + ext
                os.rename(filepath, os.path.join(rootpath, new_imagename))
                logger.info('successfully saved %s to new dimensions of banner : 960 x %s' % (new_imagename, height))
                myDB = db.DBConnection()
                myDB.upsert("storyarcs", {'ArcImage': new_imagename}, {'StoryArcID': comicid})
            else:
                logger.warn('unable to locate %s in cache directory in order to save' % filepath)

    manageBanner.exposed = True

    def choose_specific_download(self, **kwargs): #manual=True):
        try:
            action = kwargs['action']
        except:
            action = False

        try:
            comicvolume = kwargs['comicvolume']
        except:
            comicvolume = None

        if all([kwargs['issueid'] != 'None', kwargs['issueid'] is not None]) and action is False:
            issueid = kwargs['issueid']
            logger.info('checking for: %s' % issueid)
            results = search.searchforissue(issueid, manual=True)
        else:
            results = self.queueissue(kwargs['mode'], ComicName=kwargs['comicname'], ComicID=kwargs['comicid'], IssueID=kwargs['issueid'], ComicIssue=kwargs['issue'], ComicVersion=comicvolume, Publisher=kwargs['publisher'], pullinfo=kwargs['pullinfo'], pullweek=kwargs['pullweek'], pullyear=kwargs['pullyear'], manual=True)

        myDB = db.DBConnection()
        r = []

        for x in mylar.COMICINFO: #results:
            ctrlval = {'provider':      x['provider'],
                       'id':            x['nzbid']}
            newval = {'kind':           x['kind'],
                      'sarc':           x['SARC'],
                      'issuearcid':     x['IssueArcID'],
                      'comicname':      x['ComicName'],
                      'comicid':        x['ComicID'],
                      'issueid':        x['IssueID'],
                      'issuenumber':    x['IssueNumber'],
                      'volume':         x['ComicVolume'],
                      'oneoff':         x['oneoff'],
                      'fullprov':       x['nzbprov'],
                      'modcomicname':   x['modcomicname'],
                      'name':           x['nzbtitle'],
                      'link':           x['link'],
                      'size':           x['size'],
                      'pack_numbers':   x['pack_numbers'],
                      'pack_issuelist': x['pack_issuelist'],
                      'comicyear':      x['comyear'],
                      'issuedate':      x['IssueDate'],
                      'tmpprov':        x['tmpprov'],
                      'pack':           x['pack']}

            myDB.upsert('manualresults', newval, ctrlval)

            r.append({'kind':         x['kind'],
                      'provider':     x['provider'],
                      'nzbtitle':     x['nzbtitle'],
                      'nzbid':        x['nzbid'],
                      'size':         x['size'][:-1],
                      'tmpprov':      x['tmpprov']})

        #logger.fdebug('results returned: %s' % r)
        cherrypy.response.headers['Content-type'] = 'application/json'
        return json.dumps(r)

    choose_specific_download.exposed = True

    def download_specific_release(self, nzbid, provider, name):
        myDB = db.DBConnection()
        dsr = myDB.selectone('SELECT * FROM manualresults WHERE id=? AND tmpprov=? AND name=?', [nzbid, provider, name]).fetchone()
        if dsr is None:
            logger.warn('Unable to locate result - something is wrong. Try and manually search again?')
            return
        else:
            oneoff = bool(int(dsr['oneoff']))
            try:
                pack = bool(int(dsr['pack']))
            except:
                pack = False
            comicinfo = [{'ComicName':     dsr['comicname'],
                          'ComicVolume':   dsr['volume'],
                          'IssueNumber':   dsr['issuenumber'],
                          'comyear':       dsr['comicyear'],
                          'IssueDate':     dsr['issuedate'],
                          'pack':          pack,
                          'modcomicname':  dsr['modcomicname'],
                          'oneoff':        oneoff,
                          'SARC':          dsr['sarc'],
                          'IssueArcID':    dsr['issuearcid']}]
        #logger.info('comicinfo: %s' % comicinfo)
        newznabinfo = None
        if dsr['kind'] == 'usenet':
            link = dsr['link']
            for newznab_info in mylar.CONFIG.EXTRA_NEWZNABS:
                if dsr['provider'].lower() in newznab_info[0].lower():
                    if (newznab_info[5] == '1' or newznab_info[5] == 1):
                        if newznab_info[1].endswith('/'):
                            newznab_host = newznab_info[1]
                        else:
                            newznab_host = newznab_info[1] + '/'
                        newznab_api = newznab_info[3]
                        newznab_uid = newznab_info[4]
                        link = str(newznab_host) + 'api?apikey=' + str(newznab_api) + '&t=get&id=' + str(dsr['id'])
                        logger.info('newznab detected as : ' + str(newznab_info[0]) + ' @ ' + str(newznab_host))
                        logger.info('link : ' + str(link))
                        newznabinfo = (newznab_info[0], newznab_info[1], newznab_info[2], newznab_info[3], newznab_info[4])
                    else:
                        logger.error(str(newznab_info[0]) + ' is not enabled - unable to process retry request until provider is re-enabled.')
                    break
        else:
            link = nzbid
        if oneoff is True:
           mode = 'pullwant'
        else:
           mode = 'series'

        try:
            nzbname = search.nzbname_create(dsr['fullprov'], info=comicinfo, title=dsr['name'])
            sresults = search.searcher(dsr['fullprov'], nzbname, comicinfo, link=link, IssueID=dsr['issueid'], ComicID=dsr['comicid'], tmpprov=dsr['tmpprov'], directsend=True, newznab=newznabinfo)
            if sresults is not None:
                updater.foundsearch(dsr['ComicID'], dsr['IssueID'], mode='series', provider=dsr['tmpprov'], hash=sresults['t_hash'])
        except:
            return False #json.dumps({'result': 'failure'})
        else:
            return True #json.dumps({'result': 'success'})

    download_specific_release.exposed = True

    def read_comic(self, ish_id, page_num, size):
        from mylar.webviewer import WebViewer
        wv = WebViewer()
        page_num = int(page_num)
        #cherrypy.session['ishid'] = ish_id
        data = wv.read_comic(ish_id, page_num, size)
        #data = wv.read_comic(ish_id)
        return data
    read_comic.exposed = True

    def dbupdater_watchlist(self):
        updater.watchlist_updater()
    dbupdater_watchlist.exposed = True

    def dump_that_shizzle(self, **kwargs):
        # if any([user == 'Offspring', user == 'SCSi']):
        #     print('now leave me alone.')

        mass_auto = False
        publishers = []

        for k, v in kwargs.items():
            if 'publishers' in k:
                selectize = json.loads(v)
                try:
                    publishers = selectize['0']['selectize']['items']
                except Exception as e:
                    logger.info('unable to parse selectize: %s' % (selectize,))
                    continue
                else:
                    if type(publishers) == str:
                        # if it's only one selection, force it to a list.
                         publishers = [publishers]
            elif 'weeknumber' in k:
                weeknumber = v
            elif 'year' in k:
                year = v
            elif 'mass_auto' in k:
                if v == 'true':
                    mass_auto = True


        mylar.CONFIG.AUTO_MASS_ADD = mass_auto

        if len(publishers) == 0:
            publishers = None

        #watchlibrary = helpers.listLibrary()
        #watch = []

        #myDB = db.DBConnection()
        #pub_listing = []
        #if publishers is None:
        #    watchlist = myDB.select('SELECT * FROM weekly WHERE weeknumber=? and year=?', [weeknumber, year])
        #else:
        #    cnt = 0
        #    pblist = 'AND (publisher="%s"' % publishers[cnt]
        #    for pb in publishers:
        #        if cnt > 0:
        #            pblist += ' OR publisher="%s"' % pb

        #        pub_listing.append(pb)
        #        cnt += 1
        #    pblist += ')'
        #    mylar.CONFIG.MASS_PUBLISHERS = json.loads(json.dumps(pub_listing))
        #    mylar.CONFIG.writeconfig(values={'mass_publishers': json.dumps(mylar.CONFIG.MASS_PUBLISHERS)})
        #    query_line = 'SELECT * FROM WEEKLY WHERE weeknumber=%s AND year=%s %s' % (weeknumber, year, pblist)
        #    watchlist = myDB.select(query_line)

        #if watchlist:
        #    for wt in watchlist:
        #        if wt['comicid'] not in watchlibrary and wt['comicid'] is not None:
        #            if not any(ext['comicid'] == wt['comicid'] for ext in mylar.ADD_LIST):
        #                watch.append({'comicid': wt['comicid'], 'series': wt['comic']})

        pub_info = weeklypull.mass_publishers(publishers, weeknumber, year)

        pub_count = pub_info['publisher_count']
        if pub_count == 0:
            pub_count = 'all'
        return json.dumps({"status": "success", "publisher_count": pub_count, "series_count": pub_info['series_count']})


        #if len(watch) > 0:
        #    logger.info('[SHIZZLE-WHIZZLE] Now queueing to mass add %s new series to your watchlist' % len(watch))
        #    try:
        #        importer.importer_thread(watch)
        #    except Exception:
        #        pass

    dump_that_shizzle.exposed = True

    def get_description(self, **args):
        for k,v in list(args.items()):
            if k == 'id':
                comicid = v[1:]

        myDB = db.DBConnection()
        desc = myDB.selectone('SELECT Description, DescriptionEdit, ComicLocation FROM comics WHERE comicid=?', [comicid]).fetchone()

        description_load = None
        if os.path.exists(os.path.join(desc['ComicLocation'], 'series.json')):
            try:
                with open(os.path.join(desc['ComicLocation'], 'series.json')) as j_file:
                    metainfo = json.load(j_file)
                try:
                    # series.json version 1.0.1
                    description_load = metainfo['metadata']['description_text']
                except Exception as e:
                    try:
                        # series.json version 1.0
                        description_load = metainfo['metadata'][0]['description_text']
                    except Exception as e:
                        description_load = metainfo['metadata'][0]['description']
            except Exception as e:
                 try:
                    # series.json version 1.0.1
                    description_load = metainfo['metadata']['description_formatted']
                 except Exception as e:
                    try:
                        # series.json version 1.0
                        description_load = metainfo['metadata'][0]['description_formatted']
                    except Exception as e:
                        logger.info('No description found in metadata. Reloading from dB if available.[error: %s]' % e)
        if desc:
            if desc['DescriptionEdit']:
                return desc['DescriptionEdit']
            else:
                return desc['Description']
        elif description_load is not None:
            return description_load
        else:
            return 'No description available.'
    get_description.exposed = True

    def update_metadata_thread(self, **kwargs):
        sm = series_metadata.metadata_Series(kwargs=kwargs)
        threading.Thread(target=sm.update_metadata).start()
    update_metadata_thread.exposed = True

    def update_metadata(self, comicid, bulk=False, api=False):
        sm = series_metadata.metadata_Series(comicidlist=comicid, bulk=bulk, api=api)
        sm.update_metadata()
        return
    update_metadata.exposed = True

    def weekly_publisherlisting(self, weeknumber, year):
        comiclist = []
        myDB = db.DBConnection()
        thelist = myDB.select("SELECT Publisher FROM weekly WHERE weeknumber=? AND year=? GROUP BY Publisher ORDER BY Publisher ASC", [weeknumber, year])
        for ts in thelist:
            comiclist.append({"name": ts['publisher']})
        return json.dumps(comiclist)
    weekly_publisherlisting.exposed=True

    def get_the_pubs(self):
        x = []
        if mylar.CONFIG.MASS_PUBLISHERS:
            if type(mylar.CONFIG.MASS_PUBLISHERS) != list:
                try:
                    mylar.CONFIG.MASS_PUBLISHERS = json.loads(mylar.CONFIG.MASS_PUBLISHERS)
                except Exception:
                    pass
            for i in mylar.CONFIG.MASS_PUBLISHERS:
                x.append({'name': i})
        return json.dumps(x)
    get_the_pubs.exposed = True

    def ignore_search_word_listing(self, inputvalue=None, deletevalue=None):
        ignorelist = []
        new_list = []
        deleted = False
        for ts in mylar.CONFIG.IGNORE_SEARCH_WORDS:
            #logger.fdebug('ts:%s / inputvalue:%s' % (ts, inputvalue))
            if ts == deletevalue:
                deleted = True
            elif ts != inputvalue:
                ignorelist.append({"name": ts})
                new_list.append(ts)
                #logger.fdebug('inputvalue is to be deleted')

        if any([inputvalue, deletevalue]):
            if inputvalue:
                ignorelist.append({"name": inputvalue})
                new_list.append(inputvalue)
                mylar.CONFIG.IGNORE_SEARCH_WORDS = new_list
                return json.dumps({"name": inputvalue})
            else:
                mylar.CONFIG.IGNORE_SEARCH_WORDS = new_list
                return json.dumps({"name": deletevalue})

        mylar.CONFIG.writeconfig(values={'ignore_search_words': json.dumps(new_list)})
        mylar.CONFIG.IGNORE_SEARCH_WORDS = new_list
        return json.dumps(ignorelist)
    ignore_search_word_listing.exposed=True

    def list_the_directories(self, foldername=None, iDisplayStart=0, iDisplayLength=25, iSortCol_0='1', sSortDir_0="desc", sSearch="", **kwargs):
        if foldername is None or not os.path.exists(foldername):
             return json.dumps({'status': 'fail', 'message': '%s does not exist - please verify!' % (foldername)})

        flc = filechecker.FileChecker(foldername, justparse=True, pp_mode=True)
        fl = flc.listFiles()

        rows = fl['comiclist'] #[iDisplayStart:(iDisplayStart + iDisplayLength)]
        rows = [[row['series_name'], row['issue_number'], row['comicfilename']] for row in rows]

        return json.dumps({
            'iTotalDisplayRecords': len(rows),
            'iTotalRecords': fl['comiccount'],
            'aaData': rows,
        })

    list_the_directories.exposed = True

    def serieslisting(self, comicid=None):
        comiclist = []
        myDB = db.DBConnection()
        if comicid is not None:
            thelist = myDB.select("SELECT ComicName, ComicVersion, ComicYear, ComicID FROM comics WHERE ComicID=?", [comicid])
        else:
            thelist = myDB.select("SELECT ComicName, ComicVersion, ComicYear, ComicID FROM comics ORDER BY ComicName ASC")
        for ts in thelist:
            if any([ts['ComicVersion'] is None, ts['ComicVersion'] == 'v1']):
                cm_cv = ''
            else:
                cm_cv = ts['ComicVersion']
            comiclist.append({"name":       "%s %s (%s)" % (ts['ComicName'], cm_cv, ts['ComicYear']),
                              "comicid":    ts['ComicID']})
        logger.info('comiclist: %s' % (comiclist,))
        return json.dumps(comiclist)
    serieslisting.exposed=True

    def post_selections(self, foldername):
        return serve_template(templatename="post_processing.html", title="Interactive Post-Processing", foldername=foldername)
    post_selections.exposed = True

    def manageNotifs(self, session_id=None, modal=None, iDisplayStart=0, iDisplayLength=100, iSortCol_0=5, sSortDir_0="desc", sSearch="", **kwargs):
        #for k,v in kwargs.items():
        #    logger.info('%s:%s' % (k,v))

        if session_id is None:
            session_id = kwargs['paging_session_id']

        if any([modal is None, modal == 'undefined']):
            modal = kwargs['modal_p']

        if any([modal is None, modal == 'undefined']):
            modal = 'modal'  # default to modal.

        logger.fdebug('[modal:%s] session_id set to: %s' % (modal, session_id))
        myDB = db.DBConnection()
        notifs = myDB.select("SELECT * FROM notifs where session_id=? ORDER BY substr(date,4)||substr(date,6,2)||substr(date,9,2) DESC LIMIT 10", [session_id])
        rows = []
        for x in notifs:
            rows.append((x['date'], x['message'], x['comicid']))

        iDisplayStart = int(iDisplayStart)
        iDisplayLength = int(iDisplayLength)
        #if not rows:
        #    rows.append((None, None, None))
        return json.dumps({
            'iTotalDisplayRecords': len(rows),
            'iTotalRecords': len(rows),
            'aaData': rows,
            'modal': modal,
        })
    manageNotifs.exposed = True

    def clear_notifs(self, session_id):
        myDB = db.DBConnection()
        count_chk = myDB.selectone("SELECT COUNT() FROM notifs WHERE session_id=?", [session_id]).fetchone()[0]
        logger.info('notifs to be cleared: %s' % count_chk)
        if not count_chk:
            c_message = 'No notifications present currently for the given session to clear'
            c_status = 'success'
        else:
            c_not = myDB.action("DELETE FROM notifs WHERE session_id=?", [session_id])
            if c_not:
                c_message = 'Successfully cleared %s notifications for current session' % count_chk
                c_status = 'success'
            else:
                c_message = 'Unable to clear %s notifications for current session' % count_chk
                c_status = 'failure'
        return json.dumps({'status': c_status, 'message': c_message})
    clear_notifs.exposed = True

    def editDetails(self, comicid, location=None, booktype=None, imageloaded=False, query_id=None):
        og_booktype = None
        if booktype is not None:
            if booktype == 'null':
                booktype = None
            else:
                og_booktype = booktype

        if location is not None:
            if location == 'null':
                location = None

        if imageloaded == 'null':
            imageloaded = False

        if query_id == 'null':
            query_id = None

        myDB = db.DBConnection()
        comlocation = None
        if location is not None and comlocation != location:
            comlocation = location

        if query_id is not None:
            tmp_results = myDB.selectone("SELECT * FROM tmp_searches WHERE comicid=? AND query_id=?", [comicid, query_id]).fetchone()
            results = {'ComicName': tmp_results['comicname'],
                       'ComicVersion': tmp_results['volume'],
                       'ComicYear': tmp_results['comicyear'],
                       'ComicIssues': tmp_results['issues'],
                       'ComicPublisher': tmp_results['publisher'],
                       'ComicDescription': tmp_results['description'],
                       'PublisherImprint': tmp_results['publisherimprint'],
                       'ComicThumbURL': tmp_results['thumbimage'],
                       'ComicImage': tmp_results['comicimage'],
                       'Type': tmp_results['type']}
        else:
            results = mylar.cv.getComic(comicid, rtype='comic', series=True)

        if results:
            if imageloaded is False:
                if results['ComicThumbURL'] is not None:
                    image_url = results['ComicThumbURL']
                else:
                    image_url = results['ComicImage']
                comicImage = mylar.getimage.retrieve_image(image_url)
            else:
                comicImage = None

            if any([comlocation is None, booktype is None]):
                #this recreates the diretory structure
                if results['ComicVersion'] is not None:
                    if results['ComicVersion'].isdigit():
                        comicVol = 'v' + results['ComicVersion']
                        if all([mylar.CONFIG.SETDEFAULTVOLUME is False, comicVol == 'v1']):
                            comicVol = None
                        else:
                            if mylar.CONFIG.SETDEFAULTVOLUME is True:
                                comicVol = 'v1'
                            else:
                                comicVol = None
                    else:
                        comicVol = None
                else:
                    comicVol = None
                    if all([mylar.CONFIG.SETDEFAULTVOLUME is True, comicVol is None]):
                        comicVol = 'v1'

                if og_booktype is not None:
                    booktype = og_booktype
                else:
                    if all([int(results['ComicIssues']) == 1, results['ComicYear'] < helpers.today()[:4], results['Type'] != 'One-Shot', results['Type'] != 'TPB', results['Type'] != 'HC', results['Type'] != 'GN']):
                       booktype = 'One-Shot'
                    else:
                        booktype = results['Type']

                #if imageloaded is False:
                #    if results['ComicThumbURL'] is not None:
                #        image_url = results['ComicThumbURL']
                #    else:
                #        image_url = results['ComicImage']
                #    comicImage = mylar.getimage.retrieve_image(image_url)
                #else:
                #    comicImage = None

                comic_values = {'ComicName':        results['ComicName'],
                                'ComicPublisher':   results['ComicPublisher'],
                                'PublisherImprint': results['PublisherImprint'],
                                'ComicYear':        results['ComicYear'],
                                'ComicVersion':     results['ComicVersion'], #comicVol,
                                'Type':             booktype,
                                'Corrected_Type':   og_booktype}

                dothedew = mylar.filers.FileHandlers(comic=comic_values)
                comvalues = dothedew.folder_create()
                comlocation = comvalues['comlocation']
        else:
            comicImage = "data:image/gif;base64,%s" % mylar.getimage.load_image(os.path.join(mylar.PROG_DIR, 'data', 'images', 'blank.gif'),263)

        dir_exists = ''
        if comlocation is not None:
            if os.path.exists(comlocation):
                dir_exists = 'false'
            else:
                dir_exists = 'true'
        #logger.info('comlocation: %s' % comlocation)
        #if all([location is not None, comlocation != location]):
        #    comlocation = location
        #    logger.fdebug('location preset from editor as : %s' % (comlocation))
        logger.info('[%s] comlocation: %s' % (dir_exists,comlocation))
        return json.dumps({'status': 'success', 'image': comicImage, 'booktype': booktype, 'comicname': results['ComicName'], 'publisher': results['ComicPublisher'], 'comicyear': results['ComicYear'], 'issues': results['ComicIssues'], 'description': results['ComicDescription'], 'comlocation': comlocation, 'dir_exists': dir_exists})
    editDetails.exposed = True

    def addMissingSeriesFromArc(self, storyarcid):
        watchlibrary = helpers.listLibrary()
        watch = []
        storyarcname = None

        myDB = db.DBConnection()
        arcs = myDB.select('Select ComicID, ComicName, SeriesYear, StoryArc FROM storyarcs WHERE storyarcid=? AND (Manual IS NOT "deleted" OR Manual IS NULL) GROUP BY ComicID', [storyarcid])

        for ac in arcs:
            if storyarcname is None and ac['StoryArc'] is not None:
                storyarcname = ac['StoryArc']

            if not ac['ComicID'] in watchlibrary:
                if not {"comicid": ac['ComicID'], "comicname": ac['ComicName']} in mylar.ADD_LIST.queue:
                    watch.append({"comicid": ac['ComicID'], "comicname": ac['ComicName'], "seriesyear": ac['SeriesYear']})

        if len(watch) > 0:
            logger.info('[SHIZZLE-WHIZZLE] Now queueing to add %s series into your watchlist from the %s Arc' % (len(watch), storyarcname))
            try:
                importer.importer_thread(watch)
            except Exception:
                pass

    addMissingSeriesFromArc.exposed = True

    def return_checks(self):
        r = mylar.req_test.Req()
        r.check_config_values()

        return json.dumps(mylar.REQS)
    return_checks.exposed = True

    def fix_cv_removed(self, comicid, opts, delete_dir=False):
        if delete_dir == 1:
            delete_dir = True
        else:
            delete_dir = False
        myDB = db.DBConnection()
        cc = myDB.selectone('SELECT comicname, comicyear, comiclocation from comics where ComicID=?', [comicid]).fetchone()
        comicname = cc['comicname']
        comicyear = cc['comicyear']
        seriesdir = cc['comiclocation']

        if opts == 'delete':
            if not cc:
                logger.warn('[CV-REMOVAL-DETECTION] Unable to locate comicid in db - this series does not exist currently..')
                return json.dumps({'status': 'failure', 'message': 'Series has already been removed from the watchlist'})

            myDB.action("DELETE FROM comics WHERE ComicID=?", [comicid])
            myDB.action("DELETE FROM issues WHERE ComicID=?", [comicid])
            if mylar.CONFIG.ANNUALS_ON:
                myDB.action("DELETE FROM annuals WHERE ComicID=?", [comicid])
            myDB.action('DELETE from upcoming WHERE ComicID=?', [comicid])
            myDB.action('DELETE from readlist WHERE ComicID=?', [comicid])
            myDB.action("UPDATE weekly SET Status='Skipped' WHERE ComicID=? AND Status='Wanted'", [comicid])
            warnings = 0
            if delete_dir:
                logger.fdebug('Remove directory on series removal enabled.')
                if seriesdir is not None:
                    if os.path.exists(seriesdir):
                        logger.fdebug('Attempting to remove the directory and contents of : %s' % seriesdir)
                        try:
                            shutil.rmtree(seriesdir)
                        except:
                            logger.warn('Unable to remove directory after removing series from Mylar.')
                            warnings += 1
                        else:
                            logger.info('Successfully removed directory: %s' % (seriesdir))
                    else:
                        logger.warn('Unable to remove directory as it does not exist in : %s' % seriesdir)
                        warnings += 1
                else:
                    logger.warn('Unable to remove directory as it does not exist.')
                    warnings += 1

            helpers.ComicSort(sequence='update')

            c_image = os.path.join(mylar.CONFIG.CACHE_DIR, comicid + '.jpg')
            if os.path.exists(c_image):
                try:
                    os.remove(c_image)
                except Exception as e:
                    warnings += 1
                    logger.warn('[CV-REMOVAL-DETECTION] Unable to remove the image file from the cache (%s).'
                                ' You may have to delete the file manually' % c_image)
            else:
                logger.fdebug('image file already removed from cache for %s (%s) - [%s]' % (comicname, comicyear, comicid))

            linemsg = 'Successfully removed %s (%s) from the watchlist' % (comicname, comicyear)
            if warnings > 0:
                linemsg += '[%s warnings]' % warnings

            return json.dumps({'status': 'success', 'message': linemsg})

        else:
            myDB.upsert("comics", {'Status': 'Paused', 'cv_removed': 2}, {'ComicID': comicid})
            logger.info('[CV-REMOVAL-DETECTION] Successfully retained %s (%s) and is now in a Paused status' % (comicname, comicyear))
            linemsg = 'Successfully Paused %s (%s) due to CV removal' % (comicname, comicyear)
            return json.dumps({'status': 'success', 'message': linemsg})
    fix_cv_removed.exposed = True

    def checkCBLFile(self, cblFile, ignorearchived=False, issuesonly=False):
        try:
            cblXML = ET.parse(cblFile.file)
            cblRoot = cblXML.getroot()
        except ET.ParseError as e:
            return json.dumps({'status': 'error', 'message' : f'XML Parsing Error: {e}'})            
        
        # Formdata only sends strings ...
        ignorearchived = True if ignorearchived == 'true' else False
        issuesonly = True if issuesonly == 'true' else False

        results = []
        warnings = set()

        try:
            books = cblRoot.findall(".//Book")
            # Using this to try to reduce unnecessary repeat DB calls.  Alternatively, could pre-pull a single call from Issues and reference that.  Potato potato.
            volume_cache = {}
            newvol_count = 0
            missing_issue_count = 0

            # Debatable whether it's worth doing this validation in its own loop to avoid wasted DB calls.
            for book in books:
                databaseEntry = book.find(".//Database[@Name='cv']")
                if databaseEntry is None:
                    return json.dumps({'status': 'error', 'message' : f'CBL Processing Error: No CV identifiers for entry {books.index(book)}'})            

            myDB = db.DBConnection()

            for book in books:
                databaseEntry = book.find(".//Database[@Name='cv']")
                
                issueIndex = books.index(book)
                volumeName = book.get('Series')
                volumeYear = book.get('Volume')
                issueNumber = book.get('Number')
                cvSeriesID = databaseEntry.get('Series')
                cvIssueID = databaseEntry.get('Issue')

                if cvSeriesID in volume_cache.keys():
                    vol_exists = volume_cache[cvSeriesID]
                else:
                    comic = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [cvSeriesID]).fetchone()
                    vol_exists = False if comic is None else True
                    volume_cache[cvSeriesID] = vol_exists
                    if not vol_exists:
                        newvol_count += 1
                
                if vol_exists:
                    issue = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [cvIssueID]).fetchone()

                    # Check in case the issue is an integrated annual
                    if issue is None:
                        issue = myDB.selectone('SELECT * FROM annuals WHERE IssueID=?', [cvIssueID]).fetchone()

                    iss_exists = False if issue is None else True

                    if iss_exists:
                        iss_status = issue['Status']
                        
                        if iss_status in ['Downloaded', 'Wanted', 'Snatched', 'Failed']:
                            action_text = 'No action needed'
                        elif iss_status == 'Archived':
                            if ignorearchived :
                                action_text = 'No action needed' 
                            else:
                                action_text = "Mark issue as Wanted"
                                missing_issue_count += 1
                        else:
                            missing_issue_count += 1
                            action_text = 'Mark issue as Wanted'
                    else:
                        action_text = f'Warning: Could not find issue {cvIssueID} in volume {cvSeriesID}.'
                        missing_issue_count += 1
                        warnings.add('Volumes in Mylar do not recognise some Issue IDs.  This may be due to a list error.')
                else:
                    iss_exists = False
                    iss_status = 'Missing'
                    missing_issue_count += 1
                    action_text = 'Add volume & mark issue as Wanted'
                
                # List to return to import table display: Entry, Volume, Issue, Status, Action
                results.append([issueIndex, 
                                f'<a href="{"comicDetails?ComicID=" if vol_exists else "https://comicvine.com/volume/4050-"}{cvSeriesID}" target="{"_self" if vol_exists else "_blank"}">{volumeName} ({volumeYear})</a>',
                                issueNumber,
                                iss_status,
                                action_text])

        except Exception as e:
            return json.dumps({'status': 'error', 'message' : f'Error processing CBL file.  Unhandled Exception: {str(e)}'})
        
        if newvol_count > 200:
            warnings.add('Attempting to add more than 200 series may cause problems due to CV API limits.  Consider breaking up this list into smaller parts.')
        elif newvol_count > 100:
            warnings.add('Attempting to add a lot of new series.  Consider your CV API limits before triggering the import.')

        if len(warnings) > 0:
            warning_text = '<br >'.join(warnings)
        else:
            warning_text = ''

        return json.dumps({'status': 'success', 'warning_text' : warning_text, 'missing_volumes' : newvol_count, 'missing_issues' : missing_issue_count, 'results' : results,
                           'message' : f'''CBL File "{cblFile.filename}" read successfully <br >
                           <br >
                           Total Volumes: {len(volume_cache.keys())} <br >                           
                           Missing Volumes: {newvol_count} <br >
                           <br >
                           Total Issues: {len(results)} <br >
                           Issues Not Currently Wanted: {missing_issue_count} <br >'''})
    
    checkCBLFile.exposed = True

    # Assume this has been validated by check function
    def processCBLFile(self, cblFile, ignorearchived=False, issuesonly=False):
        # Track the volumes as they're added or queued
        volume_index = {}
        counters = {'volumes_added' : 0, 'issues_watched' : 0, 'issues_to_be_watched' : 0, 'issues_skipped' : 0}

        # Formdata only sends strings ...
        ignorearchived = True if ignorearchived == 'true' else False
        issuesonly = True if issuesonly == 'true' else False

        logger.info(f'Processing CBL File {cblFile.filename} to set up volumes and wanted issues')
        warning_text = ''
        warnings = set()

        try:
            cblXML = ET.parse(cblFile.file)
            cblRoot = cblXML.getroot()
        except ET.ParseError as e:
            return json.dumps({'status': 'error', 'message' : f'XML Parsing Error: {e}', 'warning_text' : warning_text})
            
        try:
            books = cblRoot.findall(".//Book")
            
            myDB = db.DBConnection()
            
            # Process the CBL File and build a dictionary of Wanted Issue IDs keyed on the ComicID
            for book in books:
                databaseEntry = book.find(".//Database[@Name='cv']")
                if databaseEntry is None:
                    return json.dumps({'status': 'error', 'message' : f'CBL Processing Error: No CV identifiers for entry {books.index(book)}', 'warning_text' : warning_text})            
                
                volumeName = book.get('Series')
                volumeYear = book.get('Volume')
                issueNumber = book.get('Number')
                cvSeriesID = databaseEntry.get('Series')
                cvIssueID = databaseEntry.get('Issue')

                checkIssue = False
                if cvSeriesID in volume_index.keys():
                    # If we've seen this volume before, and already marked it for adding
                    if volume_index[cvSeriesID]['NewVol']:
                        logger.fdebug(f'CBL File: Volume "{volumeName} ({volumeYear})" to be added, Issue #{issueNumber} to be marked as Wanted')
                        counters['issues_to_be_watched'] += 1
                        # If Auto Want is on and not suppressed, we can avoid queueing this for addition
                        if (issuesonly and mylar.CONFIG.AUTOWANT_ALL) or not mylar.CONFIG.AUTOWANT_ALL:
                            volume_index[cvSeriesID]['IssueIDs'].append(cvIssueID)
                    else:
                        checkIssue = True
                else:
                    volume = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [cvSeriesID]).fetchone()
                    if volume is None:
                        logger.fdebug(f'CBL File: Volume "{volumeName} ({volumeYear})" does not exist exist.  Adding Volume, and Issue #{issueNumber} to be marked as Wanted')
                        
                        issueList = []
                        # If Auto Want is on and not suppressed, we can avoid queueing this for addition
                        if (issuesonly and mylar.CONFIG.AUTOWANT_ALL) or not mylar.CONFIG.AUTOWANT_ALL:
                            issueList.append(cvIssueID)
                        
                        volume_index[cvSeriesID] = {'NewVol' : True, 'VolumeName' : volumeName, 'VolumeYear' : volumeYear, 'IssueIDs' : issueList}
                        counters['volumes_added'] += 1
                        counters['issues_to_be_watched'] += 1
                    else:
                        volume_index[cvSeriesID] = {'NewVol' : False, 'VolumeName' : volumeName, 'VolumeYear' : volumeYear, 'IssueIDs' : []}
                        checkIssue = True
                    
                if checkIssue:
                    issue = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [cvIssueID]).fetchone()

                    # Check in case the issue is an integrated annual
                    if issue is None:
                        issue = myDB.selectone('SELECT * FROM annuals WHERE IssueID=?', [cvIssueID]).fetchone()

                    if issue is None:
                        logger.warning(f'CBL File: Volume "{volumeName} ({volumeYear})" exists but could not find Issue #{issueNumber} with ID {cvIssueID}')
                        warnings.add(f'Some issues of existing volumes could not be found.  Check logs for details.')
                    else:
                        wantissue = False
                        if issue['Status'] in ['Downloaded', 'Wanted', 'Snatched', 'Failed']:
                            logger.fdebug(f'CBL File: Volume "{volumeName} ({volumeYear})" exists, Issue #{issueNumber} already Wanted')
                            counters['issues_skipped'] += 1
                        elif issue['Status'] == 'Archived':
                            if ignorearchived :
                                logger.fdebug(f'CBL File: Volume "{volumeName} ({volumeYear})" exists, Issue #{issueNumber} Archived.  Ignoring')
                                counters['issues_skipped'] += 1
                            else:
                                wantissue = True
                        else:
                            wantissue = True
                        
                        if wantissue:
                            logger.fdebug(f'CBL File: Volume "{volumeName} ({volumeYear})" already exists, Issue #{issueNumber} to be marked as Wanted')
                            counters['issues_watched'] += 1
                            volume_index[cvSeriesID]['IssueIDs'].append(cvIssueID)

            # No more holding back, let's get this stuff queued!
            logger.fdebug(f"Finished analysing CBL File, adding volumes and issues to MASS-ADD queues")
            for comicId,data in volume_index.items():
                if data['NewVol']:
                    comic_request = [{"comicid": comicId, "comicname": data['VolumeName'], "seriesyear": data['VolumeYear'], 'suppress_addall' : (issuesonly and mylar.CONFIG.AUTOWANT_ALL)}]
                    importer.importer_thread(comic_request)

                if len(data['IssueIDs']) > 0:
                    importer.issue_watcher_thread(data['IssueIDs'])


            # Give the MASS-ADD thread a little nudge in case it's not been started as we added no volumes
            importer.importer_thread([])

        except Exception as e:
            logger.fdebug(f"Unhandled exception when processing CBL Reading List {cblFile.filename}:\n {traceback.format_exc()}")
            return json.dumps({'status' : 'error', 'message' : f"Unhandled exception when processing CBL Reading List {cblFile.filename}: {str(e)}", 'warning_text' : warning_text})

        logger.fdebug(f"Saving CBL import settings: CBL_IMPORT_ISSUESONLY={issuesonly}, CBL_IMPORT_IGNORE_ARCHIVED={ignorearchived}")
        mylar.CONFIG.CBL_IMPORT_ISSUESONLY = issuesonly
        mylar.CONFIG.CBL_IMPORT_IGNOREARCHIVED = ignorearchived
        mylar.CONFIG.writeconfig(values={'CBL_IMPORT_ISSUESONLY': mylar.CONFIG.CBL_IMPORT_ISSUESONLY, 'CBL_IMPORT_IGNOREARCHIVED': mylar.CONFIG.CBL_IMPORT_IGNOREARCHIVED})

        warning_text = '<br >'.join(warnings)
        return json.dumps({'status': 'success', 'message' : f'''CBL File "{cblFile.filename}" fully imported <br >
                           <br >
                           Issues Already Watched: {counters['issues_skipped']} <br > 
                           Existing Volume Issues to Watch: {counters['issues_watched']} <br >
                           New Volumes Queued to Add: {counters['volumes_added']} <br >
                           New Volume Issues to Watch: {counters['issues_to_be_watched']} <br > ''', 
                           'warning_text' : warning_text})

    processCBLFile.exposed = True