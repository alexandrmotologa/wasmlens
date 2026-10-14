"""Export utilities: standalone HTML audit reports and C headers."""

from wasmlens.export.header import generate_c_header
from wasmlens.export.report import generate_html_report

__all__ = ["generate_html_report", "generate_c_header"]
