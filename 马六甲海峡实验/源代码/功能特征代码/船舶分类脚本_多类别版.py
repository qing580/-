from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


TARGET_CATEGORIES = {
    "货船",
    "油轮",
    "渔船",
    "客船",
    "拖船/港口服务船",
    "游艇/娱乐船",
    "高速船",
    "作业船",
    "其他",
    "未知",
}
REGISTRY_COLUMNS = [
    "mmsi",
    "vessel_name",
    "vessel_type",
    "category",
    "source",
    "verified",
    "remark",
    "updated_at",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "MMSI": "mmsi",
        "BaseDateTime": "timestamp",
        "LAT": "lat",
        "LON": "lon",
        "SOG": "sog",
        "COG": "cog",
        "VesselType": "vessel_type",
        "VesselName": "vessel_name",
    }
    return df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})


def parse_type_code(value) -> int | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def normalize_mmsi(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        numeric = float(text)
    except ValueError:
        return text
    if numeric.is_integer():
        return str(int(numeric))
    return text


def classify_by_ais_type(vessel_type) -> tuple[str, str, str]:
    code = parse_type_code(vessel_type)
    if code is None:
        return "未知", "低", "当前 AIS 消息没有船舶静态类型字段，无法可靠判断船型"

    if code == 30:
        return "渔船", "高", "AIS 船型码 30 表示 Fishing，按渔船处理"
    if code in {31, 32, 52, 53}:
        return "拖船/港口服务船", "高", f"AIS 船型码 {code} 表示拖带、拖船或港口服务相关船舶"
    if code in {33, 34, 50, 51, 54, 55, 58}:
        return "作业船", "高", f"AIS 船型码 {code} 表示引航、搜救、疏浚、潜水、执法或其他专项作业船"
    if code in {36, 37}:
        return "游艇/娱乐船", "高", f"AIS 船型码 {code} 表示帆船或娱乐船"
    if 60 <= code <= 69:
        return "客船", "高", f"AIS 船型码 {code} 表示 Passenger ship，按客船处理"
    if 70 <= code <= 79:
        return "货船", "高", f"AIS 船型码 {code} 表示 Cargo ship，按货船处理"
    if 80 <= code <= 89:
        return "油轮", "高", f"AIS 船型码 {code} 表示 Tanker，按油轮处理"
    if 40 <= code <= 49:
        return "高速船", "高", f"AIS 船型码 {code} 表示高速船或快速船相关类别"
    if code == 0:
        return "未知", "低", "AIS 船型码为 0，表示未提供船舶类型"
    return "其他", "中", f"AIS 船型码 {code} 已收到，但不属于本项目重点细分类别"


def normalize_category(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    aliases = {
        "cargo": "货船",
        "cargo ship": "货船",
        "freighter": "货船",
        "tanker": "油轮",
        "oil tanker": "油轮",
        "fishing": "渔船",
        "fishing vessel": "渔船",
        "passenger": "客船",
        "passenger ship": "客船",
        "tug": "拖船/港口服务船",
        "tugs": "拖船/港口服务船",
        "pilot": "作业船",
        "pilot vessel": "作业船",
        "pleasure": "游艇/娱乐船",
        "pleasure craft": "游艇/娱乐船",
        "yacht": "游艇/娱乐船",
        "sailing": "游艇/娱乐船",
        "high speed craft": "高速船",
        "hsc": "高速船",
        "service": "作业船",
        "working": "作业船",
        "other": "其他",
        "unknown": "未知",
    }
    return aliases.get(text.lower(), text if text in TARGET_CATEGORIES else None)


def classify_by_name(vessel_name) -> tuple[str, str, str] | None:
    if pd.isna(vessel_name):
        return None
    name = str(vessel_name).strip().lower()
    if not name:
        return None
    cargo_words = ["cargo", "container", "bulk", "bulker", "freighter"]
    tanker_words = ["tanker", "oil", "lng", "lpg", "chemical"]
    fishing_words = ["fish", "fishing", "trawler"]
    passenger_words = ["passenger", "ferry", "cruise"]
    service_words = ["tug", "pilot", "supply", "rescue", "patrol", "service"]
    pleasure_words = ["yacht", "pleasure", "sailing"]
    high_speed_words = ["hsc", "fast", "catamaran"]
    if any(word in name for word in cargo_words):
        return "货船", "中", f"船名包含货船相关关键词：{vessel_name}"
    if any(word in name for word in tanker_words):
        return "油轮", "中", f"船名包含油轮相关关键词：{vessel_name}"
    if any(word in name for word in fishing_words):
        return "渔船", "中", f"船名包含渔船相关关键词：{vessel_name}"
    if any(word in name for word in passenger_words):
        return "客船", "中", f"船名包含客船相关关键词：{vessel_name}"
    if any(word in name for word in service_words):
        return "拖船/港口服务船", "中", f"船名包含拖船或港口服务相关关键词：{vessel_name}"
    if any(word in name for word in pleasure_words):
        return "游艇/娱乐船", "中", f"船名包含游艇或娱乐船相关关键词：{vessel_name}"
    if any(word in name for word in high_speed_words):
        return "高速船", "中", f"船名包含高速船相关关键词：{vessel_name}"
    return None


def load_registry(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame(columns=REGISTRY_COLUMNS)
    registry_path = Path(path)
    if not registry_path.exists():
        return pd.DataFrame(columns=REGISTRY_COLUMNS)
    registry = normalize_columns(pd.read_csv(registry_path))
    for col in REGISTRY_COLUMNS:
        if col not in registry.columns:
            registry[col] = ""
    registry["mmsi"] = registry["mmsi"].astype(str).str.strip()
    return registry[REGISTRY_COLUMNS]


def registry_lookup(registry: pd.DataFrame, mmsi) -> dict | None:
    if registry.empty:
        return None
    key = str(mmsi).strip()
    matched = registry[registry["mmsi"] == key]
    if matched.empty:
        return None
    row = matched.iloc[0].to_dict()
    category = normalize_category(row.get("category"))
    if not category and row.get("vessel_type") not in ("", None):
        category, _, _ = classify_by_ais_type(row.get("vessel_type"))
    if not category:
        return None
    row["category"] = category
    return row


def classify_without_type(group: pd.DataFrame) -> tuple[str, str, str]:
    avg_sog = group["sog"].mean() if "sog" in group.columns else None
    point_count = len(group)
    if avg_sog is not None and point_count >= 20:
        if avg_sog < 3:
            return "未知", "低", "只有位置与速度信息，低速特征不足以区分具体船型"
        return "未知", "低", "只有位置与速度信息，缺少船舶静态类型，不能可靠分类"
    return "未知", "低", "采集点太少且缺少静态船型信息，建议继续采集或补充 ShipStaticData"


def broad_category(category: str) -> str:
    if category in {"货船", "油轮", "客船"}:
        return "运输类船舶"
    if category in {"渔船", "拖船/港口服务船", "作业船"}:
        return "作业类船舶"
    if category in {"游艇/娱乐船", "高速船", "其他"}:
        return "非重点船舶"
    return "信息不足"


def build_classification(df: pd.DataFrame, registry: pd.DataFrame | None = None) -> pd.DataFrame:
    df = normalize_columns(df)
    registry = registry if registry is not None else pd.DataFrame(columns=REGISTRY_COLUMNS)
    if "mmsi" not in df.columns:
        raise ValueError("输入数据缺少 mmsi 字段，无法按船舶分类")
    df = df.copy()
    df["_mmsi_key"] = df["mmsi"].map(normalize_mmsi)
    df = df[df["_mmsi_key"] != ""]

    rows = []
    for mmsi, group in df.groupby("_mmsi_key", dropna=False):
        vessel_type = None
        if "vessel_type" in group.columns:
            values = group["vessel_type"].dropna()
            values = values[values.astype(str).str.strip() != ""]
            vessel_type = values.iloc[0] if not values.empty else None

        if vessel_type is not None:
            category, confidence, reason = classify_by_ais_type(vessel_type)
            source = "AIS vessel_type"
            need_review = "否" if confidence == "高" and category in {"货船", "油轮", "渔船"} else "建议复核"
            vessel_name = group["vessel_name"].dropna().iloc[0] if "vessel_name" in group.columns and not group["vessel_name"].dropna().empty else ""
        else:
            registry_row = registry_lookup(registry, mmsi)
            if registry_row:
                category = registry_row["category"]
                verified = str(registry_row.get("verified", "")).strip().lower()
                confidence = "中高" if verified in {"yes", "y", "true", "1", "已确认"} else "中"
                source = "人工补全表"
                reason = f"MMSI 在人工补全表中标注为{category}"
                need_review = "否" if confidence == "中高" else "建议复核"
                vessel_name = registry_row.get("vessel_name", "")
                vessel_type = registry_row.get("vessel_type", "")
            else:
                name_result = None
                vessel_name = ""
                if "vessel_name" in group.columns:
                    names = group["vessel_name"].dropna()
                    names = names[names.astype(str).str.strip() != ""]
                    vessel_name = names.iloc[0] if not names.empty else ""
                    name_result = classify_by_name(vessel_name)
                if name_result:
                    category, confidence, reason = name_result
                    source = "船名关键词"
                    need_review = "建议复核"
                else:
                    category, confidence, reason = classify_without_type(group)
                    source = "轨迹弱判断/信息不足"
                    need_review = "是"

        rows.append(
            {
                "mmsi": mmsi,
                "vessel_name": vessel_name,
                "vessel_category": category,
                "broad_category": broad_category(category),
                "confidence": confidence,
                "classification_source": source,
                "classification_reason": reason,
                "need_manual_review": need_review,
                "point_count": len(group),
                "first_time": group["received_at"].min() if "received_at" in group.columns else "",
                "last_time": group["received_at"].max() if "received_at" in group.columns else "",
                "avg_sog": round(group["sog"].mean(), 2) if "sog" in group.columns else "",
                "min_lat": round(group["lat"].min(), 6) if "lat" in group.columns else "",
                "max_lat": round(group["lat"].max(), 6) if "lat" in group.columns else "",
                "min_lon": round(group["lon"].min(), 6) if "lon" in group.columns else "",
                "max_lon": round(group["lon"].max(), 6) if "lon" in group.columns else "",
                "raw_vessel_type": vessel_type if vessel_type is not None else "",
            }
        )
    return pd.DataFrame(rows).sort_values(["vessel_category", "mmsi"])


def build_review_sheet(result: pd.DataFrame) -> pd.DataFrame:
    review = result[
        (result["vessel_category"] == "未知")
        | (result["need_manual_review"].astype(str).str.contains("是|建议", regex=True, na=False))
    ].copy()
    if review.empty:
        return pd.DataFrame(
            columns=[
                "mmsi",
                "vessel_name",
                "current_category",
                "point_count",
                "avg_sog",
                "first_time",
                "last_time",
                "query_tip",
                "manual_category",
                "manual_source",
                "remark",
            ]
        )
    review["current_category"] = review["vessel_category"]
    review["query_tip"] = review["mmsi"].astype(str).map(lambda m: f"用 MMSI {m} 到 MarineTraffic、VesselFinder、MyShipTracking 等网站查询船名和船型")
    review["manual_category"] = ""
    review["manual_source"] = ""
    review["remark"] = ""
    cols = [
        "mmsi",
        "vessel_name",
        "current_category",
        "confidence",
        "classification_source",
        "classification_reason",
        "point_count",
        "avg_sog",
        "first_time",
        "last_time",
        "min_lat",
        "max_lat",
        "min_lon",
        "max_lon",
        "query_tip",
        "manual_category",
        "manual_source",
        "remark",
    ]
    return review[cols].sort_values(["current_category", "point_count"], ascending=[True, False])


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify AIS vessels into cargo, tanker, fishing, other, or unknown.")
    parser.add_argument("--input", required=True, help="AIS CSV path")
    parser.add_argument("--output", required=True, help="Classification CSV path")
    parser.add_argument("--registry", default=None, help="Optional MMSI registry CSV for manual vessel type completion")
    parser.add_argument("--review-output", default=None, help="Optional CSV path for vessels that need manual completion")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    registry = load_registry(args.registry)
    result = build_classification(df, registry)
    result.to_csv(output_path, index=False, encoding="utf-8-sig")

    if args.review_output:
        review_path = Path(args.review_output)
        review_path.parent.mkdir(parents=True, exist_ok=True)
        build_review_sheet(result).to_csv(review_path, index=False, encoding="utf-8-sig")

    print(f"saved {len(result)} vessel classifications to {output_path}")
    print(result["vessel_category"].value_counts().to_string())
    if args.review_output:
        print(f"saved manual review sheet to {args.review_output}")


if __name__ == "__main__":
    main()
