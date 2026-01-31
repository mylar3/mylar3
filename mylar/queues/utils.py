"""Queue info helpers."""

from collections import namedtuple

import mylar

QueueInfo = namedtuple("QueueInfo", ("name", "is_alive", "size"))


def queue_info():
    yield from (
        QueueInfo(queue_name, thread_obj.is_alive() if thread_obj is not None else None, queue.qsize())
        for (queue_name, thread_obj, queue) in [
            ("AUTO-COMPLETE-NZB", mylar.NZBPOOL, mylar.NZB_QUEUE),
            ("AUTO-SNATCHER", mylar.SNPOOL, mylar.SNATCHED_QUEUE),
            ("DDL-QUEUE", mylar.DDLPOOL, mylar.DDL_QUEUE),
            ("JD2-QUEUE", mylar.JD2POOL, mylar.JD2_QUEUE),
            ("POST-PROCESS-QUEUE", mylar.PPPOOL, mylar.PP_QUEUE),
            ("SEARCH-QUEUE", mylar.SEARCHPOOL, mylar.SEARCH_QUEUE),
        ]
    )
