# Copyright (C) 2016 OpenMotics BVBA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

os.environ['PYTHON_EGG_CACHE'] = '/tmp/.eggs-cache/'
path = '{0}/../../src/eggs'.format(os.path.dirname(__file__))
for egg in os.listdir(path):
    if egg.endswith('.egg'):
        sys.path.insert(0, '{0}/{1}'.format(path, egg))
