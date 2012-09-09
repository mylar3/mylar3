# just updating the sqlite db to latest issue / newest pull

from mylar import db


def latestcheck():

        myDB = db.DBConnection()
        comics = myDB.select('SELECT * from comics WHERE LatestIssue = 'None')
