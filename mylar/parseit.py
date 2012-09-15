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


from bs4 import BeautifulSoup
import urllib2
import re
import helpers
import logger
from decimal import Decimal
from HTMLParser import HTMLParseError

def MysterBinScrape(comsearch):
        searchterms = str(comsearch)
        # subsetting the results by cbr/cbz will allow for better control.
        # min/max size should be set or else *.part01's and group collections will be parsed
        #  and will result in errors all over & no hits.
        # min is set low enough to filter out cover-only releases and the like
        # max is set high enough to inlude everything but collections/groups of cbr/cbz which confuse us.
        # minsize = 9mb  maxsize = 75mb  (for now)
	input = 'http://www.mysterbin.com/advsearch?q=' + str(searchterms) + '&match=normal&minSize=9&maxSize=75&group=alt.binaries.comics.dcp&maxAge=1269&complete=2'
	#print (input)
	response = urllib2.urlopen ( input )
	try:
            soup = BeautifulSoup ( response )
        except HTMLParseError:
            logger.info(u"Unable to decipher using Experimental Search. Parser problem.")            
            return "no results"
	    #print (soup)
	cnt = len(soup.findAll("input", {"class" : "check4nzb"}))
        logger.info(u"I found " + str(cnt) + " results doing my search...now I'm going to analyze the results.")
	#print (str(cnt) + " results")
        if cnt == 0: return "no results"
	resultName = []
	resultComic = []
	n = 0
        mres = {}
        entries = []
	while ( n < cnt ):
	    resultp = soup.findAll("input", {"class" : "check4nzb"})[n]
	    nzblink = str("http://www.mysterbin.com/nzb?c=" + resultp['value'])
	    #print ( "nzb-link: " + str(nzblink) )

	    subtxt3 = soup.findAll("div", {"class" : "divc"})[n]
	    subres = subtxt3.find("span", {"style" : ""})
	    blah = subres.find('a').contents[2]
	    blah = re.sub("</?[^\W].{0,10}?>", "", str(blah))
            #print ("Blah:" + str(blah))
	    nook=3
	    totlink = str(blah)
	    while ('"' not in blah):               
	        blah = subres.find('a').contents[nook]
	        if '"</a>' in blah:
                    findyenc = blah.find('"')
                    blah = blah[findyenc:]
                    #break
                #print ("Blah:" + str(blah))
	        goo = re.sub("</?[^\W].{0,10}?>", "", str(blah))
	        #print ("goo:" + str(goo))
    	    	totlink = totlink + str(goo)
    	    	#print (nook, blah)
   	   	nook+=1

            #print ("exit mainloop")
            #print (str(nzblink))
            #print (str(totlink))
            entries.append({
                'title':   str(totlink),
                'link':    str(nzblink)
                })
            #print (entries[n])
            mres['entries'] = entries
    	    n+=1
    	#print ("FINAL: " + str(totlink))
        return mres    

def GCDScraper(ComicName, ComicYear, Total, ComicID):
    comicnm = ComicName
    comicyr = ComicYear
    comicis = Total
    comicid = ComicID
    #print ( "comicname: " + str(comicnm) )
    #print ( "comicyear: " + str(comicyr) )
    #print ( "comichave: " + str(comicis) )
    #print ( "comicid: " + str(comicid) )
    comicnm = re.sub(' ', '%20', comicnm)
    input = 'http://www.comics.org/series/name/' + str(comicnm) + '/sort/alpha/'
    response = urllib2.urlopen ( input )
    soup = BeautifulSoup ( response)

    cnt1 = len(soup.findAll("tr", {"class" : "listing_even"}))
    cnt2 = len(soup.findAll("tr", {"class" : "listing_odd"}))

    cnt = int(cnt1 + cnt2)

    #print (str(cnt) + " results")

    global resultPublished

    resultName = []
    resultID = []
    resultYear = []
    resultIssues = []
    resultURL = None
    n_odd = -1
    n_even = -1
    n = 0
    while ( n < cnt ):
        if n%2==0:
            n_even+=1
            resultp = soup.findAll("tr", {"class" : "listing_even"})[n_even]
        else:
            n_odd+=1
            resultp = soup.findAll("tr", {"class" : "listing_odd"})[n_odd]
        rtp = resultp('a')[1]
        resultName.append(helpers.cleanName(rtp.findNext(text=True)))
        #print ( "Comic Name: " + str(resultName[n]) )
        fip = resultp('a',href=True)[1]
        resultID.append(fip['href'])
        #print ( "ID: " + str(resultID[n]) )

        subtxt3 = resultp('td')[3]
        resultYear.append(subtxt3.findNext(text=True))
        resultYear[n] = resultYear[n].replace(' ','')
        subtxt4 = resultp('td')[4]
        resultIssues.append(helpers.cleanName(subtxt4.findNext(text=True)))
        resiss = resultIssues[n].find('issue')
        resiss = int(resiss)
        resultIssues[n] = resultIssues[n].replace('','')[:resiss]
        resultIssues[n] = resultIssues[n].replace(' ','')
        #print ( "Year: " + str(resultYear[n]) )
        #print ( "Issues: " + str(resultIssues[n]) )
        if resultName[n].lower() == str(ComicName).lower(): 
            #print ("n:" + str(n) + "...matched by name to Mylar!")
            #this has been seen in a few instances already, so trying to adjust.
            #when the series year is 2011, in gcd it might be 2012 due to publication
            #dates overlapping between Dec/11 and Jan/12. Let's accept a match with a 
            #1 year grace space, and then pull in the first issue to see the actual pub
            # date and if coincides with the other date..match it.
            if resultYear[n] == ComicYear or resultYear[n] == str(int(ComicYear)+1): 
                #print ("n:" + str(n) + "...matched by year to Mylar!")
                #print ( "Year: " + str(resultYear[n]) )
                #Occasionally there are discrepancies in comic count between
                #GCD and CV. 99% it's CV not updating to the newest issue as fast
                #as GCD does. Therefore, let's increase the CV count by 1 to get it
                #to match, any more variation could cause incorrect matching.
                #ie. witchblade on GCD says 159 issues, CV states 161.
                if resultIssues[n] == Total or resultIssues[n] == str(int(Total)+1): 
                    if resultIssues[n] == str(int(Total)+1):
                        issvariation = "yes"
                    else:
                        issvariation = "no"
                        #print ("n:" + str(n) + "...matched by issues to Mylar!")
                        #print ("complete match!...proceeding")
                    TotalIssues = resultIssues[n]
                    resultURL = str(resultID[n])
                    rptxt = resultp('td')[6]
                    resultPublished = rptxt.findNext(text=True)
                    #print ("Series Published: " + str(resultPublished))
                    break
                
        n+=1
    # it's possible that comicvine would return a comic name incorrectly, or gcd
    # has the wrong title and won't match 100%...
    # (ie. The Flash-2011 on comicvine is Flash-2011 on gcd)
    if resultURL is None:
        if ComicName.startswith('The '):
            ComicName = ComicName[4:]
            return GCDScraper(ComicName, ComicYear, Total, ComicID)        
        if ':' in ComicName: 
            ComicName = re.sub(':', '', ComicName)
            return GCDScraper(ComicName, ComicYear, Total, ComicID)
        if 'and' in ComicName.lower():
            ComicName = ComicName.replace('and', '&')
            return GCDScraper(ComicName, ComicYear, Total, ComicID)
        return 'No Match'
    gcdinfo = {}
    gcdchoice = []

    input2 = 'http://www.comics.org' + str(resultURL) + 'details/'
    resp = urllib2.urlopen ( input2 )
    soup = BeautifulSoup ( resp )

    #for newer comics, on-sale date has complete date...
    #for older comics, pub.date is to be used

    type = soup.find(text=' On-sale date ')
    if type:
        #print ("on-sale date detected....adjusting")
        datetype = "on-sale"
    else:
        #print ("pub date defaulting")
        datetype = "pub"

    cnt1 = len(soup.findAll("tr", {"class" : "row_even_False"}))
    cnt2 = len(soup.findAll("tr", {"class" : "row_even_True"}))

    cnt = int(cnt1 + cnt2)

    #print (str(cnt) + " Issues in Total (this may be wrong due to alternate prints, etc")

    n_odd = -1
    n_even = -1
    n = 0
    PI = "1.00"
    altcount = 0
    while ( n < cnt ):       
        if n%2==0:
            n_odd+=1
            parsed = soup.findAll("tr", {"class" : "row_even_False"})[n_odd]
            ntype = "odd"
        else:
            n_even+=1
            ntype = "even"
            parsed = soup.findAll("tr", {"class" : "row_even_True"})[n_even]
        subtxt3 = parsed.find("a")
        ParseIssue = subtxt3.findNext(text=True)
        isslen = ParseIssue.find(' ')
        #if 'isslen' exists, it means that it's an alternative cover.
        #however, if ONLY alternate covers exist of an issue it won't work.
        #let's use the FIRST record, and ignore all other covers for the given issue.
        isschk = ParseIssue[:isslen]
        if '.' in isschk:
            isschk_find = isschk.find('.')
            isschk_b4dec = isschk[:isschk_find]
            isschk_decval = isschk[isschk_find+1:]
        else:
            isschk_decval = ".00"

        if isslen > 0:
            isschk = ParseIssue[:isslen]
            isschk2 = str(isschk) + isschk_decval
            ParseIssue = str(isschk2)
            #print ("Alt.cover found = " + str(isschk2))
            if str(PI) == str(isschk2):
                if altcount == 0:
                    #this handles the first occurance..                    print ("Fist occurance detected - " + str(isschk))
                    ParseIssue = str(isschk2)
                    PI = str(isschk2)
                    altcount = 1
                else:
                    #print ("Using only first record for issue - ignoring further alternate matches")
                    ParseIssue = "this is wrong"
                    altcount+=1
            else:
                altcount = 1
                ParseIssue = str(isschk) + isschk_decval
        else:
            ParseIssue = ParseIssue + isschk_decval
            #print ("no alt.cover detected for - " + str(ParseIssue))
            altcount = 1
        if (altcount == 1):
            # in order to get the compare right, let's decimialize the string to '.00'.
            gcdinfo['ComicIssue'] = ParseIssue
            #print ( "Issue : " + str(ParseIssue) )
            #^^ will retrieve issue
            #if datetype == "on-sale":
            subtxt1 = parsed('td')[2]
            ParseDate = subtxt1.findNext(text=True)
            pdlen = len(ParseDate)
            #print ("Parsed Date length: " + str(pdlen))
            if len(ParseDate) < 7:
                subtxt1 = parsed.find("td")
                ParseDate = subtxt1.findNext(text=True)               
                if ParseDate == ' ':
                    ParseDate = "0000-00-00"
            ParseDate = ParseDate.replace(' ','')
            gcdinfo['ComicDate'] = ParseDate
            #print ( "Date : " + str(ParseDate) )
            #^^ will retrieve date #


            gcdchoice.append({
                'GCDid':                ComicID,
                'GCDIssue':             gcdinfo['ComicIssue'],
                'GCDDate':              gcdinfo['ComicDate']
                })

            gcdinfo['gcdchoice'] = gcdchoice
            PI = ParseIssue
        #else:
            # -- this needs a rework --
            # if issue only has alternative covers on comics.org, it won't match
            # and will cause the script to return a cannot retrieve..
            #compare previous issue to current issue (to help with alt.cover count)
         #   PI = ParseIssue
         #   altcount+=1
         #   print ("alternate issue - ignoring")
        #altcount = 0
        n+=1
    gcdinfo['gcdvariation'] = issvariation
    gcdinfo['totalissues'] = TotalIssues
    return gcdinfo
        ## -- end (GCD) -- ##
