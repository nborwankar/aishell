# SCIR / MLIR Dialect Definitions

*Extracted from: Server-Side WASM Components conversation (ChatGPT)*

The compiler intermediate representation layer. SCIR is a custom MLIR dialect
that represents semantic operators (embed, search, rerank) as first-class IR nodes,
enabling optimization, verification, and lowering to WASM/native targets.

---

## VQL → SCIR → Execution Pipeline (Turn 10, assistant)

```text
module A instantiates B, C with parameters → elaborated netlist
```

```text
retrieval_cell instantiates Embedder, ANN, Reranker → executable graph
```

```text
nodes = operators
edges = wires
attributes = timing/resource constraints
```

```text
nodes = semantic operators
edges = typed dataflow
attributes = placement/cost/determinism
```

```text
everything synchronized to a clock edge
```

```text
retrieval_monotonicity
no_data_exfiltration
bounded_latency
```

```text
VQL  ──parse──▶  Logical Plan
                    │
                    ▼
             SCIR (netlist)
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   Optimization   Verification  Costing
        │           │           │
        └───────rewrite passes──┘
                    │
                    ▼
              Execution Graph
                    │
           WASM / Native / Remote
```

## SCIR as MLIR Dialect — Literal Implementation (Turn 12, assistant)

```text
VQL  ──▶  SCIR Dialect (MLIR)
              │
     ┌────────┼───────────────┐
     ▼                        ▼
Dataflow / Async Dialects   Affine / Linalg (when numeric)
     │                        │
     └──────────────▶ LLVM Dialect ──▶ native code (if needed)
```

```llvm
%3 = fadd float %1, %2
```

```text
VectorSearch(topk=20, metric="cosine")
```

```mlir
scir.embedder @e5_large
    {dim = 1024}
    (%input : !scir.text)
 -> (%vec : !scir.vector<1024>)

scir.ann_search @hnsw_cos
    {k = 20}
    (%vec : !scir.vector<1024>, %index : !scir.index)
 -> (%candidates : !scir.candidate_set)

scir.rerank @bge
    (%query : !scir.text, %candidates : !scir.candidate_set)
 -> (%scored : !scir.scored_set)
```

```text
vector dimensions must match
non-deterministic op cannot feed deterministic branch
placement constraints must resolve
```

```text
SCIR.embedder
   └─▶ runtime.call_component("embedder.wasm")
            └─▶ LLVM lowering for the stub
```

```text
Verilog → synthesis → FPGA bitstream
```

## MLIR Hierarchy and SCIR Type/Op Catalog (Turn 14, assistant)

```text
High-Level Dialect      (domain semantics preserved)
        ↓
Mid-Level Dialect       (structured compute)
        ↓
Low-Level Dialect       (loops, memory)
        ↓
LLVM IR                 (machine-oriented)
```

```text
Dialect: scir
Types:
  !scir.text
  !scir.vector<d>
  !scir.index
  !scir.candidate_set

Ops:
  scir.embed
  scir.search
  scir.rerank
  scir.filter
  scir.generate
```

