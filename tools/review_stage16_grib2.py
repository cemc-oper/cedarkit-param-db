"""Compile the independent GRIB2 rules from pinned ORIG headers and receipts."""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import gzip
from hashlib import file_digest, sha256
import json
from pathlib import Path

from cedarkit_query import SourceError
from cedarkit_query.normalize import duration_seconds
from cedarkit_query.resources import effective_parameters
from reki.selection.core import matches
from reki.translation import grib
from reki.translation.grib_backend import native_matches
from reki.translation.grib_mapping import _conversion, _observed_units

from export_browser_snapshot import AUTHOR, encode
from export_cemc_orig_snapshot import write_snapshot
from export_stage16_grib2 import BASELINE, IDENTITIES, POLICY, RULES

WORKSPACE = AUTHOR.parents[2]
TRIPLE = ("discipline", "parameterCategory", "parameterNumber")
SURFACES = ("typeOfFirstFixedSurface", "typeOfSecondFixedSurface")
SCALES = (
    "scaleFactorOfFirstFixedSurface", "scaledValueOfFirstFixedSurface",
    "scaleFactorOfSecondFixedSurface", "scaledValueOfSecondFixedSurface",
)
CORE = (
    "edition", "centre", "subCentre", "tablesVersion", "localTablesVersion",
    *TRIPLE, "productDefinitionTemplateNumber", *SURFACES,
    "productionStatusOfProcessedData", "generatingProcessIdentifier",
)
INTERVAL = (
    "numberOfTimeRange", "typeOfStatisticalProcessing", "typeOfTimeIncrement",
    "indicatorOfUnitOfTimeRange", "indicatorOfUnitForTimeRange",
)
ENSEMBLE = ("numberOfForecastsInEnsemble", "typeOfEnsembleForecast", "typeOfGeneratingProcess", "typeOfProcessedData")
WIND = {
    "cedarkit.u", "cedarkit.v", "cedarkit.u10m", "cedarkit.v10m",
    "cedarkit.u10mmax-1", "cedarkit.v10mmax-1",
}
SINCE_START_HEADER = {
    "cedarkit.mx2t", "cedarkit.mn2t", "cedarkit.rhmax2m", "cedarkit.rhmin2m",
    "cedarkit.uhmax", "cedarkit.sf.with-convective-diagnostic",
}
PAGE_CARRIERS = {f"gfs-{number:03d}" for number in range(22, 46)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def json_lines(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        yield from map(json.loads, stream)


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def triple(native):
    return tuple(native[key] for key in TRIPLE)


def unit_rule(unit):
    return {"rule": "common.value_unit", "config": {"source_unit": unit}}


def pilot_mapping(row):
    return {
        "id": row["id"], "backend": "grib2", "parameter_id": row["parameter_id"],
        "applies_to": {}, "when": row["when"], "evidence": row["evidence"],
        "native": {"match": row["match"], "translate": {
            "vertical": {"rule": "grib.fixed_surfaces"}, "time": {"rule": "grib.time"},
            "unit": unit_rule(row["source_unit"]),
        }},
    }


@dataclass
class Profile:
    parameter: str
    match: dict
    when: dict
    first_message: dict
    carriers: Counter = field(default_factory=Counter)
    read_units: Counter = field(default_factory=Counter)
    decoder_units: set = field(default_factory=set)
    members: set = field(default_factory=set)


def make_match(header, carrier, pid, definition):
    result = {key: header[key] for key in CORE}
    template = header["productDefinitionTemplateNumber"]
    if not carrier["group_excludes_fixed_surface_values"]:
        result.update({key: header[key] for key in SCALES if header[key] is not None})
    if pid in WIND:
        result["uvRelativeToGrid"] = header["uvRelativeToGrid"]
    if template in (1, 11):
        result.update({key: header[key] for key in ENSEMBLE})
    if template in (8, 11):
        result.update({key: header[key] for key in INTERVAL})
        period = definition["fixed_conditions"].get("statistics", {}).get("period", {})
        if period.get("kind") == "since_initialization" or pid in SINCE_START_HEADER:
            result["forecastTime"] = header["forecastTime"]
        if period.get("kind") == "trailing" or pid == "cedarkit.rain5max":
            result["lengthOfTimeRange"] = header["lengthOfTimeRange"]
    return result


def choose_unit(profile, definition):
    """Carry a scoped value rule only where all corresponding receipts support it."""
    if len(profile.read_units) != 1 or None in profile.read_units:
        return None
    unit, = profile.read_units
    template = profile.match["productDefinitionTemplateNumber"]
    statistics = definition["fixed_conditions"].get("statistics", {})
    if template in (8, 11):
        period = statistics.get("period", {})
        if grib.TIME_OPERATIONS.get(statistics.get("operation")) != profile.match["typeOfStatisticalProcessing"]:
            return None
        if period.get("kind") == "since_initialization":
            if profile.match["forecastTime"] != 0:
                return None
        elif period.get("kind") == "trailing":
            length = profile.match["lengthOfTimeRange"]
            if length * grib.UNITS[profile.match["indicatorOfUnitForTimeRange"]] != duration_seconds(period["duration"]):
                return None
        else:
            return None
    elif statistics.get("operation", "instantaneous") != "instantaneous":
        return None
    for units, table_units in profile.decoder_units:
        header = {"units": units, "parameterUnits": table_units, "parameterNumber": profile.match["parameterNumber"]}
        observed = _observed_units(header, {}, profile.parameter, unit)
        if len(observed | _observed_units({"units": unit}, {}, profile.parameter, unit)) > 1:
            return None
    try:
        _conversion(unit, definition["unit"], pid=profile.parameter)
    except SourceError:
        return None
    return unit


def add_profile(profiles, header, carrier, pid, definition, when, position, source_unit):
    match = make_match(header, carrier, pid, definition)
    key = (pid, packed(match), packed(when))
    if key not in profiles:
        profiles[key] = Profile(pid, match, when, position)
    profile = profiles[key]
    profile.carriers[position["carrier_id"]] += 1
    profile.read_units[source_unit] += 1
    profile.decoder_units.add((header["units"], header["parameterUnits"]))
    if header.get("perturbationNumber") is not None:
        profile.members.add(header["perturbationNumber"])


def profile_rule(profile, definition, policy):
    match = dict(profile.match)
    translation = {"time": {"rule": "grib.time"}}
    if profile.parameter not in policy["raw_vertical"]:
        translation["vertical"] = {"rule": "grib.fixed_surfaces"}
    if profile.members:
        match["perturbationNumber"] = sorted(profile.members)
        translation["member"] = {"rule": "grib.member"}
    unit = choose_unit(profile, definition)
    if unit is not None:
        translation["unit"] = unit_rule(unit)
        if match["productDefinitionTemplateNumber"] in (8, 11):
            translation["statistics"] = {"rule": "grib.statistics"}
    code = sha256(packed([profile.parameter, match, profile.when]).encode()).hexdigest()[:12]
    evidence = [
        f"{policy['evidence']['orig_carriers']}#{carrier_id}" for carrier_id in sorted(profile.carriers)
    ] + [policy["evidence"]["product_reads"]]
    if profile.carriers.keys() & policy["soil_carrier_targets"].keys():
        evidence.append(policy["evidence"]["soil"])
    rule = {
        "id": f"cemc.{profile.parameter.removeprefix('cedarkit.')}.{code}",
        "parameter_id": profile.parameter, "backend": "grib2", "applies_to": {}, "when": profile.when,
        "native": {"match": match, "translate": translation},
        "evidence": evidence,
    }
    return {
        "batch": "gfs-22-45" if profile.carriers.keys() & PAGE_CARRIERS else "full-library",
        "mapping": rule, "carrier_ids": sorted(profile.carriers), "frozen_messages": sum(profile.carriers.values()),
        "representative": profile.first_message,
        "decoder_units": [list(pair) for pair in sorted(profile.decoder_units, key=repr)],
    }


def archive_rows(paths):
    headers = json_lines(paths["original_headers"])
    positions = json_lines(paths["carrier_positions"])
    receipts = json_lines(paths["product_reads"])
    for row, position, receipt in zip(headers, positions, receipts, strict=True):
        file_id, ordinal, offset, length, header_sha, carrier_id, raw_sha, *_ = position
        # Named ORIG v52 receipt columns are documented in the frozen 1.4-08 summary.
        _, _, _, _, _, _, parameter, read_sha, _, _, _, _, _, _, source_unit, *_ = receipt
        require(
            (row["file_id"], row["ordinal"], row["offset"], row["length"], row["header_sha256"])
            == (file_id, ordinal, offset, length, header_sha)
            and receipt[:5] == [file_id, ordinal, offset, length, carrier_id] and read_sha == raw_sha,
            f"header and raw read disagree at {file_id}/{ordinal}",
        )
        yield row["native_header"], {
            "file_id": file_id, "ordinal": ordinal, "carrier_id": carrier_id,
            "offset": offset, "length": length, "raw_sha256": raw_sha, "header_sha256": header_sha,
        }, parameter, source_unit


def index_by_triple(rules):
    index = defaultdict(list)
    for row in rules:
        index[triple(row["native"]["match"])].append(row)
    return index


def collect_rules(paths, policy, registry, baseline, definitions, blocked):
    carriers = read(paths["carriers"])["carriers"]
    files = {row["file_id"]: row for row in read(paths["files"])["files"]}
    targets = {cid: row["unified_parameter_id"] for row in registry["source_entries"] for cid in row["carrier_ids"]}
    targets.update(policy["soil_carrier_targets"])
    seeds = [pilot_mapping(row) for row in policy["pilot"]]
    initial = index_by_triple(baseline + seeds)
    profiles, measured = {}, defaultdict(Counter)
    representatives = {row["id"]: [] for row in seeds}
    # Fixed-surface normalization depends only on these encoded keys.
    verticals = {}
    for native, position, original_id, source_unit in archive_rows(paths):
        cid = position["carrier_id"]
        pid = targets[cid]
        require(original_id == carriers[cid]["parameter_id"], f"{cid} changes identity within the v52 source")
        native["uvRelativeToGrid"] = policy["grid_wind_axes"][native["md5GridSection"]]
        if native["productDefinitionTemplateNumber"] in (1, 11):
            kind = native["typeOfEnsembleForecast"]
            number = native["perturbationNumber"]
            require(
                kind in (0, 2, 3) and (kind == 0) == (number == 0)
                and number == files[position["file_id"]]["file_member"],
                f"{cid} has an unreviewed member encoding at {position['ordinal']}",
            )
        if cid in blocked:
            measured[cid]["ambiguous_header"] += 1
            continue
        shape = tuple(native[k] for k in SURFACES + SCALES)
        if shape not in verticals and pid not in policy["raw_vertical"]:
            verticals[shape] = grib.fixed_surfaces(native)
        vertical = {} if pid in policy["raw_vertical"] else verticals[shape]
        wmo_rules = initial.get(triple(native), ())
        same_codes = [row for row in wmo_rules if native_matches(native, row["native"]["match"])]
        direct = [row for row in same_codes if matches(vertical, row["when"])]
        if direct:
            require(len(direct) == 1 and direct[0]["parameter_id"] == pid, f"{cid} conflicts with a baseline mapping")
            mid = direct[0]["id"]
            measured[cid][mid] += 1
            if mid in representatives and not representatives[mid]:
                representatives[mid].append(position)
        else:
            # The same code may already describe a WMO field at a different height.
            when = vertical if same_codes else {}
            add_profile(profiles, native, carriers[cid], pid, definitions[pid], when, position, source_unit)

    reviews = [
        {"batch": "q2m-znt", "mapping": row,
         "carrier_ids": sorted(cid for cid, hits in measured.items() if hits[row["id"]]),
         "frozen_messages": sum(hits[row["id"]] for hits in measured.values()),
         "representative": positions[0]}
        for row in seeds if (positions := representatives[row["id"]])
    ]
    require(len(reviews) == len(seeds), "each pilot mapping needs a frozen original")
    for _, profile in sorted(profiles.items()):
        review = profile_rule(profile, definitions[profile.parameter], policy)
        reviews.append(review)
        for cid, count in profile.carriers.items():
            measured[cid][review["mapping"]["id"]] += count
    require(set(measured) == set(carriers), "carrier accounting does not cover the archive")
    for cid, hits in measured.items():
        require(sum(hits.values()) == carriers[cid]["v52_messages"], f"{cid} frozen coverage denominator changed")
    return reviews


def build_review(author=AUTHOR):
    policy = read(author / POLICY)
    require(policy["schema_version"] == 1 and policy["task"] == "1.6-08", "expected the stage 1.6-08 review policy")
    paths = {key: WORKSPACE / value["path"] for key, value in policy["sources"].items()}
    for key, path in paths.items():
        require(digest(path) == policy["sources"][key]["sha256"], f"{key} differs from its reviewed input")
    registry = read(author / IDENTITIES)
    inputs = read(paths["identity_review"])
    require(digest(author / IDENTITIES) == inputs["files_sha256"][IDENTITIES], "identity registry differs from 1.6-07")
    baseline = read(author / BASELINE)["generic_grib2_mappings"]
    definitions = effective_parameters({
        "api_version": "cedarkit.parameters/v1", "id": "cedarkit.parameters.public",
        "version": "2", "parameters": registry["unified_parameters"],
    })
    blocked = {
        cid: case for case in policy["unresolved_header_cases"] for cid in inputs["shared_header_cases"][case]["carriers"]
    }
    reviews = collect_rules(paths, policy, registry, baseline, definitions, blocked)
    group = {
        "schema_version": 1, "task": "1.6-08",
        "authoring_sha256": {name: digest(author / name) for name in (POLICY, IDENTITIES, BASELINE)},
        "rules": reviews,
    }
    return {RULES: encode(group)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_snapshot(build_review(), args.output)


if __name__ == "__main__":
    main()
