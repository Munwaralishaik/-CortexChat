"""
backend/utils/chunker.py — Semantic Text Splitting for RAG.

This module provides the logic to divide large documents into smaller, overlapping segments
(chunks) suitable for vector embedding and retrieval. 

Strategy (Word-Level Overlapping):
  - The raw document is split into discrete word tokens.
  - The text is grouped into segments of `chunk_size` words.
  - To prevent semantic loss at the boundaries, consecutive segments 
    share `overlap` words.

By maintaining context overlap, the downstream LLM has a higher chance of successfully
answering queries that span across paragraph or page breaks in the original document.
"""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping word-level chunks.

    Args:
        text:       The full document text.
        chunk_size: Target number of words per chunk.
        overlap:    Number of words shared between consecutive chunks.

    Returns:
        List of text chunk strings.

    Example:
        >>> chunks = chunk_text("word " * 1200, chunk_size=500, overlap=50)
        >>> len(chunks)
        3
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += step

    return chunks
