#!/usr/bin/env python3
"""Prepare and optionally run a cached Global Fishing Watch vessel identity pilot."""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://gateway.api.globalfishingwatch.org/v3/vessels/search"
DATASET = "public-global-vessel-identity:latest"
CATEGORY_ORDER = ["fishing", "passenger", "cargo_unspecified", "tanker", "other", "unknown"]
STATUS_FIELDS = [
    "mmsi",
    "query_priority",
    "query_value",
    "status",
    "http_status",
    "cache_hit",
    "attempts",
    "entry_count",
    "dataset_versions",
    "daily_remaining",
    "monthly_remaining",
    "requested_at_utc",
    "raw_response_file",
    "error",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def numeric(row: dict[str, str], field: str) -> int:
    try:
        return int(float(row.get(field, "0") or 0))
    except ValueError:
        return 0


def row_category(row: dict[str, str]) -> str:
    categories = (row.get("ais_rough_categories") or "unknown").split("|")
    for category in CATEGORY_ORDER:
        if category in categories:
            return category
    return "unknown"


def row_rank(row: dict[str, str]):
    return (
        -numeric(row, "valid_position_rows"),
        -(1 if row.get("preferred_imo") else 0),
        row.get("mmsi", ""),
    )


def select_pilot(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    if limit < 1:
        return []
    selected: list[dict[str, str]] = []
    used: set[str] = set()

    def add(row: dict[str, str] | None) -> None:
        if row is not None and row.get("mmsi") not in used and len(selected) < limit:
            selected.append(row)
            used.add(row["mmsi"])

    conflicts = sorted((row for row in rows if row.get("identity_conflict")), key=row_rank)
    add(conflicts[0] if conflicts else None)

    groups = defaultdict(list)
    for row in rows:
        groups[(row_category(row), row.get("query_priority") or "mmsi")].append(row)
    for group_rows in groups.values():
        group_rows.sort(key=row_rank)

    for category in CATEGORY_ORDER:
        for query_priority in ("imo", "mmsi"):
            candidates = groups[(category, query_priority)]
            add(next((row for row in candidates if row.get("mmsi") not in used), None))

    remaining_by_category = defaultdict(list)
    for row in rows:
        if row.get("mmsi") not in used:
            remaining_by_category[row_category(row)].append(row)
    for category_rows in remaining_by_category.values():
        category_rows.sort(key=row_rank)
    while len(selected) < limit:
        added_this_round = False
        for category in CATEGORY_ORDER:
            candidates = remaining_by_category[category]
            while candidates and candidates[0].get("mmsi") in used:
                candidates.pop(0)
            if candidates:
                add(candidates.pop(0))
                added_this_round = True
            if len(selected) >= limit:
                break
        if not added_this_round:
            break
    return selected


def write_pilot(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        if fields:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def cache_path(raw_dir: Path, row: dict[str, str]) -> Path:
    return raw_dir / f"{row['query_priority']}_{row['query_value']}.json"


def request_url(query_value: str) -> str:
    params = [
        ("query", query_value),
        ("datasets[0]", DATASET),
        ("includes[0]", "MATCH_CRITERIA"),
    ]
    return f"{API_URL}?{urlencode(params)}"


def error_status(http_status: int) -> tuple[str, bool]:
    if http_status == 401:
        return "authentication_failed", False
    if http_status == 403:
        return "permission_denied", False
    if http_status == 429:
        return "rate_limited", True
    if 500 <= http_status <= 599:
        return "server_error", True
    return "http_error", False


def dataset_versions(payload: dict) -> str:
    versions = sorted({str(entry.get("dataset")) for entry in payload.get("entries", []) if entry.get("dataset")})
    return "|".join(versions)


def fetch_one(
    row: dict[str, str],
    token: str,
    raw_dir: Path,
    max_attempts: int,
    timeout: float,
    opener: Callable = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = cache_path(raw_dir, row)
    now = datetime.now(timezone.utc).isoformat()
    if target.is_file():
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        entries = payload.get("entries", []) if isinstance(payload, dict) else []
        return {
            "mmsi": row["mmsi"],
            "query_priority": row["query_priority"],
            "query_value": row["query_value"],
            "status": "success" if entries else "no_result",
            "http_status": 200,
            "cache_hit": True,
            "attempts": 0,
            "entry_count": len(entries),
            "dataset_versions": dataset_versions(payload),
            "daily_remaining": "",
            "monthly_remaining": "",
            "requested_at_utc": now,
            "raw_response_file": str(target),
            "error": "",
        }

    last_status = "network_error"
    last_http = ""
    last_error = ""
    daily_remaining = ""
    monthly_remaining = ""
    attempts = 0
    for attempts in range(1, max_attempts + 1):
        request = Request(
            request_url(row["query_value"]),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "malacca-ais-academic-research/1.0",
            },
        )
        try:
            with opener(request, timeout=timeout) as response:
                last_http = getattr(response, "status", 200)
                headers = getattr(response, "headers", {})
                daily_remaining = headers.get("x-ratelimit-daily-remaining-requests", "")
                monthly_remaining = headers.get("x-ratelimit-monthly-remaining-requests", "")
                payload = json.loads(response.read().decode("utf-8"))
            with target.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            entries = payload.get("entries", []) if isinstance(payload, dict) else []
            return {
                "mmsi": row["mmsi"],
                "query_priority": row["query_priority"],
                "query_value": row["query_value"],
                "status": "success" if entries else "no_result",
                "http_status": last_http,
                "cache_hit": False,
                "attempts": attempts,
                "entry_count": len(entries),
                "dataset_versions": dataset_versions(payload),
                "daily_remaining": daily_remaining,
                "monthly_remaining": monthly_remaining,
                "requested_at_utc": now,
                "raw_response_file": str(target),
                "error": "",
            }
        except HTTPError as exc:
            last_http = exc.code
            last_status, retryable = error_status(exc.code)
            last_error = str(exc)
            headers = exc.headers or {}
            daily_remaining = headers.get("x-ratelimit-daily-remaining-requests", "")
            monthly_remaining = headers.get("x-ratelimit-monthly-remaining-requests", "")
            if not retryable:
                break
        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            last_status = "parse_error" if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)) else "network_error"
            last_error = str(exc)
        if attempts < max_attempts:
            sleeper(min(2 ** (attempts - 1), 8))

    return {
        "mmsi": row["mmsi"],
        "query_priority": row["query_priority"],
        "query_value": row["query_value"],
        "status": last_status,
        "http_status": last_http,
        "cache_hit": False,
        "attempts": attempts,
        "entry_count": 0,
        "dataset_versions": "",
        "daily_remaining": daily_remaining,
        "monthly_remaining": monthly_remaining,
        "requested_at_utc": now,
        "raw_response_file": "",
        "error": last_error,
    }


def write_status(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, pilot: list[dict[str, str]], statuses: list[dict[str, object]], executed: bool) -> None:
    summary = {
        "dataset": DATASET,
        "pilot_vessels": len(pilot),
        "query_priority_counts": dict(Counter(row["query_priority"] for row in pilot)),
        "ais_rough_category_counts": dict(Counter(row_category(row) for row in pilot)),
        "executed": executed,
        "status_counts": dict(Counter(str(row["status"]) for row in statuses)),
        "note": "Pilot preparation is not external vessel-label validation." if not executed else "API results still require source-aware label adjudication.",
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or run a cached GFW vessel identity pilot.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--execute", action="store_true", help="Actually call the GFW API. Without this flag, no network request is made.")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if not args.manifest.is_file():
        parser.error(f"manifest not found: {args.manifest}")
    if args.limit < 1:
        parser.error("limit must be at least 1")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    pilot = select_pilot(read_csv(args.manifest), args.limit)
    write_pilot(output_dir / "gfw_pilot_sample.csv", pilot)

    statuses: list[dict[str, object]] = []
    if args.execute:
        token = os.environ.get("GFW_API_TOKEN", "").strip()
        if not token:
            parser.error("GFW_API_TOKEN is not set; the token must stay in the local environment")
        for index, row in enumerate(pilot, start=1):
            status = fetch_one(row, token, output_dir / "raw_responses", args.max_attempts, args.timeout)
            statuses.append(status)
            print(f"[{index}/{len(pilot)}] mmsi={row['mmsi']} query={row['query_priority']} status={status['status']}", flush=True)
            if status["status"] in {"authentication_failed", "permission_denied"}:
                print("Stopping pilot because authentication or dataset permission failed.", flush=True)
                break
            if index < len(pilot):
                time.sleep(0.25)
        write_status(output_dir / "gfw_pilot_status.csv", statuses)
    write_summary(output_dir / "gfw_pilot_summary.json", pilot, statuses, args.execute)
    if not args.execute:
        print(f"Prepared {len(pilot)} vessels. No API requests were made. Add --execute after setting GFW_API_TOKEN.")


if __name__ == "__main__":
    main()
