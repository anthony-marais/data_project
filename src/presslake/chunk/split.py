"""Découpage de texte en chunks avec chevauchement."""

from typing import Any

DEFAULT_MAX_CHARS = 800
DEFAULT_OVERLAP = 100


def chunk_text(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict[str, Any]]:
    """
    Découpe un texte en morceaux citables avec chevauchement.

    Stratégie : fenêtre glissante ; coupe de préférence sur un espace
    pour ne pas tronquer un mot.

    Args:
        text: corps de l'article (silver.text).
        max_chars: taille max d'un chunk (caractères).
        overlap: caractères partagés entre deux chunks consécutifs.

    Returns:
        Liste de dicts {chunk_index, text, char_start, char_end}.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    if len(cleaned) <= max_chars:
        return [
            {
                "chunk_index": 0,
                "text": cleaned,
                "char_start": 0,
                "char_end": len(cleaned),
            }
        ]

    if overlap >= max_chars:
        raise ValueError("overlap doit être < max_chars")

    chunks: list[dict[str, Any]] = []
    start = 0
    index = 0

    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))

        if end < len(cleaned):
            boundary = cleaned.rfind(" ", start + 1, end)
            if boundary > start:
                end = boundary

        segment = cleaned[start:end].strip()
        if segment:
            chunks.append(
                {
                    "chunk_index": index,
                    "text": segment,
                    "char_start": start,
                    "char_end": end,
                }
            )
            index += 1

        if end >= len(cleaned):
            break

        start = max(end - overlap, start + 1)

    return chunks
