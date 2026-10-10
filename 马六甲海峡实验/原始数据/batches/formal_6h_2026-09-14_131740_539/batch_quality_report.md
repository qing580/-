# 马六甲 AIS 采集批次质量报告

验收结论：**PASS**。模式：`formal`。

批次：`formal_6h_2026-09-14_131740_539`。区域：`malacca_southeast_singapore_strait`。

共 8100 行，416 个唯一 MMSI，动态消息 7023 行，重连 0 次。
解析成功率 100.00%。船型、船长、船宽按 MMSI 覆盖率分别为 52.16%、52.16%、52.16%。
本批次严格货船/油轮候选 98 艘，其中货船 49 艘、油轮 49 艘。

## 验收检查

| 检查项 | 结果 |
| --- | --- |
| `required_columns_present` | PASS |
| `raw_json_in_csv_complete` | PASS |
| `raw_jsonl_complete_and_valid` | PASS |
| `dynamic_message_received` | PASS |
| `static_message_received` | PASS |
| `parse_success_ge_99pct` | PASS |
| `dynamic_mmsi_ge_99pct` | PASS |
| `dynamic_lat_ge_99pct` | PASS |
| `dynamic_lon_ge_99pct` | PASS |
| `dynamic_absolute_time_ge_99pct` | PASS |
| `dynamic_sog_ge_95pct` | PASS |
| `dynamic_cog_ge_95pct` | PASS |
| `at_least_one_mmsi_with_type` | PASS |
| `at_least_one_mmsi_with_size` | PASS |
| `formal_unique_mmsi_type_coverage_ge_30pct` | PASS |
| `formal_unique_mmsi_length_coverage_ge_30pct` | PASS |
| `formal_unique_mmsi_width_coverage_ge_30pct` | PASS |

## 字段覆盖

| 字段 | 动态消息覆盖 | MMSI静态覆盖 |
| --- | ---: | ---: |
| `mmsi` | 100.00% |  |
| `lat` | 100.00% |  |
| `lon` | 100.00% |  |
| `sog` | 100.00% |  |
| `cog` | 100.00% |  |
| `true_heading` | 100.00% |  |
| `rate_of_turn` | 99.86% |  |
| `navigational_status` | 99.86% |  |
| `vessel_name` |  | 95.91% |
| `imo` |  | 51.20% |
| `vessel_type` |  | 52.16% |
| `draught` |  | 51.20% |
| `ship_length` |  | 52.16% |
| `ship_width` |  | 52.16% |

## 负责人结论

本批次满足当前模式的质量门槛。预采集模式通过后，允许启动一个六小时正式窗口；正式模式通过后，才允许纳入累计分类审计。
静态字段来自较低频广播，空值不等于解析器偷工减料；报告按唯一 MMSI 统计真实覆盖率，不把动态行的正常空值伪装成字段丢失。