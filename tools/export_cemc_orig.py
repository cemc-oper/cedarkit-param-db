"""Stage reviewed CEMC ORIG resources and their pinned catalog."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from runpy import run_path

from cedarkit_query import Catalog, Mappings, Parameters, validate_resource_set

AUTHOR = Path(__file__).resolve().parents[1] / "authoring/cemc-orig-batch1.json"


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-version", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--additions", type=Path, action="append", default=[])
    parser.add_argument(
        "--release", type=Path, help="apply a reviewed ORIG naming and catalog release"
    )
    parser.add_argument(
        "--binding-candidate", type=Path, help="stage a reviewed ORIG binding candidate"
    )
    parser.add_argument(
        "--mapping-refinement", type=Path, action="append", default=[],
        help="apply a reviewed refinement to that binding in release order",
    )
    args = parser.parse_args()
    if args.binding_candidate and not args.release:
        parser.error("--binding-candidate needs the reviewed base --release")
    if args.mapping_refinement and not args.binding_candidate:
        parser.error("--mapping-refinement needs the reviewed --binding-candidate")
    author = json.loads(AUTHOR.read_bytes())
    for path in args.additions:
        additions = json.loads(path.read_bytes())
        for system, product in additions["products"].items():
            baseline = author["products"][system]
            for kind in ("parameters", "mappings"):
                resource = baseline[kind]
                extra = product[kind]
                if int(extra["version"]) <= int(resource["version"]):
                    parser.error(f"{system} {kind} additions need a newer version")
                resource["version"] = extra["version"]
                resource[kind].extend(extra[kind])
    baseline_catalog = Catalog(json.loads(args.catalog.read_bytes())).to_dict()
    catalog = deepcopy(baseline_catalog) if args.release else baseline_catalog
    target = None
    if args.release:
        release = json.loads(args.release.read_bytes())
        review = json.loads((args.release.parent / release["name_review"]).read_bytes())
        helpers = run_path(str(Path(__file__).with_name("cemc_orig_release.py")))
        helpers["apply_name_review"](author["products"], release, review)
        helpers["apply_catalog_provisions"](catalog, release)
        target = release["catalog_version"]
        if args.binding_candidate:
            candidate = json.loads(args.binding_candidate.read_bytes())
            if candidate["base_release"] != release["id"] or int(
                candidate["catalog_version"]
            ) <= int(target):
                parser.error("binding candidate needs its base release and a newer catalog version")
            helpers["apply_binding_candidate"](author["products"], catalog, candidate)
            target = candidate["catalog_version"]
            for path in args.mapping_refinement:
                refinement = json.loads(path.read_bytes())
                target = helpers["apply_mapping_refinement"](author["products"], candidate, refinement, target)
        if args.catalog_version is not None and str(args.catalog_version) != target:
            parser.error("--catalog-version conflicts with the reviewed release")
    datasets = {row["id"]: row for row in catalog["datasets"]}
    files = {}
    pins_changed = False
    for system, resources in author["products"].items():
        dataset = datasets[resources["dataset"]]
        parameters = Parameters(resources["parameters"]).to_dict()
        mappings = Mappings(resources["mappings"]).to_dict()
        validate_resource_set(parameters, [mappings], catalog, dataset["id"])
        for kind, resource, ref in (
            ("parameters", parameters, dataset["parameter_registry"]),
            ("mappings", mappings, dataset["mappings"]["grib2"]),
        ):
            filename = f"current-{system}-{kind}.json"
            raw = files[filename] = encode(resource)
            digest = hashlib.sha256(raw).hexdigest()
            if ref.get("sha256") not in {None, digest} and int(ref["version"]) >= int(
                resource["version"]
            ):
                parser.error(f"{filename} needs a newer content version")
            pins_changed |= ref.get("sha256") != digest
            ref.update(version=resource["version"], sha256=digest)
    if target is not None:
        previous = baseline_catalog["version"]
        if int(target) < int(previous) or (target == previous and catalog != baseline_catalog):
            parser.error("changed release catalog bytes require a newer catalog version")
        catalog["version"] = target
    elif args.catalog_version is not None or (args.additions and pins_changed):
        if args.catalog_version is None or args.catalog_version <= int(catalog["version"]):
            parser.error("changed resource pins require a newer --catalog-version")
        catalog["version"] = str(args.catalog_version)
    files["catalog-v1.json"] = encode(catalog)
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("--output must be empty")
    for name, raw in files.items():
        (args.output / name).write_bytes(raw)


if __name__ == "__main__":
    main()
