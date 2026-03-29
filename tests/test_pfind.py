"""Tests for pfind — project finder inverted index."""

import json
import os
import tempfile
from pathlib import Path

from aishell.commands.pfind import ProjectIndex


def _make_project(base: Path, name: str, marker: str = ".git") -> Path:
    """Create a fake project directory with a marker."""
    proj = base / name
    proj.mkdir(parents=True, exist_ok=True)
    if marker == ".git":
        (proj / ".git").mkdir()
    else:
        (proj / marker).touch()
    return proj


def test_build_index_finds_projects():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_project(root, "alpha", ".git")
        _make_project(root, "beta", "CLAUDE.md")
        _make_project(root / "nested" / "deep", "gamma", "pyproject.toml")

        idx = ProjectIndex(data_dir=root / "pfind_data")
        result = idx.build([str(root)], exclude_dirs=["node_modules"])

        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result
        assert len(result["alpha"]) == 1
        assert str((root / "alpha").resolve()) == result["alpha"][0]


def test_build_index_skips_excluded_dirs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_project(root / "node_modules", "hidden_proj", ".git")
        _make_project(root, "visible", ".git")

        idx = ProjectIndex(data_dir=root / "pfind_data")
        result = idx.build([str(root)], exclude_dirs=["node_modules"])

        assert "hidden_proj" not in result
        assert "visible" in result


def test_build_index_does_not_descend_into_projects():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parent = _make_project(root, "parent_proj", ".git")
        # Create a subdir inside parent_proj that also has a marker
        sub = parent / "subpackage"
        sub.mkdir()
        (sub / "setup.py").touch()

        idx = ProjectIndex(data_dir=root / "pfind_data")
        result = idx.build([str(root)], exclude_dirs=[])

        assert "parent_proj" in result
        assert "subpackage" not in result


def test_build_index_deduplicates_symlinks():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        real = _make_project(root / "dirs", "myproj", ".git")
        # Symlink from index/ to dirs/
        index_dir = root / "index"
        index_dir.mkdir()
        os.symlink(str(real), str(index_dir / "myproj"))

        idx = ProjectIndex(data_dir=root / "pfind_data")
        result = idx.build([str(root)], exclude_dirs=[])

        assert "myproj" in result
        # Should have exactly one entry (deduplicated)
        assert len(result["myproj"]) == 1


def test_build_index_handles_name_collisions():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_project(root / "area1", "docs", ".git")
        _make_project(root / "area2", "docs", "README.md")

        idx = ProjectIndex(data_dir=root / "pfind_data")
        result = idx.build([str(root)], exclude_dirs=[])

        assert "docs" in result
        assert len(result["docs"]) == 2


# --- Search tests ---


def _build_sample_index():
    """Return a pre-built index dict for search tests."""
    return {
        "aishell": ["/projects/aishell"],
        "strictRAG": ["/projects/strictRAG"],
        "sharpattention": ["/projects/sharpattention"],
        "redditmath": ["/projects/redditmath"],
        "docs": ["/projects/docs", "/projects/other/docs"],
    }


def test_search_exact_match():
    with tempfile.TemporaryDirectory() as tmp:
        idx = ProjectIndex(data_dir=Path(tmp))
        results = idx.search("aishell", _build_sample_index())
        assert len(results) == 1
        assert results[0][0] == "aishell"
        assert results[0][2] == "exact"


def test_search_exact_case_insensitive():
    with tempfile.TemporaryDirectory() as tmp:
        idx = ProjectIndex(data_dir=Path(tmp))
        results = idx.search("AISHELL", _build_sample_index())
        assert len(results) == 1
        assert results[0][0] == "aishell"
        assert results[0][2] == "exact"


def test_search_substring():
    with tempfile.TemporaryDirectory() as tmp:
        idx = ProjectIndex(data_dir=Path(tmp))
        results = idx.search("shell", _build_sample_index())
        assert len(results) == 1
        assert results[0][0] == "aishell"
        assert results[0][2] == "substring"


def test_search_substring_multiple():
    with tempfile.TemporaryDirectory() as tmp:
        idx = ProjectIndex(data_dir=Path(tmp))
        results = idx.search("sharp", _build_sample_index())
        assert len(results) == 1
        assert results[0][0] == "sharpattention"


def test_search_fuzzy_fallback():
    with tempfile.TemporaryDirectory() as tmp:
        idx = ProjectIndex(data_dir=Path(tmp))
        results = idx.search("strct", _build_sample_index())
        # Should find strictRAG via fuzzy match
        names = [r[0] for r in results]
        assert "strictRAG" in names
        assert results[0][2] == "fuzzy"


def test_search_no_results():
    with tempfile.TemporaryDirectory() as tmp:
        idx = ProjectIndex(data_dir=Path(tmp))
        results = idx.search("zzzznonexistent", _build_sample_index())
        assert len(results) == 0


def test_search_returns_multiple_paths_for_collision():
    with tempfile.TemporaryDirectory() as tmp:
        idx = ProjectIndex(data_dir=Path(tmp))
        results = idx.search("docs", _build_sample_index())
        assert len(results) == 1
        assert len(results[0][1]) == 2


# --- CLI tests ---

from click.testing import CliRunner
from aishell.commands.pfind import pfind


def test_cli_rebuild(tmp_path):
    data_dir = tmp_path / "pfind_data"
    root = tmp_path / "projects"
    _make_project(root, "testproj", ".git")

    runner = CliRunner()
    result = runner.invoke(
        pfind, ["--rebuild", "--data-dir", str(data_dir), "--root", str(root)]
    )
    assert result.exit_code == 0
    assert "Rebuilt" in result.output
    assert (data_dir / "invindex.json").exists()


def test_cli_search(tmp_path):
    data_dir = tmp_path / "pfind_data"
    root = tmp_path / "projects"
    _make_project(root, "myproject", ".git")

    runner = CliRunner()
    # Build first
    runner.invoke(
        pfind, ["--rebuild", "--data-dir", str(data_dir), "--root", str(root)]
    )
    # Search
    result = runner.invoke(pfind, ["myproject", "--data-dir", str(data_dir)])
    assert result.exit_code == 0
    assert "myproject" in result.output


def test_cli_stats(tmp_path):
    data_dir = tmp_path / "pfind_data"
    root = tmp_path / "projects"
    _make_project(root, "proj1", ".git")
    _make_project(root, "proj2", "CLAUDE.md")

    runner = CliRunner()
    runner.invoke(
        pfind, ["--rebuild", "--data-dir", str(data_dir), "--root", str(root)]
    )
    result = runner.invoke(pfind, ["--stats", "--data-dir", str(data_dir)])
    assert result.exit_code == 0
    assert "2" in result.output  # 2 projects


def test_cli_no_index_prompts_rebuild(tmp_path):
    data_dir = tmp_path / "pfind_data"
    runner = CliRunner()
    result = runner.invoke(pfind, ["anything", "--data-dir", str(data_dir)])
    assert result.exit_code == 0
    assert "rebuild" in result.output.lower() or "No index" in result.output
