"""
A pthyon class to manage creating image content hashes, and calculate hamming distances
"""

"""
Copyright 2013  Anthony Beville

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
import StringIO
import sys

try: 
	from PIL import Image
	from PIL import WebPImagePlugin		
	pil_available = True
except ImportError:
	pil_available = False



class ImageHasher(object):
	def __init__(self, path=None, data=None, width=8, height=8):
		#self.hash_size = size
		self.width = width
		self.height = height

		if path is None and data is None:
			raise IOError
		else:
			try:
				if path is not None:
					self.image = Image.open(path)
				else:
					self.image = Image.open(StringIO.StringIO(data))
			except:
				print "Image data seems corrupted!"
				# just generate a bogus image
				self.image = Image.new( "L", (1,1))

	def average_hash(self):
		try:
			image = self.image.resize((self.width, self.height), Image.ANTIALIAS).convert("L")
		except Exception as e:
			sys.exc_clear()
			print "average_hash error:", e
			return long(0)
		
		pixels = list(image.getdata())
		avg = sum(pixels) / len(pixels)
		
		def compare_value_to_avg(i):
			return ( 1 if i > avg else 0 )
				
		bitlist = map(compare_value_to_avg, pixels)
		
		# build up an int value from the bit list, one bit at a time
		def set_bit( x, (idx, val) ):
			return (x | (val << idx))
			
		result = reduce(set_bit, enumerate(bitlist), 0)
		
		#print "{0:016x}".format(result)
		return result

	def average_hash2( self ):
		pass
		"""
		# Got this one from somewhere on the net.  Not a clue how the 'convolve2d'
		# works! 

		from numpy import array 
		from scipy.signal import convolve2d
				
		im = self.image.resize((self.width, self.height), Image.ANTIALIAS).convert('L')

		in_data = array((im.getdata())).reshape(self.width, self.height)
		filt = array([[0,1,0],[1,-4,1],[0,1,0]])
		filt_data = convolve2d(in_data,filt,mode='same',boundary='symm').flatten()
		
		result = reduce(lambda x, (y, z): x | (z << y),
		                 enumerate(map(lambda i: 0 if i < 0 else 1, filt_data)),
		                 0)
		#print "{0:016x}".format(result)
		return result
		"""
		
	def dct_average_hash(self):
		pass
		"""
		# Algorithm source: http://syntaxcandy.blogspot.com/2012/08/perceptual-hash.html
		
		1. Reduce size. Like Average Hash, pHash starts with a small image. 
		However, the image is larger than 8x8; 32x32 is a 	good size. This 
		is really done to simplify the DCT computation and not because it 
		is needed to reduce the high frequencies.

		2. Reduce color. The image is reduced to a grayscale just to further 
		simplify the number of computations.
		
		3. Compute the DCT. The DCT separates the image into a collection of
		frequencies and scalars. While JPEG uses 	an 8x8 DCT, this algorithm 
		uses a 32x32 DCT.
		
		4. Reduce the DCT. This is the magic step. While the DCT is 32x32, 
		just keep the top-left 8x8. Those represent the lowest frequencies in 
		the picture.
		
		5. Compute the average value. Like the Average Hash, compute the mean DCT 
		value (using only the 8x8 DCT low-frequency values and excluding the first 
		term since the DC coefficient can be significantly different 	from the other 
		values and will throw off the average). Thanks to David Starkweather for the 
		added information about pHash. He wrote: "the dct hash is based on the low 2D
		DCT coefficients starting at the second from lowest, leaving out the first DC
		term. This excludes completely flat image information (i.e. solid colors) from
		being included in the hash description."
		
		6. Further reduce the DCT. This is the magic step. Set the 64 hash bits to 0 or
		1 depending on whether 	each of the 64 DCT values is above or below the average 
		value. The result doesn't tell us the actual low frequencies; it just tells us
		the very-rough relative scale of the frequencies to the mean. The result will not
		vary as long as the overall structure of the image remains the same; this can 
		survive gamma and color histogram adjustments without a problem.
		
		7. Construct the hash. Set the 64 bits into a 64-bit integer. The order does not 
		matter, just as long as you are consistent. 
		"""
		"""
		import numpy
		import scipy.fftpack
		numpy.set_printoptions(threshold=10000, linewidth=200, precision=2, suppress=True)

		# Step 1,2
		im = self.image.resize((32, 32), Image.ANTIALIAS).convert("L")
		in_data = numpy.asarray(im)
		
		# Step 3
		dct = scipy.fftpack.dct( in_data.astype(float) )
	
		# Step 4
		# Just skip the top and left rows when slicing, as suggested somewhere else...
		lofreq_dct = dct[1:9, 1:9].flatten()
		
		# Step 5
		avg = ( lofreq_dct.sum() ) / ( lofreq_dct.size  )
		median = numpy.median( lofreq_dct )

		thresh = avg

		# Step 6
		def compare_value_to_thresh(i):
			return ( 1 if i > thresh else 0 )
				
		bitlist = map(compare_value_to_thresh, lofreq_dct)
		
		#Step 7
		def set_bit( x, (idx, val) ):
			return (x | (val << idx))
			
		result = reduce(set_bit, enumerate(bitlist), long(0))


		#print "{0:016x}".format(result)
		return result
		"""

	#accepts 2 hashes (longs or hex strings) and returns the hamming distance
	
	@staticmethod
	def hamming_distance(h1, h2):
		if type(h1) == long or type(h1) == int:
			n1 = h1
			n2 = h2
		else:
			# convert hex strings to ints
			n1 = long( h1, 16)
			n2 = long( h2, 16)
			
		# xor the two numbers
		n = n1 ^ n2

		#count up the 1's in the binary string 
		return sum( b == '1' for b in bin(n)[2:] )






