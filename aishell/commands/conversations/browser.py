"""Shared Chrome/CDP browser automation helpers.

Provides Chrome lifecycle management, authenticated fetch via page.evaluate(),
and login flow helpers used by Gemini, ChatGPT, and Claude export commands.
"""

import json
import logging
import os
import socket
import subprocess
import time

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

CHROME_USER_DATA_DIR = os.path.expanduser("~/chromeuserdata")
CHROME_DEBUG_PORT = 9222
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# ── Chrome lifecycle helpers ─────────────────────────────────────────


def is_debug_port_open(port=CHROME_DEBUG_PORT):
    """Check if Chrome's CDP port is listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def chrome_quit():
    """Gracefully quit Chrome via AppleScript."""
    subprocess.run(
        ["osascript", "-e", 'tell application "Google Chrome" to quit'],
        capture_output=True,
    )
    for _ in range(10):
        time.sleep(1)
        check = subprocess.run(["pgrep", "-f", "Google Chrome"], capture_output=True)
        if check.returncode != 0:
            break
    time.sleep(1)


def chrome_launch(port=CHROME_DEBUG_PORT):
    """Launch Chrome with remote debugging. Returns Popen or None if reusing."""
    if is_debug_port_open(port):
        logger.info(f"Chrome debug port {port} already open, reusing")
        return None

    # Quit Chrome if running without debug port
    result = subprocess.run(["pgrep", "-f", "Google Chrome"], capture_output=True)
    if result.returncode == 0:
        logger.info("Chrome running without debug port — quitting it gracefully...")
        chrome_quit()

    proc = subprocess.Popen(
        [
            CHROME_PATH,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={CHROME_USER_DATA_DIR}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info(f"Chrome launched (pid={proc.pid}), waiting for debug port...")

    for _ in range(15):
        time.sleep(1)
        if is_debug_port_open(port):
            logger.info(f"Debug port {port} ready")
            return proc

    logger.warning(f"Debug port {port} not responding after 15s, proceeding anyway")
    return proc


def chrome_login(url, message, console):
    """Launch Chrome for manual sign-in, wait for user to close it.

    Args:
        url: The URL to open (e.g. "https://chatgpt.com")
        message: Instructions shown to the user (e.g. "Sign into ChatGPT...")
        console: Rich Console instance for output
    """
    console.print(f"[blue]Launching Chrome for sign-in...[/blue]")

    # Quit existing Chrome
    result = subprocess.run(["pgrep", "-f", "Google Chrome"], capture_output=True)
    if result.returncode == 0:
        console.print("[yellow]Quitting existing Chrome...[/yellow]")
        chrome_quit()

    proc = subprocess.Popen(
        [
            CHROME_PATH,
            f"--remote-debugging-port={CHROME_DEBUG_PORT}",
            f"--user-data-dir={CHROME_USER_DATA_DIR}",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    console.print(f"[green]Chrome launched (pid={proc.pid})[/green]")
    console.print(f"  User data dir: {CHROME_USER_DATA_DIR}")
    console.print(f"  Debug port:    {CHROME_DEBUG_PORT}")
    console.print()
    console.print(message)
    console.print("[dim]Waiting for Chrome to exit...[/dim]")

    proc.wait()
    console.print("[green]Chrome closed. Login session saved.[/green]")


# ── Authenticated fetch helpers ──────────────────────────────────────


def check_auth(page, indicators):
    """Check if the current page URL indicates an auth redirect.

    Args:
        page: Playwright page instance
        indicators: List of URL substrings that indicate auth failure
            (e.g. ["auth0.com", "login.openai.com", "/auth/"])

    Returns:
        True if authenticated (no indicators matched), False otherwise.
    """
    current_url = page.url.lower()
    for indicator in indicators:
        if indicator.lower() in current_url:
            return False
    return True


def fetch_json(page, url, headers=None):
    """Execute fetch() inside the browser page context with inherited cookies.

    Runs a JS fetch() call that inherits the page's authentication cookies,
    session headers, and CSRF tokens. Returns parsed JSON.

    Args:
        page: Playwright page instance (must be on the target domain)
        url: API endpoint URL (absolute)
        headers: Optional dict of extra headers to include

    Returns:
        Parsed JSON response (dict or list)

    Raises:
        RuntimeError: On HTTP errors (401 → auth error, 429 → rate limit, etc.)
    """
    headers_js = json.dumps(headers or {})

    result = page.evaluate(
        """async ([url, extraHeaders]) => {
        try {
            const opts = {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json',
                    ...JSON.parse(extraHeaders)
                }
            };
            const resp = await fetch(url, opts);
            if (!resp.ok) {
                return {
                    __error: true,
                    status: resp.status,
                    statusText: resp.statusText,
                    body: await resp.text().catch(() => '')
                };
            }
            const data = await resp.json();
            return { __error: false, data: data };
        } catch (e) {
            return { __error: true, status: 0, statusText: e.message, body: '' };
        }
    }""",
        [url, headers_js],
    )

    if result.get("__error"):
        status = result.get("status", 0)
        status_text = result.get("statusText", "Unknown error")
        if status == 401 or status == 403:
            raise RuntimeError(
                f"Authentication failed ({status} {status_text}). "
                "Run the login command first."
            )
        elif status == 429:
            raise RuntimeError(
                f"Rate limited ({status} {status_text}). "
                "Try again later or increase --delay."
            )
        else:
            body_preview = result.get("body", "")[:200]
            raise RuntimeError(
                f"API error: {status} {status_text}"
                + (f"\n{body_preview}" if body_preview else "")
            )

    return result["data"]
