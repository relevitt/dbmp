# -*- coding: utf-8 -*-

from .paths import Musicpath
from .util import mpd_check_connected
from .util import database_serialised
from .util import dbpooled
from .util import str_to_ms
from .serialiser import Serialiser
from .error import logError
from .db_player_client import db_player_client
import os
from twisted.web.static import File
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet import task
import time
from .logging_setup import getLogger
log = getLogger(__name__)


class db_player_serialiser(object):
    def __init__(self, objects):
        self.db_player = db_player(objects)

    def __getattr__(self, prop):
        obj = getattr(self.db_player, prop)
        if hasattr(obj, '__call__'):
            def _dispatcher(*args, **kwargs):
                return self.db_player.serialise(obj, *args, **kwargs)
            _dispatcher.__name__ = prop
            setattr(self, prop, _dispatcher)
            return _dispatcher
        else:
            return obj


class db_player(db_player_client):

    '''
    Client commands forming part of db_player are set out in db_player_client.

    All client commands received via the Tjson resource (i.e. everything other
    than WS commands) are serialised by db_player_serialiser, so we don't need
    to worry about serialising them here. The only things that might need to
    be serialised here are commands initiated here (__init__ / events / loops
    / timers) or by the client via the WS system.

    Not everything initiated here needs to be serialised. The question is
    whether it might interfere with or be interfered with by some other
    operation in progress. We don't bother to serialise song progress
    notifications.

    Queues are a central concept for the db_player. Like a playlist, a queue
    is an ordered collection of tracks. A queue has two additional attributes.
    First, the db_player's position in each queue is remembered (defaults to
    the first track). Secondly, the db_player must always have one (and only
    one) queue selected as its current queue (defaults to the queue tagged as
    the system queue).
    '''

    def __init__(self, objects):
        self.lastloadtimestamp = 0
        self.loaded_positions = []
        self.mpd_status = 'stop'
        self.objects = objects
        self.mpd = objects['mpd']
        self.serialise = Serialiser('DBPlayer Serialiser').serialise
        self.dbpool = objects['dbpool']
        self.wsfactory = objects['wsfactory']
        self.websockets = []
        self.WS_LoopingCall = task.LoopingCall(self.WS_song_progress)
        self.clean_clipboard()  # This is a @database_serialised function
        self.mpd.register_db_player(
            self)  # mpd will call db_player.start(), if/when connected
        Musicpath.register(self.Musicpath_up)

    def start(self):
        self.mpd.broadcast_playback_status(self.StatusChanged)
        self.mpd.broadcast_playlist_current_pos(self.PositionChanged)
        self.mpd.broadcast_playback_volume_changed(self.WS_volume)
        self.serialise(self.reload).addErrback(logError)
        self.StatusChanged(self.mpd.last_status.get('state', 'stop'))
        self.mute(startup=True)

# Broadcast callback functions
# NB: These functions self-serialise. Don't call them
# from another function (except __init__)

    @mpd_check_connected(None)
    def StatusChanged(self, status):
        def statuschanged():
            if self.mpd_status != status:
                self.mpd_status = status
                self.WS_status()
                if status != 'stop':
                    return self.WS_song()
        self.serialise(statuschanged).addErrback(logError)

    def PositionChanged(self, *result):
        self.serialise(self.bump).addErrback(logError)

# Websocket functions

    def WS_add(self, sid):
        if sid not in self.websockets:
            self.websockets.append(sid)

        def process():
            d = self.get_status(1)

            def send(items):
                items['type'] = 'init'
                items['sid'] = sid
                self.wsfactory.WS_send_sid(sid, items)
            d.addCallback(send)
        self.serialise(process).addErrback(logError)

    def WS_remove(self, sid):
        if sid in self.websockets:
            self.websockets.remove(sid)

    def WS_send_all(self, items):
        self.wsfactory.WS_send_sids(self.websockets, items)

    def WS_queues(self, deleted_pid=None):
        items = {}
        items['type'] = 'queues'
        d = self.get_queues()

        def process(queues):
            items['queues'] = queues
            if deleted_pid != None:
                items['deleted'] = deleted_pid
            self.WS_send_all(items)
        d.addCallback(process)
        return d

    def WS_queue_contents(self, pid):
        items = {}
        items['type'] = 'queue_contents'
        d = self.get_queue_metadata(pid)

        def process(queue):
            items['queue'] = queue
            self.WS_send_all(items)
        d.addCallback(process)
        return d

    def WS_queue(self, pid):
        items = {}
        items['type'] = 'queue'
        d = self.get_queue_metadata(pid)

        def process(queue):
            items['queue'] = queue
            self.WS_send_all(items)
        d.addCallback(process)
        return d

    def WS_queue_position(self, pid, pos):
        items = {}
        items['type'] = 'queue_position'
        items['id'] = pid
        items['queue_position'] = pos
        self.WS_send_all(items)

    def WS_song(self):
        d = self.get_current_song()

        def process(results):
            song = results.get('song', {})
            duration = results.get('duration', None)
            items = {}
            items['type'] = 'song'
            items['song'] = song
            if duration:
                items['song_length'] = duration
            self.WS_send_all(items)

        d.addCallback(process)
        return d

    @mpd_check_connected(0)
    def WS_song_progress(self, zero=False):
        if not zero and self.mpd_status != 'stop':
            d = self.mpd.get_output_time()
        else:
            d = defer.Deferred()
            d.callback(0)

        def process(result):
            items = {}
            items['type'] = 'song_progress'
            items['song_progress'] = result
            self.WS_send_all(items)
        d.addCallback(process)
        d.addErrback(logError)

    def WS_status(self):
        items = {}
        items['type'] = 'status'
        items['playing'] = self.mpd_status == 'play'
        items['paused'] = self.mpd_status == 'pause'
        if self.mpd_status == 'play':
            if not self.WS_LoopingCall.running:
                self.WS_LoopingCall.start(1.0)
        else:
            if self.WS_LoopingCall.running:
                self.WS_LoopingCall.stop()
        if self.mpd_status == 'stop':
            self.WS_song_progress(True)
        self.WS_send_all(items)

    def WS_volume(self, volume):
        items = {}
        items['type'] = 'volume'
        items['volume'] = {'Master Volume': volume}
        self.WS_send_all(items)
        self.mute(set_vol=volume)

    def WS_mute(self, m):
        items = {}
        items['type'] = 'mute'
        items['mute'] = {
            'Master Volume': m
        }
        self.WS_send_all(items)

    @database_serialised
    @dbpooled
    def WS_artwork(tx, self, item_id, category, timewas=None, timeis=None):

        TIME = int(time.time())
        uriID = str(item_id) + '&t={}'

        if category == 'artist':
            query = '''SELECT artwork_update FROM artist WHERE id = ?'''
            tx.execute(query, (item_id,))
            TIME_WAS = tx.fetchone()[0] or 0
            query = '''UPDATE artist SET artwork_update = ? WHERE id = ?'''
            tx.execute(query, (TIME, item_id))
            uri = '/get_cover?a=' + uriID

        elif category == 'album':
            query = '''SELECT artwork_update FROM disc WHERE id = ?'''
            tx.execute(query, (item_id,))
            TIME_WAS = tx.fetchone()[0] or 0
            query = '''UPDATE disc SET artwork_update = ? WHERE id = ?'''
            tx.execute(query, (TIME, item_id))
            uri = '/get_cover?i=' + uriID

        elif category == 'playlist':
            TIME = timeis
            TIME_WAS = timewas
            uri = '/get_cover?s=' + uriID

        items = {}
        items['type'] = 'artwork'
        items['category'] = category
        items['item_id'] = item_id
        items['uri_was'] = uri.format(str(TIME_WAS))
        items['uri'] = uri.format(str(TIME))
        reactor.callFromThread(self.wsfactory.WS_send_all, items)

# Everything else!

# MUSIC STATUS INFO: volume, song progress, song length, playing?,
# paused?, queue pos

    def get_status(self, args={}):
        results = {}
        dlist = []
        dlist.append(self.get_queue_metadata().addErrback(
            logError))
        dlist.append(self.get_queues().addErrback(
            logError))
        d = defer.DeferredList(dlist)

        def process(res):
            queue = res[0][1]
            queues = res[1][1]
            if (args == {} and self.mpd_status == 'pause') or not self.mpd.connected:
                d = defer.Deferred()
                results['volume'] = {'Master Volume': -1}
                results['mute'] = {'Master Volume': 0}
                results['song_progress'] = -1
                results['song_length'] = -1
                results['playing'] = 0
                results['paused'] = 1
                results['queue_position'] = -1
                results['queue'] = queue
                results['queues'] = queues
                results['song'] = -1
                results['connected'] = True
                results['playing_from_queue'] = True
                if not self.mpd.connected:
                    results['connected'] = False
                d.callback(results)
                return d
            dlist = []
            dlist.append(self.mpd.status().addErrback(
                logError))
            dlist.append(self.get_current_song().addErrback(
                logError))
            dlist.append(self.mute(info_only=True).addErrback(
                logError))
            d = defer.DeferredList(dlist)

            def process(res):
                status = res[0][1]
                state = status.get('state', 'stop')
                progress = int(float(status.get('elapsed', 0)) * 1000)
                duration = res[1][1].get('duration', None)
                song = res[1][1].get('song', {})
                volume, mute = res[2][1]

                results['volume'] = {'Master Volume': volume}
                results['mute'] = {'Master Volume': mute}
                results['song_progress'] = state != 'stop' and progress
                results['song_length'] = duration
                results['playing'] = state == 'play'
                results['paused'] = state == 'pause'
                results['queue_position'] = queue.get('position',  0)
                results['queue'] = queue
                results['queues'] = queues
                results['song'] = song
                results['connected'] = True
                results['playing_from_queue'] = True
                return results

            d.addCallback(process)
            return d

        d.addCallback(process)
        return d

    def get_queue_metadata(self, pid=None):
        if pid:
            query = '''SELECT *, (SELECT COUNT(*) FROM queue_data WHERE queue_id = ?)
				AS length FROM queue_names WHERE id = ?'''
            return self.dbpool.fetchone_dict(query, (pid, pid))
        query = '''SELECT *, (SELECT COUNT(*) FROM queue_data JOIN queue_names
			ON (queue_names.id = queue_id) WHERE playing = 1)
			AS length FROM queue_names WHERE playing = 1'''
        return self.dbpool.fetchone_dict(query)

    def get_queues(self):
        query = '''SELECT name, id, locked, system FROM queue_names'''
        return self.dbpool.fetchall_dict(query)

    def get_filenames(self, pos, n=1, pid=None):
        if not pid:
            query = '''SELECT filename FROM song JOIN queue_data ON (song.id = queue_data.songid)
				JOIN queue_names ON (queue_id = queue_names.id) WHERE
				queue_names.playing = 1 AND queue_data.track_num >= ?
				AND queue_data.track_num < ? ORDER BY queue_data.track_num'''
            d = self.dbpool.fetchall_list(query, (pos, pos + n))
        else:
            query = '''SELECT filename FROM song JOIN queue_data ON (song.id = queue_data.songid)
				WHERE queue_id = ? AND queue_data.track_num >= ?
				AND queue_data.track_num < ? ORDER BY queue_data.track_num'''
            d = self.dbpool.fetchall_list(query, (pid, pos, pos + n))
        return d

    @mpd_check_connected(-1)
    def get_current_song(self):

        d = self.mpd.get_currently_playing()
        res = {}

        def process(filename):

            if filename:
                query = '''SELECT artist, disc.title AS album, song.title AS title,
						discid AS albumid, disc.artwork_update as album_art_uri,
                        play_time
						FROM song JOIN disc ON (disc.id = song.discid)
						JOIN artist ON (artist.id = song.artistid)
						WHERE filename = ?'''
                d = self.dbpool.fetchone_dict(query, (filename,))

                def process_db_result(result):
                    if not result:
                        res['song'] = {
                            'artist': '[Unknown]',
                            'album': '[Unknown]',
                            'title': filename,
                            'albumid': None,
                            'album_art_uri': None
                        }
                    else:
                        uriID = str(result['albumid']) + '&t=' + str(
                            result['album_art_uri'] or 0)
                        result['album_art_uri'] = '/get_cover?i=' + uriID
                        res['song'] = result

                    if not result or not result['play_time']:
                        return self.objects['qimport'].get_song_duration(filename)
                    else:
                        return str_to_ms(result['play_time'])

                def process_duration(duration):
                    res['duration'] = duration
                    return res

                d.addCallback(process_db_result)
                d.addCallback(process_duration)
                return d

            return {}

        d.addCallback(process)
        return d

    def set_position(self, n, pid=None):
        d = self.get_queue_metadata(pid)

        def process(queue):
            if queue['position'] == n:
                return

            @database_serialised
            @dbpooled
            def set_pos(tx, self, query, params):
                tx.execute(query, params)

            if not pid:
                query = '''UPDATE queue_names SET position = ? WHERE playing = 1'''
                d1 = set_pos(self, query, (n,))
            else:
                query = '''UPDATE queue_names SET position = ? WHERE id = ?'''
                d1 = set_pos(self, query, (n, pid))

            def after(result):
                self.WS_queue_position(queue['id'], n)
            d1.addCallback(after)
            return d1
        d.addCallback(process)
        return d

    def sanitised_pid(self, pid):
        d = self.get_queue_metadata(pid)

        def process(queue):
            if not queue['locked']:
                return queue['id']

            @dbpooled
            def get_system_pid(tx, self):
                query = '''SELECT id from queue_names WHERE system = 1'''
                tx.execute(query)
                return tx.fetchone()[0]
            return get_system_pid(self)
        d.addCallback(process)
        return d

    @mpd_check_connected(None)
    def load(self, pos, n=1):
        log.info('loading')
        var = {}
        var['counter'] = 0
        var['errors'] = 0

        def load(rows):

            def loadit(filename):
                d = check(filename)

                def process1(result):
                    if result == 'FAILURE':
                        return add_another()
                    elif result == 'SUCCESS':
                        self.loaded_positions.append(pos + var['counter'])
                        return self.mpd.playlist_add_file(filename)
                    elif result == 'MISSING':
                        while len(rows):
                            rows.pop()

                def process2(result):
                    if rows:
                        var['counter'] += 1
                        return loadit(rows.pop(0))

                d.addCallback(process1)
                d.addCallback(process2)
                return d

            def add_another():
                d = self.get_filenames(pos + n + var['errors'], 1)

                def process(filenames):
                    if filenames:
                        rows.append(filenames[0])
                        var['errors'] += 1
                    else:
                        if not len(rows):
                            log.info(
                                'Reached end of queue. Nothing more to load.')
                d.addCallback(process)
                return d

            if rows:
                return loadit(rows.pop(0))

        def check(filename):
            if os.path.exists(filename):
                return check_medialib(filename)
            if not Musicpath.get_path() and os.path.commonprefix([Musicpath.defaultpath, filename]) == Musicpath.defaultpath:
                result = 'MISSING'
            elif not os.path.exists(os.path.dirname(filename)):
                log.warning(
                    '%s not found ... skipping to next file',
                    os.path.dirname(filename))
                result = 'FAILURE'
            else:
                log.warning('%s not found ... skipping to next file', filename)
                result = 'FAILURE'
            d = defer.Deferred()
            d.callback(result)
            return d

        def check_medialib(filename):
            d = self.mpd.medialib_get_info(filename)

            def process(result):
                if not result:
                    return self.mpd.medialib_add_entry(filename).addCallback(
                        lambda _: self.mpd.medialib_get_info(filename)
                    ).addCallback(check_after_adding)
                else:
                    return 'SUCCESS'

            def check_after_adding(result):
                if not result:
                    log.warning(
                        'Unable to add {} to mpd databse'.format(filename))
                    return 'FAILURE'
                else:
                    log.info('{} added to mpd database'.format(filename))
                    return 'SUCCESS'

            d.addCallback(process)
            d.addErrback(lambda err: 'FAILURE')
            return d

        d = self.get_filenames(pos, n)
        d.addCallback(load)
        return d

    @mpd_check_connected(None)
    def reload(self, pos=-1, play=False, keep_state=True):
        log.info('reloading')
        var = {
            'pos': pos,
            'play': play,
            'WS_song': True
        }
        self.loaded_positions = []
        d = self.get_queue_metadata()

        def process(queue):
            # Queue empty - cleanup and return
            if not queue['length']:
                return self.mpd.stop().addCallback(
                    lambda _: self.mpd.playlist_clear()).addCallback(
                        lambda _: self.set_position(-1)).addCallback(
                            lambda _: self.WS_song())

            # Queue has content - get relevant info
            d = self.mpd.command_list([
                ('status',),
                ('currentsong',)
            ])

            def process1(results):
                if isinstance(results, list):
                    results = results[0]
                # Populate variables
                mpd_state = results.get(
                    'state', 'stop')
                mpd_loaded_file = results.get('file', None)
                mpd_pos = int(results.get('song', 0))
                mpd_playlist_length = int(results.get('playlistlength', 0))

                if keep_state:
                    var['play'] = mpd_state == 'play'
                if var['pos'] < 0:
                    var['pos'] = queue['position']
                if var['pos'] < 0:
                    var['pos'] = 0
                self.lastloadtimestamp = time.time()
                d = self.get_filenames(var['pos'])

                def process(filenames):
                    # If the correct song is loaded, we'll clear around it
                    if mpd_loaded_file == filenames[0]:
                        if mpd_state != 'stop':
                            var['WS_song'] = False

                        # If the mpd playlist has files after the correct
                        # song being played
                        if mpd_pos < (mpd_playlist_length - 1):
                            d = self.mpd.playlist_remove_entry(
                                mpd_pos + 1, 'END')
                            if mpd_pos > 0:
                                d.addCallback(
                                    lambda _: self.mpd.playlist_remove_entry(
                                        0, mpd_pos))
                        # Else if mpd playlist has files before the
                        # correct sonf being played
                        elif mpd_pos > 0:
                            d = self.mpd.playlist_remove_entry(
                                0, mpd_pos)

                        # Else there's nothing to clear
                        else:
                            d = defer.Deferred()
                            d.callback(None)

                        def loadit(result):
                            if var['play'] and mpd_state != 'play':
                                self.mpd.play()
                            self.loaded_positions = [var['pos']]
                            return self.load(var['pos'] + 1)

                        d.addCallback(loadit)
                        return d

                    # Otherwise, we'll clear the mpd playlist before loading
                    d = self.mpd.stop()

                    def clear(result):
                        return self.mpd.playlist_clear()

                    def load(result):
                        return self.load(var['pos'], 2)

                    def check(result):
                        if len(self.loaded_positions):
                            if var['pos'] not in self.loaded_positions:
                                var['pos'] = self.loaded_positions[0]
                            d = self.mpd.set_queue_pos(0)

                            def play(result):
                                if var['play']:
                                    return self.mpd.play()
                            d.addCallback(play)
                            return d
                    d.addCallback(clear)
                    d.addCallback(load)
                    d.addCallback(check)
                    return d
                d.addCallback(process)
                return d

            def process2(result):
                return self.set_position(var['pos'])

            def process3(result):
                if var['WS_song']:
                    return self.WS_song()
            d.addCallback(process1)
            d.addCallback(process2)
            d.addCallback(process3)
            return d
        d.addCallback(process)
        return d

    @mpd_check_connected(None)
    def bump(self):

        d = self.get_queue_metadata()

        def bump(queue):
            length = queue['length']
            if not length:
                return
            if not self.loaded_positions:
                return
            var = {
                'pos': None,
                'current_pos': None,
                'mpd_pos': None,
                'mpd_length': None
            }
            d = self.mpd.status()

            def process(result):
                var['mpd_pos'] = int(result.get('song', 0))
                var['mpd_length'] = int(result.get('playlistlength', 0))
                var['pos'] = self.loaded_positions[var['mpd_pos']]
                timestamp = time.time()
                difference = timestamp - self.lastloadtimestamp
                self.lastloadtimestamp = timestamp
                if var['pos'] == queue['position']:
                    if var['pos'] == length - 1 and var['pos'] > 0 and var['mpd_length'] == 1 and difference > 2:
                        return self.reload(0, keep_state=False)
                    return

                def prune_end():
                    excess = var['mpd_length'] - (var['mpd_pos'] + 1)
                    if excess:
                        d = self.mpd.playlist_remove_entry(
                            '{}:'.format(var['mpd_pos'] + 1))
                    else:
                        d = defer.Deferred()
                        d.callback(None)
                    try:
                        for n in range(excess):
                            self.loaded_positions.pop()
                    except:
                        log.exception(
                            'in bump(), mpd_length was longer than self.loaded_positions')
                    return d

                def load_next(result):
                    queue_space = (length - 1) - var['pos']
                    if queue_space:
                        return self.load(var['pos'] + 1)

                def prune_start(result):
                    if var['mpd_pos']:
                        d = self.mpd.playlist_remove_entry(
                            '0:{}'.format(var['mpd_pos']))
                    else:
                        d = defer.Deferred()
                        d.callback(None)
                    for n in range(var['mpd_pos']):
                        self.loaded_positions.pop(0)
                    return d

                d = prune_end()
                d.addCallback(load_next)
                d.addCallback(prune_start)
                d.addCallback(lambda _: self.set_position(var['pos']))
                d.addCallback(lambda _: self.WS_song())
                return d

            d.addCallback(process)
            return d

        d.addCallback(bump)
        return d

    def Musicpath_up(self):
        self.serialise(self.reload).addErrback(logError)
        if 'music' not in self.objects['website'].resource.listStaticNames():
            self.objects['website'].resource.putChild(
                'music', File(Musicpath.path))

    # Should a recurring task be scheduled?
    # Should we notify anything through WS?

    @database_serialised
    @dbpooled
    def clean_clipboard(tx, self):
        yesterday = int(time.time()) - 86400  # 24 hours
        query = '''DELETE FROM clipboard_data WHERE clientid IN (SELECT clientid FROM clipboard_access WHERE time < ?)'''
        tx.execute(query, (yesterday,))
        query = '''DELETE FROM clipboard_access WHERE time < ?'''
        tx.execute(query, (yesterday,))

    # These next two functions are required and used by
    # the @snapshot decorator

    @dbpooled
    def check_snapshot_id(tx, self, container_id, snapshot_id):
        query = ''' SELECT snapshot_id
                    FROM queue_names
                    WHERE id = ?'''
        tx.execute(query, (container_id,))
        db_snapshot_id = tx.fetchone()[0]
        if db_snapshot_id == snapshot_id:
            return True, {}
        else:
            res = {}
            res['snapshot_id'] = db_snapshot_id
            res['status'] = 'WRONG_SNAPSHOT_ID'
            return False, res

    @dbpooled
    def update_snapshot_id(tx, self, args):
        if isinstance(args, tuple):
            qid, res = args
        else:
            qid, res = args, {}
        if not qid:
            res['status'] = 'ERROR'
            return res
        snapshot_id = int(time.time() * 1000)
        query = ''' UPDATE queue_names
                    SET snapshot_id = ?
                    WHERE id = ?'''
        tx.execute(query, (snapshot_id, qid))
        res['status'] = 'SUCCESS'
        res['snapshot_id'] = snapshot_id
        return res
