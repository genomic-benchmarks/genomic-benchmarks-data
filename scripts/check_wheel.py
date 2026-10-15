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


def _select_datasets(
    metadata: dict,
    *,
    core_set: bool,
    task_type: str | None = None,
) -> dict:
    """Select expected datasets directly from packaged metadata."""
    selected = {}
    for collection_name, collection in metadata.items():
        datasets = {
            dataset["dataset_name"]: dataset["task_description"]
            for dataset in collection["datasets"]
            if dataset["core_set"] is core_set
            and (task_type is None or dataset["task_type"] == task_type)
        }
        if datasets:
            selected[collection_name] = datasets
    return selected


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

    for collection in metadata.values():
        for dataset in collection["datasets"]:
            if type(dataset.get("core_set")) is not bool:
                raise RuntimeError(
                    "dataset has a missing or non-Boolean core_set: "
                    f"{collection['collection']}/{dataset['dataset_name']}"
                )

    expected_core = _select_datasets(metadata, core_set=True)
    expected_non_core = _select_datasets(metadata, core_set=False)
    if package.list_datasets(core_set=True) != expected_core:
        raise RuntimeError("core_set=True returned unexpected datasets")
    if package.list_datasets(core_set=False) != expected_non_core:
        raise RuntimeError("core_set=False returned unexpected datasets")

    expected_core_binary = _select_datasets(
        metadata,
        core_set=True,
        task_type="Binary classification",
    )
    if package.list_datasets(
        core_set=True,
        task_type="Binary classification",
    ) != expected_core_binary:
        raise RuntimeError("combined core_set and task_type filter failed")

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
    print(
        "ok: core-set filters returned "
        f"{sum(map(len, expected_core.values()))} core and "
        f"{sum(map(len, expected_non_core.values()))} non-core datasets"
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} PACKAGE_MODULE")
    raise SystemExit(main(sys.argv[1]))
