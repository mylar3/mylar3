
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

def cbdb(comicnm, ComicYear):
    #comicnm = 'Animal Man'
    #print ( "comicname: " + str(comicnm) )
    #print ( "comicyear: " + str(comicyr) )
    comicnm = re.sub(' ', '+', comicnm)
    input = "http://mobile.comicbookdb.com/search.php?form_search=" + str(comicnm) + "&form_searchtype=Title&x=0&y=0"
    response = urllib2.urlopen ( input )
    soup = BeautifulSoup ( response)
    abc = soup.findAll('a', href=True)
    lenabc = len(abc)
    i=0
    resultName = []
    resultID = []
    resultYear = []
    resultIssues = []
    resultURL = []
    matched = "no"

    while (i < lenabc):
        titlet = abc[i] #iterate through the href's, pulling out only results. 
        print ("titlet: " + str(titlet))
        if "title.php" in str(titlet):
            print ("found title")
            tempName = titlet.findNext(text=True)
            print ("tempName: " + tempName)
            resultName = tempName[:tempName.find("(")]
            print ("ComicName: " + resultName)

            resultYear = tempName[tempName.find("(")+1:tempName.find(")")]
            if resultYear.isdigit(): pass
            else: 
                i+=1
                continue
            print "ComicYear: " + resultYear

            ID_som = titlet['href']
            resultURL = ID_som
            print "CBDB URL: " + resultURL

            IDst = ID_som.find('?ID=')
            resultID = ID_som[(IDst+4):]

            print "CBDB ID: " + resultID


            print ("resultname: " + resultName)
            CleanComicName = re.sub('[\,\.\:\;\'\[\]\(\)\!\@\#\$\%\^\&\*\-\_\+\=\?\/]', '', comicnm)
            CleanComicName = re.sub(' ', '', CleanComicName).lower()
            CleanResultName = re.sub('[\,\.\:\;\'\[\]\(\)\!\@\#\$\%\^\&\*\-\_\+\=\?\/]', '', resultName)
            CleanResultName = re.sub(' ', '', CleanResultName).lower()
            print ("CleanComicName: " + CleanComicName)
            print ("CleanResultName: " + CleanResultName)
            if CleanResultName == CleanComicName or CleanResultName[3:] == CleanComicName or len(CleanComicName) == len(CleanResultName):
            #if resultName[n].lower() == helpers.cleanName(str(ComicName)).lower():
                print ("i:" + str(i) + "...matched by name to Mylar!")
                print ("ComicYear: " + str(ComicYear) + ".. to ResultYear: " + str(resultYear))
                if resultYear.isdigit():
                    if int(resultYear) == int(ComicYear) or int(resultYear) == int(ComicYear)+1:
                        resultID = str(resultID)
                        print ("Matchumundo!")
                        matched = "yes"
                else:
                    continue
            if matched == "yes":
                break
        i+=1
    return IssueDetails(resultID)


def IssueDetails(cbdb_id):
    annuals = {}
    annualslist = []
    gcount = 0
    pagethis = 'http://comicbookdb.com/title.php?ID=' + str(cbdb_id)
    
    response = urllib2.urlopen(pagethis)
    soup = BeautifulSoup(response)

    resultp = soup.findAll("table")
    total = len(resultp)  # -- number of tables
    #get details here
    
    startit = resultp[0].find("table", {"width" : "884" })

    i = 0
    pubchk = 0
    boop = startit.findAll('strong')
    for t in boop:
        if pubchk == 0:
            if ("publisher.php?" in startit('a')[i]['href']):
                print (startit('a')[i]['href'])
                publisher = str(startit('a')[i].contents)
                print ("publisher: " + publisher)
                pubchk = "1"
        elif 'Publication Date: ' in t:
            pdi = boop[i].nextSibling
            print ("publication date: " + pdi)
        elif 'Number of issues cataloged: ' in t:
            noi = boop[i].nextSibling
            print ("number of issues: " + noi)

        i+=1

        if i > len(boop): break

#    pd = startit.find("Publication Date: ").nextSibling.next.text
#    resultPublished = str(pd)
#    noi = startit.find("Number of issues cataloged: ").nextSibling.next.text
#    totalIssues = str(noi)
#    print ("Publication Dates : " + str(resultPublished))
#    print ("Total Issues: " + str(totalIssues))
    ti = 1 # start at one as 0 is the ENTIRE soup structure
    while (ti < total):
        #print result
        if resultp[ti].find("a", {"class" : "page_link" }):
            #print "matcheroso"
            tableno = resultp[ti].findAll('tr')  #7th table, all the tr's
            #print ti, total
            break
        ti+=1
    noresults = len(tableno)
    #print ("tableno: " + str(tableno))
    print ("there are " + str(noresults) + " issues total (cover variations, et all).")
    i=1 # start at 1 so we don't grab the table headers ;)
    issue = []
    storyarc = []
    pubdate = []
    #resultit = tableno[1]
    #print ("resultit: " + str(resultit))

    while (i < noresults):
        resultit = tableno[i]   # 7th table, 1st set of tr (which indicates an issue).
        print ("resultit: " + str(resultit))
        issuet = resultit.find("a", {"class" : "page_link" })  # gets the issue # portion
        try:
            issue = issuet.findNext(text=True)
        except:
            print ("blank space - skipping")
            i+=1
            continue
        if 'annual' not in issue.lower(): 
            i+=1
            continue
        
        lent = resultit('a',href=True) #gathers all the a href's within this particular tr
        #print ("lent: " + str(lent))
        lengtht = len(lent)  #returns the # of ahref's within this particular tr
        #print ("lengtht: " + str(lengtht))
        #since we don't know which one contains the story arc, we need to iterate through to find it
        #we need to know story arc, because the following td is the Publication Date
        n=0
        issuetitle = 'None'
        while (n < lengtht):
            storyt = lent[n] # 
            print ("storyt: " + str(storyt))
            if 'issue.php' in storyt:
                issuetitle = storyt.findNext(text=True)
                print ("title:" + issuetitle)
            if 'storyarc.php' in storyt:
                #print ("found storyarc")
                storyarc = storyt.findNext(text=True)
                #print ("Story Arc: " + str(storyarc))
                break
            n+=1
        pubd = resultit('td')  # find all the <td>'s within this tr
        publen = len(pubd) # find the # of <td>'s
        pubs = pubd[publen-1] #take the last <td> which will always contain the publication date
        pdaters = pubs.findNext(text=True) #get the actual date :)
        basmonths = {'january':'01','february':'02','march':'03','april':'04','may':'05','june':'06','july':'07','august':'09','september':'10','october':'11','december':'12','annual':''}
        for numbs in basmonths:
            if numbs in pdaters.lower():
                pconv = basmonths[numbs]
                ParseYear = re.sub('/s','',pdaters[-5:])
                if basmonths[numbs] == '':
                    pubdate = str(ParseYear)
                else:
                    pubdate= str(ParseYear) + "-" + str(pconv)
                #logger.fdebug("!success - Publication date: " + str(ParseDate))

        #pubdate = re.sub("[^0-9]", "", pdaters)
        issuetmp = re.sub("[^0-9]", '', issue)
        print ("Issue : " + str(issuetmp) + "  (" + str(pubdate) + ")")
        print ("Issuetitle " + str(issuetitle))

        annualslist.append({
            'AnnualIssue':  issuetmp.strip(),
            'AnnualTitle':  issuetitle,
            'AnnualDate':   pubdate.strip(),
            'AnnualYear':   ParseYear.strip()
            })
        gcount+=1 
        print("annualslist appended...")
        i+=1

    annuals['annualslist'] = annualslist

    print ("Issues:" + str(annuals['annualslist']))
    print ("There are " + str(gcount) + " issues.")

    annuals['totalissues'] = gcount
    annuals['GCDComicID'] = cbdb_id
    return annuals

if __name__ == '__main__':
    cbdb(sys.argv[1], sys.argv[2])
