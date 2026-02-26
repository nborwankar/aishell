# TODO: Submit PR to taylorai/mlx_embedding_models

**Status**: Deferred — finish aishell load/search first
**Upstream issue**: https://github.com/taylorai/mlx_embedding_models/issues/7
**Repo**: https://github.com/taylorai/mlx_embedding_models

## What to Fix

`embedding.py` line 15 — `SEQ_LENS` is hardcoded with max 512, but models like
nomic-text-v1.5 have `max_length: 2048` in the registry. Any input >512 tokens
crashes in `_sort_inputs()`.

## Proposed Upstream Fix

Make SEQ_LENS dynamic based on the model's max_length, not a module-level constant:

```python
# In EmbeddingModel.__init__ or encode(), generate buckets from self.max_length:
def _get_seq_lens(self):
    base = np.arange(16, 128, 16).tolist() + np.arange(128, 512, 32).tolist()
    extended = list(range(512, self.max_length + 1, 256))
    return sorted(set(base + extended))
```

This is better than our monkey-patch because it adapts to any model's max_length
rather than hardcoding specific values.

## Steps

1. Fork `taylorai/mlx_embedding_models`
2. Fix `embedding.py` — make SEQ_LENS per-model based on max_length
3. Add test with nomic-text-v1.5 and input >512 tokens
4. Submit PR referencing issue #7

## Prerequisites

- Verify our monkey-patch works in production (full load + search)
- Confirm no memory leaks with extended SEQ_LENS
- Confirm no TF transitive import issues remain
