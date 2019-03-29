## ![Mylar Logo](https://github.com/evilhero/mylar/blob/master/data/images/mylarlogo.png) Mylar

Mylar is an automated Comic Book (cbr/cbz) downloader program for use with NZB and torrents written in python. It supports SABnzbd, NZBGET, and many torrent clients in addition to DDL.

It will allow you to monitor weekly pull-lists for items belonging to user-specific series to download, as well as being able to monitor story-arcs. Support for TPB's and GN's is also now available.


This program is considered an "Alpha release" but is in development still. It is not bug-free, but it does work!

## Support & Discussion
You are free to join the Mylar support community on IRC where you can ask questions, hang around and discuss anything related to Mylar.

1. Use any IRC client and connect to the Freenode server, `irc.freenode.net`.
2. Join the `#mylar` channel.

The Mylar Forums are also online @ https://forum.mylarcomics.com

**Issues** can be reported on the Github issue tracker, provided that you:
- Search existing recent OPEN issues. If an issue is open from a year ago, please don't add to it.
- Always follow the issue template!
- Close your issue when it's solved!

## Requirements
- At least Python version 2.7.9 (3.x is not supported)
- ComicVine API key (found [here](https://comicvine.gamespot.com/api/) - program will have limited to no functionality without it

## Usage
To start the program, type `python Mylar.py` inside the root of the Mylar directory. Typing `python Mylar.py --help` will give a list of available options.

Once it's started, navigate to http://localhost:8090 in your web browser (or whatever IP the machine that has Mylar is on).

Helpful hints:
- Ensure `Comic Location` is specified in the configuration (_Configuration --> Web Interface --> Comic Location_)
  - Mylar auto-creates the Comic Series directories under the Comic Location. The directory is displayed on the Comic Detail page).
  - If you do not want directories to be created until there are issues present, set `create_folders = False` in the config.ini.
- A search provider needs to be specified to perform any search-related functions
- Enabling `Automatically Mark Upcoming Issues as Wanted` in settings will mark any **NEW** comic from the Pullist that is on your 'watchlist' as wanted
- Add a comic (series) using the Search button or via the Pullist. 
- If you know the CV comicid, enter the full id into the search box (ie. `4050-XXXXX`)
- If adding a comic fails with "Error", submit a bug and it will be checked out (usually an easy fix)
- Post-Processing is for adding new issues into existing series on your watchlist, Import is for adding files for series that don't exist on your watchlist into your watchlist
- For the most up-to-date build, use the Development build
  - Master doesn't get updated as frequently (> month), and Development is usually stable

## Post-processing
It is imperative that you enable the post-processing option if you require post-processing (_Configuration --> Quality & Post-Processing --> Enable Post-Processing_)

### Newsgroups
There are 2 ways to perform post-processing within Mylar, however you cannot use both options simultaneously. 

**ComicRN**
- You need to enable the Mylar APIKey for this to work (_Configuration --> Web Interface --> API --> Enable API --> Generate --> Save Configuration_).
- Within the post-processing/ folder of Mylar there are 2 files (autoProcessComics.py and autoProcessComics.cfg.sample)
- Within the post-processing/ folder of Mylar there are 2 directories (nzbget, sabnzbd) and within each of these client folders is a ComicRN.py script that is to be used with the respective download client.
- Edit (put in your Mylar host, port, apikey (generated from above), and ssl(0 for no, 1 for yes) and rename the autoProcessComics.cfg.sample to autoProcessComics.cfg. 
- Copy autoProcessComics.py, autoProcessComics.cfg and the respective ComicRN.py into your SABnzbd/NZBGet scripts directory (or wherever your download client stores its scripts).
- Make sure SABnzbd/NZBGet is setup to have a 'comic-related' category that points it to the ComicRN.py script that was just moved. 
- Ensure in Mylar that the category is named exactly the same.

**Completed Download Handling (CDH)**
- For the given download client (SABnzbd / NZBGet) simply click on the Enable Completed Download Handling option.
- For SABnzbd to work, you need to make sure you have a version > 0.8.0 (use the Test Connection button for verification)

### Torrents
There is no completed processing for torrents. There are methods available however:

**Torrent client on same machine as Mylar installation**
- _Configuration tab --> Quality & Post-Processing --> Post-Processing_
- set the post-processing action to copy if you want to seed your torrents, otherwise move
  - Enable Folder Monitoring
  - Folder location to monitor: set to the full location where your finished torrents are downloaded to.
  - Folder Monitor Scan Interval: do NOT set this to < 1 minute. Anywhere from 3-5 minutes should be ample.

**Torrent client on different machine than Mylar**
- Use [harpoon](https://github.com/evilhero/harpoon/) to retrieve items back to your local install as soon as they are completed and have post-processing occur immediately (also works with other automated solutions).
- Any other method that involves having the files localized and then have Folder Monitor monitor the location for files.

**Torrent client (rtorrent/deluge) on different machine than Mylar**
- a built-in option for these clients that will monitor for completion and then perform post-processing on the given items.
- files are located in the `post-processing/torrent-auto-snatch` location within the mylar directory.
- read the read.me therein for configuration / setup.

### DDL
When using DDL, post-processing will be initiated immediately upon successful completion. By default the items are downloaded to the cache directory location and removed after post-processing. However, if you wish to change the default directory location, specify the full directory location in the config.ini `ddl_location` field.

## Renaming files and folders
You can specify how Mylar renames files during post-processing / import in addition to the folders.

### Folder Format
- If left blank or as the default value of `ComicName-(Year)`, it will create subdirectories in the format `ComicName-(Year)`
- You can do multiple directory hiearchies as well - so you could do $Publisher/$Series/$Year to have it setup like DC Comics/Wildman/2011 (as an example)
- Folder Format **is** used on every Add Series / Refresh Series request
  - Enabling `Renaming` has no bearing on this, so make sure if you're not using the default, that it's what you want.

### File Format
- To enable renaming for files, you need to enable the Rename Files option, otherwise, Mylar will use the original file and not rename at all
  - This includes replacing spaces, lowercasing and zero suppression (all renaming features)



_<p align="center">You can contribute by sending in your bug reports / enhancement requests.</br> 
Telling us what's working helps too!</p>_
