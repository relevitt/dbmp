# -*- coding: utf-8 -*-

from .logging_setup import getLogger
log = getLogger(__name__)

class progress(object):

    def __init__(self, WS):
        self.WS = WS

    def create(self, conn, increments=500):
        return progress_counter(self.WS, conn, increments)


class progress_counter(object):

    '''A progress_counter is there to report on progress in a potentially long running
    activity. It's being used only in qimport when importing to the quarantine.
    '''

    def __init__(self, WS, conn, increments):
        self.WS = WS
        self.conn = conn
        self.increments = increments
        self._cancelled = False
        self.reset()
        self.register_for_shutdown()

    def end(self):
        self.unregister_for_shutdown()

    def register_for_shutdown(self):
        key = (self.conn['sid'], self.conn['ticket'])
        self.WS.register_for_shutdown(key, self)

    def unregister_for_shutdown(self):
        key = (self.conn['sid'], self.conn['ticket'])
        self.WS.unregister_for_shutdown(key)

    def check_cancelled(self):
        return self._cancelled

    def cancel(self):
        log.info('cancelling')
        self._cancelled = True
    def reset(self, n=0):
        self.c0 = n
        self.c1 = n
        self.send = self.WS_progress

    def mode(self, mode):
        if mode == 'init':
            self.send = self.WS_total_calc
        else:
            self.send = self.WS_progress

    def total(self, n=False):
        if n == False:
            n = self.c0
        self.WS_total(n)

    def inc(self, n=1):
        self.c0 += n
        self.c1 += n
        if self.c1 >= self.increments:
            self.c1 = 0
            self.send(self.c0)

    def WS_total_calc(self, n):
        self.WS_send('progress_total_calc', 'total_calc', n)

    def WS_total(self, n):
        self.WS_send('progress_total', 'total', n)

    def WS_progress(self, n):
        self.WS_send('progress_count', 'count', n)

    def WS_send(self, typ, key, n):
        items = {}
        items['ticket'] = self.conn['ticket']
        items['type'] = typ
        items[key] = n
        self.WS.WS_send_sid(self.conn['sid'], items)

    def send_and_await_result(self, items):
        items['ticket'] = self.conn['ticket']
        return self.WS.WS_send_sid_and_await_result(
            self.conn['sid'], self.conn['ticket'], items)

