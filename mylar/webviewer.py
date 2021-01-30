import os
import re
import cherrypy
import stat
import zipfile
import urllib.parse
from lib.rarfile import rarfile

import mylar

from PIL import Image
from mylar import logger, db, importer, mb, search, filechecker, helpers, updater, parseit, weeklypull, librarysync, moveit, Failed, readinglist, config
from mylar.webserve import serve_template

class WebViewer(object):

    def __init__(self):
        self.ish_id = None
        self.page_num = None
        self.kwargs = None
        self.data = None

        if not os.path.exists(os.path.join(mylar.DATA_DIR, 'sessions')):
            os.makedirs(os.path.abspath(os.path.join(mylar.DATA_DIR, 'sessions')))

        updatecherrypyconf = {
            'tools.gzip.on': True,
            'tools.gzip.mime_types': ['text/*', 'application/*', 'image/*'],
            'tools.sessions.timeout': 1440,
            'tools.sessions.storage_class': cherrypy.lib.sessions.FileSession,
            'tools.sessions.storage_path': os.path.join(mylar.DATA_DIR, "sessions"),
            'request.show_tracebacks': False,
            #'engine.timeout_monitor.on': False,
        }
        if mylar.CONFIG.HTTP_PASSWORD is None:
            updatecherrypyconf.update({
                'tools.sessions.on': True,
            })

        cherrypy.config.update(updatecherrypyconf)
        cherrypy.engine.signals.subscribe()

    def read_comic(self, ish_id = None, page_num = None, size = None):
        logger.debug("WebReader Requested, looking for ish_id %s and page_num %s" % (ish_id, page_num))
        if size == None:
            user_size_pref = 'wide'
        else:
            user_size_pref = size

        try:
            ish_id
        except:
            logger.warn("WebReader: ish_id not set!")

        myDB = db.DBConnection()
        comic = myDB.selectone('select comics.ComicLocation, issues.Location from comics, issues where comics.comicid = issues.comicid and issues.issueid = ?' , [ish_id]).fetchone()
        if comic is None:
            logger.warn("WebReader: ish_id %s requested but not in the database!" % ish_id)
            raise cherrypy.HTTPRedirect("home")
#        cherrypy.config.update()
        comic_path = os.path.join(comic['ComicLocation'], comic['Location'])
        logger.debug("WebReader found ish_id %s at %s" % (ish_id, comic_path))

#        cherrypy.session['ish_id'].load()
#        if 'sizepref' not in cherrypy.session:
#            cherrypy.session['sizepref'] = user_size_pref
#        user_size_pref = cherrypy.session['sizepref']
#        logger.debug("WebReader setting user_size_pref to %s" % user_size_pref)

        scanner = ComicScanner()
        image_list = scanner.reading_images(ish_id)
        logger.debug("Image list contains %s pages" % (len(image_list)))
        if len(image_list) == 0:
            logger.debug("Unpacking ish_id %s from comic_path %s" % (ish_id, comic_path))
            scanner.user_unpack_comic(ish_id, comic_path)
            image_list = scanner.reading_images(ish_id)
        else:
            logger.debug("ish_id %s already unpacked." % ish_id)

        num_pages = len(image_list)
        logger.debug("Found %s pages for ish_id %s from comic_path %s" % (num_pages, ish_id, comic_path))

        if num_pages == 0:
            image_list = ['images/skipped_icon.png']

        cookie_comic = re.sub(r'\W+', '', comic_path)
        cookie_comic    = "wv_" + cookie_comic
        logger.debug("about to drop a cookie for " + cookie_comic + " which represents " + comic_path)
        cookie_check = cherrypy.request.cookie
        if cookie_comic not in cookie_check:
            logger.debug("Cookie Creation")
            cookie_path = '/'
            cookie_maxage = '2419200'
            cookie_set = cherrypy.response.cookie
            cookie_set['cookie_comic'] = 0
            cookie_set['cookie_comic']['path'] = cookie_path
            cookie_set['cookie_comic']['max-age'] = cookie_maxage
            next_page = page_num + 1
            prev_page = page_num - 1
        else:
            logger.debug("Cookie Read")
            page_num = int(cherrypy.request.cookie['cookie_comic'].value)
            logger.debug("Cookie Set To %d" % page_num)
            next_page = page_num + 1
            prev_page = page_num - 1

        logger.info("Reader Served")
        logger.debug("Serving comic " + comic['Location'] + " page number " + str(page_num))

        return serve_template(templatename="read.html", pages=image_list, current_page=page_num, np=next_page, pp=prev_page, nop=num_pages, size=user_size_pref, cc=cookie_comic, comicpath=comic_path, ish_id=ish_id)

    def up_size_pref(self, pref):
        cherrypy.session.load()
        cherrypy.session['sizepref'] = pref
        cherrypy.session.save()
        return

class ComicScanner(object):

    # This method will handle scanning the directories and returning a list of them all.
    def dir_scan(self):
        logger.debug("Dir Scan Requested")
        full_paths = []
        full_paths.append(mylar.CONFIG.DESTINATION_DIR)
        for root, dirs, files in os.walk(mylar.CONFIG.DESTINATION_DIR):
            full_paths.extend(os.path.join(root, d) for d in dirs)

        logger.info("Dir Scan Completed")
        logger.info("%i Dirs Found" % (len(full_paths)))
        return full_paths

    def user_unpack_comic(self, ish_id, comic_path):
        logger.info("%s unpack requested" % comic_path)

        for root, dirs, files in os.walk(os.path.join(mylar.CONFIG.CACHE_DIR, "webviewer", ish_id), topdown=False):
            for f in files:
                os.chmod(os.path.join(root, f), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
                os.remove(os.path.join(root, f))
        for root, dirs, files in os.walk(os.path.join(mylar.CONFIG.CACHE_DIR, "webviewer", ish_id), topdown=False):
            for d in dirs:
                os.chmod(os.path.join(root, d), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
                os.rmdir(os.path.join(root, d))
        if comic_path.endswith(".cbr"):
            opened_rar = rarfile.RarFile(comic_path)
            opened_rar.extractall(os.path.join(mylar.CONFIG.CACHE_DIR, "webviewer", ish_id))
        elif comic_path.endswith(".cbz"):
            opened_zip = zipfile.ZipFile(comic_path)
            opened_zip.extractall(os.path.join(mylar.CONFIG.CACHE_DIR, "webviewer", ish_id))
        return

    # This method will return a list of .jpg files in their numerical order to be fed into the reading view.
    def reading_images(self, ish_id):
        logger.debug("Image List Requested")
        image_list = []
        image_src = os.path.join(mylar.CONFIG.CACHE_DIR, "webviewer", ish_id)
        image_loc = os.path.join(mylar.CONFIG.HTTP_ROOT, 'cache', "webviewer", ish_id)
        for root, dirs, files in os.walk(image_src):
            for f in files:
                if f.endswith((".png", ".gif", ".bmp", ".dib", ".jpg", ".jpeg", ".jpe", ".jif", ".jfif", ".jfi", ".tiff", ".tif")):
                    rel_dir = os.path.relpath(root, image_src)
                    rel_file = os.path.join(rel_dir, f)
                    image_list.append(urllib.parse.quote(os.path.join(image_loc, rel_file)))
                    image_list.sort()
        logger.debug("Image List Created")
        return image_list



