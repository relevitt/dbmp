# -*- coding: utf-8 -*-

from collections.abc import Mapping, Set, Sequence
import importlib
from .error import logError
from twisted.internet.defer import maybeDeferred
from twisted.protocols.basic import NetstringReceiver
from twisted.internet.protocol import ClientFactory
from twisted.internet import error
from twisted.internet import reactor
from twisted.python.failure import Failure
from pickle import loads, dumps, PicklingError
from .logging_setup import getLogger, spHandler
from .soco.exceptions import SoCoUPnPException
import logging
import sys
import os

log = getLogger()
# log.setLevel(logging.DEBUG)
log.setLevel(logging.INFO)
for handler in log.handlers[:]:
    log.removeHandler(handler)
custom_stream = os.fdopen(3, 'w', buffering=1)
handler = spHandler(custom_stream)
log.addHandler(handler)

module = importlib.import_module(sys.argv[1])

# This is an object walker, used to locate dumps errors
#


string_types = (str, bytes)
def iteritems(mapping): return getattr(mapping, 'iteritems', mapping.items)()


def objwalk(obj, path=(), memo=None):
    if memo is None:
        memo = set()
    iterator = None
    if isinstance(obj, Mapping):
        iterator = iteritems
    elif isinstance(obj, (Sequence, Set)) and not isinstance(obj, string_types):
        iterator = enumerate
    if iterator:
        if id(obj) not in memo:
            memo.add(id(obj))
            for path_component, value in iterator(obj):
                for result in objwalk(value, path + (path_component,), memo):
                    yield result
            memo.remove(id(obj))
    else:
        yield path, obj

# End of object walker

# MAXLEN is the maximum length of each communication.
# This sets a limit on the length returned by len(data)
# of data which our protocol can handle.


MAXLEN = 9999999999


class spwProtocol(NetstringReceiver):

    MAX_LENGTH = MAXLEN

    def __init__(self):
        if hasattr(module, 'setcoms'):
            setcoms = getattr(module, 'setcoms')
            setcoms(self)

    def connectionMade(self):
        self.send_data({
            'name': sys.argv[2],
            'index': sys.argv[4]
        })

    def stringReceived(self, data):
        try:
            command = loads(data)
            if command[0] == 'shutdown':
                if reactor.running:
                    try:
                        reactor.stop()
                    except error.ReactorNotRunning:
                        pass
                return
            # If module is os and command[0] is the string
            # 'path.isdir', executable becomes os.path.isdir
            executable = module
            for sub in command[0].split('.'):
                executable = getattr(executable, sub)
            log.debug('{}({},{})'.format(command[0], command[1], command[2]))
            maybeDeferred(
                executable,
                *command[1],
                **command[2]).addBoth(self.send_data).addErrback(logError)
        except Exception as e:
            log.exception('Exception received')
            self.send_data(Failure(e))

    def send_data(self, data, mode='D'):
        is_error = 'F'
        failure = None
        try:
            if isinstance(data, Failure):
                is_error = 'T'
                data, failure = {}, data
                data['exc_value'] = str(failure.value)
                data['exc_type'] = str(failure.type)
            pickled_data = dumps(data)

            if mode != 'D':
                log.debug(data)
            self.sendString(
                mode.encode(
                    'utf8') + is_error.encode(
                        'utf8') + pickled_data)
            if failure:
                if failure.check(SoCoUPnPException):
                    log.warning(f"SoCoUPnPException: {failure.value}")
                else:
                    failure.raiseException()
        except PicklingError as e:
            log.warning(
                'PicklingError in send_data ... trying to remove unpicklable object')
            try:
                cls = e.args[0].split("<class '")[1].split("'>")[0]
                log.warning('Unpicklable object was: {}'.format(cls))
                for item in objwalk(data):
                    if hasattr(item[1], '__class__'):
                        if cls in str(item[1].__class__):
                            obj = data
                            l = len(item[0])
                            for n in range(l):
                                if n < (l - 1):
                                    obj = obj[item[0][n]]
                                else:
                                    log.warning(
                                        'Unpicklable data address was: {}'.format(item[0]))
                                    try:
                                        new_obj = dict(obj[item[0][n]])
                                        log.warning(
                                            'Unpicklable object converted to dict: {}'.format(new_obj))
                                    except:
                                        try:
                                            new_obj = str(obj[item[0][n]])
                                            log.warning(
                                                'Unpicklable object converted to string: {}'.format(new_obj))
                                        except:
                                            new_obj = None
                                            log.warning(
                                                'Unpicklable object converted to: None')
                                    obj[item[0][n]] = new_obj
                            return self.send_data(data, mode)
            except Exception as e:
                log.exception('Error trying to remove unpicklable object')
                log.debug(data)
                if mode == 'D':
                    self.send_data(e)


class spwFactory(ClientFactory):

    protocol = spwProtocol


def main():
    reactor.connectTCP('localhost', int(sys.argv[3]), spwFactory())


if __name__ == '__main__':
    reactor.callWhenRunning(main)
    reactor.run()
