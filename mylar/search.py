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
    search_filer,
    getcomics,
    downloaders,
)
from mylar.downloaders import external_server as exs
from mylar.downloaders import airdcpp

import feedparser
import requests
import os
import errno
import sys
import re
import time
import pathlib
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import unquote, urlparse, urljoin
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
    rsschecker=None,
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
    #unaltered_ComicName = None
    #if filesafe:
    #    if filesafe != ComicName and smode != 'want_ann':
    #        logger.info(
    #            '[SEARCH] Special Characters exist within Series Title. Enabling'
    #            ' search-safe Name : %s' % filesafe
    #        )
    #        if AlternateSearch is None or AlternateSearch == 'None':
    #            AlternateSearch = filesafe
    #        else:
    #            AlternateSearch += '##' + filesafe
    #        unaltered_ComicName = ComicName

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

    provider_list = provider_order(initial_run=True)
    findit = {}
    findit['status'] = False

    if provider_list['totalproviders'] == 0:
        logger.error(
            '[WARNING] You have %s search providers enabled. I need at least ONE'
            ' provider to work. Aborting search.'
            % provider_list['totalproviders']
        )
        findit['status'] = False
        nzbprov = None
        return findit, nzbprov

    logger.fdebug('search provider order is %s' % provider_list['prov_order'])

    # fix for issue dates between Nov-Dec/(Jan-Feb-Mar)
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
    else:
        IssDt = str(IssueDate)[5:7]
        if any(
            [
                IssDt == "12",
                IssDt == "11",
                IssDt == "01",
                IssDt == "02",
                IssDt == "03"
            ]
        ):
            IssDateFix = IssDt

    searchcnt = 0
    srchloop = 1
    current_prov = {}  # Initialize current_prov here to avoid UnboundLocalError

    if rsschecker:
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

    findcomiciss, c_number = get_findcomiciss(IssueNumber)

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
            cmloopit = None
            if any([booktype == 'One-Shot', 'annual' in ComicName.lower()]):
                cmloopit = 4
                if 'annual' in ComicName.lower():
                    if IssueNumber is not None:
                        if helpers.issue_number_parser(IssueNumber).asInt != helpers.issue_number_to_int(1, None):
                            cmloopit = None
            if cmloopit is None:
                if len(c_number) == 1:
                    cmloopit = 3
                elif len(c_number) == 2:
                    cmloopit = 2
                else:
                    cmloopit = 1
        logger.info('cmloopit: %s' % cmloopit)
        chktpb = 0
        if any([booktype == 'TPB', booktype =='HC', booktype == 'GN']):
            chktpb = 1

        if findit['status'] is True:
            logger.fdebug('Found result on first run, exiting search module now.')
            break

        logger.fdebug('Initiating Search via : %s' % searchmode)

        if len(provider_list['prov_order']) == 1:
            tmp_prov_count = 1
        else:
            tmp_prov_count = len(provider_list['prov_order'])

        checked_once = []
        prov_count = 0

        while tmp_prov_count > prov_count:
            logger.info('tmp_prov_count: %s / prov_count: %s' % (tmp_prov_count,prov_count))
            tmp_cmloopit = cmloopit
            while tmp_cmloopit >= 1:
                if tmp_cmloopit == 4:
                    tmp_IssueNumber = None
                else:
                    tmp_IssueNumber = IssueNumber


                prov_order = provider_list['prov_order']
                logger.info('checked_once: %s' %(checked_once,))
                if checked_once:
                    if prov_order[prov_count] in checked_once:
                        break
                provider_blocked = helpers.block_provider_check(prov_order[prov_count])
                if provider_blocked:
                    logger.warn('provider blocked. Ignoring search on this provider.')
                    break
                send_prov_count = tmp_prov_count - prov_count
                newznab_host = None
                torznab_host = None
                logger.info('prov_order[prov_count]: %s' % (prov_order[prov_count],))

                # this loads the previous runs from the db to ensure we're always persistant
                searchprov = last_run_check(check=True)
                #logger.fdebug('searchprov: %s' % (searchprov,))

                #should be DDL(GetComics)
                if prov_order[prov_count] == 'DDL(GetComics)' and not provider_blocked and 'DDL(GetComics)' not in checked_once:
                    if 'DDL(GetComics)' not in searchprov.keys():
                       searchprov['DDL(GetComics)'] = ({'id': 200, 'type': 'DDL', 'lastrun': 0, 'active': True, 'hits': 0})
                    else:
                        searchprov['DDL(GetComics)']['active'] = True
                elif prov_order[prov_count] == 'DDL(External)' and not provider_blocked and 'DDL(External)' not in checked_once:
                    if 'DDL(External)' not in searchprov.keys():
                        searchprov['DDL(External)'] = ({'id': 201, 'type': 'DDL(External)', 'lastrun': 0, 'active': True, 'hits': 0})
                    else:
                        searchprov['DDL(External)']['active'] = True
                elif prov_order[prov_count] == '32p' and not provider_blocked:
                    searchprov['32P'] = ({'type': 'torrent', 'lastrun': 0, 'active': True, 'hits': 0})
                elif prov_order[prov_count].lower() == 'experimental' and not provider_blocked and 'experimental' not in checked_once:
                    if all(['experimental' not in searchprov.keys(), 'Experimental' not in searchprov.keys()]):
                        prov_order[prov_count] = 'experimental'  # cause it's Experimental for display
                        logger.info('resetting searchprov - last run here..')
                        searchprov['experimental'] = ({'id': 101, 'type': 'experimental', 'lastrun': 0, 'active': True, 'hits': 0})
                    else:
                        searchprov['experimental']['active'] = True
                elif (
                    prov_order[prov_count] == 'public torrents' and not provider_blocked
                ):
                    if 'Public Torrents' not in searchprov.keys():
                        searchprov['Public Torrents'] = ({'id': mylar.PROVIDER_START_ID+1, 'type': 'torrent', 'lastrun': 0, 'active': True, 'hits': 0})
                    else:
                        searchprov['Public Torrents']['active'] = True
                elif 'torznab' in prov_order[prov_count]:
                    fnd = False
                    for nninfo in provider_list['torznab_info']:
                        torznab_host = nninfo['info']
                        if torznab_host is None:
                            logger.fdebug(
                                'there was an error - torznab information was blank and'
                                ' it should not be.'
                            )
                            break
                        if all(
                               [
                                   nninfo['provider'] == prov_order[prov_count],
                                   not provider_blocked,
                                   torznab_host[0] not in searchprov.keys(),
                               ]
                        ):
                            searchprov[torznab_host[0]] = ({'id': mylar.PROVIDER_START_ID+1, 'type': 'torznab', 'lastrun': 0, 'active': True, 'hits': 0})
                            fnd = True
                        elif all(
                                 [
                                   nninfo['provider'] == prov_order[prov_count],
                                   not provider_blocked,
                                   torznab_host[0] in searchprov.keys(),
                                 ]
                        ):
                            searchprov[torznab_host[0]]['active'] = True
                            fnd = True
                        if fnd is True:
                            break
                elif 'newznab' in prov_order[prov_count]:
                    fnd = False
                    for nninfo in provider_list['newznab_info']:
                        newznab_host = nninfo['info']
                        if newznab_host is None:
                            logger.fdebug(
                                'there was an error - newznab information was blank and it'
                                ' should not be.'
                            )
                            break
                        if all(
                               [
                                   nninfo['provider'] == prov_order[prov_count],
                                   not provider_blocked,
                                   newznab_host[0] not in searchprov.keys(),
                               ]
                        ):
                            searchprov[newznab_host[0]] = ({'id': mylar.PROVIDER_START_ID+1, 'type': 'newznab', 'lastrun': 0, 'active': True, 'hits': 0})
                            fnd = True
                        elif all(
                                 [
                                   nninfo['provider'] == prov_order[prov_count],
                                   not provider_blocked,
                                   newznab_host[0] in searchprov.keys(),
                                 ]
                        ):
                            searchprov[newznab_host[0]]['active'] = True
                            fnd = True
                        if fnd is True:
                            break
                else:
                    logger.info('why here? resetting searchprov - last run here..')
                    newznab_host = None
                    torznab_host = None
                    if prov_order[prov_count].lower() not in searchprov.keys():
                        searchprov[prov_order[prov_count].lower()] = ({'id': mylar.PROVIDER_START_ID+1, 'type': prov_order[prov_count].lower(), 'lastrun': 0, 'active': True, 'hits': 0})
                    else:
                        searchprov[prov_order[prov_count].lower()]['active'] = True

                #logger.fdebug('searchprov: %s' % (searchprov,))
                # mark the currently active provider here.
                current_prov = get_current_prov(searchprov)
                logger.info('current_prov: %s' % (current_prov))

                if all(
                         [
                              not provider_blocked,
                             ''.join(current_prov.keys()) in checked_once,
                         ]
                    ):
                    break

                logger.info('tmp_cmloopit: %s [Issue #:%s]' % (tmp_cmloopit, tmp_IssueNumber))

                scarios = {'tmp_IssueNumber': tmp_IssueNumber,
                           'ComicYear': ComicYear,
                           'SeriesYear': SeriesYear,
                           'Publisher': Publisher,
                           'IssueDate': IssueDate,
                           'StoreDate': StoreDate,
                           'current_prov': current_prov,
                           'send_prov_count': send_prov_count,
                           'IssDateFix': IssDateFix,
                           'IssueID': IssueID,
                           'UseFuzzy': UseFuzzy,
                           'newznab_host': newznab_host,
                           'ComicVersion': ComicVersion,
                           'SARC': SARC,
                           'IssueArcID': IssueArcID,
                           'ComicID': ComicID,
                           'issuetitle': issuetitle,
                           'oneoff':oneoff,
                           'cmloopit':tmp_cmloopit,
                           'manual':manual,
                           'torznab_host': torznab_host,
                           'digitaldate': digitaldate,
                           'booktype': booktype,
                           'chktpb': chktpb,
                           'ignore_booktype': ignore_booktype,
                           'smode': smode,
                           'findit': findit
                         }


                if searchmode == 'rss':
                    logger.info('RSS searchmode enabled for %s' % ComicName)
                    scarios['RSS'] = 'yes'
                    for xx in gen_altnames(ComicName, AlternateSearch, filesafe, smode):
                        logger.info('comicname searched for: %s' % ComicName)
                        if all([findit['status'] is False, not provider_blocked]):
                            scarios['ComicName'] = xx['ComicName']
                            scarios['unaltered_ComicName'] = xx['unaltered_ComicName']
                            findit = search_the_matrix(scarios)
                            if findit['status'] is True:
                                logger.fdebug("findit = found!")
                                break

                else:
                    logger.info('API searchmode enabled for %s' % ComicName)
                    scarios['RSS'] = 'no'
                    for xx in gen_altnames(ComicName, AlternateSearch, filesafe, smode):
                        logger.info('comicname searched for: %s' % ComicName)
                        if all([findit['status'] is False, not provider_blocked]):
                            scarios['ComicName'] = xx['ComicName']
                            scarios['unaltered_ComicName'] = xx['unaltered_ComicName']
                            findit = search_the_matrix(scarios)
                            logger.info('findit: %s' % (findit,))
                            if findit['status'] is True:
                                logger.fdebug("findit = found!")
                                break

                if findit['status'] is True:
                    #logger.fdebug("findit = found!")
                    break

                if all(
                       [
                           not provider_blocked,
                           ''.join(current_prov.keys()) not in checked_once,
                       ]
                      ) and ''.join(current_prov.keys()) in (
                          '32P',
                          'DDL(GetComics)',
                          'DDL(External)',
                          'Public Torrents',
                          'experimental',
                      ):
                          logger.info('check_once check.')
                          checked_once.append(''.join(current_prov.keys()))

                if current_prov.get('newznab'):
                    current_prov[newznab_host[0].rstrip()] = current_prov.pop('newznab')
                elif current_prov.get('torznab'):
                    current_prov[torznab_host[0].rstrip()] = current_prov.pop('torznab')
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
                            if 'annual' in ComicName.lower():
                                if re.findall('(?:19|20)\d{2}', ComicName):
                                    issuedisplay = None

                    if issuedisplay is None:
                        logger.info(
                            'Could not find %s (%s) using %s [%s]'
                            % (ComicName, SeriesYear, list(current_prov.keys())[0], searchmode)
                        )
                    else:
                        logger.info(
                            'Could not find Issue %s of %s (%s) using %s [%s]'
                            % (
                                issuedisplay,
                                ComicName,
                                SeriesYear,
                                list(current_prov.keys())[0],
                                searchmode,
                            )
                        )
                if findit['status'] is True:
                    if current_prov.get('newznab'):
                        current_prov[newznab_host[0].rstrip() + ' (newznab)'] = current_prov.pop('newznab')
                    elif current_prov.get('torznab'):
                        current_prov[torznab_host[0].rstrip() + ' (torznab)'] = current_prov.pop('torznab')
                    srchloop = 4
                    break
                elif srchloop == 2 and (tmp_cmloopit - 1 >= 1) and ''.join(current_prov.keys()) not in checked_once:
                    # don't think this is needed as we do the check_time btwn searches now
                    pass

                tmp_cmloopit -= 1


            prov_count += 1
            logger.info('attempting to set %s to not being the active provider.'% (list(current_prov.keys())[0]))
            if findit['lastrun'] != 0:
               logger.info('setting last run to: %s' % (findit['lastrun']))
               last_run_check(write={''.join(current_prov.keys()): {'active': False, 'lastrun': findit['lastrun'], 'type': current_prov[list(current_prov.keys())[0]]['type'], 'hits': current_prov[list(current_prov.keys())[0]]['hits'], 'id': current_prov[list(current_prov.keys())[0]]['id']}})
               #current_prov[list(current_prov.keys())[0]]['lastrun'] = findit['lastrun']
            current_prov[list(current_prov.keys())[0]]['active'] = False
            logger.info('setting took. Current provider is: %s' % (current_prov,))


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
        return findit, list(current_prov.keys())[0]
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
        if current_prov.get('32P'):
            if mylar.CONFIG.MODE_32P == 0:
                return findit, 'None'
            elif mylar.CONFIG.MODE_32P == 1 and searchmode == 'api':
                return findit, 'None'

    return findit, 'None'

def provider_order(initial_run=False):
    torprovider = []
    torp = 0
    torznabs = 0
    torznab_hosts = []

    if initial_run:
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
    nzbprovider = []
    nzbp = 0
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

    if mylar.CONFIG.ENABLE_DDL is True:
        if all(
           [
                mylar.CONFIG.ENABLE_GETCOMICS is True,
                not helpers.block_provider_check('DDL(GetComics)'),
           ]
        ):
            ddlprovider.append('DDL(GetComics)')
            ddls+=1

        if all(
            [
                mylar.CONFIG.ENABLE_EXTERNAL_SERVER is True,
                not helpers.block_provider_check('DDL(External)'),
            ]
        ):
            ddlprovider.append('DDL(External)')
            ddls+=1
    if all(
       [
            mylar.CONFIG.ENABLE_AIRDCPP is True,
            not helpers.block_provider_check('AirDCPP'),
       ]
    ):
        ddlprovider.append('AirDCPP')
        ddls+=1

    if initial_run:
        logger.fdebug('nzbprovider(s): %s' % nzbprovider)
    # --------
    torproviders = torp + torznabs
    if initial_run:
        logger.fdebug('There are %s torrent providers you have selected.' % torproviders)
    torpr = torproviders - 1
    if torpr < 0:
        torpr = -1
    providercount = int(nzbp + newznabs)
    if initial_run:
        logger.fdebug('There are : %s nzb providers you have selected' % providercount)
        if providercount > 0:
            logger.fdebug('Usenet Retention : %s days' % mylar.CONFIG.USENET_RETENTION)

    if ddls > 0 and initial_run:
        logger.fdebug(
            'there are %s Direct Download providers that are currently enabled.' % ddls
        )

    totalproviders = providercount + torproviders + ddls

    prov_order, torznab_info, newznab_info = provider_sequence(
        nzbprovider, torprovider, newznab_hosts, torznab_hosts, ddlprovider
    )

    #if initial_run:
    #    logger.fdebug('search provider order is %s' % prov_order)

    return {'prov_order':    prov_order,
            'torznab_info':  torznab_info,
            'newznab_info':  newznab_info,
            'totalproviders': totalproviders}


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
    provider_stat = nzbprov
    #logger.fdebug('provider_stat_before: %s' % (provider_stat))
    if type(nzbprov) != str:
        nzbprov = list(nzbprov.keys())[0]
        provider_stat = provider_stat.get(list(provider_stat.keys())[0])
    #logger.info('nzbprov: %s' % (nzbprov))
    #logger.fdebug('provider_stat_after: %s' % (provider_stat))
    if nzbprov == 'experimental':
        apikey = 'none'
        verify = False
    elif provider_stat['type'] == 'torznab':
        name_torznab = torznab_host[0].rstrip()
        host_torznab = torznab_host[1].rstrip()
        verify = bool(int(torznab_host[2]))
        apikey = torznab_host[3].rstrip()
        category_torznab = torznab_host[4]
        if any([category_torznab is None, category_torznab == 'None']):
            category_torznab = '8020'
        if '#' in category_torznab:
            t_cats = category_torznab.split('#')
            category_torznab = ','.join(t_cats)
        logger.fdebug('Using Torznab host of : %s' % name_torznab)
    elif provider_stat['type'] == 'newznab':
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
        verify = bool(int(newznab_host[2]))
        if '#' in newznab_host[4].rstrip():
            catstart = newznab_host[4].find('#')
            category_newznab = re.sub('#', ',', newznab_host[4][catstart + 1 :]).strip()
            logger.fdebug('Non-default Newznab category set to : %s' % category_newznab)
        else:
            category_newznab = '7030'
        logger.fdebug('Using Newznab host of : %s' % name_newznab)

    if RSS == "yes":
        if provider_stat['type'] == 'newznab':
            tmpprov = '%s (%s) [RSS]' % (name_newznab, provider_stat['type'])
        elif provider_stat['type'] == 'torznab':
            tmpprov = '%s (%s) [RSS]' % (name_torznab, provider_stat['type'])
        else:
            tmpprov = '%s [RSS]' % nzbprov
    else:
        if provider_stat['type'] == 'newznab':
            tmpprov = '%s (%s)' % (name_newznab, provider_stat['type'])
        elif provider_stat['type'] == 'torznab':
            tmpprov = '%s (%s)' % (name_torznab, provider_stat['type'])
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
        intIss = helpers.issue_number_parser(IssueNumber).asInt
        # TODO: Revisit this later to see if the below can be absorbed by the string part of issueNumberParser (and to fix the fraction logic)
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
    #foundcomic = []
    foundc = {}
    foundc['status'] = False
    foundc['provider'] = nzbprov
    foundc['lastrun'] = provider_stat['lastrun']
    done = False

    is_info = {'ComicName': ComicName,
               'nzbprov': nzbprov,
               'RSS': RSS,
               'UseFuzzy': UseFuzzy,
               'StoreDate': StoreDate,
               'IssueDate': IssueDate,
               'digitaldate': digitaldate,
               'booktype': booktype,
               'ignore_booktype': ignore_booktype,
               'SeriesYear': SeriesYear,
               'ComicVersion': ComicVersion,
               'IssDateFix': IssDateFix,
               'ComicYear': ComicYear,
               'IssueID': IssueID,
               'ComicID': ComicID,
               'IssueNumber': IssueNumber,
               'manual': manual,
               'newznab_host': newznab_host,
               'torznab_host': torznab_host,
               'oneoff': oneoff,
               'tmpprov': tmpprov,
               'SARC': SARC,
               'IssueArcID': IssueArcID,
               'cmloopit': cmloopit,
               'findcomiciss': findcomiciss,
               'intIss': intIss,
               'chktpb': chktpb,
               'smode': smode,
               'provider_stat': provider_stat,
               'foundc': foundc}

    # origcmloopit = cmloopit
    # seperatealpha = "no"
    # ---issue problem
    # if issue is '011' instead of '11' in nzb search results, will not have same
    # results. '011' will return different than '11', as will '009' and '09'.
    while findloop < findcount:
        logger.fdebug('findloop: %s / findcount: %s' % (findloop, findcount))
        comsrc = comsearch
        if any([nzbprov == 'Public Torrents', 'DDL' in nzbprov, nzbprov == 'experimental']):
            # DDL iteration is handled in it's own module as is experimental.
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
                is_info['foundc']['status'] = False
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

        #is_info = {'ComicName': ComicName,
        #           'nzbprov': nzbprov,
        #           'RSS': RSS,
        #           'UseFuzzy': UseFuzzy,
        #           'StoreDate': StoreDate,
        #           'IssueDate': IssueDate,
        #           'digitaldate': digitaldate,
        #           'booktype': booktype,
        #           'ignore_booktype': ignore_booktype,
        #           'SeriesYear': SeriesYear,
        #           'ComicVersion': ComicVersion,
        #           'IssDateFix': IssDateFix,
        #           'ComicYear': ComicYear,
        #           'IssueID': IssueID,
        #           'ComicID': ComicID,
        #           'IssueNumber': IssueNumber,
        #           'manual': manual,
        #           'newznab_host': newznab_host,
        #           'torznab_host': torznab_host,
        #           'oneoff': oneoff,
        #           'tmpprov': tmpprov,
        #           'SARC': SARC,
        #           'IssueArcID': IssueArcID,
        #           'cmloopit': cmloopit,
        #           'findcomiciss': findcomiciss,
        #           'intIss': intIss,
        #           'chktpb': chktpb,
        #           'provider_stat': provider_stat,
        #           'foundc': foundc}
        if 'DDL' in nzbprov and RSS == "no":
            cmname = re.sub("%20", " ", str(comsrc))
            logger.fdebug(
                'Sending request to %s site for : %s %s'
                % (nzbprov, findcomic, isssearch)
            )
            if nzbprov == 'DDL(GetComics)':
                if any([isssearch == 'None', isssearch is None]):
                    lineq = findcomic
                else:
                    lineq = '%s %s' % (findcomic, isssearch)
                fline = {'comicname': findcomic,
                         'issue':     isssearch,
                         'year':      comyear}
                b = getcomics.GC(query=fline, provider_stat=provider_stat)
                verified_matches = b.search(is_info=is_info)
            elif nzbprov == 'DDL(External)':
                b = exs.MegaNZ(query='%s' % ComicName, provider_stat=provider_stat)
                verified_matches = b.ddl_search(is_info=is_info)
            #logger.fdebug('bb returned from %s: %s' % (nzbprov, verified_matches))

        elif RSS == "yes" and 'DDL(External)' not in nzbprov:
            if 'DDL(GetComics)' in nzbprov:
                #only GC has an available RSS Feed
                logger.fdebug(
                    'Sending request to [%s] RSS for %s : %s'
                    % (nzbprov, ComicName, mod_isssearch)
                )
                bb = rsscheck.ddl_dbsearch(
                    ComicName, mod_isssearch, ComicID, nzbprov, oneoff
                )
                if all([bb != "no results", bb is not None]):
                    newddl = []
                    for bdb in bb['entries']:
                        ddl_checkpack = rsscheck.ddlrss_pack_detect(bdb['title'], bdb['link'])
                        #logger.fdebug('ddl_checkback: %s' % (ddl_checkpack,))
                        if ddl_checkpack is not None:
                            for dd in bb['entries']:
                                if dd['link'] == ddl_checkpack['link']:
                                    newddl.append({'title': dd['title'],
                                                   'link': dd['link'],
                                                   'pubdate': dd['pubdate'],
                                                   'site': dd['site'],
                                                   'length': dd['length'],
                                                   'issues': ddl_checkpack['issues'],
                                                   'pack': ddl_checkpack['pack']})
                                else:
                                    newddl.append(dd)
                    if len(newddl) > 0:
                        bb['entries'] = newddl
                        #logger.fdebug('final ddlcheckback: %s' % (bb,))
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
            logger.info('bb: %s' % (bb,))
            if any([bb is None, bb == 'no results']):
                verified_matches = 'no results'
            else:
                if len(bb['entries']) > 0:
                    sfs = search_filer.search_check()
                    verified_matches = sfs.checker(bb['entries'], is_info)
                else:
                    verified_matches = 'no results'

        # this is the API calls
        else:
            if nzbprov == '':
                verified_matches = "no results"
            elif nzbprov != 'experimental':
                if provider_stat['type'] == 'newznab':
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
                elif provider_stat['type'] == 'torznab':
                    if host_torznab[len(host_torznab) - 1 : len(host_torznab)] == '/':
                        torznab_fix = host_torznab[:-1]
                    else:
                        torznab_fix = host_torznab
                    findurl = str(torznab_fix) + "?t=search&q=" + str(comsearch)
                    if category_torznab is not None:
                        findurl += "&cat=" + str(category_torznab)
                elif provider_stat['type'] == 'airdcpp':
                    findurl = None
                    cleaned_comicname = re.sub(r'[?:$]', '', findcomic)
                    fline = {'comicname': cleaned_comicname,
                             'issue': isssearch,
                             'year': comyear}
                    b = downloaders.airdcpp.AirDCPP(query=fline, provider_stat=provider_stat)
                    verified_matches = b.search(is_info=is_info)
                else:
                    logger.warn(
                        'You have a blank newznab entry within your configuration.'
                        'Remove it, save the config and restart mylar to fix things.'
                        'Skipping this blank provider until fixed.'
                    )
                    findurl = None
                    verified_matches = "no results"

                if findurl:
                    # helper function to replace apikey here so we avoid logging it ;)
                    findurl = findurl + "&apikey=" + str(apikey)
                    logsearch = helpers.apiremove(str(findurl), 'nzb')

                    # IF USENET_RETENTION is set, honour it
                    # For newznab sites, that means appending "&maxage=<whatever>"
                    # on the URL
                    if (
                        mylar.CONFIG.USENET_RETENTION is not None
                        and provider_stat['type'] != 'torznab'
                    ):
                        findurl = (
                            findurl + "&maxage=" + str(mylar.CONFIG.USENET_RETENTION)
                        )

                    pause_the_search = check_the_search_delay(manual)

                    # bypass for local newznabs
                    # remove the protocol string (http/https)
                    localbypass = False
                    if provider_stat['type'] == 'newznab':
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

                    # check search time here
                    if localbypass is False and foundc['lastrun'] != 0:
                        diff = check_time(foundc['lastrun'])
                        if diff < pause_the_search:
                            logger.warn('[PROVIDER-SEARCH-DELAY][%s] Waiting %s seconds before we search again...' % (nzbprov, (pause_the_search - int(diff))))
                            time.sleep(pause_the_search - int(diff))
                        else:
                            logger.fdebug('[PROVIDER-SEARCH-DELAY][%s] Last search took place %s seconds ago. We\'re clear...' % (nzbprov, int(diff)))

                    try:
                        r = requests.get(
                            findurl, params=payload, verify=verify, headers=headers
                        )
                        r.raise_for_status()
                    except requests.exceptions.Timeout as e:
                        logger.warn(
                            'Timeout occured fetching data from %s: %s' % (nzbprov, e)
                        )
                        is_info['foundc']['status'] = False
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
                        is_info['foundc']['status'] = False
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
                            is_info['foundc']['status'] = False
                        break
                    is_info['foundc']['lastrun'] = time.time()
                    logger.info('setting lastrun for %s to %s' % (is_info['foundc']['provider'], time.ctime(is_info['foundc']['lastrun'])))
                    last_run_check(write={str(nzbprov): {'active': provider_stat['active'], 'lastrun': is_info['foundc']['lastrun'], 'type': provider_stat['type'], 'hits': provider_stat['hits']+1, 'id': provider_stat['id']}})
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
                        verified_matches = feedparser.parse(data)
                    else:
                        verified_matches = "no results"

                    try:
                        if verified_matches == 'no results':
                            logger.fdebug(
                                'No results for search query from %s' % tmpprov
                            )
                            break
                        if verified_matches['feed']['error']:
                            logger.error(
                                '[ERROR CODE: %s] %s'
                                % (
                                    verified_matches['feed']['error']['code'],
                                    verified_matches['feed']['error']['description'],
                                )
                            )
                            if verified_matches['feed']['error']['code'] == '910':
                                logger.warn(
                                    'DAILY API limit reached. Disabling %s' % tmpprov
                                )
                                helpers.disable_provider(tmpprov, 'API Limit reached')
                                verified_matches = "no results"
                                is_info['foundc']['status'] = False
                                done = True
                            else:
                                logger.warn(
                                    'API Error. Check the error message and take action'
                                    ' if required.'
                                )
                                verified_matches = "no results"
                                is_info['foundc']['status'] = False
                                done = True
                            break
                    except Exception as e:
                        logger.fdebug('no errors on data retrieval...proceeding')
                        sfs = search_filer.search_check()
                        verified_matches = sfs.checker(verified_matches["entries"], is_info)

            elif nzbprov == 'experimental':
                logger.info('sending %s to experimental search' % findcomic)
                bb = findcomicfeed.Startit(
                    findcomic, isssearch, comyear, ComicVersion, IssDateFix, booktype
                )
                if any([bb == 'disable', bb == 'no results']):
                    helpers.disable_provider('experimental', 'unresponsive / down')
                    verified_matches = "no results"
                    is_info['foundc']['status'] = False
                    done = True
                else:
                    sfs = search_filer.search_check()
                    verified_matches = sfs.checker(bb, is_info)
                is_info['foundc']['lastrun'] = time.time()
                logger.fdebug('setting lastrun for %s to %s' % (is_info['foundc']['provider'], time.ctime(is_info['foundc']['lastrun'])))
                last_run_check(write={str(nzbprov): {'active': provider_stat['active'], 'lastrun': is_info['foundc']['lastrun'], 'type': provider_stat['type'], 'hits': provider_stat['hits']+1, 'id': provider_stat['id']}})

        if verified_matches != "no results":
            verification(verified_matches, is_info)

        logger.fdebug(
            'booktype:%s / chktpb: %s / findloop: %s' % (is_info['booktype'], is_info['chktpb'], findloop)
        )
        if any(
               [
                   is_info['booktype'] == 'TPB',
                   is_info['booktype'] == 'GN',
                   is_info['booktype'] == 'HC',
               ]
            ) and is_info['chktpb'] == 1 and findloop + 1 > findcount:
            pass  # findloop=-1
        else:
            findloop += 1

    return is_info['foundc']

def verification(verified_matches, is_info):
    #mylar.COMICINFO = hold_the_matches = verified_matches
    done = False
    verified_index = 0
    if verified_matches != "no results":
        for verified in verified_matches:
            # we need to make sure we index the correct match
            #logger.fdebug('verified: %s' % (verified,))
            if verified['downloadit']:
                try:
                    if verified['chkit']:
                        helpers.checkthe_id(ComicID, verified['chkit'])
                except Exception:
                    pass
                # generate nzbname
                nzbname = nzbname_create(
                    is_info['nzbprov'], info=verified_matches, title=verified['ComicTitle']
                )
                if nzbname is None:
                    logger.error(
                        '[NZBPROVIDER = NONE] Encountered an error using given '
                        'provider with requested information: %s. You have a blank '
                        'entry most likely in your newznabs, fix it & restart Mylar'
                        % verified
                    )
                    verified_index +=1
                    continue
                # generate the send-to and actually send the nzb / torrent.
                try:
                    links = {'id': verified['entry']['id'], 'link': verified['entry']['link']}
                except Exception:
                    links = verified['entry']['link']
                searchresult = searcher(
                    verified['nzbprov'],
                    nzbname,
                    verified_matches,
                    links,
                    verified['IssueID'],
                    verified['ComicID'],
                    verified['tmpprov'],
                    newznab=verified['newznab'],
                    torznab=verified['torznab'],
                    rss=is_info['RSS'],
                    provider_stat=verified['provider_stat']
                )

                if any(
                    [
                        searchresult == 'downloadchk-fail',
                        searchresult == 'double-pp',
                    ]
                ):
                    is_info['foundc']['status'] = False
                    verified_index +=1
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
                    is_info['foundc']['status'] = False
                    verified_index +=1
                    return is_info

                # nzbid, nzbname, sent_to
                nzbid = searchresult['nzbid']
                nzbname = searchresult['nzbname']
                sent_to = searchresult['sent_to']
                alt_nzbname = searchresult['alt_nzbname']
                if searchresult['SARC'] is not None:
                    SARC = searchresult['SARC']
                is_info['foundc']['info'] = searchresult
                is_info['foundc']['status'] = True
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

    #logger.fdebug(
    #    'booktype:%s / chktpb: %s / findloop: %s' % (is_info['booktype'], is_info['chktpb'], is_info['findloop'])
    #)
    #if any(
    #       [
    #           is_info['booktype'] == 'TPB',
    #           is_info['booktype'] == 'GN',
    #           is_info['booktype'] == 'HC',
    #       ]
    #    ) and is_info['chktpb'] == 1 and findloop + 1 > findcount:
    #    pass  # findloop=-1
    #else:
    #    findloop += 1

    if is_info['foundc']['status'] is True:
        #foundcomic.append("yes")
        #logger.fdebug('mylar.COMICINFO: %s' % verified_matches)
        #logger.fdebug('verified_index: %s' % verified_index)
        #logger.fdebug('isinfo: %s' % is_info)
        if verified_matches[verified_index]['pack'] is True:
            try:
                issinfo = verified_matches[verified_index]['pack_issuelist']
            except Exception:
                issinfo = verified_matches['pack_issuelist']
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
                        is_info['ComicName'],
                        SARC=is_info['SARC'],
                        IssueArcID=is_info['IssueArcID'],
                        id=verified_matches[verified_index]['nzbid'],
                        prov=is_info['nzbprov'],
                        oneoff=is_info['oneoff'],
                    )
                    updater.foundsearch(
                        is_info['ComicID'], isid['issueid'], mode=is_info['smode'], provider=is_info['nzbprov']
                    )
                notify_snatch(
                    sent_to,
                    verified_matches[verified_index]['entry']['series'], #is_info['ComicName'],
                    verified_matches[verified_index]['entry']['year'], #is_info['ComicYear'],
                    verified_matches[verified_index]['pack_numbers'],
                    verified_matches[verified_index]['nzbprov'],
                    True,
                )
            else:
                notify_snatch(
                    sent_to,
                    is_info['ComicName'],
                    is_info['ComicYear'],
                    None,
                    is_info['nzbprov'],
                    True,
                )

        else:
            tmpprov = is_info['nzbprov']
            if alt_nzbname is None or alt_nzbname == '':
                logger.fdebug(
                    'Found matching comic...preparing to send to Updater with IssueID:'
                    ' %s and nzbname: %s' % (is_info['IssueID'], nzbname)
                )
                if '[RSS]' in tmpprov:
                    tmpprov = re.sub(r'\[RSS\]', '', tmpprov).strip()
                updater.nzblog(
                    is_info['IssueID'],
                    nzbname,
                    is_info['ComicName'],
                    SARC=is_info['SARC'],
                    IssueArcID=is_info['IssueArcID'],
                    id=verified_matches[verified_index]['nzbid'],
                    prov=tmpprov,
                    oneoff=is_info['oneoff'],
                )
            else:
                logger.fdebug(
                    'Found matching comic...preparing to send to Updater with IssueID:'
                    ' %s and nzbname: %s [%s]' % (is_info['IssueID'], nzbname, alt_nzbname)
                )
                if '[RSS]' in tmpprov:
                    tmpprov = re.sub(r'\[RSS\]', '', tmpprov).strip()
                updater.nzblog(
                    is_info['IssueID'],
                    nzbname,
                    is_info['ComicName'],
                    SARC=is_info['SARC'],
                    IssueArcID=is_info['IssueArcID'],
                    id=verified_matches[verified_index]['nzbid'],
                    prov=tmpprov,
                    alt_nzbname=alt_nzbname,
                    oneoff=is_info['oneoff'],
                )
            updater.foundsearch(
                is_info['ComicID'],
                is_info['IssueID'],
                mode=is_info['smode'], #'series',
                provider=tmpprov,
                SARC=is_info['SARC'],
                IssueArcID=is_info['IssueArcID']
            )

            # send out the notifications for the snatch.
            if any([is_info['oneoff'] is True, is_info['IssueID'] is None]):
                cyear = is_info['ComicYear']
            else:
                cyear = verified_matches[verified_index]['comyear']
            notify_snatch(sent_to, is_info['ComicName'], cyear, is_info['IssueNumber'], tmpprov, False)

        #prov_count == 0
        #return is_info

    #else:
    #    foundcomic.append("no")
        # if IssDateFix == "no":
        #     logger.info('Could not find Issue ' + str(IssueNumber) + ' of '
        #     + ComicName + '(' + str(comyear) + ') using ' + str(tmpprov) '
        #     + '. Status kept as wanted.' )
        #     break
    return is_info #foundc


def searchforissue(issueid=None, new=False, rsschecker=None, manual=False):
    if rsschecker == 'yes':
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
       (mylar.CONFIG.ENABLE_DDL is True
       and any(
            [
                mylar.CONFIG.ENABLE_GETCOMICS is True,
                mylar.CONFIG.ENABLE_EXTERNAL_SERVER is True,
            ]
       ))
       or mylar.CONFIG.ENABLE_AIRDCPP is True
       or any(
            [
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
        if not issueid or rsschecker:

            if rsschecker:
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
            search_skip = {}

            if mylar.CONFIG.ANNUALS_ON:
                stloop += 1
            while stloop > 0:
                if stloop == 1:
                    if (
                        mylar.CONFIG.FAILED_DOWNLOAD_HANDLING
                        and mylar.CONFIG.FAILED_AUTO
                    ):
                        issues_1 = myDB.select(
                            "SELECT * from issues WHERE Status='Wanted' OR"
                            " Status='Failed'"
                        )
                    else:
                        issues_1 = myDB.select(
                            "SELECT * from issues WHERE Status='Wanted'"
                        )
                    for iss in issues_1:
                        checkit = searchforissue_checker(
                            iss['IssueID'],
                            iss['ReleaseDate'],
                            iss['IssueDate'],
                            iss['DigitalDate'],
                            {'ComicName': iss['ComicName'],
                             'Issue_Number': iss['Issue_Number'],
                             'ComicID': iss['ComicID']
                            }
                        )
                        if checkit['status'] is True:
                            if not any(r['IssueID'] == iss['IssueID'] for r in results):

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
                        else:
                            issueline = iss['Issue_Number']
                            schk = False
                            for s in search_skip:
                                if s == iss['ComicID']:
                                    search_skip[iss['ComicID']].update({'issue': iss['Issue_Number'], 'reason': checkit['reason']})
                                    schk = True
                                    break
                            if schk is False:
                                search_skip[iss['ComicID']] = {'Issue_Number': [iss['Issue_Number']],
                                                               'ComicName': iss['ComicName']}

                elif stloop == 2:
                    if mylar.CONFIG.SEARCH_STORYARCS is True or rsschecker:
                        if (
                            mylar.CONFIG.FAILED_DOWNLOAD_HANDLING
                            and mylar.CONFIG.FAILED_AUTO
                        ):
                            issues_2 = myDB.select(
                                "SELECT * from storyarcs WHERE Status='Wanted' OR" 
                                " Status='Failed'"
                            )
                        else:
                            issues_2 = myDB.select(
                                "SELECT * from storyarcs WHERE Status='Wanted'"
                            )
                        cnt = 0
                        for iss in issues_2:
                            checkit = searchforissue_checker(
                                iss['IssueID'],
                                iss['ReleaseDate'],
                                iss['IssueDate'],
                                iss['DigitalDate'],
                                {'ComicName': iss['ComicName'],
                                 'Issue_Number': iss['IssueNumber'],
                                 'ComicID': iss['ComicID']
                                }
                            )
                            if checkit['status'] is True:
                                if not any(r['IssueID'] == iss['IssueID'] for r in results):
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
                            else:
                                issueline = iss['IssueNumber']
                                schk = False
                                for s in search_skip:
                                    if s == iss['ComicID']:
                                        search_skip[iss['ComicID']].update({'issue': iss['IssueNumber'], 'reason': checkit['reason']})
                                        schk = True
                                        break
                                if schk is False:
                                    search_skip[iss['ComicID']] = {'Issue_Number': [iss['IssueNumber']],
                                                                   'ComicName': iss['ComicName']}

                        logger.info('Issues that belong to part of a Story Arc to be searched for : %s' % cnt)
                elif stloop == 3:
                    if (
                        mylar.CONFIG.FAILED_DOWNLOAD_HANDLING
                        and mylar.CONFIG.FAILED_AUTO
                    ):
                        issues_3 = myDB.select(
                            "SELECT * from annuals WHERE Status IN ('Wanted', 'Failed') AND NOT Deleted"
                        )
                    else:
                        issues_3 = myDB.select(
                            "SELECT * from annuals WHERE Status='Wanted' AND NOT Deleted"
                        )
                    for iss in issues_3:
                        checkit = searchforissue_checker(
                            iss['IssueID'],
                            iss['ReleaseDate'],
                            iss['IssueDate'],
                            iss['DigitalDate'],
                            {'ComicName': iss['ComicName'],
                             'Issue_Number': iss['Issue_Number'],
                             'ComicID': iss['ComicID']
                            }
                        )
                        if checkit['status'] is True:
                            if not any(r['IssueID'] == iss['IssueID'] for r in results):
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
                        else:
                            issueline = iss['Issue_Number']
                            schk = False
                            for s in search_skip:
                                if s == iss['ComicID']:
                                    search_skip[iss['ComicID']].update({'issue': iss['Issue_Number'], 'reason': checkit['reason']})
                                    schk = True
                                    break
                            if schk is False:
                                search_skip[iss['ComicID']] = {'Issue_Number': [iss['Issue_Number']],
                                                               'ComicName': iss['ComicName']}

                stloop -= 1

            # to-do: re-order the results list so it's most recent to least recent.
            rss_queue = []
            if len(search_skip) > 0:
                logger.info(
                    'The following series have been skipped due to either being'
                    ' already in a Downloaded/Snatched status or having Invalid'
                    ' Date-data in the database: %s' % (search_skip)
                )

            for result in sorted(results, key=itemgetter('StoreDate'), reverse=True):

                try:
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

                    if rsschecker is None and DateAdded >= mylar.SEARCH_TIER_DATE:
                        logger.fdebug(
                            '[TIER1] Adding: %s #%s [ComicID:%s / IssueiD: %s][ %s >= %s]'
                            % (comicname, result['Issue_Number'], result['ComicID'], result['IssueID'], DateAdded, mylar.SEARCH_TIER_DATE)
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
                    elif rsschecker:
                        if not [x for x in rss_queue if result['IssueID'] == x[8]]: #comic['ComicName'] == x[0]]: #result['ComicID'] == x[15]]: #co$
                            #remove - or : from the series titles and replace with an sqlite wildcard operator.
                            sqlquery_name = re.sub('[\:\-]', '%', comic['ComicName']).strip()
                            rss_queue.append((comic['ComicName'], sqlquery_name, result['Issue_Number'], ComicYear, SeriesYear, Publisher, IssueDate, StoreDate, result['IssueID'], AlternateSearch, UseFuzzy, ComicVersion, result['SARC'], result['IssueArcID'], result['mode'], rsschecker, result['ComicID'], Comicname_filesafe, AllowPacks, OneOff, TorrentID_32p, DigitalDate, booktype, ignore_booktype))
                    else:
                        logger.fdebug('[TIER2] %s #%s [%s < %s]' % (comicname, result['Issue_Number'], DateAdded, mylar.SEARCH_TIER_DATE))
                        continue
                    # - removed below - if uncommented will ignore the Tier searches
                    #else:
                    #    smode = result['mode']
                    #    foundNZB, prov = search_init(
                    #        comicname,
                    #        result['Issue_Number'],
                    #        str(ComicYear),
                    #        SeriesYear,
                    #        Publisher,
                    #        IssueDate,
                    #        StoreDate,
                    #        result['IssueID'],
                    #        AlternateSearch,
                    #        UseFuzzy,
                    #        ComicVersion,
                    #        SARC=result['SARC'],
                    #        IssueArcID=result['IssueArcID'],
                    #        smode=smode,
                    #        rsschecker=rsschecker,
                    #        ComicID=result['ComicID'],
                    #        filesafe=Comicname_filesafe,
                    #        allow_packs=AllowPacks,
                    #        oneoff=OneOff,
                    #        torrentid_32p=TorrentID_32p,
                    #        digitaldate=DigitalDate,
                    #        booktype=booktype,
                    #        ignore_booktype=ignore_booktype,
                    #    )
                    #    if foundNZB['status'] is True:
                    #        updater.foundsearch(
                    #            result['ComicID'],
                    #            result['IssueID'],
                    #            mode=smode,
                    #            provider=prov,
                    #            SARC=result['SARC'],
                    #            IssueArcID=result['IssueArcID'],
                    #            hash=foundNZB['info']['t_hash'],
                    #        )

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

            if rsschecker:
                provider_list = provider_order()
                if all(
                    [
                        mylar.CONFIG.ENABLE_TORRENTS is True,
                        mylar.CONFIG.ENABLE_TORRENT_SEARCH is True
                    ]
                ) or (
                    any(
                        [
                            mylar.CONFIG.EXPERIMENTAL is True,
                            mylar.CONFIG.ENABLE_GETCOMICS is True,
                            mylar.CONFIG.ENABLE_EXTERNAL_SERVER is True,
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
                    or all([mylar.CONFIG.ENABLE_AIRDCPP is True, len(mylar.CONFIG.AIRDCPP_ANNOUNCE_HUB) > 0])
                    or all([mylar.CONFIG.TORZNAB is True, len(ens) > 0])
                    and any(
                        [
                            mylar.CONFIG.ENABLE_TORRENTS is True,
                            mylar.CONFIG.ENABLE_TORRENT_SEARCH is True
                        ]
                    )
                ):
                    results = mylar.rsscheck.nzbdbsearch(None, None, rsslist=rss_queue, provider_list=provider_list)
                    # TODO is there ever a situation where we should be here without continuing at this level of indent?  Certainly not with an 'entries' key in results.  Refactor later.

                # Split the results by IssueID to then break on the first successful snatch
                unique_issue_ids = set([x['info']['IssueID'] for x in results['entries']])
                for unique_issue_id in unique_issue_ids:
                    issue_results = [r for r in results['entries'] if r['info']['IssueID'] == unique_issue_id]
                    logger.debug(f'Attempting RSS downloads for Issue ID {unique_issue_id}')

                    for x in issue_results:
                        # need to do this to make sure we care across the expected data format
                        rs = {}
                        rs['entries'] = [{'title': x['title'],
                                        'link': x['link'],
                                        'pubdate': x['pubdate'],
                                        'site': x['site'],
                                        'length': x['length']}]

                        logger.info('rss_results[x]: %s' % (x,))
                        try:
                            foundc = {}
                            foundc['status'] = False
                            foundc['provider'] = x['site']

                            xr = x['info']
                            # set these here so that it can log exceptions properly
                            comicname = xr['ComicName']
                            issue_number = xr['Issue_Number']
                            seriesyear = xr['SeriesYear']
                            comicid = xr['ComicID']
                            issueid = xr['IssueID']
                            booktype = xr['booktype']
                            searchmode = xr['searchmode']

                            current_prov = last_run_check(check=True, provider=x['site'])
                            logger.info('current_prov: %s' % (current_prov,))
                            if len(current_prov) > 0:
                                nzbprov = list(current_prov.keys())[0]
                                provider_stat = current_prov.get(list(current_prov.keys())[0])
                            else:
                                nzbprov = x['site']
                            foundc['lastrun'] = provider_stat['lastrun']
                            logger.info('nzbprov: %s' % nzbprov)
                            logger.info('provider_stat: %s' % (provider_stat,))

                            newznab_info = None
                            torznab_info = None
                            if provider_stat['type'] == 'newznab':
                                if provider_list['newznab_info']:
                                    pni = provider_list['newznab_info']
                                    for pl in pni:
                                        if pl['info'][0] == nzbprov:
                                            logger.info('newznab match: %s' % nzbprov)
                                            newznab_info = pl['info']
                                            break

                            elif provider_stat['type'] == 'torznab':
                                if provider_list['torznab_info']:
                                    pni = provider_list['torznab_info']
                                    for pl in pni:
                                        if pl['info'][0] == nzbprov:
                                            logger.info('torznab match: %s' % nzbprov)
                                            torznab_info = pl['info']
                                            break

                            #fix for issue dates between Nov-Dec/(Jan-Feb-Mar)
                            IssDateFix = "no"
                            if xr['IssueDate'] is not None:
                                IssDt = xr['IssueDate'][5:7]
                                if any([IssDt == "12", IssDt == "11", IssDt == "01", IssDt == "02", IssDt == "03"]):
                                    IssDateFix = IssDt

                            else:
                                if xr['StoreDate'] is not None:
                                    StDt = xr['StoreDate'][5:7]
                                    if any([StDt == "10", StDt == "12", StDt == "11", StDt == "01", StDt == "02", StDt == "03"]):
                                        IssDateFix = StDt

                            chktpb = 0
                            if any([booktype == 'TPB', booktype =='HC', booktype == 'GN']):
                                chktpb = 1

                            logger.info('provider_list: %s' % (provider_list,))

                            intIss = helpers.issue_number_parser(xr['Issue_Number']).asInt

                            findcomiciss, c_number = get_findcomiciss(xr['Issue_Number'])

                            if '0-Day' in comicname:
                                cmloopit = 1
                            else:
                                cmloopit = None
                                if any([booktype == 'One-Shot', 'annual' in comicname.lower()]):
                                    cmloopit = 4
                                    if 'annual' in comicname.lower():
                                        if xr['Issue_Number'] is not None:
                                            if helpers.issue_number_parser(xr['Issue_Number']).asInt != helpers.issue_number_to_int(1,None):
                                                cmloopit = None
                                if cmloopit is None:
                                    if len(c_number) == 1:
                                        cmloopit = 3
                                    elif len(c_number) == 2:
                                        cmloopit = 2
                                    else:
                                        cmloopit = 1

                            is_info = {'ComicName': xr['ComicName'],
                                       'nzbprov': nzbprov,
                                       'RSS': xr['RSS'],
                                       'UseFuzzy': xr['UseFuzzy'],
                                       'StoreDate': xr['StoreDate'],
                                       'IssueDate': xr['IssueDate'],
                                       'digitaldate': xr['DigitalDate'],
                                       'booktype': xr['booktype'],
                                       'ignore_booktype': xr['ignore_booktype'],
                                       'SeriesYear': xr['SeriesYear'],
                                       'ComicVersion': xr['ComicVersion'],
                                       'IssDateFix': IssDateFix,
                                       'ComicYear': xr['ComicYear'],
                                       'IssueID': xr['IssueID'],
                                       'ComicID': xr['ComicID'],
                                       'IssueNumber': xr['Issue_Number'],
                                       'manual': False,  # not a manual search.
                                       'newznab_host': newznab_info,
                                       'torznab_host': torznab_info,
                                       'oneoff': xr['OneOff'],
                                       'tmpprov': nzbprov,
                                       'SARC': xr['SARC'],
                                       'IssueArcID': xr['IssueArcID'],
                                       'cmloopit': cmloopit,
                                       'findcomiciss': findcomiciss,
                                       'intIss': intIss,
                                       'chktpb': chktpb,
                                       'smode': xr['searchmode'],
                                       'provider_stat': provider_stat,
                                       'foundc': foundc}


                            ##if not any(x['site'] in olist for olist in provider_list['prov_order']) or helpers.block_provider_check(x['site']):
                            ##    continue
                            #torznab_info = None
                            #newznab_info = None
                            #nzbprov = x['site']
                            #for xx in provider_list['prov_order']:
                            #    if x['site'] in xx:
                            #        if provider_list['torznab_info'] is not None:
                            #            for tn in provider_list['torznab_info']:

                            #                if x['site'].lower() == tn['provider'].lower():
                            #                    nzbprov = 'torznab'
                            #                    torznab_info = tn['info']
                            #                    break
                            #        if provider_list['newznab_info'] is not None and torznab_info is None:
                            #            for nn in provider_list['newznab_info']:
                            #                logger.fdebug('[site:%s] nn: %s' % (x['site'], nn))
                            #                if x['site'].lower() == nn['info'][0].lower():
                            #                    nzbprov = 'newznab'
                            #                    newznab_info = nn['info']
                            #                    logger.fdebug('site match hit on: %s' % x['site'])
                            #                    break
                            #    if any([torznab_info is not None, newznab_info is not None]):
                            #        break

                            # might need to put.queue this...
                            logger.info('looking for : %s %s (%s) [oneoff: %s][ignore_booktype: %s]' % (xr['ComicName'], xr['Issue_Number'], xr['StoreDate'], xr['OneOff'], xr['ignore_booktype']))
                            rs = {}

                            # if it's DDL - we need to parse out things
                            #if nzbprov == 'DDL(GetComics)':
                            #    ddlset = []
                            #    for xx in getcomics.search_results['entries']:
                            #        bb = next((item for item in ddlset if item['link'] == xx['link']), None)
                            #        try:
                            #            if 'Weekly' not in xr['ComicName'] and 'Weekly' in xx['title']:
                            #                continue
                            #            elif bb is None:
                            #                ddlset.append(xx)
                            #        except Exception as e:
                            #            ddlset.append(xx)
                            #        else:
                            #            continue
                            #    rs['entries'] = ddlset
                            #else:
                            # need to do this to make sure we care across the expected data format
                            entries = [{'title': x['title'],
                                        'link': x['link'],
                                        'pubdate': x['pubdate'],
                                        'site': x['site'],
                                        'length': x['length'],
                                        'pack': x['pack'],
                                        'issues': x['issues']}]

                            sfs = search_filer.search_check()
                            verified_matches = sfs.checker(entries, is_info)
                            logger.info('verified_matches_returned: %s' % (verified_matches,))
                            if len(verified_matches) > 0:
                                response = verification(verified_matches, is_info)
                                logger.info('response: %s' % (response,))
                                if all([response, 'foundc' in response.keys(), 'status' in response['foundc'].keys()]):
                                    if response['foundc']['status'] is True:
                                        break
                                #foundNZB = imsearch(bb={'entries': [{'title': x['title'], 'link': x['link'], 'pubdate': x['pubdate'], 'site': x['site'], 'length': x['length']}]}, nzbprov=nzbprov, newznab_host=newznab_info, torznab_host=torznab_info, ComicName=xr['ComicName'], Issue_Number=xr['Issue_Number'], ComicYear=xr['ComicYear'], SeriesYear=xr['SeriesYear'], Publisher=xr['Publisher'], IssueDate=xr['IssueDate'], StoreDate=xr['StoreDate'], IssueID=xr['IssueID'], AlternateSearch=xr['AlternateSearch'], ComicVersion=xr['ComicVersion'], UseFuzzy=xr['UseFuzzy'], SARC=xr['SARC'], IssDateFix=IssDateFix, IssueArcID=xr['IssueArcID'], searchmode=xr['searchmode'], RSS=xr['RSS'], ComicID=xr['ComicID'], filesafe=xr['ComicName_Filesafe'], allow_packs=xr['AllowPacks'], oneoff=xr['OneOff'], torrentid_32p=xr['TorrentID_32P'], digitaldate=xr['DigitalDate'], booktype=xr['booktype'], manual=False, ignore_booktype=xr['ignore_booktype'])
                                #logger.info('foundnzb result: %s' % (foundNZB,))

                        except Exception as err:
                            exc_type, exc_value, exc_tb = sys.exc_info()
                            filename, line_num, func_name, err_text = traceback.extract_tb(
                                exc_tb
                            )[-1]
                            tracebackline = traceback.format_exc()

                            except_line = {
                                'exc_value': exc_value,
                                'exc_tb': exc_tb,
                                'filename': filename,
                                'line_num': line_num,
                                'func_name': func_name,
                                'err': str(err),
                                'err_text': err_text,
                                'traceback': tracebackline,
                                'comicname': comicname,
                                'issuenumber': issue_number,
                                'seriesyear': seriesyear,
                                'issueid': issueid,
                                'comicid': comicid,
                                'mode': searchmode,
                                'booktype': booktype,
                            }

                            helpers.log_that_exception(except_line)

                            # log it regardless..
                            logger.exception(tracebackline)
                            continue

                logger.info('Completed RSS Search scan')
                if mylar.SEARCHLOCK is True:
                    mylar.SEARCHLOCK = False
            else:
                logger.info('Completed Queueing API Search scan')
                if mylar.SEARCHLOCK is True:
                    mylar.SEARCHLOCK = False
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

                #if it's not manually initiated, make sure it's not already downloaded/snatched.
                if not manual:
                    if smode == 'story_arc':
                        issnumb = result['IssueNumber']
                    else:
                        issnumb = result['Issue_Number']
                    checkit = searchforissue_checker(
                                result['IssueID'],
                                result['ReleaseDate'],
                                result['IssueDate'],
                                result['DigitalDate'],
                                {'ComicName': result['ComicName'],
                                 'Issue_Number': issnumb,
                                 'ComicID': result['ComicID']
                                }
                              )
                    if checkit['status'] is False:
                        logger.fdebug(
                              'Issue is already in a Downloaded / Snatched status. If this is'
                              ' still wanted, perform a Manual search or mark issue as Skipped'
                              ' or Wanted.'
                        )
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

                if all([IssueDate == '0000-00-00', StoreDate == '0000-00-00']):
                    IssueYear = SeriesYear
                else:
                    if StoreDate == '0000-00-00':
                        if IssueDate != '0000-00-00':
                            IssueYear = str(IssueDate)[:4]
                        else:
                            logger.fdebug('No valid date found for %s issue %s - defaulting to series year.'
                                          'You may want to edit the date to correct this.'
                                          % (ComicName, IssueNumber)
                            )
                            IssueYear = SeriesYear
                    else:
                        IssueYear = str(StoreDate)[:4]

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
                    rsschecker=rsschecker,
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
                    #updater.foundsearch(
                    #    ComicID,
                    #    actissueid,
                    #    mode=smode,
                    #    provider=prov,
                    #    SARC=SARC,
                    #    IssueArcID=IssueArcID,
                    #    hash=foundNZB['info']['t_hash'],
                    #)
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
                    'comicname': result['ComicName'],
                    'issuenumber': result['Issue_Number'],
                    #'seriesyear': SeriesYear,
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
        if rsschecker:
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
       (mylar.CONFIG.ENABLE_DDL is True
       and any(
            [
                mylar.CONFIG.ENABLE_GETCOMICS is True,
                mylar.CONFIG.ENABLE_EXTERNAL_SERVER is True,
            ]
        )
        ) or mylar.CONFIG.ENABLE_AIRDCPP is True
        or any(
            [
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
        [provider == '32P', provider == 'WWT', provider == 'DEM', 'DDL' in provider]
    ):
        # filesafe the name cause people are idiots when they post sometimes.
        nzbname = re.sub(r'\s{2,}', ' ', helpers.filesafe(title)).strip()
        # let's change all space to decimals for simplicity
        nzbname = re.sub(" ", ".", nzbname)
        # gotta replace & or escape it
        nzbname = re.sub(r'\&amp;|(amp;)|amp;|\&', 'and', title)
        nzbname = re.sub(r'[\,\:\?\']', '', nzbname)
        if nzbname.lower().endswith('.torrent'):
            nzbname = re.sub('.torrent', '', nzbname)
    elif provider == 'airdcpp':
        nzbname = re.sub(r'\s{2,}', ' ', helpers.filesafe(title)).strip()
        nzbname = re.sub(" ", ".", nzbname)
        nzbname = re.sub(r'\&amp;|(amp;)|amp;|\&', 'and', title)
        nzbname = re.sub(r'[\,\:\?\']', '', nzbname)
        # DO NOT strip the extension for AirDC++
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
    provider_stat=None
):
    alt_nzbname = None
    # load in the details of the issue from the tuple.
    ComicName = comicinfo[0]['ComicName']
    IssueNumber = comicinfo[0]['IssueNumber']
    comyear = comicinfo[0]['comyear']
    oneoff = comicinfo[0]['oneoff']
    nzbid = comicinfo[0]['nzbid']
    if type(link) != str:
        link = link['link']
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

    logger.info('[nzbprov:%s] provider_stat:%s' % (nzbprov,provider_stat,))

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
                provider_stat['type'] != 'torznab',
                'DDL' not in nzbprov,
                nzbprov != 'AirDCPP',
                nzbprov != 'airdcpp',
            ]
    ):

        # generate nzbid here.
        logger.info('nzbprov: %s' % nzbprov)
        logger.info('provider_stat: %s' % (provider_stat,))
        nzo_info = {}
        filen = None
        nzbhydra = False
        payload = None
        headers = {'User-Agent': str(mylar.USER_AGENT)}
        # link doesn't have the apikey - add it and use ?t=get for newznab based.
        if provider_stat['type'] == 'newznab':
            # need to basename the link so it just has the id/hash.
            # rss doesn't store apikey, have to put it back.
            if provider_stat['type'] == 'newznab':
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
                if 'filename*=UTF-8' in filen:
                    filen = filen[:filen.find('filename*=UTF-8')].strip()
                if filen.endswith('";'):
                    filen = re.sub(r'\"\;', '', filen).strip()
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
    if mylar.CONFIG.ENABLE_DDL is True and 'DDL' in nzbprov:
        if all([IssueID is None, IssueArcID is not None]):
            tmp_issueid = IssueArcID
        else:
            tmp_issueid = IssueID

        # we need to pass in if it's a pack and what issues are present therein
        pack_info = {'pack': comicinfo[0]['pack'],
                     'pack_numbers': comicinfo[0]['pack_numbers'],
                     'pack_issuelist': comicinfo[0]['pack_issuelist']}

        if nzbprov == 'DDL(GetComics)':
            #GC requires an extra step - do it now.
            ggc = getcomics.GC(issueid=tmp_issueid, comicid=ComicID)
            ggc.loadsite(nzbid, link)
            ddl_it = ggc.parse_downloadresults(nzbid, link, comicinfo, pack_info)
            tnzbprov = nzbprov
            if ddl_it['success'] is True:
                logger.info(
                    '[%s] Successfully snatched %s from DDL site. It is currently being queued'
                    ' to download in position %s' % (tnzbprov, nzbname, mylar.DDL_QUEUE.qsize())
                )
            else:
                logger.info('[%s] Failed to retrieve %s from the DDL site.' % (tnzbprov, nzbname))
                return "ddl-fail"
        else:
            cinfo = {'id': nzbid,
                     'series': comicinfo[0]['ComicName'],
                     'year': comicinfo[0]['comyear'],
                     'size': comicinfo[0]['size'],
                     'issues': comicinfo[0]['IssueNumber'],
                     'issueid': comicinfo[0]['IssueID'],
                     'comicid': comicinfo[0]['ComicID'],
                     'filename': comicinfo[0]['nzbtitle'],
                     'oneoff': comicinfo[0]['oneoff'],
                     'link': link,
                     'site': nzbprov}

            meganz = exs.MegaNZ(provider_stat=provider_stat)
            ddl_it = meganz.queue_the_download(cinfo, comicinfo, pack_info)
            tnzbprov = 'DDL(External)'

            if ddl_it['success'] is True:
                logger.info(
                    '[%s] Successfully snatched %s from External-DDL site. It is currently being queued'
                    ' to download in position %s' % (tnzbprov, nzbname, mylar.DDL_QUEUE.qsize())
                )
            else:
                logger.info('[%s] Failed to retrieve %s from the External-DDL site.' % (tnzbprov, nzbname))
                return "ddl-fail"

        sent_to = "is downloading it directly via %s" % tnzbprov

    elif mylar.CONFIG.ENABLE_AIRDCPP and nzbprov.lower() == 'airdcpp':
        if all([IssueID is None, IssueArcID is not None]):
            tmp_issueid = IssueArcID
        else:
            tmp_issueid = IssueID

        filename = nzbname

        airdcpp_downloader = airdcpp.AirDCPP(
            issueid=tmp_issueid,
            comicid=ComicID,
            provider_stat=provider_stat
        )

        search_instance_id = None
        if isinstance(comicinfo, list) and len(comicinfo) > 0:
            if isinstance(comicinfo[0], dict) and 'search_instance_id' in comicinfo[0]:
                search_instance_id = comicinfo[0]['search_instance_id']

        # Check if this is a TTH hash from RSS (no search instance)
        is_valid_tth = bool(re.match(r'^[A-Z2-7]{39}$', link))
        if search_instance_id is None and is_valid_tth:
            # RSS download - we have a TTH hash but no search instance
            logger.info('[AirDCPP] RSS download detected - using TTH: %s' % link)
            download_result = airdcpp_downloader.rss_download(
                tth_hash=link,
                filename=filename,
                issueid=tmp_issueid
            )
        else:
            # Normal download - we have a search instance from regular search
            logger.info('[AirDCPP] Normal download with search instance: %s' % search_instance_id)
            download_result = airdcpp_downloader.download(
                link=link,
                filename=filename,
                id=nzbid,
                issueid=tmp_issueid,
                site='AirDCPP',
                search_instance_id=search_instance_id
            )

        tnzbprov = 'AirDCPP'

        if download_result['success'] is True:
            logger.info(
                '[%s] Successfully downloaded %s from AirDC++. Downloaded to: %s'
                % (tnzbprov, filename, download_result['path'])
            )

            if mylar.CONFIG.POST_PROCESSING is True:
                mylar.PP_QUEUE.put({'nzb_name': download_result['filename'],
                                    'nzb_folder': os.path.dirname(download_result['path']),
                                    'issueid': tmp_issueid,
                                    'comicid': ComicID,
                                    'failed': False,
                                    'apicall': True,
                                    'ddl': False})
                logger.info('[%s] Added %s to post-processing queue.' % (tnzbprov, filename))
                updater.nzblog(
                    tmp_issueid,
                    filename,
                    ComicName,
                    SARC=SARC,
                    IssueArcID=IssueArcID,
                    id=nzbid,
                    prov=tnzbprov,
                    oneoff=oneoff
                )
        else:
            logger.info('[%s] Failed to download %s from AirDC++.' % (tnzbprov, filename))
            return "ddl-fail"

        sent_to = "is downloading it directly via %s" % tnzbprov

    elif mylar.USE_BLACKHOLE and all(
        [nzbprov != '32P', nzbprov != 'WWT', nzbprov != 'DEM', provider_stat['type'] != 'torznab']
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
        [nzbprov == '32P', nzbprov == 'WWT', nzbprov == 'DEM', provider_stat['type'] == 'torznab']
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

            mylar_host = helpers.where_am_i()

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
        return return_val


def notify_snatch(sent_to, comicname, comyear, IssueNumber, nzbprov, pack):
    # pack = {"pack": True, "issues": '#1 - 60', "years": "(1997-2002"}
    #logger.fdebug('sent_to: %s' % sent_to)
    #logger.fdebug('pack: %s' % pack)
    #logger.fdebug('Issue: %s' % IssueNumber)
    #logger.fdebug('nzbprov: %s' % nzbprov)
    #logger.fdebug('comyear: %s' % comyear)
    #logger.fdebug('comicname: %s' % comicname)

    if pack is False:
        snline = 'Issue snatched!'
        if IssueNumber is not None:
            snatched_name = '%s (%s) #%s' % (comicname, comyear, IssueNumber)
        else:
            snatched_name = '%s (%s)' % (comicname, comyear)
    else:
        snline = 'Pack snatched!'
        snatched_name = '%s %s (%s)' % (comicname, IssueNumber, comyear)

    #logger.fdebug('snatched_name: %s' % snatched_name)

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
    if mylar.CONFIG.GOTIFY_ENABLED and mylar.CONFIG.GOTIFY_ONSNATCH:
        logger.info("Sending Gotify notification")
        gotify = notifiers.GOTIFY()
        gotify.notify(
            "Snatched",
            snline,
            snatched_nzb=snatched_name,
            sent_to=sent_to,
            prov=nzbprov,
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

def generate_id(nzbprov, link, comicname):
    #logger.fdebug('[type:%s][%s] generate_id - link: %s' % (type(nzbprov), nzbprov, link))
    if type(nzbprov) != str:
        # provider_stat is being passed in - use the type field to get the basics.
        nzbprov = nzbprov['type']
        logger.fdebug('nzbprov setting to : %s' % nzbprov)
    if nzbprov == 'experimental':
        # id is located after the /download/ portion
        url_parts = urlparse(link)
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
            url_parts = urlparse(link)
            path_parts = url_parts[2].rpartition('/')
            nzbtempid = path_parts[2]
            nzbid = re.sub('.torrent', '', nzbtempid).rstrip()
    elif 'newznab' in nzbprov:
        # if in format of http://newznab/getnzb/<id>.nzb&i=1&r=apikey
        tmpid = urlparse(link)[
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
                tmpid = urlparse(link)[2]
                nzbid = tmpid.rsplit('/', 1)[1]
    elif nzbprov == 'torznab':
        idtmp = urlparse(link)[4]
        if idtmp == '':
            idtmp = pathlib.PurePosixPath(unquote(urlparse(link).path))
            for im in idtmp.parts:
                if all(
                    [
                         comicname.lower() not in im.lower(),
                         im != '/',
                         '.cbz' not in im.lower(),
                         '.cbr' not in im.lower(),
                    ]
                ):
                    nzbid = im
                    break
        else:
            idpos = idtmp.find('&')
            nzbid = re.sub('id=', '', idtmp[:idpos]).strip()
    elif nzbprov == 'AirDCPP' or nzbprov == 'airdcpp':
        # For AirDCPP, the link is the ID (TTH hash)
        nzbid = link
    return nzbid

def check_time(last_run):
    rd = datetime.datetime.utcfromtimestamp(last_run)
    rd_now = datetime.datetime.utcfromtimestamp(time.time())
    diff = abs(rd_now - rd).total_seconds()
    return diff

def get_current_prov(providers):
    for k,v in providers.items():
        if v['active'] is True:
            return {k: providers[k]}

    return False

def last_run_check(write=None, check=None, provider=None):
    myDB = db.DBConnection()
    if check is True:
        checkout = myDB.select("SELECT * FROM provider_searches")
        chk = {}
        if checkout:
           if provider is not None:
               if provider == 'Experimental':
                   provider = 'experimental'
               for ck in checkout:
                   if provider == ck['provider']:
                       chk[ck['provider']] = {'type': ck['type'],
                                              'lastrun': ck['lastrun'],
                                              'active': ck['active'],
                                              'hits': ck['hits'],
                                              'id': ck['id']}
                       break
           else:
               for ck in checkout:
                   ck_prov = ck['provider']
                   if ck_prov == 'Experimental':
                       ck_prov = 'experimental'
                   chk[ck_prov] = {'type': ck['type'],
                                   'lastrun': ck['lastrun'],
                                   'active': ck['active'],
                                   'hits': ck['hits'],
                                   'id': ck['id']}
        return chk
    else:
        #logger.fdebug('write: %s' % (write,))
        writekey = list(write.keys())[0]
        if writekey == 'Experimental':
            writekey = 'experimental'
        writevals = write[writekey]
        vals = {'active': writevals['active'], 'lastrun': writevals['lastrun'], 'type': writevals['type'], 'hits': writevals['hits']}
        ctrls = {'provider': writekey, 'id': writevals['id']}
        #logger.fdebug('writing: keys - %s: vals - %s' % (ctrls, vals))
        writeout = myDB.upsert("provider_searches", vals, ctrls)

def check_the_search_delay(manual=False):
    # set a delay between searches here. Default is for 30 seconds...
    # changing this to lower could result in a ban from your nzb source
    # due to hammering.
    if (
        mylar.CONFIG.SEARCH_DELAY == 'None'
        or mylar.CONFIG.SEARCH_DELAY is None
        or manual
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
    return pause_the_search

def search_the_matrix(scarios):
    return NZB_SEARCH(
                scarios['ComicName'],
                scarios['tmp_IssueNumber'],
                scarios['ComicYear'],
                scarios['SeriesYear'],
                scarios['Publisher'],
                scarios['IssueDate'],
                scarios['StoreDate'],
                scarios['current_prov'],
                scarios['send_prov_count'],
                scarios['IssDateFix'],
                scarios['IssueID'],
                scarios['UseFuzzy'],
                scarios['newznab_host'],
                ComicVersion=scarios['ComicVersion'],
                SARC=scarios['SARC'],
                IssueArcID=scarios['IssueArcID'],
                RSS = scarios['RSS'],
                ComicID=scarios['ComicID'],
                issuetitle=scarios['issuetitle'],
                unaltered_ComicName=scarios['unaltered_ComicName'],
                oneoff=scarios['oneoff'],
                cmloopit=scarios['cmloopit'],
                manual=scarios['manual'],
                torznab_host=scarios['torznab_host'],
                digitaldate=scarios['digitaldate'],
                booktype=scarios['booktype'],
                chktpb=scarios['chktpb'],
                ignore_booktype=scarios['ignore_booktype'],
                smode=scarios['smode'],
    )

def gen_altnames(ComicName, AlternateSearch, filesafe, smode):
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

    if smode == 'want_ann':
        logger.info('Annual/Special issue search detected. Appending to issue #')
        # anything for smode other than None indicates an annual.
        #if all(['annual' not in ComicName.lower(), 'special' not in ComicName.lower()]):
        #    ComicName = '%s Annual' % ComicName

        #if '2021 annual' in ComicName.lower():
        #    if any([AlternateSearch is None, AlternateSearch == 'None']):
        #        AlternateSearch = ''
        #    AlternateSearch += '%s Annual' % re.sub('2021 annual', '', ComicName, flags=re.I).strip()
        #    logger.info('Setting alternate search to %s because people are gonna people.' % AlternateSearch)

        if all(
            [
                AlternateSearch is not None,
                AlternateSearch != "None",
                'special' not in ComicName.lower(),
            ]
        ):
            AlternateSearch += '##%s Annual' % AlternateSearch
        elif all(
            [
                AlternateSearch is None,
                AlternateSearch == "None",
                'special' not in ComicName.lower(),
            ]
        ):
            AlternateSearch = '%s Annual' % AlternateSearch

    searchlist = []
    Altname = None
    ignore_previous = False
    logger.info('AlternateSearch: %s' % AlternateSearch)
    if AlternateSearch is not None and AlternateSearch != "None":
        altpriority = AlternateSearch.find('!!')
        logger.info('altpriority: %s' % altpriority)
        if altpriority != -1:
            altsplit = AlternateSearch.find('##', altpriority)
            logger.info('altsplit: %s' % altsplit)
            if altsplit == -1:
                Altname = AlternateSearch[altpriority+2:]
            else:
                Altname = AlternateSearch[altpriority+2:altsplit]
            logger.info('Altname: %s' % Altname)
            if helpers.filesafe(Altname).lower() == helpers.filesafe(ComicName).lower():
                logger.info('Alternate search pattern is an exact match to previous query. Not recreating')
                ignore_previous = True
            else:
                logger.info('Alternate Search Priority enabled. Using %s before %s during queries' % (Altname, ComicName))
                searchlist.append({'ComicName':Altname,
                                   'unaltered_ComicName': Altname})

    if ignore_previous is False:
        searchlist.append({'ComicName':ComicName,
                           'unaltered_ComicName': ComicName})

    if AlternateSearch is not None and AlternateSearch != "None":
        #chkthealt = list(filter(None, re.split("[[\#\#]|[\!\!]]+", AlternateSearch)))
        chkthealt = list(filter(None, re.split("[\!\!]+|[\#\#]+", AlternateSearch)))
        for AS_Alternate in chkthealt:
            if helpers.filesafe(AS_Alternate).lower() == helpers.filesafe(ComicName).lower():
                logger.info('Alternate search pattern is an exact match to previous query. Not recreating')
                continue
            if Altname != AS_Alternate:
                logger.info(
                    'Alternate Search pattern detected...re-adjusting'
                    ' to : %s' % AS_Alternate
                )
                searchlist.append({'ComicName': AS_Alternate,
                                   'unaltered_ComicName': AS_Alternate})

    logger.info('searchlist: %s' % (searchlist,))
    return searchlist

def searchforissue_checker(issueid, storedate, issuedate, digitaldate, info):
    # status issue check - check status to see if it's Downloaded / Snatched
    # already due to concurrent searches possibly.
    if issueid is not None:
        isscheck = helpers.issue_status(issueid)
        # isscheck will return True if already Downloaded / Snatched,
        # False if it's still in a Wanted status.
        if isscheck is True:
            #logger.fdebug(
            #   '[CID:%s] %s %s is already in a Downloaded / Snatched status.'
            #   % (info['ComicID'], info['ComicName'], info['Issue_Number'])
            #)
            return {'status': False, 'reason': 'already downloaded/snatched'}

        if (
            storedate == '0000-00-00'
            or storedate is None
        ):
            if (
                any(
                    [
                        issuedate is None,
                        issuedate == '0000-00-00',
                    ]
                )
                and digitaldate == '0000-00-00'
                ):
                    #logger.fdebug(
                    #    '[CID:%s] %s has invalid Date-data for issue #%s.'
                    #    ' Skipping searching for this issue.'
                    #    % (info['ComicID'], info['ComicName'], info['Issue_Number'])
                    #)
                    return {'status': False, 'reason': 'invalid date-data'}
        return {'status': True, 'reason': None}
    else:
        return {'status': False, 'reason': 'invalid issueid'}

def get_findcomiciss(IssueNumber):
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

    return findcomiciss, c_number
