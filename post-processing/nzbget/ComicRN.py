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
comicrn_version = "1.01"

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
    if os.environ['NZBOP_VERSION'][0:5] > '13.0':
        if os.environ['NZBPP_TOTALSTATUS'] == 'FAILURE' or os.environ['NZBPP_TOTALSTATUS'] == 'WARNING':
            failit = 1
        else:
            failit = 0
    else:
        #NZBPP_TOTALSTATUS only exists in 13.0 - so if it's not that but greater than 11.0+, we need to use NZBPP_STATUS
        #assume failit = 1 (failed) by default
        failit = 1   
        if os.environ['NZBPP_PARSTATUS'] == '1' or os.environ['NZBPP_UNPACKSTATUS'] == '1':
            print 'Download of "%s" has failed.' % (os.environ['NZBPP_NZBNAME'])
        elif os.environ['NZBPP_UNPACKSTATUS'] in ('3', '4'):
            print 'Download of "%s" has failed.' % (os.environ['NZBPP_NZBNAME'])
        elif os.environ['NZBPP_PARSTATUS'] == '4':
            print 'Download of "%s" requires par-repair.' % (os.environ['NZBPP_NZBNAME'])
        else:
            print 'Download of "%s" has successfully completed.' % (os.environ['NZBPP_NZBNAME'])
            failit = 0

    result = autoProcessComics.processIssue(os.environ['NZBPP_DIRECTORY'], os.environ['NZBPP_NZBNAME'], failed=failit, comicrn_version=comicrn_version)


elif len(sys.argv) == NZBGET_NO_OF_ARGUMENTS:
   result = autoProcessComics.processIssue(sys.argv[1], sys.argv[2], sys.argv[3], comicrn_version=comicrn_version)
	
if result == 0:
    if os.environ.has_key('NZBOP_SCRIPTDIR'): # log success for nzbget
        sys.exit(POSTPROCESS_SUCCESS)
	
else:
    if os.environ.has_key('NZBOP_SCRIPTDIR'): # log fail for nzbget
        sys.exit(POSTPROCESS_ERROR)












