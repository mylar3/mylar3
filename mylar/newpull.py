
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
import lib.requests as requests

import mylar
from mylar import logger

def newpull():
        pagelinks = "http://www.previewsworld.com/Home/1/1/71/952"

        try:
            r = requests.get(pagelinks, verify=False)

        except Exception, e:
            logger.warn('Error fetching data: %s' % (tmpprov, e))

        soup = BeautifulSoup(r.content)
        getthedate = soup.findAll("div", {"class": "Headline"})[0]

        #the date will be in the FIRST ahref
        try:
            getdate_link = getthedate('a')[0]
            newdates = getdate_link.findNext(text=True).strip()
        except IndexError:
            newdates = getthedate.findNext(text=True).strip()
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

        publishers = {'PREVIEWS PUBLICATIONS', 'DARK HORSE COMICS', 'DC COMICS', 'IDW PUBLISHING', 'IMAGE COMICS', 'MARVEL COMICS', 'COMICS & GRAPHIC NOVELS'}
        isspublisher = None

        while (x < lenlinks):
            headt = cntlinks[x] #iterate through the hrefs pulling out only results.
            found_iss = headt.findAll('td')
            pubcheck = found_iss[0].text.strip() #.findNext(text=True)
            for pub in publishers:
                if pub in pubcheck:
                    chklink = found_iss[0].findAll('a', href=True)  #make sure it doesn't have a link in it.
                    if not chklink:
                        isspublisher = pub
                        break
                    
            if isspublisher == 'PREVIEWS PUBLICATIONS' or isspublisher is None:
                pass

            else:
                if '/Catalog/' in str(headt):
                    findurl_link = headt.findAll('a', href=True)[0]
                    urlID = findurl_link.findNext(text=True)
                    issue_link = findurl_link['href']
                    issue_lk = issue_link.find('/Catalog/')
                    if issue_lk == -1:
                        x+=1
                        continue
                    elif "Home/1/1/71" in issue_link:
                        #logger.fdebug('Ignoring - menu option.')
                        x+=1
                        continue

                    if len(found_iss) > 0:
                        pull_list.append({"iss_url":   issue_link,
                                          "name":      found_iss[1].findNext(text=True),
                                          "price":     found_iss[2],
                                          "publisher": isspublisher,
                                          "ID": urlID})

                if "PREVIEWS" in headt:
                    #logger.fdebug('Ignoring: ' + found_iss[0])
                    break
                if "MAGAZINES" in headt:
                    #logger.fdebug('End.')
                    endthis = True
                    break

            x+=1

        logger.fdebug('Saving new pull-list information into local file for subsequent merge')
        except_file = os.path.join(mylar.CACHE_DIR, 'newreleases.txt')
        try:
            csvfile = open(str(except_file), 'rb')
            csvfile.close()
        except (OSError, IOError):
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
                    exceptln = str(pl['ID']) + "\t" + pl['name'].replace(u"\xA0", u" ") + "\t" + str(pl['price'])
                else:
                    exceptln = pl['publisher'] + "\n" + str(pl['ID']) + "\t" + pl['name'].replace(u"\xA0", u" ") + "\t" + str(pl['price'])

                for lb in breakhtml:
                    exceptln = re.sub(lb, '', exceptln).strip()

                exceptline = exceptln.decode('utf-8', 'ignore')
                f.write('%s\n' % (exceptline.encode('ascii', 'replace').strip()))
                oldpub = pl['publisher']


if __name__ == '__main__':
    newpull()
