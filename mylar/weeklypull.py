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


from __future__ import print_function

import sys
import fileinput
import csv
import getopt
import sqlite3
import urllib
import os
import time
import re
import datetime
import shutil

import mylar
from mylar import db, updater, helpers, logger, newpull, importer, mb, locg

def pullit(forcecheck=None, weeknumber=None, year=None):
    myDB = db.DBConnection()
    if weeknumber is None:
        popit = myDB.select("SELECT count(*) FROM sqlite_master WHERE name='weekly' and type='table'")
        if popit:
            try:
                pull_date = myDB.selectone("SELECT SHIPDATE from weekly").fetchone()
                logger.info(u"Weekly pull list present - checking if it's up-to-date..")
                if (pull_date is None):
                    pulldate = '00000000'
                else:
                    pulldate = pull_date['SHIPDATE']
            except (sqlite3.OperationalError, TypeError), msg:
                logger.info(u"Error Retrieving weekly pull list - attempting to adjust")
                myDB.action("DROP TABLE weekly")
                myDB.action("CREATE TABLE IF NOT EXISTS weekly (SHIPDATE TEXT, PUBLISHER TEXT, ISSUE TEXT, COMIC VARCHAR(150), EXTRA TEXT, STATUS TEXT, ComicID TEXT, IssueID TEXT, CV_Last_Update TEXT, DynamicName TEXT, weeknumber TEXT, year TEXT, volume TEXT, seriesyear TEXT, annuallink TEXT, format TEXT, rowid INTEGER PRIMARY KEY)")
                pulldate = '00000000'
                logger.fdebug(u"Table re-created, trying to populate")
        else:
            logger.info(u"No pullist found...I'm going to try and get a new list now.")
            pulldate = '00000000'
    else:
        pulldate = None

    if pulldate is None and weeknumber is None:
        pulldate = '00000000'

    #only for pw-file or ALT_PULL = 1
    newrl = os.path.join(mylar.CONFIG.CACHE_DIR, 'newreleases.txt')
    mylar.PULLBYFILE = False

    if mylar.CONFIG.ALT_PULL == 1:
        #logger.info('[PULL-LIST] The Alt-Pull method is currently broken. Defaulting back to the normal method of grabbing the pull-list.')
        logger.info('[PULL-LIST] Populating & Loading pull-list data directly from webpage')
        newpull.newpull()
    elif mylar.CONFIG.ALT_PULL == 2:
        logger.info('[PULL-LIST] Populating & Loading pull-list data directly from alternate website')
        if pulldate is not None:
            chk_locg = locg.locg('00000000')  #setting this to 00000000 will do a Recreate on every call instead of a Refresh
        else:
            logger.info('[PULL-LIST] Populating & Loading pull-list data directly from alternate website for specific week of %s, %s' % (weeknumber, year))
            chk_locg = locg.locg(weeknumber=weeknumber, year=year)

        if chk_locg['status'] == 'up2date':
            logger.info('[PULL-LIST] Pull-list is already up-to-date with ' + str(chk_locg['count']) + 'issues. Polling watchlist against it to see if anything is new.')
            mylar.PULLNEW = 'no'
            return new_pullcheck(chk_locg['weeknumber'],chk_locg['year'])
        elif chk_locg['status'] == 'success':
            logger.info('[PULL-LIST] Weekly Pull List successfully loaded with ' + str(chk_locg['count']) + ' issues.')
            return new_pullcheck(chk_locg['weeknumber'],chk_locg['year'])
        elif chk_locg['status'] == 'update_required':
            logger.warn('[PULL-LIST] Your version of Mylar is not up-to-date. You MUST update before this works')
            return
        else:
            logger.info('[PULL-LIST] Unable to retrieve weekly pull-list. Dropping down to legacy method of PW-file')
            mylar.PULLBYFILE = pull_the_file(newrl)
    else:
        logger.info('[PULL-LIST] Populating & Loading pull-list data from file')
        mylar.PULLBYFILE = pull_the_file(newrl)

        #set newrl to a manual file to pull in against that particular file
        #newrl = '/mylar/tmp/newreleases.txt'

    #newtxtfile header info ("SHIPDATE\tPUBLISHER\tISSUE\tCOMIC\tEXTRA\tSTATUS\n")
    #STATUS denotes default status to be applied to pulllist in Mylar (default = Skipped)

    if mylar.CONFIG.ALT_PULL != 2 or mylar.PULLBYFILE is True:
        newfl = os.path.join(mylar.CONFIG.CACHE_DIR, 'Clean-newreleases.txt')

        newtxtfile = open(newfl, 'wb')

        if check(newrl, 'Service Unavailable'):
            logger.info('Retrieval site is offline at the moment.Aborting pull-list update amd will try again later.')
            pullitcheck(forcecheck=forcecheck)
        else:
            pass

        #Prepare the Substitute name switch for pulllist to comic vine conversion
        substitutes = os.path.join(mylar.DATA_DIR, "substitutes.csv")
        if not os.path.exists(substitutes):
            logger.debug('no substitues.csv file located - not performing substitutions on weekly pull list')
            substitute_check = False
        else:
            substitute_check = True
            #shortrep is the name to be replaced, longrep the replacement
            shortrep=[]
            longrep=[]
            #open the file data
            with open(substitutes) as f:
                reader = csv.reader(f, delimiter='|')
                for row in reader:
                    if not row[0].startswith('#'):
                        logger.fdebug("Substitutes file read : " +str(row))
                        shortrep.append(row[0])
                        longrep.append(row[1])
            f.close()

        not_these=['PREVIEWS',
                   'Shipping',
                   'Every Wednesday',
                   'Please check with',
                   'PREMIER PUBLISHERS',
                   'BOOKS',
                   'COLLECTIBLES',
                   'MCFARLANE TOYS',
                   'New Releases',
                   'Upcoming Releases']

        excludes=['2ND PTG',
                  '3RD PTG',
                  '4TH PTG',
                  '5TH PTG',
                  '6TH PTG',
                  '7TH PTG',
                  '8TH PTG',
                  '9TH PTG',
                  'NEW PTG',
                  'POSTER',
                  'COMBO PACK']

        # this checks for the following lists
        # first need to only look for checkit variables
        checkit=['COMICS',
                 'IDW PUBLISHING',
                 'MAGAZINES',
                 'MERCHANDISE']
                 #'COMIC & GRAPHIC NOVELS',

        #if COMICS is found, determine which publisher
        checkit2=['DC',
                  'MARVEL',
                  'DARK HORSE',
                  'IMAGE']
        # used to determine type of comic (one shot, hardcover, tradeback, softcover, graphic novel)
        cmty=['HC',
              'TP',
              'GN',
              'SC',
              'ONE SHOT',
              'PI']

        #denotes issues that contain special characters within that would normally fail when checked if issue ONLY contained numerics.
        #add freely, just lowercase and exclude decimals (they get stripped during comparisons)
        specialissues = {'au', 'ai', 'inh', 'now', 'mu'}

        pub = "COMICS"
        prevcomic = ""
        previssue = ""

        for i in open(newrl):
            if not i.strip():
                continue
            if 'MAGAZINES' in i: break
            if 'MERCHANDISE' in i: break
            for nono in not_these:
                if nono in i:
                    #let's try and grab the date for future pull checks
                    if i.startswith('Shipping') or i.startswith('New Releases') or i.startswith('Upcoming Releases'):
                        shipdatechk = i.split()
                        if i.startswith('Shipping'):
                            shipdate = shipdatechk[1]
                        elif i.startswith('New Releases'):
                            shipdate = shipdatechk[3]
                        elif i.startswith('Upcoming Releases'):
                            shipdate = shipdatechk[3]
                        sdsplit = shipdate.split('/')
                        mo = sdsplit[0]
                        dy = sdsplit[1]
                        if len(mo) == 1: mo = "0" + sdsplit[0]
                        if len(dy) == 1: dy = "0" + sdsplit[1]
                        shipdate = sdsplit[2] + "-" + mo + "-" + dy
                        shipdaterep = shipdate.replace('-', '')
                        pulldate = re.sub('-', '', str(pulldate))
                        logger.fdebug("shipdate: " + str(shipdaterep))
                        logger.fdebug("today: " + str(pulldate))
                        if pulldate == shipdaterep:
                            logger.info(u"No new pull-list available - will re-check again in 24 hours.")
                            mylar.PULLNEW = 'no'
                            return pullitcheck()
                        else:
                            logger.info(u"Preparing to update to the new listing.")
                    break
            else:
                mylar.PULLNEW = 'yes'
                for yesyes in checkit:
                    if yesyes in i:
                        #logger.info('yesyes found: ' + yesyes)
                        if format(str(yesyes)) == 'COMICS':
                            #logger.info('yesyes = comics: ' + format(str(yesyes)))
                            for chkchk in checkit2:
                                flagged = "no"
                                #logger.info('chkchk is : ' + chkchk)
                                if chkchk in i:
                                    #logger.info('chkchk found in i: ' + chkchk)
                                    bl = i.split()
                                    blchk = str(bl[0]) + " " + str(bl[1])
                                    if chkchk in blchk:
                                        pub = format(str(chkchk)) + " COMICS"
                                        #logger.info("chkchk: " + str(pub))
                                        break
                                else:
                                    #logger.info('chkchk not in i - i.findcomics: ' + str(i.find("COMICS")) + ' length: ' + str(len(i.strip())))
                                    if all([i.find("COMICS") < 1, len(i.strip()) == 6]) or ("GRAPHIC NOVELS" in i):
#                                    if i.find("COMICS") < 1 and (len(i.strip()) == 6 or "& GRAPHIC NOVELS" in i):
                                        pub = "COMICS"
                                        #logger.info("i.find comics & len =6 : " + pub)
                                        break
                                    elif i.find("COMICS") > 12:
                                        #logger.info("comics word found in comic title")
                                        flagged = "yes"
                                        break
                        else:
                            #logger.info('yesyes not found: ' + yesyes + ' i.findcomics: ' + str(i.find("COMICS")) + ' length: ' + str(len(i.strip())))
                            if all([i.find("COMICS") < 1, len(i.strip()) == 6]) or ("GRAPHIC NOVELS" in i):
                                #logger.info("format string not comics & i.find < 1: " + pub)
                                pub = "COMICS"
                                break
                            else:
                                pub = format(str(yesyes))
                                #logger.info("format string not comics & i.find > 1: " + pub)
                                break
                        if flagged == "no":
                            break
                else:
                    dupefound = "no"
                    if '#' in i:
                        issname = i.split()
                        #print (issname)
                        issnamec = len(issname)
                        n = 0
                        while (n < issnamec):
                            #find the issue
                            if '#' in (issname[n]):
                                if issname[n] == "PI":
                                    issue = "NA"
                                    break

                                #this is to ensure we don't get any comps added by removing them entirely (ie. #1-4, etc)
                                x = None
                                try:
                                     x = float(re.sub('#', '', issname[n].strip()))
                                except ValueError, e:
                                     if any(d in re.sub(r'[^a-zA-Z0-9]', '', issname[n]).strip() for d in specialissues):
                                        issue = issname[n]
                                     else:
                                        logger.fdebug('Comp issue set detected as : ' + str(issname[n]) + '. Ignoring.')
                                        issue = 'NA'
                                else:
                                    issue = issname[n]

                                if 'ongoing' not in issname[n -1].lower() and '(vu)' not in issname[n -1].lower():
                                    #print ("issue found : " + issname[n])
                                    comicend = n - 1
                                else:
                                    comicend = n - 2
                                break
                            n+=1
                        if issue == "": issue = 'NA'
                        #find comicname
                        comicnm = issname[1]
                        n = 2
                        while (n < comicend + 1):
                            comicnm = comicnm + " " + issname[n]
                            n+=1
                        comcnm = re.sub('1 FOR \$1', '', comicnm).strip()
                        #logger.info("Comicname: " + str(comicnm) )
                        #get remainder
                        try:
                            comicrm = issname[comicend +2]
                        except:
                            try:
                                comicrm = issname[comicend +1]
                            except:
                                try:
                                    comicrm = issname[comicend]
                                except:
                                    comicrm = '$'
                        if '$' in comicrm:
                            comicrm="None"
                        n = (comicend + 3)
                        while (n < issnamec):
                            if '$' in (issname[n]):
                                break
                            comicrm = str(comicrm) + " " + str(issname[n])
                            n+=1
                        #logger.info("Comic Extra info: " + str(comicrm) )
                        #logger.info("ship: " + str(shipdate))
                        #logger.info("pub: " + str(pub))
                        #logger.info("issue: " + str(issue))

                        #--let's make sure we don't wipe out decimal issues ;)
    #                    if '.' in issue:
    #                        issue_decimal = re.compile(r'[^\d.]+')
    #                        issue = issue_decimal.sub('', str(issue))
    #                    else: issue = re.sub('#','', issue)
                        issue = re.sub('#', '', issue)
                        #issue = re.sub("\D", "", str(issue))
                        #store the previous comic/issue for comparison to filter out duplicate issues/alt covers
                        #print ("Previous Comic & Issue: " + str(prevcomic) + "--" + str(previssue))
                        dupefound = "no"
                    else:
                        #if it doesn't have a '#' in the line, then we know it's either
                        #a special edition of some kind, or a non-comic
                        issname = i.split()
                        #print (issname)
                        issnamec = len(issname)
                        n = 1
                        issue = ''
                        while (n < issnamec):
                            #find the type of non-issue (TP,HC,GN,SC,OS,PI etc)
                            for cm in cmty:
                                if "ONE" in issue and "SHOT" in issname[n +1]: issue = "OS"
                                if cm == (issname[n]):
                                    if issname[n] == 'PI':
                                        issue = 'NA'
                                        break
                                    issue = issname[n]
                                    #print ("non-issue found : " + issue)
                                    comicend = n - 1
                                    break
                            n+=1
                        #if the comic doesn't have an issue # or a keyword, adjust.
                        #set it to 'NA' and it'll be filtered out anyways.
                        if issue == "" or issue is None:
                            issue = 'NA'
                            comicend = n - 1  #comicend = comicend - 1  (adjustment for nil)
                        #find comicname
                        comicnm = issname[1]
                        n = 2
                        while (n < comicend + 1):
                            #stupid - this errors out if the array mistakingly goes to far.
                            try:
                                comicnm = comicnm + " " + issname[n]
                            except IndexError:
                                #print ("went too far looking at this comic...adjusting.")
                                comicnm = comicnm
                                break
                            n+=1
                        #print ("Comicname: " + str(comicnm) )
                        #get remainder
                        if len(issname) <= (comicend + 2):
                            comicrm = "None"
                        else:
                            #print ("length:" + str(len(issname)))
                            #print ("end:" + str(comicend + 2))
                            comicrm = issname[comicend +2]
                        if '$' in comicrm:
                            comicrm="None"
                        n = (comicend + 3)
                        while (n < issnamec):
                            if '$' in (issname[n]) or 'PI' in (issname[n]):
                                break
                            comicrm = str(comicrm) + " " + str(issname[n])
                            n+=1
                        #print ("Comic Extra info: " + str(comicrm) )
                        if "NA" not in issue and issue != "":
                            #print ("shipdate:" + str(shipdate))
                            #print ("pub: " + str(pub))
                            #print ("issue: " + str(issue))
                            dupefound = "no"

                    #-- remove html tags when alt_pull is enabled
                    if mylar.CONFIG.ALT_PULL == 1:
                        if '&amp;' in comicnm:
                            comicnm = re.sub('&amp;', '&', comicnm).strip()
                        if '&amp;' in pub:
                            pub = re.sub('&amp;', '&', pub).strip()
                        if '&amp;' in comicrm:
                            comicrm = re.sub('&amp;', '&', comicrm).strip()

                    #--start duplicate comic / issue chk
                    # pullist has shortforms of a series' title sometimes and causes problems
                    if 'O/T' in comicnm:
                        comicnm = re.sub('O/T', 'OF THE', comicnm)

                    if substitute_check == True:
                        #Step through the list - storing an index
                        for repindex, repcheck in enumerate(shortrep):
                            if len(comicnm) >= len(repcheck):
                                #if the leftmost chars match the short text then replace them with the long text
                                if comicnm[:len(repcheck)]==repcheck:
                                    logger.fdebug("Switch worked on " +comicnm + " replacing " + str(repcheck) + " with " + str(longrep[repindex]))
                                    comicnm = re.sub(repcheck, longrep[repindex], comicnm)

                    for excl in excludes:
                        if excl in str(comicrm):
                            #duplicate comic / issue detected - don't add...
                            dupefound = "yes"
                    if prevcomic == str(comicnm) and previssue == str(issue):
                        #duplicate comic/issue detected - don't add...
                        dupefound = "yes"
                    #--end duplicate chk
                    if (dupefound != "yes") and ('NA' not in str(issue)):
                        newtxtfile.write(str(shipdate) + '\t' + str(pub) + '\t' + str(issue) + '\t' + str(comicnm) + '\t' + str(comicrm) + '\tSkipped' + '\n')
                    prevcomic = str(comicnm)
                    previssue = str(issue)

        newtxtfile.close()

        if all([pulldate == '00000000', mylar.CONFIG.ALT_PULL != 2]) or mylar.PULLBYFILE is True:
            pulldate = shipdate

        try:
            weektmp = datetime.date(*(int(s) for s in pulldate.split('-')))
        except TypeError:
            weektmp = datetime.date.today()
        weeknumber = weektmp.strftime("%U")

        logger.info(u"Populating the NEW Weekly Pull list into Mylar for week " + str(weeknumber))

        myDB.action("drop table if exists weekly")
        myDB.action("CREATE TABLE IF NOT EXISTS weekly (SHIPDATE, PUBLISHER TEXT, ISSUE TEXT, COMIC VARCHAR(150), EXTRA TEXT, STATUS TEXT, ComicID TEXT, IssueID TEXT, CV_Last_Update TEXT, DynamicName TEXT, weeknumber TEXT, year TEXT, volume TEXT, seriesyear TEXT, annuallink TEXT, format TEXT, rowid INTEGER PRIMARY KEY)")

        csvfile = open(newfl, "rb")
        creader = csv.reader(csvfile, delimiter='\t')
        t=1

        for row in creader:
            if "MERCHANDISE" in row: break
            if "MAGAZINES" in row: break
            if "BOOK" in row: break
            try:
                cl_d = mylar.filechecker.FileChecker()
                cl_dyninfo = cl_d.dynamic_replace(row[3])
                dynamic_name = re.sub('[\|\s]','', cl_dyninfo['mod_seriesname'].lower()).strip()
                controlValueDict = {'COMIC': row[3],
                                    'ISSUE': row[2],
                                    'EXTRA': row[4]}
                newValueDict = {'SHIPDATE': row[0],
                                'PUBLISHER': row[1],
                                'STATUS': row[5],
                                'COMICID': None,
                                'DYNAMICNAME': dynamic_name,
                                'WEEKNUMBER': int(weeknumber),
                                'YEAR': mylar.CURRENT_YEAR}
                myDB.upsert("weekly", newValueDict, controlValueDict)
            except Exception, e:
                #print ("Error - invald arguments...-skipping")
                pass
            t+=1
        csvfile.close()
        #let's delete the files
        os.remove(os.path.join(mylar.CONFIG.CACHE_DIR, 'Clean-newreleases.txt'))
        os.remove(os.path.join(mylar.CONFIG.CACHE_DIR, 'newreleases.txt'))

        logger.info(u"Weekly Pull List successfully loaded.")

    if mylar.CONFIG.ALT_PULL != 2 or mylar.PULLBYFILE is True:
        pullitcheck(forcecheck=forcecheck)

def pullitcheck(comic1off_name=None, comic1off_id=None, forcecheck=None, futurepull=None, issue=None):
    if futurepull is None:
        logger.info(u"Checking the Weekly Releases list for comics I'm watching...")
    else:
        logger.info('Checking the Future Releases list for upcoming comics I am watching for...')

    myDB = db.DBConnection()

    not_t = ['TP',
             'NA',
             'HC',
             'PI']

    not_c = ['PTG',
             'COMBO PACK',
             '(PP #']

    lines = []
    unlines = []
    llen = []
    ccname = []
    pubdate = []
    latestissue = []
    w = 0
    wc = 0
    tot = 0
    chkout = []
    watchfnd = []
    watchfndiss = []
    watchfndextra = []
    alternate = []

    #print ("----------WATCHLIST--------")
    a_list = []
    b_list = []
    comicid = []

    if comic1off_name is None:
        #let's read in the comic.watchlist from the db here
        #cur.execute("SELECT ComicID, ComicName_Filesafe, ComicYear, ComicPublisher, ComicPublished, LatestDate, ForceContinuing, AlternateSearch, LatestIssue from comics WHERE Status = 'Active'")
        weeklylist = []
        comiclist = myDB.select("SELECT * FROM comics WHERE Status='Active'")
        if comiclist is None:
            pass
        else:

            for weekly in comiclist:
                #assign it.
                weeklylist.append({"ComicName":          weekly['ComicName'],
                                   "ComicID":            weekly['ComicID'],
                                   "ComicName_Filesafe": weekly['ComicName_Filesafe'],
                                   "ComicYear":          weekly['ComicYear'],
                                   "ComicPublisher":     weekly['ComicPublisher'],
                                   "ComicPublished":     weekly['ComicPublished'],
                                   "LatestDate":         weekly['LatestDate'],
                                   "LatestIssue":        weekly['LatestIssue'],
                                   "ForceContinuing":    weekly['ForceContinuing'],
                                   "AlternateSearch":    weekly['AlternateSearch'],
                                   "DynamicName":        weekly['DynamicComicName']})

        if len(weeklylist) > 0:
            for week in weeklylist:
                if 'Present' in week['ComicPublished'] or (helpers.now()[:4] in week['ComicPublished']) or week['ForceContinuing'] == 1:
                    # this gets buggered up when series are named the same, and one ends in the current
                    # year, and the new series starts in the same year - ie. Avengers
                    # lets' grab the latest issue date and see how far it is from current
                    # anything > 45 days we'll assume it's a false match ;)
                    logger.fdebug("ComicName: " + week['ComicName'])
                    latestdate = week['LatestDate']
                    logger.fdebug("latestdate:  " + str(latestdate))
                    if latestdate[8:] == '':
                        if '-' in latestdate[:4] and not latestdate.startswith('20'):
                        #pull-list f'd up the date by putting '15' instead of '2015' causing 500 server errors
                            st_date = latestdate.find('-')
                            st_remainder = latestdate[st_date+1:]
                            st_year = latestdate[:st_date]
                            year = '20' + st_year
                            latestdate = str(year) + '-' + str(st_remainder)
                            #logger.fdebug('year set to: ' + latestdate)
                        else:
                            logger.fdebug("invalid date " + str(latestdate) + " appending 01 for day for continuation.")
                            latest_day = '01'
                    else:
                        latest_day = latestdate[8:]
                    c_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), int(latest_day))
                    n_date = datetime.date.today()
                    logger.fdebug("c_date : " + str(c_date) + " ... n_date : " + str(n_date))
                    recentchk = (n_date - c_date).days
                    logger.fdebug("recentchk: " + str(recentchk) + " days")
                    chklimit = helpers.checkthepub(week['ComicID'])
                    logger.fdebug("Check date limit set to : " + str(chklimit))
                    logger.fdebug(" ----- ")
                    if recentchk < int(chklimit) or week['ForceContinuing'] == 1:
                        if week['ForceContinuing'] == 1:
                            logger.fdebug('Forcing Continuing Series enabled for series...')
                        # let's not even bother with comics that are not in the Present.
                        a_list.append(week['ComicName'])
                        b_list.append(week['ComicYear'])
                        comicid.append(week['ComicID'])
                        pubdate.append(week['ComicPublished'])
                        latestissue.append(week['LatestIssue'])
                        lines.append(a_list[w].strip())
                        unlines.append(a_list[w].strip())
                        w+=1   # we need to increment the count here, so we don't count the same comics twice (albeit with alternate names)

                        #here we load in the alternate search names for a series and assign them the comicid and
                        #alternate names
                        Altload = helpers.LoadAlternateSearchNames(week['AlternateSearch'], week['ComicID'])
                        if Altload == 'no results':
                            pass
                        else:
                            wc = 0
                            alt_cid = Altload['ComicID']
                            n = 0
                            iscnt = Altload['Count']
                            while (n <= iscnt):
                                try:
                                    altval = Altload['AlternateName'][n]
                                except IndexError:
                                    break
                                cleanedname = altval['AlternateName']
                                a_list.append(altval['AlternateName'])
                                b_list.append(week['ComicYear'])
                                comicid.append(alt_cid)
                                pubdate.append(week['ComicPublished'])
                                latestissue.append(week['LatestIssue'])
                                lines.append(a_list[w +wc].strip())
                                unlines.append(a_list[w +wc].strip())
                                logger.fdebug('loading in Alternate name for ' + str(cleanedname))
                                n+=1
                                wc+=1
                            w+=wc

                    else:
                        logger.fdebug("Determined to not be a Continuing series at this time.")
    else:
        # if it's a one-off check (during an add series), load the comicname here and ignore below.
        logger.fdebug("This is a one-off for " + comic1off_name + ' [ latest issue: ' + str(issue) + ' ]')
        lines.append(comic1off_name.strip())
        unlines.append(comic1off_name.strip())
        comicid.append(comic1off_id)
        latestissue.append(issue)
        w = 1

    if w >= 1:
        cnt = int(w -1)
        cntback = int(w -1)
        kp = []
        ki = []
        kc = []
        otot = 0

        logger.fdebug("You are watching for: " + str(w) + " comics")
        #print ("----------THIS WEEK'S PUBLISHED COMICS------------")
        if w > 0:
            while (cnt > -1):
                latestiss = latestissue[cnt]
                if mylar.CONFIG.ALT_PULL != 2:
                    lines[cnt] = lines[cnt].upper()
                #llen[cnt] = str(llen[cnt])
                logger.fdebug("looking for : " + lines[cnt])
                cl_d = mylar.filechecker.FileChecker()
                cl_dyninfo = cl_d.dynamic_replace(lines[cnt])
                dynamic_name = re.sub('[\|\s]','', cl_dyninfo['mod_seriesname'].lower()).strip()
                sqlsearch = '%' + dynamic_name + '%'
                logger.fdebug("searchsql: " + sqlsearch)
                if futurepull is None:
                    weekly = myDB.select('SELECT PUBLISHER, ISSUE, COMIC, EXTRA, SHIPDATE, DynamicName FROM weekly WHERE DynamicName LIKE (?) COLLATE NOCASE', [sqlsearch])
                else:
                    weekly = myDB.select('SELECT PUBLISHER, ISSUE, COMIC, EXTRA, SHIPDATE FROM future WHERE COMIC LIKE (?) COLLATE NOCASE', [sqlsearch])
                #cur.execute('SELECT PUBLISHER, ISSUE, COMIC, EXTRA, SHIPDATE FROM weekly WHERE COMIC LIKE (?)', [lines[cnt]])
                for week in weekly:
                    if week == None:
                        break
                    for nono in not_t:
                        if nono in week['PUBLISHER']:
                            #logger.fdebug("nono present")
                            continue
                        if nono in week['ISSUE']:
                            #logger.fdebug("graphic novel/tradeback detected..ignoring.")
                            continue
                    for nothere in not_c:
                        if week['EXTRA'] is not None:
                            if nothere in week['EXTRA']:
                                continue

                    comicnm = week['COMIC']
                    dyn_comicnm = week['DynamicName']
                    dyn_watchnm = dynamic_name
                    logger.fdebug("comparing" + comicnm + "..to.." + unlines[cnt].upper())
                    watchcomic = unlines[cnt]

                    logger.fdebug("watchcomic : " + watchcomic)  # / mod :" + str(modwatchcomic))
                    logger.fdebug("comicnm : " + comicnm) # / mod :" + str(modcomicnm))

                    if dyn_comicnm == dyn_watchnm:
                        if mylar.CONFIG.ANNUALS_ON:
                            if 'annual' in watchcomic.lower() and 'annual' not in comicnm.lower():
                                logger.fdebug('Annual detected in issue, but annuals are not enabled and no series match in wachlist.')
                                continue
                            else:
                                #(annual in comicnm & in watchcomic) or (annual in comicnm & not in watchcomic)(with annuals on) = match.
                                pass
                        else:
                            #annuals off
                            if ('annual' in comicnm.lower() and 'annual' not in watchcomic.lower()) or ('annual' in watchcomic.lower() and 'annual' not in comicnm.lower()):
                                logger.fdebug('Annual detected in issue, but annuals are not enabled and no series match in wachlist.')
                                continue
                            else:
                                #annual in comicnm & in watchcomic (with annuals off) = match.
                                pass
                        logger.fdebug("matched on:" + comicnm + "..." + watchcomic.upper())
                        watchcomic = unlines[cnt]
                    else:
                        continue


                    if ("NA" not in week['ISSUE']) and ("HC" not in week['ISSUE']):
                        if week['EXTRA'] is not None and any(["COMBO PACK" in week['EXTRA'],"2ND PTG" in week['EXTRA'], "3RD PTG" in week['EXTRA']]):
                            continue
                        else:
                                    #this all needs to get redone, so the ability to compare issue dates can be done systematically.
                                    #Everything below should be in it's own function - at least the callable sections - in doing so, we can
                                    #then do comparisons when two titles of the same name exist and are by definition 'current'. Issue date comparisons
                                    #would identify the difference between two #1 titles within the same series year, but have different publishing dates.
                                    #Wolverine (2013) & Wolverine (2014) are good examples of this situation.
                                    #of course initially, the issue data for the newer series wouldn't have any issue data associated with it so it would be
                                    #a null value, but given that the 2013 series (as an example) would be from 2013-05-01, it obviously wouldn't be a match to
                                    #the current date & year (2014). Throwing out that, we could just assume that the 2014 would match the #1.

                                    #get the issue number of the 'weeklypull' series.
                                    #load in the actual series issue number's store-date (not publishing date)
                                    #---use a function to check db, then return the results in a tuple/list to avoid db locks.
                                    #if the store-date is >= weeklypull-list date then continue processing below.
                                    #if the store-date is <= weeklypull-list date then break.
                                    ### week['ISSUE']  #issue # from pullist
                                    ### week['SHIPDATE']  #weeklypull-list date
                                    ### comicid[cnt] #comicid of matched series

                                    ## if it's a futurepull, the dates get mixed up when two titles exist of the same name
                                    ## ie. Wolverine-2011 & Wolverine-2014
                                    ## we need to set the compare date to today's date ( Now() ) in this case.
                            if futurepull:
                                usedate = datetime.datetime.now().strftime('%Y%m%d')  #convert to yyyymmdd
                            else:
                                usedate = re.sub("[^0-9]", "", week['SHIPDATE'])

                            if 'ANNUAL' in comicnm.upper():
                                chktype = 'annual'
                            else:
                                chktype = 'series'

                            datevalues = loaditup(watchcomic, comicid[cnt], week['ISSUE'], chktype)

                            date_downloaded = None
                            altissuenum = None

                            if datevalues == 'no results':
                                #if a series is a .NOW on the pullist, it won't match up against anything (probably) on CV
                                #let's grab the digit from the .NOW, poll it against CV to see if there's any data
                                #if there is, check the store date to make sure it's a 'new' release.
                                #if it is a new release that has the same store date as the .NOW, then we assume
                                #it's the same, and assign it the AltIssueNumber to do extra searches.
                                if week['ISSUE'].isdigit() == False and '.' not in week['ISSUE']:
                                    altissuenum = re.sub("[^0-9]", "", week['ISSUE'])  # carry this through to get added to db later if matches
                                    logger.fdebug('altissuenum is: ' + str(altissuenum))
                                    altvalues = loaditup(watchcomic, comicid[cnt], altissuenum, chktype)
                                    if altvalues == 'no results':
                                        logger.fdebug('No alternate Issue numbering - something is probably wrong somewhere.')
                                        continue

                                    validcheck = checkthis(altvalues[0]['issuedate'], altvalues[0]['status'], usedate)
                                    if validcheck == False:
                                        if date_downloaded is None:
                                            continue
                                if chktype == 'series':
                                    latest_int = helpers.issuedigits(latestiss)
                                    weekiss_int = helpers.issuedigits(week['ISSUE'])
                                    logger.fdebug('comparing ' + str(latest_int) + ' to ' + str(weekiss_int))
                                    if (latest_int > weekiss_int) and (latest_int != 0 or weekiss_int != 0):
                                        logger.fdebug(str(week['ISSUE']) + ' should not be the next issue in THIS volume of the series.')
                                        logger.fdebug('it should be either greater than ' + str(latestiss) + ' or an issue #0')
                                        continue

                            else:
                                logger.fdebug('issuedate:' + str(datevalues[0]['issuedate']))
                                logger.fdebug('status:' + str(datevalues[0]['status']))
                                datestatus = datevalues[0]['status']
                                validcheck = checkthis(datevalues[0]['issuedate'], datestatus, usedate)
                                if validcheck == True:
                                    if datestatus != 'Downloaded' and datestatus != 'Archived':
                                        pass
                                    else:
                                        logger.fdebug('Issue #' + str(week['ISSUE']) + ' already downloaded.')
                                        date_downloaded = datestatus
                                else:
                                    if date_downloaded is None:
                                        continue

                            otot+=1
                            dontadd = "no"
                            if dontadd == "no":
                                tot+=1
                                if "ANNUAL" in comicnm.upper():
                                    watchfndextra.append("annual")
                                    ComicName = str(unlines[cnt]) + " Annual"
                                else:
                                    ComicName = str(unlines[cnt])
                                    watchfndextra.append("none")
                                watchfnd.append(comicnm)
                                watchfndiss.append(week['ISSUE'])
                                ComicID = comicid[cnt]
                                if not mylar.CONFIG.CV_ONLY:
                                    ComicIssue = str(watchfndiss[tot -1] + ".00")
                                else:
                                    ComicIssue = str(watchfndiss[tot -1])
                                ComicDate = str(week['SHIPDATE'])
                                logger.fdebug("Watchlist hit for : " + ComicName + " ISSUE: " + str(watchfndiss[tot -1]))
 
                                # here we add to comics.latest
                                updater.latest_update(ComicID=ComicID, LatestIssue=ComicIssue, LatestDate=ComicDate)
                                # here we add to upcoming table...
                                statusupdate = updater.upcoming_update(ComicID=ComicID, ComicName=ComicName, IssueNumber=ComicIssue, IssueDate=ComicDate, forcecheck=forcecheck)

                                # here we update status of weekly table...
                                try:
                                    if statusupdate is not None:
                                        cstatusid = []
                                        cstatus = statusupdate['Status']
                                        cstatusid = {"ComicID": statusupdate['ComicID'],
                                                     "IssueID": statusupdate['IssueID']}

                                    else:
                                        cstatus = None
                                        cstatusid = None
                                except:
                                    cstatusid = None
                                    cstatus = None

                                if date_downloaded is None:
                                    updater.weekly_update(ComicName=week['COMIC'], IssueNumber=ComicIssue, CStatus=cstatus, CID=cstatusid, weeknumber=mylar.CURRENT_WEEKNUMBER, year=mylar.CURRENT_YEAR, altissuenumber=altissuenum)
                                else:
                                    updater.weekly_update(ComicName=week['COMIC'], IssueNumber=ComicIssue, CStatus=date_downloaded, CID=cstatusid, weeknumber=mylar.CURRENT_WEEKNUMBER, year=mylar.CURRENT_YEAR, altissuenumber=altissuenum)
                    break
                cnt-=1

        logger.fdebug("There are " + str(otot) + " comics this week to get!")
        logger.info(u"Finished checking for comics on my watchlist.")
    return {'status': 'success'}

def new_pullcheck(weeknumber, pullyear, comic1off_name=None, comic1off_id=None, forcecheck=None, issue=None):
    #the new pull method (ALT_PULL=2) already has the comicid & issueid (if available) present in the response that's polled by mylar.
    #this should be as simple as checking if the comicid exists on the given watchlist, and if so mark it as Wanted in the Upcoming table
    #and then once the issueid is present, put it the Wanted table.
    myDB = db.DBConnection()
    watchlist = []
    weeklylist = []
    pullist = helpers.listPull(weeknumber,pullyear)
    if comic1off_name:
        comiclist = myDB.select("SELECT * FROM comics WHERE Status='Active' AND ComicID=?",[comic1off_id])
    else:
        comiclist = myDB.select("SELECT * FROM comics WHERE Status='Active'")

    if comiclist is None:
        pass
    else:
        for weekly in comiclist:
            #assign it.
            watchlist.append({"ComicName":          weekly['ComicName'],
                              "ComicID":            weekly['ComicID'],
                              "ComicName_Filesafe": weekly['ComicName_Filesafe'],
                              "ComicYear":          weekly['ComicYear'],
                              "ComicPublisher":     weekly['ComicPublisher'],
                              "ComicPublished":     weekly['ComicPublished'],
                              "LatestDate":         weekly['LatestDate'],
                              "LatestIssue":        weekly['LatestIssue'],
                              "ForceContinuing":    weekly['ForceContinuing'],
                              "AlternateSearch":    weekly['AlternateSearch'],
                              "DynamicName":        weekly['DynamicComicName']})

    if len(watchlist) > 0:
        for watch in watchlist:
            listit = [pls for pls in pullist if str(pls) == str(watch['ComicID'])] 
            #logger.info('listit: %s' % listit)
            if 'Present' in watch['ComicPublished'] or (helpers.now()[:4] in watch['ComicPublished']) or watch['ForceContinuing'] == 1 or len(listit) >0:
                # this gets buggered up when series are named the same, and one ends in the current
                # year, and the new series starts in the same year - ie. Avengers
                # lets' grab the latest issue date and see how far it is from current
                # anything > 45 days we'll assume it's a false match ;)
                #logger.fdebug('[PRESENT] ComicName: %s [%s]' % (watch['ComicName'], watch['ComicID']))
                latestdate = watch['LatestDate']
                #logger.fdebug("latestdate:  " + str(latestdate))
                if latestdate[8:] == '':
                    if '-' in latestdate[:4] and not latestdate.startswith('20'):
                    #pull-list f'd up the date by putting '15' instead of '2015' causing 500 server errors
                        st_date = latestdate.find('-')
                        st_remainder = latestdate[st_date+1:]
                        st_year = latestdate[:st_date]
                        year = '20' + st_year
                        latestdate = str(year) + '-' + str(st_remainder)
                        #logger.fdebug('year set to: ' + latestdate)
                    else:
                        logger.fdebug("invalid date " + str(latestdate) + " appending 01 for day for continuation.")
                        latest_day = '01'
                else:
                    latest_day = latestdate[8:]
                try:
                    c_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), int(latest_day))
                except ValueError:
                    logger.error('Invalid Latest Date returned for ' + watch['ComicName'] + '. Series needs to be refreshed so that is what I am going to do.')
                    #refresh series here and then continue.
 
                n_date = datetime.date.today()
                #logger.fdebug("c_date : " + str(c_date) + " ... n_date : " + str(n_date))
                recentchk = (n_date - c_date).days
                #logger.fdebug("recentchk: " + str(recentchk) + " days")
                chklimit = helpers.checkthepub(watch['ComicID'])
                #logger.fdebug("Check date limit set to : " + str(chklimit))
                #logger.fdebug(" ----- ")
                if recentchk < int(chklimit) or watch['ForceContinuing'] == 1 or len(listit) > 0:
                    if watch['ForceContinuing'] == 1:
                        logger.fdebug('Forcing Continuing Series enabled for %s [%s]' % (watch['ComicName'],watch['ComicID']))
                    # let's not even bother with comics that are not in the Present.
                    Altload = helpers.LoadAlternateSearchNames(watch['AlternateSearch'], watch['ComicID'])
                    if Altload == 'no results' or Altload is None:
                        altnames = None
                    else:
                        altnames = []
                        for alt in Altload['AlternateName']:
                            altnames.append(alt['AlternateName'])

                    #pull in the annual IDs attached to the given series here for pinpoint accuracy.
                    annualist = myDB.select('SELECT * FROM annuals WHERE ComicID=?', [watch['ComicID']])
                    annual_ids = []
                    if annualist is None:
                        pass
                    else:
                        for an in annualist:
                            #logger.info('annuals for %s: %s' % (an['ReleaseComicName'], an['ReleaseComicID']))
                            if not any([x for x in annual_ids if x['ComicID'] == an['ReleaseComicID']]):
                                annual_ids.append({'ComicID':    an['ReleaseComicID'],
                                                   'ComicName':  an['ReleaseComicName']})

                    weeklylist.append({'ComicName':       watch['ComicName'],
                                       'SeriesYear':      watch['ComicYear'],
                                       'ComicID':         watch['ComicID'],
                                       'Pubdate':         watch['ComicPublished'],
                                       'latestIssue':     watch['LatestIssue'],
                                       'DynamicName':     watch['DynamicName'],
                                       'AnnDynamicName':  re.sub('annual', '', watch['DynamicName'].lower()).strip(),
                                       'AlternateNames':  altnames,
                                       'AnnualIDs':       annual_ids})
                else:
                    #logger.fdebug("Determined to not be a Continuing series at this time.")
                    pass

    if len(weeklylist) >= 1:
        kp = []
        ki = []
        kc = []
        otot = 0
        if not comic1off_id:
            logger.fdebug("[WALKSOFTLY] You are watching for: " + str(len(weeklylist)) + " comics")

        weekly = myDB.select('SELECT a.comicid, IFNULL(a.Comic,IFNULL(b.ComicName, c.ComicName)) as ComicName, a.rowid, a.issue, a.issueid, c.ComicPublisher, a.weeknumber, a.shipdate, a.dynamicname, a.annuallink FROM weekly as a INNER JOIN annuals as b INNER JOIN comics as c ON b.releasecomicid = a.comicid OR c.comicid = a.comicid OR c.DynamicComicName = a.dynamicname OR a.annuallink = c.comicid WHERE weeknumber = ? AND year = ? GROUP BY a.dynamicname', [int(weeknumber),pullyear]) #comics INNER JOIN weekly ON comics.DynamicComicName = weekly.dynamicname OR comics.comicid = weekly.comicid INNER JOIN annuals ON annuals.comicid = weekly.comicid WHERE weeknumber = ? GROUP BY weekly.dynamicname', [weeknumber])
        if mylar.CONFIG.ANNUALS_ON is True:
            #Need to loop over the weekly section and check the name of the title against the ComicName in the annuals table
            # this is to pick up new #1 annuals that don't exist in the db yet, and won't until a refresh of the series happens.
            pass
        for week in weekly:
            #logger.fdebug('week: %s [%s]' % (week['ComicName'], week['comicid']))
            idmatch = None
            annualidmatch = None
            namematch = None
            if week is None:
                break
            idmatch = [x for x in weeklylist if week['comicid'] is not None and int(x['ComicID']) == int(week['comicid'])]
            if mylar.CONFIG.ANNUALS_ON is True:
                annualidmatch = [x for x in weeklylist if week['comicid'] is not None and ([xa for xa in x['AnnualIDs'] if int(xa['ComicID']) == int(week['comicid'])])]
                if not annualidmatch:
                    annualidmatch = [x for x in weeklylist if week['annuallink'] is not None and (int(x['ComicID']) == int(week['annuallink']))]
            #The above will auto-match against ComicID if it's populated on the pullsite, otherwise do name-matching.
            namematch = [ab for ab in weeklylist if ab['DynamicName'] == week['dynamicname']]
            #logger.fdebug('rowid: ' + str(week['rowid']))
            #logger.fdebug('idmatch: ' + str(idmatch))
            #logger.fdebug('annualidmatch: ' + str(annualidmatch))
            #logger.fdebug('namematch: ' + str(namematch))
            if any([idmatch,namematch,annualidmatch]):
                if idmatch and not annualidmatch:
                    comicname = idmatch[0]['ComicName'].strip()
                    latestiss = idmatch[0]['latestIssue'].strip()
                    comicid = idmatch[0]['ComicID'].strip()
                    logger.fdebug('[WEEKLY-PULL-ID] Series Match to ID --- ' + comicname + ' [' + comicid + ']')
                elif annualidmatch:
                    try:
                        if 'annual' in week['ComicName'].lower():
                            comicname = annualidmatch[0]['AnnualIDs'][0]['ComicName'].strip()
                        else:
                            comicname = week['ComicName']
                    except:
                        comicname = week['ComicName']
                    latestiss = annualidmatch[0]['latestIssue'].strip()
                    if mylar.CONFIG.ANNUALS_ON:
                        comicid = annualidmatch[0]['ComicID'].strip()
                    else:
                        comicid = annualidmatch[0]['AnnualIDs'][0]['ComicID'].strip()
                    logger.fdebug('[WEEKLY-PULL-ANNUAL] Series Match to ID --- ' + comicname + ' [' + comicid + ']')
                else:
                    #if it's a name metch, it means that CV hasn't been populated yet with the necessary data
                    #do a quick issue check to see if the next issue number is in sequence and not a #1, or like #900
                    latestiss = namematch[0]['latestIssue'].strip()
                    try:
                        diff = int(week['Issue']) - int(latestiss)
                    except ValueError as e:
                        logger.warn('[WEEKLY-PULL] Invalid issue number detected. Skipping this entry for the time being.')
                        continue
                    if diff >= 0 and diff < 3:
                        comicname = namematch[0]['ComicName'].strip()
                        comicid = namematch[0]['ComicID'].strip()
                        logger.fdebug('[WEEKLY-PULL-NAME] Series Match to Name --- ' + comicname + ' [' + comicid + ']')
                    else:
                        logger.fdebug('[WEEKLY-PULL] Series ID:' + namematch[0]['ComicID'] + ' not a match based on issue number comparison [LatestIssue:' + latestiss + '][MatchIssue:' + week['Issue'] + ']')
                        continue

                date_downloaded = None
                todaydate = datetime.datetime.today()
                try:
                    ComicDate = str(week['shipdate'])
                except TypeError, e:
                    ComicDate = todaydate.strftime('%Y-%m-%d')
                    logger.fdebug('[WEEKLY-PULL] Invalid Cover date. Forcing to weekly pull date of : ' + str(ComicDate))

                if week['issueid'] is not None:
                    logger.fdebug('[WEEKLY-PULL] Issue Match to ID --- ' + comicname + ' #' + str(week['issue']) + '[' + comicid + '/' + week['issueid'] + ']')
                    issueid = week['issueid']
                else:
                    issueid = None
  
                    if 'annual' in comicname.lower():
                        chktype = 'annual'
                    else:
                        chktype = 'series'

                    datevalues = loaditup(comicname, comicid, week['issue'], chktype)
                    logger.fdebug('datevalues: ' + str(datevalues))

                    usedate = re.sub("[^0-9]", "", ComicDate).strip()
                    if datevalues == 'no results':
                        if week['issue'].isdigit() == False and '.' not in week['issue']:
                            altissuenum = re.sub("[^0-9]", "", week['issue'])  # carry this through to get added to db later if matches
                            logger.fdebug('altissuenum is: ' + str(altissuenum))
                            altvalues = loaditup(comicname, comicid, altissuenum, chktype)
                            if altvalues == 'no results':
                                logger.fdebug('No alternate Issue numbering - something is probably wrong somewhere.')
                                continue

                            validcheck = checkthis(altvalues[0]['issuedate'], altvalues[0]['status'], usedate)
                            if validcheck == False:
                                if date_downloaded is None:
                                    continue
                        if chktype == 'series':
                            latest_int = helpers.issuedigits(latestiss)
                            weekiss_int = helpers.issuedigits(week['issue'])
                            logger.fdebug('comparing ' + str(latest_int) + ' to ' + str(weekiss_int))
                            if (latest_int > weekiss_int) and (latest_int != 0 or weekiss_int != 0):
                                logger.fdebug(str(week['issue']) + ' should not be the next issue in THIS volume of the series.')
                                logger.fdebug('it should be either greater than ' + x['latestIssue'] + ' or an issue #0')
                                continue
                    else:
                        logger.fdebug('issuedate:' + str(datevalues[0]['issuedate']))
                        logger.fdebug('status:' + str(datevalues[0]['status']))
                        datestatus = datevalues[0]['status']
                        validcheck = checkthis(datevalues[0]['issuedate'], datestatus, usedate)
                        if validcheck == True:
                            if datestatus != 'Downloaded' and datestatus != 'Archived':
                                pass
                            else:
                                logger.fdebug('Issue #' + str(week['issue']) + ' already downloaded.')
                                date_downloaded = datestatus
                        else:
                            if date_downloaded is None:
                                continue

                logger.fdebug("Watchlist hit for : " + week['ComicName'] + " #: " + str(week['issue']))
                if mylar.CURRENT_WEEKNUMBER is None:
                    mylar.CURRENT_WEEKNUMBER = todaydate.strftime("%U")

#                if int(mylar.CURRENT_WEEKNUMBER) == int(weeknumber):
                # here we add to comics.latest
                updater.latest_update(ComicID=comicid, LatestIssue=week['issue'], LatestDate=ComicDate)
                # here we add to upcoming table...
                statusupdate = updater.upcoming_update(ComicID=comicid, ComicName=comicname, IssueNumber=week['issue'], IssueDate=ComicDate, forcecheck=forcecheck, weekinfo={'weeknumber':weeknumber,'year':pullyear})
                logger.fdebug('statusupdate: ' + str(statusupdate))

                # here we update status of weekly table...
                try:
                    if statusupdate is not None:
                        cstatusid = []
                        cstatus = statusupdate['Status']
                        cstatusid = {"ComicID": statusupdate['ComicID'],
                                     "IssueID": statusupdate['IssueID']}
                    else:
                        cstatus = None
                        cstatusid = None
                except:
                    cstatusid = None
                    cstatus = None

                logger.fdebug('date_downloaded: ' + str(date_downloaded))
                controlValue = {"rowid": int(week['rowid'])}
                if any([(idmatch and not namematch),(idmatch and annualidmatch and namematch),(annualidmatch and not namematch),(annualidmatch or idmatch and not namematch)]):
                    if annualidmatch:
                        newValue = {"ComicID":       annualidmatch[0]['ComicID']}
                    else:
                        #if it matches to id, but not name - consider this an alternate and use the cv name and update based on ID so we don't get duplicates
                        newValue = {"ComicID":       cstatusid['ComicID']}

                    newValue['COMIC'] = comicname
                    newValue['ISSUE'] = week['issue']
                    newValue['WEEKNUMBER'] = int(weeknumber)
                    newValue['YEAR'] = pullyear

                    if issueid:
                        newValue['IssueID'] = issueid

                else:
                    newValue = {"ComicID":       comicid,
                                "COMIC":         week['ComicName'],
                                "ISSUE":         week['issue'],
                                "WEEKNUMBER":    int(weeknumber),
                                "YEAR":          pullyear}

                #logger.fdebug('controlValue:' + str(controlValue))

                if not issueid:
                    try:
                        if cstatusid['IssueID']:
                            newValue['IssueID'] = cstatusid['IssueID']
                        else:
                            cidissueid = None
                    except:
                        cidissueid = None


                #logger.fdebug('cstatus:' + str(cstatus))
                if any([date_downloaded, cstatus]):
                    if date_downloaded:
                        cst = date_downloaded
                    else:
                        cst = cstatus
                    newValue['Status'] = cst
                else:
                    if mylar.CONFIG.AUTOWANT_UPCOMING:
                        newValue['Status'] = 'Wanted'
                    else:
                        newValue['Status'] = 'Skipped'


                #setting this here regardless, as it will be a match for a watchlist hit at this point anyways - so link it here what's availalbe.
                #logger.fdebug('newValue:' + str(newValue))
                myDB.upsert("weekly", newValue, controlValue)

                #if the issueid exists on the pull, but not in the series issue list, we need to forcibly refresh the series so it's in line
                if issueid:
                    #logger.info('issue id check passed.')
                    if annualidmatch:
                        isschk = myDB.selectone('SELECT * FROM annuals where IssueID=?', [issueid]).fetchone()
                    else:
                        isschk = myDB.selectone('SELECT * FROM issues where IssueID=?', [issueid]).fetchone()

                    if isschk is None:
                        isschk = myDB.selectone('SELECT * FROM annuals where IssueID=?', [issueid]).fetchone()
                        if isschk is None:
                            logger.fdebug('[WEEKLY-PULL] Forcing a refresh of the series to ensure it is current [' + str(comicid) +'].')
                            anncid = None
                            seriesyear = None
                            try:
                                if all([mylar.CONFIG.ANNUALS_ON is True, len(annualidmatch[0]['AnnualIDs']) == 0]) or all([mylar.CONFIG.ANNUALS_ON is True, annualidmatch[0]['AnnualIDs'][0]['ComicID'] != week['comicid']]):
                                #if the annual/special on the weekly is not a part of the series, pass in the anncomicid so that it can get added.
                                    anncid = week['comicid']
                                    seriesyear = annualidmatch[0]['SeriesYear']
                            except Exception as e:
                                pass

                            #refresh series.
                            if anncid is None:
                                cchk = mylar.importer.updateissuedata(comicid, comicname, calledfrom='weeklycheck')
                            else:
                                cchk = mylar.importer.manualAnnual(anncid, comicname, seriesyear, comicid)

                        else:
                            logger.fdebug('annual issue exists in db already: ' + str(issueid))
                            pass

                    else:
                        logger.fdebug('issue exists in db already: ' + str(issueid))
                        if isschk['Status'] == newValue['Status']:
                            pass
                        else:
                            if all([isschk['Status'] != 'Downloaded', isschk['Status'] != 'Snatched', isschk['Status'] != 'Archived', isschk['Status'] != 'Ignored']) and newValue['Status'] == 'Wanted':
                            #make sure the status is Wanted and that the issue status is identical if not.
                                newStat = {'Status': 'Wanted'}
                                ctrlStat = {'IssueID': issueid}
                                if all([annualidmatch, mylar.CONFIG.ANNUALS_ON]):
                                    myDB.upsert("annuals", newStat, ctrlStat)
                                else:
                                    myDB.upsert("issues", newStat, ctrlStat)
            else:
                continue
#                else:
#                    #if it's polling against a future week, don't update anything but the This Week table.
#                    updater.weekly_update(ComicName=comicname, IssueNumber=week['issue'], CStatus='Wanted', CID=comicid, weeknumber=weeknumber, year=pullyear, altissuenumber=None)





def check(fname, txt):
    try:
        with open(fname) as dataf:
            return any(txt in line for line in dataf)
    except:
        return None

def loaditup(comicname, comicid, issue, chktype):
    myDB = db.DBConnection()
    issue_number = helpers.issuedigits(issue)
    if chktype == 'annual':
        typedisplay = 'annual issue'
        logger.fdebug('[' + comicname + '] trying to locate ' + str(typedisplay) + ' ' + str(issue) + ' to do comparitive issue analysis for pull-list')
        issueload = myDB.selectone('SELECT * FROM annuals WHERE ComicID=? AND Int_IssueNumber=?', [comicid, issue_number]).fetchone()
    else:
        typedisplay = 'issue'
        logger.fdebug('[' + comicname + '] trying to locate ' + str(typedisplay) + ' ' + str(issue) + ' to do comparitive issue analysis for pull-list')
        issueload = myDB.selectone('SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?', [comicid, issue_number]).fetchone()

    if issueload is None:
        logger.fdebug('No results matched for Issue number - either this is a NEW issue with no data yet, or something is wrong')
        return 'no results'

    dataissue = []
    releasedate = issueload['ReleaseDate']
    storedate = issueload['IssueDate']
    status = issueload['Status']

    if releasedate == '0000-00-00':
        logger.fdebug('Store date of 0000-00-00 returned for ' + str(typedisplay) + ' # ' + str(issue) + '. Refreshing series to see if valid date present')
        #mismatch = 'no'
        #issuerecheck = mylar.importer.addComictoDB(comicid,mismatch,calledfrom='weekly',issuechk=issue_number,issuetype=chktype)
        #issuerecheck = mylar.importer.updateissuedata(comicid, comicname, calledfrom='weekly', issuechk=issue_number, issuetype=chktype)
        #if issuerecheck is not None:
        #    for il in issuerecheck:
        #        #this is only one record..
        #        releasedate = il['IssueDate']
        #        storedate = il['ReleaseDate']
        #        #status = il['Status']
        #    logger.fdebug('issue-recheck releasedate is : ' + str(releasedate))
        #    logger.fdebug('issue-recheck storedate of : ' + str(storedate))

    if releasedate is not None and releasedate != "None" and releasedate != "":
        logger.fdebug('Returning Release Date for ' + str(typedisplay) + ' # ' + str(issue) + ' of ' + str(releasedate))
        thedate = re.sub("[^0-9]", "", releasedate)  #convert date to numerics only (should be in yyyymmdd)
        #return releasedate
    else:
        logger.fdebug('Returning Publication Date for issue ' + str(typedisplay) + ' # ' + str(issue) + ' of ' + str(storedate))
        if storedate is None and storedate != "None" and storedate != "":
            logger.fdebug('no issue data available - both release date & store date. Returning no results')
            return 'no results'
        thedate = re.sub("[^0-9]", "", storedate)  #convert date to numerics only (should be in yyyymmdd)
        #return storedate

    dataissue.append({"issuedate":  thedate,
                      "status":     status})

    return dataissue

def checkthis(datecheck, datestatus, usedate):

    logger.fdebug('Now checking date comparison using an issue store date of ' + str(datecheck))
    logger.fdebug('Using a compare date (usedate) of ' + str(usedate))
    logger.fdebug('Status of ' + str(datestatus))

    #give an allowance of 10 days to datecheck for late publishs (+1.5 weeks)
    if int(datecheck) + 10 >= int(usedate):
        logger.fdebug('Store Date falls within acceptable range - series MATCH')
        valid_check = True
    elif int(datecheck) < int(usedate):
        if datecheck == '00000000':
            logger.fdebug('Issue date retrieved as : ' + str(datecheck) + '. This is unpopulated data on CV, which normally means it\'s a new issue and is awaiting data population.')
            valid_check = True
        else:
            logger.fdebug('The issue date of issue was on ' + str(datecheck) + ' which is prior to ' + str(usedate))
            valid_check = False

    return valid_check

def pull_the_file(newrl):
    import requests
    PULLURL = 'https://www.previewsworld.com/shipping/newreleases.txt'
    PULL_AGENT = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'}
    try:
        r = requests.get(PULLURL, verify=True, headers=PULL_AGENT, stream=True)
    except requests.exceptions.RequestException as e:
        logger.warn(e)
        return False

    with open(newrl, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()

    return True

def weekly_check(comicid, issuenum, file=None, path=None, module=None, issueid=None):

    if module is None:
        module = ''
    module += '[WEEKLY-PULL]'
    myDB = db.DBConnection()

    if issueid is None:
       chkit = myDB.selectone('SELECT * FROM weekly WHERE ComicID=? AND ISSUE=?', [comicid, issuenum]).fetchone()
    else:
       chkit = myDB.selectone('SELECT * FROM weekly WHERE ComicID=? AND IssueID=?', [comicid, issueid]).fetchone()

    if chkit is None:
        logger.fdebug(module + ' ' + file + ' is not on the weekly pull-list or it is a one-off download that is not supported as of yet.')
        return

    logger.info(module + ' Issue found on weekly pull-list.')

    weekinfo = helpers.weekly_info(chkit['weeknumber'],chkit['year'])

    if mylar.CONFIG.WEEKFOLDER:
        weekly_singlecopy(comicid, issuenum, file, path, weekinfo)
    if mylar.CONFIG.SEND2READ:
        send2read(comicid, issueid, issuenum)
    return

def weekly_singlecopy(comicid, issuenum, file, path, weekinfo):

    module = '[WEEKLY-PULL COPY]'
    if mylar.CONFIG.WEEKFOLDER:
        if mylar.CONFIG.WEEKFOLDER_LOC:
            weekdst = mylar.CONFIG.WEEKFOLDER_LOC
        else:
            weekdst = mylar.CONFIG.DESTINATION_DIR

        if mylar.CONFIG.WEEKFOLDER_FORMAT == 0:
            desdir = os.path.join(weekdst, str( str(weekinfo['year']) + '-' + str(weekinfo['weeknumber']) ))
        else:
            desdir = os.path.join(weekdst, str( str(weekinfo['midweek']) ))

        dircheck = mylar.filechecker.validateAndCreateDirectory(desdir, True, module=module)
        if dircheck:
            pass
        else:
            desdir = mylar.CONFIG.DESTINATION_DIR

    else:
        desdir = mylar.CONFIG.GRABBAG_DIR

    desfile = os.path.join(desdir, file)
    srcfile = os.path.join(path)

    try:
        shutil.copy2(srcfile, desfile)
    except IOError as e:
        logger.error(module + ' Could not copy ' + str(srcfile) + ' to ' + str(desfile))
        return

    logger.info(module + ' Sucessfully copied to ' + desfile.encode('utf-8').strip())
    return

def send2read(comicid, issueid, issuenum):

    module = '[READLIST]'
    if mylar.CONFIG.SEND2READ:
        logger.info(module + " Send to Reading List enabled for new pulls. Adding to your readlist in the status of 'Added'")
        if issueid is None:
            chkthis = myDB.selectone('SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?', [comicid, helpers.issuedigits(issuenum)]).fetchone()
            annchk = myDB.selectone('SELECT * FROM annuals WHERE ComicID=? AND Int_IssueNumber=?', [comicid, helpers.issuedigits(issuenum)]).fetchone()
            if chkthis is None and annchk is None:
                logger.warn(module + ' Unable to locate issue within your series watchlist.')
                return
            if chkthis is None:
                issueid = annchk['IssueID']
            elif annchk is None:
                issueid = chkthis['IssueID']
            else:
                #if issue number exists in issues and annuals for given series, break down by year.
                #get pulldate.
                pullcomp = pulldate[:4]
                isscomp = chkthis['ReleaseDate'][:4]
                anncomp = annchk['ReleaseDate'][:4]
                logger.info(module + ' Comparing :' + str(pullcomp) + ' to issdate: ' + str(isscomp) + ' to annyear: ' + str(anncomp))
                if int(pullcomp) == int(isscomp) and int(pullcomp) != int(anncomp):
                    issueid = chkthis['IssueID']
                elif int(pullcomp) == int(anncomp) and int(pullcomp) != int(isscomp):
                    issueid = annchk['IssueID']
                else:
                    if 'annual' in file.lower():
                        issueid = annchk['IssueID']
                    else:
                        logger.info(module + ' Unsure as to the exact issue this is. Not adding to the Reading list at this time.')
                        return
        read = mylar.readinglist.Readinglist(IssueID=issueid)
        read.addtoreadlist()
    return

def future_check():
    # this is the function that will check the futureupcoming table
    # for series that have yet to be released and have no CV data associated with it
    # ie. #1 issues would fall into this as there is no series data to poll against until it's released.
    # Mylar will look for #1 issues, and in finding any will do the following:
    # - check comicvine to see if the series data has been released and / or issue data
    # - will automatically import the series (Add A Series) upon finding match
    # - will then proceed to mark the issue as Wanted, then remove from the futureupcoming table
    # - will then attempt to download the issue(s) in question.

    # future to-do
    # specify whether you want to 'add a series (Watch For)' or 'mark an issue as a one-off download'.
    # currently the 'add series' option in the futurepulllist will attempt to add a series as per normal.
    myDB = db.DBConnection()
    chkfuture = myDB.select("SELECT * FROM futureupcoming WHERE IssueNumber='1' OR IssueNumber='0'") #is not NULL")
    if chkfuture is None:
        logger.info("There are not any series on your future-list that I consider to be a NEW series")
    else:
        cflist = []
        #load in the values on an entry-by-entry basis into a tuple, so that we can query the sql clean again.
        for cf in chkfuture:
            cflist.append({"ComicName":   cf['ComicName'],
                           "IssueDate":   cf['IssueDate'],
                           "IssueNumber": cf['IssueNumber'],   #this should be all #1's as the sql above limits the hits.
                           "Publisher":   cf['Publisher'],
                           "Status":      cf['Status']})
        logger.fdebug('cflist: ' + str(cflist))
        #now we load in
        if len(cflist) == 0:
            logger.info('No series have been marked as being on auto-watch.')
        else:
            logger.info('I will be looking to see if any information has been released for ' + str(len(cflist)) + ' series that are NEW series')
            #limit the search to just the 'current year' since if it's anything but a #1, it should have associated data already.
            #limittheyear = []
            #limittheyear.append(cf['IssueDate'][-4:])
            search_results = []

            for ser in cflist:
                matched = False
                theissdate = ser['IssueDate'][-4:]
                if not theissdate.startswith('20'):
                    theissdate = ser['IssueDate'][:4]
                logger.info('looking for new data for ' + ser['ComicName'] + '[#' + str(ser['IssueNumber']) + '] (' + str(theissdate) + ')')
                searchresults = mb.findComic(ser['ComicName'], mode='pullseries', issue=ser['IssueNumber'], limityear=theissdate)
                if len(searchresults) > 0:
                    if len(searchresults) > 1:
                        logger.info('More than one result returned - this may have to be a manual add, but I\'m going to try to figure it out myself first.')
                    matches = []
                    logger.fdebug('Publisher of series to be added: ' + str(ser['Publisher']))
                    for sr in searchresults:
                        logger.fdebug('Comparing ' + sr['name'] + ' - to - ' + ser['ComicName'])
                        tmpsername = re.sub('[\'\*\^\%\$\#\@\!\/\,\.\:\(\)]', '', ser['ComicName']).strip()
                        tmpsrname = re.sub('[\'\*\^\%\$\#\@\!\/\,\.\:\(\)]', '', sr['name']).strip()
                        tmpsername = re.sub('\-', '', tmpsername)
                        if tmpsername.lower().startswith('the '):
                            tmpsername = re.sub('the ', '', tmpsername.lower()).strip()
                        else:
                            tmpsername = re.sub(' the ', '', tmpsername.lower()).strip()
                        tmpsrname = re.sub('\-', '', tmpsrname)
                        if tmpsrname.lower().startswith('the '):
                            tmpsrname = re.sub('the ', '', tmpsrname.lower()).strip()
                        else:
                            tmpsrname = re.sub(' the ', '', tmpsrname.lower()).strip()

                        tmpsername = re.sub(' and ', '', tmpsername.lower()).strip()
                        tmpsername = re.sub(' & ', '', tmpsername.lower()).strip()
                        tmpsrname = re.sub(' and ', '', tmpsrname.lower()).strip()
                        tmpsrname = re.sub(' & ', '', tmpsrname.lower()).strip()

                        #append the cleaned-up name to get searched later against if necessary.
                        search_results.append({'name':    tmpsrname,
                                               'comicid':  sr['comicid']})

                        tmpsername = re.sub('\s', '', tmpsername).strip()
                        tmpsrname = re.sub('\s', '', tmpsrname).strip()

                        logger.fdebug('Comparing modified names: ' + tmpsrname + ' - to - ' + tmpsername)
                        if tmpsername.lower() == tmpsrname.lower():
                            logger.fdebug('Name matched successful: ' + sr['name'])
                            if str(sr['comicyear']) == str(theissdate):
                                logger.fdebug('Matched to : ' + str(theissdate))
                                matches.append(sr)

                    if len(matches) == 1:
                        logger.info('Narrowed down to one series as a direct match: ' + matches[0]['name'] + '[' + str(matches[0]['comicid']) + ']')
                        cid = matches[0]['comicid']
                        matched = True
                    else:
                        logger.info('Unable to determine a successful match at this time (this is still a WIP so it will eventually work). Not going to attempt auto-adding at this time.')
                        catch_words = ('the', 'and', '&', 'to')
                        for pos_match in search_results:
                            logger.info(pos_match)
                            length_match = len(pos_match['name']) / len(ser['ComicName'])
                            logger.fdebug('length match differential set for an allowance of 20%')
                            logger.fdebug('actual differential in length between result and series title: ' + str((length_match * 100)-100) + '%')
                            if ((length_match * 100)-100) > 20:
                                logger.fdebug('there are too many extra words to consider this as match for the given title. Ignoring this result.') 
                                continue
                            new_match = pos_match['name'].lower()
                            split_series = ser['ComicName'].lower().split()
                            for cw in catch_words:
                                for x in new_match.split():
                                    #logger.fdebug('comparing x: ' + str(x) + ' to cw: ' + str(cw)) 
                                    if x == cw:
                                        new_match = re.sub(x, '', new_match)

                            split_match = new_match.split()
                            word_match = 0
                            i = 0
                            for ss in split_series:
                                try:
                                    matchword = split_match[i].lower()
                                except:
                                    break

                                if any([x == matchword for x in catch_words]):
                                    #logger.fdebug('[MW] common word detected of : ' + matchword)
                                    word_match+=.5
                                elif any([cw == ss for cw in catch_words]):
                                    #logger.fdebug('[CW] common word detected of : ' + matchword)
                                    word_match+=.5
                                else:
                                    try:
                                        #will return word position in string.
                                        #logger.fdebug('word match to position found in both strings at position : ' + str(split_match.index(ss)))
                                        if split_match.index(ss) == split_series.index(ss):
                                            word_match+=1
                                    except ValueError:
                                        break
                                i+=1                                
                            logger.fdebug('word match score of : ' + str(word_match) + ' / ' + str(len(split_series)))
                            if word_match == len(split_series) or (word_match / len(split_series)) > 80:
                                 logger.fdebug('[' + pos_match['name'] + '] considered a match - word matching percentage is greater than 80%. Attempting to auto-add series into watchlist.')
                                 cid = pos_match['comicid']
                                 matched = True                

                if matched:
                    #we should probably load all additional issues for the series on the futureupcoming list that are marked as Wanted and then
                    #throw them to the importer as a tuple, and once imported the import can run the additional search against them.
                    #now we scan for additional issues of the same series on the upcoming list and mark them accordingly.
                    chkthewanted = []
                    chkwant = myDB.select("SELECT * FROM futureupcoming WHERE ComicName=? AND IssueNumber != '1' AND Status='Wanted'", [ser['ComicName']])
                    if chkwant is None:
                        logger.info('No extra issues to mark at this time for ' + ser['ComicName'])
                    else:
                        for chk in chkwant:
                            chkthewanted.append({"ComicName":   chk['ComicName'],
                                                 "IssueDate":   chk['IssueDate'],
                                                 "IssueNumber": chk['IssueNumber'],   #this should be all #1's as the sql above limits the hits.
                                                 "Publisher":   chk['Publisher'],
                                                 "Status":      chk['Status']})

                        logger.info('Marking ' + str(len(chkthewanted)) + ' additional issues as Wanted from ' + ser['ComicName'] + ' series as requested.')

                    future_check_add(cid, ser, chkthewanted, theissdate)

                else:
                    logger.info('No series information available as of yet for ' + ser['ComicName'] + '[#' + str(ser['IssueNumber']) + '] (' + str(theissdate) + ')')
                    continue

            logger.info('Finished attempting to auto-add new series.')
    return

def future_check_add(comicid, serinfo, chkthewanted=None, theissdate=None):
    #In order to not error out when adding series with absolutely NO issue data, we need to 'fakeup' some values
    #latestdate = the 'On sale' date from the futurepull-list OR the Shipping date if not available.
    #latestiss = the IssueNumber for the first issue (this should always be #1, but might change at some point)
    ser = serinfo
    if theissdate is None:
        theissdate = ser['IssueDate'][-4:]
        if not theissdate.startswith('20'):
            theissdate = ser['IssueDate'][:4]

    latestissueinfo = []
    latestissueinfo.append({"latestdate": ser['IssueDate'],
                            "latestiss":  ser['IssueNumber']})
    logger.fdebug('sending latestissueinfo from future as : ' + str(latestissueinfo))
    chktheadd = importer.addComictoDB(comicid, "no", chkwant=chkthewanted, latestissueinfo=latestissueinfo, calledfrom="futurecheck")

    if chktheadd != 'Exists':
       logger.info('Sucessfully imported ' + ser['ComicName'] + ' (' + str(theissdate) + ')')

    myDB = db.DBConnection()
    myDB.action('DELETE from futureupcoming WHERE ComicName=?', [ser['ComicName']])
    logger.info('Removed ' + ser['ComicName'] + ' (' + str(theissdate) + ') from the future upcoming list as it is now added.')

    return

