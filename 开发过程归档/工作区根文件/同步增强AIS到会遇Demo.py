# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验")
CSV_PATH = ROOT / "原始数据" / "malacca_enhanced_ais_6h_2026-09-08_123520_473.csv"
HTML_PATH = ROOT / "网页演示" / "Demo网页" / "会遇情景演示版" / "会遇情景演示版.html"
OUT_JSON = ROOT / "网页演示" / "Demo网页" / "会遇情景演示版" / "malacca_enhanced_ais_6h_demo_data.json"


ORDER = ["货船", "油轮", "渔船", "客船", "拖船/港口服务船", "游艇/娱乐船", "高速船", "作业船", "其他", "未知"]


def clean(value: object) -> str:
    return str(value or "").strip()


def number(value: object):
    text = clean(value)
    if not text:
        return None
    try:
        n = float(text)
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def category_from_type(raw: object):
    t = number(raw)
    if t is None or t <= 0:
        return "未知", "信息不足", "低", "缺少 AIS vessel_type，暂按未知处理", "是"
    code = int(t)
    if code == 30:
        return "渔船", "作业类船舶", "高", f"AIS 船型码 {code} 表示 Fishing vessel", "否"
    if code in {31, 32, 52, 53}:
        return "拖船/港口服务船", "作业类船舶", "高", f"AIS 船型码 {code} 表示拖带、拖船或港口服务相关船舶", "建议复核"
    if code in {33, 34, 50, 51, 54, 55, 58, 59}:
        return "作业船", "作业类船舶", "高", f"AIS 船型码 {code} 表示引航、搜救、疏浚、潜水、执法或其他专项作业船", "建议复核"
    if code == 36:
        return "游艇/娱乐船", "非重点船舶", "高", f"AIS 船型码 {code} 表示 Sailing vessel", "建议复核"
    if code == 37:
        return "游艇/娱乐船", "非重点船舶", "高", f"AIS 船型码 {code} 表示 Pleasure craft", "建议复核"
    if 40 <= code <= 49:
        return "高速船", "非重点船舶", "高", f"AIS 船型码 {code} 表示 High Speed Craft", "建议复核"
    if 60 <= code <= 69:
        return "客船", "运输类船舶", "高", f"AIS 船型码 {code} 表示 Passenger ship", "否"
    if 70 <= code <= 79:
        return "货船", "运输类船舶", "高", f"AIS 船型码 {code} 表示 Cargo ship，按货船处理", "否"
    if 80 <= code <= 89:
        return "油轮", "运输类船舶", "高", f"AIS 船型码 {code} 表示 Tanker，按油轮处理", "否"
    return "其他", "非重点船舶", "中", f"AIS 船型码 {code} 已收到，但不属于本项目重点细分类别", "建议复核"


def first_nonempty(rows, *names):
    for row in rows:
        for name in names:
            text = clean(row.get(name))
            if text:
                return text
    return ""


def build_data():
    by_mmsi = defaultdict(list)
    all_rows = []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_rows.append(row)
            mmsi = clean(row.get("mmsi"))
            if mmsi:
                by_mmsi[mmsi].append(row)

    vessels = []
    position_rows = 0
    for mmsi, rows in by_mmsi.items():
        points = []
        vessel_type = first_nonempty(rows, "vessel_type")
        name = first_nonempty(rows, "vessel_name") or first_nonempty(rows, "vessel_name", "ship_name") or "未获取船名"
        for row in rows:
            lat, lon = number(row.get("lat")), number(row.get("lon"))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            time = clean(row.get("received_at")) or clean(row.get("metadata_time_utc"))
            if not time:
                continue
            position_rows += 1
            points.append({
                "time": time,
                "lat": lat,
                "lon": lon,
                "sog": number(row.get("sog")),
                "cog": number(row.get("cog")),
                "heading": number(row.get("true_heading")),
            })
        points.sort(key=lambda p: p["time"])
        category, broad, confidence, reason, need_review = category_from_type(vessel_type)
        sogs = [p["sog"] for p in points if isinstance(p.get("sog"), (int, float))]
        vessels.append({
            "mmsi": mmsi,
            "name": name,
            "category": category,
            "broad_category": broad,
            "confidence": confidence,
            "source": "AIS vessel_type" if category != "未知" else "增强AIS采集/信息不足",
            "reason": reason,
            "need_review": need_review,
            "point_count": len(points),
            "avg_sog": round(sum(sogs) / len(sogs), 2) if sogs else None,
            "vessel_type": vessel_type,
            "call_sign": first_nonempty(rows, "call_sign"),
            "imo": first_nonempty(rows, "imo"),
            "ship_length": number(first_nonempty(rows, "ship_length")),
            "ship_width": number(first_nonempty(rows, "ship_width")),
            "draught": number(first_nonempty(rows, "draught")),
            "dl_model": "待接入：增强AIS多源船舶分类模型",
            "dl_predicted_category": "",
            "dl_confidence": None,
            "fusion_category": category,
            "dl_review_note": "新版数据已同步，模型预测需单独重训/验证",
            "dl_risk_model": "CPA/TCPA会遇风险算法 + AHP报告原型",
            "dl_predicted_risk_level": "",
            "dl_risk_confidence": None,
            "fusion_risk_level": "",
            "risk_review_note": "会遇页实时按CPA/TCPA计算船对风险",
            "prob_low_risk": None,
            "prob_medium_risk": None,
            "prob_elevated_risk": None,
            "prob_high_risk": None,
            "points": points,
        })

    vessels.sort(key=lambda v: (0 if v["points"] else 1, -len(v["points"]), v["mmsi"]))
    counts = Counter(v["category"] for v in vessels)
    return {
        "source_file": str(CSV_PATH),
        "generated_note": "由 2026-09-08 六小时增强 AIS CSV 同步生成；分类优先使用 AIS vessel_type，深度学习预测未在本次同步中重训。",
        "vessels": vessels,
        "stats": {
            "total": len(vessels),
            "known": sum(1 for v in vessels if v["category"] != "未知"),
            "position_rows": position_rows,
            "with_track": sum(1 for v in vessels if v["points"]),
            "raw_rows": len(all_rows),
            "counts": {k: counts.get(k, 0) for k in ORDER},
        },
    }


def replace_data(html: str, data: dict) -> str:
    literal = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    pattern = re.compile(r"    const DATA = .*?;\n    const COLORS =", re.S)
    replaced, n = pattern.subn("    const DATA = " + literal + ";\n    const COLORS =", html, count=1)
    if n != 1:
        raise RuntimeError("未找到唯一的 const DATA 数据块")
    replaced = replaced.replace("<title>Demo7 一小时AIS动态监测模拟版</title>", "<title>Demo7 马六甲6小时增强AIS动态监测模拟版</title>")
    replaced = replaced.replace("一小时AIS动态监测模拟版", "六小时增强AIS动态监测模拟版")
    return replaced


def main() -> None:
    data = build_data()
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    html = HTML_PATH.read_text(encoding="utf-8")
    HTML_PATH.write_text(replace_data(html, data), encoding="utf-8")
    print(json.dumps(data["stats"], ensure_ascii=False, indent=2))
    print(f"updated: {HTML_PATH}")
    print(f"data json: {OUT_JSON}")


if __name__ == "__main__":
    main()
