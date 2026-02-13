"""Embedding utilities for conversation search.

Uses mlx-embedding-models for native Apple Silicon GPU acceleration.
Lazy-loads nomic-embed-text-v1.5 on first use.
"""

import logging
import os

# Prevent TF import error from transformers transitive dependency
os.environ.setdefault("USE_TF", "0")

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "nomic-text-v1.5"
EMBEDDING_DIM = 768

# Lazy-loaded embedding model
_model = None


def get_model():
    """Load nomic-embed-text-v1.5 via MLX on first use."""
    global _model
    if _model is None:
        from mlx_embedding_models.embedding import EmbeddingModel

        logger.info(f"Loading {EMBEDDING_MODEL} (MLX)...")
        _model = EmbeddingModel.from_registry(EMBEDDING_MODEL)
        logger.info(f"Model loaded (dim={EMBEDDING_DIM})")
    return _model


def embed_texts(texts, batch_size=64):
    """Generate embeddings with search_document: prefix.

    Uses MLX for native Apple Silicon acceleration.
    Truncation to 2048 tokens handled by the model's tokenizer.
    Normalization configured in registry (normalize=True).
    """
    model = get_model()
    prefixed = [f"search_document: {t}" for t in texts]
    embeddings = model.encode(prefixed, batch_size=batch_size, show_progress=False)
    return embeddings.tolist()
