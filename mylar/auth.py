#!/usr/bin/env python
# -*- encoding: UTF-8 -*-
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
#
######
# Form based authentication for CherryPy. Requires the
# Session tool to be loaded.
###### from cherrypy/tools on github

import cherrypy
from cherrypy.lib.static import serve_file
from cgi import escape
#from datetime import datetime, timedelta
import urllib
import re
import mylar
from mylar import logger, encrypted

SESSION_KEY = '_cp_username'

def check_credentials(username, password):
    """Verifies credentials for username and password.
    Returns None on success or a string describing the error on failure"""
    # Adapt to your needs
    forms_user = cherrypy.request.config['auth.forms_username']
    forms_pass = cherrypy.request.config['auth.forms_password']
    edc = encrypted.Encryptor(forms_pass)
    ed_chk = edc.decrypt_it()
    if mylar.CONFIG.ENCRYPT_PASSWORDS is True:
        if username == forms_user and all([ed_chk['status'] is True, ed_chk['password'] == password]):
            return None
        else:
            return u"Incorrect username or password."
    else:
        if username == forms_user and password == forms_pass:
            return None
        else:
            return u"Incorrect username or password."

def check_auth(*args, **kwargs):
    """A tool that looks in config for 'auth.require'. If found and it
    is not None, a login is required and the entry is evaluated as a list of
    conditions that the user must fulfill"""
    conditions = cherrypy.request.config.get('auth.require', None)
    get_params = urllib.quote(cherrypy.request.request_line.split()[1])
    if conditions is not None:
        username = cherrypy.session.get(SESSION_KEY)
        if username:
            cherrypy.request.login = username
            for condition in conditions:
                # A condition is just a callable that returns true or false
                if not condition():
                    raise cherrypy.HTTPRedirect(mylar.CONFIG.HTTP_ROOT + "auth/login?from_page=%s" % get_params)
        else:
            raise cherrypy.HTTPRedirect(mylar.CONFIG.HTTP_ROOT + "auth/login?from_page=%s" % get_params)

cherrypy.tools.auth = cherrypy.Tool('before_handler', check_auth)

def require(*conditions):
    """A decorator that appends conditions to the auth.require config
    variable."""
    def decorate(f):
        if not hasattr(f, '_cp_config'):
            f._cp_config = dict()
        if 'auth.require' not in f._cp_config:
            f._cp_config['auth.require'] = []
        f._cp_config['auth.require'].extend(conditions)
        return f
    return decorate


# Conditions are callables that return True
# if the user fulfills the conditions they define, False otherwise
#
# They can access the current username as cherrypy.request.login
#
# Define those at will however suits the application.

def member_of(groupname):
    def check():
        # replace with actual check if <username> is in <groupname>
        return cherrypy.request.login == 'joe' and groupname == 'admin'
    return check

def name_is(reqd_username):
    return lambda: reqd_username == cherrypy.request.login

# These might be handy

def any_of(*conditions):
    """Returns True if any of the conditions match"""
    def check():
        for c in conditions:
            if c():
                return True
        return False
    return check

# By default all conditions are required, but this might still be
# needed if you want to use it inside of an any_of(...) condition
def all_of(*conditions):
    """Returns True if all of the conditions match"""
    def check():
        for c in conditions:
            if not c():
                return False
        return True
    return check

# Controller to provide login and logout actions

class AuthController(object):
    def on_login(self, username):
        """Called on successful login"""
        logger.info('%s successfully logged on.' % username)
        # not needed or used for Mylar currently

    def on_logout(self, username):
        """Called on logout"""
        # not needed or used for Mylar currently

    def get_loginform(self, username, msg="Enter login information", from_page="/"):
        from mylar.webserve import serve_template
        return serve_template(templatename="login.html", username=escape(username, True), title="Login", from_page=from_page)

    @cherrypy.expose
    def login(self, current_username=None, current_password=None, remember_me='0', from_page="/"):
        if current_username is None or current_password is None:
            return self.get_loginform("", from_page=from_page)

        error_msg = check_credentials(current_username, current_password)
        if error_msg:
            return self.get_loginform(current_username, error_msg, from_page)
        else:
            #if all([from_page != "/", from_page != "//"]):
            #    from_page = from_page
            #if mylar.OS_DETECT == 'Windows':
            #    if mylar.CONFIG.HTTP_ROOT != "//":
            #        from_page = re.sub(mylar.CONFIG.HTTP_ROOT, '', from_page,1).strip()
            #else:
            #    #if mylar.CONFIG.HTTP_ROOT != "/":
            #    from_page = re.sub(mylar.CONFIG.HTTP_ROOT, '', from_page,1).strip()
            cherrypy.session.regenerate()
            cherrypy.session[SESSION_KEY] = cherrypy.request.login = current_username
            #expiry = datetime.now() + (timedelta(days=30) if remember_me == '1' else timedelta(minutes=60))
            #cherrypy.session[SESSION_KEY] = {'user':    cherrypy.request.login,
            #                                 'expiry':  expiry}
            self.on_login(current_username)
            raise cherrypy.HTTPRedirect(from_page or mylar.CONFIG.HTTP_ROOT)

    @cherrypy.expose
    def logout(self, from_page="/"):
        sess = cherrypy.session
        username = sess.get(SESSION_KEY, None)
        sess[SESSION_KEY] = None
        return self.get_loginform("", from_page=from_page)
        if username:
            cherrypy.request.login = None
            self.on_logout(username)
            raise cherrypy.HTTPRedirect(from_page or mylar.CONFIG.HTTP_ROOT)

