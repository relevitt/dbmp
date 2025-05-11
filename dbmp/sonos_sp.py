# -*- coding: utf-8 -*-

from .config import SONOS_ZONES
from .soco.services import GroupRenderingControl
from .soco.exceptions import SoCoUPnPException
from . import soco
from .logging_setup import getLogger
from twisted.python.failure import Failure
from twisted.internet import reactor
log = getLogger(__name__)

soco.config.REQUEST_TIMEOUT = None

# group_name - returns the display name of a group


def group_name(group):
    '''

    Receives a <group> as an argument.
    Returns a str with the group name.
    The group name is constructed from the player_name of each
    group member in group.coordinator.visible_zones.
    Each player name is separated by ' + '.
    The player_name of the group coordinator appears first.
    Example group name: 'Living Room + Kitchen'

    '''

    name = group.coordinator.player_name
    for d in group.members:
        if d != group.coordinator and d in list(group.coordinator.visible_zones):
            name += ' + ' + d.player_name
    return name


def DidlMusicTrack_to_dict(track, just_ids):
    result = {}
    result['id'] = track.resources[0].uri
    if just_ids:
        return result
    if hasattr(track, 'artist'):
        result['artist'] = track.artist
    elif hasattr(track, 'creator'):
        result['artist'] = track.creator
    else:
        result['artist'] = '[Unknown]'
    if hasattr(track, 'album'):
        result['album'] = track.album
    else:
        result['album'] = '[None]'
    result['song'] = track.title
    result['play_time'] = None
    result['length'] = track.resources[0].duration
    return result


class Dispatcher(object):

    def __init__(self):
        self.uids = {}
        self.intermediated = Intermediated(self)

    def get_info(self, timeout=None):

        results = {}
        results['groups'] = []

        self.uids = {}

        if timeout:
            devices = soco.discovery.scan_network(
                scan_timeout=timeout, multi_household=True)
        else:
            devices = soco.discovery.scan_network(multi_household=True)

        try:
            success = len(devices)
        except (TypeError, IndexError):
            success = False

        if not success:
            log.warning('soco.discovery.scan_network() returned None')
            log.warning('Trying config.SONOS_ZONES')
            for ip in SONOS_ZONES:
                try:
                    device = soco.SoCo(ip)
                    if device.group:
                        devices = device.visible_zones
                        success = True
                        break
                    else:
                        device = None
                except:
                    log.warning(
                        f'Error trying config.SONOS_ZONES: could not reach {ip}')

        if success:
            groups = []
            temp_results = []
            for device in list(devices):
                try:
                    for group in list(device.all_groups):
                        if group not in groups:
                            groups.append(group)
                except Exception as e:
                    msg = f"Error retrieving device.all_groups from \
                        {device.player_name}. Skipping device: {str(e)}"
                    log.error(msg)
            groups.sort(key=group_name)
            for g in groups:
                coordinator = g.coordinator
                display_version = coordinator.get_speaker_info()[
                    'display_version']
                if int(display_version.split(".")[0]) < 12:
                    system_version = 'S1'
                else:
                    system_version = 'S2'
                if coordinator and not coordinator.is_bridge:
                    uids = {}
                    for d in coordinator.visible_zones:
                        if d in g.members:
                            uids[d.player_name] = d.uid
                            self.uids[d.uid] = d
                            d.GroupRenderingControl = GroupRenderingControl(d)
                    # If the usual coordinator for the group is switched off
                    # then the group will not appear in visible zones (nor will
                    # it appear in the list of groups shown in the sonos phone
                    # app), although the group will still appear in all_groups.
                    # Query then whether all_groups is the right function
                    # to be using here. As we are using all_groups, we have to
                    # ignore groups that are invisible. For them, uids will
                    # be {}.
                    if uids:
                        self.uids[g.uid] = g
                        temp_results.append((
                            group_name(g),
                            g.uid,
                            coordinator.uid,
                            uids,
                            coordinator.deviceProperties.base_url,
                            system_version
                        ))

            results['groups'] = (
                [d for d in temp_results if d[-1] == 'S2'] +
                [d for d in temp_results if d[-1] == 'S1']
            )
        return results

    def shutdown(self):
        self.uids = {}

    def device(self, uid, action, *args, **kwargs):
        if action == 'next_track':
            action = 'next'
        device = self.uids[uid]
        if hasattr(self.intermediated, action):
            fn = getattr(self.intermediated, action)
            return fn(device, *args, **kwargs)
        else:
            obj = getattr(device, action)
            if hasattr(obj, '__call__'):
                try:
                    return obj(*args, **kwargs)
                except SoCoUPnPException as e:
                    log.warning(e)
                except Exception as e:
                    log.warning(e)
                    return Failure(e)
            elif args != ():
                setattr(device, action, *args)
            else:
                return obj

    def service(self, uid, service, action, *args, **kwargs):
        device = self.uids[uid]
        service = getattr(device, service)
        # if hasattr(self.intermediated, action):
        # fn = getattr(self.intermediated, action)
        # return fn(device, *args, **kwargs)
        # else:
        obj = getattr(service, action)
        if hasattr(obj, '__call__'):
            return obj(*args, **kwargs)
        else:
            return obj


class Intermediated(object):

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def get_queue(self, device, start, num, just_ids):
        return [DidlMusicTrack_to_dict(track, just_ids) for track in device.get_queue(start, num)]

    def get_update_id(self, device):
        return device.get_queue(0, 1).update_id

    def get_current_track_position(self, device):
        return device.get_current_track_info()['position']

    def get_current_playlist_position(self, device):
        return device.get_current_track_info()['playlist_position']

    def join(self, device, uid):
        return device.join(self.dispatcher.uids[uid])

    def set_group_volume(self, device, volume):
        device.group.volume = volume

    # This is a hack, because it's a battle to get a sonos group
    # to play from the first track when we change queue.
    def seek_zero(self, device):
        def prev():
            try:
                device.previous()
            except:
                pass
        reactor.callLater(2, prev)

    # Debugging function
    def identify_yourself(self, device):
        print(device.player_name)
#        print(dir(device))


SoCo = Dispatcher()
