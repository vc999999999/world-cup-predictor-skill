#!/usr/bin/env python3
"""Fetch FIFA Men's World Ranking and EA FC national team ratings.

Dual-mode fetcher:
- ``ranking`` mode: scrapes the official FIFA Men's World Ranking page for
  rank, team name, confederation, ranking points, and rank change.
- ``eafc`` mode: scrapes sofifa.com for EA FC (formerly FIFA game) national
  team ratings — overall, attack, midfield, defence — which serve as a
  structured strength proxy for teams with sparse real-match data.

Both modes output compact JSON.  The ``--matchup`` flag accepts a
``"Team A vs Team B"`` string and fetches profiles for both teams.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FIFA_RANKING_URL = "https://www.fifa.com/fifa-world-ranking/men"
SOFAIFA_TEAMS_URL = "https://sofifa.com/teams?type=national"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}


class FetchError(RuntimeError):
    pass


def fetch_text(url: str, timeout: float = 30.0, retries: int = 2, pause: float = 3.0,
               extra_headers: dict | None = None) -> str:
    last_error: Exception | None = None
    session = requests.Session()
    headers = {**HEADERS, **(extra_headers or {})}
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(pause)
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
    raise FetchError(f"Failed to fetch {url}: {last_error}") from last_error


def fetch_json(url: str, timeout: float = 30.0, retries: int = 2, pause: float = 3.0,
               extra_headers: dict | None = None) -> Any:
    last_error: Exception | None = None
    session = requests.Session()
    headers = {**HEADERS, "Accept": "application/json", **(extra_headers or {})}
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(pause)
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last_error = exc
    raise FetchError(f"Failed to fetch JSON from {url}: {last_error}") from last_error


def to_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("+", "").replace("\u2013", "-")
    if not text or text in ("-", "n/a", "N/A"):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_matchup(matchup: str) -> list[str]:
    """Parse 'Team A vs Team B' or 'Team A vs. Team B' into a list of team names."""
    parts = re.split(r"\s+vs\.?\s+", matchup, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


# ---------------------------------------------------------------------------
# FIFA Ranking mode
# ---------------------------------------------------------------------------

def _try_fifa_api(timeout: float) -> list[dict[str, Any]] | None:
    """Try the FIFA internal API for ranking data."""
    api_urls = [
        "https://www.fifa.com/api/ranking-overview?id=fifa-world-ranking-men",
        "https://www.fifa.com/fifa-world-ranking/s/men?dateId=id13603",
    ]
    for url in api_urls:
        try:
            data = fetch_json(url, timeout=timeout)
            if isinstance(data, dict) and "ranking" in str(data).lower():
                return _parse_fifa_api_response(data)
        except FetchError:
            continue
    return None


def _parse_fifa_api_response(data: Any) -> list[dict[str, Any]] | None:
    """Parse FIFA API ranking response. Structure varies; adapt as needed."""
    results = []
    # Try common response shapes
    entries = []
    if isinstance(data, dict):
        for key in ("rankings", "data", "result", "entries"):
            if key in data and isinstance(data[key], list):
                entries = data[key]
                break
    if isinstance(data, list):
        entries = data

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        team_name = (
            entry.get("teamName") or entry.get("team") or entry.get("name")
            or entry.get("countryName") or ""
        )
        if not team_name:
            continue
        results.append({
            "rank": to_number(entry.get("rank") or entry.get("position")),
            "team": team_name,
            "confederation": entry.get("confederation") or entry.get("confed") or "",
            "points": to_number(entry.get("points") or entry.get("totalPoints")),
            "rank_change": to_number(entry.get("rankChange") or entry.get("change")),
            "source": "FIFA",
        })
    return results if results else None


def _parse_fifa_html(html: str) -> list[dict[str, Any]]:
    """Parse FIFA ranking from the HTML page."""
    soup = BeautifulSoup(html, "lxml")
    results = []

    # Strategy 1: look for ranking table
    tables = soup.select("table")
    for table in tables:
        rows = table.select("tbody tr, tr")
        for row in rows:
            cells = row.select("td, th")
            if len(cells) < 3:
                continue
            texts = [cell.get_text(strip=True) for cell in cells]
            # Try to identify rank (number), team name, points (number)
            rank = None
            team = None
            points = None
            confederation = ""
            rank_change = None

            for text in texts:
                num = to_number(text)
                if num is not None and rank is None and num == int(num) and 1 <= num <= 250:
                    rank = int(num)
                elif num is not None and rank is not None and team and points is None and num > 100:
                    points = num
                elif team is None and not text.replace(" ", "").replace("-", "").isdigit():
                    if len(text) > 2 and not text.startswith(("Rank", "Team", "Points", "Conf")):
                        team = text

            if rank and team:
                results.append({
                    "rank": rank,
                    "team": team,
                    "confederation": confederation,
                    "points": points,
                    "rank_change": rank_change,
                    "source": "FIFA",
                })

    # Strategy 2: look for structured divs (FIFA uses React rendering)
    if not results:
        for div in soup.select('[class*="ranking"], [class*="Ranking"], [data-testid*="rank"]'):
            rank_el = div.select_one('[class*="rank"], [class*="position"]')
            team_el = div.select_one('[class*="team"], [class*="name"], [class*="country"]')
            points_el = div.select_one('[class*="point"], [class*="score"]')
            if rank_el and team_el:
                rank = to_number(rank_el.get_text(strip=True))
                team = team_el.get_text(strip=True)
                if rank and team:
                    results.append({
                        "rank": int(rank),
                        "team": team,
                        "confederation": "",
                        "points": to_number(points_el.get_text(strip=True)) if points_el else None,
                        "rank_change": None,
                        "source": "FIFA",
                    })

    return results


def fetch_fifa_ranking(timeout: float = 30.0) -> list[dict[str, Any]]:
    """Fetch FIFA Men's World Ranking. Tries API first, then HTML."""
    # Try API
    api_result = _try_fifa_api(timeout)
    if api_result:
        return api_result

    # Fallback to HTML
    try:
        html = fetch_text(FIFA_RANKING_URL, timeout=timeout)
        results = _parse_fifa_html(html)
        if results:
            return results
    except FetchError:
        pass

    raise FetchError(
        "Could not fetch FIFA ranking from API or HTML. "
        "The page structure may have changed. Try using --team to search SoFIFA instead."
    )


def find_team_in_ranking(rankings: list[dict[str, Any]], team_name: str) -> dict[str, Any] | None:
    """Fuzzy-match a team name in the ranking list."""
    team_lower = team_name.lower().strip()
    # Exact match
    for entry in rankings:
        if entry["team"].lower().strip() == team_lower:
            return entry
    # Substring match
    for entry in rankings:
        if team_lower in entry["team"].lower() or entry["team"].lower() in team_lower:
            return entry
    return None


# ---------------------------------------------------------------------------
# EA FC / SoFIFA mode
# ---------------------------------------------------------------------------

def _parse_sofifa_teams_page(html: str) -> list[dict[str, Any]]:
    """Parse SoFIFA national teams listing page."""
    soup = BeautifulSoup(html, "lxml")
    results = []

    table = soup.select_one("table.table-responsive, table")
    if not table:
        return results

    rows = table.select("tbody tr")
    for row in rows:
        cells = row.select("td")
        if len(cells) < 4:
            continue

        # Extract team name and link
        team_link = row.select_one("a[href*='/team/']")
        team_name = team_link.get_text(strip=True) if team_link else ""
        team_url = team_link.get("href", "") if team_link else ""
        if team_url and not team_url.startswith("http"):
            team_url = f"https://sofifa.com{team_url}"

        # Extract ratings from cells
        ratings = []
        for cell in cells:
            text = cell.get_text(strip=True)
            num = to_number(text)
            if num is not None and 30 <= num <= 99:
                ratings.append(num)

        if team_name and ratings:
            results.append({
                "team": team_name,
                "team_url": team_url,
                "overall": ratings[0] if len(ratings) > 0 else None,
                "attack": ratings[1] if len(ratings) > 1 else None,
                "midfield": ratings[2] if len(ratings) > 2 else None,
                "defence": ratings[3] if len(ratings) > 3 else None,
                "source": "SoFIFA/EAFC",
            })

    return results


def _parse_sofifa_team_detail(html: str, team_name: str) -> dict[str, Any]:
    """Parse detailed ratings from a SoFIFA team page."""
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, Any] = {
        "team": team_name,
        "source": "SoFIFA/EAFC",
    }

    # Look for overall rating
    ovr_el = soup.select_one('[class*="overall"], [class*="ovr"], [data-property="overall"]')
    if ovr_el:
        result["overall"] = to_number(ovr_el.get_text(strip=True))

    # Look for sub-ratings in various structures
    rating_labels = {
        "attack": ["attack", "att", "atk", "ATT"],
        "midfield": ["midfield", "mid", "MID"],
        "defence": ["defence", "defense", "def", "DEF"],
        "pace": ["pace", "PAC"],
        "shooting": ["shooting", "sho", "SHO"],
        "passing": ["passing", "pas", "PAS"],
        "dribbling": ["dribbling", "dri", "DRI"],
        "physical": ["physical", "phy", "PHY"],
    }

    for key, labels in rating_labels.items():
        for label in labels:
            el = soup.find(string=re.compile(rf"\b{re.escape(label)}\b", re.IGNORECASE))
            if el:
                parent = el.find_parent(["td", "div", "span", "li"])
                if parent:
                    # Look for a number near the label
                    sibling_nums = parent.select('[class*="rating"], [class*="value"]')
                    for sib in sibling_nums:
                        num = to_number(sib.get_text(strip=True))
                        if num is not None and 30 <= num <= 99:
                            result[key] = num
                            break
                if key in result:
                    break

    # Also try the card-style layout
    card = soup.select_one('[class*="card"], [class*="team"]')
    if card and "overall" not in result:
        big_nums = card.select('[class*="big"], [class*="main"], h1, h2')
        for el in big_nums:
            num = to_number(el.get_text(strip=True))
            if num is not None and 30 <= num <= 99:
                result["overall"] = num
                break

    return result


def fetch_eafc_ratings(team_names: list[str], timeout: float = 30.0) -> list[dict[str, Any]]:
    """Fetch EA FC ratings for given national teams from SoFIFA."""
    # First fetch the teams listing page
    try:
        html = fetch_text(SOFAIFA_TEAMS_URL, timeout=timeout)
        all_teams = _parse_sofifa_teams_page(html)
    except FetchError:
        all_teams = []

    results = []
    for team_name in team_names:
        team_lower = team_name.lower().strip()
        matched = None

        # Try exact match first
        for entry in all_teams:
            if entry["team"].lower().strip() == team_lower:
                matched = entry
                break

        # Fuzzy match
        if not matched:
            for entry in all_teams:
                if team_lower in entry["team"].lower() or entry["team"].lower() in team_lower:
                    matched = entry
                    break

        if matched:
            # If we have a team detail URL, try to get more detailed ratings
            if matched.get("team_url"):
                try:
                    detail_html = fetch_text(matched["team_url"], timeout=timeout)
                    detail = _parse_sofifa_team_detail(detail_html, matched["team"])
                    # Merge: detail page fills in gaps
                    merged = {**matched}
                    for key, value in detail.items():
                        if value is not None:
                            merged[key] = value
                    results.append(merged)
                except FetchError:
                    results.append(matched)
            else:
                results.append(matched)
        else:
            results.append({
                "team": team_name,
                "overall": None,
                "attack": None,
                "midfield": None,
                "defence": None,
                "source": "SoFIFA/EAFC",
                "note": "team not found on SoFIFA",
            })

    return results


def classify_strength_tier(fifa_rank: float | None, eafc_ovr: float | None) -> str:
    """Classify a team into a strength tier based on FIFA rank and EA FC OVR."""
    if fifa_rank is not None:
        if fifa_rank <= 10:
            return "elite"
        if fifa_rank <= 30:
            return "strong"
        if fifa_rank <= 60:
            return "mid"
        if fifa_rank <= 100:
            return "mid-low"
        return "weak"
    if eafc_ovr is not None:
        if eafc_ovr >= 82:
            return "elite"
        if eafc_ovr >= 76:
            return "strong"
        if eafc_ovr >= 70:
            return "mid"
        if eafc_ovr >= 65:
            return "mid-low"
        return "weak"
    return "unknown"


def build_team_profile(
    team_name: str,
    ranking: list[dict[str, Any]],
    eafc: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge FIFA ranking and EA FC rating into a unified team profile."""
    fifa = find_team_in_ranking(ranking, team_name)
    eafc_entry = None
    for entry in eafc:
        if entry["team"].lower().strip() == team_name.lower().strip():
            eafc_entry = entry
            break
    if not eafc_entry:
        for entry in eafc:
            if team_name.lower() in entry["team"].lower() or entry["team"].lower() in team_name.lower():
                eafc_entry = entry
                break

    fifa_rank = fifa.get("rank") if fifa else None
    fifa_points = fifa.get("points") if fifa else None
    eafc_ovr = eafc_entry.get("overall") if eafc_entry else None
    tier = classify_strength_tier(fifa_rank, eafc_ovr)

    return {
        "team": team_name,
        "fifa_ranking": {
            "rank": fifa_rank,
            "points": fifa_points,
            "confederation": fifa.get("confederation", "") if fifa else "",
            "rank_change": fifa.get("rank_change") if fifa else None,
        } if fifa else None,
        "eafc_rating": {
            "overall": eafc_entry.get("overall") if eafc_entry else None,
            "attack": eafc_entry.get("attack") if eafc_entry else None,
            "midfield": eafc_entry.get("midfield") if eafc_entry else None,
            "defence": eafc_entry.get("defence") if eafc_entry else None,
        } if eafc_entry else None,
        "strength_tier": tier,
        "is_data_sparse": tier in ("mid-low", "weak", "unknown"),
        "data_quality": "good" if (fifa and eafc_entry) else ("partial" if (fifa or eafc_entry) else "insufficient"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch FIFA Men's World Ranking and EA FC national team ratings."
    )
    parser.add_argument(
        "--mode",
        choices=["ranking", "eafc", "profile"],
        default="profile",
        help=(
            "ranking: FIFA official ranking only. "
            "eafc: EA FC game ratings only. "
            "profile: merge both into unified team profiles (default)."
        ),
    )
    parser.add_argument(
        "--team",
        action="append",
        default=[],
        help="Team name to look up (repeatable). Required for eafc/profile modes.",
    )
    parser.add_argument(
        "--matchup",
        help='Matchup string like "Costa Rica vs Ecuador". Auto-extracts team names.',
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    retrieved_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    # Extract team names
    team_names = list(args.team)
    if args.matchup:
        team_names.extend(parse_matchup(args.matchup))
    team_names = list(dict.fromkeys(team_names))  # deduplicate preserving order

    try:
        if args.mode == "ranking":
            rankings = fetch_fifa_ranking(timeout=args.timeout)
            if team_names:
                filtered = [r for r in rankings if any(
                    t.lower() in r["team"].lower() or r["team"].lower() in t.lower()
                    for t in team_names
                )]
                rankings = filtered if filtered else rankings
            output = {
                "source": "FIFA",
                "sourceUrl": FIFA_RANKING_URL,
                "retrievedAt": retrieved_at,
                "mode": "ranking",
                "rankings": rankings,
            }

        elif args.mode == "eafc":
            if not team_names:
                print("[fifa_rating] --team or --matchup required for eafc mode", file=sys.stderr)
                return 1
            ratings = fetch_eafc_ratings(team_names, timeout=args.timeout)
            output = {
                "source": "SoFIFA/EAFC",
                "sourceUrl": SOFAIFA_TEAMS_URL,
                "retrievedAt": retrieved_at,
                "mode": "eafc",
                "ratings": ratings,
            }

        else:  # profile
            # Fetch ranking for all teams
            try:
                rankings = fetch_fifa_ranking(timeout=args.timeout)
            except FetchError as exc:
                print(f"[fifa_rating] FIFA ranking fetch failed, continuing without: {exc}", file=sys.stderr)
                rankings = []

            # Fetch EA FC for specified teams
            eafc_ratings = []
            if team_names:
                try:
                    eafc_ratings = fetch_eafc_ratings(team_names, timeout=args.timeout)
                except FetchError as exc:
                    print(f"[fifa_rating] EA FC ratings fetch failed: {exc}", file=sys.stderr)

            profiles = []
            for team_name in team_names:
                profile = build_team_profile(team_name, rankings, eafc_ratings)
                profiles.append(profile)

            # If no teams specified, return full ranking with empty EA FC
            if not team_names:
                for entry in rankings[:50]:
                    profiles.append(build_team_profile(entry["team"], rankings, []))

            output = {
                "source": "FIFA + SoFIFA/EAFC",
                "retrievedAt": retrieved_at,
                "mode": "profile",
                "profiles": profiles,
            }

    except FetchError as exc:
        print(f"[fifa_rating] failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
