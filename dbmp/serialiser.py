# -*- coding: utf-8 -*-

import time
from collections import deque
from twisted.internet import defer
from twisted.internet import reactor
from logging import DEBUG
from .logging_setup import getLogger
from types import SimpleNamespace
log = getLogger(__name__, 'magenta')
log.setLevel(DEBUG)

# These are for when we don't want to use logging to
# avoid logging circularity


def debug(*args, **kwargs):
    pass


def warning(*args, **kwargs):
    print(*args, **kwargs)


def exception(*args, **kwargs):
    print(*args, **kwargs)


# The following approach has been taken to serialisation:
#
# - database:
#
# - 	Unless a need for serialisation is identified, read only searching of
# the database (e.g. in response to search.js) isn't serialised. Sqlite can
# perform these read requests concurrently or queue them if the database is
# locked by e.g. a write operation.
#
# -	Generally, operations that will lock the database are serialised. Although
# sqlite should queue these, they won't be queued in the right order, unless
# the calls on sqlite are made in the right order. We therefore generally
# serialise these calls.
#
# -	Generally, we use one serialiser (the database_serialiser) for the database.
#
# - spotify_cache:  Has its own serialiser and uses the database_serialiser
#
# - dbplayer:       Has its own serialiser and uses the database_serialiser.
#
# - spotify:        Has its own serialiser, a second serialiser for httpRequest and
#                   a third serialiser for long running processes (related artists
#                   and recommendations). All Spotify API calls are serialised
#                   by the second serialiser (so we don't hammer the Spotify API).
#                   Long running processes employ their own internal serialiser
#                   (the third serialiser), so as not to slow other serialised
#                   processes. Spotify also uses the database_serialiser.
#
# - sonos modules:
#
#       - factory:  Has its own serialiser. As with the database, searches aren't always
#                   serialised, although we hardly use sonos for searches.
#
#       - groups:   Each group has two serialisers, one for database ops and one
#                   for device ops. Also uses the database_serialiser
#
#
# - coverart:       Uses the database_serialiser and has the following serialisers:
#
#                   -   Check Covers Serialiser: so that weekly checking for
#                           new covers happens on a serialised basis
#                   -   Playlist Cover Serialiser: for making playlist covers
#                   -   Spotify Slow Serialiser            }
#                   -   Google Slow Serialiser             }
#                   -   Musicbrainz Slow Serialiser        } See
#                   -   Coverartarchive Slow Serialiser    } below
#                   -   Wikipedia Slow Serialiser          }
#                   -   HTTP Serialiser                    }
#
#                   The various slow serialisers are so that we don't hammer the
#                   various services. These enforce a min 1s gap between queued items
#                   except Coverartarchive, which is 0.25s. The Google serialiser is
#                   not currently being used.
#
# - playlist:       Has its own serialiser and uses the database_serialiser and the
#                   spotify_cache_serialiser
#
# - album:          Uses the database_serialiser for writing the database.
#
# - qimport:        Uses the database_serialiser for writing the database.
#
# - lastfm:         Has its own serialiser and uses the database_serialiser.
#

#
# The current approach to Errbacks is
# that the Serialiser does not itself
# trap or log a failure. It simply ensures
# the failure doesn't block the queue and
# allows it to pass down to the next Errback
# if there is one. Therefore, if for any
# reason, it's necessary to check if the
# serialised function has failed, a downstream
# Errback will still trigger. This in turn
# means that an Errback should be added to
# each serialised function, because the Serialiser
# doesn't do this. However, the @serialised
# decorator in util.py does automatically add
# logError as an Errback. This means that
# a downstream Errback of a function decorated with
# the @serialised decorator will not fire (because
# the failure will have been trapped by the logError
# Errback). So, an Errback need be added
# explicitly only for functions serialised other than
# through the @serialised decorator. Query, then,
# whether the Serialiser should simply trap failures
# and log them through logError. The current approach
# allows a custom Errback to be added to a function
# serialised otherwise than through the
# @serialised decorator, but is this ever done?


class Serialiser(object):

    emit = SimpleNamespace(debug=debug, warning=warning, exception=exception)

    def __init__(self, name='Unnamed Serialiser', intervals=0):
        super(Serialiser, self).__init__()
        self.name = name
        self.intervals = intervals
        self.timestamp = 0
        self.queue = deque([])
        self.queue_closed = False
        if 'DEBUG' in globals():
            self.execute = self.debug_and_execute

    def get_fn_info(self, fn):
        wrapped = fn
        while hasattr(wrapped, '__wrapped__'):
            wrapped = wrapped.__wrapped__
        return {
            'module': fn.__module__,
            'line_no': wrapped.__code__.co_firstlineno,
            'fn_name': fn.__name__
        }

    def debug_and_execute(self, result, emit, fn, *args, **kwargs):
        fn_info = self.get_fn_info(fn)
        emit.debug('{}:{}:{}:{}'.format(
            self.name,
            fn_info['module'],
            fn_info['line_no'],
            fn_info['fn_name']
        ))
        try:
            return fn(*args, **kwargs)
        except:
            emit.exception('{}:{}:{}:{}'.format(
                self.name,
                fn_info['module'],
                fn_info['line_no'],
                fn_info['fn_name']
            ))

    def execute(self, result, unused, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def serialise(self, fn, *args, **kwargs):
        return self._serialise(True, fn, *args, **kwargs)

    # Serialise without using logging to break circularity
    def logging_serialise(self, fn, *args, **kwargs):
        return self._serialise(False, fn, *args, **kwargs)

    def _serialise(self, use_logging, fn, *args, **kwargs):

        if use_logging:
            emit = log
        else:
            emit = self.emit

        # failure.trap() ensures the failure
        # is not trapped here, but will pass
        # to the next Errback if there is one
        def error(failure):
            self.queue.popleft()
            self.callnext()
            failure.trap()

        def success(result):
            self.queue.popleft()
            self.callnext()
            return result
        d = defer.Deferred()
        if self.queue_closed:
            fn_info = self.get_fn_info(fn)
            emit.warning('Ignoring attempt to serialise following')
            emit.warning('{}:{}:{}:{}'.format(
                self.name,
                fn_info['module'],
                fn_info['line_no'],
                fn_info['fn_name']
            ))
            d.callback(None)
        else:
            d.addCallback(self.execute, emit, fn, *args, **kwargs)
            d.addErrback(error)
            d.addCallback(success)
            self.queue.append(d)
            if len(self.queue) == 1:
                self.callnext()
        return d

    def callnext(self):
        if len(self.queue):
            if self.intervals:
                now = time.time()
                if now - self.timestamp < self.intervals:
                    interval = self.timestamp + self.intervals - now
                    reactor.callLater(interval, self.callnext)
                    return
                else:
                    self.timestamp = now
            d = self.queue[0]
            d.callback(None)

    def get_queue_length(self):
        return len(self.queue)

    def close_queue(self, *args, **kwargs):
        if args:
            self.serialise(*args, **kwargs)
        self.queue_closed = True
