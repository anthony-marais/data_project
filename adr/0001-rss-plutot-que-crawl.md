# ADR 0001 — RSS plutôt que crawl

- Statut : accepted
- Date : 2026-08-31
- Décideurs : anthony-marais

## Contexte

PressLake ingère de la presse pour alimenter un datalake puis un RAG sourcé. Deux approches possibles pour collecter les articles :

1. **RSS / Atom** — flux publics publiés par les éditeurs
2. **Crawl** — parcours HTML du site, découverte de liens

Le crawl apporte plus de couverture mais introduit des risques légaux (CGU, paywall), techniques (anti-bot, HTML variable) et opérationnels (rate limit, maintenance des sélecteurs).

## Décision

PressLake s'appuie **exclusivement sur des flux RSS/Atom publics** pour l'ingest MVP (modules 02–07).

- Pas de spider site entier
- Pas de contournement de paywall
- Watermarks HTTP (`ETag`, `Last-Modified`) quand disponibles
- `guid` / `link` comme clés de dédup

Le crawl pourra être réévalué **après** stabilisation du lake et uniquement pour des sources explicitement autorisées.

## Conséquences

**Positives**

- Contrat d'entrée stable et incrémental
- Idempotence naturelle (module 02)
- Alignement avec la vision « datalake rejouable » sans dépendre du HTML du jour

**Négatives**

- Couverture limitée aux flux disponibles
- Certains flux ne fournissent qu'un extrait HTML → fetch permalink (module 05)

## Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| Crawl généraliste (Scrapy) | Complexité, fragilité, hors périmètre formation initiale |
| APIs payantes agrégateur | Coût, dépendance fournisseur |
| Archive manuelle | Non reproductible, non automatisable |
