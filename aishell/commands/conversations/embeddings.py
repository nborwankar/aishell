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


def embed_texts(texts):
    """Generate embeddings with search_document: prefix."""
    model = get_model()
    prefixed = [f"search_document: {t}" for t in texts]
    embeddings = model.encode(
        prefixed, show_progress_bar=False, normalize_embeddings=True
    )
    return embeddings.tolist()
