import os
import mylar
import base64
import time
from mylar import logger, helpers

from lib.qbittorrent import client

class TorrentClient(object):
    def __init__(self):
        self.conn = None
		
    def connect(self, host, username, password):
        if self.conn is not None:
            return self.connect
	
        if not host:
            return False

        try:
            logger.info(host)
            self.client = client.Client(host)
        except Exception as e:
            logger.error('Could not create qBittorrent Object' + str(e))
            return False
        else:
            try:
                self.client.login(username, password)
            except Exception as e:
                logger.error('Could not connect to qBittorrent ' + host)
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
        logger.debug('Getting Torrent info hash: ' + hash)
        try:
            torrent_info = self.client.get_torrent(hash)
        except Exception as e:
            logger.error('Could not get torrent info for ' + hash)
            return False
        else:
            logger.info('Successfully located information for torrent')
            return torrent_info


    def load_torrent(self, filepath):
        
        logger.info('filepath to torrent file set to : ' + filepath)
                
        if self.client._is_authenticated is True:
            logger.info('Checking if Torrent Exists!')
            
            hash = self.get_the_hash(filepath)

            logger.debug('Torrent Hash (load_torrent): "' + hash + '"')
            logger.debug('FileName (load_torrent): ' + str(os.path.basename(filepath)))


            #Check if torrent already added
            if self.find_torrent(hash):
                logger.info('load_torrent: Torrent already exists!')
                return False
                #should set something here to denote that it's already loaded, and then the failed download checker not run so it doesn't download
                #multiple copies of the same issues that's already downloaded
            else:
                logger.info('Torrent not added yet, trying to add it now!')
                try:
                    torrent_content = open(filepath, 'rb')
                    tid = self.client.download_from_file(torrent_content, label=mylar.QBITTORRENT_LABEL)
                except Exception as e:
                    logger.debug('Torrent not added')
                    return False
                else:
                    logger.debug('Successfully submitted for add. Verifying item is now on client.')

            if mylar.QBITTORRENT_STARTONLOAD:
                logger.info('attempting to start')
                startit = self.client.force_start(hash)
                logger.info('startit returned:' + str(startit))
            else:
                logger.info('attempting to pause torrent incase it starts')
                try:
                    startit = self.client.pause(hash)
                    logger.info('startit paused:' + str(startit))
                except:
                    logger.warn('Unable to pause torrent - possibly already paused?')

        try:
            time.sleep(5) # wait 5 in case it's not populated yet.
            tinfo = self.get_torrent(hash)
        except Exception as e:
            logger.warn('Torrent was not added! Please check logs')
            return False
        else:
            torrent_info = []
            logger.info('Torrent successfully added!')
            torrent_info['hash'] = hash
            filelist = self.client.get_torrent_files(hash)
            if len(filelist) == 1:
                torrent_info['name'] = filelist['name']
            else:
                torrent_info['name'] = tinfo['save_path']
            torrent_info['total_filesize'] = tinfo['total_size']
            torrent_info['folder'] = tinfo['save_path']
            torrent_info['files'] = filelist
            torrent_info['time_started'] = tinfo['addition_date']
            torrent_info['label'] = mylar.QBITTORRENT_LABEL
            return torrent_info


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

