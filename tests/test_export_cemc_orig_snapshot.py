"""The standalone export must preserve the sealed ORIG publication."""

from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

DB = Path(__file__).resolve().parents[1]
V57 = (
    DB.parents[1] / "doc/2026-11-14-stage1.5-query-reki/evidence/1.5-04D/supplement"
    / "artifacts/reki-2026.9.1.dev122+g1a95894.orig57-py3-none-any.whl"
)


@pytest.fixture
def exporter(monkeypatch):
    import cedarkit_query

    if not hasattr(cedarkit_query, "validate_standalone_grib2"):
        pytest.skip("the Stage 1.6 export requires cedarkit-query 0.2.3")
    monkeypatch.syspath_prepend(str(DB / "tools"))
    import export_cemc_orig_snapshot

    return export_cemc_orig_snapshot


def test_snapshot_preserves_product_bytes_and_pins_standalone_pair(exporter, tmp_path):
    catalog = tmp_path / "catalog-v1.json"
    with ZipFile(V57) as sealed:
        catalog.write_bytes(sealed.read("reki/catalog/builtin/catalog-v1.json"))
        files = exporter.build_snapshot(catalog)
        manifest = json.loads(files["manifest.json"])
        assert len(manifest["products"]) == 6
        assert files[catalog.name] == catalog.read_bytes()
        for product in manifest["products"].values():
            for pin in (product["parameter_registry"], product["mappings"]["grib2"]):
                assert files[pin["path"]] == sealed.read(f"reki/catalog/builtin/{pin['path']}")

    standalone = manifest["standalone"]
    for pin, rows, count in (
        (standalone["parameter_registry"], "parameters", 127),
        (standalone["mappings"]["grib2"], "mappings", 8),
    ):
        raw = files[pin["path"]]
        resource = json.loads(raw)
        assert all(pin[key] == resource[key] for key in ("api_version", "id", "version"))
        assert sha256(raw).hexdigest() == pin["sha256"]
        assert len(resource[rows]) == count
    output = tmp_path / "snapshot"
    exporter.write_snapshot(files, output)
    assert {path.name: path.read_bytes() for path in output.iterdir()} == files
    with pytest.raises(FileExistsError):
        exporter.write_snapshot(files, output)


def test_failed_staging_leaves_no_snapshot(exporter, tmp_path, monkeypatch):
    write_bytes = Path.write_bytes

    def fail_second_file(path, raw):
        if path.name == "broken.json":
            raise OSError("staging failed")
        return write_bytes(path, raw)

    monkeypatch.setattr(Path, "write_bytes", fail_second_file)
    with pytest.raises(OSError, match="staging failed"):
        exporter.write_snapshot({"first.json": b"{}", "broken.json": b"{}"}, tmp_path / "snapshot")
    assert list(tmp_path.iterdir()) == []
