# -*- coding: utf-8 -*-

from .config import SPOTIFY_CLIENT_ID as spotify_client_id
from .config import SPOTIFY_REDIRECT_URI as redirect
from .error import logError
from .util import ms_to_str
from .util import random_moves
from .util import httpRequest
from .util import cached
from .util import dbpooled
from .util import serialised, serialised2, database_serialised
from . import serialiser
from twisted.internet import defer
from twisted.internet import reactor
from fuzzywuzzy import fuzz
import functools
import json
import time
import urllib.parse
import random
from logging import DEBUG
from .logging_setup import getLogger
log = getLogger(__name__)
log.setLevel(DEBUG)


# This stores Spotify credentials for a browser client
# If a client does not have a requested credential, None
# is returned
class Client:
    def __init__(self, values=None):
        if values is None:
            values = {}
        self.__dict__.update(values)

    def __getattr__(self, key):
        # Called only if key is not found in the usual places
        return None

    def __setattr__(self, key, value):
        self.__dict__[key] = value


# This stores all the Clients. If a Client has no
# credentials, an empty Client is returned
class Clients:
    def __init__(self):
        self._clients = {}

    def any_client_id(self):
        keys = list(self._clients.keys())
        if len(keys):
            return keys[0]
        return None  # If no client_id is found

    def __getitem__(self, key):
        return self._clients.setdefault(key, Client())

    def __setitem__(self, key, values):
        self._clients[key] = Client(values)


class spotify(object):

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']
        self.serialise = serialiser.Serialiser('Spotify Serialiser').serialise
        self.serialise2 = serialiser.Serialiser(
            'Spotify HTTPRequest Serialiser').serialise
        self.third_serialiser = serialiser.Serialiser(
            'Spotify Third Serialiser')
        self.auth_requests = []
        self.clients = Clients()
        # self.spotify_searches is used by self.search_spotify, which is
        # used mainly for searches triggered by a user typing, to cancel any
        # existing such search. Subject to throttling within the client, each
        # new letter typed will trigger a new search. Cancellation needs to
        # be quick and responsive, so the deferred carrying out the search is
        # itself cancelled.
        self.spotify_searches = {}
        # self.active_searches is used (by the check_cancelled decorator and
        # by self.abort_searches) to cancel long running search ops that queue
        # multiple searches. Unlike cancellation by self.search_spotify, the
        # deferred currently performing a search is allowed to complete (that
        # shouldn't take long if the network is behaving) and only queued
        # searches are aborted. However, having coded cancellation into these
        # long running search ops, it isn't actually being used, because for
        # time being it seems better to allow the search to complete in the
        # background so that the cached result is available. This means it is
        # important for these long running searches not to delay other searches.
        self.active_searches = {}
        self.startup()
        # We call this 10 seconds after startup, to allow time for everything
        # to settle down
        reactor.callLater(10, self.clean_database)

    # See comment about self.active_searches above. When the decorator
    # is applied to a function within a method of the spotify class
    # inner(fn) is called as soon as execution of the
    # method reaches the point where the function is declared,
    # while wrapper(*args, **kwargs) is called when the
    # function is to be executed
    def check_cancelled(self, sid, searchid):

        if sid not in self.active_searches:
            self.active_searches[sid] = []
        if searchid not in self.active_searches[sid]:
            self.active_searches[sid].append(searchid)

        def inner(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                if searchid not in self.active_searches[sid]:
                    return 'CANCELLED'
                return fn(*args, **kwargs)

            wrapper.__wrapped__ = fn
            return wrapper

        return inner

    # This isn't currently being used.
    def abort_searches(self, args):
        self.active_searches[args['sid']] = []

    @database_serialised
    @serialised
    def add_sonos_queue_to_playlist(self, args):
        if 'name' in args.keys():
            fn = self.add_tracks_to_new_playlist
        else:
            fn = self.add_tracks_to_playlist
        return fn(args, get_fn=self.get_queue_segment)

    @serialised
    def add_to_playlist(self, args):

        if 'name' in args.keys():
            add = self.add_tracks_to_new_playlist
        else:
            add = self.add_tracks_to_playlist

        if args['data_source'] == 'spotify':
            if 'tracks' in args.keys():
                return add(args)
            else:
                return add(args, get_fn=self.get_container_tracks)
        else:
            if args['data_type'] == 'playlist':
                return add(args, get_fn=self.objects['playlists'].get_spotify_tracks)

    @defer.inlineCallbacks
    def add_tracks_to_playlist(self, args, get_fn=None):
        # NB We could (but we do not currently) check that the correct
        # snapshot_id was supplied
        playlist_id = args['dest_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}/tracks'.format(
            playlist_id)
        res = {}

        if 'clear' in args.keys() and args['clear']:
            yield self._clear_playlist({
                'client_id': args['client_id'],
                'container_id': args['dest_id']
            })

        def process(tracks):
            data = {}
            data['uris'] = tracks
            return self.post(args['client_id'], endpoint, None, data)

        if get_fn:
            fn_args = args
            while True:
                result = yield get_fn(fn_args)
                if result.get('tracks'):
                    outcome = yield process(result['tracks'])
                if result.get('var'):
                    fn_args = {'var': result['var']}
                else:
                    break

        else:
            while True:
                tracks = []
                while len(tracks) < 100 and len(args['tracks']):
                    track = args['tracks'].pop(0)
                    if 'spotify' in track:
                        tracks.append(track)
                if len(tracks):
                    outcome = yield process(tracks)
                else:
                    break

        if outcome and 'snapshot_id' in outcome.keys():
            res['snapshot_id'] = outcome['snapshot_id']
        return res

    @defer.inlineCallbacks
    def add_tracks_to_new_playlist(self, args, get_fn=None):

        client_id = args['client_id']
        user_id = self.clients[client_id].user_id

        if not user_id:
            return

        endpoint = 'https://api.spotify.com/v1/users/{0}/playlists'.format(
            user_id)

        result = yield self.post(
            client_id,
            endpoint,
            None,
            {
                'name': args['name'],
                'public': True
            }
        )

        if 'id' not in result.keys():
            return

        endpoint = 'https://api.spotify.com/v1/playlists/{0}/tracks'.format(
            result['id'])

        res = {}

        def process(tracks):
            data = {}
            data['uris'] = tracks
            return self.post(client_id, endpoint, None, data)

        if get_fn:
            fn_args = args
            while True:
                result = yield get_fn(fn_args)
                if result.get('tracks'):
                    outcome = yield process(result['tracks'])
                if result.get('var'):
                    fn_args = {'var': result['var']}
                else:
                    break

        else:
            while True:
                tracks = []
                while len(tracks) < 100 and len(args['tracks']):
                    track = args['tracks'].pop(0)
                    if 'spotify' in track:
                        tracks.append(track)
                if len(tracks):
                    outcome = yield process(tracks)
                else:
                    break

        if outcome and 'snapshot_id' in outcome.keys():
            res['snapshot_id'] = outcome['snapshot_id']
        return res

    def get_track_data(self, tracks, client_id=None):

        var = {}
        var['tracks'] = tracks
        data = []

        if not client_id:
            client_id = self.clients.any_client_id()

        def get():
            next_tracks = [track.split(':')[2]
                           for track in var['tracks'][0:50]]
            var['tracks'] = var['tracks'][50:]
            if len(next_tracks):
                params = {
                    'client_id': client_id,
                    'endpoint': 'https://api.spotify.com/v1/tracks',
                    'ids': ','.join(next_tracks)
                }
                d = self.search_spotify_id_cached(params)
                d.addCallback(after)
            else:
                d = defer.Deferred()
                d.callback(data)
            return d

        def item_builder(track):
            item = {}
            item['song'] = track['name']
            item['id'] = track['uri']
            item['artist'] = track['artists'][0]['name']
            item['artistid'] = track['artists'][0]['uri']
            item['album'] = track['album']['name']
            item['albumid'] = track['album']['uri']
            item['artURI'] = self.get_image_uri(
                track['album']['images'], 'albums')
            item['play_time'] = ms_to_str(
                track['duration_ms'],
                two_columns=True)
            return item

        def after(results=None):
            if results and 'tracks' in results.keys():
                for track in results['tracks']:
                    data.append(item_builder(track))
            return get()

        return after()

    @defer.inlineCallbacks
    def get_queue_segment(self, args):

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

        @dbpooled
        def get_from_db(tx, self):
            if not args['length']:
                query = '''	SELECT COUNT(*) FROM sonos_queue_data
                            WHERE groupid = ?'''
                tx.execute(query, (args['sonos_uid'],))
                args['length'] = tx.fetchone()[0]
                if not args['length']:
                    return []
            if 'indices' in args.keys():
                stub = '''AND track_num IN (''' + \
                    ",".join("?" * len(args['indices'])) + ''')'''
                params = tuple(
                    [args['sonos_uid'], start] + args['indices'])
                args['length'] = args['start']  # this will stop iteration
            else:
                stub = ''
                params = (args['sonos_uid'], start)
            query = '''	SELECT id, track_num FROM sonos_queue_data
                        WHERE groupid = ? AND track_num >= ?
                        {}
                        AND id LIKE "spotify%"
                        ORDER BY track_num LIMIT 100'''.format(stub)
            tx.execute(query, params)
            rows = tx.fetchall()
            if not rows:
                args['length'] = args['start']  # this will stop iteration
                return []
            else:
                args['start'] = rows[-1]['track_num'] + 1
            return [row['id'] for row in rows]

        tracks = yield get_from_db(self)
        result = {'tracks': tracks}
        if args['start'] < args['length']:
            result['var'] = args
        return result

    def get_container_tracks(self, args, fulldata=False):

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
        # been decorated to be an inlineCallback, so that
        # yield can be used to await the result of the deferred
        # returned by this method

        var = {
            'next': None,
            'client_id': args.get('client_id')
        }

        def return_results(items=[]):
            results = {'tracks': items}
            if var['next']:
                results['var'] = var
            return results

        if args.get('var'):
            endpoint = args['var']['next']
            params = None
            var = args['var']
            cached = var['cached']
            category = var['category']
            var['next'] = None

        else:
            category = args['container_id'].split(':')[1]
            cached = True
            # Spotify API change - is user not redundant?
            if category == 'user':
                user = args['container_id'].split(':')[2]
                playlist_id = args['container_id'].split(':')[4]
                endpoint = 'https://api.spotify.com/v1/users/{0}/playlists/{1}/tracks'.format(
                    user, playlist_id)
                params = None
                cached = False
            # Spotify API change - this is new
            elif category == 'playlist':
                endpoint = 'https://api.spotify.com/v1/playlists/{}/tracks'.format(
                    args['container_id'].split(':')[2])
                params = None
                cached = False
            elif category == 'album':
                endpoint = 'https://api.spotify.com/v1/albums/{}/tracks'.format(
                    args['container_id'].split(':')[2])
                params = {
                    'limit': 50  # This is the maximum, spotify default is 20
                }
            elif category == 'artistRecommendations':
                return self.get_recommendations(args, fulldata)
            elif category == 'trackRecommendations':
                return self.get_recommendations(args, fulldata)
            elif category == 'artistTopTracks':
                endpoint = 'https://api.spotify.com/v1/artists/{}/top-tracks'.format(
                    args['container_id'].split(':')[2])
                params = {'country': self.users[var['client_id']].country}
            else:
                log.warning('Category not recognised')
                return return_results()
            var['cached'] = cached
            var['category'] = category

        def get(endpoint, params=None):
            if not params:
                params = {}
            params['endpoint'] = endpoint
            params['client_id'] = var['client_id']
            return self.search_spotify_id(params, cached)

        def process(results):
            if not results:
                log.warning('No results returned')
                return
            if 'items' in results.keys():
                items = results['items']
            elif 'tracks' in results.keys():
                items = results['tracks']
            else:
                log.warning('Could not parse results')
                return
            if 'next' in results.keys() and results['next']:
                var['next'] = results['next']
            return handle_results(items)

        def handle_results(items):
            tracks = []
            for row in items:
                if 'track' in row.keys():
                    row = row['track']
                subrow = row[
                    'linked_from'] if 'linked_from' in row.keys() else row
                trackid = subrow['uri']
                if category in ['album']:
                    tracks.append(trackid)
                else:
                    item = {}
                    item['id'] = trackid
                    item['artist'] = row['artists'][0]['name']
                    item['artistid'] = row['artists'][0]['uri']
                    item['album'] = row['album']['name']
                    item['albumid'] = row['album']['uri']
                    item['song'] = row['name']
                    item['play_time'] = ms_to_str(
                        row['duration_ms'],
                        two_columns=True)
                    item['artURI'] = self.get_image_uri(
                        row['album']['images'], 'albums')
                    tracks.append(item)
            if category in ['album']:
                return self.objects['spotify_cache'].get_track_data(tracks, var['client_id'], fulldata=fulldata)
            else:
                return self.objects['spotify_cache'].add_track_data(tracks, fulldata=fulldata)

        d = get(endpoint, params)
        d.addCallback(process)
        d.addErrback(logError)
        d.addCallback(return_results)
        return d

    @serialised
    def clear_playlist(self, args):
        return self._clear_playlist(args)

    def _clear_playlist(self, args):
        playlist_id = args['container_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}/tracks'.format(
            playlist_id)
        return self.httpRequest(
            args['client_id'],
            'PUT',
            endpoint,
            None,
            {'uris': []}
        )

    @serialised
    def move_tracks_in_container(self, args):
        playlist_id = args['container_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}/tracks'.format(
            playlist_id)
        d = self.httpRequest(
            args['client_id'],
            'PUT',
            endpoint,
            None,
            {
                'range_start': args['move'][0],
                'range_length': args['move'][1],
                'insert_before': args['move'][2]
            }
        )

        def after(result):
            passed, res = self.check_snapshot_id(result)
            if not passed:
                log.warning(
                    'There was a problem attempting to move tracks in spotify playlist')
            return res
        d.addCallback(after)
        return d

    @serialised
    def delete_tracks_from_container(self, args):
        playlist_id = args['container_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}/tracks'.format(
            playlist_id)
        d = self.httpRequest(
            args['client_id'],
            'DELETE',
            endpoint,
            None,
            {'tracks': args['tracks']}
        )

        def after(result):
            passed, res = self.check_snapshot_id(result)
            if not passed:
                log.warning(
                    'There was a problem attempting to delete tracks from spotify playlist')
            return res
        d.addCallback(after)
        return d

    def copy_to_clipboard(self, args):

        @database_serialised
        @dbpooled
        def process(tx, self):
            query = '''DELETE FROM clipboard_data WHERE clientid = ?'''
            tx.execute(query, (args['client_id'],))
            query = '''	INSERT INTO clipboard_data (clientid, songid, type, track_num)
				 		VALUES (?, ?, ?, ?)'''
            for n, track in enumerate(args['tracks']):
                tx.execute(query, (args['client_id'], track, 's', n))
            self.objects['db_player'].update_clipboard_access(
                tx, args['client_id'])

        d = self.objects['spotify_cache'].get_track_data(
            args['tracks'], args['client_id'], fulldata=False)
        d.addCallback(lambda tracks: process(self))
        return d

    @serialised
    def paste_from_clipboard(self, args):

        @database_serialised
        @dbpooled
        def get(tx, self, args):
            clientid = args['client_id']
            query = '''SELECT songid FROM clipboard_data
				WHERE clientid = ? AND type = "s"
				ORDER BY track_num'''
            tx.execute(query, (clientid,))
            args['rows'] = tx.fetchall()
            self.objects['db_player'].update_clipboard_access(tx, clientid)
            return {'snapshot_id': None}

        def process(results):
            data = {}
            data['uris'] = results
            return self.post(args['client_id'], endpoint, {'position': args['dest']}, data)

        def after(result):
            passed, res = self.check_snapshot_id(result)
            if not passed:
                log.warning(
                    'There was a problem attempting to add tracks to spotify playlist')
                return res
            items = []
            args['dest'] += args['counter']
            while len(args['rows']) and len(items) < 50:
                items.append(args['rows'].pop(0)['songid'])
                args['counter'] += 1
            if len(items):
                d = process(items)
                d.addCallback(after)
                return d
            else:
                return res

        playlist_id = args['container_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}/tracks'.format(
            playlist_id)
        args['counter'] = 0
        args['rows'] = []
        d = get(self, args)
        d.addCallback(after)
        return d

    @serialised
    def playlist_shuffle(self, args):
        playlist_id = args['container_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}/tracks'.format(
            playlist_id)
        moves = random_moves(args['len'])

        def move(m):
            return self.httpRequest(
                args['client_id'],
                'PUT',
                endpoint,
                None,
                {
                    'range_start': m[0],
                    'insert_before': m[1]
                }
            )

        def after(result):
            passed, res = self.check_snapshot_id(result)
            if not passed:
                log.warning(
                    'There was an error attempting to shuffle spotify playlist')
                return res
            if len(moves):
                d = move(moves.pop(0))
                d.addCallback(after)
                return d
            else:
                return res
        return after({'snapshot_id': None})

    def check_snapshot_id(self, result):
        res = {}
        if not result or 'snapshot_id' not in result.keys():
            res['status'] = 'ERROR'
            return False, res
        else:
            res['status'] = 'SUCCESS'
            res['snapshot_id'] = result['snapshot_id']
            return True, res

    @serialised
    def rename_container(self, args):
        playlist_id = args['container_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}'.format(
            playlist_id)

        def rename():
            return self.httpRequest(
                args['client_id'],
                'PUT',
                endpoint,
                None,
                {'name': args['name']}
            )

        def after(result):
            return args['name']
        d = rename()
        d.addCallback(after)
        return d

    @serialised
    def playlist_public(self, args):
        playlist_id = args['playlist_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}'.format(
            playlist_id)
        return self.httpRequest(
            args['client_id'],
            'PUT',
            endpoint,
            None,
            {'public': args['pubic']}
        )

    @serialised
    def playlist_follow(self, args):
        playlist_id = args['playlist_id'].split(':')[2]
        endpoint = 'https://api.spotify.com/v1/playlists/{0}/followers'.format(
            playlist_id)
        cmd = 'PUT' if args['follow'] else 'DELETE'
        return self.httpRequest(
            args['client_id'],
            cmd,
            endpoint,
            None
        )

    def search_artists(self, args):
        return self.search(args, 'artist')

    def search_albums(self, args):
        tag = ' artist:' + args['artist'] if 'artist' in args.keys() else ''
        return self.search(args, 'album', tag)

    def search_albums_recent(self, args):
        return self.search(args, 'album', ' tag:new')

    def search_songs(self, args):
        return self.search(args, 'track')

    def search_playlists(self, args):
        return self.search(args, 'playlist')

    def search_album_from_artistid(self, args):
        return self.search_id(args, 'albums')

    def search_playlists_from_userid(self, args):
        return self.search_id(args, 'playlists')

    def search_my_albums(self, args):
        return self.search_id(args, 'my_albums')

    def search_my_tracks(self, args):
        return self.search_id(args, 'my_tracks')

    def search_my_playlists(self, args):
        return self.search_id(args, 'my_playlists')

    def search_my_playlists_editable(self, args):
        args['editable'] = True
        return self.search_id(args, 'my_playlists')

    def search_songs_from_albumid(self, args):
        search_type = args['id'].split(':')[1]
        if search_type == 'artistRecommendations':
            return self.search_artist_recommendations(args)
        if search_type == 'artistTopTracks':
            return self.search_top_tracks(args)
        return self.search_id(args, 'songs')

    def search_songs_from_playlistid(self, args):
        return self.search_id(args, 'playlist_songs')

    def search_songs_from_track_uri(self, args):
        return self.search_id(args, 'songs_from_track_uri')

    def search_artist_from_track_uri(self, args):
        return self.search_id(args, 'artist_from_track_uri')

    @defer.inlineCallbacks
    def get_recommendations(self, args, fulldata):

        # Not sure it's necessary to use a separate
        # args object, but it's safer this way.
        new_args = args.copy()
        new_args['id'] = args['container_id']
        results = yield self.search_recommendations(new_args)
        for item in results['results']:
            item['id'] = item.pop('itemid')
            item['song'] = item.pop('title')
        if not fulldata:
            tracks = [item['id'] for item in results['results']]
        else:
            tracks = results['results']
        self.objects['spotify_cache'].add_spotify_data(
            results['results'])

        return {'tracks': tracks}

    def search_recommendations_from_track_uri(self, args):
        return self.search_recommendations(args)

    def search_artist_recommendations(self, args):
        return self.search_recommendations(args)

    def search_recommendations(self, args):

        # We need parameters for the check_cancelled decorator.
        # The second parameter simply has to be unique to this
        # call of search_recommendations, so we use the current time.
        timestamp = time.time()
        check_cancelled = self.check_cancelled(args['sid'], timestamp)
        client_id = args['client_id']

        if 'database_seed' in args:
            track = args['database_seed']['track']
            artist = args['database_seed']['artist']
            params = {
                'client_id': client_id,
                'category': 'track',
                'term': 'track:' + track + ' artist:' + artist,
                'index': 0,
                'count': 1
            }

            def process(data):
                if 'tracks' in data and 'items' in data['tracks']:
                    items = data['tracks']['items']
                if items:
                    args['id'] = items[0]['uri']
                    args.pop('database_seed')
                    return self.search_recommendations(args)

            d = self.search_spotify_cached(params)
            d.addCallback(process)
            return d
        elif 'trackRecommendations' in args['id']:
            source = 'tracks'
            seed_uri = args['id']
            first_seed_uri = None
        elif 'spotify:track' in args['id']:
            source = 'tracks'
            # This unpacks the string of track uris, sorts them
            # into alphabetic order, chops off 'spotify:track:'
            # and converts them back into a string. This ensures
            # that the same recommendations will be returned if a
            # new search is performed with the same tracks, regardless
            # of their order
            seed_uri_tracks = ','.join([x.split(':')[-1]
                                       for x in sorted(args['id'].split(','))])
            seed_uri = 'spotify:trackRecommendations:{}'.format(
                seed_uri_tracks)
            # The first seed uri is used for returning metadata
            first_seed_uri = args['id'].split(',')[0]
        else:
            source = 'artist'
            seed_uri = args['id']
            first_seed_uri = None

        # res will be returned to client
        res = {}
        res['startIndex'] = 0
        res['id'] = args['id']

        # Data is stored here until processing completes.
        # lastfm_results and spotify_conversions are
        # indexed by the spotify_uri of the seed track:
        # var['lastfm_results']['spotify_uri'] = [results].
        # var['dbdata'] holds data corresponding to
        # var['seed_tracks], but formatted for the database.
        var = {}
        var['lastfm_results'] = {}
        var['spotify_conversions'] = {}
        var['seed_tracks'] = []
        var['dbdata'] = []

        # The full list of recommendations is retrieved from
        # the database, if it's there. Data is kept for 30 days.
        # The lastfm_tracks table will always have (at least) data
        # corresponding to the spotify_recommendations table
        def get_recommendations_from_db():

            @database_serialised
            @dbpooled
            def get_data(tx, self, seed_uri, source, first_seed_uri):
                data = {}
                query = ''' SELECT  spotify_title as title,
                                    spotify_uri as itemid,
                                    spotify_artist as artist,
                                    spotify_artist_uri as artistid,
                                    spotify_album as album,
                                    spotify_album_uri as albumid,
                                    spotify_album_artURI as artURI,
                                    play_time as play_time
                            FROM spotify_recommendations
                            JOIN lastfm_tracks
                            ON (spotify_recommendations.recommended_track_uri =
                                lastfm_tracks.spotify_uri)
                            WHERE seed_uri = ?
                            ORDER BY position'''
                tx.execute(query, (seed_uri,))
                rows = tx.fetchall()
                data['rows'] = [dict(row) for row in rows]

                if not first_seed_uri or not len(data['rows']):
                    return data

                query = ''' SELECT  spotify_title as title,
                                    spotify_artist as artist,
                                    spotify_artist_uri as artistid,
                                    spotify_album as album,
                                    spotify_album_uri as albumid,
                                    spotify_album_artURI as artURI
                            FROM lastfm_tracks
                            WHERE spotify_uri = ?'''
                tx.execute(query, (first_seed_uri,))
                row = tx.fetchall()[0]
                data['metadata'] = dict(row)
                return data

            def process_data(data):
                if len(data['rows']):
                    if 'metadata' in data:
                        var['metadata'] = data['metadata']
                    return finish(data['rows'])
                else:
                    return get_spotify_seed_data()

            d = get_data(self, seed_uri, source, first_seed_uri)
            d.addCallback(process_data)
            d.addErrback(logError)
            return d

        def get_spotify_seed_data():

            if source == 'artist':
                d = self.search_top_tracks(args)
            else:
                tracks = args['id'].split(',')
                d = self.objects['spotify_cache'].get_track_data(
                    tracks, client_id)

            d.addCallback(get_lastfm_recommendations)
            d.addCallback(upload_recommendations)
            d.addErrback(logError)
            return d

        @check_cancelled
        def get_lastfm_recommendations(spotify_seeds):

            items = []
            dlist = []

            if source == 'artist' and 'results' in spotify_seeds:
                items = spotify_seeds['results']
            else:
                items = spotify_seeds

            limit = int(100 / len(items))

            for item in items:

                if source == 'tracks':
                    item['title'] = item.pop('song')
                    item['itemid'] = item.pop('id')

                lastfm_seed = {}
                lastfm_seed['spotify_title'] = item['title']
                lastfm_seed['spotify_uri'] = item['itemid']
                lastfm_seed['spotify_artist'] = item['artist']
                d1 = self.objects['lastfm'].get_recommendations(
                    lastfm_seed, limit, check_cancelled)
                d1.addCallback(get_db_data)
                d1.addCallback(get_spotify_data)
                d1.addErrback(logError)
                dlist.append(d1)

                # Grab the seed track data, as it will be
                # stored in the database and (in the case of
                # artist recommendation) added to the results
                dbdata = {}
                dbdata['spotify_title'] = item['title']
                dbdata['spotify_uri'] = item['itemid']
                dbdata['spotify_artist'] = item['artist']
                dbdata['spotify_artist_uri'] = item['artistid']
                dbdata['spotify_album'] = item['album']
                dbdata['spotify_album_uri'] = item['albumid']
                dbdata['spotify_album_artURI'] = item['artURI']
                dbdata['play_time'] = item['play_time']
                var['seed_tracks'].append(item)
                var['dbdata'].append(dbdata)
                if item['itemid'] == first_seed_uri:
                    var['metadata'] = item

            return defer.DeferredList(dlist).addErrback(logError)

        # For each track returned by lastfm, we see if
        # we already have the spotify data in the database

        @check_cancelled
        def get_db_data(lastfm_results):

            spotify_seed_uri = lastfm_results['spotify_seed_uri']
            var['lastfm_results'][spotify_seed_uri] = lastfm_results['items']
            lastfm_urls = [item['url'] for item in lastfm_results['items']]

            @database_serialised
            @check_cancelled
            @dbpooled
            def get_conversions(tx, self, lastfm_urls):
                # The database may return data in a different order,
                # so we set up a list of empty results and then
                # update the list using the indices of the corresponding
                # lastfm_urls, so that the list of results ends up in the same
                # order as the list of lastfm_urls
                results = [{} for url in lastfm_urls]
                query = ''' SELECT *
                            FROM lastfm_tracks
                            WHERE lastfm_url IN (''' + ",".join(
                    "?" * len(lastfm_urls)) + ''')'''
                parameters = tuple(lastfm_urls)
                tx.execute(query, parameters)
                for row in tx.fetchall():
                    # We leave the result blank {}, if there is no spotify
                    # data in the database
                    if row['spotify_uri']:
                        index = lastfm_urls.index(row['lastfm_url'])
                        # If the spotify_uri field is populated, it has either
                        # the spotify uri or the timestamp of the last failed
                        # attempt to find a spotify match
                        if 'spotify' in row['spotify_uri']:
                            results[index]['title'] = row['spotify_title']
                            results[index]['itemid'] = row['spotify_uri']
                            results[index]['artist'] = row['spotify_artist']
                            results[index]['artistid'] = row['spotify_artist_uri']
                            results[index]['album'] = row['spotify_album']
                            results[index]['albumid'] = row['spotify_album_uri']
                            results[index]['artURI'] = row['spotify_album_artURI']
                            results[index]['play_time'] = row['play_time']
                        # In this case, we just add the timestamp to the result
                        else:
                            results[index]['timestamp'] = row['spotify_uri']
                return results

            @check_cancelled
            def process_conversions(results):
                var['spotify_conversions'][spotify_seed_uri] = results
                return spotify_seed_uri

            return get_conversions(self, lastfm_urls).addCallback(process_conversions)

        # Wherever we couldn't get the data from the database,
        # we now try to get it from spotify
        @check_cancelled
        def get_spotify_data(spotify_seed_uri):
            items = var['spotify_conversions'][spotify_seed_uri]
            dlist = []
            for index, item in enumerate(items):
                # This means we have the data
                if 'itemid' in item:
                    continue
                # If there's timestamp, we'll leave the
                # result blank {} if less than 30 days
                # have elapsed since we last tried to retrieve
                # spotify data, else we'll try again to get the data
                if 'timestamp' in item:
                    timestamp = float(item['timestamp'])
                    now = time.time()
                    items[index] = {}
                    if now - timestamp < (60*60*24*30):  # 30 days
                        continue
                # If we got this far, it means we're going to search
                # spotify for the data
                lastfm_item = var['lastfm_results'][spotify_seed_uri][index]
                track = lastfm_item['name']
                artist = lastfm_item['artist']
                params = {
                    'client_id': client_id,
                    'category': 'track',
                    'term': 'track:' + track + ' artist:' + artist,
                    'index': 0,
                    'count': 1
                }
                # We want serialisation to wrap the
                # @check_cancelled decorator, and we don't
                # want to clutter the two main serialisers
                # as this could be a long running operation
                d1 = self.third_serialiser.serialise(
                    search, spotify_seed_uri, index, params)
                d1.addCallback(process_spotify_data)
                d1.addErrback(logError)
                dlist.append(d1)
            if len(dlist):
                return defer.DeferredList(dlist).addErrback(logError)

        # Wherever we've searched spotify for data corresponding
        # to a lastfm recommendation, we now have to process that data
        # This function is called for each spotify search
        # meaning it could be called 100 times
        @check_cancelled
        def process_spotify_data(result):

            spotify_seed_uri = result['spotify_seed_uri']
            index = result['index']
            data = result['results']
            spotify_conversion = var['spotify_conversions'][spotify_seed_uri][index]
            lastfm_track = var['lastfm_results'][spotify_seed_uri][index]
            lastfm_url = lastfm_track['url']

            @database_serialised
            @dbpooled
            def upload_data_to_lastfm_tracks(tx, self, dbdata, lastfm_url):
                set_clause = ", ".join([f"{key} = ?" for key in dbdata.keys()])
                values = tuple(list(dbdata.values()) + [lastfm_url])
                query = f"UPDATE lastfm_tracks SET {set_clause} WHERE lastfm_url = ?"
                tx.execute(query, values)

            # We format the data twice, for uploading to the database and
            # for returning results to the client. This is duplicative, obviously.
            # It would have been good to have settled on a uniform data naming
            # convention. There is also a thread safety point, because database
            # calls occur within a separate thread
            dbdata = {}
            items = []
            if 'tracks' in data and 'items' in data['tracks']:
                items = data['tracks']['items']
            if items:
                dbdata['spotify_title'] = spotify_conversion['title'] = items[0]['name']
                dbdata['spotify_uri'] = spotify_conversion['itemid'] = items[0]['uri']
                dbdata['spotify_artist'] = spotify_conversion['artist'] = items[0]['artists'][0]['name']
                dbdata['spotify_artist_uri'] = spotify_conversion['artistid'] = items[0]['artists'][0]['uri']
                dbdata['spotify_album'] = spotify_conversion['album'] = items[0]['album']['name']
                dbdata['spotify_album_uri'] = spotify_conversion['albumid'] = items[0]['album']['uri']
                dbdata['spotify_album_artURI'] = spotify_conversion['artURI'] = self.get_image_uri(
                    items[0]['album']['images'], 'albums')
                dbdata['play_time'] = spotify_conversion['play_time'] = ms_to_str(
                    items[0]['duration_ms'],
                    two_columns=True)
            else:
                track = f"{lastfm_track['artist']}/{lastfm_track['name']}"
                log.warning(f'Could not find Spotify track for {track}')
                dbdata['spotify_uri'] = str(time.time())

            # Uploading to the database can take place asynchronously in the background,
            # so we don't wait for it to complete. This is partly why we
            # use a separate dataset for the database. Database calls are serialised,
            # to avoid race conditions. The lastfm_url field is unique, so duplicates
            # are automatically ignored.
            upload_data_to_lastfm_tracks(
                self, dbdata, lastfm_url).addErrback(logError)

        # This is the function for searching spotify for tracks corresponding
        # to lastfm recommendations. We return the spotify_seed_uri and
        # the index with the result, so that the relevant blank item {}
        # can be located and populated with the result
        @check_cancelled
        def search(spotify_seed_uri, index, params):

            def process(results):
                return {
                    'spotify_seed_uri': spotify_seed_uri,
                    'index': index,
                    'results': results
                }

            d = self.search_spotify_cached(params)
            d.addCallback(process)
            return d

        # This function is reached after all the lastfm
        # recommendations have been processed
        @check_cancelled
        def upload_recommendations(dummy):

            @database_serialised
            @dbpooled
            def upload_data_to_spotify_recommendations(tx, self, dbdata):
                query = ''' INSERT INTO spotify_recommendations
                            (seed_uri, position, recommended_track_uri, timestamp)
                            VALUES
                            (:seed_uri, :position, :recommended_track_uri, :timestamp)'''
                tx.executemany(query, dbdata)

            # We add a WHERE NOT EXISTS clause so that a top track
            # is added only if it's not already in the database. For
            # lastfm_urls, uniqueness is guaranteed because that field is
            # unique. However, top tracks have no corresponding lastfm_url,
            # as we don't actually need that information. If the spotify_uri
            # field were also unique, that would interfere with subsequent
            # processing of a lastfm recommendation that has the same
            # spotify_uri (a situation likely to occur). This means that a
            # top track's spotify_uri might subsequently be duplicated
            # (once only) if it crops up again as a lastfm recommendation
            # but that shouldn't matter (apart from being slightly inefficient).
            # We need to add the top track data, because this table is used by
            # the get_recommendations_from_db() function above.

            @database_serialised
            @dbpooled
            def add_seeds_to_database(tx, self, dbdata):
                insert_clause = ", ".join(dbdata[0].keys())
                values_clause = ", ".join(
                    [f":{key}" for key in dbdata[0].keys()])
                query = ''' INSERT INTO lastfm_tracks
                            (''' + insert_clause + ''')
                            SELECT ''' + values_clause + '''
                            WHERE NOT EXISTS (
                                SELECT 1 FROM lastfm_tracks
                                WHERE spotify_uri = :spotify_uri
                            )'''
                tx.executemany(query, dbdata)

                query = ''' INSERT INTO spotify_recommendations_seeds
                            (seed_uri, spotify_uri)
                            VALUES
                            (:seed_uri, :spotify_uri)'''

                tx.executemany(query, [
                               {"seed_uri": seed_uri,
                                "spotify_uri": seed["spotify_uri"]
                                } for seed in dbdata])

            itemids = []
            recommendations = []
            for key in var['spotify_conversions'].keys():
                for track in var['spotify_conversions'][key]:
                    if 'itemid' in track and track['itemid'] not in itemids:
                        recommendations.append(track)
                        itemids.append(track['itemid'])
            if source == 'artist':
                for track in var['seed_tracks']:
                    if 'itemid' in track and track['itemid'] not in itemids:
                        recommendations.append(track)
                        itemids.append(track['itemid'])
            random.shuffle(recommendations)

            dbdata = [{} for recommendation in recommendations]
            timestamp = int(time.time())

            for index, item in enumerate(recommendations):
                entry = dbdata[index]
                entry['seed_uri'] = seed_uri
                entry['position'] = index + 1
                entry['recommended_track_uri'] = recommendations[index]['itemid']
                entry['timestamp'] = timestamp

            # Uploading to the database can take place synchronously in the background,
            # so we don't wait for it to complete. This is partly why we
            # use a separate dataset for the database. Database calls are serialised,
            # to avoid race conditions.
            upload_data_to_spotify_recommendations(
                self, dbdata).addErrback(logError)
            add_seeds_to_database(self, var['dbdata']).addErrback(logError)
            return finish(recommendations)

        @check_cancelled
        def finish(recommendations):

            @check_cancelled
            def return_results(artist=None):

                if args['sid'] in self.active_searches:
                    if timestamp in self.active_searches[args['sid']]:
                        self.active_searches[args['sid']].remove(timestamp)

                if source == 'tracks' and 'metadata' in var:
                    data = var['metadata']
                    metadata = {}
                    metadata['system'] = 'spotify'
                    metadata['trackid'] = args['id']
                    metadata['album'] = 'Recommendations based on: {}/{}'.format(
                        data['album'], data['title'])
                    if len(var['seed_tracks']) > 1:
                        metadata['album'] += ' (and {} other tracks)'.format(
                            str(len(var['seed_tracks'])-1))
                    metadata['albumid'] = seed_uri
                    metadata['albumArtURI'] = data['artURI']
                    metadata['artist'] = data['artist']
                    metadata['artistid'] = data['artistid']
                    if artist and 'images' in artist:
                        metadata['artistArtURI'] = self.get_image_uri(
                            artist['images'])
                    else:
                        metadata['artistArtURI'] = 'icons/ArtistNoImage.png'
                    metadata['item_type'] = 'program'
                    res['metadata'] = metadata

                res['results'] = recommendations
                res['totalRecords'] = len(res['results'])
                return res

            if 'metadata' in var:
                artistid = var['metadata']['artistid'].split(':')[-1]
                params = {
                    'client_id': client_id,
                    'endpoint': 'https://api.spotify.com/v1/artists/' + artistid
                }
                d = self.search_spotify_id_cached(params)
                d.addCallback(return_results)
                d.addErrback(logError)
                return d
            else:
                return return_results()

        return get_recommendations_from_db()

    def search_related_artists(self, args):

        # We need parameters for the check_cancelled decorator.
        # The second parameter simply has to be unique to this
        # call of search_related_artists, so we use the current time.
        timestamp = time.time()
        check_cancelled = self.check_cancelled(args['sid'], timestamp)

        def get_db_data():

            @database_serialised
            @dbpooled
            def get_data(tx, self, artist_uri):

                query = ''' SELECT spotify_uri as uri, spotify_name as name, spotify_art_uri as art_uri
                            FROM spotify_related_artists
                            JOIN lastfm_artists
                            ON (spotify_related_artists.related_artist_uri = lastfm_artists.spotify_uri)
                            WHERE seed_artist_uri = ?
                            ORDER BY position'''
                tx.execute(query, (artist_uri,))
                rows = tx.fetchall()
                return [dict(row) for row in rows]

            def process_data(rows):

                if len(rows):
                    return finish(rows)
                else:
                    d1 = self.objects['lastfm'].get_related_artists(
                        args['id']['artist_name'])
                    d1.addCallback(update_results)
                    d1.addErrback(logError)
                    return d1
            d = get_data(self, args['id']['artist_uri'])
            d.addCallback(process_data)
            d.addErrback(logError)
            return d

        @check_cancelled
        def update_results(lastfm_reply):

            @database_serialised
            @check_cancelled
            @dbpooled
            def get_conversions(tx, self, lastfm_urls):
                conversions = [{} for url in lastfm_urls]
                query = ''' SELECT *
                            FROM lastfm_artists
                            WHERE lastfm_url IN (''' + ",".join(
                    "?" * len(lastfm_urls)) + ''')'''
                parameters = tuple(lastfm_urls)
                tx.execute(query, parameters)
                for row in tx.fetchall():
                    if row['spotify_uri']:
                        index = lastfm_urls.index(row['lastfm_url'])
                        conversions[index]['name'] = row['spotify_name']
                        conversions[index]['uri'] = row['spotify_uri']
                        conversions[index]['art_uri'] = row['spotify_art_uri']
                return conversions

            @check_cancelled
            def convert_lastfm_artists_to_spotify(conversions):

                @check_cancelled
                def process_spotify_data(response):

                    @database_serialised
                    @check_cancelled
                    @dbpooled
                    def upload_data_to_database(tx, self, dbdata, lastfm_url):
                        set_clause = ", ".join(
                            [f"{key} = ?" for key in dbdata.keys()])
                        values = tuple(list(dbdata.values()) + [lastfm_url])
                        query = f"UPDATE lastfm_artists SET {set_clause} WHERE lastfm_url = ?"
                        tx.execute(query, values)

                    results = response['results']
                    index = response['index']
                    spotify_conversion = conversions[index]
                    items = []
                    dbdata = {}
                    if 'artists' in results and 'items' in results['artists']:
                        items = results['artists']['items']
                    if len(items):
                        item = items[0]
                        lastfm_url = lastfm_reply[index]['url']
                        dbdata['spotify_uri'] = spotify_conversion['uri'] = item['uri']
                        dbdata['spotify_name'] = spotify_conversion['name'] = item['name']
                        dbdata['spotify_art_uri'] = spotify_conversion['art_uri'] = self.get_image_uri(
                            item['images'])
                    else:
                        artist = lastfm_reply[index]['artist']
                        log.warning(
                            f'Could not find Spotify artist for {artist}')
                        dbdata['spotify_uri'] = str(time.time())
                    upload_data_to_database(
                        self, dbdata, lastfm_url).addErrback(logError)

                @check_cancelled
                def upload_related_artists(dummy):

                    @database_serialised
                    @dbpooled
                    def upload_data_to_database(tx, self, dbdata):
                        query = ''' INSERT INTO spotify_related_artists
                                    (seed_artist_uri, position,
                                     related_artist_uri, timestamp)
                                    VALUES
                                    (:seed_artist_uri, :position, :related_artist_uri, :timestamp)'''
                        tx.executemany(query, dbdata)

                    uris = []

                    for index, item in reversed(list(enumerate(conversions))):
                        if 'uri' not in item:
                            del conversions[index]
                        if item['uri'] in uris:
                            del conversions[index]
                        uris.append(item['uri'])

                    dbdata = [{} for conversion in conversions]
                    timestamp = int(time.time())
                    seed_artist_uri = args['id']['artist_uri']

                    for index, item in enumerate(conversions):
                        entry = dbdata[index]
                        entry['seed_artist_uri'] = seed_artist_uri
                        entry['position'] = index + 1
                        entry['related_artist_uri'] = conversions[index]['uri']
                        entry['timestamp'] = timestamp

                    upload_data_to_database(self, dbdata)
                    return finish(conversions)

                @check_cancelled
                def search(params, index):

                    @check_cancelled
                    def process(results):
                        return {
                            'index': index,
                            'results': results
                        }

                    d = self.search_spotify_cached(params)
                    d.addCallback(process)
                    return d

                dlist = []
                for index, conversion in enumerate(conversions):
                    if 'uri' in conversion:
                        if 'spotify' in conversion['uri']:
                            continue
                        else:
                            timestamp = float(conversion['uri'])
                            now = time.time()
                            conversion = {}
                            if now - timestamp < (60*60*24*30):  # 30 days
                                continue
                    artist = lastfm_reply[index]['name']
                    params = {
                        'client_id': args['client_id'],
                        'category': 'artist',
                        'term': artist,
                        'index': 0,
                        'count': 1
                    }
                    d1 = self.third_serialiser.serialise(search, params, index)
                    d1.addCallback(process_spotify_data)
                    d1.addErrback(logError)
                    dlist.append(d1)

                if len(dlist):
                    d = defer.DeferredList(dlist)
                else:
                    d = defer.Deferred()
                    d.callback(None)
                d.addCallback(upload_related_artists)
                d.addErrback(logError)
                return d

            d = get_conversions(self, [item['url'] for item in lastfm_reply])
            d.addCallback(convert_lastfm_artists_to_spotify)
            return d

        @check_cancelled
        def finish(artists):

            if args['sid'] in self.active_searches:
                if timestamp in self.active_searches[args['sid']]:
                    self.active_searches[args['sid']].remove(timestamp)

            res = {}
            res['startIndex'] = 0
            res['totalRecords'] = len(artists)
            res['id'] = args['id']['artist_uri']
            res['results'] = []
            metadata = {}
            metadata['system'] = 'spotify'
            res['metadata'] = metadata
            for artist in artists:
                item = {}
                item['title'] = artist['name']
                item['itemid'] = artist['uri']
                item['artURI'] = artist['art_uri']
                res['results'].append(item)
            return res

        return get_db_data()

    # This purges items in the spotify_recommendations and
    # spotify_related_artists tables which are more than
    # 30 days old and related entries in the two lastfm databases,
    # even if the data has been accessed in the last 30 days
    # (i.e. we don't currently keep updating the timestamp)
    def clean_database(self):

        @database_serialised
        @dbpooled
        def clean(tx, self):

            # This yields a cutoff of 30 days ago
            now = int(time.time())
            too_old = now - (60*60*24*30)

            query = ''' DELETE FROM spotify_recommendations
                        WHERE seed_uri IN
                        (SELECT seed_uri
                        FROM spotify_recommendations
                        WHERE timestamp < ?)'''
            tx.execute(query, (too_old,))
            query = ''' DELETE FROM spotify_related_artists
                        WHERE seed_artist_uri IN
                        (SELECT seed_artist_uri
                        FROM spotify_related_artists
                        WHERE timestamp < ?)'''
            tx.execute(query, (too_old,))
            query = ''' DELETE FROM spotify_recommendations_seeds
                        WHERE seed_uri NOT IN (
                        SELECT seed_uri FROM spotify_recommendations
                        );'''
            query = ''' DELETE FROM lastfm_tracks
                        WHERE spotify_uri NOT IN (
                            SELECT recommended_track_uri
                            FROM spotify_recommendations
                            UNION
                            SELECT spotify_uri FROM spotify_recommendations_seeds
                        )'''
            tx.execute(query)
            query = ''' DELETE FROM lastfm_artists
                        WHERE spotify_uri NOT IN (
                            SELECT related_artist_uri
                            FROM spotify_related_artists
                        )'''
            tx.execute(query)

        d = clean(self)
        d.addErrback(logError)

        # Schedule another clean tomorrow
        reactor.callLater(60*60*24, self.clean_database)

    def search_find_track(self, args):
        d = self.search_id(args, 'albums')

        def process(results):
            if results == 'CANCELLED':
                return 'CANCELLED'
            res = {}
            data = []
            args2 = {}
            args2['startIndex'] = 0
            args2['rowsPerPage'] = 100
            args2['sid'] = args['sid']

            def sift(results1):
                if results1 == 'CANCELLED':
                    return 'CANCELLED'
                for r in results1['results']:
                    ratio = fuzz.partial_ratio(
                        args['value'].lower(),
                        r['title'].lower())
                    if ratio > 70:
                        data.append([ratio, r])

            def get_next(results1=None):
                if results1 == 'CANCELLED':
                    return 'CANCELLED'
                if len(results['results']):
                    r = results['results'].pop(0)
                    if 'spotify:artistRecommendations' in r['itemid'] or 'spotify:artistTopTracks' in r['itemid']:
                        return get_next()
                    args2['id'] = r['id'] = r['itemid']
                    r['albumArtURI'] = r['artURI']
                    args2['album'] = r
                    d = self.search_id(args2, 'songs_only')
                    d.addCallback(sift)
                    d.addCallback(get_next)
                    d.addErrback(logError)
                    return d
                res['totalRecords'] = len(data)
                res['startIndex'] = 0
                res['id'] = args['id']
                res['value'] = args['value']
                res['results'] = []
                sorted_data = sorted(data, key=lambda x: x[0], reverse=True)
                for d in sorted_data:
                    res['results'].append(d[1])
                return res
            return get_next()
        d.addCallback(process)
        d.addErrback(logError)
        return d

    def search(self, args, category, filters=''):
        rowsPerPage = int(args['rowsPerPage'])
        search_term = args['id']
        startIndex = int(args['startIndex'])
        res = {}
        res['startIndex'] = startIndex
        res['totalRecords'] = 0
        res['id'] = search_term
        res['results'] = []
        if not search_term:
            return res
        cached = True
        if category in ['playlist']:
            cached = False
            term = search_term + filters
        else:
            term = category + ':' + search_term + filters
        d = self.search_spotify({
            'client_id': args['client_id'],
            'category': category,
            'term': term,
            'index': int(startIndex / 50) * 50,
            'count': 50
        },
            args['sid'],
            cached
        )

        def fill_row(row):
            item = {}

            # Spotify can return null items, especially for playlists,
            # so we only populate if we actually got data. If there was a
            # null item, we append it anyway, to preserve the numbering

            if row:
                item['title'] = row['name']
                item['itemid'] = row['uri']
                if 'artists' in row.keys():
                    subrow = row['artists'][0]  # FIXME
                    item['artist'] = subrow['name']
                    item['artistid'] = subrow['uri']
                if 'album' in row.keys():
                    subrow = row['album']
                    item['album'] = subrow['name']
                    item['albumid'] = subrow['uri']
                    item['artURI'] = self.get_image_uri(
                        subrow['images'], 'albums')
                if 'snapshot_id' in row.keys():
                    item['snapshot_id'] = row['snapshot_id']
                if 'public' in row.keys():
                    item['pubic'] = row['public']
                if 'images' in row.keys():
                    item['artURI'] = self.get_image_uri(row['images'])
                if 'duration_ms' in row.keys():
                    item['play_time'] = ms_to_str(row['duration_ms'],
                                                  two_columns=True)
            res['results'].append(item)

        def unpack(results, index=0, n=0):
            data = results['items']
            if n:
                for i in range(index, index + n):
                    fill_row(data[i])
            else:
                for d in data:
                    fill_row(d)

        def process1(results):
            if results == 'CANCELLED':
                return 'CANCELLED'
            if not results:
                return
            results = list(results.values())[0]
            res['totalRecords'] = int(results['total'])
            stub = max(0, startIndex + rowsPerPage - (
                int(results['offset']) + len(results['items'])))
            n = rowsPerPage - stub
            n1 = 0
            if n:
                unpack(results, startIndex - int(results['offset']), n)
            if stub:
                n1 = min(int(results['total']) - (
                    int(results['offset']) + len(results['items'])), stub)
            if n1:
                return self.search_spotify({
                    'client_id': args['client_id'],
                    'category': category,
                    'term': term,
                    'index': int((startIndex + 50) / 50) * 50,
                    'count': n1
                },
                    args['sid'],
                    cached
                )

        def process2(results):
            if results == 'CANCELLED':
                return 'CANCELLED'
            if results:
                results = list(results.values())[0]
                unpack(results)
            return res

        d.addCallback(process1)
        d.addCallback(process2)
        return d

    def search_id(self, args, category):
        client_id = args['client_id']
        client = self.clients[client_id]
        var = {}
        var['rowsPerPage'] = int(args['rowsPerPage'])
        var['search_term'] = ','.join(
            [x.split(':')[-1] for x in args['id'].split(',')])
        var['startIndex'] = int(args['startIndex'])
        res = {}
        res['startIndex'] = var['startIndex']
        res['totalRecords'] = 0
        res['id'] = args['id']
        res['results'] = []
        if 'metadata' in args:
            metadata = args['metadata']
        else:
            metadata = {}
        metadata['system'] = 'spotify'
        cached = True
        editable = False
        if category in ['my_albums', 'my_tracks', 'playlists', 'my_playlists', 'playlist_songs']:
            cached = False
        if 'editable' in args.keys():
            editable = True
        if category == 'albums':
            endpoint = 'https://api.spotify.com/v1/artists/{}/albums'
            # We're not getting Artist Recommendations and Top Tracks from Spotify
            var['startIndex'] = max(0, var['startIndex'] - 2)
            if var['startIndex'] == 0:
                var['rowsPerPage'] -= 2
            d = defer.Deferred()
            d.callback(None)
        elif category == 'artist_from_track_uri':
            endpoint = 'https://api.spotify.com/v1/artists/{}/albums'
            # We're not getting Artist Recommendations and Top Tracks from Spotify
            var['startIndex'] = max(0, var['startIndex'] - 2)
            if var['startIndex'] == 0:
                var['rowsPerPage'] -= 2
            d = self.search_spotify_id_cached({
                'client_id': client_id,
                'endpoint': 'https://api.spotify.com/v1/tracks/{}',
                'item_id': var['search_term']
            })

            def get_artist_id(result):
                if result == 'CANCELLED':
                    return 'CANCELLED'
                var['search_term'] = result['artists'][0]['uri'].split(':')[-1]
                return self.search_spotify_id_cached({
                    'client_id': client_id,
                    'endpoint': 'https://api.spotify.com/v1/artists/{}',
                    'item_id': var['search_term']
                })

            def get_artist(result):
                if result == 'CANCELLED':
                    return 'CANCELLED'
                metadata['artist'] = result['name']
                metadata['artistid'] = result['uri']
                metadata['artistArtURI'] = self.get_image_uri(
                    result['images'], 'artists')

            d.addCallback(get_artist_id)
            d.addCallback(get_artist)

        elif category == 'related_artists':
            endpoint = 'https://api.spotify.com/v1/artists/{}/related-artists'
            d = defer.Deferred()
            d.callback(None)
        elif category == 'playlists':
            endpoint = 'https://api.spotify.com/v1/users/{}/playlists'
            d = defer.Deferred()
            d.callback(None)
        elif category == 'my_albums':
            var['search_term'] = 'me'
            endpoint = 'https://api.spotify.com/v1/{}/albums'
            d = defer.Deferred()
            d.callback(None)
        elif category == 'my_tracks':
            var['search_term'] = 'me'
            endpoint = 'https://api.spotify.com/v1/{}/tracks'
            d = defer.Deferred()
            d.callback(None)
        elif category == 'my_playlists':
            var['search_term'] = 'me'
            endpoint = 'https://api.spotify.com/v1/{}/playlists'
            d = defer.Deferred()
            d.callback(None)
        elif category == 'playlist_songs':
            endpoint = 'https://api.spotify.com/v1/playlists/{}/tracks'
            if var['startIndex']:
                d = defer.Deferred()
                d.callback(None)
            else:
                d = self.search_spotify_id_cached({
                    'client_id': client_id,
                    'endpoint': 'https://api.spotify.com/v1/playlists/{}',
                    'item_id': var['search_term']
                })

                def get_user(result):
                    if result == 'CANCELLED':
                        return 'CANCELLED'
                    user = result['owner']['id']
                    metadata['artist'] = result['owner']['display_name'] or user
                    metadata['artistid'] = result['owner']['uri']
                    metadata['artistArtURI'] = self.get_image_uri(
                        result['owner'].get('images', []), 'artists')
                    metadata['item_type'] = 'playlist'
                    metadata['editable'] = user == client.user_id
                    if not metadata['editable']:
                        return self.search_spotify_id_cached({
                            'client_id': client_id,
                            'endpoint': 'https://api.spotify.com/v1/playlists/{}/followers/contains',
                            'item_id': var['search_term'],
                            'ids': client.user_id
                        })

                def get_followed(result):
                    if result == 'CANCELLED':
                        return 'CANCELLED'
                    if result:
                        metadata['followed'] = result[0]

                d.addCallback(get_user)
                d.addCallback(get_followed)

        elif category == 'songs_from_track_uri':
            endpoint = 'https://api.spotify.com/v1/albums/{}/tracks'
            d = self.search_spotify_id_cached({
                'client_id': client_id,
                'endpoint': 'https://api.spotify.com/v1/tracks/{}',
                'item_id': var['search_term']
            })
            album = {}
            metadata['trackid'] = args['id']

            def get_album(result):
                if result == 'CANCELLED':
                    return 'CANCELLED'
                metadata['album'] = album['title'] = result['album']['name']
                metadata['albumid'] = album['id'] = result['album']['uri']
                metadata['albumArtURI'] = album['albumArtURI'] = self.get_image_uri(
                    result['album']['images'], 'albums')
                var['search_term'] = album['id'].split(':')[-1]

            d.addCallback(get_album)

        elif category == 'songs':
            endpoint = 'https://api.spotify.com/v1/albums/{}/tracks'
            d = self.search_spotify_id_cached({
                'client_id': client_id,
                'endpoint': 'https://api.spotify.com/v1/albums/{}',
                'item_id': var['search_term']
            })
            album = {}

            def get_album(result):
                if result == 'CANCELLED':
                    return 'CANCELLED'
                album['title'] = result['name']
                album['id'] = result['uri']
                album['albumArtURI'] = self.get_image_uri(
                    result['images'], 'albums')

            d.addCallback(get_album)

        elif category == 'songs_only':
            endpoint = 'https://api.spotify.com/v1/albums/{}/tracks'
            album = args['album']
            d = defer.Deferred()
            d.callback(None)

        def start(result):
            if result == 'CANCELLED':
                return 'CANCELLED'
            params = {
                'client_id': client_id,
                'endpoint': endpoint,
                'item_id': var['search_term'],
                'index': int(var['startIndex'] / 50) * 50,
                'count': 50
            }
            d = self.search_spotify_id(
                params,
                cached
            )
            d.addCallback(process1)
            d.addCallback(process2)
            d.addCallback(process3)
            return d

        def fill_row(row):
            item = {}
            if category in ['songs', 'songs_from_track_uri', 'songs_only']:
                item['title'] = row['name']
                item['itemid'] = row['uri']
                subrow = row['artists'][0]
                item['artist'] = subrow['name']
                item['artistid'] = subrow['uri']
                item['album'] = album['title']
                item['albumid'] = album['id']
                item['artURI'] = album['albumArtURI']
                item['play_time'] = ms_to_str(row['duration_ms'],
                                              two_columns=True)
            elif category in ['playlist_songs', 'my_tracks']:
                row = row['track']
                if not row:
                    return
                item['title'] = row['name']
                if 'linked_from' in row.keys():
                    subrow = row['linked_from']
                else:
                    subrow = row
                item['itemid'] = subrow['uri']
                subrow = row['artists'][0]
                item['artist'] = subrow['name']
                item['artistid'] = subrow['uri']
                subrow = row['album']
                item['album'] = subrow['name']
                item['albumid'] = subrow['uri']
                item['artURI'] = self.get_image_uri(subrow['images'], 'albums')
                item['play_time'] = ms_to_str(row['duration_ms'],
                                              two_columns=True)
            elif category in ['albums', 'my_albums', 'artist_from_track_uri']:
                if category == 'my_albums':
                    row = row['album']
                item['title'] = row['name']
                item['itemid'] = row['uri']
                item['itemtype'] = 'album'
                item['artURI'] = self.get_image_uri(row['images'], 'albums')
            elif category in ['playlists', 'my_playlists']:
                if not editable or row['owner']['id'] == client.user_id:
                    item['title'] = row['name']
                    item['itemid'] = row['uri']
                    item['snapshot_id'] = row['snapshot_id']
                    item['pubic'] = row['public']
                    item['artURI'] = self.get_image_uri(
                        row['images'], 'albums')
            res['results'].append(item)

        def unpack(results, index=0, n=0):
            data = results['items']
            if n:
                for i in range(index, index + n):
                    fill_row(data[i])
            else:
                for d in data:
                    fill_row(d)

        def process1(results):
            if results == 'CANCELLED':
                return 'CANCELLED'
            if not results:
                return
            res['totalRecords'] = int(results['total'])
            stub = max(0, var['startIndex'] + var['rowsPerPage'] - (
                int(results['offset']) + len(results['items'])))
            n = var['rowsPerPage'] - stub
            n1 = 0
            if category in ['albums', 'artist_from_track_uri']:
                res[
                    'totalRecords'] += 2  # We're not getting Artist Recommendations and Top Tracks from Spotify
                if var['startIndex'] == 0:
                    res['results'].append({
                        'title': '',
                        'itemid':
                        'spotify:artistRecommendations:{}'.format(
                            var['search_term']),
                            'itemtype': 'program',
                            'artURI': ''
                    })
                    res['results'].append({
                        'title': 'Top Tracks',
                        'itemid':
                        'spotify:artistTopTracks:{}'.format(
                            var['search_term']),
                        'itemtype': 'trackList',
                            'artURI': ''
                    })
            if n:
                unpack(results, var['startIndex'] - int(results['offset']), n)
            if stub:
                n1 = min(int(results['total']) - (
                    int(results['offset']) + len(results['items'])), stub)
            if n1:
                return self.search_spotify_id({
                    'client_id': client_id,
                    'endpoint': endpoint,
                    'item_id': var['search_term'],
                    'index': int((var['startIndex'] + 50) / 50) * 50,
                    'count': n1
                },
                    cached
                )

        def process2(results):
            if results == 'CANCELLED':
                return 'CANCELLED'
            if results:
                unpack(results)
            res['metadata'] = metadata
            if category not in ['songs', 'songs_from_track_uri']:
                return
            if category in ['songs', 'songs_from_track_uri']:
                res['metadata']['artist'] = 'Various Artists'
                res['metadata']['artistid'] = None
                res['metadata']['artistArtURI'] = 'icons/VariousArtists.png'
                res['metadata']['item_type'] = 'album_various'
                artists = []
                artistids = []
                count = {}
                for result in res['results']:
                    if result['artistid'] in artistids:
                        count[result['artistid']] += 1
                    else:
                        if len(artistids) > 3:
                            return
                        artists.append(result['artist'])
                        artistids.append(result['artistid'])
                        count[result['artistid']] = 1
                highest = 0
                for n, artistid in enumerate(artistids):
                    if count[artistid] > highest:
                        res['metadata']['artist'] = artists[n]
                        res['metadata']['artistid'] = artistid
                        highest = count[artistid]
                if len(artistids) == 1:
                    res['metadata']['item_type'] = 'album'
            return self.search_spotify_id(
                {
                    'client_id': client_id,
                    'endpoint':
                    'https://api.spotify.com/v1/artists/{}',
                    'item_id':
                    res['metadata']['artistid'].split(':')[-1]
                },
                cached
            )

        def process3(result):
            if result == 'CANCELLED':
                return 'CANCELLED'
            if result:
                res['metadata']['artistArtURI'] = self.get_image_uri(
                    result['images'])
            return res

        d.addCallback(start)
        return d

    def search_top_tracks(self, args):
        res = {}
        res['startIndex'] = 0
        res['totalRecords'] = 0
        res['id'] = args['id']
        res['results'] = []

        endpoint = 'https://api.spotify.com/v1/artists/{}/top-tracks'.format(
            args['id'].split(':')[-1])
        client_id = args['client_id']
        params = {
            'client_id': client_id,
            'country': self.clients[client_id].country,
            'endpoint': endpoint
        }
        d = self.search_spotify_id_cached(params)

        def process(results):
            data = results['tracks']
            res['totalRecords'] = len(data)
            for row in data:
                item = {}
                item['title'] = row['name']
                item['itemid'] = row['uri']
                item['artist'] = row['artists'][0]['name']
                item['artistid'] = row['artists'][0]['uri']
                item['album'] = row['album']['name']
                item['albumid'] = row['album']['uri']
                item['artURI'] = self.get_image_uri(
                    row['album']['images'], 'albums')
                item['play_time'] = ms_to_str(row['duration_ms'],
                                              two_columns=True)
                res['results'].append(item)
            return res
        d.addCallback(process)
        return d

    def get_image_uri(self, images, category='artists'):
        if not images or not len(images):
            if category == 'artists':
                return 'icons/ArtistNoImage.png'
            else:
                return 'icons/NoImage.png'
        for i in range(len(images) - 1, 0, -1):
            if int(images[i]['width']) >= 300:
                return images[i]['url']
        return images[0]['url']

    # The search_spotify method is a wrapper that adds cancellation
    # to two other search methods. Each call of this method cancels
    # any prior call that hasn't completed.
    def search_spotify(self, params, sid, cached=True):
        self.search_cancel(sid)
        self.objects['search'].cancel(sid)

        def canceller(d):
            d.callback('CANCELLED')

        d1 = defer.Deferred(canceller)
        self.spotify_searches[sid].append(d1)

        def process(result):
            self.spotify_searches[sid].remove(d1)
            d1.callback(result)

        def error(e):
            if not e.check(defer.AlreadyCalledError):
                logError(e)

        if cached:
            d2 = self.search_spotify_cached(params)
        else:
            d2 = self.search_spotify_uncached(params)

        d2.addCallback(process)
        d2.addErrback(error)
        return d1

    def search_cancel(self, sid):
        if sid not in self.spotify_searches.keys():
            self.spotify_searches[sid] = []

        for d in self.spotify_searches[sid]:
            d.cancel()

    @cached
    def search_spotify_cached(self, params):
        return self.search_spotify_uncached(params)

    def search_spotify_uncached(self, params):
        if not self.clients:
            return
        client_id = params.get('client_id')
        if not client_id:
            client_id = list(self.clients.keys())[0]
        client = self.clients[client_id]
        return self.get(
            client_id,
            'https://api.spotify.com/v1/search',
            {
                'q': params['term'],
                'type': params['category'],
                'market': client.country,
                'limit': params['count'],
                'offset': params['index']
            }
        )

    def search_spotify_id(self, params, cached=True):
        if cached:
            return self.search_spotify_id_cached(params)
        else:
            return self.search_spotify_id_uncached(params)

    @cached
    def search_spotify_id_cached(self, params):
        return self.search_spotify_id_uncached(params)

    # There's a lot of ancient history embedded
    # in this method. It would be good one day to
    # simplify it
    def search_spotify_id_uncached(self, params):
        if not self.clients:
            return
        client_id = params.get('client_id')
        if not client_id:
            client_id = list(self.clients.keys())[0]
        client_id = params['client_id']
        client = self.clients[client_id]
        if 'no_params' in params.keys():
            params_parsed = None
        else:
            params_parsed = {}
            for key in params.keys():
                if key == 'client_id':
                    pass
                elif key == 'endpoint':
                    pass
                elif key == 'item_id':
                    pass
                elif key == 'country':
                    params_parsed['country'] = client.country
                elif key == 'count':
                    params_parsed['limit'] = params['count']
                elif key == 'index':
                    params_parsed['offset'] = params['index']
                else:
                    params_parsed[key] = params[key]
            if 'country' not in params_parsed.keys():
                params_parsed['market'] = client.country
        endpoint = params['endpoint']
        client_id = params['client_id']
        if 'item_id' in params:
            endpoint = endpoint.format(params['item_id'])
        return self.get(
            client_id,
            endpoint,
            params_parsed
        )

    def get(self, client_id, endpoint, params=None):
        return self.httpRequest(client_id, 'GET', endpoint, params)

    def post(self, client_id, endpoint, params=None, data=None):
        return self.httpRequest(client_id, 'POST', endpoint, params, data)

    @serialised2
    def httpRequest(self, client_id, method, endpoint, params=None, data=None):

        d = self.token(client_id)

        def request(token):
            url = endpoint
            headers = {}
            if token:
                headers['Authorization'] = ['Bearer ' + token]
            if params:
                p = urllib.parse.urlencode(params)
                url += '?' + p
            return httpRequest(method, url, headers, data, True)

        def process(result):
            if result:
                try:
                    data = json.loads(result)
                    return data
                except:
                    log.exception(
                        'There was a problem trying to access %s',
                        endpoint)

        d.addCallback(request)
        d.addCallback(process)
        d.addErrback(logError)
        return d

    def token(self, client_id):

        client = self.clients[client_id]

        if client.access_token:
            if int(time.time()) < client.expires_in:
                d = defer.Deferred()
                d.callback(client.access_token)
                return d

        if client.refresh_token:
            return self.refresh_access_token(
                client_id,
                client.refresh_token)

        return None

    def refresh_access_token(self, client_id, refresh_token):
        client = self.clients[client_id]
        url = 'https://accounts.spotify.com/api/token'
        headers = {
            'Content-Type': ['application/x-www-form-urlencoded']
        }
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': spotify_client_id
        }
        d = httpRequest('POST', url, headers, data)

        def process(result):
            if result:
                try:
                    data = json.loads(result)
                except:
                    log.exception(
                        'There was a problem trying to refresh the Spotify access token.')
                    return None

            if not result or 'access_token' not in data.keys() or 'expires_in' not in data.keys():
                log.warning(
                    'There was a problem trying to refresh the Spotify access token.')
                return None

            log.info('Refreshed Spotify access token.')
            client.access_token = data['access_token']
            client.expires_in = int(
                time.time()) + int(data['expires_in'])
            if 'refresh_token' in data:
                client.refresh_token = data['refresh_token']

            @dbpooled
            def save_token(tx, self, access_token, refresh_token, expires_in, client_id):
                query = '''	UPDATE spotify_auth SET
					 		access_token = ?,
                            refresh_token = ?,
							expires_in = ?
							WHERE client_id = ?'''
                tx.execute(query, (access_token, refresh_token,
                                   expires_in, client_id))
                return access_token

            return save_token(self,
                              client.access_token,
                              client.refresh_token,
                              client.expires_in,
                              client_id)
        d.addCallback(process)
        return d

    @serialised
    def startup(self):

        @dbpooled
        def get_info(tx, self):
            query = ''' SELECT * FROM spotify_auth '''
            tx.execute(query)
            return [dict(row) for row in tx.fetchall()]

        def process_info(rows):
            dlist = []

            for row in rows:
                client_id = row.pop('client_id')
                self.clients[client_id] = row
                d = self.get(client_id, 'https://api.spotify.com/v1/me')

                def process(result, client_id=client_id):
                    if result:
                        self.clients[client_id].country = result['country']

                d.addCallback(process)
                dlist.append(d)

            # Wait for all callbacks to complete
            return defer.DeferredList(dlist)

        d = get_info(self)
        d.addCallback(process_info)
        d.addErrback(logError)
        return d

    @serialised
    def auth(self, args):
        try:
            client_id = args.get('client_id', '')
            code_verifier = args.get('code_verifier', '')

            if client_id and code_verifier:

                self.auth_requests.append({
                    'client_id': client_id,
                    'code_verifier': code_verifier
                })

                return {
                    'spotify_client_id': spotify_client_id,
                    'redirect': redirect
                }
        except Exception as e:
            log.exception(e)

    @serialised
    def register_code(self, args):

        # client_id is set to args['state'], which is the UUID of the browser
        # window that initiated the authorisation request. This is not to be
        # confused with the spotify_client_id, being Spotify's identifier
        # for this application

        if 'state' not in args or args['state'] not in [item['client_id'] for item in self.auth_requests]:
            try:
                log.warning(
                    'There was a problem trying to obtain a Spotify access code')
                log.warning('self.auth_requests: {}'.format(
                    json.dumps(self.auth_requests)))
            except Exception as e:
                log.exception(e)
            response = '''<html><script>window.open('spotify_error.html', '_self')</script></html>'''
            return response

        code = args['code']
        client_id = args['state']

        for item in self.auth_requests:
            if item['client_id'] == client_id:
                code_verifier = item['code_verifier']
                self.auth_requests.remove(item)

        url = 'https://accounts.spotify.com/api/token'
        headers = {
            'Content-Type': ['application/x-www-form-urlencoded']
        }
        params = {
            'client_id': spotify_client_id,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect,
            'code_verifier': code_verifier
        }
        d = httpRequest('POST', url, headers, params)

        def error(warning):
            log.warning(warning)
            response = '''<html><script>window.open('spotify_error.html', '_self')</script></html>'''
            return response

        def process_token(result):
            if result:
                try:
                    data = json.loads(result)
                except Exception as e:
                    log.exception(e)
                    return error('There was a problem trying to obtain a Spotify access token - result load error')

            if not result or 'access_token' not in data.keys() or 'expires_in' not in data.keys():
                return error('There was a problem trying to obtain a Spotify access token - missing data')

            log.info('Received access tokens from Spotify.')
            self.clients[client_id] = {
                'access_token': data['access_token'],
                'expires_in': int(time.time()) + int(data['expires_in']),
                'refresh_token': data.get('refresh_token', None)
            }
            client = self.clients[client_id]
            d = self.get(client_id, 'https://api.spotify.com/v1/me')

            def process_spotify_user_info(result):

                @dbpooled
                def save_tokens(
                    tx,
                    self,
                    client_id,
                    user_id,
                    access_token,
                    refresh_token,
                        expires_in):
                    query = '''SELECT COUNT(*) FROM spotify_auth WHERE client_id = ?'''
                    tx.execute(query, (client_id,))
                    if tx.fetchone()[0]:
                        query = '''	UPDATE spotify_auth SET
									access_token = ?,
									refresh_token = ?,
									expires_in = ?,
                                    user_id = ?
									WHERE client_id = ?'''
                    else:
                        query = '''	INSERT INTO spotify_auth
								(access_token, refresh_token, expires_in, user_id, client_id)
								VALUES (?,?,?,?, ?)'''
                    tx.execute(query, (access_token,
                                       refresh_token, expires_in, user_id, client_id))

                def after(result=None):
                    response = '<html><script>{}</script></html>'
                    response = response.format(
                        '''window.open('spotify_success.html', '_self')''')
                    return response

                if 'id' not in result:
                    return error("There was a problem obtaining user's id. Please check app permissions")
                if 'country' not in result:
                    return error("There was a problem obtaining user's country. Aborting")
                client.user_id = result['id']
                client.country = result['country']
                d = save_tokens(
                    self,
                    client_id,
                    client.user_id,
                    client.access_token,
                    client.refresh_token,
                    client.expires_in
                )
                d.addCallback(after)
                return d

            d.addCallback(process_spotify_user_info)
            return d

        d.addCallback(process_token)
        return d
