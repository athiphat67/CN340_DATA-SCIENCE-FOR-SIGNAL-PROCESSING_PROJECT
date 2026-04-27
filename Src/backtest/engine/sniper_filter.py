"""
engine/sniper_filter.py  — Sniper Pre-filter v1.0
══════════════════════════════════════════════════════════════════════
หน้าที่: คัดกรองแท่งเทียนก่อนส่งให้ LLM

หลักการ Hybrid Pipeline:
  ❌ เดิม: ทุกแท่งเทียน → LLM (แพง / ช้า / AI งง)
  ✅ ใหม่: ทุกแท่งเทียน → SniperFilter → เฉพาะที่ผ่านกรอง → LLM

กฎการกรอง (ต้องผ่าน **ทุกข้อ** จึงจะ call LLM):
  [1] Session Quota  — ยังไม่ BUY ในเซสชั่นนี้ (max 1 BUY entry/session)
  [2] Dip Setup      — มีสัญญาณย่อตัว (RSI / BB / Price Pullback)
  [3] Trend Filter   — HTF trend ไม่ขัดแย้งชัดเจน (EMA20 vs EMA50)
  [4] Spread Cover   — ATR คาดว่าจะชนะ Spread ได้ (edge > 0)
  [5] SELL Pass      — ถ้าถือทองอยู่ ให้ผ่านกรองเสมอ (SELL/EXIT ห้ามบล็อก)

Return: SniperResult (dataclass) บอกว่า should_call_llm=True/False + reason

ใช้งาน (ใน run_main_backtest.py):
  from engine.sniper_filter import SniperFilter, SniperResult

  sniper = SniperFilter()
  result = sniper.check(row, portfolio, session_trades_this_session)
  if not result.should_call_llm:
      return _build_hold_result(ts, price, result.reason)
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Config — ปรับได้ตามผล Backtest
# ══════════════════════════════════════════════════════════════════

@dataclass
class SniperConfig:
    # ── [1] Session Quota ──────────────────────────────────────────
    # จำนวน BUY entry สูงสุดต่อ session (AB / AFTN / EVEN)
    max_buy_per_session: int = 1

    # ── [2] Dip Setup ──────────────────────────────────────────────
    # RSI ต่ำกว่า threshold ถือว่า "oversold / dip zone"
    rsi_dip_threshold: float = 45.0

    # ราคาต้องอยู่ภายใน bb_band_pct% จาก BB Lower เพื่อนับว่า "near support"
    # เช่น 0.003 = ราคาต้องอยู่ภายใน 0.3% จาก BB Lower
    bb_band_pct: float = 0.005

    # price pullback: ราคาต้องลงจาก recent high อย่างน้อย pullback_pct%
    # เช่น 0.002 = ย่อลงมาอย่างน้อย 0.2% จากสูงสุด 5 แท่ง
    pullback_pct: float = 0.002

    # จำนวน condition dip ขั้นต่ำที่ต้องผ่าน (จาก 3 ตัวข้างบน)
    # ค่า 1 = ผ่านแค่ตัวเดียวก็พอ (หลวม), ค่า 2 = เข้มขึ้น
    min_dip_conditions: int = 1

    # ── [3] Trend Filter ───────────────────────────────────────────
    # True = กรอง downtrend ออก (EMA20 < EMA50 → ห้าม BUY)
    enable_trend_filter: bool = True

    # True = อนุญาตให้ BUY ได้แม้ trend neutral (EMA20 ≈ EMA50)
    allow_neutral_trend: bool = True

    # ema_neutral_pct: % gap ระหว่าง EMA20/EMA50 ที่นับว่า "neutral"
    ema_neutral_pct: float = 0.003

    # ── [4] Spread Cover ───────────────────────────────────────────
    # ATR ต้องมากกว่า spread_cover_multiplier เท่าของ spread
    # เช่น 1.0 = ATR > spread (ขั้นต่ำ), 1.5 = ATR > 1.5x spread (เข้มขึ้น)
    spread_cover_multiplier: float = 1.0

    # spread ของทองไทย (THB) — ใช้ fallback ถ้าไม่มีค่าใน row
    default_spread_thb: float = 200.0

    # ── [5] SELL Always Pass ───────────────────────────────────────
    # True = ถ้าถือทองอยู่ (gold_grams > 0) ให้ call LLM เสมอ
    sell_always_pass: bool = True

    # ── Debug ──────────────────────────────────────────────────────
    verbose: bool = False


# ══════════════════════════════════════════════════════════════════
# Result
# ══════════════════════════════════════════════════════════════════

@dataclass
class SniperResult:
    should_call_llm: bool
    reason: str               # สาเหตุที่ผ่าน หรือ บล็อก
    dip_score: int = 0        # จำนวน dip conditions ที่ผ่าน (0-3)
    checks: Dict[str, bool] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return "🎯 PASS" if self.should_call_llm else "⏭ SKIP"


# ══════════════════════════════════════════════════════════════════
# SniperFilter
# ══════════════════════════════════════════════════════════════════

class SniperFilter:
    """
    Pre-filter ที่ตรวจสอบแท่งเทียนก่อนส่งให้ LLM
    สามารถ config ได้ผ่าน SniperConfig

    ตัวอย่าง:
        sniper = SniperFilter()                        # default config
        sniper = SniperFilter(SniperConfig(rsi_dip_threshold=40))  # custom
    """

    def __init__(self, config: Optional[SniperConfig] = None):
        self.cfg = config or SniperConfig()
        self._session_buy_count: Dict[str, int] = {}  # key = "YYYY-MM-DD|SESSION_ID"

    # ── Public API ───────────────────────────────────────────────

    def check(
        self,
        row: pd.Series,
        gold_grams: float,
        session_id: Optional[str],
        date_str: str,
    ) -> SniperResult:
        """
        ตรวจสอบแท่งเทียนว่าควร call LLM หรือไม่

        Parameters
        ----------
        row         : pd.Series — แท่งเทียนปัจจุบัน (ต้องมี rsi, bb_*, ema_*, atr)
        gold_grams  : float     — ทองที่ถืออยู่ตอนนี้ (จาก portfolio.gold_grams)
        session_id  : str|None  — session ปัจจุบัน (AB / AFTN / EVEN / None)
        date_str    : str       — วันที่ "YYYY-MM-DD"

        Returns
        -------
        SniperResult
        """
        cfg = self.cfg

        # ── [5] SELL Always Pass — ถ้าถือทองอยู่ ให้ผ่านเสมอ ──────────
        if cfg.sell_always_pass and gold_grams > 1e-4:
            return SniperResult(
                should_call_llm=True,
                reason="SELL_PASS: holding gold → always evaluate exit",
                dip_score=0,
                checks={"sell_always_pass": True},
            )

        # ── [1] Session Quota ─────────────────────────────────────────
        quota_key = f"{date_str}|{session_id or 'UNKNOWN'}"
        buys_this_session = self._session_buy_count.get(quota_key, 0)
        quota_ok = buys_this_session < cfg.max_buy_per_session

        if not quota_ok:
            return SniperResult(
                should_call_llm=False,
                reason=f"QUOTA: session {session_id} already has {buys_this_session} BUY entry",
                checks={"quota": False},
            )

        # ── [2] Dip Setup Detection ───────────────────────────────────
        dip_flags, dip_details = self._check_dip(row)
        dip_score = sum(dip_flags.values())
        dip_ok = dip_score >= cfg.min_dip_conditions

        # ── [3] Trend Filter ──────────────────────────────────────────
        trend_ok, trend_detail = self._check_trend(row)

        # ── [4] Spread Cover ──────────────────────────────────────────
        spread_ok, spread_detail = self._check_spread(row)

        # ── Combine ───────────────────────────────────────────────────
        checks = {
            "quota":  quota_ok,
            "dip":    dip_ok,
            "trend":  trend_ok,
            "spread": spread_ok,
            **dip_flags,
        }

        all_pass = dip_ok and trend_ok and spread_ok

        if all_pass:
            reason = (
                f"PASS: dip_score={dip_score} | {dip_details} | "
                f"trend={trend_detail} | spread={spread_detail}"
            )
        else:
            fails = []
            if not dip_ok:
                fails.append(f"NO_DIP(score={dip_score}/{cfg.min_dip_conditions}: {dip_details})")
            if not trend_ok:
                fails.append(f"TREND_BLOCK({trend_detail})")
            if not spread_ok:
                fails.append(f"SPREAD_WEAK({spread_detail})")
            reason = "SKIP: " + " | ".join(fails)

        if cfg.verbose:
            icon = "🎯" if all_pass else "⏭"
            logger.debug(f"  {icon} SniperFilter {reason}")

        return SniperResult(
            should_call_llm=all_pass,
            reason=reason,
            dip_score=dip_score,
            checks=checks,
        )

    def record_buy(self, date_str: str, session_id: Optional[str]):
        """
        บันทึกว่า session นี้มี BUY เกิดขึ้นแล้ว 1 ครั้ง
        เรียกจาก _apply_to_portfolio() หลัง execute_buy สำเร็จ
        """
        quota_key = f"{date_str}|{session_id or 'UNKNOWN'}"
        self._session_buy_count[quota_key] = self._session_buy_count.get(quota_key, 0) + 1
        logger.debug(f"  📌 SniperFilter: recorded BUY for {quota_key} "
                     f"(total={self._session_buy_count[quota_key]})")

    def reset(self):
        """Reset session counters (ใช้ตอนเริ่ม backtest ใหม่)"""
        self._session_buy_count.clear()

    def stats(self) -> dict:
        """สรุปจำนวน BUY ที่บันทึกไว้แต่ละ session"""
        return dict(self._session_buy_count)

    # ── Internal checks ───────────────────────────────────────────

    def _check_dip(self, row: pd.Series):
        """
        ตรวจสอบ 3 dip conditions:
          [A] RSI oversold      → rsi < rsi_dip_threshold
          [B] Near BB Lower     → price within bb_band_pct% of BB Lower
          [C] Price Pullback    → price ลงจาก recent high ≥ pullback_pct%

        Returns
        -------
        flags   : dict[str, bool]
        details : str (human-readable summary)
        """
        cfg = self.cfg
        flags = {}

        # ── [A] RSI ──────────────────────────────────────────────
        rsi = float(row.get("rsi", 50.0))
        flags["dip_rsi"] = rsi < cfg.rsi_dip_threshold

        # ── [B] Near BB Lower ─────────────────────────────────────
        price = float(row.get("Mock_HSH_Sell_Close", row.get("close_thai", 0.0)))
        bb_lower = float(row.get("bb_lower", 0.0))
        if bb_lower > 0 and price > 0:
            gap_pct = (price - bb_lower) / price
            flags["dip_bb"] = gap_pct <= cfg.bb_band_pct
        else:
            flags["dip_bb"] = False

        # ── [C] Price Pullback ────────────────────────────────────
        # ใช้ ema_20 เป็น proxy ของ recent high (ถ้าไม่มี high_thai)
        # ถ้ามี high_thai ให้ใช้โดยตรง
        recent_high = float(row.get("Mock_HSH_Sell_High", row.get("high_thai", 0.0)))
        if recent_high <= 0:
            recent_high = float(row.get("ema_20", 0.0))

        if recent_high > 0 and price > 0:
            pullback = (recent_high - price) / recent_high
            flags["dip_pullback"] = pullback >= cfg.pullback_pct
        else:
            flags["dip_pullback"] = False

        details = (
            f"RSI={rsi:.1f}({'✓' if flags['dip_rsi'] else '✗'}) | "
            f"BB_gap={'✓' if flags['dip_bb'] else '✗'} | "
            f"Pullback={'✓' if flags['dip_pullback'] else '✗'}"
        )
        return flags, details

    def _check_trend(self, row: pd.Series):
        """
        Trend filter: EMA20 vs EMA50
          uptrend   → ✓ PASS
          neutral   → ✓ PASS (ถ้า allow_neutral_trend=True)
          downtrend → ✗ BLOCK (ถ้า enable_trend_filter=True)
        """
        cfg = self.cfg

        if not cfg.enable_trend_filter:
            return True, "TREND_OFF"

        ema20 = float(row.get("ema_20", 0.0))
        ema50 = float(row.get("ema_50", 0.0))

        if ema20 <= 0 or ema50 <= 0:
            # ไม่มีข้อมูล EMA → ผ่านไปก่อน (ไม่บล็อก)
            return True, "NO_EMA_DATA"

        gap_pct = (ema20 - ema50) / ema50

        if gap_pct > cfg.ema_neutral_pct:
            return True, f"UPTREND(EMA20={ema20:.0f}>EMA50={ema50:.0f})"
        elif abs(gap_pct) <= cfg.ema_neutral_pct:
            if cfg.allow_neutral_trend:
                return True, f"NEUTRAL(gap={gap_pct*100:.2f}%)"
            else:
                return False, f"NEUTRAL_BLOCKED(gap={gap_pct*100:.2f}%)"
        else:
            return False, f"DOWNTREND(EMA20={ema20:.0f}<EMA50={ema50:.0f})"

    def _check_spread(self, row: pd.Series):
        """
        Spread coverage: ATR ต้องมากกว่า spread * multiplier
        เพื่อให้มีโอกาสทำกำไรได้จริงหลังหักค่าสเปรด
        """
        cfg = self.cfg

        atr = float(row.get("atr", 0.0))
        if atr <= 0:
            # ไม่มี ATR → ผ่านไปก่อน
            return True, "NO_ATR"

        # ประมาณ spread จาก buy-sell price หรือใช้ default
        buy_price = float(row.get("Mock_HSH_Buy_Close", 0.0))
        sell_price = float(row.get("Mock_HSH_Sell_Close", 0.0))
        if buy_price > 0 and sell_price > 0 and sell_price > buy_price:
            spread = sell_price - buy_price
        else:
            spread = cfg.default_spread_thb

        min_atr_needed = spread * cfg.spread_cover_multiplier
        ok = atr >= min_atr_needed

        return ok, f"ATR={atr:.0f} vs spread*{cfg.spread_cover_multiplier:.1f}={min_atr_needed:.0f}"


# ══════════════════════════════════════════════════════════════════
# Self-test
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    print("=" * 60)
    print("SniperFilter v1.0 — Self Test")
    print("=" * 60)

    sf = SniperFilter(SniperConfig(verbose=True))

    # ── Test 1: Dip Setup (ควรผ่าน) ──────────────────────────────
    row_dip = pd.Series({
        "rsi": 38.0,
        "Mock_HSH_Sell_Close": 72000.0,
        "Mock_HSH_Buy_Close":  71800.0,
        "Mock_HSH_Sell_High":  72800.0,
        "bb_lower": 71900.0,
        "ema_20":   72100.0,
        "ema_50":   71900.0,
        "atr":      350.0,
    })
    r1 = sf.check(row_dip, gold_grams=0.0, session_id="AB", date_str="2026-04-01")
    print(f"\nTest 1 (Dip Setup):  {r1.label} | {r1.reason}")
    assert r1.should_call_llm, "Test 1 ควรผ่าน"

    # ── Test 2: No Dip (ควร SKIP) ────────────────────────────────
    row_flat = pd.Series({
        "rsi": 55.0,
        "Mock_HSH_Sell_Close": 73000.0,
        "Mock_HSH_Buy_Close":  72800.0,
        "Mock_HSH_Sell_High":  73100.0,
        "bb_lower": 71000.0,
        "ema_20":   72000.0,
        "ema_50":   73500.0,  # downtrend
        "atr":      200.0,
    })
    r2 = sf.check(row_flat, gold_grams=0.0, session_id="AB", date_str="2026-04-01")
    print(f"Test 2 (No Dip):     {r2.label} | {r2.reason}")
    assert not r2.should_call_llm, "Test 2 ควร SKIP"

    # ── Test 3: Holding Gold → Always Pass ───────────────────────
    r3 = sf.check(row_flat, gold_grams=0.08, session_id="AB", date_str="2026-04-01")
    print(f"Test 3 (Hold Gold):  {r3.label} | {r3.reason}")
    assert r3.should_call_llm, "Test 3 ถือทองอยู่ต้องผ่านเสมอ"

    # ── Test 4: Quota Exceeded ────────────────────────────────────
    sf.record_buy("2026-04-01", "AB")
    r4 = sf.check(row_dip, gold_grams=0.0, session_id="AB", date_str="2026-04-01")
    print(f"Test 4 (Quota Full): {r4.label} | {r4.reason}")
    assert not r4.should_call_llm, "Test 4 quota เต็มต้อง SKIP"

    # ── Test 5: New Session → Quota resets ───────────────────────
    r5 = sf.check(row_dip, gold_grams=0.0, session_id="AFTN", date_str="2026-04-01")
    print(f"Test 5 (New Session):{r5.label} | {r5.reason}")
    assert r5.should_call_llm, "Test 5 session ใหม่ quota ยังไม่หมด"

    print("\n✅ ทุก test ผ่าน!")
    print("=" * 60)
