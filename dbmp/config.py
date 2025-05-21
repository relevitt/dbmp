# -*- coding: utf-8 -*-

from .paths import raw_config
import os
import sys

PORT = raw_config.get("PORT")
WS_PORT = raw_config.get("WS_PORT")
SP_PORT = raw_config.get("SP_PORT")
SSL_PORT = raw_config.get("SSL_PORT")
WSS_PORT = raw_config.get("WSS_PORT")
MPD_PORT = raw_config.get("MPD_PORT")
GOOGLE_KEY = raw_config.get("GOOGLE_KEY")
GOOGLE_CX = raw_config.get("GOOGLE_CX")
SONOS_REGION_SPOTIFY = raw_config.get("SONOS_REGION_SPOTIFY")
SONOS_ZONES = raw_config.get("SONOS_ZONES")
SERVE_ROOT_CERT = raw_config.get("SERVE_ROOT_CERT")
ERRLOG_FILE = sys.argv[1] if len(
    sys.argv) > 1 else os.path.expanduser("~/.dbmp/stderr.txt")
ERRLOG_TAIL_EXECUTABLE = "/usr/bin/tail"
ERRLOG_TAIL_ARGS = ["tail", "-f", "-n", "+0", ERRLOG_FILE]
