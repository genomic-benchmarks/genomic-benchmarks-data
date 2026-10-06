# Dataset Metadata Field Documentation

This document describes the collection metadata distributed in this data package,
for example `BEACON_metadata.json` and `genomic-benchmarks_metadata.json`. Local
`dataset_path` values are not published.

The corresponding JSON Schema is `metadata.schema.json`.

## Top-level fields

- `schema_version`: The version of `metadata.schema.json` this file conforms to.
  Required, a string, and currently `1.0`. See "Schema versioning" below.
- `collection`: Name of the dataset collection.
- `collection_doi`: Primary source DOI/publication for the collection.
- `licence`: The collection's licence, and specifically whether its split files may
  be republished. Required. See "Licence fields" below.
- `datasets`: Array of dataset entries for this collection.

## Per-dataset fields (`datasets[]`)

- `dataset_name`: Dataset/task identifier.
- `major_version`: The major version of this dataset's **data**, not of the schema
  (`schema_version`). A string matching `^v[0-9]+$`; every dataset is currently `v1`.
  - Required for every dataset in this package.
  - Written by the collection's curation notebook from `DEFAULT_MAJOR_VERSION` in
    `curation/utils.py`, the same constant `write_split` stamps into the
    IDs it mints, so this field and the files cannot claim different versions.
  - It is the third field of every sequence ID —
    `<collection>:<dataset>:<major version>:<split>:<index>` — and the path prefix
    the published files sit under. A consumer composing IDs for a split it fetched
    from the original source has no other way to learn it.
  - Bumped when a dataset's sequences change: indices restart at zero and the files
    move to a new prefix rather than being rewritten in place.
- `task_description`: Human-readable description of the prediction task.
  - Must be present and non-null.
- `dataset_doi`: DOI/publication for the dataset.
- `species`: Species covered by the dataset.
  - Must be a non-null string.
- `task_type`: Task category (for example: Binary classification, Multi-class classification, Regression).
  - Must be present and non-null.
- `seq_col`: Input sequence column name(s).
  - Must be an array of strings.
- `label_col`: Label column name(s), as a string, array of strings, or `null`.
  - Must be a string or array of strings.
- `label_categories`: Map from label IDs/keys to human-readable class names.
  - `null` for non-categorical tasks.
  - Must name **at least two classes** for an included dataset whose `task_type`
    contains `classification`. A classifier's output cannot be reported without
    them: the leaderboard needs the names to label a column and to know which
    class a prediction scores.
  - The schema checks that classes are named, not that they are the **right**
    classes: naming `0` and `1` for a split containing a `2` is schema-valid.
    Confirming that means reading `split_metadata.<split>.labels` from another
    level of the same document, which JSON Schema cannot cross-reference, so
    `workflows/dataset_qc/bin/validate_metadata.py` does it — see "Cross-document
    checks" below.
- `splits`: Available split names (for example `train`, `val`, or `test`).
  - Must be a non-empty array of split names.
- `task_category`: High-level label describing the biological scope of the benchmark task
- `molecular_level`: Label for tasks at the molecule scale, specifically involving DNA, RNA, or protein sequences.
- `positive_label`: Label value treated as the positive class for scoring, stored as a string.
  `null` when the task has no positive class.
- `scoring_splits`: Split names used for benchmark scoring, stored as an array of strings.
  `null` when the dataset is not scored.
- `scoring_metric`: Metric used for benchmark scoring, stored as a string.
  `null` when no scoring metric is specified.
- `split_metadata`: Non-empty per-split metadata object.

## Split metadata fields (`split_metadata.<split_name>`)

- `seq_length`: Map from sequence column name to summary statistics for observed lengths.
  - Each summary contains `min`, `max`, and `median`.
- `seq_alphabet`: Map from sequence column name to list of observed alphabet symbols.
- `labels`: Label metadata for the split.
  - Can be an array of label values for classification.
  - Can be an object with numeric summary (`min`, `max`, `median`) for regression.
  - Can be `null` where labels are unavailable — but not for a retained
    classification dataset, where it is the evidence `label_categories` is checked
    against. See "Cross-document checks" below.
- `dataset_size`: Number of rows/examples in the split.
- `class_ratio`: Map from class key to proportion, or `null`.
  - Keyed by the same class keys as `label_categories`, which the schema cannot
    check either — it permits any key. See "Cross-document checks" below.
- `all_columns`: List of all columns present in the released split file, including
  the `id` and `row_index` columns when materialised by the publisher.
- `dataset_url`: Download URL for the split file in the released corpus.
  - Must be present for every split of an included dataset.
- `sha256`: SHA-256 checksum of the file referenced by `dataset_url`.
  - Must be a 64-character hexadecimal string.
  - Used to verify that downloaded and cached files match the dataset version described by the metadata.

## Licence fields (`licence`)

Held at collection level, where it is required, and optionally repeated on a
dataset entry to override it. A dataset's own licence wins, because a collection
release does not always speak for the sources it gathers.

- `name`: Common or SPDX-style name, for example `CC BY 4.0`. `null` where the
  source states none, which is not the same as permissive: an absent licence
  grants nothing.
- `url`: Where the licence text was read from.
- `redistribution`: `permitted`, `denied`, or `unknown`. Required. The one field
  `curation/publish_datasets.py` branches on.
  - `permitted` uploads the split file, and `dataset_url` then names that copy.
  - `denied` and `unknown` leave the file to be fetched from its original source,
    which is what `dataset_url` and `sha256` go on naming. `unknown` is kept
    distinct from `denied` because an unanswered licence is not a refusal, and
    answering one flips a collection over in a single edit.
- `note`: Why the value is what it is — the evidence, not a restatement. A denial
  should name who declined and when.

## Schema versioning

Every collection file states the schema version it conforms to. The point is not
bookkeeping: a consumer of this metadata cannot version someone else's schema, so
without the field the only way to discover that the shape moved is to hit a
`KeyError` three calls deep in whatever read it. A consumer pins the versions it
understands and fails with "metadata schema moved from 1.0 to 1.1" instead.

The schema pins the value with `const`, not a pattern. So the version and the
shape it names cannot drift apart: changing the schema means changing the `const`
and all seven collection files in the same commit, and a file left behind fails
validation rather than going on claiming a version it no longer matches. Both
directions fail — a file ahead of the schema and a file behind it.

| Bump | When | What a consumer must do |
|---|---|---|
| Major (`1.x` → `2.0`) | A reader written for the previous major can misread a document: a field removed, renamed or retyped; the meaning of an existing field changed; a value added to `task_type` or `molecular_level`. | Read the changes before accepting the new version. |
| Minor (`1.0` → `1.1`) | It cannot: a field added, or a constraint tightened so that only documents which were already wrong begin to fail. | Nothing. Widen the pin. |

A new `task_type` or `molecular_level` value is a **major** bump even though it
adds nothing to the shape. Those two fields are closed vocabularies precisely
because consumers switch on them, so a value one has no branch for is exactly the
case this number exists to announce.

`1.0` is the first numbered version and nothing was published before it, so the
rule requiring a retained classification dataset to name at least two classes,
`major_version` itself, and the three cross-document checks below are all part of
`1.0` rather than additions to it.

## Cross-document checks

Three of the rules above relate one part of a metadata record to another, which
JSON Schema has no way to express: a `$ref` reuses a *definition*, it does not
compare two *values*. They are enforced instead by
`workflows/dataset_qc/bin/validate_metadata.py`, which runs the schema and then
these, and reports them as a second section of
`{collection}_metadata_validation.txt`.

For every retained dataset whose `task_type` contains `classification` — the same
set the schema's `label_categories` rule applies to, matched the same way, so the
two cannot cover different datasets:

1. Each split's `labels` must be the list of observed classes. `null`, or a
   regression-style `{min, max, median}`, is an error here even though the schema
   allows both, because it is what the classes are checked against: were it
   skipped, deleting the observed labels would be the way to silence a real
   mismatch.
2. `label_categories` must name exactly the classes the split contains — equality,
   in both directions. A label with no name is the unreportable case. A name with
   no label is narrower, but in a binary split it means a class is missing
   altogether, which leaves accuracy and AUROC undefined.
3. `class_ratio`, where present, must be keyed by those same classes. A proportion
   and a class name that disagree cannot both be reported.

Label values are compared as JSON object keys, since that is what
`label_categories` keys are: the label `0` matches the key `"0"`, and an integral
float matches too, because whether a label column arrives as int or float depends
on the dtype pandas inferred rather than on anything about the dataset.

These run only on a collection whose schema pass was clean, and the report states
when they did not run — a check that is silently skipped cannot be told apart from
one that passed.
