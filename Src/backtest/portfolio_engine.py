"""
backtest/portfolio_engine.py
Portfolio-style Backtest Engine สำหรับแอป ออม Now (ฮั่วเซ่งเฮง)

รองรับ:
- Long-only trading (ซื้อ/ขายทองคำเท่านั้น ไม่มี Short)
- ทุนเริ่มต้น 1,500 THB (ปรับได้)
- Spread ค่าธรรมเนียมซื้อ-ขาย
- บังคับเคลียร์พอร์ตวันสุดท้าย (Force Liquidation — กฎข้อ 6)
- คำนวณการคืนเงิน VC (กฎข้อ 8)
- Walk-forward Validation
- คำนวณ PnL เป็นบาทไทย (THB)
"""

import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ─── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class PortfolioSignal:
    """สัญญาณเทรดรายวัน"""

    date: str  # YYYY-MM-DD
    signal: str  # BUY | SELL | HOLD
    confidence: float  # 0.0 – 1.0
    model_name: str = ""
    rationale: str = ""


@dataclass
class DailyState:
    """สถานะพอร์ตรายวัน"""

    date: str
    signal: str
    action_taken: str  # BUY | SELL | HOLD | FORCE_SELL | REJECTED
    cash_thb: float  # เงินสดคงเหลือ
    gold_grams: float  # น้ำหนักทองคงเหลือ (กรัม)
    gold_value_thb: float  # มูลค่าทองคำ (THB)
    portfolio_value: float  # มูลค่ารวม (cash + gold)
    price_per_gram: float  # ราคาทอง THB/กรัม วันนั้น
    pnl_thb: float  # กำไร/ขาดทุนสะสม
    note: str = ""


@dataclass
class PortfolioSummary:
    """สรุปผล backtest"""

    model_name: str
    window_year: int
    test_start: str
    test_end: str
    initial_capital: float
    final_value: float
    total_return_thb: float
    total_return_pct: float
    total_trades: int
    buy_count: int
    sell_count: int
    hold_count: int
    rejected_count: int
    max_drawdown_thb: float
    max_drawdown_pct: float
    sharpe_ratio: float
    spread_cost_total: float  # ค่า spread ทั้งหมดที่จ่าย
    vc_settlement: dict  # การคืนเงิน VC ตามกฎข้อ 8
    daily_states: list  # รายละเอียดรายวัน


# ─── Engine ──────────────────────────────────────────────────────────────────


class PortfolioBacktestEngine:
    """
    Portfolio Backtest Engine สำหรับแอป ออม Now

    Parameters
    ----------
    initial_capital : float
        ทุนเริ่มต้น (THB) default 1500
    spread_pct : float
        ค่า Spread เป็น % ของราคา (default 0.3% = 0.003)
        - ซื้อทอง: จ่ายราคา × (1 + spread_pct/2)  → Ask price
        - ขายทอง: ได้ราคา × (1 - spread_pct/2)  → Bid price
    min_trade_thb : float
        ยอดซื้อขั้นต่ำ (THB) default 100
    force_liquidation : bool
        บังคับขายทั้งหมดในวันสุดท้าย (กฎข้อ 6)
    """

    def __init__(
        self,
        initial_capital: float = 1500.0,
        spread_pct: float = 0.003,
        min_trade_thb: float = 1000.0,
        force_liquidation: bool = True,
    ):
        self.initial_capital = initial_capital
        self.spread_pct = spread_pct
        self.min_trade_thb = min_trade_thb
        self.force_liquidation = force_liquidation

    # ─── Price helpers ───────────────────────────────────────────────────

    def _get_ask_price(self, mid_price: float) -> float:
        """ราคาซื้อทอง (Ask) = mid + half spread"""
        return mid_price * (1 + self.spread_pct / 2)

    def _get_bid_price(self, mid_price: float) -> float:
        """ราคาขายทอง (Bid) = mid - half spread"""
        return mid_price * (1 - self.spread_pct / 2)

    # ─── Main Run ────────────────────────────────────────────────────────

    def run(
        self,
        price_data: pd.DataFrame,
        signals: list[PortfolioSignal],
        model_name: str = "unknown",
        window_year: int = 0,
    ) -> PortfolioSummary:
        """
        รัน portfolio backtest

        Parameters
        ----------
        price_data : pd.DataFrame
            ข้อมูลราคาช่วงทดสอบ (ต้องมี columns: date, price_per_gram)
        signals : list[PortfolioSignal]
            สัญญาณรายวัน (อย่างน้อย 1 ต่อวัน ตามกฎข้อ 4)
        model_name : str
        window_year : int
        """
        # ── Build signal lookup ──────────────────────────────────────────
        signal_map = {}
        for s in signals:
            sig_date = pd.to_datetime(s.date).strftime("%Y-%m-%d")
            signal_map[sig_date] = s

        # ── Portfolio state ──────────────────────────────────────────────
        cash = self.initial_capital
        gold_grams = 0.0
        daily_states: list[DailyState] = []
        spread_cost_total = 0.0
        buy_count = 0
        sell_count = 0
        hold_count = 0
        rejected_count = 0

        # ── Determine last trading day ───────────────────────────────────
        dates_list = price_data["date"].tolist()
        last_date = dates_list[-1] if len(dates_list) > 0 else None

        # ── Walk through each trading day ────────────────────────────────
        for _, row in price_data.iterrows():
            date_str = pd.to_datetime(row["date"]).strftime("%Y-%m-%d")
            price_per_gram = row["price_per_gram"]
            is_last_day = row["date"] == last_date

            # Get signal for this day (default HOLD if missing)
            sig = signal_map.get(date_str, None)
            signal_type = sig.signal.upper() if sig else "HOLD"

            # ── Force liquidation on last day (กฎข้อ 6) ──────────────
            if is_last_day and self.force_liquidation and gold_grams > 0:
                bid = self._get_bid_price(price_per_gram)
                proceeds = gold_grams * bid
                spread_cost = gold_grams * (price_per_gram - bid)
                spread_cost_total += spread_cost
                cash += proceeds
                sell_count += 1
                action = "FORCE_SELL"
                note = (
                    f"Force liquidation: sold {gold_grams:.4f}g "
                    f"@ {bid:.2f} THB/g → +{proceeds:.2f} THB"
                )
                gold_grams = 0.0

            # ── BUY: ใช้เงินสดทั้งหมดซื้อทอง ────────────────────────
            elif signal_type == "BUY":
                if cash >= self.min_trade_thb:
                    ask = self._get_ask_price(price_per_gram)
                    grams_bought = cash / ask
                    spread_cost = cash - (grams_bought * price_per_gram)
                    spread_cost_total += abs(spread_cost)
                    gold_grams += grams_bought
                    buy_count += 1
                    action = "BUY"
                    note = (
                        f"Bought {grams_bought:.4f}g "
                        f"@ {ask:.2f} THB/g (cash {cash:.2f})"
                    )
                    cash = 0.0
                else:
                    action = "REJECTED"
                    note = f"BUY rejected: cash {cash:.2f} < min {self.min_trade_thb}"
                    rejected_count += 1

            # ── SELL: ขายทองทั้งหมดเป็นเงินสด ────────────────────────
            elif signal_type == "SELL":
                if gold_grams > 0:
                    bid = self._get_bid_price(price_per_gram)
                    proceeds = gold_grams * bid
                    spread_cost = gold_grams * (price_per_gram - bid)
                    spread_cost_total += spread_cost
                    sell_count += 1
                    action = "SELL"
                    note = (
                        f"Sold {gold_grams:.4f}g "
                        f"@ {bid:.2f} THB/g → +{proceeds:.2f} THB"
                    )
                    cash += proceeds
                    gold_grams = 0.0
                else:
                    action = "REJECTED"
                    note = "SELL rejected: no gold in portfolio"
                    rejected_count += 1

            # ── HOLD: ไม่ทำอะไร ──────────────────────────────────────
            else:
                action = "HOLD"
                note = ""
                hold_count += 1

            # ── Record daily state ───────────────────────────────────
            gold_value = gold_grams * price_per_gram
            portfolio_value = cash + gold_value
            pnl = portfolio_value - self.initial_capital

            daily_states.append(
                DailyState(
                    date=date_str,
                    signal=signal_type,
                    action_taken=action,
                    cash_thb=round(cash, 2),
                    gold_grams=round(gold_grams, 6),
                    gold_value_thb=round(gold_value, 2),
                    portfolio_value=round(portfolio_value, 2),
                    price_per_gram=round(price_per_gram, 2),
                    pnl_thb=round(pnl, 2),
                    note=note,
                )
            )

        # ─── Calculate metrics ───────────────────────────────────────────
        final_value = (
            daily_states[-1].portfolio_value if daily_states else self.initial_capital
        )
        total_return_thb = final_value - self.initial_capital
        total_return_pct = (total_return_thb / self.initial_capital) * 100

        # Max drawdown
        pv = [s.portfolio_value for s in daily_states]
        max_dd_thb, max_dd_pct = self._calc_max_drawdown(pv, self.initial_capital)

        # Sharpe ratio
        daily_returns = []
        for i in range(1, len(pv)):
            if pv[i - 1] > 0:
                daily_returns.append((pv[i] - pv[i - 1]) / pv[i - 1])
        sharpe = self._calc_sharpe(daily_returns)

        # VC settlement (กฎข้อ 8)
        vc_settlement = self._calc_vc_settlement(final_value, self.initial_capital)

        total_trades = buy_count + sell_count
        test_start = daily_states[0].date if daily_states else ""
        test_end = daily_states[-1].date if daily_states else ""

        return PortfolioSummary(
            model_name=model_name,
            window_year=window_year,
            test_start=test_start,
            test_end=test_end,
            initial_capital=self.initial_capital,
            final_value=round(final_value, 2),
            total_return_thb=round(total_return_thb, 2),
            total_return_pct=round(total_return_pct, 2),
            total_trades=total_trades,
            buy_count=buy_count,
            sell_count=sell_count,
            hold_count=hold_count,
            rejected_count=rejected_count,
            max_drawdown_thb=round(max_dd_thb, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=round(sharpe, 4),
            spread_cost_total=round(spread_cost_total, 2),
            vc_settlement=vc_settlement,
            daily_states=daily_states,
        )

    # ─── Metrics ─────────────────────────────────────────────────────────

    @staticmethod
    def _calc_max_drawdown(values: list[float], initial: float) -> tuple[float, float]:
        """Max drawdown จาก portfolio values"""
        if not values:
            return 0.0, 0.0
        arr = np.array(values)
        peak = np.maximum.accumulate(arr)
        drawdown = peak - arr
        max_dd = float(np.max(drawdown))
        max_dd_pct = (max_dd / initial) * 100 if initial > 0 else 0.0
        return max_dd, max_dd_pct

    @staticmethod
    def _calc_sharpe(returns: list[float], risk_free: float = 0.0) -> float:
        """Sharpe Ratio (annualized)"""
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns) - risk_free
        std = np.std(arr, ddof=1)
        if std == 0:
            return 0.0
        return float(np.mean(arr) / std * np.sqrt(252))

    @staticmethod
    def _calc_vc_settlement(final_value: float, initial_capital: float) -> dict:
        """
        คำนวณการคืนเงิน VC ตามกฎข้อ 8:
        - กำไร → คืนต้นทุน 1,500 + กำไร 50% ให้ VC
        - ขาดทุน → คืนเงินทั้งหมดที่เหลือในบัญชีให้ VC
        """
        pnl = final_value - initial_capital
        if pnl > 0:
            return {
                "status": "PROFIT",
                "final_value": round(final_value, 2),
                "profit": round(pnl, 2),
                "return_to_vc": round(initial_capital + pnl * 0.5, 2),
                "keep_profit": round(pnl * 0.5, 2),
            }
        else:
            return {
                "status": "LOSS",
                "final_value": round(final_value, 2),
                "loss": round(abs(pnl), 2),
                "return_to_vc": round(final_value, 2),
                "keep_profit": 0.0,
            }
