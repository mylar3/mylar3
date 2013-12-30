
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
from mylar import logger

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

    publishers = {'DC Comics':'DC Comics', 'Marvel':'Marvel Comics', 'Image':'Image Comics', 'IDW':'IDW Publishing', 'Dark Horse':'Dark Horse Comics'}

    while (mnloop < 5):
        if year == 2014:
            if len(str(month)) == 1:
                month_string = '0' + str(month)
            else:
                month_string = str(month)
            datestring = str(year) + str(month_string)
        else:
            datestring = str(month) + str(year)
        pagelinks = "http://www.comicbookresources.com/tag/solicits" + str(datestring)
        logger.info('datestring:' + datestring)
        logger.info('checking:' + pagelinks)
        pageresponse = urllib2.urlopen ( pagelinks )
        soup = BeautifulSoup (pageresponse)
        cntlinks = soup.findAll('h3')
        lenlinks = len(cntlinks)
        logger.info( str(lenlinks) + ' results' )

        publish = []
        resultURL = []

        x = 0
        cnt = 0

        while (x < lenlinks):
            headt = cntlinks[x] #iterate through the hrefs pulling out only results.
            if "/?page=article&amp;id=" in str(headt):
                #print ("titlet: " + str(headt))
                headName = headt.findNext(text=True)
                if ('Marvel' and 'DC' and 'Image' not in headName) and ('Solicitations' in headName or 'Solicits' in headName):
                    pubstart = headName.find('Solicitations')
                    for pub in publishers:
                        if pub in headName[:pubstart]:                   
                            publish.append(publishers[pub])
                            #publish.append( headName[:pubstart].strip() )
                    abc = headt.findAll('a', href=True)[0]
                    ID_som = abc['href']  #first instance will have the right link...
                    resultURL.append( ID_som )
                    #print '[ ' + publish[cnt] + '] Link URL: ' + resultURL[cnt]
                    cnt+=1
            x+=1

        #print 'cnt:' + str(cnt)

        if cnt == 0:
            break  # no results means, end it

        loopthis = (cnt-1)
        #this loops through each 'found' solicit page 
        shipdate = str(month) + '-' + str(year)
        while ( loopthis >= 0 ):
            upcoming += populate(resultURL[loopthis], publish[loopthis], shipdate)
            loopthis -=1

        month +=1  #increment month by 1
        mnloop +=1 #increment loop by 1

        if month > 12:    #failsafe failover for months
            month = 1
            year+=1

    #print upcoming
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
        #print ("titlet: " + str(titlet))
        if "/prev_img.php?pid" in str(titlet):
            #solicits in 03-2014 have seperated <p> tags, so we need to take the subsequent <p>, not the initial.
            get_next = True
            i+=1
            continue
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
            if ' TPB' not in tempName and ' HC' not in tempName and 'GN-TPB' not in tempName and 'for $1' not in tempName.lower() and 'subscription variant' not in tempName.lower():
                #print publisher + ' found upcoming'
                if '#' in tempName:
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

                    if issue1:
                        upcome.append({
                            'Shipdate': shipdate,
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
                                'Shipdate': shipdate,
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
                            'Shipdate': shipdate,
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
