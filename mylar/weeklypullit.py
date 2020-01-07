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



import mylar

from mylar import logger, helpers, weeklypull

class Weekly():
    def __init__(self):
        pass

    def run(self):
        logger.info('[WEEKLY] Checking Weekly Pull-list for new releases/updates')
        helpers.job_management(write=True, job='Weekly Pullist', current_run=helpers.utctimestamp(), status='Running')
        mylar.WEEKLY_STATUS = 'Running'
        weeklypull.pullit()
        weeklypull.future_check()
        helpers.job_management(write=True, job='Weekly Pullist', last_run_completed=helpers.utctimestamp(), status='Waiting')
        mylar.WEEKLY_STATUS = 'Waiting'

