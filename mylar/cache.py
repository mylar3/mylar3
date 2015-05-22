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

import os
import glob, urllib, urllib2

import lib.simplejson as simplejson

import mylar
from mylar import db, helpers, logger


class Cache(object):
    """
    This class deals with getting, storing and serving up artwork (album
    art, artist images, etc) and info/descriptions (album info, artist descrptions)
    to and from the cache folder. This can be called from within a web interface,
    for example, using the helper functions getInfo(id) and getArtwork(id), to utilize the cached
    images rather than having to retrieve them every time the page is reloaded.

    So you can call cache.getArtwork(id) which will return an absolute path
    to the image file on the local machine, or if the cache directory
    doesn't exist, or can not be written to, it will return a url to the image.

    Call cache.getInfo(id) to grab the artist/album info; will return the text description

    The basic format for art in the cache is <musicbrainzid>.<date>.<ext>
    and for info it is <musicbrainzid>.<date>.txt
    """
    mylar.CACHE_DIR = os.path.join(str(mylar.PROG_DIR), 'cache/')

    path_to_art_cache = os.path.join(mylar.CACHE_DIR, 'artwork')

    id = None
    id_type = None  # 'comic' or 'issue' - set automatically depending on whether ComicID or IssueID is passed
    query_type = None  # 'artwork','thumb' or 'info' - set automatically

    artwork_files = []
    thumb_files = []

    artwork_errors = False
    artwork_url = None

    thumb_errors = False
    thumb_url = None

    def __init__(self):

        pass

    def _exists(self, type):

        self.artwork_files = glob.glob(os.path.join(self.path_to_art_cache, self.id + '*'))
        self.thumb_files = glob.glob(os.path.join(self.path_to_art_cache, 'T_' + self.id + '*'))

        if type == 'artwork':

            if self.artwork_files:
                return True
            else:
                return False

        elif type == 'thumb':

            if self.thumb_files:
                return True
            else:
                return False

    def _get_age(self, date):
        # There's probably a better way to do this
        split_date = date.split('-')
        days_old = int(split_date[0]) *365 + int(split_date[1]) *30 + int(split_date[2])

        return days_old


    def _is_current(self, filename=None, date=None):

        if filename:
            base_filename = os.path.basename(filename)
            date = base_filename.split('.')[1]

        # Calculate how old the cached file is based on todays date & file date stamp
        # helpers.today() returns todays date in yyyy-mm-dd format
        if self._get_age(helpers.today()) - self._get_age(date) < 30:
            return True
        else:
            return False

    def get_artwork_from_cache(self, ComicID=None, imageURL=None):
        '''
        Pass a comicvine id to this function (either ComicID or IssueID)
        '''

        self.query_type = 'artwork'

        if ComicID:
            self.id = ComicID
            self.id_type = 'comic'
        else:
            self.id = IssueID
            self.id_type = 'issue'

        if self._exists('artwork') and self._is_current(filename=self.artwork_files[0]):
            return self.artwork_files[0]
        else:
            # we already have the image for the comic in the sql db. Simply retrieve it, and save it.
            image_url = imageURL
            logger.debug('Retrieving comic image from: ' + image_url)
            try:
                artwork = urllib2.urlopen(image_url, timeout=20).read()
            except Exception, e:
                logger.error('Unable to open url "' + image_url + '". Error: ' + str(e))
                artwork = None

            if artwork:

                # Make sure the artwork dir exists:
                if not os.path.isdir(self.path_to_art_cache):
                    try:
                        os.makedirs(self.path_to_art_cache)
                    except Exception, e:
                        logger.error('Unable to create artwork cache dir. Error: ' + str(e))
                        self.artwork_errors = True
                        self.artwork_url = image_url
                #Delete the old stuff
                for artwork_file in self.artwork_files:
                    try:
                        os.remove(artwork_file)
                    except:
                        logger.error('Error deleting file from the cache: ' + artwork_file)

                ext = os.path.splitext(image_url)[1]

                artwork_path = os.path.join(self.path_to_art_cache, self.id + '.' + helpers.today() + ext)
                try:
                    f = open(artwork_path, 'wb')
                    f.write(artwork)
                    f.close()
                except Exception, e:
                    logger.error('Unable to write to the cache dir: ' + str(e))
                    self.artwork_errors = True
                    self.artwork_url = image_url


def getArtwork(ComicID=None, imageURL=None):

    c = Cache()
    artwork_path = c.get_artwork_from_cache(ComicID, imageURL)
    logger.info('artwork path at : ' + str(artwork_path))
    if not artwork_path:
        return None

    if artwork_path.startswith('http://'):
        return artwork_path
    else:
        artwork_file = os.path.basename(artwork_path)
        return "cache/artwork/" + artwork_file
