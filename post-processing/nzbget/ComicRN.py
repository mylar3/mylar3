#!/usr/bin/env python
#
##############################################################################
### NZBGET POST-PROCESSING SCRIPT                                          ###
#
# Move and rename comics according to Mylar's autoProcessComics.cfg 
#
# NOTE: This script requires Python to be installed on your system.
##############################################################################
### OPTIONS                                                                ###
### NZBGET POST-PROCESSING SCRIPT                                          ###
##############################################################################

import sys, os
import autoProcessComics

# NZBGet V11+
# Check if the script is called from nzbget 11.0 or later
if os.environ.has_key('NZBOP_SCRIPTDIR') and not os.environ['NZBOP_VERSION'][0:5] < '11.0':
    
    # NZBGet argv: all passed as environment variables.
    # Exit codes used by NZBGet
    POSTPROCESS_PARCHECK=92
    POSTPROCESS_SUCCESS=93
    POSTPROCESS_ERROR=94
    POSTPROCESS_NONE=95

    #Start script
    result = autoProcessComics.processIssue(os.environ['NZBPP_DIRECTORY'], os.environ['NZBPP_NZBNAME'])


elif len(sys.argv) == NZBGET_NO_OF_ARGUMENTS:
   result = autoProcessComics.processIssue(sys.argv[1], sys.argv[2], sys.argv[3])
	
if result == 0:
    if os.environ.has_key('NZBOP_SCRIPTDIR'): # log success for nzbget
        sys.exit(POSTPROCESS_SUCCESS)
	
else:
    if os.environ.has_key('NZBOP_SCRIPTDIR'): # log fail for nzbget
        sys.exit(POSTPROCESS_ERROR)












