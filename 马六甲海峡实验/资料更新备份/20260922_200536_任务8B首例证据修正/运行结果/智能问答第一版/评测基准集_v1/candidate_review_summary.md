# 任务8A候选案例审核摘要

> 本页是程序生成的审核入口，不是模型结果，也不是人工金标准。12例的标注状态均为`draft`。

| 案例 | 类型 | 船舶 | 回放时刻（UTC） | 关键候选依据 | 状态 |
| --- | --- | --- | --- | --- | --- |
| CASE-NORMAL-001 | normal/无当前关联事件 | PSA MARVEL CS05 (563105900) | 2026-09-08T05:05:30.040Z | 当前运动证据门槛通过；筛选器未形成关联事件 | 待审核 |
| CASE-NORMAL-002 | normal/无当前关联事件 | LEO MARIS (352002967) | 2026-09-08T06:05:30.040Z | 当前运动证据门槛通过；筛选器未形成关联事件 | 待审核 |
| CASE-ENCOUNTER-001 | encounter/高风险会遇 | PVT SOLANA (352003176+636093181) | 2026-09-08T04:40:30.040Z | DCPA 0.525 nm；TCPA 0.8 min | 待审核 |
| CASE-ENCOUNTER-002 | encounter/高风险会遇 | DAI VINH (352006129+563024220) | 2026-09-08T05:00:30.040Z | DCPA 0.079 nm；TCPA 1.1 min | 待审核 |
| CASE-ENCOUNTER-003 | encounter/会遇风险初筛 | ARAGUA (305034400+477229100) | 2026-09-08T04:40:30.040Z | DCPA 0.030 nm；TCPA 63.3 min | 待审核 |
| CASE-ENCOUNTER-004 | encounter/会遇风险初筛 | TREASURE STAR (311001666+351916000) | 2026-09-08T05:00:30.040Z | DCPA 0.703 nm；TCPA 1.9 min | 待审核 |
| CASE-BEHAVIOR-001 | behavior/异常转向初筛 | MARTA COSULICH (563221200) | 2026-09-08T04:50:30.040Z | 108.0° / 4.7分钟 | 待审核 |
| CASE-BEHAVIOR-002 | behavior/异常减速初筛 | PILOT 16 (563086090) | 2026-09-08T04:45:30.040Z | 22.7 -> 0.4节 | 待审核 |
| CASE-INSUFFICIENT-001 | insufficient/运动字段缺失 | MINERAL MAURITIUS (205493000) | 2026-09-08T07:36:18.278Z | 工具缺失原因：运动字段缺失 | 待审核 |
| CASE-INSUFFICIENT-002 | insufficient/观测超过5分钟 | MINERAL MAURITIUS (205493000) | 2026-09-08T04:45:12.011Z | 工具缺失原因：观测超过5分钟 | 待审核 |
| CASE-INSUFFICIENT-003 | insufficient/回放时刻前无有效观测 | WINDCAT HAARLEM (205664000) | 2026-09-08T04:39:23.034Z | 工具缺失原因：回放时刻前无有效观测 | 待审核 |
| CASE-KNOWLEDGE-001 | knowledge/AIS使用限制 | 不适用 (无MMSI) | 不适用 | 核对AIS不能作为唯一避碰依据及所需辅助信息 | 待审核 |

## 审核方法

1. 先核对本页的船舶、时刻和候选依据。
2. 打开对应案例目录的`evidence_packet.json`，确认AIS观测、事件指标和来源只来自回放时刻及以前。
3. 打开`annotation.json`，核对结论边界、必要证据ID、允许来源、数值白名单和禁用陈述。
4. 在`review_checklist.md`记录意见。确认后才可把单例状态改为`approved`；不合格案例标为`rejected`并补选。

## 解释边界

- “高风险/中高风险”是现有筛查规则的候选等级，不是违法、责任或必然碰撞认定。
- “未形成事件”只表示当前筛选器没有生成关联事件，不等于绝对安全。
- 三个证据不足案例必须拒绝给出确定运动或异常结论。
- 本轮没有调用DeepSeek，不存在模型准确率、RAG增益或图谱增益结果。
