# This script was taken almost entirely from Manders2600 Script with the use of the awesome ComicTagger.
# modified very slightly so Mylar just passes it the IssueID for it to do it's magic.


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
from subprocess import CalledProcessError, check_output
import mylar

from mylar import logger
from mylar.helpers import cvapi_check

def run (dirName, nzbName=None, issueid=None, manual=None, filename=None, module=None):
    if module is None:
        module = ''
    module += '[META-TAGGER]'

    logger.fdebug(module + ' dirName:' + dirName)

    ## Set the directory in which comictagger and other external commands are located - IMPORTANT - ##
    # ( User may have to modify, depending on their setup, but these are some guesses for now )

        
    if platform.system() == "Windows":
        #if it's a source install.
        sys_type = 'windows'
        if os.path.isdir(os.path.join(mylar.CMTAGGER_PATH, '.git')):
            comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.py')

        else:
            #regardless of 32/64 bit install
            if 'comictagger.exe' in mylar.CMTAGGER_PATH:
                comictagger_cmd = mylar.CMTAGGER_PATH
            else:
                comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.exe')

        if mylar.UNRAR_CMD == 'None' or mylar.UNRAR_CMD == '' or mylar.UNRAR_CMD is None:
            unrar_cmd = "C:\Program Files\WinRAR\UnRAR.exe"
        else:
            unrar_cmd = mylar.UNRAR_CMD.strip()

      # test for UnRAR
        if not os.path.isfile(unrar_cmd):
            unrar_cmd = "C:\Program Files (x86)\WinRAR\UnRAR.exe"
            if not os.path.isfile(unrar_cmd):
                logger.fdebug(module + ' Unable to locate UnRAR.exe - make sure it is installed.')
                logger.fdebug(module + ' Aborting meta-tagging.')
                return "fail"

        logger.fdebug(module + ' UNRAR path set to : ' + unrar_cmd)

    
    elif platform.system() == "Darwin":
        #Mac OS X
        sys_type = 'mac'
        comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.py')
        if mylar.UNRAR_CMD == 'None' or mylar.UNRAR_CMD == '' or mylar.UNRAR_CMD is None:
            unrar_cmd = "/usr/local/bin/unrar"
        else:
            unrar_cmd = mylar.UNRAR_CMD.strip()

        logger.fdebug(module + ' UNRAR path set to : ' + unrar_cmd)
    
    else:
        #for the 'nix
        sys_type = 'linux'
        if mylar.UNRAR_CMD == 'None' or mylar.UNRAR_CMD == '' or mylar.UNRAR_CMD is None:
            if 'freebsd' in platform.linux_distribution()[0].lower():
                unrar_cmd = "/usr/local/bin/unrar"
            else:
                unrar_cmd = "/usr/bin/unrar"
        else:
            unrar_cmd = mylar.UNRAR_CMD.strip()

        logger.fdebug(module + ' UNRAR path set to : ' + unrar_cmd)

        #check for dependencies here - configparser
        try:
            import configparser
        except ImportError:
            logger.fdebug(module + ' configparser not found on system. Please install manually in order to write metadata')
            logger.fdebug(module + ' continuing with PostProcessing, but I am not using metadata.')
            return "fail"

        #set this to the lib path (ie. '<root of mylar>/lib')
        comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.py')

#    if not os.path.exists( comictagger_cmd ):
#        print "ERROR:  can't find the ComicTagger program: {0}".format( comictagger_cmd )
#        print "        You probably need to edit this script!"
#        sys.exit( 1 )

    file_conversion = True
    file_extension_fixing = True
    if not os.path.exists( unrar_cmd ):
        logger.fdebug(module + ' WARNING:  cannot find the unrar command.')
        logger.fdebug(module + ' File conversion and extension fixing not available')
        logger.fdebug(module + ' You probably need to edit this script, or install the missing tool, or both!')
        return "fail"
        #file_conversion = False
        #file_extension_fixing = False


    ## Sets up other directories ##
    scriptname = os.path.basename( sys.argv[0] )
    downloadpath = os.path.abspath( dirName ) 
    sabnzbdscriptpath = os.path.dirname( sys.argv[0] )
    if manual is None:
        comicpath = os.path.join( downloadpath , "temp" )
    else:
        chkpath, chkfile = os.path.split(filename)
        logger.fdebug(module + ' chkpath: ' + chkpath)
        logger.fdebug(module + ' chkfile: ' + chkfile)
        extensions = ('.cbr', '.cbz')
        if os.path.isdir(chkpath) and chkpath != downloadpath:
            logger.fdebug(module + ' Changing ' + downloadpath + ' location to ' + chkpath + ' as it is a directory.')
            downloadpath = chkpath
        comicpath = os.path.join( downloadpath, issueid )
    unrar_folder = os.path.join( comicpath , "unrard" )

    logger.fdebug(module + ' Paths / Locations:')
    logger.fdebug(module + ' scriptname : ' + scriptname)
    logger.fdebug(module + ' downloadpath : ' + downloadpath)
    logger.fdebug(module + ' sabnzbdscriptpath : ' + sabnzbdscriptpath)
    logger.fdebug(module + ' comicpath : ' + comicpath)
    logger.fdebug(module + ' unrar_folder : ' + unrar_folder)
    logger.fdebug(module + ' Running the ComicTagger Add-on for Mylar')

    if os.path.exists( comicpath ):
        shutil.rmtree( comicpath )

    logger.fdebug(module + ' Attempting to create directory @: ' + str(comicpath))
    try:
        os.makedirs(comicpath)
    except OSError:
        raise

    logger.fdebug(module + ' Created directory @ : ' + str(comicpath))
    logger.fdebug(module + ' Filename is : ' + str(filename))
    if filename is None:
        filename_list = glob.glob( os.path.join( downloadpath, "*.cbz" ) )
        filename_list.extend( glob.glob( os.path.join( downloadpath, "*.cbr" ) ) )
        fcount = 1
        for f in filename_list:
            if fcount > 1: 
                logger.fdebug(module + ' More than one cbr/cbz within path, performing Post-Process on first file detected: ' + f)
                break
            shutil.move( f, comicpath )
            filename = f  #just the filename itself
            fcount+=1
    else:
        # if the filename is identical to the parent folder, the entire subfolder gets copied since it's the first match, instead of just the file
        shutil.move( filename, comicpath )

    try:
        filename = os.path.split(filename)[1]   # just the filename itself
    except:
        logger.warn('Unable to detect filename within directory - I am aborting the tagging. You best check things out.')
        return "fail"
    #print comicpath
    #print os.path.join( comicpath, filename )
    if filename.endswith('.cbr'):
        f = os.path.join( comicpath, filename )
        if zipfile.is_zipfile( f ):
            logger.fdebug(module + ' zipfile detected')
            base = os.path.splitext( f )[0]
            shutil.move( f, base + ".cbz" )
            logger.fdebug(module + ' {0}: renaming {1} to be a cbz'.format( scriptname, os.path.basename( f ) ))

    if file_extension_fixing:
        if filename.endswith('.cbz'):
            logger.info(module + ' Filename detected as a .cbz file.')
            f = os.path.join( comicpath, filename )
            logger.fdebug(module + ' filename : ' + f)

            if os.path.isfile( f ):
                try:
                    rar_test_cmd_output = "is not RAR archive" #default, in case of error
                    rar_test_cmd_output = subprocess.check_output( [ unrar_cmd, "t", f ] )
                except:
                    logger.fdebug(module + ' This is a zipfile. Unable to test rar.')

                if not "is not RAR archive" in rar_test_cmd_output:
                    base = os.path.splitext( f )[0]
                    shutil.move( f, base + ".cbr" )
                    logger.fdebug(module + ' {0}: renaming {1} to be a cbr'.format( scriptname, os.path.basename( f ) ))
                else:
                    try:
                        with open(f): pass
                    except:
                        logger.warn(module + ' No zip file present')
                        return "fail"


                    base = os.path.join(re.sub(issueid, '', comicpath), filename) #extension is already .cbz
                    logger.fdebug(module + ' Base set to : ' + base)
                    logger.fdebug(module + ' Moving : ' + f + ' - to - ' + base)
                    shutil.move( f, base)
                    try:
                        with open(base):
                            logger.fdebug(module + ' Verified file exists in location: ' + base)
                        removetemp = True
                    except:
                        logger.fdebug(module + ' Cannot verify file exist in location: ' + base)
                        removetemp = False

                    if removetemp == True:
                        if comicpath != downloadpath:
                            shutil.rmtree( comicpath )
                            logger.fdebug(module + ' Successfully removed temporary directory: ' + comicpath)
                        else:
                            loggger.fdebug(module + ' Unable to remove temporary directory since it is identical to the download location : ' + comicpath)
                    logger.fdebug(module + ' new filename : ' + base)
                    nfilename = base

    # Now rename all CBR files to RAR
    if filename.endswith('.cbr'):
        #logger.fdebug('renaming .cbr to .rar')
        f = os.path.join( comicpath, filename)
        base = os.path.splitext( f )[0]
        baserar = base + ".rar"
        shutil.move( f, baserar )

        ## Changes any cbr files to cbz files for insertion of metadata ##
        if file_conversion:
            f = os.path.join( comicpath, filename )
            logger.fdebug(module + ' {0}: converting {1} to be zip format'.format( scriptname, os.path.basename( f ) ))
            basename = os.path.splitext( f )[0]
            zipname = basename + ".cbz"

            # Move into the folder where we will be unrar-ing things
            os.makedirs( unrar_folder )
            os.chdir( unrar_folder )

            # Extract and zip up
            logger.fdebug(module + ' {0}: Comicpath is ' + baserar) #os.path.join(comicpath,basename))
            logger.fdebug(module + ' {0}: Unrar is ' + unrar_folder )
            try:
                #subprocess.Popen( [ unrar_cmd, "x", os.path.join(comicpath,basename) ] ).communicate()
                output = subprocess.check_output( [ unrar_cmd, 'x', baserar ] )
            except CalledProcessError as e:
                if e.returncode == 3:
                    logger.warn(module + ' [Unrar Error 3] - Broken Archive.')
                elif e.returncode == 1:
                    logger.warn(module + ' [Unrar Error 1] - No files to extract.')
                logger.warn(module + ' Marking this as an incomplete download.')
                return "unrar error"

            shutil.make_archive( basename, "zip", unrar_folder )

            # get out of unrar folder and clean up
            os.chdir( comicpath )
            shutil.rmtree( unrar_folder )

            ## Changes zip to cbz
   
            f = os.path.join( comicpath, os.path.splitext(filename)[0] + ".zip" )
            #print "zipfile" + f
            try:
                with open(f): pass
            except:
                logger.warn(module + ' No zip file present:' + f)
                return "fail"         
            base = os.path.splitext( f )[0]
            shutil.move( f, base + ".cbz" )
            nfilename = base + ".cbz"
    #else:
    #    logger.fdebug(module + ' Filename:' + filename)       
    #    nfilename = filename

    #if os.path.isfile( nfilename ):
    #    logger.fdebug(module + ' File exists in given location already : ' + nfilename)
    #    file_dir, file_n = os.path.split(nfilename)
    #else:
    #    #remove the IssueID from the path
    #    file_dir = re.sub(issueid, '', comicpath)
    #    file_n = os.path.split(nfilename)[1]
    if manual is None:
        file_dir = downloadpath
    else:
        file_dir = re.sub(issueid, '', comicpath)

    try:
        file_n = os.path.split(nfilename)[1]
    except:
        logger.error(module + ' unable to retrieve filename properly. Check your logs as there is probably an error or misconfiguration indicated (such as unable to locate unrar or configparser)')
        return "fail"

    logger.fdebug(module + ' Converted directory: ' + str(file_dir))
    logger.fdebug(module + ' Converted filename: ' + str(file_n))
    logger.fdebug(module + ' Destination path: ' + os.path.join(file_dir,file_n))  #dirName,file_n))
    logger.fdebug(module + ' dirName: ' + dirName)
    logger.fdebug(module + ' absDirName: ' + os.path.abspath(dirName))

    ##set up default comictagger options here.
    tagoptions = [ "-s", "--verbose" ]

    ## check comictagger version - less than 1.15.beta - take your chances.
    if sys_type == 'windows':
        ctversion = subprocess.check_output( [ comictagger_cmd, "--version" ] )
    else:
        ctversion = subprocess.check_output( [ sys.executable, comictagger_cmd, "--version" ] )

    ctend = ctversion.find(':')
    ctcheck = re.sub("[^0-9]", "", ctversion[:ctend])
    ctcheck = re.sub('\.', '', ctcheck).strip()
    if int(ctcheck) >= int('1115'): #(v1.1.15)
        if mylar.COMICVINE_API == mylar.DEFAULT_CVAPI:
            logger.fdebug(module + ' ' + ctversion[:ctend] + ' being used - no personal ComicVine API Key supplied. Take your chances.')
            use_cvapi = "False"
        else:
            logger.fdebug(module + ' ' + ctversion[:ctend] + ' being used - using personal ComicVine API key supplied via mylar.')
            use_cvapi = "True"
            tagoptions.extend( [ "--cv-api-key", mylar.COMICVINE_API ] )
    else:
        logger.fdebug(module + ' ' + ctversion[:ctend] + ' being used - personal ComicVine API key not supported in this version. Good luck.')
        use_cvapi = "False"

    i = 1
    tagcnt = 0

    if mylar.CT_TAG_CR:
        tagcnt = 1
        logger.fdebug(module + ' CR Tagging enabled.')

    if mylar.CT_TAG_CBL:
        if not mylar.CT_TAG_CR: i = 2  #set the tag to start at cbl and end without doing another tagging.
        tagcnt = 2
        logger.fdebug(module + ' CBL Tagging enabled.')

    if tagcnt == 0:
        logger.warn(module + ' You have metatagging enabled, but you have not selected the type(s) of metadata to write. Please fix and re-run manually')
        return "fail"
    
    #if it's a cbz file - check if no-overwrite existing tags is enabled / disabled in config.
    if nfilename.endswith('.cbz'):
        if mylar.CT_CBZ_OVERWRITE:
            logger.fdebug(module + ' Will modify existing tag blocks even if it exists.')
        else:
            logger.fdebug(module + ' Will NOT modify existing tag blocks even if they exist already.')
            tagoptions.extend( [ "--nooverwrite" ] )

    if issueid is None:
        tagoptions.extend( [ "-f", "-o" ] )
    else:
        tagoptions.extend( [ "-o", "--id", issueid ] )

    original_tagoptions = tagoptions
    og_tagtype = None

    while ( i <= tagcnt ):
        if i == 1: 
            tagtype = 'cr'  # CR meta-tagging cycle.
            tagdisp = 'ComicRack tagging'
        elif i == 2: 
            tagtype = 'cbl'  #Cbl meta-tagging cycle
            tagdisp = 'Comicbooklover tagging'


        f_tagoptions = original_tagoptions

        if og_tagtype is not None: 
            for index, item in enumerate(f_tagoptions):
                if item == og_tagtype:
                    f_tagoptions[index] = tagtype
        else:
            f_tagoptions.extend( [ "--type", tagtype, nfilename ] )

        og_tagtype = tagtype

        logger.info(module + ' ' + tagdisp + ' meta-tagging processing started.')
 
        #CV API Check here.
        if mylar.CVAPI_COUNT == 0 or mylar.CVAPI_COUNT >= 200:
            cvapi_check()
        if sys_type == 'windows':
            currentScriptName = str(comictagger_cmd).decode("string_escape")
        else:
            currentScriptName = sys.executable + ' ' + str(comictagger_cmd).decode("string_escape")
        logger.fdebug(module + ' Enabling ComicTagger script: ' + str(currentScriptName) + ' with options: ' + str(f_tagoptions))
            # generate a safe command line string to execute the script and provide all the parameters
        script_cmd = shlex.split(currentScriptName, posix=False) + f_tagoptions

            # use subprocess to run the command and capture output
        logger.fdebug(module + ' Executing command: '+str(script_cmd))
        logger.fdebug(module + ' Absolute path to script: '+script_cmd[0])
        try:
            p = subprocess.Popen(script_cmd)
            out, err = p.communicate() #@UnusedVariable
            logger.fdebug(module + '[COMIC-TAGGER] : '+str(out))
            logger.info(module + '[COMIC-TAGGER] Successfully wrote ' + tagdisp)
        except OSError, e:
            logger.warn(module + '[COMIC-TAGGER] Unable to run comictagger with the options provided: ' + str(script_cmd))

        #increment CV API counter.
        mylar.CVAPI_COUNT +=1


        ## Tag each CBZ, and move it back to original directory ##
        #if use_cvapi == "True":
        #    if issueid is None:
        #        subprocess.Popen( [ comictagger_cmd, "-s", "-t", tagtype, "--cv-api-key", mylar.COMICVINE_API, "-f", "-o", "--verbose", "--nooverwrite", nfilename ] ).communicate()
        #    else:
        #        subprocess.Popen( [ comictagger_cmd, "-s", "-t", tagtype, "--cv-api-key", mylar.COMICVINE_API, "-o", "--id", issueid, "--verbose", nfilename ] ).communicate()
        #        logger.info(module + ' ' + tagdisp + ' meta-tagging complete')
        #    #increment CV API counter.
        #    mylar.CVAPI_COUNT +=1
        #else:
        #    if issueid is None:
        #        subprocess.Popen( [ comictagger_cmd, "-s", "-t", tagtype, "-f", "-o", "--verbose", "--nooverwrite", nfilename ] ).communicate()
        #    else:
        #        subprocess.Popen( [ comictagger_cmd, "-s", "-t", tagtype, "-o", "--id", issueid, "--verbose", "--nooverwrite", nfilename ] ).communicate()
        #    #increment CV API counter.
        #    mylar.CVAPI_COUNT +=1
        i+=1

    if os.path.exists(os.path.join(os.path.abspath(file_dir),file_n)): #(os.path.abspath(dirName),file_n)):
        logger.fdebug(module + ' Unable to move from temporary directory - file already exists in destination: ' + os.path.join(os.path.abspath(file_dir),file_n))
    else:
        try:
            shutil.move( os.path.join(comicpath, nfilename), os.path.join(os.path.abspath(file_dir),file_n)) #os.path.abspath(dirName),file_n))
            #shutil.move( nfilename, os.path.join(os.path.abspath(dirName),file_n))
            logger.fdebug(module + ' Sucessfully moved file from temporary path.')
        except:
            logger.error(module + ' Unable to move file from temporary path. Deletion of temporary path halted.')
            return os.path.join(comicpath, nfilename)

        i = 0

        os.chdir( mylar.PROG_DIR )

        while i < 10:
            try:
                logger.fdebug(module + ' Attempting to remove: ' + comicpath)
                shutil.rmtree( comicpath )
            except:
                time.sleep(.1)
            else:
                return os.path.join(os.path.abspath(file_dir), file_n) #dirName), file_n)
            i+=1

        logger.fdebug(module + ' Failed to remove temporary path : ' + str(comicpath))

    return os.path.join(os.path.abspath(file_dir),file_n) #dirName),file_n)

