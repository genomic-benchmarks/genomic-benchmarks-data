#!/usr/bin/env python3
"""Validate the metadata shipped by both packages.

Run from the repository root with::

    python scripts/validate_metadata.py

Each package has its own schema because the agents package intentionally omits
held-out splits.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


ROOT = Path(__file__).resolve().parent.parent
EXPECTED_COLLECTIONS = {
    "BEACON",
    "GUE_v2",
    "OmniGenBench",
    "genomic-benchmarks",
    "mRNABench",
    "miRBench",
    "nucleotide_benchmarks",
}
PACKAGE_METADATA = (
    ROOT
    / "genomic-benchmarks-data"
    / "genomic_benchmarks_data"
    / "metadata",
    ROOT
    / "genomic-benchmarks-data4agents"
    / "genomic_benchmarks_data4agents"
    / "metadata",
)


def _reject_non_json_constant(value: str) -> None:
    """Reject NaN and infinities, which are not part of JSON."""
    raise ValueError(f"invalid JSON constant {value!r}")


def _load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_constant=_reject_non_json_constant)


def _json_path(parts: Iterable[object]) -> str:
    location = "$"
    for part in parts:
        if isinstance(part, int):
            location += f"[{part}]"
        elif isinstance(part, str) and part.isidentifier():
            location += f".{part}"
        else:
            location += f"[{json.dumps(part)}]"
    return location


def _schema_error_message(error: ValidationError) -> str:
    return f"{_json_path(error.absolute_path)}: {error.message}"


def _validate_metadata_directory(metadata_dir: Path) -> bool:
    label = metadata_dir.relative_to(ROOT)
    schema_path = metadata_dir / "metadata.schema.json"
    print(label)

    if not schema_path.is_file():
        print(f"  FAILED: missing schema {schema_path.name}", file=sys.stderr)
        return False

    try:
        schema = _load_json(schema_path)
        Draft202012Validator.check_schema(schema)
    except (OSError, ValueError, json.JSONDecodeError, SchemaError) as error:
        print(f"  FAILED schema: {error}", file=sys.stderr)
        return False

    validator = Draft202012Validator(schema)
    paths = sorted(metadata_dir.glob("*_metadata.json"))
    found: dict[str, str] = {}
    ok = True

    if not paths:
        print("  FAILED: no *_metadata.json files", file=sys.stderr)
        return False

    for path in paths:
        try:
            document = _load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"  FAILED {path.name}: {error}", file=sys.stderr)
            ok = False
            continue

        errors = sorted(
            validator.iter_errors(document),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        if errors:
            print(f"  FAILED {path.name}: {len(errors)} schema error(s)")
            for error in errors:
                print(f"    - {_schema_error_message(error)}")
            ok = False
            continue

        collection = document["collection"]
        if collection in found:
            print(
                f"  FAILED {path.name}: collection {collection!r} is already "
                f"provided by {found[collection]}",
                file=sys.stderr,
            )
            ok = False
            continue

        found[collection] = path.name
        print(
            f"  ok     {path.name}: {collection}, "
            f"{len(document['datasets'])} datasets"
        )

    missing = sorted(EXPECTED_COLLECTIONS - set(found))
    unexpected = sorted(set(found) - EXPECTED_COLLECTIONS)
    if missing:
        print(
            f"  FAILED: missing or invalid collections: {', '.join(missing)}",
            file=sys.stderr,
        )
        ok = False
    if unexpected:
        print(
            f"  FAILED: unexpected collections: {', '.join(unexpected)}",
            file=sys.stderr,
        )
        ok = False

    return ok


def main() -> int:
    results = [
        _validate_metadata_directory(metadata_dir)
        for metadata_dir in PACKAGE_METADATA
    ]

    if not all(results):
        return 1

    print("\nBoth packages' metadata passed schema validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
