# ADR 0002 — Contrats JSON Schema bronze / silver

- Statut : accepted
- Date : 2026-08-31
- Décideurs : anthony-marais

## Contexte

Les modules 03–05 écrivent des JSON dans MinIO (bronze puis silver) sans garde-fou formel. Sans contrat :

- un changement de champ casse le parser ou l'indexeur silencieusement ;
- on ne peut pas valider un rejeu ou un backfill ;
- l'entretien « comment garantis-tu la qualité des données ? » manque de réponse concrète.

## Décision

Chaque couche médaillon publiée dans le repo a un **JSON Schema versionné** sous `contracts/` :

- `bronze.v1.schema.json` — enveloppe ingest RSS
- `silver.v1.schema.json` — document parser

Règles :

1. `schema_version` entier dans chaque objet (v1 aujourd'hui)
2. Validation **à l'écriture** (poll, parse) via `jsonschema`
3. Commande `presslake validate` pour auditer le lake existant
4. Nouvelle version = nouveau fichier `*.v2.schema.json` + bump `schema_version` (pas de modification rétroactive)

Les ADR de process restent dans `adr/` (versionnés git). La doc pédagogique détaillée reste dans `docs/` (locale).

## Conséquences

**Positives**

- Erreurs détectées avant propagation dans le lake
- Contrats testables en CI (`validate examples` + échantillon lake)
- Séparation claire brut (bronze) / lisible (silver)

**Négatives**

- Overhead validation à chaque write (négligeable à ce volume)
- Discipline de versionning à maintenir

## Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| Protobuf / Avro | Overkill pour le MVP Python |
| Validation manuelle | Non reproductible |
| Schémas seulement dans `docs/` | `docs/` ignoré par git — pas de CI |
