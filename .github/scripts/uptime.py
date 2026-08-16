#!/usr/bin/env python3

import os
import re
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

USERNAME = os.environ.get("GITHUB_USERNAME", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
README_PATH = os.environ.get("README_PATH", "README.md")

START_MARKER = "<!--START_SECTION:owl-->"
END_MARKER = "<!--END_SECTION:owl-->"

BUCKETS = [
    ("Morning", "🌞", 6, 12),
    ("Daytime", "🌆", 12, 18),
    ("Evening", "🌃", 18, 24),
    ("Night", "🌙", 0, 6),
]

BAR_WIDTH = 25


def api_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_commit_hours(username):
    hours = []
    for page in range(1, 11):  # search API caps at 1000 results / 100 per page
        url = (
            "https://api.github.com/search/commits"
            f"?q=author:{username}&sort=author-date&order=desc"
            f"&per_page=100&page={page}"
        )
        try:
            data = api_get(url)
        except urllib.error.HTTPError as e:
            print(f"Search API error on page {page}: {e}", file=sys.stderr)
            break

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            date_str = item["commit"]["author"]["date"]
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            hours.append(dt.hour)

        if len(items) < 100:
            break

    return hours


def bucket_counts(hours):
    counts = {name: 0 for name, *_ in BUCKETS}
    for h in hours:
        for name, _, start, end in BUCKETS:
            if start <= h < end:
                counts[name] += 1
                break
    return counts


def render_block(counts):
    total = sum(counts.values())
    lines = []
    for name, emoji, *_ in BUCKETS:
        count = counts[name]
        pct = (count / total * 100) if total else 0.0
        filled = round(pct / 100 * BAR_WIDTH)
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        lines.append(
            f"{emoji} {name:<9} {count:>4} commits     {bar}   {pct:.2f}%"
        )
    return "\n".join(lines)


def update_readme(block_text):
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print(
            f"Markers {START_MARKER} / {END_MARKER} not found in {README_PATH} — "
            "add them around the code block you want auto-updated.",
            file=sys.stderr,
        )
        sys.exit(1)

    new_section = f"{START_MARKER}\n```text\n{block_text}\n```\n{END_MARKER}"
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

    hours = fetch_commit_hours(USERNAME)
    if not hours:
        print("No commits found (or Search API returned nothing) — leaving README untouched.")
        sys.exit(0)

    counts = bucket_counts(hours)
    block = render_block(counts)
    update_readme(block)
    print(f"Updated {README_PATH} from {len(hours)} commits.")
    print(block)


if __name__ == "__main__":
    main()
