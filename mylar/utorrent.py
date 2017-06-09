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

import re
import os
import requests
import bencode
import hashlib
import StringIO

import mylar
from mylar import logger

class utorrentclient(object):

    def __init__(self):

        host = mylar.UTORRENT_HOST   #has to be in the format of URL:PORT
        if not host.startswith('http'):
            host = 'http://' + host

        if host.endswith('/'):
            host = host[:-1]

        if host.endswith('/gui'):
            host = host[:-4]

        self.base_url = host
        self.username = mylar.UTORRENT_USERNAME
        self.password = mylar.UTORRENT_PASSWORD
        self.utorrent_url = '%s/gui/' % (self.base_url)
        self.auth = requests.auth.HTTPBasicAuth(self.username, self.password)
        self.token, self.cookies = self._get_token()

    def _get_token(self):
        TOKEN_REGEX = r'<div[^>]*id=[\"\']token[\"\'][^>]*>([^<]*)</div>'
        utorrent_url_token = '%stoken.html' % self.utorrent_url
        try:
            r = requests.get(utorrent_url_token, auth=self.auth)
        except requests.exceptions.RequestException as err:
            logger.debug('URL: ' + str(utorrent_url_token))
            logger.debug('Error getting Token. uTorrent responded with error: ' + str(err))
            return 'fail'

        token = re.search(TOKEN_REGEX, r.text).group(1)
        guid = r.cookies['GUID']
        cookies = dict(GUID = guid)
        return token, cookies

    def addfile(self, filepath=None, filename=None, bytes=None):
        params = {'action': 'add-file', 'token': self.token}
        try:
            d = open(filepath, 'rb')
            tordata = d.read()
            d.close()
        except:
            logger.warn('Unable to load torrent file. Aborting at this time.')
            return 'fail'

        files = {'torrent_file': tordata}
        try:
            r = requests.post(url=self.utorrent_url, auth=self.auth, cookies=self.cookies, params=params, files=files)
        except requests.exceptions.RequestException as err:
            logger.debug('URL: ' + str(self.utorrent_url))
            logger.debug('Error sending to uTorrent Client. uTorrent responded with error: ' + str(err))
            return 'fail'


        # (to-do) verify the hash in order to ensure it's loaded here
        if str(r.status_code) == '200':
            logger.info('Successfully added torrent to uTorrent client.')
            hash = self.calculate_torrent_hash(data=tordata)
            if mylar.UTORRENT_LABEL:
                try:
                    self.setlabel(hash)
                except:
                    logger.warn('Unable to set label for torrent.')
            return hash
        else:
            return 'fail'

    def addurl(self, url):
        params = {'action': 'add-url', 'token': self.token, 's': url}
        try:
            r = requests.post(url=self.utorrent_url, auth=self.auth, cookies=self.cookies, params=params)
        except requests.exceptions.RequestException as err:
            logger.debug('URL: ' + str(self.utorrent_url))
            logger.debug('Error sending to uTorrent Client. uTorrent responded with error: ' + str(err))
            return 'fail'

        # (to-do) verify the hash in order to ensure it's loaded here
        if str(r.status_code) == '200':
            logger.info('Successfully added torrent to uTorrent client.')
            hash = self.calculate_torrent_hash(link=url)
            if mylar.UTORRENT_LABEL:
                try:
                    self.setlabel(hash)
                except:
                    logger.warn('Unable to set label for torrent.')
            return hash
        else:
            return 'fail'


    def setlabel(self, hash):
        params = {'token': self.token, 'action': 'setprops', 'hash': hash, 's': 'label', 'v': str(mylar.UTORRENT_LABEL)}
        r = requests.post(url=self.utorrent_url, auth=self.auth, cookies=self.cookies, params=params)
        if str(r.status_code) == '200':
            logger.info('label ' + str(mylar.UTORRENT_LABEL) + ' successfully applied')
        else:
            logger.info('Unable to label torrent')
        return

    def calculate_torrent_hash(self, link=None, filepath=None, data=None):
        thehash = None
        if link is None:
            if filepath:
                torrent_file = open(filepath, "rb")
                metainfo = bencode.decode(torrent_file.read())
            else:
                metainfo = bencode.decode(data)
            info = metainfo['info']
            thehash = hashlib.sha1(bencode.encode(info)).hexdigest().upper()
            logger.info('Hash: ' + thehash)
        else:
            if link.startswith("magnet:"):
                torrent_hash = re.findall("urn:btih:([\w]{32,40})", link)[0]
                if len(torrent_hash) == 32:
                    torrent_hash = b16encode(b32decode(torrent_hash)).lower()
                thehash = torrent_hash.upper()

        if thehash is None:
            logger.warn('Cannot calculate torrent hash without magnet link or data')

        return thehash

# not implemented yet #
#    def load_torrent(self, filepath):
#        start = bool(mylar.UTORRENT_STARTONLOAD)

#        logger.info('filepath to torrent file set to : ' + filepath)
#
#        torrent = self.addfile(filepath, verify_load=True)
         #torrent should return the hash if it's valid and loaded (verify_load checks)
#        if not torrent:
#            return False

#        if mylar.UTORRENT_LABEL:
#            self.setlabel(torrent)
#            logger.info('Setting label for torrent to : ' + mylar.UTORRENT_LABEL)

#        logger.info('Successfully loaded torrent.')

#        #note that if set_directory is enabled, the torrent has to be started AFTER it's loaded or else it will give chunk errors and not seed
#        if start:
#            logger.info('[' + str(start) + '] Now starting torrent.')
#            torrent.start()
#        else:
#            logger.info('[' + str(start) + '] Not starting torrent due to configuration setting.')
#        return True
