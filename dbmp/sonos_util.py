# -*- coding: utf-8 -*-

from .util import get_track_range_tuples
from .util import create_album_art_uri
from .util import IP
from .util import serialised, serialised2, database_serialised
from .util import dbpooled
from .paths import Musicpath
from .config import PORT
from .config import SONOS_REGION_SPOTIFY as region
from .soco.data_structures import to_didl_string
from .soco.data_structures import DidlMusicTrack
from .soco.data_structures import DidlResource
from twisted.python.failure import Failure
from twisted.internet import defer
from twisted.internet import reactor
import numpy as nm
from json import dumps, loads
import weakref
import time
from urllib.parse import quote, unquote
import urllib.parse
import os
from .logging_setup import getLogger
log = getLogger(__name__)


SerialisedDataBase = serialised
SerialisedDevice = serialised2

SPOTIFY_REGIONS = {
    'EU': '2311',
    'US': '3079'
}

SPOTIFY_SERVICE = 'SA_RINCON{0}_X_#Svc{0}-0-Token'.format(
    SPOTIFY_REGIONS[region])

# Song - used to store, e.g., data obtained from a result['current_track_meta_data'] object returned in the avTransport event loop
# We put the definition here, because it gets used in various other modules.


class Song(object):

    def __init__(self, m=None, base_url=''):
        if m:
            try:
                artist = m.artist
            except:
                try:
                    artist = m.creator
                except:
                    artist = '[Unknown]'
            self.artist = artist
            if hasattr(m, 'album'):
                self.album = m.album
            else:
                self.album = '[None]'
            self.title = m.title
            if hasattr(m, 'album_art_uri'):
                if m.album_art_uri[0:4] == 'http':
                    self.album_art_uri = m.album_art_uri
                else:
                    raw_uri = base_url + m.album_art_uri
                    self.album_art_uri = "/get_cover?uri=" + quote(raw_uri)
            else:
                self.album_art_uri = None
            try:
                raw_uri = m.resources[0].uri
                decoded = urllib.parse.unquote(raw_uri)
                if decoded.startswith("x-sonos-spotify:"):
                    uri = decoded[len("x-sonos-spotify:"):].split('?')[0]
                else:
                    uri = decoded
                self.id = uri
            except:
                self.id = None
            self.length = m.resources[0].duration
        else:
            self.artist = None
            self.album = None
            self.title = None
            self.album_art_uri = None
            self.length = None
            self.id = None

    def equals(self, song):
        try:
            if self.id == song.id:
                return True
        except:
            return False
        return False

# get_server_base_uri


def get_server_base_uri():
    return 'http://{}:{}{}'.format(IP.IP, PORT, '/music/')


# get_filename_from_uri

def get_filename_from_uri(uri):
    server_base_uri = get_server_base_uri()
    if len(uri) > len(server_base_uri) and server_base_uri == uri[0:len(server_base_uri)]:
        return os.path.join(Musicpath.defaultpath, unquote(uri[len(server_base_uri):]))

# create_uri


def create_uri(filename):
    filename = os.path.relpath(filename, Musicpath.defaultpath)
    filename = os.path.join(*[quote(part.encode('utf8'))
                            for part in os.path.split(filename)])
    return get_server_base_uri() + filename

# sonos_util - adds utility functions to a sonos_group instance.


class sonos_util(object):

    @database_serialised
    @dbpooled
    def add_rows_to_db_queue(tx, self, rows, dest):

        def row_generator():
            for n, row in enumerate(rows):
                yield {
                    'groupid': self.group_uid,
                    'track_num': n + dest,
                    'album': row['album'],
                    'artist': row['artist'],
                    'song': row['song'],
                    'play_time': row['play_time'],
                    'id': row['id'],
                    'history': self.initialise_history()
                }
        query = '''	UPDATE sonos_queue_data
					SET track_num = track_num + ?
					WHERE groupid = ? AND track_num >= ?'''
        tx.execute(query, (len(rows), self.group_uid, dest))
        query = '''	INSERT INTO sonos_queue_data (groupid, track_num,
					 album, artist, song, play_time, id, history)
					VALUES(:groupid, :track_num, :album, :artist,
					:song, :play_time, :id, :history)'''
        tx.executemany(query, row_generator())
        return rows

    def get_albumid(self, s):
        try:
            ip = urllib.parse.urlparse(
                s.album_art_uri).netloc.partition(':')[0]
            if ip == IP.IP:
                i = int(urllib.parse.urlparse(
                    s.album_art_uri).query.partition('=')[2])
                return i
        except:
            pass
        return None

    def convert_art_uri(self, s):
        @dbpooled
        def get_art_uri(tx, self, track, art_uri):
            query = '''	SELECT artURI FROM spotify_track_cache
						WHERE songid = ?'''
            result = tx.execute(query, (track,))
            if not result:
                return art_uri
            result = tx.fetchone()
            if result:
                result = result[0]
            return result or art_uri

        if s.id and 'x-sonos-spotify' in str(s.id):
            uri = unquote(s.id)
            track = uri.split(':', 1)[1].split('?')[0]
            return get_art_uri(self, track, s.album_art_uri)

        else:
            d = defer.Deferred()
            d.callback(s.album_art_uri)
            return d

    def move_in_queue(self, old_pos, new_pos, no_update_id=False):
        if self.status.device_error:
            raise Exception('Stopping operation because of prior device error')
        # For some reason shuffle causes updateid problems.
        next_updateid = 0 if no_update_id else self.status.updateid + 1
        uid = 0 if no_update_id else self.status.updateid
        d = self.device.avTransport.ReorderTracksInQueue([
            ('InstanceID', 0),
            ('StartingIndex', old_pos),
            ('NumberOfTracks', 1),
            ('InsertBefore', new_pos),
            ('UpdateID', uid)
        ])

        def after(response):
            if isinstance(response, Failure):
                log.warning(
                    'In sonos_util.move_in_queue: Sonos device error. Aborting move.')
                response.trap()
            self.update_update_id(next_updateid)

        d.addBoth(after)
        return d

    def update_transition(self, state):

        now = time.time()
        state_was = self.status.transport_state

        self.status.last_transition_time = now
        self.WS_status(state, event=False)

        # It can take Sonos time to notify that it
        # has changed state

        if self.status.updating_transport_state:
            self.status.updating_transport_state.reset(3)
            return

        def restore_state():
            self.status.updating_transport_state = None
            if now > self.status.last_WS_status_time:
                self.WS_status(state_was, event=False)

        self.status.updating_transport_state = reactor.callLater(
            3, restore_state)

    def play_after_adding(self, pos, time, now=False):
        if not pos:
            return
        pos -= 1
        if time < self.status.last_transition_time:
            return
        if self.status.set_queue_requested:
            return
        if self.status.transport_state != 'PLAYING' or now:
            self.update_queue_position(find_pos=pos)
            self.go_to_queue_pos(pos)

    def get_spotify_track_codes(self, item_id):

        item_id = quote(item_id)
        # uri = "soco://{}?sid={}&sn={}".format(
        # item_id, service['service_id'],
        # service['account_serial_number']
        # )
        uri = "x-sonos-spotify://{}".format(item_id)

        meta = '''<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" \
xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" \
xmlns:r="urn:schemas-rinconnetworks-com:metadata-1-0/" \
xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">\
<item id="{}" parentID="DUMMY" restricted="true">\
<dc:title>DUMMY</dc:title>\
<upnp:class>object.item.audioItem.musicTrack</upnp:class>\
<desc id="cdudn" nameSpace="urn:schemas-rinconnetworks-com:metadata-1-0/">{}</desc>\
</item></DIDL-Lite>'''.format('0fffffff{}'.format(item_id), SPOTIFY_SERVICE)

        return (uri, meta)

    def get_spotify_container_codes(self, item_id):

        # Until Sonos API catches up ...
        if "spotify:playlist:" in item_id:
            item_id = "spotify:user:IGNORED:playlist:" + item_id.split(':')[2]

        item_id = '0fffffff{}'.format(quote(item_id))
        meta = '''<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" \
xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" \
xmlns:r="urn:schemas-rinconnetworks-com:metadata-1-0/" \
xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">\
<item id="{}" parentID="DUMMY" restricted="true">\
<dc:title>DUMMY</dc:title>\
<upnp:class>object.container.album.musicAlbum</upnp:class>\
<desc id="cdudn" nameSpace="urn:schemas-rinconnetworks-com:metadata-1-0/">{}</desc>\
</item></DIDL-Lite>'''.format(item_id, SPOTIFY_SERVICE)

        uri = 'x-rincon-cpcontainer:' + item_id

        return (uri, meta)

    def get_database_trackcodes(
            self,
            row,
            meta=None,
            uri=None,
            album_art_uri=None):

        meta = meta or row
        if uri is None:
            uri = create_uri(row['filename'])
        if album_art_uri is None:
            album_art_uri = create_album_art_uri(
                meta['discid'],
                meta['artwork_update'])
        duration = None
        if row['play_time']:
            if len(row['play_time'].split(':')) == 3:
                duration = ''
            else:
                duration = '0:'  # add an empty hours column
            duration += row['play_time']

        res = [DidlResource(uri=uri,
                            protocol_info='x-rincon-playlist:*:*:*s',
                            duration=duration
                            )]
        item = DidlMusicTrack(
            resources=res,
            title=row['song'],
            parent_id='',
            item_id='',
            artist=meta['artist'],
            album=meta['album'],
            album_art_uri=album_art_uri
        )
        metadata = to_didl_string(item)
        return (uri, metadata)

    def add_spotify_track_to_queue(self, item_id, pos=0):
        uri, meta = self.get_spotify_track_codes(item_id)
        return self.add_uri_to_queue(uri, meta, pos)

    def add_spotify_container_to_queue(self, item_id, pos=0):
        uri, meta = self.get_spotify_container_codes(item_id)
        return self.add_uri_to_queue(uri, meta, pos)

    def add_row_to_queue(self, row, meta=None, pos=0):
        uri, metadata = self.get_database_trackcodes(row, meta)
        return self.add_uri_to_queue(uri, metadata, pos)

    def add_uri_to_queue(self, uri, meta, pos=0):

        next_updateid = self.status.updateid + 1

        d = self.device.avTransport.AddURIToQueue([
            ('InstanceID', 0),
            ('EnqueuedURI', uri),
            ('EnqueuedURIMetaData', meta),
            ('DesiredFirstTrackNumberEnqueued', pos),
            ('EnqueueAsNext', 0 if pos else 1)
        ])

        def after(response):
            if isinstance(response, Failure):
                log.warning(
                    'In sonos_util.add_uri_to_queue: Sonos device error. Aborting add.')
                response.trap()
            self.update_update_id(next_updateid)
            return int(response['FirstTrackNumberEnqueued'])

        d.addBoth(after)
        return d

    def add_multiple_uris_to_queue(self, items, pos=0):

        # items: a list in the form [[uri, meta], [uri, meta] ...]
        # pos: desired first position, otherwise, everything is added at end

        chunk_size = 16  # With each request, we can add only 16 items
        var = {}
        var['first_track'] = 0  # return value
        var['num_added'] = 0  # return value
        var['pos'] = pos
        var['index'] = 0

        def add_chunk():
            if (var['index'] < len(items)) and not self.STOP_OPS:
                if self.status.device_error and var['pos']:
                    raise Exception(
                        'Stopping operation because of prior device error')
                # We compute next_updateid so that operations can fail where
                # appropriate if there has been an intervening external
                # device operation (e.g. from phone)
                var['next_updateid'] = self.status.updateid + 1
                chunk = items[var['index']:var['index'] + chunk_size]
                var['index'] += len(chunk)
                uris = ' '.join([item[0] for item in chunk])
                meta = ' '.join([item[1] for item in chunk])
                d = self.device.avTransport.AddMultipleURIsToQueue([
                    ('InstanceID', 0),
                    # Don't provide UpdateID if tracks are being added to end of
                    # the queue, as the add should be able to succeed regardless
                    ('UpdateID',
                     self.status.updateid if var['pos'] else 0),
                    ('NumberOfURIs', len(chunk)),
                    ('EnqueuedURIs', uris),
                    ('EnqueuedURIsMetaData', meta),
                    ('ContainerURI', ''),
                    ('ContainerMetaData', ''),
                    ('DesiredFirstTrackNumberEnqueued', var['pos']),
                    ('EnqueueAsNext', 0 if var['pos'] else 1)
                ])
                d.addBoth(after)
                return d
            else:
                d = defer.Deferred()
                d.callback((var['first_track'], var['num_added']))
                return d

        def after(response):
            if isinstance(response, Failure):
                log.warning(
                    'In sonos_util.add_multiple_uris_to_queue: Sonos device error. Aborting add.')
                response.trap()
            self.update_update_id(var['next_updateid'])
            first_track = int(response['FirstTrackNumberEnqueued'])
            num_added = int(response['NumTracksAdded'])
            if not var['first_track'] and first_track:  # we haven't yet set first_track
                var['first_track'] = first_track
            if var['pos'] and num_added:
                var['pos'] += num_added
            var['num_added'] += num_added
            return add_chunk()

        return add_chunk()

    def remove_tracks_from_queue(self, li):
        '''
        Removes tracks from the Sonos Queue: li must be a list of tracks positions
        for deletion, sorted in descending order. The first position in the queue is 0.
        '''

        items = get_track_range_tuples(li)
        var = {}

        def remove_queue_rows():
            if len(items):
                if self.status.device_error and var['pos']:
                    raise Exception(
                        'Stopping operation because of prior device error')
                # We compute next_updateid so that operations can fail where
                # appropriate if there has been an intervening external
                # device operation (e.g. from phone)
                var['next_updateid'] = self.status.updateid + 1
                StartingIndex, NumberOfTracks = items.pop(0)
                d = self.device.avTransport.RemoveTrackRangeFromQueue([
                    ('InstanceID', 0),
                    ('UpdateID', self.status.updateid),
                    ('StartingIndex', StartingIndex + 1),
                    ('NumberOfTracks', NumberOfTracks)
                ])
                d.addBoth(after)
                return d

        def after(response):
            if isinstance(response, Failure):
                log.warning(
                    'In remove_tracks_from_queue: Sonos device error. Aborting remove.')
                response.trap()
            self.update_update_id(var['next_updateid'])
            return remove_queue_rows()

        return remove_queue_rows()

    def update_update_id(self, next_updateid):
        if self.status.updateid < next_updateid:
            self.status.updateid = next_updateid

    def increment_history(self):

        # The history column in sonos_queue_data contains the track_num history
        # of each item in the queue, if the queue has pending or incomplete
        # device operations. The history column contains a text field
        # which when json decoded is a list with the row's track_num
        # history. The track_num of each row represents its track_num as it
        # will be after all device operations have completed. The first
        # item in the history list is the row's current position on the
        # device (or, while an operation is being executed, the row's
        # position on the device before execution started). If a track
        # is being added to the queue, the first item in the row's history
        # list will be None, to show that it didn't previously exist in the
        # queue. Care is needed when testing the state of an item in the
        # history list, because position 0 is valid. Depending on how you
        # frame your test, it could return True for a value of 0, when you
        # are testing for a value of None. Whenever a move / delete / add
        # operation is executed, the history column first needs to be
        # incremented, by appending each row's track_num to its history list.
        # After this has happened, the sonos_queue_data table can be processed
        # so that it reflects the position as it will be after the operation
        # has been completed. After a device operation has completed, each
        # history list must be decremented by popping the first item in the
        # list. The new first item in each history list represents the row's
        # position on the device before the next device operation commences.
        # When all device operations have completed, each history list is
        # empty. This is also the default value of the history column.

        self.status.pending_device_updates += 1

        @database_serialised
        def increment(self):
            def process(conn):

                var = {}
                var['first'] = True

                def update_history(track_num, history):
                    try:
                        li = loads(history)
                        li.append(track_num)
                    except Exception as e:
                        if var['first']:
                            log.exception(Failure(e))
                            var['first'] = False
                        li = [track_num]
                    return dumps(li)

                w_update_history = weakref.ref(update_history)

                conn.create_function(
                    'UPDATE_HISTORY',
                    2,
                    lambda x, y: w_update_history()(x, y))

                tx = conn.cursor()

                query = ''' UPDATE sonos_queue_data
                            SET history = UPDATE_HISTORY(track_num, history)
                            WHERE groupid = ?'''

                tx.execute(query, (self.group_uid,))

            return self.dbpool.runWithConnection(process)
        return increment(self)

    def initialise_history(self):
        # This is used when adding a new row to sonos_queue_data. As the row
        # didn't previously exist, its history list must be the same length
        # as the others in the table, but with each item in its list set to
        # None to show it didn't previously exist in the table.
        history = [None for n in range(self.status.pending_device_updates)]
        return dumps(history)

    def decrement_history(self):
        # Please read the notes for increment_history

        if self.status.set_queue_requested:
            self.status.set_queue_requested.pop(0)
            self.check_set_queue()
        self.status.pending_device_updates -= 1

        # Perhaps this could happen on a clear?
        # Clear resets self.status.pending_device_updates
        # to zero. Presumably an operation in execution
        # could decrement the counter to be less than zero
        if self.status.pending_device_updates < 0:
            self.status.pending_device_updates = 0
            return

        @database_serialised
        def decrement(self):
            def process(conn):

                def update_history(history):
                    try:
                        li = loads(history)
                        li.pop(0)
                    except Exception as e:
                        log.exception(Failure(e))
                        li = []
                    return dumps(li)

                w_update_history = weakref.ref(update_history)

                conn.create_function(
                    'UPDATE_HISTORY',
                    1,
                    lambda x: w_update_history()(x))

                tx = conn.cursor()

                query = ''' UPDATE sonos_queue_data
                            SET history = UPDATE_HISTORY(history)
                            WHERE groupid = ?'''

                tx.execute(query, (self.group_uid,))

            return self.dbpool.runWithConnection(process)
        return decrement(self)

    @database_serialised
    @dbpooled
    def get_history(tx, self, track_num):
        # This method is used by set_queue_position. It retrieves the
        # the relevant row's history list from sonos_queue_data and then
        # appends the row's track_num to the end of the history list.
        # The history list can be used to determine where to set the
        # queue position on the device, if it is lagging behind the
        # user's display. The user's display should show the track_num
        # as it will be after all device operations have completed, i.e.
        # the position appended to the end of the history list returned
        # by this method.

        query = ''' SELECT history FROM sonos_queue_data
                    WHERE groupid = ?
                    AND track_num = ?'''
        tx.execute(query, (self.group_uid, track_num))
        history = loads(tx.fetchone()[0])
        history.append(track_num)
        return history

    def check_set_queue(self, interim=None):
        # The self.status.set_queue_requested flag is set to None unless
        # the user has issued a set_queue_position instruction, in which
        # case it is set to contain the history object returned by
        # get_history. This method is called to check for such an instruction
        # and process it when the relevant item has been added to the queue
        # (if it didn't previously exist) at a safe point between device
        # operations. In the case of move / delete operations, the safe point
        # is when the pending operation has completed. These operations are
        # processed relatively fast by the device, so the user shouldn't
        # experience much delay.

        if not self.status.set_queue_requested:
            return
        self._WS_queue_position(self.status.set_queue_requested[-1])
        pos = self.status.set_queue_requested[0]
        if interim:
            if pos != None:
                if pos >= interim['dest']:
                    pos += interim['added']
            else:
                next = self.status.set_queue_requested[1]
                done = interim['dest'] + interim['added']
                if next != None and next <= done:
                    pos = next
        if pos != None:
            self.status.set_queue_requested = None
            self.WS_set_queue_alert(False)
            self.go_to_queue_pos(pos)

    def go_to_queue_pos(self, pos):

        device_uid = self.group_uid.split(':')[0]
        queue_uri = 'x-rincon-queue:{0}#0'.format(device_uid)

        def process(result):
            set_queue = False
            if result['CurrentURI'] != queue_uri:
                set_queue = True
                self.device.avTransport.SetAVTransportURI([
                    ('InstanceID', 0),
                    ('CurrentURI', queue_uri),
                    ('CurrentURIMetaData', '')
                ])
            if set_queue and (pos == 0):
                self.device.seek_zero()
            else:
                self.device.avTransport.Seek([
                    ('InstanceID', 0),
                    ('Unit', 'TRACK_NR'),
                    ('Target', pos+1)
                ])
            self.update_transition('PLAYING')
            self.device.play()

        self.device.avTransport.GetMediaInfo(
            [('InstanceID', 0)]).addCallback(process)

    # Pass through any data received,
    # so this function can be chained in callbacks
    def update_queue_position(self, data=None, find_pos=None):

        # If called without the find_pos parameter, this method finds what the
        # the current queue position on the device will become once the next
        # device operation has completed. Clients are informed of the new position
        # and the status of the sonos_group object is updated.
        #
        # As this method is executed directly after the sonos_queue has been
        # updated and before the next @SerialisedDataBase method is executed,
        # we use the most recently appended history item.
        #
        # For example, suppose three operations are scheduled by a client in
        # quick succession, and the impact on the row representing the current
        # queue position is as follows:
        #
        #   Operation:             track_num:       history:
        #
        #   0 (before we start)    10               []
        #   1                      20               [10]
        #   2                      30               [10, 20]
        #   3                      40               [10, 20, 30]
        #
        # When operation 1 commences and sonos_queue_data is updated, this method
        # will look up the track_num whose history's latest addition
        # corresponds to the current queue position of 10. This is track_num 20.
        # Therefore the sonos_group's status is updated to reflect the current
        # position is now 20 and clients are informed.
        #
        # When operation 2 commences, this method looks up the track_num whose
        # history's latest addition corresponds to the current queue position of
        # 20. This is track_num 30. When operation 3 commences, this method is
        # looking for the track_num whose history's latest addition corresponds
        # to the current position of 30. This is track_num 40. So track_num 10
        # became 20, then 30, then 40.
        #
        # What if the track now playing is deleted? As we'd expect, it will no
        # longer appear in the most recent place in any history object. In these
        # circumstances, the sonos device will move to the next position in the
        # queue, unless there is no next position in the queue, in which case it
        # will go to the previous position in the queue. Therefore, we are not
        # searching the histories for an exact correlation, but rather for the
        # closest higher track position, failing which, the closest lower track
        # position.
        #
        # This is done by creating a list of last history items and then copying
        # that list to a numpty array. The numpty array is sorted into ascending
        # track numbers. We ask numpty where the current position would go if it
        # were inserted into the array in ascending order. For example, the number
        # 7 would be inserted into the array [0, 1, 3, 5, 10, 11, 12] before
        # the number 10. Numpty therefore returns the index of 10, which is 4.
        # In the real world, if track 7 were playing, and tracks 6, 7, 8 and 9
        # were removed from the queue, sonos would start playing track 10.
        # Using the numpty index of 4, we can obtain track 10 from the array. Now
        # that we know the current position will shift from 7 to 10, we know that
        # we are looking for position 10 in the histories. List.index()
        # can be used to find where position 10 now is in the index. In the above
        # example, if there were no other changes, it would indeed be position 4.
        # However, if the queue had been shuffled before deletions were made,
        # the old track_nums would no longer appear in ascending order in the list.
        #
        # If find_pos is provided, that means we are about to set the queue
        # position during a device update, as a result of adding
        # tracks and starting to play the first added. We know the position where
        # that track has just been added on the device (because the device reports
        # this back) but we need to know what position that track will end up in
        # as a result of other pending operations. The position at history[0]
        # reflects track positions as they were before the current device update, while
        # the position at history[1] reflects track positions as they will be after
        # the current operation. Therefore, we use history[1] if there are other
        # pending operations. If not, the find_pos provided is the final position.

        pos_was = int(self.status.queue_position) - 1

        @database_serialised
        @dbpooled
        def queue_position(tx, self):

            query = ''' SELECT history from sonos_queue_data
                        WHERE groupid = ? 
                        ORDER BY track_num'''

            tx.execute(query, (self.group_uid,))
            results = tx.fetchall()
            if not results:
                return 0
            if not find_pos:
                def get_pos(h):
                    pos = loads(h[0])[-1]
                    return pos if pos != None else -1
                li = [get_pos(h) for h in results]
                ar = nm.array(li)
                ar.sort()
                index = min(nm.searchsorted(ar, pos_was), len(ar) - 1)
                closest = ar[index]
                if closest == -1:
                    return 0
                new_pos = li.index(closest)
            else:
                li = [loads(h[0])[1] for h in results]
                new_pos = li.index(find_pos)
            return new_pos

        if find_pos and self.status.pending_device_updates == 1:
            d = defer.Deferred()
            d.callback(find_pos)
        else:
            d = queue_position(self)
        d.addCallback(lambda pos: self._WS_queue_position(pos=pos))
        return data
