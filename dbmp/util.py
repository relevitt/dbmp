# -*- coding: utf-8 -*-

from .error import logError
from .config import PORT, SSL_PORT
from .meta import __appname__, __version__, __url__
from twisted.web.http_headers import Headers
from twisted.web.client import Agent, BrowserLikeRedirectAgent, readBody, FileBodyProducer
from twisted.internet import reactor
from twisted.internet import task
from twisted.internet import defer
from binaryornot.helpers import is_binary_string
import time
import json
import urllib.parse
from io import BytesIO
import random
import hashlib
import functools
import socket
import ipaddress
from .logging_setup import getLogger
log = getLogger(__name__)


def dbpooled(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return self.dbpool.runInteraction(fn, self, *args, **kwargs)
    wrapper.__wrapped__ = fn
    return wrapper


def serialised(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return self.serialise(fn, self, *args, **kwargs).addErrback(logError)
    wrapper.__wrapped__ = fn
    return wrapper


def serialised2(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return self.serialise2(fn, self, *args, **kwargs).addErrback(logError)
    wrapper.__wrapped__ = fn
    return wrapper


def database_serialised(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return self.objects['database_serialiser'].serialise(fn, self, *args, **kwargs).addErrback(logError)
    wrapper.__wrapped__ = fn
    return wrapper


def spotify_cache_serialised(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return self.objects['spotify_cache_serialiser'].serialise(fn, self, *args, **kwargs).addErrback(logError)
    wrapper.__wrapped__ = fn
    return wrapper


def snapshot(fn):
    @functools.wraps(fn)
    def wrapper(self, args):
        d = self.check_snapshot_id(
            # playlist and album use 'container_id', while dbplayer uses 'id'
            # and sonos uses 'uid', but sonos doesn't need the parameter,
            # because 'uid' has already been used to send the command to a
            # sonos_group object. Perhaps we should standardise, but it would
            # involve changing lots of other things
            args.get('container_id', args.get('id', None)),
            args['snapshot_id']
        )

        def process(result):
            passed, res = result
            if not passed:
                return res
            d = fn(self, args)
            d.addCallback(self.update_snapshot_id)
            return d
        d.addCallback(process)
        return d
    wrapper.__wrapped__ = fn
    return wrapper


def mpd_check_connected(retvalue):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            if not self.mpd.connected:
                d = defer.Deferred()
                d.callback(retvalue)
                return d
            return fn(self, *args, **kwargs)
        wrapper.__wrapped__ = fn
        return wrapper
    return decorator


def logerror(fn):
    @functools.wraps(fn)
    def wrapper(*args):
        d = fn(*args)
        d.addErrback(logError)
        return d
    wrapper.__wrapped__ = fn
    return wrapper


# Password protection is intended as a simple way of
# protecting against some forms of accidental data
# corruption or to warn users they may be invoking
# functionality aimed at debugging. It's not there
# to provide a high level of security. This "protection"
# could easily be bypassed. In any case, the database
# and related files aren't encrypted. The main reason
# for hashing the password is so that, if a regularly
# used password is chosen (like a login password),
# it won't be easy to figure out from the hash stored
# in the database what it actually is.

def authenticated(fn):

    @functools.wraps(fn)
    def wrapper(self, args):
        return authenticate(fn, self, args).addErrback(logError)
    wrapper.__wrapped__ = fn
    return wrapper


def authenticate(fn, self, args):

    digest = self.objects['config'].get('pwd')
    if not digest:
        return defer.maybeDeferred(fn, self, args)

    @database_serialised
    @dbpooled
    def get_auth_access(tx, self, args):
        cutoff = int(time.time()) - 900  # 15 minutes
        query = '''DELETE FROM auth_access WHERE time < ?'''
        tx.execute(query, (cutoff,))
        query = '''SELECT COUNT(*) FROM auth_access WHERE clientid =?'''
        tx.execute(query, (args['client_id'],))
        return tx.fetchone()[0]

    @database_serialised
    @dbpooled
    def update_auth_access(tx, self, clientid):
        query = '''SELECT COUNT(*) FROM auth_access WHERE clientid =?'''
        tx.execute(query, (clientid,))
        if tx.fetchone()[0]:
            query = '''UPDATE auth_access SET time = ? WHERE clientid = ?'''
        else:
            query = '''INSERT INTO auth_access (time, clientid) VALUES (?, ?)'''
        tx.execute(query, (int(time.time()), clientid))

    def check_pwd(pwd):
        if pwd == 'CANCELLED':
            return 'UNAUTHORISED'
        else:
            if digest == hashlib.sha256(pwd.encode()).hexdigest():
                update_auth_access(self, args['client_id'])
                return fn(self, args)
            else:
                d = self.objects['wsfactory'].WS_wrong_pwd(args['sid'])
                d.addCallback(check_pwd)
                return d

    def check_auth_access(authorised):
        if authorised:
            update_auth_access(self, args['client_id'])
            return fn(self, args)
        else:
            d = self.objects['wsfactory'].WS_get_pwd(args['sid'])
            d.addCallback(check_pwd)
            return d

    d = get_auth_access(self, args)
    d.addCallback(check_auth_access)
    return d


class cached(object):

    '''Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated). The function must take exactly two arguments, being
    self and a dict, and return a defer.Deferred().
    '''

    def __init__(self, func):
        self.func = func
        self.cache = {}
        self.timeout = 60*60  # A cached item will be deleted after an hour

    def __call__(self, _self, args):
        f = hash(frozenset(args.items()))
        if f in self.cache:
            d = defer.Deferred()
            d.callback(self.cache[f]['value'])
            self.cache[f]['task'].cancel()
            self.cache[f]['task'] = reactor.callLater(
                self.timeout, self.delete, f)
            return d
        else:
            d = self.func(_self, args)

            def process(value):
                self.cache[f] = {}
                self.cache[f]['value'] = value
                self.cache[f]['task'] = reactor.callLater(
                    self.timeout, self.delete, f)
                return value
            d.addCallback(process)
            return d

    def delete(self, f):
        del self.cache[f]

    def __repr__(self):
        '''Return the function's docstring.'''
        return self.func.__doc__

    def __get__(self, obj, objtype):
        '''Support instance methods.'''
        return functools.partial(self.__call__, obj)


def httpRequest(method, url, headers={}, values=None, jsonPOST=False):

    if IP.IP == '127.0.0.1':
        log.warning('Unable to reach %s... not connected to network', url)
        d = defer.Deferred()
        d.callback(None)
        return d

    if 'User-Agent' not in headers.keys():
        app = f"{__appname__}/{__version__}"
        headers['User-Agent'] = [f"{app} ({__url__})"]

    if values:
        if jsonPOST:
            if 'Content-Type' not in headers.keys():
                headers['Content-Type'] = ['application/json']
            data = json.dumps(values)
        else:
            data = urllib.parse.urlencode(values)
    else:
        data = None

    agent = BrowserLikeRedirectAgent(Agent(reactor))

    d = agent.request(
        method.encode('utf8'),
        url.encode('latin-1'),
        Headers(headers),
        FileBodyProducer(BytesIO(data.encode('utf8'))) if data else None
    )

    def decode(data):
        with BytesIO(data) as f:
            if is_binary_string(f.read(1024)):
                return data
        try:
            return data.decode('utf8')
        except UnicodeDecodeError:
            pass
        return data.decode('latin-1')

    def cbResponse(response):
        if response.code >= 200 and response.code < 400:
            return readBody(response).addCallback(
                lambda data: decode(data))
        else:
            log.warning(
                'There was a problem accessing {}:{}:{}'.format(
                    url,
                    response.code,
                    response.phrase))
            return None

    d.addCallback(cbResponse)
    return d


class util(object):

    def __init__(self, objects):
        self.objects = objects

    def directory(self, args):
        return self.objects['spfactory'].process_command('listdir', args['items'][0], args['items'][1])

    def set_password(self, pwd):
        digest = hashlib.sha256(pwd.encode()).hexdigest()
        self.objects['config'].set('pwd', digest)
        self.objects['wsfactory'].WS_send_all({
            "type": "password",
            "password_set": True})


def str_to_ms(s):
    '''
    Accepts a string in the format 'hh:mm:ss' or 'mm:ss'
    and returns milliseconds as an integer or None if there
    was an error
    '''

    if s is None:
        return None
    try:
        l = s.split(':')
        minutes = l[-2]
        seconds = l[-1]
        if len(l) > 2:
            hours = l[-3]
        else:
            hours = 0
        ms = (int(hours) * 60 * 60 + int(minutes) * 60 + int(seconds)) * 1000
        return ms
    except:
        log.exception('Problem in str_to_ms')
        return None


def ms_to_str(m, two_columns=False):
    '''
    Accepts milliseconds as an integer and returns a
    string in the format 'h:mm:ss' or None if there
    was an error
    '''

    try:
        m = float(m)
        hours = int(m // (60000 * 60))
        minutes = int(m // 60000 % 60)
        seconds = int(round((m / 1000) % 60))
        if two_columns and not hours:
            output = ''
        else:
            output = '' + str(hours) + ':'
        if minutes < 10:
            output += '0'
        output += str(minutes)
        output += ':'
        if seconds < 10:
            output += '0'
        output += str(seconds)
        return output
    except:
        log.exception('Problem in ms_to_str')
        return None


class ip(object):

    def __init__(self):
        self.IP = None
        self.network_down = True
        self.network_up_functions = []
        self.network_down_functions = []
        self.poll_ip()

    def poll_ip(self):
        '''
        Attempts to return the IP address of the host on which
        the app is running. There may be a better way of doing this!
        '''

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 0))
            IP = s.getsockname()[0]
        except:
            IP = '127.0.0.1'
        finally:
            s.close()

        if self.IP != IP:
            Old_IP, self.IP = self.IP, IP
            if IP == '127.0.0.1':
                self.network_down = True
                for fn in self.network_down_functions:
                    fn()
            elif Old_IP is None or Old_IP == '127.0.0.1':
                self.network_down = False
                for fn in self.network_up_functions:
                    fn()
            else:
                self.network_down = True
                for fn in self.network_down_functions:
                    fn()
                self.network_down = False
                for fn in self.network_up_functions:
                    fn()

        task.deferLater(reactor, 1, self.poll_ip)

    def register(self, network_up_function, network_down_function):
        self.network_up_functions.append(network_up_function)
        self.network_down_functions.append(network_down_function)
        if self.IP:
            if self.network_down:
                network_down_function()
            else:
                network_up_function()

    def is_local_lan_url(self, url):
        try:
            # extract `192.168.68.102:1400`
            parsed = url.split("//", 1)[-1].split("/")[0]
            ip_str = parsed.split(":")[0]
            return ipaddress.IPv4Address(ip_str) in ipaddress.IPv4Network(self.IP + '/24', strict=False)
        except:
            return False


IP = ip()


def print_browser_connection_hint():
    local_ip = IP.IP
    width = 52
    print("\n" + "     " + "*" * (width + 4))
    print(f"     * {'':<{width}} *")
    print(
        f"     * {'You can connect to dbmp by pointing your browser to':<{width}} *")
    print(
        f"     * {'any of the following (use localhost only if you are':<{width}} *")
    print(f"     * {'connecting from the same PC):':<{width}} *")
    print(f"     * {'':<{width}} *")
    print(f"     * {'https://localhost:' + str(SSL_PORT):<{width}} *")
    print(f"     * {'http://localhost:' + str(PORT):<{width}} *")
    print(f"     * {'https://' + local_ip + ':' + str(SSL_PORT):<{width}} *")
    print(f"     * {'http://' + local_ip + ':' + str(PORT):<{width}} *")
    print(f"     * {'':<{width}} *")
    print("     " + "*" * (width + 4) + "\n")


def create_album_art_uri(discid, timestamp):
    '''
    Returns an album art uri (using the IP address of the host on which the app
    is running) that should work anywhere on the LAN. The uri is in the form recognised
    by the '/get_cover' cmd to the server.
    '''
    return 'http://{}:{}/get_cover?i={}&t={}'.format(IP.IP, PORT, discid, timestamp or 0)


def create_moves(indices, dest, offset=0):
    '''
    Example:
            You have a list [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
            You wish to move items 0, 2, 4, 6 to before position 3
            The new order will therefore be [1, 0, 2, 4, 6, 3, 5, 7, 8, 9]
            create_moves([0,2,4,6], 3) will return [(0, 3), (1, 3), (4, 3), (6, 4)]
            If you make each of these moves in sequence, the desired result will be achieved:
            After first move [1, 2, 0, 3, 4, 5, 6, 7, 8, 9]
            After second move [1, 0, 2, 3, 4, 5, 6, 7, 8, 9]
            After third move [1, 0, 2, 4, 3, 5, 6, 7, 8, 9]
            After fourth move [1, 0, 2, 4, 6, 3, 5, 7, 8, 9]

    Arguments:
            indices: a list of indices to be moved
            dest: the position before which the indices are to be moved
            offset: an offset to be added to each resulting index and dest tuple

    Returns:
            A list of (index, dest) tuples, representing each individual move required.

    '''

    moves = []
    indices.sort()
    while len(indices):
        index = indices.pop(0)
        if dest == index:
            dest += 1
            continue
        if dest == index + 1:
            continue
        moves.append((index + offset, dest + offset))
        if dest < index:
            dest += 1
        if dest > index:
            for n, i in enumerate(indices):
                if i < dest:
                    indices[n] -= 1
    return moves


def random_moves(length, offset=0, indices=None):
    '''
            Using brute force, return a list of moves in the form:

              [(start1, dest1), (start2, dest2) ... ]

            which will randomise a list of the given length
    '''

    moves = []
    li1 = list(range(length))
    li2 = indices or list(range(length))
    if not indices:
        random.shuffle(li2)
    for newindex in range(length - 1, -1, -1):
        item = li2[newindex]
        oldindex = li1.index(item)
        moves.append((oldindex + offset, newindex + 1 + offset))
        li1.insert(newindex, li1.pop(oldindex))
    return moves


def get_track_range_tuples(li):
    '''
    Analyses a list of integers (which has already been sorted into ascending or descending order),
    each integer representing the position of a track in a queue, and returns
    a list of tuples each in the form (StartingIndex, NumberOfTracks) where:
            StartingIndex:	is an integer, representing the first track in
                            an unbroken range of tracks
            NumberOfTracks: is an integer, representing the number of tracks in
                            that unbroken range
    Example:

            get_track_range_tuples([11, 10, 9, 8, 6, 5, 4, 2, 1])

            returns [(8, 4), (4, 3), (1, 2)]
    '''

    tuple_list = []
    start_index = 0
    length = len(li)
    if length:
        if li[0] > li[length - 1]:
            interval = -1
        else:
            interval = 1
    previous_value = li[0] - interval
    for i, value in enumerate(li):
        if value != previous_value + interval:
            if interval == -1:
                tuple_list.append((li[i - 1], i - start_index))
            else:
                tuple_list.append((li[start_index], i - start_index))
            start_index = i
        if i == length - 1:
            if interval == -1:
                tuple_list.append((value, length - start_index))
            else:
                tuple_list.append((li[start_index], length - start_index))
        previous_value = value
    return tuple_list
