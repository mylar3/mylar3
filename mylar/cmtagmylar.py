# This script was taken almost entirely from Manders2600 Script with the use of the awesome ComicTagger.
# modified very slightly so Mylar just passes it the IssueID for it to do it's magic.


import os
import sys
import glob
import platform
import shutil
import time
import zipfile
import subprocess
import mylar

from mylar import logger

def run (dirName, nzbName=None, issueid=None, manual=None, filename=None):
    logger.fdebug("dirName:" + dirName)

    ## Set the directory in which comictagger and other external commands are located - IMPORTANT - ##
    # ( User may have to modify, depending on their setup, but these are some guesses for now )

    if platform.system() == "Windows":
        (x, y) = platform.architecture()
        if x == "64bit":
            comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.exe')
        else:
            comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.exe')
        unrar_cmd =       "C:\Program Files\WinRAR\UnRAR.exe"

      # test for UnRAR
        if not os.path.isfile(unrar_cmd):
            unrar_cmd = "C:\Program Files (x86)\WinRAR\UnRAR.exe"
            if not os.path.isfile(unrar_cmd):
                logger.fdebug("Unable to locate UnRAR.exe - make sure it's installed.")
                logger.fdebug("Aborting meta-tagging.")
                return "fail"

    
    elif platform.system() == "Darwin":  #Mac OS X
        comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH)
        unrar_cmd =       "/usr/local/bin/unrar"
    
    else:
        #for the 'nix
        #check for dependencies here - configparser
        try:
            import configparser
        except ImportError:
            logger.fdebug("configparser not found on system. Please install manually in order to write metadata")
            logger.fdebug("continuing with PostProcessing, but I'm not using metadata.")
            return "fail"

        #set this to the lib path (ie. '<root of mylar>/lib')
        comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.py')
        unrar_cmd =       "/usr/bin/unrar"

#    if not os.path.exists( comictagger_cmd ):
#        print "ERROR:  can't find the ComicTagger program: {0}".format( comictagger_cmd )
#        print "        You probably need to edit this script!"
#        sys.exit( 1 )

    file_conversion = True
    file_extension_fixing = True
    if not os.path.exists( unrar_cmd ):
        logger.fdebug("WARNING:  can't find the unrar command.")
        logger.fdebug("File conversion and extension fixing not available")
        logger.fdebug("You probably need to edit this script, or install the missing tool, or both!")
        file_conversion = False
        file_extension_fixing = False


    ## Sets up other directories ##
    scriptname = os.path.basename( sys.argv[0] )
    downloadpath = os.path.abspath( dirName ) 
    sabnzbdscriptpath = os.path.dirname( sys.argv[0] )
    if manual is None:
        comicpath = os.path.join( downloadpath , "temp" )
    else:
        comicpath = os.path.join( downloadpath, issueid )
    unrar_folder = os.path.join( comicpath , "unrard" )

    logger.fdebug("---directory settings.")
    logger.fdebug("scriptname : " + scriptname)
    logger.fdebug("downloadpath : " + downloadpath)
    logger.fdebug("sabnzbdscriptpath : " + sabnzbdscriptpath)
    logger.fdebug("comicpath : " + comicpath)
    logger.fdebug("unrar_folder : " + unrar_folder)
    logger.fdebug("Running the Post-SabNZBd/Mylar script")

    if os.path.exists( comicpath ):
        shutil.rmtree( comicpath )
    os.makedirs( comicpath )

    # make a list of all CBR and CBZ files in downloadpath
    if filename is None:
        filename_list = glob.glob( os.path.join( downloadpath, "*.cbz" ) )
        filename_list.extend( glob.glob( os.path.join( downloadpath, "*.cbr" ) ) )

    ## Takes all .cbr and .cbz files and dumps them to processing directory ##
        for f in filename_list:
            shutil.move( f, comicpath)

        ## Changes filetype extensions when needed ##
        cbr_list = glob.glob( os.path.join( comicpath, "*.cbr" ) )
        for f in cbr_list:
            if zipfile.is_zipfile( f ):        
                base = os.path.splitext( f )[0]
                shutil.move( f, base + ".cbz" )
                logger.fdebug("{0}: renaming {1} to be a cbz".format( scriptname, os.path.basename( f ) ))

        if file_extension_fixing:
            cbz_list = glob.glob( os.path.join( comicpath, "*.cbz" ) )
            for f in cbz_list:
                try:
                    rar_test_cmd_output = "is not RAR archive" #default, in case of error
                    rar_test_cmd_output = subprocess.check_output( [ unrar_cmd, "t", f ] )
                except:
                    pass
                if not "is not RAR archive" in rar_test_cmd_output:
                    base = os.path.splitext( f )[0]
                    shutil.move( f, base + ".cbr" )
                    logger.fdebug("{0}: renaming {1} to be a cbr".format( scriptname, os.path.basename( f ) ))
  
        # Now rename all CBR files to RAR
        cbr_list = glob.glob( os.path.join( comicpath, "*.cbr" ) )
        for f in cbr_list:
            base = os.path.splitext( f )[0]
            shutil.move( f, base + ".rar" )

        ## Changes any cbr files to cbz files for insertion of metadata ##
        if file_conversion:
            rar_list = glob.glob( os.path.join( comicpath, "*.rar" ) )
            for f in rar_list:
                logger.fdebug("{0}: converting {1} to be zip format".format( scriptname, os.path.basename( f ) ))
                basename = os.path.splitext( f )[0]
                zipname = basename + ".cbz"

                # Move into the folder where we will be unrar-ing things
                os.makedirs( unrar_folder )
                os.chdir( unrar_folder )

                # Extract and zip up
                subprocess.Popen( [ unrar_cmd, "x", f ] ).communicate()
                shutil.make_archive( basename, "zip", unrar_folder )

                # get out of unrar folder and clean up
                os.chdir( comicpath )
                shutil.rmtree( unrar_folder )
      
            ## Changes zip to cbz
            zip_list = glob.glob( os.path.join( comicpath, "*.zip" ) )
            for f in zip_list:
                base = os.path.splitext( f )[0]
                shutil.move( f, base + ".cbz" )

        ## Tag each CBZ, and move it back to original directory ##
        cbz_list = glob.glob( os.path.join( comicpath, "*.cbz" ) )
        for f in cbz_list:
            if issueid is None:
                subprocess.Popen( [ comictagger_cmd, "-s", "-t", "cr", "-f", "-o", "--verbose", "--nooverwrite", f ] ).communicate()
                subprocess.Popen( [ comictagger_cmd, "-s", "-t", "cbl", "-f", "-o", "--verbose", "--nooverwrite", f ] ).communicate()
            else:
                subprocess.Popen( [ comictagger_cmd, "-s", "-t", "cr", "-o", "--id", issueid, "--verbose", "--nooverwrite", f ] ).communicate()
                subprocess.Popen( [ comictagger_cmd, "-s", "-t", "cbl", "-o", "--id", issueid, "--verbose", "--nooverwrite", f ] ).communicate()
            shutil.move( f, downloadpath )
            return

    else:
        shutil.move( filename, comicpath)

        filename = os.path.split(filename)[1]   # just the filename itself
        print comicpath
        print os.path.join( comicpath, filename )
        if filename.endswith('.cbr'):
            f = os.path.join( comicpath, filename )
            if zipfile.is_zipfile( f ):
                print "zipfile detected"
                base = os.path.splitext( f )[0]
                print base
                print f
                shutil.move( f, base + ".cbz" )
                logger.fdebug("{0}: renaming {1} to be a cbz".format( scriptname, os.path.basename( f ) ))

        if file_extension_fixing:
            if filename.endswith('.cbz'):
                f = os.path.join( comicpath, filename )

                if os.path.isfile( f ):
                    try:
                        rar_test_cmd_output = "is not RAR archive" #default, in case of error
                        rar_test_cmd_output = subprocess.check_output( [ unrar_cmd, "t", f ] )
                    except:
                        pass
                    if not "is not RAR archive" in rar_test_cmd_output:
                        base = os.path.splitext( f )[0]
                        shutil.move( f, base + ".cbr" )
                        logger.fdebug("{0}: renaming {1} to be a cbr".format( scriptname, os.path.basename( f ) ))

        # Now rename all CBR files to RAR
        if filename.endswith('.cbr'):
            f = os.path.join( comicpath, filename)
            base = os.path.splitext( f )[0]
            shutil.move( f, base + ".rar" )

        ## Changes any cbr files to cbz files for insertion of metadata ##
        if file_conversion:
            f = os.path.join( comicpath, filename )
            logger.fdebug("{0}: converting {1} to be zip format".format( scriptname, os.path.basename( f ) ))
            basename = os.path.splitext( f )[0]
            zipname = basename + ".cbz"

            # Move into the folder where we will be unrar-ing things
            os.makedirs( unrar_folder )
            os.chdir( unrar_folder )

            # Extract and zip up
            logger.fdebug("{0}: Comicpath is " + os.path.join(comicpath,basename))
            logger.fdebug("{0}: Unrar is " + unrar_folder )
            subprocess.Popen( [ unrar_cmd, "x", os.path.join(comicpath,basename) ] ).communicate()
            shutil.make_archive( basename, "zip", unrar_folder )

            # get out of unrar folder and clean up
            os.chdir( comicpath )
            shutil.rmtree( unrar_folder )

            ## Changes zip to cbz

            f = os.path.join( comicpath, os.path.splitext(filename)[0] + ".zip" )
            print "zipfile" + f
            try:
                with open(f): pass
            except:
                logger.fdebug("No zip file present")
                return "fail"         
            base = os.path.splitext( f )[0]
            shutil.move( f, base + ".cbz" )
            nfilename = base + ".cbz"
        else:
            nfilename = filename

        if os.path.isfile( nfilename):
            file_dir, file_n = os.path.split(nfilename)
        else:
            #remove the IssueID from the path
            file_dir = re.sub(issueid, '', comicpath)
            file_n = os.path.split(nfilename)[1]
        logger.fdebug("converted directory: " + str(file_dir))
        logger.fdebug("converted filename: " + str(file_n))
        logger.fdebug("destination path: " + os.path.join(dirName,file_n))
        logger.fdebug("dirName: " + dirName)
        logger.fdebug("absDirName: " + os.path.abspath(dirName))
        ## Tag each CBZ, and move it back to original directory ##
        if issueid is None:
            subprocess.Popen( [ comictagger_cmd, "-s", "-t", "cr", "-f", "-o", "--verbose", "--nooverwrite", nfilename ] ).communicate()
            subprocess.Popen( [ comictagger_cmd, "-s", "-t", "cbl", "-f", "-o", "--verbose", "--nooverwrite", nfilename ] ).communicate()
        else:
            subprocess.Popen( [ comictagger_cmd, "-s", "-t", "cr", "-o", "--id", issueid, "--verbose", "--nooverwrite", nfilename ] ).communicate()
            subprocess.Popen( [ comictagger_cmd, "-s", "-t", "cbl", "-o", "--id", issueid, "--verbose", "--nooverwrite", nfilename ] ).communicate()

        if os.path.exists(os.path.join(os.path.abspath(dirName),file_n)):
            logger.fdebug("Unable to move - file already exists.")
        else:
            shutil.move( nfilename, os.path.join(os.path.abspath(dirName),file_n))
            logger.fdebug("Sucessfully moved file from temporary path.")
            i = 0

            while i < 10:
                try:
                    shutil.rmtree( comicpath )
                except:
                    time.sleep(.1)
                else:
                    return os.path.join(os.path.abspath(dirName), file_n)
                i+=1

            logger.fdebug("Failed to remove temporary path : " + str(comicpath))

        return os.path.join(os.path.abspath(dirName),file_n)

    ## Clean up temp directory  ##

    #os.chdir( sabnzbdscriptpath )
    #shutil.rmtree( comicpath )

    ## Will Run Mylar Post=processing In Future ##
