"""Apply a reviewed ORIG naming and catalog release to authored resources."""

from copy import deepcopy


def apply_name_review(products, release, review):
    canonical = {row["parameter_id"]: row for row in review["parameters"]}
    support = {row["parameter_id"]: row["name"] for row in review["support_definition_names_for_publication"]}
    versions = release["parameter_versions"]
    changed = set()
    for system, product in products.items():
        resource = product["parameters"]
        mapped = {row["parameter_id"] for row in product["mappings"]["mappings"]}
        for row in resource["parameters"]:
            pid = row["parameter_id"]
            if pid in support:
                if pid in mapped:
                    raise ValueError(f"directly mapped parameter cannot be renamed as a parent: {system}/{pid}")
                if row["name"] != support[pid]:
                    row["name"] = support[pid]
                    changed.add(system)
            if pid in canonical:
                decision = canonical[pid]
                aliases = list(dict.fromkeys([*row.get("aliases", []),
                                             *decision["new_aliases_by_product"].get(system, [])]))
                if row["name"] != decision["name"] or aliases != row.get("aliases", []):
                    row["name"] = decision["name"]
                    if aliases:
                        row["aliases"] = aliases
                    changed.add(system)
    if changed != versions.keys():
        raise ValueError(f"reviewed parameter revisions must name the changed products: {sorted(changed)}")
    for system, version in versions.items():
        resource = products[system]["parameters"]
        if int(version) < int(resource["version"]):
            raise ValueError(f"parameter revision would move backwards: {system}")
        resource["version"] = version


def apply_catalog_provisions(catalog, release):
    datasets = {row["id"]: row for row in catalog["datasets"]}
    for row in release["products"]:
        dataset = datasets[row["dataset"]]
        product, = [p for p in dataset["products"] if (p["id"], p["version"]) == (row["product"], row["product_version"])]
        for provision in row["provides"]:
            if provision not in product["provides"]:
                product["provides"].append(deepcopy(provision))
