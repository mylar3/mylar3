#  This file is part of Headphones.
#
#  Headphones is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Headphones is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Headphones.  If not, see <http://www.gnu.org/licenses/>.

from mylar import db

def getCachedArt(albumid):
    
    from mylar import cache
    
    c = cache.Cache()
    
    artwork_path = c.get_artwork_from_cache(ComicID=comicid)
    
    if not artwork_path:
        return None
    
    if artwork_path.startswith('http://'):
        artwork = urllib.urlopen(artwork_path).read()
        return artwork
    else:
        artwork = open(artwork_path, "r").read()
        return artwork
