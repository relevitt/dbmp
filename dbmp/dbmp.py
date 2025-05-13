# -*- coding: utf-8 -*-

from .error import logError
from .sp_factory import spServerFactory
from .paths import CERTFILE, KEYFILE, WEBPATH, Musicpath
from .config import PORT, WS_PORT, SSL_PORT, WSS_PORT, SP_PORT
from .config import ERRLOG_TAIL_EXECUTABLE, ERRLOG_TAIL_ARGS
from .config import GOOGLE_KEY, GOOGLE_CX
from .meta import __version__
from .util import util, dbpooled, database_serialised
from .util import print_browser_connection_hint, IP
from .serialiser import Serialiser
from . import progress
from . import system
from . import album
from . import playlist
from . import spotify_cache
from . import spotify
from . import sonos
from . import db
from . import coverart
from . import qimport
from . import search
from . import db_player
from . import mpd
from . import lastfm
from twisted.internet import defer
from twisted.internet import ssl
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.websocket import WebSocketServerProtocol
from autobahn.exception import Disconnected
from twisted.internet import protocol
from twisted.web.resource import Resource
from twisted.web.static import NoRangeStaticProducer
from twisted.web.static import File
from twisted.web.server import NOT_DONE_YET
from twisted.web.server import Site
from twisted.web.client import Agent, BrowserLikeRedirectAgent, readBody
from twisted.web.http_headers import Headers
from urllib.parse import unquote
import weakref
from PIL import Image
import json
import os
import sys
import subprocess
from twisted.internet import reactor
from datetime import datetime
from .logging_setup import getLogger, setup_logging, WS_DATEFMT, LogStore

log = getLogger('dbmp.dbmp')

objects = {
    'config': 0,
    'spserverfactory': 0,
    'spfactory': 0,
    'wsfactory': 0,
    'dbpool': 0,
    'mpd': 0,
    'db_player': 0,
    'search': 0,
    'qimport': 0,
    'covers': 0,
    'util': 0,
    'sonos': 0,
    'spotify': 0,
    'spotify_cache': 0,
    'playlists': 0,
    'albums': 0,
    'system': 0,
    'database_serialiser': 0,
    'spotify_cache_serialiser': 0,
    'website': 0,
    'lastfm': 0,
    'log_store': 0,
}


class Config:
    _type_map = {
        'dbplayer_mute': int,
        'dbplayer_vol': int,
        'spotify_track_cache_last_sync': int,
        # Add more known type-casting rules here if needed
    }

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']
        self._config = {}
        self._load_d = self._load()

    def _load(self):
        """Load config from the database into memory."""

        @dbpooled
        def get_data(tx, self):
            tx.execute("SELECT key, value FROM config")
            return tx.fetchall()

        def process_data(rows):
            for key, value in rows:
                # Default to str if unknown
                caster = self._type_map.get(key, str)
                try:
                    self._config[key] = caster(value)
                except Exception:
                    self._config[key] = value

        d = get_data(self)
        d.addCallback(process_data)
        d.addErrback(logError)
        return d

    def when_ready(self):
        return self._load_d

    @database_serialised
    @dbpooled
    def _save_single(tx, self, key, value):
        """Save a single config key-value pair immediately."""
        tx.execute("""
            INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)
        """, (key, str(value)))

    def get(self, key, default=None):
        """Get a config value, or a default if missing."""
        return self._config.get(key, default)

    def set(self, key, value):
        """Set a config value in memory and immediately save to the database."""
        self._config[key] = value
        self._save_single(key, value)

    def all(self):
        """Return the full config dictionary."""
        return dict(self._config)

# Function to process any commands we receive from the website


def process(data):

    cmd = data.get('cmd', '')
    parsedcmd = cmd.split('.')
    args = data.get('args', {})
    if not cmd:
        log.warning('no command sent')
        return {}

    if len(parsedcmd) > 1 and parsedcmd[0] in objects.keys() and hasattr(objects[parsedcmd[0]], parsedcmd[1]):
        fn = getattr(objects[parsedcmd[0]], parsedcmd[1])
    else:
        log.warning('Cmd {} not recognised.  No action taken.'.format(cmd))
        return {}

    if args == {}:
        d = defer.maybeDeferred(fn)
    else:
        d = defer.maybeDeferred(fn, args)

    def error(e):
        logError(e)
        return {}

    d.addCallback(lambda res: {'results': res})
    d.addErrback(error)
    return d


class Tget_cover(Resource):
    isLeaf = True

    def render_GET(self, request):

        args = request.args
        uri_param = args.get(b'uri', [b''])[0].decode()

        if uri_param:
            # Proxy request to remote Sonos image URL
            if not IP.is_local_lan_url(uri_param):
                request.setResponseCode(400)
                request.write(b"Invalid URI")
                request.finish()
                return NOT_DONE_YET

            uri_param = unquote(uri_param)
            agent = BrowserLikeRedirectAgent(Agent(reactor))

            d = agent.request(b"GET", uri_param.encode(), Headers({}), None)

            def handle_response(response):
                return readBody(response).addCallback(lambda body: (response, body))

            def process_body(pair):
                response, body = pair
                headers = response.headers.getRawHeaders(b"Content-Type")
                if headers:
                    request.setHeader(b"Content-Type", headers[0])
                request.setHeader(b"Access-Control-Allow-Origin", b"*")
                request.setHeader(b"Content-Length",
                                  str(len(body)).encode("utf8"))
                request.write(body)
                request.finish()

            def process_error(failure):
                log.error("Cover proxy failed: %s", failure)
                request.setResponseCode(502)
                request.write(b"Failed to fetch cover from Sonos")
                request.finish()

            d.addCallback(handle_response)
            d.addCallback(process_body)
            d.addErrback(process_error)
            d.addErrback(logError)
            return NOT_DONE_YET

        uri = request.uri.decode('utf8')
        if len(uri) > 13 and uri[11] == 'd':
            d = defer.Deferred()
            d.callback(
                objects['covers'].get_coverfile(uri[13:].split('&f=')))
        elif len(uri) > 13 and uri[11] == 'i':
            d = objects['covers'].get_cover(uri[13:].split('&t=')[0])
        elif len(uri) > 13 and uri[11] == 'a':
            d = objects['covers'].get_artist(uri[13:].split('&t=')[0])
        elif len(uri) > 13 and uri[11] == 's':
            d = objects['covers'].get_playlist_cover(
                uri[13:].split('&t=')[0])
        else:
            d = defer.Deferred()
            d.callback(None)

        def process(f):
            def no_image():
                request.setResponseCode(404)
                request.write(b'Sorry, no cover available')
                request.finish()
            if not f:
                return no_image()
            try:
                im = Image.open(f)
            except:
                f.close()
                return no_image()
            form = im.format.lower()
            im = None
            request.setHeader(b"Access-Control-Allow-Origin",
                              b"*")  # <- CORS header
            request.setHeader(b'Content-type', b'image/' + form.encode('utf8'))
            try:
                fs = os.fstat(f.fileno())
                length = fs[6]
                request.setHeader(
                    b'Content-length',
                    str(length).encode('utf8'))
            except:
                f.seek(0, 2)
                length = f.tell()
                request.setHeader(
                    b'Content-length',
                    str(length).encode('utf8'))
            f.seek(0, 0)
            NoRangeStaticProducer(request, f).start()
        d.addCallback(process)
        d.addErrback(logError)
        return NOT_DONE_YET


class Tjson(Resource):
    isLeaf = True

    def connection_terminated(self, err, status):
        log.warning('HTTP connection terminated early: {}'.format(err.value))
        status['connected'] = False

    def render_POST(self, request):
        uri = request.uri.decode('utf8')
        posted = request.content.read().decode('utf8')
        data = json.loads(posted)
        log.info('{} {}'.format(uri, posted))
        d = defer.maybeDeferred(process, data)
        status = {'connected': True}
        request.notifyFinish().addErrback(self.connection_terminated, status)

        def send(result):
            if status['connected']:
                request.setHeader(b'Content-type', b'application/json')
                request.write(json.dumps(result).encode('utf8'))
                request.finish()
        d.addCallback(send)
        d.addErrback(logError)
        return NOT_DONE_YET


class Tspotify_auth(Resource):
    isLeaf = True

    def render_GET(self, request):
        uri = request.uri.decode('utf8')
        params = uri.split('?')[1].split('&')
        args = {}
        for param in params:
            p = param.split('=')
            args[p[0]] = p[1]
        d = defer.maybeDeferred(objects['spotify'].register_code, args)

        def send(result):
            request.write(result.encode('utf8'))
            request.finish()
        d.addCallback(send)
        d.addErrback(logError)
        return NOT_DONE_YET


class Tconfig_json(Resource):
    isLeaf = True

    def render_GET(self, request):
        config = {
            "ws_port": WS_PORT,
            "wss_port": WSS_PORT,
            "https_port": SSL_PORT
        }
        request.setHeader(b"Content-Type", b"application/json")
        return json.dumps(config).encode("utf8")


class WSProtocol(WebSocketServerProtocol):

    def __init__(self):
        super().__init__()
        self.requested_object = None
        self.closed = False

    def onConnect(self, request):
        log.info('WS: Connection made')

    def onClose(self, wasClean, code, reason):
        log.info('WS: Connection lost')
        self.factory.WS_remove(self)

    def onMessage(self, posted, isBinary):
        data = json.loads(posted.decode('utf8'))

        if 'pwd' in data.keys():
            log.info('WS: pwd')
        else:
            log.info('WS: {}'.format(data))

        if 'object' in data.keys():
            if not self.requested_object:
                self.factory.WS_add(self, data)
            else:
                self.factory.WS_switch(
                    self, data['object'], data.get('queueid'))
        elif 'sonos_group' in data.keys():
            self.factory.WS_sonos_group(self, data['sonos_group'])

        elif 'progress_cancel' in data.keys():
            sid = id(self)
            ticket = data['ticket']
            key = (sid, ticket)
            self.factory.cancel_object(key)

        elif 'return_result' in data.keys():
            sid = id(self)
            ticket = data['ticket']
            results = data['results']
            key = (sid, ticket)
            self.factory.WS_return_result(key, results)

        elif 'pwd' in data.keys():
            results = data['pwd']
            sid = id(self)
            key = (sid, 'get_pwd')
            self.factory.WS_return_result(key, results)


class WSFactory(WebSocketServerFactory):
    protocol = WSProtocol

    def __init__(self):
        super(WSFactory, self).__init__()
        self.websockets = weakref.WeakValueDictionary()
        self.callbacks = {}
        self.shutting_down = False
        # for some reason weakref.WeakValueDictionary doesn't work here
        self.shutdown_objects = weakref.WeakValueDictionary()

    def WS_add(self, socket, data):
        socket.requested_object = data['object']
        sid = id(socket)
        self.websockets[sid] = socket
        if data['object'] == 'dbmp':
            objects['db_player'].WS_add(sid)
        elif data['object'] == 'sonos':
            objects['sonos'].WS_add(sid, data.get('queueid'))
        # Send log history to newly connected client
        d = objects['log_store'].get_page()
        d.addCallback(lambda logs: self.WS_send(socket, {"type": "log_history",
                                                         "logs": logs}))
        d.addErrback(print)
        # Send hostname to newly connected client
        self.WS_send(socket, {"type": "hostname", "hostname": os.uname()[1]})
        self.WS_send(socket, {
                     "type": "password",
                     "password_set": not not objects['config'].get('pwd')})
        # Send Google credentials to newly connected client
        credentials = {
            "key": GOOGLE_KEY,
            "cx": GOOGLE_CX
        }
        self.WS_send(socket, {"type": "google", "google": credentials})
        self.WS_send(socket, {
                     "type": "password",
                     "password_set": not not objects['config'].get('pwd')})

    def WS_remove(self, socket):
        obj = socket.requested_object
        sid = id(socket)
        if sid in self.websockets:
            del self.websockets[sid]
        if obj == 'dbmp':
            objects['db_player'].WS_remove(sid)
        elif obj == 'sonos':
            objects['sonos'].WS_remove(sid)
        for key in self.callbacks.keys():
            if sid in key:
                self.callbacks[key].callback(None)
                del self.callbacks[key]
        for key in self.shutdown_objects.keys():
            if sid in key:
                self.shutdown_objects[key].cancel()
                del self.shutdown_objects[key]

    def WS_switch(self, socket, new_obj, queueid):
        old_obj = socket.requested_object
        socket.requested_object = new_obj
        sid = id(socket)
        if old_obj == 'dbmp':
            objects['db_player'].WS_remove(sid)
        elif old_obj == 'sonos':
            objects['sonos'].WS_remove(sid)
        if new_obj == 'dbmp':
            objects['db_player'].WS_add(sid)
        elif new_obj == 'sonos':
            objects['sonos'].WS_add(sid, queueid)

    def WS_sonos_group(self, socket, new_gid):
        sid = id(socket)
        objects['sonos'].WS_change_group(sid, new_gid)

    def WS_send(self, socket, items):
        try:
            if not socket.closed:
                socket.sendMessage(json.dumps(items).encode('utf8'), False)
        except Disconnected:
            socket.closed = True
            log.warning("WebSocket client disconnected, disabling socket.")
        except Exception as e:
            socket.closed = True
            log.exception(
                f"Error sending log to WebSocket client, disabling socket: {e}")

    def WS_send_sid(self, sid, items):
        if sid in self.websockets.keys():
            self.WS_send(self.websockets[sid], items)

    def WS_send_sids(self, sids, items):
        k = self.websockets.keys()
        for sid in sids:
            if sid in k:
                self.WS_send(self.websockets[sid], items)

    def WS_send_all(self, items):
        for sid in self.websockets.keys():
            self.WS_send(self.websockets[sid], items)

    def WS_send_sid_and_await_result(self, sid, ticket, items):
        d = defer.Deferred()
        key = (sid, ticket)
        self.callbacks[key] = d
        self.WS_send_sid(sid, items)
        return d

    def WS_return_result(self, key, results):
        if key in self.callbacks.keys():
            self.callbacks[key].callback(results)
            del self.callbacks[key]
        else:
            objects['util'].set_password(results)

    def WS_get_pwd(self, sid, wrong_pwd=False):
        d = defer.Deferred()
        key = (sid, 'get_pwd')
        items = {}
        items['type'] = 'get_pwd'
        items['wrong_pwd'] = wrong_pwd
        self.callbacks[key] = d
        self.WS_send_sid(sid, items)
        return d

    def WS_wrong_pwd(self, sid):
        return self.WS_get_pwd(sid, True)

    def shutdown(self):
        self.shutting_down = True
        for key in self.callbacks.keys():
            self.callbacks[key].callback(None)
        for key in self.shutdown_objects.keys():
            self.shutdown_objects[key].cancel()

    def register_for_shutdown(self, key, obj):
        if key not in self.shutdown_objects.keys():
            self.shutdown_objects[key] = obj

    def unregister_for_shutdown(self, key):
        if key in self.shutdown_objects.keys():
            del self.shutdown_objects[key]

    def cancel_object(self, key):
        if key in self.callbacks.keys():
            self.callbacks[key].callback(None)
            del self.callbacks[key]
        if key in self.shutdown_objects.keys():
            self.shutdown_objects[key].cancel()
            del self.shutdown_objects[key]

    def broadcast_log(self, log):
        if self.shutting_down:
            return
        message = objects['log_store'].save_log(log)
        self.WS_send_all({"type": "log", "message": message})


class tailProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, wsfactory):
        self.wsfactory = wsfactory

    def outReceived(self, data):

        txt = data.decode('utf8')
        timestamp = datetime.now().strftime(WS_DATEFMT)[:-3]
        log = {
            'source': 'stderr',
            'timestamp': timestamp,
            'level': 'stderr',
            'name': 'dbmp',
            'message': txt,
            'color': 'black',
            'level_color': 'red',
        }
        self.wsfactory.broadcast_log(log)


def main():

    objects['database_serialiser'] = Serialiser('Database Serialiser')
    objects['dbpool'] = db.dbpool()
    objects['log_store'] = LogStore(objects)
    config = Config(objects)
    objects['config'] = config

    def after_config_loaded(_):
        if not config.get("app_version"):
            config.set("app_version", __version__)
        wsfactory = WSFactory()
        objects['spserverfactory'] = spServerFactory(wsfactory)
        setup_logging(wsfactory)

        tailProcess = tailProcessProtocol(wsfactory)
        reactor.spawnProcess(
            tailProcess, ERRLOG_TAIL_EXECUTABLE, ERRLOG_TAIL_ARGS)

        spf = objects['spserverfactory'].create_subprocess(
            'dbmp_subprocess',
            'dbmp.sp_functions',
            1)
        soco_subprocess = objects['spserverfactory'].create_subprocess(
            'dbmp_soco_subprocess', 'dbmp.sonos_sp', 1)
        soco_event_notifier = objects['spserverfactory'].create_subprocess(
            'dbmp_soco_events', 'dbmp.sonos_events', 1)

        objects['spfactory'] = spf
        objects['util'] = util(objects)
        objects['wsfactory'] = wsfactory
        objects['spotify_cache_serialiser'] = Serialiser(
            'Spotify Cache Serialiser')
        objects['spotify_cache'] = spotify_cache.spotify_cache(objects)
        objects['mpd'] = mpd.mpd()
        objects['db_player'] = db_player.db_player_serialiser(objects)
        objects['search'] = search.search(objects)
        objects['qimport'] = qimport.qimport(
            objects, progress.progress(wsfactory))
        objects['covers'] = coverart.covers(objects)
        objects['sonos'] = sonos.sonos_factory(
            objects,
            soco_subprocess,
            soco_event_notifier)
        objects['spotify'] = spotify.spotify(objects)
        objects['playlists'] = playlist.playlists(objects)
        objects['albums'] = album.albums(objects)
        objects['system'] = system.system(objects)
        objects['lastfm'] = lastfm.lastfm(objects)

        root = File(str(WEBPATH))
        root.putChild(b'get_cover', Tget_cover())
        root.putChild(b'json', Tjson())
        root.putChild(b'spotify_auth', Tspotify_auth())
        root.putChild(b'config.json', Tconfig_json())

        # The Musicpath of the tree is used to serve
        # files to sonos. See create_uri in sonos_util.py
        if os.path.exists(Musicpath.defaultpath):
            root.putChild(b'music', File(str(Musicpath.defaultpath)))

        contextFactory = ssl.DefaultOpenSSLContextFactory(
            str(KEYFILE),  # Private key path
            str(CERTFILE)  # Certificate path
        )

        objects['website'] = factory = Site(root)
        reactor.listenTCP(PORT, factory)
        reactor.listenSSL(SSL_PORT, factory, contextFactory)
        reactor.listenTCP(WS_PORT, wsfactory)
        reactor.listenSSL(WSS_PORT, wsfactory, contextFactory)

        objects['spserverfactory'].start_spFactories(
            reactor.listenTCP(SP_PORT, objects['spserverfactory']))
        reactor.addSystemEventTrigger(
            'before', 'shutdown', wsfactory.shutdown)
        reactor.callLater(3, print_browser_connection_hint)

    config.when_ready().addCallback(after_config_loaded).addErrback(logError)


if __name__ == '__main__':
    reactor.callWhenRunning(main)
    reactor.run()
    if objects['system'].relaunch_requested:
        print("Relaunching application...")
        if os.path.exists("/etc/dbmp-is-rock4"):
            if "XDG_RUNTIME_DIR" not in os.environ:
                os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
            subprocess.run(
                ["systemctl", "--user", "restart", "dbmp.service"],
                check=True
            )
        else:
            os.execv(sys.executable, [sys.executable,
                     "-B", "-m", "dbmp.dbmp"] + sys.argv[1:])
