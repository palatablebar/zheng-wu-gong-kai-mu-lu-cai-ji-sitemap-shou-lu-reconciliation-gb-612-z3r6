"""CSV 导出工具：UTF-8 BOM，避免 Excel 打开中文乱码。"""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence

BOM = "\ufeff"


def to_csv(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return (BOM + buffer.getvalue()).encode("utf-8")


def csv_response_headers(filename: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
