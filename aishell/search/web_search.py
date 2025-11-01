import asyncio
from typing import List, Dict, Any
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Try to import stealth mode (optional, for bypassing bot detection)
try:
    from playwright_stealth import Stealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    Stealth = None

console = Console()


class WebSearcher:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.playwright = None
    
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Apply stealth mode if available (helps bypass moderate bot detection)
        # Tested: Works on Wikipedia and MDN (successfully bypasses moderate detection)
        # Limitation: Cannot bypass Google's aggressive detection (and shouldn't try)
        if STEALTH_AVAILABLE and Stealth:
            stealth = Stealth()
            await stealth.apply_stealth_async(self.context)
            console.print("[dim]Stealth mode enabled[/dim]")

        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def search_google(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Google and return results."""
        page = await self.context.new_page()
        results = []
        
        try:
            # Navigate to Google
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            await page.goto(search_url, wait_until="networkidle")
            
            # Wait for search results
            await page.wait_for_selector("div#search", timeout=10000)
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')
            
            # Find search result containers
            search_results = soup.find_all('div', class_='g')
            
            for result in search_results[:limit]:
                try:
                    # Extract title
                    title_elem = result.find('h3')
                    title = title_elem.text if title_elem else "No title"
                    
                    # Extract URL
                    link_elem = result.find('a')
                    url = link_elem.get('href', '') if link_elem else ""
                    
                    # Extract snippet
                    snippet_elem = result.find('div', attrs={'data-sncf': '1'})
                    if not snippet_elem:
                        # Try alternative snippet location
                        snippet_elem = result.find('span', class_='aCOpRe')
                    snippet = snippet_elem.text if snippet_elem else "No description available"
                    
                    if title and url:
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet
                        })
                except Exception as e:
                    # Skip problematic results
                    continue
            
        except Exception as e:
            console.print(f"[red]Error during search: {str(e)}[/red]")
        finally:
            await page.close()
        
        return results
    
    async def search_duckduckgo(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search DuckDuckGo and return results."""
        page = await self.context.new_page()
        results = []
        
        try:
            # Navigate to DuckDuckGo
            search_url = f"https://duckduckgo.com/?q={quote_plus(query)}"
            await page.goto(search_url, wait_until="networkidle")
            
            # Wait for search results
            await page.wait_for_selector("div.results", timeout=10000)
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')
            
            # Find search result containers
            search_results = soup.find_all('article', attrs={'data-testid': 'result'})
            
            for result in search_results[:limit]:
                try:
                    # Extract title
                    title_elem = result.find('h2')
                    title = title_elem.text if title_elem else "No title"
                    
                    # Extract URL
                    link_elem = result.find('a', attrs={'data-testid': 'result-title-a'})
                    url = link_elem.get('href', '') if link_elem else ""
                    
                    # Extract snippet
                    snippet_elem = result.find('div', attrs={'data-result': 'snippet'})
                    if not snippet_elem:
                        snippet_elem = result.find('span', class_='result__snippet')
                    snippet = snippet_elem.text if snippet_elem else "No description available"
                    
                    if title and url:
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet
                        })
                except Exception as e:
                    # Skip problematic results
                    continue
            
        except Exception as e:
            console.print(f"[red]Error during search: {str(e)}[/red]")
        finally:
            await page.close()

        return results

    async def search_hackernews(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Hacker News and return results.

        Uses Algolia interface which doesn't have strict bot detection like Google.
        """
        page = await self.context.new_page()
        results = []

        try:
            # Navigate to Hacker News Algolia search interface
            search_url = f"https://hn.algolia.com/?q={quote_plus(query)}"
            await page.goto(search_url, wait_until="networkidle", timeout=15000)

            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Find story containers in Algolia interface
            # Each story has class 'Story_container' with title and metadata divs inside
            story_containers = soup.find_all('div', class_='Story_container')

            for story in story_containers[:limit]:
                try:
                    # Extract title and URL from Story_title div
                    title_div = story.find('div', class_='Story_title')
                    if not title_div:
                        continue

                    link_elem = title_div.find('a')
                    if not link_elem:
                        continue

                    title = link_elem.get_text(strip=True)
                    url = link_elem.get('href', '')

                    # Extract metadata from Story_meta div
                    meta_div = story.find('div', class_='Story_meta')
                    snippet = ""
                    if meta_div:
                        snippet = meta_div.get_text(strip=True)

                    if title and url:
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet
                        })
                except Exception as e:
                    # Skip problematic results
                    continue

        except Exception as e:
            console.print(f"[red]Error during Hacker News search: {str(e)}[/red]")
        finally:
            await page.close()

        return results


def display_results(results: List[Dict[str, Any]], query: str):
    """Display search results in a formatted table."""
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return
    
    # Create a table for results
    table = Table(title=f"Search Results for: {query}", show_lines=True)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Title", style="green", width=40)
    table.add_column("URL", style="blue", width=50)
    table.add_column("Snippet", style="white", width=60)
    
    for idx, result in enumerate(results, 1):
        table.add_row(
            str(idx),
            result['title'][:40] + "..." if len(result['title']) > 40 else result['title'],
            result['url'][:50] + "..." if len(result['url']) > 50 else result['url'],
            result['snippet'][:60] + "..." if len(result['snippet']) > 60 else result['snippet']
        )
    
    console.print(table)
    
    # Also print as a list for easier copying
    console.print("\n[bold]Full Results:[/bold]")
    for idx, result in enumerate(results, 1):
        panel = Panel(
            f"[green]{result['title']}[/green]\n"
            f"[blue]{result['url']}[/blue]\n"
            f"[white]{result['snippet']}[/white]",
            title=f"Result {idx}",
            expand=False
        )
        console.print(panel)


async def perform_web_search(query: str, limit: int = 10, engine: str = "google", headless: bool = True):
    """Perform a web search using Playwright and headless Chrome."""
    async with WebSearcher(headless=headless) as searcher:
        console.print(f"[blue]Searching {engine.capitalize()} for:[/blue] {query}")
        
        with console.status(f"[bold green]Searching..."):
            if engine.lower() == "google":
                results = await searcher.search_google(query, limit)
            elif engine.lower() == "duckduckgo":
                results = await searcher.search_duckduckgo(query, limit)
            elif engine.lower() == "hackernews" or engine.lower() == "hn":
                results = await searcher.search_hackernews(query, limit)
            else:
                console.print(f"[red]Unknown search engine: {engine}[/red]")
                console.print("[yellow]Available engines: google, duckduckgo, hackernews[/yellow]")
                return
        
        display_results(results, query)