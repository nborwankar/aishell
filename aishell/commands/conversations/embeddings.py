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


def _patch_seq_lens():
    """Extend mlx-embedding-models SEQ_LENS to support nomic's full 2048-token context.

    The library hardcodes SEQ_LENS with max 512, but nomic-embed-text-v1.5 supports
    2048 tokens. Without this patch, inputs >512 tokens crash in _sort_inputs().
    See: https://github.com/taylorai/mlx_embedding_models/issues/7
    See: docs/dev/MLX_BUG_FIX.md
    """
    import mlx_embedding_models.embedding as _mlx_emb

    _EXTENDED = sorted(
        set(_mlx_emb.SEQ_LENS + [640, 768, 896, 1024, 1280, 1536, 1792, 2048])
    )
    _mlx_emb.SEQ_LENS = _EXTENDED
    logger.debug(f"Patched SEQ_LENS: max={_EXTENDED[-1]} ({len(_EXTENDED)} buckets)")


def get_model():
    """Load nomic-embed-text-v1.5 via MLX on first use."""
    global _model
    if _model is None:
        _patch_seq_lens()
        from mlx_embedding_models.embedding import EmbeddingModel

        logger.info(f"Loading {EMBEDDING_MODEL} (MLX)...")
        _model = EmbeddingModel.from_registry(EMBEDDING_MODEL)
        logger.info(f"Model loaded (dim={EMBEDDING_DIM})")
    return _model


def embed_texts(texts, batch_size=64):
    """Generate embeddings with search_document: prefix.

    Uses MLX for native Apple Silicon acceleration.
    No text truncation needed — the model tokenizer truncates to 2048 natively.
    Normalization configured in registry (normalize=True).
    """
    model = get_model()
    prefixed = [f"search_document: {t}" for t in texts]
    embeddings = model.encode(prefixed, batch_size=batch_size, show_progress=False)
    return embeddings.tolist()
