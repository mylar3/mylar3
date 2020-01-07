"""A python class to manage caching of data from Comic Vine"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sqlite3 as lite
import os
import datetime
#import sys
#from pprint import pprint

from . import ctversion
from .settings import ComicTaggerSettings
from . import utils


class ComicVineCacher:

    def __init__(self):
        self.settings_folder = ComicTaggerSettings.getSettingsFolder()
        self.db_file = os.path.join(self.settings_folder, "cv_cache.db")
        self.version_file = os.path.join(
            self.settings_folder, "cache_version.txt")

        # verify that cache is from same version as this one
        data = ""
        try:
            with open(self.version_file, 'rb') as f:
                data = f.read().decode("utf-8") 
                f.close()
        except:
            pass
        if data != ctversion.version:
            self.clearCache()

        if not os.path.exists(self.db_file):
            self.create_cache_db()

    def clearCache(self):
        try:
            os.unlink(self.db_file)
        except:
            pass
        try:
            os.unlink(self.version_file)
        except:
            pass

    def create_cache_db(self):

        # create the version file
        with open(self.version_file, 'w') as f:
            f.write(ctversion.version)

        # this will wipe out any existing version
        open(self.db_file, 'w').close()

        con = lite.connect(self.db_file)

        # create tables
        with con:

            cur = con.cursor()
            # name,id,start_year,publisher,image,description,count_of_issues
            cur.execute(
                "CREATE TABLE VolumeSearchCache(" +
                "search_term TEXT," +
                "id INT," +
                "name TEXT," +
                "start_year INT," +
                "publisher TEXT," +
                "count_of_issues INT," +
                "image_url TEXT," +
                "description TEXT," +
                "timestamp DATE DEFAULT (datetime('now','localtime'))) ")

            cur.execute(
                "CREATE TABLE Volumes(" +
                "id INT," +
                "name TEXT," +
                "publisher TEXT," +
                "count_of_issues INT," +
                "start_year INT," +
                "timestamp DATE DEFAULT (datetime('now','localtime')), " +
                "PRIMARY KEY (id))")

            cur.execute(
                "CREATE TABLE AltCovers(" +
                "issue_id INT," +
                "url_list TEXT," +
                "timestamp DATE DEFAULT (datetime('now','localtime')), " +
                "PRIMARY KEY (issue_id))")

            cur.execute(
                "CREATE TABLE Issues(" +
                "id INT," +
                "volume_id INT," +
                "name TEXT," +
                "issue_number TEXT," +
                "super_url TEXT," +
                "thumb_url TEXT," +
                "cover_date TEXT," +
                "site_detail_url TEXT," +
                "description TEXT," +
                "timestamp DATE DEFAULT (datetime('now','localtime')), " +
                "PRIMARY KEY (id))")

    def add_search_results(self, search_term, cv_search_results):

        con = lite.connect(self.db_file)

        with con:
            con.text_factory = str
            cur = con.cursor()

            # remove all previous entries with this search term
            cur.execute(
                "DELETE FROM VolumeSearchCache WHERE search_term = ?", [
                    search_term.lower()])

            # now add in new results
            for record in cv_search_results:
                timestamp = datetime.datetime.now()

                if record['publisher'] is None:
                    pub_name = ""
                else:
                    pub_name = record['publisher']['name']

                if record['image'] is None:
                    url = ""
                else:
                    url = record['image']['super_url']

                cur.execute(
                    "INSERT INTO VolumeSearchCache " +
                    "(search_term, id, name, start_year, publisher, count_of_issues, image_url, description) " +
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (search_term.lower(),
                     record['id'],
                        record['name'],
                        record['start_year'],
                        pub_name,
                        record['count_of_issues'],
                        url,
                        record['description']))

    def get_search_results(self, search_term):

        results = list()
        con = lite.connect(self.db_file)
        with con:
            con.text_factory = str
            cur = con.cursor()

            # purge stale search results
            a_day_ago = datetime.datetime.today() - datetime.timedelta(days=1)
            cur.execute(
                "DELETE FROM VolumeSearchCache WHERE timestamp  < ?", [
                    str(a_day_ago)])

            # fetch
            cur.execute(
                "SELECT * FROM VolumeSearchCache WHERE search_term=?", [search_term.lower()])
            rows = cur.fetchall()
            # now process the results
            for record in rows:

                result = dict()
                result['id'] = record[1]
                result['name'] = record[2]
                result['start_year'] = record[3]
                result['publisher'] = dict()
                result['publisher']['name'] = record[4]
                result['count_of_issues'] = record[5]
                result['image'] = dict()
                result['image']['super_url'] = record[6]
                result['description'] = record[7]

                results.append(result)

        return results

    def add_alt_covers(self, issue_id, url_list):

        con = lite.connect(self.db_file)

        with con:
            con.text_factory = str
            cur = con.cursor()

            # remove all previous entries with this search term
            cur.execute("DELETE FROM AltCovers WHERE issue_id = ?", [issue_id])

            url_list_str = utils.listToString(url_list)
            # now add in new record
            cur.execute("INSERT INTO AltCovers " +
                        "(issue_id, url_list) " +
                        "VALUES(?, ?)",
                        (issue_id,
                         url_list_str)
                        )

    def get_alt_covers(self, issue_id):

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_month_ago = datetime.datetime.today() - \
                datetime.timedelta(days=30)
            cur.execute(
                "DELETE FROM AltCovers WHERE timestamp  < ?", [
                    str(a_month_ago)])

            cur.execute(
                "SELECT url_list FROM AltCovers WHERE issue_id=?", [issue_id])
            row = cur.fetchone()
            if row is None:
                return None
            else:
                url_list_str = row[0]
                if len(url_list_str) == 0:
                    return []
                raw_list = url_list_str.split(",")
                url_list = []
                for item in raw_list:
                    url_list.append(str(item).strip())
                return url_list

    def add_volume_info(self, cv_volume_record):

        con = lite.connect(self.db_file)

        with con:

            cur = con.cursor()

            timestamp = datetime.datetime.now()

            if cv_volume_record['publisher'] is None:
                pub_name = ""
            else:
                pub_name = cv_volume_record['publisher']['name']

            data = {
                "name": cv_volume_record['name'],
                "publisher": pub_name,
                "count_of_issues": cv_volume_record['count_of_issues'],
                "start_year": cv_volume_record['start_year'],
                "timestamp": timestamp
            }
            self.upsert(cur, "volumes", "id", cv_volume_record['id'], data)

    def add_volume_issues_info(self, volume_id, cv_volume_issues):

        con = lite.connect(self.db_file)

        with con:

            cur = con.cursor()

            timestamp = datetime.datetime.now()

            # add in issues

            for issue in cv_volume_issues:

                data = {
                    "volume_id": volume_id,
                    "name": issue['name'],
                    "issue_number": issue['issue_number'],
                    "site_detail_url": issue['site_detail_url'],
                    "cover_date": issue['cover_date'],
                    "super_url": issue['image']['super_url'],
                    "thumb_url": issue['image']['thumb_url'],
                    "description": issue['description'],
                    "timestamp": timestamp
                }
                self.upsert(cur, "issues", "id", issue['id'], data)

    def get_volume_info(self, volume_id):

        result = None

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale volume info
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute(
                "DELETE FROM Volumes WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            cur.execute(
                "SELECT id,name,publisher,count_of_issues,start_year FROM Volumes WHERE id = ?",
                [volume_id])

            row = cur.fetchone()

            if row is None:
                return result

            result = dict()

            # since ID is primary key, there is only one row
            result['id'] = row[0]
            result['name'] = row[1]
            result['publisher'] = dict()
            result['publisher']['name'] = row[2]
            result['count_of_issues'] = row[3]
            result['start_year'] = row[4]
            result['issues'] = list()

        return result

    def get_volume_issues_info(self, volume_id):

        result = None

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute(
                "DELETE FROM Issues WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            results = list()

            cur.execute(
                "SELECT id,name,issue_number,site_detail_url,cover_date,super_url,thumb_url,description FROM Issues WHERE volume_id = ?",
                [volume_id])
            rows = cur.fetchall()

            # now process the results
            for row in rows:
                record = dict()

                record['id'] = row[0]
                record['name'] = row[1]
                record['issue_number'] = row[2]
                record['site_detail_url'] = row[3]
                record['cover_date'] = row[4]
                record['image'] = dict()
                record['image']['super_url'] = row[5]
                record['image']['thumb_url'] = row[6]
                record['description'] = row[7]

                results.append(record)

        if len(results) == 0:
            return None

        return results

    def add_issue_select_details(
            self,
            issue_id,
            image_url,
            thumb_image_url,
            cover_date,
            site_detail_url):

        con = lite.connect(self.db_file)

        with con:
            cur = con.cursor()
            con.text_factory = str
            timestamp = datetime.datetime.now()

            data = {
                "super_url": image_url,
                "thumb_url": thumb_image_url,
                "cover_date": cover_date,
                "site_detail_url": site_detail_url,
                "timestamp": timestamp
            }
            self.upsert(cur, "issues", "id", issue_id, data)

    def get_issue_select_details(self, issue_id):

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            cur.execute(
                "SELECT super_url,thumb_url,cover_date,site_detail_url FROM Issues WHERE id=?",
                [issue_id])
            row = cur.fetchone()

            details = dict()
            if row is None or row[0] is None:
                details['image_url'] = None
                details['thumb_image_url'] = None
                details['cover_date'] = None
                details['site_detail_url'] = None

            else:
                details['image_url'] = row[0]
                details['thumb_image_url'] = row[1]
                details['cover_date'] = row[2]
                details['site_detail_url'] = row[3]

            return details

    def upsert(self, cur, tablename, pkname, pkval, data):
        """This does an insert if the given PK doesn't exist, and an
        update it if does

        TODO: look into checking if UPDATE is needed
        TODO: should the cursor be created here, and not up the stack?
        """

        ins_count = len(data) + 1

        keys = ""
        vals = list()
        ins_slots = ""
        set_slots = ""

        for key in data:

            if keys != "":
                keys += ", "
            if ins_slots != "":
                ins_slots += ", "
            if set_slots != "":
                set_slots += ", "

            keys += key
            vals.append(data[key])
            ins_slots += "?"
            set_slots += key + " = ?"

        keys += ", " + pkname
        vals.append(pkval)
        ins_slots += ", ?"
        condition = pkname + " = ?"

        sql_ins = ("INSERT OR IGNORE INTO " + tablename +
                   " (" + keys + ") " +
                   " VALUES (" + ins_slots + ")")
        cur.execute(sql_ins, vals)

        sql_upd = ("UPDATE " + tablename +
                   " SET " + set_slots + " WHERE " + condition)
        cur.execute(sql_upd, vals)
