#!/usr/bin/python

#   ComicBook Renamer v.1.01a (the 'a' means 'alpha')

# This is an add-on script for SABnzbd
# Used in conjunction with several other scripts
# it will allow for almost complete automization for downloading
# comics and sorting/moving them into the correct location.

# ---------
#-----BLURB
# In order to use this as it was intended, Mylar is required.
# Until integration is fully completed, change the settings below
# as required. Save the file into your scripts (usually sabnzbd/scripts) 
# directory of your SABnzbd install.

# In SABnzbd:
# create a category - call it whatever you want (ie.Comics).
# point the default dir to wherever you want - but make sure it is identical
# to the "Path to root of Comics directory" indicated in CONFIG below.

# In Mylar: 
# Sabnzbd tab (in the Configuration):
# Set category to same thing set in SABnzbd
#
# Quality & Post Processing tab (in the Configuration):
# Check off the option to  'Rename Files' 
# 

#--------END BLURB
#----CONFIG SECTION

# Path to root of Comics directory (include trailing /)
comdir = '/mount/mediavg/Comics/'

#----SETTINGS SECTION

# Integrate with Mylar (yes/no)
# If this is set to "yes", will integrate into Mylar for finding series information, etc.
# setting this to "no" will enable stand-alone SABnzbd integration
mylaron = "yes"

# Replace spaces?
repblank = "yes"
# If 'yes', what character do you want me to replace with.
# - Be careful, weird characters will bugger things up and there's no 
# also be sure to put the character inbetween single quotations.
# NB. this doesn't work...currently only is set for to replace spaces
#   with _
repwith = '_'

# Remove crap from filename (ie. c2c, noads, rlsgroup, pxcount, etc)
# If this is set to "no", filename will not be renamed at all.
remcrap = "yes"


# Append Series / Comic year to respective title directory and filename.
# it will appear as : someComic (2012) / someComic 001 (2009).cbz
# THIS WILL ONLY WORK WHEN USED WITH MYLAR.
comicyearopt = "yes"

# how do you want issues (0 digit, 1 digit, 2 digits) to handle zero suppression
# if set to leave, will not expand zeros...
# ....   if set to 0 digit: #1 will be #1,  #10 will be #10,  #100 will be #100
# ....   if set to 1 digit: #1 will be #01, #10 will be #010, #100 will be #100
# ....   if set to 2 digit: #1 will be #001, #10 will be #010, #100 will be #100
zerosup = "2"

# ----------

# ---Code---

import os
import shutil
import sys
import getopt
import fnmatch
import re


if mylaron == "yes":
    fullp = sys.argv[1]
    filen = sys.argv[3]
else:
    fullp = sys.argv[1]
    filen = sys.argv[3]
filen = filen.replace('_',' ')
lengthfile = len(filen) - 4
#if filen[:-4] == ".cbr" or filen[:-4] == ".cbz": filen[:lengthfile]
print ("Mylar - ComicRenamer Script - v1.0a")
print ("passed name from SAB: " + str(filen) )
    #print ("extension of file: " + str(fullp) )
    #let's narrow search down - take out year (2010), (2011), etc
    #let's check for first occurance of '(' as generally indicates
    #that the 'title' has ended
comlen = filen.find(' (')
comsub = filen[:comlen]
#print("first bracket occurs at position: " + str(comlen))
print("actual name with iss: " + str(comsub))
yrstart = int(comlen + 2)
#print ("series year starts at position: " + str(yrstart))
lenyear = len(filen)
issyr = filen.find(') (')
comyear = filen[yrstart:issyr]
comyear = comyear.replace(")", "")
print ("actual year of series (passed from SAB): " + str(comyear))
issst = int(issyr + 2)
#print ("issue year starts at position: " + str(issst))
issyear = filen[issst:]
print ("year of publication of this issue (passed from SAB): " + str(issyear))
    #we need to now determine the last position BEFORE the issue number
    #take length of findcomic (add 1 for space) and subtract comlen
    #will result in issue
comspos = comsub.rfind(" ")
    #print ("last space @ position: " + str(comspos) )
    #print ("COMLEN: " + str(comlen) )
comiss = comsub[comspos:comlen]
    # -- we need to change if there is no space after issue #
    # -- and bracket ie...star trek tng 1(c2c)(2012) etc
if (comspos-comlen) > 3:
    print ("invalid length detected..attempting to adjust")
    # --
print ("the comic issue is actually: #" + str(comiss))
splitit = []
splitcomp = []
comyx = comsub[:comspos]
print ("comyx: " + str(comyx))
if str(comyx[:3]).lower() == "the":
    print ("THE word detected...attempting to adjust pattern matching")
    splitMOD = comyx[4:]
    splitit = splitMOD.split(None)
    

# issue zero-suppression here
if zerosup == "0": zeroadd = ""
elif zerosup == "1": zeroadd = "0"
elif zerosup == "2": zeroadd = "00"


if str(len(comiss)) > 1:
    if int(comiss) < 10:
        print ("issue detected less than 10")
        prettycomiss = str(zeroadd) + str(int(comiss))
        print ( str(prettycomiss) + "...zeroadd level set to:" + str(zeroadd))
    elif int(comiss) >= 10 and int(comiss) < 100:
        print ("issue detected greater than 10, but less than 100")
        if zerosup == "0": zeroadd = ""
        elif zerosup == "1": zeroadd = ""
        elif zerosup == "2": zeroadd = "0"
        prettycomiss = str(zeroadd) + str(int(comiss))
        print ( str(prettycomiss) + "..zeroadd level set to:" + str(zeroadd))
    else:
        print ("issue detected greater than 100")
        prettycomiss = str(comiss)
else:
    print ("issue length error - cannot proceed at the moment.")



# replace section
if remcrap == "no": compath = str(comdir) + sys.argv[3]
if remcrap == "yes":
    compath = str(comdir) + str(comyx)
if comicyearopt == "yes":
    if comyear == "":
        comyear = "2012"
    comyear = "(" + str(comyear) + ")"
    compath = str(compath) + " " + str(comyear)
    comicname = str(comyx) + " " + str(prettycomiss) + " " + str(issyear)
if comicyearopt == "no":
    comicname = str(comyx) + " " + str(prettycomiss)

if repblank == "yes":
    comyx = comyx.replace(' ', '_' )
    filen = filen.replace(' ', '_' )
    comicname = comicname.replace(' ', '_' )
    compath = str(comdir) + str(comyx)
    if comicyearopt == "yes":
        compath = str(compath) + '_' + str(comyear)

print ("The directory should be: " + str(compath))
print ("filename should be: " + str(comicname) )

if os.path.isdir(str(compath)):
    print("Directory exists!")
else:
    print ("Directory doesn't exist!")
    try:
        os.makedirs(str(compath))
        print ("Directory successfully created at: " + str(compath))
    except OSError.e:
        if e.errno != errno.EEXIST:
            raise

#let's change to downloaded path
maindir = str(fullp)

#set up comic book .extensions
extensions = ('.cbr', '.cbz')

countit=0

matches = []
for root, dirnames, filenames in os.walk(maindir):
    for filename in filenames:
        if filename.lower().endswith(extensions):
            confile = filename.replace(' ','_')
            if str(comyx).lower() in str(confile).lower():
                #print ("Found: " + str(filename))
                ext = os.path.splitext(filename)[1]
                newf = str(comicname) + str(ext).lower()
                print ("New filename: " + str(newf) )
                src_file = os.path.join(maindir, filename)
                dst_file = os.path.join(compath, newf)
                shutil.move(src_file, dst_file)
                if maindir is not "/" or maindir is not comdir:
                    shutil.rmtree(maindir)
                    print ("Removed useless directory: " + maindir)
                else:
                    print ("incorrect directory passed to Removal: " + maindir)
            countit+=1

