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


def extract_image(location, single=False, imquality=None):
    #location = full path to the cbr/cbz (filename included in path)
    #single = should be set to True so that a single file can have the coverfile
    #        extracted and have the cover location returned to the calling function
    #imquality = the calling function ('notif' for notifications will initiate a resize image before saving the cover)
    if PIL_Found is False:
        return
    cover = "notfound"
    pic_extensions = ('.jpg','.png','.webp')
    issue_ends = ('1','0')
    modtime = os.path.getmtime(location)
    low_infile = 9999999999999
    low_num = 1000
    local_filename = os.path.join(mylar.CONFIG.CACHE_DIR, 'temp_notif')
    cb_filename= None
    cb_filenames=[]
    metadata = None
    if single is True:
        if location.endswith(".cbz"):
            location_in = zipfile.ZipFile(location)
            dir_opt = 'is_dir'
            actual_ext = '.cbz'
        else:
            try:
                location_in = rarfile.RarFile(location)
                dir_opt = 'isdir'
                actual_ext = '.cbr'
            except rarfile.BadRarFile as e:
                logger.warn('[WARNING] %s: %s' % (location,e))
                try:
                    logger.info('Trying to see if this is a zip renamed as a rar: %s' % (location))
                    location_in = zipfile.ZipFile(location)
                    dir_opt = 'is_dir'
                    actual_ext = '.cbz'
                except Exception as e:
                    logger.warn('[EXCEPTION] %s' % e)
                    return
            except:
                logger.warn('[EXCEPTION]: %s' % sys.exec_info()[0])
                return
        try:
            for infile in location_in.infolist():
                if infile.filename == 'ComicInfo.xml':
                    logger.fdebug('Extracting ComicInfo.xml to display.')
                    metadata = location_in.read(infile.filename)
                    if cover == 'found':
                        break

                tmp_infile = re.sub("[^0-9]","", infile.filename).strip()
                if tmp_infile == '':
                    continue
                extension = infile.filename[-4:]
                #logger.fdebug('[%s]issue_ends: %s' % (tmp_infile, tmp_infile.endswith(issue_ends)))
                #logger.fdebug('ext_ends: %s' % infile.filename.lower().endswith(pic_extensions))
                #logger.fdebug('(%s) < (%s) == %s' % (int(tmp_infile), int(low_infile), int(tmp_infile)<int(low_infile)))
                if all([infile.filename.lower().endswith(pic_extensions), int(tmp_infile) < int(low_infile), not getattr(infile, dir_opt)]):
                    low_infile = tmp_infile
                    low_infile_name = infile.filename
                elif any(['00a' in infile.filename, '00b' in infile.filename, '00c' in infile.filename, '00d' in infile.filename, '00e' in infile.filename, '00fc' in infile.filename.lower()]) and infile.filename.endswith(pic_extensions) and cover == "notfound":
                    altlist = ('00a', '00b', '00c', '00d', '00e', '00fc')
                    for alt in altlist:
                        if alt in infile.filename.lower():
                            cb_filename = infile.filename
                            cover = "found"
                            #logger.fdebug('[%s] cover found:%s' % (alt, infile.filename))
                            break
                elif all([tmp_infile.endswith(issue_ends), infile.filename.lower().endswith(pic_extensions), int(tmp_infile) < int(low_infile), cover == 'notfound']):
                    cb_filenames.append(infile.filename)
                    #logger.fdebug('filename set to: %s' % infile.filename)
                    low_infile_name = infile.filename
                    low_infile = tmp_infile
            if cover != "found" and len(cb_filenames) > 0:
                logger.fdebug('Invalid naming sequence for jpgs discovered. Attempting to find the lowest sequence and will use as cover (it might not work). Currently : %s' % (low_infile_name))
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
                wpercent = (600/float(img.size[0]))
                hsize = int((float(img.size[1])*float(wpercent)))
                img = img.resize((600, hsize), Image.ANTIALIAS)
                output = BytesIO()
                img.save(output, format="JPEG")
                ComicImage = str(base64.b64encode(output.getvalue()), 'utf-8')
                output.close()

            except Exception as e:
                logger.warn('[WARNING] Unable to resize existing image: %s' % e)
        else:
            ComicImage = local_filename
    return {'ComicImage': ComicImage, 'metadata': metadata}

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
            wpercent = (600/float(img.size[0]))
            hsize = int((float(img.size[1])*float(wpercent)))
            img = img.resize((600, hsize), Image.ANTIALIAS)
            output = BytesIO()
            img.save(output, format="JPEG")
            ComicImage = str(base64.b64encode(output.getvalue()), 'utf-8')
            output.close()

    return ComicImage

