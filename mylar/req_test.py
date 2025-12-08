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

import re
import os
import sys
import json
import subprocess
import codecs
import configparser
import platform
from packaging.version import parse as parse_version

import mylar
from mylar import logger

from lib.rarfile import rarfile

class Req(object):

    def __init__(self):
        self.req_file_present = True
        self.file = os.path.join(mylar.DATA_DIR, 'requirements.txt')
        if any([mylar.INSTALL_TYPE == 'docker', mylar.DATA_DIR != mylar.PROG_DIR]) and not os.path.isfile(self.file):
            self.file = os.path.join(mylar.PROG_DIR, 'requirements.txt')
        if not os.path.isfile(self.file):
            self.req_file_present = False

        self.req_list = []
        self.pip_list = []
        self.pip_error = None
        self.rls_messages = []
        self.operators = ['==', '>=', '<=']
        #logger.fdebug('requirements.txt location: %s' % (self.file,))

        # mylar.REQS = {'pip': {'pip_failure': true/false, 'pip_list': {pip_list_dictionary}},
        #               'rar': {'rar_failure': true/false, 'rar_exe_path': path to rar / rar message},
        #               'release_messages': release messages,
        #               'config': {'config_failure': true/false, 'config_list': {config_list dictionary}}}

    def loaders(self):
        self.check_the_pip()
        self.find_the_unrar()
        self.release_messages()

        #check_config should be run on each config page load/update
        #self.check_config_values()

    def check_the_pip(self):
        plist = []

        if not self.req_file_present:
            pip_failed = True
            plist.append({'module': '???',
                          'message': 'Unable to locate requirements.txt file',
                          'version_match': ''})
        else:
            with open(self.file, 'r')as f:
                for line in f:
                    if '#' not in line:
                        for opc in self.operators:
                            p_test = line.find(opc)
                            if p_test > 0:
                                p_arg = opc
                                p_mod = str(line[:p_test]).strip()
                                if p_mod == '':
                                    continue
                                p_version = str(line[p_test+2:]).strip()
                                if p_version == '':
                                    continue
                                if p_mod == 'requests[socks]':
                                    self.req_list.append({'module': 'requests', 'version': '2.22', 'arg': '>='})
                                    self.req_list.append({'module': 'PySocks', 'version': '1.5', 'arg': '>='})
                                else:
                                    self.req_list.append({'module': p_mod, 'version': p_version, 'arg': p_arg})
                                break

        self.pip_load()

        req_pip_list = []

        cest_boom = 'OK'

        if self.pip_error is not None:
            pip_failed = True
            plist.append({'module': '???',
                          'message': self.pip_error['message'],
                          'version_match': ''})
            if mylar.INSTALL_TYPE == 'docker':
                self.rls_messages.append("Hotio images cannot verify required modules.</br> Your python requirements might not be met")
        else:
            for rq in self.req_list:
                version_match = False
                for pl in self.pip_list:
                    if re.sub('[\-\_]', '', rq['module'].lower()).strip() == re.sub('[\-\_]', '', pl['module'].lower()).strip():
                        if parse_version(pl['version']) == parse_version(rq['version']):
                            version_match = 'OK'
                        elif parse_version(pl['version']) < parse_version(rq['version']):
                            if rq['arg'] == '<=':
                                version_match = 'OK'
                            else:
                                version_match = 'FAIL'
                                cest_boom = 'FAIL'
                        elif parse_version(pl['version']) > parse_version(rq['version']):
                            if rq['arg'] == '>=':
                                version_match = 'OK'
                            else:
                                version_match = 'FAIL'
                                cest_boom = 'FAIL'
                        logger.fdebug('[%s] REQUIRED: %s ---> INSTALLED: %s [%s]' % (rq['module'], rq['version'], pl['version'], version_match))
                        req_pip_list.append({'module': rq['module'],
                                             'req_version': rq['version'],
                                             'arg': rq['arg'],
                                             'pip_version': pl['version'],
                                             'version_match': version_match})
                        break

                if version_match is False:
                    version_match = 'FAIL'
                    cest_boom = 'FAIL'
                    logger.fdebug('[%s] REQUIRED: %s ---> INSTALLED: %s ' % (rq['module'], rq['version'], version_match))
                    req_pip_list.append({'module': rq['module'],
                                         'req_version': rq['version'],
                                         'arg': rq['arg'],
                                         'pip_version': 'Not Installed',
                                         'version_match': version_match})

            if len(req_pip_list) > 0:
                pip_failed = False

            for x in req_pip_list:
                if x['version_match'] == 'FAIL':
                    if x['pip_version'] != 'Not Installed':
                        if x['arg'] == '>=':
                            targ = '<'
                        elif x['arg'] == '<=':
                            targ = '>'
                        else:
                            targ = '='
                        pip_message = "%s installed %s %s required" % (x['pip_version'], targ, x['req_version'])
                    else:
                        pip_message = "%s %s" % (x['req_version'], x['pip_version'])
                    plist.append({"module": str(x['module']),
                                  "message": pip_message,
                                  "version_match": str(x['version_match'])})
                    pip_failed = True

        mylar.REQS['pip'] = {'pip_failure': pip_failed, 'pip_info': plist}

    def pip_load(self):
        try:
            pyloc = sys.executable
            pi = subprocess.run([pyloc, '-V'],
                capture_output=True,
                text=True)
            py_version = pi.stdout
            logger.fdebug('Python Version: %s' % (py_version.strip()))
            logger.fdebug('Python executable location: %s' % (pyloc.strip()))

            pf_out = subprocess.run([pyloc, '-m', 'pip', 'list'], capture_output=True, text=True)
            pf_err = pf_out.stderr
            pf_raw = pf_out.stdout
            if pf_err:
                if 'No module named pip' in pf_err:
                    self.pip_error = {'module': '???', 'message': 'unable to perform check'}
                    return

            for pf in pf_raw.splitlines():
                if any(['WARNING' in pf, 'You should' in pf, '----' in pf, 'Package' in pf]):
                    continue
                pipline = str(pf)
                p_mod = str(pipline[:pipline.find(' ')]).strip()
                p_version = str(pipline[pipline.find(' ')+1:]).strip()
                self.pip_list.append({'module': p_mod, 'version': p_version})
        except Exception as e:
            logger.fdebug('error: %s' % (e,))

    def find_the_unrar(self):

        cmds = []
        rar_failure = True

        # Prioritise checking the ini if specified
        if mylar.CONFIG.UNRAR_CMD:
            cmds.append(mylar.CONFIG.UNRAR_CMD)
            logger.fdebug('unrar_cmd location added to cmd checker: %s' % mylar.CONFIG.UNRAR_CMD)

        cmds.append('unrar')

        if platform.system() == 'Windows':
            cmds.append('RaR')
            if os.path.exists("C:\\Program Files\\WinRAR\\Rar.exe"):
                cmds.append("C:\\Program Files\\WinRAR\\Rar.exe")
            elif os.path.exists("C:\\Program Files (x86)\\WinRAR\\Rar.exe"):
                cmds.append("C:\\Program Files (x86)\\WinRAR\\Rar.exe")

        # check the ct_settingspath
        ctpath = os.path.join(mylar.CONFIG.CT_SETTINGSPATH, 'settings')
        config = configparser.ConfigParser()
        if os.path.isfile(ctpath):
            ct_config = config.read_file(codecs.open(ctpath, 'r', 'utf8'))
            ctrarpath = config.get('settings', 'rar_exe_path')
            if ctrarpath is not None:
                cmds.append(ctrarpath)
                logger.fdebug('comictagger .settings file path added to cmd checker: %s' % ctrarpath)

        itworked = False
        output = None        

        for cmd in cmds:
            try:
                logger.fdebug('Trying to execute: %s' % (cmd))
                output = subprocess.run(cmd, text=True, capture_output=True, shell=True)
                #logger.fdebug('rar_check output: %s' % output)
                itworked = True
            except Exception as e:
                logger.fdebug('Command %s didn\'t work [%s]' % (cmd, e))
                itworked = False
                continue
            else:
                if all([output.stderr is not None, output.stderr != '', output.returncode > 0]):
                    logger.fdebug('Encountered error: %s' % output.stderr)
                    itworked = False

            # Current windows execution has the error on stderr, but leaving stdout check for belt & braces
            if "not found" in output.stdout or "not recognized as an internal or external command" in output.stdout \
                    or "not recognized as an internal or external command" in output.stderr:
                logger.fdebug('[%s] Unable to find executable with command: %s' % (output.stdout, cmd))
                output = None
                itworked = False
            elif itworked:
                tmp_chk = output.stdout.split(r'\n')
                for tc in tmp_chk:
                    if 'unrar' or 'RAR' in tc:
                        tt = tc.lower().find('copyright')
                        if tt != -1:
                            output = tc[:tt]
                            rar_failure = False
                            break

            # If we have a working tool, override the rarfile library's choice of tool
            if rar_failure is False:
                rarfile.UNRAR_TOOL = cmd
                break

        if output is None:
            output = 'Unable to locate unrar'

        rar_exe_path = output

        rar_message = 'Unable to locate unrar'
        try:
            if rar_exe_path is not None:
                rar_message = rar_exe_path  # Set the message to be the version text from stdout
                rar_failure = rar_failure
        except Exception as e:
            pass

        mylar.REQS['rar'] = {'rar_failure': rar_failure, 'rar_message': rar_message}

    def release_messages(self):
        try:
            with open('.release_messages', 'r') as rmf:
                rls_messages = rmf.readlines()
        except Exception:
             rls_messages = None
        else:
            if len(rls_messages) == 0:
                rls_messages = None

        if self.rls_messages:
            if rls_messages is not None:
                rls_messages.append(self.rls_messages)
            else:
                rls_messages = self.rls_messages

        logger.info('release_messages: %s' % (rls_messages,))
        mylar.REQS['release_messages'] = rls_messages

    def check_config_values(self):
        mylar.REQS['config'] = []   # make sure to reset config dict here
        if any(
                [
                    mylar.CONFIG.DESTINATION_DIR is None,
                    mylar.CONFIG.DESTINATION_DIR == 'None',
                    mylar.CONFIG.DESTINATION_DIR == '',
                ]
        ):
            mylar.REQS['config'].append({'error_message': 'No Comic Location path specified'})

        if any(
                [
                    mylar.CONFIG.COMICVINE_API is None,
                    mylar.CONFIG.COMICVINE_API == 'None',
                    mylar.CONFIG.COMICVINE_API == '',
                ]
        ):
            mylar.REQS['config'].append({'error_message': 'No Comicvine API key specified'})
