#!/usr/bin/env python3
"""Install Playwright browsers."""

import subprocess
import sys
from rich.console import Console

console = Console()


def install_playwright_browsers():
    """Install Playwright browsers (Chromium, Firefox, WebKit)."""
    console.print("[bold green]Installing Playwright browsers...[/bold green]")
    
    try:
        # Install playwright browsers
        subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)
        console.print("[green]✓ Playwright browsers installed successfully![/green]")
        
        # Install system dependencies if needed
        console.print("\n[yellow]Note: If you encounter issues, you may need to install system dependencies:[/yellow]")
        console.print("[dim]For Ubuntu/Debian: sudo playwright install-deps[/dim]")
        console.print("[dim]For other systems, check Playwright documentation[/dim]")
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed to install Playwright browsers: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    install_playwright_browsers()