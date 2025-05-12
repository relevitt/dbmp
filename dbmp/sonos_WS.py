# -*- coding: utf-8 -*-

from .util import str_to_ms
from .util import serialised
from .error import logError
from .sonos_util import Song
from .sonos_util import SerialisedDevice, SerialisedDataBase
from twisted.internet import task
from twisted.internet import defer
from twisted.internet import reactor
import json
import xml.etree.ElementTree as ET
import time
from logging import DEBUG
from .logging_setup import getLogger
log = getLogger(__name__)
log.setLevel(DEBUG)


# sonos_group_WS - adds WS functionality to a sonos_group instance


class sonos_group_WS(object):

    def __init__(self):
        self.websockets = []
        self.volume_paused = False
        self.volume_pause_end_task = None
        self.WS_song_progress()
        self.WS_LoopingCall = task.LoopingCall(self.WS_song_progress)

    def WS_shutdown(self):
        if self.WS_LoopingCall.running:
            self.WS_LoopingCall.stop()
        self.WS_LoopingCall = None

    def WS_send_all(self, items):
        if not self.shutting_down:
            self.factory.WS_send_all(self.group_uid, items)

    def WS_status(self, s, event=True):
        if event:
            self.status.last_WS_status_time = time.time()
        if s == self.status.transport_state:
            return
        if s == 'TRANSITIONING':
            return
        self.status.transport_state = s
        items = {}
        items['type'] = 'status'
        items['playing'] = self.status.transport_state == 'PLAYING'
        items['paused'] = self.status.transport_state == 'PAUSED_PLAYBACK'
        if s == 'PLAYING':
            if not self.WS_LoopingCall.running:
                self.WS_LoopingCall.start(1.0)
        else:
            if self.WS_LoopingCall.running:
                self.WS_LoopingCall.stop()
            if not items['paused']:
                self.status.song_progress = '0:00:00'
                items2 = {}
                items2['type'] = 'song_progress'
                items2['song_progress'] = 0
                self.WS_send_all(items2)
        self.WS_send_all(items)

    def WS_song(self, s):
        self.status.song = s

        def process(album_art_uri):
            items = {}
            song = {}
            song['album'] = s.album
            song['artist'] = s.artist
            song['title'] = s.title
            song['album_art_uri'] = album_art_uri
            song['albumid'] = self.get_albumid(s)
            song['id'] = s.id
            items['type'] = 'song'
            items['song'] = song
            items['song_length'] = str_to_ms(s.length)
            self.WS_send_all(items)

        # Sonos returns queue positions starting at 1. However,
        # if it's not playing from the queue (e.g. Spotify is controlling
        # playback), then the 'playlist_position' returned by
        # device.get_current_track_info() will be 0, so we use this to
        # determine if the song being played is from the queue and
        # notify clients accordingly
        def playing_from_queue(pos):
            if self.shutting_down:
                return
            self.status.playing_from_queue = pos != '0'
            self.WS_send_all(
                {'type': 'playing_from_queue', 'result': pos != '0'})

        d = self.convert_art_uri(s)
        d.addCallback(process)
        d.addCallback(lambda _: self.device.get_current_playlist_position())
        d.addCallback(playing_from_queue)
        d.addErrback(logError)

    def WS_queue_position(self, p):
        '''
        During a multiple delete / move / add operation, the event loop may
        notify more than one change in queue_position. Therefore,
        we serialise the WS notification (so that it happens after
        the delete / move / add requests have been despatched and avoid
        multiple WS notifications if we have one queued.
        '''

        if self.status.queue_position == p:
            return

        self.status.queue_position = p

        self.status.updating_position = True
        self.WS_reconcile()

    def _WS_queue_position(self, pos=None):
        '''
        The soco module sends positions back starting from 1,
        so we decrement p by 1, as clients expect positions
        to start at 0
        '''
        if pos != None:
            if pos == int(self.status.queue_position) + 1:
                return
            self.status.queue_position = pos + 1

        items = {}
        items['type'] = 'queue_position'
        items['queue_position'] = int(self.status.queue_position) - 1
        self.WS_send_all(items)

    def WS_queue_contents(self, updateid=None, device_error=False, reset=False):
        '''
        During a multiple delete / move / add operation, the event loop may
        notify more than one change in queue_contents. There may also be
        multiple delete / move / add operations scheduled. Therefore, we
        serialise reconciliation, so that it happens after the delete / move /
        add requests have been processed. When the reconciliation executes, it
        will reschedule itself to the back of the device serialiser, if there
        are other pending operations and it will return without reconciling if
        further event notifications are awaited.

        '''

        if device_error:
            self.status.device_error = True
            msg = 'WS_queue_contents: Device error'
            log.debug(msg)

        else:
            msg = 'WS_queue_contents: '
            msg += 'Received updateid: {}'.format(
                updateid) if updateid else 'No updateid'
            log.debug(msg)

        msg = 'WS_queue_contents: '
        msg += 'Last updateid is: {}'.format(
            self.status.updateid)
        log.debug(msg)

        if updateid:
            self.status.last_notified_updateid = int(updateid)

        self.status.updating_contents = True
        self.WS_reconcile()

    def WS_reconcile(self, reset=False):

        # If the reset field is set to True, we reset flags and return,
        # as we can expect another call to WS_reconcile soon

        if reset:
            self.status.device_error = False
            self.set_updateid()
            return

        try:
            # Don't reconcile yet, if there are pending operations
            # In that case, another event driven reconcile should happen anyway
            # when they complete
            if self.status.pending_device_updates:
                return

            reconciled = not self.status.device_error and (
                self.status.last_reconcile == self.status.updateid) and (
                self.status.last_reconcile >= self.status.last_notified_updateid)

            # Notify WS_queue_position, if it changed
            if self.status.updating_position:
                self._WS_queue_position()
                self.status.updating_position = False

            # Reconcile queue, if contents changed
            if self.status.updating_contents:
                # Return if we've already reconciled for this updateid
                if reconciled:
                    self.status.updating_contents = False
                    return
                self.reconcile_queue()
                self.status.updating_contents = False
                self.status.device_error = False
                self.set_updateid()

        except Exception as e:
            log.exception(e)

    # We pass through any results received, in case
    # this is in a chain of callbacks
    def WS_queue_contents_send(self, results=None):
        items = {}
        items['type'] = 'queue_contents'
        items['queue'] = {'name': self.name, 'id': self.group_uid}
        self.WS_send_all(items)
        return results

    def WS_song_progress(self):
        d = self.get_song_progress()

        def process(result):
            items = {}
            items['type'] = 'song_progress'
            items['song_progress'] = str_to_ms(result)  # Errors Here
            self.WS_send_all(items)
        d.addCallback(process)
        d.addErrback(logError)

    def WS_volume(self, control_name, v):
        try:
            v = int(v)
        except TypeError:
            log.warning('Could not notify volume for {}'.format(
                control_name))
            return
        if v != self.status.volume[control_name]:
            self.status.volume[control_name] = v
            items = {}
            items['type'] = 'volume'
            items['volume'] = self.status.volume
            self.WS_send_all(items)

    def WS_volume_pause(self):
        def cb():
            self.volume_paused = False
            self.volume_pause_end_task = None
            self.WS_get_volumes()
        if self.volume_paused:
            self.volume_pause_end_task.cancel()
        self.volume_paused = True
        self.volume_pause_end_task = reactor.callLater(1, cb)

    def WS_get_volumes(self):

        dlist = []
        for channel in self.devices.keys():
            dlist.append(self.devices[channel].volume().addErrback(logError))
        dlist.append(self.device.GroupRenderingControl.GetGroupVolume([
            ('InstanceID', 0)
        ]).addErrback(logError))

        def send(results):
            if self.volume_paused:
                return
            for n, channel in enumerate(self.devices.keys()):
                self.WS_volume(channel, results[n][1])
            self.WS_volume('Group Volume', results[-1][1].get(
                'CurrentVolume',  0))

        d = defer.DeferredList(dlist)
        d.addCallback(send)
        d.addErrback(logError)

    def WS_mute(self, control_name, m):
        if m != self.status.mute[control_name]:
            self.status.mute[control_name] = m
            items = {}
            items['type'] = 'mute'
            items['mute'] = {
                control_name: m
            }
            self.WS_send_all(items)

    def WS_snapshot_id(self, snapshot_id):

        # This method is used only when the snapshot_id
        # may have changed, but the queue has not
        # changed (so clients won't reload the queue)

        items = {}
        items['type'] = 'snapshot_id'
        items['snapshot_id'] = snapshot_id
        self.WS_send_all(items)

    def WS_set_queue_alert(self, alert):
        items = {}
        items['type'] = 'set_queue_alert'
        items['alert'] = alert
        self.WS_send_all(items)

    def get_status(self, args={}):
        def process(art_uri):
            results = {}
            song = {}
            song['album'] = self.status.song.album
            song['artist'] = self.status.song.artist
            song['title'] = self.status.song.title
            song['album_art_uri'] = art_uri
            song['albumid'] = self.get_albumid(self.status.song)
            song['id'] = self.status.song.id
            results['volume'] = self.status.volume
            results['mute'] = self.status.mute
            results['song_progress'] = str_to_ms(self.status.song_progress)
            results['song_length'] = str_to_ms(self.status.song.length)
            results['playing'] = self.status.transport_state == 'PLAYING'
            results[
                'paused'] = self.status.transport_state == 'PAUSED_PLAYBACK'
            results['queue_position'] = int(self.status.queue_position) - 1
            results['queue'] = {
                'name': self.name,
                'id': self.group_uid,
                'zones': list(self.devices.keys()),
            }
            results['queues'] = self.factory.WS_get_groups()
            results['song'] = song
            results['connected'] = True
            results['playing_from_queue'] = self.status.playing_from_queue
            return results
        d = self.convert_art_uri(self.status.song)
        d.addCallback(process)
        return d

    def get_song_progress(self):
        # This isn't serialised, so we check self.shutting_down
        if not self.shutting_down:
            d = self.device.get_current_track_position()

            def process(result):
                if result == 'NOT_IMPLEMENTED':
                    log.warning('get_song_progress: ' +
                                self.name + ' returned: NOT_IMPLEMENTED')
                    return '0:00:00'
                elif result is not None and not self.shutting_down:
                    self.status.song_progress = result
                    return result
                else:
                    return '0:00:00'
            d.addCallback(process)
            d.addErrback(logError)
        else:
            d = defer.Deferred()
            d.callback('0:00:00')
        return d

# sonos_factory_WS - adds WS functionality to a sonos_factory instance


class sonos_factory_WS(object):

    def __init__(self, wsfactory):
        self.wsfactory = wsfactory
        self.websockets = {}

    @serialised
    def WS_add(self, sid, queueid):
        uid = None
        # Extract coordinator uid from group uid
        if queueid:
            uid = queueid.split(':')[0]
        self.websockets[sid] = uid
        self.WS_allocate(sid)

    def WS_reboot(self):
        for sid in self.websockets.keys():
            self.WS_allocate(sid, None)

    def WS_allocate(self, sid, uid=None):
        if not self.group1:
            d = self.get_status_empty()
        else:
            if uid:
                group = self.uids[uid]
            else:
                group = self.trace_group(sid)  # find best match
            if sid not in group.websockets:
                group.websockets.append(sid)
            self.websockets[sid] = group.device.uid
            d = group.get_status()

        def process(items):
            items['type'] = 'init'
            items['sid'] = sid
            self.wsfactory.WS_send_sid(sid, items)
        d.addCallback(process)
        d.addErrback(logError)

    def WS_remove(self, sid):
        self.websockets.pop(sid)
        for group in self.uids.values():
            if sid in group.websockets:
                group.websockets.remove(sid)

    def WS_change_group(self, sid, uid):
        for group in self.uids.values():
            if sid in group.websockets:
                group.websockets.remove(sid)
        self.WS_allocate(sid, uid)

    def WS_send_all(self, uid, items):
        self.wsfactory.WS_send_sids(self.uids[uid].websockets, items)

    def trace_group(self, sid):
        old_coordinator = self.websockets.get(sid)
        if not old_coordinator:
            return self.group1
        else:
            for group in self.uids.values():
                uids = [device.uid for device in group.devices.values()]
                if old_coordinator in uids:
                    return group
        return self.group1  # Fallback, if we found nothing

    def get_status_empty(self):
        results = {}
        results['volume'] = {'Group Volume': -1}
        results['mute'] = {'Group Volume': 0}
        results['song_progress'] = -1
        results['song_length'] = -1
        results['playing'] = 0
        results['paused'] = 1
        results['queue_position'] = -1
        results['queue'] = {}
        results['queues'] = []
        results['song'] = -1
        results['connected'] = False
        results['playing_from_queue'] = False
        d = defer.Deferred()
        d.callback(results)
        return d

    def WS_get_groups(self):
        return [
            {
                'name': g.name,
                'id': g.group_uid,
                'zones': list(g.devices.keys()),
                'system_version': g.system_version,
            }
            for g in self.names.values()
        ]

    def EventNotifier(self, args):
        if hasattr(self, args[0]):
            notifier = getattr(self, args[0])
            params = args[1:]

            # If the factory has stopped or is processing a group change
            # we discard the event, otherwise it may trigger errors,
            # unless it's a ZGTEvent, where we may need the updated
            # group hash (I'm not sure whether it's necessary to get
            # an updated group_hash, although it is likely harmless)

            if notifier != self.ZGTEvent:
                if self.stopped or self.processing_group_change:
                    return
            notifier(*params)

    def ZGTEvent(self, group_uid, player_name, result):
        # We are passed group_uid and player_name in case
        # they're needed for debugging
        uids = []
        swgen = 'S'
        zgs = result.get('zone_group_state', None)
        if zgs:
            for g in ET.fromstring(zgs).find('ZoneGroups').findall('ZoneGroup'):
                uids.append(g.get('ID'))
                for m in g.findall('ZoneGroupMember'):
                    # Extract SWGen value
                    swgen_value = m.get('SWGen')
                    if swgen_value and swgen == 'S':  # Set SWGen once per event
                        swgen += swgen_value
                        break
        self.did_groups_change(
            uids,  # Groups data
            swgen  # System version, being S1 or S2
        )

    def RCEvent(self, group_uid, player_name, result):
        group = self.uids.get(group_uid, None)
        if not group:
            log.warning(
                'Ignoring RCEvent from {}: group object missing'.format(
                    group_uid))
            return
        if not group.multizone:
            return
        if 'volume' in result.keys() and not group.volume_paused:
            group.WS_volume(player_name, result['volume']['Master'])
        if 'mute' in result.keys():
            group.WS_mute(player_name, result['mute']['Master'])

    def GRCEvent(self, group_uid, result):
        group = self.uids.get(group_uid, None)
        if not group:
            log.warning(
                'Ignoring GRCEvent from {}: group object missing'.format(
                    group_uid))
            return
        if not group.volume_paused:
            group.WS_volume('Group Volume', result['group_volume'])
        group.WS_mute('Group Volume', result['group_mute'])

    def QEvent(self, group_uid, result):
        group = self.uids.get(group_uid, None)
        if not group:
            log.warning(
                'Ignoring QEvent from {}: group object missing'.format(
                    group_uid))
            return
        if 'queue_owner_id' in result.keys():
            return
        group.WS_queue_contents(updateid=result.get('update_id', None))

    def avTransportEvent(self, group_uid, result):

        group = self.uids.get(group_uid, None)
        if not group:
            log.warning(
                'Ignoring avTEvent from {}: group object missing'.format(
                    group_uid))
            return

        try:
            if 'current_track' in result.keys():
                if result['current_track'] != group.status.queue_position:
                    group.WS_queue_position(result['current_track'])

        except:
            log.exception('Problem with queue position event')
        try:
            if 'current_track_meta_data' in result.keys():
                m = result['current_track_meta_data']
                s = Song(m, group.base_url)
                if not s.equals(group.status.song):
                    group.WS_song(s)
        except:
            log.exception('Problem with song event')
        try:
            if 'transport_state' in result.keys():
                group.WS_status(result['transport_state'])
        except:
            log.exception('Problem with transport state event')
