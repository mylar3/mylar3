"""A python class to manage communication with Comic Vine's REST API"""

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

import json
import urllib.request, urllib.error, urllib.parse
import urllib.request, urllib.parse, urllib.error
import re
import time
import datetime
import sys
import ssl
#from pprint import pprint
#import math

from bs4 import BeautifulSoup

try:
    from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
    from PyQt5.QtCore import QUrl, pyqtSignal, QObject, QByteArray
except ImportError:
    # No Qt, so define a few dummy QObjects to help us compile
    class QObject():

        def __init__(self, *args):
            pass

    class pyqtSignal():

        def __init__(self, *args):
            pass

        def emit(a, b, c):
            pass

from . import ctversion
from . import utils
from .comicvinecacher import ComicVineCacher
from .genericmetadata import GenericMetadata
from .issuestring import IssueString
#from settings import ComicTaggerSettings


class CVTypeID:
    Volume = "4050"
    Issue = "4000"


class ComicVineTalkerException(Exception):
    Unknown = -1
    Network = -2
    InvalidKey = 100
    RateLimit = 107

    def __init__(self, code=-1, desc=""):
        self.desc = desc
        self.code = code

    def __str__(self):
        if (self.code == ComicVineTalkerException.Unknown or
                self.code == ComicVineTalkerException.Network):
            return self.desc
        else:
            return "CV error #{0}:  [{1}]. \n".format(self.code, self.desc)


class ComicVineTalker(QObject):

    logo_url = "http://static.comicvine.com/bundles/comicvinesite/images/logo.png"
    api_key = ""

    @staticmethod
    def getRateLimitMessage():
        if ComicVineTalker.api_key == "":
            return "Comic Vine rate limit exceeded.  You should configue your own Comic Vine API key."
        else:
            return "Comic Vine rate limit exceeded.  Please wait a bit."

    def __init__(self):
        QObject.__init__(self)

        self.api_base_url = "https://comicvine.gamespot.com/api"
        self.wait_for_rate_limit = False

        # key that is registered to comictagger
        default_api_key = '27431e6787042105bd3e47e169a624521f89f3a4'

        if ComicVineTalker.api_key == "":
            self.api_key = default_api_key
        else:
            self.api_key = ComicVineTalker.api_key

        self.log_func = None

        # always use a tls context for urlopen
        self.ssl = ssl.SSLContext(ssl.PROTOCOL_TLS)

    def setLogFunc(self, log_func):
        self.log_func = log_func

    def writeLog(self, text):
        if self.log_func is None:
            # sys.stdout.write(text.encode(errors='replace'))
            # sys.stdout.flush()
            print(text, file=sys.stderr)
        else:
            self.log_func(text)

    def parseDateStr(self, date_str):
        day = None
        month = None
        year = None
        if date_str is not None:
            parts = date_str.split('-')
            year = parts[0]
            if len(parts) > 1:
                month = parts[1]
                if len(parts) > 2:
                    day = parts[2]
        return day, month, year

    def testKey(self, key):

        try:
            test_url = self.api_base_url + "/issue/1/?api_key=" + \
                key + "&format=json&field_list=name"
            resp = urllib.request.urlopen(test_url, context=self.ssl)
            content = resp.read()
    
            cv_response = json.loads(content.decode('utf-8'))
    
            # Bogus request, but if the key is wrong, you get error 100: "Invalid
            # API Key"
            return cv_response['status_code'] != 100
        except:
            return False

    """
    Get the contect from the CV server.  If we're in "wait mode" and status code is a rate limit error
    sleep for a bit and retry.
    """

    def getCVContent(self, url):
        total_time_waited = 0
        limit_wait_time = 1
        counter = 0
        wait_times = [1, 2, 3, 4]
        while True:
            content = self.getUrlContent(url)
            cv_response = json.loads(content.decode('utf-8'))
            if self.wait_for_rate_limit and cv_response[
                    'status_code'] == ComicVineTalkerException.RateLimit:
                self.writeLog(
                    "Rate limit encountered.  Waiting for {0} minutes\n".format(limit_wait_time))
                time.sleep(limit_wait_time * 60)
                total_time_waited += limit_wait_time
                limit_wait_time = wait_times[counter]
                if counter < 3:
                    counter += 1
                # don't wait much more than 20 minutes
                if total_time_waited < 20:
                    continue
            if cv_response['status_code'] != 1:
                self.writeLog(
                    "Comic Vine query failed with error #{0}:  [{1}]. \n".format(
                        cv_response['status_code'],
                        cv_response['error']))
                raise ComicVineTalkerException(
                    cv_response['status_code'], cv_response['error'])
            else:
                # it's all good
                break
        return cv_response

    def getUrlContent(self, url):
        # connect to server:
        #  if there is a 500 error, try a few more times before giving up
        #  any other error, just bail
        #print("---", url)
        for tries in range(3):
            try:
                resp = urllib.request.urlopen(url, context=self.ssl)
                return resp.read()
            except urllib.error.HTTPError as e:
                if e.getcode() == 500:
                    self.writeLog("Try #{0}: ".format(tries + 1))
                    time.sleep(1)
                self.writeLog(str(e) + "\n")

                if e.getcode() != 500:
                    break

            except Exception as e:
                self.writeLog(str(e) + "\n")
                raise ComicVineTalkerException(
                    ComicVineTalkerException.Network, "Network Error!")

        raise ComicVineTalkerException(
            ComicVineTalkerException.Unknown, "Error on Comic Vine server")

    def searchForSeries(self, series_name, callback=None, refresh_cache=False):

        # remove cruft from the search string
        series_name = utils.removearticles(series_name).lower().strip()

        # before we search online, look in our cache, since we might have
        # done this same search recently
        cvc = ComicVineCacher()
        if not refresh_cache:
            cached_search_results = cvc.get_search_results(series_name)

            if len(cached_search_results) > 0:
                return cached_search_results

        original_series_name = series_name

        # Split and rejoin to remove extra internal spaces
        query_word_list = series_name.split()
        query_string = " ".join( query_word_list ).strip()
        #print ("Query string = ", query_string)

        query_string = urllib.parse.quote_plus(query_string.encode("utf-8"))

        search_url = self.api_base_url + "/search/?api_key=" + self.api_key + "&format=json&resources=volume&query=" + \
            query_string + \
            "&field_list=name,id,start_year,publisher,image,description,count_of_issues&limit=100"
        cv_response = self.getCVContent(search_url + "&page=1")

        search_results = list()

        # see http://api.comicvine.com/documentation/#handling_responses

        limit = cv_response['limit']
        current_result_count = cv_response['number_of_page_results']
        total_result_count = cv_response['number_of_total_results']

        # 8 Dec 2018 - Comic Vine changed query results again. Terms are now
        # ORed together, and we get thousands of results.  Good news is the
        # results are sorted by relevance, so we can be smart about halting
        # the search.  
        # 1. Don't fetch more than some sane amount of pages.
        max_results = 500 
        # 2. Halt when not all of our search terms are present in a result
        # 3. Halt when the results contain more (plus threshold) words than
        #    our search
        result_word_count_max = len(query_word_list) + 3

        total_result_count = min(total_result_count, max_results) 

        if callback is None:
            self.writeLog(
                "Found {0} of {1} results\n".format(
                    cv_response['number_of_page_results'],
                    cv_response['number_of_total_results']))
        search_results.extend(cv_response['results'])
        page = 1

        if callback is not None:
            callback(current_result_count, total_result_count)

        # see if we need to keep asking for more pages...
        stop_searching = False
        while (current_result_count < total_result_count):

            last_result = search_results[-1]['name']

            # See if the last result's name has all the of the search terms.
            # if not, break out of this, loop, we're done.
            #print("Searching for {} in '{}'".format(query_word_list, last_result))
            for term in query_word_list:
                if term not in last_result.lower():
                    #print("Term '{}' not in last result. Halting search result fetching".format(term))
                    stop_searching = True
                    break

            # Also, stop searching when the word count of last results is too much longer
            # than our search terms list 
            if len(utils.removearticles(last_result).split()) > result_word_count_max:
                #print("Last result '{}' is too long. Halting search result fetching".format(last_result))
                stop_searching = True

            if stop_searching:
                break

            if callback is None:
                self.writeLog(
                    "getting another page of results {0} of {1}...\n".format(
                        current_result_count,
                        total_result_count))
            page += 1

            cv_response = self.getCVContent(search_url + "&page=" + str(page))

            search_results.extend(cv_response['results'])
            current_result_count += cv_response['number_of_page_results']

            if callback is not None:
                callback(current_result_count, total_result_count)

        # Remove any search results that don't contain all the search terms
        # (iterate backwards for easy removal)
        for i in range(len(search_results) - 1, -1, -1):
            record = search_results[i]
            for term in query_word_list:
                if term not in record['name'].lower():
                    del search_results[i]
                    break

        # for record in search_results:
            #print(u"{0}: {1} ({2})".format(record['id'], record['name'] , record['start_year']))
            # print(record)
            #record['count_of_issues'] = record['count_of_isssues']
        #print(u"{0}: {1} ({2})".format(search_results['results'][0]['id'], search_results['results'][0]['name'] , search_results['results'][0]['start_year']))

        # cache these search results
        cvc.add_search_results(original_series_name, search_results)

        return search_results

    def fetchVolumeData(self, series_id):

        # before we search online, look in our cache, since we might already
        # have this info
        cvc = ComicVineCacher()
        cached_volume_result = cvc.get_volume_info(series_id)

        if cached_volume_result is not None:
            return cached_volume_result

        volume_url = self.api_base_url + "/volume/" + CVTypeID.Volume + "-" + \
            str(series_id) + "/?api_key=" + self.api_key + \
            "&field_list=name,id,start_year,publisher,count_of_issues&format=json"

        cv_response = self.getCVContent(volume_url)

        volume_results = cv_response['results']

        cvc.add_volume_info(volume_results)

        return volume_results

    def fetchIssuesByVolume(self, series_id):

        # before we search online, look in our cache, since we might already
        # have this info
        cvc = ComicVineCacher()
        cached_volume_issues_result = cvc.get_volume_issues_info(series_id)

        if cached_volume_issues_result is not None:
            return cached_volume_issues_result

        #---------------------------------
        issues_url = self.api_base_url + "/issues/" + "?api_key=" + self.api_key + "&filter=volume:" + \
            str(series_id) + \
            "&field_list=id,volume,issue_number,name,image,cover_date,site_detail_url,description&format=json"
        cv_response = self.getCVContent(issues_url)

        #------------------------------------

        limit = cv_response['limit']
        current_result_count = cv_response['number_of_page_results']
        total_result_count = cv_response['number_of_total_results']
        #print("total_result_count", total_result_count)

        #print("Found {0} of {1} results".format(cv_response['number_of_page_results'], cv_response['number_of_total_results']))
        volume_issues_result = cv_response['results']
        page = 1
        offset = 0

        # see if we need to keep asking for more pages...
        while (current_result_count < total_result_count):
            #print("getting another page of issue results {0} of {1}...".format(current_result_count, total_result_count))
            page += 1
            offset += cv_response['number_of_page_results']

            # print issues_url+ "&offset="+str(offset)
            cv_response = self.getCVContent(
                issues_url + "&offset=" + str(offset))

            volume_issues_result.extend(cv_response['results'])
            current_result_count += cv_response['number_of_page_results']

        self.repairUrls(volume_issues_result)

        cvc.add_volume_issues_info(series_id, volume_issues_result)

        return volume_issues_result

    def fetchIssuesByVolumeIssueNumAndYear(
            self, volume_id_list, issue_number, year):
        volume_filter = "volume:"
        for vid in volume_id_list:
            volume_filter += str(vid) + "|"

        year_filter = ""
        if year is not None and str(year).isdigit():
            year_filter = ",cover_date:{0}-1-1|{1}-1-1".format(
                year, int(year) + 1)

        issue_number = urllib.parse.quote_plus(str(issue_number).encode("utf-8"))

        filter = "&filter=" + volume_filter + \
            year_filter + ",issue_number:" + issue_number

        issues_url = self.api_base_url + "/issues/" + "?api_key=" + self.api_key + filter + \
            "&field_list=id,volume,issue_number,name,image,cover_date,site_detail_url,description&format=json"

        cv_response = self.getCVContent(issues_url)

        #------------------------------------

        limit = cv_response['limit']
        current_result_count = cv_response['number_of_page_results']
        total_result_count = cv_response['number_of_total_results']
        #print("total_result_count", total_result_count)

        #print("Found {0} of {1} results\n".format(cv_response['number_of_page_results'], cv_response['number_of_total_results']))
        filtered_issues_result = cv_response['results']
        page = 1
        offset = 0

        # see if we need to keep asking for more pages...
        while (current_result_count < total_result_count):
            #print("getting another page of issue results {0} of {1}...\n".format(current_result_count, total_result_count))
            page += 1
            offset += cv_response['number_of_page_results']

            # print issues_url+ "&offset="+str(offset)
            cv_response = self.getCVContent(
                issues_url + "&offset=" + str(offset))

            filtered_issues_result.extend(cv_response['results'])
            current_result_count += cv_response['number_of_page_results']

        self.repairUrls(filtered_issues_result)

        return filtered_issues_result

    def fetchIssueData(self, series_id, issue_number, settings):

        volume_results = self.fetchVolumeData(series_id)
        issues_list_results = self.fetchIssuesByVolume(series_id)

        found = False
        for record in issues_list_results:
            if IssueString(issue_number).asString() is None:
                issue_number = 1
            if IssueString(record['issue_number']).asString().lower() == IssueString(
                    issue_number).asString().lower():
                found = True
                break

        if (found):
            issue_url = self.api_base_url + "/issue/" + CVTypeID.Issue + "-" + \
                str(record['id']) + "/?api_key=" + \
                self.api_key + "&format=json"

            cv_response = self.getCVContent(issue_url)
            issue_results = cv_response['results']

        else:
            return None

        # Now, map the Comic Vine data to generic metadata
        return self.mapCVDataToMetadata(
            volume_results, issue_results, settings)

    def fetchIssueDataByIssueID(self, issue_id, settings):

        issue_url = self.api_base_url + "/issue/" + CVTypeID.Issue + "-" + \
            str(issue_id) + "/?api_key=" + self.api_key + "&format=json"
        cv_response = self.getCVContent(issue_url)

        issue_results = cv_response['results']

        volume_results = self.fetchVolumeData(issue_results['volume']['id'])

        # Now, map the Comic Vine data to generic metadata
        md = self.mapCVDataToMetadata(volume_results, issue_results, settings)
        md.isEmpty = False
        return md

    def mapCVDataToMetadata(self, volume_results, issue_results, settings):

        # Now, map the Comic Vine data to generic metadata
        metadata = GenericMetadata()

        metadata.series = issue_results['volume']['name']

        num_s = IssueString(issue_results['issue_number']).asString()
        metadata.issue = num_s
        metadata.title = issue_results['name']

        metadata.publisher = volume_results['publisher']['name']
        metadata.day, metadata.month, metadata.year = self.parseDateStr(
            issue_results['cover_date'])

        #metadata.issueCount = volume_results['count_of_issues']
        metadata.comments = self.cleanup_html(
            issue_results['description'], settings.remove_html_tables)
        if settings.use_series_start_as_volume:
            metadata.volume = volume_results['start_year']

        metadata.notes = "Tagged with ComicTagger {0} using info from Comic Vine on {1}.  [Issue ID {2}]".format(
            ctversion.version,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            issue_results['id'])
        #metadata.notes  += issue_results['site_detail_url']

        metadata.webLink = issue_results['site_detail_url']

        person_credits = issue_results['person_credits']
        for person in person_credits:
            if 'role' in person:
                roles = person['role'].split(',')
                for role in roles:
                    # can we determine 'primary' from CV??
                    metadata.addCredit(
                        person['name'], role.title().strip(), False)

        character_credits = issue_results['character_credits']
        character_list = list()
        for character in character_credits:
            character_list.append(character['name'])
        metadata.characters = utils.listToString(character_list)

        team_credits = issue_results['team_credits']
        team_list = list()
        for team in team_credits:
            team_list.append(team['name'])
        metadata.teams = utils.listToString(team_list)

        location_credits = issue_results['location_credits']
        location_list = list()
        for location in location_credits:
            location_list.append(location['name'])
        metadata.locations = utils.listToString(location_list)

        story_arc_credits = issue_results['story_arc_credits']
        arc_list = []
        for arc in story_arc_credits:
            arc_list.append(arc['name'])
        if len(arc_list) > 0:
            metadata.storyArc = utils.listToString(arc_list)

        return metadata

    def cleanup_html(self, string, remove_html_tables):
        """
        converter = html2text.HTML2Text()
        #converter.emphasis_mark = '*'
        #converter.ignore_links = True
        converter.body_width = 0

        print(html2text.html2text(string))
        return string
        #return converter.handle(string)
        """

        if string is None:
            return ""
        # find any tables
        soup = BeautifulSoup(string, "html.parser")
        tables = soup.findAll('table')

        # remove all newlines first
        string = string.replace("\n", "")

        # put in our own
        string = string.replace("<br>", "\n")
        string = string.replace("</p>", "\n\n")
        string = string.replace("<h4>", "*")
        string = string.replace("</h4>", "*\n")

        # remove the tables
        p = re.compile(r'<table[^<]*?>.*?<\/table>')
        if remove_html_tables:
            string = p.sub('', string)
            string = string.replace("*List of covers and their creators:*", "")
        else:
            string = p.sub('{}', string)

        # now strip all other tags
        p = re.compile(r'<[^<]*?>')
        newstring = p.sub('', string)

        newstring = newstring.replace('&nbsp;', ' ')
        newstring = newstring.replace('&amp;', '&')

        newstring = newstring.strip()

        if not remove_html_tables:
            # now rebuild the tables into text from BSoup
            try:
                table_strings = []
                for table in tables:
                    rows = []
                    hdrs = []
                    col_widths = []
                    for hdr in table.findAll('th'):
                        item = hdr.string.strip()
                        hdrs.append(item)
                        col_widths.append(len(item))
                    rows.append(hdrs)

                    for row in table.findAll('tr'):
                        cols = []
                        col = row.findAll('td')
                        i = 0
                        for c in col:
                            item = c.string.strip()
                            cols.append(item)
                            if len(item) > col_widths[i]:
                                col_widths[i] = len(item)
                            i += 1
                        if len(cols) != 0:
                            rows.append(cols)
                    # now we have the data, make it into text
                    fmtstr = ""
                    for w in col_widths:
                        fmtstr += " {{:{}}}|".format(w + 1)
                    width = sum(col_widths) + len(col_widths) * 2
                    print("width=", width)
                    table_text = ""
                    counter = 0
                    for row in rows:
                        table_text += fmtstr.format(*row) + "\n"
                        if counter == 0 and len(hdrs) != 0:
                            table_text += "-" * width + "\n"
                        counter += 1

                    table_strings.append(table_text)

                newstring = newstring.format(*table_strings)
            except:
                # we caught an error rebuilding the table.
                # just bail and remove the formatting
                print("table parse error")
                newstring.replace("{}", "")

        return newstring

    def fetchIssueDate(self, issue_id):
        details = self.fetchIssueSelectDetails(issue_id)
        day, month, year = self.parseDateStr(details['cover_date'])
        return month, year

    def fetchIssueCoverURLs(self, issue_id):
        details = self.fetchIssueSelectDetails(issue_id)
        return details['image_url'], details['thumb_image_url']

    def fetchIssuePageURL(self, issue_id):
        details = self.fetchIssueSelectDetails(issue_id)
        return details['site_detail_url']

    def fetchIssueSelectDetails(self, issue_id):

        #cached_image_url,cached_thumb_url,cached_month,cached_year = self.fetchCachedIssueSelectDetails(issue_id)
        cached_details = self.fetchCachedIssueSelectDetails(issue_id)
        if cached_details['image_url'] is not None:
            return cached_details

        issue_url = self.api_base_url + "/issue/" + CVTypeID.Issue + "-" + \
            str(issue_id) + "/?api_key=" + self.api_key + \
            "&format=json&field_list=image,cover_date,site_detail_url"

        details = dict()
        details['image_url'] = None
        details['thumb_image_url'] = None
        details['cover_date'] = None
        details['site_detail_url'] = None

        cv_response = self.getCVContent(issue_url)

        details['image_url'] = cv_response['results']['image']['super_url']
        details['thumb_image_url'] = cv_response[
            'results']['image']['thumb_url']
        details['cover_date'] = cv_response['results']['cover_date']
        details['site_detail_url'] = cv_response['results']['site_detail_url']

        if details['image_url'] is not None:
            self.cacheIssueSelectDetails(issue_id,
                                         details['image_url'],
                                         details['thumb_image_url'],
                                         details['cover_date'],
                                         details['site_detail_url'])
        # print(details['site_detail_url'])
        return details

    def fetchCachedIssueSelectDetails(self, issue_id):

        # before we search online, look in our cache, since we might already
        # have this info
        cvc = ComicVineCacher()
        return cvc.get_issue_select_details(issue_id)

    def cacheIssueSelectDetails(
            self, issue_id, image_url, thumb_url, cover_date, page_url):
        cvc = ComicVineCacher()
        cvc.add_issue_select_details(
            issue_id, image_url, thumb_url, cover_date, page_url)

    def fetchAlternateCoverURLs(self, issue_id, issue_page_url):
        url_list = self.fetchCachedAlternateCoverURLs(issue_id)
        if url_list is not None:
            return url_list

        # scrape the CV issue page URL to get the alternate cover URLs
        resp = urllib.request.urlopen(issue_page_url, context=self.ssl)
        content = resp.read()
        alt_cover_url_list = self.parseOutAltCoverUrls(content)

        # cache this alt cover URL list
        self.cacheAlternateCoverURLs(issue_id, alt_cover_url_list)

        return alt_cover_url_list

    def parseOutAltCoverUrls(self, page_html):
        soup = BeautifulSoup(page_html, "html.parser")
    
        alt_cover_url_list = []
    
        # Using knowledge of the layout of the Comic Vine issue page here:
        # look for the divs that are in the classes 'imgboxart' and
        # 'issue-cover'
        div_list = soup.find_all('div')
        covers_found = 0
        for d in div_list:
            if 'class' in d.attrs:
                c = d['class']
                if ('imgboxart' in c and 
                        'issue-cover' in c and
                        d.img['src'].startswith("http")
                   ):
                    
                    covers_found += 1
                    if covers_found != 1:
                            alt_cover_url_list.append(d.img['src'])
    
        return alt_cover_url_list

    def fetchCachedAlternateCoverURLs(self, issue_id):

        # before we search online, look in our cache, since we might already
        # have this info
        cvc = ComicVineCacher()
        url_list = cvc.get_alt_covers(issue_id)
        if url_list is not None:
            return url_list
        else:
            return None

    def cacheAlternateCoverURLs(self, issue_id, url_list):
        cvc = ComicVineCacher()
        cvc.add_alt_covers(issue_id, url_list)

    #-------------------------------------------------------------------------
    urlFetchComplete = pyqtSignal(str, str, int)

    def asyncFetchIssueCoverURLs(self, issue_id):

        self.issue_id = issue_id
        details = self.fetchCachedIssueSelectDetails(issue_id)
        if details['image_url'] is not None:
            self.urlFetchComplete.emit(
                details['image_url'],
                details['thumb_image_url'],
                self.issue_id)
            return

        issue_url = self.api_base_url + "/issue/" + CVTypeID.Issue + "-" + \
            str(issue_id) + "/?api_key=" + self.api_key + \
            "&format=json&field_list=image,cover_date,site_detail_url"
        self.nam = QNetworkAccessManager()
        self.nam.finished.connect(self.asyncFetchIssueCoverURLComplete)
        self.nam.get(QNetworkRequest(QUrl(issue_url)))

    def asyncFetchIssueCoverURLComplete(self, reply):

        # read in the response
        data = reply.readAll()

        try:
            cv_response = json.loads(bytes(data))
        except Exception as e:
            print("Comic Vine query failed to get JSON data", file=sys.stderr)
            print(str(data), file=sys.stderr)
            return

        if cv_response['status_code'] != 1:
            print("Comic Vine query failed with error:  [{0}]. ".format(
                cv_response['error']), file=sys.stderr)
            return

        image_url = cv_response['results']['image']['super_url']
        thumb_url = cv_response['results']['image']['thumb_url']
        cover_date = cv_response['results']['cover_date']
        page_url = cv_response['results']['site_detail_url']

        self.cacheIssueSelectDetails(
            self.issue_id, image_url, thumb_url, cover_date, page_url)

        self.urlFetchComplete.emit(image_url, thumb_url, self.issue_id)

    altUrlListFetchComplete = pyqtSignal(list, int)

    def asyncFetchAlternateCoverURLs(self, issue_id, issue_page_url):
        # This async version requires the issue page url to be provided!
        self.issue_id = issue_id
        url_list = self.fetchCachedAlternateCoverURLs(issue_id)
        if url_list is not None:
            self.altUrlListFetchComplete.emit(url_list, int(self.issue_id))
            return

        self.nam = QNetworkAccessManager()
        self.nam.finished.connect(self.asyncFetchAlternateCoverURLsComplete)
        self.nam.get(QNetworkRequest(QUrl(str(issue_page_url))))

    def asyncFetchAlternateCoverURLsComplete(self, reply):
        # read in the response
        html = str(reply.readAll())
        alt_cover_url_list = self.parseOutAltCoverUrls(html)

        # cache this alt cover URL list
        self.cacheAlternateCoverURLs(self.issue_id, alt_cover_url_list)

        self.altUrlListFetchComplete.emit(
            alt_cover_url_list, int(self.issue_id))

    def repairUrls(self, issue_list):
        # make sure there are URLs for the image fields
        for issue in issue_list:
            if issue['image'] is None:
                issue['image'] = dict()
                issue['image']['super_url'] = ComicVineTalker.logo_url
                issue['image']['thumb_url'] = ComicVineTalker.logo_url
