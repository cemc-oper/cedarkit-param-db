"""roundtrip 与数据库约束测试。

基准数据：reki 包内的 param_registry.yaml（当前唯一真源快照）。
"""

import sqlite3
from pathlib import Path

import pytest
import yaml

from cedarkit_param_db.db import init_db
from cedarkit_param_db.exporter import HEADER, PARAMETER_REGISTRY_API_VERSION, export_document, export_entries, export_text
from cedarkit_param_db.importer import canonicalize_when, import_registry
from cedarkit_param_db.cmadaas import import_vocabulary, inventory

#: data/cedarkit-param-db/tests/ → 上三级为 devel 根目录
REGISTRY_YAML = (
    Path(__file__).resolve().parents[3]
    / "repo/reki/reki/readers/grib/config/param_registry.yaml"
)
CMADAAS_VOCABULARY = (
    Path(__file__).resolve().parents[3]
    / "source/nuwe-cmadaas-devel/cmadaas_param_names.md"
)


CMADAAS_MAPPINGS = {
    "cedarkit.albedo.any": "ALBO", "cedarkit.cape.any": "CAPE",
    "cedarkit.cc": "CLCO", "cedarkit.cdbz": "RACR", "cedarkit.cin.any": "CIN",
    "cedarkit.dbz": "RAR", "cedarkit.dcape": "DCAPE", "cedarkit.graupel": "GRSP",
    "cedarkit.gust": "WSGU", "cedarkit.h.any": "GPH", "cedarkit.hcc": "HCC",
    "cedarkit.hi.any": "HIDX", "cedarkit.ht0.any": "HT0", "cedarkit.kidx.any": "KIDX",
    "cedarkit.lcc": "LCC", "cedarkit.mcc": "MCC", "cedarkit.pblh.any": "PBLH",
    "cedarkit.pc.any": "PC", "cedarkit.pli.any": "PLI", "cedarkit.psl.any": "SSP",
    "cedarkit.q": "SHU", "cedarkit.qc": "CMRA", "cedarkit.qdiv": "MFVO",
    "cedarkit.qflx": "MOFU", "cedarkit.qi": "IWMR", "cedarkit.qr": "RMRA",
    "cedarkit.qs": "SMRA", "cedarkit.rain.any": "PRE", "cedarkit.rainc.any": "CPE",
    "cedarkit.rainnc.any": "LPE", "cedarkit.rh": "RHU", "cedarkit.rhmax": "RHMAX",
    "cedarkit.rhmin": "RHMIN", "cedarkit.sd.any": "SDE", "cedarkit.sf.any": "TOSN",
    "cedarkit.si.any": "SHID", "cedarkit.sweatidx.any": "SWID", "cedarkit.t": "TEM",
    "cedarkit.tadv": "TEAD", "cedarkit.tcc": "TCC", "cedarkit.tcw.any": "TCCW",
    "cedarkit.td": "DPT", "cedarkit.theta-se": "PPT", "cedarkit.tiw.any": "TCCI",
    "cedarkit.ttd": "DPD", "cedarkit.tvw.any": "TIWV", "cedarkit.u": "WIU",
    "cedarkit.v": "WIV", "cedarkit.vis.any": "VIS", "cedarkit.voradv": "VOAD",
    "cedarkit.w.any": "VVM", "cedarkit.wi.any": "WIDX", "cedarkit.znt.any": "ZNT",
}

CEMC_EXTERNAL_ELEMENTS = {
    "ALBO": "地表反照率", "CAPE": "对流有效位能", "CIN": "对流抑制能",
    "CLCO": "云量", "CMRA": "云水混合比", "DCAPE": "下沉有效位能",
    "GRSP": "霰", "HIDX": "冰雹指数", "HT0": "0℃层高度",
    "IWMR": "冰水混合比", "PC": "抬升凝结高度", "PBLH": "边界层高度", "RACR": "雷达组合反射率",
    "RAR": "雷达反射率", "RHMAX": "最大相对湿度", "RHMIN": "最小相对湿度",
    "RMRA": "雨水混合比", "SHID": "沙氏指数", "SMRA": "雪水混合比",
    "SWID": "强天气胁迫指数", "TCCI": "总柱状云冰", "TCCW": "总柱状云水",
    "TIWV": "总柱状比湿（整层水汽含量）", "TOSN": "降雪量", "WIDX": "大风指数",
    "WSGU": "阵风风速", "ZNT": "粗糙度",
}


def import_cemc_m06_elements(path):
    """Add the CEMC-only vocabulary rows required by the published v3 snapshot."""
    from cedarkit_param_db.db import connect
    conn = connect(path)
    try:
        with conn:
            conn.executemany(
                "INSERT INTO external_elements(namespace, code, description_cn, source_ref) VALUES (?, ?, ?, ?)",
                [("cmadaas", code, description, "doc/ref/cmadaas-cemc-data.md")
                 for code, description in CEMC_EXTERNAL_ELEMENTS.items()],
            )
    finally:
        conn.close()

pytestmark = pytest.mark.skipif(
    not REGISTRY_YAML.exists(), reason="reki param_registry.yaml 不在预期位置"
)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    init_db(path)
    import_vocabulary(CMADAAS_VOCABULARY, path)
    import_cemc_m06_elements(path)
    import_registry(REGISTRY_YAML, path)
    return path


@pytest.fixture(scope="module")
def source_entries():
    with open(REGISTRY_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestRoundtrip:
    def test_entries_data_equal(self, db_path, source_entries):
        """导出结果与源 YAML 的 safe_load 结构完全一致。"""
        assert source_entries["api_version"] == PARAMETER_REGISTRY_API_VERSION
        assert export_document(db_path) == source_entries

    def test_all_ids_are_non_empty_and_unique(self, db_path):
        entries = export_entries(db_path)
        ids = [entry["parameter_id"] for entry in entries]
        ids.extend(variant["parameter_id"] for entry in entries for variant in entry.get("params", []))
        assert len(ids) == len(set(ids)) == 221
        assert all(value.startswith("cedarkit.") for value in ids)

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
        import_vocabulary(CMADAAS_VOCABULARY, db2)
        import_cemc_m06_elements(db2)
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


class TestCmadaasExternalElements:
    def test_import_is_complete_idempotent_and_unmapped_is_visible(self, db_path):
        assert import_vocabulary(CMADAAS_VOCABULARY, db_path) == 146
        first = inventory(db_path)
        assert len(first["elements"]) == 173
        assert len({item["code"] for item in first["elements"]}) == 173
        mapped = {item["code"] for item in first["elements"] if item["status"] == "mapped"}
        assert mapped == set(CMADAAS_MAPPINGS.values())
        assert import_vocabulary(CMADAAS_VOCABULARY, db_path) == 146
        assert inventory(db_path) == first

    def test_mapping_requires_a_real_entry_and_cascades(self, db_path):
        from cedarkit_param_db.db import connect
        import_vocabulary(CMADAAS_VOCABULARY, db_path)
        conn = connect(db_path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO entry_external_elements(entry_id, namespace, code) VALUES (999999, 'cmadaas', 'AVO')")
            entry_id = conn.execute("SELECT id FROM entries WHERE parameter_id = 'cedarkit.apd'").fetchone()["id"]
            conn.execute("INSERT INTO entry_external_elements(entry_id, namespace, code) VALUES (?, 'cmadaas', 'AVO')", (entry_id,))
            conn.commit()
            assert inventory(db_path)["elements"][next(i for i, item in enumerate(inventory(db_path)["elements"]) if item["code"] == "AVO")]["parameter_id"] == "cedarkit.apd"
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO entry_external_elements(entry_id, namespace, code) VALUES (?, 'cmadaas', 'AVO')", (entry_id,))
        finally:
            conn.close()
