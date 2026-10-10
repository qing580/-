# GFW 免费身份补全操作流程

日期：2026-09-15  
用途：对马六甲 AIS 现有船舶做免费身份与登记来源预检

## 一、使用范围

Global Fishing Watch API 仅用于本国家级大创的非商业研究。项目使用 `public-global-vessel-identity:latest` 数据集，必须在论文、网页或图表中按官方要求注明数据来源。

官方资料：

- API 总览：https://globalfishingwatch.org/our-apis/
- Token 与认证：https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/authentication
- Vessel API：https://globalfishingwatch.org/our-apis/documentation/docs/v3/vessels
- 许可和限额：https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits
- 数据限制：https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/data-caveats

不得把 Token 写进代码、截图、CSV、文档、网页前端或聊天记录。

## 二、申请个人 Token

1. 打开 GFW API 总览并注册或登录个人账户。
2. 在 API Token 管理页面创建个人 Token。
3. 阅读并接受非商业使用、署名和保密要求。
4. Token 只保存在本人密码管理器中。项目脚本使用隐藏输入，不永久保存 Token。

官方说明显示，每个用户最多可有 5 个 Token，所有 Token 共用每日 50000 次、每月 1500000 次请求额度。当前 20 艘预检远低于该额度。

## 三、先验证离线样本

在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\卿之ya\Desktop\马六甲海峡实验\源代码\船舶分类数据准备\启动GFW身份补全预检.ps1"
```

该命令只重新生成 20 艘固定小样，不调用网络。

## 四、执行 20 艘在线预检

确认已申请本人 Token 后运行：

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\卿之ya\Desktop\马六甲海峡实验\源代码\船舶分类数据准备\启动GFW身份补全预检.ps1" -Execute
```

终端出现隐藏输入提示时粘贴 Token 并按回车。输入内容不会显示。脚本结束后会删除当前进程中的 `GFW_API_TOKEN` 环境变量。

## 五、运行时可见信息

终端逐船显示：

```text
[当前序号/20] mmsi=... query=imo或mmsi status=...
```

状态含义：

- `success`：返回至少一条候选身份，仍需标签裁决。
- `no_result`：请求成功但无匹配，不等于网络失败。
- `authentication_failed`：Token 缺失、错误或格式不正确，脚本立即停止。
- `permission_denied`：当前账户无数据集权限，脚本立即停止。
- `rate_limited`：达到限额，按退避策略重试并记录。
- `network_error`、`server_error`、`parse_error`：分别表示网络、服务端或响应解析问题。

## 六、输出目录

`运行结果/GFW身份补全预检_2026-09-15/`

- `gfw_pilot_sample.csv`：固定 20 艘样本。
- `gfw_pilot_status.csv`：逐船请求状态，仅在线执行后产生。
- `gfw_pilot_summary.json`：样本结构和状态汇总。
- `raw_responses/`：每个查询的原始 JSON 缓存。

重复运行时默认读取原始响应缓存，不重复请求同一查询。

## 七、预检验收

预检结束后不能直接运行 1499 艘全量查询。必须先检查：

1. 认证与数据集权限正常。
2. 20 艘请求状态完整，失败原因已区分。
3. 原始响应包含数据集版本、匹配依据、自报信息、登记信息或组合来源。
4. 至少人工核对 10 艘的 MMSI、IMO、船名、来源年份和细船型。
5. 评估 GFW 是否能区分集装箱船与散货船；若只返回宽泛 `cargo`，不得伪造细分类。

只有上述检查通过，才设计并执行全量身份补全。
