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

from __future__ import with_statement

import os
import glob
import re 
import shutil

import mylar
from mylar import db, logger, helpers, importer, updater

# You can scan a single directory and append it to the current library by specifying append=True
def libraryScan(dir=None, append=False, ComicID=None, ComicName=None, cron=None):

    if cron and not mylar.LIBRARYSCAN:
        return
        
    if not dir:
        dir = mylar.COMIC_DIR
    
    # If we're appending a dir, it's coming from the post processor which is
    # already bytestring
    if not append:
        dir = dir.encode(mylar.SYS_ENCODING)
        
    if not os.path.isdir(dir):
        logger.warn('Cannot find directory: %s. Not scanning' % dir.decode(mylar.SYS_ENCODING, 'replace'))
        return

    
    logger.info('Scanning comic directory: %s' % dir.decode(mylar.SYS_ENCODING, 'replace'))

    basedir = dir

    comic_list = []
    comiccnt = 0
    extensions = ('cbr','cbz')
    for r,d,f in os.walk(dir):
        #for directory in d[:]:
        #    if directory.startswith("."):
        #        d.remove(directory)
        for files in f:
            if any(files.lower().endswith('.' + x.lower()) for x in extensions):
                comic = files
                comicpath = os.path.join(r, files)
                comicsize = os.path.getsize(comicpath)
                print "Comic: " + comic
                print "Comic Path: " + comicpath
                print "Comic Size: " + str(comicsize)

                # We need the unicode path to use for logging, inserting into database
                unicode_comic_path = comicpath.decode(mylar.SYS_ENCODING, 'replace')

                comiccnt+=1
                comic_dict = { 'ComicFilename':           comic,
                               'ComicLocation':           comicpath,
                               'ComicSize':               comicsize,
                               'Unicode_ComicLocation':   unicode_comic_path }
                comic_list.append(comic_dict)

        logger.info("I've found a total of " + str(comiccnt) + " comics....analyzing now")
        logger.info("comiclist: " + str(comic_list))
    myDB = db.DBConnection()

    #let's load in the watchlist to see if we have any matches.
    logger.info("loading in the watchlist to see if a series is being watched already...")
    watchlist = myDB.select("SELECT * from comics")
    ComicName = []
    DisplayName = []
    ComicYear = []
    ComicPublisher = []
    ComicTotal = []
    ComicID = []
    ComicLocation = []

    AltName = []
    watchcnt = 0

    watch_kchoice = []
    watchchoice = {}
    import_by_comicids = []
    import_comicids = {}

    for watch in watchlist:
        #use the comicname_filesafe to start
        watchdisplaycomic = watch['ComicName'].encode('utf-8').strip() #re.sub('[\_\#\,\/\:\;\!\$\%\&\+\'\?\@]', ' ', watch['ComicName']).encode('utf-8').strip()
        # let's clean up the name, just in case for comparison purposes...
        watchcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]', '', watch['ComicName_Filesafe']).encode('utf-8').strip()
        #watchcomic = re.sub('\s+', ' ', str(watchcomic)).strip()

        if ' the ' in watchcomic.lower():
            #drop the 'the' from the watchcomic title for proper comparisons.
            watchcomic = watchcomic[-4:]

        alt_chk = "no" # alt-checker flag (default to no)
         
        # account for alternate names as well
        if watch['AlternateSearch'] is not None and watch['AlternateSearch'] is not 'None':
            altcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]', '', watch['AlternateSearch']).encode('utf-8').strip()
            #altcomic = re.sub('\s+', ' ', str(altcomic)).strip()
            AltName.append(altcomic)
            alt_chk = "yes"  # alt-checker flag

        ComicName.append(watchcomic)
        DisplayName.append(watchdisplaycomic)
        ComicYear.append(watch['ComicYear'])
        ComicPublisher.append(watch['ComicPublisher'])
        ComicTotal.append(watch['Total'])
        ComicID.append(watch['ComicID'])
        ComicLocation.append(watch['ComicLocation'])
        watchcnt+=1

    logger.info("Successfully loaded " + str(watchcnt) + " series from your watchlist.")

    ripperlist=['digital-',
                'empire',
                'dcp']

    watchfound = 0

    datelist = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
#    datemonth = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':$
#    #search for number as text, and change to numeric
#    for numbs in basnumbs:
#        #print ("numbs:" + str(numbs))
#        if numbs in ComicName.lower():
#            numconv = basnumbs[numbs]
#            #print ("numconv: " + str(numconv))


    for i in comic_list:
        print i['ComicFilename']

        #if mylar.IMP_METADATA:
        #logger.info('metatagging checking enabled.')
        #if read tags is enabled during import, check here.
        #if i['ComicLocation'].endswith('.cbz'):
        #    logger.info('Attempting to read tags present in filename: ' + str(i['ComicLocation']))
        #    issueinfo = helpers.IssueDetails(i['ComicLocation'])
        #    if issueinfo is None:
        #        pass
        #    else:
        #        logger.info('Successfully retrieved some tags. Lets see what I can figure out.')
        #        comicname = issueinfo[0]['series']
        #        logger.fdebug('Series Name: ' + comicname)
        #        issue_number = issueinfo[0]['issue_number']
        #        logger.fdebug('Issue Number: ' + str(issue_number))
        #        issuetitle = issueinfo[0]['title']
        #        logger.fdebug('Issue Title: ' + issuetitle)
        #        issueyear = issueinfo[0]['year']
        #        logger.fdebug('Issue Year: ' + str(issueyear))
        #        # if used by ComicTagger, Notes field will have the IssueID.
        #        issuenotes = issueinfo[0]['notes']
        #        logger.fdebug('Notes: ' + issuenotes)
                    

        comfilename = i['ComicFilename']
        comlocation = i['ComicLocation']
        #let's clean up the filename for matching purposes

        cfilename = re.sub('[\_\#\,\/\:\;\-\!\$\%\&\+\'\?\@]', ' ', comfilename)
        #cfilename = re.sub('\s', '_', str(cfilename))
        d_filename = re.sub('[\_\#\,\/\;\!\$\%\&\?\@]', ' ', comfilename)
        d_filename = re.sub('[\:\-\+\']', '#', d_filename)

        #strip extraspaces
        d_filename = re.sub('\s+', ' ', d_filename)
        cfilename = re.sub('\s+', ' ', cfilename)

        #versioning - remove it
        subsplit = cfilename.replace('_', ' ').split()
        volno = None
        volyr = None
        for subit in subsplit:
            if subit[0].lower() == 'v':
                vfull = 0
                if subit[1:].isdigit():
                    #if in format v1, v2009 etc...
                    if len(subit) > 3:
                        # if it's greater than 3 in length, then the format is Vyyyy
                        vfull = 1 # add on 1 character length to account for extra space
                    cfilename = re.sub(subit, '', cfilename)
                    d_filename = re.sub(subit, '', d_filename)
                    volno = re.sub("[^0-9]", " ", subit)
                elif subit.lower()[:3] == 'vol':
                    #if in format vol.2013 etc
                    #because the '.' in Vol. gets removed, let's loop thru again after the Vol hit to remove it entirely
                    logger.fdebug('volume indicator detected as version #:' + str(subit))
                    cfilename = re.sub(subit, '', cfilename)
                    cfilename = " ".join(cfilename.split())
                    d_filename = re.sub(subit, '', d_filename)
                    d_filename = " ".join(d_filename.split())
                    volyr = re.sub("[^0-9]", " ", subit).strip()
                    logger.fdebug('volume year set as : ' + str(volyr))
        cm_cn = 0

        #we need to track the counter to make sure we are comparing the right array parts
        #this takes care of the brackets :)
        m = re.findall('[^()]+', d_filename)  #cfilename)
        lenm = len(m)
        logger.fdebug("there are " + str(lenm) + " words.")
        cnt = 0
        yearmatch = "false"
        foundonwatch = "False"
        issue = 999999


        while (cnt < lenm):
            if m[cnt] is None: break
            if m[cnt] == ' ':
                pass
            else:
                logger.fdebug(str(cnt) + ". Bracket Word: " + m[cnt])
                if cnt == 0:
                    comic_andiss = m[cnt]
                    logger.fdebug("Comic: " + comic_andiss)
                    # if it's not in the standard format this will bork.
                    # let's try to accomodate (somehow).
                    # first remove the extension (if any)
                    extensions = ('cbr', 'cbz')
                    if comic_andiss.lower().endswith(extensions):
                        comic_andiss = comic_andiss[:-4]
                        logger.fdebug("removed extension from filename.")
                    #now we have to break up the string regardless of formatting.
                    #let's force the spaces.
                    comic_andiss = re.sub('_', ' ', comic_andiss)
                    cs = comic_andiss.split()
                    cs_len = len(cs)
                    cn = ''
                    ydetected = 'no'
                    idetected = 'no'
                    decimaldetect = 'no'
                    for i in reversed(xrange(len(cs))):
                        #start at the end.
                        logger.fdebug("word: " + str(cs[i]))
                        #assume once we find issue - everything prior is the actual title
                        #idetected = no will ignore everything so it will assume all title                            
                        if cs[i][:-2] == '19' or cs[i][:-2] == '20' and idetected == 'no':
                            logger.fdebug("year detected: " + str(cs[i]))
                            ydetected = 'yes'
                            result_comyear = cs[i]
                        elif cs[i].isdigit() and idetected == 'no' or '.' in cs[i]:
                            if '.' in cs[i]:
                                #make sure it's a number on either side of decimal and assume decimal issue.
                                decst = cs[i].find('.')
                                dec_st = cs[i][:decst]
                                dec_en = cs[i][decst+1:]
                                logger.fdebug("st: " + str(dec_st))
                                logger.fdebug("en: " + str(dec_en))
                                if dec_st.isdigit() and dec_en.isdigit():
                                    logger.fdebug("decimal issue detected...adjusting.")
                                    issue = dec_st + "." + dec_en
                                    logger.fdebug("issue detected: " + str(issue))
                                    idetected = 'yes'
                                else:
                                    logger.fdebug("false decimal represent. Chunking to extra word.")
                                    cn = cn + cs[i] + " "
                                    break
                            issue = cs[i]
                            logger.fdebug("issue detected : " + str(issue))
                            idetected = 'yes'

                        elif '\#' in cs[i] or decimaldetect == 'yes':
                            logger.fdebug("issue detected: " + str(cs[i]))
                            idetected = 'yes'
                        else: cn = cn + cs[i] + " "
                    if ydetected == 'no':
                        #assume no year given in filename...
                        result_comyear = "0000"
                    logger.fdebug("cm?: " + str(cn))
                    if issue is not '999999':
                        comiss = issue
                    else:
                        logger.ERROR("Invalid Issue number (none present) for " + comfilename)
                        break
                    cnsplit = cn.split()
                    cname = ''
                    findcn = 0
                    while (findcn < len(cnsplit)):
                        cname = cname + cs[findcn] + " "
                        findcn+=1
                    cname = cname[:len(cname)-1] # drop the end space...
                    print ("assuming name is : " + cname)
                    com_NAME = cname
                    print ("com_NAME : " + com_NAME)
                    yearmatch = "True"
                else:
                    logger.fdebug('checking ' + m[cnt])
                    # we're assuming that the year is in brackets (and it should be damnit)
                    if m[cnt][:-2] == '19' or m[cnt][:-2] == '20':
                        print ("year detected: " + str(m[cnt]))
                        ydetected = 'yes'
                        result_comyear = m[cnt]
                    elif m[cnt][:3].lower() in datelist:
                        logger.fdebug('possible issue date format given - verifying')
                        #if the date of the issue is given as (Jan 2010) or (January 2010) let's adjust.
                        #keeping in mind that ',' and '.' are already stripped from the string
                        if m[cnt][-4:].isdigit():
                            ydetected = 'yes'
                            result_comyear = m[cnt][-4:]
                            logger.fdebug('Valid Issue year of ' + str(result_comyear) + 'detected in format of ' + str(m[cnt]))
            cnt+=1

        displength = len(cname)
        logger.fdebug('cname length : ' + str(displength) + ' --- ' + str(cname))
        logger.fdebug('d_filename is : ' + d_filename)
        charcount = d_filename.count('#')
        logger.fdebug('charcount is : ' + str(charcount))
        if charcount > 0:
            logger.fdebug('entering loop')
            for i,m in enumerate(re.finditer('\#', d_filename)):
                if m.end() <= displength:
                    logger.fdebug(comfilename[m.start():m.end()])
                    # find occurance in c_filename, then replace into d_filname so special characters are brought across
                    newchar = comfilename[m.start():m.end()]
                    logger.fdebug('newchar:' + str(newchar))
                    d_filename = d_filename[:m.start()] + str(newchar) + d_filename[m.end():]
                    logger.fdebug('d_filename:' + str(d_filename))

        dispname = d_filename[:displength]
        logger.fdebug('dispname : ' + dispname)

        splitit = []
        watchcomic_split = []
        logger.fdebug("filename comic and issue: " + comic_andiss)

        #changed this from '' to ' '
        comic_iss_b4 = re.sub('[\-\:\,]', ' ', comic_andiss)
        comic_iss = comic_iss_b4.replace('.',' ')
        comic_iss = re.sub('[\s+]', ' ', comic_iss).strip()
        logger.fdebug("adjusted comic and issue: " + str(comic_iss))
        #remove 'the' from here for proper comparisons.
        if ' the ' in comic_iss.lower():
            comic_iss = re.sub('\\bthe\\b','', comic_iss).strip()
        splitit = comic_iss.split(None)
        logger.fdebug("adjusting from: " + str(comic_iss_b4) + " to: " + str(comic_iss))
        #here we cycle through the Watchlist looking for a match.
        while (cm_cn < watchcnt):
            #setup the watchlist
            comname = ComicName[cm_cn]
            comyear = ComicYear[cm_cn]
            compub = ComicPublisher[cm_cn]
            comtotal = ComicTotal[cm_cn]
            comicid = ComicID[cm_cn]
            watch_location = ComicLocation[cm_cn]

           # there shouldn't be an issue in the comic now, so let's just assume it's all gravy.
            splitst = len(splitit)
            watchcomic_split = helpers.cleanName(comname)
            watchcomic_split = re.sub('[\-\:\,\.]', ' ', watchcomic_split).split(None)

            logger.fdebug(str(splitit) + " file series word count: " + str(splitst))
            logger.fdebug(str(watchcomic_split) + " watchlist word count: " + str(len(watchcomic_split)))
            if (splitst) != len(watchcomic_split):
                logger.fdebug("incorrect comic lengths...not a match")
#                if str(splitit[0]).lower() == "the":
#                    logger.fdebug("THE word detected...attempting to adjust pattern matching")
#                    splitit[0] = splitit[4:]
            else:
                logger.fdebug("length match..proceeding")
                n = 0
                scount = 0
                logger.fdebug("search-length: " + str(splitst))
                logger.fdebug("Watchlist-length: " + str(len(watchcomic_split)))
                while ( n <= (splitst)-1 ):
                    logger.fdebug("splitit: " + str(splitit[n]))
                    if n < (splitst) and n < len(watchcomic_split):
                        logger.fdebug(str(n) + " Comparing: " + str(watchcomic_split[n]) + " .to. " + str(splitit[n]))
                        if '+' in watchcomic_split[n]:
                            watchcomic_split[n] = re.sub('+', '', str(watchcomic_split[n]))
                        if str(watchcomic_split[n].lower()) in str(splitit[n].lower()) and len(watchcomic_split[n]) >= len(splitit[n]):
                            logger.fdebug("word matched on : " + str(splitit[n]))
                            scount+=1
                        #elif ':' in splitit[n] or '-' in splitit[n]:
                        #    splitrep = splitit[n].replace('-', '')
                        #    print ("non-character keyword...skipped on " + splitit[n])
                    elif str(splitit[n]).lower().startswith('v'):
                        logger.fdebug("possible versioning..checking")
                        #we hit a versioning # - account for it
                        if splitit[n][1:].isdigit():
                            comicversion = str(splitit[n])
                            logger.fdebug("version found: " + str(comicversion))
                    else:
                        logger.fdebug("Comic / Issue section")
                        if splitit[n].isdigit():
                            logger.fdebug("issue detected")
                        else:
                            logger.fdebug("non-match for: "+ str(splitit[n]))
                            pass
                    n+=1
                #set the match threshold to 80% (for now)
                # if it's less than 80% consider it a non-match and discard.
                #splitit has to splitit-1 because last position is issue.
                wordcnt = int(scount)
                logger.fdebug("scount:" + str(wordcnt))
                totalcnt = int(splitst)
                logger.fdebug("splitit-len:" + str(totalcnt))
                spercent = (wordcnt/totalcnt) * 100
                logger.fdebug("we got " + str(spercent) + " percent.")
                if int(spercent) >= 80:
                    logger.fdebug("it's a go captain... - we matched " + str(spercent) + "%!")
                    logger.fdebug("this should be a match!")
                    logger.fdebug("issue we found for is : " + str(comiss))
                    #set the year to the series we just found ;)
                    result_comyear = comyear
                    #issue comparison now as well
                    logger.info(u"Found " + comname + " (" + str(comyear) + ") issue: " + str(comiss))
                    watchmatch = str(comicid)
                    dispname = DisplayName[cm_cn]
                    foundonwatch = "True"
                    break
                elif int(spercent) < 80:
                    logger.fdebug("failure - we only got " + str(spercent) + "% right!")
            cm_cn+=1

        if foundonwatch == "False":
            watchmatch = None
        #---if it's not a match - send it to the importer.
        n = 0

        if volyr is None:
            if result_comyear is None: 
                result_comyear = '0000' #no year in filename basically.
        else:
            if result_comyear is None:
                result_comyear = volyr
        if volno is None:
            if volyr is None:
                vol_label = None
            else:
                vol_label = volyr
        else:
            vol_label = volno

        logger.fdebug("adding " + com_NAME + " to the import-queue!")
        impid = dispname + '-' + str(result_comyear) + '-' + str(comiss) #com_NAME + "-" + str(result_comyear) + "-" + str(comiss)
        logger.fdebug("impid: " + str(impid))
        import_by_comicids.append({ 
            "impid"       : impid,
            "watchmatch"  : watchmatch,
            "displayname" : dispname,
            "comicname"   : dispname, #com_NAME,
            "comicyear"   : result_comyear,
            "volume"      : vol_label,
            "comfilename" : comfilename,
            "comlocation" : comlocation.decode(mylar.SYS_ENCODING)
                                   })
        logger.fdebug('import_by_ids: ' + str(import_by_comicids))

    if len(watch_kchoice) > 0:
        watchchoice['watchlist'] = watch_kchoice
        print ("watchchoice: " + str(watchchoice))

        logger.info("I have found " + str(watchfound) + " out of " + str(comiccnt) + " comics for series that are being watched.")
        wat = 0
        comicids = []

        if watchfound > 0:
            if mylar.IMP_MOVE:
                logger.info("You checked off Move Files...so that's what I'm going to do") 
                #check to see if Move Files is enabled.
                #if not being moved, set the archive bit.
                print("Moving files into appropriate directory")
                while (wat < watchfound): 
                    watch_the_list = watchchoice['watchlist'][wat]
                    watch_comlocation = watch_the_list['ComicLocation']
                    watch_comicid = watch_the_list['ComicID']
                    watch_comicname = watch_the_list['ComicName']
                    watch_comicyear = watch_the_list['ComicYear']
                    watch_comiciss = watch_the_list['ComicIssue']
                    print ("ComicLocation: " + str(watch_comlocation))
                    orig_comlocation = watch_the_list['OriginalLocation']
                    orig_filename = watch_the_list['OriginalFilename'] 
                    print ("Orig. Location: " + str(orig_comlocation))
                    print ("Orig. Filename: " + str(orig_filename))
                    #before moving check to see if Rename to Mylar structure is enabled.
                    if mylar.IMP_RENAME:
                        print("Renaming files according to configuration details : " + str(mylar.FILE_FORMAT))
                        renameit = helpers.rename_param(watch_comicid, watch_comicname, watch_comicyear, watch_comiciss)
                        nfilename = renameit['nfilename']
                    
                        dst_path = os.path.join(watch_comlocation,nfilename)
                        if str(watch_comicid) not in comicids:
                            comicids.append(watch_comicid)
                    else:
                        print("Renaming files not enabled, keeping original filename(s)")
                        dst_path = os.path.join(watch_comlocation,orig_filename)

                    #os.rename(os.path.join(self.nzb_folder, str(ofilename)), os.path.join(self.nzb_folder,str(nfilename + ext)))
                    #src = os.path.join(, str(nfilename + ext))
                    print ("I'm going to move " + str(orig_comlocation) + " to .." + str(dst_path))
                    try:
                        shutil.move(orig_comlocation, dst_path)
                    except (OSError, IOError):
                        logger.info("Failed to move directory - check directories and manually re-run.")
                    wat+=1
            else:
                # if move files isn't enabled, let's set all found comics to Archive status :)
                while (wat < watchfound):
                    watch_the_list = watchchoice['watchlist'][wat]
                    watch_comicid = watch_the_list['ComicID']
                    watch_issue = watch_the_list['ComicIssue']
                    print ("ComicID: " + str(watch_comicid))
                    print ("Issue#: " + str(watch_issue))
                    issuechk = myDB.selectone("SELECT * from issues where ComicID=? AND INT_IssueNumber=?", [watch_comicid, watch_issue]).fetchone()
                    if issuechk is None:
                        print ("no matching issues for this comic#")
                    else:
                        print("...Existing status: " + str(issuechk['Status']))
                        control = {"IssueID":   issuechk['IssueID']}
                        values = { "Status":   "Archived"}
                        print ("...changing status of " + str(issuechk['Issue_Number']) + " to Archived ")
                        myDB.upsert("issues", values, control)
                        if str(watch_comicid) not in comicids:
                            comicids.append(watch_comicid)                    
                    wat+=1
            if comicids is None: pass
            else:
                c_upd = len(comicids)
                c = 0
                while (c < c_upd ):
                    print ("Rescanning.. " + str(c))
                    updater.forceRescan(c) 
        if not len(import_by_comicids):
            return "Completed"
    if len(import_by_comicids) > 0:
        import_comicids['comic_info'] = import_by_comicids
        print ("import comicids: " + str(import_by_comicids))
        return import_comicids, len(import_by_comicids)


def scanLibrary(scan=None, queue=None):
    valreturn = []
    if scan:
        try:
            soma,noids = libraryScan()
        except Exception, e:
            logger.error('Unable to complete the scan: %s' % e)
            return
        if soma == "Completed":
            logger.info('Sucessfully completed import.')
        else:
            logger.info('Starting mass importing...' + str(noids) + ' records.')
            #this is what it should do...
            #store soma (the list of comic_details from importing) into sql table so import can be whenever
            #display webpage showing results
            #allow user to select comic to add (one at a time)
            #call addComic off of the webpage to initiate the add.
            #return to result page to finish or continue adding.
            #....
            #threading.Thread(target=self.searchit).start()
            #threadthis = threadit.ThreadUrl()
            #result = threadthis.main(soma)
            myDB = db.DBConnection()
            sl = 0
            logger.fdebug("number of records: " + str(noids))
            while (sl < int(noids)):
                soma_sl = soma['comic_info'][sl]
                logger.fdebug("soma_sl: " + str(soma_sl))
                logger.fdebug("comicname: " + soma_sl['comicname'].encode('utf-8'))
                logger.fdebug("filename: " + soma_sl['comfilename'].encode('utf-8'))
                controlValue = {"impID":    soma_sl['impid']}
                newValue = {"ComicYear":        soma_sl['comicyear'],
                            "Status":           "Not Imported",
                            "ComicName":        soma_sl['comicname'].encode('utf-8'),
                            "DisplayName":      soma_sl['displayname'].encode('utf-8'),
                            "ComicFilename":    soma_sl['comfilename'].encode('utf-8'),
                            "ComicLocation":    soma_sl['comlocation'].encode('utf-8'),
                            "ImportDate":       helpers.today(),
                            "WatchMatch":       soma_sl['watchmatch']}
                myDB.upsert("importresults", newValue, controlValue)
                sl+=1
            # because we could be adding volumes/series that span years, we need to account for this
            # add the year to the db under the term, valid-years
            # add the issue to the db under the term, min-issue

            #locate metadata here.
            # unzip -z filename.cbz will show the comment field of the zip which contains the metadata.

        #self.importResults()
        valreturn.append({"somevalue" :  'self.ie',
                          "result" :     'success'})
        return queue.put(valreturn)
        #raise cherrypy.HTTPRedirect("importResults")

