import os

import pytest
from mockito import verify

import mylar
from mylar.queues import ddl_cleanup


@pytest.mark.unit
def test_ddl_cleanup(when, monkeypatch):
    monkeypatch.setattr(mylar, "CONFIG", mylar.config.Config("./nothing"))
    monkeypatch.setattr(mylar.CONFIG, "CACHE_DIR", os.getcwd(), raising=False)
    when(os).remove(...)
    ddl_cleanup('1234')
    verify(os, times=1).remove(os.path.join(os.getcwd(), "html_cache", "getcomics-1234.html"))

## Queue Functions to mock
# postprocess_main
# search_queue
# worker_main
# nzb_monitor
# cdh_monitor
# queue_inf
