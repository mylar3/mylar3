# This file is part of Mylar.
#
# Mylar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mylar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement

import mylar

from mylar import logger, helpers

#import threading

class dbUpdate():
    def __init__(self, sched):
        pass

    def run(self, sched):
        logger.info('[DBUpdate] Updating Database.')
        helpers.job_management(write=True, job='DB Updater', current_run=helpers.utctimestamp(), status='Running')
        mylar.updater.dbUpdate(sched=sched)
        helpers.job_management(write=True, job='DB Updater', last_run_completed=helpers.utctimestamp(), status='Waiting')
