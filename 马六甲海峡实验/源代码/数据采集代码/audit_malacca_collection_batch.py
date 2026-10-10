from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DYNAMIC_TYPES = {"PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"}
STATIC_TYPES = {"ShipStaticData", "StaticDataReport"}
REQUIRED_COLUMNS = [
    "collector_version", "batch_id", "region_id", "sequence_no", "source", "bbox",
    "message_type", "received_at_utc", "received_at", "metadata_time_utc", "ais_timestamp",
    "mmsi", "lat", "lon", "sog", "cog", "true_heading", "rate_of_turn",
    "navigational_status", "vessel_name", "call_sign", "imo", "vessel_type",
    "destination", "draught", "ship_length", "ship_width", "parse_status", "parse_error",
    "raw_json",
]
PROFILE_FIELDS = [
    "vessel_name", "call_sign", "imo", "vessel_type", "ais_version", "fix_type",
    "destination", "eta_month", "eta_day", "eta_hour", "eta_minute", "draught",
    "dimension_to_bow", "dimension_to_stern", "dimension_to_port", "dimension_to_starboard",
    "ship_length", "ship_width", "vendor_id_name", "vendor_id_model", "vendor_id_serial",
]


def present(value: Any) -> bool:
    return value is not None and str(value).strip() not in {"", "0x0"}


def number(value: Any) -> float | None:
    try:
        if not present(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_time(row: dict[str, Any]) -> datetime | None:
    for field in ("metadata_time_utc", "received_at_utc", "received_at"):
        value = str(row.get(field, "")).strip()
        if not value:
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def choose_profile_value(records: list[dict[str, Any]], field: str) -> tuple[str, int, str]:
    values = [(str(row.get(field, "")).strip(), str(row.get("message_type", ""))) for row in records if present(row.get(field))]
    if not values:
        return "", 0, ""
    counts = Counter(value for value, _ in values)
    top_count = max(counts.values())
    candidates = {value for value, count in counts.items() if count == top_count}
    chosen = next(value for value, _ in reversed(values) if value in candidates)
    source = next(source for value, source in reversed(values) if value == chosen)
    return chosen, max(0, len(counts) - 1), source


def build_profiles(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        mmsi = str(row.get("mmsi", "")).strip()
        if mmsi:
            groups[mmsi].append(row)
    profiles = []
    lookup: dict[str, dict[str, str]] = {}
    for mmsi, records in sorted(groups.items()):
        times = [moment for row in records if (moment := parse_time(row)) is not None]
        profile: dict[str, Any] = {
            "mmsi": mmsi,
            "first_seen_utc": min(times).isoformat() if times else "",
            "last_seen_utc": max(times).isoformat() if times else "",
            "event_rows": len(records),
            "position_rows": sum(str(row.get("message_type")) in DYNAMIC_TYPES for row in records),
        }
        lookup[mmsi] = {}
        total_conflicts = 0
        sources = set()
        for field in PROFILE_FIELDS:
            value, conflicts, source = choose_profile_value(records, field)
            profile[field] = value
            profile[f"{field}_conflicts"] = conflicts
            lookup[mmsi][field] = value
            total_conflicts += conflicts
            if source:
                sources.add(source)
        profile["static_conflict_count"] = total_conflicts
        profile["static_source_message_types"] = "|".join(sorted(sources))
        profiles.append(profile)
    return profiles, lookup


def make_enriched_positions(rows: list[dict[str, Any]], lookup: dict[str, dict[str, str]], fields: list[str]) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        if str(row.get("message_type")) not in DYNAMIC_TYPES:
            continue
        item = dict(row)
        profile = lookup.get(str(row.get("mmsi", "")).strip(), {})
        filled = []
        for field in PROFILE_FIELDS:
            if not present(item.get(field)) and present(profile.get(field)):
                item[field] = profile[field]
                filled.append(field)
        item["static_profile_fill_fields"] = "|".join(filled)
        item["static_profile_fill_source"] = "same_batch_mmsi_merge" if filled else ""
        enriched.append(item)
    return enriched


def valid_type_code(value: Any) -> int | None:
    parsed = number(value)
    if parsed is None or parsed != int(parsed) or not 0 < parsed <= 255:
        return None
    return int(parsed)


def type_category(code: int) -> str:
    if 70 <= code <= 79:
        return "cargo"
    if 80 <= code <= 89:
        return "tanker"
    return "other"


def longest_segment(points: list[tuple[datetime, str, str]], max_gap_seconds: int = 1800) -> int:
    if not points:
        return 0
    longest = current = 1
    for previous, following in zip(points, points[1:]):
        if (following[0] - previous[0]).total_seconds() > max_gap_seconds:
            current = 1
        else:
            current += 1
        longest = max(longest, current)
    return longest


def classification_candidates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter[str]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        mmsi = str(row.get("mmsi", "")).strip()
        if mmsi:
            groups[mmsi].append(row)
    details = []
    counts: Counter[str] = Counter()
    for mmsi, records in sorted(groups.items()):
        codes = sorted({code for row in records if (code := valid_type_code(row.get("vessel_type"))) is not None})
        category = type_category(codes[0]) if len(codes) == 1 else ("conflict" if codes else "unknown")
        raw_points = []
        for row in records:
            if str(row.get("message_type")) != "PositionReport":
                continue
            moment = parse_time(row)
            lat, lon, sog = number(row.get("lat")), number(row.get("lon")), number(row.get("sog"))
            if moment is None or lat is None or lon is None or sog is None:
                continue
            if -90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= sog < 102.3:
                raw_points.append((moment, str(lat), str(lon)))
        points = sorted(set(raw_points))
        same_time_conflict = any(a[0] == b[0] and a[1:] != b[1:] for a, b in zip(points, points[1:]))
        longest = longest_segment(points)
        eligible = category in {"cargo", "tanker"} and longest >= 10 and not same_time_conflict
        details.append({
            "mmsi": mmsi, "type_codes": "|".join(map(str, codes)), "category": category,
            "valid_class_a_points": len(points), "longest_segment_points": longest,
            "same_time_position_conflict": same_time_conflict, "classification_eligible": eligible,
        })
        if eligible:
            counts[category] += 1
    return details, counts


def load_connection_stats(path: Path) -> tuple[int, Counter[str]]:
    if not path.exists():
        return 0, Counter()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        counts = Counter(row.get("event", "") for row in csv.DictReader(handle))
    return counts["connection_error"], counts


def audit(input_csv: Path, raw_jsonl: Path, connection_csv: Path, runtime_json: Path, mode: str) -> dict[str, Any]:
    with input_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    profiles, lookup = build_profiles(rows)
    enriched = make_enriched_positions(rows, lookup, fields)
    candidates, eligible_counts = classification_candidates(rows)
    message_counts = Counter(str(row.get("message_type", "")) for row in rows)
    data_rows = [row for row in rows if str(row.get("parse_status")) != "control"]
    parsed_rows = [row for row in data_rows if str(row.get("parse_status")) == "parsed"]
    dynamic_rows = [row for row in rows if str(row.get("message_type")) in DYNAMIC_TYPES]
    unique_mmsi = {str(row.get("mmsi", "")).strip() for row in rows if present(row.get("mmsi"))}
    profile_by_mmsi = {str(row["mmsi"]): row for row in profiles}

    def mmsi_with(field: str) -> set[str]:
        return {mmsi for mmsi, profile in profile_by_mmsi.items() if present(profile.get(field))}

    def coverage(population: list[dict[str, Any]], field: str) -> float:
        return sum(present(row.get(field)) for row in population) / len(population) if population else 0.0

    missing_columns = [field for field in REQUIRED_COLUMNS if field not in fields]
    raw_line_count = 0
    raw_valid = True
    if raw_jsonl.exists():
        with raw_jsonl.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw_line_count += 1
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    raw_valid = False
    else:
        raw_valid = False
    reconnects, connection_counts = load_connection_stats(connection_csv)
    checks = {
        "required_columns_present": not missing_columns,
        "raw_json_in_csv_complete": bool(rows) and coverage(rows, "raw_json") == 1.0,
        "raw_jsonl_complete_and_valid": bool(rows) and raw_valid and raw_line_count == len(rows),
        "dynamic_message_received": any(message_counts[name] for name in DYNAMIC_TYPES),
        "static_message_received": any(message_counts[name] for name in STATIC_TYPES),
        "parse_success_ge_99pct": bool(data_rows) and len(parsed_rows) / len(data_rows) >= 0.99,
        "dynamic_mmsi_ge_99pct": bool(dynamic_rows) and coverage(dynamic_rows, "mmsi") >= 0.99,
        "dynamic_lat_ge_99pct": bool(dynamic_rows) and coverage(dynamic_rows, "lat") >= 0.99,
        "dynamic_lon_ge_99pct": bool(dynamic_rows) and coverage(dynamic_rows, "lon") >= 0.99,
        "dynamic_absolute_time_ge_99pct": bool(dynamic_rows) and sum(parse_time(row) is not None for row in dynamic_rows) / len(dynamic_rows) >= 0.99,
        "dynamic_sog_ge_95pct": bool(dynamic_rows) and coverage(dynamic_rows, "sog") >= 0.95,
        "dynamic_cog_ge_95pct": bool(dynamic_rows) and coverage(dynamic_rows, "cog") >= 0.95,
        "at_least_one_mmsi_with_type": bool(mmsi_with("vessel_type")),
        "at_least_one_mmsi_with_size": bool(mmsi_with("ship_length") | mmsi_with("ship_width")),
    }
    type_coverage = len(mmsi_with("vessel_type")) / len(unique_mmsi) if unique_mmsi else 0.0
    length_coverage = len(mmsi_with("ship_length")) / len(unique_mmsi) if unique_mmsi else 0.0
    width_coverage = len(mmsi_with("ship_width")) / len(unique_mmsi) if unique_mmsi else 0.0
    if mode == "formal":
        checks["formal_unique_mmsi_type_coverage_ge_30pct"] = type_coverage >= 0.30
        checks["formal_unique_mmsi_length_coverage_ge_30pct"] = length_coverage >= 0.30
        checks["formal_unique_mmsi_width_coverage_ge_30pct"] = width_coverage >= 0.30
    verdict = "PASS" if all(checks.values()) else "FAIL"
    runtime = json.loads(runtime_json.read_text(encoding="utf-8")) if runtime_json.exists() else {}
    moments = [moment for row in data_rows if (moment := parse_time(row)) is not None]
    batch_dir = input_csv.parent
    profile_fields = ["mmsi", "first_seen_utc", "last_seen_utc", "event_rows", "position_rows"]
    for field in PROFILE_FIELDS:
        profile_fields.extend([field, f"{field}_conflicts"])
    profile_fields.extend(["static_conflict_count", "static_source_message_types"])
    write_csv(batch_dir / "vessel_static_profiles.csv", profiles, profile_fields)
    write_csv(batch_dir / "positions_enriched.csv", enriched, fields + ["static_profile_fill_fields", "static_profile_fill_source"])
    write_csv(batch_dir / "classification_candidate_audit.csv", candidates, list(candidates[0].keys()) if candidates else ["mmsi"])

    summary = {
        "verdict": verdict, "mode": mode, "batch_id": runtime.get("batch_id", ""),
        "region_id": runtime.get("region_id", ""), "bbox": runtime.get("bbox", ""),
        "rows": len(rows), "data_rows": len(data_rows), "dynamic_rows": len(dynamic_rows),
        "unique_mmsi": len(unique_mmsi), "message_counts": dict(message_counts),
        "parse_success_rate": len(parsed_rows) / len(data_rows) if data_rows else 0.0,
        "dynamic_coverage": {field: coverage(dynamic_rows, field) for field in ["mmsi", "lat", "lon", "sog", "cog", "true_heading", "rate_of_turn", "navigational_status"]},
        "unique_mmsi_static_coverage": {
            field: {"count": len(mmsi_with(field)), "rate": len(mmsi_with(field)) / len(unique_mmsi) if unique_mmsi else 0.0}
            for field in ["vessel_name", "call_sign", "imo", "vessel_type", "destination", "draught", "ship_length", "ship_width"]
        },
        "classification_eligible": sum(eligible_counts.values()),
        "classification_eligible_by_type": dict(eligible_counts),
        "received_data_start_utc": min(moments).isoformat() if moments else "",
        "received_data_end_utc": max(moments).isoformat() if moments else "",
        "reconnect_count": reconnects, "connection_event_counts": dict(connection_counts),
        "missing_required_columns": missing_columns, "checks": checks,
        "files": {},
    }
    for path in [input_csv, raw_jsonl, connection_csv, runtime_json, batch_dir / "vessel_static_profiles.csv", batch_dir / "positions_enriched.csv"]:
        if path.exists():
            summary["files"][path.name] = {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
    (batch_dir / "batch_quality_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [name for name, passed in checks.items() if not passed]
    lines = [
        "# 马六甲 AIS 采集批次质量报告", "", f"验收结论：**{verdict}**。模式：`{mode}`。", "",
        f"批次：`{summary['batch_id']}`。区域：`{summary['region_id']}`。", "",
        f"共 {len(rows)} 行，{len(unique_mmsi)} 个唯一 MMSI，动态消息 {len(dynamic_rows)} 行，重连 {reconnects} 次。",
        f"解析成功率 {summary['parse_success_rate']:.2%}。船型、船长、船宽按 MMSI 覆盖率分别为 "
        f"{type_coverage:.2%}、{length_coverage:.2%}、{width_coverage:.2%}。",
        f"本批次严格货船/油轮候选 {summary['classification_eligible']} 艘，其中货船 {eligible_counts['cargo']} 艘、油轮 {eligible_counts['tanker']} 艘。", "",
        "## 验收检查", "", "| 检查项 | 结果 |", "| --- | --- |",
    ]
    lines.extend(f"| `{name}` | {'PASS' if passed else 'FAIL'} |" for name, passed in checks.items())
    lines += ["", "## 字段覆盖", "", "| 字段 | 动态消息覆盖 | MMSI静态覆盖 |", "| --- | ---: | ---: |"]
    for field in ["mmsi", "lat", "lon", "sog", "cog", "true_heading", "rate_of_turn", "navigational_status", "vessel_name", "imo", "vessel_type", "draught", "ship_length", "ship_width"]:
        dynamic_rate = summary["dynamic_coverage"].get(field)
        static_rate = summary["unique_mmsi_static_coverage"].get(field, {}).get("rate")
        dynamic_text = f"{dynamic_rate:.2%}" if dynamic_rate is not None else ""
        static_text = f"{static_rate:.2%}" if static_rate is not None else ""
        lines.append(f"| `{field}` | {dynamic_text} | {static_text} |")
    lines += ["", "## 负责人结论", ""]
    if verdict == "PASS":
        lines.append("本批次满足当前模式的质量门槛。预采集模式通过后，允许启动一个六小时正式窗口；正式模式通过后，才允许纳入累计分类审计。")
    else:
        lines.append("本批次未通过质量门槛，禁止直接延长采集。失败项：" + "、".join(failed) + "。应先结合原始 JSON 和连接日志定位原因。")
    lines.append("静态字段来自较低频广播，空值不等于解析器偷工减料；报告按唯一 MMSI 统计真实覆盖率，不把动态行的正常空值伪装成字段丢失。")
    (batch_dir / "batch_quality_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "failed_checks": failed, "summary": str(batch_dir / "batch_quality_summary.json")}, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit one reusable Malacca AIS collection batch.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--raw-jsonl", type=Path, required=True)
    parser.add_argument("--connection-events", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--mode", choices=["preflight", "formal"], default="preflight")
    args = parser.parse_args()
    summary = audit(args.input, args.raw_jsonl, args.connection_events, args.runtime, args.mode)
    raise SystemExit(0 if summary["verdict"] == "PASS" else 2)


if __name__ == "__main__":
    main()
