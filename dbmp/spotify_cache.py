# -*- coding: utf-8 -*-

from .util import dbpooled
from .util import spotify_cache_serialised
from .util import database_serialised
from twisted.internet import reactor
import time
from .logging_setup import getLogger
log = getLogger(__name__)


class spotify_cache(object):

    next_sync_task = None

    '''Abridged and updated TODO from which this module was created:

		- add field to db saying when cache last cleaned [DONE]

		- on app startup, run cache check which: [DONE]
			- cleans cache if it hasn't been cleaned for 24 hours
			- adds timer to clean when 24 hours since last clean has elapsed

		- on these cleans (which are only cleans), reconcile cache (add/remove) to: [DONE]
			- playlists
			- sonos queues
			- clipboard

		- new serialiser used for: [DONE]
			- 24 hour cache clean
			- adding to cache
			- returning playlist data

		- add to cache whenever we: [DONE]
			- populate a sonos queue by querying a sonos device
			- reconcile a sonos queue, but only if there's a mismatch (e.g. add from phone)
			- add spotify container or track to playlist from a spotify search
			- add spotify container or track to sonos queue from a spotify search
			- add spotify track to clipboard from a spotify search

		- use cache for: [DONE]
			- returning playlist data
			- adding spotify tracks to sonos queue

		- spotify.get_track_data: [DONE]
			- to be used only by spotify_cache
			- all other calls to spotify.get_track_data to be replaced by
			  new function in spotify_cache which:
				- updates cache by retrieving missing data via spotify.get_track_data
				- returns requested data using the now updated cache
			- update spotify.get_container_tracks so that it always updates the cache

	'''

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']

        # We call this 10 seconds after startup, to allow time for everything
        # to settle down. Ideally, by this stage, we will have populated
        # the sonos queues, if there's a sonos system on the network. It
        # shouldn't be the end of the world if the queues haven't been populated,
        # because we should be updating the cache whenever that happens,
        # but it would be wasteful to delete items from the cache by syncing before
        # the sonos queues have been populated and then have to add the items back
        # to the cache afterwards.

        reactor.callLater(10, self.sync_spotify_track_cache)

    def sync_spotify_track_cache(self):

        timestamp = self.objects['config'].get('spotify_track_cache_last_sync')

        if self.next_sync_task and not self.next_sync_task.called:
            self.next_sync_task.cancel()

        now = int(time.time())

        # 86400 seconds is 24 hours
        next_sync_time = timestamp + 86400 if timestamp else now

        if next_sync_time > now:
            self.next_sync_task = reactor.callLater(
                next_sync_time - now,
                self.sync_spotify_track_cache)

        else:
            self.next_sync_task = reactor.callLater(
                86400, self.sync_spotify_track_cache)
            self.objects['config'].set('spotify_track_cache_last_sync', now)
            self.update_spotify_track_cache()

    @spotify_cache_serialised
    def update_spotify_track_cache(self):

        @database_serialised
        @dbpooled
        def check_db(tx, self):

            query = '''	DELETE FROM spotify_track_cache
						WHERE songid NOT IN

						(SELECT songid FROM playlist_data
						WHERE type = "s" AND songid IS NOT NULL

						UNION ALL

						SELECT id AS songid FROM sonos_queue_data
						WHERE id LIKE 'spotify%'

						UNION ALL

						SELECT songid FROM clipboard_data
						WHERE type = "s" AND songid IS NOT NULL)'''

            tx.execute(query)

            query = '''	SELECT DISTINCT songid FROM

						(SELECT songid FROM playlist_data
						WHERE type = "s" AND songid NOT IN
						(SELECT songid FROM spotify_track_cache
						WHERE songid IS NOT NULL)

						UNION ALL

						SELECT id AS songid FROM sonos_queue_data
						WHERE id LIKE 'spotify%' AND songid NOT IN
						(SELECT songid FROM spotify_track_cache
						WHERE songid IS NOT NULL)

						UNION ALL

						SELECT songid FROM clipboard_data
						WHERE type = "s" AND songid NOT IN
						(SELECT songid FROM spotify_track_cache
						WHERE songid IS NOT NULL))'''

            tx.execute(query)
            return tx.fetchall()

        d = check_db(self)
        d.addCallback(self.get_spotify_data)
        d.addCallback(self.add_spotify_data)
        return d

    @spotify_cache_serialised
    def sync_spotify_cache_to_sonos_queue(self, groupid):

        @database_serialised
        @dbpooled
        def check_db(tx, self):

            query = '''	SELECT DISTINCT id AS songid FROM sonos_queue_data
						WHERE groupid = ? AND id LIKE 'spotify%'
						AND songid NOT IN
						(SELECT songid FROM spotify_track_cache
						WHERE songid IS NOT NULL)'''

            tx.execute(query, (groupid,))
            return tx.fetchall()

        d = check_db(self)
        d.addCallback(self.get_spotify_data)
        d.addCallback(self.add_spotify_data)
        return d

    @spotify_cache_serialised
    def get_track_data(self, tracks, client_id, fulldata=True):

        @database_serialised
        @dbpooled
        def get_missing_tracks(tx, self):

            query = '''	CREATE TEMP TABLE tmp_data
				   		(songid TEXT UNIQUE ON CONFLICT IGNORE)'''
            tx.execute(query)
            query = ''' INSERT INTO tmp_data (songid)
						VALUES (?)'''
            tx.executemany(query, [(track,) for track in tracks])
            query = '''	SELECT songid FROM tmp_data
						WHERE songid NOT IN
						(SELECT songid FROM spotify_track_cache
						WHERE songid IS NOT NULL)'''
            tx.execute(query)
            rows = tx.fetchall()
            query = '''	DROP TABLE tmp_data'''
            tx.execute(query)
            return rows

        def return_data(result=None):

            if not fulldata:
                return tracks

            @database_serialised
            @dbpooled
            def process(tx, self):
                query = '''	CREATE TEMP TABLE tmp_data
					   		(pos INTEGER PRIMARY KEY ASC, songid TEXT)'''
                tx.execute(query)
                query = ''' INSERT INTO tmp_data (songid)
							VALUES (?)'''
                tx.executemany(query, [(track,) for track in tracks])
                query = ''' SELECT artist, artistid, album, albumid, artURI, song, tmp_data.songid AS id,
							play_time FROM tmp_data
							JOIN spotify_track_cache
							ON (tmp_data.songid = spotify_track_cache.songid)
							ORDER BY pos'''
                tx.execute(query)
                rows = tx.fetchall()
                query = '''	DROP TABLE tmp_data'''
                tx.execute(query)
                return [dict(row) for row in rows]

            d = process(self)
            return d

        d = get_missing_tracks(self)
        d.addCallback(lambda result: self.get_spotify_data(result, client_id))
        d.addCallback(self.add_spotify_data)
        d.addCallback(return_data)
        return d

    @spotify_cache_serialised
    def add_track_data(self, tracks, fulldata=True):

        @database_serialised
        @dbpooled
        def get_missing_tracks(tx, self):

            query = '''	CREATE TEMP TABLE tmp_data
				   		(songid TEXT UNIQUE ON CONFLICT IGNORE)'''
            tx.execute(query)
            query = ''' INSERT INTO tmp_data (songid)
						VALUES (?)'''
            tx.executemany(query, [(track['id'],) for track in tracks])
            query = '''	SELECT songid FROM tmp_data
						WHERE songid NOT IN
						(SELECT songid FROM spotify_track_cache
						WHERE songid IS NOT NULL)'''
            tx.execute(query)
            rows = [row['songid'] for row in tx.fetchall()]
            query = '''	DROP TABLE tmp_data'''
            tx.execute(query)
            log.info('Adding data for {} rows'.format(len(rows)))
            return [track for track in tracks if track['id'] in rows]

        def return_data(result=None):

            if not fulldata:
                return [track['id'] for track in tracks]
            else:
                return tracks

        d = get_missing_tracks(self)
        d.addCallback(self.add_spotify_data)
        d.addCallback(return_data)
        return d

    def get_spotify_data(self, rows, client_id=None):

        if rows and len(rows):
            log.info('Getting data for {} rows'.format(len(rows)))
            return self.objects['spotify'].get_track_data(
                [row['songid'] for row in rows],
                client_id
            )

    def add_spotify_data(self, spotify_data):

        @database_serialised
        @dbpooled
        def process(tx, self):
            if spotify_data:
                query = ''' INSERT INTO spotify_track_cache (song, songid, artist,
							artistid, album, albumid, artURI, play_time)
							VALUES (:song, :id, :artist, :artistid, :album,
							:albumid, :artURI, :play_time)'''
                tx.executemany(query, spotify_data)

        return process(self)
