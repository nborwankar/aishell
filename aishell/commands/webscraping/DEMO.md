# Web Scraping Demo

## Credit Cards Extraction (ICICI Bank)

Extracts 24 credit card product names from ICICI Bank's website using scroll + wait pattern for lazy-loaded content.

### Run the Demo

```bash
cd /Users/nitin/Projects/github/aishell
source venv/bin/activate
PYTHONPATH=. aishell navigate --config tests/webscraping/test_credit_cards_ajax.yaml --no-headless
```

### Expected Output

```json
{
  "page_title": "Credit Card - Apply Credit Card Online & Get Instant Approval",
  "credit_card_names": [
    "Emeralde Private Metal Credit Card",
    "Times Black Credit Card",
    "Emeralde Credit Card",
    "Sapphiro Credit Card",
    "Rubyx Credit Card",
    "Coral Credit Card",
    "Platinum Chip Credit Card",
    "Adani One Signature Credit Card",
    "Adani One Platinum Credit Card",
    "MakeMyTrip Credit Card",
    "Emirates Emeralde Credit Card",
    "Emirates Sapphiro Credit Card",
    "Emirates Skywards Rubyx Credit Card",
    "HPCL Super Saver Credit Card",
    "HPCL Coral Credit Card",
    "Expression Credit Card",
    "Amazon Pay Credit Card",
    "Manchester United Signature Credit Card",
    "Manchester United Platinum Credit Card",
    "MakeMyTrip Signature Credit Card",
    "MakeMyTrip Platinum Credit Card",
    "Chennai Super Kings Credit Card",
    "Parakram Select Credit Card",
    "Parakram Credit Card"
  ],
  "total_cards_found": 24
}
```

### How It Works

1. Navigate to credit cards page with `networkidle` wait
2. Wait 3s for initial page load
3. Scroll down 1000px (3 times) to trigger lazy loading
4. Wait 2s after each scroll for content to load
5. Extract card names using JavaScript with `.credit-card__name` selector

### Key CSS Selector

```css
.credit-card__name
```

This is the only selector that contains actual credit card product names. Other selectors like `.card__heading h3` pick up testimonials and FAQ headings.
