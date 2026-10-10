# -*- coding: utf-8 -*-
"""Prototype deep-learning vessel classifier for AIS trajectories.

This script is intentionally lightweight: it trains a small NumPy neural
network from the current weak labels so the demo can show a deep-learning
classification branch without requiring PyTorch/TensorFlow on the machine.
For the formal project design, this prototype is the replaceable front end of
the later 1D-CNN + BiLSTM + Attention model.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


CATEGORIES = ["货船", "油轮", "渔船", "客船", "拖船/港口服务船", "高速船", "作业船", "其他"]
FEATURE_COLUMNS = [
    "point_count",
    "duration_min",
    "track_distance_km",
    "avg_sog",
    "max_sog",
    "std_sog",
    "avg_abs_cog_change",
    "stop_ratio",
    "fast_ratio",
    "bbox_area",
]


def safe_float(value, default=np.nan):
    try:
        if value is None or str(value).strip() == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def haversine_km(lat1, lon1, lat2, lon2):
    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def angular_diff(a, b):
    if not math.isfinite(a) or not math.isfinite(b):
        return np.nan
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def load_positions(path: Path) -> dict[str, pd.DataFrame]:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df[df.get("message_type", "") == "PositionReport"].copy()
    for col in ["lat", "lon", "sog", "cog", "heading"]:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    df["received_at"] = pd.to_datetime(df["received_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["mmsi", "lat", "lon", "received_at"])
    return {str(mmsi): group.sort_values("received_at") for mmsi, group in df.groupby(df["mmsi"].astype(str))}


def extract_features(group: pd.DataFrame) -> dict[str, float]:
    pts = group[["lat", "lon"]].to_numpy(float)
    sog = group["sog"].dropna().to_numpy(float)
    cog = group["cog"].dropna().to_numpy(float)
    distance = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        distance += haversine_km(a[0], a[1], b[0], b[1])
    duration = (group["received_at"].max() - group["received_at"].min()).total_seconds() / 60
    cog_changes = [angular_diff(float(a), float(b)) for a, b in zip(cog[:-1], cog[1:])]
    cog_changes = [x for x in cog_changes if math.isfinite(x)]
    lat_span = float(np.nanmax(pts[:, 0]) - np.nanmin(pts[:, 0])) if len(pts) else 0.0
    lon_span = float(np.nanmax(pts[:, 1]) - np.nanmin(pts[:, 1])) if len(pts) else 0.0
    return {
        "point_count": float(len(group)),
        "duration_min": max(float(duration), 0.0) if math.isfinite(duration) else 0.0,
        "track_distance_km": float(distance),
        "avg_sog": float(np.nanmean(sog)) if len(sog) else 0.0,
        "max_sog": float(np.nanmax(sog)) if len(sog) else 0.0,
        "std_sog": float(np.nanstd(sog)) if len(sog) else 0.0,
        "avg_abs_cog_change": float(np.nanmean(cog_changes)) if cog_changes else 0.0,
        "stop_ratio": float(np.mean(sog < 0.5)) if len(sog) else 0.0,
        "fast_ratio": float(np.mean(sog > 12)) if len(sog) else 0.0,
        "bbox_area": max(lat_span * lon_span, 0.0),
    }


def softmax(x):
    x = x - np.max(x, axis=1, keepdims=True)
    exp = np.exp(x)
    return exp / np.sum(exp, axis=1, keepdims=True)


def train_mlp(x, y, class_count, epochs=420, lr=0.03, hidden=18, seed=7):
    rng = np.random.default_rng(seed)
    w1 = rng.normal(0, 0.18, size=(x.shape[1], hidden))
    b1 = np.zeros(hidden)
    w2 = rng.normal(0, 0.18, size=(hidden, class_count))
    b2 = np.zeros(class_count)
    y_onehot = np.eye(class_count)[y]
    for _ in range(epochs):
        h = np.tanh(x @ w1 + b1)
        p = softmax(h @ w2 + b2)
        grad_logits = (p - y_onehot) / len(x)
        grad_w2 = h.T @ grad_logits
        grad_b2 = grad_logits.sum(axis=0)
        grad_h = grad_logits @ w2.T
        grad_z1 = grad_h * (1 - h**2)
        grad_w1 = x.T @ grad_z1
        grad_b1 = grad_z1.sum(axis=0)
        w1 -= lr * grad_w1
        b1 -= lr * grad_b1
        w2 -= lr * grad_w2
        b2 -= lr * grad_b2
    return w1, b1, w2, b2


def predict_mlp(x, params):
    w1, b1, w2, b2 = params
    return softmax(np.tanh(x @ w1 + b1) @ w2 + b2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ais", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    positions = load_positions(args.ais)
    labels = pd.read_csv(args.labels, encoding="utf-8-sig")
    rows = []
    for _, row in labels.iterrows():
        mmsi = str(row["mmsi"]).strip()
        features = extract_features(positions[mmsi]) if mmsi in positions else {k: 0.0 for k in FEATURE_COLUMNS}
        rows.append({"mmsi": mmsi, "rule_category": row.get("vessel_category", "未知"), **features})
    feat_df = pd.DataFrame(rows)

    train_df = feat_df[feat_df["rule_category"].isin(CATEGORIES)].copy()
    classes = [c for c in CATEGORIES if c in set(train_df["rule_category"])]
    class_to_idx = {c: i for i, c in enumerate(classes)}
    x_all = feat_df[FEATURE_COLUMNS].to_numpy(float)
    mean = x_all.mean(axis=0)
    std = x_all.std(axis=0)
    std[std == 0] = 1
    x_all_norm = (x_all - mean) / std

    if len(classes) >= 2 and len(train_df) >= 8:
        train_idx = train_df.index.to_numpy()
        x_train = x_all_norm[train_idx]
        y_train = train_df["rule_category"].map(class_to_idx).to_numpy(int)
        params = train_mlp(x_train, y_train, len(classes))
        probs = predict_mlp(x_all_norm, params)
    else:
        probs = np.zeros((len(feat_df), max(len(classes), 1)))

    out_rows = []
    for i, row in feat_df.iterrows():
        if len(classes) >= 2 and len(train_df) >= 8:
            best_idx = int(np.argmax(probs[i]))
            pred = classes[best_idx]
            conf = float(probs[i, best_idx])
            prob_map = {c: float(probs[i, class_to_idx[c]]) if c in class_to_idx else 0.0 for c in CATEGORIES}
        else:
            pred = "未知"
            conf = 0.0
            prob_map = {c: 0.0 for c in CATEGORIES}
        if conf < 0.60:
            fusion = row["rule_category"] if row["rule_category"] != "未知" else "未知"
            review = "建议人工复核"
        elif row["rule_category"] == "未知":
            fusion = pred
            review = "深度学习补充分类型，建议人工确认"
        elif row["rule_category"] == pred:
            fusion = pred
            review = "规则与模型一致"
        else:
            fusion = row["rule_category"]
            review = "规则与模型冲突，建议人工复核"
        out_rows.append(
            {
                "mmsi": row["mmsi"],
                "dl_model": "NumPy-MLP弱监督原型；正式方案为1D-CNN+BiLSTM+Attention",
                "rule_category": row["rule_category"],
                "dl_predicted_category": pred,
                "dl_confidence": round(conf, 4),
                "fusion_category": fusion,
                "dl_review_note": review,
                **{f"prob_{c}": round(prob_map[c], 4) for c in CATEGORIES},
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out_rows).to_csv(args.output, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    print(f"saved {len(out_rows)} deep-learning prototype classifications to {args.output}")
    print(pd.DataFrame(out_rows)["fusion_category"].value_counts().to_string())


if __name__ == "__main__":
    main()
