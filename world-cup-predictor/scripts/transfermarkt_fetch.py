#!/usr/bin/env python3
"""Fetch and clean Transfermarkt team transfer data.

This follows the worldfootballR `tm_team_transfers()` idea: convert a
team `startseite` URL into the `transfers` URL, collect Arrivals and
Departures tables, normalize player/team metadata, and convert transfer
fees such as `€12.50m` or `Loan fee: €500k` into numeric euros.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.transfermarkt.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Referer": "https://www.transfermarkt.com/",
}


class FetchError(RuntimeError):
    pass


def fetch_text(url: str, timeout: float = 30.0, retries: int = 2, pause: float = 2.0) -> str:
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


def absolutize(path_or_url: str | None) -> str | None:
    if not path_or_url:
        return None
    if path_or_url.startswith("http"):
        return path_or_url
    return f"{BASE_URL}{path_or_url}"


def extract_season(team_url: str) -> str | None:
    match = re.search(r"/saison_id/(\d+)", team_url)
    return match.group(1) if match else None


def build_transfers_url(team_url: str, window: str = "summer") -> str:
    window_map = {"summer": "s", "winter": "w", "s": "s", "w": "w"}
    window_key = window.lower()
    if window_key not in window_map:
        raise ValueError("window must be one of summer, winter, s, or w")

    transfers_url = team_url.replace("/startseite/", "/transfers/")
    season = extract_season(team_url)
    if season is None:
        season = extract_season(transfers_url)
    query_season = season or ""
    separator = "&" if "?" in transfers_url else "?"
    return f"{transfers_url}{separator}saison_id={query_season}&pos=&detailpos=&w_s={window_map[window_key]}"


def parse_money_value(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace("\xa0", " ")
    if not text:
        return None
    lowered = text.lower()

    if "loan fee" in lowered:
        lowered = lowered.split("loan fee:", 1)[-1].strip()
    if "free" in lowered:
        return 0
    if any(token in lowered for token in ("end of loan", "loan transfer", "?", "-")) and not re.search(r"\d", lowered):
        return None

    cleaned = lowered.replace("€", "").replace(",", "").strip()
    cleaned = re.sub(r"[^0-9.,a-z]", "", cleaned)
    if not cleaned or not re.search(r"\d", cleaned):
        return None

    multiplier = 1
    if "m" in cleaned:
        multiplier = 1_000_000
        cleaned = cleaned.replace("m", "")
    elif "th" in cleaned or "k" in cleaned:
        multiplier = 1_000
        cleaned = cleaned.replace("th.", "").replace("th", "").replace("k", "")

    try:
        return int(round(float(cleaned) * multiplier))
    except ValueError:
        return None


def text_or_none(node) -> str | None:
    if node is None:
        return None
    text = node.get_text(" ", strip=True)
    return text or None


def title_or_alt(node) -> str | None:
    if node is None:
        return None
    return node.get("title") or node.get("alt")


def parse_player_cell(cell) -> dict[str, object]:
    link = cell.select_one(".hauptlink a")
    position_nodes = cell.select("tr:nth-of-type(2) td")
    return {
        "player_name": text_or_none(link),
        "player_url": absolutize(link.get("href") if link else None),
        "player_position": text_or_none(position_nodes[-1]) if position_nodes else None,
    }


def parse_club_cell(cell) -> dict[str, object]:
    link = cell.select_one(".hauptlink a")
    league_link = None
    for candidate in cell.select("a"):
        href = candidate.get("href", "")
        if "/transfers/wettbewerb/" in href:
            league_link = candidate
            break
    country_img = cell.select_one(".flaggenrahmen")
    return {
        "club_2": text_or_none(link),
        "club_2_url": absolutize(link.get("href") if link else None),
        "league_2": text_or_none(league_link),
        "country_2": title_or_alt(country_img),
    }


def parse_transfer_row(row, transfer_type: str, window_label: str, team_meta: dict[str, object]) -> dict[str, object] | None:
    cells = row.find_all("td", recursive=False)
    if len(cells) < 6:
        return None

    player = parse_player_cell(cells[1])
    if not player["player_name"]:
        return None

    nationalities = [
        title_or_alt(img)
        for img in cells[3].select(".flaggenrahmen")
        if title_or_alt(img)
    ]
    fee_text = text_or_none(cells[5])
    parsed = {
        **team_meta,
        "transfer_type": transfer_type,
        **player,
        "player_age": pd.to_numeric(text_or_none(cells[2]), errors="coerce"),
        "player_nationality": "|".join(nationalities) if nationalities else None,
        **parse_club_cell(cells[4]),
        "transfer_fee_raw": fee_text,
        "transfer_fee_eur": parse_money_value(fee_text),
        "is_loan": bool(fee_text and "loan" in fee_text.lower()),
        "window": window_label,
    }
    return parsed


def extract_team_meta(soup: BeautifulSoup, team_url: str) -> dict[str, object]:
    team_name = text_or_none(soup.select_one("h1"))
    league = text_or_none(soup.select_one(".data-header__club a"))
    country = title_or_alt(soup.select_one(".data-header__content img[title], .data-header__content img[alt]"))
    return {
        "team_name": team_name,
        "league": league,
        "country": country,
        "season": extract_season(team_url),
        "source_team_url": team_url,
    }


def parse_transfers_page(html: str, source_team_url: str, window_label: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    team_meta = extract_team_meta(soup, source_team_url)
    records: list[dict[str, object]] = []

    for box in soup.select(".box"):
        heading = text_or_none(box.select_one("h2"))
        if heading not in {"Arrivals", "Departures"}:
            continue
        for row in box.select(".responsive-table tbody tr"):
            record = parse_transfer_row(row, heading, window_label, team_meta)
            if record:
                records.append(record)

    return pd.DataFrame.from_records(records)


def fetch_team_transfers(
    team_url: str,
    transfer_window: str = "all",
    timeout: float = 30.0,
    retries: int = 2,
    pause: float = 2.0,
) -> pd.DataFrame:
    window_key = transfer_window.lower()
    if window_key == "all":
        windows = [("summer", "Summer"), ("winter", "Winter")]
    elif window_key in {"summer", "s"}:
        windows = [("summer", "Summer")]
    elif window_key in {"winter", "w"}:
        windows = [("winter", "Winter")]
    else:
        raise ValueError("transfer_window must be all, summer, or winter")

    frames = []
    for window, label in windows:
        url = build_transfers_url(team_url, window=window)
        html = fetch_text(url, timeout=timeout, retries=retries, pause=pause)
        frame = parse_transfers_page(html, source_team_url=team_url, window_label=label)
        frame.insert(0, "transfers_url", url)
        frames.append(frame)
        if len(windows) > 1:
            time.sleep(pause)

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not result.empty:
        result = result[result["player_name"].notna()].reset_index(drop=True)
    return result


def write_output(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    else:
        df.to_csv(path, index=False)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and clean Transfermarkt team transfers.")
    parser.add_argument(
        "--team-url",
        default="https://www.transfermarkt.com/fc-bayern-munchen/startseite/verein/27/saison_id/2020",
        help="Transfermarkt team startseite URL with saison_id.",
    )
    parser.add_argument("--window", choices=["all", "summer", "winter"], default="summer")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--pause", type=float, default=2.0)
    parser.add_argument("--limit", type=int, help="Limit output rows for quick smoke tests.")
    parser.add_argument("--output", type=Path, default=Path("transfermarkt_transfers.csv"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        result = fetch_team_transfers(
            args.team_url,
            transfer_window=args.window,
            timeout=args.timeout,
            retries=args.retries,
            pause=args.pause,
        )
        if args.limit:
            result = result.head(args.limit)
        write_output(result, args.output)
    except Exception as exc:
        print(f"[transfermarkt] failed: {exc}", file=sys.stderr)
        return 1

    print(f"[transfermarkt] rows={len(result)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
