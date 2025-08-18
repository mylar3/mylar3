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
import time
import datetime
import urllib.request, urllib.error, urllib.parse
import shlex
import operator
import re
import os
import itertools
import sys
import calendar

import mylar
from mylar import db, logger, helpers, filechecker

def addvialist(queue):
    while True:
        if queue.qsize() >= 1:
            time.sleep(3)
            item = queue.get(True)
            #logger.fdebug('addvialist - item: %s' % (item,))
            if item == 'exit':
                break
            try:
                r_mode = item['r_mode']
            except Exception:
                r_mode = None

            if r_mode == 'updateissuedata':
                logger.info('[MASS-REFRESH][WEEKLY-UPDATER] Now updating series data for %s (%s) [%s] ' % (item['comicname'], item['seriesyear'], item['comicid']))
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': item['comicname'], 'seriesyear': item['seriesyear'], 'comicid': item['comicid'], 'tables': 'both', 'message': 'Now refreshing %s (%s)' % (item['comicname'], item['seriesyear'])}
                mylar.importer.updateissuedata(item['comicid'], item['comicname'], calledfrom=item['calledfrom'], serieslast_updated=item['serieslast_updated'])
            elif r_mode == 'manualannual':
                logger.info('[MASS-REFRESH][WEEKLY-UPDATER][AnnualID:%s] Now updating series data for %s (%s) [%s] ' % (item['manual_comicid'], item['comicname'], item['seriesyear'], item['comicid']))
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': item['comicname'], 'seriesyear': item['seriesyear'], 'comicid': item['comicid'], 'tables': 'both', 'message': 'Now refreshing %s (%s)' % (item['comicname'], item['seriesyear'])}
                mylar.importer.manualAnnual(item['manual_comicid'], item['comicname'], comicyear=item['seriesyear'], comicid=item['comicid'], forceadd=True, serieslast_updated=item['serieslast_updated'])
            else:
                logger.info('[MASS-REFRESH][1/%s] Now refreshing %s (%s) [%s] ' % (queue.qsize()+1, item['comicname'], item['seriesyear'], item['comicid']))
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': item['comicname'], 'seriesyear': item['seriesyear'], 'comicid': item['comicid'], 'tables': 'both', 'message': 'Now refreshing %s (%s)' % (item['comicname'], item['seriesyear'])}
                dbUpdate([item['comicid']], calledfrom='refresh')
        else:
            mylar.REFRESH_QUEUE.put('exit')
    return False

def dbUpdate(ComicIDList=None, calledfrom=None, sched=False):
    if mylar.IMPORTLOCK:
        logger.info('Import is currently running - deferring this until the next scheduled run sequence.')
        return
    myDB = db.DBConnection()
    if ComicIDList is None:
        if mylar.CONFIG.UPDATE_ENDED:
            logger.info('Updating only Continuing Series (option enabled) - this might cause problems with the pull-list matching for rebooted series')
            comiclist = []
            completelist = myDB.select('SELECT LatestDate, ComicPublished, ForceContinuing, NewPublish, LastUpdated, ComicID, ComicName, Corrected_SeriesYear, Corrected_Type, ComicYear, Status from comics WHERE Status="Active" or Status="Loading" order by LastUpdated DESC, LatestDate ASC')
            for comlist in completelist:
                if comlist['LatestDate'] is None:
                    recentstatus = 'Loading'
                elif comlist['ComicPublished'] is None or comlist['ComicPublished'] == '' or comlist['LatestDate'] is None:
                    recentstatus = 'Unknown'
                elif comlist['ForceContinuing'] == 1:
                    recentstatus = 'Continuing'
                elif 'present' in comlist['ComicPublished'].lower() or (helpers.today()[:4] in comlist['LatestDate']):
                    latestdate = comlist['LatestDate']
                    c_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), 1)
                    n_date = datetime.date.today()
                    recentchk = (n_date - c_date).days
                    if comlist['NewPublish']:
                        recentstatus = 'Continuing'
                    else:
                        if recentchk < 55:
                            recentstatus = 'Continuing'
                        else:
                            recentstatus = 'Ended'
                else:
                    recentstatus = 'Ended'

                if recentstatus == 'Continuing':
                    comiclist.append({"LatestDate":            comlist['LatestDate'],
                                      "LastUpdated":           comlist['LastUpdated'],
                                      "ComicID":               comlist['ComicID'],
                                      "ComicName":             comlist['ComicName'],
                                      "ComicYear":             comlist['ComicYear'],
                                      "Status":                comlist['Status'],
                                      "Corrected_SeriesYear":  comlist['Corrected_SeriesYear'],
                                      "Corrected_Type":        comlist['Corrected_Type']})

        else:
            comiclist = myDB.select('SELECT LatestDate, LastUpdated, ComicID, ComicName, ComicYear, Corrected_SeriesYear, Corrected_Type, Status from comics WHERE Status="Active" or Status="Loading" order by LastUpdated DESC, latestDate ASC')
    else:
        comiclist = []
        comiclisting = ComicIDList
        for cl in comiclisting:
            comiclist += myDB.select('SELECT ComicID, ComicName, ComicYear, Corrected_SeriesYear, Corrected_Type, LastUpdated, Status from comics WHERE ComicID=? order by LastUpdated DESC, LatestDate ASC', [cl])

    if all([sched is False, calledfrom is None]):
        logger.info('Starting update for %i active comics' % len(comiclist))

    cnt = 1

    if sched is True:
       logger.fdebug('Refresh sequence set to fire every %s minutes for %s day(s)' % (mylar.DBUPDATE_INTERVAL, mylar.CONFIG.REFRESH_CACHE))

    for comic in sorted(comiclist, key=lambda x: x if isinstance(operator.itemgetter('LastUpdated'), str) else "", reverse=True):
        dspyear = comic['ComicYear']
        csyear = None
        fixed_type = None

        if comic['Corrected_Type'] is not None:
            fixed_type = comic['Corrected_Type']

        if comic['Corrected_SeriesYear'] is not None:
            csyear = comic['Corrected_SeriesYear']
            if int(csyear) != int(comic['ComicYear']):
                comic['ComicYear'] = csyear
                dspyear = csyear

        if ComicIDList is None:
            ComicID = comic['ComicID']
            ComicName = comic['ComicName']
            c_date = comic['LastUpdated']
            if c_date is None:
                logger.error(ComicName + ' failed during a previous add /refresh as it has no Last Update timestamp. Forcing refresh now.')
            else:
                c_obj_date = datetime.datetime.strptime(c_date, "%Y-%m-%d %H:%M:%S")
                n_date = datetime.datetime.now()
                absdiff = abs(n_date - c_obj_date)
                hours = (absdiff.days * 24 * 60 * 60 + absdiff.seconds) / 3600.0
                cache_hours = mylar.CONFIG.REFRESH_CACHE * 24
                if hours < cache_hours:
                    #logger.fdebug('%s [%s] Was refreshed less than %s hours ago. Skipping Refresh at this time.' % (ComicName, ComicID, cache_hours))
                    cnt +=1
                    continue
            logger.info('[%s/%s] Refreshing :%s (%s) [%s]' % (cnt, len(comiclist), ComicName, dspyear, ComicID))
        else:
            ComicID = comic['ComicID']
            ComicName = comic['ComicName']
            logger.info('Refreshing/Updating: %s (%s) [%s]' % (ComicName, dspyear, ComicID))

        pause_status = False
        if comic['Status'] == 'Paused':
            pause_status = True #Paused / Active

        lastupdated = '0000-00-00'
        if comic['LastUpdated'] is not None:
            lastupdated = datetime.datetime.strptime(comic['LastUpdated'], "%Y-%m-%d %H:%M:%S").strftime('%Y-%m-%d')

        mismatch = "no"
        if not mylar.CONFIG.CV_ONLY or ComicID[:1] == "G":

            CV_EXcomicid = myDB.selectone("SELECT * from exceptions WHERE ComicID=?", [ComicID]).fetchone()
            if CV_EXcomicid is None: pass
            else:
                if CV_EXcomicid['variloop'] == '99':
                    mismatch = "yes"
            if ComicID[:1] == "G":
                mylar.importer.GCDimport(ComicID)
            else:
                cchk = importer.addComictoDB(ComicID, mismatch)
        else:
            if mylar.CONFIG.CV_ONETIMER == 1:
                #if sched is True:
                #    helpers.job_management(write=True, job='DB Updater', current_run=helpers.utctimestamp(), status='Running')
                #    mylar.UPDATER_STATUS = 'Running'
                logger.fdebug("CV_OneTimer option enabled...")
                #in order to update to JUST CV_ONLY, we need to delete the issues for a given series so it's a clea$
                logger.fdebug("Gathering the status of all issues for the series.")
                issues = myDB.select('SELECT * FROM issues WHERE ComicID=?', [ComicID])

                if not issues:
                    #if issues are None it's probably a bad refresh/maxed out API that resulted in the issue data
                    #getting wiped out and not refreshed. Setting whack=True will force a complete refresh.
                    logger.fdebug('No issue data available. This is Whack.')
                    whack = True
                else:
                    #check for series that are numerically out of whack (ie. 5/4)
                    logger.fdebug('Checking how out of whack the series is.')
                    whack = helpers.havetotals(refreshit=ComicID)

                if calledfrom == 'weekly':
                    if whack == True:
                        logger.info('Series is out of whack. Forcibly refreshing series to ensure everything is in order.')
                        return True
                    else:
                        return False

                annload = []  #initiate the list here so we don't error out below.

                if mylar.CONFIG.ANNUALS_ON:
                    #now we load the annuals into memory to pass through to importer when refreshing so that it can
                    #refresh even the manually added annuals.
                    annual_load = myDB.select('SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted', [ComicID])
                    logger.fdebug('checking annual db')
                    for annthis in annual_load:
                        if not any(d['ReleaseComicID'] == annthis['ReleaseComicID'] for d in annload):
                            #print 'matched on annual'
                            annload.append({
                                  'ReleaseComicID':   annthis['ReleaseComicID'],
                                  'ReleaseComicName': annthis['ReleaseComicName'],
                                  'ComicID':          annthis['ComicID'],
                                  'ComicName':        annthis['ComicName'],
                                  'Deleted':          bool(annthis['Deleted'])
                                  })
                            #print 'added annual'
                    issues += annual_load #myDB.select('SELECT * FROM annuals WHERE ComicID=?', [ComicID])
                #store the issues' status for a given comicid, after deleting and readding, flip the status back to$
                #logger.fdebug("Deleting all issue data.")
                #myDB.action('DELETE FROM issues WHERE ComicID=?', [ComicID])
                #myDB.action('DELETE FROM annuals WHERE ComicID=?', [ComicID])
                logger.fdebug("Refreshing the series and pulling in new data using only CV.")

                lastissuedate = myDB.selectone('SELECT IssueDate, ReleaseDate FROM issues WHERE ComicID=? ORDER BY IssueDate DESC LIMIT 1', [ComicID]).fetchone()
                if not lastissuedate:
                    last_issuedate = '0000-00-00'  # set it to make sure every new issue gets autowanted if enabled.
                else:
                    last_issuedate = lastissuedate['IssueDate']
                    if any([last_issuedate is None, last_issuedate == '0000-00-00']):
                        last_issuedate = lastissuedate['ReleaseDate']

                if whack == False:
                    chkstatus = mylar.importer.addComictoDB(ComicID, mismatch, calledfrom='dbupdate', annload=annload, csyear=csyear, fixed_type=fixed_type)
                    if chkstatus['status'] == 'complete':
                        #delete the data here if it's all valid.
                        logger.fdebug("Deleting all old issue data to make sure new data is clean...")
                        myDB.action('DELETE FROM issues WHERE ComicID=?', [ComicID])
                        myDB.action('DELETE FROM annuals WHERE ComicID=?', [ComicID])
                        mylar.importer.issue_collection(chkstatus['issuedata'], nostatus='True', serieslast_updated=lastupdated)
                        #need to update annuals at this point too....
                        if chkstatus['anndata'] is not None:
                            mylar.importer.manualAnnual(annchk=chkstatus['anndata'])
                    else:
                        logger.warn('There was an error when refreshing this series - Make sure directories are writable/exist, and check the logs for any errors/problems.')
                        mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': ComicName, 'seriesyear': dspyear , 'comicid': ComicID, 'tables': 'both', 'message': 'Failure refreshing %s (%s)' % (ComicName, dspyear)}
                        return

                    issues_new = myDB.select('SELECT * FROM issues WHERE ComicID=?', [ComicID])
                    annuals = []
                    ann_list = []
                    #reload the annuals here.
                    if mylar.CONFIG.ANNUALS_ON:
                        annuals_list = myDB.select('SELECT * FROM annuals WHERE ComicID=?', [ComicID])
                        ann_list += annuals_list
                        issues_new += annuals_list

                    logger.fdebug("Attempting to put the Status' back how they were.")
                    icount = 0
                    #the problem - the loop below will not match on NEW issues that have been refreshed that weren't present in the
                    #db before (ie. you left Mylar off for abit, and when you started it up it pulled down new issue information)
                    #need to test if issuenew['Status'] is None, but in a seperate loop below.
                    fndissue = []
                    nowdate = datetime.datetime.now()
                    now_week = datetime.datetime.strftime(nowdate, "%Y%U")
                    for issue in issues:
                        for issuenew in issues_new:
                            #logger.fdebug(str(issue['Issue_Number']) + ' - issuenew:' + str(issuenew['IssueID']) + ' : ' + str(issuenew['Status']))
                            #logger.fdebug(str(issue['Issue_Number']) + ' - issue:' + str(issue['IssueID']) + ' : ' + str(issue['Status']))
                            try:
                                if issuenew['IssueID'] == issue['IssueID']:
                                    newVAL = None
                                    ctrlVAL = {"IssueID":      issue['IssueID']}
                                    if any([issuenew['Status'] != issue['Status'], issue['IssueDate_Edit'] is not None]):
                                        #if the status is None and the original status is either Downloaded / Archived, keep status & stats
                                        if issuenew['Status'] == None and (issue['Status'] == 'Downloaded' or issue['Status'] == 'Archived'):
                                            newVAL = {"Location":     issue['Location'],
                                                      "ComicSize":    issue['ComicSize'],
                                                      "Status":       issue['Status']}
                                        #if the status is now Downloaded/Snatched, keep status & stats (downloaded only)
                                        elif issuenew['Status'] == 'Downloaded' or issue['Status'] == 'Snatched':
                                            newVAL = {"Location":      issue['Location'],
                                                      "ComicSize":     issue['ComicSize']}
                                            if issuenew['Status'] == 'Downloaded':
                                                newVAL['Status'] = issuenew['Status']
                                            else:
                                                newVAL['Status'] = issue['Status']

                                        elif issue['Status'] == 'Archived':
                                            newVAL = {"Status":        issue['Status'],
                                                      "Location":      issue['Location'],
                                                      "ComicSize":     issue['ComicSize']}
                                        else:
                                            #change the status to the previous status
                                            newVAL = {"Status":        issue['Status']}

                                    if all([issuenew['Status'] == None, issue['Status'] == 'Skipped']):
                                        if issuenew['ReleaseDate'] == '0000-00-00':
                                            dk = re.sub('-', '', issue['IssueDate']).strip()
                                        else:
                                            dk = re.sub('-', '', issuenew['ReleaseDate']).strip() # converts date to 20140718 format
                                        if dk == '00000000':
                                            logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % issue['Issue_Number'])
                                            newVAL = {"Status":  "Skipped"}
                                        else:
                                            datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                                            issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                                            if pause_status is True:
                                                newVAL = {"Status": issue['Status']}
                                                logger.fdebug('[PAUSE-CATCH-STATUS] Series is Paused - keeping status of %s for #%s' % (issue['Status'], issue['Issue_Number']))
                                            else:
                                                if mylar.CONFIG.AUTOWANT_ALL:
                                                    newVAL = {"Status": "Wanted"}
                                                elif lastupdated is None:
                                                    logger.fdebug('serieslast_updated is None. Setting to Skipped')
                                                    newVAL = {"Status":"Skipped"}
                                                elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING:
                                                    logger.fdebug('Issue_week: %s -- now_week: %s' % (issue_week, now_week))
                                                    logger.fdebug('Issue date [%s] is in/beyond current week - marking as Wanted.' % dk)
                                                    newVAL = {"Status": "Wanted"}
                                                elif all([int(re.sub('-', '', lastupdated).strip()) < int(dk), mylar.CONFIG.AUTOWANT_UPCOMING is True]):
                                                    logger.info('Autowant upcoming triggered for issue #%s' % issuenew['Issue_Number'])
                                                    newVAL = {"Status": "Wanted"}
                                                else:
                                                    newVAL = {"Status":  "Skipped"}

                                    if newVAL is not None:
                                        if issue['IssueDate_Edit'] is not None:
                                            if issue['IssueDate_Edit'] == '0000-00-00':
                                                logger.fdebug('[#%s] Reverting previously edited Issue Date and replacing with CV Issue Date.' % issue['Issue_Number'])
                                                newVAL['IssueDate'] = issue['IssueDate']
                                                newVAL['IssueDate_Edit'] = None
                                            else:
                                                if issue['IssueDate_Edit'].endswith('s'):
                                                    issue_type = 'store'
                                                    newVAL['ReleaseDate'] = issue['ReleaseDate']
                                                else:
                                                    issue_type = 'cover'
                                                    newVAL['IssueDate'] = issue['IssueDate']
                                                logger.fdebug('[#%s] Detected manually edited %s Issue Date.' % (issue_type, issue['Issue_Number']))
                                                logger.fdebug('new value : ' + str(issue['IssueDate']) + ' ... cv value : ' + str(issuenew['IssueDate']))
                                                newVAL['IssueDate_Edit'] = issue['IssueDate_Edit']

                                        if any(d['IssueID'] == str(issue['IssueID']) for d in ann_list):
                                            logger.fdebug("annual detected for " + str(issue['IssueID']) + " #: " + str(issue['Issue_Number']))
                                            myDB.upsert("Annuals", newVAL, ctrlVAL)
                                        else:
                                            #logger.fdebug('#' + str(issue['Issue_Number']) + ' writing issuedata: ' + str(newVAL))
                                            myDB.upsert("Issues", newVAL, ctrlVAL)
                                        fndissue.append({"IssueID": issue['IssueID']})
                                        icount+=1
                                        break
                            except (RuntimeError, TypeError, ValueError, OSError) as e:
                                logger.warn('Something is out of whack somewhere with the series: %s' % e)
                                #if it's an annual (ie. deadpool-2011 ) on a refresh will throw index errors for some reason.
                            except:
                                logger.warn('Unexpected Error: %s' % sys.exc_info()[0])
                                raise

                    logger.info("In the process of converting the data to CV, I changed the status of " + str(icount) + " issues.")

                    issuesnew = myDB.select('SELECT * FROM issues WHERE ComicID=? AND Status is NULL', [ComicID])

                    newiss = []

                    for iss in issuesnew:
                        if iss['ReleaseDate'] == '0000-00-00':
                            dk = re.sub('-', '', iss['IssueDate']).strip()
                        else:
                            dk = re.sub('-', '', iss['ReleaseDate']).strip() # converts date to 20140718 format
                        if dk == '00000000':
                            logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % iss['Issue_Number'])
                            newstatus = "Skipped"
                        else:
                            datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                            issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                            logger.info('issue_week: %s' % issue_week)
                            if pause_status is True:
                                newstatus = "Skipped"
                                logger.fdebug('[PAUSE-ISSUE-CATCH-STATUS] Series is Paused, but new issue detected - setting status of %s for #%s' % (iss['Status'], iss['Issue_Number']))
                            else:
                                if mylar.CONFIG.AUTOWANT_ALL:
                                    logger.fdebug('autowant all')
                                    newstatus = "Wanted"
                                elif lastupdated is None:
                                    logger.fdebug('serieslast_updated is None. Setting to Skipped')
                                    newstatus = "Skipped"
                                elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING:
                                    logger.fdebug('Issue_week: %s -- now_week: %s' % (issue_week, now_week))
                                    logger.fdebug('Issue date [%s] is in/beyond current week - marking as Wanted.' % dk)
                                    newstatus = "Wanted"
                                elif all([int(re.sub('-', '', lastupdated).strip()) < int(dk), mylar.CONFIG.AUTOWANT_UPCOMING is True]):
                                    logger.info('Autowant upcoming triggered for issue #%s' % issue['Issue_Number'])
                                    newstatus = "Wanted"
                                else:
                                    logger.info('setting to Skipped')
                                    newstatus = "Skipped"
                        logger.fdebug('[#%s]status is : %s' % (iss['Issue_Number'], newstatus))

                        newiss.append({"IssueID":      iss['IssueID'],
                                       "Status":       newstatus,
                                       "Annual":       False})

                    if mylar.CONFIG.ANNUALS_ON:
                        annualsnew = myDB.select('SELECT * FROM annuals WHERE ComicID=? AND Status is NULL', [ComicID])

                        for ann in annualsnew:
                            if iss['ReleaseDate'] == '0000-00-00':
                                dk = re.sub('-', '', iss['IssueDate']).strip()
                            else:
                                dk = re.sub('-', '', iss['ReleaseDate']).strip() # converts date to 20140718 format
                            if dk == '00000000':
                                logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % iss['Issue_Number'])
                                newstatus = "Skipped"
                            else:
                                datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                                issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                                logger.info('issue_week: %s' % issue_week)
                                if pause_status is True:
                                    newstatus = ann['Status']
                                    logger.fdebug('[PAUSE-ANNUAL-CATCH-STATUS] Series is Paused - keeping status of %s for #%s' % (ann['Status'], ann['Issue_Number']))
                                else:
                                    if mylar.CONFIG.AUTOWANT_ALL:
                                        logger.fdebug('autowant all')
                                        newstatus = "Wanted"
                                    elif lastupdated is None:
                                        logger.fdebug('serieslast_updated is None. Setting to Skipped')
                                        newstatus = "Skipped"
                                    elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING:
                                        logger.fdebug('Issue_week: %s -- now_week: %s' % (issue_week, now_week))
                                        logger.fdebug('Issue date [%s] is in/beyond current week - marking as Wanted.' % dk)
                                        newstatus = "Wanted"
                                    elif all([int(re.sub('-', '', lastupdated).strip()) < int(dk), mylar.CONFIG.AUTOWANT_UPCOMING is True]):
                                        logger.info('Autowant upcoming triggered for issue #%s' % issue['Issue_Number'])
                                        newstatus = "Wanted"
                                    else:
                                        logger.info('setting to Skipped')
                                        newstatus = "Skipped"
                            logger.fdebug('[#%s]status is : %s' % (iss['Issue_Number'], newstatus))

                            newiss.append({"IssueID":      iss['IssueID'],
                                           "Status":       newstatus,
                                           "Annual":       True})

                    if len(newiss) > 0:
                         for newi in newiss:
                             ctrlVAL = {"IssueID":   newi['IssueID']}
                             newVAL = {"Status":     newi['Status']}
                             #logger.fdebug('writing issuedata: ' + str(newVAL))
                             if newi['Annual'] == True:
                                 myDB.upsert("Annuals", newVAL, ctrlVAL)
                             else:
                                 myDB.upsert("Issues", newVAL, ctrlVAL)

                    logger.info('I have added ' + str(len(newiss)) + ' new issues for this series that were not present before.')
                    forceRescan(ComicID)

                    #series.json updater here (after all data written out)
                    if not calledfrom == 'json_api' and mylar.CONFIG.SERIES_METADATA_LOCAL is True:
                        sm = mylar.series_metadata.metadata_Series(ComicID, bulk=False, api=False)
                        sm.update_metadata()

                else:
                    chkstatus = mylar.importer.addComictoDB(ComicID, mismatch, annload=annload, csyear=csyear)
                    #if cchk:
                    #    #delete the data here if it's all valid.
                    #    #logger.fdebug("Deleting all old issue data to make sure new data is clean...")
                    #    myDB.action('DELETE FROM issues WHERE ComicID=?', [ComicID])
                    #    myDB.action('DELETE FROM annuals WHERE ComicID=?', [ComicID])
                    #    mylar.importer.issue_collection(cchk, nostatus='True')
                    #    #need to update annuals at this point too....
                    #    if annchk:
                    #        mylar.importer.manualAnnual(annchk=annchk)

            else:
                chkstatus = mylar.importer.addComictoDB(ComicID, mismatch)

        cnt += 1
        if all([sched is False, calledfrom != 'refresh', len(comiclist) > 1]):
            time.sleep(15) #pause for 15 secs so dont hammer CV and get 500 error
        else:
            if calledfrom == 'refresh':
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': ComicName, 'seriesyear': dspyear , 'comicid': ComicID, 'tables': 'both', 'message': 'Successfully refreshed %s (%s)' % (ComicName, dspyear)}
            break

    #helpers.job_management(write=True, job='DB Updater', last_run_completed=helpers.utctimestamp(), status='Waiting')
    #mylar.UPDATER_STATUS = 'Waiting'
    logger.fdebug('Update complete')

def latest_update(ComicID, LatestIssue, LatestDate, ReleaseComicID=None):
    # here we add to comics.latest
    logger.fdebug(str(ComicID) + ' - updating latest_date to : ' + str(LatestDate))
    myDB = db.DBConnection()
    cid = ComicID
    if mylar.CONFIG.ANNUALS_ON:
        logger.fdebug('checking for releasecomicid %s reference in annuals table' % ReleaseComicID)
        db_check = myDB.selectone("SELECT ComicID from Annuals WHERE ReleaseComicID=?", [ReleaseComicID]).fetchone()
        if not db_check:
            logger.fdebug('Annual has not been added yet to series')
        else:
            cid = db_check[0]
            logger.fdebug('ReleaseComicID found of %s linking to series %s' % (ReleaseComicID, cid))
            if cid != ComicID:
                cid = ComicID
            #might have to set the issue to something like 'Annual %s' % LatestIssue ?

    latestCTRLValueDict = {"ComicID":      cid}
    newlatestDict = {"LatestIssue":      str(LatestIssue),
                     "intLatestIssue":   helpers.issue_number_parser(LatestIssue).asInt,
                     "LatestDate":       str(LatestDate)}
    myDB.upsert("comics", newlatestDict, latestCTRLValueDict)

def upcoming_update(ComicID, ComicName, IssueNumber, IssueDate, forcecheck=None, futurepull=None, altissuenumber=None, weekinfo=None, releasecomicid=None):
    # here we add to upcoming table...
    myDB = db.DBConnection()
    dspComicName = ComicName #to make sure that the word 'annual' will be displayed on screen
    if 'annual' in ComicName.lower():
        year_check = re.findall(r'(\d{4})(?=[\s]|annual\b|$)', ComicName, flags=re.I)
        if year_check:
            ann_line = '%s annual' % year_check[0]
            logger.fdebug('ann_line: %s' % ann_line)
            adjComicName = re.sub(ann_line, '', ComicName, flags=re.I).strip()
        else:
            adjComicName = re.sub("\\bannual\\b", "", ComicName, flags=re.I).strip() # for use with comparisons.
        logger.fdebug('annual detected - adjusting name to : %s' % adjComicName)
    else:
        adjComicName = ComicName
    controlValue = {"ComicID":      ComicID}
    newValue = {"ComicName":        adjComicName,
                "IssueNumber":      str(IssueNumber),
                "DisplayComicName": dspComicName,
                "IssueDate":        str(IssueDate)}

    #let's refresh the series here just to make sure if an issue is available/not.
    mismatch = "no"

    if mylar.CONFIG.ALT_PULL != 2 or mylar.PULLBYFILE is True:
        lastupdatechk = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [ComicID]).fetchone()
        if lastupdatechk is None:
            pullupd = "yes"
        else:
            c_date = lastupdatechk['LastUpdated']
            if c_date is None:
                logger.error(lastupdatechk['ComicName'] + ' failed during a previous add /refresh. Please either delete and readd the series, or try a refresh of the series.')
                return
            c_obj_date = datetime.datetime.strptime(c_date, "%Y-%m-%d %H:%M:%S")
            n_date = datetime.datetime.now()
            absdiff = abs(n_date - c_obj_date)
            hours = (absdiff.days * 24 * 60 * 60 + absdiff.seconds) / 3600.0
    else:
        #if it's at this point and the refresh is None, odds are very good that it's already up-to-date so let it flow thru
        if mylar.CONFIG.PULL_REFRESH is None:
            mylar.CONFIG.PULL_REFRESH = datetime.datetime.today().replace(second=0,microsecond=0)
            #update the PULL_REFRESH 
            #mylar.config_write()
        logger.fdebug('pull_refresh: ' + str(mylar.CONFIG.PULL_REFRESH))
        c_obj_date = datetime.datetime.strptime(str(mylar.CONFIG.PULL_REFRESH),"%Y-%m-%d %H:%M:%S")
        #logger.fdebug('c_obj_date: ' + str(c_obj_date))
        n_date = datetime.datetime.now()
        #logger.fdebug('n_date: ' + str(n_date))
        absdiff = abs(n_date - c_obj_date)
        #logger.fdebug('absdiff: ' + str(absdiff))
        hours = (absdiff.days * 24 * 60 * 60 + absdiff.seconds) / 3600.0
        #logger.fdebug('hours: ' + str(hours))

    if any(['annual' in ComicName.lower(), 'special' in ComicName.lower()]):
        if mylar.CONFIG.ANNUALS_ON:
            logger.info('checking: ' + str(ComicID) + ' -- issue#: ' + str(IssueNumber))
            issuechk = myDB.selectone("SELECT * FROM annuals WHERE ReleaseComicID=? AND Issue_Number=?", [ComicID, IssueNumber]).fetchone()
        else:
            logger.fdebug('Non-standard issue detected (annual/special/etc), but Annual Integration is not enabled. Ignoring result.')
            return
    else:
        issuechk = myDB.selectone("SELECT * FROM issues WHERE ComicID=? AND Issue_Number=?", [ComicID, IssueNumber]).fetchone()
    if issuechk is None and altissuenumber is not None:
        logger.info('altissuenumber is : ' + str(altissuenumber))
        issuechk = myDB.selectone("SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?", [ComicID, helpers.issue_number_parser(altissuenumber).asInt]).fetchone()

    if issuechk is not None:
        if issuechk['Issue_Number'] == IssueNumber or issuechk['Issue_Number'] == altissuenumber:
            og_status = issuechk['Status']
            #safety check - make sure the date for the issue in the db matches or is close to the one being polled against (ie. pull date)
            wk_info = helpers.weekly_info(weekinfo['weeknumber'], weekinfo['year'])
            if all([issuechk['ReleaseDate'] is not None, issuechk['ReleaseDate'] != '0000-00-00']):
               issue_checkdate = issuechk['ReleaseDate']
            elif all([issuechk['DigitalDate'] is not None, issuechk['DigitalDate'] != '0000-00-00']):
               issue_checkdate = issuechk['DigitalDate']
            else:
               issue_checkdate = issuechk['IssueDate']

            wkds = datetime.datetime.strptime(wk_info['startweek'], '%B %d, %Y')
            wkstr = wkds - datetime.timedelta(days = 2)
            wk_start = wkstr.strftime('%Y-%m-%d')

            wkde = datetime.datetime.strptime(wk_info['endweek'], '%B %d, %Y')
            wkend = wkde + datetime.timedelta(days = 2)
            wk_end = wkend.strftime('%Y-%m-%d')

            if issue_checkdate != '0000-00-00' and not ( re.sub('-', '', wk_end) >= re.sub('-', '', issue_checkdate) >= re.sub('-', '', wk_start) ):
                logger.info('[IssueDate:%s] is not within the range of [Pulldate:%s - %s]. Incorrect match being imposed by WS - please log an issue if this has not fixed itself within a few hours' %(issue_checkdate, wk_info['startweek'], wk_info['endweek']))
                if IssueNumber is not None:
                    presentline = '%s #%s' % (ComicName, IssueNumber)
                else:
                    presentline = '%s' % (ComicName)
                logger.info('[%s][comicid: %s][issueid: %s] ' % (presentline, ComicID, issuechk['IssueID'])
)
                # if it was previously marked as Wanted (prior to this patch) - let's revert so we don't download the wrong thing repeatidly
                if issuechk['Status'] == 'Wanted':
                    control = {"IssueID":   issuechk['IssueID']}
                    newchk = {'Status': 'Skipped'}
                    myDB.upsert("issues", newchk, control)
                return {"Status":  'incorrect_match',
                        "ComicID": ComicID,
                        "IssueID": issuechk['IssueID']}
                #return 'incorrect_match'
            else:
                #check for 'out-of-whack' series here.
                whackness = dbUpdate([ComicID], calledfrom='weekly', sched=False)
                if any([whackness == True, og_status is None]):
                    if any([issuechk['Status'] == 'Downloaded', issuechk['Status'] == 'Archived', issuechk['Status'] == 'Snatched']):
                        logger.fdebug('Forcibly maintaining status of : ' + og_status + ' for #' + issuechk['Issue_Number'] + ' to ensure integrity.')
                    logger.fdebug('Comic series has an incorrect total count. Forcily refreshing series to ensure data is current.')
                    dbUpdate([ComicID])
                    issuechk = myDB.selectone("SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?", [ComicID, helpers.issue_number_parser(IssueNumber).asInt]).fetchone()
                    if issuechk['Status'] != og_status and (issuechk['Status'] != 'Downloaded' or issuechk['Status'] != 'Archived' or issuechk['Status'] != 'Snatched'):
                        logger.fdebug('Forcibly changing status of %s back to %s for #%s to stop repeated downloads.' % (issuechk['Status'], og_status, issuechk['Issue_Number']))
                    else:
                        logger.fdebug('[%s] / [%s] Status has not changed during refresh or is marked as being Wanted/Skipped correctly.' % (issuechk['Status'], og_status))
                        og_status = issuechk['Status']
                else:
                    logger.fdebug('Comic series already up-to-date ... no need to refresh at this time.')

                logger.fdebug('Available to be marked for download - checking...' + adjComicName + ' Issue: ' + str(issuechk['Issue_Number']))
                logger.fdebug('...Existing status: ' + og_status)
                control = {"IssueID":   issuechk['IssueID']}
                newValue['IssueID'] = issuechk['IssueID']
                if og_status == "Snatched":
                    values = {"Status":   "Snatched"}
                    newValue['Status'] = "Snatched"
                elif og_status == "Downloaded":
                    values = {"Status":    "Downloaded"}
                    newValue['Status'] = "Downloaded"
                    #if the status is Downloaded and it's on the pullist - let's mark it so everyone can bask in the glory

                elif og_status == "Wanted":
                    values = {"Status":    "Wanted"}
                    newValue['Status'] = "Wanted"
                elif og_status == "Archived":
                    values = {"Status":    "Archived"}
                    newValue['Status'] = "Archived"
                elif og_status == 'Failed':
                    if mylar.CONFIG.FAILED_DOWNLOAD_HANDLING:
                        if mylar.CONFIG.FAILED_AUTO:
                            values = {"Status":   "Wanted"}
                            newValue['Status'] = "Wanted"
                        else:
                            values = {"Status":   "Failed"}
                            newValue['Status'] = "Failed"
                    else:
                        values = {"Status":   "Skipped"}
                        newValue['Status'] = "Skipped"
                else:
                    values = {"Status":    "Skipped"}
                    newValue['Status'] = "Skipped"
                #was in wrong place :(
        else:
            logger.fdebug('Issues do not match for some reason...weekly new issue: %s' % IssueNumber)
            return

    if issuechk is None:
        if futurepull is None:
            og_status = None
            if mylar.CONFIG.ALT_PULL != 2 or mylar.PULLBYFILE is True:
                logger.fdebug(adjComicName + ' Issue: ' + str(IssueNumber) + ' not present in listings to mark for download...updating comic and adding to Upcoming Wanted Releases.')
                # we need to either decrease the total issue count, OR indicate that an issue is upcoming.
                upco_results = myDB.select("SELECT COUNT(*) FROM UPCOMING WHERE ComicID=?", [ComicID])
                upco_iss = upco_results[0][0]
                #logger.info("upco_iss: " + str(upco_iss))
                if int(upco_iss) > 0:
                    #logger.info("There is " + str(upco_iss) + " of " + str(ComicName) + " that's not accounted for")
                    newKey = {"ComicID": ComicID}
                    newVal = {"not_updated_db": str(upco_iss)}
                    myDB.upsert("comics", newVal, newKey)
                elif int(upco_iss) <=0 and lastupdatechk['not_updated_db']:
                    #if not_updated_db has a value, and upco_iss is > 0, let's zero it back out cause it's updated now.
                    newKey = {"ComicID": ComicID}
                    newVal = {"not_updated_db": ""}
                    myDB.upsert("comics", newVal, newKey)

                if hours > 5 or forcecheck == 'yes':
                    pullupd = "yes"
                    logger.fdebug('Now Refreshing comic ' + ComicName + ' to make sure it is up-to-date')
                    if ComicID[:1] == "G":
                        mylar.importer.GCDimport(ComicID, pullupd)
                    else:
                        cchk = mylar.importer.updateissuedata(ComicID, ComicName, calledfrom='weeklycheck') #mylar.importer.addComictoDB(ComicID,mismatch,pullupd)
                else:
                    logger.fdebug('It has not been longer than 5 hours since we last did this...we will wait so we do not hammer things.')
            else:
                logger.fdebug('[WEEKLY-PULL] Walksoftly has been enabled. ComicID/IssueID control given to the ninja to monitor.')
                logger.fdebug('hours: ' + str(hours) + ' -- forcecheck: ' + str(forcecheck))
                if hours > 2 or forcecheck == 'yes':
                    logger.fdebug('weekinfo:' + str(weekinfo))
                    mylar.CONFIG.PULL_REFRESH = datetime.datetime.today().replace(second=0,microsecond=0)
                    #update the PULL_REFRESH
                    #mylar.config_write()
                    chkitout = mylar.locg.locg(weeknumber=str(weekinfo['weeknumber']),year=str(weekinfo['year']))

            logger.fdebug('linking ComicID to Pull-list to reflect status.')
            downstats = {"ComicID": ComicID,
                         "IssueID": None,
                         "Status": None}
            return downstats
        else:
            # if futurepull is not None, let's just update the status and ComicID
            # NOTE: THIS IS CREATING EMPTY ENTRIES IN THE FUTURE TABLE. ???
            nKey = {"ComicID": ComicID}
            nVal = {"Status": "Wanted"}
            myDB.upsert("future", nVal, nKey)
            return

    if mylar.CONFIG.AUTOWANT_UPCOMING:
        #for issues not in db - to be added to Upcoming table.
        if og_status is None:
            newValue['Status'] = "Wanted"
            logger.fdebug('...Changing Status to Wanted and throwing it in the Upcoming section since it is not published yet.')
        #this works for issues existing in DB...
        elif og_status == "Skipped":
            newValue['Status'] = "Wanted"
            values = {"Status":  "Wanted"}
            logger.fdebug('...New status of Wanted')
        elif og_status == "Wanted":
            logger.fdebug('...Status already Wanted .. not changing.')
        else:
            logger.fdebug('...Already have issue - keeping existing status of : ' + og_status)

    if issuechk is None:
        myDB.upsert("upcoming", newValue, controlValue)
        logger.fdebug('updating Pull-list to reflect status.')
        downstats = {"Status":  newValue['Status'],
                     "ComicID": ComicID,
                     "IssueID": None}
        return downstats

    else:
        logger.fdebug('--attempt to find errant adds to Wanted list')
        logger.fdebug('UpcomingNewValue: ' + str(newValue))
        logger.fdebug('UpcomingcontrolValue: ' + str(controlValue))
        if issuechk['IssueDate'] == '0000-00-00' and newValue['IssueDate'] != '0000-00-00':
            logger.fdebug('Found a 0000-00-00 issue - force updating series to try and get it proper.')
            dateVal = {"IssueDate":        newValue['IssueDate'],
                       "ComicName":        issuechk['ComicName'],
                       "Status":           newValue['Status'],
                       "IssueNumber":      issuechk['Issue_Number']}
            logger.fdebug('updating date in upcoming table to : ' + str(newValue['IssueDate']) + '[' + newValue['Status'] + ']')
            logger.fdebug('ComicID:' + str(controlValue))
            myDB.upsert("upcoming", dateVal, controlValue)
            logger.fdebug('Temporarily putting the Issue Date for ' + str(issuechk['Issue_Number']) + ' to ' + str(newValue['IssueDate']))
            values = {"IssueDate":  newValue['IssueDate']}
            #if ComicID[:1] == "G": mylar.importer.GCDimport(ComicID,pullupd='yes')
            #else: mylar.importer.addComictoDB(ComicID,mismatch,pullupd='yes')

        if any(['annual' in ComicName.lower(), 'special' in ComicName.lower()]):
            myDB.upsert("annuals", values, control)
        else:
            myDB.upsert("issues", values, control)

        if any([og_status == 'Downloaded', og_status == 'Archived', og_status == 'Snatched', og_status == 'Wanted', newValue['Status'] == 'Wanted']):
            logger.fdebug('updating Pull-list to reflect status change: ' + og_status + '[' + newValue['Status'] + ']')
            if og_status != 'Skipped':
                downstats = {"Status":  og_status,
                             "ComicID": issuechk['ComicID'],
                             "IssueID": issuechk['IssueID']}
            else:
                downstats = {"Status":  newValue['Status'],
                             "ComicID": issuechk['ComicID'],
                             "IssueID": issuechk['IssueID']}
            return downstats


def weekly_update(ComicName, IssueNumber, CStatus, CID, weeknumber, year, altissuenumber=None):
    logger.fdebug('Weekly Update for week ' + str(weeknumber) + '-' + str(year) + ' : ' + str(ComicName) + ' #' + str(IssueNumber) + ' to a status of ' + str(CStatus))

    if altissuenumber:
        logger.fdebug('weekly_update of table : ' + str(ComicName) + ' (Alternate Issue #):' + str(altissuenumber) + ' to a status of ' + str(CStatus))

    # here we update status of weekly table...
    # added Issue to stop false hits on series' that have multiple releases in a week
    # added CStatus to update status flags on Pullist screen
    myDB = db.DBConnection()
    issuecheck = myDB.selectone("SELECT * FROM weekly WHERE COMIC=? AND ISSUE=? and WEEKNUMBER=? AND YEAR=?", [ComicName, IssueNumber, int(weeknumber), year]).fetchone()

    if issuecheck is not None:
        controlValue = {"COMIC":         str(ComicName),
                        "ISSUE":         str(IssueNumber),
                        "WEEKNUMBER":    int(weeknumber),
                        "YEAR":          year}

        logger.info('controlValue:' + str(controlValue))
        try:
            if CID['IssueID']:
                cidissueid = CID['IssueID']
            else:
                cidissueid = None
        except:
            cidissueid = None

        logger.info('CStatus:' + str(CStatus))

        if CStatus:
            newValue = {"STATUS":      CStatus}

        else:
            if mylar.CONFIG.AUTOWANT_UPCOMING:
                newValue = {"STATUS":      "Wanted"}
            else:
                newValue = {"STATUS":      "Skipped"}

        #setting this here regardless, as it will be a match for a watchlist hit at this point anyways - so link it here what's availalbe.
        newValue['ComicID'] = CID['ComicID']
        newValue['IssueID'] = cidissueid

        logger.info('newValue:' + str(newValue))

        myDB.upsert("weekly", newValue, controlValue)

def newpullcheck(ComicName, ComicID, issue=None):
    # When adding a new comic, let's check for new issues on this week's pullist and update.
    if mylar.CONFIG.ALT_PULL != 2 or mylar.PULLBYFILE is True:
        mylar.weeklypull.pullitcheck(comic1off_name=ComicName, comic1off_id=ComicID, issue=issue)
    else:
        mylar.weeklypull.new_pullcheck(weeknumber=mylar.CURRENT_WEEKNUMBER, pullyear=mylar.CURRENT_YEAR, comic1off_name=ComicName, comic1off_id=ComicID, issue=issue)
    return

def no_searchresults(ComicID):
    # when there's a mismatch between CV & GCD - let's change the status to
    # something other than 'Loaded'
    myDB = db.DBConnection()
    controlValue = {"ComicID":        ComicID}
    newValue = {"Status":       "Error",
                "LatestDate":   "Error",
                "LatestIssue":  "Error"}
    myDB.upsert("comics", newValue, controlValue)

def nzblog(IssueID, NZBName, ComicName, SARC=None, IssueArcID=None, id=None, prov=None, alt_nzbname=None, oneoff=False):
    myDB = db.DBConnection()

    newValue = {'NZBName':  NZBName}

    if SARC:
       logger.fdebug("Story Arc (SARC) detected as: " + str(SARC))
       IssueID = 'S' + str(IssueArcID)
       newValue['SARC'] = SARC

    if oneoff is True:
       logger.fdebug('One-Off download detected when updating - crossing the t\'s and dotting the i\'s so things work...')
       newValue['OneOff'] = True

    if IssueID is None or IssueID == 'None':
       #if IssueID is None, it's a one-off download from the pull-list.
       #give it a generic ID above the last one so it doesn't throw an error later.
       if any([mylar.CONFIG.HIGHCOUNT == 0, mylar.CONFIG.HIGHCOUNT is None]):
           mylar.CONFIG.HIGHCOUNT = 900000
       else:
           mylar.CONFIG.HIGHCOUNT+=1

       IssueID = mylar.CONFIG.HIGHCOUNT
       #mylar.config_write()

    controlValue = {"IssueID":  IssueID,
                    "Provider": prov}


    if id:
        logger.info('setting the nzbid for this download grabbed by ' + prov + ' in the nzblog to : ' + str(id))
        newValue['ID'] = id

    if alt_nzbname:
        logger.info('setting the alternate nzbname for this download grabbed by ' + prov + ' in the nzblog to : ' + alt_nzbname)
        newValue['AltNZBName'] = alt_nzbname

    #check if it exists already in the log.
    chkd = myDB.selectone('SELECT * FROM nzblog WHERE IssueID=? and Provider=?', [IssueID, prov]).fetchone()
    if chkd is None:
        pass
    else:
        altnames = chkd['AltNZBName']
        if any([altnames is None, altnames == '']):
            #we need to wipe the entry so we can re-update with the alt-nzbname if required
            myDB.action('DELETE FROM nzblog WHERE IssueID=? and Provider=?', [IssueID, prov])
            logger.fdebug('Deleted stale entry from nzblog for IssueID: ' + str(IssueID) + ' [' + prov + ']')
    myDB.upsert("nzblog", newValue, controlValue)


def foundsearch(ComicID, IssueID, mode=None, down=None, provider=None, SARC=None, IssueArcID=None, module=None, hash=None, crc=None, comicname=None, issuenumber=None, pullinfo=None):
    # When doing a Force Search (Wanted tab), the resulting search calls this to update.

    # this is all redudant code that forceRescan already does.
    # should be redone at some point so that instead of rescanning entire
    # series directory, it just scans for the issue it just downloaded and
    # and change the status to Snatched accordingly. It is not to increment the have count
    # at this stage as it's not downloaded - just the .nzb has been snatched and sent to SAB.
    if module is None:
        module = ''
    module += '[UPDATER]'

    myDB = db.DBConnection()
    modcomicname = False

    logger.fdebug(module + ' comicid: ' + str(ComicID))
    logger.fdebug(module + ' issueid: ' + str(IssueID))
    seriesyear = None
    if mode != 'pullwant':
        if mode != 'story_arc':
            comic = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
            ComicName = comic['ComicName']
            seriesyear = comic['ComicYear']
            if mode == 'want_ann':
                issue = myDB.selectone('SELECT * FROM annuals WHERE IssueID=?', [IssueID]).fetchone()
                if ComicName != issue['ReleaseComicName'] + ' Annual':
                    ComicName = issue['ReleaseComicName']
                    modcomicname = True
            else:
                issue = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [IssueID]).fetchone()
            CYear = issue['IssueDate'][:4]
            IssueNum = issue['Issue_Number']

        else:
            issue = myDB.selectone('SELECT * FROM storyarcs WHERE IssueArcID=?', [IssueArcID]).fetchone()
            ComicName = issue['ComicName']
            CYear = issue['IssueYEAR']
            IssueNum = issue['IssueNumber']
    else:
        oneinfo = myDB.selectone('SELECT * FROM weekly WHERE IssueID=?', [IssueID]).fetchone()
        if oneinfo is None:
            ComicName = comicname
            IssueNum = issuenumber
            onefail = True
        else:
            ComicName = oneinfo['COMIC']
            IssueNum = oneinfo['ISSUE']
            onefail = False

    if down is None:
        # update the status to Snatched (so it won't keep on re-downloading!)
        logger.info(module + ' Updating status to snatched')
        logger.fdebug(module + ' Provider is ' + provider)
        if hash:
            logger.fdebug(module + ' Hash set to : ' + hash)
        newValue = {"Status":    "Snatched"}
        if mode == 'story_arc':
            cValue = {"IssueArcID": IssueArcID}
            snatchedupdate = {"IssueArcID": IssueArcID}
            myDB.upsert("storyarcs", newValue, cValue)
            # update the snatched DB
            snatchedupdate = {"IssueID":     IssueArcID,
                              "Status":      "Snatched",
                              "Provider":    provider
                              }

        else:
            if mode == 'want_ann':
                controlValue = {"IssueID":   IssueID}
                myDB.upsert("annuals", newValue, controlValue)
            else:
                controlValue = {"IssueID":   IssueID}
                if mode != 'pullwant':
                    myDB.upsert("issues", newValue, controlValue)

            # update the snatched DB
            snatchedupdate = {"IssueID":     IssueID,
                              "Status":      "Snatched",
                              "Provider":    provider
                              }

        if mode == 'story_arc':
            IssueNum = issue['IssueNumber']
            newsnatchValues = {"ComicName":       ComicName,
                               "ComicID":         ComicID, #'None',
                               "Issue_Number":    IssueNum,
                               "DateAdded":       helpers.now(),
                               "Status":          "Snatched",
                               "Hash":            hash
                               }

            myDB.upsert("snatched", newsnatchValues, snatchedupdate)

        elif mode != 'pullwant':
            if modcomicname:
                IssueNum = issue['Issue_Number']
            else:
                if mode == 'want_ann':
                    IssueNum = "Annual " + issue['Issue_Number']
                else:
                    IssueNum = issue['Issue_Number']

            newsnatchValues = {"ComicName":       ComicName,
                               "ComicID":         ComicID,
                               "Issue_Number":    IssueNum,
                               "DateAdded":       helpers.now(),
                               "Status":          "Snatched",
                               "Hash":            hash
                               }

            myDB.upsert("snatched", newsnatchValues, snatchedupdate)

        else:
             #updating snatched table with one-off is abit difficult due to lack of complete information in some instances
             #ie. alt_pull 2 not populated yet, alt_pull 0 method in general doesn't have enough info....

            newsnatchValues = {"ComicName":       ComicName,
                               "ComicID":         ComicID,
                               "IssueID":        IssueID,
                               "Issue_Number":    IssueNum,
                               "DateAdded":       helpers.now(),
                               "Status":          "Snatched",
                               "Hash":            hash
                               }

            myDB.upsert("snatched", newsnatchValues, snatchedupdate)

        #this will update the weeklypull list immediately after snatching to reflect the new status.
        #-is ugly, should be linked directly to other table (IssueID should be populated in weekly pull at this point hopefully).
        chkit = myDB.selectone("SELECT * FROM weekly WHERE ComicID=? AND IssueID=?", [ComicID, IssueID]).fetchone()

        if chkit is not None:
            comicname = chkit['COMIC']
            issue = chkit['ISSUE']

            ctlVal = {"ComicID":  ComicID,
                      "IssueID":  IssueID}
            myDB.upsert("weekly", newValue, ctlVal)

            newValue['IssueNumber'] =  issue
            newValue['ComicName'] = comicname
            newValue['Status'] = "Snatched"
            if pullinfo is not None:
                newValue['weeknumber'] = pullinfo['weeknumber']
                newValue['year'] = pullinfo['year']
            else:
                try:
                    newValue['weeknumber'] = chkit['weeknumber']
                    newValue['year'] = chkit['year']
                except:
                    pass

            myDB.upsert("oneoffhistory", newValue, ctlVal)

        global_line = 'Successfully snatched %s #%s' % (ComicName, IssueNum)
        if IssueNum is None:
            global_line = 'Successfully snatched %s' % (ComicName)

        logger.info('%s Updated the status (Snatched) complete for %s Issue: %s' % (module, ComicName, IssueNum))
        mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': ComicName, 'seriesyear': seriesyear, 'comicid': ComicID, 'tables': 'tables', 'message': global_line}
    else:
        if down == 'PP':
            logger.info(module + ' Setting status to Post-Processed in history.')
            downstatus = 'Post-Processed'
        else:
            logger.info(module + ' Setting status to Downloaded in history.')
            downstatus = 'Downloaded'
        if mode == 'want_ann':
            if not modcomicname:
                IssueNum = "Annual " + IssueNum
        elif mode == 'story_arc':
            IssueID = IssueArcID

        snatchedupdate = {"IssueID":     IssueID,
                          "Status":      downstatus,
                          "Provider":    provider
                          }
        newsnatchValues = {"ComicName":       ComicName,
                           "ComicID":         ComicID,
                           "Issue_Number":    IssueNum,
                           "DateAdded":       helpers.now(),
                           "Status":          downstatus,
                           "crc":             crc
                           }
        myDB.upsert("snatched", newsnatchValues, snatchedupdate)

        if mode == 'story_arc':
            cValue = {"IssueArcID":   IssueArcID}
            nValue = {"Status":       "Downloaded"}
            myDB.upsert("storyarcs", nValue, cValue)

        elif mode != 'pullwant':
            controlValue = {"IssueID":   IssueID}
            newValue = {"Status":    "Downloaded"}
            if mode == 'want_ann':
                myDB.upsert("annuals", newValue, controlValue)
            else:
                myDB.upsert("issues", newValue, controlValue)

        #this will update the weeklypull list immediately after post-processing to reflect the new status.
        chkit = myDB.selectone("SELECT * FROM weekly WHERE ComicID=? AND IssueID=? AND Status='Snatched'", [ComicID, IssueID]).fetchone()

        if chkit is not None:
            comicname = chkit['COMIC']
            issue = chkit['ISSUE']

            ctlVal = {"ComicID":  ComicID,
                      "IssueID":  IssueID}
            newVal = {"Status":   "Downloaded"}
            myDB.upsert("weekly", newVal, ctlVal)

            newVal['IssueNumber'] =  issue
            newVal['ComicName'] = comicname
            newVal['Status'] = "Downloaded"
            if pullinfo is not None:
                newVal['weeknumber'] = pullinfo['weeknumber']
                newVal['year'] = pullinfo['year']
            myDB.upsert("oneoffhistory", newVal, ctlVal)

        logger.info('%s Updating Status (%s) now completed for %s issue: %s' % (module, downstatus, ComicName, IssueNum))
    return

def forceRescan(ComicID, archive=None, module=None, recheck=False):
    if module is None:
        module = ''
    module += '[FILE-RESCAN]'
    myDB = db.DBConnection()
    # file check to see if issue exists
    rescan = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [ComicID]).fetchone()
    if rescan['AlternateSearch'] is not None:
        altnames = rescan['AlternateSearch'] + '##'
    else:
        altnames = ''

    pause_status = False
    if rescan['Status'] == 'Paused':
        pause_status = True

    if (all([rescan['Type'] != 'Print', rescan['Type'] != 'Digital', rescan['Type'] != 'None', rescan['Type'] is not None]) and rescan['Corrected_Type'] != 'Print') or any([rescan['Corrected_Type'] == 'TPB', rescan['Corrected_Type'] == 'HC', rescan['Corrected_Type'] == 'GN', rescan['Corrected_Type'] == 'One-Shot']):
        if rescan['Type'] == 'One-Shot' and rescan['Corrected_Type'] is None:
            booktype = 'One-Shot'
        else:
            if rescan['Type'] == 'GN' and rescan['Corrected_Type'] is None:
                booktype = 'GN'
            elif rescan['Type'] == 'HC' and rescan['Corrected_Type'] is None:
                booktype = 'HC'
            else:
                booktype = 'TPB'
    else:
        booktype = 'Print'

    annscan = myDB.select('SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted', [ComicID])
    if annscan is None:
        pass
    else:
        for ascan in annscan:
            #logger.info('ReleaseComicName: ' + ascan['ReleaseComicName'])
            if ascan['ReleaseComicName'] not in altnames:
                altnames += ascan['ReleaseComicName'] + '!!' + ascan['ReleaseComicID'] + '##'
        altnames = altnames[:-2]
    logger.info(module + ' Now checking files for ' + rescan['ComicName'] + ' (' + str(rescan['ComicYear']) + ') in ' + rescan['ComicLocation'])
    fca = []
    if archive is None:
        tval = filechecker.FileChecker(dir=rescan['ComicLocation'], watchcomic=rescan['ComicName'], Publisher=rescan['ComicPublisher'], AlternateSearch=altnames)
        tmpval = tval.listFiles()
        #tmpval = filechecker.listFiles(dir=rescan['ComicLocation'], watchcomic=rescan['ComicName'], Publisher=rescan['ComicPublisher'], AlternateSearch=altnames)
        comiccnt = int(tmpval['comiccount'])
        #logger.fdebug(module + 'comiccnt is:' + str(comiccnt))
        fca.append(tmpval)
        try:
            if all([mylar.CONFIG.MULTIPLE_DEST_DIRS is not None, mylar.CONFIG.MULTIPLE_DEST_DIRS != 'None']):
                if os.path.exists(os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(rescan['ComicLocation']))):
                    secondary_folders = os.path.join(mylar.CONFIG.MULTIPLE_DEST_DIRS, os.path.basename(rescan['ComicLocation']))
                else:
                    ff = mylar.filers.FileHandlers(ComicID=ComicID)
                    secondary_folders = ff.secondary_folders(rescan['ComicLocation'])

                logger.fdebug(module + 'multiple_dest_dirs:' + mylar.CONFIG.MULTIPLE_DEST_DIRS)
                logger.fdebug(module + 'dir: ' + rescan['ComicLocation'])
                logger.fdebug(module + 'os.path.basename: ' + os.path.basename(rescan['ComicLocation']))
                logger.info(module + ' Now checking files for ' + rescan['ComicName'] + ' (' + str(rescan['ComicYear']) + ') in :' + secondary_folders)
                mvals = filechecker.FileChecker(dir=secondary_folders, watchcomic=rescan['ComicName'], Publisher=rescan['ComicPublisher'], AlternateSearch=altnames)
                tmpv = mvals.listFiles()
                #tmpv = filechecker.listFiles(dir=secondary_dir, watchcomic=rescan['ComicName'], Publisher=rescan['ComicPublisher'], AlternateSearch=altnames)
                logger.fdebug(module + 'tmpv filecount: ' + str(tmpv['comiccount']))
                comiccnt += int(tmpv['comiccount'])
                fca.append(tmpv)
        except Exception:
            pass
    else:
#        files_arc = filechecker.listFiles(dir=archive, watchcomic=rescan['ComicName'], Publisher=rescan['ComicPublisher'], AlternateSearch=rescan['AlternateSearch'])
        arcval = filechecker.FileChecker(dir=archive, watchcomic=rescan['ComicName'], Publisher=rescan['ComicPublisher'], AlternateSearch=rescan['AlternateSearch'])
        files_arc = arcval.listFiles()
        fca.append(files_arc)
        comiccnt = int(files_arc['comiccount'])

    fcb = []
    fc = {}

    is_cnt = myDB.select("SELECT COUNT(*) FROM issues WHERE ComicID=?", [ComicID])
    iscnt = is_cnt[0][0]

    for ca in fca:
        i = 0
        while True:
            try:
                cla = ca['comiclist'][i]
            except (IndexError, KeyError) as e:
                break

            try:
                if all([booktype == 'TPB', iscnt > 1]) or all([booktype == 'GN', iscnt > 1]) or all([booktype =='HC', iscnt > 1]) or all([booktype == 'One-Shot', iscnt == 1, cla['JusttheDigits'] is None]):
                    if cla['SeriesVolume'] is not None:
                        just_the_digits = re.sub('[^0-9]', '', cla['SeriesVolume']).strip()
                    elif cla['JusttheDigits'] is None:
                        just_the_digits = None
                    else:
                        just_the_digits = re.sub('[^0-9]', '', cla['JusttheDigits']).strip()
                else:
                    just_the_digits = cla['JusttheDigits']
            except Exception as e:
                logger.warn('[Exception: %s] Unable to properly match up/retrieve issue number (or volume) for this [CS: %s]' % (e,cla))
            else:
                fcb.append({"ComicFilename":   cla['ComicFilename'],
                            "ComicLocation":   cla['ComicLocation'],
                            "ComicSize":       cla['ComicSize'],
                            "JusttheDigits":   just_the_digits,
                            "AnnualComicID":   cla['AnnualComicID']})
            i+=1

    fc['comiclist'] = fcb

    havefiles = 0
    if mylar.CONFIG.ANNUALS_ON:
        an_cnt = myDB.select("SELECT COUNT(*) FROM annuals WHERE ComicID=? AND NOT Deleted", [ComicID])
        anncnt = an_cnt[0][0]
    else:
        anncnt = 0
    fccnt = comiccnt #int(fc['comiccount'])
    issnum = 1
    fcnew = []
    fn = 0
    issuedupechk = []
    annualdupechk = []
    issueexceptdupechk = []
    mc_issue = []
    mc_issuenumber = []
    multiple_check = myDB.select('SELECT * FROM issues WHERE ComicID=? GROUP BY Int_IssueNumber HAVING (COUNT(Int_IssueNumber) > 1)', [ComicID])

    if len(multiple_check) == 0:
        logger.fdebug('No issues with identical issue numbering were detected for this series')
        mc_issuenumber = None
    else:
        logger.fdebug('Multiple issues with identical numbering were detected. Attempting to accomodate.')
        for mc in multiple_check:
            mc_issuenumber.append({"Int_IssueNumber": mc['Int_IssueNumber']})

    if not mc_issuenumber is None:
        for mciss in mc_issuenumber:
           mchk = myDB.select('SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?', [ComicID, mciss['Int_IssueNumber']])
           for mck in mchk:
              mc_issue.append({"Int_IssueNumber":   mck['Int_IssueNumber'],
                               "IssueYear":         mck['IssueDate'][:4],
                               "IssueID":           mck['IssueID']})

    mc_annual = []
    mc_annualnumber = []

    if mylar.CONFIG.ANNUALS_ON:
        mult_ann_check = myDB.select('SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted GROUP BY Int_IssueNumber HAVING (COUNT(Int_IssueNumber) > 1)', [ComicID])

        if len(mult_ann_check) == 0:
            logger.fdebug('[ANNUAL-CHK] No annuals with identical issue numbering across annual volumes were detected for this series')
            mc_annualnumber = None
        else:
            logger.fdebug('[ANNUAL-CHK] Multiple annuals with identical numbering were detected across multiple annual volumes. Attempting to accomodate.')
            for mc in mult_ann_check:
                mc_annualnumber.append({"Int_IssueNumber": mc['Int_IssueNumber']})

        if not mc_annualnumber is None:
            for mcann in mc_annualnumber:
                achk = myDB.select('SELECT * FROM annuals WHERE ComicID=? AND Int_IssueNumber=? AND NOT Deleted', [ComicID, mcann['Int_IssueNumber']])
                for ack in achk:
                    mc_annual.append({"Int_IssueNumber":   ack['Int_IssueNumber'],
                                      "IssueYear":         ack['IssueDate'][:4],
                                      "IssueID":           ack['IssueID'],
                                      "ReleaseComicID":    ack['ReleaseComicID']})

    #logger.fdebug('mc_issue:' + str(mc_issue))
    #logger.fdebug('mc_annual:' + str(mc_annual))

    issID_to_ignore = []
    issID_to_ignore.append(str(ComicID))
    annID_to_ignore = []
    annID_to_ignore.append(str(ComicID))
    issID_to_write = []
    ANNComicID = None
    d_annuals = []
    d_issues = []

    reissues = myDB.select('SELECT * FROM issues WHERE ComicID=?', [ComicID])

    a_start = datetime.datetime.now()
    while (fn < fccnt):
        haveissue = "no"
        issuedupe = "no"
        annualdupe = "no"
        try:
            tmpfc = fc['comiclist'][fn]
        except IndexError:
            logger.fdebug(module + ' Unable to properly retrieve a file listing for the given series.')
            logger.fdebug(module + ' Probably because the filenames being scanned are not in a parseable format')
            if fn == 0:
                return
            else:
                break

        if tmpfc['JusttheDigits'] is not None:
            temploc= tmpfc['JusttheDigits'].replace('_', ' ')
            if "Director's Cut" not in temploc:
                temploc = re.sub('[\#\']', '', temploc)
            logger.fdebug('temploc: %s' % temploc)
        else:
            #assume 1 if not given
            if any([booktype == 'TPB', booktype == 'GN', booktype == 'HC', booktype == 'One-Shot']):
                temploc = '1'
            else:
                temploc = None
                logger.warn('The filename [%s] does not have a valid issue number, and the Edition of the series is %s. You might need to Forcibly Mark the Series as TPB/GN and try this again.' % (tmpfc['ComicFilename'], rescan['Type']))
                fn += 1
                continue

        if all(['annual' not in temploc.lower(), 'special' not in temploc.lower()]):
            #remove the extension here
            extensions = ('.cbr', '.cbz', '.cb7')
            if temploc.lower().endswith(extensions):
                logger.fdebug(module + ' Removed extension for issue: ' + temploc)
                temploc = temploc[:-4]
            fcnew_af = re.findall('[^\()]+', temploc)
            p = shlex.quote(fcnew_af[0])
            fcnew = shlex.split(p)

            if temploc is not None:
                fcdigit = helpers.issue_number_parser(temploc).asInt
            elif any([booktype == 'TPB', booktype == 'GN', booktype == 'HC', booktype == 'One-Shot']) and temploc is None:
                fcdigit = helpers.issue_number_parser('1').asInt

            fcn = len(fcnew)
            n = 0
            while True:
                try:
                    reiss = reissues[n]
                    int_iss = None
                except IndexError:
                    break
                int_iss = helpers.issue_number_parser(reiss['Issue_Number']).asInt
                issyear = reiss['IssueDate'][:4]
                old_status = reiss['Status']
                issname = reiss['IssueName']

                if reiss['forced_file'] is not None and bool(reiss['forced_file']) is True:
                    logger.fdebug(module + '[FORCED-MATCH] Matched...issue: ' + rescan['ComicName'] + '#' + reiss['Issue_Number'] + ' --- ' + str(int_iss))
                    havefiles+=1
                    haveissue = "yes"
                    isslocation = tmpfc['ComicFilename'] #helpers.conversion(tmpfc['ComicFilename'])
                    issSize = str(tmpfc['ComicSize'])
                    logger.fdebug(module + ' .......filename: ' + isslocation)
                    logger.fdebug(module + ' .......filesize: ' + str(tmpfc['ComicSize']))
                    # to avoid duplicate issues which screws up the count...let's store the filename issues then
                    # compare earlier...
                    issuedupechk.append({'fcdigit':   int_iss,
                                         'filename':  tmpfc['ComicFilename'],
                                         'filesize':  tmpfc['ComicSize'],
                                         'issueyear': issyear,
                                         'issueid':   reiss['IssueID']})
                    break

                fnd_iss_except = 'None'

                if int(fcdigit) == int_iss:
                    logger.fdebug(module + ' [' + str(reiss['IssueID']) + '] Issue match - fcdigit: ' + str(fcdigit) + ' ... int_iss: ' + str(int_iss))

                    if '-' in temploc and temploc.find(reiss['Issue_Number']) > temploc.find('-'):
                        logger.fdebug(module + ' I have detected a possible Title in the filename')
                        logger.fdebug(module + ' the issue # has occured after the -, so I assume that it is part of the Title')
                        break

                    #baseline these to default to normal scanning
                    multiplechk = False
                    issuedupe = "no"
                    foundchk = False

                    #check here if muliple identical numbering issues exist for the series
                    if len(mc_issue) > 1:
                        for mi in mc_issue:
                            if mi['Int_IssueNumber'] == int_iss:
                                if mi['IssueID'] == reiss['IssueID']:
                                    logger.fdebug(module + ' IssueID matches to multiple issues : ' + str(mi['IssueID']) + '. Checking dupe.')
                                    logger.fdebug(module + ' miISSUEYEAR: ' + str(mi['IssueYear']) + ' -- issyear : ' + str(issyear))
                                    if any(mi['IssueID'] == d['issueid'] for d in issuedupechk):
                                        logger.fdebug(module + ' IssueID already within dupe. Checking next if available.')
                                        multiplechk = True
                                        break
                                    if (mi['IssueYear'] in tmpfc['ComicFilename']) and (issyear == mi['IssueYear']):
                                        logger.fdebug(module + ' Matched to year within filename : ' + str(issyear))
                                        multiplechk = False
                                        break
                                    else:
                                        logger.fdebug(module + ' Did not match to year within filename : ' + str(issyear))
                                        multiplechk = True
                    if multiplechk == True:
                        n+=1
                        continue

                    #this will detect duplicate filenames within the same directory.
                    for di in issuedupechk:
                        if di['fcdigit'] == fcdigit and di['issueid'] == reiss['IssueID']:
                            #base off of config - base duplication keep on filesize or file-type (or both)
                            logger.fdebug('[DUPECHECK] Duplicate issue detected [' + di['filename'] + '] [' + tmpfc['ComicFilename'] + ']')
                            # mylar.CONFIG.DUPECONSTRAINT = 'filesize' / 'filetype-cbr' / 'filetype-cbz'
                            logger.fdebug('[DUPECHECK] Based on duplication preferences I will retain based on : ' + mylar.CONFIG.DUPECONSTRAINT)
                            removedupe = False
                            if 'cbr' in mylar.CONFIG.DUPECONSTRAINT or 'cbz' in mylar.CONFIG.DUPECONSTRAINT:
                                if 'cbr' in mylar.CONFIG.DUPECONSTRAINT:
                                    #this has to be configured in config - either retain cbr or cbz.
                                    if tmpfc['ComicFilename'].endswith('.cbz'):
                                        #keep di['filename']
                                        logger.fdebug('[DUPECHECK-CBR PRIORITY] [#' + reiss['Issue_Number'] + '] Retaining currently scanned in file : ' + di['filename'])
                                        issuedupe = "yes"
                                        break
                                    else:
                                        #keep tmpfc['ComicFilename']
                                        logger.fdebug('[DUPECHECK-CBR PRIORITY] [#' + reiss['Issue_Number'] + '] Retaining newly scanned in file : ' + tmpfc['ComicFilename'])
                                        removedupe = True
                                elif 'cbz' in mylar.CONFIG.DUPECONSTRAINT:
                                    if tmpfc['ComicFilename'].endswith('.cbr'):
                                        #keep di['filename']
                                        logger.fdebug('[DUPECHECK-CBZ PRIORITY] [#' + reiss['Issue_Number'] + '] Retaining currently scanned in filename : ' + di['filename'])
                                        issuedupe = "yes"
                                        break
                                    else:
                                        #keep tmpfc['ComicFilename']
                                        logger.fdebug('[DUPECHECK-CBZ PRIORITY] [#' + reiss['Issue_Number'] + '] Retaining newly scanned in filename : ' + tmpfc['ComicFilename'])
                                        removedupe = True

                            if mylar.CONFIG.DUPECONSTRAINT == 'filesize':
                                if tmpfc['ComicSize'] <= di['filesize']:
                                    logger.fdebug('[DUPECHECK-FILESIZE PRIORITY] [#' + reiss['Issue_Number'] + '] Retaining currently scanned in filename : ' + di['filename'])
                                    issuedupe = "yes"
                                    break
                                else:
                                    logger.fdebug('[DUPECHECK-FILESIZE PRIORITY] [#' + reiss['Issue_Number'] + '] Retaining newly scanned in filename : ' + tmpfc['ComicFilename'])
                                    removedupe = True

                            if removedupe:
                                #need to remove the entry from issuedupechk so can add new one.
                                #tuple(y for y in x if y) for x in a
                                issuedupe_temp = []
                                tmphavefiles = 0
                                for x in issuedupechk:
                                    #logger.fdebug('Comparing x: ' + x['filename'] + ' to di:' + di['filename'])
                                    if x['filename'] != di['filename']:
                                        #logger.fdebug('Matched.')
                                        issuedupe_temp.append(x)
                                        tmphavefiles+=1
                                issuedupechk = issuedupe_temp
                                havefiles = tmphavefiles + len(annualdupechk)
                                foundchk = False
                                break

                    if issuedupe == "no":

                        if foundchk == False:
                            logger.fdebug(module + ' Matched...issue: ' + rescan['ComicName'] + '#' + reiss['Issue_Number'] + ' --- ' + str(int_iss))
                            havefiles+=1
                            haveissue = "yes"
                            isslocation = tmpfc['ComicFilename'] #helpers.conversion(tmpfc['ComicFilename'])
                            issSize = str(tmpfc['ComicSize'])
                            logger.fdebug(module + ' .......filename: ' + isslocation)
                            logger.fdebug(module + ' .......filesize: ' + str(tmpfc['ComicSize']))
                            # to avoid duplicate issues which screws up the count...let's store the filename issues then
                            # compare earlier...
                            issuedupechk.append({'fcdigit':   fcdigit,
                                                 'filename':  tmpfc['ComicFilename'],
                                                 'filesize':  tmpfc['ComicSize'],
                                                 'issueyear': issyear,
                                                 'issueid':   reiss['IssueID']})
                            break

                if issuedupe == "yes":
                    logger.fdebug(module + ' I should break out here because of a dupe.')
                    break

                if haveissue == "yes" or issuedupe == "yes": break
                n+=1
        else:
            if tmpfc['AnnualComicID']:
                ANNComicID = tmpfc['AnnualComicID']
                logger.fdebug(module + ' Forcing ComicID to ' + str(ANNComicID) + ' in case of duplicate numbering across volumes.')
                reannuals = myDB.select('SELECT * FROM annuals WHERE ComicID=? AND ReleaseComicID=? AND NOT Deleted', [ComicID, ANNComicID])
            else:
                reannuals = myDB.select('SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted', [ComicID])
                ANNComicID = ComicID

            if len(reannuals) == 0:
                #it's possible if annual integration is enabled, and an annual series is added directly to the wachlist,
                #not as part of a series, that the above won't work since it's looking in the wrong table.
                reannuals = myDB.select('SELECT * FROM issues WHERE ComicID=?', [ComicID])
                ANNComicID = None #need to set this to None so we write to the issues table and not the annuals


            # annual inclusion here.
            #logger.fdebug("checking " + str(temploc))
            fcnew = shlex.split(str(temploc))
            fcn = len(fcnew)
            n = 0
            reann = None

            year_check = re.findall(r'(\d{4})(?=[\s]|annual\b|$)', temploc, flags=re.I)
            if year_check:
                ann_line = '%s annual' % year_check[0]
                logger.fdebug('ann_line: %s' % ann_line)
                fcdigit = helpers.issue_number_parser('1').asInt
            else:
                fcdigit = helpers.issue_number_parser(re.sub('annual', '', temploc.lower()).strip()).asInt
            # TODO: Another special case harcoded int_issue to look at
            if fcdigit == 999999999999999:
                fcdigit = helpers.issue_number_parser(re.sub('special', '', temploc.lower()).strip()).asInt

            while True:
                try:
                    reann = reannuals[n]
                except IndexError:
                    break
                int_iss = helpers.issue_number_parser(reann['Issue_Number']).asInt
                #logger.fdebug(module + ' int_iss:' + str(int_iss))
                issyear = reann['IssueDate'][:4]
                old_status = reann['Status']

                if int(fcdigit) == int_iss and ANNComicID is not None:
                    logger.fdebug(module + ' [' + str(ANNComicID) + '] Annual match - issue : ' + str(int_iss))

                    #baseline these to default to normal scanning
                    multiplechk = False
                    annualdupe = "no"
                    foundchk = False

                    #check here if muliple identical numbering issues exist for the series
                    if len(mc_annual) > 1:
                        for ma in mc_annual:
                            if ma['Int_IssueNumber'] == int_iss:
                                if ma['IssueID'] == reann['IssueID']:
                                    logger.fdebug(module + ' IssueID matches to multiple issues : ' + str(ma['IssueID']) + '. Checking dupe.')
                                    logger.fdebug(module + ' maISSUEYEAR: ' + str(ma['IssueYear']) + ' -- issyear : ' + str(issyear))
                                    if any(ma['IssueID'] == d['issueid'] for d in annualdupechk):
                                        logger.fdebug(module + ' IssueID already within dupe. Checking next if available.')
                                        multiplechk = True
                                        break
                                    if (ma['IssueYear'] in tmpfc['ComicFilename']) and (issyear == ma['IssueYear']):
                                        # make sure that the IssueYear discovered is not preceded by a volume so it matches correctly
                                        vchk = tmpfc['ComicFilename'].find(ma['IssueYear'])
                                        if tmpfc['ComicFilename'][vchk-1].lower() == 'v':
                                            multiplechk = True
                                        else:
                                            logger.fdebug(module + ' Matched to year within filename : ' + str(issyear))
                                            multiplechk = False
                                            ANNComicID = ack['ReleaseComicID']
                                            break
                                    else:
                                        logger.fdebug(module + ' Did not match to year within filename : ' + str(issyear))
                                        multiplechk = True
                    if multiplechk == True:
                        n+=1
                        continue

                    #this will detect duplicate filenames within the same directory.
                    for di in annualdupechk:
                        if di['fcdigit'] == fcdigit and di['issueid'] == reann['IssueID']:
                            #base off of config - base duplication keep on filesize or file-type (or both)
                            logger.fdebug('[DUPECHECK] Duplicate issue detected [' + di['filename'] + '] [' + tmpfc['ComicFilename'] + ']')
                            # mylar.CONFIG.DUPECONSTRAINT = 'filesize' / 'filetype-cbr' / 'filetype-cbz'
                            logger.fdebug('[DUPECHECK] Based on duplication preferences I will retain based on : ' + mylar.CONFIG.DUPECONSTRAINT)
                            removedupe = False
                            if 'cbr' in mylar.CONFIG.DUPECONSTRAINT or 'cbz' in mylar.CONFIG.DUPECONSTRAINT:
                                if 'cbr' in mylar.CONFIG.DUPECONSTRAINT:
                                    #this has to be configured in config - either retain cbr or cbz.
                                    if tmpfc['ComicFilename'].endswith('.cbz'):
                                        #keep di['filename']
                                        logger.fdebug('[DUPECHECK-CBR PRIORITY] [#' + reann['Issue_Number'] + '] Retaining currently scanned in file : ' + di['filename'])
                                        annualdupe = "yes"
                                        break
                                    else:
                                        #keep tmpfc['ComicFilename']
                                        logger.fdebug('[DUPECHECK-CBR PRIORITY] [#' + reann['Issue_Number'] + '] Retaining newly scanned in file : ' + tmpfc['ComicFilename'])
                                        removedupe = True
                                elif 'cbz' in mylar.CONFIG.DUPECONSTRAINT:
                                    if tmpfc['ComicFilename'].endswith('.cbr'):
                                        #keep di['filename']
                                        logger.fdebug('[DUPECHECK-CBZ PRIORITY] [#' + reann['Issue_Number'] + '] Retaining currently scanned in filename : ' + di['filename'])
                                        annualdupe = "yes"
                                        break
                                    else:
                                        #keep tmpfc['ComicFilename']
                                        logger.fdebug('[DUPECHECK-CBZ PRIORITY] [#' + reann['Issue_Number'] + '] Retaining newly scanned in filename : ' + tmpfc['ComicFilename'])
                                        removedupe = True

                            if mylar.CONFIG.DUPECONSTRAINT == 'filesize':
                                if tmpfc['ComicSize'] <= di['filesize']:
                                    logger.fdebug('[DUPECHECK-FILESIZE PRIORITY] [#' + reann['Issue_Number'] + '] Retaining currently scanned in filename : ' + di['filename'])
                                    annualdupe = "yes"
                                    break
                                else:
                                    logger.fdebug('[DUPECHECK-FILESIZE PRIORITY] [#' + reann['Issue_Number'] + '] Retaining newly scanned in filename : ' + tmpfc['ComicFilename'])
                                    removedupe = True

                            if removedupe:
                                #need to remove the entry from issuedupechk so can add new one.
                                #tuple(y for y in x if y) for x in a
                                annualdupe_temp = []
                                tmphavefiles = 0
                                for x in annualdupechk:
                                    logger.fdebug('Comparing x: ' + x['filename'] + ' to di:' + di['filename'])
                                    if x['filename'] != di['filename']:
                                        annualdupe_temp.append(x)
                                        tmphavefiles+=1
                                annualdupechk = annualdupe_temp
                                havefiles = tmphavefiles + len(issuedupechk)
                                foundchk = False
                                break


                    if annualdupe == "no":
                        if foundchk == False:
                            logger.fdebug(module + ' Matched...annual issue: ' + rescan['ComicName'] + '#' + str(reann['Issue_Number']) + ' --- ' + str(int_iss))
                            havefiles+=1
                            haveissue = "yes"
                            isslocation = tmpfc['ComicFilename'] #helpers.conversion(tmpfc['ComicFilename'])
                            issSize = str(tmpfc['ComicSize'])
                            logger.fdebug(module + ' .......filename: ' + isslocation)
                            logger.fdebug(module + ' .......filesize: ' + str(tmpfc['ComicSize']))
                            # to avoid duplicate issues which screws up the count...let's store the filename issues then
                            # compare earlier...
                            annualdupechk.append({'fcdigit':    int(fcdigit),
                                                  'anncomicid': ANNComicID,
                                                  'filename':   tmpfc['ComicFilename'],
                                                  'filesize':   tmpfc['ComicSize'],
                                                  'issueyear':  issyear,
                                                  'issueid':    reann['IssueID']})
                        break

                if annualdupe == "yes":
                    logger.fdebug(module + ' I should break out here because of a dupe.')
                    break

                if haveissue == "yes" or annualdupe == "yes": break
                n+=1

        if issuedupe == "yes" or annualdupe == "yes": pass
        else:
            #we have the # of comics, now let's update the db.
            #even if we couldn't find the physical issue, check the status.
            #-- if annuals aren't enabled, this will bugger out.
            writeit = True
            try:
                if mylar.CONFIG.ANNUALS_ON:
                    if any(['annual' in temploc.lower(), 'special' in temploc.lower()]):
                        if reann is None:
                            logger.fdebug(module + ' Annual/Special present in location, but series does not have any annuals attached to it - Ignoring')
                            writeit = False
                        else:
                            iss_id = reann['IssueID']
                    else:
                        iss_id = reiss['IssueID']
                else:
                    if any(['annual' in temploc.lower(), 'special' in temploc.lower()]):
                        logger.fdebug(module + ' Annual support not enabled, but annual/special issue present within directory. Ignoring issue.')
                        writeit = False
                    else:
                        iss_id = reiss['IssueID']
            except:
                logger.warn(module + ' An error occured trying to get the relevant issue data. This is probably due to the series not having proper issue data.')
                logger.warn(module + ' you should either Refresh the series, and/or submit an issue on github in regards to the series and the error.')
                return

            if writeit == True and haveissue == 'yes':
                #logger.fdebug(module + ' issueID to write to db:' + str(iss_id))

                #if Archived, increase the 'Have' count.
                if archive:
                    issStatus = "Archived"
                else:
                    issStatus = "Downloaded"


                if ANNComicID:
                    d_annuals.append((issStatus, issSize, isslocation, iss_id))
                    annID_to_ignore.append(str(iss_id))
                    ANNComicID = None
                else:
                    d_issues.append((issStatus, issSize, isslocation, iss_id))
                    issID_to_ignore.append(str(iss_id))
            else:
                ANNComicID = None
        fn+=1
    logger.fdebug('[haves] issue_status_generation took %s' % (datetime.datetime.now() - a_start))

    b_start = datetime.datetime.now()
    try:
        myDB.action("UPDATE issues SET Status=?, ComicSize=?, Location=? WHERE IssueID=?", d_issues, executemany=True)
        if d_annuals:
            myDB.action("UPDATE annuals SET Status=?, ComicSize=?, Location=? WHERE IssueID=?", d_annuals, executemany=True)
    except Exception as e:
        logger.warn('Error updating: %s' % e)
    logger.fdebug('[haves] issue_status_writing took %s' % (datetime.datetime.now() - b_start))

    #if this far, forced_file is true and the file didn't parse properly due to w/e reason, we need to force the filename to link to the given issueid.
    reforce = myDB.select('SELECT * FROM issues WHERE ComicID=? AND forced_file = 1', [ComicID])
    if reforce is not None:
        for rfc in reforce:
            logger.fdebug('%s [FORCED-MATCH] Matched...issue: %s #%s --- %s' % (module, rfc['ComicName'], rfc['Issue_Number'], rfc['Int_IssueNumber']))
            havefiles+=1
            logger.fdebug('%s .......filename: %s' % (module, rfc['Location']))
            logger.fdebug('%s .......filesize: %s' % (module, rfc['ComicSize']))

            controlValueDict = {"IssueID": rfc['IssueID']}

            #if Archived, increase the 'Have' count.
            if archive:
                issStatus = "Archived"
            else:
                issStatus = "Downloaded"

            issID_to_ignore.append(rfc['IssueID'])

            newValueDict = {"Location":           rfc['Location'],
                            "ComicSize":          rfc['ComicSize'],
                            "Status":             issStatus
                            }

            myDB.upsert("issues", newValueDict, controlValueDict)

    #here we need to change the status of the ones we DIDN'T FIND above since the loop only hits on FOUND issues.
    update_iss = []
    update_ann = []
    #break this up in sequnces of 200 so it doesn't break the sql statement.
    cnt = 0
    u_start = datetime.datetime.now()
    for genlist in helpers.chunker(issID_to_ignore, 200):
        tmpsql = "SELECT * FROM issues WHERE ComicID=? AND IssueID not in ({seq})".format(seq=','.join(['?'] *(len(genlist) -1)))
        chkthis = myDB.select(tmpsql, genlist)
        if chkthis is None:
            pass
        else:
            for chk in chkthis:
                if chk['IssueID'] in issID_to_ignore:
                    continue

                old_status = chk['Status']

                if pause_status:
                    issStatus = old_status
                    logger.fdebug('[PAUSE_ISSUE_CHECK_STATUS_CHECK] series is paused, keeping status of %s for issue #%s' % (issStatus, chk['Issue_Number']))
                else:
                    #if old_status == "Skipped":
                    #    if mylar.CONFIG.AUTOWANT_ALL:
                    #        issStatus = "Wanted"
                    #    else:
                    #        issStatus = "Skipped"
                    #elif old_status == "Archived":
                    #    issStatus = "Archived"
                    if old_status == "Downloaded":
                        issStatus = "Archived"
                    else:
                        continue
                #elif old_status == "Wanted":
                #    issStatus = "Wanted"
                #elif old_status == "Ignored":
                #    issStatus = "Ignored"
                #elif old_status == "Snatched":   #this is needed for torrents, or else it'll keep on queuing..
                #    issStatus = "Snatched"
                #else:
                #    issStatus = "Skipped"
                update_iss.append((issStatus, chk['IssueID']))

    for genlist in helpers.chunker(annID_to_ignore, 200):
        tmpsql = "SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted AND IssueID not in ({seq})".format(seq=','.join(['?'] *(len(genlist) -1)))
        chkthis = myDB.select(tmpsql, genlist)
        if chkthis is None:
            pass
        else:
            for chk in chkthis:
                if chk['IssueID'] in annID_to_ignore:
                    continue

                old_status = chk['Status']

                if pause_status:
                    issStatus = old_status
                    logger.fdebug('[PAUSE_ANNUAL_CHECK_STATUS_CHECK] series is paused, keeping status of %s for issue #%s' % (issStatus, chk['Issue_Number']))
                else:
                    #if old_status == "Skipped":
                    #    if mylar.CONFIG.AUTOWANT_ALL:
                    #        issStatus = "Wanted"
                    #    else:
                    #        issStatus = "Skipped"
                    if old_status == "Downloaded":
                        issStatus = "Archived"
                    else:
                        continue
                update_ann.append((issStatus, chk['IssueID']))


    logger.fdebug('[nothaves] issue_status_generation_time_taken: %s' % (datetime.datetime.now() - u_start))

    if any([len(update_iss) > 0, len(update_ann) > 0]):
        r_start = datetime.datetime.now()
        try:
            if len(update_iss) > 0:
                myDB.action("UPDATE issues SET Status=? WHERE IssueID=?", update_iss, executemany=True)
            if len(update_ann) > 0:
                myDB.action("UPDATE annuals SET Status=? WHERE IssueID=?", update_ann, executemany=True)
        except Exception as e:
            logger.warn('Error updating: %s' % e)
        logger.fdebug('[nothaves] issue_status_writing took %s' % (datetime.datetime.now() - r_start))
        logger.info(
            '%s Updated the status of %s issues for %s (%s) that were not found.'
            % (module, len(update_iss), rescan['ComicName'], rescan['ComicYear'])
        )
    logger.info('%s Total files located: %s' % (module, havefiles))

    foundcount = havefiles
    arcfiles = 0
    arcanns = 0
    # if filechecker returns 0 files (it doesn't find any), but some issues have a status of 'Archived'
    # the loop below won't work...let's adjust :)
    arcissues = myDB.select("SELECT count(*) FROM issues WHERE ComicID=? and Status='Archived'", [ComicID])
    if int(arcissues[0][0]) > 0:
        arcfiles = arcissues[0][0]
    arcannuals = myDB.select("SELECT count(*) FROM annuals WHERE ComicID=? and Status='Archived' AND NOT Deleted", [ComicID])
    if int(arcannuals[0][0]) > 0:
        arcanns = arcannuals[0][0]

    if havefiles == 0:
        if arcfiles > 0 or arcanns > 0:
            arcfiles = arcfiles + arcanns
            havefiles = havefiles + arcfiles
            logger.fdebug(
                '%s Adjusting have total to %s because of %s files already'
                ' in an Archive status' % (module, havefiles, arcfiles)
            )
    else:
        #if files exist in the given directory, but are in an archived state - the numbers will get botched up here.
        if (arcfiles + arcanns) > 0:
            logger.fdebug(
                '%s %s issue(s) are in an Archive status already.'
                ' Increasing Have total from %s to include these archives.'
                % (module, arcfiles + arcanns, havefiles)
            )
            havefiles = havefiles + (arcfiles + arcanns)

    ignorecount = 0
    if mylar.CONFIG.IGNORE_HAVETOTAL:   # if this is enabled, will increase Have total as if in Archived Status
        ignoresi = myDB.select("SELECT count(*) FROM issues WHERE ComicID=? AND Status='Ignored'", [ComicID])
        ignoresa = myDB.select("SELECT count(*) FROM annuals WHERE ComicID=? AND Status='Ignored' AND NOT Deleted", [ComicID])
        ignorecount = int(ignoresi[0][0]) + int(ignoresa[0][0])
        if ignorecount > 0:
            havefiles = havefiles + ignorecount
            logger.fdebug(
                '%s Adjusting have total to %s because of %s Ignored files.'
                % (module, havefiles, ignorecount)
            )

    snatchedcount = 0
    if mylar.CONFIG.SNATCHED_HAVETOTAL:   # if this is enabled, will increase Have total as if in Archived Status
        snatches = myDB.select("SELECT count(*) FROM issues WHERE ComicID=? AND Status='Snatched'", [ComicID])
        if int(snatches[0][0]) > 0:
            snatchedcount = snatches[0][0]
            havefiles = havefiles + snatchedcount
            logger.fdebug(
                '%s Adjusting have total to %s because of %s Snatched files.'
                % (module, havefiles, snatchedcount)
            )

    #now that we are finished...
    #adjust for issues that have been marked as Downloaded, but aren't found/don't exist.
    #do it here, because above loop only cycles though found comics using filechecker.
    #downissues = "SELECT *, 0 as type FROM issues WHERE Status='Downloaded' and ComicID=? AND IssueID not in ({seq})".format(seq=','.join(['?'] *(len(issID_to_ignore) -1)))
    #downchk = myDB.select(downissues, issID_to_ignore)
    cnt = 0
    downchk = None
    for genlist in helpers.chunker(issID_to_ignore, 200):
        tmpsql = "SELECT *, 0 as type FROM issues WHERE Status='Downloaded' and ComicID=? AND IssueID not in ({seq})".format(seq=','.join(['?'] *(len(genlist) -1)))
        if cnt == 0:
            downchk = myDB.select(tmpsql, genlist)
        else:
            downchk += myDB.select(tmpsql, genlist)
        cnt += 1
    #logger.info('downchklist: %s' % downchklist)
    #downannuals = "SELECT *, 1 as type FROM annuals WHERE Status='Downloaded' and ComicID=? AND NOT Deleted AND IssueID not in ({seq})".format(seq=','.join(['?'] *(len(issID_to_ignore) -1)))
    #downchk += myDB.select(downannuals, issID_to_ignore)
    cnt = 0
    for genlist in helpers.chunker(annID_to_ignore, 200):
        annuals_sql = "SELECT *, 1 as type FROM annuals WHERE Status='Downloaded' and ComicID=? AND NOT Deleted AND IssueID not in ({seq})".format(seq=','.join(['?'] *(len(genlist) -1)))
        if any([cnt == 0, downchk is None]):
            downchk = myDB.select(annuals_sql, genlist)
        else:
            downchk += myDB.select(annuals_sql, genlist)
        cnt += 1

    if downchk is None:
        pass
    else:
        archivedissues = 0 #set this to 0 so it tallies correctly.
        dvalues = []

        for down in downchk:
            if down['type'] == 1:
                dtable = 'annuals'
            else:
                dtable = 'issues'

            if down['Location'] is None:
                logger.fdebug(
                    '%s Location does not exist which means file was not downloaded'
                    ' successfully, or was moved.' % (module)
                )
                controlValue = {"IssueID":  down['IssueID']}
                newValue = {"Status":    "Archived"}
                myDB.upsert(dtable, newValue, controlValue)
                archivedissues+=1
            else:
                tmp_location = [x['ComicLocation'] for x in fc['comiclist'] if x['ComicFilename'] == down['Location']]
                if not tmp_location:
                    logger.info(
                        '[%s] Changing status of #%s from Downloaded to Archived -'
                        ' cannot locate file %s' %
                        (down['Issue_Number'], down['IssueID'], down['Location'])
                    )
                    try:
                        controlValue = {"IssueID": down['IssueID']}
                        newValue = {"Status": "Archived"}
                        logger.info('[%s] %s : %s' % (dtable, newValue, controlValue))
                        myDB.upsert(dtable, newValue, controlValue)
                    except Exception as e:
                        logger.error('error: %s' % e)
                    archivedissues+=1

        if archivedissues > 0:
            logger.fdebug(
                '%s I have changed the status of %s issues to a status of Archived,'
                ' as I now cannot locate them in the series directory.'
                % (module, len(dvalues))
            )
        havefiles = havefiles + archivedissues  #arcfiles already tallied in havefiles in above segment

    #combined total for dispay total purposes only.
    combined_total = iscnt + anncnt
    if mylar.CONFIG.IGNORE_TOTAL:
        # if this is enabled, will increase Have total as if in Archived Status
        ignoresa = myDB.select("SELECT count(*) FROM issues WHERE ComicID=? AND Status='Ignored'", [ComicID])
        ignoresb = myDB.select("SELECT count(*) FROM annuals WHERE ComicID=? AND Status='Ignored' AND NOT Deleted", [ComicID])
        ignorecnt = ignoresa[0][0] + ignoresb[0][0]

        if ignorecnt > 0:
            combined_total -= ignorecnt
            logger.fdebug('%s Reducing total comics in series from %s to %s because of %s ignored files.' % (module, (iscnt+anncnt), combined_total, ignorecnt))

    #quick check
    if havefiles > combined_total:
        logger.warn(module + ' It looks like you have physical issues in the series directory, but are forcing these issues to an Archived Status. Adjusting have counts.')
        havefiles = havefiles - arcfiles

    thetotals = totals(ComicID, havefiles, combined_total, module, recheck=recheck)
    totalarc = arcfiles + archivedissues

    #enforce permissions
    if mylar.CONFIG.ENFORCE_PERMS:
        logger.fdebug(module + ' Ensuring permissions/ownership enforced for series: ' + rescan['ComicName'])
        filechecker.setperms(rescan['ComicLocation'])
    logger.info(module + ' I have physically found ' + str(foundcount) + ' issues, ignored ' + str(ignorecount) + ' issues, snatched ' + str(snatchedcount) + ' issues, and accounted for ' + str(totalarc) + ' in an Archived state [ Total Issue Count: ' + str(havefiles) + ' / ' + str(combined_total) + ' ]')

def totals(ComicID, havefiles=None, totalfiles=None, module=None, issueid=None, file=None, recheck=False):
    if module is None:
        module = '[FILE-RESCAN]'
    myDB = db.DBConnection()
    filetable = 'issues'
    if any([havefiles is None, havefiles == '+1']):
        if havefiles is None:
            hf = myDB.selectone("SELECT Have, Total FROM comics WHERE ComicID=?", [ComicID]).fetchone()
            havefiles = int(hf['Have'])
            totalfiles = int(hf['Total'])
        else:
            hf = myDB.selectone("SELECT a.Have, a.Total, b.Status as IssStatus FROM comics AS a INNER JOIN issues as b ON a.ComicID=b.ComicID WHERE b.IssueID=?", [issueid]).fetchone()
            if hf is None:
                hf = myDB.selectone("SELECT a.Have, a.Total, b.Status as IssStatus FROM comics AS a INNER JOIN annuals as b ON a.ComicID=b.ComicID WHERE b.IssueID=? AND NOT b.Deleted", [issueid]).fetchone()
                filetable = 'annuals'
            totalfiles = int(hf['Total'])
            logger.fdebug('totalfiles: %s' % totalfiles)
            logger.fdebug('status: %s' % hf['IssStatus'])
            if hf['IssStatus'] != 'Downloaded':
                try:
                    havefiles = int(hf['Have']) +1
                    if havefiles > totalfiles and recheck is False:
                        recheck = True
                        return forceRescan(ComicID, recheck=recheck)
                except TypeError:
                    if totalfiles == 1:
                        havefiles = 1
                    else:
                        logger.warn('Total issues for this series [ComiciD:%s/IssueID:%s] is not 1 when it should be. This is probably a mistake and the series should be refreshed.' % (ComicID, issueid))
                        havefiles = 0
                logger.fdebug('incremented havefiles: %s' % havefiles)
            else:
                havefiles = int(hf['Have'])
                logger.fdebug('untouched havefiles: %s' % havefiles)
    #let's update the total count of comics that was found.
    #store just the total of issues, since annuals gets tracked seperately.
    controlValueStat = {"ComicID":     ComicID}
    newValueStat = {"Have":            havefiles,
                    "Total":           totalfiles,
                    "FilesUpdated":    helpers.now()}

    myDB.upsert("comics", newValueStat, controlValueStat)
    if file is not None:
        controlValueStat = {"IssueID":     issueid,
                            "ComicID":     ComicID}
        newValueStat = {"ComicSize":       os.path.getsize(file)}
        myDB.upsert(filetable, newValueStat, controlValueStat)


def watchlist_updater(calledfrom=None, sched=False):
    # this will retrieve the 'rss' from CV showing the last updated comicids
    # btwn the last update & the current time. Any id's that fall into the existing
    # watchlist, and whose last update time is before the update in the feed will
    # then be queued to be updated. This is to replace the 5 minute auto-updater
    # since that was very ineffecient.

    myDB = db.DBConnection()

    last_date = None
    last_run = None

    chk_time = myDB.selectone(
                   "SELECT prev_run_datetime, last_run_completed, last_date,"
                   " prev_run_timestamp from jobhistory WHERE JobName='DB Updater'"
               ).fetchone()

    last_runtimestamp = None
    if chk_time:
        # get the last updated time from the sqlitedb.
        last_run = chk_time['last_date']
        last_date = chk_time['prev_run_datetime']
        last_runtimestamp = chk_time['prev_run_timestamp']
    elif mylar.DB_BACKFILL is True:
        ld = datetime.datetime.today()
        lastrun = ld - datetime.timedelta(weeks = mylar.CONFIG.BACKFILL_LENGTH)
        last_date = datetime.datetime.strftime(lastrun, '%Y-%m-%d %H:%M:%S')
        logger.info(
            '[BACKFILL-UPDATE][%s weeks] Setting backfill date to : %s. Anything that has '
            ' been updated since this date will get refreshed. Let\'s GoOoo'
            % (mylar.CONFIG.BACKFILL_LENGTH, last_date)
        )

    if last_run is not None:
        # if last_run has a value, then the previous result set was > 1500
        # so it's going thru the space-out process to backfill properly.
        last_dater = datetime.datetime.utcfromtimestamp(last_run)
        last_date = datetime.datetime.strftime(last_dater, '%Y-%m-%d %H:%M:%S')
    elif last_runtimestamp is not None:
        # check here to see if it's so it fires off no more than 15 minutes since last startup.
        # this is to avoid constant checks if mylar is restarted several times.
        rd = datetime.datetime.utcfromtimestamp(last_runtimestamp)
        rd_mins = rd + datetime.timedelta(seconds = 900)
        rd_now = datetime.datetime.utcfromtimestamp(time.time())
        if calendar.timegm(rd_mins.utctimetuple()) > calendar.timegm(rd_now.utctimetuple()):
            logger.info('[BACKFILL-UPDATE] Update ran < 15 minutes ago. Not running.')
            return

    # in order to make sure we update a bunch that probably haven't been updated
    # on intially moving to this new update method, we need to backfill a certain
    # amount. Set it to the last month which 'should' be enough. Note that this will
    # get passed on config loading so it's set at that point

    helpers.job_management(write=True, job='DB Updater', current_run=helpers.utctimestamp(), status='Running')
    mylar.UPDATER_STATUS = 'Running'

    logger.info('[BACKFILL-UPDATE] last date set to : %s' % last_date)

    # the initial load to this new method will be LARGE. So we'll have to
    # stagger the rss over a few hrs just to make sure.

    # first we get the rss feed.
    try:
        update_list = mylar.cv.getComic(
                          comicid=None, rtype='db_updater', dateinfo=last_date
                      )
        # if it returns just a boolean, problem encountered. handle it.
        if update_list is False:
            logger.warn(
                '[BACKFILL-UPDATE] CV is having problems atm. Deferring backfill'
                ' job until next db update scheduled run time.'
            )
            mylar.DB_BACKFILL = False
            helpers.job_management(write=True, job='DB Updater', last_run_completed=helpers.utctimestamp(), status='Waiting')
            mylar.UPDATER_STATUS = 'Waiting'
            return
    except Exception:
        logger.warn(
            '[BACKFILL-UPDATE] CV is having problems atm. Deferring backfill'
            ' job until next db update scheduled run time.'
        )
        mylar.DB_BACKFILL = False
        helpers.job_management(write=True, job='DB Updater', last_run_completed=helpers.utctimestamp(), status='Waiting')
        mylar.UPDATER_STATUS = 'Waiting'
        return


    #logger.fdebug('update_list: %s' % (update_list,))

    if update_list['count'] == 0:
        logger.info('[BACKFILL-UPDATE] Nothing new has been posted to any series in your watchlist')
        helpers.job_management(write=True, job='DB Updater', current_run=helpers.utctimestamp(), status='Waiting')
        mylar.UPDATER_STATUS = 'Waiting'
        return

    set_the_bar = False

    # set the staggered amount here, 1500 results = 100 * 15 api requests.
    if update_list['totalcount'] >= 1500:
        #counter = update_list['count'] - 1500
        set_the_bar = True
        if mylar.DB_BACKFILL is False:
            logger.info(
                '[BACKFILL-UPDATE] %s items returned since last CV update run. Will run every'
                ' %s minutes grabbing the next 1500 results each time'
                % (update_list['totalcount'], mylar.CONFIG.BACKFILL_TIMESPAN)
            )
            mylar.DB_BACKFILL = True


    # update_list now contains dictionary containing all required info.
    # cycle thru it to get any comicids in list, separate then poll those.

    library = {}

    if mylar.CONFIG.ANNUALS_ON is True:
        list = myDB.select("SELECT a.comicname, a.comicid, a.comicyear, b.releasecomicid, a.status, a.LastUpdated, a.Total FROM Comics AS a LEFT JOIN annuals AS b on a.comicid=b.comicid group by a.comicid")
    else:
        list = myDB.select("SELECT comicname, comicid, status, comicyear, LastUpdated, Total FROM Comics group by comicid")

    # if a series failed to update for w/e reason, LastUpdated will be NULL and cause an error otherwise.
    # the prev_failed_updates dict will store all the 'failed' ID's that will be submitted in addition to any
    # other ID's that were updated recently by CV during the check.
    prev_failed_updates = []
    popthecheck = []
    for row in list:
        if row['ComicName'] is None and mylar.CONFIG.ANNUALS_ON:
            logger.fdebug('Popping the check for: %s' % row['ComicID'])
            popthecheck.append({"comicid": row['ComicID'], "comicname": row['ComicName'], "seriesyear": row['ComicYear']})
            continue
        elif not row['LastUpdated'] and all(['ComicID' not in row['ComicName'], row['Status'] != 'Loading', row['ComicName'] is not None]):
            prev_failed_updates.append({"comicid": int(row['ComicID']), "comicname": row['ComicName'], "seriesyear": row['ComicYear']})
        else:
            try:
                tm = datetime.datetime.strptime(row['LastUpdated'], '%Y-%m-%d %H:%M:%S')
            except Exception:
                # if the lastupdated date is NULL, but the other values filled in partially - this will make sure to get the ID so it can be refeshed properly
                prev_failed_updates.append({"comicid": int(row['ComicID']), "comicname": row['ComicName'], "seriesyear": row['ComicYear']})
            else:
                library[int(row['ComicID'])] = {'comicid':        row['ComicID'],
                                                'status':         row['Status'],
                                                'comicname':      row['ComicName'],
                                                'seriesyear':     row['ComicYear'],
                                                'lastupdated':    calendar.timegm(tm.utctimetuple()),
                                                'total':          row['Total']}
        try:
            if row['ReleaseComicID'] is not None and all(['ComicID' not in row['ComicName'], row['Status'] != 'Loading', row['ComicName'] is not None]):
                library[row['ReleaseComicID']] = {'comicid':     row['ComicID'],
                                                  'status':      row['Status']}
        except:
            pass

    if len(popthecheck) > 0:
        logger.fdebug('doing the popcheck')
        # this is for annuals that have been mistakingly added during a previous phase - they have a ComicID on the comics table but nothing linked anywhere to it
        # this will check to see if the releasecomicid is present on the annuals table (as it just got verified as being on the comics table) and if it is,
        # will not flag it for a previous failed update action (ie. refresh). The None values in the Comics table will get cleared out on next restart.
        for pc in popthecheck:
            list = myDB.select("SELECT comicname, comicid, status FROM Annuals WHERE releasecomicid=? AND comicname is not NULL", [pc['comicid']]).fetchone()
            if not list:
                prev_failed_updates.append({"comicid": int(pc['comicid']), "comicname": pc['comicname'], "seriesyear": pc['seriesyear']})
                continue

    # this is based on comicid updates atm.
    to_check = []
    loaddate_stamp = None
    cntr = int(update_list['count'])
    cntr_chk = 1
    for x in update_list['results']:
        if all([set_the_bar is True, loaddate_stamp is None, cntr_chk == cntr]) or loaddate_stamp is not None:
            # set the last record timestamp as the newest date since it's in asc
            loaddate = datetime.datetime.strptime(x['last_updated'], '%Y-%m-%d %H:%M:%S')
            loaddate_stamp = calendar.timegm(loaddate.utctimetuple())

        try:
            if x['comicid']['id'] in library:
                #logger.info('matched to %s' % x['comicid']['id'])
                tm = datetime.datetime.strptime(x['last_updated'], '%Y-%m-%d %H:%M:%S')
                if all(
                   [
                       library[x['comicid']['id']]['lastupdated'] < calendar.timegm(tm.utctimetuple()),
                   ]
                ):
                    x_check = [ yy for yy in to_check if yy['comicid'] == x['comicid']['id'] ]
                    if not x_check:
                        to_check.append({'comicid': x['comicid']['id'],
                                         'comicname': library[x['comicid']['id']]['comicname'],
                                         'seriesyear': library[x['comicid']['id']]['seriesyear']})
            cntr_chk += 1
        except Exception as e:
            logger.fdebug(
                '[BACKFILL-UPDATE] Unable to properly determine item [%s] due to invalid CV entry'
                ' - ignoring (this should be fine)' % (x,)
            )
            pass

    if len(to_check) > 0:
        logger.info(
            '[BACKFILL-UPDATE] [%s] series to update: %s' % (len(to_check), to_check)
        )
    if len(prev_failed_updates) > 0:
        logger.info(
            '[BACKFILL-UPDATE] [%s] series need to be updated due to previous'
            ' failures: %s' % (len(prev_failed_updates), prev_failed_updates)
        )
        try:
            to_check = dict(to_check, **prev_failed_updates)
        except Exception as e:
            to_check = prev_failed_updates
        #to_check.extend(prev_failed_updates)
    else:
        logger.info(
            '[BACKFILL-UPDATE] No previous failures on updates detected (checked against %s items)'
            % (cntr)
        )

    logger.info('[BACKFILL-UPDATE] Setting last update date to: %s' % loaddate_stamp)

    # dbUpdate updates lasupdated so this won't get called again unless updated.
    watch = []
    for x in to_check:
        if not {"comicid": x['comicid'], "comicname": x['comicname']} in mylar.REFRESH_QUEUE.queue:
            watch.append({"comicid": x['comicid'], "comicname": x['comicname'], "seriesyear": x['seriesyear']})

    if len(watch) > 0:
        logger.info('[SHIZZLE-WHIZZLE] Now queueing to refresh %s series' % (len(watch)))
        try:
            mylar.importer.refresh_thread(watch)
        except Exception:
            pass

    #dbUpdate(to_check, calledfrom='updatedb')

    # update the last_date so that if it's large set, we'll keep on ramping it up.
    myDB.upsert("jobhistory", {'last_date': loaddate_stamp }, {'jobName': 'DB Updater'})
    if loaddate_stamp is not None:
        logger.info(
            '[BACKFILL-UPDATE] [%s/%s] Setting last date update point temporarily to %s [%s]'
            % (update_list['count'], update_list['totalcount'],
            datetime.datetime.strftime(datetime.datetime.utcfromtimestamp(loaddate_stamp),
            '%Y-%m-%d %H:%M:%S'), loaddate_stamp)
        )

    helpers.job_management(write=True, job='DB Updater', last_run_completed=helpers.utctimestamp(), status='Waiting')
    mylar.UPDATER_STATUS = 'Waiting'

    # once we trigger it the dates above are updated to backfill dates and we can
    # reset the backfill to None so it doesn't fire off again.
    if mylar.DB_BACKFILL is True and loaddate_stamp is None:
        mylar.DB_BACKFILL = False
    return
