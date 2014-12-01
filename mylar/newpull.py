
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

def newpull():
        pagelinks = "http://www.previewsworld.com/Home/1/1/71/952"

        pageresponse = urllib2.urlopen ( pagelinks )
        soup = BeautifulSoup (pageresponse)
        getthedate = soup.findAll("div", {"class": "Headline"})[0]
        #the date will be in the FIRST ahref
        getdate_link = getthedate('a')[0]
        newdates = getdate_link.findNext(text=True).strip()
        logger.fdebug('New Releases date detected as : ' + re.sub('New Releases For', '', newdates).strip())
        cntlinks = soup.findAll('tr')
        lenlinks = len(cntlinks)

        publish = []
        resultURL = []
        resultmonth = []
        resultyear = []

        x = 0
        cnt = 0
        endthis = False
        pull_list = []

        publishers = {'914':'DARK HORSE COMICS', '915':'DC COMICS', '916':'IDW PUBLISHING', '917':'IMAGE COMICS', '918':'MARVEL COMICS', '952':'COMICS & GRAPHIC NOVELS'}

        while (x < lenlinks):
            headt = cntlinks[x] #iterate through the hrefs pulling out only results.
            if '?stockItemID=' in str(headt):
                #914 - Dark Horse Comics
                #915 - DC Comics
                #916 - IDW Publishing
                #917 - Image Comics
                #918 - Marvel Comics
                #952 - Comics & Graphic Novels
                #    - Magazines
                #print ("titlet: " + str(headt))
                findurl_link = headt.findAll('a', href=True)[0]
                urlID = findurl_link.findNext(text=True)
                issue_link = findurl_link['href']
                issue_lk = issue_link.find('?stockItemID=')
                if issue_lk == -1:
                    continue
                #headName = headt.findNext(text=True)
                publisher_id = issue_link[issue_lk-3:issue_lk] 
                for pub in publishers:
                    if pub == publisher_id:
                        isspublisher = publishers[pub]
                        #logger.fdebug('publisher:' + str(isspublisher))
                        found_iss = headt.findAll('td')
                        if "Home/1/1/71/920" in issue_link:
                            logger.fdebug('Ignoring - menu option.')
                            return
                        if "PREVIEWS" in headt:
                            logger.fdebug('Ignoring: ' + found_iss[0])
                            break
                        if "MAGAZINES" in headt:
                            logger.fdebug('End.')
                            endthis = True
                            break
                        if len(found_iss) > 0:
                            pull_list.append({"iss_url":   found_iss[0],
                                              "name":      found_iss[1].findNext(text=True),
                                              "price":     found_iss[2],
                                              "publisher": isspublisher,
                                              "ID"       : urlID})                       

                if endthis == True: break
            x+=1

        logger.fdebug('Saving new pull-list information into local file for subsequent merge')
        except_file = os.path.join(mylar.CACHE_DIR, 'newreleases.txt')
        try:
            csvfile = open(str(except_file), 'rb')
            csvfile.close()
        except (OSError,IOError):
            logger.fdebug('file does not exist - continuing.')
        else:
            logger.fdebug('file exists - removing.')
            os.remove(except_file)

        oldpub = None
        breakhtml = {"<td>", "<tr>", "</td>", "</tr>"}
        with open(str(except_file), 'wb') as f:
            f.write('%s\n' % (newdates))
            for pl in pull_list:
                if pl['publisher'] == oldpub:
                    exceptln = str(pl['ID']) + "\t" + str(pl['name']) + "\t" + str(pl['price'])
                else:
                    exceptln = pl['publisher']

                for lb in breakhtml:
                    exceptln = re.sub(lb,'', exceptln).strip()

                exceptline = exceptln.decode('utf-8','ignore')
                f.write('%s\n' % (exceptline.encode('ascii','replace').strip()))
                oldpub = pl['publisher']


if __name__ == '__main__':
    newpull()
