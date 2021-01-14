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
        if 'https' not in self.sabhost:
            self.sabhost = re.sub('http://', '', self.sabhost)
            sabhttp = 'http://'
        else:
            self.sabhost = re.sub('https://', '', self.sabhost)
            sabhttp = 'https://'
        if not self.sabhost.endswith('/'):
            self.sabhost = self.sabhost + '/'

        sabline = sabhttp + str(self.sabhost)

        try:
            with requests.Session() as s:
                # Note that attempting to authenticate when SABnzbd is not configured with a username and password doe not cause an error, but only attempt it if credentials are provided.
                if all([self.sabusername is not None, self.sabusername != 'None', self.sabusername != '']) and all([self.sabpassword is not None, self.sabpassword != 'None', self.sabpassword != '']):

                    postdata = {'username': self.sabusername,
                                'password': self.sabpassword,
                                'remember_me': 0}
                    lo = s.post(sabline + 'login/', data=postdata, verify=False)

                    if not bool(s.cookies.get('login_cookie')):
                        logger.fdebug('SABnzbd authentication failed - this may or may not be relevant depending on your configuration.')

                r = s.get(sabline + 'config/general', verify=False)
                soup = BeautifulSoup(r.content, "html.parser")
                find_apikey = soup.find(id=re.compile("^apikey(|_display)$")) # id="apikey" for 2.x.x and id="apikey_display" for 3.x.x
                if find_apikey is not None:
                    apikey = find_apikey['value']
                    logger.fdebug('Found SABnzbd API Key: ' + apikey)
                    return apikey

        except Exception as e:
            logger.error('Error encountered finding SABnzbd API Key: %s' % e)

if __name__ == '__main__':
    test = sabnzbd()
    test.sab_get()
