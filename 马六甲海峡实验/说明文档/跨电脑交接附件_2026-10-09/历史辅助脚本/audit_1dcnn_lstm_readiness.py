import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


INPUT = Path(r"C:\Users\卿之ya\Documents\ChatGPT\大创\analysis\AIS累计审计_2026-09-15\马六甲增强AIS累计合并.csv")
OUTPUT = Path(__file__).with_name("1DCNN_LSTM数据适配审计_2026-09-15.json")


def number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def category(code):
    if 70 <= code <= 79:
        return "货船"
    if 80 <= code <= 89:
        return "油轮"
    if 60 <= code <= 69:
        return "客船"
    if code == 30:
        return "渔船"
    return "其他"


def quantiles(values):
    if not values:
        return {}
    ordered = sorted(values)
    def q(fraction):
        return ordered[round((len(ordered) - 1) * fraction)]
    return {"min": ordered[0], "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "p90": q(0.9), "max": ordered[-1]}


def split_segments(points, max_gap_seconds=600):
    segments = []
    current = []
    for point in points:
        if current and (point[0] - current[-1][0]).total_seconds() > max_gap_seconds:
            segments.append(current)
            current = []
        current.append(point)
    if current:
        segments.append(current)
    return segments


def main():
    groups = defaultdict(list)
    codes = defaultdict(Counter)
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            mmsi = str(row.get("mmsi", "")).strip()
            if not mmsi:
                continue
            code = number(row.get("vessel_type"))
            if code is not None and code == int(code) and 0 < code <= 255:
                codes[mmsi][int(code)] += 1
            if row.get("message_type") != "PositionReport":
                continue
            try:
                moment = datetime.fromisoformat(str(row.get("received_at", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            lat, lon, sog, cog = (number(row.get(field)) for field in ("lat", "lon", "sog", "cog"))
            if lat is None or lon is None or sog is None or cog is None:
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= sog < 102.3 and 0 <= cog < 360):
                continue
            groups[mmsi].append((moment, lat, lon, sog, cog))

    labels = {}
    for mmsi, counts in codes.items():
        top = counts.most_common()
        if top and (len(top) == 1 or top[0][1] > top[1][1]):
            labels[mmsi] = category(top[0][0])

    class_counts = Counter(labels.values())
    segment_lengths = []
    longest_by_vessel = []
    intervals = []
    windows = {16: 0, 32: 0, 64: 0, 128: 0}
    vessels_with_windows = {length: set() for length in windows}
    class_windows = {length: Counter() for length in windows}

    for mmsi, label in labels.items():
        if label not in {"货船", "油轮"}:
            continue
        points = sorted(set(groups.get(mmsi, [])))
        segments = split_segments(points)
        longest_by_vessel.append(max((len(segment) for segment in segments), default=0))
        for segment in segments:
            segment_lengths.append(len(segment))
            intervals.extend((b[0] - a[0]).total_seconds() for a, b in zip(segment, segment[1:]))
            for length in windows:
                stride = length // 2
                count = 0 if len(segment) < length else 1 + (len(segment) - length) // stride
                if count:
                    windows[length] += count
                    class_windows[length][label] += count
                    vessels_with_windows[length].add(mmsi)

    payload = {
        "source": str(INPUT),
        "labeled_vessels": dict(class_counts),
        "cargo_tanker_labeled_vessels": class_counts["货船"] + class_counts["油轮"],
        "longest_segment_points": quantiles(longest_by_vessel),
        "all_segment_points": quantiles(segment_lengths),
        "within_segment_interval_seconds": quantiles(intervals),
        "window_policy": "max gap 600 seconds; 50% overlap; no cross-vessel or cross-gap windows",
        "windows": {
            str(length): {
                "count": windows[length],
                "vessels": len(vessels_with_windows[length]),
                "by_label": dict(class_windows[length]),
            }
            for length in windows
        },
        "required_fields": {
            "direct": ["mmsi", "received_at", "lat", "lon", "sog", "cog"],
            "available_optional": ["true_heading", "rate_of_turn", "navigational_status", "ship_length", "ship_width", "draught"],
            "derived": ["delta_t", "acceleration", "course_change", "distance", "turn_rate"],
        },
        "readiness": {
            "original_five_class_replication": "not_ready",
            "cargo_tanker_two_class_prototype": "ready_with_constraints",
            "paper_grade_deep_model_claim": "not_ready_without label verification and independent evaluation",
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
