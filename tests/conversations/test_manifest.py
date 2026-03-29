"""Tier 1: Unit tests for manifest.py — load, save, already_exported."""

import json
import os

import pytest

from aishell.commands.conversations.manifest import (
    load_manifest,
    save_manifest,
    already_exported,
)


class TestLoadManifest:
    def test_returns_empty_when_missing(self, tmp_path):
        result = load_manifest(str(tmp_path / "nonexistent.json"))
        assert result == {"exported_at": None, "conversations": []}

    def test_loads_existing_file(self, tmp_path):
        data = {"exported_at": "2024-01-01T00:00:00Z", "conversations": [{"source_id": "x"}]}
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(data))

        result = load_manifest(str(path))
        assert result["exported_at"] == "2024-01-01T00:00:00Z"
        assert len(result["conversations"]) == 1


class TestSaveManifest:
    def test_creates_directory_and_saves(self, tmp_path):
        conv_dir = tmp_path / "conversations"
        manifest_path = conv_dir / "manifest.json"
        manifest = {"conversations": [{"source_id": "abc"}]}

        save_manifest(manifest, str(manifest_path), str(conv_dir))

        assert manifest_path.exists()
        saved = json.loads(manifest_path.read_text())
        assert "exported_at" in saved
        assert saved["conversations"][0]["source_id"] == "abc"

    def test_updates_exported_at_timestamp(self, tmp_path):
        conv_dir = tmp_path / "conversations"
        manifest_path = conv_dir / "manifest.json"
        manifest = {"exported_at": None, "conversations": []}

        save_manifest(manifest, str(manifest_path), str(conv_dir))

        saved = json.loads(manifest_path.read_text())
        assert saved["exported_at"] is not None
        assert saved["exported_at"].endswith("Z")

    def test_roundtrip(self, tmp_path):
        conv_dir = tmp_path / "conversations"
        manifest_path = conv_dir / "manifest.json"
        original = {
            "conversations": [
                {"source_id": "id1", "title": "First"},
                {"source_id": "id2", "title": "Second"},
            ]
        }

        save_manifest(original, str(manifest_path), str(conv_dir))
        loaded = load_manifest(str(manifest_path))

        assert len(loaded["conversations"]) == 2
        assert loaded["conversations"][0]["source_id"] == "id1"


class TestAlreadyExported:
    def test_returns_true_when_file_exists(self, tmp_path):
        (tmp_path / "abc123.json").write_text("{}")
        assert already_exported("abc123", str(tmp_path)) is True

    def test_returns_false_when_missing(self, tmp_path):
        assert already_exported("abc123", str(tmp_path)) is False

    def test_returns_false_for_nonexistent_dir(self):
        assert already_exported("abc", "/tmp/nonexistent_dir_xyz") is False
