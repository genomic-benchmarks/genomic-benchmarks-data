import logging
from pathlib import Path
from urllib.parse import urlparse

import requests
from platformdirs import user_cache_dir
from tqdm import tqdm
import shutil
import zipfile
import pandas as pd
import matplotlib.pyplot as plt

from .metadata import _get_dataset

logger = logging.getLogger(__name__)


_PACKAGE_NAME = __package__.split(".")[0]


_QC_ZENODO_RECORD_ID = "21915933"
_QC_ZENODO_BASE_URL = (f"https://zenodo.org/records/{_QC_ZENODO_RECORD_ID}/files")
_QC_CSV_URLS = {
    "split": (
        f"{_QC_ZENODO_BASE_URL}/"
        "combined_qc_results_splits.csv?download=1"
    ),
    "class": (
        f"{_QC_ZENODO_BASE_URL}/"
        "combined_qc_results_classes.csv?download=1"
    ),
}


def _download_qc_file(
    url: str,
    destination: Path,
    force: bool = False,
) -> Path:
    """Download a QC file to the user cache and return its path."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not force:
        return destination

    with requests.get(url, stream=True) as response:
        response.raise_for_status()

        total = int(response.headers.get("content-length", 0))

        with (
            destination.open("wb") as f,
            tqdm(
                total=total,
                unit="B",
                unit_scale=True,
                desc=destination.name,
            ) as progress,
        ):
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    progress.update(len(chunk))

    return destination


def download_qc_csv(
    qc_type: str,
    force: bool = False,
) -> Path:
    """Download a combined QC results CSV and return its local path."""
    try:
        url = _QC_CSV_URLS[qc_type]
    except KeyError:
        raise ValueError(
            f"Unknown QC type {qc_type!r}. "
            f"Expected one of {sorted(_QC_CSV_URLS)}."
        ) from None

    filename = Path(urlparse(url).path).name

    destination = (
        Path(user_cache_dir(_PACKAGE_NAME))
        / "qc"
        / "combined_results"
        / filename
    )

    return _download_qc_file(
        url=url,
        destination=destination,
        force=force,
    )


def _get_qc_report_dir(
    collection: str,
    dataset_name: str,
    force: bool = False,
) -> Path:
    """Ensure dataset QC reports are cached and return their directory."""
    filename = f"{collection}-{dataset_name}.zip"
    url = f"{_QC_ZENODO_BASE_URL}/{filename}?download=1"

    cache_dir = (
        Path(user_cache_dir(_PACKAGE_NAME))
        / "qc"
        / "reports"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    archive_path = cache_dir / filename
    report_dir = cache_dir / collection / dataset_name

    # Reuse already-extracted reports unless explicitly refreshed.
    if report_dir.exists() and not force:
        logger.debug("Using cached QC reports: %s", report_dir)
        return report_dir

    if force and report_dir.exists():
        shutil.rmtree(report_dir)

    if not archive_path.exists() or force:
        logger.info(
            "Downloading QC reports for %s/%s",
            collection,
            dataset_name,
        )

        _download_qc_file(
            url=url,
            destination=archive_path,
            force=force,
        )

    logger.info(
        "Extracting QC reports for %s/%s",
        collection,
        dataset_name,
    )

    with zipfile.ZipFile(archive_path, "r") as zip_ref:
        zip_ref.extractall(cache_dir)

    if not report_dir.exists():
        raise FileNotFoundError(
            f"Expected QC report directory not found after extraction: "
            f"{report_dir}"
        )

    return report_dir


def get_split_qc_report(
    collection: str,
    dataset_name: str,
    split_a: str,
    split_b: str,
    force: bool = False,
) -> Path:
    """Return the QC report comparing two dataset splits."""
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
        collection,
        dataset_name,
        force=force,
    )

    report = report_dir / "split" / f"{split_a}_{split_b}.html"

    # Split-pair filenames may use either ordering.
    if not report.exists():
        report = report_dir / "split" / f"{split_b}_{split_a}.html"

    if not report.exists():
        raise FileNotFoundError(
            f"No split QC report found for {split_a!r} and {split_b!r} "
            f"in {collection!r}/{dataset_name!r}."
        )

    logger.info(
        "QC report available at %s. Open it in a web browser to view it.",
        report,
    )

    return report


def get_class_qc_report(
    collection: str,
    dataset_name: str,
    split: str,
    seq_col: str,
    force: bool = False,
) -> Path:
    """Return the class QC report for a split and sequence column."""
    dataset = _get_dataset(collection, dataset_name)

    available_splits = set(dataset.get("splits") or [])
    if split not in available_splits:
        raise KeyError(
            f"Split {split!r} not found for dataset {dataset_name!r}."
        )

    available_seq_cols = set(dataset.get("seq_col") or [])
    if seq_col not in available_seq_cols:
        raise KeyError(
            f"Sequence column {seq_col!r} not found for "
            f"dataset {dataset_name!r}."
        )

    report_dir = _get_qc_report_dir(
        collection,
        dataset_name,
        force=force,
    )

    report = (
        report_dir
        / "class"
        / split
        / f"{seq_col}.html"
    )

    if not report.exists():
        raise FileNotFoundError(
            f"No class QC report found for {collection!r}/{dataset_name!r}, "
            f"split {split!r}, sequence column {seq_col!r}."
        )

    logger.info(
        "QC report available at %s. Open it in a web browser to view it.",
        report,
    )

    return report


def _clean_qc_value(value):
    """Convert pandas missing values to None."""
    return None if pd.isna(value) else value


def _parse_class_qc(df: pd.DataFrame) -> dict:
    """Parse combined class QC results into a nested dictionary."""
    results = {}

    for row in df.itertuples(index=False):
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


def _parse_split_qc(df: pd.DataFrame) -> dict:
    """Parse combined split QC results into a nested dictionary."""
    results = {}

    for row in df.itertuples(index=False):
        check_results = {
            "flag": _clean_qc_value(row.flag),
            "statistic": _clean_qc_value(row.statistic),
            "percentage_of_leaked_queries": _clean_qc_value(
                row.percentage_of_leaked_queries
            ),
            "percentage_of_leaked_targets": _clean_qc_value(
                row.percentage_of_leaked_targets
            ),
        }

        (
            results
            .setdefault(row.collection, {})
            .setdefault(row.dataset_name, {})
            .setdefault(row.train_split, {})
            .setdefault(row.test_split, {})
        )[row.check] = check_results

    return results


def load_qc_results(
    qc_type: str,
    force: bool = False,
) -> dict:
    """Download and load combined QC results into a nested dictionary."""
    path = download_qc_csv(qc_type, force=force)
    df = pd.read_csv(path)

    if qc_type == "class":
        return _parse_class_qc(df)

    if qc_type == "split":
        return _parse_split_qc(df)

    raise ValueError(
        f"Unknown QC type {qc_type!r}. "
        "Expected 'class' or 'split'."
    )

def _get_qc_metrics(
    results: dict,
    qc_type: str,
) -> list[str]:
    """Return available QC checks from already-loaded results."""
    checks = set()

    if qc_type == "class":
        for collection in results.values():
            for dataset in collection.values():
                for split in dataset.values():
                    checks.update(split.keys())

    elif qc_type == "split":
        for collection in results.values():
            for dataset in collection.values():
                for train_split in dataset.values():
                    for test_split in train_split.values():
                        checks.update(test_split.keys())

    else:
        raise ValueError(
            f"Unknown QC type {qc_type!r}. "
            "Expected 'class' or 'split'."
        )

    return sorted(checks)


def list_qc_metrics(
    qc_type: str,
    force: bool = False,
) -> list[str]:
    """Download QC results if needed and return available QC checks."""
    results = load_qc_results(qc_type, force=force)

    return _get_qc_metrics(results, qc_type)


def filter_datasets_by_qc(
    qc_type: str,
    check: str | list[str] | None = None,
    flag: str | list[str] = "Pass",
    force: bool = False,
) -> dict[str, list[str]]:
    """Return datasets matching the requested QC checks and flags.

    A dataset is returned only if all relevant QC results for the
    requested checks have one of the requested flags.

    Args:
        qc_type: QC result type, either ``"class"`` or ``"split"``.
        check: QC check or checks to filter on. If None, all available
            checks are considered.
        flag: Required QC flag or flags. Defaults to ``"Pass"``.
        force: Force redownload of the combined QC results CSV.

    Returns:
        Dictionary mapping collection names to matching dataset names.
    """
    results = load_qc_results(qc_type, force=force)

    if check is None:
        selected_checks = None
    elif isinstance(check, str):
        selected_checks = {check}
    else:
        selected_checks = set(check)

    if isinstance(flag, str):
        selected_flags = {flag}
    else:
        selected_flags = set(flag)

    # Validate requested checks using the already-loaded results.
    if selected_checks is not None:
        available_checks = set(_get_qc_metrics(results, qc_type))
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
            result_flags = []

            if qc_type == "class":
                # Class QC is evaluated independently for each split.
                for split_results in dataset_results.values():
                    for check_name, values in split_results.items():
                        if (
                            selected_checks is None
                            or check_name in selected_checks
                        ):
                            result_flags.append(values["flag"])

            elif qc_type == "split":
                # Split QC is evaluated for each pair of dataset splits.
                for train_results in dataset_results.values():
                    for test_results in train_results.values():
                        for check_name, values in test_results.items():
                            if (
                                selected_checks is None
                                or check_name in selected_checks
                            ):
                                result_flags.append(values["flag"])

            else:
                raise ValueError(
                    f"Unknown QC type {qc_type!r}. "
                    "Expected 'class' or 'split'."
                )

            # Require at least one matching QC result, and require every
            # relevant result to have one of the requested flags.
            if result_flags and all(
                result_flag in selected_flags
                for result_flag in result_flags
            ):
                matching_datasets.append(dataset_name)

        if matching_datasets:
            matching[collection_name] = sorted(matching_datasets)

    return matching

_FLAG_RANK = {
    "Pass": 0,
    "Warning": 1,
    "Fail": 2,
}


def _dataset_qc_flag(
    dataset_results: dict,
    qc_type: str,
    check: str | None = None,
) -> str | None:
    """Return the worst QC flag for a dataset."""
    flags = []

    if qc_type == "class":
        for split_results in dataset_results.values():
            for check_name, values in split_results.items():
                if check is None or check_name == check:
                    flags.append(values["flag"])

    elif qc_type == "split":
        for train_results in dataset_results.values():
            for test_results in train_results.values():
                for check_name, values in test_results.items():
                    if check is None or check_name == check:
                        flags.append(values["flag"])

    else:
        raise ValueError(
            f"Unknown QC type {qc_type!r}. "
            "Expected 'class' or 'split'."
        )

    flags = [flag for flag in flags if flag is not None]

    if not flags:
        return None

    return max(flags, key=lambda flag: _FLAG_RANK[flag])

FAIL_COLOR = "#c62828"
WARN_COLOR = "#f57f17"
PASS_COLOR = "#2e7d32"

def plot_qc_summary(
    qc_type: str,
    check: str | None = None,
    force: bool = False,
):
    """Plot the proportion of datasets by QC flag for each collection."""
    results = load_qc_results(qc_type, force=force)

    if check is not None:
        available_checks = set(_get_qc_metrics(results, qc_type))

        if check not in available_checks:
            raise ValueError(
                f"Unknown QC check {check!r}. "
                f"Available checks: {sorted(available_checks)}."
            )

    rows = []

    for collection_name, collection_results in results.items():
        counts = {
            "Pass": 0,
            "Warning": 0,
            "Fail": 0,
        }

        for dataset_results in collection_results.values():
            flag = _dataset_qc_flag(
                dataset_results,
                qc_type,
                check=check,
            )

            if flag is not None:
                counts[flag] += 1

        total = sum(counts.values())

        if total == 0:
            continue

        rows.append({
            "collection": collection_name,
            "Pass": counts["Pass"] / total,
            "Warning": counts["Warning"] / total,
            "Fail": counts["Fail"] / total,
        })

    if not rows:
        raise ValueError("No QC results available to plot.")

    summary = pd.DataFrame(rows).set_index("collection")

    ax = summary.plot(
        kind="bar",
        stacked=True,
        color={
            "Pass": PASS_COLOR,
            "Warning": WARN_COLOR,
            "Fail": FAIL_COLOR,
        },
    )

    ax.set_xlabel("Collection")
    ax.set_ylabel("Proportion of datasets")
    ax.set_ylim(0, 1)

    title = f"{qc_type.capitalize()} QC summary"
    if check is not None:
        title += f": {check}"

    ax.set_title(title)
    ax.legend(title="QC flag")

    return ax
