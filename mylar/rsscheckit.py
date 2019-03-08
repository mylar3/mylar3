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
    def __init__(self):
        pass 

    def run(self, forcerss=None):
        with rss_lock:

            #logger.info('[RSS-FEEDS] RSS Feed Check was last run at : ' + str(mylar.SCHED_RSS_LAST))
            firstrun = "no"
            #check the last run of rss to make sure it's not hammering.
            if mylar.SCHED_RSS_LAST is None or mylar.SCHED_RSS_LAST == '' or mylar.SCHED_RSS_LAST == '0' or forcerss == True:
                logger.info('[RSS-FEEDS] RSS Feed Check Initalizing....')
                firstrun = "yes"
                duration_diff = 0
            else:
                tstamp = float(mylar.SCHED_RSS_LAST)
                duration_diff = abs(helpers.utctimestamp() - tstamp)/60
            #logger.fdebug('[RSS-FEEDS] Duration diff: %s' % duration_diff)
            if firstrun == "no" and duration_diff < int(mylar.CONFIG.RSS_CHECKINTERVAL):
                logger.fdebug('[RSS-FEEDS] RSS Check has taken place less than the threshold - not initiating at this time.')
                return

            helpers.job_management(write=True, job='RSS Feeds', current_run=helpers.utctimestamp(), status='Running')
            mylar.RSS_STATUS = 'Running'
            #logger.fdebug('[RSS-FEEDS] Updated RSS Run time to : ' + str(mylar.SCHED_RSS_LAST))

            #function for looping through nzbs/torrent feeds
            if mylar.CONFIG.ENABLE_TORRENT_SEARCH:
                logger.info('[RSS-FEEDS] Initiating Torrent RSS Check.')
                if mylar.CONFIG.ENABLE_PUBLIC:
                    logger.info('[RSS-FEEDS] Initiating Torrent RSS Feed Check on Demonoid / WorldWideTorrents.')
                    rsscheck.torrents(pickfeed='Public')    #TPSE = DEM RSS Check + WWT RSS Check
                if mylar.CONFIG.ENABLE_32P is True:
                    logger.info('[RSS-FEEDS] Initiating Torrent RSS Feed Check on 32P.')
                    if mylar.CONFIG.MODE_32P is False:
                        logger.fdebug('[RSS-FEEDS] 32P mode set to Legacy mode. Monitoring New Releases feed only.')
                        if any([mylar.CONFIG.PASSKEY_32P is None, mylar.CONFIG.PASSKEY_32P == '', mylar.CONFIG.RSSFEED_32P is None, mylar.CONFIG.RSSFEED_32P == '']):
                            logger.error('[RSS-FEEDS] Unable to validate information from provided RSS Feed. Verify that the feed provided is a current one.')
                        else:
                            rsscheck.torrents(pickfeed='1', feedinfo=mylar.KEYS_32P)
                    else:
                        logger.fdebug('[RSS-FEEDS] 32P mode set to Auth mode. Monitoring all personal notification feeds & New Releases feed')
                        if any([mylar.CONFIG.USERNAME_32P is None, mylar.CONFIG.USERNAME_32P == '', mylar.CONFIG.PASSWORD_32P is None]):
                            logger.error('[RSS-FEEDS] Unable to sign-on to 32P to validate settings. Please enter/check your username password in the configuration.')
                        else:
                            if mylar.KEYS_32P is None:
                                feed32p = auth32p.info32p()
                                feedinfo = feed32p.authenticate()
                                if feedinfo != "disable":
                                    pass
                                else:
                                    helpers.disable_provider('32P')
                            else:
                                feedinfo = mylar.FEEDINFO_32P

                            if feedinfo is None or len(feedinfo) == 0 or feedinfo == "disable":
                                logger.error('[RSS-FEEDS] Unable to retrieve any information from 32P for RSS Feeds. Skipping for now.')
                            else:
                                rsscheck.torrents(pickfeed='1', feedinfo=feedinfo[0])
                                x = 0
                                #assign personal feeds for 32p > +8
                                for fi in feedinfo:
                                    x+=1
                                    pfeed_32p = str(7 + x)
                                    rsscheck.torrents(pickfeed=pfeed_32p, feedinfo=fi)

            logger.info('[RSS-FEEDS] Initiating RSS Feed Check for NZB Providers.')
            rsscheck.nzbs(forcerss=forcerss)
            if mylar.CONFIG.ENABLE_DDL is True:
                logger.info('[RSS-FEEDS] Initiating RSS Feed Check for DDL Provider.')
                rsscheck.ddl(forcerss=forcerss)
            logger.info('[RSS-FEEDS] RSS Feed Check/Update Complete')
            logger.info('[RSS-FEEDS] Watchlist Check for new Releases')
            mylar.search.searchforissue(rsscheck='yes')
            logger.info('[RSS-FEEDS] Watchlist Check complete.')
            if forcerss:
                logger.info('[RSS-FEEDS] Successfully ran a forced RSS Check.')
            helpers.job_management(write=True, job='RSS Feeds', last_run_completed=helpers.utctimestamp(), status='Waiting')
            mylar.RSS_STATUS = 'Waiting'
            return True
