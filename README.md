Mylar is an automated Comic Book (cbr/cbz) downloader program heavily-based on the Headphones template and logic (which is also based on Sick-Beard).

This program is considered an "Alpha release". It is not bug-free, but it does work!

## Requirements
- At least Python version 2.7.9 (3.x is not supported)
- ComicVine API key (found [here](https://comicvine.gamespot.com/api/) - program will have limited to no functionality without it

## Usage
To start the program, type `python Mylar.py` inside the root of the Mylar directory. Typing `python Mykar.py --help` will give a list of available options.

Once it's started, navigate to localhost:8090 in your web browser (or whatever IP the machine that has Mylar is on).

Helpful hints:
- Add a comic (series) using the Search button or the Pullist
- Ensure Comic Location is specified in settings
  - Mylar auto-creates the Comic Series directories under the Comic Location. The directory is displayed on the Comic Detail page).
- Restart Mylar after any settings changes, or else errors will occur 
- A search provider needs to be specified to perform any search-related functions
- Enabling 'Automatically Mark Upcoming Issues as Wanted' in settings will mark any **NEW** comic from the Pullist that is on your 'watchlist' as wanted
- If adding a comic fails with "Error", submit a bug and it will be checked out (usually an easy fix)
- For the most up-to-date build, use the Development build
  - Master doesn't get updated as frequently (> month), and Development is usually stable

The Mylar Forums are also online @ http://forum.mylarcomics.com

Please submit issues via Git for any outstanding problems that need attention.

## Post-processing
 (Post-Processing is similar to the way SickBeard handles it.)

- Within the post-processing/ folder of Mylar there are 2 files (autoProcessComics.py and autoProcessComics.cfg.sample)
- Within the post-processing/ folder of Mylar there are 2 directories (nzbget, sabnzbd) and within each of these client folders is a ComicRN.py script that is to be used with the respective download client.
- Edit (put in your Mylar host, port, login and password (if required), and ssl(0 for no, 1 for yes) and rename the autoProcessComics.cfg.sample to autoProcessComics.cfg. 
- Copy autoProcessComics.py, autoProcessComics.cfg and the respective ComicRN.py into your SABnzbd/NZBGet scripts directory (or wherever your download client stores its scripts).
- Make sure SABnzbd/NZBGet is setup to have a 'comic-related' category that points it to the ComicRN.py script that was just moved. 
- Ensure in Mylar that the category is named exactly the same.

## Renaming files and folders
You can now specify how Mylar creates the names of files and folders.

### Folder Format
- If left blank, it will default to just using the default Comic Directory 
  - Will create subdirectories in the format `ComicName-(Year)`
- You can do multi-levels as well - so you could do $Publisher/$Series/$Year to have it setup like DC Comics/Batman/2011 (as an example)
- Folder Format **is** used on every Add Series / Refresh Series request
  - Enabling `Renaming` has no bearing on this, so make sure if you're not using the default, that it's what you want.

### File Format
- If left blank, Mylar will use the original file and not rename at all
  - This includes replacing spaces, and zero suppression (both renaming features)

You can contribute by sending in your bug reports / enhancement requests. Telling us what's working for you helps too!

## Screenshots
The Main page ...
![preview thumb](http://i.imgur.com/GLGMj.png)

The Search page ...
![preview thumb](http://i.imgur.com/EM21C.png)

The Comic Detail page ...
![preview thumb](http://i.imgur.com/6z5mH.png)
![preview thumb](http://i.imgur.com/ETuXp.png)

The Pull page ...
![preview thumb](http://i.imgur.com/VWTDQ.png)

The Config screen ...
![preview thumb](http://i.imgur.com/nQjIN.png)


