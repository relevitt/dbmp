# -*- coding: utf-8 -*-

from .sonos_util import SerialisedDevice, SerialisedDataBase
from .util import IP
from .util import snapshot
from .util import dbpooled
from .util import database_serialised
from .util import random_moves
from .util import create_moves
from .util import ms_to_str
from .util import str_to_ms
from .error import logError
from twisted.internet import reactor
from twisted.python.failure import Failure
from twisted.internet import defer
import time
from sqlite3 import OperationalError
import weakref
import random
from .logging_setup import getLogger
log = getLogger(__name__)


# sonos_client - adds client cmd functionality to a sonos_group instance.


class sonos_client(object):

    # @SerialisedDevice functions
    #
    # -	A @SerialisedDevice function should return a deferred, otherwise
    # it will return immediately and the next operation in the queue
    # will begin executing. This doesn't matter if the @SerialisedDevice
    # function does nothing other than call a function on the device,
    # because the next in the queue won't start until the device has
    # returned (as we're using an sp_factory). But, if there's a
    # sequence of device functions that needs to be serialised as one
    # operation, this will happen only if all relevant deferreds in the
    # chain are returned by the @SerialisedDevice function.
    #
    # -	Although a @SerialisedDevice function should return a deferred, it
    # (or the deferred it returns) should not be returned by the outer
    # function that calls the @SerialisedDevice function, otherwise the
    # outer @SerialisedDatabase function will also be waiting on the
    # @SerialisedDevice function to complete. There should be a clean
    # boundary between the inner @SerialisedDevice function and the
    # outer @SerialisedDatabase function.
    #
    # -	The @SerialisedDevice function should handle a device Failure
    # by calling self.flush_and_reconcile(), so that everything is
    # brought into sync again. The outer @SerialisedDatabase function
    # is allowed to return and move to the next operation in the queue
    # on the assumption that eventually the device will catch up. As
    # long as the device performs the same operations in the same order,
    # everything should eventually match up. After a device Failure,
    # this assumption will no longer be True.

    @SerialisedDataBase
    def get_queue(self, args=None):

        if not args:
            rowsPerPage = 50
            numRows = 100
            startIndex = 0
        else:
            rowsPerPage = int(args['rowsPerPage'])
            numRows = int(args['numRows'])
            startIndex = int(args['startIndex'])

        pos = int(self.status.queue_position) - 1
        res = {}
        res['label'] = self.name
        res['id'] = self.group_uid
        res['locked'] = 0
        res['queue_position'] = pos

        @dbpooled
        def get_data(tx, self, startIndex):

            query = '''	SELECT snapshot_id
                        FROM sonos_queues
                        WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            row = tx.fetchone()
            if row:
                res['snapshot_id'] = row[0]
            else:
                query = ''' INSERT INTO sonos_queues (groupid)
                            VALUES (?)'''
                tx.execute(query, (self.group_uid,))
                res['snapshot_id'] = 1

            query = '''	SELECT COUNT(*) 
                        FROM sonos_queue_data   
                        WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            length = tx.fetchone()[0]

            if startIndex > length - 1:
                startIndex = int((length - 1) / rowsPerPage) * rowsPerPage
            if startIndex == -1:
                startIndex = int(pos / rowsPerPage) * rowsPerPage
            startIndex = max(startIndex, 0)

            res['totalRecords'] = length
            res['startIndex'] = startIndex

            query = '''	SELECT artist, album, song, play_time, id
						FROM sonos_queue_data
                        WHERE groupid = ?
                        AND track_num >= ?
						AND track_num < ?
                        ORDER BY track_num'''
            tx.execute(
                query,
                (self.group_uid,
                 startIndex,
                 startIndex + numRows))

            res['results'] = [dict(row) for row in tx.fetchall()]
            return res

        return get_data(self, startIndex)

    @SerialisedDataBase
    def get_queue_ids(self, args=None):

        if not args:
            rowsPerPage = 100
            startIndex = 0
        else:
            rowsPerPage = int(args['rowsPerPage'])
            startIndex = int(args['startIndex'])

        @dbpooled
        def get_data(tx, self, startIndex):

            query = '''	SELECT snapshot_id
                        FROM sonos_queues
                        WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            snapshot_id = tx.fetchone()[0]

            query = '''	SELECT COUNT(*) FROM sonos_queue_data WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            length = tx.fetchone()[0]

            if startIndex > length - 1:
                startIndex = int((length - 1) / rowsPerPage) * rowsPerPage
            startIndex = max(startIndex, 0)

            query = '''	SELECT id FROM sonos_queue_data WHERE groupid = ? AND track_num >= ?
						AND track_num < ? ORDER BY track_num'''
            tx.execute(
                query,
                (self.group_uid,
                 startIndex,
                 startIndex + rowsPerPage))

            res = {}
            res['results'] = [row['id'] for row in tx.fetchall()]
            res['totalRecords'] = length
            res['id'] = self.group_uid
            res['snapshot_id'] = snapshot_id
            return res

        return get_data(self, startIndex)

    @SerialisedDataBase
    def delete_queue_rows(self, args={}, args_getter=None):

        @database_serialised
        @snapshot
        @dbpooled
        def delete_from_db_queue(tx, self, args):

            query = '''	DELETE FROM sonos_queue_data WHERE groupid = ? AND track_num = ?'''
            tx.executemany(query, [(self.group_uid, index)
                           for index in args['indices']])
            query = '''	CREATE TEMP TABLE tmp_data
				   		(pos INTEGER PRIMARY KEY ASC, album TEXT, artist TEXT,
                        song TEXT, play_time TEXT, id TEXT, history TEXT)'''
            tx.execute(query)
            query = '''	INSERT INTO tmp_data (album, artist, song, play_time,
                        id, history)
						SELECT album, artist, song, play_time, id, history
						FROM sonos_queue_data
						WHERE groupid = ?
						ORDER BY track_num'''
            tx.execute(query, (self.group_uid,))
            query = '''	DELETE FROM sonos_queue_data WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            query = '''	INSERT INTO sonos_queue_data (groupid, track_num, album,
                        artist, song, play_time, id, history)
						SELECT ?, pos-1, album, artist, song, play_time, id,
                        history
						FROM tmp_data ORDER BY pos'''
            tx.execute(query, (self.group_uid,))
            query = '''DROP TABLE tmp_data'''
            tx.execute(query)

        def delete_from_device_queue(result):
            if result == None:
                result = {}
            if result.get('status', None) == 'UNAUTHORISED':
                return result

            @SerialisedDevice
            def delete_from_device(self):
                return self.remove_tracks_from_queue(
                    args['indices']).addErrback(
                        lambda failure: self.flush_and_reconcile(
                            failure)).addErrback(
                        logError).addCallback(
                        lambda _: self.decrement_history()).addErrback(
                        logError)
            delete_from_device(self)
            return result

        if args_getter:
            def set_args(result):
                args['snapshot_id'], args['indices'] = result
            d = args_getter()
            d.addCallback(set_args)
            d.addCallback(lambda _: self.increment_history())
        else:
            d = self.increment_history()

        d.addCallback(lambda _: delete_from_db_queue(self, args))
        d.addCallback(self.update_queue_length)
        d.addCallback(self.WS_queue_contents_send)
        d.addCallback(self.update_queue_position)
        d.addCallback(delete_from_device_queue)
        return d

    @SerialisedDataBase
    @snapshot
    def move_queue_rows(self, args):

        moves = create_moves(list(args['indices']), args['dest'], 1)

        @database_serialised
        @dbpooled
        def move_in_db(tx, self, args):

            query = '''	SELECT album, artist, song, play_time, id, history
                        FROM sonos_queue_data WHERE groupid = ?
                        AND track_num
                        IN (''' + ",".join("?" * len(args['indices'])) + ''')
						ORDER BY track_num'''
            params = tuple([self.group_uid] + args['indices'])
            tx.execute(query, params)
            moved_rows = tx.fetchall()
            query = '''	DELETE FROM sonos_queue_data WHERE groupid = ? AND track_num = ?'''
            tx.executemany(query, [(self.group_uid, index)
                           for index in args['indices']])
            query = '''	CREATE TEMP TABLE tmp_data
				   		(pos INTEGER PRIMARY KEY ASC, album TEXT, artist TEXT,
                        song TEXT, play_time TEXT, id TEXT, history TEXT)'''
            tx.execute(query)
            query = '''	INSERT INTO tmp_data (album, artist, song, play_time,
                        id, history)
						SELECT album, artist, song, play_time, id, history
						FROM sonos_queue_data
						WHERE groupid = ? AND track_num < ?
						ORDER BY track_num'''
            tx.execute(query, (self.group_uid, args['dest']))
            query = '''	INSERT INTO tmp_data (album, artist, song, play_time,
                        id, history)
						VALUES(:album, :artist, :song, :play_time, :id,
                        :history)'''
            tx.executemany(query, moved_rows)
            query = '''	INSERT INTO tmp_data (album, artist, song, play_time,
                        id, history)
						SELECT album, artist, song, play_time, id, history
						FROM sonos_queue_data
						WHERE groupid = ? AND track_num >= ?
						ORDER BY track_num'''
            tx.execute(query, (self.group_uid, args['dest']))
            query = '''	DELETE FROM sonos_queue_data WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            query = '''	INSERT INTO sonos_queue_data (groupid, track_num, album,
                        artist, song, play_time, id, history)
						SELECT ?, pos-1, album, artist, song, play_time, id,
                        history
						FROM tmp_data ORDER BY pos'''
            tx.execute(query, (self.group_uid,))
            query = '''DROP TABLE tmp_data'''
            tx.execute(query)

        def move_in_device_queue(result):

            @SerialisedDevice
            def move_in_device(self):

                def process_next():
                    d = self.move_in_queue(*moves.pop(0))
                    d.addBoth(after).addErrback(logError)
                    return d

                def after(result):
                    if isinstance(result, Failure):
                        self.flush_and_reconcile(result)
                    elif len(moves):
                        return process_next()
                    self.decrement_history()

                return after(None)

            move_in_device(self)

        d = self.increment_history()
        d.addCallback(lambda _: move_in_db(self, args))
        d.addCallback(self.WS_queue_contents_send)
        d.addCallback(self.update_queue_position)
        d.addCallback(move_in_device_queue)
        return d

    @SerialisedDataBase
    def queue_shuffle(self, *args):

        length = int(self.status.queue_contents)
        indices = list(range(length))
        random.shuffle(indices)
        moves = random_moves(length, 1, indices)

        @database_serialised
        @dbpooled
        def shuffle_db(tx, self):

            query = '''	SELECT groupid, album, artist, song, play_time, id,
                        history
                        FROM sonos_queue_data WHERE groupid = ?
						ORDER BY track_num'''
            tx.execute(query, (self.group_uid,))
            rows = [dict(item) for item in tx.fetchall()]
            shuffled_rows = []
            for n, index in enumerate(indices):
                row = rows[index]
                row['track_num'] = n
                shuffled_rows.append(row)
            query = '''	DELETE FROM sonos_queue_data WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            query = '''	INSERT INTO sonos_queue_data (groupid, track_num, album,
                        artist, song, play_time, id, history)
						VALUES (:groupid, :track_num, :album, :artist, :song,
                        :play_time, :id, :history)'''
            tx.executemany(query, shuffled_rows)

        def move_in_device_queue(result=None):

            @SerialisedDevice
            def move_in_device(self):

                var = {}
                var['first_pass'] = True

                def process_next():
                    index, dest = moves.pop(0)
                    if index != dest:
                        no_update_id = True
                        if var['first_pass']:
                            no_update_id = False
                            var['first_pass'] = False
                        d = self.move_in_queue(
                            index, dest, no_update_id=no_update_id)
                    else:
                        d = defer.Deferred().callback(None)
                    d.addBoth(after).addErrback(logError)
                    return d

                def after(result):
                    if isinstance(result, Failure):
                        self.flush_and_reconcile(result)
                    elif len(moves):
                        return process_next()
                    self.decrement_history()

                return after(None)

            move_in_device(self)

        d = self.increment_history()
        d.addCallback(lambda _: shuffle_db(self))
        d.addCallback(self.WS_queue_contents_send)
        d.addCallback(self.update_queue_position)
        d.addCallback(move_in_device_queue)
        d.addCallback(self.update_snapshot_id)
        return d

    @SerialisedDataBase
    def transfer_queue_rows(self, args):
        '''
        At the time of latest update of this method, at most one
        page (50) of rows will be transferred, so there isn't the
        same responsiveness concern as there is for add_container, where
        a playlist of any length may be added to the queue. In case
        this changes, add_container has a slightly more responsive approach.
        '''

        indices = args['indices']
        dest = args['dest'] + 1
        dlist = []
        dlist.append(self.check_snapshot_id(
            None, args['snapshot_id']).addErrback(
            logError))

        def add_items(self, rows, dest, meta_geta):

            d = self.add_rows_to_db_queue(rows, dest - 1)

            def add_to_device_queue(rows):
                @SerialisedDevice
                def add_to_device(self):
                    return self.add_multiple_uris_to_queue(
                        [meta_geta(row) for row in rows], dest).addErrback(
                            lambda failure: self.flush_and_reconcile(
                                failure)).addErrback(
                            logError).addCallback(
                            lambda _: self.decrement_history()).addErrback(
                            logError)
                add_to_device(self)

            d.addCallback(self.update_queue_length)
            d.addCallback(self.WS_queue_contents_send)
            d.addCallback(self.update_queue_position)
            d.addCallback(add_to_device_queue)
            d.addCallback(self.update_snapshot_id)
            return d

        if args['system'] == 'sonos':
            s_group = self.factory.uids[args['startId']]

            dlist.append(s_group.check_snapshot_id(
                None, args['source_snapshot_id']).addErrback(
                logError))

            def add_queue():

                def meta_geta(queueable_item):
                    if queueable_item['type'] == 's':
                        return self.get_spotify_track_codes(queueable_item['id'])
                    else:
                        return self.get_database_trackcodes(queueable_item)

                def get_db_data(conn):

                    def get_type(track_id):
                        if 'spotify' in track_id:
                            return 's'
                        else:
                            try:
                                int(track_id)
                                return 'd'
                            except ValueError:
                                return 'x'

                    def in_range(track_num):
                        if track_num in args['indices']:
                            return 1
                        else:
                            return 0

                    w_in_range = weakref.ref(in_range)

                    conn.create_function('GET_TYPE', 1, get_type)
                    conn.create_function(
                        'IN_RANGE',
                        1,
                        lambda index: w_in_range()(index))
                    tx = conn.cursor()

                    query = '''	SELECT sonos_queue_data.track_num, sonos_queue_data.album,
								sonos_queue_data.artist, sonos_queue_data.song,
								sonos_queue_data.play_time, sonos_queue_data.id,
								song.discid, song.filename,	disc.artwork_update,
								GET_TYPE(sonos_queue_data.id) AS type
								FROM sonos_queue_data
								JOIN song ON (sonos_queue_data.id = song.id)
								JOIN disc ON (song.discid = disc.id)
								WHERE sonos_queue_data.groupid = ?1
								AND sonos_queue_data.track_num >= ?2
								AND sonos_queue_data.track_num <= ?3
								AND GET_TYPE(sonos_queue_data.id) = "d"
								AND	IN_RANGE(sonos_queue_data.track_num) = 1

								UNION ALL

								SELECT sonos_queue_data.track_num, sonos_queue_data.album,
								sonos_queue_data.artist, sonos_queue_data.song,
								sonos_queue_data.play_time, sonos_queue_data.id,
								0 AS discid, '' AS filename, 0 AS artwork_update,
								GET_TYPE(sonos_queue_data.id) AS type
								FROM sonos_queue_data
								WHERE sonos_queue_data.groupid = ?1
								AND sonos_queue_data.track_num >= ?2
								AND sonos_queue_data.track_num <= ?3
								AND GET_TYPE(sonos_queue_data.id) = "s"
								AND	IN_RANGE(sonos_queue_data.track_num) = 1

								ORDER BY track_num'''

                    tx.execute(
                        query,
                        (args['startId'],
                         args['indices'][0],
                            args['indices'][-1]))
                    return tx.fetchall()

                d = self.dbpool.runWithConnection(get_db_data)

                def after(rows):
                    return add_items(self, rows, dest, meta_geta)

                d.addCallback(after)
                return d

            def delete_rows(result):
                if len(indices):
                    indices.reverse()
                    params = {}
                    params['snapshot_id'] = args['source_snapshot_id']
                    params['indices'] = indices
                    s_group.delete_queue_rows(
                        params)  # this is another group, so won't freeze serialiser
                return result

            def process():
                d = add_queue()
                d.addCallback(delete_rows)
                return d

        else:
            startId = args['startId']
            dlist.append(self.factory.db_player.check_snapshot_id(
                startId, args['source_snapshot_id']).addErrback(
                logError))

            @dbpooled
            def get_items(tx, self, startId, indices):
                query = '''SELECT artist, disc.title AS album, song.title AS song, discid, filename,
					play_time, disc.artwork_update AS artwork_update, song.id AS id
					FROM song JOIN queue_data ON (song.id = queue_data.songid)
					JOIN disc ON (disc.id = song.discid)
					JOIN artist ON (artist.id = song.artistid)
					WHERE queue_id = ? AND queue_data.track_num IN (''' + ",".join("?" * len(indices)) + ''')
					ORDER BY queue_data.track_num'''
                params = [startId]
                params += indices
                params = tuple(params)
                tx.execute(query, params)
                return tx.fetchall()

            def add_rows(rows):

                def meta_geta(row):
                    return self.get_database_trackcodes(row)

                return add_items(self, rows, dest, meta_geta)

            def process():
                d = get_items(self, startId, indices)
                d.addCallback(add_rows)
                return d

        def check_snapshot_ids(results):
            try:
                passed, res = results[0][1]
                if not passed:
                    return res
                passed, res = results[1][1]
                if not passed:
                    res['status'] = 'ERROR'
                    return res
            except:
                log.exception('Problem in transfer_queue_rows')
                res = {}
                res['status'] = 'ERROR'
                return res

            d = self.increment_history()
            d.addCallback(lambda _: process())
            return d

        d = defer.DeferredList(dlist)
        d.addCallback(check_snapshot_ids)
        return d

    @database_serialised
    def copy_to_clipboard(self, args):

        def copy_to_clipboard(conn):

            def track_num_gen():
                counter = 0
                while True:
                    yield counter
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

            def in_range(track_num):
                if track_num in args['indices']:
                    return 1
                else:
                    return 0

            w_in_range = weakref.ref(in_range)

            conn.create_function(
                'GET_NEXT_TRACK_NUM',
                0,
                lambda: next(w_gen()))
            conn.create_function('GET_TYPE', 1, get_type)
            conn.create_function(
                'IN_RANGE',
                1,
                lambda index: w_in_range()(index))
            tx = conn.cursor()

            query = '''DELETE FROM clipboard_data WHERE clientid = ?'''
            tx.execute(query, (args['client_id'],))

            query = '''	INSERT INTO clipboard_data (clientid, songid, type, track_num)
						SELECT ?,
                        id,
                        GET_TYPE(id),
						GET_NEXT_TRACK_NUM()
						FROM (SELECT id FROM sonos_queue_data
						WHERE groupid = ?
						AND track_num >= ?
						AND track_num <= ?
						AND IN_RANGE(track_num)
						AND GET_TYPE(id) != "x"
						ORDER BY track_num)'''

            tx.execute(query, (args['client_id'], self.group_uid,
                               args['indices'][0], args['indices'][-1]))

            self.factory.db_player.update_clipboard_access(
                tx, args['client_id'])

        return self.dbpool.runWithConnection(copy_to_clipboard)

    @SerialisedDataBase
    @snapshot
    def paste_from_clipboard(self, args):
        '''
        See comment on transfer_queue_rows above.
        '''

        clientid = args['client_id']
        dest = args['dest']
        if dest == -1:
            dest = int(self.status.queue_contents)
        dest += 1

        def add_items(self, rows, dest, meta_geta):

            def integrate_and_add_to_db_queue(results):
                for n in range(len(rows) - 1, -1, -1):
                    if rows[n]['type'] == 's':
                        try:
                            if rows[n]['songid'] == results[-1]['id']:
                                item = dict(rows[n])
                                item.update(dict(results.pop()))
                                rows[n] = item
                            else:  # must have been a problem getting the data so we delete
                                rows.pop(n)
                        except IndexError:  # must have been a problem getting the data so we delete
                            rows.pop(n)
                return self.add_rows_to_db_queue(rows, dest - 1)

            def add_to_device_queue(rows):
                @SerialisedDevice
                def add_to_device(self):
                    return self.add_multiple_uris_to_queue(
                        [meta_geta(row) for row in rows], dest).addErrback(
                            lambda failure: self.flush_and_reconcile(
                                failure)).addErrback(
                            logError).addCallback(
                            lambda _: self.decrement_history()).addErrback(
                            logError)
                add_to_device(self)

            d = self.objects['spotify_cache'].get_track_data(
                [row['songid'] for row in rows if row['type'] == 's'], args['client_id'])
            d.addCallback(integrate_and_add_to_db_queue)
            d.addCallback(self.update_queue_length)
            d.addCallback(self.WS_queue_contents_send)
            d.addCallback(self.update_queue_position)
            d.addCallback(add_to_device_queue)
            d.addErrback(logError)
            return d

        @database_serialised
        @dbpooled
        def get_data(tx, self, clientid):
            query = '''SELECT artist, disc.title AS album, song.title AS song, song.id AS id, discid, filename,
				play_time, type, clipboard_data.track_num, disc.artwork_update AS artwork_update
				FROM song JOIN clipboard_data ON (song.id = clipboard_data.songid)
				JOIN disc ON (disc.id = song.discid)
				JOIN artist ON (artist.id = song.artistid)
				WHERE clientid = ? AND type = 'd'
				ORDER BY clipboard_data.track_num'''
            tx.execute(query, (clientid,))
            dbplayer_rows = tx.fetchall()
            query = '''SELECT songid, type, track_num FROM clipboard_data
				WHERE clientid = ?  AND type = 's'
				ORDER BY track_num'''
            tx.execute(query, (clientid,))
            rows = tx.fetchall()
            self.factory.db_player.update_clipboard_access(tx, clientid)
            if len(rows):
                for row in dbplayer_rows:
                    rows.insert(row['track_num'], row)
                return rows
            else:
                return dbplayer_rows

        def meta_geta(row):
            if row['type'] == 'd':
                return self.get_database_trackcodes(row)
            else:
                return self.get_spotify_track_codes(row['songid'])

        def add_rows(rows):
            return add_items(self, rows, dest, meta_geta)

        d = self.increment_history()
        d.addCallback(lambda _: get_data(self, clientid))
        d.addCallback(add_rows)
        return d

    # queue_clear is not serialised, because we
    # want it to execute right away

    def queue_clear(self, *args):

        # We set the STOP_OPS flag, as pending device operations
        # are defunct if we are clearing the queue and we don't
        # want to wait for them to complete
        self.STOP_OPS = True

        self.stop()

        @SerialisedDataBase
        @SerialisedDevice
        def clear_queue(self):

            # Reset flags
            self.status.set_queue_requested = None
            self.status.pending_device_updates = 0
            self.STOP_OPS = False

            @database_serialised
            @dbpooled
            def db_queue_clear(tx, self):
                query = '''	DELETE FROM sonos_queue_data WHERE groupid = ?'''
                tx.execute(query, (self.group_uid,))

            def device_queue_clear(result=None):
                var = {}

                def device_clear(self):
                    var['next_updateid'] = self.status.updateid + 1
                    d = self.device.clear_queue()
                    d.addBoth(after).addErrback(logError)
                    return d

                def after(result):
                    if isinstance(result, Failure):
                        self.flush_and_reconcile(result)
                    else:
                        self.update_update_id(var['next_updateid'])

                return device_clear(self)

            d = db_queue_clear(self)
            d.addCallback(self.update_queue_length)
            d.addCallback(self.WS_queue_contents_send)
            d.addCallback(device_queue_clear)
            d.addCallback(self.update_snapshot_id)
            return d

        return clear_queue(self)

    @SerialisedDataBase
    def set_queue_pos(self, args):
        n = args['position']
        if not self.status.pending_device_updates:
            self.go_to_queue_pos(n)
            return

        self.WS_set_queue_alert(True)

        d = self.get_history(n)

        def set_history(history):
            self.status.set_queue_requested = history

        d.addCallback(set_history)
        return d

    def jump(self, args):
        n = args['position']
        self.device.seek(ms_to_str(n)).addErrback(lambda failure: None)

    def play(self, *args):
        self.update_transition('PLAYING')
        self.device.play().addErrback(lambda failure: None)

    def play_pause(self, *args):
        if self.status.transport_state == 'PLAYING':
            self.update_transition('PAUSED_PLAYBACK')
            self.device.pause().addErrback(lambda failure: None)
        else:
            self.update_transition('PLAYING')
            self.device.play().addErrback(lambda failure: None)

    def prev_track(self, *args):
        if int(self.status.queue_position) > 1:
            self.device.previous().addErrback(lambda failure: None)

    def next_track(self, *args):
        if int(self.status.queue_position) != int(self.status.queue_contents):
            self.device.next_track().addErrback(lambda failure: None)

    def stop(self, *args):
        self.update_transition('STOPPED')
        self.device.stop().addErrback(lambda failure: None)

    def set_main_volume(self, args):
        v = args['volume']
        channel = args['channel']

        if not self.multizone:
            self.device.volume(v).addErrback(lambda failure: None)
        else:
            self.WS_volume_pause()
            if channel == 'Group Volume':
                self.device.set_group_volume(
                    v).addErrback(lambda failure: None)
            else:
                self.devices[channel].volume(
                    v).addErrback(lambda failure: None)

        self.WS_volume(channel, v)

    def mute(self, args):

        def set_mute(self, device):
            d = device.mute()

            def after(muted):
                if muted:
                    device.mute(False)
                else:
                    device.mute(True)
            d.addCallback(after)

        channel = args['channel']
        if not self.multizone:
            set_mute(self, self.device)
        elif channel != 'Group Volume':
            set_mute(self, self.devices[channel])
        else:
            channels = list(self.devices.keys())
            for channel in channels:
                set_mute(self, self.devices[channel])

    def transfer_queue(self, args):

        from_group = self.factory.uids[args['sonos_uid']]
        transport_state = from_group.status.transport_state
        song_progress = from_group.status.song_progress
        queue_position = from_group.status.queue_position

        pass1_args = args.copy()
        pass2_args = args.copy()

        def pass1(_result):
            if self.STOP_OPS:
                return
            pass1_args['from'] = int(queue_position) - 1
            if transport_state == 'PLAYING':
                pass1_args['play_now'] = True
            pass1_args['jump'] = str_to_ms(song_progress)
            d = defer.Deferred()
            pass1_args['cb'] = d
            self.add_container(pass1_args)
            return d

        def pass2(_result):
            if self.STOP_OPS:
                from_group.queue_clear()
                return
            pass2_args['to'] = int(queue_position) - 2
            pass2_args['pos'] = 1
            d = self.add_container(pass2_args)
            d.addCallback(lambda _: from_group.queue_clear())
            return d

        d = self.queue_clear()
        d.addCallback(pass1)
        d.addCallback(pass2)
        d.addErrback(logError)
        return d

    @SerialisedDataBase
    def add_container(self, args):

        var = {}
        var['gen'] = None
        var['time'] = time.time()
        var['dest'] = args.get('pos', 0)
        if args.get('play_next', False):
            var['dest'] = int(self.status.queue_position) + 1
        if args.get('clear', False):
            var['dest'] = 1
        dest = int(self.status.queue_contents) if not var[
            'dest'] else var['dest'] - 1
        temp_table_name = 'add_container_{}'.format(
            str(self.factory.db_temp_table_counter))
        self.factory.db_temp_table_counter += 1

        def play(self, pos):
            if self.STOP_OPS:
                if args.get('cb'):
                    args['cb'].callback(None)
                return

            # If there has been a subsequent user request to change
            # the queue position, we will yield to it
            if self.status.set_queue_requested:
                if args.get('cb'):
                    args['cb'].callback(None)
                return

            if args.get('add_and_play', False) or args.get('play_now', False):
                self.play_after_adding(pos, var['time'], args['play_now'])
                # This is a blunt instrument. The transfer_queue method
                # may perform two calls of add_container in quick succession,
                # so we delay the second call slightly after setting play, so
                # that everything has time to settle. It would be nice to be
                # more precise!
                if args.get('cb'):
                    reactor.callLater(0.25, args['cb'].callback, None)
            else:
                if args.get('cb'):
                    args['cb'].callback(None)
            if args.get('jump'):
                reactor.callLater(1, self.jump, {'position': args['jump']})

        @defer.inlineCallbacks
        def add_spotify_container():

            spotify_args = args
            _dest = dest

            @SerialisedDevice
            def add_to_device(self):
                if self.STOP_OPS:
                    return
                return self.add_spotify_container_to_queue(
                    args['container_id'], var['dest'])

            while True:
                if self.STOP_OPS:
                    break
                result = yield self.objects['spotify'].get_container_tracks(
                    spotify_args, fulldata=True).addErrback(logError)
                if self.STOP_OPS:
                    break
                if result.get('tracks'):
                    yield self.add_rows_to_db_queue(
                        result['tracks'], _dest).addErrback(logError)
                    _dest += len(result['tracks'])
                if result.get('var'):
                    spotify_args = {'var': result['var']}
                else:
                    break

            yield self.update_queue_length().addCallback(
                self.WS_queue_contents_send).addCallback(
                self.update_queue_position).addErrback(
                    logError)
            try:
                n = yield add_to_device(self)
                play(self, n)
            except Exception as e:
                self.flush_and_reconcile(e)
            self.decrement_history().addErrback(logError)

        @defer.inlineCallbacks
        def add_data_to_db_queue():
            tracks = None
            if 'tracks' in args.keys():
                tracks = yield self.objects[
                    'spotify_cache'].get_track_data(args['tracks'], args['client_id'])
            elif ('artistRecommendations' in str(args.get('container_id'))
                  or 'trackRecommendations' in str(args.get('container_id'))):
                result = yield self.objects['spotify'].get_container_tracks(
                    args, fulldata=True)
                tracks = result.get('tracks')
            if tracks:
                var['count'] = len(tracks)
                outcome = yield self.add_rows_to_db_queue(tracks, dest)
            else:
                outcome = yield copy_data_to_db_queue(self)
            return outcome

        @database_serialised
        def copy_data_to_db_queue(self):
            return self.dbpool.runWithConnection(_copy_data_to_db_queue)

        def _copy_data_to_db_queue(conn):

            def track_num_gen():
                counter = 0
                while True:
                    yield dest + counter
                    counter += 1

            gen = track_num_gen()
            w_gen = weakref.ref(gen)
            conn.create_function(
                'GET_NEXT_TRACK_NUM',
                0,
                lambda: next(w_gen()))

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
            tx = conn.cursor()

            if args.get('sonos_uid'):
                args['container_id'] = args['sonos_uid']
                query = '''	SELECT COUNT(*) FROM sonos_queue_data WHERE groupid = ?'''
                if 'from' in args:
                    query += ''' AND track_num >= ?'''
                if 'to' in args:
                    query += ''' AND track_num <= ?'''
            elif args['data_type'] == 'queue':
                query = '''	SELECT COUNT(*) FROM queue_data WHERE queue_id = ?'''
            elif args['data_type'] == 'playlist':
                query = '''	SELECT COUNT(*) FROM playlist_data WHERE playlistid = ?'''
            else:
                query = '''	SELECT COUNT(*) FROM song WHERE discid = ?'''
            if 'indices' in args.keys():
                query += ''' AND track_num IN (''' + ",".join(
                    "?" * len(args['indices'])) + ''')'''
            params = [args['container_id']]
            params += args['indices'] if 'indices' in args.keys() else []
            if 'from' in args:
                params.append(args['from'])
            if 'to' in args:
                params.append(args['to'])
            tx.execute(query, tuple(params))
            var['count'] = tx.fetchone()[0]

            query = '''	UPDATE sonos_queue_data
						SET track_num = track_num + ?
						WHERE groupid = ? AND track_num >= ?'''
            tx.execute(query, (var['count'], self.group_uid, dest))

            query = '''	INSERT INTO sonos_queue_data (groupid, track_num,
					 	album, artist, song, play_time, id, history)'''

            if args.get('sonos_uid'):
                sel = '''	SELECT 
                                ?, 
                                GET_NEXT_TRACK_NUM(),
                                album, artist, song, play_time, id,
                                ?
                            FROM (
                                SELECT album, artist, song, play_time, id
                                FROM sonos_queue_data
                                WHERE groupid = ?'''

                if 'from' in args:
                    sel += ''' AND track_num >= ?'''
                if 'to' in args:
                    sel += ''' AND track_num <= ?'''
                if 'indices' in args.keys():
                    sel += ''' AND IN_RANGE(track_num) = 1'''
                sel += ''' ORDER BY track_num)'''

            elif args['data_type'] == 'queue':
                sel = '''	SELECT 
                                ?, 
                                GET_NEXT_TRACK_NUM(),
                                album, artist, song, play_time, id,
                                ?
                            FROM (
                                SELECT disc.title as album, artist,
                                song.title as song,
                                song.play_time as play_time,
                                queue_data.songid as id
                                FROM queue_data
                                JOIN song ON (queue_data.songid = song.id)
                                JOIN disc ON (song.discid = disc.id)
                                JOIN artist ON (song.artistid = artist.id)
                                WHERE queue_id = ?'''

                if 'indices' in args.keys():
                    sel += ''' AND IN_RANGE(queue_data.track_num) = 1'''
                sel += ''' ORDER BY queue_data.track_num)'''

            elif args['data_type'] == 'playlist':
                if 'indices' in args.keys():
                    stub = '''	AND	IN_RANGE(playlist_data.track_num) = 1'''
                else:
                    stub = ''
                sel = '''	SELECT
                                ?1,
                                GET_NEXT_TRACK_NUM(),
                                album, artist, song, play_time, songid,
                                ?2
							FROM (
                                SELECT disc.title AS album, artist,
                                song.title AS song, song.play_time,
                                playlist_data.songid, playlist_data.track_num
                                FROM playlist_data
                                JOIN song ON (playlist_data.songid = song.id)
                                JOIN disc ON (song.discid = disc.id)
                                JOIN artist ON (song.artistid = artist.id)
                                WHERE playlistid = ?3
                                {0} AND playlist_data.type = "d"

							UNION ALL

                                SELECT album, artist, song, play_time,
                                playlist_data.songid, track_num
                                FROM playlist_data
                                JOIN spotify_track_cache
                                ON (playlist_data.songid = spotify_track_cache.songid)
                                WHERE playlistid = ?3
                                {0} AND playlist_data.type = "s"

							ORDER BY track_num)'''.format(stub)
            else:

                sel = '''	SELECT
                                ?,
                                GET_NEXT_TRACK_NUM(),
                                album, artist, title, play_time, id,
                                ?
							FROM (
                                SELECT disc.title AS album, artist, song.title,
							    song.play_time, song.id
                                FROM
                                disc JOIN song ON (disc.id = song.discid)
							    JOIN artist ON (song.artistid = artist.id)
							    WHERE disc.id = ?'''

                if 'indices' in args.keys():
                    sel += ''' AND	IN_RANGE(track_num) = 1'''
                sel += ''' ORDER BY track_num)'''

            params = [self.group_uid, self.initialise_history(),
                      args['container_id']]
            if 'from' in args:
                params.append(args['from'])
            if 'to' in args:
                params.append(args['to'])
            tx.execute(query + sel, params)

        @dbpooled
        def create_temp_table(tx, self):
            def create_table():
                query = '''	CREATE TABLE {}
					   		(track_num INTEGER PRIMARY KEY ASC, album TEXT,
							artist TEXT, song TEXT, play_time TEXT,
							id TEXT)'''.format(temp_table_name)
                tx.execute(query)
            try:
                create_table()
            except OperationalError as e:
                if 'already exists' in e.args[0]:
                    query = '''DROP table {}'''.format(temp_table_name)
                    tx.execute(query)
                    create_table()
                else:
                    raise
            query = '''	INSERT INTO {}
						(album, artist, song, play_time, id)
						SELECT album, artist, song, play_time, id
						FROM sonos_queue_data
						WHERE groupid = ?
						AND track_num >= ?
						AND track_num < ?
						ORDER BY track_num'''.format(temp_table_name)
            tx.execute(query, (self.group_uid, dest, dest + var['count']))

        def add_data_to_device_queue(results=None):

            chunk_size = 16

            var['stop'] = False
            var['start'] = 1
            end = var['start'] + var['count']

            var['first_pass'] = True
            var['added'] = 0

            @dbpooled
            def get_rows_from_db(tx, self):

                start = var['start']
                var['start'] += chunk_size
                _end = min(var['start'], end)

                query = '''	SELECT {0}.track_num, {0}.album,
							{0}.artist, {0}.song,
							{0}.play_time, {0}.id,
							song.discid, song.filename,	disc.artwork_update
							FROM {0}
							JOIN song ON ({0}.id = song.id)
							JOIN disc ON (song.discid = disc.id)
							WHERE {0}.track_num >= ?1
							AND {0}.track_num < ?2
							AND {0}.id NOT LIKE "spotify%"

							UNION ALL

							SELECT {0}.track_num, {0}.album,
							{0}.artist, {0}.song,
							{0}.play_time, {0}.id,
							0 AS discid, '' AS filename, 0 AS artwork_update
							FROM {0}
							WHERE {0}.track_num >= ?1
							AND {0}.track_num < ?2
							AND {0}.id LIKE "spotify%"

							ORDER BY track_num'''.format(temp_table_name)

                tx.execute(query, (start, _end))
                rows = tx.fetchall()
                if len(rows) < chunk_size:
                    var['stop'] = True
                return rows

            @dbpooled
            def drop_temp_table(tx, self):
                query = '''	DROP TABLE {0}'''.format(temp_table_name)
                tx.execute(query)

            def meta_geta(row):
                if 'spotify' in str(row['id']):
                    return self.get_spotify_track_codes(row['id'])
                else:
                    return self.get_database_trackcodes(row)

            @SerialisedDevice
            @defer.inlineCallbacks
            def add_data_to_device(self):

                while True:
                    if self.STOP_OPS:
                        return
                    rows = yield get_rows_from_db(self)
                    if self.STOP_OPS:
                        return
                    if not rows or not len(rows):
                        return
                    items = [meta_geta(row) for row in rows]
                    try:
                        result = yield self.add_multiple_uris_to_queue(
                            items, var['dest'])
                        if self.STOP_OPS:
                            return
                    except Exception as e:
                        self.flush_and_reconcile(e)
                        return
                    pos, n = result
                    if var['dest']:
                        var['dest'] += n
                    if var['first_pass'] and pos:
                        var['first_pass'] = False
                        play(self, pos)
                    var['added'] += n
                    self.check_set_queue({
                        'dest': dest,
                        'added': var['added']
                    })
                    if var['stop'] or var['start'] >= end:
                        return

            def clean_up(outcome):
                if isinstance(outcome, Failure):
                    logError(outcome)
                self.decrement_history()
                drop_temp_table(self)

            add_data_to_device(self).addBoth(
                clean_up).addErrback(logError)

        d = self.increment_history()

        if (args.get('data_source') == 'database'
           or 'sonos_uid' in args
           or 'artistRecommendations' in str(args.get('container_id'))
           or 'trackRecommendations' in str(args.get('container_id'))
           or 'indices' in args.keys()
           or 'tracks' in args.keys()):
            d.addCallback(lambda _: add_data_to_db_queue())
            d.addCallback(lambda _: create_temp_table(self))
            d.addCallback(self.update_queue_length)
            d.addCallback(self.WS_queue_contents_send)
            d.addCallback(self.update_queue_position)
            d.addCallback(add_data_to_device_queue)
        else:
            d.addCallback(lambda _: add_spotify_container())

        d.addCallback(self.update_snapshot_id)
        return d

    @SerialisedDataBase
    def add_track(self, args):

        var = {}
        var['time'] = time.time()

        dest = int(self.status.queue_contents)

        @dbpooled
        def get_data(tx, self):
            query = '''	SELECT artist, disc.title AS album, song.title AS song, song.id AS id,
						discid, filename, play_time, disc.artwork_update AS artwork_update
						FROM song JOIN artist ON (song.artistid = artist.id)
						JOIN disc ON(discid = disc.id) WHERE song.id = ?'''
            tx.execute(query, (args['song_id'],))
            return tx.fetchall()

        def add_track_to_db_queue(results):
            return self.add_rows_to_db_queue(results, dest)

        def add_track_to_device_queue(rows):
            @SerialisedDevice
            def add_track_to_device(self):
                if 'spotify' in str(args['song_id']):
                    d = self.add_spotify_track_to_queue(args['song_id'])
                else:
                    d = self.add_row_to_queue(rows[0])
                d.addBoth(after).addErrback(logError)
                return d
            add_track_to_device(self)

        def after(n):
            if isinstance(n, Failure):
                self.flush_and_reconcile(n)
            elif args['add_and_play']:
                self.play_after_adding(n, var['time'])
            self.decrement_history()

        d = self.increment_history()
        if 'spotify' in str(args['song_id']):
            d.addCallback(
                lambda _: self.objects['spotify_cache'].get_track_data([args['song_id']], args['client_id']))
        else:
            d.addCallback(lambda _: get_data(self))
        d.addCallback(add_track_to_db_queue)
        d.addCallback(self.update_queue_length)
        d.addCallback(self.WS_queue_contents_send)
        d.addCallback(self.update_queue_position)
        d.addCallback(add_track_to_device_queue)
        d.addCallback(self.update_snapshot_id)
        return d

    @SerialisedDataBase
    def add_stream_to_queue(self, *args):

        uri = 'http://{}:{}{}'.format(IP.IP, '8888', '/pc.mp3')
        row = {
            'artist': 'Laptop',
            'album': 'vlc',
            'song': 'Local Stream at port 8888',
            'id': uri,
            'play_time': None
        }
        dest = int(self.status.queue_contents)

        d = self.increment_history()
        d.addCallback(lambda _: self.add_rows_to_db_queue([row], dest))

        def add_to_device_queue(_):
            @SerialisedDevice
            def add_to_device(self):
                _uri, metadata = self.get_database_trackcodes(
                    row, None, uri, '')
                return self.add_uri_to_queue(
                    _uri, metadata, 0).addErrback(
                        lambda failure: self.flush_and_reconcile(
                            failure)).addErrback(
                        logError).addCallback(
                        lambda _: self.decrement_history()).addErrback(
                        logError)
            add_to_device(self)

        d.addCallback(self.update_queue_length)
        d.addCallback(self.WS_queue_contents_send)
        d.addCallback(self.update_queue_position)
        d.addCallback(add_to_device_queue)
        d.addCallback(self.update_snapshot_id)
        return d

    @SerialisedDataBase
    @SerialisedDevice
    def detach_zone(self, args):
        return self.devices[args['zone']].unjoin()

    @SerialisedDataBase
    @SerialisedDevice
    def add_zone(self, args):
        return self.factory.uids[args['zone']].device.join(self.device.uid)

    def remove_artist_or_album_from_queue(self, args):

        @dbpooled
        def get_indices_for_removal(tx, self):

            query = ''' SELECT snapshot_id
                            FROM sonos_queues
                            WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            snapshot_id = tx.fetchone()[0]

            mainquery = '''	SELECT track_num FROM sonos_queue_data
							WHERE groupid = ?1
							AND artist = (SELECT artist FROM
							sonos_queue_data WHERE groupid = ?1
							AND track_num = ?2){}
							ORDER BY track_num DESC'''

            subquery = ''' 	AND album = (SELECT album FROM
							sonos_queue_data WHERE groupid = ?1
							AND track_num = ?2)'''

            query = mainquery.format('' if args['remove_artist'] else subquery)
            tx.execute(query, (self.group_uid, args['track_index']))
            return snapshot_id, [row['track_num'] for row in tx.fetchall()]

        self.delete_queue_rows(
            args_getter=lambda: get_indices_for_removal(self))

    @dbpooled
    def find_in_queue(tx, self, args):

        start = args['start'] if args['start'] != None else -1
        query = ''' SELECT track_num FROM sonos_queue_data
                    WHERE groupid = ?1
                    AND track_num > ?2
                    AND (artist LIKE ?3
                    OR album LIKE ?3
                    OR song LIKE ?3)
                    ORDER BY track_num'''

        tx.execute(query, (self.group_uid, start,
                   '%' + args['search_term'] + '%'))
        row = tx.fetchone()
        if row:
            return row[0]
        query = ''' SELECT track_num FROM sonos_queue_data
                    WHERE groupid = ?1
                    AND track_num <= ?2
                    AND (artist LIKE ?3
                    OR album LIKE ?3
                    OR song LIKE ?3)
                    ORDER BY track_num'''

        tx.execute(query, (self.group_uid, start,
                   '%' + args['search_term'] + '%'))
        row = tx.fetchone()
        if row:
            return row[0]
        else:
            return None
