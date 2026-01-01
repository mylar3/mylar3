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
import requests
import shlex
import queue
import json
import re
import sys
import ctypes
import platform
import calendar
import itertools
import traceback
import unicodedata
import shutil
import hashlib
import gzip
import os, errno
import urllib
from collections import namedtuple
from urllib.parse import urljoin
from io import StringIO
from apscheduler.triggers.interval import IntervalTrigger
from PIL import Image
from pathlib import Path

import zipfile
from lib.rarfile import rarfile

import mylar
from . import logger
from mylar import db, sabnzbd, nzbget, process, getcomics, getimage
from mylar.downloaders import mega, pixeldrain, mediafire


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
        if ord(i) in xlate:
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

def now(format_string=None):
    now = datetime.datetime.now()
    if format_string is None:
        format_string = "%Y-%m-%d %H:%M:%S"
    return now.strftime(format_string)

def utctimestamp():
    return time.time()

def bytes_to_mb(bytes):

    mb = int(bytes) /1048576
    size = '%.1f MB' % mb
    return size

def utc_date_to_local(run_time):
    pr = (run_time - datetime.datetime.utcfromtimestamp(0)).total_seconds()
    try:
        run_it = datetime.datetime.fromtimestamp(int(pr))
    except Exception as e:
        run_it = datetime.datetime.fromtimestamp(pr)
    return run_it

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
    if num != '0':
        assert float(num) and letter in symbols
        num = float(num)
        prefix = {symbols[0]: 1}
        for i, s in enumerate(symbols[1:]):
            prefix[s] = 1 << (i +1) *10
        return int(num * prefix[letter])
    else:
        return 0

def replace_all(text, dic):
    for i, j in dic.items():
        if all([j != 'None', j is not None]):
            text = text.replace(i, j)
    return text.rstrip()

def cleanName(string):

    pass1 = latinToAscii(string).lower()
    out_string = re.sub('[\/\@\#\$\%\^\*\+\"\[\]\{\}\<\>\=\_]', ' ', pass1) #.encode('utf-8')

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
    except (ValueError, TypeError):
        return False
    else:
        return True

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
            #import db
            myDB = db.DBConnection()
            comicid = str(comicid)   # it's coming in unicoded...

            logger.fdebug(type(comicid))
            logger.fdebug(type(issueid))
            logger.fdebug('comicid: %s' % comicid)
            logger.fdebug('issue# as per cv: %s' % issue)
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
#            logger.fdebug('issueid:' + str(issueid))

            if issueid is None:
                logger.fdebug('annualize is ' + str(annualize))
                if arc:
                    #this has to be adjusted to be able to include story arc issues that span multiple arcs
                    chkissue = myDB.selectone("SELECT * from storyarcs WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()
                else:
                    chkissue = myDB.selectone("SELECT * from issues WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()
                    if all([chkissue is None, annualize is None, not mylar.CONFIG.ANNUALS_ON]):
                        chkissue = myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Issue_Number=? AND NOT Deleted", [comicid, issue]).fetchone()

                if chkissue is None:
                    #rechk chkissue against int value of issue #
                    if arc:
                        chkissue = myDB.selectone("SELECT * from storyarcs WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issue_number_parser(issue).asInt]).fetchone()
                    else:
                        chkissue = myDB.selectone("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issue_number_parser(issue).asInt]).fetchone()
                        if all([chkissue is None, annualize == 'yes', mylar.CONFIG.ANNUALS_ON]):
                            chkissue = myDB.selectone("SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=? AND NOT Deleted", [comicid, issue_number_parser(issue).asInt]).fetchone()

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
                issuenzb = myDB.selectone("SELECT * from storyarcs WHERE ComicID=? AND IssueID=? AND StoryArc=?", [comicid, issueid, arc]).fetchone()
            else:
                issuenzb = myDB.selectone("SELECT * from issues WHERE ComicID=? AND IssueID=?", [comicid, issueid]).fetchone()
                if issuenzb is None:
                    logger.fdebug('not an issue, checking against annuals')
                    issuenzb = myDB.selectone("SELECT * from annuals WHERE ComicID=? AND IssueID=? AND NOT Deleted", [comicid, issueid]).fetchone()
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
                issuenum = issuenzb['Issue_Number']
                issuedate = issuenzb['IssueDate']
                comicnzb= myDB.selectone("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
                publisher = comicnzb['ComicPublisher']
                series = comicnzb['ComicName']
                if any(
                    [
                        comicnzb['AlternateFileName'] is None,
                        comicnzb['AlternateFileName'] == 'None'
                    ]
                ) or all(
                    [
                        comicnzb['AlternateFileName'] is not None,
                        comicnzb['AlternateFileName'].strip() == ''
                    ]
                ):
                    seriesfilename = series
                else:
                    seriesfilename = comicnzb['AlternateFileName']
                    logger.fdebug('Alternate File Naming has been enabled for this series. Will rename series title to : ' + seriesfilename)
                seriesyear = comicnzb['ComicYear']
                comlocation = comicnzb['ComicLocation']
                comversion = comicnzb['ComicVersion']

            unicodeissue = issuenum
            
            prettycomiss = issue_number_parser(issuenum, issue_id=issueid, pretty_string = True).asString
            
            logger.fdebug('Pretty Comic Issue is : ' + str(prettycomiss))
            if mylar.CONFIG.UNICODE_ISSUENUMBER:
                logger.fdebug('Setting this to Unicode format as requested: %s' % prettycomiss)
                prettycomiss = unicodeissue

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
                chunk_f_f = re.sub('\$VolumeN', '', mylar.CONFIG.FILE_FORMAT)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug('No version # found for series, removing from filename')
                logger.fdebug("new format: " + str(chunk_file_format))
            else:
                chunk_file_format = mylar.CONFIG.FILE_FORMAT

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
                           '$Annual':    'Annual'
                          }

            extensions = ('.cbr', '.cbz', '.cb7')

            if ofilename.lower().endswith(extensions):
                path, ext = os.path.splitext(ofilename)

            if mylar.CONFIG.FILE_FORMAT == '':
                logger.fdebug('Rename Files is not enabled - keeping original filename.')
                #check if extension is in nzb_name - will screw up otherwise
                if ofilename.lower().endswith(extensions):
                    nfilename = ofilename[:-4]
                else:
                    nfilename = ofilename
            else:
                nfilename = replace_all(chunk_file_format, file_values)
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


def apiremove(apistring, apitype):
    if apitype == 'nzb':
        value_regex = re.compile("(?<=apikey=)(?P<value>.*?)(?=$)")
        #match = value_regex.search(apistring)
        apiremoved = value_regex.sub("xUDONTNEEDTOKNOWTHISx", apistring)
    else:
        #type = $ to denote end of string
        #type = & to denote up until next api variable
        value_regex1 = re.compile("(?<=%26i=1%26r=)(?P<value>.*?)(?=" + str(apitype) +")")
        #match = value_regex.search(apistring)
        apiremoved1 = value_regex1.sub("xUDONTNEEDTOKNOWTHISx", apistring)
        value_regex = re.compile("(?<=apikey=)(?P<value>.*?)(?=" + str(apitype) +")")
        apiremoved = value_regex.sub("xUDONTNEEDTOKNOWTHISx", apiremoved1)

    #need to remove the urlencoded-portions as well in future
    return apiremoved

def remove_apikey(payd, key):
        #payload = some dictionary with payload values
        #key = the key to replace with REDACTED (normally apikey)
    for k,v in list(payd.items()):
        payd[key] = 'REDACTED'

    return payd

def ComicSort(comicorder=None, sequence=None, imported=None):
    if sequence:
        # if it's on startup, load the sql into a tuple for use to avoid record-locking
        i = 0
        #import db
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
            #logger.fdebug('i: %s' % i)
            if i == 0:
                placemnt = 1
            else:
                placemnt = int(i -1)
            try:
                mylar.COMICSORT['LastOrderNo'] = placemnt
                mylar.COMICSORT['LastOrderID'] = mylar.COMICSORT['SortOrder'][placemnt]['ComicID']
            except Exception:
                comicorder['SortOrder'] = ({'ComicID': '99999', 'ComicOrder': 1})
                mylar.COMICSORT['LastOrderNo'] = 1
                mylar.COMICSORT['LastOrderID'] = 99999
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
        if int(numbs) == int(monthno):
            monthconv = basmonths[numbs]

    return monthconv

def updateComicLocation():
    #in order for this to work, the ComicLocation MUST be left at the original location.
    #in the config.ini - set LOCMOVE = 1  (to enable this to run on the NEXT startup)
    #                  - set NEWCOMDIR = new ComicLocation
    #after running, set ComicLocation to new location in Configuration GUI

    #import db
    myDB = db.DBConnection()
    if mylar.CONFIG.NEWCOM_DIR is not None:
        logger.info('Performing a one-time mass update to Comic Location')
        #create the root dir if it doesn't exist
        checkdirectory = mylar.filechecker.validateAndCreateDirectory(mylar.CONFIG.NEWCOM_DIR, create=True)
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

                if dl['Corrected_Type'] is not None:
                    booktype = dl['Corrected_Type']
                else:
                    booktype = dl['Type']
                if booktype == 'Print' or all([booktype != 'Print', mylar.CONFIG.FORMAT_BOOKTYPE is False]):
                    chunk_fb = re.sub('\$Type', '', mylar.CONFIG.FOLDER_FORMAT)
                    chunk_b = re.compile(r'\s+')
                    chunk_folder_format = chunk_b.sub(' ', chunk_fb)
                else:
                    chunk_folder_format = mylar.CONFIG.FOLDER_FORMAT

                comversion = dl['ComicVersion']
                if comversion is None:
                    comversion = 'None'
                #if comversion is None, remove it so it doesn't populate with 'None'
                if comversion == 'None':
                    chunk_f_f = re.sub('\$VolumeN', '', chunk_folder_format)
                    chunk_f = re.compile(r'\s+')
                    chunk_folder = chunk_f.sub(' ', chunk_f_f)
                else:
                    chunk_folder = chunk_folder_format

                imprint = dl['PublisherImprint']
                if any([imprint is None, imprint == 'None']):
                    chunk_f_f = re.sub('\$Imprint', '', chunk_folder)
                    chunk_f = re.compile(r'\s+')
                    folderformat = chunk_f.sub(' ', chunk_f_f)
                else:
                    folderformat = chunk_folder


                #do work to generate folder path

                values = {'$Series':        comicname_folder,
                          '$Publisher':     publisher,
                          '$Imprint':       imprint,
                          '$Year':          year,
                          '$series':        comicname_folder.lower(),
                          '$publisher':     publisher.lower(),
                          '$VolumeY':       'V' + str(year),
                          '$VolumeN':       comversion,
                          '$Type':          booktype
                          }

                #set the paths here with the seperator removed allowing for cross-platform altering.
                ccdir = re.sub(r'[\\|/]', '%&', mylar.CONFIG.NEWCOM_DIR)
                ddir = re.sub(r'[\\|/]', '%&', mylar.CONFIG.DESTINATION_DIR)
                dlc = re.sub(r'[\\|/]', '%&', dl['ComicLocation'])

                if mylar.CONFIG.FFTONEWCOM_DIR:
                    #if this is enabled (1) it will apply the Folder_Format to all the new dirs
                    if mylar.CONFIG.FOLDER_FORMAT == '':
                        comlocation = re.sub(ddir, ccdir, dlc).strip()
                    else:
                        first = replace_all(folderformat, values)
                        if mylar.CONFIG.REPLACE_SPACES:
                            #mylar.CONFIG.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                            first = first.replace(' ', mylar.CONFIG.REPLACE_CHAR)
                        comlocation = os.path.join(mylar.CONFIG.NEWCOM_DIR, first).strip()

                else:
                    #DESTINATION_DIR = /mnt/mediavg/Comics
                    #NEWCOM_DIR = /mnt/mediavg/Comics/Comics-1
                    #dl['ComicLocation'] = /mnt/mediavg/Comics/Batman-(2011)
                    comlocation = re.sub(ddir, ccdir, dlc).strip()

                #regenerate the new path location so that it's os.dependent now.
                try:
                    com_done = re.sub('%&', os.sep.encode().decode('unicode-escape'), comlocation).strip()
                except Exception as e:
                    logger.warn('[%s] error during conversion: %s' % (comlocation, e))
                    com_done = comlocation.replace('%&', os.sep).strip()

                comloc.append({"comlocation":  com_done,
                               "origlocation": dl['ComicLocation'],
                               "comicid":      dl['ComicID']})

            if len(comloc) > 0:
                #give the information about what we're doing.
                if mylar.CONFIG.FFTONEWCOM_DIR:
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
        mylar.CONFIG.LOCMOVE = False
        mylar.CONFIG.writeconfig(values={'locmove': False})
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

    soup = BeautifulSoup(raw_html, "html.parser")

    for tag in soup.findAll('p'):
        if tag.name not in VALID_TAGS:
            tag.replaceWith(tag.renderContents())
    flipflop = soup.renderContents()
    print(flipflop)
    return flipflop


def checkthepub(ComicID):
    #import db
    myDB = db.DBConnection()
    publishers = ['marvel', 'dc', 'darkhorse']
    pubchk = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [ComicID]).fetchone()
    if pubchk is None:
        logger.fdebug('No publisher information found to aid in determining series..defaulting to base check of 55 days.')
        return mylar.CONFIG.BIGGIE_PUB
    else:
        for publish in publishers:
            if publish in pubchk['ComicPublisher'].lower():
                #logger.fdebug('Biggie publisher detected - ' + pubchk['ComicPublisher'])
                return mylar.CONFIG.BIGGIE_PUB

        #logger.fdebug('Indie publisher detected - ' + pubchk['ComicPublisher'])
        return mylar.CONFIG.INDIE_PUB

def annual_update():
    #import db
    myDB = db.DBConnection()
    annuallist = myDB.select('SELECT * FROM annuals WHERE NOT Deleted')
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
            print("done.")
            break
        f.write(data)
        print("Read %s bytes"%len(data))

def renamefile_readingorder(readorder):
    logger.fdebug('readingorder#: ' + str(readorder))
    if int(readorder) < 10: readord = "00" + str(readorder)
    elif int(readorder) >= 10 and int(readorder) <= 99: readord = "0" + str(readorder)
    else: readord = str(readorder)

    return readord

def latestdate_fix():
    #import db
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
        try:
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
        except:
            datefix.append({"comicid":    cl['ComicID'],
                            "latestdate": '0000-00-00'})

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
    #import db
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

    #update the storyarcsdb to include the Dynamic Names (and any futher changes as required)
    dynamic_storylist = []
    rlist = myDB.select('SELECT * FROM storyarcs WHERE StoryArcID is not NULL')
    for rl in rlist:
        rl_d = mylar.filechecker.FileChecker(watchcomic=rl['ComicName'])
        rl_dyninfo = cl_d.dynamic_replace(rl['ComicName'])
        dynamic_storylist.append({'DynamicComicName': re.sub('[\|\s]','', rl_dyninfo['mod_seriesname'].lower()).strip(),
                                  'IssueArcID':          rl['IssueArcID']})

    if len(dynamic_storylist) > 0:
        for ds in dynamic_storylist:
            CtrlVal = {"IssueArcID": ds['IssueArcID']}
            newVal = {"DynamicComicName": ds['DynamicComicName']}
            myDB.upsert("storyarcs", newVal, CtrlVal)   

    logger.info('Finished updating ' + str(len(dynamic_comiclist)) + ' / ' + str(len(dynamic_storylist)) + ' entries within the db.')
    mylar.CONFIG.DYNAMIC_UPDATE = 4
    mylar.CONFIG.writeconfig()
    return

def checkFolder(folderpath=None):
    from mylar import PostProcessor

    queue = queue.Queue()
    #monitor a selected folder for 'snatched' files that haven't been processed
    if folderpath is None:
        logger.info('Checking folder ' + mylar.CONFIG.CHECK_FOLDER + ' for newly snatched downloads')
        path = mylar.CONFIG.CHECK_FOLDER
    else:
        logger.info('Submitted folder ' + folderpath + ' for direct folder post-processing')
        path = folderpath

    PostProcess = PostProcessor.PostProcessor('Manual Run', path, queue=queue)
    vals = PostProcess.Process()
    return

def LoadAlternateSearchNames(seriesname_alt, comicid):
    #seriesname_alt = db.comics['AlternateSearch']
    AS_Alt = []
    Alternate_Names = {}
    alt_count = 0

    #logger.fdebug('seriesname_alt:' + str(seriesname_alt))
    if seriesname_alt is None or seriesname_alt == 'None':
        return "no results"
    else:
        chkthealt = seriesname_alt.split('##')
        if chkthealt == 0:
            AS_Alternate = seriesname_alt
            AS_Alt.append(seriesname_alt)
        for calt in chkthealt:
            AS_Alter = re.sub('##', '', calt)
            u_altsearchcomic = AS_Alter #.encode('ascii', 'ignore').strip()
            AS_formatrem_seriesname = re.sub('\s+', ' ', u_altsearchcomic)
            if AS_formatrem_seriesname[:1] == ' ': AS_formatrem_seriesname = AS_formatrem_seriesname[1:]

            AS_Alt.append({"AlternateName": AS_formatrem_seriesname})
            alt_count+=1

        Alternate_Names['AlternateName'] = AS_Alt
        Alternate_Names['ComicID'] = comicid
        Alternate_Names['Count'] = alt_count
        logger.info('AlternateNames returned:' + str(Alternate_Names))

        return Alternate_Names

def havetotals(refreshit=None, start_char_filter=None):
        #import db

        comics = []
        myDB = db.DBConnection()

        start_char_where_clause = ''
        if not start_char_filter is None:
            if start_char_filter == '#':
                start_char_where_clause = f"{'WHERE' if refreshit is None else 'AND'} NOT hex(lower(substr(comics.ComicName,1,1))) BETWEEN '61' AND '7A'"
            else:
                start_char_where_clause = f"{'WHERE' if refreshit is None else 'AND'} lower(substr(comics.ComicName,1,1)) = '{start_char_filter.lower()}'"

        if refreshit is None:
            if mylar.CONFIG.ANNUALS_ON:
                comiclist = myDB.select(f"SELECT comics.*, COUNT(totalAnnuals.IssueID) AS TotalAnnuals FROM comics LEFT JOIN annuals as totalAnnuals on totalAnnuals.ComicID = comics.ComicID {start_char_where_clause} GROUP BY comics.ComicID order by comics.ComicSortName COLLATE NOCASE")
            else:
                comiclist = myDB.select(f"SELECT * FROM comics {start_char_where_clause} GROUP BY ComicID order by ComicSortName COLLATE NOCASE")
        else:
            comiclist = []
            comicref = myDB.selectone(f"SELECT comics.ComicID AS ComicID, comics.Have AS Have, comics.Total as Total, COUNT(totalAnnuals.IssueID) AS TotalAnnuals FROM comics LEFT JOIN annuals as totalAnnuals on totalAnnuals.ComicID = comics.ComicID WHERE comics.ComicID=? {start_char_where_clause} GROUP BY comics.ComicID", [refreshit]).fetchone()
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
#                if mylar.CONFIG.ANNUALS_ON:
#                    totalissues += comic['TotalAnnuals']
                haveissues = comic['Have']
            except TypeError:
                logger.warn('[Warning] ComicID: ' + str(comic['ComicID']) + ' is incomplete - Removing from DB. You should try to re-add the series.')
                myDB.action("DELETE from COMICS WHERE ComicID=? AND ComicName LIKE 'Comic ID%'", [comic['ComicID']])
                myDB.action("DELETE from ISSUES WHERE ComicID=? AND ComicName LIKE 'Comic ID%'", [comic['ComicID']])
                continue

            if not haveissues:
                haveissues = 0

            if refreshit is not None:
                if haveissues > totalissues:
                    return True   # if it's 5/4, send back to updater and don't restore previous status'
                else:
                    return False  # if it's 5/5 or 4/5, send back to updater and restore previous status'

            if any([haveissues == 'None', haveissues is None]):
                haveissues = 0
            if any([totalissues == 'None', totalissues is None]):
                totalissues = 0

            try:
                percent = (haveissues *100.0) /totalissues
                if percent > 100:
                    percent = 101
            except (ZeroDivisionError, TypeError):
                percent = 0
                # TODO: This should be turned into an integer (0 or -1 preferably) to avoid issues with downstream expectations that this value is an int.  Need to follow through usages of havetotals()
                totalissues = '?'

            if comic['LatestDate'] is None:
                logger.warn(comic['ComicName'] + ' has not finished loading. Nulling some values so things display properly until they can populate.')
                recentstatus = 'Loading'
            elif comic['ComicPublished'] is None or comic['ComicPublished'] == '' or comic['LatestDate'] is None:
                recentstatus = 'Unknown'
            elif comic['ForceContinuing'] == 1:
                recentstatus = 'Continuing'
            elif 'present' in comic['ComicPublished'].lower() or (today()[:4] in comic['LatestDate']):
                if 'Err' in comic['LatestDate']:
                    recentstatus = 'Loading'
                else:
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

            if recentstatus == 'Loading':
                cpub = comic['ComicPublished']
            else:
                try:
                    cpub = re.sub('(N)', '', comic['ComicPublished']).strip()
                except Exception as e:
                    if comic['cv_removed'] == 0:
                        logger.warn('[Error: %s] No Publisher found for %s - you probably want to Refresh the series when you get a chance.' % (e, comic['ComicName']))
                    cpub = None

            comictype = comic['Type']
            try:
                if (any([comictype == 'None', comictype is None, comictype == 'Print']) and all([comic['Corrected_Type'] != 'TPB', comic['Corrected_Type'] != 'GN', comic['Corrected_Type'] != 'HC'])) or all([comic['Corrected_Type'] is not None, comic['Corrected_Type'] == 'Print']):
                    comictype = None
                else:
                    if comic['Corrected_Type'] is not None:
                        comictype = comic['Corrected_Type']
                    else:
                        comictype = comictype
            except:
                comictype = None

            if any([comic['ComicVersion'] == None, comic['ComicVersion'] == 'None', comic['ComicVersion'] == '']):
                cversion = None
            else:
                cversion = comic['ComicVersion']

            if comic['ComicImage'] is None:
                comicImage = 'cache/%s.jpg' % comic['ComicID']
            else:
                comicImage = comic['ComicImage']

            #cv_removed: 0 = series is present on CV
            #            1 = series has been removed from CV
            #            2 = series has been removed from CV but retaining what mylar has in it's db

            comics.append({"ComicID":         comic['ComicID'],
                           "ComicName":       comic['ComicName'],
                           "ComicSortName":   comic['ComicSortName'],
                           "ComicPublisher":  comic['ComicPublisher'],
                           "ComicYear":       comic['ComicYear'],
                           "ComicImage":      comicImage,
                           "LatestIssue":     comic['LatestIssue'],
                           "IntLatestIssue":  comic['IntLatestIssue'],
                           "LatestDate":      comic['LatestDate'],
                           "ComicVolume":     cversion,
                           "ComicPublished":  cpub,
                           "PublisherImprint": comic['PublisherImprint'],
                           "Status":          comic['Status'],
                           "recentstatus":    recentstatus,
                           "percent":         percent,
                           "totalissues":     totalissues,
                           "haveissues":      haveissues,
                           "DateAdded":       comic['LastUpdated'],
                           "Type":            comic['Type'],
                           "Corrected_Type":  comic['Corrected_Type'],
                           "displaytype":     comictype,
                           "cv_removed":      comic['cv_removed']})
        return comics

def filesafe(comic):
    import unicodedata
    if '\u2014' in comic:
        comic = re.sub('\u2014', ' - ', comic)
    try:
        u_comic = unicodedata.normalize('NFKD', comic).encode('ASCII', 'ignore').strip()
    except TypeError:
        u_comic = comic.encode('ASCII', 'ignore').strip()

    #logger.info('comic-type: %s' % type(u_comic))

    if type(u_comic) != bytes:
        comicname_filesafe = re.sub('[\:\'\"\,\?\!\\\]', '', u_comic)
        comicname_filesafe = re.sub('[\/\*]', '-', comicname_filesafe)
    else:
        comicname_filesafe = re.sub('[\:\'\"\,\?\!\\\]', '', u_comic.decode('utf-8'))
        comicname_filesafe = re.sub('[\/\*]', '-', comicname_filesafe)

    return comicname_filesafe

def IssueDetails(filelocation, IssueID=None, justinfo=False, comicname=None):
    import zipfile
    from xml.dom.minidom import parseString

    issuedetails = []
    issuetag = None
    if any([filelocation == 'None', filelocation is None]):
        issue_data = mylar.cv.getComic(None, 'single_issue', IssueID)
        IssueImage = getimage.retrieve_image(issue_data['image'])
        metadata_info = {'metadata_source': 'ComicVine',
                         'metadata_type': None}
        return {'metadata': issue_data, 'datamode': 'single_issue', 'IssueImage': IssueImage, 'metadata_source': metadata_info }
    #else:
    #    filelocation = urllib.parse.unquote_plus(filelocation)
    if justinfo is False:
        file_info = getimage.extract_image(filelocation, single=True, imquality='issue', comicname=comicname)
        IssueImage = file_info['ComicImage']
        data = file_info['metadata']
        if data:
            issuetag = 'xml'
            metadata_type = 'comicinfo.xml'
    else:
        IssueImage = "None"
        try:
            with zipfile.ZipFile(filelocation, 'r') as inzipfile:
                for infile in sorted(inzipfile.namelist()):
                    if infile == 'ComicInfo.xml':
                        logger.fdebug('Found ComicInfo.xml - now retrieving information.')
                        data = inzipfile.read(infile)
                        issuetag = 'xml'
                        metadata_type = 'comicinfo.xml'
                        break
        except:
            metadata_info = {'metadata_source': None,
                             'metadata_type': None}
            logger.info('ERROR. Unable to properly retrieve the cover for displaying. It\'s probably best to re-tag this file.')
            return {'IssueImage': IssueImage, 'datamode': 'file', 'metadata': None, 'metadata_source': metadata_info}


    if issuetag is None:
        data = None
        try:
            dz = zipfile.ZipFile(filelocation, 'r')
            data = dz.comment
        except:
            metadata_info = {'metadata_source': 'ComicVine',
                             'metadata_type': None}
            logger.warn('Unable to extract any metadata from within file.')
            return {'IssueImage': IssueImage, 'datamode': 'file', 'metadata': None, 'metadata_source': metadata_info}
        else:
            if data:
                issuetag = 'comment'
                metadata_info = {'metadata_source': 'ComicVine',
                                 'metadata_type': 'comicbooklover'}

            else:
                metadata_info = {'metadata_source': None,
                                  'metadata_type': None}
                logger.warn('No metadata available in zipfile comment field.')
                return {'IssueImage': IssueImage, 'datamode': 'file', 'metadata': None, 'metadata_source': metadata_info}

    logger.info('Tag returned as being: ' + str(issuetag))

    if issuetag == 'xml':
        #import easy to use xml parser called minidom:
        dom = parseString(data)

        results = dom.getElementsByTagName('ComicInfo')
        metadata_info = {'metadata_source': None,
                         'metadata_type': 'comicinfo.xml'}

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
            else:
                if 'CMXID' in notes:
                    mtype = 'Comixology'
                elif any(['cvdb' in notes.lower(), 'issue id' in notes.lower(), 'comic vine' in notes.lower()]):
                    mtype = 'ComicVine'
                else:
                    mtype = None
                metadata_info = {'metadata_source': mtype,
                                 'metadata_type': 'comicinfo.xml'}
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
                writer = None
            try:
                penciller = result.getElementsByTagName('Penciller')[0].firstChild.wholeText
            except:
                penciller = None
            try:
                inker = result.getElementsByTagName('Inker')[0].firstChild.wholeText
            except:
                inker = None
            try:
                colorist = result.getElementsByTagName('Colorist')[0].firstChild.wholeText
            except:
                colorist = None
            try:
                letterer = result.getElementsByTagName('Letterer')[0].firstChild.wholeText
            except:
                letterer = None
            try:
                cover_artist = result.getElementsByTagName('CoverArtist')[0].firstChild.wholeText
            except:
                cover_artist = None
            try:
                editor = result.getElementsByTagName('Editor')[0].firstChild.wholeText
            except:
                editor = None
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
        data = re.sub(stripline, '', data.decode('utf-8')) #.strip() #.encode("utf-8")).strip()
        if data is None or data == '':
            return {'IssueImage': IssueImage}
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

        editor = None
        colorist = None
        artist = None
        writer = None
        letterer = None
        cover_artist = None
        penciller = None
        inker = None

        try:
            series_volume = dt['volume']
        except:
            series_volume = None

        try:
            t = dt['credits']
        except:
            pass
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

    return  {'metadata': {"title":        issue_title,
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
             "pagecount":    pagecount},
             "IssueImage":   IssueImage,
             "datamode":     'file',
             "metadata_source": metadata_info}

def get_issue_title(IssueID=None, ComicID=None, IssueNumber=None, IssueArcID=None):
    #import db
    myDB = db.DBConnection()
    if IssueID:
        issue = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
        if issue is None:
            issue = myDB.selectone('SELECT * FROM annuals WHERE IssueID=?', [IssueID]).fetchone()
            if issue is None:
                logger.fdebug('Unable to locate given IssueID within the db. Assuming Issue Title is None.')
                return None
    else:
        issue = myDB.selectone('SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?', [ComicID, issue_number_parser(issue).asInt]).fetchone()
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

def listPull(weeknumber, year):
    #import db
    library = {}
    myDB = db.DBConnection()
    # Get individual comics
    list = myDB.select("SELECT ComicID FROM Weekly WHERE weeknumber=? AND year=?", [weeknumber,year])
    for row in list:
        library[row['ComicID']] = row['ComicID']
    return library

def listLibrary(comicid=None):
    #import db
    library = {}
    myDB = db.DBConnection()
    if comicid is None:
        if mylar.CONFIG.ANNUALS_ON is True:
            list = myDB.select("SELECT a.comicid, b.releasecomicid, a.status FROM Comics AS a LEFT JOIN annuals AS b on a.comicid=b.comicid group by a.comicid, b.releasecomicid")
        else:
            list = myDB.select("SELECT comicid, status FROM Comics group by comicid")
    else:
        if mylar.CONFIG.ANNUALS_ON is True:
            list = myDB.select("SELECT a.comicid, b.releasecomicid, a.status FROM Comics AS a LEFT JOIN annuals AS b on a.comicid=b.comicid WHERE a.comicid=? group by a.comicid, b.releasecomicid", [re.sub('4050-', '', comicid).strip()])
        else:
            list = myDB.select("SELECT comicid, status FROM Comics WHERE comicid=? group by comicid", [re.sub('4050-', '', comicid).strip()])

    for row in list:
        library[row['ComicID']] = {'comicid':        row['ComicID'],
                                   'status':         row['Status']}
        try:
            if row['ReleaseComicID'] is not None:
                library[row['ReleaseComicID']] = {'comicid':   row['ComicID'],
                                                  'status':    row['Status']}
        except:
            pass

    return library

def listStoryArcs():
    #import db
    library = {}
    myDB = db.DBConnection()
    # Get Distinct Arc IDs
    #list = myDB.select("SELECT DISTINCT(StoryArcID) FROM storyarcs");
    #for row in list:
    #    library[row['StoryArcID']] = row['StoryArcID']
    # Get Distinct CV Arc IDs
    list = myDB.select("SELECT DISTINCT(CV_ArcID) FROM storyarcs");
    for row in list:
        library[row['CV_ArcID']] = {'comicid': row['CV_ArcID']}
    return library

def listoneoffs(weeknumber, year):
    #import db
    library = []
    myDB = db.DBConnection()
    # Get Distinct one-off issues from the pullist that have already been downloaded / snatched
    list = myDB.select("SELECT DISTINCT(IssueID), Status, ComicID, ComicName, Status, IssueNumber FROM oneoffhistory WHERE weeknumber=? and year=? AND Status='Downloaded' OR Status='Snatched'", [weeknumber, year])
    for row in list:
        library.append({'IssueID':     row['IssueID'],
                        'ComicID':     row['ComicID'],
                        'ComicName':   row['ComicName'],
                        'IssueNumber': row['IssueNumber'],
                        'Status':      row['Status'],
                        'weeknumber':  weeknumber,
                        'year':        year})
    return library

def manualArc(issueid, reading_order, storyarcid):
    #import db
    if issueid.startswith('4000-'):
        issueid = issueid[5:]

    myDB = db.DBConnection()

    arc_chk = myDB.select("SELECT * FROM storyarcs WHERE StoryArcID=? AND NOT Manual is 'deleted'", [storyarcid])
    storyarcname = arc_chk[0]['StoryArc']
    storyarcissues = arc_chk[0]['TotalIssues']

    iss_arcids = []
    for issarc in arc_chk:
        iss_arcids.append({"IssueArcID":     issarc['IssueArcID'],
                           "IssueID":        issarc['IssueID'],
                           "Manual":         issarc['Manual'],
                           "ReadingOrder":   issarc['ReadingOrder']})


    arc_results = mylar.cv.getComic(comicid=None, rtype='issue', issueid=None, arcid=storyarcid, arclist='M' + str(issueid))
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
    int_issnum = issue_number_parser(issnum).asInt

    comicid_results = mylar.cv.getComic(comicid=None, rtype='comicyears', comicidlist=cidlist)
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
               "ReleaseDate":       storedate,
               "SeriesYear":        seriesYear,
               "IssuePublisher":    issuePublisher,
               "CV_ArcID":          storyarcid,
               "Int_IssueNumber":   int_issnum,
               "Manual":            manual_mod}

    myDB.upsert("storyarcs", newVals, newCtrl)

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

        myDB.upsert("storyarcs", r1_new, rl_ctrl)

    #check to see if the issue exists already so we can set the status right away.
    iss_chk = myDB.selectone('SELECT * FROM issues where issueid = ?', [issueid]).fetchone()
    if iss_chk is None:
        logger.info('Issue is not currently in your watchlist. Setting status to Skipped')
        status_change = 'Skipped'
    else:
        status_change = iss_chk['Status']
        logger.info('Issue currently exists in your watchlist. Setting status to ' + status_change)
        myDB.upsert("storyarcs", {'Status': status_change}, newCtrl)

    return

def listIssues(weeknumber, year):
    #import db
    library = []
    myDB = db.DBConnection()
    # Get individual issues
    list = myDB.select("SELECT issues.Status, issues.ComicID, issues.IssueID, issues.ComicName, issues.IssueDate, issues.ReleaseDate, weekly.publisher, issues.Issue_Number from weekly, issues where weekly.IssueID = issues.IssueID and weeknumber = ? and year = ?", [int(weeknumber), year])
    for row in list:
        if row['ReleaseDate'] is None:
            tmpdate = row['IssueDate']
        else:
            tmpdate = row['ReleaseDate']
        library.append({'ComicID': row['ComicID'],
                        'Status':  row['Status'],
                        'IssueID': row['IssueID'],
                        'ComicName': row['ComicName'],
                        'Publisher': row['publisher'],
                        'Issue_Number': row['Issue_Number'],
                        'IssueYear': tmpdate})

    # Add the annuals
    if mylar.CONFIG.ANNUALS_ON:
        list = myDB.select("SELECT annuals.Status, annuals.ComicID, annuals.ReleaseComicID, annuals.IssueID, annuals.ComicName, annuals.ReleaseDate, annuals.IssueDate, weekly.publisher, annuals.Issue_Number from weekly, annuals where weekly.IssueID = annuals.IssueID and weeknumber = ? and year = ?", [int(weeknumber), year])
        for row in list:
            if row['ReleaseDate'] is None:
                tmpdate = row['IssueDate']
            else:
                tmpdate = row['ReleaseDate']
            library.append({'ComicID': row['ComicID'],
                            'Status':  row['Status'],
                            'IssueID': row['IssueID'],
                            'ComicName': row['ComicName'],
                            'Publisher': row['publisher'],
                            'Issue_Number': row['Issue_Number'],
                            'IssueYear': tmpdate})

    #tmplist = library
    #librarylist = []
    #for liblist in tmplist:
    #    lb = myDB.select('SELECT ComicVersion, Type, ComicYear, ComicID from comics WHERE ComicID=?', [liblist['ComicID']])
    #    librarylist.append(liblist)
    #    librarylist.update({'Comic_Volume': lb['ComicVersion'],
    #                        'ComicYear': lb['ComicYear'],
    #                        'ComicType': lb['Type']})
    return library

def incr_snatched(ComicID):
    #import db
    myDB = db.DBConnection()
    incr_count = myDB.selectone("SELECT Have FROM Comics WHERE ComicID=?", [ComicID]).fetchone()
    logger.fdebug('Incrementing HAVE count total to : ' + str(incr_count['Have'] + 1))
    newCtrl = {"ComicID":    ComicID}
    newVal = {"Have":  incr_count['Have'] + 1}
    myDB.upsert("comics", newVal, newCtrl)
    return

def duplicate_filecheck(filename, ComicID=None, IssueID=None, StoryArcID=None, rtnval=None):
    #filename = the filename in question that's being checked against
    #comicid = the comicid of the series that's being checked for duplication
    #issueid = the issueid of the issue that's being checked for duplication
    #storyarcid = the storyarcid of the issue that's being checked for duplication.
    #rtnval = the return value of a previous duplicate_filecheck that's re-running against new values
    #
    #import db
    myDB = db.DBConnection()

    logger.info('[DUPECHECK] Duplicate check for ' + filename)
    try:
        filesz = os.path.getsize(filename)
    except OSError as e:
        logger.warn('[DUPECHECK] File cannot be located in location specified. Something has moved or altered the name.')
        logger.warn('[DUPECHECK] Make sure if you are using ComicRN, you do not have Completed Download Handling enabled (or vice-versa). Aborting')
        return {'action': None}

    if IssueID:
        dupchk = myDB.selectone("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
    if dupchk is None:
        dupchk = myDB.selectone("SELECT * FROM annuals WHERE IssueID=? AND NOT Deleted", [IssueID]).fetchone()
        if dupchk is None:
            logger.info('[DUPECHECK] Unable to find corresponding Issue within the DB. Do you still have the series on your watchlist?')
            return {'action': None}

    series = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [dupchk['ComicID']]).fetchone()

    #if it's a retry and the file was already snatched, the status is Snatched and won't hit the dupecheck.
    #rtnval will be one of 3:
    #'write' - write new file
    #'dupe_file' - do not write new file as existing file is better quality
    #'dupe_src' - write new file, as existing file is a lesser quality (dupe)

    if dupchk['Status'] == 'Downloaded' or dupchk['Status'] == 'Archived':
        try:
            dupsize = dupchk['ComicSize']
        except:
            logger.info('[DUPECHECK] Duplication detection returned no hits as this is a new Snatch. This is not a duplicate.')
            rtnval = {'action':  "write"}

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
                    if rtnval is not None:
                        if rtnval['action'] == 'dont_dupe':
                            logger.fdebug('[DUPECHECK] File is Archived but no file can be located within the db at the specified location. Assuming this was a manual archival and will not post-process this issue.')
                        return rtnval
                    else:
                        rtnval = {'action':  "dont_dupe"}
                        #file is Archived, but no entry exists in the db for the location. Assume Archived, and don't post-process.
                        #quick rescan of files in dir, then rerun the dup check again...
                        mylar.updater.forceRescan(ComicID)
                        chk1 = duplicate_filecheck(filename, ComicID, IssueID, StoryArcID, rtnval)
                        rtnval = chk1
            else:
                rtnval = {'action':  "dupe_file",
                          'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])}
        else:
            logger.info('[DUPECHECK] Existing file within db :' + dupchk['Location'] + ' has a filesize of : ' + str(dupsize) + ' bytes.')

            #keywords to force keep / delete
            #this will be eventually user-controlled via the GUI once the options are enabled.
            fixed = False
            fixed_file = re.findall(r'[(]f\d{1}[)]', filename.lower())
            fixed_db_file = re.findall(r'[(]f\d{1}[)]', dupchk['Location'].lower())
            if all([fixed_file, not fixed_db_file]):
                logger.info('[DUPECHECK] %s is a "Fixed" version that should be retained over existing version. Bypassing filesize/filetype check.' % filename)
                fixed = True
                rtnval = {'action':  "dupe_src",
                              'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])}
            elif all([fixed_db_file, not fixed_file]):
                logger.info('[DUPECHECK] %s is a "Fixed" version that should be retained over newly aquired version. Bypassing filesize/filetype check.' % filename)
                fixed = True
                rtnval = {'action':  "dupe_file",
                              'to_dupe': filename}
            elif all([fixed_file, fixed_db_file]):
                ff_int = int(re.sub('[^0-9]', '', fixed_file).strip())
                fdf_int = int(re.sub('[^0-9]', '', fixed_db_file).strip())
                if ff_int > fdf_int:
                    logger.info('[DUPECHECK] %s is a higher "Fixed" version (%s) that should be retained over existing version(%s). Bypassing filesize/filetype check.' % (fixed_file, fixed_db_file, filename))
                    fixed = True
                    rtnval = {'action':  "dupe_src",
                              'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])}
                else:
                    logger.info('[DUPECHECK] %s is a higher "Fixed" version (%s) that should be retained over existing version(%s). Bypassing filesize/filetype check.' % (fixed_db_file, fixed_file, os.path.join(series['ComicLocation'], dupehk['Location'])))
                    fixed = True
                    rtnval = {'action':  "dupe_file",
                              'to_dupe': filename}

            elif int(dupsize) == 0:
                logger.info('[DUPECHECK] Existing filesize is 0 as I cannot locate the original entry.')
                if dupchk['Status'] == 'Archived':
                    logger.info('[DUPECHECK] Assuming issue is Archived.')
                    rtnval = {'action':  "dupe_file",
                              'to_dupe': filename}
                    return rtnval
                else:
                    logger.info('[DUPECHECK] Assuming 0-byte file - this one is gonna get hammered.')

            logger.fdebug('[DUPECHECK] Based on duplication preferences I will retain based on : ' + mylar.CONFIG.DUPECONSTRAINT)

            tmp_dupeconstraint = mylar.CONFIG.DUPECONSTRAINT

            if any(['cbr' in mylar.CONFIG.DUPECONSTRAINT, 'cbz' in mylar.CONFIG.DUPECONSTRAINT]) and not fixed:
                if 'cbr' in mylar.CONFIG.DUPECONSTRAINT:
                    if filename.endswith('.cbr'):
                        #this has to be configured in config - either retain cbr or cbz.
                        if dupchk['Location'].endswith('.cbr'):
                            logger.info('[DUPECHECK-CBR PRIORITY] [#' + dupchk['Issue_Number'] + '] BOTH files are in cbr format. Retaining the larger filesize of the two.')
                            tmp_dupeconstraint = 'filesize'
                        else:
                            #keep filename
                            logger.info('[DUPECHECK-CBR PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining newly scanned in file : ' + filename)
                            rtnval = {'action':  "dupe_src",
                                      'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])}
                    else:
                        if dupchk['Location'].endswith('.cbz'):
                            logger.info('[DUPECHECK-CBR PRIORITY] [#' + dupchk['Issue_Number'] + '] BOTH files are in cbz format. Retaining the larger filesize of the two.')
                            tmp_dupeconstraint = 'filesize'
                        else:
                            #keep filename
                            logger.info('[DUPECHECK-CBR PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining newly scanned in file : ' + dupchk['Location'])
                            rtnval = {'action':  "dupe_file",
                                      'to_dupe': filename}

                elif 'cbz' in mylar.CONFIG.DUPECONSTRAINT:
                    if filename.endswith('.cbr'):
                        if dupchk['Location'].endswith('.cbr'):
                            logger.info('[DUPECHECK-CBZ PRIORITY] [#' + dupchk['Issue_Number'] + '] BOTH files are in cbr format. Retaining the larger filesize of the two.')
                            tmp_dupeconstraint = 'filesize'
                        else:
                            #keep filename
                            logger.info('[DUPECHECK-CBZ PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining currently scanned in filename : ' + dupchk['Location'])
                            rtnval = {'action':  "dupe_file",
                                      'to_dupe': filename}
                    else:
                        if dupchk['Location'].endswith('.cbz'):
                            logger.info('[DUPECHECK-CBZ PRIORITY] [#' + dupchk['Issue_Number'] + '] BOTH files are in cbz format. Retaining the larger filesize of the two.')
                            tmp_dupeconstraint = 'filesize'
                        else:
                            #keep filename
                            logger.info('[DUPECHECK-CBZ PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining newly scanned in filename : ' + filename)
                            rtnval = {'action':  "dupe_src",
                                      'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])}

            if not fixed and (mylar.CONFIG.DUPECONSTRAINT == 'filesize' or tmp_dupeconstraint == 'filesize'):
                if filesz <= int(dupsize) and int(dupsize) != 0:
                    logger.info('[DUPECHECK-FILESIZE PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining currently scanned in filename : ' + dupchk['Location'])
                    rtnval = {'action':  "dupe_file",
                              'to_dupe': filename}
                else:
                    logger.info('[DUPECHECK-FILESIZE PRIORITY] [#' + dupchk['Issue_Number'] + '] Retaining newly scanned in filename : ' + filename)
                    rtnval = {'action':  "dupe_src",
                              'to_dupe': os.path.join(series['ComicLocation'], dupchk['Location'])}

    else:
        logger.info('[DUPECHECK] Duplication detection returned no hits. This is not a duplicate of anything that I have scanned in as of yet.')
        rtnval = {'action':  "write"}
    return rtnval

def create_https_certificates(ssl_cert, ssl_key):
    """
    Create a pair of self-signed HTTPS certificares and store in them in
    'ssl_cert' and 'ssl_key'. Method assumes pyOpenSSL is installed.

    This code is stolen from SickBeard (http://github.com/midgetspy/Sick-Beard).
    """

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
    #elif site == 'TPSE':
    #    if alt is None:
    #        url = mylar.TPSEURL + 'torrent/' + str(linkid) + '.torrent'
    #    else:
    #        url = mylar.TPSEURL + 'torrent/' + str(linkid) + '.torrent'
    elif site == 'DEM':
        url = mylar.DEMURL + 'files/download/' + str(linkid) + '/'
    elif site == 'WWT':
        url = mylar.WWTURL + 'download.php'

    return url

def parse_32pfeed(rssfeedline):
    KEYS_32P = {}
    if mylar.CONFIG.ENABLE_32P and len(rssfeedline) > 1:
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
                    "passkey": mylar.CONFIG.PASSKEY_32P}

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

        unit = list(map(lambda a: a[1], NAMES)).index(units)
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
    #import db
    myDB = db.DBConnection()

    IssueID = str(IssueID)

#    logger.fdebug('[ISSUE-STATUS] Issue Status Check for %s' % IssueID)

    isschk = myDB.selectone("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
    if isschk is None:
        isschk = myDB.selectone("SELECT * FROM annuals WHERE IssueID=? AND NOT Deleted", [IssueID]).fetchone()
        if isschk is None:
            isschk = myDB.selectone("SELECT * FROM storyarcs WHERE IssueArcID=?", [IssueID]).fetchone()
            if isschk is None:
                logger.warn('Unable to retrieve IssueID from db. This is a problem. Aborting.')
                return False

    if any([isschk['Status'] == 'Downloaded', isschk['Status'] == 'Snatched']):
        return True
    else:
        return False

def crc(filename):
    #memory in lieu of speed (line by line)
    #prev = 0
    #for eachLine in open(filename,"rb"):
    #    prev = zlib.crc32(eachLine, prev)
    #return "%X"%(prev & 0xFFFFFFFF)

    #speed in lieu of memory (file into memory entirely)
    #return "%X" % (zlib.crc32(open(filename, "rb").read()) & 0xFFFFFFFF)
    try:
       filename = filename.encode(mylar.SYS_ENCODING)
    except UnicodeEncodeError:
       filename = "invalid"
       filename = filename.encode(mylar.SYS_ENCODING)

    return hashlib.md5(filename).hexdigest()

def issue_find_ids(ComicName, ComicID, pack, IssueNumber, pack_id):

    #logger.fdebug('pack: %s' % pack)
    myDB = db.DBConnection()

    issuelist = myDB.select("SELECT * FROM issues WHERE ComicID=?", [ComicID])

    if 'Annual' not in pack:
        if ',' not in pack:
            packlist = pack.split(' ')
            pack = re.sub('#', '', pack).strip()
        else:
            packlist = [x.strip() for x in pack.split(',')]
        plist = []
        pack_issues = []
        logger.fdebug('packlist: %s' % packlist)
        for pl in packlist:
            pl = re.sub('#', '', pl).strip()
            if '-' in pl:
                le_range = list(range(int(pack[:pack.find('-')]),int(pack[pack.find('-')+1:])+1))
                for x in le_range:
                    if not [y for y in plist if y == x]:
                        plist.append(int(x))
                #logger.fdebug('plist: %s' % plist)
            else:
                #logger.fdebug('starting single: %s' % pl)
                if not [x for x in plist if x == int(pl)]:
                    #logger.fdebug('single not present')
                    plist.append(int(pl))
            #logger.fdebug('plist:%s' % plist)

        for pi in plist:
            if type(pi) == list:
                for x in pi:
                    pack_issues.append(x)
            else:
                pack_issues.append(pi)

        pack_issues.sort()
        annualize = False
    else:
        #remove the annuals wording
        tmp_annuals = pack[pack.find('Annual'):]
        tmp_ann = re.sub('[annual/annuals/+]', '', tmp_annuals.lower()).strip()
        tmp_pack = re.sub('[annual/annuals/+]', '', pack.lower()).strip()
        pack_issues_numbers = re.findall(r'\d+', tmp_pack)
        pack_issues = list(range(int(pack_issues_numbers[0]),int(pack_issues_numbers[1])+1))
        annualize = True

    issues = {}
    issueinfo = []
    write_valids = []  # to keep track of snatched packs already downloading so we don't re-queue/download again

    Int_IssueNumber = issue_number_parser(IssueNumber).asInt
    valid = False

    ignores = []
    for iss in pack_issues:
       int_iss = issue_number_parser(str(iss)).asInt
       for xb in issuelist:
           if xb['Status'] != 'Downloaded':
               if xb['Int_IssueNumber'] == int_iss:
                   if Int_IssueNumber == xb['Int_IssueNumber']:
                       valid = True
                   issueinfo.append({'issueid':      xb['IssueID'],
                                     'int_iss':      int_iss,
                                     'issuenumber':  xb['Issue_Number']})

                   write_valids.append({'issueid': xb['IssueID'],
                                        'pack_id': pack_id})
                   break
           else:
               ignores.append(iss)

    if ignores:
        logger.info('[%s] These issues already exist in the pack and is already in a Downloaded state. Mark the issue as anything'
                    'other than Wanted if you want the pack to be downloaded.' % ignores)

    if valid:
        for wv in write_valids:
            mylar.PACK_ISSUEIDS_DONT_QUEUE[wv['issueid']] = wv['pack_id']

    issues['issues'] = issueinfo
    logger.fdebug('pack_issueids_dont_queue: %s' % mylar.PACK_ISSUEIDS_DONT_QUEUE)

    if len(issues['issues']) == len(pack_issues):
        logger.fdebug('Complete issue count of %s issues are available within this pack for %s' % (len(pack_issues), ComicName))
    else:
        logger.fdebug('Issue counts are not complete (not a COMPLETE pack) for %s' % ComicName)

    issues['issue_range'] = pack_issues
    issues['valid'] = valid
    return issues

def reverse_the_pack_snatch(pack_id, comicid):
    logger.info('[REVERSE UNO] Reversal of issues marked as Snatched via pack download reversing due to invalid link retrieval..')
    #logger.fdebug(mylar.PACK_ISSUEIDS_DONT_QUEUE)
    reverselist = [issueid for issueid, packid in mylar.PACK_ISSUEIDS_DONT_QUEUE.items() if pack_id == packid]
    myDB = db.DBConnection()
    for x in reverselist:
        myDB.upsert("issues", {"Status": "Skipped"}, {"IssueID": x})
    if reverselist:
        logger.info('[REVERSE UNO] Reversal completed for %s issues' % len(reverselist))
        mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicid': comicid, 'tables': 'both', 'message': 'Successfully changed status of %s issues to %s' % (len(reverselist), 'Skipped')}


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
    return [seq[pos:pos + size] for pos in range(0, len(seq), size)]

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
    #import db
    myDB = db.DBConnection()
    if not up_vals:
        chk = myDB.selectone("SELECT * from ref32p WHERE ComicID=?", [comicid]).fetchone()
        if chk is None:
           return None
        else:
           #if updated time hasn't been set or it's > 24 hrs, blank the entry so we can make sure we pull an updated groupid from 32p
           if chk['Updated'] is None:
               logger.fdebug('Reference found for 32p - but the id has never been verified after populating. Verifying it is still the right id before proceeding.')
               return None
           else:
               c_obj_date = datetime.datetime.strptime(chk['Updated'], "%Y-%m-%d %H:%M:%S")
               n_date = datetime.datetime.now()
               absdiff = abs(n_date - c_obj_date)
               hours = (absdiff.days * 24 * 60 * 60 + absdiff.seconds) / 3600.0
               if hours >= 24:
                   logger.fdebug('Reference found for 32p - but older than 24hours since last checked. Verifying it is still the right id before proceeding.')
                   return None
               else:
                   return {'id':     chk['ID'],
                           'series': chk['Series']}

    else:
        ctrlVal = {'ComicID':     comicid}
        newVal =  {'Series':      up_vals[0]['series'],
                   'ID':          up_vals[0]['id'],
                   'Updated':     now()}
        myDB.upsert("ref32p", newVal, ctrlVal)

def updatearc_locs(storyarcid, issues):
    #import db
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
                    try:
                        if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                            if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(chk['ComicLocation']))):
                                secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(chk['ComicLocation']))
                            else:
                                ff = mylar.filers.FileHandlers(ComicID=chk['ComicID'])
                                secondary_folders = ff.secondary_folders(chk['ComicLocation'])

                            pathsrc = os.path.join(secondary_folders, chk['Location'])
                        else:
                            logger.fdebug(module + ' file does not exist in location: ' + pathsrc + '. Cannot validate location - some options will not be available for this item.')
                            continue
                    except:
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
                    if mylar.CONFIG.RENAME_FILES:
                        renamed_file = rename_param(arcinfo['ComicID'], arcinfo['ComicName'], arcinfo['IssueNumber'], chk['Location'], issueid=arcinfo['IssueID'], arc=arcinfo['StoryArc'])
                        if renamed_file:
                            dfilename = renamed_file['nfilename']

                    if mylar.CONFIG.READ2FILENAME:
                        #logger.fdebug('readingorder#: ' + str(arcinfo['ReadingOrder']))
                        #if int(arcinfo['ReadingOrder']) < 10: readord = "00" + str(arcinfo['ReadingOrder'])
                        #elif int(arcinfo['ReadingOrder']) >= 10 and int(arcinfo['ReadingOrder']) <= 99: readord = "0" + str(arcinfo['ReadingOrder'])
                        #else: readord = str(arcinfo['ReadingOrder'])
                        readord = renamefile_readingorder(arcinfo['ReadingOrder'])
                        dfilename = str(readord) + "-" + dfilename

                    pathdst = os.path.join(grdst, dfilename)

                    logger.fdebug('Destination Path : ' + pathdst)
                    logger.fdebug('Source Path : ' + pathsrc)
                    if not os.path.isdir(grdst):
                        logger.fdebug('[ARC-DIRECTORY] Arc directory doesn\'t exist. Creating: %s' % grdst)
                        mylar.filechecker.validateAndCreateDirectory(grdst, create=True)

                    if not os.path.isfile(pathdst):
                        logger.info('[' + mylar.CONFIG.ARC_FILEOPS.upper() + '] ' + pathsrc + ' into directory : ' + pathdst)

                        try:
                            #need to ensure that src is pointing to the series in order to do a soft/hard-link properly
                            fileoperation = file_ops(pathsrc, pathdst, arc=True)
                            if not fileoperation:
                                raise OSError
                        except (OSError, IOError):
                            logger.fdebug('[' + mylar.CONFIG.ARC_FILEOPS.upper() + '] Failure ' + pathsrc + ' - check directories and manually re-run.')
                            continue
                    updateloc = pathdst
                else:
                    updateloc = pathsrc

                update_iss.append({'IssueID':    chk['IssueID'],
                                   'Location':   updateloc})

    for ui in update_iss:
        logger.info(ui['IssueID'] + ' to update location to: ' + ui['Location'])
        myDB.upsert("storyarcs", {'Location': ui['Location']}, {'IssueID': ui['IssueID'], 'StoryArcID': storyarcid})


def spantheyears(storyarcid):
    #import db
    myDB = db.DBConnection()

    totalcnt = myDB.select("SELECT * FROM storyarcs WHERE StoryArcID=?", [storyarcid])
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

    tmp_folderformat = mylar.CONFIG.ARC_FOLDERFORMAT

    if tmp_folderformat is not None:
        if publisher == 'None':
            chunk_f_f = re.sub('\$publisher', '', tmp_folderformat)
            chunk_f = re.compile(r'\s+')
            tmp_folderformat = chunk_f.sub(' ', chunk_f_f)


    if any([tmp_folderformat == '', tmp_folderformat is None]):
        arcpath = replace_all('$arc ($spanyears)', values)
    else:
        arcpath = replace_all(tmp_folderformat, values)

    if mylar.CONFIG.REPLACE_SPACES:
        arcpath = arcpath.replace(' ', mylar.CONFIG.REPLACE_CHAR)

    if arcpath.startswith('/'):
        arcpath = arcpath[1:]
    elif arcpath.startswith('//'):
        arcpath = arcpath[2:]

    if mylar.CONFIG.STORYARCDIR is True:
        if mylar.CONFIG.STORYARC_LOCATION is None:
            dstloc = os.path.join(mylar.CONFIG.DESTINATION_DIR, 'StoryArcs', arcpath)
        else:
            dstloc = os.path.join(mylar.CONFIG.STORYARC_LOCATION, arcpath)
    elif mylar.CONFIG.COPY2ARCDIR is True:
        logger.warn('Story arc directory is not configured. Defaulting to grabbag directory: ' + mylar.CONFIG.GRABBAG_DIR)
        dstloc = os.path.join(mylar.CONFIG.GRABBAG_DIR, arcpath)
    else:
        dstloc = None

    return dstloc

def torrentinfo(issueid=None, torrent_hash=None, download=False, monitor=False):
    #import db
    from base64 import b16encode, b32decode

    #check the status of the issueid to make sure it's in Snatched status and was grabbed via torrent.
    if issueid:
        myDB = db.DBConnection()
        cinfo = myDB.selectone('SELECT a.Issue_Number, a.ComicName, a.Status, b.Hash from issues as a inner join snatched as b ON a.IssueID=b.IssueID WHERE a.IssueID=?', [issueid]).fetchone()
        if cinfo is None:
            logger.warn('Unable to locate IssueID of : ' + issueid)
            snatch_status = 'MONITOR ERROR'

        if cinfo['Status'] != 'Snatched' or cinfo['Hash'] is None:
            logger.warn(cinfo['ComicName'] + ' #' + cinfo['Issue_Number'] + ' is currently in a ' + cinfo['Status'] + ' Status.')
            snatch_status = 'MONITOR ERROR'

        torrent_hash = cinfo['Hash']

    logger.fdebug("Working on torrent: " + torrent_hash)
    if len(torrent_hash) == 32:
       torrent_hash = b16encode(b32decode(torrent_hash))

    if not len(torrent_hash) == 40:
       logger.error("Torrent hash is missing, or an invalid hash value has been passed")
       snatch_status = 'MONITOR ERROR'
    else:
        if mylar.USE_RTORRENT:
            from . import test
            rp = test.RTorrent()
            torrent_info = rp.main(torrent_hash, check=True)
        elif mylar.USE_DELUGE:
            #need to set the connect here as well....
            from mylar.torrent.clients import deluge as delu
            dp = delu.TorrentClient()
            if not dp.connect(mylar.CONFIG.DELUGE_HOST, mylar.CONFIG.DELUGE_USERNAME, mylar.CONFIG.DELUGE_PASSWORD):
                logger.warn('Not connected to Deluge!')

            torrent_info = dp.get_torrent(torrent_hash)
        else:
            snatch_status = 'MONITOR ERROR'
            return

    logger.info('torrent_info: %s' % torrent_info)

    if torrent_info is False or len(torrent_info) == 0:
        logger.warn('torrent returned no information. Check logs - aborting auto-snatch at this time.')
        snatch_status = 'MONITOR ERROR'
    else:
        if mylar.USE_DELUGE:
            torrent_status = torrent_info['is_finished']
            torrent_files = torrent_info['num_files']
            torrent_folder = torrent_info['save_path']
            torrent_info['total_filesize'] = torrent_info['total_size']
            torrent_info['upload_total'] = torrent_info['total_uploaded']
            torrent_info['download_total'] = torrent_info['total_payload_download']
            torrent_info['time_started'] = torrent_info['time_added']

        elif mylar.USE_RTORRENT:
            torrent_status = torrent_info['completed']
            torrent_files = len(torrent_info['files'])
            torrent_folder = torrent_info['folder']

        if all([torrent_status is True, download is True]):
            if not issueid: 
                torrent_info['snatch_status'] = 'MONITOR STARTING'
                #yield torrent_info

            import shlex, subprocess
            logger.info('Torrent is completed and status is currently Snatched. Attempting to auto-retrieve.')
            with open(mylar.CONFIG.AUTO_SNATCH_SCRIPT, 'r') as f:
                first_line = f.readline()

            if mylar.CONFIG.AUTO_SNATCH_SCRIPT.endswith('.sh'):
                shell_cmd = re.sub('#!', '', first_line)
                if shell_cmd == '' or shell_cmd is None:
                    shell_cmd = '/bin/bash'
            else:
                shell_cmd = sys.executable

            curScriptName = shell_cmd + ' ' + str(mylar.CONFIG.AUTO_SNATCH_SCRIPT) #.decode("string_escape")
            if torrent_files > 1:
                downlocation = torrent_folder
            else:
                if mylar.USE_DELUGE:
                    downlocation = os.path.join(torrent_folder, torrent_info['files'][0]['path'])
                else:
                    downlocation = torrent_info['files'][0]

            autosnatch_env = os.environ.copy()
            autosnatch_env['downlocation'] = downlocation.replace("'", "\\'")

            #these are pulled from the config and are the ssh values to use to retrieve the data
            autosnatch_env['host'] = mylar.CONFIG.PP_SSHHOST
            autosnatch_env['port'] = mylar.CONFIG.PP_SSHPORT
            autosnatch_env['user'] = mylar.CONFIG.PP_SSHUSER
            autosnatch_env['localcd'] = mylar.CONFIG.PP_SSHLOCALCD
            #bash won't accept None, so send check and send empty strings for the 2 possible None values if needed
            if mylar.CONFIG.PP_SSHKEYFILE is not None:
                autosnatch_env['keyfile'] = mylar.CONFIG.PP_SSHKEYFILE
            else:
                autosnatch_env['keyfile'] = ''
            if mylar.CONFIG.PP_SSHPASSWD is not None:
                autosnatch_env['passwd'] = mylar.CONFIG.PP_SSHPASSWD
            else:
                autosnatch_env['passwd'] = ''


            #downlocation = re.sub("\'", "\\'", downlocation)
            #downlocation = re.sub("&", "\&", downlocation)

            script_cmd = shlex.split(curScriptName, posix=False) # + [downlocation]
            logger.fdebug('Executing command %s' % script_cmd)
            try:
                p = subprocess.Popen(script_cmd, env=dict(autosnatch_env), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
                out, err = p.communicate()
                logger.fdebug('Script result: %s' % out)
            except OSError as e:
                logger.warn('Unable to run extra_script: %s' % e)
                snatch_status = 'MONITOR ERROR'
            else:
                if 'Access failed: No such file' in str(out):
                    logger.fdebug('Not located in location it is supposed to be in - probably has been moved by some script and I got the wrong location due to timing. Trying again...')
                    snatch_status = 'IN PROGRESS'
                else:
                    snatch_status = 'MONITOR COMPLETE' #COMPLETED
                torrent_info['completed'] = torrent_status
                torrent_info['files'] = torrent_files
                torrent_info['folder'] = torrent_folder
                torrent_info['copied_filepath'] = os.path.join(mylar.CONFIG.PP_SSHLOCALCD, torrent_info['name'])
                torrent_info['snatch_status'] = snatch_status
        else:
            if download is True:
                snatch_status = 'IN PROGRESS'
            elif monitor is True:
                #pause the torrent, copy it to the cache folder, unpause the torrent and return the complete path to the cache location
                if mylar.USE_DELUGE:
                    pauseit = dp.stop_torrent(torrent_hash)
                    if pauseit is False:
                        logger.warn('Unable to pause torrent - cannot run post-process on item at this time.')
                        snatch_status = 'MONITOR FAIL'
                    else:
                        try:
                            new_filepath = os.path.join(torrent_path, '.copy')
                            logger.fdebug('New_Filepath: %s' % new_filepath)
                            shutil.copy(torrent_path, new_filepath)
                            torrent_info['copied_filepath'] = new_filepath
                        except:
                            logger.warn('Unexpected Error: %s' % sys.exc_info()[0])
                            logger.warn('Unable to create temporary directory to perform meta-tagging. Processing cannot continue with given item at this time.')
                            torrent_info['copied_filepath'] = torrent_path
                            SNATCH_STATUS = 'MONITOR FAIL'
                        else:
                            startit = dp.start_torrent(torrent_hash)
                            SNATCH_STATUS = 'MONITOR COMPLETE'
            else:
                snatch_status = 'NOT SNATCHED'

    #torrent_info['snatch_status'] = snatch_status
    return torrent_info

def weekly_info(week=None, year=None, current=None):
    #find the current week and save it as a reference point.
    todaydate = datetime.datetime.today()
    if todaydate.year == 2025:
        current_weeknumber = todaydate.isocalendar()[1]
    else:
        current_weeknumber = todaydate.strftime("%U")
    if current is not None:
        c_weeknumber = int(current[:current.find('-')])
        c_weekyear = int(current[current.find('-')+1:])
    else:
        c_weeknumber = week
        c_weekyear = year

    if week:
        weeknumber = int(week)
        year = int(year)
    else:
        #find the given week number for the current day
        weeknumber = int(current_weeknumber)
        year = int(todaydate.strftime("%Y"))

    #monkey patch for 2018/2019 - week 52/week 0
    if all([weeknumber == 52, c_weeknumber == 51, c_weekyear == 2018]):
        weeknumber = 0
        year = 2019
    elif all([weeknumber == 52, c_weeknumber == 0, c_weekyear == 2019]):
        weeknumber = 51
        year = 2018

    #monkey patch for 2019/2020 - week 52/week 0
    if all([weeknumber == 52, c_weeknumber == 51, c_weekyear == 2019]) or all([weeknumber == '52', year == '2019']):
        weeknumber = 0
        year = 2020
    elif all([weeknumber == 52, c_weeknumber == 0, c_weekyear == 2020]):
        weeknumber = 51
        year = 2019

    #monkey patch for 2020/2021 - week 52/week 0
    if all([int(weeknumber) == 0, int(year) == 2021]) or all([int(weeknumber) == 52, int(year) == 2020]):
        weeknumber = 52
        year = 2020

    #monkey patch for 2021/2022 - week 52/week 0
    if all([int(weeknumber) == 0, int(year) == 2022]) or all([int(weeknumber) == 52, int(year) == 2021]):
        weeknumber = 52
        year = 2021

    #monkey patch for 2024/2025 - week 52/week 0
    if all([weeknumber == 52, c_weeknumber == 51, c_weekyear == 2024]) or all([weeknumber == '52', year == '2024']):
        weeknumber = 1
        year = 2025
    elif any([weeknumber == 52, weeknumber == 0]) and all([c_weeknumber == 1, c_weekyear == 2025]):
        weeknumber = 51
        year = 2024

    startofyear = date(year,1,1)
    week0 = startofyear - timedelta(days=startofyear.isoweekday())
    stweek = datetime.datetime.strptime(week0.strftime('%Y-%m-%d'), '%Y-%m-%d')
    if year == 2025:
        startweek = stweek + timedelta(weeks = weeknumber -1)
    else:
        startweek = stweek + timedelta(weeks = weeknumber)

    midweek = startweek + timedelta(days = 3)
    endweek = startweek + timedelta(days = 6)

    if all([weeknumber == 1, year == 2021]):
        # make sure the arrow going back will hit the correct week in the previous year.
        prev_week = 52
        prev_year = 2020
    elif all([weeknumber == 0, year == 2022]):
        # make sure the arrow going back will hit the correct week in the previous year.
        prev_week = 52
        prev_year = 2021
    elif all([weeknumber == 0, year == 2025]):
        # make sure the arrow going back will hit the correct week in the previous year.
        prev_week = 51
        prev_year = 2024
    else:
        prev_week = int(weeknumber) - 1
        prev_year = year
        if prev_week < 0:
            prev_week = 52
            prev_year = int(year) - 1

    next_week = int(weeknumber) + 1
    next_year = year
    if next_week > 52:
        next_year = int(year) + 1
        if all([weeknumber == 52, year == 2020]):
            # make sure the next arrow will hit the correct week in the following year.
            next_week = '1'
        elif all([weeknumber == 52, year == 2021]):
            # make sure the next arrow will hit the correct week in the following year.
            next_week = '1'
        elif all([weeknumber == 51, year == 2024]):
            # make sure the next arrow will hit the correct week in the following year.
            next_week = '1'
        else:
            next_week = datetime.date(int(next_year),1,1).strftime("%U")

    date_fmt = "%B %d, %Y"
    try:
        con_startweek = "" + startweek.strftime(date_fmt)
        con_endweek = "" + endweek.strftime(date_fmt)
    except:
        con_startweek = "" + startweek.strftime(date_fmt)
        con_endweek = "" + endweek.strftime(date_fmt)

    if mylar.CONFIG.WEEKFOLDER_LOC is not None:
        weekdst = mylar.CONFIG.WEEKFOLDER_LOC
    else:
        weekdst = mylar.CONFIG.DESTINATION_DIR

    if mylar.SCHED_WEEKLY_LAST is not None:
        weekly_stamp = datetime.datetime.fromtimestamp(mylar.SCHED_WEEKLY_LAST)
        weekly_last = weekly_stamp.replace(microsecond=0)
    else:
        weekly_last = 'None'

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
                'last_update':        weekly_last}

    if weekdst is not None:
        if mylar.CONFIG.WEEKFOLDER_FORMAT == 0:
            weekn = weeknumber
            if len(str(weekn)) == 1:
                weekn = '%s%s' % ('0', str(weekn))
            weekfold = os.path.join(weekdst, '%s-%s' % (weekinfo['year'], weekn))
        else:
            weekfold = os.path.join(weekdst, str( str(weekinfo['midweek']) ))
    else:
        weekfold = None

    weekinfo['week_folder'] = weekfold

    return weekinfo

def latestdate_update():
    #import db
    myDB = db.DBConnection()
    ccheck = myDB.select("SELECT a.ComicID, b.IssueID, a.LatestDate, b.ReleaseDate, b.Issue_Number from comics as a left join issues as b on a.comicid=b.comicid where a.LatestDate < b.ReleaseDate or a.LatestDate like '%Unknown%' group by a.ComicID")
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

def latestissue_update():
    myDB = db.DBConnection()
    cck = myDB.select('SELECT ComicID, LatestIssue FROM comics WHERE intLatestIssue is NULL')

    if cck:
        c_list = []
        for ck in cck:
            c_list.append({'ComicID': ck['ComicID'],
                           'intLatestIssue': issue_number_parser(ck['LatestIssue']).asInt})

        logger.info('[LATEST_ISSUE_TO_INT] Updating the latestIssue field for %s series' % (len(c_list)))

        for ct in c_list:
            try:
                newVal = {'intLatestIssue': ct['intLatestIssue']}
                ctrlVal = {'ComicID': ct['ComicID']}
                myDB.upsert("comics", newVal, ctrlVal)
            except Exception as e:
                logger.fdebug('exception encountered: %s' % e)
                continue

def ddl_downloader(queue):
    myDB = db.DBConnection()
    link_type_failure = {}
    while True:
        if mylar.DDL_LOCK is True:
            time.sleep(5)

        elif mylar.DDL_LOCK is False and queue.qsize() >= 1:
            item = queue.get(True)

            if item == 'exit':
                logger.info('Cleaning up workers for shutdown')
                break

            if item['id'] not in mylar.DDL_QUEUED:
                mylar.DDL_QUEUED.append(item['id'])

            try:
                link_type_failure[item['id']].append(item['link_type_failure'])
            except Exception:
                pass

            #logger.info('[%s] link_type_failure: %s' % (item['id'], link_type_failure))

            logger.info('Now loading request from DDL queue: %s' % item['series'])

            #write this to the table so we have a record of what's going on.
            ctrlval = {'id':      item['id']}
            val = {'status':       'Downloading',
                   'updated_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
            myDB.upsert('ddl_info', val, ctrlval)

            if item['site'] == 'DDL(GetComics)':
                try:
                    remote_filesize = item['remote_filesize']
                except Exception:
                    try:
                        remote_filesize = helpers.human2bytes(re.sub('/s', '', item['size'][:-1]).strip())
                    except Exception:
                        remote_filesize = 0

                if any([item['link_type'] == 'GC-Main', item['link_type'] == 'GC_Mirror']):
                    ddz = getcomics.GC()
                    ddzstat = ddz.downloadit(item['id'], item['link'], item['mainlink'], item['resume'], item['issueid'], remote_filesize)
                elif item['link_type'] == 'GC-Mega':
                    meganz = mega.MegaNZ()
                    ddzstat = meganz.ddl_download(item['link'], None, item['id'], item['issueid'], item['link_type']) #item['filename'], item['id'])
                elif item['link_type'] == 'GC-Media':
                    mediaf = mediafire.MediaFire()
                    ddzstat = mediaf.ddl_download(item['link'], item['id'], item['issueid']) #item['filename'], item['id'])
                elif item['link_type'] == 'GC-Pixel':
                    pdrain = pixeldrain.PixelDrain()
                    ddzstat = pdrain.ddl_download(item['link'], item['id'], item['issueid']) #item['filename'], item['id'])

            elif item['site'] == 'DDL(External)':
                meganz = mega.MegaNZ()
                ddzstat = meganz.ddl_download(item['link'], item['filename'], item['id'], item['issueid'], item['link_type'])

            # Check for file validity post download and mark as failure if file is not a zip, rar, or pdf
            # Can only check single downloads.  Packs will have to be managed by post-processing if enabled
            if ddzstat['success'] and ddzstat['filename'] is not None:
                filecondition = check_file_condition(ddzstat['path'])
                if not filecondition['status']:
                    logger.warn(f"CRC Check: File {ddzstat['path']} failed condition check ({filecondition['quality']}).  Marking as failed.")
                    ddzstat['success'] = False
                    ddzstat['link_type_failure'] = item['link_type']

            if ddzstat['success'] is True:
                tdnow = datetime.datetime.now()
                nval = {'status':  'Completed',
                        'updated_date': tdnow.strftime('%Y-%m-%d %H:%M')}
                myDB.upsert('ddl_info', nval, ctrlval)

            if all([ddzstat['success'] is True, mylar.CONFIG.POST_PROCESSING is True]):
                try:
                    if ddzstat['filename'] is None:
                        logger.info('%s successfully downloaded - now initiating post-processing for %s.' % (os.path.basename(ddzstat['path']), ddzstat['path']))
                        mylar.PP_QUEUE.put({'nzb_name':     os.path.basename(ddzstat['path']),
                                            'nzb_folder':   ddzstat['path'],
                                            'failed':       False,
                                            'issueid':      None,
                                            'comicid':      item['comicid'],
                                            'apicall':      True,
                                            'ddl':          True,
                                            'download_info': {'provider': 'DDL', 'id': item['id']}})
                    else:
                        logger.info('%s successfully downloaded - now initiating post-processing for %s' % (ddzstat['filename'], ddzstat['path']))
                        mylar.PP_QUEUE.put({'nzb_name':     ddzstat['filename'],
                                            'nzb_folder':   ddzstat['path'],
                                            'failed':       False,
                                            'issueid':      item['issueid'],
                                            'comicid':      item['comicid'],
                                            'apicall':      True,
                                            'ddl':          True,
                                            'download_info': {'provider': 'DDL', 'id': item['id']}})
                except Exception as e:
                    logger.error('process error: %s [%s]' %(e, ddzstat))

                #logger.fdebug('mylar.ddl_queued: %s' % mylar.DDL_QUEUED)
                mylar.DDL_QUEUED.remove(item['id'])
                try:
                    link_type_failure.pop(item['id'])
                except KeyError:
                    pass

                try:
                    pck_cnt = 0
                    if item['comicinfo'][0]['pack'] is True:
                        logger.fdebug('[PACK DETECTION] Attempting to remove issueids from the pack dont-queue list')
                        for x,y in dict(mylar.PACK_ISSUEIDS_DONT_QUEUE).items():
                            if y == item['id']:
                                pck_cnt +=1
                                del mylar.PACK_ISSUEIDS_DONT_QUEUE[x]
                        logger.fdebug('Successfully removed %s issueids from pack queue list as download is completed.' % pck_cnt)
                except Exception:
                    pass

                # remove html file from cache if it's successful
                ddl_cleanup(item['id'])

            elif all([ddzstat['success'] is True, mylar.CONFIG.POST_PROCESSING is False]):
                path = ddzstat['path']
                if ddzstat['filename'] is not None:
                    path = os.path.join(path, ddzstat['filename'])
                logger.info('File successfully downloaded. Post Processing is not enabled - item retained here: %s' % (path,))
                ddl_cleanup(item['id'])
            else:
                if item['site'] == 'DDL(GetComics)':
                    try:
                        ltf = ddzstat['links_exhausted']
                    except KeyError:
                        logger.info('[Status: %s] Failed to download item from %s : %s ' % (ddzstat['success'], item['link_type'], ddzstat))
                        try:
                            link_type_failure[item['id']].append(item['link_type'])
                        except KeyError:
                            link_type_failure[item['id']] = [item['link_type']]
                        logger.fdebug('[%s] link_type_failure: %s' % (item['id'], link_type_failure))
                        ggc = getcomics.GC(comicid=item['comicid'], issueid=item['issueid'], oneoff=item['oneoff'])
                        ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])
                    else:
                        logger.info('[REDO] Exhausted all available links [%s] for issueid %s and was not able to download anything' % (link_type_failure[item['id']], item['issueid']))
                        nval = {'status':  'Failed',
                                'updated_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
                        myDB.upsert('ddl_info', nval, ctrlval)
                        #undo all snatched items, to previous status via item['id'] - this will be set to Skipped currently regardless of previous status
                        reverse_the_pack_snatch(item['id'], item['comicid'])
                        link_type_failure.pop(item['id'])
                        ddl_cleanup(item['id'])
                else:
                    logger.info('[Status: %s] Failed to download item from %s : %s ' % (ddzstat['success'], item['site'], ddzstat))
                    myDB.action('DELETE FROM ddl_info where id=?', [item['id']])
                    mylar.search.FailedMark(item['issueid'], item['comicid'], item['id'], ddzstat['filename'], item['site'])
        else:
            time.sleep(5)

def ddl_cleanup(id):
   # remove html file from cache if it's successful
   tlnk = 'getcomics-%s.html' % id
   try:
       os.remove(os.path.join(mylar.CONFIG.CACHE_DIR, 'html_cache', tlnk))
   except Exception as e:
       logger.fdebug('[HTML-cleanup] Unable to remove html used for item from html_cache folder.'
                     ' Manual removal required or set `cleanup_cache=True` in the config.ini to'
                     ' clean cache items on every startup. If this was a Retry - ignore this.')


def postprocess_main(queue):
    while True:
        if mylar.APILOCK is True:
            time.sleep(5)

        elif mylar.APILOCK is False and queue.qsize() >= 1: #len(queue) > 1:
            pp = None
            item = queue.get(True)
            logger.info('Now loading from post-processing queue: %s' % item)
            if item == 'exit':
                logger.info('Cleaning up workers for shutdown')
                break

            if mylar.APILOCK is False:
                try:
                    pprocess = process.Process(item['nzb_name'], item['nzb_folder'], item['failed'], item['issueid'], item['comicid'], item['apicall'], item['ddl'], item['download_info'])
                except:
                    pprocess = process.Process(item['nzb_name'], item['nzb_folder'], item['failed'], item['issueid'], item['comicid'], item['apicall'])
                pp = pprocess.post_process()
                time.sleep(5) #arbitrary sleep to let the process attempt to finish pp'ing

            if pp is not None:
                if pp['mode'] == 'stop':
                    #reset the lock so any subsequent items can pp and not keep the queue locked up.
                    mylar.APILOCK = False

            if mylar.APILOCK is True:
                logger.info('Another item is post-processing still...')
                time.sleep(15)
                #mylar.PP_QUEUE.put(item)
        else:
            time.sleep(5)

def search_queue(queue):
    while True:
        if mylar.SEARCHLOCK is True:
            time.sleep(5)

        elif mylar.SEARCHLOCK is False and queue.qsize() >= 1: #len(queue) > 1:
            item = queue.get(True)
            if item == 'exit':
                logger.info('[SEARCH-QUEUE] Cleaning up workers for shutdown')
                break

            gumbo_line = True
            #logger.fdebug('pack_issueids_dont_queue: %s' % mylar.PACK_ISSUEIDS_DONT_QUEUE)
            #logger.fdebug('ddl_queued: %s' % mylar.DDL_QUEUED)
            if item['issueid'] in mylar.PACK_ISSUEIDS_DONT_QUEUE:
                if mylar.PACK_ISSUEIDS_DONT_QUEUE[item['issueid']] in mylar.DDL_QUEUED:
                    logger.fdebug('[SEARCH-QUEUE-PACK-DETECTION] %s already queued to download via pack...Ignoring' % item['issueid'])
                    gumbo_line = False

            if gumbo_line:
                logger.fdebug('[SEARCH-QUEUE] Now loading item from search queue: %s' % item)
                if mylar.SEARCHLOCK is False:
                    arcid = None
                    comicid = item['comicid']
                    issueid = item['issueid']
                    if issueid is not None:
                        if '_' in issueid:
                            arcid = issueid
                            comicid = None # required for storyarcs to work
                            issueid = None # required for storyarcs to work
                    mofo = mylar.filers.FileHandlers(ComicID=comicid, IssueID=issueid, arcID=arcid)
                    local_check = mofo.walk_the_walk()

                    if local_check['status']:
                        fullpath = Path(local_check['filepath']) / local_check['filename']
                        filecondition = check_file_condition(fullpath)
                        if not filecondition['status']:
                            logger.warn(f"CRC Check: File {fullpath} failed condition check ({filecondition['quality']}).  Ignoring.")
                            local_check['status'] = False

                    if local_check['status'] is True:
                        mylar.PP_QUEUE.put({'nzb_name':     local_check['filename'],
                                            'nzb_folder':   local_check['filepath'],
                                            'failed':       False,
                                            'issueid':      item['issueid'],
                                            'comicid':      item['comicid'],
                                            'apicall':      True,
                                            'ddl':          False,
                                            'download_info': None})
                    else:
                        try:
                            manual = item['manual']
                        except Exception as e:
                            manual = False
                        ss_queue = mylar.search.searchforissue(item['issueid'], manual=manual)
                    time.sleep(5) #arbitrary sleep to let the process attempt to finish pp'ing

            if mylar.SEARCHLOCK is True:
                logger.fdebug('[SEARCH-QUEUE] Another item is currently being searched....')
                time.sleep(15)
        else:
            time.sleep(5)


def worker_main(queue):
    while True:
        if queue.qsize() >= 1:
            item = queue.get(True)
            logger.info('Now loading from queue: %s' % item)
            if item == 'exit':
                logger.info('Cleaning up workers for shutdown')
                break
            snstat = torrentinfo(torrent_hash=item['hash'], download=True)
            if snstat['snatch_status'] == 'IN PROGRESS':
                logger.info('Still downloading in client....let us try again momentarily.')
                time.sleep(30)
                mylar.SNATCHED_QUEUE.put(item)
            elif any([snstat['snatch_status'] == 'MONITOR FAIL', snstat['snatch_status'] == 'MONITOR COMPLETE']):
                logger.info('File copied for post-processing - submitting as a direct pp.')
                mylar.PP_QUEUE.put({'nzb_name':     os.path.basename(snstat['copied_filepath']),
                                    'nzb_folder':   snstat['copied_filepath'], #os.path.abspath(os.path.join(snstat['copied_filepath'], os.pardir)),
                                    'failed':       False,
                                    'issueid':      item['issueid'],
                                    'comicid':      item['comicid'],
                                    'apicall':      True,
                                    'ddl':          False,
                                    'download_info': None})
                #threading.Thread(target=self.checkFolder, args=[os.path.abspath(os.path.join(snstat['copied_filepath'], os.pardir))]).start()
        else:
            time.sleep(15)

def nzb_monitor(queue):
    while True:
        if mylar.RETURN_THE_NZBQUEUE.qsize() >= 1:
            if mylar.USE_SABNZBD is True:
                # this checks the sabnzbd queue to see if it's paused / unpaused.
                sab_params = {
                    'apikey': mylar.CONFIG.SAB_APIKEY,
                    'mode': 'queue',
                    'start': 0,
                    'limit': 5,
                    'search': None,
                    'output': 'json',
                }
                s = sabnzbd.SABnzbd(params=sab_params)
                sabresponse = s.sender(chkstatus=True)
                # response will be: Paused = True, UnPaused = False
                if sabresponse['status'] is False:
                    while True:
                        if mylar.RETURN_THE_NZBQUEUE.qsize() >= 1:
                            qu_retrieve = mylar.RETURN_THE_NZBQUEUE.get(True)
                            try:
                                nzstat = s.historycheck(qu_retrieve)
                                cdh_monitor(queue, qu_retrieve, nzstat, readd=True)
                            except Exception as e:
                                logger.error('Exception occured trying to re-add %s to queue: %s' % (qu_retrieve, e))
                            time.sleep(5)
                        else:
                            break

        if queue.qsize() >= 1:
            item = queue.get(True)
            if item == 'exit':
                logger.info('Cleaning up workers for shutdown')
                break
            try:
                tmp_apikey = item['queue'].pop('apikey')
                logger.info('Now loading from queue: %s' % item)
            except Exception:
                #nzbget doesn't pass the queue field. So just let it fly.
                logger.info('Now loading from queue: %s' % item)
            else:
                item['queue']['apikey'] = tmp_apikey
            if all([mylar.USE_SABNZBD is True, mylar.CONFIG.SAB_CLIENT_POST_PROCESSING is True]):
                nz = sabnzbd.SABnzbd(item)
                nzstat = nz.processor()
            elif all([mylar.USE_NZBGET is True, mylar.CONFIG.NZBGET_CLIENT_POST_PROCESSING is True]):
                nz = nzbget.NZBGet()
                nzstat = nz.processor(item)
            else:
                logger.warn('There are no NZB Completed Download handlers enabled. Not sending item to completed download handling...')
                break
            cdh_monitor(queue, item, nzstat)
        else:
            time.sleep(5)


def cdh_monitor(queue, item, nzstat, readd=False):
    known_nzb_id = item['nzo_id'] if (mylar.USE_SABNZBD is True) else item['NZBID']
    if any([nzstat['status'] == 'file not found', nzstat['status'] == 'double-pp']):
        logger.warn('Unable to complete post-processing call due to not finding file in the location provided. [%s]' % item)
    elif nzstat['status'] == 'nzb removed' or 'unhandled status' in str(nzstat['status']).lower():
        if readd is True:
            # if the queue isn't empty, retry it like 5 times or until queue is empty
            # if queue is empty, this could be a timing issue, so we'd have to recheck it one more time at least
            # need to implement some kind of counter here for all of this ^^^
            logger.warn('NZB seems to have been in a staging process within SABnzbd during attempt. Will requeue: %s.' % known_nzb_id)
            mylar.RETURN_THE_NZBQUEUE.put(item)
        else:
            logger.warn('NZB seems to have been removed from queue: %s' % known_nzb_id)
    elif nzstat['status'] == 'failed_in_sab':
        logger.warn('Failure returned from SAB for %s for some reason. You should probably check your SABnzbd logs' % known_nzb_id)
    elif nzstat['status'] == 'queue_paused':
        # queue pause check for sabnzbd only atm.
        if mylar.USE_SABNZBD is True:
            logger.info('[PAUSED_SAB_QUEUE] adding %s to a temporary queue that will fire off when SABnzbd is unpaused' % item)
            mylar.RETURN_THE_NZBQUEUE.put(item)
    elif nzstat['status'] is False:
        logger.info('Download %s failed. Requeue NZB to check later...' % known_nzb_id)
        time.sleep(5)
        if item not in queue.queue:
            mylar.NZB_QUEUE.put(item)
    elif nzstat['status'] is True:
        # Currently only checks SAB at this point as nzbget filename not available
        if nzstat['failed'] is False and mylar.USE_SABNZBD is True:
            fullpath = Path(nzstat['location']) / nzstat['name']
            filecondition = check_file_condition(fullpath)
            if not filecondition['status']:
                logger.warn(f"CRC Check: File {fullpath} failed condition check ({filecondition['quality']}).  Marking as failed.")
                nzstat['failed'] = True

        if nzstat['failed'] is False:
            logger.info('File successfully downloaded - now initiating completed downloading handling.')
        else:
            logger.info('File failed either due to being corrupt or incomplete - now initiating completed failed downloading handling.')
        try:
            mylar.PP_QUEUE.put({'nzb_name':     nzstat['name'],
                                'nzb_folder':   nzstat['location'],
                                'failed':       nzstat['failed'],
                                'issueid':      nzstat['issueid'],
                                'comicid':      nzstat['comicid'],
                                'apicall':      nzstat['apicall'],
                                'ddl':          False,
                                'download_info': nzstat['download_info']})
        except Exception as e:
            logger.error('process error: %s' % e)
    return


QueueInfo = namedtuple("QueueInfo", ("name", "is_alive", "size"))


def queue_info():
    yield from (
        QueueInfo(queue_name, thread_obj.is_alive() if thread_obj is not None else None, queue.qsize())
        for (queue_name, thread_obj, queue) in [
            ("AUTO-COMPLETE-NZB", mylar.NZBPOOL, mylar.NZB_QUEUE),
            ("AUTO-SNATCHER", mylar.SNPOOL, mylar.SNATCHED_QUEUE),
            ("DDL-QUEUE", mylar.DDLPOOL, mylar.DDL_QUEUE),
            ("POST-PROCESS-QUEUE", mylar.PPPOOL, mylar.PP_QUEUE),
            ("SEARCH-QUEUE", mylar.SEARCHPOOL, mylar.SEARCH_QUEUE),
        ]
    )


def script_env(mode, vars):
    #mode = on-snatch, pre-postprocess, post-postprocess
    #var = dictionary containing variables to pass
    mylar_env = os.environ.copy()
    shell_cmd = sys.executable
    if mode == 'on-snatch':
        runscript = mylar.CONFIG.SNATCH_SCRIPT
        if mylar.CONFIG.SNATCH_SHELL_LOCATION is not None:
            shell_cmd = mylar.CONFIG.SNATCH_SHELL_LOCATION
        if 'torrentinfo' in vars:
            if 'hash' in vars['torrentinfo']:
                mylar_env['mylar_release_hash'] = vars['torrentinfo']['hash']
            if 'torrent_filename' in vars['torrentinfo']:
                mylar_env['mylar_torrent_filename'] = vars['torrentinfo']['torrent_filename']
            if 'name' in vars['torrentinfo']:
                mylar_env['mylar_release_name'] = vars['torrentinfo']['name']
            if 'folder' in vars['torrentinfo']:
                mylar_env['mylar_release_folder'] = vars['torrentinfo']['folder']
            if 'label' in vars['torrentinfo']:
                mylar_env['mylar_release_label'] = vars['torrentinfo']['label']
            if 'total_filesize' in vars['torrentinfo']:
                mylar_env['mylar_release_filesize'] = str(vars['torrentinfo']['total_filesize'])
            if 'time_started' in vars['torrentinfo']:
                mylar_env['mylar_release_start'] = str(vars['torrentinfo']['time_started'])
            if 'filepath' in vars['torrentinfo']:
                mylar_env['mylar_torrent_file'] = str(vars['torrentinfo']['filepath'])
            else:
                try:
                    mylar_env['mylar_release_files'] = '|'.join(vars['torrentinfo']['files'])
                except TypeError:
                    mylar_env['mylar_release_files'] = '|'.join(json.dumps(vars['torrentinfo']['files']))
        elif 'nzbinfo' in vars:
            mylar_env['mylar_release_id'] = vars['nzbinfo']['id']
            if 'client_id' in vars['nzbinfo']:
                mylar_env['mylar_client_id'] = vars['nzbinfo']['client_id']
            mylar_env['mylar_release_nzbname'] = vars['nzbinfo']['nzbname']
            mylar_env['mylar_release_link'] = vars['nzbinfo']['link']
            mylar_env['mylar_release_nzbpath'] = vars['nzbinfo']['nzbpath']
            if 'blackhole' in vars['nzbinfo']:
                mylar_env['mylar_release_blackhole'] = vars['nzbinfo']['blackhole']
        mylar_env['mylar_release_provider'] = vars['provider']
        if 'comicinfo' in vars:
            try:
                if vars['comicinfo']['comicid'] is not None:
                    mylar_env['mylar_comicid'] = vars['comicinfo']['comicid']  #comicid/issueid are unknown for one-offs (should be fixable tho)
                else:
                    mylar_env['mylar_comicid'] = 'None'
            except:
                pass
            try:
                if vars['comicinfo']['issueid'] is not None:
                    mylar_env['mylar_issueid'] = vars['comicinfo']['issueid']
                else:
                    mylar_env['mylar_issueid'] = 'None'
            except:
                pass
            try:
                if vars['comicinfo']['issuearcid'] is not None:
                    mylar_env['mylar_issuearcid'] = vars['comicinfo']['issuearcid']
                else:
                    mylar_env['mylar_issuearcid'] = 'None'
            except:
                pass
            mylar_env['mylar_comicname'] = vars['comicinfo']['comicname']
            mylar_env['mylar_issuenumber'] = str(vars['comicinfo']['issuenumber'])
            try:
                mylar_env['mylar_comicvolume'] = str(vars['comicinfo']['volume'])
            except:
                pass
            try:
                mylar_env['mylar_seriesyear'] = str(vars['comicinfo']['seriesyear'])
            except:
                pass
            try:
                mylar_env['mylar_issuedate'] = str(vars['comicinfo']['issuedate'])
            except:
                pass

        mylar_env['mylar_release_pack'] = str(vars['pack'])
        if vars['pack'] is True:
            if vars['pack_numbers'] is not None:
                mylar_env['mylar_release_pack_numbers'] = vars['pack_numbers']
            if vars['pack_issuelist'] is not None:
                mylar_env['mylar_release_pack_issuelist'] = vars['pack_issuelist']
        mylar_env['mylar_method'] = vars['method']
        mylar_env['mylar_client'] = vars['clientmode']

    elif mode == 'post-process':
        #to-do
        runscript = mylar.CONFIG.EXTRA_SCRIPTS
        if mylar.CONFIG.ES_SHELL_LOCATION is not None:
            shell_cmd = mylar.CONFIG.ES_SHELL_LOCATION

    elif mode == 'pre-process':
        #to-do
        runscript = mylar.CONFIG.PRE_SCRIPTS
        if mylar.CONFIG.PRE_SHELL_LOCATION is not None:
            shell_cmd = mylar.CONFIG.PRE_SHELL_LOCATION

    logger.fdebug('Initiating ' + mode + ' script detection.')
    with open(runscript, 'r') as f:
        first_line = f.readline()

    if runscript.endswith('.sh'):
        shell_cmd = re.sub('#!', '', first_line)
        if shell_cmd == '' or shell_cmd is None:
            shell_cmd = '/bin/bash'

    curScriptName = shell_cmd + ' ' + runscript #.decode("string_escape")
    logger.fdebug("snatch script detected...enabling: " + str(curScriptName))

    script_cmd = shlex.split(curScriptName)
    logger.fdebug("Executing command " +str(script_cmd))
    try:
        subprocess.call(script_cmd, env=dict(mylar_env))
    except OSError as e:
        logger.warn("Unable to run extra_script: " + str(script_cmd))
        return False
    except TypeError as e:
        bad_environment = False
        for key, value in mylar_env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                bad_environment = True
                if key in os.environ:
                    logger.error('Invalid global environment variable: {k!r} = {v!r}'.format(k=key, v=value))
                else:
                    logger.error('Invalid Mylar environment variable: {k!r} = {v!r}'.format(k=key, v=value))
        if not bad_environment:
            raise e
    else:
        return True

def get_the_hash(filepath):
    import bencode
    # Open torrent file
    torrent_file = open(filepath, "rb")
    metainfo = bencode.decode(torrent_file.read())
    info = metainfo['info']
    thehash = hashlib.sha1(bencode.encode(info)).hexdigest().upper()
    logger.info('Hash of file : ' + thehash)
    return {'hash':     thehash}

def block_provider_check(site, simple=True, force=False):
    timenow = int(time.time())
    for prov in mylar.PROVIDER_BLOCKLIST:
        if prov['site'] == site:
            if force is True:
                mylar.PROVIDER_BLOCKLIST.remove(prov)
                if simple is True:
                    return False
                else:
                    return {'blocked': False, 'remain': (int(prov['resume'])-timenow)/60}
            else:
                if timenow < int(prov['resume']):
                    if simple is True:
                        return True
                    else:
                        return {'blocked': True, 'remain': (int(prov['resume'])-timenow)/60}
                else:
                    mylar.PROVIDER_BLOCKLIST.remove(prov)
    if simple is True:
        return False
    else:
        return {'blocked': False, 'remain': 0}

def disable_provider(site, reason=None, delay=0):
    if not delay:
        if mylar.CONFIG.BLOCKLIST_TIMER > 0:
            delay = int(mylar.CONFIG.BLOCKLIST_TIMER)
        else:
            delay = 3600
    mins = int(delay / 60) + (delay % 60 > 0)
    logger.info('Temporarily blocking provider %s for %s minutes...'% (site, mins))
    for entry in mylar.PROVIDER_BLOCKLIST:
        if entry['site'] == site:
            mylar.PROVIDER_BLOCKLIST.remove(entry)
    newentry = {'site': site, 'resume': int(time.time()) + delay, 'reason': reason}
    mylar.PROVIDER_BLOCKLIST.append(newentry)
    logger.info('provider_blocklist: %s' % mylar.PROVIDER_BLOCKLIST)

def date_conversion(originaldate):
    c_obj_date = datetime.datetime.strptime(originaldate, "%Y-%m-%d %H:%M:%S")
    n_date = datetime.datetime.now()
    absdiff = abs(n_date - c_obj_date)
    hours = (absdiff.days * 24 * 60 * 60 + absdiff.seconds) / 3600.0
    return hours

def job_management(write=False, job=None, last_run_completed=None, current_run=None, status=None, failure=False, startup=False):
    jobresults = []

    myDB = db.DBConnection()
    if startup is True:
        # on startup - db status will over-ride any settings to ensure persistent state
        job_info = myDB.select('SELECT DISTINCT(JobName), status, prev_run_timestamp FROM jobhistory')
        for ji in job_info:
            jstatus = ji['status']
            if any([jstatus is None, jstatus == 'Running']):
                jstatus = 'Waiting'
            if 'update' in ji['JobName'].lower():
                if mylar.SCHED_DBUPDATE_LAST is None:
                    mylar.SCHED_DBUPDATE_LAST = ji['prev_run_timestamp']
                if jstatus is None:
                    jstatus = 'Waiting'
                mylar.UPDATER_STATUS = jstatus
            elif 'search' in ji['JobName'].lower():
                if mylar.SCHED_SEARCH_LAST is None:
                    mylar.SCHED_SEARCH_LAST = ji['prev_run_timestamp']
                if jstatus is None:
                    jstatus = 'Waiting'
                mylar.SEARCH_STATUS = jstatus
            elif 'rss' in ji['JobName'].lower():
                # db value isn't used in startup as config option controls status
                if mylar.SCHED_RSS_LAST is None:
                    mylar.SCHED_RSS_LAST = ji['prev_run_timestamp']
                if jstatus is None:
                    if mylar.CONFIG.ENABLE_RSS:
                        jstatus = 'Waiting'
                if any([jstatus == 'Waiting', jstatus == 'Running']) and mylar.CONFIG.ENABLE_RSS is False:
                    jstatus = 'Paused'
                mylar.RSS_STATUS = jstatus
            elif 'weekly' in ji['JobName'].lower():
                if mylar.SCHED_WEEKLY_LAST is None:
                    mylar.SCHED_WEEKLY_LAST = ji['prev_run_timestamp']
                if jstatus is None:
                    jstatus = 'Waiting'
                mylar.WEEKLY_STATUS = jstatus
            elif 'version' in ji['JobName'].lower():
                # db value isn't used in startup as config option controls status
                if mylar.SCHED_VERSION_LAST is None:
                    mylar.SCHED_VERSION_LAST = ji['prev_run_timestamp']
                if jstatus is None:
                    if mylar.CONFIG.CHECK_GITHUB:
                        jstatus = 'Waiting'
                if any([jstatus == 'Waiting', jstatus == 'Running']) and mylar.CONFIG.CHECK_GITHUB is False:
                    jstatus = 'Paused'
                mylar.VERSION_STATUS = jstatus
            elif 'monitor' in ji['JobName'].lower():
                # db value isn't used in startup as config option controls status
                if mylar.SCHED_MONITOR_LAST is None:
                    mylar.SCHED_MONITOR_LAST = ji['prev_run_timestamp']
                if jstatus is None:
                    if mylar.CONFIG.CHECK_FOLDER:
                        jstatus = 'Waiting'
                if any([jstatus == 'Waiting', jstatus == 'Running']) and mylar.CONFIG.CHECK_FOLDER is False:
                    jstatus = 'Paused'
                mylar.MONITOR_STATUS = jstatus

        return {'weekly': {'last': mylar.SCHED_WEEKLY_LAST, 'status': mylar.WEEKLY_STATUS},
                'monitor': {'last': mylar.SCHED_MONITOR_LAST, 'status': mylar.MONITOR_STATUS},
                'search': {'last': mylar.SCHED_SEARCH_LAST, 'status': mylar.SEARCH_STATUS},
                'updater': {'last': mylar.SCHED_DBUPDATE_LAST, 'status': mylar.UPDATER_STATUS},
                'version': {'last': mylar.SCHED_VERSION_LAST, 'status': mylar.VERSION_STATUS},
                'rss': {'last': mylar.SCHED_RSS_LAST, 'status': mylar.RSS_STATUS},
               }

    for jb in mylar.SCHED.get_jobs():
        jobinfo = str(jb)
        jobname = jobinfo[:jobinfo.find('(')-1].strip()
        jobstatus = jobinfo[jobinfo.find('],')+2:len(jobinfo)-1].strip()
        next_the_run = False

        #logger.info('[%s] ==> %s' % (jobname, jobstatus))

        #jobstatus will be either paused / next run - running jobs have to be
        #identified farther below
        if jobname == 'DB Updater':
            prev_run_timestamp = mylar.SCHED_DBUPDATE_LAST
            if 'next run' in jobstatus:
                mylar.UPDATER_STATUS = 'Waiting'
                if any(ky == 'updater' for ky, vl in mylar.FORCE_STATUS.items()):
                    mylar.UPDATER_STATUS = mylar.FORCE_STATUS['updater']
                    next_the_run = True
            else:
                mylar.UPDATER_STATUS = 'Paused'
            sched_status = mylar.UPDATER_STATUS
        elif jobname == 'Auto-Search':
            prev_run_timestamp = mylar.SCHED_SEARCH_LAST
            if 'next run' in jobstatus:
                mylar.SEARCH_STATUS = 'Waiting'
                if any(ky == 'search' for ky, vl in mylar.FORCE_STATUS.items()):
                    mylar.SEARCH_STATUS = mylar.FORCE_STATUS['search']
                    next_the_run = True
            else:
                mylar.SEARCH_STATUS = 'Paused'
            sched_status = mylar.SEARCH_STATUS
        elif jobname == 'RSS Feeds':
            prev_run_timestamp = mylar.SCHED_RSS_LAST
            if 'next run' in jobstatus:
                mylar.RSS_STATUS = 'Waiting'
                if any(ky == 'rss' for ky, vl in mylar.FORCE_STATUS.items()):
                    mylar.RSS_STATUS = mylar.FORCE_STATUS['rss']
                    next_the_run = True
            else:
                mylar.RSS_STATUS = 'Paused'
            sched_status = mylar.RSS_STATUS
        elif jobname == 'Weekly Pullist':
            prev_run_timestamp = mylar.SCHED_WEEKLY_LAST
            if 'next run' in jobstatus:
                mylar.WEEKLY_STATUS = 'Waiting'
                if any(ky == 'weekly' for ky, vl in mylar.FORCE_STATUS.items()):
                    mylar.WEEKLY_STATUS = mylar.FORCE_STATUS['weekly']
                    next_the_run = True
            else:
                mylar.WEEKLY_STATUS = 'Paused'
            sched_status = mylar.WEEKLY_STATUS
        elif jobname == 'Check Version':
            prev_run_timestamp = mylar.SCHED_VERSION_LAST
            if 'next run' in jobstatus:
                mylar.VERSION_STATUS = 'Waiting'
                if any(ky == 'version' for ky, vl in mylar.FORCE_STATUS.items()):
                    mylar.VERSION_STATUS = mylar.FORCE_STATUS['version']
                    next_the_run = True
            else:
                mylar.VERSION_STATUS = 'Paused'
            sched_status = mylar.VERSION_STATUS
        elif jobname == 'Folder Monitor':
            prev_run_timestamp = mylar.SCHED_MONITOR_LAST
            if 'next run' in jobstatus:
                mylar.MONITOR_STATUS = 'Waiting'
                if any(ky == 'monitor' for ky, vl in mylar.FORCE_STATUS.items()):
                    mylar.MONITOR_STATUS = mylar.FORCE_STATUS['monitor']
                    next_the_run = True
            else:
                mylar.MONITOR_STATUS = 'Paused'
            sched_status = mylar.MONITOR_STATUS

        #jobname = jobinfo[:jobinfo.find('(')-1].strip()
        #logger.fdebug('jobinfo: %s' % jobinfo)
        try:
            jobtimetmp = jobinfo.split('at: ')[1].split('.')[0].strip()
        except:
            jobtime = None
        else:
            if next_the_run is False:
                jtime = float(calendar.timegm(datetime.datetime.strptime(jobtimetmp[:-1], '%Y-%m-%d %H:%M:%S %Z').timetuple()))
                jobtime = datetime.datetime.utcfromtimestamp(jtime)
            else:
                jobtime = None

        if prev_run_timestamp is not None:
            prev_run_time_utc = datetime.datetime.utcfromtimestamp(float(prev_run_timestamp))
            prev_run_time_utc = prev_run_time_utc.replace(microsecond=0)
        else:
            prev_run_time_utc = None

        jobresults.append({'jobname': jobname,
                           'next_run_datetime': jobtime,
                           'prev_run_datetime': prev_run_time_utc,
                           'next_run_timestamp': jobtime,
                           'prev_run_timestamp': prev_run_timestamp,
                           'status': sched_status})

    if not write:
        if len(jobresults) == 0:
            return monitors
        else:
            return jobresults
    else:
        if job is None:
            for x in jobresults:
                updateCtrl = {'JobName':  x['jobname']}
                updateVals = {'next_run_timestamp': x['next_run_timestamp'],
                              'prev_run_timestamp': x['prev_run_timestamp'],
                              'next_run_datetime': x['next_run_datetime'],
                              'prev_run_datetime': x['prev_run_datetime'],
                              'status': x['status']}

                myDB.upsert('jobhistory', updateVals, updateCtrl)
        else:
            #logger.fdebug('Updating info - job: %s' % job)
            #logger.fdebug('Updating info - last run: %s' % last_run_completed)
            #logger.fdebug('Updating info - status: %s' % status)
            updateCtrl = {'JobName':  job}
            if current_run is not None:
                pr_datetime = datetime.datetime.utcfromtimestamp(current_run)
                pr_datetime = pr_datetime.replace(microsecond=0)
                updateVals = {'prev_run_timestamp': current_run,
                              'prev_run_datetime': pr_datetime,
                              'status':  status}
                #logger.info('updateVals: %s' % updateVals)
            elif last_run_completed is not None:
                if any([job == 'DB Updater', job == 'Auto-Search', job == 'RSS Feeds', job == 'Weekly Pullist', job == 'Check Version', job == 'Folder Monitor']):
                    jobstore = None
                    nextrun_stamp = None
                    nextrun_date = None
                    for jbst in mylar.SCHED.get_jobs():
                        jb = str(jbst)
                        if 'Status Updater' in jb.lower():
                           continue
                        elif job == 'DB Updater' and 'update' in jb.lower():
                            if any(ky == 'updater' for ky, vl in mylar.FORCE_STATUS.items()):
                                mylar.UPDATER_STATUS = mylar.FORCE_STATUS['updater']
                                mylar.FORCE_STATUS.pop('updater')

                            if mylar.UPDATER_STATUS != 'Paused':
                                if mylar.DB_BACKFILL is True:
                                    #if backfilling, set it for every 15 mins
                                    nextrun_stamp = utctimestamp() + (mylar.CONFIG.BACKFILL_TIMESPAN * 60)
                                    logger.fdebug(
                                        '[BACKFILL-UPDATER] Will fire off every %s'
                                        ' minutes until backlog is decimated.'
                                        % (mylar.CONFIG.BACKFILL_TIMESPAN)
                                    )
                                else:
                                    nextrun_stamp = utctimestamp() + (int(mylar.DBUPDATE_INTERVAL) * 60)
                            else:
                                mylar.SCHED.pause_job('dbupdater')
                            jobstore = jbst
                            break
                        elif job == 'Auto-Search' and 'search' in jb.lower():
                            if any(ky == 'search' for ky, vl in mylar.FORCE_STATUS.items()):
                                mylar.SEARCH_STATUS = mylar.FORCE_STATUS['search']
                                mylar.FORCE_STATUS.pop('search')

                            if mylar.SEARCH_STATUS != 'Paused':
                                if failure is True:
                                   logger.info('Previous job could not run due to other jobs. Scheduling Auto-Search for 10 minutes from now.')
                                   s_interval = (10 * 60)
                                else:
                                   s_interval = mylar.CONFIG.SEARCH_INTERVAL * 60
                                nextrun_stamp = utctimestamp() + s_interval
                            else:
                                mylar.SCHED.pause_job('search')
                            jobstore = jbst
                            break
                        elif job == 'RSS Feeds' and 'rss' in jb.lower():
                            if any(ky == 'rss' for ky, vl in mylar.FORCE_STATUS.items()):
                                mylar.RSS_STATUS = mylar.FORCE_STATUS['rss']
                                mylar.FORCE_STATUS.pop('rss')

                            if mylar.RSS_STATUS != 'Paused':
                                nextrun_stamp = utctimestamp() + (int(mylar.CONFIG.RSS_CHECKINTERVAL) * 60)
                            else:
                                mylar.SCHED.pause_job('rss')
                            mylar.SCHED_RSS_LAST = last_run_completed
                            jobstore = jbst
                            break
                        elif job == 'Weekly Pullist' and 'weekly' in jb.lower():
                            if any(ky == 'weekly' for ky, vl in mylar.FORCE_STATUS.items()):
                                mylar.WEEKLY_STATUS = mylar.FORCE_STATUS['weekly']
                                mylar.FORCE_STATUS.pop('weekly')

                            if mylar.WEEKLY_STATUS != 'Paused':
                                if mylar.CONFIG.ALT_PULL == 2:
                                   wkt = 4
                                else:
                                    wkt = 24
                                nextrun_stamp = utctimestamp() + (wkt * 60 * 60)
                            else:
                                mylar.SCHED.pause_job('weekly')
                            mylar.SCHED_WEEKLY_LAST = last_run_completed
                            jobstore = jbst
                            break
                        elif job == 'Check Version' and 'version' in jb.lower():
                            if any(ky == 'version' for ky, vl in mylar.FORCE_STATUS.items()):
                                mylar.VERSION_STATUS = mylar.FORCE_STATUS['version']
                                mylar.FORCE_STATUS.pop('version')

                            if mylar.VERSION_STATUS != 'Paused':
                                nextrun_stamp = utctimestamp() + (mylar.CONFIG.CHECK_GITHUB_INTERVAL * 60)
                            else:
                                mylar.SCHED.pause_job('version')
                            jobstore = jbst
                            break
                        elif job == 'Folder Monitor' and 'monitor' in jb.lower():
                            if any(ky == 'monitor' for ky, vl in mylar.FORCE_STATUS.items()):
                                mylar.MONITOR_STATUS = mylar.FORCE_STATUS['monitor']
                                mylar.FORCE_STATUS.pop('monitor')

                            if mylar.MONITOR_STATUS != 'Paused':
                                nextrun_stamp = utctimestamp() + (int(mylar.CONFIG.DOWNLOAD_SCAN_INTERVAL) * 60)
                            else:
                                mylar.SCHED.pause_job('monitor')
                            jobstore = jbst
                            break

                    if jobstore is not None:
                        if nextrun_stamp is not None:
                            nextrun_date = datetime.datetime.utcfromtimestamp(nextrun_stamp)
                            jobstore.modify(next_run_time=nextrun_date)
                            nextrun_date = nextrun_date.replace(microsecond=0)
                    else:
                        # if the rss is enabled after startup, we have to re-set it up...
                        nextrun_stamp = utctimestamp() + (int(mylar.CONFIG.RSS_CHECKINTERVAL) * 60)
                        nextrun_date = datetime.datetime.utcfromtimestamp(nextrun_stamp)
                        mylar.SCHED_RSS_LAST = last_run_completed

                if nextrun_date is not None:
                    logger.fdebug('ReScheduled job: %s to %s' % (job, mylar.helpers.utc_date_to_local(nextrun_date)))
                lastrun_comp = datetime.datetime.utcfromtimestamp(last_run_completed)
                lastrun_comp = lastrun_comp.replace(microsecond=0)
                #if it's completed, then update the last run time to the ending time of the job
                updateVals = {'prev_run_timestamp':   last_run_completed,
                              'prev_run_datetime':    lastrun_comp,
                              'last_run_completed':   'True',
                              'next_run_timestamp':   nextrun_stamp,
                              'next_run_datetime':    nextrun_date,
                              'status':               status}

            logger.fdebug('Job update for %s: %s' % (updateCtrl, updateVals))
            myDB.upsert('jobhistory', updateVals, updateCtrl)

def stupidchk():
    #import db
    myDB = db.DBConnection()
    CCOMICS = myDB.select("SELECT COUNT(*) FROM comics WHERE Status='Active'")
    ens = myDB.select("SELECT COUNT(*) FROM comics WHERE Status='Loading' OR Status='Paused'")
    mylar.COUNT_COMICS = CCOMICS[0][0]
    mylar.EN_OOMICS = ens[0][0]

def newznab_test(name, host, ssl, apikey):
    from xml.dom.minidom import parseString, Element
    params = {'t':       'search',
              'apikey':  apikey,
              'o':       'xml'}

    if not host.endswith('api'):
        if not host.endswith('/'):
            host += '/'
        host = urljoin(host, 'api')
        logger.fdebug('[TEST-NEWZNAB] Appending `api` to end of host: %s' % host)
    headers = {'User-Agent': str(mylar.USER_AGENT)}
    logger.info('host: %s' % host)
    try:
        r = requests.get(host, params=params, headers=headers, verify=bool(ssl))
    except Exception as e:
        logger.warn('Unable to connect: %s' % e)
        return
    else:
        try:
            data = parseString(r.content)
        except Exception as e:
            logger.warn('[WARNING] Error attempting to test: %s' % e)

        try:
            error_code = data.getElementsByTagName('error')[0].attributes['code'].value
        except Exception as e:
            logger.info('Connected - Status code returned: %s' % r.status_code)
            if r.status_code == 200:
                return True
            else:
                logger.warn('Received response - Status code returned: %s' % r.status_code)
                return False

        code = error_code
        description = data.getElementsByTagName('error')[0].attributes['description'].value
        logger.info('[ERROR:%s] - %s' % (code, description))
        return False

def torznab_test(name, host, ssl, apikey):
    from xml.dom.minidom import parseString, Element
    params = {'t':       'search',
              'apikey':  apikey,
              'o':       'xml'}

    if host[-1:] == '/':
        host = host[:-1]
    headers = {'User-Agent': str(mylar.USER_AGENT)}
    logger.info('host: %s' % host)
    try:
        r = requests.get(host, params=params, headers=headers, verify=bool(ssl))
    except Exception as e:
        logger.warn('Unable to connect: %s' % e)
        return
    else:
        try:
            data = parseString(r.content)
        except Exception as e:
            logger.warn('[WARNING] Error attempting to test: %s' % e)

        try:
            error_code = data.getElementsByTagName('error')[0].attributes['code'].value
        except Exception as e:
            logger.info('Connected - Status code returned: %s' % r.status_code)
            if r.status_code == 200:
                return True
            else:
                logger.warn('Received response - Status code returned: %s' % r.status_code)
                return False

        code = error_code
        description = data.getElementsByTagName('error')[0].attributes['description'].value
        logger.info('[ERROR:%s] - %s' % (code, description))
        return False

def get_free_space(folder):
    min_threshold = 100000000 #threshold for minimum amount of freespace available (#100mb)
    if platform.system() == "Windows":
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes))
        dst_freesize = free_bytes.value
    else:
        st = os.statvfs(folder)
        dst_freesize = st.f_bavail * st.f_frsize
    logger.fdebug('[FREESPACE-CHECK] %s has %s free' % (folder, sizeof_fmt(dst_freesize)))
    if min_threshold > dst_freesize:
        logger.warn('[FREESPACE-CHECK] There is only %s space left on %s' % (dst_freesize, folder))
        return False
    else:
        return True

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def getImage(comicid, url, issueid=None, thumbnail_path=None, apicall=False, overwrite=False):

    if thumbnail_path is None:
        if os.path.exists(mylar.CONFIG.CACHE_DIR):
            pass
        else:
            #let's make the dir.
            try:
                os.makedirs(str(mylar.CONFIG.CACHE_DIR))
                if apicall is False:
                    logger.info('Cache Directory successfully created at: %s' % mylar.CONFIG.CACHE_DIR)

            except OSError:
                if apicall is False:
                    logger.error('Could not create cache dir. Check permissions of cache dir: %s' % mylar.CONFIG.CACHE_DIR)

        coverfile = os.path.join(mylar.CONFIG.CACHE_DIR,  str(comicid) + '.jpg')
    else:
        coverfile = thumbnail_path

    #if cover has '+' in url it's malformed, we need to replace '+' with '%20' to retrieve properly.

    #new CV API restriction - one api request / second.(probably unecessary here, but it doesn't hurt)
    if mylar.CONFIG.CVAPI_RATE is None or mylar.CONFIG.CVAPI_RATE < 2:
        time.sleep(2)
    else:
        time.sleep(mylar.CONFIG.CVAPI_RATE)

    if apicall is False:
        logger.info('Attempting to retrieve the comic image for series')
    try:
        r = requests.get(url, params=None, stream=True, verify=mylar.CONFIG.CV_VERIFY, headers=mylar.CV_HEADERS)
    except Exception as e:
        if apicall is False:
            logger.warn('[ERROR: %s] Unable to download image from CV URL link: %s' % (e, url))
        coversize = 0
        statuscode = '400'
    else:
        statuscode = str(r.status_code)
        if apicall is False:
            logger.fdebug('comic image retrieval status code: %s' % statuscode)

        if statuscode != '200':
            if apicall is False:
                logger.warn('Unable to download image from CV URL link: %s [Status Code returned: %s]' % (url, statuscode))
            coversize = 0
        else:
            if os.path.exists(coverfile) and overwrite:
                try:
                    os.remove(coverfile)
                except Exception:
                    pass

            with open(coverfile, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()

            statinfo = os.stat(coverfile)
            coversize = statinfo.st_size

        #quick test for image integrity
        try:
            im = Image.open(coverfile)
        except OSError as e:
            logger.warn('Truncated image retrieved - trying alternate image file.')
            return {'coversize': coversize,
                    'status': 'retry'}

        return {'coversize': coversize,
                'status':    'success'}

    if any([int(coversize) < 10000, statuscode != '200']) and thumbnail_path is None:
        try:
            if statuscode != '200':
                if apicall is False:
                    logger.info('Trying to grab an alternate cover due to problems trying to retrieve the main cover image.')
            else:
                if apicall is False:
                    logger.info('Image size invalid [%s bytes] - trying to get alternate cover image.' % coversize)
        except Exception as e:
            if apicall is False:
                logger.info('Image size invalid [%s bytes] - trying to get alternate cover image.' % coversize)

        if apicall is False:
            logger.fdebug('invalid image link is here: %s' % url)

        if os.path.exists(coverfile):
            os.remove(coverfile)

        return {'coversize': coversize,
                'status':    'retry'}
    else:
        return {'coversize': coversize,
                'status':    'failed'}

def publisherImages(publisher):
    comicpublisher = None
    if mylar.CONFIG.INTERFACE == 'default':
        #these are specific images taht are better displayed in the default theme.
        if any([publisher == 'Image', publisher == 'Image Comics']):
            comicpublisher = {'publisher_image':       'images/publisherlogos/logo-imagecomics.png',
                              'publisher_image_alt':   'Image',
                              'publisher_imageH':      '125',
                              'publisher_imageW':      '75'}
        elif publisher == 'IDW Publishing':
            comicpublisher = {'publisher_image':       'images/publisherlogos/logo-idwpublish.png',
                              'publisher_image_alt':   'IDW',
                              'publisher_imageH':      '50',
                              'publisher_imageW':      '100'}
        elif publisher == 'Boom! Studios':
            comicpublisher = {'publisher_image':       'images/publisherlogos/logo-boom.jpg',
                              'publisher_image_alt':   'Boom!',
                              'publisher_imageH':      '50',
                              'publisher_imageW':      '100'}

    else:
        # --- for carbon theme (any non-white theme)
        if any([publisher == 'Image', publisher == 'Image Comics']):
            comicpublisher = {'publisher_image':       'images/publisherlogos/logo-imagecomics_carbon.png',
                              'publisher_image_alt':   'Image',
                              'publisher_imageH':      '125',
                              'publisher_imageW':      '75'}
        elif publisher == 'IDW Publishing':
            comicpublisher = {'publisher_image':       'images/publisherlogos/logo-idwpublish_carbon.png',
                              'publisher_image_alt':   'IDW',
                              'publisher_imageH':      '50',
                              'publisher_imageW':      '100'}
        elif publisher == 'Boom! Studios':
            comicpublisher = {'publisher_image':       'images/publisherlogos/logo-boom_carbon.png',
                              'publisher_image_alt':   'Boom!',
                              'publisher_imageH':      '50',
                              'publisher_imageW':      '100'}

    if comicpublisher is not None:
        return comicpublisher

    #--- all other logos are safe for current interface changes.
    if publisher == 'DC Comics':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-dccomics.png',
                          'publisher_image_alt':   'DC',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '75'}
    elif publisher == 'Marvel':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-marvel.png',
                          'publisher_image_alt':   'Marvel',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '100'}
    elif publisher == 'Dark Horse Comics' or publisher == 'Dark Horse':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-darkhorse.png',
                          'publisher_image_alt':   'DarkHorse',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '75'}
    elif publisher == 'Icon Comics':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-iconcomics.png',
                          'publisher_image_alt':   'Icon',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '100'}
    elif publisher == 'Magnetic Press':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-magneticpress.png',
                          'publisher_image_alt':   'Magnetic Press',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '100'}
    elif publisher == 'Max':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-max.png',
                          'publisher_image_alt':   'Max Comics',
                          'publisher_imageH':      '120',
                          'publisher_imageW':      '80'}
    elif publisher == 'Rebellion':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-rebellion.png',
                          'publisher_image_alt':   'Rebellion',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '100'}
    elif publisher == 'Red5':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-red5comics.png',
                          'publisher_image_alt':   'Red5',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '100'}
    elif publisher == 'Vertigo':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-vertigo.png',
                          'publisher_image_alt':   'Vertigo',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '100'}
    elif publisher == 'Shadowline':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-shadowline.png',
                          'publisher_image_alt':   'Shadowline',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '150'}
    elif publisher == 'Archie Comics':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-archiecomics.png',
                          'publisher_image_alt':   'Archie',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '75'}
    elif publisher == 'Oni Press':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-onipress.jpg',
                          'publisher_image_alt':   'Oni Press',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '100'}
    elif publisher == 'Tokyopop':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-tokyopop.jpg',
                          'publisher_image_alt':   'Tokyopop',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '50'}
    elif publisher == 'Midtown Comics':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-midtowncomics.jpg',
                          'publisher_image_alt':   'Midtown',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '100'}
    elif publisher == 'Skybound':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-skybound.jpg',
                          'publisher_image_alt':   'Skybound',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '100'}
    elif publisher == 'Dynamite Entertainment':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-dynamite.png',
                          'publisher_image_alt':   'Dynamite',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '125'}
    elif publisher == 'Top Cow':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-topcow.png',
                          'publisher_image_alt':   'Top Cow',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '100'}
    elif publisher == 'Cartoon Books':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-cartoonbooks.jpg',
                          'publisher_image_alt':   'Cartoon Books',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '90'}
    elif publisher == 'Valiant':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-valiant.png',
                          'publisher_image_alt':   'Valiant',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '100'}
    elif publisher == 'Action Lab':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-actionlabs.png',
                          'publisher_image_alt':   'Action Lab',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '100'}
    elif publisher == 'Aspen MLT':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-aspen.png',
                          'publisher_image_alt':   'Aspen MLT',
                          'publisher_imageH':      '65',
                          'publisher_imageW':      '65'}
    elif publisher == 'Zenescope Entertainment':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-zenescope.png',
                          'publisher_image_alt':   'Zenescope',
                          'publisher_imageH':      '125',
                          'publisher_imageW':      '125'}
    elif publisher == '2000 ad':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-2000ad.jpg',
                          'publisher_image_alt':   '2000 AD',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '50'}
    elif publisher == 'Aardvark':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-aardvark.png',
                          'publisher_image_alt':   'Aardvark',
                          'publisher_imageH':      '90',
                          'publisher_imageW':      '106'}
    elif publisher == 'Abstract Studio':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-abstract.png',
                          'publisher_image_alt':   'Abstract Studio',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '100'}
    elif publisher == 'Aftershock Comics':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-aftershock.png',
                          'publisher_image_alt':   'Aftershock',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '75'}
    elif publisher == 'Avatar Press':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-avatarpress.jpg',
                          'publisher_image_alt':   'Avatar Press',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '75'}
    elif publisher == 'Benitez Productions':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-benitez.png',
                          'publisher_image_alt':   'Benitez',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '125'}
    elif publisher == 'Boundless Comics':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-boundless.png',
                          'publisher_image_alt':   'Boundless',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '75'}
    elif publisher == 'Darby Pop':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-darbypop.png',
                          'publisher_image_alt':   'Darby Pop',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '125'}
    elif publisher == 'Devil\'s Due':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-devilsdue.png',
                          'publisher_image_alt':   'Devil\'s Due',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '75'}
    elif publisher == 'Joe Books':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-joebooks.png',
                          'publisher_image_alt':   'Joe Books',
                          'publisher_imageH':      '100',
                          'publisher_imageW':      '100'}
    elif publisher == 'Titan Comics':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-titan.png',
                          'publisher_image_alt':   'Titan',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '75'}
    elif publisher == 'Viz':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-viz.png',
                          'publisher_image_alt':   'Viz',
                          'publisher_imageH':      '50',
                          'publisher_imageW':      '50'}
    elif publisher == 'Warp Graphics':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-warpgraphics.png',
                          'publisher_image_alt':   'Warp Graphics',
                          'publisher_imageH':      '125',
                          'publisher_imageW':      '75'}
    elif any([publisher == 'WildStorm', publisher == 'Wildstorm']):
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-wildstorm.png',
                          'publisher_image_alt':   'Wildstorm',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '75'}
    elif publisher == 'AWA Studios':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-awa.png',
                          'publisher_image_alt':   'AWA Studios',
                          'publisher_imageH':      '75',
                          'publisher_imageW':      '125'}
    elif publisher == 'Bongo':
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-bongo.png',
                          'publisher_image_alt':   'Bongo',
                          'publisher_imageH':      '79',
                          'publisher_imageW':      '125'}

    if comicpublisher is None:
        comicpublisher = {'publisher_image':       'images/publisherlogos/logo-blank_publisher.png',
                          'publisher_image_alt':   None,
                          'publisher_imageH':      '0',
                          'publisher_imageW':      '0'}

    return comicpublisher

def lookupthebitches(filelist, folder, nzbname, nzbid, prov, hash, pulldate):
    #import db
    myDB = db.DBConnection()
    watchlist = listLibrary()
    matchlist = []
    #get the weeknumber/year for the pulldate
    dt = datetime.datetime.strptime(pulldate, '%Y-%m-%d')
    weeknumber = dt.strftime("%U")
    year = dt.strftime("%Y")
    for f in filelist:
        file = re.sub(folder, '', f).strip()
        pp = mylar.filechecker.FileChecker(justparse=True, file=file)
        parsedinfo = pp.listFiles()
        if parsedinfo['parse_status'] == 'success':
            dyncheck = re.sub('[\|\s]', '', parsedinfo['dynamic_name'].lower()).strip()
            check = myDB.selectone('SELECT * FROM weekly WHERE DynamicName=? AND weeknumber=? AND year=? AND STATUS<>"Downloaded"', [dyncheck, weeknumber, year]).fetchone()
            if check is not None:
                logger.fdebug('[%s] found match: %s #%s' % (file, check['COMIC'], check['ISSUE']))
                matchlist.append({'comicname':     check['COMIC'],
                                  'issue':         check['ISSUE'],
                                  'comicid':       check['ComicID'],
                                  'issueid':       check['IssueID'],
                                  'dynamicname':   check['DynamicName']})
        else:
            logger.fdebug('[%s] unable to match to the pull: %s' % (file, parsedinfo))

    if len(matchlist) > 0:
        for x in matchlist:
            if all([x['comicid'] not in watchlist, mylar.CONFIG.PACK_0DAY_WATCHLIST_ONLY is False]):
                oneoff = True
                mode = 'pullwant'
            elif all([x['comicid'] not in watchlist, mylar.CONFIG.PACK_0DAY_WATCHLIST_ONLY is True]):
                continue
            else:
                oneoff = False
                mode = 'want'
            mylar.updater.nzblog(x['issueid'], nzbname, x['comicname'], id=nzbid, prov=prov, oneoff=oneoff)
            mylar.updater.foundsearch(x['comicid'], x['issueid'], mode=mode, provider=prov, hash=hash)

def ignored_publisher_check(publisher):
    if publisher is not None:
        if mylar.CONFIG.IGNORED_PUBLISHERS is not None and any(
          [
            x for x in mylar.CONFIG.IGNORED_PUBLISHERS if any(
              [
                 x.lower() == publisher.lower(),
                 ('*' in x and re.sub(r'\*', '', x.lower()).strip() in publisher.lower()),
              ]
            )
          ]
        ):
            logger.fdebug('Ignored publisher [%s]. Ignoring this result.' % publisher)
            return True
    return False

def DateAddedFix():
    #import db
    myDB = db.DBConnection()
    DA_A = datetime.datetime.today()
    DateAdded = DA_A.strftime('%Y-%m-%d')
    issues = myDB.select("SELECT IssueID FROM issues WHERE Status='Wanted' and DateAdded is NULL")
    for da in issues:
        myDB.upsert("issues", {'DateAdded': DateAdded}, {'IssueID': da[0]})
    annuals = myDB.select("SELECT IssueID FROM annuals WHERE Status='Wanted' and DateAdded is NULL and not Deleted")
    for an in annuals:
        myDB.upsert("annuals", {'DateAdded': DateAdded}, {'IssueID': an[0]})


def statusChange(status_from, status_to, comicid=None, bulk=False, api=True):
    myDB = db.DBConnection()
    the_list = []
    if bulk is False: #type(comicid) != list:
        sc = myDB.select("SELECT IssueID FROM issues WHERE ComicID=? AND Status=?", [comicid, status_from])
        for s in sc:
            the_list.append({'table': 'issues', 'issueid': s['IssueID']})
        if mylar.CONFIG.ANNUALS_ON:
            ac = myDB.select("SELECT IssueID FROM annuals WHERE ComicID=? AND Status=?", [comicid, status_from])
            for s in ac:
                the_list.append({'table': 'annuals', 'issueid': s['IssueID']})
    else:
        if comicid == 'All':
            sc = myDB.select("SELECT IssueID FROM issues WHERE Status=?", [status_from])
            for s in sc:
                the_list.append({'table': 'issues', 'issueid': s['IssueID']})
            if mylar.CONFIG.ANNUALS_ON:
                ac = myDB.select("SELECT IssueID FROM annuals WHERE Status=?", [status_from])
                for s in ac:
                   the_list.append({'table': 'annuals', 'issueid': s['IssueID']})

        else:
            for x in comicid:
                sc = myDB.select("SELECT IssueID FROM issues WHERE ComicID=? AND Status=?", [x, status_from])
                for s in sc:
                    the_list.append({'table': 'issues', 'issueid': s['IssueID']})
                if mylar.CONFIG.ANNUALS_ON:
                    ac = myDB.select("SELECT IssueID FROM annuals WHERE ComicID=? AND Status=?", [x, status_from])
                    for s in ac:
                        the_list.append({'table': 'annuals', 'issueid': s['IssueID']})

    #logger.info('the_list: %s' % the_list)
    #for genlist in chunker(the_list, 200):
    #    tmpsql = "SELECT IssueID FROM issues WHERE Status=? AND ComicID in ({seq})".format(status_from, seq=','.join(['?'] *(len(genlist) -1)))
    #    chkthis = myDB.upsert("issues", {'Status': status_to}, dict(myDB.select(tmpsql, genlist))) #select(tmpsql, genlist)
    #    logger.info('succeeded')

    #this probably won't scale well, but atm it's the best that can be done
    cnt=0
    dlist = []
    for x in the_list:
        try:
            myDB.upsert(x['table'], {'Status': status_to}, {'IssueID': x['issueid'], 'Status': status_from})
        except Exception as e:
            pass
        else:
            cnt+=1

    rtnline = 'Updated %s Issues from a status of %s to %s' % (cnt, status_from, status_to)
    logger.info(rtnline)

    return rtnline

def file_ops(path,dst,arc=False,one_off=False,multiple=False):
#    # path = source path + filename
#    # dst = destination path + filename
#    # arc = to denote if the file_operation is being performed as part of a story arc or not where the series exists on the watchlist already
#    # one-off = if the file_operation is being performed where it is either going into the grabbab_dst or story arc folder

#    #get the crc of the file prior to the operation and then compare after to ensure it's complete.
#    crc_check = mylar.filechecker.crc(path)
#    #will be either copy / move

    softlink_type = 'absolute'

    if any([one_off, arc]):
        if multiple is True:
            action_op = 'copy'
        else:
            action_op = mylar.CONFIG.ARC_FILEOPS
        if mylar.CONFIG.ARC_FILEOPS_SOFTLINK_RELATIVE is True:
            softlink_type = 'relative'
    else:
        action_op = mylar.CONFIG.FILE_OPTS

    if action_op == 'copy' or (arc is True and any([action_op == 'copy', action_op == 'move'])):
        try:
            shutil.copy( path , dst )
#        if crc_check == mylar.filechecker.crc(dst):
        except Exception as e:
            logger.error('[%s] error : %s' % (action_op, e))
            return False
        return True

    elif action_op == 'move':
        try:
            shutil.move( path , dst )
#        if crc_check == mylar.filechecker.crc(dst):
        except Exception as e:
            logger.error('[MOVE] error : %s' % e)
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
                except OSError as e:
                    if e.errno == errno.EXDEV:
                        logger.warn('[' + str(e) + '] Hardlinking failure. Could not create hardlink - dropping down to copy mode so that this operation can complete. Intervention is required if you wish to continue using hardlinks.')
                        try:
                            shutil.copy( path, dst )
                            logger.fdebug('Successfully copied file to : ' + dst)
                            return True
                        except Exception as e:
                            logger.error('[COPY] error : %s' % e)
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

            elif action_op == 'softlink':
                try:
                    #first we need to copy the file to the new location, then create the symlink pointing from new -> original
                    if not arc:
                        shutil.move( path, dst )
                        if os.path.lexists( path ):
                            os.remove( path )
                        if softlink_type == 'absolute':
                            os.symlink( dst, path )
                            logger.fdebug('Successfully created softlink [' + dst + ' --> ' + path + ']')
                        else:
                            os.symlink(os.path.relpath(dst, os.path.dirname(path)), path)
                            logger.fdebug('Successfully created (relative) softlink [' + os.path.relpath(dst, os.path.dirname(path)) + ' --> ' + path + ']')

                    else:
                        if softlink_type == 'absolute':
                            os.symlink( path, dst )
                            logger.fdebug('Successfully created softlink [' + path + ' --> ' + dst + ']')
                        else:
                            os.symlink(os.path.relpath(path, os.path.dirname(dst)), dst)
                            logger.fdebug('Successfully created (relative) softlink [' + os.path.relpath(path, os.path.dirname(dst)) + ' --> ' + dst + ']')
                except OSError as e:
                    #if e.errno == errno.EEXIST:
                    #    os.remove(dst)
                    #    os.symlink( path, dst )
                    #else:
                    logger.warn('[' + str(e) + '] Unable to create symlink. Dropping down to copy mode so that this operation can continue.')
                    try:
                        shutil.copy( dst, path )
                        logger.fdebug('Successfully copied file [' + dst + ' --> ' + path + ']')
                    except Exception as e:
                        logger.error('[COPY] error : %s' % e)
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
            if mylar.CONFIG.FILE_OPTS == 'hardlink':
                try:
                    os.system(r'mklink /H dst path')
                    logger.fdebug('Successfully hardlinked file [' + dst + ' --> ' + path + ']')
                except OSError as e:
                    logger.warn('[' + e + '] Unable to create symlink. Dropping down to copy mode so that this operation can continue.')
                    try:
                        shutil.copy( dst, path )
                        logger.fdebug('Successfully copied file [' + dst + ' --> ' + path + ']')
                    except:
                        return False

            elif mylar.CONFIG.FILE_OPTS == 'softlink':  #ie. shortcut.
                try:
                    shutil.move( path, dst )
                    if os.path.lexists( path ):
                        os.remove( path )
                    os.system(r'mklink dst path')
                    logger.fdebug('Successfully created symlink [' + dst + ' --> ' + path + ']')
                except OSError as e:
                    raise e
                    logger.warn('[' + e + '] Unable to create softlink. Dropping down to copy mode so that this operation can continue.')
                    try:
                        shutil.copy( dst, path )
                        logger.fdebug('Successfully copied file [' + dst + ' --> ' + path + ']')
                    except:
                        return False


    else:
        return False

def log_that_exception(except_info):

    #snip the log here and get the last 100 lines as quick leadup glance.
    leadup = tail_that_log()

    #logger.info('[LEADUP_LOG] %s' % leadup)
    gather_info = {'comicname':   except_info.get('comicname', None),
                   'issuenumber': except_info.get('issuenumber', None),
                   'seriesyear':  except_info.get('seriesyear', None),
                   'issueid':     except_info.get('issueid', None),
                   'comicid':     except_info.get('comicid', None),
                   'searchmode':  except_info.get('mode', None),
                   'booktype':    except_info.get('booktype', None),
                   'filename':    except_info.get('filename', None),
                   'line_num':    except_info.get('line_num', None),
                   'func_name':   except_info.get('func_name', None),
                   'error_text':  except_info.get('err_text', None),
                   'error':       except_info.get('err', None),
                   'traceback':   except_info.get('traceback', None)}

    #write it to the exceptions table.
    logdate = now()
    myDB = db.DBConnection()
    myDB.upsert("exceptions_log", gather_info, {'date': logdate})

    #write the leadup log lines that were tailed above to the external file here...
    fileline = myDB.selectone("SELECT rowid from exceptions_log where date = ?", [logdate]).fetchone()
    with open(os.path.join(mylar.CONFIG.LOG_DIR, 'specific_' + str(fileline['rowid']) + '.log'), 'w') as f:
        f.writelines(leadup)
        f.write(except_info.get('traceback', None))

def tail_that_log():
    """Tail a file and get X lines from the end"""
    # place holder for the lines found
    lines_found = []

    f = open(os.path.join(mylar.CONFIG.LOG_DIR,'mylar.log'), 'r')
    lines = 100
    buffer = 4098

    # block counter will be multiplied by buffer
    # to get the block size from the end
    block_counter = -1

    # loop until we find X lines
    while len(lines_found) <= lines:
        try:
            f.seek(block_counter * buffer, os.SEEK_END)
        except IOError:  # either file is too small, or too many lines requested
            f.seek(0)
            lines_found = f.readlines()
            break

        lines_found = f.readlines()

        # we found enough lines, get out
        # Removed this line because it was redundant the while will catch
        # it, I left it for history
        # if len(lines_found) > lines:
        #    break

        # decrement the block counter to get the
        # next X bytes
        block_counter -= 1

    return lines_found[-lines:]

# Magic numbers for checks below
# Reference: https://www.garykessler.net/library/file_sigs.html
magic_numbers = {
    'PDF' : bytes([0x25, 0x50, 0x44, 0x46]),
    'ZIP' : bytes([0x50, 0x4B, 0x03, 0x04]),
    'RAR' : bytes([0x52, 0x61, 0x72, 0x21, 0x1A, 0x07]), # Should cover both v4 and v5
    '7Z' :  bytes([0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C])
}

def check_file_condition(file_path):
    """ Use magic numbers to confirm a file type, and do some sanity checks for quality of
        the file (CRC checks, etc.)

    Args:
        file_path (str): Location of the file to check

    Returns:
        dict: A dictionary containing a status (True/False for good/bad file), type (known file type),
            and quality (descriptive string)
    """
    if not os.path.isfile(file_path):
        return {'status': True, 'type' : 'unknown', 'quality': 'Asked to check something that does not exist or is a diretory.  Passing it for now.'}

    logger.fdebug(f'Checking file condition of {file_path}')

    max_number_length = max(len(m) for m in magic_numbers.values())
    try:
        with open(file_path, 'rb') as file:
            header = file.read(max_number_length)
    except Exception as e:
        logger.error(f"Could not open {file_path} to check for file type")
        return {'status': False, 'type' : 'unknown', 'quality': f'Failed to open file to check quality {e}.'}

    if header.startswith(magic_numbers['ZIP']):
        try:
            with zipfile.ZipFile(file_path, mode='r') as zf:
                test_result = zf.testzip()
                if test_result is not None:
                    return {'status': False, 'type' : 'ZIP', 'quality': f'CRC error in file {test_result}.'}
        except Exception as e:
            logger.fdebug("Issue working with zip file.  Likely a broken archive.")
            return {'status': False, 'type' : 'ZIP', 'quality': f'Error processing zip compressed file: {e}.'}

        return {'status': True, 'type' : 'ZIP', 'quality': 'Good condition.'}
    elif header.startswith(magic_numbers['RAR']):
        try:
            with rarfile.RarFile(file_path, mode='r') as rarf:
                test_result = rarf.testrar()
                if test_result is not None:
                    return {'status': False, 'type' : 'RAR', 'quality': f'CRC error in file {test_result}.'}
        except Exception as e:
            logger.fdebug("Issue working with rar file.  Likely a broken archive.")
            return {'status': False, 'type' : 'RAR', 'quality': f'Error processing rar compressed file: {e}.'}

        return {'status': True, 'type' : 'RAR', 'quality': 'Good condition.'}
    elif header.startswith(magic_numbers['7Z']):
        return {'status': True, 'type' : '7Z', 'quality': 'File is using 7zip compression.'}
    elif header.startswith(magic_numbers['PDF']):
        return {'status': True, 'type' : 'PDF', 'quality': 'PDF file.  No quality checks performed.'}
    else:
        return {'status': False, 'type' : 'unknown', 'quality': 'Unknown file type, unknown condition'}

def issue_number_to_int(number_part = None, string_part = None):
    """
    Calculate the numeric representation of an issue number based on the numeric and string components.  This prioritised the
    numeric part for sorting purposes.

    Parameters
    ----------
    number_part : float
        The numeric part of the issue number
    string_part : str
        The string decorations of the issue number

    Returns
    -------
    An integer representation of the issue number
    """
    # TODO: Add a check for integer overflow (miniscule risk) for SQLITE maxint - either limit it here as a preventative check, or handle it in database handler class.

    if number_part is None and string_part is None:
        return 0

    if string_part is None and isinstance(number_part, int):
        return number_part * 1000

    string_ordinal_sum = 0
    if string_part is not None:
        string_part = string_part.lower()
        for x in string_part:
            string_ordinal_sum += ord(x)

    # If the number is not visible within three decimal places, but non-zero, need to differentiate it from zero (e.g. Quantum and Woody)
    if (number_part is not None) and (0 < number_part < 0.001):
        string_ordinal_sum += 1

    if (number_part is not None) and (number_part < 0):
        string_ordinal_sum *= -1

    int_issuenum = round((0 if number_part is None else number_part) * 1000) + string_ordinal_sum

    return int_issuenum

def format_issue_number(number, zero_padding=0):
    """
    Consistent formatting string for numbers

    Parameters
    ----------
    number: str
        The numeric part of the issue number
    zero_padding : int
        Significant figures for padding the whole number part

    Returns
    -------
    Formatted string
    """
    negative = False
    if number[0] == '-':
        negative = True
        number = number[1:]

    split_num = number.split('.')

    whole = 0 if split_num[0] == '' else split_num[0]
    dec = 0 if len(split_num) == 1 else split_num[1]

    return f"{'-' if negative else ''}{whole:0>{zero_padding}}{'' if dec == 0 else f'.{dec}'}"


IssueNumber = namedtuple('IssueNumber', ['asInt', 'asString', 'asLegacy'], defaults=[None])
def issue_number_parser(issue_no, zero_padding=None, issue_id= None, from_data_source= False, pretty_string = False):
    """
    Returns a tuple of the integer representation of an issue "number", and the string representation for file naming.

    For ordering purposes, it will choose the first valid numeric string found in the issue number, and treat all remaining
    characters as decoration for differentiation purposes between two different "numbers".

    General approach is to minimise change to the raw issue number for the filename, for naming stability and avoiding
    creating a situation where a rename stops mylar from identifying the number again causing an archive status.  Any
    characters that are ill supported on filesystems should be dealt with, any any characters that represent numbers
    (fractions, infinity, etc.) should be converted for some semblance of sensible ordering.

    Parameters
    ----------
    issue_no         : str
        The issue number as a string
    issue_id         : str (optional)
        The IssueID for this issue for potential dupe detection within volumes
    from_data_source : bool
        If this has been called using data from a data source of record (e.g. ComicVine) then any string parts may be
        considered for addition to the exceptions list for file identification / matching
    pretty_string    : bool
        For efficiency saving, it will not generate the string formatted version by default.

    The below parameter will default to the global mylar config if not set.
    zero_padding : int (optional)
        The width of zero padding required for the numeric part string representation

    Returns
    -------
    A namedtuple of issue number representations.

    asInt    : int
        The integer representation of the issue number
    asString : str
        The formatted string representation of the issue number
    asLegacy : str
        The legacy issue number denoted by square brackets (if one exists)

    References
    ----------
    Here are a list of known awkward issue numbering examples that have been used to inform this method and
    their CV URLs correct at time of writing.

    Amazing Spider-Man 65.Deaths : https://comicvine.gamespot.com/the-amazing-spider-man/4050-142577/
    Ninjak 0 and 00 : https://comicvine.gamespot.com/ninjak/4050-5348/
    Wolverine & the X-Men 027AU : https://comicvine.gamespot.com/wolverine-the-x-men/4050-43539/
    Weapon Zero T-4 : https://comicvine.gamespot.com/weapon-zero/4050-19915/
    Super DC Giant S-27 : https://comicvine.gamespot.com/super-dc-giant/4050-2466/
    Earth X X, Earth X ½ : https://comicvine.gamespot.com/earth-x/4050-6354/
    Avengers 1½ : https://comicvine.gamespot.com/the-avengers/4050-2128/
    Shield Infinity 1 : https://comicvine.gamespot.com/shield-infinity/4050-112433/
    Prime Infinity ∞ : https://comicvine.gamespot.com/prime-infinity/4050-61187/ (see also https://comicvine.gamespot.com/the-night-man-infinity/4050-61188/)
    Wizard 207 (duplicated) : https://comicvine.gamespot.com/wizard-the-comics-magazine/4050-18692/
    X-O Manowar 050X : https://comicvine.gamespot.com/x-o-manowar/4050-4831/
    Amazing Spider-Man 92.BEY : https://comicvine.gamespot.com/the-amazing-spider-man/4050-112161/
    U-Comix 170/171 : https://comicvine.gamespot.com/u-comix-170-171/4000-472797/
    Spider-Man Badrock 1A : https://comicvine.gamespot.com/spider-manbadrock/4050-20275/
    Totally Awesome Hulk 1.MU : https://comicvine.gamespot.com/the-totally-awesome-hulk/4050-86408/
    Hulk -1 : https://comicvine.gamespot.com/the-incredible-hulk/4050-2406/
    Original Sin 3.3 : https://comicvine.gamespot.com/original-sin/4050-73241/
    Haunt of Fear 1 [15] : https://comicvine.gamespot.com/haunt-of-fear/4050-1398/
    God is Dead Alpha/Omega : https://comicvine.gamespot.com/god-is-dead-the-book-of-acts/4050-76270/
    Quantum and Woody 0.0001½ : https://comicvine.gamespot.com/quantum-and-woody/4050-105656/

    Still unsolved (need more filechecker changes):
    Army and Navy 1 #02: https://comicvine.gamespot.com/army-and-navy-fun-parade/4050-127823/
    Dark Fantasies 9 & 10: https://comicvine.gamespot.com/dark-fantasies/4050-24691/
    """
    #logger.debug(f'Attempting to process issue number "{issue_no}"')

    # if not isinstance(issue_no, str):
    #     logger.warn(f'Issue Number not a string, attempting to cast as one: {issue_no}')
    #     try:
    #         issue_no = str(issue_no)
    #     except:
    #         logger.error(f'Failed to convert issue number to string.  Defaulting to a large number.')
    #         return IssueNumber(999999999999999,'999999999999999')

    legacy_issue = None

    # Grab mylar's settings for number formatting
    #issueHashPrefix = False
    #if r'#$Issue' in mylar.CONFIG.FILE_FORMAT:
    #    issueHashPrefix = True

    if zero_padding is None:
        if mylar.CONFIG.ZERO_LEVEL_N == '0x':
            zero_padding = 2
        elif mylar.CONFIG.ZERO_LEVEL_N == '00x':
            zero_padding = 3
        else:
            zero_padding = 0

    try:
        if issue_no.isdigit():
            return IssueNumber(issue_number_to_int(int(issue_no)),format_issue_number(issue_no,zero_padding) if pretty_string else None, legacy_issue)
    except:
        if issue_no is None:
            return IssueNumber(999999999999999,'999999999999999')
        
        try:
            test_issue_no = str(issue_no)
            if test_issue_no.isdigit():
                return IssueNumber(issue_number_to_int(int(test_issue_no)),format_issue_number(test_issue_no,zero_padding) if pretty_string else None, legacy_issue)
        except:
            return IssueNumber(999999999999999,'999999999999999')

    # - Filename safety characters
    # - Hash marks as special for mylar identification
    if len(issue_no) > 0 and issue_no[0] == '#':
        issue_no = issue_no[1:]

    # Numbers traversing issues listed in CV as either A/B or C-D will get picked up as separate numbers by
    # the file checker.  Let's just consider them to be the first number for sorting and ordering purposes
    # Examples are Cerebus and U-Comix
    check_range = re.fullmatch(r'(?P<firstno>\d+)(?P<splitter>[\/\-])(?P<lastno>\d+)', issue_no)
    if check_range:
        first_no = check_range.group('firstno')
        last_no  = check_range.group('lastno')
        logger.fdebug(f'Issue number {issue_no} provided as range, sorting based on first number {first_no}')
        formatted_first_no = format_issue_number(first_no,zero_padding)
        formatted_last_no = format_issue_number(last_no,zero_padding)
        return IssueNumber(issue_number_to_int(float(first_no)), f"{formatted_first_no}-{formatted_last_no}" if pretty_string else None, legacy_issue)

    issue_no = re.sub(r'[\\/&#]', '.', issue_no)

    if issue_no == '':
        return IssueNumber(1,'')

    # Extract any legacy issue numbers and drop the legacy part
    if all([ '[' in issue_no, ']' in issue_no ]):
        legacy_start = issue_no.find('[')
        legacy_issue = issue_no[legacy_start+1:issue_no.find(']')]
        issue_no = issue_no[:legacy_start].strip()
        #logger.debug(f'Found legacy issue number [{legacy_issue}] and treating this as #{issue_no}')

    # Make the assumption that infinity is a) large for sorting b) uses the whole string for
    # differentiation (if not solo) and c) can be expressed in a filename without error
    if '\u221e' in issue_no:
        #logger.debug(f'Found infinity issue - setting to be very large')
        return IssueNumber(issue_number_to_int(9999999,issue_no), issue_no if pretty_string else None, legacy_issue)

    # Tries its best to account for multiple fractions in a number, but there really is a limit ...
    # fraction_chars = {'\xbc' : '25', '\xbd' : '5', '\xbe' : '75', '\u2152' : '1', '\u2153' : '33', '\u2154' : '67'}
    fraction_chars = {chr(x) : str(round(unicodedata.numeric(chr(x)),2))[2:] for x in itertools.chain(range(0x00BC, 0x00BF),range(0x2150,0x215F))}
    fractions_present = [x for x in fraction_chars.keys() if x in issue_no]
    # if len(fractions_present) > 0:
    #     logger.debug(f'Found fractions in issue number ({fractions_present}) - converting to decimal form')

    for fraction_char in fractions_present:
        # Substitue in order of solo entry (quickest), existing decimal prefix, then existing whole number prefix
        if issue_no == fraction_char:
            issue_no = f'0.{fraction_chars[fraction_char]}'
        else:
            decimal_search = fr'(?P<decimal>\.\d*)(?P<fraction>{fraction_char})'
            wholenum_search = fr'(?P<wholenum>\d*)(?P<fraction>{fraction_char})'

            # This has to be done sequentially for special case of 0.000¼0000¼
            while re.search(decimal_search, issue_no) is not None:
                issue_no = re.sub(decimal_search,fr'\g<decimal>{fraction_chars[fraction_char]}', issue_no, count=1)
            issue_no = re.sub(wholenum_search,fr'\g<wholenum>.{fraction_chars[fraction_char]}', issue_no)

    # Pre-scrub any commas within numbers for thousandths seperators
    issue_no = re.sub(r'(?P<prenum>\d),(?P<postnum>\d)',r'\g<prenum>\g<postnum>',issue_no)

    # Quick finish if we've already got a number after pre-processing
    try:
        float(issue_no)
    except ValueError:
        #logger.debug('Issue Number is not solely numeric, moving on')
        pass
    else:
        #logger.debug(f'Issue identified as numeric {issue_no}')
        return IssueNumber(issue_number_to_int(float(issue_no)),format_issue_number(issue_no,zero_padding) if pretty_string else None, legacy_issue)

    # Find the first recognisable numeric string, and use that to denote the issue "number"
    # Note that the regex will match empty strings so we need to filter this result set.  This was to
    # allow for decimals <1 with no leading 0
    numeric_parts = [x for x in re.findall(r'(?:-|\+)?\d*(?:\.\d{1,3})?', issue_no) if x != '']

    if len(numeric_parts) == 0:
        # Issue number is a pure string.
        #logger.debug('Issue Number is entirely String based')
        if from_data_source:
            add_issue_exception(issue_no, exception_type='Exact')
        return IssueNumber(issue_number_to_int(string_part=issue_no), issue_no if pretty_string else None, legacy_issue)
    else:
        numeric_part = numeric_parts[0]
        match_position = issue_no.find(numeric_part)
        # The filechecker has to operate on a l-r basis to avoid picking part of the volume as the issue number.  It also will remove full-stops, 
        # and spaces when processing so we need to remove these from the int calculation to ensure comparisons.  The calculation itself is case insensitive
        prefix = issue_no[:match_position]
        suffix = issue_no[match_position + len(numeric_part):]
        intIssueNumStringPart = re.sub(r'[\.\-]','',(prefix.strip() + suffix.strip()))

        # Manage the exception list if this issue number has come from CV
        # For string prefixed issues, the whole issue should be considered for matching, otherwise just the suffix
        if from_data_source:
            if len(prefix) > 0:
                add_issue_exception(issue_no, exception_type='Exact')
            else:
                add_issue_exception(re.sub(r'[\. ]','',suffix), exception_type='Exact')

        #logger.debug(f'Breaking Issue Number into parts and formatting number ({prefix},{numeric_part},{suffix})')
        formatted_number = format_issue_number(numeric_part,zero_padding)
        return IssueNumber(issue_number_to_int(float(numeric_part), intIssueNumStringPart), (prefix + formatted_number + suffix) if pretty_string else None, legacy_issue)

    logger.error(f'Something went horribly wrong and I could not work out the issue number from {issue_no}.  Somehow I have also bypassed the conditional above.')
    return IssueNumber(999999999999999,'999999999999999')

def issueExceptionCheck(checkString, full_match=True):
    if full_match:
        return any(re.fullmatch(pattern, checkString, re.IGNORECASE) for pattern in issue_exception_list('Pattern')) or any(exact.lower() == checkString.lower() for exact in issue_exception_list('Exact'))
    else:
        return any(re.search(pattern, checkString, re.IGNORECASE) for pattern in issue_exception_list('Pattern')) or any(exact.lower() in checkString.lower() for exact in issue_exception_list('Exact'))

def issue_exception_list(exception_type = 'Exact'):
    """Returns the superset of the inbuilt INBUILT_ISSUE_EXCEPTIONS and any stored in config.ini as CUSTOM_ISSUE_EXCEPTIONS

    Returns:
        list[str] : Issue numbering exceptions
    """
    if type(mylar.CONFIG.CUSTOM_ISSUE_EXCEPTIONS) != list:
        try:
            mylar.CONFIG.CUSTOM_ISSUE_EXCEPTIONS = json.loads(mylar.CONFIG.CUSTOM_ISSUE_EXCEPTIONS)
        except Exception:
            pass

    return [x[0] for x in
            [list(item) for item in set([tuple(entry) for entry in mylar.INBUILT_ISSUE_EXCEPTIONS] +
                                         [tuple(entry) for entry in mylar.CONFIG.CUSTOM_ISSUE_EXCEPTIONS])]
              if x[1] == exception_type]

def add_issue_exception(exception, exception_type='Exact'):
    """Check if a non-numeric issue number part is already covered by existing issue exceptions, and add it to
    the list if not covered.

    Args:
        exception (str) : The string exception to be checked against
        exception_type (Exact/Pattern) : The type of exception being checked
    """
    exception_exists = False
    if exception_type == 'Exact':
        if exception.lower() in [x.lower() for x in issue_exception_list(exception_type)] or any(re.fullmatch(pattern, exception, re.IGNORECASE) for pattern in issue_exception_list('Pattern')):
            exception_exists = True
    else:
        if exception.lower() in [x.lower() for x in issue_exception_list('Pattern')]:
            exception_exists = True

    if not exception_exists:
        logger.info(f'Issue numbering exception "{exception}" not found in list.  Adding to CUSTOM_ISSUE_EXCEPTIONS.')

        # Storing numeric exceptions is likely to cause problems.  Let's not.  If we can cast it, GTFO
        try:
            float(exception)
            logger.fdebug(f"Attempted to add {exception} as an issue number exception but it is numeric")
            return
        except ValueError:
            pass

        mylar.CONFIG.CUSTOM_ISSUE_EXCEPTIONS.append([exception, exception_type])
        mylar.CONFIG.writeconfig(values={'custom_issue_exceptions': json.dumps(mylar.CONFIG.CUSTOM_ISSUE_EXCEPTIONS)})

def where_am_i(ignore_host_return=False):
    """ Attempt to determine the externally facing URL for mylar.

    Args:
        ignore_host_return (bool, optional): Ignore the host_return config override. Defaults to False.

    Returns:
        str: A URL for mylar in the form protocol://address:port/
    """
    # generate the mylar host address if applicable.
    if mylar.CONFIG.ENABLE_HTTPS:
        proto = 'https://'
    else:
        proto = 'http://'

    if mylar.CONFIG.HTTP_ROOT is None:
        hroot = '/'
    elif mylar.CONFIG.HTTP_ROOT.endswith('/'):
        hroot = mylar.CONFIG.HTTP_ROOT
    else:
        if mylar.CONFIG.HTTP_ROOT != '/':
            hroot = mylar.CONFIG.HTTP_ROOT + '/'
        else:
            hroot = mylar.CONFIG.HTTP_ROOT

    if mylar.LOCAL_IP is None:
        # if mylar's local, get the local IP using socket.
        try:
            import socket

            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            mylar.LOCAL_IP = s.getsockname()[0]
            s.close()
        except Exception as e:
            logger.warn(
                'Unable to determine local IP. Defaulting to host address for'
                ' Mylar provided as : %s. Error returned: %s'
                % (mylar.CONFIG.HTTP_HOST, e)
            )

    if mylar.CONFIG.HOST_RETURN and not ignore_host_return:
        # mylar has the return value already provided
        # (easier and will work if it's right)
        if mylar.CONFIG.HOST_RETURN.endswith('/'):
            mylar_host = mylar.CONFIG.HOST_RETURN
        else:
            mylar_host = mylar.CONFIG.HOST_RETURN + '/'

    elif mylar.CONFIG.SAB_TO_MYLAR:
        # if sab & mylar are on different machines, check to see if they are
        # local or external IP's provided for host.
        if (
            mylar.CONFIG.HTTP_HOST == 'localhost'
            or mylar.CONFIG.HTTP_HOST == '0.0.0.0'
            or mylar.CONFIG.HTTP_HOST.startswith('10.')
            or mylar.CONFIG.HTTP_HOST.startswith('192.')
            or mylar.CONFIG.HTTP_HOST.startswith('172.')
        ):
            # if mylar's local, use the local IP already assigned to LOCAL_IP.
            mylar_host = (
                '%s%s:%s%s'
                % (proto, mylar.LOCAL_IP, mylar.CONFIG.HTTP_PORT, hroot)
                )
        else:
            if mylar.EXT_IP is None:
                # if mylar isn't local, get the external IP using pystun.
                import stun

                sip = mylar.CONFIG.HTTP_HOST
                port = int(mylar.CONFIG.HTTP_PORT)
                try:
                    nat_type, ext_ip, ext_port = stun.get_ip_info(sip, port)
                    mylar_host = (
                        '%s%s:%s%s'
                        % (proto, ext_ip, ext_port, hroot)
                        )
                    mylar.EXT_IP = ext_ip
                except Exception as e:
                    logger.warn(
                        'Unable to retrieve External IP - try using the'
                        ' host_return option in the config.ini. Error: %s' % e
                    )
                    mylar_host = (
                        '%s%s:%s%s'
                        % (proto, mylar.CONFIG.HTTP_HOST,
                            mylar.CONFIG.HTTP_PORT, hroot)
                    )
            else:
                mylar_host = (
                    '%s%s:%s%s'
                    % (proto, mylar.EXT_IP, mylar.CONFIG.HTTP_PORT, hroot)
                )

    else:
        # if all else fails, drop it back to the basic host:port and try that.
        if mylar.LOCAL_IP is None:
            tmp_host = mylar.CONFIG.HTTP_HOST
        else:
            tmp_host = mylar.LOCAL_IP
        mylar_host = (
            proto + str(tmp_host) + ':' + str(mylar.CONFIG.HTTP_PORT) + hroot
        )

    return mylar_host

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

