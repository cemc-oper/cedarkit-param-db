"""Check normalization of the pinned wgrib2 source tables."""

from hashlib import sha256
import json
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture
def exporter(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    import export_wgrib2_names

    return export_wgrib2_names


def test_export_preserves_order_and_uppercases_reachable_names(exporter, tmp_path):
    ncep = (
        '/* {0,1,0,255,0,0,0,0, "unused", "Commented out", "K"}, */\n'
        '{0,1,0,255,0,0,0,0, "TMP", "Temperature", "K"},\n'
        '{0,0,0,255,7,1,1,225, "frzr", "Freezing rain", "kg/m^2"},\n'
    )
    tigge = '{0,-1,0,255,-1,-1,0,0, "t", "Temperature", "K"},\n'
    contents = {"ncep.dat": ncep, "tigge.dat": tigge}
    for file, content in contents.items():
        (tmp_path / file).write_text(content, encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps({
            "version": "1",
            "upstream": {
                "tag": "test",
                "sha256": {file: sha256(text.encode()).hexdigest() for file, text in contents.items()},
            },
            "tables": {
                "ncep": ["ncep.dat"],
                "tigge": ["tigge.dat"],
                "ecmwf_local": [],
                "dwd_local": [],
                "local": [],
            },
        }),
        encoding="utf-8",
    )

    snapshot = json.loads(exporter.encode_snapshot(exporter.build_snapshot(tmp_path, policy)))
    assert snapshot["short_name_case"] == "upper"
    assert snapshot["tables"]["ncep"] == [
        [0, 0, 0, 0, 255, 0, 0, "TMP"],
        [0, 1, 225, 0, 255, 7, 1, "FRZR"],
    ]
    assert snapshot["tables"]["tigge"] == []

    (tmp_path / "ncep.dat").write_text(ncep + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differs from pinned wgrib2"):
        exporter.build_snapshot(tmp_path, policy)


def test_unrecognized_source_row_reports_its_location(exporter):
    with pytest.raises(ValueError, match="table.dat:2: invalid GRIB table row"):
        list(exporter.read_rows("// comment\n{0,1,0,255,0,0,0,0, without_quotes},", "table.dat"))
