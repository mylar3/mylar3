Mylar is an automated Comic Book (cbr/cbz) downloader program heavily-based on the Headphones template and logic (which is also based on Sick-Beard).

Yes, it does work, yes there are still bugs, and for that reson I still consider it the definition of an 'Alpha Release'.

-REQUIREMENTS-
- at least version 2.7.9 Python for proper usage (3.x is not supported).

                                                     ** NEW ** 
                   You will need to get your OWN ComicVine API Key for this application to fully work. 
                      Failure to do this will result in limited (to No) ability when using Mylar.

To start it, type in 'python Mylar.py' from within the root of the mylar directory. Adding a --help option to the command will give a list of available options.

Once it's started, navigate to to localhost:8090 in your web browser (or whatever IP the machine that has Mylar is on).

Here are some helpful hints hopefully:
- Add a comic (series) using the Search button, or using the Pullist. 
- Make sure you specify Comic Location in the Configuration!
 (Mylar auto-creates the Comic Series directories under the Comic Location. The directory is displayed on the Comic Detail page).
- If you make any Configuration changes, shutdown Mylar and restart it or else errors will occur - this is an outstanding bug.
- You need to specify a search-provider in order to perform any search-related function!
- In the Configuration section, if you enable 'Automatically Mark Upcoming Issues as Wanted' it will mark any NEW comic from the pullist that is on your 'watchlist' as wanted.
- There are times when adding a comic it will fail with an 'Error', submit a bug and it will be checked out (usually an easy fix).
- For the most up-to-date build, use the Development build. Master doesn't get updated as frequently (> month), and Development is usually fairly stable.

The Mylar Forums are also online @ http://forum.mylarcomics.com

Please submit issues via git for any outstanding problems that need attention.

Post-Processing
 (Post-Processing is similar to the way SickBeard handles it.)

- Within the post-processing/ folder of Mylar there are 2 files (autoProcessComics.py and autoProcessComics.cfg.sample)
- Within the post-processing/ folder of Mylar there are 2 directories (nzbget, sabnzbd) and within each of these client folders, is a ComicRN.py script that is to be used with the respective download client.
- Edit (put in your Mylar host, port, login and password (if required), and ssl(0 for no, 1 for yes) and rename the autoProcessComics.cfg.sample to autoProcessComics.cfg. 
- Copy autoProcessComics.py, autoProcessComics.cfg and the respective ComicRN.py into your SABnzbd/NZBGet scripts directory (or wherever your download client stores it's scripts).
- Make sure SABnzbd/NZBGet is setup to have a 'comic-related' category that points it to the ComicRN.py script that was just moved. 
- Ensure in Mylar that the category is named exactly the same.

Renaming
- You can now specify Folder / File Formats.
- Folder Format - if left blank, it will default to just using the default Comic Directory [ and creating subdirectories beneath in the format of ComicName-(Year) ]
  You can do multi-levels as well - so you could do $Publisher/$Series/$Year to have it setup like DC Comics/Batman/2011 (as an example)
- File Format - if left blank, Mylar will use the original file and not rename at all. This includes replacing spaces, and zero suppression (both renaming features).
- Folder Format IS used on every Add Series / Refresh Series request. Enabling Renaming has no bearing on this, so make sure if you're not using the default, that it's what you want.


Please help make it better, by sending in your bug reports / enhancement requests or just say what's working for you.

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


