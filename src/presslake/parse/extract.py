"""
Extraction de texte depuis le bronze RSS.

Stratégie (module 05) :
  1. summary HTML du flux RSS → trafilatura
  2. si texte trop court → fetch permalink + trafilatura
"""

import httpx
import trafilatura

# Même User-Agent que l'ingest (évite 403 sur les médias FR).
USER_AGENT = "PressLake/0.1 (learning; local dev)"

# En dessous de ce seuil, on tente le fetch du permalink.
MIN_TEXT_LENGTH = 80


def extract_text_from_html(html: str) -> str | None:
    """
    Extrait le texte principal d'un fragment HTML (summary RSS ou page).

    trafilatura retire scripts, nav, etc. et garde le corps de l'article.
    """
    if not html or not html.strip():
        return None

    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        deduplicate=True,
    )
    return text.strip() if text else None


def fetch_permalink_html(url: str) -> str | None:
    """
    Télécharge le HTML de l'article (permalink).

    Returns:
        Corps HTML ou None si échec réseau / HTTP erreur.
    """
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text
    except httpx.HTTPError:
        return None


def extract_text_from_bronze(bronze: dict) -> tuple[str, str]:
    """
    Produit le texte silver à partir d'une enveloppe bronze.

    Args:
        bronze: dict lu depuis MinIO (build_bronze_envelope).

    Returns:
        (texte, source) où source est 'rss_summary' ou 'permalink'.

    Raises:
        ValueError: si aucun texte extractible.
    """
    raw = bronze.get("raw") or {}
    summary = raw.get("summary") or ""

    # Étape 1 : extraire depuis le summary RSS (souvent du HTML).
    text = extract_text_from_html(summary)
    if text and len(text) >= MIN_TEXT_LENGTH:
        return text, "rss_summary"

    # Étape 2 : fallback permalink.
    link = bronze.get("link")
    if link:
        html = fetch_permalink_html(str(link))
        if html:
            text = extract_text_from_html(html)
            if text and len(text) >= MIN_TEXT_LENGTH:
                return text, "permalink"

    # Dernier recours : summary court ou titre seul (mieux que rien).
    if text:
        return text, "rss_summary"

    title = bronze.get("title")
    if title and str(title).strip():
        return str(title).strip(), "title_only"

    raise ValueError(
        f"texte non extractible : feed={bronze.get('feed_id')!r} "
        f"link={bronze.get('link')!r}"
    )
