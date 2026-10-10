from pathlib import Path


ROOT = Path(r"C:\Users\卿之ya\Desktop\马六甲海峡实验")


def main():
    docs = ROOT / "说明文档"
    docs.mkdir(parents=True, exist_ok=True)
    note = docs / "Datalastic历史AIS数据源评估_2026-09-09.md"
    note.write_text(
        "\n".join(
            [
                "# Datalastic 历史 AIS 数据源评估（2026-09-09）",
                "",
                "## 适配结论",
                "",
                "Datalastic 值得作为马六甲历史 AIS 数据的优先试探对象，原因是其公开价格较透明，核心套餐包含 Historical Area Scan，并支持按区域半径提交历史位置报告。但它采用半径区域，不是任意 bbox，马六甲海峡需要用多个中心点覆盖；正式购买前必须确认导出的 CSV 字段是否包含本项目分类所需的完整静态字段。",
                "",
                "## 价格与扣费",
                "",
                "- Starter：20,000 credits / month，2 周 9 欧试用后 199 欧/月。",
                "- Growth/Experimenter：80,000 credits / month，2 周 19 欧试用后 569 欧/月。",
                "- Developer Pro+：unlimited monthly requests，2 周 45 欧试用后 679 欧/月。",
                "- Historical Area Scan / inradius_history：公开文档说明按 unique vessel per calendar day 扣费；第三方 OpenAPI 摘要还注明每天最多 500 vessels 的扣费上限。",
                "- 账户 `/stat` 可查询 credits 使用情况；成功请求才扣 credits，响应头含 `X-Request-Cost` 与剩余额度。",
                "",
                "## 与本项目字段需求的关系",
                "",
                "本项目主实验至少需要：MMSI、timestamp、lat、lon、SOG、COG、heading、rate_of_turn、navigational_status、vessel_name、call_sign、IMO、vessel_type、destination、draught、ship_length、ship_width。Datalastic 的实时/Pro/Info 文档显示其支持 AIS、吃水、目的港、船舶规格等信息，但 Historical Area Scan 导出 ZIP 的实际字段必须用小样本报告确认，不能仅凭宣传页认定可用。",
                "",
                "## 推荐购买/试用策略",
                "",
                "1. 先开最小试用，不直接上 569 欧/月或 679 欧/月。",
                "2. 只提交马六甲/新加坡海峡区域，不采其他海域。",
                "3. 先用 1 天、2-3 个半径点覆盖主航道，下载 ZIP 后审计字段覆盖。",
                "4. 如果导出含完整静态字段，再扩展到 3-7 天；如果不含船长/船宽/吃水，则只作为动态轨迹补充，不再继续付费扩量。",
                "",
                "## 建议测试区域",
                "",
                "Datalastic inradius_history 使用中心点 + 半径，最大半径需要按其 API 限制执行。可用多个点覆盖：新加坡海峡东口、主航道中段、马六甲西向入口。每个点半径建议先 20-50 NM，小样本确认后再调整。",
                "",
                "## 参考来源",
                "",
                "- Datalastic Docs: https://docs.datalastic.com/",
                "- Datalastic Pricing Blog: https://datalastic.com/blog/the-best-maritime-api-plan-compare-features-pricing/",
                "- Starter Checkout: https://datalastic.com/pricing/checkout-starter/",
                "- Growth Checkout: https://datalastic.com/pricing/checkout-growth/",
                "- Historical Location AIS Data API: https://datalastic.com/historical-location-ais-data-api/",
                "- Official OpenAPI GitHub: https://github.com/datalastic/datalastic-openapi",
                "",
            ]
        ),
        encoding="utf-8",
    )

    index = ROOT / "马六甲海峡实验资料说明.md"
    marker = "## 2026-09-09 Datalastic 历史 AIS 数据源评估"
    addition = "\n".join(
        [
            "",
            marker,
            "",
            f"- 新增说明文档：`说明文档/{note.name}`",
            "- 结论：Datalastic 可作为优先试用对象，公开价格透明，套餐包含 Historical Area Scan；但区域查询为中心点+半径，马六甲需多点覆盖。正式扩量前必须用小样本确认导出字段是否包含 `vessel_type`、长宽、吃水、IMO、动态航行字段等。",
            "",
        ]
    )
    old = index.read_text(encoding="utf-8") if index.exists() else "# 马六甲海峡实验资料说明\n"
    if marker not in old:
        index.write_text(old.rstrip() + addition, encoding="utf-8")


if __name__ == "__main__":
    main()
