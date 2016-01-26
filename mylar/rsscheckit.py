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
import threading
import mylar
from mylar import logger, rsscheck, helpers, auth32p

rss_lock = threading.Lock()


class tehMain():
    def __init__(self, forcerss=None):

        self.forcerss = forcerss

    def run(self):

        with rss_lock:

            logger.info('RSS Feed Check was last run at : ' + str(mylar.RSS_LASTRUN))
            firstrun = "no"
            #check the last run of rss to make sure it's not hammering.
            if mylar.RSS_LASTRUN is None or mylar.RSS_LASTRUN == '' or mylar.RSS_LASTRUN == '0' or self.forcerss == True:
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
            if mylar.ENABLE_TORRENT_SEARCH:
                logger.info('[RSS] Initiating Torrent RSS Check.')
                if mylar.ENABLE_KAT:
                    logger.info('[RSS] Initiating Torrent RSS Feed Check on KAT.')
                    rsscheck.torrents(pickfeed='3')
                    rsscheck.torrents(pickfeed='6')
                if mylar.ENABLE_32P:
                    logger.info('[RSS] Initiating Torrent RSS Feed Check on 32P.')
                    if mylar.MODE_32P == 0:
                        logger.fdebug('[RSS] 32P mode set to Legacy mode. Monitoring New Releases feed only.')
                        if any([mylar.PASSKEY_32P is None, mylar.PASSKEY_32P == '', mylar.RSSFEED_32P is None, mylar.RSSFEED_32P == '']):
                            logger.error('[RSS] Unable to validate information from provided RSS Feed. Verify that the feed provided is a current one.')
                        else:
                            rsscheck.torrents(pickfeed='1', feedinfo=mylar.KEYS_32P)
                    else:
                        logger.fdebug('[RSS] 32P mode set to Auth mode. Monitoring all personal notification feeds & New Releases feed')
                        if any([mylar.USERNAME_32P is None, mylar.USERNAME_32P == '', mylar.PASSWORD_32P is None]):
                            logger.error('[RSS] Unable to sign-on to 32P to validate settings. Please enter/check your username password in the configuration.')
                        else:
                            if mylar.KEYS_32P is None:
                                feed32p = auth32p.info32p()
                                feedinfo = feed32p.authenticate()
                                if feedinfo == "disable":
                                    mylar.ENABLE_32P = 0
                                    mylar.config_write()
                            else:
                                feedinfo = mylar.FEEDINFO_32P

                            if feedinfo is None or len(feedinfo) == 0 or feedinfo == "disable":
                                logger.error('[RSS] Unable to retrieve any information from 32P for RSS Feeds. Skipping for now.')
                            else:
                                rsscheck.torrents(pickfeed='1', feedinfo=feedinfo[0])
                                x = 0
                                #assign personal feeds for 32p > +8
                                for fi in feedinfo:
                                    x+=1
                                    pfeed_32p = str(7 + x)
                                    rsscheck.torrents(pickfeed=pfeed_32p, feedinfo=fi)

            logger.info('[RSS] Initiating RSS Feed Check for NZB Providers.')
            rsscheck.nzbs(forcerss=self.forcerss)
            logger.info('[RSS] RSS Feed Check/Update Complete')
            logger.info('[RSS] Watchlist Check for new Releases')
            mylar.search.searchforissue(rsscheck='yes')
            logger.info('[RSS] Watchlist Check complete.')
            if self.forcerss:
                logger.info('[RSS] Successfully ran a forced RSS Check.')
            return
