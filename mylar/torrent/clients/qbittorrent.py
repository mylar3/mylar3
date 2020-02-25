import os
import mylar
from base64 import b16encode, b32decode
import re
import time
from mylar import logger, helpers

from qbittorrent import Client

class TorrentClient(object):
    def __init__(self):
        self.conn = None

    def connect(self, host, username, password, test=False):
        if self.conn is not None:
            return self.connect

        if not host:
            return {'status': False, 'error': 'host not specified'}

        try:
            self.client = Client(host)
        except Exception as e:
            logger.error('Could not create qBittorrent Object %s' % e)
            return {'status': False, 'error': e}
        else:
            try:
                self.client.login(username, password)
            except Exception as e:
                logger.error('Could not connect to qBittorrent: %s' % host)
                return {'status': False, 'error': e}
            else:
                if test is True:
                    version = self.client.qbittorrent_version
                    return {'status': True, 'version': version}
                else:
                    return self.client

    def find_torrent(self, hash):
        logger.debug('Finding Torrent hash: %s' % hash)
        torrent_info = self.get_torrent(hash)
        if torrent_info:
            return True
        else:
            return False

    def get_torrent(self, hash):
        logger.debug('Getting Torrent info hash: %s' % hash)
        try:
            torrent_info = self.client.get_torrent(hash)
        except Exception as e:
            logger.error('Could not get torrent info for %s' % hash)
            return False
        else:
            logger.info('Successfully located information for torrent')
            return torrent_info


    def load_torrent(self, filepath):

        if not filepath.startswith('magnet'):
            logger.info('filepath to torrent file set to : %s' % filepath)

        if self.client._is_authenticated is True:
            logger.info('Checking if Torrent Exists!')

            if filepath.startswith('magnet'):
                torrent_hash = re.findall("urn:btih:([\w]{32,40})", filepath)[0]
                if len(torrent_hash) == 32:
                    torrent_hash = b16encode(b32decode(torrent_hash)).lower()
                hash = torrent_hash.upper()
                logger.debug('Magnet (load_torrent) initiating')
            else:
                hash = self.get_the_hash(filepath)
                logger.debug('FileName (load_torrent): %s' % os.path.basename(filepath))

            logger.debug('Torrent Hash (load_torrent): "%s"' % hash)


            #Check if torrent already added
            if self.find_torrent(hash):
                logger.info('load_torrent: Torrent already exists!')
                return {'status': False, 'error': 'Torrent already exists'}
                #should set something here to denote that it's already loaded, and then the failed download checker not run so it doesn't download
                #multiple copies of the same issues that's already downloaded
            else:
                logger.info('Torrent not added yet, trying to add it now!')

                # Build an arg dict based on user prefs.
                addargs = {}
                if not any([mylar.CONFIG.QBITTORRENT_LABEL is None, mylar.CONFIG.QBITTORRENT_LABEL == '', mylar.CONFIG.QBITTORRENT_LABEL == 'None']):
                    addargs.update( { 'category': str(mylar.CONFIG.QBITTORRENT_LABEL) } )
                    logger.info('Setting download label to: %s' % mylar.CONFIG.QBITTORRENT_LABEL)
                if not any([mylar.CONFIG.QBITTORRENT_FOLDER is None, mylar.CONFIG.QBITTORRENT_FOLDER == '', mylar.CONFIG.QBITTORRENT_FOLDER == 'None']):
                    addargs.update( { 'savepath': str(mylar.CONFIG.QBITTORRENT_FOLDER) } )
                    logger.info('Forcing download location to: %s' % mylar.CONFIG.QBITTORRENT_FOLDER)
                if mylar.CONFIG.QBITTORRENT_LOADACTION == 'pause':
                    addargs.update( { 'paused': 'true' } )
                    logger.info('Attempting to add torrent in paused state')

                if filepath.startswith('magnet'):
                    try:
                        tid = self.client.download_from_link(filepath, **addargs)
                    except Exception as e:
                        logger.error('Torrent not added - %s' % e)
                        return {'status': False, 'error': e}
                    else:
                        logger.debug('Successfully submitted for add as a magnet. Verifying item is now on client.')
                else:
                    try:
                        torrent_content = open(filepath, 'rb')
                        tid = self.client.download_from_file(torrent_content, **addargs)
                    except Exception as e:
                        logger.error('Torrent not added - %s' % e)
                        return {'status': False, 'error': e}
                    else:
                        logger.debug('Successfully submitted for add via file. Verifying item is now on client.')

            if mylar.CONFIG.QBITTORRENT_LOADACTION == 'force_start':
                logger.info('Attempting to force start torrent')
                try:
                    startit = self.client.force_start(hash)
                    logger.info('startit returned: %s' % startit)
                except:
                    logger.warn('Unable to force start torrent - please check your client.')
            else:
                logger.info('Client default add action selected. Doing nothing.')

        try:
            time.sleep(5) # wait 5 in case it's not populated yet.
            tinfo = self.get_torrent(hash)
        except Exception as e:
            logger.warn('Torrent was not added! Please check logs')
            return {'status': False, 'error': e}
        else:
            logger.info('Torrent successfully added!')
            filelist = self.client.get_torrent_files(hash)
            #logger.info(filelist)
            if len(filelist) == 1:
                to_name = filelist[0]['name']
            else:
                to_name = tinfo['save_path']
 
            torrent_info = {'hash':             hash,
                            'files':            filelist,
                            'name':             to_name,
                            'total_filesize':   tinfo['total_size'],
                            'folder':           tinfo['save_path'],
                            'time_started':     tinfo['addition_date'],
                            'label':            mylar.CONFIG.QBITTORRENT_LABEL,
                            'status':           True}

            #logger.info(torrent_info)
            return torrent_info


    def get_the_hash(self, filepath):
        import hashlib
        import bencode

        # Open torrent file
        torrent_file = open(filepath, "rb")
        metainfo = bencode.decode(torrent_file.read())
        info = metainfo['info']
        thehash = hashlib.sha1(bencode.encode(info)).hexdigest().upper()
        return thehash

