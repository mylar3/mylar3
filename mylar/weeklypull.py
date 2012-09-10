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

#from collections import Counter

import sys
import fileinput
import csv
import getopt
import sqlite3
import urllib
import os
import codecs
import time
import re

import mylar 
from mylar import db, updater, helpers, logger

def pullit():
    myDB = db.DBConnection()
    popit = myDB.select("SELECT * FROM sqlite_master WHERE name='weekly' and type='table'")
    if popit:
        pullold = myDB.action("SELECT * from weekly").fetchone()
        pulldate = pullold['SHIPDATE'] 
    else:
        logger.info(u"No pullist found...I'm going to try and get a new list now.")
        pulldate = '00000000'
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
               'New Releases']

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

    f = urllib.urlopen(PULLURL)
    
    newrl = mylar.CACHE_DIR + "/newreleases.txt"
    local_file = open(newrl, "wb")
    local_file.write(f.read())
    local_file.close

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
                if 'Shipping' in nono or 'New Releases' in nono:
                    shipdatechk = i.split()
                    if 'Shipping' in nono:
                        shipdate = shipdatechk[1]                
                    if 'New Releases' in nono:
                        shipdate = shipdatechk[3]
                    sdsplit = shipdate.split('/')
                    mo = sdsplit[0]
                    dy = sdsplit[1]
                    if len(mo) == 1: mo = "0" + sdsplit[0]
                    if len(dy) == 1: dy = "0" + sdsplit[1]
                    shipdate = sdsplit[2] + "-" + mo + "-" + dy
                    shipdaterep = shipdate.replace('-', '')
                    pulldate = pulldate.replace('-', '')
                    #print ("shipdate: " + str(shipdaterep))
                    #print ("today: " + str(pulldate))
                    if pulldate == shipdaterep:
                        logger.info(u"No new pull-list available - will re-check again in 24 hours.")
                        return
                break    
        else:
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
                            #print ("issue found : " + issname[n])
                            comicend = n - 1
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
                    issue = re.sub("\D", "", str(issue))
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
                    if issue == '': issue = 'NA'
                    if issue is None: issue = 'NA'
                    #find comicname
                    comicnm = issname[1]
                    n = 2
                    while (n < comicend + 1):
                        comicnm = comicnm + " " + issname[n]
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
    newtxtfile.close()

    connection = sqlite3.connect("mylar.db")
    cursor = connection.cursor()

    cursor.executescript('drop table if exists weekly;')

    cursor.execute("CREATE TABLE IF NOT EXISTS weekly (SHIPDATE, PUBLISHER text, ISSUE text, COMIC VARCHAR(150), EXTRA text, STATUS text);")
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
            cursor.execute("INSERT INTO weekly VALUES (?,?,?,?,?,?);", row)
        except Exception, e:
            #print ("Error - invald arguments...-skipping")
            pass
        t+=1
    csvfile.close()
    connection.commit()
    connection.close()
    #let's delete the files
    pullpath = str(mylar.PROG_DIR) + "/cache/"
    os.remove( str(pullpath) + "Clean-newreleases.txt" )
    os.remove( str(pullpath) + "newreleases.txt" )
    pullitcheck()

def pullitcheck():
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

    con = sqlite3.connect("mylar.db")

    with con:

        cur = con.cursor()
        #let's read in the comic.watchlist from the db here
        cur.execute("SELECT ComicID, ComicName, ComicYear, ComicPublisher from comics")
        while True:
            watchd = cur.fetchone()
            if watchd == None:
                break
            a_list.append(watchd[1])
            b_list.append(watchd[2])
            comicid.append(watchd[0])
            #print ( "Comic:" + str(a_list[w]) + " Year: " + str(b_list[w]) )
            if "WOLVERINE AND THE X-MEN" in str(a_list[w]): a_list[w] = "WOLVERINE AND X-MEN"
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
        #print ("You are watching for: " + str(w) + " comics")
        #print ("----------THIS WEEK'S PUBLISHED COMICS------------")
        if w > 0:
            while (cnt > -1):
                lines[cnt] = str(lines[cnt]).upper()
                llen[cnt] = str(llen[cnt])
                #print ("looking for : " + str(lines[cnt]))
                cur.execute('SELECT PUBLISHER, ISSUE, COMIC, EXTRA, SHIPDATE FROM weekly WHERE COMIC LIKE (?)', [lines[cnt]])
                while True:
                    row = cur.fetchone()
                    #print (row)
                    if row == None:
                        break
                    for nono in not_t:
                        if nono in row[1]:
                            #print ("nono present")
                            break
                        for nothere in not_c:
                            if nothere in row[3]:
                                #print ("nothere present")
                                break
                            else:
                                comicnm = row[2]
                                #here's the tricky part, ie. BATMAN will match on
                                #every batman comic, not exact
                                #print ("comparing" + str(comicnm) + "..to.." + str(unlines[cnt]).upper())
                                if str(comicnm) == str(unlines[cnt]).upper():
                                    #print ("matched on:")
                                    pass
                                elif ("ANNUAL" in row[3]):
                                    pass
                                    #print ( row[3] + " matched on ANNUAL")
                                else:
                                    #print ( row[2] + " not an EXACT match...")
                                    break
                                    break
                                if "WOLVERINE AND X-MEN" in str(comicnm):
                                    comicnm = "WOLVERINE AND THE X-MEN"
                                    #print ("changed wolvy")
                                if ("NA" not in row[1]) and ("HC" not in row[1]):
                                    if ("COMBO PACK" not in row[3]) and ("2ND PTG" not in row[3]) and ("3RD PTG" not in row[3]):
                                        otot+=1
                                        dontadd = "no"
                                        if dontadd == "no":
                                            #print (row[0], row[1], row[2])
                                            tot+=1
                                            kp.append(row[0])
                                            ki.append(row[1])
                                            kc.append(comicnm)
                                            if ("ANNUAL" in row[3]):
                                                watchfndextra.append("annual")
                                            else:
                                                watchfndextra.append("none")
                                            watchfnd.append(comicnm)
                                            watchfndiss.append(row[1])
                                            ComicID = comicid[cnt]
                                            ComicIssue = str(watchfndiss[tot -1] + ".00")
                                            ComicDate = str(row[4])
                                            ComicName = str(unlines[cnt])
                                            #print ("added: " + str(watchfnd[tot -1]) + " ISSUE: " + str(watchfndiss[tot -1]))
                                            # here we add to comics.latest
                                            updater.latest_update(ComicID=ComicID, LatestIssue=ComicIssue, LatestDate=ComicDate)
                                            # here we add to upcoming table...
                                            updater.upcoming_update(ComicID=ComicID, ComicName=ComicName, IssueNumber=ComicIssue, IssueDate=ComicDate)
                                            # here we update status of weekly table...
                                            updater.weekly_update(ComicName=comicnm)
                                            break
                                        break
                        break
                cnt-=1
        #print ("-------------------------")
        #print ("There are " + str(otot) + " comics this week to get!")
        #print ("However I've already grabbed " + str(btotal) )
        #print ("I need to get " + str(tot) + " comic(s)!" )

    con.close()
    return
