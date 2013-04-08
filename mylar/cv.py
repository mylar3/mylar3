#  This file is part of Mylar.
#
#  Mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mylar is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the 
#  implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public 
#  License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.


import sys
import os
import re
import logger
import string
import urllib
import lib.feedparser
import mylar
from bs4 import BeautifulSoup as Soup

def pulldetails(comicid,type,issueid=None,offset=1):
    import urllib2

    #import easy to use xml parser called minidom:
    from xml.dom.minidom import parseString

    comicapi='583939a3df0a25fc4e8b7a29934a13078002dc27'
    if type == 'comic':
        PULLURL='http://api.comicvine.com/volume/' + str(comicid) + '/?api_key=' + str(comicapi) + '&format=xml&field_list=name,count_of_issues,issues,start_year,site_detail_url,image,publisher,description,first_issue'
    elif type == 'issue':
        if mylar.CV_ONLY:
            cv_type = 'issues'
            searchset = 'filter=volume:' + str(comicid) + '&field_list=cover_date,description,id,image,issue_number,name,date_last_updated,store_date'
        else:
            cv_type = 'volume/' + str(comicid)
            searchset = 'name,count_of_issues,issues,start_year,site_detail_url,image,publisher,description'
        PULLURL = 'http://api.comicvine.com/' + str(cv_type) + '/?api_key=' + str(comicapi) + '&format=xml&' + str(searchset) + '&offset=' + str(offset)
    elif type == 'firstissue':
        #this is used ONLY for CV_ONLY
        PULLURL = 'http://api.comicvine.com/issues/?api_key=' + str(comicapi) + '&format=xml&filter=id:' + str(issueid) + '&field_list=cover_date'

    #download the file:
    file = urllib2.urlopen(PULLURL)
    #convert to string:
    data = file.read()
    #close file because we dont need it anymore:
    file.close()
    #parse the xml you downloaded
    dom = parseString(data)

    return dom


def getComic(comicid,type,issueid=None):
    if type == 'issue': 
        offset = 1
        issue = {}
        ndic = []
        issuechoice = []
        comicResults = []
        firstdate = '2099-00-00'
        #let's find out how many results we get from the query...
        searched = pulldetails(comicid,'issue',None,0)
        if searched is None: return False
        totalResults = searched.getElementsByTagName('number_of_total_results')[0].firstChild.wholeText
        logger.fdebug("there are " + str(totalResults) + " search results...")
        if not totalResults:
            return False
        countResults = 0
        while (countResults < int(totalResults)):
            logger.fdebug("querying " + str(countResults))
            if countResults > 0:
                #new api - have to change to page # instead of offset count
                offsetcount = countResults
                searched = pulldetails(comicid,'issue',None,offsetcount)
            issuechoice,tmpdate = GetIssuesInfo(comicid,searched)
            if tmpdate < firstdate:
                firstdate = tmpdate
            ndic = ndic + issuechoice
            #search results are limited to 100 and by pagination now...let's account for this.
            countResults = countResults + 100

        issue['issuechoice'] = ndic
        issue['firstdate'] = firstdate

        print ("issuechoice completed: " + str(issue))
        return issue

    elif type == 'comic':
        dom = pulldetails(comicid,'comic',None,1)
        return GetComicInfo(comicid,dom)
    elif type == 'firstissue': 
        dom = pulldetails(comicid,'firstissue',issueid,1)
        return GetFirstIssue(issueid,dom)

def GetComicInfo(comicid,dom):

    #comicvine isn't as up-to-date with issue counts..
    #so this can get really buggered, really fast.
    tracks = dom.getElementsByTagName('issue')
    try:
        cntit = dom.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
    except:
        cntit = len(tracks)
    trackcnt = len(tracks)
    logger.fdebug("number of issues I counted: " + str(trackcnt))
    logger.fdebug("number of issues CV says it has: " + str(cntit))
    # if the two don't match, use trackcnt as count_of_issues might be not upto-date for some reason
    if int(trackcnt) != int(cntit):
        cntit = trackcnt
        vari = "yes"
    else: vari = "no"
    logger.fdebug("vari is set to: " + str(vari))
    #if str(trackcnt) != str(int(cntit)+2):
    #    cntit = int(cntit) + 1
    comic = {}
    comicchoice = []
    cntit = int(cntit)
    #retrieve the first xml tag (<tag>data</tag>)
    #that the parser finds with name tagName:
    comic['ComicName'] = dom.getElementsByTagName('name')[trackcnt+1].firstChild.wholeText
    comic['ComicName'] = comic['ComicName'].rstrip() 
    try:
        comic['ComicYear'] = dom.getElementsByTagName('start_year')[0].firstChild.wholeText
    except:
        comic['ComicYear'] = '0000'
    comic['ComicURL'] = dom.getElementsByTagName('site_detail_url')[trackcnt].firstChild.wholeText
    #the description field actually holds the Volume# - so let's grab it
    try:
        comic['ComicDescription'] = dom.getElementsByTagName('description')[0].firstChild.wholeText
    except:
        comic['ComicDescription'] = 'None'
    #extract the first 60 characters
    comicDes = comic['ComicDescription'][:60]
    if 'volume' in comicDes.lower():
        #found volume - let's grab it.
        v_find = comicDes.lower().find('volume')
        #arbitrarily grab the next 10 chars (6 for volume + 1 for space + 3 for the actual vol #)
        #increased to 10 to allow for text numbering (+5 max)
        vfind = comicDes[v_find:v_find+15]
        volconv = ''
        basenums = {'zero':'0','one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8'}
        for nums in basenums:
            if nums in vfind.lower():
                sconv = basenums[nums]
                volconv = re.sub(nums, sconv, vfind.lower())
                break        
        if volconv != '':
            vfind = volconv
        vf = re.findall('[^<>]+', vfind)
        comic['ComicVersion'] = re.sub("[^0-9]", "", vf[0])
        logger.info("Volume information found! Adding to series record : volume " + comic['ComicVersion'])
    else:
        comic['ComicVersion'] = "noversion"

    if vari == "yes": 
        comic['ComicIssues'] = str(cntit)
    else:
        comic['ComicIssues'] = dom.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
    comic['ComicImage'] = dom.getElementsByTagName('super_url')[0].firstChild.wholeText
    comic['ComicPublisher'] = dom.getElementsByTagName('name')[trackcnt+2].firstChild.wholeText

    comic['FirstIssueID'] = dom.getElementsByTagName('id')[0].firstChild.wholeText

#    print ("fistIss:" + str(comic['FirstIssueID']))
#    comicchoice.append({
#        'ComicName':              comic['ComicName'],
#        'ComicYear':              comic['ComicYear'],
#        'Comicid':                comicid,
#        'ComicURL':               comic['ComicURL'],
#        'ComicIssues':            comic['ComicIssues'],
#        'ComicImage':             comic['ComicImage'],
#        'ComicVolume':            ParseVol,
#        'ComicPublisher':         comic['ComicPublisher']
#        })

#    comic['comicchoice'] = comicchoice
    return comic

def GetIssuesInfo(comicid,dom):
    subtracks = dom.getElementsByTagName('issue')
    if not mylar.CV_ONLY:
        cntiss = dom.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
        logger.fdebug("issues I've counted: " + str(len(subtracks)))
        logger.fdebug("issues CV says it has: " + str(int(cntiss)))

        if int(len(subtracks)) != int(cntiss):
            logger.fdebug("CV's count is wrong, I counted different...going with my count for physicals" + str(len(subtracks)))
            cntiss = len(subtracks) # assume count of issues is wrong, go with ACTUAL physical api count
        cntiss = int(cntiss)
        n = cntiss-1
    else:
        n = int(len(subtracks))
    tempissue = {}
    issuech = []
    firstdate = '2099-00-00'
    for subtrack in subtracks:
        if not mylar.CV_ONLY:
            if (dom.getElementsByTagName('name')[n].firstChild) is not None:
                issue['Issue_Name'] = dom.getElementsByTagName('name')[n].firstChild.wholeText
            else:
                issue['Issue_Name'] = 'None'

            issue['Issue_ID'] = dom.getElementsByTagName('id')[n].firstChild.wholeText
            issue['Issue_Number'] = dom.getElementsByTagName('issue_number')[n].firstChild.wholeText
            
            issuech.append({
                'Issue_ID':                issue['Issue_ID'],
                'Issue_Number':            issue['Issue_Number'],
                'Issue_Name':              issue['Issue_Name']
                })
        else:
            try:
                tempissue['Issue_Name'] = subtrack.getElementsByTagName('name')[0].firstChild.wholeText
            except:
                tempissue['Issue_Name'] = 'None'
            tempissue['Issue_ID'] = subtrack.getElementsByTagName('id')[0].firstChild.wholeText
            try:
                tempissue['CoverDate'] = subtrack.getElementsByTagName('cover_date')[0].firstChild.wholeText
            except:
                tempissue['CoverDate'] = '0000-00-00'
            tempissue['Issue_Number'] = subtrack.getElementsByTagName('issue_number')[0].firstChild.wholeText
            issuech.append({
                'Issue_ID':                tempissue['Issue_ID'],
                'Issue_Number':            tempissue['Issue_Number'],
                'Issue_Date':              tempissue['CoverDate'],
                'Issue_Name':              tempissue['Issue_Name']
                })

            if tempissue['CoverDate'] < firstdate and tempissue['CoverDate'] != '0000-00-00':
                firstdate = tempissue['CoverDate']
        n-=1

    #issue['firstdate'] = firstdate
    return issuech, firstdate

def GetFirstIssue(issueid,dom):
    #if the Series Year doesn't exist, get the first issue and take the date from that
    try:
        first_year = dom.getElementsByTagName('cover_date')[0].firstChild.wholeText
    except:
        first_year = '0000'
        return first_year

    the_year = first_year[:4]
    the_month = first_year[5:7]
    the_date = the_year + '-' + the_month

    return the_year
