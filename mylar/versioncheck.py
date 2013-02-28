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

import lib.simplejson as simplejson

user = "evilhero"
branch = "development"

def runGit(args):

    if mylar.GIT_PATH:
        git_locations = ['"'+mylar.GIT_PATH+'"']
    else:
        git_locations = ['git']
        
    if platform.system().lower() == 'darwin':
        git_locations.append('/usr/local/git/bin/git')
        
    
    output = err = None
    
    for cur_git in git_locations:
    
        cmd = cur_git+' '+args
    
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

    if version.MYLAR_VERSION.startswith('win32build'):
        
        mylar.INSTALL_TYPE = 'win'
        
        # Don't have a way to update exe yet, but don't want to set VERSION to None
        return 'Windows Install'
    
    elif os.path.isdir(os.path.join(mylar.PROG_DIR, '.git')):
    
        mylar.INSTALL_TYPE = 'git'
        output, err = runGit('rev-parse HEAD')
        
        if not output:
            logger.error('Couldn\'t find latest installed version.')
            return None
            
        #branch_history, err = runGit("log --oneline --pretty=format:'%h - %ar - %s' -n 5")
        #bh = []
        #print ("branch_history: " + branch_history)
        #bh.append(branch_history.split('\n'))
        #print ("bh1: " + bh[0])

        cur_commit_hash = output.strip()
        
        if not re.match('^[a-z0-9]+$', cur_commit_hash):
            logger.error('Output doesn\'t look like a hash, not using it')
            return None
            
        return cur_commit_hash
        
    else:
        
        mylar.INSTALL_TYPE = 'source'
        
        version_file = os.path.join(mylar.PROG_DIR, 'version.txt')
        
        if not os.path.isfile(version_file):
            return None
    
        fp = open(version_file, 'r')
        current_version = fp.read().strip(' \n\r')
        fp.close()
        
        if current_version:
            return current_version
        else:
            return None
    
def checkGithub():

    # Get the latest commit available from github
    url = 'https://api.github.com/repos/%s/mylar/commits/%s' % (user, branch)
    logger.info ('Retrieving latest version information from github')
    try:
        result = urllib2.urlopen(url).read()
        git = simplejson.JSONDecoder().decode(result)
        mylar.LATEST_VERSION = git['sha']
    except:
        logger.warn('Could not get the latest commit from github')
        mylar.COMMITS_BEHIND = 0
        return mylar.CURRENT_VERSION
    
    # See how many commits behind we are    
    if mylar.CURRENT_VERSION:
        logger.info('Comparing currently installed version with latest github version')
        url = 'https://api.github.com/repos/%s/mylar/compare/%s...%s' % (user, mylar.CURRENT_VERSION, mylar.LATEST_VERSION)
        
        try:
            result = urllib2.urlopen(url).read()
            git = simplejson.JSONDecoder().decode(result)
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
        
        output, err = runGit('pull origin ' + version.MYLAR_VERSION)
        
        if not output:
            logger.error('Couldn\'t download latest version')
            
        for line in output.split('\n'):
        
            if 'Already up-to-date.' in line:
                logger.info('No update available, not updating')
                logger.info('Output: ' + str(output))
            elif line.endswith('Aborting.'):
                logger.error('Unable to update from git: '+line)
                logger.info('Output: ' + str(output))
                
    else:
    
        tar_download_url = 'https://github.com/%s/mylar/tarball/%s' % (user, branch)
        update_dir = os.path.join(mylar.PROG_DIR, 'update')
        version_path = os.path.join(mylar.PROG_DIR, 'version.txt')
        
        try:
            logger.info('Downloading update from: '+tar_download_url)
            data = urllib2.urlopen(tar_download_url)
        except (IOError, URLError):
            logger.error("Unable to retrieve new version from "+tar_download_url+", can't update")
            return

        #try sanitizing the name here...            
        download_name = data.geturl().split('/')[-1].split('?')[0]
        tar_download_path = os.path.join(mylar.PROG_DIR, download_name)
        
        # Save tar to disk
        f = open(tar_download_path, 'wb')
        f.write(data.read())
        f.close()
        
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
            logger.error(u"Invalid update data, update failed: "+str(update_dir_contents))
            return
        content_dir = os.path.join(update_dir, update_dir_contents[0])
        
        # walk temp folder and move files to main folder
        for dirname, dirnames, filenames in os.walk(content_dir):
            dirname = dirname[len(content_dir)+1:]
            for curfile in filenames:
                old_path = os.path.join(content_dir, dirname, curfile)
                new_path = os.path.join(mylar.PROG_DIR, dirname, curfile)
                
                if os.path.isfile(new_path):
                    os.remove(new_path)
                os.renames(old_path, new_path)
                
        # Update version.txt
        try:
            ver_file = open(version_path, 'w')
            ver_file.write(mylar.LATEST_VERSION)
            ver_file.close()
        except IOError, e:
            logger.error(u"Unable to write current version to version.txt, update not complete: "+ex(e))
            return
