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
import re
import sys
import glob
import shutil
import operator
import urllib.request, urllib.parse, urllib.error
import logging
import unicodedata
import optparse
import getpass
import platform
from fnmatch import fnmatch

import datetime as dt

import subprocess
from subprocess import CalledProcessError, check_output

import mylar
from mylar import logger, helpers


if 'windows' not in platform.system().lower():
    #since these aren't available in windows, we import them now...
    from pwd import getpwnam
    from grp import getgrnam

class FileChecker(object):

    def __init__(self, dir=None, watchcomic=None, Publisher=None, AlternateSearch=None, manual=None, sarc=None, justparse=None, file=None, pp_mode=False):
        #dir = full path to the series Comic Location (manual pp will just be psssing the already parsed filename)
        if dir:
            self.dir = dir
        else:
            self.dir = None

        if watchcomic:
            #watchcomic = unicode name of series that is being searched against
            self.og_watchcomic = watchcomic
            self.watchcomic = re.sub('\?', '', watchcomic).strip()  #strip the ? seperate since it affects the regex.
            #replace variations of unicode dashes with a normal - because this world is f'd up enough to have something like that.
            self.watchcomic = re.sub(r'[\u2014|\u2013|\u2e3a|\u2e3b]', ' - ', self.watchcomic).strip()
            self.watchcomic = re.sub(r'\u2019', " ' ", self.watchcomic).strip()  #replace the \u2019 with a normal ' because again, people are dumb.
            if type(self.watchcomic) != str:
                self.watchcomic = unicodedata.normalize('NFKD', self.watchcomic).encode('ASCII', 'ignore')
        else:
            self.watchcomic = None

        if Publisher:
            #publisher = publisher of watchcomic
            self.publisher = Publisher
        else:
            self.publisher = None

        #alternatesearch = list of alternate search names
        if AlternateSearch:
            self.AlternateSearch = AlternateSearch
        else:
            self.AlternateSearch = None

        #manual = true / false if it's a manual post-processing run
        if manual:
            self.manual = manual
        else:
            self.manual = None

        #sarc = true / false if it's being run against an existing story-arc
        if sarc:
            self.sarc = sarc
        else:
            self.sarc = None

        #justparse = true/false when manually post-processing, will quickly parse the filename to find
        #the series name in order to query the sql instead of cycling through each series in the watchlist.
        if justparse:
            self.justparse = True
        else:
            self.justparse = False

        #file = parse just one filename (used primarily during import/scan)
        if file:
            self.file = file
            self.justparse = True
        else:
            self.file = None

        if pp_mode:
            self.pp_mode = True
        else:
            self.pp_mode = False

        self.failed_files = []
        self.dynamic_handlers = ['/','-',':',';','\'','"',',','&','?','!','+','*','(',')','\\u2014','\\u2013','\\u2019']
        self.dynamic_replacements = ['and','the']
        self.rippers = ['-empire','-empire-hd','minutemen-','-dcp','Glorith-HD']

        #pre-generate the AS_Alternates now
        AS_Alternates = self.altcheck()
        self.AS_Alt = AS_Alternates['AS_Alt']
        self.AS_Tuple = AS_Alternates['AS_Tuple']

    def listFiles(self):
        comiclist = []
        watchmatch = {}
        dirlist = []
        comiccnt = 0
        if self.file:
            runresults = self.parseit(self.dir, self.file)
            return {'parse_status':        runresults['parse_status'],
                    'sub':                 runresults['sub'],
                    'comicfilename':       runresults['comicfilename'],
                    'comiclocation':       runresults['comiclocation'],
                    'series_name':         runresults['series_name'],
                    'series_name_decoded': runresults['series_name_decoded'],
                    'issueid':             runresults['issueid'],
                    'dynamic_name':        runresults['dynamic_name'],
                    'series_volume':       runresults['series_volume'],
                    'alt_series':          runresults['alt_series'],
                    'alt_issue':           runresults['alt_issue'],
                    'issue_year':          runresults['issue_year'],
                    'issue_number':        runresults['issue_number'],
                    'scangroup':           runresults['scangroup'],
                    'reading_order':       runresults['reading_order'],
                    'booktype':            runresults['booktype']
                    }
        else:
            filelist = self.traverse_directories(self.dir)
            for files in filelist:
                filedir = files['directory']
                filename = files['filename']
                filesize = files['comicsize']
                if filename.startswith('.'):
                    if self.watchcomic is None:
                        continue
                    elif self.watchcomic.startswith('.'):
                        pass
                    else:
                        continue

                logger.debug('[FILENAME]: %s' % filename)
                runresults = self.parseit(self.dir, filename, filedir)
                if runresults:
                    try:
                        if runresults['parse_status']:
                            run_status = runresults['parse_status']
                    except:
                        if runresults['process_status']:
                            run_status = runresults['process_status']

                    if any([run_status == 'success', run_status == 'match', run_status == 'alt_match']):
                        if self.justparse:
                            comiclist.append({
                                    'sub':                 runresults['sub'],
                                    'comicfilename':       runresults['comicfilename'],
                                    'comiclocation':       runresults['comiclocation'],
                                    'series_name':         runresults['series_name'], #helpers.conversion(runresults['series_name']),
                                    'series_name_decoded': runresults['series_name_decoded'],
                                    'issueid':             runresults['issueid'],
                                    'alt_series':          runresults['alt_series'], #helpers.conversion(runresults['alt_series']),
                                    'alt_issue':           runresults['alt_issue'],
                                    'dynamic_name':        runresults['dynamic_name'],
                                    'series_volume':       runresults['series_volume'],
                                    'issue_year':          runresults['issue_year'],
                                    'issue_number':        runresults['issue_number'],
                                    'scangroup':           runresults['scangroup'],
                                    'reading_order':       runresults['reading_order'],
                                    'booktype':            runresults['booktype']
                                    })
                        else:
                            comiclist.append({
                                     'sub':                     runresults['sub'],
                                     'ComicFilename':           runresults['comicfilename'],
                                     'ComicLocation':           runresults['comiclocation'],
                                     'ComicSize':               files['comicsize'],
                                     'ComicName':               runresults['series_name'], #helpers.conversion(runresults['series_name']),
                                     'SeriesVolume':            runresults['series_volume'],
                                     'IssueYear':               runresults['issue_year'],
                                     'JusttheDigits':           runresults['justthedigits'],
                                     'AnnualComicID':           runresults['annual_comicid'],
                                     'issueid':                 runresults['issueid'],
                                     'scangroup':               runresults['scangroup'],
                                     'booktype':                runresults['booktype']
                                     })
                        comiccnt +=1
                    else:
                        #failure
                        self.failed_files.append({'parse_status':   'failure',
                                                  'sub':            runresults['sub'],
                                                  'comicfilename':  runresults['comicfilename'],
                                                  'comiclocation':  runresults['comiclocation'],
                                                  'series_name':    runresults['series_name'], #helpers.conversion(runresults['series_name']),
                                                  'series_volume':  runresults['series_volume'],
                                                  'alt_series':     runresults['alt_series'], #helpers.conversion(runresults['alt_series']),
                                                  'alt_issue':      runresults['alt_issue'],
                                                  'issue_year':     runresults['issue_year'],
                                                  'issue_number':   runresults['issue_number'],
                                                  'issueid':        runresults['issueid'],
                                                  'scangroup':      runresults['scangroup'],
                                                  'booktype':       runresults['booktype']
                                                  })

        watchmatch['comiccount'] = comiccnt
        if len(comiclist) > 0:
            watchmatch['comiclist'] = comiclist
        else:
            watchmatch['comiclist'] = []

        if len(self.failed_files) > 0:
            logger.info('FAILED FILES: %s' % self.failed_files)

        return watchmatch

    def parseit(self, path, filename, subpath=None):

        path_list = None
        if subpath is None:
            subpath = path
            tmppath = None
            path_list = None
        else:
            logger.fdebug('[CORRECTION] Sub-directory found. Altering path configuration.')
            #basepath the sub if it exists to get the parent folder.
            logger.fdebug('[SUB-PATH] Checking Folder Name for more information.')
            #sub = re.sub(origpath, '', path).strip()})
            logger.fdebug('[SUB-PATH] Original Path : %s' % path)
            logger.fdebug('[SUB-PATH] Sub-directory : %s' % subpath)
            #subpath = helpers.conversion(subpath)
            if 'windows' in mylar.OS_DETECT.lower():
                if path in subpath:
                    ab = len(path)
                    tmppath = subpath[ab:]
            else:
                tmppath = subpath.replace(path, '').strip()

            path_list = os.path.normpath(tmppath)
            if '/' == path_list[0] or '\\' == path_list[0]:
                #need to remove any leading slashes so the os join can properly join the components
                path_list = path_list[1:]
            logger.fdebug('[SUB-PATH] subpath set to : %s' % path_list)


        #parse out the extension for type
        comic_ext = ('.cbr','.cbz','.cb7','.pdf')
        comic_ext = tuple(x for x in comic_ext if x not in mylar.CONFIG.IGNORE_SEARCH_WORDS)
        if os.path.splitext(filename)[1].endswith(comic_ext):
            filetype = os.path.splitext(filename)[1]
        else:
            filetype = 'unknown'

        #find the issue number first.
        #split the file and then get all the relevant numbers that could possibly be an issue number.
        #remove the extension.
        modfilename = re.sub(filetype, '', filename).strip()
        reading_order = None

        #if it's a story-arc, make sure to remove any leading reading order #'s
        if self.sarc and mylar.CONFIG.READ2FILENAME:
            removest = modfilename.find('-') # the - gets removed above so we test for the first blank space...
            if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                logger.fdebug('[SARC] Checking filename for Reading Order sequence - Reading Sequence Order found #: %s' % modfilename[:removest])
            if modfilename[:removest].isdigit() and removest <= 3:
                reading_order = {'reading_sequence': str(modfilename[:removest]),
                                 'filename':         filename[removest+1:]}
                modfilename = modfilename[removest+1:]
                if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                    logger.fdebug('[SARC] Removed Reading Order sequence from subname. Now set to : %s' % modfilename)

        #make sure all the brackets are properly spaced apart
        if modfilename.find('\s') == -1:
            #if no spaces exist, assume decimals being used as spacers (ie. nzb name)
            modspacer = '.'
        else:
            modspacer = ' '
        m = re.findall('[^()]+', modfilename)
        cnt = 1
        #2019-12-24----fixed to accomodate naming convention like Amazing Mary Jane (2019) 002.cbr, and to account for brackets properly
        try:
            while cnt < len(m):
                #logger.fdebug('[m=%s] modfilename.find: %s' % (m[cnt], modfilename[modfilename.find('('+m[cnt]+')')+len(m[cnt])+2]))
                #logger.fdebug('mod_1: %s' % modfilename.find('('+m[cnt]+')'))
                if modfilename[modfilename.find('('+m[cnt]+')')-1] != modspacer and modfilename.find('('+m[cnt]+')') != -1:
                    #logger.fdebug('before_space: %s' % modfilename[modfilename.find('('+m[cnt]+')')-1])
                    #logger.fdebug('after_space: %s' % modfilename[modfilename.find('('+m[cnt]+')')+len(m[cnt])+2])
                    modfilename = '%s%s%s' % (modfilename[:modfilename.find('('+m[cnt]+')')], modspacer, modfilename[modfilename.find('('+m[cnt]+')'):])
                cnt+=1
        except Exception as e:
            #logger.warn('[ERROR] %s' % e)
            pass
        #---end 2019-12-24

        #grab the scanner tags here.
        scangroup = None
        rippers = [x for x in self.rippers if x.lower() in modfilename.lower()]
        if rippers:
            #it's always possible that this could grab something else since tags aren't unique. Try and figure it out.
            if len(rippers) > 0:
                m = re.findall('[^()]+', modfilename)
                #--2019-11-30  needed for Glorith naming conventions when it's an nzb name with all formatting removed.
                if len(m) == 1:
                    spf30 = re.compile(r"[^.]+", re.UNICODE)
                    #logger.fdebug('spf30: %s' % spf30)
                    split_file30 = spf30.findall(modfilename)
                    #logger.fdebug('split_file30: %s' % split_file30)
                    if len(split_file30) > 3 and 'Glorith-HD' in modfilename:
                        scangroup = 'Glorith-HD'
                        sp_pos = 0
                        for x in split_file30:
                            if sp_pos+1 > len(split_file30):
                                break
                            if x[-1] == ',' and self.checkthedate(split_file30[sp_pos+1]):
                                modfilename = re.sub(x, x[:-1], modfilename, count=1)
                                break
                            sp_pos+=1
                #-- end 2019-11-30
                cnt = 1
                for rp in rippers:
                    while cnt < len(m):
                        if m[cnt] == ' ':
                            pass
                        elif rp.lower() in m[cnt].lower():
                            scangroup = re.sub('[\(\)]', '', m[cnt]).strip()
                            logger.fdebug('Scanner group tag discovered: %s' % scangroup)
                            modfilename = modfilename.replace(m[cnt],'').strip()
                            break
                        cnt +=1

                modfilename = modfilename.replace('()','').strip()

        issueid = None
        x = modfilename.find('[__')
        if x != -1:
            y = modfilename.find('__]', x)
            if y != -1:
                issueid = modfilename[x+3:y]
                logger.fdebug('issueid: %s' % issueid)
                modfilename = '%s %s'.strip() % (modfilename[:x], modfilename[y+3:])
                logger.fdebug('issueid %s removed successfully: %s' % (issueid, modfilename))

        #here we take a snapshot of the current modfilename, the intent is that we will remove characters that match
        #as we discover them - namely volume, issue #, years, etc
        #the remaining strings should be the series title and/or issue title if present (has to be detected properly)
        modseries = modfilename

        #try and remove /remember unicode character strings here (multiline ones get seperated/removed in below regex)
        pat = re.compile('[\x00-\x7f]{3,}', re.UNICODE)
        replack = pat.sub('XCV', modfilename)
        wrds = replack.split('XCV')
        tmpfilename = modfilename
        if len(wrds) > 1:
            for i in list(wrds):
                if i != '':
                    tmpfilename = tmpfilename.replace(i, 'XCV')

        tmpfilename = ''.join(tmpfilename)
        modfilename = tmpfilename

        sf3 = re.compile(r"[^,\s_]+", re.UNICODE)
        split_file3 = sf3.findall(modfilename)
        #--2019-11-30
        if len(split_file3) == 1 or all([len(split_file3) == 2, scangroup == 'Glorith-HD']):
        #--end 2019-11-30
            logger.fdebug('Improperly formatted filename - there is no seperation using appropriate characters between wording.')
            sf3 = re.compile(r"[^,\s_\.]+", re.UNICODE)
            split_file3 = sf3.findall(modfilename)
            logger.fdebug('NEW split_file3: %s' % split_file3)

        ret_sf2 = ' '.join(split_file3)

        sf = re.findall('''\( [^\)]* \) |\[ [^\]]* \] |\[ [^\#]* \]|\S+''', ret_sf2, re.VERBOSE)
        #sf = re.findall('''\( [^\)]* \) |\[ [^\]]* \] |\S+''', ret_sf2, re.VERBOSE)

        ret_sf1 = ' '.join(sf)

        #here we should account for some characters that get stripped out due to the regex's
        #namely, unique characters - known so far: +, &, @
        #c11 = '\+'
        #f11 = '\&'
        #g11 = '\''
        ret_sf1 = re.sub('\+', 'c11', ret_sf1).strip()
        ret_sf1 = re.sub('\&', 'f11', ret_sf1).strip()
        ret_sf1 = re.sub('\'', 'g11', ret_sf1).strip()
        ret_sf1 = re.sub('\@', 'h11', ret_sf1).strip()

        #split_file = re.findall('(?imu)\([\w\s-]+\)|[-+]?\d*\.\d+|\d+[\s]COVERS+|\d{4}-\d{2}-\d{2}|\d+[(th|nd|rd|st)]+|[\(^\)+]|\d+|[\w-]+|#?\d\.\d+|#[\.-]\w+|#[\d*\.\d+|\w+\d+]+|#(?<![\w\d])XCV(?![\w\d])+|#[\w+]|\)', ret_sf1, re.UNICODE)

        #updated to keep words within square brackets together.
        split_file = re.findall('(?imu)\([\w\s-]+\)|[-+]?\d*\.\d+|\d+[\s]COVERS+|\d+[(\s|\-)]PAGE+|\d{4}-\d{2}-\d{2}|\d+[(th|nd|rd|st)]+|[\(^\)+]|\[.*?\]|\d+|[\w-]+|#?\d\.\d+|#[\.-]\w+|#[\d*\.\d+|\w+\d+]+|#(?<![\w\d])XCV(?![\w\d])+|#[\w+]|\)', ret_sf1, re.UNICODE)

        #10-20-2018 ---START -- attempt to detect '01 (of 7.3)'
        #10-20-2018          -- attempt to detect '36p ctc' as one element
        #4-7-2020 -- remove '####px' as it's useless and will muck up the parser.
        spf = []
        mini = False
        wrdcnt = 0
        for x in split_file:
            if x == 'of':
                if split_file[wrdcnt-1].isdigit():
                    mini = True
                    wrdcnt+=1
                    spf.append(x)
                    continue
            if mini is True:
                mini = False
                try:
                    logger.fdebug('checking now: %s' % x)
                    if x.lower() == 'infinity':
                        raise Exception
                    if x.isdigit():
                        logger.fdebug('[MINI-SERIES] MAX ISSUES IN SERIES: %s' % x)
                        spf.append('(of %s)' % x)
                    elif float(x) > 0:
                        logger.fdebug('[MINI-DECIMAL SERIES] MAX ISSUES IN SERIES: %s' % x)
                        spf.append('(of %s)' % x)
                except Exception as e:
                    spf.append(x)

            elif x  == ')' or x == '(':
                pass
            elif x == 'p' or x == 'ctc' or x == 'px':
                try:
                    if spf[wrdcnt-1].isdigit():
                        logger.debug('THIS SHOULD BE : %s%s' % (spf[wrdcnt-1], x))
                        newline = '%s%s' % (spf[wrdcnt-1], x)
                        spf[wrdcnt -1] = newline
                        #wrdcnt =-1
                    elif spf[wrdcnt-1][-1] == 'p' and spf[wrdcnt-1][:-1].isdigit() and x == 'ctc':
                        logger.fdebug('THIS SHOULD BE : %s%s' % (spf[wrdcnt-1], x))
                        newline = '%s%s' % (spf[wrdcnt-1], x)
                        spf[wrdcnt -1] = newline
                        #wrdcnt =-1
                except Exception as e:
                    spf.append(x)
            else:
                spf.append(x)
            wrdcnt +=1

        if len(spf) > 0:
            split_file = spf
            logger.fdebug('NEWLY SPLIT REORGD: %s' % split_file)
        #10-20-2018 ---END

        if len(split_file) == 1:
            logger.fdebug('Improperly formatted filename - there is no seperation using appropriate characters between wording.')
            ret_sf1 = re.sub('\-',' ', ret_sf1).strip()
            split_file = re.findall('(?imu)\([\w\s-]+\)|[-+]?\d*\.\d+|\d+|[\w-]+|#?\d\.\d+|#(?<![\w\d])XCV(?![\w\d])+|\)', ret_sf1, re.UNICODE)


        possible_issuenumbers = []
        volumeprior = False
        volume = None
        volume_found = {}
        datecheck = []
        lastissue_label = None
        lastissue_position = 0
        lastmod_position = 0
        booktype = 'issue'

        file_length = 0
        validcountchk = False
        sep_volume = False
        current_pos = -1

        year_check = re.findall(r'(\d{4})(?=[\s]|annual\b|$)', modfilename, flags=re.I)
        ignore_mod_position = -1
        if year_check:
            ignore_mod_position = self.char_file_position(modfilename, year_check[0], modfilename.index(year_check[0]))
            #logger.fdebug('[%s] year_check: %s' % (ignore_mod_position,year_check,))

        for sf in split_file:
            current_pos +=1
            #the series title will always be first and be AT LEAST one word.
            if split_file.index(sf) >= 0 and not volumeprior:
                dtcheck = re.sub('[\(\)\,]', '', sf).strip()
                #if there's more than one date, assume the right-most date is the actual issue date.
                if any(['19' in dtcheck, '20' in dtcheck]) and not any([dtcheck.lower().startswith('v19'), dtcheck.lower().startswith('v20')]) and len(dtcheck) >=4:
                    logger.fdebug('checking date : %s' % dtcheck)
                    checkdate_response = self.checkthedate(dtcheck)
                    if checkdate_response:
                        if dtcheck.endswith('-') and int(dtcheck[:-1]) == int(checkdate_response):
                            volume_found['volume'] = dtcheck[:-1]
                            volume_found['position'] = split_file.index(sf,current_pos)
                            logger.fdebug('volume detected as : %s' % dtcheck)
                            continue
                        logger.fdebug('date: %s' % checkdate_response)
                        datecheck.append({'date':         dtcheck,
                                          'position':     split_file.index(sf),
                                          'mod_position': self.char_file_position(modfilename, sf, lastmod_position)})

            #this handles the exceptions list in the match for alpha-numerics
            if re.sub('g11', "\'", sf.lower()) == "director's":
                try:
                    tmp_test = split_file.index(sf)+1
                except Exception as e:
                    logger.warn('failure to match to Director\'s Cut - ignoring as an issue match')
                else:
                    try:
                        if all([split_file[tmp_test].lower() == 'cut', split_file.index("Directorg11s")+1 <= len(split_file), split_file.index("Cut") == split_file.index("Directorg11s")+1]):
                            logger.fdebug('director\'s match!')
                            test_exception = "Director's Cut"
                    except Exception as e:
                        pass
            else:
                #test_exception = ''.join([i for i in sf if not i.isdigit()])
                # Changing this to look at whole strings for new pattern match exceptions
                test_exception = sf

            if helpers.issueExceptionCheck(test_exception, full_match=True):
                logger.fdebug('Exception match: %s' % test_exception)
                if lastissue_label is not None:
                    if lastissue_position == (split_file.index(sf) -1):
                        if any([test_exception == "Director's Cut", test_exception == '(DC)']):
                            num_label = '%s %s' % (lastissue_label, "Director's Cut")
                        else:
                            num_label = '%s %s' % (lastissue_label, sf)
                        logger.fdebug('alphanumeric issue number detected as : %s' % num_label)
                        for x in possible_issuenumbers:
                            possible_issuenumbers = []
                            if int(x['position']) != int(lastissue_position):
                                possible_issuenumbers.append({'number':        x['number'],
                                                              'position':      x['position'],
                                                              'mod_position':  x['mod_position'],
                                                              'validcountchk': x['validcountchk']})

                        possible_issuenumbers.append({'number':       num_label,
                                                      'position':     lastissue_position,
                                                      'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                      'validcountchk': validcountchk})
                else:
                    #if the issue number & alpha character(s) don't have a space seperating them (ie. 15A)
                    #test_exception is the alpha-numeric
                    logger.fdebug('Possible alpha numeric issue (or non-numeric only). Testing my theory.')
                    if sf.lower() == test_exception.lower():
                        logger.fdebug('[%s] Exception is exact match to %s (Pure String Issue Number)' % (test_exception, sf))
                        possible_issuenumbers.append({'number':       sf,
                                                        'position':     current_pos,
                                                        'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                        'validcountchk': validcountchk})
                    else:
                        test_sf = re.sub(test_exception.lower(), '', sf.lower()).strip()
                        logger.fdebug('[%s] Removing possible alpha issue leaves: %s (Should be a numeric)' % (test_exception, test_sf))
                        if test_sf.isdigit():
                            possible_issuenumbers.append({'number':       sf,
                                                        'position':     split_file.index(sf),
                                                        'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                        'validcountchk': validcountchk})
                        else:
                            test_position = modfilename[self.char_file_position(modfilename, sf,lastmod_position)-1]
                            if test_position == '#':
                                possible_issuenumbers.append({'number':       sf,
                                                            'position':     split_file.index(sf),
                                                            'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                            'validcountchk': validcountchk})

            if sf == 'XCV':
#  new 2016-09-19 \ attempt to check for XCV which replaces any unicode above
                for x in list(wrds):
                    if x != '':
                        tmpissue_number = re.sub('XCV', x, split_file[split_file.index(sf)])
                logger.fdebug('[SPECIAL-CHARACTER ISSUE] Possible issue # : %s' % tmpissue_number)
                possible_issuenumbers.append({'number':       sf,
                                              'position':     split_file.index(sf),
                                              'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                              'validcountchk': validcountchk})

            count = None
            found = False

            match = re.search('(?<=\sof\s)\d+(?=\s)', sf, re.IGNORECASE)
            if match:
                logger.fdebug('match')
                count = match.group()
                found = True

            if found is False:
                match = re.search('(?<=\(of\s)\d+(?=\))', sf,  re.IGNORECASE)
                if match:
                    count = match.group()
                    found = True


            if count:
#                count = count.lstrip("0")
                logger.fdebug('Mini-Series Count detected. Maximum issue # set to : %s' % count.lstrip('0'))
                # if the count was  detected, then it's in a '(of 4)' or whatever pattern
                # 95% of the time the digit immediately preceding the '(of 4)' is the actual issue #
                logger.fdebug('Issue Number SHOULD BE: %s' % lastissue_label)
                validcountchk = True

            match2 = re.search('(\d+[\s])covers', sf, re.IGNORECASE)
            if match2:
                num_covers = re.sub('[^0-9]', '', match2.group()).strip()
                #logger.fdebug('%s covers detected within filename' % num_covers)
                continue

            if all([lastissue_position == (split_file.index(sf) -1), lastissue_label is not None, '#' not in sf, sf != 'p']):
                #find it in the original file to see if there's a decimal between.
                findst = lastissue_mod_position+1
                if findst >= len(modfilename):
                    findst = len(modfilename) -1

                # TODO: What is this condition?  How can this ever be anything but true?
                if modfilename[findst] != '.' or modfilename[findst] != '#': #findst != '.' and findst != '#':
                    if sf.isdigit():
                        seper_num = False
                        for x in datecheck:
                            if x['position'] == split_file.index(sf, lastissue_position):
                                seper_num = True
                        if seper_num is False:
                            logger.fdebug('2 seperate numbers detected. Assuming 2nd number is the actual issue')

                        #possible_issuenumbers.append({'number':       sf,
                        #                              'position':     split_file.index(sf, lastissue_position), #modfilename.find(sf)})
                        #                              'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                        #                              'validcountchk': validcountchk})
                        #used to see if the issue is an alpha-numeric (ie. 18.NOW, 50-X, etc)
                        lastissue_position = split_file.index(sf, lastissue_position)
                        lastissue_label = sf
                        lastissue_mod_position = file_length
                    else:
                        pass
                else:
                    bb = len(lastissue_label) + findst
                    #find current sf 
                    #logger.fdebug('bb: ' + str(bb) + '[' + modfilename[findst:bb] + ']')
                    cf = modfilename.find(sf, file_length)
                    #logger.fdebug('cf: ' + str(cf) + '[' + modfilename[cf:cf+len(sf)] + ']')
                    diff = bb
                    #logger.fdebug('diff: ' + str(bb) + '[' + modfilename[bb] + ']')
                    if modfilename[bb] == '.':
                        #logger.fdebug('decimal detected.')
                        logger.fdebug('[DECiMAL-DETECTION] Issue being stored for validation as : %s' % modfilename[findst:cf+len(sf)])
                        for x in possible_issuenumbers:
                            possible_issuenumbers = []
                            #logger.fdebug('compare: ' + str(x['position']) + ' .. ' + str(lastissue_position))
                            #logger.fdebug('compare: ' + str(x['position']) + ' .. ' + str(split_file.index(sf, lastissue_position)))
                            if int(x['position']) != int(lastissue_position) and int(x['position']) != split_file.index(sf, lastissue_position):
                                possible_issuenumbers.append({'number':        x['number'],
                                                              'position':      x['position'],
                                                              'mod_position':  x['mod_position'],
                                                              'validcountchk': x['validcountchk']})

                        possible_issuenumbers.append({'number':        modfilename[findst:cf+len(sf)],
                                                      'position':      split_file.index(lastissue_label, lastissue_position),
                                                      'mod_position':  findst,
                                                      'dec_position':  bb,
                                                      'rem_position':  split_file.index(sf),
                                                      'validcountchk': validcountchk})
                    else:
                        if ('#' in sf or sf.isdigit()) or validcountchk:
                            if validcountchk:
                                #if it's not a decimal but the digits are back-to-back, then it's something else.
                                possible_issuenumbers.append({'number':        lastissue_label,
                                                              'position':      lastissue_position,
                                                              'mod_position':  lastissue_mod_position,
                                                              'validcountchk': validcountchk})

                                validcountchk = False
                            #used to see if the issue is an alpha-numeric (ie. 18.NOW, 50-X, etc)
                            lastissue_position = split_file.index(sf, lastissue_position)
                            lastissue_label = sf
                            lastissue_mod_position = file_length

            elif '#' in sf:
                logger.fdebug('Issue number found: %s' % sf)
                #pound sign will almost always indicate an issue #, so just assume it's as such.
                locateiss_st = modfilename.find('#')
                locateiss_end = modfilename.find(' ', locateiss_st)
                if locateiss_end == -1:
                    locateiss_end = modfilename.find('_', locateiss_st)
                    if locateiss_end == -1:
                        locateiss_end = modfilename.find('\.', locateiss_st)
                        if locateiss_end == -1:
                            locateiss_end = len(modfilename)
                if modfilename[locateiss_end-1] == ')':
                    locateiss_end = locateiss_end -1
                possible_issuenumbers.append({'number':       modfilename[locateiss_st:locateiss_end],
                                              'position':     split_file.index(sf), #locateiss_st})
                                              'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                              'validcountchk': validcountchk})

                #used to see if the issue is an alpha-numeric (ie. 18.NOW, 50-X, etc)
                lastissue_position = split_file.index(sf, lastissue_position)
                lastissue_label = sf
                lastissue_mod_position = file_length

            #now we try to find the series title &/or volume lablel.
            if any( [sf.lower().startswith('v'), sf.lower().startswith('vol'), volumeprior == True, 'volume' in sf.lower(), 'vol' in sf.lower(), 'part' in sf.lower()] ) and sf.lower() not in {'one','two','three','four','five','six'}:
                if any([ split_file[split_file.index(sf)].isdigit(), split_file[split_file.index(sf)][3:].isdigit(), split_file[split_file.index(sf)][1:].isdigit() ]):
                    if all(identifier in sf for identifier in ['.', 'v']):
                        volume = sf.split('.')[0]
                    else:
                        volume = re.sub("[^0-9]", "", sf)
                    if volumeprior:
                        try:
                            volume_found['position'] = split_file.index(volumeprior_label, current_pos -1) #if this passes, then we're ok, otherwise will try exception
                            logger.fdebug('volume_found: %s' % volume_found['position'])
                            #remove volume numeric from split_file
                            split_file.pop(volume_found['position'])
                            split_file.pop(split_file.index(sf, current_pos-1))
                            #join the previous label to the volume numeric
                            #volume = str(volumeprior_label) + str(volume)
                            #insert the combined info back
                            split_file.insert(volume_found['position'], volumeprior_label + volume)
                            split_file.insert(volume_found['position']+1, '')
                            #volume_found['position'] = split_file.index(sf, current_pos)
                            #logger.fdebug('NEWSPLITFILE: %s' % split_file)
                        except:
                            volumeprior = False
                            volumeprior_label = None
                            sep_volume = False
                            continue
                    else:
                        volume_found['position'] = split_file.index(sf, current_pos)

                    volume_found['volume'] = volume
                    logger.fdebug('volume label detected as : Volume %s @ position: %s' % (volume, volume_found['position']))
                    volumeprior = False
                    volumeprior_label = None
                elif all(['vol' in sf.lower(), len(sf) == 3]) or all(['vol.' in sf.lower(), len(sf) == 4]):
                    #if there's a space between the vol and # - adjust.
                    volumeprior = True
                    volumeprior_label = sf
                    sep_volume = True
                    logger.fdebug('volume label detected, but vol. number is not adjacent, adjusting scope to include number.')
                elif 'volume' in sf.lower():
                    volume = re.sub("[^0-9]", "", sf)
                    if volume.isdigit():
                        volume_found['volume'] = volume
                        volume_found['position'] = split_file.index(sf)
                    else:
                        volumeprior = True
                        volumeprior_label = sf
                        sep_volume = True
                elif all(['part' in sf.lower(), len(sf) == 4]):
                    if self.watchcomic is not None and 'part' not in self.watchcomic.lower():
                        volume = re.sub("[^0-9]", "", sf)
                        if volume.isdigit():
                            volume_found['volume'] = volume
                            volume_found['position'] = split_file.index(sf)
                        else:
                            volumeprior = True
                            volumeprior_label = sf
                            sep_volume = True

                elif any([sf == 'I', sf == 'II', sf == 'III', sf == 'IV']) and volumeprior:
                    volumeprior = False
                    volumeprior_label = None
                    sep_volume = False
                    continue
            else:
                #reset the sep_volume indicator here in case a false Volume detected above
                sep_volume = False
                #check here for numeric or negative number
                if sf.isdigit() and split_file.index(sf, current_pos) == 0:
                    continue
                if sf.isdigit():
                    possible_issuenumbers.append({'number':       sf,
                                                  'position':     split_file.index(sf, current_pos), #modfilename.find(sf)})
                                                  'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                  'validcountchk': validcountchk})

                    #used to see if the issue is an alpha-numeric (ie. 18.NOW, 50-X, etc)
                    lastissue_position = split_file.index(sf, current_pos)
                    lastissue_label = sf
                    lastissue_mod_position = file_length
                    #logger.fdebug('possible issue found: %s' % sf)
                else:
                    try:
                        x = float(sf)
                        #validity check
                        if x < 0:
                            # Check that this negative isn't part of a hyphenated split issue number
                            if (lastissue_label is not None) and (lastissue_position == (current_pos -1)) and re.sub(r'^#','',lastissue_label).isdigit():
                                splitIssue = re.sub(r'^#','',lastissue_label) + sf
                                logger.fdebug('I have encountered a hyphenated split issue #: %s' % splitIssue)    
                                possible_issuenumbers.append({'number':       splitIssue,
                                                            'position':     lastissue_position,
                                                            'mod_position': lastissue_mod_position,
                                                            'validcountchk': validcountchk})
                                lastissue_label = splitIssue
                                lastissue_position = split_file.index(sf, lastissue_position)                            
                                lastissue_mod_position = file_length
                            else:
                                logger.fdebug('I have encountered a negative issue #: %s' % sf)
                                possible_issuenumbers.append({'number':       sf,
                                                            'position':     split_file.index(sf, lastissue_position), #modfilename.find(sf)})
                                                            'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                            'validcountchk': validcountchk})
                                lastissue_label = sf
                                lastissue_position = split_file.index(sf, lastissue_position)                            
                                lastissue_mod_position = file_length
                        elif x > 0:
                            if x == float('inf') and split_file.index(sf, lastissue_position) <= 2:
                                logger.fdebug('infinity wording detected - position places it within series title boundaries..')
                            else:
                                logger.fdebug('I have encountered a decimal issue #: %s' % sf)
                                possible_issuenumbers.append({'number':       sf,
                                                              'position':     split_file.index(sf, lastissue_position), #modfilename.find(sf)})
                                                              'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                              'validcountchk': validcountchk})

                                lastissue_position = split_file.index(sf, lastissue_position)
                                lastissue_label = sf
                                lastissue_mod_position = file_length
                        else:
                            raise ValueError
                    except ValueError as e:
                       #10-20-2018 - to detect issue numbers such as #000.0000½
                        if lastissue_label is not None and lastissue_position == int(split_file.index(sf))-1 and sf == 'XCV':
                            logger.fdebug('this should be: %s%s' % (lastissue_label, sf))
                            pi = []
                            for x in possible_issuenumbers:
                                if (x['number'] == lastissue_label and x['position'] == lastissue_position) or (x['number'] == sf and x['position'] == split_file.index(sf, lastissue_position)):
                                    pass
                                else:
                                    pi.append({'number':       x['number'],
                                               'position':     x['position'],
                                               'mod_position': x['mod_position'],
                                               'validcountchk': x['validcountchk']})

                            lastissue_label = '%s%s' % (lastissue_label, sf)
                            pi.append({'number':        lastissue_label,
                                       'position':      lastissue_position,
                                       'mod_position':  lastmod_position,
                                       'validcountchk': validcountchk})

                            if len(pi) > 0:
                                possible_issuenumbers = pi

                        elif sf.lower() == 'of' and lastissue_label is not None and lastissue_position == int(split_file.index(sf))-1:
                            logger.fdebug('MINI-SERIES DETECTED')
                        else:
                            if any([re.sub('[\(\)]', '', sf.lower()).strip() == 'tpb', re.sub('[\(\)]', '', sf.lower()).strip() == 'digital tpb']):
                                logger.fdebug('TRADE PAPERBACK DETECTED. NOT DETECTING ISSUE NUMBER - ASSUMING VOLUME')
                                booktype = 'TPB'
                                try:
                                    if volume_found['volume'] is not None:
                                        possible_issuenumbers.append({'number':       volume_found['volume'],
                                                                      'position':     volume_found['position'],
                                                                      'mod_position': self.char_file_position(modfilename, volume_found['volume'], lastmod_position),
                                                                      'validcountchk': validcountchk})
                                except:
                                    possible_issuenumbers.append({'number':       '1',
                                                                  'position':      split_file.index(sf, lastissue_position), #modfilename.find(sf)})
                                                                  'mod_position':  self.char_file_position(modfilename, sf, lastmod_position),
                                                                  'validcountchk': validcountchk})

                            elif any([sf.lower() == 'gn', sf.lower() == 'graphic novel']):
                                logger.fdebug('GRAPHIC NOVEL DETECTED. NOT DETECTING ISSUE NUMBER - ASSUMING VOLUME')
                                booktype = 'GN'
                            elif any([sf.lower() == 'hc', sf.lower() == 'hardcover']):
                                logger.fdebug('HARDCOVER DETECTED. NOT DETECTING ISSUE NUMBER - ASSUMING VOLUME')
                                booktype = 'HC'
                            else:
                                if 'could not convert string to float' not in str(e):
                                    logger.fdebug('[%s] Error detecting issue # - ignoring this result : %s' % (e, sf))

                        volumeprior = False
                        volumeprior_label = None
                        sep_volume = False
                        pass

            #keep track of where in the original modfilename the positions are in order to check against it for decimal places, etc.
            file_length += len(sf) + 1 #1 for space
            if file_length > len(modfilename):
                file_length = len(modfilename)

            lastmod_position = self.char_file_position(modfilename, sf, lastmod_position)


        highest_series_pos = len(split_file)
        issue2year = False
        issue_year = None
        possible_years = []
        yearmodposition = None
        logger.fdebug('datecheck: %s' % datecheck)
        if len(datecheck) > 0:
            for dc in sorted(datecheck, key=operator.itemgetter('position'), reverse=True):
                a = self.checkthedate(dc['date'])
                ab = str(a)
                sctd = self.checkthedate(str(dt.datetime.now().year))
                logger.fdebug('sctd: %s' % sctd)
                # + 1 sctd so that we can allow for issue dates that cross over into the following year when it's nearer to the end of said year.
                if int(ab) > int(sctd) + 1:
                    logger.fdebug('year is in the future, ignoring and assuming part of series title.')
                    yearposition = None
                    yearmodposition = None
                    continue
                else:
                    logger.fdebug('year verified as : %s' % issue_year)
                    if highest_series_pos > dc['position'] and all([dc['position'] != 0, len(datecheck) > 1]):
                        highest_series_pos = dc['position']
                    issue_year = dc['date']
                    yearposition = dc['position']
                    yearmodposition = dc['mod_position']
                if len(ab) == 4:
                    issue_year = ab
                    logger.fdebug('year verified as: %s' % issue_year)
                    possible_years.append({'year':            issue_year,
                                           'yearposition':    dc['position'],
                                           'yearmodposition': dc['mod_position']})
                else:
                    issue_year = ab
                    logger.fdebug('date verified as: %s' % issue_year)

            if len(possible_years) == 1:
                issueyear = possible_years[0]['year']
                yearposition = possible_years[0]['yearposition']
                yearmodposition = possible_years[0]['yearmodposition']
            else:
                if len(possible_issuenumbers) > 0:
                    for x in possible_years:
                        logger.fdebug('yearposition[%s] -- dc[position][%s]' % (yearposition, x['yearposition']))
                        if yearposition < x['yearposition']:
                            if all([len(possible_issuenumbers) == 1, possible_issuenumbers[0]['number'] == x['year'], x['yearposition'] != possible_issuenumbers[0]['position']]):
                                logger.fdebug('issue2year is true')
                                issue2year = True
                                highest_series_pos = x['yearposition']
                            yearposition = x['yearposition']
                            yearmodposition = x['yearmodposition']

            if yearposition is not None and highest_series_pos > yearposition:
                highest_series_pos = yearposition #dc['position']: highest_series_pos = dc['position']
        else:
            issue_year = None
            yearposition = None
            yearmodposition = None
            logger.fdebug('No year present within title - ignoring as a variable.')

        #if ignore_mod_position != -1:
        #    logger.info('possible_issuenumbers: %s' % (possible_issuenumbers,))
        #    p_cnt = 0
        #    for pp in possible_issuenumbers:
        #        logger.info('pp: %s' % (pp,))
        #        if ignore_mod_position == pp['mod_position']:
        #            pppp = possible_issuenumbers.pop(p_cnt)
        #            logger.info('IGNORE POSITION TRIGGERED for : %s' % (pppp,))
        #            break
        #        p_cnt +=1

        logger.fdebug('highest_series_position: %s' % highest_series_pos)
        #---2019-11-30 account for scanner Glorith-HD stupid naming conventions
        if len(possible_issuenumbers) == 0 and scangroup == 'Glorith-HD':
            logger.fdebug('Abnormal formatting detected. Time to fix this shiet, yo.')
            if any([yearposition == 0, yearposition is None]):
                logger.fdebug('Too stupid of a format. Nope. Not gonna happen - just reinvent the wheel you fooker.')
            else:
                issposs = yearposition + 1
                #logger.fdebug('split_file: %s' % split_file[issposs])
                if '(' and ')' in split_file[issposs]:
                    new_issuenumber = split_file[issposs]
                possible_issuenumbers.append({'number':        re.sub('[/(/)]', '', split_file[issposs]).strip(),
                                              'position':      split_file.index(new_issuenumber, yearposition),
                                              'mod_position':  self.char_file_position(modfilename, new_issuenumber, yearmodposition),
                                              'validcountchk': False})
        #---end 2019-11-30
        issue_number = None
        dash_numbers = []
        issue_number_position = len(split_file)
        if len(possible_issuenumbers) > 0:
            logger.fdebug('possible_issuenumbers: %s' % possible_issuenumbers)
            if len(possible_issuenumbers) >= 1:
                p = 1
                if '-' not in split_file[0]:
                    finddash = modfilename.find('-')
                    if finddash != -1:
                        logger.fdebug('hyphen located at position: %s' % finddash)
                        if yearposition:
                            logger.fdebug('yearposition: %s' % yearposition)
                else:
                    finddash = -1
                    logger.fdebug('dash is in first word, not considering for determing issue number.')

                for pis in sorted(possible_issuenumbers, key=operator.itemgetter('position'), reverse=True):
                    a = ' '.join(split_file)
                    lenn = pis['mod_position'] + len(pis['number'])
                    if lenn == len(a) and finddash != -1:
                        logger.fdebug('Numeric detected as the last digit after a hyphen. Typically this is the issue number.')
                        if pis['position'] != yearposition:
                            issue_number = pis['number']
                            #logger.info('Issue set to: ' + str(issue_number))
                            issue_number_position = pis['position']
                            if highest_series_pos > pis['position']: highest_series_pos = pis['position']
                        #break
                    elif pis['validcountchk'] == True:
                        issue_number = pis['number']
                        issue_number_position = pis['position']
                        logger.fdebug('Issue verified and detected as part of a numeric count sequnce: %s' % issue_number)
                        if highest_series_pos > pis['position']: highest_series_pos = pis['position']
                        break
                    elif pis['mod_position'] > finddash and finddash != -1:
                        if yearmodposition is not None:
                            if finddash < yearmodposition and finddash > (yearmodposition + len(split_file[yearposition])):
                                logger.fdebug('issue number is positioned after a dash - probably not an issue number, but part of an issue title')
                                dash_numbers.append({'mod_position': pis['mod_position'],
                                                     'number':       pis['number'],
                                                     'position':     pis['position']})
                                continue
                            #2019-10-05 fix - if decimal-spaced filename has a series title with a hyphen will include issue # as part of series title
                            elif yearposition == pis['position']:
                                logger.fdebug('Already validated year, ignoring as possible issue number: %s' % pis['number'])
                                continue
                            #end 2019-10-05
                    elif yearposition == pis['position']:
                        logger.fdebug('Already validated year, ignoring as possible issue number: %s' % pis['number'])
                        continue
                    if p == 1:
                        issue_number = pis['number']
                        issue_number_position = pis['position']
                        logger.fdebug('issue number :%s' % issue_number) #(pis)
                        if highest_series_pos > pis['position'] and issue2year is False: highest_series_pos = pis['position']
                    #else:
                        #logger.fdebug('numeric probably belongs to series title: ' + str(pis))
                    p+=1
            else:
                issue_number = possible_issuenumbers[0]['number']
                issue_number_position = possible_issuenumbers[0]['position']
                if highest_series_pos > possible_issuenumbers[0]['position']: highest_series_pos = possible_issuenumbers[0]['position']

        if issue_number:
            issue_number = re.sub('#', '', issue_number).strip()
        else:
            if len(dash_numbers) > 0 and finddash !=-1 :
                #there are numbers after a dash, which was incorrectly accounted for.
                fin_num_position = finddash
                fin_num = None
                for dn in dash_numbers:
                    if dn['mod_position'] > finddash and dn['mod_position'] > fin_num_position:
                        fin_num_position = dn['mod_position']
                        fin_num = dn['number']
                        fin_pos = dn['position']

                if fin_num:
                    logger.fdebug('Issue number re-corrected to : %s' % fin_num)
                    issue_number = fin_num
                    if highest_series_pos > fin_pos: highest_series_pos = fin_pos

#--- this is new - 2016-09-18 /account for unicode in issue number when issue number is not deteted above
        logger.fdebug('issue_position: %s' % issue_number_position)
        if all([issue_number_position == highest_series_pos, 'XCV' in split_file, issue_number is None]):
            for x in list(wrds):
                if x != '':
                    issue_number = re.sub('XCV', x, split_file[issue_number_position-1])
                    highest_series_pos -=1
                    issue_number_position -=1

        if issue_number is None:
            if any([booktype == 'TPB', booktype == 'HC', booktype == 'GN']):
                logger.fdebug('%s detected. Volume assumption is number: %s' % (booktype, volume_found))
            else:
                if issue_year is not None and issue_number is None and '2000ad' in ''.join(split_file).lower():
                    for x in possible_years:
                        try:
                            if split_file.index(issue_year) < x['yearposition'] and x['year'] != issue_year:
                                issue_year = x['year']
                                break
                        except Exception as e:
                            pass
                    issue_number = issue_year
                    issue_year = None
                elif len(volume_found) > 0:
                    logger.fdebug('Possible UNKNOWN TPB/GN/HC {One-Shot} detected. Volume assumption is number: %s' % (volume_found))
                    booktype = 'TPB/GN/HC/One-Shot'
                else:
                    logger.fdebug('No issue number present in filename.')
        else:
            logger.fdebug('issue verified as : %s' % issue_number)
        issue_volume = None
        if len(volume_found) > 0:
            issue_volume = 'v' + str(volume_found['volume'])
            if all([highest_series_pos + 1 != volume_found['position'], highest_series_pos != volume_found['position'] + 1, sep_volume == False, booktype == 'issue', len(possible_issuenumbers) > 0]):
                logger.fdebug('Extra item(s) are present between the volume label and the issue number. Checking..')
                split_file.insert(int(issue_number_position), split_file.pop(volume_found['position'])) #highest_series_pos-1, split_file.pop(volume_found['position']))
                logger.fdebug('new split: %s' % split_file)
                highest_series_pos = volume_found['position'] -1
                #2019-10-02 -  account for volume BEFORE issue number
                if issue_number_position > highest_series_pos:
                    issue_number_position -=1
            else:
                if highest_series_pos > volume_found['position']:
                    if sep_volume:
                        highest_series_pos = volume_found['position'] - 1
                    else:
                        highest_series_pos = volume_found['position']
            logger.fdebug('Volume detected as : %s' % issue_volume)

        if all([len(volume_found) == 0, booktype != 'issue']) or all([len(volume_found) == 0, issue_number_position == len(split_file)]):
            if not '2000ad' in ''.join(split_file).lower():
                issue_volume = 'v1'

        #at this point it should be in a SERIES ISSUE VOLUME YEAR kind of format
        #if the position of the issue number is greater than the highest series position, make it the highest series position.
        if issue_number_position != len(split_file) and issue_number_position > highest_series_pos:
            if not volume_found:
                highest_series_pos = issue_number_position
            else:
                if sep_volume:
                    highest_series_pos = issue_number_position -2
                else:
                    if split_file[issue_number_position -1].lower() == 'annual' or split_file[issue_number_position -1].lower() == 'special':
                        highest_series_pos = issue_number_position
                    else:
                        highest_series_pos = issue_number_position - 1
                        #if volume_found['position'] < issue_number_position:
                        #    highest_series_pos = issue_number_position - 1
                        #else:
                        #    highest_series_pos = issue_number_position

        #make sure if we have multiple years detected, that the right one gets picked for the actual year vs. series title
        if len(possible_years) > 1:
            for x in sorted(possible_years, key=operator.itemgetter('yearposition'), reverse=False):
                if x['yearposition'] <= highest_series_pos:
                    logger.fdebug('year %s is within series title. Ignoring as YEAR value' % x['year'])
                else:
                    logger.fdebug('year %s is outside of series title range. Accepting of year.' % x['year'])
                    issue_year = x['year']
                    highest_series_pos = x['yearposition']
                    break
        else:
            try:
                if possible_years[0]['yearposition'] <= highest_series_pos and possible_years[0]['year_position'] != 0:
                   highest_series_pos = possible_years[0]['yearposition']
                elif possible_years[0]['year_position'] == 0:
                   yearposition = 1
            except:
                pass

        match_type = None  #folder/file based on how it was matched.

        #logger.fdebug('highest_series_pos is : ' + str(highest_series_pos)
        splitvalue = None
        alt_series = None
        alt_issue = None
        onefortheleader = False
        try:
            if yearposition is not None:
                try:
                    if volume_found['position'] >= issue_number_position:
                        tmpval = highest_series_pos + (issue_number_position - volume_found['position'])
                    else:
                        tmpval = yearposition - issue_number_position
                except:
                    tmpval = yearposition - issue_number_position
            else:
                tmpval = 1
        except:
            pass
        else:
            if tmpval >= 2:
                #logger.fdebug('There are %s extra words between the issue # and the year position. Deciphering if issue title or part of series title.' % tmpval)
                #logger.fdebug('split_file[issue_number_position]: [%s] -->  %s' % (issue_number_position, split_file[issue_number_position]))
                #logger.fdebug('split_file[yearposition]: [%s] --> %s' % (yearposition, split_file[yearposition]))
                #2024-01-07 - new for one-shot where no issue number in filename, but year is present in title
                if split_file[issue_number_position] == re.sub(r'[\)\(]', '', split_file[yearposition]).strip():
                    logger.fdebug('issue number is the same as year - assuming issue number is actually part of the title and this is a one-shot-type of book')
                    onefortheleader = True
                    if [True for x in split_file if x.lower() == 'annual']:
                        booktype = 'issue'
                    else:
                        booktype = 'TPB/GN/HC/One-Shot'
                    issue_number = None
                else:
                    tmpval1 = ' '.join(split_file[issue_number_position:yearposition])
                    if split_file[issue_number_position+1] == '-':
                        usevalue = ' '.join(split_file[issue_number_position+2:yearposition])
                        splitv = split_file[issue_number_position+2:yearposition]
                    else:
                        splitv = split_file[issue_number_position:yearposition]
                    splitvalue = ' '.join(splitv)
                #end 2024-01-07
            else:
                #store alternate naming of title just in case
                if '-' not in split_file[0]:
                    c_pos = 1
                    #logger.info('split_file: %s' % split_file)
                    while True:
                        try:
                            fdash = split_file.index("-", c_pos)
                        except:
                            #logger.info('dash not located/finished searching for dashes.')
                            break
                        else:
                            #logger.info('hyphen located at position: ' + str(fdash))
                            c_pos = 2
                            #c_pos = fdash +1
                            break
                    if c_pos > 1:
                        #logger.info('Issue_number_position: %s / fdash: %s' % (issue_number_position, fdash))
                        try:
                            if volume_found['position'] < issue_number_position:
                                alt_issue = ' '.join(split_file[fdash+1:volume_found['position']])
                            else:
                                alt_issue = ' '.join(split_file[fdash+1:issue_number_position])
                        except:
                                alt_issue = ' '.join(split_file[fdash+1:issue_number_position])

                        if alt_issue.endswith('-'): alt_issue = alt_issue[:-1].strip()
                        if len(alt_issue) == 0:
                            alt_issue = None
                        alt_series = ' '.join(split_file[:fdash])
                        logger.fdebug('ALT-SERIES NAME [ISSUE TITLE]: %s [%s]' % (alt_series, alt_issue))

        #logger.info('highest_series_position: ' + str(highest_series_pos))
        #logger.info('issue_number_position: ' + str(issue_number_position))
        #logger.info('volume_found: ' + str(volume_found))

   #2017-10-21
        if highest_series_pos > issue_number_position and not onefortheleader:
            highest_series_pos = issue_number_position
            #if volume_found['position'] >= issue_number_position:
            #    highest_series_pos = issue_number_position
            #else:
            #    print 'nuhuh'
   #---
        match_type = None  #folder/file based on how it was matched.
        logger.fdebug('sf_highest_series_pos: %s' % split_file[:highest_series_pos])

        #here we should account for some characters that get stripped out due to the regex's
        #namely, unique characters - known so far: +
        #c1 = '+'
        #series_name = ' '.join(split_file[:highest_series_pos])
        if yearposition != 0:
            if yearposition is not None and yearposition < highest_series_pos:
                if yearposition+1 == highest_series_pos:
                    highest_series_pos = yearposition
                else:
                    if split_file[yearposition+1] == '-' and yearposition+2 == highest_series_pos:
                        highest_series_pos = yearposition
            series_name = ' '.join(split_file[:highest_series_pos])
        else:
            if highest_series_pos <= issue_number_position and all([len(split_file[0]) == 4, split_file[0].isdigit()]):
                if re.sub('[\.\s]', '', split_file[yearposition+1]).strip().lower() == 'ad' or all([split_file[yearposition+1].lower() == 'a' and split_file[yearposition+2].lower() == 'd']):
                    series_name = ' '.join(split_file[yearposition:highest_series_pos]) #logger.info('BOOOOYYYYAHHHHH')
                    issue_year = None
                else:
                    series_name = ' '.join(split_file[:highest_series_pos])
            else:
                series_name = ' '.join(split_file[yearposition+1:highest_series_pos])

        for x in list(wrds):
            if x != '':
                if 'XCV' in series_name:
                    series_name = re.sub('XCV', x, series_name,1)
                elif issue_number and 'XCV' in issue_number:
                    issue_number = re.sub('XCV', x, issue_number,1)
                if alt_series is not None:
                    if 'XCV' in alt_series:
                        alt_series = re.sub('XCV', x, alt_series,1)
                if alt_issue is not None:
                    if 'XCV' in alt_issue:
                        alt_issue = re.sub('XCV', x, alt_issue,1)

        series_name = re.sub('c11', '+', series_name)
        series_name = re.sub('f11', '&', series_name)
        series_name = re.sub('g11', '\'', series_name)
        series_name = re.sub('h11', '@', series_name)
        if alt_series is not None:
            alt_series = re.sub('c11', '+', alt_series)
            alt_series = re.sub('f11', '&', alt_series)
            alt_series = re.sub('g11', '\'', alt_series)
            alt_series = re.sub('h11', '@', alt_series)

        if series_name.endswith('-'): 
            series_name = series_name[:-1].strip()
        if '\?' in series_name:
            series_name = re.sub('\?', '', series_name).strip()

        logger.fdebug('series title possibly: %s' % series_name)
        if splitvalue is not None:
            logger.fdebug('[SPLITVALUE] possible issue title: %s' % splitvalue)
            alt_series = '%s %s' % (series_name, splitvalue)
            if booktype != 'issue':
                if alt_issue is not None:
                    alt_issue =  re.sub('tpb', '', splitvalue, flags=re.I).strip()
                if alt_series is not None:
                    alt_series = re.sub('tpb', '', alt_series, flags=re.I).strip()
        if alt_series is not None:
            if booktype != 'issue':
                if alt_series is not None:
                    alt_series = re.sub('tpb', '', alt_series, flags=re.I).strip()
            logger.fdebug('Alternate series / issue title: %s [%s]' % (alt_series, alt_issue))

        #if the filename is unicoded, it won't match due to the unicode translation. Keep the unicode as well as the decoded.
        series_name_decoded= unicodedata.normalize('NFKD', series_name)
        og_seriesn = series_name
        #check for annual in title(s) here.
        if not self.justparse and all([mylar.CONFIG.ANNUALS_ON, 'annual' not in self.watchcomic.lower(), 'special' not in self.watchcomic.lower()]):
            if 'annual' in series_name.lower():
                isn = 'Annual'
                if issue_number is not None:
                    issue_number = '%s %s' % (isn, issue_number)
                else:
                    issue_number = isn
                year_check = re.findall(r'(\d{4})(?=[\s]|annual\b|$)', series_name, flags=re.I)
                if year_check:
                    ann_line = '%s annual' % year_check[0]
                    logger.fdebug('ann_line: %s' % ann_line)
                    if any([issue_number is None, issue_number == 'Annual']):
                        issue_number = ann_line
                    series_name = re.sub(ann_line, '', series_name, flags=re.I).strip()
                    series_name_decoded = re.sub(ann_line, '', series_name_decoded, flags=re.I).strip()
                series_name = re.sub('annual', '', series_name, flags=re.I).strip()
                series_name_decoded = re.sub('annual', '', series_name_decoded, flags=re.I).strip()
            elif 'special' in series_name.lower():
                isn = 'Special'
                if issue_number is not None:
                    issue_number = '%s %s' % (isn, issue_number)
                else:
                    issue_number = isn
                series_name = re.sub('special', '', series_name, flags=re.I).strip()
                series_name_decoded = re.sub('special', '', series_name_decoded, flags=re.I).strip()

        if (any([issue_number is None, series_name is None]) and booktype == 'issue'):
            bythepass = False
            if all([issue_number is None, booktype == 'issue', issue_volume is not None]):
                if ignore_mod_position != -1:
                    logger.fdebug('Possible Annual detected - no identifying issue number present, no clarification in filename - assuming year (%s) as issue number' % issue_year)
                    issue_number = issue_year
                else:
                    logger.fdebug('Possible UNKNOWN TPB/GN/HC detected - no issue number present, no clarification in filename, but volume present with series title')
                    booktype = 'TPB/GN/HC/One-Shot'
            else:
                if all([issue_number is None, issue_volume is None, 'annual' in series_name.lower(), booktype == 'issue']):
                    if ignore_mod_position != -1:
                        logger.fdebug('Possible Annual detected - no identifying issue number present, no clarification in filename - assuming year (%s) as issue number' % issue_year)
                        issue_number = issue_year
                        bythepass = True
                    else:
                        logger.fdebug('Cannot parse the filename properly. I\'m going to make note of this filename so that my evil ruler can make it work.')
                else:
                    logger.fdebug('Cannot parse the filename properly. I\'m going to make note of this filename so that my evil ruler can make it work.')

                if not bythepass:
                    if series_name is not None:
                        dreplace = self.dynamic_replace(series_name)['mod_seriesname']
                    else:
                        dreplace = None
                    return {'parse_status':        'failure',
                            'sub':                 path_list,
                            'comicfilename':       filename,
                            'comiclocation':       self.dir,
                            'series_name':         series_name,
                            'series_name_decoded': series_name_decoded,
                            'issueid':             issueid,
                            'alt_series':          alt_series,
                            'alt_issue':           alt_issue,
                            'dynamic_name':        dreplace,
                            'issue_number':        issue_number,
                            'justthedigits':       issue_number, #redundant but it's needed atm
                            'series_volume':       issue_volume,
                            'issue_year':          issue_year,
                            'annual_comicid':      None,
                            'scangroup':           scangroup,
                            'booktype':            booktype,
                            'reading_order':       None}

        if self.justparse:
            return {'parse_status':           'success',
                    'type':                   re.sub('\.','', filetype).strip(),
                    'sub':                    path_list,
                    'comicfilename':          filename,
                    'comiclocation':          self.dir,
                    'series_name':            series_name,
                    'series_name_decoded':    series_name_decoded,
                    'issueid':                issueid,
                    'alt_series':             alt_series,
                    'alt_issue':              alt_issue,
                    'dynamic_name':           self.dynamic_replace(series_name)['mod_seriesname'],
                    'series_volume':          issue_volume,
                    'issue_year':             issue_year,
                    'issue_number':           issue_number,
                    'scangroup':              scangroup,
                    'booktype':               booktype,
                    'reading_order':          reading_order}

        series_info = {}
        series_info = {'sub':                    path_list,
                       'type':                   re.sub('\.','', filetype).strip(),
                       'comicfilename':          filename,
                       'comiclocation':          self.dir,
                       'series_name':            series_name,
                       'series_name_decoded':    series_name_decoded,
                       'issueid':                issueid,
                       'alt_series':             alt_series,
                       'alt_issue':              alt_issue,
                       'series_volume':          issue_volume,
                       'issue_year':             issue_year,
                       'issue_number':           issue_number,
                       'scangroup':              scangroup,
                       'booktype':               booktype}

        return self.matchIT(series_info)

    def matchIT(self, series_info):
        qmatch_chk = None
        series_name = series_info['series_name']
        alt_series = series_info['alt_series']
        filename = series_info['comicfilename']
        #compare here - match comparison against u_watchcomic.
        #logger.fdebug('Series_Name: ' + series_name + ' --- WatchComic: ' + self.watchcomic)
        #check for dynamic handles here.
        mod_dynamicinfo = self.dynamic_replace(series_name)
        mod_seriesname = mod_dynamicinfo['mod_seriesname']
        mod_watchcomic = mod_dynamicinfo['mod_watchcomic']
        mod_altseriesname = None
        mod_altseriesname_decoded = None
        if series_info['alt_series'] is not None:
            mod_dynamicalt = self.dynamic_replace(alt_series)
            mod_altseriesname = mod_dynamicalt['mod_seriesname']
            mod_alt_decoded = self.dynamic_replace(alt_series)
            mod_altseriesname_decoded = mod_alt_decoded['mod_seriesname']
        #logger.fdebug('mod_altseriesname: %s' % mod_altseriesname)
        mod_series_decoded = self.dynamic_replace(series_info['series_name_decoded'])
        mod_seriesname_decoded = mod_series_decoded['mod_seriesname']
        mod_watch_decoded = self.dynamic_replace(self.og_watchcomic)
        mod_watchname_decoded = mod_watch_decoded['mod_watchcomic']

        #remove the spaces...
        nspace_seriesname = re.sub(' ', '', mod_seriesname)
        nspace_watchcomic = re.sub(' ', '', mod_watchcomic)
        nspace_altseriesname = None
        if mod_altseriesname is not None:
            nspace_altseriesname = re.sub(' ', '', mod_altseriesname)
            nspace_altseriesname_decoded = re.sub(' ', '', mod_altseriesname_decoded)
        nspace_seriesname_decoded = re.sub(' ', '', mod_seriesname_decoded)
        nspace_watchname_decoded = re.sub(' ', '', mod_watchname_decoded)
        try:
            if self.AS_ALT[0] != '127372873872871091383 abdkhjhskjhkjdhakajhf':
                logger.fdebug('Possible Alternate Names to match against (if necessary): %s' % self.AS_Alt)
        except:
            pass
        justthedigits = series_info['issue_number']

        #logger.fdebug('nspace_watchcomic: %s' % nspace_watchcomic)
        #logger.fdebug('series_name: %s' % series_name)
        annualisation = False
        n_name = 'annual'
        if mylar.CONFIG.ANNUALS_ON:
            ann_year_check = re.findall(r'(\d{4})(?=[\s]|annual\b|$)', self.watchcomic, flags=re.I)
            if all(
                      [
                          'annual' in nspace_watchcomic.lower(),
                          'annual' not in series_name.lower()
                      ]
                ) or all(
                      [
                          'annual' not in nspace_watchcomic.lower(),
                          'annual' in series_name.lower()
                      ]
                ):
                annualisation = True
                justthedigits = 'Annual'
                if series_info['issue_number'] is not None:
                    if len(justthedigits) == 4:
                        justthedigits = '%s %s' % (series_info['issue_number'], justthedigits)
                    else:
                        justthedigits += ' %s' % series_info['issue_number']
                if ann_year_check:
                    n_name = '%s%s' % (ann_year_check[0], 'annual')
                    nspace_seriesname = re.sub(n_name, '', nspace_seriesname.lower()).strip()
                    nspace_seriesname_decoded = re.sub(n_name, '', nspace_seriesname_decoded.lower()).strip()
                nspace_seriesname = re.sub('annual', '', nspace_seriesname.lower()).strip()
                nspace_seriesname_decoded = re.sub('annual', '', nspace_seriesname_decoded.lower()).strip()
            if alt_series is not None and 'annual' in alt_series.lower():
                if ann_year_check:
                    n_name = '%s%s' % (ann_year_check[0], 'annual')
                    nspace_altseriesname = re.sub(n_name, '', nspace_altseriesname.lower()).strip()
                    nspace_altseriesname_decoded = re.sub(n_name, '', nspace_altseriesname_decoded.lower()).strip()
                nspace_altseriesname = re.sub('annual', '', nspace_altseriesname.lower()).strip()
                nspace_altseriesname_decoded = re.sub('annual', '', nspace_altseriesname_decoded.lower()).strip()
        if mylar.CONFIG.ANNUALS_ON and 'special' not in nspace_watchcomic.lower():
            if 'special' in series_name.lower():
                justthedigits = 'Special'
                if series_info['issue_number'] is not None:
                    justthedigits += ' %s' % series_info['issue_number']
                nspace_seriesname = re.sub('special', '', nspace_seriesname.lower()).strip()
                nspace_seriesname_decoded = re.sub('special', '', nspace_seriesname_decoded.lower()).strip()
            if alt_series is not None and 'special' in alt_series.lower():
                nspace_altseriesname = re.sub('special', '', nspace_altseriesname.lower()).strip()
                nspace_altseriesname_decoded = re.sub('special', '', nspace_altseriesname_decoded.lower()).strip()

        seriesalt = False
        if nspace_altseriesname is not None:
            if re.sub('\|','', nspace_altseriesname.lower()).strip() == re.sub('\|', '', nspace_watchcomic.lower()).strip():
                seriesalt = True
                qmatch_chk = 'alt_match'

        #logger.info('seriesalt: %s' % seriesalt)
        #logger.info('nspace_seriesname: %s' % nspace_seriesname)
        #logger.info('nspace_watchcomic: %s' % nspace_watchcomic)
        #logger.info('nspace_serisname_decoded: %s' % nspace_seriesname_decoded)
        #logger.info('nspace_watchname_decoded: %s' % nspace_watchname_decoded)
        #logger.info('self.AS_Alt: %s' % self.AS_Alt)
        if any(
                  [
                       seriesalt is True,
                       re.sub('\|','', nspace_seriesname.lower()).strip() == re.sub('\|', '', nspace_watchcomic.lower()).strip(),
                       re.sub('\|','', nspace_seriesname_decoded.lower()).strip() == re.sub('\|', '', nspace_watchname_decoded.lower()).strip(),
                   ]
       ) or all(
                   [
                       annualisation is True,
                       re.sub(n_name, '', re.sub('\|', '', nspace_watchcomic.lower()).strip()) == re.sub('\|', '', nspace_seriesname.lower()).strip(),
                   ]
       ) or any(
                   re.sub('[\|\s]','', x.lower()).strip() == re.sub('[\|\s]','', nspace_seriesname.lower()).strip() for x in self.AS_Alt
       ):
            if qmatch_chk is None:
                qmatch_chk = 'match'
        if qmatch_chk is not None:
            #logger.fdebug('[%s][MATCH: %s][seriesALT: %s] %s' % (qmatch_chk, seriesalt, series_info['series_name'], filename))
            enable_annual = False
            annual_comicid = None
            if any(re.sub('[\|\s]','', x.lower()).strip() == re.sub('[\|\s]','', nspace_seriesname.lower()).strip() for x in self.AS_Alt):
                #if the alternate search name is almost identical, it won't match up because it will hit the 'normal' first.
                #not important for series' matches, but for annuals, etc it is very important.
                #loop through the Alternates picking out the ones that match and then do an overall loop.
                loopchk = [x for x in self.AS_Alt if re.sub('[\|\s]','', x.lower()).strip() == re.sub('[\|\s]','', nspace_seriesname.lower()).strip()]
                if len(loopchk) > 0 and loopchk[0] != '':
                    if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('[FILECHECKER] This should be an alternate: %s' % loopchk)
                    if any(['annual' in series_name.lower(), 'special' in series_name.lower()]):
                        if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                            logger.fdebug('[FILECHECKER] Annual/Special detected - proceeding')
                        enable_annual = True

                else:
                    loopchk = []
                    #logger.info('loopchk: ' + str(loopchk))

                #if the names match up, and enable annuals isn't turned on - keep it all together.
                if re.sub('\|', '', nspace_watchcomic.lower()).strip() == re.sub('\|', '', nspace_seriesname.lower()).strip() and enable_annual is False:
                    loopchk.append(nspace_watchcomic)
                    if any(['annual' in nspace_seriesname.lower(), 'special' in nspace_seriesname.lower()]):
                        if 'biannual' in nspace_seriesname.lower():
                            if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                                logger.fdebug('[FILECHECKER] BiAnnual detected - wouldn\'t Deadpool be proud?')
                            nspace_seriesname = re.sub('biannual', '', nspace_seriesname).strip()
                            enable_annual = True
                        elif 'annual' in nspace_seriesname.lower():
                            if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                                logger.fdebug('[FILECHECKER] Annual detected - proceeding cautiously.')
                            off_year_check = re.findall(r'(\d{4})(?=[\s]|annual\b|$)', self.watchcomic, flags=re.I)
                            if off_year_check:
                                n_name = '%s%s' % (off_year_check[0], 'annual')
                                nspace_seriesname = re.sub(n_name, '', nspace_seriesname.lower()).strip()
                            nspace_seriesname = re.sub('annual', '', nspace_seriesname.lower()).strip()
                            enable_annual = False
                        elif 'special' in nspace_seriesname.lower():
                            if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                                logger.fdebug('[FILECHECKER] Special detected - proceeding cautiously.')
                            nspace_seriesname = re.sub('special', '', nspace_seriesname).strip()
                            enable_annual = False

                if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                    logger.fdebug('[FILECHECKER] Complete matching list of names to this file [%s] : %s' % (len(loopchk), loopchk))

                for loopit in loopchk:
                    #now that we have the list of all possible matches for the watchcomic + alternate search names, we go through the list until we find a match.
                    modseries_name = loopit
                    if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('[FILECHECKER] AS_Tuple : %s' % self.AS_Tuple)
                        for ATS in self.AS_Tuple:
                            if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                                logger.fdebug('[FILECHECKER] %s comparing to %s' % (ATS['AS_Alternate'], nspace_seriesname))
                            if re.sub('\|','', ATS['AS_Alternate'].lower()).strip() == re.sub('\|','', nspace_seriesname.lower()).strip():
                                if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                                    logger.fdebug('[FILECHECKER] Associating ComiciD : %s' % ATS['ComicID'])
                                annual_comicid = str(ATS['ComicID'])
                                modseries_name = ATS['AS_Alternate']
                                break

                    logger.fdebug('[FILECHECKER] %s - watchlist match on : %s' % (modseries_name, filename))

            if enable_annual:
                if annual_comicid is not None:
                   if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                       logger.fdebug('enable annual is on')
                       logger.fdebug('annual comicid is %s' % annual_comicid)
                   if 'biannual' in nspace_watchcomic.lower():
                       if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                           logger.fdebug('bi annual detected')
                       justthedigits = 'BiAnnual %s' % justthedigits
                   elif 'annual' in nspace_watchcomic.lower():
                       if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                           logger.fdebug('annual detected')
                       justthedigits = 'Annual %s' % justthedigits
                   elif 'special' in nspace_watchcomic.lower():
                       justthedigits = 'Special %s' % justthedigits

            return {'process_status':  qmatch_chk,
                    'sub':             series_info['sub'],
                    'volume':          series_info['series_volume'],
                    'match_type':      None,  #match_type - will eventually pass if it wasa folder vs. filename match,
                    'comicfilename':   filename,
                    'comiclocation':   series_info['comiclocation'],
                    'series_name':     series_info['series_name'],
                    'series_volume':   series_info['series_volume'],
                    'alt_series':      series_info['alt_series'],
                    'alt_issue':       series_info['alt_issue'],
                    'issue_year':      series_info['issue_year'],
                    'issueid':         series_info['issueid'],
                    'justthedigits':   justthedigits,
                    'annual_comicid':  annual_comicid,
                    'scangroup':       series_info['scangroup'],
                    'booktype':        series_info['booktype']}

        else:
            #logger.fdebug('[NO MATCH] ' + filename + ' [WATCHLIST:' + self.watchcomic + ']')
            return {'process_status': 'fail',
                    'comicfilename':  filename,
                    'sub':            series_info['sub'],
                    'comiclocation':  series_info['comiclocation'],
                    'series_name':    series_info['series_name'],
                    'alt_series':     series_info['alt_series'],
                    'alt_issue':      series_info['alt_issue'],
                    'issue_number':   series_info['issue_number'],
                    'series_volume':  series_info['series_volume'],
                    'issue_year':     series_info['issue_year'],
                    'issueid':        series_info['issueid'],
                    'scangroup':      series_info['scangroup'],
                    'booktype':       series_info['booktype']}

    def char_file_position(self, file, findchar, lastpos):
        return file.find(findchar, lastpos)

    def traverse_directories(self, dir):
        filelist = []
        comic_ext = ('.cbr','.cbz','.cb7','.pdf')
        comic_ext = tuple(x for x in comic_ext if x not in mylar.CONFIG.IGNORE_SEARCH_WORDS)

        if all([mylar.CONFIG.ENABLE_TORRENTS is True, self.pp_mode is True]):
            from mylar import db
            myDB = db.DBConnection()
            pp_crclist =[]
            pp_crc = myDB.select("SELECT a.crc, b.IssueID FROM Snatched as a INNER JOIN issues as b ON a.IssueID=b.IssueID WHERE (a.Status='Post-Processed' or a.status='Snatched' or a.provider='32P' or a.provider='WWT' or a.provider='DEM') and a.crc is not NULL and (b.Status='Downloaded' or b.status='Archived') GROUP BY a.crc ORDER BY a.DateAdded")
            for pp in pp_crc:
                pp_crclist.append({'IssueID':   pp['IssueID'],
                                   'crc':       pp['crc']})

        for dirname, subs, files in os.walk(dir):

            for fname in files:
                if dirname == dir:
                    direc = None
                else:
                    direc = dirname
                    if '.AppleDouble' in direc:
                        #Ignoring MAC OS Finder directory of cached files (/.AppleDouble/<name of file(s)>)
                        continue

                if fname.startswith('._'):
                    continue

                if all([mylar.CONFIG.ENABLE_TORRENTS is True, self.pp_mode is True]):
                    tcrc = helpers.crc(os.path.join(dirname, fname))
                    crcchk = [x for x in pp_crclist if tcrc == x['crc']]
                    if crcchk:
                        #logger.fdebug('[FILECHECKEER] Already post-processed this item %s - Ignoring' % fname)
                        continue

                filename = fname
                comicsize = 0
                if os.path.splitext(filename)[1].lower().endswith(comic_ext):
                    if direc is None:
                        try:
                            comicsize = os.path.getsize(os.path.join(dir, filename))
                        except Exception as e:
                            logger.warn('error: %s' % e)
                    else:
                        comicsize = os.path.getsize(os.path.join(dir, direc, fname))

                    if comicsize == 0:
                        # 0-byte size file encountered - ignore it as it's a placeholder most likely
                        continue

                    filelist.append({'directory':  direc,   #subdirectory if it exists
                                     'filename':   filename,
                                     'comicsize':  comicsize})

        logger.info('there are %s files.' % len(filelist))

        return filelist

    def dynamic_replace(self, series_name):
        mod_watchcomic = None

        if self.watchcomic:
            watchdynamic_handlers_match = [x for x in self.dynamic_handlers if x.lower() in self.watchcomic.lower()]
            #logger.fdebug('watch dynamic handlers recognized : ' + str(watchdynamic_handlers_match))
            watchdynamic_replacements_match = [x for x in self.dynamic_replacements if x.lower() in self.watchcomic.lower()]
            #logger.fdebug('watch dynamic replacements recognized : ' + str(watchdynamic_replacements_match))
            mod_watchcomic = re.sub('[\s\s+\_\.]', '%$', self.watchcomic)
            mod_watchcomic = re.sub('[\#]', '', mod_watchcomic)
            mod_find = []
            wdrm_find = []
            if any([watchdynamic_handlers_match, watchdynamic_replacements_match]):
                for wdhm in watchdynamic_handlers_match:
                    #check the watchcomic
                    #first get the position.
                    mod_find.extend([m.start() for m in re.finditer('\\' + wdhm, mod_watchcomic)])
                    if len(mod_find) > 0:
                        for mf in mod_find:
                            spacer = ''
                            for i in range(0, len(wdhm)):
                                spacer+='|'
                            mod_watchcomic = mod_watchcomic[:mf] + spacer + mod_watchcomic[mf+1:]

                for wdrm in watchdynamic_replacements_match:
                    wdrm_find.extend([m.start() for m in re.finditer(wdrm.lower(), mod_watchcomic.lower())])
                    if len(wdrm_find) > 0:
                        for wd in wdrm_find:
                            spacer = ''
                            for i in range(0, len(wdrm)):
                                spacer+='|'
                            mod_watchcomic = mod_watchcomic[:wd] + spacer + mod_watchcomic[wd+len(wdrm):]

        series_name = re.sub(r'[\u2014|\u2013|\u2e3a|\u2e3b]', ' - ', series_name)
        series_name = re.sub('\u2019', " ' ", series_name)
        seriesdynamic_handlers_match = [x for x in self.dynamic_handlers if x.lower() in series_name.lower()]
        #logger.fdebug('series dynamic handlers recognized : ' + str(seriesdynamic_handlers_match))
        seriesdynamic_replacements_match = [x for x in self.dynamic_replacements if x.lower() in series_name.lower()]
        #logger.fdebug('series dynamic replacements recognized : ' + str(seriesdynamic_replacements_match))
        mod_seriesname = re.sub('[\s\s+\_\.]', '%$', series_name)
        mod_seriesname = re.sub('[\#]', '', mod_seriesname)
        ser_find = []
        sdrm_find = []
        if any([seriesdynamic_handlers_match, seriesdynamic_replacements_match]):
            for sdhm in seriesdynamic_handlers_match:
                #check the series_name
                ser_find.extend([m.start() for m in re.finditer('\\' + sdhm, mod_seriesname)])
                if len(ser_find) > 0:
                    for sf in ser_find:
                        spacer = ''
                        for i in range(0, len(sdhm)):
                            spacer+='|'
                        mod_seriesname = mod_seriesname[:sf] + spacer + mod_seriesname[sf+1:]

            for sdrm in seriesdynamic_replacements_match:
                sdrm_find.extend([m.start() for m in re.finditer(sdrm.lower(), mod_seriesname.lower())])
                if len(sdrm_find) > 0:
                    for sd in sdrm_find:
                        spacer = ''
                        for i in range(0, len(sdrm)):
                            spacer+='|'
                        mod_seriesname = mod_seriesname[:sd] + spacer + mod_seriesname[sd+len(sdrm):]

        if mod_watchcomic:
            mod_watchcomic = re.sub('\|+', '|', mod_watchcomic)
            if mod_watchcomic.endswith('|'):
                mod_watchcomic = mod_watchcomic[:-1]
            mod_watchcomic = re.sub('[\%\$]+', '', mod_watchcomic)

        mod_seriesname = re.sub('\|+', '|', mod_seriesname)
        if mod_seriesname.endswith('|'):
            mod_seriesname = mod_seriesname[:-1]
        mod_seriesname = re.sub('[\%\$]+', '', mod_seriesname)

        return {'mod_watchcomic':  mod_watchcomic,
                'mod_seriesname':  mod_seriesname}

    def altcheck(self):
       #iniitate the alternate list here so we can add in the different alternate search names (if present)
        AS_Alt = []

        AS_Tuple = []
        if self.AlternateSearch is not None and self.AlternateSearch != 'None':
            chkthealt = self.AlternateSearch.split('##')
            #logger.info('[' + str(len(chkthealt)) + '] chkthealt: ' + str(chkthealt))
            i = 0
            while (i <= len(chkthealt)):
                try:
                    calt = chkthealt[i]
                except IndexError:
                    break
                AS_tupled = False
                AS_Alternate = re.sub('##', '', calt)
                if '!!' in AS_Alternate:
                    # if it's !! present, it's the comicid associated with the series as an added annual.
                    # extract the !!, store it and then remove it so things will continue.
                    as_start = AS_Alternate.find('!!')
                    if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('as_start: %s --- %s' % (as_start, AS_Alternate[as_start:]))
                    as_end = AS_Alternate.find('##', as_start)
                    if as_end == -1:
                        as_end = len(AS_Alternate)
                    if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('as_start: %s --- %s' % (as_end, AS_Alternate[as_start:as_end]))
                    AS_ComicID =  AS_Alternate[as_start +2:as_end]
                    if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('[FILECHECKER] Extracted comicid for given annual : %s' % AS_ComicID)
                    AS_Alternate = re.sub('!!' + str(AS_ComicID), '', AS_Alternate)
                    AS_tupled = True
                as_dyninfo = self.dynamic_replace(AS_Alternate)
                altsearchcomic = as_dyninfo['mod_seriesname']

                if AS_tupled:
                    AS_Tuple.append({"ComicID":      AS_ComicID,
                                     "AS_Alternate": altsearchcomic})
                AS_Alt.append(altsearchcomic)
                i+=1
        else:
            #create random characters so it will never match.
            altsearchcomic = "127372873872871091383 abdkhjhskjhkjdhakajhf"
            AS_Alt.append(altsearchcomic)

        return {'AS_Alt':   AS_Alt,
                'AS_Tuple': AS_Tuple}
    
    def checkthedate(self, txt, fulldate=False, cnt=0):
    #    txt='''\
    #    Jan 19, 1990
    #    January 19, 1990
    #    Jan 19,1990
    #    01/19/1990
    #    01/19/90
    #    1990
    #    Jan 1990
    #    January1990'''

        fmts = ('%Y','%Y-', '%b %d, %Y','%B %d, %Y','%B %d %Y','%m/%d/%Y','%m/%d/%y','(%m/%d/%Y)','%b %Y','%B%Y','%b %d,%Y','%m-%Y','%B %Y','%Y-%m-%d','%Y-%m','%Y%m','%Y-%m-00')
        mnths = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
        parsed=[]

        if fulldate is False:
            for e in txt.splitlines():
                for fmt in fmts:
                    try:
                        t = dt.datetime.strptime(e, fmt)
                        parsed.append((e, fmt, t)) 
                        break
                    except ValueError as err:
                        pass
        else:
            for e in txt.split():
                if cnt == 0:
                    for x in mnths:
                        mnth = re.sub('\.', '', e.lower())
                        if x.lower() in mnth and len(mnth) <= 4:
                            add_date = x + ' '
                            cnt+=1
                            break

                elif cnt == 1:
                    issnumb = re.sub(',', '', e).strip()
                    if issnumb.isdigit() and int(issnumb) < 31:
                        add_date += issnumb + ', '
                        cnt+=1
                elif cnt == 2:
                    possyear = helpers.cleanhtml(re.sub('\.', '', e).strip())
                    if type(possyear) == bytes:
                        possyear = possyear.decode('utf-8')
                    if possyear.isdigit() and int(possyear) > 1970 and int(possyear) < 2020:
                        add_date += possyear
                        cnt +=1
                if cnt == 3:
                    return self.checkthedate(add_date, fulldate=False, cnt=-1)


                if cnt <= 0:
                    for fmt in fmts:
                        try:
                            t = dt.datetime.strptime(e, fmt)
                            parsed.append((e, fmt, t))
                            break
                        except ValueError as err:
                            pass
        # check that all the cases are handled
        success={t[0] for t in parsed}
        for e in txt.splitlines():
            if e not in success:
                pass #print e    

        dateline = None

        #logger.info('parsed: %s' % parsed)

        for t in parsed:
            #logger.fdebug('"{:20}" => "{:20}" => {}'.format(*t))
            if fulldate is False and cnt != -1:
                dateline = t[2].year
            else:
                dateline = t[2].strftime('%Y-%m-%d')
            break

        return dateline

def validateAndCreateDirectory(dir, create=False, module=None, dmode=None):
    if module is None:
        module = ''
    module += '[DIRECTORY-CHECK]'
    if dmode is None:
        dirmode = 'comic'
    else:
        dirmode = dmode

    try:
        if os.path.exists(dir):
            logger.info('%s Found %s directory: %s' % (module, dirmode, dir))
            return True
        else:
            logger.warn('%s Could not find %s directory: %s' % (module, dirmode, dir))
            if create:
                if dir.strip():
                    logger.info('%s Creating %s directory (%s) : %s' % (module, dirmode, mylar.CONFIG.CHMOD_DIR, dir))
                    try:
                        os.umask(0) # this is probably redudant, but it doesn't hurt to clear the umask here.
                        if mylar.CONFIG.ENFORCE_PERMS:
                            permission = int(mylar.CONFIG.CHMOD_DIR, 8)
                            os.makedirs(dir.rstrip(), permission)
                            s_perms = setperms(dir.rstrip(), True)
                            if not s_perms:
                                raise OSError
                        else:
                            os.makedirs(dir.rstrip())
                    except OSError as e:
                        if not s_perms:
                            logger.warn('%s Unable to set permissions for : %s [%s]' % (module, dir, e))
                        else:
                            logger.warn('%s Could not create directory: %s [%s]. Aborting' % (module, dir, e))
                        return False
                    else:
                        return True
                else:
                    logger.warn('%s Provided directory [%s] is blank. Aborting.' % (module, dir))
                    return False
    except OSError as e:
        logger.warn('%s Could not create directory: %s [%s]. Aborting.' % (module, dir, e))
        return False
    return False

def setperms(path, dir=False):

    if 'windows' not in mylar.OS_DETECT.lower():
        try:
            os.umask(0) # this is probably redudant, but it doesn't hurt to clear the umask here.
            if mylar.CONFIG.CHGROUP:
                if mylar.CONFIG.CHOWNER is None or mylar.CONFIG.CHOWNER == 'None' or mylar.CONFIG.CHOWNER == '':
                    mylar.CONFIG.CHOWNER = getpass.getuser()

                if not mylar.CONFIG.CHOWNER.isdigit():
                    try:
                        chowner = getpwnam(mylar.CONFIG.CHOWNER)[2]
                    except Exception as e:
                        logger.warn('[PERMISSIONS] %s does not exist on this system as a user' % mylar.CONFIG.CHOWNER)
                        chowner = -1
                else:
                    chowner = int(mylar.CONFIG.CHOWNER)

                if not mylar.CONFIG.CHGROUP.isdigit():
                    try:
                        chgroup = getgrnam(mylar.CONFIG.CHGROUP)[2]
                    except Exception as e:
                        logger.warn('[PERMISSIONS] %s does not exist on this system as a group' % mylar.CONFIG.CHGROUP)
                        chgroup = -1
                else:
                    chgroup = int(mylar.CONFIG.CHGROUP)

                validity_perm = check_valid_perms(chowner,chgroup)
                logger.fdebug('validity_perm: %s' % validity_perm)
                if validity_perm['status']:
                    chowner = validity_perm['owner']
                    chgroup = validity_perm['group']

                if dir:
                    permission = int(mylar.CONFIG.CHMOD_DIR, 8)
                    if validity_perm['status']:
                        os.chown(path, chowner, chgroup)
                    os.chmod(path, permission)
                elif os.path.isfile(path):
                    permission = int(mylar.CONFIG.CHMOD_FILE, 8)
                    if validity_perm['status']:
                        os.chown(path, chowner, chgroup)
                    os.chmod(path, permission)
                else:
                    for root, dirs, files in os.walk(path):
                        for momo in dirs:
                            permission = int(mylar.CONFIG.CHMOD_DIR, 8)
                            if validity_perm['status']:
                                os.chown(os.path.join(root, momo), chowner, chgroup)
                            os.chmod(os.path.join(root, momo), permission)
                        for momo in files:
                            permission = int(mylar.CONFIG.CHMOD_FILE, 8)
                            if validity_perm['status']:
                                os.chown(os.path.join(root, momo), chowner, chgroup)
                            os.chmod(os.path.join(root, momo), permission)

                logger.fdebug('Successfully changed ownership and permissions [%s:%s] / [%s/%s]' %
                              (chowner, chgroup, mylar.CONFIG.CHMOD_DIR, mylar.CONFIG.CHMOD_FILE))

            elif os.path.isfile(path):
                    permission = int(mylar.CONFIG.CHMOD_FILE, 8)
                    os.chmod(path, permission)
            else:
                for root, dirs, files in os.walk(path):
                    for momo in dirs:
                        permission = int(mylar.CONFIG.CHMOD_DIR, 8)
                        os.chmod(os.path.join(root, momo), permission)
                    for momo in files:
                        permission = int(mylar.CONFIG.CHMOD_FILE, 8)
                        os.chmod(os.path.join(root, momo), permission)

                logger.fdebug('Successfully changed permissions [%s/%s]' % (mylar.CONFIG.CHMOD_DIR, mylar.CONFIG.CHMOD_FILE))

        except OSError as e:
            logger.error('[ERROR @ path: %s] %s. Exiting...' % (path, e))
            return False

    return True

def check_valid_perms(chowner, chgroup):
    if all([chowner == -1, chgroup == -1]):
        logger.warn('[PERMISSONS] Unable to set ownership due to both owner:group [%s:%s] being invalid.' % (mylar.CONFIG.CHOWNER, mylar.CONFIG.CHGROUP))
        return {'status': False,
                'owner': chowner,
                'group': chgroup}
    else:
        ch_problem = None
        if chowner == -1:
            ch_problem = 'owner'
            chownr = getpass.getuser()
            chowner = getgrnam(chownr)[1]
        elif chgroup == -1:
            ch_problem = 'group'
            chgp = getpass.getuser()
            chgroup = getgrnam(chgp)[2]
        if ch_problem:
            logger.warn('[PERMISSIONS] Partial enforcement of permissions being done due to invalid %s specified.'
                        ' Perms set to: %s:%s ' % (ch_problem, chowner, chgroup))

        return {'status': True,
                'owner': chowner,
                'group': chgroup}
