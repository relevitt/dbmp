# -*- coding: utf-8 -*-

from .error import logError
from .config import PORT
from twisted.web.http_headers import Headers
from twisted.web.client import Agent, BrowserLikeRedirectAgent, readBody
from twisted.internet import reactor, defer
from urllib.parse import urljoin
from collections import OrderedDict
from zipfile import ZipFile
import mutagen
from io import BytesIO
from PIL import Image
import os
from .logging_setup import getLogger
log = getLogger(__name__)


AUDIO_EXTS = ['.aac', '.aiff', '.alac', '.flac', '.m4a', '.mp3',
              '.mp4', '.m4p', '.ogg', '.pcm', '.shn', '.wav', '.wma']

BASE_URL = f"http://localhost:{PORT}"


def is_music(path): return True if os.path.splitext(
    path)[1].lower() in AUDIO_EXTS else False


def list_musicfiles_in_zipfile(location, path, root):

    filenames = []
    has_music = False
    items = {}

    def path_to_list(path):
        li = []
        li_new = []
        switched = False
        while not os.path.exists(path) or (os.path.exists(path) and not os.path.samefile(root, path)):
            if not switched:
                if os.path.exists(path):
                    li_new, li = li, []
                    switched = True
            path, n = os.path.split(path)
            li.append(n)
        li.append('Filesystem')
        li.reverse()
        if li_new:
            li_new.reverse()
        return li, li_new

    z = ZipFile(path, 'r')
    for filename in z.namelist():
        filenames.append(filename)
        if not has_music and is_music(filename):
            has_music = True

    if has_music:
        items['type'] = 'zipfiles'
        items['zipfile'] = os.path.basename(path)
        items['file_groups'] = []

        def make_group(path):
            group = {}
            group['path'] = path
            group['files'] = []
            items['file_groups'].append(group)

        for n, filename in enumerate(filenames):
            path, name = os.path.split(os.path.join(location, filename))
            if not n:
                make_group(path)
            if path != items['file_groups'][-1]['path']:
                make_group(path)
            item = {}
            item['n'] = n
            item['name'] = name
            item['deleted'] = False
            items['file_groups'][-1]['files'].append(item)

        for file_group in items['file_groups']:
            path, file_group['path'] = file_group['path'], {}
            file_group['path']['exists'], file_group[
                'path']['not_exists'] = path_to_list(path)

    z.close()
    return items, filenames


def unzip_musicfiles(results, filenames, zipfilepath, root):

    music_files = []
    already_exists = []

    def list_to_path(li):
        dirname = root
        while len(li) > 1:
            dirname = os.path.join(dirname, li.pop(1))
        return dirname

    if results:
        z = ZipFile(zipfilepath, 'r')
        for file_group in results:
            path = list_to_path(file_group['path']['exists'])
            for item in file_group['path']['not_exists']:
                path = os.path.join(path, item)
            if not os.path.exists(path):
                os.makedirs(path)
            for item in file_group['files']:
                if not item['deleted']:
                    zipfilename = filenames[item['n']]
                    filename = os.path.basename(zipfilename)
                    dest = os.path.join(path, filename)
                    if os.path.exists(dest):
                        already_exists.append(dest)
                    else:
                        if is_music(dest):
                            music_files.append(dest)
                        with z.open(zipfilename) as infile, open(dest, 'wb') as outfile:
                            data = infile.read()
                            while data:
                                outfile.write(data)
                                data = infile.read()
        z.close()
    return music_files, already_exists


def get_tagged_artwork(filename):

    try:
        audiofile = mutagen.File(filename.encode('utf8'))
        matching = [s for s in audiofile.keys() if 'APIC:' in s]
        artwork = audiofile.tags[matching[0]].data
        return artwork
    except (IndexError, AttributeError, IOError):
        pass


def coverart_make_image(filename, uris):

    dlist = []

    def make_image(dlist_results):

        results = []
        for result in dlist_results:
            if not result[0]:
                logError(result[1])
            else:
                results.append(result[1])

        log.info('Entering coverart_make_image')
        s = 250
        if len(results) == 1:
            s = s * 2
            composite_size = s, s
        elif len(results) == 2:
            composite_size = s * 2, s
        else:
            composite_size = s * 2, s * 2

        size = s, s
        composite_image = Image.new('RGB', composite_size)
        positions = [(0, 0), (s, 0), (0, s), (s, s)]

        for n, result in enumerate(results):
            im = Image.open(BytesIO(result))
            im.thumbnail(size, Image.ANTIALIAS)
            composite_image.paste(im, positions[n])
            if n == 3:
                break

        if composite_image:
            composite_image.save(filename, 'JPEG')
        log.info('Exiting coverart_make_image')

    for uri in uris:
        if uri.startswith('/'):
            uri = urljoin(BASE_URL, uri)
        dlist.append(httpRequest('GET', uri).addErrback(logError))
    d = defer.DeferredList(dlist)
    d.addCallback(make_image)
    return d


def listdir(path, directory=''):

    if directory == '':
        dirname = path
    else:
        dirname = os.path.join(path, directory)

    dirs = []
    files = []

    for entry in os.scandir(dirname):
        if entry.is_dir():
            dirs.append(entry.name)
        else:
            files.append(entry.name)

    return {'dirs': sorted(dirs), 'files': sorted(files), 'dirname': dirname}


def httpRequest(method, url, headers={}):

    # Simplified version, without 'User-Agent' added to headers,
    # no checking to see if network is up and no ability to
    # post data

    agent = BrowserLikeRedirectAgent(Agent(reactor))

    d = agent.request(
        method.encode('latin-1'),
        url.encode('latin-1'),
        Headers(headers),
        None
    )

    def cbResponse(response):
        if response.code >= 200 and response.code < 400:
            return readBody(response)
        else:
            log.warning(
                'There was a problem accessing {}:{}:{}'.format(
                    url,
                    response.code,
                    response.phrase))
            return None

    d.addCallback(cbResponse)
    return d


def get_tags(filename):

    tags = {
        'title': None,
        'album': None,
        'artist': None,
        'genre': None,
        'track_num': None
    }
    try:
        audiofile = mutagen.File(filename, easy=True)
    except:
        log.error('%s ... omitting tags: mutagen error', filename)
        return tags
    try:
        keys = audiofile.keys()
    except:
        log.error('%s ... omitting tags: unable to get any keys', filename)
        return tags
    if 'artist' in keys:
        tags['artist'] = audiofile['artist'][0]
    if 'album' in keys:
        tags['album'] = audiofile['album'][0]
    if 'title' in keys:
        tags['title'] = audiofile['title'][0]
    if 'genre' in keys:
        tags['genre'] = audiofile['genre'][0]
    if 'tracknumber' in keys:
        try:
            tags['track_num'] = int(str(audiofile['tracknumber'][0]))
        except:
            try:
                tags['track_num'] = int(
                    str(audiofile['tracknumber'][0]).split(os.sep)[0])
            except:
                tags['track_num'] = None
    return tags


def is_zip(path):

    exts = ['.zip']
    title, e = os.path.splitext(path)
    if e.lower() in exts:
        return True
    else:
        return False


class Walker(object):
    def __init__(self, directories, files):
        self.directories = directories
        self.files = files
        self.counter = 0
        self.processed = self.get_empty_processed_results()
        self.dir_index = 0
        self.gen = None
        self.directory = None
        self.results = {}
        self.results['directories'] = OrderedDict()
        self.results['files'] = OrderedDict()
        self.results['zipfiles'] = []

    def walker(self, path):
        def walk(path):
            try:
                for entry in os.scandir(path):
                    if entry.is_dir():
                        yield from walk(entry.path)
                    else:
                        yield entry
            except Exception as e:
                msg = 'Error in walker - {}'.format(str(e))
                log.exception(msg)
        yield from walk(path)

    def count(self):
        gen, directory = self.get_gen()
        if not gen:
            return self.send_count_results(complete=True)
        while self.counter < 500:
            try:
                next(gen)
            except StopIteration:
                self.gen = None
                return self.count()
            self.counter += 1
        return self.send_count_results()

    def send_count_results(self, complete=False):
        results = {}
        results['count'] = self.counter
        results['count_complete'] = complete
        self.counter = 0
        if complete:
            self.gen = None
            self.dir_index = 0
        return results

    def walk(self):
        gen, directory = self.get_gen()
        if not gen:
            return self.process_files()
        while self.counter < 100:
            try:
                entry = next(gen)
                self.process_path('directories', directory,
                                  entry.name, entry.path)
            except StopIteration:
                self.gen = None
                return self.walk()
            self.counter += 1
        return self.send_walk_results()

    def send_walk_results(self, complete=False):
        processed = self.processed
        processed['count'] = self.counter
        if complete:
            self.gen = None
            processed['walk_complete'] = self.results
        else:
            self.counter = 0
            self.processed = self.get_empty_processed_results()
        return processed

    def process_files(self):
        for path in self.files:
            self.counter += 1
            filename = os.path.basename(path)
            self.results['files'][path] = 'failure'
            self.process_path('files', path, filename, path)
        return self.send_walk_results(complete=True)

    def zipfiles(self, zipfiles):
        self.processed = self.get_empty_processed_results()
        for path in zipfiles:
            filename = os.path.basename(path)
            self.process_path(None, None, filename, path)
        return self.processed['rows']

    def process_path(self, source, source_path, filename, path):
        try:
            if is_music(filename):
                if source:
                    self.results[source][source_path] = 'success'
                row = {}
                row['filename'] = path
                row['title'], e = os.path.splitext(filename)
                head, r = os.path.split(path)
                head, row['album'] = os.path.split(head)
                head, row['artist'] = os.path.split(head)
                head, row['extra'] = os.path.split(head)
                tags = get_tags(path)
                row['tag_title'] = tags['title']
                row['tag_album'] = tags['album']
                row['tag_artist'] = tags['artist']
                row['tag_genre'] = tags['genre']
                row['tag_track_num'] = tags['track_num']
                self.processed['rows'].append(row)
            elif is_zip(filename):
                row = {}
                row['path'] = path
                row['source'] = source
                row['source_path'] = source_path
                self.results['zipfiles'].append(row)
        except:
            log.exception(
                'Problem in process_path -> process: %s: %s',
                path,
                filename)

    def get_gen(self):
        if self.gen:
            return self.gen, self.directory
        if self.dir_index == len(self.directories):
            return None, None
        self.directory = self.directories[self.dir_index]
        self.gen = self.walker(self.directory)
        self.dir_index += 1
        self.results['directories'][self.directory] = 'failure'
        return self.gen, self.directory

    def get_empty_processed_results(self):
        pr = {}
        pr['rows'] = []
        pr['count'] = 0
        pr['walk_complete'] = None
        return pr


class Dispatcher(object):

    def __init__(self):
        self.wids = 0
        self.walkers = {}

    def init(self, directories, files):
        wid = self.wids
        self.wids += 1
        self.walkers[wid] = Walker(directories, files)
        return wid

    def cancel(self, wid):
        del self.walkers[wid]

    def count(self, wid):
        return self.walkers[wid].count()

    def walk(self, wid):
        return self.walkers[wid].walk()

    def zipfiles(self, wid, zipfiles):
        return self.walkers[wid].zipfiles(zipfiles)


WALKER = Dispatcher()
