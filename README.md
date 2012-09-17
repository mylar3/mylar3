Mylar is an automated Comic Book (cbr/cbz) downloader program heavily-based on the Headphones template and logic (which is also based on Sick-Beard). Please note, before you laugh hysterically at my code, I have only started learning python (<2 months ago) and this is my first 'pet project.'

Yes, it does work for the most part but it is the pure definition of an 'Alpha Release'.

To start it, type in 'python Mylar.py' from within the root of the mylar directory. Adding a --help option to the command will give a list of available options.

Once it's started, navigate to to localhost:8090 in your web browser (or whatever IP the machine that has Mylar is on).

Here are some helpful hints hopefully:
- Add a comic (series) using the Search button, or using the Pullist. 
- Make sure you specify Comic Location as well as your SABnzbd settings in the Configuration!
 (Mylar auto-creates the Comic Series directories under the Comic Location. The directory is displayed on the Comic Detail page).
- If you make any Configuration changes, shutdown Mylar and restart it or else errors will occur - this is a current bug.
- You need to specify a search-provider in order to get the downloads to send to SABnzbd. If you don't have either listed, choose Experimental!
- To get renaming to work (somewhat working), enable the option in the Configuration then move the ComicRN.py script located in mylar/sabnzbd to your sabnzbd/scripts directory.
  Edit the file, making sure to read the documentation included and that it's correct.
- In the Configuration section, if you enable 'Automatically Mark Upcoming Issues as Wanted' it will mark any NEW comic from the pullist that is on your 'watchlist' as wanted.
- There are times when adding a comic it will fail with an 'Error', submit a bug and it will be checked out (usually an easy fix).


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
