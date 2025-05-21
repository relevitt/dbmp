# -*- coding: utf-8 -*-

from .sp_functions import is_music
from .error import logError
from .util import mpd_check_connected, ms_to_str
from .util import dbpooled
from twisted.internet import defer
from .logging_setup import getLogger
log = getLogger(__name__)


class qduration(object):

    @mpd_check_connected(None)
    @defer.inlineCallbacks
    def check_db_for_gaps(self):

        @dbpooled
        def get_disc_ids(tx, self):
            query = '''SELECT DISTINCT discid FROM song WHERE play_time IS NULL'''
            tx.execute(query)
            return [row["discid"] for row in tx.fetchall()]

        try:
            discids = yield get_disc_ids(self)
            for discid in discids:
                yield self.get_duration(discid, warn=False)
        except Exception as e:
            log.exception(e)

    @mpd_check_connected(None)
    def get_duration(self, discid, warn=True):
        song_ids = []
        query = '''SELECT id, filename FROM song WHERE
			discid = ? AND play_time IS NULL'''
        d = self.dbpool.fetchall_dict(query, (discid,))

        def process1(rows):
            dlist = []
            for row in rows:
                if not is_music(row['filename']):
                    pass
                else:
                    song_ids.append(row['id'])
                    dlist.append(
                        self.mpd_get_duration(row['filename'], warn))
            return defer.DeferredList(dlist)

        def process2(results):
            durations = []
            for r in results:
                if not r[0]:
                    logError(r[1])
                    durations.append(None)
                else:
                    durations.append(r[1])
            return self.insert_duration_into_db(song_ids, durations)

        d.addCallback(process1)
        d.addCallback(process2)
        d.addErrback(logError)

    @mpd_check_connected(None)
    def get_song_duration(self, filename, ms=True):
        if not is_music(filename):
            d = defer.Deferred()
            d.callback(None)
            return d

        song_id = []

        query = '''SELECT id FROM song WHERE filename = ?'''
        d = self.dbpool.fetchone_dict(query, (filename,))

        def process1(row):
            song_id.append(row['id'])
            return self.mpd_get_duration(filename)

        def process2(result):
            if result:
                self.insert_duration_into_db(song_id, [result])
                if ms:
                    return result
                else:
                    return self.millisecs_to_str(result)

        d.addCallback(process1)
        d.addCallback(process2)
        return d

    @dbpooled
    def insert_duration_into_db(tx, self, song_ids, durations):
        query = '''CREATE TEMP TABLE tmp_song ("id" INTEGER, "play_time" TEXT)'''
        tx.execute(query)
        query = '''INSERT INTO tmp_song (id, play_time) VALUES (?,?)'''

        for n, song_id in enumerate(song_ids):
            duration = durations[n]
            if duration:
                duration = self.millisecs_to_str(duration)
                tx.execute(query, (song_id, duration))

        query = '''UPDATE song SET play_time = (SELECT tmp_song.play_time
			FROM tmp_song WHERE tmp_song.id = song.id)
			WHERE EXISTS (SELECT * FROM tmp_song WHERE tmp_song.id = song.id)'''
        tx.execute(query)
        query = '''DROP TABLE tmp_song'''
        tx.execute(query)

    def mpd_get_duration(self, filename, warn=True):

        d = self.mpd.medialib_get_info(filename)

        def process(result):
            if not result:
                return self.mpd.medialib_add_entry(filename).addCallback(
                    lambda _: self.mpd.medialib_get_info(filename)).addCallback(
                        check_after_adding)
            else:
                time = 0
                if isinstance(result, dict):  # If it's a dictionary
                    time = result.get('Time', 0)

                elif isinstance(result, list) and result:  # If it's a non-empty list
                    for entry in result:
                        if isinstance(entry, dict) and 'Time' in entry:
                            # Convert the duration to int if it's a string
                            try:
                                time = int(entry['Time'])
                            except ValueError:
                                time = None  # Return None if conversion fails
                return int(time) * 1000

        def check_after_adding(result):
            if not result:
                if warn:
                    log.warning(
                        'Unable to add {} to mpd database'.format(filename))
                return None
            else:
                if warn:
                    log.info('{} added to mpd database'.format(filename))
                return result['Time']

        d.addCallback(process)
        return d

    def millisecs_to_str(self, m):
        if not m:
            return
        output = ms_to_str(m)
        if output and output[0] == '0':  # eg 0:10:04
            return output[2:]  # then we'll remove the hours and return 10:04
        return output  # otherwise, we'll return the hours as well
