#!/usr/bin/env python




import sys, os
import autoProcessComics

if len(sys.argv) < 2:
    if os.getenv('NZBPP_NZBCOMPLETED', 0):
        #if this variable is set, we're being called from NZBGet
        autoProcessComics.processEpisode(os.getenv('NZBPP_DIRECTORY'), os.getenv('NZBPP_NZBFILENAME'))
    else:
        print "No folder supplied - is this being called from SABnzbd or NZBGet?"
        sys.exit()
elif len(sys.argv) >= 3:
    sys.exit(autoProcessComics.processEpisode(sys.argv[1], sys.argv[3]))
else:
    sys.exit(autoProcessComics.processEpisode(sys.argv[1]))
