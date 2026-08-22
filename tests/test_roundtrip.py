"""roundtrip 与数据库约束测试。

基准数据：reki 包内的 param_registry.yaml（当前唯一真源快照）。
"""

import sqlite3
from pathlib import Path

import pytest
import yaml

from cedarkit_param_db.db import init_db
from cedarkit_param_db.exporter import HEADER, export_entries, export_text
from cedarkit_param_db.importer import canonicalize_when, import_registry

#: data/cedarkit-param-db/tests/ → 上三级为 devel 根目录
REGISTRY_YAML = (
    Path(__file__).resolve().parents[3]
    / "repo/reki/reki/readers/grib/config/param_registry.yaml"
)

pytestmark = pytest.mark.skipif(
    not REGISTRY_YAML.exists(), reason="reki param_registry.yaml 不在预期位置"
)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    init_db(path)
    import_registry(REGISTRY_YAML, path)
    return path


@pytest.fixture(scope="module")
def source_entries():
    with open(REGISTRY_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestRoundtrip:
    def test_entries_data_equal(self, db_path, source_entries):
        """导出结果与源 YAML 的 safe_load 结构完全一致。"""
        assert export_entries(db_path) == source_entries

    def test_byte_identical_after_header(self, db_path):
        """除头部注释外，导出文本与源文件逐字节一致。"""
        source_lines = REGISTRY_YAML.read_text(encoding="utf-8").splitlines(keepends=True)
        source_body = "".join(line for line in source_lines if not line.startswith("#"))
        exported = export_text(db_path)
        assert exported == HEADER + source_body

    def test_reimport_idempotent(self, db_path, tmp_path):
        """导出结果再次导入后导出，文本不变（幂等）。"""
        first = export_text(db_path)
        yaml_path = tmp_path / "roundtrip.yaml"
        yaml_path.write_text(first, encoding="utf-8")
        db2 = tmp_path / "second.db"
        init_db(db2)
        import_registry(yaml_path, db2)
        assert export_text(db2) == first


class TestCanonicalizeWhen:
    def test_key_order_normalized(self):
        a = canonicalize_when({"first_level": 2, "first_level_type": 103})
        b = canonicalize_when({"first_level_type": 103, "first_level": 2})
        assert a == b

    def test_types_preserved(self):
        when = {"first_level_type": 106, "first_level": 0, "second_level": 0.1,
                "stepType": "max", "time_range_hours": 3}
        import json
        assert json.loads(canonicalize_when(when)) == when

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            canonicalize_when({})


class TestConstraints:
    """schema 硬约束：U1 / U2 / C4 / E1。"""

    def test_U1_duplicate_triple_rejected(self, db_path):
        from cedarkit_param_db.db import connect
        conn = connect(db_path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO entries (discipline, category, number, name) "
                    "VALUES (0, 0, 0, 'dup')"
                )
        finally:
            conn.close()

    def test_U2_duplicate_variant_name_rejected(self, db_path):
        from cedarkit_param_db.db import connect
        conn = connect(db_path)
        try:
            entry_id = conn.execute(
                "SELECT id FROM entries WHERE discipline = 0 AND category = 0 AND number = 0"
            ).fetchone()["id"]
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO variants (entry_id, name, when_json, sort_order) "
                    "VALUES (?, 't2m', '{\"first_level_type\":1}', 999)",
                    (entry_id,),
                )
        finally:
            conn.close()

    def test_C4_duplicate_when_rejected(self, db_path):
        from cedarkit_param_db.db import connect
        conn = connect(db_path)
        try:
            entry_id = conn.execute(
                "SELECT id FROM entries WHERE discipline = 0 AND category = 0 AND number = 0"
            ).fetchone()["id"]
            when_json = conn.execute(
                "SELECT when_json FROM variants WHERE entry_id = ? AND name = 't2m'",
                (entry_id,),
            ).fetchone()["when_json"]
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO variants (entry_id, name, when_json, sort_order) "
                    "VALUES (?, 'another_name', ?, 999)",
                    (entry_id, when_json),
                )
        finally:
            conn.close()

    def test_E1_empty_name_rejected(self, db_path):
        from cedarkit_param_db.db import connect
        conn = connect(db_path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO entries (discipline, category, number, name) "
                    "VALUES (1, 1, 1, '  ')"
                )
        finally:
            conn.close()

    def test_V2_empty_when_rejected(self, db_path):
        from cedarkit_param_db.db import connect
        conn = connect(db_path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO variants (entry_id, name, when_json, sort_order) "
                    "VALUES (1, 'x', '{}', 0)"
                )
        finally:
            conn.close()
