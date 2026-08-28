"""Helpers for building minimal text PDFs in tests."""

from __future__ import annotations

from pathlib import Path


def write_text_pdf(path: Path, text: str) -> None:
    escaped = (
        text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )
    content = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET\n".encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        ),
        b"4 0 obj << /Length %d >> stream\n" % len(content)
        + content
        + b"endstream\nendobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    header = b"%PDF-1.4\n"
    body = b""
    offsets = [0]
    cursor = len(header)
    for obj in objects:
        offsets.append(cursor)
        body += obj
        cursor += len(obj)
    xref = [b"xref\n0 6\n0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode())
    trailer = (
        b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(len(header) + len(body)).encode()
        + b"\n%%EOF\n"
    )
    path.write_bytes(header + body + b"".join(xref) + trailer)
