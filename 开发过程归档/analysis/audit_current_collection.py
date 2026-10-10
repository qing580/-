import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


SOURCE_DIR = Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\源代码")
sys.path.insert(0, str(SOURCE_DIR))

from classification_feature_ablation import build_features  # noqa: E402


DYNAMIC_TYPES = {
    "PositionReport",
    "StandardClassBPositionReport",
    "ExtendedClassBPositionReport",
}

INPUTS = [
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\malacca_enhanced_ais_0p5h_2026-09-07_194446_570.csv"),
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\malacca_enhanced_ais_6h_2026-09-08_123520_473.csv"),
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\batches\formal_6h_2026-09-09_124141_605\normalized_events.csv"),
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\batches\formal_6h_2026-09-13_123437_689\normalized_events.csv"),
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\batches\formal_6h_2026-09-14_131740_539\normalized_events.csv"),
    Path(r"C:\Users\卿之ya\Documents\xwechat_files\wxid_0ybhi61e8yog22_5f4c\msg\file\2026-09\normalized_events.csv"),
]


def present(value):
    return value is not None and str(value).strip() not in {"", "0x0"}


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_time(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def row_hash(row):
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def mmsi_set(rows):
    return {str(row.get("mmsi", "")).strip() for row in rows if present(row.get("mmsi"))}


def profile_sets(rows):
    output = {field: set() for field in ["vessel_type", "ship_length", "ship_width", "draught", "imo", "call_sign"]}
    for row in rows:
        mmsi = str(row.get("mmsi", "")).strip()
        if not mmsi:
            continue
        for field in output:
            if present(row.get(field)):
                output[field].add(mmsi)
    return output


def summarize(rows):
    mmsis = mmsi_set(rows)
    profiles = profile_sets(rows)
    dynamic = [row for row in rows if row.get("message_type") in DYNAMIC_TYPES]
    data_rows = [row for row in rows if row.get("parse_status") != "control"]
    parsed = [row for row in data_rows if row.get("parse_status") == "parsed"]
    times = [
        moment
        for row in rows
        if (moment := parse_time(row.get("received_at_utc") or row.get("received_at"))) is not None
    ]
    _, features = build_features(rows)
    eligible = {str(row["mmsi"]): row["label"] for row in features}
    in_bbox = []
    for row in dynamic:
        try:
            lat = float(row.get("lat", ""))
            lon = float(row.get("lon", ""))
        except ValueError:
            continue
        in_bbox.append(1.0 <= lat <= 3.5 and 103.0 <= lon <= 104.5)
    return {
        "rows": len(rows),
        "unique_mmsi": len(mmsis),
        "mmsis": mmsis,
        "messages": Counter(row.get("message_type", "") for row in rows),
        "parse_success": len(parsed) / len(data_rows) if data_rows else 0,
        "dynamic_rows": len(dynamic),
        "dynamic_coverage": {
            field: sum(present(row.get(field)) for row in dynamic) / len(dynamic) if dynamic else 0
            for field in ["mmsi", "lat", "lon", "sog", "cog", "true_heading", "rate_of_turn", "navigational_status"]
        },
        "profile_counts": {field: len(values) for field, values in profiles.items()},
        "profile_coverage": {
            field: len(values) / len(mmsis) if mmsis else 0 for field, values in profiles.items()
        },
        "eligible": eligible,
        "eligible_counts": Counter(eligible.values()),
        "start": min(times).isoformat() if times else "",
        "end": max(times).isoformat() if times else "",
        "bbox_valid": sum(in_bbox) / len(in_bbox) if in_bbox else 0,
        "batch_ids": sorted({row.get("batch_id", "") for row in rows if present(row.get("batch_id"))}),
        "region_ids": sorted({row.get("region_id", "") for row in rows if present(row.get("region_id"))}),
    }


def public(summary):
    return {key: value for key, value in summary.items() if key not in {"mmsis", "eligible"}}


def main():
    per_file = []
    cumulative_rows = []
    seen = set()
    cumulative = []
    previous_mmsis = set()
    previous_eligible = set()

    for path in INPUTS:
        rows = read_rows(path)
        one = summarize(rows)
        one_public = public(one)
        one_public["file"] = str(path)
        one_public["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        one_public["new_mmsi_vs_previous"] = len(one["mmsis"] - previous_mmsis)

        added_rows = 0
        for row in rows:
            digest = row_hash(row)
            if digest in seen:
                continue
            seen.add(digest)
            cumulative_rows.append(row)
            added_rows += 1

        cumulative_summary = summarize(cumulative_rows)
        current_eligible = set(cumulative_summary["eligible"])
        one_public["new_eligible_after_addition"] = len(current_eligible - previous_eligible)
        one_public["added_rows_after_exact_dedup"] = added_rows
        per_file.append(one_public)

        cumulative.append({
            "through_file": path.name,
            "rows": cumulative_summary["rows"],
            "unique_mmsi": cumulative_summary["unique_mmsi"],
            "eligible": len(current_eligible),
            "eligible_counts": cumulative_summary["eligible_counts"],
        })
        previous_mmsis = cumulative_summary["mmsis"]
        previous_eligible = current_eligible

    final = summarize(cumulative_rows)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "per_file": per_file,
        "cumulative": cumulative,
        "final": public(final),
        "remaining_to_500": max(0, 500 - len(final["eligible"])),
        "estimated_test_20pct": round(len(final["eligible"]) * 0.2),
    }
    output = Path(__file__).with_name("AIS采集现状详细审计_2026-09-15.json")
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=dict), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
