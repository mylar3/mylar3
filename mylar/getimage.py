#  This file is part of Mylar.
# -*- coding: utf-8 -*-
#
#  Mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mylar is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

from lib.rarfile import rarfile
import requests
import zipfile
from io import BytesIO

try:
    from PIL import Image
    from PIL import ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    PIL_Found = True
except Exception as e:
    logger.warn('[WARNING] PIL is not available - it\'s used to resize images for notifications, and other things.')
    logger.warn('[WARNING] Using fallback method of URL / no image - install PIL with pip: pip install PIL')
    PIL_Found = False

import os
import re
import base64
from operator import itemgetter

import mylar
from mylar import logger, helpers

def open_archive(location):
    if location.endswith(".cbz"):
        return zipfile.ZipFile(location), 'is_dir'
    else:
        try:
            return rarfile.RarFile(location), 'isdir'
        except rarfile.BadRarFile as e:
            logger.warn('[WARNING] %s: %s' % (location,e))
            try:
                logger.info('Trying to see if this is a zip renamed as a rar: %s' % (location))
                return zipfile.ZipFile(location), 'is_dir'
            except Exception as e:
                logger.warn('[EXCEPTION] %s' % e)
        except Exception as e:
            logger.warn('[EXCEPTION]: %s' % e)

def isimage(filename):
    return os.path.splitext(filename)[1][1:].lower() in ['jpg', 'jpeg', 'png', 'webp']

def comic_pages(archive):
      return sorted([name for name in archive.namelist() if isimage(name)])

def page_count(archive):
      return len(comic_pages(archive))

def scale_image(img, iformat, new_width, algorithm=Image.LANCZOS):
    # img = PIL image object
    # iformat = 'jpeg', 'png', or 'webp'
    # new_width = width in pixels
    # algorithm = scaling algorithm used
    scale = (new_width / float(img.size[0]))
    new_height = int(scale * img.size[1])
    if img.mode in ("RGBA", "P"):
        im = img.convert("RGB")
        img = im.resize((new_width, new_height), algorithm)
        logger.info('converted to webp...')
    else:
        img = img.resize((new_width, new_height), algorithm)

    with BytesIO() as output:
        img.save(output, format=iformat)
        return output.getvalue()

def extract_image(location, single=False, imquality=None, comicname=None):
    #location = full path to the cbr/cbz (filename included in path)
    #single = should be set to True so that a single file can have the coverfile
    #        extracted and have the cover location returned to the calling function
    #imquality = the calling function ('notif' for notifications will initiate a resize image before saving the cover)
    if PIL_Found is False:
        return
    cover = "notfound"
    pic_extensions = ('.jpg','.jpeg','.png','.webp')
    issue_ends = ('1','0')
    modtime = os.path.getmtime(location)
    low_infile = 999999999999999999
    low_num = 1000
    local_filename = os.path.join(mylar.CONFIG.CACHE_DIR, 'temp_notif')
    cb_filename= None
    cb_filenames=[]
    metadata = None
    if single is True:
        location_in, dir_opt = open_archive(location)
        try:
            cntr = 0
            newlencnt = 0
            newlen = 0
            newlist = []
            for infile in location_in.infolist():
                cntr +=1
                basename = os.path.basename(infile.filename)
                if infile.filename == 'ComicInfo.xml':
                    logger.fdebug('Extracting ComicInfo.xml to display.')
                    metadata = location_in.read(infile.filename)
                    if cover == 'found':
                        break
                filename, extension = os.path.splitext(basename)
                tmp_infile = re.sub("[^0-9]","", filename).strip()
                lenfile = len(infile.filename)
                if any([tmp_infile == '', not getattr(infile, dir_opt), 'zzz' in filename.lower(), 'logo' in filename.lower()]) or ((comicname is not None) and all([comicname.lower().startswith('z'), filename.lower().startswith('z')])):
                    continue
                if all([infile.filename.lower().endswith(pic_extensions), int(tmp_infile) < int(low_infile)]):
                    #logger.info('cntr: %s / infolist: %s' % (cntr, len(location_in.infolist())) )
                    #get the length of the filename, compare it to others. scanner ones are always different named than the other 98% of the files.
                    if lenfile >= newlen:
                        newlen = lenfile
                        newlencnt += 1
                    newlist.append({'length':       lenfile,
                                    'filename':     infile.filename,
                                    'tmp_infile':   tmp_infile})

                    #logger.info('newlen: %s / newlencnt: %s' % (newlen, newlencnt))
                    if newlencnt > 0 and lenfile >= newlen:
                        #logger.info('setting it to : %s' % infile.filename)
                        low_infile = tmp_infile
                        low_infile_name = infile.filename
                elif any(['00a' in infile.filename, '00b' in infile.filename, '00c' in infile.filename, '00d' in infile.filename, '00e' in infile.filename, '00fc' in infile.filename.lower()]) and infile.filename.endswith(pic_extensions) and cover == "notfound":
                    if cntr == 0:
                        altlist = ('00a', '00b', '00c', '00d', '00e', '00fc')
                        for alt in altlist:
                            if alt in infile.filename.lower():
                                cb_filename = infile.filename
                                cover = "found"
                                #logger.fdebug('[%s] cover found:%s' % (alt, infile.filename))
                                break
                elif all([tmp_infile.endswith(issue_ends), infile.filename.lower().endswith(pic_extensions), int(tmp_infile) < int(low_infile), cover == 'notfound']):
                    cb_filenames.append(infile.filename)

            if cover != "found" and any([len(cb_filenames) > 0, low_infile != 9999999999999]):
                logger.fdebug('Invalid naming sequence for jpgs discovered. Attempting to find the lowest sequence and will use as cover (it might not work). Currently : %s' % (low_infile_name))
                # based on newlist - if issue doesn't end in 0 & 1, take the lowest numeric of the most common length of filenames within the rar
                if not any([low_infile.endswith('0'),low_infile.endswith('1')]):
                    from collections import Counter
                    cnt = Counter([t['length'] for t in newlist])
                    #logger.info('cnt: %s' % (cnt,)) #cnt: Counter({15: 23, 20: 1})
                    tmpst = 999999999
                    cntkey = max(cnt.items(), key=itemgetter(1))[0]
                    #logger.info('cntkey: %s' % cntkey)
                    for x in newlist:
                        if x['length'] == cntkey and int(x['tmp_infile']) < tmpst:
                            tmpst = int(x['tmp_infile'])
                            cb_filename = x['filename']
                            logger.fdebug('SETTING cb_filename set to : %s' % cb_filename)
                else:
                    cb_filename = low_infile_name
                    cover = "found"

        except Exception as e:
            logger.error('[ERROR] Unable to properly retrieve the cover. It\'s probably best to re-tag this file : %s' % e)
            return

        logger.fdebug('cb_filename set to : %s' % cb_filename)

        if extension is not None:
            ComicImage = local_filename + extension
            try:
                insidefile = location_in.getinfo(cb_filename)
                img = Image.open( BytesIO( location_in.read(insidefile) ))
                imdata = scale_image(img, "JPEG", 600)
                try:
                    ComicImage = str(base64.b64encode(imdata), 'utf-8')
                    RawImage = imdata
                except Exception as e:
                    ComicImage = str(base64.b64encode(imdata + "==="), 'utf-8')
                    RawImage = imdata + "==="

            except Exception as e:
                logger.warn('[WARNING] Unable to resize existing image: %s' % e)
        else:
            ComicImage = local_filename
    return {'ComicImage': ComicImage, 'metadata': metadata, 'rawImage': RawImage}

def retrieve_image(url):
    try:
        r = requests.get(url, params=None, verify=mylar.CONFIG.CV_VERIFY, headers=mylar.CV_HEADERS)
    except Exception as e:
        logger.warn('[ERROR: %s] Unable to download image from CV URL link: %s' % (e, url))
        ComicImage = None
    else:
        statuscode = str(r.status_code)

        if statuscode != '200':
            logger.warn('Unable to download image from CV URL link: %s [Status Code returned: %s]' % (url, statuscode))
            coversize = 0
            ComicImage = None
        else:
            data = r.content
            img = Image.open(BytesIO(data))
            imdata = scale_image(img, "JPEG", 600)
            ComicImage = str(base64.b64encode(imdata), 'utf-8')

    return ComicImage

def load_image(filename, resize=600):
    #logger.info('filename: %s' % filename)
    # used to load an image from file for display using the getimage method (w/out extracting) ie. series detail cover page
    with open(filename, 'rb') as i:
        imagefile = i.read()
    img = Image.open( BytesIO( imagefile) )
    imdata = scale_image(img, "JPEG", resize)
    try:
        ComicImage = str(base64.b64encode(imdata), 'utf-8')
        RawImage = imdata
    except Exception as e:
        ComicImage = str(base64.b64encode(imdata + "==="), 'utf-8')
        RawImage = imdata + "==="

    return ComicImage
