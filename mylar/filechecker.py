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
import pprint
import subprocess
import re
import logger
import mylar
import sys

def file2comicmatch(watchmatch):
    #print ("match: " + str(watchmatch))
    pass

def listFiles(dir,watchcomic,AlternateSearch=None):
    # use AlternateSearch to check for filenames that follow that naming pattern
    # ie. Star Trek TNG Doctor Who Assimilation won't get hits as the 
    # checker looks for Star Trek TNG Doctor Who Assimilation2 (according to CV)
    
    # we need to convert to ascii, as watchcomic is utf-8 and special chars f'it up
    u_watchcomic = watchcomic.encode('ascii', 'ignore').strip()    
    logger.fdebug("comic: " + watchcomic)
    basedir = dir
    logger.fdebug("Looking in: " + dir)
    watchmatch = {}
    comiclist = []
    comiccnt = 0
    not_these = ['\#',
               ',',
               '\/',
               ':',
               '\;',
               '.',
               '-',
               '\!',
               '\$',
               '\%',
               '\+',
               '\'',
               '\?',
               '\@']


    for item in os.listdir(basedir):
        #print item
        #subname = os.path.join(basedir, item)
        subname = item
        #versioning - remove it
        subsplit = subname.split()
        volrem = None
        for subit in subsplit:
            #print ("subit:" + str(subit))
            if 'v' in str(subit).lower():
                #print ("possible versioning detected.")
                vfull = 0
                if subit[1:].isdigit():
                    #if in format v1, v2009 etc...
                    if len(subit) > 3:
                        # if it's greater than 3 in length, then the format is Vyyyy
                        vfull = 1 # add on 1 character length to account for extra space
                    #print (subit + "  - assuming versioning. Removing from initial search pattern.")
                    subname = re.sub(str(subit), '', subname)
                    volrem = subit
                if subit.lower()[:3] == 'vol':
                    #if in format vol.2013 etc
                    #because the '.' in Vol. gets removed, let's loop thru again after the Vol hit to remove it entirely
                    #print ("volume detected as version #:" + str(subit))
                    subname = re.sub(subit, '', subname)
                    volrem = subit

        #remove the brackets..
        subname = re.findall('[^()]+', subname)
        logger.fdebug("subname no brackets: " + str(subname[0]))
        subname = re.sub('\_', ' ', subname[0])
        nonocount = 0
        for nono in not_these:
            if nono in subname:
                subcnt = subname.count(nono)
                #logger.fdebug(str(nono) + " detected " + str(subcnt) + " times.")
                # segment '.' having a . by itself will denote the entire string which we don't want
                if nono == '.':
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
                            logger.fdebug("blankspace detected before and after " + str(nono))
                            blspc+=1
                        x+=1
                    subname = re.sub(str(nono), ' ', subname)
                    nonocount = nonocount + subcnt + blspc
        #subname = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\+\'\?\@]',' ', subname)
        modwatchcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\'\?\@]', ' ', u_watchcomic)
        detectand = False
        modwatchcomic = re.sub('\&', ' and ', modwatchcomic)
        modwatchcomic = re.sub('\s+', ' ', str(modwatchcomic)).strip()
        if '&' in subname:
            subname = re.sub('\&', ' and ', subname) 
            detectand = True
        subname = re.sub('\s+', ' ', str(subname)).strip()
        if AlternateSearch is not None:
            #same = encode.
            u_altsearchcomic = AlternateSearch.encode('ascii', 'ignore').strip()
            altsearchcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\+\'\?\@]', ' ', u_altsearchcomic)
            altseachcomic = re.sub('\&', ' and ', altsearchcomic)
            altsearchcomic = re.sub('\s+', ' ', str(altsearchcomic)).strip()       
        else:
            #create random characters so it will never match.
            altsearchcomic = "127372873872871091383 abdkhjhskjhkjdhakajhf"
        #if '_' in subname:
        #    subname = subname.replace('_', ' ')
        logger.fdebug("watchcomic:" + str(modwatchcomic) + " ..comparing to found file: " + str(subname))
        if modwatchcomic.lower() in subname.lower() or altsearchcomic.lower() in subname.lower():
            if 'annual' in subname.lower():
                #print ("it's an annual - unsure how to proceed")
                continue
            comicpath = os.path.join(basedir, item)
            logger.fdebug( modwatchcomic + " - watchlist match on : " + comicpath)
            comicsize = os.path.getsize(comicpath)
            #print ("Comicsize:" + str(comicsize))
            comiccnt+=1
            if modwatchcomic.lower() in subname.lower():
                #logger.fdebug("we should remove " + str(nonocount) + " characters")                
                #remove versioning here
                if volrem != None:
                    jtd_len = len(modwatchcomic) + len(volrem) + nonocount + 1 #1 is to account for space btwn comic and vol #
                else:
                    jtd_len = len(modwatchcomic) + nonocount
                if detectand:
                    jtd_len = jtd_len - 2 # char substitution diff between & and 'and' = 2 chars
            elif altsearchcomic.lower() in subname.lower():
                #remove versioning here
                if volrem != None:
                    jtd_len = len(altsearchcomic) + len(volrem) + nonocount + 1
                else:
                    jtd_len = len(altsearchcomic) + nonocount
                if detectand: 
                    jtd_len = jtd_len - 2

            justthedigits = item[jtd_len:]

            comiclist.append({
                 'ComicFilename':           item,
                 'ComicLocation':           comicpath,
                 'ComicSize':               comicsize,
                 'JusttheDigits':           justthedigits
                 })
            watchmatch['comiclist'] = comiclist
        else:
            pass
            #print ("directory found - ignoring")
    logger.fdebug("you have a total of " + str(comiccnt) + " " + watchcomic + " comics")
    watchmatch['comiccount'] = comiccnt
    return watchmatch

def validateAndCreateDirectory(dir, create=False):
    if os.path.exists(dir):
        logger.info("Found comic directory: " + dir)
        return True
    else:
        logger.warn("Could not find comic directory: " + dir)
        if create:
            if dir.strip():
                logger.info("Creating comic directory ("+str(mylar.CHMOD_DIR)+") : " + dir)
                try:
                    permission = int(mylar.CHMOD_DIR, 8)
                    os.umask(0) # this is probably redudant, but it doesn't hurt to clear the umask here.
                    os.makedirs(str(dir), permission )
                except OSError:
                    raise SystemExit('Could not create data directory: ' + mylar.DATA_DIR + '. Exiting....')
                return True
            else:
                logger.warn("Provided directory is blank, aborting")
                return False
    return False
