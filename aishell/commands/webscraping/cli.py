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

    \b
    1. Free-form task (LLM translates to actions):
       aishell webscraping navigate https://example.com --task "Extract all product prices"

    \b
    2. Configuration-based (reusable patterns):
       aishell webscraping navigate --config home_loans.yaml

    \b
    3. Task variations with fallback:
       aishell webscraping navigate https://example.com --task "Get loan rates" --provider haiku --fallback opus
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
            console.print(f"[red]Error:[/red] Configuration file not found: {config}")
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
        async with WebNavigator(headless=headless, browser_type=browser) as navigator:

            result = None

            if config:
                # Mode 2: Configuration-based
                console.print(f"[blue]Loading configuration:[/blue] {config}")
                scraping_config = ScrapingConfig.load(Path(config))

                console.print(f"[blue]Task:[/blue] {scraping_config.name}")
                console.print(f"[blue]URL:[/blue] {scraping_config.url}")
                console.print(f"[blue]Actions:[/blue] {len(scraping_config.actions)}")
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
                    console.print("[green]✓ Navigation completed successfully[/green]")
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

                            console.print(f"[green]✓[/green] Data saved to: {output}")

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
