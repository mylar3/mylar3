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
import mylar
from mylar import helpers, db, logger

class FileHandlers(object):

    def __init__(self, comic=None, issue=None, ComicID=None, IssueID=None):

        self.myDB = db.DBConnection()
        if ComicID is not None:
            self.comicid = ComicID
            self.comic = self.myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
        elif comic is not None:
            self.comic = comic
            self.comicid = None
        else:
            self.comic = None
            self.comicid = None

        if IssueID is not None:
            self.issueid = IssueID
            self.issue = self.myDB.select('SELECT * FROM issues WHERE IssueID=?', [IssueID])
        elif issue is not None:
            self.issue = issue
            self.issueid = None
        else:
            self.issue = None
            self.issueid = None

    def folder_create(self, booktype=None, update_loc=None, secondary=None):
        # dictionary needs to passed called comic with
        #  {'ComicPublisher', 'CorrectedType, 'Type', 'ComicYear', 'ComicName', 'ComicVersion'}
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

        if mylar.OS_DETECT == 'Windows':
            if '/' in folder_format:
                folder_format = re.sub('/', '\\', folder_format).strip()
        else:
            if '\\' in folder_format:
                folder_format = folder_format.replace('\\', '/').strip()

        u_comicnm = self.comic['ComicName']
        # let's remove the non-standard characters here that will break filenaming / searching.
        comicname_filesafe = helpers.filesafe(u_comicnm)
        comicdir = comicname_filesafe

        series = comicdir
        if series[-1:] == '.':
            series[:-1]

        publisher = re.sub('!', '', self.comic['ComicPublisher']) # thanks Boom!
        publisher = helpers.filesafe(publisher)

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

        if any([self.comic['ComicVersion'] is None, booktype != 'Print']):
            comicVol = 'None'
        else:
            comicVol = self.comic['ComicVersion']

        #if comversion is None, remove it so it doesn't populate with 'None'
        if comicVol == 'None':
            chunk_f_f = re.sub('\$VolumeN', '', chunk_folder_format)
            chunk_f = re.compile(r'\s+')
            chunk_folder_format = chunk_f.sub(' ', chunk_f_f)

        chunk_folder_format = re.sub("[()|[]]", '', chunk_folder_format).strip()
        ccf = chunk_folder_format.find('/ ')
        if ccf != -1:
            chunk_folder_format = chunk_folder_format[:ccf+1] + chunk_folder_format[ccf+2:]
        ccf = chunk_folder_format.find('\ ')
        if ccf != -1:
            chunk_folder_format = chunk_folder_format[:ccf+1] + chunk_folder_format[ccf+2:]

        #do work to generate folder path
        values = {'$Series':        series,
                  '$Publisher':     publisher,
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
            logger.fdebug('bb_tuple: %s' % bb_tuple)
            if mylar.OS_DETECT == 'Windows':
                p_path = pathlib.PureWindowsPath(pathlib.PurePath(bb2).joinpath(bb_tuple))
            else:
                p_path = pathlib.PurePosixPath(pathlib.PurePath(bb2).joinpath(bb_tuple))

            logger.fdebug('p_path: %s' % p_path)

            first = helpers.replace_all(chunk_folder_format, values)
            logger.fdebug('first-1: %s' % first)

            if mylar.CONFIG.REPLACE_SPACES:
                first = first.replace(' ', mylar.CONFIG.REPLACE_CHAR)
            logger.fdebug('first-2: %s' % first)
            comlocation = str(p_path.joinpath(first))
            com_parentdir = str(p_path.joinpath(first).parent)
            logger.fdebug('comlocation: %s' % comlocation)

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
                        chkissue = self.myDB.selectone("SELECT * from storyarcs WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issuedigits(issue)]).fetchone()
                    else:
                        chkissue = self.myDB.selectone("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issuedigits(issue)]).fetchone()
                        if all([chkissue is None, annualize == 'yes', mylar.CONFIG.ANNUALS_ON]):
                            chkissue = self.myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issuedigits(issue)]).fetchone()

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
                    storyarcd = os.path.join(mylar.CONFIG.DESTINATION_DIR, "StoryArcs", arcdir)
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

            if type(issuenum) == str:
               vals = {'\xbd':'.5','\xbc':'.25','\xbe':'.75','\u221e':'9999999999','\xe2':'9999999999'}
            else:
               vals = {'\xbd':'.5','\xbc':'.25','\xbe':'.75','\\u221e':'9999999999','\xe2':'9999999999'}
            x = [vals[key] for key in vals if key in issuenum]
            if x:
                issuenum = x[0]
                logger.fdebug('issue number formatted: %s' % issuenum)

            #comicid = issueinfo['ComicID']
            #issueno = str(issuenum).split('.')[0]
            issue_except = 'None'
            valid_spaces = ('.', '-')
            for issexcept in mylar.ISSUE_EXCEPTIONS:
                if issexcept.lower() in issuenum.lower():
                    logger.fdebug('ALPHANUMERIC EXCEPTION : [' + issexcept + ']')
                    v_chk = [v for v in valid_spaces if v in issuenum]
                    if v_chk:
                        iss_space = v_chk[0]
                        logger.fdebug('character space denoted as : ' + iss_space)
                    else:
                        logger.fdebug('character space not denoted.')
                        iss_space = ''
#                    if issexcept == 'INH':
#                       issue_except = '.INH'
                    if issexcept == 'NOW':
                       if '!' in issuenum: issuenum = re.sub('\!', '', issuenum)
#                       issue_except = '.NOW'

                    issue_except = iss_space + issexcept
                    logger.fdebug('issue_except denoted as : ' + issue_except)
                    issuenum = re.sub("[^0-9]", "", issuenum)
                    break

#            if 'au' in issuenum.lower() and issuenum[:1].isdigit():
#                issue_except = ' AU'
#            elif 'ai' in issuenum.lower() and issuenum[:1].isdigit():
#                issuenum = re.sub("[^0-9]", "", issuenum)
#                issue_except = ' AI'
#            elif 'inh' in issuenum.lower() and issuenum[:1].isdigit():
#                issuenum = re.sub("[^0-9]", "", issuenum)
#                issue_except = '.INH'
#            elif 'now' in issuenum.lower() and issuenum[:1].isdigit():
#                if '!' in issuenum: issuenum = re.sub('\!', '', issuenum)
#                issuenum = re.sub("[^0-9]", "", issuenum)
#                issue_except = '.NOW'
            if '.' in issuenum:
                iss_find = issuenum.find('.')
                iss_b4dec = issuenum[:iss_find]
                if iss_find == 0:
                    iss_b4dec = '0'
                iss_decval = issuenum[iss_find +1:]
                if iss_decval.endswith('.'):
                    iss_decval = iss_decval[:-1]
                if int(iss_decval) == 0:
                    iss = iss_b4dec
                    issdec = int(iss_decval)
                    issueno = iss
                else:
                    if len(iss_decval) == 1:
                        iss = iss_b4dec + "." + iss_decval
                        issdec = int(iss_decval) * 10
                    else:
                        iss = iss_b4dec + "." + iss_decval.rstrip('0')
                        issdec = int(iss_decval.rstrip('0')) * 10
                    issueno = iss_b4dec
            else:
                iss = issuenum
                issueno = iss
            # issue zero-suppression here
            if mylar.CONFIG.ZERO_LEVEL is False:
                zeroadd = ""
            else:
                if any([mylar.CONFIG.ZERO_LEVEL_N  == "none", mylar.CONFIG.ZERO_LEVEL_N is None]): zeroadd = ""
                elif mylar.CONFIG.ZERO_LEVEL_N == "0x": zeroadd = "0"
                elif mylar.CONFIG.ZERO_LEVEL_N == "00x": zeroadd = "00"

            logger.fdebug('Zero Suppression set to : ' + str(mylar.CONFIG.ZERO_LEVEL_N))
            prettycomiss = None

            if issueno.isalpha():
                logger.fdebug('issue detected as an alpha.')
                prettycomiss = str(issueno)
            else:
                try:
                    x = float(issuenum)
                    #validity check
                    if x < 0:
                        logger.info('I\'ve encountered a negative issue #: %s. Trying to accomodate.' % issueno)
                        prettycomiss = '-' + str(zeroadd) + str(issueno[1:])
                    elif x == 9999999999:
                        logger.fdebug('Infinity issue found.')
                        issuenum = 'infinity'
                    elif x >= 0:
                        pass
                    else:
                        raise ValueError
                except ValueError as e:
                    logger.warn('Unable to properly determine issue number [ %s] - you should probably log this on github for help.' % issueno)
                    return

            if all([prettycomiss is None, len(str(issueno)) > 0]):
                #if int(issueno) < 0:
                #    self._log("issue detected is a negative")
                #    prettycomiss = '-' + str(zeroadd) + str(abs(issueno))
                if int(issueno) < 10:
                    logger.fdebug('issue detected less than 10')
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                            prettycomiss = str(zeroadd) + str(iss)
                        else:
                            prettycomiss = str(zeroadd) + str(int(issueno))
                    else:
                        prettycomiss = str(zeroadd) + str(iss)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('Zero level supplement set to ' + str(mylar.CONFIG.ZERO_LEVEL_N) + '. Issue will be set as : ' + str(prettycomiss))
                elif int(issueno) >= 10 and int(issueno) < 100:
                    logger.fdebug('issue detected greater than 10, but less than 100')
                    if any([mylar.CONFIG.ZERO_LEVEL_N == "none", mylar.CONFIG.ZERO_LEVEL_N is None, mylar.CONFIG.ZERO_LEVEL is False]):
                        zeroadd = ""
                    else:
                        zeroadd = "0"
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                            prettycomiss = str(zeroadd) + str(iss)
                        else:
                           prettycomiss = str(zeroadd) + str(int(issueno))
                    else:
                        prettycomiss = str(zeroadd) + str(iss)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('Zero level supplement set to ' + str(mylar.CONFIG.ZERO_LEVEL_N) + '.Issue will be set as : ' + str(prettycomiss))
                else:
                    logger.fdebug('issue detected greater than 100')
                    if issuenum == 'infinity':
                        prettycomiss = 'infinity'
                    else:
                        if '.' in iss:
                            if int(iss_decval) > 0:
                                issueno = str(iss)
                        prettycomiss = str(issueno)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('Zero level supplement set to ' + str(mylar.CONFIG.ZERO_LEVEL_N) + '. Issue will be set as : ' + str(prettycomiss))
            elif len(str(issueno)) == 0:
                prettycomiss = str(issueno)
                logger.fdebug('issue length error - cannot determine length. Defaulting to None:  ' + str(prettycomiss))

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
