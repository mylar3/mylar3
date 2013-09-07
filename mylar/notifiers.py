#  This file is part of mylar.
#
#  mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  mylar is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with mylar.  If not, see <http://www.gnu.org/licenses/>.

from mylar import logger
import base64
import cherrypy
import urllib
import urllib2
import mylar
from httplib import HTTPSConnection
from urllib import urlencode
import os.path
import subprocess
import time
import lib.simplejson as simplejson

# This was obviously all taken from headphones with great appreciation :)

class PROWL:

    keys = []
    priority = []

    def __init__(self):
        self.enabled = mylar.PROWL_ENABLED
        self.keys = mylar.PROWL_KEYS
        self.priority = mylar.PROWL_PRIORITY   
        pass

    def conf(self, options):
        return cherrypy.config['config'].get('Prowl', options)

    def notify(self, message, event):
        if not mylar.PROWL_ENABLED:
            return

        http_handler = HTTPSConnection("api.prowlapp.com")
                                                
        data = {'apikey': mylar.PROWL_KEYS,
                'application': 'Mylar',
                'event': event,
                'description': message.encode("utf-8"),
                'priority': mylar.PROWL_PRIORITY }

        http_handler.request("POST",
                                "/publicapi/add",
                                headers = {'Content-type': "application/x-www-form-urlencoded"},
                                body = urlencode(data))
        response = http_handler.getresponse()
        request_status = response.status

        if request_status == 200:
                logger.info(u"Prowl notifications sent.")
                return True
        elif request_status == 401: 
                logger.info(u"Prowl auth failed: %s" % response.reason)
                return False
        else:
                logger.info(u"Prowl notification failed.")
                return False

    def updateLibrary(self):
        #For uniformity reasons not removed
        return

    def test(self, keys, priority):

        self.enabled = True
        self.keys = keys
        self.priority = priority

        self.notify('ZOMG Lazors Pewpewpew!', 'Test Message')
        
class NMA:

    def __init__(self):
    
        self.apikey = mylar.NMA_APIKEY
        self.priority = mylar.NMA_PRIORITY
        
    def _send(self, data):
        
        url_data = urllib.urlencode(data)
        url = 'https://www.notifymyandroid.com/publicapi/notify'
        
        req = urllib2.Request(url, url_data)

        try:
            handle = urllib2.urlopen(req)
        except Exception, e:
            logger.warn('Error opening NotifyMyAndroid url: ' % e)
            return

        response = handle.read().decode(mylar.SYS_ENCODING)
        
        return response     
        
    def notify(self, ComicName=None, Year=None, Issue=None, snatched_nzb=None, sent_to=None):
    
        apikey = self.apikey
        priority = self.priority
        
        if snatched_nzb:
            event = snatched_nzb + " snatched!"
            description = "Mylar has snatched: " + snatched_nzb + " and has sent it to " + sent_to
        else:
            event = ComicName + ' (' + Year + ') - Issue #' + Issue + ' complete!'
            description = "Mylar has downloaded and postprocessed: " + ComicName + ' (' + Year + ') #' + Issue
    
        data = { 'apikey': apikey, 'application':'Mylar', 'event': event, 'description': description, 'priority': priority}

        logger.info('Sending notification request to NotifyMyAndroid')
        request = self._send(data)
        
        if not request:
            logger.warn('Error sending notification request to NotifyMyAndroid')        
        
# 2013-04-01 Added Pushover.net notifications, based on copy of Prowl class above.
# No extra care has been put into API friendliness at the moment (read: https://pushover.net/api#friendly)
class PUSHOVER:

    def __init__(self):
        self.enabled = mylar.PUSHOVER_ENABLED
        self.apikey = mylar.PUSHOVER_APIKEY
        self.userkey = mylar.PUSHOVER_USERKEY
        self.priority = mylar.PUSHOVER_PRIORITY
        # other API options:
        # self.device_id = mylar.PUSHOVER_DEVICE_ID
        # device - option for specifying which of your registered devices Mylar should send to. No option given, it sends to all devices on Pushover (default)
        # URL / URL_TITLE (both for use with the COPS/OPDS server I'm building maybe?)
        # Sound - name of soundfile to override default sound choice
    
    # not sure if this is needed for Pushover
    
    #def conf(self, options):
    # return cherrypy.config['config'].get('Pushover', options)

    def notify(self, message, event):
        if not mylar.PUSHOVER_ENABLED:
            return

        http_handler = HTTPSConnection("api.pushover.net:443")
                                                
        data = {'token': mylar.PUSHOVER_APIKEY,
                'user': mylar.PUSHOVER_USERKEY,
                'message': message.encode("utf-8"),
                'title': event,
                'priority': mylar.PUSHOVER_PRIORITY }

        http_handler.request("POST",
                                "/1/messages.json",
                                body = urlencode(data),
                                headers = {'Content-type': "application/x-www-form-urlencoded"}
                                )
        response = http_handler.getresponse()
        request_status = response.status

        if request_status == 200:
                logger.info(u"Pushover notifications sent.")
                return True
        elif request_status == 401:
                logger.info(u"Pushover auth failed: %s" % response.reason)
                return False
        else:
                logger.info(u"Pushover notification failed.")
                return False

    def test(self, apikey, userkey, priority):

        self.enabled = True
        self.apikey = apikey
        self.userkey = userkey
        self.priority = priority

        self.notify('ZOMG Lazors Pewpewpew!', 'Test Message')


API_URL = "https://boxcar.io/devices/providers/WqbewHpV8ZATnawpCsr4/notifications"

class BOXCAR:

    def test_notify(self, email, title="Test"):
        return self._sendBoxcar("This is a test notification from SickBeard", title, email)

    def _sendBoxcar(self, msg, title, email, subscribe=False):
        """
        Sends a boxcar notification to the address provided

        msg: The message to send (unicode)
        title: The title of the message
        email: The email address to send the message to (or to subscribe with)
        subscribe: If true then instead of sending a message this function will send a subscription notificat$

        returns: True if the message succeeded, False otherwise
        """

        # build up the URL and parameters
        msg = msg.strip()
        curUrl = API_URL

        # if this is a subscription notification then act accordingly
        if subscribe:
            data = urllib.urlencode({'email': email})
            curUrl = curUrl + "/subscribe"

        # for normal requests we need all these parameters
        else:
            data = urllib.urlencode({
                'email': email,
                'notification[from_screen_name]': title,
                'notification[message]': msg.encode('utf-8'),
                'notification[from_remote_service_id]': int(time.time())
                })


        # send the request to boxcar
        try:
            req = urllib2.Request(curUrl)
            handle = urllib2.urlopen(req, data)
            handle.close()

        except urllib2.URLError, e:
            # if we get an error back that doesn't have an error code then who knows what's really happening
            if not hasattr(e, 'code'):
                logger.error("Boxcar notification failed." + ex(e))
                return False
            else:
                logger.error("Boxcar notification failed. Error code: " + str(e.code))

            # HTTP status 404 if the provided email address isn't a Boxcar user.
            if e.code == 404:
                logger.error("Username is wrong/not a boxcar email. Boxcar will send an email to it")
                return False

            # For HTTP status code 401's, it is because you are passing in either an invalid token, or the user has not added$
            elif e.code == 401:

                # If the user has already added your service, we'll return an HTTP status code of 401.
                if subscribe:
                    logger.error("Already subscribed to service")
                    # i dont know if this is true or false ... its neither but i also dont know how we got here in the first $
                    return False

                #HTTP status 401 if the user doesn't have the service added
                else:
                    subscribeNote = self._sendBoxcar(msg, title, email, True)
                    if subscribeNote:
                        logger.info("Subscription send")
                        return True
                    else:
                        logger.info("Subscription could not be send")
                        return False

            # If you receive an HTTP status code of 400, it is because you failed to send the proper parameters
            elif e.code == 400:
                logger.info("Wrong data sent to boxcar")
                logger.info('data:' + data)
                return False

        logger.fdebug("Boxcar notification successful.")
        return True

    def notify(self, ComicName=None, Year=None, Issue=None, sent_to=None, snatched_nzb=None, username=None, force=False):
        """
        Sends a boxcar notification based on the provided info or SB config

        title: The title of the notification to send
        message: The message string to send
        username: The username to send the notification to (optional, defaults to the username in the config)
        force: If True then the notification will be sent even if Boxcar is disabled in the config
        """

        if not mylar.BOXCAR_ENABLED and not force:
            logger.fdebug("Notification for Boxcar not enabled, skipping this notification")
            return False

        # if no username was given then use the one from the config
        if not username:
            username = mylar.BOXCAR_USERNAME


        if snatched_nzb:
            title = "Mylar. Sucessfully Snatched!"
            message = "Mylar has snatched: " + snatched_nzb + " and has sent it to " + sent_to
        else:
            title = "Mylar. Successfully Downloaded & Post-Processed!"
            message = "Mylar has downloaded and postprocessed: " + ComicName + ' (' + Year + ') #' + Issue


        logger.info("Sending notification to Boxcar")

        self._sendBoxcar(message, title, username)
        return True


