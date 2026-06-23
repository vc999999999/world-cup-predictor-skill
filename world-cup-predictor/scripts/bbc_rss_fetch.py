#!/usr/bin/env python3
"""
Fetch BBC Sport FIFA World Cup RSS feed and extract structured news signals.

Usage:
    python3 bbc_rss_fetch.py [--feed FEED_URL] [--days N] [--keywords KEYWORDS] [--output PATH]

Examples:
    python3 bbc_rss_fetch.py --days 3 --output bbc_worldcup.json
    python3 bbc_rss_fetch.py --keywords "injury,absence,squad,tactics,selection"
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:  # pragma: no cover
    print("requests not installed; install with: pip install requests")
    sys.exit(1)


DEFAULT_FEED = "https://feeds.bbci.co.uk/sport/football/rss.xml"
DEFAULT_KEYWORDS = (
    "injury,absence,squad,selection,lineup,tactics,manager,coach,"
    "suspended,red card,yellow card,hamstring,ankle,knee,fitness,"
    "withdrawn,ruled out,doubtful,ruled out,covid,virus"
)


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed: List[str] = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed)


def strip_tags(html: str) -> str:
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def clean_text(text: str) -> str:
    """Clean whitespace and HTML entities from text."""
    if not text:
        return ""
    text = text.replace("&quot;", '"').replace("&apos;", "'")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_rfc822_date(text: str) -> Optional[datetime]:
    """Parse RFC 822 date string (e.g. 'Mon, 23 Jun 2026 12:00:00 GMT')."""
    if not text:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def extract_items(xml_text: str) -> List[dict]:
    """Extract <item> elements from RSS XML."""
    items = []
    item_blocks = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)
    for block in item_blocks:
        title_match = re.search(r"<title>(.*?)</title>", block)
        desc_match = re.search(r"<(?:description|summary)>(.*?)</(?:description|summary)>", block)
        link_match = re.search(r"<link>(.*?)</link>", block)
        pubdate_match = re.search(r"<pubDate>(.*?)</pubDate>", block)
        guid_match = re.search(r"<guid[^>]*>(.*?)</guid>", block)

        title = clean_text(strip_tags(title_match.group(1))) if title_match else None
        desc = clean_text(strip_tags(desc_match.group(1))) if desc_match else None
        link = clean_text(link_match.group(1)) if link_match else None
        pubdate_str = clean_text(pubdate_match.group(1)) if pubdate_match else None
        guid = clean_text(guid_match.group(1)) if guid_match else None

        items.append({
            "title": title,
            "description": desc,
            "link": link,
            "pubDate": pubdate_str,
            "guid": guid or link,
        })
    return items


def classify_signal(item: dict, keywords: List[str]) -> dict:
    """Classify a news item into signal categories and determine relevance."""
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    categories = []
    severity = "low"

    injury_keywords = ["injury", "injured", "absence", "absent", "hamstring", "ankle", "knee",
                        "fitness", "fit", "doubtful", "ruled out", "withdrawn"]
    card_keywords = ["suspended", "suspension", "red card", "yellow card", "sent off"]
    squad_keywords = ["squad", "selection", "lineup", "line-up", "starting", "bench"]
    tactics_keywords = ["tactics", "tactical", "formation", "system", "manager", "coach"]
    illness_keywords = ["covid", "virus", "illness", "sick"]

    if any(k in text for k in injury_keywords):
        category = "injury"
        category_severity = "high"
    elif any(k in text for k in card_keywords):
        category = "suspension"
        category_severity = "high"
    elif any(k in text for k in squad_keywords):
        category = "squad"
        category_severity = "medium"
    elif any(k in text for k in tactics_keywords):
        category = "tactics"
        category_severity = "medium"
    elif any(k in text for k in illness_keywords):
        category = "illness"
        category_severity = "high"
    else:
        category = "general"
        category_severity = "low"

    categories.append(category)

    # Boost severity for key phrases
    boost_phrases = ["key player", "captain", "star", "main", "crucial", "vital",
                     "ruled out", "ruled out for", "will miss", "confirmed absent"]
    if any(p in text for p in boost_phrases):
        category_severity = "high" if category_severity != "high" else "high"

    return {
        "category": category,
        "severity": category_severity,
        "categories": categories,
        "keywords_matched": [k for k in keywords if k in text]
    }


def extract_teams(item: dict, team_names: Optional[List[str]] = None) -> List[str]:
    """Try to extract team names mentioned in the article."""
    text = f"{item.get('title', '')} {item.get('description', '')}"
    if team_names:
        return [t for t in team_names if t.lower() in text.lower()]
    return []


def fetch_rss(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml,application/xml,*/*",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch RSS from {url}: {e}")


def build_signal_record(item: dict, classification: dict, teams: List[str]) -> dict:
    return {
        "title": item.get("title"),
        "description": item.get("description"),
        "link": item.get("link"),
        "pubDate": item.get("pubDate"),
        "guid": item.get("guid"),
        "teams_mentioned": teams,
        "signal": {
            "category": classification["category"],
            "severity": classification["severity"],
            "keywords_matched": classification["keywords_matched"]
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch BBC Sport FIFA World Cup RSS feed.")
    parser.add_argument("--feed", default=DEFAULT_FEED, help="RSS feed URL")
    parser.add_argument("--days", type=int, default=7, help="Only include items from last N days")
    parser.add_argument("--keywords", default=DEFAULT_KEYWORDS, help="Comma-separated keywords for filtering")
    parser.add_argument("--output", default="", help="Path to write JSON output (default: stdout)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--teams", default="", help="Comma-separated team names to track")
    args = parser.parse_args()

    keyword_list = [k.strip().lower() for k in args.keywords.split(",") if k.strip()]
    team_list = [t.strip() for t in args.teams.split(",") if t.strip()] if args.teams else []

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    # Fetch
    xml_text = fetch_rss(args.feed)

    # Parse items
    raw_items = extract_items(xml_text)

    signals = []
    for item in raw_items:
        pub_dt = parse_rfc822_date(item.get("pubDate"))
        if pub_dt and pub_dt < cutoff:
            continue

        classification = classify_signal(item, keyword_list)
        # Only include if it matches at least one keyword
        if not classification["keywords_matched"]:
            continue

        teams = extract_teams(item, team_list)
        record = build_signal_record(item, classification, teams)
        signals.append(record)

    # Build output
    output = {
        "source": {
            "name": "BBC Sport",
            "feed_url": args.feed,
            "retrieved_at": datetime.now(timezone.utc).isoformat()
        },
        "filter": {
            "days": args.days,
            "keywords": keyword_list
        },
        "total_items": len(raw_items),
        "signal_count": len(signals),
        "signals": signals
    }

    json_str = json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"Wrote {len(signals)} signals to {args.output}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
