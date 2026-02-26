# Dolt — The Database Inside Beads

**Date**: 2026-02-20

## What is Dolt?

Dolt is a **MySQL-compatible database with git built into it**. Think "git for data." Created by DoltHub (a YC company). It is NOT SQLite.

## How it differs from SQLite

| | SQLite | Dolt |
|---|---|---|
| Wire protocol | None (embedded library) | **MySQL** (any MySQL client works) |
| Versioning | None | **commit, branch, merge, diff, log** — on table data |
| Merge granularity | N/A | **Cell-level** (not row, not file) |
| Language | C | Go |
| Storage engine | B-tree pages | Content-addressed (like git's object store) |

## Why Beads uses it

The git-like properties are the point:

- **Branching**: Beads issues can live on different git branches and Dolt branches in parallel, then merge cleanly
- **Cell-level merge**: If you change an issue title on one branch and someone changes its priority on another, Dolt merges both without conflict
- **Commit history**: Every `bd create`, `bd update`, `bd close` is a Dolt commit — full audit trail
- **Embedded mode**: Beads runs Dolt as a Go library inside the `bd` binary (no separate server process). That's why you see `.beads/dolt/` not a running daemon

## What's actually on disk

```
.beads/
├── dolt/              ← Dolt database (content-addressed chunks)
│   ├── .dolt/         ← Dolt internal state (like .git/)
│   └── ...
├── issues.jsonl       ← Export for git sync (one JSON line per issue)
└── hooks/             ← Git hook scripts
```

The Dolt DB is the source of truth for fast queries. The JSONL is a serialized export that travels through regular git for cross-machine sync.

## Dolt Resources

- **Docs**: https://docs.dolthub.com — official documentation, architecture, getting started
- **GitHub**: https://github.com/dolthub/dolt — source code, issues, README
- **DoltHub**: https://www.dolthub.com/ — hosted platform for sharing Dolt databases (like GitHub for data)
- **Architecture deep dive**: https://docs.dolthub.com/architecture/architecture — storage engine internals
- **Getting started as a database**: https://docs.dolthub.com/introduction/getting-started/database — using Dolt as a MySQL-compatible DB

## "Is Dolt a SQL interface on top of git?"

Close but not quite — and the distinction matters.

**Dolt does NOT use git underneath.** It reimplemented git's *conceptual model* (commit, branch, merge, diff, log) inside its own storage engine. The storage is content-addressed like git, but optimized for tabular data, not files.

- **"SQL interface on top of git"** → implies git stores the data, SQL queries it. That's not what happens.
- **"A relational database that natively speaks git's versioning language"** → this is Dolt.

The versioning operations are actually SQL:

```sql
SELECT * FROM dolt_log;                                    -- git log
CALL dolt_commit('-m', 'added rows');                      -- git commit
CALL dolt_checkout('-b', 'feature');                       -- git checkout -b
CALL dolt_merge('feature');                                -- git merge
SELECT * FROM dolt_diff('main', 'feature', 'mytable');    -- git diff
```

The storage engine descends from **Noms**, an earlier content-addressed database by the same team. They essentially asked: "what if we built a database where every write is automatically content-addressed, so branching and merging come for free?"

**In Beads specifically**, Dolt and git never talk to each other directly. The relationship is:

```
Dolt DB (.beads/dolt/)      ←── source of truth, fast queries
        ↓ bd sync
JSONL (.beads/issues.jsonl) ←── serialized export
        ↓ git commit/push
Git repo                    ←── how it travels to other machines
```

Real git only enters the picture at the JSONL layer.

## "Is Dolt a MySQL fork?"

No. Dolt shares **zero code** with MySQL. It is a ground-up Go implementation that speaks the MySQL wire protocol. The architecture:

```
┌─────────────────────────────┐
│  MySQL wire protocol        │  ← Any MySQL client connects here
├─────────────────────────────┤
│  go-mysql-server            │  ← SQL parser + query engine (pure Go)
├─────────────────────────────┤
│  Dolt storage engine        │  ← Prolly trees (probabilistic B-trees)
├─────────────────────────────┤
│  Noms-derived chunk store   │  ← Content-addressed, immutable chunks
└─────────────────────────────┘
```

### The layers

- **MySQL wire protocol**: Any MySQL client, driver, or ORM can connect. But it's a reimplementation of the protocol, not MySQL's code.
- **go-mysql-server**: An open-source SQL engine also built by DoltHub. Implements MySQL's query parsing and execution from scratch in Go.
- **Prolly trees**: The key innovation — probabilistic B-trees that give structural sharing between versions. When you change one row, only the affected tree nodes get new hashes; everything else is shared with the previous version. This is what makes branching cheap and cell-level merge possible.
- **Noms-derived chunk store**: Content-addressed storage inherited from Noms, an earlier database by the same team. Data is stored as immutable, hash-identified chunks (like git objects).

### Why this matters

- MySQL-*compatible* (you can use the `mysql` CLI, any MySQL driver) but not MySQL
- No GPL licensing concerns (Dolt is Apache 2.0)
- The storage engine is purpose-built for versioning — not bolted on after the fact
- Embedded mode works as a Go library (no separate server process needed)

## "Could you build a SQLite version of Dolt?"

Yes, in principle. You'd drop the MySQL wire protocol (not needed — SQLite is in-process) and build versioning on top of SQLite's existing query engine. The key enabler is the **SQLite session extension**, which already records cell-level changesets.

### Architecture

```
┌─────────────────────────────┐
│  SQLite query engine         │  ← Already embedded, no server
├─────────────────────────────┤
│  Version control layer       │  ← commit, branch, merge, diff, log
│  (SQLite session extension)  │  ← Records changesets (built into SQLite!)
├─────────────────────────────┤
│  Storage                     │
│  base.db + changeset chain   │  ← Current state + chain of diffs
└─────────────────────────────┘
```

### How it would work

```
sqlite-vcs/
├── base.db              ← Current state (regular SQLite file)
└── .history/
    ├── commits.db       ← Commit graph + changeset blobs
    └── branches.json    ← Branch pointers
```

1. **Open** `base.db`, enable session recording
2. **Work** — normal SQL queries
3. **Commit** → extract changeset from session, store as blob in `commits.db`
4. **Branch** → new entry in branches pointing to current commit
5. **Checkout** → apply/invert changesets to transform `base.db` to target state
6. **Merge** → apply changesets from source branch; session extension detects cell-level conflicts
7. **Diff** → compare two changesets

### Prior art

- **Fossil** — by SQLite's creator (D. Richard Hipp). A VCS that uses SQLite as storage, but versions *files* not *rows*.
- **cr-sqlite** — CRDT-based merge for SQLite. Multi-writer merge without conflicts, but no commit/branch/log model.
- **SQLite session extension** — built-in changeset recording. The foundation you'd build on.

### Difficulty assessment

| Aspect | Difficulty | Why |
|---|---|---|
| Basic commit/log | Easy | Changeset blobs + metadata table |
| Branching | Medium | Checkout requires applying/inverting changeset chains |
| Cell-level merge | Medium | Session extension handles conflict detection |
| Structural sharing | Hard | Without prolly trees, storage grows linearly with commits |
| Performance at scale | Hard | Changeset chains get slow for deep history |

### Honest estimate

- **Working prototype** (commit/branch/merge on small DBs): a few weeks in Python using the SQLite session extension
- **Production-quality** system competitive with Dolt: person-years, because the storage layer (structural sharing via content-addressed prolly trees) is where the real engineering lives

The SQLite session extension is the unlock — it gives you changesets for free. The question is whether changeset chains scale for your use case, or whether you'd eventually need content-addressed storage (at which point you're basically rebuilding Dolt's storage engine on top of SQLite's pager).

## The CGO connection

Dolt's storage engine uses a Go wrapper around ICU (International Components for Unicode) for collation/sorting, which requires CGO (C bindings from Go).

This is why the pre-built Beads binary failed on `bd init` — it was compiled without CGO, so the Dolt embedded database couldn't start. The fix was building from source with:

```bash
ICU_PREFIX="$(brew --prefix icu4c)"
CGO_ENABLED=1 \
  CGO_CFLAGS="-I${ICU_PREFIX}/include" \
  CGO_CPPFLAGS="-I${ICU_PREFIX}/include" \
  CGO_LDFLAGS="-L${ICU_PREFIX}/lib -licuuc -licui18n -licudata" \
  go install github.com/steveyegge/beads/cmd/bd@latest
```

The `--no-db` flag on `bd init` would fall back to JSONL-only mode (no Dolt), but with the CGO build you get the full database.
