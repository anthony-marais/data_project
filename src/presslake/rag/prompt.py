"""Construction du prompt RAG avec citations."""

from presslake.retrieve.types import RetrievedPassage

REFUSAL_MESSAGE = (
    "Je n'ai trouvé aucun passage pertinent dans le corpus PressLake pour répondre "
    "à cette question. Je ne peux pas inventer d'information hors de vos articles indexés."
)

SYSTEM_PROMPT = """Tu es l'assistant PressLake. Tu réponds UNIQUEMENT à partir des extraits \
du corpus presse fournis ci-dessous.

Règles strictes :
- Cite tes sources avec [1], [2], etc. correspondant aux numéros des extraits.
- Si les extraits ne suffisent pas, dis-le clairement — ne complète pas par ta connaissance générale.
- Ne invente jamais d'URL, de date ou de citation absente des extraits.
- Réponds dans la langue de la question sauf si l'utilisateur demande autrement.
- Sois concis et factuel."""


def format_passages_for_prompt(passages: list[RetrievedPassage]) -> str:
    """Numérote les extraits pour le prompt et les citations."""
    blocks: list[str] = []
    for index, passage in enumerate(passages, start=1):
        title = passage.title or "(sans titre)"
        source = "+".join(passage.sources)
        uri = passage.silver_s3_uri or "(uri inconnue)"
        blocks.append(
            f"[{index}] ({source}) {title}\n"
            f"    feed: {passage.feed_id or '?'}\n"
            f"    silver: {uri}\n"
            f"    extrait: {passage.text.strip()}"
        )
    return "\n\n".join(blocks)


def build_chat_messages(
    user_question: str,
    passages: list[RetrievedPassage],
) -> list[dict[str, str]]:
    """
    Messages au format Ollama / OpenAI pour un tour RAG one-shot.

    L'historique multi-tours pourra être ajouté au module agentique (ADR 0006).
    """
    context = format_passages_for_prompt(passages)
    user_content = (
        f"Extraits du corpus :\n\n{context}\n\n"
        f"Question : {user_question.strip()}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def format_sources_footer(passages: list[RetrievedPassage]) -> str:
    """Bloc markdown des sources — ajouté en fin de réponse assistant."""
    if not passages:
        return ""
    lines = ["\n\n---\n**Sources PressLake**"]
    for index, passage in enumerate(passages, start=1):
        title = passage.title or "(sans titre)"
        url = passage.canonical_url or passage.silver_s3_uri or "?"
        lines.append(f"- [{index}] {title} — {url}")
    return "\n".join(lines)
