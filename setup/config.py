# -*- coding: utf-8 -*-

# MUSICPATH should point to the directory where your music files are kept.
# Ideally the directory structure will be /MUSICPATH/artist/album/filename,
# as in /MUSICPATH/The Beatles/Revolver/Yellow Submarine.flac, as this will
# make the process of importing files into the database easier.
# Any zipfiles selected for importing will be extracted to MUSICPATH
MUSICPATH = '~/Music'

# SEARCHPATH is the directory displayed by default at the beginning of the
# process for importing files into the database
SEARCHPATH = '~/Music'

# DOWNLOADSPATH has a button shortcut on the page for importing files to
# the database. The import process will not move the files from
# your Downloads directory, although any imported zipfiles will be extracted
# to MUSICPATH. You should therefore move files (other than zipfiles)
# to their intended final location before you import them into the
# database. If you change their location after importing them, you
# will need to delete them from the database and import them again,
# otherwise their filenames will be invalid.
DOWNLOADSPATH = '~/Downloads'

# SSL_PORT is where the web interface is served via https
SSL_PORT = 8005

# WSS_PORT is where clients connect via websockets for https clients
WSS_PORT = 8006

# PORT is where the web interface is served via http
PORT = 8002

# WS_PORT is where clients connect via websockets for http clients
WS_PORT = 8003

# SP_PORT is used for communication with subprocesses
SP_PORT = 8004

# These are the details registered with Spotify for accessing its Web API.
# These values are public and safe to include in this file.
# Users will authorize their own accounts at runtime and their tokens will
# be stored on their local database
SPOTIFY_CLIENT_ID = 'e47c6be17ef944dc8335617bf8f56b21'
# Redirect URI for Spotify auth — must match the 'PORT' defined above (http, not https)
SPOTIFY_REDIRECT_URI = 'http://localhost:8002/spotify_auth'

# Choose the appropriate region: 'US' or 'EU'
SONOS_REGION_SPOTIFY = 'EU'

# soco.discover() can randomly fail to detect a sonos device on the
# network, so you can specify known IP addresses here as a fallback for when
# soco.discover() fails to find anything
#SONOS_ZONES = ['192.168.1.185', '192.168.1.76']
SONOS_ZONES = []

