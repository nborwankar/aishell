# MLX Embedding Models: SEQ_LENS Bug Fix

**Date**: 2026-02-12
**Library**: `mlx-embedding-models` v0.0.11 (taylorai)
**Upstream issue**: https://github.com/taylorai/mlx_embedding_models/issues/7

## The Bug

The `mlx-embedding-models` library has a mismatch between its model registry
and its batching system:

```
registry.py:
  "nomic-text-v1.5": { "max_length": 2048, ... }   ← model supports 2048 tokens

embedding.py:
  SEQ_LENS = np.arange(16,128,16) + np.arange(128,512,32) + [512]
                                                       ↑ max bucket = 512
```

### What happens

```
_tokenize()       → truncates to max_length=2048    ✓ correct
_sort_inputs()    → rounds token count up to nearest SEQ_LENS bucket
                  → if tokens > 512, no bucket exists → IndexError

Line 242-244 in embedding.py:
  sorted_lengths = np.array([
      [x for x in SEQ_LENS if x >= l][0] for l in sorted_lengths
  ])
  # ↑ empty list when l > 512 → IndexError: list index out of range
```

### Key distinction

- **MLX the framework**: No sequence length limit. Handles arbitrary lengths.
- **mlx-embedding-models the wrapper library**: Has this hardcoded batching bug.

## Our Fix (monkey-patch)

In `embeddings.py`, before model creation:

```python
import mlx_embedding_models.embedding as _mlx_emb
_EXTENDED = sorted(set(
    _mlx_emb.SEQ_LENS + [640, 768, 896, 1024, 1280, 1536, 1792, 2048]
))
_mlx_emb.SEQ_LENS = _EXTENDED
```

This extends the batching buckets to cover the full 2048-token context window
that the nomic model actually supports. SEQ_LENS is purely a batching
optimization (pad shorter sequences to nearest bucket for efficient batching).
Extending it has no correctness implications.

## Risk Assessment

```
Risk:     LOW — SEQ_LENS is a batching hint, not a correctness concern
Rollback: Revert embeddings.py to sentence-transformers version (one file)
Removal:  If library updates and fixes this, remove the _patch_seq_lens() call
```

## Verified Against

```
File: /Users/nitin/anaconda3/lib/python3.11/site-packages/mlx_embedding_models/embedding.py
Line 15:  SEQ_LENS = np.arange(16, 128, 16).tolist() + np.arange(128, 512, 32).tolist() + [512]

File: /Users/nitin/anaconda3/lib/python3.11/site-packages/mlx_embedding_models/registry.py
Line 69-76:
  "nomic-text-v1.5": {
      "repo": "nomic-ai/nomic-embed-text-v1.5",
      "max_length": 2048,          ← confirms 2048 support
      "pooling_strategy": "mean",
      "normalize": True,
      "ndim": 768,
      "apply_ln": True,
  }
```
