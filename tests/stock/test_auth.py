import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet

from slicer_link import auth as module
from slicer_link.auth import Auth
from slicer_link.model import LinkError, digest
from slicer_link.store import Store


@pytest.mark.parametrize(
    "error, expected",
    [
        (HTTPError("https://example.invalid/private-code", 401, "private-reason", {}, None), "HTTP 401"),
        (URLError("private-network-details"), "securely reach Onshape"),
    ],
)
def test_token_errors_explain_failure_without_echoing_credentials(monkeypatch, error, expected):
    class FailingOpener:
        def open(self, *args, **kwargs):
            raise error

    monkeypatch.setattr(module, "secure_opener", lambda: FailingOpener())
    with pytest.raises(module.ConnectionFailure) as failure:
        module.token_request({"client_secret": "private-secret"})
    assert expected in str(failure.value)
    assert "private-" not in str(failure.value)


def test_oauth_codes_are_one_use_nonce_bound_and_tokens_remain_server_side(tmp_path, monkeypatch):
    owner = "a" * 24
    monkeypatch.setattr(module.Client, "request", lambda client, path: {"id": owner})
    calls = []

    def transport(fields):
        calls.append(fields["grant_type"])
        return {
            "access_token": "CAD-SECRET-ACCESS",
            "refresh_token": "CAD-SECRET-REFRESH",
            "expires_in": 3600,
        }

    store = Store(tmp_path, Fernet.generate_key())
    auth = Auth(store, "client", "client-secret", "https://link.example", transport)
    nonce = "n" * 40
    state = parse_qs(urlsplit(auth.begin(nonce)).query)["state"][0]
    code, returned_nonce = auth.complete(state, "authorization-code")
    assert returned_nonce == nonce
    with pytest.raises(LinkError, match="already used"):
        auth.complete(state, "authorization-code")
    with pytest.raises(LinkError, match="verified"):
        auth.exchange(code, "wrong" * 10)
    session = auth.exchange(code, nonce)
    assert auth.owner(session) == owner
    with pytest.raises(LinkError):
        auth.exchange(code, nonce)
    with pytest.raises(LinkError):
        auth.owner("CAD-SECRET-ACCESS")
    assert calls == ["authorization_code"]
    assert store.usage(owner)[0]["successful"] == 1
    with store.lock:
        rows = store.db.execute("SELECT data FROM records").fetchall()
    assert "CAD-SECRET" not in json.dumps(rows)
    assert store.decrypt(store.get("account", owner)["tokens"])["access_token"] == "CAD-SECRET-ACCESS"
    store.close()


def test_token_refresh_has_no_extra_cad_request_and_keeps_old_grant_on_failure(tmp_path, monkeypatch):
    store = Store(tmp_path, Fernet.generate_key())
    owner = "a" * 24
    old = {"access_token": "old-access", "refresh_token": "old-refresh", "expires_at": 0}
    store.put("account", owner, owner, {"id": owner, "tokens": store.encrypt(old)})
    calls = []

    def transport(fields):
        calls.append(fields)
        if len(calls) == 1:
            raise LinkError("network unavailable")
        return {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}

    auth = Auth(store, "client", "secret", "https://link.example", transport)
    monkeypatch.setattr(module.Client, "request", lambda *args: pytest.fail("Unexpected probe API call"))
    with pytest.raises(LinkError):
        auth.client(owner)
    assert store.decrypt(store.get("account", owner)["tokens"]) == old
    assert auth.client(owner).token == "new-access"
    assert auth.client(owner).token == "new-access"
    assert len(calls) == 2
    assert calls[-1]["refresh_token"] == "old-refresh"
    assert store.usage(owner) == []
    store.close()


def test_expired_state_and_session_cannot_be_used(tmp_path):
    store = Store(tmp_path, Fernet.generate_key())
    auth = Auth(
        store,
        "client",
        "secret",
        "https://link.example",
        lambda fields: pytest.fail("Expired grant exchanged"),
    )
    store.put("oauth", digest(b"state"), "", {"nonce": "n" * 40}, ttl=-1)
    store.put("session", digest(b"session"), "a" * 24, {"owner": "a" * 24}, ttl=-1)
    with pytest.raises(LinkError):
        auth.complete("state", "code")
    with pytest.raises(LinkError):
        auth.owner("session")
    store.close()
