"""
test_deploy_gate.py — Pytest สำหรับทดสอบ deploy_gate

Strategy: 100% Real (ไม่มี mock)
- deploy_gate รับ dict → เปรียบเทียบ thresholds → คืน dict
- ไม่มี I/O ใดๆ ทั้งสิ้น

Thresholds:
  sharpe_ratio        > 1.0
  win_rate            > 50%
  max_drawdown        < 20%
  profit_factor       > 1.2
  session_compliance  > 80%
  portfolio_not_bust  = True
  calmar_ratio        > 1.0
"""

import pytest

from backtest.metrics.deploy_gate import deploy_gate, _safe, print_gate_report

# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════


def _make_metrics(
    sharpe=1.5,
    mdd=-10.0,
    win_rate=60.0,
    pf=1.5,
    compliance=90.0,
    bust=False,
    calmar=1.5,
    ann_return=20.0,
):
    """สร้าง metrics dict ตาม structure ที่ deploy_gate คาดหวัง"""
    return {
        "risk": {
            "sharpe_ratio": sharpe,
            "mdd_pct": mdd,
            "annualized_return_pct": ann_return,
        },
        "trade": {
            "win_rate_pct": win_rate,
            "profit_factor": pf,
            "calmar_ratio": calmar,
        },
        "session_compliance": {
            "compliance_pct": compliance,
        },
        "bust_flag": bust,
    }


@pytest.fixture
def passing_metrics():
    """Metrics ที่ผ่านทุก threshold"""
    return _make_metrics()


@pytest.fixture
def failing_metrics():
    """Metrics ที่ไม่ผ่านทุก threshold"""
    return _make_metrics(
        sharpe=0.5,
        mdd=-25.0,
        win_rate=40.0,
        pf=0.8,
        compliance=60.0,
        bust=True,
        calmar=0.5,
    )


# ══════════════════════════════════════════════════════════════════
# 1. DEPLOY Verdict (ผ่านทุกข้อ)
# ══════════════════════════════════════════════════════════════════


class TestDeployPass:
    """Metrics ดีทั้งหมด → ✅ DEPLOY"""

    def test_verdict_deploy(self, passing_metrics):
        gate = deploy_gate(passing_metrics)
        assert gate["verdict"] == "✅ DEPLOY"

    def test_all_checks_true(self, passing_metrics):
        gate = deploy_gate(passing_metrics)
        assert all(gate["checks"].values())

    def test_passed_count_equals_total(self, passing_metrics):
        gate = deploy_gate(passing_metrics)
        assert gate["passed_count"] == gate["total_count"]
        assert gate["total_count"] == 7  # 7 checks

    def test_no_fail_reasons(self, passing_metrics):
        gate = deploy_gate(passing_metrics)
        assert gate["fail_reasons"] == []

    def test_bust_flag_false(self, passing_metrics):
        gate = deploy_gate(passing_metrics)
        assert gate["bust_flag"] is False


# ══════════════════════════════════════════════════════════════════
# 2. NOT READY Verdict (ไม่ผ่านทุกข้อ)
# ══════════════════════════════════════════════════════════════════


class TestDeployFail:
    """Metrics แย่ทั้งหมด → ❌ NOT READY"""

    def test_verdict_not_ready(self, failing_metrics):
        gate = deploy_gate(failing_metrics)
        assert gate["verdict"] == "❌ NOT READY"

    def test_all_checks_false(self, failing_metrics):
        gate = deploy_gate(failing_metrics)
        assert all(not v for v in gate["checks"].values())

    def test_passed_count_zero(self, failing_metrics):
        gate = deploy_gate(failing_metrics)
        assert gate["passed_count"] == 0

    def test_fail_reasons_7(self, failing_metrics):
        gate = deploy_gate(failing_metrics)
        assert len(gate["fail_reasons"]) == 7

    def test_bust_flag_true(self, failing_metrics):
        gate = deploy_gate(failing_metrics)
        assert gate["bust_flag"] is True


# ══════════════════════════════════════════════════════════════════
# 3. Single Threshold Failures
# ══════════════════════════════════════════════════════════════════


class TestSingleFailure:
    """ทดสอบแต่ละ threshold แยก — fail ข้อเดียวก็ NOT READY"""

    def test_low_sharpe(self):
        gate = deploy_gate(_make_metrics(sharpe=0.8))
        assert gate["verdict"] == "❌ NOT READY"
        assert gate["checks"]["sharpe_ratio"] is False
        assert gate["passed_count"] == 6

    def test_low_win_rate(self):
        gate = deploy_gate(_make_metrics(win_rate=45.0))
        assert gate["checks"]["win_rate_pct"] is False

    def test_high_drawdown(self):
        """mdd = -25% → abs = 25 > 20 → fail"""
        gate = deploy_gate(_make_metrics(mdd=-25.0))
        assert gate["checks"]["mdd_pct_abs"] is False

    def test_low_profit_factor(self):
        gate = deploy_gate(_make_metrics(pf=1.0))
        assert gate["checks"]["profit_factor"] is False

    def test_low_compliance(self):
        gate = deploy_gate(_make_metrics(compliance=75.0))
        assert gate["checks"]["session_compliance"] is False

    def test_bust_true(self):
        gate = deploy_gate(_make_metrics(bust=True))
        assert gate["checks"]["portfolio_not_bust"] is False

    def test_low_calmar(self):
        gate = deploy_gate(_make_metrics(calmar=0.9))
        assert gate["checks"]["calmar_ratio"] is False


# ══════════════════════════════════════════════════════════════════
# 4. Boundary Values (ขอบ threshold)
# ══════════════════════════════════════════════════════════════════


class TestBoundaryValues:
    """ทดสอบค่าที่อยู่บน boundary ของ threshold"""

    def test_sharpe_exactly_1(self):
        """sharpe = 1.0 → NOT > 1.0 → fail"""
        gate = deploy_gate(_make_metrics(sharpe=1.0))
        assert gate["checks"]["sharpe_ratio"] is False

    def test_sharpe_just_above(self):
        """sharpe = 1.001 → > 1.0 → pass"""
        gate = deploy_gate(_make_metrics(sharpe=1.001))
        assert gate["checks"]["sharpe_ratio"] is True

    def test_win_rate_exactly_50(self):
        """win_rate = 50.0 → NOT > 50 → fail"""
        gate = deploy_gate(_make_metrics(win_rate=50.0))
        assert gate["checks"]["win_rate_pct"] is False

    def test_mdd_exactly_20(self):
        """abs(mdd) = 20.0 → NOT < 20 → fail"""
        gate = deploy_gate(_make_metrics(mdd=-20.0))
        assert gate["checks"]["mdd_pct_abs"] is False

    def test_mdd_just_under(self):
        """abs(mdd) = 19.99 → < 20 → pass"""
        gate = deploy_gate(_make_metrics(mdd=-19.99))
        assert gate["checks"]["mdd_pct_abs"] is True


# ══════════════════════════════════════════════════════════════════
# 5. Missing / None Values
# ══════════════════════════════════════════════════════════════════


class TestMissingValues:
    """ทดสอบกรณี metrics มี keys ไม่ครบหรือเป็น None"""

    def test_empty_metrics(self):
        """dict ว่าง → ใช้ default ทั้งหมด → fail ทุกข้อ"""
        gate = deploy_gate({})
        assert gate["verdict"] == "❌ NOT READY"
        assert gate["passed_count"] < gate["total_count"]

    def test_none_values(self):
        """ค่า None → fallback to default"""
        metrics = _make_metrics()
        metrics["risk"]["sharpe_ratio"] = None
        gate = deploy_gate(metrics)
        # sharpe default = 0.0 → fail
        assert gate["checks"]["sharpe_ratio"] is False

    def test_missing_risk_key(self):
        """ไม่มี risk key → default 0"""
        metrics = {
            "trade": {"win_rate_pct": 60, "profit_factor": 1.5, "calmar_ratio": 1.5},
            "session_compliance": {"compliance_pct": 90},
            "bust_flag": False,
        }
        gate = deploy_gate(metrics)
        assert gate["checks"]["sharpe_ratio"] is False  # default 0

    def test_bust_flag_integer_truthy(self):
        """bust_flag=1 (int) → bool(1)=True → fail"""
        metrics = _make_metrics(bust=1)
        gate = deploy_gate(metrics)
        assert gate["bust_flag"] is True
        assert gate["checks"]["portfolio_not_bust"] is False


# ══════════════════════════════════════════════════════════════════
# 6. Output Structure
# ══════════════════════════════════════════════════════════════════


class TestOutputStructure:
    """ทดสอบว่า output dict มี keys ครบ"""

    def test_required_keys(self, passing_metrics):
        gate = deploy_gate(passing_metrics)
        required = {
            "verdict",
            "checks",
            "values",
            "thresholds",
            "passed_count",
            "total_count",
            "fail_reasons",
            "bust_flag",
        }
        assert required.issubset(gate.keys())

    def test_checks_has_7_entries(self, passing_metrics):
        gate = deploy_gate(passing_metrics)
        assert len(gate["checks"]) == 7

    def test_values_are_numeric(self, passing_metrics):
        gate = deploy_gate(passing_metrics)
        for name, val in gate["values"].items():
            if name == "portfolio_not_bust":
                assert isinstance(val, bool)
            else:
                assert isinstance(val, (int, float))


# ══════════════════════════════════════════════════════════════════
# 7. _safe Helper
# ══════════════════════════════════════════════════════════════════


class TestSafeHelper:
    """ทดสอบ _safe utility function"""

    def test_existing_key(self):
        assert _safe({"a": 42}, "a") == 42

    def test_missing_key(self):
        assert _safe({"a": 42}, "b", default=0.0) == 0.0

    def test_none_value_uses_default(self):
        assert _safe({"a": None}, "a", default=99) == 99


class TestPrintGateReport:
    """ทดสอบว่า print_gate_report ไม่ crash"""

    def test_print_pass(self, passing_metrics, capsys):
        gate = deploy_gate(passing_metrics)
        print_gate_report(gate)
        out = capsys.readouterr().out
        assert "DEPLOY" in out

    def test_print_fail(self, failing_metrics, capsys):
        gate = deploy_gate(failing_metrics)
        print_gate_report(gate)
        out = capsys.readouterr().out
        assert "NOT READY" in out
