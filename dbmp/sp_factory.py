# -*- coding: utf-8 -*-

from twisted.python.failure import Failure
from twisted.protocols.basic import NetstringReceiver
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.protocol import ServerFactory
from twisted.internet.error import ProcessExitedAlready
from twisted.internet import defer, reactor
from sys import executable
import os
from subprocess import Popen
from collections import deque
from pickle import dumps, loads
from .logging_setup import getLogger, WebSocketHandler, WS_DATEFMT
import json
from datetime import datetime
import logging

log = getLogger(__name__)


# MAXLEN is the maximum length of each communication.
# This sets a limit on the length returned by len(data)
# of data which our protocol can handle.

MAXLEN = 9999999999

# The processProtocol is used to log information from
# a subprocess to both webclients via websockets and
# the screen via logging. In retrospect, as logging
# already logs to webclients via websockets, this
# could have been implemented just using logging.
# However, I did logging to webclients first and
# then added logging to screen second as an
# afterthought. This has resulted in the screen display
# differing slightly from the webclient display.
# I could have changed this, for consistency and
# simplicity, but it would have meant some extra work,
# as it would also have meant recoding the webclients
# (probably not a lot of work). However, there may
# be a slight benefit to the way the webclient display
# has worked out (it displays "stderr" or "stdout" in
# the loglevel column), and it might not be easy to make
# the screen display conform to the webclient display,
# because "stderr" and "stdout" aren't known loglevels.


class processProtocol(ProcessProtocol):
    def __init__(self, wsfactory, name):
        self.wsfactory = wsfactory
        self.name = name[5:]  # Removes "dbmp_"
        self.logger = logging.getLogger()

    def create_log(self, childFD, txt, log=None):

        if not log:
            timestamp = datetime.now().strftime(WS_DATEFMT)[:-3]
            log = {
                'message': txt,
                'timestamp': timestamp,
                'color': 'black',
            }

        log['source'] = 'subprocess'
        # This overwrites the name of a log
        log['name'] = self.name

        if childFD == 1:
            log['level'] = 'stdout'
            log['level_color'] = 'black'
        elif childFD == 2:
            log['level'] = 'stderr'
            log['level_color'] = 'red'

        return log

    def log_to_root_logger(self, log):
        """ Creates a log record and emits it using root handlers. """
        try:
            level = getattr(logging, log.get(
                "level", "INFO").upper(), logging.INFO)
            msg = ""
            if log["level"] == "stderr":
                level = getattr(logging, "ERROR")
                msg = "Received on stderr: "
            if log["level"] == "stdout":
                msg = "Received on stdout: "
            msg += log["message"]

            record = logging.LogRecord(
                name=log["name"],
                level=level,
                pathname="subprocess",
                lineno=0,
                msg=msg,
                args=(),
                exc_info=None,
            )

            # Emit record using root logger handlers, excluding WebSocketHandler
            for handler in self.logger.handlers:
                if not isinstance(handler, WebSocketHandler):  # Avoid duplication
                    handler.emit(record)

        except Exception as e:
            self.logger.error(f"Failed to log subprocess message: {e}")

    def childDataReceived(self, childFD, data):

        txt = data.decode('utf8')

        if childFD == 3:
            try:
                for line in txt.splitlines():
                    log = self.create_log(childFD, line, json.loads(line))
                    self.wsfactory.broadcast_log(log)
                    self.log_to_root_logger(log)
                return

            except Exception as e:
                pass

        log = self.create_log(childFD, txt)
        self.wsfactory.broadcast_log(log)
        self.log_to_root_logger(log)


class spFactory(object):

    callback = None
    errback = None
    registered = False
    terminated = False

    def __init__(self, wsfactory, name, modulename, poolsize, index):
        self.wsfactory = wsfactory
        self.name = name
        self.modulename = modulename
        self.poolsize = poolsize
        self.index = index
        self.queue = deque([])
        self.protocols = []
        self.subprocesses = []

    def startup(self, port):
        for n in range(self.poolsize):
            _name = self.name if self.poolsize == 1 else '{}_{}'.format(
                self.name, n)
            subprocess = processProtocol(self.wsfactory, _name)
            reactor.spawnProcess(
                subprocess,
                executable=executable,
                args=(
                    '({}) {}'.format(_name, executable),
                    '-B',
                    '-u',
                    '-m',
                    'dbmp.sp_worker',
                    self.modulename,
                    _name,
                    str(port),
                    str(self.index)
                ),
                env=os.environ,
                childFDs={0: "w", 1: "r", 2: "r", 3: "r"}
            )
            self.subprocesses.append(subprocess)
        reactor.addSystemEventTrigger('before', 'shutdown', self.shutdown)

    def process_command(self, command, *args, **kwargs):
        d = defer.Deferred()
        self.queue.append((d, command, args, kwargs))
        self.send_next_command()
        return d

    def send_next_command(self):
        if not self.registered:
            return
        if len(self.queue):
            if not len(self.protocols):
                while len(self.queue):
                    self.queue.popleft()[0].callback(None)
            else:
                for protocol in self.protocols:
                    if protocol.ready:
                        protocol.send_command(self.queue.popleft())
                        break

    def process_quit(self, protocol):
        self.protocols.remove(protocol)
        # Callback all queued deferreds if pool empty
        self.send_next_command()

    def register_protocol(self, protocol):
        self.protocols.append(protocol)
        self.registered = True
        self.send_next_command()

    def shutdown(self):
        if self.terminated:
            return
        self.terminated = True
        for protocol in self.protocols:
            protocol.shutdown()

    def kill_zombies(self):
        for subprocess in self.subprocesses:
            try:
                subprocess.transport.signalProcess('KILL')
            except ProcessExitedAlready:
                pass
            except Exception as e:
                log.error(e)
        self.subprocesses = []


class spProtocol(NetstringReceiver):

    name = ''
    ready = False
    terminated = False
    deferred = None
    spFactory = None
    MAX_LENGTH = MAXLEN

    def send_command(self, command):
        self.ready = False
        self.deferred = command[0]
        self.send_data(command[1:])

    def return_output(self, output, data_mode, is_error):
        if self.terminated:
            return
        if data_mode == 'C':
            callback = self.spFactory.callback
            errback = self.spFactory.errback
        else:
            callback = self.deferred.callback
            errback = self.deferred.errback
        if is_error == 'T':
            log.warning(
                'Subprocess {} returned an error.'.format(self.name))
            if isinstance(output, dict) and 'exc_type' in output and 'exc_value' in output:
                err = Exception(f"{output['exc_type']}: {output['exc_value']}")
            else:
                err = Exception(f"Unknown subprocess error: {output}")
            errback(Failure(err))
        else:
            try:
                callback(output)
            except Exception as e:
                log.exception('Exception in return_output: {}'.format(str(e)))
        if data_mode != 'C':
            self.ready = True
            self.deferred = None
            self.spFactory.send_next_command()

    def register(self, details):
        self.name = details['name']
        self.spFactory = self.factory.get_spFactory(details['index'])
        self.ready = True
        self.spFactory.register_protocol(self)

    def shutdown(self, tell_process=True):
        if self.terminated:
            return
        self.terminated = True
        self.ready = False
        if self.deferred:
            self.deferred.callback(None)
            self.deferred = None
        if tell_process:
            self.send_data(['shutdown'])

    def send_data(self, data):
        self.sendString(dumps(data))

    def connectionLost(self, reason):
        self.shutdown(tell_process=False)
        self.spFactory.process_quit(self)

    def stringReceived(self, data):
        data_mode = chr(data[0])
        is_error = chr(data[1])
        output = loads(data[2:])
        if self.spFactory:
            self.return_output(output, data_mode, is_error)
        else:
            self.register(output)


class spServerFactory(ServerFactory):

    protocol = spProtocol
    spFactories = []

    def __init__(self, wsfactory):
        super(spServerFactory, self).__init__()
        self.wsfactory = wsfactory

    def create_subprocess(self, name, modulename, poolsize):
        index = len(self.spFactories)
        spf = spFactory(self.wsfactory, name, modulename, poolsize, index)
        self.spFactories.append(spf)
        return spf

    def start_spFactories(self, port):
        for spf in self.spFactories:
            spf.startup(port.port)

    def shutdown(self):
        for spf in self.spFactories:
            spf.shutdown()

    def kill_zombies(self):
        for spf in self.spFactories:
            spf.kill_zombies()

    def get_spFactory(self, index):
        spf = self.spFactories[int(index)]
        return spf
