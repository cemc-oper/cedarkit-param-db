"""Complete, canonical text checkpoints for schema-4 authoring state.

SQL JSON columns remain strings so their original bytes, including legacy audit
payloads, survive reconstruction. Generated columns come from the checked schema.
"""

from contextlib import closing
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import sqlite3
import tempfile

from .db import SCHEMA_VERSION, connect, init_db, transaction
from .exporter import compact, json_text, read_resources

FORMAT = "cedarkit.authoring-state/v1"


def _quoted(name):
    return '"' + name.replace('"', '""') + '"'


def _schema(conn):
    return [
        tuple(row)
        for row in conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT GLOB 'sqlite_*' ORDER BY type,name"
        )
    ]


def _layout(conn):
    tables = []
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT GLOB 'sqlite_*' ORDER BY name"
    ):
        # table_info excludes the stored generated object_id column. It must be
        # regenerated from fixed_json rather than maintained as a second source.
        columns = list(conn.execute("PRAGMA table_info(" + _quoted(name) + ")"))
        tables.append(
            {
                "name": name,
                "columns": [c[1] for c in columns],
                "primary_key": [
                    c[1] for c in sorted(columns, key=lambda c: c[5]) if c[5]
                ],
            }
        )
    return tables


def _reference():
    with closing(sqlite3.connect(":memory:")) as conn:
        for name in ["schema.sql", "review.sql"]:
            conn.executescript(files("cedarkit_param_db").joinpath(name).read_text())
        return _schema(conn), _layout(conn)


def _table_bytes(conn, table):
    columns = table["columns"]
    query = (
        "SELECT "
        + ",".join(map(_quoted, columns))
        + " FROM "
        + _quoted(table["name"])
        + " ORDER BY "
        + ",".join(map(_quoted, table["primary_key"]))
    )
    rows = [dict(zip(columns, row)) for row in conn.execute(query)]
    if any(
        type(v) not in {str, int, float, type(None)}
        for row in rows
        for v in row.values()
    ):
        raise ValueError("authoring text supports SQLite text, numbers and null only")
    return ("".join(compact(row) + "\n" for row in rows)).encode(), len(rows)


def write_authoring_source(database, destination, *, replace=False):
    """Capture all tables from one WAL-aware SQLite snapshot, then publish them."""
    database, destination = Path(database).resolve(), Path(destination).resolve()
    if database.is_relative_to(destination):
        raise ValueError("candidate database must be outside the text source directory")
    if destination.exists() and (not replace or not destination.is_dir()):
        raise FileExistsError(destination)
    expected_schema, layout = _reference()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".cedarkit-source-", dir=destination.parent
    ) as tmp:
        temporary = Path(tmp)
        snapshot = temporary / "snapshot.db"
        with closing(connect(database, readonly=True)) as reader:
            with closing(sqlite3.connect(snapshot)) as writer:
                reader.backup(writer)
        group = temporary / "source"
        group.mkdir()
        manifest = {
            "format": FORMAT,
            "schema_version": SCHEMA_VERSION,
            "schema_sha256": hashlib.sha256(
                compact(expected_schema).encode()
            ).hexdigest(),
            "tables": [],
        }
        with closing(connect(snapshot, readonly=True)) as conn:
            if _schema(conn) != expected_schema:
                raise ValueError(
                    "authoring schema differs from the packaged schema-4 definition"
                )
            read_resources(conn)
            if tuple(conn.execute("PRAGMA integrity_check").fetchone()) != ("ok",):
                raise ValueError("authoring database failed SQLite integrity check")
            for table in layout:
                data, count = _table_bytes(conn, table)
                (group / (table["name"] + ".jsonl")).write_bytes(data)
                manifest["tables"].append(
                    {**table, "rows": count, "sha256": hashlib.sha256(data).hexdigest()}
                )
        (group / "manifest.json").write_text(json_text(manifest), encoding="utf-8")
        previous = temporary / "previous"
        if destination.exists():
            destination.rename(previous)
        try:
            group.rename(destination)
        except BaseException:
            if previous.exists():
                previous.rename(destination)
            raise
    return destination


def _read_source(source):
    source = Path(source).resolve()
    original = (source / "manifest.json").read_bytes()
    manifest = json.loads(original)
    schema, layout = _reference()
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"format", "schema_version", "schema_sha256", "tables"}
        or manifest["format"] != FORMAT
        or manifest["schema_version"] != SCHEMA_VERSION
        or manifest["schema_sha256"]
        != hashlib.sha256(compact(schema).encode()).hexdigest()
        or not isinstance(manifest["tables"], list)
        or len(manifest["tables"]) != len(layout)
    ):
        raise ValueError("invalid authoring source manifest or schema")
    expected_files = {"manifest.json"} | {t["name"] + ".jsonl" for t in layout}
    if {p.name for p in source.iterdir()} != expected_files:
        raise ValueError(
            "authoring source must contain exactly the declared table files"
        )
    result = []
    for table, declared in zip(layout, manifest["tables"]):
        if (
            not isinstance(declared, dict)
            or set(declared) != set(table) | {"rows", "sha256"}
            or any(declared[k] != v for k, v in table.items())
        ):
            raise ValueError("authoring table layout differs from schema")
        data = (source / (table["name"] + ".jsonl")).read_bytes()
        if hashlib.sha256(data).hexdigest() != declared["sha256"]:
            raise ValueError("authoring table SHA256 mismatch: " + table["name"])
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines()]
        if type(declared["rows"]) is not int or len(rows) != declared["rows"]:
            raise ValueError("authoring row count mismatch: " + table["name"])
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(table["columns"]):
                raise ValueError("authoring row columns differ from schema")
            if any(type(v) not in {str, int, float, type(None)} for v in row.values()):
                raise ValueError("invalid authoring SQLite value")
        if data != "".join(compact(row) + "\n" for row in rows).encode():
            raise ValueError("authoring rows must use canonical JSON lines")
        result.append((table, data, rows))
    if (source / "manifest.json").read_bytes() != original:
        raise ValueError("authoring source changed during reading")
    return result


def build_authoring_database(source, destination):
    """Build an exclusive new database, checking full data, schema and semantics."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.is_relative_to(source):
        raise ValueError("generated database must be outside the text source directory")
    tables = _read_source(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    init_db(destination)
    try:
        with transaction(destination) as conn:
            conn.execute("PRAGMA defer_foreign_keys = ON")
            conn.execute("DELETE FROM schema_meta")
            for table, data, rows in tables:
                columns = table["columns"]
                conn.executemany(
                    "INSERT INTO "
                    + _quoted(table["name"])
                    + " ("
                    + ",".join(map(_quoted, columns))
                    + ") VALUES ("
                    + ",".join("?" for _ in columns)
                    + ")",
                    [tuple(row[c] for c in columns) for row in rows],
                )
                # Reject coercion and noncanonical ordering, retaining exact
                # SQL JSON strings and every other original stored value.
                if _table_bytes(conn, table)[0] != data:
                    raise ValueError(
                        "authoring table does not reconstruct exactly: " + table["name"]
                    )
            if tuple(conn.execute("PRAGMA integrity_check").fetchone()) != ("ok",):
                raise ValueError("rebuilt authoring database failed integrity check")
    except BaseException:
        destination.unlink()
        raise
    return destination
