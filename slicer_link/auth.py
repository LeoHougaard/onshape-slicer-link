"""Server-side OAuth and opaque app sessions. CAD tokens never reach the helper."""

import json
import secrets
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from .model import LinkError, digest, require
from .onshape import Client, NoRedirect

AUTH_URL = "https://oauth.onshape.com/oauth/authorize"
TOKEN_URL = "https://oauth.onshape.com/oauth/token"


def token_request(fields):
    try:
        with build_opener(NoRedirect).open(
            Request(
                TOKEN_URL,
                data=urlencode(fields).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ),
            timeout=30,
        ) as response:
            data = response.read(64 * 1024 + 1)
            require(len(data) <= 64 * 1024, "Invalid authorization response.")
            return json.loads(data)
    except (OSError, ValueError):
        raise LinkError("Onshape authorization failed. Try connecting again.") from None


class Auth:
    def __init__(self, store, client_id, client_secret, origin, transport=token_request):
        self.store, self.client_id, self.client_secret = store, client_id, client_secret
        self.origin, self.transport = origin, transport
        self.lock = threading.RLock()

    def begin(self, nonce):
        require(
            self.client_id and self.client_secret,
            "The operator must configure the Onshape application first.",
        )
        require(isinstance(nonce, str) and 32 <= len(nonce) <= 128, "Invalid sign-in request.")
        state = secrets.token_urlsafe(32)
        self.store.put("oauth", digest(state.encode()), "", {"nonce": nonce}, ttl=600)
        return (
            AUTH_URL
            + "?"
            + urlencode(
                {
                    "response_type": "code",
                    "client_id": self.client_id,
                    "redirect_uri": self.origin + "/auth/callback",
                    "scope": "OAuth2Read",
                    "state": state,
                }
            )
        )

    def _tokens(self, tokens):
        require(
            isinstance(tokens, dict)
            and all(isinstance(tokens.get(k), str) and tokens[k] for k in ("access_token", "refresh_token")),
            "Onshape did not issue valid credentials.",
        )
        expires = tokens.get("expires_in")
        require(isinstance(expires, (int, float)) and 0 < expires <= 86400, "Invalid token expiry.")
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_at": time.time() + expires,
        }

    def complete(self, state, code):
        pending = self.store.consume("oauth", digest(state.encode()))
        require(
            pending and isinstance(code, str) and 0 < len(code) <= 4096,
            "Sign-in expired or was already used. Connect again.",
        )
        tokens = self._tokens(
            self.transport(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.origin + "/auth/callback",
                }
            )
        )
        info = Client(tokens["access_token"]).request("/api/v16/users/sessioninfo")
        owner = info.get("id") or info.get("userId")
        require(
            isinstance(owner, str) and len(owner) == 24, "Onshape did not identify the signed-in account."
        )
        self.store.record_request(owner, 200)
        self.store.put("account", owner, owner, {"id": owner, "tokens": self.store.encrypt(tokens)})
        login_code = secrets.token_urlsafe(32)
        self.store.put(
            "login", digest(login_code.encode()), owner, {"owner": owner, "nonce": pending["nonce"]}, ttl=120
        )
        return login_code, pending["nonce"]

    def exchange(self, code, nonce):
        with self.lock:
            key = digest(code.encode())
            pending = self.store.get("login", key)
            require(
                pending and secrets.compare_digest(pending["nonce"], nonce), "Sign-in could not be verified."
            )
            self.store.consume("login", key)
            token = secrets.token_urlsafe(32)
            self.store.put(
                "session",
                digest(token.encode()),
                pending["owner"],
                {"owner": pending["owner"]},
                ttl=12 * 3600,
            )
            return token

    def owner(self, token):
        session = self.store.get("session", digest(token.encode()))
        require(session, "Connect to Onshape to continue.")
        return session["owner"]

    def client(self, owner):
        with self.lock:
            account = self.store.get("account", owner)
            require(account, "Reconnect your Onshape account.")
            tokens = self.store.decrypt(account["tokens"])
            if tokens["expires_at"] <= time.time() + 120:
                tokens = self._tokens(
                    self.transport(
                        {
                            "grant_type": "refresh_token",
                            "refresh_token": tokens["refresh_token"],
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                        }
                    )
                )
                # Refresh does not perform the old probe's extra document-list call.
                self.store.put("account", owner, owner, {"id": owner, "tokens": self.store.encrypt(tokens)})
            return Client(tokens["access_token"], lambda status: self.store.record_request(owner, status))
