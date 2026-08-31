"""
Poll des flux RSS : fetch HTTP, parse XML, déduplication.

Chaîne :
  Feed.url → httpx GET → feedparser → entries[]
  → clé composite (feed_id + item_key) → seen.json
"""

from pathlib import Path

import feedparser
import httpx

from presslake.ingest.feeds import Feed
from presslake.ingest.seen import DEFAULT_SEEN_PATH, load_seen, mark_seen, save_seen

# Certains médias (France24, RFI, CNIL) renvoient 403 sans User-Agent explicite.
USER_AGENT = "PressLake/0.1 (learning; local dev)"


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    """
    Télécharge un flux RSS/Atom et le parse.

    Args:
        url: URL du flux (ex. https://www.france24.com/fr/rss).

    Returns:
        Objet feedparser avec .feed (métadonnées) et .entries (liste d'articles).

    Raises:
        httpx.HTTPStatusError: si le serveur répond 4xx ou 5xx.
    """
    response = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT},  # « headers » au pluriel (pas « header »)
        timeout=30.0,
        follow_redirects=True,  # suit les 301/308 (ex. certains flux institutionnels)
    )
    response.raise_for_status()  # lève une exception si status != 2xx

    # feedparser attend du texte XML (str), pas des bytes bruts.
    return feedparser.parse(response.text)


def item_key(entry: dict) -> str:
    """
    Extrait une clé stable pour un article, quel que soit le format du flux.

    Ordre de priorité (couvre RSS 2.0 et Atom) :
      1. id   — courant en Atom
      2. guid — courant en RSS 2.0
      3. link — fallback universel (URL de l'article)

    Raises:
        ValueError: si aucun des trois champs n'est présent.
    """
    for field in ("id", "guid", "link"):
        value = entry.get(field)
        if value:
            # str() : feedparser peut renvoyer des types exotiques pour guid.
            return str(value).strip()

    raise ValueError(f"item sans clé : title={entry.get('title')!r}")


def composite_key(feed: Feed, entry: dict) -> str:
    """
    Clé unique par flux ET par article.

    Sans le préfixe feed.id, deux flux différents pourraient partager
    la même URL de link → fausse dédup. Ex. : "france24:uuid-abc".
    """
    return f"{feed.id}:{item_key(entry)}"


def poll_feed(feed: Feed, seen: dict[str, str]) -> int:
    """
    Poll un seul flux et affiche les nouveaux items.

    Args:
        feed: flux à interroger.
        seen: dict des clés déjà vues (modifié en place via mark_seen).

    Returns:
        Nombre d'items nouveaux pour ce flux.
    """
    parsed = fetch_feed(feed.url)
    new_count = 0

    for entry in parsed.entries:
        key = composite_key(feed, entry)

        # mark_seen retourne True si déjà connu → on skip (dédup).
        if mark_seen(seen, key):
            continue

        new_count += 1
        title = entry.get("title", "(sans titre)")
        print(f"[NEW] {feed.id} | {title}")

    return new_count


def poll_all_dedup(
    feeds: list[Feed],
    seen_path: Path = DEFAULT_SEEN_PATH,
) -> int:
    """
    Poll tous les flux configurés, avec déduplication persistée.

    Workflow :
      1. Charger seen.json (ou {} si premier run)
      2. Pour chaque feed → poll_feed
      3. Sauvegarder seen.json
      4. Afficher le total de nouveaux items

    Critère *done* module 02 : 2e appel consécutif → total = 0.

    Returns:
        Nombre total de nouveaux items sur tous les flux.
    """
    seen = load_seen(seen_path)
    total_new = 0

    for feed in feeds:
        total_new += poll_feed(feed, seen)

    save_seen(seen, seen_path)
    print(f"\n→ {total_new} nouvel(s) item(s)")

    return total_new
