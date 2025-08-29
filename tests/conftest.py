import pytest
import requests

@pytest.fixture(autouse=True)
def disable_network_calls(monkeypatch):
    def mock_request():
        raise RuntimeError("Requests monkeypatched out - needs implementing on a case by case basis")
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_request())

