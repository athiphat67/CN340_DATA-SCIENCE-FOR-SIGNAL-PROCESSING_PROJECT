"""
Tests for data_engine/tools/schema_validator.py

Covers:
- validate_market_state: valid payload, empty dict, all 4 required paths,
  None-value leaf, non-dict intermediate node, extra fields, return type
"""

import copy
import pytest

from data_engine.tools.schema_validator import (
    REQUIRED_FIELDS,
    validate_market_state,
)

pytestmark = pytest.mark.data_engine

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def valid_state():
    """A market-state dict that satisfies all 4 required paths."""
    return {
        "market_data": {
            "spot_price_usd": 3200.50,
            "thai_gold_thb": {
                "sell_price_thb": 108500,
                "buy_price_thb": 108000,
            },
        },
        "technical_indicators": {
            "rsi": {
                "value": 52.5,
            },
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# TestValidateMarketState
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateMarketState:
    def test_valid_state_returns_empty_list(self, valid_state):
        """A fully-populated state produces zero errors."""
        assert validate_market_state(valid_state) == []

    def test_return_type_is_list(self, valid_state):
        """Return value must always be a list, even on success."""
        result = validate_market_state(valid_state)
        assert isinstance(result, list)

    def test_empty_dict_returns_four_errors(self):
        """An empty dict is missing every required field."""
        errors = validate_market_state({})
        assert len(errors) == 4

    def test_all_errors_start_with_missing_prefix(self):
        """Each error string must begin with 'Missing: '."""
        errors = validate_market_state({})
        assert all(e.startswith("Missing: ") for e in errors)

    def test_all_four_fields_missing_returns_four_errors(self):
        """Alias for empty-dict test — validates the count explicitly."""
        errors = validate_market_state({})
        assert len(errors) == 4

    @pytest.mark.parametrize("missing_path", REQUIRED_FIELDS)
    def test_each_required_path_detected_when_absent(self, valid_state, missing_path):
        """Removing a single required key must produce exactly that path in errors."""
        state = copy.deepcopy(valid_state)
        parts = missing_path.split(".")

        # Navigate to the parent dict and delete the leaf key.
        obj = state
        for part in parts[:-1]:
            obj = obj[part]
        del obj[parts[-1]]

        errors = validate_market_state(state)
        assert f"Missing: {missing_path}" in errors

    def test_none_value_at_leaf_passes_validation(self, valid_state):
        """A key present with None value is NOT missing — validation must pass."""
        state = copy.deepcopy(valid_state)
        state["market_data"]["spot_price_usd"] = None
        assert validate_market_state(state) == []

    def test_intermediate_node_is_string_returns_error(self, valid_state):
        """Replacing a dict node with a scalar breaks nested-path traversal."""
        state = copy.deepcopy(valid_state)
        # Replace the dict at thai_gold_thb with a plain string.
        state["market_data"]["thai_gold_thb"] = "not_a_dict"

        errors = validate_market_state(state)
        # Both nested paths inside thai_gold_thb should be reported missing.
        assert "Missing: market_data.thai_gold_thb.sell_price_thb" in errors
        assert "Missing: market_data.thai_gold_thb.buy_price_thb" in errors

    def test_extra_fields_do_not_cause_errors(self, valid_state):
        """Additional keys beyond the required set must be silently ignored."""
        state = copy.deepcopy(valid_state)
        state["extra_top_level_key"] = "ignored"
        state["market_data"]["extra_nested_key"] = 999
        assert validate_market_state(state) == []

    def test_error_message_contains_full_dotted_path(self):
        """Each error message must embed the full dot-separated path."""
        errors = validate_market_state({})
        reported_paths = [e.replace("Missing: ", "") for e in errors]
        for path in REQUIRED_FIELDS:
            assert path in reported_paths

    def test_only_missing_fields_reported(self, valid_state):
        """When one field is absent, only that one path appears in errors."""
        state = copy.deepcopy(valid_state)
        del state["technical_indicators"]["rsi"]["value"]

        errors = validate_market_state(state)
        assert len(errors) == 1
        assert errors[0] == "Missing: technical_indicators.rsi.value"
