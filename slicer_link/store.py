"""Small SQLite store for the single-process service; encrypted OAuth tokens."""

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet

from .model import canonical, require


class Store:
    def __init__(self, directory, encryption_key):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cipher = Fernet(encryption_key)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / "app.sqlite3", check_same_thread=False)
        require(
            self.db.execute("PRAGMA user_version").fetchone()[0] in {0, 1},
            "This database needs a newer version of Slicer Link.",
        )
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                kind TEXT NOT NULL, id TEXT NOT NULL, owner TEXT NOT NULL,
                expires REAL, data TEXT NOT NULL, PRIMARY KEY(kind,id)
            );
            CREATE INDEX IF NOT EXISTS records_owner ON records(kind,owner);
            CREATE TABLE IF NOT EXISTS usage (
                owner TEXT NOT NULL, day TEXT NOT NULL, attempts INTEGER NOT NULL,
                successful INTEGER NOT NULL, PRIMARY KEY(owner,day)
            );
            PRAGMA user_version=1;
        """)

    def close(self):
        self.db.close()

    def encrypt(self, value):
        return self.cipher.encrypt(canonical(value).encode()).decode()

    def decrypt(self, value):
        return json.loads(self.cipher.decrypt(value.encode()))

    @contextmanager
    def transaction(self):
        with self.lock, self.db:
            yield

    def put(self, kind, key, owner, data, *, ttl=None):
        expiry = time.time() + ttl if ttl is not None else None
        with self.transaction():
            self.db.execute("DELETE FROM records WHERE expires IS NOT NULL AND expires<=?", (time.time(),))
            self.db.execute(
                "INSERT OR REPLACE INTO records VALUES (?,?,?,?,?)",
                (kind, key, owner, expiry, canonical(data)),
            )

    def get(self, kind, key):
        with self.lock:
            row = self.db.execute(
                "SELECT data,expires FROM records WHERE kind=? AND id=?", (kind, key)
            ).fetchone()
        if row and (row[1] is None or row[1] > time.time()):
            return json.loads(row[0])
        return None

    def consume(self, kind, key):
        with self.transaction():
            row = self.db.execute(
                "DELETE FROM records WHERE kind=? AND id=? RETURNING data,expires", (kind, key)
            ).fetchone()
        if row and (row[1] is None or row[1] > time.time()):
            return json.loads(row[0])
        return None

    def list(self, kind, owner=None):
        query = "SELECT data FROM records WHERE kind=? AND (expires IS NULL OR expires>?)"
        args = [kind, time.time()]
        if owner is not None:
            query += " AND owner=?"
            args.append(owner)
        with self.lock:
            return [json.loads(row[0]) for row in self.db.execute(query, args).fetchall()]

    def delete(self, kind, key):
        with self.transaction():
            self.db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, key))

    def record_request(self, owner, status):
        day = time.strftime("%Y-%m-%d", time.gmtime())
        with self.transaction():
            self.db.execute(
                """INSERT INTO usage VALUES (?,?,1,?) ON CONFLICT(owner,day)
                DO UPDATE SET attempts=attempts+1, successful=successful+excluded.successful""",
                (owner, day, int(200 <= status < 400)),
            )

    def usage(self, owner):
        with self.lock:
            rows = self.db.execute(
                "SELECT day,attempts,successful FROM usage WHERE owner=? ORDER BY day DESC", (owner,)
            ).fetchall()
        return [
            {"day": day, "attempts": attempts, "successful": successful} for day, attempts, successful in rows
        ]
