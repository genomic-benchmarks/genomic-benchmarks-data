# Genomic Benchmarks Data

Genomic Benchmarks Data provides consistent Python access to curated genomic
machine-learning datasets, their metadata, and quality-control (QC) results.

## Choose a package

| Package | Data access | QC access |
| --- | --- | --- |
| [`genomic-benchmarks-data`](genomic-benchmarks-data/) | All published splits, including `test` splits | Class and split QC |
| [`genomic-benchmarks-data4agents`](genomic-benchmarks-data4agents/) | `train` and `val` splits where available; no `test` splits | Class QC for `train` and `val`; `train`–`val` split QC |

Use `genomic-benchmarks-data` for ordinary model development and evaluation.
Use `genomic-benchmarks-data4agents` when an agent must be able to work with
`train` and `val` data without being given `test` data or `test`-related QC
information.

## What you can do

Both packages let you:

- discover collections and datasets and filter them by their metadata;
- inspect dataset- and split-level metadata;
- download a split to a local cache or load it as a pandas DataFrame;
- inspect, filter, and plot the QC results available to that package; and
- retrieve self-contained HTML class-QC reports.

The full package additionally exposes `test` splits and split QC for all
available comparisons. The agents package limits split QC to `train`–`val`
comparisons, so datasets without a `val` split have no split-QC result there.

## Quick start

Install one of the packages:

```bash
python -m pip install genomic-benchmarks-data
# or
python -m pip install genomic-benchmarks-data4agents
```

The imports have the same shape; replace `genomic_benchmarks_data` with
`genomic_benchmarks_data4agents` when using the agent-safe package.

```python
import genomic_benchmarks_data as gbd

collections = gbd.list_collections()
core_datasets = gbd.list_datasets(core_set=True)
gbd.pretty(core_datasets)
train = gbd.load_dataset("BEACON", "CRISPROnTarget", "train")
train.head()
```

## Tutorials

- [Full-package tutorial](tutorials/genomic-benchmarks-data.ipynb)
- [Agent-safe package tutorial](tutorials/genomic-benchmarks-data4agents.ipynb)

## Public API at a glance

Both packages expose the same function names. The agents package applies its
`train`/`val`-only boundary to dataset and QC functions.

| Function | What it does | Package notes |
| --- | --- | --- |
| `load_metadata()` | Loads all packaged collection and dataset metadata. | The agents metadata omits unavailable `test` splits. |
| `list_collections()` | Lists collection names and their source DOIs. | Same interface in both packages. |
| `list_dataset_filters(collection=None)` | Lists the values accepted by each dataset filter. | Optionally limits metadata-derived values to one collection. |
| `list_datasets(...)` | Lists datasets, with optional collection, metadata, and `core_set` filters. | Results reflect the datasets included in the package. |
| `pretty(value)` | Presents dictionaries and lists readably in notebooks or terminals. | Presentation only; the original value is unchanged. |
| `list_molecular_levels(collection)` | Lists molecular levels available in a collection. | Same interface in both packages. |
| `list_task_categories(collection)` | Lists task categories available in a collection. | Same interface in both packages. |
| `list_task_types(collection)` | Lists task types available in a collection. | Same interface in both packages. |
| `list_species(collection)` | Lists species values available in a collection. | Same interface in both packages. |
| `get_dataset_info(collection, dataset_name)` | Returns metadata for one dataset. | The agents result lists only accessible splits. |
| `get_split_info(collection, dataset_name, split)` | Returns metadata for one split. | The agents package accepts only `train` and available `val` splits. |
| `download_dataset(collection, dataset_name, split)` | Downloads a split and returns its cached path. | The agents package cannot download `test` splits. |
| `load_dataset(collection, dataset_name, split, ...)` | Loads a split as a pandas DataFrame. | The agents package cannot load `test` splits. |
| `download_qc_csv(qc_type)` | Downloads the combined class- or split-QC CSV and returns its cached path. | The agents QC artifacts contain no `test`-related results. |
| `load_qc_results(qc_type)` | Downloads and parses class- or split-QC results. | The agents split results contain `train`–`val` comparisons only. |
| `list_qc_metrics(qc_type)` | Lists the available checks for a QC type. | Results reflect the QC exposed by the package. |
| `filter_datasets_by_qc(qc_type, ...)` | Selects datasets by QC check and outcome. | Results reflect the QC exposed by the package. |
| `plot_qc_summary(qc_type, ...)` | Plots QC outcome proportions by collection. | Agents split plots include only collections with `train`–`val` comparisons. |
| `get_class_qc_report(...)` | Retrieves a self-contained report for one dataset split. | The agents package supports `train` and `val` reports only. |
| `get_split_qc_report(...)` | Retrieves a self-contained report comparing two splits. | The agents package supports `train`–`val` reports only. |

## Repository layout

- `genomic-benchmarks-data/`: the full package;
- `genomic-benchmarks-data4agents/`: the package that excludes `test` data;
- `tutorials/`: package-specific tutorial notebooks;
- `shared/core/`: implementation bundled into both wheels;
- `scripts/`: metadata validation and installed-wheel checks.

The GitHub Actions workflow runs for pull requests, pushes to `main`, and
manual dispatches. It validates each package's metadata against its schema,
then builds, installs, and smoke-tests both wheels.

This project is licensed under the Apache License 2.0. Individual dataset
licenses and attribution information are recorded in the packaged metadata.
