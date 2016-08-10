import mylar
from mylar import db, logger, helpers, updater
import os
import shutil
import ast

def movefiles(comicid, comlocation, imported):
    #comlocation is destination
    #comicid is used for rename
    files_moved = []
    imported = ast.literal_eval(imported)

    myDB = db.DBConnection()

    logger.fdebug('comlocation is : ' + comlocation)
    logger.fdebug('original comicname is : ' + imported['ComicName'])

    impres = imported['filelisting']

    if impres is not None:
        for impr in impres:
            srcimp = impr['comiclocation']
            orig_filename = impr['comicfilename']
            #before moving check to see if Rename to Mylar structure is enabled.
            if mylar.IMP_RENAME and mylar.FILE_FORMAT != '':
                logger.fdebug("Renaming files according to configuration details : " + str(mylar.FILE_FORMAT))
                renameit = helpers.rename_param(comicid, imported['ComicName'], impr['issuenumber'], orig_filename)
                nfilename = renameit['nfilename']
                dstimp = os.path.join(comlocation, nfilename)
            else:
                logger.fdebug("Renaming files not enabled, keeping original filename(s)")
                dstimp = os.path.join(comlocation, orig_filename)

            logger.info("moving " + srcimp + " ... to " + dstimp)
            try:
                shutil.move(srcimp, dstimp)
                files_moved.append({'srid':     imported['srid'],
                                    'filename': impr['comicfilename']})
            except (OSError, IOError):
                logger.error("Failed to move files - check directories and manually re-run.")

        logger.fdebug("all files moved.")
        #now that it's moved / renamed ... we remove it from importResults or mark as completed.

    if len(files_moved) > 0:
        logger.info('files_moved: ' + str(files_moved))
        for result in files_moved:
            try:
                res = result['import_id']
            except:
                #if it's an 'older' import that wasn't imported, just make it a basic match so things can move and update properly.
                controlValue = {"ComicFilename": result['filename'],
                                "SRID":          result['srid']}
                newValue = {"Status":            "Imported",
                            "ComicID":           comicid}
            else:                 
                controlValue = {"impID":         result['import_id'],
                                "ComicFilename": result['filename']}
                newValue = {"Status":            "Imported",
                            "SRID":              result['srid'],
                            "ComicID":           comicid}
            myDB.upsert("importresults", newValue, controlValue)
    return

def archivefiles(comicid, comlocation, imported):
    myDB = db.DBConnection()
    # if move files isn't enabled, let's set all found comics to Archive status :)
    imported = ast.literal_eval(imported)
    ComicName = imported['ComicName']
    impres = imported['filelisting']

    if impres is not None:
        scandir = []
        for impr in impres:
            srcimp = impr['comiclocation']
            orig_filename = impr['comicfilename']

            if not any([os.path.abspath(os.path.join(srcimp, os.pardir)) == x for x in scandir]):
                scandir.append(os.path.abspath(os.path.join(srcimp, os.pardir)))


        for sdir in scandir:
            logger.info('Updating issue information and setting status to Archived for location: ' + sdir)
            updater.forceRescan(comicid, archive=sdir) #send to rescanner with archive mode turned on

        logger.info('Now scanning in files.')
        updater.forceRescan(comicid)

        for result in impres:
            try:
                res = result['import_id']
            except:
                #if it's an 'older' import that wasn't imported, just make it a basic match so things can move and update properly.
                controlValue = {"ComicFilename": result['comicfilename'],
                                "SRID":          imported['srid']}
                newValue = {"Status":            "Imported",
                            "ComicID":           comicid}
            else:
                controlValue = {"impID":         result['import_id'],
                                "ComicFilename": result['comicfilename']}
                newValue = {"Status":            "Imported",
                            "SRID":              imported['srid'],
                            "ComicID":           comicid}
            myDB.upsert("importresults", newValue, controlValue)


    return
