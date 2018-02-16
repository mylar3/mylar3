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

import requests
from bs4 import BeautifulSoup, UnicodeDammit
import datetime
import re
import mylar
from mylar import logger, db

def locg(pulldate=None,weeknumber=None,year=None):

        todaydate = datetime.datetime.today().replace(second=0,microsecond=0)
        if pulldate:
            logger.info('pulldate is : ' + str(pulldate))
            if pulldate is None or pulldate == '00000000':
                weeknumber = todaydate.strftime("%U")
            elif '-' in pulldate:
                #find the week number            
                weektmp = datetime.date(*(int(s) for s in pulldate.split('-')))
                weeknumber = weektmp.strftime("%U")
                #we need to now make sure we default to the correct week
                weeknumber_new = todaydate.strftime("%U")
                if weeknumber_new > weeknumber:
                    weeknumber = weeknumber_new

        else:
            if str(weeknumber).isdigit() and int(weeknumber) <= 52:
                #already requesting week #
                weeknumber = weeknumber
            else:
                logger.warn('Invalid date requested. Aborting pull-list retrieval/update at this time.')
                return {'status': 'failure'}

        if year is None:
            year = todaydate.strftime("%Y")

        params = {'week': str(weeknumber),
                  'year': str(year)}

        url = 'https://walksoftly.itsaninja.party/newcomics.php'

        try:
            r = requests.get(url, params=params, verify=True, headers={'User-Agent': mylar.USER_AGENT[:mylar.USER_AGENT.find('/')+7] + mylar.USER_AGENT[mylar.USER_AGENT.find('(')+1]})
        except requests.exceptions.RequestException as e:
            logger.warn(e)
            return {'status': 'failure'}

        if r.status_code == '619':
            logger.warn('[' + str(r.status_code) + '] No date supplied, or an invalid date was provided [' + str(pulldate) + ']')
            return {'status': 'failure'}            
        elif r.status_code == '999' or r.status_code == '111':
            logger.warn('[' + str(r.status_code) + '] Unable to retrieve data from site - this is a site.specific issue [' + str(pulldate) + ']')
            return {'status': 'failure'}            

        data = r.json()

        logger.info('[WEEKLY-PULL] There are ' + str(len(data)) + ' issues for the week of ' + str(weeknumber) + ', ' + str(year))
        pull = []

        for x in data:
            pull.append({'series':     x['series'],
                         'alias':      x['alias'],
                         'issue':      x['issue'],
                         'publisher':  x['publisher'],
                         'shipdate':   x['shipdate'],
                         'coverdate':  x['coverdate'],
                         'comicid':    x['comicid'],
                         'issueid':    x['issueid'],
                         'weeknumber': x['weeknumber'],
                         'annuallink': x['link'],
                         'year':       x['year'],
                         'volume':     x['volume'],
                         'seriesyear': x['seriesyear']})
            shipdate = x['shipdate']

        myDB = db.DBConnection()

        myDB.action("CREATE TABLE IF NOT EXISTS weekly (SHIPDATE, PUBLISHER text, ISSUE text, COMIC VARCHAR(150), EXTRA text, STATUS text, ComicID text, IssueID text, CV_Last_Update text, DynamicName text, weeknumber text, year text, volume text, seriesyear text, annuallink text, rowid INTEGER PRIMARY KEY)")

        #clear out the upcoming table here so they show the new values properly.
        if pulldate == '00000000':
            logger.info('Re-creating pullist to ensure everything\'s fresh.')
            myDB.action('DELETE FROM weekly WHERE weeknumber=? AND year=?',[int(weeknumber), int(year)])

        for x in pull:
            comicid = None
            issueid = None
            comicname = x['series']
            if x['comicid'] is not None:
                comicid = x['comicid']
            if x['issueid'] is not None:
                issueid= x['issueid']
            if x['alias'] is not None:
                comicname = x['alias']

            cl_d = mylar.filechecker.FileChecker()
            cl_dyninfo = cl_d.dynamic_replace(comicname)
            dynamic_name = re.sub('[\|\s]','', cl_dyninfo['mod_seriesname'].lower()).strip()

            controlValueDict = {'DYNAMICNAME':   dynamic_name,
                                'ISSUE':   re.sub('#', '', x['issue']).strip()}
                
            newValueDict = {'SHIPDATE':    x['shipdate'],
                            'PUBLISHER':   x['publisher'],
                            'STATUS':      'Skipped',
                            'COMIC':       comicname,
                            'COMICID':     comicid,
                            'ISSUEID':     issueid,
                            'WEEKNUMBER':  x['weeknumber'],
                            'ANNUALLINK':  x['annuallink'],
                            'YEAR':        x['year'],
                            'VOLUME':      x['volume'],
                            'SERIESYEAR':  x['seriesyear']}
            myDB.upsert("weekly", newValueDict, controlValueDict)

        logger.info('[PULL-LIST] Successfully populated pull-list into Mylar for the week of: ' + str(weeknumber))
        #set the last poll date/time here so that we don't start overwriting stuff too much...
        mylar.CONFIG.PULL_REFRESH = todaydate

        return {'status':     'success',
                'count':      len(data),
                'weeknumber': weeknumber,
                'year':       year}

