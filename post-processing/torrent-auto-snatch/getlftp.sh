#!/bin/bash

#load the value from the conf.
HOST="$host"
PORT="$port"
USER="$user"
PASSWD="$passwd"
LOCALCD="$localcd"
KEYFILE="$keyfile"
filename="$downlocation"

cd $LOCALCD

if [[ "${filename##*.}" == "cbr" || "${filename##*.}" == "cbz" ]]; then
    LCMD="pget -n 6 '$filename'"
else
    LCMD="mirror -P 2 --use-pget-n=6 '$filename'"
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
