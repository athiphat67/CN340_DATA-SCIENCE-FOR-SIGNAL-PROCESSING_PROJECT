"""
data_engine/csv_orchestrator.py
══════════════════════════════════════════════════════════════════════
CSVOrchestrator — Drop-in replacement สำหรับ GoldTradingOrchestrator
อ่านข้อมูลจาก CSV แทน live API/scrape

Interface เดียวกับ GoldTradingOrchestrator:
  orchestrator.run(history_days=90, save_to_file=False) → dict

โครงสร้าง payload เหมือนกันทุก key → ใช้กับ AnalysisService ได้เลย
ไม่ต้องแก้ services.py หรือ ReactOrchestrator แม้แต่บรรทัดเดียว

ไฟล์ที่รองรับ:
  gold_csv     (บังคับ) : Datetime, Open, High, Low, Close, Volume  ← HSH OHLCV
  external_csv (optional): timestamp, gold_spot_usd, usd_thb_rate   ← Spot + Forex
  news_csv     (optional): timestamp, overall_sentiment, news_count, top_headlines_summary

Usage:
  from data_engine.csv_orchestrator import CSVOrchestrator

  orchestrator = CSVOrchestrator(
      gold_csv="backtest/data/Final_Merged_Backtest_Data_M5.csv",
      external_csv="backtest/data/spot_forex.csv",   # optional
      news_csv="backtest/data/news.csv",             # optional
      interval="5m",
  )
  payload = orchestrator.run(history_days=90, save_to_file=False)
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class CSVOrchestrator:
    """
    Drop-in replacement สำหรับ GoldTradingOrchestrator
    อ่านข้อมูลจาก CSV ไม่ต้อง fetch live
    """

    def __init__(
        self,
        gold_csv: str,
        external_csv: str = "",   # gold_spot_usd, usd_thb_rate
        news_csv: str     = "",   # overall_sentiment, news_count, top_headlines_summary
        interval: str     = "5m",
        output_dir: str   = "./output",
    ):
        self.gold_csv     = gold_csv
        self.external_csv = external_csv
        self.news_csv     = news_csv
        self.interval     = interval
        self.output_dir   = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # โหลด CSV ครั้งเดียวตอน init (ไม่โหลดซ้ำทุก run)
        self._gold_df:  Optional[pd.DataFrame] = None
        self._ext_df:   Optional[pd.DataFrame] = None
        self._news_df:  Optional[pd.DataFrame] = None
        self._load_all()

    # ── Data loading ─────────────────────────────────────────────

    def _load_all(self):
        """โหลดทุก CSV ครั้งเดียว"""
        # 1. Gold OHLCV (บังคับ)
        try:
            from backtest.data.csv_loader import load_gold_csv
            df = load_gold_csv(self.gold_csv)
            self._gold_df = df
            logger.info(f"✓ CSVOrchestrator: loaded {len(df):,} candles from {self.gold_csv}")
        except Exception as e:
            raise RuntimeError(f"CSVOrchestrator: ไม่สามารถโหลด gold_csv: {e}") from e

        # 2. External (spot/forex) — optional
        if self.external_csv and Path(self.external_csv).exists():
            try:
                ext = pd.read_csv(self.external_csv, encoding="utf-8-sig")
                ext.columns = ext.columns.str.strip().str.lower()
                ts_col = next((c for c in ["timestamp","datetime","time","date"] if c in ext.columns), None)
                if ts_col:
                    ext["timestamp"] = pd.to_datetime(ext[ts_col], errors="coerce")
                    ext = ext.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
                    # normalize column names
                    _alias = {
                        "gold_spot_usd": ["gold_spot_usd","xau_usd","xauusd","spot_usd","spot","price_usd"],
                        "usd_thb_rate":  ["usd_thb_rate","usdthb","usd_thb","thb","thbrate"],
                    }
                    for std, aliases in _alias.items():
                        for a in aliases:
                            if a in ext.columns and std not in ext.columns:
                                ext = ext.rename(columns={a: std})
                                break
                    self._ext_df = ext
                    logger.info(f"✓ CSVOrchestrator: loaded external data {list(ext.columns)}")
            except Exception as e:
                logger.warning(f"⚠ external_csv load failed: {e}")

        # 3. News — optional
        if self.news_csv and Path(self.news_csv).exists():
            try:
                news = pd.read_csv(self.news_csv, encoding="utf-8-sig")
                news.columns = news.columns.str.strip().str.lower()
                ts_col = next((c for c in ["timestamp","datetime","time","date"] if c in news.columns), None)
                if ts_col:
                    news["timestamp"] = pd.to_datetime(news[ts_col], errors="coerce")
                    news = news.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
                    self._news_df = news
                    logger.info(f"✓ CSVOrchestrator: loaded {len(news):,} news rows")
            except Exception as e:
                logger.warning(f"⚠ news_csv load failed: {e}")

    # ── Main interface (เหมือน GoldTradingOrchestrator.run()) ────

    def run(self, history_days: int = 90, save_to_file: bool = False) -> dict:
        """
        คืน payload dict structure เดียวกับ GoldTradingOrchestrator.run()
        ทุก key ตรงกัน → ใช้กับ AnalysisService ได้โดยตรง
        """
        from data_engine.thailand_timestamp import get_thai_time

        df = self._gold_df.copy()

        # filter ตาม history_days
        cutoff = df["timestamp"].max() - pd.Timedelta(days=history_days)
        df = df[df["timestamp"] >= cutoff].reset_index(drop=True)

        if df.empty:
            raise ValueError(f"CSVOrchestrator: ไม่มีข้อมูลใน {history_days} วันล่าสุด")

        latest     = df.iloc[-1]
        latest_ts  = pd.Timestamp(latest["timestamp"])
        close_thai = float(latest.get("close_thai", latest.get("close", 0)))

        # ── ดึง spot USD / forex จาก external_csv ─────────────────
        gold_spot_usd = 0.0
        usd_thb_rate  = 0.0
        ext_source    = "csv_external"

        if self._ext_df is not None:
            ext = self._ext_df
            idx = ext["timestamp"].searchsorted(latest_ts, side="right") - 1
            if idx >= 0:
                row = ext.iloc[idx]
                # tolerance 4h
                if abs((latest_ts - row["timestamp"]).total_seconds()) <= 14400:
                    gold_spot_usd = float(row.get("gold_spot_usd", 0.0) or 0.0)
                    usd_thb_rate  = float(row.get("usd_thb_rate", 0.0) or 0.0)
        else:
            ext_source = "not_available"

        # ── ดึง news ──────────────────────────────────────────────
        news_dict = self._get_news(latest_ts)

        # ── Technical Indicators (ใช้ TechnicalIndicators เดียวกับ main) ──
        indicators_dict = {}
        data_quality = {
            "quality_score": "good",
            "is_weekend":    latest_ts.weekday() >= 5,
            "llm_instruction": "Use standard technical analysis. Data from CSV.",
            "warnings": [],
            "data_source": "csv_historical",
        }

        try:
            from data_engine.indicators import TechnicalIndicators

            # สร้าง ohlcv_df ที่ TechnicalIndicators ต้องการ (open/high/low/close/volume)
            ohlcv_for_ind = df.rename(columns={
                "open_thai": "open", "high_thai": "high",
                "low_thai": "low",   "close_thai": "close",
            })[["open","high","low","close","volume"]].copy()

            calc = TechnicalIndicators(ohlcv_for_ind)
            indicators_dict = calc.to_dict(interval=self.interval)

            # ดึง data_quality ออกจาก indicators
            if "data_quality" in indicators_dict:
                dq = indicators_dict.pop("data_quality")
                data_quality["warnings"].extend(dq.get("warnings", []))
                if dq.get("quality_score") == "degraded":
                    data_quality["quality_score"] = "degraded"

        except ImportError:
            # fallback: ใช้ indicators ที่คำนวณไว้แล้วใน csv_loader
            logger.warning("TechnicalIndicators ไม่พบ → ใช้ pre-computed indicators จาก csv_loader")
            indicators_dict = self._build_indicators_from_row(latest)
            data_quality["warnings"].append("Using pre-computed indicators from csv_loader (not TechnicalIndicators)")

        except Exception as e:
            logger.error(f"Indicator calculation failed: {e}")
            data_quality["quality_score"] = "degraded"
            data_quality["warnings"].append(f"Indicator calc error: {e}")

        # ── Recent price action (5 candles) ───────────────────────
        recent_5 = df.tail(5)
        recent_price_action = []
        for _, row in recent_5.iterrows():
            recent_price_action.append({
                "datetime": str(row["timestamp"]),
                "open":     float(row.get("open_thai", row.get("open", 0))),
                "high":     float(row.get("high_thai", row.get("high", 0))),
                "low":      float(row.get("low_thai",  row.get("low", 0))),
                "close":    float(row.get("close_thai", row.get("close", 0))),
                "volume":   int(row.get("volume", 0)),
            })

        # ── Thai gold price ────────────────────────────────────────
        # HSH CSV: Close = mid price ≈ ราคาสมาคม
        # bid (sell to us) ≈ close - 100, ask (buy from us) ≈ close + 100
        # SPREAD ≈ 200 THB/gram สำหรับ 99.99% gold
        thai_gold_thb = {
            "sell_price_thb": round(close_thai - 100, 2),   # ราคาที่ HSH รับซื้อ
            "buy_price_thb":  round(close_thai + 100, 2),   # ราคาที่ HSH ขาย
            "mid_price_thb":  round(close_thai, 2),
            "source":         "csv_hsh",
            "timestamp":      str(latest_ts),
        }

        # ── Assemble payload (structure เหมือน GoldTradingOrchestrator) ──
        now = get_thai_time()
        payload = {
            "meta": {
                "agent":        "gold-trading-agent",
                "version":      "csv-mode",
                "generated_at": now.isoformat(),
                "history_days": history_days,
                "interval":     self.interval,
                "data_mode":    "csv",
            },
            "data_quality": data_quality,
            "data_sources": {
                "price":     "csv_hsh",
                "forex":     ext_source,
                "thai_gold": "csv_hsh",
                "news":      "csv_news" if self._news_df is not None else "null",
            },
            "market_data": {
                "spot_price_usd": {
                    "price_usd_per_oz": gold_spot_usd,
                    "source":           ext_source,
                },
                "forex": {
                    "usd_thb":  usd_thb_rate,
                    "source":   ext_source,
                },
                "thai_gold_thb":       thai_gold_thb,
                "recent_price_action": recent_price_action,
            },
            "technical_indicators": indicators_dict,
            "news": {
                "summary": {
                    "total_articles":    news_dict.get("news_count", 0),
                    "token_estimate":    0,
                    "overall_sentiment": news_dict.get("overall_sentiment", 0.0),
                    "fetched_at":        str(latest_ts),
                    "errors":            [],
                },
                "by_category": {
                    "csv_news": {
                        "articles": [{
                            "headline":        news_dict.get("top_headlines_summary", ""),
                            "sentiment_score": news_dict.get("overall_sentiment", 0.0),
                        }] if news_dict.get("top_headlines_summary") else []
                    }
                },
            },
        }

        # ── Save to file (เพื่อ compatibility กับ services.py save_to_file=True) ──
        if save_to_file:
            try:
                ts_str = now.strftime("%Y%m%d_%H%M%S")
                for fp in [
                    self.output_dir / f"payload_{ts_str}.json",
                    self.output_dir / "latest.json",
                ]:
                    with open(fp, "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
                logger.info(f"✓ CSVOrchestrator: saved payload → {self.output_dir}/latest.json")
            except Exception as e:
                logger.warning(f"⚠ save_to_file failed: {e}")

        logger.info(
            f"✓ CSVOrchestrator.run() complete | "
            f"ts={latest_ts} | price={close_thai:,.0f} THB | "
            f"spot_usd={gold_spot_usd:.2f} | usdthb={usd_thb_rate:.2f}"
        )
        return payload

    # ── Helpers ──────────────────────────────────────────────────

    def _get_news(self, ts: pd.Timestamp) -> dict:
        """ดึง news ที่ใกล้ที่สุดก่อน ts (backward)"""
        _neutral = {"overall_sentiment": 0.0, "news_count": 0, "top_headlines_summary": ""}

        if self._news_df is None:
            return _neutral

        ts_utc = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        news = self._news_df.copy()
        news["_ts_utc"] = news["timestamp"].apply(
            lambda x: x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")
        )
        before = news[news["_ts_utc"] <= ts_utc]
        if before.empty:
            return _neutral

        row = before.iloc[-1]
        # tolerance 4h
        if abs((ts_utc - row["_ts_utc"]).total_seconds()) > 14400:
            return _neutral

        return {
            "overall_sentiment":     round(float(row.get("overall_sentiment", 0.0)), 4),
            "news_count":            int(row.get("news_count", 0)),
            "top_headlines_summary": str(row.get("top_headlines_summary", ""))[:300],
        }

    def _build_indicators_from_row(self, row: pd.Series) -> dict:
        """
        Fallback: สร้าง indicators dict จาก pre-computed columns ใน csv_loader
        ใช้เมื่อ TechnicalIndicators import ไม่ได้
        Structure ตรงกับ TechnicalIndicators.to_dict()
        """
        rsi   = float(row.get("rsi", 50))
        ema20 = float(row.get("ema_20", 0))
        ema50 = float(row.get("ema_50", 0))
        trend = "uptrend" if ema20 > ema50 else "downtrend" if ema20 < ema50 else "sideways"
        hist  = float(row.get("macd_hist", 0))

        return {
            "rsi": {
                "value":  round(rsi, 2),
                "signal": "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral",
                "period": 14,
            },
            "macd": {
                "macd_line":   round(float(row.get("macd_line", 0)), 4),
                "signal_line": round(float(row.get("signal_line", 0)), 4),
                "histogram":   round(hist, 4),
                "crossover":   "none",
            },
            "bollinger": {
                "upper":     round(float(row.get("bb_upper", 0)), 2),
                "middle":    round(float(row.get("bb_mid", 0)), 2),
                "lower":     round(float(row.get("bb_lower", 0)), 2),
                "bandwidth": 0.0,
                "pct_b":     0.5,
                "signal":    "inside",
            },
            "atr": {
                "value":           round(float(row.get("atr", 0)), 2),
                "period":          14,
                "volatility_level":"normal",
            },
            "trend": {
                "ema_20":       round(ema20, 2),
                "ema_50":       round(ema50, 2),
                "sma_200":      round(ema50, 2),   # ไม่มีใน csv_loader → ใช้ ema50 แทน
                "trend":        trend,
                "golden_cross": ema20 > ema50,
                "death_cross":  ema20 < ema50,
            },
            "latest_close":  round(float(row.get("close_thai", row.get("close", 0))), 2),
            "calculated_at": str(row.get("timestamp", "")),
        }
