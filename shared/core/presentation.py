"""Human-readable presentation of package results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from html import escape
from pprint import pformat
from typing import Any


class _PrettyValue:
    """Notebook and terminal representation of an existing Python value."""

    __slots__ = ("_value",)

    def __init__(self, value: Any) -> None:
        self._value = value

    def __str__(self) -> str:
        return pformat(self._value, sort_dicts=False, width=88)

    def __repr__(self) -> str:
        return str(self)

    def _repr_html_(self) -> str:
        """Return the rich representation used automatically by notebooks."""
        return (
            '<div class="gbd-pretty">'
            "<style>"
            ".gbd-pretty{font-family:var(--jp-ui-font-family,system-ui,sans-serif);}"
            ".gbd-pretty table{border-collapse:collapse;width:100%;}"
            ".gbd-pretty th,.gbd-pretty td{"
            "border:1px solid #d0d7de;padding:0.4rem 0.55rem;"
            "text-align:left!important;vertical-align:top;"
            "white-space:normal;overflow-wrap:anywhere;}"
            ".gbd-pretty th{font-weight:600;width:12rem;}"
            ".gbd-pretty ul{margin:0;padding-left:1.25rem;}"
            ".gbd-pretty details>summary{cursor:pointer;font-weight:500;}"
            ".gbd-pretty .gbd-pretty-scalar{white-space:pre-wrap;}"
            "</style>"
            f"{_render_html(self._value)}"
            "</div>"
        )


def _render_html(value: Any, *, depth: int = 0) -> str:
    """Render supported Python containers recursively with escaped values."""
    if isinstance(value, Mapping):
        if not value:
            return "<em>empty dictionary</em>"

        rows = "".join(
            "<tr>"
            f"<th>{escape(str(key))}</th>"
            f"<td>{_render_html(item, depth=depth + 1)}</td>"
            "</tr>"
            for key, item in value.items()
        )
        table = f"<table><tbody>{rows}</tbody></table>"

        if depth:
            count = len(value)
            noun = "entry" if count == 1 else "entries"
            return (
                "<details>"
                f"<summary>{count} {noun}</summary>"
                f"{table}"
                "</details>"
            )
        return table

    if isinstance(value, Set) and not isinstance(value, (str, bytes)):
        values = sorted(value, key=str)
        return _render_sequence(values, depth=depth)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return _render_sequence(value, depth=depth)

    if value is None:
        text = "None"
    elif isinstance(value, bool):
        text = "True" if value else "False"
    else:
        text = str(value)

    return f'<span class="gbd-pretty-scalar">{escape(text)}</span>'


def _render_sequence(value: Sequence, *, depth: int) -> str:
    """Render each sequence member on its own line."""
    if not value:
        return "<em>empty list</em>"
    items = "".join(
        f"<li>{_render_html(item, depth=depth + 1)}</li>"
        for item in value
    )
    return f"<ul>{items}</ul>"


def pretty(value: Any) -> _PrettyValue:
    """Return a full human-readable view without changing the input value.

    Notebooks automatically use a structured HTML representation. Calling
    print uses an indented text representation suitable for a terminal.
    """
    return _PrettyValue(value)
