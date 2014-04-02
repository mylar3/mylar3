import mylar
from mylar import logger

import requests
from bs4 import BeautifulSoup, UnicodeDammit
import re
import datetime
import sys
from decimal import Decimal
from HTMLParser import HTMLParseError
from time import strptime

def sabnzbd():
       SAB_USERNAME = mylar.SAB_USERNAME
       SAB_PASSWORD = mylar.SAB_PASSWORD
       SAB_HOST = mylar.SAB_HOST   #'http://localhost:8085/'
       if SAB_USERNAME is None or SAB_PASSWORD is None:
           logger.fdebug('No Username / Password specified for SABnzbd. Unable to auto-retrieve SAB API')
       if 'https' not in SAB_HOST:
           sabhost = re.sub('http://', '', SAB_HOST)
           sabhttp = 'http://'
       else:
           sabhost = re.sub('https://', '', SAB_HOST)
           sabhttp = 'https://'
       if not sabhost.endswith('/'):
           #sabhost = sabhost[:len(sabhost)-1].rstrip()
           sabhost = sabhost + '/'
       sabline = sabhttp + SAB_USERNAME + ':' + SAB_PASSWORD + '@' + sabhost
       r = requests.get(sabline + 'config/general/')
       soup = BeautifulSoup(r.content)
       #lenlinks = len(cntlinks)
       cnt1 = len(soup.findAll("div", {"class" : "field-pair alt"}))
       cnt2 = len(soup.findAll("div", {"class" : "field-pair"}))

       cnt = int(cnt1 + cnt2)
       n = 0
       n_even = -1
       n_odd = -1
       while ( n < cnt ):
           if n%2==0:
               n_even+=1
               resultp = soup.findAll("div", {"class" : "field-pair"})[n_even]
           else:
               n_odd+=1
               resultp = soup.findAll("div", {"class" : "field-pair alt"})[n_odd]

           if resultp.find("label", {"for" : "nzbkey"}):
               #logger.fdebug resultp
               try:
                   result = resultp.find("input", {"type" : "text"})

               except:
                   continue
               if result['id'] == "nzbkey":
                   nzbkey = result['value']             
                   logger.fdebug('found SABnzbd NZBKey: ' + str(nzbkey))
                   return nzbkey
           n+=1

#if __name__ == '__main__':
#    sabnzbd()
