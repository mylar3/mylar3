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


import mylar
from mylar import (
    logger,
    db,
    updater,
    helpers,
    findcomicfeed,
    notifiers,
    rsscheck,
    Failed,
    filechecker,
    auth32p,
    sabnzbd,
    nzbget,
    wwt,
    getcomics,
)

import feedparser
import requests
import os
import errno
import sys
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urljoin
import email.utils
import datetime
import shutil
from operator import itemgetter
from wsgiref.handlers import format_date_time
import traceback


def search_init(
    ComicName,
    IssueNumber,
    ComicYear,
    SeriesYear,
    Publisher,
    IssueDate,
    StoreDate,
    IssueID,
    AlternateSearch=None,
    UseFuzzy=None,
    ComicVersion=None,
    SARC=None,
    IssueArcID=None,
    smode=None,
    rsscheck=None,
    ComicID=None,
    manualsearch=None,
    filesafe=None,
    allow_packs=None,
    oneoff=False,
    manual=False,
    torrentid_32p=None,
    digitaldate=None,
    booktype=None,
    ignore_booktype=False,
):

    mylar.COMICINFO = []
    unaltered_ComicName = None
    if filesafe:
        if filesafe != ComicName and smode != 'want_ann':
            logger.info(
                '[SEARCH] Special Characters exist within Series Title. Enabling'
                ' search-safe Name : %s' % filesafe
            )
            if AlternateSearch is None or AlternateSearch == 'None':
                AlternateSearch = filesafe
            else:
                AlternateSearch += '##' + filesafe
            unaltered_ComicName = ComicName

    if ComicYear is None:
        ComicYear = str(datetime.datetime.now().year)
    else:
        ComicYear = str(ComicYear)[:4]
    if Publisher:
        if Publisher == 'IDW Publishing':
            Publisher = 'IDW'
        logger.fdebug('Publisher is : %s' % Publisher)

    if IssueArcID and not IssueID:
        issuetitle = helpers.get_issue_title(IssueArcID)
    else:
        issuetitle = helpers.get_issue_title(IssueID)

    if issuetitle:
        logger.fdebug('Issue Title given as : %s' % issuetitle)
    else:
        logger.fdebug('Issue Title not found. Setting to None.')

    if smode == 'want_ann':
        logger.info('Annual/Special issue search detected. Appending to issue #')
        # anything for smode other than None indicates an annual.
        #if all(['annual' not in ComicName.lower(), 'special' not in ComicName.lower()]):
        #    ComicName = '%s Annual' % ComicName
        if '2021 annual' in ComicName.lower():
            AlternateSearch= '%s Annual' % re.sub('2021 annual', '', ComicName, flags=re.I).strip()
            logger.info('Setting alternate search to %s because people are gonna people.' % AlternateSearch)

        elif all(
            [
                AlternateSearch is not None,
                AlternateSearch != "None",
                'special' not in ComicName.lower(),
            ]
        ):
            AlternateSearch = '%s Annual' % AlternateSearch

    if smode == 'pullwant' or IssueID is None:
        # one-off the download.
        logger.fdebug('One-Off Search parameters:')
        logger.fdebug('ComicName: %s' % ComicName)
        logger.fdebug('Issue: %s' % IssueNumber)
        logger.fdebug('Year: %s' % ComicYear)
        logger.fdebug('IssueDate: %s' % IssueDate)
        oneoff = True
    if SARC:
        logger.fdebug("Story-ARC Search parameters:")
        logger.fdebug("Story-ARC: %s" % SARC)
        logger.fdebug("IssueArcID: %s" % IssueArcID)

    torprovider = []
    torp = 0
    torznabs = 0
    torznab_hosts = []

    logger.fdebug("Checking for torrent enabled.")
    if mylar.CONFIG.ENABLE_TORRENT_SEARCH:
        if mylar.CONFIG.ENABLE_32P and not helpers.block_provider_check('32P'):
            torprovider.append('32p')
            torp += 1
        if mylar.CONFIG.ENABLE_PUBLIC and not helpers.block_provider_check(
            'public torrents'
        ):
            torprovider.append('public torrents')
            torp += 1
        if mylar.CONFIG.ENABLE_TORZNAB is True:
            for torznab_host in mylar.CONFIG.EXTRA_TORZNABS:
                if any([torznab_host[5] == '1', torznab_host[5] == 1]):
                    if not helpers.block_provider_check(torznab_host[0]):
                        torznab_hosts.append(torznab_host)
                        torprovider.append('torznab: %s' % torznab_host[0])
                        torznabs += 1

    # nzb provider selection##
    # 'dognzb' or 'nzb.su' or 'experimental'
    nzbprovider = []
    nzbp = 0
    if mylar.CONFIG.NZBSU is True and not helpers.block_provider_check('nzb.su'):
        nzbprovider.append('nzb.su')
        nzbp += 1
    if mylar.CONFIG.DOGNZB is True and not helpers.block_provider_check('dognzb'):
        nzbprovider.append('dognzb')
        nzbp += 1

    # --------
    #  Xperimental
    if mylar.CONFIG.EXPERIMENTAL is True and not helpers.block_provider_check(
        'experimental'
    ):
        nzbprovider.append('experimental')
        nzbp += 1

    newznabs = 0

    newznab_hosts = []

    if mylar.CONFIG.NEWZNAB is True:
        for newznab_host in mylar.CONFIG.EXTRA_NEWZNABS:
            if any([newznab_host[5] == '1', newznab_host[5] == 1]):
                if not helpers.block_provider_check(newznab_host[0]):
                    newznab_hosts.append(newznab_host)
                    nzbprovider.append('newznab: %s' % newznab_host[0])
                    newznabs += 1

    ddls = 0
    ddlprovider = []

    if mylar.CONFIG.ENABLE_DDL is True and not helpers.block_provider_check('DDL'):
        ddlprovider.append('DDL')
        ddls += 1

    logger.fdebug('nzbprovider(s): %s' % nzbprovider)
    # --------
    torproviders = torp + torznabs
    logger.fdebug('There are %s torrent providers you have selected.' % torproviders)
    torpr = torproviders - 1
    if torpr < 0:
        torpr = -1
    providercount = int(nzbp + newznabs)
    logger.fdebug('There are : %s nzb providers you have selected' % providercount)
    if providercount > 0:
        logger.fdebug('Usenet Retention : %s days' % mylar.CONFIG.USENET_RETENTION)

    if ddls > 0:
        logger.fdebug(
            'there are %s Direct Download providers that are currently enabled.' % ddls
        )
    findit = {}
    findit['status'] = False

    totalproviders = providercount + torproviders + ddls

    if totalproviders == 0:
        logger.error(
            '[WARNING] You have %s search providers enabled. I need at least ONE'
            ' provider to work. Aborting search.'
            % totalproviders
        )
        findit['status'] = False
        nzbprov = None
        return findit, nzbprov

    prov_order, torznab_info, newznab_info = provider_sequence(
        nzbprovider, torprovider, newznab_hosts, torznab_hosts, ddlprovider
    )
    # end provider order sequencing
    logger.fdebug('search provider order is %s' % prov_order)

    # fix for issue dates between Nov-Dec/(Jan-Feb-Mar)
    IssDt = str(IssueDate)[5:7]
    if any([IssDt == "12", IssDt == "11", IssDt == "01", IssDt == "02", IssDt == "03"]):
        IssDateFix = IssDt
    else:
        IssDateFix = "no"
        if StoreDate is not None:
            StDt = str(StoreDate)[5:7]
            if any(
                [
                    StDt == "10",
                    StDt == "12",
                    StDt == "11",
                    StDt == "01",
                    StDt == "02",
                    StDt == "03",
                ]
            ):
                IssDateFix = StDt

    searchcnt = 0
    srchloop = 1

    if rsscheck:
        if mylar.CONFIG.ENABLE_RSS:
            searchcnt = 1  # rss-only
        else:
            searchcnt = 1  # if it's not enabled, don't even bother.
    else:
        if mylar.CONFIG.ENABLE_RSS:
            searchcnt = 2  # rss first, then api on non-matches
        else:
            searchcnt = 2  # set the searchcnt to 2 (api)
            srchloop = 2  # start the counter at API, so itll exit without running RSS

    if IssueNumber is not None:
        findcomiciss = IssueNumber
        if '\xbd' in IssueNumber:
            findcomiciss = '0.5'
        elif '\xbc' in IssueNumber:
            findcomiciss = '0.25'
        elif '\xbe' in IssueNumber:
            findcomiciss = '0.75'
        elif '\u221e' in IssueNumber:
            # issnum = utf-8 will encode the infinity symbol without any help
            findcomiciss = 'infinity'  # set 9999999999 for integer value of issue

        # determine the amount of loops here
        fcs = 0
        c_alpha = None
        c_number = None
        dsp_c_alpha = None
        c_num_a4 = None
        while fcs < len(findcomiciss):
            # take first occurance of alpha in string and carry it through
            if findcomiciss[fcs].isalpha():
                c_alpha = findcomiciss[fcs:].rstrip()
                c_number = findcomiciss[:fcs].rstrip()
                break
            elif '.' in findcomiciss[fcs]:
                c_number = findcomiciss[:fcs].rstrip()
                c_num_a4 = findcomiciss[fcs + 1 :].rstrip()
                # if decimal seperates numeric from alpha (ie - 7.INH), don't give
                # calpha a value or else will seperate with a space further down.
                # Assign it to dsp_c_alpha so that it can be displayed for debugging.
                if not c_num_a4.isdigit():
                    dsp_c_alpha = c_num_a4
                else:
                    c_number = str(c_number) + '.' + str(c_num_a4)
                break
            fcs += 1
        logger.fdebug('calpha/cnumber: %s / %s' % (dsp_c_alpha, c_number))

        if c_number is None:
            c_number = findcomiciss  # if it's None = no special alphas or decimals

        if '.' in c_number:
            decst = c_number.find('.')
            c_number = c_number[:decst].rstrip()

    while srchloop <= searchcnt:
        """searchmodes:
        rss - will run through the built-cached db of entries
        api - will run through the providers via api (or non-api in the case of
              Experimental) the trick is if the search is done during an rss compare,
              it needs to exit when done. Ootherwise, the order of operations is rss
              feed check first, followed by api on non-results.
        """

        if srchloop == 1:
            searchmode = 'rss'  # order of ops - this will be used first.
        elif srchloop == 2:
            searchmode = 'api'

        if '0-Day' in ComicName:
            cmloopit = 1
        else:
            if booktype == 'One-Shot':
                cmloopit = 4
            elif len(c_number) == 1:
                cmloopit = 3
            elif len(c_number) == 2:
                cmloopit = 2
            else:
                cmloopit = 1

        chktpb = 0
        if any([booktype == 'TPB', booktype =='HC', booktype == 'GN']):
            chktpb = 1

        if findit['status'] is True:
            logger.fdebug('Found result on first run, exiting search module now.')
            break

        logger.fdebug('Initiating Search via : %s' % searchmode)

        if len(prov_order) == 1:
            tmp_prov_count = 1
        else:
            tmp_prov_count = len(prov_order)

        checked_once = []
        while cmloopit >= 1:
            prov_count = 0
            if cmloopit == 4:
                tmp_IssueNumber = None
            else:
                tmp_IssueNumber = IssueNumber
            searchprov = None
            while tmp_prov_count > prov_count:
                if checked_once:
                    if prov_order[prov_count] in checked_once:
                        prov_count +=1
                        continue
                provider_blocked = helpers.block_provider_check(prov_order[prov_count])
                if provider_blocked:
                    logger.warn('provider blocked. Ignoring search on this provider.')
                    prov_count += 1
                    continue
                send_prov_count = tmp_prov_count - prov_count
                newznab_host = None
                torznab_host = None
                if prov_order[prov_count] == 'DDL' and not provider_blocked:
                    searchprov = 'DDL'
                elif prov_order[prov_count] == '32p' and not provider_blocked:
                    searchprov = '32P'
                elif (
                    prov_order[prov_count] == 'public torrents' and not provider_blocked
                ):
                    searchprov = 'Public Torrents'
                elif 'torznab' in prov_order[prov_count]:
                    searchprov = 'torznab'
                    for nninfo in torznab_info:
                        if (
                            nninfo['provider'] == prov_order[prov_count]
                            and not provider_blocked
                        ):
                            torznab_host = nninfo['info']
                    if torznab_host is None:
                        logger.fdebug(
                            'there was an error - torznab information was blank and'
                            ' it should not be.'
                        )
                elif 'newznab' in prov_order[prov_count]:
                    searchprov = 'newznab'
                    for nninfo in newznab_info:
                        if (
                            nninfo['provider'] == prov_order[prov_count]
                            and not provider_blocked
                        ):
                            newznab_host = nninfo['info']
                    if newznab_host is None:
                        logger.fdebug(
                            'there was an error - newznab information was blank and it'
                            ' should not be.'
                        )
                else:
                    newznab_host = None
                    torznab_host = None
                    searchprov = prov_order[prov_count].lower()

                if searchprov == 'dognzb' and any(
                    [mylar.CONFIG.DOGNZB == 0, provider_blocked]
                ):
                    # since dognzb could hit the 100 daily api limit during the middle
                    # of a search run, check here on each pass to make sure it's not
                    # disabled (it gets auto-disabled on maxing out the API hits)
                    prov_count += 1
                    continue
                elif all(
                         [
                             not provider_blocked,
                             searchprov in checked_once,
                         ]
                    ):
                    prov_count += 1
                    continue
                if searchmode == 'rss':
                    findit = NZB_SEARCH(
                        ComicName,
                        tmp_IssueNumber,
                        ComicYear,
                        SeriesYear,
                        Publisher,
                        IssueDate,
                        StoreDate,
                        searchprov,
                        send_prov_count,
                        IssDateFix,
                        IssueID,
                        UseFuzzy,
                        newznab_host,
                        ComicVersion=ComicVersion,
                        SARC=SARC,
                        IssueArcID=IssueArcID,
                        RSS="yes",
                        ComicID=ComicID,
                        issuetitle=issuetitle,
                        unaltered_ComicName=unaltered_ComicName,
                        oneoff=oneoff,
                        cmloopit=cmloopit,
                        manual=manual,
                        torznab_host=torznab_host,
                        digitaldate=digitaldate,
                        booktype=booktype,
                        chktpb=chktpb,
                        ignore_booktype=ignore_booktype,
                        smode=smode,
                    )
                    if findit['status'] is False:
                        if AlternateSearch is not None and AlternateSearch != "None":
                            chkthealt = AlternateSearch.split('##')
                            if chkthealt == 0:
                                AS_Alternate = AlternateSearch
                            for calt in chkthealt:
                                AS_Alternate = re.sub('##', '', calt)
                                logger.info(
                                    'Alternate Search pattern detected...re-adjusting'
                                    ' to : %s' % AS_Alternate
                                )
                                findit = NZB_SEARCH(
                                    AS_Alternate,
                                    tmp_IssueNumber,
                                    ComicYear,
                                    SeriesYear,
                                    Publisher,
                                    IssueDate,
                                    StoreDate,
                                    searchprov,
                                    send_prov_count,
                                    IssDateFix,
                                    IssueID,
                                    UseFuzzy,
                                    newznab_host,
                                    ComicVersion=ComicVersion,
                                    SARC=SARC,
                                    IssueArcID=IssueArcID,
                                    RSS="yes",
                                    ComicID=ComicID,
                                    issuetitle=issuetitle,
                                    unaltered_ComicName=AS_Alternate,
                                    allow_packs=allow_packs,
                                    oneoff=oneoff,
                                    cmloopit=cmloopit,
                                    manual=manual,
                                    torznab_host=torznab_host,
                                    digitaldate=digitaldate,
                                    booktype=booktype,
                                    chktpb=chktpb,
                                    ignore_booktype=ignore_booktype,
                                    smode=smode,
                                )
                                if findit['status'] is True:
                                    break
                            if findit['status'] is True:
                                break
                    else:
                        logger.fdebug("findit = found!")
                        break

                else:
                    findit = NZB_SEARCH(
                        ComicName,
                        tmp_IssueNumber,
                        ComicYear,
                        SeriesYear,
                        Publisher,
                        IssueDate,
                        StoreDate,
                        searchprov,
                        send_prov_count,
                        IssDateFix,
                        IssueID,
                        UseFuzzy,
                        newznab_host,
                        ComicVersion=ComicVersion,
                        SARC=SARC,
                        IssueArcID=IssueArcID,
                        RSS="no",
                        ComicID=ComicID,
                        issuetitle=issuetitle,
                        unaltered_ComicName=unaltered_ComicName,
                        allow_packs=allow_packs,
                        oneoff=oneoff,
                        cmloopit=cmloopit,
                        manual=manual,
                        torznab_host=torznab_host,
                        torrentid_32p=torrentid_32p,
                        digitaldate=digitaldate,
                        booktype=booktype,
                        chktpb=chktpb,
                        ignore_booktype=ignore_booktype,
                        smode=smode,
                    )
                    if all(
                           [
                               not provider_blocked,
                               searchprov not in checked_once,
                           ]
                          ) and searchprov in (
                              '32P',
                              'DDL',
                              'Public Torrents',
                              'experimental',
                          ):
                              checked_once.append(searchprov)
                    if findit['status'] is False:
                        if AlternateSearch is not None and AlternateSearch != "None":
                            chkthealt = AlternateSearch.split('##')
                            if chkthealt == 0:
                                AS_Alternate = AlternateSearch
                            for calt in chkthealt:
                                AS_Alternate = re.sub('##', '', calt)
                                logger.info(
                                    'Alternate Search pattern detected...re-adjusting'
                                    'to : %s' % AS_Alternate
                                )
                                findit = NZB_SEARCH(
                                    AS_Alternate,
                                    tmp_IssueNumber,
                                    ComicYear,
                                    SeriesYear,
                                    Publisher,
                                    IssueDate,
                                    StoreDate,
                                    searchprov,
                                    send_prov_count,
                                    IssDateFix,
                                    IssueID,
                                    UseFuzzy,
                                    newznab_host,
                                    ComicVersion=ComicVersion,
                                    SARC=SARC,
                                    IssueArcID=IssueArcID,
                                    RSS="no",
                                    ComicID=ComicID,
                                    issuetitle=issuetitle,
                                    unaltered_ComicName=unaltered_ComicName,
                                    allow_packs=allow_packs,
                                    oneoff=oneoff,
                                    cmloopit=cmloopit,
                                    manual=manual,
                                    torznab_host=torznab_host,
                                    torrentid_32p=torrentid_32p,
                                    digitaldate=digitaldate,
                                    booktype=booktype,
                                    chktpb=chktpb,
                                    ignore_booktype=ignore_booktype,
                                    smode=smode,
                                )
                                if findit['status'] is True:
                                    break
                            if findit['status'] is True:
                                break
                    else:
                        logger.fdebug("findit = found!")
                        break

                if searchprov == 'newznab':
                    searchprov = newznab_host[0].rstrip()
                elif searchprov == 'torznab':
                    searchprov = torznab_host[0].rstrip()
                if manual is not True:
                    if tmp_IssueNumber is not None:
                        issuedisplay = tmp_IssueNumber
                    else:
                        if any(
                               [
                                   booktype == 'One-Shot',
                                   booktype == 'TPB',
                                   booktype == 'HC',
                                   booktype == 'GC'
                               ]
                        ):
                            issuedisplay = None
                        else:
                            issuedisplay = StoreDate[5:]
                    if issuedisplay is None:
                        logger.info(
                            'Could not find %s (%s) using %s [%s]'
                            % (ComicName, SeriesYear, searchprov, searchmode)
                        )
                    else:
                        logger.info(
                            'Could not find Issue %s of %s (%s) using %s [%s]'
                            % (
                                issuedisplay,
                                ComicName,
                                SeriesYear,
                                searchprov,
                                searchmode,
                            )
                        )
                prov_count += 1

            if findit['status'] is True:
                if searchprov == 'newznab':
                    searchprov = newznab_host[0].rstrip() + ' (newznab)'
                elif searchprov == 'torznab':
                    searchprov = torznab_host[0].rstrip() + ' (torznab)'
                srchloop = 4
                break
            elif srchloop == 2 and (cmloopit - 1 >= 1) and searchprov not in checked_once:
                time.sleep(30)  # pause for 30s to not hammmer api's

            cmloopit -= 1

        srchloop += 1

    if manual is True:
        logger.info(
            'I have matched %s files: %s' % (len(mylar.COMICINFO), mylar.COMICINFO)
        )
        return mylar.COMICINFO, 'None'

    if findit['status'] is True:
        # check for snatched_havetotal being enabled here and adjust counts now.
        # IssueID being the catch/check for one-offs as they won't exist on the
        # watchlist and error out otherwise.
        if mylar.CONFIG.SNATCHED_HAVETOTAL and any(
            [oneoff is False, IssueID is not None]
        ):
            logger.fdebug('Adding this to the HAVE total for the series.')
            helpers.incr_snatched(ComicID)
        if searchprov == 'Public Torrents' and mylar.TMP_PROV != searchprov:
            searchprov = mylar.TMP_PROV
        return findit, searchprov
    else:
        logger.fdebug('findit: %s' % findit)
        if manualsearch is None:
            logger.info(
                'Finished searching via : %s. Issue not found - status kept as Wanted.'
                % searchmode
            )
        else:
            logger.fdebug(
                'Could not find issue doing a manual search via : %s' % searchmode
            )
        if searchprov == '32P':
            if mylar.CONFIG.MODE_32P == 0:
                return findit, 'None'
            elif mylar.CONFIG.MODE_32P == 1 and searchmode == 'api':
                return findit, 'None'

    return findit, 'None'


def NZB_SEARCH(
    ComicName,
    IssueNumber,
    ComicYear,
    SeriesYear,
    Publisher,
    IssueDate,
    StoreDate,
    nzbprov,
    prov_count,
    IssDateFix,
    IssueID,
    UseFuzzy,
    newznab_host=None,
    ComicVersion=None,
    SARC=None,
    IssueArcID=None,
    RSS=None,
    ComicID=None,
    issuetitle=None,
    unaltered_ComicName=None,
    allow_packs=None,
    oneoff=False,
    cmloopit=None,
    manual=False,
    torznab_host=None,
    torrentid_32p=None,
    digitaldate=None,
    booktype=None,
    chktpb=0,
    ignore_booktype=False,
    smode=None
):

    if any([allow_packs == 1, allow_packs == '1']) and all(
        [mylar.CONFIG.ENABLE_TORRENT_SEARCH, mylar.CONFIG.ENABLE_32P]
    ):
        allow_packs = True
    else:
        allow_packs = False
    newznab_local = False
    untouched_name = None
    if nzbprov == 'nzb.su':
        apikey = mylar.CONFIG.NZBSU_APIKEY
        verify = bool(mylar.CONFIG.NZBSU_VERIFY)
    elif nzbprov == 'dognzb':
        apikey = mylar.CONFIG.DOGNZB_APIKEY
        verify = bool(mylar.CONFIG.DOGNZB_VERIFY)
    elif nzbprov == 'experimental':
        apikey = 'none'
        verify = False
    elif nzbprov == 'torznab':
        name_torznab = torznab_host[0].rstrip()
        host_torznab = torznab_host[1].rstrip()
        verify = bool(torznab_host[2])
        apikey = torznab_host[3].rstrip()
        category_torznab = torznab_host[4]
        if any([category_torznab is None, category_torznab == 'None']):
            category_torznab = '8020'
        if '#' in category_torznab:
            t_cats = category_torznab.split('#')
            category_torznab = ','.join(t_cats)
        logger.fdebug('Using Torznab host of : %s' % name_torznab)
    elif nzbprov == 'newznab':
        # updated to include Newznab Name now
        name_newznab = newznab_host[0].rstrip()
        host_newznab = newznab_host[1].rstrip()
        untouched_name = name_newznab
        if name_newznab[-7:] == '[local]':
            name_newznab = name_newznab[:-7].strip()
            newznab_local = True
        elif name_newznab[-10:] == '[nzbhydra]':
            name_newznab = name_newznab[:-10].strip()
            newznab_local = False
        apikey = newznab_host[3].rstrip()
        verify = bool(newznab_host[2])
        if '#' in newznab_host[4].rstrip():
            catstart = newznab_host[4].find('#')
            category_newznab = re.sub('#', ',', newznab_host[4][catstart + 1 :]).strip()
            logger.fdebug('Non-default Newznab category set to : %s' % category_newznab)
        else:
            category_newznab = '7030'
        logger.fdebug('Using Newznab host of : %s' % name_newznab)

    if RSS == "yes":
        if 'newznab' in nzbprov:
            tmpprov = '%s (%s) [RSS]' % (name_newznab, nzbprov)
        elif 'torznab' in nzbprov:
            tmpprov = '%s (%s) [RSS]' % (name_torznab, nzbprov)
        else:
            tmpprov = '%s [RSS]' % nzbprov
    else:
        if 'newznab' in nzbprov:
            tmpprov = '%s (%s)' % (name_newznab, nzbprov)
        elif 'torznab' in nzbprov:
            tmpprov = '%s (%s)' % (name_torznab, nzbprov)
        else:
            tmpprov = nzbprov
    if cmloopit == 4:
        issuedisplay = None
        logger.info(
            'Shhh be very quiet...I\'m looking for %s (%s) using %s.'
            % (ComicName, ComicYear, tmpprov)
        )
    elif IssueNumber is not None:
        issuedisplay = IssueNumber
    else:
        issuedisplay = StoreDate[5:]

    if '0-Day Comics Pack' in ComicName:
        logger.info(
            'Shhh be very quiet...I\'m looking for %s using %s.' % (ComicName, tmpprov)
        )
    elif cmloopit != 4:
        logger.info(
            'Shhh be very quiet...I\'m looking for %s issue: %s (%s) using %s.'
            % (ComicName, issuedisplay, ComicYear, tmpprov)
        )

    comsearch = []
    isssearch = []
    comyear = str(ComicYear)
    findcomic = ComicName

    cm1 = re.sub(r'[\/\-]', ' ', findcomic)
    # remove 'and' & '&' from the search pattern entirely
    # (broader results, will filter out later)
    cm = re.sub("\\band\\b", "", cm1.lower())

    # remove 'the' from the search pattern to accomodate naming differences
    cm = re.sub("\\bthe\\b", "", cm.lower())

    cm = re.sub(r'[\&\:\?\,]', '', str(cm))
    cm = re.sub(r'\s+', ' ', cm)
    # replace whitespace in comic name with %20 for api search
    cm = re.sub(" ", "%20", str(cm))
    cm = re.sub("'", "%27", str(cm))

    if IssueNumber is not None:
        intIss = helpers.issuedigits(IssueNumber)
        iss = IssueNumber
        if '\xbd' in IssueNumber:
            findcomiciss = '0.5'
        elif '\xbc' in IssueNumber:
            findcomiciss = '0.25'
        elif '\xbe' in IssueNumber:
            findcomiciss = '0.75'
        elif '\u221e' in IssueNumber:
            # issnum = utf-8 will encode the infinity symbol without any help
            findcomiciss = 'infinity'  # set 9999999999 for integer value of issue
        else:
            findcomiciss = iss

        isssearch = str(findcomiciss)
    else:
        intIss = None
        isssearch = None
        findcomiciss = None

    comsearch = cm
    findcount = 1  # this could be a loop in the future possibly

    findloop = 0
    foundcomic = []
    foundc = {}
    foundc['status'] = False
    done = False
    # origcmloopit = cmloopit
    # seperatealpha = "no"
    hold_the_matches = []
    # ---issue problem
    # if issue is '011' instead of '11' in nzb search results, will not have same
    # results. '011' will return different than '11', as will '009' and '09'.
    while findloop < findcount:
        logger.fdebug('findloop: %s / findcount: %s' % (findloop, findcount))
        comsrc = comsearch
        if nzbprov == 'dognzb' and not mylar.CONFIG.DOGNZB:
            foundc['status'] = False
            done = True
            break
        if any([nzbprov == '32P', nzbprov == 'Public Torrents', nzbprov == 'DDL']):
            # 32p directly stores the exact issue, no need to iterate over variations
            # of the issue number. DDL iteration is handled in it's own module.
            findloop = 99

        if done is True:  # and seperatealpha == "no":
            logger.fdebug("we should break out now - sucessful search previous")
            findloop = 99
            break

            # here we account for issue pattern variations
        if IssueNumber is not None:
            # if seperatealpha == "yes":
            #     isssearch = str(c_number) + "%20" + str(c_alpha)
            if cmloopit == 3:
                comsearch = comsrc + "%2000" + str(isssearch)
                issdig = '00'
            elif cmloopit == 2:
                comsearch = comsrc + "%200" + str(isssearch)
                issdig = '0'
            elif cmloopit == 1:
                comsearch = comsrc + "%20" + str(isssearch)
                issdig = ''
                if chktpb == 1:
                    # this will open end the search based on just the series title,
                    # no issue number, & no volume. Putting it at the last search option
                    # and ONLY for tpb items hopefully will help it not retrieve 1000's.
                    comsearch = comsrc
                    chktpb += 1
            else:
                foundc['status'] = False
                done = True
                break
            mod_isssearch = str(issdig) + str(isssearch)
        else:
            if cmloopit == 4:
                if any([booktype == 'TPB', booktype == 'HC', booktype == 'GN']):
                    comsearch = comsrc + "%20v" + str(isssearch)
                mod_isssearch = ''
            else:
                comsearch = StoreDate
                mod_isssearch = StoreDate

        if nzbprov == 'DDL' and RSS == "no":
            cmname = re.sub("%20", " ", str(comsrc))
            logger.fdebug(
                'Sending request to DDL site for : %s %s' % (findcomic, isssearch)
            )
            if any([isssearch == 'None', isssearch is None]):
                lineq = findcomic
            else:
                lineq = '%s %s' % (findcomic, isssearch)
            fline = {'comicname': findcomic,
                     'issue':     isssearch,
                     'year':      comyear}
            b = getcomics.GC(query=fline)
            bb = b.search()
        elif RSS == "yes":
            if nzbprov == 'DDL':
                logger.fdebug(
                    'Sending request to [%s] RSS for %s : %s'
                    % (nzbprov, ComicName, mod_isssearch)
                )
                bb = rsscheck.ddl_dbsearch(
                    ComicName, mod_isssearch, ComicID, nzbprov, oneoff
                )
            elif nzbprov == '32P' or nzbprov == 'Public Torrents':
                cmname = re.sub("%20", " ", str(comsrc))
                logger.fdebug(
                    'Sending request to [%s] RSS for %s : %s'
                    % (nzbprov, ComicName, mod_isssearch)
                )
                bb = rsscheck.torrentdbsearch(
                    ComicName, mod_isssearch, ComicID, nzbprov, oneoff
                )
            else:
                logger.fdebug(
                    'Sending request to RSS for %s : %s (%s)'
                    % (findcomic, mod_isssearch, ComicYear)
                )
                if untouched_name is not None:
                    nzbprov_fix = untouched_name
                elif nzbprov == 'newznab':
                    nzbprov_fix = name_newznab
                elif nzbprov == 'torznab':
                    nzbprov_fix = name_torznab
                else:
                    nzbprov_fix = nzbprov
                bb = rsscheck.nzbdbsearch(
                    findcomic,
                    mod_isssearch,
                    ComicID,
                    nzbprov_fix,
                    ComicYear,
                    ComicVersion,
                    oneoff,
                )
            if bb is None:
                bb = 'no results'
        # this is the API calls
        else:
            # 32P is redudant now since only RSS works
            # - just getting it ready for when it's not redudant :)
            if nzbprov == '':
                bb = "no results"
            if nzbprov == '32P':
                if all([mylar.CONFIG.MODE_32P == 1, mylar.CONFIG.ENABLE_32P is True]):
                    if ComicName[:17] == '0-Day Comics Pack':
                        searchterm = {
                            'series': ComicName,
                            'issue': StoreDate[8:10],
                            'volume': StoreDate[5:7],
                            'torrentid_32p': None,
                        }
                    else:
                        searchterm = {
                            'series': ComicName,
                            'id': ComicID,
                            'issue': findcomiciss,
                            'volume': ComicVersion,
                            'publisher': Publisher,
                            'torrentid_32p': torrentid_32p,
                            'booktype': booktype,
                        }

                    # first we find the id on the serieslist of 32P
                    # then call the ajax against the id & issue# and volume (if exists)
                    a = auth32p.info32p(searchterm=searchterm)
                    bb = a.searchit()
                    try:
                        if bb['status'] is False:
                            helpers.disable_provider(nzbprov, bb['error'])
                        bb = bb['results']
                        if any([bb is None, bb == 'no results']):
                            bb = 'no results'
                    except Exception as e:
                        logger.fdebug('No applicable results returned: %s' % e)
                        bb = 'no results'
                else:
                    bb = "no results"
            elif nzbprov == 'Public Torrents':
                cmname = re.sub("%20", " ", str(comsrc))
                logger.fdebug(
                    'Sending request to [WWT-SEARCH] for %s : %s'
                    % (cmname, mod_isssearch)
                )
                ww = wwt.wwt(cmname, mod_isssearch)
                bb = ww.wwt_connect()
                if bb is None:
                    bb = 'no results'
            elif nzbprov != 'experimental':
                if nzbprov == 'dognzb':
                    findurl = (
                        "https://api.dognzb.cr/api?t=search&q="
                        + str(comsearch)
                        + "&o=xml&cat=7030"
                    )
                elif nzbprov == 'nzb.su':
                    findurl = (
                        "https://api.nzb.su/api?t=search&q="
                        + str(comsearch)
                        + "&o=xml&cat=7030"
                    )
                elif nzbprov == 'newznab':
                    # let's make sure the host has a '/' at the end, if not add it.
                    host_newznab_fix = host_newznab
                    if not host_newznab_fix.endswith('api'):
                        if not host_newznab_fix.endswith('/'):
                            host_newznab_fix += '/'
                        host_newznab_fix = urljoin(host_newznab_fix, 'api')
                    findurl = '%s?t=search&q=%s&o=xml&cat=%s' % (
                        host_newznab_fix,
                        comsearch,
                        category_newznab,
                    )
                elif nzbprov == 'torznab':
                    if host_torznab[len(host_torznab) - 1 : len(host_torznab)] == '/':
                        torznab_fix = host_torznab[:-1]
                    else:
                        torznab_fix = host_torznab
                    findurl = str(torznab_fix) + "?t=search&q=" + str(comsearch)
                    if category_torznab is not None:
                        findurl += "&cat=" + str(category_torznab)
                else:
                    logger.warn(
                        'You have a blank newznab entry within your configuration.'
                        'Remove it, save the config and restart mylar to fix things.'
                        'Skipping this blank provider until fixed.'
                    )
                    findurl = None
                    bb = "noresults"

                if findurl:
                    # helper function to replace apikey here so we avoid logging it ;)
                    findurl = findurl + "&apikey=" + str(apikey)
                    logsearch = helpers.apiremove(str(findurl), 'nzb')

                    # IF USENET_RETENTION is set, honour it
                    # For newznab sites, that means appending "&maxage=<whatever>"
                    # on the URL
                    if (
                        mylar.CONFIG.USENET_RETENTION is not None
                        and nzbprov != 'torznab'
                    ):
                        findurl = (
                            findurl + "&maxage=" + str(mylar.CONFIG.USENET_RETENTION)
                        )

                    # set a delay between searches here. Default is for 30 seconds...
                    # changing this to lower could result in a ban from your nzb source
                    # due to hammering.
                    if (
                        mylar.CONFIG.SEARCH_DELAY == 'None'
                        or mylar.CONFIG.SEARCH_DELAY is None
                    ):
                        pause_the_search = 30  # in seconds
                    elif str(mylar.CONFIG.SEARCH_DELAY).isdigit() and manual is False:
                        pause_the_search = int(mylar.CONFIG.SEARCH_DELAY) * 60
                    else:
                        logger.warn(
                            'Check Search Delay - invalid numerical given.'
                            ' Force-setting to 30 seconds.'
                        )
                        pause_the_search = 30

                    # bypass for local newznabs
                    # remove the protocol string (http/https)
                    localbypass = False
                    if nzbprov == 'newznab':
                        if host_newznab_fix.startswith('http'):
                            hnc = host_newznab_fix.replace('http://', '')
                        elif host_newznab_fix.startswith('https'):
                            hnc = host_newznab_fix.replace('https://', '')
                        else:
                            hnc = host_newznab_fix

                        if (
                            any(
                                [
                                    hnc[:3] == '10.',
                                    hnc[:4] == '172.',
                                    hnc[:4] == '192.',
                                    hnc.startswith('localhost'),
                                    newznab_local is True,
                                ]
                            )
                            and newznab_local is not False
                        ):
                            logger.fdebug(
                                'local domain bypass for %s is active.' % name_newznab
                            )
                            localbypass = True

                    if localbypass is False:
                        logger.info(
                            'Pausing for %s seconds before continuing to'
                            ' avoid hammering.' % pause_the_search
                        )
                        # time.sleep(pause_the_search)

                    # Add a user-agent
                    headers = {'User-Agent': str(mylar.USER_AGENT)}
                    payload = None

                    if findurl.startswith('https:') and verify is False:
                        try:
                            from requests.packages.urllib3 import disable_warnings

                            disable_warnings()
                        except Exception as e:
                            logger.warn(
                                'Unable to disable https warnings. Expect some spam if'
                                'using https nzb providers.' % e
                            )

                    elif findurl.startswith('http:') and verify is True:
                        verify = False

                    # logger.fdebug('[SSL: ' + str(verify) + '] Search URL: ' + findurl)
                    logger.fdebug('[SSL: %s] Search URL: %s' % (verify, logsearch))

                    try:
                        r = requests.get(
                            findurl, params=payload, verify=verify, headers=headers
                        )
                        r.raise_for_status()
                    except requests.exceptions.Timeout as e:
                        logger.warn(
                            'Timeout occured fetching data from %s: %s' % (nzbprov, e)
                        )
                        foundc['status'] = False
                        break
                    except requests.exceptions.ConnectionError as e:
                        logger.warn(
                            'Connection error trying to retrieve data from %s: %s'
                            % (nzbprov, e)
                        )
                        logger.warn(
                            '[%s]Connection error trying to retrieve data from %s: %s'
                            % (errno, nzbprov, e)
                        )
                        if any(
                            [
                                errno.ETIMEDOUT,
                                errno.ECONNREFUSED,
                                errno.EHOSTDOWN,
                                errno.EHOSTUNREACH,
                            ]
                        ):
                            helpers.disable_provider(tmpprov, 'Connection Refused.')
                        foundc['status'] = False
                        break
                    except requests.exceptions.RequestException as e:
                        logger.warn(
                            '[%s]General Error fetching data from %s: %s'
                            % (errno.errorcode, nzbprov, e)
                        )
                        if any(
                            [
                                errno.ETIMEDOUT,
                                errno.ECONNREFUSED,
                                errno.EHOSTDOWN,
                                errno.EHOSTUNREACH,
                            ]
                        ):
                            helpers.disable_provider(tmpprov, 'Connection Refused.')
                            logger.warn(
                                'Aborting search due to Provider unavailability'
                            )
                            foundc['status'] = False
                        break

                    try:
                        if str(r.status_code) != '200':
                            logger.warn(
                                'Unable to retrieve search results from %s'
                                '[Status Code returned: %s]' % (tmpprov, r.status_code)
                            )
                            if any(
                                [
                                    str(r.status_code) == '503',
                                    str(r.status_code) == '404',
                                ]
                            ):
                                logger.warn(
                                    'Unavailable indexer detected. Disabling for a'
                                    ' short duration and will try again.'
                                )
                                helpers.disable_provider(tmpprov, 'Unavailable Indexer')
                            data = False
                        else:
                            data = r.content
                    except Exception as e:
                        logger.warn('[ERROR] %s' % e)
                        data = False

                    if data:
                        bb = feedparser.parse(data)
                    else:
                        bb = "no results"

                    try:
                        if bb == 'no results':
                            logger.fdebug(
                                'No results for search query from %s' % tmpprov
                            )
                            break
                        elif bb['feed']['error']:
                            logger.error(
                                '[ERROR CODE: %s] %s'
                                % (
                                    bb['feed']['error']['code'],
                                    bb['feed']['error']['description'],
                                )
                            )
                            if bb['feed']['error']['code'] == '910':
                                logger.warn(
                                    'DAILY API limit reached. Disabling %s' % tmpprov
                                )
                                helpers.disable_provider(tmpprov, 'API Limit reached')
                                foundc['status'] = False
                                done = True
                            else:
                                logger.warn(
                                    'API Error. Check the error message and take action'
                                    ' if required.'
                                )
                                foundc['status'] = False
                                done = True
                            break
                    except Exception:
                        logger.fdebug('no errors on data retrieval...proceeding')
                        pass
            elif nzbprov == 'experimental':
                logger.info('sending %s to experimental search' % findcomic)
                bb = findcomicfeed.Startit(
                    findcomic, isssearch, comyear, ComicVersion, IssDateFix, booktype
                )
                if bb == 'disable':
                    helpers.disable_provider('experimental', 'unresponsive / down')
                    foundc['status'] = False
                    done = True
                # since the regexs in findcomicfeed do the 3 loops,
                # lets force the exit after
                cmloopit == 1

        done = False
        log2file = ""
        pack0day = False
        pack_warning = False
        if not bb == "no results":
            for entry in bb['entries']:
                alt_match = False
                # logger.fdebug('entry: %s' % entry)
                # ^^^ uncomment the above line to see what the search result(s) are
                # brief match here against 32p since it returns the direct issue number
                if nzbprov == '32P' and entry['title'][:17] == '0-Day Comics Pack':
                    logger.info(
                        '[32P-0DAY] 0-Day Comics Pack Discovered. Analyzing the'
                        ' pack info...'
                    )
                    if len(bb['entries']) == 1 or pack0day is True:
                        logger.info(
                            '[32P-0DAY] Only one pack for the week available. Selecting'
                            ' this by default.'
                        )
                    else:
                        logger.info(
                            '[32P-0DAY] More than one pack for the week is available...'
                        )
                        logger.fdebug('bb-entries: %s' % bb['entries'])
                        if bb['entries'][1]['int_pubdate'] >= bb['int_pubdate']:
                            logger.info(
                                '[32P-0DAY] 2nd Pack is newest. Snatching that...'
                            )
                            pack0day = True
                            continue
                elif nzbprov == '32P' and RSS == 'no':
                    if entry['pack'] == '0':
                        if helpers.issuedigits(entry['issues']) == intIss:
                            logger.fdebug(
                                '32P direct match to issue # : %s' % entry['issues']
                            )
                        else:
                            logger.fdebug(
                                'The search result issue [%s] does not match up for'
                                ' some reason to our search result [%s]'
                                % (entry['issues'], findcomiciss)
                            )
                            continue
                    elif (
                        any([entry['pack'] == '1', entry['pack'] == '2'])
                        and allow_packs is False
                    ):
                        if pack_warning is False:
                            logger.fdebug(
                                '(possibly more than one) Pack detected, but option not'
                                ' enabled for this series. Ignoring subsequent pack'
                                ' results (to enable: on the series details page ->'
                                ' Edit Settings -> Enable Pack Downloads)'
                            )
                            pack_warning = True
                        continue

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
                            len(subs) >= len(ComicName.split())
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

                comsize_m = 0
                if nzbprov != "dognzb":
                    # rss for experimental doesn't have the size constraints embedded.
                    # So we do it here.
                    if RSS == "yes":
                        if nzbprov == '32P':
                            try:
                                # newer rss feeds will now return filesize from 32p.
                                # Safe-guard it incase it's an older result
                                comsize_b = entry['length']
                            except Exception:
                                comsize_b = None
                        elif nzbprov == 'Public Torrents':
                            comsize_b = entry['length']
                        else:
                            comsize_b = entry['length']
                    else:
                        # Experimental already has size constraints done.
                        if nzbprov == '32P':
                            comsize_b = entry['filesize']
                        elif nzbprov == 'Public Torrents':
                            comsize_b = entry['size']
                        elif nzbprov == 'experimental':
                            # we only want the size from the rss as
                            # the search/api has it already.
                            comsize_b = entry['length']
                        else:
                            try:
                                if entry['site'] == 'WWT':
                                    comsize_b = entry['size']
                                elif entry['site'] == 'DDL':
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
                    # only works with TPSE (done here) & 32P (done in rsscheck) &
                    # Experimental (has it embeded in search and rss checks)
                    if nzbprov == 'Public Torrents' or (
                        nzbprov == '32P'
                        and RSS == 'no'
                        and entry['title'][:17] != '0-Day Comics Pack'
                    ):
                        if nzbprov == 'Public Torrents':
                            if 'cbr' in entry['title'].lower():
                                format_type = 'cbr'
                            elif 'cbz' in entry['title'].lower():
                                format_type = 'cbz'
                            else:
                                format_type = 'unknown'
                        else:
                            if 'cbr' in entry['format']:
                                format_type = 'cbr'
                            elif 'cbz' in entry['format']:
                                format_type = 'cbz'
                            else:
                                format_type = 'unknown'
                        if mylar.CONFIG.PREFERRED_QUALITY == 1:
                            if format_type == 'cbr':
                                logger.fdebug(
                                    'Quality restriction enforced [ .cbr only ].'
                                    ' Accepting result.'
                                )
                            else:
                                logger.fdebug(
                                    'Quality restriction enforced [ .cbr only ].'
                                    ' Rejecting this result.'
                                )
                                continue
                        elif mylar.CONFIG.PREFERRED_QUALITY == 2:
                            if format_type == 'cbz':
                                logger.fdebug(
                                    'Quality restriction enforced [ .cbz only ].'
                                    ' Accepting result.'
                                )
                            else:
                                logger.fdebug(
                                    'Quality restriction enforced [ .cbz only ].'
                                    ' Rejecting this result.'
                                )
                                continue

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

                if mylar.CONFIG.IGNORE_COVERS is True and 'coveronly' in re.sub(
                    r'[\s\s+\_\.]', '', entry['title'].lower(), re.UNICODE
                ):
                    logger.fdebug('Cover only detected. Ignoring result.')
                    continue

                # ---- date constaints.
                # if the posting date is prior to the publication date,
                # dump it and save the time.
                # logger.fdebug('entry: %s' % entry)
                if nzbprov == 'experimental' or nzbprov == '32P':
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
                    if all([nzbprov == '32P', RSS == 'no']) or all(
                        [nzbprov == 'DDL', len(pubdate) == 10]
                    ):
                        postdate_int = pubdate
                        logger.fdebug(
                            '[%s] postdate_int (%s): %s'
                            % (nzbprov, type(postdate_int), postdate_int)
                        )
                    if any(
                        [postdate_int is None, type(postdate_int) != int]
                    ) or not all([nzbprov == '32P', RSS == 'no']):
                        # convert it to a tuple
                        dateconv = email.utils.parsedate_tz(pubdate)
                        if all([nzbprov == '32P', dateconv is None, RSS == 'no']):
                            try:
                                pubdate = email.utils.formatdate(
                                    entry['int_pubdate'], localtime=True, usegmt=False
                                )
                            except Exception as e:
                                logger.warn(
                                    '[%s] Unable to parse the date [%s] to a long-date'
                                    % (e, entry['int_pubdate'])
                                )
                            else:
                                logger.fdebug(
                                    'Successfully converted to : %s' % pubdate
                                )
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

                # if it's coming from 32P, remove the ' -' at the end as it screws it up
                if nzbprov == '32P':
                    if cleantitle.endswith(' - '):
                        cleantitle = cleantitle[:-3]
                        logger.fdebug('Cleaned up title to : %s' % cleantitle)

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
                        [booktype == 'One-Shot', parsed_comic['booktype'] == 'issue']
                    )
                    or all(
                        [booktype != parsed_comic['booktype'], ignore_booktype is True]
                    )
                    or booktype in parsed_comic['booktype']
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

                yearmatch = "false"
                if vers4vol != "no" or vers4year != "no":
                    logger.fdebug(
                        'Series Year not provided but Series Volume detected of %s.'
                        ' Bypassing Year Match.'
                        % fndcomicversion
                    )
                    yearmatch = "true"
                elif ComVersChk == 0 and parsed_comic['issue_year'] is None:
                    logger.fdebug(
                        'Series version detected as V1 (only series in existance with'
                        ' that title). Bypassing Year/Volume check'
                    )
                    yearmatch = "true"
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
                            yearmatch = "true"
                        else:
                            logger.fdebug(
                                '%s - not right - years do not match' % comyear
                            )
                            yearmatch = "false"
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
                                    yearmatch = "true"
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
                                        yearmatch = "true"
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
                                        yearmatch = "true"
                                    else:
                                        logger.fdebug(
                                            '%s - not the right year.' % comyear
                                        )
                elif UseFuzzy == "1":
                    yearmatch = "true"

                if yearmatch == "false":
                    continue

                annualize = "false"
                if 'annual' in ComicName.lower():
                    logger.fdebug(
                        "IssueID of : %s This is an annual...let's adjust." % IssueID
                    )
                    annualize = "true"

                F_ComicVersion = None

                if versionfound == "yes":
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
                    if SeriesYear is None:
                        S_ComicVersion = 0
                    else:
                        S_ComicVersion = str(SeriesYear)

                    F_ComicVersion = re.sub("[^0-9]", "", fndcomicversion)
                    # if found volume is a vol.0, up it to vol.1 (since there is no V0)
                    if F_ComicVersion == '0':
                        # need to convert dates to just be yyyy-mm-dd and do comparison,
                        # time operator in the below calc
                        F_ComicVersion = '1'
                        if postdate_int is not None:
                            if digitaldate != '0000-00-00' and all(
                                [postdate_int >= digitaldate_int, nzbprov == '32P']
                            ):
                                logger.fdebug(
                                    '32P torrent discovery. Posting date (%s) is after'
                                    ' DIGITAL store date (%s), forcing volume label to'
                                    ' be the same as series label (0-Day Enforcement):'
                                    ' v%s --> v%s'
                                    % (
                                        pubdate,
                                        digitaldate,
                                        F_ComicVersion,
                                        S_ComicVersion,
                                    )
                                )
                                F_ComicVersion = D_ComicVersion
                            elif all([postdate_int >= issuedate_int, nzbprov == '32P']):
                                logger.fdebug(
                                    '32P torrent discovery. Posting date (%s) is after'
                                    ' store date (%s), forcing volume label to be the'
                                    ' same as series label (0-Day Enforcement): v%s'
                                    ' --> v%s'
                                    % (pubdate, stdate, F_ComicVersion, S_ComicVersion)
                                )
                                F_ComicVersion = D_ComicVersion
                            else:
                                pass
                    logger.fdebug('FCVersion: %s' % F_ComicVersion)
                    logger.fdebug('DCVersion: %s' % D_ComicVersion)
                    logger.fdebug('SCVersion: %s' % S_ComicVersion)

                    # here's the catch, sometimes annuals get posted as the Pub Year
                    # instead of the Series they belong to (V2012 vs V2013)
                    if annualize == "true" and int(ComicYear) == int(F_ComicVersion):
                        logger.fdebug(
                            "We matched on versions for annuals %s" % fndcomicversion
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
                            ) and (
                                int(F_ComicVersion) == int(findcomiciss)
                                and filecomic['justthedigits'] is None
                        ):
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

                if nzbprov == 'Public Torrents' and any(
                    [entry['site'] == 'WWT', entry['site'] == 'DEM']
                ):
                    if entry['site'] == 'WWT':
                        nzbprov = 'WWT'
                    else:
                        nzbprov = 'DEM'

                if all([nzbprov == '32P', allow_packs is True, RSS == 'no']):
                    logger.fdebug('pack: %s' % entry['pack'])
                if (
                    all([nzbprov == '32P', RSS == 'no', allow_packs is True])
                    and any([entry['pack'] == '1', entry['pack'] == '2'])
                ) or (all([nzbprov == 'DDL', pack_test is True])):
                    if nzbprov == '32P':
                        if entry['pack'] == '2':
                            logger.fdebug(
                                '[PACK-QUEUE] Diamond FreeLeech Pack detected.'
                            )
                        elif entry['pack'] == '1':
                            logger.fdebug(
                                '[PACK-QUEUE] Normal Pack detected. Checking available'
                                ' inkdrops prior to downloading.'
                            )
                        else:
                            logger.fdebug('[PACK-QUEUE] Invalid Pack.')
                    else:
                        logger.fdebug(
                            '[PACK-QUEUE] DDL Pack detected for %s.' % entry['filename']
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
                    if all([nzbprov == 'DDL', 'getcomics' in entry['link']]):
                        nzbid = entry['id']
                    else:
                        nzbid = generate_id(nzbprov, entry['link'])
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
                            "size": comsize_m,
                            "tmpprov": tmpprov,
                            "kind": kind,
                            "SARC": SARC,
                            "booktype": booktype,
                            "IssueArcID": IssueArcID,
                            "newznab": newznab_host,
                            "torznab": torznab_host,
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
                                intIss = 9999999999
                        if filecomic['justthedigits'] is not None:
                            logger.fdebug(
                                "issue we found for is : %s"
                                % filecomic['justthedigits']
                            )
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
                        ):
                            nowrite = False
                            if all(
                                [
                                    nzbprov == 'torznab',
                                    'worldwidetorrents' in entry['link'],
                                ]
                            ):
                                nzbid = generate_id(nzbprov, entry['id'])
                            elif all(
                                [nzbprov == 'DDL', 'getcomics' in entry['link']]
                            ) or all([nzbprov == 'DDL', RSS == 'yes']):
                                if RSS == "yes":
                                    entry['id'] = entry['link']
                                    entry['link'] = 'https://getcomics.info/?p=' + str(
                                        entry['id']
                                    )
                                    entry['filename'] = entry['title']
                                if '/cat/' in entry['link']:
                                    entry['link'] = 'https://getcomics.info/?p=' + str(
                                        entry['id']
                                    )
                                nzbid = entry['id']
                                entry['title'] = entry['filename']
                            else:
                                nzbid = generate_id(nzbprov, entry['link'])
                                try:
                                    entry['link'] = entry.enclosures[0]['url']
                                except Exception:
                                    pass
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
                                    "size": comsize_m,
                                    "tmpprov": tmpprov,
                                    "kind": kind,
                                    "booktype": booktype,
                                    "SARC": SARC,
                                    "IssueArcID": IssueArcID,
                                    "newznab": newznab_host,
                                    "torznab": torznab_host,
                                }

                                mylar.COMICINFO.append(search_values)

                                hold_the_matches.append(search_values)

                        else:
                            log2file = log2file + "issues don't match.." + "\n"
                            downloadit = False
                            foundc['status'] = False

                # logger.fdebug('mylar.COMICINFO: %s' % mylar.COMICINFO)
                if downloadit:
                    try:
                        if entry['chkit']:
                            helpers.checkthe_id(ComicID, entry['chkit'])
                    except Exception:
                        pass

                    # generate nzbname
                    nzbname = nzbname_create(
                        nzbprov, info=mylar.COMICINFO, title=ComicTitle
                    )
                    if nzbname is None:
                        logger.error(
                            '[NZBPROVIDER = NONE] Encountered an error using given '
                            'provider with requested information: %s. You have a blank '
                            'entry most likely in your newznabs, fix it & restart Mylar'
                            % mylar.COMICINFO
                        )
                        continue
                    # generate the send-to and actually send the nzb / torrent.
                    # logger.info('entry: %s' % entry)
                    try:
                        links = {'id': entry['id'], 'link': entry['link']}
                    except Exception:
                        links = entry['link']
                    searchresult = searcher(
                        nzbprov,
                        nzbname,
                        mylar.COMICINFO,
                        links,
                        IssueID,
                        ComicID,
                        tmpprov,
                        newznab=newznab_host,
                        torznab=torznab_host,
                        rss=RSS,
                    )

                    if any(
                        [
                            searchresult == 'downloadchk-fail',
                            searchresult == 'double-pp',
                        ]
                    ):
                        foundc['status'] = False
                        continue
                    elif any(
                        [
                            searchresult == 'torrent-fail',
                            searchresult == 'nzbget-fail',
                            searchresult == 'sab-fail',
                            searchresult == 'blackhole-fail',
                            searchresult == 'ddl-fail',
                        ]
                    ):
                        foundc['status'] = False
                        return foundc

                    # nzbid, nzbname, sent_to
                    nzbid = searchresult['nzbid']
                    nzbname = searchresult['nzbname']
                    sent_to = searchresult['sent_to']
                    alt_nzbname = searchresult['alt_nzbname']
                    if searchresult['SARC'] is not None:
                        SARC = searchresult['SARC']
                    foundc['info'] = searchresult
                    foundc['status'] = True
                    done = True
                    break

                if done is True:
                    # cmloopit == 1 #let's make sure it STOPS searching after a
                    # sucessful match.
                    break
        # cmloopit-=1
        # if (
        #     cmloopit < 1 and c_alpha is not None and seperatealpha == "no" and
        #     foundc['status'] is False
        #     ):
        #     logger.info("Alphanumerics detected within IssueNumber. Seperating
        #                 " from Issue # and re-trying.")
        #     cmloopit = origcmloopit
        #     seperatealpha = "yes"
        logger.fdebug(
            'booktype:%s / chktpb: %s / findloop: %s' % (booktype, chktpb, findloop)
        )
        if any(
               [
                   booktype == 'TPB',
                   booktype == 'GN',
                   booktype == 'HC',
                ]
            ) and chktpb == 1 and findloop + 1 > findcount:
            pass  # findloop=-1
        else:
            findloop += 1

    if foundc['status'] is True:
        if 'Public Torrents' in tmpprov and any([nzbprov == 'WWT', nzbprov == 'DEM']):
            tmpprov = re.sub('Public Torrents', nzbprov, tmpprov)
        foundcomic.append("yes")
        logger.fdebug('mylar.COMICINFO: %s' % mylar.COMICINFO)
        if mylar.COMICINFO[0]['pack'] is True:
            try:
                issinfo = mylar.COMICINFO[0]['pack_issuelist']
            except Exception:
                issinfo = mylar.COMICINFO['pack_issuelist']
            if issinfo is not None:
                # we need to get EVERY issue ID within the pack and update the log to
                # reflect that they're being downloaded via a pack.
                try:
                    logger.fdebug(
                        'Found matching comic within pack...preparing to send to'
                        ' Updater with IssueIDs: %s and nzbname of %s'
                        % (issueid_info, nzbname)
                    )
                except NameError:
                    logger.fdebug('Did not find issueid_info')

                # because packs need to have every issue that's not already Downloaded
                # in a Snatched status, throw it to
                # the updater here as well.
                for isid in issinfo['issues']:
                    updater.nzblog(
                        isid['issueid'],
                        nzbname,
                        ComicName,
                        SARC=SARC,
                        IssueArcID=IssueArcID,
                        id=nzbid,
                        prov=tmpprov,
                        oneoff=oneoff,
                    )
                    updater.foundsearch(
                        ComicID, isid['issueid'], mode=smode, provider=tmpprov
                    )
                notify_snatch(
                    sent_to,
                    mylar.COMICINFO[0]['ComicName'],
                    mylar.COMICINFO[0]['comyear'],
                    mylar.COMICINFO[0]['pack_numbers'],
                    nzbprov,
                    True,
                )
            else:
                notify_snatch(
                    sent_to,
                    mylar.COMICINFO[0]['ComicName'],
                    mylar.COMICINFO[0]['comyear'],
                    None,
                    nzbprov,
                    True,
                )

        else:
            if alt_nzbname is None or alt_nzbname == '':
                logger.fdebug(
                    'Found matching comic...preparing to send to Updater with IssueID:'
                    ' %s and nzbname: %s' % (IssueID, nzbname)
                )
                if '[RSS]' in tmpprov:
                    tmpprov = re.sub(r'\[RSS\]', '', tmpprov).strip()
                updater.nzblog(
                    IssueID,
                    nzbname,
                    ComicName,
                    SARC=SARC,
                    IssueArcID=IssueArcID,
                    id=nzbid,
                    prov=tmpprov,
                    oneoff=oneoff,
                )
            else:
                logger.fdebug(
                    'Found matching comic...preparing to send to Updater with IssueID:'
                    ' %s and nzbname: %s [%s]' % (IssueID, nzbname, alt_nzbname)
                )
                if '[RSS]' in tmpprov:
                    tmpprov = re.sub(r'\[RSS\]', '', tmpprov).strip()
                updater.nzblog(
                    IssueID,
                    nzbname,
                    ComicName,
                    SARC=SARC,
                    IssueArcID=IssueArcID,
                    id=nzbid,
                    prov=tmpprov,
                    alt_nzbname=alt_nzbname,
                    oneoff=oneoff,
                )
                updater.foundsearch(
                    ComicID,
                    IssueID,
                    mode=smode, #'series',
                    provider=tmpprov,
                    SARC=SARC,
                    IssueArcID=IssueArcID
                )

            # send out the notifications for the snatch.
            if any([oneoff is True, IssueID is None]):
                cyear = ComicYear
            else:
                cyear = comyear
            notify_snatch(sent_to, ComicName, cyear, IssueNumber, tmpprov, False)
        prov_count == 0
        mylar.TMP_PROV = nzbprov

        return foundc

    else:
        foundcomic.append("no")
        # if IssDateFix == "no":
        #     logger.info('Could not find Issue ' + str(IssueNumber) + ' of '
        #     + ComicName + '(' + str(comyear) + ') using ' + str(tmpprov) '
        #     + '. Status kept as wanted.' )
        #     break
    return foundc


def searchforissue(issueid=None, new=False, rsscheck=None, manual=False):
    if rsscheck == 'yes':
        while mylar.SEARCHLOCK is True:
           # logger.info(
           #     'A search is currently in progress....queueing this up again to try'
           #     ' in a bit.'
           # )
            time.sleep(5)

    if mylar.SEARCHLOCK is True:
        logger.info(
            'A search is currently in progress....queueing this up again to try'
            ' in a bit.'
        )
        return {'status': 'IN PROGRESS'}

    myDB = db.DBConnection()

    ens = [x for x in mylar.CONFIG.EXTRA_NEWZNABS if x[5] == '1']
    ets = [x for x in mylar.CONFIG.EXTRA_TORZNABS if x[5] == '1']
    if (
        any(
            [
                mylar.CONFIG.ENABLE_DDL is True,
                mylar.CONFIG.NZBSU is True,
                mylar.CONFIG.DOGNZB is True,
                mylar.CONFIG.EXPERIMENTAL is True,
            ]
        )
        or all([mylar.CONFIG.NEWZNAB is True, len(ens) > 0])
        and any(
            [
                mylar.USE_SABNZBD is True,
                mylar.USE_NZBGET is True,
                mylar.USE_BLACKHOLE is True,
            ]
        )
    ) or (
        all(
            [
                mylar.CONFIG.ENABLE_TORRENT_SEARCH is True,
                mylar.CONFIG.ENABLE_TORRENTS is True,
            ]
        )
        and (
            any([mylar.CONFIG.ENABLE_PUBLIC is True, mylar.CONFIG.ENABLE_32P is True])
            or all([mylar.CONFIG.ENABLE_TORZNAB is True, len(ets) > 0])
        )
    ):
        if not issueid or rsscheck:

            if rsscheck:
                logger.info(
                    'Initiating RSS Search Scan at the scheduled interval of %s minutes'
                    % mylar.CONFIG.RSS_CHECKINTERVAL
                )
                mylar.SEARCHLOCK = True
            else:
                logger.info('Initiating check to add Wanted items to Search Queue....')

            myDB = db.DBConnection()

            stloop = 2  # 3 levels - one for issues, one for storyarcs, one  for annuals
            results = []

            if mylar.CONFIG.ANNUALS_ON:
                stloop += 1
            while stloop > 0:
                if stloop == 1:
                    if (
                        mylar.CONFIG.FAILED_DOWNLOAD_HANDLING
                        and mylar.CONFIG.FAILED_AUTO
                    ):
                        issues_1 = myDB.select(
                            'SELECT * from issues WHERE Status="Wanted" OR'
                            ' Status="Failed"'
                        )
                    else:
                        issues_1 = myDB.select(
                            'SELECT * from issues WHERE Status="Wanted"'
                        )
                    for iss in issues_1:
                        results.append(
                            {
                                'ComicID': iss['ComicID'],
                                'IssueID': iss['IssueID'],
                                'Issue_Number': iss['Issue_Number'],
                                'IssueDate': iss['IssueDate'],
                                'StoreDate': iss['ReleaseDate'],
                                'DigitalDate': iss['DigitalDate'],
                                'SARC': None,
                                'StoryArcID': None,
                                'IssueArcID': None,
                                'mode': 'want',
                                'DateAdded': iss['DateAdded'],
                                'ComicName': iss['ComicName'],
                            }
                        )
                elif stloop == 2:
                    if mylar.CONFIG.SEARCH_STORYARCS is True or rsscheck:
                        if (
                            mylar.CONFIG.FAILED_DOWNLOAD_HANDLING
                            and mylar.CONFIG.FAILED_AUTO
                        ):
                            issues_2 = myDB.select(
                                'SELECT * from storyarcs WHERE Status="Wanted" OR'
                                ' Status="Failed"'
                            )
                        else:
                            issues_2 = myDB.select(
                                'SELECT * from storyarcs WHERE Status="Wanted"'
                            )
                        cnt = 0
                        for iss in issues_2:
                            results.append(
                                {
                                    'ComicID': iss['ComicID'],
                                    'IssueID': iss['IssueID'],
                                    'Issue_Number': iss['IssueNumber'],
                                    'IssueDate': iss['IssueDate'],
                                    'StoreDate': iss['ReleaseDate'],
                                    'DigitalDate': iss['DigitalDate'],
                                    'SARC': iss['StoryArc'],
                                    'StoryArcID': iss['StoryArcID'],
                                    'IssueArcID': iss['IssueArcID'],
                                    'mode': 'story_arc',
                                    'DateAdded': iss['DateAdded'],
                                    'ComicName': iss['ComicName'],
                                }
                            )
                            cnt += 1
                        logger.info('Storyarcs to be searched for : %s' % cnt)
                elif stloop == 3:
                    if (
                        mylar.CONFIG.FAILED_DOWNLOAD_HANDLING
                        and mylar.CONFIG.FAILED_AUTO
                    ):
                        issues_3 = myDB.select(
                            'SELECT * from annuals WHERE Status="Wanted" OR'
                            ' Status="Failed AND NOT Deleted"'
                        )
                    else:
                        issues_3 = myDB.select(
                            'SELECT * from annuals WHERE Status="Wanted AND NOT Deleted"'
                        )
                    for iss in issues_3:
                        results.append(
                            {
                                'ComicID': iss['ComicID'],
                                'IssueID': iss['IssueID'],
                                'Issue_Number': iss['Issue_Number'],
                                'IssueDate': iss['IssueDate'],
                                'StoreDate': iss['ReleaseDate'],
                                'DigitalDate': iss['DigitalDate'],
                                'SARC': None,
                                'StoryArcID': None,
                                'IssueArcID': None,
                                'mode': 'want_ann',
                                'DateAdded': iss['DateAdded'],
                                'ComicName': iss['ReleaseComicName'],
                            }
                        )
                stloop -= 1

            # to-do: re-order the results list so it's most recent to least recent.

            for result in sorted(results, key=itemgetter('StoreDate'), reverse=True):

                try:
                    # status issue check - check status to see if it's Downloaded /
                    # Snatched already due to concurrent searches possible.
                    if result['IssueID'] is not None:
                        if result['mode'] == 'story_arc':
                            isscheck = helpers.issue_status(result['IssueArcID'])
                        else:
                            isscheck = helpers.issue_status(result['IssueID'])
                        # isscheck will return True if already Downloaded / Snatched,
                        # False if it's still in a Wanted status.
                        if isscheck is True:
                            logger.fdebug(
                                'Issue is already in a Downloaded / Snatched status.'
                            )
                            continue

                    OneOff = False
                    storyarc_watchlist = False
                    comic = myDB.selectone(
                        "SELECT * from comics WHERE ComicID=? AND ComicName != 'None'",
                        [result['ComicID']],
                    ).fetchone()
                    if all([comic is None, result['mode'] == 'story_arc']):
                        comic = myDB.selectone(
                            "SELECT * from storyarcs WHERE StoryArcID=? AND"
                            " IssueArcID=?",
                            [result['StoryArcID'], result['IssueArcID']],
                        ).fetchone()
                        if comic is None:
                            logger.fdebug(
                                '%s has no associated comic information in the Arc.'
                                ' Skipping searching for this series.'
                                % result['ComicID']
                            )
                            continue
                        else:
                            OneOff = True
                    elif comic is None:
                        logger.fdebug(
                            '%s has no associated comic information in the Arc.'
                            ' Skipping searching for this series.'
                            % result['ComicID']
                        )
                        continue
                    else:
                        storyarc_watchlist = True
                    if (
                        result['StoreDate'] == '0000-00-00'
                        or result['StoreDate'] is None
                    ):
                        if (
                            any(
                                [
                                    result['IssueDate'] is None,
                                    result['IssueDate'] == '0000-00-00',
                                ]
                            )
                            and result['DigitalDate'] == '0000-00-00'
                        ):
                            logger.fdebug(
                                'ComicID: %s has invalid Date data. Skipping searching'
                                ' for this series.'
                                % result['ComicID']
                            )
                            continue

                    foundNZB = "none"
                    AllowPacks = False
                    if result['mode'] == 'want_ann' or 'annual' in result['ComicName']:
                        comicname = result['ComicName']
                    else:
                        comicname = comic['ComicName']
                    if all(
                        [result['mode'] == 'story_arc', storyarc_watchlist is False]
                    ):
                        Comicname_filesafe = helpers.filesafe(comicname)
                        SeriesYear = comic['SeriesYear']
                        Publisher = comic['Publisher']
                        AlternateSearch = None
                        UseFuzzy = None
                        ComicVersion = comic['Volume']
                        TorrentID_32p = None
                        booktype = comic['Type']
                        ignore_booktype = False
                    else:
                        Comicname_filesafe = comic['ComicName_Filesafe']
                        SeriesYear = comic['ComicYear']
                        Publisher = comic['ComicPublisher']
                        AlternateSearch = comic['AlternateSearch']
                        UseFuzzy = comic['UseFuzzy']
                        ComicVersion = comic['ComicVersion']
                        TorrentID_32p = comic['TorrentID_32P']
                        booktype = comic['Type']
                        if (
                            comic['Corrected_Type'] is not None
                            and comic['Type'] != comic['Corrected_Type']
                        ):
                            booktype = comic['Corrected_Type']
                        ignore_booktype = bool(comic['IgnoreType'])
                        if any([comic['AllowPacks'] == 1, comic['AllowPacks'] == '1']):
                            AllowPacks = True

                    IssueDate = result['IssueDate']
                    StoreDate = result['StoreDate']
                    DigitalDate = result['DigitalDate']

                    if result['IssueDate'] is None:
                        ComicYear = SeriesYear
                    else:
                        ComicYear = str(result['IssueDate'])[:4]

                    if result['DateAdded'] is None:
                        DA = datetime.datetime.today()
                        DateAdded = DA.strftime('%Y-%m-%d')
                        if result['mode'] == 'want':
                            table = 'issues'
                        elif result['mode'] == 'want_ann':
                            table = 'annuals'
                        elif result['mode'] == 'story_arc':
                            table = 'storyarcs'
                        else:
                            table = None
                            # not writing to the table here will mean the Tier won't
                            # get changed
                            logger.warn(
                                '[SEARCH-ERROR] Error while trying to write DateAdded'
                                ' value to non-existant table due to given search mode'
                                ' of %s' % result['mode']
                            )
                        if table is not None:
                            logger.fdebug(
                                '%s #%s did not have a DateAdded recorded, setting it'
                                ' : %s'
                                % (
                                    comicname,
                                    result['Issue_Number'],
                                    DateAdded,
                                )
                            )
                            myDB.upsert(
                                table,
                                {'DateAdded': DateAdded},
                                {'IssueID': result['IssueID']},
                            )

                    else:
                        DateAdded = result['DateAdded']

                    if rsscheck is None:
                        if DateAdded >= mylar.SEARCH_TIER_DATE:
                            logger.info(
                                'adding: ComicID:%s  IssueiD: %s'
                                % (result['ComicID'], result['IssueID'])
                            )
                            mylar.SEARCH_QUEUE.put(
                                {
                                    'comicname': comicname,
                                    'seriesyear': SeriesYear,
                                    'issuenumber': result['Issue_Number'],
                                    'issueid': result['IssueID'],
                                    'comicid': result['ComicID'],
                                    'booktype': booktype,
                                }
                            )
                        continue

                    smode = result['mode']
                    foundNZB, prov = search_init(
                        comicname,
                        result['Issue_Number'],
                        str(ComicYear),
                        SeriesYear,
                        Publisher,
                        IssueDate,
                        StoreDate,
                        result['IssueID'],
                        AlternateSearch,
                        UseFuzzy,
                        ComicVersion,
                        SARC=result['SARC'],
                        IssueArcID=result['IssueArcID'],
                        smode=smode,
                        rsscheck=rsscheck,
                        ComicID=result['ComicID'],
                        filesafe=Comicname_filesafe,
                        allow_packs=AllowPacks,
                        oneoff=OneOff,
                        torrentid_32p=TorrentID_32p,
                        digitaldate=DigitalDate,
                        booktype=booktype,
                        ignore_booktype=ignore_booktype,
                    )
                    if foundNZB['status'] is True:
                        updater.foundsearch(
                            result['ComicID'],
                            result['IssueID'],
                            mode=smode,
                            provider=prov,
                            SARC=result['SARC'],
                            IssueArcID=result['IssueArcID'],
                            hash=foundNZB['info']['t_hash'],
                        )

                except Exception as err:
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    filename, line_num, func_name, err_text = traceback.extract_tb(
                        exc_tb
                    )[-1]
                    tracebackline = traceback.format_exc()

                    except_line = {
                        'exc_type': exc_type,
                        'exc_value': exc_value,
                        'exc_tb': exc_tb,
                        'filename': filename,
                        'line_num': line_num,
                        'func_name': func_name,
                        'err': str(err),
                        'err_text': err_text,
                        'traceback': tracebackline,
                        'comicname': comicname,
                        'issuenumber': result['Issue_Number'],
                        'seriesyear': SeriesYear,
                        'issueid': result['IssueID'],
                        'comicid': result['ComicID'],
                        'smode': smode,
                        'booktype': booktype,
                    }

                    helpers.log_that_exception(except_line)

                    # log it regardless..
                    logger.exception(tracebackline)
                    continue

            if rsscheck:
                logger.info('Completed RSS Search scan')
                mylar.SEARCHLOCK = False
            else:
                logger.info('Completed Queueing API Search scan')
        else:
            try:
                mylar.SEARCHLOCK = True
                result = myDB.selectone(
                    'SELECT * FROM issues where IssueID=?', [issueid]
                ).fetchone()
                smode = 'want'
                oneoff = False
                if result is None:
                    result = myDB.selectone(
                        'SELECT * FROM annuals where IssueID=? AND NOT Deleted', [issueid]
                    ).fetchone()
                    smode = 'want_ann'
                    if result is None:
                        result = myDB.selectone(
                            'SELECT * FROM storyarcs where IssueArcID=?', [issueid]
                        ).fetchone()
                        smode = 'story_arc'
                        oneoff = True
                        if result is None:
                            result = myDB.selectone(
                                'SELECT * FROM weekly where IssueID=?', [issueid]
                            ).fetchone()
                            smode = 'pullwant'
                            oneoff = True
                            if result is None:
                                logger.fdebug(
                                    'Unable to locate IssueID - you probably should'
                                    ' delete/refresh the series.'
                                )
                                mylar.SEARCHLOCK = False
                                return

                allow_packs = False
                ComicID = result['ComicID']
                if smode == 'story_arc':
                    ComicName = result['ComicName']
                    Comicname_filesafe = helpers.filesafe(ComicName)
                    SeriesYear = result['SeriesYear']
                    IssueNumber = result['IssueNumber']
                    Publisher = result['Publisher']
                    AlternateSearch = None
                    UseFuzzy = None
                    ComicVersion = result['Volume']
                    SARC = result['StoryArc']
                    IssueArcID = issueid
                    actissueid = result['IssueID'] #None
                    IssueDate = result['IssueDate']
                    StoreDate = result['ReleaseDate']
                    DigitalDate = result['DigitalDate']
                    TorrentID_32p = None
                    booktype = result['Type']
                    ignore_booktype = False
                elif smode == 'pullwant':
                    ComicName = result['COMIC']
                    Comicname_filesafe = helpers.filesafe(ComicName)
                    SeriesYear = result['seriesyear']
                    IssueNumber = result['ISSUE']
                    Publisher = result['PUBLISHER']
                    AlternateSearch = None
                    UseFuzzy = None
                    ComicVersion = result['volume']
                    SARC = None
                    IssueArcID = None
                    actissueid = issueid
                    TorrentID_32p = None
                    IssueDate = result['SHIPDATE']
                    StoreDate = IssueDate
                    DigitalDate = '0000-00-00'
                    booktype = result['format']
                    ignore_booktype = False
                else:
                    comic = myDB.selectone(
                        'SELECT * FROM comics where ComicID=?', [ComicID]
                    ).fetchone()
                    if smode == 'want_ann':
                        ComicName = result['ReleaseComicName']
                        Comicname_filesafe = None
                        AlternateSearch = None
                    else:
                        ComicName = comic['ComicName']
                        Comicname_filesafe = comic['ComicName_Filesafe']
                        AlternateSearch = comic['AlternateSearch']
                    SeriesYear = comic['ComicYear']
                    IssueNumber = result['Issue_Number']
                    Publisher = comic['ComicPublisher']
                    UseFuzzy = comic['UseFuzzy']
                    ComicVersion = comic['ComicVersion']
                    IssueDate = result['IssueDate']
                    StoreDate = result['ReleaseDate']
                    DigitalDate = result['DigitalDate']
                    SARC = None
                    IssueArcID = None
                    actissueid = issueid
                    TorrentID_32p = comic['TorrentID_32P']
                    booktype = comic['Type']
                    if (
                        comic['Corrected_Type'] is not None
                        and comic['Type'] != comic['Corrected_Type']
                    ):
                        booktype = comic['Corrected_Type']
                    ignore_booktype = bool(comic['IgnoreType'])
                    if any([comic['AllowPacks'] == 1, comic['AllowPacks'] == '1']):
                        allow_packs = True

                if IssueDate is None:
                    IssueYear = SeriesYear
                else:
                    IssueYear = str(IssueDate)[:4]

                foundNZB, prov = search_init(
                    ComicName,
                    IssueNumber,
                    str(IssueYear),
                    SeriesYear,
                    Publisher,
                    IssueDate,
                    StoreDate,
                    actissueid,
                    AlternateSearch,
                    UseFuzzy,
                    ComicVersion,
                    SARC=SARC,
                    IssueArcID=IssueArcID,
                    smode=smode,
                    rsscheck=rsscheck,
                    ComicID=ComicID,
                    filesafe=Comicname_filesafe,
                    allow_packs=allow_packs,
                    oneoff=oneoff,
                    manual=manual,
                    torrentid_32p=TorrentID_32p,
                    digitaldate=DigitalDate,
                    booktype=booktype,
                    ignore_booktype=ignore_booktype,
                )
                if manual is True:
                    mylar.SEARCHLOCK = False
                    return foundNZB
                if foundNZB['status'] is True:
                    mylar.SEARCHLOCK = False
                    logger.fdebug('I found %s #%s' % (ComicName, IssueNumber))
                    updater.foundsearch(
                        ComicID,
                        actissueid,
                        mode=smode,
                        provider=prov,
                        SARC=SARC,
                        IssueArcID=IssueArcID,
                        hash=foundNZB['info']['t_hash'],
                    )
                return foundNZB

            except Exception as err:
                exc_type, exc_value, exc_tb = sys.exc_info()
                filename, line_num, func_name, err_text = traceback.extract_tb(exc_tb)[
                    -1
                ]
                tracebackline = traceback.format_exc()

                except_line = {
                    'exc_type': exc_type,
                    'exc_value': exc_value,
                    'exc_tb': exc_tb,
                    'filename': filename,
                    'line_num': line_num,
                    'func_name': func_name,
                    'err': str(err),
                    'err_text': err_text,
                    'traceback': tracebackline,
                    'comicname': comic['ComicName'],
                    'issuenumber': result['Issue_Number'],
                    'seriesyear': SeriesYear,
                    'issueid': result['IssueID'],
                    'comicid': result['ComicID'],
                    'smode': smode,
                    'booktype': booktype,
                }

                helpers.log_that_exception(except_line)

                # log it regardless..
                logger.exception(tracebackline)

            finally:
                mylar.SEARCHLOCK = False
    else:
        if rsscheck:
            logger.warn(
                'There are no search providers enabled atm - not performing an RSS'
                ' check for obvious reasons'
            )
        else:
            logger.warn(
                'There are no search providers enabled atm - not performing an Force'
                ' Check for obvious reasons'
            )
    return


def searchIssueIDList(issuelist):
    myDB = db.DBConnection()
    ens = [x for x in mylar.CONFIG.EXTRA_NEWZNABS if x[5] == '1']
    ets = [x for x in mylar.CONFIG.EXTRA_TORZNABS if x[5] == '1']
    if (
        any(
            [
                mylar.CONFIG.ENABLE_DDL is True,
                mylar.CONFIG.NZBSU is True,
                mylar.CONFIG.DOGNZB is True,
                mylar.CONFIG.EXPERIMENTAL is True,
            ]
        )
        or all([mylar.CONFIG.NEWZNAB is True, len(ens) > 0])
        and any(
            [
                mylar.USE_SABNZBD is True,
                mylar.USE_NZBGET is True,
                mylar.USE_BLACKHOLE is True,
            ]
        )
    ) or (
        all(
            [
                mylar.CONFIG.ENABLE_TORRENT_SEARCH is True,
                mylar.CONFIG.ENABLE_TORRENTS is True,
            ]
        )
        and (
            any([mylar.CONFIG.ENABLE_PUBLIC is True, mylar.CONFIG.ENABLE_32P is True])
            or all([mylar.CONFIG.ENABLE_TORZNAB is True, len(ets) > 0])
        )
    ):
        for issueid in issuelist:
            comicname = None
            issue = myDB.selectone(
                'SELECT * from issues WHERE IssueID=?', [issueid]
            ).fetchone()
            if issue is None:
                issue = myDB.selectone(
                    'SELECT * from annuals WHERE IssueID=? AND NOT Deleted', [issueid]
                ).fetchone()
                if issue is None:
                    issue = myDB.selectone(
                        'SELECT * from storyarcs WHERE IssueArcID=?', [issueid]
                    ).fetchone()
                    if issue is not None:
                        comicname = issue['ComicName']
                        seriesyear = issue['SeriesYear']
                        booktype = issue['Type']
                        issuenumber = issue['IssueNumber']
                    else:
                        logger.warn(
                            'Unable to determine IssueID - perhaps you need to'
                            ' delete/refresh series? Skipping this entry: %s'
                            % issueid
                        )
                        continue

            if any([issue['Status'] == 'Downloaded', issue['Status'] == 'Snatched']):
                logger.fdebug(
                    'Issue is already in a Downloaded / Snatched status. If this is'
                    ' still wanted, perform a Manual search or mark issue as Skipped'
                    ' or Wanted.'
                )
                continue

            if comicname is None:
                comic = myDB.selectone(
                    'SELECT * from comics WHERE ComicID=?', [issue['ComicID']]
                ).fetchone()
                comicname = comic['ComicName']
                seriesyear = comic['ComicYear']
                booktype = comic['Type']
                issuenumber = issue['Issue_Number']

                if (
                    comic['Corrected_Type'] is not None
                    and comic['Type'] != comic['Corrected_Type']
                ):
                    booktype = comic['Corrected_Type']

            mylar.SEARCH_QUEUE.put(
                {
                    'comicname': comicname,
                    'seriesyear': seriesyear,
                    'issuenumber': issuenumber,
                    'issueid': issue['IssueID'], #issueid,
                    'comicid': issue['ComicID'],
                    'booktype': booktype,
                }
            )

        logger.info('Completed queuing of search request.')
    else:
        logger.warn(
            'There are no search providers enabled atm - not performing the requested'
            ' search for obvious reasons'
        )

def provider_sequence(
    nzbprovider, torprovider, newznab_hosts, torznab_hosts, ddlprovider
):
    # provider order sequencing here.
    newznab_info = []
    torznab_info = []
    prov_order = []

    nzbproviders_lower = [x.lower() for x in nzbprovider]
    torproviders_lower = [y.lower() for y in torprovider]
    ddlproviders_lower = [z.lower() for z in ddlprovider]

    if len(mylar.CONFIG.PROVIDER_ORDER) > 0:
        for pr_order in sorted(
            list(mylar.CONFIG.PROVIDER_ORDER.items()), key=itemgetter(0), reverse=False
        ):
            if (
                any(pr_order[1].lower() in y for y in torproviders_lower)
                or any(pr_order[1].lower() in x for x in nzbproviders_lower)
                or any(pr_order[1].lower() == z for z in ddlproviders_lower)
            ):
                if any(pr_order[1].lower() in x for x in nzbproviders_lower):
                    # this is for nzb providers
                    for np in nzbprovider:
                        if all(['newznab' in np, pr_order[1].lower() in np.lower()]):
                            for newznab_host in newznab_hosts:
                                if newznab_host[0].lower() == pr_order[1].lower():
                                    prov_order.append(np)
                                    newznab_info.append(
                                        {"provider": np, "info": newznab_host}
                                    )
                                    break
                                else:
                                    if newznab_host[0] == "":
                                        if (
                                            newznab_host[1].lower()
                                            == pr_order[1].lower()
                                        ):
                                            prov_order.append(np)
                                            newznab_info.append(
                                                {"provider": np, "info": newznab_host}
                                            )
                                            break
                        elif pr_order[1].lower() in np.lower():
                            prov_order.append(pr_order[1])
                            break
                elif any(pr_order[1].lower() in y for y in torproviders_lower):
                    for tp in torprovider:
                        if all(['torznab' in tp, pr_order[1].lower() in tp.lower()]):
                            for torznab_host in torznab_hosts:
                                if torznab_host[0].lower() == pr_order[1].lower():
                                    prov_order.append(tp)
                                    torznab_info.append(
                                        {"provider": tp, "info": torznab_host}
                                    )
                                    break
                                else:
                                    if torznab_host[0] == "":
                                        if (
                                            torznab_host[1].lower()
                                            == pr_order[1].lower()
                                        ):
                                            prov_order.append(tp)
                                            torznab_info.append(
                                                {"provider": tp, "info": torznab_host}
                                            )
                                            break
                        elif pr_order[1].lower() in tp.lower():
                            prov_order.append(pr_order[1])
                            break
                elif any(pr_order[1].lower() == z for z in ddlproviders_lower):
                    for dd in ddlprovider:
                        if dd.lower() == pr_order[1].lower():
                            prov_order.append(pr_order[1])
                            break

    return prov_order, torznab_info, newznab_info


def nzbname_create(provider, title=None, info=None):
    """
    The nzbname here is used when post-processing.
    It searches nzblog which contains the nzbname to pull out the IssueID and start the
    post-processing. It is also used to keep the hashinfo for the nzbname in case it
    fails downloading, and then it will get put into the failed db for future exclusions
    """
    nzbname = None

    if mylar.USE_BLACKHOLE and all(
        [provider != '32P', provider != 'WWT', provider != 'DEM']
    ):
        if os.path.exists(mylar.CONFIG.BLACKHOLE_DIR):
            # load in the required info to generate the nzb names when required
            # (blackhole only)
            ComicName = info[0]['ComicName']
            IssueNumber = info[0]['IssueNumber']
            comyear = info[0]['comyear']
            # pretty this biatch up.
            BComicName = re.sub(r'[\:\,\/\?\']', '', str(ComicName))
            Bl_ComicName = re.sub(r'[\&]', 'and', str(BComicName))
            if IssueNumber is not None:
                if '\xbd' in IssueNumber:
                    str_IssueNumber = '0.5'
                elif '\xbc' in IssueNumber:
                    str_IssueNumber = '0.25'
                elif '\xbe' in IssueNumber:
                    str_IssueNumber = '0.75'
                elif '\u221e' in IssueNumber:
                    str_IssueNumber = 'infinity'
                else:
                    str_IssueNumber = IssueNumber
                nzbline = '%s.%s.(%s)'
            else:
                str_IssueNumber = ''
                nzbline = '%s%s(%s)'
            nzbname = nzbline % (
                re.sub(" ", ".", str(Bl_ComicName)),
                str_IssueNumber,
                comyear,
            )

            logger.fdebug('nzb name to be used for post-processing is : %s' % nzbname)

    elif any(
        [provider == '32P', provider == 'WWT', provider == 'DEM', provider == 'DDL']
    ):
        # filesafe the name cause people are idiots when they post sometimes.
        nzbname = re.sub(r'\s{2,}', ' ', helpers.filesafe(title)).strip()
        # let's change all space to decimals for simplicity
        nzbname = re.sub(" ", ".", nzbname)
        # gotta replace & or escape it
        nzbname = re.sub(r'\&', 'and', nzbname)
        nzbname = re.sub(r'[\,\:\?\']', '', nzbname)
        if nzbname.lower().endswith('.torrent'):
            nzbname = re.sub('.torrent', '', nzbname)

    else:
        # let's change all space to decimals for simplicity
        logger.fdebug('[SEARCHER] entry[title]: %s' % title)
        # gotta replace & or escape it
        nzbname = re.sub(r'\&amp;|(amp;)|amp;|\&', 'and', title)
        nzbname = re.sub(r'[\,\:\?\'\+]', '', nzbname)
        nzbname = re.sub(r'[\(\)]', ' ', nzbname)
        logger.fdebug('[SEARCHER] nzbname (remove chars): %s' % nzbname)
        nzbname = re.sub('.cbr', '', nzbname).strip()
        nzbname = re.sub('.cbz', '', nzbname).strip()
        nzbname = re.sub(r'[\.\_]', ' ', nzbname).strip()
        nzbname = re.sub(r'\s+', ' ', nzbname)  # make sure we remove the extra spaces.
        logger.fdebug('[SEARCHER] nzbname : %s' % nzbname)
        nzbname = re.sub(r'\s', '.', nzbname)
        # remove the [1/9] parts or whatever kinda crap (usually in experimental)
        pattern = re.compile(r'\W\d{1,3}\/\d{1,3}\W')
        match = pattern.search(nzbname)
        if match:
            nzbname = re.sub(match.group(), '', nzbname).strip()
        logger.fdebug('[SEARCHER] end nzbname: %s' % nzbname)

    if nzbname is None:
        return None
    else:
        logger.fdebug('nzbname used for post-processing: %s' % nzbname)
        return nzbname


def searcher(
    nzbprov,
    nzbname,
    comicinfo,
    link,
    IssueID,
    ComicID,
    tmpprov,
    directsend=None,
    newznab=None,
    torznab=None,
    rss=None,
):
    alt_nzbname = None
    # load in the details of the issue from the tuple.
    ComicName = comicinfo[0]['ComicName']
    IssueNumber = comicinfo[0]['IssueNumber']
    comyear = comicinfo[0]['comyear']
    oneoff = comicinfo[0]['oneoff']
    try:
        SARC = comicinfo[0]['SARC']
    except Exception:
        SARC = None
    try:
        IssueArcID = comicinfo[0]['IssueArcID']
    except Exception:
        IssueArcID = None

    # setup the priorities.
    if mylar.CONFIG.SAB_PRIORITY:
        if mylar.CONFIG.SAB_PRIORITY == 'Default':
            sabpriority = '-100'
        elif mylar.CONFIG.SAB_PRIORITY == 'Low':
            sabpriority = '-1'
        elif mylar.CONFIG.SAB_PRIORITY == 'Normal':
            sabpriority = '0'
        elif mylar.CONFIG.SAB_PRIORITY == 'High':
            sabpriority = '1'
        elif mylar.CONFIG.SAB_PRIORITY == 'Paused':
            sabpriority = '-2'
    else:
        # if sab priority isn't selected, default to Normal (0)
        sabpriority = '0'

    if nzbprov == 'torznab' or nzbprov == 'DDL':
        if nzbprov == 'DDL':
            nzbid = link['id']
        else:
            nzbid = generate_id(nzbprov, link['id'])
        link = link['link']
    else:
        try:
            link = link['link']
        except Exception:
            link = link
        nzbid = generate_id(nzbprov, link)

    logger.fdebug('issues match!')
    if 'Public Torrents' in tmpprov and any([nzbprov == 'WWT', nzbprov == 'DEM']):
        tmpprov = re.sub('Public Torrents', nzbprov, tmpprov)

    if comicinfo[0]['pack'] is True:
        if '0-Day Comics Pack' not in comicinfo[0]['ComicName']:
            logger.info(
                'Found %s (%s) issue: %s using %s within a pack containing issues %s'
                % (
                    ComicName,
                    comyear,
                    IssueNumber,
                    tmpprov,
                    comicinfo[0]['pack_numbers'],
                )
            )
        else:
            logger.info(
                'Found %s using %s for %s'
                % (ComicName, tmpprov, comicinfo[0]['IssueDate'])
            )
    else:
        if any([oneoff is True, IssueID is None]):
            # one-off information
            logger.fdebug('ComicName: %s' % ComicName)
            logger.fdebug('Issue: %s' % IssueNumber)
            logger.fdebug('Year: %s' % comyear)
            logger.fdebug('IssueDate: %s' % comicinfo[0]['IssueDate'])
        if IssueNumber is None:
            logger.info('Found %s (%s) using %s' % (ComicName, comyear, tmpprov))
        else:
            logger.info(
                'Found %s (%s) #%s using %s'
                % (ComicName, comyear, IssueNumber, tmpprov)
            )

    logger.fdebug('link given by: %s' % nzbprov)

    if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING:
        logger.info('nzbid: %s' % nzbid)
        logger.info('IssueID: %s' % IssueID)
        logger.info('oneoff: %s' % oneoff)
        if all(
            [nzbid is not None and nzbid != '', IssueID is not None, oneoff is False]
        ):
            # --- this causes any possible snatch to get marked as a Failed download
            # when doing a one-off search...
            # try:
            #    # only nzb providers will have a filen, try it and pass exception
            #    if IssueID is None:
            #        logger.fdebug(
            #            'One-off mode was initiated - Failed Download'
            #            ' handling for : ' + ComicName + ' #' + str(IssueNumber)
            #        )
            #        comicinfo = {"ComicName": ComicName,
            #                     "IssueNumber": IssueNumber}
            #        return FailedMark(ComicID=ComicID, IssueID=IssueID, id=nzbid,
            #                          nzbname=nzbname, prov=nzbprov,
            #                          oneoffinfo=comicinfo)
            # except:
            #    pass
            call_the_fail = Failed.FailedProcessor(
                nzb_name=nzbname,
                id=nzbid,
                issueid=IssueID,
                comicid=ComicID,
                prov=tmpprov,
            )
            check_the_fail = call_the_fail.failed_check()
            if check_the_fail == 'Failed':
                logger.fdebug(
                    '[FAILED_DOWNLOAD_CHECKER] [%s] Marked as a bad download : %s'
                    % (tmpprov, nzbid)
                )
                return "downloadchk-fail"
            elif check_the_fail == 'Good':
                logger.fdebug(
                    '[FAILED_DOWNLOAD_CHECKER] This is not in the failed downloads'
                    ' list. Will continue with the download.'
                )
        else:
            logger.fdebug(
                '[FAILED_DOWNLOAD_CHECKER] Failed download checking is not available'
                ' for one-off downloads atm. Fixed soon!'
            )

    if link and all(
        [
            nzbprov != 'WWT',
            nzbprov != 'DEM',
            nzbprov != '32P',
            nzbprov != 'torznab',
            nzbprov != 'DDL',
        ]
    ):

        # generate nzbid here.

        nzo_info = {}
        filen = None
        nzbhydra = False
        payload = None
        headers = {'User-Agent': str(mylar.USER_AGENT)}
        # link doesn't have the apikey - add it and use ?t=get for newznab based.
        if nzbprov == 'newznab' or nzbprov == 'nzb.su':
            # need to basename the link so it just has the id/hash.
            # rss doesn't store apikey, have to put it back.
            if nzbprov == 'newznab':
                host_newznab = newznab[1].rstrip()
                if host_newznab[len(host_newznab) - 1 : len(host_newznab)] != '/':
                    host_newznab_fix = str(host_newznab) + "/"
                else:
                    host_newznab_fix = host_newznab

                # account for nzbmegasearch & nzbhydra
                if 'searchresultid' in link:
                    logger.fdebug('NZBHydra V1 url detected. Adjusting...')
                    nzbhydra = True
                else:
                    apikey = newznab[3].rstrip()
                    if rss == 'yes':
                        uid = newznab[4].rstrip()
                        payload = {'r': str(apikey)}
                        if uid is not None:
                            payload['i'] = uid
                    verify = bool(newznab[2])
            else:
                down_url = 'https://api.nzb.su/api'
                apikey = mylar.CONFIG.NZBSU_APIKEY
                verify = bool(mylar.CONFIG.NZBSU_VERIFY)

            if nzbhydra is True:
                down_url = link
                verify = False
            elif 'https://cdn.' in link:
                down_url = host_newznab_fix + 'api'
                logger.fdebug(
                    'Re-routing incorrect RSS URL response for NZBGeek to correct API'
                )
                payload = {'t': 'get', 'id': str(nzbid), 'apikey': str(apikey)}
            else:
                down_url = link

        elif nzbprov == 'dognzb':
            # dognzb - need to add back in the dog apikey
            down_url = urljoin(link, str(mylar.CONFIG.DOGNZB_APIKEY))
            verify = bool(mylar.CONFIG.DOGNZB_VERIFY)

        else:
            # experimental - direct link.
            down_url = link
            headers = None
            verify = False

        if payload is None:
            tmp_line = down_url
            tmp_url = down_url
            tmp_url_st = tmp_url.find('apikey=')
            if tmp_url_st == -1:
                tmp_url_st = tmp_url.find('r=')
                tmp_line = tmp_url[: tmp_url_st + 2]
            else:
                tmp_line = tmp_url[: tmp_url_st + 7]
            tmp_line += 'xYOUDONTNEEDTOKNOWTHISx'
            tmp_url_en = tmp_url.find('&', tmp_url_st)
            if tmp_url_en == -1:
                tmp_url_en = len(tmp_url)
            tmp_line += tmp_url[tmp_url_en:]
            # tmp_url = helpers.apiremove(down_url.copy(), '&')
            logger.fdebug(
                '[PAYLOAD-NONE] Download URL: %s [VerifySSL: %s]' % (tmp_line, verify)
            )
        else:
            tmppay = payload.copy()
            tmppay['apikey'] = 'YOUDONTNEEDTOKNOWTHIS'
            logger.fdebug(
                '[PAYLOAD] Download URL: %s?%s [VerifySSL: %s]'
                % (down_url, urllib.parse.urlencode(tmppay), verify)
            )

        if down_url.startswith('https') and verify is False:
            try:
                from requests.packages.urllib3 import disable_warnings

                disable_warnings()
            except Exception:
                logger.warn(
                    'Unable to disable https warnings. Expect some spam if using https'
                    ' nzb providers.'
                )

        try:
            r = requests.get(down_url, params=payload, verify=verify, headers=headers)

        except Exception as e:
            logger.warn('Error fetching data from %s: %s' % (tmpprov, e))
            return "sab-fail"

        logger.fdebug('Status code returned: %s' % r.status_code)
        try:
            nzo_info['filename'] = r.headers['x-dnzb-name']
            filen = r.headers['x-dnzb-name']
        except KeyError:
            filen = None
        try:
            nzo_info['propername'] = r.headers['x-dnzb-propername']
        except KeyError:
            pass
        try:
            nzo_info['failure'] = r.headers['x-dnzb-failure']
        except KeyError:
            pass
        try:
            nzo_info['details'] = r.headers['x-dnzb-details']
        except KeyError:
            pass

        if filen is None:
            try:
                filen = (
                    r.headers['content-disposition'][
                        r.headers['content-disposition'].index("filename=") + 9 :
                    ]
                    .strip(';')
                    .strip('"')
                )
                logger.fdebug('filename within nzb: %s' % filen)
            except Exception:
                pass

        if filen is None:
            if payload is None:
                logger.error(
                    '[PAYLOAD:NONE] Unable to download nzb from link: %s [%s]'
                    % (down_url, link)
                )
            else:
                errorlink = down_url + '?' + urllib.parse.urlencode(payload)
                logger.error(
                    '[PAYLOAD:PRESENT] Unable to download nzb from link: %s [%s]'
                    % (errorlink, link)
                )
            return "sab-fail"
        else:
            # convert to a generic type of format to help with post-processing.
            filen = re.sub(r'\&', 'and', filen)
            filen = re.sub(r'[\,\:\?\']', '', filen)
            filen = re.sub(r'[\(\)]', ' ', filen)
            filen = re.sub(
                r'[\s\s+]', '', filen
            )  # make sure we remove the extra spaces.
            logger.fdebug('[FILENAME] filename (remove chars): %s' % filen)
            filen = re.sub('.cbr', '', filen).strip()
            filen = re.sub('.cbz', '', filen).strip()
            logger.fdebug('[FILENAME] nzbname : %s' % filen)
            # filen = re.sub('\s', '.', filen)
            logger.fdebug('[FILENAME] end nzbname: %s' % filen)

            if (
                re.sub('.nzb', '', filen.lower()).strip()
                != re.sub('.nzb', '', nzbname.lower()).strip()
            ):
                alt_nzbname = re.sub('.nzb', '', filen).strip()
                alt_nzbname = re.sub(r'[\s+]', ' ', alt_nzbname)
                alt_nzbname = re.sub(r'[\s\_]', '.', alt_nzbname)
                logger.info(
                    'filen: %s -- nzbname: %s are not identical.'
                    ' Storing extra value as : %s' % (filen, nzbname, alt_nzbname)
                )

            # make sure the cache directory exists - if not, create it
            # (used for storing nzbs).
            if os.path.exists(mylar.CONFIG.CACHE_DIR):
                if mylar.CONFIG.ENFORCE_PERMS:
                    logger.fdebug(
                        'Cache Directory successfully found at : %s.'
                        ' Ensuring proper permissions.' % mylar.CONFIG.CACHE_DIR
                    )
                    # enforce the permissions here to ensure the lower portion writes
                    # successfully
                    filechecker.setperms(mylar.CONFIG.CACHE_DIR, True)
                else:
                    logger.fdebug(
                        'Cache Directory successfully found at : %s'
                        % mylar.CONFIG.CACHE_DIR
                    )
            else:
                # let's make the dir.
                logger.fdebug(
                    'Could not locate Cache Directory, attempting to create at : %s'
                    % mylar.CONFIG.CACHE_DIR
                )
                try:
                    filechecker.validateAndCreateDirectory(mylar.CONFIG.CACHE_DIR, True)
                    logger.info(
                        'Temporary NZB Download Directory successfully created at: %s'
                        % mylar.CONFIG.CACHE_DIR
                    )
                except OSError:
                    raise

            # save the nzb grabbed, so we can bypass all the 'send-url' crap.
            if not nzbname.endswith('.nzb'):
                nzbname = nzbname + '.nzb'
            nzbpath = os.path.join(mylar.CONFIG.CACHE_DIR, nzbname)

            with open(nzbpath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()

    # blackhole
    sent_to = None
    t_hash = None
    if mylar.CONFIG.ENABLE_DDL is True and nzbprov == 'DDL':
        if all([IssueID is None, IssueArcID is not None]):
            tmp_issueid = IssueArcID
        else:
            tmp_issueid = IssueID
        ggc = getcomics.GC(issueid=tmp_issueid, comicid=ComicID)
        ggc.loadsite(nzbid, link)
        ddl_it = ggc.parse_downloadresults(nzbid, link, comicinfo)
        if ddl_it['success'] is True:
            logger.info(
                'Successfully snatched %s from DDL site. It is currently being queued'
                ' to download in position %s' % (nzbname, mylar.DDL_QUEUE.qsize())
            )
        else:
            logger.info('Failed to retrieve %s from the DDL site.' % nzbname)
            return "ddl-fail"

        sent_to = "is downloading it directly via DDL"

    elif mylar.USE_BLACKHOLE and all(
        [nzbprov != '32P', nzbprov != 'WWT', nzbprov != 'DEM', nzbprov != 'torznab']
    ):
        logger.fdebug('Using blackhole directory at : %s' % mylar.CONFIG.BLACKHOLE_DIR)
        if os.path.exists(mylar.CONFIG.BLACKHOLE_DIR):
            # copy the nzb from nzbpath to blackhole dir.
            try:
                shutil.move(nzbpath, os.path.join(mylar.CONFIG.BLACKHOLE_DIR, nzbname))
            except (OSError, IOError):
                logger.warn(
                    'Failed to move nzb into blackhole directory - check blackhole'
                    ' directory and/or permissions.'
                )
                return "blackhole-fail"
            logger.fdebug('Filename saved to your blackhole as : %s' % nzbname)
            logger.info(
                'Successfully sent .nzb to your Blackhole directory : %s'
                % (os.path.join(mylar.CONFIG.BLACKHOLE_DIR, nzbname))
            )
            sent_to = "has sent it to your Blackhole Directory"

            if mylar.CONFIG.ENABLE_SNATCH_SCRIPT:
                if comicinfo[0]['pack'] is False:
                    pnumbers = None
                    plist = None
                else:
                    pnumbers = '|'.join(comicinfo[0]['pack_numbers'])
                    plist = '|'.join(comicinfo[0]['pack_issuelist'])
                snatch_vars = {
                    'nzbinfo': {
                        'link': link,
                        'id': nzbid,
                        'nzbname': nzbname,
                        'nzbpath': nzbpath,
                        'blackhole': mylar.CONFIG.BLACKHOLE_DIR,
                    },
                    'comicinfo': {
                        'comicname': ComicName,
                        'volume': comicinfo[0]['ComicVolume'],
                        'comicid': ComicID,
                        'issueid': IssueID,
                        'issuearcid': IssueArcID,
                        'issuenumber': IssueNumber,
                        'issuedate': comicinfo[0]['IssueDate'],
                        'seriesyear': comyear,
                    },
                    'pack': comicinfo[0]['pack'],
                    'pack_numbers': pnumbers,
                    'pack_issuelist': plist,
                    'provider': nzbprov,
                    'method': 'nzb',
                    'clientmode': 'blackhole',
                }

                snatchitup = helpers.script_env('on-snatch', snatch_vars)
                if snatchitup is True:
                    logger.info('Successfully submitted on-grab script as requested.')
                else:
                    logger.info(
                        'Could not Successfully submit on-grab script as requested.'
                        ' Please check logs...'
                    )
    # end blackhole

    # torrents (32P & DEM)
    elif any(
        [nzbprov == '32P', nzbprov == 'WWT', nzbprov == 'DEM', nzbprov == 'torznab']
    ):
        logger.fdebug('ComicName: %s' % ComicName)
        logger.fdebug('link: %s' % link)
        logger.fdebug('Torrent Provider: %s' % nzbprov)

        # nzbid = hash for usage with public torrents
        rcheck = rsscheck.torsend2client(
            ComicName, IssueNumber, comyear, link, nzbprov, nzbid
        )
        if rcheck == "fail":
            if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING:
                logger.error(
                    'Unable to send torrent to client. Assuming incomplete link -'
                    ' sending to Failed Handler and continuing search.'
                )
                if any([oneoff is True, IssueID is None]):
                    logger.fdebug(
                        'One-off mode was initiated - Failed Download handling for :'
                        ' %s #%s' % (ComicName, IssueNumber)
                    )
                    comicinfo = {"ComicName": ComicName, "IssueNumber": IssueNumber}
                else:
                    comicinfo_temp = {
                        "ComicName": comicinfo[0]['ComicName'],
                        "modcomicname": comicinfo[0]['modcomicname'],
                        "IssueNumber": comicinfo[0]['IssueNumber'],
                        "comyear": comicinfo[0]['comyear'],
                    }
                    comicinfo = comicinfo_temp
                return FailedMark(
                    ComicID=ComicID,
                    IssueID=IssueID,
                    id=nzbid,
                    nzbname=nzbname,
                    prov=nzbprov,
                    oneoffinfo=comicinfo,
                )
            else:
                logger.error(
                    'Unable to send torrent - check logs and settings (this would be'
                    ' marked as a BAD torrent if Failed Handling was enabled)'
                )
                return "torrent-fail"
        else:
            """
            Start the auto-snatch segway here (if rcheck isn't False, it contains the
            info of the torrent). Since this is torrentspecific snatch, the vars will
            be different than nzb snatches.
            torrent_info{'folder','name','total_filesize','label','hash',
                         'files','time_started'}
            """
            t_hash = rcheck['hash']
            rcheck.update({'torrent_filename': nzbname})

            if any([mylar.USE_RTORRENT, mylar.USE_DELUGE]) and mylar.CONFIG.AUTO_SNATCH:
                mylar.SNATCHED_QUEUE.put(
                    {'issueid': IssueID, 'comicid': ComicID, 'hash': rcheck['hash']}
                )
            elif (
                any([mylar.USE_RTORRENT, mylar.USE_DELUGE])
                and mylar.CONFIG.LOCAL_TORRENT_PP
            ):
                mylar.SNATCHED_QUEUE.put(
                    {'issueid': IssueID, 'comicid': ComicID, 'hash': rcheck['hash']}
                )
            else:
                if mylar.CONFIG.ENABLE_SNATCH_SCRIPT:
                    try:
                        if comicinfo[0]['pack'] is False:
                            pnumbers = None
                            plist = None
                        else:
                            if '0-Day Comics Pack' in ComicName:
                                helpers.lookupthebitches(
                                    rcheck['files'],
                                    rcheck['folder'],
                                    nzbname,
                                    nzbid,
                                    nzbprov,
                                    t_hash,
                                    comicinfo[0]['IssueDate'],
                                )
                                pnumbers = None
                                plist = None
                            else:
                                pnumbers = '|'.join(comicinfo[0]['pack_numbers'])
                                plist = '|'.join(comicinfo[0]['pack_issuelist'])
                        snatch_vars = {
                            'comicinfo': {
                                'comicname': ComicName,
                                'volume': comicinfo[0]['ComicVolume'],
                                'issuenumber': IssueNumber,
                                'issuedate': comicinfo[0]['IssueDate'],
                                'seriesyear': comyear,
                                'comicid': ComicID,
                                'issueid': IssueID,
                                'issuearcid': IssueArcID,
                            },
                            'pack': comicinfo[0]['pack'],
                            'pack_numbers': pnumbers,
                            'pack_issuelist': plist,
                            'provider': nzbprov,
                            'method': 'torrent',
                            'clientmode': rcheck['clientmode'],
                            'torrentinfo': rcheck,
                        }

                        snatchitup = helpers.script_env('on-snatch', snatch_vars)
                        if snatchitup is True:
                            logger.info(
                                'Successfully submitted on-grab script as requested.'
                            )
                        else:
                            logger.info(
                                'Could not Successfully submit on-grab script as'
                                ' requested. Please check logs...'
                            )
                    except Exception as e:
                        logger.warn('error: %s' % e)

        if mylar.USE_WATCHDIR is True:
            if mylar.CONFIG.TORRENT_LOCAL is True:
                sent_to = 'has sent it to your local Watch folder'
            else:
                sent_to = 'has sent it to your seedbox Watch folder'
        elif mylar.USE_UTORRENT is True:
            sent_to = 'has sent it to your uTorrent client'
        elif mylar.USE_RTORRENT is True:
            sent_to = 'has sent it to your rTorrent client'
        elif mylar.USE_TRANSMISSION is True:
            sent_to = 'has sent it to your Transmission client'
        elif mylar.USE_DELUGE is True:
            sent_to = 'has sent it to your Deluge client'
        elif mylar.USE_QBITTORRENT is True:
            sent_to = 'has sent it to your qBittorrent client'
    # end torrents

    else:
        # SABnzbd / NZBGet

        # nzb.get
        if mylar.USE_NZBGET:
            ss = nzbget.NZBGet()
            send_to_nzbget = ss.sender(nzbpath)
            if mylar.CONFIG.NZBGET_CLIENT_POST_PROCESSING is True:
                if send_to_nzbget['status'] is True:
                    send_to_nzbget['comicid'] = ComicID
                    if IssueID is not None:
                        send_to_nzbget['issueid'] = IssueID
                    else:
                        send_to_nzbget['issueid'] = 'S' + IssueArcID
                    send_to_nzbget['apicall'] = True
                    send_to_nzbget['download_info'] = {'provider': nzbprov, 'id': nzbid}
                    mylar.NZB_QUEUE.put(send_to_nzbget)
                elif send_to_nzbget['status'] == 'double-pp':
                    return send_to_nzbget['status']
                else:
                    logger.warn(
                        'Unable to send nzb file to NZBGet. There was an unknown'
                        ' parameter error'
                    )
                    return "nzbget-fail"

            if send_to_nzbget['status'] is True:
                logger.info("Successfully sent nzb to NZBGet!")
            else:
                logger.info("Unable to send nzb to NZBGet - check your configs.")
                return "nzbget-fail"
            sent_to = "has sent it to your NZBGet"

        # end nzb.get

        elif mylar.USE_SABNZBD:
            sab_params = None
            # let's build the send-to-SAB string now:
            # changed to just work with direct links now...

            # generate the api key to download here and then kill it immediately after.
            if mylar.DOWNLOAD_APIKEY is None:
                import hashlib
                import random

                mylar.DOWNLOAD_APIKEY = hashlib.sha224(
                    str(random.getrandbits(256)).encode('utf-8')
                ).hexdigest()[0:32]

            # generate the mylar host address if applicable.
            if mylar.CONFIG.ENABLE_HTTPS:
                proto = 'https://'
            else:
                proto = 'http://'

            if mylar.CONFIG.HTTP_ROOT is None:
                hroot = '/'
            elif mylar.CONFIG.HTTP_ROOT.endswith('/'):
                hroot = mylar.CONFIG.HTTP_ROOT
            else:
                if mylar.CONFIG.HTTP_ROOT != '/':
                    hroot = mylar.CONFIG.HTTP_ROOT + '/'
                else:
                    hroot = mylar.CONFIG.HTTP_ROOT

            if mylar.LOCAL_IP is None:
                # if mylar's local, get the local IP using socket.
                try:
                    import socket

                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(('8.8.8.8', 80))
                    mylar.LOCAL_IP = s.getsockname()[0]
                    s.close()
                except Exception as e:
                    logger.warn(
                        'Unable to determine local IP. Defaulting to host address for'
                        ' Mylar provided as : %s. Error returned: %s'
                        % (mylar.CONFIG.HTTP_HOST, e)
                    )

            if mylar.CONFIG.HOST_RETURN:
                # mylar has the return value already provided
                # (easier and will work if it's right)
                if mylar.CONFIG.HOST_RETURN.endswith('/'):
                    mylar_host = mylar.CONFIG.HOST_RETURN
                else:
                    mylar_host = mylar.CONFIG.HOST_RETURN + '/'

            elif mylar.CONFIG.SAB_TO_MYLAR:
                # if sab & mylar are on different machines, check to see if they are
                # local or external IP's provided for host.
                if (
                    mylar.CONFIG.HTTP_HOST == 'localhost'
                    or mylar.CONFIG.HTTP_HOST == '0.0.0.0'
                    or mylar.CONFIG.HTTP_HOST.startswith('10.')
                    or mylar.CONFIG.HTTP_HOST.startswith('192.')
                    or mylar.CONFIG.HTTP_HOST.startswith('172.')
                ):
                    # if mylar's local, use the local IP already assigned to LOCAL_IP.
                    mylar_host = (
                        '%s%s:%s%s'
                        % (proto, mylar.LOCAL_IP, mylar.CONFIG.HTTP_PORT, hroot)
                     )
                else:
                    if mylar.EXT_IP is None:
                        # if mylar isn't local, get the external IP using pystun.
                        import stun

                        sip = mylar.CONFIG.HTTP_HOST
                        port = int(mylar.CONFIG.HTTP_PORT)
                        try:
                            nat_type, ext_ip, ext_port = stun.get_ip_info(sip, port)
                            mylar_host = (
                                '%s%s:%s%s'
                                % (proto, ext_ip, ext_port, hroot)
                             )
                            mylar.EXT_IP = ext_ip
                        except Exception as e:
                            logger.warn(
                                'Unable to retrieve External IP - try using the'
                                ' host_return option in the config.ini. Error: %s' % e
                            )
                            mylar_host = (
                                '%s%s:%s%s'
                                % (proto, mylar.CONFIG.HTTP_HOST,
                                   mylar.CONFIG.HTTP_PORT, hroot)
                            )
                    else:
                        mylar_host = (
                            '%s%s:%s%s'
                            % (proto, mylar.EXT_IP, mylar.CONFIG.HTTP_PORT, hroot)
                        )

            else:
                # if all else fails, drop it back to the basic host:port and try that.
                if mylar.LOCAL_IP is None:
                    tmp_host = mylar.CONFIG.HTTP_HOST
                else:
                    tmp_host = mylar.LOCAL_IP
                mylar_host = (
                    proto + str(tmp_host) + ':' + str(mylar.CONFIG.HTTP_PORT) + hroot
                )

            fileURL = (
                mylar_host
                + 'api?apikey='
                + mylar.DOWNLOAD_APIKEY
                + '&cmd=downloadNZB&nzbname='
                + nzbname
            )

            sab_params = {
                'apikey': mylar.CONFIG.SAB_APIKEY,
                'mode': 'addurl',
                'name': fileURL,
                'cmd': 'downloadNZB',
                'nzbname': nzbname,
                'output': 'json',
            }

            # determine SAB priority
            if mylar.CONFIG.SAB_PRIORITY:
                # setup the priorities.
                if mylar.CONFIG.SAB_PRIORITY == 'Default':
                    sabpriority = '-100'
                elif mylar.CONFIG.SAB_PRIORITY == 'Low':
                    sabpriority = '-1'
                elif mylar.CONFIG.SAB_PRIORITY == 'Normal':
                    sabpriority = '0'
                elif mylar.CONFIG.SAB_PRIORITY == 'High':
                    sabpriority = '1'
                elif mylar.CONFIG.SAB_PRIORITY == 'Paused':
                    sabpriority = '-2'
            else:
                # if sab priority isn't selected, default to Normal (0)
                sabpriority = '0'

            sab_params['priority'] = sabpriority

            # if category is blank, let's adjust
            if mylar.CONFIG.SAB_CATEGORY:
                sab_params['cat'] = mylar.CONFIG.SAB_CATEGORY

            if sab_params is not None:
                ss = sabnzbd.SABnzbd(sab_params)
                sendtosab = ss.sender()
                if all(
                    [
                        sendtosab['status'] is True,
                        mylar.CONFIG.SAB_CLIENT_POST_PROCESSING is True,
                    ]
                ):
                    sendtosab['comicid'] = ComicID
                    if IssueID is not None:
                        sendtosab['issueid'] = IssueID
                    else:
                        sendtosab['issueid'] = 'S' + IssueArcID
                    sendtosab['apicall'] = True
                    sendtosab['download_info'] = {'provider': nzbprov, 'id': nzbid}
                    logger.info('sendtosab: %s' % sendtosab)
                    mylar.NZB_QUEUE.put(sendtosab)
                elif sendtosab['status'] == 'double-pp':
                    return sendtosab['status']
                elif sendtosab['status'] is False:
                    return 'sab-fail'
            else:
                logger.warn(
                    'Unable to send nzb file to SABnzbd. There was a parameter error as'
                    ' there are no values present: %s'
                    % sab_params
                )
                mylar.DOWNLOAD_APIKEY = None
                return 'sab-fail'

            sent_to = 'has sent it to your SABnzbd+'
            logger.info('Successfully sent nzb file to SABnzbd')

        if mylar.CONFIG.ENABLE_SNATCH_SCRIPT:
            if mylar.USE_NZBGET:
                clientmode = 'nzbget'
                client_id = '%s' % send_to_nzbget['NZBID']
            elif mylar.USE_SABNZBD:
                clientmode = 'sabnzbd'
                client_id = sendtosab['nzo_id']

            if comicinfo[0]['pack'] is False:
                pnumbers = None
                plist = None
            else:
                pnumbers = '|'.join(comicinfo[0]['pack_numbers'])
                plist = '|'.join(comicinfo[0]['pack_issuelist'])
            snatch_vars = {
                'nzbinfo': {
                    'link': link,
                    'id': nzbid,
                    'client_id': client_id,
                    'nzbname': nzbname,
                    'nzbpath': nzbpath,
                },
                'comicinfo': {
                    'comicname': comicinfo[0]['ComicName'].encode('utf-8'),
                    'volume': comicinfo[0]['ComicVolume'],
                    'comicid': ComicID,
                    'issueid': IssueID,
                    'issuearcid': IssueArcID,
                    'issuenumber': IssueNumber,
                    'issuedate': comicinfo[0]['IssueDate'],
                    'seriesyear': comyear,
                },
                'pack': comicinfo[0]['pack'],
                'pack_numbers': pnumbers,
                'pack_issuelist': plist,
                'provider': nzbprov,
                'method': 'nzb',
                'clientmode': clientmode,
            }

            snatchitup = helpers.script_env('on-snatch', snatch_vars)
            if snatchitup is True:
                logger.info('Successfully submitted on-grab script as requested.')
            else:
                logger.info(
                    'Could not Successfully submit on-grab script as requested.'
                    ' Please check logs...'
                )

    # nzbid, nzbname, sent_to
    nzbname = re.sub('.nzb', '', nzbname).strip()

    return_val = {}
    return_val = {
        "nzbid": nzbid,
        "nzbname": nzbname,
        "sent_to": sent_to,
        "SARC": SARC,
        "alt_nzbname": alt_nzbname,
        "t_hash": t_hash,
    }

    # if it's a directsend link (ie. via a retry).
    if directsend is None:
        return return_val
    else:
        if 'Public Torrents' in tmpprov and any([nzbprov == 'WWT', nzbprov == 'DEM']):
            tmpprov = re.sub('Public Torrents', nzbprov, tmpprov)
        # update the db on the snatch.
        if alt_nzbname is None or alt_nzbname == '':
            logger.fdebug(
                'Found matching comic...preparing to send to Updater with IssueID %s'
                ' and nzbname of %s [Oneoff:%s]'
                % (IssueID, nzbname, oneoff)
            )
            if '[RSS]' in tmpprov:
                tmpprov = re.sub(r'\[RSS\]', '', tmpprov).strip()
            updater.nzblog(
                IssueID,
                nzbname,
                ComicName,
                SARC=SARC,
                IssueArcID=IssueArcID,
                id=nzbid,
                prov=tmpprov,
                oneoff=oneoff,
            )
        else:
            logger.fdebug(
                'Found matching comic...preparing to send to Updater with IssueID %s'
                ' and nzbname of %s [ALTNZBNAME:%s][OneOff:%s]'
                % (IssueID, nzbname, alt_nzbname, oneoff)
            )
            if '[RSS]' in tmpprov:
                tmpprov = re.sub(r'\[RSS\]', '', tmpprov).strip()
            updater.nzblog(
                IssueID,
                nzbname,
                ComicName,
                SARC=SARC,
                IssueArcID=IssueArcID,
                id=nzbid,
                prov=tmpprov,
                alt_nzbname=alt_nzbname,
                oneoff=oneoff,
            )
        # send out notifications for on snatch after the updater incase notification
        # fails (it would bugger up the updater/pp scripts)
        notify_snatch(sent_to, ComicName, comyear, IssueNumber, tmpprov, False)
        mylar.TMP_PROV = nzbprov
        return return_val


def notify_snatch(sent_to, comicname, comyear, IssueNumber, nzbprov, pack):
    if pack is False:
        snline = 'Issue snatched!'
    else:
        snline = 'Pack snatched!'

    if IssueNumber is not None:
        snatched_name = '%s (%s) #%s' % (comicname, comyear, IssueNumber)
    else:
        snatched_name = '%s (%s)' % (comicname, comyear)

    nzbprov = re.sub(r'\(newznab\)', '', nzbprov).strip()
    nzbprov = re.sub(r'\(torznab\)', '', nzbprov).strip()

    if mylar.CONFIG.PROWL_ENABLED and mylar.CONFIG.PROWL_ONSNATCH:
        logger.info("Sending Prowl notification")
        prowl = notifiers.PROWL()
        prowl.notify(snatched_name, 'Download started using %s' % sent_to)
    if mylar.CONFIG.PUSHOVER_ENABLED and mylar.CONFIG.PUSHOVER_ONSNATCH:
        logger.info("Sending Pushover notification")
        pushover = notifiers.PUSHOVER()
        pushover.notify(
            snline, snatched_nzb=snatched_name, prov=nzbprov, sent_to=sent_to
        )
    if mylar.CONFIG.BOXCAR_ENABLED and mylar.CONFIG.BOXCAR_ONSNATCH:
        logger.info("Sending Boxcar notification")
        boxcar = notifiers.BOXCAR()
        boxcar.notify(snatched_nzb=snatched_name, sent_to=sent_to, snline=snline)
    if mylar.CONFIG.PUSHBULLET_ENABLED and mylar.CONFIG.PUSHBULLET_ONSNATCH:
        logger.info("Sending Pushbullet notification")
        pushbullet = notifiers.PUSHBULLET()
        pushbullet.notify(
            snline=snline,
            snatched=snatched_name,
            sent_to=sent_to,
            prov=nzbprov,
            method='POST',
        )
    if mylar.CONFIG.TELEGRAM_ENABLED and mylar.CONFIG.TELEGRAM_ONSNATCH:
        logger.info("Sending Telegram notification")
        telegram = notifiers.TELEGRAM()
        telegram.notify("%s - %s - Mylar %s" % (snline, snatched_name, sent_to))
    if mylar.CONFIG.SLACK_ENABLED and mylar.CONFIG.SLACK_ONSNATCH:
        logger.info("Sending Slack notification")
        slack = notifiers.SLACK()
        slack.notify(
            "Snatched",
            snline,
            snatched_nzb=snatched_name,
            sent_to=sent_to,
            prov=nzbprov,
        )
    if mylar.CONFIG.DISCORD_ENABLED and mylar.CONFIG.DISCORD_ONSNATCH:
        logger.info("Sending Discord notification")
        discord = notifiers.DISCORD()
        discord.notify(
            "Snatched",
            snline,
            snatched_nzb=snatched_name,
            sent_to=sent_to,
            prov=nzbprov,
        )
    if mylar.CONFIG.EMAIL_ENABLED and mylar.CONFIG.EMAIL_ONGRAB:
        logger.info("Sending email notification")
        email = notifiers.EMAIL()
        email.notify(
            snline + " - " + snatched_name,
            "Mylar notification - Snatch",
            module="[SEARCH]",
        )

    return


def FailedMark(IssueID, ComicID, id, nzbname, prov, oneoffinfo=None):
    # Used to pass a failed attempt at sending a download to a client, to the failed
    # handler, and then back again to continue searching.

    from mylar import Failed

    FailProcess = Failed.FailedProcessor(
        issueid=IssueID,
        comicid=ComicID,
        id=id,
        nzb_name=nzbname,
        prov=prov,
        oneoffinfo=oneoffinfo,
    )
    FailProcess.markFailed()

    if prov == '32P' or prov == 'Public Torrents':
        return "torrent-fail"
    else:
        return "downloadchk-fail"


def IssueTitleCheck(
    issuetitle,
    watchcomic_split,
    splitit,
    splitst,
    issue_firstword,
    hyphensplit,
    orignzb=None,
):
    vals = []
    isstitle_chk = False

    logger.fdebug("incorrect comic lengths...not a match")

    issuetitle = re.sub(r'[\-\:\,\?\.]', ' ', str(issuetitle))
    issuetitle_words = issuetitle.split(None)
    # issue title comparison here:
    logger.fdebug(
        'there are %s words in the issue title of : %s'
        % (len(issuetitle_words), issuetitle)
    )
    # we minus 1 the splitst since the issue # is included in there.
    if (splitst - 1) > len(watchcomic_split):
        logger.fdebug('splitit:' + str(splitit))
        logger.fdebug('splitst:' + str(splitst))
        logger.fdebug('len-watchcomic:' + str(len(watchcomic_split)))
        possibleissue_num = splitit[len(watchcomic_split)]  # [splitst]
        logger.fdebug('possible issue number of : %s' % possibleissue_num)
        extra_words = splitst - len(watchcomic_split)
        logger.fdebug(
            'there are %s left over after we remove the series title.' % extra_words
        )
        wordcount = 1
        # remove the series title here so we just have the 'hopefully' issue title
        for word in splitit:
            # logger.info('word: ' + str(word))
            if wordcount > len(watchcomic_split):
                # logger.info('wordcount: ' + str(wordcount))
                # logger.info('watchcomic_split: ' + str(len(watchcomic_split)))
                if wordcount - len(watchcomic_split) == 1:
                    search_issue_title = word
                    possibleissue_num = word
                else:
                    search_issue_title += ' ' + word
            wordcount += 1

        decit = search_issue_title.split(None)
        if decit[0].isdigit() and decit[1].isdigit():
            logger.fdebug(
                'possible decimal - referencing position from original title.'
            )
            chkme = orignzb.find(decit[0])
            chkend = orignzb.find(decit[1], chkme + len(decit[0]))
            chkspot = orignzb[chkme : chkend + 1]
            print(chkme, chkend)
            print(chkspot)
            # we add +1 to decit totals in order to account for the '.' that's
            # missing and we assume is there.
            if len(chkspot) == (len(decit[0]) + len(decit[1]) + 1):
                logger.fdebug('lengths match for possible decimal issue.')
                if '.' in chkspot:
                    logger.fdebug('decimal located within : %s' % chkspot)
                    possibleissue_num = chkspot
                    splitst = (
                        splitst - 1
                    )  # remove the second numeric it's a decimal & would add extra char

        logger.fdebug('search_issue_title is : %s' % search_issue_title)
        logger.fdebug('possible issue number of : %s' % possibleissue_num)

        if hyphensplit is not None and 'of' not in search_issue_title:
            logger.fdebug('hypen split detected.')
            try:
                issue_start = search_issue_title.find(issue_firstword)
                logger.fdebug(
                    'located first word of : %s at position : %s'
                    % (issue_firstword, issue_start)
                )
                search_issue_title = search_issue_title[issue_start:]
                logger.fdebug(
                    'corrected search_issue_title is now : %s' % search_issue_title
                )
            except TypeError:
                logger.fdebug('invalid parsing detection. Ignoring this result.')
                return vals.append(
                    {
                        "splitit": splitit,
                        "splitst": splitst,
                        "isstitle_chk": isstitle_chk,
                        "status": "continue",
                    }
                )
        # now we have the nzb issue title (if it exists), let's break it down further.
        sit_split = search_issue_title.split(None)
        watch_split_count = len(issuetitle_words)
        isstitle_removal = []
        isstitle_match = 0  # counter to tally % match
        misword = (
            0  # counter to tally words that probably don't need to be an 'exact' match.
        )
        for wsplit in issuetitle_words:
            of_chk = False
            if wsplit.lower() == 'part' or wsplit.lower() == 'of':
                if wsplit.lower() == 'of':
                    of_chk = True
                logger.fdebug('not worrying about this word : %s' % wsplit)
                misword += 1
                continue
            if wsplit.isdigit() and of_chk is True:
                logger.fdebug('of %s detected. Ignoring for matching.' % wsplit)
                of_chk = False
                continue

            for sit in sit_split:
                logger.fdebug('looking at : %s -TO- %s' % (sit.lower(), wsplit.lower()))
                if sit.lower() == 'part':
                    logger.fdebug('not worrying about this word : %s' % sit)
                    misword += 1
                    isstitle_removal.append(sit)
                    break
                elif sit.lower() == wsplit.lower():
                    logger.fdebug('word match: %s' % sit)
                    isstitle_match += 1
                    isstitle_removal.append(sit)
                    break
                else:
                    try:
                        if int(sit) == int(wsplit):
                            logger.fdebug('found matching numeric: %s' % wsplit)
                            isstitle_match += 1
                            isstitle_removal.append(sit)
                            break
                    except Exception:
                        pass

        logger.fdebug('isstitle_match count : %s' % isstitle_match)
        if isstitle_match > 0:
            iss_calc = ((isstitle_match + misword) / watch_split_count) * 100
            logger.fdebug(
                'iss_calc: %s %s with %s unaccounted for words'
                % (iss_calc, '%', misword)
            )
        else:
            iss_calc = 0
            logger.fdebug('0 words matched on issue title.')
        if (
            iss_calc >= 80
        ):
            # mylar.ISSUE_TITLEMATCH
            # user-defined percentage to match against for issue name comparisons.
            logger.fdebug(
                '>80% match on issue name. If this were implemented, this would be'
                ' considered a match.'
            )
            logger.fdebug(
                'we should remove %s words : %s'
                % (len(isstitle_removal), isstitle_removal)
            )
            logger.fdebug(
                'Removing issue title from nzb filename to improve matching algorithims'
            )
            splitst = splitst - len(isstitle_removal)
            isstitle_chk = True
            vals.append(
                {
                    "splitit": splitit,
                    "splitst": splitst,
                    "isstitle_chk": isstitle_chk,
                    "possibleissue_num": possibleissue_num,
                    "isstitle_removal": isstitle_removal,
                    "status": 'ok',
                }
            )
            return vals
    return


def generate_id(nzbprov, link):
    # logger.fdebug('[%s] generate_id - link: %s' % (nzbprov, link))
    if nzbprov == 'experimental':
        # id is located after the /download/ portion
        url_parts = urllib.parse.urlparse(link)
        path_parts = url_parts[2].rpartition('/')
        nzbtempid = path_parts[0].rpartition('/')
        nzblen = len(nzbtempid)
        nzbid = nzbtempid[nzblen - 1]
    elif nzbprov == '32P':
        # 32P just has the torrent id stored.
        nzbid = link
    elif any([nzbprov == 'WWT', nzbprov == 'DEM']):
        if 'http' not in link and any([nzbprov == 'WWT', nzbprov == 'DEM']):
            nzbid = link
        else:
            # for users that already have the cache in place.
            url_parts = urllib.parse.urlparse(link)
            path_parts = url_parts[2].rpartition('/')
            nzbtempid = path_parts[2]
            nzbid = re.sub('.torrent', '', nzbtempid).rstrip()
    elif nzbprov == 'nzb.su':
        nzbid = os.path.splitext(link)[0].rsplit('/', 1)[1]
    elif nzbprov == 'dognzb':
        url_parts = urllib.parse.urlparse(link)
        path_parts = url_parts[2].rpartition('/')
        nzbid = path_parts[0].rsplit('/', 1)[1]
    elif 'newznab' in nzbprov:
        # if in format of http://newznab/getnzb/<id>.nzb&i=1&r=apikey
        tmpid = urllib.parse.urlparse(link)[
            4
        ]  # param 4 is the query string from the url.
        if 'searchresultid' in tmpid:
            nzbid = os.path.splitext(link)[0].rsplit('searchresultid=', 1)[1]
        elif tmpid == '' or tmpid is None:
            nzbid = os.path.splitext(link)[0].rsplit('/', 1)[1]
        else:
            nzbinfo = urllib.parse.parse_qs(link)
            nzbid = nzbinfo.get('id', None)
            if nzbid is not None:
                nzbid = ''.join(nzbid)
        if nzbid is None:
            # if apikey is passed in as a parameter and the id is in the path
            findend = tmpid.find('&')
            if findend == -1:
                findend = len(tmpid)
                nzbid = tmpid[findend + 1 :].strip()
            else:
                findend = tmpid.find('apikey=', findend)
                nzbid = tmpid[findend + 1 :].strip()
            if '&id' not in tmpid or nzbid == '':
                tmpid = urllib.parse.urlparse(link)[2]
                nzbid = tmpid.rsplit('/', 1)[1]
    elif nzbprov == 'torznab':
        idtmp = urllib.parse.urlparse(link)[4]
        idpos = idtmp.find('&')
        nzbid = re.sub('id=', '', idtmp[:idpos]).strip()
    return nzbid
