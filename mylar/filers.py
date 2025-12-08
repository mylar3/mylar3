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

import re
import os
import pathlib
import json
import shutil
import calendar
import datetime
import time
import mylar
from mylar import helpers, db, logger, filechecker

class FileHandlers(object):

    def __init__(self, comic=None, issue=None, ComicID=None, IssueID=None, arcID=None):

        self.myDB = db.DBConnection()
        self.weekly = None
        if ComicID is not None:
            self.comicid = ComicID
            self.comic = self.myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
            if not self.comic:
                self.weekly = self.myDB.selectone('SELECT * FROM weekly WHERE ComicID=? AND IssueID=?', [ComicID, IssueID]).fetchone()
                if not self.weekly:
                    self.comic = None
        elif comic is not None:
            self.comic = comic
            self.comicid = None
        else:
            self.comic = None
            self.comicid = None

        if IssueID is not None:
            self.issueid = IssueID
            self.issue = self.myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
            if not self.issue:
                if mylar.CONFIG.ANNUALS_ON:
                    self.issue = self.myDB.selectone('SELECT * FROM annuals WHERE IssueID=?', [IssueID]).fetchone()
                if not self.issue:
                    self.issue = None
        elif issue is not None:
            self.issue = issue
            self.issueid = None
        else:
            self.issue = None
            self.issueid = None

        if arcID is not None:
            self.arcid = arcID
            self.arc = self.myDB.selectone('SELECT * FROM storyarcs WHERE IssueArcID=?', [arcID]).fetchone()
        else:
            self.arc = None
            self.arcid = None

    def folder_create(self, booktype=None, update_loc=None, secondary=None, imprint=None):
        # dictionary needs to passed called comic with
        #  {'ComicPublisher', 'Corrected_Type, 'Type', 'ComicYear', 'ComicName', 'ComicVersion'}
        # or pass in comicid value from __init__

        # setup default location here
        if update_loc is not None:
            comic_location = update_loc['temppath']
            enforce_format = update_loc['tempff']
            folder_format = update_loc['tempformat']
            comicid = update_loc['comicid']
        else:
            comic_location = mylar.CONFIG.DESTINATION_DIR
            enforce_format = False
            folder_format = mylar.CONFIG.FOLDER_FORMAT

        if folder_format is None:
            folder_format = '$Series ($Year)'

        publisher = re.sub('!', '', self.comic['ComicPublisher']) # thanks Boom!
        publisher = helpers.filesafe(publisher)

        if mylar.OS_DETECT == 'Windows':
            if '/' in folder_format:
                folder_format = re.sub('/', '\\', folder_format).strip()
        else:
            if '\\' in folder_format:
                folder_format = folder_format.replace('\\', '/').strip()

        if publisher is not None:
            if publisher.endswith('.'):
                publisher = publisher[:-1]

        u_comicnm = self.comic['ComicName']
        # let's remove the non-standard characters here that will break filenaming / searching.
        comicname_filesafe = helpers.filesafe(u_comicnm)
        comicdir = comicname_filesafe

        series = comicdir
        if any([series.endswith('.'), series.endswith('..'), series.endswith('...'), series.endswith('....')]):
            if series.endswith('....'):
                series = series[:-4]
            elif series.endswith('...'):
                series = series[:-3]
            elif series.endswith('..'):
                series = series[:-2]
            elif series.endswith('.'):
                series = series[:-1]

        if booktype is not None:
            if self.comic['Corrected_Type'] is not None:
                if self.comic['Corrected_Type'] != booktype:
                    booktype = booktype
                else:
                    booktype = self.comic['Corrected_Type']
            else:
                booktype = booktype
        else:
            booktype = self.comic['Type']

        if any([booktype is None, booktype == 'None', booktype == 'Print']) or all([booktype != 'Print', mylar.CONFIG.FORMAT_BOOKTYPE is False]):
            chunk_fb = re.sub('\$Type', '', folder_format)
            chunk_b = re.compile(r'\s+')
            chunk_folder_format = chunk_b.sub(' ', chunk_fb)
            if booktype != 'Print':
                booktype = 'None'
        else:
            chunk_folder_format = folder_format

        if self.comic['ComicVersion'] is None:
            comicVol = 'None'
        else:
            if booktype != 'Print':
                comicVol = self.comic['ComicVersion']
            else:
                comicVol = self.comic['ComicVersion']
            if comicVol is None:
                comicVol = 'None'

        #if comversion is None, remove it so it doesn't populate with 'None'
        if comicVol == 'None':
            chunk_f_f = re.sub('\$VolumeN', '', chunk_folder_format)
            chunk_f = re.compile(r'\s+')
            chunk_folder_format = chunk_f.sub(' ', chunk_f_f)

        if any([imprint is None, imprint == 'None']):
            imprint = self.comic['PublisherImprint']
        if any([imprint is None, imprint == 'None']):
            chunk_f_f = re.sub('\$Imprint', '', chunk_folder_format)
            chunk_f = re.compile(r'\s+')
            chunk_folder_format = chunk_f.sub(' ', chunk_f_f)

        chunk_folder_format = re.sub(r'\(\)|\[\]', '', chunk_folder_format).strip()
        ccf = chunk_folder_format.find('/ ')
        if ccf != -1:
            chunk_folder_format = chunk_folder_format[:ccf+1] + chunk_folder_format[ccf+2:]
        ccf = chunk_folder_format.find('\ ')
        if ccf != -1:
            chunk_folder_format = chunk_folder_format[:ccf+1] + chunk_folder_format[ccf+2:]
        ccf = chunk_folder_format.find(' /')
        if ccf != -1:
            chunk_folder_format = chunk_folder_format[:ccf] + chunk_folder_format[ccf+1:]
        ccf = chunk_folder_format.find(' \\')
        if ccf != -1:
            chunk_folder_format = chunk_folder_format[:ccf] + chunk_folder_format[ccf+1:]

        chunk_folder_format = re.sub(r'\s+', ' ', chunk_folder_format)

        # if the path contains // in linux it will incorrectly parse things out.
        #logger.fdebug('newPath: %s' % re.sub('//', '/', chunk_folder_format).strip())

        #do work to generate folder path
        values = {'$Series':        series,
                  '$Publisher':     publisher,
                  '$Imprint':       imprint,
                  '$Year':          self.comic['ComicYear'],
                  '$series':        series.lower(),
                  '$publisher':     publisher.lower(),
                  '$VolumeY':       'V' + self.comic['ComicYear'],
                  '$VolumeN':       comicVol.upper(),
                  '$Type':          booktype
                  }

        if update_loc is not None:
            #set the paths here with the seperator removed allowing for cross-platform altering.
            ccdir = pathlib.PurePath(comic_location)
            ddir = pathlib.PurePath(mylar.CONFIG.DESTINATION_DIR)
            dlc = pathlib.PurePath(self.comic['ComicLocation'])
            path_convert = True
            i = 0
            bb = []
            while i < len(dlc.parts):
                try:
                    if dlc.parts[i] == ddir.parts[i]:
                        i+=1
                        continue
                    else:
                        bb.append(dlc.parts[i])
                        i+=1 #print('d.parts: %s' % ccdir.parts[i])
                except IndexError:
                    bb.append(dlc.parts[i])
                    i+=1
            bb_tuple = pathlib.PurePath(os.path.sep.join(bb))
            try:
                com_base = pathlib.PurePath(dlc).relative_to(ddir)
            except ValueError as e:
                #if the original path is not located in the same path as the ComicLocation (destination_dir).
                #this can happen when manually altered to a new path, or thru various changes to the ComicLocation path over time.
                #ie. ValueError: '/mnt/Comics/Death of Wolverine The Logan Legacy-(2014)' does not start with '/mnt/mediavg/Comics/Comics-2'
                dir_fix = []
                dir_parts = pathlib.PurePath(dlc).parts
                for dp in dir_parts:
                    try:
                        if self.comic['ComicYear'] is not None:
                            if self.comic['ComicYear'] in dp:
                                break
                        if self.comic['ComicName'] is not None:
                            if self.comic['ComicName'] in dp:
                                break
                        if self.comic['ComicPublisher'] is not None:
                            if self.comic['ComicPublisher'] in dp:
                                break
                        if self.comic['PublisherImprint'] is not None:
                            if self.comic['PublisherImprint'] in dp:
                                break
                        if self.comic['ComicVersion'] is not None:
                            if self.comic['ComicVersion'] in dp:
                                break
                        dir_fix.append(dp)
                    except:
                        pass

                if len(dir_fix) > 0:
                    spath = ''
                    t=0
                    while (t < len(dir_parts)):
                        newpath = os.path.join(spath, dir_parts[t])
                        t+=1
                    com_base = newpath
                    #path_convert = False
            #print('com_base: %s' % com_base)
            #detect comiclocation path based on OS so that the path seperators are correct
            #have to figure out how to determine OS of original location...
            if mylar.OS_DETECT == 'Windows':
                p_path = pathlib.PureWindowsPath(ccdir)
            else:
                p_path = pathlib.PurePosixPath(ccdir)
            if enforce_format is True:
                first = helpers.replace_all(chunk_folder_format, values)
                if mylar.CONFIG.REPLACE_SPACES:
                    #mylar.CONFIG.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                    first = first.replace(' ', mylar.CONFIG.REPLACE_CHAR)
                comlocation = str(p_path.joinpath(first))
            else:
                comlocation = str(p_path.joinpath(com_base))

            return {'comlocation':  comlocation,
                    'path_convert': path_convert,
                    'comicid':      comicid}
        else:
            if secondary is not None:
                ppath = secondary
            else:
                ppath = mylar.CONFIG.DESTINATION_DIR

            ddir = pathlib.PurePath(ppath)
            i = 0
            bb = []
            while i < len(ddir.parts):
                try:
                    bb.append(ddir.parts[i])
                    i+=1
                except IndexError:
                    break

            bb2 = bb[0]
            bb.pop(0)
            bb_tuple = pathlib.PurePath(os.path.sep.join(bb))
            #logger.fdebug('bb_tuple: %s' % bb_tuple)
            if mylar.OS_DETECT == 'Windows':
                p_path = pathlib.PureWindowsPath(pathlib.PurePath(bb2).joinpath(bb_tuple))
            else:
                p_path = pathlib.PurePosixPath(pathlib.PurePath(bb2).joinpath(bb_tuple))

            #logger.fdebug('p_path: %s' % p_path)

            first = helpers.replace_all(chunk_folder_format, values)
            #logger.fdebug('first-1: %s' % first)

            if mylar.CONFIG.REPLACE_SPACES:
                first = first.replace(' ', mylar.CONFIG.REPLACE_CHAR)
            #logger.fdebug('first-2: %s' % first)
            comlocation = str(p_path.joinpath(first))
            com_parentdir = str(p_path.joinpath(first).parent)
            #logger.fdebug('comlocation: %s' % comlocation)

            #try:
            #    if folder_format == '':
            #        #comlocation = pathlib.PurePath(comiclocation).joinpath(comicdir, '(%s)') % comic['SeriesYear']
            #        comlocation = os.path.join(comic_location, comicdir, " (" + comic['SeriesYear'] + ")")
            #    else:
            #except TypeError as e:
            #    if comic_location is None:
            #        logger.error('[ERROR] %s' % e)
            #        logger.error('No Comic Location specified. This NEEDS to be set before anything can be added successfully.')
            #        return
            #    else:
            #        logger.error('[ERROR] %s' % e)
            #        return
            #except Exception as e:
            #    logger.error('[ERROR] %s' % e)
            #    logger.error('Cannot determine Comic Location path properly. Check your Comic Location and Folder Format for any errors.')
            #    return

            if comlocation == "":
                logger.error('There is no Comic Location Path specified - please specify one in Config/Web Interface.')
                return

            return {'comlocation': comlocation,
                    'subpath':     bb_tuple,
                    'com_parentdir': com_parentdir}

    def series_folder_collision_detection(self, comlocation, comicid, booktype, comicyear, volume):
        myDB = db.DBConnection()
        chk = myDB.select(f"SELECT * FROM comics WHERE ComicLocation LIKE '%{comlocation}%' AND ComicID !=?", [comicid])

        tryit = None
        if chk:
            for ck in chk:
                comloc = ck['ComicLocation']
                if comloc == comlocation:
                    logger.info('[SERIES_FOLDER_COLLISION_DETECTION] %s already exists for %s (%s).' % (ck['ComicLocation'], ck['ComicName'], ck['ComicYear']))
                    tmp_ff_head, tmp_ff = os.path.split(re.sub(r'[\/\\]$', '', mylar.CONFIG.FOLDER_FORMAT))
                    if ck['ComicYear'] != comicyear:
                        volumeyear = True
                    else:
                        volumeyear = False
                    if '$Type' not in tmp_ff and booktype != ck['Type']:
                        logger.fdebug('[SERIES_FOLDER_COLLISION_DETECTION] Trying to rename using BookType declaration.')
                        new_format = os.path.join(tmp_ff_head, '%s [%s]' % (tmp_ff, '$Type'))
                    elif '$Volume' not in tmp_ff:
                        logger.fdebug('[SERIES_FOLDER_COLLISION_DETECTION] Trying to rename using Volume declaration.')
                        volume_choice = '$VolumeY'
                        #use volume instead of ck['ComicVersion'] since volume has already had changes applied in other module
                        if volumeyear is False:
                            if volume is None:
                                volume_choice = '$VolumeY'
                            else:
                                volume_choice = '$VolumeN'
                        t_name = tmp_ff.find('$Series')
                        if t_name != -1:
                            new_format = os.path.join(tmp_ff_head, '%s %s %s' % (tmp_ff[:t_name+len('$Series'):], volume_choice, tmp_ff[t_name+len('$Series')+1:]))
                    else:
                        logger.fdebug('[SERIES_FOLDER_COLLISION_DETECTION] Defaulting to Series (Year).')
                        new_format = os.path.join(tmp_ff_head, '$Series ($Year)')

                    self.comic = {'ComicPublisher': ck['ComicPublisher'],
                                  'PublisherImprint': ck['PublisherImprint'],
                                  'Corrected_Type': ck['Corrected_Type'],
                                  'Type': booktype,
                                  'ComicYear': comicyear,
                                  'ComicName': ck['ComicName'],
                                  'ComicLocation': ck['ComicLocation'],
                                  'ComicVersion': volume}

                    update_loc = {'temppath': mylar.CONFIG.DESTINATION_DIR,
                                  'tempff': True,
                                  'tempformat': new_format,
                                  'comicid': ck['ComicID']}
                    tryit = self.folder_create(update_loc=update_loc)
                    break

        logger.fdebug('tryit_response: %s' % (tryit,))
        return tryit

    def rename_file(self, ofilename, issue=None, annualize=None, arc=False, file_format=None): #comicname, issue, comicyear=None, issueid=None)
            comicid = self.comicid   # it's coming in unicoded...
            issueid = self.issueid

            if file_format is None:
                file_format = mylar.CONFIG.FILE_FORMAT

            logger.fdebug(type(comicid))
            logger.fdebug(type(issueid))
            logger.fdebug('comicid: %s' % comicid)
            logger.fdebug('issue# as per cv: %s' % issue)
            logger.fdebug('issueid:' + str(issueid))

            if issueid is None:
                logger.fdebug('annualize is ' + str(annualize))
                if arc:
                    #this has to be adjusted to be able to include story arc issues that span multiple arcs
                    chkissue = self.myDB.selectone("SELECT * from storyarcs WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()
                else:
                    chkissue = self.myDB.selectone("SELECT * from issues WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()
                    if all([chkissue is None, annualize is None, not mylar.CONFIG.ANNUALS_ON]):
                        chkissue = self.myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()

                if chkissue is None:
                    #rechk chkissue against int value of issue #
                    if arc:
                        chkissue = self.myDB.selectone("SELECT * from storyarcs WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issue_number_parser(issue).asInt]).fetchone()
                    else:
                        chkissue = self.myDB.selectone("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issue_number_parser(issue).asInt]).fetchone()
                        if all([chkissue is None, annualize == 'yes', mylar.CONFIG.ANNUALS_ON]):
                            chkissue = self.myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issue_number_parser(issue).asInt]).fetchone()

                    if chkissue is None:
                        logger.error('Invalid Issue_Number - please validate.')
                        return
                    else:
                        logger.info('Int Issue_number compare found. continuing...')
                        issueid = chkissue['IssueID']
                else:
                    issueid = chkissue['IssueID']

            #use issueid to get publisher, series, year, issue number
            logger.fdebug('issueid is now : ' + str(issueid))
            if arc:
                issueinfo = self.myDB.selectone("SELECT * from storyarcs WHERE ComicID=? AND IssueID=? AND StoryArc=?", [comicid, issueid, arc]).fetchone()
            else:
                issueinfo = self.myDB.selectone("SELECT * from issues WHERE ComicID=? AND IssueID=?", [comicid, issueid]).fetchone()
                if issueinfo is None:
                    logger.fdebug('not an issue, checking against annuals')
                    issueinfo = self.myDB.selectone("SELECT * from annuals WHERE ComicID=? AND IssueID=?", [comicid, issueid]).fetchone()
                    if issueinfo is None:
                        logger.fdebug('Unable to rename - cannot locate issue id within db')
                        return
                    else:
                        annualize = True

            if issueinfo is None:
                logger.fdebug('Unable to rename - cannot locate issue id within db')
                return

            #remap the variables to a common factor.
            if arc:
                issuenum = issueinfo['IssueNumber']
                issuedate = issueinfo['IssueDate']
                publisher = issueinfo['IssuePublisher']
                series = issueinfo['ComicName']
                seriesfilename = series   #Alternate FileNaming is not available with story arcs.
                seriesyear = issueinfo['SeriesYear']
                arcdir = helpers.filesafe(issueinfo['StoryArc'])
                if mylar.CONFIG.REPLACE_SPACES:
                    arcdir = arcdir.replace(' ', mylar.CONFIG.REPLACE_CHAR)
                if mylar.CONFIG.STORYARCDIR:
                    if mylar.CONFIG.STORYARC_LOCATION is None:
                        storyarcd = os.path.join(mylar.CONFIG.DESTINATION_DIR, "StoryArcs", arcdir)
                    else:
                        storyarcd = os.path.join(mylar.CONFIG.STORYARC_LOCATION, arcdir)
                    logger.fdebug('Story Arc Directory set to : ' + storyarcd)
                else:
                    logger.fdebug('Story Arc Directory set to : ' + mylar.CONFIG.GRABBAG_DIR)
                    storyarcd = os.path.join(mylar.CONFIG.DESTINATION_DIR, mylar.CONFIG.GRABBAG_DIR)

                comlocation = storyarcd
                comversion = None   #need to populate this.

            else:
                issuenum = issueinfo['Issue_Number']
                issuedate = issueinfo['IssueDate']
                publisher = self.comic['ComicPublisher']
                series = self.comic['ComicName']
                if self.comic['AlternateFileName'] is None or self.comic['AlternateFileName'] == 'None':
                    seriesfilename = series
                else:
                    seriesfilename = self.comic['AlternateFileName']
                    logger.fdebug('Alternate File Naming has been enabled for this series. Will rename series title to : ' + seriesfilename)
                seriesyear = self.comic['ComicYear']
                comlocation = self.comic['ComicLocation']
                comversion = self.comic['ComicVersion']

            unicodeissue = issuenum

            _, prettycomiss, _ = helpers.issue_number_parser(issuenum, issue_id = issueid)
            
            logger.fdebug('Pretty Comic Issue is : ' + str(prettycomiss))
            if mylar.CONFIG.UNICODE_ISSUENUMBER:
                logger.fdebug('Setting this to Unicode format as requested: %s' % prettycomiss)
                prettycomiss = unicodeissue

            issueyear = issuedate[:4]
            month = issuedate[5:7].replace('-', '').strip()
            month_name = helpers.fullmonth(month)
            if month_name is None:
                month_name = 'None'
            logger.fdebug('Issue Year : ' + str(issueyear))
            logger.fdebug('Publisher: ' + publisher)
            logger.fdebug('Series: ' + series)
            logger.fdebug('Year: '  + str(seriesyear))
            logger.fdebug('Comic Location: ' + comlocation)

            if self.comic['Corrected_Type'] is not None:
                if self.comic['Type'] != self.comic['Corrected_Type']:
                    booktype = self.comic['Corrected_Type']
                else:
                    booktype = self.comic['Type']
            else:
                booktype = self.comic['Type']

            if booktype == 'Print' or all([booktype != 'Print', mylar.CONFIG.FORMAT_BOOKTYPE is False]):
                chunk_fb = re.sub('\$Type', '', file_format)
                chunk_b = re.compile(r'\s+')
                chunk_file_format = chunk_b.sub(' ', chunk_fb)
            else:
                chunk_file_format = file_format

            if any([comversion is None, booktype != 'Print']):
                comversion = 'None'

            #if comversion is None, remove it so it doesn't populate with 'None'
            if comversion == 'None':
                chunk_f_f = re.sub('\$VolumeN', '', chunk_file_format)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug('No version # found for series, removing from filename')
                logger.fdebug("new format: " + str(chunk_file_format))

            if annualize is None:
                chunk_f_f = re.sub('\$Annual', '', chunk_file_format)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug('not an annual - removing from filename paramaters')
                logger.fdebug('new format: ' + str(chunk_file_format))

            else:
                logger.fdebug('chunk_file_format is: ' + str(chunk_file_format))
                if mylar.CONFIG.ANNUALS_ON:
                    if 'annual' in series.lower():
                        if '$Annual' not in chunk_file_format: # and 'annual' not in ofilename.lower():
                        #if it's an annual, but $annual isn't specified in file_format, we need to
                        #force it in there, by default in the format of $Annual $Issue
                            #prettycomiss = "Annual " + str(prettycomiss)
                            logger.fdebug('[%s][ANNUALS-ON][ANNUAL IN SERIES][NO ANNUAL FORMAT] prettycomiss: %s' % (series, prettycomiss))
                        else:
                            #because it exists within title, strip it then use formatting tag for placement of wording.
                            chunk_f_f = re.sub('\$Annual', '', chunk_file_format)
                            chunk_f = re.compile(r'\s+')
                            chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                            logger.fdebug('[%s][ANNUALS-ON][ANNUAL IN SERIES][ANNUAL FORMAT] prettycomiss: %s' % (series, prettycomiss))
                    else:
                        if '$Annual' not in chunk_file_format: # and 'annual' not in ofilename.lower():
                        #if it's an annual, but $annual isn't specified in file_format, we need to
                        #force it in there, by default in the format of $Annual $Issue
                            prettycomiss = "Annual %s" % prettycomiss
                            logger.fdebug('[%s][ANNUALS-ON][ANNUAL NOT IN SERIES][NO ANNUAL FORMAT] prettycomiss: %s' % (series, prettycomiss))
                        else:
                            logger.fdebug('[%s][ANNUALS-ON][ANNUAL NOT IN SERIES][ANNUAL FORMAT] prettycomiss: %s' % (series, prettycomiss))

                else:
                    #if annuals aren't enabled, then annuals are being tracked as independent series.
                    #annualize will be true since it's an annual in the seriesname.
                    if 'annual' in series.lower():
                        if '$Annual' not in chunk_file_format: # and 'annual' not in ofilename.lower():
                        #if it's an annual, but $annual isn't specified in file_format, we need to
                        #force it in there, by default in the format of $Annual $Issue
                            #prettycomiss = "Annual " + str(prettycomiss)
                            logger.fdebug('[%s][ANNUALS-OFF][ANNUAL IN SERIES][NO ANNUAL FORMAT] prettycomiss: %s' % (series, prettycomiss))
                        else:
                            #because it exists within title, strip it then use formatting tag for placement of wording.
                            chunk_f_f = re.sub('\$Annual', '', chunk_file_format)
                            chunk_f = re.compile(r'\s+')
                            chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                            logger.fdebug('[%s][ANNUALS-OFF][ANNUAL IN SERIES][ANNUAL FORMAT] prettycomiss: %s' % (series, prettycomiss))
                    else:
                        if '$Annual' not in chunk_file_format: # and 'annual' not in ofilename.lower():
                            #if it's an annual, but $annual isn't specified in file_format, we need to
                            #force it in there, by default in the format of $Annual $Issue
                            prettycomiss = "Annual %s" % prettycomiss
                            logger.fdebug('[%s][ANNUALS-OFF][ANNUAL NOT IN SERIES][NO ANNUAL FORMAT] prettycomiss: %s' % (series, prettycomiss))
                        else:
                            logger.fdebug('[%s][ANNUALS-OFF][ANNUAL NOT IN SERIES][ANNUAL FORMAT] prettycomiss: %s' % (series, prettycomiss))


                    logger.fdebug('Annual detected within series title of ' + series + '. Not auto-correcting issue #')

            seriesfilename = seriesfilename #.encode('ascii', 'ignore').strip()
            filebad = [':', ',', '/', '?', '!', '\'', '\"', '\*'] #in u_comicname or '/' in u_comicname or ',' in u_comicname or '?' in u_comicname:
            for dbd in filebad:
                if dbd in seriesfilename:
                    if any([dbd == '/', dbd == '*']): 
                        repthechar = '-'
                    else:
                        repthechar = ''
                    seriesfilename = seriesfilename.replace(dbd, repthechar)
                    logger.fdebug('Altering series name due to filenaming restrictions: ' + seriesfilename)

            publisher = re.sub('!', '', publisher)

            file_values = {'$Series':    seriesfilename,
                           '$Issue':     prettycomiss,
                           '$Year':      issueyear,
                           '$series':    series.lower(),
                           '$Publisher': publisher,
                           '$publisher': publisher.lower(),
                           '$VolumeY':   'V' + str(seriesyear),
                           '$VolumeN':   comversion,
                           '$monthname': month_name,
                           '$month':     month,
                           '$Annual':    'Annual',
                           '$Type':      booktype
                          }

            extensions = ('.cbr', '.cbz', '.cb7')

            if ofilename.lower().endswith(extensions):
                path, ext = os.path.splitext(ofilename)

            if file_format == '':
                logger.fdebug('Rename Files is not enabled - keeping original filename.')
                #check if extension is in nzb_name - will screw up otherwise
                if ofilename.lower().endswith(extensions):
                    nfilename = ofilename[:-4]
                else:
                    nfilename = ofilename
            else:
                chunk_file_format = re.sub('[()|[]]', '', chunk_file_format).strip()
                nfilename = helpers.replace_all(chunk_file_format, file_values)
                if mylar.CONFIG.REPLACE_SPACES:
                    #mylar.CONFIG.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                    nfilename = nfilename.replace(' ', mylar.CONFIG.REPLACE_CHAR)

            nfilename = re.sub('[\,\:]', '', nfilename) + ext.lower()
            logger.fdebug('New Filename: ' + nfilename)

            if mylar.CONFIG.LOWERCASE_FILENAMES:
                nfilename = nfilename.lower()
                dst = os.path.join(comlocation, nfilename)
            else:
                dst = os.path.join(comlocation, nfilename)

            logger.fdebug('Source: ' + ofilename)
            logger.fdebug('Destination: ' + dst)

            rename_this = {"destination_dir": dst,
                           "nfilename": nfilename,
                           "issueid": issueid,
                           "comicid": comicid}

            return rename_this

    def secondary_folders(self, comiclocation, secondary=None):
        if not secondary:
            secondary = mylar.CONFIG.MULTIPLE_DEST_DIRS

        secondary_main = self.folder_create(secondary=secondary)
        secondaryfolders = secondary_main['comlocation']

        if not os.path.exists(secondaryfolders):
            tmpbase = os.path.basename(comiclocation)
            tmpath = os.path.join(secondary_main['com_parentdir'], tmpbase)

            if os.path.exists(tmpath):
                secondaryfolders = tmpath

        return secondaryfolders

    def walk_the_walk(self):
        folder_location = mylar.CONFIG.FOLDER_CACHE_LOCATION
        if folder_location is None:
            return {'status': False}

        logger.info('checking locally...')
        filelist = None

        logger.info('check_folder_cache: %s' % (mylar.CHECK_FOLDER_CACHE))
        if mylar.CHECK_FOLDER_CACHE is not None:
            rd = mylar.CHECK_FOLDER_CACHE #datetime.datetime.utcfromtimestamp(mylar.CHECK_FOLDER_CACHE)
            rd_mins = rd + datetime.timedelta(seconds = 600)  #10 minute cache retention
            rd_now = datetime.datetime.utcfromtimestamp(time.time())
            if calendar.timegm(rd_mins.utctimetuple()) > calendar.timegm(rd_now.utctimetuple()):
                # if < 10 minutes since last check, use cached listing
                logger.info('using cached folder listing since < 10 minutes since last file check.')
                filelist = mylar.FOLDER_CACHE

        if filelist is None:
            logger.info('generating new directory listing for folder_cache')
            flc = filechecker.FileChecker(folder_location, justparse=True, pp_mode=True)
            mylar.FOLDER_CACHE = flc.listFiles()
            mylar.CHECK_FOLDER_CACHE = datetime.datetime.utcfromtimestamp(helpers.utctimestamp())

        local_status = False
        filepath = None
        filename = None
        for fl in mylar.FOLDER_CACHE['comiclist']:
            logger.info('fl: %s' % (fl,))
            if self.arc is not None:
                comicname = self.arc['ComicName']
                corrected_type = None
                alternatesearch = None
                booktype = self.arc['Type']
                publisher = self.arc['Publisher']
                issuenumber = self.arc['IssueNumber']
                issuedate = self.arc['IssueDate']
                issuename = self.arc['IssueName']
                issuestatus = self.arc['Status']
            elif self.comic is not None:
                comicname = self.comic['ComicName']
                booktype = self.comic['Type']
                corrected_type = self.comic['Corrected_Type']
                alternatesearch = self.comic['AlternateSearch']
                publisher = self.comic['ComicPublisher']
                issuenumber = self.issue['Issue_Number']
                issuedate = self.issue['IssueDate']
                issuename = self.issue['IssueName']
                issuestatus = self.issue['Status']
            else:
                # weekly - (one/off)
                comicname = self.weekly['COMIC']
                booktype = self.weekly['format']
                corrected_type = None
                alternatesearch = None
                publisher = self.weekly['PUBLISHER']
                issuenumber = self.weekly['ISSUE']
                issuedate = self.weekly['SHIPDATE']
                issuename = None
                issuestatus = self.weekly['STATUS']

            if booktype is not None:
                if (all([booktype != 'Print', booktype != 'Digital', booktype != 'None', booktype is not None]) and corrected_type != 'Print') or any([corrected_type == 'TPB', corrected_type == 'GN', corrected_type == 'HC']):
                    if booktype == 'One-Shot' and corrected_type is None:
                        booktype = 'One-Shot'
                    else:
                        if booktype == 'GN' and corrected_type is None:
                            booktype = 'GN'
                        elif booktype == 'HC' and corrected_type is None:
                            booktype = 'HC'
                        else:
                            booktype = 'TPB'

            wm = filechecker.FileChecker(watchcomic=comicname, Publisher=publisher, AlternateSearch=alternatesearch)
            watchmatch = wm.matchIT(fl)

            logger.info('watchmatch: %s' % (watchmatch,))

            # this is all for a really general type of match - if passed, the post-processing checks will do the real brunt work
            if watchmatch['process_status'] == 'fail':
                continue

            if watchmatch['justthedigits'] is not None:
                temploc= watchmatch['justthedigits'].replace('_', ' ')
                if "Director's Cut" not in temploc:
                    temploc = re.sub('[\#\']', '', temploc)
            else:
                if any([booktype == 'TPB', booktype =='GN', booktype == 'HC', booktype == 'One-Shot']):
                    temploc = '1'
                else:
                    temploc = None
                    continue

            int_iss = helpers.issue_number_parser(issuenumber).asInt
            issyear = issuedate[:4]
            old_status = issuestatus
            issname = issuename


            if temploc is not None:
                fcdigit = helpers.issue_number_parser(temploc).asInt
            elif any([booktype == 'TPB', booktype == 'GN', booktype == 'GC', booktype == 'One-Shot']) and temploc is None:
                fcdigit = helpers.issue_number_parser('1').asInt

            if int(fcdigit) == int_iss:
                logger.fdebug('[%s] Issue match - #%s' % (self.issueid, self.issue['Issue_Number']))
                local_status = True
                if watchmatch['sub'] is None:
                    filepath = watchmatch['comiclocation']
                    filename = watchmatch['comicfilename']
                else:
                    filepath = os.path.join(watchmatch['comiclocation'], watchmatch['sub'])
                    filename = watchmatch['comicfilename']
                break


        #if local_status is True:
            #try:
            #    copied_folder = os.path.join(mylar.CONFIG.CACHE_DIR, 'tmp_filer')
            #    if os.path.exists(copied_folder):
            #        shutil.rmtree(copied_folder)
            #    os.mkdir(copied_folder)
            #    logger.info('created temp directory: %s' % copied_folder)
            #    shutil.copy(os.path.join(filepath, filename), copied_folder)

            #except Exception as e:
            #    logger.error('[%s] error: %s' % (e, filepath))
            #    filepath = None
            #    local_status = False
            #else:
            #filepath = os.path.join(copied_folder, filename)
            #logger.info('Successfully copied file : %s' % filepath)

        return {'status': local_status,
                'filename': filename,
                'filepath': filepath}
