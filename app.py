"""
航运物流异常检测系统 - Streamlit Web 版
支持：上传 CSV / 使用演示数据 → 异常检测 → 可视化 → AI 分析 → 下载报告
"""
import os, sys, io, tempfile, time
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from generate_data    import generate_port_throughput, generate_shipment_orders
from detector         import ShippingAnomalyDetector
from charts           import (plot_anomaly_overview, plot_carrier_performance,
                               plot_port_throughput, plot_delay_distribution)
from report_generator import generate_report
from ai_analyst       import generate_ai_summary, generate_ai_carrier_insight

# ── 页面配置 ────────────────────────────────────────────────────
if "shipping_api_key" not in st.session_state:
    st.session_state.shipping_api_key = ""

st.set_page_config(
    page_title="航运异常检测系统",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 全局样式 ────────────────────────────────────────────────────
st.markdown("""
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
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  侧边栏
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/container-ship.png", width=60)
    st.title("🚢 航运异常检测")
    st.caption("Shipping Anomaly Detection System")
    st.divider()

    # DeepSeek API Key
    st.subheader("🤖 AI 分析（可选）")
    api_key_input = st.text_input(
        "DeepSeek API Key",
        type="password",
        value=st.session_state.shipping_api_key,
        placeholder="sk-xxxxxxxxxxxx",
        help="填入后点击下面的 应用 API Key。Key 只保存在本次会话。",
    )
    col_apply, col_clear = st.columns(2)
    with col_apply:
        if st.button("✅ 应用 API Key", use_container_width=True):
            st.session_state.shipping_api_key = api_key_input.strip()
            if st.session_state.shipping_api_key:
                st.success("已应用，AI 分析已开启")
            else:
                st.info("未填写 Key，将只使用本地异常检测")
    with col_clear:
        if st.button("🧹 清除", use_container_width=True):
            st.session_state.shipping_api_key = ""
            st.rerun()
    api_key = st.session_state.shipping_api_key
    use_ai = bool(api_key.strip())

    st.divider()

    # 数据来源
    st.subheader("📂 数据来源")
    data_source = st.radio(
        "选择数据来源",
        ["使用演示数据", "上传订单 CSV", "上传吞吐量 CSV（可选）"],
        index=0,
    )

    uploaded_orders     = None
    uploaded_throughput = None

    if data_source == "上传订单 CSV":
        uploaded_orders = st.file_uploader(
            "上传运输订单 CSV",
            type="csv",
            help="需包含字段：计划发货日期、计划到达日期、实际到达日期、承运商、运输方式、起运港、目的港",
        )
        st.caption("📥 [下载字段模板](# '字段：订单ID,承运商,货物类型,运输方式,起运港,目的港,"
                   "计划发货日期,计划到达日期,实际到达日期,计划运输天数,实际延误天数,货重_吨,运费_USD')")

    if data_source == "上传吞吐量 CSV（可选）":
        uploaded_throughput = st.file_uploader("上传港口吞吐量 CSV", type="csv")

    st.divider()

    # 检测参数
    st.subheader("⚙️ 检测参数")
    zscore_threshold = st.slider("Z-Score 阈值", 1.5, 4.0, 2.5, 0.1,
                                  help="数值越小越敏感，报警越多")
    iforest_contam   = st.slider("Isolation Forest 异常比例", 0.01, 0.15, 0.05, 0.01,
                                  help="预期数据中的异常比例")
    carrier_filter   = st.multiselect(
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
        "对运输订单进行异常识别，并自动生成专业分析报告。"
    )
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info("**📋 Step 1**\n\n选择数据来源（演示或上传）")
    with col2:
        st.info("**🔍 Step 2**\n\n调整检测参数（侧边栏）")
    with col3:
        st.info("**🤖 Step 3**\n\n填入 DeepSeek Key（可选）")
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
    os.makedirs(os.path.join(tmpdir, "data"),   exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "charts"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "output"), exist_ok=True)

    orders_path     = os.path.join(tmpdir, "data", "shipment_orders.csv")
    throughput_path = os.path.join(tmpdir, "data", "port_throughput.csv")
    chart_dir       = os.path.join(tmpdir, "charts")
    report_path     = os.path.join(tmpdir, "output", "运输计划异常检测报告.docx")

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
    # 注入用户参数
    detector.zscore_threshold = zscore_threshold
    result   = detector.run_all()
    stats    = detector.get_summary_stats(result)

with st.spinner("正在生成图表..."):
    chart_paths = {
        "anomaly_overview":    plot_anomaly_overview(stats, chart_dir),
        "carrier_performance": plot_carrier_performance(stats, chart_dir),
        "port_throughput":     plot_port_throughput(df_tp, chart_dir),
        "delay_distribution":  plot_delay_distribution(result, chart_dir),
    }

# AI 分析（异步，不阻塞其他渲染）
ai_summary = None
if use_ai:
    with st.spinner("🤖 DeepSeek 正在生成 AI 分析结论..."):
        ai_summary = generate_ai_summary(stats, api_key.strip())

with st.spinner("正在生成 Word 报告..."):
    generate_report(stats, result, chart_paths, report_path)

st.success("✅ 分析完成！")


# ══════════════════════════════════════════════════════════════
#  展示结果
# ══════════════════════════════════════════════════════════════

# ── Tab 导航 ────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 总览", "🏢 承运商分析", "🗺️ 路线分析", "📋 异常订单明细", "📥 下载报告"]
)


# ════════ Tab 1：总览 ════════════════════════════════════════════
with tab1:
    # KPI 卡片
    sev   = stats["severity_dist"]
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="metric-card">
            <p class="metric-value">{stats['total_orders']:,}</p>
            <p class="metric-label">📦 总分析订单</p></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card">
            <p class="metric-value">{stats['total_anomalies']:,}</p>
            <p class="metric-label">⚠️ 检测异常订单</p></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card">
            <p class="metric-value">{stats['anomaly_rate']*100:.1f}%</p>
            <p class="metric-label">📈 整体异常率</p></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="metric-card">
            <p class="metric-value">{stats['avg_delay']}天</p>
            <p class="metric-label">⏱️ 平均延误</p></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # AI 结论（如果有）
    if ai_summary:
        with st.expander("🤖 AI 智能分析结论（DeepSeek）", expanded=True):
            st.markdown(ai_summary)

    # 总览图
    st.markdown('<p class="section-title">异常检测总览</p>', unsafe_allow_html=True)
    st.image(chart_paths["anomaly_overview"], use_container_width=True)

    # 严重等级分布
    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.markdown('<p class="section-title">等级分布</p>', unsafe_allow_html=True)
        for level, css in [("严重","risk-severe"),("中等","risk-medium"),
                            ("轻微","risk-medium"),("正常","risk-normal")]:
            count = sev.get(level, 0)
            st.markdown(
                f'<div class="{css}"><strong>{level}</strong>：{count} 票 '
                f'（{count/stats["total_orders"]*100:.1f}%）</div>',
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
    cs_display["延误率"]  = (cs_display["延误率"]  * 100).round(1).astype(str) + "%"
    cs_display["异常率"]  = (cs_display["异常率"]  * 100).round(1).astype(str) + "%"
    cs_display["平均延误天数"] = cs_display["平均延误天数"].round(2)
    st.dataframe(
        cs_display[["承运商","总订单数","平均延误天数","延误率","异常订单数","异常率"]],
        use_container_width=True, hide_index=True,
    )

    # 单个承运商 AI 洞察
    if use_ai:
        st.markdown('<p class="section-title">🤖 单承运商 AI 洞察</p>',
                    unsafe_allow_html=True)
        selected_carrier = st.selectbox(
            "选择承运商",
            options=stats["carrier_stats"]["承运商"].tolist(),
        )
        if st.button("生成 AI 洞察", key="carrier_ai"):
            row = stats["carrier_stats"][
                stats["carrier_stats"]["承运商"] == selected_carrier
            ].iloc[0].to_dict()
            with st.spinner("分析中..."):
                insight = generate_ai_carrier_insight(selected_carrier, row, api_key.strip())
            st.info(insight)


# ════════ Tab 3：路线分析 ════════════════════════════════════════
with tab3:
    st.image(chart_paths["port_throughput"], use_container_width=True)

    st.markdown('<p class="section-title">高风险路线排名</p>', unsafe_allow_html=True)
    rs_display = stats["route_stats"].copy()
    rs_display["异常率"] = (rs_display["异常率"] * 100).round(1).astype(str) + "%"
    rs_display["平均延误"] = rs_display["平均延误"].round(1)
    st.dataframe(
        rs_display[["路线","订单数","平均延误","最大延误","异常数","异常率"]],
        use_container_width=True, hide_index=True,
    )


# ════════ Tab 4：异常订单明细 ════════════════════════════════════
with tab4:
    anomaly_df = result[result["final_anomaly"] == 1][[
        "订单ID","承运商","路线","运输方式",
        "计划发货日期","实际到达日期","实际延误天数",
        "severity","anomaly_votes","rule_reason",
    ]].sort_values("实际延误天数", ascending=False)

    st.markdown(f'<p class="section-title">共 {len(anomaly_df)} 条异常订单</p>',
                unsafe_allow_html=True)

    # 快速筛选
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        sev_filter = st.multiselect("严重等级筛选", ["严重","中等","轻微"], default=["严重","中等"])
    with col_f2:
        carrier_f2 = st.multiselect("承运商筛选（明细）",
                                     options=anomaly_df["承运商"].unique().tolist())

    filtered = anomaly_df.copy()
    if sev_filter:
        filtered = filtered[filtered["severity"].isin(sev_filter)]
    if carrier_f2:
        filtered = filtered[filtered["承运商"].isin(carrier_f2)]

    st.dataframe(filtered, use_container_width=True, hide_index=True)

    # 导出异常明细 CSV
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
        "承运商绩效评估 · Top10 异常订单 · 高风险路线 · 风险应对建议"
        + ("  \n🤖 **本次报告已包含 AI 智能分析结论**" if ai_summary else "")
    )

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
        "anomaly_overview":    "异常检测总览",
        "carrier_performance": "承运商绩效",
        "port_throughput":     "港口吞吐量",
        "delay_distribution":  "延误分布",
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
