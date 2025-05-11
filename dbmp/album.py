# -*- coding: utf-8 -*-

from .logging_setup import getLogger
log = getLogger(__name__)

import time
from datetime import datetime
import weakref

from twisted.internet import reactor

from .util import database_serialised, dbpooled, authenticated, snapshot


class albums(object):

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']

    @authenticated
    @database_serialised
    @dbpooled
    def create_artist(tx, self, args):

        date = datetime.now().strftime('%Y-%m-%d')
        query = ''' SELECT artistid FROM disc WHERE id = ?'''
        tx.execute(query, (args['container_id'],))
        old_artist_id = tx.fetchone()[0]
        query = ''' SELECT MAX(id) AS id FROM artist'''
        tx.execute(query)
        row = tx.fetchone()
        artist_id = row['id'] + 1
        query = ''' INSERT INTO artist values (?, ?, ?, NULL)'''
        tx.execute(query, (artist_id, args['name'], date))
        query = ''' UPDATE disc SET artistid = ? WHERE id = ?'''
        tx.execute(query, (artist_id, args['container_id']))
        query = ''' UPDATE song SET artistid = ? WHERE discid = ?'''
        tx.execute(query, (artist_id, args['container_id']))
        res = {}
        res['artist'] = args['name']
        res['artistid'] = artist_id
        res['artistArtURI'] = '/get_cover?a={}&t={}'.format(
            str(artist_id), '0')
        res['artistid_deleted'] = self.delete_artist_if_unused(tx, old_artist_id)
        res['container_id'] = args['container_id']
        res['data_source'] = args['data_source']
        res['data_type'] = args['data_type']
        res['action'] = 'album_change'
        return res

    @authenticated
    def rename_artist(self, args):

        @database_serialised
        @dbpooled
        def rename_artist(tx, self):
            query = '''UPDATE artist SET artist = ? WHERE id = ?'''
            tx.execute(query, (args['name'], args['artistid']))
            return {'artistid' : args['artistid']}

        def remove_cover(result):
            self.objects['covers'].remove(result)
            res = {}
            res['artist'] = args['name']
            res['container_id'] = args['container_id']
            res['data_source'] = args['data_source']
            res['data_type'] = args['data_type']
            res['action'] = 'album_change'
            return res

        return rename_artist(self).addCallback(remove_cover)

    @database_serialised
    @dbpooled
    def search_artist(tx, self, args):

        query = ''' SELECT artist, id
                    FROM
                    (SELECT artist, id
                    FROM artist 
                    WHERE artist LIKE ?1
                    ORDER BY artist)
                    UNION ALL
                    SELECT artist, id
                    FROM
                    (SELECT artist, id
                    FROM artist
                    WHERE artist LIKE ?2
                    AND artist NOT LIKE ?1
                    ORDER BY artist)'''

        tx.execute(query, (args['term'] + '%', '%' + args['term'] + '%'))
        rows = tx.fetchall()
        res = {}
        res['artists'] = [row['artist'] for row in rows]
        res['artistids'] = [row['id'] for row in rows]
        return res

    @database_serialised
    @dbpooled
    def search_artist_albums(tx, self, args):

        query = ''' SELECT title, id
                    FROM disc
                    WHERE artistid = ?
                    AND id != ?
                    ORDER BY title'''

        tx.execute(query, (args['artistid'], args['container_id']))
        rows = tx.fetchall()
        res = {}
        res['albums'] = [row['title'] for row in rows]
        res['albumids'] = [row['id'] for row in rows]
        return res

    @authenticated
    @database_serialised
    @dbpooled
    def change_artist(tx, self, args):

        query = ''' SELECT artistid FROM disc WHERE id = ?'''
        tx.execute(query, (args['container_id'],))
        old_artistid = tx.fetchone()[0]
        query = ''' SELECT artist, artwork_update
                    FROM artist
                    WHERE id = ?'''
        tx.execute(query, (args['artistid'],))
        row = tx.fetchone()
        artist = row['artist']
        artwork_update = row['artwork_update']
        query = '''UPDATE disc SET artistid = ? WHERE id = ?'''
        tx.execute(query, (args['artistid'], args['container_id']))
        query = '''UPDATE song SET artistid = ? WHERE discid = ?'''
        tx.execute(query, (args['artistid'], args['container_id']))
        res = {}
        res['artist'] = artist
        res['artistid'] = args['artistid']
        res['artistArtURI'] = '/get_cover?a={}&t={}'.format(
            str(args['artistid']), str(artwork_update))
        res['artistid_deleted'] = self.delete_artist_if_unused(tx, old_artistid)
        res['container_id'] = args['container_id']
        res['data_source'] = args['data_source']
        res['data_type'] = args['data_type']
        res['action'] = 'album_change'
        return res

    # Call from within dbpooled function and provide tx
    # returns artistid if the artist was deleted, else None
    def delete_artist_if_unused(self, tx, artistid):
        query = '''SELECT COUNT(*) from disc WHERE artistid = ?'''
        tx.execute(query, (artistid,))
        keep_artist = tx.fetchone()[0]
        if not keep_artist:
            query = '''DELETE FROM artist WHERE id = ?'''
            tx.execute(query, (artistid,))
            reactor.callFromThread(self.objects['covers'].delete_cover,
                'artist', artistid)
        return None if keep_artist else artistid

    @authenticated
    @database_serialised
    @dbpooled
    def rename_tracks(tx, self, args):
        query = ''' SELECT COUNT(*) FROM song
                    WHERE discid = ?'''
        tx.execute(query, (args['container_id'],))
        count = tx.fetchone()[0]
        if count != len(args['track_names']):
            print(count)
            print(len(args['track_names']))
            return
        query = ''' UPDATE song SET title = ?
                    WHERE discid = ?
                    AND track_num = ?'''
        tx.executemany(query, [(track_name, args['container_id'],
            n) for n, track_name in enumerate(args['track_names'])])
        query = ''' SELECT title FROM song
                    WHERE discid = ?
                    ORDER BY track_num'''
        tx.execute(query, (args['container_id'],))
        return [item[0] for item in tx.fetchall()]        

    @authenticated
    @database_serialised
    def create_album(self, args):

        @snapshot
        @dbpooled
        def create_album(tx, self, args):

            date = datetime.now().strftime('%Y-%m-%d')
            query = ''' SELECT artistid FROM disc WHERE id = ?'''
            tx.execute(query, (args['container_id'],))
            artistid = tx.fetchone()[0]
            query = ''' SELECT MAX(id) AS id FROM disc'''
            tx.execute(query)
            row = tx.fetchone()
            albumid = row['id'] + 1
            query = ''' INSERT INTO disc values (?, ?, ?, NULL, NULL, ?, NULL, 1)'''
            tx.execute(query, (albumid, args['name'], artistid, date))
            args['move_to'] = albumid
            results = self._move_tracks_to_album(tx, args)
            return args['container_id'], results

        return create_album(self, args)

    @authenticated
    @database_serialised
    def move_tracks_to_album(self, args):

        @snapshot
        @dbpooled
        def move_tracks(tx, self, args):
            results = self._move_tracks_to_album(tx, args)
            return args['container_id'], results

        return move_tracks(self, args)

    def _move_tracks_to_album(self, tx, args):
        query = ''' SELECT COUNT(*) FROM song
                    WHERE discid = ?'''
        tx.execute(query, (args['move_to'],))
        n = tx.fetchone()[0]
        query = ''' UPDATE song SET discid = ?,
                    track_num = ?
                    WHERE discid = ?
                    AND track_num = ?'''
        tx.executemany(query, [(
            args['move_to'],
            n + i,
            args['container_id'],
            index
            ) for i, index in enumerate(args['indices'])])
        query = '''SELECT COUNT(*) FROM song WHERE discid = ?'''
        tx.execute(query, (args['container_id'],))
        album_empty = tx.fetchone()[0] == 0
        res = {}
        res['album_empty'] = album_empty
        if album_empty:
            query = '''SELECT artistid FROM disc WHERE id = ?'''
            tx.execute(query, (args['container_id'],))
            artistid = tx.fetchone()[0]
            query = '''DELETE FROM disc WHERE id = ?'''
            tx.execute(query, (args['container_id'],))
            reactor.callFromThread(self.objects['covers'].delete_cover,
                'album', args['container_id'])
            res['artistid_deleted'] = self.delete_artist_if_unused(tx, artistid)
            res['action'] = 'album_delete'
            res['container_id'] = args['container_id']
            res['data_source'] = args['data_source']
            res['data_type'] = args['data_type']
        else:
            query = ''' SELECT track_num FROM song
                        WHERE discid = ?
                        ORDER BY track_num'''
            tx.execute(query, (args['container_id'],))
            track_nums = [row[0] for row in tx.fetchall()]
            query = ''' UPDATE song SET track_num = ?
                        WHERE discid = ?
                        AND track_num = ?'''
            tx.executemany(query, [(
                n,
                args['container_id'],
                index
                ) for n, index in enumerate(track_nums)])
        return res

    @authenticated
    @database_serialised
    def merge_albums(self, args):

        results = {}
        results['merge_from'] = []

        @snapshot
        @dbpooled
        def merge_albums(tx, self, args):

            for albumid in args['merge_from']:
                query = ''' SELECT COUNT(*) FROM song
                            WHERE discid = ?'''
                tx.execute(query, (args['merge_to'],))
                n = tx.fetchone()[0]
                query = ''' UPDATE song SET discid = ?,
                            track_num = track_num + ?
                            WHERE discid = ?'''
                tx.execute(query, (args['merge_to'], n, albumid))
                query = '''DELETE FROM disc WHERE id = ?'''
                tx.execute(query, (albumid,))
                reactor.callFromThread(self.objects['covers'].delete_cover,
                    'album', albumid)
                res = {}
                res['container_id'] = albumid
                res['data_source'] = args['data_source']
                res['data_type'] = args['data_type']
                res['action'] = 'album_delete'
                results['merge_from'].append(res)

            return args['container_id'], results

        return merge_albums(self, args)

    @authenticated
    @database_serialised
    @dbpooled
    def rename_container(tx, self, args):
        query = '''UPDATE disc SET title = ? WHERE id = ?'''
        tx.execute(query, (args['name'], args['container_id']))
        return args['name']

    @authenticated
    @database_serialised
    def delete_container(self, args):

        var = {}

        @dbpooled
        def update_db(tx, self):
            query = '''SELECT artistid FROM disc WHERE id = ?'''
            tx.execute(query, (args['container_id'],))
            artistid = tx.fetchone()[0]
            query = '''SELECT id FROM song WHERE discid = ?'''
            tx.execute(query, (args['container_id'],))
            songids = [t[0] for t in tx.fetchall()]
            query = '''DELETE FROM disc WHERE id = ?'''
            tx.execute(query, (args['container_id'],))
            query = '''DELETE FROM song WHERE discid = ?'''
            tx.execute(query, (args['container_id'],))
            var['artistid'] = self.delete_artist_if_unused(tx, artistid)
            return songids

        def covers(dummy):
            self.objects['covers'].delete_cover('album', args['container_id'])
            res = {}
            res['artistid_deleted'] = var['artistid']
            res['container_id'] = args['container_id']
            res['data_source'] = args['data_source']
            res['data_type'] = args['data_type']
            res['action'] = 'album_delete'
            return res

        d = update_db(self)
        d.addCallback(self.objects['playlists']._delete_songids)
        d.addCallback(covers)
        return d

    @authenticated
    @database_serialised
    def delete_tracks_from_container(self, args):

        @snapshot
        @dbpooled
        def delete_tracks(tx, self, args):
            query = ''' DELETE FROM song WHERE discid = ? AND
						track_num IN (''' + ",".join("?" * len(args['tracks'])) + ''')
					'''
            parameters = tuple([args['container_id']] + args['tracks'])
            tx.execute(query, parameters)
            query = ''' SELECT id FROM song WHERE discid = ?
						ORDER BY track_num'''
            tx.execute(query, (args['container_id'],))
            query = ''' UPDATE song SET track_num = ? WHERE id = ?'''
            tx.executemany(query, [(n, s[0])
                           for n, s in enumerate(tx.fetchall())])
            return args['container_id']

        return delete_tracks(self, args)

    @database_serialised
    @dbpooled
    def copy_to_clipboard(tx, self, args):
        query = '''DELETE FROM clipboard_data WHERE clientid = ?'''
        tx.execute(query, (args['client_id'],))
        query = '''CREATE TEMP TABLE tmp_data (pos INTEGER PRIMARY KEY ASC, songid INTEGER)'''
        tx.execute(query)
        query = '''INSERT INTO tmp_data (songid) SELECT id
			   FROM song WHERE discid = ? AND track_num IN
			   (''' + ",".join("?" * len(args['indices'])) + ''')
			   ORDER BY track_num'''
        params = [args['container_id']]
        params += args['indices']
        params = tuple(params)
        tx.execute(query, params)
        query = '''INSERT INTO clipboard_data (clientid, songid, type, track_num)
			   SELECT ?, songid, ?, pos-1 FROM tmp_data'''
        tx.execute(query, (args['client_id'], 'd'))
        query = '''DROP TABLE tmp_data'''
        tx.execute(query)
        self.objects['db_player'].update_clipboard_access(
            tx, args['client_id'])

    @authenticated
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
						(pos INTEGER PRIMARY KEY ASC, songid INTEGER)'''
            tx.execute(query)
            query = '''	SELECT id FROM song
						WHERE discid = ? AND track_num IN (''' + ",".join("?" * len(indices)) + ''')
						ORDER BY track_num'''
            parameters = tuple([args['container_id']] + indices)
            tx.execute(query, parameters)
            tracks = [(row[0],) for row in tx.fetchall()]
            query = '''	INSERT INTO tmp_data (songid) SELECT id FROM song
						WHERE discid = ? AND track_num < ?
						AND track_num NOT IN (''' + ",".join("?" * len(indices)) + ''')
						ORDER BY track_num'''
            parameters = tuple([args['container_id'], dest] + indices)
            tx.execute(query, parameters)
            query = '''	INSERT INTO tmp_data (songid) VALUES(?)	'''
            tx.executemany(query, tracks)
            query = '''	INSERT INTO tmp_data (songid) SELECT id FROM song
						WHERE discid = ? AND track_num >= ?
						AND track_num NOT IN (''' + ",".join("?" * len(indices)) + ''')
						ORDER BY track_num'''
            tx.execute(query, parameters)
            query = '''	SELECT songid FROM tmp_data ORDER BY pos'''
            tx.execute(query)
            query = '''	UPDATE song SET track_num = ? WHERE id = ?'''
            parameters = [(n, s[0]) for n, s in enumerate(tx.fetchall())]
            tx.executemany(query, parameters)
            query = '''DROP TABLE tmp_data'''
            tx.execute(query)
            return args['container_id']

        return move_tracks(self, args)

    # These next two functions are required and used by
    # the @snapshot decorator

    @dbpooled
    def check_snapshot_id(tx, self, did, snapshot_id):
        query = '''SELECT snapshot_id FROM disc WHERE id = ?'''
        tx.execute(query, (did,))
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
            did, res = args
        else:
            did, res = args, {}
        snapshot_id = int(time.time() * 1000)
        query = '''UPDATE disc SET snapshot_id = ? WHERE id = ?'''
        tx.execute(query, (snapshot_id, did))
        res['status'] = 'SUCCESS'
        res['snapshot_id'] = snapshot_id
        return res
