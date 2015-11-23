"""
A python class to manage fetching and caching of images by URL
"""

"""
Copyright 2012-2014  Anthony Beville

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sqlite3 as lite
import os
import datetime
import shutil
import tempfile
import urllib2, urllib

try: 
	from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest
	from PyQt4.QtCore import QUrl, pyqtSignal, QObject, QByteArray
	from PyQt4 import  QtGui
except ImportError:
	# No Qt, so define a few dummy QObjects to help us compile
	class QObject():
		def __init__(self,*args):
			pass
	class QByteArray():
		pass
	class pyqtSignal():
		def __init__(self,*args):
			pass
		def emit(a,b,c):
			pass

from settings import ComicTaggerSettings 

class ImageFetcherException(Exception):
	pass

class ImageFetcher(QObject):
	
	fetchComplete = pyqtSignal( QByteArray , int)


	def __init__(self ):
		QObject.__init__(self)

		self.settings_folder = ComicTaggerSettings.getSettingsFolder()
		self.db_file = os.path.join( self.settings_folder, "image_url_cache.db" )
		self.cache_folder = os.path.join( self.settings_folder, "image_cache" )
		
		if not os.path.exists( self.db_file ):
			self.create_image_db()

	def clearCache( self ):
		os.unlink( self.db_file )
		if os.path.isdir( self.cache_folder ):
			shutil.rmtree( self.cache_folder )


	def fetch( self, url, user_data=None, blocking=False  ):
		"""
		If called with blocking=True, this will block until the image is 
		fetched.
		
		If called with blocking=False, this will run the fetch in the 
		background, and emit a signal when done
		"""

		self.user_data = user_data
		self.fetched_url = url
		
		# first look in the DB
		image_data = self.get_image_from_cache( url )
		
		if blocking:
			if image_data is None:
				try:
					image_data = urllib.urlopen(url).read()
				except Exception as e:
					print e
					raise ImageFetcherException("Network Error!")

			# save the image to the cache
			self.add_image_to_cache( self.fetched_url, image_data )	
			return image_data
		
		else:
			
			# if we found it, just emit the signal asap
			if image_data is not None:
				self.fetchComplete.emit( QByteArray(image_data), self.user_data )
				return
			
			# didn't find it.  look online
			self.nam = QNetworkAccessManager()
			self.nam.finished.connect(self.finishRequest)
			self.nam.get(QNetworkRequest(QUrl(url)))
			
			#we'll get called back when done...
		
		

	def finishRequest(self, reply):
		
		# read in the image data
		image_data = reply.readAll()
		
		# save the image to the cache
		self.add_image_to_cache( self.fetched_url, image_data )	

		self.fetchComplete.emit( QByteArray(image_data), self.user_data )

		
		
	def create_image_db( self ):
		
		# this will wipe out any existing version
		open( self.db_file, 'w').close()

		# wipe any existing image cache folder too
		if os.path.isdir( self.cache_folder ):
			shutil.rmtree( self.cache_folder )
		os.makedirs( self.cache_folder )

		con = lite.connect( self.db_file )
		
		# create tables 
		with con:
			
			cur = con.cursor()    

			cur.execute("CREATE TABLE Images(" +
							"url TEXT," +
							"filename TEXT," +
							"timestamp TEXT," +
							"PRIMARY KEY (url) )" 
						)


	def add_image_to_cache( self, url, image_data ):

		con = lite.connect( self.db_file )

		with con:
			
			cur = con.cursor()    
			
			timestamp = datetime.datetime.now()
			
			tmp_fd, filename = tempfile.mkstemp(dir=self.cache_folder, prefix="img")
			f = os.fdopen(tmp_fd, 'w+b')
			f.write( image_data )		
			f.close()
			
			cur.execute("INSERT or REPLACE INTO Images VALUES( ?, ?, ? )" ,
							(url,
							filename,
							timestamp ) 
			            )

	def get_image_from_cache( self, url ):
		
		con = lite.connect( self.db_file )
		with con:
			cur = con.cursor() 
			
			cur.execute("SELECT filename FROM Images WHERE url=?", [ url ])
			row = cur.fetchone()

			if row is None :
				return None
			else:
				filename = row[0]
				image_data = None

				try:
					with open( filename, 'rb' ) as f: 
						image_data = f.read()
						f.close()			
				except IOError as e:
					pass
				
				return image_data




