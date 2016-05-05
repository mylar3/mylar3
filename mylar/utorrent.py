#  This file is part of Mylar and is adapted from Headphones.

import hashlib
import urllib
import json
import time
from collections import namedtuple
import urllib2
import urlparse
import cookielib

import re
import os
import mylar
from mylar import logger
from bencode import bencode, bdecode
from hashlib import sha1


class utorrentclient(object):
    TOKEN_REGEX = "<div id='token' style='display:none;'>([^<>]+)</div>"
    UTSetting = namedtuple("UTSetting", ["name", "int", "str", "access"])

    def __init__(self, base_url=None, username=None, password=None, ):

        host = mylar.UTORRENT_HOST
        if not host.startswith('http'):
            host = 'http://' + host

        if host.endswith('/'):
            host = host[:-1]

        if host.endswith('/gui'):
            host = host[:-4]

        self.base_url = host
        self.username = mylar.UTORRENT_USERNAME
        self.password = mylar.UTORRENT_PASSWORD
        self.opener = self._make_opener('uTorrent', self.base_url, self.username, self.password)
        self.token = self._get_token()
        # TODO refresh token, when necessary

    def _make_opener(self, realm, base_url, username, password):
        """uTorrent API need HTTP Basic Auth and cookie support for token verify."""
        auth = urllib2.HTTPBasicAuthHandler()
        auth.add_password(realm=realm, uri=base_url, user=username, passwd=password)
        opener = urllib2.build_opener(auth)
        urllib2.install_opener(opener)

        cookie_jar = cookielib.CookieJar()
        cookie_handler = urllib2.HTTPCookieProcessor(cookie_jar)

        handlers = [auth, cookie_handler]
        opener = urllib2.build_opener(*handlers)
        return opener

    def _get_token(self):
        url = urlparse.urljoin(self.base_url, 'gui/token.html')
        try:
            response = self.opener.open(url)
        except urllib2.HTTPError as err:
            logger.debug('URL: ' + str(url))
            logger.debug('Error getting Token. uTorrent responded with error: ' + str(err))
            return
        match = re.search(utorrentclient.TOKEN_REGEX, response.read())
        return match.group(1)

    def list(self, **kwargs):
        params = [('list', '1')]
        params += kwargs.items()
        return self._action(params)

    def add_url(self, url):
        # can receive magnet or normal .torrent link
        params = [('action', 'add-url'), ('s', url)]
        return self._action(params)

    def start(self, *hashes):
        params = [('action', 'start'), ]
        for hash in hashes:
            params.append(('hash', hash))
        return self._action(params)

    def stop(self, *hashes):
        params = [('action', 'stop'), ]
        for hash in hashes:
            params.append(('hash', hash))
        return self._action(params)

    def pause(self, *hashes):
        params = [('action', 'pause'), ]
        for hash in hashes:
            params.append(('hash', hash))
        return self._action(params)

    def forcestart(self, *hashes):
        params = [('action', 'forcestart'), ]
        for hash in hashes:
            params.append(('hash', hash))
        return self._action(params)

    def getfiles(self, hash):
        params = [('action', 'getfiles'), ('hash', hash)]
        return self._action(params)

    def getprops(self, hash):
        params = [('action', 'getprops'), ('hash', hash)]
        return self._action(params)

    def setprops(self, hash, s, val):
        params = [('action', 'setprops'), ('hash', hash), ("s", s), ("v", val)]
        logger.debug('Params: ' + str(params))
        return self._action(params)

    def setprio(self, hash, priority, *files):
        params = [('action', 'setprio'), ('hash', hash), ('p', str(priority))]
        for file_index in files:
            params.append(('f', str(file_index)))

        return self._action(params)

    def get_settings(self, key=None):
        params = [('action', 'getsettings'), ]
        status, value = self._action(params)
        settings = {}
        for args in value['settings']:
            settings[args[0]] = self.UTSetting(*args)
        if key:
            return settings[key]
        return settings

    def remove(self, hash, remove_data=False):
        if remove_data:
            params = [('action', 'removedata'), ('hash', hash)]
        else:
            params = [('action', 'remove'), ('hash', hash)]
        return self._action(params)

    def _action(self, params, body=None, content_type=None):

        if not self.token:
            return

        url = self.base_url + '/gui/' + '?token=' + self.token + '&' + urllib.urlencode(params)
        request = urllib2.Request(url)

        if body:
            request.add_data(body)
            request.add_header('Content-length', len(body))
        if content_type:
            request.add_header('Content-type', content_type)

        try:
            response = self.opener.open(request)
            return response.code, json.loads(response.read())
        except urllib2.HTTPError as err:
            logger.debug('URL: ' + str(url))
            logger.debug('uTorrent webUI raised the following error: ' + str(err))


def labelTorrent(hash):
    label = mylar.UTORRENT_LABEL
    uTorrentClient = utorrentclient()
    if label:
        uTorrentClient.setprops(hash, 'label', str(label))


def removeTorrent(hash, remove_data=False):
    uTorrentClient = utorrentclient()
    status, torrentList = uTorrentClient.list()
    torrents = torrentList['torrents']
    for torrent in torrents:
        if torrent[0].upper() == hash.upper():
            if torrent[21] == 'Finished':
                logger.info('%s has finished seeding, removing torrent and data' % torrent[2])
                uTorrentClient.remove(hash, remove_data)
                return True
            else:
                logger.info(
                    '%s has not finished seeding yet, torrent will not be removed, will try again on next run' %
                    torrent[2])
                return False
    return False


def setSeedRatio(hash, ratio):
    uTorrentClient = utorrentclient()
    uTorrentClient.setprops(hash, 'seed_override', '1')
    if ratio != 0:
        uTorrentClient.setprops(hash, 'seed_ratio', ratio * 10)
    else:
        # TODO passing -1 should be unlimited
        uTorrentClient.setprops(hash, 'seed_ratio', -10)

def addTorrent(link):
    uTorrentClient = utorrentclient()
    uTorrentClient.add_url(link)


def calculate_torrent_hash(link, data=None):
    """
    Calculate the torrent hash from a magnet link or data. Raises a ValueError
    when it cannot create a torrent hash given the input data.
    """

    if link.startswith("magnet:"):
        torrent_hash = re.findall("urn:btih:([\w]{32,40})", link)[0]
        if len(torrent_hash) == 32:
            torrent_hash = b16encode(b32decode(torrent_hash)).lower()
    elif data:
        info = bdecode(data)["info"]
        torrent_hash = sha1(bencode(info)).hexdigest()
    else:
        raise ValueError("Cannot calculate torrent hash without magnet link " \
                         "or data")
    logger.debug("Torrent hash: " + torrent_hash)
    return torrent_hash.upper()
    