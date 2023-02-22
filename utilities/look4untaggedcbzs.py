from lib2to3.pgen2.token import NEWLINE
import sys
import zipfile
import os
import subprocess
from zipfile import BadZipFile
from pathlib import Path

results = Path().cwd().glob('**/*.cbz')
file1 = open("notags.txt", "a")
file2 = open("badzip.txt", "a")


for result in results:
    tagged = 0
    # with pathlib your result is always going to be
    # a path object
    # making this unnecessary
    target_zip = result
#    print("file: %s" % target_zip)
    try:
        with zipfile.ZipFile(target_zip) as zip_file:
            for member in zip_file.namelist():
                if 'ComicInfo.xml' in member:
                    tagged = 1
            if tagged == 0:
                print('Filename %s is not metatagged' % target_zip)
                stuff= f'Filename {target_zip} is not metatagged' + os.linesep 
                file1.write(stuff)
            elif tagged == 1:
                next
#                print("filename %s is correctly metatagged" % target_zip)
            else:
                print("Something's not right! %s" % target_zip)
    except BadZipFile:
        print("%s is a bad zipfile!" % target_zip)      
        badstuff= f'{target_zip} is a bad zipfile' + os.linesep 
        file2.write(badstuff)

file1.close()
file2.close()
