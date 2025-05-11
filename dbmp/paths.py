# -*- coding: utf-8 -*-

from twisted.internet import task
import os
from pathlib import Path
import runpy
from .logging_setup import getLogger
log = getLogger(__name__)


def expand_path(s):
    return Path(os.path.expanduser(s))


APPDIR = Path(__file__).resolve().parent.parent
HOMEDIR = Path.home()
CONFIGDIR = HOMEDIR / ".dbmp"

WEBPATH = APPDIR / "html"
DB = CONFIGDIR / "dbmp.sqlite"
CONFIG = CONFIGDIR / "config.py"
ARTWORKPATH = CONFIGDIR / "artwork"
COVERPATH = ARTWORKPATH / "covers"
ARTISTPATH = ARTWORKPATH / "artists"
PLAYLISTPATH = ARTWORKPATH / "playlists"

CERTDIR = CONFIGDIR / "certs"
CERTFILE = CERTDIR / "server.pem"
KEYFILE = CERTDIR / "server-key.pem"

raw_config = runpy.run_path(CONFIG)
MUSICPATH = expand_path(raw_config.get("MUSICPATH", "~/Music"))
SEARCHPATH = expand_path(raw_config.get("SEARCHPATH", "~/Music"))
DOWNLOADSPATH = expand_path(raw_config.get("DOWNLOADSPATH", "~/Downloads"))


class PathChecker(object):

    def __init__(self, name, defaultpath, fallback=None):
        self.LoopingCall = None
        self.name = name  # e.g. MUSICPATH
        self.defaultpath = defaultpath  # path we want
        self.fallback = fallback  # optional fallback path
        self.path = defaultpath
        self.up = True  # True if defaultpath is available
        self.path_up_functions = []
        # Executed if path becomes available after it was down
        self.path_down_functions = []
        # Executed if path is or becomes unavailable
        self.get_path()
        # Checks path is available, deals with consequences if not, returns
        # the actual path (which may be None)

    def get_path(self):
        if self.LoopingCall:  # there's a problem, but periodic checking is running, so just return self.path
            return self.path
        if self.path.exists():
            return self.path
        self.warn()  # warn before changing self.path
        if self.fallback and self.path.absolute() != self.fallback.absolute():
            self.path = self.fallback
            if not self.path.exists():
                self.warn()
                self.path = None
        else:
            self.path = None
        self.defaultpath_is_down()
        return self.path

    def defaultpath_is_down(self):
        self.up = False
        for fn in self.path_down_functions:
            fn()
        self.LoopingCall = task.LoopingCall(self.looping_check)
        self.LoopingCall.start(1)

    def looping_check(self):
        if self.defaultpath.exists():
            self.LoopingCall.stop()
            self.LoopingCall = None
            self.up = True
            self.path = self.defaultpath
            log.info('%s (%s) connected ... ' % (self.name, self.path))
            for fn in self.path_up_functions:
                fn()

    def warn(self):
        if self.fallback and self.path.absolute() != self.fallback.absolute():
            warning = (
                '%s (%s) not found. Using %s instead.' %
                (self.name, self.path, self.fallback))
        else:
            warning = ('%s (%s) not found.' % (self.name, self.path))
        log.warning(warning)

    def register(self, path_up_function, path_down_function=None):
        self.path_up_functions.append(path_up_function)
        if path_down_function:
            self.path_down_functions.append(path_down_function)
            if self.LoopingCall:
                path_down_function()


Searchpath = PathChecker('SEARCHPATH', SEARCHPATH, HOMEDIR)
Downloadspath = PathChecker('DOWNLOADSPATH', DOWNLOADSPATH, HOMEDIR)
Musicpath = PathChecker('MUSICPATH', MUSICPATH)
