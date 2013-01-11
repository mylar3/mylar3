import lib.simplejson as json
import mylar
from mylar import logger
import urllib2


def searchit(cm):
        entries = []
        mres = {}

        if mylar.NZBX:
            provider = "nzbx"
            #stringsearch = str(cm) + "%20" + str(issue) + "%20" + str(year)
            searchURL = 'https://nzbx.co/api/search?cat=7030&q=' + str(cm)
                
            logger.info(u'Parsing results from <a href="%s">nzbx.co</a>' % searchURL)
            
            try:
                data = urllib2.urlopen(searchURL, timeout=20).read()
            except urllib2.URLError, e:
                logger.warn('Error fetching data from nzbx.co: %s' % str(e))
                data = False
                
            if data:
                
                d = json.loads(data)
                
                if not len(d):
                    logger.info(u"No results found from nzbx.co.")
                    pass
                
                else:
                    for item in d:
                        try:
                            url = item['nzb']
                            title = item['name']
                            size = item['size']
                            
                            entries.append({
                                    'title':   str(title),
                                    'link':    str(url)
                                    })
                            #resultlist.append((title, size, url, provider))
                            logger.info('Found %s. Size: %s' % (title, helpers.bytes_to_mb(size)))
                            
                        except Exception, e:
                            logger.error(u"An unknown error occurred trying to parse the feed: %s" % e)

            if len(entries) >= 1:
                mres['entries'] = entries
        return mres

