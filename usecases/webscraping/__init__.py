"""
Web Scraping Module for AIShell

This module provides LLM-assisted web scraping capabilities using Playwright.
It allows navigation and data extraction from JavaScript-heavy websites using
natural language task descriptions.

Main components:
- actions: Define navigation action types
- navigator: Core Playwright-based navigation engine
- llm_navigator: LLM-assisted task translation and execution
- extractors: Data extraction utilities
- config: Configuration file management

Example usage:
    from usecases.webscraping import WebNavigator, LLMNavigator, ScrapingConfig
    from aishell.llm.providers import ClaudeProvider

    # Initialize
    llm = ClaudeProvider()
    async with WebNavigator(headless=True) as navigator:
        llm_nav = LLMNavigator(llm, navigator)

        # Execute task
        result = await llm_nav.execute_task(
            task="Extract all product names and prices",
            url="https://example.com",
            save_config="products.yaml"
        )

        print(result.to_json())
"""

from .actions import (
    Action,
    ActionType,
    ClickAction,
    HoverAction,
    WaitAction,
    ExtractAction,
    ScrollAction,
    TypeAction,
    SelectAction,
    ScreenshotAction,
    JavaScriptAction,
    NavigateAction,
    create_action
)

from .navigator import (
    WebNavigator,
    NavigationResult
)

from .llm_navigator import (
    LLMNavigator
)

from .extractors import (
    DataExtractor
)

from .config import (
    ScrapingConfig,
    ConfigValidator,
    ConfigLibrary
)

__all__ = [
    # Actions
    "Action",
    "ActionType",
    "ClickAction",
    "HoverAction",
    "WaitAction",
    "ExtractAction",
    "ScrollAction",
    "TypeAction",
    "SelectAction",
    "ScreenshotAction",
    "JavaScriptAction",
    "NavigateAction",
    "create_action",

    # Navigation
    "WebNavigator",
    "NavigationResult",
    "LLMNavigator",

    # Extraction
    "DataExtractor",

    # Configuration
    "ScrapingConfig",
    "ConfigValidator",
    "ConfigLibrary",
]
