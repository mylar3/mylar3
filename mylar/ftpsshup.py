#!/usr/local/bin/python

import os
import time

import mylar
from mylar import logger

def putfile(localpath, file):    #localpath=full path to .torrent (including filename), file=filename of torrent

    try:
        import paramiko
    except ImportError:
        logger.fdebug('paramiko not found on system. Please install manually in order to use seedbox option')
        logger.fdebug('get it at https://github.com/paramiko/paramiko')
        logger.fdebug('to install: python setup.py install')
        logger.fdebug('aborting send.')
        return "fail"

    host = mylar.CONFIG.SEEDBOX_HOST
    port = int(mylar.CONFIG.SEEDBOX_PORT)   #this is usually 22
    transport = paramiko.Transport((host, port))

    logger.fdebug('Sending file: ' + str(file))
    logger.fdebug('destination: ' + str(host))
    logger.fdebug('Using SSH port : ' + str(port))
    password = mylar.CONFIG.SEEDBOX_PASS
    username = mylar.CONFIG.SEEDBOX_USER
    transport.connect(username = username, password = password)

    sftp = paramiko.SFTPClient.from_transport(transport)

    import sys
    if file[-7:] != "torrent":
        file += ".torrent"
    rempath = os.path.join(mylar.CONFIG.SEEDBOX_WATCHDIR, file) #this will default to the OS running mylar for slashes.
    logger.fdebug('remote path set to ' + str(rempath))
    logger.fdebug('local path set to ' + str(localpath))

    if not os.path.exists(localpath):
        logger.fdebug('file has not finished writing yet - pausing for 5s to allow for completion.')
        time.sleep(5)
        if not localpath.exists():
            logger.fdebug('Skipping file at this time.')
            return "fail"

    sendcheck = False

    while sendcheck == False:
        try:
            sftp.put(localpath, rempath)
            sendcheck = True
        except Exception, e:
            logger.fdebug('ERROR Sending torrent to seedbox *** Caught exception: %s: %s' % (e.__class__, e))
            logger.fdebug('Forcibly closing connection and attempting to reconnect')
            sftp.close()
            transport.close()
            #reload the transport here cause it locked up previously.
            transport = paramiko.Transport((host, port))
            transport.connect(username = username, password = password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            logger.fdebug('sucessfully reconnected via sftp - attempting to resend.')
            #return "fail"

    sftp.close()
    transport.close()
    logger.fdebug('Upload complete to seedbox.')
    return "pass"

def sendfiles(filelist):

    try:
        import paramiko
    except ImportError:
        logger.fdebug('paramiko not found on system. Please install manually in order to use seedbox option')
        logger.fdebug('get it at https://github.com/paramiko/paramiko')
        logger.fdebug('to install: python setup.py install')
        logger.fdebug('aborting send.')
        return

    fhost = mylar.CONFIG.TAB_HOST.find(':')
    host = mylar.CONFIG.TAB_HOST[:fhost]
    port = int(mylar.CONFIG.TAB_HOST[fhost +1:])

    logger.fdebug('Destination: ' + host)
    logger.fdebug('Using SSH port : ' + str(port))

    transport = paramiko.Transport((host, port))

    password = mylar.CONFIG.TAB_PASS
    username = mylar.CONFIG.TAB_USER
    transport.connect(username = username, password = password)

    sftp = paramiko.SFTPClient.from_transport(transport)

    remotepath = mylar.CONFIG.TAB_DIRECTORY
    logger.fdebug('remote path set to ' + remotepath)

    if len(filelist) > 0:
        logger.info('Initiating send for ' + str(len(filelist)) + ' files...')
        return sendtohome(sftp, remotepath, filelist, transport)


def sendtohome(sftp, remotepath, filelist, transport):
    fhost = mylar.CONFIG.TAB_HOST.find(':')
    host = mylar.CONFIG.TAB_HOST[:fhost]
    port = int(mylar.CONFIG.TAB_HOST[fhost +1:])

    successlist = []
    filestotal = len(filelist)

    for files in filelist:
        tempfile = files['filename']
        issid = files['issueid']
        logger.fdebug('Checking filename for problematic characters: ' + tempfile)
        #we need to make the required directory(ies)/subdirectories before the get will work.
        if u'\xb4' in files['filename']:
            # right quotation
            logger.fdebug('detected abnormal character in filename')
            filename = tempfile.replace('0xb4', '\'')
        if u'\xbd' in files['filename']:
            # 1/2 character
            filename = tempfile.replace('0xbd', 'half')
        if u'\uff1a' in files['filename']:
            #some unknown character
            filename = tempfile.replace('\0ff1a', '-')

        #now we encode the structure to ascii so we can write directories/filenames without error.
        filename = tempfile.encode('ascii', 'ignore')

        remdir = remotepath

        if mylar.CONFIG.MAINTAINSERIESFOLDER == 1:
            # Get folder path of issue
            comicdir = os.path.split(files['filepath'])[0]
            # Isolate comic folder name
            comicdir = os.path.split(comicdir)[1]
            logger.info('Checking for Comic Folder: ' + comicdir)
            chkdir = os.path.join(remdir, comicdir)
            try:
                sftp.stat(chkdir)
            except IOError, e:
                logger.info('Comic Folder does not Exist, creating ' + chkdir )
                try:
                    sftp.mkdir(chkdir)
                except :
                    # Fallback to default behavior
                    logger.info('Could not create Comic Folder, adding to device root')
                else :
                    remdir = chkdir
            else :
                remdir = chkdir

        localsend = files['filepath']
        logger.info('Sending : ' + localsend)
        remotesend = os.path.join(remdir, filename)
        logger.info('To : ' + remotesend)

        try:
            sftp.stat(remotesend)
        except IOError, e:
            if e[0] == 2:
                filechk = False
        else:
            filechk = True

        if not filechk:
            sendcheck = False
            count = 1

            while sendcheck == False:
                try:
                    sftp.put(localsend, remotesend)#, callback=printTotals)
                    sendcheck = True
                except Exception, e:
                    logger.info('Attempt #' + str(count) + ': ERROR Sending issue to seedbox *** Caught exception: %s: %s' % (e.__class__, e))
                    logger.info('Forcibly closing connection and attempting to reconnect')
                    sftp.close()
                    transport.close()
                    #reload the transport here cause it locked up previously.
                    transport = paramiko.Transport((host, port))
                    transport.connect(username=mylar.CONFIG.TAB_USER, password=mylar.CONFIG.TAB_PASS)
                    sftp = paramiko.SFTPClient.from_transport(transport)
                    count+=1
                    if count > 5:
                        break

            if count > 5:
                logger.info('Unable to send - tried 5 times and failed. Aborting entire process.')
                break

        else:
            logger.info('file already exists - checking if complete or not.')
            filesize = sftp.stat(remotesend).st_size
            if not filesize == os.path.getsize(files['filepath']):
                logger.info('file not complete - attempting to resend')
                sendcheck = False
                count = 1

                while sendcheck == False:
                    try:
                        sftp.put(localsend, remotesend)
                        sendcheck = True
                    except Exception, e:
                        logger.info('Attempt #' + str(count) + ': ERROR Sending issue to seedbox *** Caught exception: %s: %s' % (e.__class__, e))
                        logger.info('Forcibly closing connection and attempting to reconnect')
                        sftp.close()
                        transport.close()
                        #reload the transport here cause it locked up previously.
                        transport = paramiko.Transport((host, port))
                        transport.connect(username=mylar.CONFIG.TAB_USER, password=mylar.CONFIG.TAB_PASS)
                        sftp = paramiko.SFTPClient.from_transport(transport)
                        count+=1
                        if count > 5:
                            break

                if count > 5:
                    logger.info('Unable to send - tried 5 times and failed. Aborting entire process.')
                    break
            else:
               logger.info('file 100% complete according to byte comparison.')

        logger.info('Marking as being successfully Downloaded to 3rd party device (Queuing to change Read Status to Downloaded)')
        successlist.append({"issueid":  issid})

    sftp.close()
    transport.close()
    logger.fdebug('Upload of readlist complete.')
    return successlist

#def printTotals(transferred, toBeTransferred):
#    percent = transferred / toBeTransferred
#    logger.info("Transferred: " + str(transferred) + " Out of " + str(toBeTransferred))

#if __name__ == '__main__':
#    putfile(sys.argv[1])

