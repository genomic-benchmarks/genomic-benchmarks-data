# Genomic Benchmarks Data

Genomic Benchmarks Data provides consistent Python access to curated genomic
machine-learning datasets, their metadata, and quality-control (QC) results.

## Choose a package

| Package | Data access | QC access |
| --- | --- | --- |
| [`genomic-benchmarks-data`](genomic-benchmarks-data/) | All published splits, including test splits | Class and split QC |
| [`genomic-benchmarks-data4agents`](genomic-benchmarks-data4agents/) | Train and validation (`val`) splits where available; no test splits | Class QC for train and `val`; train–`val` split QC |

Use `genomic-benchmarks-data` for ordinary model development and evaluation.
Use `genomic-benchmarks-data4agents` when an agent must be able to work with
train and validation data without being given test data or test-related QC
information.

## What you can do

Both packages let you:

- discover collections and datasets and filter them by their metadata;
- inspect dataset- and split-level metadata;
- download a split to a local cache or load it as a pandas DataFrame;
- inspect, filter, and plot the QC results available to that package; and
- retrieve self-contained HTML class-QC reports.

The full package additionally exposes test splits and split QC for all
available comparisons. The agents package limits split QC to train–`val`
comparisons, so datasets without a `val` split have no split-QC result there.

Downloaded dataset tables have two common leading columns:

- `id`: a stable identifier for the example;
- `row_index`: the example's original zero-based row number.

The remaining columns depend on the dataset and are described by its metadata.

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

datasets = gbd.list_datasets(task_type="Binary classification")
info = gbd.get_dataset_info(
    "genomic-benchmarks",
    "demo_coding_vs_intergenomic_seqs",
)
train = gbd.load_dataset(
    "genomic-benchmarks",
    "demo_coding_vs_intergenomic_seqs",
    "train",
)
```

`load_dataset(...)` returns the sequence and label columns by default. For
`test` and `test_leftout`, it also returns `id` and `row_index` as the
first two columns. Pass `columns="all"` to retain every column in the dataset
file.

`download_dataset(...)` returns the exact path of the cached file. On Linux,
the package caches are under `~/.cache/genomic_benchmarks_data` and
`~/.cache/genomic_benchmarks_data4agents`; other operating systems use their
standard user cache directory. Dataset files and downloaded QC artifacts use
the same package-specific cache.

QC results are produced by
[`genomic-benchmarks-qc`](https://github.com/genomic-benchmarks/genomic-benchmarks-qc).
See the individual package READMEs for the QC available in each package and
the corresponding Zenodo record.

## Repository layout

- `genomic-benchmarks-data/`: the full package;
- `genomic-benchmarks-data4agents/`: the package that excludes test data;
- `shared/core/`: implementation bundled into both wheels;
- `scripts/`: metadata validation and installed-wheel checks.

The GitHub Actions workflow runs for pull requests, pushes to `main`, and
manual dispatches. It validates each package's metadata against its schema,
then builds, installs, and smoke-tests both wheels.

This project is licensed under the Apache License 2.0. Individual dataset
licenses and attribution information are recorded in the packaged metadata.
