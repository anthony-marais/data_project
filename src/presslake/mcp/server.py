"""Serveur MCP stdio — outils search + read (même index que le chat)."""

from __future__ import annotations

from mcp.server import MCPServer

from presslake.mcp.tools import read_silver, search_corpus

INSTRUCTIONS = """
PressLake : corpus presse RSS (silver MinIO + OpenSearch + Qdrant).
Outils :
- search : retrieve hybride, passages citables (pas de LLM).
- read : texte silver complet (tronqué). Interdit : bronze / HTML brut.
Cite toujours silver_s3_uri ou canonical_url. N'invente pas hors corpus.
""".strip()


def create_server() -> MCPServer:
    server = MCPServer(
        name="presslake",
        version="0.1.0",
        instructions=INSTRUCTIONS,
        log_level="WARNING",
    )

    @server.tool(
        name="search",
        description=(
            "Recherche dans le corpus PressLake (BM25 + vecteurs, fusion RRF). "
            "Retourne des extraits JSON avec content_hash et silver_s3_uri pour read."
        ),
    )
    def search(query: str, limit: int = 5, lang: str | None = None) -> str:
        return search_corpus(query, limit=limit, lang=lang)

    @server.tool(
        name="read",
        description=(
            "Lit un article silver (texte extractible). "
            "Passer content_hash (issu de search) ou silver_s3_uri. Jamais le bronze."
        ),
    )
    def read(
        content_hash: str | None = None,
        silver_s3_uri: str | None = None,
        max_chars: int = 4000,
    ) -> str:
        return read_silver(
            content_hash=content_hash,
            silver_s3_uri=silver_s3_uri,
            max_chars=max_chars,
        )

    return server


def run_stdio() -> None:
    """Bloque : JSON-RPC MCP sur stdin/stdout (ne pas print() sur stdout)."""
    create_server().run(transport="stdio")
