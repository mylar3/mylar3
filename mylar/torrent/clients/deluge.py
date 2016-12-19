import os
import mylar
import base64
from mylar import logger, helpers

from deluge_client import DelugeRPCClient

class TorrentClient(object):
    def __init__(self):
        self.conn = None
		
    def connect(self, host, username, password):
        if self.conn is not None:
            return self.connect
	
        if not host:
            return False

        # Get port from the config
        host,portnr = host.split(':')


        #if username and password:
        logger.info('Connecting to ' + host + ':' + portnr + ' Username: ' + username + ' Password: ' + password )
        self.client = DelugeRPCClient(host,int(portnr),username,password)
        self.client.connect()
        
        logger.info('connected? ' + str(self.client.connected))
        
        return self.client
		
	
    def find_torrent(self, hash):
        #To be Added
        return False

    def get_torrent(self, torrent):
		# To be Added
		return False

    def start_torrent(self, torrent):
        return torrent.start()

    def stop_torrent(self, torrent):
        return torrent.stop()

    def load_torrent(self, filepath):
        logger.info('filepath to torrent file set to : ' + filepath)
        torrent_id = False
                
        if self.client.connected is True:
            logger.info('Trying to send to deluge now')
            # Open torrent to endcode
            
            torrentfile = open(filepath, 'rb')
            torrentcontent = torrentfile.read()
            torrentencode = base64.encodestring(torrentcontent)

            # Send to Deluge and return torrent_id 
            logger.info('FileName: ' + str(os.path.basename(filepath)))
            
            
            torrent_id = self.client.call('core.add_torrent_file', str(os.path.basename(filepath)), torrentencode, '')
            
            if not torrent_id:
                logger.error('Torrent not added')
                return False
            else:
                logger.info('TorrentID: ' + torrent_id)

            # If label enabled put label on torrent in Deluge
            logger.info('Label: ' + mylar.DELUGE_LABEL)
            if torrent_id and mylar.DELUGE_LABEL:
                logger.info ('Setting label to ' + mylar.DELUGE_LABEL)
                try:
                    self.client.call('label.set_torrent', torrent_id, mylar.DELUGE_LABEL)
                except:
                    #if label isn't set, let's try and create one.
                    try:
                        self.client.call('label.add', mylar.DELUGE_LABEL)
                        self.client.call('label.set_torrent', torrent_id, mylar.DELUGE_LABEL)
                    except:
                        logger.warn('Unable to set label - Either try to create it manually within Deluge, and/or ensure there are no spaces, capitalization or special characters in label')            
                        return False
                logger.info('Succesfully set label to ' + mylar.DELUGE_LABEL)
        return True


    def delete_torrent(self, torrent):
		# To be Added
		return False

        
