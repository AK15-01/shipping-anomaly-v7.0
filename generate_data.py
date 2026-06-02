"""
模拟数据生成器
生成两类数据：
1. 港口月度吞吐量（模拟交通运输部数据格式）
2. 运输订单明细（模拟 Kaggle Supply Chain Shipment 数据）
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

np.random.seed(42)
random.seed(42)


# ── 1. 港口吞吐量数据 ────────────────────────────────────────────
def generate_port_throughput(base_dir):
    ports = ["上海港", "宁波舟山港", "深圳港", "广州港", "青岛港", "天津港", "厦门港", "大连港"]
    base = {
        "上海港": 4200, "宁波舟山港": 3100, "深圳港": 2600,
        "广州港": 2100, "青岛港": 1900, "天津港": 1700, "厦门港": 1200, "大连港": 900,
    }
    # 季节性系数（春节低谷 2月，旺季 9-11月）
    seasonal = [0.92, 0.78, 0.95, 0.98, 1.02, 1.05, 1.03, 1.04, 1.08, 1.10, 1.07, 1.01]

    records = []
    for port in ports:
        for year in [2022, 2023, 2024]:
            for month in range(1, 13):
                base_val = base[port]
                trend    = 1 + 0.04 * (year - 2022)
                noise    = np.random.normal(1.0, 0.03)
                shock    = 0.82 if (year == 2022 and month in [4, 5]) else 1.0
                value    = base_val * seasonal[month - 1] * trend * noise * shock
                records.append({
                    "港口":          port,
                    "年份":          year,
                    "月份":          month,
                    "货物吞吐量_万吨":  round(value, 1),
                    "集装箱吞吐量_万TEU": round(value * 0.18 + np.random.normal(0, 5), 1),
                })

    df   = pd.DataFrame(records)
    path = os.path.join(base_dir, "data", "port_throughput.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  ✓ 港口吞吐量数据：{len(df)} 条 → {path}")
    return df


# ── 2. 运输订单数据 ──────────────────────────────────────────────
def generate_shipment_orders(base_dir):
    carriers    = ["中远海运", "马士基", "中外运", "德邦物流", "顺丰快运"]
    cargo_types = ["电子元器件", "机械设备", "化工原料", "农产品", "消费品", "纺织品"]
    routes = [
        ("上海", "洛杉矶"), ("上海", "鹿特丹"), ("宁波", "新加坡"),
        ("深圳", "汉堡"),   ("青岛", "迪拜"),   ("广州", "巴塞罗那"),
        ("天津", "首尔"),   ("厦门", "横滨"),
    ]
    transport_modes = ["海运", "空运", "铁路"]
    mode_weights    = [0.65, 0.20, 0.15]

    carrier_perf = {
        "中远海运": {"delay_rate": 0.18, "avg_delay": 2.5},
        "马士基":   {"delay_rate": 0.14, "avg_delay": 1.8},
        "中外运":   {"delay_rate": 0.22, "avg_delay": 3.1},
        "德邦物流": {"delay_rate": 0.12, "avg_delay": 1.5},
        "顺丰快运": {"delay_rate": 0.08, "avg_delay": 0.9},
    }

    records    = []
    start_date = datetime(2023, 1, 1)

    for i in range(2000):
        carrier = random.choice(carriers)
        route   = random.choice(routes)
        mode    = random.choices(transport_modes, weights=mode_weights)[0]
        plan_days = {"海运": random.randint(18, 35),
                     "空运": random.randint(3, 7),
                     "铁路": random.randint(12, 20)}[mode]

        ship_date   = start_date + timedelta(days=random.randint(0, 730))
        plan_arrive = ship_date + timedelta(days=plan_days)

        perf        = carrier_perf[carrier]
        is_delayed  = random.random() < perf["delay_rate"]
        actual_delay = 0
        anomaly_flag = 0

        if is_delayed:
            actual_delay = max(0, int(np.random.exponential(perf["avg_delay"])) + 1)
            if random.random() < 0.05:          # 极端异常（港口拥堵/天气）
                actual_delay = random.randint(10, 25)
                anomaly_flag = 1

        actual_arrive = plan_arrive + timedelta(days=actual_delay)
        weight        = round(np.random.lognormal(3.5, 0.8), 1)

        records.append({
            "订单ID":       f"ORD-{2023 + i // 1000}-{i:05d}",
            "承运商":        carrier,
            "货物类型":      random.choice(cargo_types),
            "运输方式":      mode,
            "起运港":        route[0],
            "目的港":        route[1],
            "计划发货日期":   ship_date.strftime("%Y-%m-%d"),
            "计划到达日期":   plan_arrive.strftime("%Y-%m-%d"),
            "实际到达日期":   actual_arrive.strftime("%Y-%m-%d"),
            "计划运输天数":   plan_days,
            "实际延误天数":   actual_delay,
            "货重_吨":       weight,
            "运费_USD":     round(weight * random.uniform(80, 350) + random.uniform(200, 800), 2),
            "标注异常":      anomaly_flag,
        })

    df   = pd.DataFrame(records)
    path = os.path.join(base_dir, "data", "shipment_orders.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  ✓ 运输订单数据：{len(df)} 条 → {path}")
    return df
