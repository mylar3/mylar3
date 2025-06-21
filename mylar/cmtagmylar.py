# This script was initially based from Manders2600 Script with the use of the awesome ComicTagger.
# Modified, so Mylar just can pass in relevant information instead of querying CV for it to do it's magic.


import os, errno
import sys
import re
import glob
import shlex
import platform
import shutil
import time
import zipfile
import subprocess
from packaging.version import parse as parse_version
from subprocess import CalledProcessError, check_output
import mylar

from mylar import logger, notifiers




def check_cbr_has_folders(filepath):
    """Check if a CBR file has internal folder structure"""
    try:
        from lib.rarfile import rarfile
        with rarfile.RarFile(filepath) as rf:
            for name in rf.namelist():
                if '/' in name or '\\' in name:
                    # Found a path separator, indicating folders
                    return True
        return False
    except Exception as e:
        logger.fdebug('Error checking CBR structure: %s' % e)
        return False


def flatten_cbr(source_cbr, temp_dir, module=''):
    """Extract and create a flattened CBR without folder structure"""
    try:
        # Import Mylar's bundled rarfile correctly
        from lib.rarfile import rarfile
        import zipfile
        import tempfile
        import subprocess

        # First, find a working unrar tool
        unrar_tool = None

        # Try system unrar first
        try:
            result = subprocess.run(['/usr/bin/unrar'], capture_output=True)
            # unrar exists if we get any return code (it returns 7 when run without args)
            unrar_tool = '/usr/bin/unrar'
            logger.fdebug('%s Found system unrar at: %s' % (module, unrar_tool))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.fdebug('%s Error checking /usr/bin/unrar: %s' % (module, e))

        if not unrar_tool:
            try:
                result = subprocess.run(['unrar'], capture_output=True)
                unrar_tool = 'unrar'
                logger.fdebug('%s Found unrar in PATH' % module)
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.fdebug('%s Error checking unrar in PATH: %s' % (module, e))

        if not unrar_tool:
            logger.error('%s Cannot find unrar tool - unable to flatten CBR' % module)
            return None

        # Configure rarfile BEFORE creating any RarFile instances
        rarfile.UNRAR_TOOL = unrar_tool
        rarfile.PATH_SEP = '/'

        logger.fdebug('%s CBR has folder structure - flattening it using %s' % (module, unrar_tool))

        # Create a temporary directory for extraction
        extract_dir = tempfile.mkdtemp(dir=temp_dir)
        flattened_files = []

        # Use subprocess to extract directly instead of rarfile.extract
        logger.fdebug('%s Extracting CBR to: %s' % (module, extract_dir))

        # Change to extraction directory first (like manual unrar command)
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(extract_dir)
            extract_cmd = [unrar_tool, 'x', '-y', source_cbr]
            logger.fdebug('%s Running: %s' % (module, ' '.join(extract_cmd)))
            result = subprocess.run(extract_cmd, capture_output=True, text=True)

            # Check if any files were actually extracted (even if unrar reported errors)
            extracted_files = []
            for root, dirs, files in os.walk(extract_dir):
                extracted_files.extend(files)

            if not extracted_files:
                logger.error('%s No files were extracted from CBR' % module)
                logger.error('%s stdout: %s' % (module, result.stdout))
                logger.error('%s stderr: %s' % (module, result.stderr))
                os.chdir(original_dir)
                import shutil
                shutil.rmtree(extract_dir)
                return None
            else:
                logger.fdebug(
                    '%s Extraction completed - found %d files (return code: %d)' % (module, len(extracted_files),
                                                                                    result.returncode))
                if result.returncode != 0:
                    logger.fdebug('%s unrar returned non-zero code but files were extracted' % module)
                if result.stdout:
                    logger.fdebug('%s unrar output: %s' % (module, result.stdout[:500]))  # First 500 chars
        finally:
            os.chdir(original_dir)

        # Now find all extracted files and flatten the structure
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                # Skip .DS_Store but keep other files
                if file == '.DS_Store':
                    continue

                old_path = os.path.join(root, file)
                new_path = os.path.join(extract_dir, file)

                if old_path != new_path:
                    # Handle filename conflicts
                    if os.path.exists(new_path):
                        base, ext = os.path.splitext(file)
                        counter = 1
                        while os.path.exists(new_path):
                            new_name = f"{base}_{counter}{ext}"
                            new_path = os.path.join(extract_dir, new_name)
                            counter += 1
                    os.rename(old_path, new_path)
                    flattened_files.append(os.path.basename(new_path))
                else:
                    flattened_files.append(file)

        # Remove empty directories
        for root, dirs, files in os.walk(extract_dir, topdown=False):
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                try:
                    os.rmdir(dir_path)
                except:
                    pass

        # Create a temporary CBZ
        temp_cbz = source_cbr.replace('.cbr', '_flattened.cbz')
        if os.path.exists(temp_cbz):
            os.remove(temp_cbz)

        logger.fdebug('%s Creating flattened archive with %d files' % (module, len(flattened_files)))

        with zipfile.ZipFile(temp_cbz, 'w', zipfile.ZIP_STORED) as zf:
            for filename in sorted(flattened_files):
                filepath = os.path.join(extract_dir, filename)
                if os.path.exists(filepath) and os.path.isfile(filepath):
                    zf.write(filepath, filename)

        # Clean up extraction directory
        import shutil
        shutil.rmtree(extract_dir)

        logger.fdebug('%s Created flattened archive: %s' % (module, temp_cbz))
        return temp_cbz

    except Exception as e:
        logger.error('%s Error flattening CBR: %s' % (module, e))
        import traceback
        logger.error(traceback.format_exc())
        return None

def run(dirName, nzbName=None, issueid=None, comversion=None, manual=None, filename=None, module=None, manualmeta=False, readingorder=None, agerating=None):
    if module is None:
        module = ''
    module += '[META-TAGGER]'

    logger.fdebug(module + ' dirName:' + dirName)

    # 2015-11-23: Recent CV API changes restrict the rate-limit to 1 api request / second.
    # ComicTagger has to be included now with the install as a timer had to be added to allow for the 1/second rule.
    comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.py')
    logger.fdebug('ComicTagger Path location for internal comictagger.py set to : ' + comictagger_cmd)

    # Force mylar to use cmtagger_path = mylar.PROG_DIR to force the use of the included lib.

    logger.fdebug(module + ' Filename is : ' + filename)

    filepath = filename
    og_filepath = filepath
    try:
        filename = os.path.split(filename)[1]   # just the filename itself
    except:
        logger.warn('Unable to detect filename within directory - I am aborting the tagging. You best check things out.')
        sendnotify("Error - Unable to detect filename within directory. Tagging aborted.", filename, module)
        return "fail"

    #make use of temporary file location in order to post-process this to ensure that things don't get hammered when converting
    new_filepath = None
    new_folder = None
    try:
        import tempfile
        logger.fdebug('Filepath: %s' %filepath)
        logger.fdebug('Filename: %s' %filename)
        new_folder = tempfile.mkdtemp(prefix='mylar_', dir=mylar.CONFIG.CACHE_DIR) #prefix, suffix, dir
        os.chmod(new_folder, 0o777)
        logger.fdebug('New_Folder: %s' % new_folder)
        new_filepath = os.path.join(new_folder, filename)
        logger.fdebug('New_Filepath: %s' % new_filepath)
        if mylar.CONFIG.FILE_OPTS == 'copy' and manualmeta == False:
            shutil.copy(filepath, new_filepath)
        else:
            shutil.copy(filepath, new_filepath)
        filepath = new_filepath
    except Exception as e:
        logger.warn('%s Unexpected Error: %s [%s]' % (module, sys.exc_info()[0], e))
        logger.warn(module + ' Unable to create temporary directory to perform meta-tagging. Processing without metatagging.')
        sendnotify("Error - Unable to create temporary directory to perform meta-tagging. Processing without metatagging.", filename, module)
        tidyup(og_filepath, new_filepath, new_folder, manualmeta)
        return "fail"

    # Check if CBR has folder structure and flatten if needed
    if filename.lower().endswith('.cbr'):
        if check_cbr_has_folders(filepath):
            logger.fdebug(module + ' CBR file has folder structure - flattening it')
            flattened_cbr = flatten_cbr(filepath, new_folder, module)
            if flattened_cbr and os.path.exists(flattened_cbr):
                # Replace the filepath with the flattened version
                old_filepath = filepath
                filepath = flattened_cbr
                filename = os.path.basename(flattened_cbr)
                logger.fdebug(module + ' Using flattened CBR: ' + filepath)
            else:
                logger.error(module + ' Failed to flatten CBR with folder structure - cannot continue conversion')
                sendnotify("Error - Failed to flatten CBR with folder structure", filename, module)
                tidyup(og_filepath, new_filepath, new_folder, manualmeta)
                return "fail"

    ## Sets up other directories ##
    scriptname = os.path.basename(sys.argv[0])
    downloadpath = os.path.abspath(dirName)
    sabnzbdscriptpath = os.path.dirname(sys.argv[0])
    comicpath = new_folder

    logger.fdebug(module + ' Paths / Locations:')
    logger.fdebug(module + ' scriptname : ' + scriptname)
    logger.fdebug(module + ' downloadpath : ' + downloadpath)
    logger.fdebug(module + ' sabnzbdscriptpath : ' + sabnzbdscriptpath)
    logger.fdebug(module + ' comicpath : ' + comicpath)
    logger.fdebug(module + ' Running the ComicTagger Add-on for Mylar')


    ##set up default comictagger options here.
    #used for cbr - to - cbz conversion
    #depending on copy/move - either we retain the rar or we don't.
    if mylar.CONFIG.FILE_OPTS == 'move':
        cbr2cbzoptions = ["--configfolder", mylar.CONFIG.CT_SETTINGSPATH, "-e", "--delete-rar"]
    else:
        cbr2cbzoptions = ["--configfolder", mylar.CONFIG.CT_SETTINGSPATH, "-e"]

    tagoptions = ["-s"]

    cvers = "volume="
    if mylar.CONFIG.CMTAG_VOLUME:
        if mylar.CONFIG.CMTAG_START_YEAR_AS_VOLUME:
            pass
            # comversion is already converted - just leaving this here so we know
        else:
            if mylar.CONFIG.SETDEFAULTVOLUME:
                if any([comversion is None, comversion == '', comversion == 'None']):
                    comversion = '1'
                comversion = re.sub('[^0-9]', '', comversion).strip()
            else:
                if any([comversion is None, comversion == '', comversion == 'None']):
                    comversion = None
                else:
                    comversion = re.sub('[^0-9]', '', comversion).strip()
        if comversion is not None:
            cvers = 'volume=%s' % comversion

    if readingorder is not None:
        if type(readingorder) == list:
            orderseq = []
            arcseq = []
            for osq in readingorder:
                orderseq.append(str(osq[1]))
                arcseq.append(osq[0])
            arcseqn = ','.join(arcseq).strip()
            arcseqname = re.sub(r',', '^,', arcseqn).strip()
            ordersn = ','.join(orderseq).strip()
            orders = re.sub(r',', '^,', ordersn).strip()
            rorder = 'storyArcNumber=%s, storyArc=%s' % (orders, arcseqname)
        else:
            roder = 'storyArcNumber=%s' % readingorder
    else:
        rorder = 'storyArcNumber='

    if all([agerating is not None, agerating != 'None']):
        arating = 'ageRating=%s' % (agerating)
    else:
        arating = 'ageRating='

    tline = '%s, %s, %s' % (cvers, rorder, arating)
    tagoptions.extend(["-m", tline])

    try:
        #from comictaggerlib import ctversion
        ct_check = subprocess.check_output([sys.executable, comictagger_cmd, "--version"], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        #logger.warn(module + "[WARNING] "command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
        logger.warn(module + '[WARNING] Make sure that you are using the comictagger included with Mylar.')
        tidyup(filepath, new_filepath, new_folder, manualmeta)
        return "fail"

    logger.info('ct_check: %s' % ct_check)
    ctend = str(ct_check).find('[')
    ct_version = re.sub("[^0-9]", "", str(ct_check)[:ctend])
    if parse_version(ct_version) >= parse_version('1.3.1'):
        if any([mylar.CONFIG.COMICVINE_API == 'None', mylar.CONFIG.COMICVINE_API is None]):
            logger.fdebug('%s ComicTagger v.%s being used - no personal ComicVine API Key supplied. Take your chances.' % (module, ct_version))
            use_cvapi = "False"
        else:
            logger.fdebug('%s ComicTagger v.%s being used - using personal ComicVine API key supplied via mylar.' % (module, ct_version))
            use_cvapi = "True"
            tagoptions.extend(["--cv-api-key", mylar.CONFIG.COMICVINE_API, "--configfolder", mylar.CONFIG.CT_SETTINGSPATH, "--notes_format", mylar.CONFIG.CT_NOTES_FORMAT])
    else:
        logger.fdebug('%s ComicTagger v.ct_version being used - personal ComicVine API key not supported in this version. Good luck.' % (module, ct_version))
        use_cvapi = "False"

    i = 1
    tagcnt = 0

    if mylar.CONFIG.CBR2CBZ_ONLY:
        logger.fdebug(module + ' CBR2CBZ Conversion only.')
    else:
        if mylar.CONFIG.CT_TAG_CR:
            tagcnt = 1
            logger.fdebug(module + ' CR Tagging enabled.')

        if mylar.CONFIG.CT_TAG_CBL:
            if not mylar.CONFIG.CT_TAG_CR: i = 2  #set the tag to start at cbl and end without doing another tagging.
            tagcnt = 2
            logger.fdebug(module + ' CBL Tagging enabled.')

    if tagcnt == 0 and not mylar.CONFIG.CBR2CBZ_ONLY:
        logger.warn(module + ' You have metatagging enabled, but you have not selected the type(s) of metadata to write. Please fix and re-run manually')
        tidyup(filepath, new_filepath, new_folder, manualmeta)
        return "fail"

    #if it's a cbz file - check if no-overwrite existing tags is enabled / disabled in config.
    if filename.endswith('.cbz'):
        if mylar.CONFIG.CT_CBZ_OVERWRITE:
            logger.fdebug(module + ' Will modify existing tag blocks even if it exists.')
        else:
            logger.fdebug(module + ' Will NOT modify existing tag blocks even if they exist already.')
            tagoptions.extend(["--nooverwrite"])
        initial_ctrun = False
    else:
        # CBR files need conversion
        initial_ctrun = True

    if issueid is None:
        tagoptions.extend(["-f", "-o"])
    else:
        tagoptions.extend(["-o", "--id", issueid])

    original_tagoptions = tagoptions
    og_tagtype = None
    initial_ctrun = True
    error_remove = False

    while (i <= tagcnt):
        if initial_ctrun:
            f_tagoptions = cbr2cbzoptions
            f_tagoptions.extend([filepath])
        else:
            if i == 1:
                tagtype = 'cr'  # CR meta-tagging cycle.
                tagdisp = 'ComicRack tagging'
            elif i == 2:
                tagtype = 'cbl'  # Cbl meta-tagging cycle
                tagdisp = 'Comicbooklover tagging'

            f_tagoptions = original_tagoptions

            if og_tagtype is not None:
                for index, item in enumerate(f_tagoptions):
                    if item == og_tagtype:
                        f_tagoptions[index] = tagtype
            else:
                f_tagoptions.extend(["--type", tagtype, filepath])

            og_tagtype = tagtype

            logger.info(module + ' ' + tagdisp + ' meta-tagging processing started.')

        currentScriptName = [sys.executable, comictagger_cmd]
        script_cmd = currentScriptName + f_tagoptions

        if initial_ctrun:
            logger.fdebug('%s Enabling ComicTagger script with options: %s' % (module, f_tagoptions))
            script_cmdlog = script_cmd

        else:
            logger.fdebug('%s Enabling ComicTagger script with options: %s' %(module, re.sub(f_tagoptions[f_tagoptions.index(mylar.CONFIG.COMICVINE_API)], 'REDACTED', str(f_tagoptions))))
            # generate a safe command line string to execute the script and provide all the parameters
            script_cmdlog = re.sub(f_tagoptions[f_tagoptions.index(mylar.CONFIG.COMICVINE_API)], 'REDACTED', str(script_cmd))

        logger.fdebug(module + ' Executing command: ' +str(script_cmdlog))
        logger.fdebug(module + ' Absolute path to script: ' +script_cmd[0])
        try:
            # use subprocess to run the command and capture output
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, text=True, stderr=subprocess.STDOUT)
            out, err = p.communicate()
            #logger.info(out)
            #logger.info(err)
            #if out is not None:
            #    out = out.decode('utf-8')
            if all([err is not None, err != '']):
                logger.warn('[ERROR RETURNED FROM COMIC-TAGGER] %s' % (err,))
            #    err = err.decode('utf-8')
            if initial_ctrun and 'exported successfully' in out:
                logger.fdebug('%s[COMIC-TAGGER] : %s' % (module, out))
                #Archive exported successfully to: X-Men v4 008 (2014) (Digital) (Nahga-Empire).cbz (Original deleted)
                if 'Error deleting' in filepath:
                    tf1 = out.find('exported successfully to: ')
                    tmpfilename = out[tf1 + len('exported successfully to: '):].strip()
                    error_remove = True
                else:
                    tmpfilename = re.sub('Archive exported successfully to: ', '', out.rstrip())
                if mylar.CONFIG.FILE_OPTS == 'move':
                    tmpfilename = re.sub('\(Original deleted\)', '', tmpfilename).strip()
                tmpf = tmpfilename
                filepath = os.path.join(comicpath, tmpf)
                if filename.lower() != tmpf.lower() and tmpf.endswith('(1).cbz'):
                    logger.fdebug('New filename [%s] is named incorrectly due to duplication during metatagging - Making sure it\'s named correctly [%s].' % (tmpf, filename))
                    tmpfilename = filename
                    filepath_new = os.path.join(comicpath, tmpfilename)
                    try:
                        os.rename(filepath, filepath_new)
                        filepath = filepath_new
                    except:
                        logger.warn('%s unable to rename file to accomodate metatagging cbz to the same filename' % module)
                if not os.path.isfile(filepath):
                    logger.fdebug('%s Trying utf-8 conversion.' % module)
                    tmpf = tmpfilename.encode('utf-8')
                    filepath = os.path.join(comicpath, tmpf)
                    if not os.path.isfile(filepath):
                        logger.fdebug('%s Trying latin-1 conversion.' % module)
                        tmpf = tmpfilename.encode('Latin-1')
                        filepath = os.path.join(comicpath, tmpf)

                logger.fdebug('%s[COMIC-TAGGER][CBR-TO-CBZ] New filename: %s' % (module, filepath))
                initial_ctrun = False
            elif initial_ctrun and 'Archive is not a RAR' in out:
                logger.fdebug('%s Output: %s' % (module,out))
                logger.warn('%s[COMIC-TAGGER] file is not in a RAR format: %s' % (module, filename))
                initial_ctrun = False
            elif initial_ctrun:
                initial_ctrun = False
                if any(['file is not expected size' in out, 'Failed the read' in out]):
                    logger.fdebug('%s Output: %s' % (module,out))
                    tidyup(og_filepath, new_filepath, new_folder, manualmeta)
                    return 'corrupt'
                else:
                    logger.fdebug('out: %s' % (out,))
                    logger.fdebug('filename: %s' % (filename,))
                    cbz_message = 'Failed to convert cbr to cbz - check permissions on folder %s and/or the location where Mylar is trying to tag the files from.' % mylar.CONFIG.CACHE_DIR
                    logger.warn('%s[COMIC-TAGGER][CBR-TO-CBZ]%s' % (module, cbz_message))
                    sendnotify('Error - %s' % (cbz_message), filename, module)
                    tidyup(og_filepath, new_filepath, new_folder, manualmeta)
                    return 'fail'
            elif 'Cannot find' in out:
                logger.fdebug('%s Output: %s' % (module,out))
                logger.warn('%s[COMIC-TAGGER] Unable to locate file: %s' % (module, filename))
                file_error = 'file not found||' + filename
                return file_error
            elif 'not a comic archive!' in out:
                logger.fdebug('%s Output: %s' % (module,out))
                logger.warn('%s[COMIC-TAGGER] Unable to locate file: %s' % (module, filename))
                file_error = 'file not found||%s' % filename
                return file_error
            else:
                if 'Save complete' not in out:
                    unknown_message = out
                    logger.warn('%s[COMIC-TAGGER][UNKNOWN-ERROR-DURING-METATAGGING] %s' % (module, unknown_message))
                    sendnotify('Error - %s' % (unknown_message), filename, module)
                    tidyup(og_filepath, new_filepath, new_folder, manualmeta)
                    return 'fail'
                else:
                    logger.info('%s[COMIC-TAGGER] Successfully wrote %s [%s]' % (module, tagdisp, filepath))
                i+=1
        except OSError as e:
            logger.warn('%s[COMIC-TAGGER] Unable to run comictagger with the options provided: %s' % (module, re.sub(f_tagoptions[f_tagoptions.index(mylar.CONFIG.COMICVINE_API)], 'REDACTED', str(script_cmd))))
            tidyup(filepath, new_filepath, new_folder, manualmeta)
            return "fail"
        except Exception as e:
            logger.warn('%s[COMIC-TAGGER] Error : %s' % (module, e))
            tidyup(filepath, new_filepath, new_folder, manualmeta)
            return "fail"
        if mylar.CONFIG.CBR2CBZ_ONLY and initial_ctrun == False:
            break

    return filepath


def tidyup(filepath, new_filepath, new_folder, manualmeta):
   if all([new_filepath is not None, new_folder is not None]):
        if mylar.CONFIG.FILE_OPTS == 'copy' and manualmeta == False:
            if all([os.path.exists(new_folder), os.path.isfile(filepath)]):
                shutil.rmtree(new_folder)
            elif os.path.exists(new_filepath) and not os.path.exists(filepath):
                shutil.move(new_filepath, filepath + '.BAD')
        else:
            if os.path.exists(new_filepath) and not os.path.exists(filepath):
                shutil.move(new_filepath, filepath + '.BAD')
            if all([os.path.exists(new_folder), os.path.isfile(filepath)]):
                shutil.rmtree(new_folder)

def sendnotify(message, filename, module):

    prline = filename

    prline2 = 'Mylar metatagging error: ' + message + ' File: ' + prline

    try:
        if mylar.CONFIG.PROWL_ENABLED:
            pushmessage = prline
            prowl = notifiers.PROWL()
            prowl.notify(pushmessage, "Mylar metatagging error: ", module=module)

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
            slack.notify("Mylar metatagging error: ", prline2, module=module)

        if mylar.CONFIG.MATTERMOST_ENABLED:
            mattermost = notifiers.MATTERMOST()
            mattermost.notify("Mylar metatagging error: ", prline2, module=module)

        if mylar.CONFIG.DISCORD_ENABLED:
            discord = notifiers.DISCORD()
            discord.notify(filename, message, module=module)

        if mylar.CONFIG.EMAIL_ENABLED and mylar.CONFIG.EMAIL_ONPOST:
            logger.info("Sending email notification")
            email = notifiers.EMAIL()
            email.notify(prline2, "Mylar metatagging error: ", module=module)

        if mylar.CONFIG.GOTIFY_ENABLED:
            gotify = notifiers.GOTIFY()
            gotify.notify("Mylar metatagging error: ", prline2, module=module)
    except Exception as e:
        logger.warn('[NOTIFICATION] Unable to send notification: %s' % e)

    return
