"""Shared SQLite connection helper for the SQLite-backed adapters.

The prepare job writes from several threads while the API reads, which produced
"database is locked" errors when every call opened its own connection. This
helper keeps ONE long-lived connection per database file for the whole process,
serializes access to it with a lock, and uses WAL. Reusing the connection also
avoids the WAL checkpoint (and disk sync) that SQLite runs whenever the last
connection to a file closes, which made each operation cost tens of ms.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

BUSY_TIMEOUT_SECONDS = 30.0

_registry_lock = threading.Lock()
_connections: dict[str, tuple[sqlite3.Connection, threading.RLock]] = {}


def _shared_connection(db_path: str) -> tuple[sqlite3.Connection, threading.RLock]:
    with _registry_lock:
        if db_path not in _connections:
            connection = sqlite3.connect(
                db_path, timeout=BUSY_TIMEOUT_SECONDS, check_same_thread=False
            )
            connection.execute("PRAGMA journal_mode=WAL")
            # With WAL, NORMAL skips the fsync on every commit; a power loss can drop
            # the last transaction but never corrupts the file, fine for a local cache.
            connection.execute("PRAGMA synchronous=NORMAL")
            _connections[db_path] = (connection, threading.RLock())
        return _connections[db_path]


@contextmanager
def open_connection(db_path: str) -> Iterator[sqlite3.Connection]:
    connection, lock = _shared_connection(db_path)
    with lock, connection:
        yield connection
