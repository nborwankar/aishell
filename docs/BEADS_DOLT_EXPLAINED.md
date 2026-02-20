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
