"""数据库连接与初始化。"""

import sqlite3
from importlib.resources import files
from pathlib import Path

#: 项目根目录（src/cedarkit_param_db/db.py → 上三级）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: 默认数据库文件位置（项目根目录下，可直接纳入版本管理）
DEFAULT_DB_PATH = PROJECT_ROOT / "cedarkit_param.db"
SCHEMA_VERSION = 3


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """打开数据库连接，启用外键约束，行返回 dict 风格。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    """按 schema.sql 建库（幂等：已存在的表会报错，请先删除旧库或换路径）。"""
    schema = files("cedarkit_param_db").joinpath("schema.sql").read_text(encoding="utf-8")
    db_path = Path(db_path)
    conn = connect(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
    return db_path


def schema_version(db_path: Path | str = DEFAULT_DB_PATH) -> int:
    """Return the database schema version, rejecting incomplete migrations."""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
        if row is None:
            raise ValueError("database has no schema version; run the stage-2 migration")
        version = int(row["value"])
        if version != SCHEMA_VERSION:
            raise ValueError(f"unsupported database schema version: {version}")
        for table in ("entries", "variants"):
            missing = conn.execute(f"SELECT count(*) AS count FROM {table} WHERE parameter_id IS NULL OR parameter_id = ''").fetchone()["count"]
            if missing:
                raise ValueError(f"database migration incomplete: {table} has {missing} missing parameter_id values")
        for table in ("external_elements", "entry_external_elements"):
            row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
            if row is None:
                raise ValueError(f"database migration incomplete: missing {table}")
        return version
    finally:
        conn.close()
