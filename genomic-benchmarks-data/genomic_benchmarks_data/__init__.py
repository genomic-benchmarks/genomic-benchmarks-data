"""Access to quality-curated genomic benchmark datasets."""

from ._core.data import (
    download_dataset,
    load_dataset,
)
from ._core.identity import write_split
from ._core.metadata import (
    add_local_collection,
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
