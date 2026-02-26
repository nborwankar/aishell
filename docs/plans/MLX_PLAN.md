# MLX Embedding Migration Plan

## Current State (broken)

- `embeddings.py` was switched to `mlx-embedding-models` mid-session
- `conversations_raw` is truncated (1 row), `turn_embeddings` is empty
- The MLX library crashes on inputs >512 tokens

## Problem Analysis

### The Core Bug: SEQ_LENS vs max_length Mismatch

```
mlx-embedding-models internals:

  SEQ_LENS = [16, 32, 48, ... 480, 512]     ← hardcoded max 512
  nomic registry: max_length = 2048          ← model supports 2048

  _tokenize():  truncates to max_length=2048  ✓ (tokenizer does its job)
  _sort_inputs(): rounds token count up to nearest SEQ_LENS value
                  → any input >512 tokens → IndexError (no SEQ_LEN >= l)
```

The tokenizer correctly tokenizes up to 2048 tokens, but the batching
system only handles sequences up to 512. **This is a library bug.**

### Workarounds Evaluated

| Approach | Pros | Cons |
|----------|------|------|
| **A. Truncate to ~2000 chars** | Simple, works now | Loses 75% of nomic's 2048-token context window vs sentence-transformers |
| **B. Monkey-patch SEQ_LENS** | Uses full 2048 context | Fragile, could break on library update |
| **C. Fix upstream (PR)** | Proper fix | Blocks on maintainer, library last updated Sep 2024 |
| **D. Use Blaizzy/mlx-embeddings** | Alternative MLX lib | Different API, also depends on transformers, less tested with nomic |
| **E. Stay with sentence-transformers** | Proven, 2048 tokens, mature | PyTorch/MPS memory issues (fixable), TF import noise |

### Dependency Chain Comparison

```
sentence-transformers path (CURRENT WORKING):
  sentence-transformers → transformers → torch (MPS)
  - TF imported transitively (USE_TF=0 fixes it)
  - MPS memory managed via torch.mps.empty_cache()
  - Full 2048-token context
  - Mature, well-tested

mlx-embedding-models path (BROKEN):
  mlx-embedding-models → transformers (weight loading) → mlx (compute)
  - ALSO imports TF transitively (same USE_TF=0 fix needed)
  - ALSO depends on numpy (returns np.ndarray)
  - SEQ_LENS bug limits to 512 tokens
  - Library last updated Sep 2024, 0.0.11
```

**Key insight**: Both paths depend on `transformers`. The MLX library
does NOT eliminate the transformers/TF dependency — it only replaces
PyTorch with MLX for the forward pass.

## Recommendation

**Option B (monkey-patch SEQ_LENS)** — extend to cover 2048 tokens.

Rationale:
- MLX is genuinely better on Apple Silicon (unified memory, no MPS leaks)
- The fix is 3 lines and the risk is low (SEQ_LENS is just a batching hint)
- We keep full 2048-token context (same as sentence-transformers)
- If the library updates and fixes this, we remove the patch

### The Patch

```python
# In embeddings.py, before model creation:
import mlx_embedding_models.embedding as _mlx_emb
_EXTENDED_SEQ_LENS = sorted(set(
    _mlx_emb.SEQ_LENS + [640, 768, 896, 1024, 1280, 1536, 1792, 2048]
))
_mlx_emb.SEQ_LENS = _EXTENDED_SEQ_LENS
```

This extends the batching buckets up to 2048 to match the nomic model's
actual context window. The library will pad shorter sequences to the
nearest bucket (same as before, just with more buckets).

## Implementation Steps

### Step 1: Fix embeddings.py
- Keep MLX backend
- Add SEQ_LENS monkey-patch in `get_model()` before loading
- Keep `os.environ.setdefault("USE_TF", "0")`
- No text truncation needed (model tokenizer truncates to 2048 natively)

### Step 2: Reload all data
- Tables are already truncated
- Run `aishell conversations load --skip-embeddings` (fast, ~2 min)
- Run `aishell conversations load` (with embeddings, ~10-20 min)

### Step 3: Verify
- `SELECT source, count(*) FROM conversations_raw GROUP BY source`
  → expect: gemini 33, chatgpt 811, claude ~920
- `SELECT count(*) FROM turn_embeddings`
  → expect: ~11,600
- `aishell conversations search "manifold geometry"` → returns results

### Step 4: Commit
- Single commit with embeddings.py fix + comment explaining the patch

## What NOT to Change
- db.py — working, no changes needed
- cli.py — working (except the table width cosmetic issue, defer)
- Provider files — working, no changes needed
- __init__.py — working, no changes needed

## Risk Assessment
- **Low risk**: SEQ_LENS is a batching optimization, not a correctness concern
- **Rollback**: If MLX produces bad embeddings, revert embeddings.py to
  sentence-transformers version (one file change) and re-embed
- **Compatibility**: Both libraries use the same nomic-embed-text-v1.5 weights
  from HuggingFace, so embeddings should be numerically close (not identical
  due to float32 vs MLX precision, but close enough for cosine similarity)
