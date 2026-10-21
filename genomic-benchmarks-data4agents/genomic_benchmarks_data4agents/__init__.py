"""Access to quality-curated genomic benchmark datasets for agents."""

from pathlib import Path

from ._core.data import (
    _TEST_SPLITS,
    download_dataset,
    load_dataset,
)
from ._core.identity import write_split
from ._core.metadata import (
    add_local_collection as _add_local_collection,
    get_dataset_info,
    get_split_info,
    list_collections,
    list_dataset_filters,
    list_datasets,
    list_molecular_levels,
    list_species,
    list_task_categories,
    list_task_types,
    load_metadata,
)
from ._core.presentation import pretty
from .qc import (
    download_qc_csv,
    filter_datasets_by_qc,
    get_class_qc_results,
    get_class_qc_report,
    get_split_qc_results,
    get_split_qc_report,
    list_qc_metrics,
    load_all_qc_results,
    plot_qc_summary,
)


def add_local_collection(path: str | Path) -> str:
    """Make a collection in a local folder available to every function.

    Its ``test`` and ``test_leftout`` splits are left out, as in the packaged
    metadata, and so is a dataset that has no other split. See the full
    package's ``add_local_collection`` for the folder's layout.

    Returns:
        The collection's name.
    """
    return _add_local_collection(path, exclude_splits=_TEST_SPLITS)


__all__ = [
    "add_local_collection",
    "download_dataset",
    "download_qc_csv",
    "filter_datasets_by_qc",
    "get_class_qc_results",
    "get_class_qc_report",
    "get_dataset_info",
    "get_split_info",
    "get_split_qc_results",
    "get_split_qc_report",
    "list_collections",
    "list_dataset_filters",
    "list_datasets",
    "list_molecular_levels",
    "list_qc_metrics",
    "list_species",
    "list_task_categories",
    "list_task_types",
    "load_dataset",
    "load_all_qc_results",
    "load_metadata",
    "plot_qc_summary",
    "pretty",
    "write_split",
]
