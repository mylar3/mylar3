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

import json
import os
import re
import datetime
import threading

import mylar
from mylar import db, filechecker, helpers, logger, updater

class metadata_Series(object):

    def __init__(self, comicidlist, bulk=False, api=False, refreshSeries=False):
        self.comiclist = comicidlist
        if not type(comicidlist) is list:
            self.comiclist = [comicidlist]

        self.bulk = bulk
        self.api = api
        self.refreshSeries = refreshSeries

    def update_metadata_thread(self):
        threading.Thread(target=self.update_metadata).start()

    def update_metadata(self):
        for cid in self.comiclist:

            if self.refreshSeries is True:
                updater.dbupdate(cid, calledfrom='json_api')

            myDB = db.DBConnection()
            comic = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [cid]).fetchone()

            if comic:

                description_load = None
                if not os.path.exists(comic['ComicLocation']) and mylar.CONFIG.CREATE_FOLDERS is True:
                    try:
                        checkdirectory = filechecker.validateAndCreateDirectory(comic['ComicLocation'], True)
                    except Exception as e:
                        logger.warn('[%s] Unable to create series directory @ %s. Aborting updating of series.json' % (e, comic['ComicLocation']))
                        continue
                    else:
                        if checkdirectory is False:
                            logger.warn('Unable to create series directory @ %s. Aborting updating of series.json' % (comic['ComicLocation']))
                            continue

                if os.path.exists(os.path.join(comic['ComicLocation'], 'series.json')):
                    try:
                        with open(os.path.join(comic['ComicLocation'], 'series.json')) as j_file:
                            metainfo = json.load(j_file)
                            logger.fdebug('metainfo_loaded: %s' % (metainfo,))
                        try:
                            # series.json version 1.0.1
                            description_load = metainfo['metadata']['description_text']
                        except Exception as e:
                            try:
                                # series.json version 1.0
                                description_load = metainfo['metadata'][0]['description_text']
                            except Exception as e:
                                description_load = metainfo['metadata'][0]['description']
                    except Exception as e:
                        try:
                            description_load = metainfo['metadata']['description_formatted']
                        except Exception as e:
                            try:
                                description_load = metainfo['metadata'][0]['description_formatted']
                            except Exception as e:
                                logger.info('No description found in metadata. Reloading from dB if available.[error: %s]' % e)

                c_date = datetime.date(int(comic['LatestDate'][:4]), int(comic['LatestDate'][5:7]), 1)
                n_date = datetime.date.today()
                recentchk = (n_date - c_date).days
                if comic['NewPublish'] is True:
                    seriesStatus = 'Continuing'
                else:
                    #do this just incase and as an extra measure of accuracy hopefully.
                     if recentchk < 55:
                         seriesStatus = 'Continuing'
                     else:
                         seriesStatus = 'Ended'

                clean_issue_list = None
                if comic['Collects'] != 'None':
                    clean_issue_list = comic['Collects']

                if mylar.CONFIG.SERIESJSON_FILE_PRIORITY is True:
                    if description_load is not None:
                        cdes_removed = re.sub(r'\n', '', description_load).strip()
                        cdes_formatted = description_load
                    elif comic['DescriptionEdit'] is not None:
                        cdes_removed = re.sub(r'\n', ' ', comic['DescriptionEdit']).strip()
                        cdes_formatted = comic['DescriptionEdit']
                    else:
                        if comic['Description'] is not None:
                            cdes_removed = re.sub(r'\n', '', comic['Description']).strip()
                        else:
                            cdes_removed = comic['Description']
                            logger.warn('Series does not have a description. Not populating, but you might need to do a Refresh Series to fix this')
                        cdes_formatted = comic['Description']
                else:
                    if comic['DescriptionEdit'] is not None:
                        cdes_removed = re.sub(r'\n', ' ', comic['DescriptionEdit']).strip()
                        cdes_formatted = comic['DescriptionEdit']
                    elif description_load is not None:
                        cdes_removed = re.sub(r'\n', '', description_load).strip()
                        cdes_formatted = description_load
                    else:
                        if comic['Description'] is not None:
                            cdes_removed = re.sub(r'\n', '', comic['Description']).strip()
                        else:
                            cdes_removed = comic['Description']
                            logger.warn('Series does not have a description. Not populating, but you might need to do a Refresh Series to fix this')
                        cdes_formatted = comic['Description']

                comicVol = comic['ComicVersion']
                if all([mylar.CONFIG.SETDEFAULTVOLUME is True, comicVol is None]):
                    comicVol = 1
                if comicVol is not None:
                    if comicVol.isdigit():
                        comicVol = int(comicVol)
                        logger.info('Updated version to :' + str(comicVol))
                        if all([mylar.CONFIG.SETDEFAULTVOLUME is False, comicVol == 'v1']):
                           comicVol = None
                    else:
                        comicVol = int(re.sub('[^0-9]', '', comicVol).strip())
                else:
                    if mylar.CONFIG.SETDEFAULTVOLUME is True:
                        comicVol = 1

                if any([comic['ComicYear'] is None, comic['ComicYear'] == '0000', comic['ComicYear'][-1:] == '-']):
                    SeriesYear = int(issued['firstdate'][:4])
                else:
                    SeriesYear = int(comic['ComicYear'])

                csyear = comic['Corrected_SeriesYear']

                if any([SeriesYear > int(datetime.datetime.now().year) + 1, SeriesYear == 2099]) and csyear is not None:
                    logger.info('Corrected year of ' + str(SeriesYear) + ' to corrected year for series that was manually entered previously of ' + str(csyear))
                    SeriesYear = int(csyear)

                if all([int(comic['Total']) == 1, SeriesYear < int(helpers.today()[:4]), comic['Type'] != 'One-Shot', comic['Type'] != 'TPB']):
                    logger.info('Determined to be a one-shot issue. Forcing Edition to One-Shot')
                    booktype = 'One-Shot'
                else:
                    booktype = comic['Type']

                if comic['Corrected_Type'] and comic['Corrected_Type'] != booktype:
                    booktype = comic['Corrected_Type']

                c_image = comic
                metadata = {}
                metadata['version'] = '1.0.1'
                metadata['metadata'] = (
                                            {'type': 'comicSeries',
                                             'publisher': comic['ComicPublisher'],
                                             'imprint': comic['PublisherImprint'],
                                             'name': comic['ComicName'],
                                             'cid': int(cid),
                                             'year': SeriesYear,
                                             'description_text': cdes_removed,
                                             'description_formatted': cdes_formatted,
                                             'volume': comicVol,
                                             'booktype': booktype,
                                             'age_rating': comic['AgeRating'],
                                             'collects': clean_issue_list,
                                             'ComicImage': comic['ComicImageURL'],
                                             'total_issues': comic['Total'],
                                             'publication_run': comic['ComicPublished'],
                                             'status': seriesStatus}
                )

                try:
                    with open(os.path.join(comic['ComicLocation'], 'series.json'), 'w', encoding='utf-8') as outfile:
                        json.dump(metadata, outfile, indent=4, ensure_ascii=False)
                except Exception as e:
                    logger.error('Unable to write series.json to %s. Error returned: %s' % (comic['ComicLocation'], e))
                    continue
                else:
                    logger.fdebug('Successfully written series.json file to %s' % comic['ComicLocation'])
                    myDB.upsert("comics", {"seriesjsonPresent": int(True)} ,{"ComicID": cid})

        return

