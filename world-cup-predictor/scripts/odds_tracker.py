#!/usr/bin/env python3
"""Track Sporttery odds movement across multiple runs.

Each time ``sporttery_fetch.py`` is executed, this script can snapshot the
odds into a local history store.  Subsequent runs compare current odds
against historical snapshots to detect significant movements — a powerful
signal especially for weaker-team matches where public data is sparse.

Odds movement often reflects non-public information (injuries, tactical
changes, sharp money) that is otherwise invisible for data-sparse teams.

Storage
-------
Snapshots are stored as JSON files under::

    work/world-cup-predictor/.odds_history/

Each file is named ``{businessDate}_{matchId}.json`` and contains an
append-only list of timestamped odds snapshots.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ODDS_HISTORY_DIR = ".odds_history"
MOVEMENT_THRESHOLDS = {
    "minor": 0.03,     # 3% movement
    "moderate": 0.07,  # 7% movement
    "significant": 0.12,  # 12% movement
    "major": 0.20,     # 20% movement
}


def get_history_dir(run_dir: Path | str | None = None) -> Path:
    """Get the odds history directory, creating it if needed."""
    if run_dir:
        base = Path(run_dir)
    else:
        base = Path.cwd()
    history_dir = base / ODDS_HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def snapshot_key(business_date: str, match_id: str) -> str:
    """Generate a filename key for a match snapshot."""
    safe_id = str(match_id).replace("/", "_").replace(" ", "_")
    return f"{business_date}_{safe_id}.json"


def load_snapshot_file(history_dir: Path, key: str) -> list[dict[str, Any]]:
    """Load existing snapshots for a match, or return empty list."""
    path = history_dir / key
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_snapshot_file(history_dir: Path, key: str, snapshots: list[dict[str, Any]]) -> None:
    """Save snapshots for a match."""
    path = history_dir / key
    path.write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_odds_from_sporttery(sporttery_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract per-match odds from sporttery_fetch.py output."""
    results = []
    for match in sporttery_data.get("matches", []):
        match_info = {
            "matchId": match.get("matchId"),
            "home": match.get("home"),
            "away": match.get("away"),
            "businessDate": match.get("businessDate"),
            "markets": [],
        }
        for market in match.get("markets", []):
            market_entry = {
                "poolCode": market.get("poolCode"),
                "poolName": market.get("poolName"),
                "updatedAt": market.get("updatedAt"),
                "selections": {},
            }
            for sel in market.get("selections", []):
                sel_code = sel.get("selectionCode", "")
                market_entry["selections"][sel_code] = {
                    "selection": sel.get("selection"),
                    "decimalOdds": sel.get("decimalOdds"),
                    "impliedProbability": sel.get("impliedProbability"),
                }
            match_info["markets"].append(market_entry)
        results.append(match_info)
    return results


def snapshot_odds(
    sporttery_data: dict[str, Any],
    run_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Store a new snapshot of current Sporttery odds.

    Call this after running sporttery_fetch.py.  It reads the Sporttery
    output, appends a timestamped snapshot to the history store, and
    returns a summary of how many matches were snapshot.
    """
    history_dir = get_history_dir(run_dir)
    timestamp = datetime.now().astimezone().isoformat()
    extracted = extract_odds_from_sporttery(sporttery_data)
    count = 0

    for match in extracted:
        match_id = match.get("matchId", "unknown")
        business_date = match.get("businessDate", "unknown")
        key = snapshot_key(business_date, match_id)
        snapshots = load_snapshot_file(history_dir, key)

        snapshot_entry = {
            "timestamp": timestamp,
            "home": match.get("home"),
            "away": match.get("away"),
            "markets": match.get("markets"),
        }
        snapshots.append(snapshot_entry)
        save_snapshot_file(history_dir, key, snapshots)
        count += 1

    return {
        "action": "snapshot",
        "matches_stored": count,
        "timestamp": timestamp,
        "history_dir": str(history_dir),
    }


def compute_movement(
    old_odds: float | None,
    new_odds: float | None,
) -> dict[str, Any]:
    """Compute odds movement between two snapshots."""
    if old_odds is None or new_odds is None:
        return {
            "movement": None,
            "movement_pct": None,
            "direction": "unknown",
            "severity": "no_data",
        }

    movement = round(new_odds - old_odds, 4)
    movement_pct = round((new_odds - old_odds) / old_odds * 100, 2) if old_odds != 0 else None

    if movement < -MOVEMENT_THRESHOLDS["minor"]:
        direction = "shortening"
    elif movement > MOVEMENT_THRESHOLDS["minor"]:
        direction = "drifting"
    else:
        direction = "stable"

    abs_pct = abs(movement_pct) if movement_pct is not None else 0
    if abs_pct >= MOVEMENT_THRESHOLDS["major"] * 100:
        severity = "major"
    elif abs_pct >= MOVEMENT_THRESHOLDS["significant"] * 100:
        severity = "significant"
    elif abs_pct >= MOVEMENT_THRESHOLDS["moderate"] * 100:
        severity = "moderate"
    elif abs_pct >= MOVEMENT_THRESHOLDS["minor"] * 100:
        severity = "minor"
    else:
        severity = "negligible"

    return {
        "movement": movement,
        "movement_pct": movement_pct,
        "direction": direction,
        "severity": severity,
    }


def odds_history(
    match_text: str | None = None,
    business_date: str | None = None,
    run_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """List odds history for matches matching a text filter."""
    history_dir = get_history_dir(run_dir)
    results = []

    if not history_dir.is_dir():
        return results

    for snapshot_file in sorted(history_dir.glob("*.json")):
        # Filter by business date
        if business_date and not snapshot_file.name.startswith(business_date):
            continue

        snapshots = load_snapshot_file(history_dir, snapshot_file.name)
        if not snapshots:
            continue

        # Filter by match text
        if match_text:
            first = snapshots[0]
            combined = f"{first.get('home', '')} {first.get('away', '')}"
            if match_text.lower() not in combined.lower():
                continue

        home = snapshots[0].get("home", "?")
        away = snapshots[0].get("away", "?")
        results.append({
            "file": snapshot_file.name,
            "match": f"{home} vs {away}",
            "snapshots_count": len(snapshots),
            "first_timestamp": snapshots[0].get("timestamp"),
            "last_timestamp": snapshots[-1].get("timestamp"),
            "markets": snapshots[-1].get("markets", []),
        })

    return results


def odds_movement_report(
    match_text: str | None = None,
    business_date: str | None = None,
    run_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Generate a movement report comparing first and last snapshots."""
    history_dir = get_history_dir(run_dir)
    reports = []

    if not history_dir.is_dir():
        return reports

    for snapshot_file in sorted(history_dir.glob("*.json")):
        if business_date and not snapshot_file.name.startswith(business_date):
            continue

        snapshots = load_snapshot_file(history_dir, snapshot_file.name)
        if len(snapshots) < 2:
            continue

        if match_text:
            first = snapshots[0]
            combined = f"{first.get('home', '')} {first.get('away', '')}"
            if match_text.lower() not in combined.lower():
                continue

        home = snapshots[0].get("home", "?")
        away = snapshots[0].get("away", "?")
        first_snap = snapshots[0]
        last_snap = snapshots[-1]

        market_movements = []
        for market in last_snap.get("markets", []):
            pool_code = market.get("poolCode")
            pool_name = market.get("poolName")

            # Find matching market in first snapshot
            first_market = None
            for fm in first_snap.get("markets", []):
                if fm.get("poolCode") == pool_code:
                    first_market = fm
                    break

            if not first_market:
                continue

            first_selections = first_market.get("selections", {})
            last_selections = market.get("selections", {})

            for sel_code, last_sel in last_selections.items():
                first_sel = first_selections.get(sel_code, {})
                old_odds = first_sel.get("decimalOdds")
                new_odds = last_sel.get("decimalOdds")
                mov = compute_movement(old_odds, new_odds)

                if mov["severity"] not in ("negligible", "no_data"):
                    market_movements.append({
                        "poolCode": pool_code,
                        "poolName": pool_name,
                        "selection": last_sel.get("selection", sel_code),
                        "opening_odds": old_odds,
                        "current_odds": new_odds,
                        **mov,
                        "snapshots_count": len(snapshots),
                        "time_span": f"{first_snap.get('timestamp', '?')} → {last_snap.get('timestamp', '?')}",
                    })

        if market_movements:
            # Determine overall signal
            max_severity = max(
                (m["severity"] for m in market_movements),
                key=lambda s: list(MOVEMENT_THRESHOLDS.keys()).index(s) if s in MOVEMENT_THRESHOLDS else -1,
            )
            signal = f"{max_severity}_movement_detected"

            reports.append({
                "match": f"{home} vs {away}",
                "signal": signal,
                "max_severity": max_severity,
                "movements": market_movements,
            })

    return reports


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track Sporttery odds movement across multiple runs."
    )
    parser.add_argument(
        "--action",
        choices=["snapshot", "history", "movement"],
        required=True,
        help="snapshot: store current odds. history: list stored snapshots. movement: compute odds changes.",
    )
    parser.add_argument(
        "--sporttery-file",
        help="Path to sporttery_fetch.py JSON output (required for snapshot action).",
    )
    parser.add_argument("--match", help="Filter by team name substring.")
    parser.add_argument("--business-date", help="Filter by Sporttery businessDate.")
    parser.add_argument("--run-dir", help="Run directory (default: cwd).")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run_dir) if args.run_dir else None

    if args.action == "snapshot":
        if not args.sporttery_file:
            # Try reading from stdin
            try:
                data = json.loads(sys.stdin.read())
            except json.JSONDecodeError:
                print("[odds_tracker] --sporttery-file required or pipe valid JSON to stdin", file=sys.stderr)
                return 1
        else:
            try:
                data = json.loads(Path(args.sporttery_file).read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[odds_tracker] failed to read Sporttery file: {exc}", file=sys.stderr)
                return 1

        result = snapshot_odds(data, run_dir=run_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))

    elif args.action == "history":
        result = odds_history(
            match_text=args.match,
            business_date=args.business_date,
            run_dir=run_dir,
        )
        output = {
            "action": "history",
            "matches": result,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))

    elif args.action == "movement":
        result = odds_movement_report(
            match_text=args.match,
            business_date=args.business_date,
            run_dir=run_dir,
        )
        output = {
            "action": "movement",
            "reports": result,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
