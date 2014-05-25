# This file is part of Mylar.
#
# Mylar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mylar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement

import datetime

import mylar

from mylar import logger, rsscheck, helpers

#import threading

class tehMain():
    def __init__(self, forcerss=None):

        self.forcerss = forcerss

    def run(self):
        forcerss = self.forcerss
        logger.info('RSS Feed Check was last run at : ' + str(mylar.RSS_LASTRUN))
        firstrun = "no"
        #check the last run of rss to make sure it's not hammering.
        if mylar.RSS_LASTRUN is None or mylar.RSS_LASTRUN == '' or mylar.RSS_LASTRUN == '0' or forcerss == True:
            logger.info('RSS Feed Check First Ever Run.')
            firstrun = "yes"
            mins = 0
        else:
            c_obj_date = datetime.datetime.strptime(mylar.RSS_LASTRUN, "%Y-%m-%d %H:%M:%S")
            n_date = datetime.datetime.now()
            absdiff = abs(n_date - c_obj_date)
            mins = (absdiff.days * 24 * 60 * 60 + absdiff.seconds) / 60.0  #3600 is for hours.

        if firstrun == "no" and mins < int(mylar.RSS_CHECKINTERVAL):
            logger.fdebug('RSS Check has taken place less than the threshold - not initiating at this time.')
            return

        mylar.RSS_LASTRUN = helpers.now()
        logger.fdebug('Updating RSS Run time to : ' + str(mylar.RSS_LASTRUN))
        mylar.config_write()

        #function for looping through nzbs/torrent feeds
        if mylar.ENABLE_TORRENTS:
            logger.fdebug('[RSS] Initiating Torrent RSS Check.')
            if mylar.ENABLE_KAT:
                logger.fdebug('[RSS] Initiating Torrent RSS Feed Check on KAT.')
                rsscheck.torrents(pickfeed='3')
                rsscheck.torrents(pickfeed='6')
            if mylar.ENABLE_CBT:
                logger.fdebug('[RSS] Initiating Torrent RSS Feed Check on CBT.')
                rsscheck.torrents(pickfeed='1')
                rsscheck.torrents(pickfeed='4')
        logger.fdebug('[RSS] Initiating RSS Feed Check for NZB Providers.')
        rsscheck.nzbs()
        logger.fdebug('[RSS] RSS Feed Check/Update Complete')
        logger.fdebug('[RSS] Watchlist Check for new Releases')
        mylar.search.searchforissue(rsscheck='yes')
        logger.fdebug('[RSS] Watchlist Check complete.')
        return
