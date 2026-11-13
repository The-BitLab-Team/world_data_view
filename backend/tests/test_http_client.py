from app.collectors.base import HttpClient


def test_connect_timeout_is_short_and_read_timeout_is_configurable():
    client = HttpClient(timeout=60.0)
    assert client.timeout == (10.0, 60.0)


def test_connect_timeout_never_exceeds_the_read_timeout():
    assert HttpClient(timeout=3.0).timeout == (3.0, 3.0)


def test_requests_use_the_split_timeout(monkeypatch):
    client = HttpClient(timeout=30.0)
    seen = {}

    class FakeResponse:
        text = "ok"
        encoding = "utf-8"

        def raise_for_status(self):
            return None

    def fake_get(url, params=None, timeout=None):
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(client.session, "get", fake_get)
    assert client.get_text("https://example.org") == "ok"
    assert seen["timeout"] == (10.0, 30.0)
