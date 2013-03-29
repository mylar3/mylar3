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


from bs4 import BeautifulSoup, UnicodeDammit 
import urllib2 
import re 
import helpers 
import logger 
import datetime 
import sys
from decimal import Decimal 
from HTMLParser import HTMLParseError
from time import strptime
import mylar

def GCDScraper(ComicName, ComicYear, Total, ComicID, quickmatch=None):
    NOWyr = datetime.date.today().year
    if datetime.date.today().month == 12:
        NOWyr = NOWyr + 1
        logger.fdebug("We're in December, incremented search Year to increase search results: " + str(NOWyr))
    comicnm = ComicName.encode('utf-8').strip()
    comicyr = ComicYear
    comicis = Total
    comicid = ComicID
    #print ( "comicname: " + str(comicnm) )
    #print ( "comicyear: " + str(comicyr) )
    #print ( "comichave: " + str(comicis) )
    #print ( "comicid: " + str(comicid) )
    comicnm_1 = re.sub('\+', '%2B', comicnm)
    comicnm = re.sub(' ', '+', comicnm_1)
    input = 'http://www.comics.org/search/advanced/process/?target=series&method=icontains&logic=False&order2=date&order3=&start_date=' + str(comicyr) + '-01-01&end_date=' + str(NOWyr) + '-12-31&series=' + str(comicnm) + '&is_indexed=None'
    response = urllib2.urlopen ( input )
    soup = BeautifulSoup ( response)
    cnt1 = len(soup.findAll("tr", {"class" : "listing_even"}))
    cnt2 = len(soup.findAll("tr", {"class" : "listing_odd"}))

    cnt = int(cnt1 + cnt2)

    #print (str(cnt) + " results")

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
        CleanComicName = re.sub('[\,\.\:\;\'\[\]\(\)\!\@\#\$\%\^\&\*\-\_\+\=\?\/]', '', comicnm)
        CleanComicName = re.sub(' ', '', CleanComicName).lower()
        CleanResultName = re.sub('[\,\.\:\;\'\[\]\(\)\!\@\#\$\%\^\&\*\-\_\+\=\?\/]', '', resultName[n])        
        CleanResultName = re.sub(' ', '', CleanResultName).lower()
        #print ("CleanComicName: " + str(CleanComicName))
        #print ("CleanResultName: " + str(CleanResultName))
        if CleanResultName == CleanComicName or CleanResultName[3:] == CleanComicName:
        #if resultName[n].lower() == helpers.cleanName(str(ComicName)).lower(): 
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
                if int(resultIssues[n]) == int(Total) or int(resultIssues[n]) == int(Total)+1 or (int(resultIssues[n])+1) == int(Total):
                    #print ("initial issue match..continuing.")
                    if int(resultIssues[n]) == int(Total)+1:
                        issvariation = "cv"
                    elif int(resultIssues[n])+1 == int(Total):
                        issvariation = "gcd"
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
    # this section is to account for variations in spelling, punctuation, etc/
    basnumbs = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12}
    if resultURL is None:
        #search for number as text, and change to numeric
        for numbs in basnumbs:
            #print ("numbs:" + str(numbs))
            if numbs in ComicName.lower():
                numconv = basnumbs[numbs]
                #print ("numconv: " + str(numconv))
                ComicNm = re.sub(str(numbs), str(numconv), ComicName.lower())
                #print ("comicname-reVISED:" + str(ComicNm))
                return GCDScraper(ComicNm, ComicYear, Total, ComicID)
                break
        if ComicName.lower().startswith('the '):
            ComicName = ComicName[4:]
            return GCDScraper(ComicName, ComicYear, Total, ComicID)        
        if ':' in ComicName: 
            ComicName = re.sub(':', '', ComicName)
            return GCDScraper(ComicName, ComicYear, Total, ComicID)
        if '-' in ComicName:
            ComicName = re.sub('-', ' ', ComicName)
            return GCDScraper(ComicName, ComicYear, Total, ComicID)
        if 'and' in ComicName.lower():
            ComicName = ComicName.replace('and', '&')
            return GCDScraper(ComicName, ComicYear, Total, ComicID)        
        if not quickmatch: return 'No Match'
    #vari_loop = 0
    if quickmatch == "yes":
        if resultURL is None: return 'No Match'
        else: return 'Match'
    return GCDdetails(comseries=None, resultURL=resultURL, vari_loop=0, ComicID=ComicID, TotalIssues=TotalIssues, issvariation=issvariation, resultPublished=resultPublished)


def GCDdetails(comseries, resultURL, vari_loop, ComicID, TotalIssues, issvariation, resultPublished):

    gcdinfo = {}
    gcdchoice = []
    gcount = 0
    i = 0
#    datemonth = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':$
#    #search for number as text, and change to numeric
#    for numbs in basnumbs:
#        #print ("numbs:" + str(numbs))
#        if numbs in ComicName.lower():
#            numconv = basnumbs[numbs]
#            #print ("numconv: " + str(numconv))


    if vari_loop > 1:
        resultPublished = "Unknown"

    if vari_loop == 99: vari_loop = 1

    while (i <= vari_loop):
        if vari_loop > 0:
            try:
                boong = comseries['comseries'][i]
            except IndexError:
                break
            resultURL = boong['comseriesID']
            ComicID = boong['comicid']
            TotalIssues+= int(boong['comseriesIssues'])
        else: 
            resultURL = resultURL
            # if we're here - it means it's a mismatched name.
            # let's pull down the publication date as it'll be blank otherwise
            inputMIS = 'http://www.comics.org' + str(resultURL)
            resp = urllib2.urlopen ( inputMIS )
#            soup = BeautifulSoup ( resp )
            try:
                soup = BeautifulSoup(urllib2.urlopen(inputMIS))
            except UnicodeDecodeError:
                logger.info("I've detected your system is using: " + sys.stdout.encoding)
                logger.info("unable to parse properly due to utf-8 problem, ignoring wrong symbols")
                try:
                    soup = BeautifulSoup(urllib2.urlopen(inputMIS)).decode('utf-8', 'ignore')
                except UnicodeDecodeError:
                    logger.info("not working...aborting. Tell Evilhero.")
                    return
            #If CV doesn't have the Series Year (Stupid)...Let's store the Comics.org stated year just in case.
            pyearit = soup.find("div", {"class" : "item_data"})
            pyeartxt = pyearit.find(text=re.compile(r"Series"))
            pyearst = pyeartxt.index('Series')
            ParseYear = pyeartxt[int(pyearst)-5:int(pyearst)]

            parsed = soup.find("div", {"id" : "series_data"})
            #recent structure changes - need to adjust now
            subtxt3 = parsed.find("dd", {"id" : "publication_dates"})
            resultPublished = subtxt3.findNext(text=True).rstrip()
            #print ("pubdate:" + str(resultPublished))
            parsfind = parsed.findAll("dt", {"class" : "long"})
            seriesloop = len(parsfind)
            resultFormat = ''
            for pf in parsfind:
                if 'Publishing Format:' in pf.findNext(text=True):
                    subtxt9 = pf.find("dd", {"id" : "series_format"})
                    resultFormat = subtxt9.findNext(text=True).rstrip()
                    continue
            # the caveat - if a series is ongoing but only has 1 issue published at a particular point in time,
            # resultPublished will return just the date and not the word 'Present' which dictates on the main
            # page if a series is Continuing / Ended .
            if resultFormat != '':
                if 'ongoing series' in resultFormat.lower() and 'was' not in resultFormat.lower() and 'present' not in resultPublished.lower():
                    resultPublished = resultPublished + " - Present"
                if 'limited series' in resultFormat.lower() and '?' in resultPublished:
                    resultPublished = resultPublished + " (Limited Series)"
            coverst = soup.find("div", {"id" : "series_cover"})
            if coverst < 0: 
                gcdcover = "None"
            else:
                subcoverst = coverst('img',src=True)[0]
                gcdcover = subcoverst['src']

        #print ("resultURL:" + str(resultURL))
        #print ("comicID:" + str(ComicID))
        input2 = 'http://www.comics.org' + str(resultURL) + 'details/'
        resp = urllib2.urlopen(input2)
        soup = BeautifulSoup(resp)

        #for newer comics, on-sale date has complete date...
        #for older comics, pub.date is to be used

#        type = soup.find(text=' On-sale date ')
        type = soup.find(text=' Pub. Date ')
        if type:
            #print ("on-sale date detected....adjusting")
            datetype = "pub"
        else:
            #print ("pub date defaulting")
            datetype = "on-sale"

        cnt1 = len(soup.findAll("tr", {"class" : "row_even_False"}))
        cnt2 = len(soup.findAll("tr", {"class" : "row_even_True"}))

        cnt = int(cnt1 + cnt2)

        #print (str(cnt) + " Issues in Total (this may be wrong due to alternate prints, etc")

        n_odd = -1
        n_even = -1
        n = 0
        PI = "1.00"
        altcount = 0
        PrevYRMO = "0000-00"
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

            fid = parsed('a',href=True)[0]
            resultGID = fid['href']
            resultID = resultGID[7:-1]

            if ',' in ParseIssue: ParseIssue = re.sub("\,", "", ParseIssue)
            variant="no"
            if 'Vol' in ParseIssue or '[' in ParseIssue or 'a' in ParseIssue or 'b' in ParseIssue or 'c' in ParseIssue:
                m = re.findall('[^\[\]]+', ParseIssue)
                # ^^ takes care of [] 
                # if it's a decimal - variant ...whoo-boy is messed.
                if '.' in m[0]:
                    dec_chk = m[0]
                    #if it's a digit before and after decimal, assume decimal issue
                    dec_st = dec_chk.find('.')
                    dec_b4 = dec_chk[:dec_st]
                    dec_ad = dec_chk[dec_st+1:]
                    dec_ad = re.sub("\s", "", dec_ad)
                    if dec_b4.isdigit() and dec_ad.isdigit():
                        #logger.fdebug("Alternate decimal issue...*Whew* glad I caught that")
                        ParseIssue = dec_b4 + "." + dec_ad
                    else:
                        #logger.fdebug("it's a decimal, but there's no digits before or after decimal")
                        #not a decimal issue, drop it down to the regex below.
                        ParseIssue = re.sub("[^0-9]", " ", dec_chk)
                else:                
                    ParseIssue = re.sub("[^0-9]", " ", m[0])
                    # ^^ removes everything but the digits from the remaining non-brackets
                
                logger.fdebug("variant cover detected : " + str(ParseIssue))
                variant="yes"
                altcount = 1
            isslen = ParseIssue.find(' ')
            if isslen < 0:
                #logger.fdebug("just digits left..using " + str(ParseIssue))
                isslen == 0
                isschk = ParseIssue
                #logger.fdebug("setting ParseIssue to isschk: " + str(isschk))
            else:
                #logger.fdebug("parse issue is " + str(ParseIssue))
                #logger.fdebug("more than digits left - first space detected at position : " + str(isslen))
                #if 'isslen' exists, it means that it's an alternative cover.
                #however, if ONLY alternate covers exist of an issue it won't work.
                #let's use the FIRST record, and ignore all other covers for the given issue.
                isschk = ParseIssue[:isslen]
            #logger.fdebug("Parsed Issue#: " + str(isschk))
            ParseIssue = re.sub("\s", "", ParseIssue)
            #check if decimal or '1/2' exists or not, and store decimal results
            halfchk = "no"
            if '.' in isschk:
                isschk_find = isschk.find('.')
                isschk_b4dec = isschk[:isschk_find]
                isschk_decval = isschk[isschk_find+1:]
                #logger.fdebug("decimal detected for " + str(isschk))
                #logger.fdebug("isschk_decval is " + str(isschk_decval))
                if len(isschk_decval) == 1:
                    ParseIssue = isschk_b4dec + "." + str(int(isschk_decval) * 10)

            elif '/' in isschk:
                ParseIssue = "0.50"
                isslen = 0
                halfchk = "yes"
            else:
                isschk_decval = ".00"
                ParseIssue = ParseIssue + isschk_decval
            if variant == "yes":
                #logger.fdebug("alternate cover detected - skipping/ignoring.")
                altcount = 1
  
            # in order to get the compare right, let's decimialize the string to '.00'.
#            if halfchk == "yes": pass
#            else: 
#                ParseIssue = ParseIssue + isschk_decval

            datematch="false"

            if not any(d.get('GCDIssue', None) == str(ParseIssue) for d in gcdchoice):
                #logger.fdebug("preparing to add issue to db : " + str(ParseIssue))
                pass
            else:
                #logger.fdebug("2 identical issue #'s have been found...determining if it's intentional")
                #get current issue & publication date.
                #logger.fdebug("Issue #:" + str(ParseIssue))
                #logger.fdebug("IssueDate: " + str(gcdinfo['ComicDate']))
                #get conflicting issue from tuple
                for d in gcdchoice:
                    if str(d['GCDIssue']) == str(ParseIssue):
                       #logger.fdebug("Issue # already in tuple - checking IssueDate:" + str(d['GCDDate']) )
                       if str(d['GCDDate']) == str(gcdinfo['ComicDate']):
                           #logger.fdebug("Issue #'s and dates match...skipping.")
                           datematch="true"
                       else:
                           #logger.fdebug("Issue#'s match but different publication dates, not skipping.")
                           datematch="false"

            if datematch == "false":
                gcdinfo['ComicIssue'] = ParseIssue
                #--- let's use pubdate.
                #try publicationd date first
                ParseDate = GettheDate(parsed,PrevYRMO)                
   
                ParseDate = ParseDate.replace(' ','')
                PrevYRMO = ParseDate
                gcdinfo['ComicDate'] = ParseDate
                #^^ will retrieve date #
                #logger.fdebug("adding: " + str(gcdinfo['ComicIssue']) + " - date: " + str(ParseDate))
                if ComicID[:1] == "G":
                    gcdchoice.append({
                        'GCDid':                ComicID,
                        'IssueID':              resultID,
                        'GCDIssue':             gcdinfo['ComicIssue'],
                        'GCDDate':              gcdinfo['ComicDate']
                        })
                    gcount+=1
                else:
                    gcdchoice.append({
                        'GCDid':                ComicID,
                        'GCDIssue':             gcdinfo['ComicIssue'],
                        'GCDDate':              gcdinfo['ComicDate']
                        })

                gcdinfo['gcdchoice'] = gcdchoice

            altcount = 0 
            n+=1
        i+=1
    gcdinfo['gcdvariation'] = issvariation
    if ComicID[:1] == "G":
        gcdinfo['totalissues'] = gcount
    else:
        gcdinfo['totalissues'] = TotalIssues
    gcdinfo['ComicImage'] = gcdcover
    gcdinfo['resultPublished'] = resultPublished
    gcdinfo['SeriesYear'] = ParseYear
    gcdinfo['GCDComicID'] = resultURL.split('/')[0]
    return gcdinfo
        ## -- end (GCD) -- ##

def GettheDate(parsed,PrevYRMO):
    #--- let's use pubdate.
    #try publicationd date first
    #logger.fdebug("parsed:" + str(parsed))    
    subtxt1 = parsed('td')[1]
    ParseDate = subtxt1.findNext(text=True).rstrip()
    pformat = 'pub'
    if ParseDate is None or ParseDate == '':
        subtxt1 = parsed('td')[2]
        ParseDate = subtxt1.findNext(text=True)
        pformat = 'on-sale'
        if len(ParseDate) < 7: ParseDate = '0000-00' #invalid on-sale date format , drop it 0000-00 to avoid errors
    basmonths = {'january':'01','february':'02','march':'03','april':'04','may':'05','june':'06','july':'07','august':'08','september':'09','october':'10','november':'11','december':'12'}
    pdlen = len(ParseDate)
    pdfind = ParseDate.find(' ',2)
    #logger.fdebug("length: " + str(pdlen) + "....first space @ pos " + str(pdfind))
    #logger.fdebug("this should be the year: " + str(ParseDate[pdfind+1:pdlen-1]))
    if pformat == 'on-sale': pass # date is in correct format...
    else:
        if ParseDate[pdfind+1:pdlen-1].isdigit():
            #assume valid date.
            #search for number as text, and change to numeric
            for numbs in basmonths:
                if numbs in ParseDate.lower():
                    pconv = basmonths[numbs]
                    ParseYear = re.sub('/s','',ParseDate[-5:])
                    ParseDate = str(ParseYear) + "-" + str(pconv)
                    #logger.fdebug("!success - Publication date: " + str(ParseDate))
                    break
            # some comics are messed with pub.dates and have Spring/Summer/Fall/Winter
        else:
            baseseasons = {'spring':'03','summer':'06','fall':'09','winter':'12'}
            for seas in baseseasons:
                if seas in ParseDate.lower():
                    sconv = baseseasons[seas]
                    ParseYear = re.sub('/s','',ParseDate[-5:])
                    ParseDate = str(ParseYear) + "-" + str(sconv)
                    break        
#               #try key date
#               subtxt1 = parsed('td')[2]
#               ParseDate = subtxt1.findNext(text=True)
#               #logger.fdebug("no pub.date detected, attempting to use on-sale date: " + str(ParseDate))
#               if (ParseDate) < 7:
#                   #logger.fdebug("Invalid on-sale date - less than 7 characters. Trying Key date")
#                   subtxt3 = parsed('td')[0]
#                   ParseDate = subtxt3.findNext(text=True)
#                   if ParseDate == ' ':
            #increment previous month by one and throw it in until it's populated properly.
            if PrevYRMO == '0000-00':
                ParseDate = '0000-00'
            else:
                PrevYR = str(PrevYRMO)[:4]
                PrevMO = str(PrevYRMO)[5:]
                #let's increment the month now (if it's 12th month, up the year and hit Jan.)
                if int(PrevMO) == 12:
                    PrevYR = int(PrevYR) + 1
                    PrevMO = 1
                else:
                    PrevMO = int(PrevMO) + 1
                if int(PrevMO) < 10:
                    PrevMO = "0" + str(PrevMO)
                ParseDate = str(PrevYR) + "-" + str(PrevMO)
                #logger.fdebug("parseDAte:" + str(ParseDate))
    return ParseDate

def GCDAdd(gcdcomicid):
    serieschoice = []
    series = {}
    logger.fdebug("I'm trying to find these GCD comicid's:" + str(gcdcomicid))
    for gcdid in gcdcomicid:
        logger.fdebug("looking at gcdid:" + str(gcdid))
        input2 = 'http://www.comics.org/series/' + str(gcdid)
        logger.fdebug("---url: " + str(input2))
        resp = urllib2.urlopen ( input2 )
        soup = BeautifulSoup ( resp )
        logger.fdebug("SeriesName section...")
        parsen = soup.find("span", {"id" : "series_name"})
        #logger.fdebug("series name (UNPARSED): " + str(parsen))
        subpar = parsen('a')[0]
        resultName = subpar.findNext(text=True)
        logger.fdebug("ComicName: " + str(resultName))
        #covers-start
        logger.fdebug("Covers section...")
        coverst = soup.find("div", {"id" : "series_cover"})
        if coverst < 0:
            gcdcover = "None"
            logger.fdebug("unable to find any covers - setting to None")
        else:
            subcoverst = coverst('img',src=True)[0]
            #logger.fdebug("cover (UNPARSED) : " + str(subcoverst))
            gcdcover = subcoverst['src']
        logger.fdebug("Cover: " + str(gcdcover))
        #covers end
        #publisher start
        logger.fdebug("Publisher section...")
        try:
            pubst = soup.find("div", {"class" : "item_data"})
            catchit = pubst('a')[0]

        except (IndexError, TypeError):
            pubst = soup.findAll("div", {"class" : "left"})[1]
            catchit = pubst.find("a")

        publisher = catchit.findNext(text=True)
        logger.fdebug("Publisher: " + str(publisher))
        #publisher end
        parsed = soup.find("div", {"id" : "series_data"})
        #logger.fdebug("series_data: " + str(parsed))
        #print ("parse:" + str(parsed))
        subtxt3 = parsed.find("dd", {"id" : "publication_dates"})
        #logger.fdebug("publication_dates: " + str(subtxt3))
        pubdate = subtxt3.findNext(text=True).rstrip()
        logger.fdebug("pubdate:" + str(pubdate))
        subtxt4 = parsed.find("dd", {"id" : "issues_published"})
        noiss = subtxt4.findNext(text=True)
        lenwho = len(noiss)
        lent = noiss.find(' ',2)
        lenf = noiss.find('(')
        stringit = noiss[lenf:lenwho]
        stringout = noiss[:lent]
        noissues = stringout.rstrip('  \t\r\n\0')
        numbering = stringit.rstrip('  \t\r\n\0')
        logger.fdebug("noissues:" + str(noissues))
        logger.fdebug("numbering:" + str(numbering))
        serieschoice.append({
               "ComicID":         gcdid,
               "ComicName":       resultName,
               "ComicYear" :        pubdate,
               "ComicIssues" :    noissues,
               "ComicPublisher" : publisher,
               "ComicCover" :     gcdcover
              })   
    series['serieschoice'] = serieschoice 
    return series


def ComChk(ComicName, ComicYear, ComicPublisher, Total, ComicID):
    comchkchoice = []
    comchoice = {}

    NOWyr = datetime.date.today().year
    if datetime.date.today().month == 12:
        NOWyr = NOWyr + 1
        logger.fdebug("We're in December, incremented search Year to increase search results: " + str(NOWyr))
    comicnm = ComicName.encode('utf-8').strip()
    comicyr = ComicYear
    comicis = Total
    comicid = ComicID
    comicpub = ComicPublisher.encode('utf-8').strip()
    #print ("...comchk parser initialization...")
    #print ( "comicname: " + str(comicnm) )
    #print ( "comicyear: " + str(comicyr) )
    #print ( "comichave: " + str(comicis) )
    #print ( "comicpub: " + str(comicpub) )
    #print ( "comicid: " + str(comicid) )
    # do 3 runs at the comics.org search to get the best results
    comicrun = []
    # &pub_name=DC
    # have to remove the spaces from Publisher or else will not work (ie. DC Comics vs DC will not match)
    # take the 1st word ;)
    #comicpub = comicpub.split()[0]
    # if it's not one of the BIG publisher's it might fail - so let's increase the odds.
    pubbiggies = [ 'DC', 
                   'Marvel',
                   'Image',
                   'IDW' ]
    uhuh = "no"
    for pb in pubbiggies:
        if pb in comicpub:
            #keep publisher in url if a biggie.    
            uhuh = "yes"
            #print (" publisher match : " + str(comicpub))
            conv_pub = comicpub.split()[0]
            #print (" converted publisher to : " + str(conv_pub))
    #1st run setup - leave it all as it is.
    comicrun.append(comicnm)
    cruncnt = 0
    #2nd run setup - remove the last character and do a broad search (keep year or else will blow up)
    if len(str(comicnm).split()) > 2:
        comicrun.append(' '.join(comicnm.split(' ')[:-1]))
        cruncnt+=1
    # to increase the likely hood of matches and to get a broader scope...
    # lets remove extra characters
    if re.sub('[\.\,\:]', '', comicnm) != comicnm:
        comicrun.append(re.sub('[\.\,\:]', '', comicnm))
        cruncnt+=1
    # one more addition - if the title contains a 'the', remove it ;)
    if comicnm.lower().startswith('the'):
        comicrun.append(comicnm[4:].strip())
        cruncnt+=1
    totalcount = 0
    cr = 0
    #print ("cruncnt is " + str(cruncnt))
    while (cr <= cruncnt):
        #print ("cr is " + str(cr))
        comicnm = comicrun[cr]
        #leaving spaces in will screw up the search...let's take care of it
        comicnm = re.sub(' ', '+', comicnm)
        #print ("comicnm: " + str(comicnm))
        if uhuh == "yes":
            publink = "&pub_name=" + str(conv_pub)
        if uhuh == "no":
            publink = "&pub_name="
        input = 'http://www.comics.org/search/advanced/process/?target=series&method=icontains&logic=False&keywords=&order1=series&order2=date&order3=&start_date=' + str(comicyr) + '-01-01&end_date=' + str(NOWyr) + '-12-31' + '&title=&feature=&job_number=&pages=&script=&pencils=&inks=&colors=&letters=&story_editing=&genre=&characters=&synopsis=&reprint_notes=&story_reprinted=None&notes=' + str(publink) + '&pub_notes=&brand=&brand_notes=&indicia_publisher=&is_surrogate=None&ind_pub_notes=&series=' + str(comicnm) + '&series_year_began=&series_notes=&tracking_notes=&issue_count=&is_comics=None&format=&color=&dimensions=&paper_stock=&binding=&publishing_format=&issues=&volume=&issue_title=&variant_name=&issue_date=&indicia_frequency=&price=&issue_pages=&issue_editing=&isbn=&barcode=&issue_notes=&issue_reprinted=None&is_indexed=None'
        response = urllib2.urlopen ( input )
        soup = BeautifulSoup ( response)
        cnt1 = len(soup.findAll("tr", {"class" : "listing_even"}))
        cnt2 = len(soup.findAll("tr", {"class" : "listing_odd"}))

        cnt = int(cnt1 + cnt2)
#        print ("cnt1: " + str(cnt1))
#        print ("cnt2: " + str(cnt2))
#        print (str(cnt) + " results")

        resultName = []
        resultID = []
        resultYear = []
        resultIssues = []
        resultPublisher = []
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
            rtpit = rtp.findNext(text=True)
            rtpthis = rtpit.encode('utf-8').strip()
            resultName.append(helpers.cleanName(rtpthis))
#            print ( "Comic Name: " + str(resultName[n]) )

            pub = resultp('a')[0]
            pubit = pub.findNext(text=True)
#            pubthis = u' '.join(pubit).encode('utf-8').strip()
            pubthis = pubit.encode('utf-8').strip()
            resultPublisher.append(pubthis)
#            print ( "Publisher: " + str(resultPublisher[n]) )

            fip = resultp('a',href=True)[1]
            resultID.append(fip['href'])
#            print ( "ID: " + str(resultID[n]) )

            subtxt3 = resultp('td')[3]
            resultYear.append(subtxt3.findNext(text=True))
            resultYear[n] = resultYear[n].replace(' ','')
            subtxt4 = resultp('td')[4]
            resultIssues.append(helpers.cleanName(subtxt4.findNext(text=True)))
            resiss = resultIssues[n].find('issue')
            resiss = int(resiss)
            resultIssues[n] = resultIssues[n].replace('','')[:resiss]
            resultIssues[n] = resultIssues[n].replace(' ','')
#            print ( "Year: " + str(resultYear[n]) )
#            print ( "Issues: " + str(resultIssues[n]) )
#            print ("comchkchoice: " + str(comchkchoice))
            if not any(d.get('GCDID', None) == str(resultID[n]) for d in comchkchoice):
                #print ( str(resultID[n]) + " not in DB...adding.")
                comchkchoice.append({
                       "ComicID":         str(comicid),
                       "ComicName":       resultName[n],
                       "GCDID":           str(resultID[n]).split('/')[2],
                       "ComicYear" :      str(resultYear[n]),
                       "ComicPublisher" : resultPublisher[n],
                       "ComicURL" :       "http://www.comics.org" + str(resultID[n]),
                       "ComicIssues" :    str(resultIssues[n])
                      })
            #else:
                #print ( str(resultID[n]) + " already in DB...skipping" ) 
            n+=1
        cr+=1
    totalcount= totalcount + cnt
    comchoice['comchkchoice'] = comchkchoice
    return comchoice, totalcount 

def decode_html(html_string):
    converted = UnicodeDammit(html_string)
    if not converted.unicode:
        raise UnicodeDecodeError(
            "Failed to detect encoding, tried [%s]",
            ', '.join(converted.triedEncodings))
    # print converted.originalEncoding
    return converted.unicode

def annualCheck(gcomicid, comicid, comicname, comicyear):
    # will only work if we already matched for gcd.
    # search for <comicname> annual
    # grab annual listing that hits on comicyear (seriesyear)
    # grab results :)
    print ("GcomicID: " + str(gcomicid))
    print ("comicID: " + str(comicid))
    print ("comicname: " + comicname)
    print ("comicyear: " + str(comicyear))
    comicnm = comicname.encode('utf-8').strip()
    comicnm_1 = re.sub('\+', '%2B', comicnm + " annual")
    comicnm = re.sub(' ', '+', comicnm_1)
    input = 'http://www.comics.org/search/advanced/process/?target=series&method=icontains&logic=False&order2=date&order3=&start_date=' + str(comicyear) + '-01-01&end_date=' + str(comicyear) + '-12-31&series=' + str(comicnm) + '&is_indexed=None'

    response = urllib2.urlopen ( input )
    soup = BeautifulSoup ( response)
    cnt1 = len(soup.findAll("tr", {"class" : "listing_even"}))
    cnt2 = len(soup.findAll("tr", {"class" : "listing_odd"}))

    cnt = int(cnt1 + cnt2)

    print (str(cnt) + " results")

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
        rtp1 = re.sub('Annual', '', rtp)
        resultName.append(helpers.cleanName(rtp1.findNext(text=True)))
        print ( "Comic Name: " + str(resultName[n]) )
        fip = resultp('a',href=True)[1]
        resultID.append(fip['href'])
        print ( "ID: " + str(resultID[n]) )

        subtxt3 = resultp('td')[3]
        resultYear.append(subtxt3.findNext(text=True))
        resultYear[n] = resultYear[n].replace(' ','')
   
        subtxt4 = resultp('td')[4]
        resultIssues.append(helpers.cleanName(subtxt4.findNext(text=True)))
        resiss = resultIssues[n].find('issue')
        resiss = int(resiss)
        resultIssues[n] = resultIssues[n].replace('','')[:resiss]
        resultIssues[n] = resultIssues[n].replace(' ','')
        print ( "Year: " + str(resultYear[n]) )
        print ( "Issues: " + str(resultIssues[n]) )
        CleanComicName = re.sub('[\,\.\:\;\'\[\]\(\)\!\@\#\$\%\^\&\*\-\_\+\=\?\/]', '', comicnm)

        CleanComicName = re.sub(' ', '', CleanComicName).lower()
        CleanResultName = re.sub('[\,\.\:\;\'\[\]\(\)\!\@\#\$\%\^\&\*\-\_\+\=\?\/]', '', resultName[n])
        CleanResultName = re.sub(' ', '', CleanResultName).lower()
        print ("CleanComicName: " + str(CleanComicName))
        print ("CleanResultName: " + str(CleanResultName))
        if CleanResultName == CleanComicName or CleanResultName[3:] == CleanComicName:
        #if resultName[n].lower() == helpers.cleanName(str(ComicName)).lower():
            #print ("n:" + str(n) + "...matched by name to Mylar!")
            if resultYear[n] == ComicYear or resultYear[n] == str(int(ComicYear)+1):
                print ("n:" + str(n) + "...matched by year to Mylar!")
                print ( "Year: " + str(resultYear[n]) )
                TotalIssues = resultIssues[n]
                resultURL = str(resultID[n])
                rptxt = resultp('td')[6]
                resultPublished = rptxt.findNext(text=True)
                #print ("Series Published: " + str(resultPublished))
                break

        n+=1
    return
