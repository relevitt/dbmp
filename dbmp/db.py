# -*- coding: utf-8 -*-

from .error import logError
from .paths import DB
from twisted.internet import defer
from twisted.enterprise import adbapi
import threading
import sqlite3
from .logging_setup import getLogger
log = getLogger(__name__)


# Database access is the one place where this app still uses threads, because the methods in
# adbapi.ConnectionPool run in a thread. The approach to thread safety in this app is:
#
# - no deferred may be created or referenced from within a thread
# - db functions must be called from main thread (enforced in this module)
# - thread must not reference mutable objects outside the thread if they may change their state
# - use threads.blockingCallFromThread when appropriate, but it won't stop
# a mutable object outside the thread from changing it's state afterwards (and
# before the thread finishes executing)
# - discIO generally to be done on blocking basis, except directory listing or directory walking,
# because it's generally quick and trying to implement file locking or serialised file access is
# too complicated
# - use twisted.internet.utils.getProcessOutput to get output from processes; if more complex IPC
# is needed, use subprocess_factory


class dbpool(object):

    ATTEMPTS = 5

    def __init__(self):
        self.dbpool = adbapi.ConnectionPool(
            'sqlite3',
            DB,
            check_same_thread=False,
            cp_openfun=self.set_row_factory)

    def set_row_factory(self, conn):
        conn.row_factory = sqlite3.Row

    def runInteraction(self, *args, **kwargs):
        return self.runIt(self.dbpool.runInteraction, *args, **kwargs)

    def runOperation(self, *args, **kwargs):
        return self.runIt(self.dbpool.runOperation, *args, **kwargs)

    def runQuery(self, *args, **kwargs):
        return self.runIt(self.dbpool.runQuery, *args, **kwargs)

    def runWithConnection(self, *args, **kwargs):
        return self.runIt(self.dbpool.runWithConnection, *args, **kwargs)

    def runIt(self, dbpool_fn, *args, **kwargs):

        if not isinstance(threading.current_thread(), threading._MainThread):
            raise Exception('dbpool must be called from the main thread.')

        counter = 0

        while True:

            try:
                d = dbpool_fn(*args, **kwargs)
                return d

            except sqlite3.OperationalError as e:
                if e.message == "database is locked":
                    counter += 1
                    if counter <= self.ATTEMPTS:
                        log.warning(
                            'Database is locked. Trying again ({}) ...'.format(counter))
                    else:
                        log.warning('Database is still locked. Giving up.')
                        break
                else:
                    break

            except Exception as e:
                break

        d = defer.Deferred()
        d.errback(e)
        return d

    def fetchone(self, query, *args):
        def fetchone(tx, query, *args):
            tx.execute(query, *args)
            return tx.fetchone()
        return self.runInteraction(fetchone, query, *args)

    def fetchone_dict(self, query, *args):
        def fetchone_dict(tx, query, *args):
            tx.execute(query, *args)
            result = tx.fetchone()
            if result:
                return dict(result)
            else:
                return {}
        return self.runInteraction(fetchone_dict, query, *args)

    def fetchall_dict(self, query, *args):
        d = self.runQuery(query, *args)

        def process(rows):
            return [dict(row) for row in rows]

        def error(e):
            logError(e)
            return []
        d.addCallback(process)
        d.addErrback(error)
        return d

    def fetchall_list(self, query, *args):
        d = self.runQuery(query, *args)

        def process(rows):
            return [row[0] if len(row) == 1 else [item for item in row] for row in rows]

        def error(e):
            logError(e)
            return []
        d.addCallback(process)
        d.addErrback(error)
        return d
