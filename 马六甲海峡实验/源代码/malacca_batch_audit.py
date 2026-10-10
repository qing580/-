import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from classification_audit import category, write_csv
from classification_feature_ablation import build_features, run as run_ablation


IMPORTANT_FIELDS = [
    "mmsi",
    "lat",
    "lon",
    "sog",
    "cog",
    "true_heading",
    "rate_of_turn",
    "navigational_status",
    "vessel_name",
    "call_sign",
    "imo",
    "vessel_type",
    "destination",
    "draught",
    "ship_length",
    "ship_width",
    "raw_json",
]


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def number(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except ValueError:
        return None


def row_key(row):
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collect_inputs(paths):
    rows, files, seen = [], [], set()
    for path in paths:
        raw = read_rows(path)
        before = len(rows)
        for row in raw:
            key = row_key(row)
            if key in seen:
                continue
            seen.add(key)
            row = dict(row)
            row["batch_source_file"] = path.name
            rows.append(row)
        files.append(
            {
                "文件名": path.name,
                "路径": str(path),
                "原始行数": len(raw),
                "合并新增行数": len(rows) - before,
                "SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return rows, files


def write_combined(path, rows):
    if not rows:
        raise RuntimeError("No rows to write")
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def field_coverage(rows):
    out = []
    total = len(rows)
    for field in IMPORTANT_FIELDS:
        filled = sum(1 for r in rows if str(r.get(field, "")).strip() not in ("", "0x0"))
        out.append({"字段": field, "非空行数": filled, "总行数": total, "覆盖率": filled / total if total else 0})
    return out


def vessel_type_stats(rows):
    by_mmsi = {}
    for r in rows:
        mmsi = str(r.get("mmsi", "")).strip()
        vt = number(r.get("vessel_type"))
        if not mmsi or vt is None or vt != int(vt) or not (0 < vt <= 255):
            continue
        by_mmsi.setdefault(mmsi, Counter())[int(vt)] += 1
    categories = Counter()
    conflicts = 0
    for counts in by_mmsi.values():
        codes = counts.most_common()
        if len(codes) > 1 and codes[0][1] == codes[1][1]:
            conflicts += 1
            categories["编码冲突"] += 1
        else:
            categories[category(codes[0][0])] += 1
    return by_mmsi, categories, conflicts


def report(out, input_files, rows, archive, features, coverage, categories, target_eligible):
    cargo = sum(1 for r in features if r["label"] == "货船")
    tanker = sum(1 for r in features if r["label"] == "油轮")
    eligible = len(features)
    estimated_test = round(eligible * 0.2)
    need = max(0, target_eligible - eligible)
    status = "达到当前停止条件" if eligible >= target_eligible else "继续扩样"
    lines = [
        "# 马六甲增强 AIS 累计批次审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}。",
        "",
        "## 结论",
        "",
        f"累计合并 {len(input_files)} 个增强 AIS CSV，共 {len(rows)} 行。按轨迹质量筛选后，货船/油轮候选为 {eligible} 艘，其中货船 {cargo} 艘、油轮 {tanker} 艘。",
        f"若继续按 20% 留作测试，预计测试集约 {estimated_test} 艘。目标候选船为 {target_eligible} 艘，当前还差约 {need} 艘。当前状态：{status}。",
        "",
        "这个审计只统计马六甲/新加坡海峡增强采集数据，不混入 NOAA、休斯敦、纽约等外部海域数据。",
        "",
        "## 输入批次",
        "",
        "| 文件 | 原始行数 | 合并新增行数 |",
        "| --- | ---: | ---: |",
    ]
    for item in input_files:
        lines.append(f"| `{item['文件名']}` | {item['原始行数']} | {item['合并新增行数']} |")

    lines += [
        "",
        "## 船型弱标签统计",
        "",
        "| 类别 | MMSI 数 |",
        "| --- | ---: |",
    ]
    for name, count in categories.most_common():
        lines.append(f"| {name} | {count} |")

    lines += [
        "",
        "## 关键字段行级覆盖",
        "",
        "| 字段 | 非空行数 | 覆盖率 |",
        "| --- | ---: | ---: |",
    ]
    for item in coverage:
        lines.append(f"| `{item['字段']}` | {item['非空行数']} | {item['覆盖率']:.2%} |")

    lines += [
        "",
        "## 负责人判断",
        "",
        "如果累计候选船增长速度接近当前估计，继续分批实时采集是可行的；如果新增 6 小时窗口只带来很少新候选船，说明重复 MMSI 较多或静态船型覆盖不足，应停止盲目实时采集，转向马六甲历史 AIS 购买/申请方案。",
        "",
        "当前输出中的分类消融结果仍是 AIS 弱标签验证，不是论文最终真实船型准确率。正式论文结论必须使用封存日期/批次，或进行外部船舶登记核验。",
    ]
    (out / "累计批次审计报告.md").write_text("\n".join(lines), encoding="utf-8")


def run(input_paths, out, target_eligible):
    out.mkdir(parents=True, exist_ok=True)
    rows, input_files = collect_inputs(input_paths)
    combined = out / "马六甲增强AIS累计合并.csv"
    write_combined(combined, rows)

    archive, features = build_features(rows)
    coverage = field_coverage(rows)
    _, categories, conflicts = vessel_type_stats(rows)

    write_csv(out / "输入批次清单.csv", input_files)
    write_csv(out / "累计字段覆盖.csv", coverage)
    write_csv(out / "累计船舶档案.csv", archive)
    write_csv(out / "累计货船油轮候选特征.csv", features)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_file_count": len(input_files),
        "rows": len(rows),
        "unique_mmsi": len({str(r.get("mmsi", "")).strip() for r in rows if str(r.get("mmsi", "")).strip()}),
        "message_types": dict(Counter(r.get("message_type", "") for r in rows)),
        "vessel_categories": dict(categories),
        "vessel_type_conflicts": conflicts,
        "eligible_cargo_tanker": len(features),
        "eligible_by_label": dict(Counter(r["label"] for r in features)),
        "estimated_test_20pct": round(len(features) * 0.2),
        "target_eligible": target_eligible,
        "remaining_to_target": max(0, target_eligible - len(features)),
        "combined_csv": str(combined),
    }
    (out / "累计审计摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report(out, input_files, rows, archive, features, coverage, categories, target_eligible)

    ablation_out = out / "累计分类消融"
    run_ablation(combined, ablation_out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=Path, help="One enhanced Malacca AIS CSV. Can be repeated.")
    parser.add_argument("--raw-dir", type=Path, default=Path.home() / "Desktop" / "马六甲海峡实验" / "原始数据")
    parser.add_argument("--glob", default="malacca_enhanced_ais_*.csv")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--target-eligible", type=int, default=500)
    args = parser.parse_args()

    input_paths = args.input or sorted(args.raw_dir.glob(args.glob))
    input_paths = [p for p in input_paths if p.exists() and p.is_file()]
    if not input_paths:
        raise SystemExit("No input CSV files found.")
    output = args.output or (Path.home() / "Desktop" / "马六甲海峡实验" / "运行结果" / f"马六甲增强AIS累计审计_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}")
    run(input_paths, output, args.target_eligible)


if __name__ == "__main__":
    main()
