"""
DeepSeek AI 分析模块
只在报告的"智能分析结论"部分调用，其余检测逻辑全部本地运行
"""
import json
import urllib.request
import urllib.error


def _call_deepseek(api_key: str, prompt: str, stream: bool = False) -> str:
    """
    直接用标准库调用 DeepSeek API，不依赖 openai 包
    """
    url     = "https://api.deepseek.com/chat/completions"
    payload = json.dumps({
        "model":    "deepseek-v4-flash",
        "messages": [
            {"role": "system",
             "content": (
                 "你是一位资深航运物流数据分析师，熟悉港口运营、供应链管理和承运商绩效评估。"
                 "请用专业、简洁的中文输出分析结论，避免废话，直接给出业务价值判断。"
             )},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens":  800,
        "stream":      False,
        "thinking":    {"type": "disabled"},
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"].get("content")
            return (content or "[API 有返回，但回答内容为空，请稍后重试]").strip()
    except urllib.error.HTTPError as e:
        return f"[API 调用失败: HTTP {e.code} — 请检查 API Key 是否正确]"
    except Exception as e:
        return f"[API 调用失败: {e}]"


def generate_ai_summary(stats: dict, api_key: str) -> str:
    """
    把检测结果摘要喂给 DeepSeek，生成针对性的业务分析结论
    返回 markdown 格式字符串，直接展示在 Streamlit 或写入报告
    """
    cs  = stats["carrier_stats"]
    rs  = stats["route_stats"].head(5)
    sev = stats["severity_dist"]

    # 构造数据摘要（控制 token 用量）
    carrier_summary = "\n".join(
        f"  - {row['承运商']}：异常率 {row['异常率']*100:.1f}%，"
        f"平均延误 {row['平均延误天数']:.1f} 天，共 {row['总订单数']} 票"
        for _, row in cs.iterrows()
    )
    route_summary = "\n".join(
        f"  - {row['路线']}：平均延误 {row['平均延误']:.1f} 天，"
        f"最大延误 {row['最大延误']} 天，异常率 {row['异常率']*100:.1f}%"
        for _, row in rs.iterrows()
    )

    prompt = f"""
以下是一批运输订单的异常检测结果，请给出专业的业务分析结论（300字以内）：

【总体情况】
- 分析订单总数：{stats['total_orders']:,} 票
- 检测异常订单：{stats['total_anomalies']:,} 票，整体异常率 {stats['anomaly_rate']*100:.1f}%
- 平均延误：{stats['avg_delay']} 天，最长延误：{stats['max_delay']} 天
- 严重异常（>14天）：{sev.get('严重', 0)} 票，中等异常（7-14天）：{sev.get('中等', 0)} 票

【承运商表现】
{carrier_summary}

【高风险路线 Top5】
{route_summary}

请从以下角度给出结论：
1. 当前运输体系最突出的风险点是什么
2. 哪个承运商/路线需要立即关注
3. 给采购或物流管理部门的1-2条具体行动建议
"""
    return _call_deepseek(api_key, prompt)


def generate_ai_carrier_insight(carrier_name: str, carrier_data: dict, api_key: str) -> str:
    """针对单个承运商生成分析洞察（用于详情页）"""
    prompt = f"""
承运商「{carrier_name}」的绩效数据如下：
- 总订单量：{carrier_data['总订单数']} 票
- 平均延误天数：{carrier_data['平均延误天数']:.1f} 天
- 延误率：{carrier_data['延误率']*100:.1f}%
- 异常订单数：{carrier_data['异常订单数']} 票，异常率：{carrier_data['异常率']*100:.1f}%

请用2-3句话给出这家承运商的绩效评价和建议，语气专业简练。
"""
    return _call_deepseek(api_key, prompt)
