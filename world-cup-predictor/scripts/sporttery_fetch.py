#!/usr/bin/env python3
"""Fetch compact Sporttery football odds for Jingcai-style analysis."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Any, Iterable

import requests


ENDPOINT = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry"

POOL_LABELS = {
    "had": "胜平负",
    "hhad": "让球胜平负",
    "crs": "比分",
    "ttg": "总进球",
    "hafu": "半全场",
}

DEFAULT_POOL_CODES = ["had", "hhad", "crs", "ttg", "hafu"]
META_KEYS = {"goalLine", "goalLineValue", "id", "updateDate", "updateTime"}


def sporttery_headers() -> dict[str, str]:
    return {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "zh-CN,zh;q=0.9",
        "origin": "https://m.sporttery.cn",
        "priority": "u=1, i",
        "referer": "https://m.sporttery.cn/",
        "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
    }


def normalize_pool_codes(pool_codes: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in pool_codes:
        for code in item.split(","):
            code = code.strip().lower()
            if not code or code in seen:
                continue
            if code not in POOL_LABELS:
                raise ValueError(f"unsupported poolCode: {code}")
            seen.add(code)
            normalized.append(code)
    return normalized


def decimal_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def implied_probability(decimal_odds: float | None) -> float | None:
    if not decimal_odds or decimal_odds <= 0:
        return None
    return round(1 / decimal_odds, 4)


def fetch_pool(pool_code: str, timeout: int) -> dict[str, Any]:
    response = requests.get(
        ENDPOINT,
        params={"channel": "c", "poolCode": pool_code},
        headers=sporttery_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        message = payload.get("errorMessage") or "Sporttery request failed"
        raise RuntimeError(f"{pool_code}: {message}")
    return payload


def selection_label(pool: str, key: str, odds_map: dict[str, Any]) -> str:
    if pool == "had":
        return {"h": "主胜", "d": "平", "a": "客胜"}.get(key, key)
    if pool == "hhad":
        goal_line = odds_map.get("goalLineValue") or odds_map.get("goalLine") or ""
        suffix = f"({goal_line})" if goal_line else ""
        return {"h": f"让胜{suffix}", "d": f"让平{suffix}", "a": f"让负{suffix}"}.get(key, key)
    if pool == "ttg" and re.fullmatch(r"s\d", key):
        goals = key[1:]
        return "7+球" if goals == "7" else f"{goals}球"
    if pool == "hafu" and re.fullmatch(r"[hda]{2}", key):
        side = {"h": "胜", "d": "平", "a": "负"}
        return f"{side[key[0]]}{side[key[1]]}"
    if pool == "crs":
        exact = re.fullmatch(r"s(\d{2})s(\d{2})", key)
        if exact:
            return f"{int(exact.group(1))}:{int(exact.group(2))}"
        return {"s1sh": "胜其他", "s1sd": "平其他", "s1sa": "负其他"}.get(key, key)
    return key


def extract_market(match: dict[str, Any], pool: str) -> dict[str, Any] | None:
    odds_map = match.get(pool) or {}
    rows = []
    for key, value in odds_map.items():
        if key in META_KEYS or key.endswith("f"):
            continue
        decimal_odds = decimal_or_none(value)
        if decimal_odds is None:
            continue
        rows.append(
            {
                "selectionCode": key,
                "selection": selection_label(pool, key, odds_map),
                "decimalOdds": decimal_odds,
                "impliedProbability": implied_probability(decimal_odds),
            }
        )
    if not rows:
        return None
    return {
        "poolCode": pool,
        "poolName": POOL_LABELS[pool],
        "goalLine": odds_map.get("goalLineValue") or odds_map.get("goalLine") or "",
        "updatedAt": " ".join(
            part for part in [odds_map.get("updateDate"), odds_map.get("updateTime")] if part
        ),
        "selections": rows,
    }


def match_identity(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "matchId": match.get("matchId"),
        "matchNumStr": match.get("matchNumStr"),
        "league": match.get("leagueAbbName") or match.get("leagueAllName"),
        "home": match.get("homeTeamAllName") or match.get("homeTeamAbbName"),
        "away": match.get("awayTeamAllName") or match.get("awayTeamAbbName"),
        "matchDate": match.get("matchDate"),
        "matchTime": match.get("matchTime"),
        "businessDate": match.get("businessDate"),
        "status": match.get("matchStatus"),
    }


def iter_matches(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for day in payload.get("value", {}).get("matchInfoList", []):
        yield from day.get("subMatchList", [])


def match_filter(match: dict[str, Any], text: str | None) -> bool:
    if not text:
        return True
    haystack = " ".join(str(value or "") for value in match_identity(match).values())
    return text.lower() in haystack.lower()


def business_date_filter(match: dict[str, Any], business_date: str | None) -> bool:
    if not business_date:
        return True
    return str(match.get("businessDate") or "") == business_date


def compact_payload(
    payloads: list[dict[str, Any]],
    pools: list[str],
    match_text: str | None,
    business_date: str | None,
    retrieved_at: str,
) -> dict[str, Any]:
    by_match: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        for match in iter_matches(payload):
            if not match_filter(match, match_text):
                continue
            if not business_date_filter(match, business_date):
                continue
            identity = match_identity(match)
            key = str(identity["matchId"] or json.dumps(identity, ensure_ascii=False, sort_keys=True))
            item = by_match.setdefault(key, {**identity, "markets": []})
            existing = {market["poolCode"] for market in item["markets"]}
            for pool in pools:
                market = extract_market(match, pool)
                if market and pool not in existing:
                    item["markets"].append(market)
                    existing.add(pool)
    return {
        "source": "Sporttery",
        "sourceUrl": ENDPOINT,
        "retrievedAt": retrieved_at,
        "poolCodes": pools,
        "businessDate": business_date,
        "matches": sorted(
            by_match.values(),
            key=lambda match: (
                str(match.get("matchDate") or ""),
                str(match.get("matchTime") or ""),
                str(match.get("matchNumStr") or ""),
            ),
        ),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch compact Sporttery football odds.")
    parser.add_argument(
        "--pool-code",
        action="append",
        default=[],
        help="Sporttery poolCode, repeatable or comma-separated. Defaults: had,hhad,crs,ttg,hafu.",
    )
    parser.add_argument("--match", help="Filter by team, match number, league, or date substring.")
    parser.add_argument(
        "--business-date",
        help="Filter by Sporttery businessDate, which should be the US fixture date for World Cup requests.",
    )
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    requested = args.pool_code or DEFAULT_POOL_CODES
    pools = normalize_pool_codes(requested)
    retrieved_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    payloads = [fetch_pool(pool, args.timeout) for pool in pools]
    result = compact_payload(payloads, pools, args.match, args.business_date, retrieved_at)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
