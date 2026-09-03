"""
Point d'entrée CLI : uv run presslake <commande>
"""

import argparse
import sys

from presslake.catalog.db import init_schema
from presslake.contracts.run import run_validate
from presslake.ingest.feeds import load_feeds
from presslake.ingest.poll import poll_all_dedup
from presslake.observability.alerts import evaluate_ops_status
from presslake.parse.run import parse_all, parse_from_kafka
from presslake.retrieve.hybrid import retrieve_passages
from presslake.rag.chat import answer_question
from presslake.rag.ollama import OllamaError, check_ollama_available
from presslake.rag.config import ollama_model
from presslake.search.index import search_articles
from presslake.search.run import index_all
from presslake.vector.collection import search_similar
from presslake.vector.embed import embed_query
from presslake.vector.run import embed_all
from presslake.storage.postgres import get_connection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="presslake",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Datalake presse — ingest RSS, lake médaillon, RAG sourcé.",
        epilog=(
            "De A à Z (commandes commentées) :  uv run presslake guide\n"
            "Ingest quotidien :                 uv run presslake pipeline\n"
            "Script shell :                     ./scripts/presslake-a-to-z.sh"
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "guide",
        help="Afficher le mode d'emploi A→Z (chaque commande commentée).",
        description=(
            "Imprime le runbook : infra Docker, db init, poll/parse/index/embed, "
            "retrieve/chat/eval, Langfuse. Rien n'est exécuté."
        ),
    )

    pipeline_parser = sub.add_parser(
        "pipeline",
        help="Enchaîner poll → parse → index → embed.",
        description=(
            "Pipeline quotidien. poll écrit le bronze ; parse le silver ; "
            "index ouvre BM25 ; embed pousse les chunks dans Qdrant. "
            "N'inclut pas docker compose ni le chat."
        ),
    )
    pipeline_parser.add_argument(
        "--from-kafka",
        action="store_true",
        help="parse via topic presslake.articles.ingested au lieu du catalogue.",
    )
    pipeline_parser.add_argument(
        "--replay",
        action="store_true",
        help="Avec --from-kafka : rejouer depuis l'offset 0.",
    )
    pipeline_parser.add_argument("--limit", type=int, default=None)
    pipeline_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recréer l'index OpenSearch et la collection Qdrant avant d'écrire.",
    )
    pipeline_parser.add_argument(
        "--skip-poll",
        action="store_true",
        help="Ne pas re-fetcher les RSS (parse + index + embed seulement).",
    )
    pipeline_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Logs [NEW]/[PARSED]/… au lieu de la barre de progression.",
    )

    sub.add_parser(
        "poll",
        help="Poll RSS → bronze MinIO + catalogue Postgres.",
        description=(
            "Lit config/feeds.yml, télécharge chaque flux, déduplique (seen + URL), "
            "écrit un JSON immuable dans MinIO (partition source=/dt=) et upsert "
            "une ligne catalogue (statut fetched). 2e poll sans nouvel item = 0 écriture."
        ),
    )

    parse_parser = sub.add_parser(
        "parse",
        help="Parser bronze → silver (texte extractible).",
        description=(
            "Pour chaque article fetched : extraire titre/texte (permalink ou résumé RSS), "
            "écrire l'enveloppe silver dans MinIO, passer le statut à parsed. "
            "Le LLM ne lit jamais le HTML bronze, seulement ce silver."
        ),
    )
    parse_parser.add_argument("--limit", type=int, default=None)
    parse_parser.add_argument(
        "--from-kafka",
        action="store_true",
        help="Consommer presslake.articles.ingested au lieu du catalogue.",
    )
    parse_parser.add_argument(
        "--replay",
        action="store_true",
        help="Rejeu depuis l'offset 0 (avec --from-kafka).",
    )

    validate_parser = sub.add_parser(
        "validate",
        help="Valider les contrats JSON Schema.",
        description=(
            "examples = fichiers sample du repo. lake = objets bronze/silver déjà "
            "écrits dans MinIO (échantillon --limit). Échoue si le schéma n'est pas respecté."
        ),
    )
    validate_parser.add_argument("target", choices=["examples", "lake"])
    validate_parser.add_argument("--limit", type=int, default=10)

    serve_parser = sub.add_parser(
        "serve",
        help="API FastAPI (catalogue, retrieve, chat, /v1, /metrics).",
        description=(
            "Ouvre :8000. Open WebUI doit pointer vers http://<hôte>:8000/v1 "
            "(pas vers Ollama). --host 0.0.0.0 si l'UI tourne dans Docker."
        ),
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    ops_parser = sub.add_parser(
        "ops",
        help="Surveillance ops.",
        description="Alerte si le catalogue n'a plus d'écriture depuis PRESSLAKE_STALE_HOURS (défaut 6 h).",
    )
    ops_sub = ops_parser.add_subparsers(dest="ops_command", required=True)
    ops_sub.add_parser("status", help="Dernière écriture + alerte 6 h.")

    db_parser = sub.add_parser(
        "db",
        help="Opérations base de données.",
        description="init : crée / aligne le schéma catalogue (articles, worker_runs, …).",
    )
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("init", help="Applique schema.sql + migrations.")

    index_parser = sub.add_parser(
        "index",
        help="Indexer silver → OpenSearch (BM25).",
        description=(
            "Lit les articles parsed/indexed, pousse titre+texte dans presslake-articles. "
            "--recreate si tu as changé le mapping (ex. champs langue)."
        ),
    )
    index_parser.add_argument("--limit", type=int, default=None)
    index_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Supprime et recrée l'index (re-indexe parsed + indexed).",
    )

    search_parser = sub.add_parser(
        "search",
        help="Recherche BM25 OpenSearch (mots exacts).",
        description="Ne lance pas le LLM. Utile pour un « mot rare » ou un nom propre.",
    )
    search_parser.add_argument("query", help="Termes à chercher.")
    search_parser.add_argument("--limit", type=int, default=5)
    search_parser.add_argument(
        "--lang",
        choices=["fr", "en"],
        default=None,
        help="Filtre content_lang + analyzer dédié.",
    )

    embed_parser = sub.add_parser(
        "embed",
        help="Chunker + embedder silver → Qdrant.",
        description=(
            "Découpe le texte (chunks citables), calcule les vecteurs, upsert "
            "la collection presslake-chunks. Statut catalogue → embedded."
        ),
    )
    embed_parser.add_argument("--limit", type=int, default=None)
    embed_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Supprime et recrée la collection (re-embed indexed + embedded).",
    )

    similar_parser = sub.add_parser(
        "similar",
        help="Recherche sémantique Qdrant (paraphrase).",
        description="Cosine sur les chunks. Complément du BM25 ; le chat fusionne les deux (retrieve).",
    )
    similar_parser.add_argument("query", help="Question ou phrase en langage naturel.")
    similar_parser.add_argument("--limit", type=int, default=5)
    similar_parser.add_argument(
        "--lang",
        choices=["fr", "en"],
        default=None,
        help="Filtre content_lang dans Qdrant.",
    )

    retrieve_parser = sub.add_parser(
        "retrieve",
        help="Retrieve hybride BM25 + Qdrant (sans LLM).",
        description=(
            "Même retrieve que le chat : fusion RRF, seuil RAG_MIN_VECTOR_SCORE. "
            "Debug : --bm25-only, --vector-only, --raw (voisins Qdrant non filtrés)."
        ),
    )
    retrieve_parser.add_argument("query", help="Question ou mots-clés.")
    retrieve_parser.add_argument("--limit", type=int, default=10)
    retrieve_parser.add_argument(
        "--lang",
        choices=["fr", "en"],
        default=None,
        help="Filtre content_lang sur les deux moteurs.",
    )
    retrieve_parser.add_argument(
        "--bm25-only",
        action="store_true",
        help="OpenSearch uniquement (debug).",
    )
    retrieve_parser.add_argument(
        "--vector-only",
        action="store_true",
        help="Qdrant uniquement (debug).",
    )
    retrieve_parser.add_argument(
        "--raw",
        action="store_true",
        help="Ne pas filtrer les voisins Qdrant sous RAG_MIN_VECTOR_SCORE.",
    )

    chat_parser = sub.add_parser(
        "chat",
        help="Chat RAG sur le corpus (Ollama local).",
        description=(
            "retrieve → prompt avec extraits [1]…[k] → Ollama → réponse + footer sources. "
            "Sans question : mode interactif. Refus si aucun passage pertinent."
        ),
    )
    chat_parser.add_argument("question", nargs="?", default=None, help="Question (mode one-shot).")
    chat_parser.add_argument("--limit", type=int, default=None, help="Nombre de passages retrieve.")
    chat_parser.add_argument("--lang", choices=["fr", "en"], default=None)
    chat_parser.add_argument(
        "--retrieve-only",
        action="store_true",
        help="Afficher les passages sans appeler Ollama.",
    )

    eval_parser = sub.add_parser(
        "eval",
        help="Jeu d'eval RAG (retrieve / refus / citations).",
        description=(
            "Charge config/eval/rag-v1.yml. --skip-llm = retrieve seul (pas d'Ollama). "
            "Exit 1 s'il reste des cas KO. Traces Langfuse si LANGFUSE_TRACING_ENABLED=true."
        ),
    )
    eval_parser.add_argument(
        "--set",
        dest="eval_set",
        default=None,
        help="Fichier YAML (défaut config/eval/rag-v1.yml).",
    )
    eval_parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Scorer le retrieve seul (pas d'Ollama).",
    )
    eval_parser.add_argument("--limit", type=int, default=None)
    eval_parser.add_argument("--lang", choices=["fr", "en"], default=None)

    sub.add_parser(
        "mcp",
        help="Serveur MCP stdio (outils search + read).",
        description=(
            "Expose le corpus à un agent (Cursor, Claude, …) via stdin/stdout. "
            "Ne pas lancer à la main sauf debug : le host MCP spawn le process. "
            "Aucun print sur stdout (protocole JSON-RPC)."
        ),
    )

    return parser


def _print_retrieved_passages(passages: list, *, lang: str | None = None) -> None:
    if not passages:
        print("Aucun passage.")
        return
    lang_hint = f" (lang={lang})" if lang else ""
    for rank, passage in enumerate(passages, start=1):
        title = passage.title or "(sans titre)"
        src = "+".join(passage.sources)
        cl = passage.content_lang or "?"
        chunk = (
            f" chunk {passage.chunk_index}"
            if passage.chunk_index is not None
            else ""
        )
        print(
            f"{rank}. [RRF {passage.score:.4f}] [{src}] {passage.feed_id} [{cl}]{lang_hint} "
            f"|{chunk} {title[:55]}"
        )
        if passage.canonical_url:
            print(f"   {passage.canonical_url}")
        text = (passage.text or "")[:140]
        if text:
            print(f"   … {text}…")
        if passage.silver_s3_uri:
            print(f"   silver: {passage.silver_s3_uri}")


def _run_serve(host: str, port: int, reload: bool) -> None:
    import uvicorn

    uvicorn.run("presslake.api.app:app", host=host, port=port, reload=reload)


def _run_ops_status() -> int:
    """Affiche l'état ops ; code 1 si stale (pour scripts cron)."""
    with get_connection() as conn:
        status = evaluate_ops_status(conn)

    print(status.message)
    if status.last_write_at:
        print(f"Dernière écriture : {status.last_write_at.isoformat()}")
        print(f"Il y a            : {status.seconds_since_write // 3600}h {(status.seconds_since_write % 3600) // 60}min")
    print(f"Articles          : {status.articles_total}")
    print(f"Stale             : {status.stale}")

    return 1 if status.stale else 0


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.command == "guide":
        from presslake.guide import GUIDE_TEXT

        print(GUIDE_TEXT)
        return

    if args.command == "pipeline":
        from presslake.pipeline import run_ingest_pipeline

        try:
            run_ingest_pipeline(
                from_kafka=args.from_kafka,
                replay=args.replay,
                limit=args.limit,
                recreate=args.recreate,
                skip_poll=args.skip_poll,
                verbose=args.verbose,
            )
        except ValueError as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            sys.exit(2)
        return

    if args.command == "poll":
        poll_all_dedup(load_feeds())

    elif args.command == "parse":
        if args.replay and not args.from_kafka:
            print("Erreur : --replay nécessite --from-kafka.", file=sys.stderr)
            sys.exit(2)
        if args.from_kafka:
            parse_from_kafka(replay=args.replay, limit=args.limit)
        else:
            parse_all(limit=args.limit)

    elif args.command == "validate":
        sys.exit(run_validate(target=args.target, limit=args.limit))

    elif args.command == "serve":
        _run_serve(host=args.host, port=args.port, reload=args.reload)

    elif args.command == "ops" and args.ops_command == "status":
        sys.exit(_run_ops_status())

    elif args.command == "db" and args.db_command == "init":
        with get_connection() as conn:
            init_schema(conn)
        print("Schéma catalogue initialisé.")

    elif args.command == "index":
        index_all(limit=args.limit, recreate=args.recreate)

    elif args.command == "search":
        from presslake.search.client import get_opensearch_client

        hits = search_articles(
            get_opensearch_client(),
            args.query,
            limit=args.limit,
            lang=args.lang,
        )
        if not hits:
            print("Aucun résultat.")
            return
        lang_hint = f" (lang={args.lang})" if args.lang else ""
        for rank, hit in enumerate(hits, start=1):
            title = hit.get("title") or "(sans titre)"
            cl = hit.get("content_lang") or "?"
            print(f"{rank}. [{hit['score']:.2f}] {hit['feed_id']} [{cl}]{lang_hint} | {title[:70]}")
            if hit.get("canonical_url"):
                print(f"   {hit['canonical_url']}")
            if hit.get("snippet"):
                print(f"   … {hit['snippet'][:120]}…")

    elif args.command == "embed":
        embed_all(limit=args.limit, recreate=args.recreate)

    elif args.command == "similar":
        from presslake.vector.client import get_qdrant_client

        vector = embed_query(args.query)
        hits = search_similar(
            get_qdrant_client(),
            vector,
            limit=args.limit,
            lang=args.lang,
        )
        if not hits:
            print("Aucun résultat.")
            return
        lang_hint = f" (lang={args.lang})" if args.lang else ""
        for rank, hit in enumerate(hits, start=1):
            title = hit.get("title") or "(sans titre)"
            cl = hit.get("content_lang") or "?"
            print(
                f"{rank}. [{hit['score']:.3f}] {hit['feed_id']} [{cl}]{lang_hint} "
                f"| chunk {hit.get('chunk_index')} | {title[:55]}"
            )
            if hit.get("canonical_url"):
                print(f"   {hit['canonical_url']}")
            text = (hit.get("text") or "")[:140]
            if text:
                print(f"   … {text}…")
            if hit.get("silver_s3_uri"):
                print(f"   silver: {hit['silver_s3_uri']}")

    elif args.command == "retrieve":
        passages = retrieve_passages(
            args.query,
            limit=args.limit,
            lang=args.lang,
            bm25_only=args.bm25_only,
            vector_only=args.vector_only,
            skip_min_score=args.raw,
        )
        _print_retrieved_passages(passages, lang=args.lang)

    elif args.command == "chat":
        _run_chat(
            question=args.question,
            limit=args.limit,
            lang=args.lang,
            retrieve_only=args.retrieve_only,
        )

    elif args.command == "eval":
        sys.exit(
            _run_eval(
                set_path=args.eval_set,
                skip_llm=args.skip_llm,
                limit=args.limit,
                lang=args.lang,
            )
        )

    elif args.command == "mcp":
        from presslake.mcp.server import run_stdio

        run_stdio()


def _run_eval(
    *,
    set_path: str | None,
    skip_llm: bool,
    limit: int | None,
    lang: str | None,
) -> int:
    from presslake.eval.run import format_report, run_eval
    from presslake.eval.tracing import tracing_enabled

    if not skip_llm and not check_ollama_available():
        print(
            f"Ollama inaccessible — `ollama serve` / `ollama pull {ollama_model()}`, "
            "ou relancer avec --skip-llm.",
            file=sys.stderr,
        )
        return 1

    try:
        eval_set, scores = run_eval(
            set_path=set_path,
            skip_llm=skip_llm,
            limit=limit,
            lang=lang,
        )
    except OllamaError as exc:
        print(f"Erreur Ollama : {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Jeu d'eval illisible : {exc}", file=sys.stderr)
        return 2

    print(format_report(eval_set, scores))
    if tracing_enabled():
        print("\nTraces envoyées vers Langfuse (LANGFUSE_BASE_URL).")
    failed = sum(1 for s in scores if not s.ok)
    return 1 if failed else 0


def _run_chat(
    *,
    question: str | None,
    limit: int | None,
    lang: str | None,
    retrieve_only: bool,
) -> None:
    if not retrieve_only and not check_ollama_available():
        print(
            f"Ollama inaccessible — lancer `ollama serve` puis `ollama pull {ollama_model()}`.",
            file=sys.stderr,
        )
        sys.exit(1)

    def _ask_one(q: str) -> None:
        try:
            result = answer_question(
                q,
                limit=limit,
                lang=lang,
                skip_llm=retrieve_only,
            )
        except OllamaError as exc:
            print(f"Erreur Ollama : {exc}", file=sys.stderr)
            return

        if result.passages:
            print("\n--- Sources retrieve ---")
            for i, p in enumerate(result.passages, start=1):
                print(f"[{i}] {p.citation_label()} ({'+'.join(p.sources)})")
                if p.silver_s3_uri:
                    print(f"    {p.silver_s3_uri}")
        print(f"\n{result.answer}\n")

    if question:
        _ask_one(question)
        return

    print("PressLake chat (corpus RSS). Tape 'quit' pour quitter.\n")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in {"quit", "exit", "q"}:
            break
        _ask_one(line)
