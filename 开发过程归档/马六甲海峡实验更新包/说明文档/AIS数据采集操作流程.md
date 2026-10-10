# AIS数据采集操作流程

更新日期：2026-09-06。根据本项目历史成功采集记录及当天读取的实际脚本整理。本次只生成操作文档，未启动新采集、未验证当前接口连通性、未修改采集代码。不包含API密钥。

## 1. 给新对话的说明

用户已成功用AISStream采集10分钟、一小时、六小时数据。不要从零更换服务或反复询问既有配置。默认沿用下面的Python、脚本和websockets依赖；需要采集时只确认时长、是否调整海域、当前环境是否仍有效。用户希望在自己的PowerShell窗口运行，并实时看到每条消息保存成功。

推荐今后直接输出到桌面“马六甲海峡实验/原始数据”，使用带开始时间的新文件名，保留旧数据。历史六小时文件已经归档，不要覆盖或继续追加进已完成的实验文件。

新对话可以接收这句话：

> 请阅读《说明文档/AIS数据采集操作流程.md》，沿用上次成功的AISStream采集方式，开启逐条保存日志，将新数据直接保存到桌面实验目录。先检查环境，不要更换API服务，不要覆盖旧文件，不要输出我的密钥。此次采集时长为___小时。

## 2. 上次使用的配置

| 项目 | 配置 |
| --- | --- |
| 终端 | Windows PowerShell |
| 项目目录 | C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent |
| 实际脚本 | 上述目录下 src\data\collect_malacca_aisstream.py |
| Python | C:\Users\卿之ya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe |
| 依赖 | 项目目录下 .local_pydeps_ws12，历史安装websockets==12.0 |
| 环境变量 | AISSTREAM_API_KEY、PYTHONPATH |
| WebSocket端点 | wss://stream.aisstream.io/v0/stream |
| 海域参数 | --bbox "1.0,103.0,3.5,104.5" |
| 实时保存参数 | --flush-every 1 |

范围是北纬1.0至3.5、东经103.0至104.5的矩形，主要涉及马六甲东南段/新加坡海峡附近，不能称为整个马六甲海峡完整覆盖。接收的是服务当时推送的数据，不是按历史日期下载。

## 3. 窗口A：准备环境

打开PowerShell。以下代码块按顺序执行：复制一个完整代码块到窗口，按回车，执行完成再执行下一个。不要复制前面的 `PS C:\...>` 提示符，也不要额外给下划线加反斜杠。

第一步：设置路径。即使初始窗口位于System32，也会切换到正确项目。

```powershell
$project = 'C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent'
$python = 'C:\Users\卿之ya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$script = Join-Path $project 'src\data\collect_malacca_aisstream.py'
Set-Location -LiteralPath $project
$env:PYTHONPATH = Join-Path $project '.local_pydeps_ws12'
```

第二步：检查文件与依赖。路径检查应显示True；最后的connect_available应为True，版本应核对为历史使用的12.0。否则先按故障表处理，不启动长时间采集。

```powershell
Test-Path -LiteralPath $python
Test-Path -LiteralPath $script
& $python -c "import websockets; print('version:', websockets.__version__); print('module:', websockets.__file__); print('connect_available:', callable(getattr(websockets, 'connect', None)))"
```

第三步：只在本地输入有效API Key。下面通过隐藏输入设置变量，避免把密钥直接写进命令历史；运行时按提示粘贴真实Key并回车，不要把提示语当成Key。环境变量仍是进程内明文，不应分享终端转储。历史截图曾暴露Key，建议用户在服务账户内自行轮换。

```powershell
$secret = Read-Host '请输入有效的AISStream API Key（输入隐藏）' -AsSecureString
$credential = New-Object System.Management.Automation.PSCredential('AISStream', $secret)
$env:AISSTREAM_API_KEY = $credential.GetNetworkCredential().Password
Remove-Variable secret, credential
```

设置后没有输出是正常现象。环境变量只对当前窗口及它启动的进程生效；关闭后重新打开需要重设。不需要将密钥发给新对话，也不要把它写进本文档。

## 4. 窗口A：启动采集

下面默认六小时。若采集一小时，只把 `$hours = 6` 改为 `$hours = 1`；三分钟短测使用0.05。不要同时运行多个相同输出文件的采集进程。

代码采用桌面真实路径，直接保存至实验目录，不再先写旧项目后搬运。每次启动生成新的时间戳文件名。若有同名文件会停止，防止旧脚本自动追加。

```powershell
$hours = 6
$rawDir = Join-Path ([Environment]::GetFolderPath('Desktop')) '马六甲海峡实验\原始数据'
New-Item -ItemType Directory -Path $rawDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd_HHmmss_fff'
$output = Join-Path $rawDir ("马六甲AIS_{0}小时_{1}.csv" -f $hours, $stamp)
if (Test-Path -LiteralPath $output) { throw '文件已存在，请使用新的输出文件名。' }
Write-Host "输出文件：$output"
& $python -u $script --hours $hours --bbox '1.0,103.0,3.5,104.5' --flush-every 1 --output $output
```

正常的实际采集证据是连续出现并增长的日志：

```text
started: bbox=... output=...
saved 1 AIS position rows
saved 2 AIS position rows
saved 3 AIS position rows
```

`started`只表示连接后已发出订阅，不独立证明鉴权成功或已收到有效消息。`saved N`表示本次进程累计写入N条记录，日志虽然叫position rows，实际上也包括静态消息；不是N艘船。

`--flush-every 1`每条刷新文件并输出日志；`-u`用于Python标准输出无缓冲，不能替代文件flush参数。

## 5. 窗口B：查看是否正在保存

保留窗口A运行，另开一个PowerShell作为窗口B。在下方提示出现时，粘贴窗口A打印的完整“输出文件”路径，不带外层引号。

```powershell
$file = Read-Host '粘贴窗口A输出的完整CSV路径'
Get-Item -LiteralPath $file | Select-Object Name,Length,LastWriteTime
Get-Content -LiteralPath $file -TotalCount 5
```

要自动每10秒检查一次，可执行：

```powershell
while ($true) {
    Get-Item -LiteralPath $file | Select-Object Name,Length,LastWriteTime
    Start-Sleep -Seconds 10
}
```

在窗口B按键盘Ctrl+C只会停止这个检查循环，不会停止窗口A采集。Ctrl+C是组合按键，不是要粘贴的文字。不要对仍在采集的文件使用Excel打开后保存，以免锁文件或改格式。

文件大小增长、尾部新增记录，以及窗口A的saved数增长，能共同证明持续写入。只有文件存在或大小约149字节可能只是表头，不能证明采集成功。未指定逐条flush时可能先缓存在内存，因此文件暂时不增长也不能单凭这一点断言API坏了。

## 6. 完成、暂停与断网

正常完成会显示：

```text
done. saved N rows to ...csv
PS C:\...>
```

脚本计时从本次进程初始化开始，连接和重连等待也计入时长；不是保证累计收到满六小时的有效数据。日志使用UTC的+00:00，北京时间加8小时。

重要局限：现脚本在等待下一条WebSocket消息时没有独立的总时限超时控制；完全无消息时可能超过设定时间才结束。到点不退出，应先看连接日志，不要把“--hours 6”描述成保证精确准点停止。改进超时机制应另做受测代码更新。

需要停止时，在窗口A按Ctrl+C。Windows可能显示CancelledError或KeyboardInterrupt，这是手动中断可能产生的堆栈，不等于之前采集全部失败。逐条flush已写入的记录通常保留，但应结束后读取核实，不能保证恰在中断瞬间的消息完整。

网络/VPN切换可能造成连接中断；现脚本会打印connection error和reconnect编号并尝试重连，退避等待最高60秒。断线时段的历史消息不会由本脚本自动补抓。是否需要VPN取决于本机到服务的实际连通性，不保证关闭后还能采集；长时间采集期间保持稳定网络、终端开启、电脑不睡眠。

## 7. 常见报错及上次解决方式

| 现象 | 解释和处理 |
| --- | --- |
| can't open file，路径在System32下面 | 相对路径基准错误；执行准备环境，使用脚本绝对路径 |
| 缺少AISStream API Key | 在窗口A设置环境变量，不能填“你之前那个Key”等占位文字 |
| module 'websockets' has no attribute 'connect' | 上次是导入环境问题；先看module输出，使用.local_pydeps_ws12和对应Python，不要先换Key |
| Cache entry deserialization failed | 历史安装中出现的缓存警告；最终Successfully installed与导入检查比警告本身更重要 |
| no close frame received or sent | WebSocket异常断开，可能与网络切换有关；等重连并看saved恢复，不能单凭此认定Key无效 |
| 只有started、表头或文件不变 | 检查是否查看本次正确文件、是否有--flush-every 1、日志有无连接错误；必要时短测、检查服务返回，不能无限等待或直接断言API无效 |
| 文件时间仍是前一天 | 很可能查看的是旧文件；对照窗口A本次output路径 |

只有依赖缺失或导入检查失败时才考虑重新安装。以下是历史成功安装方式，不是每次采集都必须执行；使用前先停止失败进程，确认当前Python兼容该版本：

```powershell
& $python -m pip install --no-cache-dir --target (Join-Path $project '.local_pydeps_ws12') 'websockets==12.0'
$env:PYTHONPATH = Join-Path $project '.local_pydeps_ws12'
```

安装后重做导入检查。若目标目录已有损坏或冲突文件，不要盲目覆盖或反复安装，让新对话检查实际导入路径并选择新依赖目录。

## 8. 采集结束后验证及归档

窗口A返回提示符后执行下面的检查，变量$output仍指向本次文件。它们统计的是消息与唯一MMSI，不是分类准确率：

```powershell
$rows = @(Import-Csv -LiteralPath $output)
Write-Host "消息数：$($rows.Count)"
Write-Host "唯一MMSI数：$(@($rows | Select-Object -ExpandProperty mmsi -Unique).Count)"
$rows | Group-Object message_type | Select-Object Name,Count
Get-FileHash -LiteralPath $output -Algorithm SHA256
```

下一步应记录开始/结束接收时间、消息类别、每船轨迹点数、缺口、静态标签覆盖率和SHA256；保留原始CSV，另做清洗副本。新数据不自动替换Demo，也不代表模型已经训练。

之前六小时采集记录：2026-09-05，北京时间约11:57:50至17:57:41，13,045条记录，451个MMSI。旧项目原文件为 `data_raw\ais_malacca_6hour_visible.csv`，归档文件为 `原始数据/马六甲6小时AIS采集数据_2026-09-05.csv`。今后直接输出到桌面无需再复制；这些历史名称仅用于核对，不用于新采集输出。

## 9. 数据与费用边界

当前脚本只订阅PositionReport和ShipStaticData，不覆盖Class B相关消息。静态与动态字段分别出现，需按MMSI关联，不能认为每一条位置消息都包含船型。PositionReport的timestamp可能只有分钟内秒值，分析时不能直接当完整日期时间。

这段采集脚本没有调用大模型接口，单独在本地运行六小时不会按AIS记录消耗大模型token；与AI对话、请求AI分析另算。AIS服务价格、条款、限额应在正式使用时查官方当前说明，本文不承诺永久免费，也不保证实时覆盖或服务可用性。不要未经用户确认开通付费订阅。

本流程的依据是本机脚本和历史成功记录，不是一次新的在线采集测试。代码未来改变时，应同步更新命令、字段覆盖、超时行为和本文件。
