import sys
import zipfile
import os
import subprocess
from zipfile import BadZipFile

results = subprocess.run(['find', '.', '-iname', '*.cbz'], universal_newlines = True, stdout=subprocess.PIPE)

for result in results.stdout.splitlines():
    tagged = 0
    target_zip = str(result)
#    print("file: %s" % target_zip)
    try:
        with zipfile.ZipFile(target_zip) as zip_file:
            for member in zip_file.namelist():
                if 'ComicInfo.xml' in member:
                    tagged = 1
            if tagged == 0:
                print("Filename %s is not metatagged" % target_zip)
            elif tagged == 1:
                next
#                print("filename %s is correctly metatagged" % target_zip)
            else:
                print("Something's not right! %s" % target_zip)
    except BadZipFile:
        print("%s is a bad zipfile!" % target_zip)        

