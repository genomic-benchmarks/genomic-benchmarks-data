import json
from pathlib import Path


def load_metadata() -> dict:
    """Load metadata for all included dataset collections."""
    metadata_dir = Path(__file__).parent.parent / "metadata"

    collections = {}

    for path in sorted(metadata_dir.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            metadata = json.load(f)

        metadata["datasets"] = [
            dataset
            for dataset in metadata["datasets"]
            if dataset.get("excluded") is None
        ]

        collections[metadata["collection"]] = metadata

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
    golden_set: bool | None = None,
) -> dict[str, dict[str, str]]:
    """Return datasets, optionally filtered by collection and metadata."""
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
        "golden_set": golden_set,
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

    excluded_fields = {
        "split_metadata",
        "path_to_qc_csv",
        "path_to_qc_html",
        "excluded",
    }

    return {
        key: value
        for key, value in dataset.items()
        if key not in excluded_fields
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
        if key != "dataset_path"
    }
