#!/usr/bin/env bash
# Lancé dans le conteneur spark-backfill (réseau Compose → http://minio:9000).
set -euo pipefail

INPUT="${SPARK_INPUT:-s3a://presslake/silver}"
OUTPUT="${SPARK_OUTPUT:-s3a://presslake/gold/layer=silver_parquet}"
ENDPOINT="${MINIO_S3A_ENDPOINT:-http://minio:9000}"
ACCESS="${MINIO_ROOT_USER:?MINIO_ROOT_USER manquant}"
SECRET="${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD manquant}"

# Ivy dans /tmp (user spark n'écrit pas /root).
export IVY_HOME="${IVY_HOME:-/tmp/ivy2}"
mkdir -p "$IVY_HOME"

exec /opt/spark/bin/spark-submit \
  --master "local[2]" \
  --driver-memory 1g \
  --packages "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262" \
  --conf "spark.jars.ivy=${IVY_HOME}" \
  --conf "spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem" \
  --conf "spark.hadoop.fs.s3a.endpoint=${ENDPOINT}" \
  --conf "spark.hadoop.fs.s3a.access.key=${ACCESS}" \
  --conf "spark.hadoop.fs.s3a.secret.key=${SECRET}" \
  --conf "spark.hadoop.fs.s3a.path.style.access=true" \
  --conf "spark.hadoop.fs.s3a.connection.ssl.enabled=false" \
  --conf "spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider" \
  --conf "spark.hadoop.fs.s3a.change.detection.mode=none" \
  --class presslake.SilverToParquet \
  /opt/presslake/presslake-spark.jar \
  --input "$INPUT" \
  --output "$OUTPUT"
