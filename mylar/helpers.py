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

import time
from operator import itemgetter
import datetime
import re
import platform
import itertools
import os
import mylar

def multikeysort(items, columns):

    comparers = [ ((itemgetter(col[1:].strip()), -1) if col.startswith('-') else (itemgetter(col.strip()), 1)) for col in columns]
    
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
    xlate = {0xc0:'A', 0xc1:'A', 0xc2:'A', 0xc3:'A', 0xc4:'A', 0xc5:'A',
        0xc6:'Ae', 0xc7:'C',
        0xc8:'E', 0xc9:'E', 0xca:'E', 0xcb:'E', 0x86:'e',
        0xcc:'I', 0xcd:'I', 0xce:'I', 0xcf:'I',
        0xd0:'Th', 0xd1:'N',
        0xd2:'O', 0xd3:'O', 0xd4:'O', 0xd5:'O', 0xd6:'O', 0xd8:'O',
        0xd9:'U', 0xda:'U', 0xdb:'U', 0xdc:'U',
        0xdd:'Y', 0xde:'th', 0xdf:'ss',
        0xe0:'a', 0xe1:'a', 0xe2:'a', 0xe3:'a', 0xe4:'a', 0xe5:'a',
        0xe6:'ae', 0xe7:'c',
        0xe8:'e', 0xe9:'e', 0xea:'e', 0xeb:'e', 0x0259:'e',
        0xec:'i', 0xed:'i', 0xee:'i', 0xef:'i',
        0xf0:'th', 0xf1:'n',
        0xf2:'o', 0xf3:'o', 0xf4:'o', 0xf5:'o', 0xf6:'o', 0xf8:'o',
        0xf9:'u', 0xfa:'u', 0xfb:'u', 0xfc:'u',
        0xfd:'y', 0xfe:'th', 0xff:'y',
        0xa1:'!', 0xa2:'{cent}', 0xa3:'{pound}', 0xa4:'{currency}',
        0xa5:'{yen}', 0xa6:'|', 0xa7:'{section}', 0xa8:'{umlaut}',
        0xa9:'{C}', 0xaa:'{^a}', 0xab:'<<', 0xac:'{not}',
        0xad:'-', 0xae:'{R}', 0xaf:'_', 0xb0:'{degrees}',
        0xb1:'{+/-}', 0xb2:'{^2}', 0xb3:'{^3}', 0xb4:"'",
        0xb5:'{micro}', 0xb6:'{paragraph}', 0xb7:'*', 0xb8:'{cedilla}',
        0xb9:'{^1}', 0xba:'{^o}', 0xbb:'>>',
        0xbc:'{1/4}', 0xbd:'{1/2}', 0xbe:'{3/4}', 0xbf:'?',
        0xd7:'*', 0xf7:'/'
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

    seconds = ms/1000
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

    mb = int(bytes)/1048576
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

    suffixes_table = [('bytes',0),('KB',0),('MB',1),('GB',2),('TB',2), ('PB',2)]

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
    num = s[:-1]
    assert num.isdigit() and letter in symbols
    num = float(num)
    prefix = {symbols[0]:1}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i+1)*10
    return int(num * prefix[letter])

def replace_all(text, dic):
    for i, j in dic.iteritems():
        text = text.replace(i, j)
    return text
    
def cleanName(string):

    pass1 = latinToAscii(string).lower()
    out_string = re.sub('[\/\@\#\$\%\^\*\+\"\[\]\{\}\<\>\=\_]', '', pass1).encode('utf-8')
    
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
        iss_decval = iss[iss_find+1:]
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

def rename_param(comicid, comicname, issue, ofilename, comicyear=None, issueid=None, annualize=None):
            import db, logger
            myDB = db.DBConnection()
            logger.fdebug('comicid: ' + str(comicid))
            logger.fdebug('issue#: ' + str(issue))
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
                if annualize is None:
                    chkissue = myDB.action("SELECT * from issues WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()
                else:
                    chkissue = myDB.action("SELECT * from annuals WHERE ComicID=? AND Issue_Number=?", [comicid, issue]).fetchone()

                if chkissue is None:
                    #rechk chkissue against int value of issue #
                    chkissue = myDB.action("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, issuedigits(issue)]).fetchone()
                    if chkissue is None:
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
            issuenzb = myDB.action("SELECT * from issues WHERE ComicID=? AND IssueID=?", [comicid,issueid]).fetchone()
            if issuenzb is None:
                logger.fdebug('not an issue, checking against annuals')
                issuenzb = myDB.action("SELECT * from annuals WHERE ComicID=? AND IssueID=?", [comicid,issueid]).fetchone()
                if issuenzb is None:
                    logger.fdebug('Unable to rename - cannot locate issue id within db')
                    return
                else:
                    annualize = True
            logger.fdebug('blah')
            #comicid = issuenzb['ComicID']
            issuenum = issuenzb['Issue_Number']
            #issueno = str(issuenum).split('.')[0]
            issue_except = 'None'
            if 'au' in issuenum.lower():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = ' AU'
            if '.' in issuenum:
                iss_find = issuenum.find('.')
                iss_b4dec = issuenum[:iss_find]
                iss_decval = issuenum[iss_find+1:]
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
            logger.fdebug('iss:' + str(iss))
            logger.fdebug('issueno:' + str(issueno))
            # issue zero-suppression here
            if mylar.ZERO_LEVEL == "0":
                zeroadd = ""
            else:
                if mylar.ZERO_LEVEL_N  == "none": zeroadd = ""
                elif mylar.ZERO_LEVEL_N == "0x": zeroadd = "0"
                elif mylar.ZERO_LEVEL_N == "00x": zeroadd = "00"

            logger.fdebug('Zero Suppression set to : ' + str(mylar.ZERO_LEVEL_N))

            if str(len(issueno)) > 1:
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
            else:
                prettycomiss = str(issueno)
                logger.fdebug('issue length error - cannot determine length. Defaulting to None:  ' + str(prettycomiss))

            logger.fdebug('Pretty Comic Issue is : ' + str(prettycomiss))
            issueyear = issuenzb['IssueDate'][:4]
            month = issuenzb['IssueDate'][5:7].replace('-','').strip()
            month_name = fullmonth(month)
            logger.fdebug('Issue Year : ' + str(issueyear))
            comicnzb= myDB.action("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
            publisher = comicnzb['ComicPublisher']
            logger.fdebug('Publisher: ' + str(publisher))
            series = comicnzb['ComicName']
            logger.fdebug('Series: ' + str(series))
            seriesyear = comicnzb['ComicYear']
            logger.fdebug('Year: '  + str(seriesyear))
            comlocation = comicnzb['ComicLocation']
            logger.fdebug('Comic Location: ' + str(comlocation))
            comversion = comicnzb['ComicVersion']
            if comversion is None:
                comversion = 'None'
            #if comversion is None, remove it so it doesn't populate with 'None'
            if comversion == 'None':
                chunk_f_f = re.sub('\$VolumeN','',mylar.FILE_FORMAT)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug('No version # found for series, removing from filename')
                logger.fdebug("new format: " + str(chunk_file_format))
            else:
                chunk_file_format = mylar.FILE_FORMAT

            if annualize is None:
                chunk_f_f = re.sub('\$Annual','',chunk_file_format)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug('not an annual - removing from filename paramaters')
                logger.fdebug('new format: ' + str(chunk_file_format))

            else:
                logger.fdebug('chunk_file_format is: ' + str(chunk_file_format))
                if '$Annual' not in chunk_file_format:
                #if it's an annual, but $annual isn't specified in file_format, we need to
                #force it in there, by default in the format of $Annual $Issue
                    prettycomiss = "Annual " + str(prettycomiss)
                    logger.fdebug('prettycomiss: ' + str(prettycomiss))

            file_values = {'$Series':    series,
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

            extensions = ('.cbr', '.cbz')

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
            logger.fdebug('New Filename: ' + str(nfilename))

            if mylar.LOWERCASE_FILENAMES:
                dst = (comlocation + "/" + nfilename).lower()
            else:
                dst = comlocation + "/" + nfilename
            logger.fdebug('Source: ' + str(ofilename))
            logger.fdebug('Destination: ' + str(dst))

            rename_this = { "destination_dir" : dst, 
                            "nfilename" : nfilename,
                            "issueid" : issueid,
                            "comicid" : comicid }

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

    return apiremoved

def ComicSort(comicorder=None,sequence=None,imported=None):
    if sequence:
        # if it's on startup, load the sql into a tuple for use to avoid record-locking
        i = 0
        import db, logger
        myDB = db.DBConnection()
        comicsort = myDB.action("SELECT * FROM comics ORDER BY ComicSortName COLLATE NOCASE")
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
                comicorder['SortOrder'] = ({'ComicID':'99999','ComicOrder':1})  
                comicorder['LastOrderNo'] = 1
                comicorder['LastOrderID'] = 99999
            else: 
                comicorder['SortOrder'] = comicorderlist
                comicorder['LastOrderNo'] = i-1
                comicorder['LastOrderID'] = comicorder['SortOrder'][i-1]['ComicID']
            logger.info('Sucessfully ordered ' + str(i-1) + ' series in your watchlist.')
            return comicorder
        elif sequence == 'update':
            mylar.COMICSORT['SortOrder'] = comicorderlist
            print ("i:" + str(i))
            if i == 0:
                placemnt = 1
            else:
                placemnt = int(i-1)
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
    basmonths = {'1':'January','2':'February','3':'March','4':'April','5':'May','6':'June','7':'July','8':'August','9':'September','10':'October','11':'November','12':'December'}

    for numbs in basmonths:
        if numbs in str(int(monthno)):
            monthconv = basmonths[numbs]

    return monthconv

def updateComicLocation():
    import db, logger
    myDB = db.DBConnection()
    if mylar.NEWCOM_DIR is not None:
        logger.info('Performing a one-time mass update to Comic Location')
        #create the root dir if it doesn't exist
        if os.path.isdir(mylar.NEWCOM_DIR):
            logger.info('Directory (' + mylar.NEWCOM_DIR + ') already exists! Continuing...')
        else:
            logger.info('Directory does not exist!')
            try:
                os.makedirs(mylar.NEWCOM_DIR)
                logger.info('Directory successfully created at: ' + mylar.NEWCOM_DIR)
            except OSError:
                logger.error('Could not create comicdir : ' + mylar.NEWCOM_DIR)
                return

        dirlist = myDB.select("SELECT * FROM comics")

        if dirlist is not None:
            for dl in dirlist:
                
                comversion = dl['ComicVersion']                
                if comversion is None:
                    comversion = 'None'
                #if comversion is None, remove it so it doesn't populate with 'None'
                if comversion == 'None':
                    chunk_f_f = re.sub('\$VolumeN','',mylar.FOLDER_FORMAT)
                    chunk_f = re.compile(r'\s+')
                    folderformat = chunk_f.sub(' ', chunk_f_f)
                else:
                    folderformat = mylar.FOLDER_FORMAT

                #remove all 'bad' characters from the Series Name in order to create directories.
                u_comicnm = dl['ComicName']
                u_comicname = u_comicnm.encode('ascii', 'ignore').strip()
                if ':' in u_comicname or '/' in u_comicname or ',' in u_comicname or '?' in u_comicname:
                    comicdir = u_comicname
                if ':' in comicdir:
                    comicdir = comicdir.replace(':','')
                if '/' in comicdir:
                    comicdir = comicdir.replace('/','-')
                if ',' in comicdir:
                    comicdir = comicdir.replace(',','')
                if '?' in comicdir:
                    comicdir = comicdir.replace('?','')
                else: comicdir = u_comicname


                values = {'$Series':        comicdir,
                          '$Publisher':     re.sub('!','',dl['ComicPublisher']),
                          '$Year':          dl['ComicYear'],
                          '$series':        dl['ComicName'].lower(),
                          '$publisher':     re.sub('!','',dl['ComicPublisher']).lower(),
                          '$VolumeY':       'V' + str(dl['ComicYear']),
                          '$VolumeN':       comversion
                          }

                if mylar.FFTONEWCOM_DIR:
                    #if this is enabled (1) it will apply the Folder_Format to all the new dirs
                    if mylar.FOLDER_FORMAT == '':
                        comlocation = re.sub(mylar.DESTINATION_DIR, mylar.NEWCOM_DIR, comicdir)
                    else:
                        first = replace_all(folderformat, values)                    
                        if mylar.REPLACE_SPACES:
                            #mylar.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                            first = first.replace(' ', mylar.REPLACE_CHAR)
                        comlocation = os.path.join(mylar.NEWCOM_DIR,first)

                else:
                    comlocation = re.sub(mylar.DESTINATION_DIR, mylar.NEWCOM_DIR, comicdir)

                ctrlVal = {"ComicID":    dl['ComicID']}
                newVal = {"ComicLocation": comlocation}
                myDB.upsert("Comics", newVal, ctrlVal)
                logger.fdebug('updated ' + dl['ComicName'] + ' to : ' + comlocation)
        #set the value to 0 here so we don't keep on doing this...
        mylar.LOCMOVE = 0
        mylar.config_write()
    else:
        logger.info('No new ComicLocation path specified - not updating.')
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
    #print "issnum : " + str(issnum)
    if str(issnum).isdigit():
        int_issnum = int( issnum ) * 1000
    else:
        if 'au' in issnum.lower() and issnum[:1].isdigit():
            int_issnum = (int(issnum[:-2]) * 1000) + ord('a') + ord('u')
        elif 'ai' in issnum.lower() and issnum[:1].isdigit():
            int_issnum = (int(issnum[:-2]) * 1000) + ord('a') + ord('i')
        elif 'inh' in issnum.lower():
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
        elif u'\xbd' in issnum:
            issnum = .5
            int_issnum = int(issnum) * 1000
        elif u'\xbc' in issnum:
            issnum = .25
            int_issnum = int(issnum) * 1000
        elif u'\xbe' in issnum:
            issnum = .75
            int_issnum = int(issnum) * 1000
        elif u'\u221e' in issnum:
            #issnum = utf-8 will encode the infinity symbol without any help
            int_issnum = 9999999999 * 1000  # set 9999999999 for integer value of issue
        elif '.' in issnum or ',' in issnum:
            #logger.fdebug('decimal detected.')
            if ',' in issnum: issnum = re.sub(',','.', issnum)
            issst = str(issnum).find('.')
            if issst == 0:
                issb4dec = 0
            else:
                issb4dec = str(issnum)[:issst]
            decis = str(issnum)[issst+1:]
            if len(decis) == 1:
                decisval = int(decis) * 10
                issaftdec = str(decisval)
            if len(decis) >= 2:
                decisval = int(decis)
                issaftdec = str(decisval)
            try:
                int_issnum = (int(issb4dec) * 1000) + (int(issaftdec) * 10)
            except ValueError:
                #logger.fdebug('This has no issue # for me to get - Either a Graphic Novel or one-shot.')
                int_issnum = 999999999999999
        else:
            try:
                x = float(issnum)
                #validity check
                if x < 0:
                    #logger.info("I've encountered a negative issue #: " + str(issnum) + ". Trying to accomodate.")
                    int_issnum = (int(x)*1000) - 1
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
                        issno = issnum[:x].rstrip()
                        try:
                            isschk = float(issno)
                        except ValueError, e:
                            logger.fdebug('invalid numeric for issue - cannot be found. Ignoring.')
                            issno = None
                            tstord = None
                            invchk = "true"
                        break
                    x+=1
                if tstord is not None and issno is not None:
                    logger.fdebug('tstord: ' + str(tstord))
                    a = 0
                    ordtot = 0
                    while (a < len(tstord)):
                        try:
                            ordtot += ord(tstord[a].lower())  #lower-case the letters for simplicty
                        except ValueError:
                            break
                        a+=1
                    logger.fdebug('issno: ' + str(issno))
                    int_issnum = (int(issno) * 1000) + ordtot
                    logger.fdebug('intissnum : ' + str(int_issnum))
                elif invchk == "true":
                    logger.fdebug('this does not have an issue # that I can parse properly.')
                    int_issnum = 999999999999999
                else:
                    logger.error(str(issnum) + 'this has an alpha-numeric in the issue # which I cannot account for.')
                    int_issnum = 999999999999999
    return int_issnum


def checkthepub(ComicID):
    import db, logger
    myDB = db.DBConnection()
    publishers = ['marvel', 'dc', 'darkhorse']
    pubchk = myDB.action("SELECT * FROM comics WHERE ComicID=?", [ComicID]).fetchone()
    if pubchk is None:
        logger.fdebug('No publisher information found to aid in determining series..defaulting to base check of 55 days.')
        return mylar.BIGGIE_PUB
    else:
        for publish in publishers:
            if publish in str(pubchk['ComicPublisher']).lower():
                logger.fdebug('Biggie publisher detected - ' + str(pubchk['ComicPublisher']))
                return mylar.BIGGIE_PUB

        logger.fdebug('Indie publisher detected - ' + str(pubchk['ComicPublisher']))
        return mylar.INDIE_PUB

def annual_update():
    import db, logger
    myDB = db.DBConnection()
    annuallist = myDB.action('SELECT * FROM annuals')
    if annuallist is None:
        logger.info('no annuals to update.')
        return

    cnames = []
    #populate the ComicName field with the corresponding series name from the comics table.
    for ann in annuallist:
        coms = myDB.action('SELECT * FROM comics WHERE ComicID=?', [ann['ComicID']]).fetchone()
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
    elif int(readorder) > 10 and int(readorder) < 99: readord = "0" + str(readorder)
    else: readord = str(readorder)

    return readord

def latestdate_fix():
    import db, logger
    datefix = []
    myDB = db.DBConnection()
    comiclist = myDB.action('SELECT * FROM comics')
    if comiclist is None:
        logger.fdebug('No Series in watchlist to correct latest date')
        return
    for cl in comiclist:
        latestdate = cl['LatestDate']
        #logger.fdebug("latestdate:  " + str(latestdate))
        if latestdate[8:] == '':
            #logger.fdebug("invalid date " + str(latestdate) + " appending 01 for day to avoid errors")
            if len(latestdate) <= 7:
                finddash = latestdate.find('-')
                #logger.info('dash found at position ' + str(finddash))
                if finddash != 4:  #format of mm-yyyy
                    lat_month = latestdate[:finddash]
                    lat_year = latestdate[finddash+1:]
                else:  #format of yyyy-mm
                    lat_month = latestdate[finddash+1:]
                    lat_year = latestdate[:finddash]

                latestdate = (lat_year) + '-' + str(lat_month) + '-01'
                datefix.append({"comicid":    cl['ComicID'],
                                "latestdate": latestdate})
                #logger.info('latest date: ' + str(latestdate))

    #now we fix.
    if len(datefix) > 0:
       for df in datefix:
          newCtrl = {"ComicID":    df['comicid']}
          newVal = {"LatestDate":  df['latestdate']}
          myDB.upsert("comics", newVal, newCtrl)
    return

def checkFolder():
    import PostProcessor, logger
    #monitor a selected folder for 'snatched' files that haven't been processed
    logger.info('Checking folder ' + mylar.CHECK_FOLDER + ' for newly snatched downloads')
    PostProcess = PostProcessor.PostProcessor('Manual Run', mylar.CHECK_FOLDER)
    result = PostProcess.Process()
    logger.info('Finished checking for newly snatched downloads')

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
            AS_Alter = re.sub('##','',calt)
            u_altsearchcomic = AS_Alter.encode('ascii', 'ignore').strip()
            AS_formatrem_seriesname = re.sub('\s+', ' ', u_altsearchcomic)
            if AS_formatrem_seriesname[:1] == ' ': AS_formatrem_seriesname = AS_formatrem_seriesname[1:]

            AS_Alt.append({"AlternateName": AS_formatrem_seriesname})
            alt_count+=1

        Alternate_Names['AlternateName'] = AS_Alt
        Alternate_Names['ComicID'] = comicid
        Alternate_Names['Count'] = alt_count
        #logger.info('AlternateNames returned:' + str(Alternate_Names))

        return Alternate_Names
