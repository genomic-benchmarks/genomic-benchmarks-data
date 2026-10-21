"""Shared helpers for the tutorial notebooks."""

from html import escape

from IPython.display import display


def display_qc_report(path, height=900):
    """Display a standalone QC report without leaking its styles into Jupyter."""
    document = escape(path.read_text(encoding="utf-8"), quote=True)
    iframe = (
        f'<iframe srcdoc="{document}" '
        f'style="width: 100%; height: {height}px; border: 1px solid #ddd;"'
        '></iframe>'
    )
    display({"text/html": iframe}, raw=True)
