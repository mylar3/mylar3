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

import platform, subprocess, re, os, urllib.request, urllib.error, urllib.parse, tarfile

import mylar
from mylar import logger

import requests
import re

def runGit(args):

    git_locations = []
    if mylar.CONFIG.GIT_PATH is not None:
        git_locations.append(mylar.CONFIG.GIT_PATH)

    git_locations.append('git')

    if platform.system().lower() == 'darwin':
        git_locations.append('/usr/local/git/bin/git')


    output = err = None

    for cur_git in git_locations:

        cmd = '%s %s' % (cur_git, args)

        try:
            logger.debug('Trying to execute: %s with shell in %s' % (cmd, mylar.PROG_DIR))
            output = subprocess.run(cmd, text=True, capture_output=True, shell=True, cwd=mylar.PROG_DIR)
            logger.debug('Git output: %s' % output)
        except Exception as e:
            logger.error('Command %s didn\'t work [%s]' % (cmd, e))
            continue
        else:
            if all([output.stderr is not None, output.stderr != '']):
                logger.error('Encountered error: %s' % output.stderr)

        if "not found" in output.stdout or "not recognized as an internal or external command" in output.stdout:
            logger.error('[%s] Unable to find git with command: %s' % (output.stdout, cmd))
            output = None
        elif 'fatal:' in output.stdout or output.stderr:
            logger.error('Error: %s' % output.stderr)
            logger.error('Git returned bad info. Are you sure this is a git installation? [%s]' % output.stdout)
            output = None
        elif output:
            break

    return (output.stdout, output.stderr)

def getVersion():
    current_version_name = None

    if mylar.CONFIG.GIT_BRANCH is not None and mylar.CONFIG.GIT_BRANCH.startswith('win32build'):

        mylar.INSTALL_TYPE = 'win'

        # Don't have a way to update exe yet, but don't want to set VERSION to None
        return {'current_version': 'Windows Install', 'current_version_name': 'None', 'branch': 'None'}

    elif os.path.isdir(os.path.join(mylar.PROG_DIR, '.git')):

        mylar.INSTALL_TYPE = 'git'
        output, err = runGit('describe --exact-match --tags 2> %s && git rev-parse HEAD --abbrev-ref HEAD' % os.devnull)
        #output, err = runGit('rev-parse HEAD --abbrev-ref HEAD')

        if not output:
            output, err = runGit('describe --exact-match --tags 2> %s || git rev-parse HEAD --abbrev-ref HEAD' % os.devnull)
            if not output:
                logger.error('Couldn\'t find latest installed version.')
                cur_commit_hash = None

        #branch_history, err = runGit("log --oneline --pretty=format:'%h - %ar - %s' -n 5")
        #bh = []
        #print ("branch_history: " + branch_history)
        #bh.append(branch_history.split('\n'))
        #print ("bh1: " + bh[0])

        opp = output.find('\n')
        cur_commit_hash = output[:opp]
        cur_branch = output[opp:output.find('\n', opp+1)].strip()

        if cur_commit_hash.startswith('v'):
            url2 = 'https://api.github.com/repos/%s/mylar3/tags' % (mylar.CONFIG.GIT_USER)
            try:
                response = requests.get(url2, verify=True)
                git = response.json()
            except Exception as e:
                logger.warn('[ERROR] %s' % e)
                pass
            else:
                if git[0]['name'] is not None:
                    for x in git:
                        if x['name'] == output[:opp]:
                            current_version_name = x['name']
                            cur_commit_hash = x['commit']['sha']
                            break

        logger.info('cur_commit_hash: %s' % cur_commit_hash)
        logger.info('cur_branch: %s' % cur_branch)

        if not re.match('^[a-z0-9]+$', cur_commit_hash) and current_version_name is None:
            logger.error('Output does not look like a hash, not using it')
            cur_commit_hash = None

        if mylar.CONFIG.GIT_BRANCH == cur_branch:
            branch = mylar.CONFIG.GIT_BRANCH

        if cur_commit_hash is None:
            branch = None
        else:
            branch = None
            branch_name, err = runGit('branch --contains %s' % cur_commit_hash)
            if not branch_name:
                logger.warn('Could not retrieve branch name [%s] from git. Defaulting to Master.' % branch)
                branch = 'master'
            else:
                for line in branch_name.split('\n'):
                    if '*' in line:
                        branch = re.sub('[\*\n]','',line).strip()
                        break

        if not branch and mylar.CONFIG.GIT_BRANCH:
            logger.warn('Unable to retrieve branch name [%s] from git. Setting branch to configuration value of : %s' % (branch, mylar.CONFIG.GIT_BRANCH))
            branch = mylar.CONFIG.GIT_BRANCH
        if not branch:
            logger.warn('Could not retrieve branch name [%s] from git. Defaulting to Master.' % branch)
            branch = 'master'
        else:
            logger.info('Branch detected & set to : %s' % branch)

        return {'current_version': cur_commit_hash, 'current_version_name': current_version_name, 'branch': branch}

    else:

        mylar.INSTALL_TYPE = 'source'
        current_version = None
        branch = None

        url2 = 'https://api.github.com/repos/%s/mylar3/tags' % (mylar.CONFIG.GIT_USER)
        try:
            response = requests.get(url2, verify=True)
            git = response.json()
        except Exception as e:
            pass

        if current_version is None:
            try:
                version_file = os.path.join(mylar.PROG_DIR, '.LAST_RELEASE')

                if not os.path.isfile(version_file):
                    current_version = None
                else:
                    cnt = 0
                    with open('.LAST_RELEASE', 'r') as f:
                        for i in f.readlines():
                            tmp = i.split()
                            if cnt == 0:
                                if i.find('>') != -1:
                                    i_clean = tmp[len(tmp)-1]
                                    mrclean = re.sub('[\)\(\>]', '', i_clean).strip()
                                    branch = mrclean
                                    logger.info('[LAST_RELEASE] Branch: %s' % branch)
                                if 'tag' in i:
                                    i_clean = i.find('tag')
                                    mrclean = re.sub('tag: ', '', re.sub('[\(\)]', '', i[i_clean:])).strip()
                                    current_version_name = mrclean
                                    logger.info('[LAST_RELEASE] Version: %s' % current_version_name)
                            elif cnt == 1:
                                current_version = i.strip()
                                logger.info('[LAST_RELEASE] Commit: %s' % ''.join(current_version))
                            cnt+=1
            except Exception as e:
                logger.error('error: %s' % e)

        if current_version:
            if mylar.CONFIG.GIT_BRANCH:
                logger.info('Branch detected & set to : ' + mylar.CONFIG.GIT_BRANCH)
                return {'current_version': current_version, 'current_version_name': current_version_name, 'branch': mylar.CONFIG.GIT_BRANCH}
            else:
                if branch:
                    logger.info('Branch detected & set to : ' + branch)
                else:
                    branch = 'master'
                    logger.warn('No branch specified within config - could not poll version from mylar. Defaulting to %s' % branch)
                return {'current_version': current_version, 'current_version_name': current_version_name, 'branch': branch}
        else:
            if mylar.CONFIG.GIT_BRANCH:
                logger.info('Branch detected & set to : ' + mylar.CONFIG.GIT_BRANCH)
                return {'current_version': current_version, 'current_version_name': current_version_name, 'branch': mylar.CONFIG.GIT_BRANCH}
            else:
                logger.warn('No branch specified within config - will attempt to poll version from mylar')
                try:
                    branch = version.MYLAR_VERSION
                    logger.info('Branch detected & set to : ' + branch)
                except:
                    branch = 'master'
                    logger.info('Unable to detect branch properly - set branch in config.ini, currently defaulting to : ' + branch)
                return {'current_version': current_version, 'current_version_name': current_version_name, 'branch': branch}

            logger.warn('Unable to determine which commit is currently being run. Defaulting to Master branch.')

def checkGithub(current_version=None):
    if current_version is None:
        current_version = mylar.CURRENT_VERSION

    # Get the latest commit available from github
    url = 'https://api.github.com/repos/%s/mylar3/commits/%s' % (mylar.CONFIG.GIT_USER, mylar.CONFIG.GIT_BRANCH)
    try:
        response = requests.get(url, verify=True)
        git = response.json()
        mylar.LATEST_VERSION = git['sha']
    except Exception as e:
            logger.warn('[ERROR] Could not get the latest commit from github: %s' % e)
            mylar.COMMITS_BEHIND = 0
            return mylar.CURRENT_VERSION

    # See how many commits behind we are
    if current_version is not None:
        logger.fdebug('Comparing currently installed version [%s] with latest github version [%s]' % (current_version, mylar.LATEST_VERSION))
        url = 'https://api.github.com/repos/%s/mylar3/compare/%s...%s' % (mylar.CONFIG.GIT_USER, current_version, mylar.LATEST_VERSION)

        try:
            response = requests.get(url, verify=True)
            git = response.json()
            mylar.COMMITS_BEHIND = git['total_commits']
        except Exception as e:
            logger.warn('[ERROR] Could not get commits behind from github: %s' % e)
            mylar.COMMITS_BEHIND = 0
            return mylar.CURRENT_VERSION

        if mylar.COMMITS_BEHIND >= 1:
            logger.info('New version is available. You are %s commits behind' % mylar.COMMITS_BEHIND)
            if mylar.CONFIG.AUTO_UPDATE is True:
                mylar.SIGNAL = 'update'
        elif mylar.COMMITS_BEHIND == 0:
            logger.info('Mylar is up to date')
        elif mylar.COMMITS_BEHIND == -1:
            logger.info('You are running an unknown version of Mylar. Run the updater to identify your version')

    else:
        logger.info('You are running an unknown version of Mylar. Run the updater to identify your version')

    return mylar.LATEST_VERSION

def update():


    if mylar.INSTALL_TYPE == 'win':

        logger.info('Windows .exe updating not supported yet.')
        pass


    elif mylar.INSTALL_TYPE == 'git':

        output, err = runGit('pull origin ' + mylar.CONFIG.GIT_BRANCH)

        if output is None:
            logger.error('Couldn\'t download latest version')
            return

        for line in output.split('\n'):

            if 'Already up-to-date.' in line:
                logger.info('No update available, not updating')
                logger.info('Output: ' + str(output))
            elif line.endswith('Aborting.'):
                logger.error('Unable to update from git: ' +line)
                logger.info('Output: ' + str(output))

    else:

        tar_download_url = 'https://github.com/%s/mylar/tarball/%s' % (mylar.CONFIG.GIT_USER, mylar.CONFIG.GIT_BRANCH)
        update_dir = os.path.join(mylar.PROG_DIR, 'update')

        try:
            logger.info('Downloading update from: ' + tar_download_url)
            response = requests.get(tar_download_url, verify=True, stream=True)
        except (IOError, urllib.error.URLError):
            logger.error("Unable to retrieve new version from " + tar_download_url + ", can't update")
            return

        #try sanitizing the name here...
        download_name = mylar.CONFIG.GIT_BRANCH + '-github' #data.geturl().split('/')[-1].split('?')[0]
        tar_download_path = os.path.join(mylar.PROG_DIR, download_name)

        # Save tar to disk
        with open(tar_download_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()

        # Extract the tar to update folder
        logger.info('Extracting file' + tar_download_path)
        tar = tarfile.open(tar_download_path)
        tar.extractall(update_dir)
        tar.close()

        # Delete the tar.gz
        logger.info('Deleting file' + tar_download_path)
        os.remove(tar_download_path)

        # Find update dir name
        update_dir_contents = [x for x in os.listdir(update_dir) if os.path.isdir(os.path.join(update_dir, x))]
        if len(update_dir_contents) != 1:
            logger.error("Invalid update data, update failed: " +str(update_dir_contents))
            return
        content_dir = os.path.join(update_dir, update_dir_contents[0])

        # walk temp folder and move files to main folder
        for dirname, dirnames, filenames in os.walk(content_dir):
            dirname = dirname[len(content_dir) +1:]
            for curfile in filenames:
                old_path = os.path.join(content_dir, dirname, curfile)
                new_path = os.path.join(mylar.PROG_DIR, dirname, curfile)

                if os.path.isfile(new_path):
                    os.remove(new_path)
                os.renames(old_path, new_path)

def versionload():

    version_info = getVersion()
    logger.info('version_info: %s' % (version_info,))
    mylar.CURRENT_VERSION = version_info['current_version']
    mylar.CURRENT_VERSION_NAME = version_info['current_version_name']
    mylar.CONFIG.GIT_BRANCH = version_info['branch']

    if mylar.CURRENT_VERSION is not None:
        hash = mylar.CURRENT_VERSION[:7]
    else:
        hash = "unknown"

    if mylar.CONFIG.GIT_BRANCH == 'master':
        vers = 'M'
    elif mylar.CONFIG.GIT_BRANCH == 'python3-dev':
        vers = 'D'
    else:
        vers = 'NONE'

    mylar.USER_AGENT = 'Mylar3/' +str(hash) +'(' +vers +') +http://www.github.com/mylar3/mylar3/'

    logger.info('Version information: %s [%s]' % (mylar.CONFIG.GIT_BRANCH, mylar.CURRENT_VERSION))

    if mylar.CONFIG.CHECK_GITHUB_ON_STARTUP:
        try:
            mylar.LATEST_VERSION = checkGithub() #(CURRENT_VERSION)
        except:
            mylar.LATEST_VERSION = mylar.CURRENT_VERSION
    else:
        mylar.LATEST_VERSION = mylar.CURRENT_VERSION

    if mylar.CONFIG.AUTO_UPDATE:
        if mylar.CURRENT_VERSION != mylar.LATEST_VERSION and mylar.INSTALL_TYPE != 'win' and mylar.COMMITS_BEHIND > 0:
             logger.info('Auto-updating has been enabled. Attempting to auto-update.')
             mylar.SIGNAL = 'update'
