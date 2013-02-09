import mylar
from mylar import db, logger
import os
import shutil


def movefiles(comlocation,ogcname,imported=None):
    myDB = db.DBConnection()
    print ("comlocation is : " + str(comlocation))
    print ("original comicname is : " + str(ogcname))
    impres = myDB.action("SELECT * from importresults WHERE ComicName=?", [ogcname])

    if impres is not None:
        #print ("preparing to move " + str(len(impres)) + " files into the right directory now.")
        for impr in impres:
            srcimp = impr['ComicLocation']
            dstimp = os.path.join(comlocation, impr['ComicFilename'])
            logger.info("moving " + str(srcimp) + " ... to " + str(dstimp))
            try:
                shutil.move(srcimp, dstimp)
            except (OSError, IOError):
                logger.error("Failed to move files - check directories and manually re-run.")
        #print("files moved.")
    #now that it's moved / renamed ... we remove it from importResults or mark as completed.
        results = myDB.action("SELECT * FROM importresults WHERE ComicName=?", [ogcname])
        if results is None: pass
        else:
            for result in results:
                controlValue = {"impID":    result['impid']}
                newValue = {"Status":           "Imported" }
                myDB.upsert("importresults", newValue, controlValue)
    return
