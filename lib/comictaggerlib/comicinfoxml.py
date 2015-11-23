"""
A python class to encapsulate ComicRack's ComicInfo.xml data 
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

from datetime import datetime
import zipfile
from pprint import pprint 
import xml.etree.ElementTree as ET
from genericmetadata import GenericMetadata
import utils

class ComicInfoXml:
	
	writer_synonyms = ['writer', 'plotter', 'scripter']
	penciller_synonyms = [ 'artist', 'penciller', 'penciler', 'breakdowns' ]
	inker_synonyms = [ 'inker', 'artist', 'finishes' ]
	colorist_synonyms = [ 'colorist', 'colourist', 'colorer', 'colourer' ]
	letterer_synonyms = [ 'letterer']
	cover_synonyms = [ 'cover', 'covers', 'coverartist', 'cover artist' ]
	editor_synonyms = [ 'editor']


	def getParseableCredits( self ):
		parsable_credits =  []
		parsable_credits.extend( self.writer_synonyms )
		parsable_credits.extend( self.penciller_synonyms )
		parsable_credits.extend( self.inker_synonyms )
		parsable_credits.extend( self.colorist_synonyms )
		parsable_credits.extend( self.letterer_synonyms )
		parsable_credits.extend( self.cover_synonyms )
		parsable_credits.extend( self.editor_synonyms )		
		return parsable_credits
		
	def metadataFromString( self, string ):

		tree = ET.ElementTree(ET.fromstring( string ))
		return self.convertXMLToMetadata( tree )

	def stringFromMetadata( self, metadata ):

		header = '<?xml version="1.0"?>\n'
		
		tree = self.convertMetadataToXML( self, metadata )
		return header + ET.tostring(tree.getroot())

	def indent( self, elem, level=0 ):
		# for making the XML output readable
		i = "\n" + level*"  "
		if len(elem):
			if not elem.text or not elem.text.strip():
				elem.text = i + "  "
			if not elem.tail or not elem.tail.strip():
				elem.tail = i
			for elem in elem:
				self.indent( elem, level+1 )
			if not elem.tail or not elem.tail.strip():
				elem.tail = i
		else:
			if level and (not elem.tail or not elem.tail.strip()):
				elem.tail = i
	
	def convertMetadataToXML( self, filename, metadata ):

		#shorthand for the metadata
		md = metadata

		# build a tree structure
		root = ET.Element("ComicInfo")
		root.attrib['xmlns:xsi']="http://www.w3.org/2001/XMLSchema-instance"
		root.attrib['xmlns:xsd']="http://www.w3.org/2001/XMLSchema"
		#helper func
		def assign( cix_entry, md_entry):
			if md_entry is not None:
				ET.SubElement(root, cix_entry).text = u"{0}".format(md_entry)

		assign( 'Title', md.title )
		assign( 'Series', md.series )
		assign( 'Number', md.issue )
		assign( 'Count', md.issueCount )
		assign( 'Volume', md.volume )
		assign( 'AlternateSeries', md.alternateSeries )
		assign( 'AlternateNumber', md.alternateNumber )
		assign( 'StoryArc', md.storyArc )
		assign( 'SeriesGroup', md.seriesGroup )
		assign( 'AlternateCount', md.alternateCount )
		assign( 'Summary', md.comments )
		assign( 'Notes', md.notes )
		assign( 'Year', md.year )
		assign( 'Month', md.month )
		assign( 'Day', md.day )

		# need to specially process the credits, since they are structured differently than CIX	
		credit_writer_list    = list()
		credit_penciller_list = list()
		credit_inker_list     = list()
		credit_colorist_list  = list()
		credit_letterer_list  = list()
		credit_cover_list     = list()
		credit_editor_list    = list()
		
		# first, loop thru credits, and build a list for each role that CIX supports
		for credit in metadata.credits:

			if credit['role'].lower() in set( self.writer_synonyms ):
				credit_writer_list.append(credit['person'].replace(",",""))

			if credit['role'].lower() in set( self.penciller_synonyms ):
				credit_penciller_list.append(credit['person'].replace(",",""))
				
			if credit['role'].lower() in set( self.inker_synonyms ):
				credit_inker_list.append(credit['person'].replace(",",""))
				
			if credit['role'].lower() in set( self.colorist_synonyms ):
				credit_colorist_list.append(credit['person'].replace(",",""))

			if credit['role'].lower() in set( self.letterer_synonyms ):
				credit_letterer_list.append(credit['person'].replace(",",""))

			if credit['role'].lower() in set( self.cover_synonyms ):
				credit_cover_list.append(credit['person'].replace(",",""))

			if credit['role'].lower() in set( self.editor_synonyms ):
				credit_editor_list.append(credit['person'].replace(",",""))
				
		# second, convert each list to string, and add to XML struct
		if len( credit_writer_list ) > 0:
			node = ET.SubElement(root, 'Writer')
			node.text = utils.listToString( credit_writer_list )

		if len( credit_penciller_list ) > 0:
			node = ET.SubElement(root, 'Penciller')
			node.text = utils.listToString( credit_penciller_list )

		if len( credit_inker_list ) > 0:
			node = ET.SubElement(root, 'Inker')
			node.text = utils.listToString( credit_inker_list )

		if len( credit_colorist_list ) > 0:
			node = ET.SubElement(root, 'Colorist')
			node.text = utils.listToString( credit_colorist_list )

		if len( credit_letterer_list ) > 0:
			node = ET.SubElement(root, 'Letterer')
			node.text = utils.listToString( credit_letterer_list )

		if len( credit_cover_list ) > 0:
			node = ET.SubElement(root, 'CoverArtist')
			node.text = utils.listToString( credit_cover_list )
		
		if len( credit_editor_list ) > 0:
			node = ET.SubElement(root, 'Editor')
			node.text = utils.listToString( credit_editor_list )

		assign( 'Publisher', md.publisher )
		assign( 'Imprint', md.imprint )
		assign( 'Genre', md.genre )
		assign( 'Web', md.webLink )
		assign( 'PageCount', md.pageCount )
		assign( 'LanguageISO', md.language )
		assign( 'Format', md.format )
		assign( 'AgeRating', md.maturityRating )
		if md.blackAndWhite is not None and md.blackAndWhite:
			ET.SubElement(root, 'BlackAndWhite').text = "Yes"
		assign( 'Manga', md.manga )
		assign( 'Characters', md.characters )
		assign( 'Teams', md.teams )
		assign( 'Locations', md.locations )
		assign( 'ScanInformation', md.scanInfo )

		#  loop and add the page entries under pages node
		if len( md.pages ) > 0:
			pages_node = ET.SubElement(root, 'Pages')
			for page_dict in md.pages:
				page_node = ET.SubElement(pages_node, 'Page')
				page_node.attrib = page_dict

		# self pretty-print
		self.indent(root)

		# wrap it in an ElementTree instance, and save as XML
		tree = ET.ElementTree(root)
		return tree
				 

	def convertXMLToMetadata( self, tree ):
			
		root = tree.getroot()

		if root.tag != 'ComicInfo':
			raise 1
			return None

		metadata = GenericMetadata()
		md = metadata
	
		
		# Helper function
		def xlate( tag ):
			node = root.find( tag )
			if node is not None:
				return node.text
			else:
				return None
				
		md.series =           xlate( 'Series' )
		md.title =            xlate( 'Title' )
		md.issue =            xlate( 'Number' )
		md.issueCount =       xlate( 'Count' )
		md.volume =           xlate( 'Volume' )
		md.alternateSeries =  xlate( 'AlternateSeries' )
		md.alternateNumber =  xlate( 'AlternateNumber' )
		md.alternateCount =   xlate( 'AlternateCount' )
		md.comments =         xlate( 'Summary' )
		md.notes =            xlate( 'Notes' )
		md.year =             xlate( 'Year' )
		md.month =            xlate( 'Month' )
		md.day =              xlate( 'Day' )
		md.publisher =        xlate( 'Publisher' )
		md.imprint =          xlate( 'Imprint' )
		md.genre =            xlate( 'Genre' )
		md.webLink =          xlate( 'Web' )
		md.language =         xlate( 'LanguageISO' )
		md.format =           xlate( 'Format' )
		md.manga =            xlate( 'Manga' )
		md.characters =       xlate( 'Characters' )
		md.teams =            xlate( 'Teams' )
		md.locations =        xlate( 'Locations' )
		md.pageCount =        xlate( 'PageCount' )
		md.scanInfo =         xlate( 'ScanInformation' )
		md.storyArc =         xlate( 'StoryArc' )
		md.seriesGroup =      xlate( 'SeriesGroup' )
		md.maturityRating =   xlate( 'AgeRating' )

		tmp = xlate( 'BlackAndWhite' )
		md.blackAndWhite = False
		if tmp is not None and tmp.lower() in [ "yes", "true", "1" ]:
			md.blackAndWhite = True
		# Now extract the credit info
		for n in root:
			if (  n.tag == 'Writer' or 
				n.tag == 'Penciller' or
				n.tag == 'Inker' or
				n.tag == 'Colorist' or
				n.tag == 'Letterer' or
				n.tag == 'Editor' 
			):
				if n.text is not None:
					for name in n.text.split(','):
						metadata.addCredit( name.strip(), n.tag )

			if n.tag == 'CoverArtist':
				if n.text is not None:
					for name in n.text.split(','):
						metadata.addCredit( name.strip(), "Cover" )

		# parse page data now	
		pages_node = root.find( "Pages" )
		if pages_node is not None:			
			for page in pages_node:
				metadata.pages.append( page.attrib )
				#print page.attrib

		metadata.isEmpty = False
		
		return metadata

	def writeToExternalFile( self, filename, metadata ):
		
		tree = self.convertMetadataToXML( self, metadata )
		#ET.dump(tree)		
		tree.write(filename, encoding='utf-8')
	
	def readFromExternalFile( self, filename ):

		tree = ET.parse( filename )
		return self.convertXMLToMetadata( tree )

