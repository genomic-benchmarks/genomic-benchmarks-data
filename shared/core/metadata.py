import json
from pathlib import Path


# Local collections registered with add_local_collection: the collection name
# mapped to its folder and the splits that the package leaves out.
_LOCAL_COLLECTIONS: dict[str, tuple[Path, frozenset[str]]] = {}


def _load_packaged_metadata() -> dict:
    """Load metadata for the collections included in the package."""
    metadata_dir = Path(__file__).parent.parent / "metadata"

    collections = {}

    for path in sorted(metadata_dir.glob("*_metadata.json")):
        with path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        collections[metadata["collection"]] = metadata

    return collections


def _load_local_metadata(folder: Path, exclude_splits: frozenset[str]) -> dict:
    """Load a local collection's metadata without the excluded splits.

    A dataset left without splits is left out, as in the packaged metadata.
    """
    paths = sorted(folder.glob("*_metadata.json"))
    if len(paths) != 1:
        raise ValueError(
            "A local collection folder must hold exactly one "
            f"'*_metadata.json' file; {folder} holds {len(paths)}."
        )

    with paths[0].open(encoding="utf-8") as f:
        metadata = json.load(f)

    datasets = []
    for dataset in metadata["datasets"]:
        dataset["splits"] = [
            split for split in dataset["splits"] if split not in exclude_splits
        ]
        dataset["split_metadata"] = {
            split: info
            for split, info in (dataset.get("split_metadata") or {}).items()
            if split not in exclude_splits
        }
        if dataset["splits"]:
            datasets.append(dataset)
    metadata["datasets"] = datasets

    return metadata


def add_local_collection(
    path: str | Path,
    exclude_splits: frozenset[str] = frozenset(),
) -> str:
    """Make a collection in a local folder available to every function.

    The folder holds the collection's ``*_metadata.json`` and its split files.
    A split is read from the file that the last component of its
    ``dataset_url`` names, in that folder, after a check against its
    ``sha256``. Registering the same collection again replaces its folder.
    The registration lasts for the running process.

    Args:
        path: The folder of the collection.
        exclude_splits: Splits to leave out of the collection's metadata.

    Returns:
        The collection's name.
    """
    folder = Path(path).resolve()
    exclude_splits = frozenset(exclude_splits)
    name = _load_local_metadata(folder, exclude_splits)["collection"]

    if name in _load_packaged_metadata():
        raise ValueError(
            f"Collection {name!r} is included in the package; a local "
            "collection needs another name."
        )

    _LOCAL_COLLECTIONS[name] = (folder, exclude_splits)

    return name


def _local_collection_folder(collection: str) -> Path | None:
    """Return the folder of a local collection, or None for any other."""
    local = _LOCAL_COLLECTIONS.get(collection)

    return local[0] if local else None


def load_metadata() -> dict:
    """Load metadata for all included and local dataset collections."""
    collections = _load_packaged_metadata()

    for name, (folder, exclude_splits) in _LOCAL_COLLECTIONS.items():
        collections[name] = _load_local_metadata(folder, exclude_splits)

    return collections


def list_collections() -> dict[str, str]:
    """Return available collections and their DOIs."""
    metadata = load_metadata()

    return {
        name: collection["collection_doi"]
        for name, collection in metadata.items()
    }


def list_datasets(
    collection: str | None = None,
    molecular_level: str | None = None,
    task_category: str | None = None,
    task_type: str | None = None,
    species: str | None = None,
    core_set: bool | None = None,
) -> dict[str, dict[str, str]]:
    """Return datasets, optionally filtered by collection and metadata.

    Args:
        collection: Collection name, or ``None`` to search all collections.
        molecular_level: Exact molecular-level value to match.
        task_category: Exact task-category value to match.
        task_type: Exact task-type value to match.
        species: Exact species value to match.
        core_set: ``True`` for core datasets, ``False`` for non-core datasets,
            or ``None`` to include both.

    Use :func:`list_dataset_filters` to discover the currently available
    values for these filters.
    """
    metadata = load_metadata()

    collections = (
        {collection: metadata[collection]}
        if collection is not None
        else metadata
    )

    filters = {
        "molecular_level": molecular_level,
        "task_category": task_category,
        "task_type": task_type,
        "species": species,
        "core_set": core_set,
    }

    # TODO: Support matching individual species in multi-species values
    # (currently encoded as pipe-separated strings).
    result = {}

    for collection_name, collection_data in collections.items():
        datasets = {
            dataset["dataset_name"]: dataset["task_description"]
            for dataset in collection_data["datasets"]
            if all(
                value is None or dataset.get(field) == value
                for field, value in filters.items()
            )
        }

        if datasets:
            result[collection_name] = datasets

    return result


def list_dataset_filters(
    collection: str | None = None,
) -> dict[str, list[str] | list[bool]]:
    """Return values accepted by each ``list_datasets`` filter.

    Args:
        collection: Limit metadata-derived values to one collection. If
            omitted, values are gathered across all available collections.

    Returns:
        Filter names mapped to their available values. ``core_set`` always
        contains the two Boolean choices.
    """
    metadata = load_metadata()
    selected = (
        {collection: metadata[collection]}
        if collection is not None
        else metadata
    )
    fields = (
        "molecular_level",
        "task_category",
        "task_type",
        "species",
    )

    return {
        "collection": sorted(selected),
        **{
            field: sorted({
                dataset[field]
                for collection_data in selected.values()
                for dataset in collection_data["datasets"]
                if dataset.get(field) is not None
            })
            for field in fields
        },
        "core_set": [True, False],
    }


def _list_unique_values(collection: str, field: str) -> list[str]:
    """Return sorted unique non-null values for a dataset field."""
    metadata = load_metadata()
    datasets = metadata[collection]["datasets"]

    return sorted({
        dataset[field]
        for dataset in datasets
        if dataset.get(field) is not None
    })

def list_molecular_levels(collection: str) -> list[str]:
    """Return molecular levels available in a collection."""
    return _list_unique_values(collection, "molecular_level")

def list_task_categories(collection: str) -> list[str]:
    """Return task categories available in a collection."""
    return _list_unique_values(collection, "task_category")

def list_task_types(collection: str) -> list[str]:
    """Return task types available in a collection."""
    return _list_unique_values(collection, "task_type")

def list_species(collection: str) -> list[str]:
    """Return species available in a collection."""
    # TODO: Split pipe-separated multi-species values into individual species.
    return _list_unique_values(collection, "species")


def _get_dataset(collection: str, dataset_name: str) -> dict:
    """Return a dataset entry from a collection."""
    metadata = load_metadata()

    for dataset in metadata[collection]["datasets"]:
        if dataset["dataset_name"] == dataset_name:
            return dataset

    raise KeyError(
        f"Dataset {dataset_name!r} not found in collection {collection!r}."
    )

def get_dataset_info(collection: str, dataset_name: str) -> dict:
    """Return dataset-level metadata."""
    dataset = _get_dataset(collection, dataset_name)

    private_fields = {
        "split_metadata",
    }

    return {
        key: value
        for key, value in dataset.items()
        if key not in private_fields
    }

def get_split_info(
    collection: str,
    dataset_name: str,
    split: str,
) -> dict:
    """Return metadata for a specific dataset split."""
    dataset = _get_dataset(collection, dataset_name)
    split_metadata = dataset.get("split_metadata") or {}

    if split not in split_metadata:
        raise KeyError(
            f"Split {split!r} not found for dataset {dataset_name!r}."
        )

    return {
        key: value
        for key, value in split_metadata[split].items()
        if key != "dataset_url"
    }
