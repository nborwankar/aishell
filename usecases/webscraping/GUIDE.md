# AIShell Web Scraping & Navigation Guide

## Overview

AIShell's navigation system combines Playwright browser automation with LLM-powered intelligence to handle complex web scraping tasks, particularly for JavaScript-heavy sites with dynamic menus and AJAX-loaded content.

**Key Innovation**: Instead of writing brittle scraping scripts, you describe what you want in natural language, and the LLM figures out how to navigate the site and extract the data.

## Use Case: Customer Service RAG System

This guide uses ICICI Bank (https://www.icici.bank.in) as an example for building a Q&A RAG system that answers customer questions about:
- Loan products (interest rates, eligibility, tenure)
- Deposit products (FD/RD rates, terms)
- Credit/debit cards (types, rewards, fees)
- Branch/ATM locations
- Fees and charges
- Customer service processes

## Three Navigation Modes

### Mode 1: Free-Form Task (LLM Discovers Navigation)

**What it does**: You write a natural language task, the LLM analyzes the page structure, generates navigation actions, and extracts data.

**When to use**:
- First time scraping a page
- Exploring new sections
- Complex navigation requirements
- Site structure unknown

**Example**:
```bash
aishell navigate https://www.icici.bank.in \
  --task "Find home loan interest rates for amounts above 50 lakhs" \
  --provider opus \
  --output home_loans.json
```

**What happens behind the scenes**:
1. **Page fetch**: Browser loads the URL and waits for JavaScript
2. **LLM analysis**: Opus receives the page HTML/structure
3. **Action generation**: Opus creates navigation sequence:
   ```yaml
   actions:
     - type: hover
       selector: ".nav-personal"
       reason: "Personal banking menu contains loans"
     - type: wait
       selector: ".mega-menu"
       timeout: 5000
     - type: click
       selector: "a:has-text('Home Loan')"
     - type: wait
       selector: ".rate-table"
     - type: extract
       selectors:
         loan_amount: "td.amount"
         interest_rate: "td.rate"
         tenure: "td.tenure"
       filter: "amount > 5000000"  # 50 lakhs
   ```
4. **Execution**: Actions are executed in sequence
5. **Extraction**: Data is extracted and formatted as JSON
6. **Output**: Results saved to `home_loans.json`

**No hard-coding required!** The LLM understands:
- Your intent ("find home loan interest rates")
- The constraint ("amounts above 50 lakhs")
- How to navigate the site
- What data to extract

### Mode 2: Configuration-Based (Reusable Patterns)

**What it does**: Opus discovers navigation once, saves the action sequence, then Haiku (or any LLM) executes the saved pattern repeatedly.

**When to use**:
- Repeated scraping (weekly updates)
- Known navigation paths
- Cost optimization (Haiku vs Opus)
- Production RAG pipeline

**Two-step process**:

#### Step 1: Discovery Phase (One-time with Opus)
```bash
# Discover navigation and save config
aishell navigate https://www.icici.bank.in \
  --task "Extract all personal loan products with rates and eligibility" \
  --provider opus \
  --save-config personal_loans.yaml \
  --output personal_loans.json
```

**Generated config** (`personal_loans.yaml`):
```yaml
name: "ICICI Personal Loans Extraction"
url: "https://www.icici.bank.in"
discovered_by: "opus"
discovered_at: "2025-01-15T10:30:00Z"
last_successful: "2025-01-15T10:30:00Z"

actions:
  - type: hover
    selector: ".nav-personal"
    description: "Open personal banking menu"

  - type: wait
    selector: ".mega-menu.visible"
    timeout: 5000
    description: "Wait for mega-menu to appear"

  - type: click
    selector: "a[href*='personal-loan']"
    description: "Click personal loan link"

  - type: wait
    selector: ".product-details"
    timeout: 5000

  - type: extract
    selectors:
      loan_type: "h2.product-name"
      interest_rate: ".rate-value"
      processing_fee: ".fee-amount"
      min_amount: ".loan-range .min"
      max_amount: ".loan-range .max"
      min_tenure: ".tenure-range .min"
      max_tenure: ".tenure-range .max"
      eligibility: ".eligibility-criteria li"
    description: "Extract loan product details"

output:
  format: "json"
  schema:
    loan_type: "string"
    interest_rate: "string"
    processing_fee: "string"
    min_amount: "number"
    max_amount: "number"
    min_tenure: "number"
    max_tenure: "number"
    eligibility: "array"
```

#### Step 2: Execution Phase (Repeated with Haiku)
```bash
# Weekly execution - fast and cheap!
aishell navigate --config personal_loans.yaml \
  --provider haiku \
  --output data/personal_loans_$(date +%Y%m%d).json
```

**What happens**:
1. Haiku loads the config (no reasoning needed)
2. Executes actions sequentially
3. Extracts data using saved selectors
4. Outputs JSON

**Cost comparison** (for weekly scraping):
- Opus every time: ~$2-5/week
- Haiku with saved config: ~$0.20-0.50/week
- **Savings: 90%**

### Mode 3: Task Variations with Fallback

**What it does**: Use saved config as base, but apply variations or handle site changes with intelligent fallback.

**When to use**:
- Site structure changed slightly
- Need filtered/modified extraction
- Want reliability with cost optimization

**Example 1: Filtered extraction**
```bash
# Base config extracts all loans, filter for specific criteria
aishell navigate --config all_loans.yaml \
  --task "Only include loans with rates below 10%" \
  --provider haiku \
  --fallback opus
```

**What happens**:
1. Haiku executes base navigation
2. Haiku applies filter based on task
3. If Haiku fails → Opus takes over
4. If Opus succeeds → Updates config for next time

**Example 2: Adaptive scraping**
```bash
# Handle site changes automatically
aishell navigate --config credit_cards.yaml \
  --provider haiku \
  --fallback opus \
  --update-config
```

**What happens**:
1. Haiku tries saved actions
2. If selectors fail (site changed) → Opus analyzes new structure
3. Opus generates updated actions
4. Config automatically updated with `--update-config`
5. Next run uses new config

## Two-Phase Strategy for RAG System

### Phase 1: Discovery (Week 1 - Setup)

**Goal**: Create comprehensive configs covering all customer service topics

**Use**: Claude Opus for intelligent discovery

**Tasks**:
```bash
# 1. Loan Products
aishell navigate https://www.icici.bank.in \
  --task "Extract all home loan products with interest rates, tenure options, and eligibility criteria" \
  --provider opus --save-config configs/home_loans.yaml

aishell navigate https://www.icici.bank.in \
  --task "Extract personal loan products with rates, processing fees, and documentation requirements" \
  --provider opus --save-config configs/personal_loans.yaml

aishell navigate https://www.icici.bank.in \
  --task "Extract car loan products with rates for new and used vehicles" \
  --provider opus --save-config configs/car_loans.yaml

aishell navigate https://www.icici.bank.in \
  --task "Extract education loan details including loan amounts, rates, and eligibility for studying abroad" \
  --provider opus --save-config configs/education_loans.yaml

# 2. Deposit Products
aishell navigate https://www.icici.bank.in \
  --task "Extract fixed deposit rates for all tenures with special rates for senior citizens" \
  --provider opus --save-config configs/fd_rates.yaml

aishell navigate https://www.icici.bank.in \
  --task "Extract recurring deposit rates and minimum monthly investment amounts" \
  --provider opus --save-config configs/rd_rates.yaml

# 3. Card Products
aishell navigate https://www.icici.bank.in \
  --task "Extract all credit card types with annual fees, reward programs, and eligibility criteria" \
  --provider opus --save-config configs/credit_cards.yaml

aishell navigate https://www.icici.bank.in \
  --task "Extract debit card types with features and associated account types" \
  --provider opus --save-config configs/debit_cards.yaml

# 4. Accounts
aishell navigate https://www.icici.bank.in \
  --task "Extract savings account types with minimum balance requirements and features" \
  --provider opus --save-config configs/savings_accounts.yaml

aishell navigate https://www.icici.bank.in \
  --task "Extract current account types for business banking with features and fees" \
  --provider opus --save-config configs/current_accounts.yaml

# 5. Services & Locations
aishell navigate https://www.icici.bank.in \
  --task "Extract branch locations with addresses, services offered, and operating hours" \
  --provider opus --save-config configs/branches.yaml

aishell navigate https://www.icici.bank.in \
  --task "Extract ATM locations and types (cash deposit, withdrawal only, etc.)" \
  --provider opus --save-config configs/atms.yaml

# 6. Fees & Charges
aishell navigate https://www.icici.bank.in \
  --task "Extract all service fees and charges for common banking operations" \
  --provider opus --save-config configs/fees_charges.yaml

# 7. Customer Service
aishell navigate https://www.icici.bank.in \
  --task "Extract customer service contact numbers, email addresses, and support hours" \
  --provider opus --save-config configs/customer_service.yaml

aishell navigate https://www.icici.bank.in \
  --task "Extract common FAQs about account opening, KYC, and documentation" \
  --provider opus --save-config configs/faqs.yaml
```

**Expected output**: 15-20 YAML configs covering comprehensive banking data

**Cost estimate**: $20-40 one-time (Opus discovery)

### Phase 2: Weekly Execution (Ongoing)

**Goal**: Keep RAG system updated with latest data

**Use**: Claude Haiku for cost-effective execution

**Weekly scrape script** (`scripts/weekly_scrape.sh`):
```bash
#!/bin/bash

# Weekly ICICI Bank data refresh for RAG system
# Runs every Sunday at 2 AM via cron

DATE=$(date +%Y%m%d)
OUTPUT_DIR="data/icici_bank/$DATE"
mkdir -p "$OUTPUT_DIR"

echo "Starting weekly ICICI Bank scrape: $DATE"

# Execute all configs with Haiku (cheap and fast)
for config in configs/*.yaml; do
  config_name=$(basename "$config" .yaml)
  echo "Processing: $config_name"

  aishell navigate \
    --config "$config" \
    --provider haiku \
    --fallback opus \
    --output "$OUTPUT_DIR/${config_name}.json" \
    --update-config
done

# Combine all JSON files for RAG ingestion
python scripts/combine_for_rag.py "$OUTPUT_DIR" > "data/icici_bank_latest.json"

# Update vector database
python scripts/update_rag_index.py "data/icici_bank_latest.json"

echo "Scrape complete! Data saved to: $OUTPUT_DIR"
```

**Cost estimate**: $0.50-2/week (Haiku execution with occasional Opus fallback)

**Annual savings vs all-Opus**: ~$200-250

## LLM Provider Strategy

### When to Use Each Model

| Model | Use Case | Cost | Speed | Reasoning |
|-------|----------|------|-------|-----------|
| **Claude Opus** | Initial discovery, complex sites, site changes | High ($15/M tokens) | Slow | Excellent reasoning |
| **Claude Sonnet** | Balanced option, moderately complex tasks | Medium ($3/M tokens) | Medium | Good reasoning |
| **Claude Haiku** | Executing known configs, simple extraction | Low ($0.25/M tokens) | Fast | Basic reasoning |

### Recommended Configuration

**For RAG system development**:
```bash
# .env configuration
DEFAULT_LLM_PROVIDER=claude
CLAUDE_MODEL=claude-3-opus-20240229  # For initial setup

# After configs are created, switch to:
CLAUDE_MODEL=claude-3-haiku-20240307  # For weekly execution
```

### Smart Fallback Example

```bash
# Try Haiku first, use Opus if needed
aishell navigate --config product.yaml \
  --provider haiku \
  --fallback opus \
  --fallback-threshold 0.8  # Use Opus if confidence < 80%
```

**Decision tree**:
1. Try with Haiku
2. If extraction confidence < 80% → Use Opus
3. If Opus succeeds → Update config with new selectors
4. If both fail → Alert for manual review

## Action Types Reference

### Navigation Actions

#### `hover`
Hover over element (for dropdown menus)
```yaml
- type: hover
  selector: ".nav-menu"
  description: "Trigger dropdown menu"
```

#### `click`
Click element (works for HTML links and JS buttons)
```yaml
- type: click
  selector: "a[href='/products']"
  description: "Navigate to products page"
```

#### `wait`
Wait for element or time
```yaml
# Wait for element
- type: wait
  selector: ".content-loaded"
  timeout: 5000

# Wait for time (milliseconds)
- type: wait
  duration: 2000
```

#### `scroll`
Scroll to element (trigger lazy-loading)
```yaml
- type: scroll
  selector: ".load-more"
  description: "Scroll to load more items"
```

### Data Extraction Actions

#### `extract`
Extract data using selectors
```yaml
- type: extract
  selectors:
    title: "h1.product-title"
    price: ".price-value"
    description: ".description"
    features: ".feature-list li"  # Extracts array
  description: "Extract product details"
```

#### `extract-table`
Extract tabular data
```yaml
- type: extract-table
  selector: "table.rate-table"
  columns:
    tenure: "td:nth-child(1)"
    rate: "td:nth-child(2)"
    amount: "td:nth-child(3)"
```

### Form Interaction Actions

#### `type`
Fill input fields
```yaml
- type: type
  selector: "input[name='amount']"
  value: "5000000"
  description: "Enter loan amount"
```

#### `select`
Select dropdown option
```yaml
- type: select
  selector: "select[name='tenure']"
  value: "240"  # 20 years
```

### Utility Actions

#### `screenshot`
Capture screenshot
```yaml
- type: screenshot
  filename: "product_page.png"
  fullpage: true
```

#### `js`
Execute custom JavaScript
```yaml
- type: js
  code: "window.scrollTo(0, document.body.scrollHeight)"
  description: "Scroll to bottom"
```

## Configuration File Format

### Complete Example

```yaml
# Config metadata
name: "ICICI Home Loans Extraction"
url: "https://www.icici.bank.in"
description: "Extract home loan products with rates, tenure, and eligibility"

# Discovery tracking
discovered_by: "opus"
discovered_at: "2025-01-15T10:30:00Z"
last_successful: "2025-01-20T08:15:00Z"
last_updated: "2025-01-20T08:15:00Z"
success_count: 12
failure_count: 1

# Browser settings
browser:
  headless: true
  timeout: 30000
  wait_until: "networkidle"
  viewport:
    width: 1920
    height: 1080

# Navigation strategy
strategy: "llm-assisted"  # or "manual"
fallback_strategy: "opus"  # If haiku fails

# Action sequence
actions:
  - type: hover
    selector: ".nav-personal"
    timeout: 5000
    description: "Open personal banking menu"

  - type: wait
    selector: ".mega-menu.visible"
    timeout: 5000

  - type: click
    selector: "a:has-text('Home Loan')"
    description: "Navigate to home loans"

  - type: wait
    selector: ".product-details"
    timeout: 10000

  - type: extract
    selectors:
      loan_type: "h2.product-name"
      interest_rate: ".rate-value"
      rate_type: ".rate-type"  # Fixed/Floating
      processing_fee: ".fee-amount"
      min_amount: ".loan-range .min"
      max_amount: ".loan-range .max"
      min_tenure: ".tenure-range .min"
      max_tenure: ".tenure-range .max"
      eligibility_income: ".eligibility .income"
      eligibility_age: ".eligibility .age"
      eligibility_employment: ".eligibility .employment"
      documents_required: ".documents li"
      special_features: ".features li"
    description: "Extract comprehensive loan details"

# Output configuration
output:
  format: "json"
  pretty: true
  schema:
    loan_type: "string"
    interest_rate: "float"
    rate_type: "string"
    processing_fee: "string"
    min_amount: "integer"
    max_amount: "integer"
    min_tenure: "integer"
    max_tenure: "integer"
    eligibility_income: "string"
    eligibility_age: "string"
    eligibility_employment: "string"
    documents_required: "array"
    special_features: "array"

# Validation rules
validation:
  required_fields:
    - loan_type
    - interest_rate
  data_quality:
    interest_rate: "must be between 6% and 20%"
    min_tenure: "must be greater than 0"
```

## Output Format

### JSON Structure
```json
{
  "metadata": {
    "url": "https://www.icici.bank.in/personal-banking/loans/home-loan",
    "scraped_at": "2025-01-20T08:15:30Z",
    "config": "home_loans.yaml",
    "provider": "haiku",
    "success": true
  },
  "data": [
    {
      "loan_type": "Home Loan",
      "interest_rate": 8.75,
      "rate_type": "Floating",
      "processing_fee": "0.5% of loan amount",
      "min_amount": 100000,
      "max_amount": 50000000,
      "min_tenure": 12,
      "max_tenure": 360,
      "eligibility_income": "Minimum Rs. 25,000 per month",
      "eligibility_age": "23 to 65 years",
      "eligibility_employment": "Salaried or Self-employed",
      "documents_required": [
        "Identity proof (Aadhaar, PAN, Passport)",
        "Address proof (Utility bill, Aadhaar)",
        "Income proof (Salary slips, ITR)",
        "Property documents",
        "Bank statements (6 months)"
      ],
      "special_features": [
        "Pre-payment allowed after 6 months",
        "Top-up loan facility available",
        "Balance transfer option",
        "Doorstep service available"
      ]
    }
  ]
}
```

## Error Handling & Reliability

### Automatic Retry Logic
```yaml
# In config file
retry:
  max_attempts: 3
  backoff: "exponential"  # 1s, 2s, 4s
  retry_on:
    - "timeout"
    - "element_not_found"
    - "network_error"
```

### Fallback Strategies
```yaml
fallback:
  - provider: "haiku"
    timeout: 30000
  - provider: "sonnet"  # If haiku fails
    timeout: 60000
  - provider: "opus"    # Last resort
    timeout: 120000
  - action: "alert"     # If all fail
    notify: "admin@example.com"
```

### Validation & Alerts
```yaml
validation:
  required_fields:
    - loan_type
    - interest_rate
  alert_on_failure: true
  alert_email: "data-team@example.com"
  data_quality_threshold: 0.9  # Alert if < 90% fields populated
```

## Integration with RAG System

### Data Pipeline
```
Weekly Scrape → JSON Files → Data Validation → Vector Embedding → RAG Index
```

### Example RAG Integration Script
```python
# scripts/update_rag_index.py
import json
from datetime import datetime
from your_rag_system import update_embeddings

def process_scraped_data(json_file):
    """Convert scraped data to RAG-friendly format"""
    with open(json_file) as f:
        data = json.load(f)

    documents = []
    for item in data['data']:
        # Create searchable document
        doc = {
            'id': f"icici_{item['loan_type'].lower().replace(' ', '_')}_{datetime.now().isoformat()}",
            'title': f"ICICI {item['loan_type']}",
            'content': f"""
            ICICI Bank {item['loan_type']} Details:

            Interest Rate: {item['interest_rate']}% ({item['rate_type']})
            Loan Amount: ₹{item['min_amount']:,} to ₹{item['max_amount']:,}
            Tenure: {item['min_tenure']} to {item['max_tenure']} months
            Processing Fee: {item['processing_fee']}

            Eligibility:
            - Income: {item['eligibility_income']}
            - Age: {item['eligibility_age']}
            - Employment: {item['eligibility_employment']}

            Documents Required:
            {chr(10).join('- ' + doc for doc in item['documents_required'])}

            Special Features:
            {chr(10).join('- ' + feat for feat in item['special_features'])}
            """,
            'metadata': {
                'source': 'icici_bank',
                'product_type': 'loan',
                'loan_category': item['loan_type'],
                'last_updated': data['metadata']['scraped_at']
            }
        }
        documents.append(doc)

    return documents

# Update RAG index
documents = process_scraped_data('data/icici_bank_latest.json')
update_embeddings(documents)
```

## Best Practices

### 1. Start Broad, Then Specific
```bash
# First: Understand site structure
aishell navigate https://www.icici.bank.in \
  --task "What are the main navigation categories?"

# Then: Extract specific data
aishell navigate https://www.icici.bank.in \
  --task "Extract home loan interest rates"
```

### 2. Use Descriptive Config Names
```
✅ Good: home_loans_with_eligibility.yaml
❌ Bad: scrape1.yaml
```

### 3. Version Your Configs
```
configs/
  v1/
    home_loans.yaml
  v2/
    home_loans.yaml  # Updated for site redesign
  current/
    home_loans.yaml  # Symlink to latest version
```

### 4. Monitor Success Rates
```bash
# Check config performance
aishell navigate --config home_loans.yaml --dry-run --stats

# Output:
# Success rate: 92% (23/25 runs)
# Average time: 8.3s
# Last failure: 2025-01-18 (selector changed)
# Recommended: Update config
```

### 5. Test Before Production
```bash
# Test with visible browser first
aishell navigate --config new_config.yaml \
  --show-browser \
  --provider opus

# Then run headless
aishell navigate --config new_config.yaml \
  --provider haiku
```

## Troubleshooting

### Common Issues

#### Issue: Selectors Not Found
```
Error: Selector '.product-name' not found
```

**Solution**:
```bash
# Re-discover with Opus
aishell navigate --config product.yaml \
  --provider opus \
  --update-config

# Or inspect manually
aishell navigate https://example.com \
  --show-browser \
  --task "Find the product name selector"
```

#### Issue: JavaScript Not Loaded
```
Error: Element not interactive
```

**Solution**: Add waits
```yaml
- type: wait
  selector: ".js-loaded-indicator"
  timeout: 10000

- type: wait
  duration: 2000  # Additional buffer
```

#### Issue: Data Quality Low
```
Warning: Only 45% of fields populated
```

**Solution**: Review extraction selectors
```bash
aishell navigate --config product.yaml \
  --debug \
  --show-browser  # See what's actually on page
```

## Future Enhancements

### Planned Features
- [ ] Session management for authenticated sites
- [ ] Proxy support for rate limiting
- [ ] Parallel scraping for multiple pages
- [ ] Interactive recorder (click on page, generate config)
- [ ] Visual regression testing (detect layout changes)
- [ ] Multi-language support
- [ ] PDF extraction
- [ ] API endpoint detection (use API instead of scraping when available)

---

## Quick Reference

### Common Commands
```bash
# Discover navigation
aishell navigate <url> --task "<description>" --provider opus --save-config <file>

# Execute config
aishell navigate --config <file> --provider haiku --output <json>

# With fallback
aishell navigate --config <file> --provider haiku --fallback opus

# Update config
aishell navigate --config <file> --provider opus --update-config

# Debug mode
aishell navigate <url> --task "<task>" --show-browser --debug
```

### Cost Optimization
- Use Opus for discovery (one-time)
- Use Haiku for execution (recurring)
- Use fallback to balance cost and reliability
- Cache successful patterns in configs

### LLM Selection Guide
- **Complex site**: Opus
- **Site changed**: Opus
- **Known pattern**: Haiku
- **Unsure**: Haiku with Opus fallback

---

**Last Updated**: 2025-01-25
**Version**: 1.0
**Author**: AIShell Development Team
