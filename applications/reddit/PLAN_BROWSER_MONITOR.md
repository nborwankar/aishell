# Reddit Preference Learning Agent

An agent that monitors your manual Reddit browsing in Chrome to learn preferences and interests, then uses that knowledge to curate content, suggest subreddits, and provide personalized summaries.

## Architecture Overview

```
applications/reddit/
├── monitor/                    # Browser monitoring
│   ├── __init__.py
│   ├── chrome_connector.py     # Connect to Chrome via CDP
│   ├── activity_tracker.py     # Track Reddit activity
│   ├── event_processor.py      # Process browsing events
│   └── chrome_extension/       # Optional: dedicated extension
│       ├── manifest.json
│       ├── background.js
│       └── content.js
├── preferences/                # Preference learning
│   ├── __init__.py
│   ├── models.py              # Interest/preference data models
│   ├── analyzer.py            # LLM-based preference analysis
│   ├── interest_graph.py      # Build interest relationships
│   └── storage.py             # SQLite storage for preferences
├── agent/                      # Claude Agent SDK integration
│   ├── __init__.py
│   ├── preference_agent.py    # Main agent orchestrator
│   ├── tools.py               # Agent tools for Reddit
│   └── prompts.py             # System prompts
└── curator/                    # Content curation
    ├── __init__.py
    ├── recommender.py         # Recommend content based on prefs
    ├── summarizer.py          # Summarize preferred topics
    └── digest.py              # Generate daily/weekly digests
```

---

## Approach 1: Chrome DevTools Protocol (CDP)

Connect to your running Chrome instance via the Chrome DevTools Protocol. This is the most seamless approach - no extension needed.

### Setup

Start Chrome with remote debugging enabled:

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/chrome-debug

# Or add to your Chrome shortcut/alias
alias chrome-debug='open -a "Google Chrome" --args --remote-debugging-port=9222'
```

### Implementation

```python
# chrome_connector.py
import asyncio
import json
import websockets
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

@dataclass
class BrowsingEvent:
    """A single browsing event."""
    event_type: str  # "page_visit", "scroll", "click", "time_spent"
    url: str
    timestamp: float
    data: dict  # Additional event-specific data

class ChromeConnector:
    """Connect to Chrome via DevTools Protocol."""

    def __init__(self, debug_port: int = 9222):
        self.debug_port = debug_port
        self.ws = None
        self.event_handlers: list[Callable] = []
        self._message_id = 0

    async def connect(self):
        """Connect to Chrome's DevTools WebSocket."""
        import aiohttp

        # Get list of debuggable pages
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://localhost:{self.debug_port}/json") as resp:
                pages = await resp.json()

        # Find Reddit tabs
        reddit_pages = [p for p in pages if "reddit.com" in p.get("url", "")]

        if not reddit_pages:
            raise ConnectionError("No Reddit tabs found in Chrome")

        # Connect to the first Reddit tab
        ws_url = reddit_pages[0]["webSocketDebuggerUrl"]
        self.ws = await websockets.connect(ws_url)

        # Enable necessary domains
        await self._send("Page.enable")
        await self._send("Network.enable")
        await self._send("DOM.enable")

        return self

    async def _send(self, method: str, params: dict = None) -> dict:
        """Send a CDP command."""
        self._message_id += 1
        message = {
            "id": self._message_id,
            "method": method,
            "params": params or {}
        }
        await self.ws.send(json.dumps(message))

        # Wait for response
        while True:
            response = json.loads(await self.ws.recv())
            if response.get("id") == self._message_id:
                return response
            elif "method" in response:
                # This is an event, process it
                await self._handle_event(response)

    async def _handle_event(self, event: dict):
        """Handle CDP events."""
        method = event.get("method", "")
        params = event.get("params", {})

        # Convert to BrowsingEvent
        browsing_event = None

        if method == "Page.frameNavigated":
            url = params.get("frame", {}).get("url", "")
            if "reddit.com" in url:
                browsing_event = BrowsingEvent(
                    event_type="page_visit",
                    url=url,
                    timestamp=asyncio.get_event_loop().time(),
                    data={"frame_id": params.get("frame", {}).get("id")}
                )

        if browsing_event:
            for handler in self.event_handlers:
                await handler(browsing_event)

    def on_event(self, handler: Callable):
        """Register an event handler."""
        self.event_handlers.append(handler)

    async def get_current_page_content(self) -> str:
        """Get the current page's HTML content."""
        result = await self._send("DOM.getDocument")
        root_node_id = result["result"]["root"]["nodeId"]

        html_result = await self._send("DOM.getOuterHTML", {
            "nodeId": root_node_id
        })
        return html_result["result"]["outerHTML"]

    async def monitor(self):
        """Start monitoring browsing activity."""
        print("Monitoring Reddit browsing... Press Ctrl+C to stop")
        try:
            while True:
                message = await self.ws.recv()
                event = json.loads(message)
                if "method" in event:
                    await self._handle_event(event)
        except websockets.exceptions.ConnectionClosed:
            print("Chrome connection closed")
```

### Activity Tracker

```python
# activity_tracker.py
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta

@dataclass
class SubredditVisit:
    """Track a subreddit visit."""
    subreddit: str
    visit_count: int = 0
    total_time_seconds: float = 0
    last_visit: Optional[datetime] = None
    posts_viewed: List[str] = field(default_factory=list)

@dataclass
class PostInteraction:
    """Track interaction with a post."""
    post_id: str
    subreddit: str
    title: str
    time_spent_seconds: float
    scroll_depth: float  # 0.0 to 1.0
    clicked_comments: bool = False
    upvoted: bool = False  # Detected via DOM changes
    timestamp: datetime = field(default_factory=datetime.now)

class ActivityTracker:
    """Track Reddit browsing activity."""

    def __init__(self):
        self.subreddit_visits: Dict[str, SubredditVisit] = {}
        self.post_interactions: List[PostInteraction] = []
        self.current_url: Optional[str] = None
        self.current_start_time: Optional[float] = None

    def parse_reddit_url(self, url: str) -> dict:
        """Parse Reddit URL to extract components."""
        from urllib.parse import urlparse
        import re

        parsed = urlparse(url)
        path = parsed.path

        result = {
            "type": "unknown",
            "subreddit": None,
            "post_id": None,
            "sort": None
        }

        # Subreddit patterns
        subreddit_match = re.match(r"/r/([^/]+)/?", path)
        if subreddit_match:
            result["subreddit"] = subreddit_match.group(1)
            result["type"] = "subreddit"

        # Post patterns
        post_match = re.match(r"/r/([^/]+)/comments/([^/]+)", path)
        if post_match:
            result["subreddit"] = post_match.group(1)
            result["post_id"] = post_match.group(2)
            result["type"] = "post"

        # User profile
        user_match = re.match(r"/user/([^/]+)", path)
        if user_match:
            result["type"] = "user"
            result["username"] = user_match.group(1)

        # Search
        if "/search" in path:
            result["type"] = "search"

        return result

    async def handle_event(self, event: 'BrowsingEvent'):
        """Process a browsing event."""
        if event.event_type == "page_visit":
            # End tracking for previous page
            if self.current_url and self.current_start_time:
                time_spent = time.time() - self.current_start_time
                await self._record_time_spent(self.current_url, time_spent)

            # Start tracking new page
            self.current_url = event.url
            self.current_start_time = time.time()

            # Record visit
            parsed = self.parse_reddit_url(event.url)
            if parsed["subreddit"]:
                self._record_subreddit_visit(parsed["subreddit"])

    def _record_subreddit_visit(self, subreddit: str):
        """Record a subreddit visit."""
        if subreddit not in self.subreddit_visits:
            self.subreddit_visits[subreddit] = SubredditVisit(subreddit=subreddit)

        visit = self.subreddit_visits[subreddit]
        visit.visit_count += 1
        visit.last_visit = datetime.now()

    async def _record_time_spent(self, url: str, seconds: float):
        """Record time spent on a page."""
        parsed = self.parse_reddit_url(url)

        if parsed["subreddit"]:
            if parsed["subreddit"] in self.subreddit_visits:
                self.subreddit_visits[parsed["subreddit"]].total_time_seconds += seconds

        if parsed["post_id"]:
            self.post_interactions.append(PostInteraction(
                post_id=parsed["post_id"],
                subreddit=parsed["subreddit"] or "unknown",
                title="",  # Would need to extract from page
                time_spent_seconds=seconds,
                scroll_depth=0.0,  # Would need scroll tracking
                timestamp=datetime.now()
            ))

    def get_top_subreddits(self, n: int = 10) -> List[SubredditVisit]:
        """Get most visited subreddits."""
        return sorted(
            self.subreddit_visits.values(),
            key=lambda x: x.total_time_seconds,
            reverse=True
        )[:n]

    def get_engagement_stats(self) -> dict:
        """Get overall engagement statistics."""
        return {
            "total_subreddits": len(self.subreddit_visits),
            "total_posts_viewed": len(self.post_interactions),
            "total_time_hours": sum(
                v.total_time_seconds for v in self.subreddit_visits.values()
            ) / 3600,
            "avg_post_time_seconds": (
                sum(p.time_spent_seconds for p in self.post_interactions) /
                len(self.post_interactions)
                if self.post_interactions else 0
            )
        }
```

---

## Approach 2: Chrome Extension

A dedicated extension provides more control and works without special Chrome launch flags.

### Extension Manifest

```json
// chrome_extension/manifest.json
{
  "manifest_version": 3,
  "name": "AIShell Reddit Monitor",
  "version": "1.0",
  "description": "Monitor Reddit browsing for preference learning",
  "permissions": [
    "activeTab",
    "storage",
    "tabs"
  ],
  "host_permissions": [
    "*://*.reddit.com/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["*://*.reddit.com/*"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ]
}
```

### Content Script

```javascript
// chrome_extension/content.js
(function() {
  const AISHELL_ENDPOINT = "http://localhost:8765/reddit/event";

  // Track page metadata
  function getPageData() {
    const data = {
      url: window.location.href,
      timestamp: Date.now(),
      type: "unknown"
    };

    // Detect page type
    const path = window.location.pathname;

    if (path.match(/^\/r\/([^\/]+)\/?$/)) {
      data.type = "subreddit";
      data.subreddit = path.match(/^\/r\/([^\/]+)/)[1];
    } else if (path.match(/^\/r\/([^\/]+)\/comments\/([^\/]+)/)) {
      data.type = "post";
      data.subreddit = path.match(/^\/r\/([^\/]+)/)[1];
      data.postId = path.match(/\/comments\/([^\/]+)/)[1];

      // Extract post title
      const titleEl = document.querySelector('[data-testid="post-title"]') ||
                      document.querySelector('h1');
      if (titleEl) data.title = titleEl.textContent.trim();
    } else if (path.startsWith("/search")) {
      data.type = "search";
      data.query = new URLSearchParams(window.location.search).get("q");
    }

    return data;
  }

  // Track scroll depth
  let maxScrollDepth = 0;
  window.addEventListener("scroll", () => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const scrollPercent = docHeight > 0 ? scrollTop / docHeight : 0;
    maxScrollDepth = Math.max(maxScrollDepth, scrollPercent);
  });

  // Track upvotes (detect clicks on vote buttons)
  document.addEventListener("click", (e) => {
    const target = e.target.closest('[data-click-id="upvote"], [data-click-id="downvote"]');
    if (target) {
      sendEvent({
        type: "vote",
        voteType: target.dataset.clickId,
        ...getPageData()
      });
    }
  });

  // Send event to aishell
  async function sendEvent(event) {
    try {
      await fetch(AISHELL_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event)
      });
    } catch (e) {
      // Store locally if aishell not running
      const stored = JSON.parse(localStorage.getItem("aishell_events") || "[]");
      stored.push(event);
      localStorage.setItem("aishell_events", JSON.stringify(stored.slice(-1000)));
    }
  }

  // Track page visit
  const pageData = getPageData();
  sendEvent({ type: "page_visit", ...pageData });

  // Track time spent on page
  const startTime = Date.now();
  window.addEventListener("beforeunload", () => {
    sendEvent({
      type: "page_leave",
      timeSpentMs: Date.now() - startTime,
      scrollDepth: maxScrollDepth,
      ...pageData
    });
  });

  // Periodic heartbeat
  setInterval(() => {
    sendEvent({
      type: "heartbeat",
      timeSpentMs: Date.now() - startTime,
      scrollDepth: maxScrollDepth,
      ...pageData
    });
  }, 30000);  // Every 30 seconds
})();
```

### Event Receiver Server

```python
# monitor/event_server.py
from aiohttp import web
import asyncio
from typing import Callable, List

class EventServer:
    """HTTP server to receive events from Chrome extension."""

    def __init__(self, port: int = 8765):
        self.port = port
        self.handlers: List[Callable] = []
        self.app = web.Application()
        self.app.router.add_post("/reddit/event", self.handle_event)

    async def handle_event(self, request: web.Request) -> web.Response:
        """Handle incoming event from extension."""
        try:
            event_data = await request.json()

            # Process with all handlers
            for handler in self.handlers:
                await handler(event_data)

            return web.json_response({"status": "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    def on_event(self, handler: Callable):
        """Register event handler."""
        self.handlers.append(handler)

    async def start(self):
        """Start the event server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", self.port)
        await site.start()
        print(f"Event server listening on http://localhost:{self.port}")
```

---

## Preference Learning with LLM

### Preference Analyzer

```python
# preferences/analyzer.py
from dataclasses import dataclass
from typing import List, Dict, Optional
import json

@dataclass
class Interest:
    """A detected interest/preference."""
    topic: str
    confidence: float  # 0.0 to 1.0
    evidence: List[str]  # Subreddits, posts that suggest this interest
    related_topics: List[str]

@dataclass
class UserProfile:
    """Aggregated user preferences."""
    interests: List[Interest]
    favorite_subreddits: List[str]
    posting_times: Dict[str, float]  # Hour -> activity level
    content_preferences: Dict[str, float]  # "text", "image", "video", "link"
    engagement_style: str  # "lurker", "commenter", "poster"

class PreferenceAnalyzer:
    """Analyze browsing activity to learn preferences using LLM."""

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    async def analyze_activity(
        self,
        subreddit_visits: List['SubredditVisit'],
        post_interactions: List['PostInteraction'],
        time_window_days: int = 30
    ) -> UserProfile:
        """Analyze activity to build user profile."""

        # Prepare activity summary for LLM
        activity_summary = self._prepare_summary(
            subreddit_visits,
            post_interactions
        )

        prompt = f"""Analyze this Reddit browsing activity and identify the user's interests and preferences.

## Activity Summary
{activity_summary}

## Instructions
Based on this browsing data, provide a JSON analysis with:
1. "interests": List of topics the user is interested in, with confidence scores (0-1) and evidence
2. "content_preferences": What types of content they prefer (text posts, images, videos, links)
3. "engagement_style": Are they a lurker, casual browser, active commenter, or content creator?
4. "time_patterns": When are they most active?
5. "recommended_subreddits": 5 subreddits they might enjoy but haven't visited

Return ONLY valid JSON."""

        response = await self.llm_provider.query(prompt, temperature=0.3)

        # Parse LLM response
        try:
            analysis = json.loads(response.content)
            return self._build_profile(analysis)
        except json.JSONDecodeError:
            # Fallback to rule-based analysis
            return self._rule_based_analysis(subreddit_visits, post_interactions)

    def _prepare_summary(
        self,
        subreddit_visits: List['SubredditVisit'],
        post_interactions: List['PostInteraction']
    ) -> str:
        """Prepare activity summary for LLM analysis."""
        lines = ["### Subreddit Visits (sorted by time spent)"]

        sorted_visits = sorted(
            subreddit_visits,
            key=lambda x: x.total_time_seconds,
            reverse=True
        )[:20]  # Top 20

        for visit in sorted_visits:
            lines.append(
                f"- r/{visit.subreddit}: {visit.visit_count} visits, "
                f"{visit.total_time_seconds/60:.1f} minutes total"
            )

        lines.append("\n### Recent Post Interactions")
        for post in post_interactions[-50:]:  # Last 50
            lines.append(
                f"- [{post.subreddit}] {post.title[:50]}... "
                f"({post.time_spent_seconds:.0f}s, scroll: {post.scroll_depth:.0%})"
            )

        return "\n".join(lines)

    def _build_profile(self, analysis: dict) -> UserProfile:
        """Build UserProfile from LLM analysis."""
        interests = [
            Interest(
                topic=i["topic"],
                confidence=i.get("confidence", 0.5),
                evidence=i.get("evidence", []),
                related_topics=i.get("related_topics", [])
            )
            for i in analysis.get("interests", [])
        ]

        return UserProfile(
            interests=interests,
            favorite_subreddits=analysis.get("favorite_subreddits", []),
            posting_times=analysis.get("time_patterns", {}),
            content_preferences=analysis.get("content_preferences", {}),
            engagement_style=analysis.get("engagement_style", "unknown")
        )

    async def get_interest_explanation(self, interest: Interest) -> str:
        """Get a human-readable explanation of why an interest was detected."""
        prompt = f"""Explain why the following interest was detected based on Reddit browsing:

Interest: {interest.topic}
Confidence: {interest.confidence:.0%}
Evidence (subreddits/posts): {', '.join(interest.evidence[:10])}

Write 2-3 sentences explaining this interest detection."""

        response = await self.llm_provider.query(prompt, temperature=0.5)
        return response.content
```

---

## Claude Agent SDK Integration

### Preference Agent

```python
# agent/preference_agent.py
from anthropic import Anthropic

class RedditPreferenceAgent:
    """
    Claude Agent SDK-based agent for Reddit preference learning.

    Uses the agentic loop pattern to:
    1. Monitor browsing activity
    2. Analyze preferences
    3. Provide recommendations
    4. Answer questions about interests
    """

    def __init__(self, anthropic_client: Anthropic = None):
        self.client = anthropic_client or Anthropic()
        self.activity_tracker = ActivityTracker()
        self.preference_storage = PreferenceStorage()
        self.tools = self._define_tools()

    def _define_tools(self) -> list:
        """Define tools available to the agent."""
        return [
            {
                "name": "get_browsing_stats",
                "description": "Get statistics about Reddit browsing activity",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "time_range": {
                            "type": "string",
                            "enum": ["today", "week", "month", "all"],
                            "description": "Time range for statistics"
                        }
                    },
                    "required": ["time_range"]
                }
            },
            {
                "name": "get_top_subreddits",
                "description": "Get most visited subreddits",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 10},
                        "sort_by": {
                            "type": "string",
                            "enum": ["time_spent", "visit_count", "recent"],
                            "default": "time_spent"
                        }
                    }
                }
            },
            {
                "name": "analyze_interests",
                "description": "Analyze browsing to identify interests",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "depth": {
                            "type": "string",
                            "enum": ["quick", "detailed"],
                            "default": "quick"
                        }
                    }
                }
            },
            {
                "name": "find_new_subreddits",
                "description": "Recommend new subreddits based on interests",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "default": 5},
                        "based_on": {
                            "type": "string",
                            "description": "Specific interest to base recommendations on"
                        }
                    }
                }
            },
            {
                "name": "browse_reddit",
                "description": "Browse Reddit and fetch posts (uses Playwright/PRAW)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "subreddit": {"type": "string"},
                        "sort": {
                            "type": "string",
                            "enum": ["hot", "new", "top", "rising"]
                        },
                        "limit": {"type": "integer", "default": 10}
                    },
                    "required": ["subreddit"]
                }
            },
            {
                "name": "search_reddit",
                "description": "Search Reddit for posts matching interests",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "subreddit": {"type": "string"},
                        "time_filter": {
                            "type": "string",
                            "enum": ["hour", "day", "week", "month", "year", "all"]
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    async def process_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Process a tool call from the agent."""
        if tool_name == "get_browsing_stats":
            stats = self.activity_tracker.get_engagement_stats()
            return json.dumps(stats, indent=2)

        elif tool_name == "get_top_subreddits":
            subreddits = self.activity_tracker.get_top_subreddits(
                n=tool_input.get("limit", 10)
            )
            return json.dumps([
                {"name": s.subreddit, "time_minutes": s.total_time_seconds/60, "visits": s.visit_count}
                for s in subreddits
            ], indent=2)

        elif tool_name == "analyze_interests":
            analyzer = PreferenceAnalyzer(self.llm_provider)
            profile = await analyzer.analyze_activity(
                list(self.activity_tracker.subreddit_visits.values()),
                self.activity_tracker.post_interactions
            )
            return json.dumps({
                "interests": [{"topic": i.topic, "confidence": i.confidence} for i in profile.interests],
                "engagement_style": profile.engagement_style
            }, indent=2)

        elif tool_name == "browse_reddit":
            # Use Playwright or PRAW navigator
            posts = await self.reddit_navigator.browse_subreddit(
                tool_input["subreddit"],
                sort=tool_input.get("sort", "hot"),
                limit=tool_input.get("limit", 10)
            )
            return json.dumps([p.to_dict() for p in posts], indent=2)

        # ... more tool implementations

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    async def chat(self, user_message: str) -> str:
        """
        Chat with the preference agent using agentic loop.

        The agent can:
        - Answer questions about your Reddit habits
        - Analyze your interests
        - Recommend new content
        - Browse Reddit on your behalf
        """
        messages = [{"role": "user", "content": user_message}]

        system_prompt = """You are a helpful Reddit preference learning assistant.
You have access to the user's Reddit browsing history and can:
1. Analyze their interests based on browsing patterns
2. Recommend new subreddits and content
3. Browse Reddit to find relevant posts
4. Answer questions about their Reddit habits

Be conversational and insightful. When making recommendations, explain WHY
you think they'd enjoy something based on their browsing history."""

        # Agentic loop
        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=self.tools,
                messages=messages
            )

            # Check if we need to process tool calls
            if response.stop_reason == "tool_use":
                # Extract tool uses
                tool_uses = [
                    block for block in response.content
                    if block.type == "tool_use"
                ]

                # Add assistant response to messages
                messages.append({"role": "assistant", "content": response.content})

                # Process each tool call
                tool_results = []
                for tool_use in tool_uses:
                    result = await self.process_tool_call(
                        tool_use.name,
                        tool_use.input
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result
                    })

                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})

            else:
                # No more tool calls, return final response
                return "".join(
                    block.text for block in response.content
                    if hasattr(block, "text")
                )
```

---

## CLI Integration

```python
# cli.py additions

@reddit.command()
@click.option("--port", default=9222, help="Chrome debug port")
@click.option("--extension", is_flag=True, help="Use extension mode instead of CDP")
def monitor(port, extension):
    """Start monitoring Reddit browsing activity."""
    async def run():
        if extension:
            # Start event server for extension
            server = EventServer(port=8765)
            tracker = ActivityTracker()
            server.on_event(tracker.handle_event)
            await server.start()
            console.print("[green]Extension event server started[/green]")
            console.print("Install the Chrome extension and browse Reddit")
        else:
            # Connect via CDP
            connector = ChromeConnector(debug_port=port)
            tracker = ActivityTracker()
            connector.on_event(tracker.handle_event)

            try:
                await connector.connect()
                console.print("[green]Connected to Chrome[/green]")
                await connector.monitor()
            except ConnectionError as e:
                console.print(f"[red]Error:[/red] {e}")
                console.print("Start Chrome with: --remote-debugging-port=9222")

    asyncio.run(run())

@reddit.command()
@click.option("--detailed", is_flag=True, help="Show detailed interest analysis")
def interests(detailed):
    """Show learned interests from browsing activity."""
    async def run():
        storage = PreferenceStorage()
        profile = storage.load_profile()

        if not profile:
            console.print("[yellow]No browsing data yet. Run 'aishell reddit monitor' first.[/yellow]")
            return

        console.print("[blue]Your Reddit Interests[/blue]\n")

        for interest in profile.interests[:10]:
            bar = "█" * int(interest.confidence * 20)
            console.print(f"  {interest.topic}: {bar} {interest.confidence:.0%}")

            if detailed:
                console.print(f"    Evidence: {', '.join(interest.evidence[:3])}")

    asyncio.run(run())

@reddit.command()
@click.argument("message", nargs=-1)
@click.option("--provider", "-p", default="claude")
def agent(message, provider):
    """Chat with the Reddit preference agent."""
    async def run():
        agent = RedditPreferenceAgent()
        user_message = " ".join(message) if message else "What are my main interests?"

        console.print(f"[blue]You:[/blue] {user_message}\n")

        with console.status("[yellow]Thinking...[/yellow]"):
            response = await agent.chat(user_message)

        console.print(f"[green]Agent:[/green] {response}")

    asyncio.run(run())
```

---

## Usage Examples

```bash
# Start monitoring (CDP mode)
chrome --remote-debugging-port=9222 &
aishell reddit monitor --port 9222

# Start monitoring (extension mode)
aishell reddit monitor --extension
# Then install extension in Chrome

# View learned interests
aishell reddit interests --detailed

# Chat with preference agent
aishell reddit agent "What topics am I most interested in?"
aishell reddit agent "Find me some new subreddits about machine learning"
aishell reddit agent "Show me trending posts in my favorite subreddits"
aishell reddit agent "What time of day am I most active on Reddit?"

# Generate personalized digest
aishell reddit digest --format email --interests "python,AI"
```

---

## Privacy Considerations

1. **Local-first**: All data stored locally in SQLite
2. **Opt-in**: Monitoring requires explicit user action
3. **Transparent**: User can view all collected data
4. **Deletable**: Easy commands to clear history
5. **No external sharing**: Data never leaves your machine (except to LLM API for analysis)

```bash
# View collected data
aishell reddit data --show

# Export data
aishell reddit data --export data.json

# Clear all data
aishell reddit data --clear
```

---

## Development Timeline

### Week 1: Browser Integration
- [ ] Chrome DevTools Protocol connector
- [ ] Chrome extension skeleton
- [ ] Activity tracker data models

### Week 2: Data Collection
- [ ] Event processing pipeline
- [ ] SQLite storage for activity data
- [ ] Real-time monitoring CLI

### Week 3: Preference Learning
- [ ] LLM-based interest analysis
- [ ] Interest graph building
- [ ] Profile storage and updates

### Week 4: Agent Integration
- [ ] Claude Agent SDK integration
- [ ] Tool definitions and handlers
- [ ] Conversational interface

### Week 5: Polish
- [ ] Digest generation
- [ ] Recommendation engine
- [ ] Privacy controls
- [ ] Documentation
