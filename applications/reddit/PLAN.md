# Reddit Client Application Plan

A configurable Reddit client built on aishell's web navigation framework. This application demonstrates a skill-based architecture that can be extended to other services (Twitter, HackerNews, LinkedIn, etc.).

## Architecture Overview

```
applications/
├── reddit/
│   ├── PLAN.md                 # This document
│   ├── __init__.py
│   ├── skills/                 # Reddit-specific skills
│   │   ├── __init__.py
│   │   ├── base_skill.py       # Abstract skill interface
│   │   ├── browse_skill.py     # Browse subreddits, posts
│   │   ├── search_skill.py     # Search Reddit
│   │   ├── interact_skill.py   # Upvote, comment, save (auth required)
│   │   └── extract_skill.py    # Extract data from posts/comments
│   ├── playwright/             # Browser automation approach
│   │   ├── __init__.py
│   │   ├── reddit_navigator.py # Playwright-based navigation
│   │   ├── selectors.py        # CSS selectors for Reddit elements
│   │   └── actions.py          # Reddit-specific actions
│   ├── praw/                   # API approach
│   │   ├── __init__.py
│   │   ├── reddit_api.py       # PRAW wrapper
│   │   └── auth.py             # OAuth handling
│   ├── configs/                # Reusable configurations
│   │   ├── browse_subreddit.yaml
│   │   ├── search_posts.yaml
│   │   └── extract_post_data.yaml
│   └── cli.py                  # CLI commands for Reddit client
├── base/                       # Shared base classes
│   ├── __init__.py
│   ├── service_client.py       # Abstract service client
│   └── skill.py                # Abstract skill interface
└── __init__.py
```

---

# Part 1: Playwright Approach

## Overview

Use Playwright to browse Reddit as a headless browser. This approach:
- Works without API keys for public content
- Supports all Reddit features visible to users
- Can handle JavaScript-rendered content
- Enables screenshot capture and visual extraction

## Implementation Plan

### Phase 1: Core Navigator (Week 1)

#### 1.1 Reddit Selectors
Define CSS selectors for Reddit's DOM structure (both old and new Reddit):

```python
# selectors.py
REDDIT_SELECTORS = {
    # New Reddit (sh-reddit)
    "new": {
        "post_container": "shreddit-post",
        "post_title": "[slot='title']",
        "post_author": "shreddit-post [author]",
        "post_score": "shreddit-post [score]",
        "post_comments_count": "shreddit-post [comment-count]",
        "post_content": "shreddit-post [slot='text-body']",
        "comment_container": "shreddit-comment",
        "comment_author": "shreddit-comment [author]",
        "comment_text": "shreddit-comment [slot='comment']",
        "subreddit_name": "shreddit-subreddit-header [name]",
        "search_input": "search-dynamic-id-cache input",
        "next_page": "shreddit-feed-paginator [slot='next']",
    },
    # Old Reddit (optional fallback)
    "old": {
        "post_container": ".thing.link",
        "post_title": ".title a.title",
        "post_author": ".author",
        "post_score": ".score.unvoted",
        "post_comments_count": ".comments",
        "subreddit_name": ".redditname",
        "search_input": "#search input[name='q']",
    }
}
```

#### 1.2 Reddit Navigator Class

```python
# reddit_navigator.py
class RedditNavigator:
    """Playwright-based Reddit navigation."""

    def __init__(
        self,
        headless: bool = True,
        use_old_reddit: bool = False,
        llm_provider=None
    ):
        self.base_url = "https://old.reddit.com" if use_old_reddit else "https://www.reddit.com"
        self.web_navigator = WebNavigator(headless=headless)
        self.llm_provider = llm_provider
        self.selectors = REDDIT_SELECTORS["old" if use_old_reddit else "new"]

    async def browse_subreddit(
        self,
        subreddit: str,
        sort: str = "hot",
        limit: int = 25
    ) -> List[RedditPost]:
        """Browse a subreddit and extract posts."""
        ...

    async def get_post(self, post_url: str) -> RedditPostDetail:
        """Get full post details including comments."""
        ...

    async def search(
        self,
        query: str,
        subreddit: Optional[str] = None,
        sort: str = "relevance",
        time_filter: str = "all"
    ) -> List[RedditPost]:
        """Search Reddit."""
        ...

    async def get_user_profile(self, username: str) -> RedditUser:
        """Get user profile information."""
        ...
```

#### 1.3 Data Models

```python
# models.py
@dataclass
class RedditPost:
    id: str
    title: str
    author: str
    subreddit: str
    score: int
    num_comments: int
    url: str
    permalink: str
    created_utc: datetime
    is_self: bool
    selftext: Optional[str] = None
    thumbnail: Optional[str] = None

@dataclass
class RedditComment:
    id: str
    author: str
    body: str
    score: int
    created_utc: datetime
    replies: List["RedditComment"] = field(default_factory=list)

@dataclass
class RedditPostDetail(RedditPost):
    comments: List[RedditComment] = field(default_factory=list)
    content_html: Optional[str] = None
```

### Phase 2: Skills System (Week 2)

#### 2.1 Base Skill Interface

```python
# base_skill.py
class RedditSkill(ABC):
    """Abstract base class for Reddit skills."""

    name: str
    description: str

    @abstractmethod
    async def execute(
        self,
        navigator: RedditNavigator,
        **kwargs
    ) -> SkillResult:
        """Execute the skill."""
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, SkillParameter]:
        """Get skill parameters with types and descriptions."""
        pass
```

#### 2.2 Browse Skill

```python
# browse_skill.py
class BrowseSubredditSkill(RedditSkill):
    name = "browse_subreddit"
    description = "Browse posts in a subreddit"

    async def execute(
        self,
        navigator: RedditNavigator,
        subreddit: str,
        sort: str = "hot",
        limit: int = 25,
        extract_content: bool = False
    ) -> SkillResult:
        posts = await navigator.browse_subreddit(
            subreddit=subreddit,
            sort=sort,
            limit=limit
        )

        return SkillResult(
            success=True,
            data={"posts": [p.to_dict() for p in posts]},
            metadata={"subreddit": subreddit, "sort": sort}
        )
```

#### 2.3 Search Skill

```python
# search_skill.py
class SearchRedditSkill(RedditSkill):
    name = "search_reddit"
    description = "Search Reddit for posts"

    async def execute(
        self,
        navigator: RedditNavigator,
        query: str,
        subreddit: Optional[str] = None,
        sort: str = "relevance",
        time: str = "all",
        limit: int = 25
    ) -> SkillResult:
        results = await navigator.search(
            query=query,
            subreddit=subreddit,
            sort=sort,
            time_filter=time
        )

        return SkillResult(
            success=True,
            data={"results": [r.to_dict() for r in results]},
            metadata={"query": query, "count": len(results)}
        )
```

### Phase 3: LLM Integration (Week 3)

#### 3.1 Natural Language Task Processing

```python
# nl_processor.py
class RedditNLProcessor:
    """Process natural language Reddit commands."""

    def __init__(self, llm_provider, skills: Dict[str, RedditSkill]):
        self.llm_provider = llm_provider
        self.skills = skills

    async def process(self, task: str) -> SkillResult:
        """
        Process natural language task.

        Examples:
        - "Show me the top 10 posts from r/python"
        - "Search for 'machine learning' in r/MachineLearning"
        - "Get the most controversial posts from r/news today"
        """
        # Use LLM to map task to skill + parameters
        skill_call = await self._task_to_skill(task)

        # Execute the skill
        skill = self.skills[skill_call.skill_name]
        return await skill.execute(**skill_call.parameters)
```

#### 3.2 LLM-Assisted Content Extraction

For complex pages where selectors may change, use LLM to extract structured data:

```python
async def extract_with_llm(
    self,
    page_html: str,
    extraction_prompt: str
) -> Dict[str, Any]:
    """Use LLM to extract structured data from page HTML."""
    prompt = f"""Extract the following from this Reddit page:
    {extraction_prompt}

    Page HTML:
    {page_html[:10000]}  # Truncate for token limits

    Return JSON with extracted data.
    """

    response = await self.llm_provider.query(prompt)
    return json.loads(response.content)
```

### Phase 4: CLI Integration (Week 4)

#### 4.1 CLI Commands

```python
# cli.py
@click.group(name="reddit")
def reddit():
    """Reddit client commands."""
    pass

@reddit.command()
@click.argument("subreddit")
@click.option("--sort", type=click.Choice(["hot", "new", "top", "rising"]), default="hot")
@click.option("--limit", default=25)
@click.option("--output", "-o", type=click.Path())
def browse(subreddit, sort, limit, output):
    """Browse a subreddit."""
    ...

@reddit.command()
@click.argument("query")
@click.option("--subreddit", "-r")
@click.option("--sort", type=click.Choice(["relevance", "hot", "top", "new", "comments"]))
@click.option("--time", type=click.Choice(["hour", "day", "week", "month", "year", "all"]))
def search(query, subreddit, sort, time):
    """Search Reddit."""
    ...

@reddit.command()
@click.argument("task", nargs=-1)
@click.option("--provider", "-p", type=click.Choice(["claude", "openai", "gemini"]))
def ask(task, provider):
    """Execute natural language Reddit task."""
    ...
```

## Playwright Usage Examples

```bash
# Browse r/python hot posts
aishell reddit browse python --sort hot --limit 10

# Search for machine learning content
aishell reddit search "transformer architecture" -r MachineLearning --time month

# Natural language query
aishell reddit ask "Show me the top Python news this week" -p claude

# Export to JSON
aishell reddit browse programming --output posts.json
```

---

# Part 2: PRAW Approach

## Overview

PRAW (Python Reddit API Wrapper) provides direct API access to Reddit. This approach:
- Faster than browser automation
- Official API with rate limiting built-in
- Access to user-specific features (requires OAuth)
- More reliable data extraction
- Subject to API quotas and Terms of Service

## Implementation Plan

### Phase 1: API Setup (Week 1)

#### 1.1 Reddit Application Registration

Users must register a Reddit application at https://www.reddit.com/prefs/apps:
1. Create "script" type application for personal use
2. Note the `client_id` and `client_secret`
3. Store credentials in `.env` file

#### 1.2 Environment Configuration

```bash
# .env additions
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_username        # Optional: for authenticated features
REDDIT_PASSWORD=your_password        # Optional: for authenticated features
REDDIT_USER_AGENT=aishell:v1.0 (by /u/your_username)
```

#### 1.3 PRAW Client Wrapper

```python
# reddit_api.py
import praw
from praw.models import Submission, Comment, Subreddit

class RedditAPI:
    """PRAW-based Reddit API client."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        # Load from environment if not provided
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self.username = username or os.getenv("REDDIT_USERNAME")
        self.password = password or os.getenv("REDDIT_PASSWORD")
        self.user_agent = user_agent or os.getenv("REDDIT_USER_AGENT", "aishell:v1.0")

        # Initialize PRAW
        if self.username and self.password:
            # Authenticated (script) mode
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                username=self.username,
                password=self.password,
                user_agent=self.user_agent
            )
        else:
            # Read-only mode
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )

    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        try:
            return self.reddit.user.me() is not None
        except Exception:
            return False
```

### Phase 2: Core API Methods (Week 2)

#### 2.1 Subreddit Operations

```python
# reddit_api.py (continued)

def get_subreddit_posts(
    self,
    subreddit: str,
    sort: str = "hot",
    time_filter: str = "all",
    limit: int = 25
) -> List[RedditPost]:
    """Get posts from a subreddit."""
    sub = self.reddit.subreddit(subreddit)

    if sort == "hot":
        submissions = sub.hot(limit=limit)
    elif sort == "new":
        submissions = sub.new(limit=limit)
    elif sort == "top":
        submissions = sub.top(time_filter=time_filter, limit=limit)
    elif sort == "rising":
        submissions = sub.rising(limit=limit)
    elif sort == "controversial":
        submissions = sub.controversial(time_filter=time_filter, limit=limit)
    else:
        raise ValueError(f"Invalid sort: {sort}")

    return [self._submission_to_post(s) for s in submissions]

def _submission_to_post(self, submission: Submission) -> RedditPost:
    """Convert PRAW Submission to RedditPost."""
    return RedditPost(
        id=submission.id,
        title=submission.title,
        author=str(submission.author) if submission.author else "[deleted]",
        subreddit=str(submission.subreddit),
        score=submission.score,
        num_comments=submission.num_comments,
        url=submission.url,
        permalink=f"https://reddit.com{submission.permalink}",
        created_utc=datetime.fromtimestamp(submission.created_utc),
        is_self=submission.is_self,
        selftext=submission.selftext if submission.is_self else None,
        thumbnail=submission.thumbnail if submission.thumbnail not in ["self", "default", "nsfw"] else None
    )
```

#### 2.2 Search Operations

```python
def search(
    self,
    query: str,
    subreddit: Optional[str] = None,
    sort: str = "relevance",
    time_filter: str = "all",
    limit: int = 25
) -> List[RedditPost]:
    """Search Reddit."""
    if subreddit:
        search_results = self.reddit.subreddit(subreddit).search(
            query,
            sort=sort,
            time_filter=time_filter,
            limit=limit
        )
    else:
        search_results = self.reddit.subreddit("all").search(
            query,
            sort=sort,
            time_filter=time_filter,
            limit=limit
        )

    return [self._submission_to_post(s) for s in search_results]
```

#### 2.3 Post Details and Comments

```python
def get_post_detail(
    self,
    post_id: str,
    comment_sort: str = "best",
    comment_limit: int = 100
) -> RedditPostDetail:
    """Get post with comments."""
    submission = self.reddit.submission(id=post_id)
    submission.comment_sort = comment_sort
    submission.comments.replace_more(limit=0)  # Remove "load more" links

    comments = []
    for comment in submission.comments[:comment_limit]:
        comments.append(self._comment_to_model(comment))

    post = self._submission_to_post(submission)
    return RedditPostDetail(
        **post.__dict__,
        comments=comments,
        content_html=submission.selftext_html if submission.is_self else None
    )

def _comment_to_model(self, comment: Comment, depth: int = 0) -> RedditComment:
    """Convert PRAW Comment to RedditComment."""
    replies = []
    if depth < 3 and hasattr(comment, "replies"):
        for reply in comment.replies[:5]:
            if isinstance(reply, Comment):
                replies.append(self._comment_to_model(reply, depth + 1))

    return RedditComment(
        id=comment.id,
        author=str(comment.author) if comment.author else "[deleted]",
        body=comment.body,
        score=comment.score,
        created_utc=datetime.fromtimestamp(comment.created_utc),
        replies=replies
    )
```

### Phase 3: Authenticated Features (Week 3)

#### 3.1 User Actions (requires authentication)

```python
# Voting
def upvote(self, submission_id: str) -> bool:
    """Upvote a post."""
    if not self.is_authenticated:
        raise AuthenticationError("Authentication required for voting")
    submission = self.reddit.submission(id=submission_id)
    submission.upvote()
    return True

def downvote(self, submission_id: str) -> bool:
    """Downvote a post."""
    if not self.is_authenticated:
        raise AuthenticationError("Authentication required for voting")
    submission = self.reddit.submission(id=submission_id)
    submission.downvote()
    return True

# Saving
def save_post(self, submission_id: str) -> bool:
    """Save a post."""
    if not self.is_authenticated:
        raise AuthenticationError("Authentication required for saving")
    submission = self.reddit.submission(id=submission_id)
    submission.save()
    return True

# Commenting
def comment(self, submission_id: str, body: str) -> str:
    """Add a comment to a post. Returns comment ID."""
    if not self.is_authenticated:
        raise AuthenticationError("Authentication required for commenting")
    submission = self.reddit.submission(id=submission_id)
    comment = submission.reply(body)
    return comment.id
```

#### 3.2 User Profile Operations

```python
def get_my_saved(self, limit: int = 100) -> List[RedditPost]:
    """Get saved posts for authenticated user."""
    if not self.is_authenticated:
        raise AuthenticationError("Authentication required")
    saved = self.reddit.user.me().saved(limit=limit)
    return [self._submission_to_post(s) for s in saved if isinstance(s, Submission)]

def get_my_upvoted(self, limit: int = 100) -> List[RedditPost]:
    """Get upvoted posts for authenticated user."""
    if not self.is_authenticated:
        raise AuthenticationError("Authentication required")
    upvoted = self.reddit.user.me().upvoted(limit=limit)
    return [self._submission_to_post(s) for s in upvoted]
```

### Phase 4: PRAW Skills Integration (Week 4)

#### 4.1 API-Based Skills

```python
# praw_skills.py
class PRAWBrowseSkill(RedditSkill):
    """Browse skill using PRAW API."""

    name = "browse_subreddit_api"
    description = "Browse posts using Reddit API (faster, more reliable)"

    def __init__(self, api: RedditAPI):
        self.api = api

    async def execute(
        self,
        subreddit: str,
        sort: str = "hot",
        time_filter: str = "all",
        limit: int = 25
    ) -> SkillResult:
        # PRAW is synchronous, wrap in executor
        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(
            None,
            lambda: self.api.get_subreddit_posts(
                subreddit, sort, time_filter, limit
            )
        )

        return SkillResult(
            success=True,
            data={"posts": [p.to_dict() for p in posts]},
            source="praw_api"
        )
```

## PRAW Usage Examples

```bash
# Browse using API (faster)
aishell reddit browse python --api --sort top --time week

# Search with API
aishell reddit search "async python" --api -r programming

# Authenticated actions (requires credentials)
aishell reddit upvote POST_ID
aishell reddit save POST_ID
aishell reddit comment POST_ID "Great post!"

# Get my saved posts
aishell reddit saved --limit 50
```

---

# Comparison: Playwright vs PRAW

| Feature | Playwright | PRAW |
|---------|------------|------|
| Setup Complexity | Low (no API keys for public) | Medium (need Reddit app) |
| Speed | Slower (browser overhead) | Fast (direct API) |
| Rate Limits | Browser-like | API rate limits |
| Public Content | Yes | Yes |
| Authentication | Cookie-based (complex) | OAuth (simple) |
| Reliability | May break with UI changes | Stable API |
| Screenshots | Yes | No |
| JavaScript Content | Yes | No |
| Voting/Commenting | Difficult | Easy |
| Data Completeness | Visual only | Full API data |

## Recommended Usage

1. **Public Browsing**: Use Playwright for screenshots and visual content
2. **Data Extraction**: Use PRAW for reliable structured data
3. **Authenticated Actions**: Use PRAW exclusively
4. **LLM Integration**: Works with both approaches

---

# Extensible Service Architecture

## Adding New Services

The skill-based architecture can be extended to other services:

```python
# applications/twitter/skills/browse_skill.py
class BrowseTimelineSkill(TwitterSkill):
    ...

# applications/hackernews/skills/browse_skill.py
class BrowseFrontPageSkill(HackerNewsSkill):
    ...

# applications/linkedin/skills/browse_skill.py
class BrowseFeedSkill(LinkedInSkill):
    ...
```

## Unified CLI

```bash
# Service-agnostic commands
aishell browse reddit python --sort hot
aishell browse hackernews --sort top
aishell browse twitter home

# Service-specific commands
aishell reddit search "python async"
aishell hackernews search "LLM"
aishell twitter search "AI news"
```

---

# Development Timeline

## Week 1: Foundation
- [ ] Create directory structure
- [ ] Define data models
- [ ] Implement Reddit selectors (Playwright)
- [ ] Set up PRAW client

## Week 2: Core Features
- [ ] Implement Playwright navigator
- [ ] Implement PRAW API methods
- [ ] Create browse/search skills

## Week 3: Integration
- [ ] LLM natural language processing
- [ ] LLM-assisted extraction
- [ ] Authenticated features (PRAW)

## Week 4: CLI & Polish
- [ ] CLI commands
- [ ] Configuration files
- [ ] Documentation
- [ ] Tests

---

# Dependencies

```toml
# pyproject.toml additions
[project.optional-dependencies]
reddit = [
    "praw>=7.7.0",
    "playwright>=1.40.0",
]
```

Install with:
```bash
pip install -e ".[reddit]"
```
