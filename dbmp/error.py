# -*- coding: utf-8 -*-

import os
from twisted.python.failure import Failure
from .logging_setup import getLogger
log = getLogger(__name__)


class mpdException(Exception):
    pass


def logError(e):
    try:
        if isinstance(e, Failure):
            if e.frames:
                last_frame = e.frames[-1]
                try:
                    logger = getLogger(last_frame[1].split(
                        os.sep)[-1].split('.')[0])
                except Exception:
                    logger = log
                logger.error("Failure: %s", e.getTraceback())
            else:
                log.error("Failure (no frames): %s", e.getTraceback())
        else:
            log.exception(e)
    except Exception as ex:
        print('Exception in logError ...')
        print(ex)
