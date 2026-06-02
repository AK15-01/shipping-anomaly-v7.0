"""
异常检测引擎
方法：多层检测，从简单规则到统计方法，输出结构化结果
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import warnings
warnings.filterwarnings("ignore")


class ShippingAnomalyDetector:
    def __init__(self, orders_path, throughput_path):
        self.orders     = pd.read_csv(orders_path,
                                      parse_dates=["计划发货日期", "计划到达日期", "实际到达日期"])
        self.throughput = pd.read_csv(throughput_path)
        self._preprocess()

    def _preprocess(self):
        df = self.orders
        df["延误偏差率"] = df["实际延误天数"] / df["计划运输天数"].clip(lower=1)
        df["发货月"]     = df["计划发货日期"].dt.month
        df["发货年"]     = df["计划发货日期"].dt.year
        df["路线"]       = df["起运港"] + "→" + df["目的港"]
        self.orders = df

    # ── 方法1：规则阈值 ──────────────────────────────────────────
    def rule_based_detection(self):
        df = self.orders.copy()
        df["rule_anomaly"] = 0
        df["rule_reason"]  = ""

        mask1 = df["延误偏差率"] > 0.5
        df.loc[mask1, "rule_anomaly"] = 1
        df.loc[mask1, "rule_reason"] += "延误超50%;"

        mask2 = df["实际延误天数"] > 7
        df.loc[mask2, "rule_anomaly"] = 1
        df.loc[mask2, "rule_reason"] += "延误>7天;"

        sea      = df["运输方式"] == "海运"
        low_cost = df["运费_USD"] < df[sea]["运费_USD"].quantile(0.02)
        df.loc[sea & low_cost, "rule_anomaly"] = 1
        df.loc[sea & low_cost, "rule_reason"] += "运费异常低;"

        return df[["订单ID", "rule_anomaly", "rule_reason"]]

    # ── 方法2：Z-Score（按路线分组）─────────────────────────────
    def zscore_detection(self, threshold=2.5):
        df      = self.orders.copy()
        results = []
        for route, group in df.groupby("路线"):
            delays = group["实际延误天数"]
            group  = group.copy()
            if len(group) < 5:
                group["zscore_anomaly"] = 0
                group["z_score"]        = 0.0
            else:
                mean = delays.mean()
                std  = max(delays.std(), 0.1)
                z    = (delays - mean) / std
                group["z_score"]        = z.round(2)
                group["zscore_anomaly"] = (z.abs() > threshold).astype(int)
            results.append(group[["订单ID", "zscore_anomaly", "z_score"]])
        return pd.concat(results)

    # ── 方法3：Isolation Forest ──────────────────────────────────
    def isolation_forest_detection(self):
        df       = self.orders.copy()
        features = df[["实际延误天数", "延误偏差率", "货重_吨",
                        "运费_USD", "计划运输天数"]].fillna(0)
        clf    = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
        preds  = clf.fit_predict(features)
        scores = clf.decision_function(features)
        return pd.DataFrame({
            "订单ID":         df["订单ID"],
            "iforest_anomaly": (preds == -1).astype(int),
            "anomaly_score":   (-scores).round(4),
        })

    # ── 综合评分 ─────────────────────────────────────────────────
    def run_all(self):
        r1 = self.rule_based_detection()
        r2 = self.zscore_detection()
        r3 = self.isolation_forest_detection()

        result = self.orders.copy()
        result = result.merge(r1, on="订单ID").merge(r2, on="订单ID").merge(r3, on="订单ID")
        result["anomaly_votes"] = (result["rule_anomaly"]
                                   + result["zscore_anomaly"]
                                   + result["iforest_anomaly"])
        result["final_anomaly"] = (result["anomaly_votes"] >= 2).astype(int)

        def grade(row):
            if row["实际延误天数"] > 14: return "严重"
            if row["实际延误天数"] > 7:  return "中等"
            if row["final_anomaly"] == 1: return "轻微"
            return "正常"

        result["severity"] = result.apply(grade, axis=1)
        return result

    # ── 统计汇总 ─────────────────────────────────────────────────
    def get_summary_stats(self, result):
        total    = len(result)
        anomalies = result[result["final_anomaly"] == 1]
        n_anomaly = len(anomalies)

        carrier_stats = result.groupby("承运商").agg(
            总订单数   = ("订单ID",        "count"),
            平均延误天数 = ("实际延误天数",  "mean"),
            延误率     = ("实际延误天数",  lambda x: (x > 0).mean()),
            异常订单数  = ("final_anomaly", "sum"),
        ).round(2).reset_index()
        carrier_stats["异常率"] = (carrier_stats["异常订单数"]
                                   / carrier_stats["总订单数"]).round(3)
        carrier_stats = carrier_stats.sort_values("异常率", ascending=False)

        route_stats = result.groupby("路线").agg(
            订单数  = ("订单ID",        "count"),
            平均延误 = ("实际延误天数",  "mean"),
            最大延误 = ("实际延误天数",  "max"),
            异常数  = ("final_anomaly", "sum"),
        ).round(2).reset_index()
        route_stats["异常率"] = (route_stats["异常数"] / route_stats["订单数"]).round(3)
        route_stats = route_stats.sort_values("平均延误", ascending=False)

        monthly = result.groupby(["发货年", "发货月"]).agg(
            订单数  = ("订单ID",        "count"),
            异常数  = ("final_anomaly", "sum"),
            平均延误 = ("实际延误天数",  "mean"),
        ).round(2).reset_index()
        monthly["异常率"] = (monthly["异常数"] / monthly["订单数"]).round(3)

        return {
            "total_orders":   total,
            "total_anomalies": n_anomaly,
            "anomaly_rate":   round(n_anomaly / total, 4),
            "avg_delay":      round(result["实际延误天数"].mean(), 2),
            "max_delay":      int(result["实际延误天数"].max()),
            "carrier_stats":  carrier_stats,
            "route_stats":    route_stats,
            "monthly_trend":  monthly,
            "severity_dist":  result["severity"].value_counts(),
            "top_anomalies":  anomalies.nlargest(10, "实际延误天数")[
                ["订单ID", "承运商", "路线", "运输方式",
                 "实际延误天数", "severity", "rule_reason"]
            ],
        }
