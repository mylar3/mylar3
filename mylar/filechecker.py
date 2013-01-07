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

def file2comicmatch(watchmatch):
    #print ("match: " + str(watchmatch))
    pass

def listFiles(dir,watchcomic,AlternateSearch=None):
    # use AlternateSearch to check for filenames that follow that naming pattern
    # ie. Star Trek TNG Doctor Who Assimilation won't get hits as the 
    # checker looks for Star Trek TNG Doctor Who Assimilation2 (according to CV)

    logger.fdebug("comic: " + watchcomic)
    basedir = dir
    logger.fdebug("Looking in: " + dir)
    watchmatch = {}
    comiclist = []
    comiccnt = 0
    for item in os.listdir(basedir):
        #print item
        #subname = os.path.join(basedir, item)
        subname = item
        #print subname
        subname = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]',' ', str(subname))
        modwatchcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]', ' ', str(watchcomic))
        modwatchcomic = re.sub('\s+', ' ', str(modwatchcomic)).strip()
        subname = re.sub('\s+', ' ', str(subname)).strip()
        if AlternateSearch is not None:
            altsearchcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]', ' ', str(AlternateSearch))
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
            comiclist.append({
                 'ComicFilename':           item,
                 'ComicLocation':           comicpath,
                 'ComicSize':               comicsize
                 })
            watchmatch['comiclist'] = comiclist
        else:
            pass
            #print ("directory found - ignoring")
    
    logger.fdebug("you have a total of " + str(comiccnt) + " " + str(watchcomic) + " comics")
    watchmatch['comiccount'] = comiccnt
    return watchmatch


