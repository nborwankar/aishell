# Web Scraping Framework - Testing

## Implementation Status

- [x] **Architecture Design**: Generic scraping framework (not ICICI-specific)
- [x] **Core Modules Implementation**:
  - [x] `actions.py` - Define 10 action types (click, hover, wait, extract, scroll, type, select, screenshot, js, navigate)
  - [x] `navigator.py` - Playwright-based navigation engine with async support
  - [x] `llm_navigator.py` - LLM task-to-actions translation system
  - [x] `extractors.py` - Data extraction utilities (text, HTML, attributes, tables, links)
  - [x] `config.py` - YAML configuration parser and validator
- [x] **CLI Integration**:
  - [x] Add `aishell navigate` command with full option set
  - [x] Support for --task (LLM-assisted), --config (YAML-based), --provider, --fallback
  - [x] Opus/Haiku shortcuts for Claude model selection
  - [x] Output format support (JSON, YAML)
- [x] **Documentation**:
  - [x] Comprehensive README.md emphasizing generic design
  - [x] GUIDE.md with three navigation modes explained
  - [x] Real-world examples across 8 industries
  - [x] Cost optimization strategy (Opus discovery → Haiku execution)
- [x] **Example Configurations** (ICICI Bank - for testing only, gitignored):
  - [x] Home loans extraction config
  - [x] Credit cards listing config
  - [x] Savings accounts config
  - [x] Branch locator config
  - [x] Fixed deposits rates config

## Test Scenarios for ICICI Bank Scraping

### Scenario 1: Simple Navigation Test (HTML Links) ✅ PASSED
**Objective**: Test basic navigation to a static page without JavaScript

**Test Steps**:
```bash
aishell navigate https://www.icicibank.com/about-us \
  --task "Extract the page title and main heading" \
  --provider haiku \
  --no-headless
```

**Result**: ✅ PASSED
- Extracted: `page_title: "About Us - ICICI Bank"`, `main_heading: "About Us"`
- 2 actions executed, no errors

### Scenario 2: JavaScript Menu Navigation (Hover Menu) ✅ PASSED
**Objective**: Test JavaScript-driven mega menu interaction

**Test Steps**:
```bash
# Used JS workaround for hidden menu elements (mobile responsive view)
aishell navigate --config test_home_loan_nav.yaml --no-headless
```

**Result**: ✅ PASSED (with JS workaround)
- Standard hover failed ("element not visible" in default viewport)
- JS click via `data-cta-region` attribute selector worked
- Extracted: `page_title: "Home Loan - Apply for Home Loan Online..."`, `main_heading: "Hassle-Free Home Loans"`
- 7 actions executed, no errors

**Learnings**:
- Menu items hidden in mobile-responsive view
- Use `js` action with IIFE wrapper for hidden elements
- Add 5s wait after JS-triggered navigation

### Scenario 3: Data Extraction from Product Page ⚠️ NOT APPLICABLE
**Objective**: Extract structured data from home loan page

**Result**: ⚠️ **PAGE NOT SUITABLE FOR SCRAPING**

The ICICI Home Loan page (`/personal-banking/loans/home-loan`) is a **marketing page with interactive calculators**, not a data page with static loan terms:
- Interest rates shown via sliders (8%, 10%, 12%, etc.) - not actual rates
- No static processing fee, tenure, or eligibility data
- Content is personalized/dynamic, not structured

**Lesson Learned**: Not all pages are suitable for extraction. Marketing pages with calculators need different approaches (API calls, form submission) or should be skipped.

**Pages to skip for ICICI**:
- `/personal-banking/loans/home-loan` - interactive calculator, no static data
- Similar product landing pages with calculators

**Better targets for extraction**:
- Rate comparison tables
- Fee schedules
- Branch/ATM locator results
- Account feature comparison pages

### Scenario 4: AJAX Content Loading ✅ PASSED
**Objective**: Test handling of dynamically loaded content

**Test Steps**:
```bash
aishell navigate --config tests/webscraping/test_credit_cards_ajax.yaml --no-headless
```

**Result**: ✅ PASSED
- Successfully extracted 24 credit card names (actual products)
- Scroll + wait pattern triggered lazy loading correctly
- **Correct CSS selector**: `.credit-card__name` only
- Removed overly broad selectors that captured testimonials and FAQs

**Success Criteria**:
- ✅ Scroll action triggers lazy loading
- ✅ Wait ensures content is loaded before extraction
- ✅ All dynamically loaded elements captured

### Scenario 5: Multi-Step Navigation ✅ PASSED
**Objective**: Test complex navigation sequence

**Test Steps**:
```bash
aishell navigate --config tests/webscraping/test_multi_step_nav.yaml --no-headless
```

**Result**: ✅ PASSED
- All 10 actions executed successfully
- Navigation path: Personal Banking → Loans → Home Loan → Eligibility
- Final URL: `https://www.icici.bank.in/calculator/customer-360-eligibility...`
- Page title: "Customer 360 Eligibility Calculator – Check Loan Eligibility"

**Success Criteria**:
- ✅ Each navigation step completes successfully
- ✅ Correct page reached after multi-step navigation
- ✅ Data extraction accurate

### Scenario 6: Fallback Mechanism Test ⚠️ PARTIAL (Infrastructure Works)
**Objective**: Verify Haiku → Opus fallback works

**Test Steps**:
```bash
aishell navigate https://www.icicibank.com/ \
  --task "Navigate to Credit Cards section, find the Amazon Pay credit card..." \
  --provider haiku \
  --fallback opus \
  --save-config /tmp/fallback_test.yaml \
  --no-headless
```

**Result**: ⚠️ PARTIAL
- Haiku successfully generated valid JSON actions (5 actions)
- One action failed at runtime (selector didn't match)
- **Fallback was NOT triggered** because Haiku didn't fail at generation level

**Note**: The fallback mechanism is designed for LLM generation failures (API errors, malformed JSON), not runtime execution errors. This is expected behavior.

**Success Criteria**:
- ✅ System attempts with Haiku first
- ⚠️ Falls back to Opus if Haiku fails (not triggered - Haiku succeeded)
- ⚠️ Final result is successful (partial - some actions failed)

### Scenario 7: Configuration Reusability Test ✅ PASSED
**Objective**: Verify saved configs work reliably

**Test Steps**:
```bash
for i in 1 2 3; do
  aishell navigate --config tests/webscraping/test_credit_cards_ajax.yaml
  sleep 3
done
```

**Result**: ✅ PASSED
- All 3 runs completed successfully
- All runs returned exactly 24 credit card names (actual products)
- Fixed extraction to use only `.credit-card__name` selector
- Removed overly broad selectors that captured testimonials and FAQs

**Success Criteria**:
- ✅ All three runs succeed
- ✅ Data is consistent across runs (24 cards each time)
- ✅ No intermittent failures

### Scenario 8: Browser Compatibility Test ⏭️ SKIPPED
**Objective**: Test across different browsers

**Result**: ⏭️ SKIPPED - Not applicable for automated scraping
- We control the browser (Chromium default)
- Single Playwright instance, not serving end users
- Playwright API is identical across browsers
- No value in testing Firefox/WebKit for scraping use case

### Scenario 9: Error Handling Test ✅ PASSED
**Objective**: Test graceful error handling

**Test Steps**:
```bash
# Test 9a: Invalid selector
aishell navigate --config tests/webscraping/test_error_handling.yaml

# Test 9b: Non-existent URL
aishell navigate https://invalid-url-xyz123.com --task "Extract data" --provider haiku
```

**Result**: ✅ PASSED
- Invalid selector: Caught timeout error, reported "Timeout 5000ms exceeded"
- Non-existent URL: Caught `net::ERR_NAME_NOT_RESOLVED`, reported clearly
- No crashes or hangs in either case
- Error messages are actionable (show what failed and why)

**Success Criteria**:
- ✅ Errors are caught and reported clearly
- ✅ No crashes or hangs
- ✅ Error messages are actionable

### Scenario 10: Cost Optimization Validation ⏳ PENDING
**Objective**: Verify Opus → Haiku cost savings

**Test Steps**:
```bash
# Phase 1: Discovery with Opus
time aishell navigate https://www.icicibank.com/ \
  --task "Extract home loan details" \
  --provider opus \
  --save-config cost_test.yaml

# Phase 2: Execute with Haiku (5 times)
for i in {1..5}; do
  time aishell navigate --config cost_test.yaml --provider haiku
done
```

**Success Criteria**:
- ✅ Config generated successfully with Opus
- ✅ Haiku executes faster than Opus discovery
- ✅ Results are equivalent

## Test Execution Checklist
- [x] Run scenarios #1-7
- [x] Run scenario #9 (Error Handling)
- [ ] Run scenario #10 (Cost Optimization)
- [x] Document findings
- [x] Fix extraction selectors (use only `.credit-card__name`)
- [x] Move documentation to usecases/webscraping/

## Key Learnings

### 1. Marketing vs Data Pages
Not all pages are suitable for extraction:
- **Skip**: Pages with calculators, sliders, personalized content
- **Target**: Rate tables, fee schedules, product listings

### 2. CSS Selector Precision
Broad selectors pick up unrelated content:
- **Bad**: `h3` with `[class*="card"]` parent (picks up testimonials, FAQs)
- **Good**: `.credit-card__name` (only card product names)

### 3. JavaScript Actions
Use IIFE wrapper for return statements:
```javascript
(() => {
  // code here
  return result;
})()
```

### 4. Hidden Menu Elements
Use JS click, not hover:
- Menus often hidden in responsive view
- Use `data-cta-region` attribute selectors
- Add 5s wait after JS-triggered navigation
