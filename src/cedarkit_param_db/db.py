"""Explicit schema-4 connections and validated transactions. No implicit migration."""

from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = (
    PROJECT_ROOT / "cedarkit_param.db"
)  # Archived v3 input; never auto-upgrade.
SCHEMA_VERSION = 4


def connect(db_path, *, readonly=False):
    path = Path(db_path).resolve()
    conn = sqlite3.connect(
        path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if readonly:
        conn.execute("PRAGMA query_only = ON")
    return conn


def require_schema(conn):
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()
    if row is None or row[0] != str(SCHEMA_VERSION):
        raise ValueError(
            "schema 4 required; explicitly migrate identified legacy inputs to a new copy"
        )
    return SCHEMA_VERSION


def schema_version(db_path):
    conn = connect(db_path, readonly=True)
    try:
        return require_schema(conn)
    finally:
        conn.close()


def init_db(db_path):
    """Create a new database exclusively; never overwrite an existing path."""
    path = Path(db_path)
    with path.open("xb"):
        pass
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            files("cedarkit_param_db")
            .joinpath("schema.sql")
            .read_text(encoding="utf-8")
        )
        conn.executescript(
            files("cedarkit_param_db")
            .joinpath("review.sql")
            .read_text(encoding="utf-8")
        )
        conn.commit()
    except BaseException:
        conn.close()
        path.unlink()
        raise
    finally:
        conn.close()
    return path


@contextmanager
def transaction(db_path):
    """Validate the entire final resource set before commit; failure rolls back all edits."""
    from .exporter import read_resources

    conn = connect(db_path)
    try:
        require_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        read_resources(conn)
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(f"foreign key violations: {list(map(tuple, violations))}")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def retire_parameter(db_path, parameter_id, reason):
    with transaction(db_path) as conn:
        if not conn.execute(
            "SELECT 1 FROM parameters WHERE parameter_id=?", (parameter_id,)
        ).fetchone():
            raise ValueError("unknown active parameter ID")
        conn.execute("DELETE FROM aliases WHERE parameter_id=?", (parameter_id,))
        conn.execute(
            "DELETE FROM parameter_notes WHERE parameter_id=?", (parameter_id,)
        )
        conn.execute("DELETE FROM parameters WHERE parameter_id=?", (parameter_id,))
        conn.execute(
            "INSERT INTO parameter_id_tombstones VALUES (?,?)", (parameter_id, reason)
        )
