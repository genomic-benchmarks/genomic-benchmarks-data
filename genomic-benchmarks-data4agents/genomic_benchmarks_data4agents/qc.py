"""Public QC API for genomic-benchmarks-data4agents."""

from ._core.qc import (
    download_class_qc_csv,
    download_split_qc_csv,
    filter_class_datasets_by_qc,
    filter_split_datasets_by_qc,
    get_class_qc_report as _get_class_qc_report,
    get_split_qc_report as _get_split_qc_report,
    list_class_qc_metrics,
    list_split_qc_metrics,
    load_class_qc_results,
    load_split_qc_results,
    plot_class_qc_summary,
    plot_split_qc_summary,
)
from ._qc_config import (
    QC_CLASS_REPORT_SPLITS,
    QC_SPLIT_REPORT_PAIRS,
    QC_ZENODO_RECORD_ID,
)


def _record_id() -> str:
    if not QC_ZENODO_RECORD_ID:
        raise RuntimeError(
            "The agents-package QC Zenodo record has not been configured."
        )
    return QC_ZENODO_RECORD_ID


def _qc_function(qc_type: str, class_function, split_function):
    if qc_type == "class":
        return class_function
    if qc_type == "split":
        return split_function
    raise ValueError(
        f"Unknown QC type {qc_type!r}. Expected 'class' or 'split'."
    )


def download_qc_csv(qc_type: str, force: bool = False):
    function = _qc_function(
        qc_type,
        download_class_qc_csv,
        download_split_qc_csv,
    )
    return function(_record_id(), force=force)


def load_qc_results(qc_type: str, force: bool = False) -> dict:
    function = _qc_function(
        qc_type,
        load_class_qc_results,
        load_split_qc_results,
    )
    return function(_record_id(), force=force)


def list_qc_metrics(qc_type: str, force: bool = False) -> list[str]:
    function = _qc_function(
        qc_type,
        list_class_qc_metrics,
        list_split_qc_metrics,
    )
    return function(_record_id(), force=force)


def filter_datasets_by_qc(
    qc_type: str,
    check: str | list[str] | None = None,
    flag: str | list[str] = "Pass",
    force: bool = False,
) -> dict[str, list[str]]:
    function = _qc_function(
        qc_type,
        filter_class_datasets_by_qc,
        filter_split_datasets_by_qc,
    )
    return function(_record_id(), check=check, flag=flag, force=force)


def plot_qc_summary(
    qc_type: str,
    check: str | None = None,
    force: bool = False,
):
    function = _qc_function(
        qc_type,
        plot_class_qc_summary,
        plot_split_qc_summary,
    )
    return function(_record_id(), check=check, force=force)


def get_class_qc_report(
    collection: str,
    dataset_name: str,
    split: str,
    seq_col: str,
    force: bool = False,
):
    return _get_class_qc_report(
        _record_id(),
        collection,
        dataset_name,
        split,
        seq_col,
        force=force,
        allowed_report_splits=QC_CLASS_REPORT_SPLITS,
    )


def get_split_qc_report(
    collection: str,
    dataset_name: str,
    split_a: str,
    split_b: str,
    force: bool = False,
):
    return _get_split_qc_report(
        _record_id(),
        collection,
        dataset_name,
        split_a,
        split_b,
        force=force,
        allowed_report_pairs=QC_SPLIT_REPORT_PAIRS,
    )
