"""params.json 导出（export-json）与 JSON drift 检查测试。

基准数据：reki 包内的 param_registry.yaml（与 test_roundtrip 同一夹具来源）。
"""

import json
from pathlib import Path

import pytest

from cedarkit_param_db.__main__ import main
from cedarkit_param_db.db import init_db
from cedarkit_param_db.exporter import JSON_SCHEMA_VERSION, export_json
from cedarkit_param_db.importer import import_registry
from cedarkit_param_db.cmadaas import import_vocabulary

#: data/cedarkit-param-db/tests/ → 上三级为 devel 根目录
REGISTRY_YAML = (
    Path(__file__).resolve().parents[3]
    / "repo/reki/reki/readers/grib/config/param_registry.yaml"
)
CMADAAS_VOCABULARY = (
    Path(__file__).resolve().parents[3]
    / "source/nuwe-cmadaas-devel/cmadaas_param_names.md"
)

pytestmark = pytest.mark.skipif(
    not REGISTRY_YAML.exists(), reason="reki param_registry.yaml 不在预期位置"
)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "json_test.db"
    init_db(path)
    import_vocabulary(CMADAAS_VOCABULARY, path)
    import_registry(REGISTRY_YAML, path)
    return path


class TestExportJson:
    def test_structure(self, db_path):
        doc = json.loads(export_json(db_path))
        assert doc["meta"]["schema_version"] == JSON_SCHEMA_VERSION
        stats = doc["meta"]["stats"]
        assert stats["entries"] == len(doc["entries"]) > 0
        assert stats["parameter_ids"] == 221

        entry = next(e for e in doc["entries"] if e["name"] == "t")
        assert entry["key"] == {"discipline": 0, "category": 0, "number": 0}
        assert entry["parameter_id"] == "cedarkit.t"
        assert entry["external_names"] == {"cmadaas": "TEM"}
        assert entry["updated_at"]  # 数据库独有字段必须存在
        variant = next(v for v in entry["variants"] if v["name"] == "t2m")
        assert variant["parameter_id"] == "cedarkit.t2m"
        # when 恢复为 spec 语义顺序
        assert list(variant["when"]) == ["first_level_type", "first_level"]

    def test_no_presentation_fields(self, db_path):
        """契约只含原始数据：不得混入展示层预加工字段。"""
        doc = json.loads(export_json(db_path))
        for entry in doc["entries"]:
            for field in ("triplet", "detail_url", "search_text", "discipline_label"):
                assert field not in entry
            for variant in entry.get("variants", []):
                assert "when_text" not in variant

    def test_deterministic(self, db_path):
        assert export_json(db_path) == export_json(db_path)


class TestCheckJson:
    def test_check_json_ok(self, db_path, tmp_path):
        json_path = tmp_path / "params.json"
        json_path.write_text(export_json(db_path), encoding="utf-8")
        assert main(["--db", str(db_path), "check", "--json", str(json_path)]) == 0

    def test_check_json_drift(self, db_path, tmp_path, capsys):
        json_path = tmp_path / "params.json"
        doc = json.loads(export_json(db_path))
        doc["entries"][0]["name"] = "tampered"
        json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        assert main(["--db", str(db_path), "check", "--json", str(json_path)]) == 1
        assert "DRIFT" in capsys.readouterr().out

    def test_check_requires_target(self, db_path, capsys):
        assert main(["--db", str(db_path), "check"]) == 2
