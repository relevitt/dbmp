# -*- coding: utf-8 -*-

from .error import logError
from .paths import COVERPATH, WEBPATH, PLAYLISTPATH, ARTISTPATH, Musicpath
from .util import httpRequest
from .util import cached
from .util import database_serialised
from .util import dbpooled
from .util import serialised, serialised2
from . import serialiser
from twisted.python.failure import Failure
from twisted.internet import defer
import time
from shutil import copyfile
import json
import urllib.parse
from io import BytesIO
import os
from .logging_setup import getLogger
log = getLogger(__name__)


# string_clean is used to clean up the names of artists and albums
# when searching services like Spotify.
#
# Examples:
#
# >>> string_clean("Album Title DISC 1 and some extra text", 'disc')
# 'Album Title'
#
# >>> string_clean("Album Title (something random) a bit more", '(', ')')
# 'Album Title a bit more'


def string_clean(str, char1, char2=''):
    result = str
    while char1.lower() in result.lower():
        start = result.lower().rfind(char1.lower())
        end = result.lower().find(char2.lower())
        str1 = result[:start]
        if end == -1 or end == len(result)-1 or end < start:
            result = str1
        else:
            str2 = result[end+1:]
            if str1[-1] == str2[0] == ' ':
                str2 = str2.strip()
            result = str1 + str2
    if len(result.split()) >= 1:
        return result.strip()
    else:
        return str


cleanup_artist = cleanup_album = [('(',), ('[',), ('{',)]
cleanup_album += [('- disc',), ('-disc',), ('disc',),
                  ('- cd',), ('-cd',), ('cd',),
                  ('- deluxe',), ('-deluxe',), ('deluxe',),
                  ('- bonus',), ('-bonus',), ('bonus',),
                  ('- remastered',), ('-remastered',), ('remastered',)]


def clean(str, artist=False):
    cleanup = cleanup_artist if artist else cleanup_album
    for args in cleanup:
        str = string_clean(str, *args)
    return str


class covers(object):

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']
        self.db_player = objects['db_player']
        self.serialise = serialiser.Serialiser(
            'Coverart Check Covers Serialiser').serialise
        self.serialise2 = serialiser.Serialiser(
            'Coverart Playlist Cover Serialiser').serialise
        self.spotify_serialise = serialiser.Serialiser(
            'Coverart Spotify Slow Serialiser', 1).serialise
        self.google_serialise = serialiser.Serialiser(
            'Coverart Google Slow Serialiser', 1).serialise
        self.musicbrainz_serialise = serialiser.Serialiser(
            'Coverart Musicbrainz Slow Serialiser', 1).serialise
        self.coverartarchive_serialise = serialiser.Serialiser(
            'Coverart Coverartarchive Slow Serialiser', 0.25).serialise
        self.wikipedia_serialise = serialiser.Serialiser(
            'Coverart Wikipedia Slow Serialiser', 1).serialise
        self.HTTP_serialise = serialiser.Serialiser(
            'Coverart HTTP Serialiser').serialise
        self.check_covers()

    def listdir(self, path, directory=''):
        return self.objects['spfactory'].process_command('listdir', path, directory)

    def copy_blank_cover(self, blank, filename):
        try:
            copyfile(blank, filename)
            log.info('Saved blank file to {}'.format(filename))
            return True
        except:
            log.exception('Unable to copy %s to %s', blank, filename)
            return False

    def remove_file(self, filename):
        if not os.path.lexists(filename):
            return True
        try:
            os.remove(filename)
            return True
        except:
            log.exception('Unable to remove outdated file ... %s', filename)
            return False

# Periodically checks for missing covers

    def check_covers(self):

        # This performs a weekly check or, if a previous weekly
        # check was interrupted, continues from where it
        # stopped. The ids of 50 artists or albums are retrieved
        # at a time from the database and then the ids are checked
        # to see if they have artwork stored in the relevant
        # coverart directory. If artwork is missing, it is retrieved
        # failing which a blank cover is saved. This is done using
        # the same functions that are used to return covers to
        # clients, but without those functions returning an open
        # file descriptor

        @dbpooled
        def get_last_checked(tx, self):
            query = '''SELECT * FROM covers'''
            tx.execute(query)
            return tx.fetchone()

        def test_last_checked(results):
            now = time.time()
            if not results:
                update_covers('artist', 0)
            elif results['artist_last_id_updated']:
                update_covers('artist', results['artist_last_id_updated'])
            elif now - results['artist_last_searched'] > 604800:
                update_covers('artist', 0)
            elif results['album_last_id_updated']:
                update_covers('album', results['album_last_id_updated'])
            elif now - results['album_last_searched'] > 604800:
                update_covers('album', 0)

        def update_covers(search_type, last_searched):

            table = 'disc' if search_type == 'album' else 'artist'
            updater = self.get_cover if search_type == 'album' else self.get_artist

            @dbpooled
            def get_next_batch(tx, self):
                query = '''SELECT id FROM ''' + table + ''' WHERE id > ?
                            ORDER BY id LIMIT 50'''
                tx.execute(query, (last_searched,))
                return tx.fetchall()

            def process_results(results):
                d = None
                for result in results:
                    d = update_cover(self, result['id'])
                if d:
                    d.addCallback(update_database)
                    d.addCallback(run_next)

            @serialised
            def update_cover(self, result):
                def process():
                    return updater(result, True)

                def after(dummy):
                    return result
                d = process()
                d.addCallback(after)
                return d

            def update_database(result):

                @database_serialised
                @dbpooled
                def run(tx, self):
                    last_id_updated = result
                    query = '''SELECT MAX(id) AS id FROM ''' + table
                    tx.execute(query)
                    if tx.fetchone()['id'] == last_id_updated:
                        now = time.time()
                        query = '''UPDATE covers SET ''' + search_type + '''_last_searched = ?'''
                        tx.execute(query, (now,))
                        last_id_updated = 0
                    query = '''UPDATE covers SET ''' + search_type + '''_last_id_updated = ?'''
                    tx.execute(query, (last_id_updated,))

                return run(self)

            def run_next(result):
                self.check_covers()

            d = get_next_batch(self)
            d.addCallback(process_results)
            d.addErrback(logError)

        d = get_last_checked(self)
        d.addCallback(test_last_checked)
        d.addErrback(logError)


# Returns the coverfile for discid

    def get_cover(self, discid, only_check=False):

        # The search order is:
        #   -   artwork saved in the coverart directory
        #   -   artwork embedded in the first track's tag
        #   -   artwork found on musicbrainz / coverartarchive
        #   -   artwork found on spotify
        #   -   a blank file

        if int(discid) < 0:
            return

        coverfile = os.path.join(COVERPATH, str(discid) + '.jpg')

        services = [
            self.coverartarchive_get_cover,
            self.spotify_get_cover]

        var = {}

        @dbpooled
        def get_data(tx, self, discid):
            query = '''SELECT artist, disc.title AS title, filename FROM artist
                            JOIN disc ON disc.artistid = artist.id
                            JOIN song ON song.discid = disc.id 
                            WHERE disc.id = ?
                            ORDER BY track_num LIMIT 1'''
            tx.execute(query, (discid,))
            return tx.fetchone()

        def check_coverfile(results):

            try:
                if os.path.isfile(coverfile):
                    f = open(coverfile, 'rb')
                    d = defer.Deferred()
                    if only_check:
                        f.close()
                        d.callback(None)
                    else:
                        d.callback(f)
                    return d
            except:
                log.exception('Exception looking for saved cover')

            d = self.objects['spfactory'].process_command(
                'get_tagged_artwork',
                results['filename']
            )

            def check_error(result):
                if isinstance(result, Failure):
                    return None
                else:
                    return result

            def after(artwork):
                if artwork:
                    with open(coverfile, 'wb') as f:
                        f.write(artwork)
                    if only_check:
                        return
                    else:
                        return BytesIO(artwork)
                else:
                    var['title'] = clean(results['title'])
                    var['artist'] = clean(results['artist'], True)
                    return get_image_from_servers()

            d.addBoth(check_error)
            d.addCallback(after)
            return d

        def get_image_from_servers():
            service = services.pop(0)
            d = service({
                'title': var['title'],
                'artist': var['artist']})
            d.addCallback(replace)
            d.addCallback(check)
            d.addErrback(logError)
            return d

        def replace(url):
            if url:
                args = {}
                args['url'] = url
                args['albumid'] = discid
                return self.replace(args)
            else:
                return False

        def check(success):
            if not success:
                if len(services):
                    return get_image_from_servers()
                else:
                    icons = os.path.join(WEBPATH, 'icons')
                    blank = os.path.join(icons, 'NoImage.png')
                    if self.copy_blank_cover(blank, coverfile):
                        self.db_player.WS_artwork(discid, 'album')
            if os.path.isfile(coverfile):
                return open(coverfile, 'rb')

        d = get_data(self, discid)
        d.addCallback(check_coverfile)
        d.addErrback(logError)
        return d

# Returns the artwork for artistid

    def get_artist(self, artistid, only_check=False):

        # The search order is:
        #   -   artwork saved in the coverart directory
        #   -   artwork found on spotify
        #   -   a blank file

        coverfile = os.path.join(ARTISTPATH, str(artistid) + '.jpg')
        var = {}
        var['artist'] = None

        try:
            if os.path.isfile(coverfile):
                f = open(coverfile, 'rb')
                d = defer.Deferred()
                if only_check:
                    f.close()
                    d.callback(None)
                else:
                    d.callback(f)
                return d
        except:
            log.exception('Unable to send saved cover.')

        @dbpooled
        def get_data(tx, self, artistid):
            query = '''SELECT artist FROM artist
                            WHERE id = ?'''
            tx.execute(query, (artistid,))
            row = tx.fetchone()
            var['artist'] = row['artist']
            return var

        def replace(url):
            if url:
                args = {}
                args['url'] = url
                args['artistid'] = artistid
                return self.replace(args)
            return False

        def check(success):
            if not success:
                icons = os.path.join(WEBPATH, 'icons')
                blank = os.path.join(icons, 'ArtistNoImage.png')
                if self.copy_blank_cover(blank, coverfile):
                    self.db_player.WS_artwork(artistid, 'artist')
            if os.path.isfile(coverfile):
                return open(coverfile, 'rb')

        d = get_data(self, artistid)
        d.addCallback(self.spotify_get_cover)
        d.addCallback(replace)
        d.addErrback(logError)
        d.addCallback(check)
        d.addErrback(logError)
        return d

# get_playlist_cover

    # Not serialised as it seems pointless
    # to serialise opening of files, when the
    # subsequent reading of files is not
    # serialised. Would it be too slow to
    # serialise the reading? It would be more complicated.
    # Current approach means a file read may compete
    # with a separate attempt to remove or write it.
    # Will the operating system sort that out?

    def get_playlist_cover(self, playlist_id):

        filename = os.path.join(PLAYLISTPATH, playlist_id + '.jpg')
        d = defer.Deferred()

        try:
            if os.path.isfile(filename):
                f = open(filename, 'rb')
                d.callback(f)
            else:
                d.callback(None)
        except:
            log.exception('Unable to send saved cover.')
            d.callback(None)
        return d

# update_playlist_cover

    @serialised2
    def update_playlist_cover(self, playlist_id, uris):

        filename = os.path.join(PLAYLISTPATH, str(playlist_id) + '.jpg')
        timewas = self.get_playlist_cover_timestamps([playlist_id])[0]

        if not uris or not len(uris):
            log.info('No artwork uris found for playlist %s', playlist_id)
            icons = os.path.join(WEBPATH, 'icons')
            blank = os.path.join(icons, 'VariousArtists.png')
            self.copy_blank_cover(blank, filename)
            return

        if not self.remove_file(filename):
            return

        # This may be overkill, but we delegate playlist image
        # creation to a subprocess, so the main thread isn't locked.
        # Python has Global Interpreter Lock, so it seems pointless
        # to put this into a thread. Therefore, choices appear to be
        # creating image within the main thread or delegating it as
        # we've done here. Image creation seems quite quick,
        # which is why this may be overkill.

        d = self.objects['spfactory'].process_command(
            'coverart_make_image',
            filename,
            uris
        )

        def after(result=None):
            timeis = self.get_playlist_cover_timestamps([playlist_id])[0]
            self.db_player.WS_artwork(playlist_id, 'playlist', timewas, timeis)

        d.addCallback(after)
        d.addErrback(logError)
        return d

# get_playlist_cover_timestamps

    # As we don't serialise this, an old timestamp may be sent

    def get_playlist_cover_timestamps(self, playlist_ids):
        timestamps = []
        for playlist_id in playlist_ids:
            filename = os.path.join(PLAYLISTPATH, str(playlist_id) + '.jpg')
            try:
                timestamp = int(os.path.getmtime(filename))
            except:
                timestamp = int(time.time())
            timestamps.append(timestamp)
        return timestamps

# delete_cover

    def delete_cover(self, category, cid):
        directory = ''
        if category == 'album':
            directory = COVERPATH
        elif category == 'artist':
            directory = ARTISTPATH
        elif category == 'playlist':
            directory = PLAYLISTPATH
        filename = os.path.join(directory, str(cid) + '.jpg')
        if category == 'playlist':
            self.serialise2(self.remove_file, filename)
        else:
            self.remove_file(filename)

# musicbrainz/coverartarchive search

    def coverartarchive_get_cover(self, search_terms):

        # Musicbrainz is searched for ids of matching albums.
        # Coverart Archive is searched with a Musicbrainz id.
        # Not all albums have a Musicbrainz id.
        # Not all albums with a Musicbrainz id have artwork.
        # We search for the first 8 matching album ids on Musicbrainz and
        # return the first artwork uri we are able to find on Coverart Archive.
        # If none of the ids have artwork, we give up. As one Musicbrainz search
        # can generate up to eight Coverart Archive searches (plus another for
        # downloading the artwork), the serialiser for Coverart Archive
        # has been set for 0.25 second intervals (as opposed to 1s for
        # the other slow serialisers).

        queue = []

        def process_musicbrainz(data):
            for release in data.get('releases', []):
                queue.append(release)
            if len(queue):
                return search_coverartarchive()

        def search_coverartarchive():
            url = 'http://coverartarchive.org/release/' + queue.pop(0)['id']
            d = self.search({'url': url})
            d.addErrback(logError)
            d.addCallback(process_coverartarchive)
            d.addErrback(logError)
            return d

        def process_coverartarchive(data):
            try:
                images = data.get('images', [])
            except AttributeError:
                images = []
            for image in images:
                if image['front']:
                    return image['image']
            if len(queue):
                return search_coverartarchive()

        url = 'https://musicbrainz.org/ws/2/release/?query=release:'
        url += '%22' + \
            urllib.parse.quote(search_terms['title'].encode('utf8')) + '%22'
        url += '%20AND%20artistname:%22'
        url += urllib.parse.quote(
            search_terms['artist'].encode('utf8')) + '%22'
        url += '&limit=8'
        url += '&fmt=json'

        d = self.search({'url': url})
        d.addCallback(process_musicbrainz)
        d.addErrback(logError)
        return d

# Spotify search

    def spotify_get_cover(self, search_terms):

        def process(results):
            uri = ''
            data = list(results.values())[0]['items']
            if len(data):
                row = data[0]
                if 'album' in row.keys():
                    subrow = row['album']
                    uri = self.objects['spotify'].get_image_uri(
                        subrow['images'], 'albums')
                if 'images' in row.keys():
                    uri = self.objects['spotify'].get_image_uri(row['images'])
            return uri

        args = {}
        args['count'] = 1
        args['index'] = 0
        if 'title' in search_terms.keys():
            args['term'] = 'album:' + search_terms['title'] + \
                ' artist:' + search_terms['artist']
            args['category'] = 'album'
        else:
            args['term'] = 'artist:' + search_terms['artist']
            args['category'] = 'artist'

        d = self.spotify_serialise(
            self.objects['spotify'].search_spotify_uncached, args)
        d.addCallback(process)
        d.addErrback(logError)
        return d

# Wikipedia search

    def wikipedia_get_biography(self, args):

        def get_data():
            searchterm = args['id']
            res = {}
            res['startIndex'] = 0
            res['totalRecords'] = 1
            res['id'] = searchterm
            res['results'] = [{'metadata': [[], [], []], 'extract': ''}]
            url = 'https://en.wikipedia.org/w/api.php?'
            url += 'action=opensearch'
            url += '&search=' + \
                urllib.parse.quote(searchterm.encode('utf8'))
            url += '&limit=20&redirects=resolve'
            url += '&utf8=&format=json'

            d = self.search({'url': url})

            def process1(data):
                try:
                    if len(data[1]):
                        return process2(data)
                except:
                    log.exception('Problem in process1')
                log.warning(
                    'Could not retrieve data from Wikipedia for %s',
                    searchterm)
                return res

            def process2(data):

                d = self.wikipedia_get_biography_extract(data[1][0])

                def unpack(result):
                    res['results'][0] = {'metadata': data, 'extract': result}
                    return res

                d.addCallback(unpack)
                return d

            def error(e):
                logError(e)
                return res

            d.addCallback(process1)
            d.addErrback(error)
            return d

        return get_data()

    def wikipedia_get_biography_extract(self, searchterm):

        def get_data():
            url = 'https://en.wikipedia.org/w/api.php?'
            url += 'action=query'
            url += '&titles=' + \
                urllib.parse.quote(searchterm.encode('utf8'))
            url += '&prop=extracts'
            url += '&utf8=&format=json'
            d = self.search({'url': url})
            d.addCallback(unpack)
            d.addErrback(logError)
            return d

        def unpack(result):
            try:
                result = result['query']['pages']
                result = result[list(result.keys())[0]]
                return result['extract']
            except:
                log.exception('Problem in unpack')

        return get_data()

    def wikipedia_get_biography_page(self, args):

        return self.wikipedia_get_biography_extract(args['page'])

# Google search

    def google_get_cover(self, discid):

        # We are no longer using Google here (it is being used
        # on the Client), because there are often many google results
        # and the chances of getting something irrelevant are high,
        # especially when nothing was found on the other services
        # we are using. However, the method is beng kept here in
        # case we ever want to use or adapt it.

        @dbpooled
        def get_disc(tx, self, discid):
            query = '''SELECT artist, title FROM disc JOIN artist
				ON (disc.artistid = artist.id) WHERE disc.id = ?'''
            tx.execute(query, (discid,))
            return tx.fetchone()

        def get_data(row):
            query = row['artist'] + ' ' + row['title']
            query.replace(' ', '+')
            url = 'https://www.googleapis.com/customsearch/v1?'
            url += 'key=AIzaSyC5Pa3AjCI9gyBghQ4yQ80-bQ2UHzaFkT0'
            url += '&cx=013427824773846804726:jxnacxpuvkk'
            url += '&searchType=image'
            url += '&start=1'
            url += '&num=10'
            url += '&q=' + \
                urllib.parse.quote(query.encode('utf8'))

            log.info(
                'Searching Google for artwork for %s %s',
                row['artist'],
                row['title'])

            d = self.search({'url': url})

            def process(data):
                try:
                    urls = []
                    if data['items']:
                        for item in data['items']:
                            urls.append(item['link'])
                    log.info(
                        'Found artwork on Google for %s %s',
                        row['artist'],
                        row['title'])
                    return urls
                except:
                    log.exception(
                        'Could not retrieve artwork from Google for %s %s',
                        row['artist'],
                        row['title'])

            d.addCallback(process)
            d.addErrback(logError)
            return d

        d = get_disc(self, discid)
        d.addCallback(get_data)
        return d

# search

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

# get_coverfile

    def get_coverfile(self, args):
        coverfile = os.path.join(
            urllib.parse.unquote(args[0]),
            urllib.parse.unquote(args[1]))
        try:
            if os.path.isfile(coverfile):
                return open(coverfile, 'rb')
        except:
            log.exception('Unable to open image file')

# replace

    def replace(self, args):
        # TODO - stop calling these jpegs, as they might not be
        if 'artistid' in args.keys():
            filename = os.path.join(ARTISTPATH, str(args['artistid']) + '.jpg')
            item_id = args['artistid']
            category = 'artist'
        else:
            filename = os.path.join(COVERPATH, str(args['albumid']) + '.jpg')
            item_id = args['albumid']
            category = 'album'

        if not self.remove_file(filename):
            d = defer.Deferred()
            d.callback(False)
            return d

        d = self.GET(args['url'])

        def process(body):
            f = open(filename, 'wb')
            try:
                f.write(body)
                f.close()
                log.info('Image saved to %s', filename)
                return True  # The return value is checked for success in self.get_artist
            except Exception as e:
                log.exception('Problem writing data to file')
                print(e)
                return False

        def after(success):
            if success:
                self.db_player.WS_artwork(item_id, category)
            return success  # The return value is checked for success in self.get_artist

        d.addCallback(process)
        d.addCallback(after)
        return d

# remove

    def remove(self, args):
        if 'artistid' in args.keys():
            item_id = args['artistid']
            category = 'artist'
            filename = os.path.join(ARTISTPATH, str(item_id) + '.jpg')
        else:
            item_id = args['albumid']
            category = 'album'
            filename = os.path.join(COVERPATH, str(item_id) + '.jpg')
        if self.remove_file(filename):
            self.db_player.WS_artwork(item_id, category)

# open_albumdir

    def open_albumdir(self, args):
        @dbpooled
        def get_filename(tx, self, args):
            query = '''SELECT filename FROM song WHERE discid = ?'''
            tx.execute(query, (args['item_id'],))
            return tx.fetchone()[0]

        def process(filename):
            return self.listdir(os.path.dirname(filename))
        d = get_filename(self, args)
        d.addCallback(process)
        return d

# open_artistdir

    def open_artistdir(self, args):
        @dbpooled
        def get_filename(tx, self, args):
            query = '''SELECT filename FROM song WHERE artistid = ?'''
            tx.execute(query, (args['item_id'],))
            return tx.fetchone()[0]

        def process(path):
            while (os.path.dirname(path) != Musicpath.defaultpath) and (os.path.dirname(path) != path):
                path = os.path.dirname(path)
            return self.listdir(path)
        d = get_filename(self, args)
        d.addCallback(process)
        return d

    def GET(self, url):

        serialise = self.HTTP_serialise
        if "musicbrainz.org" in url:
            serialise = self.musicbrainz_serialise
        elif "coverartarchive.org" in url:
            serialise = self.coverartarchive_serialise
        elif "en.wikipedia.org" in url:
            serialise = self.wikipedia_serialise
        elif "googleapis.com" in url:
            serialise = self.google_serialise
        elif "spotify" in url:
            serialise = self.spotify_serialise

        return serialise(httpRequest, 'GET', url)
