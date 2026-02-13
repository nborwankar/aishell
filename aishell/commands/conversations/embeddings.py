"""Embedding utilities for conversation search.

Lazy-loads nomic-embed-text-v1.5 and provides text embedding functions.
"""

import logging

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768

# Lazy-loaded embedding model
_model = None


def get_model():
    """Load nomic-embed-text-v1.5 on first use."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading {EMBEDDING_MODEL}...")
        _model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)
        logger.info(f"Model loaded (dim={_model.get_sentence_embedding_dimension()})")
    return _model


def embed_texts(texts, batch_size=16):
    """Generate embeddings with search_document: prefix.

    Truncates to ~2000 tokens (8000 chars) to stay within the model's
    2048-token context window and avoid MPS OOM on long content.
    """
    import torch

    model = get_model()
    # Truncate to ~2000 tokens (model max is 2048)
    MAX_CHARS = 8000
    prefixed = [f"search_document: {t[:MAX_CHARS]}" for t in texts]
    embeddings = model.encode(
        prefixed,
        show_progress_bar=False,
        normalize_embeddings=True,
        batch_size=batch_size,
    )
    result = embeddings.tolist()

    # Free MPS GPU memory between calls
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()

    return result
