"""Test doubles with no app imports, so conftest can load them before any app module."""

import hashlib
import math
import re

DIMENSIONS = 384  # matches DocumentChunk.content_vector (BAAI/bge-small-en-v1.5)


def unit_vector(*weights):
    """Normalised vector with the given weights on the first axes, e.g. unit_vector(1, 1)."""
    vec = [0.0] * DIMENSIONS
    for i, w in enumerate(weights):
        vec[i] = float(w)
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


def fake_vector(text):
    """Deterministic bag-of-words embedding: texts sharing words are close in cosine distance."""
    vec = [0.0] * DIMENSIONS
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if not norm:
        return unit_vector(1)
    return [v / norm for v in vec]


class FakeTextEmbedding:
    """Stands in for fastembed.TextEmbedding so component tests skip the model download."""

    def __init__(self, *args, **kwargs):
        pass

    def embed(self, documents, **kwargs):
        if isinstance(documents, str):
            documents = [documents]
        for text in documents:
            yield fake_vector(text)


def build_pdf(lines):
    """Build a minimal one-page PDF with extractable text (parsed by pdfminer)."""

    def escape(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = ("BT /F1 12 Tf 72 720 Td 16 TL "
              + " ".join(f"({escape(line)}) Tj T*" for line in lines)
              + " ET").encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_at)
    return pdf
