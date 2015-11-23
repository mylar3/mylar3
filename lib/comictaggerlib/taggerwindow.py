# coding=utf-8
"""
The main window of the ComicTagger app
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

from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import QUrl,pyqtSignal
from PyQt4 import QtNetwork       

import sys
import signal
import locale
import platform
import os
import pprint
import json
import webbrowser
import re
import pickle

from volumeselectionwindow import VolumeSelectionWindow
from comicarchive import MetaDataStyle
from comicinfoxml import ComicInfoXml
from genericmetadata import GenericMetadata
from comicvinetalker import ComicVineTalker, ComicVineTalkerException
from comicarchive import ComicArchive
from crediteditorwindow import CreditEditorWindow
from settingswindow import SettingsWindow
from settings import ComicTaggerSettings
from pagebrowser import PageBrowserWindow
from filenameparser import FileNameParser
from logwindow import LogWindow
from optionalmsgdialog import OptionalMessageDialog
from pagelisteditor import PageListEditor
from fileselectionlist import FileSelectionList
from cbltransformer import CBLTransformer
from renamewindow import RenameWindow
from exportwindow import ExportWindow, ExportConflictOpts
from pageloader import PageLoader
from issueidentifier import IssueIdentifier
from autotagstartwindow import AutoTagStartWindow
from autotagprogresswindow import AutoTagProgressWindow
from autotagmatchwindow import AutoTagMatchWindow
from coverimagewidget import CoverImageWidget
from versionchecker import VersionChecker

import utils
import ctversion

class OnlineMatchResults():
	def __init__(self):
		self.goodMatches = []  
		self.noMatches = []    
		self.multipleMatches = []  
		self.lowConfidenceMatches = []  
		self.writeFailures = []
		self.fetchDataFailures = []
		
class MultipleMatch():
	def __init__( self, ca, match_list):
		self.ca = ca  
		self.matches = match_list  		

class TaggerWindow( QtGui.QMainWindow):
	
	appName = "ComicTagger"
	version = ctversion.version
	
	def __init__(self, file_list, settings, parent = None, opts=None):
		super(TaggerWindow, self).__init__(parent)

		uic.loadUi(ComicTaggerSettings.getUIFile('taggerwindow.ui' ), self)
		self.settings = settings

		#----------------------------------
		# prevent multiple instances
		socket = QtNetwork.QLocalSocket(self) 
		socket.connectToServer(settings.install_id)
		alive = socket.waitForConnected(3000)
		if alive:
			print "Another application with key [{}] is already running".format( settings.install_id)
			# send file list to other instance
			if len(file_list) > 0:
				socket.write(pickle.dumps(file_list))
				if not socket.waitForBytesWritten(3000):
					print socket.errorString().toLatin1()
			socket.disconnectFromServer()			
			sys.exit()
		else:
			# listen on a socket to prevent multiple instances
			self.socketServer = QtNetwork.QLocalServer(self)
			self.socketServer.newConnection.connect(self.onIncomingSocketConnection)
			ok = self.socketServer.listen(settings.install_id)
			if not ok:
				if self.socketServer.serverError() == QtNetwork.QAbstractSocket.AddressInUseError:
					#print "Resetting unresponsive socket with key [{}]".format(settings.install_id)
					self.socketServer.removeServer(settings.install_id)
					ok = self.socketServer.listen(settings.install_id)
				if not ok:
					print "Cannot start local socket with key [{}]. Reason: %s ".format(settings.install_id, self.socketServer.errorString())
					sys.exit()
			#print "Registering as single instance with key [{}]".format(settings.install_id)
		#----------------------------------


		self.archiveCoverWidget = CoverImageWidget( self.coverImageContainer, CoverImageWidget.ArchiveMode )
		gridlayout = QtGui.QGridLayout( self.coverImageContainer )
		gridlayout.addWidget( self.archiveCoverWidget )
		gridlayout.setContentsMargins(0,0,0,0)
					
		self.pageListEditor = PageListEditor( self.tabPages )
		gridlayout = QtGui.QGridLayout( self.tabPages )
		gridlayout.addWidget( self.pageListEditor ) 
		
		#---------------------------
		self.fileSelectionList = FileSelectionList( self.widgetListHolder, self.settings )
		gridlayout = QtGui.QGridLayout( self.widgetListHolder )
		gridlayout.addWidget( self.fileSelectionList )
		
		self.fileSelectionList.selectionChanged.connect( self.fileListSelectionChanged )
		self.fileSelectionList.listCleared.connect( self.fileListCleared )
		self.fileSelectionList.setSorting(self.settings.last_filelist_sorted_column,
										  self.settings.last_filelist_sorted_order)

		# we can't specify relative font sizes in the UI designer, so
		# walk through all the lablels in the main form, and make them
		# a smidge smaller
		for child in self.scrollAreaWidgetContents.children():
			if ( isinstance(child, QtGui.QLabel) ):
				f = child.font()
				if f.pointSize() > 10:
					f.setPointSize( f.pointSize() - 2 )
				f.setItalic( True )
				child.setFont( f )

		self.scrollAreaWidgetContents.adjustSize()
		
		self.setWindowIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('app.png')))

		if opts is not None and opts.data_style is not None and opts.data_style != MetaDataStyle.COMET:
			#respect the command line option tag type
			settings.last_selected_save_data_style = opts.data_style
			settings.last_selected_load_data_style = opts.data_style

		self.save_data_style = settings.last_selected_save_data_style
		self.load_data_style = settings.last_selected_load_data_style

		self.setAcceptDrops(True)
		self.configMenus()
		self.statusBar()	
		self.populateComboBoxes()	

		self.page_browser = None
		self.resetApp()
		
		# set up some basic field validators
		validator = QtGui.QIntValidator(1900, 2099, self)
		self.lePubYear.setValidator(validator)

		validator = QtGui.QIntValidator(1, 12, self)
		self.lePubMonth.setValidator(validator)
		
		validator = QtGui.QIntValidator(1, 99999, self)
		self.leIssueCount.setValidator(validator)
		self.leVolumeNum.setValidator(validator)
		self.leVolumeCount.setValidator(validator)
		self.leAltIssueNum.setValidator(validator)
		self.leAltIssueCount.setValidator(validator)
		
		#TODO set up an RE validator for issueNum that allows
		# for all sorts of wacky things

		# tweak some control fonts	
		utils.reduceWidgetFontSize( self.lblFilename, 1 )
		utils.reduceWidgetFontSize( self.lblArchiveType )
		utils.reduceWidgetFontSize( self.lblTagList )
		utils.reduceWidgetFontSize( self.lblPageCount )

		#make sure some editable comboboxes don't take drop actions
		self.cbFormat.lineEdit().setAcceptDrops(False)
		self.cbMaturityRating.lineEdit().setAcceptDrops(False)

		# hook up the callbacks		
		self.cbLoadDataStyle.currentIndexChanged.connect(self.setLoadDataStyle)
		self.cbSaveDataStyle.currentIndexChanged.connect(self.setSaveDataStyle)
		self.btnEditCredit.clicked.connect(self.editCredit)	
		self.btnAddCredit.clicked.connect(self.addCredit)	
		self.btnRemoveCredit.clicked.connect(self.removeCredit)	
		self.twCredits.cellDoubleClicked.connect(self.editCredit)
		self.connectDirtyFlagSignals()
		self.pageListEditor.modified.connect(self.setDirtyFlag)		
		self.pageListEditor.firstFrontCoverChanged.connect( self.frontCoverChanged )
		self.pageListEditor.listOrderChanged.connect( self.pageListOrderChanged )
		self.tabWidget.currentChanged.connect( self.tabChanged )
		
		self.updateStyleTweaks()

		self.show()
		self.setAppPosition()
		if self.settings.last_form_side_width != -1:
			self.splitter.setSizes([ self.settings.last_form_side_width , self.settings.last_list_side_width])
		self.raise_()
		QtCore.QCoreApplication.processEvents()
		self.resizeEvent( None )

		self.splitter.splitterMoved.connect( self.splitterMovedEvent )

		self.fileSelectionList.addAppAction( self.actionAutoIdentify )
		self.fileSelectionList.addAppAction( self.actionAutoTag )
		self.fileSelectionList.addAppAction( self.actionCopyTags )
		self.fileSelectionList.addAppAction( self.actionRename )
		self.fileSelectionList.addAppAction( self.actionRemoveAuto )
		self.fileSelectionList.addAppAction( self.actionRepackage )
		
		if len(file_list) != 0:
			self.fileSelectionList.addPathList( file_list )
			
		if self.settings.show_disclaimer:
			checked = OptionalMessageDialog.msg(  self, "Welcome!",
								"""
								Thanks for trying ComicTagger!<br><br>
								Be aware that this is beta-level software, and consider it experimental.
								You should use it very carefully when modifying your data files.  As the
								license says, it's "AS IS!"<br><br>
								Also, be aware that writing tags to comic archives will change their file hashes,
								which has implications with respect to other software packages.  It's best to
								use ComicTagger on local copies of your comics.<br><br>
								Have fun!
								"""
								)
			self.settings.show_disclaimer = not checked

		if self.settings.ask_about_usage_stats:
			reply = QtGui.QMessageBox.question(self, 
				 self.tr("Anonymous Stats"), 
				 self.tr(
						"Is it okay if ComicTagger occasionally sends some anonymous usage statistics?  Nothing nefarious, "
						"just trying to get a better idea of how the app is being used.\n\nThanks for your support!"
						),
				 QtGui.QMessageBox.Yes|QtGui.QMessageBox.Default, QtGui.QMessageBox.No )
				 
			if reply == QtGui.QMessageBox.Yes:		
				self.settings.send_usage_stats = True
			self.settings.ask_about_usage_stats = False
				
		if self.settings.check_for_new_version:
			self.checkLatestVersionOnline()
					
	def sigint_handler(self, *args):
		# defer the actual close in the app loop thread
		QtCore.QTimer.singleShot(200, self.close)

	def resetApp( self ):

		self.archiveCoverWidget.clear()
		self.comic_archive = None
		self.dirtyFlag = False
		self.clearForm()
		self.pageListEditor.resetPage()
		if self.page_browser is not None:
			self.page_browser.reset()
		self.updateAppTitle()
		self.updateMenus()
		self.updateInfoBox()
		
		self.droppedFile = None
		self.page_loader = None

		
	def updateAppTitle( self ):
			
		if self.comic_archive is None:
			self.setWindowTitle( self.appName )
		else:
			mod_str = ""
			ro_str = ""
			
			if self.dirtyFlag:
				mod_str = " [modified]"
			
			if not self.comic_archive.isWritable():
				ro_str = " [read only]"
				
			self.setWindowTitle( self.appName + " - " + self.comic_archive.path + mod_str + ro_str)

	def configMenus( self):
		
		# File Menu
		self.actionExit.setShortcut( 'Ctrl+Q' )
		self.actionExit.setStatusTip( 'Exit application' )
		self.actionExit.triggered.connect( self.close )

		self.actionLoad.setShortcut( 'Ctrl+O' )
		self.actionLoad.setStatusTip( 'Load comic archive' )
		self.actionLoad.triggered.connect( self.selectFile )

		self.actionLoadFolder.setShortcut( 'Ctrl+Shift+O' )
		self.actionLoadFolder.setStatusTip( 'Load folder with comic archives' )
		self.actionLoadFolder.triggered.connect( self.selectFolder )

		self.actionWrite_Tags.setShortcut( 'Ctrl+S' )
		self.actionWrite_Tags.setStatusTip( 'Save tags to comic archive' )
		self.actionWrite_Tags.triggered.connect( self.commitMetadata )

		self.actionAutoTag.setShortcut( 'Ctrl+T' )
		self.actionAutoTag.setStatusTip( 'Auto-tag multiple archives' )
		self.actionAutoTag.triggered.connect( self.autoTag )
				
		self.actionCopyTags.setShortcut( 'Ctrl+C' )
		self.actionCopyTags.setStatusTip( 'Copy one tag style to another' )
		self.actionCopyTags.triggered.connect( self.copyTags )

		self.actionRemoveAuto.setShortcut( 'Ctrl+D' )
		self.actionRemoveAuto.setStatusTip( 'Remove currently selected modify tag style from the archive' )
		self.actionRemoveAuto.triggered.connect( self.removeAuto )
		
		self.actionRemoveCBLTags.setStatusTip( 'Remove ComicBookLover tags from comic archive' )
		self.actionRemoveCBLTags.triggered.connect( self.removeCBLTags )

		self.actionRemoveCRTags.setStatusTip( 'Remove ComicRack tags from comic archive' )
		self.actionRemoveCRTags.triggered.connect( self.removeCRTags )
	
		self.actionViewRawCRTags.setStatusTip( 'View raw ComicRack tag block from file' )
		self.actionViewRawCRTags.triggered.connect( self.viewRawCRTags )

		self.actionViewRawCBLTags.setStatusTip( 'View raw ComicBookLover tag block from file' )
		self.actionViewRawCBLTags.triggered.connect( self.viewRawCBLTags )

		self.actionRepackage.setShortcut( 'Ctrl+E' )
		self.actionRepackage.setStatusTip( 'Re-create archive as CBZ' )
		self.actionRepackage.triggered.connect( self.repackageArchive )

		self.actionRename.setShortcut( 'Ctrl+N' )
		self.actionRename.setStatusTip( 'Rename archive based on tags' )
		self.actionRename.triggered.connect( self.renameArchive )
		
		self.actionSettings.setShortcut( 'Ctrl+Shift+S' )
		self.actionSettings.setStatusTip( 'Configure ComicTagger' )
		self.actionSettings.triggered.connect( self.showSettings )
		
		# Tag Menu
		self.actionParse_Filename.setShortcut( 'Ctrl+F' )
		self.actionParse_Filename.setStatusTip( 'Try to extract tags from filename' )
		self.actionParse_Filename.triggered.connect( self.useFilename )

		self.actionSearchOnline.setShortcut( 'Ctrl+W' )
		self.actionSearchOnline.setStatusTip( 'Search online for tags' )
		self.actionSearchOnline.triggered.connect( self.queryOnline )

		self.actionAutoIdentify.setShortcut( 'Ctrl+I' )
		self.actionAutoIdentify.triggered.connect( self.autoIdentifySearch )
		
		self.actionApplyCBLTransform.setShortcut( 'Ctrl+L' )
		self.actionApplyCBLTransform.setStatusTip( 'Modify tags specifically for CBL format' )
		self.actionApplyCBLTransform.triggered.connect( self.applyCBLTransform )		

		self.actionClearEntryForm.setShortcut( 'Ctrl+Shift+C' )
		self.actionClearEntryForm.setStatusTip( 'Clear all the data on the screen' )
		self.actionClearEntryForm.triggered.connect( self.clearForm )

		# Window Menu
		self.actionPageBrowser.setShortcut( 'Ctrl+P' )
		self.actionPageBrowser.setStatusTip( 'Show the page browser' )
		self.actionPageBrowser.triggered.connect( self.showPageBrowser )

		# Help Menu
		self.actionAbout.setStatusTip( 'Show the ' + self.appName + ' info' )
		self.actionAbout.triggered.connect( self.aboutApp )
		self.actionWiki.triggered.connect( self.showWiki )
		self.actionReportBug.triggered.connect( self.reportBug )
		self.actionComicTaggerForum.triggered.connect( self.showForum )
	
		# ToolBar

		self.actionLoad.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('open.png')))
		self.actionLoadFolder.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('longbox.png')))
		self.actionWrite_Tags.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('save.png')))
		self.actionParse_Filename.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('parse.png')))
		self.actionSearchOnline.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('search.png')))
		self.actionAutoIdentify.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('auto.png')))
		self.actionAutoTag.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('autotag.png')))
		self.actionClearEntryForm.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('clear.png')))
		self.actionPageBrowser.setIcon(QtGui.QIcon( ComicTaggerSettings.getGraphic('browse.png')))
		
		self.toolBar.addAction( self.actionLoad )
		self.toolBar.addAction( self.actionLoadFolder )
		self.toolBar.addAction( self.actionWrite_Tags )
		self.toolBar.addAction( self.actionSearchOnline )
		self.toolBar.addAction( self.actionAutoIdentify )
		self.toolBar.addAction( self.actionAutoTag )
		self.toolBar.addAction( self.actionClearEntryForm )
		self.toolBar.addAction( self.actionPageBrowser )

	def repackageArchive( self ):
		ca_list = self.fileSelectionList.getSelectedArchiveList()
		rar_count = 0
		for ca in ca_list:
			if ca.isRar( ):
				rar_count += 1
		
		if rar_count == 0:
			QtGui.QMessageBox.information(self, self.tr("Export as Zip Archive"), self.tr("No RAR archives selected!"))
			return

		if not self.dirtyFlagVerification( "Export as Zip Archive",
								"If you export archives as Zip now, unsaved data in the form may be lost.  Are you sure?"):			
			return

		if rar_count != 0:
			dlg = ExportWindow( self, self.settings,
						self.tr("You have selected {0} archive(s) to export  to Zip format.  New archives will be created in the same folder as the original.\n\nPlease choose options below, and select OK.\n".format(rar_count) ))
			dlg.adjustSize( )
			dlg.setModal( True )
			if not dlg.exec_():
				return
					
			progdialog = QtGui.QProgressDialog("", "Cancel", 0, rar_count, self)
			progdialog.setWindowTitle( "Exporting as ZIP" )
			progdialog.setWindowModality(QtCore.Qt.ApplicationModal)
			progdialog.show()
			prog_idx = 0
		
			new_archives_to_add = []
			archives_to_remove = []
			skipped_list = []
			failed_list = []
			success_count = 0
			
			for ca in ca_list:
				if ca.isRar():
					QtCore.QCoreApplication.processEvents()
					if progdialog.wasCanceled():
						break
					progdialog.setValue(prog_idx)
					prog_idx += 1
					progdialog.setLabelText( ca.path )
					utils.centerWindowOnParent( progdialog )
					QtCore.QCoreApplication.processEvents()

					original_path = os.path.abspath( ca.path )
					export_name = os.path.splitext(original_path)[0] + ".cbz"
					
					if os.path.lexists( export_name ):
						if dlg.fileConflictBehavior == ExportConflictOpts.dontCreate:
							export_name = None
							skipped_list.append( ca.path )
						elif dlg.fileConflictBehavior == ExportConflictOpts.createUnique:
							export_name = utils.unique_file( export_name )
								
					if export_name is not None:
						if ca.exportAsZip( export_name ):
							success_count += 1
							if dlg.addToList:
								new_archives_to_add.append( export_name )
							if dlg.deleteOriginal:
								archives_to_remove.append( ca )
								os.unlink( ca.path )
								
						else:
							# last export failed, so remove the zip, if it exists
							failed_list.append( ca.path )
							if os.path.lexists( export_name ):
								os.remove( export_name )
						
			progdialog.close()
			
			self.fileSelectionList.addPathList( new_archives_to_add )
			self.fileSelectionList.removeArchiveList( archives_to_remove )
			
			summary = u"Successfully created {0} Zip archive(s).".format( success_count )
			if len( skipped_list ) > 0:
				summary += u"\n\nThe following {0} RAR archive(s) were skipped due to file name conflicts:\n".format( len( skipped_list ) )
				for f in skipped_list:
					summary += u"\t{0}\n".format( f )
			if len( failed_list ) > 0:
				summary += u"\n\nThe following {0} RAR archive(s) failed to export due to read/write errors:\n".format( len( failed_list ) )
				for f in failed_list:
					summary += u"\t{0}\n".format( f )
				
			dlg = LogWindow( self )
			dlg.setText( summary )
			dlg.setWindowTitle( "Archive Export to Zip Summary" )
			dlg.exec_()
			

	def aboutApp( self ):
		
		website = "http://code.google.com/p/comictagger"
		email = "comictagger@gmail.com"
		license_link = "http://www.apache.org/licenses/LICENSE-2.0"
		license_name = "Apache License 2.0"
		
		msgBox = QtGui.QMessageBox()
		msgBox.setWindowTitle( self.tr("About " + self.appName ) )
		msgBox.setTextFormat( QtCore.Qt.RichText )
		msgBox.setIconPixmap( QtGui.QPixmap(ComicTaggerSettings.getGraphic('about.png')) )
		msgBox.setText( "<br><br><br>" 
		               + self.appName + " v" + self.version + "<br>" 
		               + "(c)2014 Anthony Beville<br><br>"
		               + "<a href='{0}'>{0}</a><br><br>".format(website)
		               + "<a href='mailto:{0}'>{0}</a><br><br>".format(email) 
		               + "License: <a href='{0}'>{1}</a>".format(license_link, license_name) )

		msgBox.setStandardButtons( QtGui.QMessageBox.Ok )
		msgBox.exec_()
		
	def dragEnterEvent(self, event):
		self.droppedFiles = None
		if event.mimeData().hasUrls():
					
			# walk through the URL list and build a file list
			for url in event.mimeData().urls():
				if url.isValid() and url.scheme() == "file":
					if self.droppedFiles is None:
						self.droppedFiles = []
					self.droppedFiles.append(url.toLocalFile())
					
			if self.droppedFiles is not None:	
				event.accept()
					
	def dropEvent(self, event):
		#if self.dirtyFlagVerification( "Open Archive",
		#							"If you open a new archive now, data in the form will be lost.  Are you sure?"):
		self.fileSelectionList.addPathList( self.droppedFiles )
		event.accept()

	def actualLoadCurrentArchive( self ):
		if self.metadata.isEmpty:
			self.metadata = self.comic_archive.metadataFromFilename( self.settings.parse_scan_info)
		if len(self.metadata.pages) == 0:
			self.metadata.setDefaultPageList( self.comic_archive.getNumberOfPages() )

		self.updateCoverImage()
		
		if self.page_browser is not None:
			self.page_browser.setComicArchive( self.comic_archive )
			self.page_browser.metadata = self.metadata

		self.metadataToForm()
		self.pageListEditor.setData( self.comic_archive, self.metadata.pages )
		self.clearDirtyFlag()  # also updates the app title
		self.updateInfoBox()
		self.updateMenus()
		self.updateAppTitle()

	def updateCoverImage( self ):
		cover_idx = self.metadata.getCoverPageIndexList()[0]
		self.archiveCoverWidget.setArchive( self.comic_archive, cover_idx)

	def updateMenus( self ):
		
		# First just disable all the questionable items
		self.actionAutoTag.setEnabled( False )
		self.actionCopyTags.setEnabled( False )		
		self.actionRemoveAuto.setEnabled( False )
		self.actionRemoveCRTags.setEnabled( False )
		self.actionRemoveCBLTags.setEnabled( False )
		self.actionWrite_Tags.setEnabled( False )
		self.actionRepackage.setEnabled(False)
		self.actionViewRawCBLTags.setEnabled( False )
		self.actionViewRawCRTags.setEnabled( False )
		self.actionParse_Filename.setEnabled( False )
		self.actionAutoIdentify.setEnabled( False )
		self.actionRename.setEnabled( False )
		self.actionApplyCBLTransform.setEnabled( False )
			
		# now, selectively re-enable
		if self.comic_archive is not None :
			has_cix = self.comic_archive.hasCIX()
			has_cbi = self.comic_archive.hasCBI()
			
			self.actionParse_Filename.setEnabled( True )
			self.actionAutoIdentify.setEnabled( True )
			self.actionAutoTag.setEnabled( True )
			self.actionRename.setEnabled( True )
			self.actionApplyCBLTransform.setEnabled( True )
			self.actionRepackage.setEnabled(True)
			self.actionRemoveAuto.setEnabled( True )
			self.actionRemoveCRTags.setEnabled( True )
			self.actionRemoveCBLTags.setEnabled( True )
			self.actionCopyTags.setEnabled( True )		
			
			if has_cix:
				self.actionViewRawCRTags.setEnabled( True )
			if has_cbi:
				self.actionViewRawCBLTags.setEnabled( True )
				
			if self.comic_archive.isWritable():
				self.actionWrite_Tags.setEnabled( True )


	def updateInfoBox( self ):
		
		ca = self.comic_archive
		
		if ca is None:
			self.lblFilename.setText( "" )
			self.lblArchiveType.setText( "" )
			self.lblTagList.setText( "" )
			self.lblPageCount.setText( "" )
			return
			
		filename = os.path.basename( ca.path )
		filename = os.path.splitext(filename)[0]
		filename = FileNameParser().fixSpaces(filename, False)

		self.lblFilename.setText( filename )

		if ca.isZip():
			self.lblArchiveType.setText( "ZIP archive" )
		elif ca.isRar():
			self.lblArchiveType.setText( "RAR archive" )
		elif ca.isFolder():
			self.lblArchiveType.setText( "Folder archive" )
		else:
			self.lblArchiveType.setText( "" )
			
		page_count = " ({0} pages)".format(ca.getNumberOfPages())
		self.lblPageCount.setText( page_count)
		
		tag_info = ""
		if ca.hasCIX():
			tag_info = u"• ComicRack tags"
		if ca.hasCBI():
			if tag_info != "":
				tag_info += "\n"
			tag_info += u"• ComicBookLover tags"

		self.lblTagList.setText( tag_info )
        
	def setDirtyFlag( self, param1=None, param2=None, param3=None  ):
		if not self.dirtyFlag:
			self.dirtyFlag = True
			self.fileSelectionList.setModifiedFlag( True )
			self.updateAppTitle()

	def clearDirtyFlag( self ):
		if self.dirtyFlag:
			self.dirtyFlag = False
			self.fileSelectionList.setModifiedFlag( False )
			self.updateAppTitle()
		
	def connectDirtyFlagSignals( self ):		
		# recursivly connect the tab form child slots
		self.connectChildDirtyFlagSignals( self.tabWidget )
		
	def connectChildDirtyFlagSignals (self, widget ):

		if ( isinstance(widget, QtGui.QLineEdit)):
			widget.textEdited.connect(self.setDirtyFlag)
		if ( isinstance(widget, QtGui.QTextEdit)):
			widget.textChanged.connect(self.setDirtyFlag)
		if ( isinstance(widget, QtGui.QComboBox) ):
			widget.currentIndexChanged.connect(self.setDirtyFlag)
		if ( isinstance(widget, QtGui.QCheckBox) ):
			widget.stateChanged.connect(self.setDirtyFlag)

		# recursive call on chillun
		for child in widget.children():
			if child != self.pageListEditor:
				self.connectChildDirtyFlagSignals( child )

	
	def clearForm( self ):		
	
		# get a minty fresh metadata object
		self.metadata = GenericMetadata()
		if self.comic_archive is not None:
			self.metadata.setDefaultPageList( self.comic_archive.getNumberOfPages() )
		
		# recursivly clear the tab form
		self.clearChildren( self.tabWidget )
		
		# clear the dirty flag, since there is nothing in there now to lose
		self.clearDirtyFlag()  

		self.pageListEditor.setData( self.comic_archive, self.metadata.pages )
		
	def clearChildren (self, widget ):

		if ( isinstance(widget, QtGui.QLineEdit) or   
				isinstance(widget, QtGui.QTextEdit)):
			widget.setText("")
		if ( isinstance(widget, QtGui.QComboBox) ):
			widget.setCurrentIndex( 0 )
		if ( isinstance(widget, QtGui.QCheckBox) ):
			widget.setChecked( False )
		if ( isinstance(widget, QtGui.QTableWidget) ):
			while widget.rowCount() > 0:
				widget.removeRow(0)

		# recursive call on chillun
		for child in widget.children():
			self.clearChildren( child )

		
	def metadataToForm( self ):
		# copy the the metadata object into to the form
		
		#helper func
		def assignText( field, value):
			if value is not None:
				field.setText( unicode(value) )
			
		md = self.metadata
		
		assignText( self.leSeries,       md.series )
		assignText( self.leIssueNum,     md.issue )
		assignText( self.leIssueCount,   md.issueCount )
		assignText( self.leVolumeNum,    md.volume )
		assignText( self.leVolumeCount,  md.volumeCount )
		assignText( self.leTitle,        md.title )
		assignText( self.lePublisher,    md.publisher )
		assignText( self.lePubMonth,     md.month )
		assignText( self.lePubYear,      md.year )
		assignText( self.leGenre,        md.genre )
		assignText( self.leImprint,      md.imprint )
		assignText( self.teComments,     md.comments )
		assignText( self.teNotes,        md.notes )
		assignText( self.leCriticalRating, md.criticalRating )
		assignText( self.leStoryArc,      md.storyArc )
		assignText( self.leScanInfo,      md.scanInfo )
		assignText( self.leSeriesGroup,   md.seriesGroup )
		assignText( self.leAltSeries,     md.alternateSeries )
		assignText( self.leAltIssueNum,   md.alternateNumber )
		assignText( self.leAltIssueCount, md.alternateCount )
		assignText( self.leWebLink,       md.webLink )
		assignText( self.teCharacters,    md.characters )
		assignText( self.teTeams,         md.teams )
		assignText( self.teLocations,     md.locations )
		
		if md.format is not None and md.format != "":
			i = self.cbFormat.findText( md.format )
			if i == -1:
				self.cbFormat.setEditText( md.format  )
			else:	
				self.cbFormat.setCurrentIndex( i )

		if md.maturityRating is not None and md.maturityRating != "":
			i = self.cbMaturityRating.findText( md.maturityRating )
			if i == -1:
				self.cbMaturityRating.setEditText( md.maturityRating  )
			else:	
				self.cbMaturityRating.setCurrentIndex( i )
			
		if md.language is not None:
			i = self.cbLanguage.findData( md.language )
			self.cbLanguage.setCurrentIndex( i )

		if md.country is not None:
			i = self.cbCountry.findText( md.country )
			self.cbCountry.setCurrentIndex( i )
		
		if md.manga is not None:
			i = self.cbManga.findData( md.manga )
			self.cbManga.setCurrentIndex( i )
		
		if md.blackAndWhite is not None and md.blackAndWhite:
			self.cbBW.setChecked( True )

		assignText( self.teTags, utils.listToString( md.tags ) )
			
		# !!! Should we clear the credits table or just avoid duplicates?
		while self.twCredits.rowCount() > 0:
			self.twCredits.removeRow(0)

		if md.credits is not None and len(md.credits) != 0:
		
			self.twCredits.setSortingEnabled( False )
	
			row = 0
			for credit in md.credits: 
				# if the role-person pair already exists, just skip adding it to the list
				if self.isDupeCredit( credit['role'].title(), credit['person']):
					continue
				
				self.addNewCreditEntry( row, credit['role'].title(), credit['person'], (credit['primary'] if credit.has_key('primary') else False ) )

				row += 1
				
		self.twCredits.setSortingEnabled( True )
		self.updateCreditColors()

	def addNewCreditEntry( self, row, role, name, primary_flag=False ):
		self.twCredits.insertRow(row)
		
		item_text = role
		item = QtGui.QTableWidgetItem(item_text)			
		item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
		item.setData( QtCore.Qt.ToolTipRole, item_text )
		self.twCredits.setItem(row, 1, item)

		
		item_text = name
		item = QtGui.QTableWidgetItem(item_text)			
		item.setData( QtCore.Qt.ToolTipRole, item_text )
		item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
		self.twCredits.setItem(row, 2, item)
		
		item = QtGui.QTableWidgetItem("")			
		item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
		self.twCredits.setItem(row, 0, item)
		self.updateCreditPrimaryFlag( row, primary_flag )
		
	def isDupeCredit( self, role, name ):
		r = 0
		while r < self.twCredits.rowCount():
			if ( self.twCredits.item(r, 1).text() == role and
					self.twCredits.item(r, 2).text() == name ):
				return True
			r = r + 1
			
		return False

	def formToMetadata( self ):
		
		#helper func
		def xlate( data, type_str):
			s = u"{0}".format(data).strip()
			if s == "":
				return None
			elif type_str == "str":
				return s
			else:
				return int(s)

		# copy the data from the form into the metadata
		md = self.metadata
		md.series =             xlate( self.leSeries.text(), "str" )
		md.issue =              xlate( self.leIssueNum.text(), "str" )
		md.issueCount =         xlate( self.leIssueCount.text(), "int" )
		md.volume =             xlate( self.leVolumeNum.text(), "int" )
		md.volumeCount =        xlate( self.leVolumeCount.text(), "int" )
		md.title =              xlate( self.leTitle.text(), "str" )
		md.publisher =          xlate( self.lePublisher.text(), "str" )
		md.month =              xlate( self.lePubMonth.text(), "int" )
		md.year =               xlate( self.lePubYear.text(), "int" )
		md.genre =              xlate( self.leGenre.text(), "str" )
		md.imprint =            xlate( self.leImprint.text(), "str" )
		md.comments =           xlate( self.teComments.toPlainText(), "str" )
		md.notes =              xlate( self.teNotes.toPlainText(), "str" )
		md.criticalRating =     xlate( self.leCriticalRating.text(), "int" )
		md.maturityRating =     xlate( self.cbMaturityRating.currentText(), "str" )

		md.storyArc =           xlate( self.leStoryArc.text(), "str" )
		md.scanInfo =           xlate( self.leScanInfo.text(), "str" )
		md.seriesGroup =        xlate( self.leSeriesGroup.text(), "str" )
		md.alternateSeries =    xlate( self.leAltSeries.text(), "str" )
		md.alternateNumber =    xlate( self.leAltIssueNum.text(), "int" )
		md.alternateCount =     xlate( self.leAltIssueCount.text(), "int" )
		md.webLink =            xlate( self.leWebLink.text(), "str" )
		md.characters =         xlate( self.teCharacters.toPlainText(), "str" )
		md.teams =              xlate( self.teTeams.toPlainText(), "str" )
		md.locations =          xlate( self.teLocations.toPlainText(), "str" )

		md.format =             xlate( self.cbFormat.currentText(), "str" )
		md.country =            xlate( self.cbCountry.currentText(), "str" )
		
		langiso = self.cbLanguage.itemData(self.cbLanguage.currentIndex()).toString()
		md.language =           xlate( langiso, "str" )

		manga_code = self.cbManga.itemData(self.cbManga.currentIndex()).toString()
		md.manga =           xlate( manga_code, "str" )
	
		# Make a list from the coma delimited tags string
		tmp = xlate( self.teTags.toPlainText(), "str" )
		if tmp != None:
			def striplist(l):
				return([x.strip() for x in l])

			md.tags = striplist(tmp.split( "," ))

		if ( self.cbBW.isChecked() ):
			md.blackAndWhite = True
		else:
			md.blackAndWhite = False

		# get the credits from the table
		md.credits = list()
		row = 0
		while row < self.twCredits.rowCount():
			role = u"{0}".format(self.twCredits.item(row, 1).text())
			name = u"{0}".format(self.twCredits.item(row, 2).text())
			primary_flag = self.twCredits.item( row, 0 ).text() != ""

			md.addCredit( name, role, bool(primary_flag) )
			row += 1

		md.pages = self.pageListEditor.getPageList()

	def useFilename( self ):
		if self.comic_archive is not None:
			#copy the form onto metadata object
			self.formToMetadata()
			new_metadata = self.comic_archive.metadataFromFilename(self.settings.parse_scan_info)
			if new_metadata is not None:
				self.metadata.overlay( new_metadata )				
				self.metadataToForm()

	def selectFolder( self ):
		self.selectFile( folder_mode=True )
		
	def selectFile( self , folder_mode = False):
		
		dialog = QtGui.QFileDialog(self)
		if folder_mode:
			dialog.setFileMode(QtGui.QFileDialog.Directory)
		else:
			dialog.setFileMode(QtGui.QFileDialog.ExistingFiles)
		
		if self.settings.last_opened_folder is not None:
			dialog.setDirectory( self.settings.last_opened_folder )
		#dialog.setFileMode(QtGui.QFileDialog.Directory )
		
		if not folder_mode:
			if platform.system() != "Windows" and utils.which("unrar") is None:
				archive_filter = "Comic archive files (*.cbz *.zip)"
			else:
				archive_filter = "Comic archive files (*.cbz *.zip *.cbr *.rar)"
			filters  = [ 
						 archive_filter,
						 "Any files (*)"
						 ]
			dialog.setNameFilters(filters)
		
		if (dialog.exec_()):
			fileList = dialog.selectedFiles()
			#if self.dirtyFlagVerification( "Open Archive",
			#							"If you open a new archive now, data in the form will be lost.  Are you sure?"):
			self.fileSelectionList.addPathList( fileList )
			
	def autoIdentifySearch(self):
		if self.comic_archive is None:
			QtGui.QMessageBox.warning(self, self.tr("Automatic Identify Search"), 
			       self.tr("You need to load a comic first!"))
			return
		
		self.queryOnline( autoselect=True )
		
	def queryOnline(self, autoselect=False):
		
		issue_number = unicode(self.leIssueNum.text()).strip()

		if autoselect and issue_number == "":
			QtGui.QMessageBox.information(self,"Automatic Identify Search", "Can't auto-identify without an issue number (yet!)")
			return
	
		if unicode(self.leSeries.text()).strip() != "":
			series_name = unicode(self.leSeries.text()).strip()
		else:
			QtGui.QMessageBox.information(self, self.tr("Online Search"), self.tr("Need to enter a series name to search."))
			return
		
		year = str(self.lePubYear.text()).strip()
		if year == "":
			year = None

		issue_count = str(self.leIssueCount.text()).strip()
		if issue_count == "":
			issue_count = None
			
		cover_index_list =  self.metadata.getCoverPageIndexList()
		selector = VolumeSelectionWindow( self, series_name, issue_number, year, issue_count, cover_index_list, self.comic_archive, self.settings, autoselect )

		title = "Search: '" + series_name + "' - "
		selector.setWindowTitle( title + "Select Series")

		selector.setModal(True)
		selector.exec_()
		
		if selector.result():
			#we should now have a volume ID
			QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

			#copy the form onto metadata object
			self.formToMetadata()
			
			try:
				comicVine = ComicVineTalker()
				new_metadata = comicVine.fetchIssueData( selector.volume_id, selector.issue_number, self.settings )
			except ComicVineTalkerException as e:
				QtGui.QApplication.restoreOverrideCursor()		
				if e.code == ComicVineTalkerException.RateLimit:
					QtGui.QMessageBox.critical(self, self.tr("Comic Vine Error"), ComicVineTalker.getRateLimitMessage())
				else:	
					QtGui.QMessageBox.critical(self, self.tr("Network Issue"), self.tr("Could not connect to ComicVine to get issue details.!"))
			else:
				QtGui.QApplication.restoreOverrideCursor()		
				if new_metadata is not None:
				
					if self.settings.apply_cbl_transform_on_cv_import:
						new_metadata = CBLTransformer( new_metadata, self.settings ).apply()

					if self.settings.clear_form_before_populating_from_cv:					
						self.clearForm()
						
					self.metadata.overlay( new_metadata )				
					# Now push the new combined data into the edit controls
					self.metadataToForm()
				else:
					QtGui.QMessageBox.critical(self, self.tr("Search"), self.tr("Could not find an issue {0} for that series".format(selector.issue_number)))


	def commitMetadata(self):

		if ( self.metadata is not None and self.comic_archive is not None):	
			reply = QtGui.QMessageBox.question(self, 
			     self.tr("Save Tags"), 
			     self.tr("Are you sure you wish to save " +  MetaDataStyle.name[self.save_data_style] + " tags to this archive?"),
			     QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )
			     
			if reply == QtGui.QMessageBox.Yes:		
				QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
				self.formToMetadata()
				
				success = self.comic_archive.writeMetadata( self.metadata, self.save_data_style )
				self.comic_archive.loadCache( [ MetaDataStyle.CBI, MetaDataStyle.CIX ] )
				QtGui.QApplication.restoreOverrideCursor()
				
				if not success:
					QtGui.QMessageBox.warning(self, self.tr("Save failed"), self.tr("The tag save operation seemed to fail!"))
				else:
					self.clearDirtyFlag()
					self.updateInfoBox()
					self.updateMenus()
					#QtGui.QMessageBox.information(self, self.tr("Yeah!"), self.tr("File written."))
				self.fileSelectionList.updateCurrentRow()

		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops!"), self.tr("No data to commit!"))


	def setLoadDataStyle(self, s):
		if self.dirtyFlagVerification( "Change Tag Read Style",
										"If you change read tag style now, data in the form will be lost.  Are you sure?"):
			self.load_data_style, b = self.cbLoadDataStyle.itemData(s).toInt()
			self.settings.last_selected_load_data_style = self.load_data_style
			self.updateMenus()
			if self.comic_archive is not None:
				self.loadArchive( self.comic_archive )
		else:
			self.cbLoadDataStyle.currentIndexChanged.disconnect(self.setLoadDataStyle)
			self.adjustLoadStyleCombo()
			self.cbLoadDataStyle.currentIndexChanged.connect(self.setLoadDataStyle)

	def setSaveDataStyle(self, s):
		self.save_data_style, b = self.cbSaveDataStyle.itemData(s).toInt()

		self.settings.last_selected_save_data_style = self.save_data_style
		self.updateStyleTweaks()
		self.updateMenus()
		
	def updateCreditColors( self ):
		inactive_color = QtGui.QColor(255, 170, 150)
		active_palette = self.leSeries.palette()
		active_color = active_palette.color( QtGui.QPalette.Base )

		cix_credits = ComicInfoXml().getParseableCredits()

		if self.save_data_style == MetaDataStyle.CIX:
			#loop over credit table, mark selected rows
			r = 0
			while r < self.twCredits.rowCount():
				if str(self.twCredits.item(r, 1).text()).lower() not in cix_credits:
					self.twCredits.item(r, 1).setBackgroundColor( inactive_color )
				else:
					self.twCredits.item(r, 1).setBackgroundColor( active_color )
				# turn off entire primary column
				self.twCredits.item(r, 0).setBackgroundColor( inactive_color )
				r = r + 1
		
		if self.save_data_style == MetaDataStyle.CBI:
			#loop over credit table, make all active color
			r = 0
			while r < self.twCredits.rowCount():
				self.twCredits.item(r, 0).setBackgroundColor( active_color )
				self.twCredits.item(r, 1).setBackgroundColor( active_color )
				r = r + 1
		

	def updateStyleTweaks( self ):

		# depending on the current data style, certain fields are disabled
		
		inactive_color = QtGui.QColor(255, 170, 150)
		active_palette = self.leSeries.palette()
		
		inactive_palette1 = self.leSeries.palette()
		inactive_palette1.setColor(QtGui.QPalette.Base, inactive_color)

		inactive_palette2 = self.leSeries.palette()

		inactive_palette3 = self.leSeries.palette()
		inactive_palette3.setColor(QtGui.QPalette.Base, inactive_color)
		
		inactive_palette3.setColor(QtGui.QPalette.Base, inactive_color)

		#helper func
		def enableWidget( item, enable ):
			inactive_palette3.setColor(item.backgroundRole(), inactive_color)
			inactive_palette2.setColor(item.backgroundRole(), inactive_color)
			inactive_palette3.setColor(item.foregroundRole(), inactive_color)

			if enable:
				item.setPalette(active_palette)
				item.setAutoFillBackground( False )
				if type(item) == QtGui.QCheckBox:
					item.setEnabled( True )
				elif type(item) == QtGui.QComboBox:
					item.setEnabled( True )
				else:
					item.setReadOnly( False )
			else:
				item.setAutoFillBackground( True )
				if type(item) == QtGui.QCheckBox:
					item.setPalette(inactive_palette2)
					item.setEnabled( False )
				elif type(item) == QtGui.QComboBox:
					item.setPalette(inactive_palette3)
					item.setEnabled( False )
				else:
					item.setReadOnly( True )
					item.setPalette(inactive_palette1)

		
		cbi_only = [ self.leVolumeCount, self.cbCountry, self.leCriticalRating, self.teTags ]
		cix_only = [ 
						self.leImprint, self.teNotes, self.cbBW, self.cbManga,
						self.leStoryArc, self.leScanInfo, self.leSeriesGroup, 
						self.leAltSeries, self.leAltIssueNum, self.leAltIssueCount,
						self.leWebLink, self.teCharacters, self.teTeams,
						self.teLocations, self.cbMaturityRating, self.cbFormat
					]
							
		if self.save_data_style == MetaDataStyle.CIX:
			for item in cix_only:
				enableWidget( item, True )
			for item in cbi_only:
				enableWidget(item, False )
		
		if self.save_data_style == MetaDataStyle.CBI:
			for item in cbi_only:
				enableWidget( item, True )
			for item in cix_only:
				enableWidget(item, False )
		
		self.updateCreditColors()
		self.pageListEditor.setMetadataStyle( self.save_data_style )
	
	def cellDoubleClicked( self, r, c ):
		self.editCredit()

	def addCredit( self ):
		self.modifyCredits( "add" )
		
	def editCredit( self ):
		if ( self.twCredits.currentRow() > -1 ):
			self.modifyCredits( "edit" )
	
	def updateCreditPrimaryFlag( self, row, primary ):
		
		# if we're clearing a flagm do it and quit
		if not primary:
			self.twCredits.item(row, 0).setText( "" )
			return
		
		# otherwise, we need to check for, and clear, other primaries with same role
		role = str(self.twCredits.item(row, 1).text())
		r = 0
		while r < self.twCredits.rowCount():
			if ( self.twCredits.item(r, 0).text() != "" and
					str(self.twCredits.item(r, 1).text()).lower() == role.lower() ):
				self.twCredits.item(r, 0).setText( "" )
			r = r + 1
		
		# Now set our new primary
		self.twCredits.item(row, 0).setText( "Yes" )

	def modifyCredits( self , action ):
		
		if action == "edit":
			row = self.twCredits.currentRow()
			role = self.twCredits.item( row, 1 ).text()
			name = self.twCredits.item( row, 2 ).text()
			primary = self.twCredits.item( row, 0 ).text() != ""
		else:
			role = ""
			name = ""
			primary = False
		
		editor = CreditEditorWindow( self, CreditEditorWindow.ModeEdit, role, name, primary )
		editor.setModal(True)
		editor.exec_()
		if editor.result():
			new_role, new_name, new_primary =  editor.getCredits()
			
			if new_name == name and new_role == role and new_primary == primary:
				#nothing has changed, just quit
				return
			
			# name and role is the same, but primary flag changed
			if new_name == name and new_role == role:
				self.updateCreditPrimaryFlag( row, new_primary )
				return
			
			# check for dupes
			ok_to_mod = True
			if self.isDupeCredit( new_role, new_name):
				# delete the dupe credit from list
				reply = QtGui.QMessageBox.question(self, 
								self.tr("Duplicate Credit!"), 
								self.tr("This will create a duplicate credit entry. Would you like to merge the entries, or create a duplicate?"),
								self.tr("Merge"), self.tr("Duplicate" ))

				if reply == 0: 
					# merge
					if action == "edit":
						# just remove the row that would be same
						self.twCredits.removeRow( row )
						# TODO -- need to find the row of the dupe, and possible change the primary flag
						
					ok_to_mod = False

		
			if ok_to_mod:
				#modify it
				if action == "edit":
					self.twCredits.item(row, 1).setText( new_role )
					self.twCredits.item(row, 2).setText( new_name )
					self.updateCreditPrimaryFlag( row, new_primary )
				else:
					# add new entry
					row = self.twCredits.rowCount()
					self.addNewCreditEntry( row, new_role, new_name, new_primary)

			self.updateCreditColors()	
			self.setDirtyFlag()

	def removeCredit( self ):
		row = self.twCredits.currentRow()
		if row != -1 :
			self.twCredits.removeRow( row )
		self.setDirtyFlag()

	def showSettings( self ):
		
		settingswin = SettingsWindow( self, self.settings )
		settingswin.setModal(True)
		settingswin.exec_()
		if settingswin.result():
			pass

	def setAppPosition( self ):
		if self.settings.last_main_window_width != 0:
			self.move( self.settings.last_main_window_x, self.settings.last_main_window_y )
			self.resize( self.settings.last_main_window_width, self.settings.last_main_window_height )
		else:
			screen = QtGui.QDesktopWidget().screenGeometry()
			size =  self.frameGeometry()
			self.move((screen.width()-size.width())/2, (screen.height()-size.height())/2)
		
		
	def adjustLoadStyleCombo( self ):
		# select the current style
		if ( self.load_data_style == MetaDataStyle.CBI ):
			self.cbLoadDataStyle.setCurrentIndex ( 0 )
		elif ( self.load_data_style == MetaDataStyle.CIX ):
			self.cbLoadDataStyle.setCurrentIndex ( 1 )

	def adjustSaveStyleCombo( self ):
		# select the current style
		if ( self.save_data_style == MetaDataStyle.CBI ):
			self.cbSaveDataStyle.setCurrentIndex ( 0 )
		elif ( self.save_data_style == MetaDataStyle.CIX ):
			self.cbSaveDataStyle.setCurrentIndex ( 1 )
		self.updateStyleTweaks()
		

	def populateComboBoxes( self ):
		    
		# Add the entries to the tag style combobox
		self.cbLoadDataStyle.addItem( "ComicBookLover", MetaDataStyle.CBI )
		self.cbLoadDataStyle.addItem( "ComicRack", MetaDataStyle.CIX )
		self.adjustLoadStyleCombo()

		self.cbSaveDataStyle.addItem( "ComicBookLover", MetaDataStyle.CBI )
		self.cbSaveDataStyle.addItem( "ComicRack", MetaDataStyle.CIX )
		self.adjustSaveStyleCombo()
			
		# Add the entries to the country combobox
		self.cbCountry.addItem( "", "" )
		for c in utils.countries:
			self.cbCountry.addItem( c[1], c[0] )
		
		# Add the entries to the language combobox
		self.cbLanguage.addItem( "", "" )
		lang_dict = utils.getLanguageDict()
		for key in sorted(lang_dict, cmp=locale.strcoll, key=lang_dict.get):
			self.cbLanguage.addItem(  lang_dict[key], key )
		
		# Add the entries to the manga combobox
		self.cbManga.addItem( "", "" )
		self.cbManga.addItem( "Yes", "Yes" )
		self.cbManga.addItem( "Yes (Right to Left)", "YesAndRightToLeft" )
		self.cbManga.addItem( "No", "No" )

		# Add the entries to the maturity combobox
		self.cbMaturityRating.addItem( "", "" )
		self.cbMaturityRating.addItem( "Everyone", "" )
		self.cbMaturityRating.addItem( "G", "" )
		self.cbMaturityRating.addItem( "Early Childhood", "" )
		self.cbMaturityRating.addItem( "Everyone 10+", "" )
		self.cbMaturityRating.addItem( "PG", "" )
		self.cbMaturityRating.addItem( "Kids to Adults", "" )
		self.cbMaturityRating.addItem( "Teen", "" )
		self.cbMaturityRating.addItem( "MA15+", "" )
		self.cbMaturityRating.addItem( "Mature 17+", "" )
		self.cbMaturityRating.addItem( "R18+", "" )
		self.cbMaturityRating.addItem( "X18+", "" )
		self.cbMaturityRating.addItem( "Adults Only 18+", "" )
		self.cbMaturityRating.addItem( "Rating Pending", "" )
		
		# Add entries to the format combobox
		self.cbFormat.addItem("")
		self.cbFormat.addItem(".1")
		self.cbFormat.addItem("-1")
		self.cbFormat.addItem("1 Shot")
		self.cbFormat.addItem("1/2")
		self.cbFormat.addItem("1-Shot")
		self.cbFormat.addItem("Annotation")
		self.cbFormat.addItem("Annotations")
		self.cbFormat.addItem("Annual")
		self.cbFormat.addItem("Anthology")
		self.cbFormat.addItem("B&W")
		self.cbFormat.addItem("B/W")
		self.cbFormat.addItem("B&&W")
		self.cbFormat.addItem("Black & White")
		self.cbFormat.addItem("Box Set")
		self.cbFormat.addItem("Box-Set")
		self.cbFormat.addItem("Crossover")
		self.cbFormat.addItem("Director's Cut")
		self.cbFormat.addItem("Epilogue")
		self.cbFormat.addItem("Event")
		self.cbFormat.addItem("FCBD")
		self.cbFormat.addItem("Flyer")
		self.cbFormat.addItem("Giant")
		self.cbFormat.addItem("Giant Size")
		self.cbFormat.addItem("Giant-Size")
		self.cbFormat.addItem("Graphic Novel")
		self.cbFormat.addItem("Hardcover")
		self.cbFormat.addItem("Hard-Cover")
		self.cbFormat.addItem("King")
		self.cbFormat.addItem("King Size")
		self.cbFormat.addItem("King-Size")
		self.cbFormat.addItem("Limited Series")
		self.cbFormat.addItem("Magazine")
		self.cbFormat.addItem("-1")
		self.cbFormat.addItem("NSFW")
		self.cbFormat.addItem("One Shot")
		self.cbFormat.addItem("One-Shot")
		self.cbFormat.addItem("Point 1")
		self.cbFormat.addItem("Preview")
		self.cbFormat.addItem("Prologue")
		self.cbFormat.addItem("Reference")
		self.cbFormat.addItem("Review")
		self.cbFormat.addItem("Reviewed")
		self.cbFormat.addItem("Scanlation")
		self.cbFormat.addItem("Script")
		self.cbFormat.addItem("Series")
		self.cbFormat.addItem("Sketch")
		self.cbFormat.addItem("Special")
		self.cbFormat.addItem("TPB")
		self.cbFormat.addItem("Trade Paper Back")
		self.cbFormat.addItem("WebComic")
		self.cbFormat.addItem("Web Comic")
		self.cbFormat.addItem("Year 1")
		self.cbFormat.addItem("Year One")
		
	def removeAuto( self ):
		self.removeTags( self.save_data_style )

	def removeCBLTags( self ):
		self.removeTags(  MetaDataStyle.CBI )
			
	def removeCRTags( self ):
		self.removeTags(  MetaDataStyle.CIX )
			
	def removeTags( self, style):
		# remove the indicated tags from the archive
		ca_list = self.fileSelectionList.getSelectedArchiveList()
		has_md_count = 0
		for ca in ca_list:
			if ca.hasMetadata( style ):
				has_md_count += 1

		if has_md_count == 0:
			QtGui.QMessageBox.information(self, self.tr("Remove Tags"),
						self.tr("No archives with {0} tags selected!".format(MetaDataStyle.name[style])))
			return
				
		if has_md_count != 0 and not self.dirtyFlagVerification( "Remove Tags",
						"If you remove tags now, unsaved data in the form will be lost.  Are you sure?"):			
			return
		
		if has_md_count != 0:
			reply = QtGui.QMessageBox.question(self, 
			     self.tr("Remove Tags"), 
			     self.tr("Are you sure you wish to remove the {0} tags from {1} archive(s)?".format(MetaDataStyle.name[style], has_md_count)),
			     QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )
			     
			if reply == QtGui.QMessageBox.Yes:
				progdialog = QtGui.QProgressDialog("", "Cancel", 0, has_md_count, self)
				progdialog.setWindowTitle( "Removing Tags" )
				progdialog.setWindowModality(QtCore.Qt.ApplicationModal)
				progdialog.show()				
				prog_idx = 0
				
				failed_list = []
				success_count = 0
				for ca in ca_list:
					if ca.hasMetadata( style ):
						QtCore.QCoreApplication.processEvents()
						if progdialog.wasCanceled():
							break
						progdialog.setValue(prog_idx)
						prog_idx += 1
						progdialog.setLabelText( ca.path )
						utils.centerWindowOnParent( progdialog )
						QtCore.QCoreApplication.processEvents()
					
					if ca.hasMetadata( style ) and ca.isWritable():
						if not ca.removeMetadata( style ):
							failed_list.append( ca.path )
						else:
							success_count += 1
						ca.loadCache( [ MetaDataStyle.CBI, MetaDataStyle.CIX ] )
	
				progdialog.close()		
				self.fileSelectionList.updateSelectedRows()
				self.updateInfoBox()
				self.updateMenus()

				summary = u"Successfully removed tags in {0} archive(s).".format( success_count )
				if len( failed_list ) > 0:
					summary += u"\n\nThe remove operation failed in the following {0} archive(s):\n".format( len( failed_list ) )
					for f in failed_list:
						summary += u"\t{0}\n".format( f )
					
				dlg = LogWindow( self )
				dlg.setText( summary )
				dlg.setWindowTitle( "Tag Remove Summary" )
				#dlg.adjustSize()
				dlg.exec_()			
				
	def copyTags( self ):
		# copy the indicated tags in the archive
		ca_list = self.fileSelectionList.getSelectedArchiveList()
		has_src_count = 0
		
		src_style = self.load_data_style
		dest_style = self.save_data_style
		
		if src_style == dest_style:
			QtGui.QMessageBox.information(self, self.tr("Copy Tags"), self.tr("Can't copy tag style onto itself." +
						"  Read style and modify style must be different."))
			return
		
		for ca in ca_list:
			if ca.hasMetadata( src_style ):
				has_src_count += 1
				
		if has_src_count == 0:
			QtGui.QMessageBox.information(self, self.tr("Copy Tags"), self.tr("No archives with {0} tags selected!".format(
					MetaDataStyle.name[src_style])))
			return
			
		if has_src_count != 0 and not self.dirtyFlagVerification( "Copy Tags",
						"If you copy tags now, unsaved data in the form may be lost.  Are you sure?"):			
			return
		
		if has_src_count != 0:
			reply = QtGui.QMessageBox.question(self, 
					self.tr("Copy Tags"), 
					self.tr("Are you sure you wish to copy the {0} tags to {1} tags in {2} archive(s)?".format(
					MetaDataStyle.name[src_style], MetaDataStyle.name[dest_style], has_src_count)),
					QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )

			if reply == QtGui.QMessageBox.Yes:
				progdialog = QtGui.QProgressDialog("", "Cancel", 0, has_src_count, self)
				progdialog.setWindowTitle( "Copying Tags" )
				progdialog.setWindowModality(QtCore.Qt.ApplicationModal)
				progdialog.show()
				prog_idx = 0
				
				failed_list = []
				success_count = 0
				for ca in ca_list:
					if ca.hasMetadata( src_style ):
						QtCore.QCoreApplication.processEvents()
						if progdialog.wasCanceled():
							break
						progdialog.setValue(prog_idx)
						prog_idx += 1
						progdialog.setLabelText( ca.path )
						utils.centerWindowOnParent( progdialog )
						QtCore.QCoreApplication.processEvents()
					
					if ca.hasMetadata( src_style ) and ca.isWritable():
						md = ca.readMetadata( src_style )

						if dest_style == MetaDataStyle.CBI and self.settings.apply_cbl_transform_on_bulk_operation:
							md = CBLTransformer( md, self.settings ).apply()
												
						if not ca.writeMetadata( md, dest_style ):
							failed_list.append( ca.path )
						else:
							success_count += 1

						ca.loadCache( [ MetaDataStyle.CBI, MetaDataStyle.CIX ] )

				progdialog.close()		
				self.fileSelectionList.updateSelectedRows()
				self.updateInfoBox()
				self.updateMenus()
				
				summary = u"Successfully copied tags in {0} archive(s).".format( success_count )
				if len( failed_list ) > 0:
					summary += u"\n\nThe copy operation failed in the following {0} archive(s):\n".format( len( failed_list ) )
					for f in failed_list:
						summary += u"\t{0}\n".format( f )
					
				dlg = LogWindow( self )
				dlg.setText( summary )
				dlg.setWindowTitle( "Tag Copy Summary" )
				dlg.exec_()				

	def actualIssueDataFetch( self, match ):
	
		# now get the particular issue data
		cv_md = None
		QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
		
		try:
			comicVine = ComicVineTalker( )
			comicVine.wait_for_rate_limit = self.settings.wait_and_retry_on_rate_limit
			cv_md = comicVine.fetchIssueData( match['volume_id'],  match['issue_number'], self.settings )
		except ComicVineTalkerException:
			print "Network error while getting issue details.  Save aborted"
		
		if cv_md is not None:
			if self.settings.apply_cbl_transform_on_cv_import:
				cv_md = CBLTransformer( cv_md, self.settings ).apply()

		QtGui.QApplication.restoreOverrideCursor()		
	
		return cv_md

	def autoTagLog( self, text ):
		IssueIdentifier.defaultWriteOutput( text )
		if self.atprogdialog is not None:
			self.atprogdialog.textEdit.insertPlainText(text)
			self.atprogdialog.textEdit.ensureCursorVisible()
			QtCore.QCoreApplication.processEvents()
			QtCore.QCoreApplication.processEvents()
			QtCore.QCoreApplication.processEvents()
		
	def identifyAndTagSingleArchive( self, ca, match_results, dlg):
		success = False
		ii = IssueIdentifier( ca, self.settings )

		# read in metadata, and parse file name if not there
		md = ca.readMetadata( self.save_data_style )
		if md.isEmpty:
			md = ca.metadataFromFilename(self.settings.parse_scan_info)
			if dlg.ignoreLeadingDigitsInFilename and md.series is not None:
				#remove all leading numbers
				md.series = re.sub( "([\d.]*)(.*)", "\\2", md.series)

		# use the dialog specified search string
		if dlg.searchString is not None:
			md.series = dlg.searchString
			
		if md is None or md.isEmpty:
			print "!!!!No metadata given to search online with!"
			return False, match_results
	
		if dlg.dontUseYear:
			md.year = None
		if dlg.assumeIssueOne and ( md.issue is None or md.issue == ""):
			md.issue = "1"
		ii.setAdditionalMetadata( md )
		ii.onlyUseAdditionalMetaData = True
		ii.waitAndRetryOnRateLimit = dlg.waitAndRetryOnRateLimit
		ii.setOutputFunction( self.autoTagLog )
		ii.cover_page_index = md.getCoverPageIndexList()[0]
		ii.setCoverURLCallback( self.atprogdialog.setTestImage )
		ii.setNameLengthDeltaThreshold( dlg.nameLengthMatchTolerance )

		matches = ii.search()
		
		result = ii.search_result
		
		found_match = False
		choices = False
		low_confidence = False
		no_match = False
		
		if result == ii.ResultNoMatches:
			pass
		elif result == ii.ResultFoundMatchButBadCoverScore:
			low_confidence = True
			found_match = True
		elif result == ii.ResultFoundMatchButNotFirstPage :
			found_match = True
		elif result == ii.ResultMultipleMatchesWithBadImageScores:
			low_confidence = True
			choices = True
		elif result == ii.ResultOneGoodMatch:
			found_match = True
		elif result == ii.ResultMultipleGoodMatches:
			choices = True
	
		if choices:
			if low_confidence:
				self.autoTagLog( "Online search: Multiple low-confidence matches.  Save aborted\n" )
				match_results.lowConfidenceMatches.append(MultipleMatch(ca,matches))
			else:
				self.autoTagLog( "Online search: Multiple matches.  Save aborted\n" ) 
				match_results.multipleMatches.append(MultipleMatch(ca,matches))
		elif low_confidence and not dlg.autoSaveOnLow:
			self.autoTagLog(  "Online search: Low confidence match.  Save aborted\n" )
			match_results.lowConfidenceMatches.append(MultipleMatch(ca,matches))
		elif not found_match:
			self.autoTagLog(  "Online search: No match found.  Save aborted\n" )
			match_results.noMatches.append(ca.path)
		else:
			#  a single match!
			if low_confidence:
				self.autoTagLog(  "Online search: Low confidence match, but saving anyways, as indicated...\n" )				
			
			# now get the particular issue data
			cv_md = self.actualIssueDataFetch( matches[0] )
			if cv_md is None:
				match_results.fetchDataFailures.append(ca.path)
				
			if cv_md is not None:				
				md.overlay( cv_md )
			
				if not ca.writeMetadata( md, self.save_data_style ):
						match_results.writeFailures.append(ca.path)
						self.autoTagLog(  "Save failed ;-(\n" )				
				else:
						match_results.goodMatches.append(ca.path)
						success = True
						self.autoTagLog(  "Save complete!\n" )
				ca.loadCache( [ MetaDataStyle.CBI, MetaDataStyle.CIX ] )

		return success, match_results
				
	def autoTag( self ):
		ca_list = self.fileSelectionList.getSelectedArchiveList()
		style = self.save_data_style

		if len(ca_list) == 0:
			QtGui.QMessageBox.information(self, self.tr("Auto-Tag"), self.tr("No archives selected!"))
			return
						
		if not self.dirtyFlagVerification( "Auto-Tag",
						"If you auto-tag now, unsaved data in the form will be lost.  Are you sure?"):			
			return

		atstartdlg = AutoTagStartWindow( self, self.settings,
					self.tr("You have selected {0} archive(s) to automatically identify and write {1} tags to.\n\n".format(len(ca_list), MetaDataStyle.name[style]) +
							"Please choose options below, and select OK to Auto-Tag.\n" ))

		atstartdlg.adjustSize( )
		atstartdlg.setModal( True )
		if not atstartdlg.exec_():
			return

		self.atprogdialog = AutoTagProgressWindow( self)
		self.atprogdialog.setModal(True)
		self.atprogdialog.show()
		self.atprogdialog.progressBar.setMaximum( len(ca_list) )
		self.atprogdialog.setWindowTitle( "Auto-Tagging" )

		self.autoTagLog( u"========================================================================\n" )			
		self.autoTagLog( u"Auto-Tagging Started for {0} items\n".format(len(ca_list)))

		prog_idx = 0
		
		match_results = OnlineMatchResults()
		archives_to_remove = []
		for ca in ca_list:
			self.autoTagLog( u"============================================================\n" )			
			self.autoTagLog( u"Auto-Tagging {0} of {1}\n".format(prog_idx+1, len(ca_list)))
			self.autoTagLog( u"{0}\n".format(ca.path) )
			cover_idx = ca.readMetadata(style).getCoverPageIndexList()[0]
			image_data = ca.getPage( cover_idx )	
			self.atprogdialog.setArchiveImage( image_data )				
			self.atprogdialog.setTestImage( None )				
			
			QtCore.QCoreApplication.processEvents()
			if self.atprogdialog.isdone:
				break
			self.atprogdialog.progressBar.setValue( prog_idx )
			prog_idx += 1
			self.atprogdialog.label.setText( ca.path )
			utils.centerWindowOnParent( self.atprogdialog )
			QtCore.QCoreApplication.processEvents()
			
			if ca.isWritable():
				success, match_results = self.identifyAndTagSingleArchive( ca, match_results, atstartdlg )

				if success and atstartdlg.removeAfterSuccess:
					archives_to_remove.append( ca )

		self.atprogdialog.close()
		
		if atstartdlg.removeAfterSuccess:
			self.fileSelectionList.removeArchiveList( archives_to_remove )
		self.fileSelectionList.updateSelectedRows()

		self.loadArchive( self.fileSelectionList.getCurrentArchive() )
		self.atprogdialog = None				
		
		summary = u""		
		summary += u"Successfully tagged archives: {0}\n".format( len(match_results.goodMatches))

		if len ( match_results.multipleMatches ) > 0:
			summary += u"Archives with multiple matches: {0}\n".format( len(match_results.multipleMatches))
		if len ( match_results.lowConfidenceMatches ) > 0:
			summary += u"Archives with one or more low-confidence matches: {0}\n".format( len(match_results.lowConfidenceMatches))
		if len ( match_results.noMatches ) > 0:
			summary += u"Archives with no matches: {0}\n".format( len(match_results.noMatches))
		if len ( match_results.fetchDataFailures ) > 0:
			summary += u"Archives that failed due to data fetch errors: {0}\n".format( len(match_results.fetchDataFailures))
		if len ( match_results.writeFailures ) > 0:
			summary += u"Archives that failed due to file writing errors: {0}\n".format( len(match_results.writeFailures))

		self.autoTagLog( summary )			
		
		sum_selectable = len ( match_results.multipleMatches ) + len(match_results.lowConfidenceMatches)
		if sum_selectable > 0:
			summary += u"\n\nDo you want to manually select the ones with multiple matches and/or low-confidence matches now?"
		
			reply = QtGui.QMessageBox.question(self, 
			     self.tr(u"Auto-Tag Summary"), 
			     self.tr(summary),
			     QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )
			
			match_results.multipleMatches.extend( match_results.lowConfidenceMatches )
			if reply == QtGui.QMessageBox.Yes:
				matchdlg = AutoTagMatchWindow( self, match_results.multipleMatches, style, self.actualIssueDataFetch)
				matchdlg.setModal( True )
				matchdlg.exec_()
				self.fileSelectionList.updateSelectedRows()
				self.loadArchive( self.fileSelectionList.getCurrentArchive() )

		else:
				QtGui.QMessageBox.information(self, self.tr("Auto-Tag Summary"), self.tr(summary))

		



	def dirtyFlagVerification( self, title, desc):
		if self.dirtyFlag:
			reply = QtGui.QMessageBox.question(self, 
			     self.tr(title), 
			     self.tr(desc),
			     QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )
			     
			if reply != QtGui.QMessageBox.Yes:
				return False
		return True
			
	def closeEvent(self, event):

		if self.dirtyFlagVerification( "Exit " + self.appName,
		                             "If you quit now, data in the form will be lost.  Are you sure?"):
			appsize = self.size()
			self.settings.last_main_window_width = appsize.width()
			self.settings.last_main_window_height = appsize.height()
			self.settings.last_main_window_x = self.x()
			self.settings.last_main_window_y = self.y()
			self.settings.last_form_side_width = self.splitter.sizes()[0]
			self.settings.last_list_side_width = self.splitter.sizes()[1]
			self.settings.last_filelist_sorted_column, self.settings.last_filelist_sorted_order = self.fileSelectionList.getSorting()
			self.settings.save()

			
			event.accept()
		else:
			event.ignore()

	def showPageBrowser( self ):
		if self.page_browser is None:
			self.page_browser = PageBrowserWindow( self, self.metadata )
			if self.comic_archive is not None:
				self.page_browser.setComicArchive( self.comic_archive )
			self.page_browser.finished.connect(self.pageBrowserClosed)
			
	def pageBrowserClosed( self ):
		self.page_browser = None
			
	def viewRawCRTags( self ):
		if self.comic_archive is not None and self.comic_archive.hasCIX():
			dlg = LogWindow( self )
			dlg.setText( self.comic_archive.readRawCIX() )
			dlg.setWindowTitle( "Raw ComicRack Tag View" )
			dlg.exec_()
		
	def viewRawCBLTags( self ):
		if self.comic_archive is not None and self.comic_archive.hasCBI():
			dlg = LogWindow( self )
			text = pprint.pformat( json.loads(self.comic_archive.readRawCBI()), indent=4  )
			dlg.setText(text )
			dlg.setWindowTitle( "Raw ComicBookLover Tag View" )
			dlg.exec_()

	def showWiki( self ):
		webbrowser.open("http://code.google.com/p/comictagger/wiki/Home?tm=6")
		
	def reportBug( self ):
		webbrowser.open("http://code.google.com/p/comictagger/issues/list")
		
	def showForum( self ):
		webbrowser.open("http://comictagger.forumotion.com/")

	def frontCoverChanged( self, int ):
		self.metadata.pages = self.pageListEditor.getPageList()
		self.updateCoverImage()
		
	def pageListOrderChanged( self ):
		self.metadata.pages = self.pageListEditor.getPageList()
	
	def applyCBLTransform(self):
		self.formToMetadata()
		self.metadata = CBLTransformer( self.metadata, self.settings ).apply()
		self.metadataToForm()
	
	def renameArchive(self):
		ca_list = self.fileSelectionList.getSelectedArchiveList()

		if len(ca_list) == 0:
			QtGui.QMessageBox.information(self, self.tr("Rename"), self.tr("No archives selected!"))	
			return
		
		if self.dirtyFlagVerification( "File Rename",
								"If you rename files now, unsaved data in the form will be lost.  Are you sure?"):			

			dlg = RenameWindow( self, ca_list, self.load_data_style, self.settings )
			dlg.setModal( True )
			if dlg.exec_():
				self.fileSelectionList.updateSelectedRows()
				self.loadArchive( self.comic_archive )


		
	def fileListSelectionChanged( self, qvarFI ):
		fi = qvarFI.toPyObject()
		self.loadArchive( fi.ca )
		
	def loadArchive( self, comic_archive ):
		self.comic_archive = None
		self.clearForm()

		self.settings.last_opened_folder = os.path.abspath(os.path.split(comic_archive.path)[0])
		self.comic_archive = comic_archive
		self.metadata = self.comic_archive.readMetadata(self.load_data_style)
		if self.metadata is None:
			self.metadata = GenericMetadata()
			
		self.actualLoadCurrentArchive()
	
	def fileListCleared( self ):
		self.resetApp()

	def splitterMovedEvent( self, w1, w2 ):
		scrollbar_w = 0
		if self.scrollArea.verticalScrollBar().isVisible():
			scrollbar_w = self.scrollArea.verticalScrollBar().width()
		
		new_w = self.scrollArea.width() - scrollbar_w - 5
		self.scrollAreaWidgetContents.resize( new_w, self.scrollAreaWidgetContents.height())

	def resizeEvent( self, ev ):
		self.splitterMovedEvent( 0, 0)

	def tabChanged( self, idx ):
		if idx == 0:
			self.splitterMovedEvent( 0, 0)
		
	def checkLatestVersionOnline( self ):
		self.versionChecker = VersionChecker()
		self.versionChecker.versionRequestComplete.connect( self.versionCheckComplete )
		self.versionChecker.asyncGetLatestVersion( self.settings.install_id, self.settings.send_usage_stats )
	
	def versionCheckComplete( self, new_version ):
		if (  new_version != self.version and
		      new_version != self.settings.dont_notify_about_this_version):
			website = "http://code.google.com/p/comictagger"
			checked = OptionalMessageDialog.msg(  self, "New version available!",
					"New version ({0}) available!<br>(You are currently running {1})<br><br>".format( new_version, self.version) +
					"Visit <a href='{0}'>{0}</a> for more info.<br><br>".format(website),
					QtCore.Qt.Unchecked,
					"Don't tell me about this version again")
			if checked:
				self.settings.dont_notify_about_this_version = new_version

	def onIncomingSocketConnection(self):
		# accept connection from other instance.
		# read in the file list if they're giving it,
		# and add to our own list
		localSocket = self.socketServer.nextPendingConnection()
		if localSocket.waitForReadyRead(3000):
			byteArray = localSocket.readAll()
			if len(byteArray) > 0:
				obj = pickle.loads(byteArray)
				localSocket.disconnectFromServer()
				if type(obj) is list:
					self.fileSelectionList.addPathList( obj )
		else:
			#print localSocket.errorString().toLatin1()
			pass

		self.bringToTop()

	def bringToTop(self):
		if platform.system() == "Windows":
			self.showNormal()
			self.raise_()
			self.activateWindow()
			try:
				import win32con
				import win32gui
				hwnd = self.effectiveWinId()
				rect = win32gui.GetWindowRect(hwnd)
				x = rect[0]
				y = rect[1]
				w = rect[2] - x
				h = rect[3] - y
				# mark it "always on top", just for a moment, to force it to the top
				win32gui.SetWindowPos(hwnd,win32con.HWND_TOPMOST,   x, y, w, h, 0)
				win32gui.SetWindowPos(hwnd,win32con.HWND_NOTOPMOST, x, y, w, h, 0)
			except Exception as e:
				print "Whoops", e
		elif platform.system() == "Darwin":
			self.raise_()
			self.showNormal()
			self.activateWindow()
		else:
			flags = self.windowFlags() 
			self.setWindowFlags( flags |  QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.X11BypassWindowManagerHint)
			QtCore.QCoreApplication.processEvents()
			#self.show()
			self.setWindowFlags( flags )
			self.show()
		