#/usr/bin/env python
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
import urllib
import logging
import unicodedata
import optparse
from fnmatch import fnmatch

import datetime as dt

import subprocess
from subprocess import CalledProcessError, check_output

import mylar
from mylar import logger, helpers

class FileChecker(object):

    def __init__(self, dir=None, watchcomic=None, Publisher=None, AlternateSearch=None, manual=None, sarc=None, justparse=None, file=None):
        #dir = full path to the series Comic Location (manual pp will just be psssing the already parsed filename)
        if dir:
            self.dir = dir
        else:
            self.dir = None

        if watchcomic:
            #watchcomic = unicode name of series that is being searched against
            self.og_watchcomic = watchcomic
            self.watchcomic = re.sub('\?', '', watchcomic).strip()  #strip the ? sepearte since it affects the regex.
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


        self.failed_files = []
        self.dynamic_handlers = ['/','-',':','\'',',','&','?']
        self.dynamic_replacements = ['and','the']
        self.rippers = ['-empire','-empire-hd','minutemen-','-dcp']

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
            return {'parse_status':   runresults['parse_status'],
                    'sub':            runresults['sub'],
                    'comicfilename':  runresults['comicfilename'],
                    'comiclocation':  runresults['comiclocation'],
                    'series_name':    runresults['series_name'],
                    'series_volume':  runresults['series_volume'],
                    'issue_year':     runresults['issue_year'],
                    'issue_number':   runresults['issue_number'],
                    'scangroup':      runresults['scangroup']
                    }
        else:
            filelist = self.traverse_directories(self.dir)

            for files in filelist:
                filedir = files['directory']
                filename = files['filename']
                filesize = files['comicsize']
                if filename.startswith('.'):
                    continue

                logger.info('[FILENAME]: ' + filename)
                runresults = self.parseit(self.dir, filename, filedir)
                if runresults:
                    try:
                        if runresults['parse_status']:
                            run_status = runresults['parse_status']
                    except:
                        if runresults['process_status']:
                            run_status = runresults['process_status']

                    if any([run_status == 'success', run_status == 'match']):
                        if self.justparse:
                            comiclist.append({
                                    'sub':            runresults['sub'],
                                    'comicfilename':  runresults['comicfilename'],
                                    'comiclocation':  runresults['comiclocation'],
                                    'series_name':    runresults['series_name'],
                                    'series_volume':  runresults['series_volume'],
                                    'issue_year':     runresults['issue_year'],
                                    'issue_number':   runresults['issue_number'],
                                    'scangroup':      runresults['scangroup']
                                    })
                        else:
                            comiclist.append({
                                     'sub':                     runresults['sub'],
                                     'ComicFilename':           runresults['comicfilename'],
                                     'ComicLocation':           runresults['comiclocation'],
                                     'ComicSize':               files['comicsize'],
                                     'ComicName':               runresults['series_name'],
                                     'SeriesVolume':            runresults['series_volume'],
                                     'IssueYear':               runresults['issue_year'],
                                     'JusttheDigits':           runresults['justthedigits'],
                                     'AnnualComicID':           runresults['annual_comicid'],
                                     'scangroup':               runresults['scangroup']
                                     })
                        comiccnt +=1
                    else:
                        #failiure
                        self.failed_files.append({'parse_status':   'failure',
                                                  'sub':            runresults['sub'],
                                                  'comicfilename':  runresults['comicfilename'],
                                                  'comiclocation':  runresults['comiclocation'],
                                                  'series_name':    runresults['series_name'],
                                                  'series_volume':  runresults['series_volume'],
                                                  'issue_year':     runresults['issue_year'],
                                                  'issue_number':   runresults['issue_number'],
                                                  'scangroup':      runresults['scangroup']
                                                  })

        watchmatch['comiccount'] = comiccnt
        if len(comiclist) > 0:
            watchmatch['comiclist'] = comiclist

        if len(self.failed_files) > 0:
            logger.info('FAILED FILES: %s', self.failed_files)

        return watchmatch

    def parseit(self, path, filename, subpath=None):

            #filename = filename.encode('ASCII').decode('utf8')
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
                logger.fdebug('[SUB-PATH] Original Path : ' + str(path))
                logger.fdebug('[SUB-PATH] Sub-direcotry : ' + str(subpath))
                tmppath = re.sub(path, '', subpath).strip()
                tmppath = os.path.normpath(tmppath)
                path_list = tmppath.split(os.sep)[-1]
                logger.fdebug('[SUB-PATH] subpath set to : ' + path_list)


            #parse out the extension for type
            comic_ext = ('.cbr','.cbz')
            if os.path.splitext(filename)[1].endswith(comic_ext):
                filetype = os.path.splitext(filename)[1]
            else:
                filetype = 'unknown'

            #find the issue number first.
            #split the file and then get all the relevant numbers that could possibly be an issue number.
            #remove the extension.
            modfilename = re.sub(filetype, '', filename).strip()

            #if it's a story-arc, make sure to remove any leading reading order #'s
            if self.sarc and mylar.READ2FILENAME:
                removest = modfilename.find('-') # the - gets removed above so we test for the first blank space...
                if mylar.FOLDER_SCAN_LOG_VERBOSE:
                   logger.fdebug('[SARC] Checking filename for Reading Order sequence - Reading Sequence Order found #: ' + str(modfilename[:removest]))
                if modfilename[:removest].isdigit() and removest <= 3:
                    modfilename = modfilename[removest+1:]
                    if mylar.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('[SARC] Removed Reading Order sequence from subname. Now set to : ' + modfilename)


            #grab the scanner tags here.
            scangroup = None
            rippers = [x for x in self.rippers if x.lower() in modfilename.lower()]
            if rippers:
                #it's always possible that this could grab something else since tags aren't unique. Try and figure it out.
                if len(rippers) > 0:
                    m = re.findall('[^()]+', modfilename)
                    cnt = 1
                    for rp in rippers:
                        while cnt < len(m):
                            if m[cnt] == ' ':
                                pass
                            elif rp.lower() in m[cnt].lower():
                                scangroup = re.sub('[\(\)]', '', m[cnt]).strip()
                                logger.fdebug('Scanner group tag discovered: ' + scangroup)
                                modfilename = re.sub(m[cnt],'', modfilename).strip()
                                break
                            cnt +=1

            #here we take a snapshot of the current modfilename, the intent is that we will remove characters that match
            #as we discover them - namely volume, issue #, years, etc
            #the remaining strings should be the series title and/or issue title if present (has to be detected properly)
            modseries = modfilename

            sf3 = re.compile(ur"[^,\s_]+", re.UNICODE)
            split_file3 = sf3.findall(modfilename)
            #print split_file3
            ret_sf2 = ' '.join(split_file3)

            sf = re.findall('''\( [^\)]* \) |\[ [^\]]* \] |\S+''', ret_sf2, re.VERBOSE)
            #print sf
            ret_sf1 = ' '.join(sf)

            #here we should account for some characters that get stripped out due to the regex's
            #namely, unique characters - known so far: +, &
            #c11 = '\+'
            #f11 = '\&'
            #g11 = '\''
            ret_sf1 = re.sub('\+', 'c11', ret_sf1).strip()
            ret_sf1 = re.sub('\&', 'f11', ret_sf1).strip()
            ret_sf1 = re.sub('\'', 'g11', ret_sf1).strip()

            #split_file = re.findall('\([\w\s-]+\)|[\w-]+', ret_sf1, re.UNICODE)
            split_file = re.findall('\([\w\s-]+\)|[-+]?\d*\.\d+|\d+|[\w-]+|#?\d+|\)', ret_sf1, re.UNICODE)

            if len(split_file) == 1:
                logger.fdebug('Improperly formatted filename - there is no seperation using appropriate characters between wording.')
                ret_sf1 = re.sub('\-',' ', ret_sf1).strip()
                split_file = re.findall('\([\w\s-]+\)|[-+]?\d*\.\d+|\d+|[\w-]+', ret_sf1, re.UNICODE)


            possible_issuenumbers = []
            volumeprior = False
            volume = None
            volume_found = {}
            datecheck = []
            lastissue_label = None
            lastissue_position = 0
            lastmod_position = 0

            #exceptions that are considered alpha-numeric issue numbers
            exceptions = ('NOW', 'AI', 'AU', 'X', 'A', 'B', 'C', 'INH')

            #unicode characters, followed by int value 
    #        num_exceptions = [{iss:u'\xbd',val:.5},{iss:u'\xbc',val:.25}, {iss:u'\xe',val:.75}, {iss:u'\221e',val:'infinity'}]

            file_length = 0
            validcountchk = False
            sep_volume = False
   
            for sf in split_file:
                #the series title will always be first and be AT LEAST one word.
                if split_file.index(sf) >= 1 and not volumeprior:
                    dtcheck = re.sub('[\(\)\,]', '', sf).strip()
                    #if there's more than one date, assume the right-most date is the actual issue date.
                    if any(['19' in dtcheck, '20' in dtcheck]) and not any([dtcheck.lower().startswith('v19'), dtcheck.lower().startswith('v20')]) and len(dtcheck) >=4:
                        logger.fdebug('checking date : ' + str(dtcheck))
                        checkdate_response = self.checkthedate(dtcheck)
                        if checkdate_response:
                            logger.fdebug('date: ' + str(checkdate_response))
                            datecheck.append({'date':         dtcheck,
                                              'position':     split_file.index(sf),
                                              'mod_position': self.char_file_position(modfilename, sf, lastmod_position)})

                #this handles the exceptions list in the match for alpha-numerics
                test_exception = ''.join([i for i in sf if not i.isdigit()])
                if any([x for x in exceptions if x.lower() == test_exception.lower()]):
                    logger.fdebug('Exception match: ' + test_exception)
                    if lastissue_label is not None:
                        if lastissue_position == (split_file.index(sf) -1):
                            logger.fdebug('alphanumeric issue number detected as : ' + str(lastissue_label) + ' ' + str(sf))
                            for x in possible_issuenumbers:
                                possible_issuenumbers = []
                                if int(x['position']) != int(lastissue_position):
                                    possible_issuenumbers.append({'number':        x['number'],
                                                                  'position':      x['position'],
                                                                  'mod_position':  x['mod_position'],
                                                                  'validcountchk': x['validcountchk']})

                            possible_issuenumbers.append({'number':       str(lastissue_label) + ' ' + str(sf),
                                                          'position':     lastissue_position,
                                                          'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                          'validcountchk': validcountchk})
                    else:
                        #if the issue number & alpha character(s) don't have a space seperating them (ie. 15A)
                        #test_exception is the alpha-numeric
                        logger.fdebug('Possible alpha numeric issue (or non-numeric only). Testing my theory.')
                        test_sf = re.sub(test_exception.lower(), '', sf.lower()).strip()
                        logger.fdebug('[' + test_exception + '] Removing possible alpha issue leaves: ' + test_sf + ' (Should be a numeric)')
                        if test_sf.isdigit():
                            possible_issuenumbers.append({'number':       sf,
                                                          'position':     split_file.index(sf),
                                                          'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                          'validcountchk': validcountchk})
 
                try:
                    sf.decode('ascii')
                except:
                    logger.fdebug('Unicode character detected: ' + sf)
                    if '\xbd' in sf: #.encode('utf-8'):
                        logger.fdebug('[SPECIAL-CHARACTER ISSUE] Possible issue # : ' + sf)
                        possible_issuenumbers.append({'number':       sf,
                                                      'position':     split_file.index(sf),
                                                      'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                      'validcountchk': validcountchk})

                    if '\xe2' in sf:  #(maybe \u221e)
                        logger.fdebug('[SPECIAL-CHARACTER ISSUE] Possible issue # : ' + sf)
                        possible_issuenumbers.append({'number':       sf,
                                                      'position':     split_file.index(sf),
                                                      'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                      'validcountchk': validcountchk})

                    #if '\xbc' in sf:
                    #   '0.25'
                    #if '\xbe' in sf::
                    #   '0.75'


                count = None
                found = False

                match = re.search('(?<=\sof\s)\d+(?=\s)', sf, re.IGNORECASE)
                if match:
                        logger.fdebug('match')
                        count = match.group()
                        found = True

                if not found:
                        match = re.search('(?<=\(of\s)\d+(?=\))', sf,  re.IGNORECASE)
                        if match:
                                count = match.group()
                                found = True


                if count:
#                    count = count.lstrip("0")
                    logger.fdebug('Mini-Series Count detected. Maximum issue # set to : ' + count.lstrip('0'))
                    # if the count was  detected, then it's in a '(of 4)' or whatever pattern
                    # 95% of the time the digit immediately preceding the '(of 4)' is the actual issue #
                    logger.fdebug('Issue Number SHOULD BE: ' + str(lastissue_label))
                    validcountchk = True

                if lastissue_position == (split_file.index(sf) -1) and lastissue_label is not None:
                    #find it in the original file to see if there's a decimal between.
                    #logger.fdebug('lastissue_label: ' + str(lastissue_label))
                    #logger.fdebug('current sf: ' + str(sf))
                    #logger.fdebug('file_length: ' + str(file_length))
                    #logger.fdebug('search_file_length: ' + str(lastissue_mod_position))
                    #logger.fdebug('trunced_search_length: ' + modfilename[lastissue_mod_position+1:]
                    findst = lastissue_mod_position+1
                    #findst = modfilename.find(lastissue_label, lastissue_mod_position+1) #lastissue_mod_position) #file_length - len(lastissue_label))
                    #logger.fdebug('findst: ' + str(findst))
                    if findst != '.': #== -1:
                        if sf.isdigit():
                            logger.fdebug('2 seperate numbers detected. Assuming 2nd number is the actual issue')
                            possible_issuenumbers.append({'number':       sf,
                                                          'position':     split_file.index(sf, lastissue_position), #modfilename.find(sf)})
                                                          'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                          'validcountchk': validcountchk})

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
                            logger.fdebug('[DECiMAL-DETECTION] Issue being stored for validation as : ' + modfilename[findst:cf+len(sf)])
                            for x in possible_issuenumbers:
                                possible_issuenumbers = []
                                logger.fdebug('compare: ' + str(x['position']) + ' .. ' + str(lastissue_position))
                                logger.fdebug('compare: ' + str(x['position']) + ' .. ' + str(split_file.index(sf, lastissue_position)))
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
                                logger.fdebug('validated: ' + sf)
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
                    logger.fdebug('Iissue number found: ' + sf)
                    #pound sign will almost always indicate an issue #, so just assume it's as such.
                    locateiss_st = modfilename.find('#')
                    locateiss_end = modfilename.find(' ', locateiss_st)
                    if locateiss_end == -1:
                        locateiss_end = len(modfilename)
                    possible_issuenumbers.append({'number':       modfilename[locateiss_st:locateiss_end],
                                                  'position':     split_file.index(sf), #locateiss_st})
                                                  'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                  'validcountchk': validcountchk})

                #now we try to find the series title &/or volume lablel.
                if any( [sf.lower().startswith('v'), sf.lower().startswith('vol'), volumeprior == True, 'volume' in sf.lower(), 'vol' in sf.lower()] ):
                    if sf[1:].isdigit() or sf[3:].isdigit() or volumeprior == True:
                        volume = re.sub("[^0-9]", "", sf)
                        volume_found['volume'] = volume
                        if volumeprior:
                            volume_found['position'] = split_file.index(volumeprior_label)
                        else:
                            volume_found['position'] = split_file.index(sf)
                        #logger.fdebug('volume label detected as : Volume ' + str(volume) + ' @ position: ' + str(split_file.index(sf)))
                        volumeprior = False
                        volumeprior_label = None
                    elif 'vol' in sf.lower() and len(sf) == 3:
                        #if there's a space between the vol and # - adjust.
                        volumeprior = True
                        volumeprior_label = sf
                        sep_volume = True
                        #logger.fdebug('volume label detected, but vol. number is not adjacent, adjusting scope to include number.')
                    elif 'volume' in sf.lower():
                        volume = re.sub("[^0-9]", "", sf)
                        if volume.isdigit():
                            volume_found['volume'] = volume
                            volume_found['position'] = split_file.index(sf)
                        else:
                            volumeprior = True
                            volumeprior_label = sf
                            sep_volume = True

                else:
                    #check here for numeric or negative number
                    if sf.isdigit():
                        possible_issuenumbers.append({'number':       sf,
                                                      'position':     split_file.index(sf, lastissue_position), #modfilename.find(sf)})
                                                      'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                      'validcountchk': validcountchk})

                        #used to see if the issue is an alpha-numeric (ie. 18.NOW, 50-X, etc)
                        lastissue_position = split_file.index(sf, lastissue_position)
                        lastissue_label = sf
                        lastissue_mod_position = file_length
                        #logger.fdebug('possible issue found: ' + str(sf)
                    else:
                        try:
                            x = float(sf)
                            #validity check
                            if x < 0:
                                logger.fdebug('I have encountered a negative issue #: ' + str(sf))
                                possible_issuenumbers.append({'number':       sf,
                                                              'position':     split_file.index(sf, lastissue_position), #modfilename.find(sf)})
                                                              'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                              'validcountchk': validcountchk})

                                lastissue_position = split_file.index(sf, lastissue_position)
                                lastissue_label = sf
                                lastissue_mod_position = file_length
                            elif x > 0:
                                logger.fdebug('I have encountered a decimal issue #: ' + str(sf))
                                possible_issuenumbers.append({'number':       sf,
                                                              'position':     split_file.index(sf, lastissue_position), #modfilename.find(sf)})
                                                              'mod_position': self.char_file_position(modfilename, sf, lastmod_position),
                                                              'validcountchk': validcountchk})

                                lastissue_position = split_file.index(sf, lastissue_position)
                                lastissue_label = sf
                                lastissue_mod_position = file_length
                            else:
                                raise ValueError
                        except ValueError, e:
                            pass
                            #logger.fdebug('Error detecting issue # - ignoring this result : '  + str(sf))

                #keep track of where in the original modfilename the positions are in order to check against it for decimal places, etc.
                file_length += len(sf) + 1 #1 for space
                if file_length > len(modfilename):
                    file_length = len(modfilename)

                lastmod_position = self.char_file_position(modfilename, sf, lastmod_position)


            highest_series_pos = len(split_file)
            issue_year = None
            logger.fdebug('datecheck: ' + str(datecheck))
            if len(datecheck) > 0:
                for dc in sorted(datecheck, key=operator.itemgetter('position'), reverse=True):
                    a = self.checkthedate(dc['date'])
                    ab = str(a)
                    sctd = self.checkthedate(str(dt.datetime.now().year))
                    logger.fdebug('sctd: ' + str(sctd))
                    if int(ab) > int(sctd):
                        logger.fdebug('year is in the future, ignoring and assuming part of series title.')
                        yearposition = None
                        yearmodposition = None
                        continue
                    else:
                        issue_year = dc['date']
                        logger.fdebug('year verified as : ' + str(issue_year))
                        if highest_series_pos > dc['position']: highest_series_pos = dc['position']
                        yearposition = dc['position']
                        yearmodposition = dc['mod_position']
                    if len(ab) == 4:
                        issue_year = ab
                        logger.fdebug('year verified as: ' + str(issue_year))
                    else:
                        issue_year = ab
                        logger.fdebug('date verified as: ' + str(issue_year))
                    if highest_series_pos > dc['position']: highest_series_pos = dc['position']
                    yearposition = dc['position']
                    yearmodposition = dc['mod_position']
            else:
                issue_year = None
                yearposition = None
                yearmodposition = None
                logger.fdebug('No year present within title - ignoring as a variable.')

            logger.fdebug('highest_series_position: ' + str(highest_series_pos))

            issue_number = None
            if len(possible_issuenumbers) > 0:
                logger.fdebug('possible_issuenumbers: ' + str(possible_issuenumbers))
                dash_numbers = []
                if len(possible_issuenumbers) > 1:
                    p = 1
                    if '-' not in split_file[0]:
                        finddash = modfilename.find('-')
                        if finddash != -1:
                            logger.fdebug('hyphen located at position: ' + str(finddash))
                            if yearposition:
                                logger.fdebug('yearposition: ' + str(yearposition))
                    else:
                        finddash = -1
                        logger.fdebug('dash is in first word, not considering for determing issue number.')

                    for pis in sorted(possible_issuenumbers, key=operator.itemgetter('position'), reverse=True):
                        a = ' '.join(split_file)
                        lenn = pis['mod_position'] + len(pis['number'])
                        if lenn == len(a):
                            logger.fdebug('Numeric detected as the last digit after a hyphen. Typically this is the issue number.')
                            issue_number = pis['number']
                            logger.fdebug('Issue set to: ' + issue_number)
                            if highest_series_pos > pis['position']: highest_series_pos = pis['position']
                            break
                        if pis['validcountchk'] == True:
                            issue_number = pis['number']
                            logger.fdebug('Issue verified and detected as part of a numeric count sequnce: ' + issue_number)
                            if highest_series_pos > pis['position']: highest_series_pos = pis['position']
                            break
                        if pis['mod_position'] > finddash and finddash != -1:
                            if finddash < yearposition and finddash > (yearmodposition + len(split_file[yearposition])):
                                logger.fdebug('issue number is positioned after a dash - probably not an issue number, but part of an issue title')
                                dash_numbers.append({'mod_position': pis['mod_position'],
                                                     'number':       pis['number'],
                                                     'position':     pis['position']})
                                continue
                        if yearposition == pis['position']:
                            logger.fdebug('Already validated year, ignoring as possible issue number: ' + str(pis['number']))
                            continue
                        if p == 1:
                            issue_number = pis['number']
                            logger.fdebug('issue number :' + issue_number) #(pis)
                            if highest_series_pos > pis['position']: highest_series_pos = pis['position']
                        #else:
                            #logger.fdebug('numeric probably belongs to series title: ' + str(pis))
                        p+=1
                else:
                    issue_number = possible_issuenumbers[0]['number']
                    logger.fdebug('issue verified as : ' + issue_number)
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
                            print 'Issue number re-corrected to : ' + fin_num
                            issue_number = fin_num
                            if highest_series_pos > fin_pos: highest_series_pos = fin_pos


            issue_volume = None
            if len(volume_found) > 0:
                issue_volume = 'v' + str(volume_found['volume'])
                if highest_series_pos != volume_found['position'] + 1 and sep_volume == False:
                    logger.fdebug('Extra item(s) are present between the volume label and the issue number. Checking..')
                    split_file.insert(highest_series_pos-1, split_file.pop(volume_found['position']))
                    logger.fdebug('new split: ' + str(split_file))
                    highest_series_pos = highest_series_pos -1
                else:
                    if highest_series_pos > volume_found['position']: highest_series_pos = volume_found['position']
                logger.fdebug('Volume detected as : ' + issue_volume)

            match_type = None  #folder/file based on how it was matched.

            #logger.fdebug('highest_series_pos is : ' + str(highest_series_pos)
            #here we should account for some characters that get stripped out due to the regex's
            #namely, unique characters - known so far: +
            #c1 = '+'
            series_name = ' '.join(split_file[:highest_series_pos])
            series_name = re.sub('c11', '+', series_name)
            series_name = re.sub('f11', '&', series_name)
            series_name = re.sub('g11', '\'', series_name)
            if series_name.endswith('-'): 
                series_name = series_name[:-1].strip()
            if '\?' in series_name:
                series_name = re.sub('\?', '', series_name).strip()

            logger.fdebug('series title possibly: ' + series_name)

            #check for annual in title(s) here.
            if mylar.ANNUALS_ON:
                if 'annual' in series_name.lower():
                    issue_number = 'Annual ' + str(issue_number)
                    series_name = re.sub('annual', '', series_name, flags=re.I).strip()
            #if path_list is not None:
            #    clocation = os.path.join(path, path_list, filename)
            #else:
            #    clocation = self.dir

            #if issue_number is None:
            #    sntmp = series_name.split()
            #    for sn in sorted(sntmp):
            #        if sn.isdigit():
            #            issue_number = sn
            #            series_name = re.sub(sn, '' , series_name).strip()
            #            break

            if issue_number is None or series_name is None:
                logger.fdebug('Cannot parse the filename properly. I\'m going to make note of this filename so that my evil ruler can make it work.')
                return {'parse_status':   'failure',
                        'sub':            path_list,
                        'comicfilename':  filename,
                        'comiclocation':  self.dir,
                        'series_name':    series_name,
                        'issue_number':   issue_number,
                        'justthedigits':   issue_number, #redundant but it's needed atm
                        'series_volume':  issue_volume,
                        'issue_year':     issue_year,
                        'annual_comicid': None,
                        'scangroup':      scangroup}

            if self.justparse:
                return {'parse_status':   'success',
                        'type':           re.sub('\.','', filetype).strip(),
                        'sub':            path_list,
                        'comicfilename':  filename,
                        'comiclocation':  self.dir,
                        'series_name':    series_name,
                        'series_volume':  issue_volume,
                        'issue_year':     issue_year,
                        'issue_number':   issue_number,
                        'scangroup':      scangroup}

            series_info = {}
            series_info = {'sub':            path_list,
                          'comicfilename':   filename,
                          'comiclocation':   self.dir,
                          'series_name':     series_name,
                          'series_volume':   issue_volume,
                          'issue_year':      issue_year,
                          'issue_number':    issue_number,
                          'scangroup':       scangroup}

            return self.matchIT(series_info)

    def matchIT(self, series_info):
            series_name = series_info['series_name']
            filename = series_info['comicfilename']
            #compare here - match comparison against u_watchcomic.
            logger.info('Series_Name: ' + series_name.lower() + ' --- WatchComic: ' + self.watchcomic.lower())
            #check for dynamic handles here.
            mod_dynamicinfo = self.dynamic_replace(series_name)
            mod_seriesname = mod_dynamicinfo['mod_seriesname'] 
            mod_watchcomic = mod_dynamicinfo['mod_watchcomic'] 

            #remove the spaces...
            nspace_seriesname = re.sub(' ', '', mod_seriesname)
            nspace_watchcomic = re.sub(' ', '', mod_watchcomic)

            if self.AS_Alt != '127372873872871091383 abdkhjhskjhkjdhakajhf':
                logger.fdebug('Possible Alternate Names to match against (if necessary): ' + str(self.AS_Alt))

            justthedigits = series_info['issue_number']

            if mylar.ANNUALS_ON:
                if 'annual' in series_name.lower():
                    justthedigits = 'Annual ' + series_info['issue_number']
                nspace_seriesname = re.sub('annual', '', nspace_seriesname.lower()).strip()

            if re.sub('\|','', nspace_seriesname.lower()).strip() == re.sub('\|', '', nspace_watchcomic.lower()).strip() or any(re.sub('[\|\s]','', x.lower()).strip() == re.sub('[\|\s]','', nspace_seriesname.lower()).strip() for x in self.AS_Alt):
                logger.fdebug('[MATCH: ' + series_info['series_name'] + '] ' + filename)
                enable_annual = False
                annual_comicid = None
                if any(re.sub('[\|\s]','', x.lower()).strip() == re.sub('[\|\s]','', nspace_seriesname.lower()).strip() for x in self.AS_Alt):
                    #if the alternate search name is almost identical, it won't match up because it will hit the 'normal' first.
                    #not important for series' matches, but for annuals, etc it is very important.
                    #loop through the Alternates picking out the ones that match and then do an overall loop.
                    loopchk = [x for x in self.AS_Alt if re.sub('[\|\s]','', x.lower()).strip() == re.sub('[\|\s]','', nspace_seriesname.lower()).strip()]
                    if len(loopchk) > 0 and loopchk[0] != '':
                        if mylar.FOLDER_SCAN_LOG_VERBOSE:
                            logger.fdebug('[FILECHECKER] This should be an alternate: ' + str(loopchk))
                        if 'annual' in series_name.lower():
                            if mylar.FOLDER_SCAN_LOG_VERBOSE:
                                logger.fdebug('[FILECHECKER] Annual detected - proceeding')
                            enable_annual = True

                    else:
                        loopchk = []
                    logger.info('loopchk: ' + str(loopchk))

                    #if the names match up, and enable annuals isn't turned on - keep it all together.
                    if re.sub('\|', '', nspace_watchcomic.lower()).strip() == re.sub('\|', '', nspace_seriesname.lower()).strip() and enable_annual == False:
                        loopchk.append(nspace_watchcomic)
                        if 'annual' in nspace_seriesname.lower():
                            if 'biannual' in nspace_seriesname.lower():
                                if mylar.FOLDER_SCAN_LOG_VERBOSE:
                                    logger.fdebug('[FILECHECKER] BiAnnual detected - wouldn\'t Deadpool be proud?')
                                nspace_seriesname = re.sub('biannual', '', nspace_seriesname).strip()
                                enable_annual = True
                            else:
                                if mylar.FOLDER_SCAN_LOG_VERBOSE:
                                    logger.fdebug('[FILECHECKER] Annual detected - proceeding cautiously.')
                                nspace_seriesname = re.sub('annual', '', nspace_seriesname).strip()
                                enable_annual = False

                    if mylar.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('[FILECHECKER] Complete matching list of names to this file [' + str(len(loopchk)) + '] : ' + str(loopchk))

                    for loopit in loopchk:
                        #now that we have the list of all possible matches for the watchcomic + alternate search names, we go through the list until we find a match.
                        modseries_name = loopit
                        if mylar.FOLDER_SCAN_LOG_VERBOSE:
                            logger.fdebug('[FILECHECKER] AS_Tuple : ' + str(self.AS_Tuple))
                            for ATS in self.AS_Tuple:
                                if mylar.FOLDER_SCAN_LOG_VERBOSE:
                                    logger.fdebug('[FILECHECKER] ' + str(ATS['AS_Alternate']) + ' comparing to ' + nspace_seriesname)
                                if re.sub('\|','', ATS['AS_Alternate'].lower()).strip() == re.sub('\|','', nspace_seriesname.lower()).strip():
                                    if mylar.FOLDER_SCAN_LOG_VERBOSE:
                                        logger.fdebug('[FILECHECKER] Associating ComiciD : ' + str(ATS['ComicID']))
                                    annual_comicid = str(ATS['ComicID'])
                                    modseries_name = ATS['AS_Alternate']
                                    break

                        logger.fdebug('[FILECHECKER] ' + modseries_name + ' - watchlist match on : ' + filename)

                if enable_annual:
                    if annual_comicid is not None:
                       if mylar.FOLDER_SCAN_LOG_VERBOSE:
                           logger.fdebug('enable annual is on')
                           logger.fdebug('annual comicid is ' + str(annual_comicid))
                       if 'biannual' in nspace_watchcomic.lower():
                           if mylar.FOLDER_SCAN_LOG_VERBOSE:
                               logger.fdebug('bi annual detected')
                           justthedigits = 'BiAnnual ' + justthedigits
                       else:
                           if mylar.FOLDER_SCAN_LOG_VERBOSE:
                               logger.fdebug('annual detected')
                           justthedigits = 'Annual ' + justthedigits

                return {'process_status': 'match',
                        'sub':             series_info['sub'],
                        'volume':          series_info['series_volume'],
                        'match_type':      None,  #match_type - will eventually pass if it wasa folder vs. filename match,
                        'comicfilename':   filename,
                        'comiclocation':   series_info['comiclocation'],
                        'series_name':     series_info['series_name'],
                        'series_volume':   series_info['series_volume'],
                        'issue_year':      series_info['issue_year'],
                        'justthedigits':   justthedigits,
                        'annual_comicid':  annual_comicid,
                        'scangroup':       series_info['scangroup']}

            else:
                logger.info('[NO MATCH] ' + filename + ' [WATCHLIST:' + self.watchcomic + ']')
                return {'process_status': 'fail',
                        'comicfilename':  filename,
                        'comiclocation':  series_info['comiclocation'],
                        'series_name':    series_info['series_name'],
                        'issue_number':   series_info['issue_number'],
                        'series_volume':  series_info['series_volume'],
                        'issue_year':     series_info['issue_year'],
                        'scangroup':      series_info['scangroup']}


    def char_file_position(self, file, findchar, lastpos):
        return file.find(findchar, lastpos)

    def traverse_directories(self, dir):
        filelist = []
        comic_ext = ('.cbr','.cbz')

        dir = dir.encode(mylar.SYS_ENCODING)

        for (dirname, subs, files) in os.walk(dir):

            for fname in files:
                if dirname == dir:
                    direc = None
                else:
                    direc = dirname
                    if '.AppleDouble' in direc:
                        #Ignoring MAC OS Finder directory of cached files (/.AppleDouble/<name of file(s)>)
                        continue

                if fname.endswith(comic_ext):
                    if direc is None:
                        comicsize = os.path.getsize(os.path.join(dir, fname))
                    else:
                        comicsize = os.path.getsize(os.path.join(dir, direc, fname))

                    filelist.append({'directory':  direc,   #subdirectory if it exists
                                     'filename':   fname,
                                     'comicsize':  comicsize})

        logger.info('there are ' + str(len(filelist)) + ' files.')

        return filelist

    def dynamic_replace(self, series_name):
        mod_watchcomic = None

        if self.watchcomic:
            watchdynamic_handlers_match = [x for x in self.dynamic_handlers if x.lower() in self.watchcomic.lower()]
            #logger.fdebug('watch dynamic handlers recognized : ' + str(watchdynamic_handlers_match))
            watchdynamic_replacements_match = [x for x in self.dynamic_replacements if x.lower() in self.watchcomic.lower()]
            #logger.fdebug('watch dynamic replacements recognized : ' + str(watchdynamic_replacements_match))
            mod_watchcomic = re.sub('[\s\_\.\s+]', '', self.watchcomic)
            mod_find = []
            wdrm_find = []
            if any([watchdynamic_handlers_match, watchdynamic_replacements_match]):
                for wdhm in watchdynamic_handlers_match:
                    #check the watchcomic
                    #first get the position.
                    mod_find.extend([m.start() for m in re.finditer('\\' + wdhm, mod_watchcomic)])
                    if len(mod_find) > 0:
                        for mf in mod_find:
                            mod_watchcomic = mod_watchcomic[:mf] + '|' + mod_watchcomic[mf+1:]

                for wdrm in watchdynamic_replacements_match:
                    wdrm_find.extend([m.start() for m in re.finditer(wdrm.lower(), mod_watchcomic.lower())])
                    if len(wdrm_find) > 0:
                        for wd in wdrm_find:
                           mod_watchcomic = mod_watchcomic[:wd] + '|' + mod_watchcomic[wd+len(wdrm):]

        seriesdynamic_handlers_match = [x for x in self.dynamic_handlers if x.lower() in series_name.lower()]
        #logger.fdebug('series dynamic handlers recognized : ' + str(seriesdynamic_handlers_match))
        seriesdynamic_replacements_match = [x for x in self.dynamic_replacements if x.lower() in series_name.lower()]
        #logger.fdebug('series dynamic replacements recognized : ' + str(seriesdynamic_replacements_match))
        mod_seriesname = re.sub('[\s\_\.\s+]', '', series_name)
        ser_find = []
        sdrm_find = []
        if any([seriesdynamic_handlers_match, seriesdynamic_replacements_match]):
            for sdhm in seriesdynamic_handlers_match:
                #check the series_name
                ser_find.extend([m.start() for m in re.finditer('\\' + sdhm, mod_seriesname)])
                if len(ser_find) > 0:
                    for sf in ser_find:
                        mod_seriesname = mod_seriesname[:sf] + '|' + mod_seriesname[sf+1:]

            for sdrm in seriesdynamic_replacements_match:
                sdrm_find.extend([m.start() for m in re.finditer(sdrm.lower(), mod_seriesname.lower())])
                if len(sdrm_find) > 0:
                    for sd in sdrm_find:
                        mod_seriesname = mod_seriesname[:sd] + '|' + mod_seriesname[sd+len(sdrm):]

        return {'mod_watchcomic': mod_watchcomic,
                'mod_seriesname': mod_seriesname}

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
                    if mylar.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('as_start: ' + str(as_start) + ' --- ' + str(AS_Alternate[as_start:]))
                    as_end = AS_Alternate.find('##', as_start)
                    if as_end == -1:
                        as_end = len(AS_Alternate)
                    if mylar.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('as_start: ' + str(as_end) + ' --- ' + str(AS_Alternate[as_start:as_end]))
                    AS_ComicID =  AS_Alternate[as_start +2:as_end]
                    if mylar.FOLDER_SCAN_LOG_VERBOSE:
                        logger.fdebug('[FILECHECKER] Extracted comicid for given annual : ' + str(AS_ComicID))
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
    
    def checkthedate(self, txt):
    #    txt='''\
    #    Jan 19, 1990
    #    January 19, 1990
    #    Jan 19,1990
    #    01/19/1990
    #    01/19/90
    #    1990
    #    Jan 1990
    #    January1990'''

        fmts = ('%Y','%b %d, %Y','%b %d, %Y','%B %d, %Y','%B %d %Y','%m/%d/%Y','%m/%d/%y','%b %Y','%B%Y','%b %d,%Y','%m-%Y','%B %Y','%Y-%m-%d','%Y-%m')

        parsed=[]
        for e in txt.splitlines():
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

        dateyear = None

        for t in parsed:
        #    logger.fdebug('"{:20}" => "{:20}" => {}'.format(*t) 
            dateyear = t[2].year
            break

        return dateyear

def validateAndCreateDirectory(dir, create=False, module=None):
    if module is None:
        module = ''
    module += '[DIRECTORY-CHECK]'
    try:
        if os.path.exists(dir):
            logger.info(module + ' Found comic directory: ' + dir)
            return True
        else:
            logger.warn(module + ' Could not find comic directory: ' + dir)
            if create:
                if dir.strip():
                    logger.info(module + ' Creating comic directory (' + str(mylar.CHMOD_DIR) + ') : ' + dir)
                    try:
                        permission = int(mylar.CHMOD_DIR, 8)
                        os.umask(0) # this is probably redudant, but it doesn't hurt to clear the umask here.
                        os.makedirs(dir.rstrip(), permission)
                        setperms(dir.rstrip(), True)
                    except OSError as e:
                        logger.warn(module + ' Could not create directory: ' + dir + '[' + str(e) + ']. Aborting.')
                        return False
                    else:
                        return True
                else:
                    logger.warn(module + ' Provided directory [' + dir + '] is blank. Aborting.')
                    return False
    except OSError as e:
        logger.warn(module + ' Could not create directory: ' + dir + '[' + str(e) + ']. Aborting.')
        return False
    return False

def setperms(path, dir=False):

    if 'windows' not in mylar.OS_DETECT.lower():

        try:
            os.umask(0) # this is probably redudant, but it doesn't hurt to clear the umask here.
            if mylar.CHGROUP:
                if mylar.CHOWNER is None or mylar.CHOWNER == 'None' or mylar.CHOWNER == '':
                    import getpass
                    mylar.CHOWNER = getpass.getuser()

                if not mylar.CHOWNER.isdigit():
                    from pwd import getpwnam
                    chowner = getpwnam(mylar.CHOWNER)[2]
                else:
                    chowner = mylar.CHOWNER

                if not mylar.CHGROUP.isdigit():
                    from grp import getgrnam
                    chgroup = getgrnam(mylar.CHGROUP)[2]
                else:
                    chgroup = mylar.CHGROUP

                if dir:
                    permission = int(mylar.CHMOD_DIR, 8)
                    os.chmod(path, permission)
                    os.chown(path, chowner, chgroup)
                else:
                    for root, dirs, files in os.walk(path):
                        for momo in dirs:
                            permission = int(mylar.CHMOD_DIR, 8)
                            os.chown(os.path.join(root, momo), chowner, chgroup)
                            os.chmod(os.path.join(root, momo), permission)
                        for momo in files:
                            permission = int(mylar.CHMOD_FILE, 8)
                            os.chown(os.path.join(root, momo), chowner, chgroup)
                            os.chmod(os.path.join(root, momo), permission)

                logger.fdebug('Successfully changed ownership and permissions [' + str(mylar.CHOWNER) + ':' + str(mylar.CHGROUP) + '] / [' + str(mylar.CHMOD_DIR) + ' / ' + str(mylar.CHMOD_FILE) + ']')

            else:
                for root, dirs, files in os.walk(path):
                    for momo in dirs:
                        permission = int(mylar.CHMOD_DIR, 8)
                        os.chmod(os.path.join(root, momo), permission)
                    for momo in files:
                        permission = int(mylar.CHMOD_FILE, 8)
                        os.chmod(os.path.join(root, momo), permission)

                logger.fdebug('Successfully changed permissions [' + str(mylar.CHMOD_DIR) + ' / ' + str(mylar.CHMOD_FILE) + ']')

        except OSError:
            logger.error('Could not change permissions : ' + path + '. Exiting...')

    return


#if __name__ == '__main__':
#    test = FileChecker()
#    test.getlist()


