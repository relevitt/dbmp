# -*- coding: utf-8 -*-

from .error import logError
from .qduration import qduration
from .paths import Downloadspath, Musicpath, Searchpath, HOMEDIR, APPDIR
from .util import logerror
from .util import dbpooled
from .util import database_serialised
from binaryornot.check import is_binary
from sqlite3 import OperationalError
from twisted.internet.utils import getProcessOutput
from twisted.internet import defer, task, reactor
from datetime import datetime
import os
from .logging_setup import getLogger
log = getLogger(__name__)


def doc_to_text_catdoc(filename):

    def success(result):
        return result.splitlines()

    def failure(e):
        logError(e)
        return []

    scripts = APPDIR / "scripts"
    catdocx = scripts / "catdocx.sh"

    d = getProcessOutput(str(catdocx), (filename,), errortoo=True)
    d.addCallback(success)
    d.addErrback(failure)
    return d

# For convenience, the get_duration function is stored in qduration.py


class qimport(qduration):

    def __init__(self, objects, progress):
        self.objects = objects
        self.dbpool = objects['dbpool']
        self.progress = progress
        self.db_temp_table_counter = 0
        self.mpd = objects['mpd']
        self.set_root()
        # Check db for songs missing play_time:
        # 10s after startup and then every 24 hours
        reactor.callLater(10, self.check_db_for_gaps)
        task.LoopingCall(self.check_db_for_gaps).start(86400, now=False)

    def set_root(self):
        self.root = str(Searchpath.get_path())
        while not os.path.samefile(self.root, os.path.dirname(self.root)):
            self.root = os.path.dirname(self.root)

    def path_to_list(self, path, check_exists=False):
        li = []
        li_new = []
        switched = False
        while not os.path.exists(path) or (os.path.exists(path) and not os.path.samefile(self.root, path)):
            if check_exists and not switched:
                if os.path.exists(path):
                    li_new, li = li, []
                    switched = True
            path, n = os.path.split(path)
            li.append(n)
        li.append('Filesystem')
        li.reverse()
        if li_new:
            li_new.reverse()
        if check_exists:
            return li, li_new
        return li

    def list_to_path(self, li):
        dirname = self.root
        while len(li) > 1:
            dirname = os.path.join(dirname, li.pop(1))
        return dirname

    def listdir(self, path, directory=''):
        return self.objects['spfactory'].process_command('listdir', path, directory)

    def extract_zip(self, location, path, progress_counter):

        var = {}
        var['filenames'] = None

        def process_zipfile_list(results):
            items, var['filenames'] = results
            if not items:
                return []
            return progress_counter.send_and_await_result(items)

        def unzip(results):
            return self.objects['spfactory'].process_command(
                'unzip_musicfiles',
                results,
                var['filenames'],
                path,
                self.root)

        def report_outcome(results):
            music_files, already_exists = results
            for dest in already_exists:
                log.warning(
                    '{} already exists ... extraction skipped'.format(dest))
            return music_files

        d = self.objects['spfactory'].process_command(
            'list_musicfiles_in_zipfile',
            location,
            path,
            self.root)

        d.addCallback(process_zipfile_list)
        d.addCallback(unzip)
        d.addCallback(report_outcome)
        return d

    @logerror
    def qlist(self, args):
        if not len(args['items']):
            dirname = str(Searchpath.get_path())
        else:
            dirname = self.list_to_path(args['items'])
        return self.directory_listing(dirname)

    @logerror
    def qlist_home(self, args):
        return self.directory_listing(str(HOMEDIR))

    @logerror
    def qlist_search(self, args):
        return self.directory_listing(str(Searchpath.get_path()))

    @logerror
    def qlist_downloads(self, args):
        return self.directory_listing(str(Downloadspath.get_path()))

    def directory_listing(self, dirname):
        d = self.listdir(dirname)

        def process(result):
            result['cwd'] = self.path_to_list(dirname)
            return result
        d.addCallback(process)
        return d

    def make_directory(self, args):
        path = os.path.join(args['cwd'], args['name'])
        if os.path.exists(path):
            log.warning('Directory exists.')
            return {'exists': True}
        try:
            os.makedirs(path)
        except:
            log.warning('Could not make new directory.')
            return {'failure': True}
        return self.listdir(path)

    def importtosearch(self, args):

        var = {}
        var['walker'] = None
        var['walker_results'] = None
        var['zipfiles'] = []
        var['zipfile_in_process'] = None
        var['cancelled'] = False

        results = {
            'directories': {
                'success': [],
                'failure': []
            },
            'files': {
                'success': [],
                'failure': []
            }
        }

        location = str(Musicpath.get_path())
        if not location:
            log.warning(
                'Warning ... MUSICPATH (%s) not found. Using %s instead.',
                Musicpath.defaultpath,
                HOMEDIR)
            location = str(HOMEDIR)

        directories = []
        files = []

        for d in args['dirs']:
            directories.append(self.list_to_path(d))

        for f in args['files']:
            filename = self.root
            while len(f) > 1:
                filename = os.path.join(filename, f.pop(1))
            files.append(filename)

        temp_table_name = 'tmp_search_{}'.format(
            str(self.db_temp_table_counter))
        self.db_temp_table_counter += 1

        p = self.progress.create(args['progress'])
        p.mode('init')

        d1 = defer.Deferred()
        d2 = defer.Deferred()
        d3 = defer.Deferred()

        @database_serialised
        @dbpooled
        def create_temp_table(tx, self):
            def create_table():
                query = '''	CREATE TABLE {}
					   		(filename TEXT, title TEXT, album TEXT,
                            artist TEXT, extra TEXT, tag_title TEXT,
                            tag_album TEXT, tag_artist TEXT, tag_genre TEXT,
                            tag_track_num INTEGER, updated INTEGER)'''.format(
                    temp_table_name)
                tx.execute(query)
            try:
                create_table()
            except OperationalError as e:
                if 'already exists' in e.args[0]:
                    query = '''DROP table {}'''.format(temp_table_name)
                    tx.execute(query)
                    create_table()
                else:
                    raise

        @database_serialised
        @dbpooled
        def add_to_temp_table(tx, self, rows):
            query = ''' INSERT INTO {}
                        (filename, title, album, artist, extra, tag_title,
                        tag_album, tag_artist, tag_genre, tag_track_num,
                        updated)
                        VALUES (:filename, :title, :album, :artist, :extra,
                        :tag_title, :tag_album, :tag_artist, :tag_genre,
                        :tag_track_num, 0)'''.format(
                temp_table_name)
            tx.executemany(query, rows)

        def init(walker):
            var['walker'] = walker
            count(None)
            return d1

        def count(result):
            if p.check_cancelled():
                var['cancelled'] = True
                d1.callback(None)
                return
            if result:
                p.inc(result['count'])
                if result['count_complete']:
                    p.inc(len(files))
                    p.total()
                    p.reset()
                    d1.callback(None)
                    return
            self.objects['spfactory'].process_command(
                'WALKER.count',
                var['walker']).addCallback(count)

        def start_walking(result):
            if var['cancelled']:
                d2.callback(None)
            else:
                walk(None)
            return d2

        def walk(result):
            if p.check_cancelled():
                var['cancelled'] = True
                d2.callback(None)
                return
            if result:
                p.inc(result['count'])
                add_to_temp_table(self, result['rows'])
                if result['walk_complete']:
                    var['walker_results'] = result['walk_complete']
                    d2.callback(None)
                    return
            self.objects['spfactory'].process_command(
                'WALKER.walk',
                var['walker']).addCallback(walk)

        def start_extracting_zipfiles(result):
            if var['cancelled']:
                d3.callback(None)
            else:
                extract(None)
            return d3

        def extract(result):
            if p.check_cancelled():
                var['cancelled'] = True
                d3.callback(None)
                return
            if result:
                var['zipfiles'] += result
                source = var['zipfile_in_process']['source']
                source_path = var['zipfile_in_process']['source_path']
                var['walker_results'][source][source_path] = 'success'
            if len(var['walker_results']['zipfiles']):
                var['zipfile_in_process'] = var['walker_results']['zipfiles'].pop(
                    0)
                path = var['zipfile_in_process']['path']
                self.extract_zip(location, path, p).addCallback(extract)
            else:
                wr = var['walker_results']
                def res(source, outcome): return [
                    p for p in wr[source].keys() if wr[source][p] == outcome]
                for s in ['directories', 'files']:
                    for o in ['success', 'failure']:
                        results[s][o] = res(s, o)
                d3.callback(None)

        def add_zipfiles(result):
            if var['cancelled']:
                return
            if p.check_cancelled():
                var['cancelled'] = True
                return
            p.end()

            return self.objects['spfactory'].process_command(
                'WALKER.zipfiles',
                var['walker'],
                var['zipfiles']).addCallback(
                    lambda result: add_to_temp_table(self, result))

        def import_to_db(result):
            self.objects['spfactory'].process_command(
                'WALKER.cancel',
                var['walker'])
            if var['cancelled']:
                return
            return import_to_search(self)

        @database_serialised
        @dbpooled
        def import_to_search(tx, self):
            query = '''INSERT OR IGNORE INTO search (filename, title, album, artist, extra, tag_title, tag_album,
			    tag_artist, tag_genre, tag_track_num, updated)
			    SELECT filename, title, album, artist, extra, tag_title, tag_album,
			    tag_artist, tag_genre, tag_track_num, updated
			    FROM {}'''.format(temp_table_name)
            tx.execute(query)

        @database_serialised
        @dbpooled
        def drop_temp_table(tx, self):
            query = '''	DROP TABLE {}'''.format(temp_table_name)
            tx.execute(query)
            if not var['cancelled']:
                return results

        d = create_temp_table(self)
        d.addCallback(lambda _: self.objects['spfactory'].process_command(
            'WALKER.init',
            directories,
            files))
        d.addCallback(init)
        d.addCallback(start_walking)
        d.addCallback(start_extracting_zipfiles)
        d.addCallback(add_zipfiles)
        d.addCallback(import_to_db)
        d.addCallback(lambda _: drop_temp_table(self))
        return d

    @database_serialised
    @dbpooled
    def quarantine(tx, self, args):
        query = ''' SELECT COUNT(*) FROM
                    (SELECT id FROM search
                    GROUP BY updated, extra, artist, album)'''
        tx.execute(query)
        length = tx.fetchone()[0]
        if length:
            query = ''' SELECT MIN(id) AS id, artist, album
                        FROM search
                        GROUP BY updated, extra, artist, album
                        ORDER BY artist, album
                        LIMIT ? OFFSET ?'''
            tx.execute(query, (args['numRows'], args['startIndex']))
            rows = tx.fetchall()
            results = [dict(row) for row in rows]
        else:
            results = []
        return {
            'results': results,
            'startIndex': args['startIndex'],
            'totalRecords': length
        }

    @database_serialised
    @dbpooled
    def delete(tx, self, args):
        for n in args['indices']:
            query = '''SELECT album, artist, extra, updated FROM search WHERE id = ?'''
            tx.execute(query, (n,))
            row = tx.fetchone()
            query = '''DELETE FROM search WHERE album like ? AND artist like ? AND extra like ?
				AND updated = ?'''
            tx.execute(
                query,
                (row['album'],
                    row['artist'],
                    row['extra'],
                    row['updated']))

    @database_serialised
    @dbpooled
    def getids(tx, self, args):
        query = ''' SELECT COUNT(*) FROM
                    (SELECT id FROM search
                    GROUP BY updated, extra, artist, album)'''
        tx.execute(query)
        length = tx.fetchone()[0]
        start = args['startIndex']
        if start > length - 1:
            start = int((length - 1) / args['rowsPerPage']) * args[
                'rowsPerPage']
        start = max(start, 0)
        if length:
            query = ''' SELECT MIN(id) AS id
                        FROM search
                        GROUP BY updated, extra, artist, album
                        ORDER BY artist, album
                        LIMIT ? OFFSET ?'''
            tx.execute(query, (args['rowsPerPage'], start))
            rows = tx.fetchall()
            results = [row['id'] for row in rows]
        else:
            results = []
        res = {}
        res['totalRecords'] = length
        res['results'] = results
        return res

    @database_serialised
    @dbpooled
    def duplicates(tx, self, *args):
        query = '''DELETE FROM search WHERE id IN
			(SELECT search.id FROM search JOIN song ON
			(search.filename = song.filename))'''
        tx.execute(query)

    @database_serialised
    @dbpooled
    def clear(tx, self, *args):
        query = '''DELETE FROM search'''
        tx.execute(query)

    @database_serialised
    @dbpooled
    def edit(tx, self, args):
        query = '''SELECT album, artist, extra, updated FROM search WHERE id = ?'''
        tx.execute(query, (args['id'],))
        row = tx.fetchone()
        res = {
            'artist': row['artist'],
            'album': row['album']
        }
        updated = row['updated']
        results = []
        if updated:
            query = '''SELECT id, title FROM search WHERE album like ? AND artist like ? AND
				extra like ? AND updated = ? ORDER BY id'''
        else:
            query = '''SELECT tag_track_num FROM search WHERE album like ? AND artist like ? AND
				extra like ? AND updated = ?'''
            tx.execute(
                query,
                (row['album'],
                    row['artist'],
                    row['extra'],
                    row['updated']))
            use_tag_track_num = True
            for r in tx.fetchall():
                if not r['tag_track_num']:  # What if track_num == 0?
                    use_tag_track_num = False
                    break
            if use_tag_track_num:
                query = '''SELECT id, title, tag_title FROM search WHERE album like ? AND artist like ? AND
					extra like ? AND updated = ? ORDER BY album, tag_track_num, title'''
            else:
                query = '''SELECT id, title, NULL AS tag_title FROM search WHERE album like ? AND artist like ? AND
					extra like ? AND updated = ? ORDER BY album, title'''
        tx.execute(
            query,
            (row['album'],
                row['artist'],
                row['extra'],
                row['updated']))
        for row in tx.fetchall():
            if updated or not row['tag_title']:
                results.append({
                    'title': row['title'],
                    'id': row['id']
                })
            else:
                results.append({
                    'title': row['tag_title'],
                    'id': row['id']
                })
        res['results'] = results
        return res

# Got lazy! The approach to paths in the next functions should reflect the
# style above

    @database_serialised
    def popup(self, args):

        @dbpooled
        def get_filename(tx, self):
            query = 'SELECT filename FROM search WHERE id = ?'
            tx.execute(query, (args['id'],))
            return tx.fetchone()[0]

        def get_directory(filename):
            return self.listdir(os.path.dirname(filename))

        d = get_filename(self)
        d.addCallback(get_directory)
        return d

    def popupFile(self, args):
        fname = os.path.join(args['items'][0], args['items'][1])
        binary = 0
        content = []
        lines = []
        if fname[-3:] == 'doc' or fname[-4:] == 'docx':
            d = doc_to_text_catdoc(fname)
        elif is_binary(fname):
            binary = 1
            d = defer.Deferred()
            d.callback(None)
        else:
            with open(fname, 'r+b') as f:
                lines = f.readlines()
            d = defer.Deferred()
            d.callback(lines)

        def process(lines):
            if lines:
                for l in lines:
                    try:
                        if isinstance(l, bytes):
                            line = l.decode('utf8')
                    except:
                        log.warning(
                            'Could not fully decode following line: %s',
                            l.strip(b'\n'))
                        line = ''
                        for c in l:
                            try:
                                line += c.decode('utf8')
                            except:
                                pass
                    while len(line) > 100:
                        n = line.find(u' ', 100)
                        if n > 0:
                            sub = line[0:n]
                            line = line[n + 1:]
                        else:
                            sub = line[0:100]
                            line = line[101:]
                        if len(sub) > 1 and sub[-1] == '\n':
                            sub = sub[:-1]
                        content.append(sub)
                    if len(line) > 1 and line[-1] == '\n':
                        line = line[:-1]
                    content.append(line)
            return {'content': content, 'binary': binary}
        d.addCallback(process)
        return d

    @database_serialised
    @dbpooled
    def update(tx, self, args):
        if not len(args['songs']):
            return 0
        query = '''SELECT MAX(updated) AS updated FROM search'''
        tx.execute(query)
        updated = int(tx.fetchone()['updated']) + 1
        for song in args['songs']:
            query = '''SELECT filename, extra, tag_title, tag_album, tag_artist, tag_genre,
				tag_track_num FROM search WHERE id = ?'''
            tx.execute(query, (song['id'],))
            row = tx.fetchone()
            query = '''DELETE FROM search WHERE id like ?'''
            tx.execute(query, (song['id'],))
            query = '''INSERT INTO search (filename,title,album,artist,extra,tag_title,tag_album,tag_artist,tag_genre,
				tag_track_num, updated) VALUES (?,?,?,?,?,?,?,?,?,?,?)'''
            tx.execute(
                query, (
                    row['filename'], song['title'], args[
                        'album'], args['artist'], row['extra'],
                    row['tag_title'], row['tag_album'], row[
                        'tag_artist'], row['tag_genre'], row['tag_track_num'],
                    updated))
        query = '''SELECT id FROM search WHERE album like ? AND artist like ? AND extra like ?
			AND updated = ? ORDER BY id LIMIT 1'''
        tx.execute(
            query,
            (args['album'],
             args['artist'],
                row['extra'],
                updated))
        row = tx.fetchone()
        return row['id']

    def qimport(self, args):

        @database_serialised
        @dbpooled
        def add(tx, self, args):
            results = {}
            results['songs'] = []
            date = datetime.now().strftime('%Y-%m-%d')

            query = '''SELECT id FROM artist WHERE artist like ?'''
            tx.execute(query, (args['artist'],))
            row = tx.fetchone()
            if row and dict(row).get('id'):
                artist_id = row['id']
            else:
                query = '''SELECT MAX(id) AS id FROM artist'''
                tx.execute(query)
                row = tx.fetchone()
                if not row['id']:
                    artist_id = 1
                else:
                    artist_id = row['id'] + 1
                query = '''INSERT INTO artist values (?, ?, ?, NULL)'''
                tx.execute(query, (artist_id, args['artist'], date))

            query = '''SELECT MAX(id) AS id FROM disc'''
            tx.execute(query)
            row = tx.fetchone()
            if not row['id']:
                disc_id = 1
            else:
                disc_id = row['id'] + 1
            query = '''INSERT INTO disc values (?, ?, ?, NULL, NULL, ?, NULL, 1)'''
            tx.execute(query, (disc_id, args['album'], artist_id, date))

            for i, song in enumerate(args['songs']):
                searchid = song['id']
                query = '''SELECT filename FROM search WHERE id = ?'''
                tx.execute(query, (searchid,))
                row = tx.fetchone()
                filename = row['filename']
                query = '''SELECT MAX(id) AS id FROM song'''
                tx.execute(query)
                row = tx.fetchone()
                if not row['id']:
                    song_id = 1
                else:
                    song_id = row['id'] + 1
                query = '''INSERT INTO song values (?, ?, ?, ?, ?,
					NULL, ?, NULL, NULL, NULL, NULL, ?)'''
                tx.execute(
                    query,
                    (song_id,
                        filename,
                        song['title'],
                        artist_id,
                        disc_id,
                        i,
                        date))
                query = '''DELETE FROM search WHERE id = ?'''
                tx.execute(query, (searchid,))

            query = '''SELECT title, discid, artistid FROM song WHERE discid = ? ORDER BY track_num'''
            tx.execute(query, (disc_id,))
            rows = tx.fetchall()
            for i, row in enumerate(rows):
                if not i:
                    query = '''SELECT artist FROM artist WHERE id = ?'''
                    tx.execute(query, (row['artistid'],))
                    r = tx.fetchone()
                    results['artist'] = r['artist']
                    query = '''SELECT title FROM disc WHERE id = ?'''
                    tx.execute(query, (row['discid'],))
                    r = tx.fetchone()
                    results['album'] = r['title']
                results['songs'].append(row['title'])
            return {
                'results': results,
                'discid': disc_id
            }

        def duration(results):
            self.get_duration(results['discid'])
            return results['results']

        d = add(self, args)
        d.addCallback(duration)
        return d
