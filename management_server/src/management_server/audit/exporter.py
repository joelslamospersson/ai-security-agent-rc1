"""
Audit export — export interfaces for JSON, CSV, and Parquet formats.

No scheduling. No automatic export. Only format generation.
"""

from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog

from management_server.audit.exceptions import ExportError

logger = structlog.get_logger("audit.exporter")


class AuditExporter(ABC):
    """Abstract base class for audit event exporters."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Exporter format name."""
        ...

    @abstractmethod
    def export(self, events: list[dict[str, Any]]) -> tuple[str, bytes]:
        """Export events to bytes.

        Returns (filename, data).
        """
        ...


class JsonExporter(AuditExporter):
    """Exports audit events as JSON array."""

    format_name = "json"

    def export(self, events: list[dict[str, Any]]) -> tuple[str, bytes]:
        try:
            data = json.dumps(events, indent=2, default=str, sort_keys=True).encode()
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"audit_export_{ts}.json", data
        except Exception as e:
            raise ExportError("json", str(e)) from e


class CsvExporter(AuditExporter):
    """Exports audit events as CSV."""

    format_name = "csv"

    def export(self, events: list[dict[str, Any]]) -> tuple[str, bytes]:
        try:
            output = io.StringIO()
            if not events:
                return "audit_export_empty.csv", b""

            fieldnames = list(events[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for event in events:
                row = {
                    k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                    for k, v in event.items()
                }
                writer.writerow(row)

            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"audit_export_{ts}.csv", output.getvalue().encode()
        except Exception as e:
            raise ExportError("csv", str(e)) from e


class ParquetExporter(AuditExporter):
    """Exports audit events as Parquet (placeholder — requires pyarrow)."""

    format_name = "parquet"

    def export(self, events: list[dict[str, Any]]) -> tuple[str, bytes]:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            if not events:
                ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                return f"audit_export_{ts}.parquet", b""

            table = pa.Table.from_pylist(events)
            buf = pa.BufferOutputStream()
            pq.write_table(table, buf)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"audit_export_{ts}.parquet", buf.getvalue().to_pybytes()
        except ImportError:
            raise ExportError("parquet", "pyarrow not installed — cannot export parquet") from None
        except Exception as e:
            raise ExportError("parquet", str(e)) from e


class ExportRegistry:
    """Registry of available exporters."""

    def __init__(self) -> None:
        self._exporters: dict[str, AuditExporter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for exp in [JsonExporter(), CsvExporter()]:
            self._exporters[exp.format_name] = exp
        # Parquet is optional
        try:
            p = ParquetExporter()
            self._exporters[p.format_name] = p
        except Exception:
            pass

    def get(self, format_name: str) -> AuditExporter | None:
        return self._exporters.get(format_name)

    def get_or_error(self, format_name: str) -> AuditExporter:
        exporter = self._exporters.get(format_name)
        if exporter is None:
            raise ExportError(format_name, f"Unsupported format: '{format_name}'")
        return exporter

    @property
    def available(self) -> list[str]:
        return list(self._exporters.keys())
