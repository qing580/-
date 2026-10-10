#!/usr/bin/env python3
"""Build a traceable vessel identity query manifest from normalized Malacca AIS CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_BBOX = (1.0, 103.0, 3.5, 104.5)
DYNAMIC_MESSAGE_TYPES = {
    "PositionReport",
    "StandardClassBPositionReport",
    "ExtendedClassBPositionReport",
}

OUTPUT_FIELDS = [
    "mmsi",
    "preferred_imo",
    "imo_candidates",
    "invalid_imo_candidates",
    "imo_status",
    "vessel_name",
    "vessel_name_candidates",
    "call_sign",
    "call_sign_candidates",
    "vessel_type_codes",
    "ais_rough_categories",
    "first_seen_utc",
    "last_seen_utc",
    "total_rows",
    "dynamic_rows",
    "valid_position_rows",
    "in_region_position_rows",
    "out_of_region_position_rows",
    "region_status",
    "source_files",
    "identity_conflict",
    "query_priority",
    "query_value",
]


def open_csv(path: Path):
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            handle = path.open("r", encoding=encoding, newline="")
            handle.read(2048)
            handle.seek(0)
            return handle
        except UnicodeError:
            continue
    return path.open("r", encoding="utf-8", errors="replace", newline="")


def normalize_mmsi(value: object) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{9}", text):
        return text
    if re.fullmatch(r"\d{9}\.0+", text):
        return text.split(".", 1)[0]
    return ""


def normalize_imo(value: object) -> str:
    text = re.sub(r"\s+", "", str(value or "").upper())
    if text.startswith("IMO"):
        text = text[3:]
    if not re.fullmatch(r"\d{7}", text) or text == "0000000":
        return ""
    weighted = sum(int(digit) * weight for digit, weight in zip(text[:6], range(7, 1, -1)))
    return text if weighted % 10 == int(text[-1]) else ""


def is_missing_imo_sentinel(value: object) -> bool:
    text = re.sub(r"\s+", "", str(value or "").upper())
    if text.startswith("IMO"):
        text = text[3:]
    try:
        return float(text) == 0
    except ValueError:
        return False


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def normalize_type_code(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        code = int(float(text))
    except ValueError:
        return ""
    return str(code) if 0 < code <= 255 else ""


def rough_category(code_text: str) -> str:
    if not code_text:
        return ""
    code = int(code_text)
    if code == 30:
        return "fishing"
    if 60 <= code <= 69:
        return "passenger"
    if 70 <= code <= 79:
        return "cargo_unspecified"
    if 80 <= code <= 89:
        return "tanker"
    return "other"


def parse_number(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


def parse_time(row: dict[str, str]) -> datetime | None:
    for field in ("received_at_utc", "received_at", "metadata_time_utc", "timestamp"):
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        candidate = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def preferred(counter: Counter[str]) -> str:
    if not counter:
        return ""
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def joined(counter: Counter[str]) -> str:
    return "|".join(sorted(counter))


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be lat_min,lon_min,lat_max,lon_max")
    lat_min, lon_min, lat_max, lon_max = parts
    if not (-90 <= lat_min < lat_max <= 90 and -180 <= lon_min < lon_max <= 180):
        raise argparse.ArgumentTypeError("bbox coordinates or ordering are invalid")
    return lat_min, lon_min, lat_max, lon_max


def build_manifest(inputs: Iterable[Path], bbox: tuple[float, float, float, float]):
    vessels = defaultdict(
        lambda: {
            "imos": Counter(),
            "invalid_imos": Counter(),
            "names": Counter(),
            "callsigns": Counter(),
            "types": Counter(),
            "sources": set(),
            "times": [],
            "total_rows": 0,
            "dynamic_rows": 0,
            "valid_position_rows": 0,
            "in_region_position_rows": 0,
            "out_of_region_position_rows": 0,
        }
    )
    file_rows = Counter()
    blank_mmsi_rows = 0
    invalid_mmsi_values = Counter()
    lat_min, lon_min, lat_max, lon_max = bbox

    for path in inputs:
        with open_csv(path) as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                file_rows[path.name] += 1
                raw_mmsi = str(row.get("mmsi") or row.get("MMSI") or "").strip()
                mmsi = normalize_mmsi(raw_mmsi)
                if not mmsi:
                    if raw_mmsi:
                        invalid_mmsi_values[raw_mmsi] += 1
                    else:
                        blank_mmsi_rows += 1
                    continue
                vessel = vessels[mmsi]
                vessel["total_rows"] += 1
                vessel["sources"].add(str(row.get("batch_source_file") or path.name).strip())

                timestamp = parse_time(row)
                if timestamp is not None:
                    vessel["times"].append(timestamp)

                raw_imo = str(row.get("imo") or row.get("IMO") or "").strip()
                if raw_imo and not is_missing_imo_sentinel(raw_imo):
                    imo = normalize_imo(raw_imo)
                    if imo:
                        vessel["imos"][imo] += 1
                    else:
                        vessel["invalid_imos"][normalize_text(raw_imo)] += 1

                name = normalize_text(row.get("vessel_name") or row.get("VesselName") or row.get("ship_name"))
                if name:
                    vessel["names"][name] += 1
                callsign = normalize_text(row.get("call_sign") or row.get("CallSign"))
                if callsign:
                    vessel["callsigns"][callsign] += 1
                type_code = normalize_type_code(row.get("vessel_type") or row.get("VesselType"))
                if type_code:
                    vessel["types"][type_code] += 1

                message_type = str(row.get("message_type") or "").strip()
                if message_type in DYNAMIC_MESSAGE_TYPES:
                    vessel["dynamic_rows"] += 1
                    lat = parse_number(row.get("lat") or row.get("LAT") or row.get("latitude"))
                    lon = parse_number(row.get("lon") or row.get("LON") or row.get("longitude"))
                    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
                        vessel["valid_position_rows"] += 1
                        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                            vessel["in_region_position_rows"] += 1
                        else:
                            vessel["out_of_region_position_rows"] += 1

    manifest = []
    for mmsi in sorted(vessels):
        vessel = vessels[mmsi]
        valid_imos = vessel["imos"]
        if len(valid_imos) == 1:
            imo_status = "valid_unique"
            preferred_imo = preferred(valid_imos)
        elif len(valid_imos) > 1:
            imo_status = "conflict"
            preferred_imo = ""
        elif vessel["invalid_imos"]:
            imo_status = "invalid_only"
            preferred_imo = ""
        else:
            imo_status = "missing"
            preferred_imo = ""

        conflicts = []
        if len(valid_imos) > 1:
            conflicts.append("imo")
        if len(vessel["names"]) > 1:
            conflicts.append("vessel_name")
        if len(vessel["callsigns"]) > 1:
            conflicts.append("call_sign")

        out_count = vessel["out_of_region_position_rows"]
        in_count = vessel["in_region_position_rows"]
        if out_count:
            region_status = "mixed_or_outside"
        elif in_count:
            region_status = "inside"
        else:
            region_status = "no_valid_position"

        categories = Counter(rough_category(code) for code in vessel["types"])
        categories.pop("", None)
        times = vessel["times"]
        query_priority = "imo" if preferred_imo else "mmsi"
        manifest.append(
            {
                "mmsi": mmsi,
                "preferred_imo": preferred_imo,
                "imo_candidates": joined(valid_imos),
                "invalid_imo_candidates": joined(vessel["invalid_imos"]),
                "imo_status": imo_status,
                "vessel_name": preferred(vessel["names"]),
                "vessel_name_candidates": joined(vessel["names"]),
                "call_sign": preferred(vessel["callsigns"]),
                "call_sign_candidates": joined(vessel["callsigns"]),
                "vessel_type_codes": joined(vessel["types"]),
                "ais_rough_categories": joined(categories),
                "first_seen_utc": min(times).isoformat() if times else "",
                "last_seen_utc": max(times).isoformat() if times else "",
                "total_rows": vessel["total_rows"],
                "dynamic_rows": vessel["dynamic_rows"],
                "valid_position_rows": vessel["valid_position_rows"],
                "in_region_position_rows": in_count,
                "out_of_region_position_rows": out_count,
                "region_status": region_status,
                "source_files": "|".join(sorted(vessel["sources"])),
                "identity_conflict": "|".join(conflicts),
                "query_priority": query_priority,
                "query_value": preferred_imo or mmsi,
            }
        )

    return manifest, {
        "input_files": [str(path.resolve()) for path in inputs],
        "bbox": list(bbox),
        "input_rows_by_file": dict(file_rows),
        "blank_mmsi_rows": blank_mmsi_rows,
        "invalid_mmsi_values": dict(sorted(invalid_mmsi_values.items())),
        "invalid_mmsi_rows": sum(invalid_mmsi_values.values()),
    }


def summarize(manifest: list[dict[str, object]], metadata: dict[str, object]) -> dict[str, object]:
    category_counts = Counter()
    for row in manifest:
        categories = str(row["ais_rough_categories"] or "unknown").split("|")
        category_counts.update(categories)
    total = len(manifest)
    valid_imo = sum(row["imo_status"] == "valid_unique" for row in manifest)
    imo_status_counts = Counter(str(row["imo_status"]) for row in manifest)
    identity_conflicts = sum(bool(row["identity_conflict"]) for row in manifest)
    region_anomalies = sum(row["region_status"] == "mixed_or_outside" for row in manifest)
    no_valid_position = sum(row["region_status"] == "no_valid_position" for row in manifest)
    summary = {
        **metadata,
        "unique_valid_mmsi": total,
        "valid_unique_imo_vessels": valid_imo,
        "valid_unique_imo_coverage_pct": round(valid_imo / total * 100, 2) if total else 0.0,
        "imo_status_vessel_counts": dict(sorted(imo_status_counts.items())),
        "identity_conflict_vessels": identity_conflicts,
        "region_anomaly_vessels": region_anomalies,
        "no_valid_position_vessels": no_valid_position,
        "ais_rough_category_vessel_counts": dict(sorted(category_counts.items())),
        "status": "inventory_only_not_external_label_validation",
    }
    return summary


def write_outputs(output_dir: Path, manifest: list[dict[str, object]], summary: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "vessel_query_manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(manifest)
    with (output_dir / "manifest_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with (output_dir / "invalid_mmsi_report.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["raw_mmsi", "row_count", "decision"])
        writer.writeheader()
        for raw_mmsi, row_count in summary["invalid_mmsi_values"].items():
            writer.writerow(
                {
                    "raw_mmsi": raw_mmsi,
                    "row_count": row_count,
                    "decision": "isolated_not_padded_not_queried",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an MMSI/IMO query manifest from normalized Malacca AIS CSV files.")
    parser.add_argument("--input", nargs="+", required=True, type=Path, help="One or more normalized AIS CSV files.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--bbox", type=parse_bbox, default=DEFAULT_BBOX)
    args = parser.parse_args()
    missing = [path for path in args.input if not path.is_file()]
    if missing:
        parser.error("input file not found: " + ", ".join(str(path) for path in missing))
    manifest, metadata = build_manifest(args.input, args.bbox)
    summary = summarize(manifest, metadata)
    write_outputs(args.output_dir, manifest, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
