"""Pull incremental OCR/audio events from a local Screenpipe service.

Step 1 scope:
- Read-only polling from Screenpipe
- Every 60 seconds by default
- Print incremental OCR and audio text entries
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

LOGGER = logging.getLogger("screenpipe_incremental_pull")


@dataclass
class CursorState:
    """Track latest timestamp we've observed for incremental pulls."""

    since_iso: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll Screenpipe for incremental OCR/audio text and print it."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:3030")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--source-types", default="ocr,audio")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--start-since", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    timestamp = (
        row.get("timestamp")
        or row.get("created_at")
        or row.get("time")
        or row.get("frame_timestamp")
    )
    source = row.get("source") or row.get("type") or "unknown"
    content = (
        row.get("content")
        or row.get("text")
        or row.get("transcript")
        or row.get("ocr_text")
        or ""
    )
    app_context = row.get("app_context") or row.get("window_name") or row.get("app_name")

    return {
        "timestamp": timestamp,
        "source": source,
        "content": content,
        "app_context": app_context,
    }


def extract_rows(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("data", "results", "items", "events"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def fetch_incremental(
    base_url: str,
    source_types: str,
    since_iso: str,
    limit: int,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    endpoint = f"{base_url.rstrip('/')}/search"
    query = urllib.parse.urlencode(
        {
            "content_type": source_types,
            "start_time": since_iso,
            "limit": limit,
        }
    )
    url = f"{endpoint}?{query}"

    request = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")

    data = json.loads(body)
    rows = extract_rows(data)
    return [normalize_row(row) for row in rows]


def update_cursor_from_rows(previous_since_iso: str, rows: list[dict[str, Any]]) -> str:
    timestamps = [r["timestamp"] for r in rows if r.get("timestamp")]
    if not timestamps:
        return previous_since_iso

    latest = max(timestamps)
    return latest if isinstance(latest, str) else previous_since_iso


def print_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        LOGGER.info("No new OCR/audio rows in this interval.")
        return

    LOGGER.info("Fetched %s new rows", len(rows))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    state = CursorState(since_iso=args.start_since or utc_now_iso())
    LOGGER.info(
        "Starting incremental pull from %s/search, since=%s, source_types=%s, interval=%ss",
        args.base_url,
        state.since_iso,
        args.source_types,
        args.interval_seconds,
    )

    while True:
        try:
            rows = fetch_incremental(
                base_url=args.base_url,
                source_types=args.source_types,
                since_iso=state.since_iso,
                limit=args.limit,
                timeout_seconds=args.timeout_seconds,
            )
            print_rows(rows)
            state.since_iso = update_cursor_from_rows(state.since_iso, rows)
        except urllib.error.URLError as exc:
            LOGGER.warning("Screenpipe request failed: %s", exc)
        except json.JSONDecodeError as exc:
            LOGGER.warning("Failed to decode Screenpipe response JSON: %s", exc)

        if args.once:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
