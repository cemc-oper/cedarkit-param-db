from copy import deepcopy
import json

import pytest

from cedarkit_param_db import init_db, import_resources


@pytest.fixture
def parameters():
    return {
        "api_version": "cedarkit.parameters/v1",
        "id": "example.parameters",
        "version": "1",
        "parameters": [
            {
                "parameter_id": "example.t2m",
                "name": "t2m",
                "parent": "example.t",
                "aliases": ["temperature2"],
                "fixed_conditions": {"level_type": "height_above_ground", "level": 2},
            },
            {
                "parameter_id": "example.t",
                "name": "t",
                "unit": "K",
                "description": "Temperature",
                "aliases": ["temperature"],
            },
        ],
    }


@pytest.fixture
def mappings():
    scope = {"dataset": "example", "product": "orig", "product_version": "v1"}
    grib = {
        "api_version": "cedarkit.mappings/v1",
        "id": "example.grib2",
        "version": "1",
        "backend": "grib2",
        "tables": [],
        "mappings": [
            {
                "id": "t",
                "parameter_id": "example.t",
                "backend": "grib2",
                "applies_to": deepcopy(scope),
                "when": {},
                "native": {
                    "match": {
                        "discipline": 0,
                        "parameterCategory": 0,
                        "parameterNumber": 0,
                    },
                    "translate": {
                        "vertical": {"rule": "grib.fixed_surfaces"},
                        "time": {"rule": "grib.time"},
                        "member": {"rule": "grib.member"},
                        "statistics": {"rule": "grib.statistics"},
                        "unit": {
                            "rule": "common.value_unit",
                            "config": {"source_unit": "K"},
                        },
                    },
                },
                "evidence": ["fixture:definition", "fixture:native"],
            }
        ],
    }
    cmadaas = {
        "api_version": "cedarkit.mappings/v1",
        "id": "example.cmadaas",
        "version": "2",
        "backend": "cmadaas",
        "tables": [
            {
                "id": "levels",
                "key_kind": "level_type_and_level",
                "applies_to": deepcopy(scope),
                "evidence": ["fixture:joint-level"],
                "rows": [
                    {
                        "id": "height2",
                        "native": {"level_type": "103", "level": "2"},
                        "canonical": {
                            "level_type": "height_above_ground",
                            "level": 2,
                            "level_unit": "m",
                        },
                        "evidence": ["fixture:row"],
                    }
                ],
            },
            {
                "id": "members",
                "key_kind": "code",
                "applies_to": deepcopy(scope),
                "evidence": [],
                "rows": [
                    {
                        "id": "control",
                        "native": {"code": "00"},
                        "canonical": {"member": 0},
                    }
                ],
            },
        ],
        "mappings": [
            {
                "id": "t2m",
                "parameter_id": "example.t2m",
                "backend": "cmadaas",
                "applies_to": deepcopy(scope),
                "when": {},
                "native": {
                    "match": {"element": "TEM"},
                    "translate": {
                        "vertical": {
                            "rule": "cmadaas.vertical_table",
                            "config": {"table": "levels"},
                        },
                        "time": {"rule": "cmadaas.time_fields"},
                        "member": {
                            "rule": "cmadaas.member_field",
                            "config": {"table": "members"},
                        },
                        "statistics": {"rule": "cmadaas.statistics_fields"},
                        "unit": {
                            "rule": "common.value_unit",
                            "config": {"source_unit": "K"},
                        },
                    },
                },
                "evidence": ["fixture:binding"],
            }
        ],
    }
    return [grib, cmadaas]


@pytest.fixture
def db(tmp_path, parameters, mappings):
    p = tmp_path / "authoring.db"
    init_db(p)
    import_resources(p, parameters, mappings)
    return p


@pytest.fixture
def legacy(tmp_path):
    p = tmp_path / "legacy.json"
    p.write_text(
        json.dumps(
            {
                "api_version": "reki.parameter-registry/v3",
                "entries": [
                    {
                        "parameter_id": "example.t",
                        "name": "t",
                        "unit": "K",
                        "description": "Temperature ",
                        "key": {"discipline": 0, "category": 0, "number": 0},
                        "aliases": ["temperature"],
                        "external_names": {"cmadaas": "TEM"},
                        "typeOfLevel": "surface",
                        "params": [
                            {
                                "parameter_id": "example.t2m",
                                "name": "t2m",
                                "aliases": ["temperature2"],
                                "when": {"first_level_type": 103, "first_level": 2},
                                "typeOfLevel": "heightAboveGround",
                                "level": 2,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return p
