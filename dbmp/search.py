# -*- coding: utf-8 -*-

from fuzzywuzzy import fuzz

from twisted.internet import defer

from .util import dbpooled
from .error import logError


class search(object):

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']
        self.searches = {}

    def artists(self, args):
        query_count1 = '''SELECT COUNT(*) FROM artist WHERE artist LIKE ?'''
        query_count2 = '''SELECT COUNT(*) FROM artist WHERE artist LIKE ? AND
			artist NOT IN (SELECT artist FROM artist WHERE artist LIKE ?)'''
        query_search1 = '''SELECT artist AS title, id AS itemid, artwork_update AS artURI FROM artist WHERE artist LIKE ?
			ORDER BY artist LIMIT ? OFFSET ?'''
        query_search2 = '''SELECT artist AS title, id AS itemid, artwork_update AS artURI FROM artist WHERE artist LIKE ?
			AND artist NOT IN (SELECT artist FROM artist WHERE artist LIKE ?)
			ORDER BY artist LIMIT ? OFFSET ?'''
        return self.search(True, args, query_count1, query_count2, query_search1, query_search2, 'artist')

    def albums(self, args):
        query_count1 = '''SELECT COUNT(*) FROM disc WHERE title LIKE ?'''
        query_count2 = '''SELECT COUNT(*) FROM disc WHERE title LIKE ? AND
			title NOT IN (SELECT title FROM disc WHERE title LIKE ?)'''
        query_search1 = '''SELECT title, disc.id AS itemid, artist, artistid, disc.artwork_update AS artURI
			FROM disc JOIN artist ON (artistid = artist.id) WHERE title LIKE ?
			ORDER BY title LIMIT ? OFFSET ?'''
        query_search2 = '''SELECT title, disc.id AS itemid, artist, artistid, disc.artwork_update AS artURI
			FROM disc JOIN artist ON (artistid = artist.id) WHERE title LIKE ?
			AND title NOT IN (SELECT title FROM disc WHERE title LIKE ?)
			ORDER BY title LIMIT ? OFFSET ?'''
        return self.search(True, args, query_count1, query_count2, query_search1, query_search2, 'album')

    def albums_recent(self, args):
        query_count1 = '''SELECT COUNT(*) FROM disc WHERE title LIKE ?'''
        query_count2 = '''SELECT COUNT(*) FROM disc WHERE title LIKE ? AND
			title NOT IN (SELECT title FROM disc WHERE title LIKE ?)'''
        query_search1 = '''SELECT title, disc.id AS itemid, artist, artistid, disc.artwork_update AS artURI
			FROM disc JOIN artist ON (artistid = artist.id) WHERE title LIKE ?
			ORDER BY disc.date_added DESC LIMIT ? OFFSET ?'''
        query_search2 = '''SELECT title, disc.id AS itemid, artist, artistid, disc.artwork_update AS artURI
			FROM disc JOIN artist ON (artistid = artist.id) WHERE title LIKE ?
			AND title NOT IN (SELECT title FROM disc WHERE title LIKE ?)
			ORDER BY disc.date_added DESC LIMIT ? OFFSET ?'''
        return self.search(True, args, query_count1, query_count2, query_search1, query_search2, 'album')

    def songs(self, args):
        query_count1 = '''SELECT COUNT(*) FROM song WHERE title LIKE ?'''
        query_count2 = '''SELECT COUNT(*) FROM song WHERE title LIKE ? AND
			title NOT IN (SELECT title FROM song WHERE title LIKE ?)'''
        query_search1 = '''SELECT song.title AS title, song.id AS itemid, artist, song.artistid AS artistid,
			disc.title AS album, discid AS albumid, disc.artwork_update AS artURI
			FROM song JOIN artist ON (song.artistid = artist.id) JOIN disc ON
			(discid = disc.id) WHERE song.title LIKE ? ORDER BY song.title LIMIT ? OFFSET ?'''
        query_search2 = '''SELECT song.title AS title, song.id AS itemid, artist, song.artistid AS artistid,
			disc.title AS album, discid AS albumid, disc.artwork_update AS artURI
			FROM song JOIN artist ON (song.artistid = artist.id) JOIN disc ON
			(discid = disc.id) WHERE song.title LIKE ? AND song.title NOT IN
			(SELECT title FROM song WHERE title LIKE ?)
			ORDER BY song.title LIMIT ? OFFSET ?'''
        return self.search(True, args, query_count1, query_count2, query_search1, query_search2, 'song')

    def album_from_artistid(self, args):
        query_count = '''SELECT COUNT(*) FROM disc WHERE artistid = ?'''
        query_search = '''SELECT title, id AS itemid, artwork_update AS artURI FROM disc WHERE artistid = ?
				ORDER BY title LIMIT ? OFFSET ?'''
        return self.search(False, args, query_count, query_search, 'itemid')

    def songs_from_albumid(self, args):
        if 'spotify' in str(args['id']):
            return self.objects['spotify'].search_songs_from_albumid(args)

        @dbpooled
        def get_metadata(tx, self):
            query = '''	SELECT artist, artistid, artist.artwork_update AS artwork_update, snapshot_id FROM disc
						JOIN artist ON (disc.artistid = artist.id)
						WHERE disc.id = ?'''
            tx.execute(query, (args['id'],))
            row = tx.fetchone()
            metadata = {}
            metadata['artist'] = row['artist']
            metadata['artistid'] = row['artistid']
            metadata['artistArtURI'] = '/get_cover?a={}&t={}'.format(
                str(row['artistid']), str(row['artwork_update'] or 0))
            metadata['editable'] = True
            metadata['snapshot_id'] = row['snapshot_id']
            return metadata

        def process(metadata):
            query_count = '''SELECT COUNT(*) FROM song WHERE discid = ?'''
            query_search = '''SELECT title, id AS itemid FROM song WHERE discid = ?
					ORDER BY track_num LIMIT ? OFFSET ?'''
            return self.search(False, args, query_count, query_search, None, metadata)
        d = get_metadata(self)
        d.addCallback(process)
        return d

    def songs_from_track_uri(self, args):

        if 'spotify' in str(args['id']):
            return self.objects['spotify'].search_songs_from_track_uri(args)

        @dbpooled
        def get_metadata(tx, self):
            search_term = args['id']
            query = '''	SELECT artist.artist AS artist, song.artistid AS artistid,
						disc.title AS album, song.discid AS albumid,
						artist.artwork_update AS artist_artwork_update,
						disc.artwork_update AS album_artwork_update,
						song.id AS songid
						FROM song JOIN disc ON (song.discid = disc.id)
						JOIN artist ON (song.artistid = artist.id)
						WHERE song.id = ?'''
            tx.execute(query, (search_term,))
            row = tx.fetchone()
            metadata = {}
            metadata['artist'] = row['artist']
            metadata['artistid'] = row['artistid']
            metadata[
                'artistArtURI'] = '/get_cover?a={}&t={}'.format(str(row['artistid']),
                                                                str(row['artist_artwork_update'] or 0))
            metadata['album'] = row['album']
            metadata['albumid'] = row['albumid']
            metadata[
                'albumArtURI'] = '/get_cover?i={}&t={}'.format(str(row['albumid']),
                                                               str(row['album_artwork_update'] or 0))
            metadata['trackid'] = row['songid']
            metadata['system'] = 'database'
            metadata['editable'] = True
            return metadata

        def process(metadata):
            query_count = '''SELECT COUNT(*) FROM song WHERE discid = ?'''
            query_search = '''SELECT title, id AS itemid FROM song WHERE discid = ?
					ORDER BY track_num LIMIT ? OFFSET ?'''
            return self.search(False, args, query_count, query_search, None, metadata, metadata['albumid'])
        d = get_metadata(self)
        d.addCallback(process)
        return d

    def artist_from_track_uri(self, args):

        if 'spotify' in str(args['id']):
            return self.objects['spotify'].search_artist_from_track_uri(args)

        @dbpooled
        def get_metadata(tx, self):
            search_term = args['id']
            query = '''	SELECT artist.artist AS artist, song.artistid AS artistid,
						artist.artwork_update AS artist_artwork_update
						FROM song JOIN artist ON (song.artistid = artist.id)
						WHERE song.id = ?'''
            tx.execute(query, (search_term,))
            row = tx.fetchone()
            metadata = {}
            metadata['artist'] = row['artist']
            metadata['artistid'] = row['artistid']
            metadata[
                'artistArtURI'] = '/get_cover?a={}&t={}'.format(str(row['artistid']),
                                                                str(row['artist_artwork_update'] or 0))
            metadata['system'] = 'database'
            return metadata

        def process(metadata):
            query_count = '''SELECT COUNT(*) FROM disc WHERE artistid = ?'''
            query_search = '''SELECT title, id AS itemid, artwork_update AS artURI FROM disc WHERE artistid = ?
					ORDER BY title LIMIT ? OFFSET ?'''
            return self.search(False, args, query_count, query_search, 'itemid', metadata, metadata['artistid'])
        d = get_metadata(self)
        d.addCallback(process)
        return d

    def find_track(self, args):
        query_count = '''SELECT COUNT(*) FROM song WHERE song.artistid = ? AND FUZZY_MATCH(?, song.title)'''
        query_search = '''SELECT song.title AS title, song.id AS itemid, artist, song.artistid AS artistid,
			disc.title AS album, discid AS albumid, disc.artwork_update AS artURI
			FROM song JOIN artist ON (song.artistid = artist.id) JOIN disc ON
			(discid = disc.id) WHERE song.artistid = ? AND FUZZY_MATCH(?, song.title) LIMIT ? OFFSET ?'''
        return self.search(False, args, query_count, query_search, 'albumid')

    def search_playlists(self, args):
        return self.objects['playlists'].search_playlists(args)

    def songs_from_playlistid(self, args):
        return self.objects['playlists'].search_songs_from_playlistid(args)

    def recommendations_from_track_uri(self, args):

        @dbpooled
        def get_data(tx, self):
            search_term = args['id']
            query = '''	SELECT artist.artist AS artist, song.title as track
						FROM song JOIN artist ON (song.artistid = artist.id)
						WHERE song.id = ?'''
            tx.execute(query, (search_term,))
            return dict(tx.fetchone())

        def process(data):
            args['database_seed'] = data
            return self.objects['spotify'].search_recommendations_from_track_uri(args)

        if 'spotify' in str(args['id']):
            return self.objects['spotify'].search_recommendations_from_track_uri(args)
        else:
            d = get_data(self)
            d.addCallback(process)
            return d

    def search(self, double, *args):
        sid = args[0]['sid']
        self.cancel(sid)
        self.objects['spotify'].search_cancel(sid)

        def canceller(d):
            d.callback('CANCELLED')

        d1 = defer.Deferred(canceller)
        self.searches[sid].append(d1)

        def process(result):
            self.searches[sid].remove(d1)
            d1.callback(result)

        def error(e):
            if not e.check(defer.AlreadyCalledError):
                logError(e)

        if double:
            d2 = self.double_search(*args)
        else:
            d2 = self.single_search(*args)
        d2.addCallback(process)
        d2.addErrback(error)
        return d1

    def cancel(self, sid):
        if sid not in self.searches.keys():
            self.searches[sid] = []

        for d in self.searches[sid]:
            d.cancel()

    def single_search(
            self,
            args,
            query_count,
            query_search,
            include_artwork=None,
            metadata=None,
            search_term=None):
        rowsPerPage = int(args['rowsPerPage'])
        search_term = search_term or args['id']
        var = {
            'startIndex': int(args['startIndex'])
        }
        if 'value' not in args.keys():
            d = self.dbpool.fetchone(query_count, (search_term,))
        else:
            d = self.fuzzy_match(
                query_count,
                (search_term,
                 args['value']),
                True)

        def process1(results):
            length = results[0]
            if var['startIndex'] > length - 1:
                var['startIndex'] = int(
                    (length - 1) / rowsPerPage) * rowsPerPage
            var['startIndex'] = max(var['startIndex'], 0)
            n = min(rowsPerPage, length - var['startIndex'])
            var['length'] = length
            if 'value' not in args.keys():
                return self.dbpool.fetchall_dict(query_search, (search_term, n, var['startIndex']))
            else:
                return self.fuzzy_match(query_search, (search_term, args['value'], n, var['startIndex']))

        def process2(results):
            res = {}
            res['totalRecords'] = var['length']
            res['startIndex'] = var['startIndex']
            res['id'] = args['id']
            if 'value' in args.keys():
                res['value'] = args['value']
            if include_artwork is not None:
                uri = '/get_cover?i={}&t={}'
                for n, item in enumerate(results):
                    item_id = str(item[include_artwork])
                    artwork = uri.format(item_id, str(item['artURI'] or 0))
                    results[n]['artURI'] = artwork
            res['results'] = results
            if metadata:
                res['metadata'] = metadata
            return res
        d.addCallback(process1)
        d.addCallback(process2)
        return d

    def double_search(
            self,
            args,
            query_count1,
            query_count2,
            query_search1,
            query_search2,
            search_type):
        rowsPerPage = int(args['rowsPerPage'])
        search_term = args['id']
        var = {}
        var['startIndex'] = int(args['startIndex'])
        var['length'] = 0
        if search_type == 'artist':
            uri = '/get_cover?a={}&t={}'
        else:
            uri = '/get_cover?i={}&t={}'
        dlist = []
        dlist.append(self.dbpool.fetchone(query_count1, (search_term + '%',)))
        if len(search_term) > 1:
            dlist.append(
                self.dbpool.fetchone(query_count2,
                                     ('%' + search_term + '%',
                                      search_term + '%')))
        d = defer.DeferredList(dlist)

        def process1(results):

            failure = False
            for r in results:
                if not r[0]:
                    logError(r[1])
                    failure = True
            if failure:
                return []

            length = 0
            n1 = 0
            n2 = 0
            for r in results:
                length += r[1][0]
            if var['startIndex'] > length - 1:
                var['startIndex'] = int(
                    (length - 1) / rowsPerPage) * rowsPerPage
            var['startIndex'] = max(var['startIndex'], 0)
            if var['startIndex'] < results[0][1][0]:
                n1 = min(rowsPerPage, results[0][1][0] - var['startIndex'])
            if n1 < rowsPerPage and n1 < length:
                n2 = min(rowsPerPage - n1, length - var['startIndex'] - n1)
            var['length'] = length
            dlist = []
            if n1:
                dlist.append(self.dbpool.fetchall_dict(
                    query_search1, (search_term + '%', n1, var['startIndex'])))
            if n2:
                dlist.append(
                    self.dbpool.fetchall_dict(
                        query_search2, ('%' + search_term + '%',
                                        search_term + '%', n2, var['startIndex'] + n1 - results[0][1][0])))
            d = defer.DeferredList(dlist)
            return d

        def process2(results):
            res = {}
            res['totalRecords'] = var['length']
            res['startIndex'] = var['startIndex']
            res['id'] = search_term
            res['results'] = []

            failure = False
            for r in results:
                if not r[0]:
                    logError(r[1])
                    failure = True
            if failure:
                return res

            for r in results:
                for n, item in enumerate(r[1]):
                    if search_type == 'song':
                        item_id = str(item['albumid'])
                    else:
                        item_id = str(item['itemid'])
                    artwork = uri.format(item_id, str(item['artURI'] or 0))
                    r[1][n]['artURI'] = artwork
                res['results'] += r[1]
            return res
        d.addCallback(process1)
        d.addCallback(process2)
        return d

    def fuzzy_match(self, query, args, fetchone=False):

        def fuzzy_match(arg1, arg2):
            ratio = fuzz.partial_ratio(arg1.lower(), arg2.lower())
            if ratio > 70:
                return True
            return False

        def execute(conn):

            conn.create_function("FUZZY_MATCH", 2, fuzzy_match)
            cur = conn.cursor()
            cur.execute(query, args)
            if fetchone:
                return cur.fetchone()
            l = []
            rows = cur.fetchall()
            for row in rows:
                item = dict(row)
                ratio = fuzz.partial_ratio(
                    args[1].lower(),
                    item['title'].lower())
                l.append([ratio, item])
            l.sort(key=lambda li: li[0], reverse=True)
            res = []
            for row in l:
                res.append(row[1])
            return res

        return self.dbpool.runWithConnection(execute)
