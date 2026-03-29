# ICICI Bank Scraping Examples

This directory contains example scraping configurations for ICICI Bank website.

## Available Configurations

### 1. Home Loans (`icici_home_loans.yaml`)
Extracts home loan products including:
- Loan types
- Interest rates
- Processing fees
- Eligibility criteria
- Required documents

**Usage:**
```bash
aishell navigate --config usecases/webscraping/examples/icici_home_loans.yaml \
  --provider haiku --fallback opus --output home_loans.json
```

### 2. Credit Cards (`icici_credit_cards.yaml`)
Extracts all credit card offerings:
- Card names and types
- Annual fees
- Rewards programs
- Key benefits
- Application URLs

**Usage:**
```bash
aishell navigate --config usecases/webscraping/examples/icici_credit_cards.yaml \
  --provider haiku --output credit_cards.json
```

### 3. Savings Accounts (`icici_savings_accounts.yaml`)
Extracts savings account types:
- Account types
- Minimum balance requirements
- Interest rates
- Monthly charges
- Features and benefits

**Usage:**
```bash
aishell navigate --config usecases/webscraping/examples/icici_savings_accounts.yaml \
  --provider haiku --output savings_accounts.json
```

### 4. Branch Locator (`icici_branch_locator.yaml`)
Searches for branches by location:
- Branch names
- Addresses
- Contact information
- Timings
- Available services

**Usage:**
```bash
aishell navigate --config usecases/webscraping/examples/icici_branch_locator.yaml \
  --provider haiku --output branches_mumbai.json
```

### 5. Fixed Deposits (`icici_fixed_deposits.yaml`)
Extracts FD interest rates:
- Tenure-wise rates
- General vs senior citizen rates
- Minimum deposit amounts
- Tax benefits
- Terms and conditions

**Usage:**
```bash
aishell navigate --config usecases/webscraping/examples/icici_fixed_deposits.yaml \
  --provider haiku --output fd_rates.json
```

## Two-Phase Strategy for RAG System

### Phase 1: Discovery (One-time, use Opus)
Generate configurations using natural language:

```bash
# Discover home loans structure
aishell navigate https://www.icici.bank.in \
  --task "Navigate to home loans section and extract all product details including rates, fees, eligibility" \
  --provider opus \
  --save-config icici_home_loans.yaml

# Discover credit cards
aishell navigate https://www.icici.bank.in \
  --task "Find all credit cards, extract names, fees, rewards, and benefits" \
  --provider opus \
  --save-config icici_credit_cards.yaml
```

**Cost:** $20-40 for initial discovery of 10-15 product pages

### Phase 2: Weekly Execution (use Haiku)
Run saved configurations with Haiku for 90% cost savings:

```bash
# Weekly scraping script
for config in usecases/webscraping/examples/*.yaml; do
    aishell navigate --config "$config" \
      --provider haiku \
      --fallback opus \
      --output "data/$(basename $config .yaml).json"
done
```

**Cost:** $0.50-2.00 per week for all product pages

## Customization

### Modifying Selectors
If ICICI Bank changes their website structure, update the CSS selectors in the YAML files:

```yaml
selectors:
  interest_rate: ".rate-value"  # Old selector
  interest_rate: ".new-rate-class"  # Updated selector
```

### Adding New Products
Create new configurations using the discovery approach:

```bash
aishell navigate https://www.icici.bank.in \
  --task "Extract personal loan details including rates, tenure, eligibility" \
  --provider opus \
  --save-config icici_personal_loans.yaml
```

## Integration with RAG System

After scraping, process the data for RAG ingestion:

```python
import json
from pathlib import Path

# Combine all scraped data
all_data = {}
for json_file in Path("data").glob("*.json"):
    with open(json_file) as f:
        data = json.load(f)
        all_data[json_file.stem] = data

# Format for RAG ingestion
rag_documents = []
for product_type, details in all_data.items():
    doc = {
        "id": f"icici_{product_type}",
        "text": format_for_rag(details),  # Convert to readable text
        "metadata": {
            "source": "ICICI Bank",
            "product": product_type,
            "scraped_at": datetime.now().isoformat()
        }
    }
    rag_documents.append(doc)

# Ingest into vector database
vector_db.add_documents(rag_documents)
```

## Notes

- These configurations use CSS selectors that may need updating if ICICI Bank redesigns their website
- Always run with `--fallback opus` to handle unexpected changes
- Test configurations in non-headless mode first: `--no-headless`
- Respect robots.txt and rate limits
- Weekly scraping is sufficient for banking product information
