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
""" The OpenMotics plugin decorators. """

import cherrypy


def om_expose(method=None, auth=True, content_type='application/json'):
    """
    Decorator to expose a method of the plugin class through the
    webinterface. The url will be /plugins/<plugin-name>/<method>.

    Normally an authentication token is required to access the method.
    The token will be checked and removed automatically when using the
    following construction:

    @om_expose
    def method_to_expose(self, ...):
        ...

    It is possible to expose a method without authentication: no token
    will be required to access the method, this is done as follows:

    @om_expose(auth=False)
    def method_to_expose(self, ...):
        ...
    """
    def decorate(func):
        def _exposed(*args, **kwargs):
            result = func(*args, **kwargs)
            cherrypy.response.headers["Content-Type"] = content_type
            return result
        if auth is True:
            _exposed = cherrypy.tools.authenticated()(_exposed)
        _exposed.exposed = True
        _exposed.auth = auth
        _exposed.orig = func
        return _exposed

    if method is not None:
        return decorate(method)
    return decorate


def input_status(method):
    """
    Decorator to indicate that the method should receive input status messages.
    The receiving method should accept one parameter, a tuple of (input, output).
    Each time an input is pressed, the method will be called.

    Important !This method should not block, as this will result in an unresponsive system.
    Please use a separate thread to perform complex actions on input status messages.
    """
    method.input_status = True
    return method


def output_status(method):
    """
    Decorator to indicate that the method should receive output status messages.
    The receiving method should accept one parameter, a list of tuples (output, dimmer value).
    Each time an output status is changed, the method will be called.

    Important !This method should not block, as this will result in an unresponsive system.
    Please use a separate thread to perform complex actions on output status messages.
    """
    method.output_status = True
    return method


def shutter_status(method):
    """
    Decorator to indicate that the method should receive shutter status messages.
    The receiving method should accept one parameter, the list of shutter states.
    Each time an shutter status is changed, the method will be called.

    Important !This method should not block, as this will result in an unresponsive system.
    Please use a separate thread to perform complex actions on shutten status messages.
    """
    method.shutter_status = True
    return method


def receive_events(method):
    """
    Decorator to indicate that the method should receive event messages.
    The receiving method should accept one parameter: the event code.
    Each time an event is triggered, the method will be called.

    Important !This method should not block, as this will result in an unresponsive system.
    Please use a separate thread to perform complex actions on event messages.
    """
    method.receive_events = True
    return method


def background_task(method):
    """
    Decorator to indicate that the method is a background task. A thread running this
    background task will be started on startup.
    """
    method.background_task = True
    return method


def on_remove(method):
    """
    Decorator to indicate that the method should be called just before removing the plugin.
    This can be used to cleanup files written by the plugin. Note: the plugin package and plugin
    configuration data will be removed automatically and should not be touched by this method.
    """
    method.on_remove = True
    return method


def om_metric_data(interval=5):
    """
    Decorator to indicate that the method should be called periodically to retrieve metrics
    provided by the plugin.
    """
    try:
        interval = int(interval)
    except ValueError:
        interval = 5

    def decorate(method):
        method.metric_data = {'interval': interval}
        return method
    return decorate


def om_metric_receive(source=None, metric_type=None, interval=None):
    """
    Decorator to indicate that the decorated method should be called when new data mathing the
    filter is available.
    """
    def decorate(method):
        """ The decorated method. """
        method.metric_receive = {'source': source,
                                 'metric_type': metric_type,
                                 'interval': interval}
        return method
    return decorate
