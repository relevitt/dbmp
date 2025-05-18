# -*- coding: utf-8 -*-

from .util import snapshot
from .util import dbpooled
from .util import spotify_cache_serialised
from .util import serialised, database_serialised
from .serialiser import Serialiser
from .error import logError
import weakref
import time
from twisted.internet import defer
from .logging_setup import getLogger
log = getLogger(__name__)


def create_album_art_uri(discid, timestamp):
    '''
    Returns an album art uri in the form recognised
    by the '/get_cover' cmd to the server.
    '''
    return '/get_cover?i={}&t={}'.format(discid, timestamp or 0)


# At first I wanted to keep data in playlist_data nicely grouped by pid.
# This is no longer the objective, but sections of the code in this module
# will reflect the first approach.


class playlists(object):

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']
        self.serialise = Serialiser('Playlist Serialiser').serialise
        self.startup_artwork_check()

    @serialised
    @database_serialised
    def startup_artwork_check(self):

        @dbpooled
        def get_playlist_ids(tx, self):
            query = '''	SELECT id AS pid FROM playlist_names
						ORDER BY id'''
            tx.execute(query)
            return tx.fetchall()

        def process_results(rows):

            data = {'pid': None}

            def check_cover_exists(result):
                if not result:
                    return self.update_snapshot_id(data['pid'], True)

            def process_row(pid):
                data['pid'] = pid
                d = self.objects['covers'].get_playlist_cover(pid)
                d.addCallback(check_cover_exists)
                d.addCallback(after)
                return d

            def after(result):
                if len(rows):
                    return process_row(str(rows.pop()['pid']))
            return after(None)

        d = get_playlist_ids(self)
        d.addCallback(process_results)
        return d

    @serialised
    @database_serialised
    def add_sonos_queue_to_playlist(self, args):
        # NB We could (but we do not currently) check that the correct snapshot_id
        # was supplied

        def add_queue(conn):

            def track_num_gen():
                counter = 0
                while True:
                    yield next_track_num + counter
                    counter += 1

            gen = track_num_gen()
            w_gen = weakref.ref(gen)

            def get_type(track_id):
                if 'spotify' in track_id:
                    return 's'
                else:
                    try:
                        int(track_id)
                        return 'd'
                    except ValueError:
                        return 'x'

            conn.create_function(
                'GET_NEXT_TRACK_NUM',
                0,
                lambda: next(w_gen()))
            conn.create_function('GET_TYPE', 1, get_type)
            tx = conn.cursor()

            pid, next_track_num = self.get_pid_and_next_track_num(tx, args)
            if not pid:
                return

            if 'indices' in args.keys():
                stub = '''AND track_num IN (''' + \
                    ",".join("?" * len(args['indices'])) + ''')'''
                params = tuple([pid, args['sonos_uid']] + args['indices'])
            else:
                stub = ''
                params = (pid, args['sonos_uid'])

            query = '''	INSERT INTO playlist_data (playlistid, songid, track_num, type)
						SELECT ?,
                        id,
                        GET_NEXT_TRACK_NUM(),
                        GET_TYPE(id)
						FROM (SELECT id FROM sonos_queue_data
						WHERE sonos_queue_data.groupid = ?
                        AND GET_TYPE(id) != "x"
                        {}
						ORDER BY track_num)'''.format(stub)

            tx.execute(query, params)
            return pid

        d = self.dbpool.runWithConnection(add_queue)
        d.addCallback(self.update_snapshot_id)
        return d

    def search_playlists(self, args):

        res = {}
        res['startIndex'] = args['startIndex']

        @dbpooled
        def get_playlists(tx, self):
            query = '''SELECT COUNT(*) FROM playlist_names'''
            tx.execute(query)
            res['totalRecords'] = tx.fetchone()[0]
            query = '''	SELECT name AS title, id AS itemid FROM playlist_names
						ORDER BY id'''
            tx.execute(query)
            return tx.fetchall()

        def process_results(rows):
            if args['startIndex'] > len(rows):
                return
            res['results'] = [
                dict(p) for p in rows[
                    args['startIndex']:args['startIndex'] + args['rowsPerPage']
                ]
            ]
            albumArtURI = '''/get_cover?s={}&t={}'''
            for n, timestamp in enumerate(
                    self.objects['covers'].get_playlist_cover_timestamps(
                        [str(p['itemid']) for p in res['results']]
                    )):
                res['results'][n]['artURI'] = albumArtURI.format(
                    res['results'][n]['itemid'], timestamp)
            return res

        d = get_playlists(self)
        d.addCallback(process_results)
        return d

    @spotify_cache_serialised
    def search_songs_from_playlistid(self, args):

        res = {}
        res['startIndex'] = args['startIndex']
        res['id'] = args['id']
        res['metadata'] = {
            'item_type': 'playlist',
            'editable': True,
            'artist': None,
            'artistid': None,
            'artistArtURI': 'icons/ArtistNoImage.png',
            'snapshot_id': None
        }
        res['results'] = []

        def get_items(conn):

            conn.create_function('GET_ARTWORK_URI', 2, create_album_art_uri)
            tx = conn.cursor()

            query = '''SELECT COUNT(*) FROM playlist_data WHERE playlistid = ?'''
            tx.execute(query, (args['id'],))
            res['totalRecords'] = tx.fetchone()[0]
            if res['totalRecords'] <= args['startIndex']:
                return res

            query = '''SELECT snapshot_id FROM playlist_names WHERE id = ?'''
            tx.execute(query, (args['id'],))
            res['metadata']['snapshot_id'] = tx.fetchone()[0]

            query = '''	SELECT spotify_track_cache.song AS title,
						spotify_track_cache.songid AS itemid,
						spotify_track_cache.artist,
						spotify_track_cache.artistid,
						spotify_track_cache.album,
						spotify_track_cache.albumid,
						spotify_track_cache.artURI,
						playlist_data.type, playlist_data.track_num
						FROM playlist_data
						JOIN spotify_track_cache
						ON (playlist_data.songid = spotify_track_cache.songid)
						WHERE playlistid = ?1
						AND type = 's'
						AND track_num >= ?2
						AND track_num < ?3

						UNION ALL

						SELECT song.title,
						song.id AS itemid,
						artist.artist,
						artist.id AS artistid,
						disc.title AS album,
						disc.id AS albumid,
						GET_ARTWORK_URI(disc.id, disc.artwork_update) AS artURI,
						playlist_data.type, playlist_data.track_num
						FROM playlist_data
						JOIN song ON (playlist_data.songid = song.id)
						JOIN disc ON (song.discid = disc.id)
						JOIN artist ON (song.artistid = artist.id)
						WHERE playlistid = ?1
						AND type = 'd'
						AND playlist_data.track_num >= ?2
						AND playlist_data.track_num < ?3

						ORDER BY track_num'''

            tx.execute(
                query,
                (args['id'],
                 args['startIndex'],
                    args['startIndex'] + args['rowsPerPage']))
            rows = tx.fetchall()
            res['results'] = [dict(row) for row in rows]
            return res

        return self.dbpool.runWithConnection(get_items)

    @serialised
    @database_serialised
    def clear_playlist(self, args):

        @dbpooled
        def clear(tx, self):
            query = '''DELETE FROM playlist_data WHERE playlistid = ?'''
            tx.execute(query, (args['container_id'],))
            return args['container_id']

        d = clear(self)
        d.addCallback(self.update_snapshot_id)
        return d

    @serialised
    @database_serialised
    def delete_tracks_from_container(self, args):

        @snapshot
        @dbpooled
        def delete_tracks(tx, self, args):
            query = '''	CREATE TEMP TABLE tmp_data
						(pos INTEGER PRIMARY KEY ASC, songid INTEGER, type TEXT)'''
            tx.execute(query)
            query = '''	INSERT INTO tmp_data (songid, type) SELECT songid, type FROM playlist_data
						WHERE playlistid = ? AND track_num NOT IN (''' + ",".join("?" * len(args['tracks'])) + ''')
						ORDER BY track_num
						'''
            parameters = tuple([args['container_id']] + args['tracks'])
            tx.execute(query, parameters)
            query = '''DELETE FROM playlist_data WHERE playlistid = ?'''
            tx.execute(query, (args['container_id'],))
            query = '''	INSERT INTO playlist_data (playlistid, songid, type, track_num)
						SELECT ?, songid, type, pos-1 FROM tmp_data'''
            tx.execute(query, (args['container_id'],))
            query = '''DROP TABLE tmp_data'''
            tx.execute(query)
            return args['container_id']

        return delete_tracks(self, args)

    # Called from album.py, so not further serialised here
    @serialised
    def _delete_songids(self, songids):

        args = [
            {'id': 'playlistid',
             'table': 'playlist_data'
             },
            {'id': 'clientid',
             'table': 'clipboard_data'
             }]

        def process_next_arg(result=None):

            if not len(args):
                return

            arg = args.pop(0)

            @dbpooled
            def get_container_ids(tx, self):
                query = '''	SELECT DISTINCT ''' + arg['id'] + ''' FROM ''' + arg['table'] + '''
							WHERE songid IN (''' + ",".join("?" * len(songids)) + ''')'''
                parameters = tuple(songids)
                tx.execute(query, parameters)
                pids = [p[0] for p in tx.fetchall()]
                return pids

            def process_container_ids(pids):

                def process_next_pid(result=None):

                    if not len(pids):
                        return

                    d = process_container_pid(self, pids.pop(0))
                    if arg['id'] == 'playlistid':
                        d.addCallback(self.update_snapshot_id)
                    d.addCallback(process_next_pid)
                    return d

                @dbpooled
                def process_container_pid(tx, self, pid):
                    query = '''	CREATE TEMP TABLE tmp_data
						 		(pos INTEGER PRIMARY KEY ASC, songid INTEGER, type TEXT)'''
                    tx.execute(query)
                    query = '''	INSERT INTO tmp_data (songid, type) SELECT songid, type FROM ''' + arg['table'] + '''
								WHERE ''' + arg['id'] + ''' = ? AND songid NOT IN (''' + ",".join("?" * len(songids)) + ''')
								ORDER BY track_num'''
                    parameters = tuple([pid] + songids)
                    tx.execute(query, parameters)
                    query = '''	DELETE FROM ''' + \
                        arg['table'] + ''' WHERE ''' + arg['id'] + ''' = ?'''
                    tx.execute(query, (pid,))
                    query = '''	INSERT INTO ''' + arg['table'] + ''' (''' + arg['id'] + ''', songid, type, track_num)
							 	SELECT ?, songid, type, pos-1 FROM tmp_data'''
                    tx.execute(query, (pid,))
                    query = '''	DROP TABLE tmp_data'''
                    tx.execute(query)
                    return pid

                return process_next_pid()

            d = get_container_ids(self)
            d.addCallback(process_container_ids)
            d.addCallback(process_next_arg)
            return d

        return process_next_arg()

    @serialised
    @database_serialised
    def move_tracks_in_container(self, args):

        @snapshot
        @dbpooled
        def move_tracks(tx, self, args):
            first = args['move'][0]
            last = args['move'][1]
            dest = args['move'][2]
            indices = list(range(first, first + last))
            query = '''	CREATE TEMP TABLE tmp_data
						(pos INTEGER PRIMARY KEY ASC, songid INTEGER, type TEXT)'''
            tx.execute(query)
            query = '''	SELECT songid, type FROM playlist_data
						WHERE playlistid = ? AND track_num IN (''' + ",".join("?" * len(indices)) + ''')
						ORDER BY track_num'''
            parameters = tuple([args['container_id']] + indices)
            tx.execute(query, parameters)
            tracks = [(row[0], row[1]) for row in tx.fetchall()]
            query = '''	DELETE FROM playlist_data
						WHERE playlistid = ? AND track_num IN (''' + ",".join("?" * len(indices)) + ''')'''
            parameters = tuple([args['container_id']] + indices)
            tx.execute(query, parameters)
            query = '''	INSERT INTO tmp_data (songid, type) SELECT songid, type FROM playlist_data
						WHERE playlistid = ? AND track_num < ?
						ORDER BY track_num'''
            tx.execute(query, (args['container_id'], dest))
            query = '''	INSERT INTO tmp_data (songid, type) VALUES(?,?)	'''
            tx.executemany(query, tracks)
            query = '''	INSERT INTO tmp_data (songid, type) SELECT songid, type FROM playlist_data
						WHERE playlistid = ? AND track_num >= ?
						ORDER BY track_num'''
            tx.execute(query, (args['container_id'], dest))
            query = '''DELETE FROM playlist_data WHERE playlistid = ?'''
            tx.execute(query, (args['container_id'],))
            query = '''	INSERT INTO playlist_data (playlistid, songid, type, track_num)
						SELECT ?, songid, type, pos-1 FROM tmp_data'''
            tx.execute(query, (args['container_id'],))
            query = '''DROP TABLE tmp_data'''
            tx.execute(query)
            return args['container_id']

        return move_tracks(self, args)

    @database_serialised
    @dbpooled
    def copy_to_clipboard(tx, self, args):
        query = '''DELETE FROM clipboard_data WHERE clientid = ?'''
        tx.execute(query, (args['client_id'],))
        query = '''	INSERT INTO clipboard_data (clientid, songid, type, track_num)
			 		SELECT ?, songid, type, ? FROM playlist_data
					WHERE playlistid = ? AND track_num = ?'''
        for n, index in enumerate(args['indices']):
            tx.execute(
                query,
                (args['client_id'],
                 n,
                 args['container_id'],
                    index))
        self.objects['db_player'].update_clipboard_access(
            tx, args['client_id'])

    @serialised
    @database_serialised
    def paste_from_clipboard(self, args):

        @snapshot
        @dbpooled
        def paste_tracks(tx, self, args):
            query = '''	SELECT COUNT(*) FROM clipboard_data
						WHERE clientid = ?'''
            tx.execute(query, (args['client_id'],))
            num = tx.fetchone()[0]
            if not num:
                res = {}
                res['status'] = 'SUCCESS'
                res['snapshot_id'] = args['snapshot_id']
                return res
            query = '''	CREATE TEMP TABLE tmp_data
						(pos INTEGER PRIMARY KEY ASC, songid INTEGER, type TEXT)'''
            tx.execute(query)
            query = '''	INSERT INTO tmp_data (songid, type) SELECT songid, type FROM playlist_data
						WHERE playlistid = ? AND track_num < ? ORDER BY track_num'''
            tx.execute(query, (args['container_id'], args['dest']))
            query = '''	INSERT INTO tmp_data (songid, type) SELECT songid, type FROM clipboard_data
				 		WHERE clientid = ? ORDER BY track_num'''
            tx.execute(query, (args['client_id'],))
            query = '''	INSERT INTO tmp_data (songid, type) SELECT songid, type FROM playlist_data
				 		WHERE playlistid = ? AND track_num >= ? ORDER BY track_num'''
            tx.execute(query, (args['container_id'], args['dest']))
            query = '''DELETE FROM playlist_data WHERE playlistid = ?'''
            tx.execute(query, (args['container_id'],))
            query = '''	INSERT INTO playlist_data (playlistid, songid, type, track_num)
						SELECT ?, songid, type, pos-1 FROM tmp_data'''
            tx.execute(query, (args['container_id'],))
            query = '''DROP TABLE tmp_data'''
            tx.execute(query)
            return args['container_id']

        return paste_tracks(self, args)

    @serialised
    @database_serialised
    def playlist_shuffle(self, args):

        @dbpooled
        def shuffle(tx, self):
            query = '''CREATE TEMP TABLE tmp_data
					(pos INTEGER PRIMARY KEY ASC, songid TEXT, type, TEXT)'''
            tx.execute(query)
            query = '''INSERT INTO tmp_data (songid, type) SELECT songid, type FROM playlist_data
				WHERE playlistid = ? ORDER BY RANDOM()'''
            tx.execute(query, (args['container_id'],))
            query = '''DELETE FROM playlist_data WHERE playlistid = ?'''
            tx.execute(query, (args['container_id'],))
            query = '''INSERT INTO playlist_data (playlistid, songid, type, track_num)
				SELECT ?, songid, type, pos-1 FROM tmp_data ORDER BY pos'''
            tx.execute(query, (args['container_id'],))
            query = '''DROP TABLE tmp_data'''
            tx.execute(query)
            return args['container_id']

        d = shuffle(self)
        d.addCallback(self.update_snapshot_id)
        return d

    @serialised
    @database_serialised
    @dbpooled
    def rename_container(tx, self, args):
        query = '''UPDATE playlist_names SET name = ? WHERE id = ?'''
        tx.execute(query, (args['name'], args['container_id']))
        return args['name']

    @serialised
    @database_serialised
    def delete_container(self, args):

        @dbpooled
        def playlist_delete(tx, self):
            query = '''DELETE FROM playlist_data WHERE playlistid = ?'''
            tx.execute(query, (args['container_id'],))
            query = '''DELETE FROM playlist_names WHERE id = ?'''
            tx.execute(query, (args['container_id'],))

        def cover(dummy):
            self.objects['covers'].delete_cover(
                'playlist', args['container_id'])

        d = playlist_delete(self)
        d.addCallback(cover)
        return d

    @serialised
    @defer.inlineCallbacks
    def add_to_playlist(self, args):

        var = {}
        var['counter'] = 0
        var['pid'] = None

        def add(tracks=None):
            @database_serialised
            def process(self):
                return self.dbpool.runWithConnection(add_to_db, tracks)
            return process(self)

        def update_snapshot_id(pid):
            @database_serialised
            def update(self):
                return self.update_snapshot_id(pid)
            return update(self)

        def add_to_db(conn, tracks):

            def track_num_gen():
                while True:
                    yield var['counter']
                    var['counter'] += 1

            gen = track_num_gen()
            w_gen = weakref.ref(gen)
            conn.create_function(
                'GET_NEXT_TRACK_NUM',
                0,
                lambda: next(w_gen()))

            tx = conn.cursor()

            if var['counter'] == 0:
                pid, next_track_num = self.get_pid_and_next_track_num(tx, args)
                if not pid:
                    return
                else:
                    var['pid'] = pid
                    var['counter'] = next_track_num
            else:
                if not var['pid']:
                    return
                # If we got here it means we're processing the next
                # batch of rows so we increment the counter,
                # otherwise we will duplicate the previous track_num
                var['counter'] += 1

            if tracks:
                query = '''	INSERT INTO playlist_data (playlistid, songid,
							track_num, type)
							VALUES (?, ?, GET_NEXT_TRACK_NUM(), 's')'''
                tx.executemany(query, [(var['pid'], t) for t in tracks])

            else:

                if 'indices' in args.keys():
                    subquery = '''AND track_num IN (''' + ",".join(
                        "?" * len(args['indices'])) + ''')'''
                else:
                    subquery = ''

                if args['data_type'] == 'queue':
                    select = '''SELECT ?,
                                songid,
                                GET_NEXT_TRACK_NUM(),
                                "d"
								FROM (SELECT songid FROM queue_data
                                WHERE queue_id = ?'''
                elif args['data_type'] == 'playlist':
                    select = '''SELECT ?,
                                songid,
                                GET_NEXT_TRACK_NUM(),
                                type
								FROM (SELECT songid, type FROM playlist_data
                                WHERE playlistid = ?'''
                elif args['data_type'] == 'album':
                    select = '''SELECT ?,
                                id,
                                GET_NEXT_TRACK_NUM(),
                                "d"
								FROM (SELECT id FROM song
                                WHERE discid = ?'''

                query = '''	INSERT INTO playlist_data
							(playlistid, songid, track_num, type)
							{} {}
							ORDER BY track_num)'''.format(select, subquery)
                params = [var['pid'], args['container_id']]
                params += args['indices'] if 'indices' in args.keys() else []
                tx.execute(query, tuple(params))
            return var['pid']

        if args['data_source'] == 'spotify':
            if 'tracks' in args.keys():
                results = yield self.objects['spotify_cache'].get_track_data(
                    args['tracks'], args['client_id'], fulldata=False)
                pid = yield add(results)
            else:
                fn_args = args
                while True:
                    result = yield self.objects['spotify'].get_container_tracks(
                        fn_args)
                    if result.get('tracks'):
                        pid = yield add(result['tracks'])
                    if result.get('var'):
                        fn_args = {'var': result['var']}
                    else:
                        break
        else:
            pid = yield add()

        snapshot_id = yield update_snapshot_id(pid)
        return snapshot_id

    @defer.inlineCallbacks
    def get_spotify_tracks(self, args):

        # This method returns up to 100 tracks at a time.
        # If there are more tracks available, the dict it
        # returns will include the key 'var' with the variables
        # it will need to return the next batch of tracks. This
        # method should then be called with args['var] set to
        # the value of the 'var' key it returned. The calling
        # method can use this method to generate results as follows
        # (where get_fn has been set to refer to this method):
        #
        # fn_args = args
        # while True:
        #     result = get_fn(fn_args)
        #     if result.get('tracks'):
        #         outcome = yield process(result['tracks'])
        #     if result.get('var'):
        #         fn_args = {'var': result['var']}
        #     else:
        #         break
        #
        # The code above assumes that the calling method has
        # also been decorated to be an inlineCallback, so that
        # yield can be used to await the result of the deferred
        # returned by this method

        if args.get('var'):
            args = args['var']
        if not args.get('start'):
            args['start'] = 0
        if not args.get('length'):
            args['length'] = 0
        start = args['start']

        def get_from_db(conn):
            subquery = ''
            if 'indices' in args.keys():
                def in_range(track_num):
                    if track_num in args['indices']:
                        return 1
                    else:
                        return 0
                w_in_range = weakref.ref(in_range)
                conn.create_function(
                    'IN_RANGE',
                    1,
                    lambda index: w_in_range()(index))
                subquery = '''AND IN_RANGE(track_num)'''
            tx = conn.cursor()
            if not args['length']:
                query = '''	SELECT COUNT(*) FROM playlist_data
                            WHERE playlistid = ?
                            AND type = "s"'''
                tx.execute(query, (args['container_id'],))
                args['length'] = tx.fetchone()[0]
                if not args['length']:
                    return []
            query = '''	SELECT songid, track_num FROM playlist_data
                        WHERE playlistid = ?
                        AND track_num >= ? {}
                        AND type = 's'
                        ORDER BY track_num LIMIT 100'''.format(subquery)
            tx.execute(query, (args['container_id'], start))
            rows = tx.fetchall()
            if not rows:
                args['length'] = args['start']  # this will stop iteration
                return []
            else:
                args['start'] = rows[-1]['track_num'] + 1
            return [row['songid'] for row in rows]

        tracks = yield self.dbpool.runWithConnection(get_from_db)
        result = {'tracks': tracks}
        if args['start'] < args['length']:
            result['var'] = args
        return result

    def get_pid_and_next_track_num(self, tx, args):
        '''Call this function from within an @dbpooled function'''
        if 'name' in args.keys():
            try:
                query = '''INSERT INTO playlist_names (name) VALUES (?)'''
                tx.execute(query, (args['name'],))
                query = '''SELECT id FROM playlist_names WHERE name = ?'''
                tx.execute(query, (args['name'],))
                pid = tx.fetchone()[0]
            except:
                log.exception('problem in get_pid_and_next_track_num')
                return 0, 0
        else:
            pid = args['dest_id']

        if args['clear']:
            query = '''DELETE FROM playlist_data where playlistid = ?'''
            tx.execute(query, (pid,))

        query = '''SELECT COUNT(*) FROM playlist_data WHERE playlistid = ?'''
        tx.execute(query, (pid,))
        return pid, tx.fetchone()[0]

    def get_playlist_artwork_uris(self, pid):

        def get_items(conn):

            conn.create_function('GET_ARTWORK_URI', 2, create_album_art_uri)
            tx = conn.cursor()

            query = '''	SELECT DISTINCT artURI
						FROM

						(SELECT spotify_track_cache.artURI,
						playlist_data.track_num
						FROM playlist_data
						JOIN spotify_track_cache
						ON (playlist_data.songid = spotify_track_cache.songid)
						WHERE playlistid = ?1
						AND type = 's'

						UNION

						SELECT GET_ARTWORK_URI(disc.id, disc.artwork_update) AS artURI,
						playlist_data.track_num
						FROM playlist_data
						JOIN song ON (playlist_data.songid = song.id)
						JOIN disc ON (song.discid = disc.id)
						WHERE playlistid = ?1
						AND type = 'd'

						ORDER BY track_num)

						LIMIT 4'''

            tx.execute(query, (pid,))
            rows = tx.fetchall()
            return [row[0] for row in rows]

        return self.dbpool.runWithConnection(get_items)

    # These next two functions are required and used by
    # the @snapshot decorator

    @dbpooled
    def check_snapshot_id(tx, self, pid, snapshot_id):
        query = '''SELECT snapshot_id FROM playlist_names WHERE id = ?'''
        tx.execute(query, (pid,))
        db_snapshot_id = tx.fetchone()[0]
        if db_snapshot_id == snapshot_id:
            return True, {}
        else:
            res = {}
            res['snapshot_id'] = db_snapshot_id
            res['status'] = 'WRONG_SNAPSHOT_ID'
            return False, res

    # database_serialised by the calling function
    def update_snapshot_id(self, pid, artwork_only=False):

        if not pid:
            return

        def update(result):

            @dbpooled
            def update_db(tx, self):
                snapshot_id = int(time.time() * 1000)
                query = '''UPDATE playlist_names SET snapshot_id = ? WHERE id = ?'''
                tx.execute(query, (snapshot_id, pid))
                res = {}
                res['status'] = 'SUCCESS'
                res['snapshot_id'] = snapshot_id
                return res

            return update_db(self)

        def update_cover(uris):

            @dbpooled
            def uris_match_db(tx, self):
                query = '''SELECT artwork_uris FROM playlist_names WHERE id = ?'''
                tx.execute(query, (pid,))
                new_uris = '{' + '}{'.join(uris) + '}'
                old_uris = tx.fetchone()[0]
                if new_uris == old_uris:
                    return True
                else:
                    query = '''UPDATE playlist_names SET artwork_uris = ? WHERE id = ?'''
                    tx.execute(query, (new_uris, pid))
                    return False

            def after(matched):
                if not matched or artwork_only:
                    # update_playlist_cover is serialised separately
                    # We dont return this, so that updating cover continues in the
                    # background
                    self.objects['covers'].update_playlist_cover(pid, uris)

            d = uris_match_db(self)
            d.addCallback(after)
            return d

        d = self.get_playlist_artwork_uris(pid).addCallback(
            update_cover).addErrback(
                logError)

        if not artwork_only:
            d.addCallback(update)

        return d
