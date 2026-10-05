"""Stable sequence identity helpers shared by both data packages."""

from __future__ import annotations

import gzip
import io
from pathlib import Path

import numpy as np
import pandas as pd


ID_COLUMN = "id"
ROW_INDEX_COLUMN = "row_index"
ID_SEPARATOR = ":"
ID_INDEX_WIDTH = 7
DEFAULT_MAJOR_VERSION = "v1"


def assert_id_safe_name(name, what="name"):
    """Reject a name that would make an ID unparseable.

    Called as a name is minted rather than trusted, because the check is only worth
    anything at the moment a new collection or dataset name enters the corpus.
    """
    if ID_SEPARATOR in str(name):
        raise ValueError(
            f"{what} {name!r} contains {ID_SEPARATOR!r}, which is the sequence "
            f"ID separator. IDs are parsed by splitting on it, so this name "
            f"would produce IDs that cannot be read back. Rename it."
        )
    return str(name)


def id_prefix(collection, dataset_name, split, major_version=DEFAULT_MAJOR_VERSION):
    """Everything in a sequence ID up to and including the last separator.

    `<collection>:<dataset>:<major version>:<split>:` - a literal prefix of
    every ID in the split, which is what lets a validator reject a file
    submitted against the wrong benchmark or a stale version by string
    comparison alone.
    """
    assert_id_safe_name(collection, "collection")
    assert_id_safe_name(dataset_name, "dataset_name")
    assert_id_safe_name(split, "split")
    assert_id_safe_name(major_version, "major_version")
    return ID_SEPARATOR.join(
        [str(collection), str(dataset_name), str(major_version), str(split), ""]
    )


def sequence_ids(collection, dataset_name, split, n_rows,
                 major_version=DEFAULT_MAJOR_VERSION):
    """The IDs of a split of `n_rows`, in row order, as a pandas Series."""
    if n_rows < 0:
        raise ValueError(f"n_rows must not be negative, got {n_rows}")
    limit = 10 ** ID_INDEX_WIDTH
    if n_rows > limit:
        raise ValueError(
            f"{collection}/{dataset_name} split {split} has {n_rows} rows, "
            f"which does not fit in ID_INDEX_WIDTH={ID_INDEX_WIDTH} digits "
            f"(limit {limit}). Widening it renumbers every ID in the corpus, "
            f"so it is a major version bump for every dataset, not a patch."
        )
    prefix = id_prefix(collection, dataset_name, split, major_version)
    index = pd.Series(np.arange(n_rows, dtype=np.int64), dtype="int64")
    return prefix + index.astype(str).str.zfill(ID_INDEX_WIDTH)


def parse_sequence_id(identifier):
    """`GUE_v2:tf_mouse_2:v1:test:0000142` -> (collection, dataset, version, split, 142).

    Splitting from the right, because a dataset name may contain anything except
    the separator and the four fields around it are fixed in number.
    """
    parts = str(identifier).split(ID_SEPARATOR)
    if len(parts) != 5:
        raise ValueError(
            f"sequence ID {identifier!r} has {len(parts)} fields, expected 5: "
            f"<collection>:<dataset>:<major version>:<split>:<index>"
        )
    collection, dataset_name, major_version, split, index = parts
    if len(index) != ID_INDEX_WIDTH or not index.isdigit():
        raise ValueError(
            f"sequence ID {identifier!r} ends in {index!r}, which is not "
            f"{ID_INDEX_WIDTH} digits"
        )
    return collection, dataset_name, major_version, split, int(index)


def assign_sequence_ids(df, collection, dataset_name, split,
                        major_version=DEFAULT_MAJOR_VERSION):
    """Return `df` with `id` and `row_index` as its first two columns.

    Idempotent: a frame that already carries the two columns is renumbered
    from its current row order, so rewriting an unchanged file reproduces it
    exactly.
    The emitted index is asserted to equal row order rather than assumed,
    which is the one check the whole scheme rests on.
    """
    out = df.drop(columns=[c for c in (ID_COLUMN, ROW_INDEX_COLUMN)
                           if c in df.columns]).reset_index(drop=True)

    row_index = pd.Series(np.arange(len(out), dtype=np.int64))
    identifiers = sequence_ids(collection, dataset_name, split, len(out),
                               major_version)

    out.insert(0, ROW_INDEX_COLUMN, row_index)
    out.insert(0, ID_COLUMN, identifiers)

    expected = np.arange(len(out), dtype=np.int64)
    if not np.array_equal(out[ROW_INDEX_COLUMN].to_numpy(), expected):
        raise AssertionError(
            f"{collection}/{dataset_name} split {split}: {ROW_INDEX_COLUMN} "
            f"does not equal row order"
        )
    if len(out):
        parsed = np.array([parse_sequence_id(i)[4] for i in out[ID_COLUMN]])
        if not np.array_equal(parsed, expected):
            raise AssertionError(
                f"{collection}/{dataset_name} split {split}: the index parsed "
                f"back out of {ID_COLUMN} does not equal row order"
            )
    return out


def write_split(df, out_path, collection, dataset_name, split,
                major_version=DEFAULT_MAJOR_VERSION, *, name=None):
    """Assign sequence IDs and write the split. Returns the frame as written.

    The bytes are a function of the rows and of `name` alone. A gzip member
    carries the uncompressed file's modification time and its name in its
    header, and both would otherwise reach the checksum a consumer verifies a
    download against: `mtime=0` because the default writes the current time,
    so the same rows would hash differently on every run; and `name` because
    it is taken from where the file comes to rest rather than from the path
    being written. A caller that writes through a temporary and renames would
    otherwise put the temporary's name inside the file, which is bytes that
    differ for no reason a reader could see; `name` is how such a caller says
    what the file will be called.
    """
    out = assign_sequence_ids(df, collection, dataset_name, split,
                              major_version)
    stem = name or Path(out_path).name
    if stem.endswith(".gz"):
        stem = stem[: -len(".gz")]

    with open(out_path, "wb") as raw:
        # compresslevel pinned rather than left to the default, on the same
        # principle: a checksum should not move because a standard library did.
        with gzip.GzipFile(filename=stem, mode="wb", fileobj=raw,
                           mtime=0, compresslevel=9) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8",
                                  newline="") as text:
                out.to_csv(text, index=False, lineterminator="\n")
    return out
