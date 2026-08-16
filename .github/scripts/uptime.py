#!/usr/bin/env python3
"""
Pulls the account's real `created_at` date from the GitHub Users API and
rewrites the "days on GitHub" line between the START_SECTION:uptime /
END_SECTION:uptime markers in README.md.

Env vars required:
  GITHUB_TOKEN     - provided automatically by Actions
  GITHUB_USERNAME  - the account to check

Note: this counts days since the GitHub account was created, not since you
started coding or learning - it's the only date GitHub's API can give us
without you maintaining a separate "start date" by hand.
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
README_PATH = os.environ.get("README_PATH", "README.md")

START_MARKER = "<!--START_SECTION:uptime-->"
END_MARKER = "<!--END_SECTION:uptime-->"


def fetch_created_at(username):
    req = urllib.request.Request(f"https://api.github.com/users/{username}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    return data["created_at"]


def render_line(created_at_str):
    created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    days = (now - created).days
    return f"`day {days}` on GitHub · joined {created.strftime('%b %Y')}"


def update_readme(line_text):
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print(
            f"Markers {START_MARKER} / {END_MARKER} not found in {README_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)

    new_section = f"{START_MARKER}\n{line_text}\n{END_MARKER}"
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
    )
    updated = pattern.sub(new_section, content)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(updated)


def main():
    if not USERNAME:
        print("GITHUB_USERNAME env var is required", file=sys.stderr)
        sys.exit(1)

    try:
        created_at = fetch_created_at(USERNAME)
    except urllib.error.HTTPError as e:
        print(f"Users API error: {e}", file=sys.stderr)
        sys.exit(1)

    line = render_line(created_at)
    update_readme(line)
    print(f"Updated {README_PATH}: {line}")


if __name__ == "__main__":
    main()
