import argparse
import csv
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlretrieve


OUTPUT_FIELDS = [
    "collector_version",
    "source",
    "bbox",
    "message_type",
    "received_at",
    "metadata_time_utc",
    "ais_timestamp",
    "mmsi",
    "valid",
    "repeat_indicator",
    "message_id",
    "lat",
    "lon",
    "sog",
    "cog",
    "true_heading",
    "rate_of_turn",
    "navigational_status",
    "position_accuracy",
    "raim",
    "special_manoeuvre_indicator",
    "communication_state",
    "assigned_mode",
    "dte",
    "vessel_name",
    "call_sign",
    "imo",
    "vessel_type",
    "ais_version",
    "fix_type",
    "destination",
    "eta_month",
    "eta_day",
    "eta_hour",
    "eta_minute",
    "draught",
    "dimension_to_bow",
    "dimension_to_stern",
    "dimension_to_port",
    "dimension_to_starboard",
    "ship_length",
    "ship_width",
    "vendor_id_name",
    "vendor_id_model",
    "vendor_id_serial",
    "parse_status",
    "parse_error",
    "raw_json",
]


def number(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except ValueError:
        return None


def clean_text(value):
    return str(value or "").strip()


def parse_time(value):
    text = clean_text(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def within_bbox(row, bbox):
    lat = number(row.get("LAT"))
    lon = number(row.get("LON"))
    return lat is not None and lon is not None and bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]


def download_if_needed(url, zip_path):
    if zip_path.exists() and zip_path.stat().st_size > 0:
        return False
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    urlretrieve(url, zip_path)
    return True


def map_row(row, bbox_text):
    dt = parse_time(row.get("BaseDateTime"))
    if not dt:
        return None
    lat = number(row.get("LAT"))
    lon = number(row.get("LON"))
    sog = number(row.get("SOG"))
    if lat is None or lon is None or sog is None:
        return None
    mapped = {field: "" for field in OUTPUT_FIELDS}
    mapped.update(
        {
            "collector_version": "noaa_marinecadastre_mapper_2026-09-08",
            "source": "NOAA MarineCadastre historical AIS",
            "bbox": bbox_text,
            "message_type": "PositionReport",
            "received_at": dt.isoformat(),
            "metadata_time_utc": dt.isoformat(),
            "ais_timestamp": dt.second,
            "mmsi": clean_text(row.get("MMSI")),
            "valid": "True",
            "repeat_indicator": "",
            "message_id": "",
            "lat": lat,
            "lon": lon,
            "sog": sog,
            "cog": clean_text(row.get("COG")),
            "true_heading": clean_text(row.get("Heading")),
            "rate_of_turn": "",
            "navigational_status": clean_text(row.get("Status")),
            "vessel_name": clean_text(row.get("VesselName")),
            "call_sign": clean_text(row.get("CallSign")),
            "imo": clean_text(row.get("IMO")),
            "vessel_type": clean_text(row.get("VesselType")),
            "draught": clean_text(row.get("Draft")),
            "ship_length": clean_text(row.get("Length")),
            "ship_width": clean_text(row.get("Width")),
            "parse_status": "parsed",
            "raw_json": json.dumps(row, ensure_ascii=False),
        }
    )
    return mapped


def convert(zip_path, output_path, bbox, max_rows=None, max_hours=None):
    bbox_text = f"[[{bbox[0]},{bbox[1]}],[{bbox[2]},{bbox[3]}]]"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {"read": 0, "bbox_rows": 0, "written": 0, "skipped_missing": 0}
    mmsi = set()
    vessel_types = {}
    first_time = None

    with zipfile.ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if not names:
            raise RuntimeError(f"No CSV found inside {zip_path}")
        with zf.open(names[0]) as raw, output_path.open("w", encoding="utf-8-sig", newline="") as fout:
            reader = csv.DictReader((line.decode("utf-8", errors="replace") for line in raw))
            writer = csv.DictWriter(fout, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            for row in reader:
                counts["read"] += 1
                if not within_bbox(row, bbox):
                    continue
                counts["bbox_rows"] += 1
                dt = parse_time(row.get("BaseDateTime"))
                if not dt:
                    counts["skipped_missing"] += 1
                    continue
                if first_time is None:
                    first_time = dt
                if max_hours is not None and (dt - first_time).total_seconds() > max_hours * 3600:
                    break
                mapped = map_row(row, bbox_text)
                if mapped is None:
                    counts["skipped_missing"] += 1
                    continue
                writer.writerow(mapped)
                counts["written"] += 1
                m = mapped["mmsi"]
                if m:
                    mmsi.add(m)
                    vt = mapped["vessel_type"]
                    if vt:
                        vessel_types[m] = vt
                if max_rows is not None and counts["written"] >= max_rows:
                    break
                if counts["written"] and counts["written"] % 10000 == 0:
                    print(f"written={counts['written']} unique_mmsi={len(mmsi)}")

    summary = {
        **counts,
        "unique_mmsi": len(mmsi),
        "mmsi_with_vessel_type": len(vessel_types),
        "bbox": bbox,
        "source_zip": str(zip_path),
        "source_zip_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        "output": str(output_path),
    }
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2023/AIS_2023_01_01.zip")
    p.add_argument("--zip-path", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--bbox", nargs=4, type=float, metavar=("MIN_LAT", "MIN_LON", "MAX_LAT", "MAX_LON"), default=[40.45, -74.35, 40.95, -73.55])
    p.add_argument("--max-rows", type=int, default=120000)
    p.add_argument("--max-hours", type=float, default=6)
    args = p.parse_args()

    downloaded = download_if_needed(args.url, args.zip_path)
    summary = convert(args.zip_path, args.output, args.bbox, args.max_rows, args.max_hours)
    summary["downloaded"] = downloaded
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
