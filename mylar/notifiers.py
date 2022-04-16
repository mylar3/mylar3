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
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import mylar
from http.client import HTTPSConnection
from urllib.parse import urlencode
import os.path
import subprocess
import time
import simplejson
import json
import requests
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

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
        #self._session.headers = doesn't need to be defined, requests figures it out based on parameters

    def notify(self, event, message=None, snatched_nzb=None, prov=None, sent_to=None, module=None, imageFile=None):
        if self.apikey is None:
            return False

        if module is None:
            module = ''
        module += '[NOTIFIER]'

        if snatched_nzb:
            if snatched_nzb[-1] == '\.': 
                snatched_nzb = snatched_nzb[:-1]
            message = "Mylar has snatched: " + snatched_nzb + " from " + prov + " and " + sent_to

        data = {'token': mylar.CONFIG.PUSHOVER_APIKEY,
                'user': mylar.CONFIG.PUSHOVER_USERKEY,
                'message': message.encode("utf-8"),
                'title': event,
                'priority': mylar.CONFIG.PUSHOVER_PRIORITY}

        files = None
        if imageFile:
            # Add image.
            files =  {'attachment': ('image.jpeg', base64.b64decode(imageFile), 'image/jpeg')}

        if all([self.device is not None, self.device != 'None']):
            data.update({'device': self.device})

        r = self._session.post(self.PUSHOVER_URL, data=data, files=files, verify=True)

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

            data = urllib.parse.urlencode({
                'user_credentials': mylar.CONFIG.BOXCAR_TOKEN,
                'notification[title]': title.encode('utf-8').strip(),
                'notification[long_message]': msg.encode('utf-8'),
                'notification[sound]': "done"
                })

            req = urllib.request.Request(self.url)
            handle = urllib.request.urlopen(req, data)
            handle.close()
            return True

        except urllib.error.URLError as e:
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
            message = "Mylar has snatched: " + snatched_nzb + " and " + sent_to
        else:
            title = prline
            message = prline2

        logger.info(module + ' Sending notification to Boxcar2')

        self._sendBoxcar(message, title, module)
        return True

    def test_notify(self):
        self.notify(prline='Test Message',prline2='ZOMG Lazors Pewpewpew!')

class PUSHBULLET:

    def __init__(self, test_apikey=None, channel=None):
        self.PUSH_URL = "https://api.pushbullet.com/v2/pushes"
        if test_apikey is None:
            self.apikey = mylar.CONFIG.PUSHBULLET_APIKEY
        else:
            self.apikey = test_apikey
        self.deviceid = mylar.CONFIG.PUSHBULLET_DEVICEID
        self.channel_tag = mylar.CONFIG.PUSHBULLET_CHANNEL_TAG
        self._json_header = {"Content-Type": "application/json",
                             "Accept": "application/json"}
        self._session = requests.Session()
        self._session.auth = (self.apikey, "")
        self._session.headers = self._json_header

    def get_devices(self):
        return self.notify(method="GET")

    def notify(self, snline=None, prline=None, prline2=None, snatched=None, sent_to=None, prov=None, module=None, method=None):
        if module is None:
            module = ''
        module += '[NOTIFIER]'

        if method == 'GET':
            data = None
            self.PUSH_URL = 'https://api.pushbullet.com/v2/devices'
        else:
            if snatched:
                if snatched[-1] == '.': snatched = snatched[:-1]
                event = snline
                message = "Mylar has snatched: " + snatched + " from " + prov + " and " + sent_to
            else:
                event = prline + ' complete!'
                message = prline2
            data = {'type': 'note',
                    'title': event,
                    'body': message}

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

    def notify(self, message, imageFile=None):
        payload = {'chat_id': self.userid, 'text': message}
        sendMethod = "sendMessage"
        files = None

        if imageFile:
            # Construct message
            try:
                files = {'photo': base64.b64decode(imageFile)}
                payload = {'chat_id': self.userid, 'caption': message}
                sendMethod = "sendPhoto"
            except Exception as e:
                logger.info('Telegram notify failed to decode image: ' + str(e))

        # Send message to user using Telegram's Bot API
        try:
            if files is None:
                response = requests.post(self.TELEGRAM_API % (self.token, sendMethod), json=payload, verify=True)
            else:
                response = requests.post(self.TELEGRAM_API % (self.token, sendMethod), payload, files=files, verify=True)
            sent_successfully = True
        except Exception as e:
            logger.info('Telegram notify failed: ' + str(e))
            sent_successfully = False

        # Error logging
        if sent_successfully:
            if not response.status_code == 200:
                logger.info(u'Could not send notification to TelegramBot (token=%s). Response: [%s]' % (self.token, response.text))
                sent_successfully = False

        if not sent_successfully and sendMethod != "sendMessage":
            return self.notify(message)

        if sent_successfully:
            logger.info(u"Telegram notifications sent.")
        return sent_successfully

    def test_notify(self):
        return self.notify('Test Message: Release the Ninjas!')

class EMAIL:
    def __init__(self, test_emailfrom=None, test_emailto=None, test_emailsvr=None, test_emailport=None, test_emailuser=None, test_emailpass=None, test_emailenc=None):
        self.emailfrom = mylar.CONFIG.EMAIL_FROM if test_emailfrom is None else test_emailfrom
        self.emailto = mylar.CONFIG.EMAIL_TO if test_emailto is None else test_emailto
        self.emailsvr = mylar.CONFIG.EMAIL_SERVER if test_emailsvr is None else test_emailsvr
        self.emailport = mylar.CONFIG.EMAIL_PORT if test_emailport is None else test_emailport
        self.emailuser = mylar.CONFIG.EMAIL_USER if test_emailuser is None else test_emailuser
        self.emailpass = mylar.CONFIG.EMAIL_PASSWORD if test_emailpass is None else test_emailpass
        self.emailenc = mylar.CONFIG.EMAIL_ENC if test_emailenc is None else int(test_emailenc)

    def notify(self, message, subject, module=None):
        if module is None:
            module = ''
        module += '[NOTIFIER]'
        sent_successfully = False

        try:
            logger.debug(module + ' Sending email notification. From: [%s] - To: [%s] - Server: [%s] - Port: [%s] - Username: [%s] - Password: [********] - Encryption: [%s] - Message: [%s]' % (self.emailfrom, self.emailto, self.emailsvr, self.emailport, self.emailuser, self.emailenc, message))
            msg = MIMEMultipart()
            msg['From'] = str(self.emailfrom)
            msg['To'] = str(self.emailto)
            msg['Subject'] = subject
            msg['Date'] = formatdate()
            msg['Message-ID'] = make_msgid('mylar')
            msg.attach(MIMEText(message, 'plain'))

            if self.emailenc == 1:
                sock = smtplib.SMTP_SSL(self.emailsvr, str(self.emailport))
            else:
                sock = smtplib.SMTP(self.emailsvr, str(self.emailport))

            if self.emailenc == 2:
                sock.starttls()

            if self.emailuser or self.emailpass:
                sock.login(str(self.emailuser), str(self.emailpass))

            sock.sendmail(str(self.emailfrom), str(self.emailto), msg.as_string())
            sock.quit()
            sent_successfully = True

        except Exception as e:
            logger.warn(module + ' Oh no!! Email notification failed: ' + str(e))

        return sent_successfully

    def test_notify(self):
        return self.notify('Test Message: With great power comes great responsibility.', 'Mylar notification - Test')

class SLACK:
    def __init__(self, test_webhook_url=None):
        self.webhook_url = mylar.CONFIG.SLACK_WEBHOOK_URL if test_webhook_url is None else test_webhook_url

    def notify(self, text, attachment_text, snatched_nzb=None, prov=None, sent_to=None, module=None):
        if module is None:
            module = ''
        module += '[NOTIFIER]'

        if 'snatched' in attachment_text.lower():
            snatched_text = '%s: %s' % (attachment_text, snatched_nzb)
            if all([sent_to is not None, prov is not None]):
                snatched_text += ' from %s and %s' % (prov, sent_to)
            elif sent_to is None:
                snatched_text += ' from %s' % prov
            attachment_text = snatched_text
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
        except Exception as e:
            logger.info(module + 'Slack notify failed: ' + str(e))

        # Error logging
        sent_successfuly = True
        if not response.status_code == 200:
            logger.info(module + 'Could not send notification to Slack (webhook_url=%s). Response: [%s]' % (self.webhook_url, response.text))
            sent_successfuly = False

        logger.info(module + "Slack notifications sent.")
        return sent_successfuly

    def test_notify(self):
        return self.notify('Test Message', 'Release the Ninjas!')
    
class MATTERMOST:
    def __init__(self, test_webhook_url=None):
        self.webhook_url = mylar.CONFIG.MATTERMOST_WEBHOOK_URL if test_webhook_url is None else test_webhook_url

    def notify(self, text, attachment_text, snatched_nzb=None, prov=None, sent_to=None, module=None):
        if module is None:
            module = ''
        module += '[NOTIFIER]'

        if 'snatched' in attachment_text.lower():
            snatched_text = '%s: %s' % (attachment_text, snatched_nzb)
            if all([sent_to is not None, prov is not None]):
                snatched_text += ' from %s and %s' % (prov, sent_to)
            elif sent_to is None:
                snatched_text += ' from %s' % prov
            attachment_text = snatched_text
        else:
            pass

        payload = {
            "text": attachment_text
        }

        try:
            response = requests.post(self.webhook_url, json=payload, verify=True)
        except Exception as e:
            logger.info(module + 'Mattermost notify failed: ' + str(e))

        # Error logging
        sent_successfuly = True
        if not response.status_code == 200:
            logger.info(module + 'Could not send notification to Mattermost (webhook_url=%s). Response: [%s]' % (self.webhook_url, response.text))
            sent_successfuly = False

        logger.info(module + "Mattermost notifications sent.")
        return sent_successfuly

    def test_notify(self):
        return self.notify('Test Message', 'Release the Ninjas!')

class DISCORD:
    def __init__(self, test_webhook_url=None):
        if test_webhook_url is None:
            self.webhook_url = mylar.CONFIG.DISCORD_WEBHOOK_URL
            self.test = False
        else:
            self.webhook_url = test_webhook_url
            self.test = True

    def notify(self, text, attachment_text, snatched_nzb=None, prov=None, sent_to=None, module=None, imageFile=None):
        if module is None:
            module = ''
        module += '[NOTIFIER]'

        # Setup discord variables
        payload = {}
        timestamp = str(datetime.utcnow())

        payload = {
               "username": "Mylar",
               "avatar_url": "https://github.com/mylar3/mylar3/raw/master/data/images/mylarlogo.png",
        }
        if self.test:
            payload["content"] = attachment_text
        else:
            if 'snatched' in attachment_text.lower():
                snatched_text = '%s: %s' % (attachment_text, snatched_nzb)
                if all([sent_to is not None, prov is not None]):
                    snatched_text += ' from %s and %s' % (prov, sent_to)
                    # If sent_to is not None, split it by whitespace into a list
                    sent_to_split = sent_to.split()
                    if 'DDL' in sent_to:
                        sent_to = 'DDL'
                    # If client is in this string, that's a torrent client. Get second to last word.
                    elif 'client' in sent_to:
                        # This should be the name of our torrent client
                        sent_to = sent_to_split[len(sent_to_split) - 2]
                    # If neither DDL nor client are in the string, it's an nzb. Get last word.
                    else:
                        sent_to = sent_to_split[len(sent_to_split) - 1]
                elif sent_to is None:
                    snatched_text += ' from %s' % prov
                # Separate series and issue numbers
                split_snatched_nzb = snatched_nzb.split()
                issue = split_snatched_nzb[len(split_snatched_nzb) - 1]
                split_snatched_nzb.pop()
                series = ' '.join(map(str, split_snatched_nzb))
                payload["content"] = snatched_text
                payload["embeds"] = [
                        {
                            "author": {
                               "name": "Grabbed by Mylar"
                            },
                            "description": attachment_text,
                            "color": 49151,
                            "fields": [
                                {
                                    "name": "Series",
                                    "value": series,
                                    "inline": "true"
                                },
                                {
                                    "name": "Issue",
                                    "value": issue,
                                    "inline": "true"
                                },
                                {
                                    "name": chr(173),
                                    "value": chr(173)
                                },
                                {
                                    "name": "Indexer",
                                    "value": prov,
                                    "inline": "true"
                                },
                                {
                                    "name": "Sent to",
                                    "value": sent_to,
                                    "inline": "true"
                                }
                            ],
                            "timestamp": timestamp
                        }
                    ]
            # If error is in the message
            elif 'error' in attachment_text.lower():
                payload["content"] = attachment_text
                payload["embeds"] = [
                        {
                            "author": {
                                "name": "Mylar Error"
                            },
                            "description": attachment_text,
                            "color": 16705372,
                            "fields": [
                                {
                                    "name": "File",
                                    "value": text
                                }
                            ],
                            "timestamp": timestamp
                        }
                    ]
            # If snatched or error is not in the message, it's a download and post-process
            else:
                logger.info('attachment_text:%s' % (attachment_text,))
                # extract series and issue number
                series_num = attachment_text[41:]
                series_num_split = series_num.split()
                issue = series_num_split[len(series_num_split) - 1]
                series_num_split.pop()
                series = ' '.join(map(str, series_num_split))

                # If there's an image file, put it in
                if imageFile is not None:
                    payload["content"] = attachment_text
                    payload["embeds"] = [
                            {
                                "author": {
                                    "name": "Downloaded by Mylar"
                                },
                                "description": "Issue downloaded!",
                                "color": 32768,
                                "fields": [
                                    {
                                        "name": "Series",
                                        "value": series,
                                        "inline": "true"
                                    },
                                    {
                                        "name": "Issue",
                                        "value": issue,
                                        "inline": "true"
                                    },
                                ],
                                "image": {
                                    "url": "attachment://image.jpg",
                                },
                                "timestamp": timestamp
                            }
                        ]
                else:
                    payload["content"] = attachment_text
                    payload["embeds"] = [
                            {
                                "author": {
                                    "name": "Downloaded by Mylar"
                                },
                                "description": "Issue downloaded!",
                                "color": 32768,
                                "fields": [
                                    {
                                        "name": "Series",
                                        "value": series,
                                        "inline": "true"
                                    },
                                    {
                                        "name": "Issue",
                                        "value": issue,
                                        "inline": "true"
                                    },
                                ],
                                "timestamp": timestamp
                            }
                        ]

        if imageFile is not None:
            files = {
                'payload_json': (None, json.dumps(payload)),
                'file1': ('image.jpg', base64.b64decode(imageFile))
            }
            try:
                response = requests.post(self.webhook_url, files=files, verify=True)
            except Exception as e:
                logger.info(module + 'Discord notify failed: ' + str(e))
        else:
            try:
                response = requests.post(self.webhook_url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, verify=True)
            except Exception as e:
                logger.info(module + 'Discord notify failed: ' + str(e))

        # Error logging
        sent_successfuly = True
        if not response.status_code == 204 or response.status_code == 200:
            logger.info(module + 'Could not send notification to Discord (webhook_url=%s). Response: [%s]' % (self.webhook_url, response.text))
            sent_successfuly = False

        logger.info(module + "Discord notifications sent.")
        return sent_successfuly

    def test_notify(self):
        return self.notify('Test Message', 'Release the Ninjas!')

class GOTIFY:
    def __init__(self, test_webhook_url=None):
        self.webhook_url = mylar.CONFIG.GOTIFY_SERVER_URL+"message?token="+mylar.CONFIG.GOTIFY_TOKEN if test_webhook_url is None else test_webhook_url

    def notify(self, text, attachment_text, snatched_nzb=None, prov=None, sent_to=None, module=None, imageFile=None):
        if module is None:
            module = ''
        module += '[NOTIFIER]'

        if 'snatched' in attachment_text.lower():
            snatched_text = '%s: %s' % (attachment_text, snatched_nzb)
            if all([sent_to is not None, prov is not None]):
                snatched_text += ' from %s and %s' % (prov, sent_to)
            elif sent_to is None:
                snatched_text += ' from %s' % prov
            attachment_text = snatched_text
        else:
            pass

        if imageFile is None:
            payload = {
                "title": text,
                "message": attachment_text
            }
        else:
            markdown = attachment_text+"\n\n"+f"![](data:image/jpeg;base64,{imageFile})"
            payload = {
                "title": text,
                "message": markdown,
                "extras": {
                    "client::display": {
                        "contentType": "text/markdown"
                    }
                }
            }
        
        try:
            response = requests.post(self.webhook_url, json=payload, verify=True)
        except Exception as e:
            logger.info(module + 'Gotify notify failed: ' + str(e))

        # Error logging
        sent_successfuly = True
        if not response.status_code == 200:
            logger.info(module + 'Could not send notification to Gotify (webhook_url=%s). Response: [%s]' % (self.webhook_url, response.text))
            sent_successfuly = False

        logger.info(module + "Gotify notifications sent.")
        return sent_successfuly

    def test_notify(self):
        return self.notify('Test Message', 'Release the Ninjas!')
