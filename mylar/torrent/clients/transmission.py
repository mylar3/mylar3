import os
import mylar
from mylar import logger
from transmissionrpc import Client


class TorrentClient(object):
    def __init__(self):
        self.conn = None

    def connect(self, host, username, password):
        if self.conn is not None:
            return self.conn

        if not host:
            return False
        try:
            if username and password:
                self.conn = Client(
                    host,
                    user=username,
                    password=password
                )
            else:
                self.conn = Client(host)
        except:
            logger.error('Could not connect to %h' % host)
            return False

        return self.conn

    def find_torrent(self, hash):
        try:
            return self.conn.get_torrent(hash)
        except KeyError:
            logger.error('torrent %s does not exist')
            return False

    def get_torrent(self, torrent):
        torrent = self.conn.get_torrent(torrent.hashString)
        torrent_files = []
        torrent_directory = os.path.normpath(torrent.downloadDir)

        for f in torrent.files().values():
            if not os.path.normpath(f['name']).startswith(torrent_directory):
                file_path = os.path.join(torrent_directory,
                                         f['name'].lstrip('/'))
            else:
                file_path = f['name']

            torrent_files.append(file_path)

        torrent_info = {
            'hash': torrent.hashString,
            'name': torrent.name,
            'folder': torrent.downloadDir,
            'completed': torrent.progress == 100,
            'label': 'None', ## labels not supported in transmission - for when it's in transmission
            'files': torrent_files,
            'upload_total': torrent.uploadedEver,
            'download_total': torrent.downloadedEver,
            'ratio': torrent.ratio,
            'total_filesize': torrent.sizeWhenDone,
            'time_started': torrent.date_started
        }
        logger.debug(torrent_info)
        return torrent_info if torrent_info else False

    def start_torrent(self, torrent):
        return torrent.start()

    def stop_torrent(self, torrent):
        return torrent.stop()

    def load_torrent(self, filepath):
        if any([mylar.CONFIG.TRANSMISSION_DIRECTORY is None, mylar.CONFIG.TRANSMISSION_DIRECTORY == '', mylar.CONFIG.TRANSMISSION_DIRECTORY == 'None']):
            down_dir = mylar.CONFIG.CHECK_FOLDER
        else:
            down_dir = mylar.CONFIG.TRANSMISSION_DIRECTORY
        if filepath.startswith('magnet'):
            torrent = self.conn.add_torrent('%s' % filepath,
                                            download_dir=down_dir)
        else:
            torrent = self.conn.add_torrent('file://%s' % filepath,
                                            download_dir=down_dir)

        torrent.start()
        return self.get_torrent(torrent)

    def delete_torrent(self, torrent):
        deleted = []
        files = torrent.files()
        for file_item in files.values():
            file_path = os.path.join(torrent.downloadDir,
                                     file_item['name'])
            deleted.append(file_path)

        if len(files) > 1:
            torrent_path = os.path.join(torrent.downloadDir, torrent.name)
            for path, _, _ in os.walk(torrent_path, topdown=False):
                deleted.append(path)

        if self.conn.remove_torrent(torrent.hashString, delete_data=True):
            return deleted
        else:
            logger.error('Unable to delete %s' % torrent.name)
            return []
