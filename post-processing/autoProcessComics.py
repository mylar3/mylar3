import sys
import os.path
import configparser
import urllib.request, urllib.error, urllib.parse
import urllib.request, urllib.parse, urllib.error
import platform

try:
    import requests
    use_requests = True
except ImportError:
    print('''Requests module not found on system. I'll revert so this will work, but you probably should install 
        requests to bypass this in the future (i.e. pip install requests)''')
    use_requests = False

use_win32api = False
if platform.system() == 'Windows':
    try:
        import win32api
        use_win32api = True
    except ImportError:
        print('''The win32api module was not found on this system. While it's fine to run without it, you're 
            running a Windows-based OS, so it would benefit you to install it. It enables ComicRN to better 
            work with file paths beyond the 260 character limit. Run "pip install pypiwin32".''')

apc_version = "2.04"

def processEpisode(dirName, nzbName=None):
    print("Your ComicRN.py script is outdated. I'll force this through, but Failed Download Handling and possible enhancements/fixes will not work and could cause errors.")
    return processIssue(dirName, nzbName)

def processIssue(dirName, nzbName=None, failed=False, comicrn_version=None):
    if use_win32api is True:
        dirName = win32api.GetShortPathName(dirName)

    config = configparser.ConfigParser()
    configFilename = os.path.join(os.path.dirname(sys.argv[0]), "autoProcessComics.cfg")
    print("Loading config from", configFilename)

    if not os.path.isfile(configFilename):
        print("ERROR: You need an autoProcessComics.cfg file - did you rename and edit the .sample?")
        sys.exit(-1)

    try:
        with open(configFilename, "r") as fp:
            config.read_file(fp)
    except IOError as e:
        print("Could not read configuration file: ", str(e))
        sys.exit(1)

    host = config.get("Mylar", "host")
    port = config.get("Mylar", "port")
    apikey = config.get("Mylar", "apikey")
    if apikey is None:
        print("No ApiKey has been set within Mylar to allow this script to run. This is NEW. Generate an API within Mylar, and make sure to enter the apikey value into the autoProcessComics.cfg file before re-running.")
        sys.exit(1)
    try:
        ssl = int(config.get("Mylar", "ssl"))
    except (configparser.NoOptionError, ValueError):
        ssl = 0

    try:
        web_root = config.get("Mylar", "web_root")
    except configparser.NoOptionError:
        web_root = ""

    if ssl:
        protocol = "https://"
    else:
        protocol = "http://"

    url = protocol + host + ":" + port + web_root + '/api'

    params = {'cmd': 'forceProcess',
              'apikey': apikey,
              'nzb_folder': dirName}

    if nzbName != None:
        params['nzb_name'] = nzbName
    params['failed'] = failed

    params['apc_version'] = apc_version
    params['comicrn_version'] = comicrn_version

    if use_requests is True:
        try:
            print("Opening URL for post-process of %s @ %s/forceProcess:" % (dirName,url))
            pp = requests.post(url, params=params, verify=False)
        except Exception as e:
            print("Unable to open URL: %s" %e)
            sys.exit(1)
        else:
            print('statuscode: %s' % pp.status_code)
            result = pp.content
            print(result)
    else:
        url += "?" + urllib.parse.urlencode(params)
        print("Opening URL:", url)
        try:
            urlObj = urllib.request.urlopen(url)
        except IOError as e:
            print("Unable to open URL: ", str(e))
            sys.exit(1)
        else:
            result = urlObj.readlines()
            for line in result:
                print(line.decode('utf-8').strip())

    if type(result) == list:
        if any(b"Post Processing SUCCESSFUL" in s if isinstance(s, bytes) else "Post Processing SUCCESSFUL" in s for s in result):
            return 0
        else:
            return 1
    elif type(result) == bytes:
        if b'Post Processing SUCCESSFUL' in result:
            return 0
        else:
            return 1
    else:
        if any("Post Processing SUCCESSFUL" in s for s in result.split('\n')):
            return 0
        else:
            return 1
