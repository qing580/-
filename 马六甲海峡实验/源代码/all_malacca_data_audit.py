import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


DEFAULT_FILES = [
    r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\malacca_enhanced_ais_0p5h_2026-09-07_194446_570.csv",
    r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\malacca_enhanced_ais_6h_2026-09-08_123520_473.csv",
    r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\马六甲1小时AIS采集数据_实时可见版.csv",
    r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\马六甲1小时AIS采集数据_用于新版Demo.csv",
    r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\马六甲6小时AIS采集数据_2026-09-05.csv",
    r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\马六甲10分钟AIS采集数据.csv",
    r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\马六甲测试AIS采集数据.csv",
]

CANONICAL_FIELDS = [
    "mmsi",
    "timestamp",
    "received_at",
    "lat",
    "lon",
    "sog",
    "cog",
    "heading",
    "rate_of_turn",
    "nav_status",
    "vessel_type",
    "vessel_name",
    "call_sign",
    "imo",
    "destination",
    "draught",
    "ship_length",
    "ship_width",
    "message_type",
    "source",
    "schema_group",
    "source_file",
]

ALIASES = {
    "mmsi": ["mmsi", "MMSI"],
    "timestamp": ["timestamp", "ais_timestamp", "metadata_time_utc", "BaseDateTime"],
    "received_at": ["received_at"],
    "lat": ["lat", "LAT", "latitude"],
    "lon": ["lon", "LON", "longitude"],
    "sog": ["sog", "SOG"],
    "cog": ["cog", "COG"],
    "heading": ["heading", "true_heading", "Heading"],
    "rate_of_turn": ["rate_of_turn", "ROT"],
    "nav_status": ["nav_status", "navigational_status", "Status"],
    "vessel_type": ["vessel_type", "VesselType"],
    "vessel_name": ["vessel_name", "VesselName", "ship_name"],
    "call_sign": ["call_sign", "CallSign"],
    "imo": ["imo", "IMO"],
    "destination": ["destination", "Destination"],
    "draught": ["draught", "Draft"],
    "ship_length": ["ship_length", "Length"],
    "ship_width": ["ship_width", "Width"],
    "message_type": ["message_type"],
    "source": ["source"],
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def open_csv(path: Path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            f = path.open("r", encoding=enc, newline="")
            sample = f.read(2048)
            f.seek(0)
            sample.encode(enc)
            return f
        except UnicodeError:
            continue
    return path.open("r", encoding="utf-8", errors="replace", newline="")


def pick(row, canonical):
    for name in ALIASES[canonical]:
        if name in row:
            return (row.get(name) or "").strip()
    return ""


def normalize_type(value):
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        return str(int(float(value)))
    except ValueError:
        return value


def type_category(value):
    value = normalize_type(value)
    if not value:
        return ""
    try:
        code = int(value)
    except ValueError:
        lowered = value.lower()
        if "cargo" in lowered:
            return "cargo"
        if "tanker" in lowered:
            return "tanker"
        return "other"
    if 70 <= code <= 79:
        return "cargo"
    if 80 <= code <= 89:
        return "tanker"
    return "other"


def paper_label(value):
    cat = type_category(value)
    if cat == "cargo":
        return "货船"
    if cat == "tanker":
        return "油轮"
    if cat:
        return "其他编码"
    return "未知"


def number(value):
    try:
        x = float(value)
        if x == x and x not in (float("inf"), float("-inf")):
            return x
    except (TypeError, ValueError):
        return None
    return None


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def classification_ready(rows_subset):
    groups = defaultdict(list)
    for row in rows_subset:
        mmsi = (row.get("mmsi") or "").strip()
        if mmsi:
            groups[mmsi].append(row)
    ready = Counter()
    label_only = Counter()
    quality_rows = []
    for mmsi, records in groups.items():
        codes = sorted(
            {
                int(x)
                for r in records
                if (x := number(r.get("vessel_type"))) is not None
                and x == int(x)
                and 0 < x <= 255
            }
        )
        label = paper_label(codes[0]) if len(codes) == 1 else ("编码冲突" if codes else "未知")
        if label in {"货船", "油轮"}:
            label_only[label] += 1
        points = []
        invalid = 0
        for r in records:
            if r.get("message_type") != "PositionReport":
                continue
            t = parse_time(r.get("received_at") or r.get("timestamp"))
            lat, lon, sog = number(r.get("lat")), number(r.get("lon")), number(r.get("sog"))
            if t is None or lat is None or lon is None or sog is None:
                invalid += 1
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= sog < 102.3):
                invalid += 1
                continue
            points.append((t, lat, lon, sog, r.get("cog") or ""))
        points = sorted(set(points), key=lambda p: (p[0], p[1], p[2], p[3], p[4]))
        same_time = sum(a[0] == b[0] for a, b in zip(points, points[1:]))
        segments, current = [], []
        for p in points:
            if current and (p[0] - current[-1][0]).total_seconds() > 600:
                segments.append(current)
                current = []
            current.append(p)
        if current:
            segments.append(current)
        longest = max((len(s) for s in segments), default=0)
        is_ready = label in {"货船", "油轮"} and longest >= 10 and same_time == 0
        if is_ready:
            ready[label] += 1
        quality_rows.append(
            {
                "mmsi": mmsi,
                "label": label,
                "valid_position_points": len(points),
                "invalid_position_points": invalid,
                "same_time_conflicts": same_time,
                "longest_segment_points": longest,
                "classification_ready": is_ready,
            }
        )
    return {
        "label_only_cargo_tanker_mmsi": label_only["货船"] + label_only["油轮"],
        "label_only_cargo_mmsi": label_only["货船"],
        "label_only_tanker_mmsi": label_only["油轮"],
        "ready_cargo_tanker_mmsi": ready["货船"] + ready["油轮"],
        "ready_cargo_mmsi": ready["货船"],
        "ready_tanker_mmsi": ready["油轮"],
        "estimated_test_mmsi_at_20pct": round((ready["货船"] + ready["油轮"]) * 0.2),
        "quality_rows": quality_rows,
    }


def schema_group(headers):
    hs = set(headers)
    if {"collector_version", "raw_json", "ship_length", "ship_width", "draught"} <= hs:
        return "enhanced_full_static"
    if "vessel_type" in hs:
        return "old_partial_static"
    return "old_dynamic_only"


def summarize_file(path: Path, is_duplicate: bool):
    h = sha256_file(path)
    with open_csv(path) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        group = schema_group(headers)
        row_count = 0
        coverage = Counter()
        msg_counts = Counter()
        mmsi_profiles = defaultdict(lambda: Counter())
        canonical_rows = []
        for row in reader:
            row_count += 1
            normalized = {field: pick(row, field) for field in CANONICAL_FIELDS if field not in {"schema_group", "source_file"}}
            normalized["vessel_type"] = normalize_type(normalized["vessel_type"])
            normalized["schema_group"] = group
            normalized["source_file"] = path.name
            canonical_rows.append(normalized)
            for field in CANONICAL_FIELDS:
                if field in {"schema_group", "source_file"}:
                    continue
                if normalized.get(field):
                    coverage[field] += 1
            msg_counts[normalized.get("message_type") or "(blank)"] += 1
            mmsi = normalized.get("mmsi")
            if mmsi:
                cat = type_category(normalized.get("vessel_type"))
                if cat:
                    mmsi_profiles[mmsi][cat] += 1
        type_by_mmsi = {}
        for mmsi, counts in mmsi_profiles.items():
            if counts:
                type_by_mmsi[mmsi] = counts.most_common(1)[0][0]
        return {
            "path": str(path),
            "name": path.name,
            "sha256": h,
            "duplicate_file": is_duplicate,
            "schema_group": group,
            "headers": headers,
            "rows": row_count,
            "columns": len(headers),
            "coverage": dict(coverage),
            "message_type_counts": dict(msg_counts),
            "unique_mmsi": len({r.get("mmsi") for r in canonical_rows if r.get("mmsi")}),
            "mmsi_with_vessel_type": sum(1 for v in type_by_mmsi.values() if v in {"cargo", "tanker", "other"}),
            "cargo_mmsi": sum(1 for v in type_by_mmsi.values() if v == "cargo"),
            "tanker_mmsi": sum(1 for v in type_by_mmsi.values() if v == "tanker"),
            "canonical_rows": canonical_rows,
        }


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def pct(n, d):
    return 0.0 if not d else 100.0 * n / d


def build_report(summary, out_dir: Path):
    target = summary["target_eligible_mmsi"]
    strict = summary["strict_enhanced"]
    all_usable = summary["all_unique"]
    strict_ready = summary["strict_enhanced_classification_ready"]
    all_ready = summary["all_unique_classification_ready"]
    strict_need = max(0, target - strict_ready["ready_cargo_tanker_mmsi"])
    weak_need = max(0, target - all_ready["ready_cargo_tanker_mmsi"])
    lines = [
        "# 全部马六甲历史采集数据整合审计",
        "",
        f"- 审计时间: {summary['generated_at']}",
        f"- 输入文件数: {summary['input_file_count']}；完全重复文件数: {summary['duplicate_file_count']}",
        f"- 去重后总行数: {all_usable['rows']}；去重后有效 MMSI: {all_usable['valid_mmsi']}",
        "",
        "## 结论",
        "",
        f"1. 严格增强数据中，只有唯一明确船型标签的货船/油轮 MMSI 为 **{strict_ready['label_only_cargo_tanker_mmsi']}** 艘；同时满足当前分类实验轨迹质量要求的为 **{strict_ready['ready_cargo_tanker_mmsi']}** 艘，其中货船 {strict_ready['ready_cargo_mmsi']}、油轮 {strict_ready['ready_tanker_mmsi']}。按 20% 测试集估算，测试集约 **{strict_ready['estimated_test_mmsi_at_20pct']}** 艘。",
        f"2. 如果把旧版缺少船长/船宽/吃水的文件也作为弱辅助数据，只有唯一明确船型标签的货船/油轮 MMSI 为 **{all_ready['label_only_cargo_tanker_mmsi']}** 艘；满足轨迹质量要求的为 **{all_ready['ready_cargo_tanker_mmsi']}** 艘，其中货船 {all_ready['ready_cargo_mmsi']}、油轮 {all_ready['ready_tanker_mmsi']}。这些旧数据不能直接替代增强主实验。",
        f"3. 以主实验目标 {target} 艘“分类可用”货船/油轮 MMSI 计，严格增强数据还差 **{strict_need}** 艘；即使计入旧版弱辅助数据，还差 **{weak_need}** 艘。",
        "",
        "## 文件级审计",
        "",
        "| 文件 | 行数 | 类型 | 重复 | 有 vessel_type 的 MMSI | 货船 MMSI | 油轮 MMSI | 说明 |",
        "|---|---:|---|---|---:|---:|---:|---|",
    ]
    for item in summary["files"]:
        note = "主实验可用" if item["schema_group"] == "enhanced_full_static" else ("弱辅助: 缺少尺度/吃水" if item["schema_group"] == "old_partial_static" else "动态轨迹辅助: 无 vessel_type")
        lines.append(
            f"| {item['name']} | {item['rows']} | {item['schema_group']} | {'是' if item['duplicate_file'] else '否'} | {item['mmsi_with_vessel_type']} | {item['cargo_mmsi']} | {item['tanker_mmsi']} | {note} |"
        )
    lines.extend([
        "",
        "## 字段判断",
        "",
        "- `mmsi`、`lat`、`lon`、`sog`、`cog`、`heading`、`rate_of_turn`、`nav_status` 是动态行为特征，旧版和增强版都能部分贡献。",
        "- `vessel_type` 是监督分类标签，只能用于训练/验证标签，不能作为模型输入特征。",
        "- `ship_length`、`ship_width`、`draught` 是提高船舶类型分类的重要静态尺度特征；这次只有增强版采集包含这些字段，所以旧版数据不能完全解决测试集不足问题。",
        "- 两个 1 小时 CSV 文件哈希完全相同，已按一个文件计入，不能重复扩样。",
        "",
        "## 下一步负责人决策",
        "",
        "- 主实验不要把旧版数据和增强数据混成一个“完整静态特征”训练集，否则会制造缺失偏差，论文里也站不住。",
        "- 旧版数据可以做两个用途：一是动态轨迹基线/消融实验，二是帮助检查马六甲区域航速、转向、停泊等行为特征是否稳定。",
        "- 继续采集或购买/下载历史 AIS 时，必须优先保证增强字段完整，尤其是 `vessel_type`、船长、船宽、吃水、IMO、船名与动态轨迹字段。",
    ])
    if strict_ready["estimated_hours_for_remaining"] is not None:
        lines.append(f"- 按当前增强数据的分类可用样本产出速率粗估，还需约 **{strict_ready['estimated_hours_for_remaining']:.1f} 小时** 同区域增强采集；考虑连接中断和重复 MMSI，建议安排 **18-24 小时** 或直接采购/申请马六甲历史 AIS。")
    report_path = out_dir / "全部历史采集数据整合分析报告.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=r"C:\Users\卿之ya\Desktop\马六甲海峡实验\运行结果\全部马六甲历史采集整合审计_2026-09-09")
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("files", nargs="*", default=DEFAULT_FILES)
    args = parser.parse_args()

    paths = [Path(p) for p in args.files]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    hashes = {}
    duplicate_hashes = set()
    for path in paths:
        h = sha256_file(path)
        if h in hashes:
            duplicate_hashes.add(h)
        hashes[h] = hashes.get(h, []) + [path.name]

    files = []
    unique_rows = {}
    for path in paths:
        h = sha256_file(path)
        is_duplicate = len(hashes[h]) > 1 and hashes[h][0] != path.name
        item = summarize_file(path, is_duplicate)
        for row in item.pop("canonical_rows"):
            if is_duplicate:
                continue
            key = tuple(row.get(f, "") for f in CANONICAL_FIELDS if f != "source_file")
            unique_rows[key] = row
        files.append(item)

    rows = list(unique_rows.values())
    strict_rows = [r for r in rows if r["schema_group"] == "enhanced_full_static"]

    def aggregate(rows_subset):
        profiles = defaultdict(lambda: {"types": Counter(), "rows": 0})
        for row in rows_subset:
            mmsi = row.get("mmsi")
            if not mmsi:
                continue
            profiles[mmsi]["rows"] += 1
            cat = type_category(row.get("vessel_type"))
            if cat:
                profiles[mmsi]["types"][cat] += 1
        cargo = tanker = other = 0
        for profile in profiles.values():
            if not profile["types"]:
                continue
            top = profile["types"].most_common(1)[0][0]
            if top == "cargo":
                cargo += 1
            elif top == "tanker":
                tanker += 1
            else:
                other += 1
        coverage = Counter()
        for row in rows_subset:
            for field in CANONICAL_FIELDS:
                if field in {"schema_group", "source_file"}:
                    continue
                if row.get(field):
                    coverage[field] += 1
        return {
            "rows": len(rows_subset),
            "valid_mmsi": len(profiles),
            "cargo_mmsi": cargo,
            "tanker_mmsi": tanker,
            "other_type_mmsi": other,
            "eligible_cargo_tanker_mmsi": cargo + tanker,
            "coverage": dict(coverage),
        }

    strict = aggregate(strict_rows)
    all_unique = aggregate(rows)
    strict_ready = classification_ready(strict_rows)
    all_ready = classification_ready(rows)
    if strict_ready["ready_cargo_tanker_mmsi"]:
        hours_observed = 6.5
        rate = strict_ready["ready_cargo_tanker_mmsi"] / hours_observed
        strict_ready["estimated_hours_for_remaining"] = max(0, args.target - strict_ready["ready_cargo_tanker_mmsi"]) / rate
    else:
        strict_ready["estimated_hours_for_remaining"] = None

    file_rows = []
    for item in files:
        row = {k: item[k] for k in ["name", "path", "sha256", "duplicate_file", "schema_group", "rows", "columns", "mmsi_with_vessel_type", "cargo_mmsi", "tanker_mmsi"]}
        for field in ["mmsi", "lat", "lon", "sog", "cog", "heading", "rate_of_turn", "nav_status", "vessel_type", "ship_length", "ship_width", "draught"]:
            row[f"{field}_coverage_pct"] = f"{pct(item['coverage'].get(field, 0), item['rows']):.2f}"
        file_rows.append(row)

    write_csv(out_dir / "全部文件清单与字段审计.csv", file_rows, list(file_rows[0].keys()))
    write_csv(out_dir / "全部文件唯一合并_通用字段.csv", rows, CANONICAL_FIELDS)
    write_csv(out_dir / "增强数据分类可用质量明细.csv", strict_ready.pop("quality_rows"), ["mmsi", "label", "valid_position_points", "invalid_position_points", "same_time_conflicts", "longest_segment_points", "classification_ready"])
    write_csv(out_dir / "全部数据分类可用质量明细.csv", all_ready.pop("quality_rows"), ["mmsi", "label", "valid_position_points", "invalid_position_points", "same_time_conflicts", "longest_segment_points", "classification_ready"])

    profile_rows = []
    by_mmsi = defaultdict(lambda: {"sources": set(), "schemas": set(), "rows": 0, "types": Counter(), "name": "", "imo": "", "length": "", "width": "", "draught": ""})
    for row in rows:
        mmsi = row.get("mmsi")
        if not mmsi:
            continue
        p = by_mmsi[mmsi]
        p["rows"] += 1
        p["sources"].add(row["source_file"])
        p["schemas"].add(row["schema_group"])
        cat = type_category(row.get("vessel_type"))
        if cat:
            p["types"][cat] += 1
        for src, dst in [("vessel_name", "name"), ("imo", "imo"), ("ship_length", "length"), ("ship_width", "width"), ("draught", "draught")]:
            if row.get(src) and not p[dst]:
                p[dst] = row[src]
    for mmsi, p in sorted(by_mmsi.items()):
        top = p["types"].most_common(1)[0][0] if p["types"] else ""
        profile_rows.append({
            "mmsi": mmsi,
            "label_category": top,
            "rows": p["rows"],
            "schemas": ";".join(sorted(p["schemas"])),
            "source_files": ";".join(sorted(p["sources"])),
            "vessel_name": p["name"],
            "imo": p["imo"],
            "ship_length": p["length"],
            "ship_width": p["width"],
            "draught": p["draught"],
        })
    write_csv(out_dir / "全部累计船舶档案.csv", profile_rows, ["mmsi", "label_category", "rows", "schemas", "source_files", "vessel_name", "imo", "ship_length", "ship_width", "draught"])

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_eligible_mmsi": args.target,
        "input_file_count": len(paths),
        "duplicate_file_count": sum(1 for f in files if f["duplicate_file"]),
        "duplicate_hash_groups": {h: names for h, names in hashes.items() if len(names) > 1},
        "files": files,
        "all_unique": all_unique,
        "strict_enhanced": strict,
        "all_unique_classification_ready": all_ready,
        "strict_enhanced_classification_ready": strict_ready,
    }
    (out_dir / "全部数据审计摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = build_report(summary, out_dir)
    print(f"Report: {report_path}")
    print(f"Strict enhanced unique-label cargo/tanker MMSI: {strict_ready['label_only_cargo_tanker_mmsi']}")
    print(f"Strict enhanced classification-ready cargo/tanker MMSI: {strict_ready['ready_cargo_tanker_mmsi']}")
    print(f"All unique weak+strict classification-ready cargo/tanker MMSI: {all_ready['ready_cargo_tanker_mmsi']}")
    print(f"Need strict enhanced classification-ready MMSI to target {args.target}: {max(0, args.target - strict_ready['ready_cargo_tanker_mmsi'])}")


if __name__ == "__main__":
    main()
