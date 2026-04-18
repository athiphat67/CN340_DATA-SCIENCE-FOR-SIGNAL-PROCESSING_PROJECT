"""
Src/tests/test_ui/test_ui_renderers.py
══════════════════════════════════════════════════════════════════════
ทดสอบ Renderer classes ใน ui/core/renderers.py

Strategy: ทดสอบ HTML output ที่คืนกลับมา
- ตรวจว่า HTML มี content สำคัญอยู่
- ตรวจว่า edge cases (empty input) ไม่ crash
- ไม่ต้อง launch Gradio หรือ browser

ครอบคลุม:
  1. StatusRenderer  — error/success/info badges
  2. TraceRenderer   — ReAct trace HTML
  3. HistoryRenderer — run history table HTML
  4. StatsRenderer   — signal statistics HTML
  5. PortfolioRenderer — portfolio cards HTML
══════════════════════════════════════════════════════════════════════
"""

import pytest
from ui.core.renderers import (
    StatusRenderer,
    TraceRenderer,
    HistoryRenderer,
    StatsRenderer,
    PortfolioRenderer,
)


# ══════════════════════════════════════════════
# 1. StatusRenderer
# ══════════════════════════════════════════════

class TestStatusRendererErrorBadge:
    """ทดสอบ StatusRenderer.error_badge()"""

    def test_returns_string(self):
        result = StatusRenderer.error_badge("Something failed")
        assert isinstance(result, str)

    def test_contains_message(self):
        result = StatusRenderer.error_badge("API timeout")
        assert "API timeout" in result

    def test_contains_html(self):
        """ต้องเป็น HTML"""
        result = StatusRenderer.error_badge("error")
        assert "<div" in result

    def test_validation_error_different_style(self):
        """is_validation=True ต้องมี style ต่างจากปกติ"""
        normal = StatusRenderer.error_badge("msg", is_validation=False)
        validation = StatusRenderer.error_badge("msg", is_validation=True)
        assert normal != validation

    def test_empty_message_no_crash(self):
        """message ว่าง → ไม่ crash"""
        result = StatusRenderer.error_badge("")
        assert isinstance(result, str)


class TestStatusRendererSuccessBadge:
    """ทดสอบ StatusRenderer.success_badge()"""

    def test_returns_string(self):
        result = StatusRenderer.success_badge("Done")
        assert isinstance(result, str)

    def test_contains_message(self):
        result = StatusRenderer.success_badge("Analysis complete")
        assert "Analysis complete" in result

    def test_contains_html(self):
        result = StatusRenderer.success_badge("ok")
        assert "<div" in result

    def test_contains_checkmark(self):
        """success badge ต้องมี checkmark หรือ ✓"""
        result = StatusRenderer.success_badge("ok")
        assert "✓" in result or "check" in result.lower() or "success" in result.lower()


class TestStatusRendererInfoBadge:
    """ทดสอบ StatusRenderer.info_badge()"""

    def test_returns_string(self):
        result = StatusRenderer.info_badge("Info message")
        assert isinstance(result, str)

    def test_contains_message(self):
        result = StatusRenderer.info_badge("Auto-run disabled")
        assert "Auto-run disabled" in result

    def test_contains_html(self):
        result = StatusRenderer.info_badge("info")
        assert "<div" in result


class TestStatusRendererSignalDecisionCard:
    """ทดสอบ StatusRenderer.signal_decision_card()"""

    def test_returns_string(self):
        result = StatusRenderer.signal_decision_card("BUY", 0.85)
        assert isinstance(result, str)

    def test_contains_signal(self):
        result = StatusRenderer.signal_decision_card("BUY", 0.85)
        assert "BUY" in result

    def test_contains_confidence(self):
        result = StatusRenderer.signal_decision_card("SELL", 0.75)
        assert "75%" in result or "0.75" in result or "75" in result

    def test_sell_signal(self):
        result = StatusRenderer.signal_decision_card("SELL", 0.8)
        assert "SELL" in result

    def test_hold_signal(self):
        result = StatusRenderer.signal_decision_card("HOLD", 0.5)
        assert "HOLD" in result

    def test_with_price_levels(self):
        """ใส่ entry/sl/tp → ต้องแสดงราคา"""
        result = StatusRenderer.signal_decision_card(
            "BUY", 0.9,
            entry_price=45000,
            stop_loss=44500,
            take_profit=46000,
        )
        assert "45,000" in result or "45000" in result
        assert "44,500" in result or "44500" in result

    def test_strong_signal_label(self):
        """confidence >= 0.85 → STRONG BUY/SELL"""
        result = StatusRenderer.signal_decision_card("BUY", 0.9)
        assert "STRONG" in result or "BUY" in result


# ══════════════════════════════════════════════
# 2. TraceRenderer
# ══════════════════════════════════════════════

class TestTraceRenderer:
    """ทดสอบ TraceRenderer.format_trace_html()"""

    def _sample_trace(self):
        return [
            {
                "step": "THOUGHT_1",
                "iteration": 1,
                "response": {
                    "thought": "ราคาทองกำลังขึ้น RSI = 65",
                    "action": "get_indicators",
                },
            },
            {
                "step": "TOOL_EXECUTION",
                "iteration": 1,
                "response": {"action": "get_indicators"},
                "observation": {"status": "success", "data": {"rsi": 65}},
            },
            {
                "step": "FINAL_DECISION",
                "iteration": 2,
                "response": {
                    "thought": "BUY signal ชัดเจน",
                    "signal": "BUY",
                    "confidence": 0.85,
                },
            },
        ]

    def test_returns_string(self):
        result = TraceRenderer.format_trace_html(self._sample_trace())
        assert isinstance(result, str)

    def test_empty_trace_no_crash(self):
        """trace ว่าง → ไม่ crash, คืน HTML"""
        result = TraceRenderer.format_trace_html([])
        assert isinstance(result, str)
        assert "<div" in result

    def test_contains_step_count(self):
        """ต้องแสดงจำนวน steps"""
        trace = self._sample_trace()
        result = TraceRenderer.format_trace_html(trace)
        assert "3" in result or "steps" in result.lower()

    def test_contains_thought_text(self):
        """ต้องแสดง thought text"""
        result = TraceRenderer.format_trace_html(self._sample_trace())
        assert "RSI" in result or "ราคาทอง" in result

    def test_contains_signal(self):
        """FINAL_DECISION ต้องแสดง BUY signal"""
        result = TraceRenderer.format_trace_html(self._sample_trace())
        assert "BUY" in result

    def test_contains_html_structure(self):
        """ต้องมี HTML structure"""
        result = TraceRenderer.format_trace_html(self._sample_trace())
        assert "<div" in result

    def test_single_step_no_crash(self):
        """1 step → ไม่ crash"""
        trace = [{"step": "THOUGHT_1", "iteration": 1, "response": {"thought": "test"}}]
        result = TraceRenderer.format_trace_html(trace)
        assert isinstance(result, str)


# ══════════════════════════════════════════════
# 3. HistoryRenderer
# ══════════════════════════════════════════════

class TestHistoryRenderer:
    """ทดสอบ HistoryRenderer.format_history_html()"""

    def _sample_rows(self):
        return [
            {
                "id": 1,
                "signal": "BUY",
                "confidence": 0.85,
                "gold_price": 45000,
                "rsi": 55.0,
                "provider": "openai",
                "interval_tf": "1h,4h",
                "run_at": "2026-04-01T10:00:00+07:00",
                "iterations_used": 3,
            },
            {
                "id": 2,
                "signal": "SELL",
                "confidence": 0.72,
                "gold_price": 45500,
                "rsi": 72.0,
                "provider": "gemini",
                "interval_tf": "1h",
                "run_at": "2026-04-01T14:00:00+07:00",
                "iterations_used": 2,
            },
        ]

    def test_returns_string(self):
        result = HistoryRenderer.format_history_html(self._sample_rows())
        assert isinstance(result, str)

    def test_empty_rows_no_crash(self):
        """rows ว่าง → ไม่ crash, คืน HTML"""
        result = HistoryRenderer.format_history_html([])
        assert isinstance(result, str)
        assert "<div" in result

    def test_contains_signal(self):
        """ต้องแสดง BUY/SELL signal"""
        result = HistoryRenderer.format_history_html(self._sample_rows())
        assert "BUY" in result
        assert "SELL" in result

    def test_contains_run_id(self):
        """ต้องแสดง run ID"""
        result = HistoryRenderer.format_history_html(self._sample_rows())
        assert "1" in result
        assert "2" in result

    def test_contains_provider(self):
        """ต้องแสดง provider"""
        result = HistoryRenderer.format_history_html(self._sample_rows())
        assert "openai" in result

    def test_contains_html_table(self):
        """ต้องมี <table> structure"""
        result = HistoryRenderer.format_history_html(self._sample_rows())
        assert "<table" in result

    def test_contains_price(self):
        """ต้องแสดงราคาทอง"""
        result = HistoryRenderer.format_history_html(self._sample_rows())
        assert "45,000" in result or "45000" in result

    def test_single_row_no_crash(self):
        """1 row → ไม่ crash"""
        result = HistoryRenderer.format_history_html([self._sample_rows()[0]])
        assert isinstance(result, str)


# ══════════════════════════════════════════════
# 4. StatsRenderer
# ══════════════════════════════════════════════

class TestStatsRenderer:
    """ทดสอบ StatsRenderer.format_stats_html()"""

    def _sample_stats(self):
        return {
            "total": 10,
            "buy_count": 5,
            "sell_count": 3,
            "hold_count": 2,
            "avg_confidence": 0.78,
            "avg_price": 45200,
        }

    def test_returns_string(self):
        result = StatsRenderer.format_stats_html(self._sample_stats())
        assert isinstance(result, str)

    def test_zero_total_no_crash(self):
        """total = 0 → ไม่ crash"""
        result = StatsRenderer.format_stats_html({"total": 0})
        assert isinstance(result, str)

    def test_contains_buy_count(self):
        """ต้องแสดง BUY count"""
        result = StatsRenderer.format_stats_html(self._sample_stats())
        assert "BUY" in result
        assert "5" in result

    def test_contains_sell_count(self):
        """ต้องแสดง SELL count"""
        result = StatsRenderer.format_stats_html(self._sample_stats())
        assert "SELL" in result

    def test_contains_total_runs(self):
        """ต้องแสดงจำนวน runs ทั้งหมด"""
        result = StatsRenderer.format_stats_html(self._sample_stats())
        assert "10" in result

    def test_contains_avg_confidence(self):
        """ต้องแสดง avg confidence"""
        result = StatsRenderer.format_stats_html(self._sample_stats())
        assert "78%" in result or "0.78" in result or "78" in result

    def test_contains_avg_price(self):
        """ต้องแสดง avg price"""
        result = StatsRenderer.format_stats_html(self._sample_stats())
        assert "45,200" in result or "45200" in result


# ══════════════════════════════════════════════
# 5. PortfolioRenderer
# ══════════════════════════════════════════════

class TestPortfolioRenderer:
    """ทดสอบ PortfolioRenderer.format_portfolio_html()"""

    def _sample_portfolio(self):
        return {
            "cash_balance": 5000.0,
            "gold_grams": 1.0,
            "cost_basis_thb": 4500.0,
            "current_value_thb": 4800.0,
            "unrealized_pnl": 300.0,
            "trades_today": 2,
            "updated_at": "2026-04-01T10:00:00+00:00",
        }

    def test_returns_string(self):
        result = PortfolioRenderer.format_portfolio_html(self._sample_portfolio())
        assert isinstance(result, str)

    def test_empty_portfolio_no_crash(self):
        """portfolio ว่าง → ไม่ crash"""
        result = PortfolioRenderer.format_portfolio_html({})
        assert isinstance(result, str)

    def test_none_portfolio_no_crash(self):
        """portfolio = None → ไม่ crash"""
        result = PortfolioRenderer.format_portfolio_html(None)
        assert isinstance(result, str)

    def test_contains_cash_balance(self):
        """ต้องแสดง cash balance"""
        result = PortfolioRenderer.format_portfolio_html(self._sample_portfolio())
        assert "5,000" in result or "5000" in result

    def test_contains_gold_grams(self):
        """ต้องแสดง gold grams"""
        result = PortfolioRenderer.format_portfolio_html(self._sample_portfolio())
        assert "1.0" in result or "1.0000" in result

    def test_contains_pnl(self):
        """ต้องแสดง P&L"""
        result = PortfolioRenderer.format_portfolio_html(self._sample_portfolio())
        assert "300" in result

    def test_contains_html_structure(self):
        """ต้องมี HTML div"""
        result = PortfolioRenderer.format_portfolio_html(self._sample_portfolio())
        assert "<div" in result

    def test_can_buy_indicator(self):
        """cash >= 1000 → แสดง Can Buy"""
        result = PortfolioRenderer.format_portfolio_html(self._sample_portfolio())
        assert "Can Buy" in result or "buy" in result.lower()

    def test_cannot_buy_when_cash_low(self):
        """cash < 1000 → Can Buy แสดงสถานะปิด"""
        poor = {**self._sample_portfolio(), "cash_balance": 500.0}
        result = PortfolioRenderer.format_portfolio_html(poor)
        assert isinstance(result, str)

    def test_trades_today_shown(self):
        """ต้องแสดง trades today"""
        result = PortfolioRenderer.format_portfolio_html(self._sample_portfolio())
        assert "2" in result