"""Shared conversation export infrastructure.

Provides schema conversion, database loading, embedding generation,
and manifest management for multi-provider conversation exports.
"""

from .schema import slugify, generate_conv_id, convert_to_schema, ROLE_MAP
from .db import ensure_database, load_conversation, SCHEMA_SQL, DB_NAME
from .embeddings import get_model, embed_texts, EMBEDDING_MODEL, EMBEDDING_DIM
from .manifest import load_manifest, save_manifest, already_exported

__all__ = [
    "slugify",
    "generate_conv_id",
    "convert_to_schema",
    "ROLE_MAP",
    "ensure_database",
    "load_conversation",
    "SCHEMA_SQL",
    "DB_NAME",
    "get_model",
    "embed_texts",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "load_manifest",
    "save_manifest",
    "already_exported",
]
