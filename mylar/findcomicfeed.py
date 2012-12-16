#!/usr/bin/env python

import os
import sys
import lib.feedparser as feedparser
#import feedparser
import re

def Startit(searchName, searchIssue, searchYear):
    #searchName = "Uncanny Avengers"
    #searchIssue = "01"
    #searchYear = "2012"
    #clean up searchName due to webparse.
    searchName = searchName.replace("%20", " ")
    print "name:"+searchName
    print "issue:"+searchIssue
    print "year:"+searchYear
#    searchName = input("Enter a Title: ")
#    searchIssue =input("Enter an Issue #: ")
#    searchYear = input("Enter a year: ")
    splitSearch = searchName.split(" ")
    joinSearch = "+".join(splitSearch)+"+"+searchIssue
    searchIsOne = "0"+searchIssue
    searchIsTwo = "00"+searchIssue


    feed = feedparser.parse("http://nzbindex.nl/rss/alt.binaries.comics.dcp/?sort=agedesc&minsize=10&dq=%s&max=25&more=1" %joinSearch)

    totNum = len(feed.entries)

    keyPair = {}
    regList = []
    entries = []
    mres = {}
    countUp = 0

    print (str(totNum))+" results"

    while countUp < totNum:
 	urlParse = feed.entries[countUp].enclosures[0]
	#keyPair[feed.entries[countUp].title] = feed.entries[countUp].link
	keyPair[feed.entries[countUp].title] = urlParse["href"]

	countUp=countUp+1


    #print(keyPair)
    # keyPair.keys()

    #for title, link in keyPair.items():
    #	print(title, link)




    for title, link in keyPair.items():
	#print("titlesplit: " + str(title.split("\"")))
	splitTitle = title.split("\"")

	for subs in splitTitle:
		print("looking at: " + str(subs))
		regEx = re.findall("\\b%s\\b\\s*\\b%s\\b\\s*[(]\\b%s\\b[)]" %(searchName, searchIssue, searchYear), subs, flags=re.IGNORECASE)
		regExOne = re.findall("\\b%s\\b\\s*\\b%s\\b\\s*[(]\\b%s\\b[)]" %(searchName, searchIsOne, searchYear), subs, flags=re.IGNORECASE)
		regExTwo = re.findall("\\b%s\\b\\s*\\b%s\\b\\s*[(]\\b%s\\b[)]" %(searchName, searchIsTwo, searchYear), subs, flags=re.IGNORECASE)

		#print("regex: " + str(regEx))
		if regEx or regExOne or regExTwo:
			print("name: " + str(title))
                        print("sub: " + str(subs))
			print("-----")
			print("url: " + str(link))
			print("-----")
			#regList.append(title)
                        #regList.append(subs)
                        entries.append({
                                'title':   str(subs),
                                'link':    str(link)
                                })
              
    if len(entries) >= 1:
        mres['entries'] = entries
        return mres 
#       print("Title: "+regList[0])
#       print("Link: "+keyPair[regList[0]])        
    else:
        print("No Results Found")
        return "no results"
   

    #mres['entries'] = entries
    #return mres

