# -*- coding: utf-8 -*-

import logging
import textwrap
import sys
import json
import time
import functools
from datetime import datetime
from twisted.internet import task

WS_DATEFMT = "%Y-%m-%d %H:%M:%S.%f"
FORMAT = '%(asctime)s:%(msecs)03d: %(levelname)-9s %(name)-15s %(message)s'
DATEFMT = '%H:%M:%S'

logging.basicConfig(level=logging.INFO)

warning_logs = ('requests', 'dbmp.soco')
for name in warning_logs:
    log = logging.getLogger(name)
    log.setLevel(logging.WARNING)

# info_logs = ('soco.events', 'soco.events_base_twisted')
# for name in info_logs:
# log = logging.getLogger(name)
# log.setLevel(logging.INFO)

level_color_map = {
    'DEBUG': 'magenta',
    'INFO': 'white',
    'WARNING': 'yellow',
    'ERROR': 'red'
}


def getLogger(name=None, color='default'):
    '''
            Pass an optional color parameter to set the default color
            of messages for this logger. Example:

                    from logging_setup import getLogger
                    log = getLogger(__name__, 'blue')
                    log.info('This message will be colored blue by default.')
                    log.info('But this message will be colored red.',
                             extra={'color':'red'})

            Available colors are defined in MyFormatter class.

    '''

    logger = logging.getLogger(name)
    logger.color = color
    return logger


def getColor(record):
    logger = logging.getLogger(record.name)
    default_color = getattr(logger, 'color', 'default')
    return record.__dict__.get('color', default_color)


def getLevelColor(record):
    return level_color_map.get(record.levelname, 'default')


class MyFormatter(logging.Formatter):

    '''
            This formatter allows for colored messages.	See getLogger
            for example.

            It also wraps and indents the msg body so that it appears in the console
            in its own column.

    '''

    colors = {
        'black': "\033[1;30m%s\033[1;0m",
        'red': "\033[1;31m%s\033[1;0m",
        'green': "\033[1;32m%s\033[1;0m",
        'yellow': "\033[1;33m%s\033[1;0m",
        'blue': "\033[1;34m%s\033[1;0m",
        'magenta': "\033[1;35m%s\033[1;0m",
        'cyan': "\033[1;36m%s\033[1;0m",
        'white': "\033[1;37m%s\033[1;0m"
    }

    wrapper = textwrap.TextWrapper(width=70, replace_whitespace=False)

    def formatException(self, exc_info):
        result = super().formatException(exc_info)
        if result:
            return self.wrap(result,  first_line=True)

    def format(self, record):
        msg = record.getMessage()
        output = super(MyFormatter, self).format(record)

        # Extract the intro (everything before 'msg' in output)
        intro, _, _ = output.rpartition(msg)

        # Get the default color
        color = getColor(record)
        color_code = self.colors.get(color, '%s')

        # Colorize the log level
        level_color = self.colors.get(getLevelColor(record), '%s')
        colored_levelname = level_color % record.levelname

        # Apply color to message
        colored_msg = color_code % msg
        wrapped_msg = self.wrap(colored_msg)

        # Rebuild log entry with colored level name
        return intro.replace(record.levelname, colored_levelname) + wrapped_msg

    def wrap(self, msg, first_line=False):
        msg_segments = []
        for line in msg.splitlines():
            n = len(line) - len(line.lstrip(' '))
            space = line[0:n]
            for n,  segment in enumerate(self.wrapper.wrap(line)):
                msg_segments.append(space+segment if n else segment)
        if msg_segments:
            wrapped_msg = msg_segments.pop(0) if not first_line else ''
            for segment in msg_segments:
                wrapped_msg += '\n{:>40}{}'.format('', segment)
        else:
            wrapped_msg = ''
        return wrapped_msg


class WebSocketHandler(logging.Handler):
    """ Custom logging handler that sends structured logs to WebSocket clients. """

    def __init__(self, ws_factory):
        super().__init__()
        self.ws_factory = ws_factory
        self.formatTime = logging.Formatter().formatTime

    def emit(self, record):
        """ Convert log record to a structured dict and send via WebSocket. """
        try:
            timestamp = datetime.fromtimestamp(
                record.created).strftime(WS_DATEFMT)[:-3]
            log_entry = {
                "source": 'logging',
                "timestamp": timestamp,
                "level": record.levelname,
                "name": record.name,
                "message": self.format(record),
                "color": getColor(record),
                "level_color": getLevelColor(record),
            }
            self.ws_factory.broadcast_log(log_entry)

        except Exception:
            self.handleError(record)


class spHandler(logging.StreamHandler):
    """ Custom logging handler that sends structured logs to custom stream. """

    def __init__(self, stream):
        super().__init__(stream)
        self.formatTime = logging.Formatter().formatTime

    def emit(self, record):
        """ Convert log record to a structured dict and send via custom stream. """
        try:
            timestamp = datetime.fromtimestamp(
                record.created).strftime(WS_DATEFMT)[:-3]
            log_entry = {
                "timestamp": timestamp,
                "level": record.levelname,
                "name": record.name,
                "message": self.format(record),
                "color": getColor(record),
                "level_color": getLevelColor(record),
            }
            self.stream.write(json.dumps(log_entry)+'\n')
            self.flush()

        except Exception:
            self.handleError(record)


# Defined here both because we use the logging_serialise
# function (avoids inifinite circular logging) and
# because if we import from util we get circular imports
def database_serialised(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return self.objects['database_serialiser'].logging_serialise(fn, self, *args, **kwargs)
    wrapper.__wrapped__ = fn
    return wrapper


# Defined here to avoid circular imports
def dbpooled(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return self.dbpool.runInteraction(fn, self, *args, **kwargs)
    wrapper.__wrapped__ = fn
    return wrapper


class LogStore(object):

    page_length = 50
    max_logs = 10000

    def __init__(self, objects):
        self.objects = objects
        self.dbpool = objects['dbpool']
        self.last_log = None  # Stores the last log
        self.last_log_json = None  # Caches JSON representation for fast comparison
        self.last_count = 0  # Stores the repeat count
        self.schedule_purge()

    def get_summary_log(self):
        return {
            "source": self.last_log['source'],
            "timestamp": datetime.now().strftime(WS_DATEFMT)[:-3],
            "level": "INFO",
            "name": "log_summarizer",
            "message": f"The previous log was repeated {self.last_count} times.",
            "color": "green",
            "level_color": "default"
        }

    def save_log(self, log):

        @database_serialised
        @dbpooled
        def save(tx, self, log):
            query = '''	INSERT INTO logs (timestamp, source, log)
				 		VALUES (?, ?, ?)'''
            tx.execute(query, (time.time(), log['source'], json.dumps(log)))

        # Convert log to JSON for easy comparison
        log_json = json.dumps(
            {k: log[k] for k in ["message", "source", "name", "level"] if k in log})
        repeating_log = self.last_log_json is not None and self.last_log_json == log_json

        if repeating_log:
            self.last_count += 1
            return self.get_summary_log()
        else:
            if self.last_count > 0:
                save(self, self.get_summary_log()).addErrback(print)
            self.last_log = log
            self.last_log_json = log_json
            self.last_count = 0
            save(self, log).addErrback(print)
            return log

    def get_page(self, args=None):

        @database_serialised
        @dbpooled
        def get(tx, self, args=None):
            res = {}

            res['id'] = 'all'

            if args:
                res['id'] = args.get('id', 'all')

            add_summary = self.last_count and (
                res['id'] == 'all' or res['id'] == self.last_log['source'])

            if res['id'] != 'all':
                query = '''	SELECT COUNT(*) FROM logs
                            WHERE source = ?'''
                tx.execute(query, (args['id'],))

            else:
                query = '''	SELECT COUNT(*) FROM logs'''
                tx.execute(query)

            res['totalRecords'] = tx.fetchone()[0]

            if args and 'rowsPerPage' in args:
                limit = args['rowsPerPage']
            else:
                limit = self.page_length

            if args and 'startIndex' in args and args['startIndex'] <= res['totalRecords']:
                res['startIndex'] = args['startIndex']
            else:
                res['startIndex'] = int(
                    res['totalRecords'] / self.page_length) * self.page_length
            if res['startIndex'] > 0 and res['startIndex'] == res['totalRecords']:
                res['startIndex'] -= limit

            if not res['totalRecords']:
                res['results'] = []
                return res

            if add_summary:
                res['totalRecords'] += 1
                if res['startIndex'] + limit + 1 == res['totalRecords']:
                    res['startIndex'] += limit
                    res['results'] = [self.get_summary_log()]
                    return res

            if res['id'] != 'all':
                query = ''' SELECT timestamp, log
                            FROM logs
                            WHERE source = ?
                            ORDER BY timestamp ASC
                            LIMIT ? OFFSET ?'''
                tx.execute(query, (args['id'], limit, res['startIndex']))
            else:
                query = ''' SELECT timestamp, log
                            FROM logs
                            ORDER BY timestamp ASC
                            LIMIT ? OFFSET ?'''
                tx.execute(query, (limit, res['startIndex']))

            res['results'] = [json.loads(row['log']) for row in tx.fetchall()]
            if add_summary:
                res['results'].append(self.get_summary_log())
            return res

        return get(self, args)

    def enforce_log_limit(self):

        @database_serialised
        @dbpooled
        def update_db(tx, self):
            query = '''SELECT COUNT(*) FROM logs'''
            tx.execute(query)
            total_logs = tx.fetchone()[0]

            if total_logs > self.max_logs:
                logs_to_delete = total_logs - self.max_logs
                query = '''DELETE FROM logs WHERE timestamp IN (
                            SELECT timestamp FROM logs ORDER BY timestamp ASC LIMIT ?)'''
                tx.execute(query, (logs_to_delete,))
                print(
                    f"Deleted {logs_to_delete} oldest logs to maintain limit of {self.max_logs}")

        return update_db(self).addErrback(print)

    def purge_old_logs(self):

        @database_serialised
        @dbpooled
        def update_db(tx, self):
            threshold_time = time.time() - 86400  # 24 hours ago
            query = '''DELETE FROM logs WHERE timestamp < ?'''
            tx.execute(query, (threshold_time,))
            print("Purged logs older than 24 hours")

        return update_db(self).addErrback(print)

    def schedule_purge(self):
        purge_loop1 = task.LoopingCall(self.purge_old_logs)
        # Run immediately and then every 24 hours
        purge_loop1.start(86400, now=True)
        purge_loop2 = task.LoopingCall(self.enforce_log_limit)
        # Run immediately and then every hour
        purge_loop2.start(3600, now=True)


def setup_logging(ws_factory):
    """ Sets up logging with WebSocket integration. """

    # Get root logger
    logger = logging.getLogger()

    # Remove any existing handlers to prevent duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Console handler (prints to screen)
    console_handler = logging.StreamHandler(sys.__stdout__)
    console_handler.setFormatter(MyFormatter(FORMAT, DATEFMT))

    # WebSocket handler (sends logs to WebSocket clients)
    ws_handler = WebSocketHandler(ws_factory)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(ws_handler)

    # Ensure logging errors use real stderr, not the redirected logger
    logging._original_stderr = sys.__stderr__

    # Ensure all existing loggers use the root handlers
    for logger_name in logging.root.manager.loggerDict:
        log = logging.getLogger(logger_name)
        log.handlers.clear()  # Remove existing handlers so they inherit root handlers
        log.propagate = True  # Ensure they forward logs to the root logger

    logger.info("Logging setup complete with WebSocket integration.")
