#!/usr/bin/env python3
"""Smoke-test metadata through an installed package's public API."""

from __future__ import annotations

import importlib
import sys
from importlib import resources
from pathlib import Path


EXPECTED_COLLECTIONS = {
    "BEACON",
    "GUE_v2",
    "OmniGenBench",
    "genomic-benchmarks",
    "mRNABench",
    "miRBench",
    "nucleotide_benchmarks",
}


def main(module_name: str) -> int:
    package = importlib.import_module(module_name)
    package_path = Path(package.__file__).resolve()
    metadata = package.load_metadata()
    metadata_dir = resources.files(module_name).joinpath("metadata")

    if set(metadata) != EXPECTED_COLLECTIONS:
        missing = sorted(EXPECTED_COLLECTIONS - set(metadata))
        unexpected = sorted(set(metadata) - EXPECTED_COLLECTIONS)
        raise RuntimeError(
            f"unexpected collections; missing={missing}, "
            f"unexpected={unexpected}"
        )

    metadata_files = sorted(
        item.name
        for item in metadata_dir.iterdir()
        if item.name.endswith("_metadata.json")
    )
    if len(metadata_files) != len(EXPECTED_COLLECTIONS):
        raise RuntimeError(
            f"expected {len(EXPECTED_COLLECTIONS)} metadata documents, "
            f"found {len(metadata_files)}: {metadata_files}"
        )

    schema = metadata_dir.joinpath("metadata.schema.json")
    if not schema.is_file():
        raise RuntimeError("installed package does not contain metadata.schema.json")

    print(f"ok: imported {module_name} from {package_path}")
    print(
        f"ok: loaded {len(metadata)} collections and found "
        f"{len(metadata_files)} metadata documents plus the schema"
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} PACKAGE_MODULE")
    raise SystemExit(main(sys.argv[1]))
