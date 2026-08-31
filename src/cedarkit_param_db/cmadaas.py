"""Auditable CMADaaS external-element vocabulary import and inventory."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .db import PROJECT_ROOT, connect

CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def read_vocabulary(path: Path | str) -> tuple[tuple[str, str], ...]:
    """Parse the canonical two-column Markdown vocabulary without guessing mappings."""
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()]
    start = next((i for i, value in enumerate(lines) if value == "代码"), None)
    if start is None:
        raise ValueError("CMADaaS vocabulary has no '代码' heading")
    # The document has two column headings (``代码`` / ``意义``); begin at
    # the first actual uppercase code rather than relying on blank-line count.
    first = next((i for i, value in enumerate(lines[start + 1:], start + 1) if CODE.fullmatch(value)), None)
    if first is None:
        raise ValueError("CMADaaS vocabulary has no codes")
    values = [value for value in lines[first:] if value]
    if len(values) % 2:
        raise ValueError("CMADaaS vocabulary has an unpaired code/description")
    records = tuple((values[i], values[i + 1]) for i in range(0, len(values), 2))
    codes = [code for code, _ in records]
    if any(not CODE.fullmatch(code) for code in codes):
        raise ValueError("CMADaaS vocabulary contains an invalid code")
    if len(set(codes)) != len(codes):
        raise ValueError("CMADaaS vocabulary contains duplicate codes")
    return records


def provenance(path: Path | str) -> str:
    """Return the stable source path plus SHA-256 used in database rows."""
    source = Path(path).resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    try:
        label = source.relative_to(PROJECT_ROOT.parents[1]).as_posix()
    except ValueError:
        label = source.as_posix()
    return f"{label}#sha256={digest}"


def import_vocabulary(path: Path | str, db_path: Path | str, *, namespace: str = "cmadaas") -> int:
    """Idempotently import vocabulary rows; mappings are deliberately untouched."""
    records, source_ref = read_vocabulary(path), provenance(path)
    conn = connect(db_path)
    try:
        with conn:
            for code, description in records:
                current = conn.execute(
                    "SELECT description_cn, source_ref FROM external_elements WHERE namespace = ? AND code = ?",
                    (namespace, code),
                ).fetchone()
                if current is None:
                    conn.execute("INSERT INTO external_elements(namespace, code, description_cn, source_ref) VALUES (?, ?, ?, ?)", (namespace, code, description, source_ref))
                elif tuple(current) != (description, source_ref):
                    conn.execute("UPDATE external_elements SET description_cn = ?, source_ref = ? WHERE namespace = ? AND code = ?", (description, source_ref, namespace, code))
        return len(records)
    finally:
        conn.close()


def inventory(db_path: Path | str, *, namespace: str = "cmadaas") -> dict[str, object]:
    """Produce stable, machine-readable mapped/unmapped inventory."""
    conn = connect(db_path)
    try:
        rows = conn.execute("""
            SELECT e.code, e.description_cn, e.source_ref, p.parameter_id
            FROM external_elements e
            LEFT JOIN entry_external_elements m ON m.namespace = e.namespace AND m.code = e.code
            LEFT JOIN entries p ON p.id = m.entry_id
            WHERE e.namespace = ? ORDER BY e.code
        """, (namespace,)).fetchall()
    finally:
        conn.close()
    elements = [{"code": row["code"], "description_cn": row["description_cn"],
                 "provenance": row["source_ref"], "status": "mapped" if row["parameter_id"] else "unmapped",
                 **({"parameter_id": row["parameter_id"]} if row["parameter_id"] else {})} for row in rows]
    return {"namespace": namespace, "elements": elements}


def inventory_json(db_path: Path | str, *, namespace: str = "cmadaas") -> str:
    return json.dumps(inventory(db_path, namespace=namespace), ensure_ascii=False, indent=2) + "\n"
