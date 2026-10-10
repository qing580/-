# **《基于AIS数据和LSTM网络的船舶航行动态预测》核心内容总结**

本报告对任宇翔等人撰写的《基于AIS数据和LSTM网络的船舶航行动态预测》一文进行了系统性提炼。该论文重点研究了如何利用深度学习技术，根据船舶历史航行轨迹精准预测其未来的动态行为（位置、航向、航速），这对于水上交通监管（VTS）和船舶防碰撞预警具有极高的实用价值。

## **一、 论文采集与使用的数据说明**

为了训练出能够精准预测的人工智能模型，论文使用了真实的海上船舶航行数据作为“教材”。

### **1\. 核心数据源：船舶自动识别系统（AIS）数据**

* **数据定位**：AIS 数据是水上交通领域的标准大数据。  
* *初学者指南*：可以把 AIS 数据理解为船舶随身携带的“行车记录仪 \+ GPS \+ 广播”。它每隔几秒钟就会把船只当前的状态发送出去，形成一条完整的时间线。

### **2\. 提取的关键特征字段**

论文并没有使用 AIS 报文中的所有信息，而是精准剥离出了与“航行动态”最相关的 6 个核心特征：

* MMSI：船舶唯一识别码（船舶的“身份证”，用于锁定同一艘船）。  
* UTC：时间戳（记录该状态发生的准确时间）。  
* Longitude & Latitude：经度和纬度（船具体在哪里）。  
* COG（Course Over Ground）：对地航向（船头正指向哪个角度）。  
* SOG（Speed Over Ground）：对地航速（船开得有多快）。

### **3\. 数据预处理（数据清洗与打包）**

在把数据喂给人工智能之前，作者进行了严格的“洗菜”过程：

* **航迹插值修复**：真实的 AIS 数据常常会因为信号不好而丢包。论文采用了“线性插值法”，把原本不规律的数据，修复成了**每隔10秒一个点**的标准等间距数据。  
* **归一化处理**：将经纬度、航速等不同单位的庞大数字，按比例缩放到了 ![][image1] 到 ![][image2] 的区间内。  
  * *初学者指南*：经纬度的数字可能高达一百多，而航速只有十几，直接让机器学，机器会被大数字带偏。归一化就像是把所有指标换算成“百分制”，让机器一视同仁地学习。

## **二、 论文所用核心算法解析**

为了实现高精度的预测，论文摒弃了传统的数学公式推导，引入了人工智能领域处理时间序列的“王牌”算法。

### **1\. 核心算法：LSTM（长短期记忆网络）**

* **算法本质**：这是一种特殊的深度循环神经网络（RNN）。  
* *初学者指南*：  
  * **传统神经网络（如 BP 网络）的缺点**：它们像是一个“没有记忆的直男”，只能看到当前这一秒的经纬度，无法把前一分钟的轨迹连贯起来思考。  
  * **LSTM 的绝招**：LSTM 内部有一个“记忆细胞（Cell）”**和三个**“门（输入门、遗忘门、输出门）”。它就像一个聪明的做题家，**遗忘门**会扔掉没用的信息（比如很久之前的一个小颠簸），**输入门**会记下当前有用的趋势，**输出门**则结合过去的记忆和现在的状态，给出下一步的预测。这就使得 LSTM 特别擅长处理像船舶轨迹这样“前后高度相关”的连串数据。

### **2\. 模型训练机制**

* **滑动窗口预测**：论文采用前 ![][image3] 个历史航迹点作为输入，去预测第 ![][image4] 个航迹点。这就好比让机器看了船只过去 5 分钟的连续动作，然后猜它接下来的 10 秒钟会在哪里。  
* **评估标准**：使用平均绝对误差（MAE）来衡量预测的准不准，误差越小，模型越聪明。

### **3\. 算法对比与实验结论**

为了证明 LSTM 有多厉害，作者设立了两个“对照组”来进行同场竞技：

* **对照组 A：传统航迹推算法**（靠纯物理公式和几何推导）。  
* **对照组 B：BP 神经网络**（一种没有时间记忆功能的传统人工智能）。

**最终实验结论**：

LSTM 模型在经度、纬度、航向、航速四个维度的预测上，实现了**全方位的碾压**。

* 在航速和航向上，BP 神经网络预测出来的线条像锯齿一样抖动剧烈，而 LSTM 的预测曲线极其平滑，几乎与船舶真实的航行曲线完美重合。  
* **总结论**：基于 LSTM 网络的船舶航行行为预测模型具有**精度高、鲁棒性（抗干扰能力）强、泛化性好**的优点，完美攻克了传统方法面对船舶复杂非线性运动时“算不准”的难题。

## **三、 总结**

本论文是一次深度学习在海事交通领域的成功应用。作者敏锐地抓住了船舶轨迹“时间序列”的本质特征，通过提取 AIS 动态数据，并投喂给最擅长记忆时间规律的 **LSTM 神经网络**。该研究为未来的智能船舶自动驾驶、海事交管中心（VTS）提前发现偏航危险、预防船舶碰撞与搁浅，提供了非常坚实的技术底座。

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAbCAYAAABFuB6DAAAA6ElEQVR4XmNgGAXEAgUFBQF5eXkrJSUlOWNjY1Z0eTCQkZERAip6AMRzgXgLEL8FYk90RZxAwc0qKiqiUCFGoOkJQLFPyOoY5eTk5gMF/yELioqK8gDFDgCxJlgAqEgQyDkNxF+RFYIA0NSFQHlfMAeoQBKIH+JRWA7mgIyGOhy/QiDDGKSIoEJFRUV9kO8IKiTajUDAAlS0Boj/IyuCBQ/IaXBBoM4IdIVSUlIiQLGrwOjkhwtKS0sLAxWfQhYE8sOBCn/BFcEANJj2AXE0ELcC8TegtWXo6sAAGAJ2UIWBIFvQ5YcNAAC7yUGXzZjgPQAAAABJRU5ErkJggg==>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAbCAYAAABFuB6DAAAAaUlEQVR4XmNgGAUkAkYZGRkVIM2MLgEHcnJyWgoKChvl5eUfALEkujwD0ARdoMQVIP4GxP+B+CFWhTAANNEYqODrqEKsgPoKgdHnAVTwG4hfAdkGQCFGFAUg3VBT/qNjUVFRHhTFIwoAAHWnNqj2v6FHAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAZCAYAAADe1WXtAAABsUlEQVR4Xu2UzysEcRjGZ0IRDn6ssTs7O9bSphQ1SYqLpBxEOTq4Ojg5kL/ASTk4bcnRxVU5OCjlopRyoi0ublJqRcr6vHbe7btjU+um9qmn2ed5n+/7/THzXcuqow6B7bpul+/78Uwm0xMtGrClTm6C3w3RYgUIXcFLuA8f4JoVGdQH8C/gDczBO6xRM1MGK0xSXDS0rLiIt2rmwmZHyWSyRXQqldpG52UyM/cNivMUnz3PG1ZPmsJTx3FaDe+T7Iyhh+AT3EPa6itsZh9QISsJm+6oR7N+v3QscfVisVgb+gwWqAfqVwUrnmJHt+l02ldPBv3StCi7Vb8MVtdJcckvvYA3mvaaddn2n5rSaIHAMoETntOWcU7hudfW1EQQBE1hcMMKG6PnamoqwUQi0R3xChKG66KrvahsNtuOPoevvIex8uDwm7yGx2y/WX0JhivYFM2zA/3CyxsxMvFwonuOz1XfIuRg5qs0LcJ3v3Qd1fug+aSh9Ts9RDaqL7BptstMg2romcKc/FYf/UjTA/UYt4VX4DmumQrwJ+HJVYUrPw7dgNwwdjcrOfO21fEP8QW80XzZkqtupAAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAZCAYAAADe1WXtAAABTElEQVR4Xu2UvUrEQBSFE4KgaKXGuPmbhGhnl0phG3tRsLSwEwsrC30KwXrBxxAsfAIFwVawsLG1UrRRvwszy+ywu4mt5INDNveeOblkJut5HR2CnyTJklKqV1XVitt0qet6hovv1kcg7AHdoyv0gk4oB64PAnpbRVHchWG44DaHMGGKac+6l4l/qB3bPmqv6Bt9SH9qaJ7nO5jesizbMDVZhG6jKJq3aj0eNKv900PBT9N0zdzwe06HXtgmQ9vQEZi4z0RPZVkqtye0DmW6RYz7aIA+CV11PYY/hRK0i/mARTdct70JR6Z1qI2cQVnE4jNvTHCrUNnVOI6Xndq73qxTuy40huoz+Yiu5biYutJnkYBz2y80hrLDEYbnMaEy5RfatP1CYyj4hF2yUeumYN4pGuhv3CYg9Ej6k47cEP5EMvlU0aFM4vY7/iG/4ChYkUMdUSUAAAAASUVORK5CYII=>