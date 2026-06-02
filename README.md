# 🚢 航运物流运输计划异常检测系统

> 针对中远海运科技、中国外运等航运物流科技岗位设计的数据分析项目

**在线演示**：[点击访问]() <!-- 部署后填入 Streamlit Cloud 链接 -->

---

## 项目简介

本系统采用**三层异常检测引擎**对运输订单进行异常识别，自动生成专业分析报告。

- 宏观层：港口月度吞吐量季节性分析（模拟交通运输部数据格式）
- 微观层：运输订单延误异常检测（规则 + 统计 + 机器学习三层投票）
- 输出层：Streamlit 可视化界面 + Word 报告自动生成 + AI 智能结论（接 DeepSeek）

---

## 核心功能

| 功能 | 说明 |
|------|------|
| 数据接入 | 支持上传 CSV / 使用内置演示数据 |
| 异常检测 | 规则阈值 · Z-Score（按路线分组）· Isolation Forest 三层投票 |
| 可视化 | 异常等级分布 · 承运商绩效矩阵 · 港口热力图 · 延误分布 |
| AI 分析 | 接入 DeepSeek API，自动生成业务结论 |
| 报告导出 | 一键下载 Word 报告 + 图表 PNG + 异常明细 CSV |

---

## 技术栈

```
Python · Streamlit · Pandas · Scikit-learn · Matplotlib · python-docx · DeepSeek API
```

---

## 本地运行

```bash
# 1. 克隆项目
git clone https://github.com/你的用户名/shipping-anomaly-detector.git
cd shipping-anomaly-detector

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`

---

## 数据字段说明

上传 CSV 需包含以下字段：

```
订单ID, 承运商, 货物类型, 运输方式, 起运港, 目的港,
计划发货日期, 计划到达日期, 实际到达日期,
计划运输天数, 实际延误天数, 货重_吨, 运费_USD
```

不上传则自动使用内置演示数据（2000 条模拟订单）。

---

## 部署到 Streamlit Cloud

1. Fork 本项目到你的 GitHub
2. 登录 [share.streamlit.io](https://share.streamlit.io)
3. 选择仓库 → 主文件填 `app.py` → Deploy

DeepSeek API Key 在侧边栏输入，不需要写入代码。

---

## 项目背景

本项目模拟航运物流企业的实际数据分析场景：

- **宏观数据**：港口吞吐量季节性规律（参考交通运输部统计数据格式）
- **微观数据**：参考 Kaggle Supply Chain Shipment Pricing Dataset 字段设计
- **业务场景**：运输计划偏差分析、承运商 KPI 考核、高风险路线识别

---

## 作者

宋孙洋 · 莫纳什大学商业信息系统硕士


---

## 中文展示定位（当前升级版补充）

**项目名称：** 航运数据异常检测系统

本项目保留原版操作方式：双击 `run_windows.bat` 后会自动创建虚拟环境、安装依赖，并在本地浏览器打开 Streamlit。若页面侧边栏提供 API Key 输入框，请先输入 Key 并点击“应用/Apply”后再使用 AI 生成功能。

**注意：** 不要把 API Key 提交到 GitHub；部署公网 Demo 时建议使用 Streamlit Secrets。
