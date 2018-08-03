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
import simplejson
import json
import requests

# This was obviously all taken from headphones with great appreciation :)

class PROWL:

    keys = []
    priority = []

    def __init__(self):
        self.enabled = mylar.CONFIG.PROWL_ENABLED
        self.keys = mylar.CONFIG.PROWL_KEYS
        self.priority = mylar.CONFIG.PROWL_PRIORITY
        pass

    def conf(self, options):
        return cherrypy.config['config'].get('Prowl', options)

    def notify(self, message, event, module=None):
        if not mylar.CONFIG.PROWL_ENABLED:
            return

        if module is None:
            module = ''
        module += '[NOTIFIER]'

        http_handler = HTTPSConnection("api.prowlapp.com")

        data = {'apikey': mylar.CONFIG.PROWL_KEYS,
                'application': 'Mylar',
                'event': event,
                'description': message.encode("utf-8"),
                'priority': mylar.CONFIG.PROWL_PRIORITY}

        http_handler.request("POST",
                                "/publicapi/add",
                                headers = {'Content-type': "application/x-www-form-urlencoded"},
                                body = urlencode(data))
        response = http_handler.getresponse()
        request_status = response.status

        if request_status == 200:
                logger.info(module + ' Prowl notifications sent.')
                return True
        elif request_status == 401:
                logger.info(module + ' Prowl auth failed: %s' % response.reason)
                return False
        else:
                logger.info(module + ' Prowl notification failed.')
                return False

    def test_notify(self):
        self.notify('ZOMG Lazors Pewpewpew!', 'Test Message')

class NMA:

    def __init__(self, test_apikey=None):

        self.NMA_URL = "https://www.notifymyandroid.com/publicapi/notify"
        self.TEST_NMA_URL = "https://www.notifymyandroid.com/publicapi/verify"
        if test_apikey is None:
            self.apikey = mylar.CONFIG.NMA_APIKEY
            self.test = False
        else:
            self.apikey = test_apikey
            self.test = True
        self.priority = mylar.CONFIG.NMA_PRIORITY

        self._session = requests.Session()

    def _send(self, data, module):
        try:
            r = self._session.post(self.NMA_URL, data=data, verify=True)
        except requests.exceptions.RequestException as e:                
            logger.error(module + '[' + str(e) + '] Unable to send via NMA. Aborting notification for this item.')
            return {'status':  False,
                    'message': str(e)}

        logger.fdebug('[NMA] Status code returned: ' + str(r.status_code))
        if r.status_code == 200:
            from xml.dom.minidom import parseString
            dom = parseString(r.content)
            try:
                success_info = dom.getElementsByTagName('success')
                success_code = success_info[0].getAttribute('code')
            except:
                error_info = dom.getElementsByTagName('error')
                error_code = error_info[0].getAttribute('code')
                error_message = error_info[0].childNodes[0].nodeValue
                logger.info(module + '[' + str(error_code) + '] ' + error_message)
                return {'status':  False,
                        'message': '[' + str(error_code) + '] ' + error_message}

            else:
                if self.test is True:
                    logger.info(module + '[' + str(success_code) + '] NotifyMyAndroid apikey valid. Test notification sent successfully.')
                else:
                    logger.info(module + '[' + str(success_code) + '] NotifyMyAndroid notification sent successfully.')
                return {'status':  True,
                        'message': 'APIKEY verified OK / notification sent'}
        elif r.status_code >= 400 and r.status_code < 500:
            logger.error(module + ' NotifyMyAndroid request failed: %s' % r.content)
            return {'status':  False,
                    'message': 'APIKEY verified OK / failure to send notification'}
        else:
            logger.error(module + ' NotifyMyAndroid notification failed serverside.')
            return {'status':  False,
                    'message': 'APIKEY verified OK / failure to send notification'}

    def notify(self, snline=None, prline=None, prline2=None, snatched_nzb=None, sent_to=None, prov=None, module=None):

        if module is None:
            module = ''
        module += '[NOTIFIER]'

        apikey = self.apikey
        priority = self.priority

        if snatched_nzb:
            if snatched_nzb[-1] == '\.': snatched_nzb = snatched_nzb[:-1]
            event = snline
            description = "Mylar has snatched: " + snatched_nzb + " from " + prov + " and has sent it to " + sent_to
        else:
            event = prline
            description = prline2

        data = {'apikey': apikey, 'application': 'Mylar', 'event': event.encode('utf-8'), 'description': description.encode('utf-8'), 'priority': priority}

        logger.info(module + ' Sending notification request to NotifyMyAndroid')
        request = self._send(data, module)

        if not request:
            logger.warn(module + ' Error sending notification request to NotifyMyAndroid')

    def test_notify(self):
        module = '[TEST-NOTIFIER]'
        try:
            r = self._session.get(self.TEST_NMA_URL, params={'apikey': self.apikey}, verify=True)
        except requests.exceptions.RequestException as e:
            logger.error(module + '[' + str(e) + '] Unable to send via NMA. Aborting test notification - something is probably wrong...')
            return {'status':  False,
                    'message': str(e)}

        logger.fdebug('[NMA] Status code returned: ' + str(r.status_code))
        if r.status_code == 200:
            from xml.dom.minidom import parseString
            dom = parseString(r.content)
            try:
                success_info = dom.getElementsByTagName('success')
                success_code = success_info[0].getAttribute('code')
            except:
                error_info = dom.getElementsByTagName('error')
                error_code = error_info[0].getAttribute('code')
                error_message = error_info[0].childNodes[0].nodeValue
                logger.info(module + '[' + str(error_code) + '] ' + error_message)
                return {'status':  False,
                        'message': '[' + str(error_code) + '] ' + error_message}

            else:
                logger.info(module + '[' + str(success_code) + '] NotifyMyAndroid apikey valid. Testing notification service with it.')
        elif r.status_code >= 400 and r.status_code < 500:
            logger.error(module + ' NotifyMyAndroid request failed: %s' % r.content)
            return {'status':  False,
                    'message': 'Unable to send request to NMA - check your connection.'}
        else:
            logger.error(module + ' NotifyMyAndroid notification failed serverside.')
            return {'status':  False,
                    'message': 'Internal Server Error. Try again later.'}

        event = 'Test Message'
        description = 'ZOMG Lazors PewPewPew!'
        data = {'apikey': self.apikey, 'application': 'Mylar', 'event': event.encode('utf-8'), 'description': description.encode('utf-8'), 'priority': 2}

        return self._send(data,'[NOTIFIER]')

# 2013-04-01 Added Pushover.net notifications, based on copy of Prowl class above.
# No extra care has been put into API friendliness at the moment (read: https://pushover.net/api#friendly)
class PUSHOVER:

    def __init__(self, test_apikey=None, test_userkey=None, test_device=None):
        if all([test_apikey is None, test_userkey is None, test_device is None]):
            self.PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'
            self.test = False
        else:
            self.PUSHOVER_URL = 'https://api.pushover.net/1/users/validate.json'
            self.test = True
        self.enabled = mylar.CONFIG.PUSHOVER_ENABLED
        if test_apikey is None:
            if mylar.CONFIG.PUSHOVER_APIKEY is None or mylar.CONFIG.PUSHOVER_APIKEY == 'None':
                logger.warn('No Pushover Apikey is present. Fix it')
                return False
            else:
                self.apikey = mylar.CONFIG.PUSHOVER_APIKEY
        else:
            self.apikey = test_apikey

        if test_device is None:
            self.device = mylar.CONFIG.PUSHOVER_DEVICE
        else:
            self.device = test_device

        if test_userkey is None:
            self.userkey = mylar.CONFIG.PUSHOVER_USERKEY
        else:
            self.userkey = test_userkey

        self.priority = mylar.CONFIG.PUSHOVER_PRIORITY

        self._session = requests.Session()
        self._session.headers = {'Content-type': "application/x-www-form-urlencoded"}

    def notify(self, event, message=None, snatched_nzb=None, prov=None, sent_to=None, module=None):

        if module is None:
            module = ''
        module += '[NOTIFIER]'

        if snatched_nzb:
            if snatched_nzb[-1] == '\.': 
                snatched_nzb = snatched_nzb[:-1]
            message = "Mylar has snatched: " + snatched_nzb + " from " + prov + " and has sent it to " + sent_to

        data = {'token': mylar.CONFIG.PUSHOVER_APIKEY,
                'user': mylar.CONFIG.PUSHOVER_USERKEY,
                'message': message.encode("utf-8"),
                'title': event,
                'priority': mylar.CONFIG.PUSHOVER_PRIORITY}

        if all([self.device is not None, self.device != 'None']):
            data.update({'device': self.device})

        r = self._session.post(self.PUSHOVER_URL, data=data, verify=True)

        if r.status_code == 200:
            try:
                response = r.json()
                if 'devices' in response and self.test is True:
                    logger.fdebug('%s Available devices: %s' % (module, response))
                    if any([self.device is None, self.device == 'None']):
                        self.device = 'all available devices'

                    r = self._session.post('https://api.pushover.net/1/messages.json', data=data, verify=True)
                    if r.status_code == 200:
                        logger.info('%s PushOver notifications sent to %s.' % (module, self.device))
                    elif r.status_code >=400 and r.status_code < 500:
                        logger.error('%s PushOver request failed to %s: %s' % (module, self.device, r.content))
                        return False
                    else:
                        logger.error('%s PushOver notification failed serverside.' % module)
                        return False
                else:
                    logger.info('%s PushOver notifications sent.' % module)
            except Exception as e:
                logger.warn('%s[ERROR] - %s' % (module, e))
                return False
            else:
                return True
        elif r.status_code >= 400 and r.status_code < 500:
            logger.error('%s PushOver request failed: %s' % (module, r.content))
            return False
        else:
            logger.error('%s PushOver notification failed serverside.' % module)
            return False

    def test_notify(self):
        return self.notify(event='Test Message', message='Release the Ninjas!')

class BOXCAR:

    #new BoxCar2 API
    def __init__(self):

        self.url = 'https://new.boxcar.io/api/notifications'

    def _sendBoxcar(self, msg, title, module):

        """
        Sends a boxcar notification to the address provided

        msg: The message to send (unicode)
        title: The title of the message

        returns: True if the message succeeded, False otherwise
        """

        try:

            data = urllib.urlencode({
                'user_credentials': mylar.CONFIG.BOXCAR_TOKEN,
                'notification[title]': title.encode('utf-8').strip(),
                'notification[long_message]': msg.encode('utf-8'),
                'notification[sound]': "done"
                })

            req = urllib2.Request(self.url)
            handle = urllib2.urlopen(req, data)
            handle.close()
            return True

        except urllib2.URLError, e:
            # if we get an error back that doesn't have an error code then who knows what's really happening
            if not hasattr(e, 'code'):
                logger.error(module + 'Boxcar2 notification failed. %s' % e)
            # If you receive an HTTP status code of 400, it is because you failed to send the proper parameters
            elif e.code == 400:
                logger.info(module + ' Wrong data sent to boxcar')
                logger.info(module + ' data:' + data)
            else:
                logger.error(module + ' Boxcar2 notification failed. Error code: ' + str(e.code))
            return False

        logger.fdebug(module + ' Boxcar2 notification successful.')
        return True

    def notify(self, prline=None, prline2=None, sent_to=None, snatched_nzb=None, force=False, module=None, snline=None):
        """
        Sends a boxcar notification based on the provided info or SB config

        title: The title of the notification to send
        message: The message string to send
        force: If True then the notification will be sent even if Boxcar is disabled in the config
        """
        if module is None:
            module = ''
        module += '[NOTIFIER]'

        if not mylar.CONFIG.BOXCAR_ENABLED and not force:
            logger.fdebug(module + ' Notification for Boxcar not enabled, skipping this notification.')
            return False

        # if no username was given then use the one from the config
        if snatched_nzb:
            title = snline
            message = "Mylar has snatched: " + snatched_nzb + " and has sent it to " + sent_to
        else:
            title = prline
            message = prline2

        logger.info(module + ' Sending notification to Boxcar2')

        self._sendBoxcar(message, title, module)
        return True

    def test_notify(self):
        self.notify(prline='Test Message',prline2='ZOMG Lazors Pewpewpew!')

class PUSHBULLET:

    def __init__(self, test_apikey=None):
        self.PUSH_URL = "https://api.pushbullet.com/v2/pushes"
        if test_apikey is None:
            self.apikey = mylar.CONFIG.PUSHBULLET_APIKEY
        else:
            self.apikey = test_apikey
        self.deviceid = mylar.CONFIG.PUSHBULLET_DEVICEID
        self.channel_tag = mylar.CONFIG.PUSHBULLET_CHANNEL_TAG
        self._json_header = {'Content-Type': 'application/json',
                             'Authorization': 'Basic %s' % base64.b64encode(self.apikey + ":")}
        self._session = requests.Session()
        self._session.headers.update(self._json_header)

    def get_devices(self, api):
        return self.notify(method="GET")

    def notify(self, snline=None, prline=None, prline2=None, snatched=None, sent_to=None, prov=None, module=None, method=None):
        if module is None:
            module = ''
        module += '[NOTIFIER]'
        
#        http_handler = HTTPSConnection("api.pushbullet.com")

#        if method == 'GET':
#            uri = '/v2/devices'
#        else:
#            method = 'POST'
#            uri = '/v2/pushes'

#        authString = base64.b64encode(self.apikey + ":")

        if method == 'GET':
            pass
#           http_handler.request(method, uri, None, headers={'Authorization': 'Basic %s:' % authString})
        else:
            if snatched:
                if snatched[-1] == '.': snatched = snatched[:-1]
                event = snline
                message = "Mylar has snatched: " + snatched + " from " + prov + " and has sent it to " + sent_to
            else:
                event = prline + ' complete!'
                message = prline2

            data = {'type': "note", #'device_iden': self.deviceid,
                    'title': event.encode('utf-8'), #"mylar",
                    'body': message.encode('utf-8')}

            if self.channel_tag:
                data['channel_tag'] = self.channel_tag

        r = self._session.post(self.PUSH_URL, data=json.dumps(data))
        dt = r.json()
        if r.status_code == 200:
            if method == 'GET':
                return dt
            else:
                logger.info(module + ' PushBullet notifications sent.')
                return {'status':  True,
                        'message': 'APIKEY verified OK / notification sent'}
        elif r.status_code >= 400 and r.status_code < 500:
            logger.error(module + ' PushBullet request failed: %s' % r.content)
            return {'status':  False,
                    'message': '[' + str(r.status_code) + '] ' + dt['error']['message']}
        else:
            logger.error(module + ' PushBullet notification failed serverside: %s' % r.content)
            return {'status':  False,
                    'message': '[' + str(r.status_code) + '] ' + dt['error']['message']}

    def test_notify(self):
        return self.notify(prline='Test Message', prline2='Release the Ninjas!')

class TELEGRAM:
    def __init__(self, test_userid=None, test_token=None):
        self.TELEGRAM_API = "https://api.telegram.org/bot%s/%s"
        if test_userid is None:
            self.userid = mylar.CONFIG.TELEGRAM_USERID
        else:
            self.userid = test_userid
        if test_token is None:
            self.token = mylar.CONFIG.TELEGRAM_TOKEN
        else:
            self.token = test_token

    def notify(self, message):
        # Construct message
        payload = {'chat_id': self.userid, 'text': message}

        # Send message to user using Telegram's Bot API
        try:
            response = requests.post(self.TELEGRAM_API % (self.token, "sendMessage"), json=payload, verify=True)
        except Exception, e:
            logger.info(u'Telegram notify failed: ' + str(e))

        # Error logging
        sent_successfuly = True
        if not response.status_code == 200:
            logger.info(u'Could not send notification to TelegramBot (token=%s). Response: [%s]' % (self.token, response.text))
            sent_successfuly = False

        logger.info(u"Telegram notifications sent.")
        return sent_successfuly

    def test_notify(self):
        return self.notify('Test Message: Release the Ninjas!')

class SLACK:
    def __init__(self, test_webhook_url=None):
        self.webhook_url = mylar.CONFIG.SLACK_WEBHOOK_URL if test_webhook_url is None else test_webhook_url

    def notify(self, text, attachment_text, snatched_nzb=None, prov=None, sent_to=None, module=None):
        if module is None:
            module = ''
        module += '[NOTIFIER]'

        if all([sent_to is not None, prov is not None]):
            attachment_text += ' from %s and sent to %s' % (prov, sent_to)
        elif sent_to is None:
            attachment_text += ' from %s' % prov
        else:
            pass

        payload = {
#            "text": text,
#            "attachments": [
#                {
#                    "color": "#36a64f",
#                    "text": attachment_text
#                }
#            ]
# FIX: #1861 move notif from attachment to msg body - bbq
            "text": attachment_text
        }

        try:
            response = requests.post(self.webhook_url, json=payload, verify=True)
        except Exception, e:
            logger.info(module + u'Slack notify failed: ' + str(e))

        # Error logging
        sent_successfuly = True
        if not response.status_code == 200:
            logger.info(module + u'Could not send notification to Slack (webhook_url=%s). Response: [%s]' % (self.webhook_url, response.text))
            sent_successfuly = False

        logger.info(module + u"Slack notifications sent.")
        return sent_successfuly

    def test_notify(self):
        return self.notify('Test Message', 'Release the Ninjas!')
