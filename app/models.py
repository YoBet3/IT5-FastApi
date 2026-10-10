"""Database layer: owns the SQLite connection and the table definitions."""
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS books (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL,
    author            TEXT    NOT NULL,
    copies_total      INTEGER NOT NULL CHECK (copies_total >= 0),
    copies_available  INTEGER NOT NULL CHECK (copies_available >= 0),
    CHECK (copies_available <= copies_total)
);

CREATE TABLE IF NOT EXISTS loans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id      INTEGER NOT NULL,
    member_id    INTEGER NOT NULL,
    borrowed_at  TEXT    NOT NULL,
    due_date     TEXT    NOT NULL,
    returned_at  TEXT,
    fine         REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (book_id)   REFERENCES books(id),
    FOREIGN KEY (member_id) REFERENCES members(id)
);
"""


class Database:
    """Wraps a SQLite file and hands out transactional connections."""

    def __init__(self, path: str = "library.db"):
        self.path = path
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores FKs unless enabled
        return conn

    def init_schema(self) -> None:
        with self.transaction() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def transaction(self):
        """Commit if the block succeeds, roll back if anything raises."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
