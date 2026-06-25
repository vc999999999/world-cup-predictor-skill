#!/usr/bin/env python3
"""Fetch head-to-head national team records from 11v11.com.

Provides historical matchup statistics between two national teams:
total matches, wins/draws/losses, goal averages, recent form, and
a trend summary.  Particularly valuable for weaker teams where
club-level data is unavailable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.11v11.com"
SEARCH_URL = f"{BASE_URL}/teams/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Referer": BASE_URL,
}


class FetchError(RuntimeError):
    pass


def fetch_text(url: str, timeout: float = 30.0, retries: int = 2, pause: float = 3.0) -> str:
    last_error: Exception | None = None
    session = requests.Session()
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(pause)
        try:
            response = session.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
    raise FetchError(f"Failed to fetch {url}: {last_error}") from last_error


def to_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("+", "")
    if not text or text in ("-", "n/a"):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def find_team_url(team_name: str, timeout: float = 30.0) -> str | None:
    """Search 11v11.com for a national team and return its URL."""
    search_query = quote_plus(team_name)
    search_page_url = f"{BASE_URL}/teams/{search_query}"
    try:
        html = fetch_text(search_page_url, timeout=timeout)
    except FetchError:
        return None

    soup = BeautifulSoup(html, "lxml")

    # Look for links to team pages
    for link in soup.select("a[href*='/teams/']"):
        href = link.get("href", "")
        link_text = link.get_text(strip=True)
        if team_name.lower() in link_text.lower() and "/teams/" in href and href != "/teams/":
            if not href.startswith("http"):
                href = f"{BASE_URL}{href}"
            return href

    # Try direct URL pattern
    slug = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")
    direct_url = f"{BASE_URL}/teams/{slug}"
    try:
        fetch_text(direct_url, timeout=timeout, retries=0)
        return direct_url
    except FetchError:
        pass

    return None


def parse_h2h_page(html: str, home: str, away: str) -> list[dict[str, Any]]:
    """Parse the H2H results page into a list of match records."""
    soup = BeautifulSoup(html, "lxml")
    matches = []

    # Strategy 1: look for match result tables
    tables = soup.select("table")
    for table in tables:
        rows = table.select("tbody tr, tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            texts = [cell.get_text(strip=True) for cell in cells]
            match_record = _parse_h2h_row(texts, home, away)
            if match_record:
                matches.append(match_record)

    # Strategy 2: look for structured divs
    if not matches:
        for div in soup.select('[class*="match"], [class*="result"], [class*="fixture"]'):
            text = div.get_text(" ", strip=True)
            match_record = _parse_match_text(text, home, away)
            if match_record:
                matches.append(match_record)

    # Strategy 3: look for score patterns in the full page
    if not matches:
        matches = _extract_scores_from_page(soup, home, away)

    return matches


def _parse_h2h_row(texts: list[str], home: str, away: str) -> dict[str, Any] | None:
    """Try to parse a single H2H row from cell texts."""
    date = None
    score = None
    competition = ""
    home_goals = None
    away_goals = None
    venue = ""

    for text in texts:
        # Date pattern
        date_match = re.match(r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})", text)
        if date_match and not date:
            date = date_match.group(1)
            continue

        # Score pattern: "2-1", "2:1", "2 - 1"
        score_match = re.match(r"(\d+)\s*[-:–]\s*(\d+)", text)
        if score_match and score is None:
            home_goals = int(score_match.group(1))
            away_goals = int(score_match.group(2))
            score = f"{home_goals}-{away_goals}"
            continue

        # Competition keywords
        comp_keywords = [
            "World Cup", "FIFA", "friendly", "Qualifier", "Championship",
            "Copa", "Euro", "Asian Cup", "Nations League", "Gold Cup",
            "Africa Cup", "Confederation",
        ]
        if any(kw.lower() in text.lower() for kw in comp_keywords) and not competition:
            competition = text
            continue

    if home_goals is not None and away_goals is not None:
        # Determine winner
        if home_goals > away_goals:
            winner = "home"
        elif away_goals > home_goals:
            winner = "away"
        else:
            winner = "draw"

        return {
            "date": date,
            "score": score,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "winner": winner,
            "competition": competition,
            "venue": venue,
        }
    return None


def _parse_match_text(text: str, home: str, away: str) -> dict[str, Any] | None:
    """Try to parse a match from unstructured text."""
    # Look for score pattern
    score_match = re.search(r"(\d+)\s*[-:–]\s*(\d+)", text)
    if not score_match:
        return None

    home_goals = int(score_match.group(1))
    away_goals = int(score_match.group(2))

    # Look for date
    date_match = re.search(r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})", text)
    date = date_match.group(1) if date_match else None

    winner = "home" if home_goals > away_goals else ("away" if away_goals > home_goals else "draw")

    return {
        "date": date,
        "score": f"{home_goals}-{away_goals}",
        "home_goals": home_goals,
        "away_goals": away_goals,
        "winner": winner,
        "competition": "",
        "venue": "",
    }


def _extract_scores_from_page(soup: BeautifulSoup, home: str, away: str) -> list[dict[str, Any]]:
    """Last-resort extraction: find all score-like patterns on the page."""
    matches = []
    text = soup.get_text("\n", strip=True)
    for line in text.split("\n"):
        score_match = re.search(r"(\d+)\s*[-:–]\s*(\d+)", line.strip())
        if score_match:
            home_goals = int(score_match.group(1))
            away_goals = int(score_match.group(2))
            date_match = re.search(r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})", line)
            matches.append({
                "date": date_match.group(1) if date_match else None,
                "score": f"{home_goals}-{away_goals}",
                "home_goals": home_goals,
                "away_goals": away_goals,
                "winner": "home" if home_goals > away_goals else ("away" if away_goals > home_goals else "draw"),
                "competition": "",
                "venue": "",
            })
    return matches


def compute_h2h_summary(
    matches: list[dict[str, Any]],
    recent_years: int | None = None,
) -> dict[str, Any]:
    """Compute aggregate H2H statistics from match records."""
    if not matches:
        return {
            "total_matches": 0,
            "home_wins": 0, "draws": 0, "away_wins": 0,
            "home_goals_total": 0, "away_goals_total": 0,
            "home_goals_avg": 0, "away_goals_avg": 0,
            "goal_total_avg": 0,
            "recent_5": [],
            "trend": "insufficient_data",
        }

    # Filter by recent years if requested
    filtered = matches
    if recent_years:
        current_year = datetime.now().year
        cutoff = current_year - recent_years
        filtered = []
        for match in matches:
            if match.get("date"):
                # Try to extract year from date
                year_match = re.search(r"(\d{4})$", str(match["date"]))
                if not year_match:
                    year_match = re.search(r"(\d{2})$", str(match["date"]))
                    if year_match:
                        year_short = int(year_match.group(1))
                        year = 2000 + year_short if year_short < 50 else 1900 + year_short
                    else:
                        filtered.append(match)  # keep if can't parse
                        continue
                else:
                    year = int(year_match.group(1))
                if year >= cutoff:
                    filtered.append(match)
            else:
                filtered.append(match)  # keep if no date

    if not filtered:
        filtered = matches  # fallback to all if filter removed everything

    home_wins = sum(1 for m in filtered if m["winner"] == "home")
    away_wins = sum(1 for m in filtered if m["winner"] == "away")
    draws = sum(1 for m in filtered if m["winner"] == "draw")
    total = len(filtered)

    home_goals_total = sum(m["home_goals"] for m in filtered)
    away_goals_total = sum(m["away_goals"] for m in filtered)

    # Recent 5 matches (most recent first)
    recent_5 = filtered[:5] if len(filtered) >= 5 else filtered[:]

    # Trend analysis
    if total < 3:
        trend = "insufficient_data"
    else:
        home_rate = home_wins / total
        away_rate = away_wins / total
        if home_rate > 0.6:
            trend = "home_dominant"
        elif away_rate > 0.6:
            trend = "away_dominant"
        elif home_rate > away_rate + 0.15:
            trend = "home_slight_edge"
        elif away_rate > home_rate + 0.15:
            trend = "away_slight_edge"
        else:
            trend = "balanced"

    return {
        "total_matches": total,
        "home_wins": home_wins,
        "draws": draws,
        "away_wins": away_wins,
        "home_goals_total": home_goals_total,
        "away_goals_total": away_goals_total,
        "home_goals_avg": round(home_goals_total / total, 2) if total else 0,
        "away_goals_avg": round(away_goals_total / total, 2) if total else 0,
        "goal_total_avg": round((home_goals_total + away_goals_total) / total, 2) if total else 0,
        "recent_5": recent_5,
        "trend": trend,
    }


def fetch_h2h(
    home: str,
    away: str,
    recent_years: int | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Full H2H fetch pipeline: find team URLs, fetch page, parse, summarize."""
    # Try to find the H2H page
    # 11v11.com pattern: /teams/{home}/v/{away}
    home_slug = re.sub(r"[^a-z0-9]+", "-", home.lower()).strip("-")
    away_slug = re.sub(r"[^a-z0-9]+", "-", away.lower()).strip("-")

    # Try direct H2H URL
    h2h_url = f"{BASE_URL}/teams/{home_slug}/against/{away_slug}"
    alt_urls = [
        f"{BASE_URL}/teams/{home_slug}/v/{away_slug}",
        f"{BASE_URL}/teams/{home_slug}/head-to-head/{away_slug}",
    ]

    matches = []
    used_url = None

    for url in [h2h_url] + alt_urls:
        try:
            html = fetch_text(url, timeout=timeout)
            matches = parse_h2h_page(html, home, away)
            if matches:
                used_url = url
                break
        except FetchError:
            continue

    # Fallback: try to find team page and navigate
    if not matches:
        home_url = find_team_url(home, timeout=timeout)
        if home_url:
            # Try the against/h2h pattern from the actual team URL
            h2h_candidates = [
                home_url.replace("/teams/", f"/teams/{home_slug}/against/{away_slug}"),
                f"{home_url}/against/{away_slug}",
                f"{home_url}/h2h/{away_slug}",
            ]
            for url in h2h_candidates:
                try:
                    html = fetch_text(url, timeout=timeout)
                    matches = parse_h2h_page(html, home, away)
                    if matches:
                        used_url = url
                        break
                except FetchError:
                    continue

    summary = compute_h2h_summary(matches, recent_years=recent_years)

    return {
        "source": "11v11.com",
        "sourceUrl": used_url or h2h_url,
        "retrievedAt": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "home": home,
        "away": away,
        "matches_found": len(matches),
        **summary,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch head-to-head national team records."
    )
    parser.add_argument("--home", required=True, help="Home team name.")
    parser.add_argument("--away", required=True, help="Away team name.")
    parser.add_argument(
        "--recent-years",
        type=int,
        default=None,
        help="Only include matches from the last N years.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        result = fetch_h2h(
            home=args.home,
            away=args.away,
            recent_years=args.recent_years,
            timeout=args.timeout,
        )
    except FetchError as exc:
        print(f"[h2h] failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
