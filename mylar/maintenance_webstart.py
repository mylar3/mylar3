# -*- coding: utf-8 -*-

#  This file is part of Mylar.
#
#  Mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mylar is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

import cherrypy
import portend as portend

import mylar
from mylar import logger
from mylar.webserve import WebMaintenance
from mylar.helpers import create_https_certificates

def initialize(options):

    # HTTPS stuff stolen from sickbeard
    enable_https = options['enable_https']
    https_cert = options['https_cert']
    https_key = options['https_key']
    https_chain = options['https_chain']

    if enable_https:
        # If either the HTTPS certificate or key do not exist, try to make
        # self-signed ones.
        if not (https_cert and os.path.exists(https_cert)) or not (https_key and os.path.exists(https_key)):
            if not create_https_certificates(https_cert, https_key):
                logger.warn("Unable to create certificate and key. Disabling " \
                    "HTTPS")
                enable_https = False

        if not (os.path.exists(https_cert) and os.path.exists(https_key)):
            logger.warn("Disabled HTTPS because of missing certificate and " \
                "key.")
            enable_https = False

    options_dict = {
        'server.socket_port': options['http_port'],
        'server.socket_host': options['http_host'],
        'server.thread_pool': 10,
        'tools.encode.on': True,
        'tools.encode.encoding': 'utf-8',
        'tools.encode.text_only': False,
        'tools.decode.on': True,
        'log.screen': False,
        'engine.autoreload.on': False,
    }

    if enable_https:
        options_dict['server.ssl_certificate'] = https_cert
        options_dict['server.ssl_private_key'] = https_key
        if https_chain:
            options_dict['server.ssl_certificate_chain'] = https_chain
        protocol = "https"
    else:
        protocol = "http"

    logger.info("[MAINTENANCE-MODE] Starting Mylar in maintenance mode on %s://%s:%d%s" % (protocol,options['http_host'], options['http_port'], options['http_root']))
    cherrypy.config.update(options_dict)

    conf = {
        '/': {
            'tools.staticdir.root': os.path.join(mylar.PROG_DIR, 'data'),
            'tools.proxy.on': True  # pay attention to X-Forwarded-Proto header
        },
        '/interfaces': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "interfaces"
        },
        '/images': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "images"
        },
        '/css': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "css"
        },
        '/js': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "js"
        },
        '/favicon.ico': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': os.path.join(os.path.abspath(os.curdir), 'images' + os.sep + 'favicon.ico')
        },
        '/cache': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': mylar.CONFIG.CACHE_DIR
        }
    }

    if options['http_password'] is not None:
        #userpassdict = dict(zip((options['http_username'].encode('utf-8'),), (options['http_password'].encode('utf-8'),)))
        #get_ha1= cherrypy.lib.auth_digest.get_ha1_dict_plain(userpassdict)
        if options['authentication'] == 2:
            # Set up a sessions based login page instead of using basic auth,
            # using the credentials set for basic auth. Attempting to browse to
            # a restricted page without a session token will result in a
            # redirect to the login page. A sucessful login should then redirect
            # to the originally requested page.
            #
            # Login sessions timeout after 43800 minutes (1 month) unless
            # changed in the config.
            # Note - the following command doesn't actually work, see update statement 2 lines down
            # cherrypy.tools.sessions.timeout = options['login_timeout']
            conf['/'].update({
                'tools.sessions.on': True,
                'tools.auth.on': True,
                'tools.sessions.timeout': options['login_timeout'],
                'auth.forms_username': options['http_username'],
                'auth.forms_password': options['http_password'],
                # Set all pages to require authentication.
                # You can also set auth requirements on a per-method basis by
                # using the @require() decorator on the methods in webserve.py
                'auth.require': []
            })
            # exempt api, login page and static elements from authentication requirements
            for i in ('/api', '/auth/login', '/css', '/images', '/js', 'favicon.ico'):
                if i in conf:
                    conf[i].update({'tools.auth.on': False})
                else:
                    conf[i] = {'tools.auth.on': False}
        elif options['authentication'] == 1:
            conf['/'].update({
                        'tools.auth_basic.on': True,
                        'tools.auth_basic.realm': 'Mylar',
                        'tools.auth_basic.checkpassword':  cherrypy.lib.auth_basic.checkpassword_dict(
                                {options['http_username']: options['http_password']})
                    })

    cherrypy.tree.mount(WebMaintenance(), str(options['http_root']), config = conf)

    cherrypy.config.update({'error_page.default': os.path.join(mylar.PROG_DIR, 'data', 'interfaces', 'default', 'maintenance_mode.html')})

    try:
        portend.Checker().assert_free(options['http_host'], options['http_port'])
        cherrypy.server.start()
    except Exception as e:
        logger.error('[ERROR] %s' % e)
        print('Failed to start on port: %i. Is something else running?' % (options['http_port']))
        sys.exit(0)

    cherrypy.server.wait()

def shutdown():
    cherrypy.engine.exit()
    cherrypy.config.update({ 'server.shutdown_timeout': 1})
