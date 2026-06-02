"""
航运物流异常检测系统 - Streamlit Web 版
支持：上传 CSV / 使用演示数据 → 异常检测 → 可视化 → AI 分析 → 下载报告

展示版改动：
1. 默认使用“AI 演示模式”，HR 打开后无需填写 DeepSeek API Key 也能看到完整分析结论。
2. DeepSeek API Key 被放到“高级功能”里，只有需要真实调用时才填写。
3. 移除远程 logo 图片，避免 Streamlit Cloud 上出现左上角破图标。
4. 兼容根目录模块与 src/ 模块两种结构。
"""

import os
import sys
import io
import tempfile
import time
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── 路径配置：兼容“模块放根目录”和“模块放 src 目录”两种项目结构 ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
SRC_DIR = os.path.join(BASE_DIR, "src")
if os.path.isdir(SRC_DIR) and SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from generate_data import generate_port_throughput, generate_shipment_orders
from detector import ShippingAnomalyDetector
from charts import (
    plot_anomaly_overview,
    plot_carrier_performance,
    plot_port_throughput,
    plot_delay_distribution,
)
from report_generator import generate_report
from ai_analyst import generate_ai_summary, generate_ai_carrier_insight


# ══════════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════════

def get_streamlit_secret_api_key() -> str:
    """从 Streamlit Secrets 中读取 DeepSeek API Key。没有配置时安全返回空字符串。"""
    possible_keys = [
        "DEEPSEEK_API_KEY",
        "deepseek_api_key",
        "DEEPSEEK_KEY",
        "deepseek_key",
    ]
    for key in possible_keys:
        try:
            value = st.secrets.get(key, "")
            if value:
                return str(value).strip()
        except Exception:
            pass

    # 兼容 [deepseek] api_key = "..." 这种写法
    try:
        value = st.secrets.get("deepseek", {}).get("api_key", "")
        if value:
            return str(value).strip()
    except Exception:
        pass

    return ""


def safe_pct(value: Any) -> float:
    """把小数比例转成百分比数值，失败时返回 0。"""
    try:
        return float(value) * 100
    except Exception:
        return 0.0


def generate_demo_ai_summary(stats: Dict[str, Any]) -> str:
    """
    不调用外部 API 的演示版 AI 分析。
    目的：给 HR / 面试官展示完整业务闭环，避免因为没有 API Key 导致页面体验断裂。
    """
    total_orders = stats.get("total_orders", 0)
    total_anomalies = stats.get("total_anomalies", 0)
    anomaly_rate = safe_pct(stats.get("anomaly_rate", 0))
    avg_delay = stats.get("avg_delay", 0)

    severe_count = 0
    severity_dist = stats.get("severity_dist", {})
    if isinstance(severity_dist, dict):
        severe_count = severity_dist.get("严重", 0)

    # 承运商风险
    carrier_text = "暂无足够承运商数据。"
    carrier_stats = stats.get("carrier_stats")
    if isinstance(carrier_stats, pd.DataFrame) and not carrier_stats.empty:
        cs = carrier_stats.copy()
        if "异常率" in cs.columns:
            cs = cs.sort_values("异常率", ascending=False)
        top_carriers = []
        for _, row in cs.head(3).iterrows():
            name = row.get("承运商", "未知承运商")
            rate = safe_pct(row.get("异常率", 0))
            delay = row.get("平均延误天数", 0)
            try:
                delay = round(float(delay), 1)
            except Exception:
                pass
            top_carriers.append(f"**{name}**（异常率约 {rate:.1f}%，平均延误 {delay} 天）")
        carrier_text = "、".join(top_carriers)

    # 路线风险
    route_text = "暂无足够路线数据。"
    route_stats = stats.get("route_stats")
    if isinstance(route_stats, pd.DataFrame) and not route_stats.empty:
        rs = route_stats.copy()
        if "异常率" in rs.columns:
            rs = rs.sort_values("异常率", ascending=False)
        top_routes = []
        for _, row in rs.head(3).iterrows():
            route = row.get("路线", "未知路线")
            rate = safe_pct(row.get("异常率", 0))
            max_delay = row.get("最大延误", 0)
            top_routes.append(f"**{route}**（异常率约 {rate:.1f}%，最大延误 {max_delay} 天）")
        route_text = "、".join(top_routes)

    return f"""
### 业务分析结论（演示模式）

1. **整体风险水平：可控但需要重点跟踪。**  
   本次共分析 **{total_orders:,}** 条运输订单，识别出 **{total_anomalies:,}** 条异常订单，整体异常率约 **{anomaly_rate:.1f}%**，平均延误约 **{avg_delay} 天**。从运营视角看，异常并非大面积失控，而是集中在部分承运商、路线或极端延误订单上。

2. **核心风险点：严重异常订单需要优先处理。**  
   当前严重异常订单约 **{severe_count}** 条。建议业务团队优先复核这些订单的真实原因，例如港口拥堵、承运商履约能力不足、天气影响、船期变更或计划排程不合理。

3. **需重点关注的承运商：**  
   {carrier_text}

4. **需重点关注的高风险路线：**  
   {route_text}

5. **行动建议：**  
   - 对异常率较高的承运商建立月度绩效复盘机制；  
   - 对高风险路线设置更保守的运输时间缓冲；  
   - 对严重异常订单建立人工复核清单，区分系统性风险与偶发风险；  
   - 将本系统接入真实 TMS / Excel 台账后，可形成“异常识别 → 业务复核 → 报告输出”的闭环。

> 当前为作品集演示模式，未调用外部大模型 API。需要真实 DeepSeek 分析时，可在左侧“高级功能”中输入 API Key。
"""


def generate_demo_carrier_insight(carrier_name: str, row: Dict[str, Any]) -> str:
    """不调用外部 API 的单承运商演示洞察。"""
    total = row.get("总订单数", "-")
    avg_delay = row.get("平均延误天数", 0)
    delay_rate = safe_pct(row.get("延误率", 0))
    anomaly_count = row.get("异常订单数", 0)
    anomaly_rate = safe_pct(row.get("异常率", 0))

    return f"""
**{carrier_name} 承运商洞察（演示模式）**

- 该承运商本次样本订单数为 **{total}**，异常订单数为 **{anomaly_count}**，异常率约 **{anomaly_rate:.1f}%**。  
- 平均延误约 **{avg_delay:.2f} 天**，延误率约 **{delay_rate:.1f}%**。  
- 如果异常率高于整体平均水平，建议优先复盘该承运商的重点线路、旺季履约能力和港口节点衔接。  
- 后续可将该承运商纳入月度 KPI 看板，持续跟踪准时率、平均延误、严重异常订单占比三个指标。
"""


def try_generate_real_ai_summary(stats: Dict[str, Any], api_key: str) -> Optional[str]:
    """真实调用 DeepSeek。失败时返回 None，不中断页面。"""
    try:
        return generate_ai_summary(stats, api_key.strip())
    except Exception as exc:
        st.warning(f"真实 AI 分析暂时不可用，已自动切换为演示分析。原因：{exc}")
        return None


def try_generate_real_carrier_insight(carrier_name: str, row: Dict[str, Any], api_key: str) -> Optional[str]:
    """真实调用 DeepSeek 生成单承运商洞察。失败时返回 None。"""
    try:
        return generate_ai_carrier_insight(carrier_name, row, api_key.strip())
    except Exception as exc:
        st.warning(f"真实 AI 洞察暂时不可用，已自动切换为演示洞察。原因：{exc}")
        return None


# ══════════════════════════════════════════════════════════════
#  页面配置
# ══════════════════════════════════════════════════════════════
if "shipping_api_key" not in st.session_state:
    st.session_state.shipping_api_key = ""
if "ai_mode" not in st.session_state:
    st.session_state.ai_mode = "演示模式（推荐，无需 Key）"

st.set_page_config(
    page_title="航运异常检测系统",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 全局样式 ────────────────────────────────────────────────────
st.markdown(
    """
<style>
  .metric-card {
    background: linear-gradient(135deg,#1A3C5E,#2563a8);
    border-radius:12px; padding:20px 24px; color:white; text-align:center;
  }
  .metric-value { font-size:2rem; font-weight:700; margin:0; }
  .metric-label { font-size:.85rem; opacity:.8; margin:4px 0 0; }
  .risk-severe  { background:#fff0ee; border-left:4px solid #E8412B;
                  padding:8px 12px; border-radius:4px; margin:4px 0; }
  .risk-medium  { background:#fffbee; border-left:4px solid #F5A623;
                  padding:8px 12px; border-radius:4px; margin:4px 0; }
  .risk-normal  { background:#f0fff4; border-left:4px solid #27AE60;
                  padding:8px 12px; border-radius:4px; margin:4px 0; }
  .section-title{ font-size:1.1rem; font-weight:600;
                  color:#1A3C5E; margin:16px 0 8px; }
  .small-note { font-size:0.9rem; color:#667085; }
</style>
""",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════
#  侧边栏
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    # 不再使用远程图片，避免 Streamlit Cloud 出现破图标
    st.title("🚢 航运异常检测")
    st.caption("Shipping Anomaly Detection System")
    st.divider()

    # AI 分析模式
    st.subheader("🤖 AI 分析")
    ai_mode = st.radio(
        "选择 AI 模式",
        ["演示模式（推荐，无需 Key）", "高级功能：使用 DeepSeek API Key", "关闭 AI 分析"],
        index=["演示模式（推荐，无需 Key）", "高级功能：使用 DeepSeek API Key", "关闭 AI 分析"].index(
            st.session_state.ai_mode
        ),
        help="简历展示建议使用演示模式。面试现场如需真实大模型分析，可切换到高级功能。",
    )
    st.session_state.ai_mode = ai_mode

    cloud_api_key = get_streamlit_secret_api_key()
    api_key = ""

    if ai_mode == "演示模式（推荐，无需 Key）":
        st.success("已开启演示模式：无需 API Key，HR 可直接体验完整流程。")
        st.caption("该模式展示的是基于检测结果生成的固定业务分析模板，不调用外部 API。")

    elif ai_mode == "高级功能：使用 DeepSeek API Key":
        st.info("高级功能仅用于真实调用 DeepSeek。Key 不会保存到 GitHub。")

        if cloud_api_key:
            use_cloud_key = st.checkbox(
                "优先使用 Streamlit Secrets 中配置的 API Key",
                value=True,
                help="适合正式展示版：你在 Streamlit Cloud 后台配置 Key，访问者无需填写。",
            )
        else:
            use_cloud_key = False
            st.caption("未检测到 Streamlit Secrets 中的 API Key。你可以手动填写临时 Key。")

        if use_cloud_key and cloud_api_key:
            api_key = cloud_api_key
            st.success("已读取云端 API Key，真实 AI 分析可用。")
        else:
            api_key_input = st.text_input(
                "DeepSeek API Key",
                type="password",
                value=st.session_state.shipping_api_key,
                placeholder="sk-xxxxxxxxxxxx",
                help="只保存在本次 Streamlit 会话，不会写入 GitHub。",
            )
            col_apply, col_clear = st.columns(2)
            with col_apply:
                if st.button("✅ 应用", use_container_width=True):
                    st.session_state.shipping_api_key = api_key_input.strip()
                    if st.session_state.shipping_api_key:
                        st.success("已应用，真实 AI 分析已开启。")
                    else:
                        st.info("未填写 Key，将无法使用真实 AI 调用。")
            with col_clear:
                if st.button("🧹 清除", use_container_width=True):
                    st.session_state.shipping_api_key = ""
                    st.rerun()
            api_key = st.session_state.shipping_api_key.strip()

        if not api_key:
            st.warning("当前未配置 API Key。运行后将自动回退到演示分析。")

    else:
        st.caption("AI 分析已关闭，只运行本地异常检测与图表报告。")

    use_ai_demo = ai_mode == "演示模式（推荐，无需 Key）"
    use_ai_real = ai_mode == "高级功能：使用 DeepSeek API Key" and bool(api_key.strip())

    st.divider()

    # 数据来源
    st.subheader("📂 数据来源")
    data_source = st.radio(
        "选择数据来源",
        ["使用演示数据", "上传订单 CSV", "上传吞吐量 CSV（可选）"],
        index=0,
    )

    uploaded_orders = None
    uploaded_throughput = None

    if data_source == "上传订单 CSV":
        uploaded_orders = st.file_uploader(
            "上传运输订单 CSV",
            type="csv",
            help="需包含字段：计划发货日期、计划到达日期、实际到达日期、承运商、运输方式、起运港、目的港",
        )
        st.caption(
            "字段模板：订单ID,承运商,货物类型,运输方式,起运港,目的港,"
            "计划发货日期,计划到达日期,实际到达日期,计划运输天数,实际延误天数,货重_吨,运费_USD"
        )

    if data_source == "上传吞吐量 CSV（可选）":
        uploaded_throughput = st.file_uploader("上传港口吞吐量 CSV", type="csv")

    st.divider()

    # 检测参数
    st.subheader("⚙️ 检测参数")
    zscore_threshold = st.slider(
        "Z-Score 阈值",
        1.5,
        4.0,
        2.5,
        0.1,
        help="数值越小越敏感，报警越多。",
    )
    iforest_contam = st.slider(
        "Isolation Forest 异常比例",
        0.01,
        0.15,
        0.05,
        0.01,
        help="预期数据中的异常比例。若 detector.py 支持该参数，会自动写入。",
    )
    carrier_filter = st.multiselect(
        "筛选承运商（留空=全部）",
        options=["中远海运", "马士基", "中外运", "德邦物流", "顺丰快运"],
    )

    st.divider()
    run_btn = st.button("🚀 开始分析", type="primary", use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  主区域 - 未运行时展示引导
# ══════════════════════════════════════════════════════════════
if not run_btn:
    st.markdown("## 🚢 航运物流运输计划异常检测系统")
    st.markdown(
        "本系统采用**三层异常检测引擎**（规则阈值 + 统计 Z-Score + Isolation Forest）"
        "对运输订单进行异常识别，并自动生成图表、异常明细与 Word 报告。"
    )

    st.info(
        "简历展示版默认开启 **AI 演示模式**：访问者无需填写 API Key，点击「开始分析」即可完整体验。"
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info("**📋 Step 1**\n\n选择数据来源（演示或上传）")
    with col2:
        st.info("**🔍 Step 2**\n\n调整检测参数（侧边栏）")
    with col3:
        st.info("**🤖 Step 3**\n\n默认使用 AI 演示模式")
    with col4:
        st.info("**🚀 Step 4**\n\n点击「开始分析」")

    st.divider()
    st.markdown("### 📌 支持的数据字段")
    st.code(
        "订单ID, 承运商, 货物类型, 运输方式, 起运港, 目的港,\n"
        "计划发货日期, 计划到达日期, 实际到达日期,\n"
        "计划运输天数, 实际延误天数, 货重_吨, 运费_USD",
        language="text",
    )
    st.stop()


# ══════════════════════════════════════════════════════════════
#  运行分析
# ══════════════════════════════════════════════════════════════
with st.spinner("正在准备数据..."):
    tmpdir = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "charts"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "output"), exist_ok=True)

    orders_path = os.path.join(tmpdir, "data", "shipment_orders.csv")
    throughput_path = os.path.join(tmpdir, "data", "port_throughput.csv")
    chart_dir = os.path.join(tmpdir, "charts")
    report_path = os.path.join(tmpdir, "output", "运输计划异常检测报告.docx")

    # 数据加载
    if uploaded_orders is not None:
        df_orders = pd.read_csv(uploaded_orders)
        df_orders.to_csv(orders_path, index=False, encoding="utf-8-sig")
    else:
        df_orders = generate_shipment_orders(tmpdir)

    if uploaded_throughput is not None:
        df_tp = pd.read_csv(uploaded_throughput)
        df_tp.to_csv(throughput_path, index=False, encoding="utf-8-sig")
    else:
        df_tp = generate_port_throughput(tmpdir)

    # 承运商筛选
    if carrier_filter:
        df_orders = df_orders[df_orders["承运商"].isin(carrier_filter)]
        df_orders.to_csv(orders_path, index=False, encoding="utf-8-sig")

with st.spinner("正在运行异常检测引擎..."):
    detector = ShippingAnomalyDetector(orders_path, throughput_path)

    # 注入用户参数：兼容不同 detector.py 里的属性命名
    if hasattr(detector, "zscore_threshold"):
        detector.zscore_threshold = zscore_threshold
    if hasattr(detector, "iforest_contamination"):
        detector.iforest_contamination = iforest_contam
    if hasattr(detector, "contamination"):
        detector.contamination = iforest_contam
    if hasattr(detector, "iforest_contam"):
        detector.iforest_contam = iforest_contam

    result = detector.run_all()
    stats = detector.get_summary_stats(result)

with st.spinner("正在生成图表..."):
    chart_paths = {
        "anomaly_overview": plot_anomaly_overview(stats, chart_dir),
        "carrier_performance": plot_carrier_performance(stats, chart_dir),
        "port_throughput": plot_port_throughput(df_tp, chart_dir),
        "delay_distribution": plot_delay_distribution(result, chart_dir),
    }

# AI 分析：默认演示，真实调用失败则回退演示，不阻塞页面
ai_summary = None
if use_ai_demo:
    ai_summary = generate_demo_ai_summary(stats)
elif use_ai_real:
    with st.spinner("🤖 DeepSeek 正在生成真实 AI 分析结论..."):
        ai_summary = try_generate_real_ai_summary(stats, api_key.strip())
    if not ai_summary:
        ai_summary = generate_demo_ai_summary(stats)

with st.spinner("正在生成 Word 报告..."):
    generate_report(stats, result, chart_paths, report_path)

st.success("✅ 分析完成！")


# ══════════════════════════════════════════════════════════════
#  展示结果
# ══════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 总览", "🏢 承运商分析", "🗺️ 路线分析", "📋 异常订单明细", "📥 下载报告"]
)


# ════════ Tab 1：总览 ════════════════════════════════════════════
with tab1:
    sev = stats["severity_dist"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""<div class="metric-card">
            <p class="metric-value">{stats['total_orders']:,}</p>
            <p class="metric-label">📦 总分析订单</p></div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""<div class="metric-card">
            <p class="metric-value">{stats['total_anomalies']:,}</p>
            <p class="metric-label">⚠️ 检测异常订单</p></div>""",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""<div class="metric-card">
            <p class="metric-value">{stats['anomaly_rate']*100:.1f}%</p>
            <p class="metric-label">📈 整体异常率</p></div>""",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"""<div class="metric-card">
            <p class="metric-value">{stats['avg_delay']}天</p>
            <p class="metric-label">⏱️ 平均延误</p></div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    if ai_summary:
        label = "🤖 AI 智能分析结论（演示模式）" if use_ai_demo or not use_ai_real else "🤖 AI 智能分析结论（DeepSeek）"
        with st.expander(label, expanded=True):
            st.markdown(ai_summary)

    st.markdown('<p class="section-title">异常检测总览</p>', unsafe_allow_html=True)
    st.image(chart_paths["anomaly_overview"], use_container_width=True)

    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.markdown('<p class="section-title">等级分布</p>', unsafe_allow_html=True)
        for level, css in [
            ("严重", "risk-severe"),
            ("中等", "risk-medium"),
            ("轻微", "risk-medium"),
            ("正常", "risk-normal"),
        ]:
            count = sev.get(level, 0)
            st.markdown(
                f'<div class="{css}"><strong>{level}</strong>：{count} 票 '
                f'（{count / stats["total_orders"] * 100:.1f}%）</div>',
                unsafe_allow_html=True,
            )
    with col_right:
        st.markdown('<p class="section-title">延误分布分析</p>', unsafe_allow_html=True)
        st.image(chart_paths["delay_distribution"], use_container_width=True)


# ════════ Tab 2：承运商分析 ══════════════════════════════════════
with tab2:
    st.image(chart_paths["carrier_performance"], use_container_width=True)

    st.markdown('<p class="section-title">承运商绩效详情</p>', unsafe_allow_html=True)
    cs_display = stats["carrier_stats"].copy()
    cs_display["延误率"] = (cs_display["延误率"] * 100).round(1).astype(str) + "%"
    cs_display["异常率"] = (cs_display["异常率"] * 100).round(1).astype(str) + "%"
    cs_display["平均延误天数"] = cs_display["平均延误天数"].round(2)
    st.dataframe(
        cs_display[["承运商", "总订单数", "平均延误天数", "延误率", "异常订单数", "异常率"]],
        use_container_width=True,
        hide_index=True,
    )

    if ai_mode != "关闭 AI 分析":
        st.markdown('<p class="section-title">🤖 单承运商 AI 洞察</p>', unsafe_allow_html=True)
        selected_carrier = st.selectbox(
            "选择承运商",
            options=stats["carrier_stats"]["承运商"].tolist(),
        )
        if st.button("生成 AI 洞察", key="carrier_ai"):
            row = stats["carrier_stats"][
                stats["carrier_stats"]["承运商"] == selected_carrier
            ].iloc[0].to_dict()

            if use_ai_real:
                with st.spinner("真实 AI 分析中..."):
                    insight = try_generate_real_carrier_insight(selected_carrier, row, api_key.strip())
                if not insight:
                    insight = generate_demo_carrier_insight(selected_carrier, row)
            else:
                insight = generate_demo_carrier_insight(selected_carrier, row)

            st.info(insight)


# ════════ Tab 3：路线分析 ════════════════════════════════════════
with tab3:
    st.image(chart_paths["port_throughput"], use_container_width=True)

    st.markdown('<p class="section-title">高风险路线排名</p>', unsafe_allow_html=True)
    rs_display = stats["route_stats"].copy()
    rs_display["异常率"] = (rs_display["异常率"] * 100).round(1).astype(str) + "%"
    rs_display["平均延误"] = rs_display["平均延误"].round(1)
    st.dataframe(
        rs_display[["路线", "订单数", "平均延误", "最大延误", "异常数", "异常率"]],
        use_container_width=True,
        hide_index=True,
    )


# ════════ Tab 4：异常订单明细 ════════════════════════════════════
with tab4:
    anomaly_df = result[result["final_anomaly"] == 1][
        [
            "订单ID",
            "承运商",
            "路线",
            "运输方式",
            "计划发货日期",
            "实际到达日期",
            "实际延误天数",
            "severity",
            "anomaly_votes",
            "rule_reason",
        ]
    ].sort_values("实际延误天数", ascending=False)

    st.markdown(
        f'<p class="section-title">共 {len(anomaly_df)} 条异常订单</p>',
        unsafe_allow_html=True,
    )

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        sev_filter = st.multiselect(
            "严重等级筛选",
            ["严重", "中等", "轻微"],
            default=["严重", "中等"],
        )
    with col_f2:
        carrier_f2 = st.multiselect(
            "承运商筛选（明细）",
            options=anomaly_df["承运商"].unique().tolist(),
        )

    filtered = anomaly_df.copy()
    if sev_filter:
        filtered = filtered[filtered["severity"].isin(sev_filter)]
    if carrier_f2:
        filtered = filtered[filtered["承运商"].isin(carrier_f2)]

    st.dataframe(filtered, use_container_width=True, hide_index=True)

    csv_bytes = filtered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "📥 下载异常明细 CSV",
        data=csv_bytes,
        file_name="异常订单明细.csv",
        mime="text/csv",
    )


# ════════ Tab 5：下载报告 ════════════════════════════════════════
with tab5:
    st.markdown("### 📄 Word 报告下载")
    st.markdown(
        "报告包含：执行摘要 · 异常等级分布 · 港口吞吐量分析 · 延误模式分析 · "
        "承运商绩效评估 · Top10 异常订单 · 高风险路线 · 风险应对建议。"
    )
    if ai_summary:
        st.caption("说明：AI 智能分析结论已在页面总览区展示；Word 报告由本地报告模块生成。")

    with open(report_path, "rb") as f:
        report_bytes = f.read()

    st.download_button(
        label="⬇️ 下载 Word 报告（.docx）",
        data=report_bytes,
        file_name="运输计划异常检测报告.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary",
        use_container_width=True,
    )

    st.divider()
    st.markdown("### 📊 分析图表单独下载")
    chart_labels = {
        "anomaly_overview": "异常检测总览",
        "carrier_performance": "承运商绩效",
        "port_throughput": "港口吞吐量",
        "delay_distribution": "延误分布",
    }
    cols = st.columns(2)
    for i, (key, label) in enumerate(chart_labels.items()):
        with cols[i % 2]:
            with open(chart_paths[key], "rb") as f:
                st.download_button(
                    f"⬇️ {label}",
                    data=f.read(),
                    file_name=f"{label}.png",
                    mime="image/png",
                    use_container_width=True,
                )

