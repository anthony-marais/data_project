"""MLflow opt-in — tracking file local par défaut (pas de cloud)."""

from __future__ import annotations

import os
from pathlib import Path

from presslake.mlops.recall import RecallReport

_REPO = Path(__file__).resolve().parents[3]


def tracking_uri() -> str | None:
    raw = os.environ.get("MLFLOW_TRACKING_URI", "").strip()
    if raw:
        return raw
    if os.environ.get("MLFLOW_ENABLED", "").strip().lower() in {"1", "true", "yes"}:
        return (_REPO / "mlruns").as_uri()
    return None


def log_recall(report: RecallReport) -> str | None:
    """
    Enregistre un run MLflow. Returns l'URI tracking utilisée, ou None si désactivé.
    """
    uri = tracking_uri()
    if not uri:
        return None

    try:
        import mlflow
    except ImportError:
        raise RuntimeError(
            "mlflow n'est pas installé — `uv add mlflow` ou omettre --mlflow"
        ) from None

    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("presslake-embed")
    with mlflow.start_run(run_name=report.model.split("/")[-1][:80]):
        mlflow.log_param("embedding_model", report.model)
        mlflow.log_param("vector_size", report.vector_size)
        mlflow.log_param("k", report.k)
        mlflow.log_param("eval_set", report.eval_set)
        mlflow.log_metric("recall_at_k", report.recall_at_k)
        mlflow.log_metric("n_hits", report.n_hits)
        mlflow.log_metric("n_grounded", report.n_grounded)
        mlflow.log_metric("n_refuse_ok", report.n_refuse_ok)
    return uri
