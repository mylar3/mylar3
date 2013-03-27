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

from __future__ import with_statement

import time
import threading
import urllib2
from xml.dom.minidom import parseString, Element

import mylar
from mylar import logger, db, cv
from mylar.helpers import multikeysort, replace_all, cleanName

mb_lock = threading.Lock()


def pullsearch(comicapi,comicquery,offset):
    PULLURL='http://api.comicvine.com/search?api_key=' + str(comicapi) + '&resources=volume&query=' + str(comicquery) + '&field_list=id,name,start_year,site_detail_url,count_of_issues,image,publisher&format=xml&page=' + str(offset)

    #all these imports are standard on most modern python implementations
    #download the file:
    try:
        file = urllib2.urlopen(PULLURL)
    except urllib2.HTTPError, err:
        logger.error("There was a major problem retrieving data from ComicVine - on their end. You'll have to try again later most likely.")
        return        
    #convert to string:
    data = file.read()
    #close file because we dont need it anymore:
    file.close()
    #parse the xml you downloaded
    dom = parseString(data)
    return dom

def findComic(name, mode, issue, limityear=None):

    #with mb_lock:       
    comiclist = []
    comicResults = None
        
    chars = set('!?*')
    if any((c in chars) for c in name):
        name = '"'+name+'"'

    #print ("limityear: " + str(limityear))            
    if limityear is None: limityear = 'None'

    comicquery=name.replace(" ", "%20")
    comicapi='583939a3df0a25fc4e8b7a29934a13078002dc27'
    offset = 1

    #let's find out how many results we get from the query...    
    searched = pullsearch(comicapi,comicquery,1)
    if searched is None: return False
    totalResults = searched.getElementsByTagName('number_of_total_results')[0].firstChild.wholeText
    #print ("there are " + str(totalResults) + " search results...")
    if not totalResults:
        return False
    countResults = 0
    while (countResults < totalResults):
        #print ("querying " + str(countResults))
        if countResults > 0:
            #new api - have to change to page # instead of offset count
            offsetcount = (countResults/100) + 1
            searched = pullsearch(comicapi,comicquery,offsetcount)
        comicResults = searched.getElementsByTagName('volume')
        body = ''
        n = 0        
        if not comicResults:
           break        
        for result in comicResults:
                #retrieve the first xml tag (<tag>data</tag>)
                #that the parser finds with name tagName:
                xmlcnt = result.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
                #here we can determine what called us, and either start gathering all issues or just limited ones.
                #print ("n: " + str(n) + "--xmcnt" + str(xmlcnt))
                if issue is not None:
                    #this gets buggered up with NEW/ONGOING series because the db hasn't been updated
                    #to reflect the proper count. Drop it by 1 to make sure.
                    limiter = int(issue) - 1
                else: limiter = 0
                if int(xmlcnt) >= limiter:
                    
                    xmlTag = result.getElementsByTagName('name')[0].firstChild.wholeText
                    if (result.getElementsByTagName('start_year')[0].firstChild) is not None:
                        xmlYr = result.getElementsByTagName('start_year')[0].firstChild.wholeText
                    else: xmlYr = "0000"
                    if xmlYr in limityear or limityear == 'None':
                        xmlurl = result.getElementsByTagName('site_detail_url')[0].firstChild.wholeText
                        xmlid = result.getElementsByTagName('id')[0].firstChild.wholeText
                        publishers = result.getElementsByTagName('publisher')
                        if len(publishers) > 0:
                            pubnames = publishers[0].getElementsByTagName('name')
                            if len(pubnames) >0:
                                xmlpub = pubnames[0].firstChild.wholeText
                        if (result.getElementsByTagName('name')[0].childNodes[0].nodeValue) is None:
                            xmlimage = result.getElementsByTagName('super_url')[0].firstChild.wholeText
                        else:
                            xmlimage = "cache/blankcover.jpg"            
                        comiclist.append({
                                'name':             xmlTag,
                                'comicyear':             xmlYr,
                                'comicid':                xmlid,
                                'url':                 xmlurl,
                                'issues':            xmlcnt,
                                'comicimage':          xmlimage,
                                'publisher':            xmlpub
                                })
                    else:
                        print ("year: " + str(xmlYr) + " -  contraint not met. Has to be within " + str(limityear)) 
                n+=1    
        #search results are limited to 100 and by pagination now...let's account for this.
        countResults = countResults + 100
   
    return comiclist
        
