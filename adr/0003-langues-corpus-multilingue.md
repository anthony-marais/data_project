# ADR 0003 — Langues : corpus natif multilingue (pas de traduction à l'ingest)

- Statut : accepted
- Date : 2026-08-31
- Décideurs : anthony-marais

## Contexte

PressLake ingère des flux RSS **hétérogènes** (`feeds.yml` : `fr`, `en`, et à terme `ru`, `zh`, `ar`…). Aujourd'hui :

- `feed.lang` est déclaré mais non propagé dans silver / Postgres / OpenSearch ;
- la recherche BM25 utilise un analyzer unique (`standard`) ;
- le RAG futur (modules 11–12) aura besoin de **citations** sur le texte **original**.

Question : faut-il **traduire automatiquement tout en FR/EN** à l'ingest ?

## Décision

1. **Corpus natif** : le silver conserve le texte dans la langue source + métadonnées `feed_lang` et `content_lang`.
2. **Pas de traduction systématique à l'ingest** : le bronze et le silver original restent la source de vérité pour les citations.
3. **Détection** au parse : `content_lang` via `langdetect`, fallback sur `feed.lang` du YAML.
4. **OpenSearch** : filtre `content_lang` + champs analysés `title_fr` / `text_fr` / `title_en` / `text_en` selon la langue.
5. **Cross-lingue sémantique** : reporté au **module 11** (embeddings multilingues Qdrant), pas à une traduction massive du lake.
6. **Traduction éventuelle** : uniquement sur les **chunks retrievés** au moment du RAG (module 12), ou en couche **gold dérivée** versionnée — jamais en remplacement du silver.

## Conséquences

**Positives**

- Citations honnêtes (`s3_uri` → texte original).
- Prêt pour RU/ZH/AR : analyzers dédiés ajoutés au fil des flux, sans re-traduire tout le lake.
- Filtre `presslake search "…" --lang fr` sur corpus mixte.

**Négatives**

- Index OpenSearch plus riche ; re-index après changement de mapping (`presslake index --recreate`).
- Silver existant sans champs langue : re-parse ou fallback `feed_lang` à l'indexation.

## Hors scope (pour l'instant)

- Traduction ingest FR/EN only.
- Analyzers `russian`, `smartcn`, `arabic` (ajoutés quand les flux correspondants entrent dans `feeds.yml`).
- Détection de la langue de la **requête** utilisateur (module 12).

## Liens

- `docs/modules/10-opensearch.md` — filtre `--lang`
- ADR 0006 — retrieve hybride lexical + vectoriel
