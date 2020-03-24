import sys
import os
import platform
import subprocess
import mylar
import configparser
import codecs
import shutil
import itertools
#import pathlib
from collections import OrderedDict
from operator import itemgetter

from glob import glob
from mylar import mylar, config, logger, encrypted
import zipfile

class carePackage(object):

    def __init__(self):
        self.filename = os.path.join(mylar.CONFIG.LOG_DIR, 'MylarRunningEnvironment.txt')
        self.panicfile = os.path.join(mylar.CONFIG.LOG_DIR, "carepackage.zip")
        self.configpath = os.path.join(mylar.DATA_DIR, 'config.ini')
        self.cleanpath = os.path.join(mylar.CONFIG.LOG_DIR, 'clean_config.ini')
        self.lastrelpath = os.path.join(mylar.PROG_DIR, '.LASTRELEASE')
        self.keylist = []
        self.cleaned_list = {
                            ('Interface', 'http_password'),
                            ('SABnzbd', 'sab_username'),
                            ('SABnzbd', 'sab_password'),
                            ('SABnzbd', 'sab_apikey'),
                            ('NZBGet', 'nzbget_username'),
                            ('NZBGet', 'nzbget_password'),
                            ('NZBsu', 'nzbsu_apikey'),
                            ('DOGnzb', 'dognzb_apikey'),
                            ('uTorrent', 'utorrent_username'),
                            ('uTorrent', 'utorrent_password'),
                            ('Transmission', 'transmission_username'),
                            ('Transmission', 'transmission_password'),
                            ('Deluge', 'deluge_username'),
                            ('Deluge', 'deluge_password'),
                            ('qBittorrent', 'qbittorrent_username'),
                            ('qBittorrent', 'qbittorrent_password'),
                            ('Rtorrent', 'rtorrent_username'),
                            ('Rtorrent', 'rtorrent_password'),
                            ('Prowl', 'prowl_keys'),
                            ('PUSHOVER', 'pushover_apikey'),
                            ('PUSHOVER', 'pushover_userkey'),
                            ('BOXCAR', 'boxcar_token'),
                            ('PUSHBULLET', 'pushbullet_apikey'),
                            ('NMA', 'nma_apikey'),
                            ('TELEGRAM', 'telegram_token'),
                            ('CV', 'comicvine_api'),
                            ('32P', 'password_32p'),
                            ('32P', 'passkey_32p'),
                            ('32P', 'username_32p'),
                            ('32P', 'rssfeed_32p'),
                            ('Seedbox', 'seedbox_user'),
                            ('Seedbox', 'seedbox_pass'),
                            ('Seedbox', 'seedbox_port'),
                            ('Tablet', 'tab_pass'),
                            ('API', 'api_key'),
                            ('OPDS', 'opds_password'),
                            ('AutoSnatch', 'pp_sshpasswd'),
                            ('AutoSnatch', 'pp_sshport'),
                            ('Email', 'email_password'),
                            ('Email', 'email_user')
                            }
        self.hostname_list = {
                            ('SABnzbd', 'sab_host'),
                            ('NZBGet', 'nzbget_host'),
                            ('Torznab', 'torznab_host'),
                            ('uTorrent', 'utorrent_host'),
                            ('Transmission', 'transmission_host'),
                            ('Deluge', 'deluge_host'),
                            ('qBittorrent', 'qbittorrent_host'),
                            ('Interface', 'http_host'),
                            ('Rtorrent', 'rtorrent_host'),
                            ('AutoSnatch', 'pp_sshhost'),
                            ('Tablet', 'tab_host'),
                            ('Seedbox', 'seedbox_host'),
                            ('Email', 'email_server')
                             }
        self.environment()
        self.cleaned_config()
        self.panicbutton()

    def environment(self):
        f = open(self.filename, "w+")

        f.write("Mylar host information:\n")
        if platform.system() == 'Windows':
            objline = ['systeminfo']
        else:
            objline = ['uname', '-a']

        hi = subprocess.run(objline,
            capture_output=True,
            text=True)
        for hiline in hi.stdout.split('\n'):
            if platform.system() == 'Windows':
                if all(['Host Name' not in hiline, 'OS Name' not in hiline, 
				'OS Version' not in hiline, 'OS Configuration' not in hiline,
				'OS Build Type' not in hiline, 'Locale' not in hiline,
				'Time Zone' not in hiline]):
                    continue
            f.write("%s\n" % hiline)

        f.write("\n\nMylar python information:\n")
        pyloc = sys.executable
        pi = subprocess.run([pyloc, '-V'],
            capture_output=True,
            text=True)
        f.write("%s" % pi.stdout)
        f.write("%s\n" % pyloc)

        try:
            pf = subprocess.run(['pip3', 'freeze'],
                capture_output=True,
                text=True)
            f.write("\nPIP (freeze) list:\n")
            for pfout in pf.stdout.split('\n'):
                f.write("%s\n" % pfout)
        except Exception as e:
            logger.warn('Unable to retrieve current pip listing. Usually this is due to pip being referenced as something other than pip3')

        f.write("\n\nMylar running environment:\n")
        for param in list(os.environ.keys()):
            if all(['SSH' not in param, 'LS_COLORS' not in param]):
                f.write("%20s = %s\n" % (param,os.environ[param]))

        f.write("\n\nMylar git status:\n")
        try:
            cmd = [['git', '--version'],['git', 'status']]
            for c in cmd:
                gs = subprocess.run(c,
                    capture_output=True,
                    text=True)
                for line in gs.stdout.split('\n'):
                    f.write("%s\n" % line)
        except Exception as e:
            f.write("\n\nUnable to retrieve Git information")

        f.close()

    def cleaned_config(self):
        shutil.copy(self.configpath, self.cleanpath)
        tmpconfig = configparser.SafeConfigParser()
        tmpconfig.readfp(codecs.open(self.cleanpath, 'r', 'utf8'))

        for v in self.cleaned_list:
            try:
                tmpkey = tmpconfig.get(v[0], v[1])
                if all([tmpkey is not None, tmpkey != 'None']):
                    if tmpkey[:5] == '^~$z$':
                        tk = encrypted.Encryptor(tmpkey)
                        tk_stat = tk.decrypt_it()
                        if tk_stat['status'] is True:
                            tmpkey = tk_stat['password']
                    if tmpkey not in self.keylist:
                        self.keylist.append(tmpkey)
                    tmpconfig.set(v[0], v[1], 'xXX[REMOVED]XXx')
            except configparser.NoSectionError as e:
                pass

        for h in self.hostname_list:
            hkey = tmpconfig.get(h[0], h[1])
            if all([hkey is not None, hkey != 'None']):
                if hkey[:5] == '^~$z$':
                    hk = encrypted.Encryptor(hkey)
                    hk_stat = tk.decrypt_it()
                    if tk_stat['status'] is True and 'username' not in h[1]:
                        hkey = hk_stat['password']
                if hkey not in self.keylist:
                    self.keylist.append(hkey)
                tmpconfig.set(h[0], h[1], 'xXX[REMOVED]XXx')

        extra_newznabs = list(zip(*[iter(tmpconfig.get('Newznab', 'extra_newznabs').split(', '))]*6))
        extra_torznabs = list(zip(*[iter(tmpconfig.get('Torznab', 'extra_torznabs').split(', '))]*5))
        cleaned_newznabs = []
        cleaned_torznabs = []
        for ens in extra_newznabs:
            n_host = None
            n_uid = None
            n_api = None
            if ens[1] is not None:
                n_host = 'xXX[REMOVED]XXx'
            if ens[3] is not None:
                nzkey = ens[3]
                if nzkey[:5] == '^~$z$':
                    nz = encrypted.Encryptor(nzkey)
                    nz_stat = nz.decrypt_it()
                    if nz_stat['status'] is True:
                        nzkey = nz_stat['password']
                if nzkey not in self.keylist:
                    self.keylist.append(nzkey)
                n_api = 'xXX[REMOVED]XXx'
            if ens[4] is not None:
                n_uid = 'xXX[REMOVED]XXx'
            newnewzline = (ens[0], n_host, ens[2], n_api, n_uid, ens[5])
            cleaned_newznabs.append(newnewzline)

        for ets in extra_torznabs:
            n_host = None
            n_uid = None
            n_api = None
            if ets[1] is not None:
                n_host = 'xXX[REMOVED]XXx'
            if ets[2] is not None:
                tzkey = ets[2]
                if tzkey[:5] == '^~$z$':
                    tz = encrypted.Encryptor(tzkey)
                    tz_stat = tz.decrypt_it()
                    if tz_stat['status'] is True:
                        tzkey = tz_stat['password']
                if tzkey not in self.keylist:
                    self.keylist.append(tzkey)
                n_api = 'xXX[REMOVED]XXx'
            if ets[4] is not None:
                n_uid = 'xXX[REMOVED]XXx'
            newtorline = (ets[0], n_host, n_api, ets[3], ets[4])
            cleaned_torznabs.append(newtorline)

        tmpconfig.set('Newznab', 'extra_newznabs', ', '.join(self.write_extras(cleaned_newznabs)))
        tmpconfig.set('Torznab', 'extra_torznabs', ', '.join(self.write_extras(cleaned_torznabs)))
        try:
            with codecs.open(self.cleanpath, encoding='utf8', mode='w+') as tmp_configfile:
                tmpconfig.write(tmp_configfile)
            logger.fdebug('Configuration cleaned of keys/passwords and written to temporary location.')
        except IOError as e:
            logger.warn("Error writing configuration file: %s" % e)

    def write_extras(self, value):
        flattened = []
        for item in value:
            for i in item:
                try:
                    if "\"" in i and " \"" in i:
                        ib = str(i).replace("\"", "").strip()
                    else:
                        ib = i
                except:
                    ib = i
                flattened.append(str(ib))
        return flattened


    def panicbutton(self):
        dbpath = os.path.join(mylar.DATA_DIR, 'mylar.db')
        with zipfile.ZipFile(self.panicfile, 'w') as zip:
            zip.write(self.filename, os.path.basename(self.filename))
            zip.write(dbpath, os.path.basename(dbpath))
            zip.write(self.cleanpath, os.path.basename(self.cleanpath))
            if os.path.exists(self.lastrelpath):
                zip.write(self.lastrelpath, os.path.basename(self.lastrelpath))

            files = []
            try:
                caredir = os.path.join(mylar.CONFIG.LOG_DIR, 'carepackage')
                os.mkdir(caredir)
            except Exception as e:
                pass

            for file in glob(os.path.join(mylar.CONFIG.LOG_DIR,'mylar.log*')):
                #files.append(pathlib.Path(pathlib.PurePath(mylar.CONFIG.LOG_DIR).joinpath(os.path.basename(file)))) #os.path.join(mylar.CONFIG.LOG_DIR, os.path.basename(file)))
                files.append(os.path.join(mylar.CONFIG.LOG_DIR, os.path.basename(file)))

            if len(files) > 0:
                for fname in files:
                    logger.fdebug('analyzing %s' % fname)
                    cnt = 0
                    wrote = False
                    #remove the apikeys first.
                    filename = os.path.join(caredir, os.path.basename(fname))
                    output = open(filename, 'w')
                    #output = pathlib.Path(filename) #open(filename, 'w')
                    with open(fname, 'r') as f:
                        line = f.readline()
                        while line:
                            for keyed in self.keylist:
                                if keyed in line and len(keyed) > 0:
                                    cnt+=1
                                    line = line.replace(keyed, '-REDACTED-')
                            output.write(line)
                            line = f.readline()

                    logger.fdebug('removed %s keys from %s' % (cnt, fname))
                    try:
                        zip.write(filename, os.path.basename(fname), zipfile.ZIP_DEFLATED)
                    except RuntimeError:
                        #if zlib isn't available, will throw RuntimeError, then just use default compression
                        zip.write(filename, os.path.basename(fname))
                    except Exception as e:
                        logger.warn(e)
                    else:
                        os.unlink(filename)

        try:
            os.rmdir(os.path.join(mylar.CONFIG.LOG_DIR, 'carepackage'))
        except:
            pass

        os.unlink(self.filename)
        os.unlink(self.cleanpath)
