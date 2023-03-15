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
import time
import pytz
from mylar import logger, helpers
import string
import feedparser
import mylar
import platform
from bs4 import BeautifulSoup as Soup
from xml.parsers.expat import ExpatError
import http.client
import requests
import datetime
from operator import itemgetter

def pulldetails(comicid, rtype, issueid=None, offset=1, arclist=None, comicidlist=None, dateinfo=None):
    #import easy to use xml parser called minidom:
    from xml.dom.minidom import parseString

    if mylar.CONFIG.COMICVINE_API == 'None' or mylar.CONFIG.COMICVINE_API is None:
        logger.warn('You have not specified your own ComicVine API key - it\'s a requirement. Get your own @ http://api.comicvine.com.')
        return
    else:
        comicapi = mylar.CONFIG.COMICVINE_API

    if rtype == 'comic':
        if not comicid.startswith('4050-'): comicid = '4050-' + comicid
        PULLURL = mylar.CVURL + 'volume/' + str(comicid) + '/?api_key=' + str(comicapi) + '&format=xml&field_list=name,count_of_issues,issues,start_year,site_detail_url,image,publisher,description,first_issue,deck,aliases'
    elif rtype == 'issue':
        if mylar.CONFIG.CV_ONLY:
            cv_rtype = 'issues'
            if arclist is None:
                searchset = 'filter=volume:' + str(comicid) + '&field_list=cover_date,description,id,image,issue_number,name,date_last_updated,store_date'
            else:
                searchset = 'filter=id:' + (arclist) + '&field_list=cover_date,id,issue_number,name,date_last_updated,store_date,volume'
        else:
            cv_rtype = 'volume/' + str(comicid)
            searchset = 'name,count_of_issues,issues,start_year,site_detail_url,image,publisher,description,store_date'
        PULLURL = mylar.CVURL + str(cv_rtype) + '/?api_key=' + str(comicapi) + '&format=xml&' + str(searchset) + '&offset=' + str(offset)
    elif any([rtype == 'image', rtype == 'firstissue', rtype == 'imprints_first']):
        #this is used ONLY for CV_ONLY
        PULLURL = mylar.CVURL + 'issues/?api_key=' + str(comicapi) + '&format=xml&filter=id:' + str(issueid) + '&field_list=cover_date,store_date,image'
    elif rtype == 'storyarc':
        PULLURL = mylar.CVURL + 'story_arcs/?api_key=' + str(comicapi) + '&format=xml&filter=name:' + str(issueid) + '&field_list=cover_date'
    elif rtype == 'comicyears':
        PULLURL = mylar.CVURL + 'volumes/?api_key=' + str(comicapi) + '&format=xml&filter=id:' + str(comicidlist) + '&field_list=name,id,start_year,publisher,description,deck,aliases,count_of_issues&offset=' + str(offset)
    elif rtype == 'import':
        PULLURL = mylar.CVURL + 'issues/?api_key=' + str(comicapi) + '&format=xml&filter=id:' + (comicidlist) + '&field_list=cover_date,id,issue_number,name,date_last_updated,store_date,volume' + '&offset=' + str(offset)
    elif rtype == 'update_dates':
        PULLURL = mylar.CVURL + 'issues/?api_key=' + str(comicapi) + '&format=xml&filter=id:' + (comicidlist)+ '&field_list=date_last_updated, id, issue_number, store_date, cover_date, name, volume ' + '&offset=' + str(offset)
    elif rtype == 'single_issue':
        #this is used for retrieving single issue metadata for use when displaying metadata information for a selected issue.
        PULLURL = mylar.CVURL + 'issue/4000-' + str(issueid) + '?api_key=' + str(comicapi) + '&format=json'
    elif rtype == 'db_updater':
        PULLURL = mylar.CVURL + 'issues/?api_key=' + str(comicapi) + '&format=json&filter=date_last_updated:'+dateinfo['start_date']+'|'+dateinfo['end_date']+'&field_list=date_last_updated,id,volume,issue_number&sort=date_last_updated:asc&offset=' + str(offset)
    #logger.info('CV.PULLURL: ' + PULLURL)
    #new CV API restriction - one api request / second.
    if mylar.CONFIG.CVAPI_RATE is None or mylar.CONFIG.CVAPI_RATE < 2:
        time.sleep(2)
    else:
        time.sleep(mylar.CONFIG.CVAPI_RATE)

    #download the file:
    #set payload to None for now...
    payload = None

    try:
        r = requests.get(PULLURL, params=payload, verify=mylar.CONFIG.CV_VERIFY, headers=mylar.CV_HEADERS)
    except Exception as e:
        logger.warn('Error fetching data from ComicVine: %s' % (e))
        if all(['Expecting value: line 1 column 1' not in str(e), rtype != 'db_updater']):
            mylar.BACKENDSTATUS_CV = 'down'
            return
        else:
            return False

    mylar.BACKENDSTATUS_CV = 'up'
    #logger.fdebug('cv status code : ' + str(r.status_code))
    #logger.fdebug('rtype: %s' % rtype)
    try:
        if any([rtype == 'single_issue', rtype == 'db_updater']):
            dom = r.json()
            #logger.info('cv_data returned: %s' % dom)
        else:
            dom = parseString(r.content)
    except ExpatError:
        if '<title>Abnormal Traffic Detected' in r.content.decode('utf-8'):
            logger.error('ComicVine has banned this server\'s IP address because it exceeded the API rate limit.')
        else:
            logger.warn('[WARNING] ComicVine is not responding correctly at the moment. This is usually due to some problems on their end. If you re-try things again in a few moments, things might work')
            mylar.BACKENDSTATUS_CV = 'down'
        return
    except Exception as e:
        if all(['Expecting value: line 1 column 1' in str(e), rtype == 'db_updater']):
            return False
        else:
            logger.warn('[ERROR] Error returned from CV: %s [%s]' % (e, r.content))
            mylar.BACKENDSTATUS_CV = 'down'
            return
    else:
        return dom

def getComic(comicid, rtype, issueid=None, arc=None, arcid=None, arclist=None, comicidlist=None, dateinfo=None, series=False):
    if rtype == 'issue':
        offset = 1
        issue = {}
        ndic = []
        issuechoice = []
        comicResults = []
        firstdate = '2099-00-00'
        #let's find out how many results we get from the query...
        if comicid is None:
            #if comicid is None, it's coming from the story arc search results.
            id = arcid
            #since the arclist holds the issueids, and the pertinent reading order - we need to strip out the reading order so this works.
            aclist = ''
            if arclist.startswith('M'):
                islist = arclist[1:]
            else:
                for ac in arclist.split('|'):
                    aclist += ac[:ac.find(',')] + '|'
                if aclist.endswith('|'):
                    aclist = aclist[:-1]
                islist = aclist
        else:
            id = comicid
            islist = None
        searched = pulldetails(id, 'issue', None, 0, islist)
        if searched is None:
            return False
        totalResults = searched.getElementsByTagName('number_of_total_results')[0].firstChild.wholeText
        logger.fdebug("there are " + str(totalResults) + " search results...")
        if not totalResults:
            return False
        countResults = 0
        while (countResults < int(totalResults)):
            logger.fdebug('Querying & compiling from %s - %s out of %s results'
                % (countResults, countResults + 100, totalResults)
            )
            if countResults > 0:
                #new api - have to change to page # instead of offset count
                offsetcount = countResults
                searched = pulldetails(id, 'issue', None, offsetcount, islist)
            if not searched:
                # if it's a CV timeout/error, just return what we have thus far and hopefully
                # the next run will be able to catch things up
                break
            issuechoice, tmpdate = GetIssuesInfo(id, searched, arcid)
            if tmpdate < firstdate:
                firstdate = tmpdate
            ndic = ndic + issuechoice
            #search results are limited to 100 and by pagination now...let's account for this.
            countResults = countResults + 100

        issue['issuechoice'] = ndic
        issue['firstdate'] = firstdate
        return issue

    elif rtype == 'comic':
        dom = pulldetails(comicid, 'comic', None, 1)
        return GetComicInfo(comicid, dom, series=series)
    elif any([rtype == 'image', rtype == 'firstissue', rtype == 'imprints_first']):
        dom = pulldetails(comicid, rtype, issueid, 1)
        return Getissue(issueid, dom, rtype)
    elif rtype == 'storyarc':
        dom = pulldetails(arc, 'storyarc', None, 1)
        return GetComicInfo(issueid, dom)
    elif rtype == 'comicyears':
        #used by the story arc searcher when adding a given arc to poll each ComicID in order to populate the Series Year & volume (hopefully).
        #this grabs each issue based on issueid, and then subsets the comicid for each to be used later.
        #set the offset to 0, since we're doing a filter.
        dom = pulldetails(arcid, 'comicyears', offset=0, comicidlist=comicidlist)
        return GetSeriesYears(dom)
    elif rtype == 'import':
        #used by the importer when doing a scan with metatagging enabled. If metatagging comes back true, then there's an IssueID present
        #within the tagging (with CT). This compiles all of the IssueID's during a scan (in 100's), and returns the corresponding CV data
        #related to the given IssueID's - namely ComicID, Name, Volume (more at some point, but those are the important ones).
        offset = 1
        id_count = 0
        import_list = []
        logger.fdebug('comicidlist:' + str(comicidlist))

        while id_count < len(comicidlist):
            #break it up by 100 per api hit
            #do the first 100 regardless
            in_cnt = 0
            if id_count + 100 <= len(comicidlist):
                endcnt = id_count + 100
            else:
                endcnt = len(comicidlist)

            for i in range(id_count, endcnt):
                if in_cnt == 0:
                    tmpidlist = str(comicidlist[i])
                else:
                    tmpidlist += '|' + str(comicidlist[i])
                in_cnt +=1
            logger.fdebug('tmpidlist: ' + str(tmpidlist))

            searched = pulldetails(None, 'import', offset=0, comicidlist=tmpidlist)

            if searched is None:
                break
            else:
                tGIL = GetImportList(searched)
                import_list += tGIL

            id_count +=100

        return import_list

    elif rtype == 'update_dates':
        dom = pulldetails(None, 'update_dates', offset=1, comicidlist=comicidlist)
        return UpdateDates(dom)
    elif rtype == 'single_issue':
        dom = pulldetails(comicid, 'single_issue', issueid=issueid, offset=1, arclist=None, comicidlist=None)
        return singleIssue(dom)
    elif rtype == 'db_updater':
        dtchk1 = datetime.datetime.strptime(dateinfo, '%Y-%m-%d %H:%M:%S')
        dtnow = datetime.datetime.now(tz=datetime.timezone.utc)
        dtnow = dtnow.strftime('%Y-%m-%d %H:%M:%S')
        # stupid convert it back to a datetime after we localized the UTC timestamp
        dtnow = datetime.datetime.strptime(dtnow, '%Y-%m-%d %H:%M:%S')
        dateline_range = []
        for x in mylar.CONFIG.PROBLEM_DATES:
            bline = datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S')
            # check if problem date is greater than the start range
            if bline > dtchk1:
                # check if problem date is lower than the end range
                if bline < dtnow:
                    dateline_range.append({'start_date': dateinfo,
                                           'end_date': (bline - datetime.timedelta(seconds=round((mylar.CONFIG.PROBLEM_DATES_SECONDS / 60),2))).strftime('%Y-%m-%d %H:%M:%S')})
                    dateline_range.append({'start_date': (bline + datetime.timedelta(seconds=round((mylar.CONFIG.PROBLEM_DATES_SECONDS / 60),2))).strftime('%Y-%m-%d %H:%M:%S'),
                                           'end_date': helpers.now()})

        if not dateline_range:
            # we store dates in UTC - CV API returns dates in UTC-7 (Pacific time zone)
            p_zone =  pytz.timezone("US/Pacific")
            dtchk1 = datetime.datetime.strptime(dateinfo, '%Y-%m-%d %H:%M:%S')
            p_aware = pytz.utc.localize(dtchk1)
            p_start = p_aware.astimezone(p_zone)

            p_now = dtnow.astimezone(p_zone)
            dateline_range.append({'start_date': datetime.datetime.strftime(p_start, '%Y-%m-%d %H:%M:%S'),
                                   'end_date': datetime.datetime.strftime(p_now, '%Y-%m-%d %H:%M:%S')})

        resultlist = {}
        theResults = []
        innerbreak = False
        for dateline in dateline_range:
            offset = 1

            resultlist = pulldetails(None, 'db_updater', offset=0, dateinfo=dateline)

            totalResults = resultlist['number_of_total_results']
            logger.fdebug('There are %s total results' % totalResults)

            if not totalResults:
                if len(dateline_range) == 1:
                    return {'count': 0, 'results': [], 'totalcount': 0}
                else:
                    continue

            overallResults = totalResults
            if totalResults > 1500:
                # force set this here and we'll stagger the remainder over the next hr + depending on size.
                totalResults = 1500
                #if it's the 1st of 2 loops, we need to break out after the 1st loop if it's > 1500 results
                innerbreak = True

            countResults = 0
            while (countResults < int(totalResults)):
                logger.fdebug('Querying & compiling from %s - %s out of %s results'
                    % (countResults, countResults + 100, totalResults)
                )
                if countResults > 0:
                    #new api - have to change to page # instead of offset count
                    offsetcount = countResults
                    resultlist = pulldetails(None, 'db_updater', offset=offsetcount, dateinfo=dateline)
                    if resultlist is False:
                        logger.info('reached as far as (%s) of (%s) and CV has returned an error. Stopping here unfortunately...' % (offsetcount, totalResults))
                        break
                resultlist = db_updates(resultlist)
                theResults = theResults + resultlist
                #search results are limited to 100 and by pagination now...let's account for this.
                countResults = countResults + 100

            if innerbreak is True:
                break

        return {'count': len(theResults),
                'results': theResults,
                'totalcount': overallResults}

def GetComicInfo(comicid, dom, safechk=None, series=False):
    if safechk is None:
        #safetycheck when checking comicvine. If it times out, increment the chk on retry attempts up until 5 tries then abort.
        safechk = 1
    elif safechk > 4:
        logger.error('Unable to add / refresh the series due to inablity to retrieve data from ComicVine. You might want to try abit later and/or make sure ComicVine is up.')
        return
    #comicvine isn't as up-to-date with issue counts..
    #so this can get really buggered, really fast.
    try:
       tracks = dom.getElementsByTagName('issue')
    except:
       logger.error('Unable to add / refresh the series due to inablity to retrieve data from ComicVine. You might want to try abit later and/or make sure ComicVine is up.')
       return
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
    # to return the parent name of the <name> node : dom.getElementsByTagName('name')[0].parentNode.nodeName
    # where [0] denotes the number of the name field(s)
    # where nodeName denotes the parentNode : ComicName = results, publisher = publisher, issues = issue
    try:
        names = len(dom.getElementsByTagName('name'))
        n = 0
        comic['ComicPublisher'] = 'Unknown'   #set this to a default value here so that it will carry through properly
        while (n < names):
            if dom.getElementsByTagName('name')[n].parentNode.nodeName == 'results':
                try:
                    comic['ComicName'] = dom.getElementsByTagName('name')[n].firstChild.wholeText
                    comic['ComicName'] = comic['ComicName'].strip()
                except:
                    logger.error('There was a problem retrieving the given data from ComicVine. Ensure that www.comicvine.com is accessible AND that you have provided your OWN ComicVine API key.')
                    return

            elif dom.getElementsByTagName('name')[n].parentNode.nodeName == 'publisher':
                try:
                    comic['ComicPublisher'] = dom.getElementsByTagName('name')[n].firstChild.wholeText
                except Exception as e:
                    logger.error('error encountered: %s' % e)
                    comic['ComicPublisher'] = "Unknown"
            n += 1
    except:
        logger.warn('Something went wrong retrieving from ComicVine. Ensure your API is up-to-date and that comicvine is accessible')
        return

    comic['FirstIssueID'] = dom.getElementsByTagName('id')[0].firstChild.wholeText

    try:
        comic['ComicYear'] = dom.getElementsByTagName('start_year')[0].firstChild.wholeText
    except:
        comic['ComicYear'] = '0000'

    #safety check, cause you known, dufus'...
    if any([comic['ComicYear'][-1:] == '-', comic['ComicYear'][-1:] == '?']):
        comic['ComicYear'] = comic['ComicYear'][:-1]

    found = False
    comicPublisher = comic['ComicPublisher']
    publisherImprint= None

    #the description field actually holds the Volume# - so let's grab it
    desc_soup = None
    try:
        descchunk = dom.getElementsByTagName('description')[0].firstChild.wholeText
        desc_soup = Soup(descchunk, "html.parser")
        desclinks = desc_soup.findAll('a')
        comic_desc = drophtml(descchunk)
    #    desdeck +=1
    except:
        comic_desc = 'None'

    #sometimes the deck has volume labels
    try:
        deckchunk = dom.getElementsByTagName('deck')[0].firstChild.wholeText
        comic_deck = deckchunk
    #    desdeck +=1
    except:
        comic_deck = 'None'

    givb = get_imprint_volume_and_booktype(series, comic['ComicYear'], comic['ComicPublisher'], comic['FirstIssueID'], comic_desc, comic_deck)
    if givb:
        comic['ComicPublisher'] = givb['ComicPublisher']
        comic['PublisherImprint'] = givb['PublisherImprint']
        comic['ComicDescription'] = givb['ComicDescription']
        comic['ComicVersion'] = givb['ComicVersion']
        comic['Type'] = givb['Type']
        comic['incorrect_volume'] = givb['incorrect_volume']
    #if series is True:
    #    # this is a really crappy way to do it - it works, but meh.
    #    try:
    #        for k,v in mylar.PUBLISHER_IMPRINTS.items():
    #            if k == 'publishers':
    #                for b in v:
    #                    for d,e in b.items():
    #                        for g in e:
    #                            chkyear = False
    #                            for f,h in g.items():
    #                                if f == 'name':
    #                                    pubname = h
    #                                if f == 'publication_run' and chkyear is True:
    #                                    pubrun = h
    #                                    y = pubrun.find('-')
    #                                    pub_start = pubrun[:y][:4].strip()
    #                                    pub_start_month = pubrun[:y][pubrun.find('.')+1:].strip()
    #                                    pub_end = pubrun[y+2:][:4].strip()
    #                                    if len(pub_end) == 0 and len(pub_start) == 0:
    #                                        chkyear = False
    #                                        found = False
    #                                        continue
    #                                    elif len(pub_end) == 0:
    #                                        pub_end = None
    #                                        if int(comic['ComicYear']) <= int(pub_start[:4]):
    #                                            logger.info('comic year of %s is prior to imprint publication date of %s' % (comic['ComicYear'], pub_start[:4]))
    #                                            comic['ComicPublisher'] = None
    #                                            comic['PublisherImprint'] = None
    #                                            found = False
    #                                        else:
    #                                            found = True
    #                                    else:
    #                                        if int(pub_end[:4]) > int(comic['ComicYear'])  > int(pub_start[:4]):
    #                                            found = True
    #                                        else:
    #                                            pub_end_month = pubrun[y+2:][pubrun.find('.',y+2)+1:].strip()
    #                                            if any([ int(pub_end[:4]) == int(comic['ComicYear']), int(pub_start[:4]) == int(comic['ComicYear']) ]):
    #                                                quick_chk = getComic(comicid=None, rtype='imprints_first', issueid=comic['FirstIssueID'])
    #                                                if quick_chk:
    #                                                    cdate = None
    #                                                    sdate = None
    #                                                    #quick_chk['store_date'], quick_chk['cover_date']
    #                                                    if quick_chk['cover_date'] and quick_chk['cover_date'] != '0000':
    #                                                        cdate = quick_chk['cover_date'][5:7]
    #                                                    if quick_chk['store_date'] and quick_chk['store_date'] != '0000':
    #                                                        sdate = quick_chk['store_date'][5:7]

    #                                                    if int(pub_end[:4]) == int(comic['ComicYear']):
    #                                                        if cdate != None:
    #                                                            end_month = cdate
    #                                                        else:
    #                                                            end_month = sdate
    #                                                        if int(pub_end_month) <= int(end_month):
    #                                                            logger.fdebug('[Year;%s] publication month of %s is before the end imprint date of %s' % (comic['ComicYear'], end_month, pub_end_month))
    #                                                            found = True
    #                                                        else:
    #                                                            found = False

    #                                                    elif int(pub_start[:4]) == int(comic['ComicYear']):
    #                                                        if cdate != None:
    #                                                            start_month = cdate
    #                                                        else:
    #                                                            start_month = sdate
    #                                                        if int(pub_start_month) <= int(start_month):
    #                                                            logger.fdebug('[Year:%s] issue publication month of %s is after the start imprint date of %s' % (comic['ComicYear'], start_month, pub_start_month))
    #                                                            found = True
    #                                                        else:
    #                                                            found = False

    #                                            else:
    #                                                logger.info('comic year of %s is not within the imprint publication date range of %s - %s' % (comic['ComicYear'], pub_start[:4], pub_end[:4]))
    #                                                comicPublisher = None
    #                                                publisherImprint = None
    #                                                found = False
    #                                    chkyear = False

    #                                elif f == 'imprints' and h is not None:
    #                                    # if we get here, it's an imprint of an imprint
    #                                    for i in h:
    #                                        if i['name'].lower() == comic['ComicPublisher'].lower():
    #                                            logger.info('imprint matched: %s ---> %s' % (i['name'],h))
    #                                            comicPublisher = pubname
    #                                            publisherImprint = i['name']
    #                                            found = True
    #                                            break
    #                                elif all([f != 'imprints', f != 'publication_run']) and h is not None and found is not True:
    #                                    if h.lower() == comic['ComicPublisher'].lower():
    #                                        logger.info('imprint matched: %s ---> %s' % (d, h))
    #                                        comicPublisher = d
    #                                        publisherImprint = h
    #                                        chkyear = True
    #                                        found = True

    #                            if found is True:
    #                                break
    #                        if found is True:
    #                            break
    #                    if found is True:
    #                        break
    #    except Exception as e:
    #        logger.error('error: %s' % e)

    #if comicPublisher is not None:
    #    comic['ComicPublisher'] = comicPublisher
    #comic['PublisherImprint'] = publisherImprint

    try:
        comic['ComicURL'] = dom.getElementsByTagName('site_detail_url')[trackcnt].firstChild.wholeText
    except:
        #this should never be an exception. If it is, it's probably due to CV timing out - so let's sleep for abit then retry.
        logger.warn('Unable to retrieve URL for volume. This is usually due to a timeout to CV, or going over the API. Retrying again in 10s.')
        time.sleep(10)
        safechk +=1
        GetComicInfo(comicid, dom, safechk)

    #desdeck = 0
    #the description field actually holds the Volume# - so let's grab it
    #desc_soup = None
    #try:
    #    descchunk = dom.getElementsByTagName('description')[0].firstChild.wholeText
    #    desc_soup = Soup(descchunk, "html.parser")
    #    desclinks = desc_soup.findAll('a')
    #    comic_desc = drophtml(descchunk)
    #    desdeck +=1
    #except:
    #    comic_desc = 'None'

    #sometimes the deck has volume labels
    #try:
    #    deckchunk = dom.getElementsByTagName('deck')[0].firstChild.wholeText
    #    comic_deck = deckchunk
    #    desdeck +=1
    #except:
    #    comic_deck = 'None'

    #comic['ComicDescription'] = comic_desc

    try:
        comic['Aliases'] = dom.getElementsByTagName('aliases')[0].firstChild.wholeText
        comic['Aliases'] = re.sub('\n', '##', comic['Aliases']).strip()
        if comic['Aliases'][-2:] == '##':
            comic['Aliases'] = comic['Aliases'][:-2]
        #logger.fdebug('Aliases: ' + str(aliases))
    except:
        comic['Aliases'] = 'None'

    #comic['ComicVersion'] = 'None' #noversion'

    #figure out if it's a print / digital edition.
    #comic['Type'] = 'None'
    #if comic_deck != 'None':
    #    if any(['print' in comic_deck.lower(), 'digital' in comic_deck.lower(), 'paperback' in comic_deck.lower(), 'one shot' in re.sub('-', '', comic_deck.lower()).strip(), 'hardcover' in comic_deck.lower()]):
    #        if all(['print' in comic_deck.lower(), 'reprint' not in comic_deck.lower()]):
    #            comic['Type'] = 'Print'
    #        elif 'digital' in comic_deck.lower():
    #            comic['Type'] = 'Digital'
    #        elif 'paperback' in comic_deck.lower():
    #            comic['Type'] = 'TPB'
    #        elif 'graphic novel' in comic_deck.lower():
    #            comic['Type'] = 'GN'
    #        elif 'hardcover' in comic_deck.lower():
    #            comic['Type'] = 'HC'
    #        elif 'oneshot' in re.sub('-', '', comic_deck.lower()).strip():
    #            comic['Type'] = 'One-Shot'
    #        else:
    #            comic['Type'] = 'Print'

    #if comic_desc != 'None' and comic['Type'] == 'None':
    #    if 'print' in comic_desc[:60].lower() and all(['also available as a print' not in comic_desc.lower(), 'for the printed edition' not in comic_desc.lower(), 'print edition can be found' not in comic_desc.lower(), 'reprints' not in comic_desc.lower()]):
    #        comic['Type'] = 'Print'
    #    elif all(['digital' in comic_desc[:60].lower(), 'graphic novel' not in comic_desc[:60].lower(), 'digital edition can be found' not in comic_desc.lower()]):
    #        comic['Type'] = 'Digital'
    #    elif all(['paperback' in comic_desc[:60].lower(), 'paperback can be found' not in comic_desc.lower()]) or all(['hardcover' not in comic_desc[:60].lower(), 'collects' in comic_desc[:60].lower()]):
    #        comic['Type'] = 'TPB'
    #    elif all(['graphic novel' in comic_desc[:60].lower(), 'graphic novel can be found' not in comic_desc.lower()]):
    #        comic['Type'] = 'GN'
    #    elif 'hardcover' in comic_desc[:60].lower() and 'hardcover can be found' not in comic_desc.lower():
    #        comic['Type'] = 'HC'
    #    elif any(['one-shot' in comic_desc[:60].lower(), 'one shot' in comic_desc[:60].lower()]) and any(['can be found' not in comic_desc.lower(), 'following the' not in comic_desc.lower(), 'after the' not in comic_desc.lower()]):
    #        i = 0
    #        comic['Type'] = 'One-Shot'
    #        avoidwords = ['preceding', 'after the', 'following the', 'continued from']
    #        while i < 2:
    #            if i == 0:
    #                cbd = 'one-shot'
    #            elif i == 1:
    #                cbd = 'one shot'
    #            tmp1 = comic_desc[:60].lower().find(cbd)
    #            if tmp1 != -1:
    #                for x in avoidwords:
    #                    tmp2 = comic_desc[:tmp1].lower().find(x)
    #                    if tmp2 != -1:
    #                        logger.fdebug('FAKE NEWS: caught incorrect reference to one-shot. Forcing to Print')
    #                        comic['Type'] = 'Print'
    #                        i = 3
    #                        break
    #            i+=1
    #    else:
    #        comic['Type'] = 'Print'

    if all([comic_desc != 'None', 'trade paperback' in comic_desc[:30].lower(), 'collecting' in comic_desc[:40].lower()]):
        #ie. Trade paperback collecting Marvel Team-Up #9-11, 48-51, 72, 110 & 145.
        first_collect = comic_desc.lower().find('collecting')
        #logger.info('first_collect: %s' % first_collect)
        #logger.info('comic_desc: %s' % comic_desc)
        #logger.info('desclinks: %s' % desclinks)
        issue_list = []
        micdrop = []
        if desc_soup is not None:
            #if it's point form bullets, ignore it cause it's not the current volume stuff.
            test_it = desc_soup.find('ul')
            if test_it:
                for x in test_it.findAll('li'):
                    if any(['Next' in x.findNext(text=True), 'Previous' in x.findNext(text=True)]):
                        mic_check = x.find('a')
                        micdrop.append(mic_check['data-ref-id'])

        for fc in desclinks:
            try:
                fc_id = fc['data-ref-id']
            except Exception:
                continue

            if fc_id in micdrop:
                continue

            fc_name = fc.findNext(text=True)

            if fc_id.startswith('4000'):
                fc_cid = None
                fc_isid = fc_id
                iss_start = fc_name.find('#')
                issuerun = fc_name[iss_start:].strip()
                fc_name = fc_name[:iss_start].strip()
            elif fc_id.startswith('4050'):
                fc_cid = fc_id
                fc_isid = None
                issuerun = fc.next_sibling
                if issuerun is not None:
                    lines = re.sub("[^0-9]", ' ', issuerun).strip().split(' ')
                    if len(lines) > 0:
                        for x in sorted(lines, reverse=True):
                            srchline = issuerun.rfind(x)
                            if srchline != -1:
                                try:
                                    if issuerun[srchline+len(x)] == ',' or issuerun[srchline+len(x)] == '.' or issuerun[srchline+len(x)] == ' ':
                                        issuerun = issuerun[:srchline+len(x)]
                                        break
                                except Exception as e:
                                    #logger.warn('[ERROR] %s' % e)
                                    continue
                else:
                    iss_start = fc_name.find('#')
                    issuerun = fc_name[iss_start:].strip()
                    fc_name = fc_name[:iss_start].strip()

                if issuerun.strip().endswith('.') or issuerun.strip().endswith(','):
                    #logger.fdebug('Changed issuerun from %s to %s' % (issuerun, issuerun[:-1]))
                    issuerun = issuerun.strip()[:-1]
                if issuerun.endswith(' and '):
                    issuerun = issuerun[:-4].strip()
                elif issuerun.endswith(' and'):
                    issuerun = issuerun[:-3].strip()
            else:
                continue
                #    except:
                #        pass
            issue_list.append({'series':   fc_name,
                               'comicid':  fc_cid,
                               'issueid':  fc_isid,
                               'issues':   issuerun})
            #first_collect = cis

        logger.info('Collected issues in volume: %s' % issue_list)
        if len(issue_list) == 0:
            comic['Issue_List'] = 'None'
        else:
            comic['Issue_List'] = issue_list
    else:
        comic['Issue_List'] = 'None'

    #comic['incorrect_volume'] = None
    #while (desdeck > 0):
    #    if desdeck == 1:
    #        if comic_desc == 'None':
    #            comicDes = comic_deck[:30]
    #        else:
    #            #extract the first 60 characters
    #            comicDes = comic_desc[:60].replace('New 52', '')
    #    elif desdeck == 2:
    #        #extract the characters from the deck
    #        comicDes = comic_deck[:30].replace('New 52', '')
    #    else:
    #        break

    #    i = 0
    #    while (i < 2):
    #        incorrect_volume = None
    #        if 'volume' in comicDes.lower():
    #            #found volume - let's grab it.
    #            v_find = comicDes.lower().find('volume')
    #            #arbitrarily grab the next 10 chars (6 for volume + 1 for space + 3 for the actual vol #)
    #            #increased to 10 to allow for text numbering (+5 max)
    #            #sometimes it's volume 5 and ocassionally it's fifth volume.
    #            if 'collected' in comicDes.lower():
    #                cde = re.sub(r'[\s\-]', '', comicDes).strip().lower()
    #                if (
    #                       'oneshot' in cde[:cde.find('collected')]
    #                       and cde.find('volume') > cde.find('collected')
    #                ):
    #                    # we set the incorrect_volume here so that when it returns to update the db we can
    #                    # check to see if it matches the existing volume and if so replace it with any new
    #                    # values since the incorrect volume is incorrect.
    #                    incorrect_volume = comicDes[v_find:v_find+15]
    #            if comicDes[v_find+7:comicDes.find(' ', v_find+7)].isdigit():
    #                comic['ComicVersion'] = re.sub("[^0-9]", "", comicDes[v_find+7:comicDes.find(' ', v_find+7)]).strip()
    #                break
    #            elif i == 0:
    #                vfind = comicDes[v_find:v_find +15]   #if it's volume 5 format
    #                basenums = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10', 'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5'}
    #                logger.fdebug('volume X format - ' + str(i) + ': ' + vfind)
    #            else:
    #                vfind = comicDes[:v_find]   # if it's fifth volume format
    #                basenums = {'zero': '0', 'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5', 'sixth': '6', 'seventh': '7', 'eighth': '8', 'nineth': '9', 'tenth': '10', 'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5'}
    #                logger.fdebug('X volume format - ' + str(i) + ': ' + vfind)
    #            og_vfind = vfind
    #            volconv = ''
    #            for nums in basenums:
    #                if nums in vfind.lower():
    #                    sconv = basenums[nums]
    #                    vfind = re.sub(nums, sconv, vfind.lower())
    #                    break
    #            #logger.info('volconv: ' + str(volconv))

    #            #now we attempt to find the character position after the word 'volume'
    #            if i == 0:
    #                volthis = vfind.lower().find('volume')
    #                volthis = volthis + 6  # add on the actual word to the position so that we can grab the subsequent digit
    #                vfind = vfind[volthis:volthis + 4]  # grab the next 4 characters ;)
    #            elif i == 1:
    #                volthis = vfind.lower().find('volume')
    #                vfind = vfind[volthis - 4:volthis]  # grab the next 4 characters ;)

    #            if '(' in vfind:
    #                #bracket detected in versioning'
    #                vfindit = re.findall('[^()]+', vfind)
    #                vfind = vfindit[0]
    #            vf = re.findall('[^<>]+', vfind)
    #            try:
    #                ledigit = re.sub("[^0-9]", "", vf[0])
    #                if ledigit != '':
    #                    #logger.info('incorrect_volume: %s / vfind: %s' % (incorrect_volume, og_vfind))
    #                    if all([incorrect_volume is not None, incorrect_volume == og_vfind]):
    #                        logger.fdebug('previous incorrect volume possible. Assigning incorrect value as: %s' % ledigit)
    #                        comic['incorrect_volume'] = ledigit
    #                    else:
    #                        comic['ComicVersion'] = ledigit
    #                        logger.fdebug("Volume information found! Adding to series record : volume " + comic['ComicVersion'])
    #                        break
    #            except:
    #                pass

    #            i += 1
    #        else:
    #            i += 1

    #    if comic['ComicVersion'] == 'None':
    #        logger.fdebug('comic[ComicVersion]:' + str(comic['ComicVersion']))
    #        desdeck -= 1
    #    else:
    #        break

    if vari == "yes":
        comic['ComicIssues'] = str(cntit)
    else:
        comic['ComicIssues'] = dom.getElementsByTagName('count_of_issues')[0].firstChild.wholeText

    try:
        comic['ComicImage'] = dom.getElementsByTagName('super_url')[0].firstChild.wholeText
    except:
        try:
            comic['ComicImage'] = dom.getElementByTagName('original_url')[0].firstChild.wholeText
        except:
            comic['ComicImage'] = 'None'

    try:
        comic['ComicImageALT'] = dom.getElementsByTagName('small_url')[0].firstChild.wholeText
    except:
        comic['ComicImageALT'] = 'None'

    try:
        comic['ComicImageThumbnail'] = dom.getElementsByTagName('icon_url')[0].firstChild.wholeText
    except:
        comic['ComicImageThumbnail'] = 'None'

    try:
        comic['ComicThumbURL'] = dom.getElementsByTagName('thumb_url')[0].firstChild.wholeText
    except:
        comic['ComicThumbURL'] = 'None'

    #logger.info('comic: %s' % comic)
    return comic

def GetIssuesInfo(comicid, dom, arcid=None):
    subtracks = dom.getElementsByTagName('issue')
    if not mylar.CONFIG.CV_ONLY:
        cntiss = dom.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
        logger.fdebug("issues I've counted: " + str(len(subtracks)))
        logger.fdebug("issues CV says it has: " + str(int(cntiss)))

        if int(len(subtracks)) != int(cntiss):
            logger.fdebug("CV's count is wrong, I counted different...going with my count for physicals" + str(len(subtracks)))
            cntiss = len(subtracks) # assume count of issues is wrong, go with ACTUAL physical api count
        cntiss = int(cntiss)
        n = cntiss -1
    else:
        n = int(len(subtracks))
    tempissue = {}
    issuech = []
    firstdate = '2099-00-00'
    for subtrack in subtracks:
        if not mylar.CONFIG.CV_ONLY:
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
                totnames = len(subtrack.getElementsByTagName('name'))
                tot = 0
                while (tot < totnames):
                    if subtrack.getElementsByTagName('name')[tot].parentNode.nodeName == 'volume':
                        tempissue['ComicName'] = subtrack.getElementsByTagName('name')[tot].firstChild.wholeText
                        tempissue['ComicName'] = tempissue['ComicName'].strip()
                    elif subtrack.getElementsByTagName('name')[tot].parentNode.nodeName == 'issue':
                        try:
                            tempissue['Issue_Name'] = subtrack.getElementsByTagName('name')[tot].firstChild.wholeText
                        except:
                            tempissue['Issue_Name'] = None
                    tot += 1
            except:
                tempissue['ComicName'] = 'None'

            try:
                totids = len(subtrack.getElementsByTagName('id'))
                idt = 0
                while (idt < totids):
                    if subtrack.getElementsByTagName('id')[idt].parentNode.nodeName == 'volume':
                        tempissue['Comic_ID'] = subtrack.getElementsByTagName('id')[idt].firstChild.wholeText
                    elif subtrack.getElementsByTagName('id')[idt].parentNode.nodeName == 'issue':
                        tempissue['Issue_ID'] = subtrack.getElementsByTagName('id')[idt].firstChild.wholeText
                    idt += 1
            except:
                tempissue['Issue_Name'] = 'None'

            try:
                tempissue['CoverDate'] = subtrack.getElementsByTagName('cover_date')[0].firstChild.wholeText
            except:
                tempissue['CoverDate'] = '0000-00-00'
            try:
                tempissue['StoreDate'] = subtrack.getElementsByTagName('store_date')[0].firstChild.wholeText
            except:
                tempissue['StoreDate'] = '0000-00-00'
            try:
                digital_desc = subtrack.getElementsByTagName('description')[0].firstChild.wholeText
            except:
                tempissue['DigitalDate'] = '0000-00-00'
            else:
                tempissue['DigitalDate'] = '0000-00-00'
                if all(['digital' in digital_desc.lower()[-90:], 'print' in digital_desc.lower()[-90:]]):
                    #get the digital date of issue here...
                    mff = mylar.filechecker.FileChecker()
                    vlddate = mff.checkthedate(digital_desc[-90:], fulldate=True)
                    #logger.fdebug('vlddate: %s' % vlddate)
                    if vlddate:
                        tempissue['DigitalDate'] = vlddate
            try:
                tempissue['Issue_Number'] = subtrack.getElementsByTagName('issue_number')[0].firstChild.wholeText
            except:
                logger.fdebug('No Issue Number available - Trade Paperbacks, Graphic Novels and Compendiums are not supported as of yet.')
            else:
                tempissue['Issue_Number'] = tempissue['Issue_Number'].strip()
                if 'Issue #' in tempissue['Issue_Number']:
                    tempissue['Issue_Number'] = re.sub('Issue #', '', tempissue['Issue_Number']).strip()
            try:
                tempissue['ComicImage'] = subtrack.getElementsByTagName('small_url')[0].firstChild.wholeText
            except:
                tempissue['ComicImage'] = 'None'

            try:
                tempissue['ComicImageALT'] = subtrack.getElementsByTagName('medium_url')[0].firstChild.wholeText
            except:
                tempissue['ComicImageALT'] = 'None'

            if arcid is None:
                issuech.append({
                    'Comic_ID':                comicid,
                    'Issue_ID':                tempissue['Issue_ID'],
                    'Issue_Number':            tempissue['Issue_Number'],
                    'Issue_Date':              tempissue['CoverDate'],
                    'Store_Date':              tempissue['StoreDate'],
                    'Digital_Date':            tempissue['DigitalDate'],
                    'Issue_Name':              tempissue['Issue_Name'],
                    'Image':                   tempissue['ComicImage'],
                    'ImageALT':                tempissue['ComicImageALT']
                    })

            else:
                issuech.append({
                    'ArcID':                   arcid,
                    'ComicName':               tempissue['ComicName'],
                    'ComicID':                 tempissue['Comic_ID'],
                    'IssueID':                 tempissue['Issue_ID'],
                    'Issue_Number':            tempissue['Issue_Number'],
                    'Issue_Date':              tempissue['CoverDate'],
                    'Store_Date':              tempissue['StoreDate'],
                    'Digital_Date':            tempissue['DigitalDate'],
                    'Issue_Name':              tempissue['Issue_Name']
                    })

            if tempissue['CoverDate'] < firstdate and tempissue['CoverDate'] != '0000-00-00':
                firstdate = tempissue['CoverDate']
        n-= 1

    #logger.fdebug('issue_info: %s' % issuech)
    #issue['firstdate'] = firstdate
    return issuech, firstdate

def Getissue(issueid, dom, rtype):
    #if the Series Year doesn't exist, get the first issue and take the date from that
    if any([rtype == 'firstissue', rtype == 'imprints_first']):
        try:
            first_year = dom.getElementsByTagName('cover_date')[0].firstChild.wholeText
        except:
            first_year = '0000'
            if rtype == 'firstissue':
                return first_year

        if first_year != '0000':
            the_year = first_year[:4]
            the_month = first_year[5:7]
            the_date = the_year + '-' + the_month

        if rtype == 'firstissue':
            return the_year
        else:
            try:
                store_year = dom.getElementsByTagName('store_date')[0].firstChild.wholeText
            except:
                store_year = '0000'
                return {'store_date': store_year, 'cover_date': first_year}

            storeyear = store_year[:4]
            store_month = store_year[5:7]
            store_date = storeyear + '-' + store_month
            return {'store_date': store_date, 'cover_date': the_date}
    else:
        try:
            image = dom.getElementsByTagName('super_url')[0].firstChild.wholeText
        except:
            image = None
        try:
            image_alt = dom.getElementsByTagName('small_url')[0].firstChild.wholeText
        except:
            image_alt = None

        return {'image':     image,
                'image_alt': image_alt}

def GetSeriesYears(dom):
    #used by the 'add a story arc' option to individually populate the Series Year for each series within the given arc.
    #series year is required for alot of functionality.
    series = dom.getElementsByTagName('volume')
    tempseries = {}
    serieslist = []
    for dm in series:
        # we need to know # of issues in a given series to force the type if required based on number of issues published to date.
        number_issues = dm.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
        try:
            totids = len(dm.getElementsByTagName('id'))
            idc = 0
            while (idc < totids):
                if dm.getElementsByTagName('id')[idc].parentNode.nodeName == 'volume':
                    tempseries['ComicID'] = dm.getElementsByTagName('id')[idc].firstChild.wholeText
                idc+=1
        except:
            logger.warn('There was a problem retrieving a comicid for a series within the arc. This will have to manually corrected most likely.')
            tempseries['ComicID'] = 'None'

        tempseries['Series'] = 'None'
        tempseries['Publisher'] = 'None'
        try:
            totnames = len(dm.getElementsByTagName('name'))
            namesc = 0
            while (namesc < totnames):
                if dm.getElementsByTagName('name')[namesc].parentNode.nodeName == 'volume':
                    tempseries['Series'] = dm.getElementsByTagName('name')[namesc].firstChild.wholeText
                    tempseries['Series'] = tempseries['Series'].strip()
                elif dm.getElementsByTagName('name')[namesc].parentNode.nodeName == 'publisher':
                    tempseries['Publisher'] = dm.getElementsByTagName('name')[namesc].firstChild.wholeText
                namesc+=1
        except:
            logger.warn('There was a problem retrieving a Series Name or Publisher for a series within the arc. This will have to manually corrected.')

        try:
            tempseries['SeriesYear'] = dm.getElementsByTagName('start_year')[0].firstChild.wholeText
        except:
            logger.warn('There was a problem retrieving the start year for a particular series within the story arc.')
            tempseries['SeriesYear'] = '0000'

        #cause you know, dufus'...
        if tempseries['SeriesYear'][-1:] == '-':
            tempseries['SeriesYear'] = tempseries['SeriesYear'][:-1]

        desdeck = 0
        #the description field actually holds the Volume# - so let's grab it
        desc_soup = None
        try:
            descchunk = dm.getElementsByTagName('description')[0].firstChild.wholeText
            desc_soup = Soup(descchunk, "html.parser")
            desclinks = desc_soup.findAll('a')
            comic_desc = drophtml(descchunk)
            desdeck +=1
        except:
            comic_desc = 'None'

        #sometimes the deck has volume labels
        try:
            deckchunk = dm.getElementsByTagName('deck')[0].firstChild.wholeText
            comic_deck = deckchunk
            desdeck +=1
        except:
            comic_deck = 'None'

        #comic['ComicDescription'] = comic_desc

        try:
            tempseries['Aliases'] = dm.getElementsByTagName('aliases')[0].firstChild.wholeText
            tempseries['Aliases'] = re.sub('\n', '##', tempseries['Aliases']).strip()
            if tempseries['Aliases'][-2:] == '##':
                tempseries['Aliases'] = tempseries['Aliases'][:-2]
            #logger.fdebug('Aliases: ' + str(aliases))
        except:
            tempseries['Aliases'] = 'None'

        tempseries['Volume'] = 'None' #noversion'

        #figure out if it's a print / digital edition.
        tempseries['Type'] = 'None'
        if comic_deck != 'None':
            if any(['print' in comic_deck.lower(), 'digital' in comic_deck.lower(), 'paperback' in comic_deck.lower(), 'one shot' in re.sub('-', '', comic_deck.lower()).strip(), 'hardcover' in comic_deck.lower()]):
                if all(['print' in comic_deck.lower(), 'reprint' not in comic_deck.lower()]):
                    tempseries['Type'] = 'Print'
                elif 'digital' in comic_deck.lower():
                    tempseries['Type'] = 'Digital'
                elif 'paperback' in comic_deck.lower():
                    tempseries['Type'] = 'TPB'
                elif 'graphic novel' in comic_deck.lower():
                    tempseries['Type'] = 'GN'
                elif 'hardcover' in comic_deck.lower():
                    tempseries['Type'] = 'HC'
                elif 'oneshot' in re.sub('-', '', comic_deck.lower()).strip():
                    tempseries['Type'] = 'One-Shot'
                else:
                    tempseries['Type'] = 'Print'

        if comic_desc != 'None' and tempseries['Type'] == 'None':
            if 'print' in comic_desc[:60].lower() and all(['also available as a print' not in comic_desc.lower(), 'for the printed edition' not in comic_desc.lower(), 'print edition can be found' not in comic_desc.lower(), 'reprints' not in comic_desc.lower()]):
                tempseries['Type'] = 'Print'
            elif all(['digital' in comic_desc[:60].lower(), 'graphic novel' not in comic_desc[:60].lower(), 'digital edition can be found' not in comic_desc.lower()]):
                tempseries['Type'] = 'Digital'
            elif all(['paperback' in comic_desc[:60].lower(), 'paperback can be found' not in comic_desc.lower()]) or all(['hardcover' not in comic_desc[:60].lower(), 'collects' in comic_desc[:60].lower()]):
                tempseries['Type'] = 'TPB'
            elif all(['graphic novel' in comic_desc[:60].lower(), 'graphic novel can be found' not in comic_desc.lower()]):
                tempseries['Type'] = 'GN'
            elif 'hardcover' in comic_desc[:60].lower() and 'hardcover can be found' not in comic_desc.lower():
                tempseries['Type'] = 'HC'
            elif any(['one-shot' in comic_desc[:60].lower(), 'one shot' in comic_desc[:60].lower()]) and any(['can be found' not in comic_desc.lower(), 'following the' not in comic_desc.lower()]):
                i = 0
                tempseries['Type'] = 'One-Shot'
                avoidwords = ['preceding', 'after the special', 'following the', 'continued from']
                while i < 2:
                    if i == 0:
                        cbd = 'one-shot'
                    elif i == 1:
                        cbd = 'one shot'
                    tmp1 = comic_desc[:60].lower().find(cbd)
                    if tmp1 != -1:
                        for x in avoidwords:
                            tmp2 = comic_desc[:tmp1].lower().find(x)
                            if tmp2 != -1:
                                logger.fdebug('FAKE NEWS: caught incorrect reference to one-shot. Forcing to Print')
                                tempseries['Type'] = 'Print'
                                i = 3
                                break
                    i+=1
            else:
                tempseries['Type'] = 'Print'

        if all([comic_desc != 'None', 'trade paperback' in comic_desc[:30].lower(), 'collecting' in comic_desc[:40].lower()]):
            #ie. Trade paperback collecting Marvel Team-Up #9-11, 48-51, 72, 110 & 145.
            first_collect = comic_desc.lower().find('collecting')
            #logger.info('first_collect: %s' % first_collect)
            #logger.info('comic_desc: %s' % comic_desc)
            #logger.info('desclinks: %s' % desclinks)
            issue_list = []
            micdrop = []
            if desc_soup is not None:
                #if it's point form bullets, ignore it cause it's not the current volume stuff.
                test_it = desc_soup.find('ul')
                if test_it:
                    for x in test_it.findAll('li'):
                        if any(['Next' in x.findNext(text=True), 'Previous' in x.findNext(text=True)]):
                            mic_check = x.find('a')
                            micdrop.append(mic_check['data-ref-id'])

            for fc in desclinks:
                try:
                    fc_id = fc['data-ref-id']
                except Exception:
                    continue

                if fc_id in micdrop:
                    continue
                fc_name = fc.findNext(text=True)
                if fc_id.startswith('4000'):
                    fc_cid = None
                    fc_isid = fc_id
                    iss_start = fc_name.find('#')
                    issuerun = fc_name[iss_start:].strip()
                    fc_name = fc_name[:iss_start].strip()
                elif fc_id.startswith('4050'):
                    fc_cid = fc_id
                    fc_isid = None
                    issuerun = fc.next_sibling
                    if issuerun is not None:
                        lines = re.sub("[^0-9]", ' ', issuerun).strip().split(' ')
                        if len(lines) > 0:
                            for x in sorted(lines, reverse=True):
                                srchline = issuerun.rfind(x)
                                if srchline != -1:
                                    try:
                                        if issuerun[srchline+len(x)] == ',' or issuerun[srchline+len(x)] == '.' or issuerun[srchline+len(x)] == ' ':
                                            issuerun = issuerun[:srchline+len(x)]
                                            break
                                    except Exception as e:
                                        logger.warn('[ERROR] %s' % e)
                                        continue
                    else:
                        iss_start = fc_name.find('#')
                        issuerun = fc_name[iss_start:].strip()
                        fc_name = fc_name[:iss_start].strip()

                    if issuerun.endswith('.') or issuerun.endswith(','):
                        #logger.fdebug('Changed issuerun from %s to %s' % (issuerun, issuerun[:-1]))
                        issuerun = issuerun[:-1]
                    if issuerun.endswith(' and '):
                        issuerun = issuerun[:-4].strip()
                    elif issuerun.endswith(' and'):
                        issuerun = issuerun[:-3].strip()
                else:
                    continue
                    #    except:
                    #        pass
                issue_list.append({'series':   fc_name,
                                   'comicid':  fc_cid,
                                   'issueid':  fc_isid,
                                   'issues':   issuerun})
                #first_collect = cis

            logger.info('Collected issues in volume: %s' % issue_list)
            tempseries['Issue_List'] = issue_list
        else:
            tempseries['Issue_List'] = 'None'

        volume_found = None
        while (desdeck > 0):
            if desdeck == 1:
                if comic_desc == 'None':
                    comicDes = comic_deck[:30]
                else:
                    #extract the first 60 characters
                    comicDes = comic_desc[:60].replace('New 52', '')
            elif desdeck == 2:
                #extract the characters from the deck
                comicDes = comic_deck[:30].replace('New 52', '')
            else:
                break

            i = 0
            looped_once = False
            while (i < 2):
                if 'volume' in comicDes.lower():
                    #found volume - let's grab it.
                    v_find = comicDes.lower().find('volume')

                    if all([comicDes.lower().find('annual issue from') > 0, volume_found is not None, looped_once is False]):
                        logger.fdebug('wrong annual declaration found previously. Attempting to correct')
                        cd_find = comic_desc.lower().find('annual issue from') + 17
                        comicDes = comic_desc[cd_find:cd_find+30]
                        if 'volume' in comicDes.lower():
                            v_find = comicDes.lower().find('volume') #_desc[cd_find:cd_find+45].lower().find('volume')
                            if i == 1:
                                i = 0
                            looped_once = True
                            volume_found = None

                    #arbitrarily grab the next 10 chars (6 for volume + 1 for space + 3 for the actual vol #)
                    #increased to 10 to allow for text numbering (+5 max)
                    #sometimes it's volume 5 and ocassionally it's fifth volume.
                    if i == 0:
                        vfind = comicDes[v_find:v_find +15]   #if it's volume 5 format
                        basenums = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10', 'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5'}
                        logger.fdebug('volume X format - %s: %s' % (i, vfind))
                    else:
                        vfind = comicDes[:v_find]   # if it's fifth volume format
                        basenums = {'zero': '0', 'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5', 'sixth': '6', 'seventh': '7', 'eighth': '8', 'nineth': '9', 'tenth': '10', 'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5'}
                        logger.fdebug('X volume format - %s: %s' % (i, vfind))
                    volconv = ''
                    for nums in basenums:
                        if nums in vfind.lower():
                            sconv = basenums[nums]
                            vfind = re.sub(nums, sconv, vfind.lower())
                            break

                    #now we attempt to find the character position after the word 'volume'
                    if i == 0:
                        volthis = vfind.lower().find('volume')
                        volthis = volthis + 6  # add on the actual word to the position so that we can grab the subsequent digit
                        vfind = vfind[volthis:volthis + 4]  # grab the next 4 characters ;)
                    elif i == 1:
                        volthis = vfind.lower().find('volume')
                        vfind = vfind[volthis - 4:volthis]  # grab the next 4 characters ;)

                    if '(' in vfind:
                        #bracket detected in versioning'
                        vfindit = re.findall('[^()]+', vfind)
                        vfind = vfindit[0]
                    vf = re.findall('[^<>]+', vfind)
                    try:
                        ledigit = re.sub("[^0-9]", "", vf[0])
                        if ledigit != '' and volume_found is None:
                            volume_found = ledigit
                            #tempseries['Volume'] = ledigit
                            logger.fdebug("Volume information found! Adding to series record : volume %s" % volume_found)
                    except:
                        pass

                    i += 1
                else:
                    i += 1
            tempseries['Volume'] = volume_found

            if tempseries['Volume'] == 'None':
                logger.fdebug('tempseries[Volume]: %s' % tempseries['Volume'])
                desdeck -= 1
            else:
                break

        if all([int(number_issues) == 1, tempseries['SeriesYear'] < helpers.today()[:4], tempseries['Type'] != 'One-Shot', tempseries['Type'] != 'TPB', tempseries['Type'] != 'HC', tempseries['Type'] != 'GN']):
            booktype = 'One-Shot'
        else:
            booktype = tempseries['Type']

        serieslist.append({"ComicID":    tempseries['ComicID'],
                           "ComicName":  tempseries['Series'],
                           "SeriesYear": tempseries['SeriesYear'],
                           "Publisher":  tempseries['Publisher'],
                           "Volume":     tempseries['Volume'],
                           "Aliases":    tempseries['Aliases'],
                           "Type":       booktype})

    return serieslist

def UpdateDates(dom):
    issues = dom.getElementsByTagName('issue')
    tempissue = {}
    issuelist = []
    for dm in issues:
        tempissue['ComicID'] = 'None'
        tempissue['IssueID'] = 'None'
        try:
            totids = len(dm.getElementsByTagName('id'))
            idc = 0
            while (idc < totids):
                if dm.getElementsByTagName('id')[idc].parentNode.nodeName == 'volume':
                    tempissue['ComicID'] = dm.getElementsByTagName('id')[idc].firstChild.wholeText
                if dm.getElementsByTagName('id')[idc].parentNode.nodeName == 'issue':
                    tempissue['IssueID'] = dm.getElementsByTagName('id')[idc].firstChild.wholeText
                idc+=1
        except:
            logger.warn('There was a problem retrieving a comicid/issueid for the given issue. This will have to manually corrected most likely.')

        tempissue['SeriesTitle'] = 'None'
        tempissue['IssueTitle'] = 'None'
        try:
            totnames = len(dm.getElementsByTagName('name'))
            namesc = 0
            while (namesc < totnames):
                if dm.getElementsByTagName('name')[namesc].parentNode.nodeName == 'issue':
                    tempissue['IssueTitle'] = dm.getElementsByTagName('name')[namesc].firstChild.wholeText
                elif dm.getElementsByTagName('name')[namesc].parentNode.nodeName == 'volume':
                    tempissue['SeriesTitle'] = dm.getElementsByTagName('name')[namesc].firstChild.wholeText
                namesc+=1
        except:
            logger.warn('There was a problem retrieving the Series Title / Issue Title for a series within the arc. This will have to manually corrected.')

        try:
            tempissue['CoverDate'] = dm.getElementsByTagName('cover_date')[0].firstChild.wholeText
        except:
            tempissue['CoverDate'] = '0000-00-00'
        try:
            tempissue['StoreDate'] = dm.getElementsByTagName('store_date')[0].firstChild.wholeText
        except:
            tempissue['StoreDate'] = '0000-00-00'
        try:
            tempissue['IssueNumber'] = dm.getElementsByTagName('issue_number')[0].firstChild.wholeText
        except:
            logger.fdebug('No Issue Number available - Trade Paperbacks, Graphic Novels and Compendiums are not supported as of yet.')
            tempissue['IssueNumber'] = 'None'
        else:
            if 'Issue #' in tempissue['IssueNumber']:
                tempissue['IssueNumber'] = re.sub('Issue #', '', tempissue['IssueNumber']).strip()

        try:
            tempissue['date_last_updated'] = dm.getElementsByTagName('date_last_updated')[0].firstChild.wholeText
        except:
            tempissue['date_last_updated'] = '0000-00-00'

        issuelist.append({'ComicID':            tempissue['ComicID'],
                          'IssueID':            tempissue['IssueID'],
                          'SeriesTitle':        tempissue['SeriesTitle'],
                          'IssueTitle':         tempissue['IssueTitle'],
                          'CoverDate':          tempissue['CoverDate'],
                          'StoreDate':          tempissue['StoreDate'],
                          'IssueNumber':        tempissue['IssueNumber'],
                          'Date_Last_Updated':  tempissue['date_last_updated']})

    return issuelist

def singleIssue(results):
    data = results['results']
    issue_info = {}
    issuecredits = []
    if results['number_of_total_results'] == 1:
        issue_info['series'] = data['volume']['name']
        issue_info['title'] = data['name']
        issue_info['comicid'] = data['volume']['id']
        issue_info['coverdate'] = data['cover_date']
        issue_info['storedate'] = data['store_date']
        issue_info['date_added'] = data['date_added']
        issue_info['date_updated'] = data['date_last_updated']
        issue_info['deck']= data['deck']
        issue_info['description'] = drophtml(data['description'])
        issue_info['issueid'] = data['id']
        issue_info['image'] = data['image']['medium_url'] #/ ['screen_url'] / ['screen_large_url'] / ['original_url']
        issue_info['issue_number'] = data['issue_number']
        try:
            if 'Issue #' in issue_info['issue_number']:
                issue_info['issue_number'] = re.sub('Issue #', '', issue_info['issue_number']).strip()
        except Exception:
            pass
        for x in data['person_credits']:
            issuecredits.append({'role': x['role'], 'name': x['name']})
        issue_info['credits'] = issuecredits
        #logger.fdebug('issue_info: %s' % issue_info)
        return issue_info

def GetImportList(results):
    importlist = results.getElementsByTagName('issue')
    serieslist = []
    importids = {}
    tempseries = {}
    for implist in importlist:
        try:
            totids = len(implist.getElementsByTagName('id'))
            idt = 0
            while (idt < totids):
                if implist.getElementsByTagName('id')[idt].parentNode.nodeName == 'volume':
                    tempseries['ComicID'] = implist.getElementsByTagName('id')[idt].firstChild.wholeText
                elif implist.getElementsByTagName('id')[idt].parentNode.nodeName == 'issue':
                    tempseries['IssueID'] = implist.getElementsByTagName('id')[idt].firstChild.wholeText
                idt += 1
        except:
            tempseries['ComicID'] = None

        try:
            totnames = len(implist.getElementsByTagName('name'))
            tot = 0
            while (tot < totnames):
                if implist.getElementsByTagName('name')[tot].parentNode.nodeName == 'volume':
                    tempseries['ComicName'] = implist.getElementsByTagName('name')[tot].firstChild.wholeText
                    tempseries['ComicName'] = tempseries['ComicName'].strip()
                elif implist.getElementsByTagName('name')[tot].parentNode.nodeName == 'issue':
                    try:
                        tempseries['Issue_Name'] = implist.getElementsByTagName('name')[tot].firstChild.wholeText
                    except:
                        tempseries['Issue_Name'] = None
                tot += 1
        except:
            tempseries['ComicName'] = 'None'

        try:
            tempseries['Issue_Number'] = implist.getElementsByTagName('issue_number')[0].firstChild.wholeText
        except:
            logger.fdebug('No Issue Number available - Trade Paperbacks, Graphic Novels and Compendiums are not supported as of yet.')
        else:
            if 'Issue #' in tempseries['Issue_Number']:
                tempseries['Issue_Number'] = re.sub('Issue #', '', tempseries['Issue_Number']).strip()

        logger.info('tempseries:' + str(tempseries))
        serieslist.append({"ComicID":      tempseries['ComicID'],
                           "IssueID":      tempseries['IssueID'],
                           "ComicName":    tempseries['ComicName'],
                           "Issue_Name":   tempseries['Issue_Name'],
                           "Issue_Number": tempseries['Issue_Number']})


    return serieslist

def db_updates(results, rtype='issueid'):
    # type is either 'issueid' or 'comicid'
    # issueid = update based on changes to issues (new issues, updates, etc)
    # comicid = update based on changes to comicid
    dataset = []
    data = results['results']
    for x in sorted(data, key=itemgetter('date_last_updated'), reverse=False):
        if rtype == 'comicid':
            xlastissue = None
            if x['last_issue'] is not None:
                xlastissue = {'issueid': x['last_issue'],
                              'issue_number': x['last_issue']['issue_number']}

            dataset.append({
                               'comicid': x['id'],
                               'count_of_issues': x['count_of_issues'],
                               'last_updated': x['date_last_updated'],
                               'last_issue': xlastissue,
                          })
        else:
            dataset.append({
                               'comicid': x['volume'],
                               'issueid': x['id'],
                               'last_updated': x['date_last_updated'],
                               'issue_number': x['issue_number'],
                          })
    return dataset


def drophtml(html):
    if html is not None:
        soup = Soup(html, "html.parser")

        text_parts = soup.findAll(text=True)
        #print ''.join(text_parts)
        return ''.join(text_parts)
    else:
        return ''

def get_imprint_volume_and_booktype(series, comicyear, publisher, firstissueid, description, deck, annual_check=False):
    # this is used to quick_load the imprint, volume and booktype of a specific issue (ie. searchresults editing a result)
    comic = {}

    comic['ComicYear'] = comicyear
    if any([comicyear[-1:] == '-', comicyear[-1:] == '?']):
        comic['ComicYear'] = comicyear[:-1]

    found = False
    comic['ComicPublisher'] = publisher
    comicPublisher = publisher
    publisherImprint= None

    if series is True:
        # this is a really crappy way to do it - it works, but meh.
        try:
            for k,v in mylar.PUBLISHER_IMPRINTS.items():
                if k == 'publishers':
                    for b in v:
                        for d,e in b.items():
                            for g in e:
                                chkyear = False
                                for f,h in g.items():
                                    if f == 'name':
                                        pubname = h
                                    if f == 'publication_run' and chkyear is True:
                                        pubrun = h
                                        y = pubrun.find('-')
                                        pub_start = pubrun[:y][:4].strip()
                                        pub_start_month = pubrun[:y][pubrun.find('.')+1:].strip()
                                        pub_end = pubrun[y+2:][:4].strip()
                                        if len(pub_end) == 0 and len(pub_start) == 0:
                                            chkyear = False
                                            found = False
                                            continue
                                        elif len(pub_end) == 0:
                                            pub_end = None
                                            if int(comic['ComicYear']) <= int(pub_start[:4]):
                                                logger.info('comic year of %s is prior to imprint publication date of %s' % (comic['ComicYear'], pub_start[:4]))
                                                comic['ComicPublisher'] = None
                                                comic['PublisherImprint'] = None
                                                found = False
                                            else:
                                                found = True
                                        else:
                                            if int(pub_end[:4]) > int(comic['ComicYear'])  > int(pub_start[:4]):
                                                found = True
                                            else:
                                                pub_end_month = pubrun[y+2:][pubrun.find('.',y+2)+1:].strip()
                                                if any([ int(pub_end[:4]) == int(comic['ComicYear']), int(pub_start[:4]) == int(comic['ComicYear']) ]):
                                                    quick_chk = getComic(comicid=None, rtype='imprints_first', issueid=firstissueid)
                                                    if quick_chk:
                                                        cdate = None
                                                        sdate = None
                                                        #quick_chk['store_date'], quick_chk['cover_date']
                                                        if quick_chk['cover_date'] and quick_chk['cover_date'] != '0000':
                                                            cdate = quick_chk['cover_date'][5:7]
                                                        if quick_chk['store_date'] and quick_chk['store_date'] != '0000':
                                                            sdate = quick_chk['store_date'][5:7]

                                                        if int(pub_end[:4]) == int(comic['ComicYear']):
                                                            if cdate != None:
                                                                end_month = cdate
                                                            else:
                                                                end_month = sdate
                                                            if int(pub_end_month) <= int(end_month):
                                                                logger.fdebug('[Year;%s] publication month of %s is before the end imprint date of %s' % (comic['ComicYear'], end_month, pub_end_month))
                                                                found = True
                                                            else:
                                                                found = False

                                                        elif int(pub_start[:4]) == int(comic['ComicYear']):
                                                            if cdate != None:
                                                                start_month = cdate
                                                            else:
                                                                start_month = sdate
                                                            if int(pub_start_month) <= int(start_month):
                                                                logger.fdebug('[Year:%s] issue publication month of %s is after the start imprint date of %s' % (comic['ComicYear'], start_month, pub_start_month))
                                                                found = True
                                                            else:
                                                                found = False

                                                else:
                                                    logger.info('comic year of %s is not within the imprint publication date range of %s - %s' % (comic['ComicYear'], pub_start[:4], pub_end[:4]))
                                                    comicPublisher = None
                                                    publisherImprint = None
                                                    found = False
                                        chkyear = False

                                    elif f == 'imprints' and h is not None:
                                        # if we get here, it's an imprint of an imprint
                                        for i in h:
                                            if i['name'].lower() == comic['ComicPublisher'].lower():
                                                logger.info('imprint matched: %s ---> %s' % (i['name'],h))
                                                comicPublisher = pubname
                                                publisherImprint = i['name']
                                                found = True
                                                break
                                    elif all([f != 'imprints', f != 'publication_run']) and h is not None and found is not True:
                                        imprint_match = False
                                        for x, y in mylar.IMPRINT_MAPPING.items():
                                            if all([
                                                y.lower() == h.lower(),
                                                x.lower() == comic['ComicPublisher'].lower()
                                            ]):
                                                imprint_match = True
                                                break

                                        if h.lower() == comic['ComicPublisher'].lower() or imprint_match is True:
                                            if mylar.CONFIG.IMPRINT_MAPPING_TYPE == 'CV':
                                                comicPublisher = d
                                                publisherImprint = comic['ComicPublisher']
                                            else:
                                                comicPublisher = d
                                                publisherImprint = h
                                            logger.fdebug('imprint matching: [PRIORITY:%s] %s ---> %s' % (mylar.CONFIG.IMPRINT_MAPPING_TYPE, comicPublisher, publisherImprint))
                                            chkyear = True
                                            found = True

                                if found is True:
                                    break
                            if found is True:
                                break
                        if found is True:
                            break
        except Exception as e:
            logger.error('error: %s' % e)

    if comicPublisher is not None:
        comic['ComicPublisher'] = comicPublisher
    comic['PublisherImprint'] = publisherImprint

    desdeck = 0
    #the description field actually holds the Volume# - so let's grab it
    try:
        if annual_check is False:
            comic_desc = drophtml(description)
        else:
            comic_desc = description
        desdeck +=1
    except:
        comic_desc = 'None'

    #sometimes the deck has volume labels
    try:
        comic_deck = deck
        desdeck +=1
    except:
        comic_deck = 'None'

    comic['ComicDescription'] = comic_desc

    comic['ComicVersion'] = 'None' #noversion'

    #figure out if it's a print / digital edition.
    comic['Type'] = 'None'
    if comic_deck != 'None':
        if any(['print' in comic_deck.lower(), 'digital' in comic_deck.lower(), 'paperback' in comic_deck.lower(), 'one shot' in re.sub('-', '', comic_deck.lower()).strip(), 'hardcover' in comic_deck.lower()]):
            if all(['print' in comic_deck.lower(), 'reprint' not in comic_deck.lower()]):
                comic['Type'] = 'Print'
            elif 'digital' in comic_deck.lower():
                comic['Type'] = 'Digital'
            elif 'paperback' in comic_deck.lower():
                comic['Type'] = 'TPB'
            elif 'graphic novel' in comic_deck.lower():
                comic['Type'] = 'GN'
            elif 'hardcover' in comic_deck.lower():
                comic['Type'] = 'HC'
            elif 'oneshot' in re.sub('-', '', comic_deck.lower()).strip():
                comic['Type'] = 'One-Shot'
            else:
                comic['Type'] = 'Print'

    if comic_desc != 'None' and comic['Type'] == 'None':
        if 'print' in comic_desc[:60].lower() and all(['also available as a print' not in comic_desc.lower(), 'for the printed edition' not in comic_desc.lower(), 'print edition can be found' not in comic_desc.lower(), 'reprints' not in comic_desc.lower()]):
            comic['Type'] = 'Print'
        elif all(['digital' in comic_desc[:60].lower(), 'graphic novel' not in comic_desc[:60].lower(), 'digital edition can be found' not in comic_desc.lower()]):
            comic['Type'] = 'Digital'
        elif all(['paperback' in comic_desc[:60].lower(), 'paperback can be found' not in comic_desc.lower()]) or all(['hardcover' not in comic_desc[:60].lower(), 'collects' in comic_desc[:60].lower()]):
            comic['Type'] = 'TPB'
        elif all(['graphic novel' in comic_desc[:60].lower(), 'graphic novel can be found' not in comic_desc.lower()]):
            comic['Type'] = 'GN'
        elif 'hardcover' in comic_desc[:60].lower() and 'hardcover can be found' not in comic_desc.lower():
            comic['Type'] = 'HC'
        elif any(['one-shot' in comic_desc[:60].lower(), 'one shot' in comic_desc[:60].lower()]) and any(['can be found' not in comic_desc.lower(), 'following the' not in comic_desc.lower(), 'after the' not in comic_desc.lower()]):
            i = 0
            comic['Type'] = 'One-Shot'
            avoidwords = ['preceding', 'after the', 'following the', 'continued from']
            while i < 2:
                if i == 0:
                    cbd = 'one-shot'
                elif i == 1:
                    cbd = 'one shot'
                tmp1 = comic_desc[:60].lower().find(cbd)
                if tmp1 != -1:
                    for x in avoidwords:
                        tmp2 = comic_desc[:tmp1].lower().find(x)
                        if tmp2 != -1:
                            logger.fdebug('FAKE NEWS: caught incorrect reference to one-shot. Forcing to Print')
                            comic['Type'] = 'Print'
                            i = 3
                            break
                i+=1
        else:
            comic['Type'] = 'Print'

    comic['incorrect_volume'] = None
    while (desdeck > 0):
        if desdeck == 1:
            if comic_desc == 'None':
                comicDes = comic_deck[:30]
            else:
                #extract the first 60 characters
                comicDes = comic_desc[:60].replace('New 52', '')
        elif desdeck == 2:
            #extract the characters from the deck
            comicDes = comic_deck[:30].replace('New 52', '')
        else:
            break

        i = 0
        while (i < 2):
            incorrect_volume = None
            if 'volume' in comicDes.lower():
                #found volume - let's grab it.
                v_find = comicDes.lower().find('volume')
                #arbitrarily grab the next 10 chars (6 for volume + 1 for space + 3 for the actual vol #)
                #increased to 10 to allow for text numbering (+5 max)
                #sometimes it's volume 5 and ocassionally it's fifth volume.
                if 'collected' in comicDes.lower():
                    cde = re.sub(r'[\s\-]', '', comicDes).strip().lower()
                    if (
                           'oneshot' in cde[:cde.find('collected')]
                           and cde.find('volume') > cde.find('collected')
                    ):
                        # we set the incorrect_volume here so that when it returns to update the db we can
                        # check to see if it matches the existing volume and if so replace it with any new
                        # values since the incorrect volume is incorrect.
                        incorrect_volume = comicDes[v_find:v_find+15]
                if comicDes[v_find+7:comicDes.find(' ', v_find+7)].isdigit():
                    comic['ComicVersion'] = re.sub("[^0-9]", "", comicDes[v_find+7:comicDes.find(' ', v_find+7)]).strip()
                    break
                elif i == 0:
                    vfind = comicDes[v_find:v_find +15]   #if it's volume 5 format
                    basenums = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10', 'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5'}
                    logger.fdebug('volume X format - ' + str(i) + ': ' + vfind)
                else:
                    vfind = comicDes[:v_find]   # if it's fifth volume format
                    basenums = {'zero': '0', 'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5', 'sixth': '6', 'seventh': '7', 'eighth': '8', 'nineth': '9', 'tenth': '10', 'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5'}
                    logger.fdebug('X volume format - ' + str(i) + ': ' + vfind)
                og_vfind = vfind
                volconv = ''
                for nums in basenums:
                    if nums in vfind.lower():
                        sconv = basenums[nums]
                        vfind = re.sub(nums, sconv, vfind.lower())
                        break
                #logger.info('volconv: ' + str(volconv))

                #now we attempt to find the character position after the word 'volume'
                if i == 0:
                    volthis = vfind.lower().find('volume')
                    volthis = volthis + 6  # add on the actual word to the position so that we can grab the subsequent digit
                    vfind = vfind[volthis:volthis + 4]  # grab the next 4 characters ;)
                elif i == 1:
                    volthis = vfind.lower().find('volume')
                    vfind = vfind[volthis - 4:volthis]  # grab the next 4 characters ;)

                if '(' in vfind:
                    #bracket detected in versioning'
                    vfindit = re.findall('[^()]+', vfind)
                    vfind = vfindit[0]
                vf = re.findall('[^<>]+', vfind)
                try:
                    ledigit = re.sub("[^0-9]", "", vf[0])
                    if ledigit != '':
                        #logger.info('incorrect_volume: %s / vfind: %s' % (incorrect_volume, og_vfind))
                        if all([incorrect_volume is not None, incorrect_volume == og_vfind]):
                            logger.fdebug('previous incorrect volume possible. Assigning incorrect value as: %s' % ledigit)
                            comic['incorrect_volume'] = ledigit
                        else:
                            comic['ComicVersion'] = ledigit
                            logger.fdebug("Volume information found! Adding to series record : volume " + comic['ComicVersion'])
                            break
                except:
                    pass


                i += 1
            else:
                i += 1

        if comic['ComicVersion'] == 'None':
            logger.fdebug('comic[ComicVersion]:' + str(comic['ComicVersion']))
            desdeck -= 1
        else:
            break

    logger.info('comic_values: %s' % (comic,))

    return comic
