"""Probe ChatGPT's internal API to discover project-related endpoints.

Uses raw Chrome DevTools Protocol (CDP) over WebSocket — no Playwright node
driver needed. Connects to an already-running Chrome on port 9222.

Usage:
    python scripts/probe_chatgpt_projects.py

Prerequisite:
    Chrome running with --remote-debugging-port=9222 --remote-allow-origins=*
    User logged into chatgpt.com
"""

import json
import time
import requests
import websocket

PROJECT_GIZMO_ID = "g-p-69c309f7d2a8819190d7072a0672a5a9"
API_BASE = "https://chatgpt.com/backend-api"

ENDPOINTS = [
    # High probability - gizmo-based
    ("/gizmos/discovery/mine", "User's gizmos (may include projects)"),
    (f"/gizmos/{PROJECT_GIZMO_ID}", "Project detail as gizmo"),
    (
        f"/conversations?gizmo_id={PROJECT_GIZMO_ID}&offset=0&limit=5&order=updated",
        "Conversations filtered by project gizmo ID",
    ),
    # Medium probability
    ("/gizmos", "All gizmos"),
    ("/gizmos/mine", "User's own gizmos"),
    ("/gpts/mine", "User's GPTs"),
    ("/projects", "Dedicated projects endpoint"),
    # Lower probability
    ("/workspaces", "Workspaces"),
    ("/folders", "Folders"),
    ("/collections", "Collections"),
    # Gizmo discovery variants
    ("/gizmos/discovery", "Gizmo discovery main"),
    ("/gizmos/discovery/mine?limit=100", "Gizmo discovery mine with limit"),
    # Project-specific sub-resources
    (f"/gizmos/{PROJECT_GIZMO_ID}/project", "Project sub-resource on gizmo"),
    (f"/gizmos/{PROJECT_GIZMO_ID}/files", "Files attached to project gizmo"),
    (f"/gizmos/{PROJECT_GIZMO_ID}/conversations", "Conversations on project gizmo"),
]


class CDPSession:
    """Minimal Chrome DevTools Protocol client over WebSocket."""

    def __init__(self, port=9222):
        # Find a chatgpt.com page target
        targets = requests.get(f"http://127.0.0.1:{port}/json").json()
        chatgpt_targets = [t for t in targets if "chatgpt.com" in t.get("url", "")]
        if not chatgpt_targets:
            raise RuntimeError(
                f"No chatgpt.com page found. Available: "
                + ", ".join(t.get("url", "?")[:60] for t in targets)
            )

        target = chatgpt_targets[0]
        print(f"    Target page: {target['url'][:80]}")

        self.ws = websocket.create_connection(target["webSocketDebuggerUrl"])
        self._msg_id = 0

    def evaluate(self, expression):
        """Run JS expression in the page and return the result value."""
        self._msg_id += 1
        self.ws.send(
            json.dumps(
                {
                    "id": self._msg_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                }
            )
        )

        # Read until we get the response for our message ID
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._msg_id:
                result = msg.get("result", {}).get("result", {})
                if result.get("type") == "undefined":
                    return None
                return result.get("value")

    def close(self):
        self.ws.close()


def describe_structure(text):
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            desc = {}
            for k, v in data.items():
                if isinstance(v, list):
                    desc[k] = f"list[{len(v)}]"
                    if v and isinstance(v[0], dict):
                        desc[k] += f" keys={list(v[0].keys())[:8]}"
                elif isinstance(v, dict):
                    desc[k] = f"dict({', '.join(list(v.keys())[:5])})"
                elif isinstance(v, str) and len(v) > 50:
                    desc[k] = f"str({len(v)} chars)"
                else:
                    desc[k] = repr(v)
            return desc
        elif isinstance(data, list):
            s = f"list of {len(data)} items"
            if data and isinstance(data[0], dict):
                s += f", first item keys: {list(data[0].keys())[:8]}"
            return s
        return repr(type(data))
    except Exception:
        return None


def main():
    print("=" * 70)
    print("ChatGPT Project API Endpoint Probe")
    print("=" * 70)

    print("\n[1] Connecting to Chrome CDP on port 9222...")
    try:
        cdp = CDPSession(port=9222)
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nMake sure Chrome is running with:")
        print("  --remote-debugging-port=9222 --remote-allow-origins=*")
        return

    print("[2] Fetching access token...")
    token = cdp.evaluate(
        """(async () => {
        try {
            const resp = await fetch('/api/auth/session', {credentials: 'include'});
            if (!resp.ok) return null;
            const data = await resp.json();
            return data.accessToken || null;
        } catch(e) { return null; }
    })()"""
    )

    if not token:
        print("ERROR: Could not get access token. Is Chrome logged into ChatGPT?")
        cdp.close()
        return
    print(f"    Token: {token[:20]}...{token[-10:]}")

    successes = []
    print(f"\n[3] Probing {len(ENDPOINTS)} endpoints...\n")

    for path, description in ENDPOINTS:
        url = API_BASE + path
        print(f">>> {path}")
        print(f"    ({description})")

        result = cdp.evaluate(
            """(async () => {
            try {
                const resp = await fetch('"""
            + url
            + """', {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json',
                        'Authorization': 'Bearer """
            + token
            + """'
                    }
                });
                const text = await resp.text();
                return JSON.stringify({status: resp.status, statusText: resp.statusText, body: text});
            } catch (e) {
                return JSON.stringify({status: 0, statusText: e.message, body: ''});
            }
        })()"""
        )

        parsed = json.loads(result)
        status = parsed["status"]
        body = parsed.get("body", "")

        if status == 200:
            print(f"    STATUS: {status} OK  <<<< SUCCESS")
            structure = describe_structure(body)
            if structure:
                print(f"    STRUCTURE: {json.dumps(structure, indent=6)}")
            try:
                pretty = json.dumps(json.loads(body), indent=2)
                print(f"    PREVIEW:\n{pretty[:800]}")
                if len(pretty) > 800:
                    print("    ... (truncated)")
            except (json.JSONDecodeError, TypeError):
                print(f"    BODY: {body[:800]}")
            successes.append((path, description, body))
        elif status == 0:
            print(f"    STATUS: NETWORK ERROR - {parsed.get('statusText', '?')}")
        else:
            print(f"    STATUS: {status} {parsed.get('statusText', '')}")

        print()
        time.sleep(0.5)

    print("=" * 70)
    print(f"SUMMARY: {len(successes)}/{len(ENDPOINTS)} endpoints returned 200")
    print("=" * 70)
    for path, description, body in successes:
        print(f"  OK  {path}")
        print(f"       {description}")

    cdp.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
