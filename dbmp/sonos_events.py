# -*- coding: utf-8 -*-

from .logging_setup import getLogger
log = getLogger(__name__)

from . import soco
from .soco import events_twisted
soco.config.EVENTS_MODULE = events_twisted
from .soco.services import GroupRenderingControl
from .soco.services import Queue as SonosQueue

from .config import SONOS_ZONES

# event_notifier - sets up event notification for a device


class event_notifier():

    def __init__(self, factory, device):
        self.factory = factory
        self.device = device
        self.stopped = False
        self.subscriptions = {}
        self.startup()

    def startup(self):
        if self.stopped:
            return

        subscriptions = (
            ('subRCEvent', self.device.renderingControl, self.RCEvent_callback),
            ('subAVTransportEvent', self.device.avTransport, self.AVTransportEvent_callback),
            ('subGRCEvent', GroupRenderingControl(self.device), self.GRCEvent_callback),
            ('subQEvent', SonosQueue(self.device), self.QEvent_callback),   
# Added this next one
            ('subZGTEvent', self.device.zoneGroupTopology, self.ZGTEvent_callback),   
        )

        for s in subscriptions:
            name = s[0]
            sub = s[1].subscribe(auto_renew=True).subscription
            sub.callback = s[2]
            self.subscriptions[name] = sub

    def shutdown(self):
        if self.stopped:
            return
        events_twisted.event_listener.stop()
        self.unsubscribe_all()
        self.stopped = True

    def unsubscribe_all(self):
        for key in self.subscriptions.keys():
            self.subscriptions[key].unsubscribe()
        self.subscriptions = {}

    def send_data(self, data):
        self.factory.protocol.send_data(data, 'C')

    def RCEvent_callback(self, event):
        result = event.variables
        if result:
            try:
                self.send_data(
                    ('RCEvent',
                     self.device.group.uid,
                     self.device.player_name,
                     result))
            except AttributeError:
                log.warning('RCEvent_callback: problem with device')
            except:
                log.exception('Exception in RCEvent_callback')
                

    def AVTransportEvent_callback(self, event):
        result = event.variables
        if result:
            try:
                if self.device.is_coordinator:
                    self.send_data(
                        ('avTransportEvent',
                         self.device.group.uid,
                         result))
            except AttributeError:
                log.warning('AVTransportEvent_callback: problem with device')
            except:
                log.exception('Exception in AVTransportEvent_callback')

    def GRCEvent_callback(self, event):
        result = event.variables
        if result:
            try:
                self.send_data(('GRCEvent', self.device.group.uid, result))
            except AttributeError:
                log.warning('GRCEvent_callback: problem with device')
            except:
                log.exception('Exception in GRCEvent_callback')

    def QEvent_callback(self, event):
        result = event.variables
        if result:
            try:
                self.send_data(('QEvent', self.device.group.uid, result))
            except AttributeError:
                log.warning('QEvent_callback: problem with device')
            except:
                log.exception('Exception in QEvent_callback')

    def ZGTEvent_callback(self, event):
        result = event.variables
        if result:
            self.send_data(
            ('ZGTEvent',
             self.device.group.uid,
             self.device.player_name,
            result))

class Factory(object):

    def __init__(self):
        self.protocol = None
        self.event_notifiers = []

    def startup(self):
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
                        success = False
                except:
                    log.exception('Error trying config.SONOS_ZONES')

        if success:
            for device in list(devices):
                self.event_notifiers.append(event_notifier(self, device))

    def shutdown(self):
        for event_notifier in self.event_notifiers:
            event_notifier.shutdown()
        self.event_notifiers = []

SoCo = Factory()


def setcoms(protocol):
    SoCo.protocol = protocol
