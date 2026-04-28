"""
[PATCH — XGBoost Signal Integration]
เพิ่ม xgb_signal section ใน _format_market_state()

วิธีใช้:
    1. คำนวณ xgb_signal string จาก SignalAggregator.aggregate_to_prompt()
    2. ใส่เข้า market_state ก่อนส่งเข้า run():

        market_state["xgb_signal"] = aggregator.aggregate_to_prompt(xgb_out, news_sig)

    3. PromptBuilder จะ render ให้อัตโนมัติตรง ## XGBoost Pre-Analysis block

ไม่ต้องแก้ react.py, roles.json, หรือ RoleDefinition ใดๆ
"""

# ════════════════════════════════════════════════════════════════
#  PATCH: เพิ่มบรรทัดนี้ใน _format_market_state() ของ PromptBuilder
#  วางหลัง ATR line (บรรทัดสุดท้ายของ lines = [...] block)
#  และก่อน # latest_news comment block
# ════════════════════════════════════════════════════════════════

PATCH_LOCATION = "_format_market_state() — หลัง ATR line, ก่อน news block"

PATCH_CODE = '''
        # ── XGBoost Pre-Analysis (inject จาก SignalAggregator) ──────────
        xgb_signal = state.get("xgb_signal")
        if xgb_signal:
            lines += [
                "",
                "── XGBoost Pre-Analysis ──",
                *[f"  {ln}" for ln in xgb_signal.splitlines()],
                "── End XGBoost ──",
            ]
'''

# ════════════════════════════════════════════════════════════════
#  Full patched _format_market_state() — copy/paste แทนของเดิม
#  (แสดงเฉพาะ Iteration 1 block ที่เพิ่ม XGBoost เข้าไป)
# ════════════════════════════════════════════════════════════════

FULL_PATCH_SNIPPET = '''
    def _format_market_state(self, state: dict, iteration: int = 1) -> str:
        """Format market state for LLM — dynamically slims down in later iterations"""
        md   = state.get("market_data", {})
        ti   = state.get("technical_indicators", {})
        news_data = state.get("news", {})

        spot    = md.get("spot_price_usd", {}).get("price_usd_per_oz", "N/A")
        usd_thb = md.get("forex", {}).get("usd_thb", "N/A")
        thai    = md.get("thai_gold_thb", {})
        spread_cov = md.get("spread_coverage", {})
        sell_thb = thai.get("sell_price_thb", "N/A")
        buy_thb  = thai.get("buy_price_thb", "N/A")

        rsi   = ti.get("rsi", {})
        macd  = ti.get("macd", {})
        trend = ti.get("trend", {})
        bb    = ti.get("bollinger", {})
        atr   = ti.get("atr", {})

        timestamp_str = state.get("timestamp") or md.get("spot_price_usd", {}).get("timestamp", "")
        interval      = state.get("interval", "15m")

        time_part = ""
        if timestamp_str and timestamp_str != "N/A":
            try:
                if "T" in timestamp_str:
                    time_part = timestamp_str.split("T")[1][:5]
                else:
                    time_part = timestamp_str.split(" ")[1][:5]
            except Exception:
                time_part = str(timestamp_str)

        dead_zone_warning = ""
        if time_part:
            try:
                minutes = self._parse_to_bkk_minutes(timestamp_str)
                if minutes is not None:
                    if 90 <= minutes <= 119:
                        dead_zone_warning = "\\n*** WARNING: Time 01:30–01:59 — Market closes at 02:00. SL3: SELL if holding gold! ***"
            except Exception:
                pass

        # ── 1. แกนหลัก (ส่งทุกรอบ) ─────────────────────────────────────
        lines = [
            f"Timestamp: {timestamp_str} (time: {time_part}) | Interval: {interval}{dead_zone_warning}",
            f"Gold (USD): ${spot}/oz | USD/THB: {usd_thb}",
            f"Gold (THB/gram): ฿{sell_thb} sell / ฿{buy_thb} buy  [ออม NOW]",
            f"Spread coverage: spread={spread_cov.get(\'spread_thb\', \'N/A\')} THB | effective_spread={spread_cov.get(\'effective_spread\', spread_cov.get(\'spread_thb\', \'N/A\'))} THB | expected_move={spread_cov.get(\'expected_move_thb\', \'N/A\')} THB | edge_score={spread_cov.get(\'edge_score\', \'N/A\')}",
            f"RSI({rsi.get(\'period\', 14)}): {rsi.get(\'value\', \'N/A\')} [{rsi.get(\'signal\', \'N/A\')}]",
            f"MACD: {macd.get(\'macd_line\', \'N/A\')}/{macd.get(\'signal_line\', \'N/A\')} hist:{macd.get(\'histogram\', \'N/A\')} [{macd.get(\'signal\', \'N/A\')}]",
            f"Trend: EMA20={trend.get(\'ema_20\', \'N/A\')} EMA50={trend.get(\'ema_50\', \'N/A\')} [{trend.get(\'trend\', \'N/A\')}]",
            f"BB: upper={bb.get(\'upper\', \'N/A\')} lower={bb.get(\'lower\', \'N/A\')}",
            f"Latest Close ({interval}): ${ti.get(\'latest_close\', \'N/A\')}/oz  ← use this vs EMA/BB",
            f"ATR: {atr.get(\'value\', \'N/A\')} {atr.get(\'unit\', \'\')} (≈{atr.get(\'value_usd\', \'?\')} USD/oz)",
        ]

        # ── [NEW] XGBoost Pre-Analysis (inject จาก SignalAggregator) ─────
        xgb_signal = state.get("xgb_signal")
        if xgb_signal:
            lines += [
                "",
                "── XGBoost Pre-Analysis ──",
                *[f"  {ln}" for ln in xgb_signal.splitlines()],
                "── End XGBoost ──",
            ]

        # ... (ส่วนที่เหลือของ method เหมือนเดิมทุกอย่าง — portfolio, news, quota, etc.)
'''

print("Patch reference file created — ดูใน PATCH_CODE และ FULL_PATCH_SNIPPET")
print("แก้ไขใน prompt.py จริงโดยเพิ่ม PATCH_CODE หลัง ATR line")
