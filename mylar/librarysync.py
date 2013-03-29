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
    watchlist = myDB.action("SELECT * from comics")
    ComicName = []
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
        # let's clean up the name, just in case for comparison purposes...
        watchcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]', ' ', watch['ComicName']).encode('utf-8').strip()
        #watchcomic = re.sub('\s+', ' ', str(watchcomic)).strip()

        if ' the ' in watchcomic.lower():
            #drop the 'the' from the watchcomic title for proper comparisons.
            watchcomic = watchcomic[-4:]

        alt_chk = "no" # alt-checker flag (default to no)
         
        # account for alternate names as well
        if watch['AlternateSearch'] is not None and watch['AlternateSearch'] is not 'None':
            altcomic = re.sub('[\_\#\,\/\:\;\.\-\!\$\%\&\+\'\?\@]', ' ', watch['AlternateSearch']).encode('utf-8').strip()
            #altcomic = re.sub('\s+', ' ', str(altcomic)).strip()
            AltName.append(altcomic)
            alt_chk = "yes"  # alt-checker flag

        ComicName.append(watchcomic)
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

    for i in comic_list:
        print i['ComicFilename']

        comfilename = i['ComicFilename']
        comlocation = i['ComicLocation']
        #let's clean up the filename for matching purposes

        cfilename = re.sub('[\_\#\,\/\:\;\-\!\$\%\&\+\'\?\@]', ' ', comfilename)
        #cfilename = re.sub('\s', '_', str(cfilename))

        cm_cn = 0

        #we need to track the counter to make sure we are comparing the right array parts  
        #this takes care of the brackets :)
        m = re.findall('[^()]+', cfilename)
        lenm = len(m)
        print ("there are " + str(lenm) + " words.")
        cnt = 0
        yearmatch = "false"
        foundonwatch = "False"

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
                        print ("removed extension from filename.")
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
                        print ("word: " + str(cs[i]))
                        #assume once we find issue - everything prior is the actual title
                        #idetected = no will ignore everything so it will assume all title                            
                        if cs[i][:-2] == '19' or cs[i][:-2] == '20' and idetected == 'no':
                            print ("year detected: " + str(cs[i]))
                            ydetected = 'yes'
                            result_comyear = cs[i]
                        elif cs[i].isdigit() and idetected == 'no' or '.' in cs[i]:
                            issue = cs[i]
                            print ("issue detected : " + str(issue))
                            idetected = 'yes'
                            if '.' in cs[i]:
                                #make sure it's a number on either side of decimal and assume decimal issue.
                                decst = cs[i].find('.')
                                dec_st = cs[i][:decst]
                                dec_en = cs[i][decst+1:]
                                print ("st: " + str(dec_st))
                                print ("en: " + str(dec_en))
                                if dec_st.isdigit() and dec_en.isdigit():
                                    print ("decimal issue detected...adjusting.")
                                    issue = dec_st + "." + dec_en
                                    print ("issue detected: " + str(issue))
                                    idetected = 'yes'
                                else:
                                    print ("false decimal represent. Chunking to extra word.")
                                    cn = cn + cs[i] + " "
                                    break
                        elif '\#' in cs[i] or decimaldetect == 'yes':
                            print ("issue detected: " + str(cs[i]))
                            idetected = 'yes'

                        else: cn = cn + cs[i] + " "
                    if ydetected == 'no':
                        #assume no year given in filename...
                        result_comyear = "0000"
                    print ("cm?: " + str(cn))
                    comiss = issue
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
            cnt+=1

        splitit = []
        watchcomic_split = []
        logger.fdebug("filename comic and issue: " + cfilename)
        #changed this from '' to ' '
        comic_iss_b4 = re.sub('[\-\:\,]', ' ', com_NAME)
        comic_iss = comic_iss_b4.replace('.',' ')
        logger.fdebug("adjusted  comic and issue: " + str(comic_iss))
        #remove 'the' from here for proper comparisons.
        if ' the ' in comic_iss.lower():
            comic_iss = comic_iss[-4:]
        splitit = comic_iss.split(None)
        logger.fdebug("adjusting from: " + str(comic_iss_b4) + " to: " + str(comic_iss))
        #bmm = re.findall('v\d', comic_iss)
        #if len(bmm) > 0: splitst = len(splitit) - 2
        #else: splitst = len(splitit) - 1
      #-----
        #here we cycle through the Watchlist looking for a match.
        while (cm_cn < watchcnt):
            #setup the watchlist
            comname = ComicName[cm_cn]
            print ("watch_comic:" + comname)
            comyear = ComicYear[cm_cn]
            compub = ComicPublisher[cm_cn]
            comtotal = ComicTotal[cm_cn]
            comicid = ComicID[cm_cn]
            watch_location = ComicLocation[cm_cn]

#            if splitit[(len(splitit)-1)].isdigit():
#                #compares - if the last digit and second last digit are #'s seperated by spaces assume decimal
#                comic_iss = splitit[(len(splitit)-1)]
#                splitst = len(splitit) - 1
#                if splitit[(len(splitit)-2)].isdigit():
#                    # for series that have a digit at the end, it screws up the logistics.
#                    i = 1
#                    chg_comic = splitit[0]
#                    while (i < (len(splitit)-1)):
#                        chg_comic = chg_comic + " " + splitit[i]
#                        i+=1
#                    logger.fdebug("chg_comic:" + str(chg_comic))
#                    if chg_comic.upper() == comname.upper():
#                        logger.fdebug("series contains numerics...adjusting..")
#                    else:
#                        changeup = "." + splitit[(len(splitit)-1)]
#                        logger.fdebug("changeup to decimal: " + str(changeup))
#                        comic_iss = splitit[(len(splitit)-2)] + "." + comic_iss
#                        splitst = len(splitit) - 2
#            else:
              # if the nzb name doesn't follow the series-issue-year format even closely..ignore nzb
#               logger.fdebug("invalid naming format of filename detected - cannot properly determine issue")
#               continue

            # make sure that things like - in watchcomic are accounted for when comparing to nzb.

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
                            #comiss = splitit[n]
#                            comicNAMER = n - 1
#                            com_NAME = splitit[0]
#                           cmnam = 1
#                            while (cmnam <= comicNAMER):
#                                com_NAME = str(com_NAME) + " " + str(splitit[cmnam])
#                                cmnam+=1
#                            logger.fdebug("comic: " + str(com_NAME))
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
#                    if '.' in comic_iss:
#                        comisschk_find = comic_iss.find('.')
#                        comisschk_b4dec = comic_iss[:comisschk_find]
#                        comisschk_decval = comic_iss[comisschk_find+1:]
#                        logger.fdebug("Found IssueNumber: " + str(comic_iss))
#                        logger.fdebug("..before decimal: " + str(comisschk_b4dec))
#                        logger.fdebug("...after decimal: " + str(comisschk_decval))
#                        #--let's make sure we don't wipe out decimal issues ;)
#                        if int(comisschk_decval) == 0:
#                            ciss = comisschk_b4dec
#                            cintdec = int(comisschk_decval)
#                        else:
#                            if len(comisschk_decval) == 1:
#                                ciss = comisschk_b4dec + "." + comisschk_decval
#                                cintdec = int(comisschk_decval) * 10
#                            else:
#                                ciss = comisschk_b4dec + "." + comisschk_decval.rstrip('0')
#                                cintdec = int(comisschk_decval.rstrip('0')) * 10
#                        comintIss = (int(comisschk_b4dec) * 1000) + cintdec
#                    else:
#                        comintIss = int(comic_iss) * 1000
                    logger.fdebug("issue we found for is : " + str(comiss))
                    #set the year to the series we just found ;)
                    result_comyear = comyear
                    #issue comparison now as well
                    logger.info(u"Found " + comname + " (" + str(comyear) + ") issue: " + str(comiss))
#                    watchfound+=1
                    watchmatch = str(comicid)
#                    watch_kchoice.append({
#                       "ComicID":         str(comicid),
#                       "ComicName":       str(comname),
#                       "ComicYear":       str(comyear),
#                       "ComicIssue":      str(int(comic_iss)),
#                       "ComicLocation":   str(watch_location),
#                       "OriginalLocation" : str(comlocation),
#                       "OriginalFilename" : str(comfilename)
#                                        })
                    foundonwatch = "True"
                    break
                elif int(spercent) < 80:
                    logger.fdebug("failure - we only got " + str(spercent) + "% right!")
            cm_cn+=1

        if foundonwatch == "False":
            watchmatch = None
        #---if it's not a match - send it to the importer.
        n = 0
#        print ("comic_andiss : " + str(comic_andiss))
#        csplit = comic_andiss.split(None)
#        while ( n <= (len(csplit)-1) ):
#            print ("csplit:" + str(csplit[n]))
#            if csplit[n].isdigit():
#                logger.fdebug("issue detected")
#                comiss = splitit[n]
#                logger.fdebug("issue # : " + str(comiss))
#                comicNAMER = n - 1
#                com_NAME = csplit[0]
#                cmnam = 1
#                while (cmnam <= comicNAMER):
#                    com_NAME = str(com_NAME) + " " + str(csplit[cmnam])
#                    cmnam+=1
#                logger.fdebug("comic: " + str(com_NAME))
#            n+=1
        if result_comyear is None: result_comyear = '0000' #no year in filename basically.
        print ("adding " + com_NAME + " to the import-queue!")
        impid = com_NAME + "-" + str(result_comyear) + "-" + str(comiss)
        print ("impid: " + str(impid))
        import_by_comicids.append({ 
            "impid": impid,
            "watchmatch": watchmatch,
            "comicname" : com_NAME,
            "comicyear" : result_comyear,
            "comfilename" : comfilename,
            "comlocation" : comlocation.decode(mylar.SYS_ENCODING)
                                   })

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
                    issuechk = myDB.action("SELECT * from issues where ComicID=? AND INT_IssueNumber=?", [watch_comicid, watch_issue]).fetchone()
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
