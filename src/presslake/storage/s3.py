"""
Client S3 compatible MinIO.

MinIO expose une API S3. boto3 sans endpoint_url viserait AWS ;
on charge les credentials depuis .env (module 01 + 03).
"""

import os
from functools import lru_cache

import boto3
from botocore.client import BaseClient, Config
from dotenv import load_dotenv

# Charge .env à l'import (racine du repo quand on lance uv run presslake).
load_dotenv()


@lru_cache(maxsize=1)
def get_s3_client() -> BaseClient:
    """
    Fabrique un client boto3 S3 pointant vers MinIO local.

    lru_cache : un seul client par processus (poll_all_dedup ne recrée pas
    la connexion à chaque article).

    Variables d'environnement requises :
      - MINIO_ENDPOINT (ex. http://localhost:9000)
      - MINIO_ROOT_USER
      - MINIO_ROOT_PASSWORD

    region_name=us-east-1 est exigé par boto3 mais ignoré par MinIO.
    """
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def get_bucket() -> str:
    """Nom du bucket lake (défaut : presslake, créé par minio-init dans Compose)."""
    return os.environ.get("MINIO_BUCKET", "presslake")


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """
    Décompose s3://bucket/key en (bucket, key).

    Raises:
        ValueError: si le format n'est pas s3://…
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"URI S3 invalide : {s3_uri!r}")

    parts = s3_uri[5:].split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"URI S3 invalide : {s3_uri!r}")

    return parts[0], parts[1]


def get_json_object(client: BaseClient, bucket: str, key: str) -> dict:
    """
    Lit un objet JSON depuis MinIO et le parse.

    Utilisé par le parser silver pour charger le bronze.
    """
    import json

    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


def put_json_object(
    client: BaseClient,
    bucket: str,
    key: str,
    payload: dict,
) -> str:
    """
    Écrit un dict en JSON dans MinIO.

    Returns:
        s3_uri de l'objet écrit.
    """
    import json

    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    return f"s3://{bucket}/{key}"
