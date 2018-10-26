import os
import subprocess
import time
import sys
import cherrypy

from threading import Thread, Lock
from Queue import Queue, Empty, Full

try:
    import json
except ImportError:
    import simplejson as json


class PluginRunner:

    def __init__(self, runtime_path, plugin_path, logger, command_timeout=5):
        self.runtime_path = runtime_path
        self.plugin_path = plugin_path
        self.logger = logger
        self.command_timeout = command_timeout

        self._cid = 0
        self._proc = None
        self._stopped = False
        self._out_thread = None
        self._command_lock = Lock()
        self._response_queue = None

        self._async_command_thread = None
        self._async_command_queue = None

        self._commands_executed = 0
        self._commands_failed = 0

        self.__collector_runs = {}

    def start(self):
        python_executable = sys.executable
        if python_executable is None or len(python_executable) == 0:
            python_executable = "/usr/bin/python"

        self._proc = subprocess.Popen(
                        [python_executable, "runtime.py", "start", self.plugin_path],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
                        cwd=self.runtime_path, universal_newlines=True, bufsize=1)

        self._stopped = False
        self._commands_executed = 0
        self._commands_failed = 0

        self._response_queue = Queue()
        self._out_thread = Thread(target=self._read_out,
                                  name="PluginRunner %s stdout reader" % self.plugin_path)
        self._out_thread.daemon = True
        self._out_thread.start()

        start_out = self._do_command('start')
        self.name = start_out['name']
        self.version = start_out['version']
        self.interfaces = start_out['interfaces']

        self._receivers = start_out['receivers']
        self._exposes = start_out['exposes']
        self._metric_collectors = start_out['metric_collectors']
        self._metric_receivers = start_out['metric_receivers']

        self._async_command_queue = Queue(100)
        self._async_command_thread = Thread(target=self._perform_async_commands,
                                            name="PluginRunner %s async thread" % self.plugin_path)
        self._async_command_thread.daemon = True
        self._async_command_thread.start()

    def get_webservice(self):
        class Service:
            def __init__(self, runner):
                self.runner = runner

            def _cp_dispatch(self, vpath):
                method = vpath.pop()
                for exposed in self.runner._exposes:
                    if exposed['name'] == method:
                        cherrypy.request.params['method'] = method
                        cherrypy.response.headers['Content-Type'] = exposed['content_type']
                        if exposed['auth'] is True:
                            cherrypy.request.hooks.attach('before_handler',
                                                          cherrypy.tools.authenticated.callable)
                        return self

                raise cherrypy.HTTPError(404)

            @cherrypy.expose
            def index(self, method, *args, **kwargs):
                return self.runner.request(method, args=args, kwargs=kwargs)

        return Service(self)

    def is_stopped(self):
        return self._stopped

    def stop(self):
        if not self._stopped:
            self.logger("[Runner] Sending stop command")
            try:
                self._do_command('stop')
            except Exception as exception:
                self.logger("[Runner] Exception during stopping plugin: %s" % exception)

            time.sleep(0.1)

            if self._proc.poll() is None:
                self.logger("[Runner] Terminating process")
                try:
                    self._proc.terminate()
                except Exception as exception:
                    self.logger("[Runner] Exception during terminating plugin: %s" % exception)
                time.sleep(0.5)

                if self._proc.poll() is None:
                    self.logger("[Runner] Killing process")
                    try:
                        self._proc.kill()
                    except Exception as exception:
                        self.logger("[Runner] Exception during killing plugin: %s" % exception)

            self._stopped = True

    def process_input_status(self, status):
        self._do_async('input_status', {'status':status}, filter=True)

    def process_output_status(self, status):
        self._do_async('output_status', {'status':status}, filter=True)

    def process_shutter_status(self, status):
        self._do_async('shutter_status', {'status':status}, filter=True)

    def process_event(self, code):
        self._do_async('process_event', {'code':code}, filter=True)

    def collect_metrics(self):
        for mc in self._metric_collectors:
            try:
                now = time.time()
                (name, interval) = (mc['name'], mc['interval'])

                if self.__collector_runs.get(name, 0) < now - interval:
                    self.__collector_runs[name] = now
                    metrics = self._do_command('collect_metrics', {'name':name})['metrics']
                    for metric in metrics:
                        if metric is None:
                            continue
                        metric['source'] = self.name
                        yield metric
            except Exception as exception:
                self.logger("[Runner] Exception while collecting metrics %s: %s" % (exception, traceback.format_exc()))

    def get_metric_receivers(self):
        return self._metric_receivers

    def distribute_metric(self, method, metric):
        self._do_async('distribute_metric', {'name':method, 'metric':metric})

    def get_metric_definitions(self):
        return self._do_command('get_metric_definitions')['metric_definitions']

    def request(self, method, args=[], kwargs={}):
        ret = self._do_command('request', {'method':method, 'args':args, 'kwargs':kwargs})
        if ret['success']:
            return ret['response']
        else:
            raise Exception('%s : %s' % (ret['exception'], ret['stacktrace']))

    def remove_callback(self):
        self._do_command('remove_callback')

    def _read_out(self):
        while not self._stopped:
            exit_code = self._proc.poll()
            if exit_code is not None:
                self.logger("[Runner] Stopped with exit code %s" % exit_code)
                self._stopped = True
                break

            try:
                line = self._proc.stdout.readline()
            except Exception as exception:
                self.logger("[Runner] Exception while reading output: %s" % exception)
            else:
                if line is not None and len(line) > 0:
                    line = line.strip()
                    try:
                        response = json.loads(line)
                    except ValueError:
                        self.logger("[Runner] JSON error in reading output (%s)" % line)
                    else:
                        if response['cid'] == 0:
                            self._handle_async_response(response)
                        elif response['cid'] == self._cid:
                            self._handle_response(response)
                        else:
                            self.logger("[Runner] Received message with unknown cid: %s" % response)

    def _handle_async_response(self, response):
        if response['action'] == 'logs':
            self.logger(response['logs'])
        else:
            self.logger("[Runner] Unkown async message: %s" % response)

    def _handle_response(self, response):
        self._response_queue.put(response)

    def _do_async(self, action, fields, filter=False):
        if (filter and action not in self._receivers) or self._stopped:
            return

        try:
            self._async_command_queue.put({'action':action, 'fields':fields}, block=False)
        except Full:
            self.logger("Async action cannot be queued, queue is full")

    def _perform_async_commands(self):
        while not self._stopped:
            try:
                # Give it a timeout in order to check whether the plugin is not stopped.
                command = self._async_command_queue.get(block=True, timeout=10)
                self._do_command(command['action'], command['fields'])
            except Empty:
                pass
            except Exception as exception:
                self.logger("[Runner] Failed to perform async command: %s" % exception)

    def _do_command(self, action, fields={}):
        self._commands_executed += 1

        if self._stopped:
            raise Exception('Plugin was stopped')

        with self._command_lock:
            command = self._create_command(action, fields)
            self._proc.stdin.write(json.dumps(command) + '\n')
            self._proc.stdin.flush()

            try:
                response = self._response_queue.get(block=True, timeout=self.command_timeout)
                while response['cid'] != self._cid:
                    response = self._response_queue.get(block=False)
                return response
            except Empty:
                self.logger("[Runner] No response within timeout (action=%s, fields=%s)" % (action, fields))
                self._commands_failed += 1
                raise Exception('Plugin did not respond')

    def _create_command(self, action, fields={}):
        self._cid += 1
        command = { 'cid' : self._cid, 'action' : action }
        command.update(fields)
        return command

    def error_score(self):
        if self._commands_executed == 0:
            return 0
        else:
            (self._commands_failed, self._commands_executed, score) = (0, 0, float(self._commands_failed) / self._commands_executed)
            return score


class RunnerWatchdog:

    def __init__(self, plugin_runner, threshold=0.25, check_interval=60):
        self._plugin_runner = plugin_runner
        self._threshold = threshold
        self._check_interval = check_interval
        self._stopped = False

    def stop(self):
        self._stopped = True

    def start(self):
        thread = Thread(target=self.run, name="RunnerWatchdog for %s" % self._plugin_runner.plugin_path)
        thread.daemon = True
        thread.start()

    def run(self):
        while not self._stopped:
            try:
                score = self._plugin_runner.error_score()
                if score > self._threshold:
                    self._plugin_runner.logger("[Watchdog] Stopping unhealthy runner")
                    self._plugin_runner.stop()
                if self._plugin_runner.is_stopped():
                    self._plugin_runner.logger("[Watchdog] Starting stopped runner")
                    self._plugin_runner.start()
            except Exception as e:
                self._plugin_runner.logger("[Watchdog] Exception in watchdog: %s" % e)

            time.sleep(self._check_interval)
