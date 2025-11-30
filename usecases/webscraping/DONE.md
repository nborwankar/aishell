# Web Scraping Framework - Development Log

## Implementation - 2025-11-25

### Summary
Implemented a complete, generic web scraping framework with LLM-assisted navigation using Playwright. The framework works with ANY public website (not ICICI-specific) and supports natural language task descriptions.

### Core Features Implemented

#### 1. Action System (`actions.py`)
- **10 action types**: navigate, click, hover, wait, extract, scroll, type, select, screenshot, js
- Dataclass-based architecture with type safety
- Action factory function for dynamic creation from dictionaries
- Full serialization support (to_dict/from_dict)

#### 2. Navigation Engine (`navigator.py`)
- **Playwright integration** with async/await support
- Context manager pattern for resource cleanup
- Support for 3 browsers: Chromium, Firefox, WebKit
- Headless and non-headless modes
- Action execution engine with error handling
- Screenshot capabilities
- Page source and metadata extraction

#### 3. LLM Integration (`llm_navigator.py`)
- **Natural language to actions** translation
- Prompt engineering for accurate action generation
- Multi-provider support (Claude, OpenAI, Gemini, Ollama)
- Fallback mechanism (Haiku → Opus)
- Configuration save/load for reusable patterns
- Retry logic with refinement on failure

#### 4. Data Extraction (`extractors.py`)
- **Multiple extraction modes**: text, HTML, attributes
- Table extraction with header detection
- Link extraction with text
- Structured extraction with multiple selectors
- Page metadata extraction (title, description, OG tags)
- Fallback selector support

#### 5. Configuration Management (`config.py`)
- **YAML-based configuration** files
- Configuration validation with detailed error messages
- Configuration library for managing multiple configs
- Metadata support (category, frequency, etc.)
- Provider specification per config

#### 6. CLI Command (`aishell/cli.py`)
- **`aishell navigate` command** with comprehensive options
- Three navigation modes:
  - Mode 1: Free-form task (`--task "natural language"`)
  - Mode 2: Configuration-based (`--config file.yaml`)
  - Mode 3: Hybrid with fallback
- Opus/Haiku shortcuts for Claude models
- Output format support (JSON, YAML)
- Browser selection (chromium, firefox, webkit)
- Headless/non-headless toggle

### Architecture Design Decisions

#### Generic Framework
- **Zero ICICI-specific code** in any module
- Works with any public website immediately
- Examples are templates, not hard-coded logic
- LLM figures out navigation patterns dynamically

#### Two-Phase Strategy
- **Discovery Phase**: Use Opus to explore site, generate configs (one-time, $2-4/page)
- **Execution Phase**: Use Haiku with saved configs (recurring, $0.05-0.20/page)
- **Cost savings**: 90% reduction for recurring scraping

#### JavaScript Menu Handling
- **Hover → Wait → Click pattern** for mega menus
- AJAX content loading with explicit waits
- Network idle detection for dynamic content
- Scroll-triggered lazy loading support

### Files Created

**Core Framework**:
- `usecases/webscraping/__init__.py` - Package initialization
- `usecases/webscraping/actions.py` - 365 lines
- `usecases/webscraping/navigator.py` - 342 lines
- `usecases/webscraping/llm_navigator.py` - 285 lines
- `usecases/webscraping/extractors.py` - 298 lines
- `usecases/webscraping/config.py` - 257 lines
- `usecases/webscraping/README.md` - Comprehensive documentation
- `usecases/webscraping/GUIDE.md` - 7,500+ word guide

**CLI Integration**:
- Updated `aishell/cli.py` - Added `navigate` command (242 lines)
- Updated `.gitignore` - Protected examples directory

### Total Lines of Code
- Core modules: ~1,547 lines
- CLI integration: ~242 lines
- Documentation: ~7,500 words

---

## Bug Fixes - 2025-11-25

### 1. Design Flaw: Read-Only `default_model` Property
**Problem**: CLI tried to set `llm_provider_instance.default_model = model_override` but `default_model` was a read-only property computed from environment variables.

**Root Cause**: Poor design - model override was attempted via property mutation instead of method parameter.

**Fix** (proper design, not workaround):
- Added `model` and `fallback_model` parameters to `LLMNavigator.__init__()`
- Updated all `query()` calls to pass model parameter: `self.llm_provider.query(prompt, model=self.model)`
- CLI now passes model to `LLMNavigator` constructor instead of trying to set provider property

**Files Modified**:
- `usecases/webscraping/llm_navigator.py` (lines 24-26, 69, 78, 287, 289)
- `aishell/cli.py` (lines 746-748, 784-785, 827-828)

### 2. Critical Bug: `_parse_llm_response()` Type Mismatch
**Problem**: `_parse_llm_response()` expected `str` but `query()` returns `LLMResponse` object.

**Code Before** (broken):
```python
response = await self.llm_provider.query(prompt)
actions = self._parse_llm_response(response)  # TypeError!
```

**Code After** (fixed):
```python
response = await self.llm_provider.query(prompt, model=self.model)
if response.is_error:
    raise ValueError(response.error)
actions = self._parse_llm_response(response.content)  # Correct!
```

**Files Modified**:
- `usecases/webscraping/llm_navigator.py` (lines 69-72, 78-81, 291-293)

### 3. Missing Dependencies
**Problem**: `yaml` module not found, `usecases` not a Python package.

**Fix**:
- Installed `pyyaml` package
- Created `usecases/__init__.py`

### 4. JS Action Results Not Captured
**Problem**: Navigator wasn't storing JavaScript action return values.

**Fix**: Added code to parse and store JS results in `navigator.py:319-330`

---

## Technical Notes

### JavaScript Action Syntax
```yaml
# WRONG - causes "Illegal return statement"
- type: js
  code: |
    const x = 1;
    return x;

# CORRECT - wrap in IIFE
- type: js
  code: |
    (() => {
      const x = 1;
      return x;
    })()
```

### Hidden Element Workaround
When Playwright's `hover` fails with "element is not visible" but locator finds elements:
1. Use JavaScript action to click directly
2. Target elements by `data-*` attributes
3. Add explicit waits after navigation

### Selector Strategies
- CSS selectors with Playwright-specific extensions
- Text-based selectors (`:has-text()`)
- Attribute selectors for data attributes
- Fallback selector chains

### Async Architecture
- All operations use async/await
- Proper resource cleanup with context managers
- No blocking operations
- Concurrent action execution where safe
