# -*- coding: utf-8 -*-

from .util import authenticated
from twisted.internet import error
from twisted.internet import reactor
from .logging_setup import getLogger
log = getLogger(__name__)


class system(object):

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']
        # flag for relaunch
        self.relaunch_requested = False

    @authenticated
    def check_auth(self, args):
        return True

    def stop_reactor(self):
        if reactor.running:
            try:
                reactor.stop()
            except error.ReactorNotRunning:
                pass

    def relaunch(self, *args):
        print("Relaunch requested.")
        self.relaunch_requested = True
        reactor.callLater(1, self.stop_reactor)
        self.objects['sonos'].shutdown()
        self.objects['spserverfactory'].shutdown()
        reactor.addSystemEventTrigger(
            'before', 'shutdown', self.objects['spserverfactory'].kill_zombies)
