# -*- coding: utf-8 -*-

from .sonos_util import SerialisedDevice, SerialisedDataBase
from .sonos_util import get_filename_from_uri
from .sonos_util import Song
from .sonos_util import sonos_util
from .sonos_client import sonos_client
from .sonos_WS import sonos_factory_WS
from .sonos_WS import sonos_group_WS
from .util import dbpooled
from .util import IP
from .util import serialised, database_serialised
from .error import logError
from . import serialiser
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
import time
from urllib.parse import unquote
from .logging_setup import getLogger
log = getLogger(__name__)


# sonos_status - mainly used by a sonos_group object to track info
# received from event loops


class sonos_status(object):

    def __init__(self):

        self.transport_state = 'STOPPED'
        self.song_progress = '0:00:00'
        self.queue_position = '0'
        self.queue_contents = '0'
        self.song = Song()
        self.volume = {
            'Group Volume': 0
        }
        self.mute = {
            'Group Volume': 0
        }
        self.updating_position = False
        self.updating_contents = False
        self.updateid = 0
        self.last_notified_updateid = 0
        self.device_error = False
        self.last_reconcile = 0
        self.updating_transport_state = None
        self.last_transition_time = 0
        self.last_WS_status_time = 0
        self.pending_device_updates = 0
        self.set_queue_requested = None
        self.playing_from_queue = False

# sonos_service - interface to a service of a soco device running in a
# subprocess


class sonos_service(object):

    def __init__(self, service, device):
        self.service = service
        self.device = device
        self.commands = []

    def __getattr__(self, action):
        self.commands.append(action)

        def _dispatcher(*args, **kwargs):
            """Dispatch to send_command."""
            return self.device.send_command('SoCo.service', self.service, action, *args, **kwargs)
        _dispatcher.__name__ = action
        setattr(self, action, _dispatcher)
        return _dispatcher

    def shutdown(self):
        # Break circular references
        # Required for efficient garbage collection
        self.device = None
        for command in self.commands:
            delattr(self, command)

# sonos_device - interface to a soco device running in a subprocess


class sonos_device(object):

    def __init__(self, subprocess, uid):
        self.subprocess = subprocess
        self.uid = uid
        self.services = ['avTransport', 'GroupRenderingControl']
        self.commands = []
        self.has_been_shutdown = False
        for service in self.services:
            setattr(self, service, sonos_service(service, self))

    def __getattr__(self, action):
        def _dispatcher(*args, **kwargs):
            """Dispatch to send_command."""
            return self.send_command('SoCo.device', action, *args, **kwargs)
        _dispatcher.__name__ = action
        setattr(self, action, _dispatcher)
        self.commands.append(action)
        return _dispatcher

    def send_command(self, command, *args, **kwargs):
        return self.subprocess.process_command(command, self.uid, *args, **kwargs)

    def shutdown(self):
        if self.has_been_shutdown:
            return
        self.has_been_shutdown = True
        # Break circular references
        # Required for efficient garbage collection
        for service in self.services:
            s = getattr(self, service)
            s.shutdown()
            delattr(self, service)
        for command in self.commands:
            delattr(self, command)

# sonos_group - represents a single group; most action occurs here


class sonos_group(sonos_group_WS, sonos_client, sonos_util):

    def __init__(
            self,
            group_name,
            group_uid,
            coordinator,
            devices,
            base_url,
            system_version,
            factory):

        self.name = group_name
        self.group_uid = group_uid
        self.device = coordinator
        self.devices = devices
        self.base_url = base_url
        self.system_version = system_version
        self.factory = factory
        self.objects = self.factory.objects
        self.db_serialiser = serialiser.Serialiser(
            '{} DataBase Serialiser'.format(self.name))
        self.device_serialiser = serialiser.Serialiser(
            '{} Device Serialiser'.format(self.name))
        self.serialise = self.db_serialiser.serialise
        self.serialise2 = self.device_serialiser.serialise
        self.dbpool = self.factory.dbpool
        self.multizone = False
        self.status = sonos_status()
        self.volume_controls_init()
        self.STOP_OPS = False  # Used by queue_clear
        self.shutting_down = False
        self.serialise(self._set_updateid)
        self.serialise(self._reconcile_queue)
        sonos_group_WS.__init__(self)

    def shutdown(self):
        self.shutting_down = True

        def final_clean_up():
            self.serialise = None
            self.serialise2 = None
            self.device_serialiser = None
            self.db_serialiser = None
            self.objects = None

        def shutdown(self):
            self.WS_shutdown()
            self.factory = None
            self.device.shutdown()
            self.device = None
            self.devices = None
            self.status = None
            # Delay shutting down queues by 5 seconds so
            # pending processes have a chance to complete
            reactor.callLater(5, self.db_serialiser.close_queue)
            reactor.callLater(5, self.device_serialiser.close_queue)
            reactor.callLater(10, final_clean_up)

        shutdown(self)

    def volume_controls_init(self):
        if len(self.devices) > 1:
            self.multizone = True
            for name in self.devices.keys():
                self.status.volume[name] = 0
                self.status.mute[name] = 0

    # We keep a copy of the device queue in the database, because adding
    # items to the device queue can be time consuming (with a long database
    # playlist, it could take minutes) and the client interface would
    # be unresponsive. Thus:
    #
    # -	We load a copy of the device queue into the database at startup.
    #
    # -	Whenever we change the device queue, we preemptively update
    # the database copy (i.e. we update the database copy before we
    # change the device queue, on the basis that the changes to
    # the device queue will be successful).
    #
    # -	When event notifications show the device queue has changed,
    # we reconcile the database copy against the device queue.
    #
    # -	If the reconciliation shows a mismatch, we reload a copy of
    # the device queue into the database.
    #
    # -	A reconciliation mismatch could occur because our changes to the
    # device queue were unsuccessful or because the device queue was changed
    # by another application (e.g. Sonos mobile phone app).
    #
    # -	When the client requests a copy of the device queue, we take this
    # copy from the database. This is part of what improves
    # responsiveness.
    #
    # -	We inform clients the queue has changed (via the WS system) whenever
    # (and as soon as) the database copy changes. This is the other part
    # of what improves responsiveness. This notification occurs when the
    # database copy is updated preemptively before the device
    # queue is changed and when we reload a copy of the device queue into
    # the database because there was a reconciliation mismatch.

    @SerialisedDataBase
    @SerialisedDevice
    def set_updateid(self):
        return self._set_updateid()

    def _set_updateid(self):
        def process(updateid):

            # This is to fix an error that results from an S1 device notifying
            # a queue change after a ZGT change. By the time we reach this
            # callback, the group might have been shut down
            if not self.status:
                return

            updateid = int(updateid)
            self.status.updateid = updateid
            self.status.last_reconcile = updateid
            msg = '{} set updateid: {}'.format(
                self.name,
                updateid
            )
            log.info(msg)
        d = self.device.get_update_id()
        d.addCallback(process)
        return d

    @SerialisedDataBase
    @SerialisedDevice
    def reconcile_queue(self):
        return self._reconcile_queue()

    @defer.inlineCallbacks
    def _reconcile_queue(self):

        var = {}
        var['start'] = 0
        var['mismatch'] = False
        var['snapshot_id'] = None
        num = 100

        def process_queue(results):
            if self.device is None:
                return cleanup(self)
            start = var['start']
            var['start'] += len(results)
            if not var['mismatch']:
                return check(self, results, start)
            else:
                return sync(self, results, start)

        @database_serialised
        @dbpooled
        def check(tx, self, results, start=0):
            if not start:
                query = ''' SELECT snapshot_id
                            FROM sonos_queues
                            WHERE groupid = ?'''
                tx.execute(query, (self.group_uid,))
                row = tx.fetchone()
                if row:
                    var['snapshot_id'] = row[0]
                else:
                    query = ''' INSERT INTO sonos_queues (groupid)
                                VALUES (?)'''
                    tx.execute(query, (self.group_uid,))
                    var['snapshot_id'] = 1

            query = '''	CREATE TEMP TABLE tmp_data
				   		(pos INTEGER PRIMARY KEY ASC, id TEXT)'''
            tx.execute(query)
            query = '''	INSERT INTO tmp_data (id)
						VALUES(:id)'''

            def rows():
                for row in results:
                    yield {'id': row['id']}
            tx.executemany(query, rows())
            query = '''	SELECT COUNT(*), *
						FROM
						(
							SELECT pos + ? - 1 as track_num, id
							FROM tmp_data
							UNION ALL
							SELECT track_num, id
							FROM sonos_queue_data
							WHERE groupid = ? AND track_num >= ? AND track_num < ?
						) tmp
						GROUP BY track_num, id
						HAVING COUNT(*) = 1
						ORDER BY track_num'''
            tx.execute(query, (start, self.group_uid, start, start + num))
            result = tx.fetchall()
            if len(result):
                var['mismatch'] = True
                var['start'] = start
                query = ''' DELETE FROM sonos_queue_data
                			WHERE groupid = ? and track_num >= ?'''
                tx.execute(query, (self.group_uid, start))
                snapshot_id = int(time.time() * 1000)
                query = ''' UPDATE sonos_queues
                            SET snapshot_id = ?
                            WHERE groupid = ?'''
                tx.execute(query, (snapshot_id, self.group_uid))
            query = '''DROP TABLE tmp_data'''
            tx.execute(query)

        @database_serialised
        @dbpooled
        def sync(tx, self, results, start=0):

            query = '''	INSERT INTO sonos_queue_data
						(groupid, track_num, album, artist, song, play_time, id)
						VALUES (?,?,?,?,?,?,?)'''
            tx.executemany(query, [(self.group_uid,
                                    n + start,
                                    item['album'],
                                    item['artist'],
                                    item['song'],
                                    item['play_time'],
                                    item['id']) for n, item in enumerate(results)])

        @database_serialised
        @dbpooled
        def cleanup(tx, self):
            var['mismatch'] = False
            query = ''' DELETE FROM sonos_queue_data
						WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            return

        def WS_notify(results=None):
            if var['mismatch']:
                self.WS_queue_contents_send()
            else:

                # We send the snapshot_id only if there is no mismatch,
                # because the queue is unchanged (so clients won't reload it)
                # but the snapshot_id might have changed. This could happen
                # if a move has occurred with the same origin and destination
                # or if an item was added and immediately deleted before the
                # reconciliation occurred (as the device can be slower to
                # process than the database).

                self.WS_snapshot_id(var['snapshot_id'])

        args = {'just_ids': True}
        while True:
            result = yield self.get_queue_segment(args)
            if result and 'tracks' in result:
                yield process_queue(result['tracks'])
            if result.get('var') and not var['mismatch']:
                args = result['var']
            else:
                break

        if var['mismatch']:
            while True:
                args = {'start': var['start']}
                result = yield self.get_queue_segment(args)
                if result and 'tracks' in result:
                    yield process_queue(result['tracks'])
                if result and result.get('var'):
                    args = result['var']
                else:
                    break
        elif not var['start']:
            yield cleanup(self)

        yield self.update_queue_length()

        if var['mismatch']:
            yield self.update_spotify_cache()

        yield WS_notify()

    def flush_and_reconcile(self, failure):
        # Send client a warning?
        logError(failure)
        # Unset the set_queue_requested flag
        self.status.set_queue_requested = None
        # See WS_queue_contents docstring for explanation
        self.WS_queue_contents(device_error=True)

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

        num = 100

        if args.get('var'):
            args = args['var']
        if not args.get('start'):
            args['start'] = 0
        just_ids = args.get('just_ids', False)

        def return_result(tracks=[]):
            result = {'tracks': tracks}
            if tracks and args['start'] < args.get('length', 0):
                result['var'] = args
            return result

        if self.device is None:
            return

        if 'length' not in args:
            args['length'] = yield self.device.queue_size()
            if self.device is None:
                return

        result = yield self.device.get_queue(args['start'], num, just_ids)
        if self.device is None:
            return
        if not result:
            return return_result()
        args['start'] += num
        tracks = yield self.convert_queue_fields(result)
        if self.device is None:
            return
        return return_result(tracks)

    def convert_queue_fields(self, queue):

        filenames = []
        dlist = []

        for n in range(len(queue)):
            uri = queue[n]['id']
            filename = None
            if 'x-sonos-spotify' in uri:
                uri = unquote(uri)
                queue[n]['id'] = uri.split(':', 1)[1].split('?')[0]
            else:
                filename = get_filename_from_uri(uri)
                if filename:
                    filenames.append((queue[n]['id'], filename))
            if 'length' in queue[n].keys():
                if filename and not queue[n]['length']:
                    d = self.objects[
                        'qimport'].get_song_duration(
                            filename, False).addErrback(logError)
                else:
                    d = defer.Deferred()
                    d.callback(queue[n]['length'])
                dlist.append(d)

        def update_song_durations(results):
            for n in range(len(queue)):
                if 'length' in queue[n].keys():
                    song_duration = results.pop(0)[1]
                    if not song_duration:
                        log.warning(
                            'Could not get duration for {}'.format(queue[n]['song']))
                        duration = ''
                    else:
                        try:
                            pieces = song_duration.split(':')
                            if len(pieces) == 3 and pieces[0] == '0':
                                duration = pieces[1] + ':' + pieces[2]
                            else:
                                duration = ''
                                for p in pieces:
                                    duration = duration + p + ':'
                                duration = duration[0:-1]
                        except:
                            log.exception(
                                'problem trying to parse duration ...')
                            duration = ''
                    queue[n]['play_time'] = duration
                    del (queue[n]['length'])
            return queue

        def convert_filenames(queue):

            @dbpooled
            def execute(tx, self):
                if len(filenames):
                    query = '''CREATE TEMP TABLE tmp_data
						   (pos INTEGER PRIMARY KEY ASC, uri TEXT, songid TEXT)'''
                    tx.execute(query)
                    query = '''	INSERT INTO tmp_data (uri, songid) SELECT ?, id FROM song
								WHERE filename = ?'''
                    tx.executemany(query, filenames)
                    query = '''SELECT uri, songid from tmp_data ORDER BY pos'''
                    tx.execute(query)
                    results = tx.fetchall()
                    query = '''DROP TABLE tmp_data'''
                    tx.execute(query)

                for n in range(len(queue)):
                    if 'spotify' not in queue[n]['id']:
                        if len(results) and queue[n]['id'] == results[0]['uri']:
                            queue[n]['id'] = results.pop(0)['songid']
                return queue
            return execute(self)

        if len(dlist):
            d = defer.DeferredList(dlist)
            d.addCallback(update_song_durations)
        else:
            d = defer.Deferred()
            d.callback(queue)

        if len(filenames):
            d.addCallback(convert_filenames)

        return d

    # Pass through any data received,
    # so this function can be chained in callbacks
    def update_queue_length(self, data=None):

        if self.device is None:
            return data

        @dbpooled
        def get_queue_length(tx, self):
            query = '''	SELECT COUNT(*) FROM sonos_queue_data
						WHERE groupid = ?'''
            tx.execute(query, (self.group_uid,))
            return tx.fetchone()[0]

        def process(length):
            self.status.queue_contents = length
            return data

        d = get_queue_length(self)
        d.addCallback(process)
        return d

    def update_spotify_cache(self, data=None):
        if self.device is None:
            return data

        self.objects['spotify_cache'].sync_spotify_cache_to_sonos_queue(
            self.group_uid)
        return data

    # These next two functions are required and used by
    # the @snapshot decorator

    @dbpooled
    def check_snapshot_id(tx, self, container_id, snapshot_id):
        query = ''' SELECT snapshot_id
                    FROM sonos_queues
                    WHERE groupid = ?'''
        tx.execute(query, (self.group_uid,))
        db_snapshot_id = tx.fetchone()[0]
        if db_snapshot_id == snapshot_id:
            return True, {}
        else:
            res = {}
            res['snapshot_id'] = db_snapshot_id
            res['status'] = 'WRONG_SNAPSHOT_ID'
            return False, res

    @dbpooled
    def update_snapshot_id(tx, self, res):
        if res == None:
            res = {}
        snapshot_id = int(time.time() * 1000)
        query = ''' UPDATE sonos_queues
                    SET snapshot_id = ?
                    WHERE groupid = ?'''
        tx.execute(query, (snapshot_id, self.group_uid))
        res['status'] = 'SUCCESS'
        res['snapshot_id'] = snapshot_id
        return res

# sonos_factory - top level object


class sonos_factory(sonos_factory_WS):

    def __init__(self, objects, soco_subprocess, soco_event_notifier):
        sonos_factory_WS.__init__(self, objects['wsfactory'])
        self.objects = objects
        self.soco_subprocess = soco_subprocess
        self.soco_event_notifier = soco_event_notifier
        self.soco_event_notifier.callback = self.EventNotifier
        self.soco_event_notifier.errback = logError
        self.db_player = objects['db_player']
        self.dbpool = objects['dbpool']
        self.serialiser = serialiser.Serialiser('Sonos Factory Serialiser')
        self.serialise = self.serialiser.serialise
        self.uids = {}
        self.names = {}
        self.processing_group_change = False
        self.group1 = None
        self.stopped = True
        self.startup_warnings = {}
        self.startup_warnings['sonos_not_found'] = False
        self.db_temp_table_counter = 0
        self.add_functions()
        IP.register(self.startup, self.network_down)

    def add_functions(self):
        for n in dir(sonos_client):
            if n[0] != '_' and hasattr(getattr(sonos_client, n), '__call__'):
                setattr(self, n, self._decorate(n))

    @serialised
    def startup(self):
        self._startup()

    def _startup(self, timeout=None):

        def setup(info):
            if self.stopped:
                return
            if info and info['groups']:
                log.info('Sonos system found')
                self.startup_warnings['sonos_not_found'] = False
                d = self.set_groups(info['groups'])
                d.addCallback(lambda _:
                              self.soco_event_notifier.process_command('SoCo.startup'))
                return d
            else:
                if not self.startup_warnings['sonos_not_found']:
                    log.warning(
                        'Sonos system not found ... will keep looking every second')
                    self.startup_warnings['sonos_not_found'] = True
                task.deferLater(reactor, 1, self._startup, 1)

        if not IP.network_down:
            self.stopped = False
            d = self.soco_subprocess.process_command('SoCo.get_info', timeout)
            d.addCallback(setup)
            d.addErrback(logError)
            return d

    def network_down(self):
        log.warning(
            'The network is disconnected ... shutting down sonos connectivity.')
        self.shutdown()

    def shutdown(self):
        if self.stopped:
            return
        self.stopped = True
        for sg in self.uids.values():
            sg.shutdown()
        self.uids = {}
        self.names = {}
        self.group1 = None
        self.soco_subprocess.process_command('SoCo.shutdown')
        self.soco_event_notifier.process_command('SoCo.shutdown')
        self.WS_reboot()

    def did_groups_change(self, uids, swgen):
        if self.stopped:
            return
        if self.processing_group_change:
            return
        old_uids = [
            g.group_uid
            for g in self.uids.values()
            if g.system_version == swgen
        ]
        old_uids.sort()
        uids.sort()
        if uids != old_uids:
            self.groups_changed()

    @serialised
    def groups_changed(self):
        if self.stopped:
            return defer.succeed(None)  # Return an already-resolved Deferred
        if self.processing_group_change:
            return defer.succeed(None)  # Same as above
        self.processing_group_change = True
        log.info('Group change detected')

        # Shutdown existing groups
        for sg in self.uids.values():
            sg.shutdown()
        self.uids = {}
        self.names = {}
        self.group1 = None

        # Call SoCo.shutdown immediately
        self.soco_event_notifier.process_command('SoCo.shutdown')

        outer_deferred = defer.Deferred()

        def delayed_restart():

            def setup(info):
                if self.stopped:
                    outer_deferred.callback(None)
                    return
                if info and info['groups']:
                    d = self.set_groups(info['groups'])
                    d.addCallback(
                        lambda _: self.soco_event_notifier.process_command('SoCo.startup'))
                    d.addCallback(lambda _: log.info(
                        'Group change processing completed'))
                    d.addCallback(lambda _: setattr(
                        self, 'processing_group_change', False) or _)
                    d.addCallback(lambda _: outer_deferred.callback(True))
                    # Propagate errors
                    d.addErrback(lambda err: outer_deferred.errback(err))

            d = self.soco_subprocess.process_command('SoCo.get_info')
            d.addCallback(setup)
            # Log and propagate errors
            d.addErrback(lambda err: logError(
                err) or outer_deferred.errback(err))

        # Schedule delayed_restart after 1 second
        reactor.callLater(1, delayed_restart)

        return outer_deferred

    def set_groups(self, groups):

        @database_serialised
        @dbpooled
        def reset_db(tx, self):
            # This is a partial purge of queue data:
            # over time, all queue data for missing components
            # will be purged
            query = ''' DELETE FROM sonos_queue_data
                        WHERE groupid NOT IN
                        (SELECT groupid
                        FROM sonos_queues)'''
            tx.execute(query)
            query = ''' DELETE FROM sonos_queues'''
            tx.execute(query)

        def set_groups(result):
            for group_name, group_uid, coordinator_uid, devices_uids, base_url, system_version in groups:
                devices = {}
                for name in devices_uids.keys():
                    devices[name] = sonos_device(
                        self.soco_subprocess,
                        devices_uids[name])
                    if devices_uids[name] == coordinator_uid:
                        coordinator = devices[name]
                sg = sonos_group(
                    group_name,
                    group_uid,
                    coordinator,
                    devices,
                    base_url,
                    system_version,
                    self
                )
                self.uids[group_uid] = sg
                self.names[group_name] = sg
                if not self.group1:
                    self.group1 = sg
            self.WS_reboot()

        d = reset_db(self)
        d.addCallback(set_groups)
        return d

    def _decorate(self, fn_name):
        '''
        This returns a function intended to form part of the sonos_factory object.
        The process() function in dbmp calls one of these functions in the sonos_factory object.
        After running certain sanity checks, the function in the sonos_factory object calls
        the corresponding function in the relevant sonos_group object.
        This call is serialised if the factory is starting up or changing groups.
        '''
        res = None

        if fn_name == 'get_queue':
            res = {}
            res['results'] = []
            res['totalRecords'] = 0
            res['startIndex'] = 0
            if IP.network_down:
                res['label'] = 'Not connected to network'
            else:
                res['label'] = 'Sonos not found'
            res['id'] = 0
            res['queue_position'] = 0

        def inner(args):
            def relay(args):
                if not self.group1:
                    return res
                try:
                    uid = args['uid']
                except KeyError:
                    log.warning('No uid received. Ignoring command.')
                    return
                try:
                    g = self.uids[uid]
                except:
                    log.info('No group uid. Picking first group in list.')
                    g = self.group1
                fn = getattr(g, fn_name)
                if list(args.keys()) == ['uid']:
                    return fn()
                return fn(args)

            if len(self.serialiser.queue):
                return self.serialise(relay, args)
            return relay(args)

        return inner

    def transfer_queue_to_group(self, args):
        group = self.uids[args['dest_id']]
        group.transfer_queue(args)

    def add_container_to_group(self, args):
        group = self.uids[args['dest_id']]
        group.add_container(args)

    def search_groups(self, args):
        groups = self.WS_get_groups()
        res = {}
        res['startIndex'] = args['startIndex']
        res['totalRecords'] = len(groups)
        res['results'] = []
        if args['startIndex'] > len(groups):
            return
        for g in groups[args['startIndex']:args['startIndex'] + args['rowsPerPage']]:
            res['results'].append({'title': g['name'], 'itemid': g['id']})
        return res
