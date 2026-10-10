# 增强 AIS 数据字段字典

日期：2026-09-08。适用文件示例：`原始数据/malacca_enhanced_ais_0p5h_2026-09-07_194446_570.csv` 及后续增强采集 CSV。

## 字段说明

| 字段 | 含义 | 对船舶分类的作用 |
| --- | --- | --- |
| collector_version | 采集脚本版本 | 用于复现实验和区分旧/新采集方式 |
| source | 数据来源，本项目为 AISStream | 用于数据来源记录 |
| bbox | 本次订阅的经纬度范围 | 用于说明采集海域边界 |
| message_type | AISStream 消息类型 | 区分动态位置、静态船舶资料、Class B 等消息 |
| received_at | 本机收到消息的 UTC 时间 | 作为接收时序代理，适合排序，但不是精确广播时间 |
| metadata_time_utc | AISStream 元数据中的 UTC 时间 | 可辅助判断服务端接收时间 |
| ais_timestamp | AIS 报文内时间戳 | 常为分钟内秒值或报文字段值，不能单独当完整日期时间 |
| mmsi | Maritime Mobile Service Identity，船舶海上移动业务识别码 | 按船汇总、外部核验和训练集分组的核心 ID |
| valid | 报文字段是否标记有效 | 数据质量控制 |
| repeat_indicator | AIS 重复指示符 | 一般用于报文转发/重复情况分析 |
| message_id | AIS 报文编号 | 可辅助识别消息类别 |
| lat | 纬度 | 轨迹、航道位置和空间特征 |
| lon | 经度 | 轨迹、航道位置和空间特征 |
| sog | Speed Over Ground，对地航速，通常单位为节 | 船型行为特征、低速/停泊判断 |
| cog | Course Over Ground，对地航向，单位通常为度 | 航向变化、转弯特征 |
| true_heading | 船艏向，单位通常为度 | 与 COG 结合可分析航向稳定性；511 常表示不可用 |
| rate_of_turn | 转向率 | 区分航行行为和异常转向的重要特征；特殊值需清洗 |
| navigational_status | 航行状态编码 | 区分在航、锚泊、受限、靠泊等状态 |
| position_accuracy | 位置精度标志 | 数据质量控制 |
| raim | RAIM 完整性标志 | 数据质量控制 |
| special_manoeuvre_indicator | 特殊操纵指示 | 辅助识别特殊机动状态 |
| communication_state | AIS 通信状态 | 一般用于报文质量和通信机制分析 |
| assigned_mode | Class B 相关分配模式字段 | Class B 报文辅助字段 |
| dte | Data Terminal Equipment 状态 | 通信/设备状态字段 |
| vessel_name | 船名 | 外部核验、人工补全、船名关键词弱判断 |
| call_sign | 呼号 | 外部登记核验 |
| imo | IMO 编号 | 外部登记核验和船舶身份确认的强字段 |
| vessel_type | AIS 船型码 | 当前规则分类和弱标签来源的核心字段 |
| ais_version | AIS 版本 | 静态资料质量辅助字段 |
| fix_type | 定位设备类型 | 数据质量和设备来源参考 |
| destination | 目的港/目的地 | 可辅助判断航行任务和路线，但不能单独决定船型 |
| eta_month | 预计到达月份 | 航次资料 |
| eta_day | 预计到达日期 | 航次资料 |
| eta_hour | 预计到达小时 | 航次资料 |
| eta_minute | 预计到达分钟 | 航次资料 |
| draught | 吃水 | 区分大型货船、油轮等的重要静态/航次特征 |
| dimension_to_bow | AIS 尺寸字段，到船首距离 | 计算船长 |
| dimension_to_stern | AIS 尺寸字段，到船尾距离 | 计算船长 |
| dimension_to_port | AIS 尺寸字段，到左舷距离 | 计算船宽 |
| dimension_to_starboard | AIS 尺寸字段，到右舷距离 | 计算船宽 |
| ship_length | 船长，脚本由 bow + stern 计算 | 船舶分类的重要静态特征 |
| ship_width | 船宽，脚本由 port + starboard 计算 | 船舶分类的重要静态特征 |
| vendor_id_name | Class B 静态报文中的设备厂商/设备标识 | 一般不直接用于分类，可用于追溯 |
| vendor_id_model | Class B 静态报文中的设备型号 | 一般不直接用于分类 |
| vendor_id_serial | Class B 静态报文中的设备序列号 | 一般不直接用于分类 |
| parse_status | 解析状态，如 parsed、unsupported、error | 判断该行是否可用于分析 |
| parse_error | 解析错误信息 | 排查采集或字段解析问题 |
| raw_json | AISStream 原始 JSON 报文 | 字段追溯、补解析和审计用，不直接作为模型特征 |

## 使用注意

- 一条 CSV 行是一条 AIS 消息，不是一艘船。建模前必须按 `mmsi` 汇总或切成轨迹片段。
- 动态消息通常有 `lat/lon/sog/cog`，静态消息通常有 `vessel_type/vessel_name/imo/ship_length/ship_width`，不是每行都有全部字段。
- `vessel_type` 是 AIS 自报船型码，可作为弱标签或规则分类依据，但论文级准确率仍需要外部核验。
- `received_at` 是本机接收时间；`ais_timestamp` 可能不是完整时间，分析时不能直接当作完整广播时间。
- `raw_json` 应保留，后续发现字段解析不足时可以回溯原始消息。
