import pandas as pd

from ..metadata import _get_dataset
from ..splits import HomologySplitter, SklearnSplitter


SPLIT_TYPE = {
    "mrl-sugimoto": "homology",

    "mrl-sample-egfp-m1pseudo": "default",
    "mrl-sample-egfp-pseudo": "default",
    "mrl-sample-egfp-unmod": "default",

    "mrl-sample-mcherry": "default",
    "mrl-sample-designed": "default",
    "mrl-sample-varying": "default",

    "rnahl-human": "homology",
    "rnahl-mouse": "homology",

    "translation-efficiency-human": "homology",
    "translation-efficiency-mouse": "homology",
}

DATASET_SPECIES = {
    "rnahl-human": "human",
    "rnahl-mouse": "mouse",

    "translation-efficiency-human": "human",
    "translation-efficiency-mouse": "mouse",
}

_EGFP_TARGET_COLUMNS = {
    "target_mrl_egfp_m1pseudo",
    "target_mrl_egfp_pseudo",
    "target_mrl_egfp_unmod",
}


def _make_splits(
    dataset: pd.DataFrame,
    dataset_name: str,
) -> dict[str, pd.DataFrame]:
    """Reproduce the canonical mRNABench train/val/test split."""
    try:
        split_type = SPLIT_TYPE[dataset_name]
    except KeyError:
        raise ValueError(
            f"No split type configured for mRNABench dataset "
            f"{dataset_name!r}."
        ) from None

    if split_type == "default":
        splitter = SklearnSplitter()

    elif split_type == "homology":
        try:
            species = DATASET_SPECIES[dataset_name]
        except KeyError:
            raise ValueError(
                f"No species configured for homology-split dataset "
                f"{dataset_name!r}."
            ) from None

        splitter = HomologySplitter(species=species)

    else:
        raise ValueError(
            f"Unsupported mRNABench split type {split_type!r} "
            f"for dataset {dataset_name!r}."
        )

    train, val, test = splitter.get_all_splits_df(
        dataset,
        split_ratios=(0.7, 0.15, 0.15),
        random_seed=2541,
    )

    return {
        "train": train,
        "val": val,
        "test": test,
    }


def _select_split(
    dataset: pd.DataFrame,
    dataset_name: str,
    split: str,
) -> pd.DataFrame:
    """Return the requested canonical mRNABench split."""
    splits = _make_splits(dataset, dataset_name)

    # Accept validation as an alias even though mRNABench uses "val".
    if split == "validation":
        split = "val"

    try:
        return splits[split]
    except KeyError:
        raise ValueError(f"Unknown split: {split!r}") from None


def _select_task(
    dataset: pd.DataFrame,
    dataset_name: str,
) -> pd.DataFrame:
    """Keep all dataset columns except targets belonging to other logical tasks."""
    metadata = _get_dataset("mRNABench", dataset_name)
    label_col = metadata["label_col"]

    if dataset_name.startswith("mrl-sample-egfp-"):
        drop_cols = _EGFP_TARGET_COLUMNS - {label_col}

        return dataset.drop(
            columns=[col for col in drop_cols if col in dataset.columns]
        ).copy()

    return dataset.copy()


def prepare_dataset(
    dataset: pd.DataFrame,
    dataset_name: str,
    split: str,
) -> pd.DataFrame:
    """Prepare a requested mRNABench logical dataset and split."""
    dataset = _select_split(dataset, dataset_name, split)
    dataset = _select_task(dataset, dataset_name)

    return dataset