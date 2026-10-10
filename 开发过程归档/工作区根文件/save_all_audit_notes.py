from pathlib import Path
import shutil


ROOT = Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验")
WORK = Path(r"C:\Users\卿之ya\Documents\ChatGPT\大创")
RESULT_DIR = ROOT / "运行结果" / "全部马六甲历史采集整合审计_2026-09-09"


def main():
    source_dir = ROOT / "源代码"
    source_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(WORK / "all_malacca_data_audit.py", source_dir / "all_malacca_data_audit.py")

    docs_dir = ROOT / "说明文档"
    docs_dir.mkdir(parents=True, exist_ok=True)
    note = docs_dir / "全部历史AIS采集数据整合审计记录_2026-09-09.md"
    note.write_text(
        "\n".join(
            [
                "# 全部历史 AIS 采集数据整合审计记录（2026-09-09）",
                "",
                "## 审计目的",
                "",
                "本次审计整合用户此前在马六甲/新加坡海峡区域采集的 7 个 CSV 文件，目标是判断这些数据对船舶分类实验到底还能贡献多少，避免把旧版不完整字段误当成增强分类主实验数据。",
                "",
                "## 核心结论",
                "",
                "- 两个 1 小时 AIS 文件内容完全相同，已按重复文件处理，不能重复计入样本量。",
                "- 严格增强数据口径：有货船/油轮标签的 MMSI 为 286 艘；同时满足当前分类实验轨迹质量要求的为 152 艘，其中货船 66 艘、油轮 86 艘，20% 测试集约 30 艘。",
                "- 全部旧版 + 增强数据弱辅助口径：有货船/油轮标签的 MMSI 为 495 艘；满足轨迹质量要求的为 279 艘，其中货船 128 艘、油轮 151 艘，20% 测试集约 56 艘。",
                "- 主实验不能直接把旧版数据当成完整增强数据，因为旧版文件缺少 `ship_length`、`ship_width`、`draught` 等关键静态尺度字段。",
                "- 若目标是 500 艘严格增强分类可用货船/油轮 MMSI，当前还差 348 艘。按现有增强数据产出速率粗估，还需约 14.9 小时；考虑连接中断、重复 MMSI 和类别波动，建议安排 18-24 小时同区域增强采集，或同步申请/购买马六甲历史 AIS。",
                "",
                "## 保存位置",
                "",
                f"- 可复用审计脚本：`{source_dir / 'all_malacca_data_audit.py'}`",
                f"- 详细结果目录：`{RESULT_DIR}`",
                f"- 主报告：`{RESULT_DIR / '全部历史采集数据整合分析报告.md'}`",
                f"- 文件级字段审计：`{RESULT_DIR / '全部文件清单与字段审计.csv'}`",
                f"- 全部船舶档案：`{RESULT_DIR / '全部累计船舶档案.csv'}`",
                f"- 分类可用质量明细：`{RESULT_DIR / '增强数据分类可用质量明细.csv'}` 与 `{RESULT_DIR / '全部数据分类可用质量明细.csv'}`",
                "",
                "## 后续实验口径",
                "",
                "论文主实验仍以增强 AIS 数据为主；旧版数据可用于动态轨迹基线、消融对照或区域行为分布检查，但不能作为完整静态特征模型的主要证据。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    index = ROOT / "马六甲海峡实验资料说明.md"
    addition = "\n".join(
        [
            "",
            "## 2026-09-09 全部历史采集数据整合审计",
            "",
            f"- 新增说明文档：`说明文档/{note.name}`",
            f"- 新增可复用脚本：`源代码/all_malacca_data_audit.py`",
            f"- 新增结果目录：`运行结果/{RESULT_DIR.name}`",
            "- 结论：严格增强分类可用货船/油轮 MMSI 为 152 艘，按 20% 测试集约 30 艘；若计入旧版弱辅助数据，分类可用货船/油轮 MMSI 为 279 艘，按 20% 测试集约 56 艘。",
            "- 判断：旧版数据能辅助动态轨迹基线和消融，但缺少船长、船宽、吃水等关键静态字段，不能替代增强主实验数据。若目标为 500 艘严格增强分类可用样本，还差 348 艘。",
            "",
        ]
    )
    old = index.read_text(encoding="utf-8") if index.exists() else "# 马六甲海峡实验资料说明\n"
    marker = "## 2026-09-09 全部历史采集数据整合审计"
    if marker not in old:
        index.write_text(old.rstrip() + addition, encoding="utf-8")


if __name__ == "__main__":
    main()
