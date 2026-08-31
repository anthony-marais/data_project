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
