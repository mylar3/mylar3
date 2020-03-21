#!/usr/bin/env python
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

import mylar
from mylar import logger

import requests
from bs4 import BeautifulSoup, UnicodeDammit
import re
import datetime
import sys
from decimal import Decimal
from time import strptime

class sabnzbd(object):

    def __init__(self, sabhost, sabusername, sabpassword):
        self.sabhost = sabhost
        self.sabusername = sabusername
        self.sabpassword = sabpassword

    def sab_get(self):
        if self.sabusername is None or self.sabpassword is None:
            logger.fdebug('No Username / Password specified for SABnzbd. Unable to auto-retrieve SAB API')
        if 'https' not in self.sabhost:
            self.sabhost = re.sub('http://', '', self.sabhost)
            sabhttp = 'http://'
        else:
            self.sabhost = re.sub('https://', '', self.sabhost)
            sabhttp = 'https://'
        if not self.sabhost.endswith('/'):
            self.sabhost = self.sabhost + '/'

        sabline = sabhttp + str(self.sabhost)
        with requests.Session() as s:
            postdata = {'username': self.sabusername,
                        'password': self.sabpassword,
                        'remember_me': 0}
            lo = s.post(sabline + 'login/', data=postdata, verify=False)

            if not lo.status_code == 200:
                return

            r = s.get(sabline + 'config/general', verify=False)

            soup = BeautifulSoup(r.content, "html.parser")
            resultp = soup.findAll("div", {"class": "field-pair"})

            for res in resultp:
                if res.find("label", {"for": "apikey"}):
                    try:
                        result = res.find("input", {"type": "text"})
                    except:
                        continue
                    if result['id'] == "apikey":
                        apikey = result['value']
                        logger.fdebug('found SABnzbd APIKey: ' + str(apikey))
                        return apikey

if __name__ == '__main__':
    test = sabnzbd()
    test.sab_get()


