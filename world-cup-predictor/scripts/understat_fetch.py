#!/usr/bin/env python3
"""Fetch and clean Understat league results or match shots.

This ports the core worldfootballR Understat pattern: read the page,
find a JavaScript variable such as `datesData` or `shotsData`, decode the
JSON.parse string, flatten nested JSON, and coerce numeric fields.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests


BASE_URL = "https://understat.com"
LEAGUES = {
    "EPL": "EPL",
    "La liga": "La_liga",
    "La_liga": "La_liga",
    "Bundesliga": "Bundesliga",
    "Serie A": "Serie_A",
    "Serie_A": "Serie_A",
    "Ligue 1": "Ligue_1",
    "Ligue_1": "Ligue_1",
    "RFPL": "RFPL",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Referer": "https://understat.com/",
    "X-Requested-With": "XMLHttpRequest",
}


class FetchError(RuntimeError):
    pass


def fetch_text(url: str, timeout: float = 30.0, retries: int = 2, pause: float = 1.0) -> str:
    last_error: Exception | None = None
    session = requests.Session()
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(pause)
        try:
            response = session.get(url, headers=HEADERS, cookies={"beget": "begetok"}, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
    raise FetchError(f"Failed to fetch {url}: {last_error}") from last_error


def decode_json_parse_string(escaped: str) -> Any:
    """Decode the JavaScript string inside JSON.parse('...')."""
    try:
        return json.loads(escaped)
    except json.JSONDecodeError:
        js_string = f'"{escaped}"'
        decoded = json.loads(js_string)
        return json.loads(decoded)


def extract_understat_json(html: str, variable_name: str) -> Any:
    pattern = re.compile(rf"var\s+{re.escape(variable_name)}\s*=\s*JSON\.parse\('(?P<payload>.*?)'\)", re.S)
    match = pattern.search(html)
    if not match:
        raise ValueError(f"Could not find Understat variable {variable_name}")
    return decode_json_parse_string(match.group("payload"))


def flatten_records(records: Any) -> pd.DataFrame:
    if isinstance(records, dict):
        rows: list[dict[str, Any]] = []
        for side, side_records in records.items():
            if isinstance(side_records, list):
                for record in side_records:
                    if isinstance(record, dict):
                        rows.append({"side": side, **record})
            elif isinstance(side_records, dict):
                rows.append({"side": side, **side_records})
        return pd.json_normalize(rows)
    return pd.json_normalize(records)


def to_number(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def clean_match_results(records: Any, league: str) -> pd.DataFrame:
    df = flatten_records(records)
    if df.empty:
        return df
    if "isResult" in df.columns:
        df = df[df["isResult"].astype(bool)].copy()

    rename = {
        "id": "match_id",
        "h.id": "home_id",
        "h.title": "home_team",
        "h.short_title": "home_abbr",
        "a.id": "away_id",
        "a.title": "away_team",
        "a.short_title": "away_abbr",
        "goals.h": "home_goals",
        "goals.a": "away_goals",
        "xG.h": "home_xg",
        "xG.a": "away_xg",
        "forecast.w": "forecast_win",
        "forecast.d": "forecast_draw",
        "forecast.l": "forecast_loss",
    }
    df = df.rename(columns=rename)
    df.insert(0, "league", league)
    df = to_number(
        df,
        [
            "home_goals",
            "away_goals",
            "home_xg",
            "away_xg",
            "forecast_win",
            "forecast_draw",
            "forecast_loss",
        ],
    )

    ordered = [
        "league",
        "match_id",
        "datetime",
        "home_id",
        "home_team",
        "home_abbr",
        "away_id",
        "away_team",
        "away_abbr",
        "home_goals",
        "away_goals",
        "home_xg",
        "away_xg",
        "forecast_win",
        "forecast_draw",
        "forecast_loss",
    ]
    existing = [col for col in ordered if col in df.columns]
    remaining = [col for col in df.columns if col not in existing]
    return df[existing + remaining].reset_index(drop=True)


def clean_shots(records: Any) -> pd.DataFrame:
    df = flatten_records(records)
    if df.empty:
        return df
    rename = {
        "h_a": "home_away",
        "h_team": "home_team",
        "a_team": "away_team",
        "h_goals": "home_goals",
        "a_goals": "away_goals",
        "player_id": "player_id",
        "match_id": "match_id",
    }
    df = df.rename(columns=rename)
    df = to_number(df, ["minute", "X", "Y", "xG", "home_goals", "away_goals"])
    return df.reset_index(drop=True)


def league_url(league: str, season_start_year: int) -> str:
    if league not in LEAGUES:
        supported = ", ".join(LEAGUES)
        raise ValueError(f"Unknown league {league}. Supported leagues: {supported}")
    return f"{BASE_URL}/league/{LEAGUES[league]}/{season_start_year}"


def league_data_url(league: str, season_start_year: int) -> str:
    if league not in LEAGUES:
        supported = ", ".join(LEAGUES)
        raise ValueError(f"Unknown league {league}. Supported leagues: {supported}")
    return f"{BASE_URL}/getLeagueData/{LEAGUES[league]}/{season_start_year}"


def fetch_league_results(
    league: str,
    season_start_year: int,
    timeout: float = 30.0,
    retries: int = 2,
    pause: float = 1.0,
) -> pd.DataFrame:
    url = league_data_url(league, season_start_year)
    text = fetch_text(url, timeout=timeout, retries=retries, pause=pause)
    try:
        payload = json.loads(text)
        records = payload.get("dates", [])
    except json.JSONDecodeError:
        records = extract_understat_json(text, "datesData")
    df = clean_match_results(records, league=league)
    df.insert(0, "source_url", url)
    return df


def fetch_match_shots(
    match_url: str,
    timeout: float = 30.0,
    retries: int = 2,
    pause: float = 1.0,
) -> pd.DataFrame:
    html = fetch_text(match_url, timeout=timeout, retries=retries, pause=pause)
    records = extract_understat_json(html, "shotsData")
    df = clean_shots(records)
    df.insert(0, "source_url", match_url)
    return df


def write_output(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    else:
        df.to_csv(path, index=False)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and clean Understat data.")
    parser.add_argument("--mode", choices=["results", "shots"], default="results")
    parser.add_argument("--league", default="EPL", help="EPL, La liga, Bundesliga, Serie A, Ligue 1, RFPL")
    parser.add_argument("--season-start-year", type=int, default=2024)
    parser.add_argument("--match-url", default="https://understat.com/match/26602")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--limit", type=int, help="Limit output rows for quick smoke tests.")
    parser.add_argument("--output", type=Path, default=Path("understat_results.csv"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.mode == "results":
            result = fetch_league_results(
                args.league,
                args.season_start_year,
                timeout=args.timeout,
                retries=args.retries,
                pause=args.pause,
            )
        else:
            result = fetch_match_shots(args.match_url, timeout=args.timeout, retries=args.retries, pause=args.pause)
        if args.limit:
            result = result.head(args.limit)
        write_output(result, args.output)
    except Exception as exc:
        print(f"[understat] failed: {exc}", file=sys.stderr)
        return 1

    print(f"[understat] rows={len(result)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
