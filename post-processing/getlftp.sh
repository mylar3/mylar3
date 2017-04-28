#!/bin/bash

##-- start configuration

#this needs to be edited to the full path to the get.conf file containing the torrent client information
configfile=''

#this is the temporary location where it will make sure the conf is safe for use (by default this should be fine if left alone)
configfile_secured='/tmp/get.conf'

##-- end configuration


## --- don't change stuff below here ----

# check if the file contains something we don't want
if egrep -q -v '^#|^[^ ]*=[^;]*' "$configfile"; then
  # echo "Config file is unclean, cleaning it..." >&2
  # filter the original to a new file
  egrep '^#|^[^ ]*=[^;&]*'  "$configfile" > "$configfile_secured"
  configfile="$configfile_secured"
fi

# now source it, either the original or the filtered variant
source "$configfile"

cd $LOCALCD
filename="$1"

if [[ "${filename##*.}" == "cbr" || "${filename##*.}" == "cbz" ]]; then
    LCMD="pget -n 6 '$1'"
else
    LCMD="mirror -P 2 --use-pget-n=6 '$1'"
fi

if [[ -z $KEYFILE ]]; then
    PARAM="$USER $PASSWD"
else
    PARAM="$USER $KEYFILE"
fi

lftp<<END_SCRIPT
open sftp://$HOST:$PORT
user $PARAM
$LCMD
bye
END_SCRIPT

echo "Successfully ran script."
