import requests
import json

class LoginRequired(Exception):
    def __str__(self):
        return 'Please login first.'


class Client(object):
    """class to interact with qBittorrent WEB API"""
    def __init__(self, url):
        if not url.endswith('/'):
            url += '/'
        self.url = url

        session = requests.Session()
        check_prefs = session.get(url+'api/v2/app/preferences')

        if check_prefs.status_code == 200:
            self._is_authenticated = True
            self.session = session

        elif check_prefs.status_code == 404:
            self._is_authenticated = False
            raise RuntimeError("""
                This wrapper only supports qBittorrent applications with
                version higher than 4.1.0 (which implemented Web API v2.0).
                Please use the latest qBittorrent release.
                """)

        else:
            self._is_authenticated = False

    def _get(self, endpoint, **kwargs):
        """
        Method to perform GET request on the API.

        :param endpoint: Endpoint of the API.
        :param kwargs: Other keyword arguments for requests.

        :return: Response of the GET request.
        """
        return self._request(endpoint, 'get', **kwargs)

    def _post(self, endpoint, data, **kwargs):
        """
        Method to perform POST request on the API.

        :param endpoint: Endpoint of the API.
        :param data: POST DATA for the request.
        :param kwargs: Other keyword arguments for requests.

        :return: Response of the POST request.
        """
        return self._request(endpoint, 'post', data, **kwargs)

    def _request(self, endpoint, method, data=None, **kwargs):
        """
        Method to hanle both GET and POST requests.

        :param endpoint: Endpoint of the API.
        :param method: Method of HTTP request.
        :param data: POST DATA for the request.
        :param kwargs: Other keyword arguments.

        :return: Response for the request.
        """
        final_url = self.url + endpoint

        if not self._is_authenticated:
            raise LoginRequired

        rq = self.session
        if method == 'get':
            request = rq.get(final_url, **kwargs)
        else:
            request = rq.post(final_url, data, **kwargs)

        request.raise_for_status()
        request.encoding = 'utf_8'

        if len(request.text) == 0:
            data = json.loads('{}')
        else:
            try:
                data = json.loads(request.text)
            except ValueError:
                data = request.text

        return data

    def login(self, username='admin', password='admin'):
        """
        Method to authenticate the qBittorrent Client.

        Declares a class attribute named ``session`` which
        stores the authenticated session if the login is correct.
        Else, shows the login error.

        :param username: Username.
        :param password: Password.

        :return: Response to login request to the API.
        """
        self.session = requests.Session()
        login = self.session.post(self.url+'api/v2/auth/login',
                                  data={'username': username,
                                        'password': password})
        if login.text == 'Ok.':
            self._is_authenticated = True
        else:
            return login.text

    def logout(self):
        """
        Logout the current session.
        """
        response = self._get('api/v2/auth/logout')
        self._is_authenticated = False
        return response

    @property
    def qbittorrent_version(self):
        """
        Get qBittorrent version.
        """
        return self._get('api/v2/app/version')

    @property
    def api_version(self):
        """
        Get WEB API version.
        """
        return self._get('api/v2/app/webapiVersion')

    def shutdown(self):
        """
        Shutdown qBittorrent.
        """
        return self._get('api/v2/app/shutdown')

    def torrents(self, **filters):
        """
        Returns a list of torrents matching the supplied filters.

        :param filter: Current status of the torrents.
        :param category: Fetch all torrents with the supplied label.
        :param sort: Sort torrents by.
        :param reverse: Enable reverse sorting.
        :param limit: Limit the number of torrents returned.
        :param offset: Set offset (if less than 0, offset from end).
        :param hashes: Filter by hashes. Can contain multiple hashes separated by |.

        :return: list() of torrent with matching filter.
        """
        params = {}
        for name, value in filters.items():
            # make sure that old 'status' argument still works
            name = 'filter' if name == 'status' else name
            params[name] = value

        return self._get('api/v2/torrents/info', params=params)

    def get_torrent(self, infohash):
        """
        Get details of the torrent.

        :param infohash: INFO HASH of the torrent.
        """
        return self._get('api/v2/torrents/properties', params={'hash': infohash.lower()})

    def get_torrent_trackers(self, infohash):
        """
        Get trackers for the torrent.

        :param infohash: INFO HASH of the torrent.
        """
        return self._get('api/v2/torrents/trackers', params={'hash': infohash.lower()})

    def get_torrent_webseeds(self, infohash):
        """
        Get webseeds for the torrent.

        :param infohash: INFO HASH of the torrent.
        """
        return self._get('api/v2/torrents/webseeds', params={'hash': infohash.lower()})

    def get_torrent_files(self, infohash):
        """
        Get list of files for the torrent.

        :param infohash: INFO HASH of the torrent.
        """
        return self._get('api/v2/torrents/files', params={'hash': infohash.lower()})

    @property
    def global_transfer_info(self):
        """
        Get JSON data of the global transfer info of qBittorrent.
        """
        return self._get('api/v2/transfer/info')

    @property
    def preferences(self):
        """
        Get the current qBittorrent preferences.
        Can also be used to assign individual preferences.
        For setting multiple preferences at once,
        see ``set_preferences`` method.

        Note: Even if this is a ``property``,
        to fetch the current preferences dict, you are required
        to call it like a bound method.

        Wrong::

            qb.preferences

        Right::

            qb.preferences()

        """
        prefs = self._get('api/v2/app/preferences')

        class Proxy(Client):
            """
            Proxy class to to allow assignment of individual preferences.
            this class overrides some methods to ease things.

            Because of this, settings can be assigned like::

                In [5]: prefs = qb.preferences()

                In [6]: prefs['autorun_enabled']
                Out[6]: True

                In [7]: prefs['autorun_enabled'] = False

                In [8]: prefs['autorun_enabled']
                Out[8]: False

            """

            def __init__(self, url, prefs, auth, session):
                super(Proxy, self).__init__(url)
                self.prefs = prefs
                self._is_authenticated = auth
                self.session = session

            def __getitem__(self, key):
                return self.prefs[key]

            def __setitem__(self, key, value):
                kwargs = {key: value}
                return self.set_preferences(**kwargs)

            def __call__(self):
                return self.prefs

        return Proxy(self.url, prefs, self._is_authenticated, self.session)

    def sync(self, rid=0):
        """
        Sync the torrents by supplied LAST RESPONSE ID.
        Read more @ https://git.io/fxgB8

        :param rid: Response ID of last request.
        """
        return self._get('api/v2/sync/maindata', params={'rid': rid})

    def download_from_link(self, link, **kwargs):
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        # qBittorrent requires adds to be done with multipath/form-data
        # POST requests for both URLs and .torrent files. Info on this
        # can be found here, and here:
        # http://docs.python-requests.org/en/master/user/quickstart/#post-a-multipart-encoded-file
        # http://docs.python-requests.org/en/master/user/advanced/#post-multiple-multipart-encoded-files
        if isinstance(link, list):
            links = '\n'.join(link)
        else:
            links = link
        torrent_data = {}
        torrent_data['urls'] = (None, links)
        for k, v in kwargs.items():
            torrent_data[k] = (None, v)
        return self._post('api/v2/torrents/add', data=None, files=torrent_data)

    def download_from_file(self, file_buffer, **kwargs):
        """
        Download torrent using a file.

        :param file_buffer: Single file() buffer or list of.
        :param save_path: Path to download the torrent.
        :param label: Label of the torrent(s).

        :return: Empty JSON data.
        """
        # qBittorrent requires adds to be done with multipath/form-data
        # POST requests for both URLs and .torrent files. Info on this
        # can be found here, and here:
        # http://docs.python-requests.org/en/master/user/quickstart/#post-a-multipart-encoded-file
        # http://docs.python-requests.org/en/master/user/advanced/#post-multiple-multipart-encoded-files
        if isinstance(file_buffer, list):
            torrent_data = []
            for f in file_buffer:
                fname = f.name
                torrent_data.append(('torrents', (fname, f)))
        else:
            fname = file_buffer.name
            torrent_data = [('torrents', (fname, file_buffer))]
        for k, v in kwargs.items():
            torrent_data.append((k, (None, v)))

        return self._post('api/v2/torrents/add', data=None, files=torrent_data)

    def add_trackers(self, infohash, trackers):
        """
        Add trackers to a torrent.

        :param infohash: INFO HASH of torrent.
        :param trackers: Trackers.
        """
        data = {'hash': infohash.lower(),
                'urls': trackers}
        return self._post('api/v2/torrents/addTrackers', data=data)

    @staticmethod
    def _process_infohash_list(infohash_list):
        """
        Method to convert the infohash_list to qBittorrent API friendly values.

        :param infohash_list: List of infohash.
        """
        if isinstance(infohash_list, list):
            data = {'hashes': '|'.join([h.lower() for h in infohash_list])}
        else:
            data = {'hashes': infohash_list.lower()}
        return data

    def pause(self, infohash):
        """
        Pause a torrent.

        :param infohash: INFO HASH of torrent.
        """
        return self._post('api/v2/torrents/pause', data={'hashes': infohash.lower()})

    def pause_all(self):
        """
        Pause all torrents.
        """
        return self._post('api/v2/torrents/pause', data={'hashes': 'all'})

    def pause_multiple(self, infohash_list):
        """
        Pause multiple torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/pause', data=data)

    def set_category(self, infohash_list, category):
        """
        Set the category on multiple torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        data['category'] = category
        return self._post('api/v2/torrents/setCategory', data=data)

    def resume(self, infohash):
        """
        Resume a paused torrent.

        :param infohash: INFO HASH of torrent.
        """
        return self._post('api/v2/torrents/resume', data={'hashes': infohash.lower()})

    def resume_all(self):
        """
        Resume all torrents.
        """
        return self._post('api/v2/torrents/resume', data={'hashes': 'all'})

    def resume_multiple(self, infohash_list):
        """
        Resume multiple paused torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/resume', data=data)

    def delete(self, infohash_list):
        """
        Delete torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        data['deleteFiles'] = 'false'
        return self._post('api/v2/torrents/delete', data=data)

    def delete_permanently(self, infohash_list):
        """
        Permanently delete torrents.

        ***  WARNING :  This will instruct qBittorrent to delete files
        ***             from your hard disk. Use with caution.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        data['deleteFiles'] = 'true'
        return self._post('api/v2/torrents/delete', data=data)

    def recheck(self, infohash_list):
        """
        Recheck torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/recheck', data=data)

    def increase_priority(self, infohash_list):
        """
        Increase priority of torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/increasePrio', data=data)

    def decrease_priority(self, infohash_list):
        """
        Decrease priority of torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/decreasePrio', data=data)

    def set_max_priority(self, infohash_list):
        """
        Set torrents to maximum priority level.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/topPrio', data=data)

    def set_min_priority(self, infohash_list):
        """
        Set torrents to minimum priority level.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/bottomPrio', data=data)

    def set_file_priority(self, infohash, file_id, priority):
        """
        Set file of a torrent to a supplied priority level.

        :param infohash: INFO HASH of torrent.
        :param file_id: ID of the file to set priority.
        :param priority: Priority level of the file.
        """
        if priority not in [0, 1, 6, 7]:
            raise ValueError("Invalid priority, refer WEB-UI docs for info.")
        elif not isinstance(file_id, int):
            raise TypeError("File ID must be an int")

        data = {'hash': infohash.lower(),
                'id': file_id,
                'priority': priority}

        return self._post('api/v2/torrents/filePrio', data=data)

    # Get-set global download and upload speed limits.

    def get_global_download_limit(self):
        """
        Get global download speed limit.
        """
        return self._get('api/v2/transfer/downloadLimit')

    def set_global_download_limit(self, limit):
        """
        Set global download speed limit.

        :param limit: Speed limit in bytes.
        """
        return self._post('api/v2/transfer/setDownloadLimit', data={'limit': limit})

    global_download_limit = property(get_global_download_limit,
                                     set_global_download_limit)

    def get_global_upload_limit(self):
        """
        Get global upload speed limit.
        """
        return self._get('api/v2/transfer/uploadLimit')

    def set_global_upload_limit(self, limit):
        """
        Set global upload speed limit.

        :param limit: Speed limit in bytes.
        """
        return self._post('api/v2/transfer/setUploadLimit', data={'limit': limit})

    global_upload_limit = property(get_global_upload_limit,
                                   set_global_upload_limit)

    # Get-set download and upload speed limits of the torrents.
    def get_torrent_download_limit(self, infohash_list):
        """
        Get download speed limit of the supplied torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/downloadLimit', data=data)

    def set_torrent_download_limit(self, infohash_list, limit):
        """
        Set download speed limit of the supplied torrents.

        :param infohash_list: Single or list() of infohashes.
        :param limit: Speed limit in bytes.
        """
        data = self._process_infohash_list(infohash_list)
        data.update({'limit': limit})
        return self._post('api/v2/torrents/setDownloadLimit', data=data)

    def get_torrent_upload_limit(self, infohash_list):
        """
        Get upoload speed limit of the supplied torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/uploadLimit', data=data)

    def set_torrent_upload_limit(self, infohash_list, limit):
        """
        Set upload speed limit of the supplied torrents.

        :param infohash_list: Single or list() of infohashes.
        :param limit: Speed limit in bytes.
        """
        data = self._process_infohash_list(infohash_list)
        data.update({'limit': limit})
        return self._post('api/v2/torrents/setUploadLimit', data=data)

    # setting preferences
    def set_preferences(self, **kwargs):
        """
        Set preferences of qBittorrent.
        Read all possible preferences @ https://git.io/fx2Y9

        :param kwargs: set preferences in kwargs form.
        """
        json_data = "json={}".format(json.dumps(kwargs))
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        return self._post('api/v2/app/setPreferences', data=json_data,
                          headers=headers)

    def get_alternative_speed_status(self):
        """
        Get Alternative speed limits. (1/0)
        """
        return self._get('api/v2/transfer/speedLimitsMode')

    alternative_speed_status = property(get_alternative_speed_status)

    def toggle_alternative_speed(self):
        """
        Toggle alternative speed limits.
        """
        return self._get('api/v2/transfer/toggleSpeedLimitsMode')

    def toggle_sequential_download(self, infohash_list):
        """
        Toggle sequential download in supplied torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/toggleSequentialDownload', data=data)

    def toggle_first_last_piece_priority(self, infohash_list):
        """
        Toggle first/last piece priority of supplied torrents.

        :param infohash_list: Single or list() of infohashes.
        """
        data = self._process_infohash_list(infohash_list)
        return self._post('api/v2/torrents/toggleFirstLastPiecePrio', data=data)

    def force_start(self, infohash_list, value=True):
        """
        Force start selected torrents.

        :param infohash_list: Single or list() of infohashes.
        :param value: Force start value (bool)
        """
        data = self._process_infohash_list(infohash_list)
        data.update({'value': json.dumps(value)})
        return self._post('api/v2/torrents/setForceStart', data=data)
