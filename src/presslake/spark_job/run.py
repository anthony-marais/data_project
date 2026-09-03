"""
Backfill Spark (module 15) : silver JSON MinIO → gold parquet.

Le job Scala tourne dans Compose (profil `spark`), pas sur le chemin quotidien poll/parse.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from presslake.storage.s3 import get_bucket, get_s3_client

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[3]


def default_input_uri() -> str:
    return f"s3a://{get_bucket()}/silver"


def default_output_uri() -> str:
    return f"s3a://{get_bucket()}/gold/layer=silver_parquet"


def list_gold_keys(*, prefix: str = "gold/", max_keys: int = 50) -> list[str]:
    """Clés MinIO sous gold/ (parquet + _SUCCESS)."""
    client = get_s3_client()
    bucket = get_bucket()
    keys: list[str] = []
    token: str | None = None
    while len(keys) < max_keys:
        kwargs: dict = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": min(1000, max_keys - len(keys))}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents") or []:
            keys.append(obj["Key"])
            if len(keys) >= max_keys:
                break
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
        if not token:
            break
    return keys


def compose_run_argv(*, input_uri: str, output_uri: str, build: bool) -> list[str]:
    env_flags = [
        "-e",
        f"SPARK_INPUT={input_uri}",
        "-e",
        f"SPARK_OUTPUT={output_uri}",
    ]
    prefix = ["docker", "compose", "--profile", "spark"]
    if build:
        return prefix + ["run", "--rm", "--build", *env_flags, "spark-backfill"]
    return prefix + ["run", "--rm", *env_flags, "spark-backfill"]


def run_backfill(
    *,
    input_uri: str | None = None,
    output_uri: str | None = None,
    build: bool = False,
    dry_run: bool = False,
    list_only: bool = False,
) -> int:
    if list_only:
        keys = list_gold_keys()
        if not keys:
            print("Aucun objet sous gold/ (lancer `presslake spark` après un parse).")
            return 0
        for key in keys:
            print(key)
        print(f"\n→ {len(keys)} objet(s) (max 50)")
        return 0

    inp = input_uri or default_input_uri()
    out = output_uri or default_output_uri()
    argv = compose_run_argv(input_uri=inp, output_uri=out, build=build)

    print("Backfill Spark Scala — voie volume, pas le poll RSS.", file=sys.stderr)
    print(f"  input  {inp}", file=sys.stderr)
    print(f"  output {out}", file=sys.stderr)
    print("  " + " ".join(argv), file=sys.stderr)

    if dry_run:
        return 0

    if not (REPO_ROOT / "docker-compose.yml").is_file():
        print("docker-compose.yml introuvable (lancer depuis la racine du repo).", file=sys.stderr)
        return 2

    env = os.environ.copy()
    try:
        completed = subprocess.run(argv, cwd=REPO_ROOT, env=env, check=False)
    except FileNotFoundError:
        print("docker introuvable. Installer Docker Compose, puis reconstruire :", file=sys.stderr)
        print("  docker compose --profile spark build spark-backfill", file=sys.stderr)
        return 2

    return completed.returncode
