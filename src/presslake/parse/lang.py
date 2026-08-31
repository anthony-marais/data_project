"""Détection de langue du contenu silver."""

from langdetect import DetectorFactory, LangDetectException, detect_langs

# Résultats reproductibles (échantillon fixe).
DetectorFactory.seed = 0

MIN_TEXT_LEN = 40


def detect_content_lang(text: str, *, fallback: str = "und") -> tuple[str, float | None]:
    """
    Détecte la langue principale d'un texte.

    Args:
        text: corps de l'article (titre + texte recommandé).
        fallback: code ISO si texte trop court ou indéterminé (souvent feed.lang).

    Returns:
        (code ISO 639-1, probabilité) — probabilité None si fallback utilisé.
    """
    sample = (text or "").strip()
    if len(sample) < MIN_TEXT_LEN:
        return fallback, None

    try:
        candidates = detect_langs(sample)
    except LangDetectException:
        return fallback, None

    if not candidates:
        return fallback, None

    best = candidates[0]
    code = best.lang.lower()
    if len(code) != 2:
        return fallback, None
    return code, float(best.prob)
