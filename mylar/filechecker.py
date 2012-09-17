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

def file2comicmatch(watchmatch):
    #print ("match: " + str(watchmatch))
    pass

def listFiles(dir,watchcomic):
    #print("dir:" + dir)
    #print("comic: " + watchcomic)
    if ':' in watchcomic:
        watchcomic = watchcomic.replace(':','')
    basedir = dir
    #print "Files in ", dir, ": "
    watchmatch = {}
    comiclist = []
    comiccnt = 0
    for item in os.listdir(basedir):
        #print item
        subname = os.path.join(basedir, item)
        #print subname
        if '_' in subname:
            subname = subname.replace('_', ' ')
        if watchcomic.lower() in subname.lower():
            if 'annual' in subname.lower():
                print ("it's an annual - unsure how to proceed")
                break
            comicpath = os.path.join(basedir, item)
            #print ( watchcomic + " - watchlist match on : " + comicpath)
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
    
    #print ("you have a total of " + str(comiccnt) + " comics")
    #print ("watchdata: " + str(watchmatch))
    watchmatch['comiccount'] = comiccnt
    return watchmatch


