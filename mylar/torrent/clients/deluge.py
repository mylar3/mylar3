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
        # logger.info('Connecting to ' + host + ':' + portnr + ' Username: ' + username + ' Password: ' + password )
        try:
            self.client = DelugeRPCClient(host,int(portnr),username,password)
        except Exception as e:
            logger.error('Could not create DelugeRPCClient Object' + e)
            return False
        else:
            try:
                self.client.connect()
            except Exception as e:
                logger.error('Could not connect to Deluge ' + host)
            else:
                return self.client
	
    def find_torrent(self, hash):
        logger.debug('Finding Torrent hash: ' + hash)
        torrent_info = self.get_torrent(hash)
        if torrent_info:
            return True
        else:
            return False

    def get_torrent(self, hash):
        logger.debug('Getting Torrent info from hash: ' + hash)
        try:
            torrent_info = self.client.call('core.get_torrent_status', hash, '')
        except Exception as e:
            logger.error('Could not get torrent info for ' + hash)
            return False
        else:
            if torrent_info is None:
                torrent_info = False
            return torrent_info


    def start_torrent(self, hash):
        try:
            self.find_torrent(hash)
        except Exception as e:
            return False
        else:
            try:
                self.client.call('core.resume_torrent', hash)
            except Exception as e:
                logger.error('Torrent failed to start ' + e)
            else:
                logger.info('Torrent ' + hash + ' was started')
                return True

    def stop_torrent(self, hash):
        try:
            self.client.find_torrent(hash)
        except Exception as e:
            logger.error('Torrent Not Found')
            return False
        else:
            try:
                self.client.call('core.pause_torrent', hash)
            except Exception as e:
                logger.error('Torrent failed to be stopped: ' + e)
                return False
            else:
                logger.info('Torrent ' + hash + ' was stopped')
                return True
        

    def load_torrent(self, filepath):
        
        logger.info('filepath to torrent file set to : ' + filepath)
        torrent_id = False
                
        if self.client.connected is True:
            logger.info('Checking if Torrent Exists!')
            
            if not filepath.startswith('magnet'):
                torrentcontent = open(filepath, 'rb').read()
                hash = str.lower(self.get_the_hash(filepath)) # Deluge expects a lower case hash

                logger.debug('Torrent Hash (load_torrent): "' + hash + '"')
                logger.debug('FileName (load_torrent): ' + str(os.path.basename(filepath)))


                #Check if torrent already added
                if self.find_torrent(str.lower(hash)):
                    logger.info('load_torrent: Torrent already exists!')
                    #should set something here to denote that it's already loaded, and then the failed download checker not run so it doesn't download
                    #multiple copies of the same issues that's already downloaded
                else:
                    logger.info('Torrent not added yet, trying to add it now!')
                    try:
                        torrent_id = self.client.call('core.add_torrent_file', str(os.path.basename(filepath)), base64.encodestring(torrentcontent), '')
                    except Exception as e:
                        logger.debug('Torrent not added')
                        return False
            else:
                try:
                    torrent_id = self.client.call('core.add_torrent_magnet', str(filepath), {})
                except Exception as e:
                    logger.debug('Torrent not added')
                    return False

            # If label enabled put label on torrent in Deluge
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
                    else:
                        logger.info('Succesfully set label to ' + mylar.DELUGE_LABEL)

        try:
            torrent_info = self.get_torrent(torrent_id)
            logger.info('Double checking that the torrent was added.')
        except Exception as e:
            logger.warn('Torrent was not added! Please check logs')
            return False
        else:
            logger.info('Torrent successfully added!')
            return {'hash':             torrent_info['hash'],
                    'label':            mylar.DELUGE_LABEL,
                    'folder':           torrent_info['save_path'],
                    'total_filesize':   torrent_info['total_size'],
                    'name':             torrent_info['name'],
                    'files':            torrent_info['files'],
                    'time_started':     torrent_info['active_time'],
                    'completed':        torrent_info['is_finished']}


    def delete_torrent(self, hash, removeData=False):
        try:
            self.client.find_torrent(hash)
        except Exception as e:
            logger.error('Torrent ' + hash + ' does not exist')
            return False
        else:
            try:
                self.client.call('core.remote_torrent', hash, removeData)
            except Exception as e:
                logger.error('Unable to delete torrent ' + hash)
                return False
            else:
                logger.info('Torrent deleted ' + hash)
                return True


    def get_the_hash(self, filepath):
        import hashlib, StringIO
        import bencode

        # Open torrent file
        torrent_file = open(filepath, "rb")
        metainfo = bencode.decode(torrent_file.read())
        info = metainfo['info']
        thehash = hashlib.sha1(bencode.encode(info)).hexdigest().upper()
        logger.debug('Hash: ' + thehash)
        return thehash

