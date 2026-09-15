"""Server-side OAuth and opaque app sessions. CAD tokens never reach the helper."""

import json
import secrets
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from .model import LinkError, digest, require
from .onshape import Client, secure_opener

AUTH_URL = "https://oauth.onshape.com/oauth/authorize"
TOKEN_URL = "https://oauth.onshape.com/oauth/token"


class ConnectionFailure(LinkError):
    """A fixed, credential-free explanation suitable for the connection screen."""


def token_request(fields):
    try:
        with secure_opener().open(
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
    except HTTPError as error:
        status = error.code
        error.close()
        raise ConnectionFailure(
            f"Onshape rejected authorization (HTTP {status}). Check the client ID and secret."
        ) from None
    except URLError:
        raise ConnectionFailure(
            "Could not securely reach Onshape. Check your internet connection and computer's date and time."
        ) from None
    except (OSError, ValueError):
        raise ConnectionFailure("Onshape authorization failed. Try connecting again.") from None


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
        if not (pending and isinstance(code, str) and 0 < len(code) <= 4096):
            raise ConnectionFailure("Sign-in expired or was already used. Connect again.")
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
