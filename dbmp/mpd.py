# -*- coding: utf-8 -*-

from .paths import MUSICPATH
from .error import logError, mpdException
from twisted.internet.utils import getProcessOutput
from twisted.python.failure import Failure
from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import ClientFactory
from twisted.internet import reactor, defer
import functools
from collections import deque
from pathlib import Path
import os
from logging import DEBUG
from .logging_setup import getLogger
log = getLogger(__name__)
log.setLevel(DEBUG)


def format_uri_for_mpd(uri):
    if not uri:
        return uri

    try:
        uri_path = Path(uri).absolute()
        musicpath = MUSICPATH.absolute()
        if musicpath in uri_path.parents:
            relative_path = uri_path.relative_to(musicpath)
            return str(relative_path)
    except Exception as e:
        log.warning(f"Failed to process URI '{uri}': {e}")

    return str(uri_path)


def keep_state(fn):
    '''
    This decorator is used to ensure that mpd remains in the same state
    (play / pause / stop) after the wrapped method is executed as it was in
    before.

    It should be used only to wrap the simplest methods in which:

    * The method does nothing more than execute and return an mpd command
      (being a command added to the mpd class via its __getattr__ method)

    * The method does not add any callback or errback.

    '''
    @functools.wraps(fn)
    def wrapper(self, *args):
        cmd = [fn(self.reflector, *args)]
        state = self.last_status.get('state', 'stop')
        if state == 'stop':
            cmd.append(self.reflector.stop())
        elif state == 'pause':
            cmd.append(self.reflector.pause(1))
        return self.factory.process_command(cmd)
    wrapper.__wrapped__ = fn
    return wrapper


class mpd(object):

    def __init__(self):
        self.factory = mpdFactory(self)
        self.reflector = Reflector()
        self.connected = False
        self.first_pass = True
        self.db_player = None
        self.playback_status_callbacks = []
        self.playlist_current_pos_callbacks = []
        self.volume_changed_callbacks = []
        self.last_status = {}
        self.update_queue = {}
        self.launch()

    def launch(self):

        def psSuccess(result):
            mpd_up = False
            for line in result.splitlines():
                line = line.decode('utf8')
                if 'mpd' in line:
                    if not 'defunct' in line:
                        mpd_up = True
                    else:
                        pid = int(line.split()[0])
                        os.kill(pid, 9)
            if mpd_up:
                self.start()
            else:
                mpd_launch()

        def psFailure(e):
            logError(e)
            mpd_launch()

        def mpd_launch():
            log.info('Launching mpd')
            d = getProcessOutput('mpd', errortoo=True)
            d.addCallback(mpdSuccess)
            d.addErrback(mpdFailure)

        def mpdSuccess(result):
            self.start()

        def mpdFailure(e):
            log.warning('There was a problem launching mpd')
            logError(e)

        d = getProcessOutput('ps', ('-eo', 'pid,comm'), errortoo=True)
        d.addCallback(psSuccess)
        d.addErrback(psFailure)

    def start(self):
        reactor.connectTCP('localhost', 6600, self.factory)

    def connectionMade(self):
        self.connected = True
        self.status().addCallback(
            lambda status: setattr(
                self, 'last_status', status)).addCallback(
            lambda _: self.db_player.start() if self.db_player else None)

    def connectionLost(self):
        self.connected = False

    def register_db_player(self, db_player):
        self.db_player = db_player
        if self.connected:
            self.db_player.start()

    def broadcast_playback_status(self, cb):
        self.playback_status_callbacks.append(cb)

    def broadcast_playlist_current_pos(self, cb):
        self.playlist_current_pos_callbacks.append(cb)

    def broadcast_playback_volume_changed(self, cb):
        self.volume_changed_callbacks.append(cb)

    def get_currently_playing(self):

        def cb(result):
            if isinstance(result, dict):  # If it's a dictionary
                return result.get('file', None)
            elif isinstance(result, list) and result:  # If it's a non-empty list
                first_item = result[0]
                if isinstance(first_item, dict):  # If the first item is a dictionary
                    return first_item.get('file', None)
            return None

        return self.currentsong().addCallback(cb)

    def get_output_time(self):
        return self.status().addCallback(
            lambda result: int(float(result.get('elapsed', 0)) * 1000))

    def jump(self, ms):
        self.play()
        return self.seekcur(ms/1000)

    def medialib_add_entry(self, uri):
        d = defer.Deferred()

        def update(result):
            job = int(result['updating_db'])
            self.update_queue[job] = d
        self.update(format_uri_for_mpd(uri)).addCallback(update)
        return d

    def medialib_get_info(self, uri):
        return self.find('file', format_uri_for_mpd(uri))

    @keep_state
    def next_track(self):
        return self.next()

    def play_pause(self):
        state = self.last_status.get('state', 'stop')
        if state == 'stop':
            return self.play()
        elif state == 'play':
            return self.pause(1)
        else:
            return self.pause(0)

    def playlist_add_file(self, filename):
        return self.add(format_uri_for_mpd(filename))

    def playlist_clear(self):
        return self.clear()

    def playlist_remove_entry(self, start, end=None):
        if end == None:
            r = start
        elif end == 'END':
            r = '{}:'.format(start)
        else:
            r = '{}:{}'.format(start, end)
        return self.delete(r)

    def set_main_volume(self, vol):
        if not vol:
            vol = 0
        return self.setvol(vol).addErrback(lambda _: None)

    @keep_state
    def set_queue_pos(self, n):
        return self.seek(n, 0)

    def command_list(self, cmds):
        '''
        cmds must be a list of tuples, each tuple in the form
        (action, arg1, arg2 ...)
        '''
        return self.factory.process_command(cmds)

    def event(self, result):

        def check_status(status):
            self.last_status, status = status, self.last_status
            for key, callbacks in [
                ('state', self.playback_status_callbacks),
                ('song', self.playlist_current_pos_callbacks),
                ('volume', self.volume_changed_callbacks)
            ]:
                if status.get(key, None) != self.last_status.get(key, None):
                    for cb in callbacks:
                        cb(self.last_status.get(key, None))
            if 'changed: update' in result:
                current_job = int(self.last_status.get('updating_db', 0))
                keys = list(self.update_queue.keys())
                for key in keys:
                    if not current_job or key < current_job:
                        self.update_queue[key].callback(None)
                        del self.update_queue[key]

        self.status().addCallback(check_status).addErrback(logError)

    def __getattr__(self, action):
        def _dispatcher(*args):
            """Dispatch to send_command."""
            return self.factory.process_command(action, *args)
        _dispatcher.__name__ = action
        setattr(self, action, _dispatcher)
        return _dispatcher


class Reflector(object):
    def __getattr__(self, action):
        def _dispatcher(*args):
            """Return tuple with action and args."""
            li = [action]
            li += args
            return tuple(li)
        _dispatcher.__name__ = action
        setattr(self, action, _dispatcher)
        return _dispatcher


def format_uri_from_mpd(uri):
    if not uri:
        return uri

    try:
        abs_path = (MUSICPATH / uri).absolute()
        return str(abs_path)
    except Exception as e:
        log.warning(f"Failed to resolve MPD URI '{uri}': {e}")
        return str(uri)  # fallback


def format_result(lines):
    result = {}
    results = None
    for line in lines:
        key, value = line.split(': ', maxsplit=1)
        if key == 'file':
            value = format_uri_from_mpd(value)
        if key in result.keys():
            if not results:
                results = []
            results.append(result)
            result = {}
        result[key] = value
    if results and result:
        results.append(result)
    return results if results else result


def tuple_to_string(t):
    cmd, args = t[0], t[1:]
    for arg in args:
        arg = str(arg)
        arg = arg.replace('''"''', r'''\"''')
        arg = arg.replace("""'""", r"""\'""")
        if ' ' in arg:
            arg = '"' + arg + '"'
        cmd += ' '
        cmd += arg
    return cmd


class mpdProtocol(LineReceiver):

    delimiter = b'\n'
    mpdversion = None
    received_output = []
    received_event = []
    deferred = None
    ready = False
    pending_command = None
    idling = False
    noidle_issued = False

    def no_idle(self):
        if self.idling:
            self.idling = False
            self.noidle_issued = True
            self.sendLine('noidle')

    def idle(self):
        if not self.idling:
            self.idling = True
            self.sendLine('idle')

    def send_command(self, command):
        self.ready = False
        self.deferred = command[0]
        cmd = command[1]  # a tuple
        if isinstance(cmd[0], list):  # a command list, comprising tuples
            cmd = [tuple_to_string(item) for item in cmd[0]]
        else:  # the tuple resulting from *args
            cmd = tuple_to_string(cmd)
        self.pending_command = cmd
        self.no_idle()

    def return_output(self, output, error):
        # log.debug('return_output %s', output)
        if not self.deferred:
            return
        if error:
            log.error('mpd returned error %s', output)
            self.deferred.errback(Failure(mpdException(output)))
        else:
            try:
                self.deferred.callback(format_result(output))
            except:
                log.exception('Exception in return_output')
        self.ready = True
        self.deferred = None
        self.factory.send_next_command()

    def return_event(self, output):
        log.debug('Event received: %s', output)
        self.factory.event(output)

    def sendLine(self, line):
        # log.debug('sendLine %s', line)
        super(mpdProtocol, self).sendLine(line.encode('utf8'))

    def lineReceived(self, line):
        line = line.decode('utf8')
        # log.debug('LineReceived %s', line)

        # The first thing the mpd daemon does after a connection is opened
        # is to sent the protocol version. We use self.mpdversion for the
        # sole purpose of ignoring this line on the one and only occasion
        # we receive it.
        if self.mpdversion == None:
            self.mpdversion = line.split(' ')[2]

        # 'OK' is used to signal the end of event notification, the end of
        # the return value of a command or, if there is no return value, to
        # acknowledge the command was received.
        elif line.startswith('OK'):

            # We can't be idling if we received 'OK'
            self.idling = False

            if self.received_event:
                event, self.received_event = self.received_event, []
                # Whenever we issue a noidle, it is acknowledged with an OK.
                # However event notification may precede this OK. Put another
                # way, if we get an event notification and its accompanying OK
                # after we issue a noidle, we aren't going to get another OK
                # to acknowledge the noidle. Therefore, whenever we receive
                # an event notification, we set self.noidle_issued to false,
                # so we know that noidle has been acknowledged.
                self.noidle_issued = False
                self.return_event(event)

            elif self.noidle_issued:
                # If we've issued a noidle, the first OK we receive afterwards
                # is to acknowledge it. Therefore, we set self.noidle_issued
                # to false, so we know it has been acknowledged and we don't
                # yet return output
                self.noidle_issued = False

            else:
                # If the OK didn't relate to event notification, nor was it
                # acknowledging a noidle, then it was acknowledging another
                # command and we can return the output
                output, self.received_output = self.received_output, []
                self.return_output(output, error=False)

            if self.pending_command:
                # Whenever we issue a command (other than idle / noidle), we
                # must first issue a noidle, because the default state of the
                # connection is idle. When the connection is in the idle
                # state, one is permitted only to send a noidle. If any other
                # command is issued while in the idle state, not only will
                # it be ignored, but the mpd daemon will drop the connection.
                # Therefore we must first issue a noidle, wait for it to be
                # acknowledged with an 'OK' and then issue the command we
                # wanted to issue. To deal with this, the command we wanted to
                # issue is set as self.pending_command. Whenever we get an
                # 'OK', we're no longer idling, so now we can send the
                # command. FFS.
                cmd, self.pending_command = self.pending_command, None
                if isinstance(cmd, list):
                    self.sendLine('command_list_begin')
                    for line in cmd:
                        self.sendLine(line)
                    self.sendLine('command_list_end')
                else:
                    self.sendLine(cmd)

            else:
                # If we aren't sending a command, then we go back into the
                # idle state. Why, you ask? First, so that we receive event
                # notifications and secondly because, if we don't, the mpd
                # daemon will drop the connection after 60 seconds.
                self.idle()

        # 'ACK' is used to signal an error
        elif line.startswith('ACK'):
            # We can't be idling if we received 'ACK'
            self.idling = False
            self.idle()
            self.received_output = []
            self.return_output(line[len('ACK '):], error=True)

        # 'changed' is used to signal an event
        elif line.startswith('changed'):
            self.received_event.append(line)

        # anything else is part of the return value of a command (depending
        # on the command, this could take multiple lines)
        else:
            self.received_output.append(line)

    def connectionMade(self):
        self.idle()
        self.ready = True
        self.factory.register_connection(self)
        self.factory.send_next_command()

    def connectionLost(self, reason):
        log.info('connectionLost')


class mpdFactory(ClientFactory):
    protocol = mpdProtocol
    connection = None

    def __init__(self, client):
        self.queue = deque([])
        self.client = client

    def process_command(self, *args):
        d = defer.Deferred()
        self.queue.append((d, args))
        self.send_next_command()
        return d

    def send_next_command(self):
        if len(self.queue):
            if self.connection and self.connection.ready:
                self.connection.send_command(self.queue.popleft())

    def register_connection(self, connection):
        self.connection = connection
        self.client.connectionMade()

    def event(self, result):
        self.client.event(result)

    def clientConnectionLost(self, connector, reason):
        log.info('clientConnectionLost')
        self.client.connectionLost()
