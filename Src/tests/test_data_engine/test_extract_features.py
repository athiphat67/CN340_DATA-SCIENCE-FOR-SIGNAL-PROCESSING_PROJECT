"""
test_extract_features.py — Pytest สำหรับ extract_features module

ครอบคลุม:
  1. build_feature_dataset — สร้าง feature dataset จาก JSON → CSV
  2. Time features — session encoding (Asian/London/NY)
  3. Trend mapping — uptrend/downtrend/sideways → 1/-1/0
  4. Sentiment features — เฉลี่ย sentiment จากข่าว
  5. CSV append mode — ไฟล์ใหม่ + ต่อท้าย
  6. Error handling — ไฟล์ JSON ไม่มี

Strategy: ใช้ tmp_path สำหรับ file I/O, สร้าง mock JSON data
  - Deterministic 100%
  - ไม่เรียก API จริง
"""

import json
import os
import pytest
import pandas as pd

from data_engine.extract_features import build_feature_dataset


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _make_sample_json(hour: int = 10, trend: str = "uptrend") -> dict:
    """สร้าง mock JSON payload ที่ build_feature_dataset คาดหวัง"""
    return {
        "meta": {"generated_at": f"2026-04-01T{hour:02d}:00:00+07:00"},
        "market_data": {
            "spot_price_usd": {"price_usd_per_oz": 2350.50},
            "forex": {"usd_thb": 34.50},
            "thai_gold_thb": {"sell_price_thb": 45200},
        },
        "technical_indicators": {
            "rsi": {"value": 55.0},
            "macd": {"histogram": 2.3},
            "bollinger": {"pct_b": 0.65, "bandwidth": 0.04},
            "atr": {"value": 15.5},
            "trend": {"trend": trend, "ema_20": 2340.0, "sma_200": 2300.0},
        },
        "news": {
            "by_category": {
                "thai_gold_market": {
                    "articles": [
                        {"sentiment_score": 0.5},
                        {"sentiment_score": -0.2},
                    ]
                },
                "gold_price": {
                    "articles": [{"sentiment_score": 0.8}]
                },
                "geopolitics": {"articles": []},
                "dollar_index": {"articles": []},
                "fed_policy": {"articles": []},
            }
        },
    }


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ══════════════════════════════════════════════════════════════════
# 1. build_feature_dataset — สร้าง features สำเร็จ
# ══════════════════════════════════════════════════════════════════


class TestBuildFeatureDataset:
    """ทดสอบ build_feature_dataset() end-to-end"""

    def test_creates_csv(self, tmp_path):
        """สร้างไฟล์ CSV สำเร็จ"""
        json_path = str(tmp_path / "test.json")
        csv_path = str(tmp_path / "features.csv")
        _write_json(json_path, _make_sample_json())
        build_feature_dataset(json_path, csv_path)
        assert os.path.exists(csv_path)

    def test_csv_has_correct_columns(self, tmp_path):
        """CSV มี columns ที่คาดหวัง"""
        json_path = str(tmp_path / "test.json")
        csv_path = str(tmp_path / "features.csv")
        _write_json(json_path, _make_sample_json())
        build_feature_dataset(json_path, csv_path)
        df = pd.read_csv(csv_path)
        expected_cols = [
            "datetime", "hour", "day_of_week",
            "spot_price", "usd_thb", "thai_gold_sell",
            "rsi", "macd_hist", "atr",
            "trend_encoded", "ema_20", "sma_200",
        ]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_csv_append_mode(self, tmp_path):
        """เรียก 2 ครั้ง → CSV มี 2 rows"""
        json_path = str(tmp_path / "test.json")
        csv_path = str(tmp_path / "features.csv")
        _write_json(json_path, _make_sample_json(hour=10))
        build_feature_dataset(json_path, csv_path)
        _write_json(json_path, _make_sample_json(hour=14))
        build_feature_dataset(json_path, csv_path)
        df = pd.read_csv(csv_path)
        assert len(df) == 2

    def test_missing_json_returns_none(self, tmp_path, capsys):
        """JSON ไม่มี → ไม่สร้าง CSV, print error"""
        csv_path = str(tmp_path / "features.csv")
        build_feature_dataset(str(tmp_path / "nonexistent.json"), csv_path)
        assert not os.path.exists(csv_path)

    def test_creates_parent_dir(self, tmp_path):
        """สร้าง directory อัตโนมัติถ้าไม่มี"""
        json_path = str(tmp_path / "test.json")
        csv_path = str(tmp_path / "deep" / "nested" / "features.csv")
        _write_json(json_path, _make_sample_json())
        build_feature_dataset(json_path, csv_path)
        assert os.path.exists(csv_path)


# ══════════════════════════════════════════════════════════════════
# 2. Time features — session encoding
# ══════════════════════════════════════════════════════════════════


class TestTimeFeatures:
    """ทดสอบ trading session encoding"""

    def _get_features(self, tmp_path, hour: int) -> pd.Series:
        json_path = str(tmp_path / "test.json")
        csv_path = str(tmp_path / "features.csv")
        _write_json(json_path, _make_sample_json(hour=hour))
        build_feature_dataset(json_path, csv_path)
        return pd.read_csv(csv_path).iloc[0]

    def test_asian_session(self, tmp_path):
        """hour=10 → Asian session (07-15)"""
        row = self._get_features(tmp_path, hour=10)
        assert row["is_asian_session"] == 1
        assert row["is_london_session"] == 0

    def test_london_session(self, tmp_path):
        """hour=16 → London session (15-23)"""
        row = self._get_features(tmp_path, hour=16)
        assert row["is_london_session"] == 1
        assert row["is_asian_session"] == 0

    def test_ny_session(self, tmp_path):
        """hour=21 → NY session (20-04)"""
        row = self._get_features(tmp_path, hour=21)
        assert row["is_ny_session"] == 1

    def test_ny_session_overlap(self, tmp_path):
        """hour=21 → ทั้ง London + NY (overlap zone)"""
        row = self._get_features(tmp_path, hour=21)
        assert row["is_london_session"] == 1
        assert row["is_ny_session"] == 1


# ══════════════════════════════════════════════════════════════════
# 3. Trend mapping
# ══════════════════════════════════════════════════════════════════


class TestTrendMapping:
    """ทดสอบ trend_encoded mapping"""

    def _get_trend(self, tmp_path, trend: str) -> int:
        json_path = str(tmp_path / "test.json")
        csv_path = str(tmp_path / "features.csv")
        _write_json(json_path, _make_sample_json(trend=trend))
        build_feature_dataset(json_path, csv_path)
        return int(pd.read_csv(csv_path).iloc[0]["trend_encoded"])

    def test_uptrend(self, tmp_path):
        assert self._get_trend(tmp_path, "uptrend") == 1

    def test_downtrend(self, tmp_path):
        assert self._get_trend(tmp_path, "downtrend") == -1

    def test_sideways(self, tmp_path):
        assert self._get_trend(tmp_path, "sideways") == 0

    def test_unknown_defaults_zero(self, tmp_path):
        """trend ที่ไม่รู้จัก → 0"""
        assert self._get_trend(tmp_path, "unknown_trend") == 0


# ══════════════════════════════════════════════════════════════════
# 4. Sentiment features
# ══════════════════════════════════════════════════════════════════


class TestSentimentFeatures:
    """ทดสอบ sentiment feature extraction"""

    def test_sentiment_average(self, tmp_path):
        """เฉลี่ย sentiment ถูกต้อง"""
        json_path = str(tmp_path / "test.json")
        csv_path = str(tmp_path / "features.csv")
        _write_json(json_path, _make_sample_json())
        build_feature_dataset(json_path, csv_path)
        df = pd.read_csv(csv_path)
        # thai_gold_market: (0.5 + -0.2) / 2 = 0.15
        assert abs(df.iloc[0]["sentiment_thai_gold_market"] - 0.15) < 0.01
        # gold_price: 0.8 / 1 = 0.8
        assert abs(df.iloc[0]["sentiment_gold_price"] - 0.8) < 0.01

    def test_empty_category_sentiment_zero(self, tmp_path):
        """ไม่มีข่าวใน category → sentiment = 0"""
        json_path = str(tmp_path / "test.json")
        csv_path = str(tmp_path / "features.csv")
        _write_json(json_path, _make_sample_json())
        build_feature_dataset(json_path, csv_path)
        df = pd.read_csv(csv_path)
        assert df.iloc[0]["sentiment_geopolitics"] == 0.0
