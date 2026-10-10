# 船舶分类在线 Demo 必要代码说明

这个文件夹里的代码用于复现“马六甲海峡 AIS 数据采集 -> 船舶分类 -> 在线地图展示”的流程。

## 1. 采集马六甲 AIS 数据.py

作用：连接 AISStream，采集马六甲海峡附近的 AIS 数据，保存成 CSV 表格。

主要输出：原始 AIS 数据，例如船舶 MMSI、经纬度、航速、航向、船型码、船名等。

常用命令示例：

```powershell
$env:AISSTREAM_API_KEY="你的AISStream API Key"
& "C:\Users\卿之ya\AppData\Local\Python\pythoncore-3.14-64\python.exe" "C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent\src\data\collect_malacca_aisstream.py" --hours 0.17 --output "C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent\data_raw\ais_malacca_10min.csv" --flush-every 1
```

说明：`--hours 0.17` 大约采集 10 分钟。如果正式实验，可以改成 `--hours 1`、`--hours 6` 或 `--hours 24`。

## 2. 船舶分类脚本.py

作用：读取采集到的 AIS 数据，把船舶分成货船、油轮、渔船、其他、未知。

分类依据：

- AIS 船型码 30：渔船
- AIS 船型码 70-79：货船
- AIS 船型码 80-89：油轮
- 其他船型码：其他
- 缺少船型码且人工补全表也没有结果：未知

常用命令示例：

```powershell
& "C:\Users\卿之ya\AppData\Local\Python\pythoncore-3.14-64\python.exe" "C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent\src\features\classify_vessels.py" --input "C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent\data_raw\ais_malacca_10min.csv" --registry "C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent\data_processed\vessel_registry.csv" --output "C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent\results\tables\malacca_vessel_classification_10min.csv"
```

## 3. 生成Demo6船舶分类在线地图版.py

作用：把 AIS 轨迹和船舶分类结果合并，生成可以双击打开的网页地图。

网页里能看到：

- 船舶在地图上的位置和轨迹
- 不同船型用不同颜色显示
- 按货船、油轮、渔船、其他、未知筛选
- 点击船舶查看分类依据和是否需要人工复核

常用命令示例：

```powershell
& "C:\Users\卿之ya\AppData\Local\Python\pythoncore-3.14-64\python.exe" "C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent\src\visualization\build_demo_v6_vessel_classification_online.py"
```

生成结果：

```text
frontend/demo/demo_map_v6_vessel_classification_online.html
```

## 4. requirements.txt

作用：记录运行这些脚本需要安装的 Python 库。

安装命令：

```powershell
cd "C:\Users\卿之ya\Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent"
& "C:\Users\卿之ya\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m pip install -r requirements.txt
```

## 推荐运行顺序

1. 先运行“采集马六甲 AIS 数据.py”，得到原始 AIS 表格。
2. 再运行“船舶分类脚本.py”，得到船舶分类结果表。
3. 最后运行“生成Demo6船舶分类在线地图版.py”，生成在线地图网页。
4. 打开“大创/网页演示/Demo网页/Demo6船舶分类在线地图版.html”查看展示效果。

## 注意

在线地图版需要联网，因为底图来自在线地图服务。如果没有网络，地图底图可能显示不出来，但船舶分类数据和网页代码本身还在。
