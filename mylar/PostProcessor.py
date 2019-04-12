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
import shutil
import datetime
import re
import shlex
import time
import logging
import mylar
import subprocess
import urllib2
import sys
from xml.dom.minidom import parseString


from mylar import logger, db, helpers, updater, notifiers, filechecker, weeklypull

class PostProcessor(object):
    """
    A class which will process a media file according to the post processing settings in the config.
    """

    EXISTS_LARGER = 1
    EXISTS_SAME = 2
    EXISTS_SMALLER = 3
    DOESNT_EXIST = 4

    NZB_NAME = 1
    FOLDER_NAME = 2
    FILE_NAME = 3

    def __init__(self, nzb_name, nzb_folder, issueid=None, module=None, queue=None, comicid=None, apicall=False, ddl=False):
        """
        Creates a new post processor with the given file path and optionally an NZB name.

        file_path: The path to the file to be processed
        nzb_name: The name of the NZB which resulted in this file being downloaded (optional)
        """
        # name of the NZB that resulted in this folder
        self.nzb_name = nzb_name
        self.nzb_folder = nzb_folder
        if module is not None:
            self.module = module + '[POST-PROCESSING]'
        else:
            self.module = '[POST-PROCESSING]'

        if queue:
            self.queue = queue

        if mylar.APILOCK is True:
            return {'status':  'IN PROGRESS'}

        if apicall is True:
            self.apicall = True
            mylar.APILOCK = True
        else:
            self.apicall = False

        if ddl is True:
            self.ddl = True
        else:
            self.ddl = False

        if mylar.CONFIG.FILE_OPTS == 'copy':
            self.fileop = shutil.copy
        else:
            self.fileop = shutil.move

        self.valreturn = []
        self.extensions = ('.cbr', '.cbz', '.pdf')
        self.failed_files = 0
        self.log = ''
        if issueid is not None:
            self.issueid = issueid
        else:
            self.issueid = None

        if comicid is not None:
            self.comicid = comicid
        else:
            self.comicid = None

        self.issuearcid = None

    def _log(self, message, level=logger): #.message):  #level=logger.MESSAGE):
        """
        A wrapper for the internal logger which also keeps track of messages and saves them to a string for sabnzbd post-processing logging functions.

        message: The string to log (unicode)
        level: The log level to use (optional)
        """
#        logger.log(message, level)
        self.log += message + '\n'

    def _run_pre_scripts(self, nzb_name, nzb_folder, seriesmetadata):
        """
        Executes any pre scripts defined in the config.

        ep_obj: The object to use when calling the pre script
        """
        logger.fdebug("initiating pre script detection.")
        self._log("initiating pre script detection.")
        logger.fdebug("mylar.PRE_SCRIPTS : " + mylar.CONFIG.PRE_SCRIPTS)
        self._log("mylar.PRE_SCRIPTS : " + mylar.CONFIG.PRE_SCRIPTS)
#        for currentScriptName in mylar.CONFIG.PRE_SCRIPTS:
        with open(mylar.CONFIG.PRE_SCRIPTS, 'r') as f:
            first_line = f.readline()

        if mylar.CONFIG.PRE_SCRIPTS.endswith('.sh'):
            shell_cmd = re.sub('#!', '', first_line).strip()
            if shell_cmd == '' or shell_cmd is None:
                shell_cmd = '/bin/bash'
        else:
            #forces mylar to use the executable that it was run with to run the extra script.
            shell_cmd = sys.executable

        currentScriptName = shell_cmd + ' ' + str(mylar.CONFIG.PRE_SCRIPTS).decode("string_escape")
        logger.fdebug("pre script detected...enabling: " + str(currentScriptName))
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(currentScriptName, posix=False) + [str(nzb_name), str(nzb_folder), str(seriesmetadata)]
        logger.fdebug("cmd to be executed: " + str(script_cmd))
        self._log("cmd to be executed: " + str(script_cmd))

            # use subprocess to run the command and capture output
        logger.fdebug(u"Executing command " +str(script_cmd))
        logger.fdebug(u"Absolute path to script: " +script_cmd[0])
        try:
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
            out, err = p.communicate() #@UnusedVariable
            logger.fdebug(u"Script result: " + out)
            self._log(u"Script result: " + out)
        except OSError, e:
           logger.warn(u"Unable to run pre_script: " + str(script_cmd))
           self._log(u"Unable to run pre_script: " + str(script_cmd))

    def _run_extra_scripts(self, nzb_name, nzb_folder, filen, folderp, seriesmetadata):
        """
        Executes any extra scripts defined in the config.

        ep_obj: The object to use when calling the extra script
        """
        logger.fdebug("initiating extra script detection.")
        self._log("initiating extra script detection.")
        logger.fdebug("mylar.EXTRA_SCRIPTS : " + mylar.CONFIG.EXTRA_SCRIPTS)
        self._log("mylar.EXTRA_SCRIPTS : " + mylar.CONFIG.EXTRA_SCRIPTS)
#        for curScriptName in mylar.CONFIG.EXTRA_SCRIPTS:
        with open(mylar.CONFIG.EXTRA_SCRIPTS, 'r') as f:
            first_line = f.readline()

        if mylar.CONFIG.EXTRA_SCRIPTS.endswith('.sh'):
            shell_cmd = re.sub('#!', '', first_line)
            if shell_cmd == '' or shell_cmd is None:
                shell_cmd = '/bin/bash'
        else:
            #forces mylar to use the executable that it was run with to run the extra script.
            shell_cmd = sys.executable

        curScriptName = shell_cmd + ' ' + str(mylar.CONFIG.EXTRA_SCRIPTS).decode("string_escape")
        logger.fdebug("extra script detected...enabling: " + str(curScriptName))
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(curScriptName) + [str(nzb_name), str(nzb_folder), str(filen), str(folderp), str(seriesmetadata)]
        logger.fdebug("cmd to be executed: " + str(script_cmd))
        self._log("cmd to be executed: " + str(script_cmd))

            # use subprocess to run the command and capture output
        logger.fdebug(u"Executing command " +str(script_cmd))
        logger.fdebug(u"Absolute path to script: " +script_cmd[0])
        try:
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=mylar.PROG_DIR)
            out, err = p.communicate() #@UnusedVariable
            logger.fdebug(u"Script result: " + out)
            self._log(u"Script result: " + out)
        except OSError, e:
            logger.warn(u"Unable to run extra_script: " + str(script_cmd))
            self._log(u"Unable to run extra_script: " + str(script_cmd))


    def duplicate_process(self, dupeinfo):
            #path to move 'should' be the entire path to the given file
            path_to_move = dupeinfo['to_dupe']
            file_to_move = os.path.split(path_to_move)[1]

            if dupeinfo['action'] == 'dupe_src' and mylar.CONFIG.FILE_OPTS == 'move':
                logger.info('[DUPLICATE-CLEANUP] New File will be post-processed. Moving duplicate [%s] to Duplicate Dump Folder for manual intervention.' % path_to_move)
            else:
                if mylar.CONFIG.FILE_OPTS == 'move':
                    logger.info('[DUPLICATE-CLEANUP][MOVE-MODE] New File will not be post-processed. Moving duplicate [%s] to Duplicate Dump Folder for manual intervention.' % path_to_move)
                else:
                    logger.info('[DUPLICATE-CLEANUP][COPY-MODE] NEW File will not be post-processed. Retaining file in original location [%s]' % path_to_move)
                    return True

            #this gets tricky depending on if it's the new filename or the existing filename, and whether or not 'copy' or 'move' has been selected.
            if mylar.CONFIG.FILE_OPTS == 'move':
                #check to make sure duplicate_dump directory exists:
                checkdirectory = filechecker.validateAndCreateDirectory(mylar.CONFIG.DUPLICATE_DUMP, True, module='[DUPLICATE-CLEANUP]')

                if mylar.CONFIG.DUPLICATE_DATED_FOLDERS is True:
                    todaydate = datetime.datetime.now().strftime("%Y-%m-%d")
                    dump_folder = os.path.join(mylar.CONFIG.DUPLICATE_DUMP, todaydate)
                    checkdirectory = filechecker.validateAndCreateDirectory(dump_folder, True, module='[DUPLICATE-DATED CLEANUP]')
                else:
                    dump_folder = mylar.CONFIG.DUPLICATE_DUMP

                try:
                    shutil.move(path_to_move, os.path.join(dump_folder, file_to_move))
                except (OSError, IOError):
                    logger.warn('[DUPLICATE-CLEANUP] Failed to move %s ... to ... %s' % (path_to_move, os.path.join(dump_folder, file_to_move)))
                    return False

                logger.warn('[DUPLICATE-CLEANUP] Successfully moved %s ... to ... %s' % (path_to_move, os.path.join(dump_folder, file_to_move)))
                return True

    def tidyup(self, odir=None, del_nzbdir=False, sub_path=None, cacheonly=False, filename=None):
        # del_nzbdir will remove the original directory location. Must be set to False for manual pp or else will delete manual dir that's provided (if empty).
        # move = cleanup/delete original location (self.nzb_folder) AND cache location (odir) if metatagging is enabled.
        # copy = cleanup/delete cache location (odir) only if enabled.
        # cacheonly = will only delete the cache location (useful if there's an error during metatagging, and/or the final location is out of space)
        try:
            #tidyup old path
            if cacheonly is False:
                logger.fdebug('File Option: %s [META-ENABLED: %s]' % (mylar.CONFIG.FILE_OPTS, mylar.CONFIG.ENABLE_META))
                logger.fdebug('odir: %s [filename: %s][self.nzb_folder: %s]' % (odir, filename, self.nzb_folder))
                logger.fdebug('sub_path: %s [cacheonly: %s][del_nzbdir: %s]' % (sub_path, cacheonly, del_nzbdir))
                #if sub_path exists, then we need to use that in place of self.nzb_folder since the file was in a sub-directory within self.nzb_folder
                if all([sub_path is not None, sub_path != self.nzb_folder]): #, self.issueid is not None]):
                    if self.issueid is None:
                        logger.fdebug('Sub-directory detected during cleanup. Will attempt to remove if empty: %s' % sub_path)
                        orig_folder = sub_path
                    else:
                        logger.fdebug('Direct post-processing was performed against specific issueid. Using supplied filepath for deletion.')
                        orig_folder = self.nzb_folder
                else:
                    orig_folder = self.nzb_folder

                #make sure we don't delete the directory passed via manual-pp and ajust for trailling slashes or not
                if orig_folder.endswith('/') or orig_folder.endswith('\\'):
                    tmp_folder = orig_folder[:-1]
                else:
                    tmp_folder = orig_folder

                if os.path.split(tmp_folder)[1] == filename and not os.path.isdir(tmp_folder):
                    logger.fdebug('%s item to be deleted is file, not folder due to direct submission: %s' % (self.module, tmp_folder))
                    tmp_folder = os.path.split(tmp_folder)[0]

                #if all([os.path.isdir(odir), self.nzb_folder != tmp_folder]) or any([odir.startswith('mylar_'),del_nzbdir is True]):
                    # check to see if the directory is empty or not.

                if all([mylar.CONFIG.FILE_OPTS == 'move', self.nzb_name == 'Manual Run', tmp_folder != self.nzb_folder]):
                    if not os.listdir(tmp_folder):
                        logger.fdebug('%s Tidying up. Deleting sub-folder location : %s' % (self.module, tmp_folder))
                        shutil.rmtree(tmp_folder)
                        self._log("Removed temporary directory : %s" % tmp_folder)
                    else:
                        if filename is not None:
                            if os.path.isfile(os.path.join(tmp_folder,filename)):
                                logger.fdebug('%s Attempting to remove file: %s' % (self.module, os.path.join(tmp_folder, filename)))
                                try:
                                    os.remove(os.path.join(tmp_folder, filename))
                                except Exception as e:
                                    logger.warn('%s [%s] Unable to remove file : %s' % (self.module, e, os.path.join(tmp_folder, filename)))
                                else:
                                    if not os.listdir(tmp_folder):
                                       logger.fdebug('%s Tidying up. Deleting original folder location : %s' % (self.module, tmp_folder))
                                       try:
                                           shutil.rmtree(tmp_folder)
                                       except Exception as e:
                                           logger.warn('%s [%s] Unable to delete original folder location: %s' % (self.module, e, tmp_folder))
                                       else:
                                           logger.fdebug('%s Removed original folder location: %s' % (self.module, tmp_folder))
                                           self._log("Removed temporary directory : %s" % tmp_folder)
                                    else:
                                        self._log('Failed to remove temporary directory: %s' % tmp_folder)
                                        logger.error('%s %s not empty. Skipping removal of directory - this will either be caught in further post-processing or it will have to be manually deleted.' % (self.module, tmp_folder))
                        else:
                            self._log('Failed to remove temporary directory: ' + tmp_folder)
                            logger.error('%s %s not empty. Skipping removal of directory - this will either be caught in further post-processing or it will have to be manually deleted.' % (self.module, tmp_folder))

                elif all([mylar.CONFIG.FILE_OPTS == 'move', self.nzb_name == 'Manual Run', filename is not None]):
                    if os.path.isfile(os.path.join(tmp_folder,filename)):
                        logger.fdebug('%s Attempting to remove original file: %s' % (self.module, os.path.join(tmp_folder, filename)))
                        try:
                            os.remove(os.path.join(tmp_folder, filename))
                        except Exception as e:
                            logger.warn('%s [%s] Unable to remove file : %s' % (self.module, e, os.path.join(tmp_folder, filename)))

                elif mylar.CONFIG.FILE_OPTS == 'move' and all([del_nzbdir is True, self.nzb_name != 'Manual Run']): #tmp_folder != self.nzb_folder]):
                    if not os.listdir(tmp_folder):
                        logger.fdebug('%s Tidying up. Deleting original folder location : %s' % (self.module, tmp_folder))
                        shutil.rmtree(tmp_folder)
                        self._log("Removed temporary directory : %s" % tmp_folder)
                    else:
                        if filename is not None:
                            if os.path.isfile(os.path.join(tmp_folder,filename)):
                                logger.fdebug('%s Attempting to remove file: %s' % (self.module, os.path.join(tmp_folder, filename)))
                                try:
                                    os.remove(os.path.join(tmp_folder, filename))
                                except Exception as e:
                                    logger.warn('%s [%s] Unable to remove file : %s' % (self.module, e, os.path.join(tmp_folder, filename)))
                                else:
                                    if not os.listdir(tmp_folder):
                                       logger.fdebug('%s Tidying up. Deleting original folder location : %s' % (self.module, tmp_folder))
                                       try:
                                           shutil.rmtree(tmp_folder)
                                       except Exception as e:
                                           logger.warn('%s [%s] Unable to delete original folder location: %s' % (self.module, e, tmp_folder))
                                       else:
                                           logger.fdebug('%s Removed original folder location: %s' % (self.module, tmp_folder))
                                           self._log("Removed temporary directory : " + tmp_folder)
                                    else:
                                        self._log('Failed to remove temporary directory: ' + tmp_folder)
                                        logger.error('%s %s not empty. Skipping removal of directory - this will either be caught in further post-processing or it will have to be manually deleted.' % (self.module, tmp_folder))
                        else:
                            self._log('Failed to remove temporary directory: ' + tmp_folder)
                            logger.error('%s %s not empty. Skipping removal of directory - this will either be caught in further post-processing or it will have to be manually deleted.' % (self.module, tmp_folder))

            if mylar.CONFIG.ENABLE_META and all([os.path.isdir(odir), 'mylar_' in odir]):
                #Regardless of the copy/move operation, we need to delete the files from within the cache directory, then remove the cache directory itself for the given issue.
                #sometimes during a meta, it retains the cbr as well after conversion depending on settings. Make sure to delete too thus the 'walk'.
                for filename in os.listdir(odir):
                    filepath = os.path.join(odir, filename)
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass
                if not os.listdir(odir):
                    logger.fdebug('%s Tidying up. Deleting temporary cache directory : %s' % (self.module, odir))
                    shutil.rmtree(odir)
                    self._log("Removed temporary directory : %s" % odir)
                else:
                    self._log('Failed to remove temporary directory: %s' % odir)
                    logger.error('%s %s not empty. Skipping removal of temporary cache directory - this will either be caught in further post-processing or have to be manually deleted.' % (self.module, odir))

        except (OSError, IOError):
            logger.fdebug('%s Failed to remove directory - Processing will continue, but manual removal is necessary' % self.module)
            self._log('Failed to remove temporary directory')


    def Process(self):
            module = self.module
            self._log('nzb name: %s' % self.nzb_name)
            self._log('nzb folder: %s' % self.nzb_folder)
            logger.fdebug('%s nzb name: %s' % (module, self.nzb_name))
            logger.fdebug('%s nzb folder: %s' % (module, self.nzb_folder))
            if self.ddl is False:
                if mylar.USE_SABNZBD==1:
                    if self.nzb_name != 'Manual Run':
                        logger.fdebug('%s Using SABnzbd' % module)
                        logger.fdebug('%s NZB name as passed from NZBGet: %s' % (module, self.nzb_name))

                    if self.nzb_name == 'Manual Run':
                        logger.fdebug('%s Manual Run Post-Processing enabled.' % module)
                    else:
                        # if the SAB Directory option is enabled, let's use that folder name and append the jobname.
                        if all([mylar.CONFIG.SAB_TO_MYLAR, mylar.CONFIG.SAB_DIRECTORY is not None, mylar.CONFIG.SAB_DIRECTORY != 'None']):
                            self.nzb_folder = os.path.join(mylar.CONFIG.SAB_DIRECTORY, self.nzb_name).encode(mylar.SYS_ENCODING)
                            logger.fdebug('%s SABnzbd Download folder option enabled. Directory set to : %s' % (module, self.nzb_folder))

                if mylar.USE_NZBGET==1:
                    if self.nzb_name != 'Manual Run':
                        logger.fdebug('%s Using NZBGET' % module)
                        logger.fdebug('%s NZB name as passed from NZBGet: %s' % (module, self.nzb_name))
                    # if the NZBGet Directory option is enabled, let's use that folder name and append the jobname.
                    if self.nzb_name == 'Manual Run':
                        logger.fdebug('%s Manual Run Post-Processing enabled.' % module)
                    elif all([mylar.CONFIG.NZBGET_DIRECTORY is not None, mylar.CONFIG.NZBGET_DIRECTORY is not 'None']):
                        logger.fdebug('%s NZB name as passed from NZBGet: %s' % (module, self.nzb_name))
                        self.nzb_folder = os.path.join(mylar.CONFIG.NZBGET_DIRECTORY, self.nzb_name).encode(mylar.SYS_ENCODING)
                        logger.fdebug('%s NZBGET Download folder option enabled. Directory set to : %s' % (module, self.nzb_folder))
            else:
                logger.fdebug('%s Now performing post-processing of %s sent from DDL' % (module, self.nzb_name))

            myDB = db.DBConnection()

            self.oneoffinlist = False

            if any([self.nzb_name == 'Manual Run', self.issueid is not None, self.comicid is not None, self.apicall is True]):
                if all([self.issueid is None, self.comicid is not None, self.apicall is True]) or self.nzb_name == 'Manual Run' or all([self.apicall is True, self.comicid is None, self.issueid is None, self.nzb_name.startswith('0-Day')]):
                    if self.comicid is not None:
                        logger.fdebug('%s Now post-processing pack directly against ComicID: %s' % (module, self.comicid))
                    elif all([self.apicall is True, self.issueid is None, self.comicid is None, self.nzb_name.startswith('0-Day')]):
                        logger.fdebug('%s Now post-processing 0-day pack: %s' % (module, self.nzb_name))
                    else:
                        logger.fdebug('%s Manual Run initiated' % module)
                    #Manual postprocessing on a folder.
                    #first we get a parsed results list  of the files being processed, and then poll against the sql to get a short list of hits.
                    flc = filechecker.FileChecker(self.nzb_folder, justparse=True, pp_mode=True)
                    filelist = flc.listFiles()
                    if filelist['comiccount'] == 0: # is None:
                        logger.warn('There were no files located - check the debugging logs if you think this is in error.')
                        return
                    logger.info('I have located %s files that I should be able to post-process. Continuing...' % filelist['comiccount'])
                else:
                    if all([self.comicid is None, '_' not in self.issueid]):
                         cid = myDB.selectone('SELECT ComicID FROM issues where IssueID=?', [str(self.issueid)]).fetchone()
                         self.comicid = cid[0]
                    else:
                         if '_' in self.issueid:
                             logger.fdebug('Story Arc post-processing request detected.')
                             self.issuearcid = self.issueid
                             self.issueid = None
                             logger.fdebug('%s Now post-processing directly against StoryArcs -  ComicID: %s / IssueArcID: %s' % (module, self.comicid, self.issuearcid))
                    if self.issueid is not None:
                        logger.fdebug('%s Now post-processing directly against ComicID: %s / IssueID: %s' % (module, self.comicid, self.issueid))
                    if self.issuearcid is None:
                        if self.nzb_name.lower().endswith(self.extensions):
                            flc = filechecker.FileChecker(self.nzb_folder, file=self.nzb_name, pp_mode=True)
                            fl = flc.listFiles()
                            filelist = {}
                            filelist['comiclist'] = [fl]
                            filelist['comiccount'] = len(filelist['comiclist'])
                        else:
                            flc = filechecker.FileChecker(self.nzb_folder, justparse=True, pp_mode=True)
                            filelist = flc.listFiles()
                    else:
                        filelist = {}
                        filelist['comiclist'] =  []
                        filelist['comiccount'] = 0
                #preload the entire ALT list in here.
                alt_list = []
                alt_db = myDB.select("SELECT * FROM Comics WHERE AlternateSearch != 'None'")
                if alt_db is not None:
                    for aldb in alt_db:
                        as_d = filechecker.FileChecker(AlternateSearch=helpers.conversion(aldb['AlternateSearch']))
                        as_dinfo = as_d.altcheck()
                        alt_list.append({'AS_Alt':   as_dinfo['AS_Alt'],
                                         'AS_Tuple': as_dinfo['AS_Tuple'],
                                         'AS_DyComicName': aldb['DynamicComicName']})

                manual_arclist = []
                oneoff_issuelist = []
                manual_list = []
                for fl in filelist['comiclist']:
                    self.matched = False
                    as_d = filechecker.FileChecker()
                    as_dinfo = as_d.dynamic_replace(helpers.conversion(fl['series_name']))
                    orig_seriesname = as_dinfo['mod_seriesname']
                    mod_seriesname = as_dinfo['mod_seriesname']
                    loopchk = []
                    if fl['alt_series'] is not None:
                        logger.fdebug('%s Alternate series naming detected: %s' % (module, fl['alt_series']))
                        as_sinfo = as_d.dynamic_replace(helpers.conversion(fl['alt_series']))
                        mod_altseriesname = as_sinfo['mod_seriesname']
                        if all([mylar.CONFIG.ANNUALS_ON, 'annual' in mod_altseriesname.lower()]) or all([mylar.CONFIG.ANNUALS_ON, 'special' in mod_altseriesname.lower()]):
                            mod_altseriesname = re.sub('annual', '', mod_altseriesname, flags=re.I).strip()
                            mod_altseriesname = re.sub('special', '', mod_altseriesname, flags=re.I).strip()
                        if not any(re.sub('[\|\s]', '', mod_altseriesname).lower() == x for x in loopchk):
                            loopchk.append(re.sub('[\|\s]', '', mod_altseriesname.lower()))

                    for x in alt_list:
                        cname = x['AS_DyComicName']
                        for ab in x['AS_Alt']:
                            tmp_ab = re.sub(' ', '', ab)
                            tmp_mod_seriesname = re.sub(' ', '', mod_seriesname)
                            if re.sub('\|', '', tmp_mod_seriesname.lower()).strip() == re.sub('\|', '', tmp_ab.lower()).strip():
                                if not any(re.sub('[\|\s]', '', cname.lower()) == x for x in loopchk):
                                    loopchk.append(re.sub('[\|\s]', '', cname.lower()))

                    if all([mylar.CONFIG.ANNUALS_ON, 'annual' in mod_seriesname.lower()]) or all([mylar.CONFIG.ANNUALS_ON, 'special' in mod_seriesname.lower()]):
                        mod_seriesname = re.sub('annual', '', mod_seriesname, flags=re.I).strip()
                        mod_seriesname = re.sub('special', '', mod_seriesname, flags=re.I).strip()

                    #make sure we add back in the original parsed filename here.
                    if not any(re.sub('[\|\s]', '', mod_seriesname).lower() == x for x in loopchk):
                        loopchk.append(re.sub('[\|\s]', '', mod_seriesname.lower()))

                    if any([self.issueid is not None, self.comicid is not None]):
                        comicseries = myDB.select('SELECT * FROM comics WHERE ComicID=?', [self.comicid])
                    else:
                        if fl['issueid'] is not None:
                            logger.info('issueid detected in filename: %s' % fl['issueid'])
                            csi = myDB.selectone('SELECT i.ComicID, i.IssueID, i.Issue_Number, c.ComicName FROM comics as c JOIN issues as i ON c.ComicID = i.ComicID WHERE i.IssueID=?', [fl['issueid']]).fetchone()
                            if csi is None:
                                csi = myDB.selectone('SELECT i.ComicID as comicid, i.IssueID, i.Issue_Number, a.ReleaseComicName, c.ComicName FROM comics as c JOIN annuals as a ON c.ComicID = a.ComicID WHERE a.IssueID=?', [fl['issueid']]).fetchone()
                                if csi is not None:
                                    annchk = 'yes'
                                else:
                                    continue
                            else:
                                annchk = 'no'
                            if fl['sub']:
                                logger.fdebug('%s[SUB: %s][CLOCATION: %s]' % (module, fl['sub'], fl['comiclocation']))
                                clocation = os.path.join(fl['comiclocation'], fl['sub'], helpers.conversion(fl['comicfilename']))
                            else:
                                logger.fdebug('%s[CLOCATION] %s' % (module, fl['comiclocation']))
                                clocation = os.path.join(fl['comiclocation'],helpers.conversion(fl['comicfilename']))
                            annualtype = None
                            if annchk == 'yes':
                                if 'Annual' in csi['ReleaseComicName']:
                                    annualtype = 'Annual'
                                elif 'Special' in csi['ReleaseComicName']:
                                    annualtype = 'Special'
                            else:
                                if 'Annual' in csi['ComicName']:
                                    annualtype = 'Annual'
                                elif 'Special' in csi['ComicName']:
                                    annualtype = 'Special'
                            manual_list.append({"ComicLocation":   clocation,
                                                "ComicID":         csi['ComicID'],
                                                "IssueID":         csi['IssueID'],
                                                "IssueNumber":     csi['Issue_Number'],
                                                "AnnualType":      annualtype,
                                                "ComicName":       csi['ComicName'],
                                                "Series":          fl['series_name'],
                                                "AltSeries":       fl['alt_series'],
                                                "One-Off":         False,
                                                "ForcedMatch":     True})
                            logger.info('manual_list: %s' % manual_list)
                            break

                        else:
                            tmpsql = "SELECT * FROM comics WHERE DynamicComicName IN ({seq}) COLLATE NOCASE".format(seq=','.join('?' * len(loopchk)))
                            comicseries = myDB.select(tmpsql, tuple(loopchk))

                    if not comicseries or orig_seriesname != mod_seriesname:
                        if all(['special' in orig_seriesname.lower(), mylar.CONFIG.ANNUALS_ON, orig_seriesname != mod_seriesname]):
                            if not any(re.sub('[\|\s]', '', orig_seriesname).lower() == x for x in loopchk):
                                loopchk.append(re.sub('[\|\s]', '', orig_seriesname.lower()))
                                tmpsql = "SELECT * FROM comics WHERE DynamicComicName IN ({seq}) COLLATE NOCASE".format(seq=','.join('?' * len(loopchk)))
                                comicseries = myDB.select(tmpsql, tuple(loopchk))
                                #if not comicseries:
                                #    logger.error('[%s][%s] No Series named %s - checking against Story Arcs (just in case). If I do not find anything, maybe you should be running Import?' % (module, fl['comicfilename'], fl['series_name']))
                                #    continue
                    watchvals = []
                    for wv in comicseries:
                        logger.info('Now checking: %s [%s]' % (wv['ComicName'], wv['ComicID']))
                        #do some extra checks in here to ignore these types:
                        #check for Paused status /
                        #check for Ended status and 100% completion of issues.
                        if wv['Status'] == 'Paused' or (wv['Have'] == wv['Total'] and not any(['Present' in wv['ComicPublished'], helpers.now()[:4] in wv['ComicPublished']])):
                            logger.warn('%s [%s] is either Paused or in an Ended status with 100%s completion. Ignoring for match.' % (wv['ComicName'], wv['ComicYear'], '%'))
                            continue
                        wv_comicname = wv['ComicName']
                        wv_comicpublisher = wv['ComicPublisher']
                        wv_alternatesearch = wv['AlternateSearch']
                        wv_comicid = wv['ComicID']
                        if (all([wv['Type'] != 'Print', wv['Type'] != 'Digital']) and wv['Corrected_Type'] != 'Print') or wv['Corrected_Type'] == 'TPB':
                            wv_type = 'TPB'
                        else:
                            wv_type = None
                        wv_seriesyear = wv['ComicYear']
                        wv_comicversion = wv['ComicVersion']
                        wv_publisher = wv['ComicPublisher']
                        wv_total = wv['Total']
                        if mylar.CONFIG.FOLDER_SCAN_LOG_VERBOSE:
                            logger.fdebug('Queuing to Check: %s [%s] -- %s' % (wv['ComicName'], wv['ComicYear'], wv['ComicID']))

                        #force it to use the Publication Date of the latest issue instead of the Latest Date (which could be anything)
                        latestdate = myDB.select('SELECT IssueDate from issues WHERE ComicID=? order by ReleaseDate DESC', [wv['ComicID']])
                        if latestdate:
                            tmplatestdate = latestdate[0][0]
                            if tmplatestdate[:4] != wv['LatestDate'][:4]:
                                if tmplatestdate[:4] > wv['LatestDate'][:4]:
                                    latestdate = tmplatestdate
                                else:
                                    latestdate = wv['LatestDate']
                            else:
                                latestdate = tmplatestdate
                        else:
                            latestdate = wv['LatestDate']

                        if latestdate == '0000-00-00' or latestdate == 'None' or latestdate is None:
                            logger.fdebug('Forcing a refresh of series: %s as it appears to have incomplete issue dates.' % wv_comicname)
                            updater.dbUpdate([wv_comicid])
                            logger.fdebug('Refresh complete for %s. Rechecking issue dates for completion.' % wv_comicname)
                            latestdate = myDB.select('SELECT IssueDate from issues WHERE ComicID=? order by ReleaseDate DESC', [wv['ComicID']])
                            if latestdate:
                                tmplatestdate = latestdate[0][0]
                                if tmplatestdate[:4] != wv['LatestDate'][:4]:
                                    if tmplatestdate[:4] > wv['LatestDate'][:4]:
                                        latestdate = tmplatestdate
                                    else:
                                        latestdate = wv['LatestDate']
                                else:
                                    latestdate = tmplatestdate
                            else:
                                latestdate = wv['LatestDate']

                            logger.fdebug('Latest Date (after forced refresh) set to :' + str(latestdate))

                            if latestdate == '0000-00-00' or latestdate == 'None' or latestdate is None:
                                logger.fdebug('Unable to properly attain the Latest Date for series: %s. Cannot check against this series for post-processing.' % wv_comicname)
                                continue 

                        watchvals.append({"ComicName":       wv_comicname,
                                          "ComicPublisher":  wv_comicpublisher,
                                          "AlternateSearch": wv_alternatesearch,
                                          "ComicID":         wv_comicid,
                                          "LastUpdated":     wv['LastUpdated'],
                                          "WatchValues": {"SeriesYear":   wv_seriesyear,
                                                          "LatestDate":   latestdate,
                                                          "ComicVersion": wv_comicversion,
                                                          "Type":         wv_type,
                                                          "Publisher":    wv_publisher,
                                                          "Total":        wv_total,
                                                          "ComicID":      wv_comicid,
                                                          "IsArc":        False}
                                         })

                    ccnt=0
                    nm=0
                    for cs in watchvals:
                        wm = filechecker.FileChecker(watchcomic=cs['ComicName'], Publisher=cs['ComicPublisher'], AlternateSearch=cs['AlternateSearch'], manual=cs['WatchValues'])
                        watchmatch = wm.matchIT(fl)
                        if watchmatch['process_status'] == 'fail':
                            nm+=1
                            continue
                        else:
                            try:
                                if cs['WatchValues']['Type'] == 'TPB' and cs['WatchValues']['Total'] > 1:
                                    if watchmatch['series_volume'] is not None:
                                        just_the_digits = re.sub('[^0-9]', '', watchmatch['series_volume']).strip()
                                    else:
                                        just_the_digits = re.sub('[^0-9]', '', watchmatch['justthedigits']).strip()
                                else:
                                    just_the_digits = watchmatch['justthedigits']
                            except Exception as e:
                                logger.warn('[Exception: %s] Unable to properly match up/retrieve issue number (or volume) for this [CS: %s] [WATCHMATCH: %s]' % (e, cs, watchmatch))
                                nm+=1
                                continue

                            if just_the_digits is not None:
                                temploc= just_the_digits.replace('_', ' ')
                                temploc = re.sub('[\#\']', '', temploc)
                                #logger.fdebug('temploc: %s' % temploc)
                            else:
                                temploc = None
                            datematch = "False"

                            if temploc is not None and (any(['annual' in temploc.lower(), 'special' in temploc.lower()]) and mylar.CONFIG.ANNUALS_ON is True):
                                biannchk = re.sub('-', '', temploc.lower()).strip()
                                if 'biannual' in biannchk:
                                    logger.fdebug('%s Bi-Annual detected.' % module)
                                    fcdigit = helpers.issuedigits(re.sub('biannual', '', str(biannchk)).strip())
                                else:
                                    if 'annual' in temploc.lower():
                                        fcdigit = helpers.issuedigits(re.sub('annual', '', str(temploc.lower())).strip())
                                    else:
                                        fcdigit = helpers.issuedigits(re.sub('special', '', str(temploc.lower())).strip())
                                    logger.fdebug('%s Annual/Special detected [%s]. ComicID assigned as %s' % (module, fcdigit, cs['ComicID']))
                                annchk = "yes"
                                issuechk = myDB.select("SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=?", [cs['ComicID'], fcdigit])
                            else:
                                annchk = "no"
                                if temploc is not None:
                                    fcdigit = helpers.issuedigits(temploc)
                                    issuechk = myDB.select("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [cs['ComicID'], fcdigit])
                                else:
                                    fcdigit = None
                                    issuechk = myDB.select("SELECT * from issues WHERE ComicID=?", [cs['ComicID']])

                            if not issuechk:
                                try:
                                    logger.fdebug('%s No corresponding issue #%s found for %s' % (module, temploc, cs['ComicID']))
                                except:
                                    continue
                                #check the last refresh date of the series, and if > than an hr try again:
                                c_date = cs['LastUpdated']
                                if c_date is None:
                                    logger.error('%s %s failed during a previous add /refresh as it has no Last Update timestamp. Forcing refresh now.' % (module, cs['ComicName']))
                                else:
                                    c_obj_date = datetime.datetime.strptime(c_date, "%Y-%m-%d %H:%M:%S")
                                    n_date = datetime.datetime.now()
                                    absdiff = abs(n_date - c_obj_date)
                                    hours = (absdiff.days * 24 * 60 * 60 + absdiff.seconds) / 3600.0
                                    if hours < 1:
                                        logger.fdebug('%s %s [%s] Was refreshed less than 1 hours ago. Skipping Refresh at this time so we don\'t hammer things unnecessarily.' % (module, cs['ComicName'], cs['ComicID']))
                                        continue
                                updater.dbUpdate([cs['ComicID']])
                                logger.fdebug('%s Succssfully refreshed series - now re-querying against new data for issue #%s.' % (module, temploc))
                                if annchk == 'yes':
                                    issuechk = myDB.select("SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=?", [cs['ComicID'], fcdigit])
                                else:
                                    issuechk = myDB.select("SELECT * from issues WHERE ComicID=? AND Int_IssueNumber=?", [cs['ComicID'], fcdigit])
                                if not issuechk:
                                    logger.fdebug('%s No corresponding issue #%s found for %s even after refreshing. It might not have the information available as of yet...' % (module, temploc, cs['ComicID']))
                                    continue

                            for isc in issuechk:
                                datematch = "True"
                                datechkit = False
                                if isc['ReleaseDate'] is not None and isc['ReleaseDate'] != '0000-00-00':
                                    try:
                                        if isc['DigitalDate'] != '0000-00-00' and int(re.sub('-', '', isc['DigitalDate']).strip()) <= int(re.sub('-', '', isc['ReleaseDate']).strip()):
                                            monthval = isc['DigitalDate']
                                            watch_issueyear = isc['DigitalDate'][:4]
                                        else:
                                            monthval = isc['ReleaseDate']
                                            watch_issueyear = isc['ReleaseDate'][:4]
                                    except:
                                        monthval = isc['ReleaseDate']
                                        watch_issueyear = isc['ReleaseDate'][:4]

                                else:
                                    try:
                                        if isc['DigitalDate'] != '0000-00-00' and int(re.sub('-', '', isc['DigitalDate']).strip()) <= int(re.sub('-', '', isc['ReleaseDate']).strip()):
                                            monthval = isc['DigitalDate']
                                            watch_issueyear = isc['DigitalDate'][:4]
                                        else:
                                            monthval = isc['IssueDate']
                                            watch_issueyear = isc['IssueDate'][:4]
                                    except:
                                        monthval = isc['IssueDate']
                                        watch_issueyear = isc['IssueDate'][:4]

                                if len(watchmatch) >= 1 and watchmatch['issue_year'] is not None:
                                    #if the # of matches is more than 1, we need to make sure we get the right series
                                    #compare the ReleaseDate for the issue, to the found issue date in the filename.
                                    #if ReleaseDate doesn't exist, use IssueDate
                                    #if no issue date was found, then ignore.
                                    logger.fdebug('%s[ISSUE-VERIFY] Now checking against %s - %s' % (module, cs['ComicName'], cs['ComicID']))
                                    issyr = None
                                    #logger.fdebug(module + ' issuedate:' + str(isc['IssueDate']))
                                    #logger.fdebug(module + ' isc: ' + str(isc['IssueDate'][5:7]))

                                    #logger.info(module + ' ReleaseDate: ' + str(isc['ReleaseDate']))
                                    #logger.info(module + ' IssueDate: ' + str(isc['IssueDate']))
                                    if isc['DigitalDate'] is not None and isc['DigitalDate'] != '0000-00-00':
                                        if int(isc['DigitalDate'][:4]) < int(watchmatch['issue_year']):
                                            logger.fdebug('%s[ISSUE-VERIFY] %s is before the issue year of %s that was discovered in the filename' % (module, isc['DigitalDate'], watchmatch['issue_year']))
                                            datematch = "False"

                                    elif isc['ReleaseDate'] is not None and isc['ReleaseDate'] != '0000-00-00':
                                        if int(isc['ReleaseDate'][:4]) < int(watchmatch['issue_year']):
                                            logger.fdebug('%s[ISSUE-VERIFY] %s is before the issue year of %s that was discovered in the filename' % (module, isc['ReleaseDate'], watchmatch['issue_year']))
                                            datematch = "False"
                                    else:
                                        if int(isc['IssueDate'][:4]) < int(watchmatch['issue_year']):
                                            logger.fdebug('%s[ISSUE-VERIFY] %s is before the issue year %s that was discovered in the filename' % (module, isc['IssueDate'], watchmatch['issue_year']))
                                            datematch = "False"

                                    if int(watch_issueyear) != int(watchmatch['issue_year']):
                                        if int(monthval[5:7]) == 11 or int(monthval[5:7]) == 12:
                                            issyr = int(monthval[:4]) + 1
                                            logger.fdebug('%s[ISSUE-VERIFY] IssueYear (issyr) is %s' % (module, issyr))
                                            datechkit = True
                                        elif int(monthval[5:7]) == 1 or int(monthval[5:7]) == 2 or int(monthval[5:7]) == 3:
                                            issyr = int(monthval[:4]) - 1
                                            datechkit = True

                                        if datechkit is True and issyr is not None:
                                            logger.fdebug('%s[ISSUE-VERIFY] %s comparing to %s : rechecking by month-check versus year.' % (module, issyr, watchmatch['issue_year']))
                                            datematch = "True"
                                            if int(issyr) != int(watchmatch['issue_year']):
                                                logger.fdebug('%s[ISSUE-VERIFY][.:FAIL:.] Issue is before the modified issue year of %s' % (module, issyr))
                                                datematch = "False"

                                else:
                                    if fcdigit is None:
                                        logger.info('%s[ISSUE-VERIFY] Found matching issue for ComicID: %s / IssueID: %s' % (module, cs['ComicID'], isc['IssueID']))
                                    else:
                                        logger.info('%s[ISSUE-VERIFY] Found matching issue # %s for ComicID: %s / IssueID: %s' % (module, fcdigit, cs['ComicID'], isc['IssueID']))

                                if datematch == "True":
                                    #need to reset this to False here so that the True doesn't carry down and avoid the year checks due to the True
                                    datematch = "False"
                                    # if we get to here, we need to do some more comparisons just to make sure we have the right volume
                                    # first we chk volume label if it exists, then we drop down to issue year
                                    # if the above both don't exist, and there's more than one series on the watchlist (or the series is > v1)
                                    # then spit out the error message and don't post-process it.
                                    watch_values = cs['WatchValues']
                                    #logger.fdebug('WATCH_VALUES:' + str(watch_values))
                                    if any([watch_values['ComicVersion'] is None, watch_values['ComicVersion'] == 'None']):
                                        tmp_watchlist_vol = '1'
                                    else:
                                        tmp_watchlist_vol = re.sub("[^0-9]", "", watch_values['ComicVersion']).strip()
                                    if all([watchmatch['series_volume'] != 'None', watchmatch['series_volume'] is not None]):
                                        tmp_watchmatch_vol = re.sub("[^0-9]","", watchmatch['series_volume']).strip()
                                        if len(tmp_watchmatch_vol) == 4:
                                            if int(tmp_watchmatch_vol) == int(watch_values['SeriesYear']):
                                                logger.fdebug('%s[ISSUE-VERIFY][SeriesYear-Volume MATCH] Series Year of %s matched to volume/year label of %s' % (module, watch_values['SeriesYear'], tmp_watchmatch_vol))
                                            else:
                                                logger.fdebug('%s[ISSUE-VERIFY][SeriesYear-Volume FAILURE] Series Year of %s DID NOT match to volume/year label of %s' % (module, watch_values['SeriesYear'], tmp_watchmatch_vol))
                                                datematch = "False"
                                        elif len(watchvals) > 1 and int(tmp_watchmatch_vol) >= 1:
                                            if int(tmp_watchmatch_vol) == int(tmp_watchlist_vol):
                                                logger.fdebug('%s[ISSUE-VERIFY][SeriesYear-Volume MATCH] Volume label of series Year of %s matched to volume label of %s' % (module, watch_values['ComicVersion'], watchmatch['series_volume']))
                                            else:
                                                logger.fdebug('%s[ISSUE-VERIFY][SeriesYear-Volume FAILURE] Volume label of Series Year of %s DID NOT match to volume label of %s' % (module, watch_values['ComicVersion'], watchmatch['series_volume']))
                                                datematch = "False"
                                    else:
                                        if any([tmp_watchlist_vol is None, tmp_watchlist_vol == 'None', tmp_watchlist_vol == '']):
                                            logger.fdebug('%s[ISSUE-VERIFY][NO VOLUME PRESENT] No Volume label present for series. Dropping down to Issue Year matching.' % module)
                                            datematch = "False"
                                        elif len(watchvals) == 1 and int(tmp_watchlist_vol) == 1:
                                            logger.fdebug('%s[ISSUE-VERIFY][Lone Volume MATCH] Volume label of %s indicates only volume for this series on your watchlist.' % (module, watch_values['ComicVersion']))
                                        elif int(tmp_watchlist_vol) > 1:
                                            logger.fdebug('%s[ISSUE-VERIFY][Lone Volume FAILURE] Volume label of %s indicates that there is more than one volume for this series, but the one on your watchlist has no volume label set.' % (module, watch_values['ComicVersion']))
                                            datematch = "False"

                                    if datematch == "False" and all([watchmatch['issue_year'] is not None, watchmatch['issue_year'] != 'None', watch_issueyear is not None]):
                                        #now we see if the issue year matches exactly to what we have within Mylar.
                                        if int(watch_issueyear) == int(watchmatch['issue_year']):
                                            logger.fdebug('%s[ISSUE-VERIFY][Issue Year MATCH] Issue Year of %s is a match to the year found in the filename of : %s' % (module, watch_issueyear, watchmatch['issue_year']))
                                            datematch = 'True'
                                        else:
                                            logger.fdebug('%s[ISSUE-VERIFY][Issue Year FAILURE] Issue Year of %s does NOT match the year found in the filename of : %s' % (module, watch_issueyear, watchmatch['issue_year']))
                                            logger.fdebug('%s[ISSUE-VERIFY] Checking against complete date to see if month published could allow for different publication year.' % module)
                                            if issyr is not None:
                                                if int(issyr) != int(watchmatch['issue_year']):
                                                    logger.fdebug('%s[ISSUE-VERIFY][Issue Year FAILURE] Modified Issue year of %s is before the modified issue year of %s' % (module, issyr, watchmatch['issue_year']))
                                                else:
                                                    logger.fdebug('%s[ISSUE-VERIFY][Issue Year MATCH] Modified Issue Year of %s is a match to the year found in the filename of : %s' % (module, issyr, watchmatch['issue_year']))
                                                    datematch = 'True'

                                    if datematch == 'True':
                                        if watchmatch['sub']:
                                            logger.fdebug('%s[SUB: %s][CLOCATION: %s]' % (module, watchmatch['sub'], watchmatch['comiclocation']))
                                            clocation = os.path.join(watchmatch['comiclocation'], watchmatch['sub'], helpers.conversion(watchmatch['comicfilename']))
                                            if not os.path.exists(clocation):
                                                scrubs = re.sub(watchmatch['comiclocation'], '', watchmatch['sub']).strip()
                                                if scrubs[:2] == '//' or scrubs[:2] == '\\':
                                                    scrubs = scrubs[1:]
                                                    if os.path.exists(scrubs):
                                                        logger.fdebug('[MODIFIED CLOCATION] %s' % scrubs)
                                                        clocation = scrubs
                                        else:
                                            logger.fdebug('%s[CLOCATION] %s' % (module, watchmatch['comiclocation']))
                                            if self.issueid is not None and os.path.isfile(watchmatch['comiclocation']):
                                                clocation = watchmatch['comiclocation']
                                            else:
                                                clocation = os.path.join(watchmatch['comiclocation'],helpers.conversion(watchmatch['comicfilename']))
                                        annualtype = None
                                        if annchk == 'yes':
                                            if 'Annual' in isc['ReleaseComicName']:
                                                annualtype = 'Annual'
                                            elif 'Special' in isc['ReleaseComicName']:
                                                annualtype = 'Special'
                                        else:
                                            if 'Annual' in isc['ComicName']:
                                                annualtype = 'Annual'
                                            elif 'Special' in isc['ComicName']:
                                                annualtype = 'Special'

                                        manual_list.append({"ComicLocation":   clocation,
                                                            "ComicID":         cs['ComicID'],
                                                            "IssueID":         isc['IssueID'],
                                                            "IssueNumber":     isc['Issue_Number'],
                                                            "AnnualType":      annualtype,
                                                            "ComicName":       cs['ComicName'],
                                                            "Series":          watchmatch['series_name'],
                                                            "AltSeries":       watchmatch['alt_series'],
                                                            "One-Off":         False,
                                                            "ForcedMatch":     False})
                                        break
                                    else:
                                        logger.fdebug('%s[NON-MATCH: %s-%s] Incorrect series - not populating..continuing post-processing' % (module, cs['ComicName'], cs['ComicID']))
                                        continue
                                else:
                                    logger.fdebug('%s[NON-MATCH: %s-%s] Incorrect series - not populating..continuing post-processing' % (module, cs['ComicName'], cs['ComicID']))
                                    continue

                        if datematch == 'True':
                            xmld = filechecker.FileChecker()
                            xmld1 = xmld.dynamic_replace(helpers.conversion(cs['ComicName']))
                            xseries = xmld1['mod_seriesname'].lower()
                            xmld2 = xmld.dynamic_replace(helpers.conversion(watchmatch['series_name']))
                            xfile = xmld2['mod_seriesname'].lower()

                            if re.sub('\|', '', xseries) == re.sub('\|', '', xfile):
                                logger.fdebug('%s[DEFINITIVE-NAME MATCH] Definitive name match exactly to : %s [%s]' % (module, watchmatch['series_name'], cs['ComicID']))
                                if len(manual_list) > 1:
                                    manual_list = [item for item in manual_list if all([item['IssueID'] == isc['IssueID'], item['AnnualType'] is not None]) or all([item['IssueID'] == isc['IssueID'], item['ComicLocation'] == clocation]) or all([item['IssueID'] != isc['IssueID'], item['ComicLocation'] != clocation])]
                                self.matched = True
                            else:
                                continue #break

                        if datematch == 'True':
                            logger.fdebug('%s[SUCCESSFUL MATCH: %s-%s] Match verified for %s' % (module, cs['ComicName'], cs['ComicID'], helpers.conversion(fl['comicfilename'])))
                            break
                        elif self.matched is True:
                            logger.warn('%s[MATCH: %s - %s] We matched by name for this series, but cannot find a corresponding issue number in the series list.' % (module, cs['ComicName'], cs['ComicID']))

                    #we should setup for manual post-processing of story-arc issues here
                    #we can also search by ComicID to just grab those particular arcs as an alternative as well (not done)

                    #as_d = filechecker.FileChecker()
                    #as_dinfo = as_d.dynamic_replace(helpers.conversion(fl['series_name']))
                    #mod_seriesname = as_dinfo['mod_seriesname']
                    #arcloopchk = []
                    #for x in alt_list:
                    #    cname = x['AS_DyComicName']
                    #    for ab in x['AS_Alt']:
                    #        if re.sub('[\|\s]', '', mod_seriesname.lower()).strip() in re.sub('[\|\s]', '', ab.lower()).strip():
                    #            if not any(re.sub('[\|\s]', '', cname.lower()) == x for x in arcloopchk):
                    #                arcloopchk.append(re.sub('[\|\s]', '', cname.lower()))

                    ##make sure we add back in the original parsed filename here.
                    #if not any(re.sub('[\|\s]', '', mod_seriesname).lower() == x for x in arcloopchk):
                    #    arcloopchk.append(re.sub('[\|\s]', '', mod_seriesname.lower()))
                    if self.issuearcid is None:
                        tmpsql = "SELECT * FROM storyarcs WHERE DynamicComicName IN ({seq}) COLLATE NOCASE".format(seq=','.join('?' * len(loopchk))) #len(arcloopchk)))
                        arc_series = myDB.select(tmpsql, tuple(loopchk)) #arcloopchk))
                    else:
                        if self.issuearcid[0] == 'S':
                            self.issuearcid = self.issuearcid[1:]
                        arc_series = myDB.select("SELECT * FROM storyarcs WHERE IssueArcID=?", [self.issuearcid])

                    if arc_series is None:
                        logger.error('%s No Story Arcs in Watchlist that contain that particular series - aborting Manual Post Processing. Maybe you should be running Import?' % module)
                        return
                    else:
                        arcvals = []
                        for av in arc_series:
                            arcvals.append({"ComicName":       av['ComicName'],
                                            "ArcValues":       {"StoryArc":         av['StoryArc'],
                                                                "StoryArcID":       av['StoryArcID'],
                                                                "IssueArcID":       av['IssueArcID'],
                                                                "ComicName":        av['ComicName'],
                                                                "DynamicComicName": av['DynamicComicName'],
                                                                "ComicPublisher":   av['IssuePublisher'],
                                                                "Publisher":        av['Publisher'],
                                                                "IssueID":          av['IssueID'],
                                                                "IssueNumber":      av['IssueNumber'],
                                                                "IssueYear":        av['IssueYear'],   #for some reason this is empty 
                                                                "ReadingOrder":     av['ReadingOrder'],
                                                                "IssueDate":        av['IssueDate'],
                                                                "Status":           av['Status'],
                                                                "Location":         av['Location']},
                                            "WatchValues":     {"SeriesYear":       av['SeriesYear'],
                                                                "LatestDate":       av['IssueDate'],
                                                                "ComicVersion":     av['Volume'],
                                                                "ComicID":          av['ComicID'],
                                                                "Publisher":        av['IssuePublisher'],
                                                                "Total":            av['TotalIssues'],   # this will return the total issues in the arc (not needed for this)
                                                                "Type":             av['Type'],
                                                                "IsArc":            True}
                                            })

                        ccnt=0
                        nm=0
                        from collections import defaultdict
                        res = defaultdict(list)
                        for acv in arcvals:
                            if len(manual_list) == 0:
                                res[acv['ComicName']].append({"ArcValues":     acv['ArcValues'],
                                                              "WatchValues":   acv['WatchValues']})
                            else:
                                acv_check = [x for x in manual_list if x['ComicID'] == acv['WatchValues']['ComicID']]
                                if acv_check:
                                    res[acv['ComicName']].append({"ArcValues":     acv['ArcValues'],
                                                                  "WatchValues":   acv['WatchValues']})
                    if len(res) > 0:
                        logger.fdebug('%s Now Checking if %s issue(s) may also reside in one of the storyarc\'s that I am watching.' % (module, len(res)))
                    for k,v in res.items():
                        i = 0
                        #k is ComicName
                        #v is ArcValues and WatchValues
                        while i < len(v):
                            if k is None or k == 'None':
                                pass
                            else:
                                arcm = filechecker.FileChecker(watchcomic=k, Publisher=v[i]['ArcValues']['ComicPublisher'], manual=v[i]['WatchValues'])
                                arcmatch = arcm.matchIT(fl)
                                #logger.fdebug('arcmatch: ' + str(arcmatch))
                                if arcmatch['process_status'] == 'fail':
                                    nm+=1
                                else:
                                    try:
                                        if all([v[i]['WatchValues']['Type'] == 'TPB', v[i]['WatchValues']['Total'] > 1]) or all([v[i]['WatchValues']['Type'] == 'One-Shot', v[i]['WatchValues']['Total'] == 1]):
                                            if watchmatch['series_volume'] is not None:
                                                just_the_digits = re.sub('[^0-9]', '', arcmatch['series_volume']).strip()
                                            else:
                                                just_the_digits = re.sub('[^0-9]', '', arcmatch['justthedigits']).strip()
                                        else:
                                            just_the_digits = arcmatch['justthedigits']
                                    except Exception as e:
                                        logger.warn('[Exception: %s] Unable to properly match up/retrieve issue number (or volume) for this [CS: %s] [WATCHMATCH: %s]' % (e, v[i]['ArcValues'], v[i]['WatchValues']))
                                        nm+=1
                                        continue

                                    if just_the_digits is not None:
                                        temploc= just_the_digits.replace('_', ' ')
                                        temploc = re.sub('[\#\']', '', temploc)
                                        #logger.fdebug('temploc: %s' % temploc)
                                    else:
                                        if any([v[i]['WatchValues']['Type'] == 'TPB', v[i]['WatchValues']['Type'] == 'One-Shot']):
                                            temploc = '1'
                                        else:
                                            temploc = None

                                    if temploc is not None and helpers.issuedigits(temploc) != helpers.issuedigits(v[i]['ArcValues']['IssueNumber']):
                                        #logger.fdebug('issues dont match. Skipping')
                                        i+=1
                                        continue
                                    else:
                                        if temploc is not None and (any(['annual' in temploc.lower(), 'special' in temploc.lower()]) and mylar.CONFIG.ANNUALS_ON is True):
                                            biannchk = re.sub('-', '', temploc.lower()).strip()
                                            if 'biannual' in biannchk:
                                                logger.fdebug('%s Bi-Annual detected.' % module)
                                                fcdigit = helpers.issuedigits(re.sub('biannual', '', str(biannchk)).strip())
                                            else:
                                                if 'annual' in temploc.lower():
                                                    fcdigit = helpers.issuedigits(re.sub('annual', '', str(temploc.lower())).strip())
                                                else:
                                                    fcdigit = helpers.issuedigits(re.sub('special', '', str(temploc.lower())).strip())
                                                logger.fdebug('%s Annual detected [%s]. ComicID assigned as %s' % (module, fcdigit, v[i]['WatchValues']['ComicID']))
                                            annchk = "yes"
                                            issuechk = myDB.selectone("SELECT * from storyarcs WHERE ComicID=? AND Int_IssueNumber=?", [v[i]['WatchValues']['ComicID'], fcdigit]).fetchone()
                                        else:
                                            annchk = "no"
                                            if temploc is not None:
                                                fcdigit = helpers.issuedigits(temploc)
                                                issuechk = myDB.select("SELECT * from storyarcs WHERE ComicID=? AND Int_IssueNumber=?", [v[i]['WatchValues']['ComicID'], fcdigit])
                                            else:
                                                fcdigit = None
                                                issuechk = myDB.select("SELECT * from storyarcs WHERE ComicID=?", [v[i]['WatchValues']['ComicID']])

                                    if issuechk is None:
                                        try:
                                            logger.fdebug('%s No corresponding issue # found for %s' % (module, v[i]['WatchValues']['ComicID']))
                                        except:
                                            continue
                                    else:
                                        for isc in issuechk:
                                            datematch = "True"
                                            datechkit = False
                                            if isc['ReleaseDate'] is not None and isc['ReleaseDate'] != '0000-00-00':
                                                try:
                                                    if isc['DigitalDate'] != '0000-00-00' and int(re.sub('-', '', isc['DigitalDate']).strip()) <= int(re.sub('-', '', isc['ReleaseDate']).strip()):
                                                        monthval = isc['DigitalDate']
                                                        arc_issueyear = isc['DigitalDate'][:4]
                                                    else:
                                                        monthval = isc['ReleaseDate']
                                                        arc_issueyear = isc['ReleaseDate'][:4]
                                                except:
                                                    monthval = isc['ReleaseDate']
                                                    arc_issueyear = isc['ReleaseDate'][:4]

                                            else:
                                                try:
                                                    if isc['DigitalDate'] != '0000-00-00' and int(re.sub('-', '', isc['DigitalDate']).strip()) <= int(re.sub('-', '', isc['ReleaseDate']).strip()):
                                                        monthval = isc['DigitalDate']
                                                        arc_issueyear = isc['DigitalDate'][:4]
                                                    else:
                                                        monthval = isc['IssueDate']
                                                        arc_issueyear = isc['IssueDate'][:4]
                                                except:
                                                    monthval = isc['IssueDate']
                                                    arc_issueyear = isc['IssueDate'][:4]


                                            if len(arcmatch) >= 1 and arcmatch['issue_year'] is not None:
                                                #if the # of matches is more than 1, we need to make sure we get the right series
                                                #compare the ReleaseDate for the issue, to the found issue date in the filename.
                                                #if ReleaseDate doesn't exist, use IssueDate
                                                #if no issue date was found, then ignore.
                                                logger.fdebug('%s[ARC ISSUE-VERIFY] Now checking against %s - %s' % (module, k, v[i]['WatchValues']['ComicID']))
                                                issyr = None
                                                #logger.fdebug('issuedate: %s' % isc['IssueDate'])
                                                #logger.fdebug('issuechk: %s' % isc['IssueDate'][5:7])
                                                #logger.fdebug('StoreDate %s' % isc['ReleaseDate'])
                                                #logger.fdebug('IssueDate: %s' % isc['IssueDate'])
                                                if isc['DigitalDate'] is not None and isc['DigitalDate'] != '0000-00-00':
                                                    if int(isc['DigitalDate'][:4]) < int(arcmatch['issue_year']):
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY] %s is before the issue year of %s that was discovered in the filename' % (module, isc['DigitalDate'], arcmatch['issue_year']))
                                                        datematch = "False"

                                                elif all([isc['ReleaseDate'] is not None, isc['ReleaseDate'] != '0000-00-00']):
                                                    if isc['ReleaseDate'] == '0000-00-00':
                                                        datevalue = isc['IssueDate']
                                                    else:
                                                        datevalue = isc['ReleaseDate']
                                                    if int(datevalue[:4]) < int(arcmatch['issue_year']):
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY] %s is before the issue year %s that was discovered in the filename' % (module, datevalue[:4], arcmatch['issue_year']))
                                                        datematch = "False"
                                                elif all([isc['IssueDate'] is not None, isc['IssueDate'] != '0000-00-00']):
                                                    if isc['IssueDate'] == '0000-00-00':
                                                        datevalue = isc['ReleaseDate']
                                                    else:
                                                        datevalue = isc['IssueDate']
                                                    if int(datevalue[:4]) < int(arcmatch['issue_year']):
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY] %s is before the issue year of %s that was discovered in the filename' % (module, datevalue[:4], arcmatch['issue_year']))
                                                        datematch = "False"
                                                else:
                                                    if int(isc['IssueDate'][:4]) < int(arcmatch['issue_year']):
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY] %s is before the issue year %s that was discovered in the filename' % (module, isc['IssueDate'], arcmatch['issue_year']))
                                                        datematch = "False"

                                                if int(arc_issueyear) != int(arcmatch['issue_year']):
                                                    if int(monthval[5:7]) == 11 or int(monthval[5:7]) == 12:
                                                        issyr = int(monthval[:4]) + 1
                                                        datechkit = True
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY] IssueYear (issyr) is %s' % (module, issyr))
                                                    elif int(monthval[5:7]) == 1 or int(monthval[5:7]) == 2 or int(monthval[5:7]) == 3:
                                                        issyr = int(monthval[:4]) - 1
                                                        datechkit = True

                                                    if datechkit is True and issyr is not None:
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY] %s comparing to %s : rechecking by month-check versus year.' % (module, issyr, arcmatch['issue_year']))
                                                        datematch = "True"
                                                        if int(issyr) != int(arcmatch['issue_year']):
                                                            logger.fdebug('%s[.:FAIL:.] Issue is before the modified issue year of %s' % (module, issyr))
                                                            datematch = "False"

                                            else:
                                                if fcdigit is None:
                                                    logger.info('%s Found matching issue for ComicID: %s / IssueID: %s' % (module, v[i]['WatchValues']['ComicID'], isc['IssueID']))
                                                else:
                                                    logger.info('%s Found matching issue # %s for ComicID: %s / IssueID: %s' % (module, fcdigit, v[i]['WatchValues']['ComicID'], isc['IssueID']))

                                            logger.fdebug('datematch: %s' % datematch)
                                            logger.fdebug('temploc: %s' % helpers.issuedigits(temploc))
                                            logger.fdebug('arcissue: %s' % helpers.issuedigits(v[i]['ArcValues']['IssueNumber']))
                                            if datematch == "True" and helpers.issuedigits(temploc) == helpers.issuedigits(v[i]['ArcValues']['IssueNumber']):
                                                #reset datematch here so it doesn't carry the value down and avoid year checks
                                                datematch = "False"
                                                arc_values = v[i]['WatchValues']
                                                if any([arc_values['ComicVersion'] is None, arc_values['ComicVersion'] == 'None']):
                                                    tmp_arclist_vol = '1'
                                                else:
                                                    tmp_arclist_vol = re.sub("[^0-9]", "", arc_values['ComicVersion']).strip()
                                                if all([arcmatch['series_volume'] != 'None', arcmatch['series_volume'] is not None]):
                                                    tmp_arcmatch_vol = re.sub("[^0-9]","", arcmatch['series_volume']).strip()
                                                    if len(tmp_arcmatch_vol) == 4:
                                                        if int(tmp_arcmatch_vol) == int(arc_values['SeriesYear']):
                                                            logger.fdebug('%s[ARC ISSUE-VERIFY][SeriesYear-Volume MATCH] Series Year of %s matched to volume/year label of %s' % (module, arc_values['SeriesYear'], tmp_arcmatch_vol))
                                                        else:
                                                            logger.fdebug('%s[ARC ISSUE-VERIFY][SeriesYear-Volume FAILURE] Series Year of %s DID NOT match to volume/year label of %s' % (module, arc_values['SeriesYear'], tmp_arcmatch_vol))
                                                            datematch = "False"
                                                    if len(arcvals) > 1 and int(tmp_arcmatch_vol) >= 1:
                                                        if int(tmp_arcmatch_vol) == int(tmp_arclist_vol):
                                                            logger.fdebug('%s[ARC ISSUE-VERIFY][SeriesYear-Volume MATCH] Volume label of series Year of %s matched to volume label of %s' % (module, arc_values['ComicVersion'], arcmatch['series_volume']))
                                                        else:
                                                            logger.fdebug('%s[ARC ISSUE-VERIFY][SeriesYear-Volume FAILURE] Volume label of Series Year of %s DID NOT match to volume label of %s' % (module, arc_values['ComicVersion'], arcmatch['series_volume']))
                                                            datematch = "False"
                                                else:
                                                    if any([tmp_arclist_vol is None, tmp_arclist_vol == 'None', tmp_arclist_vol == '']):
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY][NO VOLUME PRESENT] No Volume label present for series. Dropping down to Issue Year matching.' % module)
                                                        datematch = "False"
                                                    elif len(arcvals) == 1 and int(tmp_arclist_vol) == 1:
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY][Lone Volume MATCH] Volume label of %s indicates only volume for this series on your watchlist.' % (module, arc_values['ComicVersion']))
                                                    elif int(tmp_arclist_vol) > 1:
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY][Lone Volume FAILURE] Volume label of %s indicates that there is more than one volume for this series, but the one on your watchlist has no volume label set.' % (module, arc_values['ComicVersion']))
                                                        datematch = "False"

                                                if datematch == "False" and all([arcmatch['issue_year'] is not None, arcmatch['issue_year'] != 'None', arc_issueyear is not None]):
                                                    #now we see if the issue year matches exactly to what we have within Mylar.
                                                    if int(arc_issueyear) == int(arcmatch['issue_year']):
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY][Issue Year MATCH] Issue Year of %s is a match to the year found in the filename of : %s' % (module, arc_issueyear, arcmatch['issue_year']))
                                                        datematch = 'True'
                                                    else:
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY][Issue Year FAILURE] Issue Year of %s does NOT match the year found in the filename of : %s' % (module, arc_issueyear, arcmatch['issue_year']))
                                                        logger.fdebug('%s[ARC ISSUE-VERIFY] Checking against complete date to see if month published could allow for different publication year.' % module)
                                                        if issyr is not None:
                                                            if int(issyr) != int(arcmatch['issue_year']):
                                                                logger.fdebug('%s[ARC ISSUE-VERIFY][Issue Year FAILURE] Modified Issue year of %s is before the modified issue year of %s' % (module, issyr, arcmatch['issue_year']))
                                                            else:
                                                                logger.fdebug('%s[ARC ISSUE-VERIFY][Issue Year MATCH] Modified Issue Year of %s is a match to the year found in the filename of : %s' % (module, issyr, arcmatch['issue_year']))
                                                                datematch = 'True'

                                                if datematch == 'True':
                                                    passit = False
                                                    if len(manual_list) > 0:
                                                        if any([ v[i]['ArcValues']['IssueID'] == x['IssueID'] for x in manual_list ]):
                                                            logger.info('[STORY-ARC POST-PROCESSING] IssueID %s exists in your watchlist. Bypassing Story-Arc post-processing performed later.' % v[i]['ArcValues']['IssueID'])
                                                            #add in the storyarcid into the manual list so it will perform story-arc functions after normal manual PP is finished.
                                                            for a in manual_list:
                                                                if a['IssueID'] == v[i]['ArcValues']['IssueID']:
                                                                    a['IssueArcID'] = v[i]['ArcValues']['IssueArcID']
                                                                    break
                                                            passit = True

                                                    if passit == False:
                                                        tmpfilename = helpers.conversion(arcmatch['comicfilename'])
                                                        if arcmatch['sub']:
                                                            clocation = os.path.join(arcmatch['comiclocation'], arcmatch['sub'], tmpfilename)
                                                        else:
                                                            clocation = os.path.join(arcmatch['comiclocation'], tmpfilename)
                                                        logger.info('[%s #%s] MATCH: %s / %s / %s' % (k, isc['IssueNumber'], clocation, isc['IssueID'], v[i]['ArcValues']['IssueID']))
                                                        if v[i]['ArcValues']['Publisher'] is None:
                                                            arcpublisher = v[i]['ArcValues']['ComicPublisher']
                                                        else:
                                                            arcpublisher = v[i]['ArcValues']['Publisher']

                                                        manual_arclist.append({"ComicLocation":   clocation,
                                                                               "Filename":        tmpfilename,
                                                                               "ComicID":         v[i]['WatchValues']['ComicID'],
                                                                               "IssueID":         v[i]['ArcValues']['IssueID'],
                                                                               "IssueNumber":     v[i]['ArcValues']['IssueNumber'],
                                                                               "StoryArc":        v[i]['ArcValues']['StoryArc'],
                                                                               "StoryArcID":      v[i]['ArcValues']['StoryArcID'],
                                                                               "IssueArcID":      v[i]['ArcValues']['IssueArcID'],
                                                                               "Publisher":       arcpublisher,
                                                                               "ReadingOrder":    v[i]['ArcValues']['ReadingOrder'],
                                                                               "ComicName":       k})
                                                        logger.info('%s[SUCCESSFUL MATCH: %s-%s] Match verified for %s' % (module, k, v[i]['WatchValues']['ComicID'], arcmatch['comicfilename']))
                                                        self.matched = True
                                                        break
                                                else:
                                                    logger.fdebug('%s[NON-MATCH: %s-%s] Incorrect series - not populating..continuing post-processing' % (module, k, v[i]['WatchValues']['ComicID']))

                            i+=1
                    if self.matched is False:
                        #one-off manual pp'd of torrents
                        if all(['0-Day Week' in self.nzb_name, mylar.CONFIG.PACK_0DAY_WATCHLIST_ONLY is True]):
                            pass
                        else:
                            oneofflist = myDB.select("select s.Issue_Number, s.ComicName, s.IssueID, s.ComicID, s.Provider, w.format, w.PUBLISHER, w.weeknumber, w.year from snatched as s inner join nzblog as n on s.IssueID = n.IssueID inner join weekly as w on s.IssueID = w.IssueID WHERE n.OneOff = 1;") #(s.Provider ='32P' or s.Provider='WWT' or s.Provider='DEM') AND n.OneOff = 1;")
                            #oneofflist = myDB.select("select s.Issue_Number, s.ComicName, s.IssueID, s.ComicID, s.Provider, w.PUBLISHER, w.weeknumber, w.year from snatched as s inner join nzblog as n on s.IssueID = n.IssueID and s.Hash is not NULL inner join weekly as w on s.IssueID = w.IssueID WHERE n.OneOff = 1;") #(s.Provider ='32P' or s.Provider='WWT' or s.Provider='DEM') AND n.OneOff = 1;")
                            if not oneofflist:
                                pass #continue
                            else:
                                logger.fdebug('%s[ONEOFF-SELECTION][self.nzb_name: %s]' % (module, self.nzb_name))
                                oneoffvals = []
                                for ofl in oneofflist:
                                    #logger.info('[ONEOFF-SELECTION] ofl: %s' % ofl)
                                    oneoffvals.append({"ComicName":       ofl['ComicName'],
                                                       "ComicPublisher":  ofl['PUBLISHER'],
                                                       "Issue_Number":    ofl['Issue_Number'],
                                                       "AlternateSearch": None,
                                                       "ComicID":         ofl['ComicID'],
                                                       "IssueID":         ofl['IssueID'],
                                                       "WatchValues": {"SeriesYear":   None,
                                                                       "LatestDate":   None,
                                                                       "ComicVersion": None,
                                                                       "Publisher":    ofl['PUBLISHER'],
                                                                       "Total":        None,
                                                                       "Type":         ofl['format'],
                                                                       "ComicID":      ofl['ComicID'],
                                                                       "IsArc":        False}})

                                #this seems redundant to scan in all over again...
                                #for fl in filelist['comiclist']:
                                for ofv in oneoffvals:
                                    #logger.info('[ONEOFF-SELECTION] ofv: %s' % ofv)
                                    wm = filechecker.FileChecker(watchcomic=ofv['ComicName'], Publisher=ofv['ComicPublisher'], AlternateSearch=None, manual=ofv['WatchValues'])
                                    #if fl['sub'] is not None:
                                    #    pathtofile = os.path.join(fl['comiclocation'], fl['sub'], fl['comicfilename'])
                                    #else:
                                    #    pathtofile = os.path.join(fl['comiclocation'], fl['comicfilename'])
                                    watchmatch = wm.matchIT(fl)
                                    if watchmatch['process_status'] == 'fail':
                                        nm+=1
                                        continue
                                    else:
                                        try:
                                            if ofv['WatchValues']['Type'] is not None and ofv['WatchValues']['Total'] > 1:
                                                if watchmatch['series_volume'] is not None:
                                                    just_the_digits = re.sub('[^0-9]', '', watchmatch['series_volume']).strip()
                                                else:
                                                    just_the_digits = re.sub('[^0-9]', '', watchmatch['justthedigits']).strip()
                                            else:
                                                just_the_digits = watchmatch['justthedigits']
                                        except Exception as e:
                                            logger.warn('[Exception: %s] Unable to properly match up/retrieve issue number (or volume) for this [CS: %s] [WATCHMATCH: %s]' % (e, cs, watchmatch))
                                            nm+=1
                                            continue

                                        if just_the_digits is not None:
                                            temploc= just_the_digits.replace('_', ' ')
                                            temploc = re.sub('[\#\']', '', temploc)
                                            logger.fdebug('temploc: %s' % temploc)
                                        else:
                                            temploc = None

                                    logger.info('watchmatch: %s' % watchmatch)
                                    if temploc is not None:
                                        if 'annual' in temploc.lower():
                                            biannchk = re.sub('-', '', temploc.lower()).strip()
                                            if 'biannual' in biannchk:
                                                logger.fdebug('%s Bi-Annual detected.' % module)
                                                fcdigit = helpers.issuedigits(re.sub('biannual', '', str(biannchk)).strip())
                                            else:
                                                fcdigit = helpers.issuedigits(re.sub('annual', '', str(temploc.lower())).strip())
                                                logger.fdebug('%s Annual detected [%s]. ComicID assigned as %s' % (module, fcdigit, ofv['ComicID']))
                                            annchk = "yes"
                                        else:
                                            fcdigit = helpers.issuedigits(temploc)

                                    if temploc is not None and fcdigit == helpers.issuedigits(ofv['Issue_Number']) or all([temploc is None, helpers.issuedigits(ofv['Issue_Number']) == '1']):
                                        if watchmatch['sub']:
                                            clocation = os.path.join(watchmatch['comiclocation'], watchmatch['sub'], helpers.conversion(watchmatch['comicfilename']))
                                            if not os.path.exists(clocation):
                                                scrubs = re.sub(watchmatch['comiclocation'], '', watchmatch['sub']).strip()
                                                if scrubs[:2] == '//' or scrubs[:2] == '\\':
                                                    scrubs = scrubs[1:]
                                                    if os.path.exists(scrubs):
                                                        logger.fdebug('[MODIFIED CLOCATION] %s' % scrubs)
                                                        clocation = scrubs

                                        else:
                                            if self.issueid is not None and os.path.isfile(watchmatch['comiclocation']):
                                                clocation = watchmatch['comiclocation']
                                            else:
                                                clocation = os.path.join(watchmatch['comiclocation'],helpers.conversion(watchmatch['comicfilename']))
                                        oneoff_issuelist.append({"ComicLocation":   clocation,
                                                                 "ComicID":         ofv['ComicID'],
                                                                 "IssueID":         ofv['IssueID'],
                                                                 "IssueNumber":     ofv['Issue_Number'],
                                                                 "ComicName":       ofv['ComicName'],
                                                                 "One-Off":         True})
                                        self.oneoffinlist = True
                                    else:
                                        logger.fdebug('%s No corresponding issue # in dB found for %s # %s' % (module, ofv['ComicName'], ofv['Issue_Number']))
                                        continue

                                    logger.fdebug('%s[SUCCESSFUL MATCH: %s-%s] Match Verified for %s' % (module, ofv['ComicName'], ofv['ComicID'], helpers.conversion(fl['comicfilename'])))
                                    self.matched = True
                                    break

                if filelist['comiccount'] > 0:
                    logger.fdebug('%s There are %s files found that match on your watchlist, %s files are considered one-off\'s, and %s files do not match anything' % (module, len(manual_list), len(oneoff_issuelist), int(filelist['comiccount']) - len(manual_list)))

                delete_arc = []
                if len(manual_arclist) > 0:
                    logger.info('[STORY-ARC MANUAL POST-PROCESSING] I have found %s issues that belong to Story Arcs. Flinging them into the correct directories.' % len(manual_arclist))
                    for ml in manual_arclist:
                        issueid = ml['IssueID']
                        ofilename = orig_filename = ml['ComicLocation']
                        logger.info('[STORY-ARC POST-PROCESSING] Enabled for %s' % ml['StoryArc'])

                        if all([mylar.CONFIG.STORYARCDIR is True, mylar.CONFIG.COPY2ARCDIR is True]):
                            grdst = helpers.arcformat(ml['StoryArc'], helpers.spantheyears(ml['StoryArcID']), ml['Publisher'])
                            logger.info('grdst: %s' % grdst)

                            #tag the meta.
                            metaresponse = None

                            crcvalue = helpers.crc(ofilename)

                            if mylar.CONFIG.ENABLE_META:
                                logger.info('[STORY-ARC POST-PROCESSING] Metatagging enabled - proceeding...')
                                try:
                                    import cmtagmylar
                                    metaresponse = cmtagmylar.run(self.nzb_folder, issueid=issueid, filename=ofilename)
                                except ImportError:
                                    logger.warn('%s comictaggerlib not found on system. Ensure the ENTIRE lib directory is located within mylar/lib/comictaggerlib/' % module)
                                    metaresponse = "fail"

                                if metaresponse == "fail":
                                    logger.fdebug('%s Unable to write metadata successfully - check mylar.log file. Attempting to continue without metatagging...' % module)
                                elif any([metaresponse == "unrar error", metaresponse == "corrupt"]):
                                    logger.error('%s This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and retrying it.' % module)
                                    continue
                                    #launch failed download handling here.
                                elif metaresponse.startswith('file not found'):
                                    filename_in_error = metaresponse.split('||')[1]
                                    self._log("The file cannot be found in the location provided for metatagging to be used [%s]. Please verify it exists, and re-run if necessary. Attempting to continue without metatagging..." % (filename_in_error))
                                    logger.error('%s The file cannot be found in the location provided for metatagging to be used [%s]. Please verify it exists, and re-run if necessary. Attempting to continue without metatagging...' % (module, filename_in_error))
                                else:
                                    odir = os.path.split(metaresponse)[0]
                                    ofilename = os.path.split(metaresponse)[1]
                                    ext = os.path.splitext(metaresponse)[1]
                                    logger.info('%s Sucessfully wrote metadata to .cbz (%s) - Continuing..' % (module, ofilename))
                                    self._log('Sucessfully wrote metadata to .cbz (%s) - proceeding...' % ofilename)

                                dfilename = ofilename
                            else:
                                dfilename = ml['Filename']


                            if metaresponse:
                                src_location = odir
                                grab_src = os.path.join(src_location, ofilename)
                            else:
                                src_location = ofilename
                                grab_src = ofilename

                            logger.fdebug('%s Source Path : %s' % (module, grab_src))

                            checkdirectory = filechecker.validateAndCreateDirectory(grdst, True, module=module)
                            if not checkdirectory:
                                logger.warn('%s Error trying to validate/create directory. Aborting this process at this time.' % module)
                                self.valreturn.append({"self.log": self.log,
                                                       "mode": 'stop'})
                                return self.queue.put(self.valreturn)

                            #send to renamer here if valid.
                            if mylar.CONFIG.RENAME_FILES:
                                renamed_file = helpers.rename_param(ml['ComicID'], ml['ComicName'], ml['IssueNumber'], dfilename, issueid=ml['IssueID'], arc=ml['StoryArc'])
                                if renamed_file:
                                    dfilename = renamed_file['nfilename']
                                    logger.fdebug('%s Renaming file to conform to configuration: %s' % (module, ofilename))

                            #if from a StoryArc, check to see if we're appending the ReadingOrder to the filename
                            if mylar.CONFIG.READ2FILENAME:

                                logger.fdebug('%s readingorder#: %s' % (module, ml['ReadingOrder']))
                                if int(ml['ReadingOrder']) < 10: readord = "00" + str(ml['ReadingOrder'])
                                elif int(ml['ReadingOrder']) >= 10 and int(ml['ReadingOrder']) <= 99: readord = "0" + str(ml['ReadingOrder'])
                                else: readord = str(ml['ReadingOrder'])
                                dfilename = str(readord) + "-" + os.path.split(dfilename)[1]

                            grab_dst = os.path.join(grdst, dfilename)

                            logger.fdebug('%s Destination Path : %s' % (module, grab_dst))
                            logger.fdebug('%s Source Path : %s' % (module, grab_src))

                            logger.info('%s[ONE-OFF MODE][%s] %s into directory : %s' % (module, mylar.CONFIG.ARC_FILEOPS.upper(), grab_src, grab_dst))
                            #this is also for issues that are part of a story arc, and don't belong to a watchlist series (ie. one-off's)

                            try:
                                checkspace = helpers.get_free_space(grdst)
                                if checkspace is False:
                                    if all([metaresponse is not None, metaresponse != 'fail']):  # meta was done
                                        self.tidyup(src_location, True, cacheonly=True)
                                    raise OSError
                                fileoperation = helpers.file_ops(grab_src, grab_dst, one_off=True)
                                if not fileoperation:
                                    raise OSError
                            except Exception as e:
                                logger.error('%s [ONE-OFF MODE] Failed to %s %s: %s' % (module, mylar.CONFIG.ARC_FILEOPS, grab_src, e))
                                return

                            #tidyup old path
                            if any([mylar.CONFIG.FILE_OPTS == 'move', mylar.CONFIG.FILE_OPTS == 'copy']):
                                self.tidyup(src_location, True, filename=orig_filename)

                            #delete entry from nzblog table
                            #if it was downloaded via mylar from the storyarc section, it will have an 'S' in the nzblog
                            #if it was downloaded outside of mylar and/or not from the storyarc section, it will be a normal issueid in the nzblog
                            #IssArcID = 'S' + str(ml['IssueArcID'])
                            myDB.action('DELETE from nzblog WHERE IssueID=? AND SARC=?', ['S' + str(ml['IssueArcID']),ml['StoryArc']])
                            myDB.action('DELETE from nzblog WHERE IssueID=? AND SARC=?', [ml['IssueArcID'],ml['StoryArc']])

                            logger.fdebug('%s IssueArcID: %s' % (module, ml['IssueArcID']))
                            newVal = {"Status":       "Downloaded",
                                      "Location":     grab_dst}
                        else:
                            newVal = {"Status":       "Downloaded",
                                      "Location":     ml['ComicLocation']}
                        ctrlVal = {"IssueArcID":  ml['IssueArcID']}
                        logger.fdebug('writing: %s -- %s' % (newVal, ctrlVal))
                        myDB.upsert("storyarcs", newVal, ctrlVal)
                        if all([mylar.CONFIG.STORYARCDIR is True, mylar.CONFIG.COPY2ARCDIR is True]):
                            logger.fdebug('%s [%s] Post-Processing completed for: %s' % (module, ml['StoryArc'], grab_dst))
                        else:
                            logger.fdebug('%s [%s] Post-Processing completed for: %s' % (module, ml['StoryArc'], ml['ComicLocation']))

            if (all([self.nzb_name != 'Manual Run', self.apicall is False]) or (self.oneoffinlist is True or all([self.issuearcid is not None, self.issueid is None]))) and not self.nzb_name.startswith('0-Day'): # and all([self.issueid is None, self.comicid is None, self.apicall is False]):
                ppinfo = []
                if self.oneoffinlist is False:
                    self.oneoff = False
                    if any([self.issueid is not None, self.issuearcid is not None]):
                        if self.issuearcid is not None:
                            s_id = self.issuearcid
                        else:
                            s_id = self.issueid
                        nzbiss = myDB.selectone('SELECT * FROM nzblog WHERE IssueID=?', [s_id]).fetchone()
                        if nzbiss is None and self.issuearcid is not None:
                            nzbiss = myDB.selectone('SELECT * FROM nzblog WHERE IssueID=?', ['S'+s_id]).fetchone()

                    else:
                        nzbname = self.nzb_name
                        #remove extensions from nzb_name if they somehow got through (Experimental most likely)
                        if nzbname.lower().endswith(self.extensions):
                            fd, ext = os.path.splitext(nzbname)
                            self._log("Removed extension from nzb: " + ext)
                            nzbname = re.sub(str(ext), '', str(nzbname))

                        #replace spaces
                        # let's change all space to decimals for simplicity
                        logger.fdebug('[NZBNAME]: ' + nzbname)
                        #gotta replace & or escape it
                        nzbname = re.sub("\&", 'and', nzbname)
                        nzbname = re.sub('[\,\:\?\'\+]', '', nzbname)
                        nzbname = re.sub('[\(\)]', ' ', nzbname)
                        logger.fdebug('[NZBNAME] nzbname (remove chars): ' + nzbname)
                        nzbname = re.sub('.cbr', '', nzbname).strip()
                        nzbname = re.sub('.cbz', '', nzbname).strip()
                        nzbname = re.sub('[\.\_]', ' ', nzbname).strip()
                        nzbname = re.sub('\s+', ' ', nzbname)  #make sure we remove the extra spaces.
                        logger.fdebug('[NZBNAME] nzbname (remove extensions, double spaces, convert underscores to spaces): ' + nzbname)
                        nzbname = re.sub('\s', '.', nzbname)

                        logger.fdebug('%s After conversions, nzbname is : %s' % (module, nzbname))
                        self._log("nzbname: %s" % nzbname)

                        nzbiss = myDB.selectone("SELECT * from nzblog WHERE nzbname=? or altnzbname=?", [nzbname, nzbname]).fetchone()

                        if nzbiss is None:
                            self._log("Failure - could not initially locate nzbfile in my database to rename.")
                            logger.fdebug('%s Failure - could not locate nzbfile initially' % module)
                            # if failed on spaces, change it all to decimals and try again.
                            nzbname = re.sub('[\(\)]', '', str(nzbname))
                            self._log("trying again with this nzbname: %s" % nzbname)
                            logger.fdebug('%s Trying to locate nzbfile again with nzbname of : %s' % (module, nzbname))
                            nzbiss = myDB.selectone("SELECT * from nzblog WHERE nzbname=? or altnzbname=?", [nzbname, nzbname]).fetchone()
                            if nzbiss is None:
                                logger.error('%s Unable to locate downloaded file within items I have snatched. Attempting to parse the filename directly and process.' % module)
                                #set it up to run manual post-processing on self.nzb_folder
                                self._log('Unable to locate downloaded file within items I have snatched. Attempting to parse the filename directly and process.')
                                self.valreturn.append({"self.log": self.log,
                                                       "mode": 'outside'})
                                return self.queue.put(self.valreturn)
                            else:
                                self._log("I corrected and found the nzb as : %s" % nzbname)
                                logger.fdebug('%s Auto-corrected and found the nzb as : %s' % (module, nzbname))
                                #issueid = nzbiss['IssueID']

                    issueid = nzbiss['IssueID']
                    logger.fdebug('%s Issueid: %s' % (module, issueid))
                    sarc = nzbiss['SARC']
                    self.oneoff = nzbiss['OneOff']
                    tmpiss = myDB.selectone('SELECT * FROM issues WHERE IssueID=?', [issueid]).fetchone()
                    if tmpiss is None:
                        tmpiss = myDB.selectone('SELECT * FROM annuals WHERE IssueID=?', [issueid]).fetchone()
                    comicid = None
                    comicname = None
                    issuenumber = None
                    if tmpiss is not None:
                        ppinfo.append({'comicid':       tmpiss['ComicID'],
                                       'issueid':       issueid,
                                       'comicname':     tmpiss['ComicName'],
                                       'issuenumber':   tmpiss['Issue_Number'],
                                       'comiclocation': None,
                                       'publisher':     None,
                                       'sarc':          sarc,
                                       'oneoff':        self.oneoff})

                    elif all([self.oneoff is not None, issueid[0] == 'S']):
                        issuearcid = re.sub('S', '', issueid).strip()
                        oneinfo = myDB.selectone("SELECT * FROM storyarcs WHERE IssueArcID=?", [issuearcid]).fetchone()
                        if oneinfo is None:
                            logger.warn('Unable to locate issue as previously snatched arc issue - it might be something else...')
                            self._log('Unable to locate issue as previously snatched arc issue - it might be something else...')
                        else:
                            #reverse lookup the issueid here to see if it possible exists on watchlist...
                            tmplookup = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [oneinfo['ComicID']]).fetchone()
                            if tmplookup is not None:
                                logger.fdebug('[WATCHLIST-DETECTION-%s] Processing as Arc, detected on watchlist - will PP for both.' % tmplookup['ComicName'])
                                self.oneoff = False
                            else:
                                self.oneoff = True
                            ppinfo.append({'comicid':       oneinfo['ComicID'],
                                           'comicname':     oneinfo['ComicName'],
                                           'issuenumber':   oneinfo['IssueNumber'],
                                           'publisher':     oneinfo['IssuePublisher'],
                                           'comiclocation': None,
                                           'issueid':       issueid, #need to keep it so the 'S' is present to denote arc.
                                           'sarc':          sarc,
                                           'oneoff':        self.oneoff})


                    if all([len(ppinfo) == 0, self.oneoff is not None, mylar.CONFIG.ALT_PULL == 2]):
                        oneinfo = myDB.selectone('SELECT * FROM weekly WHERE IssueID=?', [issueid]).fetchone()
                        if oneinfo is None:
                            oneinfo = myDB.selectone('SELECT * FROM oneoffhistory WHERE IssueID=?', [issueid]).fetchone()
                            if oneinfo is None:
                                logger.warn('Unable to locate issue as previously snatched one-off')
                                self._log('Unable to locate issue as previously snatched one-off')
                                self.valreturn.append({"self.log": self.log,
                                                       "mode": 'stop'})
                                return self.queue.put(self.valreturn)
                            else:
                                OComicname = oneinfo['ComicName']
                                OIssue = oneinfo['IssueNumber']
                                OPublisher = None
                        else:
                            OComicname = oneinfo['COMIC']
                            OIssue = oneinfo['ISSUE']
                            OPublisher = oneinfo['PUBLISHER']

                        ppinfo.append({'comicid':       oneinfo['ComicID'],
                                       'comicname':     OComicname,
                                       'issuenumber':   OIssue,
                                       'publisher':     OPublisher,
                                       'comiclocation': None,
                                       'issueid':       issueid,
                                       'sarc':          None,
                                       'oneoff':        True})

                        self.oneoff = True
                        #logger.info(module + ' Discovered %s # %s by %s [comicid:%s][issueid:%s]' % (comicname, issuenumber, publisher, comicid, issueid))
                    #use issueid to get publisher, series, year, issue number
                else:
                    for x in oneoff_issuelist:
                        if x['One-Off'] is True:
                            oneinfo = myDB.selectone('SELECT * FROM weekly WHERE IssueID=?', [x['IssueID']]).fetchone()
                            if oneinfo is not None:
                                ppinfo.append({'comicid':       oneinfo['ComicID'],
                                               'comicname':     oneinfo['COMIC'],
                                               'issuenumber':   oneinfo['ISSUE'],
                                               'publisher':     oneinfo['PUBLISHER'],
                                               'issueid':       x['IssueID'],
                                               'comiclocation': x['ComicLocation'],
                                               'sarc':          None,
                                               'oneoff':        x['One-Off']})
                                self.oneoff = True

                if len(ppinfo) > 0:
                    for pp in ppinfo:
                        logger.info('[PPINFO-POST-PROCESSING-ATTEMPT] %s' % pp)
                        self.nzb_or_oneoff_pp(tinfo=pp)

            if any([self.nzb_name == 'Manual Run', self.issueid is not None, self.comicid is not None, self.apicall is True]):
                #loop through the hits here.
                if len(manual_list) == 0 and len(manual_arclist) == 0:
                    if self.nzb_name == 'Manual Run':
                        logger.info('%s No matches for Manual Run ... exiting.' % module)
                    if mylar.APILOCK is True:
                        mylar.APILOCK = False
                    return
                elif len(manual_arclist) > 0 and len(manual_list) == 0:
                    logger.info('%s Manual post-processing completed for %s story-arc issues.' % (module, len(manual_arclist)))
                    if mylar.APILOCK is True:
                        mylar.APILOCK = False
                    return
                elif len(manual_arclist) > 0:
                    logger.info('%s Manual post-processing completed for %s story-arc issues.' % (module, len(manual_arclist)))

                i = 0

                for ml in manual_list:
                    i+=1
                    comicid = ml['ComicID']
                    issueid = ml['IssueID']
                    issuenumOG = ml['IssueNumber']
                    #check to see if file is still being written to.
                    waiting = True
                    while waiting is True:
                        try:
                            ctime = max(os.path.getctime(ml['ComicLocation']), os.path.getmtime(ml['ComicLocation']))
                            if time.time() > ctime > time.time() - 10:
                                time.sleep(max(time.time() - ctime, 0))
                            else:
                                break
                        except:
                            #file is no longer present in location / can't be accessed.
                            break

                    dupthis = helpers.duplicate_filecheck(ml['ComicLocation'], ComicID=comicid, IssueID=issueid)
                    if dupthis['action'] == 'dupe_src' or dupthis['action'] == 'dupe_file':
                        #check if duplicate dump folder is enabled and if so move duplicate file in there for manual intervention.
                        #'dupe_file' - do not write new file as existing file is better quality
                        #'dupe_src' - write new file, as existing file is a lesser quality (dupe)
                        if mylar.CONFIG.DDUMP and not all([mylar.CONFIG.DUPLICATE_DUMP is None, mylar.CONFIG.DUPLICATE_DUMP == '']): #DUPLICATE_DUMP
                            dupchkit = self.duplicate_process(dupthis)
                            if dupchkit == False:
                                logger.warn('Unable to move duplicate file - skipping post-processing of this file.')
                                continue

                    if any([dupthis['action'] == "write", dupthis['action'] == 'dupe_src']):
                        stat = ' [%s/%s]' % (i, len(manual_list))
                        self.Process_next(comicid, issueid, issuenumOG, ml, stat)
                        dupthis = None

                if self.failed_files == 0:
                    if all([self.comicid is not None, self.issueid is None]):
                        logger.info('%s post-processing of pack completed for %s issues.' % (module, i))
                    if self.issueid is not None:
                        if ml['AnnualType'] is not None:
                            logger.info('%s direct post-processing of issue completed for %s %s #%s.' % (module, ml['ComicName'], ml['AnnualType'], ml['IssueNumber']))
                        else:
                            logger.info('%s direct post-processing of issue completed for %s #%s.' % (module, ml['ComicName'], ml['IssueNumber']))
                    else:
                        logger.info('%s Manual post-processing completed for %s issues.' % (module, i))
                else:
                    if self.comicid is not None:
                        logger.info('%s post-processing of pack completed for %s issues [FAILED: %s]' % (module, i, self.failed_files))
                    else:
                        logger.info('%s Manual post-processing completed for %s issues [FAILED: %s]' % (module, i, self.failed_files))
                if mylar.APILOCK is True:
                    mylar.APILOCK = False
                return
            else:
                pass

    def nzb_or_oneoff_pp(self, tinfo=None, manual=None):
        module = self.module
        myDB = db.DBConnection()
        manual_list = None
        if tinfo is not None: #manual is None:
            sandwich = None
            issueid = tinfo['issueid']
            comicid = tinfo['comicid']
            comicname = tinfo['comicname']
            issuearcid = None
            issuenumber = tinfo['issuenumber']
            publisher = tinfo['publisher']
            sarc = tinfo['sarc']
            oneoff = tinfo['oneoff']
            if all([oneoff is True, tinfo['comiclocation'] is not None]):
                location = os.path.abspath(os.path.join(tinfo['comiclocation'], os.pardir))
            else:
                location = self.nzb_folder
            annchk = "no"
            issuenzb = myDB.selectone("SELECT * from issues WHERE IssueID=? AND ComicName NOT NULL", [issueid]).fetchone()
            if issuenzb is None:
                logger.info('%s Could not detect as a standard issue - checking against annuals.' % module)
                issuenzb = myDB.selectone("SELECT * from annuals WHERE IssueID=? AND ComicName NOT NULL", [issueid]).fetchone()
                if issuenzb is None:
                    logger.info('%s issuenzb not found.' % module)
                    #if it's non-numeric, it contains a 'G' at the beginning indicating it's a multi-volume
                    #using GCD data. Set sandwich to 1 so it will bypass and continue post-processing.
                    if 'S' in issueid:
                        sandwich = issueid
                        if oneoff is False:
                            onechk = myDB.selectone('SELECT * FROM storyarcs WHERE IssueArcID=?', [re.sub('S','', issueid).strip()]).fetchone()
                            if onechk is not None:
                                issuearcid = onechk['IssueArcID']
                                issuenzb = myDB.selectone('SELECT * FROM issues WHERE IssueID=? AND ComicName NOT NULL', [onechk['IssueID']]).fetchone()
                                if issuenzb is None:
                                    issuenzb = myDB.selectone("SELECT * from annuals WHERE IssueID=? AND ComicName NOT NULL", [onechk['IssueID']]).fetchone()
                            if issuenzb is not None:
                                issueid = issuenzb['IssueID']
                                logger.fdebug('Reverse lookup discovered watchlisted series [issueid: %s] - adjusting so we can PP both properly.' % issueid)
                    elif 'G' in issueid or '-' in issueid:
                        sandwich = 1
                    elif any([oneoff is True, issueid >= '900000', issueid == '1']):
                        logger.info('%s [ONE-OFF POST-PROCESSING] One-off download detected. Post-processing as a non-watchlist item.' % module)
                        sandwich = None #arbitrarily set it to None just to force one-off downloading below.
                    else:
                        logger.error('%s Unable to locate downloaded file as being initiated via Mylar. Attempting to parse the filename directly and process.' % module)
                        self._log('Unable to locate downloaded file within items I have snatched. Attempting to parse the filename directly and process.')
                        self.valreturn.append({"self.log": self.log,
                                               "mode": 'outside'})
                        return self.queue.put(self.valreturn)
                else:
                    logger.info('%s Successfully located issue as an annual. Continuing.' % module)
                    annchk = "yes"

            if issuenzb is not None:
                logger.info('%s issuenzb found.' % module)
                if helpers.is_number(issueid):
                    sandwich = int(issuenzb['IssueID'])
            if all([sandwich is not None, helpers.is_number(sandwich), sarc is None]):
                if sandwich < 900000:
                    # if sandwich is less than 900000 it's a normal watchlist download. Bypass.
                    pass
            else:
                if any([oneoff is True, issuenzb is None]) or all([sandwich is not None, 'S' in str(sandwich), oneoff is True]) or int(sandwich) >= 900000:
                    # this has no issueID, therefore it's a one-off or a manual post-proc.
                    # At this point, let's just drop it into the Comic Location folder and forget about it..
                    if sandwich is not None and 'S' in sandwich:
                        self._log("One-off STORYARC mode enabled for Post-Processing for %s" % sarc)
                        logger.info('%s One-off STORYARC mode enabled for Post-Processing for %s' % (module, sarc))
                    else:
                        self._log("One-off mode enabled for Post-Processing. All I'm doing is moving the file untouched into the Grab-bag directory.")
                        if mylar.CONFIG.GRABBAG_DIR is None:
                            mylar.CONFIG.GRABBAG_DIR = os.path.join(mylar.CONFIG.DESTINATION_DIR, 'Grabbag')
                        logger.info('%s One-off mode enabled for Post-Processing. Will move into Grab-bag directory: %s' % (module, mylar.CONFIG.GRABBAG_DIR))
                        self._log("Grab-Bag Directory set to : %s" % mylar.CONFIG.GRABBAG_DIR)
                        grdst = mylar.CONFIG.GRABBAG_DIR

                    odir = location

                    if odir is None:
                        odir = self.nzb_folder

                    ofilename = orig_filename = tinfo['comiclocation']

                    if ofilename is not None:
                        path, ext = os.path.splitext(ofilename)
                    else:
                        #os.walk the location to get the filename...(coming from sab kinda thing) where it just passes the path.
                        for root, dirnames, filenames in os.walk(odir, followlinks=True):
                            for filename in filenames:
                                if filename.lower().endswith(self.extensions):
                                    ofilename = orig_filename = filename
                                    logger.fdebug('%s Valid filename located as : %s' % (module, ofilename))
                                    path, ext = os.path.splitext(ofilename)
                                    break

                    if ofilename is None:
                        logger.error('%s Unable to post-process file as it is not in a valid cbr/cbz format or cannot be located in path. PostProcessing aborted.' % module)
                        self._log('Unable to locate downloaded file to rename. PostProcessing aborted.')
                        self.valreturn.append({"self.log": self.log,
                                               "mode": 'stop'})
                        return self.queue.put(self.valreturn)

                    if sandwich is not None and 'S' in sandwich:
                        issuearcid = re.sub('S', '', issueid)
                        logger.fdebug('%s issuearcid:%s' % (module, issuearcid))
                        arcdata = myDB.selectone("SELECT * FROM storyarcs WHERE IssueArcID=?", [issuearcid]).fetchone()
                        if arcdata is None:
                            logger.warn('%s Unable to locate issue within Story Arcs. Cannot post-process at this time - try to Refresh the Arc and manual post-process if necessary.' % module)
                            self._log('Unable to locate issue within Story Arcs in orde to properly assign metadata. PostProcessing aborted.')
                            self.valreturn.append({"self.log": self.log,
                                                   "mode": 'stop'})
                            return self.queue.put(self.valreturn)

                        if arcdata['Publisher'] is None:
                            arcpub = arcdata['IssuePublisher']
                        else:
                            arcpub = arcdata['Publisher']

                        grdst = helpers.arcformat(arcdata['StoryArc'], helpers.spantheyears(arcdata['StoryArcID']), arcpub)

                        if comicid is None:
                            comicid = arcdata['ComicID']
                        if comicname is None:
                            comicname = arcdata['ComicName']
                        if issuenumber is None:
                            issuenumber = arcdata['IssueNumber']
                        issueid = arcdata['IssueID']

                    #tag the meta.
                    metaresponse = None
                    crcvalue = helpers.crc(os.path.join(location, ofilename))

                    #if a one-off download from the pull-list, will not have an issueid associated with it, and will fail to due conversion/tagging.
                    #if altpull/2 method is being used, issueid may already be present so conversion/tagging is possible with some additional fixes.
                    if all([mylar.CONFIG.ENABLE_META, issueid is not None]):
                        self._log("Metatagging enabled - proceeding...")
                        try:
                            import cmtagmylar
                            metaresponse = cmtagmylar.run(location, issueid=issueid, filename=os.path.join(self.nzb_folder, ofilename))
                        except ImportError:
                            logger.warn('%s comictaggerlib not found on system. Ensure the ENTIRE lib directory is located within mylar/lib/comictaggerlib/' % module)
                            metaresponse = "fail"

                        if metaresponse == "fail":
                            logger.fdebug('%s Unable to write metadata successfully - check mylar.log file. Attempting to continue without metatagging...' % module)
                        elif any([metaresponse == "unrar error", metaresponse == "corrupt"]):
                            logger.error('%s This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and retrying it.' %module)
                            #launch failed download handling here.
                        elif metaresponse.startswith('file not found'):
                            filename_in_error = metaresponse.split('||')[1]
                            self._log("The file cannot be found in the location provided for metatagging [%s]. Please verify it exists, and re-run if necessary." % filename_in_error)
                            logger.error('%s The file cannot be found in the location provided for metagging [%s]. Please verify it exists, and re-run if necessary.' % (module, filename_in_error))
                        else:
                            odir = os.path.split(metaresponse)[0]
                            ofilename = os.path.split(metaresponse)[1]
                            ext = os.path.splitext(metaresponse)[1]
                            logger.info('%s Sucessfully wrote metadata to .cbz (%s) - Continuing..' % (module, ofilename))
                            self._log('Sucessfully wrote metadata to .cbz (%s) - proceeding...' % ofilename)

                    dfilename = ofilename
                    if metaresponse:
                        src_location = odir
                    else:
                        src_location = location

                    grab_src = os.path.join(src_location, ofilename)
                    self._log("Source Path : %s" % grab_src)
                    logger.info('%s Source Path : %s' % (module, grab_src))

                    checkdirectory = filechecker.validateAndCreateDirectory(grdst, True, module=module)
                    if not checkdirectory:
                        logger.warn('%s Error trying to validate/create directory. Aborting this process at this time.' % module)
                        self.valreturn.append({"self.log": self.log,
                                               "mode": 'stop'})
                        return self.queue.put(self.valreturn)

                    #send to renamer here if valid.
                    if mylar.CONFIG.RENAME_FILES:
                        renamed_file = helpers.rename_param(comicid, comicname, issuenumber, dfilename, issueid=issueid, arc=sarc)
                        if renamed_file:
                            dfilename = renamed_file['nfilename']
                            logger.fdebug('%s Renaming file to conform to configuration: %s' % (module, dfilename))

                    if sandwich is not None and 'S' in sandwich:
                        #if from a StoryArc, check to see if we're appending the ReadingOrder to the filename
                        if mylar.CONFIG.READ2FILENAME:
                            logger.fdebug('%s readingorder#: %s' % (module, arcdata['ReadingOrder']))
                            if int(arcdata['ReadingOrder']) < 10: readord = "00" + str(arcdata['ReadingOrder'])
                            elif int(arcdata['ReadingOrder']) >= 10 and int(arcdata['ReadingOrder']) <= 99: readord = "0" + str(arcdata['ReadingOrder'])
                            else: readord = str(arcdata['ReadingOrder'])
                            dfilename = str(readord) + "-" + dfilename
                        else:
                            dfilename = ofilename
                        grab_dst = os.path.join(grdst, dfilename)
                    else:
                        grab_dst = os.path.join(grdst, dfilename)

                    if not os.path.exists(grab_dst) or grab_src == grab_dst:
                        #if it hits this, ofilename is the full path so we need to extract just the filename to path it back to a possible grab_bag dir
                        grab_dst = os.path.join(grdst, os.path.split(dfilename)[1])

                    self._log("Destination Path : %s" % grab_dst)

                    logger.info('%s Destination Path : %s' % (module, grab_dst))
                    logger.info('%s[%s] %s into directory : %s' % (module, mylar.CONFIG.FILE_OPTS, ofilename, grab_dst))

                    try:
                        checkspace = helpers.get_free_space(grdst)
                        if checkspace is False:
                            if all([metaresponse != 'fail', metaresponse is not None]):  # meta was done
                                self.tidyup(src_location, True, cacheonly=True)
                            raise OSError
                        fileoperation = helpers.file_ops(grab_src, grab_dst)
                        if not fileoperation:
                            raise OSError
                    except Exception as e:
                        logger.error('%s Failed to %s %s: %s' % (module, mylar.CONFIG.FILE_OPTS, grab_src, e))
                        self._log("Failed to %s %s: %s" % (mylar.CONFIG.FILE_OPTS, grab_src, e))
                        return

                    #tidyup old path
                    if any([mylar.CONFIG.FILE_OPTS == 'move', mylar.CONFIG.FILE_OPTS == 'copy']):
                        self.tidyup(src_location, True, filename=orig_filename)

                    #delete entry from nzblog table
                    myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])

                    if sandwich is not None and 'S' in sandwich:
                        logger.info('%s IssueArcID is : %s' % (module, issuearcid))
                        ctrlVal = {"IssueArcID":  issuearcid}
                        newVal = {"Status":       "Downloaded",
                                  "Location":     grab_dst}
                        myDB.upsert("storyarcs", newVal, ctrlVal)
                        logger.info('%s Updated status to Downloaded' % module)

                        logger.info('%s Post-Processing completed for: [%s] %s' % (module, sarc, grab_dst))
                        self._log(u"Post Processing SUCCESSFUL! ")
                    elif oneoff is True:
                        logger.info('%s IssueID is : %s' % (module, issueid))
                        ctrlVal = {"IssueID":  issueid}
                        newVal = {"Status":       "Downloaded"}
                        logger.info('%s Writing to db: %s -- %s' % (module, newVal, ctrlVal))
                        myDB.upsert("weekly", newVal, ctrlVal)
                        logger.info('%s Updated status to Downloaded' % module)
                        myDB.upsert("oneoffhistory", newVal, ctrlVal)
                        logger.info('%s Updated history for one-off\'s for tracking purposes' % module)
                        logger.info('%s Post-Processing completed for: [ %s #%s ] %s' % (module, comicname, issuenumber, grab_dst))
                        self._log(u"Post Processing SUCCESSFUL! ")

                    try:
                        self.sendnotify(comicname, issueyear=None, issuenumOG=issuenumber, annchk=annchk, module=module)
                    except:
                        pass

                    self.valreturn.append({"self.log": self.log,
                                               "mode": 'stop'})

                    return self.queue.put(self.valreturn)

                else:
                    try:
                        len(manual_arclist)
                    except:
                        manual_arclist = []

                    if tinfo['comiclocation'] is None:
                        cloc = self.nzb_folder
                    else:
                        cloc = tinfo['comiclocation']

                    clocation = cloc
                    if os.path.isdir(cloc):
                        for root, dirnames, filenames in os.walk(cloc, followlinks=True):
                            for filename in filenames:
                                if filename.lower().endswith(self.extensions):
                                    clocation = os.path.join(root, filename)

                    manual_list = {'ComicID':       tinfo['comicid'],
                                   'IssueID':       tinfo['issueid'],
                                   'ComicLocation': clocation,
                                   'SARC':          tinfo['sarc'],
                                   'IssueArcID':    issuearcid,
                                   'ComicName':     tinfo['comicname'],
                                   'IssueNumber':   tinfo['issuenumber'],
                                   'Publisher':     tinfo['publisher'],
                                   'OneOff':        tinfo['oneoff'],
                                   'ForcedMatch':   False}


        else:
            manual_list = manual

        if self.nzb_name == 'Manual Run':
            #loop through the hits here.
            if len(manual_list) == 0 and len(manual_arclist) == 0:
                logger.info('%s No matches for Manual Run ... exiting.' % module)
                return
            elif len(manual_arclist) > 0 and len(manual_list) == 0:
                logger.info('%s Manual post-processing completed for %s story-arc issues.' % (module, len(manual_arclist)))
                return
            elif len(manual_arclist) > 0:
                logger.info('%s Manual post-processing completed for %s story-arc issues.' % (module, len(manual_arclist)))
            i = 0

            for ml in manual_list:
                i+=1
                comicid = ml['ComicID']
                issueid = ml['IssueID']
                issuenumOG = ml['IssueNumber']
                #check to see if file is still being written to.
                while True:
                    waiting = False
                    try:
                        ctime = max(os.path.getctime(ml['ComicLocation']), os.path.getmtime(ml['ComicLocation']))
                        if time.time() > ctime > time.time() - 10:
                            time.sleep(max(time.time() - ctime, 0))
                            waiting = True
                        else:
                            break
                    except:
                        #file is no longer present in location / can't be accessed.
                        break

                dupthis = helpers.duplicate_filecheck(ml['ComicLocation'], ComicID=comicid, IssueID=issueid)
                if dupthis['action'] == 'dupe_src' or dupthis['action'] == 'dupe_file':
                    #check if duplicate dump folder is enabled and if so move duplicate file in there for manual intervention.
                    #'dupe_file' - do not write new file as existing file is better quality
                    #check if duplicate dump folder is enabled and if so move duplicate file in there for manual intervention.
                    #'dupe_file' - do not write new file as existing file is better quality
                    #'dupe_src' - write new file, as existing file is a lesser quality (dupe)
                    if mylar.CONFIG.DDUMP and not all([mylar.CONFIG.DUPLICATE_DUMP is None, mylar.CONFIG.DUPLICATE_DUMP == '']): #DUPLICATE_DUMP
                        dupchkit = self.duplicate_process(dupthis)
                        if dupchkit == False:
                            logger.warn('Unable to move duplicate file - skipping post-processing of this file.')
                            continue

                if any([dupthis['action'] == "write", dupthis['action'] == 'dupe_src']):
                    stat = ' [%s/%s]' % (i, len(manual_list))
                    self.Process_next(comicid, issueid, issuenumOG, ml, stat)
                    dupthis = None

            if self.failed_files == 0:
                logger.info('%s Manual post-processing completed for %s issues.' % (module, i))
            else:
                logger.info('%s Manual post-processing completed for %s issues [FAILED: %s]' % (module, i, self.failed_files))
            return

        else:
            comicid = issuenzb['ComicID']
            issuenumOG = issuenzb['Issue_Number']
            #the self.nzb_folder should contain only the existing filename
            dupthis = helpers.duplicate_filecheck(self.nzb_folder, ComicID=comicid, IssueID=issueid)
            if dupthis['action'] == 'dupe_src' or dupthis['action'] == 'dupe_file':
                #check if duplicate dump folder is enabled and if so move duplicate file in there for manual intervention.
                #'dupe_file' - do not write new file as existing file is better quality
                #'dupe_src' - write new file, as existing file is a lesser quality (dupe)
                if mylar.CONFIG.DUPLICATE_DUMP:
                    if mylar.CONFIG.DDUMP and not all([mylar.CONFIG.DUPLICATE_DUMP is None, mylar.CONFIG.DUPLICATE_DUMP == '']):
                        dupchkit = self.duplicate_process(dupthis)
                        if dupchkit == False:
                            logger.warn('Unable to move duplicate file - skipping post-processing of this file.')
                            self.valreturn.append({"self.log": self.log,
                                                   "mode": 'stop',
                                                   "issueid": issueid,
                                                   "comicid": comicid})
                            return self.queue.put(self.valreturn)

            if dupthis['action'] == "write" or dupthis['action'] == 'dupe_src':
                if manual_list is None:
                    return self.Process_next(comicid, issueid, issuenumOG)
                else:
                    logger.info('Post-processing issue is found in more than one destination - let us do this!')
                    return self.Process_next(comicid, issueid, issuenumOG, manual_list)
            else:
                self.valreturn.append({"self.log": self.log,
                                       "mode": 'stop',
                                       "issueid": issueid,
                                       "comicid": comicid})
                return self.queue.put(self.valreturn)


    def Process_next(self, comicid, issueid, issuenumOG, ml=None, stat=None):
            if stat is None: stat = ' [1/1]'
            module = self.module
            annchk = "no"
            snatchedtorrent = False
            myDB = db.DBConnection()
            comicnzb = myDB.selectone("SELECT * from comics WHERE comicid=?", [comicid]).fetchone()
            issuenzb = myDB.selectone("SELECT * from issues WHERE issueid=? AND comicid=? AND ComicName NOT NULL", [issueid, comicid]).fetchone()
            if ml is not None and mylar.CONFIG.SNATCHEDTORRENT_NOTIFY:
                snatchnzb = myDB.selectone("SELECT * from snatched WHERE IssueID=? AND ComicID=? AND (provider=? OR provider=? OR provider=? OR provider=?) AND Status='Snatched'", [issueid, comicid, 'TPSE', 'DEM', 'WWT', '32P']).fetchone()
                if snatchnzb is None:
                    logger.fdebug('%s Was not snatched as a torrent. Using manual post-processing.' % module) 
                else:
                    logger.fdebug('%s Was downloaded from %s. Enabling torrent manual post-processing completion notification.' % (module, snatchnzb['Provider']))
            if issuenzb is None:
                issuenzb = myDB.selectone("SELECT * from annuals WHERE issueid=? and comicid=?", [issueid, comicid]).fetchone()
                annchk = "yes"
            if annchk == "no":
                logger.info('%s %s Starting Post-Processing for %s issue: %s' % (module, stat, issuenzb['ComicName'], issuenzb['Issue_Number']))
            else:
                logger.info('%s %s Starting Post-Processing for %s issue: %s' % (module, stat, issuenzb['ReleaseComicName'], issuenzb['Issue_Number']))
            logger.fdebug('%s issueid: %s' % (module, issueid))
            logger.fdebug('%s issuenumOG: %s' % (module, issuenumOG))
            #issueno = str(issuenum).split('.')[0]
            #new CV API - removed all decimals...here we go AGAIN!
            issuenum = issuenzb['Issue_Number']
            issue_except = 'None'

            if 'au' in issuenum.lower() and issuenum[:1].isdigit():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = ' AU'
            elif 'ai' in issuenum.lower() and issuenum[:1].isdigit():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = ' AI'
            elif 'inh' in issuenum.lower() and issuenum[:1].isdigit():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = '.INH'
            elif 'now' in issuenum.lower() and issuenum[:1].isdigit():
                if '!' in issuenum: issuenum = re.sub('\!', '', issuenum)
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = '.NOW'
            elif 'mu' in issuenum.lower() and issuenum[:1].isdigit():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = '.MU'
            elif 'hu' in issuenum.lower() and issuenum[:1].isdigit():
                issuenum = re.sub("[^0-9]", "", issuenum)
                issue_except = '.HU'
            elif u'\xbd' in issuenum:
                issuenum = '0.5'
            elif u'\xbc' in issuenum:
                issuenum = '0.25'
            elif u'\xbe' in issuenum:
                issuenum = '0.75'
            elif u'\u221e' in issuenum:
                #issnum = utf-8 will encode the infinity symbol without any help
                issuenum = 'infinity'
            else:
                issue_exceptions = ['A',
                                    'B',
                                    'C',
                                    'X',
                                    'O']

                exceptionmatch = [x for x in issue_exceptions if x.lower() in issuenum.lower()]
                if exceptionmatch:
                    logger.fdebug('[FILECHECKER] We matched on : ' + str(exceptionmatch))
                    for x in exceptionmatch:
                        issuenum = re.sub("[^0-9]", "", issuenum)
                        issue_except = x

            if '.' in issuenum:
                iss_find = issuenum.find('.')
                iss_b4dec = issuenum[:iss_find]
                if iss_b4dec == '':
                    iss_b4dec = '0'
                iss_decval = issuenum[iss_find +1:]
                if iss_decval.endswith('.'): iss_decval = iss_decval[:-1]
                if int(iss_decval) == 0:
                    iss = iss_b4dec
                    issdec = int(iss_decval)
                    issueno = str(iss)
                    self._log("Issue Number: %s" % issueno)
                    logger.fdebug('%s Issue Number: %s' % (module, issueno))
                else:
                    if len(iss_decval) == 1:
                        iss = iss_b4dec + "." + iss_decval
                        issdec = int(iss_decval) * 10
                    else:
                        iss = iss_b4dec + "." + iss_decval.rstrip('0')
                        issdec = int(iss_decval.rstrip('0')) * 10
                    issueno = iss_b4dec
                    self._log("Issue Number: %s" % iss)
                    logger.fdebug('%s Issue Number: %s' % (module, iss))
            else:
                iss = issuenum
                issueno = iss

            # issue zero-suppression here
            if mylar.CONFIG.ZERO_LEVEL == "0":
                zeroadd = ""
            else:
                if mylar.CONFIG.ZERO_LEVEL_N  == "none": zeroadd = ""
                elif mylar.CONFIG.ZERO_LEVEL_N == "0x": zeroadd = "0"
                elif mylar.CONFIG.ZERO_LEVEL_N == "00x": zeroadd = "00"

            logger.fdebug('%s Zero Suppression set to : %s' % (module, mylar.CONFIG.ZERO_LEVEL_N))

            prettycomiss = None

            if issueno.isalpha():
                logger.fdebug('issue detected as an alpha.')
                prettycomiss = str(issueno)
            else:
                try:
                    x = float(issueno)
                    #validity check
                    if x < 0:
                        logger.info('%s I\'ve encountered a negative issue #: %s. Trying to accomodate' % (module, issueno))
                        prettycomiss = '-%s%s' % (zeroadd, issueno[1:])
                    elif x >= 0:
                        pass
                    else:
                        raise ValueError
                except ValueError, e:
                    logger.warn('Unable to properly determine issue number [%s] - you should probably log this on github for help.' % issueno)
                    return

            if prettycomiss is None and len(str(issueno)) > 0:
                #if int(issueno) < 0:
                #    self._log("issue detected is a negative")
                #    prettycomiss = '-' + str(zeroadd) + str(abs(issueno))
                if int(issueno) < 10:
                    logger.fdebug('issue detected less than 10')
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                            prettycomiss = str(zeroadd) + str(iss)
                        else:
                            prettycomiss = str(zeroadd) + str(int(issueno))
                    else:
                        prettycomiss = str(zeroadd) + str(iss)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('%s Zero level supplement set to %s. Issue will be set as : %s' % (module, mylar.CONFIG.ZERO_LEVEL_N, prettycomiss))
                elif int(issueno) >= 10 and int(issueno) < 100:
                    logger.fdebug('issue detected greater than 10, but less than 100')
                    if mylar.CONFIG.ZERO_LEVEL_N == "none":
                        zeroadd = ""
                    else:
                        zeroadd = "0"
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                            prettycomiss = str(zeroadd) + str(iss)
                        else:
                           prettycomiss = str(zeroadd) + str(int(issueno))
                    else:
                        prettycomiss = str(zeroadd) + str(iss)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('%s Zero level supplement set to %s. Issue will be set as : %s' % (module, mylar.CONFIG.ZERO_LEVEL_N, prettycomiss))
                else:
                    logger.fdebug('issue detected greater than 100')
                    if '.' in iss:
                        if int(iss_decval) > 0:
                            issueno = str(iss)
                    prettycomiss = str(issueno)
                    if issue_except != 'None':
                        prettycomiss = str(prettycomiss) + issue_except
                    logger.fdebug('%s Zero level supplement set to %s. Issue will be set as : %s' % (module, mylar.CONFIG.ZERO_LEVEL_N, prettycomiss))

            elif len(str(issueno)) == 0:
                prettycomiss = str(issueno)
                logger.fdebug('issue length error - cannot determine length. Defaulting to None: %s ' % prettycomiss)

            if annchk == "yes":
                self._log("Annual detected.")
            logger.fdebug('%s Pretty Comic Issue is : %s' % (module, prettycomiss))
            issueyear = issuenzb['IssueDate'][:4]
            self._log("Issue Year: %s" % issueyear)
            logger.fdebug('%s Issue Year : %s' % (module, issueyear))
            month = issuenzb['IssueDate'][5:7].replace('-', '').strip()
            month_name = helpers.fullmonth(month)
            if month_name is None:
                month_name = 'None'
            publisher = comicnzb['ComicPublisher']
            self._log("Publisher: %s" % publisher)
            logger.fdebug('%s Publisher: %s' % (module, publisher))
            #we need to un-unicode this to make sure we can write the filenames properly for spec.chars
            series = comicnzb['ComicName'].encode('ascii', 'ignore').strip()
            self._log("Series: %s" % series)
            logger.fdebug('%s Series: %s' % (module, series))
            if comicnzb['AlternateFileName'] is None or comicnzb['AlternateFileName'] == 'None':
                seriesfilename = series
            else:
                seriesfilename = comicnzb['AlternateFileName'].encode('ascii', 'ignore').strip()
                logger.fdebug('%s Alternate File Naming has been enabled for this series. Will rename series to : %s' % (module, seriesfilename))
            seriesyear = comicnzb['ComicYear']
            self._log("Year: %s" % seriesyear)
            logger.fdebug('%s Year: %s' % (module, seriesyear))
            comlocation = comicnzb['ComicLocation']
            self._log("Comic Location: %s" % comlocation)
            logger.fdebug('%s Comic Location: %s' % (module, comlocation))
            comversion = comicnzb['ComicVersion']
            self._log("Comic Version: %s" % comversion)
            logger.fdebug('%s Comic Version: %s' % (module, comversion))
            if comversion is None:
                comversion = 'None'
            #if comversion is None, remove it so it doesn't populate with 'None'
            if comversion == 'None':
                chunk_f_f = re.sub('\$VolumeN', '', mylar.CONFIG.FILE_FORMAT)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                self._log("No version # found for series - tag will not be available for renaming.")
                logger.fdebug('%s No version # found for series, removing from filename' % module)
                logger.fdebug('%s New format is now: %s' % (module, chunk_file_format))
            else:
                chunk_file_format = mylar.CONFIG.FILE_FORMAT

            if annchk == "no":
                chunk_f_f = re.sub('\$Annual', '', chunk_file_format)
                chunk_f = re.compile(r'\s+')
                chunk_file_format = chunk_f.sub(' ', chunk_f_f)
                logger.fdebug('%s Not an annual - removing from filename parameters' % module)
                logger.fdebug('%s New format: %s' % (module, chunk_file_format))

            else:
                logger.fdebug('%s Chunk_file_format is: %s' % (module, chunk_file_format))
                if '$Annual' not in chunk_file_format:
                #if it's an annual, but $Annual isn't specified in file_format, we need to
                #force it in there, by default in the format of $Annual $Issue
                    prettycomiss = "Annual %s" % prettycomiss
                    logger.fdebug('%s prettycomiss: %s' % (module, prettycomiss))


            ofilename = None

            #if it's a Manual Run, use the ml['ComicLocation'] for the exact filename.
            if ml is None:
                importissue = False
                for root, dirnames, filenames in os.walk(self.nzb_folder, followlinks=True):
                    for filename in filenames:
                        if filename.lower().endswith(self.extensions):
                            odir = root
                            logger.fdebug('%s odir (root): %s' % (module, odir))
                            ofilename = filename
                            logger.fdebug('%s ofilename: %s' % (module, ofilename))
                            path, ext = os.path.splitext(ofilename)
                try:
                    if odir is None:
                        logger.fdebug('%s No root folder set.' % module)
                        odir = self.nzb_folder
                except:
                    logger.error('%s unable to set root folder. Forcing it due to some error above most likely.' % module)
                    if os.path.isfile(self.nzb_folder) and self.nzb_folder.lower().endswith(self.extensions):
                        import ntpath
                        odir, ofilename = ntpath.split(self.nzb_folder)
                        path, ext = os.path.splitext(ofilename)
                        importissue = True
                    else:
                        odir = self.nzb_folder

                if ofilename is None:
                    self._log("Unable to locate a valid cbr/cbz file. Aborting post-processing for this filename.")
                    logger.error('%s unable to locate a valid cbr/cbz file. Aborting post-processing for this filename.' % module)
                    self.failed_files +=1
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)
                logger.fdebug('%s odir: %s' % (module, odir))
                logger.fdebug('%s ofilename: %s' % (module, ofilename))


            #if meta-tagging is not enabled, we need to declare the check as being fail
            #if meta-tagging is enabled, it gets changed just below to a default of pass
            pcheck = "fail"

            #make sure we know any sub-folder off of self.nzb_folder that is being used so when we do
            #tidy-up we can remove the empty directory too. odir is the original COMPLETE path at this point
            if ml is None:
                subpath = odir
                orig_filename = ofilename
                crcvalue = helpers.crc(os.path.join(odir, ofilename))
            else:
                subpath, orig_filename = os.path.split(ml['ComicLocation'])
                crcvalue = helpers.crc(ml['ComicLocation'])

            #tag the meta.
            if mylar.CONFIG.ENABLE_META:

                self._log("Metatagging enabled - proceeding...")
                logger.fdebug('%s Metatagging enabled - proceeding...' % module)
                pcheck = "pass"
                if mylar.CONFIG.CMTAG_START_YEAR_AS_VOLUME:
                    vol_label = seriesyear
                else:
                    vol_label = comversion

                try:
                    import cmtagmylar
                    if ml is None:
                        pcheck = cmtagmylar.run(self.nzb_folder, issueid=issueid, comversion=vol_label, filename=os.path.join(odir, ofilename))
                    else:
                        pcheck = cmtagmylar.run(self.nzb_folder, issueid=issueid, comversion=vol_label, manual="yes", filename=ml['ComicLocation'])

                except ImportError:
                    logger.fdebug('%s comictaggerlib not found on system. Ensure the ENTIRE lib directory is located within mylar/lib/comictaggerlib/' % module)
                    logger.fdebug('%s continuing with PostProcessing, but I am not using metadata.' % module)
                    pcheck = "fail"

                if pcheck == "fail":
                    self._log("Unable to write metadata successfully - check mylar.log file. Attempting to continue without tagging...")
                    logger.fdebug('%s Unable to write metadata successfully - check mylar.log file. Attempting to continue without tagging...' %module)
                    self.failed_files +=1
                    #we need to set this to the cbz file since not doing it will result in nothing getting moved.
                    #not sure how to do this atm
                elif any([pcheck == "unrar error", pcheck == "corrupt"]):
                    if ml is not None:
                        self._log("This is a corrupt archive - whether CRC errors or it's incomplete. Marking as BAD, and not post-processing.")
                        logger.error('%s This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and not post-processing.' % module)
                        self.failed_files +=1
                        self.valreturn.append({"self.log": self.log,
                                               "mode": 'stop'})
                    else:
                        self._log("This is a corrupt archive - whether CRC errors or it's incomplete. Marking as BAD, and retrying a different copy.")
                        logger.error('%s This is a corrupt archive - whether CRC errors or it is incomplete. Marking as BAD, and retrying a different copy.' % module)
                        self.valreturn.append({"self.log":    self.log,
                                               "mode":        'fail',
                                               "issueid":     issueid,
                                               "comicid":     comicid,
                                               "comicname":   comicnzb['ComicName'],
                                               "issuenumber": issuenzb['Issue_Number'],
                                               "annchk":      annchk})
                    return self.queue.put(self.valreturn)
                elif pcheck.startswith('file not found'):
                    filename_in_error = pcheck.split('||')[1]
                    self._log("The file cannot be found in the location provided [%s]. Please verify it exists, and re-run if necessary. Aborting." % filename_in_error)
                    logger.error('%s The file cannot be found in the location provided [%s]. Please verify it exists, and re-run if necessary. Aborting' % (module, filename_in_error))
                    self.failed_files +=1
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)

                else:
                    #need to set the filename source as the new name of the file returned from comictagger.
                    odir = os.path.split(pcheck)[0]
                    ofilename = os.path.split(pcheck)[1]
                    ext = os.path.splitext(ofilename)[1]
                    self._log("Sucessfully wrote metadata to .cbz - Continuing..")
                    logger.info('%s Sucessfully wrote metadata to .cbz (%s) - Continuing..' % (module, ofilename))
            #Run Pre-script

            if mylar.CONFIG.ENABLE_PRE_SCRIPTS:
                nzbn = self.nzb_name #original nzb name
                nzbf = self.nzb_folder #original nzb folder
                #name, comicyear, comicid , issueid, issueyear, issue, publisher
                #create the dic and send it.
                seriesmeta = []
                seriesmetadata = {}
                seriesmeta.append({
                            'name':                 series,
                            'comicyear':            seriesyear,
                            'comicid':              comicid,
                            'issueid':              issueid,
                            'issueyear':            issueyear,
                            'issue':                issuenum,
                            'publisher':            publisher
                            })
                seriesmetadata['seriesmeta'] = seriesmeta
                self._run_pre_scripts(nzbn, nzbf, seriesmetadata)

            file_values = {'$Series':    seriesfilename,
                           '$Issue':     prettycomiss,
                           '$Year':      issueyear,
                           '$series':    series.lower(),
                           '$Publisher': publisher,
                           '$publisher': publisher.lower(),
                           '$VolumeY':   'V' + str(seriesyear),
                           '$VolumeN':   comversion,
                           '$monthname': month_name,
                           '$month':     month,
                           '$Annual':    'Annual'
                          }


            if ml:

                if pcheck == "fail":
                    odir, ofilename = os.path.split(ml['ComicLocation'])
                    orig_filename = ofilename
                elif pcheck:
                    #odir, ofilename already set. Carry it through.
                    pass
                else:
                    odir, orig_filename = os.path.split(ml['ComicLocation'])
                logger.fdebug('%s ofilename: %s' % (module, ofilename))
                if any([ofilename == odir, ofilename == odir[:-1], ofilename == '']):
                    self._log("There was a problem deciphering the filename/directory - please verify that the filename : [%s] exists in location [%s]. Aborting." % (ofilename, odir))
                    logger.error(module + ' There was a problem deciphering the filename/directory - please verify that the filename : [%s] exists in location [%s]. Aborting.' % (ofilename, odir))
                    self.failed_files +=1
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)
                logger.fdebug('%s odir: %s' % (module, odir))
                logger.fdebug('%s ofilename: %s' % (module, ofilename))
                ext = os.path.splitext(ofilename)[1]
                logger.fdebug('%s ext: %s' % (module, ext))

            if ofilename is None or ofilename == '':
                logger.error('%s Aborting PostProcessing - the filename does not exist in the location given. Make sure that %s exists and is the correct location.' % (module, self.nzb_folder))
                self.failed_files +=1
                self.valreturn.append({"self.log": self.log,
                                       "mode": 'stop'})
                return self.queue.put(self.valreturn)

            self._log('Original Filename: %s [%s]' % (orig_filename, ext))
            logger.fdebug('%s Original Filename: %s [%s]' % (module, orig_filename, ext))

            if mylar.CONFIG.FILE_FORMAT == '' or not mylar.CONFIG.RENAME_FILES:
                self._log("Rename Files isn't enabled...keeping original filename.")
                logger.fdebug('%s Rename Files is not enabled - keeping original filename.' % module)
                #check if extension is in nzb_name - will screw up otherwise
                if ofilename.lower().endswith(self.extensions):
                    nfilename = ofilename[:-4]
                else:
                    nfilename = ofilename
            else:
                nfilename = helpers.replace_all(chunk_file_format, file_values)
                if mylar.CONFIG.REPLACE_SPACES:
                    #mylar.CONFIG.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
                    nfilename = nfilename.replace(' ', mylar.CONFIG.REPLACE_CHAR)
            nfilename = re.sub('[\,\:\?\"\']', '', nfilename)
            nfilename = re.sub('[\/\*]', '-', nfilename)
            if ml is not None and ml['ForcedMatch'] is True:
                xyb = nfilename.find('[__')
                if xyb != -1:
                    yyb = nfilename.find('__]', xyb)
                    if yyb != -1:
                        rem_issueid = nfilename[xyb+3:yyb]
                        logger.fdebug('issueid: %s' % rem_issueid)
                        nfilename = '%s %s'.strip() % (nfilename[:xyb], nfilename[yyb+3:])
                        logger.fdebug('issueid information [%s] removed successsfully: %s' % (rem_issueid, nfilename))

            self._log("New Filename: %s" % nfilename)
            logger.fdebug('%s New Filename: %s' % (module, nfilename))

            src = os.path.join(odir, ofilename)
            checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True, module=module)
            if not checkdirectory:
                logger.warn('%s Error trying to validate/create directory. Aborting this process at this time.' % module)
                self.failed_files +=1
                self.valreturn.append({"self.log": self.log,
                                       "mode": 'stop'})
                return self.queue.put(self.valreturn)

            if mylar.CONFIG.LOWERCASE_FILENAMES:
                dst = os.path.join(comlocation, (nfilename + ext).lower())
            else:
                dst = os.path.join(comlocation, (nfilename + ext.lower()))
            self._log("Source: %s" % src)
            self._log("Destination: %s" %  dst)
            logger.fdebug('%s Source: %s' % (module, src))
            logger.fdebug('%s Destination: %s' % (module, dst))

            if ml is None:
                #downtype = for use with updater on history table to set status to 'Downloaded'
                downtype = 'True'
                #non-manual run moving/deleting...
                logger.fdebug('%s self.nzb_folder: %s' % (module, self.nzb_folder))
                logger.fdebug('%s odir: %s' % (module, odir))
                logger.fdebug('%s ofilename: %s' % (module,  ofilename))
                logger.fdebug('%s nfilename: %s' % (module, nfilename + ext))
                if mylar.CONFIG.RENAME_FILES:
                    if ofilename != (nfilename + ext):
                        logger.fdebug('%s Renaming %s ..to.. %s' % (module, os.path.join(odir, ofilename), os.path.join(odir, nfilename + ext)))
                    else:
                        logger.fdebug('%s Filename is identical as original, not renaming.' % module)

                src = os.path.join(odir, ofilename)
                try:
                    self._log("[%s] %s - to - %s" % (mylar.CONFIG.FILE_OPTS, src, dst))
                    checkspace = helpers.get_free_space(comlocation)
                    if checkspace is False:
                        if all([pcheck is not None, pcheck != 'fail']):  # meta was done
                            self.tidyup(odir, True, cacheonly=True)
                        raise OSError
                    fileoperation = helpers.file_ops(src, dst)
                    if not fileoperation:
                        raise OSError
                except Exception as e:
                    self._log("Failed to %s %s - check log for exact error." % (mylar.CONFIG.FILE_OPTS, src))
                    self._log("Post-Processing ABORTED.")
                    logger.error('%s Failed to %s %s: %s' % (module, mylar.CONFIG.FILE_OPTS, src, e))
                    logger.error('%s Post-Processing ABORTED' % module)
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)

                #tidyup old path
                if any([mylar.CONFIG.FILE_OPTS == 'move', mylar.CONFIG.FILE_OPTS == 'copy']):
                    self.tidyup(odir, True, filename=orig_filename)

            else:
                #downtype = for use with updater on history table to set status to 'Post-Processed'
                downtype = 'PP'
                #Manual Run, this is the portion.
                src = os.path.join(odir, ofilename)
                if mylar.CONFIG.RENAME_FILES:
                    if ofilename != (nfilename + ext):
                        logger.fdebug('%s Renaming %s ..to.. %s' % (module, os.path.join(odir, ofilename), os.path.join(odir, self.nzb_folder, str(nfilename + ext))))
                    else:
                        logger.fdebug('%s Filename is identical as original, not renaming.' % module)

                logger.fdebug('%s odir src : %s' % (module, src))
                logger.fdebug('%s[%s] %s ... to ... %s' % (module, mylar.CONFIG.FILE_OPTS, src, dst))
                try:
                    checkspace = helpers.get_free_space(comlocation)
                    if checkspace is False:
                        if all([pcheck != 'fail', pcheck is not None]):  # meta was done
                            self.tidyup(odir, True, cacheonly=True)
                        raise OSError
                    fileoperation = helpers.file_ops(src, dst)
                    if not fileoperation:
                        raise OSError
                except Exception as e:
                    logger.error('%s Failed to %s %s: %s' % (module, mylar.CONFIG.FILE_OPTS, src, e))
                    logger.error('%s Post-Processing ABORTED.' %module)
                    self.failed_files +=1
                    self.valreturn.append({"self.log": self.log,
                                           "mode": 'stop'})
                    return self.queue.put(self.valreturn)
                logger.info('%s %s successful to : %s' % (module, mylar.CONFIG.FILE_OPTS, dst))

                if any([mylar.CONFIG.FILE_OPTS == 'move', mylar.CONFIG.FILE_OPTS == 'copy']):
                    self.tidyup(odir, True, subpath, filename=orig_filename)

            #Hopefully set permissions on downloaded file
            if mylar.CONFIG.ENFORCE_PERMS:
                if mylar.OS_DETECT != 'windows':
                    filechecker.setperms(dst.rstrip())
                else:
                    try:
                        permission = int(mylar.CONFIG.CHMOD_FILE, 8)
                        os.umask(0)
                        os.chmod(dst.rstrip(), permission)
                    except OSError:
                        logger.error('%s Failed to change file permissions. Ensure that the user running Mylar has proper permissions to change permissions in : %s' % (module,  dst))
                        logger.fdebug('%s Continuing post-processing but unable to change file permissions in %s' % (module, dst))

            #let's reset the fileop to the original setting just in case it's a manual pp run
            if mylar.CONFIG.FILE_OPTS == 'copy':
                self.fileop = shutil.copy
            else:
                self.fileop = shutil.move

            #delete entry from nzblog table
            myDB.action('DELETE from nzblog WHERE issueid=?', [issueid])

            updater.totals(comicid, havefiles='+1',issueid=issueid,file=dst)

            #update snatched table to change status to Downloaded
            if annchk == "no":
                updater.foundsearch(comicid, issueid, down=downtype, module=module, crc=crcvalue)
                dispiss = '#%s' % issuenumOG
                updatetable = 'issues'
            else:
                updater.foundsearch(comicid, issueid, mode='want_ann', down=downtype, module=module, crc=crcvalue)
                if 'annual' in issuenzb['ReleaseComicName'].lower(): #series.lower():
                    dispiss = 'Annual #%s' % issuenumOG
                elif 'special' in issuenzb['ReleaseComicName'].lower():
                    dispiss = 'Special #%s' % issuenumOG
                else:
                    dispiss = '#%s' % issuenumOG
                updatetable = 'annuals'
            logger.fdebug('[annchk:%s] issue to update: %s' % (annchk, dispiss))

            #new method for updating status after pp
            if os.path.isfile(dst):
                ctrlVal = {"IssueID":     issueid}
                newVal = {"Status":       "Downloaded",
                          "Location":     os.path.basename(dst)}
                logger.fdebug('writing: %s -- %s' % (newVal, ctrlVal))
                myDB.upsert(updatetable, newVal, ctrlVal)

            try:
                if ml['IssueArcID']:
                    logger.info('Watchlist Story Arc match detected.')
                    logger.info(ml)
                    arcinfo = myDB.selectone('SELECT * FROM storyarcs where IssueArcID=?', [ml['IssueArcID']]).fetchone()
                    if arcinfo is None:
                        logger.warn('Unable to locate IssueID within givin Story Arc. Ensure everything is up-to-date (refreshed) for the Arc.')
                    else:
                        if mylar.CONFIG.COPY2ARCDIR is True:
                            if arcinfo['Publisher'] is None:
                                arcpub = arcinfo['IssuePublisher']
                            else:
                                arcpub = arcinfo['Publisher']

                            grdst = helpers.arcformat(arcinfo['StoryArc'], helpers.spantheyears(arcinfo['StoryArcID']), arcpub)
                            logger.info('grdst:' + grdst)
                            checkdirectory = filechecker.validateAndCreateDirectory(grdst, True, module=module)
                            if not checkdirectory:
                                logger.warn('%s Error trying to validate/create directory. Aborting this process at this time.' % module)
                                self.valreturn.append({"self.log": self.log,
                                                       "mode": 'stop'})
                                return self.queue.put(self.valreturn)

                            if mylar.CONFIG.READ2FILENAME:
                                logger.fdebug('%s readingorder#: %s' % (module, arcinfo['ReadingOrder']))
                                if int(arcinfo['ReadingOrder']) < 10: readord = "00" + str(arcinfo['ReadingOrder'])
                                elif int(arcinfo['ReadingOrder']) >= 10 and int(arcinfo['ReadingOrder']) <= 99: readord = "0" + str(arcinfo['ReadingOrder'])
                                else: readord = str(arcinfo['ReadingOrder'])
                                dfilename = str(readord) + "-" + os.path.split(dst)[1]
                            else:
                                dfilename = os.path.split(dst)[1]

                            grab_dst = os.path.join(grdst, dfilename)

                            logger.fdebug('%s Destination Path : %s' % (module, grab_dst))
                            grab_src = dst
                            logger.fdebug('%s Source Path : %s' % (module, grab_src))
                            logger.info('%s[%s] %s into directory: %s' % (module, mylar.CONFIG.ARC_FILEOPS.upper(), dst, grab_dst))

                            try:
                                #need to ensure that src is pointing to the series in order to do a soft/hard-link properly
                                checkspace = helpers.get_free_space(grdst)
                                if checkspace is False:
                                    raise OSError
                                fileoperation = helpers.file_ops(grab_src, grab_dst, arc=True)
                                if not fileoperation:
                                    raise OSError
                            except Exception as e:
                                logger.error('%s Failed to %s %s: %s' % (module, mylar.CONFIG.ARC_FILEOPS, grab_src, e))
                                return
                        else:
                            grab_dst = dst

                        #delete entry from nzblog table in case it was forced via the Story Arc Page
                        IssArcID = 'S' + str(ml['IssueArcID'])
                        myDB.action('DELETE from nzblog WHERE IssueID=? AND SARC=?', [IssArcID,arcinfo['StoryArc']])

                        logger.fdebug('%s IssueArcID: %s' % (module, ml['IssueArcID']))
                        ctrlVal = {"IssueArcID":  ml['IssueArcID']}
                        newVal = {"Status":       "Downloaded",
                                  "Location":     grab_dst}
                        logger.fdebug('writing: %s -- %s' % (newVal, ctrlVal))
                        myDB.upsert("storyarcs", newVal, ctrlVal)
                        logger.fdebug('%s [%s] Post-Processing completed for: %s' % (module, arcinfo['StoryArc'], grab_dst))

            except:
                pass

            if mylar.CONFIG.WEEKFOLDER or mylar.CONFIG.SEND2READ:
                #mylar.CONFIG.WEEKFOLDER = will *copy* the post-processed file to the weeklypull list folder for the given week.
                #mylar.CONFIG.SEND2READ = will add the post-processed file to the readinglits
                weeklypull.weekly_check(comicid, issuenum, file=(nfilename +ext), path=dst, module=module, issueid=issueid)

            # retrieve/create the corresponding comic objects
            if mylar.CONFIG.ENABLE_EXTRA_SCRIPTS:
                folderp = dst #folder location after move/rename
                nzbn = self.nzb_name #original nzb name
                filen = nfilename + ext #new filename
                #name, comicyear, comicid , issueid, issueyear, issue, publisher
                #create the dic and send it.
                seriesmeta = []
                seriesmetadata = {}
                seriesmeta.append({
                            'name':                 series,
                            'comicyear':            seriesyear,
                            'comicid':              comicid,
                            'issueid':              issueid,
                            'issueyear':            issueyear,
                            'issue':                issuenum,
                            'publisher':            publisher
                            })
                seriesmetadata['seriesmeta'] = seriesmeta
                self._run_extra_scripts(nzbn, self.nzb_folder, filen, folderp, seriesmetadata)

            #if ml is not None:
            #    #we only need to return self.log if it's a manual run and it's not a snatched torrent
            #    #manual run + not snatched torrent (or normal manual-run)
            #    logger.info(module + ' Post-Processing completed for: ' + series + ' ' + dispiss)
            #    self._log(u"Post Processing SUCCESSFUL! ")
            #    self.valreturn.append({"self.log": self.log,
            #                           "mode": 'stop',
            #                           "issueid": issueid,
            #                           "comicid": comicid})
            #    #if self.apicall is True:
            #    self.sendnotify(series, issueyear, dispiss, annchk, module)
            #    return self.queue.put(self.valreturn)

            self.sendnotify(series, issueyear, dispiss, annchk, module)

            logger.info('%s Post-Processing completed for: %s %s' % (module, series, dispiss))
            self._log(u"Post Processing SUCCESSFUL! ")

            self.valreturn.append({"self.log": self.log,
                                   "mode": 'stop',
                                   "issueid": issueid,
                                   "comicid": comicid})

            return self.queue.put(self.valreturn)


    def sendnotify(self, series, issueyear, issuenumOG, annchk, module):

        if issueyear is None:
            prline = '%s %s' % (series, issuenumOG)
        else:
            prline = '%s (%s) %s' % (series, issueyear, issuenumOG)

        prline2 = 'Mylar has downloaded and post-processed: ' + prline

        if mylar.CONFIG.PROWL_ENABLED:
            pushmessage = prline
            prowl = notifiers.PROWL()
            prowl.notify(pushmessage, "Download and Postprocessing completed", module=module)

        if mylar.CONFIG.PUSHOVER_ENABLED:
            pushover = notifiers.PUSHOVER()
            pushover.notify(prline, prline2, module=module)

        if mylar.CONFIG.BOXCAR_ENABLED:
            boxcar = notifiers.BOXCAR()
            boxcar.notify(prline=prline, prline2=prline2, module=module)

        if mylar.CONFIG.PUSHBULLET_ENABLED:
            pushbullet = notifiers.PUSHBULLET()
            pushbullet.notify(prline=prline, prline2=prline2, module=module)

        if mylar.CONFIG.TELEGRAM_ENABLED:
            telegram = notifiers.TELEGRAM()
            telegram.notify(prline2)

        if mylar.CONFIG.SLACK_ENABLED:
            slack = notifiers.SLACK()
            slack.notify("Download and Postprocessing completed", prline2, module=module)

        if mylar.CONFIG.EMAIL_ENABLED and mylar.CONFIG.EMAIL_ONPOST:
            logger.info(u"Sending email notification")
            email = notifiers.EMAIL()
            email.notify(prline2, "Mylar notification - Processed", module=module)

        return

class FolderCheck():

    def __init__(self):
        import Queue
        import PostProcessor, logger

        self.module = '[FOLDER-CHECK]'
        self.queue = Queue.Queue()

    def run(self):
        if mylar.IMPORTLOCK:
            logger.info('There is an import currently running. In order to ensure successful import - deferring this until the import is finished.')
            return
        #monitor a selected folder for 'snatched' files that haven't been processed
        #junk the queue as it's not needed for folder monitoring, but needed for post-processing to run without error.
        helpers.job_management(write=True, job='Folder Monitor', current_run=helpers.utctimestamp(), status='Running')
        mylar.MONITOR_STATUS = 'Running'
        logger.info('%s Checking folder %s for newly snatched downloads' % (self.module, mylar.CONFIG.CHECK_FOLDER))
        PostProcess = PostProcessor('Manual Run', mylar.CONFIG.CHECK_FOLDER, queue=self.queue)
        result = PostProcess.Process()
        logger.info('%s Finished checking for newly snatched downloads' % self.module)
        helpers.job_management(write=True, job='Folder Monitor', last_run_completed=helpers.utctimestamp(), status='Waiting')
        mylar.MONITOR_STATUS = 'Waiting'
