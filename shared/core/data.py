import hashlib
import logging
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse

import pandas as pd
import requests
from platformdirs import user_cache_dir
from tqdm import tqdm

from .identity import write_split
from .metadata import _get_dataset, _local_collection_folder

logger = logging.getLogger(__name__)

# The shared core is bundled under either genomic_benchmarks_data
# or genomic_benchmarks_data4agents. Using the parent package name
# keeps their caches separate.
_PACKAGE_NAME = __package__.split(".")[0]

# Only prepared copies of these non-redistributable sources may be cached.
_COLLECTIONS_REQUIRING_GENERATED_IDS = frozenset({"nucleotide_benchmarks"})
_TEST_SPLITS = frozenset({"test", "test_leftout"})
_LOAD_COLUMN_MODES = frozenset({"default", "all"})


def _cache_component(value: str, field: str) -> str:
    """Return a metadata value that is safe to use as one path component."""
    value = str(value)

    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(
            f"Cannot use {field} {value!r} in the dataset cache path."
        )

    return value


def _sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""
    digest = hashlib.sha256()

    # Read in chunks to avoid loading large datasets into memory.
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _prepared_checksum_path(destination: Path) -> Path:
    """Return the local checksum sidecar path for a prepared dataset."""
    return destination.with_name(f"{destination.name}.sha256")


def _prepared_cache_is_valid(destination: Path) -> bool:
    """Return whether a prepared file matches its local checksum sidecar."""
    checksum_path = _prepared_checksum_path(destination)
    if not destination.is_file() or not checksum_path.is_file():
        return False

    try:
        expected = checksum_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return False

    if len(expected) != 64 or any(
        character not in "0123456789abcdef" for character in expected
    ):
        return False

    return _sha256(destination) == expected


def _stream_source_to_temporary_file(
    url: str,
    source_file,
    filename: str,
) -> str:
    """Download a source into an already-open temporary file."""
    digest = hashlib.sha256()

    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))

        with tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            desc=filename,
        ) as progress:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    source_file.write(chunk)
                    digest.update(chunk)
                    progress.update(len(chunk))

    return digest.hexdigest()


def _download_and_prepare_dataset(
    *,
    collection: str,
    dataset_name: str,
    major_version: str,
    split: str,
    url: str,
    expected_sha256: str,
    filename: str,
    cache_dir: Path,
    destination: Path,
    force: bool,
) -> Path:
    """Cache an ID-enriched copy without persisting the source file."""
    checksum_path = _prepared_checksum_path(destination)

    if not force:
        if _prepared_cache_is_valid(destination):
            logger.debug("Using cached prepared dataset file: %s", destination)
            return destination

        if destination.exists() or checksum_path.exists():
            logger.warning(
                "Prepared cache is incomplete or failed checksum validation "
                "and will be replaced: %s",
                destination,
            )

    prepared_path = None
    prepared_checksum_path = None

    try:
        # TemporaryFile is removed automatically when closed, so the original
        # four-column source is never left in the package-managed cache.
        with tempfile.TemporaryFile(mode="w+b", dir=cache_dir) as source_file:
            actual_sha256 = _stream_source_to_temporary_file(
                url,
                source_file,
                filename,
            )
            if actual_sha256 != expected_sha256:
                raise ValueError(
                    f"Checksum mismatch for {dataset_name!r} split {split!r}. "
                    "The downloaded file does not match the version described "
                    "by the package metadata."
                )

            source_file.seek(0)
            source_dataset = pd.read_parquet(source_file)

        prepared_fd, prepared_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=cache_dir,
        )
        os.close(prepared_fd)
        prepared_path = Path(prepared_name)
        write_split(
            source_dataset,
            prepared_path,
            collection,
            dataset_name,
            split,
            major_version,
            name=destination.name,
        )

        prepared_sha256 = _sha256(prepared_path)
        checksum_fd, checksum_name = tempfile.mkstemp(
            prefix=f".{destination.name}.sha256.",
            suffix=".tmp",
            dir=cache_dir,
        )
        prepared_checksum_path = Path(checksum_name)
        with os.fdopen(checksum_fd, "w", encoding="ascii") as checksum_file:
            checksum_file.write(f"{prepared_sha256}\n")

        os.replace(prepared_path, destination)
        prepared_path = None
        os.replace(prepared_checksum_path, checksum_path)
        prepared_checksum_path = None
    finally:
        if prepared_path is not None:
            prepared_path.unlink(missing_ok=True)
        if prepared_checksum_path is not None:
            prepared_checksum_path.unlink(missing_ok=True)

    logger.info("Downloaded and prepared dataset file at %s", destination)
    return destination


def download_dataset(
    collection: str,
    dataset_name: str,
    split: str,
    force: bool = False,
) -> Path:
    """Download a dataset split to the user cache and return its path.

    A split of a local collection is not copied: its path in the collection's
    folder is returned, after a check against the metadata.
    """
    dataset = _get_dataset(collection, dataset_name)
    split_metadata = dataset.get("split_metadata") or {}

    if split not in split_metadata:
        raise KeyError(
            f"Split {split!r} not found for dataset {dataset_name!r}."
        )

    info = split_metadata[split]
    url = info["dataset_url"]
    expected_sha256 = info["sha256"]
    major_version = dataset["major_version"]

    filename = _cache_component(
        Path(urlparse(url).path).name,
        "dataset filename",
    )

    local_folder = _local_collection_folder(collection)
    if local_folder is not None:
        path = local_folder / filename
        if not path.is_file():
            raise FileNotFoundError(
                f"Split {split!r} of {dataset_name!r} is missing from the "
                f"local collection: {path}"
            )
        if _sha256(path) != expected_sha256:
            raise ValueError(
                f"Checksum mismatch for {dataset_name!r} split {split!r}. "
                f"The local file {path} does not match the version described "
                "by the collection metadata."
            )
        return path

    # Keep the cache human-readable while retaining the source checksum as the
    # exact artifact identity. Dataset major_version comes from metadata and is
    # also the version encoded in sequence IDs.
    cache_dir = (
        Path(user_cache_dir(_PACKAGE_NAME))
        / "data"
        / _cache_component(collection, "collection")
        / _cache_component(dataset_name, "dataset_name")
        / _cache_component(major_version, "major_version")
        / _cache_component(split, "split")
        / _cache_component(expected_sha256, "sha256")
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    if collection in _COLLECTIONS_REQUIRING_GENERATED_IDS:
        prepared_filename = f"{Path(filename).stem}.csv.gz"
        destination = cache_dir / prepared_filename

        return _download_and_prepare_dataset(
            collection=collection,
            dataset_name=dataset_name,
            major_version=major_version,
            split=split,
            url=url,
            expected_sha256=expected_sha256,
            filename=filename,
            cache_dir=cache_dir,
            destination=destination,
            force=force,
        )

    destination = cache_dir / filename

    # The checksum in the packaged metadata defines the exact file expected
    # by this package. Reuse a cached copy only if its contents still match.
    if destination.exists() and not force:
        if _sha256(destination) == expected_sha256:
            logger.debug("Using cached dataset file: %s", destination)
            return destination

        logger.warning(
            "Cached file failed checksum validation and will be replaced: %s",
            destination,
        )
        destination.unlink()

    # Stream the download so large datasets are not loaded into memory.
    with requests.get(url, stream=True) as response:
        response.raise_for_status()

        total = int(response.headers.get("content-length", 0))

        with (
            destination.open("wb") as f,
            tqdm(
                total=total,
                unit="B",
                unit_scale=True,
                desc=filename,
            ) as progress,
        ):
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    progress.update(len(chunk))

    # If the upstream file changes without a corresponding metadata update,
    # reject it rather than exposing data inconsistent with the metadata.
    if _sha256(destination) != expected_sha256:
        destination.unlink()
        raise ValueError(
            f"Checksum mismatch for {dataset_name!r} split {split!r}. "
            "The downloaded file does not match the version described "
            "by the package metadata."
        )

    logger.info("Downloaded dataset file to %s", destination)

    return destination


def load_dataset(
    collection: str,
    dataset_name: str,
    split: str,
    columns: str = "default",
) -> pd.DataFrame:
    """Load a dataset split, selecting task columns unless all are requested."""
    if columns not in _LOAD_COLUMN_MODES:
        raise ValueError(
            f"Unknown columns mode {columns!r}. Expected 'default' or 'all'."
        )

    metadata = _get_dataset(collection, dataset_name)
    path = download_dataset(collection, dataset_name, split)

    selected_columns = None
    if columns == "default":
        seq_columns = metadata.get("seq_col") or []
        if isinstance(seq_columns, str):
            seq_columns = [seq_columns]

        label_columns = metadata.get("label_col") or []
        if isinstance(label_columns, str):
            label_columns = [label_columns]

        selected_columns = [
            *(["id", "row_index"] if split in _TEST_SPLITS else []),
            *seq_columns,
            *label_columns,
        ]
        # Preserve the defined order while avoiding duplicate columns.
        selected_columns = list(dict.fromkeys(selected_columns))

    suffixes = path.suffixes

    if ".parquet" in suffixes:
        dataset = pd.read_parquet(
            path,
            columns=selected_columns or None,
        )

    elif ".tsv" in suffixes:
        dataset = pd.read_csv(
            path,
            sep="\t",
            usecols=selected_columns or None,
        )

    elif ".csv" in suffixes:
        dataset = pd.read_csv(
            path,
            usecols=selected_columns or None,
        )

    else:
        raise ValueError(
            f"Unsupported dataset format: {path.name}"
        )

    if selected_columns is not None:
        dataset = dataset.loc[:, selected_columns]

    return dataset
