import mylar
from mylar import db, logger, helpers, updater, filechecker
import os
import shutil
import ast

def movefiles(comicid, comlocation, imported):
    #comlocation is destination
    #comicid is used for rename
    files_moved = []
    try:
        imported = ast.literal_eval(imported)
    except ValueError:
        pass

    myDB = db.DBConnection()

    logger.fdebug('comlocation is : ' + comlocation)
    logger.fdebug('original comicname is : ' + imported['ComicName'])

    impres = imported['filelisting']

    if impres is not None:
        if all([mylar.CONFIG.CREATE_FOLDERS is False, not os.path.isdir(comlocation)]):
            checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True)
            if not checkdirectory:
                logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                return

        for impr in impres:
            rename_file = True
            srcimp = impr['comiclocation']
            orig_filename = impr['comicfilename']
            #before moving check to see if Rename to Mylar structure is enabled.
            if mylar.CONFIG.IMP_RENAME and mylar.CONFIG.FILE_FORMAT != '':
                logger.fdebug("Renaming files according to configuration details : " + str(mylar.CONFIG.FILE_FORMAT))
                logger.fdebug(f"impr: {impr}")
                logger.fdebug(f"comicid: {comicid}")
                logger.fdebug(f"imported['ComicName']: {imported['ComicName']}")
                logger.fdebug(f"impr['issuenumber']: {impr['issuenumber']}")
                logger.fdebug(f"orig_filename: {orig_filename}")
                if impr['issuenumber'] is None:
                    logger.fdebug(f"Issue number is not known, trying to use the ComicID to see if single issue.")
                    try:
                        db_query = myDB.selectone('SELECT Total FROM comics WHERE ComicID=?', [comicid]).fetchone()
                        if db_query[0] == 1:
                            impr['issuenumber'] = 1
                        else:
                            logger.fdebug(f"Issue number is not known, Cannot rename.")
                            rename_file = False
                    except:
                        logger.fdebug(f"Issue number is not known, and could not be learned from the ComicID via the DB.")
                        rename_file = False
                if rename_file:
                    logger.info("===============================================")
                    logger.info(f"comicid: {comicid}")
                    logger.info(f"imported['ComicName']: {imported['ComicName']}")
                    logger.info(f"impr['issuenumber']: {impr['issuenumber']}")
                    logger.info(f"orig_filename: {orig_filename}")
                    renameit = helpers.rename_param(comicid, imported['ComicName'], impr['issuenumber'], orig_filename)
                    logger.fdebug(f"renameit contains: {renameit}")
                    if renameit:
                        nfilename = renameit['nfilename']
                        dstimp = os.path.join(comlocation, nfilename)
                    else:
                        rename_file = False
            else:
                logger.fdebug("Renaming files not enabled, keeping original filename(s)")
                dstimp = os.path.join(comlocation, orig_filename)
            if rename_file:
                try:
                    logger.info("moving " + srcimp + " ... to " + dstimp)
                    shutil.move(srcimp, dstimp)
                    files_moved.append({'srid':       imported['srid'],
                                        'filename':   impr['comicfilename'],
                                        'import_id':  impr['import_id']})
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
    try:
        imported = ast.literal_eval(imported)
    except Exception as e:
        logger.warn('[%s] Error encountered converting import data' % e)

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
