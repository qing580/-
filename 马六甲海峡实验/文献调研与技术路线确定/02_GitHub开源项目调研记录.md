# GitHub 开源项目调研记录

## 1. 调研目的

本文件记录与 AIS 船舶分类、轨迹分类、船舶行为识别相关的开源项目。它们的作用不是直接复制代码，而是帮助确定本项目技术路线、模型输入字段、实验评价方式和 Demo 展示方式。

## 2. 重点开源项目

| 序号 | 项目 | 方向 | 可借鉴内容 | 本项目可怎么用 |
|---|---|---|---|---|
| 1 | GlobalFishingWatch/vessel-classification | AIS/VMS 船舶分类 | 使用 AIS/VMS 时间序列和 1D CNN 识别船舶类别及行为 | 支撑“用轨迹序列做船型分类”，可作为深度学习路线参考 |
| 2 | hoyon-lab/AIS_tracking | AIS 分类与异常检测 | 包含 CNN-LSTM、TCN、Transformer 等结构，输入字段和本项目 AIS 字段接近 | 可参考其模型对比和结果可视化思路 |
| 3 | destiny1103/GIN-Ship-type | 图神经网络船型识别 | 将 AIS 轨迹或船舶关系转为图结构，类别包括 Cargo、Tanker、Passenger、Tug、Fishing 等 | 后续可作为高级创新方向：图神经网络船型识别 |
| 4 | AIS 轨迹分类类项目 | 轨迹图像/CNN | 将轨迹转换成图像，用 CNN 做分类 | 可用于后续“轨迹图像 + AIS 序列”的多模态升级 |
| 5 | LightGBM/XGBoost 分类模板项目 | 表格特征分类 | 对速度、航向、转向率等统计特征做树模型分类 | 适合作为小数据阶段的机器学习基线 |

## 3. 项目启发

### 3.1 本项目不应只做规则映射

规则映射只是 Demo 的第一阶段，适合保证基础可解释性。但导师关注“技术含量”时，需要加入模型学习过程。开源项目中常见做法是把 AIS 点序列输入 CNN、LSTM、TCN 或 Transformer。

### 3.2 先做可解释基线，再做深度学习

因为当前马六甲数据仍在积累中，建议先做传统机器学习基线，例如 Random Forest 或 LightGBM。它们对小数据友好，还能输出特征重要性，便于写论文和答辩。

### 3.3 低置信度样本进入人工补全表

当前未知船多，本质上是标签不完整。可以借鉴半监督学习和主动学习思路：

1. 高置信度预测结果自动补全；
2. 低置信度或规则/模型冲突样本进入人工补全表；
3. 人工确认后的样本重新进入训练集；
4. 模型不断迭代，未知船比例逐步降低。

## 4. 推荐用于 Demo 的体现方式

在网页 Demo 中，不需要展示复杂训练代码，而是把模型结果体现在右侧报告里：

- 规则分类结果；
- 机器学习预测船型；
- 深度学习预测船型；
- 预测置信度；
- 是否需要人工复核；
- 模型依据，例如速度分布、航向变化、轨迹长度、停留比例。

这样评委看到的不只是“颜色分类”，而是一个有分析链条的智能体。

## 5. 来源链接

- GlobalFishingWatch/vessel-classification：https://github.com/GlobalFishingWatch/vessel-classification
- hoyon-lab/AIS_tracking：https://github.com/hoyon-lab/AIS_tracking
- GIN-Ship-type：https://github.com/destiny1103/GIN-Ship-type

