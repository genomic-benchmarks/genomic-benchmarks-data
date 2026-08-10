import hashlib
from pathlib import Path
from urllib.parse import urlparse

import requests
from platformdirs import user_cache_dir
from tqdm import tqdm

import pandas as pd

from .metadata import _get_dataset


# The shared core is bundled under either genomic_benchmarks_data
# or genomic_benchmarks_data4agents. Using the parent package name
# keeps their caches separate.
_PACKAGE_NAME = __package__.split(".")[0]


def _sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""
    digest = hashlib.sha256()

    # Read in chunks to avoid loading large datasets into memory.
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def download_dataset(
    collection: str,
    dataset_name: str,
    split: str,
    force: bool = False,
) -> Path:
    """Download a dataset split to the user cache and return its path."""
    dataset = _get_dataset(collection, dataset_name)
    split_metadata = dataset.get("split_metadata") or {}

    if split not in split_metadata:
        raise KeyError(
            f"Split {split!r} not found for dataset {dataset_name!r}."
        )

    info = split_metadata[split]
    url = info["dataset_path"]
    expected_sha256 = info["sha256"]

    filename = Path(urlparse(url).path).name

    # Use the platform-standard cache directory rather than storing
    # downloaded data inside the package or directly under the user's home.
    cache_dir = (
        Path(user_cache_dir(_PACKAGE_NAME))
        / collection
        / dataset_name
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    destination = cache_dir / filename

    # The checksum in the packaged metadata defines the exact dataset
    # version expected by this package. A cached file is reused only
    # when it matches that checksum.
    #
    # If metadata is updated to describe a new dataset version, its
    # checksum changes. The old cached file will then fail this check,
    # be removed, and the new version will be downloaded automatically.
    if destination.exists() and not force:
        if _sha256(destination) == expected_sha256:
            return destination

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

    # Validate every new download against the metadata. If the upstream
    # file changes without a corresponding metadata update, do not keep
    # or expose the unexpected file.
    if _sha256(destination) != expected_sha256:
        destination.unlink()
        raise ValueError(
            f"Checksum mismatch for {dataset_name!r} split {split!r}. "
            "The downloaded file does not match the version described "
            "by the package metadata."
        )

    return destination


def load_dataset(
    collection: str,
    dataset_name: str,
    split: str,
    show_head: bool = False,
) -> pd.DataFrame:
    """Load a dataset split into memory."""
    path = download_dataset(collection, dataset_name, split)

    dataset = pd.read_csv(path)

    if show_head:
        print(dataset.head())

    return dataset


# check dataset specific loading / splits needed if dataset at dataset_path is not a single csv file
