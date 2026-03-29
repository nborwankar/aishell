"""Tier 1 + 2: Tests for file_search.py helpers and MacOSFileSearcher."""

import pytest
from datetime import datetime

from aishell.search.file_search import format_size, format_date, MacOSFileSearcher


# ── format_size (pure) ──────────────────────────────────────────────


class TestFormatSize:
    def test_bytes(self):
        assert format_size(500) == "500.0 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert format_size(1024**3) == "1.0 GB"

    def test_zero(self):
        assert format_size(0) == "0.0 B"


# ── format_date (pure, time-dependent but testable) ─────────────────


class TestFormatDate:
    def test_yesterday(self):
        from datetime import timedelta

        yesterday = datetime.now() - timedelta(days=1)
        assert format_date(yesterday) == "yesterday"

    def test_days_ago(self):
        from datetime import timedelta

        three_days = datetime.now() - timedelta(days=3)
        assert "3 days ago" in format_date(three_days)

    def test_old_date_shows_absolute(self):
        old = datetime(2020, 1, 15, 10, 30)
        result = format_date(old)
        assert "2020-01-15" in result


# ── MacOSFileSearcher internals ─────────────────────────────────────


class TestMacOSFileSearcher:
    def test_parse_size_for_find_greater(self):
        searcher = MacOSFileSearcher()
        result = searcher._parse_size_for_find(">1MB")
        assert result == f"+{1024**2}c"

    def test_parse_size_for_find_less(self):
        searcher = MacOSFileSearcher()
        result = searcher._parse_size_for_find("<500KB")
        assert result == f"-{500 * 1024}c"

    def test_parse_size_for_find_unparsable(self):
        searcher = MacOSFileSearcher()
        assert searcher._parse_size_for_find("unknown") == "unknown"

    def test_parse_date_for_find_today(self):
        searcher = MacOSFileSearcher()
        assert searcher._parse_date_for_find("today") == ["-mtime", "-1"]

    def test_parse_date_for_find_last_week(self):
        searcher = MacOSFileSearcher()
        assert searcher._parse_date_for_find("last week") == ["-mtime", "-7"]

    def test_parse_date_for_find_numeric(self):
        searcher = MacOSFileSearcher()
        assert searcher._parse_date_for_find("14") == ["-mtime", "-14"]

    def test_parse_date_for_find_unparsable(self):
        searcher = MacOSFileSearcher()
        assert searcher._parse_date_for_find("garbage") == []

    def test_build_type_query_known_type(self):
        searcher = MacOSFileSearcher()
        result = searcher._build_type_query("pdf")
        assert any("com.adobe.pdf" in q for q in result)

    def test_build_type_query_extension(self):
        searcher = MacOSFileSearcher()
        result = searcher._build_type_query("rs")
        assert any("*.rs" in q for q in result)
