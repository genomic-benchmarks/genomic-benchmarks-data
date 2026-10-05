"""Public class-QC API for genomic-benchmarks-data4agents."""

from ._core.qc import (
    download_class_qc_csv,
    filter_class_datasets_by_qc,
    get_class_qc_report as _get_class_qc_report,
    list_class_qc_metrics,
    load_class_qc_results,
    plot_class_qc_summary,
)
from ._qc_config import QC_CLASS_REPORT_SPLITS, QC_ZENODO_RECORD_ID


def _record_id() -> str:
    if not QC_ZENODO_RECORD_ID:
        raise RuntimeError(
            "The agents-package QC Zenodo record has not been configured."
        )
    return QC_ZENODO_RECORD_ID


def _require_class_qc(qc_type: str) -> None:
    if qc_type != "class":
        raise ValueError(
            f"QC type {qc_type!r} is not available in "
            "genomic-benchmarks-data4agents. Expected 'class'."
        )


def download_qc_csv(qc_type: str, force: bool = False):
    _require_class_qc(qc_type)
    return download_class_qc_csv(_record_id(), force=force)


def load_qc_results(qc_type: str, force: bool = False) -> dict:
    _require_class_qc(qc_type)
    return load_class_qc_results(_record_id(), force=force)


def list_qc_metrics(qc_type: str, force: bool = False) -> list[str]:
    _require_class_qc(qc_type)
    return list_class_qc_metrics(_record_id(), force=force)


def filter_datasets_by_qc(
    qc_type: str,
    check: str | list[str] | None = None,
    flag: str | list[str] = "Pass",
    force: bool = False,
) -> dict[str, list[str]]:
    _require_class_qc(qc_type)
    return filter_class_datasets_by_qc(
        _record_id(),
        check=check,
        flag=flag,
        force=force,
    )


def plot_qc_summary(
    qc_type: str,
    check: str | None = None,
    force: bool = False,
):
    _require_class_qc(qc_type)
    return plot_class_qc_summary(
        _record_id(),
        check=check,
        force=force,
    )


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
