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

import re
import time
import threading
import platform
import urllib, urllib2
from xml.dom.minidom import parseString, Element
import requests

import mylar
from mylar import logger, db, cv
from mylar.helpers import multikeysort, replace_all, cleanName, listLibrary, listStoryArcs
import httplib

mb_lock = threading.Lock()

def patch_http_response_read(func):
    def inner(*args):
        try:
            return func(*args)
        except httplib.IncompleteRead, e:
            return e.partial

    return inner
httplib.HTTPResponse.read = patch_http_response_read(httplib.HTTPResponse.read)

if platform.python_version() == '2.7.6':
    httplib.HTTPConnection._http_vsn = 10
    httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'

def pullsearch(comicapi, comicquery, offset, type):

    cnt = 1
    for x in comicquery:
       if cnt == 1:
           filterline = '%s' % x
       else:
           filterline+= ',name:%s' % x
       cnt+=1

    PULLURL = mylar.CVURL + str(type) + 's?api_key=' + str(comicapi) + '&filter=name:' + filterline + '&field_list=id,name,start_year,site_detail_url,count_of_issues,image,publisher,deck,description,first_issue,last_issue&format=xml&offset=' + str(offset) # 2012/22/02 - CVAPI flipped back to offset instead of page

    #all these imports are standard on most modern python implementations
    #logger.info('MB.PULLURL:' + PULLURL)

    #new CV API restriction - one api request / second.
    if mylar.CONFIG.CVAPI_RATE is None or mylar.CONFIG.CVAPI_RATE < 2:
        time.sleep(2)
    else:
        time.sleep(mylar.CONFIG.CVAPI_RATE)

    #download the file:
    payload = None

    try:
        r = requests.get(PULLURL, params=payload, verify=mylar.CONFIG.CV_VERIFY, headers=mylar.CV_HEADERS)
    except Exception, e:
        logger.warn('Error fetching data from ComicVine: %s' % (e))
        return

    try:
        dom = parseString(r.content) #(data)
    except ExpatError:
         if u'<title>Abnormal Traffic Detected' in r.content:
            logger.error("ComicVine has banned this server's IP address because it exceeded the API rate limit.")
        else:
            logger.warn('[WARNING] ComicVine is not responding correctly at the moment. This is usually due to some problems on their end. If you re-try things again in a few moments, it might work properly.')
        return

    return dom

def findComic(name, mode, issue, limityear=None, type=None):

    #with mb_lock:
    comicResults = None
    comicLibrary = listLibrary()
    comiclist = []
    arcinfolist = []

    commons = ['and', 'the', '&', '-']
    for x in commons:
        cnt = 0
        for m in re.finditer(x, name.lower()):
            cnt +=1
            tehstart = m.start()
            tehend = m.end()
            if any([x == 'the', x == 'and']):
                if len(name) == tehend:
                    tehend =-1
                if not all([tehstart == 0, name[tehend] == ' ']) or not all([tehstart != 0, name[tehstart-1] == ' ', name[tehend] == ' ']):
                    continue
            else:
                name = name.replace(x, ' ', cnt)

    originalname = name
    if '+' in name:
       name = re.sub('\+', 'PLUS', name)

    pattern = re.compile(ur'\w+', re.UNICODE)
    name = pattern.findall(name)

    if '+' in originalname:
        y = []
        for x in name:
            y.append(re.sub("PLUS", "%2B", x))
        name = y

    if limityear is None: limityear = 'None'

    comicquery = name

    if mylar.CONFIG.COMICVINE_API == 'None' or mylar.CONFIG.COMICVINE_API is None:
        logger.warn('You have not specified your own ComicVine API key - this is a requirement. Get your own @ http://api.comicvine.com.')
        return
    else:
        comicapi = mylar.CONFIG.COMICVINE_API

    if type is None:
        type = 'volume'

    #let's find out how many results we get from the query...
    searched = pullsearch(comicapi, comicquery, 0, type)
    if searched is None:
        return False
    totalResults = searched.getElementsByTagName('number_of_total_results')[0].firstChild.wholeText
    logger.fdebug("there are " + str(totalResults) + " search results...")
    if not totalResults:
        return False
    if int(totalResults) > 1000:
        logger.warn('Search returned more than 1000 hits [' + str(totalResults) + ']. Only displaying first 1000 results - use more specifics or the exact ComicID if required.')
        totalResults = 1000
    countResults = 0
    while (countResults < int(totalResults)):
        #logger.fdebug("querying " + str(countResults))
        if countResults > 0:
            offsetcount = countResults

            searched = pullsearch(comicapi, comicquery, offsetcount, type)
        comicResults = searched.getElementsByTagName(type)
        body = ''
        n = 0
        if not comicResults:
           break
        for result in comicResults:
                #retrieve the first xml tag (<tag>data</tag>)
                #that the parser finds with name tagName:
                arclist = []
                if type == 'story_arc':
                    #call cv.py here to find out issue count in story arc
                    try:
                        logger.fdebug('story_arc ascension')
                        names = len(result.getElementsByTagName('name'))
                        n = 0
                        logger.fdebug('length: ' + str(names))
                        xmlpub = None #set this incase the publisher field isn't populated in the xml
                        while (n < names):
                            logger.fdebug(result.getElementsByTagName('name')[n].parentNode.nodeName)
                            if result.getElementsByTagName('name')[n].parentNode.nodeName == 'story_arc':
                                logger.fdebug('yes')
                                try:
                                    xmlTag = result.getElementsByTagName('name')[n].firstChild.wholeText
                                    xmlTag = xmlTag.rstrip()
                                    logger.fdebug('name: ' + xmlTag)
                                except:
                                    logger.error('There was a problem retrieving the given data from ComicVine. Ensure that www.comicvine.com is accessible.')
                                    return

                            elif result.getElementsByTagName('name')[n].parentNode.nodeName == 'publisher':
                                logger.fdebug('publisher check.')
                                xmlpub = result.getElementsByTagName('name')[n].firstChild.wholeText

                            n+=1
                    except:
                        logger.warn('error retrieving story arc search results.')
                        return

                    siteurl = len(result.getElementsByTagName('site_detail_url'))
                    s = 0
                    logger.fdebug('length: ' + str(names))
                    xmlurl = None
                    while (s < siteurl):
                        logger.fdebug(result.getElementsByTagName('site_detail_url')[s].parentNode.nodeName)
                        if result.getElementsByTagName('site_detail_url')[s].parentNode.nodeName == 'story_arc':
                            try:
                                xmlurl = result.getElementsByTagName('site_detail_url')[s].firstChild.wholeText
                            except:
                                logger.error('There was a problem retrieving the given data from ComicVine. Ensure that www.comicvine.com is accessible.')
                                return
                        s+=1

                    xmlid = result.getElementsByTagName('id')[0].firstChild.wholeText

                    if xmlid is not None:
                        arcinfolist = storyarcinfo(xmlid)
                        logger.info('[IMAGE] : ' + arcinfolist['comicimage'])
                        comiclist.append({
                                'name':                 xmlTag,
                                'comicyear':            arcinfolist['comicyear'],
                                'comicid':              xmlid,
                                'cvarcid':              xmlid,
                                'url':                  xmlurl,
                                'issues':               arcinfolist['issues'],
                                'comicimage':           arcinfolist['comicimage'],
                                'publisher':            xmlpub,
                                'description':          arcinfolist['description'],
                                'deck':                 arcinfolist['deck'],
                                'arclist':              arcinfolist['arclist'],
                                'haveit':               arcinfolist['haveit']
                                })
                    else:
                        comiclist.append({
                                'name':                 xmlTag,
                                'comicyear':            arcyear,
                                'comicid':              xmlid,
                                'url':                  xmlurl,
                                'issues':               issuecount,
                                'comicimage':           xmlimage,
                                'publisher':            xmlpub,
                                'description':          xmldesc,
                                'deck':                 xmldeck,
                                'arclist':              arclist,
                                'haveit':               haveit
                                })

                        logger.fdebug('IssueID\'s that are a part of ' + xmlTag + ' : ' + str(arclist))
                else:
                    xmlcnt = result.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
                    #here we can determine what called us, and either start gathering all issues or just limited ones.
                    if issue is not None and str(issue).isdigit():
                        #this gets buggered up with NEW/ONGOING series because the db hasn't been updated
                        #to reflect the proper count. Drop it by 1 to make sure.
                        limiter = int(issue) - 1
                    else: limiter = 0
                    #get the first issue # (for auto-magick calcs)

                    iss_len = len(result.getElementsByTagName('name'))
                    i=0
                    xmlfirst = '1'
                    xmllast = None
                    try:
                        while (i < iss_len):
                            if result.getElementsByTagName('name')[i].parentNode.nodeName == 'first_issue':
                                xmlfirst = result.getElementsByTagName('issue_number')[i].firstChild.wholeText
                                if '\xbd' in xmlfirst:
                                    xmlfirst = '1'  #if the first issue is 1/2, just assume 1 for logistics
                            elif result.getElementsByTagName('name')[i].parentNode.nodeName == 'last_issue':
                                xmllast = result.getElementsByTagName('issue_number')[i].firstChild.wholeText
                            if all([xmllast is not None, xmlfirst is not None]):
                                break
                            i+=1
                    except:
                        xmlfirst = '1'

                    if all([xmlfirst == xmllast, xmlfirst.isdigit(), xmlcnt == '0']):
                        xmlcnt = '1'

                    #logger.info('There are : ' + str(xmlcnt) + ' issues in this series.')
                    #logger.info('The first issue started at # ' + str(xmlfirst))

                    cnt_numerical = int(xmlcnt) + int(xmlfirst) # (of issues + start of first issue = numerical range)
                    #logger.info('The maximum issue number should be roughly # ' + str(cnt_numerical))
                    #logger.info('The limiter (issue max that we know of) is # ' + str(limiter))
                    if cnt_numerical >= limiter:
                        cnl = len (result.getElementsByTagName('name'))
                        cl = 0
                        xmlTag = 'None'
                        xmlimage = "cache/blankcover.jpg"
                        xml_lastissueid = 'None'
                        while (cl < cnl):
                            if result.getElementsByTagName('name')[cl].parentNode.nodeName == 'volume':
                                xmlTag = result.getElementsByTagName('name')[cl].firstChild.wholeText
                                #break

                            if result.getElementsByTagName('name')[cl].parentNode.nodeName == 'image':
                                xmlimage = result.getElementsByTagName('super_url')[0].firstChild.wholeText

                            if result.getElementsByTagName('name')[cl].parentNode.nodeName == 'last_issue':
                                xml_lastissueid = result.getElementsByTagName('id')[cl].firstChild.wholeText
                            cl+=1

                        if (result.getElementsByTagName('start_year')[0].firstChild) is not None:
                            xmlYr = result.getElementsByTagName('start_year')[0].firstChild.wholeText
                        else: xmlYr = "0000"

                        yearRange = []
                        tmpYr = re.sub('\?', '', xmlYr)

                        if tmpYr.isdigit():

                            yearRange.append(tmpYr)
                            tmpyearRange = int(xmlcnt) / 12
                            if float(tmpyearRange): tmpyearRange +1
                            possible_years = int(tmpYr) + tmpyearRange

                            for i in range(int(tmpYr), int(possible_years),1):
                                if not any(int(x) == int(i) for x in yearRange):
                                    yearRange.append(str(i))

                        logger.fdebug('[RESULT][' + str(limityear) + '] ComicName:' + xmlTag + ' -- ' + str(xmlYr) + ' [Series years: ' + str(yearRange) + ']')
                        if tmpYr != xmlYr:
                            xmlYr = tmpYr

                        if any(map(lambda v: v in limityear, yearRange)) or limityear == 'None':
                            xmlurl = result.getElementsByTagName('site_detail_url')[0].firstChild.wholeText
                            idl = len (result.getElementsByTagName('id'))
                            idt = 0
                            xmlid = None
                            while (idt < idl):
                                if result.getElementsByTagName('id')[idt].parentNode.nodeName == 'volume':
                                    xmlid = result.getElementsByTagName('id')[idt].firstChild.wholeText
                                    break
                                idt+=1

                            if xmlid is None:
                                logger.error('Unable to figure out the comicid - skipping this : ' + str(xmlurl))
                                continue

                            publishers = result.getElementsByTagName('publisher')
                            if len(publishers) > 0:
                                pubnames = publishers[0].getElementsByTagName('name')
                                if len(pubnames) >0:
                                    xmlpub = pubnames[0].firstChild.wholeText
                                else:
                                    xmlpub = "Unknown"
                            else:
                                xmlpub = "Unknown"

                            #ignore specific publishers on a global scale here.
                            if mylar.CONFIG.BLACKLISTED_PUBLISHERS is not None and any([x for x in mylar.CONFIG.BLACKLISTED_PUBLISHERS if x.lower() == xmlpub.lower()]):
                                logger.fdebug('Blacklisted publisher [' + xmlpub + ']. Ignoring this result.')
                                continue

                            try:
                                xmldesc = result.getElementsByTagName('description')[0].firstChild.wholeText
                            except:
                                xmldesc = "None"

                            #this is needed to display brief synopsis for each series on search results page.
                            try:
                                xmldeck = result.getElementsByTagName('deck')[0].firstChild.wholeText
                            except:
                                xmldeck = "None"

                            xmltype = None
                            if xmldeck != 'None':
                                if any(['print' in xmldeck.lower(), 'digital' in xmldeck.lower(), 'paperback' in xmldeck.lower(), 'hardcover' in xmldeck.lower()]):
                                    if 'print' in xmldeck.lower():
                                        xmltype = 'Print'
                                    elif 'digital' in xmldeck.lower():
                                        xmltype = 'Digital'
                                    elif 'paperback' in xmldeck.lower():
                                        xmltype = 'TPB'
                                    elif 'hardcover' in xmldeck.lower():
                                        xmltype = 'HC'
                            if xmldesc != 'None' and xmltype is None:
                                if 'print' in xmldesc[:60].lower() and 'print edition can be found' not in xmldesc.lower():
                                    xmltype = 'Print'
                                elif 'digital' in xmldesc[:60].lower() and 'digital edition can be found' not in xmldesc.lower():
                                    xmltype = 'Digital'
                                elif 'paperback' in xmldesc[:60].lower() and 'paperback can be found' not in xmldesc.lower():
                                    xmltype = 'TPB'
                                elif 'hardcover' in xmldesc[:60].lower() and 'hardcover can be found' not in xmldesc.lower():
                                    xmltype = 'HC'
                                else:
                                    xmltype = 'Print'

                            if xmlid in comicLibrary:
                                haveit = comicLibrary[xmlid]
                            else:
                                haveit = "No"
                            comiclist.append({
                                    'name':                 xmlTag,
                                    'comicyear':            xmlYr,
                                    'comicid':              xmlid,
                                    'url':                  xmlurl,
                                    'issues':               xmlcnt,
                                    'comicimage':           xmlimage,
                                    'publisher':            xmlpub,
                                    'description':          xmldesc,
                                    'deck':                 xmldeck,
                                    'type':                 xmltype,
                                    'haveit':               haveit,
                                    'lastissueid':          xml_lastissueid,
                                    'seriesrange':          yearRange  # returning additional information about series run polled from CV
                                    })
                            #logger.fdebug('year: %s - constraint met: %s [%s] --- 4050-%s' % (xmlYr,xmlTag,xmlYr,xmlid))
                        else:
                            #logger.fdebug('year: ' + str(xmlYr) + ' -  contraint not met. Has to be within ' + str(limityear))
                            pass
                n+=1
        #search results are limited to 100 and by pagination now...let's account for this.
        countResults = countResults + 100

    return comiclist

def storyarcinfo(xmlid):

    comicLibrary = listStoryArcs()

    arcinfo = {}

    if mylar.CONFIG.COMICVINE_API == 'None' or mylar.CONFIG.COMICVINE_API is None:
        logger.warn('You have not specified your own ComicVine API key - this is a requirement. Get your own @ http://api.comicvine.com.')
        return
    else:
        comicapi = mylar.CONFIG.COMICVINE_API

    #respawn to the exact id for the story arc and count the # of issues present.
    ARCPULL_URL = mylar.CVURL + 'story_arc/4045-' + str(xmlid) + '/?api_key=' + str(comicapi) + '&field_list=issues,publisher,name,first_appeared_in_issue,deck,image&format=xml&offset=0'
    #logger.fdebug('arcpull_url:' + str(ARCPULL_URL))

    #new CV API restriction - one api request / second.
    if mylar.CONFIG.CVAPI_RATE is None or mylar.CONFIG.CVAPI_RATE < 2:
        time.sleep(2)
    else:
        time.sleep(mylar.CONFIG.CVAPI_RATE)

    #download the file:
    payload = None

    try:
        r = requests.get(ARCPULL_URL, params=payload, verify=mylar.CONFIG.CV_VERIFY, headers=mylar.CV_HEADERS)
    except Exception, e:
        logger.warn('Error fetching data from ComicVine: %s' % (e))
        return
#    try:
#        file = urllib2.urlopen(ARCPULL_URL)
#    except urllib2.HTTPError, err:
#        logger.error('err : ' + str(err))
#        logger.error('There was a major problem retrieving data from ComicVine - on their end.')
#        return
#    arcdata = file.read()
#    file.close()
    try:
        arcdom = parseString(r.content) #(arcdata)
    except ExpatError:
        if u'<title>Abnormal Traffic Detected' in r.content:
            logger.error("ComicVine has banned this server's IP address because it exceeded the API rate limit.")
        else:
            logger.warn('While parsing data from ComicVine, got exception: %s for data: %s' % (str(e), r.content))
        return

    try:
        logger.fdebug('story_arc ascension')
        issuecount = len( arcdom.getElementsByTagName('issue') )
        issuedom = arcdom.getElementsByTagName('issue')
        isc = 0
        arclist = ''
        ordernum = 1
        for isd in issuedom:
            zeline = isd.getElementsByTagName('id')
            isdlen = len( zeline )
            isb = 0
            while ( isb < isdlen):
                if isc == 0:
                    arclist = str(zeline[isb].firstChild.wholeText).strip() + ',' + str(ordernum)
                else:
                    arclist += '|' + str(zeline[isb].firstChild.wholeText).strip() + ',' + str(ordernum)
                ordernum+=1 
                isb+=1

            isc+=1

    except:
        logger.fdebug('unable to retrive issue count - nullifying value.')
        issuecount = 0

    try:
        firstid = None
        arcyear = None
        fid = len ( arcdom.getElementsByTagName('id') )
        fi = 0
        while (fi < fid):
            if arcdom.getElementsByTagName('id')[fi].parentNode.nodeName == 'first_appeared_in_issue':
                if not arcdom.getElementsByTagName('id')[fi].firstChild.wholeText == xmlid:
                    logger.fdebug('hit it.')
                    firstid = arcdom.getElementsByTagName('id')[fi].firstChild.wholeText
                    break # - dont' break out here as we want to gather ALL the issue ID's since it's here
            fi+=1
        logger.fdebug('firstid: ' + str(firstid))
        if firstid is not None:
            firstdom = cv.pulldetails(comicid=None, type='firstissue', issueid=firstid)
            logger.fdebug('success')
            arcyear = cv.Getissue(firstid,firstdom,'firstissue')
    except:
        logger.fdebug('Unable to retrieve first issue details. Not caclulating at this time.')

    try:
        xmlimage = arcdom.getElementsByTagName('super_url')[0].firstChild.wholeText
    except:
        xmlimage = "cache/blankcover.jpg"

    try:
        xmldesc = arcdom.getElementsByTagName('desc')[0].firstChild.wholeText
    except:
        xmldesc = "None"

    try:
        xmlpub = arcdom.getElementsByTagName('publisher')[0].firstChild.wholeText
    except:
        xmlpub = "None"

    try:
        xmldeck = arcdom.getElementsByTagName('deck')[0].firstChild.wholeText
    except:
        xmldeck = "None"

    if xmlid in comicLibrary:
        haveit = comicLibrary[xmlid]
    else:
        haveit = "No"

    arcinfo = {
            #'name':                 xmlTag,    #theese four are passed into it only when it's a new add
            #'url':                  xmlurl,    #needs to be modified for refreshing to work completely.
            #'publisher':            xmlpub,
            'comicyear':            arcyear,
            'comicid':              xmlid,
            'issues':               issuecount,
            'comicimage':           xmlimage,
            'description':          xmldesc,
            'deck':                 xmldeck,
            'arclist':              arclist,
            'haveit':               haveit,
            'publisher':            xmlpub
            }

    return arcinfo

