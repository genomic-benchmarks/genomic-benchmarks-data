"""Shared class-QC downloads, parsing, filtering, and plotting."""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests
from platformdirs import user_cache_dir
from tqdm import tqdm

from .metadata import _get_dataset

logger = logging.getLogger(__name__)

_PACKAGE_NAME = __package__.split(".")[0]
_CLASS_RESULTS_FILENAME = "combined_classes_results.csv"

_FLAG_RANK = {
    "Pass": 0,
    "Warning": 1,
    "Fail": 2,
    "Unknown": 3,
}
_FLAG_COLORS = {
    "Pass": "#2e7d32",
    "Warning": "#f57f17",
    "Fail": "#c62828",
    "Unknown": "#757575",
}


def _zenodo_file_url(record_id: str, filename: str) -> str:
    """Return the public download URL for a file in a Zenodo record."""
    return f"https://zenodo.org/records/{record_id}/files/{filename}?download=1"


def _qc_cache_root(record_id: str) -> Path:
    """Return the package- and record-specific QC cache directory."""
    return Path(user_cache_dir(_PACKAGE_NAME)) / "qc" / record_id


def _download_qc_file(
    record_id: str,
    filename: str,
    destination: Path,
    force: bool = False,
) -> Path:
    """Download one QC artifact to the package cache."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not force:
        return destination

    url = _zenodo_file_url(record_id, filename)
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))

        with (
            destination.open("wb") as output,
            tqdm(
                total=total,
                unit="B",
                unit_scale=True,
                desc=filename,
            ) as progress,
        ):
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
                    progress.update(len(chunk))

    return destination


def _download_qc_csv(
    record_id: str,
    filename: str,
    force: bool = False,
) -> Path:
    """Download a combined QC CSV and return its cached path."""
    destination = _qc_cache_root(record_id) / "combined_results" / filename
    return _download_qc_file(record_id, filename, destination, force=force)


def _get_qc_report_dir(
    record_id: str,
    collection: str,
    dataset_name: str,
    force: bool = False,
) -> Path:
    """Ensure one dataset's report archive is extracted and return its root."""
    filename = f"{collection}-{dataset_name}.zip"
    cache_dir = _qc_cache_root(record_id) / "reports"
    cache_dir.mkdir(parents=True, exist_ok=True)

    archive_path = cache_dir / filename
    report_dir = cache_dir / f"{collection}-{dataset_name}"

    if report_dir.exists() and not force:
        logger.debug("Using cached QC reports: %s", report_dir)
        return report_dir

    if force and report_dir.exists():
        shutil.rmtree(report_dir)

    if not archive_path.exists() or force:
        logger.info("Downloading QC reports for %s/%s", collection, dataset_name)
        _download_qc_file(
            record_id,
            filename,
            archive_path,
            force=force,
        )

    logger.info("Extracting QC reports for %s/%s", collection, dataset_name)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(cache_dir)

    if not report_dir.exists():
        raise FileNotFoundError(
            f"Expected QC report directory not found after extraction: "
            f"{report_dir}"
        )

    return report_dir


def download_class_qc_csv(
    record_id: str,
    force: bool = False,
) -> Path:
    """Download the combined class-QC results CSV."""
    return _download_qc_csv(record_id, _CLASS_RESULTS_FILENAME, force=force)


def get_class_qc_report(
    record_id: str,
    collection: str,
    dataset_name: str,
    split: str,
    seq_col: str,
    force: bool = False,
    allowed_report_splits: frozenset[str] | None = None,
) -> Path:
    """Return the class-QC HTML report for a split and sequence column."""
    dataset = _get_dataset(collection, dataset_name)

    available_splits = set(dataset.get("splits") or [])
    if split not in available_splits:
        raise KeyError(
            f"Split {split!r} not found for dataset {dataset_name!r}."
        )

    if allowed_report_splits is not None and split not in allowed_report_splits:
        raise ValueError(
            f"Class QC HTML reports for {_PACKAGE_NAME!r} are available only "
            f"for splits {sorted(allowed_report_splits)}; got {split!r}."
        )

    available_seq_cols = set(dataset.get("seq_col") or [])
    if seq_col not in available_seq_cols:
        raise KeyError(
            f"Sequence column {seq_col!r} not found for "
            f"dataset {dataset_name!r}."
        )

    report_dir = _get_qc_report_dir(
        record_id,
        collection,
        dataset_name,
        force=force,
    )
    report = report_dir / "class" / split / f"{seq_col}.html"

    if not report.exists():
        raise FileNotFoundError(
            f"No class QC report found for {collection!r}/{dataset_name!r}, "
            f"split {split!r}, sequence column {seq_col!r}."
        )

    logger.info("QC report available at %s", report)
    return report


def _clean_qc_value(value):
    """Convert pandas missing values to None."""
    return None if pd.isna(value) else value


def _parse_class_qc(frame: pd.DataFrame) -> dict:
    """Parse combined class-QC results into a nested dictionary."""
    results = {}

    for row in frame.itertuples(index=False):
        check_results = {
            "flag": _clean_qc_value(row.flag),
            "accuracy": _clean_qc_value(row.accuracy),
            "au_pr": _clean_qc_value(row.au_pr),
            "au_roc": _clean_qc_value(row.au_roc),
        }
        (
            results
            .setdefault(row.collection, {})
            .setdefault(row.dataset_name, {})
            .setdefault(row.split, {})
        )[row.check] = check_results

    return results


def load_class_qc_results(
    record_id: str,
    force: bool = False,
) -> dict:
    """Download and parse combined class-QC results."""
    path = download_class_qc_csv(record_id, force=force)
    return _parse_class_qc(pd.read_csv(path))


def _get_class_qc_metrics(results: dict) -> list[str]:
    """Return the class-QC check names present in parsed results."""
    checks = set()
    for collection in results.values():
        for dataset in collection.values():
            for split in dataset.values():
                checks.update(split.keys())
    return sorted(checks)


def list_class_qc_metrics(
    record_id: str,
    force: bool = False,
) -> list[str]:
    """Return available class-QC check names."""
    return _get_class_qc_metrics(
        load_class_qc_results(record_id, force=force)
    )


def filter_class_datasets_by_qc(
    record_id: str,
    check: str | list[str] | None = None,
    flag: str | list[str] = "Pass",
    force: bool = False,
) -> dict[str, list[str]]:
    """Return datasets whose selected class-QC results have allowed flags."""
    results = load_class_qc_results(record_id, force=force)
    selected_checks = (
        None
        if check is None
        else {check} if isinstance(check, str) else set(check)
    )
    selected_flags = {flag} if isinstance(flag, str) else set(flag)

    if selected_checks is not None:
        available_checks = set(_get_class_qc_metrics(results))
        unknown_checks = selected_checks - available_checks
        if unknown_checks:
            raise ValueError(
                f"Unknown QC check(s): {sorted(unknown_checks)}. "
                f"Available checks: {sorted(available_checks)}."
            )

    matching = {}
    for collection_name, collection_results in results.items():
        matching_datasets = []
        for dataset_name, dataset_results in collection_results.items():
            flags = [
                values["flag"]
                for split_results in dataset_results.values()
                for check_name, values in split_results.items()
                if selected_checks is None or check_name in selected_checks
            ]
            if flags and all(value in selected_flags for value in flags):
                matching_datasets.append(dataset_name)

        if matching_datasets:
            matching[collection_name] = sorted(matching_datasets)

    return matching


def _worst_flag(flags) -> str | None:
    """Return the worst non-null QC flag in an iterable."""
    values = [flag for flag in flags if flag is not None]
    if not values:
        return None
    return max(values, key=lambda value: _FLAG_RANK[value])


def _plot_flag_summary(rows: list[dict], title: str):
    """Plot already-aggregated per-collection QC flag proportions."""
    if not rows:
        raise ValueError("No QC results available to plot.")

    summary = pd.DataFrame(rows).set_index("collection")
    columns = [flag for flag in _FLAG_RANK if flag in summary.columns]
    axis = summary[columns].plot(
        kind="bar",
        stacked=True,
        color={flag: _FLAG_COLORS[flag] for flag in columns},
    )
    axis.set_xlabel("Collection")
    axis.set_ylabel("Proportion of datasets")
    axis.set_ylim(0, 1)
    axis.set_title(title)
    axis.legend(title="QC flag")
    return axis


def plot_class_qc_summary(
    record_id: str,
    check: str | None = None,
    force: bool = False,
):
    """Plot class-QC dataset flags for each collection."""
    results = load_class_qc_results(record_id, force=force)

    if check is not None:
        available_checks = set(_get_class_qc_metrics(results))
        if check not in available_checks:
            raise ValueError(
                f"Unknown QC check {check!r}. "
                f"Available checks: {sorted(available_checks)}."
            )

    rows = []
    for collection_name, collection_results in results.items():
        counts = {flag: 0 for flag in _FLAG_RANK}
        for dataset_results in collection_results.values():
            flag = _worst_flag(
                values["flag"]
                for split_results in dataset_results.values()
                for check_name, values in split_results.items()
                if check is None or check_name == check
            )
            if flag is not None:
                counts[flag] += 1

        total = sum(counts.values())
        if total:
            rows.append({
                "collection": collection_name,
                **{flag: count / total for flag, count in counts.items()},
            })

    title = "Class QC summary"
    if check is not None:
        title += f": {check}"
    return _plot_flag_summary(rows, title)
