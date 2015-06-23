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

import platform, subprocess, re, os, urllib2, tarfile

import mylar
from mylar import logger, version

import lib.requests as requests
import re

#user = "evilhero"
#branch = "development"

def runGit(args):

    if mylar.GIT_PATH:
        git_locations = ['"' +mylar.GIT_PATH +'"']
    else:
        git_locations = ['git']

    if platform.system().lower() == 'darwin':
        git_locations.append('/usr/local/git/bin/git')


    output = err = None

    for cur_git in git_locations:

        cmd = cur_git +' ' +args

        try:
            logger.debug('Trying to execute: "' + cmd + '" with shell in ' + mylar.PROG_DIR)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, cwd=mylar.PROG_DIR)
            output, err = p.communicate()
            logger.debug('Git output: ' + output)
        except OSError:
            logger.debug('Command ' + cmd + ' didn\'t work, couldn\'t find git')
            continue

        if 'not found' in output or "not recognized as an internal or external command" in output:
            logger.debug('Unable to find git with command ' + cmd)
            output = None
        elif 'fatal:' in output or err:
            logger.error('Git returned bad info. Are you sure this is a git installation?')
            output = None
        elif output:
            break

    return (output, err)

def getVersion():

    if mylar.GIT_BRANCH is not None and mylar.GIT_BRANCH.startswith('win32build'):

        mylar.INSTALL_TYPE = 'win'

        # Don't have a way to update exe yet, but don't want to set VERSION to None
        return 'Windows Install', 'None'

    elif os.path.isdir(os.path.join(mylar.PROG_DIR, '.git')):

        mylar.INSTALL_TYPE = 'git'
        output, err = runGit('rev-parse HEAD')

        if not output:
            logger.error('Couldn\'t find latest installed version.')
            cur_commit_hash = None

        #branch_history, err = runGit("log --oneline --pretty=format:'%h - %ar - %s' -n 5")
        #bh = []
        #print ("branch_history: " + branch_history)
        #bh.append(branch_history.split('\n'))
        #print ("bh1: " + bh[0])

        cur_commit_hash = str(output).strip()

        if not re.match('^[a-z0-9]+$', cur_commit_hash):
            logger.error('Output does not look like a hash, not using it')
            cur_commit_hash = None

        if mylar.GIT_BRANCH:
            branch = mylar.GIT_BRANCH

        else:
            branch = None

            branch_name, err = runGit('branch --contains ' + cur_commit_hash) #rev-parse --abbrev-ref HEAD')
            for line in branch_name.split('\n'):
                if '*' in line:
                    branch = re.sub('[\*\n]','',line).strip()
                    break
            

            if not branch and mylar.GIT_BRANCH:
                logger.warn('Unable to retrieve branch name [' + branch + '] from git. Setting branch to configuration value of : ' + mylar.GIT_BRANCH)
                branch = mylar.GIT_BRANCH
            if not branch:
                logger.warn('Could not retrieve branch name [' + branch + '] form git. Defaulting to Master.')
                branch = 'master'
            else:
                logger.info('Branch detected & set to : ' + branch)

        return cur_commit_hash, branch

    else:

        mylar.INSTALL_TYPE = 'source'

        version_file = os.path.join(mylar.PROG_DIR, 'version.txt')

        if not os.path.isfile(version_file):
            current_version = None
        else:
            with open(version_file, 'r') as f:
                current_version = f.read().strip(' \n\r')

        if current_version:
            if mylar.GIT_BRANCH:
                logger.info('Branch detected & set to : ' + mylar.GIT_BRANCH)
                return current_version, mylar.GIT_BRANCH
            else:
                logger.warn('No branch specified within config - will attempt to poll version from mylar')
                try:
                    branch = version.MYLAR_VERSION
                    logger.info('Branch detected & set to : ' + branch)
                except:
                    branch = 'master'
                    logger.info('Unable to detect branch properly - set branch in config.ini, currently defaulting to : ' + branch)
                return current_version, branch
        else:
            if mylar.GIT_BRANCH:
                logger.info('Branch detected & set to : ' + mylar.GIT_BRANCH)
                return current_version, mylar.GIT_BRANCH
            else:
                logger.warn('No branch specified within config - will attempt to poll version from mylar')
                try:
                    branch = version.MYLAR_VERSION
                    logger.info('Branch detected & set to : ' + branch)
                except:
                    branch = 'master'
                    logger.info('Unable to detect branch properly - set branch in config.ini, currently defaulting to : ' + branch)
                return current_version, branch

            logger.warn('Unable to determine which commit is currently being run. Defaulting to Master branch.')

def checkGithub():

    # Get the latest commit available from github
    url = 'https://api.github.com/repos/%s/mylar/commits/%s' % (mylar.GIT_USER, mylar.GIT_BRANCH)
    logger.info ('Retrieving latest version information from github')
    try:
        response = requests.get(url, verify=True)
        git = response.json()
        mylar.LATEST_VERSION = git['sha']
    except:
        logger.warn('Could not get the latest commit from github')
        mylar.COMMITS_BEHIND = 0
        return mylar.CURRENT_VERSION

    # See how many commits behind we are
    if mylar.CURRENT_VERSION:
        logger.fdebug('Comparing currently installed version [' + mylar.CURRENT_VERSION + '] with latest github version [' + mylar.LATEST_VERSION +']')
        url = 'https://api.github.com/repos/%s/mylar/compare/%s...%s' % (mylar.GIT_USER, mylar.CURRENT_VERSION, mylar.LATEST_VERSION)

        try:
            response = requests.get(url, verify=True)
            git = response.json()
            mylar.COMMITS_BEHIND = git['total_commits']
        except:
            logger.warn('Could not get commits behind from github')
            mylar.COMMITS_BEHIND = 0
            return mylar.CURRENT_VERSION

        if mylar.COMMITS_BEHIND >= 1:
            logger.info('New version is available. You are %s commits behind' % mylar.COMMITS_BEHIND)
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

        output, err = runGit('pull origin ' + mylar.GIT_BRANCH)

        if not output:
            logger.error('Couldn\'t download latest version')

        for line in output.split('\n'):
           
            if 'Already up-to-date.' in line:
                logger.info('No update available, not updating')
                logger.info('Output: ' + str(output))
            elif line.endswith('Aborting.'):
                logger.error('Unable to update from git: ' +line)
                logger.info('Output: ' + str(output))
        
    else:

        tar_download_url = 'https://github.com/%s/mylar/tarball/%s' % (mylar.GIT_USER, mylar.GIT_BRANCH)
        update_dir = os.path.join(mylar.PROG_DIR, 'update')
        version_path = os.path.join(mylar.PROG_DIR, 'version.txt')

        try:
            logger.info('Downloading update from: ' + tar_download_url)
            response = requests.get(tar_download_url, verify=True, stream=True)
        except (IOError, urllib2.URLError):
            logger.error("Unable to retrieve new version from " + tar_download_url + ", can't update")
            return

        #try sanitizing the name here...
        download_name = mylar.GIT_BRANCH + '-github' #data.geturl().split('/')[-1].split('?')[0]
        tar_download_path = os.path.join(mylar.PROG_DIR, download_name)

        # Save tar to disk
        with open(tar_download_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()

        # Extract the tar to update folder
        logger.info('Extracing file' + tar_download_path)
        tar = tarfile.open(tar_download_path)
        tar.extractall(update_dir)
        tar.close()

        # Delete the tar.gz
        logger.info('Deleting file' + tar_download_path)
        os.remove(tar_download_path)

        # Find update dir name
        update_dir_contents = [x for x in os.listdir(update_dir) if os.path.isdir(os.path.join(update_dir, x))]
        if len(update_dir_contents) != 1:
            logger.error(u"Invalid update data, update failed: " +str(update_dir_contents))
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

        # Update version.txt
        try:
            with open(version_path, 'w') as f:
                f.write(str(mylar.LATEST_VERSION))
        except IOError, e:
            logger.error("Unable to write current version to version.txt, update not complete: " +ex(e))
            return
