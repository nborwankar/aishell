# Web Scraping with LLM-Assisted Navigation

This module provides intelligent web scraping capabilities for AIShell using Playwright and LLM-assisted navigation.

## Features

- **LLM-Assisted Navigation**: Translate natural language tasks into browser actions
- **JavaScript Menu Support**: Handle hover menus, dropdowns, and AJAX-loaded content
- **Reusable Configurations**: Save successful navigation patterns as YAML files
- **Two-Phase Strategy**: Discovery with Opus, execution with Haiku (90% cost savings)
- **Fallback Mechanism**: Automatic fallback to more powerful model if needed
- **Rich Data Extraction**: Extract text, HTML, attributes, tables, and links
- **Screenshot Capabilities**: Capture page screenshots during navigation

## 🌍 Works with ANY Website - Not Just ICICI Bank!

**Important**: This is a **completely generic web scraping framework** that works with any public website. The code is **NOT hard-coded** for ICICI Bank.

### What's Generic (100% Reusable):
- ✅ All core modules (`actions.py`, `navigator.py`, `llm_navigator.py`, etc.)
- ✅ CLI command (`aishell navigate`)
- ✅ LLM task translation system
- ✅ Configuration file format
- ✅ Data extraction engine

**Zero ICICI-specific code in any module.**

### What's ICICI-Specific (Just Examples):
- 📄 Example YAML configurations in `examples/` directory
- 📄 These are just **templates** to show the format

### Use It On Any Website Immediately:

```bash
# E-commerce
aishell navigate https://amazon.com/s?k=laptops \
  --task "Extract product names, prices, and ratings" \
  --provider opus

# News/Social
aishell navigate https://news.ycombinator.com \
  --task "Get top 30 story titles and URLs" \
  --provider haiku

# Real Estate
aishell navigate https://zillow.com \
  --task "Find houses under $500k with prices and addresses" \
  --provider opus

# Job Boards
aishell navigate https://indeed.com/jobs?q=python \
  --task "Extract job titles, companies, locations, and salaries" \
  --provider haiku

# Any Banking Site
aishell navigate https://chase.com \
  --task "Extract mortgage rates and terms" \
  --provider opus

# Government Data
aishell navigate https://data.gov \
  --task "Find datasets about climate with download links" \
  --provider haiku

# Documentation Sites
aishell navigate https://docs.python.org \
  --task "Extract all function signatures from this page" \
  --provider haiku
```

**The LLM figures out the navigation for you - no coding required!**

### Why ICICI Bank Examples?

The `examples/` directory contains ICICI Bank configurations to:
1. **Demonstrate the YAML format** - Show what a complete configuration looks like
2. **Provide templates** - Copy and modify for your own websites
3. **Illustrate complex scenarios** - JavaScript menus, AJAX content, multi-step navigation
4. **Show real-world use case** - Building a RAG system for banking Q&A

**You can scrape literally any public website without changing a line of code.**

## Quick Start

### 1. Install Dependencies

Playwright is already part of aishell dependencies. If needed:

```bash
python -m playwright install
```

### 2. Discovery Phase (One-time with Opus)

Use Claude Opus to discover website structure and generate configurations:

```bash
aishell navigate https://www.icici.bank.in \
  --task "Navigate to home loans section and extract all product details" \
  --provider opus \
  --save-config icici_home_loans.yaml
```

### 3. Execution Phase (Weekly with Haiku)

Run saved configuration with Haiku for cost-effective weekly scraping:

```bash
aishell navigate --config icici_home_loans.yaml \
  --provider haiku \
  --fallback opus \
  --output home_loans.json
```

## Three Navigation Modes

### Mode 1: Free-Form Task (LLM translates to actions)

```bash
aishell navigate https://example.com \
  --task "Find all product prices and descriptions" \
  --provider opus
```

**How it works:**
- LLM analyzes the task and website structure
- Generates appropriate action sequence
- Executes actions and extracts data
- No hard-coding required!

### Mode 2: Configuration-Based (Reusable patterns)

```bash
aishell navigate --config product_extraction.yaml \
  --provider haiku \
  --output products.json
```

**How it works:**
- Loads pre-defined action sequence from YAML
- Executes actions exactly as configured
- Fast and cost-effective for repeated scraping

### Mode 3: Task Variations with Fallback

```bash
aishell navigate https://example.com \
  --task "Extract quarterly financial results" \
  --provider haiku \
  --fallback opus
```

**How it works:**
- Haiku attempts to translate and execute task
- If it fails, automatically falls back to Opus
- Learns from failures and improves over time

## Architecture

```
usecases/webscraping/
├── __init__.py           # Package initialization
├── actions.py            # Action type definitions
├── navigator.py          # Playwright navigation engine
├── llm_navigator.py      # LLM integration for task translation
├── extractors.py         # Data extraction utilities
├── config.py             # Configuration file management
├── examples/             # Example configurations
│   ├── icici_home_loans.yaml
│   ├── icici_credit_cards.yaml
│   ├── icici_savings_accounts.yaml
│   ├── icici_branch_locator.yaml
│   └── icici_fixed_deposits.yaml
└── README.md             # This file
```

## Action Types

The following action types are supported:

### Navigation Actions
- **navigate**: Navigate to URL
- **click**: Click on element
- **hover**: Hover over element (for dropdown menus)
- **wait**: Wait for element or duration

### Data Actions
- **extract**: Extract structured data from page
- **screenshot**: Take page screenshot
- **js**: Execute custom JavaScript

### Input Actions
- **type**: Type text into input field
- **select**: Select dropdown option
- **scroll**: Scroll page or element

## Configuration File Format

```yaml
name: "Task Description"
url: "https://example.com"
actions:
  - type: hover
    selector: ".menu-item"
    timeout: 30000

  - type: wait
    selector: ".dropdown-menu"
    state: "visible"

  - type: click
    selector: "a:has-text('Products')"

  - type: extract
    selectors:
      product_name: ".product-title"
      price: ".product-price"
    extract_type: "text"
    multiple: true

output:
  format: "json"
  file: "products.json"

llm_provider: "ClaudeProvider"
fallback_provider: "ClaudeProvider"
```

## Cost Optimization Strategy

### Two-Phase Approach for RAG Systems

**Phase 1: Discovery (One-time, $20-40)**
- Use Claude Opus to explore site structure
- Generate 10-15 configuration files
- Test and validate extraction patterns
- One-time cost: ~$2-4 per page

**Phase 2: Weekly Execution ($0.50-2/week)**
- Run saved configs with Claude Haiku
- 90% cost reduction vs. using Opus
- Automatic fallback to Opus if site changes
- Weekly cost: ~$0.05-0.20 per page

**Total Cost:**
- Initial setup: $30 (one-time)
- Weekly maintenance: $1-2 (15 pages)
- Annual cost: $60-80 (vs. $600-800 with Opus only)

## JavaScript Menu Handling

The scraper handles JavaScript-driven menus using a hover-wait-click pattern:

```yaml
actions:
  # 1. Hover to trigger menu
  - type: hover
    selector: ".nav-item"

  # 2. Wait for menu to appear
  - type: wait
    selector: ".mega-menu.visible"
    state: "visible"
    timeout: 30000

  # 3. Click menu item
  - type: click
    selector: ".menu-link"

  # 4. Wait for AJAX content
  - type: wait
    selector: ".content-loaded"
    state: "visible"
```

This pattern works for:
- Mega menus
- Dropdown menus
- Hover-activated navigation
- AJAX-loaded content

## CLI Command Reference

```bash
# Basic syntax
aishell navigate [URL] [OPTIONS]

# Options
--task, -t              Natural language task description
--config, -c            Path to configuration file
--provider, -p          LLM provider (claude/openai/gemini/ollama/opus/haiku)
--fallback              Fallback provider
--save-config           Save generated config to file
--output, -o            Output file for extracted data
--headless/--no-headless  Run browser in headless mode (default: True)
--browser               Browser type (chromium/firefox/webkit)

# Examples
aishell navigate https://example.com --task "Extract prices"
aishell navigate --config my_config.yaml --output data.json
aishell navigate https://example.com --task "Get products" --provider haiku --fallback opus
```

## Integration with RAG Systems

### Weekly Scraping Script

```bash
#!/bin/bash
# weekly_scrape.sh

CONFIG_DIR="usecases/webscraping/examples"
OUTPUT_DIR="data/icici_bank"

mkdir -p "$OUTPUT_DIR"

for config in "$CONFIG_DIR"/*.yaml; do
    filename=$(basename "$config" .yaml)
    echo "Scraping: $filename"

    aishell navigate --config "$config" \
      --provider haiku \
      --fallback opus \
      --output "$OUTPUT_DIR/${filename}.json"
done

echo "Scraping complete. Updating vector database..."
python update_rag.py "$OUTPUT_DIR"
```

### RAG Integration Script

```python
# update_rag.py
import json
from pathlib import Path
from datetime import datetime

def ingest_scraped_data(data_dir: Path):
    """Ingest scraped data into RAG vector database."""

    documents = []

    for json_file in data_dir.glob("*.json"):
        with open(json_file) as f:
            data = json.load(f)

        # Convert to RAG document format
        doc = {
            "id": f"icici_{json_file.stem}",
            "text": format_for_qa(data),
            "metadata": {
                "source": "ICICI Bank",
                "product": json_file.stem,
                "scraped_at": datetime.now().isoformat(),
                "url": data.get("metadata", {}).get("url")
            }
        }
        documents.append(doc)

    # Ingest into vector database
    vector_db.add_documents(documents)
    print(f"Ingested {len(documents)} documents")

def format_for_qa(data: dict) -> str:
    """Format scraped data for Q&A."""
    # Convert structured data to natural language
    # that works well with RAG retrieval
    ...
```

## Testing

Run tests with actual ICICI Bank website (recommended to start in non-headless mode):

```bash
# Test home loans extraction
aishell navigate --config examples/icici_home_loans.yaml \
  --no-headless \
  --output test_home_loans.json

# Test with task (uses LLM)
aishell navigate https://www.icici.bank.in \
  --task "Find savings account types and their minimum balance requirements" \
  --provider opus \
  --no-headless
```

## Future Enhancements

### Session/Authentication Support (Planned)
For scraping authenticated content:

```yaml
session:
  auth_type: "form"
  login_url: "https://example.com/login"
  credentials:
    username_field: "#username"
    password_field: "#password"
    submit_button: "#login-btn"
  session_indicator: ".user-profile"
```

### Rate Limiting
```yaml
rate_limit:
  requests_per_minute: 10
  delay_between_pages: 2000  # milliseconds
```

### Error Recovery
```yaml
error_handling:
  retry_attempts: 3
  retry_delay: 5000
  fallback_selectors:
    product_name: [".title", ".product-title", "h1"]
```

## Real-World Use Cases Across Industries

This framework is being used to scrape data from diverse websites across many industries:

### E-Commerce & Retail
```bash
# Amazon product research
aishell navigate "https://amazon.com/s?k=headphones" \
  --task "Extract all products with name, price, rating, review count" \
  --provider opus --save-config amazon_headphones.yaml

# Walmart price monitoring
aishell navigate "https://walmart.com/search?q=groceries" \
  --task "Get product prices for weekly price tracking" \
  --provider haiku --fallback opus
```

### News & Media
```bash
# Hacker News daily digest
aishell navigate "https://news.ycombinator.com" \
  --task "Extract top 30 stories with titles, URLs, and scores" \
  --provider haiku

# Reddit trending topics
aishell navigate "https://reddit.com/r/technology" \
  --task "Get hot posts with titles, scores, and comment counts" \
  --provider haiku
```

### Financial Services
```bash
# Stock market data
aishell navigate "https://finance.yahoo.com" \
  --task "Extract S&P 500 current prices and changes" \
  --provider haiku

# Cryptocurrency tracking
aishell navigate "https://coinmarketcap.com" \
  --task "Get top 50 crypto prices and market caps" \
  --provider haiku
```

### Real Estate
```bash
# Zillow property search
aishell navigate "https://zillow.com/homes/San-Francisco_rb/" \
  --task "Find all properties with price, bedrooms, bathrooms, sqft" \
  --provider opus --save-config zillow_sf.yaml

# Weekly price monitoring (cost-effective)
aishell navigate --config zillow_sf.yaml \
  --provider haiku --output sf_properties_weekly.json
```

### Job Boards
```bash
# Indeed job scraping
aishell navigate "https://indeed.com/jobs?q=python+developer" \
  --task "Extract job titles, companies, locations, salaries, descriptions" \
  --provider opus

# LinkedIn job monitoring
aishell navigate "https://linkedin.com/jobs/search?keywords=data+scientist" \
  --task "Get new job postings from last 24 hours" \
  --provider haiku
```

### Government & Research
```bash
# Data.gov datasets
aishell navigate "https://data.gov/climate" \
  --task "Find climate datasets with titles, descriptions, download URLs" \
  --provider haiku

# Research papers
aishell navigate "https://arxiv.org/list/cs.AI/recent" \
  --task "Extract recent AI papers with titles, authors, abstracts" \
  --provider haiku
```

### Travel & Hospitality
```bash
# Airbnb listings
aishell navigate "https://airbnb.com/s/Paris" \
  --task "Extract listings with price, rating, amenities, availability" \
  --provider opus

# Flight price tracking
aishell navigate "https://kayak.com/flights/SFO-JFK" \
  --task "Get all flight options with prices and times" \
  --provider haiku
```

### Documentation & Learning
```bash
# Python documentation
aishell navigate "https://docs.python.org/3/library/index.html" \
  --task "Extract all module names and descriptions" \
  --provider haiku

# Stack Overflow answers
aishell navigate "https://stackoverflow.com/questions/tagged/python" \
  --task "Get top questions with answers and vote counts" \
  --provider haiku
```

### Key Pattern: Discovery Once, Execute Forever

For any industry/website:
1. **Discovery** (One-time with Opus): Explore site, save config
2. **Execution** (Recurring with Haiku): Run saved config regularly

```bash
# Step 1: Discovery (one-time, $2-4)
aishell navigate https://your-target-site.com \
  --task "Your data extraction goal" \
  --provider opus \
  --save-config my_site.yaml

# Step 2: Weekly/Daily execution (ongoing, $0.05-0.20)
aishell navigate --config my_site.yaml \
  --provider haiku \
  --fallback opus \
  --output data_$(date +%Y%m%d).json
```

**Total Cost Example** (monitoring 10 websites weekly):
- Discovery: $30 (one-time)
- Weekly execution: $1-2 per week with Haiku
- Annual: ~$80 vs. $800 with Opus-only

## Best Practices

1. **Start with Discovery**: Always use Opus first to explore new sites
2. **Test Non-Headless**: Debug with `--no-headless` to see what's happening
3. **Save Configs**: Save successful patterns with `--save-config`
4. **Use Fallbacks**: Always specify `--fallback opus` for reliability
5. **Respect Rate Limits**: Don't scrape too aggressively
6. **Update Regularly**: Review and update selectors monthly
7. **Monitor Costs**: Track Haiku usage to ensure cost savings

## Troubleshooting

### Selector Not Found
- Run with `--no-headless` to inspect page
- Check if element is in iframe
- Try alternative selectors (class, id, text)

### Timeout Errors
- Increase timeout in action config
- Add wait action after navigation
- Check if page requires authentication

### AJAX Content Not Loading
- Add explicit wait after interaction
- Use `wait_until: "networkidle"` for navigation
- Consider adding JavaScript action to check load state

### LLM Generating Wrong Actions
- Provide more specific task description
- Use Opus instead of Haiku for complex sites
- Manually create config and test

## Support

For issues and questions:
- Check `SCRAPING_GUIDE.md` for detailed documentation
- Review example configurations in `examples/`
- Test with `--no-headless` flag to debug
- Use `--provider opus` for challenging sites

## License

Part of AIShell project. See main LICENSE file.
