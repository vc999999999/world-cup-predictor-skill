#!/usr/bin/env python3
"""Fetch and clean FBref match results.

The cleaning mirrors the worldfootballR `fb_match_results()` path:
read the FBref fixtures table, remove repeated header rows, split Score
into home/away goals, coerce xG and attendance to numbers, and attach
match-report URLs.
"""

from __future__ import annotations

import argparse
import sys
import time
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment


BASE_URL = "https://fbref.com"
COMPETITIONS_CSV = (
    "https://raw.githubusercontent.com/JaseZiv/worldfootballR_data/"
    "master/raw-data/all_leages_and_cups/all_competitions.csv"
)
CACHED_MATCH_RESULTS_URL = (
    "https://raw.githubusercontent.com/JaseZiv/worldfootballR_data/"
    "master/data/match_results/{country}_match_results.rds"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Referer": "https://fbref.com/",
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


def download_file(url: str, path: Path, timeout: float = 60.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return path

    with requests.get(url, headers=HEADERS, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    handle.write(chunk)
        tmp.replace(path)
    return path


def soup_with_comments(html: str) -> BeautifulSoup:
    """FBref sometimes hides useful tables in HTML comments."""
    soup = BeautifulSoup(html, "lxml")
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if "<table" in comment:
            comment_soup = BeautifulSoup(comment, "lxml")
            for table in comment_soup.find_all("table"):
                soup.append(table)
    return soup


def table_to_dataframe(table) -> pd.DataFrame:
    tables = pd.read_html(StringIO(str(table)))
    if not tables:
        raise ValueError("No table found in supplied HTML")
    df = tables[0]
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "_".join(str(part) for part in col if str(part) and not str(part).startswith("Unnamed"))
            for col in df.columns
        ]
    df.columns = [str(col).strip() for col in df.columns]
    return df


def clean_column_name(name: str) -> str:
    cleaned = (
        str(name)
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_per_")
        .replace("%", "_percent")
        .replace("#", "num")
    )
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_").lower()


def to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA}),
        errors="coerce",
    )


def normalize_score(value: object) -> tuple[float | None, float | None]:
    if value is None or pd.isna(value):
        return None, None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None, None
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    parts = [part.strip() for part in text.split("-")]
    if len(parts) != 2:
        parts = text.split()
    if len(parts) != 2:
        return None, None
    return pd.to_numeric(parts[0], errors="coerce"), pd.to_numeric(parts[1], errors="coerce")


def extract_match_urls(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    rows = soup.select(".stats_table tbody tr")
    for row in rows:
        classes = row.get("class", [])
        if "spacer" in classes or "thead" in classes:
            continue
        cell = row.select_one('[data-stat="match_report"] a')
        urls.append(urljoin(BASE_URL, cell["href"]) if cell and cell.get("href") else pd.NA)
    return urls


def clean_match_results(df: pd.DataFrame, match_urls: list[str] | None = None) -> pd.DataFrame:
    df = df.copy()
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

    if "Time" in df.columns:
        df = df[df["Time"].astype(str).str.lower() != "time"]
    if "Score" in df.columns:
        goals = df["Score"].apply(normalize_score)
        df["home_goals"] = [g[0] for g in goals]
        df["away_goals"] = [g[1] for g in goals]
    else:
        df["home_goals"] = pd.NA
        df["away_goals"] = pd.NA

    rename_map = {
        "Wk": "week",
        "Round": "round",
        "Day": "day",
        "Date": "date",
        "Time": "time",
        "Home": "home_team",
        "Away": "away_team",
        "Attendance": "attendance",
        "Venue": "venue",
        "Referee": "referee",
        "Notes": "notes",
        "xG": "home_xg",
        "xG.1": "away_xg",
    }
    df = df.rename(columns={col: rename_map.get(col, clean_column_name(col)) for col in df.columns})

    for col in ("home_goals", "away_goals", "attendance", "home_xg", "away_xg"):
        if col in df.columns:
            df[col] = to_number(df[col])

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype("string")

    if match_urls is not None:
        usable_urls = list(match_urls)[: len(df)]
        if len(usable_urls) < len(df):
            usable_urls.extend([pd.NA] * (len(df) - len(usable_urls)))
        df["match_url"] = usable_urls

    ordered = [
        "week",
        "round",
        "day",
        "date",
        "time",
        "home_team",
        "home_goals",
        "home_xg",
        "away_team",
        "away_goals",
        "away_xg",
        "attendance",
        "venue",
        "referee",
        "notes",
        "match_url",
    ]
    existing = [col for col in ordered if col in df.columns]
    remaining = [col for col in df.columns if col not in existing and col not in {"score", "match_report"}]
    return df[existing + remaining].reset_index(drop=True)


def parse_fixture_page(html: str) -> pd.DataFrame:
    soup = soup_with_comments(html)
    table = soup.select_one(".stats_table")
    if table is None:
        raise ValueError("Could not find FBref fixtures table with class .stats_table")
    match_urls = extract_match_urls(soup)
    return clean_match_results(table_to_dataframe(table), match_urls=match_urls)


def load_competitions(timeout: float = 30.0) -> pd.DataFrame:
    text = fetch_text(COMPETITIONS_CSV, timeout=timeout)
    return pd.read_csv(StringIO(text))


def fixture_urls_from_metadata(
    country: str,
    gender: str,
    season_end_year: int,
    tier: str,
    non_dom_league_url: str | None = None,
) -> list[str]:
    seasons = load_competitions()
    data = seasons[seasons["fixtures_url"].notna()]
    if non_dom_league_url:
        data = data[
            (data["comp_url"] == non_dom_league_url)
            & (data["gender"] == gender)
            & (data["season_end_year"] == season_end_year)
        ]
    else:
        data = data[
            data["competition_type"].astype(str).str.contains("Leagues", na=False)
            & (data["country"] == country)
            & (data["gender"] == gender)
            & (data["season_end_year"] == season_end_year)
            & (data["tier"] == tier)
        ]
    return data.sort_values("season_end_year")["fixtures_url"].drop_duplicates().tolist()


def fetch_fixture_results(url: str, timeout: float = 30.0, retries: int = 2, pause: float = 3.0) -> pd.DataFrame:
    html = fetch_text(url, timeout=timeout, retries=retries, pause=pause)
    data = parse_fixture_page(html)
    data.insert(0, "fixture_url", url)
    return data


def write_output(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    else:
        df.to_csv(path, index=False)


def normalize_cached_results(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "Competition_Name": "competition_name",
        "Gender": "gender",
        "Country": "country",
        "Season_End_Year": "season_end_year",
        "Tier": "tier",
        "Round": "round",
        "Wk": "week",
        "Day": "day",
        "Date": "date",
        "Time": "time",
        "Home": "home_team",
        "HomeGoals": "home_goals",
        "Home_xG": "home_xg",
        "Away": "away_team",
        "AwayGoals": "away_goals",
        "Away_xG": "away_xg",
        "Attendance": "attendance",
        "Venue": "venue",
        "Referee": "referee",
        "Notes": "notes",
        "MatchURL": "match_url",
    }
    df = df.rename(columns={col: rename_map.get(col, clean_column_name(col)) for col in df.columns}).copy()
    for col in ("season_end_year", "home_goals", "away_goals", "attendance", "home_xg", "away_xg"):
        if col in df.columns:
            df[col] = to_number(df[col])
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype("string")
    return df


def fetch_cached_match_results(
    country: str,
    gender: str,
    season_end_year: int,
    tier: str,
    timeout: float = 60.0,
) -> pd.DataFrame:
    try:
        import pyreadr
    except ImportError as exc:
        raise FetchError("Cached FBref mode requires pyreadr. Install with: python3 -m pip install pyreadr") from exc

    country = country.upper()
    url = CACHED_MATCH_RESULTS_URL.format(country=country)
    cache_root = Path(__file__).resolve().parents[1] / "work" / "cache"
    path = download_file(url, cache_root / f"{country}_match_results.rds", timeout=timeout)
    result = pyreadr.read_r(str(path))
    if not result:
        raise FetchError(f"No dataframe found in cached RDS file {path}")

    data = normalize_cached_results(next(iter(result.values())))
    data = data[
        (data["country"] == country)
        & (data["gender"] == gender)
        & (data["season_end_year"] == season_end_year)
        & (data["tier"] == tier)
    ].copy()
    data.insert(0, "source_url", url)
    if data.empty:
        raise FetchError(
            f"No cached FBref rows for country={country}, gender={gender}, "
            f"season_end_year={season_end_year}, tier={tier}"
        )
    return data.reset_index(drop=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and clean FBref fixtures/match results.")
    parser.add_argument(
        "--source",
        choices=["auto", "live", "cached"],
        default="auto",
        help="auto tries live FBref first and falls back to worldfootballR_data cached FBref results.",
    )
    parser.add_argument(
        "--fixtures-url",
        default="https://fbref.com/en/comps/9/10728/schedule/2022-2023-Premier-League-Scores-and-Fixtures",
        help="Direct FBref fixtures URL. Used unless --from-meta is passed.",
    )
    parser.add_argument("--from-meta", action="store_true", help="Resolve fixtures URL from worldfootballR_data metadata.")
    parser.add_argument("--country", default="ENG")
    parser.add_argument("--gender", default="M")
    parser.add_argument("--season-end-year", type=int, default=2023)
    parser.add_argument("--tier", default="1st")
    parser.add_argument("--non-dom-league-url")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--pause", type=float, default=3.0)
    parser.add_argument("--limit", type=int, help="Limit output rows for quick smoke tests.")
    parser.add_argument("--output", type=Path, default=Path("fbref_results.csv"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        if args.source == "cached":
            result = fetch_cached_match_results(args.country, args.gender, args.season_end_year, args.tier)
        else:
            try:
                urls = (
                    fixture_urls_from_metadata(
                        country=args.country,
                        gender=args.gender,
                        season_end_year=args.season_end_year,
                        tier=args.tier,
                        non_dom_league_url=args.non_dom_league_url,
                    )
                    if args.from_meta
                    else [args.fixtures_url]
                )
                if not urls:
                    raise FetchError("No FBref fixtures URL matched the supplied metadata filters.")

                frames = [
                    fetch_fixture_results(url, timeout=args.timeout, retries=args.retries, pause=args.pause)
                    for url in urls
                ]
                result = pd.concat(frames, ignore_index=True)
            except Exception as live_exc:
                if args.source == "live":
                    raise
                print(f"[fbref] live fetch failed, falling back to cached data: {live_exc}", file=sys.stderr)
                result = fetch_cached_match_results(args.country, args.gender, args.season_end_year, args.tier)
        if args.limit:
            result = result.head(args.limit)
        write_output(result, args.output)
    except Exception as exc:
        print(f"[fbref] failed: {exc}", file=sys.stderr)
        return 1

    print(f"[fbref] rows={len(result)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
