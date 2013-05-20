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

import mylar 
from mylar import db, updater, helpers, logger

def pullit(forcecheck=None):
    myDB = db.DBConnection()
    popit = myDB.select("SELECT count(*) FROM sqlite_master WHERE name='weekly' and type='table'")
    if popit:
        try:
            pull_date = myDB.action("SELECT SHIPDATE from weekly").fetchone()
            logger.info(u"Weekly pull list present - checking if it's up-to-date..")
            if (pull_date is None):
                pulldate = '00000000'
            else:
                pulldate = pull_date['SHIPDATE']
        except (sqlite3.OperationalError, TypeError),msg:
            conn=sqlite3.connect(mylar.DB_FILE)
            c=conn.cursor()
            logger.info(u"Error Retrieving weekly pull list - attempting to adjust")
            c.execute('DROP TABLE weekly')    
            c.execute('CREATE TABLE IF NOT EXISTS weekly (SHIPDATE text, PUBLISHER text, ISSUE text, COMIC VARCHAR(150), EXTRA text, STATUS text, ComicID text)')
            pulldate = '00000000'
            logger.fdebug(u"Table re-created, trying to populate")
    else:
        logger.info(u"No pullist found...I'm going to try and get a new list now.")
        pulldate = '00000000'
    if pulldate is None: pulldate = '00000000'
    PULLURL = 'http://www.previewsworld.com/shipping/newreleases.txt'
    #PULLURL = 'http://www.previewsworld.com/Archive/GetFile/1/1/71/994/081512.txt'

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
              'NEW PTG',
              'POSTER',
              'COMBO PACK']

    # this checks for the following lists
    # first need to only look for checkit variables
    checkit=['COMICS',
             'IDW PUBLISHING',
             'MAGAZINES',
             'MERCHANDISE']

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

    pub = "COMICS"
    prevcomic = ""
    previssue = ""

    #newtxtfile header info ("SHIPDATE\tPUBLISHER\tISSUE\tCOMIC\tEXTRA\tSTATUS\n")
    #STATUS denotes default status to be applied to pulllist in Mylar (default = Skipped)
    newrl = mylar.CACHE_DIR + "/newreleases.txt"
    f = urllib.urlretrieve(PULLURL, newrl)
#    local_file = open(newrl, "wb")
#    local_file.write(f.read())
#    local_file.close

    newfl = mylar.CACHE_DIR + "/Clean-newreleases.txt"
    newtxtfile = open(newfl, 'wb')

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
                    #print ("shipdate: " + str(shipdaterep))
                    #print ("today: " + str(pulldate))
                    if pulldate == shipdaterep:
                        logger.info(u"No new pull-list available - will re-check again in 24 hours.")
                        pullitcheck()
                        mylar.PULLNEW = 'no'
                        return
                    else:
                        logger.info(u"Preparing to update to the new listing.")
                break    
        else:
            mylar.PULLNEW = 'yes'
            for yesyes in checkit:
                if yesyes in i:
                    if format(str(yesyes)) == 'COMICS':
                        for chkchk in checkit2:
                            flagged = "no"
                            if chkchk in i:
                                bl = i.split()
                                blchk = str(bl[0]) + " " + str(bl[1])
                                if chkchk in blchk:
                                    pub = format(str(chkchk)) + " COMICS"
                                    #print (pub)
                                    break
                            else:
                                if i.find("COMICS") < 1 and "GRAPHIC NOVELS" in i:
                                    pub = "COMICS"
                                    #print (pub)
                                    break 
                                elif i.find("COMICS") > 12:
                                    #print ("comics word found in comic title")
                                    flagged = "yes"                    
                                    break
                    else:
                        pub = format(str(yesyes))
                        #print (pub)
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
                            issue = issname[n]
                            if 'ongoing' not in issname[n-1].lower() and '(vu)' not in issname[n-1].lower():
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
                    #print ("Comicname: " + str(comicnm) )
                    #get remainder
                    comicrm = issname[comicend +2]
                    if '$' in comicrm:
                        comicrm="None"
                    n = (comicend + 3)
                    while (n < issnamec):
                        if '$' in (issname[n]):
                            break
                        comicrm = str(comicrm) + " " + str(issname[n])
                        n+=1
                    #print ("Comic Extra info: " + str(comicrm) )
                    #print ("ship: " + str(shipdate))
                    #print ("pub: " + str(pub))
                    #print ("issue: " + str(issue))
                    #--let's make sure we don't wipe out decimal issues ;)
                    if '.' in issue:
                        issue_decimal = re.compile(r'[^\d.]+')
                        issue = issue_decimal.sub('', str(issue))
                    else: issue = re.sub('#','', issue)                                       
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
                            if "ONE" in issue and "SHOT" in issname[n+1]: issue = "OS"
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
                #--start duplicate comic / issue chk
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
    logger.info(u"Populating the NEW Weekly Pull list into Mylar.")
    newtxtfile.close()

    mylardb = os.path.join(mylar.DATA_DIR, "mylar.db")

    connection = sqlite3.connect(str(mylardb))
    cursor = connection.cursor()

    cursor.executescript('drop table if exists weekly;')

    cursor.execute("CREATE TABLE IF NOT EXISTS weekly (SHIPDATE, PUBLISHER text, ISSUE text, COMIC VARCHAR(150), EXTRA text, STATUS text, ComicID text);")
    connection.commit()


    csvfile = open(newfl, "rb")
    creader = csv.reader(csvfile, delimiter='\t')
    t=1

    for row in creader:
        if "MERCHANDISE" in row: break
        if "MAGAZINES" in row: break
        if "BOOK" in row: break
        #print (row)
        try:
            logger.debug("Row: %s" % row)
            cursor.execute("INSERT INTO weekly VALUES (?,?,?,?,?,?,null);", row)
        except Exception, e:
            #print ("Error - invald arguments...-skipping")
            pass
        t+=1
    csvfile.close()
    connection.commit()
    connection.close()
    logger.info(u"Weekly Pull List successfully loaded.")
    #let's delete the files
    pullpath = str(mylar.CACHE_DIR) + "/"
    os.remove( str(pullpath) + "Clean-newreleases.txt" )
    os.remove( str(pullpath) + "newreleases.txt" )
    pullitcheck(forcecheck=forcecheck)

def pullitcheck(comic1off_name=None,comic1off_id=None,forcecheck=None):
    logger.info(u"Checking the Weekly Releases list for comics I'm watching...")
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
    w = 0
    tot = 0
    chkout = []
    watchfnd = []
    watchfndiss = []
    watchfndextra = []

    #print ("----------WATCHLIST--------")
    a_list = []
    b_list = []
    comicid = []

    mylardb = os.path.join(mylar.DATA_DIR, "mylar.db")

    con = sqlite3.connect(str(mylardb))

    with con:

        cur = con.cursor()
        # if it's a one-off check (during an add series), load the comicname here and ignore below.
        if comic1off_name:
            logger.fdebug("this is a one-off" + str(comic1off_name))
            lines.append(comic1off_name.strip())
            unlines.append(comic1off_name.strip())
            comicid.append(comic1off_id)
            w = 1            
        else:
            #let's read in the comic.watchlist from the db here
            cur.execute("SELECT ComicID, ComicName, ComicYear, ComicPublisher, ComicPublished, LatestDate from comics")
            while True:
                watchd = cur.fetchone()
                #print ("watchd: " + str(watchd))
                if watchd is None:
                    break
                if 'Present' in watchd[4] or (helpers.now()[:4] in watchd[4]):
                 # this gets buggered up when series are named the same, and one ends in the current
                 # year, and the new series starts in the same year - ie. Avengers
                 # lets' grab the latest issue date and see how far it is from current
                 # anything > 45 days we'll assume it's a false match ;)
                    #logger.fdebug("ComicName: " + watchd[1])
                    latestdate = watchd[5]
                    #logger.fdebug("latestdate:  " + str(latestdate))
                    c_date = datetime.date(int(latestdate[:4]),int(latestdate[5:7]),1)
                    n_date = datetime.date.today()
                    #logger.fdebug("c_date : " + str(c_date) + " ... n_date : " + str(n_date))
                    recentchk = (n_date - c_date).days
                    #logger.fdebug("recentchk: " + str(recentchk) + " days")
                    #logger.fdebug(" ----- ")
                    if recentchk < 55:
                        # let's not even bother with comics that are in the Present.
                        a_list.append(watchd[1])
                        b_list.append(watchd[2])
                        comicid.append(watchd[0])
                        pubdate.append(watchd[4])
                        #print ( "Comic:" + str(a_list[w]) + " Year: " + str(b_list[w]) )
                        #if "WOLVERINE AND THE X-MEN" in str(a_list[w]): a_list[w] = "WOLVERINE AND X-MEN"
                        lines.append(a_list[w].strip())
                        unlines.append(a_list[w].strip())
                        llen.append(a_list[w].splitlines())
                        ccname.append(a_list[w].strip())
                        tmpwords = a_list[w].split(None)
                        ltmpwords = len(tmpwords)
                        ltmp = 1
                        w+=1
        cnt = int(w-1)
        cntback = int(w-1)
        kp = []
        ki = []
        kc = []
        otot = 0

        logger.fdebug("You are watching for: " + str(w) + " comics")
        #print ("----------THIS WEEK'S PUBLISHED COMICS------------")
        if w > 0:
            while (cnt > -1):
                lines[cnt] = lines[cnt].upper()
                #llen[cnt] = str(llen[cnt])
                #logger.fdebug("looking for : " + str(lines[cnt]))
                sqlsearch = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\'\?\@]', ' ', lines[cnt])
                sqlsearch = re.sub(r'\s', '%', sqlsearch) 
                if 'THE' in sqlsearch: sqlsearch = re.sub('THE', '', sqlsearch)
                if '+' in sqlsearch: sqlsearch = re.sub('\+', '%PLUS%', sqlsearch)
                #logger.fdebug("searchsql: " + str(sqlsearch))
                weekly = myDB.select('SELECT PUBLISHER, ISSUE, COMIC, EXTRA, SHIPDATE FROM weekly WHERE COMIC LIKE (?)', [sqlsearch])
                #cur.execute('SELECT PUBLISHER, ISSUE, COMIC, EXTRA, SHIPDATE FROM weekly WHERE COMIC LIKE (?)', [lines[cnt]])
                for week in weekly:
                    if week == None:
                        break
                    for nono in not_t:
                        if nono in week['PUBLISHER']:
                            #logger.fdebug("nono present")
                            break
                        if nono in week['ISSUE']:
                            #logger.fdebug("graphic novel/tradeback detected..ignoring.")
                            break
                        for nothere in not_c:
                            if nothere in week['EXTRA']:
                                #logger.fdebug("nothere present")
                                break
                            else:
                                comicnm = week['COMIC']
                                #here's the tricky part, ie. BATMAN will match on
                                #every batman comic, not exact
                                #logger.fdebug("comparing" + str(comicnm) + "..to.." + str(unlines[cnt]).upper())

                                #-NEW-
                                # strip out all special characters and compare
                                watchcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\'\?\@]', '', unlines[cnt])
                                comicnm = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\'\?\@]', '', comicnm)
                                watchcomic = re.sub(r'\s', '', watchcomic)
                                comicnm = re.sub(r'\s', '', comicnm)
                                #logger.fdebug("Revised_Watch: " + watchcomic)
                                #logger.fdebug("ComicNM: " + comicnm)
                                if 'THE' in watchcomic.upper():
                                    modwatchcomic = re.sub('THE', '', watchcomic.upper())
                                    modcomicnm = re.sub('THE', '', comicnm)
                                else:
                                    modwatchcomic = watchcomic
                                    modcomicnm = comicnm
                                #thnx to A+X for this...
                                if '+' in watchcomic:
                                    logger.fdebug("+ detected...adjusting.")
                                    #logger.fdebug("comicnm:" + comicnm)
                                    #logger.fdebug("watchcomic:" + watchcomic)
                                    modwatchcomic = re.sub('\+', 'PLUS', modwatchcomic)
                                    #logger.fdebug("modcomicnm:" + modcomicnm)
                                    #logger.fdebug("modwatchcomic:" + modwatchcomic)
                                if comicnm == watchcomic.upper() or modcomicnm == modwatchcomic.upper():
                                    logger.fdebug("matched on:" + str(comicnm) + "..." + str(watchcomic).upper())
                                    pass
                                elif ("ANNUAL" in week['EXTRA']):
                                    pass
                                    #print ( row[3] + " matched on ANNUAL")
                                else:
                                    break
                                if ("NA" not in week['ISSUE']) and ("HC" not in week['ISSUE']):
                                    if ("COMBO PACK" not in week['EXTRA']) and ("2ND PTG" not in week['EXTRA']) and ("3RD PTG" not in week['EXTRA']):
                                        otot+=1
                                        dontadd = "no"
                                        if dontadd == "no":
                                            #print (row[0], row[1], row[2])
                                            tot+=1
                                            #kp.append(row[0])
                                            #ki.append(row[1])
                                            #kc.append(comicnm)
                                            if ("ANNUAL" in week['EXTRA']):
                                                watchfndextra.append("annual")
                                            else:
                                                watchfndextra.append("none")
                                            watchfnd.append(comicnm)
                                            watchfndiss.append(week['ISSUE'])
                                            ComicID = comicid[cnt]
                                            if not mylar.CV_ONLY:
                                                ComicIssue = str(watchfndiss[tot -1] + ".00")
                                            else:
                                                ComicIssue = str(watchfndiss[tot -1])
                                            ComicDate = str(week['SHIPDATE'])
                                            ComicName = str(unlines[cnt])
                                            logger.fdebug("Watchlist hit for : " + ComicName + " ISSUE: " + str(watchfndiss[tot -1]))
                                            # here we add to comics.latest
                                            updater.latest_update(ComicID=ComicID, LatestIssue=ComicIssue, LatestDate=ComicDate)
                                            # here we add to upcoming table...
                                            statusupdate = updater.upcoming_update(ComicID=ComicID, ComicName=ComicName, IssueNumber=ComicIssue, IssueDate=ComicDate, forcecheck=forcecheck)
                                            # here we update status of weekly table...
                                            if statusupdate is not None:
                                                cstatus = statusupdate['Status']
                                                cstatusid = statusupdate['ComicID']
                                            else:
                                                cstatus = None
                                                cstatusid = None
                                            updater.weekly_update(ComicName=week['COMIC'], IssueNumber=ComicIssue, CStatus=cstatus, CID=cstatusid)
                                            break
                                        break
                        break
                cnt-=1
        #print ("-------------------------")
        logger.fdebug("There are " + str(otot) + " comics this week to get!")
        #print ("However I've already grabbed " + str(btotal) )
        #print ("I need to get " + str(tot) + " comic(s)!" )
        logger.info(u"Finished checking for comics on my watchlist.")
    #con.close()
    return
