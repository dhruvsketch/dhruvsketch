#!/usr/bin/env python3
"""
Pulls real data from the GitHub API for a single user and:
  1. Builds a plain-text ASCII bar chart of commit activity by hour (IST),
     based on actual push events - no invented numbers.
  2. Builds a small custom SVG stats card (repo count, followers, top
     languages by bytes) styled to match the profile's own color system.
  3. Writes both into README.md between marker comments.

Runs on a schedule via .github/workflows/update-metrics.yml.
"""

import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta

USERNAME = "dhruvsketch"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
IST = timezone(timedelta(hours=5, minutes=30))

IVORY = "#F6F2EA"
CHARCOAL = "#1B1B1B"
ACCENT = "#00D9A3"

API_ROOT = "https://api.github.com"


def api_get(path):
    req = urllib.request.Request(f"{API_ROOT}{path}")
    req.add_header("User-Agent", USERNAME)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def get_push_hours():
    """Approximate commit-time-of-day from public push events (last ~300)."""
    hours = []
    for page in (1, 2, 3):
        try:
            events = api_get(f"/users/{USERNAME}/events/public?per_page=100&page={page}")
        except Exception:
            break
        if not events:
            break
        for e in events:
            if e.get("type") == "PushEvent":
                ts = e.get("created_at")
                if ts:
                    utc_dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    ist_dt = utc_dt.astimezone(IST)
                    hours.append(ist_dt.hour)
    return hours


def render_ascii_clock(hours):
    if not hours:
        return "No public push activity found yet — this fills in as commits happen."

    counts = Counter(hours)
    max_count = max(counts.values())
    lines = []
    for h in range(24):
        c = counts.get(h, 0)
        bar_len = round((c / max_count) * 24) if max_count else 0
        bar = "█" * bar_len
        label = f"{h:02d}:00"
        lines.append(f"{label}  {bar}  {c}")

    peak_hour = max(counts, key=counts.get)
    header = f"Most active around {peak_hour:02d}:00 IST (based on last {len(hours)} public pushes)\n\n"
    return header + "\n".join(lines)


def get_language_totals():
    totals = Counter()
    page = 1
    while page <= 5:
        repos = api_get(f"/users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
        if not repos:
            break
        for repo in repos:
            if repo.get("fork"):
                continue
            try:
                langs = api_get(f"/repos/{USERNAME}/{repo['name']}/languages")
            except Exception:
                continue
            for lang, byte_count in langs.items():
                totals[lang] += byte_count
        page += 1
    return totals


def get_profile():
    return api_get(f"/users/{USERNAME}")


def render_stats_svg(profile, lang_totals):
    top_langs = lang_totals.most_common(5)
    total_bytes = sum(lang_totals.values()) or 1

    rows = []
    y = 100
    for lang, byte_count in top_langs:
        pct = byte_count / total_bytes * 100
        bar_w = round(pct * 3.2)
        rows.append(
            f'<text x="30" y="{y}" font-family="Menlo, Consolas, monospace" '
            f'font-size="13" fill="{CHARCOAL}">{lang}</text>'
            f'<rect x="150" y="{y-12}" width="{bar_w}" height="12" fill="{ACCENT}"/>'
            f'<text x="{160+bar_w}" y="{y}" font-family="Menlo, Consolas, monospace" '
            f'font-size="12" fill="{CHARCOAL}" opacity="0.7">{pct:.1f}%</text>'
        )
        y += 30

    svg = f'''<svg width="100%" viewBox="0 0 500 {y+20}" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="GitHub stats: {profile.get('public_repos', 0)} public repos, {profile.get('followers', 0)} followers, top languages by bytes written.">
  <rect width="500" height="{y+20}" rx="8" fill="{IVORY}" stroke="{CHARCOAL}" stroke-width="1"/>
  <text x="30" y="34" font-family="Georgia, serif" font-size="16" fill="{CHARCOAL}">Repo Stats</text>
  <text x="30" y="60" font-family="Menlo, Consolas, monospace" font-size="13" fill="{CHARCOAL}">
    public repos: {profile.get('public_repos', 0)}  ·  followers: {profile.get('followers', 0)}
  </text>
  <line x1="30" y1="72" x2="470" y2="72" stroke="{CHARCOAL}" stroke-width="0.5" opacity="0.4"/>
  {''.join(rows)}
</svg>'''
    return svg


def update_readme(readme_path, clock_text, stats_generated_note):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    clock_block = f"<!--CODING-CLOCK:START-->\n```text\n{clock_text}\n```\n<!--CODING-CLOCK:END-->"
    content = re.sub(
        r"<!--CODING-CLOCK:START-->.*?<!--CODING-CLOCK:END-->",
        clock_block,
        content,
        flags=re.DOTALL,
    )

    stamp_block = f"<!--METRICS-UPDATED:START-->_Last updated {stats_generated_note} UTC_<!--METRICS-UPDATED:END-->"
    content = re.sub(
        r"<!--METRICS-UPDATED:START-->.*?<!--METRICS-UPDATED:END-->",
        stamp_block,
        content,
        flags=re.DOTALL,
    )

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    profile = get_profile()
    hours = get_push_hours()
    clock_text = render_ascii_clock(hours)

    lang_totals = get_language_totals()
    stats_svg = render_stats_svg(profile, lang_totals)

    with open("assets/stats.svg", "w", encoding="utf-8") as f:
        f.write(stats_svg)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    update_readme("README.md", clock_text, now)

    print("Updated assets/stats.svg and README.md coding-clock section.")


if __name__ == "__main__":
    main()
