import mylar
from mylar import db, logger, helpers, updater
import os
import shutil


def movefiles(comicid, comlocation, ogcname, imported=None):
    myDB = db.DBConnection()
    logger.fdebug('comlocation is : ' + str(comlocation))
    logger.fdebug('original comicname is : ' + str(ogcname))
    impres = myDB.select("SELECT * from importresults WHERE ComicName=?", [ogcname])

    if impres is not None:
        #print ("preparing to move " + str(len(impres)) + " files into the right directory now.")
        for impr in impres:
            srcimp = impr['ComicLocation']
            orig_filename = impr['ComicFilename']
            orig_iss = impr['impID'].rfind('-')
            orig_iss = impr['impID'][orig_iss +1:]
            logger.fdebug("Issue :" + str(orig_iss))
            #before moving check to see if Rename to Mylar structure is enabled.
            if mylar.IMP_RENAME and mylar.FILE_FORMAT != '':
                logger.fdebug("Renaming files according to configuration details : " + str(mylar.FILE_FORMAT))
                renameit = helpers.rename_param(comicid, impr['ComicName'], orig_iss, orig_filename)
                nfilename = renameit['nfilename']
                dstimp = os.path.join(comlocation, nfilename)
            else:
                logger.fdebug("Renaming files not enabled, keeping original filename(s)")
                dstimp = os.path.join(comlocation, orig_filename)

            logger.info("moving " + str(srcimp) + " ... to " + str(dstimp))
            try:
                shutil.move(srcimp, dstimp)
            except (OSError, IOError):
                logger.error("Failed to move files - check directories and manually re-run.")
        logger.fdebug("all files moved.")
        #now that it's moved / renamed ... we remove it from importResults or mark as completed.

    results = myDB.select("SELECT * from importresults WHERE ComicName=?", [ogcname])
    if results is not None:
        for result in results:
            controlValue = {"impID":    result['impid']}
            newValue = {"Status":           "Imported"}
            myDB.upsert("importresults", newValue, controlValue)
    return

def archivefiles(comicid, ogdir, ogcname):
    myDB = db.DBConnection()
    # if move files isn't enabled, let's set all found comics to Archive status :)
    result = myDB.select("SELECT * FROM importresults WHERE ComicName=?", [ogcname])
    if result is None:
        pass
    else:
        scandir = []
        for res in result:
            if any([os.path.dirname(res['ComicLocation']) in x for x in scandir]):
                pass
            else:
                scandir.append(os.path.dirname(res['ComicLocation']))

        for sdir in scandir:
            logger.info('Updating issue information and setting status to Archived for location: ' + sdir)
            updater.forceRescan(comicid, archive=sdir) #send to rescanner with archive mode turned on

        logger.info('Now scanning in files.')
        updater.forceRescan(comicid)

    return
