"""
Data extraction utilities for web scraping.

This module provides utilities to extract structured data from web pages
using Playwright's page object.
"""

from typing import Any, Dict, List, Optional, Union
from playwright.async_api import Page, ElementHandle


class DataExtractor:
    """Extract structured data from web pages."""

    def __init__(self, page: Page):
        """
        Initialize the data extractor.

        Args:
            page: Playwright page object
        """
        self.page = page

    async def extract_text(
        self,
        selector: str,
        multiple: bool = False
    ) -> Union[str, List[str], None]:
        """
        Extract text content from elements.

        Args:
            selector: CSS selector
            multiple: Whether to extract from all matching elements

        Returns:
            Extracted text (single string or list of strings)
        """
        if multiple:
            elements = await self.page.query_selector_all(selector)
            texts = []
            for element in elements:
                text = await element.inner_text()
                if text:
                    texts.append(text.strip())
            return texts
        else:
            element = await self.page.query_selector(selector)
            if element:
                text = await element.inner_text()
                return text.strip() if text else None
            return None

    async def extract_html(
        self,
        selector: str,
        multiple: bool = False
    ) -> Union[str, List[str], None]:
        """
        Extract HTML content from elements.

        Args:
            selector: CSS selector
            multiple: Whether to extract from all matching elements

        Returns:
            Extracted HTML (single string or list of strings)
        """
        if multiple:
            elements = await self.page.query_selector_all(selector)
            htmls = []
            for element in elements:
                html = await element.inner_html()
                if html:
                    htmls.append(html)
            return htmls
        else:
            element = await self.page.query_selector(selector)
            if element:
                return await element.inner_html()
            return None

    async def extract_attribute(
        self,
        selector: str,
        attribute: str,
        multiple: bool = False
    ) -> Union[str, List[str], None]:
        """
        Extract attribute values from elements.

        Args:
            selector: CSS selector
            attribute: Attribute name (e.g., 'href', 'src', 'data-id')
            multiple: Whether to extract from all matching elements

        Returns:
            Extracted attribute value(s)
        """
        if multiple:
            elements = await self.page.query_selector_all(selector)
            values = []
            for element in elements:
                value = await element.get_attribute(attribute)
                if value:
                    values.append(value)
            return values
        else:
            element = await self.page.query_selector(selector)
            if element:
                return await element.get_attribute(attribute)
            return None

    async def extract_table(
        self,
        selector: str,
        headers: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Extract data from an HTML table.

        Args:
            selector: CSS selector for the table
            headers: Optional list of header names (uses first row if None)

        Returns:
            List of dictionaries representing table rows
        """
        table = await self.page.query_selector(selector)
        if not table:
            return []

        rows = await table.query_selector_all("tr")
        if not rows:
            return []

        data = []
        start_row = 0

        # Get headers
        if headers is None:
            header_row = rows[0]
            header_cells = await header_row.query_selector_all("th, td")
            headers = []
            for cell in header_cells:
                text = await cell.inner_text()
                headers.append(text.strip())
            start_row = 1

        # Extract data rows
        for row in rows[start_row:]:
            cells = await row.query_selector_all("td")
            if len(cells) == len(headers):
                row_data = {}
                for i, cell in enumerate(cells):
                    text = await cell.inner_text()
                    row_data[headers[i]] = text.strip()
                data.append(row_data)

        return data

    async def extract_links(
        self,
        selector: str = "a",
        include_text: bool = True
    ) -> List[Dict[str, str]]:
        """
        Extract links from the page.

        Args:
            selector: CSS selector for link elements
            include_text: Whether to include link text

        Returns:
            List of dictionaries with 'href' and optionally 'text' keys
        """
        links = await self.page.query_selector_all(selector)
        results = []

        for link in links:
            href = await link.get_attribute("href")
            if href:
                link_data = {"href": href}
                if include_text:
                    text = await link.inner_text()
                    link_data["text"] = text.strip() if text else ""
                results.append(link_data)

        return results

    async def extract_structured(
        self,
        selectors: Dict[str, str],
        extract_type: str = "text",
        attribute: Optional[str] = None,
        multiple: bool = False
    ) -> Dict[str, Any]:
        """
        Extract structured data using multiple selectors.

        Args:
            selectors: Dictionary mapping field names to CSS selectors
            extract_type: Type of extraction ("text", "html", "attribute")
            attribute: Attribute name (required if extract_type="attribute")
            multiple: Whether to extract all matching elements

        Returns:
            Dictionary with extracted data
        """
        data = {}

        for field_name, selector in selectors.items():
            if extract_type == "text":
                data[field_name] = await self.extract_text(selector, multiple)
            elif extract_type == "html":
                data[field_name] = await self.extract_html(selector, multiple)
            elif extract_type == "attribute":
                if not attribute:
                    raise ValueError("attribute parameter required for extract_type='attribute'")
                data[field_name] = await self.extract_attribute(selector, attribute, multiple)
            else:
                raise ValueError(f"Unknown extract_type: {extract_type}")

        return data

    async def extract_metadata(self) -> Dict[str, str]:
        """
        Extract common page metadata.

        Returns:
            Dictionary with title, description, keywords, etc.
        """
        metadata = {}

        # Title
        title = await self.page.title()
        metadata["title"] = title

        # Meta tags
        meta_selectors = {
            "description": 'meta[name="description"]',
            "keywords": 'meta[name="keywords"]',
            "og:title": 'meta[property="og:title"]',
            "og:description": 'meta[property="og:description"]',
            "og:image": 'meta[property="og:image"]',
        }

        for key, selector in meta_selectors.items():
            element = await self.page.query_selector(selector)
            if element:
                content = await element.get_attribute("content")
                if content:
                    metadata[key] = content

        # Canonical URL
        canonical = await self.page.query_selector('link[rel="canonical"]')
        if canonical:
            href = await canonical.get_attribute("href")
            if href:
                metadata["canonical"] = href

        return metadata

    async def wait_for_content_load(
        self,
        selector: str,
        timeout: int = 30000
    ) -> bool:
        """
        Wait for dynamic content to load.

        Args:
            selector: CSS selector for element to wait for
            timeout: Maximum wait time in milliseconds

        Returns:
            True if content loaded, False if timeout
        """
        try:
            await self.page.wait_for_selector(
                selector,
                state="visible",
                timeout=timeout
            )
            return True
        except Exception:
            return False

    async def extract_with_fallback(
        self,
        selectors: List[str],
        extract_type: str = "text",
        attribute: Optional[str] = None
    ) -> Optional[str]:
        """
        Try multiple selectors until one succeeds.

        Args:
            selectors: List of CSS selectors to try in order
            extract_type: Type of extraction
            attribute: Attribute name if extract_type="attribute"

        Returns:
            Extracted value from first successful selector
        """
        for selector in selectors:
            try:
                if extract_type == "text":
                    result = await self.extract_text(selector)
                elif extract_type == "html":
                    result = await self.extract_html(selector)
                elif extract_type == "attribute":
                    if not attribute:
                        raise ValueError("attribute required for extract_type='attribute'")
                    result = await self.extract_attribute(selector, attribute)
                else:
                    raise ValueError(f"Unknown extract_type: {extract_type}")

                if result:
                    return result
            except Exception:
                continue

        return None
