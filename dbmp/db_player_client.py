# -*- coding: utf-8 -*-

from .util import authenticated, mpd_check_connected
from .util import dbpooled, database_serialised, snapshot
from .error import logError
from twisted.internet import defer
import time
from .logging_setup import getLogger
log = getLogger(__name__)


class db_player_client(object):

    '''
    Client commands forming part of db_player appear here.
    '''

# search_queues

    @dbpooled
    def search_queues(tx, self, args):

        query = '''SELECT COUNT(*) FROM queue_names WHERE locked = 0'''
        tx.execute(query)
        totalRecords = tx.fetchone()[0]
        query = '''	SELECT name AS title, id AS itemid FROM queue_names WHERE locked = 0
					ORDER BY id'''
        tx.execute(query)
        rows = tx.fetchall()
        if args['startIndex'] > len(rows):
            return
        res = {}
        res['startIndex'] = args['startIndex']
        res['totalRecords'] = totalRecords
        res['results'] = [
            dict(row) for row in rows[
                args['startIndex']:args['startIndex'] + args['rowsPerPage']
            ]
        ]
        return res

# get_queue

    def get_queue(self, args):
        rowsPerPage = int(args['rowsPerPage'])
        numRows = int(args['numRows'])
        var = {
            'startIndex': int(args['startIndex'])
        }
        if 'id' in args.keys():
            d = self.get_queue_metadata(args['id'])
        else:
            d = self.get_queue_metadata()

        @dbpooled
        def process(tx, self, queue):
            length = queue['length']
            pos = queue['position']
            if var['startIndex'] > length - 1:
                var['startIndex'] = int(
                    (length - 1) / rowsPerPage) * rowsPerPage
            if var['startIndex'] == -1:
                var['startIndex'] = int(pos / rowsPerPage) * rowsPerPage
            var['startIndex'] = max(var['startIndex'], 0)
            n = min(numRows, length - var['startIndex'])
            query = ''' SELECT snapshot_id
                        FROM queue_names
                        WHERE id = ?'''
            tx.execute(query, (queue['id'],))
            snapshot_id = tx.fetchone()[0]
            query = ''' SELECT artist, disc.title AS album,
                        song.title AS song, song.id AS id,
                        play_time AS play_time
        				FROM queue_data
                        JOIN song ON (queue_data.songid = song.id)
        				JOIN disc ON (song.discid = disc.id)
        				JOIN artist ON (song.artistid = artist.id)
        				WHERE queue_id = ? AND queue_data.track_num >= ?
        				ORDER BY queue_data.track_num LIMIT ?'''
            tx.execute(query, (queue['id'], var['startIndex'], n))
            results = [dict(row) for row in tx.fetchall()]
            res = {}
            res['results'] = results
            res['totalRecords'] = length
            res['startIndex'] = var['startIndex']
            res['label'] = queue['name']
            res['id'] = queue['id']
            res['locked'] = queue['locked']
            res['queue_position'] = pos
            res['snapshot_id'] = snapshot_id
            return res

        d.addCallback(lambda queue: process(self, queue))
        return d

# get_queue_ids

    def get_queue_ids(self, args):
        var = {
            'startIndex': int(args['startIndex'])
        }
        rowsPerPage = int(args['rowsPerPage'])
        pid = args['id']
        d = self.get_queue_metadata(pid)

        @dbpooled
        def process(tx, self, queue):
            length = queue['length']
            if var['startIndex'] > length - 1:
                var['startIndex'] = int(
                    (length - 1) / rowsPerPage) * rowsPerPage
            var['startIndex'] = max(var['startIndex'], 0)
            n = min(rowsPerPage, length - var['startIndex'])
            query = ''' SELECT snapshot_id
                        FROM queue_names
                        WHERE id = ?'''
            tx.execute(query, (queue['id'],))
            snapshot_id = tx.fetchone()[0]
            query = '''SELECT songid FROM queue_data
				WHERE queue_id = ? AND track_num >= ?
				ORDER BY track_num LIMIT ?'''
            tx.execute(query, (pid, var['startIndex'], n))
            results = [row[0] for row in tx.fetchall()]
            res = {}
            res['totalRecords'] = length
            res['results'] = results
            res['id'] = pid
            res['snapshot_id'] = snapshot_id
            return res

        d.addCallback(lambda queue: process(self, queue))
        return d

# set_queue

    def set_queue(self, args):
        return self._set_queue(args['id'])

    def _set_queue(self, pid):

        dlist = []
        dlist.append(self.get_queue_metadata())
        dlist.append(self.get_queue_metadata(pid))
        d = defer.DeferredList(dlist)

        def process(results):
            failure = False
            for r in results:
                if not r[0]:
                    logError(r[1])
                    failure = True
            if failure:
                return
            queue_now = results[0][1]
            queue_new = results[1][1]

            @database_serialised
            @dbpooled
            def update(tx, self, pid):
                query = '''UPDATE queue_names SET playing = 0'''
                tx.execute(query)
                query = '''UPDATE queue_names SET playing = 1 WHERE id = ?'''
                tx.execute(query, (pid,))

            def process1(result):
                self.WS_queue_position(pid, queue_new['position'])
                return self.WS_queue(pid)

            def process2(result):
                return self.reload()
            if queue_now['id'] != pid:
                d = update(self, pid)
                d.addCallback(process1)
                d.addCallback(process2)
                return d
        d.addCallback(process)
        return d

# set_queue_pos

    def set_queue_pos(self, args):
        n = args['position']
        d = self.get_queue_metadata()

        def process(queue):
            if queue['position'] != n:
                return self.reload(n, play=True, keep_state=False)
            else:
                return self.mpd.play()
        d.addCallback(process)
        return d

# prev_track

    def prev_track(self, *args):
        d = self.get_queue_metadata()

        def process(queue):
            return self.reload(queue['position'] - 1)
        d.addCallback(process)
        return d

# next_track

    @mpd_check_connected(None)
    def next_track(self, *args):
        return self.mpd.next_track()

# play_pause
    @mpd_check_connected(None)
    def play_pause(self, *args):
        return self.mpd.play_pause()

# stop

    @mpd_check_connected(None)
    def stop(self, *args):
        return self.mpd.stop()

# jump

    @mpd_check_connected(None)
    def jump(self, args):
        return self.mpd.jump(args['position'])

# set_main_volume

    @mpd_check_connected(None)
    def set_main_volume(self, args):
        return self.mpd.set_main_volume(args['volume'])

# mute

    @mpd_check_connected(None)
    def mute(self, args={}, startup=False, info_only=False, set_vol=None):

        if set_vol != None:
            set_vol = int(set_vol)
            if set_vol == 0:
                return
            else:
                self.objects['config'].set('dbplayer_vol', set_vol)
                self.objects['config'].set('dbplayer_mute', 0)
                return self.WS_mute(0)

        def process(status):

            if not status:
                status = {}

            device_vol = int(status.get('volume', -1))
            saved_vol = self.objects['config'].get('dbplayer_vol')
            mute = self.objects['config'].get('dbplayer_mute')

            if startup:
                vol = saved_vol
            elif info_only:
                vol = saved_vol if mute else device_vol
            else:
                mute = 1 - mute
                vol = device_vol if mute else saved_vol
                self.objects['config'].set('dbplayer_vol', vol)
                self.objects['config'].set('dbplayer_mute', mute)

            return vol, mute

        def mpd(results):
            vol, mute = results
            self.WS_mute(mute)
            if mute:
                return self.mpd.set_main_volume(0)
            else:
                return self.mpd.set_main_volume(vol)

        if startup:
            d = defer.Deferred()
            d.callback(None)
        else:
            d = self.mpd.status()

        d.addCallback(process)

        if not info_only:
            d.addCallback(mpd)

        return d


# queue_clear

    def queue_clear(self, args):
        pid = args['id']
        d = self.get_queue_metadata(pid)

        def process(queue):
            if queue['locked']:
                return

            @database_serialised
            @dbpooled
            def clear(tx, self, pid):
                query = '''DELETE FROM queue_data where queue_id = ?'''
                tx.execute(query, (pid,))

            def process1(result):
                return self.set_position(-1, pid)

            def process2(result):
                self.WS_queue_contents(pid)
                return self.get_queue_metadata()

            def process3(result):
                if result['id'] == pid:
                    return self.reload()
            d = clear(self, pid)
            d.addCallback(process1)
            d.addCallback(process2)
            d.addCallback(process3)
            d.addCallback(lambda _: self.update_snapshot_id(pid))
            return d
        d.addCallback(process)
        return d

# move_queue_rows

    @snapshot
    def move_queue_rows(self, args):
        return self._move_queue_rows(args)

    def _move_queue_rows(self, args):
        pid = args['id']
        d = self.get_queue_metadata(pid)

        def process(queue):
            if queue['locked']:
                self.WS_queue_contents(pid)
                return

            @database_serialised
            @dbpooled
            def move(tx, self):
                query = '''	CREATE TEMP TABLE tmp_data
						    (pos INTEGER PRIMARY KEY ASC,
                            songid INTEGER, track_num INTEGER)'''
                tx.execute(query)
                query = ''' SELECT songid, track_num
                            FROM queue_data
                            WHERE queue_id = ?
                            AND track_num IN (''' + ",".join(
                    "?" * len(args['indices'])) + ''')
                            ORDER BY track_num'''
                parameters = tuple([pid] + args['indices'])
                tx.execute(query, parameters)
                rows = [(row[0], row[1]) for row in tx.fetchall()]
                query = ''' DELETE FROM queue_data
                            WHERE queue_id = ?
                            AND track_num IN (''' + ",".join(
                    "?" * len(args['indices'])) + ''')'''
                parameters = tuple([pid] + args['indices'])
                tx.execute(query, parameters)
                query = ''' INSERT INTO tmp_data (songid, track_num)
                            SELECT songid, track_num
                            FROM queue_data
                            WHERE queue_id = ?
                            AND track_num < ?
                            ORDER BY track_num'''
                tx.execute(query, (pid, args['dest']))
                query = ''' INSERT INTO tmp_data (songid, track_num)
                            VALUES(?,?)'''
                tx.executemany(query, rows)
                query = ''' INSERT INTO tmp_data (songid, track_num)
                            SELECT songid, track_num
                            FROM queue_data
                            WHERE queue_id = ?
                            AND track_num >= ?
                            ORDER BY track_num'''
                tx.execute(query, (pid, args['dest']))
                query = ''' SELECT pos - 1
                            FROM tmp_data
                            WHERE track_num = ?'''
                tx.execute(query, (queue['position'],))
                position = tx.fetchone()[0]
                query = ''' DELETE FROM queue_data
                            WHERE queue_id = ?'''
                tx.execute(query, (pid,))
                query = ''' INSERT INTO queue_data
                            (queue_id, songid, track_num)
                            SELECT ?, songid, pos-1
                            FROM tmp_data
                            ORDER BY pos'''
                tx.execute(query, (pid,))
                query = '''DROP TABLE tmp_data'''
                tx.execute(query)
                return position

            def set_position(position):
                return self.set_position(position, pid)

            def queue_contents(result):
                self.WS_queue_contents(pid)
                if queue['playing']:
                    return self.reload()

            d = move(self)
            d.addCallback(set_position)
            d.addCallback(queue_contents)
            d.addCallback(lambda _: pid)
            return d

        d.addCallback(process)
        return d

# transfer_queue_rows

    def transfer_queue_rows(self, args):
        pid = args['id']
        s_pid = args['startId']
        dlist = []
        dlist.append(self.get_queue_metadata(pid))
        dlist.append(self.get_queue_metadata(s_pid))
        dlist.append(self.check_snapshot_id(pid, args['snapshot_id']))
        dlist.append(self.check_snapshot_id(s_pid, args['source_snapshot_id']))
        d = defer.DeferredList(dlist)

        def process(results):

            failure = False
            for r in results:
                if not r[0]:
                    logError(r[1])
                    failure = True
            if failure:
                return

            try:
                passed, res = results[2][1]
                if not passed:
                    return res
                passed, res = results[3][1]
                if not passed:
                    res['status'] = 'ERROR'
                    return res
            except:
                log.exception('Problem in transfer_queue_rows')
                res = {}
                res['status'] = 'ERROR'
                return res

            queue = results[0][1]
            s_queue = results[1][1]
            if queue['locked']:
                self.WS_queue_contents(pid)
                return

            @database_serialised
            @dbpooled
            def process1(tx, self, pid, s_pid, s_locked, indices, dest):
                query = '''CREATE TEMP TABLE tmp_data (pos INTEGER PRIMARY KEY ASC, songid INTEGER)'''
                tx.execute(query)
                query = '''INSERT INTO tmp_data (songid) SELECT songid
					   FROM queue_data WHERE queue_id = ? AND track_num < ?
					   ORDER BY track_num'''
                tx.execute(query, (pid, dest))
                query = '''INSERT INTO tmp_data (songid) SELECT songid
					   FROM queue_data WHERE queue_id = ? AND track_num IN
					   (''' + ",".join("?" * len(indices)) + ''')
					   ORDER BY track_num'''
                params = [s_pid]
                params += indices
                params = tuple(params)
                tx.execute(query, params)
                query = '''INSERT INTO tmp_data (songid) SELECT songid
					   FROM queue_data WHERE queue_id = ? AND track_num >=?
					   ORDER BY track_num'''
                tx.execute(query, (pid, dest))
                query = '''DELETE FROM queue_data WHERE queue_id = ?'''
                tx.execute(query, (pid,))
                query = '''INSERT INTO queue_data (queue_id, songid, track_num)
					   SELECT ?, songid, pos-1 FROM tmp_data'''
                tx.execute(query, (pid,))
                if not s_locked:
                    query = '''DELETE FROM tmp_data'''
                    tx.execute(query)
                    query = '''DELETE FROM queue_data WHERE queue_id = ? AND track_num IN
						   (''' + ",".join("?" * len(indices)) + ''')'''
                    params = [s_pid]
                    params += indices
                    params = tuple(params)
                    tx.execute(query, params)
                    query = '''INSERT INTO tmp_data (songid) SELECT songid
						   FROM queue_data WHERE queue_id = ?
						   ORDER BY track_num'''
                    tx.execute(query, (s_pid,))
                    query = '''DELETE FROM queue_data WHERE queue_id = ?'''
                    tx.execute(query, (s_pid,))
                    query = '''INSERT INTO queue_data (queue_id, songid, track_num)
						   SELECT ?, songid, pos-1 FROM tmp_data'''
                    tx.execute(query, (s_pid,))
                query = '''DROP TABLE tmp_data'''
                tx.execute(query)

            def process2(result):
                if queue['position'] >= args['dest']:
                    return self.set_position(queue['position'] + len(args['indices']), pid)

            def process3(result):
                if not s_queue['locked']:
                    position = s_queue['position']
                    for index in args['indices']:
                        if index <= s_queue['position']:
                            position -= 1
                    position = max(0, position)
                    return self.set_position(position, s_pid)

            def process4(result):
                self.WS_queue_contents(pid)
                if not s_queue['locked']:
                    self.WS_queue_contents(s_pid)
                if queue['playing']:
                    return self.reload()
                if s_queue['playing'] and not s_queue['locked']:
                    return self.reload()
            d = process1(
                self,
                pid,
                s_pid,
                s_queue['locked'],
                args['indices'],
                args['dest'])
            d.addCallback(process2)
            d.addCallback(process3)
            d.addCallback(process4)
            d.addCallback(lambda _: self.update_snapshot_id(s_pid))
            d.addCallback(lambda _: self.update_snapshot_id(pid))
            return d
        d.addCallback(process)
        return d

# delete_queue_rows

    @snapshot
    def delete_queue_rows(self, args):
        pid = args['id']
        indices = args['indices']
        if not indices:
            return
        var = {
            'rload': 0,
        }
        d = self.get_queue_metadata(pid)

        def process(queue):
            if queue['locked']:
                self.WS_queue_contents(pid)
                return
            var['length'] = queue['length']
            if not var['length']:
                return
            var['pos'] = queue['position']

            @database_serialised
            @dbpooled
            def delete(tx, self, pid, indices, loaded_positions):
                def execute(i):
                    query = '''DELETE FROM queue_data WHERE queue_id = ?
						AND track_num = ?'''
                    tx.execute(query, (pid, i))
                    query = '''UPDATE queue_data SET track_num = track_num - 1
						WHERE queue_id = ? AND track_num > ?'''
                    tx.execute(query, (pid, i))
                for index in indices:
                    execute(index)
                    var['length'] -= 1
                    if var['pos'] > index:
                        var['pos'] -= 1
                    if queue['playing']:
                        if index in loaded_positions:
                            var['rload'] = 1

            d = delete(self, pid, indices, self.loaded_positions[:])

            def post_process1(result):
                if queue['playing']:
                    if not var['rload']:
                        for index in indices:
                            for i in range(len(self.loaded_positions)):
                                if self.loaded_positions[i] > index:
                                    self.loaded_positions[i] -= 1
                if var['pos'] > var['length'] - 1:
                    var['pos'] = var['length'] - 1
                if var['pos'] < 0:
                    var['pos'] = 0
                return self.set_position(var['pos'], pid)

            def post_process2(result):
                self.WS_queue_contents(pid)
                if var['rload']:
                    return self.reload()
            d.addCallback(post_process1)
            d.addCallback(post_process2)
            d.addCallback(lambda _: pid)
            return d
        d.addCallback(process)
        return d

# add_container

    def add_container(self, args):
        var = {}
        var['length'] = 0
        var['cancel'] = False
        if 'name' in args.keys():
            d = self.add_queue(args)
        else:
            d = self.sanitised_pid(args['dest_id'])

        def process1(pid):
            var['pid'] = pid
            if 'name' in args.keys() and pid is None:
                var['cancel'] = True
                return
            if 'add_and_play' in args.keys() and self.mpd_status != 'play':
                return self._set_queue(pid)

        def process2(result):
            if var['cancel']:
                return
            if 'clear' in args.keys():
                if args['clear']:
                    return self.queue_clear({'id': var['pid']})

        def process3(result):
            if var['cancel']:
                return
            return self.get_queue_metadata(var['pid'])

        def process4(queue):
            if var['cancel']:
                return
            var['queue'] = queue
            if args['data_type'] == 'album':
                query = '''SELECT song.id FROM song WHERE discid = ?'''
            elif args['data_type'] == 'queue':
                query = '''	SELECT songid FROM queue_data
							WHERE queue_id = ?'''
            else:
                query = '''	SELECT songid FROM playlist_data
							WHERE playlistid = ? AND type = "d"'''
            if 'indices' in args.keys():
                stub = '''	AND track_num IN (''' + ",".join("?" * len(args['indices'])) + ''')
							ORDER BY track_num'''
                parameters = tuple([args['container_id']] + args['indices'])
            else:
                stub = '''	ORDER BY track_num'''
                parameters = (args['container_id'],)
            return self.dbpool.fetchall_list(query + stub, parameters)

        def process5(ids):
            if var['cancel']:
                return
            var['count'] = len(ids)

            @database_serialised
            @dbpooled
            def execute(tx, self, pid, ids, position):
                for n, songid in enumerate(ids):
                    query = '''INSERT INTO queue_data (queue_id, songid, track_num) VALUES (?,?,?)'''
                    tx.execute(query, (pid, songid, n + position))
            return execute(self, var['pid'], ids, var['queue']['length'])

        def process6(result):
            if var['cancel']:
                return
            if 'play_next' in args.keys():
                if args['play_next']:
                    return self._move_queue_rows({
                        'id': var['pid'],
                        'dest': var['queue']['position'] + 1,
                        'indices':
                        list(
                            range(var['queue']['length'],
                                  var['queue']['length'] + var['count']))
                    })
            self.WS_queue_contents(var['pid'])
            if 'add_and_play' in args.keys() or 'play_now' in args.keys():
                if args['add_and_play'] or args['play_now']:
                    if self.mpd_status != 'play' or args['play_now']:
                        return self.reload(var['queue']['length'], play=True, keep_state=False)
                    if var['queue']['playing'] and len(self.loaded_positions) == 1:
                        return self.reload(var['queue']['length'] - 1, play=True, keep_state=False)

        def process7(result):
            if not var['cancel']:
                return self.update_snapshot_id(var['pid'])
        d.addCallback(process1)
        d.addCallback(process2)
        d.addCallback(process3)
        d.addCallback(process4)
        d.addCallback(process5)
        d.addCallback(process6)
        d.addCallback(process7)
        return d

# add_track

    def add_track(self, args):
        var = {
            'length': 0
        }
        d = self.sanitised_pid(args['id'])

        def process1(pid):
            var['pid'] = pid
            if self.mpd_status != 'play':
                return self._set_queue(pid)

        def process2(result):
            return self.get_queue_metadata(var['pid'])

        def process3(queue):
            var['queue'] = queue

            @database_serialised
            @dbpooled
            def execute(tx, self, pid, songid, position):
                query = '''INSERT INTO queue_data (queue_id, songid, track_num) VALUES (?,?,?)'''
                tx.execute(query, (pid, songid, position))
            return execute(self, var['pid'], args['song_id'], var['queue']['length'])

        def process4(result):
            self.WS_queue_contents(var['pid'])
            if args['add_and_play']:
                if self.mpd_status != 'play':
                    return self.reload(var['queue']['length'], play=True, keep_state=False)
                if var['queue']['playing'] and len(self.loaded_positions) == 1:
                    return self.reload(var['queue']['length'] - 1, play=True, keep_state=False)
        d.addCallback(process1)
        d.addCallback(process2)
        d.addCallback(process3)
        d.addCallback(process4)
        d.addCallback(lambda _: self.update_snapshot_id(var['pid']))
        return d

# add_queue

    def add_queue(self, args):

        var = {}
        var['pid'] = None

        @database_serialised
        @dbpooled
        def add(tx, self, queue):
            try:
                query = '''INSERT INTO queue_names (name, position, playing) VALUES (?, -1, 0)'''
                tx.execute(query, (queue,))
                query = '''SELECT id FROM queue_names WHERE name = ? ORDER BY id'''
                tx.execute(query, (queue,))
                var['pid'] = tx.fetchall()[-1]['id']

            except:
                log.exception('problem in add_queue')

        def after1(result):
            if var['pid']:
                return self.WS_queues()

        def after2(result):
            return var['pid']

        d = add(self, args['name'])
        d.addCallback(after1)
        d.addCallback(after2)
        return d

# delete_queue

    def delete_queue(self, args):

        pid = args['id']
        d = self.get_queue_metadata(pid)

        def process(queue):
            if queue['locked'] or queue['system']:
                return

            @database_serialised
            @dbpooled
            def delete(tx, self, pid, playing):
                query = '''DELETE FROM queue_names WHERE id = ?'''
                tx.execute(query, (pid,))
                query = '''DELETE FROM queue_data WHERE queue_id = ?'''
                tx.execute(query, (pid,))
                if playing:
                    query = '''UPDATE queue_names SET playing = 1 WHERE system = 1'''
                    tx.execute(query)
                    query = '''SELECT id FROM queue_names WHERE system = 1'''
                    tx.execute(query)
                    return tx.fetchone()['id']

            def after1(pid):
                if queue['playing']:
                    return self.WS_queue(pid)

            def after2(result):
                if queue['playing']:
                    return self.reload(-1, keep_state=False)

            def after3(result):
                return self.WS_queues(deleted_pid=pid)
            d1 = delete(self, pid, queue['playing'])
            d1.addCallback(after1)
            d1.addCallback(after2)
            d1.addCallback(after3)
            return d1
        d.addCallback(process)
        return d

# rename_queue

    def rename_queue(self, args):

        d = self.get_queue_metadata(args['id'])

        def process(queue):
            if queue['locked'] or queue['system']:
                return

            @database_serialised
            @dbpooled
            def rename(tx, self, name, pid):
                query = '''UPDATE queue_names SET name = ? WHERE id = ?'''
                tx.execute(query, (name, pid))

            def after(result):
                return self.WS_queues()
            d1 = rename(self, args['name'], args['id'])
            d1.addCallback(after)
            return d1
        d.addCallback(process)
        return d

# add_all_to_queue

    def add_all_to_queue(self, args):

        d = self.get_queue_metadata(args['id'])

        def process(queue):
            if queue['locked']:
                return

            @database_serialised
            @dbpooled
            def addAll(tx, self, pid):
                query = '''SELECT COUNT(*) FROM queue_data WHERE queue_id = ?'''
                tx.execute(query, (pid,))
                count = tx.fetchone()[0]
                query = '''CREATE TEMP TABLE tmp_song
						(pos INTEGER PRIMARY KEY ASC, id INTEGER)'''
                tx.execute(query)
                query = '''INSERT INTO tmp_song (id) SELECT id FROM song ORDER BY id'''
                tx.execute(query)
                query = '''INSERT INTO queue_data (queue_id, songid, track_num)
					SELECT ?, id, pos-1+? FROM tmp_song'''
                tx.execute(query, (pid, count))
                query = '''DROP TABLE tmp_song'''
                tx.execute(query)

            def after(result):
                return self.WS_queue_contents(args['id'])
            d = addAll(self, args['id'])
            d.addCallback(after)
            d.addCallback(lambda _: self.update_snapshot_id(args['id']))
            return d
        d.addCallback(process)
        return d

# lock_queue

    @authenticated
    def lock_queue(self, args):

        @database_serialised
        @dbpooled
        def lock(tx, self, locked, pid):
            query = '''UPDATE queue_names SET locked = ? WHERE id = ?'''
            tx.execute(query, (locked, pid))

        def after(result):
            return self.WS_queues()
        d = lock(self, args['locked'], args['id'])
        d.addCallback(after)
        return d

# queue_shuffle

    def queue_shuffle(self, args):
        pid = args['id']
        d = self.get_queue_metadata(pid)

        def process(queue):
            if queue['locked']:
                return
            if queue['playing']:
                d = self.stop()
            else:
                d = defer.Deferred()
                d.callback(0)

            def process1(results):

                @database_serialised
                @dbpooled
                def shuffle(tx, self, pid):
                    query = '''CREATE TEMP TABLE tmp_song
							(pos INTEGER PRIMARY KEY ASC, id INTEGER)'''
                    tx.execute(query)
                    query = '''INSERT INTO tmp_song (id) SELECT songid FROM queue_data
						WHERE queue_id = ? ORDER BY RANDOM()'''
                    tx.execute(query, (pid,))
                    query = '''DELETE FROM queue_data WHERE queue_id = ?'''
                    tx.execute(query, (pid,))
                    query = '''INSERT INTO queue_data (queue_id, songid, track_num)
						SELECT ?, id, pos-1 FROM tmp_song'''
                    tx.execute(query, (pid,))
                    query = '''DROP TABLE tmp_song'''
                    tx.execute(query)

                return shuffle(self, pid)

            def process2(result):
                return self.set_position(0, pid)

            def process3(result):
                self.WS_queue_contents(pid)

            def process4(result):
                if queue['playing']:
                    if self.mpd_status == 'play':
                        return self.reload(0, play=True, keep_state=False)
                    return self.reload()
            d.addCallback(process1)
            d.addCallback(process2)
            d.addCallback(process3)
            d.addCallback(process4)
            d.addCallback(lambda _: self.update_snapshot_id(pid))
            return d
        d.addCallback(process)
        return d

# copy_to_clipboard

    @database_serialised
    @dbpooled
    def copy_to_clipboard(tx, self, args):
        query = '''DELETE FROM clipboard_data WHERE clientid = ?'''
        tx.execute(query, (args['client_id'],))
        query = '''CREATE TEMP TABLE tmp_data (pos INTEGER PRIMARY KEY ASC, songid INTEGER)'''
        tx.execute(query)
        query = '''INSERT INTO tmp_data (songid) SELECT songid
			   FROM queue_data WHERE queue_id = ? AND track_num IN
			   (''' + ",".join("?" * len(args['indices'])) + ''')
			   ORDER BY track_num'''
        params = [args['id']]
        params += args['indices']
        params = tuple(params)
        tx.execute(query, params)
        query = '''INSERT INTO clipboard_data (clientid, songid, type, track_num)
			   SELECT ?, songid, ?, pos-1 FROM tmp_data'''
        tx.execute(query, (args['client_id'], 'd'))
        query = '''DROP TABLE tmp_data'''
        tx.execute(query)
        self.update_clipboard_access(tx, args['client_id'])

# add_to_clipboard - NOT YET IN USE! ASSUMES SAME ARGS AS copy_to_clipboard

    @database_serialised
    @dbpooled
    def add_to_clipboard(tx, self, args):
        query = '''CREATE TEMP TABLE tmp_data (pos INTEGER PRIMARY KEY ASC, songid INTEGER, type TEXT)'''
        tx.execute(query)
        query = '''INSERT INTO tmp_data (songid, type) SELECT songid, type FROM clipboard_data
			   WHERE clientid = ? ORDER BY track_num'''
        tx.execute(query, (args['client_id'],))
        query = '''INSERT INTO tmp_data (songid, type) SELECT songid, ?
			   FROM queue_data WHERE queue_id = ? AND track_num IN
			   (''' + ",".join("?" * len(args['indices'])) + ''')
			   ORDER BY track_num'''
        params = ['d', args['id']]
        params += args['indices']
        params = tuple(params)
        tx.execute(query, params)
        query = '''DELETE FROM clipboard_data WHERE clientid = ?'''
        tx.execute(query, (args['client_id'],))
        query = '''INSERT INTO clipboard_data (clientid, songid, type, track_num)
			   SELECT ?, songid, type, pos-1 FROM tmp_data'''
        tx.execute(query, (args['client_id'],))
        query = '''DROP TABLE tmp_data'''
        tx.execute(query)
        self.update_clipboard_access(tx, args['client_id'])

# paste_from_clipboard

    @snapshot
    def paste_from_clipboard(self, args):
        d = self.get_queue_metadata(args['id'])

        def process(queue):
            if queue['locked']:
                return
            var = {'clipboard_has_content': True}
            if args['dest'] == -1:
                args['dest'] = queue['length']

            @database_serialised
            @dbpooled
            def addSongs(tx, self, clientid, pid, dest):
                query = '''SELECT COUNT(*) FROM clipboard_data WHERE clientid = ?
					   AND type = "d"'''
                tx.execute(query, (clientid,))
                if not tx.fetchone()[0]:
                    var['clipboard_has_content'] = False
                    return 0
                query = '''CREATE TEMP TABLE tmp_data
					   (pos INTEGER PRIMARY KEY ASC, songid INTEGER)'''
                tx.execute(query)
                query = '''INSERT INTO tmp_data (songid) SELECT songid FROM queue_data
					   WHERE queue_id = ? AND track_num < ? ORDER BY track_num'''
                tx.execute(query, (pid, dest))
                query = '''INSERT INTO tmp_data (songid) SELECT songid FROM clipboard_data
					   WHERE clientid = ? AND type = "d" ORDER BY track_num'''
                tx.execute(query, (clientid,))
                query = '''INSERT INTO tmp_data (songid) SELECT songid FROM queue_data
					   WHERE queue_id = ? AND track_num >= ? ORDER BY track_num'''
                tx.execute(query, (pid, dest))
                query = '''DELETE FROM queue_data WHERE queue_id = ?'''
                tx.execute(query, (pid,))
                query = '''INSERT INTO queue_data (queue_id, songid, track_num)
					   SELECT ?, songid, pos-1 FROM tmp_data'''
                tx.execute(query, (pid,))
                query = '''DROP TABLE tmp_data'''
                tx.execute(query)
                self.update_clipboard_access(tx, args['client_id'])
                query = '''SELECT COUNT(*) FROM clipboard_data WHERE clientid = ?'''
                tx.execute(query, (clientid,))
                return tx.fetchone()[0]

            def after1(clipboard_length):
                if var['clipboard_has_content'] and queue['position'] >= args['dest']:
                    return self.set_position(queue['position'] + clipboard_length, args['id'])

            def after2(result):
                if var['clipboard_has_content']:
                    self.WS_queue_contents(args['id'])
                    if queue['playing']:
                        return self.reload()

            d = addSongs(self, args['client_id'], args['id'], args['dest'])
            d.addCallback(after1)
            d.addCallback(after2)
            d.addCallback(lambda _: args['id'])
            return d
        d.addCallback(process)
        return d

# remove_artist_or_album_from_queue

    def remove_artist_or_album_from_queue(self, args):
        d = self.get_queue_metadata(args['id'])

        def process(queue):
            if queue['locked']:
                return

            @database_serialised
            @dbpooled
            def remove(tx, self):
                field = 'artistid' if args['remove_artist'] else 'discid'
                query = '''SELECT song.{} FROM queue_data
					JOIN song ON (queue_data.songid = song.id)
					WHERE queue_data.queue_id = ?
					AND queue_data.track_num = ?'''.format(field)
                tx.execute(query, (args['id'], args['track_index'],))
                field_id = tx.fetchone()[0]
                query = '''SELECT COUNT(*) FROM	queue_data
					JOIN song ON (queue_data.songid = song.id)
					WHERE queue_data.queue_id = ?
					AND queue_data.track_num <= ?
					AND song.{} != ?'''.format(field)
                tx.execute(query, (args['id'], queue['position'], field_id))
                new_pos = int(tx.fetchone()[0]) - 1
                query = '''CREATE TEMP TABLE tmp_data (pos INTEGER PRIMARY KEY ASC, songid INTEGER)'''
                tx.execute(query)
                query = '''INSERT INTO tmp_data (songid)
					SELECT queue_data.songid FROM queue_data
					JOIN song ON (queue_data.songid = song.id)
					WHERE queue_data.queue_id = ?
					AND song.{} != ?
					ORDER BY queue_data.track_num'''.format(field)
                tx.execute(query, (args['id'], field_id))
                query = '''DELETE FROM queue_data WHERE queue_id = ?'''
                tx.execute(query, (args['id'],))
                query = '''INSERT INTO queue_data (queue_id, songid, track_num)
					SELECT ?, songid, pos-1 FROM tmp_data'''
                tx.execute(query, (args['id'],))
                query = '''DROP TABLE tmp_data'''
                tx.execute(query)
                return max(new_pos, 0)

            def after(new_pos):
                d = self.reload(new_pos) if queue[
                    'playing'] else self.set_position(new_pos, args['id'])

                def queue_contents(result):
                    return self.WS_queue_contents(args['id'])

                d.addCallback(queue_contents)
                return d

            d = remove(self)
            d.addCallback(after)
            d.addCallback(lambda _: self.update_snapshot_id(args['id']))
            return d

        d.addCallback(process)
        return d

# update_clipboard_access

# Call this only from within a @dbpooled function
# Supply the 'tx' and 'clientid' parameters

    def update_clipboard_access(self, tx, clientid):
        query = '''SELECT COUNT(*) FROM clipboard_access WHERE clientid =?'''
        tx.execute(query, (clientid,))
        if tx.fetchone()[0]:
            query = '''UPDATE clipboard_access SET time = ? WHERE clientid = ?'''
        else:
            query = '''INSERT INTO clipboard_access (time, clientid) VALUES (?, ?)'''
        tx.execute(query, (int(time.time()), clientid))
