# -*- coding: utf-8 -*-

from .error import logError
from .util import httpRequest
from .util import cached
from .util import dbpooled
from .util import serialised, database_serialised
from . import serialiser
import json
import urllib.parse
from logging import DEBUG
from .logging_setup import getLogger
log = getLogger(__name__)
log.setLevel(DEBUG)


class lastfm(object):

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']
        self.serialise = serialiser.Serialiser(
            'LastFM Serialiser').serialise
        self.api_key = '790325f35ac825539461f0a489d4f380'

    def get_related_artists(self, artist_name):

        @database_serialised
        @dbpooled
        def save_items(tx, self, reply):
            query = ''' INSERT INTO lastfm_artists (lastfm_url, lastfm_name)
                        VALUES (:url, :name)'''
            tx.executemany(
                query, reply)
            return reply

        def process_response(data):
            artists = []
            if 'similarartists' in data and 'artist' in data['similarartists']:
                artists = data['similarartists']['artist']
                reply = []
                for artist in artists:
                    item = {}
                    item['name'] = artist['name']
                    item['url'] = artist['url']
                    reply.append(item)
                return save_items(self, reply)
            else:
                log.warning(f'Did not get similar artists for: {artist_name}')

        def search():

            url = 'https://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist='
            url += urllib.parse.quote(artist_name.encode('utf8'))
            url += '&limit=20&autocorrect=1&api_key='
            url += self.api_key
            url += '&format=json'
            return self.search({'url': url})

        d = self.serialise(search)
        d.addCallback(process_response)
        d.addErrback(logError)
        return d

    def get_recommendations(self, spotify_track, limit, check_cancelled):

        @database_serialised
        @check_cancelled
        @dbpooled
        def save_items(tx, self, items):
            query = ''' INSERT INTO lastfm_tracks (lastfm_url, lastfm_name, lastfm_artist)
                        VALUES (:url, :name, :artist)'''
            tx.executemany(query, items)

        @check_cancelled
        def process_response(data):

            reply = {}
            reply['spotify_seed_uri'] = spotify_track['spotify_uri']
            reply['items'] = []

            if 'similartracks' in data and 'track' in data['similartracks']:
                tracks = data['similartracks']['track']
                for track in tracks:
                    item = {}
                    item['url'] = track['url']
                    item['name'] = track['name']
                    item['artist'] = track['artist']['name']
                    reply['items'].append(item)

            else:
                track = f"{spotify_track['spotify_artist']}/{spotify_track['spotify_title']}"
                log.warning(f'Did not get similar tracks for: {track}')

            @check_cancelled
            def finish(dummy):
                return reply

            d1 = save_items(self, reply['items'])
            d1.addCallback(finish)
            return d1

        @check_cancelled
        def search():
            url = 'https://ws.audioscrobbler.com/2.0/?method=track.getsimilar&artist='
            url += urllib.parse.quote(
                spotify_track['spotify_artist'].encode('utf8'))
            url += '&track='
            url += urllib.parse.quote(
                spotify_track['spotify_title'].encode('utf8'))
            url += '&limit='
            url += str(limit)
            url += '&autocorrect=1&api_key='
            url += self.api_key
            url += '&format=json'
            return self.search({'url': url})

        d = self.serialise(search)
        d.addCallback(process_response)
        d.addErrback(logError)
        return d

    @cached
    def search(self, args):

        def process(result):
            if result:
                try:
                    data = json.loads(result)
                    return data
                except:
                    log.exception(
                        'There was a problem trying to access {}'.format(args['url']))

        d = self.GET(args['url']).addErrback(logError)
        d.addCallback(process)
        return d

    def GET(self, url):
        return httpRequest('GET', url)
