#!/usr/bin/env python
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

import random
import base64
import re
import sys
import os

import mylar
from mylar import logger

class Encryptor(object):
    def __init__(self, password, chk_password=None):
        self.password = password.encode('utf-8')

    def encrypt_it(self):
       try:
           salt = os.urandom(8)
           saltedhash = [salt[i] for i in range (0, len(salt))]
           salted_pass = base64.b64encode('%s%s' % (self.password,salt))
       except Exception as e:
           logger.warn('Error when encrypting: %s' % e)
           return {'status': False}
       else:
           return {'status': True, 'password': '^~$z$' + salted_pass}

    def decrypt_it(self):
       try:
           if not self.password.startswith('^~$z$'):
               logger.warn('Error not an encryption that I recognize.')
               return {'status': False}
           passd = base64.b64decode(self.password[5:]) #(base64.decodestring(self.password))
           saltedhash = [bytes(passd[-8:])]
       except Exception as e:
           logger.warn('Error when decrypting password: %s' % e)
           return {'status': False}
       else:
           return {'status': True, 'password': passd[:-8]}

