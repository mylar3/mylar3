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
import urllib, urllib2
from xml.dom.minidom import parseString, Element

import mylar
from mylar import logger, db, cv
from mylar.helpers import multikeysort, replace_all, cleanName

mb_lock = threading.Lock()


def pullsearch(comicapi,comicquery,offset,explicit):
    u_comicquery = urllib.quote(comicquery.encode('utf-8').strip())
    u_comicquery = u_comicquery.replace(" ", "%20")

    if explicit == 'all' or explicit == 'loose':
        PULLURL = mylar.CVURL + 'search?api_key=' + str(comicapi) + '&resources=volume&query=' + u_comicquery + '&field_list=id,name,start_year,site_detail_url,count_of_issues,image,publisher,description&format=xml&page=' + str(offset)

    else:
        # 02/22/2014 use the volume filter label to get the right results.
        PULLURL = mylar.CVURL + 'volumes?api_key=' + str(comicapi) + '&filter=name:' + u_comicquery + '&field_list=id,name,start_year,site_detail_url,count_of_issues,image,publisher,description&format=xml&offset=' + str(offset) # 2012/22/02 - CVAPI flipped back to offset instead of page

    #all these imports are standard on most modern python implementations
    #download the file:
    try:
        file = urllib2.urlopen(PULLURL)
    except urllib2.HTTPError, err:
        logger.error('err : ' + str(err))
        logger.error("There was a major problem retrieving data from ComicVine - on their end. You'll have to try again later most likely.")
        return        
    #convert to string:
    data = file.read()
    #close file because we dont need it anymore:
    file.close()
    #parse the xml you downloaded
    dom = parseString(data)
    return dom

def findComic(name, mode, issue, limityear=None, explicit=None):

    #with mb_lock:       
    comiclist = []
    comicResults = None
        
    chars = set('!?*')
    if any((c in chars) for c in name):
        name = '"'+name+'"'

    #print ("limityear: " + str(limityear))            
    if limityear is None: limityear = 'None'
    
    comicquery = name
    #comicquery=name.replace(" ", "%20")

    if explicit is None:
        #logger.fdebug('explicit is None. Setting to Default mode of ALL search words.')
        comicquery=name.replace(" ", " AND ")
        explicit = 'all'

    #OR
    if explicit == 'loose':
        logger.fdebug('Changing to loose mode - this will match ANY of the search words')
        comicquery = name.replace(" ", " OR ")
    elif explicit == 'explicit':
        logger.fdebug('Changing to explicit mode - this will match explicitly on the EXACT words')
        comicquery=name.replace(" ", " AND ")
    else:
        logger.fdebug('Default search mode - this will match on ALL search words')
        comicquery = name.replace(" ", " AND ")
        explicit = 'all'


    if mylar.COMICVINE_API == 'None' or mylar.COMICVINE_API is None or mylar.COMICVINE_API == mylar.DEFAULT_CVAPI:
        logger.warn('You have not specified your own ComicVine API key - alot of things will be limited. Get your own @ http://api.comicvine.com.')
        comicapi = mylar.DEFAULT_CVAPI
    else:
        comicapi = mylar.COMICVINE_API

    #let's find out how many results we get from the query...    
    searched = pullsearch(comicapi,comicquery,0,explicit)
    if searched is None: return False
    totalResults = searched.getElementsByTagName('number_of_total_results')[0].firstChild.wholeText
    logger.fdebug("there are " + str(totalResults) + " search results...")
    if not totalResults:
        return False
    countResults = 0
    while (countResults < int(totalResults)):
        #logger.fdebug("querying " + str(countResults))
        if countResults > 0:
            #2012/22/02 - CV API flipped back to offset usage instead of page 
            if explicit == 'all' or explicit == 'loose':
                #all / loose uses page for offset
                offsetcount = (countResults/100) + 1
            else:
                #explicit uses offset
                offsetcount = countResults
            
            searched = pullsearch(comicapi,comicquery,offsetcount,explicit)
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
                if issue is not None and str(issue).isdigit():
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
                            else:
                                xmlpub = "Unknown"
                        else:
                            xmlpub = "Unknown"
                        if (result.getElementsByTagName('name')[0].childNodes[0].nodeValue) is None:
                            xmlimage = result.getElementsByTagName('super_url')[0].firstChild.wholeText
                        else:
                            xmlimage = "cache/blankcover.jpg"            

                        try:
                            xmldesc = result.getElementsByTagName('description')[0].firstChild.wholeText
                        except:
                            xmldesc = "None"
                        comiclist.append({
                                'name':             xmlTag,
                                'comicyear':             xmlYr,
                                'comicid':                xmlid,
                                'url':                 xmlurl,
                                'issues':            xmlcnt,
                                'comicimage':          xmlimage,
                                'publisher':            xmlpub,
                                'description':          xmldesc
                                })
                    else:
                        logger.fdebug('year: ' + str(xmlYr) + ' -  contraint not met. Has to be within ' + str(limityear)) 
                n+=1    
        #search results are limited to 100 and by pagination now...let's account for this.
        countResults = countResults + 100
   
    return comiclist, explicit
