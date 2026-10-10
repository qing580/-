import argparse
import csv
import hashlib
import json
import math
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from classification_audit import (
    GaussianNBModel,
    LogisticModel,
    MajorityModel,
    NearestCentroidModel,
    category,
    distance,
    metrics_dict,
    stratified_split,
    write_csv,
    zscore_apply,
    zscore_fit,
)


def number(s):
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None


def valid_heading(x):
    x = number(x)
    return x if x is not None and 0 <= x < 360 else None


def valid_rot(x):
    x = number(x)
    return x if x is not None and -127 <= x <= 127 else None


def percentile(values, q):
    if not values:
        return 0.0
    vals = sorted(values)
    idx = int(round((len(vals) - 1) * q))
    return vals[max(0, min(len(vals) - 1, idx))]


def mean_or_zero(values):
    return st.mean(values) if values else 0.0


def sd_or_zero(values):
    return st.pstdev(values) if len(values) > 1 else 0.0


def circular_stats(angles):
    if not angles:
        return 0.0, 0.0, 0.0
    sins = [math.sin(math.radians(a)) for a in angles]
    coss = [math.cos(math.radians(a)) for a in angles]
    sin_mean = st.mean(sins)
    cos_mean = st.mean(coss)
    concentration = math.sqrt(sin_mean * sin_mean + cos_mean * cos_mean)
    return sin_mean, cos_mean, concentration


def first_static(records, field):
    vals = []
    for r in records:
        x = number(r.get(field))
        if x is not None and x > 0:
            vals.append(x)
    return st.median(vals) if vals else 0.0


def split_segments(points, max_gap_seconds=600):
    segments, current = [], []
    for p in points:
        if current and (p["time"] - current[-1]["time"]).total_seconds() > max_gap_seconds:
            segments.append(current)
            current = []
        current.append(p)
    if current:
        segments.append(current)
    return segments


def build_features(rows):
    groups = defaultdict(list)
    for r in rows:
        mmsi = str(r.get("mmsi", "")).strip()
        if mmsi:
            groups[mmsi].append(r)

    archive, features = [], []
    for mmsi, records in sorted(groups.items()):
        codes = sorted(
            {
                int(x)
                for r in records
                if (x := number(r.get("vessel_type"))) is not None
                and x == int(x)
                and 0 < x <= 255
            }
        )
        label = category(codes[0]) if len(codes) == 1 else ("编码冲突" if codes else "未知")

        points, invalid = [], 0
        for r in records:
            if r.get("message_type") != "PositionReport":
                continue
            lat, lon, speed = (number(r.get(k)) for k in ("lat", "lon", "sog"))
            if lat is None or lon is None or speed is None:
                invalid += 1
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= speed < 102.3):
                invalid += 1
                continue
            points.append(
                {
                    "time": datetime.fromisoformat(r["received_at"]),
                    "lat": lat,
                    "lon": lon,
                    "sog": speed,
                    "cog": valid_heading(r.get("cog")),
                    "heading": valid_heading(r.get("true_heading")),
                    "rot": valid_rot(r.get("rate_of_turn")),
                    "nav": number(r.get("navigational_status")),
                }
            )
        unique_points = []
        seen = set()
        for p in sorted(points, key=lambda x: (x["time"], x["lat"], x["lon"], x["sog"], x["cog"] or -1)):
            key = (p["time"], p["lat"], p["lon"], p["sog"], p["cog"])
            if key not in seen:
                seen.add(key)
                unique_points.append(p)
        points = unique_points
        same_time = sum(a["time"] == b["time"] for a, b in zip(points, points[1:]))
        gaps = [(b["time"] - a["time"]).total_seconds() for a, b in zip(points, points[1:])]
        segments = split_segments(points)
        seg = max(segments, key=len, default=[])
        eligible = label in ("货船", "油轮") and len(seg) >= 10 and same_time == 0

        archive.append(
            {
                "MMSI": mmsi,
                "报文类别": label,
                "船型码": "|".join(map(str, codes)),
                "有效位置点": len(points),
                "无效位置点": invalid,
                "同秒冲突": same_time,
                "最长分段点数": len(seg),
                "分段数": len(segments),
                "最大间隔秒": max(gaps, default=0),
                "候选": eligible,
            }
        )
        if not eligible:
            continue

        speeds = [p["sog"] for p in seg]
        moving = [p for p in seg if p["sog"] >= 1.0]
        moving_cogs = [p["cog"] for p in moving if p["cog"] is not None]
        heading_values = [p["heading"] for p in moving if p["heading"] is not None]
        rot_values = [abs(p["rot"]) for p in seg if p["rot"] is not None]
        nav_values = [int(p["nav"]) for p in seg if p["nav"] is not None]
        lats = [p["lat"] for p in seg]
        lons = [p["lon"] for p in seg]

        acc, turns, path = [], [], 0.0
        for a, b in zip(seg, seg[1:]):
            dt = (b["time"] - a["time"]).total_seconds()
            if dt <= 0:
                continue
            path += distance((a["time"], a["lat"], a["lon"]), (b["time"], b["lat"], b["lon"]))
            acc.append(abs(b["sog"] - a["sog"]) * 60 / dt)
            if a["cog"] is not None and b["cog"] is not None and min(a["sog"], b["sog"]) >= 1:
                turns.append(abs((b["cog"] - a["cog"] + 180) % 360 - 180) * 60 / dt)

        cog_sin, cog_cos, cog_conc = circular_stats(moving_cogs)
        head_sin, head_cos, head_conc = circular_stats(heading_values)
        nav_anchor = sum(v in (1, 5, 6) for v in nav_values) / len(nav_values) if nav_values else 0.0
        obs_minutes = (seg[-1]["time"] - seg[0]["time"]).total_seconds() / 60 if len(seg) > 1 else 0.0

        features.append(
            {
                "mmsi": mmsi,
                "label": label,
                "speed_mean": mean_or_zero(speeds),
                "speed_sd": sd_or_zero(speeds),
                "speed_median": st.median(speeds),
                "speed_p90": percentile(speeds, 0.9),
                "low_speed_fraction": sum(x < 1 for x in speeds) / len(speeds),
                "speed_change_per_min": mean_or_zero(acc),
                "turn_per_min": mean_or_zero(turns),
                "path_m": path,
                "obs_minutes": obs_minutes,
                "points_per_hour": len(seg) / (obs_minutes / 60) if obs_minutes > 0 else 0.0,
                "segment_count": len(segments),
                "moving_fraction": len(moving) / len(seg),
                "stop_fraction": sum(x < 0.5 for x in speeds) / len(speeds),
                "turn_p90": percentile(turns, 0.9),
                "turn_max": max(turns, default=0.0),
                "large_turn_rate": sum(x >= 10 for x in turns) / len(turns) if turns else 0.0,
                "cog_sin_mean": cog_sin,
                "cog_cos_mean": cog_cos,
                "cog_concentration": cog_conc,
                "heading_sin_mean": head_sin,
                "heading_cos_mean": head_cos,
                "heading_concentration": head_conc,
                "rot_abs_mean": mean_or_zero(rot_values),
                "rot_abs_p90": percentile(rot_values, 0.9),
                "nav_anchor_fraction": nav_anchor,
                "lat_mean": mean_or_zero(lats),
                "lon_mean": mean_or_zero(lons),
                "lat_sd": sd_or_zero(lats),
                "lon_sd": sd_or_zero(lons),
                "lat_range": max(lats) - min(lats),
                "lon_range": max(lons) - min(lons),
                "east_fraction": sum(x >= 103.75 for x in lons) / len(lons),
                "north_fraction": sum(x >= 1.25 for x in lats) / len(lats),
                "ship_length": first_static(records, "ship_length"),
                "ship_width": first_static(records, "ship_width"),
                "draught": first_static(records, "draught"),
            }
        )
    return archive, features


FEATURE_SETS = {
    "A_old_track": [
        "speed_mean",
        "speed_sd",
        "speed_median",
        "speed_p90",
        "low_speed_fraction",
        "speed_change_per_min",
        "turn_per_min",
        "path_m",
    ],
    "B_heading_turn_segment": [
        "speed_mean",
        "speed_sd",
        "speed_median",
        "speed_p90",
        "low_speed_fraction",
        "speed_change_per_min",
        "turn_per_min",
        "path_m",
        "obs_minutes",
        "points_per_hour",
        "segment_count",
        "moving_fraction",
        "stop_fraction",
        "turn_p90",
        "turn_max",
        "large_turn_rate",
        "cog_sin_mean",
        "cog_cos_mean",
        "cog_concentration",
        "heading_sin_mean",
        "heading_cos_mean",
        "heading_concentration",
        "rot_abs_mean",
        "rot_abs_p90",
        "nav_anchor_fraction",
    ],
    "C_dynamic_static_spatial": [
        "speed_mean",
        "speed_sd",
        "speed_median",
        "speed_p90",
        "low_speed_fraction",
        "speed_change_per_min",
        "turn_per_min",
        "path_m",
        "obs_minutes",
        "points_per_hour",
        "segment_count",
        "moving_fraction",
        "stop_fraction",
        "turn_p90",
        "turn_max",
        "large_turn_rate",
        "cog_sin_mean",
        "cog_cos_mean",
        "cog_concentration",
        "heading_sin_mean",
        "heading_cos_mean",
        "heading_concentration",
        "rot_abs_mean",
        "rot_abs_p90",
        "nav_anchor_fraction",
        "lat_mean",
        "lon_mean",
        "lat_sd",
        "lon_sd",
        "lat_range",
        "lon_range",
        "east_fraction",
        "north_fraction",
        "ship_length",
        "ship_width",
        "draught",
    ],
}


def model_factory():
    return {
        "多数类": MajorityModel(),
        "最近质心": NearestCentroidModel(),
        "高斯朴素贝叶斯": GaussianNBModel(),
        "逻辑回归": LogisticModel(),
    }


def evaluate(features):
    y = [r["label"] for r in features]
    train, valid, test = stratified_split(y, seed=42)
    rows, predictions = [], []
    models = model_factory()
    details = {"class_order": ["货船", "油轮"], "splits": {"train": len(train), "valid": len(valid), "test": len(test)}}
    for set_name, names in FEATURE_SETS.items():
        X = [[float(r.get(k, 0.0) or 0.0) for k in names] for r in features]
        mu, sd = zscore_fit([X[i] for i in train])
        Xz = zscore_apply(X, mu, sd).tolist()
        for model_name, model in models.items():
            model.fit([Xz[i] for i in train], [y[i] for i in train])
            for split_name, part in [("验证", valid), ("测试", test)]:
                pred = list(model.predict([Xz[i] for i in part]))
                truth = [y[i] for i in part]
                acc, macro_f1, report, confusion = metrics_dict(truth, pred)
                key = f"{set_name}|{model_name}|{split_name}"
                details[key] = {"report": report, "confusion": confusion}
                rows.append(
                    {
                        "特征组": set_name,
                        "模型": model_name,
                        "集合": split_name,
                        "船舶数": len(part),
                        "准确率": acc,
                        "宏平均F1": macro_f1,
                        "货船召回": report["货船"]["recall"],
                        "油轮召回": report["油轮"]["recall"],
                    }
                )
                predictions.extend(
                    {
                        "MMSI": features[i]["mmsi"],
                        "特征组": set_name,
                        "模型": model_name,
                        "集合": split_name,
                        "报文标签": y[i],
                        "预测": p,
                    }
                    for i, p in zip(part, pred)
                )
    split_rows = [
        {"MMSI": features[i]["mmsi"], "报文类别": y[i], "集合": split_name}
        for split_name, part in [("训练", train), ("验证", valid), ("测试", test)]
        for i in part
    ]
    return rows, predictions, split_rows, details


def evaluate_repeated_splits(features, seeds=range(30)):
    y = [r["label"] for r in features]
    raw = []
    for seed in seeds:
        train, valid, test = stratified_split(y, seed=seed)
        trainval = train + valid
        for set_name, names in FEATURE_SETS.items():
            X = [[float(r.get(k, 0.0) or 0.0) for k in names] for r in features]
            mu, sd = zscore_fit([X[i] for i in trainval])
            Xz = zscore_apply(X, mu, sd).tolist()
            for model_name, model in model_factory().items():
                model.fit([Xz[i] for i in trainval], [y[i] for i in trainval])
                pred = list(model.predict([Xz[i] for i in test]))
                truth = [y[i] for i in test]
                acc, macro_f1, report, _ = metrics_dict(truth, pred)
                raw.append(
                    {
                        "seed": seed,
                        "特征组": set_name,
                        "模型": model_name,
                        "测试船舶数": len(test),
                        "准确率": acc,
                        "宏平均F1": macro_f1,
                        "货船召回": report["货船"]["recall"],
                        "油轮召回": report["油轮"]["recall"],
                    }
                )
    summary = []
    for set_name in FEATURE_SETS:
        for model_name in ["多数类", "最近质心", "高斯朴素贝叶斯", "逻辑回归"]:
            part = [r for r in raw if r["特征组"] == set_name and r["模型"] == model_name]
            f1s = [r["宏平均F1"] for r in part]
            accs = [r["准确率"] for r in part]
            cargo_recalls = [r["货船召回"] for r in part]
            tanker_recalls = [r["油轮召回"] for r in part]
            summary.append(
                {
                    "特征组": set_name,
                    "模型": model_name,
                    "重复次数": len(part),
                    "准确率均值": mean_or_zero(accs),
                    "准确率标准差": sd_or_zero(accs),
                    "宏F1均值": mean_or_zero(f1s),
                    "宏F1标准差": sd_or_zero(f1s),
                    "宏F1最小值": min(f1s, default=0.0),
                    "宏F1最大值": max(f1s, default=0.0),
                    "货船召回均值": mean_or_zero(cargo_recalls),
                    "油轮召回均值": mean_or_zero(tanker_recalls),
                }
            )
    return raw, summary


def write_report(out, source, rows, repeated_summary, features, archive, details):
    best_valid = max((r for r in rows if r["集合"] == "验证" and r["模型"] != "多数类"), key=lambda r: r["宏平均F1"])
    matching_tests = [r for r in rows if r["集合"] == "测试" and r["特征组"] == best_valid["特征组"] and r["模型"] == best_valid["模型"]]
    selected_test = matching_tests[0] if matching_tests else None
    majority_test = [r for r in rows if r["集合"] == "测试" and r["特征组"] == "A_old_track" and r["模型"] == "多数类"][0]
    old_lr_test = [r for r in rows if r["集合"] == "测试" and r["特征组"] == "A_old_track" and r["模型"] == "逻辑回归"][0]

    lines = [
        "# 六小时增强 AIS 特征消融验证",
        "",
        f"日期：2026-09-08。输入数据为 `{source.name}`。",
        "",
        "## 结论",
        "",
        "本报告是在 6 小时 AIS 数据上的开发性验证，不是论文最终独立测试结果。标签仍来自 AIS 自报 `vessel_type`，未完成外部登记核验。",
        "",
        f"本次可用货船/油轮候选仍为 {len(features)} 艘。按固定 MMSI 分层划分，测试集为 {details['splits']['test']} 艘。",
        f"验证集最好的组合是 `{best_valid['特征组']}` + `{best_valid['模型']}`，验证宏 F1 为 {best_valid['宏平均F1']:.4f}。",
    ]
    if selected_test:
        lines.append(
            f"同一组合在已曝光测试集上的准确率为 {selected_test['准确率']:.2%}，宏 F1 为 {selected_test['宏平均F1']:.4f}。"
        )
    lines += [
        "",
        f"关键判断：这批数据不是废数据，动态字段、静态字段和轨迹字段能支撑分类验证；但仅靠当前 {len(features)} 艘候选船和 AIS 弱标签，还不能证明准确率稳定提高。若要写论文，必须补外部核验或独立日期封存测试。",
        "",
        "## 消融结果",
        "",
        "| 特征组 | 模型 | 验证准确率 | 验证宏F1 | 测试准确率 | 测试宏F1 | 测试货船召回 | 测试油轮召回 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for set_name in FEATURE_SETS:
        for model_name in ["多数类", "最近质心", "高斯朴素贝叶斯", "逻辑回归"]:
            val = [r for r in rows if r["特征组"] == set_name and r["模型"] == model_name and r["集合"] == "验证"][0]
            test = [r for r in rows if r["特征组"] == set_name and r["模型"] == model_name and r["集合"] == "测试"][0]
            lines.append(
                f"| `{set_name}` | {model_name} | {val['准确率']:.2%} | {val['宏平均F1']:.4f} | {test['准确率']:.2%} | {test['宏平均F1']:.4f} | {test['货船召回']:.2%} | {test['油轮召回']:.2%} |"
            )
    lines += [
        "",
        "## 借鉴方法落地情况",
        "",
        "- 已落地：航向圆周统计、转向强度、急转比例、停航/低速比例、分段数量、采样密度、观测跨度、空间分布和尺寸/吃水特征。",
        "- 暂未落地：DBSCAN/HDBSCAN 航道聚类、CPA/TCPA 会遇风险、外部船舶登记核验。原因是本轮目标是先判断现有数据对船舶分类是否有增益，聚类和外部核验需要单独保存参数与来源。",
        "- 明确禁用：`vessel_type`、船名、IMO、MMSI 不进入模型特征。`vessel_type` 只用于生成弱标签。",
        "",
        "## 解释",
        "",
        f"旧特征组 A 的逻辑回归测试准确率为 {old_lr_test['准确率']:.2%}，宏 F1 为 {old_lr_test['宏平均F1']:.4f}；多数类基线测试准确率为 {majority_test['准确率']:.2%}，宏 F1 为 {majority_test['宏平均F1']:.4f}。",
        "如果 B 或 C 明显优于 A，说明“轨迹行为特征/静态空间特征”确实带来额外信号；如果只在测试集好、验证集不好，按保守口径视为不稳定，不写成结论。",
        "",
        "本轮测试集已经被前一次实验看过，因此只能作为开发检查。后续正式结论要使用独立日期数据或交叉验证，并优先核验预测错误船舶的真实类型。",
        "",
        "## 重复划分稳定性检查",
        "",
        "下面不是最终论文测试，而是用 30 个随机种子做开发稳定性检查；每次按 MMSI 分层划分，训练+验证集合并训练，测试约 29 艘。",
        "",
        "| 特征组 | 模型 | 准确率均值 | 宏F1均值 | 宏F1标准差 | 宏F1范围 | 货船召回均值 | 油轮召回均值 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in repeated_summary:
        lines.append(
            f"| `{r['特征组']}` | {r['模型']} | {r['准确率均值']:.2%} | {r['宏F1均值']:.4f} | {r['宏F1标准差']:.4f} | {r['宏F1最小值']:.4f}-{r['宏F1最大值']:.4f} | {r['货船召回均值']:.2%} | {r['油轮召回均值']:.2%} |"
        )
    lines += [
        "",
        "如果重复划分的均值也提升，才说明特征方向值得继续；如果只是某一次固定测试好看，则只能当偶然结果处理。",
        "",
        "## 输出文件",
        "",
        "- `增强特征_货船油轮.csv`：每艘候选船的 A/B/C 全部特征。",
        "- `增强特征消融_指标.csv`：各特征组和模型的验证/测试指标。",
        "- `增强特征消融_逐船预测.csv`：逐船预测，便于找错分船。",
        "- `增强特征消融_固定划分.csv`：本轮固定训练/验证/测试 MMSI。",
        "- `增强特征消融_重复划分原始指标.csv`：30 个随机种子的逐次指标。",
        "- `增强特征消融_重复划分汇总.csv`：重复划分均值、标准差和范围。",
        "- `增强特征消融_详细指标.json`：混淆矩阵、分组、源文件 SHA256。",
    ]
    (out / "增强特征消融验证报告.md").write_text("\n".join(lines), encoding="utf-8")


def run(source, out):
    out.mkdir(parents=True, exist_ok=True)
    with source.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    archive, features = build_features(rows)
    metrics, predictions, split_rows, details = evaluate(features)
    repeated_raw, repeated_summary = evaluate_repeated_splits(features)
    details.update(
        {
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "rows": len(rows),
            "ships": len({r["MMSI"] for r in archive}),
            "categories": dict(Counter(r["报文类别"] for r in archive)),
            "eligible": dict(Counter(r["label"] for r in features)),
            "feature_sets": FEATURE_SETS,
            "repeated_split_runs": 30,
        }
    )
    write_csv(out / "增强特征_船舶档案.csv", archive)
    write_csv(out / "增强特征_货船油轮.csv", features)
    write_csv(out / "增强特征消融_指标.csv", metrics)
    write_csv(out / "增强特征消融_逐船预测.csv", predictions)
    write_csv(out / "增强特征消融_固定划分.csv", split_rows)
    write_csv(out / "增强特征消融_重复划分原始指标.csv", repeated_raw)
    write_csv(out / "增强特征消融_重复划分汇总.csv", repeated_summary)
    (out / "增强特征消融_详细指标.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out, source, metrics, repeated_summary, features, archive, details)
    print(json.dumps({"rows": len(rows), "features": len(features), "metrics": metrics, "repeated_summary": repeated_summary}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    run(args.input, args.output)
