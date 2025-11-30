"""
Web navigation engine using Playwright.

This module provides the core navigation functionality for web scraping,
executing action sequences and extracting data from web pages.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError
)

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
    NavigateAction
)
from .extractors import DataExtractor
from .config import ScrapingConfig


class NavigationResult:
    """Result of a navigation/scraping task."""

    def __init__(self):
        self.success: bool = False
        self.data: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.screenshots: List[str] = []
        self.actions_executed: int = 0
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "errors": self.errors,
            "screenshots": self.screenshots,
            "actions_executed": self.actions_executed,
            "metadata": self.metadata
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert result to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class WebNavigator:
    """Navigate web pages using Playwright."""

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        user_agent: Optional[str] = None,
        viewport: Optional[Dict[str, int]] = None,
        timeout: int = 30000
    ):
        """
        Initialize the web navigator.

        Args:
            headless: Whether to run browser in headless mode
            browser_type: Browser to use (chromium, firefox, webkit)
            user_agent: Custom user agent string
            viewport: Viewport size {'width': int, 'height': int}
            timeout: Default timeout in milliseconds
        """
        self.headless = headless
        self.browser_type = browser_type
        self.user_agent = user_agent
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.timeout = timeout

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.extractor: Optional[DataExtractor] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Start the browser and create a new page."""
        self.playwright = await async_playwright().start()

        # Get browser launcher
        if self.browser_type == "chromium":
            launcher = self.playwright.chromium
        elif self.browser_type == "firefox":
            launcher = self.playwright.firefox
        elif self.browser_type == "webkit":
            launcher = self.playwright.webkit
        else:
            raise ValueError(f"Unknown browser type: {self.browser_type}")

        # Launch browser
        self.browser = await launcher.launch(headless=self.headless)

        # Create context
        context_options = {
            "viewport": self.viewport,
            "user_agent": self.user_agent
        }
        self.context = await self.browser.new_context(**{k: v for k, v in context_options.items() if v is not None})

        # Create page
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout)

        # Create extractor
        self.extractor = DataExtractor(self.page)

    async def close(self) -> None:
        """Close the browser and cleanup."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def execute_action(self, action: Action) -> Optional[Any]:
        """
        Execute a single action.

        Args:
            action: Action to execute

        Returns:
            Action result (if any)

        Raises:
            ValueError: If action type is unknown
            PlaywrightTimeoutError: If action times out
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        action_type = action.type

        if action_type == ActionType.NAVIGATE:
            return await self._execute_navigate(action)
        elif action_type == ActionType.CLICK:
            return await self._execute_click(action)
        elif action_type == ActionType.HOVER:
            return await self._execute_hover(action)
        elif action_type == ActionType.WAIT:
            return await self._execute_wait(action)
        elif action_type == ActionType.EXTRACT:
            return await self._execute_extract(action)
        elif action_type == ActionType.SCROLL:
            return await self._execute_scroll(action)
        elif action_type == ActionType.TYPE:
            return await self._execute_type(action)
        elif action_type == ActionType.SELECT:
            return await self._execute_select(action)
        elif action_type == ActionType.SCREENSHOT:
            return await self._execute_screenshot(action)
        elif action_type == ActionType.JAVASCRIPT:
            return await self._execute_javascript(action)
        else:
            raise ValueError(f"Unknown action type: {action_type}")

    async def _execute_navigate(self, action: NavigateAction) -> None:
        """Navigate to URL."""
        await self.page.goto(action.url, wait_until=action.wait_until)

    async def _execute_click(self, action: ClickAction) -> None:
        """Click on element."""
        await self.page.click(
            action.selector,
            button=action.button,
            click_count=action.click_count,
            timeout=action.timeout
        )

    async def _execute_hover(self, action: HoverAction) -> None:
        """Hover over element."""
        await self.page.hover(action.selector, timeout=action.timeout)

    async def _execute_wait(self, action: WaitAction) -> None:
        """Wait for condition."""
        if action.selector:
            await self.page.wait_for_selector(
                action.selector,
                state=action.state,
                timeout=action.timeout
            )
        elif action.duration:
            await asyncio.sleep(action.duration / 1000.0)

    async def _execute_extract(self, action: ExtractAction) -> Dict[str, Any]:
        """Extract data from page."""
        return await self.extractor.extract_structured(
            selectors=action.selectors,
            extract_type=action.extract_type,
            attribute=action.attribute,
            multiple=action.multiple
        )

    async def _execute_scroll(self, action: ScrollAction) -> None:
        """Scroll the page."""
        if action.selector:
            # Scroll specific element
            element = await self.page.query_selector(action.selector)
            if element:
                await element.scroll_into_view_if_needed()
        else:
            # Scroll entire page
            scroll_map = {
                "down": "window.scrollBy(0, {amount})",
                "up": "window.scrollBy(0, -{amount})",
                "left": "window.scrollBy(-{amount}, 0)",
                "right": "window.scrollBy({amount}, 0)"
            }

            amount = action.amount or "window.innerHeight"
            js_code = scroll_map.get(action.direction, scroll_map["down"])
            js_code = js_code.replace("{amount}", str(amount))
            await self.page.evaluate(js_code)

    async def _execute_type(self, action: TypeAction) -> None:
        """Type text into input."""
        if action.clear_first:
            await self.page.fill(action.selector, "")

        await self.page.type(action.selector, action.text, delay=action.delay)

    async def _execute_select(self, action: SelectAction) -> None:
        """Select option from dropdown."""
        if action.value:
            await self.page.select_option(action.selector, value=action.value)
        elif action.label:
            await self.page.select_option(action.selector, label=action.label)
        elif action.index is not None:
            await self.page.select_option(action.selector, index=action.index)

    async def _execute_screenshot(self, action: ScreenshotAction) -> str:
        """Take screenshot."""
        screenshot_path = Path(action.path)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        if action.selector:
            # Screenshot specific element
            element = await self.page.query_selector(action.selector)
            if element:
                await element.screenshot(path=str(screenshot_path))
        else:
            # Screenshot full page or viewport
            await self.page.screenshot(
                path=str(screenshot_path),
                full_page=action.full_page
            )

        return str(screenshot_path)

    async def _execute_javascript(self, action: JavaScriptAction) -> Any:
        """Execute JavaScript code."""
        return await self.page.evaluate(action.code)

    async def execute_config(self, config: ScrapingConfig) -> NavigationResult:
        """
        Execute a scraping configuration.

        Args:
            config: Scraping configuration

        Returns:
            NavigationResult with extracted data
        """
        result = NavigationResult()

        try:
            # Navigate to URL if not already there
            if self.page.url != config.url:
                await self.page.goto(config.url, wait_until="networkidle")

            # Execute actions
            for i, action in enumerate(config.actions):
                try:
                    action_result = await self.execute_action(action)

                    # Store extracted data
                    if action.type == ActionType.EXTRACT and action_result:
                        result.data.update(action_result)

                    # Store screenshot paths
                    if action.type == ActionType.SCREENSHOT and action_result:
                        result.screenshots.append(action_result)

                    # Store JavaScript results
                    if action.type == ActionType.JAVASCRIPT and action_result:
                        # Try to parse as JSON, otherwise store as string
                        try:
                            import json
                            js_data = json.loads(action_result)
                            if isinstance(js_data, dict):
                                result.data.update(js_data)
                            else:
                                result.data[f"js_result_{i}"] = js_data
                        except (json.JSONDecodeError, TypeError):
                            result.data[f"js_result_{i}"] = action_result

                    result.actions_executed += 1

                except Exception as e:
                    error_msg = f"Error executing action {i} ({action.type.value}): {str(e)}"
                    result.errors.append(error_msg)

                    # Decide whether to continue or stop
                    if action.type in [ActionType.NAVIGATE, ActionType.CLICK, ActionType.WAIT]:
                        # Critical actions - stop execution
                        break

            # Extract page metadata
            result.metadata = await self.extractor.extract_metadata()

            # Mark success if at least one action executed without critical errors
            result.success = result.actions_executed > 0 and not any(
                "NAVIGATE" in err or "CLICK" in err for err in result.errors
            )

        except Exception as e:
            result.errors.append(f"Fatal error: {str(e)}")
            result.success = False

        return result

    async def navigate_and_extract(
        self,
        url: str,
        actions: List[Action]
    ) -> NavigationResult:
        """
        Navigate to URL and execute actions.

        Args:
            url: URL to navigate to
            actions: List of actions to execute

        Returns:
            NavigationResult
        """
        config = ScrapingConfig(
            name="Ad-hoc Navigation",
            url=url,
            actions=actions
        )

        return await self.execute_config(config)

    async def get_page_source(self) -> str:
        """Get current page HTML source."""
        if not self.page:
            raise RuntimeError("Browser not started")
        return await self.page.content()

    async def get_current_url(self) -> str:
        """Get current page URL."""
        if not self.page:
            raise RuntimeError("Browser not started")
        return self.page.url

    async def take_screenshot(self, path: str, full_page: bool = False) -> str:
        """
        Take a screenshot of current page.

        Args:
            path: Where to save screenshot
            full_page: Whether to capture full page

        Returns:
            Path to saved screenshot
        """
        if not self.page:
            raise RuntimeError("Browser not started")

        screenshot_path = Path(path)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        await self.page.screenshot(path=str(screenshot_path), full_page=full_page)
        return str(screenshot_path)
