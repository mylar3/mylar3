#!/usr/bin/env python
#
##############################################################################
### SABNZBD POST-PROCESSING SCRIPT                                         ###
#
# Move and rename comics according to Mylar's autoProcessComics.cfg
#
# NOTE: This script requires Python to be installed on your system.
##############################################################################

#module loading
import sys
import autoProcessComics

comicrn_version = "1.01"

#the code.
if len(sys.argv) < 2:
    print "No folder supplied - is this being called from SABnzbd or NZBGet?"
    sys.exit()
elif len(sys.argv) >= 3:
    sys.exit(autoProcessComics.processIssue(sys.argv[1], sys.argv[3], sys.argv[7], comicrn_version=comicrn_version))
else:
    sys.exit(autoProcessComics.processIssue(sys.argv[1], comicrn_version=comicrn_version))

