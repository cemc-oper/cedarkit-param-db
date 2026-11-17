"""Export the Stage 1.6 standalone GRIB2 and CEMC ORIG resource snapshot."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cedarkit_query import Mappings, Parameters, validate_standalone_grib2

from cemc_orig_registry import product_parameter_definitions
from export_cemc_orig import AUTHOR, build_product_resources, encode

REGISTRY = AUTHOR.with_name("cemc-orig-stage1.6-registry.json")
CATALOG = "catalog-v1.json"
PUBLIC = "public-parameters.json"
GENERIC = "generic-grib2-mappings.json"


def _pin(name, raw):
    resource = json.loads(raw)
    return {
        "path": name,
        **{key: resource[key] for key in ("api_version", "id", "version")},
        "sha256": sha256(raw).hexdigest(),
    }


def build_snapshot(catalog, registry_path=REGISTRY):
    """Return the validated snapshot as relative file names and bytes."""
    registry_raw = registry_path.read_bytes()
    registry = json.loads(registry_raw)
    if registry["schema_version"] != 1:
        raise ValueError("unsupported ORIG authoring registry version")

    parameters = Parameters({
        "api_version": "cedarkit.parameters/v1",
        "id": "cedarkit.parameters.public",
        "version": "1",
        "parameters": registry["public_parameters"],
    })
    mappings = Mappings({
        "api_version": "cedarkit.mappings/v1",
        "id": "cedarkit.grib2.generic",
        "version": "1",
        "backend": "grib2",
        "tables": [],
        "mappings": registry["generic_grib2_mappings"],
    })
    validate_standalone_grib2(parameters, mappings)

    source = registry["v57_authoring"]
    recipe = source["recipe"]
    author = registry_path.parent
    base = author / recipe["native_base"]
    additions = [author / name for name in recipe["native_additions"]]
    release = author / recipe["native_release"]
    review = release.parent / json.loads(release.read_bytes())["name_review"]
    binding = author / recipe["native_binding"]
    refinements = [author / name for name in recipe["native_mapping_refinement"]]
    for path in (base, *additions, release, review, binding, *refinements):
        if sha256(path.read_bytes()).hexdigest() != source["source_files_sha256"].get(path.name):
            raise ValueError(f"{path.name} differs from the reviewed v57 author input")

    files = build_product_resources(
        catalog, author_path=base, additions=additions, release=release,
        binding_candidate=binding, mapping_refinements=refinements,
        projected_parameters={
            dataset: product_parameter_definitions(registry, dataset)
            for dataset in registry["products"]
        },
    )
    catalog_pin = _pin(CATALOG, files[CATALOG])
    if catalog_pin != {"path": CATALOG, **source["catalog"]}:
        raise ValueError("catalog differs from the reviewed v57 catalog")
    datasets = {row["id"]: row for row in json.loads(files[CATALOG])["datasets"]}
    products = {}
    for dataset, product in registry["products"].items():
        entry = datasets[dataset]
        scope = product["scope"]
        if scope["dataset"] != dataset or not any(
            (row["id"], row["version"]) == (scope["product"], scope["product_version"])
            for row in entry["products"]
        ):
            raise ValueError(f"{dataset} scope differs from the catalog")
        refs = {"parameters": entry["parameter_registry"], "mappings": entry["mappings"]["grib2"]}
        pins = {}
        for kind, ref in refs.items():
            expected = product["v57_resources"][kind]
            if ref != {key: expected[key] for key in ("path", "version", "sha256")}:
                raise ValueError(f"{dataset} {kind} catalog reference differs from v57")
            name = ref["path"]
            pin = _pin(name, files[name])
            if pin != {**expected, "api_version": f"cedarkit.{kind}/v1"}:
                raise ValueError(f"{dataset} {kind} differs from the pinned v57 bytes")
            pins[kind] = pin
        products[dataset] = {
            "scope": scope, "parameter_registry": pins["parameters"],
            "mappings": {"grib2": pins["mappings"]},
        }

    files[PUBLIC] = encode(parameters.to_dict())
    files[GENERIC] = encode(mappings.to_dict())
    files["manifest.json"] = encode({
        "schema_version": 1,
        "authoring": {"id": registry["id"], "sha256": sha256(registry_raw).hexdigest()},
        "catalog": catalog_pin,
        "standalone": {
            "parameter_registry": _pin(PUBLIC, files[PUBLIC]),
            "mappings": {"grib2": _pin(GENERIC, files[GENERIC])},
        },
        "products": products,
    })
    return files


def write_snapshot(files, output):
    """Publish all staged files together to a new directory."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent, prefix=".cemc-orig-") as temporary:
        stage = Path(temporary) / "snapshot"
        stage.mkdir()
        for name, raw in files.items():
            (stage / name).write_bytes(raw)
        stage.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        write_snapshot(build_snapshot(args.catalog, args.registry), args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
