#  This file is part of Mylar.
# -*- coding: utf-8 -*-
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

import time
from operator import itemgetter
import datetime
from datetime import timedelta, date
import subprocess
import shlex
import json
import re
import sys
import platform
import itertools
import shutil
import os, errno
import mylar
import logger

def multikeysort(items, columns):

    comparers = [((itemgetter(col[1:].strip()), -1) if col.startswith('-') else (itemgetter(col.strip()), 1)) for col in columns]

    def comparer(left, right):
        for fn, mult in comparers:
            result = cmp(fn(left), fn(right))
            if result:
                return mult * result
        else:
            return 0

    return sorted(items, cmp=comparer)

def checked(variable):
    if variable:
        return 'Checked'
    else:
        return ''

def radio(variable, pos):

    if variable == pos:
        return 'Checked'
    else:
        return ''

def latinToAscii(unicrap):
    """
    From couch potato
    """
    xlate = {0xc0: 'A', 0xc1: 'A', 0xc2: 'A', 0xc3: 'A', 0xc4: 'A', 0xc5: 'A',
        0xc6: 'Ae', 0xc7: 'C',
        0xc8: 'E', 0xc9: 'E', 0xca: 'E', 0xcb: 'E', 0x86: 'e',
        0xcc: 'I', 0xcd: 'I', 0xce: 'I', 0xcf: 'I',
        0xd0: 'Th', 0xd1: 'N',
        0xd2: 'O', 0xd3: 'O', 0xd4: 'O', 0xd5: 'O', 0xd6: 'O', 0xd8: 'O',
        0xd9: 'U', 0xda: 'U', 0xdb: 'U', 0xdc: 'U',
        0xdd: 'Y', 0xde: 'th', 0xdf: 'ss',
        0xe0: 'a', 0xe1: 'a', 0xe2: 'a', 0xe3: 'a', 0xe4: 'a', 0xe5: 'a',
        0xe6: 'ae', 0xe7: 'c',
        0xe8: 'e', 0xe9: 'e', 0xea: 'e', 0xeb: 'e', 0x0259: 'e',
        0xec: 'i', 0xed: 'i', 0xee: 'i', 0xef: 'i',
        0xf0: 'th', 0xf1: 'n',
        0xf2: 'o', 0xf3: 'o', 0xf4: 'o', 0xf5: 'o', 0xf6: 'o', 0xf8: 'o',
        0xf9: 'u', 0xfa: 'u', 0xfb: 'u', 0xfc: 'u',
        0xfd: 'y', 0xfe: 'th', 0xff: 'y',
        0xa1: '!', 0xa2: '{cent}', 0xa3: '{pound}', 0xa4: '{currency}',
        0xa5: '{yen}', 0xa6: '|', 0xa7: '{section}', 0xa8: '{umlaut}',
        0xa9: '{C}', 0xaa: '{^a}', 0xab: '<<', 0xac: '{not}',
        0xad: '-', 0xae: '{R}', 0xaf: '_', 0xb0: '{degrees}',
        0xb1: '{+/-}', 0xb2: '{^2}', 0xb3: '{^3}', 0xb4: "'",
        0xb5: '{micro}', 0xb6: '{paragraph}', 0xb7: '*', 0xb8: '{cedilla}',
        0xb9: '{^1}', 0xba: '{^o}', 0xbb: '>>',
        0xbc: '{1/4}', 0xbd: '{1/2}', 0xbe: '{3/4}', 0xbf: '?',
        0xd7: '*', 0xf7: '/'
        }

    r = ''
    for i in unicrap:
        if xlate.has_key(ord(i)):
            r += xlate[ord(i)]
        elif ord(i) >= 0x80:
            pass
        else:
            r += str(i)
    return r

def convert_milliseconds(ms):

    seconds = ms /1000
    gmtime = time.gmtime(seconds)
    if seconds > 3600:
        minutes = time.strftime("%H:%M:%S", gmtime)
    else:
        minutes = time.strftime("%M:%S", gmtime)

    return minutes

def convert_seconds(s):

    gmtime = time.gmtime(s)
    if s > 3600:
        minutes = time.strftime("%H:%M:%S", gmtime)
    else:
        minutes = time.strftime("%M:%S", gmtime)

    return minutes

def today():
    today = datetime.date.today()
    yyyymmdd = datetime.date.isoformat(today)
    return yyyymmdd

def now():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

def bytes_to_mb(bytes):

    mb = int(bytes) /1048576
    size = '%.1f MB' % mb
    return size

def human_size(size_bytes):
    """
    format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
    Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
    e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
    """
    if size_bytes == 1:
        # because I really hate unnecessary plurals
        return "1 byte"

    suffixes_table = [('bytes', 0), ('KB', 0), ('MB', 1), ('GB', 2), ('TB', 2), ('PB', 2)]

    num = float(0 if size_bytes is None else size_bytes)
    for suffix, precision in suffixes_table:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s %s" % (formatted_size, suffix)

def human2bytes(s):
    """
    >>> human2bytes('1M')
    1048576
    >>> human2bytes('1G')
    1073741824
    """
    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    letter = s[-1:].strip().upper()
    num = re.sub(',', '', s[:-1])
    #assert num.isdigit() and letter in symbols
    #use below assert statement to handle sizes with decimal places
    assert float(num) and letter in symbols
    num = float(num)
    prefix = {symbols[0]: 1}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i +1) *10
    return int(num * prefix[letter])

def replace_all(text, dic):
    for i, j in dic.iteritems():
        text = text.replace(i, j)
    return text.rstrip()

def cleanName(string):

    pass1 = latinToAscii(string).lower()
    out_string = re.sub('[\/\@\#\$\%\^\*\+\"\[\]\{\}\<\>\=\_]', ' ', pass1).encode('utf-8')

    return out_string

def cleanTitle(title):

    title = re.sub('[\.\-\/\_]', ' ', title).lower()

    # Strip out extra whitespace
    title = ' '.join(title.split())

    title = title.title()

    return title

def extract_logline(s):
    # Default log format
    pattern = re.compile(r'(?P<timestamp>.*?)\s\-\s(?P<level>.*?)\s*\:\:\s(?P<thread>.*?)\s\:\s(?P<message>.*)', re.VERBOSE)
    match = pattern.match(s)
    if match:
        timestamp = match.group("timestamp")
        level = match.group("level")
        thread = match.group("thread")
        message = match.group("message")
        return (timestamp, level, thread, message)
    else:
        return None

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def decimal_issue(iss):
    iss_find = iss.find('.')
    dec_except = None
    if iss_find == -1:
        #no matches for a decimal, assume we're converting from decimal to int.
        #match for special issues with alphanumeric numbering...
        if 'au' in iss.lower():
            dec_except = 'AU'
            decex = iss.lower().find('au')
            deciss = int(iss[:decex]) * 1000
        else:
            deciss = int(iss) * 1000
    else:
        iss_b4dec = iss[:iss_find]
        iss_decval = iss[iss_find +1:]
        if int(iss_decval) == 0:
            iss = iss_b4dec
            issdec = int(iss_decval)
        else:
            if len(iss_decval) == 1:
                iss = iss_b4dec + "." + iss_decval
                issdec = int(iss_decval) * 10
            else:
                iss = iss_b4dec + "." + iss_decval.rstrip('0')
                issdec = int(iss_decval.rstrip('0')) * 10
        deciss = (int(iss_b4dec) * 1000) + issdec
    return deciss, dec_except

def rename_param(comicid, comicname, issue, ofilename, comicyear=None, issueid=None, annualize=None, arc=False):
            import db, logger
            myDB = db.DBConnection()
            comicid = str(comicid)   # it's coming in unicoded...

            logger.fdebug(type(comicid))
            logger.fdebug(type(issueid))
            logger.fdebug(type(issue))
            logger.fdebug('comicid: ' + comicid)
            logger.fdebug('issue#: ' + issue)
            # the issue here is a non-decimalized version, we need to see if it's got a decimal and if not, add '.00'
#            iss_find = issue.find('.')
#            if iss_find < 0:
#                # no decimal in issue number
#                iss = str(int(issue)) + ".00"
#            else:
#                iss_b4dec = issue[:iss_find]
#                iss_decval = issue[iss_find+1:]
#                if len(str(int(iss_decval))) == 1:
#                    iss = str(int(iss_b4dec)) + "." + str(int(iss_decval)*10)
#                else:
#                    if issue.endswith(".00"):
#                        iss = issue
#                    else:
#                        iss = str(int(iss_b4dec)) + "." + iss_decval
#            issue = iss

#            print ("converted issue#: " + str(issue))
            logger.fdebug('issueid:' + str(issueid))

            if issueid is None:
                logger.fdebug('annualize is ' + str(annualize))
                if arc:
                    #this has to be adjusted to be able to include story arc issues that span multiple arcs
                    chkissue = myDB.selectone("SELECT * from readinglist WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()
                else:
                    if all([annualize is None, not mylar.ANNUALS_ON]):
                        chkissue = myDB.selectone("SELECT * from issues WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()
                    else:
                        chkissue = myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()

                if chkissue is None:
                    #rechk chkissue against int value of issue #
                    if arc:
                        chkissue = myDB.selectone("SELECT * from readinglist WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issuedigits(issue)]).fetchone()
                    else:
                        chkissue = myDB.selectone("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issuedigits(issue)]).fetchone()
                        if all([annualize == 'yes', mylar.ANNUALS_ON]):
                            chkissue = myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issuedigits(issue)]).fetchone()

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
                issuenzb = myDB.selectone("SELECT * from readinglist WHERE ComicID=? AND IssueID=? AND StoryArc=?", [comicid, issueid, arc]).fetchone()
            else:
                issuenzb = myDB.selectone("SELECT * from issues WHERE ComicID=? AND IssueID=?", [comicid, issueid]).fetchone()
                if issuenzb is None:
                    logger.fdebug('not an issue, checking against annuals')
                    issuenzb = myDB.selectone("SELECT * from annuals WHERE ComicID=? AND IssueID=?", [comicid, issueid]).fetchone()
                    if issuenzb is None:
                        logger.fdebug('Unable to rename - cannot locate issue id within db')
                        return
                    else:
                        annualize = True

            if issuenzb is None:
                logger.fdebug('Unable to rename - cannot locate issue id within db')
                return

            #remap the variables to a common factor.
            if arc:
                issuenum = issuenzb['IssueNumber']
                issuedate = issuenzb['IssueDate']
                publisher = issuenzb['IssuePublisher']
                series = issuenzb['ComicName']
                seriesfilename = series   #Alternate FileNaming is not available with story arcs.
                seriesyear = issuenzb['SeriesYear']
                arcdir = filesafe(issuenzb['StoryArc'])
                if mylar.REPLACE_SPACES:
                    arcdir = arcdir.replace(' ', mylar.REPLACE_CHAR)
                if mylar.STORYARCDIR:
                    storyarcd = os.path.join(mylar.DESTINATION_DIR, "StoryArcs", arcdir)
                    logger.fdebug('Story Arc Directory set to : ' + storyarcd)
                else:
                    logger.fdebug('Story Arc Directory set to : ' + mylar.GRABBAG_DIR)
                    storyarcd = os.path.join(mylar.DESTINATION_DIR, mylar.GRABBAG_DIR)

                comlocation = storyarcd
                comversion = None   #need to populate this.

            else:
                issuenum = issuenzb['Issue_Number']
                issuedate = issuenzb['IssueDate']
                comicnzb= myDB.selectone("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
                publisher = comicnzb['ComicPublisher']
                series = comicnzb['ComicName']
                if comicnzb['AlternateFileName'] is None or comicnzb['AlternateFileName'] == 'None':
                    seriesfilename = series
                else:
                    seriesfilename = comicnzb['AlternateFileName']
                    logger.fdebug('Alternate File Naming has been enabled for this series. Will rename series title to : ' + seriesfilename)
                seriesyear = comicnzb['ComicYear']
                comlocation = comicnzb['ComicLocation']
                comversion = comicnzb['ComicVersion']

            #comicid = issuenzb['ComicID']
            #issueno = str(issuenum).split('.')[0]
            issue_except = 'None'
            issue_exceptions = ['AU',
                                'INH',
                                'NOW',
                                'AI',
                                'MU',
                                'A',
                                'B',
                                'C',
                                'X',
                                'O']
            valid_spaces = ('.', '-')
            for issexcept in issue_exceptions:
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
                iss_decval = issuenum[iss_find +1:]
                if iss_decval.endswith('.'):
                    iss_decval = iss_decval[:-1]
                if int(iss_decval) == 0:
                    iss = iss_b4dec
                    issdec = int(iss_decval)
                    issueno = str(iss)
                    logger.fdebug('Issue Number: ' + str(issueno))
                else:
                    if len(iss_decval) == 1:
                        iss = iss_b4dec + "." + iss_decval
                        issdec = int(iss_decval) * 10
                    else:
                        iss = iss_b4dec + "." + iss_decval.rstrip('0')
                        issdec = int(iss_decval.rstrip('0')) * 10
                    issueno = iss_b4dec
                    logger.fdebug('Issue Number: ' + str(iss))
            else:
                iss = issuenum
                issueno = str(iss)
            logger.fdebug('iss:' + iss)
            logger.fdebug('issueno:' + str(issueno))
            # issue zero-suppression here
            if mylar.ZERO_LEVEL == "0":
                zeroadd = ""
            else:
                if mylar.ZERO_LEVEL_N  == "none": zeroadd = ""
                elif mylar.ZERO_LEVEL_N == "0x": zeroadd = "0"
                elif mylar.ZERO_LEVEL_N == "00x": zeroadd = "00"

            logger.fdebug('Zero Suppression set to : ' + str(mylar.ZERO_LEVEL_N))
            prettycomiss = None

            if issueno.isalpha():
                logger.fdebug('issue detected as an alpha.')
                prettycomiss = str(issueno)
            else:
                try:
                    x = float(issueno)
                    #validity check
                    if x < 0:
                        logger.info('I\'ve encountered a negative issue #: ' + str(issueno) + '. Trying to accomodate.')
                        prettycomiss = '-' + str(zeroadd) + str(issueno[1:])
                    elif x >= 0:
                        pass
                    else:
                        raise ValueError
                except ValueError, e:
                    logger.warn('Unable to properly determine issue number [' + str(issueno) + '] - you should probably log this on github for help.')
                    return

            if prettycomiss is None and len(str(issueno)) > 0:
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
                    logger.fdebug('Zero level supplement set to ' + str(mylar.ZERO_LEVEL_N) + '. Issue will be set as : ' + str(prettycomiss))
                elif int(issueno) >= 10 and int(issueno) < 100:
                    logger.fdebug('issue detected greater than 10, but less than 100')
                    if mylar.ZERO_LEVEL_N == "none":
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
                    logger.fdebug('Zero level supplement set to ' + str(mylar.ZERO_LEVEL_N) + '.Issue will be set as : ' + str(prettycomiss))
                else:
                    logger.fdebug('issue detected greater than 100')
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                    prettycomiss = str(issueno)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('Zero level supplement set to ' + str(mylar.ZERO_LEVEL_N) + '. Issue will be set as : ' + str(prettycomiss))
            elif len(str(issueno)) == 0:
                prettycomiss = str(issueno)
                logger.fdebug('issue length error - cannot determine length. Defaulting to None:  ' + str(prettycomiss))

            logger.fdebug('Pretty Comic Issue is : ' + str(prettycomiss))
            issueyear = issuedate[:4]
            month = issuedate[5:7].replace('-', '').strip()
            month_name = fullmonth(month)
            if month_name is None:
                month_name = 'None'
            logger.fdebug('Issue Year : ' + str(issueyear))
            logger.fdebug('Publisher: ' + publisher)
            logger.fdebug('Series: ' + series)
            logger.fdebug('Year: '  + str(seriesyear))
            logger.fdebug('Comic Location: ' + comlocation)
            if comversion is None:
                comversion = 'None'
            #if comversion is None, remove it so it doesn't populate with 'None'
            if comversion == 'None':
                chunk_f_f = re.sub('\$VolumeN', '', mylar.FILE_FORMAT)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug('No version # found for series, removing from filename')
                logger.fdebug("new format: " + str(chunk_file_format))
            else:
                chunk_file_format = mylar.FILE_FORMAT

            if annualize is None:
                chunk_f_f = re.sub('\$Annual', '', chunk_file_format)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug('not an annual - removing from filename paramaters')
                logger.fdebug('new format: ' + str(chunk_file_format))

            else:
                logger.fdebug('chunk_file_format is: ' + str(chunk_file_format))
                if mylar.ANNUALS_ON:
                    if 'annual' in series.lower():
                        if '$Annual' not in chunk_file_format: # and 'annual' not in ofilename.lower():
                        #if it's an annual, but $annual isn't specified in file_format, we need to
                        #force it in there, by default in the format of $Annual $Issue
                            #prettycomiss = "Annual " + str(prettycomiss)
                            logger.fdebug('[' + series + '][ANNUALS-ON][ANNUAL IN SERIES][NOT $ANNUAL] prettycomiss: ' + str(prettycomiss))
                        else:
                            #because it exists within title, strip it then use formatting tag for placement of wording.
                            chunk_f_f = re.sub('\$Annual', '', chunk_file_format)
                            chunk_f = re.compile(r'\s+')
                            chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                            logger.fdebug('[' + series + '][ANNUALS-ON][ANNUAL IN SERIES][$ANNUAL] prettycomiss: ' + str(prettycomiss))
                    else:
                        if '$Annual' not in chunk_file_format: # and 'annual' not in ofilename.lower():
                        #if it's an annual, but $annual isn't specified in file_format, we need to
                        #force it in there, by default in the format of $Annual $Issue
                            prettycomiss = "Annual " + str(prettycomiss)
                            logger.fdebug('[' + series + '][ANNUALS-ON][ANNUAL NOT IN SERIES][NOT $ANNUAL] prettycomiss: ' + str(prettycomiss))
                        else:
                            logger.fdebug('[' + series + '][ANNUALS-ON][ANNUAL NOT IN SERIES][$ANNUAL] prettycomiss: ' + str(prettycomiss))

                else:
                    #if annuals aren't enabled, then annuals are being tracked as independent series.
                    #annualize will be true since it's an annual in the seriesname.
                    if 'annual' in series.lower():
                        if '$Annual' not in chunk_file_format: # and 'annual' not in ofilename.lower():
                        #if it's an annual, but $annual isn't specified in file_format, we need to
                        #force it in there, by default in the format of $Annual $Issue
                            #prettycomiss = "Annual " + str(prettycomiss)
                            logger.fdebug('[' + series + '][ANNUALS-OFF][ANNUAL IN SERIES][NOT $ANNUAL] prettycomiss: ' + str(prettycomiss))
                        else:
                            #because it exists within title, strip it then use formatting tag for placement of wording.
                            chunk_f_f = re.sub('\$Annual', '', chunk_file_format)
                            chunk_f = re.compile(r'\s+')
                            chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                            logger.fdebug('[' + series + '][ANNUALS-OFF][ANNUAL IN SERIES][$ANNUAL] prettycomiss: ' + str(prettycomiss))
                    else:
                        if '$Annual' not in chunk_file_format: # and 'annual' not in ofilename.lower():
                            #if it's an annual, but $annual isn't specified in file_format, we need to
                            #force it in there, by default in the format of $Annual $Issue
                            prettycomiss = "Annual " + str(prettycomiss)
                            logger.fdebug('[' + series + '][ANNUALS-OFF][ANNUAL NOT IN SERIES][NOT $ANNUAL] prettycomiss: ' + str(prettycomiss))
                        else:
                            logger.fdebug('[' + series + '][ANNUALS-OFF][ANNUAL NOT IN SERIES][$ANNUAL] prettycomiss: ' + str(prettycomiss))


                    logger.fdebug('Annual detected within series title of ' + series + '. Not auto-correcting issue #')

            seriesfilename = seriesfilename.encode('ascii', 'ignore').strip()
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
                           '$Annual':    'Annual'
                          }

            extensions = ('.cbr', '.cbz', '.cb7')

            if ofilename.lower().endswith(extensions):
                path, ext = os.path.splitext(ofilename)

            if mylar.FILE_FORMAT == '':
                logger.fdebug('Rename Files is not enabled - keeping original filename.')
                #check if extension is in nzb_name - will screw up otherwise
                if ofilename.lower().endswith(extensions):
                    nfilename = ofilename[:-4]
                else:
                    nfilename = ofilename
            else:
                nfilename = replace_all(chunk_file_format, file_values)
                if mylar.REPLACE_SPACES:
                    #mylar.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                    nfilename = nfilename.replace(' ', mylar.REPLACE_CHAR)

            nfilename = re.sub('[\,\:]', '', nfilename) + ext.lower()
            logger.fdebug('New Filename: ' + nfilename)

            if mylar.LOWERCASE_FILENAMES:
                dst = os.path.join(comlocation, nfilename.lower())
            else:
                dst = os.path.join(comlocation, nfilename)

            logger.fdebug('Source: ' + ofilename)
            logger.fdebug('Destination: ' + dst)

            rename_this = {"destination_dir": dst,
                            "nfilename": nfilename,
                            "issueid": issueid,
                            "comicid": comicid}

            return rename_this


def apiremove(apistring, type):
    if type == 'nzb':
        value_regex = re.compile("(?<=apikey=)(?P<value>.*?)(?=$)")
        #match = value_regex.search(apistring)
        apiremoved = value_regex.sub("xUDONTNEEDTOKNOWTHISx", apistring)
    else:
        #type = $ to denote end of string
        #type = & to denote up until next api variable
        value_regex = re.compile("(?<=%26i=1%26r=)(?P<value>.*?)(?=" + str(type) +")")
        #match = value_regex.search(apistring)
        apiremoved = value_regex.sub("xUDONTNEEDTOKNOWTHISx", apistring)

    #need to remove the urlencoded-portions as well in future
    return apiremoved

def remove_apikey(payd, key):
        #payload = some dictionary with payload values
        #key = the key to replace with REDACTED (normally apikey)
    for k,v in payd.items():
        payd[key] = 'REDACTED'

    return payd

def ComicSort(comicorder=None, sequence=None, imported=None):
    if sequence:
        # if it's on startup, load the sql into a tuple for use to avoid record-locking
        i = 0
        import db, logger
        myDB = db.DBConnection()
        comicsort = myDB.select("SELECT * FROM comics ORDER BY ComicSortName COLLATE NOCASE")
        comicorderlist = []
        comicorder = {}
        comicidlist = []
        if sequence == 'update':
            mylar.COMICSORT['SortOrder'] = None
            mylar.COMICSORT['LastOrderNo'] = None
            mylar.COMICSORT['LastOrderID'] = None
        for csort in comicsort:
            if csort['ComicID'] is None: pass
            if not csort['ComicID'] in comicidlist:
                if sequence == 'startup':
                    comicorderlist.append({
                         'ComicID':             csort['ComicID'],
                         'ComicOrder':           i
                         })
                elif sequence == 'update':
                    comicorderlist.append({
#                    mylar.COMICSORT['SortOrder'].append({
                         'ComicID':             csort['ComicID'],
                         'ComicOrder':           i
                         })

                comicidlist.append(csort['ComicID'])
                i+=1
        if sequence == 'startup':
            if i == 0:
                comicorder['SortOrder'] = ({'ComicID': '99999', 'ComicOrder': 1})
                comicorder['LastOrderNo'] = 1
                comicorder['LastOrderID'] = 99999
            else:
                comicorder['SortOrder'] = comicorderlist
                comicorder['LastOrderNo'] = i -1
                comicorder['LastOrderID'] = comicorder['SortOrder'][i -1]['ComicID']
            if i < 0: i == 0
            logger.info('Sucessfully ordered ' + str(i -1) + ' series in your watchlist.')
            return comicorder
        elif sequence == 'update':
            mylar.COMICSORT['SortOrder'] = comicorderlist
            #print ("i:" + str(i))
            if i == 0:
                placemnt = 1
            else:
                placemnt = int(i -1)
            mylar.COMICSORT['LastOrderNo'] = placemnt
            mylar.COMICSORT['LastOrderID'] = mylar.COMICSORT['SortOrder'][placemnt]['ComicID']
            return
    else:
        # for new series adds, we already know the comicid, so we set the sortorder to an abnormally high #
        # we DO NOT write to the db to avoid record-locking.
        # if we get 2 999's we're in trouble though.
        sortedapp = []
        if comicorder['LastOrderNo'] == '999':
            lastorderval = int(comicorder['LastOrderNo']) + 1
        else:
            lastorderval = 999
        sortedapp.append({
             'ComicID':             imported,
             'ComicOrder':           lastorderval
             })
        mylar.COMICSORT['SortOrder'] = sortedapp
        mylar.COMICSORT['LastOrderNo'] = lastorderval
        mylar.COMICSORT['LastOrderID'] = imported
        return

def fullmonth(monthno):
    #simple numerical to worded month conversion....
    basmonths = {'1': 'January', '2': 'February', '3': 'March', '4': 'April', '5': 'May', '6': 'June', '7': 'July', '8': 'August', '9': 'September', '10': 'October', '11': 'November', '12': 'December'}

    monthconv = None

    for numbs in basmonths:
        if numbs in str(int(monthno)):
            monthconv = basmonths[numbs]

    return monthconv

def updateComicLocation():
    #in order for this to work, the ComicLocation MUST be left at the original location.
    #in the config.ini - set LOCMOVE = 1  (to enable this to run on the NEXT startup)
    #                  - set NEWCOMDIR = new ComicLocation
    #after running, set ComicLocation to new location in Configuration GUI

    import db, logger
    myDB = db.DBConnection()
    if mylar.NEWCOM_DIR is not None:
        logger.info('Performing a one-time mass update to Comic Location')
        #create the root dir if it doesn't exist
        checkdirectory = mylar.filechecker.validateAndCreateDirectory(mylar.NEWCOM_DIR, create=True)
        if not checkdirectory:
            logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
            return
        dirlist = myDB.select("SELECT * FROM comics")
        comloc = []

        if dirlist is not None:
            for dl in dirlist:

                u_comicnm = dl['ComicName']
                # let's remove the non-standard characters here that will break filenaming / searching.
                comicname_folder = filesafe(u_comicnm)

                publisher = re.sub('!', '', dl['ComicPublisher']) # thanks Boom!
                year = dl['ComicYear']
                comversion = dl['ComicVersion']
                if comversion is None:
                    comversion = 'None'
                #if comversion is None, remove it so it doesn't populate with 'None'
                if comversion == 'None':
                    chunk_f_f = re.sub('\$VolumeN', '', mylar.FOLDER_FORMAT)
                    chunk_f = re.compile(r'\s+')
                    folderformat = chunk_f.sub(' ', chunk_f_f)
                else:
                    folderformat = mylar.FOLDER_FORMAT

                #do work to generate folder path

                values = {'$Series':        comicname_folder,
                          '$Publisher':     publisher,
                          '$Year':          year,
                          '$series':        comicname_folder.lower(),
                          '$publisher':     publisher.lower(),
                          '$VolumeY':       'V' + str(year),
                          '$VolumeN':       comversion,
                          '$Annual':        'Annual'
                          }

                #set the paths here with the seperator removed allowing for cross-platform altering.
                ccdir = re.sub(r'[\\|/]', '%&', mylar.NEWCOM_DIR)
                ddir = re.sub(r'[\\|/]', '%&', mylar.DESTINATION_DIR)
                dlc = re.sub(r'[\\|/]', '%&', dl['ComicLocation'])

                if mylar.FFTONEWCOM_DIR:
                    #if this is enabled (1) it will apply the Folder_Format to all the new dirs
                    if mylar.FOLDER_FORMAT == '':
                        comlocation = re.sub(ddir, ccdir, dlc).strip()
                    else:
                        first = replace_all(folderformat, values)
                        if mylar.REPLACE_SPACES:
                            #mylar.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                            first = first.replace(' ', mylar.REPLACE_CHAR)
                        comlocation = os.path.join(mylar.NEWCOM_DIR, first).strip()

                else:
                    #DESTINATION_DIR = /mnt/mediavg/Comics
                    #NEWCOM_DIR = /mnt/mediavg/Comics/Comics-1
                    #dl['ComicLocation'] = /mnt/mediavg/Comics/Batman-(2011)
                    comlocation = re.sub(ddir, ccdir, dlc).strip()

                #regenerate the new path location so that it's os.dependent now.
                com_done = re.sub('%&', os.sep.encode('unicode-escape'), comlocation).strip()

                comloc.append({"comlocation":  com_done,
                               "origlocation": dl['ComicLocation'],
                               "comicid":      dl['ComicID']})

            if len(comloc) > 0:
                #give the information about what we're doing.
                if mylar.FFTONEWCOM_DIR:
                    logger.info('FFTONEWCOM_DIR is enabled. Applying the existing folder format to ALL directories regardless of existing location paths')
                else:
                    logger.info('FFTONEWCOM_DIR is not enabled. I will keep existing subdirectory paths, and will only change the actual Comic Location in the path.')
                    logger.fdebug(' (ie. /mnt/Comics/Marvel/Hush-(2012) to /mnt/mynewLocation/Marvel/Hush-(2012) ')

                #do the deed.
                for cl in comloc:
                    ctrlVal = {"ComicID":      cl['comicid']}
                    newVal = {"ComicLocation": cl['comlocation']}
                    myDB.upsert("Comics", newVal, ctrlVal)
                    logger.fdebug('Updated : ' + cl['origlocation'] + ' .: TO :. ' + cl['comlocation'])
                logger.info('Updated ' + str(len(comloc)) + ' series to a new Comic Location as specified in the config.ini')
            else:
                logger.fdebug('Failed in updating the Comic Locations. Check Folder Format string and/or log the issue.')
        else:
            logger.info('There are no series in your watchlist to Update the locations. Not updating anything at this time.')
        #set the value to 0 here so we don't keep on doing this...
        mylar.LOCMOVE = 0
        mylar.config_write()
    else:
        logger.info('No new ComicLocation path specified - not updating. Set NEWCOMD_DIR in config.ini')
        #raise cherrypy.HTTPRedirect("config")
    return

def cleanhtml(raw_html):
    #cleanr = re.compile('<.*?>')
    #cleantext = re.sub(cleanr, '', raw_html)
    #return cleantext
    from bs4 import BeautifulSoup

    VALID_TAGS = ['div', 'p']

    soup = BeautifulSoup(raw_html)

    for tag in soup.findAll('p'):
        if tag.name not in VALID_TAGS:
            tag.replaceWith(tag.renderContents())
    flipflop = soup.renderContents()
    print flipflop
    return flipflop


def issuedigits(issnum):
    import db, logger

    int_issnum = None

    try:
        tst = issnum.isdigit()
    except:
        try:
            isstest = str(issnum)
            tst = isstest.isdigit()
        except:
            return 9999999999
        else:
            issnum = str(issnum)

    if issnum.isdigit():
        int_issnum = int(issnum) * 1000
    else:
        #count = 0
        #for char in issnum:
        #    if char.isalpha():
        #        count += 1
        #if count > 5:
        #    logger.error('This is not an issue number - not enough numerics to parse')
        #    int_issnum = 999999999999999
        #    return int_issnum
        try:
            if 'au' in issnum.lower() and issnum[:1].isdigit():
                int_issnum = (int(issnum[:-2]) * 1000) + ord('a') + ord('u')
            elif 'ai' in issnum.lower() and issnum[:1].isdigit():
                int_issnum = (int(issnum[:-2]) * 1000) + ord('a') + ord('i')
            elif 'inh' in issnum.lower() or 'now' in issnum.lower():
                remdec = issnum.find('.')  #find the decimal position.
                if remdec == -1:
                #if no decimal, it's all one string
                #remove the last 3 characters from the issue # (INH)
                    int_issnum = (int(issnum[:-3]) * 1000) + ord('i') + ord('n') + ord('h')
                else:
                    int_issnum = (int(issnum[:-4]) * 1000) + ord('i') + ord('n') + ord('h')
            elif 'now' in issnum.lower():
                if '!' in issnum: issnum = re.sub('\!', '', issnum)
                remdec = issnum.find('.')  #find the decimal position.
                if remdec == -1:
                #if no decimal, it's all one string
                #remove the last 3 characters from the issue # (NOW)
                    int_issnum = (int(issnum[:-3]) * 1000) + ord('n') + ord('o') + ord('w')
                else:
                    int_issnum = (int(issnum[:-4]) * 1000) + ord('n') + ord('o') + ord('w')
            elif 'mu' in issnum.lower():
                remdec = issnum.find('.')
                if remdec == -1:
                    int_issnum = (int(issnum[:-2]) * 1000) + ord('m') + ord('u')
                else:
                    int_issnum = (int(issnum[:-3]) * 1000) + ord('m') + ord('u')

        except ValueError as e:
            logger.error('[' + issnum + '] Unable to properly determine the issue number. Error: %s', e)
            return 9999999999

        if int_issnum is not None:
            return int_issnum

        #try:
        #    issnum.decode('ascii')
        #    logger.fdebug('ascii character.')
        #except:
        #    logger.fdebug('Unicode character detected: ' + issnum)
        #else: issnum.decode(mylar.SYS_ENCODING).decode('utf-8')
        if type(issnum) == str:
            try:
                issnum = issnum.decode('utf-8')
            except:
                issnum = issnum.decode('windows-1252')

        if type(issnum) == unicode:
            vals = {u'\xbd':.5,u'\xbc':.25,u'\xbe':.75,u'\u221e':9999999999,u'\xe2':9999999999}
        else:
            vals = {'\xbd':.5,'\xbc':.25,'\xbe':.75,'\u221e':9999999999,'\xe2':9999999999}

        x = [vals[key] for key in vals if key in issnum]

        if x:
            #logger.fdebug('Unicode Issue present - adjusting.')
            int_issnum = x[0] * 1000
            #logger.fdebug('int_issnum: ' + str(int_issnum))
        else:
            if any(['.' in issnum, ',' in issnum]):
                #logger.fdebug('decimal detected.')
                if ',' in issnum: issnum = re.sub(',', '.', issnum)
                issst = str(issnum).find('.')
                if issst == 0:
                    issb4dec = 0
                else:
                    issb4dec = str(issnum)[:issst]
                decis = str(issnum)[issst +1:]
                if len(decis) == 1:
                    decisval = int(decis) * 10
                    issaftdec = str(decisval)
                elif len(decis) == 2:
                    decisval = int(decis)
                    issaftdec = str(decisval)
                else:
                    decisval = decis
                    issaftdec = str(decisval)
                #if there's a trailing decimal (ie. 1.50.) and it's either intentional or not, blow it away.
                if issaftdec[-1:] == '.':
                    issaftdec = issaftdec[:-1]
                try:
                    int_issnum = (int(issb4dec) * 1000) + (int(issaftdec) * 10)
                except ValueError:
                    #logger.fdebug('This has no issue # for me to get - Either a Graphic Novel or one-shot.')
                    int_issnum = 999999999999999
            else:
                try:
                    x = float(issnum)
                    #logger.info(x)
                    #validity check
                    if x < 0:
                        #logger.info("I've encountered a negative issue #: " + str(issnum) + ". Trying to accomodate.")
                        int_issnum = (int(x) *1000) - 1
                    elif bool(x):
                        logger.fdebug('Infinity issue found.')
                        int_issnum = 9999999999 * 1000
                    else: raise ValueError
                except ValueError, e:
                    #this will account for any alpha in a issue#, so long as it doesn't have decimals.
                    x = 0
                    tstord = None
                    issno = None
                    invchk = "false"
                    while (x < len(issnum)):
                        if issnum[x].isalpha():
                        #take first occurance of alpha in string and carry it through
                            tstord = issnum[x:].rstrip()
                            tstord = re.sub('[\-\,\.\+]', '', tstord).rstrip()
                            issno = issnum[:x].rstrip()
                            issno = re.sub('[\-\,\.\+]', '', issno).rstrip()
                            try:
                                isschk = float(issno)
                            except ValueError, e:
                                if len(issnum) == 1 and issnum.isalpha():
                                    break
                                logger.fdebug('[' + issno + '] Invalid numeric for issue - cannot be found. Ignoring.')
                                issno = None
                                tstord = None
                                invchk = "true"
                            break
                        x+=1
                    if tstord is not None and issno is not None:
                        a = 0
                        ordtot = 0
                        if len(issnum) == 1 and issnum.isalpha():
                            int_issnum = ord(tstord.lower())
                        else:
                            while (a < len(tstord)):
                                ordtot += ord(tstord[a].lower())  #lower-case the letters for simplicty
                                a+=1
                            int_issnum = (int(issno) * 1000) + ordtot
                    elif invchk == "true":
                        logger.fdebug('this does not have an issue # that I can parse properly.')
                        return 999999999999999
                    else:
                        if issnum == '9-5':
                            issnum = u'9\xbd'
                            logger.fdebug('issue: 9-5 is an invalid entry. Correcting to : ' + issnum)
                            int_issnum = (9 * 1000) + (.5 * 1000)
                        elif issnum == '112/113':
                            int_issnum = (112 * 1000) + (.5 * 1000)
                        else:
                            logger.error(issnum + ' this has an alpha-numeric in the issue # which I cannot account for.')
                            return 999999999999999

    return int_issnum


def checkthepub(ComicID):
    import db, logger
    myDB = db.DBConnection()
    publishers = ['marvel', 'dc', 'darkhorse']
    pubchk = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [ComicID]).fetchone()
    if pubchk is None:
        logger.fdebug('No publisher information found to aid in determining series..defaulting to base check of 55 days.')
        return mylar.BIGGIE_PUB
    else:
        for publish in publishers:
            if publish in pubchk['ComicPublisher'].lower():
                logger.fdebug('Biggie publisher detected - ' + pubchk['ComicPublisher'])
                return mylar.BIGGIE_PUB

        logger.fdebug('Indie publisher detected - ' + pubchk['ComicPublisher'])
        return mylar.INDIE_PUB

def annual_update():
    import db, logger
    myDB = db.DBConnection()
    annuallist = myDB.select('SELECT * FROM annuals')
    if annuallist is None:
        logger.info('no annuals to update.')
        return

    cnames = []
    #populate the ComicName field with the corresponding series name from the comics table.
    for ann in annuallist:
        coms = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [ann['ComicID']]).fetchone()
        cnames.append({'ComicID':     ann['ComicID'],
                       'ComicName':   coms['ComicName']
                      })

    #write in a seperate loop to avoid db locks
    i=0
    for cns in cnames:
        ctrlVal = {"ComicID":      cns['ComicID']}
        newVal = {"ComicName":     cns['ComicName']}
        myDB.upsert("annuals", newVal, ctrlVal)
        i+=1

    logger.info(str(i) + ' series have been updated in the annuals table.')
    return

def replacetheslash(data):
    # this is necessary for the cache directory to display properly in IE/FF.
    # os.path.join will pipe in the '\' in windows, which won't resolve
    # when viewing through cherrypy - so convert it and viola.
    if platform.system() == "Windows":
        slashreplaced = data.replace('\\', '/')
    else:
        slashreplaced = data
    return slashreplaced

def urlretrieve(urlfile, fpath):
    chunk = 4096
    f = open(fpath, "w")
    while 1:
        data = urlfile.read(chunk)
        if not data:
            print "done."
            break
        f.write(data)
        print "Read %s bytes"%len(data)

def renamefile_readingorder(readorder):
    import logger
    logger.fdebug('readingorder#: ' + str(readorder))
    if int(readorder) < 10: readord = "00" + str(readorder)
    elif int(readorder) >= 10 and int(readorder) < 99: readord = "0" + str(readorder)
    else: readord = str(readorder)

    return readord

def latestdate_fix():
    import db, logger
    datefix = []
    cnupdate = []
    myDB = db.DBConnection()
    comiclist = myDB.select('SELECT * FROM comics')
    if comiclist is None:
        logger.fdebug('No Series in watchlist to correct latest date')
        return
    for cl in comiclist:
        if cl['ComicName_Filesafe'] is None:
            cnupdate.append({"comicid":  cl['ComicID'],
                            "comicname_filesafe": filesafe(cl['ComicName'])})
        latestdate = cl['LatestDate']
        #logger.fdebug("latestdate:  " + str(latestdate))
        if latestdate[8:] == '':
            #logger.fdebug("invalid date " + str(latestdate) + " appending 01 for day to avoid errors")
            if len(latestdate) <= 7:
                finddash = latestdate.find('-')
                #logger.info('dash found at position ' + str(finddash))
                if finddash != 4:  #format of mm-yyyy
                    lat_month = latestdate[:finddash]
                    lat_year = latestdate[finddash +1:]
                else:  #format of yyyy-mm
                    lat_month = latestdate[finddash +1:]
                    lat_year = latestdate[:finddash]

                latestdate = (lat_year) + '-' + str(lat_month) + '-01'
                datefix.append({"comicid":    cl['ComicID'],
                                "latestdate": latestdate})
                #logger.info('latest date: ' + str(latestdate))

    #now we fix.
    if len(datefix) > 0:
       logger.info('Preparing to correct/fix ' + str(len(datefix)) + ' series that have incorrect values given for the Latest Date field.')
       for df in datefix:
          newCtrl = {"ComicID":    df['comicid']}
          newVal = {"LatestDate":  df['latestdate']}
          myDB.upsert("comics", newVal, newCtrl)
    if len(cnupdate) > 0:
       logger.info('Preparing to update ' + str(len(cnupdate)) + ' series on your watchlist for use with non-ascii characters')
       for cn in cnupdate:
          newCtrl = {"ComicID":           cn['comicid']}
          newVal = {"ComicName_Filesafe": cn['comicname_filesafe']}
          myDB.upsert("comics", newVal, newCtrl)

    return

def upgrade_dynamic():
    import db, logger
    dynamic_comiclist = []
    myDB = db.DBConnection()
    #update the comicdb to include the Dynamic Names (and any futher changes as required)
    clist = myDB.select('SELECT * FROM Comics')
    for cl in clist:
        cl_d = mylar.filechecker.FileChecker(watchcomic=cl['ComicName'])
        cl_dyninfo = cl_d.dynamic_replace(cl['ComicName'])
        dynamic_comiclist.append({'DynamicComicName': re.sub('[\|\s]','', cl_dyninfo['mod_seriesname'].lower()).strip(),
                             'ComicID':          cl['ComicID']})

    if len(dynamic_comiclist) > 0:
        for dl in dynamic_comiclist:
            CtrlVal = {"ComicID": dl['ComicID']}
            newVal = {"DynamicComicName": dl['DynamicComicName']}
            myDB.upsert("Comics", newVal, CtrlVal)

    #update the readinglistdb to include the Dynamic Names (and any futher changes as required)
    dynamic_storylist = []
    rlist = myDB.select('SELECT * FROM readinglist WHERE StoryArcID is not NULL')
    for rl in rlist:
        rl_d = mylar.filechecker.FileChecker(watchcomic=rl['ComicName'])
        rl_dyninfo = cl_d.dynamic_replace(rl['ComicName'])
        dynamic_storylist.append({'DynamicComicName': re.sub('[\|\s]','', rl_dyninfo['mod_seriesname'].lower()).strip(),
                                  'IssueArcID':          rl['IssueArcID']})

    if len(dynamic_storylist) > 0:
        for ds in dynamic_storylist:
            CtrlVal = {"IssueArcID": ds['IssueArcID']}
            newVal = {"DynamicComicName": ds['DynamicComicName']}
            myDB.upsert("readinglist", newVal, CtrlVal)   

    logger.info('Finshed updating ' + str(len(dynamic_comiclist)) + ' / ' + str(len(dynamic_storylist)) + ' entries within the db.')
    mylar.DYNAMIC_UPDATE = 4
    mylar.config_write()
    return

def checkFolder():
    from mylar import PostProcessor, logger
    import Queue

    queue = Queue.Queue()
    #monitor a selected folder for 'snatched' files that haven't been processed
    logger.info('Checking folder ' + mylar.CHECK_FOLDER + ' for newly snatched downloads')
    PostProcess = PostProcessor.PostProcessor('Manual Run', mylar.CHECK_FOLDER, queue=queue)
    vals = PostProcess.Process()
    return

def LoadAlternateSearchNames(seriesname_alt, comicid):
    import logger
    #seriesname_alt = db.comics['AlternateSearch']
    AS_Alt = []
    Alternate_Names = {}
    alt_count = 0

    #logger.fdebug('seriesname_alt:' + str(seriesname_alt))
    if seriesname_alt is None or seriesname_alt == 'None':
        logger.fdebug('no Alternate name given. Aborting search.')
        return "no results"
    else:
        chkthealt = seriesname_alt.split('##')
        if chkthealt == 0:
            AS_Alternate = seriesname_alt
            AS_Alt.append(seriesname_alt)
        for calt in chkthealt:
            AS_Alter = re.sub('##', '', calt)
            u_altsearchcomic = AS_Alter.encode('ascii', 'ignore').strip()
            AS_formatrem_seriesname = re.sub('\s+', ' ', u_altsearchcomic)
            if AS_formatrem_seriesname[:1] == ' ': AS_formatrem_seriesname = AS_formatrem_seriesname[1:]

            AS_Alt.append({"AlternateName": AS_formatrem_seriesname})
            alt_count+=1

        Alternate_Names['AlternateName'] = AS_Alt
        Alternate_Names['ComicID'] = comicid
        Alternate_Names['Count'] = alt_count
        logger.info('AlternateNames returned:' + str(Alternate_Names))

        return Alternate_Names

def havetotals(refreshit=None):
        import db, logger

        comics = []
        myDB = db.DBConnection()

        if refreshit is None:
            if mylar.ANNUALS_ON:
                comiclist = myDB.select('SELECT comics.*, COUNT(totalAnnuals.IssueID) AS TotalAnnuals FROM comics LEFT JOIN annuals as totalAnnuals on totalAnnuals.ComicID = comics.ComicID GROUP BY comics.ComicID order by comics.ComicSortName COLLATE NOCASE')
            else:
                comiclist = myDB.select('SELECT * FROM comics GROUP BY ComicID order by ComicSortName COLLATE NOCASE')
        else:
            comiclist = []
            comicref = myDB.selectone('SELECT comics.ComicID, comics.Have, comics.Total, COUNT(totalAnnuals.IssueID) AS TotalAnnuals FROM comics LEFT JOIN annuals as totalAnnuals on totalAnnuals.ComicID = comics.ComicID WHERE comics.ComicID=? GROUP BY comics.ComicID', [refreshit]).fetchone()
            #refreshit is the ComicID passed from the Refresh Series to force/check numerical have totals
            comiclist.append({"ComicID":      comicref['ComicID'],
                              "Have":         comicref['Have'],
                              "Total":        comicref['Total'],
                              "TotalAnnuals": comicref['TotalAnnuals']})

        for comic in comiclist:
            #--not sure about this part
            #if comic['Total'] is None:
            #    if refreshit is not None:
            #        logger.fdebug(str(comic['ComicID']) + ' has no issuedata available. Forcing complete Refresh/Rescan')
            #        return True
            #    else:
            #        continue
            try:
                totalissues = comic['Total']
                if mylar.ANNUALS_ON:
                    totalissues += comic['TotalAnnuals']
                haveissues = comic['Have']
            except TypeError:
                logger.warning('[Warning] ComicID: ' + str(comic['ComicID']) + ' is incomplete - Removing from DB. You should try to re-add the series.')
                myDB.action("DELETE from COMICS WHERE ComicID=? AND ComicName LIKE 'Comic ID%'", [comic['ComicID']])
                myDB.action("DELETE from ISSUES WHERE ComicID=? AND ComicName LIKE 'Comic ID%'", [comic['ComicID']])
                continue

            if not haveissues:
                havetracks = 0

            if refreshit is not None:
                if haveissues > totalissues:
                    return True   # if it's 5/4, send back to updater and don't restore previous status'
                else:
                    return False  # if it's 5/5 or 4/5, send back to updater and restore previous status'

            try:
                percent = (haveissues *100.0) /totalissues
                if percent > 100:
                    percent = 101
            except (ZeroDivisionError, TypeError):
                percent = 0
                totalissuess = '?'

            if comic['LatestDate'] is None:
                logger.warn(comic['ComicName'] + ' has not finished loading. Nulling some values so things display properly until they can populate.')
                recentstatus = 'Loading'
            elif comic['ComicPublished'] is None or comic['ComicPublished'] == '' or comic['LatestDate'] is None:
                recentstatus = 'Unknown'
            elif comic['ForceContinuing'] == 1:
                recentstatus = 'Continuing'
            elif 'present' in comic['ComicPublished'].lower() or (today()[:4] in comic['LatestDate']):
                latestdate = comic['LatestDate']
                #pull-list f'd up the date by putting '15' instead of '2015' causing 500 server errors
                if '-' in latestdate[:3]:
                    st_date = latestdate.find('-')
                    st_remainder = latestdate[st_date+1:]
                    st_year = latestdate[:st_date]
                    year = '20' + st_year
                    latestdate = str(year) + '-' + str(st_remainder)
                    #logger.fdebug('year set to: ' + latestdate)
                c_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), 1)
                n_date = datetime.date.today()
                recentchk = (n_date - c_date).days
                if comic['NewPublish'] is True:
                    recentstatus = 'Continuing'
                else:
                    #do this just incase and as an extra measure of accuracy hopefully.
                    if recentchk < 55:
                        recentstatus = 'Continuing'
                    else:
                        recentstatus = 'Ended'
            else:
                recentstatus = 'Ended'

            comics.append({"ComicID":         comic['ComicID'],
                           "ComicName":       comic['ComicName'],
                           "ComicSortName":   comic['ComicSortName'],
                           "ComicPublisher":  comic['ComicPublisher'],
                           "ComicYear":       comic['ComicYear'],
                           "ComicImage":      comic['ComicImage'],
                           "LatestIssue":     comic['LatestIssue'],
                           "LatestDate":      comic['LatestDate'],
                           "ComicPublished":  re.sub('(N)', '', comic['ComicPublished']).strip(),
                           "Status":          comic['Status'],
                           "recentstatus":    recentstatus,
                           "percent":         percent,
                           "totalissues":     totalissues,
                           "haveissues":      haveissues,
                           "DateAdded":       comic['LastUpdated']})

        return comics

def filesafe(comic):
    import unicodedata
    try:
        u_comic = unicodedata.normalize('NFKD', comic).encode('ASCII', 'ignore').strip()
    except TypeError:
        u_comic = comic.encode('ASCII', 'ignore').strip()

    comicname_filesafe = re.sub('[\:\'\"\,\?\!\\\]', '', u_comic)
    comicname_filesafe = re.sub('[\/\*]', '-', comicname_filesafe)

    return comicname_filesafe

def IssueDetails(filelocation, IssueID=None, justinfo=False):
    import zipfile, logger
    from xml.dom.minidom import parseString

    issuedetails = []
    issuetag = None

    if justinfo is False:
        dstlocation = os.path.join(mylar.CACHE_DIR, 'temp.zip')


        if filelocation.endswith('.cbz'):
            logger.fdebug('CBZ file detected. Checking for .xml within file')
            shutil.copy(filelocation, dstlocation)
        else:
            logger.fdebug('filename is not a cbz : ' + filelocation)
            return

        cover = "notfound"
        pic_extensions = ('.jpg','.png','.webp')
        modtime = os.path.getmtime(dstlocation)
        low_infile = 999999

        try:
            with zipfile.ZipFile(dstlocation, 'r') as inzipfile:
                for infile in sorted(inzipfile.namelist()):
                    tmp_infile = re.sub("[^0-9]","", infile).strip()
                    if tmp_infile == '':
                        pass
                    elif int(tmp_infile) < int(low_infile):
                        low_infile = tmp_infile
                        low_infile_name = infile
                    if infile == 'ComicInfo.xml':
                        logger.fdebug('Extracting ComicInfo.xml to display.')
                        dst = os.path.join(mylar.CACHE_DIR, 'ComicInfo.xml')
                        data = inzipfile.read(infile)
                        #print str(data)
                        issuetag = 'xml'
                    #looks for the first page and assumes it's the cover. (Alternate covers handled later on)
                    elif any(['000.' in infile, '00.' in infile]) and infile.endswith(pic_extensions) and cover == "notfound":
                        logger.fdebug('Extracting primary image ' + infile + ' as coverfile for display.')
                        local_file = open(os.path.join(mylar.CACHE_DIR, 'temp.jpg'), "wb")
                        local_file.write(inzipfile.read(infile))
                        local_file.close
                        cover = "found"
                    elif any(['00a' in infile, '00b' in infile, '00c' in infile, '00d' in infile, '00e' in infile]) and infile.endswith(pic_extensions) and cover == "notfound":
                        logger.fdebug('Found Alternate cover - ' + infile + ' . Extracting.')
                        altlist = ('00a', '00b', '00c', '00d', '00e')
                        for alt in altlist:
                            if alt in infile:
                                local_file = open(os.path.join(mylar.CACHE_DIR, 'temp.jpg'), "wb")
                                local_file.write(inzipfile.read(infile))
                                local_file.close
                                cover = "found"
                                break

                    elif any(['001.jpg' in infile, '001.png' in infile, '001.webp' in infile, '01.jpg' in infile, '01.png' in infile, '01.webp' in infile]) and cover == "notfound":
                        logger.fdebug('Extracting primary image ' + infile + ' as coverfile for display.')
                        local_file = open(os.path.join(mylar.CACHE_DIR, 'temp.jpg'), "wb")
                        local_file.write(inzipfile.read(infile))
                        local_file.close
                        cover = "found"

                if cover != "found":
                    logger.fdebug('Invalid naming sequence for jpgs discovered. Attempting to find the lowest sequence and will use as cover (it might not work). Currently : ' + str(low_infile))
                    local_file = open(os.path.join(mylar.CACHE_DIR, 'temp.jpg'), "wb")
                    local_file.write(inzipfile.read(low_infile_name))
                    local_file.close
                    cover = "found"                

        except:
            logger.info('ERROR. Unable to properly retrieve the cover for displaying. It\'s probably best to re-tag this file.')
            return

        ComicImage = os.path.join('cache', 'temp.jpg?' +str(modtime))
        IssueImage = replacetheslash(ComicImage)

    else:
        IssueImage = "None"
        try:
            with zipfile.ZipFile(filelocation, 'r') as inzipfile:
                for infile in sorted(inzipfile.namelist()):
                    if infile == 'ComicInfo.xml':
                        logger.fdebug('Found ComicInfo.xml - now retrieving information.')
                        data = inzipfile.read(infile)
                        issuetag = 'xml'
                        break
        except:
            logger.info('ERROR. Unable to properly retrieve the cover for displaying. It\'s probably best to re-tag this file.')
            return


    if issuetag is None:
        data = None
        try:
            dz = zipfile.ZipFile(filelocation, 'r')
            data = dz.comment
        except:
            logger.warn('Unable to extract comment field from zipfile.')
            return
        else:
            if data:
                issuetag = 'comment'
            else:
                logger.warn('No metadata available in zipfile comment field.')
                return   

    logger.info('Tag returned as being: ' + str(issuetag))

    #logger.info('data:' + str(data))

    if issuetag == 'xml':
        #import easy to use xml parser called minidom:
        dom = parseString(data)

        results = dom.getElementsByTagName('ComicInfo')
        for result in results:
            try:
                issue_title = result.getElementsByTagName('Title')[0].firstChild.wholeText
            except:
                issue_title = "None"
            try:
                series_title = result.getElementsByTagName('Series')[0].firstChild.wholeText
            except:
                series_title = "None"
            try:
                series_volume = result.getElementsByTagName('Volume')[0].firstChild.wholeText
            except:
                series_volume = "None"
            try:
                issue_number = result.getElementsByTagName('Number')[0].firstChild.wholeText
            except:
                issue_number = "None"
            try:
                summary = result.getElementsByTagName('Summary')[0].firstChild.wholeText
            except:
                summary = "None"

            if '*List' in summary:
                summary_cut = summary.find('*List')
                summary = summary[:summary_cut]
                #check here to see if Covers exist as they will probably be misnamed when trying to determine the actual cover
                # (ie. 00a.jpg / 00d.jpg  - when there's a Cover A or a Cover D listed)
            try:
                notes = result.getElementsByTagName('Notes')[0].firstChild.wholeText  #IssueID is in here
            except:
                notes = "None"
            try:
                year = result.getElementsByTagName('Year')[0].firstChild.wholeText
            except:
                year = "None"
            try:
                month = result.getElementsByTagName('Month')[0].firstChild.wholeText
            except:
                month = "None"
            try:
                day = result.getElementsByTagName('Day')[0].firstChild.wholeText
            except:
                day = "None"
            try:
                writer = result.getElementsByTagName('Writer')[0].firstChild.wholeText
            except:
                writer = "None"
            try:
                penciller = result.getElementsByTagName('Penciller')[0].firstChild.wholeText
            except:
                penciller = "None"
            try:
                inker = result.getElementsByTagName('Inker')[0].firstChild.wholeText
            except:
                inker = "None"
            try:
                colorist = result.getElementsByTagName('Colorist')[0].firstChild.wholeText
            except:
                colorist = "None"
            try:
                letterer = result.getElementsByTagName('Letterer')[0].firstChild.wholeText
            except:
                letterer = "None"
            try:
                cover_artist = result.getElementsByTagName('CoverArtist')[0].firstChild.wholeText
            except:
                cover_artist = "None"
            try:
                editor = result.getElementsByTagName('Editor')[0].firstChild.wholeText
            except:
                editor = "None"
            try:
                publisher = result.getElementsByTagName('Publisher')[0].firstChild.wholeText
            except:
                publisher = "None"
            try:
                webpage = result.getElementsByTagName('Web')[0].firstChild.wholeText
            except:
                webpage = "None"
            try:
                pagecount = result.getElementsByTagName('PageCount')[0].firstChild.wholeText
            except:
                pagecount = 0

            #not used atm.
            #to validate a front cover if it's tagged as one within the zip (some do this)
            #i = 0
            #try:
            #    pageinfo = result.getElementsByTagName('Page')[0].attributes
            #    if pageinfo: pageinfo_test == True
            #except:
            #    pageinfo_test = False

            #if pageinfo_test:
            #    while (i < int(pagecount)):
            #        pageinfo = result.getElementsByTagName('Page')[i].attributes
            #        attrib = pageinfo.getNamedItem('Image')
            #        #logger.fdebug('Frontcover validated as being image #: ' + str(attrib.value))
            #        att = pageinfo.getNamedItem('Type')
            #        #logger.fdebug('pageinfo: ' + str(pageinfo))
            #        if att.value == 'FrontCover':
            #            #logger.fdebug('FrontCover detected. Extracting.')
            #            break
            #        i+=1

    elif issuetag == 'comment':
        logger.info('CBL Tagging.')
        stripline = 'Archive:  ' + filelocation
        data = re.sub(stripline, '', data.encode("utf-8")).strip()
        if data is None or data == '':
            return
        import ast
        ast_data = ast.literal_eval(str(data))
        lastmodified = ast_data['lastModified']

        dt = ast_data['ComicBookInfo/1.0']
        try:
            publisher = dt['publisher']
        except:
            publisher = None
        try:
            year = dt['publicationYear']
        except:
            year = None
        try:
            month = dt['publicationMonth']
        except:
            month = None
        try:
            day = dt['publicationDay']
        except:
            day = None
        try:
            issue_title = dt['title']
        except:
            issue_title = None
        try:
            series_title = dt['series']
        except:
            series_title = None
        try:
            issue_number = dt['issue']
        except:
            issue_number = None
        try:
            summary = dt['comments']
        except:
            summary = "None"

        editor = "None"
        colorist = "None"
        artist = "None"
        writer = "None"
        letterer = "None"
        cover_artist = "None"
        penciller = "None"
        inker = "None"

        try:
            series_volume = dt['volume']
        except:
            series_volume = None

        try:
            t = dt['credits']
        except:
            editor = None
            colorist = None
            artist = None
            writer = None
            letterer = None
            cover_artist = None
            penciller = None
            inker = None
            
        else:
            for cl in dt['credits']:
                if cl['role'] == 'Editor':
                    if editor == "None": editor = cl['person']
                    else: editor += ', ' + cl['person']
                elif cl['role'] == 'Colorist':
                    if colorist == "None": colorist = cl['person']
                    else: colorist += ', ' + cl['person']
                elif cl['role'] == 'Artist':
                    if artist == "None": artist = cl['person']
                    else: artist += ', ' + cl['person']
                elif cl['role'] == 'Writer':
                    if writer == "None": writer = cl['person']
                    else: writer += ', ' + cl['person']
                elif cl['role'] == 'Letterer':
                    if letterer == "None": letterer = cl['person']
                    else: letterer += ', ' + cl['person']
                elif cl['role'] == 'Cover':
                    if cover_artist == "None": cover_artist = cl['person']
                    else: cover_artist += ', ' + cl['person']
                elif cl['role'] == 'Penciller':
                    if penciller == "None": penciller = cl['person']
                    else: penciller += ', ' + cl['person']
                elif cl['role'] == 'Inker':
                    if inker == "None": inker = cl['person']
                    else: inker += ', ' + cl['person']

        try:
            notes = dt['notes']
        except:
            notes = "None"
        try:
            webpage = dt['web']
        except:
            webpage = "None"
        try:
            pagecount = dt['pagecount']
        except:
            pagecount = "None"

    else:
        logger.warn('Unable to locate any metadata within cbz file. Tag this file and try again if necessary.')
        return

    issuedetails.append({"title":        issue_title,
                         "series":       series_title,
                         "volume":       series_volume,
                         "issue_number": issue_number,
                         "summary":      summary,
                         "notes":        notes,
                         "year":         year,
                         "month":        month,
                         "day":          day,
                         "writer":       writer,
                         "penciller":    penciller,
                         "inker":        inker,
                         "colorist":     colorist,
                         "letterer":     letterer,
                         "cover_artist": cover_artist,
                         "editor":       editor,
                         "publisher":    publisher,
                         "webpage":      webpage,
                         "pagecount":    pagecount,
                         "IssueImage":   IssueImage})

    return issuedetails

def get_issue_title(IssueID=None, ComicID=None, IssueNumber=None, IssueArcID=None):
    import db, logger
    myDB = db.DBConnection()
    if IssueID:
        issue = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
        if issue is None:
            issue = myDB.selectone('SELECT * FROM annuals WHERE IssueID=?', [IssueID]).fetchone()
            if issue is None:
                logger.fdebug('Unable to locate given IssueID within the db. Assuming Issue Title is None.')
                return None
    else:
        issue = myDB.selectone('SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?', [ComicID, issuedigits(IssueNumber)]).fetchone()
        if issue is None:
            issue = myDB.selectone('SELECT * FROM annuals WHERE IssueID=?', [IssueID]).fetchone()
            if issue is None:
                if IssueArcID:
                    issue = myDB.selectone('SELECT * FROM readlist WHERE IssueArcID=?', [IssueArcID]).fetchone()
                    if issue is None:
                        logger.fdebug('Unable to locate given IssueID within the db. Assuming Issue Title is None.')
                        return None
                else:
                    logger.fdebug('Unable to locate given IssueID within the db. Assuming Issue Title is None.')
                    return None

    return issue['IssueName']

def int_num(s):
    try:
        return int(s)
    except ValueError:
        return float(s)

def listLibrary():
    import db
    library = {}
    myDB = db.DBConnection()
    # Get individual comics
    list = myDB.select("SELECT ComicId FROM Comics")
    for row in list:
        library[row['ComicID']] = row['ComicID']
    # Add the annuals
    if mylar.ANNUALS_ON:
        list = myDB.select("SELECT ReleaseComicId,ComicID FROM Annuals")
        for row in list:
            library[row['ReleaseComicId']] = row['ComicID']
    return library

def listStoryArcs():
    import db
    library = {}
    myDB = db.DBConnection()
    # Get Distinct Arc IDs
    list = myDB.select("SELECT DISTINCT(StoryArcID) FROM readinglist");
    for row in list:
        library[row['StoryArcID']] = row['StoryArcID']
    # Get Distinct CV Arc IDs
    list = myDB.select("SELECT DISTINCT(CV_ArcID) FROM readinglist");
    for row in list:
        library[row['CV_ArcID']] = row['CV_ArcID']
    return library

def manualArc(issueid, reading_order, storyarcid):
    import db
    if issueid.startswith('4000-'):
        issueid = issueid[5:]

    myDB = db.DBConnection()

    arc_chk = myDB.select("SELECT * FROM readinglist WHERE StoryArcID=? AND NOT Manual is 'deleted'", [storyarcid])
    storyarcname = arc_chk[0]['StoryArc']
    storyarcissues = arc_chk[0]['TotalIssues']

    iss_arcids = []
    for issarc in arc_chk:
        iss_arcids.append({"IssueArcID":     issarc['IssueArcID'],
                           "IssueID":        issarc['IssueID'],
                           "Manual":         issarc['Manual'],
                           "ReadingOrder":   issarc['ReadingOrder']})


    arc_results = mylar.cv.getComic(comicid=None, type='issue', issueid=None, arcid=storyarcid, arclist='M' + str(issueid))
    arcval = arc_results['issuechoice'][0]
    comicname = arcval['ComicName']
    st_d = mylar.filechecker.FileChecker(watchcomic=comicname)
    st_dyninfo = st_d.dynamic_replace(comicname)
    dynamic_name = re.sub('[\|\s]','', st_dyninfo['mod_seriesname'].lower()).strip()
    issname = arcval['Issue_Name']
    issid = str(arcval['IssueID'])
    comicid = str(arcval['ComicID'])
    cidlist = str(comicid)
    st_issueid = None
    manual_mod = 'added'
    new_readorder = []
    for aid in iss_arcids:
        if aid['IssueID'] == issid:
            logger.info('Issue already exists for storyarc [IssueArcID:' + aid['IssueArcID'] + '][Manual:' + aid['Manual'])
            st_issueid = aid['IssueArcID']
            manual_mod = aid['Manual']

        if reading_order is None:
            #if no reading order is given, drop in the last spot.
            reading_order = len(iss_arcids) + 1
        if int(aid['ReadingOrder']) >= int(reading_order):
            reading_seq = int(aid['ReadingOrder']) + 1
        else:
            reading_seq = int(aid['ReadingOrder'])

        new_readorder.append({'IssueArcID':   aid['IssueArcID'],
                              'IssueID':      aid['IssueID'],
                              'ReadingOrder': reading_seq})

    import random
    if st_issueid is None:
        st_issueid = str(storyarcid) + "_" + str(random.randint(1000,9999))
    issnum = arcval['Issue_Number']
    issdate = str(arcval['Issue_Date'])
    storedate = str(arcval['Store_Date'])
    int_issnum = issuedigits(issnum)

    comicid_results = mylar.cv.getComic(comicid=None, type='comicyears', comicidlist=cidlist)
    seriesYear = 'None'
    issuePublisher = 'None'
    seriesVolume = 'None'

    if issname is None:
        IssueName = 'None'
    else:
        IssueName = issname[:70]

    for cid in comicid_results:
        if cid['ComicID'] == comicid:
            seriesYear = cid['SeriesYear']
            issuePublisher = cid['Publisher']
            seriesVolume = cid['Volume']
            #assume that the arc is the same
            storyarcpublisher = issuePublisher
            break


    newCtrl = {"IssueID":           issid,
               "StoryArcID":        storyarcid}
    newVals = {"ComicID":           comicid,
               "IssueArcID":        st_issueid,
               "StoryArc":          storyarcname,
               "ComicName":         comicname,
               "Volume":            seriesVolume,
               "DynamicComicName":  dynamic_name,
               "IssueName":         IssueName,
               "IssueNumber":       issnum,
               "Publisher":         storyarcpublisher,
               "TotalIssues":       str(int(storyarcissues) +1),
               "ReadingOrder":      int(reading_order),  #arbitrarily set it to the last reading order sequence # just to see if it works.
               "IssueDate":         issdate,
               "StoreDate":         storedate,
               "SeriesYear":        seriesYear,
               "IssuePublisher":    issuePublisher,
               "CV_ArcID":          storyarcid,
               "Int_IssueNumber":   int_issnum,
               "Manual":            manual_mod}

    myDB.upsert("readinglist", newVals, newCtrl)

    #now we resequence the reading-order to accomdate the change.
    logger.info('Adding the new issue into the reading order & resequencing the order to make sure there are no sequence drops...')
    new_readorder.append({'IssueArcID':   st_issueid,
                          'IssueID':      issid,
                          'ReadingOrder': int(reading_order)})

    newrl = 0
    for rl in sorted(new_readorder, key=itemgetter('ReadingOrder'), reverse=False):
        if rl['ReadingOrder'] - 1 != newrl:
            rorder = newrl + 1
            logger.fdebug(rl['IssueID'] + ' - changing reading order seq to : ' + str(rorder))
        else:
            rorder = rl['ReadingOrder']
            logger.fdebug(rl['IssueID'] + ' - setting reading order seq to : ' + str(rorder))

        rl_ctrl = {"IssueID":           rl['IssueID'],
                   "IssueArcID":        rl['IssueArcID'],
                   "StoryArcID":        storyarcid}
        r1_new = {"ReadingOrder":       rorder}
        newrl = rorder

        myDB.upsert("readinglist", r1_new, rl_ctrl)

    #check to see if the issue exists already so we can set the status right away.
    iss_chk = myDB.selectone('SELECT * FROM issues where issueid = ?', [issueid]).fetchone()
    if iss_chk is None:
        logger.info('Issue is not currently in your watchlist. Setting status to Skipped')
        status_change = 'Skipped'
    else:
        status_change = iss_chk['Status']
        logger.info('Issue currently exists in your watchlist. Setting status to ' + status_change)
        myDB.upsert("readinglist", {'Status': status_change}, newCtrl)

    return

def listIssues(weeknumber, year):
    import db
    library = []
    myDB = db.DBConnection()
    # Get individual issues
    list = myDB.select("SELECT issues.Status, issues.ComicID, issues.IssueID, issues.ComicName, weekly.publisher, issues.Issue_Number from weekly, issues where weekly.IssueID = issues.IssueID and weeknumber = ? and year = ?", [int(weeknumber), year])
    for row in list:
        library.append({'ComicID': row['ComicID'],
                       'Status':  row['Status'],
                       'IssueID': row['IssueID'],
                       'ComicName': row['ComicName'],
                       'Publisher': row['publisher'],
                       'Issue_Number': row['Issue_Number']})
    # Add the annuals
    if mylar.ANNUALS_ON:
        list = myDB.select("SELECT annuals.Status, annuals.ComicID, annuals.ReleaseComicID, annuals.IssueID, annuals.ComicName, weekly.publisher, annuals.Issue_Number from weekly, annuals where weekly.IssueID = annuals.IssueID and weeknumber = ? and year = ?", [int(weeknumber), year])
        for row in list:
            library.append({'ComicID': row['ComicID'],
                            'Status':  row['Status'],
                            'IssueID': row['IssueID'],
                            'ComicName': row['ComicName'],
                            'Publisher': row['publisher'],
                            'Issue_Number': row['Issue_Number']})

    return library

def incr_snatched(ComicID):
    import db, logger
    myDB = db.DBConnection()
    incr_count = myDB.selectone("SELECT Have FROM Comics WHERE ComicID=?", [ComicID]).fetchone()
    logger.fdebug('Incrementing HAVE count total to : ' + str(incr_count['Have'] + 1))
    newCtrl = {"ComicID":    ComicID}
    newVal = {"Have":  incr_count['Have'] + 1}
    myDB.upsert("comics", newVal, newCtrl)
    return

def duplicate_filecheck(filename, ComicID=None, IssueID=None, StoryArcID=None):
    #filename = the filename in question that's being checked against
    #comicid = the comicid of the series that's being checked for duplication
    #issueid = the issueid of the issue that's being checked for duplication
    #storyarcid = the storyarcid of the issue that's being checked for duplication.
    #
    import db, logger
    myDB = db.DBConnection()

    logger.info('[DUPECHECK] Duplicate check for ' + filename)
    filesz = os.path.getsize(filename)

    if IssueID:
        dupchk = myDB.selectone("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
    if dupchk is None:
        dupchk = myDB.selectone("SELECT * FROM annuals WHERE IssueID=?", [IssueID]).fetchone()
        if dupchk is None:
            logger.info('[DUPECHECK] Unable to find corresponding Issue within the DB. Do you still have the series on your watchlist?')
            return

    series = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [dupchk['ComicID']]).fetchone()

    #if it's a retry and the file was already snatched, the status is Snatched and won't hit the dupecheck.
    #rtnval will be one of 3: 
    #'write' - write new file
    #'dupe_file' - do not write new file as existing file is better quality
    #'dupe_src' - write new file, as existing file is a lesser quality (dupe)
    rtnval = []
    if dupchk['Status'] == 'Downloaded' or dupchk['Status'] == 'Archived':
        try:
            dupsize = dupchk['ComicSize']
        except:
            logger.info('[DUPECHECK] Duplication detection returned no hits as this is a new Snatch. This is not a duplicate.')
            rtnval.append({'action':  "write"})

        logger.info('[DUPECHECK] Existing Status already set to ' + dupchk['Status'])
        cid = []
        if dupsize is None:
            logger.info('[DUPECHECK] Existing filesize is 0 bytes as I cannot locate the orginal entry - it is probably archived.')
            logger.fdebug('[DUPECHECK] Checking series for unrefreshed series syndrome (USS).')
            havechk = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
            if havechk:
                if havechk['Have'] > havechk['Total']:
                    logger.info('[DUPECHECK] Series has invalid issue totals [' + str(havechk['Have']) + '/' + str(havechk['Total']) + '] Attempting to Refresh & continue post-processing this issue.')
                    cid.append(ComicID)
                    logger.fdebug('[DUPECHECK] ComicID: ' + str(ComicID))
                    mylar.updater.dbUpdate(ComicIDList=cid, calledfrom='dupechk')
                    return duplicate_filecheck(filename, ComicID, IssueID, StoryArcID)
                else:
                    #file is Archived, but no entry exists in the db for the location. Assume Archived, and don't post-process.
                    logger.fdebug('[DUPECHECK] File is Archived but no file can be located within the db at the specified location. Assuming this was a manual archival and will not post-process this issue.')
                    rtnval.append({'action':  "dont_dupe"})

            else:
                rtnval.append({'action':  "dupe_file",
                               'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])})
        else:
            logger.info('[DUPECHECK] Existing file within db :' + dupchk['Location'] + ' has a filesize of : ' + str(dupsize) + ' bytes.')

            #keywords to force keep / delete
            #this will be eventually user-controlled via the GUI once the options are enabled.

            if int(dupsize) == 0:
                logger.info('[DUPECHECK] Existing filesize is 0 as I cannot locate the original entry.')
                if dupchk['Status'] == 'Archived':
                    logger.info('[DUPECHECK] Assuming issue is Archived.')
                    rtnval.append({'action':  "dupe_file",
                                   'to_dupe': filename})
                    return rtnval
                else:
                    logger.info('[DUPECHECK] Assuming 0-byte file - this one is gonna get hammered.')

            logger.fdebug('[DUPECHECK] Based on duplication preferences I will retain based on : ' + mylar.DUPECONSTRAINT)

            tmp_dupeconstraint = mylar.DUPECONSTRAINT

            if any(['cbr' in mylar.DUPECONSTRAINT, 'cbz' in mylar.DUPECONSTRAINT]):
                if 'cbr' in mylar.DUPECONSTRAINT:
                    if filename.endswith('.cbr'):
                        #this has to be configured in config - either retain cbr or cbz.
                        if dupchk['Location'].endswith('.cbr'):
                            logger.info('[DUPECHECK-CBR PRIORITY] [#' + dupchk['Issue_Number'] + '] BOTH files are in cbr format. Retaining the larger filesize of the two.')
                            tmp_dupeconstraint = 'filesize'
                        else:
                            #keep filename
                            logger.info('[DUPECHECK-CBR PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining newly scanned in file : ' + filename)
                            rtnval.append({'action':  "dupe_src",
                                           'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])})
                    else:
                        if dupchk['Location'].endswith('.cbz'):
                            logger.info('[DUPECHECK-CBR PRIORITY] [#' + dupchk['Issue_Number'] + '] BOTH files are in cbz format. Retaining the larger filesize of the two.')
                            tmp_dupeconstraint = 'filesize'
                        else:
                            #keep filename
                            logger.info('[DUPECHECK-CBR PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining newly scanned in file : ' + dupchk['Location'])
                            rtnval.append({'action':  "dupe_file",
                                           'to_dupe': filename})

                elif 'cbz' in mylar.DUPECONSTRAINT:
                    if filename.endswith('.cbr'):
                        if dupchk['Location'].endswith('.cbr'):
                            logger.info('[DUPECHECK-CBZ PRIORITY] [#' + dupchk['Issue_Number'] + '] BOTH files are in cbr format. Retaining the larger filesize of the two.')
                            tmp_dupeconstraint = 'filesize'
                        else:
                            #keep filename
                            logger.info('[DUPECHECK-CBZ PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining currently scanned in filename : ' + dupchk['Location'])
                            rtnval.append({'action':  "dupe_file",
                                           'to_dupe': filename})
                    else:
                        if dupchk['Location'].endswith('.cbz'):
                            logger.info('[DUPECHECK-CBZ PRIORITY] [#' + dupchk['Issue_Number'] + '] BOTH files are in cbz format. Retaining the larger filesize of the two.')
                            tmp_dupeconstraint = 'filesize'
                        else:
                            #keep filename
                            logger.info('[DUPECHECK-CBZ PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining newly scanned in filename : ' + filename)
                            rtnval.append({'action':  "dupe_src",
                                           'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])})

            if mylar.DUPECONSTRAINT == 'filesize' or tmp_dupeconstraint == 'filesize':
                if filesz <= int(dupsize) and int(dupsize) != 0:
                    logger.info('[DUPECHECK-FILESIZE PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining currently scanned in filename : ' + dupchk['Location'])
                    rtnval.append({'action':  "dupe_file",
                                   'to_dupe': filename}) 
                else:
                    logger.info('[DUPECHECK-FILESIZE PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining newly scanned in filename : ' + filename)
                    rtnval.append({'action':  "dupe_src",
                                   'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])})

    else:
        logger.info('[DUPECHECK] Duplication detection returned no hits. This is not a duplicate of anything that I have scanned in as of yet.')
        rtnval.append({'action':  "write"})
    return rtnval

def create_https_certificates(ssl_cert, ssl_key):
    """
    Create a pair of self-signed HTTPS certificares and store in them in
    'ssl_cert' and 'ssl_key'. Method assumes pyOpenSSL is installed.

    This code is stolen from SickBeard (http://github.com/midgetspy/Sick-Beard).
    """

    import logger
    from OpenSSL import crypto
    from certgen import createKeyPair, createCertRequest, createCertificate, \
        TYPE_RSA, serial

    # Create the CA Certificate
    cakey = createKeyPair(TYPE_RSA, 2048)
    careq = createCertRequest(cakey, CN="Certificate Authority")
    cacert = createCertificate(careq, (careq, cakey), serial, (0, 60 * 60 * 24 * 365 * 10)) # ten years

    pkey = createKeyPair(TYPE_RSA, 2048)
    req = createCertRequest(pkey, CN="Mylar")
    cert = createCertificate(req, (cacert, cakey), serial, (0, 60 * 60 * 24 * 365 * 10)) # ten years

    # Save the key and certificate to disk
    try:
        with open(ssl_key, "w") as fp:
            fp.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey))
        with open(ssl_cert, "w") as fp:
            fp.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    except IOError as e:
        logger.error("Error creating SSL key and certificate: %s", e)
        return False

    return True

def torrent_create(site, linkid, alt=None):
    if any([site == '32P', site == 'TOR']):
        pass
    elif site == 'TPSE':
        if alt is None:
            url = 'http://torrentproject.se/torrent/' + str(linkid) + '.torrent'
        else:
            url = 'http://torrentproject.se/torrent/' + str(linkid) + '.torrent'
    elif site == 'DEM':
        url = 'https://www.dnoid.me/files/download/' + str(linkid) + '/'
    elif site == 'WWT':
        url = 'https://worldwidetorrents.eu/download.php'

    return url

def parse_32pfeed(rssfeedline):
    KEYS_32P = {}
    if mylar.ENABLE_32P and len(rssfeedline) > 1:
        userid_st = rssfeedline.find('&user')
        userid_en = rssfeedline.find('&', userid_st +1)
        if userid_en == -1:
            USERID_32P = rssfeedline[userid_st +6:]
        else:
            USERID_32P = rssfeedline[userid_st +6:userid_en]

        auth_st = rssfeedline.find('&auth')
        auth_en = rssfeedline.find('&', auth_st +1)
        if auth_en == -1:
            AUTH_32P = rssfeedline[auth_st +6:]
        else:
            AUTH_32P = rssfeedline[auth_st +6:auth_en]

        authkey_st = rssfeedline.find('&authkey')
        authkey_en = rssfeedline.find('&', authkey_st +1)
        if authkey_en == -1:
            AUTHKEY_32P = rssfeedline[authkey_st +9:]
        else:
            AUTHKEY_32P = rssfeedline[authkey_st +9:authkey_en]

        KEYS_32P = {"user":    USERID_32P,
                    "auth":    AUTH_32P,
                    "authkey": AUTHKEY_32P,
                    "passkey": mylar.PASSKEY_32P}

    return KEYS_32P

def humanize_time(amount, units = 'seconds'):

    def process_time(amount, units):

        INTERVALS = [   1, 60,
                        60*60,
                        60*60*24,
                        60*60*24*7,
                        60*60*24*7*4,
                        60*60*24*7*4*12,
                        60*60*24*7*4*12*100,
                        60*60*24*7*4*12*100*10]
        NAMES = [('second', 'seconds'),
                 ('minute', 'minutes'),
                 ('hour', 'hours'),
                 ('day', 'days'),
                 ('week', 'weeks'),
                 ('month', 'months'),
                 ('year', 'years'),
                 ('century', 'centuries'),
                 ('millennium', 'millennia')]

        result = []

        unit = map(lambda a: a[1], NAMES).index(units)
        # Convert to seconds
        amount = amount * INTERVALS[unit]

        for i in range(len(NAMES)-1, -1, -1):
            a = amount // INTERVALS[i]
            if a > 0:
                result.append( (a, NAMES[i][1 % a]) )
                amount -= a * INTERVALS[i]

        return result

    rd = process_time(int(amount), units)
    cont = 0
    for u in rd:
        if u[0] > 0:
            cont += 1

    buf = ''
    i = 0
    for u in rd:
        if u[0] > 0:
            buf += "%d %s" % (u[0], u[1])
            cont -= 1

        if i < (len(rd)-1):
            if cont > 1:
                buf += ", "
            else:
                buf += " and "

        i += 1

    return buf

def issue_status(IssueID):
    import db, logger
    myDB = db.DBConnection()

    logger.fdebug('[ISSUE-STATUS] Issue Status Check for ' + str(IssueID))

    isschk = myDB.selectone("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
    if isschk is None:
        isschk = myDB.selectone("SELECT * FROM annuals WHERE IssueID=?", [IssueID]).fetchone()
        if isschk is None:
            logger.warn('Unable to retrieve IssueID from db. This is a problem. Aborting.')
            return False

    if any([isschk['Status'] == 'Downloaded', isschk['Status'] == 'Snatched']):
        return True
    else:
        return False

def crc(filename):
    import hashlib
    #memory in lieu of speed (line by line)
    #prev = 0
    #for eachLine in open(filename,"rb"):
    #    prev = zlib.crc32(eachLine, prev)
    #return "%X"%(prev & 0xFFFFFFFF)

    #speed in lieu of memory (file into memory entirely)
    #return "%X" % (zlib.crc32(open(filename, "rb").read()) & 0xFFFFFFFF)
    filename = filename.encode(mylar.SYS_ENCODING)
    return hashlib.md5(filename).hexdigest()

def issue_find_ids(ComicName, ComicID, pack, IssueNumber):
    import db, logger

    myDB = db.DBConnection()

    issuelist = myDB.select("SELECT * FROM issues WHERE ComicID=?", [ComicID])

    if 'Annual' not in pack:
        pack_issues = range(int(pack[:pack.find('-')]),int(pack[pack.find('-')+1:])+1)
        annualize = False
    else:
        #remove the annuals wording
        tmp_annuals = pack[pack.find('Annual'):]
        tmp_ann = re.sub('[annual/annuals/+]', '', tmp_annuals.lower()).strip()
        tmp_pack = re.sub('[annual/annuals/+]', '', pack.lower()).strip() 
        pack_issues = range(int(tmp_pack[:tmp_pack.find('-')]),int(tmp_pack[tmp_pack.find('-')+1:])+1)
        annualize = True

    issues = {}
    issueinfo = []

    Int_IssueNumber = issuedigits(IssueNumber)
    valid = False

    for iss in pack_issues:
       int_iss = issuedigits(iss)
       for xb in issuelist:
           if xb['Status'] != 'Downloaded':
               if xb['Int_IssueNumber'] == int_iss:
                   issueinfo.append({'issueid':      xb['IssueID'],
                                     'int_iss':      int_iss,
                                     'issuenumber':  xb['Issue_Number']})
                   break

    for x in issueinfo:
       if Int_IssueNumber == x['int_iss']:
           valid = True
           break

    issues['issues'] = issueinfo

    if len(issues['issues']) == len(pack_issues):
        logger.info('Complete issue count of ' + str(len(pack_issues)) + ' issues are available within this pack for ' + ComicName)
    else:
        logger.info('Issue counts are not complete (not a COMPLETE pack) for ' + ComicName)

    issues['issue_range'] = pack_issues
    issues['valid'] = valid
    return issues

def conversion(value):
    if type(value) == str:
        try:
            value = value.decode('utf-8')
        except:
            value = value.decode('windows-1252')
    return value

def clean_url(url):
    leading = len(url) - len(url.lstrip(' '))
    ending = len(url) - len(url.rstrip(' '))
    if leading >= 1:
        url = url[leading:]
    if ending >=1:
        url = url[:-ending]
    return url

def chunker(seq, size):
    #returns a list from a large group of tuples by size (ie. for group in chunker(seq, 3))
    return [seq[pos:pos + size] for pos in xrange(0, len(seq), size)]

def cleanHost(host, protocol = True, ssl = False, username = None, password = None):
    """  Return a cleaned up host with given url options set
            taken verbatim from CouchPotato
    Changes protocol to https if ssl is set to True and http if ssl is set to false.
    >>> cleanHost("localhost:80", ssl=True)
    'https://localhost:80/'
    >>> cleanHost("localhost:80", ssl=False)
    'http://localhost:80/'

    Username and password is managed with the username and password variables
    >>> cleanHost("localhost:80", username="user", password="passwd")
    'http://user:passwd@localhost:80/'

    Output without scheme (protocol) can be forced with protocol=False
    >>> cleanHost("localhost:80", protocol=False)
    'localhost:80'
    """

    if not '://' in host and protocol:
        host = ('https://' if ssl else 'http://') + host

    if not protocol:
        host = host.split('://', 1)[-1]

    if protocol and username and password:
        try:
            auth = re.findall('^(?:.+?//)(.+?):(.+?)@(?:.+)$', host)
            if auth:
                log.error('Cleanhost error: auth already defined in url: %s, please remove BasicAuth from url.', host)
            else:
                host = host.replace('://', '://%s:%s@' % (username, password), 1)
        except:
            pass

    host = host.rstrip('/ ')
    if protocol:
        host += '/'

    return host

def checkthe_id(comicid=None, up_vals=None):
    import db, logger
    myDB = db.DBConnection()
    if not up_vals:
        chk = myDB.selectone("SELECT * from ref32p WHERE ComicID=?", [comicid]).fetchone()
        if chk is None:
           return None
        else:
           return {'id':     chk['ID'],
                   'series': chk['Series']}
    else:
        ctrlVal = {'ComicID':     comicid}
        newVal =  {'Series':      up_vals[0]['series'],
                   'ID':          up_vals[0]['id']}
        myDB.upsert("ref32p", newVal, ctrlVal)

def updatearc_locs(storyarcid, issues):
    import db, logger
    myDB = db.DBConnection()
    issuelist = []
    for x in issues:
        issuelist.append(x['IssueID'])
    tmpsql = "SELECT a.comicid, a.comiclocation, b.comicid, b.status, b.issueid, b.location FROM comics as a INNER JOIN issues as b ON a.comicid = b.comicid WHERE b.issueid in ({seq})".format(seq=','.join(['?'] *(len(issuelist))))
    chkthis = myDB.select(tmpsql, issuelist)
    update_iss = []
    if chkthis is None:
        return
    else:
        for chk in chkthis:
            if chk['Status'] == 'Downloaded':
                pathsrc = os.path.join(chk['ComicLocation'], chk['Location'])
                if not os.path.exists(pathsrc):
                    if all([mylar.MULTIPLE_DEST_DIRS is not None, mylar.MULTIPLE_DEST_DIRS != 'None', os.path.join(mylar.MULTIPLE_DEST_DIRS, os.path.basename(chk['ComicLocation'])) != chk['ComicLocation'], os.path.exists(os.path.join(mylar.MULTIPLE_DEST_DIRS, os.path.basename(chk['ComicLocation'])))]):
                        pathsrc = os.path.join(mylar.MULTIPLE_DEST_DIRS, os.path.basename(chk['ComicLocation']), chk['Location'])
                    else:
                        logger.fdebug(module + ' file does not exist in location: ' + pathdir + '. Cannot valid location - some options will not be available for this item.')
                        continue

#                update_iss.append({'IssueID':    chk['IssueID'],
#                                   'Location':   pathdir})
                arcinfo = None
                for la in issues:
                    if la['IssueID'] == chk['IssueID']:
                        arcinfo = la
                        break

                if arcinfo is None:
                    continue

                if arcinfo['Publisher'] is None:
                    arcpub = arcinfo['IssuePublisher']
                else:
                    arcpub = arcinfo['Publisher']

                grdst = arcformat(arcinfo['StoryArc'], spantheyears(arcinfo['StoryArcID']), arcpub)
                if grdst is not None:
                    logger.info('grdst:' + grdst)
                    #send to renamer here if valid.
                    dfilename = chk['Location']
                    if mylar.RENAME_FILES:
                        renamed_file = rename_param(arcinfo['ComicID'], arcinfo['ComicName'], arcinfo['IssueNumber'], chk['Location'], issueid=arcinfo['IssueID'], arc=arcinfo['StoryArc'])
                        if renamed_file:
                            dfilename = renamed_file['nfilename']

                    if mylar.READ2FILENAME:
                        #logger.fdebug('readingorder#: ' + str(arcinfo['ReadingOrder']))
                        #if int(arcinfo['ReadingOrder']) < 10: readord = "00" + str(arcinfo['ReadingOrder'])
                        #elif int(arcinfo['ReadingOrder']) >= 10 and int(arcinfo['ReadingOrder']) <= 99: readord = "0" + str(arcinfo['ReadingOrder'])
                        #else: readord = str(arcinfo['ReadingOrder'])
                        readord = renamefile_readingorder(arcinfo['ReadingOrder'])
                        dfilename = str(readord) + "-" + dfilename

                    pathdst = os.path.join(grdst, dfilename)

                    logger.fdebug('Destination Path : ' + pathdst)
                    logger.fdebug('Source Path : ' + pathsrc)
                    if not os.path.isfile(pathdst):
                        logger.info('[' + mylar.ARC_FILEOPS.upper() + '] ' + pathsrc + ' into directory : ' + pathdst)

                        try:
                            #need to ensure that src is pointing to the series in order to do a soft/hard-link properly
                            fileoperation = file_ops(pathsrc, pathdst, arc=True)
                            if not fileoperation:
                                raise OSError
                        except (OSError, IOError):
                            logger.fdebug('[' + mylar.ARC_FILEOPS.upper() + '] Failure ' + pathsrc + ' - check directories and manually re-run.')
                            continue
                    updateloc = pathdst
                else:
                    updateloc = pathsrc

                update_iss.append({'IssueID':    chk['IssueID'],
                                   'Location':   updateloc})

    for ui in update_iss:
        logger.info(ui['IssueID'] + ' to update location to: ' + ui['Location'])
        myDB.upsert("readinglist", {'Location': ui['Location']}, {'IssueID': ui['IssueID'], 'StoryArcID': storyarcid})


def spantheyears(storyarcid):
    import db
    myDB = db.DBConnection()

    totalcnt = myDB.select("SELECT * FROM readinglist WHERE StoryArcID=?", [storyarcid])
    lowyear = 9999
    maxyear = 0
    for la in totalcnt:
        if la['IssueDate'] is None or la['IssueDate'] == '0000-00-00':
            continue
        else:
            if int(la['IssueDate'][:4]) > maxyear:
                maxyear = int(la['IssueDate'][:4])
            if int(la['IssueDate'][:4]) < lowyear:
                lowyear = int(la['IssueDate'][:4])

    if maxyear == 0:
        spanyears = la['SeriesYear']
    elif lowyear == maxyear:
        spanyears = str(maxyear)
    else:
        spanyears = str(lowyear) + ' - ' + str(maxyear) #la['SeriesYear'] + ' - ' + str(maxyear)
    return spanyears

def arcformat(arc, spanyears, publisher):
    arcdir = filesafe(arc)
    if publisher is None:
        publisher = 'None'

    values = {'$arc':         arcdir,
              '$spanyears':   spanyears,
              '$publisher':   publisher}

    tmp_folderformat = mylar.ARC_FOLDERFORMAT

    if publisher == 'None':
        chunk_f_f = re.sub('\$publisher', '', tmp_folderformat)
        chunk_f = re.compile(r'\s+')
        tmp_folderformat = chunk_f.sub(' ', chunk_f_f)


    if any([tmp_folderformat == '', tmp_folderformat is None]):
        arcpath = arcdir
    else:
        arcpath = replace_all(tmp_folderformat, values)

    if mylar.REPLACE_SPACES:
        arcpath = arcpath.replace(' ', mylar.REPLACE_CHAR)

    if arcpath.startswith('/'):
        arcpath = arcpath[1:]
    elif arcpath.startswith('//'):
        arcpath = arcpath[2:]

    if mylar.STORYARCDIR:
        logger.info(mylar.DESTINATION_DIR)
        logger.info('StoryArcs')
        logger.info(arcpath)
        dstloc = os.path.join(mylar.DESTINATION_DIR, 'StoryArcs', arcpath)
    elif mylar.COPY2ARCDIR:
        logger.warn('Story arc directory is not configured. Defaulting to grabbag directory: ' + mylar.GRABBAG_DIR)
        dstloc = os.path.join(mylar.GRABBAG_DIR, arcpath)
    else:
        dstloc = None

    return dstloc

def torrentinfo(issueid=None, torrent_hash=None, download=False):
    import db
    from base64 import b16encode, b32decode

    #check the status of the issueid to make sure it's in Snatched status and was grabbed via torrent.
    if issueid:
        myDB = db.DBConnection()
        cinfo = myDB.selectone('SELECT a.Issue_Number, a.ComicName, a.Status, b.Hash from issues as a inner join snatched as b ON a.IssueID=b.IssueID WHERE a.IssueID=?', [issueid]).fetchone()
        if cinfo is None:
            logger.warn('Unable to locate IssueID of : ' + issueid)
            snatch_status = 'ERROR'

        if cinfo['Status'] != 'Snatched' or cinfo['Hash'] is None:
            logger.warn(cinfo['ComicName'] + ' #' + cinfo['Issue_Number'] + ' is currently in a ' + cinfo['Status'] + ' Status.')
            snatch_status = 'ERROR'

        torrent_hash = cinfo['Hash']

    logger.fdebug("Working on torrent: " + torrent_hash)
    if len(torrent_hash) == 32:
       torrent_hash = b16encode(b32decode(torrent_hash))

    if not len(torrent_hash) == 40:
       logger.error("Torrent hash is missing, or an invalid hash value has been passed")
       snatch_status = 'ERROR'
    else:
        if mylar.USE_RTORRENT:
            import test
            rp = test.RTorrent()
            torrent_info = rp.main(torrent_hash, check=True)
        elif mylar.USE_DELUGE:
            #need to set the connect here as well....
            import torrent.clients.deluge as delu
            dp = delu.TorrentClient()
            if not dp.connect(mylar.DELUGE_HOST, mylar.DELUGE_USERNAME, mylar.DELUGE_PASSWORD):
                logger.warn('Not connected to Deluge!')

            torrent_info = dp.get_torrent(torrent_hash)
        else:
            snatch_status = 'ERROR'
            return

    if torrent_info is False or len(torrent_info) == 0:
        logger.warn('torrent returned no information. Check logs - aborting auto-snatch at this time.')
        snatch_status = 'ERROR'
    else:
        if mylar.USE_DELUGE:
            torrent_status = torrent_info['is_finished']
            torrent_files = torrent_info['num_files']        
            torrent_folder = torrent_info['save_path']
        elif mylar.USE_RTORRENT:
            torrent_status = torrent_info['completed']
            torrent_files = len(torrent_info['files'])
            torrent_folder = torrent_info['folder']

        if all([torrent_status is True, download is True]):
            if not issueid: 
                torrent_info['snatch_status'] = 'STARTING...'
                #yield torrent_info

            import shlex, subprocess
            logger.info('Torrent is completed and status is currently Snatched. Attempting to auto-retrieve.')
            with open(mylar.AUTO_SNATCH_SCRIPT, 'r') as f:
                first_line = f.readline()

            if mylar.AUTO_SNATCH_SCRIPT.endswith('.sh'):
                shell_cmd = re.sub('#!', '', first_line)
                if shell_cmd == '' or shell_cmd is None:
                    shell_cmd = '/bin/bash'
            else:
                shell_cmd = sys.executable

            curScriptName = shell_cmd + ' ' + str(mylar.AUTO_SNATCH_SCRIPT).decode("string_escape")
            if torrent_files > 1:
                downlocation = torrent_folder
            else:
                downlocation = os.path.join(torrent_folder, torrent_info['name'])

            downlocation = re.sub("'", "\\'", downlocation)

            script_cmd = shlex.split(curScriptName, posix=False) + [downlocation]
            logger.fdebug(u"Executing command " +str(script_cmd))
            try:
                p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
                out, err = p.communicate()
                logger.fdebug(u"Script result: " + out)
            except OSError, e:
                logger.warn(u"Unable to run extra_script: " + e)
                snatch_status = 'ERROR'
            else:
                if 'Access failed: No such file' in out:
                    logger.fdebug('Not located in location it is supposed to be in - probably has been moved by some script and I got the wrong location due to timing. Trying again...')
                    snatch_status = 'IN PROGRESS'
                else:
                    snatch_status = 'COMPLETED'
        else:
            if download is True:
                snatch_status = 'IN PROGRESS'
            else:
                snatch_status = 'NOT SNATCHED'

    torrent_info['snatch_status'] = snatch_status
    return torrent_info

def weekly_info(week=None, year=None):
    #find the current week and save it as a reference point.
    todaydate = datetime.datetime.today()
    current_weeknumber = todaydate.strftime("%U")


    if week:
        weeknumber = int(week)
        year = int(year)
        #view specific week (prev_week, next_week)
        startofyear = date(year,1,1)
        week0 = startofyear - timedelta(days=startofyear.isoweekday())
        stweek = datetime.datetime.strptime(week0.strftime('%Y-%m-%d'), '%Y-%m-%d')
        startweek = stweek + timedelta(weeks = weeknumber)
        midweek = startweek + timedelta(days = 3)
        endweek = startweek + timedelta(days = 6)
    else:
        #find the given week number for the current day
        weeknumber = current_weeknumber
        stweek = datetime.datetime.strptime(todaydate.strftime('%Y-%m-%d'), '%Y-%m-%d')
        startweek = stweek - timedelta(days = (stweek.weekday() + 1) % 7)
        midweek = startweek + timedelta(days = 3)
        endweek = startweek + timedelta(days = 6)
        year = todaydate.strftime("%Y")

    prev_week = int(weeknumber) - 1
    prev_year = year
    if prev_week == 0:
        prev_week = 52
        prev_year = int(year) - 1

    next_week = int(weeknumber) + 1
    next_year = year
    if next_week == 53:
        next_week = 1
        next_year = int(year) + 1

    date_fmt = "%B %d, %Y"
    try:
        con_startweek = u"" + startweek.strftime(date_fmt).decode('utf-8')
        con_endweek = u"" + endweek.strftime(date_fmt).decode('utf-8')
    except:
        con_startweek = u"" + startweek.strftime(date_fmt).decode('cp1252')
        con_endweek = u"" + endweek.strftime(date_fmt).decode('cp1252')

    if mylar.WEEKFOLDER_LOC is not None:
        weekdst = mylar.WEEKFOLDER_LOC
    else:
        weekdst = mylar.DESTINATION_DIR

    weekinfo = {'weeknumber':         weeknumber,
                'startweek':          con_startweek,
                'midweek':            midweek.strftime('%Y-%m-%d'),
                'endweek':            con_endweek,
                'year':               year,
                'prev_weeknumber':    prev_week,
                'prev_year':          prev_year,
                'next_weeknumber':    next_week,
                'next_year':          next_year,
                'current_weeknumber': current_weeknumber,
                'last_update':        mylar.PULL_REFRESH}

    if mylar.WEEKFOLDER_FORMAT == 0:
        weekfold = os.path.join(weekdst, str( str(weekinfo['year']) + '-' + str(weeknumber) ))
    else:
        weekfold = os.path.join(weekdst, str( str(weekinfo['midweek']) ))

    weekinfo['week_folder'] = weekfold

    return weekinfo

def latestdate_update():
    import db
    myDB = db.DBConnection()
    ccheck = myDB.select('SELECT a.ComicID, b.IssueID, a.LatestDate, b.ReleaseDate, b.Issue_Number from comics as a left join issues as b on a.comicid=b.comicid where a.LatestDate < b.ReleaseDate or a.LatestDate like "%Unknown%" group by a.ComicID')
    if ccheck is None or len(ccheck) == 0:
        return
    logger.info('Now preparing to update ' + str(len(ccheck)) + ' series that have out-of-date latest date information.')
    ablist = []
    for cc in ccheck:
        ablist.append({'ComicID':     cc['ComicID'],
                       'LatestDate':  cc['ReleaseDate'],
                       'LatestIssue': cc['Issue_Number']})

    #forcibly set the latest date and issue number to the most recent.
    for a in ablist:
        logger.info(a)
        newVal = {'LatestDate':         a['LatestDate'],
                  'LatestIssue':        a['LatestIssue']}
        ctrlVal = {'ComicID':           a['ComicID']}
        logger.info('updating latest date for : ' + a['ComicID'] + ' to ' + a['LatestDate'] + ' #' + a['LatestIssue'])
        myDB.upsert("comics", newVal, ctrlVal)
   
def worker_main(queue):
    while True:
        item = queue.get(True)
        logger.info('Now loading from queue: ' + item)
        if item == 'exit':
            logger.info('Cleaning up workers for shutdown')
            break
        snstat = torrentinfo(torrent_hash=item, download=True)
        if snstat['snatch_status'] == 'IN PROGRESS':
            logger.info('Still downloading in client....let us try again momentarily.')
            time.sleep(15)
            mylar.SNATCHED_QUEUE.put(item)
        
def script_env(mode, vars):
    #mode = on-snatch, pre-postprocess, post-postprocess
    #var = dictionary containing variables to pass
    if mode == 'on-snatch':
        runscript = mylar.SNATCH_SCRIPT
        if 'torrentinfo' in vars:
            os.environ['mylar_release_hash'] = vars['torrentinfo']['hash'] 
            os.environ['mylar_release_name'] = vars['torrentinfo']['name']
            os.environ['mylar_release_folder'] = vars['torrentinfo']['folder']
            if 'label' in vars['torrentinfo']:
                os.environ['mylar_release_label'] = vars['torrentinfo']['label']
            os.environ['mylar_release_filesize'] = str(vars['torrentinfo']['total_filesize'])
            if 'time_started' in vars['torrentinfo']:
                os.environ['mylar_release_start'] = str(vars['torrentinfo']['time_started'])
            if 'filepath' in vars['torrentinfo']:
                os.environ['mylar_torrent_file'] = str(vars['torrentinfo']['filepath'])
            else:
                try:
                    os.environ['mylar_release_files'] = "|".join(vars['torrentinfo']['files'])
                except TypeError:
                    os.environ['mylar_release_files'] = "|".join(json.dumps(vars['torrentinfo']['files']))
        elif 'nzbinfo' in vars:
            os.environ['mylar_release_id'] = vars['nzbinfo']['id']
            os.environ['mylar_release_nzbname'] = vars['nzbinfo']['nzbname']
            os.environ['mylar_release_link'] = vars['nzbinfo']['link']
            os.environ['mylar_release_nzbpath'] = vars['nzbinfo']['nzbpath']
            if 'blackhole' in vars['nzbinfo']:
                os.environ['mylar_release_blackhole'] = vars['nzbinfo']['blackhole']
        os.environ['mylar_release_provider'] = vars['provider']
        if 'comicinfo' in vars:
            try:
                os.environ['mylar_comicid'] = vars['comicinfo']['comicid']  #comicid/issueid are unknown for one-offs (should be fixable tho)
            except:
                pass
            try:
                os.environ['mylar_issueid'] = vars['comicinfo']['issueid']
            except:
                pass
            os.environ['mylar_comicname'] = vars['comicinfo']['comicname']
            os.environ['mylar_issuenumber'] = str(vars['comicinfo']['issuenumber'])
            try:
                os.environ['mylar_comicvolume'] = str(vars['comicinfo']['volume'])
            except:
                pass
            try:
                os.environ['mylar_seriesyear'] = str(vars['comicinfo']['seriesyear'])
            except:
                pass
            try:
                os.environ['mylar_issuedate'] = str(vars['comicinfo']['issuedate'])
            except:
                pass

        os.environ['mylar_release_pack'] = str(vars['pack'])
        if vars['pack'] is True:
            os.environ['mylar_release_pack_numbers'] = vars['pack_numbers']
            os.environ['mylar_release_pack_issuelist'] = vars['pack_issuelist']
        os.environ['mylar_method'] = vars['method']
        os.environ['mylar_client'] = vars['clientmode']

    elif mode == 'post-process':
        #to-do
        runscript = mylar.EXTRA_SCRIPTS
    elif mode == 'pre-process':
        #to-do
        runscript = mylar.PRE_SCRIPTS

    logger.fdebug('Initiating ' + mode + ' script detection.')
    with open(runscript, 'r') as f:
        first_line = f.readline()

    if runscript.endswith('.sh'):
        shell_cmd = re.sub('#!', '', first_line)
        if shell_cmd == '' or shell_cmd is None:
            shell_cmd = '/bin/bash'
    else:
        shell_cmd = sys.executable

    curScriptName = shell_cmd + ' ' + runscript.decode("string_escape")
    logger.fdebug("snatch script detected...enabling: " + str(curScriptName))

    script_cmd = shlex.split(curScriptName)
    logger.fdebug(u"Executing command " +str(script_cmd))
    try:
        subprocess.call(script_cmd, env=dict(os.environ))
    except OSError, e:
        logger.warn(u"Unable to run extra_script: " + str(script_cmd))
        return False
    else:
        return True

def get_the_hash(filepath):
    import hashlib, StringIO
    import bencode
    # Open torrent file
    torrent_file = open(filepath, "rb")
    metainfo = bencode.decode(torrent_file.read())
    info = metainfo['info']
    thehash = hashlib.sha1(bencode.encode(info)).hexdigest().upper()
    logger.info('Hash of file : ' + thehash)
    return {'hash':     thehash}


def file_ops(path,dst,arc=False,one_off=False):
#    # path = source path + filename
#    # dst = destination path + filename
#    # arc = to denote if the file_operation is being performed as part of a story arc or not where the series exists on the watchlist already
#    # one-off = if the file_operation is being performed where it is either going into the grabbab_dst or story arc folder

#    #get the crc of the file prior to the operation and then compare after to ensure it's complete.
#    crc_check = mylar.filechecker.crc(path)
#    #will be either copy / move

    if any([one_off, arc]):
        action_op = mylar.ARC_FILEOPS
    else:
        action_op = mylar.FILE_OPTS

    if action_op == 'copy' or (arc is True and any([action_op == 'copy', action_op == 'move'])):
        try:
            shutil.copy( path , dst )
#        if crc_check == mylar.filechecker.crc(dst):
        except:
            return False
        return True

    elif action_op == 'move':
        try:
            shutil.move( path , dst )
#        if crc_check == mylar.filechecker.crc(dst):
        except:
            return False
        return True

    elif any([action_op == 'hardlink', action_op == 'softlink']):
        if 'windows' not in mylar.OS_DETECT.lower():
            # if it's an arc, then in needs to go reverse since we want to keep the src files (in the series directory)
            if action_op == 'hardlink':
                import sys

                # Open a file
                try:
                    fd = os.open( path, os.O_RDWR|os.O_CREAT )
                    os.close( fd )

                    # Now create another copy of the above file.
                    os.link( path, dst )
                    logger.info('Created hard link successfully!!')
                except OSError, e:
                    if e.errno == errno.EXDEV:
                        logger.warn('[' + str(e) + '] Hardlinking failure. Could not create hardlink - dropping down to copy mode so that this operation can complete. Intervention is required if you wish to continue using hardlinks.')
                        try:
                            shutil.copy( path, dst )
                            logger.fdebug('Successfully copied file to : ' + dst) 
                            return True
                        except:
                            return False
                    else:
                        logger.warn('[' + str(e) + '] Hardlinking failure. Could not create hardlink - Intervention is required if you wish to continue using hardlinks.')
                        return False

                hardlinks = os.lstat( dst ).st_nlink
                if hardlinks > 1:
                    logger.info('Created hard link [' + str(hardlinks) + '] successfully!! (' + dst + ')')
                else:
                    logger.warn('Hardlink cannot be verified. You should probably verify that it is created properly.')

                return True

            elif action_op ==  'softlink':
                try:
                    #first we need to copy the file to the new location, then create the symlink pointing from new -> original
                    if not arc:
                        shutil.move( path, dst )            
                        if os.path.lexists( path ):
                            os.remove( path )
                        os.symlink( dst, path )
                        logger.fdebug('Successfully created softlink [' + dst + ' --> ' + path + ']')
                    else:
                        os.symlink ( path, dst )
                        logger.fdebug('Successfully created softlink [' + path + ' --> ' + dst + ']')
                except OSError, e:
                    #if e.errno == errno.EEXIST:
                    #    os.remove(dst)
                    #    os.symlink( path, dst )
                    #else:
                    logger.warn('[' + str(e) + '] Unable to create symlink. Dropping down to copy mode so that this operation can continue.')
                    try:
                        shutil.copy( dst, path )
                        logger.fdebug('Successfully copied file [' + dst + ' --> ' + path + ']')
                    except:
                        return False

                return True

        else:
            #Not ready just yet.
            pass

            #softlinks = shortcut (normally junctions are called softlinks, but for this it's being called a softlink)
            #hardlinks = MUST reside on the same drive as the original
            #junctions = not used (for directories across same machine only but different drives)

            #option 1
            #this one needs to get tested
            #import ctypes
            #kdll = ctypes.windll.LoadLibrary("kernel32.dll")
            #kdll.CreateSymbolicLinkW(path, dst, 0)

            #option 2
            import lib.winlink as winlink
            if mylar.FILE_OPTS == 'hardlink':
                try:
                    os.system(r'mklink /H dst path')
                    logger.fdebug('Successfully hardlinked file [' + dst + ' --> ' + path + ']')
                except OSError, e:
                    logger.warn('[' + e + '] Unable to create symlink. Dropping down to copy mode so that this operation can continue.')
                    try:
                        shutil.copy( dst, path )
                        logger.fdebug('Successfully copied file [' + dst + ' --> ' + path + ']')
                    except:
                        return False

            elif mylar.FILE_OPTS == 'softlink':  #ie. shortcut.
                try:
                    shutil.move( path, dst )
                    if os.path.lexists( path ):
                        os.remove( path )
                    os.system(r'mklink dst path')
                    logger.fdebug('Successfully created symlink [' + dst + ' --> ' + path + ']')
                except OSError, e:
                    raise e
                    logger.warn('[' + e + '] Unable to create softlink. Dropping down to copy mode so that this operation can continue.')
                    try:
                        shutil.copy( dst, path )
                        logger.fdebug('Successfully copied file [' + dst + ' --> ' + path + ']')
                    except:
                        return False


    else:
        return False


from threading import Thread

class ThreadWithReturnValue(Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs={}, Verbose=None):
        Thread.__init__(self, group, target, name, args, kwargs, Verbose)
        self._return = None
    def run(self):
        if self._Thread__target is not None:
            self._return = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)

    def join(self):
        Thread.join(self)
        return self._return

