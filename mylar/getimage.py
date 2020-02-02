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
    modtime = os.path.getmtime(location)
    low_infile = 999999
    local_filename = os.path.join(mylar.CONFIG.CACHE_DIR, 'temp_notif')
    cb_filename= None
    cb_filenames=[]
    metadata = None
    if single is True:
        if location.endswith(".cbz"):
            location_in = zipfile.ZipFile(location)
        else:
            location_in = rarfile.RarFile(location)
        try:
            for infile in location_in.infolist():
                #if cover == 'found': break

                tmp_infile = re.sub("[^0-9]","", infile.filename).strip()
                extension = infile.filename[-4:]
                if tmp_infile == '':
                    pass
                elif int(tmp_infile) < int(low_infile):
                    low_infile = tmp_infile
                    low_infile_name = infile.filename
                if infile.filename == 'ComicInfo.xml':
                    logger.fdebug('Extracting ComicInfo.xml to display.')
                    metadata = location_in.read(infile.filename)
                    if cover == 'found': break
                if any(['000.' in infile.filename, '00.' in infile.filename]) and infile.filename.endswith(pic_extensions) and cover == "notfound":
                    cb_filename = infile.filename
                    cover = "found"
                elif any(['00a' in infile.filename, '00b' in infile.filename, '00c' in infile.filename, '00d' in infile.filename, '00e' in infile.filename]) and infile.filename.endswith(pic_extensions) and cover == "notfound":
                    altlist = ('00a', '00b', '00c', '00d', '00e')
                    for alt in altlist:
                        if alt in infile.filename:
                            cb_filename = infile.filename
                            cover = "found"
                        break

                elif (any(['001.jpg' in infile.filename, '001.png' in infile.filename, '001.webp' in infile.filename, '01.jpg' in infile.filename, '01.png' in infile.filename, '01.webp' in infile.filename]) or all(['0001' in infile.filename,  infile.filename.endswith(pic_extensions)]) or all(['01' in infile.filename, infile.filename.endswith(pic_extensions)])) and cover == "notfound":
                    cb_filenames.append(infile.filename)
                    #cover = "found"
            if cover != "found" and len(cb_filenames) > 0:
                logger.fdebug('Invalid naming sequence for jpgs discovered. Attempting to find the lowest sequence and will use as cover (it might not work). Currently : %s' % (low_infile_name))
                cb_filename = low_infile_name
                cover = "found"

        except Exception as e:
            logger.error('[ERROR] Unable to properly retrieve the cover. It\'s probably best to re-tag this file : %s' % e)
            return

        logger.info('cb_filename set to : %s' % cb_filename)

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
