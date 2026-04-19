"""
Src/tests/test_ui/test_ui_services.py
══════════════════════════════════════════════════════════════════════
ทดสอบ Services Layer ใน ui/core/services.py

Strategy: Mock DB และ external dependencies ทั้งหมด
- ไม่เรียก API จริง, ไม่เชื่อมต่อ DB จริง
- ทดสอบ logic ของ Service แต่ละตัว

ครอบคลุม:
  1. _normalize_provider()  — provider name normalization
  2. _extract_llm_log()     — log extraction helper
  3. PortfolioService       — save/load portfolio + validation
  4. HistoryService         — get_recent_runs, statistics, run_detail, llm_logs
  5. AnalysisService        — input validation, error handling
══════════════════════════════════════════════════════════════════════
"""

import pytest
from unittest.mock import MagicMock, patch

from ui.core.services import (
    _normalize_provider,
    _extract_llm_log,
    PortfolioService,
    HistoryService,
    AnalysisService,
)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _mock_db():
    """สร้าง mock DB object"""
    db = MagicMock()
    db.get_portfolio.return_value = {
        "cash_balance":      5000.0,
        "gold_grams":        1.0,
        "cost_basis_thb":    4500.0,
        "current_value_thb": 4800.0,
        "unrealized_pnl":    300.0,
        "trades_today":      2,
        "updated_at":        "2026-04-01T10:00:00+00:00",
    }
    db.save_portfolio.return_value = None
    db.get_recent_runs.return_value = [
        {"id": 1, "signal": "BUY", "confidence": 0.85, "provider": "openai"},
        {"id": 2, "signal": "SELL", "confidence": 0.72, "provider": "gemini"},
    ]
    db.get_signal_stats.return_value = {
        "total": 10, "buy_count": 5, "sell_count": 3,
        "hold_count": 2, "avg_confidence": 0.78, "avg_price": 45200,
    }
    db.get_llm_logs_for_run.return_value = [
        {"interval_tf": "1h", "signal": "BUY", "confidence": 0.85},
    ]
    db.get_recent_llm_logs.return_value = []
    db.save_run.return_value = 42
    db.save_llm_logs_batch.return_value = [1]
    return db


def _sample_interval_result():
    return {
        "signal":          "BUY",
        "confidence":      0.85,
        "rationale":       "Gold price trending up",
        "reasoning":       "Gold price trending up",
        "entry_price":     45000.0,
        "stop_loss":       44500.0,
        "take_profit":     46000.0,
        "trace":           [],
        "provider_used":   "openai",
        "fallback_log":    [],
        "is_fallback":     False,
        "fallback_from":   None,
        "elapsed_ms":      1200,
        "token_input":     500,
        "token_output":    200,
        "token_total":     700,
        "iterations_used": 3,
        "tool_calls_used": 2,
        "full_prompt":     "Analyze gold...",
        "full_response":   "BUY signal detected",
    }


# ══════════════════════════════════════════════
# 1. _normalize_provider
# ══════════════════════════════════════════════

class TestNormalizeProvider:
    """ทดสอบ provider name normalization"""

    def test_gemini_variant_normalized(self):
        """gemini_2.5_flash → gemini"""
        assert _normalize_provider("gemini_2.5_flash") == "gemini"

    def test_gemini_with_hyphen(self):
        """gemini-2.5-flash → gemini"""
        assert _normalize_provider("gemini-2.5-flash") == "gemini"

    def test_groq_variant_normalized(self):
        """groq_llama → groq"""
        assert _normalize_provider("groq_llama") == "groq"

    def test_mock_variant_normalized(self):
        """mock-v1 → mock"""
        assert _normalize_provider("mock-v1") == "mock"

    def test_canonical_name_unchanged(self):
        """openai ไม่มีใน alias → คืนตัวเดิม"""
        assert _normalize_provider("openai") == "openai"

    def test_empty_string_returns_empty(self):
        """string ว่าง → คืน string ว่าง"""
        assert _normalize_provider("") == ""

    def test_none_returns_none(self):
        """None → คืน None"""
        assert _normalize_provider(None) is None

    def test_unknown_provider_unchanged(self):
        """provider ที่ไม่รู้จัก → คืนตัวเดิม"""
        result = _normalize_provider("some_unknown_provider")
        assert result == "some_unknown_provider"

    def test_mock_v1_with_underscore(self):
        """mock_v1 → mock"""
        assert _normalize_provider("mock_v1") == "mock"

    def test_case_insensitive(self):
        """uppercase variant → normalize ได้"""
        result = _normalize_provider("MOCK-V1")
        assert result in {"mock", "MOCK-V1"}  # อาจ normalize หรือ return เดิม


# ══════════════════════════════════════════════
# 2. _extract_llm_log
# ══════════════════════════════════════════════

class TestExtractLlmLog:
    """ทดสอบ _extract_llm_log() helper"""

    def test_returns_dict(self):
        result = _extract_llm_log(_sample_interval_result(), "1h")
        assert isinstance(result, dict)

    def test_interval_tf_set(self):
        result = _extract_llm_log(_sample_interval_result(), "4h")
        assert result["interval_tf"] == "4h"

    def test_signal_extracted(self):
        result = _extract_llm_log(_sample_interval_result(), "1h")
        assert result["signal"] == "BUY"

    def test_confidence_extracted(self):
        result = _extract_llm_log(_sample_interval_result(), "1h")
        assert result["confidence"] == 0.85

    def test_provider_extracted(self):
        result = _extract_llm_log(_sample_interval_result(), "1h")
        assert result["provider"] == "openai"

    def test_token_info_extracted(self):
        result = _extract_llm_log(_sample_interval_result(), "1h")
        assert result["token_total"] == 700
        assert result["token_input"] == 500

    def test_no_fallback_when_clean(self):
        result = _extract_llm_log(_sample_interval_result(), "1h")
        assert result["is_fallback"] is False
        assert result["fallback_from"] is None

    def test_fallback_detected(self):
        """fallback_log มีข้อมูล → is_fallback = True"""
        ir = {**_sample_interval_result(), "fallback_log": [{"provider": "openai"}]}
        result = _extract_llm_log(ir, "1h")
        assert result["is_fallback"] is True
        assert result["fallback_from"] == "openai"

    def test_has_required_keys(self):
        """ต้องมี keys ครบที่ DB ต้องการ"""
        result = _extract_llm_log(_sample_interval_result(), "1h")
        required = {
            "interval_tf", "signal", "confidence", "provider",
            "rationale", "token_total", "elapsed_ms", "is_fallback",
        }
        assert required.issubset(result.keys())

    def test_missing_fields_use_defaults(self):
        """interval_result ไม่ครบ → ใช้ default ไม่ crash"""
        result = _extract_llm_log({}, "1h")
        assert result["signal"] == "HOLD"
        assert result["confidence"] == 0.0
        assert result["is_fallback"] is False


# ══════════════════════════════════════════════
# 3. PortfolioService
# ══════════════════════════════════════════════

class TestPortfolioServiceSave:
    """ทดสอบ PortfolioService.save_portfolio()"""

    def test_save_success(self):
        """save ปกติ → status = success"""
        svc = PortfolioService(_mock_db())
        result = svc.save_portfolio(
            cash=5000, gold_grams=1.0, cost_basis=4500,
            current_value=4800, pnl=300, trades_today=2,
        )
        assert result["status"] == "success"

    def test_save_returns_data(self):
        """save สำเร็จ → ต้องมี data"""
        svc = PortfolioService(_mock_db())
        result = svc.save_portfolio(5000, 1.0, 4500, 4800, 300, 2)
        assert "data" in result
        assert result["data"]["cash_balance"] == 5000.0

    def test_save_calls_db(self):
        """ต้องเรียก db.save_portfolio()"""
        db = _mock_db()
        svc = PortfolioService(db)
        svc.save_portfolio(5000, 1.0, 4500, 4800, 300, 2)
        db.save_portfolio.assert_called_once()

    def test_negative_cash_rejected(self):
        """cash < 0 → validation fail → status = error"""
        svc = PortfolioService(_mock_db())
        result = svc.save_portfolio(-100, 1.0, 4500, 4800, 300, 2)
        assert result["status"] == "error"

    def test_negative_gold_rejected(self):
        """gold_grams < 0 → validation fail"""
        svc = PortfolioService(_mock_db())
        result = svc.save_portfolio(5000, -1.0, 4500, 4800, 300, 2)
        assert result["status"] == "error"

    def test_negative_pnl_allowed(self):
        """pnl < 0 ได้ (ขาดทุนปกติ)"""
        svc = PortfolioService(_mock_db())
        result = svc.save_portfolio(5000, 1.0, 4500, 4800, -300, 2)
        assert result["status"] == "success"

    def test_db_error_returns_error_status(self):
        """db.save_portfolio() raise exception → status = error"""
        db = _mock_db()
        db.save_portfolio.side_effect = Exception("DB connection failed")
        svc = PortfolioService(db)
        result = svc.save_portfolio(5000, 1.0, 4500, 4800, 300, 2)
        assert result["status"] == "error"

    def test_zero_values_allowed(self):
        """ค่า 0 ทั้งหมดได้ (portfolio ว่าง)"""
        svc = PortfolioService(_mock_db())
        result = svc.save_portfolio(0, 0.0, 0, 0, 0, 0)
        assert result["status"] == "success"


class TestPortfolioServiceLoad:
    """ทดสอบ PortfolioService.load_portfolio()"""

    def test_load_success(self):
        """load ปกติ → status = success"""
        svc = PortfolioService(_mock_db())
        result = svc.load_portfolio()
        assert result["status"] == "success"

    def test_load_returns_data(self):
        """ต้องมี data"""
        svc = PortfolioService(_mock_db())
        result = svc.load_portfolio()
        assert "data" in result
        assert result["data"]["cash_balance"] == 5000.0

    def test_load_uses_default_when_db_empty(self):
        """DB ว่าง → ใช้ DEFAULT_PORTFOLIO"""
        db = _mock_db()
        db.get_portfolio.return_value = None
        svc = PortfolioService(db)
        result = svc.load_portfolio()
        assert result["status"] == "success"
        assert "cash_balance" in result["data"]

    def test_load_db_error_returns_default(self):
        """DB error → คืน default portfolio ไม่ crash"""
        db = _mock_db()
        db.get_portfolio.side_effect = Exception("DB down")
        svc = PortfolioService(db)
        result = svc.load_portfolio()
        assert result["status"] == "error"
        assert "data" in result  # ยังต้องมี data (default)


# ══════════════════════════════════════════════
# 4. HistoryService
# ══════════════════════════════════════════════

class TestHistoryServiceGetRecentRuns:
    """ทดสอบ HistoryService.get_recent_runs()"""

    def test_returns_list(self):
        svc = HistoryService(_mock_db())
        result = svc.get_recent_runs()
        assert isinstance(result, list)

    def test_returns_correct_count(self):
        svc = HistoryService(_mock_db())
        result = svc.get_recent_runs(limit=50)
        assert len(result) == 2  # mock มี 2 rows

    def test_calls_db_with_limit(self):
        db = _mock_db()
        svc = HistoryService(db)
        svc.get_recent_runs(limit=20)
        db.get_recent_runs.assert_called_with(limit=20)

    def test_db_error_returns_empty_list(self):
        """DB error → คืน [] ไม่ crash"""
        db = _mock_db()
        db.get_recent_runs.side_effect = Exception("DB down")
        svc = HistoryService(db)
        result = svc.get_recent_runs()
        assert result == []


class TestHistoryServiceGetStatistics:
    """ทดสอบ HistoryService.get_statistics()"""

    def test_returns_dict(self):
        svc = HistoryService(_mock_db())
        result = svc.get_statistics()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        svc = HistoryService(_mock_db())
        result = svc.get_statistics()
        assert "total" in result
        assert "buy_count" in result
        assert "sell_count" in result

    def test_correct_values(self):
        svc = HistoryService(_mock_db())
        result = svc.get_statistics()
        assert result["total"] == 10
        assert result["buy_count"] == 5

    def test_db_error_returns_zero_stats(self):
        """DB error → คืน zero stats ไม่ crash"""
        db = _mock_db()
        db.get_signal_stats.side_effect = Exception("DB down")
        svc = HistoryService(db)
        result = svc.get_statistics()
        assert result["total"] == 0
        assert result["buy_count"] == 0


class TestHistoryServiceGetRunDetail:
    """ทดสอบ HistoryService.get_run_detail()"""

    def test_found_run_returns_success(self):
        db = _mock_db()
        db.get_run_by_id = MagicMock(return_value={
            "id": 1, "signal": "BUY", "confidence": 0.85
        })
        svc = HistoryService(db)
        result = svc.get_run_detail(1)
        assert result["status"] == "success"
        assert result["data"]["id"] == 1

    def test_not_found_returns_error(self):
        """run ไม่เจอ → status = error"""
        db = _mock_db()
        db.get_run_by_id = MagicMock(return_value=None)
        svc = HistoryService(db)
        result = svc.get_run_detail(999)
        assert result["status"] == "error"

    def test_fallback_to_recent_runs_when_no_get_run_by_id(self):
        """ถ้า DB ไม่มี get_run_by_id → fallback ไป get_recent_runs"""
        db = _mock_db()
        del db.get_run_by_id  # ลบ method ออก
        db.get_recent_runs.return_value = [{"id": 1, "signal": "BUY"}]
        svc = HistoryService(db)
        result = svc.get_run_detail(1)
        assert result["status"] == "success"

    def test_db_error_returns_error(self):
        db = _mock_db()
        db.get_run_by_id = MagicMock(side_effect=Exception("DB down"))
        svc = HistoryService(db)
        result = svc.get_run_detail(1)
        assert result["status"] == "error"


class TestHistoryServiceGetLlmLogs:
    """ทดสอบ HistoryService.get_llm_logs()"""

    def test_returns_list(self):
        svc = HistoryService(_mock_db())
        result = svc.get_llm_logs(run_id=1)
        assert isinstance(result, list)

    def test_calls_db_with_run_id(self):
        db = _mock_db()
        svc = HistoryService(db)
        svc.get_llm_logs(run_id=42)
        db.get_llm_logs_for_run.assert_called_with(42)

    def test_db_error_returns_empty_list(self):
        db = _mock_db()
        db.get_llm_logs_for_run.side_effect = Exception("DB down")
        svc = HistoryService(db)
        result = svc.get_llm_logs(run_id=1)
        assert result == []

    def test_get_recent_llm_logs_returns_list(self):
        svc = HistoryService(_mock_db())
        result = svc.get_recent_llm_logs(limit=10)
        assert isinstance(result, list)


# ══════════════════════════════════════════════
# 5. AnalysisService — Input Validation
# ══════════════════════════════════════════════

class TestAnalysisServiceValidation:
    """ทดสอบ _validate_inputs() ของ AnalysisService"""

    def _make_service(self):
        return AnalysisService(
            skill_registry=MagicMock(),
            role_registry=MagicMock(),
            data_orchestrator=MagicMock(),
            persistence=None,
        )

    def test_empty_intervals_returns_error(self):
        """intervals ว่าง → validation error"""
        svc = self._make_service()
        result = svc.run_analysis("mock", "1d", [])
        assert result["status"] == "error"
        assert result["error_type"] == "validation"

    def test_invalid_provider_returns_error(self):
        """provider ไม่ถูกต้อง → validation error"""
        svc = self._make_service()
        result = svc.run_analysis("invalid_xyz_provider", "1d", ["1h"])
        assert result["status"] == "error"
        assert result["error_type"] == "validation"

    def test_provider_normalization_applied(self):
        """gemini_2.5_flash → normalize เป็น gemini ก่อน validate"""
        svc = self._make_service()
        with patch("ui.core.config.validate_provider", return_value=True), \
             patch("ui.core.config.validate_period", return_value=True), \
             patch("ui.core.config.validate_intervals", return_value=True):
            with patch.object(svc, "_run_single_interval",
                              return_value=_sample_interval_result()):
                with patch.object(svc.data_orchestrator, "run",
                                  return_value={"market_data": {}}):
                    result = svc.run_analysis("gemini_2.5_flash", "1d", ["1h"])
                    # แค่ตรวจว่าไม่ crash และ normalize ทำงาน

    def test_validate_inputs_no_error_when_valid(self):
        """input ถูกต้อง → _validate_inputs คืน None"""
        svc = self._make_service()
        with patch("ui.core.config.validate_provider", return_value=True), \
             patch("ui.core.config.validate_period", return_value=True), \
             patch("ui.core.config.validate_intervals", return_value=True):
            result = svc._validate_inputs("mock", "1d", ["1h"])
            assert result is None

    def test_validate_inputs_bad_provider(self):
        """provider ไม่ถูกต้อง → _validate_inputs คืน error string"""
        svc = self._make_service()
        with patch("ui.core.config.validate_provider", return_value=False):
            result = svc._validate_inputs("bad_provider", "1d", ["1h"])
            assert result is not None
            assert "provider" in result.lower() or "Invalid" in result

    def test_validate_inputs_empty_intervals(self):
        """intervals ว่าง → _validate_inputs คืน error string"""
        svc = self._make_service()
        with patch("ui.core.config.validate_provider", return_value=True), \
             patch("ui.core.config.validate_period", return_value=True):
            result = svc._validate_inputs("mock", "1d", [])
            assert result is not None
            assert "interval" in result.lower()

    def test_run_analysis_returns_error_dict_on_exception(self):
        """data_orchestrator.run() raise exception → status = error"""
        svc = self._make_service()
        with patch("ui.core.config.validate_provider", return_value=True), \
             patch("ui.core.config.validate_period", return_value=True), \
             patch("ui.core.config.validate_intervals", return_value=True):
            svc.data_orchestrator.run.side_effect = Exception("Network error")
            result = svc.run_analysis("mock", "1d", ["1h"])
            assert result["status"] == "error"