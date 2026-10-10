import csv
import json
import sys
from pathlib import Path


SOURCE_DIR = Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\源代码")
sys.path.insert(0, str(SOURCE_DIR))

from classification_audit import metrics_dict, zscore_apply, zscore_fit  # noqa: E402
from classification_feature_ablation import FEATURE_SETS, build_features, model_factory  # noqa: E402


TRAIN_FILES = [
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\malacca_enhanced_ais_0p5h_2026-09-07_194446_570.csv"),
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\malacca_enhanced_ais_6h_2026-09-08_123520_473.csv"),
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\batches\formal_6h_2026-09-09_124141_605\normalized_events.csv"),
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\batches\formal_6h_2026-09-13_123437_689\normalized_events.csv"),
    Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验\原始数据\batches\formal_6h_2026-09-14_131740_539\normalized_events.csv"),
]
TEST_FILE = Path(r"C:\Users\卿之ya\Documents\xwechat_files\wxid_0ybhi61e8yog22_5f4c\msg\file\2026-09\normalized_events.csv")


def read_rows(paths):
    rows = []
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def matrix(features, names):
    return [[float(row.get(name, 0.0) or 0.0) for name in names] for row in features]


def main():
    train_rows = read_rows(TRAIN_FILES)
    test_rows = read_rows([TEST_FILE])
    train_mmsis = {str(row.get("mmsi", "")).strip() for row in train_rows if str(row.get("mmsi", "")).strip()}
    _, train_features = build_features(train_rows)
    _, all_test_features = build_features(test_rows)
    test_features = [row for row in all_test_features if str(row["mmsi"]) not in train_mmsis]

    train_labels = [row["label"] for row in train_features]
    test_labels = [row["label"] for row in test_features]
    results = []
    predictions = []

    for feature_set, names in FEATURE_SETS.items():
        train_x = matrix(train_features, names)
        test_x = matrix(test_features, names)
        mean, sd = zscore_fit(train_x)
        train_z = zscore_apply(train_x, mean, sd).tolist()
        test_z = zscore_apply(test_x, mean, sd).tolist()
        for model_name, model in model_factory().items():
            model.fit(train_z, train_labels)
            predicted = list(model.predict(test_z))
            accuracy, macro_f1, report, confusion = metrics_dict(test_labels, predicted)
            results.append({
                "feature_set": feature_set,
                "model": model_name,
                "train_vessels": len(train_features),
                "test_vessels": len(test_features),
                "accuracy": accuracy,
                "macro_f1": macro_f1,
                "cargo_recall": report["货船"]["recall"],
                "tanker_recall": report["油轮"]["recall"],
                "confusion": confusion,
            })
            predictions.extend({
                "mmsi": row["mmsi"],
                "feature_set": feature_set,
                "model": model_name,
                "ais_weak_label": truth,
                "prediction": pred,
            } for row, truth, pred in zip(test_features, test_labels, predicted))

    output_dir = Path(__file__).with_name("独立日期测试_2026-09-15")
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "train_dates": "2026-09-07 to 2026-09-14",
        "test_date": "2026-09-15",
        "train_vessels": len(train_features),
        "test_unseen_vessels": len(test_features),
        "train_label_counts": {label: train_labels.count(label) for label in sorted(set(train_labels))},
        "test_label_counts": {label: test_labels.count(label) for label in sorted(set(test_labels))},
        "results": results,
        "label_note": "AIS vessel_type weak labels; not externally verified ground truth",
    }
    (output_dir / "独立日期测试指标.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with (output_dir / "独立日期测试逐船预测.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)

    best = max(results, key=lambda item: item["macro_f1"])
    lines = [
        "# 马六甲 AIS 独立日期测试",
        "",
        "训练数据：2026-09-07 至 2026-09-14 的增强 AIS 批次。",
        "",
        "测试数据：2026-09-15 新批次中此前从未出现过的 MMSI。",
        "",
        f"训练候选 {len(train_features)} 艘；独立日期未见船舶测试集 {len(test_features)} 艘。",
        f"测试集类别：货船 {test_labels.count('货船')} 艘，油轮 {test_labels.count('油轮')} 艘。",
        "",
        "| 特征组 | 模型 | 准确率 | 宏 F1 | 货船召回 | 油轮召回 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in results:
        lines.append(
            f"| {item['feature_set']} | {item['model']} | {item['accuracy']:.2%} | "
            f"{item['macro_f1']:.4f} | {item['cargo_recall']:.2%} | {item['tanker_recall']:.2%} |"
        )
    lines += [
        "",
        "## 当前结论",
        "",
        f"本次最高开发结果为 {best['feature_set']} + {best['model']}，准确率 {best['accuracy']:.2%}，宏 F1 {best['macro_f1']:.4f}。",
        "该测试按日期分离并排除了训练期已出现的 MMSI，比随机划分更接近跨日期泛化检查。",
        "标签仍来自 AIS vessel_type 自报弱标签，不能作为论文最终真实船型准确率；空间特征仍可能带有区域偏差。",
    ]
    (output_dir / "独立日期测试报告.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
