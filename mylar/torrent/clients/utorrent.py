import os

from libs.utorrent.client import UTorrentClient

# Only compatible with uTorrent 3.0+

class TorrentClient(object):
    def __init__(self):
        self.conn = None

    def connect(self, host, username, password):
        if self.conn is not None:
            return self.conn

        if not host:
            return False

        if username and password:
            self.conn = UTorrentClient(
                host,
                username,
                password
            )
        else:
            self.conn = UTorrentClient(host)

        return self.conn

    def find_torrent(self, hash):
        try:
            torrent_list = self.conn.list()[1]

            for t in torrent_list['torrents']:
                if t[0] == hash:
                    torrent = t

        except Exception:
            raise

        return torrent if torrent else False

    def get_torrent(self, torrent):
        if not torrent[26]:
            raise Exception('Only compatible with uTorrent 3.0+')

        torrent_files = []
        torrent_completed = False
        torrent_directory = os.path.normpath(torrent[26])
        try:

            if torrent[4] == 1000:
                torrent_completed = True

            files = self.conn.getfiles(torrent[0])[1]['files'][1]

            for f in files:
                if not os.path.normpath(f[0]).startswith(torrent_directory):
                    file_path = os.path.join(torrent_directory, f[0].lstrip('/'))
                else:
                    file_path = f[0]

                torrent_files.append(file_path)

            torrent_info = {
                'hash': torrent[0],
                'name': torrent[2],
                'label': torrent[11] if torrent[11] else '',
                'folder': torrent[26],
                'completed': torrent_completed,
                'files': torrent_files,
            }
        except Exception:
            raise

        return torrent_info

    def start_torrent(self, torrent_hash):
        return self.conn.start(torrent_hash)

    def stop_torrent(self, torrent_hash):
        return self.conn.stop(torrent_hash)

    def delete_torrent(self, torrent):
        deleted = []
        try:
            files = self.conn.getfiles(torrent[0])[1]['files'][1]

            for f in files:
                deleted.append(os.path.normpath(os.path.join(torrent[26], f[0])))

            self.conn.removedata(torrent[0])

        except Exception:
            raise

        return deleted
