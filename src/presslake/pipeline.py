"""Enchaînement ingest quotidien : poll → parse → index → embed."""

from __future__ import annotations

from presslake.ingest.feeds import load_feeds
from presslake.ingest.poll import poll_all_dedup
from presslake.output import quiet_with_progress
from presslake.parse.run import parse_all, parse_from_kafka
from presslake.search.run import index_all
from presslake.vector.run import embed_all


def run_ingest_pipeline(
    *,
    from_kafka: bool = False,
    replay: bool = False,
    limit: int | None = None,
    recreate: bool = False,
    skip_poll: bool = False,
    verbose: bool = False,
) -> None:
    """Exécute le pipeline médaillon + index (barre de progression par défaut)."""
    if replay and not from_kafka:
        raise ValueError("--replay nécessite --from-kafka")

    steps: list[tuple[str, str]]
    if skip_poll:
        steps = []
    else:
        steps = [("poll", "RSS → bronze + catalogue")]
    parse_how = "Kafka → silver" if from_kafka else "bronze → silver"
    if replay:
        parse_how += " (replay)"
    steps.extend(
        [
            ("parse", parse_how),
            ("index", "silver → OpenSearch BM25"),
            ("embed", "chunks → Qdrant"),
        ]
    )

    if verbose:
        _run_steps(
            steps,
            from_kafka=from_kafka,
            replay=replay,
            limit=limit,
            recreate=recreate,
        )
        return

    _run_steps_with_bar(
        steps,
        from_kafka=from_kafka,
        replay=replay,
        limit=limit,
        recreate=recreate,
    )


def _run_one(
    name: str,
    *,
    from_kafka: bool,
    replay: bool,
    limit: int | None,
    recreate: bool,
) -> None:
    if name == "poll":
        poll_all_dedup(load_feeds())
    elif name == "parse":
        if from_kafka:
            parse_from_kafka(replay=replay, limit=limit)
        else:
            parse_all(limit=limit)
    elif name == "index":
        index_all(limit=limit, recreate=recreate)
    elif name == "embed":
        embed_all(limit=limit, recreate=recreate)


def _run_steps(
    steps: list[tuple[str, str]],
    **kwargs: object,
) -> None:
    total = len(steps)
    for i, (name, why) in enumerate(steps, start=1):
        print(f"\n>>> [{i}/{total}] {name}")
        print(f"    {why}")
        _run_one(name, **kwargs)  # type: ignore[arg-type]
    print("\nPipeline ingest terminé.")


def _run_steps_with_bar(
    steps: list[tuple[str, str]],
    **kwargs: object,
) -> None:
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    step_count = len(steps)
    # 1000 unités = pourcentage plus fluide (un article = une fraction d'étape)
    scale = 1000

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.fields[label]}"),
        BarColumn(bar_width=32),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        transient=False,
    ) as progress:
        task_id = progress.add_task("pipeline", total=scale, label="démarrage")
        state = {"index": 0}

        def on_progress(current: int, total: int | None) -> None:
            step_index = state["index"]
            base = step_index * (scale / step_count)
            span = scale / step_count
            if total and total > 0:
                frac = min(current / total, 1.0)
                detail = f"{steps[step_index][0]}  {current}/{total}"
            else:
                frac = 0.0
                detail = f"{steps[step_index][0]}  {current}"
            completed = min(base + span * frac, scale)
            percent = int(completed / scale * 100)
            progress.update(
                task_id,
                completed=completed,
                label=f"{percent}%  {detail}",
            )

        with quiet_with_progress(on_progress):
            for step_index, (name, why) in enumerate(steps):
                state["index"] = step_index
                base = step_index * (scale / step_count)
                progress.update(
                    task_id,
                    completed=base,
                    label=f"{int(base / scale * 100)}%  {name} — {why}",
                )
                _run_one(name, **kwargs)  # type: ignore[arg-type]
                done = (step_index + 1) * (scale / step_count)
                progress.update(
                    task_id,
                    completed=done,
                    label=f"{int(done / scale * 100)}%  {name} terminé",
                )

    print("Pipeline ingest terminé.")
