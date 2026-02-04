"""
Reddit Client Application.

A configurable Reddit client with two implementation approaches:

1. Playwright: Browser automation for visual browsing and screenshots
2. PRAW: Direct API access for fast, reliable data extraction

Example usage:
    from applications.reddit import RedditNavigator, RedditAPI

    # Playwright approach
    async with RedditNavigator() as navigator:
        posts = await navigator.browse_subreddit("python", sort="hot", limit=10)

    # PRAW approach
    api = RedditAPI()
    posts = api.get_subreddit_posts("python", sort="hot", limit=10)
"""

__version__ = "0.1.0"

# These will be implemented in subsequent development
# from .playwright import RedditNavigator
# from .praw import RedditAPI

__all__ = [
    "__version__",
    # "RedditNavigator",
    # "RedditAPI",
]
