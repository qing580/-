# -*- coding: utf-8 -*-
"""Prototype deep-learning risk level predictor for AIS vessels.

This is a separate model from ship-type classification. It predicts risk
levels from risk-related features, including speed behavior, nearby density,
waterway environment, ship consequence and AIS credibility.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np
import pandas as pd


RISK_LEVELS = ["低风险", "中风险", "较高风险", "高风险"]
AHP_WEIGHTS = {
    "behavior": 0.3197,
    "encounter": 0.3197,
    "environment": 0.1836,
    "consequence": 0.1091,
    "credibility": 0.0680,
}
CATEGORY_CONSEQUENCE = {
    "油轮": 82,
    "货船": 68,
    "客船": 74,
    "拖船/港口服务船": 58,
    "作业船": 62,
    "高速船": 64,
    "渔船": 48,
    "游艇/娱乐船": 38,
    "其他": 42,
    "未知": 55,
}
FEATURE_COLUMNS = [
    "behavior_score",
    "encounter_score",
    "environment_score",
    "consequence_score",
    "credibility_score",
    "ahp_score",
    "avg_sog",
    "point_count",
    "nearby_count",
    "missing_static_flag",
]


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, float(value)))


def safe_float(value, default=np.nan):
    try:
        if value is None or str(value).strip() == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def haversine_km(a, b):
    rad = math.pi / 180
    dlat = (b["lat"] - a["lat"]) * rad
    dlon = (b["lon"] - a["lon"]) * rad
    lat1 = a["lat"] * rad
    lat2 = b["lat"] * rad
    s = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(s), math.sqrt(1 - s))


def risk_level(score: float) -> str:
    if score >= 80:
        return "高风险"
    if score >= 60:
        return "较高风险"
    if score >= 40:
        return "中风险"
    return "低风险"


def read_positions(path: Path) -> dict[str, list[dict]]:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df[df.get("message_type", "") == "PositionReport"].copy()
    for col in ["lat", "lon", "sog", "cog", "heading"]:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    df["received_at"] = pd.to_datetime(df["received_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["mmsi", "lat", "lon", "received_at"])
    positions = {}
    for mmsi, group in df.groupby(df["mmsi"].astype(str)):
        records = []
        for _, row in group.sort_values("received_at").iterrows():
            records.append(
                {
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "sog": safe_float(row.get("sog"), 0.0),
                    "cog": safe_float(row.get("cog"), 0.0),
                }
            )
        positions[str(mmsi)] = records
    return positions


def nearby_count(mmsi: str, positions: dict[str, list[dict]], km: float = 3) -> int:
    pts = positions.get(mmsi, [])
    if not pts:
        return 0
    last = pts[-1]
    total = 0
    for other_mmsi, other_pts in positions.items():
        if other_mmsi == mmsi or not other_pts:
            continue
        if haversine_km(last, other_pts[-1]) <= km:
            total += 1
    return total


def compute_features(label_row: pd.Series, positions: dict[str, list[dict]]) -> dict[str, float | str]:
    mmsi = str(label_row["mmsi"]).strip()
    pts = positions.get(mmsi, [])
    sogs = [p["sog"] for p in pts if math.isfinite(p["sog"])]
    avg_sog = float(np.mean(sogs)) if sogs else np.nan
    point_count = len(pts)
    near = nearby_count(mmsi, positions)
    last = pts[-1] if pts else {}

    behavior = 28
    if not math.isfinite(avg_sog):
        behavior += 18
    elif avg_sog < 0.5:
        behavior += 34
    elif avg_sog < 2:
        behavior += 22
    elif avg_sog > 18:
        behavior += 24
    elif avg_sog > 12:
        behavior += 14
    if point_count <= 1:
        behavior += 18
    elif point_count <= 3:
        behavior += 10

    encounter = 30 + near * 13 + (8 if math.isfinite(avg_sog) and avg_sog > 10 else 0)
    lon = safe_float(last.get("lon") if last else None, np.nan)
    environment = 58 + (10 if math.isfinite(lon) and 103.75 <= lon <= 103.95 else 0) + (8 if near >= 3 else 0)
    category = label_row.get("vessel_category", "未知") or "未知"
    consequence = CATEGORY_CONSEQUENCE.get(category, 50)
    credibility = 24
    if not label_row.get("vessel_name") or str(label_row.get("vessel_name")) == "未获取船名":
        credibility += 18
    if not label_row.get("raw_vessel_type") or str(label_row.get("raw_vessel_type")).strip() == "":
        credibility += 18
    if point_count <= 1:
        credibility += 30
    elif point_count <= 3:
        credibility += 18
    if "建议" in str(label_row.get("need_manual_review", "")) or "是" in str(label_row.get("need_manual_review", "")):
        credibility += 12

    raw = {
        "behavior_score": clamp(behavior),
        "encounter_score": clamp(encounter),
        "environment_score": clamp(environment),
        "consequence_score": clamp(consequence),
        "credibility_score": clamp(credibility),
    }
    ahp_score = (
        raw["behavior_score"] * AHP_WEIGHTS["behavior"]
        + raw["encounter_score"] * AHP_WEIGHTS["encounter"]
        + raw["environment_score"] * AHP_WEIGHTS["environment"]
        + raw["consequence_score"] * AHP_WEIGHTS["consequence"]
        + raw["credibility_score"] * AHP_WEIGHTS["credibility"]
    )
    return {
        "mmsi": mmsi,
        **raw,
        "ahp_score": round(ahp_score, 2),
        "avg_sog": 0.0 if not math.isfinite(avg_sog) else round(avg_sog, 2),
        "point_count": point_count,
        "nearby_count": near,
        "missing_static_flag": 1 if not label_row.get("raw_vessel_type") or str(label_row.get("raw_vessel_type")).strip() == "" else 0,
        "weak_risk_label": risk_level(ahp_score),
    }


def softmax(x):
    x = x - np.max(x, axis=1, keepdims=True)
    exp = np.exp(x)
    return exp / np.sum(exp, axis=1, keepdims=True)


def train_residual_mlp(x, y, class_count, epochs=550, lr=0.025, hidden=20, seed=11):
    rng = np.random.default_rng(seed)
    w1 = rng.normal(0, 0.15, size=(x.shape[1], hidden))
    b1 = np.zeros(hidden)
    w2 = rng.normal(0, 0.15, size=(hidden, hidden))
    b2 = np.zeros(hidden)
    w3 = rng.normal(0, 0.15, size=(hidden, class_count))
    b3 = np.zeros(class_count)
    y_hot = np.eye(class_count)[y]
    for _ in range(epochs):
        h1 = np.tanh(x @ w1 + b1)
        h2_pre = h1 @ w2 + b2
        h2 = np.tanh(h2_pre) + h1
        p = softmax(h2 @ w3 + b3)
        g = (p - y_hot) / len(x)
        gw3 = h2.T @ g
        gb3 = g.sum(axis=0)
        gh2 = g @ w3.T
        gh1_skip = gh2
        gh2_pre = gh2 * (1 - np.tanh(h2_pre) ** 2)
        gw2 = h1.T @ gh2_pre
        gb2 = gh2_pre.sum(axis=0)
        gh1 = gh1_skip + gh2_pre @ w2.T
        gz1 = gh1 * (1 - h1**2)
        gw1 = x.T @ gz1
        gb1 = gz1.sum(axis=0)
        w1 -= lr * gw1
        b1 -= lr * gb1
        w2 -= lr * gw2
        b2 -= lr * gb2
        w3 -= lr * gw3
        b3 -= lr * gb3
    return w1, b1, w2, b2, w3, b3


def predict(x, params):
    w1, b1, w2, b2, w3, b3 = params
    h1 = np.tanh(x @ w1 + b1)
    h2 = np.tanh(h1 @ w2 + b2) + h1
    return softmax(h2 @ w3 + b3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ais", required=True, type=Path)
    parser.add_argument("--classification", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    positions = read_positions(args.ais)
    labels = pd.read_csv(args.classification, encoding="utf-8-sig")
    feat_df = pd.DataFrame([compute_features(row, positions) for _, row in labels.iterrows()])
    x = feat_df[FEATURE_COLUMNS].to_numpy(float)
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std == 0] = 1
    x_norm = (x - mean) / std
    y = feat_df["weak_risk_label"].map({name: i for i, name in enumerate(RISK_LEVELS)}).to_numpy(int)
    params = train_residual_mlp(x_norm, y, len(RISK_LEVELS))
    probs = predict(x_norm, params)

    out = feat_df.copy()
    best = probs.argmax(axis=1)
    out["dl_risk_model"] = "Risk-MLP残差神经网络弱监督原型"
    out["dl_predicted_risk_level"] = [RISK_LEVELS[i] for i in best]
    out["dl_risk_confidence"] = probs.max(axis=1).round(4)
    for idx, level in enumerate(RISK_LEVELS):
        out[f"prob_{level}"] = probs[:, idx].round(4)
    out["fusion_risk_level"] = out.apply(
        lambda row: row["dl_predicted_risk_level"]
        if row["dl_risk_confidence"] >= 0.65
        else row["weak_risk_label"],
        axis=1,
    )
    out["risk_review_note"] = out.apply(
        lambda row: "深度学习与AHP一致"
        if row["dl_predicted_risk_level"] == row["weak_risk_label"]
        else "深度学习与AHP存在差异，建议人工复核",
        axis=1,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    print(f"saved {len(out)} deep-learning risk predictions to {args.output}")
    print(out["fusion_risk_level"].value_counts().to_string())


if __name__ == "__main__":
    main()
