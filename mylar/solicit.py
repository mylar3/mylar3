
from bs4 import BeautifulSoup, UnicodeDammit
import urllib2
import csv
import fileinput
import sys
import re
import os
import sqlite3
import datetime
import unicodedata
from decimal import Decimal
from HTMLParser import HTMLParseError
from time import strptime

import mylar
from mylar import logger, helpers

def solicit(month, year):
    #convert to numerics just to ensure this...
    month = int(month)
    year = int(year)

    #print ( "month: " + str(month) )
    #print ( "year: " + str(year) )

    # in order to gather ALL upcoming - let's start to loop through months going ahead one at a time
    # until we get a null then break. (Usually not more than 3 months in advance is available)
    mnloop = 0
    upcoming = []

    publishers = {'DC Comics':'DC Comics', 'DC\'s': 'DC Comics', 'Marvel':'Marvel Comics', 'Image':'Image Comics', 'IDW':'IDW Publishing', 'Dark Horse':'Dark Horse'}


# -- this is no longer needed (testing)
#    while (mnloop < 5):
#        if year == 2014:
#            if len(str(month)) == 1:
#                month_string = '0' + str(month)
#            else:
#                month_string = str(month)
#            datestring = str(year) + str(month_string)
#        else:
#            datestring = str(month) + str(year)

#        pagelinks = "http://www.comicbookresources.com/tag/solicits" + str(datestring)

        #using the solicits+datestring leaves out some entries occasionally
        #should use http://www.comicbookresources.com/tag/solicitations
        #then just use the logic below but instead of datestring, find the month term and 
        #go ahead up to +5 months.

    if month > 0:
        month_start = month
        month_end = month + 5
        #if month_end > 12:
            # ms = 8, me=13  [(12-8)+(13-12)] = [4 + 1] = 5
            # [(12 - ms) + (me - 12)] = number of months (5)

        monthlist = []
        mongr = month_start

        #we need to build the months we can grab, but the non-numeric way.
        while (mongr <= month_end):
            mon = mongr
            if mon == 13:
                mon = 1
                year +=1

            if len(str(mon)) == 1:
                mon = '0' + str(mon)

            monthlist.append({"month":     helpers.fullmonth(str(mon)).lower(),
                              "num_month": mon,
                              "year":      str(year)})
            mongr+=1

        logger.info('months: ' + str(monthlist))

        pagelinks = "http://www.comicbookresources.com/tag/solicitations"


        #logger.info('datestring:' + datestring)
        #logger.info('checking:' + pagelinks)
        pageresponse = urllib2.urlopen ( pagelinks )
        soup = BeautifulSoup (pageresponse)
        cntlinks = soup.findAll('h3')
        lenlinks = len(cntlinks)
        #logger.info( str(lenlinks) + ' results' )

        publish = []
        resultURL = []
        resultmonth = []
        resultyear = []

        x = 0
        cnt = 0

        while (x < lenlinks):
            headt = cntlinks[x] #iterate through the hrefs pulling out only results.
            if "/?page=article&amp;id=" in str(headt):
                #print ("titlet: " + str(headt))
                headName = headt.findNext(text=True)
                #print ('headName: ' + headName)
                if 'Image' in headName: print 'IMAGE FOUND'
                if not all( ['Marvel' in headName, 'DC' in headName, 'Image' in headName] ) and ('Solicitations' in headName or 'Solicits' in headName):
                   # test for month here (int(month) + 5)
                    if not any(d.get('month', None) == str(headName).lower() for d in monthlist):
                        for mt in monthlist:
                            if mt['month'] in headName.lower():
                                logger.info('matched on month: ' + str(mt['month']))
                                logger.info('matched on year: ' + str(mt['year']))
                                resultmonth.append(mt['num_month'])
                                resultyear.append(mt['year'])

                                pubstart = headName.find('Solicitations')
                                publishchk = False
                                for pub in publishers:
                                    if pub in headName[:pubstart]:
                                        #print 'publisher:' + str(publishers[pub])
                                        publish.append(publishers[pub])
                                        publishchk = True
                                        break
                                if publishchk == False:
                                    break
                                    #publish.append( headName[:pubstart].strip() )
                                abc = headt.findAll('a', href=True)[0]
                                ID_som = abc['href']  #first instance will have the right link...
                                resultURL.append( ID_som )
                                #print '(' + str(cnt) + ') [ ' + publish[cnt] + '] Link URL: ' + resultURL[cnt]
                                cnt+=1

                    else:
                        logger.info('incorrect month - not using.')
                       
            x+=1

        if cnt == 0:
            return #break  # no results means, end it

        loopthis = (cnt-1)
        #this loops through each 'found' solicit page 
        #shipdate = str(month_string) + '-' + str(year)  - not needed.
        while ( loopthis >= 0 ):
            #print 'loopthis is : ' + str(loopthis)
            #print 'resultURL is : ' + str(resultURL[loopthis])
            shipdate = str(resultmonth[loopthis]) + '-' + str(resultyear[loopthis])
            upcoming += populate(resultURL[loopthis], publish[loopthis], shipdate)
            loopthis -=1

    logger.info( str(len(upcoming)) + ' upcoming issues discovered.' )

    newfl = mylar.CACHE_DIR + "/future-releases.txt"
    newtxtfile = open(newfl, 'wb')

    cntr = 1
    for row in upcoming:
        if row['Extra'] is None or row['Extra'] == '':
            extrarow = 'N/A'
        else:
            extrarow = row['Extra']
        newtxtfile.write(str(row['Shipdate']) + '\t' + str(row['Publisher']) + '\t' + str(row['Issue']) + '\t' + str(row['Comic']) + '\t' + str(extrarow) + '\tSkipped' + '\t' + str(cntr) + '\n')
        cntr +=1

    newtxtfile.close()


    logger.fdebug( 'attempting to populate future upcoming...' )

    mylardb = os.path.join(mylar.DATA_DIR, "mylar.db")

    connection = sqlite3.connect(str(mylardb))
    cursor = connection.cursor()

    # we should extract the issues that are being watched, but no data is available yet ('Watch For' status)
    # once we get the data, store it, wipe the existing table, retrieve the new data, populate the data into 
    # the table, recheck the series against the current watchlist and then restore the Watch For data.


    cursor.executescript('drop table if exists future;')

    cursor.execute("CREATE TABLE IF NOT EXISTS future (SHIPDATE, PUBLISHER text, ISSUE text, COMIC VARCHAR(150), EXTRA text, STATUS text, FutureID text, ComicID text);")
    connection.commit()

    csvfile = open(newfl, "rb")
    creader = csv.reader(csvfile, delimiter='\t')

    t = 1

    for row in creader:
        try:
            #print ("Row: %s" % row)
            cursor.execute("INSERT INTO future VALUES (?,?,?,?,?,?,?,null);", row)
        except Exception, e:
            logger.fdebug("Error - invald arguments...-skipping")
            pass
        t+=1
    logger.fdebug('successfully added ' + str(t) + ' issues to future upcoming table.')
    csvfile.close()
    connection.commit()
    connection.close()


    mylar.weeklypull.pullitcheck(futurepull="yes")
    #.end

def populate(link,publisher,shipdate):
    #this is the secondary url call to populate
    input = 'http://www.comicbookresources.com/' + link
    #print 'checking ' + str(input)
    response = urllib2.urlopen ( input )
    soup = BeautifulSoup (response)
    abc = soup.findAll('p')
    lenabc = len(abc)
    i=0
    resultName = []
    resultID = []
    resultURL = []
    matched = "no"
    upcome = []
    get_next = False
    prev_chk = False

    while (i < lenabc):
        titlet = abc[i] #iterate through the p pulling out only results. 
        titlet_next = titlet.findNext(text=True)
        #print ("titlet: " + str(titlet))
        if "/prev_img.php?pid" in str(titlet) and titlet_next is None:
            #solicits in 03-2014 have seperated <p> tags, so we need to take the subsequent <p>, not the initial.
            prev_chk = False
            get_next = True
            i+=1
            continue
        elif titlet_next is not None:
            #logger.fdebug('non seperated <p> tags - taking next text.')
            get_next = False
            prev_chk = True

        elif "/news/preview2.php" in str(titlet):
            prev_chk = True
            get_next = False
        elif get_next == True:
            prev_chk = True
        else:
            prev_chk = False
            get_next = False

        if prev_chk == True:
            tempName = titlet.findNext(text=True)
            if not any( [' TPB' in tempName, 'HC' in tempName, 'GN-TPB' in tempName, 'for $1' in tempName.lower(), 'subscription variant' in tempName.lower(), 'poster' in tempName.lower() ] ):
                if '#' in tempName[:50]:
                    #tempName = tempName.replace(u'.',u"'")
                    tempName = tempName.encode('ascii', 'replace')    #.decode('utf-8')
                    if '???' in tempName:
                        tempName = tempName.replace('???', ' ')
                    stissue = tempName.find('#')
                    endissue = tempName.find(' ', stissue)
                    if tempName[stissue+1] == ' ':   #if issue has space between # and number, adjust.
                        endissue = tempName.find(' ', stissue+2)
                    if endissue == -1: endissue = len(tempName)
                    issue = tempName[stissue:endissue].lstrip(' ')
                    if ':'in issue: issue = re.sub(':', '', issue).rstrip()
                    exinfo = tempName[endissue:].lstrip(' ')

                    issue1 = None
                    issue2 = None

                    if '-' in issue:
                        #print ('multiple issues detected. Splitting.')
                        ststart = issue.find('-')
                        issue1 = issue[:ststart]
                        issue2 = '#' + str(issue[ststart+1:])

                    if '&' in exinfo:
                        #print ('multiple issues detected. Splitting.')
                        ststart = exinfo.find('&')
                        issue1 = issue   # this detects fine
                        issue2 = '#' + str(exinfo[ststart+1:])
                        if '& ' in issue2: issue2 = re.sub("&\\b", "", issue2)
                        exinfo = exinfo.replace(exinfo[ststart+1:len(issue2)], '').strip()
                        if exinfo == '&': exinfo = 'N/A'

                    comic = tempName[:stissue].strip()

                    if 'for \$1' in comic:
                        exinfo = 'for $1'
                        comic = comic.replace('for \$1\:', '').lstrip()

                    issuedate = shipdate
                    if 'on sale' in str(titlet).lower():
                        onsale_start = str(titlet).lower().find('on sale') + 8
                        onsale_end = str(titlet).lower().find('<br>',onsale_start)
                        thedate = str(titlet)[onsale_start:onsale_end]
                        m = None

                        basemonths = {'january':'1','jan':'1','february':'2','feb':'2','march':'3','mar':'3','april':'4','apr':'4','may':'5','june':'6','july':'7','august':'8','aug':'8','september':'9','sept':'9','october':'10','oct':'10','november':'11','nov':'11','december':'12','dec':'12'}
                        for month in basemonths:
                            if month in thedate.lower():
                                m = basemonths[month]
                                monthname = month
                                break

                        if m is not None:
                            theday = len(month) + 1  # account for space between month & day
                            thedaystart = thedate[theday:(theday+2)].strip() # day numeric won't exceed 2
                            if len(str(thedaystart)) == 1:
                                thedaystart = '0' + str(thedaystart)
                            if len(str(m)) == 1:
                                m = '0' + str(m)
                            thedate = shipdate[-4:] + '-' + str(m) + '-' + str(thedaystart)

                        logger.info('[' + comic + '] On sale :' + str(thedate))
                        exinfo += ' [' + str(thedate) + ']'
                        issuedate = thedate
                    

                    if issue1:
                        upcome.append({
                            'Shipdate': issuedate,
                            'Publisher': publisher.upper(),
                            'Issue':   re.sub('#', '',issue1).lstrip(),
                            'Comic':   comic.upper(),
                            'Extra':   exinfo.upper()
                        })
                        #print ('Comic: ' + comic)
                        #print('issue#: ' + re.sub('#', '', issue1))
                        #print ('extra info: ' + exinfo)
                        if issue2:
                            upcome.append({
                                'Shipdate': issuedate,
                                'Publisher': publisher.upper(),
                                'Issue':   re.sub('#', '', issue2).lstrip(),
                                'Comic':   comic.upper(),
                                'Extra':   exinfo.upper()
                            })
                            #print ('Comic: ' + comic)
                            #print('issue#: ' + re.sub('#', '', issue2))
                            #print ('extra info: ' + exinfo)
                    else:          
                        upcome.append({
                            'Shipdate': issuedate,
                            'Publisher': publisher.upper(),
                            'Issue':   re.sub('#', '', issue).lstrip(),
                            'Comic':   comic.upper(),
                            'Extra':   exinfo.upper()
                        })
                        #print ('Comic: ' + comic)
                        #print ('issue#: ' + re.sub('#', '', issue))
                        #print ('extra info: ' + exinfo)
                else:
                    pass
                    #print ('no issue # to retrieve.')
        i+=1
    return upcome
    #end.

if __name__ == '__main__':
    solicit(sys.argv[1], sys.argv[2])
