# Directory Cleanup & Webscraping Command Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up cruft from the repo and move `usecases/webscraping/` into `aishell/commands/webscraping/` as a proper auto-discovered command plugin.

**Architecture:** The webscraping modules move into a package under `aishell/commands/` following the same pattern as `aishell/commands/conversations/` — a package with `cli.py` exporting a `click.Group`. The `navigate` command currently hardcoded in `cli.py` (lines 1261-1551) gets extracted into this new plugin. Cruft directories (`__pycache__`, `venv`, empty `scrape/`, dead `tools/`) get deleted.

**Tech Stack:** Python, Click CLI framework, Playwright, Rich

---

## File Structure

```
Changes:
  DELETE: __pycache__/                          (stale root pytest bytecode)
  DELETE: venv/                                 (old venv, user uses conda)
  DELETE: aishell/venv/                         (nested venv in source, wrong location)
  DELETE: aishell/scrape/                       (empty directory)
  DELETE: aishell/tools/                        (untracked dead code, never integrated)
  DELETE: usecases/                             (entire dir — code moves to commands/)
  MOVE:   usecases/webscraping/*.py         →   aishell/commands/webscraping/*.py
  MOVE:   usecases/webscraping/examples/    →   aishell/commands/webscraping/examples/
  CREATE: aishell/commands/webscraping/cli.py   (Click group + navigate command)
  MODIFY: aishell/commands/webscraping/__init__.py  (fix import path in docstring)
  MODIFY: aishell/cli.py                        (remove navigate command, lines 1261-1551)
  MODIFY: .gitignore                            (update examples path)
```

---

### Task 1: Delete Cruft Directories

**Files:**
- Delete: `__pycache__/` (root)
- Delete: `venv/` (root)
- Delete: `aishell/venv/`
- Delete: `aishell/scrape/`
- Delete: `aishell/tools/`
- Delete: `usecases/__pycache__/`
- Delete: `usecases/webscraping/__pycache__/`

- [ ] **Step 1: Verify none are symlinks**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
ls -la __pycache__ venv aishell/venv aishell/scrape aishell/tools
```

Expected: No `->` arrows (none are symlinks).

- [ ] **Step 2: Delete cruft**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
rm -rf __pycache__
rm -rf venv
rm -rf aishell/venv
rm -rf aishell/scrape
rm -rf aishell/tools
rm -rf usecases/__pycache__
rm -rf usecases/webscraping/__pycache__
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
git add -A
git commit -m "chore: remove cruft dirs (stale pycache, dead venv, empty scrape, unused tools)"
```

Note: `venv/` and `__pycache__/` are gitignored so `git add -A` won't stage them — that's fine, they're just local cleanup. The tracked deletions are `aishell/scrape/` and `aishell/tools/` (untracked, so no git change either). The commit may be empty if none were tracked — skip commit in that case.

---

### Task 2: Move Webscraping Modules into Commands Package

**Files:**
- Create: `aishell/commands/webscraping/` (directory)
- Move: `usecases/webscraping/actions.py` → `aishell/commands/webscraping/actions.py`
- Move: `usecases/webscraping/navigator.py` → `aishell/commands/webscraping/navigator.py`
- Move: `usecases/webscraping/llm_navigator.py` → `aishell/commands/webscraping/llm_navigator.py`
- Move: `usecases/webscraping/extractors.py` → `aishell/commands/webscraping/extractors.py`
- Move: `usecases/webscraping/config.py` → `aishell/commands/webscraping/config.py`
- Move: `usecases/webscraping/examples/` → `aishell/commands/webscraping/examples/`
- Move: `usecases/webscraping/README.md` → `aishell/commands/webscraping/README.md`
- Move: `usecases/webscraping/DONE.md` → `aishell/commands/webscraping/DONE.md`
- Move: `usecases/webscraping/TESTING.md` → `aishell/commands/webscraping/TESTING.md`
- Move: `usecases/webscraping/DEMO.md` → `aishell/commands/webscraping/DEMO.md`
- Move: `usecases/webscraping/GUIDE.md` → `aishell/commands/webscraping/GUIDE.md`

- [ ] **Step 1: Create target directory and copy files**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
mkdir -p aishell/commands/webscraping/examples
cp usecases/webscraping/actions.py aishell/commands/webscraping/
cp usecases/webscraping/navigator.py aishell/commands/webscraping/
cp usecases/webscraping/llm_navigator.py aishell/commands/webscraping/
cp usecases/webscraping/extractors.py aishell/commands/webscraping/
cp usecases/webscraping/config.py aishell/commands/webscraping/
cp usecases/webscraping/__init__.py aishell/commands/webscraping/
cp usecases/webscraping/README.md aishell/commands/webscraping/
cp usecases/webscraping/DONE.md aishell/commands/webscraping/
cp usecases/webscraping/TESTING.md aishell/commands/webscraping/
cp usecases/webscraping/DEMO.md aishell/commands/webscraping/
cp usecases/webscraping/GUIDE.md aishell/commands/webscraping/
cp usecases/webscraping/examples/*.yaml aishell/commands/webscraping/examples/
cp usecases/webscraping/examples/README.md aishell/commands/webscraping/examples/
```

- [ ] **Step 2: Update `__init__.py` docstring import path**

In `aishell/commands/webscraping/__init__.py`, change the example import from:

```python
    from usecases.webscraping import WebNavigator, LLMNavigator, ScrapingConfig
```

to:

```python
    from aishell.commands.webscraping import WebNavigator, LLMNavigator, ScrapingConfig
```

- [ ] **Step 3: Commit the move**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
git add aishell/commands/webscraping/
git commit -m "refactor: move webscraping modules from usecases/ to aishell/commands/webscraping/"
```

---

### Task 3: Create CLI Plugin (`cli.py`) for Webscraping Command Group

This is the key integration step. We create `aishell/commands/webscraping/cli.py` with a `click.Group` named `webscraping` and a `navigate` subcommand that contains the logic currently in `aishell/cli.py` lines 1261-1551.

The command syntax changes from `aishell navigate ...` to `aishell webscraping navigate ...` (consistent with the plugin pattern: `aishell conversations load`, `aishell gemini pull`, etc.).

**Files:**
- Create: `aishell/commands/webscraping/cli.py`

- [ ] **Step 1: Create `aishell/commands/webscraping/cli.py`**

```python
"""Webscraping command group — LLM-assisted web navigation and extraction.

Subcommands:
    aishell webscraping navigate URL [OPTIONS]   # Navigate and scrape
    aishell webscraping configs                   # List saved configs
"""

import asyncio
import json
import logging

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()
logger = logging.getLogger(__name__)

SKILL = {
    "name": "webscraping",
    "description": "LLM-assisted web scraping with Playwright",
    "capabilities": [
        "Navigate websites using natural language task descriptions",
        "Execute saved YAML scraping configurations",
        "Two-phase strategy: Opus for discovery, Haiku for execution",
        "Extract structured data (text, HTML, attributes, tables)",
    ],
    "examples": [
        'aishell webscraping navigate https://example.com --task "Extract product prices"',
        "aishell webscraping navigate --config saved.yaml --provider haiku",
        "aishell webscraping configs",
    ],
    "tools": [],
}


@click.group()
def webscraping():
    """LLM-assisted web scraping with Playwright."""
    pass


@webscraping.command()
@click.argument("url", required=False)
@click.option("--task", "-t", help="Natural language task description (LLM-assisted)")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Use saved configuration file",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["claude", "openai", "gemini", "ollama", "opus", "haiku"]),
    help="LLM provider for task translation",
)
@click.option(
    "--fallback",
    type=click.Choice(["claude", "openai", "gemini", "ollama", "opus", "haiku"]),
    help="Fallback provider if primary fails",
)
@click.option(
    "--save-config", type=click.Path(), help="Save generated configuration to file"
)
@click.option(
    "--output", "-o", type=click.Path(), help="Output file for extracted data"
)
@click.option(
    "--headless/--no-headless", default=True, help="Run browser in headless mode"
)
@click.option(
    "--browser",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
    help="Browser type",
)
def navigate(
    url, task, config, provider, fallback, save_config, output, headless, browser
):
    """Navigate and scrape websites using LLM-assisted Playwright automation.

    Three modes of operation:

    1. Free-form task (LLM translates to actions):
       aishell webscraping navigate https://example.com --task "Extract all product prices"

    2. Configuration-based (reusable patterns):
       aishell webscraping navigate --config home_loans.yaml

    3. Task variations with fallback:
       aishell webscraping navigate https://example.com --task "Get loan rates" --provider haiku --fallback opus

    Examples:
        # Discovery with Opus
        aishell webscraping navigate https://www.icici.bank.in \\
          --task "Extract all home loan products with rates" \\
          --provider opus --save-config home_loans.yaml

        # Weekly execution with Haiku
        aishell webscraping navigate --config home_loans.yaml \\
          --provider haiku --fallback opus --output data.json

        # Quick extraction
        aishell webscraping navigate https://news.ycombinator.com \\
          --task "Get top 10 story titles and URLs"
    """

    async def run_navigation():
        from pathlib import Path

        from aishell.commands.webscraping import (
            WebNavigator,
            LLMNavigator,
            ScrapingConfig,
        )
        from aishell.llm import (
            ClaudeLLMProvider,
            OpenAILLMProvider,
            GeminiLLMProvider,
            OllamaLLMProvider,
        )
        from aishell.utils import get_env_manager

        # Validate inputs
        if not url and not config:
            console.print("[red]Error:[/red] Either URL or --config must be provided")
            return

        if config and not Path(config).exists():
            console.print(
                f"[red]Error:[/red] Configuration file not found: {config}"
            )
            return

        # Get LLM provider if needed
        llm_provider_instance = None
        fallback_provider_instance = None
        model_override = None
        fallback_model = None

        if task or (config and provider):
            env_manager = get_env_manager()

            # Map opus/haiku to claude with specific models
            if provider == "opus":
                provider_name = "claude"
                model_override = "claude-opus-4-20250514"
            elif provider == "haiku":
                provider_name = "claude"
                model_override = "claude-3-5-haiku-20241022"
            else:
                provider_name = provider or env_manager.get_var(
                    "DEFAULT_LLM_PROVIDER", "claude"
                )
                model_override = None

            # Create primary provider
            config_dict = env_manager.get_llm_config(provider_name)

            if provider_name == "claude":
                llm_provider_instance = ClaudeLLMProvider(
                    api_key=config_dict.get("api_key"),
                    base_url=config_dict.get("base_url"),
                )
            elif provider_name == "openai":
                llm_provider_instance = OpenAILLMProvider(
                    api_key=config_dict.get("api_key"),
                    base_url=config_dict.get("base_url"),
                )
            elif provider_name == "gemini":
                llm_provider_instance = GeminiLLMProvider(
                    api_key=config_dict.get("api_key"),
                    base_url=config_dict.get("base_url"),
                )
            elif provider_name == "ollama":
                llm_provider_instance = OllamaLLMProvider(
                    base_url=config_dict.get("base_url")
                )

            # Create fallback provider if specified
            if fallback:
                if fallback == "opus":
                    fallback_name = "claude"
                    fallback_model = "claude-opus-4-20250514"
                elif fallback == "haiku":
                    fallback_name = "claude"
                    fallback_model = "claude-3-5-haiku-20241022"
                else:
                    fallback_name = fallback
                    fallback_model = None

                fallback_config = env_manager.get_llm_config(fallback_name)

                if fallback_name == "claude":
                    fallback_provider_instance = ClaudeLLMProvider(
                        api_key=fallback_config.get("api_key"),
                        base_url=fallback_config.get("base_url"),
                    )
                elif fallback_name == "openai":
                    fallback_provider_instance = OpenAILLMProvider(
                        api_key=fallback_config.get("api_key"),
                        base_url=fallback_config.get("base_url"),
                    )
                elif fallback_name == "gemini":
                    fallback_provider_instance = GeminiLLMProvider(
                        api_key=fallback_config.get("api_key"),
                        base_url=fallback_config.get("base_url"),
                    )
                elif fallback_name == "ollama":
                    fallback_provider_instance = OllamaLLMProvider(
                        base_url=fallback_config.get("base_url")
                    )

        # Create navigator
        async with WebNavigator(
            headless=headless, browser_type=browser
        ) as navigator:

            result = None

            if config:
                # Mode 2: Configuration-based
                console.print(f"[blue]Loading configuration:[/blue] {config}")
                scraping_config = ScrapingConfig.load(Path(config))

                console.print(f"[blue]Task:[/blue] {scraping_config.name}")
                console.print(f"[blue]URL:[/blue] {scraping_config.url}")
                console.print(
                    f"[blue]Actions:[/blue] {len(scraping_config.actions)}"
                )
                console.print()

                with console.status(
                    "[yellow]Executing navigation...[/yellow]", spinner="dots"
                ):
                    result = await navigator.execute_config(scraping_config)

            elif task:
                # Mode 1: Free-form task with LLM
                if not llm_provider_instance:
                    console.print(
                        "[red]Error:[/red] LLM provider required for task-based navigation"
                    )
                    return

                llm_nav = LLMNavigator(
                    llm_provider=llm_provider_instance,
                    navigator=navigator,
                    fallback_provider=fallback_provider_instance,
                    model=model_override,
                    fallback_model=fallback_model if fallback else None,
                )

                console.print(f"[blue]Task:[/blue] {task}")
                console.print(f"[blue]URL:[/blue] {url}")
                console.print(f"[blue]Provider:[/blue] {provider or 'default'}")
                if fallback:
                    console.print(f"[blue]Fallback:[/blue] {fallback}")
                console.print()

                with console.status(
                    "[yellow]Generating navigation plan...[/yellow]",
                    spinner="dots",
                ):
                    save_path = Path(save_config) if save_config else None
                    result = await llm_nav.execute_task(
                        task, url, save_config=save_path
                    )

                if save_config:
                    console.print(
                        f"[green]✓[/green] Configuration saved to: {save_config}"
                    )
                    console.print()

            else:
                console.print(
                    "[red]Error:[/red] Either --task or --config must be provided"
                )
                return

            # Display results
            if result:
                if result.success:
                    console.print(
                        "[green]✓ Navigation completed successfully[/green]"
                    )
                    console.print(
                        f"[blue]Actions executed:[/blue] {result.actions_executed}"
                    )

                    if result.data:
                        console.print()
                        console.print("[blue]Extracted data:[/blue]")

                        data_json = json.dumps(result.data, indent=2)
                        syntax = Syntax(
                            data_json,
                            "json",
                            theme="monokai",
                            line_numbers=False,
                        )
                        panel = Panel(
                            syntax,
                            title="[green]Data[/green]",
                            border_style="green",
                            padding=(1, 2),
                        )
                        console.print(panel)

                        # Save to output file if specified
                        if output:
                            output_path = Path(output)
                            output_path.parent.mkdir(parents=True, exist_ok=True)

                            if output_path.suffix == ".json":
                                with open(output_path, "w") as f:
                                    json.dump(result.data, f, indent=2)
                            elif output_path.suffix == ".yaml":
                                import yaml

                                with open(output_path, "w") as f:
                                    yaml.dump(result.data, f)
                            else:
                                with open(output_path, "w") as f:
                                    json.dump(result.data, f, indent=2)

                            console.print(
                                f"[green]✓[/green] Data saved to: {output}"
                            )

                    if result.screenshots:
                        console.print()
                        console.print("[blue]Screenshots:[/blue]")
                        for screenshot in result.screenshots:
                            console.print(f"  • {screenshot}")

                    if result.metadata:
                        console.print()
                        console.print("[dim]Page metadata:[/dim]")
                        console.print(
                            f"  [dim]Title:[/dim] {result.metadata.get('title', 'N/A')}"
                        )

                else:
                    console.print("[red]✗ Navigation failed[/red]")

                if result.errors:
                    console.print()
                    console.print("[red]Errors:[/red]")
                    for error in result.errors:
                        console.print(f"  • {error}")

    asyncio.run(run_navigation())


@webscraping.command()
def configs():
    """List saved scraping configurations in ~/.aishell/webscraping/configs/."""
    import os
    from pathlib import Path
    from rich.table import Table

    config_dir = Path(os.path.expanduser("~/.aishell/webscraping/configs"))
    if not config_dir.exists():
        console.print("[dim]No saved configurations found.[/dim]")
        console.print(
            f"[dim]Save configs with: aishell webscraping navigate URL --task '...' --save-config NAME.yaml[/dim]"
        )
        return

    yaml_files = sorted(config_dir.glob("*.yaml"))
    if not yaml_files:
        console.print("[dim]No saved configurations found.[/dim]")
        return

    table = Table(title="Saved Scraping Configurations")
    table.add_column("Name", style="cyan")
    table.add_column("File", style="dim")

    for f in yaml_files:
        table.add_row(f.stem, str(f))

    console.print(table)
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
git add aishell/commands/webscraping/cli.py
git commit -m "feat: add webscraping CLI plugin (aishell webscraping navigate)"
```

---

### Task 4: Remove Navigate Command from `cli.py`

**Files:**
- Modify: `aishell/cli.py` — remove lines 1261-1551 (the `@main.command()` for `navigate` and the entire `def navigate(...)` function including its inner `async def run_navigation()`)

- [ ] **Step 1: Remove the navigate command block**

Delete from `aishell/cli.py` the block starting at line 1261 (`@main.command()` before `navigate`) through line 1551 (`asyncio.run(run_navigation())`), inclusive.

The file should go directly from the end of `mcp-convert` command (line 1258: `asyncio.run(run_conversion())`) to line 1554: `from aishell.commands import discover_commands`.

- [ ] **Step 2: Verify the CLI still loads**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
python -m aishell.cli --help
```

Expected: Should show `webscraping` as a subcommand (auto-discovered). Should NOT show `navigate` as a top-level command.

- [ ] **Step 3: Verify the webscraping subcommand works**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
python -m aishell.cli webscraping --help
python -m aishell.cli webscraping navigate --help
```

Expected: Shows navigate subcommand with all options (--task, --config, --provider, etc.).

- [ ] **Step 4: Commit**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
git add aishell/cli.py
git commit -m "refactor: extract navigate command into webscraping plugin"
```

---

### Task 5: Update `.gitignore` and Delete `usecases/`

**Files:**
- Modify: `.gitignore` — update webscraping examples path
- Delete: `usecases/` (entire directory)

- [ ] **Step 1: Update `.gitignore`**

Change:
```
usecases/webscraping/examples/
```
to:
```
aishell/commands/webscraping/examples/
```

- [ ] **Step 2: Delete `usecases/` directory**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
rm -rf usecases/
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
git add -A
git commit -m "chore: remove usecases/ dir (moved to aishell/commands/webscraping/), update gitignore"
```

---

### Task 6: Update CLAUDE.md Directory Structure

**Files:**
- Modify: `CLAUDE.md` — update directory tree and command syntax examples

- [ ] **Step 1: Update the directory tree**

In the `Project Directory Structure` section of CLAUDE.md, remove the `usecases/` entry and add `webscraping/` under `aishell/commands/`:

Under `commands/`:
```
│   ├── commands/                 # Command plugins (auto-discovered)
│   │   ├── __init__.py           # discover_commands() + skill registry
│   │   ├── gemini.py             # Gemini: login, pull, import
│   │   ├── chatgpt.py            # ChatGPT: login, pull, import, reimport
│   │   ├── claude_export.py      # Claude: login, pull, import
│   │   ├── webscraping/          # LLM-assisted web scraping
│   │   │   ├── cli.py            # Click group: navigate, configs
│   │   │   ├── navigator.py      # Playwright navigation engine
│   │   │   ├── llm_navigator.py  # LLM task-to-action translation
│   │   │   ├── actions.py        # Action type definitions
│   │   │   ├── extractors.py     # Data extraction utilities
│   │   │   ├── config.py         # YAML config management
│   │   │   └── examples/         # Example YAML configs (gitignored)
│   │   └── conversations/        # Shared export infrastructure
```

Remove `usecases/` from the tree entirely.

- [ ] **Step 2: Update command examples**

Change all `aishell navigate` references to `aishell webscraping navigate` in CLAUDE.md.

- [ ] **Step 3: Commit**

```bash
cd /Users/nitin/Projects/dirs/github/aishell
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for webscraping command relocation"
```
