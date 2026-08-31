"""
Package PressLake — datalake presse (RSS → MinIO → RAG sourcé).

Le CLI est exposé via main(), référencé dans pyproject.toml :
  [project.scripts]
  presslake = "presslake:main"
"""

from presslake.cli import main

__all__ = ["main"]
