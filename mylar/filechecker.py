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
import os.path
import zlib
import pprint
import subprocess
import re
#import logger
import mylar 
from mylar import logger, helpers 
import unicodedata 
import sys 
import platform

def file2comicmatch(watchmatch):
    #print ("match: " + str(watchmatch))
    pass

def listFiles(dir,watchcomic,Publisher,AlternateSearch=None,manual=None,sarc=None):

    # use AlternateSearch to check for filenames that follow that naming pattern
    # ie. Star Trek TNG Doctor Who Assimilation won't get hits as the 
    # checker looks for Star Trek TNG Doctor Who Assimilation2 (according to CV)
    
    # we need to convert to ascii, as watchcomic is utf-8 and special chars f'it up
    u_watchcomic = unicodedata.normalize('NFKD', watchcomic).encode('ASCII', 'ignore') #watchcomic.encode('ascii', 'ignore').strip()
    logger.fdebug('[FILECHECKER] comic: ' + u_watchcomic)
    basedir = dir
    logger.fdebug('[FILECHECKER] Looking in: ' + dir)
    watchmatch = {}
    comiclist = []
    comiccnt = 0
    not_these = ['#',
               ',',
               '\/',
               ':',
               '\;',
               '.',
               '-',
               '!',
               '\$',
               '\%',
               '\+',
               '\'',
               '\?',
               '\@']

    issue_exceptions = ['AU',
                      '.INH',
                      '.NOW',
                      'AI', 
                      'A',
                      'B',
                      'C',
                      'X',
                      'O']

    extensions = ('.cbr', '.cbz', '.cb7')

#    #get the entire tree here
    dirlist = traverse_directories(basedir)

#    for item in os.listdir(basedir):
    for fname in dirlist:
        moddir = None
        # at a later point, we should store the basedir and scan it in for additional info, since some users
        # have their structure setup as 'Batman v2 (2011)/Batman #1.cbz' or 'Batman/V2-(2011)/Batman #1.cbz'
        if fname['directory'] == '':
            basedir = dir
        else:
            basedir = fname['directory']
            #if it's a subdir, strip out the main dir and retain the remainder for the filechecker to find it.
            #start at position 1 so the initial slash is removed since it's a sub, and os.path.join will choke.
            moddir = basedir.replace(dir,'')[1:].rstrip()

        item = fname['filename']

        #for mac OS metadata ignoring.
        if item.startswith('._'):
            logger.info('ignoring os metadata for ' + item)
            continue
             
        if item == 'cover.jpg' or item == 'cvinfo': continue
        if not item.lower().endswith(extensions):
            logger.fdebug('[FILECHECKER] filename not a valid cbr/cbz - ignoring: ' + item)
            continue

        #print item
        #subname = os.path.join(basedir, item)
        subname = item
        subname = re.sub('\_', ' ', subname)

        #Remove html code for ( )
        subname = re.sub(r'%28', '(', subname)
        subname = re.sub(r'%29', ')', subname)

        #versioning - remove it
        subsplit = subname.replace('_', ' ').split()
        volrem = None

        vers4year = "no"
        vers4vol = "no"

        for subit in subsplit:
            if subit[0].lower() == 'v':
                vfull = 0
                if subit[1:].isdigit():
                    #if in format v1, v2009 etc...
                    if len(subit[1:]) == 4: #v2013
                        # if it's greater than 3 in length, then the format is Vyyyy
                        logger.fdebug('[FILECHECKER] Version detected as : ' + str(subit))
                        vers4year = "yes"
                    else:
                        if len(subit) < 4:
                            logger.fdebug('[FILECHECKER] Version detected as : ' + str(subit))
                            vers4vol = str(subit)

                    subname = re.sub(subit, '', subname)
                    volrem = subit
                    vers4vol = volrem
                    break
                elif subit.lower()[:3] == 'vol':
                    #if in format vol.2013 etc
                    #because the '.' in Vol. gets removed, let's loop thru again after the Vol hit to remove it entirely
                    logger.fdebug('[FILECHECKER] volume indicator detected as version #:' + str(subit))
                    subname = re.sub(subit, '', subname)
                    volrem = subit
                    vers4year = "yes"
                    

        #check if a year is present in series title (ie. spider-man 2099)
        #also check if decimal present in series title (ie. batman beyond 2.0)
        #- check if brackets present in series title
        numberinseries = 'False'
        decimalinseries = 'False'
        bracketsinseries = 'False'

        for i in watchcomic.split():
            if i.isdigit():
                numberinseries = 'True'

            if ('20' in i or '19' in i):
                if i.isdigit():
                    numberinseries = 'True'
                else:
                    find20 = i.find('20')
                    if find20:
                        stf = i[find20:4].strip()
                    find19 = i.find('19')
                    if find19:
                        stf = i[find19:4].strip()
                    logger.fdebug('[FILECHECKER] stf is : ' + str(stf))
                    if stf.isdigit():
                        numberinseries = 'True'
            if ('.' in i):
                try:
                    float(i)
                    decimalinseries = 'True'
                    std = i
                    logger.fdebug('[FILECHECKER] std is : ' + str(std))
                except:
                    pass
            #logger.fdebug('[FILECHECKER] i : ' + str(i))
            if ('(' in i):
                bracketsinseries = 'True'
                bracket_length_st = watchcomic.find('(')
                bracket_length_en = watchcomic.find(')', bracket_length_st)
                bracket_length = bracket_length_en - bracket_length_st
                bracket_word = watchcomic[bracket_length_st:bracket_length_en]
                logger.fdebug('[FILECHECKER] bracketinseries: ' + str(bracket_word))

        logger.fdebug('[FILECHECKER] numberinseries: ' + str(numberinseries))
        logger.fdebug('[FILECHECKER] decimalinseries: ' + str(decimalinseries))
        logger.fdebug('[FILECHECKER] bracketinseries: ' + str(bracketsinseries))

        #remove the brackets..
        if bracketsinseries == 'True':
            logger.fdebug('[FILECHECKER] modifying subname to accomodate brackets within series title.')
            subnm_mod2 = re.findall('[^()]+', subname[bracket_length_en:])
            logger.fdebug('[FILECHECKER] subnm_mod : ' + str(subnm_mod2))
            
            subnm_mod = re.sub('[\(\)]',' ', subname[:bracket_length_en]) + str(subname[bracket_length_en+1:])
            logger.fdebug('[FILECHECKER] modified subname is now : ' + str(subnm_mod))
            subname = subnm_mod

        subnm = re.findall('[^()]+', subname)
        logger.fdebug('[FILECHECKER] subnm len : ' + str(len(subnm)))
        if len(subnm) == 1:
            logger.fdebug('[FILECHECKER] ' + str(len(subnm)) + ': detected invalid filename - attempting to detect year to continue')
            #if the series has digits this f's it up.
            if numberinseries == 'True' or decimalinseries == 'True':
                #we need to remove the series from the subname and then search the remainder.
                watchname = re.sub('[\:\;\!\'\/\?\+\=\_\%\.\-]', '', watchcomic)   #remove spec chars for watchcomic match.
                logger.fdebug('[FILECHECKER] watch-cleaned: ' + watchname)
                subthis = re.sub('.cbr', '', subname)
                subthis = re.sub('.cbz', '', subthis)
                subthis = re.sub('[\:\;\!\'\/\?\+\=\_\%\.\-]', '', subthis)
                subthis = re.sub('\s+',' ', subthis)
                logger.fdebug('[FILECHECKER] sub-cleaned: ' + subthis)
                #we need to make sure the file is part of the correct series or else will match falsely 
                if watchname not in subthis:
                    logger.fdebug('[FILECHECKER] this is a false match. Ignoring this result.')
                    continue
                subthis = subthis[len(watchname):]  #remove watchcomic
                #we need to now check the remainder of the string for digits assuming it's a possible year
                logger.fdebug('[FILECHECKER] new subname: ' + str(subthis))
                if subthis.startswith('('):
                    # if it startswith a bracket, then it's probably a year - let's check.
                    for i in subthis.split():
                        tmpi = re.sub('[\(\)]','',i).strip()
                        if tmpi.isdigit():
                            if (tmpi.startswith('19') or tmpi.startswith('20')) and len(tmpi) == 4:
                                logger.fdebug('[FILECHECKER] year detected: ' + str(tmpi))
                                subname = re.sub('(19\d{2}|20\d{2})(.*)', '\\2 (\\1)', subthis)
                                subname = re.sub('\(\)', '', subname).strip()
                                subname = watchcomic + ' ' + subname
                                logger.fdebug('[FILECHECKER] new subname reversed: ' + str(subname))
                                break
                else:
                    subname = re.sub('(.*)[\s+|_+](19\d{2}|20\d{2})(.*)', '\\1 \\2 (\\3)', subthis)

                subnm = re.findall('[^()]+', subname)
            else:
                subit = re.sub('(.*)[\s+|_+](19\d{2}|20\d{2})(.*)', '\\1 \\3 (\\2)', subname).replace('( )', '')
                subthis2 = re.sub('.cbr', '', subit)
                subthis1 = re.sub('.cbz', '', subthis2)
                subname = re.sub('[\:\;\!\'\/\?\+\=\_\%]', '', subthis1)
                #if '.' appears more than once at this point, then it's being used in place of spaces.
                #if '.' only appears once at this point, it's a decimal issue (since decimalinseries is False within this else stmt).
                if len(str(subname.count('.'))) == 1:
                    logger.fdebug('[FILECHECKER] decimal issue detected, not removing decimals')
                else:
                    logger.fdebug('[FILECHECKER] more than one decimal detected, and the series does not have decimals - assuming in place of spaces.')
                    subname = re.sub('[\.]', '', subname)
               
                subnm = re.findall('[^()]+', subname)
        else:
            if numberinseries == 'True' or decimalinseries == 'True':
                #we need to remove the series from the subname and then search the remainder.
                subthis = re.sub('.cbr', '', subname)
                subthis = re.sub('.cbz', '', subthis)
                if decimalinseries == 'True': 
                    watchname = re.sub('[\:\;\!\'\/\?\+\=\_\%\-]', '', watchcomic)   #remove spec chars for watchcomic match.
                    subthis = re.sub('[\:\;\!\'\/\?\+\=\_\%\-]', '', subthis)
                else:
                    # in order to get series like Earth 2 scanned in that contain a decimal, I removed the \. from the re.subs below - 28-08-2014
                    watchname = re.sub('[\:\;\!\'\/\?\+\=\_\%\-]', '', watchcomic)   #remove spec chars for watchcomic match.
                    subthis = re.sub('[\:\;\!\'\/\?\+\=\_\%\-]', '', subthis)
                logger.fdebug('[FILECHECKER] watch-cleaned: ' + watchname)
                subthis = re.sub('\s+',' ', subthis)
                logger.fdebug('[FILECHECKER] sub-cleaned: ' + subthis)
                #we need to make sure the file is part of the correct series or else will match falsely
                if watchname not in subthis:
                    logger.fdebug('[FILECHECKER] this is a false match. Ignoring this result.')
                    continue
                subthis = subthis[len(watchname):].strip()  #remove watchcomic
                #we need to now check the remainder of the string for digits assuming it's a possible year
                logger.fdebug('[FILECHECKER] new subname: ' + str(subthis))
                if subthis.startswith('('):
                    # if it startswith a bracket, then it's probably a year and the format is incorrect to continue - let's check.
                    for i in subthis.split():
                        tmpi = re.sub('[\(\)]','',i).strip()
                        if tmpi.isdigit():
                            if (tmpi.startswith('19') or tmpi.startswith('20')) and len(tmpi) == 4:
                                logger.fdebug('[FILECHECKER] Year detected: ' + str(tmpi))
                                subname = re.sub('(19\d{2}|20\d{2})(.*)', '\\2 (\\1)', subthis)
                                subname = re.sub('\(\)', '', subname).strip()
                                logger.fdebug('[FILECHECKER] Flipping the issue with the year: ' + str(subname))
                                break
                else:                        
                    numcheck = re.findall('[19\d{2}|20\d{2}]', subthis)
                    if len(numcheck) == 1:
                        subname = re.sub('(19\d{2}|20\d{2})(.*)', '\\2 (\\1)', subthis)
                    else:
                        subname = re.sub('(19\d{2}|20\d{2})(.*)', '\\1 (\\2)', subthis)
                    subname = re.sub('\(\)', '', subname).strip()

                subname = watchname + ' ' + subname
                subname = re.sub('\s+', ' ', subname).strip()

                logger.fdebug('[FILECHECKER] New subname reversed: ' + str(subname))
                subnm = re.findall('[^()]+', subname)


        subsplit = subname.replace('_', ' ').split()

        if sarc is None:
            if Publisher.lower() in re.sub('_', ' ', subname.lower()):
                #if the Publisher is given within the title or filename even (for some reason, some people
                #have this to distinguish different titles), let's remove it entirely.
                lenm = len(subnm)

                cnt = 0
                pub_removed = None

                while (cnt < lenm):
                    submod = re.sub('_', ' ', subnm[cnt])
                    if submod is None: break
                    if submod == ' ':
                        pass
                    else:
                        logger.fdebug('[FILECHECKER] ' + str(cnt) + ". Bracket Word: " + str(submod))

                    if Publisher.lower() in submod.lower() and cnt >= 1:
                        logger.fdebug('[FILECHECKER] Publisher detected within title : ' + str(submod))
                        logger.fdebug('[FILECHECKER] cnt is : ' + str(cnt) + ' --- Publisher is: ' + Publisher)
                        #-strip publisher if exists here-
                        pub_removed = submod
                        logger.fdebug('[FILECHECKER] removing publisher from title')
                        subname_pubremoved = re.sub(pub_removed, '', subname)
                        logger.fdebug('[FILECHECKER] pubremoved : ' + str(subname_pubremoved))
                        subname_pubremoved = re.sub('\(\)', '', subname_pubremoved) #remove empty brackets
                        subname_pubremoved = re.sub('\s+', ' ', subname_pubremoved) #remove spaces > 1
                        logger.fdebug('[FILECHECKER] blank brackets removed: ' + str(subname_pubremoved))
                        subnm = re.findall('[^()]+', subname_pubremoved)
                        break
                    cnt+=1

        #If the Year comes before the Issue # the subname is passed with no Issue number.
        #This logic checks for numbers before the extension in the format of 1 01 001 
        #and adds to the subname. (Cases where comic name is $Series_$Year_$Issue)

#        if len(subnm) > 1:
#            if (re.search('(19\d{2}|20\d{2})',subnm[1]) is not None):
#                logger.info('subnm[1]: ' + str(subnm[1]))
#                for i in subnm:
#                    tmpi = i.strip()
#                    if tmpi.isdigit():
#                        if (tmpi.startswith('19') or tmpi.startswith('20')) and len(tmpi) == 4:
#                            logger.info('[FILECHECKER] year detected: ' + str(tmpi))
#                            #strip out all the brackets in the subnm[2] if it exists so we're left with just the issue # in most cases
#                            subremoved = re.findall('[^()]+', subnm[2]).strip()
#                            if len(subremoved) > 5:
#                                logger.info('[FILECHECKER] something is wrong with the parsing - better report the issue on github.')
#                                break
#                            subname = re.sub('(.*)[\s+|_+](19\d{2}|20\d{2})(.*)', '\\1 ' + str(subremoved) + ' (\\2)', subname)
#                            subname = re.sub('\(\)', '', subname).strip()
#                            logger.info('[FILECHECKER] THE new subname reversed: ' + str(subname))
#                            break
#            else:
#                subname = re.sub('(.*)[\s+|_+](19\d{2}|20\d{2})(.*)', '\\1 \\2 (\\3)', subname)

#            subnm = re.findall('[^()]+', subname)  # we need to regenerate this here.
#            logger.fdebug('[FILECHECKER] subnm0: ' + str(subnm[0]))
#            logger.fdebug('[FILECHECKER] subnm1: ' + str(subnm[1]))
#                logger.fdebug('subnm2: ' + str(subnm[2]))
#                subname = str(subnm[0]).lstrip() + ' (' + str(subnm[1]).strip() + ') '

        subname = subnm[0]

        if len(subnm):
            # if it still has no year (brackets), check setting and either assume no year needed.
            subname = subname                
        logger.fdebug('[FILECHECKER] subname no brackets: ' + str(subname))
        nonocount = 0
        charpos = 0
        detneg = "no"
        leavehyphen = False
        should_restart = True
        lenwatch = len(watchcomic)  # because subname gets replaced dynamically, the length will change and things go wrong.
        while should_restart:
            should_restart = False
            for nono in not_these:
                if nono in subname:
                    subcnt = subname.count(nono)
                    charpos = indices(subname,nono) # will return a list of char positions in subname
                    #print "charpos: " + str(charpos)
                    if nono == '-':
                        i=0
                        while (i < len(charpos)):
                            for i,j in enumerate(charpos):
                                if j+2 > len(subname): 
                                    sublimit = subname[j+1:]
                                else:
                                    sublimit = subname[j+1:j+2]
                                if sublimit.isdigit():
                                    logger.fdebug('[FILECHECKER] possible negative issue detected.')
                                    nonocount = nonocount + subcnt - 1
                                    detneg = "yes"                                
                                elif '-' in watchcomic and j < lenwatch:
                                    lenwatch -=1
                                    logger.fdebug('[FILECHECKER] - appears in series title.')
                                    logger.fdebug('[FILECHECKER] up to - :' + subname[:j+1].replace('-', ' '))
                                    logger.fdebug('[FILECHECKER] after -  :' + subname[j+1:])
                                    subname = subname[:j+1].replace('-', '') + subname[j+1:]
                                    logger.fdebug('[FILECHECKER] new subname is : ' +  str(subname))
                                    should_restart = True
                                    leavehyphen = True
                            i+=1
                        if detneg == "no" and leavehyphen == False: 
                            subname = re.sub(str(nono), ' ', subname)
                            nonocount = nonocount + subcnt
                #logger.fdebug('[FILECHECKER] (str(nono) + " detected " + str(subcnt) + " times.")
                # segment '.' having a . by itself will denote the entire string which we don't want
                    elif nono == '.':
                        x = 0
                        fndit = 0
                        dcspace = 0
                        while x < subcnt:
                            fndit = subname.find(nono, fndit)
                            if subname[fndit-1:fndit].isdigit() and subname[fndit+1:fndit+2].isdigit():
                                logger.fdebug('[FILECHECKER] decimal issue detected.')
                                dcspace+=1
                            x+=1
                        if dcspace == 1:
                            nonocount = nonocount + subcnt + dcspace                    
                        else:
                            subname = re.sub('\.', ' ', subname)
                            nonocount = nonocount + subcnt - 1 #(remove the extension from the length)
                    else:
                        #this is new - if it's a symbol seperated by a space on each side it drags in an extra char.
                        x = 0
                        fndit = 0
                        blspc = 0
                        while x < subcnt:
                            fndit = subname.find(nono, fndit)
                            #print ("space before check: " + str(subname[fndit-1:fndit]))
                            #print ("space after check: " + str(subname[fndit+1:fndit+2]))
                            if subname[fndit-1:fndit] == ' ' and subname[fndit+1:fndit+2] == ' ':
                                logger.fdebug('[FILECHECKER] blankspace detected before and after ' + str(nono))
                                blspc+=1
                            x+=1
                        #logger.fdebug('[FILECHECKER] replacing ' + str(nono) + ' with a space')
                        subname = re.sub(str(nono), '', subname)
                        nonocount = nonocount + subcnt + blspc
        #subname = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\+\'\?\@]',' ', subname)
        if decimalinseries == 'True':
            modwatchcomic = re.sub('[\_\#\,\/\:\;\!\$\%\?\@]', ' ', u_watchcomic)
        else:
            modwatchcomic = re.sub('[\_\#\,\/\:\;\.\!\$\%\?\@]', ' ', u_watchcomic)
        if bracketsinseries == 'True':
            modwatchcomic = re.sub('[\(\)]', ' ', modwatchcomic)
        modwatchcomic = re.sub('[\-\']', '', modwatchcomic)   #trying this too - 2014-03-01
        #if leavehyphen == False:
        #    logger.fdebug('[FILECHECKER] ('removing hyphen for comparisons')
        #    modwatchcomic = re.sub('-', ' ', modwatchcomic)
        #    subname = re.sub('-', ' ', subname)
        detectand = False
        detectthe_mod = False
        detectthe_sub = False
        modwatchcomic = re.sub('\&', ' and ', modwatchcomic)
        if ' the ' in modwatchcomic.lower() or modwatchcomic.lower().startswith('the '):
            modwatchcomic = re.sub("\\bthe\\b", "", modwatchcomic.lower())
            logger.fdebug('[FILECHECKER] new modwatchcomic: ' + str(modwatchcomic))
            detectthe_mod = True
        modwatchcomic = re.sub('\s+', ' ', str(modwatchcomic)).strip()
        if '&' in subname:
            logger.fdebug('[FILECHECKER] detected & in subname')
            subname = re.sub('\&', ' and ', subname) 
            detectand = True
        if ' the ' in subname.lower() or subname.lower().startswith('the '):
            subname = re.sub("\\bthe\\b", "", subname.lower())
            detectthe_sub = True
        subname = re.sub('\s+', ' ', str(subname)).strip()

        AS_Alt = []
        AS_Tuple = []
        if AlternateSearch is not None:
            chkthealt = AlternateSearch.split('##')
            if chkthealt == 0:
                AS_Alternate = AlternateSearch
            for calt in chkthealt:
                AS_tupled = False
                AS_Alternate = re.sub('##','',calt)
                if '!!' in AS_Alternate:
                    # if it's !! present, it's the comicid associated with the series as an added annual.
                    # extract the !!, store it and then remove it so things will continue.
                    as_start = AS_Alternate.find('!!')
                    logger.fdebug('as_start: ' + str(as_start) + ' --- ' + str(AS_Alternate[as_start:]))
                    as_end = AS_Alternate.find('##', as_start)
                    if as_end == -1: as_end = len(AS_Alternate)
                    logger.fdebug('as_start: ' + str(as_end) + ' --- ' + str(AS_Alternate[as_start:as_end]))
                    AS_ComicID =  AS_Alternate[as_start+2:as_end]
                    logger.fdebug('[FILECHECKER] Extracted comicid for given annual : ' + str(AS_ComicID))
                    AS_Alternate = re.sub('!!' + str(AS_ComicID), '', AS_Alternate)
                    AS_tupled = True
                #same = encode.
                u_altsearchcomic = AS_Alternate.encode('ascii', 'ignore').strip()
                altsearchcomic = re.sub('[\_\#\,\/\:\;\.\!\$\%\+\?\@]', ' ', u_altsearchcomic)
                altsearchcomic = re.sub('[\-\']', '', altsearchcomic)  #because this is a watchcomic registered, use same algorithim for watchcomic
                altsearchcomic = re.sub('\&', ' and ', altsearchcomic)
                if detectthe_sub == True:
                    altsearchcomic = re.sub("\\bthe\\b", "", altsearchcomic.lower())
                altsearchcomic = re.sub('\s+', ' ', str(altsearchcomic)).strip()
               
                if AS_tupled:
                    AS_Tuple.append({"ComicID":      AS_ComicID,
                                     "AS_Alternate": altsearchcomic})
                AS_Alt.append(altsearchcomic)
        else:
            #create random characters so it will never match.
            altsearchcomic = "127372873872871091383 abdkhjhskjhkjdhakajhf"
            AS_Alt.append(altsearchcomic)
        #if '_' in subname:
        #    subname = subname.replace('_', ' ')
        logger.fdebug('[FILECHECKER] AS_Alt : ' + str(AS_Alt))
        logger.fdebug('[FILECHECKER] watchcomic:' + str(modwatchcomic) + ' ..comparing to found file: ' + str(subname))
        if modwatchcomic.lower() in subname.lower() or any(x.lower() in subname.lower() for x in AS_Alt):
            #if the alternate search name is almost identical, it won't match up because it will hit the 'normal' first.
            #not important for series' matches, but for annuals, etc it is very important.
            #loop through the Alternates picking out the ones that match and then do an overall loop.
            enable_annual = False
            loopchk = [x for x in AS_Alt if x.lower() in subname.lower()]
            if len(loopchk) > 0 and loopchk[0] != '':
                logger.fdebug('[FILECHECKER] This should be an alternate: ' + str(loopchk))
                if 'annual' in subname.lower():
                    logger.fdebug('[FILECHECKER] Annual detected - proceeding')
                    enable_annual = True

            else:
                loopchk = []

            if modwatchcomic.lower() in subname.lower() and enable_annual == False:
                loopchk.append(modwatchcomic)
                if 'annual' in subname.lower():
                    if 'bi annual' in subname.lower():
                        logger.fdebug('[FILECHECKER] BiAnnual detected - wouldn\'t Deadpool be proud?')
                        subname = re.sub('Bi Annual', 'BiAnnual', subname)
                        jtd_len = subname.lower().find('bi annual')
                        enable_annual = True
                    else:
                        logger.fdebug('[FILECHECKER] Annual detected - proceeding cautiously.')
                        jtd_len = subname.lower().find('annual')
                        enable_annual = False

            logger.fdebug('[FILECHECKER] Complete matching list of names to this file [' + str(len(loopchk)) + '] : ' + str(loopchk))

            for loopit in loopchk:
                modwatchcomic = loopit
                logger.fdebug('[FILECHECKER] AS_Tuple : ' + str(AS_Tuple))
                annual_comicid = None
                for ATS in AS_Tuple:
                    logger.fdebug('[FILECHECKER] ' + str(ATS['AS_Alternate']) + ' comparing to ' + str(subname[:len(ATS['AS_Alternate'])])) #str(modwatchcomic))
                    if ATS['AS_Alternate'].lower().strip() == str(subname[:len(ATS['AS_Alternate'])]).lower().strip(): #modwatchcomic
                        logger.fdebug('[FILECHECKER] Associating ComiciD : ' + str(ATS['ComicID']))
                        annual_comicid = str(ATS['ComicID'])
                        modwatchcomic = ATS['AS_Alternate']
                        break
                comicpath = os.path.join(basedir, item)
                logger.fdebug('[FILECHECKER] ' + modwatchcomic + ' - watchlist match on : ' + comicpath)
                comicsize = os.path.getsize(comicpath)
                #print ("Comicsize:" + str(comicsize))
                comiccnt+=1

                stann = 0

                cchk = modwatchcomic
                #else:
                #if modwatchcomic.lower() in subname.lower():
                #    cchk = modwatchcomic
                #else:
                #    cchk_ls = [x for x in AS_Alt if x.lower() in subname.lower()]
                #    cchk = cchk_ls[0]

                logger.fdebug('[FILECHECKER] cchk is : ' + str(cchk))
                logger.fdebug('[FILECHECKER] we should remove ' + str(nonocount) + ' characters')                

                findtitlepos = subname.find('-')
                if charpos != 0:
                    logger.fdebug('[FILECHECKER] detected ' + str(len(charpos)) + ' special characters')
                    for i,j in enumerate(charpos):
                        logger.fdebug('i,j:' + str(i) + ',' + str(j))
                        logger.fdebug(str(len(subname)) + ' - subname: ' + subname)
                        logger.fdebug("digitchk: " + str(subname[j:]))
                        if j >= len(subname):
                            logger.fdebug('[FILECHECKER] ' + str(j) + ' is >= ' + str(len(subname)) + ' .End reached. ignoring remainder.')
                            break
                        elif subname[j:] == '-':
                            if j <= len(subname) and subname[j+1].isdigit():
                                logger.fdebug('[FILECHECKER] negative issue detected.')
                                #detneg = "yes"
                        elif j > findtitlepos:
                            if subname[j:] == '#':
                                if subname[j+1].isdigit():
                                    logger.fdebug('[FILECHECKER] # detected denoting issue#, ignoring.')
                                else: 
                                    nonocount-=1
                            elif ('-' in watchcomic or '.' in watchcomic) and j < len(watchcomic):
                                logger.fdebug('[FILECHECKER] - appears in series title, ignoring.')
                            else:                             
                                logger.fdebug('[FILECHECKER] special character appears outside of title - ignoring @ position: ' + str(charpos[i]))
                                nonocount-=1

                #remove versioning here
                if volrem != None:
                    jtd_len = len(cchk)# + len(volrem)# + nonocount + 1 #1 is to account for space btwn comic and vol #
                else:
                    jtd_len = len(cchk)# + nonocount

                if sarc and mylar.READ2FILENAME:
                    removest = subname.find(' ') # the - gets removed above so we test for the first blank space...
                    if subname[:removest].isdigit():
                        jtd_len += removest + 1  # +1 to account for space in place of - 
                        logger.fdebug('[FILECHECKER] adjusted jtd_len to : ' + str(removest) + ' because of story-arc reading order tags')

                logger.fdebug('[FILECHECKER] nonocount [' + str(nonocount) + '] cchk [' + cchk + '] length [' + str(len(cchk)) + ']')

                #if detectand:
                #    jtd_len = jtd_len - 2 # char substitution diff between & and 'and' = 2 chars
                #if detectthe_mod == True and detectthe_sub == False:
                    #jtd_len = jtd_len - 3  # char subsitiution diff between 'the' and '' = 3 chars

                #justthedigits = item[jtd_len:]

                logger.fdebug('[FILECHECKER] final jtd_len to prune [' + str(jtd_len) + ']')
                logger.fdebug('[FILECHECKER] before title removed from FILENAME [' + str(item) + ']')
                logger.fdebug('[FILECHECKER] after title removed from FILENAME [' + str(item[jtd_len:]) + ']')
                logger.fdebug('[FILECHECKER] creating just the digits using SUBNAME, pruning first [' + str(jtd_len) + '] chars from [' + subname + ']')

                justthedigits_1 = subname[jtd_len:].strip()

                if enable_annual:
                    logger.fdebug('enable annual is on')
                    if annual_comicid is not None:
                       logger.fdebug('annual comicid is ' + str(annual_comicid))
                       if 'biannual' in modwatchcomic.lower():
                           logger.fdebug('bi annual detected')
                           justthedigits_1 = 'BiAnnual ' + str(justthedigits_1)
                       else:
                           logger.fdebug('annual detected')
                           justthedigits_1 = 'Annual ' + str(justthedigits_1)

                logger.fdebug('[FILECHECKER] after title removed from SUBNAME [' + justthedigits_1 + ']')

                #remove the title if it appears
                #findtitle = justthedigits.find('-')
                #if findtitle > 0 and detneg == "no":
                #    justthedigits = justthedigits[:findtitle]
                #    logger.fdebug('[FILECHECKER] ("removed title from name - is now : " + str(justthedigits))

                justthedigits = justthedigits_1.split(' ', 1)[0]
            
                digitsvalid = "false"
   
                for jdc in list(justthedigits):
                    #logger.fdebug('[FILECHECKER] ('jdc:' + str(jdc))
                    if not jdc.isdigit():
                        #logger.fdebug('[FILECHECKER] ('alpha')
                        jdc_start = justthedigits.find(jdc)
                        alpha_isschk = justthedigits[jdc_start:]
                        #logger.fdebug('[FILECHECKER] ('alpha_isschk:' + str(alpha_isschk))
                        for issexcept in issue_exceptions:
                            if issexcept.lower() in alpha_isschk.lower() and len(alpha_isschk) <= len(issexcept):
                                logger.fdebug('[FILECHECKER] ALPHANUMERIC EXCEPTION : [' + justthedigits + ']')
                                digitsvalid = "true"
                                break
                    if digitsvalid == "true": break

                try:
                    tmpthedigits = justthedigits_1.split(' ', 1)[1]
                    logger.fdebug('[FILECHECKER] If the series has a decimal, this should be a number [' + tmpthedigits + ']')
                    if 'cbr' in tmpthedigits.lower() or 'cbz' in tmpthedigits.lower():
                        tmpthedigits = tmpthedigits[:-3].strip()
                        logger.fdebug('[FILECHECKER] Removed extension - now we should just have a number [' + tmpthedigits + ']')
                    poss_alpha = tmpthedigits
                    if poss_alpha.isdigit():
                        digitsvalid = "true"
                        if (justthedigits.lower() == 'annual' and 'annual' not in watchcomic.lower()) or (annual_comicid is not None):
                            logger.fdebug('[FILECHECKER] ANNUAL DETECTED ['  + poss_alpha + ']')
                            justthedigits += ' ' + poss_alpha
                        else:
                            justthedigits += '.' + poss_alpha
                            logger.fdebug('[FILECHECKER] DECIMAL ISSUE DETECTED [' + justthedigits + ']')
                    else:
                        for issexcept in issue_exceptions:
                            decimalexcept = False
                            if '.' in issexcept:
                                decimalexcept = True
                                issexcept = issexcept[1:] #remove the '.' from comparison...
                            if issexcept.lower() in poss_alpha.lower() and len(poss_alpha) <= len(issexcept):
                                if decimalexcept:
                                    issexcept = '.' + issexcept
                                justthedigits += issexcept #poss_alpha
                                logger.fdebug('[FILECHECKER] ALPHANUMERIC EXCEPTION. COMBINING : [' + justthedigits + ']')
                                digitsvalid = "true"
                                break
                except:
                    tmpthedigits = None

    #            justthedigits = justthedigits.split(' ', 1)[0]
   
                #if the issue has an alphanumeric (issue_exceptions, join it and push it through)
                logger.fdebug('[FILECHECKER] JUSTTHEDIGITS [' + justthedigits + ']' )
                if digitsvalid == "true":
                    pass
                else:
                    if justthedigits.isdigit():
                        digitsvalid = "true"
                    else:
                        if '.' in justthedigits:
                            tmpdec = justthedigits.find('.')
                            b4dec = justthedigits[:tmpdec]
                            a4dec = justthedigits[tmpdec+1:]
                            if a4dec.isdigit() and b4dec.isdigit():
                                logger.fdebug('[FILECHECKER] DECIMAL ISSUE DETECTED')
                                digitsvalid = "true"
                        else:
                            try:
                                x = float(justthedigits)
                                #validity check
                                if x < 0:
                                    logger.fdebug("I've encountered a negative issue #: " + str(justthedigits) + ". Trying to accomodate.")
                                    digitsvalid = "true"
                                else: raise ValueError
                            except ValueError, e:
                                    logger.fdebug('Probably due to an incorrect match - I cannot determine the issue number from given issue #: ' + str(justthedigits))


                logger.fdebug('[FILECHECKER] final justthedigits [' + justthedigits + ']')
                if digitsvalid == "false": 
                    logger.fdebug('[FILECHECKER] Issue number not properly detected...ignoring.')
                    comiccnt -=1  # remove the entry from the list count as it was incorrrectly tallied.
                    continue            
            

                if manual is not None:
                    #this is needed for Manual Run to determine matches
                    #without this Batman will match on Batman Incorporated, and Batman and Robin, etc..

                    # in case it matches on an Alternate Search pattern, set modwatchcomic to the cchk value
                    modwatchcomic = cchk
                    logger.fdebug('[FILECHECKER] cchk = ' + cchk.lower())
                    logger.fdebug('[FILECHECKER] modwatchcomic = ' + modwatchcomic.lower())
                    logger.fdebug('[FILECHECKER] subname = ' + subname.lower())
                    comyear = manual['SeriesYear']
                    issuetotal = manual['Total']
                    comicvolume = manual['ComicVersion']
                    logger.fdebug('[FILECHECKER] SeriesYear: ' + str(comyear))
                    logger.fdebug('[FILECHECKER] IssueTotal: ' + str(issuetotal))
                    logger.fdebug('[FILECHECKER] Comic Volume: ' + str(comicvolume))
                    logger.fdebug('[FILECHECKER] volume detected: ' + str(volrem))

                    if comicvolume:
                        ComVersChk = re.sub("[^0-9]", "", comicvolume)
                        if ComVersChk == '' or ComVersChk == '1':
                            ComVersChk = 0
                    else:
                        ComVersChk = 0

                    # even if it's a V1, we need to pull the date for the given issue ID and get the publication year
                    # for the issue. Because even if it's a V1, if there are additional Volumes then it's possible that
                    # it will take the incorrect series. (ie. Detective Comics (1937) & Detective Comics (2011). 
                    # If issue #28 (2013) is found, it exists in both series, and because DC 1937 is a V1, it will bypass 
                    # the year check which will result in the incorrect series being picked (1937)


                    #set the issue/year threshold here.
                    #  2013 - (24issues/12) = 2011.
                    #minyear = int(comyear) - (int(issuetotal) / 12)

                    maxyear = manual['LatestDate'][:4]  # yyyy-mm-dd

                    #subnm defined at being of module.
                    len_sm = len(subnm)

                    #print ("there are " + str(lenm) + " words.")
                    cnt = 0
                    yearmatch = "none"
                    #vers4year = "no"
                    #vers4vol = "no"

                    logger.fdebug('[FILECHECKER] subsplit : ' + str(subsplit))

                    #for ct in subsplit:
                    #    if ct.lower().startswith('v') and ct[1:].isdigit():
                    #        logger.fdebug('[FILECHECKER] possible versioning..checking')
                    #        #we hit a versioning # - account for it
                    #        if ct[1:].isdigit():
                    #            if len(ct[1:]) == 4:  #v2013
                    #                logger.fdebug('[FILECHECKER] Version detected as ' + str(ct))
                    #                vers4year = "yes" #re.sub("[^0-9]", " ", str(ct)) #remove the v
                    #                break
                    #            else:
                    #                if len(ct) < 4:
                    #                    logger.fdebug('[FILECHECKER] Version detected as ' + str(ct))
                    #                    vers4vol = str(ct)
                    #                    break
                    #        logger.fdebug('[FILECHECKER] false version detection..ignoring.')

                    versionmatch = "false"
                    if vers4year is not "no" or vers4vol is not "no":

                        if comicvolume: #is not "None" and comicvolume is not None:
                            D_ComicVersion = re.sub("[^0-9]", "", comicvolume)
                            if D_ComicVersion == '':
                                D_ComicVersion = 0
                        else:
                            D_ComicVersion = 0

                        F_ComicVersion = re.sub("[^0-9]", "", volrem)
                        S_ComicVersion = str(comyear)
                        logger.fdebug('[FILECHECKER] FCVersion: ' + str(F_ComicVersion))
                        logger.fdebug('[FILECHECKER] DCVersion: ' + str(D_ComicVersion))
                        logger.fdebug('[FILECHECKER] SCVersion: ' + str(S_ComicVersion))

                        #if annualize == "true" and int(ComicYear) == int(F_ComicVersion):
                        #    logger.fdebug('[FILECHECKER] ("We matched on versions for annuals " + str(volrem))

                        try:
                            if int(F_ComicVersion) == int(D_ComicVersion) or int(F_ComicVersion) == int(S_ComicVersion):
                                logger.fdebug('[FILECHECKER] We matched on versions...' + str(volrem))
                                versionmatch = "true"
                                yearmatch = "false"
                            else:
                                logger.fdebug('[FILECHECKER] Versions wrong. Ignoring possible match.')
                        except ValueError:
                            logger.warning('[FILECHECKER] Unable to determine version number. This issue will be skipped.')

                    result_comyear = None
                    while (cnt < len_sm):
                        if subnm[cnt] is None: break
                        if subnm[cnt] == ' ':
                            pass
                        else:
                            logger.fdebug('[FILECHECKER] ' + str(cnt) + ' Bracket Word: ' + str(subnm[cnt]))

                            #if ComVersChk == 0:
                            #    logger.fdebug('[FILECHECKER] Series version detected as V1 (only series in existance with that title). Bypassing year check')
                            #    yearmatch = "true"
                            #    break
                        if subnm[cnt][:-2] == '19' or subnm[cnt][:-2] == '20':
                            logger.fdebug('[FILECHECKER] year detected: ' + str(subnm[cnt]))
                            result_comyear = subnm[cnt]
                            if int(result_comyear) <= int(maxyear) and int(result_comyear) >= int(comyear):
                                logger.fdebug('[FILECHECKER] ' + str(result_comyear) + ' is within the series range of ' + str(comyear) + '-' + str(maxyear))
                                #still possible for incorrect match if multiple reboots of series end/start in same year
                                yearmatch = "true"
                                break
                            else:
                                logger.fdebug('[FILECHECKER] ' + str(result_comyear) + ' - not right - year not within series range of ' + str(comyear) + '-' + str(maxyear))
                                yearmatch = "false"
                                break
                        cnt+=1
                    if versionmatch == "false":
                        if yearmatch == "false":
                            logger.fdebug('[FILECHECKER] Failed to match on both version and issue year.')
                            continue
                        else:
                            logger.fdebug('[FILECHECKER] Matched on year, not on version - continuing.')
                    else:
                         if yearmatch == "false":
                            logger.fdebug('[FILECHECKER] Matched on version, but not on year - continuing.')
                         else:
                            logger.fdebug('[FILECHECKER] Matched on both version, and issue year - continuing.')

                    logger.fdebug('[FILECHECKER] yearmatch string is : ' + str(yearmatch))

                    if yearmatch == "none":
                        if ComVersChk == 0:
                            logger.fdebug('[FILECHECKER] Series version detected as V1 (only series in existance with that title). Bypassing year check.')
                            yearmatch = "true"
                        else:
                            continue

                    if 'annual' in subname.lower():
                        subname = re.sub('annual', '', subname.lower())
                        subname = re.sub('\s+', ' ', subname)
                        #if the sub has an annual, let's remove it from the modwatch as well
                        modwatchcomic = re.sub('annual', '', modwatchcomic.lower())

                    #tmpitem = item[:jtd_len]
                    # if it's an alphanumeric with a space, rejoin, so we can remove it cleanly just below this.
                    substring_removal = None
                    poss_alpha = subname.split(' ')[-1:]
                    logger.fdebug('[FILECHECKER] poss_alpha: ' + str(poss_alpha))
                    logger.fdebug('[FILECHECKER] lenalpha: ' + str(len(''.join(poss_alpha))))
                    for issexcept in issue_exceptions:
                        if issexcept.lower()in str(poss_alpha).lower() and len(''.join(poss_alpha)) <= len(issexcept):
                            #get the last 2 words so that we can remove them cleanly
                            substring_removal = ' '.join(subname.split(' ')[-2:])
                            substring_join = ''.join(subname.split(' ')[-2:])
                            logger.fdebug('[FILECHECKER] substring_removal: ' + str(substring_removal))
                            logger.fdebug('[FILECHECKER] substring_join: ' + str(substring_join))
                            break

                    if substring_removal is not None:
                        sub_removed = subname.replace('_', ' ').replace(substring_removal, substring_join)
                    else:
                        sub_removed = subname.replace('_', ' ')
                    logger.fdebug('[FILECHECKER] sub_removed: ' + str(sub_removed))
                    split_sub = sub_removed.rsplit(' ',1)[0].split(' ')  #removes last word (assuming it's the issue#)
                    split_mod = modwatchcomic.replace('_', ' ').split()   #batman
                    logger.fdebug('[FILECHECKER] split_sub: ' + str(split_sub))
                    logger.fdebug('[FILECHECKER] split_mod: ' + str(split_mod))

                    x = len(split_sub)-1
                    scnt = 0
                    if x > len(split_mod)-1:
                        logger.fdebug('[FILECHECKER] number of words do not match...aborting.')
                    else:
                        while ( x > -1 ):
                            logger.fdebug(str(split_sub[x]) + ' comparing to ' + str(split_mod[x]))
                            if str(split_sub[x]).lower() == str(split_mod[x]).lower():
                                scnt+=1
                                logger.fdebug('[FILECHECKER] word match exact. ' + str(scnt) + '/' + str(len(split_mod)))
                            x-=1

                    wordcnt = int(scnt)
                    logger.fdebug('[FILECHECKER] scnt:' + str(scnt))
                    totalcnt = int(len(split_mod))
                    logger.fdebug('[FILECHECKER] split_mod length:' + str(totalcnt))
                    try:
                        spercent = (wordcnt/totalcnt) * 100
                    except ZeroDivisionError:
                        spercent = 0
                    logger.fdebug('[FILECHECKER] we got ' + str(spercent) + ' percent.')
                    if int(spercent) >= 80:
                        logger.fdebug('[FILECHECKER] this should be considered an exact match.Justthedigits:' + justthedigits)
                    else:
                        logger.fdebug('[FILECHECKER] failure - not an exact match.')
                        continue

                if manual:
                    #print item
                    #print comicpath
                    #print comicsize
                    #print result_comyear
                    #print justthedigits
                    comiclist.append({
                         'ComicFilename':           item,
                         'ComicLocation':           comicpath,
                         'ComicSize':               comicsize,
                         'ComicYear':               result_comyear,
                         'JusttheDigits':           justthedigits
                         })
                    #print('appended.')
#                   watchmatch['comiclist'] = comiclist
#                   break
                else:
                    if moddir is not None:
                        item = os.path.join(moddir, item)
                    comiclist.append({
                         'ComicFilename':           item,
                         'ComicLocation':           comicpath,
                         'ComicSize':               comicsize,
                         'JusttheDigits':           justthedigits,
                         'AnnualComicID':           annual_comicid
                         })
                #crcvalue = crc(comicpath)
                #logger.fdebug('[FILECHECKER] CRC is calculated as ' + str(crcvalue) + ' for : ' + item)
                watchmatch['comiclist'] = comiclist
                break
        else:
            #directory found - ignoring
            pass

    logger.fdebug('[FILECHECKER] you have a total of ' + str(comiccnt) + ' ' + watchcomic + ' comics')
    watchmatch['comiccount'] = comiccnt
    return watchmatch

def validateAndCreateDirectory(dir, create=False, module=None):
    if module is None:
        module = ''
    module += '[DIRECTORY-CHECK]'
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
                    os.makedirs(dir.rstrip(), permission )
                except OSError:
                    raise SystemExit(module + ' Could not create directory: ' + dir + '. Exiting....')
                return True
            else:
                logger.warn(module + ' Provided directory is blank, aborting')
                return False
    return False


def indices(string, char):
    return [ i for i,c in enumerate(string) if c == char ]

def traverse_directories(dir):
    filelist = []

    for (dirname, subs, files) in os.walk(dir):

        for fname in files:
            if dirname == dir:
                direc = ''
            else:
                direc = dirname
                if '.AppleDouble' in direc:
                    #Ignoring MAC OS Finder directory of cached files (/.AppleDouble/<name of file(s)>)
                    continue

            filelist.append({"directory":  direc,
                             "filename":   fname})

    logger.fdebug('there are ' + str(len(filelist)) + ' files.')
    #logger.fdeubg(filelist)

    return filelist

def crc(filename):
    #memory in lieu of speed (line by line)
    #prev = 0
    #for eachLine in open(filename,"rb"):
    #    prev = zlib.crc32(eachLine, prev)
    #return "%X"%(prev & 0xFFFFFFFF)

    #speed in lieu of memory (file into memory entirely)
    return "%X" % (zlib.crc32(open(filename,"rb").read()) & 0xFFFFFFFF)
