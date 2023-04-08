# -*- coding: utf-8 -*-
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

import re
import email.utils
import datetime
import time
from wsgiref.handlers import format_date_time

import mylar
from mylar import logger, filechecker, helpers, search


class search_check(object):

    def __init__(self):
        pass


    def checker(self, entries, is_info=None):
        mylar.COMICINFO = []
        hold_the_matches = []
        if is_info:
            ComicName = is_info['ComicName']
            nzbprov = is_info['nzbprov']
            RSS = is_info['RSS']
            UseFuzzy = is_info['UseFuzzy']
            StoreDate = is_info['StoreDate']
            IssueDate = is_info['IssueDate']
            digitaldate = is_info['digitaldate']
            booktype = is_info['booktype']
            ignore_booktype = is_info['ignore_booktype']
            SeriesYear = is_info['SeriesYear']
            ComicVersion = is_info['ComicVersion']
            IssDateFix = is_info['IssDateFix']
            ComicYear = comyear = is_info['ComicYear']
            IssueID = is_info['IssueID']
            ComicID = is_info['ComicID']
            IssueNumber = is_info['IssueNumber']
            manual = is_info['manual']
            newznab_host = is_info['newznab_host']
            torznab_host = is_info['torznab_host']
            oneoff = is_info['oneoff']
            tmpprov = is_info['tmpprov']
            SARC = is_info['SARC']
            IssueArcID = is_info['IssueArcID']
            cmloopit = is_info['cmloopit']
            findcomiciss = is_info['findcomiciss']
            intIss = is_info['intIss']
            chktpb = is_info['chktpb']
            provider_stat = is_info['provider_stat']

        #logger.fdebug('entries: %s' % (entries,))
        for entry in entries['entries']:
                alt_match = False
                #logger.fdebug('entry: %s' % (entry,))
                # brief match here against 32p since it returns the direct issue number

                logger.fdebug("checking search result: %s" % entry['title'])
                # some nzbsites feel that comics don't deserve a nice regex to strip
                # the crap from the header, the end result is that we're dealing with
                # the actual raw header which causes incorrect matches below. This is a
                # temporary cut from the experimental search option (findcomicfeed) as
                # it does this part well usually.
                except_list = [
                    'releases',
                    'gold line',
                    'distribution',
                    '0-day',
                    '0 day',
                ]
                splitTitle = entry['title'].split("\"")
                _digits = re.compile(r'\d')

                ComicTitle = entry['title']
                for subs in splitTitle:
                    logger.fdebug('sub: %s' % subs)
                    try:
                        if (
                            len(subs) >= len(ComicName)
                            and not any(d in subs.lower() for d in except_list)
                            and bool(_digits.search(subs)) is True
                        ):
                            if subs.lower().startswith('for'):
                                if ComicName.lower().startswith('for'):
                                    pass
                                else:
                                    # this is the crap we ignore. Continue
                                    continue
                                logger.fdebug(
                                    'Detected crap within header. Ignoring this portion'
                                    ' of the result in order to see if it\'s a valid'
                                    ' match.'
                                )
                            ComicTitle = subs
                            break
                    except Exception:
                        break

                ignored = []
                for x in mylar.CONFIG.IGNORE_SEARCH_WORDS:
                    if x.lower() in ComicTitle.lower():
                        ignored.append(x)

                if ignored:
                    logger.fdebug('[IGNORE_SEARCH_WORDS] %s exists within the search result (%s). Ignoring this result.' % (ignored, ComicTitle))
                    continue

                comsize_m = 0
                if nzbprov != "dognzb":
                    # rss for experimental doesn't have the size constraints embedded.
                    # So we do it here.
                    if RSS == "yes":
                        comsize_b = entry['length']
                    else:
                        # Experimental already has size constraints done.
                        if nzbprov == 'experimental':
                            # we only want the size from the rss as
                            # the search/api has it already.
                            comsize_b = entry['length']
                        else:
                            try:
                                if entry['site'] == 'DDL(GetComics)':
                                    comsize_b = entry['size']
                                    if comsize_b is not None:
                                        cb2 = re.sub(r'[^0-9]', '', comsize_b).strip()
                                        if cb2 == '':
                                            logger.warn(
                                                'Invalid filesize encountered. Ignoring'
                                            )
                                            comsize_b = None
                                        else:
                                            comsize_b = helpers.human2bytes(entry['size'])
                            except Exception:
                                tmpsz = entry.enclosures[0]
                                comsize_b = tmpsz['length']

                    logger.fdebug('comsize_b: %s' % comsize_b)
                    # file restriction limitation here
                    # Experimental (has it embeded in search and rss checks)

                    if comsize_b is None or comsize_b == '0':
                        logger.fdebug(
                            'Size of file cannot be retrieved.'
                            ' Ignoring size-comparison and continuing.'
                        )
                        # comsize_b = 0
                    else:
                        if entry['title'][:17] != '0-Day Comics Pack':
                            comsize_m = helpers.human_size(comsize_b)
                            logger.fdebug('size given as: %s' % comsize_m)
                            # ----size constraints.
                            # if it's not within size constaints - dump it now.
                            if mylar.CONFIG.USE_MINSIZE:
                                conv_minsize = helpers.human2bytes(
                                    mylar.CONFIG.MINSIZE + "M"
                                )
                                logger.fdebug(
                                    'comparing Min threshold %s .. to .. nzb %s'
                                    % (conv_minsize, comsize_b)
                                )
                                if int(conv_minsize) > int(comsize_b):
                                    logger.fdebug(
                                        'Failure to meet the Minimum size threshold'
                                        ' - skipping'
                                    )
                                    continue
                            if mylar.CONFIG.USE_MAXSIZE:
                                conv_maxsize = helpers.human2bytes(
                                    mylar.CONFIG.MAXSIZE + "M"
                                )
                                logger.fdebug(
                                    'comparing Max threshold %s .. to .. nzb %s'
                                    % (conv_maxsize, comsize_b)
                                )
                                if int(comsize_b) > int(conv_maxsize):
                                    logger.fdebug(
                                        'Failure to meet the Maximium size threshold'
                                        ' - skipping'
                                    )
                                    continue

                if mylar.CONFIG.IGNORE_COVERS is True:
                    cvrchk = re.sub(r'[\s\s+\_\.]', '', entry['title']).lower()
                    if any(['coversonly' in cvrchk, 'coveronly' in cvrchk]):
                        logger.fdebug('Cover(s) only detected. Ignoring result.')
                        continue

                # ---- date constaints.
                # if the posting date is prior to the publication date,
                # dump it and save the time.
                # logger.fdebug('entry: %s' % entry)
                if nzbprov == 'experimental':
                    pubdate = entry['pubdate']
                else:
                    try:
                        pubdate = entry['updated']
                    except Exception:
                        try:
                            pubdate = entry['pubdate']
                        except Exception as e:
                            logger.fdebug(
                                'Invalid date found. Unable to continue'
                                ' - skipping result. Error returned: %s' % e
                            )
                            continue

                if UseFuzzy == "1":
                    logger.fdebug(
                        'Year has been fuzzied for this series,'
                        ' ignoring store date comparison entirely.'
                    )
                    postdate_int = None
                    issuedate_int = None
                else:
                    # use store date instead of publication date for comparisons since
                    # publication date is usually +2 months
                    if StoreDate is None or StoreDate == '0000-00-00':
                        if IssueDate is None or IssueDate == '0000-00-00':
                            logger.fdebug(
                                'Invalid store date & issue date detected - you'
                                ' probably should refresh the series or wait for CV'
                                ' to correct the data'
                            )
                            continue
                        else:
                            stdate = IssueDate
                        logger.fdebug('issue date used is : %s' % stdate)
                    else:
                        stdate = StoreDate
                        logger.fdebug('store date used is : %s' % stdate)
                    logger.fdebug('date used is : %s' % stdate)

                    postdate_int = None
                    if all(['DDL' in nzbprov, len(pubdate) == 10]):
                        postdate_int = pubdate
                        logger.fdebug(
                            '[%s] postdate_int (%s): %s'
                            % (nzbprov, type(postdate_int), postdate_int)
                        )
                    if any(
                        [postdate_int is None, type(postdate_int) != int]
                    ) or not RSS == 'no':
                        # convert it to a tuple
                        dateconv = email.utils.parsedate_tz(pubdate)

                        try:
                            dateconv2 = datetime.datetime(*dateconv[:6])
                        except TypeError as e:
                            logger.warn(
                                'Unable to convert timestamp from : %s [%s]'
                                % ((dateconv,), e)
                            )
                        try:
                            # convert it to a numeric time, then subtract the
                            # timezone difference (+/- GMT)
                            if dateconv[-1] is not None:
                                postdate_int = (
                                    time.mktime(dateconv[: len(dateconv) - 1])
                                    - dateconv[-1]
                                )
                            else:
                                postdate_int = time.mktime(
                                    dateconv[: len(dateconv) - 1]
                                )
                        except Exception as e:
                            logger.warn(
                                'Unable to parse posting date from provider result set'
                                ' for : %s. Error returned: %s' % (entry['title'], e)
                            )
                            continue

                    if all([digitaldate != '0000-00-00', digitaldate is not None]):
                        i = 0
                    else:
                        digitaldate_int = '00000000'
                        i = 1

                    while i <= 1:
                        if i == 0:
                            usedate = digitaldate
                        else:
                            usedate = stdate
                        logger.fdebug('usedate: %s' % usedate)
                        # convert it to a Thu, 06 Feb 2014 00:00:00 format
                        issue_converted = datetime.datetime.strptime(
                            usedate.rstrip(), '%Y-%m-%d'
                        )
                        issue_convert = issue_converted + datetime.timedelta(days=-1)
                        # to get past different locale's os-dependent dates, let's
                        # convert it to a generic datetime format
                        try:
                            stamp = time.mktime(issue_convert.timetuple())
                            issconv = format_date_time(stamp)
                        except OverflowError as e:
                            logger.fdebug(
                                'Error converting the timestamp into a generic format:'
                                ' %s' % e
                            )
                            issconv = issue_convert.strftime('%a, %d %b %Y %H:%M:%S')
                        # convert it to a tuple
                        econv = email.utils.parsedate_tz(issconv)
                        econv2 = datetime.datetime(*econv[:6])
                        # convert it to a numeric and drop the GMT/Timezone
                        try:
                            usedate_int = time.mktime(econv[: len(econv) - 1])
                        except OverflowError:
                            logger.fdebug(
                                'Unable to convert timestamp to integer format.'
                                ' Forcing things through.'
                            )
                            isyear = econv[1]
                            epochyr = '1970'
                            if int(isyear) <= int(epochyr):
                                tm = datetime.datetime(1970, 1, 1)
                                try:
                                    usedate_int = int(time.mktime(tm.timetuple()))
                                except Exception as e:
                                    logger.warn(
                                        '[%s] Failed to convert tm of [%s]' % (e,tm)
                                    )
                                    logger.fdebug('issconv: %s' % issconv)
                                    diff = issue_convert - tm
                                    logger.fdebug('diff: %s' % diff)
                                    usedate_int = diff.total_seconds()
                            else:
                                continue
                        if i == 0:
                            digitaldate_int = usedate_int
                            digconv2 = econv2
                        else:
                            issuedate_int = usedate_int
                            issconv2 = econv2
                        i += 1

                    try:
                        # try new method to get around issues populating in a diff
                        # timezone thereby putting them in a different day.
                        # logger.info('digitaldate: %s' % digitaldate)
                        # logger.info('dateconv2: %s' % dateconv2.date())
                        # logger.info('digconv2: %s' % digconv2.date())
                        if (
                            digitaldate != '0000-00-00'
                            and dateconv2.date() >= digconv2.date()
                        ):
                            logger.fdebug(
                                '%s is after DIGITAL store date of %s'
                                % (pubdate, digitaldate)
                            )
                        elif dateconv2.date() < issconv2.date():
                            logger.fdebug(
                                '[CONV] pubdate: %s  < storedate: %s'
                                % (dateconv2.date(), issconv2.date())
                            )
                            logger.fdebug(
                                '%s is before store date of %s. Ignoring search result'
                                ' as this is not the right issue.'
                                % (pubdate, stdate)
                            )
                            continue
                        else:
                            logger.fdebug(
                                '[CONV] %s is after store date of %s'
                                % (pubdate, stdate)
                            )
                    except Exception:
                        # if the above fails, drop down to the integer compare method
                        # as a failsafe.
                        if (
                            digitaldate != '0000-00-00'
                            and postdate_int >= digitaldate_int
                        ):
                            logger.fdebug(
                                '%s is after DIGITAL store date of %s'
                                % (pubdate, digitaldate)
                            )
                        elif postdate_int < issuedate_int:
                            logger.fdebug(
                                '[INT]pubdate: %s  < storedate: %s'
                                % (postdate_int, issuedate_int)
                            )
                            logger.fdebug(
                                '%s is before store date of %s. Ignoring search result'
                                ' as this is not the right issue.'
                                % (pubdate, stdate)
                            )
                            continue
                        else:
                            logger.fdebug(
                                '[INT] %s is after store date of %s' % (pubdate, stdate)
                            )
                # -- end size constaints.
                if '(digital first)' in ComicTitle.lower():
                    dig_moving = re.sub(
                        r'\(digital first\)', '', ComicTitle.lower()
                    ).strip()
                    dig_moving = re.sub(r'[\s+]', ' ', dig_moving)
                    dig_mov_end = '%s (Digital First)' % dig_moving
                    thisentry = dig_mov_end
                else:
                    thisentry = ComicTitle

                logger.fdebug('Entry: %s' % thisentry)
                cleantitle = thisentry

                if 'mixed format' in cleantitle.lower():
                    cleantitle = re.sub('mixed format', '', cleantitle).strip()
                    logger.fdebug(
                        'removed extra information after issue # that'
                        ' is not necessary: %s' % cleantitle
                    )

                # send it to the parser here.
                p_comic = filechecker.FileChecker(file=ComicTitle, watchcomic=ComicName)
                parsed_comic = p_comic.listFiles()

                logger.fdebug('parsed_info: %s' % parsed_comic)
                logger.fdebug(
                    'booktype: %s / parsed_booktype: %s [ignore_booktype: %s]'
                    % (booktype, parsed_comic['booktype'], ignore_booktype)
                )
                if parsed_comic['parse_status'] == 'success' and (
                    all([booktype is None, parsed_comic['booktype'] == 'issue'])
                    or all([booktype == 'Print', parsed_comic['booktype'] == 'issue'])
                    or all(
                        [booktype == 'One-Shot', any(
                            [parsed_comic['booktype'] == 'issue',
                            'One-Shot' in parsed_comic['booktype']
                             ]
                        )
                        ]
                    )
                    or all(
                        [booktype != parsed_comic['booktype'], ignore_booktype is True]
                    )
                    or re.sub('None', 'issue', str(booktype)) in parsed_comic['booktype']
                ):
                    try:
                        fcomic = filechecker.FileChecker(watchcomic=ComicName)
                        filecomic = fcomic.matchIT(parsed_comic)
                    except Exception as e:
                        logger.error('[PARSE-ERROR]: %s' % e)
                        continue
                    else:
                        logger.fdebug('match_check: %s' % filecomic)
                        if filecomic['process_status'] == 'fail':
                            logger.fdebug(
                                '%s was not a match to %s (%s)'
                                % (cleantitle, ComicName, SeriesYear)
                            )
                            continue
                        elif filecomic['process_status'] == 'alt_match':
                            # if it's an alternate series match, we'll retain each value
                            # until the search has compeletely run, compiling matches.
                            # If at any point it's a standard match (ie. non-alternate
                            # series) that will be accepted as the one match and
                            # ignore the alts. Once all the search options have been
                            # exhausted and no matches aside from alternate series then
                            # we go get the best result from that list
                            logger.fdebug(
                                '%s was a match due to alternate matching.  Continuing'
                                ' to search, but retaining this result just in case.'
                                % ComicTitle
                            )
                            alt_match = True
                elif booktype != parsed_comic['booktype'] and ignore_booktype is False:
                    logger.fdebug(
                        'Booktypes do not match. Looking for %s, this is a %s.'
                        ' Ignoring this result.' % (booktype, parsed_comic['booktype'])
                    )
                    continue
                else:
                    logger.fdebug(
                        'Unable to parse name properly: %s. Ignoring this result'
                        % parsed_comic
                    )
                    continue

                # adjust for covers only by removing them entirely...
                vers4year = "no"
                vers4vol = "no"
                versionfound = "no"

                if ComicVersion:
                    ComVersChk = re.sub("[^0-9]", "", ComicVersion)
                    if ComVersChk == '' or ComVersChk == '1':
                        ComVersChk = 0
                else:
                    ComVersChk = 0

                fndcomicversion = None

                if parsed_comic['series_volume'] is not None:
                    versionfound = "yes"
                    if len(parsed_comic['series_volume'][1:]) == 4 and (
                        parsed_comic['series_volume'][1:].isdigit()
                    ):  # v2013
                        logger.fdebug(
                            "[Vxxxx] Version detected as %s"
                            % (parsed_comic['series_volume'])
                        )
                        vers4year = "yes"
                        fndcomicversion = parsed_comic['series_volume']
                    elif len(parsed_comic['series_volume'][1:]) == 1 and (
                        parsed_comic['series_volume'][1:].isdigit()
                    ):  # v2
                        logger.fdebug(
                            "[Vx] Version detected as %s"
                            % parsed_comic['series_volume']
                        )
                        vers4vol = parsed_comic['series_volume']
                        fndcomicversion = parsed_comic['series_volume']
                    elif (
                        parsed_comic['series_volume'][1:].isdigit()
                        and len(parsed_comic['series_volume']) < 4
                    ):
                        logger.fdebug(
                            '[Vxxx] Version detected as %s'
                            % parsed_comic['series_volume']
                        )
                        vers4vol = parsed_comic['series_volume']
                        fndcomicversion = parsed_comic['series_volume']
                    elif (
                        parsed_comic['series_volume'].isdigit()
                        and len(parsed_comic['series_volume']) <= 4
                    ):
                        # this stuff is necessary for 32P volume manipulation
                        if len(parsed_comic['series_volume']) == 4:
                            vers4year = "yes"
                            fndcomicversion = parsed_comic['series_volume']
                        elif len(parsed_comic['series_volume']) == 1:
                            vers4vol = parsed_comic['series_volume']
                            fndcomicversion = parsed_comic['series_volume']
                        elif len(parsed_comic['series_volume']) < 4:
                            vers4vol = parsed_comic['series_volume']
                            fndcomicversion = parsed_comic['series_volume']
                        else:
                            logger.fdebug(
                                "error - unknown length for : %s"
                                % parsed_comic['series_volume']
                            )

                yearmatch = False
                #logger.fdebug('UseFuzzy: %s / ComVersChk: %s / IssDateFix: %s' % (UseFuzzy, ComVersChk, IssDateFix))
                if vers4vol != "no" or vers4year != "no":
                    logger.fdebug(
                        'Series Year not provided but Series Volume detected of %s.'
                        ' Bypassing Year Match.'
                        % fndcomicversion
                    )
                    yearmatch = True
                elif ComVersChk == 0 and parsed_comic['issue_year'] is None:
                    logger.fdebug(
                        'Series version detected as V1 (only series in existance with'
                        ' that title). Bypassing Year/Volume check'
                    )
                    yearmatch = True
                elif (
                    any(
                        [
                            UseFuzzy == "0",
                            UseFuzzy == "2",
                            UseFuzzy is None,
                            IssDateFix != "no",
                        ]
                    )
                    and parsed_comic['issue_year'] is not None
                ):
                    if any(
                        [
                            parsed_comic['issue_year'][:-2] == '19',
                            parsed_comic['issue_year'][:-2] == '20',
                        ]
                    ):
                        if str(comyear) == parsed_comic['issue_year']:
                            logger.fdebug('%s - right years match baby!' % comyear)
                            yearmatch = True
                        else:
                            logger.fdebug(
                                '%s - not right - years do not match' % comyear
                            )
                            yearmatch = False
                            if UseFuzzy == "2":
                                # Fuzzy the year +1 and -1
                                ComUp = int(ComicYear) + 1
                                ComDwn = int(ComicYear) - 1
                                if (
                                    str(ComUp) in parsed_comic['issue_year']
                                    or str(ComDwn) in parsed_comic['issue_year']
                                ):
                                    logger.fdebug(
                                        'Fuzzy Logicd the Year and matched to a year'
                                        ' of %s' % parsed_comic['issue_year']
                                    )
                                    yearmatch = True
                                else:
                                    logger.fdebug(
                                        '%s Fuzzy logicd the Year and year still did'
                                        ' not match.' % comyear
                                    )
                            # let's do this here and save a few extra loops ;)
                            # fix for issue dates between Nov-Dec/Jan
                            if IssDateFix != "no" and UseFuzzy != "2":
                                if (
                                    IssDateFix == "01"
                                    or IssDateFix == "02"
                                    or IssDateFix == "03"
                                ):
                                    ComicYearFix = int(ComicYear) - 1
                                    if str(ComicYearFix) in parsed_comic['issue_year']:
                                        logger.fdebug(
                                            'Further analysis reveals this was'
                                            ' published inbetween Nov-Jan, decreasing'
                                            ' year to %s has resulted in a match!'
                                            % ComicYearFix
                                        )
                                        yearmatch = True
                                    else:
                                        logger.fdebug(
                                            '%s- not the right year.' % comyear
                                        )
                                else:
                                    ComicYearFix = int(ComicYear) + 1
                                    if str(ComicYearFix) in parsed_comic['issue_year']:
                                        logger.fdebug(
                                            'Further analysis reveals this was'
                                            ' published inbetween Nov-Jan, incrementing'
                                            ' year to %s has resulted in a match!'
                                            % ComicYearFix
                                        )
                                        yearmatch = True
                                    else:
                                        logger.fdebug(
                                            '%s - not the right year.' % comyear
                                        )
                elif UseFuzzy == "1":
                    yearmatch = True

                if yearmatch is False:
                    continue

                annualize = False
                if 'annual' in ComicName.lower():
                    logger.fdebug(
                        "IssueID of : %s This is an annual...let's adjust." % IssueID
                    )
                    annualize = True

                D_ComicVersion = 1
                F_ComicVersion = None

                if versionfound == "yes" or annualize is True:
                    logger.fdebug("volume detection commencing - adjusting length.")
                    logger.fdebug("watch comicversion is %s" % ComicVersion)
                    logger.fdebug("version found: %s" % fndcomicversion)
                    logger.fdebug("vers4year: %s" % vers4year)
                    logger.fdebug("vers4vol: %s" % vers4vol)

                    if vers4year != "no" or vers4vol != "no":
                        # if the volume is None, assume it's a V1 to increase % hits
                        if ComVersChk == 0:
                            D_ComicVersion = 1
                        else:
                            D_ComicVersion = ComVersChk

                    # if this is a one-off, SeriesYear will be None and cause errors.
                    S_ComicVersion = 0
                    if all([SeriesYear is not None, annualize is False]):
                        S_ComicVersion = str(SeriesYear)

                    if fndcomicversion:
                        F_ComicVersion = re.sub("[^0-9]", "", fndcomicversion)
                        # if found volume is a vol.0, up it to vol.1 (since there is no V0)
                        if F_ComicVersion == '0':
                            if annualize is True:
                                F_ComicVersion = parsed_comic['issue_year']
                            else:
                                # need to convert dates to just be yyyy-mm-dd and do comparison,
                                # time operator in the below calc
                                F_ComicVersion = '1'
                    else:
                        F_ComicVersion = '1'

                    logger.fdebug('FCVersion: %s' % F_ComicVersion)
                    logger.fdebug('DCVersion: %s' % D_ComicVersion)
                    logger.fdebug('SCVersion: %s' % S_ComicVersion)
                    logger.fdebug('ComicYear: %s' % ComicYear)

                    # here's the catch, sometimes annuals get posted as the Pub Year
                    # instead of the Series they belong to (V2012 vs V2013)
                    if annualize is True and any(
                            [
                                int(ComicYear) == int(F_ComicVersion),
                                int(ComicYear) == int(parsed_comic['issue_number']),
                            ]
                    ):
                        logger.fdebug(
                            "We matched on versions for annuals %s (%s = %s = %s)"
                            % (ComicYear, fndcomicversion, F_ComicVersion, parsed_comic['issue_number'])
                        )
                    elif all(
                            [
                                 booktype != 'TPB',
                                 booktype != 'HC',
                                 booktype != 'GN',
                            ]
                        ) and (
                            int(F_ComicVersion) == int(D_ComicVersion)
                            or int(F_ComicVersion) == int(S_ComicVersion)
                    ):
                        logger.fdebug("We matched on versions...%s" % fndcomicversion)
                    else:
                        if any(
                               [
                                   booktype == 'TPB',
                                   booktype == 'HC',
                                   booktype == 'GN',
                               ]
                            ) and any([
                               all(
                               [
                                   int(F_ComicVersion) == int(findcomiciss)
                                   and filecomic['justthedigits'] is None
                               ]
                            ), all(
                               [
                                   int(F_ComicVersion) == int(findcomiciss)
                                   and ComicYear == parsed_comic['issue_year']
                               ]
                            )
                        ]):
                            logger.fdebug(
                                '%s detected - reassigning volume %s to match as the'
                                ' issue number based on Volume'
                                % (booktype, fndcomicversion)
                            )
                        elif all(
                                 [
                                     booktype == 'TPB',
                                     booktype == 'HC',
                                     booktype == 'GN',
                                 ]
                            ) and all(
                            [
                                int(F_ComicVersion) == int(findcomiciss),
                                fndcomicversion is not None,
                                booktype in filecomic['booktype'],
                                filecomic['justthedigits'] is None,
                            ]
                        ):
                            logger.fdebug(
                                '%s detected - reassigning volume %s to match as the issue number'
                                % (booktype, fndcomicversion)
                            )
                        else:
                            logger.fdebug("Versions wrong. Ignoring possible match.")
                            continue

                downloadit = False

                try:
                    pack_test = entry['pack']
                except Exception:
                    pack_test = False


                if all(['DDL' in nzbprov, pack_test is True]):
                    logger.fdebug(
                        '[PACK-QUEUE] %s Pack detected for %s.'
                        % (nzbprov, entry['filename'])
                    )

                    # find the pack range.
                    pack_issuelist = None
                    issueid_info = None
                    try:
                        if not entry['title'].startswith('0-Day Comics Pack'):
                            pack_issuelist = entry['issues']
                            issueid_info = helpers.issue_find_ids(
                                ComicName, ComicID, pack_issuelist, IssueNumber
                            )
                            if issueid_info['valid'] is True:
                                logger.info(
                                    'Issue Number %s exists within pack. Continuing.'
                                    % IssueNumber
                                )
                            else:
                                logger.fdebug(
                                    'Issue Number %s does NOT exist within this pack.'
                                    ' Skipping' % IssueNumber
                                )
                                continue
                    except Exception as e:
                        logger.error(
                            'Unable to identify pack range for %s. Error returned: %s'
                            % (entry['title'], e)
                        )
                        continue
                    # pack support.
                    nowrite = False
                    if 'DDL' in nzbprov:
                        if 'getcomics' in entry['link']:
                            nzbid = entry['id']
                    else:
                        nzbid = search.generate_id(provider_stat, entry['link'], ComicName)
                    if all([manual is not True, alt_match is False]):
                        downloadit = True
                    else:
                        for x in mylar.COMICINFO:
                            if (
                                all(
                                    [
                                        x['link'] == entry['link'],
                                        x['tmpprov'] == tmpprov,
                                    ]
                                )
                                or all(
                                    [x['nzbid'] == nzbid, x['newznab'] == newznab_host]
                                )
                                or all(
                                    [x['nzbid'] == nzbid, x['torznab'] == torznab_host]
                                )
                            ):
                                nowrite = True
                                break

                    if nowrite is False:
                        if any(
                            [
                                nzbprov == 'dognzb',
                                nzbprov == 'nzb.su',
                                nzbprov == 'experimental',
                                'newznab' in nzbprov,
                            ]
                        ):
                            tprov = nzbprov
                            kind = 'usenet'
                            if newznab_host is not None:
                                tprov = newznab_host[0]
                        else:
                            tprov = nzbprov
                            kind = 'torrent'
                            if torznab_host is not None:
                                tprov = torznab_host[0]

                        search_values = {
                            "ComicName": ComicName,
                            "ComicID": ComicID,
                            "IssueID": IssueID,
                            "ComicVolume": ComicVersion,
                            "IssueNumber": IssueNumber,
                            "IssueDate": IssueDate,
                            "comyear": comyear,
                            "pack": True,
                            "pack_numbers": pack_issuelist,
                            "pack_issuelist": issueid_info,
                            "modcomicname": entry['title'],
                            "oneoff": oneoff,
                            "nzbprov": nzbprov,
                            "nzbtitle": entry['title'],
                            "nzbid": nzbid,
                            "provider": tprov,
                            "link": entry['link'],
                            "pubdate": pubdate,
                            "size": comsize_m,
                            "tmpprov": tmpprov,
                            "kind": kind,
                            "SARC": SARC,
                            "booktype": booktype,
                            "IssueArcID": IssueArcID,
                            "newznab": newznab_host,
                            "torznab": torznab_host,
                            "downloadit": downloadit,
                            "ComicTitle": ComicTitle,
                            "entry": entry,
                            "provider_stat": provider_stat,
                        }

                        mylar.COMICINFO.append(search_values)

                        hold_the_matches.append(search_values)

                else:
                    if filecomic['process_status'] == 'match':
                        if cmloopit != 4:
                            logger.fdebug(
                                "issue we are looking for is : %s" % findcomiciss
                            )
                            logger.fdebug(
                                "integer value of issue we are looking for : %s"
                                % intIss
                            )
                        else:
                            if intIss is None and all(
                                [
                                    booktype == 'One-Shot',
                                    helpers.issuedigits(parsed_comic['issue_number'])
                                    == 1000,
                                ]
                            ):
                                intIss = 1000
                            else:
                                if annualize is True and len(re.sub('[^0-9]', '', parsed_comic['issue_number']).strip()) == 4:
                                    intIss = 1000
                                else:
                                    intIss = 9999999999
                        if filecomic['justthedigits'] is not None:
                            logger.fdebug(
                                "issue we found for is : %s"
                                % filecomic['justthedigits']
                            )
                            if annualize is True and len(re.sub('[^0-9]', '', filecomic['justthedigits']).strip()) == 4:
                                comintIss = 1000
                            else:
                                comintIss = helpers.issuedigits(filecomic['justthedigits'])
                            logger.fdebug(
                                "integer value of issue we have found : %s" % comintIss
                            )
                        else:
                            comintIss = 11111111111

                        # do this so that we don't touch the actual value but just
                        # use it for comparisons
                        if filecomic['justthedigits'] is None:
                            pc_in = None
                        else:
                            pc_in = helpers.issuedigits(filecomic['justthedigits'])
                        # issue comparison now as well
                        if (
                            all([intIss is not None, comintIss is not None])
                            and int(intIss) == int(comintIss)
                            or (any(
                                [
                                    filecomic['booktype'] == 'TPB',
                                    filecomic['booktype'] == 'GN',
                                    filecomic['booktype'] == 'HC',
                                    filecomic['booktype'] == 'TPB/GN/HC',
                                ]
                                ) and all(
                                    [
                                        chktpb != 0,
                                        pc_in is None,
                                        helpers.issuedigits(F_ComicVersion) == intIss,
                                    ]
                            ))
                            or (any(
                                [
                                    filecomic['booktype'] == 'TPB',
                                    filecomic['booktype'] == 'GN',
                                    filecomic['booktype'] == 'HC',
                                    filecomic['booktype'] == 'TPB/GN/HC',
                                ]
                                )  and all(
                                    [
                                        chktpb == 2,
                                        pc_in is None,
                                        cmloopit == 1,
                                    ]
                            ))
                            or all([cmloopit == 4, findcomiciss is None, pc_in is None])
                            or all([cmloopit == 4, findcomiciss is None, pc_in == 1])
                            or all([cmloopit == 4, findcomiciss == 1, pc_in is None])
                        ):
                            nowrite = False
                            logger.info('[nzbprov:%s] provider_stat: %s' % (nzbprov, provider_stat,))
                            if nzbprov == 'torznab' or provider_stat['type'] == 'torznab':
                                nzbid = search.generate_id(provider_stat, entry['id'], ComicName)
                            elif 'DDL' in nzbprov:
                                if 'GetComics' in nzbprov:
                                    if RSS == "yes":
                                        entry['id'] = entry['link']
                                        entry['link'] = 'https://getcomics.info/?p=' + str(
                                            entry['id']
                                        )
                                        entry['filename'] = entry['title']
                                    else:
                                        nzbid = entry['id']
                                    if '/cat/' in entry['link']:
                                        entry['link'] = 'https://getcomics.info/?p=%s' % entry['id']
                                entry['title'] = entry['filename']
                                nzbid = entry['id']
                            else:
                                try:
                                    logger.fdebug('title_id: %s' % (entry['id'],))
                                    if 'details' in entry['id']:
                                        nzbid = search.generate_id(provider_stat, entry['id'], ComicName)
                                    else:
                                        nzbid = search.generate_id(provider_stat, entry['link'], ComicName)
                                except Exception as e:
                                    nzbid = search.generate_id(provider_stat, entry['link'], ComicName)
                            if all([manual is not True, alt_match is False]):
                                downloadit = True
                            else:
                                for x in mylar.COMICINFO:
                                    if (
                                        all(
                                            [
                                                x['link'] == entry['link'],
                                                x['tmpprov'] == tmpprov,
                                            ]
                                        )
                                        or all(
                                            [
                                                x['nzbid'] == nzbid,
                                                x['newznab'] == newznab_host,
                                            ]
                                        )
                                        or all(
                                            [
                                                x['nzbid'] == nzbid,
                                                x['torznab'] == torznab_host,
                                            ]
                                        )
                                    ):
                                        nowrite = True
                                        break

                            # modify the name for annualization to be displayed properly
                            if annualize is True:
                                modcomicname = '%s Annual' % ComicName
                            else:
                                modcomicname = ComicName

                            if IssueID is None:
                                cyear = ComicYear
                            else:
                                cyear = comyear

                            if nowrite is False:
                                if any(
                                    [
                                        nzbprov == 'dognzb',
                                        nzbprov == 'nzb.su',
                                        nzbprov == 'experimental',
                                        'newznab' in nzbprov,
                                        provider_stat['type'] == 'newznab',
                                    ]
                                ):
                                    tprov = nzbprov
                                    kind = 'usenet'
                                    if newznab_host is not None:
                                        tprov = newznab_host[0]
                                else:
                                    kind = 'torrent'
                                    tprov = nzbprov
                                    if torznab_host is not None:
                                        tprov = torznab_host[0]

                                search_values = {
                                    "ComicName": ComicName,
                                    "ComicID": ComicID,
                                    "IssueID": IssueID,
                                    "ComicVolume": ComicVersion,
                                    "IssueNumber": IssueNumber,
                                    "IssueDate": IssueDate,
                                    "comyear": cyear,
                                    "pack": False,
                                    "pack_numbers": None,
                                    "pack_issuelist": None,
                                    "modcomicname": modcomicname,
                                    "oneoff": oneoff,
                                    "nzbprov": nzbprov,
                                    "provider": tprov,
                                    "nzbtitle": entry['title'],
                                    "nzbid": nzbid,
                                    "link": entry['link'],
                                    "pubdate": pubdate,
                                    "size": comsize_m,
                                    "tmpprov": tmpprov,
                                    "kind": kind,
                                    "booktype": booktype,
                                    "SARC": SARC,
                                    "IssueArcID": IssueArcID,
                                    "newznab": newznab_host,
                                    "torznab": torznab_host,
                                    "downloadit": downloadit,
                                    "ComicTitle": ComicTitle,
                                    "entry": entry,
                                    "provider_stat": provider_stat,
                                }

                                mylar.COMICINFO.append(search_values)

                                hold_the_matches.append(search_values)

                        else:
                            #log2file = log2file + "issues don't match.." + "\n"
                            downloadit = False
                            #foundc['status'] = False
        #logger.fdebug('returning hold_the_matches: %s' % (hold_the_matches,))
        return hold_the_matches
