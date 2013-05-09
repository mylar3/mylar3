#!/usr/bin/env python

import os
import sys
import lib.feedparser as feedparser
#import feedparser
import re
import logger
import mylar
import unicodedata


def Startit(searchName, searchIssue, searchYear, ComicVersion):
    #searchName = "Uncanny Avengers"
    #searchIssue = "01"
    #searchYear = "2012"
    #clean up searchName due to webparse.
    searchName = searchName.replace("%20", " ")
    if "," in searchName:
        searchName = searchName.replace(",", "")
    logger.fdebug("name:" + str(searchName))
    logger.fdebug("issue:" + str(searchIssue))
    logger.fdebug("year:" + str(searchYear))
    splitSearch = searchName.split(" ")
    joinSearch = "+".join(splitSearch)+"+"+searchIssue
    searchIsOne = "0"+searchIssue
    searchIsTwo = "00"+searchIssue

    if "-" in searchName:
        searchName = searchName.replace("-", '((\\s)?[-:])?(\\s)?')

    regexName = searchName.replace(" ", '((\\s)?[-:])?(\\s)?')


    if mylar.USE_MINSIZE:
        size_constraints = "minsize=" + str(mylar.MINSIZE)
    else:
        size_constraints = "minsize=10"

    if mylar.USE_MAXSIZE:
        size_constraints = size_constraints + "&maxsize=" + str(mylar.MAXSIZE)

    if mylar.USENET_RETENTION != None:
        max_age = "&age=" + str(mylar.USENET_RETENTION)

    feed = feedparser.parse("http://nzbindex.nl/rss/alt.binaries.comics.dcp/?sort=agedesc&" + str(size_constraints) + str(max_age) + "&dq=%s&max=50&more=1" %joinSearch)

    totNum = len(feed.entries)

    keyPair = {}
    regList = []
    entries = []
    mres = {}
    countUp = 0

    logger.fdebug(str(totNum) + " results")

    while countUp < totNum:
 	urlParse = feed.entries[countUp].enclosures[0]
	#keyPair[feed.entries[countUp].title] = feed.entries[countUp].link
	keyPair[feed.entries[countUp].title] = urlParse["href"]

	countUp=countUp+1


    # thanks to SpammyHagar for spending the time in compiling these regEx's!

    regExTest=""

    regEx = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, searchYear)
    regExOne = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, searchYear)

    #Sometimes comics aren't actually published the same year comicVine says - trying to adjust for these cases
    regExTwo = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear)+1)
    regExThree = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear)-1)
    regExFour = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear)+1)
    regExFive = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear)-1)

    regexList=[regEx, regExOne, regExTwo, regExThree, regExFour, regExFive]

    for title, link in keyPair.items():
        #print("titlesplit: " + str(title.split("\"")))
        splitTitle = title.split("\"")

        for subs in splitTitle:
#        print(title)
            regExCount = 0
            if len(subs) > 10:
                #Looping through dictionary to run each regEx - length + regex is determined by regexList up top.
                while regExCount < len(regexList):
                    regExTest = re.findall(regexList[regExCount], subs, flags=re.IGNORECASE)
                    regExCount = regExCount +1
                    if regExTest:   
                        logger.fdebug(title)
                        entries.append({
                                  'title':   subs,
                                  'link':    str(link)
                                  })
              
    if len(entries) >= 1:
        mres['entries'] = entries
        return mres 
#       print("Title: "+regList[0])
#       print("Link: "+keyPair[regList[0]])        
    else:
        logger.fdebug("No Results Found")
        return "no results"
