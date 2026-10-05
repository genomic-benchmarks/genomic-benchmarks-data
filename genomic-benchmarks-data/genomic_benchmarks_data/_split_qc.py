"""Split-QC functionality available only in genomic-benchmarks-data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ._core.metadata import _get_dataset
from ._core.qc import (
    _clean_qc_value,
    _download_qc_csv,
    _get_qc_report_dir,
    _plot_flag_summary,
    _worst_flag,
)

_SPLIT_RESULTS_FILENAME = "combined_splits_results.csv"
_SPLIT_CHECK = "Data Leakage"


def download_split_qc_csv(
    record_id: str,
    force: bool = False,
) -> Path:
    """Download the combined split-QC results CSV."""
    return _download_qc_csv(record_id, _SPLIT_RESULTS_FILENAME, force=force)


def get_split_qc_report(
    record_id: str,
    collection: str,
    dataset_name: str,
    split_a: str,
    split_b: str,
    force: bool = False,
) -> Path:
    """Return the QC HTML report comparing two dataset splits."""
    dataset = _get_dataset(collection, dataset_name)
    available_splits = set(dataset.get("splits") or [])

    if split_a not in available_splits:
        raise KeyError(
            f"Split {split_a!r} not found for dataset {dataset_name!r}."
        )
    if split_b not in available_splits:
        raise KeyError(
            f"Split {split_b!r} not found for dataset {dataset_name!r}."
        )

    report_dir = _get_qc_report_dir(
        record_id,
        collection,
        dataset_name,
        force=force,
    )
    report = report_dir / "split" / f"{split_a}_{split_b}.html"
    if not report.exists():
        report = report_dir / "split" / f"{split_b}_{split_a}.html"

    if not report.exists():
        raise FileNotFoundError(
            f"No split QC report found for {split_a!r} and {split_b!r} "
            f"in {collection!r}/{dataset_name!r}."
        )

    return report


def _parse_split_qc(frame: pd.DataFrame) -> dict:
    """Separate pair comparisons from overall dataset split-QC rows."""
    results = {}

    for row in frame.itertuples(index=False):
        dataset_results = (
            results
            .setdefault(row.collection, {})
            .setdefault(
                row.dataset_name,
                {"overall": None, "comparisons": {}},
            )
        )

        if pd.notna(row.check):
            comparison = {
                "flag": _clean_qc_value(row.flag),
                "percentage_of_leaked_queries": _clean_qc_value(
                    row.percentage_of_leaked_queries
                ),
                "percentage_of_leaked_targets": _clean_qc_value(
                    row.percentage_of_leaked_targets
                ),
            }
            (
                dataset_results["comparisons"]
                .setdefault(row.train_split, {})
                .setdefault(row.test_split, {})
            )[row.check] = comparison

        elif pd.notna(row.statistic):
            dataset_results["overall"] = {
                "statistic": row.statistic,
                "flag": _clean_qc_value(row.flag),
            }

        else:
            raise ValueError(
                "Split-QC row has neither a check nor a statistic for "
                f"{row.collection!r}/{row.dataset_name!r}."
            )

    return results


def load_split_qc_results(
    record_id: str,
    force: bool = False,
) -> dict:
    """Download and parse combined split-QC results."""
    path = download_split_qc_csv(record_id, force=force)
    return _parse_split_qc(pd.read_csv(path))


def _get_split_qc_metrics(results: dict) -> list[str]:
    """Return check names from detailed train/held-out comparisons."""
    checks = set()
    for collection in results.values():
        for dataset in collection.values():
            for train_results in dataset["comparisons"].values():
                for test_results in train_results.values():
                    checks.update(test_results.keys())
    return sorted(checks)


def list_split_qc_metrics(
    record_id: str,
    force: bool = False,
) -> list[str]:
    """Return available split-QC check names."""
    return _get_split_qc_metrics(
        load_split_qc_results(record_id, force=force)
    )


def _validate_checks(results: dict, check: str | list[str] | None) -> None:
    if check is None:
        return

    selected = {check} if isinstance(check, str) else set(check)
    available = set(_get_split_qc_metrics(results))
    unknown = selected - available
    if unknown:
        raise ValueError(
            f"Unknown QC check(s): {sorted(unknown)}. "
            f"Available checks: {sorted(available)}."
        )


def _overall_flag(dataset_results: dict) -> str | None:
    """Return the supplied overall flag, falling back to detailed rows."""
    overall = dataset_results["overall"]
    if overall is not None:
        return overall["flag"]

    return _worst_flag(
        values["flag"]
        for train_results in dataset_results["comparisons"].values()
        for test_results in train_results.values()
        for values in test_results.values()
    )


def filter_split_datasets_by_qc(
    record_id: str,
    check: str | list[str] | None = None,
    flag: str | list[str] = "Pass",
    force: bool = False,
) -> dict[str, list[str]]:
    """Filter datasets using their supplied overall split-QC flag."""
    results = load_split_qc_results(record_id, force=force)
    _validate_checks(results, check)
    selected_flags = {flag} if isinstance(flag, str) else set(flag)

    matching = {}
    for collection_name, collection_results in results.items():
        datasets = [
            dataset_name
            for dataset_name, dataset_results in collection_results.items()
            if _overall_flag(dataset_results) in selected_flags
        ]
        if datasets:
            matching[collection_name] = sorted(datasets)

    return matching


def plot_split_qc_summary(
    record_id: str,
    check: str | None = None,
    force: bool = False,
):
    """Plot the supplied overall split-QC flags for each collection."""
    results = load_split_qc_results(record_id, force=force)
    _validate_checks(results, check)

    rows = []
    for collection_name, collection_results in results.items():
        counts = {"Pass": 0, "Warning": 0, "Fail": 0, "Unknown": 0}
        for dataset_results in collection_results.values():
            flag = _overall_flag(dataset_results)
            if flag is not None:
                counts[flag] += 1

        total = sum(counts.values())
        if total:
            rows.append({
                "collection": collection_name,
                **{flag: count / total for flag, count in counts.items()},
            })

    title = "Split QC summary"
    if check is not None:
        title += f": {check}"
    return _plot_flag_summary(rows, title)
