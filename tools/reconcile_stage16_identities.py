"""Register identities from the seven published v57 parameter resources."""

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
from importlib.metadata import version
from io import StringIO
import json
from pathlib import Path

from cedarkit_query import QueryError, prepare_queries, validate_standalone_grib2
from cedarkit_query.resources import effective_parameters

from cemc_orig_registry import product_parameter_definitions
from export_browser_snapshot import AUTHOR, build_bundle, encode
from export_cemc_orig_snapshot import write_snapshot

WORKSPACE = AUTHOR.parents[2]
EVIDENCE = WORKSPACE / "doc/2026-11-16-stage1.6-query-reki/evidence"
SERVICE_EVIDENCE = "doc/2026-11-04-stage1.2-query-reki/evidence"
ORIG_REGISTRY = "cemc-orig-stage1.6-registry.json"
CARRIERS = "cemc-orig-stage1.6-carriers.json"
DECISIONS = "stage1.6-identity-decisions.json"
REGISTRY = "stage1.6-identity-registry.json"
SOURCE_INDEX = "source-index.tsv"
BRANCH_INDEX = "branch-index.tsv"
INSTANTANEOUS = {"over": "time", "operation": "instantaneous"}


def load_sources(catalog, author):
    policy_path = author / "browser-current.json"
    policy = json.loads(policy_path.read_bytes())
    sealed = json.loads((EVIDENCE / "1.6-03/verification.json").read_bytes())
    if policy["version"] != "17" or policy["catalog"] != sealed["v57_catalog"]:
        raise ValueError("expected browser revision 17 and its frozen v57 catalog")
    for filename in (ORIG_REGISTRY, CARRIERS):
        if sha256((author / filename).read_bytes()).hexdigest() != sealed["author_files_sha256"][filename]:
            raise ValueError(f"{filename} differs from the reviewed 1.6-03 input")
    orig = json.loads((author / ORIG_REGISTRY).read_bytes())
    carriers = json.loads((author / CARRIERS).read_bytes())["carriers"]
    files = build_bundle(author=author, policy=policy_path, catalog=catalog)
    manifest = json.loads(files["manifest.json"])

    sources, pins = {}, {}
    for scope in policy["resources"]:
        key, datasets = scope["key"], scope["dataset_ids"]
        parameters, mappings = [
            json.loads(files["resources/" + scope[kind]["file"]])
            for kind in ("parameters", "mappings")
        ]
        if mappings["backend"] == "grib2":
            dataset, = datasets
            projected = product_parameter_definitions(orig, dataset)
            if projected != parameters["parameters"]:
                raise ValueError(f"{key} v57 parameters differ from the 1.6-03 projection")
        sources[key] = (parameters, mappings)
        pins[key] = {
            "dataset_ids": datasets,
            "parameters": scope["parameters"],
            "mappings": scope["mappings"],
        }
    return sources, pins, manifest, orig, carriers


def index_decisions(document):
    if document["schema_version"] != 1 or document["task"] != "1.6-07":
        raise ValueError("expected the 1.6-07 identity decisions")
    definitions, source_targets, service_targets, name_targets = {}, {}, {}, {}
    cases_by_id = defaultdict(set)
    for case, decision in document["decisions"].items():
        for ref in decision["evidence"]:
            if not (WORKSPACE / ref.split("#")[0]).exists():
                raise ValueError(f"{case} references missing evidence {ref}")
        scoped = {
            (source, pid): target
            for source, replacements in decision.get("source_targets", {}).items()
            for pid, target in replacements.items()
        }
        for index, additions in (
            (definitions, decision.get("definitions", {})),
            (source_targets, scoped),
            (service_targets, decision.get("service_targets", {})),
            (name_targets, decision.get("source_name_targets", {})),
        ):
            if index.keys() & additions.keys():
                raise ValueError(f"{case} overrides an existing identity decision")
            index.update({key: (value, case) for key, value in additions.items()})
        for pid in (*decision.get("parameter_ids", []), *decision.get("definitions", {})):
            cases_by_id[pid].add(case)
    return definitions, source_targets, service_targets, name_targets, cases_by_id


def ancestors(definitions, pid):
    seen = {pid}
    while (pid := definitions[pid].get("parent")) is not None:
        if pid in seen:
            raise ValueError(f"cyclic parent relationship for {pid}")
        seen.add(pid)
        yield pid


def choose_definitions(sources, public, overrides, redirects, name_choices):
    """Reuse reviewed definitions and apply the evidence-backed identity decisions."""
    sources_by_id = defaultdict(dict)
    targets = {}
    for key, (parameters, _) in sources.items():
        for row in parameters["parameters"]:
            pid = row["parameter_id"]
            target = redirects.get((key, pid), (pid, None))[0]
            targets[key, pid] = target
            sources_by_id[target][key, pid] = row
    if redirects.keys() - targets.keys():
        raise ValueError("a source identity decision refers to an absent source definition")

    definitions, spellings = {}, defaultdict(lambda: defaultdict(list))
    for pid in sorted(sources_by_id.keys() | overrides.keys()):
        choices = sources_by_id[pid]
        preferred = public.get(pid)
        if preferred is None and choices:
            (key, _), row = next(iter(choices.items()))
            preferred = dict(row)
            if "parent" in preferred:
                preferred["parent"] = targets[key, preferred["parent"]]
        definition = {**(preferred or {}), **overrides.get(pid, ({}, None))[0], "parameter_id": pid}
        definition.pop("aliases", None)
        definitions[pid] = definition
        for (key, _), row in choices.items():
            for name in (row["name"], *row.get("aliases", [])):
                spellings[name][pid].append({"resource": key, "parameter_id": row["parameter_id"]})
        if pid in public:
            for name in public[pid].get("aliases", []):
                spellings[name][pid].append({"resource": "public-1.6-03", "parameter_id": pid})

    canonical = {row["name"]: pid for pid, row in definitions.items()}
    if len(canonical) != len(definitions):
        raise ValueError("unified canonical names must be unique")
    name_decisions = {}
    if name_choices.keys() - spellings.keys():
        raise ValueError("a name decision refers to an absent source spelling")
    for name, candidates in sorted(spellings.items()):
        owner = canonical.get(name)
        if name in name_choices:
            chosen, case = name_choices[name]
            if chosen is not None and chosen not in candidates:
                raise ValueError(f"{name} chooses an identity outside the recorded source candidates")
            if owner is not None and owner != chosen:
                raise ValueError(f"{name} is reserved by a conflicting canonical name")
        elif len(candidates) == 1:
            chosen, = candidates
            case = "source-definitions"
        elif owner is not None and candidates.keys() <= {owner, *ancestors(definitions, owner)}:
            chosen, case = owner, "parent-names"
        else:
            raise ValueError(f"source spelling {name!r} requires a name decision: {sorted(candidates)}")
        if chosen is not None and name in definitions and chosen != name:
            raise ValueError(f"{name} is reserved by a different stable ID")
        old_ids = {row["parameter_id"] for rows in candidates.values() for row in rows}
        if len(old_ids) > 1 or len(candidates) > 1 or name in name_choices:
            name_decisions[name] = {"sources": dict(candidates), "target": chosen, "decision": case}
            if chosen is None and name in definitions:
                name_decisions[name]["stable_id"] = name
        if chosen is not None and definitions[chosen]["name"] != name:
            definitions[chosen].setdefault("aliases", []).append(name)
    return definitions, targets, name_decisions


def group_carriers(carriers, sources, pins):
    keys = {
        datasets["dataset_ids"][0]: key for key, datasets in pins.items()
        if sources[key][1]["backend"] == "grib2"
    }
    by_parameter, by_mapping = defaultdict(list), defaultdict(list)
    mappings = {
        key: {row["id"]: row for row in resource["mappings"]}
        for key, (_, resource) in sources.items()
    }
    for carrier_id, row in carriers.items():
        key, pid = keys[row["scope"]["dataset"]], row["parameter_id"]
        by_parameter[key, pid].append(carrier_id)
        for reference in row["product_mappings"]:
            mapping_id = reference["id"]
            if mappings[key][mapping_id]["parameter_id"] != pid:
                raise ValueError(f"{carrier_id} has an inconsistent mapping identity")
            by_mapping[key, mapping_id].append(carrier_id)
    return by_parameter, by_mapping


def service_evidence(mapping, source_definition):
    fixed = source_definition["fixed_conditions"]
    period = fixed.get("statistics", {}).get("period", {})
    if period.get("kind") == "trailing":
        return "service_endpoint_difference"
    if mapping["id"] in {"S-gfs-fcst.frozen.CPE", "S-gfs-fcst.frozen.LPE"}:
        return "service_window_matches_initialization_at_24h"
    for ref in mapping["evidence"]:
        if not ref.startswith("stage1.2/") or "original" not in ref:
            continue
        path = ref.removeprefix("stage1.2/").split(";")[0].split("#")[0]
        if (WORKSPACE / SERVICE_EVIDENCE / path).exists():
            return "service_original_comparison"
    return "service_evidence_only"


def collect_entries(sources, pins, orig, by_parameter, by_mapping, targets, service_targets, cases):
    entries, branches, by_old_id = [], [], defaultdict(list)
    for key, (parameters, mapping_resource) in sources.items():
        backend = mapping_resource["backend"]
        effective = effective_parameters(parameters)
        mappings_by_pid, children = defaultdict(list), defaultdict(list)
        service_elements, branch_targets = defaultdict(set), defaultdict(dict)
        origins = {}
        if backend == "grib2":
            dataset, = pins[key]["dataset_ids"]
            origins = {
                row.get("public_parameter_id") or row["definition"]["parameter_id"]:
                "public_reference" if "public_parameter_id" in row else "product_definition"
                for row in orig["products"][dataset]["parameters"]
            }

        for pid, row in effective.items():
            if "parent" in row:
                children[row["parent"]].append(pid)
        for mapping in sorted(mapping_resource["mappings"], key=lambda row: row["id"]):
            pid, mid = mapping["parameter_id"], mapping["id"]
            target = targets[key, pid]
            decisions = cases[pid] | cases[target]
            carrier_ids = by_mapping.get((key, mid), [])
            if backend == "grib2":
                evidence = "orig_carrier_receipt" if carrier_ids else "orig_product_mapping"
                value_mode = "original_values" if "unit" not in mapping["native"].get("translate", {}) else "unit_rule"
            else:
                evidence = service_evidence(mapping, effective[pid])
                value_mode = "service"
                service_elements[pid].add(mapping["native"]["match"]["fcstEle"])
                if mid in service_targets:
                    target, case = service_targets[mid]
                    decisions = decisions | {case}
                    branch_targets[pid][mid] = target
            branches.append({
                "resource": key, "backend": backend, "scope": mapping["applies_to"], "mapping_id": mid,
                "source_parameter_id": pid, "unified_parameter_id": target,
                "value_mode": value_mode, "file_evidence": evidence, "carrier_ids": carrier_ids,
                "evidence": mapping["evidence"], "decisions": sorted(decisions),
            })
            mappings_by_pid[pid].append(mid)
        for pid, row in sorted(effective.items()):
            target = targets[key, pid]
            decisions = cases[pid] | cases[target]
            if backend == "cmadaas" and row["fixed_conditions"].get("statistics") == INSTANTANEOUS:
                decisions = decisions | {"service-instantaneous"}
            if not mappings_by_pid[pid] and not children[pid]:
                raise ValueError(f"{key} {pid} has neither mappings nor an inheritance role")
            entry = {
                "resource": key,
                "origin": origins.get(pid, "service_definition"),
                "source": row,
                "unified_parameter_id": target,
                "source_mapping_ids": mappings_by_pid[pid],
                "source_children": sorted(children[pid]),
                "carrier_ids": by_parameter.get((key, pid), []),
                "decisions": sorted(decisions or {"source-definitions"}),
            }
            if backend == "cmadaas":
                entry["service_elements"] = sorted(service_elements[pid])
                if branch_targets[pid]:
                    entry["branch_targets"] = branch_targets[pid]
            entries.append(entry)
            by_old_id[pid].append(entry)
    if service_targets.keys() - {row["mapping_id"] for row in branches if row["backend"] == "cmadaas"}:
        raise ValueError("a service identity decision refers to an absent mapping")
    return entries, branches, by_old_id


def compare_source_ids(by_old_id):
    differences = {}
    for pid, entries in sorted(by_old_id.items()):
        rows = [entry["source"] for entry in entries]
        fields = sorted(set().union(*(row.keys() for row in rows)))
        changed = [field for field in fields if len({encode(row.get(field)) for row in rows}) > 1]
        targets = {row["resource"]: row["unified_parameter_id"] for row in entries}
        split = len(set(targets.values())) > 1
        if not changed and not split:
            continue
        decisions = {case for entry in entries for case in entry["decisions"]}
        physical = {"unit", "parent", "description", "fixed_conditions"} & set(changed)
        shared_physics = {
            encode({key: value for key, value in row["fixed_conditions"].items()
                    if key != "statistics" or value != INSTANTANEOUS})
            for row in rows
        }
        if physical == {"fixed_conditions"} and len(shared_physics) == 1:
            decisions.add("service-instantaneous")
        elif physical and not decisions - {"source-definitions", "service-instantaneous"}:
            raise ValueError(f"{pid} requires a physical identity decision for {sorted(physical)}")
        differences[pid] = {
            "fields": changed,
            "unified_ids_by_resource": targets,
            "split_identity": split,
            "decisions": sorted(decisions),
        }
    return differences


def index_uses(definitions, branches, generic):
    kinds, children, family = defaultdict(Counter), defaultdict(list), defaultdict(list)
    for branch in branches:
        pid = branch["unified_parameter_id"]
        if pid not in definitions:
            raise ValueError(f"{branch['mapping_id']} refers to an absent unified identity")
        kinds[pid][branch["file_evidence"]] += 1
    for pid, row in definitions.items():
        if "parent" in row:
            children[row["parent"]].append(pid)
        if kinds[pid]:
            for parent in ancestors(definitions, pid):
                family[parent].append(pid)

    uses = {}
    for pid in definitions:
        generic_ids = sorted(row["id"] for row in generic if row["parameter_id"] == pid)
        use = {"direct_branches": dict(kinds[pid]), "baseline_grib2_mappings": generic_ids,
               "children": children[pid]}
        if not kinds[pid]:
            if not family[pid]:
                raise ValueError(f"{pid} has no concrete source branch or descendant")
            variants = []
            for child in family[pid]:
                item = {"parameter_id": child}
                fixed = definitions[child]["fixed_conditions"]
                query = {"parameter": pid, **{k: v for k, v in fixed.items() if k != "statistics"}}
                try:
                    resolved = prepare_queries([query], definitions)
                except QueryError:
                    resolved = ()
                if len(resolved) == 1 and resolved[0].to_dict()["parameter"] == child:
                    item["parent_query"] = query
                variants.append(item)
            use["field_variants"] = variants
        uses[pid] = use
    return uses


def validate_concrete_names(definitions, uses):
    count = 0
    for pid, row in definitions.items():
        if not uses[pid]["direct_branches"]:
            continue
        for token in {pid, row["name"], *row.get("aliases", [])}:
            resolved, = prepare_queries([{"parameter": token}], definitions)
            if resolved.to_dict()["parameter"] != pid:
                raise ValueError(f"{token} selects a different identity than the registered {pid}")
            count += 1
    return count


def tsv(header, rows):
    output = StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def build_reconciliation(catalog, author=AUTHOR):
    sources, pins, manifest, orig, carriers = load_sources(catalog, author)
    decision_bytes = (author / DECISIONS).read_bytes()
    policy = json.loads(decision_bytes)
    overrides, redirects, service_targets, name_choices, cases = index_decisions(policy)
    public = {row["parameter_id"]: row for row in orig["public_parameters"]}
    definitions, targets, name_decisions = choose_definitions(sources, public, overrides, redirects, name_choices)
    for (_, pid), (target, case) in redirects.items():
        cases[pid].add(case)
        cases[target].add(case)
    for target, case in service_targets.values():
        cases[target].add(case)

    parameters = {
        "api_version": "cedarkit.parameters/v1", "id": "cedarkit.parameters.stage1.6-identity-review",
        "version": "1", "parameters": list(definitions.values()),
    }
    generic = orig["generic_grib2_mappings"]
    validated = validate_standalone_grib2(parameters, {
        "api_version": "cedarkit.mappings/v1", "id": "cedarkit.grib2.generic",
        "version": "1", "backend": "grib2", "tables": [], "mappings": generic,
    })
    by_parameter, by_mapping = group_carriers(carriers, sources, pins)
    entries, branches, by_old_id = collect_entries(
        sources, pins, orig, by_parameter, by_mapping, targets, service_targets, cases,
    )
    uses = index_uses(validated, branches, generic)
    checked_names = validate_concrete_names(validated, uses)
    source_differences = compare_source_ids(by_old_id)
    data = {
        "schema_version": 1, "task": "1.6-07",
        "catalog": {key: manifest["catalog"][key] for key in ("id", "version", "sha256")},
        "browser": {key: manifest[key] for key in ("id", "version")},
        "source_resources": pins,
        "decisions": {"file": DECISIONS, "sha256": sha256(decision_bytes).hexdigest()},
        "orig_carriers": {"file": CARRIERS, "sha256": sha256((author / CARRIERS).read_bytes()).hexdigest()},
        "unified_parameters": list(definitions.values()),
        "unified_uses": uses, "source_entries": entries,
        "same_id_differences": source_differences, "source_name_decisions": name_decisions,
    }
    files = {
        REGISTRY: encode(data),
        SOURCE_INDEX: tsv(
            ("resource", "origin", "source_id", "source_name", "aliases", "source_unit", "source_parent",
             "unified_id", "unified_name", "unified_unit", "mapping_ids", "carrier_ids", "source_children", "decisions"),
            ((row["resource"], row["origin"], row["source"]["parameter_id"], row["source"]["name"],
              ",".join(row["source"].get("aliases", [])), row["source"]["unit"], row["source"].get("parent"),
              row["unified_parameter_id"], definitions[row["unified_parameter_id"]]["name"],
              validated[row["unified_parameter_id"]]["unit"], ",".join(row["source_mapping_ids"]),
              ",".join(row["carrier_ids"]), ",".join(row["source_children"]), ",".join(row["decisions"]))
             for row in entries),
        ),
        BRANCH_INDEX: tsv(
            ("resource", "backend", "mapping_id", "source_id", "unified_id", "unified_name", "file_evidence",
             "value_mode", "carrier_ids", "scope", "evidence", "decisions"),
            ((row["resource"], row["backend"], row["mapping_id"], row["source_parameter_id"],
              row["unified_parameter_id"], definitions[row["unified_parameter_id"]]["name"], row["file_evidence"],
              row["value_mode"], ",".join(row["carrier_ids"]),
              json.dumps(row["scope"], sort_keys=True), json.dumps(row["evidence"], ensure_ascii=False),
              ",".join(row["decisions"]))
             for row in branches),
        ),
    }
    source_mapped = {
        backend: {row["source_parameter_id"] for row in branches if row["backend"] == backend}
        for backend in ("grib2", "cmadaas")
    }
    unified_mapped = {
        backend: {row["unified_parameter_id"] for row in branches if row["backend"] == backend}
        for backend in source_mapped
    }
    header_cases = {}
    for case, decision in policy["decisions"].items():
        if "shared_header_carriers" not in decision:
            continue
        first, *others = [carriers[cid] for cid in decision["shared_header_carriers"]]
        common = {key: first[key] for key in ("grib2_triple", "native_context")}
        if any(any(row[key] != value for key, value in common.items()) for row in others):
            raise ValueError(f"{case} carriers no longer share the recorded header conditions")
        header_cases[case] = {**common, "carriers": decision["shared_header_carriers"],
                              "remaining_evidence": decision["remaining_evidence"]}
    files["verification.json"] = encode({
        "task": "1.6-07", "status": "passed", "cedarkit_query": version("cedarkit-query"),
        "catalog": data["catalog"], "browser": data["browser"],
        "verified_resource_files": 1 + 2 * len(pins),
        "verified_dataset_bindings": len(manifest["dataset_bindings"]),
        "source_definitions_by_resource": dict(Counter(row["resource"] for row in entries)),
        "source_roles": dict(Counter(row["origin"] for row in entries)),
        "source_entries_with_mappings": sum(bool(row["source_mapping_ids"]) for row in entries),
        "source_ids": len(by_old_id), "source_entries": len(entries),
        "source_ids_with_orig": len(source_mapped["grib2"]),
        "source_ids_with_service_only": len(source_mapped["cmadaas"] - source_mapped["grib2"]),
        "source_inheritance_only_ids": len(by_old_id.keys() - set.union(*source_mapped.values())),
        "orig_carriers": sum(map(len, by_parameter.values())),
        "orig_carriers_with_product_definition": sum(
            len(row["carrier_ids"]) for row in entries if row["origin"] == "product_definition"
        ),
        "orig_evidence_messages": sum(row["v52_messages"] for row in carriers.values()),
        "v57_added_messages": sum(row["v57_added_messages"] for row in carriers.values()),
        "mapping_rows_by_resource": dict(Counter(row["resource"] for row in branches)),
        "mapping_rows_by_file_evidence": dict(Counter(row["file_evidence"] for row in branches)),
        "unified_ids": len(uses),
        "unified_ids_with_orig": len(unified_mapped["grib2"]),
        "unified_ids_with_service_only": len(unified_mapped["cmadaas"] - unified_mapped["grib2"]),
        "unified_inheritance_only_ids": sum(not row["direct_branches"] for row in uses.values()),
        "concrete_name_id_alias_queries_checked": checked_names,
        "baseline_independent_grib2_mappings": len(generic),
        "same_id_differences": len(source_differences),
        "split_source_identities": sum(row["split_identity"] for row in source_differences.values()),
        "source_name_decisions": len(name_decisions),
        "shared_header_cases": header_cases,
        "resolved_inputs": manifest["sources"],
        "files_sha256": {name: sha256(raw).hexdigest() for name, raw in files.items()},
    })
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True, help="sealed v57 catalog beside its seven resource pairs")
    parser.add_argument("--output", type=Path, required=True, help="new directory for the registration and its indices")
    args = parser.parse_args()
    write_snapshot(build_reconciliation(args.catalog), args.output)


if __name__ == "__main__":
    main()
