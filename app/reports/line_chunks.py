"""Lossless LINE text segmentation. Pure planning; transport is injected."""
from hashlib import sha256

MAX_TEXT_UNITS = 5000


def text_units(text):
    return len(text.encode("utf-16-le")) // 2


def split_line_text(text, limit=MAX_TEXT_UNITS):
    if not isinstance(text, str) or not text or not 2 <= limit <= MAX_TEXT_UNITS:
        raise ValueError("invalid_line_text_or_limit")
    chunks, current, units = [], [], 0
    for char in text:
        size = text_units(char)
        if units + size > limit:
            chunks.append("".join(current))
            current, units = [], 0
        current.append(char)
        units += size
    if current:
        chunks.append("".join(current))
    assert "".join(chunks) == text
    return chunks


def chunk_evidence(text):
    chunks = split_line_text(text)
    return {"chunk_count": len(chunks), "message_count": len(chunks),
            "message_chars": len(text), "message_utf16_units": text_units(text),
            "content_sha256": sha256(text.encode()).hexdigest(),
            "chunk_sha256": [sha256(x.encode()).hexdigest() for x in chunks],
            "lossless": "".join(chunks) == text}


class LineChunkFailure(RuntimeError):
    def __init__(self, evidence):
        super().__init__("line_chunk_transport_failed")
        self.chunk_delivery = evidence


def deliver_line_chunks(text, sender):
    evidence = {**chunk_evidence(text), "completed_chunk_count": 0}
    for index, chunk in enumerate(split_line_text(text)):
        try:
            sender(chunk)
        except Exception as exc:
            # A recipient may have accepted this chunk; never claim atomicity or
            # automatically retry the entire message and duplicate accepted parts.
            raise LineChunkFailure({**evidence, "failed_chunk_index": index,
                                    "partial_delivery_possible": True,
                                    "error_type": type(exc).__name__}) from None
        evidence["completed_chunk_count"] += 1
    return evidence
