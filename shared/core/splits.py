import logging
from abc import ABC, abstractmethod
import hashlib
from pathlib import Path
import shutil
import zipfile

import numpy as np
import pandas as pd
import requests
from platformdirs import user_cache_dir
from sklearn.model_selection import train_test_split
from tqdm import tqdm

logger = logging.getLogger(__name__)

_PACKAGE_NAME = __package__.split(".")[0]

HOMOLOGY_MAP_URL = (
    "https://zenodo.org/records/13910050/files/"
    "homology_maps_homologene.zip"
)

HOMOLOGY_MAP_SHA256 = (
    "7f88f7ccea03ca144237caa00e0514da"
    "6ebc5ea1a7349373b894d8d6d745e521"
)


def _sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _download_homology_maps(
    species: str,
    force: bool = False,
) -> Path:
    """Download and extract homology maps to the user cache."""
    cache_dir = (
        Path(user_cache_dir(_PACKAGE_NAME))
        / "resources"
        / "homology_maps"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    archive_path = cache_dir / "homology_maps_homologene.zip"
    homology_map = cache_dir / f"{species}_homology_map.csv"

    # Download the archive if it is missing, invalid, or explicitly refreshed.
    needs_download = (
        force
        or not archive_path.exists()
        or _sha256(archive_path) != HOMOLOGY_MAP_SHA256
    )

    if not needs_download:
        logger.debug(
            "Using cached homology map archive: %s",
            archive_path,
        )

    if needs_download:
        if archive_path.exists():
            if force:
                logger.debug(
                    "Replacing cached homology map archive due to forced refresh: %s",
                    archive_path,
                )
            else:
                logger.warning(
                    "Cached homology map archive failed checksum validation "
                    "and will be replaced: %s",
                    archive_path,
                )

            archive_path.unlink()

        logger.info(
            "Downloading homology map archive from %s",
            HOMOLOGY_MAP_URL,
        )
        with requests.get(HOMOLOGY_MAP_URL, stream=True) as response:
            response.raise_for_status()

            total = int(response.headers.get("content-length", 0))

            with (
                archive_path.open("wb") as f,
                tqdm(
                    total=total,
                    unit="B",
                    unit_scale=True,
                    desc=archive_path.name,
                ) as progress,
            ):
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        progress.update(len(chunk))

        if _sha256(archive_path) != HOMOLOGY_MAP_SHA256:
            archive_path.unlink()
            raise ValueError(
                "Checksum mismatch for homology map archive."
            )

        logger.info(
            "Downloaded homology map archive to %s",
            archive_path,
        )

    if not force and homology_map.exists():
        logger.debug(
            "Using cached homology map for species %r: %s",
            species,
            homology_map,
        )

    # Extract the archive if the required species map is not available.
    if force or not homology_map.exists():
        logger.info(
            "Extracting homology maps from %s",
            archive_path,
        )
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            for file in zip_ref.namelist():
                if not file.endswith("/"):
                    source = zip_ref.open(file)
                    destination = cache_dir / Path(file).name

                    with destination.open("wb") as target:
                        shutil.copyfileobj(source, target)

    if not homology_map.exists():
        raise FileNotFoundError(
            f"Homology map for species {species!r} "
            "was not found in the archive."
        )

    logger.debug(
        "Homology map available for species %r: %s",
        species,
        homology_map,
    )

    return cache_dir


class DataSplitter(ABC):
    """Generates reproducible train/test splits."""

    def __init__(
        self,
        default_split_ratio: tuple[float, float, float] = (
            0.7,
            0.15,
            0.15,
        ),
        **kwargs,
    ):
        self.default_split_ratio = default_split_ratio

    @abstractmethod
    def split_df(
        self,
        df: pd.DataFrame,
        test_size: float,
        random_seed: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Split dataframe into train and test dataframes."""
        pass

    def get_all_splits_df(
        self,
        df: pd.DataFrame,
        split_ratios: tuple[float, float, float] | None = None,
        random_seed: int = 2541,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Get train, validation, and test splits from dataframe."""
        if split_ratios is None:
            split_ratios = self.default_split_ratio

        if sum(split_ratios) != 1:
            raise ValueError("Split ratios must sum to 1.")

        tv_split_size = split_ratios[1] + split_ratios[2]

        if tv_split_size == 0:
            return df, pd.DataFrame(), pd.DataFrame()

        test_split_size = split_ratios[2] / tv_split_size

        if split_ratios[0] == 0:
            train_df = pd.DataFrame()
            tv_df = df
        else:
            train_df, tv_df = self.split_df(
                df,
                tv_split_size,
                random_seed,
            )

        if split_ratios[1] == 0:
            return train_df, pd.DataFrame(), tv_df

        if split_ratios[2] == 0:
            return train_df, tv_df, pd.DataFrame()

        val_df, test_df = self.split_df(
            tv_df,
            test_split_size,
            random_seed,
        )

        return train_df, val_df, test_df


class SklearnSplitter(DataSplitter):
    """Wrapper for sklearn train_test_split."""

    def split_df(
        self,
        df: pd.DataFrame,
        test_size: float,
        random_seed: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        return train_test_split(
            df,
            test_size=test_size,
            random_state=random_seed,
        )


def train_test_split_homologous(
    genes: list[str],
    homology_df: pd.DataFrame,
    test_size: float = 0.3,
    random_state: int | None = None,
) -> tuple[list[int], list[int]]:
    """Split genes while keeping homologous genes in the same split."""
    homo_group_map = (
        homology_df
        .set_index("gene_name")["gene_group"]
        .to_dict()
    )

    gene_groups = np.array([
        homo_group_map.get(gene, None)
        for gene in genes
    ])

    group_to_index: dict[int, list[int]] = {}

    for i, group in enumerate(gene_groups):
        if group is not None:
            group_to_index.setdefault(group, []).append(i)

    gene_index = np.arange(len(genes))

    np.random.seed(random_state)
    np.random.shuffle(gene_index)

    len_of_train = int(len(gene_index) * (1 - test_size))

    train_indices: list[int] = []
    test_indices: list[int] = []

    seen_groups = set()

    for index in gene_index:
        group = gene_groups[index]

        if group is not None and group in seen_groups:
            continue

        seen_groups.add(group)

        if len(train_indices) < len_of_train:
            train_indices.extend(
                group_to_index.get(group, [int(index)])
            )
        else:
            test_indices.extend(
                group_to_index.get(group, [int(index)])
            )

    train_indices = [int(ind) for ind in train_indices]
    test_indices = [int(ind) for ind in test_indices]

    return train_indices, test_indices


class HomologySplitter(DataSplitter):
    """Homology-based data splitter."""

    def __init__(
        self,
        species: str,
        default_split_ratio: tuple[float, float, float] = (
            0.7,
            0.15,
            0.15,
        ),
        force_redownload: bool = False,
        **kwargs,
    ):
        super().__init__(default_split_ratio)

        self.species = [species]

        self.homology_map_path = _download_homology_maps(
            species=species,
            force=force_redownload,
        )

        self.homology_df = self.get_homology_df()

    def get_homology_df(self) -> pd.DataFrame:
        """Get homology dataframe for the specified species."""
        species_maps = []

        for species in self.species:
            homology_map = (
                self.homology_map_path
                / f"{species}_homology_map.csv"
            )

            if not homology_map.exists():
                raise FileNotFoundError(
                    f"Homology map for species "
                    f"{species!r} is missing."
                )

            species_maps.append(pd.read_csv(homology_map))

        max_groups = [
            max(species_df["gene_group"])
            for species_df in species_maps
        ]
        cumulative_max_groups = np.cumsum(max_groups)

        for i, species_df in enumerate(species_maps[1:]):
            species_df["gene_group"] += cumulative_max_groups[i]

        out_df = pd.concat(
            species_maps,
            axis=0,
            ignore_index=True,
        )

        out_df.groupby("gene_name", as_index=False).min()
        out_df.reset_index(drop=True, inplace=True)

        return out_df

    def split_df(
        self,
        df: pd.DataFrame,
        test_size: float,
        random_seed: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Split dataframe while keeping homologous genes together."""
        if "gene" not in df.columns:
            raise ValueError(
                "Gene must be a column for homology split."
            )

        genes = df["gene"].to_list()

        train_indices, test_indices = train_test_split_homologous(
            genes,
            self.homology_df,
            test_size,
            random_seed,
        )

        assert (
            len(set(train_indices).intersection(test_indices)) == 0
        )

        train_df = df.iloc[train_indices]
        test_df = df.iloc[test_indices]

        return train_df, test_df