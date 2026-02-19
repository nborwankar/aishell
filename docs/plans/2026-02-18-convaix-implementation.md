# convaix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract aishell's conversation infrastructure into a standalone `convaix` package with SQLite+sqlite-vec storage, verb-first CLI, immutable snapshots with `convaix_id`, and git-based P2P exchange.

**Architecture:** convaix is the standalone product — owns schema, storage, search, provider adapters, and git exchange. aishell becomes a thin client. PostgreSQL replaced by SQLite3 + sqlite-vec for zero-install friction.

**Tech Stack:** Python 3.11, Click (CLI), Rich (output), sqlite-vec (vectors), mlx-embedding-models (embeddings), Playwright (providers, optional)

**Source reference:** All code extracted/adapted from `/Users/nitin/Projects/github/etcprojects/aishell/aishell/commands/conversations/`

---

## Phase 0: Project Scaffolding

### Task 0.1: Create convaix project directory

**Files:**
- Create: `/Users/nitin/Projects/github/etcprojects/convaix/`
- Create: `/Users/nitin/Projects/github/etcprojects/convaix/pyproject.toml`
- Create: `/Users/nitin/Projects/github/etcprojects/convaix/.gitignore`
- Create: `/Users/nitin/Projects/github/etcprojects/convaix/CLAUDE.md`
- Create: `/Users/nitin/Projects/github/etcprojects/convaix/DONE.md`
- Create: `/Users/nitin/Projects/github/etcprojects/convaix/README.md`

**Step 1: Create directory structure**

```bash
mkdir -p /Users/nitin/Projects/github/etcprojects/convaix/{src/convaix,src/convaix/providers,src/convaix/exchange,tests,docs/plans}
```

**Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "convaix"
version = "0.1.0"
description = "AI conversation exchange — store, search, share"
requires-python = ">=3.10"

dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "sqlite-vec>=0.1.1",
]

[project.optional-dependencies]
embeddings = [
    "mlx-embedding-models>=0.1.0",
]
providers = [
    "playwright>=1.40",
    "beautifulsoup4>=4.12",
    "lxml>=4.9",
    "requests>=2.31",
]
all = ["convaix[embeddings,providers]"]

[project.scripts]
convaix = "convaix.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 3: Create .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.eggs/
*.db
.env
```

**Step 4: Create CLAUDE.md** (project-specific instructions — content TBD, minimal starter)

**Step 5: Create README.md** (minimal — name, one-line description, install command)

**Step 6: Create DONE.md** (empty starter with header)

**Step 7: Create `src/convaix/__init__.py`**

```python
"""convaix — AI conversation exchange."""

__version__ = "0.1.0"
```

**Step 8: Create empty `__init__.py` files**

- `src/convaix/providers/__init__.py`
- `src/convaix/exchange/__init__.py`

**Step 9: Git init and commit**

```bash
cd /Users/nitin/Projects/github/etcprojects/convaix
git init
git add .
git commit -m "chore: Initial project scaffolding"
```

---

## Phase 1: Schema + Validation

### Task 1.1: Port schema.py with x-convaix extension support

**Files:**
- Create: `src/convaix/schema.py`
- Test: `tests/test_schema.py`
- Source: `aishell/commands/conversations/schema.py`

**Step 1: Write the failing test**

```python
# tests/test_schema.py
import uuid
from convaix.schema import (
    slugify,
    generate_conv_id,
    generate_convaix_id,
    convert_to_schema,
    add_convaix_extension,
    ROLE_MAP,
)


def test_slugify_basic():
    assert slugify("Hello World!") == "hello-world"


def test_slugify_truncates():
    assert len(slugify("a" * 100, max_len=60)) == 60


def test_generate_conv_id_stable():
    id1 = generate_conv_id("chatgpt", "abc123")
    id2 = generate_conv_id("chatgpt", "abc123")
    assert id1 == id2
    assert id1.startswith("conv_")


def test_generate_conv_id_different_sources():
    id1 = generate_conv_id("chatgpt", "abc123")
    id2 = generate_conv_id("claude", "abc123")
    assert id1 != id2


def test_generate_convaix_id():
    cid = generate_convaix_id()
    assert cid.startswith("cx_")
    # Should be valid UUID after prefix
    uuid.UUID(cid[3:])


def test_role_map():
    assert ROLE_MAP["model"] == "assistant"
    assert ROLE_MAP["human"] == "user"


def test_convert_to_schema():
    turns = [
        {"role": "human", "content": "Hello"},
        {"role": "model", "content": "Hi there"},
    ]
    result = convert_to_schema(
        source="gemini",
        source_id="test123",
        title="Test Conversation",
        turns=turns,
    )
    assert result["schema_version"] == "1.0"
    assert result["conversation"]["source"] == "gemini"
    assert result["turns"][0]["role"] == "user"
    assert result["turns"][1]["role"] == "assistant"
    assert result["statistics"]["turn_count"] == 2
    assert "x-convaix" not in result


def test_add_convaix_extension():
    conv = convert_to_schema(
        source="claude",
        source_id="test456",
        title="Test",
        turns=[{"role": "user", "content": "Hi"}],
    )
    extended = add_convaix_extension(conv, author_handle="nborwankar")
    assert "x-convaix" in extended
    ext = extended["x-convaix"]
    assert ext["convaix_id"].startswith("cx_")
    assert ext["author"]["handle"] == "nborwankar"
    assert ext["conv_id"] == conv["conversation"]["id"]
    assert ext["parent_refs"] == []
    assert ext["signature"] is None
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/nitin/Projects/github/etcprojects/convaix
python -m pytest tests/test_schema.py -v
```

Expected: FAIL (module not found)

**Step 3: Write implementation**

Port `schema.py` from aishell with additions:
- `generate_convaix_id()` — returns `cx_{uuid4}`
- `add_convaix_extension(conv_data, author_handle, parent_refs=None)` — adds `x-convaix` block
- All existing functions unchanged: `slugify`, `generate_conv_id`, `convert_to_schema`, `ROLE_MAP`

```python
# src/convaix/schema.py
"""Conversation schema utilities.

Provides slugification, ID generation, role normalization, schema
conversion, and x-convaix extension support.
"""

import hashlib
import re
import uuid
from datetime import datetime, timezone

ROLE_MAP = {
    "model": "assistant",
    "user": "user",
    "assistant": "assistant",
    "system": "system",
    "human": "user",
}


def slugify(text, max_len=60):
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len]


def generate_conv_id(source, source_id):
    """Generate a stable, platform-agnostic conversation ID."""
    raw = f"{source}:{source_id}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"conv_{digest}"


def generate_convaix_id():
    """Generate a globally unique convaix snapshot ID."""
    return f"cx_{uuid.uuid4()}"


def convert_to_schema(
    source,
    source_id,
    title,
    turns,
    source_url=None,
    model=None,
    created_at=None,
    extra_metadata=None,
):
    """Convert provider-specific data to schema-compliant format."""
    schema_turns = []
    for i, turn in enumerate(turns):
        raw_role = turn.get("role", "unknown")
        role = ROLE_MAP.get(raw_role, raw_role)
        schema_turns.append(
            {
                "turn_number": i + 1,
                "role": role,
                "content": turn.get("content", ""),
                "timestamp": turn.get("timestamp"),
                "attachments": turn.get("attachments", []),
                "metadata": turn.get("metadata", {}),
            }
        )

    user_turns = sum(1 for t in schema_turns if t["role"] == "user")
    assistant_turns = sum(1 for t in schema_turns if t["role"] == "assistant")
    total_chars = sum(len(t["content"]) for t in schema_turns)

    effective_source_id = source_id or hashlib.sha256(title.encode()).hexdigest()[:16]
    conv_id = generate_conv_id(source, effective_source_id)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    metadata = extra_metadata or {}

    return {
        "schema_version": "1.0",
        "conversation": {
            "id": conv_id,
            "title": title,
            "source": source,
            "source_id": source_id,
            "source_url": source_url,
            "model": model,
            "created_at": created_at,
            "exported_at": now_iso,
            "tags": [],
            "metadata": metadata,
        },
        "turns": schema_turns,
        "statistics": {
            "turn_count": len(schema_turns),
            "user_turns": user_turns,
            "assistant_turns": assistant_turns,
            "total_chars": total_chars,
        },
    }


def add_convaix_extension(conv_data, author_handle, parent_refs=None):
    """Add x-convaix extension block to a schema v1.0 conversation.

    Returns the modified conv_data (mutates in place and returns).
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conv_data["x-convaix"] = {
        "convaix_id": generate_convaix_id(),
        "version": "0.1",
        "conv_id": conv_data["conversation"]["id"],
        "author": {
            "handle": author_handle,
            "key_id": None,
        },
        "published_at": now_iso,
        "parent_refs": parent_refs or [],
        "annotations": [],
        "signature": None,
    }
    return conv_data
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_schema.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/convaix/schema.py tests/test_schema.py
git commit -m "feat: Port schema.py with x-convaix extension support"
```

### Task 1.2: Schema validation

**Files:**
- Create: `src/convaix/validate.py`
- Test: `tests/test_validate.py`

**Step 1: Write the failing test**

```python
# tests/test_validate.py
import pytest
from convaix.validate import validate_conversation, ValidationError


def _minimal_valid():
    return {
        "schema_version": "1.0",
        "conversation": {
            "id": "conv_abc123",
            "title": "Test",
            "source": "chatgpt",
            "source_id": "xyz",
            "exported_at": "2026-02-18T00:00:00Z",
        },
        "turns": [
            {"turn_number": 1, "role": "user", "content": "Hello"},
        ],
        "statistics": {
            "turn_count": 1,
            "user_turns": 1,
            "assistant_turns": 0,
            "total_chars": 5,
        },
    }


def test_valid_minimal():
    validate_conversation(_minimal_valid())  # should not raise


def test_missing_schema_version():
    data = _minimal_valid()
    del data["schema_version"]
    with pytest.raises(ValidationError, match="schema_version"):
        validate_conversation(data)


def test_missing_conversation_id():
    data = _minimal_valid()
    del data["conversation"]["id"]
    with pytest.raises(ValidationError, match="id"):
        validate_conversation(data)


def test_invalid_role():
    data = _minimal_valid()
    data["turns"][0]["role"] = "alien"
    with pytest.raises(ValidationError, match="role"):
        validate_conversation(data)


def test_valid_with_x_convaix():
    data = _minimal_valid()
    data["x-convaix"] = {
        "convaix_id": "cx_test",
        "version": "0.1",
        "conv_id": "conv_abc123",
        "author": {"handle": "test"},
        "published_at": "2026-02-18T00:00:00Z",
        "parent_refs": [],
        "annotations": [],
        "signature": None,
    }
    validate_conversation(data)  # should not raise


def test_unknown_top_level_keys_ignored():
    data = _minimal_valid()
    data["x-future-extension"] = {"foo": "bar"}
    validate_conversation(data)  # should not raise
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_validate.py -v
```

**Step 3: Write implementation**

```python
# src/convaix/validate.py
"""Schema validation for conversation JSON files."""

VALID_ROLES = {"user", "assistant", "system"}
REQUIRED_CONV_FIELDS = {"id", "title", "source", "exported_at"}
REQUIRED_TURN_FIELDS = {"turn_number", "role", "content"}
REQUIRED_TOP_LEVEL = {"schema_version", "conversation", "turns", "statistics"}


class ValidationError(Exception):
    """Raised when a conversation fails schema validation."""
    pass


def validate_conversation(data):
    """Validate a conversation dict against schema v1.0.

    Raises ValidationError with a descriptive message on failure.
    Unknown top-level keys (like x-convaix, x-future) are ignored.
    """
    # Top-level required fields
    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            raise ValidationError(f"Missing required top-level field: {field}")

    if data["schema_version"] != "1.0":
        raise ValidationError(
            f"Unsupported schema_version: {data['schema_version']}"
        )

    # Conversation block
    conv = data["conversation"]
    for field in REQUIRED_CONV_FIELDS:
        if field not in conv:
            raise ValidationError(
                f"Missing required conversation field: {field}"
            )

    # Turns
    turns = data["turns"]
    if not isinstance(turns, list):
        raise ValidationError("turns must be a list")

    for i, turn in enumerate(turns):
        for field in REQUIRED_TURN_FIELDS:
            if field not in turn:
                raise ValidationError(
                    f"Turn {i + 1}: missing required field: {field}"
                )
        if turn["role"] not in VALID_ROLES:
            raise ValidationError(
                f"Turn {i + 1}: invalid role '{turn['role']}' "
                f"(must be one of {VALID_ROLES})"
            )
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_validate.py -v
```

**Step 5: Commit**

```bash
git add src/convaix/validate.py tests/test_validate.py
git commit -m "feat: Add schema validation with x-convaix support"
```

---

## Phase 2: SQLite Storage Layer

### Task 2.1: Database setup and snapshot loading

**Files:**
- Create: `src/convaix/db.py`
- Test: `tests/test_db.py`

**Step 1: Write the failing test**

```python
# tests/test_db.py
import json
import os
import tempfile
import pytest
from convaix.db import init_db, load_snapshot, list_snapshots, get_snapshot


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


def _sample_conv(convaix_id="cx_test-1234", conv_id="conv_abc123"):
    return {
        "schema_version": "1.0",
        "conversation": {
            "id": conv_id,
            "title": "Test Conversation",
            "source": "chatgpt",
            "source_id": "xyz789",
            "source_url": None,
            "model": "gpt-4",
            "created_at": "2026-02-18T10:00:00Z",
            "exported_at": "2026-02-18T12:00:00Z",
            "tags": ["test"],
            "metadata": {},
        },
        "turns": [
            {"turn_number": 1, "role": "user", "content": "Hello world"},
            {"turn_number": 2, "role": "assistant", "content": "Hi there! How can I help?"},
        ],
        "statistics": {
            "turn_count": 2,
            "user_turns": 1,
            "assistant_turns": 1,
            "total_chars": 37,
        },
        "x-convaix": {
            "convaix_id": convaix_id,
            "version": "0.1",
            "conv_id": conv_id,
            "author": {"handle": "testuser", "key_id": None},
            "published_at": "2026-02-18T14:00:00Z",
            "parent_refs": [],
            "annotations": [],
            "signature": None,
        },
    }


def test_init_db_creates_tables(db_path):
    conn = init_db(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "snapshots" in tables
    assert "chunks" in tables
    conn.close()


def test_load_snapshot(db_path):
    conn = init_db(db_path)
    data = _sample_conv()
    result = load_snapshot(conn, data)
    assert result is True
    conn.close()


def test_load_snapshot_duplicate_rejected(db_path):
    conn = init_db(db_path)
    data = _sample_conv()
    load_snapshot(conn, data)
    result = load_snapshot(conn, data)
    assert result is False
    conn.close()


def test_list_snapshots(db_path):
    conn = init_db(db_path)
    load_snapshot(conn, _sample_conv("cx_001", "conv_aaa"))
    load_snapshot(conn, _sample_conv("cx_002", "conv_aaa"))
    load_snapshot(conn, _sample_conv("cx_003", "conv_bbb"))
    rows = list_snapshots(conn)
    assert len(rows) == 3
    conn.close()


def test_list_snapshots_filter_source(db_path):
    conn = init_db(db_path)
    load_snapshot(conn, _sample_conv("cx_001"))
    rows = list_snapshots(conn, source="chatgpt")
    assert len(rows) == 1
    rows = list_snapshots(conn, source="claude")
    assert len(rows) == 0
    conn.close()


def test_get_snapshot(db_path):
    conn = init_db(db_path)
    data = _sample_conv("cx_get_test")
    load_snapshot(conn, data)
    row = get_snapshot(conn, "cx_get_test")
    assert row is not None
    assert row["title"] == "Test Conversation"
    assert row["convaix_id"] == "cx_get_test"
    conn.close()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_db.py -v
```

**Step 3: Write implementation**

```python
# src/convaix/db.py
"""SQLite3 + sqlite-vec database for conversation storage.

Handles schema creation, snapshot loading, and query helpers.
"""

import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.expanduser("~/.convaix/convaix.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    convaix_id  TEXT PRIMARY KEY,
    conv_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL,
    source_id   TEXT,
    model       TEXT,
    created_at  TEXT,
    published_at TEXT,
    author      TEXT,
    tags        TEXT DEFAULT '[]',
    raw         TEXT NOT NULL,
    turn_count  INTEGER NOT NULL DEFAULT 0,
    total_chars INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_snapshots_conv_id ON snapshots(conv_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_author ON snapshots(author);
CREATE INDEX IF NOT EXISTS idx_snapshots_source ON snapshots(source);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    convaix_id   TEXT NOT NULL REFERENCES snapshots(convaix_id),
    turn_number  INTEGER NOT NULL,
    chunk_number INTEGER NOT NULL,
    role         TEXT NOT NULL,
    chunk_text   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(convaix_id, turn_number, chunk_number)
);

CREATE TABLE IF NOT EXISTS discussions (
    discussion_id TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    created_by    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discussion_refs (
    discussion_id TEXT NOT NULL REFERENCES discussions(discussion_id),
    convaix_id    TEXT NOT NULL REFERENCES snapshots(convaix_id),
    PRIMARY KEY (discussion_id, convaix_id)
);

CREATE TABLE IF NOT EXISTS discussion_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id TEXT NOT NULL REFERENCES discussions(discussion_id),
    author        TEXT NOT NULL,
    content       TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


def init_db(db_path=None):
    """Create database and tables. Returns connection.

    Also initializes sqlite-vec virtual table if available.
    """
    db_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)

    # Try to load sqlite-vec for vector search
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
                embedding float[768]
            )
        """)
        logger.debug("sqlite-vec loaded, chunks_vec table ready")
    except (ImportError, Exception) as e:
        logger.debug(f"sqlite-vec not available: {e} (keyword search only)")

    conn.commit()
    return conn


def load_snapshot(conn, conv_data):
    """Load a conversation snapshot into the database.

    Expects conv_data with x-convaix block containing convaix_id.
    Returns True if loaded, False if duplicate convaix_id.
    """
    ext = conv_data.get("x-convaix", {})
    convaix_id = ext.get("convaix_id")
    if not convaix_id:
        logger.warning("No convaix_id in x-convaix block, skipping")
        return False

    conv = conv_data["conversation"]
    stats = conv_data.get("statistics", {})
    author = ext.get("author", {}).get("handle", "")

    try:
        conn.execute(
            """INSERT INTO snapshots
               (convaix_id, conv_id, title, source, source_id, model,
                created_at, published_at, author, tags, raw,
                turn_count, total_chars)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                convaix_id,
                conv.get("id", ""),
                conv.get("title", "Untitled"),
                conv.get("source", "unknown"),
                conv.get("source_id"),
                conv.get("model"),
                conv.get("created_at"),
                ext.get("published_at"),
                author,
                json.dumps(conv.get("tags", [])),
                json.dumps(conv_data),
                stats.get("turn_count", 0),
                stats.get("total_chars", 0),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def list_snapshots(conn, source=None, author=None, limit=1000):
    """List snapshots. Returns list of Row objects."""
    query = "SELECT convaix_id, conv_id, title, source, author, published_at, turn_count FROM snapshots"
    params = []
    conditions = []

    if source:
        conditions.append("source = ?")
        params.append(source)
    if author:
        conditions.append("author = ?")
        params.append(author)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY title LIMIT ?"
    params.append(limit)

    return conn.execute(query, params).fetchall()


def get_snapshot(conn, convaix_id):
    """Get a single snapshot by convaix_id. Returns Row or None."""
    return conn.execute(
        "SELECT * FROM snapshots WHERE convaix_id = ?", (convaix_id,)
    ).fetchone()


def get_snapshot_history(conn, conv_id):
    """Get all snapshots for a conv_id lineage, ordered by published_at."""
    return conn.execute(
        """SELECT convaix_id, conv_id, title, source, author, published_at, turn_count
           FROM snapshots WHERE conv_id = ? ORDER BY published_at""",
        (conv_id,),
    ).fetchall()
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_db.py -v
```

**Step 5: Commit**

```bash
git add src/convaix/db.py tests/test_db.py
git commit -m "feat: SQLite storage layer with snapshots and chunks tables"
```

---

## Phase 3: Chunking + Embeddings

### Task 3.1: Port paragraph chunking

**Files:**
- Create: `src/convaix/chunking.py`
- Test: `tests/test_chunking.py`
- Source: `aishell/commands/conversations/db.py:342-362` (`split_turn_into_chunks`)

**Step 1: Write the failing test**

```python
# tests/test_chunking.py
from convaix.chunking import split_into_chunks


def test_single_paragraph():
    assert split_into_chunks("Hello world") == ["Hello world"]


def test_double_newline_split():
    text = "First paragraph.\n\nSecond paragraph."
    result = split_into_chunks(text)
    assert len(result) == 2
    assert result[0] == "First paragraph."
    assert result[1] == "Second paragraph."


def test_short_paragraphs_merged():
    text = "First paragraph with enough content.\n\nOK\n\nThird paragraph with enough content."
    result = split_into_chunks(text, min_chars=50)
    # "OK" (2 chars) should merge into previous
    assert len(result) == 2


def test_empty_input():
    assert split_into_chunks("") == []
    assert split_into_chunks("   ") == []
    assert split_into_chunks(None) == []


def test_whitespace_only_paragraphs():
    text = "Real content.\n\n   \n\nMore content."
    result = split_into_chunks(text)
    assert len(result) == 2
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_chunking.py -v
```

**Step 3: Write implementation**

```python
# src/convaix/chunking.py
"""Paragraph-level chunking for conversation turns."""


def split_into_chunks(content, min_chars=50):
    """Split content on double newlines, merge short paragraphs.

    Returns list of paragraph strings. Empty/None input returns [].
    """
    if not content or not content.strip():
        return []

    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    merged = [paragraphs[0]]
    for p in paragraphs[1:]:
        if len(p) < min_chars and merged:
            merged[-1] = merged[-1] + "\n\n" + p
        else:
            merged.append(p)

    return merged
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_chunking.py -v
```

**Step 5: Commit**

```bash
git add src/convaix/chunking.py tests/test_chunking.py
git commit -m "feat: Paragraph-level chunking for conversation turns"
```

### Task 3.2: Port embeddings (MLX + nomic)

**Files:**
- Create: `src/convaix/embeddings.py`
- Test: `tests/test_embeddings.py`
- Source: `aishell/commands/conversations/embeddings.py`

**Step 1: Write the failing test**

```python
# tests/test_embeddings.py
import pytest
from convaix.embeddings import embed_texts, EMBEDDING_DIM


@pytest.mark.slow
def test_embed_single_text():
    result = embed_texts(["Hello world"])
    assert len(result) == 1
    assert len(result[0]) == EMBEDDING_DIM


@pytest.mark.slow
def test_embed_multiple():
    result = embed_texts(["Hello", "World", "Test"])
    assert len(result) == 3
    for emb in result:
        assert len(emb) == EMBEDDING_DIM


@pytest.mark.slow
def test_embed_query():
    from convaix.embeddings import embed_query
    result = embed_query("test query")
    assert len(result) == EMBEDDING_DIM
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_embeddings.py -v -m slow
```

**Step 3: Write implementation**

```python
# src/convaix/embeddings.py
"""Embedding utilities for conversation search.

Uses mlx-embedding-models for native Apple Silicon GPU acceleration.
Lazy-loads nomic-embed-text-v1.5 on first use.
"""

import logging
import os

os.environ.setdefault("USE_TF", "0")

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "nomic-text-v1.5"
EMBEDDING_DIM = 768

_model = None


def _patch_seq_lens():
    """Extend mlx-embedding-models SEQ_LENS for nomic's full 2048-token context."""
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
    """Generate embeddings with search_document: prefix for storage."""
    model = get_model()
    prefixed = [f"search_document: {t}" for t in texts]
    embeddings = model.encode(prefixed, batch_size=batch_size, show_progress=False)
    return embeddings.tolist()


def embed_query(text):
    """Generate a single embedding with search_query: prefix for retrieval."""
    model = get_model()
    embeddings = model.encode(
        [f"search_query: {text}"], show_progress=False
    )
    return embeddings.tolist()[0]
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_embeddings.py -v -m slow
```

**Step 5: Commit**

```bash
git add src/convaix/embeddings.py tests/test_embeddings.py
git commit -m "feat: MLX embedding layer with nomic-embed-text-v1.5"
```

### Task 3.3: Wire chunking + embedding into snapshot loading

**Files:**
- Modify: `src/convaix/db.py` — add `chunk_and_embed_snapshot()`
- Test: `tests/test_db.py` — add chunking tests

**Step 1: Write the failing test** (append to `tests/test_db.py`)

```python
def test_chunk_snapshot_stores_chunks(db_path):
    from convaix.db import init_db, load_snapshot, chunk_snapshot, get_chunks
    conn = init_db(db_path)
    data = _sample_conv("cx_chunk_test")
    load_snapshot(conn, data)
    count = chunk_snapshot(conn, data, skip_embeddings=True)
    assert count > 0
    chunks = get_chunks(conn, "cx_chunk_test")
    assert len(chunks) > 0
    assert chunks[0]["role"] in ("user", "assistant")
    conn.close()
```

**Step 2: Run test to verify it fails**

**Step 3: Add `chunk_snapshot()` and `get_chunks()` to `db.py`**

```python
# Add to src/convaix/db.py

def chunk_snapshot(conn, conv_data, skip_embeddings=False):
    """Split snapshot turns into paragraph chunks and optionally embed them.

    Returns number of chunks stored.
    """
    import hashlib
    from .chunking import split_into_chunks

    ext = conv_data.get("x-convaix", {})
    convaix_id = ext.get("convaix_id")
    title = conv_data["conversation"].get("title", "")
    turns = conv_data.get("turns", [])

    chunk_data = []
    for turn in turns:
        content = turn.get("content", "")
        role = turn.get("role", "user")
        turn_number = turn.get("turn_number", 0)
        paragraphs = split_into_chunks(content)
        for j, paragraph in enumerate(paragraphs):
            chunk_number = j + 1
            content_hash = hashlib.sha256(paragraph.encode()).hexdigest()
            chunk_data.append(
                (convaix_id, turn_number, chunk_number, role, paragraph, content_hash)
            )

    if not chunk_data:
        return 0

    stored = 0
    for row in chunk_data:
        try:
            conn.execute(
                """INSERT INTO chunks
                   (convaix_id, turn_number, chunk_number, role, chunk_text, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                row,
            )
            stored += 1
        except sqlite3.IntegrityError:
            pass  # already exists

    # Embed if requested and sqlite-vec is available
    if not skip_embeddings and stored > 0:
        _embed_chunks(conn, convaix_id, title, chunk_data)

    conn.commit()
    return stored


def _embed_chunks(conn, convaix_id, title, chunk_data):
    """Generate and store embeddings for chunks."""
    try:
        from .embeddings import embed_texts
    except ImportError:
        logger.debug("Embeddings not available (install convaix[embeddings])")
        return

    # Check if chunks_vec table exists
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
    )
    if not cur.fetchone():
        logger.debug("chunks_vec table not found, skipping embeddings")
        return

    # Build prefixed texts
    texts = []
    chunk_ids = []
    for convaix_id_val, turn_number, chunk_number, role, paragraph, _ in chunk_data:
        prefixed = f"[{title}] {role}: {paragraph}"
        texts.append(prefixed)
        # Get the chunk row id
        row = conn.execute(
            "SELECT id FROM chunks WHERE convaix_id=? AND turn_number=? AND chunk_number=?",
            (convaix_id_val, turn_number, chunk_number),
        ).fetchone()
        if row:
            chunk_ids.append(row["id"])

    if not texts:
        return

    embeddings = embed_texts(texts)
    for chunk_id, emb in zip(chunk_ids, embeddings):
        conn.execute(
            "INSERT OR REPLACE INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
            (chunk_id, json.dumps(emb)),
        )


def get_chunks(conn, convaix_id):
    """Get all chunks for a snapshot, ordered by turn and chunk number."""
    return conn.execute(
        """SELECT * FROM chunks
           WHERE convaix_id = ?
           ORDER BY turn_number, chunk_number""",
        (convaix_id,),
    ).fetchall()
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_db.py -v
```

**Step 5: Commit**

```bash
git add src/convaix/db.py tests/test_db.py
git commit -m "feat: Wire chunking + embedding into snapshot loading"
```

---

## Phase 4: Search

### Task 4.1: Hybrid search (semantic + keyword)

**Files:**
- Create: `src/convaix/search.py`
- Test: `tests/test_search.py`

**Step 1: Write the failing test**

```python
# tests/test_search.py
import pytest
from convaix.db import init_db, load_snapshot, chunk_snapshot
from convaix.search import search_chunks, search_conversations


@pytest.fixture
def loaded_db(tmp_path):
    db_path = str(tmp_path / "search_test.db")
    conn = init_db(db_path)
    data = {
        "schema_version": "1.0",
        "conversation": {
            "id": "conv_search",
            "title": "Manifold Geometry Discussion",
            "source": "claude",
            "source_id": "search_test",
            "exported_at": "2026-02-18T00:00:00Z",
        },
        "turns": [
            {"turn_number": 1, "role": "user", "content": "Tell me about Riemannian manifolds"},
            {"turn_number": 2, "role": "assistant", "content": "Riemannian manifolds are smooth manifolds equipped with a Riemannian metric."},
        ],
        "statistics": {"turn_count": 2, "user_turns": 1, "assistant_turns": 1, "total_chars": 100},
        "x-convaix": {
            "convaix_id": "cx_search_test",
            "version": "0.1",
            "conv_id": "conv_search",
            "author": {"handle": "testuser"},
            "published_at": "2026-02-18T00:00:00Z",
            "parent_refs": [], "annotations": [], "signature": None,
        },
    }
    load_snapshot(conn, data)
    chunk_snapshot(conn, data, skip_embeddings=True)
    return conn


def test_keyword_search(loaded_db):
    results = search_chunks(loaded_db, "Riemannian", mode="keyword")
    assert len(results) > 0
    assert any("Riemannian" in r["chunk_text"] for r in results)


def test_keyword_search_title_match(loaded_db):
    results = search_chunks(loaded_db, "Manifold Geometry", mode="keyword")
    assert len(results) > 0


def test_keyword_search_no_results(loaded_db):
    results = search_chunks(loaded_db, "zzznonexistent", mode="keyword")
    assert len(results) == 0


def test_conversation_search(loaded_db):
    results = search_conversations(loaded_db, "Riemannian")
    assert len(results) > 0
    assert results[0]["title"] == "Manifold Geometry Discussion"
```

**Step 2: Run test to verify it fails**

**Step 3: Write implementation**

```python
# src/convaix/search.py
"""Hybrid search across conversation snapshots.

Combines semantic similarity (sqlite-vec cosine) with keyword matching
(LIKE on chunk_text and title).
"""

import json
import logging

logger = logging.getLogger(__name__)


def search_chunks(conn, query, source=None, limit=10, mode="hybrid"):
    """Search chunks by keyword, semantic, or hybrid mode.

    Returns list of dicts with: chunk_text, role, title, source,
    convaix_id, similarity, match_type.
    """
    results = {}

    # Keyword search
    if mode in ("keyword", "hybrid"):
        kw_results = _keyword_search(conn, query, source, limit)
        for r in kw_results:
            key = (r["convaix_id"], r["chunk_text"][:100])
            results[key] = {**r, "match_type": "kw"}

    # Semantic search
    if mode in ("semantic", "hybrid"):
        sem_results = _semantic_search(conn, query, source, limit)
        for r in sem_results:
            key = (r["convaix_id"], r["chunk_text"][:100])
            if key in results:
                results[key]["match_type"] = "both"
                results[key]["similarity"] = max(
                    results[key]["similarity"], r["similarity"]
                )
            else:
                results[key] = {**r, "match_type": "sem"}

    # Sort by similarity descending
    sorted_results = sorted(
        results.values(), key=lambda r: r["similarity"], reverse=True
    )
    return sorted_results[:limit]


def search_conversations(conn, query, source=None, limit=20):
    """Conversation-level keyword search with hit counts.

    Returns list of dicts with: title, source, convaix_id, hits, turn_count.
    """
    kw_pattern = f"%{query}%"
    params = [kw_pattern, kw_pattern]
    source_filter = ""

    if source:
        source_filter = "AND s.source = ?"
        params.append(source)

    params.append(limit)

    rows = conn.execute(
        f"""SELECT s.title, s.source, s.convaix_id,
                   COUNT(*) AS hits, s.turn_count
            FROM chunks c
            JOIN snapshots s ON c.convaix_id = s.convaix_id
            WHERE (c.chunk_text LIKE ? OR s.title LIKE ?)
            {source_filter}
            GROUP BY s.convaix_id
            ORDER BY hits DESC
            LIMIT ?""",
        params,
    ).fetchall()

    return [dict(r) for r in rows]


def _keyword_search(conn, query, source, limit):
    """LIKE-based keyword search on chunk_text and title."""
    kw_pattern = f"%{query}%"
    params = [kw_pattern, kw_pattern]
    source_filter = ""

    if source:
        source_filter = "AND s.source = ?"
        params.append(source)

    params.append(limit)

    rows = conn.execute(
        f"""SELECT c.role, c.chunk_text, s.title, s.source, s.convaix_id,
                   1.0 AS similarity
            FROM chunks c
            JOIN snapshots s ON c.convaix_id = s.convaix_id
            WHERE (c.chunk_text LIKE ? OR s.title LIKE ?)
            {source_filter}
            LIMIT ?""",
        params,
    ).fetchall()

    return [dict(r) for r in rows]


def _semantic_search(conn, query, source, limit):
    """sqlite-vec cosine similarity search."""
    try:
        from .embeddings import embed_query
    except ImportError:
        logger.debug("Embeddings not available, skipping semantic search")
        return []

    # Check if chunks_vec exists
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
    )
    if not cur.fetchone():
        return []

    # Check if there are any embeddings
    cur = conn.execute("SELECT COUNT(*) FROM chunks_vec")
    if cur.fetchone()[0] == 0:
        return []

    query_emb = embed_query(query)

    rows = conn.execute(
        """SELECT v.rowid, v.distance
           FROM chunks_vec v
           WHERE embedding MATCH ?
           ORDER BY distance
           LIMIT ?""",
        (json.dumps(query_emb), limit),
    ).fetchall()

    results = []
    for row in rows:
        chunk = conn.execute(
            """SELECT c.role, c.chunk_text, c.convaix_id, s.title, s.source
               FROM chunks c
               JOIN snapshots s ON c.convaix_id = s.convaix_id
               WHERE c.id = ?""",
            (row["rowid"],),
        ).fetchone()

        if chunk:
            results.append({
                "role": chunk["role"],
                "chunk_text": chunk["chunk_text"],
                "title": chunk["title"],
                "source": chunk["source"],
                "convaix_id": chunk["convaix_id"],
                "similarity": 1.0 - row["distance"],
            })

    return results
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_search.py -v
```

**Step 5: Commit**

```bash
git add src/convaix/search.py tests/test_search.py
git commit -m "feat: Hybrid search (semantic + keyword) for snapshots"
```

---

## Phase 5: CLI

### Task 5.1: Core CLI commands

**Files:**
- Create: `src/convaix/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py
import json
import os
from click.testing import CliRunner
from convaix.cli import main


def _write_sample_conv(path, convaix_id="cx_cli_test"):
    data = {
        "schema_version": "1.0",
        "conversation": {
            "id": "conv_cli", "title": "CLI Test Conv",
            "source": "chatgpt", "source_id": "cli_test",
            "exported_at": "2026-02-18T00:00:00Z",
        },
        "turns": [
            {"turn_number": 1, "role": "user", "content": "Hello from CLI test"},
            {"turn_number": 2, "role": "assistant", "content": "Hi! This is the CLI test."},
        ],
        "statistics": {"turn_count": 2, "user_turns": 1, "assistant_turns": 1, "total_chars": 42},
        "x-convaix": {
            "convaix_id": convaix_id, "version": "0.1", "conv_id": "conv_cli",
            "author": {"handle": "testuser"}, "published_at": "2026-02-18T00:00:00Z",
            "parent_refs": [], "annotations": [], "signature": None,
        },
    }
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def test_load_command(tmp_path):
    conv_dir = tmp_path / "convs"
    conv_dir.mkdir()
    _write_sample_conv(str(conv_dir / "test.json"))

    runner = CliRunner()
    db_path = str(tmp_path / "test.db")
    result = runner.invoke(main, ["load", str(conv_dir), "--db", db_path, "--skip-embeddings"])
    assert result.exit_code == 0
    assert "Loaded" in result.output or "1" in result.output


def test_list_command(tmp_path):
    conv_dir = tmp_path / "convs"
    conv_dir.mkdir()
    _write_sample_conv(str(conv_dir / "test.json"))

    runner = CliRunner()
    db_path = str(tmp_path / "test.db")
    runner.invoke(main, ["load", str(conv_dir), "--db", db_path, "--skip-embeddings"])
    result = runner.invoke(main, ["list", "--db", db_path])
    assert result.exit_code == 0
    assert "CLI Test Conv" in result.output


def test_search_keyword(tmp_path):
    conv_dir = tmp_path / "convs"
    conv_dir.mkdir()
    _write_sample_conv(str(conv_dir / "test.json"))

    runner = CliRunner()
    db_path = str(tmp_path / "test.db")
    runner.invoke(main, ["load", str(conv_dir), "--db", db_path, "--skip-embeddings"])
    result = runner.invoke(main, ["search", "CLI test", "--db", db_path])
    assert result.exit_code == 0


def test_validate_command(tmp_path):
    path = str(tmp_path / "valid.json")
    _write_sample_conv(path)
    runner = CliRunner()
    result = runner.invoke(main, ["validate", path])
    assert result.exit_code == 0
    assert "Valid" in result.output or "valid" in result.output
```

**Step 2: Run test to verify it fails**

**Step 3: Write implementation**

```python
# src/convaix/cli.py
"""convaix CLI — AI conversation exchange."""

import json
import logging
import os

import click
from rich.console import Console
from rich.table import Table

console = Console()
logger = logging.getLogger(__name__)

DEFAULT_DB = os.path.expanduser("~/.convaix/convaix.db")


@click.group()
@click.version_option()
def main():
    """convaix — store, search, and share AI conversations."""
    pass


@main.command()
@click.argument("path")
@click.option("--db", default=DEFAULT_DB, help="Database path")
@click.option("--skip-embeddings", is_flag=True, help="Load without generating embeddings")
def load(path, db, skip_embeddings):
    """Load conversation JSON files into local database."""
    from .db import init_db, load_snapshot, chunk_snapshot
    from .schema import add_convaix_extension
    from .validate import validate_conversation, ValidationError

    conn = init_db(db)
    loaded = 0
    skipped = 0
    errors = 0

    files = []
    if os.path.isdir(path):
        for f in sorted(os.listdir(path)):
            if f.endswith(".json"):
                files.append(os.path.join(path, f))
    elif os.path.isfile(path):
        files.append(path)
    else:
        console.print(f"[red]Path not found: {path}[/red]")
        return

    for filepath in files:
        basename = os.path.basename(filepath)
        try:
            with open(filepath) as f:
                data = json.load(f)

            validate_conversation(data)

            # Add x-convaix extension if not present
            if "x-convaix" not in data:
                add_convaix_extension(data, author_handle="local")

            if load_snapshot(conn, data):
                chunk_snapshot(conn, data, skip_embeddings=skip_embeddings)
                console.print(f"  [green]Loaded[/green]: {basename}")
                loaded += 1
            else:
                skipped += 1
        except (ValidationError, json.JSONDecodeError) as e:
            console.print(f"  [red]Error[/red]: {basename}: {e}")
            errors += 1

    conn.close()

    table = Table(title="Load Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green")
    table.add_row("Loaded", str(loaded))
    table.add_row("Skipped", str(skipped))
    table.add_row("Errors", str(errors))
    console.print(table)


@main.command("list")
@click.option("--db", default=DEFAULT_DB, help="Database path")
@click.option("--source", "-s", help="Filter by source")
def list_cmd(db, source):
    """List loaded conversation snapshots."""
    from .db import init_db, list_snapshots

    conn = init_db(db)
    rows = list_snapshots(conn, source=source)
    conn.close()

    if not rows:
        console.print("[yellow]No snapshots found.[/yellow]")
        return

    table = Table(title="Snapshots")
    table.add_column("#", style="dim")
    table.add_column("Title", style="blue", ratio=2)
    table.add_column("Source", style="magenta")
    table.add_column("Author", style="cyan")
    table.add_column("Turns", style="green")
    table.add_column("convaix_id", style="dim")

    for i, row in enumerate(rows, 1):
        table.add_row(
            str(i), row["title"], row["source"],
            row["author"] or "", str(row["turn_count"]),
            row["convaix_id"][:16] + "...",
        )

    console.print(table)


@main.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--db", default=DEFAULT_DB, help="Database path")
@click.option("--limit", "-l", type=int, default=10, help="Max results")
@click.option("--source", "-s", help="Filter by source")
@click.option("--conversations", "-c", "conv_mode", is_flag=True, help="Conversation-level results")
def search(query, db, limit, source, conv_mode):
    """Hybrid search across loaded conversations."""
    from .db import init_db
    from .search import search_chunks, search_conversations

    query_str = " ".join(query)
    conn = init_db(db)

    if conv_mode:
        results = search_conversations(conn, query_str, source=source, limit=limit)
        conn.close()
        if not results:
            console.print("[yellow]No conversations found.[/yellow]")
            return

        table = Table(title=f'Conversations: "{query_str}"', show_lines=True)
        table.add_column("#", style="dim")
        table.add_column("Title", style="blue", ratio=2)
        table.add_column("Src", style="magenta")
        table.add_column("Hits", style="green")
        table.add_column("Turns", style="cyan")

        for i, r in enumerate(results, 1):
            table.add_row(str(i), r["title"], r["source"], str(r["hits"]), str(r["turn_count"]))
        console.print(table)
        return

    results = search_chunks(conn, query_str, source=source, limit=limit)
    conn.close()

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title=f'Search: "{query_str}"', show_lines=True)
    table.add_column("Sim", style="green", no_wrap=True)
    table.add_column("Match", style="yellow", no_wrap=True)
    table.add_column("Src", style="magenta")
    table.add_column("Role", style="cyan")
    table.add_column("Conversation", style="blue", max_width=30)
    table.add_column("Content", ratio=2)

    for r in results:
        preview = r["chunk_text"][:300]
        if len(r["chunk_text"]) > 300:
            preview += "..."
        table.add_row(
            f"{r['similarity']:.3f}", r["match_type"],
            r["source"], r["role"], r["title"][:30], preview,
        )
    console.print(table)


@main.command()
@click.argument("file_path")
def validate(file_path):
    """Validate a conversation JSON file against schema v1.0."""
    from .validate import validate_conversation, ValidationError

    try:
        with open(file_path) as f:
            data = json.load(f)
        validate_conversation(data)
        console.print(f"[green]Valid[/green]: {file_path}")
    except ValidationError as e:
        console.print(f"[red]Invalid[/red]: {e}")
        raise SystemExit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON error[/red]: {e}")
        raise SystemExit(1)


@main.command()
@click.argument("conv_id")
@click.option("--db", default=DEFAULT_DB, help="Database path")
def history(conv_id, db):
    """Show all snapshots of a conversation lineage."""
    from .db import init_db, get_snapshot_history

    conn = init_db(db)
    rows = get_snapshot_history(conn, conv_id)
    conn.close()

    if not rows:
        console.print(f"[yellow]No snapshots found for {conv_id}[/yellow]")
        return

    table = Table(title=f"History: {conv_id}")
    table.add_column("convaix_id", style="dim")
    table.add_column("Published", style="cyan")
    table.add_column("Turns", style="green")
    table.add_column("Author", style="blue")

    for row in rows:
        table.add_row(
            row["convaix_id"][:16] + "...",
            row["published_at"] or "",
            str(row["turn_count"]),
            row["author"] or "",
        )
    console.print(table)


@main.command()
@click.argument("convaix_id")
@click.option("--db", default=DEFAULT_DB, help="Database path")
@click.option("--output", "-o", help="Output file path (default: stdout)")
def export(convaix_id, db, output):
    """Export a snapshot back to JSON."""
    from .db import init_db, get_snapshot

    conn = init_db(db)
    row = get_snapshot(conn, convaix_id)
    conn.close()

    if not row:
        console.print(f"[red]Snapshot not found: {convaix_id}[/red]")
        raise SystemExit(1)

    raw = json.loads(row["raw"])
    formatted = json.dumps(raw, indent=2, ensure_ascii=False)

    if output:
        with open(output, "w") as f:
            f.write(formatted)
        console.print(f"[green]Exported to {output}[/green]")
    else:
        click.echo(formatted)
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_cli.py -v
```

**Step 5: Commit**

```bash
git add src/convaix/cli.py tests/test_cli.py
git commit -m "feat: Core CLI commands (load, list, search, validate, history, export)"
```

---

## Phase 6: Provider Adapters

### Task 6.1: Provider base class and registry

**Files:**
- Create: `src/convaix/providers/base.py`
- Modify: `src/convaix/providers/__init__.py`
- Test: `tests/test_providers.py`

**Step 1: Write the failing test**

```python
# tests/test_providers.py
from convaix.providers import get_provider, list_providers


def test_list_providers():
    providers = list_providers()
    assert "chatgpt" in providers
    assert "claude" in providers
    assert "gemini" in providers


def test_get_provider():
    p = get_provider("chatgpt")
    assert p is not None
    assert hasattr(p, "pull")
    assert hasattr(p, "login")
```

**Step 2: Run test to verify it fails**

**Step 3: Write implementation**

```python
# src/convaix/providers/base.py
"""Base class for conversation providers."""

from abc import ABC, abstractmethod


class Provider(ABC):
    """Base class for LLM conversation providers."""

    name: str = ""

    @abstractmethod
    def login(self, console):
        """Launch browser for manual sign-in."""
        pass

    @abstractmethod
    def pull(self, output_dir, console, **kwargs):
        """Download conversations from provider. Returns count."""
        pass

    @abstractmethod
    def parse_raw(self, raw_data):
        """Parse raw provider JSON into (meta_dict, turns_list)."""
        pass
```

```python
# src/convaix/providers/__init__.py
"""Provider registry for LLM conversation sources."""

_PROVIDERS = {}


def _register_providers():
    """Lazy-register built-in providers."""
    global _PROVIDERS
    if _PROVIDERS:
        return

    try:
        from .chatgpt import ChatGPTProvider
        _PROVIDERS["chatgpt"] = ChatGPTProvider()
    except ImportError:
        pass

    try:
        from .claude import ClaudeProvider
        _PROVIDERS["claude"] = ClaudeProvider()
    except ImportError:
        pass

    try:
        from .gemini import GeminiProvider
        _PROVIDERS["gemini"] = GeminiProvider()
    except ImportError:
        pass


def list_providers():
    _register_providers()
    return list(_PROVIDERS.keys())


def get_provider(name):
    _register_providers()
    return _PROVIDERS.get(name)
```

**Step 4: Run test — will partially pass (providers not yet ported)**

Note: Full provider porting (chatgpt.py, claude.py, gemini.py, browser.py) is Task 6.2–6.5. These are direct ports from aishell with minimal changes (swap aishell paths for convaix paths, use `~/.convaix/` data dirs).

**Step 5: Commit**

```bash
git add src/convaix/providers/
git commit -m "feat: Provider base class and registry"
```

### Task 6.2: Port browser.py (shared Chrome/CDP helpers)

**Files:**
- Create: `src/convaix/providers/browser.py`
- Source: `aishell/commands/conversations/browser.py`

Direct port — no functional changes. Update import paths only. The file is self-contained (no aishell dependencies).

**Commit:**

```bash
git commit -m "feat: Port Chrome/CDP browser helpers"
```

### Task 6.3: Port ChatGPT provider

**Files:**
- Create: `src/convaix/providers/chatgpt.py`
- Source: `aishell/commands/chatgpt.py`

Port the ChatGPT provider class wrapping the existing pull/import/parse logic. Change data dirs from `~/.aishell/chatgpt/` to `~/.convaix/chatgpt/`.

**Commit:**

```bash
git commit -m "feat: Port ChatGPT provider adapter"
```

### Task 6.4: Port Claude provider

**Files:**
- Create: `src/convaix/providers/claude.py`
- Source: `aishell/commands/claude_export.py`

Same approach as ChatGPT. Change data dirs to `~/.convaix/claude/`.

**Commit:**

```bash
git commit -m "feat: Port Claude provider adapter"
```

### Task 6.5: Port Gemini provider

**Files:**
- Create: `src/convaix/providers/gemini.py`
- Source: `aishell/commands/gemini.py`

Same approach. Change data dirs to `~/.convaix/gemini/`.

**Commit:**

```bash
git commit -m "feat: Port Gemini provider adapter"
```

### Task 6.6: Add provider CLI commands (verb-first)

**Files:**
- Modify: `src/convaix/cli.py` — add `login`, `pull`, `import` commands

**Add to cli.py:**

```python
@main.command()
@click.argument("provider_name")
def login(provider_name):
    """Launch browser sign-in for a provider."""
    from .providers import get_provider
    p = get_provider(provider_name)
    if not p:
        console.print(f"[red]Unknown provider: {provider_name}[/red]")
        raise SystemExit(1)
    p.login(console)


@main.command()
@click.argument("provider_name")
@click.option("--output-dir", "-o", help="Custom output directory")
@click.option("--resume", is_flag=True, help="Resume interrupted pull")
def pull(provider_name, output_dir, resume):
    """Pull conversations from a provider."""
    from .providers import get_provider
    p = get_provider(provider_name)
    if not p:
        console.print(f"[red]Unknown provider: {provider_name}[/red]")
        raise SystemExit(1)
    p.pull(output_dir=output_dir, console=console, resume=resume)


@main.command("import")
@click.argument("provider_name")
@click.argument("path")
def import_cmd(provider_name, path):
    """Import conversations from a local file/directory."""
    from .providers import get_provider
    p = get_provider(provider_name)
    if not p:
        console.print(f"[red]Unknown provider: {provider_name}[/red]")
        raise SystemExit(1)
    p.import_from(path, console)
```

**Commit:**

```bash
git commit -m "feat: Verb-first CLI commands (login, pull, import <provider>)"
```

---

## Phase 7: Git Exchange

### Task 7.1: Init and publish

**Files:**
- Create: `src/convaix/exchange/git.py`
- Create: `src/convaix/exchange/manifest.py`
- Test: `tests/test_exchange.py`

**Step 1: Write the failing test**

```python
# tests/test_exchange.py
import json
import os
import subprocess
import pytest
from convaix.exchange.git import init_repo, publish_snapshot
from convaix.exchange.manifest import load_manifest, save_manifest


@pytest.fixture
def repo_path(tmp_path):
    path = str(tmp_path / "test-repo")
    return path


def test_init_repo(repo_path):
    init_repo(repo_path, name="test-team", description="Test repo")
    assert os.path.isdir(repo_path)
    assert os.path.isdir(os.path.join(repo_path, "conversations"))
    assert os.path.isdir(os.path.join(repo_path, "discussions"))
    assert os.path.isfile(os.path.join(repo_path, ".convaix", "repo.toml"))
    assert os.path.isfile(os.path.join(repo_path, "manifest.json"))
    # Should be a git repo
    assert os.path.isdir(os.path.join(repo_path, ".git"))


def test_publish_snapshot(repo_path):
    init_repo(repo_path, name="test-team")
    snapshot_data = {
        "schema_version": "1.0",
        "conversation": {"id": "conv_pub", "title": "Publish Test", "source": "claude",
                         "source_id": "pub1", "exported_at": "2026-02-18T00:00:00Z"},
        "turns": [{"turn_number": 1, "role": "user", "content": "Hello"}],
        "statistics": {"turn_count": 1, "user_turns": 1, "assistant_turns": 0, "total_chars": 5},
        "x-convaix": {
            "convaix_id": "cx_pub_test_1234",
            "version": "0.1", "conv_id": "conv_pub",
            "author": {"handle": "tester"}, "published_at": "2026-02-18T00:00:00Z",
            "parent_refs": [], "annotations": [], "signature": None,
        },
    }
    filepath = publish_snapshot(repo_path, snapshot_data)
    assert os.path.isfile(filepath)
    assert "cx_pub_test" in filepath

    # Check manifest updated
    manifest = load_manifest(os.path.join(repo_path, "manifest.json"))
    assert len(manifest["snapshots"]) == 1
    assert manifest["snapshots"][0]["convaix_id"] == "cx_pub_test_1234"


def test_manifest_roundtrip(tmp_path):
    path = str(tmp_path / "manifest.json")
    data = {"repo": "test", "snapshots": [], "discussions": []}
    save_manifest(data, path)
    loaded = load_manifest(path)
    assert loaded["repo"] == "test"
```

**Step 2: Run test to verify it fails**

**Step 3: Write implementation**

```python
# src/convaix/exchange/manifest.py
"""Manifest management for shared convaix repos."""

import json
import os


def load_manifest(path):
    """Load manifest.json, returning empty structure if not found."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"repo": "", "description": "", "snapshots": [], "discussions": []}


def save_manifest(data, path):
    """Save manifest.json."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
```

```python
# src/convaix/exchange/git.py
"""Git-based conversation exchange."""

import json
import logging
import os
import subprocess

from ..schema import slugify
from .manifest import load_manifest, save_manifest

logger = logging.getLogger(__name__)


def init_repo(path, name="", description=""):
    """Initialize a shared convaix repo at the given path."""
    os.makedirs(os.path.join(path, "conversations"), exist_ok=True)
    os.makedirs(os.path.join(path, "discussions"), exist_ok=True)
    os.makedirs(os.path.join(path, ".convaix"), exist_ok=True)

    # repo.toml
    toml_path = os.path.join(path, ".convaix", "repo.toml")
    with open(toml_path, "w") as f:
        f.write(f'name = "{name}"\n')
        f.write(f'description = "{description}"\n')

    # manifest.json
    manifest_path = os.path.join(path, "manifest.json")
    if not os.path.exists(manifest_path):
        save_manifest(
            {"repo": name, "description": description, "snapshots": [], "discussions": []},
            manifest_path,
        )

    # git init
    if not os.path.isdir(os.path.join(path, ".git")):
        subprocess.run(["git", "init"], cwd=path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: Initialize convaix repo"],
            cwd=path, capture_output=True,
        )

    logger.info(f"Initialized convaix repo at {path}")


def publish_snapshot(repo_path, snapshot_data):
    """Publish a snapshot to a shared repo. Returns file path."""
    ext = snapshot_data.get("x-convaix", {})
    convaix_id = ext.get("convaix_id", "cx_unknown")
    title = snapshot_data["conversation"].get("title", "untitled")
    slug = slugify(title)
    prefix = convaix_id[:11]  # "cx_" + 8 chars

    filename = f"{prefix}-{slug}.json"
    filepath = os.path.join(repo_path, "conversations", filename)

    with open(filepath, "w") as f:
        json.dump(snapshot_data, f, indent=2, ensure_ascii=False)

    # Update manifest
    manifest_path = os.path.join(repo_path, "manifest.json")
    manifest = load_manifest(manifest_path)
    manifest["snapshots"].append({
        "convaix_id": convaix_id,
        "conv_id": ext.get("conv_id", ""),
        "title": title,
        "source": snapshot_data["conversation"].get("source", ""),
        "author": ext.get("author", {}).get("handle", ""),
        "published_at": ext.get("published_at", ""),
        "file": f"conversations/{filename}",
        "turn_count": snapshot_data.get("statistics", {}).get("turn_count", 0),
    })
    save_manifest(manifest, manifest_path)

    # Git commit
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"publish: {title} ({prefix})"],
        cwd=repo_path, capture_output=True,
    )

    return filepath


def sync_repo(repo_path, remote=None):
    """Push local commits and pull remote changes."""
    if remote:
        # Add remote if not exists
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path, capture_output=True, text=True,
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "remote", "add", "origin", remote],
                cwd=repo_path, capture_output=True,
            )

    subprocess.run(["git", "pull", "--rebase", "origin", "main"],
                    cwd=repo_path, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"],
                    cwd=repo_path, capture_output=True)
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_exchange.py -v
```

**Step 5: Commit**

```bash
git add src/convaix/exchange/ tests/test_exchange.py
git commit -m "feat: Git-based exchange (init, publish, sync, manifest)"
```

### Task 7.2: Exchange CLI commands

**Files:**
- Modify: `src/convaix/cli.py` — add `init`, `publish`, `sync` commands

Add exchange commands to cli.py following the same verb-first pattern.

**Commit:**

```bash
git commit -m "feat: Exchange CLI commands (init, publish, sync)"
```

---

## Phase 8: Integration Test + Polish

### Task 8.1: End-to-end test

**Files:**
- Create: `tests/test_e2e.py`

Write an end-to-end test that:
1. Creates a sample conversation JSON
2. Validates it
3. Loads it into a temp DB (skip embeddings)
4. Searches for it
5. Exports it back
6. Initializes a shared repo
7. Publishes the snapshot to the repo
8. Verifies the manifest

```bash
python -m pytest tests/test_e2e.py -v
```

**Commit:**

```bash
git commit -m "test: End-to-end integration test"
```

### Task 8.2: Install and smoke test

**Steps:**

```bash
cd /Users/nitin/Projects/github/etcprojects/convaix
pip install -e .

# Smoke test
convaix --help
convaix --version
convaix validate tests/fixtures/sample.json
convaix load tests/fixtures/ --skip-embeddings
convaix list
convaix search "test"
```

**Commit:**

```bash
git commit -m "chore: Smoke test passed, v0.1.0 ready"
```

### Task 8.3: Update CLAUDE.md and DONE.md

Update project state files with completed work.

**Commit:**

```bash
git commit -m "docs: Update CLAUDE.md and DONE.md with initial release"
```

---

## Summary of Phases

| Phase | Description | Tasks | Key Deliverable |
|-------|-------------|-------|-----------------|
| 0 | Scaffolding | 0.1 | Project structure, pyproject.toml, git init |
| 1 | Schema | 1.1–1.2 | schema.py + validate.py with x-convaix |
| 2 | Storage | 2.1 | SQLite + sqlite-vec, snapshots/chunks tables |
| 3 | Chunking + Embedding | 3.1–3.3 | Paragraph splitting, MLX embeddings, wiring |
| 4 | Search | 4.1 | Hybrid semantic + keyword search |
| 5 | CLI | 5.1 | Core commands (load, list, search, validate, etc.) |
| 6 | Providers | 6.1–6.6 | Base class, registry, 3 adapters, verb-first CLI |
| 7 | Exchange | 7.1–7.2 | Git init/publish/sync, manifest, exchange CLI |
| 8 | Integration | 8.1–8.3 | E2E test, smoke test, docs |
