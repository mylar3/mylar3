import datetime
import time
import pytest

# 30 seconds to the King's Speech, get the mince pies ready
BASE_TZ = datetime.timezone.utc
STATIC_TIME = datetime.datetime(2001, 12, 25, 14, 59, 30, tzinfo=BASE_TZ)
TIME_SINCE_EPOCH = (STATIC_TIME - datetime.datetime.fromtimestamp(0, tz=BASE_TZ)).total_seconds()
USER_TZ = datetime.timezone(datetime.timedelta(hours=2))
USER_TIME = datetime.datetime.fromtimestamp(TIME_SINCE_EPOCH, tz=USER_TZ)

@pytest.fixture
def patch_datetime(monkeypatch):

    class mockdate(datetime.date):
        @classmethod
        def today(cls):
            return STATIC_TIME.astimezone(USER_TZ).date()

    class mockdatetime(datetime.datetime):
        @classmethod
        def now(cls):
            return STATIC_TIME.astimezone(USER_TZ)

        @classmethod
        def fromtimestamp(cls, _):
            return USER_TIME

    monkeypatch.setattr(datetime, 'date', mockdate)
    monkeypatch.setattr(datetime, 'datetime', mockdatetime)


@pytest.fixture
def patch_time(monkeypatch):

    class mocktime():
        @classmethod
        def time(cls):
            return TIME_SINCE_EPOCH

    monkeypatch.setattr(time, 'time', mocktime.time)
