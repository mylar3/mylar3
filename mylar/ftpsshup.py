#!/usr/local/bin/python

#import paramiko
import os

import mylar
from mylar import logger

def putfile(localpath,file):    #localpath=full path to .torrent (including filename), file=filename of torrent

    try:
        import paramiko
    except ImportError:
        logger.fdebug("paramiko not found on system. Please install manually in order to use seedbox option")
        logger.fdebug("get it at https://github.com/paramiko/paramiko")
        logger.fdebug("to install: python setup.py install")
        logger.fdebug("aborting send.")
        return "fail"

    host = mylar.SEEDBOX_HOST   
    port = int(mylar.SEEDBOX_PORT)   #this is usually 22
    transport = paramiko.Transport((host, port))

    logger.fdebug("Sending file: " + str(file))
    logger.fdebug("destination: " + str(host))
    logger.fdebug("Using SSH port : " + str(port))
    password = mylar.SEEDBOX_PASS
    username = mylar.SEEDBOX_USER
    transport.connect(username = username, password = password)

    sftp = paramiko.SFTPClient.from_transport(transport)

    import sys
    if file[-7:] != "torrent":
        file += ".torrent"
    rempath = os.path.join(mylar.SEEDBOX_WATCHDIR, file) #this will default to the OS running mylar for slashes.
    logger.fdebug("remote path set to " + str(rempath))
    logger.fdebug("local path set to " + str(localpath))
    sftp.put(localpath, rempath)

    sftp.close()
    transport.close()
    logger.fdebug("Upload complete to seedbox.")
    return "pass"

if __name__ == '__main__':
    putfile(sys.argv[1])

