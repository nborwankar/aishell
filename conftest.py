"""Root conftest.py — shared configuration and markers for the test suite."""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "playwright: tests that require a Playwright browser (chromium)"
    )
    config.addinivalue_line(
        "markers", "database: tests that require PostgreSQL"
    )
    config.addinivalue_line(
        "markers", "slow: tests that take more than 5 seconds"
    )
