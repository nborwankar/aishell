"""
LLM-assisted web navigation.

This module integrates LLM capabilities to translate natural language tasks
into navigation action sequences.
"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from .actions import create_action, Action
from .config import ScrapingConfig
from .navigator import WebNavigator, NavigationResult


class LLMNavigator:
    """LLM-assisted web navigation and scraping."""

    def __init__(
        self,
        llm_provider,
        navigator: WebNavigator,
        fallback_provider=None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None
    ):
        """
        Initialize LLM navigator.

        Args:
            llm_provider: LLM provider instance (from aishell.llm)
            navigator: WebNavigator instance
            fallback_provider: Optional fallback LLM provider
            model: Optional model override for primary provider
            fallback_model: Optional model override for fallback provider
        """
        self.llm_provider = llm_provider
        self.navigator = navigator
        self.fallback_provider = fallback_provider
        self.model = model
        self.fallback_model = fallback_model

    async def task_to_actions(
        self,
        task: str,
        url: str,
        page_content: Optional[str] = None
    ) -> List[Action]:
        """
        Convert natural language task to action sequence using LLM.

        Args:
            task: Natural language description of task
            url: Target URL
            page_content: Optional HTML content for context

        Returns:
            List of Action objects

        Raises:
            ValueError: If LLM response is invalid
        """
        # Build prompt for LLM
        prompt = self._build_task_prompt(task, url, page_content)

        try:
            # Query LLM
            response = await self.llm_provider.query(prompt, model=self.model)
            if response.is_error:
                raise ValueError(response.error)
            actions = self._parse_llm_response(response.content)
            return actions

        except Exception as e:
            if self.fallback_provider:
                # Try fallback provider
                response = await self.fallback_provider.query(prompt, model=self.fallback_model)
                if response.is_error:
                    raise ValueError(response.error)
                actions = self._parse_llm_response(response.content)
                return actions
            else:
                raise ValueError(f"Failed to generate actions from task: {str(e)}")

    def _build_task_prompt(
        self,
        task: str,
        url: str,
        page_content: Optional[str] = None
    ) -> str:
        """
        Build prompt for LLM to generate navigation actions.

        Args:
            task: User's task description
            url: Target URL
            page_content: Optional page HTML for context

        Returns:
            Prompt string
        """
        prompt = f"""You are a web scraping expert. Convert the following natural language task into a sequence of browser actions.

Task: {task}
URL: {url}

Available action types:
1. navigate - Navigate to URL
   {{"type": "navigate", "url": "https://example.com", "wait_until": "networkidle"}}

2. click - Click on element
   {{"type": "click", "selector": ".menu-item", "timeout": 30000}}

3. hover - Hover over element
   {{"type": "hover", "selector": ".dropdown-trigger", "timeout": 30000}}

4. wait - Wait for condition
   {{"type": "wait", "selector": ".content-loaded", "state": "visible", "timeout": 30000}}
   {{"type": "wait", "duration": 1000}}

5. extract - Extract data from page
   {{"type": "extract", "selectors": {{"title": "h1", "price": ".price"}}, "extract_type": "text", "multiple": false}}

6. scroll - Scroll the page
   {{"type": "scroll", "direction": "down", "amount": 500}}

7. type - Type text into input
   {{"type": "type", "selector": "input[name='search']", "text": "query", "clear_first": true}}

8. select - Select dropdown option
   {{"type": "select", "selector": "select[name='category']", "value": "electronics"}}

9. screenshot - Take screenshot
   {{"type": "screenshot", "path": "screenshot.png", "full_page": false}}

10. js - Execute JavaScript (PREFERRED for menu navigation)
    {{"type": "js", "code": "document.querySelector('a[href*=target]').click()"}}

Instructions:
- Use CSS selectors (e.g., ".class", "#id", "tag[attr='value']", "a:has-text('Click')")
- IMPORTANT: For dropdown/mega menus, use JavaScript (js action) instead of hover - menus are often hidden
- For menu navigation: use js action with document.querySelector('selector').click()
- Use href patterns: 'a[href*="credit-card"]', 'a[href*="loans"]'
- For AJAX content: use wait after interactions (duration: 2000-5000ms)
- After JS-triggered navigation, add wait with duration: 5000 for page load
- Extract data using descriptive field names
- Return ONLY a valid JSON array of actions, no explanation

"""

        if page_content:
            # Include relevant parts of page content for context
            # (truncate if too long to avoid token limits)
            content_preview = page_content[:2000] if len(page_content) > 2000 else page_content
            prompt += f"\nPage HTML preview:\n```html\n{content_preview}\n```\n"

        prompt += "\nReturn JSON array of actions:"

        return prompt

    def _parse_llm_response(self, response: str) -> List[Action]:
        """
        Parse LLM response into action list.

        Args:
            response: LLM response text

        Returns:
            List of Action objects

        Raises:
            ValueError: If response cannot be parsed
        """
        # Extract JSON from response (LLM might include explanation)
        response = response.strip()

        # Try to find JSON array in response
        json_start = response.find('[')
        json_end = response.rfind(']') + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON array found in LLM response")

        json_str = response[json_start:json_end]

        try:
            action_dicts = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {str(e)}")

        if not isinstance(action_dicts, list):
            raise ValueError("LLM response must be a JSON array")

        # Convert to Action objects
        actions = []
        for action_dict in action_dicts:
            action = create_action(action_dict)
            actions.append(action)

        return actions

    async def execute_task(
        self,
        task: str,
        url: str,
        save_config: Optional[Path] = None
    ) -> NavigationResult:
        """
        Execute a natural language task.

        Args:
            task: Natural language description
            url: Target URL
            save_config: Optional path to save generated config

        Returns:
            NavigationResult

        Raises:
            RuntimeError: If navigator not started
        """
        # Get current page content for context
        page_content = None
        try:
            if self.navigator.page and self.navigator.page.url == url:
                page_content = await self.navigator.get_page_source()
        except Exception:
            pass

        # Generate actions from task
        actions = await self.task_to_actions(task, url, page_content)

        # Create config
        config = ScrapingConfig(
            name=task[:50],  # Use first 50 chars of task as name
            url=url,
            actions=actions,
            llm_provider=self.llm_provider.__class__.__name__
        )

        # Save config if requested
        if save_config:
            config.save(save_config)

        # Execute navigation
        result = await self.navigator.execute_config(config)

        return result

    async def refine_actions(
        self,
        task: str,
        url: str,
        previous_actions: List[Action],
        error_message: str
    ) -> List[Action]:
        """
        Refine actions based on previous failure.

        Args:
            task: Original task
            url: Target URL
            previous_actions: Actions that failed
            error_message: Error from previous attempt

        Returns:
            Refined list of actions
        """
        prompt = f"""The following navigation sequence failed. Analyze the error and provide corrected actions.

Task: {task}
URL: {url}

Previous actions:
{json.dumps([a.to_dict() for a in previous_actions], indent=2)}

Error: {error_message}

Common issues and fixes:
- Selector not found: Try alternative selectors (.class, #id, [data-*])
- Timeout: Increase timeout or add wait action
- Element not visible: Add hover or scroll action first
- AJAX content: Add wait for selector after interaction

Return ONLY a corrected JSON array of actions:
"""

        if self.fallback_provider:
            response = await self.fallback_provider.query(prompt, model=self.fallback_model)
        else:
            response = await self.llm_provider.query(prompt, model=self.model)

        if response.is_error:
            raise ValueError(response.error)
        return self._parse_llm_response(response.content)

    async def execute_with_retry(
        self,
        task: str,
        url: str,
        max_retries: int = 2,
        save_config: Optional[Path] = None
    ) -> NavigationResult:
        """
        Execute task with automatic retry and refinement.

        Args:
            task: Natural language task
            url: Target URL
            max_retries: Maximum retry attempts
            save_config: Optional path to save final config

        Returns:
            NavigationResult
        """
        actions = None
        result = None

        for attempt in range(max_retries + 1):
            if attempt == 0:
                # First attempt - generate from task
                page_content = None
                try:
                    if self.navigator.page and self.navigator.page.url == url:
                        page_content = await self.navigator.get_page_source()
                except Exception:
                    pass

                actions = await self.task_to_actions(task, url, page_content)

            else:
                # Retry - refine based on previous error
                error_msg = "; ".join(result.errors) if result else "Unknown error"
                actions = await self.refine_actions(task, url, actions, error_msg)

            # Execute actions
            config = ScrapingConfig(
                name=task[:50],
                url=url,
                actions=actions,
                llm_provider=self.llm_provider.__class__.__name__
            )

            result = await self.navigator.execute_config(config)

            if result.success:
                # Save successful config
                if save_config:
                    config.save(save_config)
                break

        return result

    def create_config_from_actions(
        self,
        name: str,
        url: str,
        actions: List[Action],
        output_format: str = "json"
    ) -> ScrapingConfig:
        """
        Create a reusable configuration from actions.

        Args:
            name: Configuration name
            url: Target URL
            actions: List of actions
            output_format: Output format (json, yaml, csv)

        Returns:
            ScrapingConfig
        """
        return ScrapingConfig(
            name=name,
            url=url,
            actions=actions,
            output={
                "format": output_format,
                "file": f"{name.replace(' ', '_').lower()}_data.{output_format}"
            },
            llm_provider=self.llm_provider.__class__.__name__,
            fallback_provider=self.fallback_provider.__class__.__name__ if self.fallback_provider else None
        )
