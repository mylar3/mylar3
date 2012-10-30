#!/usr/bin/env python




import sys
import autoProcessComics

if len(sys.argv) < 2:
    print "No folder supplied - is this being called from SABnzbd?"
    sys.exit()
elif len(sys.argv) >= 3:
    autoProcessComics.processEpisode(sys.argv[1], sys.argv[3])
else:
    autoProcessComics.processEpisode(sys.argv[1])