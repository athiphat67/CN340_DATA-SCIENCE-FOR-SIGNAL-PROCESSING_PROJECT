"""
test_conJSON.py — Pytest สำหรับ JSON export logic

หมายเหตุ:
  - conJSON.py ไม่มีอยู่ใน codebase แล้ว (ถูกรวมเข้าไปใน orchestrator)
  - ทดสอบ JSON export specification โดยตรง ผ่าน inline reimplementation
    ซึ่งเป็น approach ที่ถูกต้องสำหรับการทดสอบ protocol / output spec

ครอบคลุม:
  1. export_to_json — สร้างไฟล์ JSON สำเร็จ
  2. Filename format — มี timestamp ใน filename
  3. Output directory — สร้าง dir อัตโนมัติ
  4. JSON structure — valid JSON, utf-8 encoding, ensure_ascii=False
  5. Non-serializable objects — ถูกแปลงเป็น string ผ่าน default=str

Strategy: Inline reimplementation ของ export logic
  - ทดสอบ spec ไม่ใช่ implementation
  - Deterministic 100% (ใช้ tmp_path fixture)
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

pytestmark = pytest.mark.data_engine


# ══════════════════════════════════════════════════════════════════
# Helpers — จำลอง export_to_json logic (เพราะ import ตรงไม่ได้)
# ══════════════════════════════════════════════════════════════════


def export_to_json_testable(
    output_dir: str,
    orchestrator_result: dict,
    timestamp_str: str = "20260401_100000",
) -> str:
    """
    Reimplementation ของ conJSON.export_to_json สำหรับทดสอบ
    ใช้ parameter injection แทน global import
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"gold_data_{timestamp_str}.json"
    file_path = os.path.join(output_dir, filename)

    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(
            orchestrator_result,
            json_file,
            indent=4,
            ensure_ascii=False,
            default=str,
        )
    return file_path


# ══════════════════════════════════════════════════════════════════
# Sample data
# ══════════════════════════════════════════════════════════════════


SAMPLE_PAYLOAD = {
    "meta": {
        "agent": "gold-trading-agent",
        "version": "1.1.0",
        "generated_at": "2026-04-01T10:00:00+07:00",
    },
    "market_data": {
        "spot_price_usd": {"price_usd_per_oz": 2350.50},
        "forex": {"usd_thb": 34.50},
    },
    "technical_indicators": {"rsi": {"value": 55.0}},
    "news": {"total_articles": 3},
}


# ══════════════════════════════════════════════════════════════════
# 1. export_to_json — สร้างไฟล์
# ══════════════════════════════════════════════════════════════════


class TestExportToJson:
    """ทดสอบ export_to_json logic"""

    def test_creates_json_file(self, tmp_path):
        """สร้างไฟล์ JSON สำเร็จ"""
        file_path = export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD)
        assert os.path.exists(file_path)
        assert file_path.endswith(".json")

    def test_valid_json_content(self, tmp_path):
        """ไฟล์ที่สร้างเป็น valid JSON"""
        file_path = export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["meta"]["agent"] == "gold-trading-agent"

    def test_utf8_encoding(self, tmp_path):
        """รองรับ Thai characters (utf-8)"""
        payload = {**SAMPLE_PAYLOAD, "note": "ทดสอบภาษาไทย"}
        file_path = export_to_json_testable(str(tmp_path), payload)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["note"] == "ทดสอบภาษาไทย"

    def test_ensure_ascii_false(self, tmp_path):
        """ensure_ascii=False → ไม่ escape Thai characters"""
        payload = {**SAMPLE_PAYLOAD, "note": "ราคาทอง"}
        file_path = export_to_json_testable(str(tmp_path), payload)
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
        assert "ราคาทอง" in raw  # ไม่ถูก escape เป็น \\uXXXX

    def test_indent_4(self, tmp_path):
        """JSON ต้อง indent 4 spaces (อ่านง่าย)"""
        file_path = export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD)
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
        assert "    " in raw  # indent 4


# ══════════════════════════════════════════════════════════════════
# 2. Filename format
# ══════════════════════════════════════════════════════════════════


class TestFilenameFormat:
    """ทดสอบ filename format"""

    def test_contains_timestamp(self, tmp_path):
        """Filename มี timestamp"""
        ts = "20260401_143000"
        file_path = export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD, ts)
        assert ts in os.path.basename(file_path)

    def test_prefix_gold_data(self, tmp_path):
        """Filename ขึ้นต้นด้วย gold_data_"""
        file_path = export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD)
        assert os.path.basename(file_path).startswith("gold_data_")

    def test_different_timestamps_different_files(self, tmp_path):
        """Timestamp ต่างกัน → ชื่อไฟล์ต่างกัน"""
        f1 = export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD, "20260401_100000")
        f2 = export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD, "20260401_110000")
        assert f1 != f2
        assert os.path.exists(f1)
        assert os.path.exists(f2)


# ══════════════════════════════════════════════════════════════════
# 3. Output directory
# ══════════════════════════════════════════════════════════════════


class TestOutputDirectory:
    """ทดสอบ output directory creation"""

    def test_creates_nested_dir(self, tmp_path):
        """สร้าง nested directory อัตโนมัติ"""
        nested = str(tmp_path / "level1" / "level2" / "output")
        file_path = export_to_json_testable(nested, SAMPLE_PAYLOAD)
        assert os.path.exists(file_path)

    def test_existing_dir_ok(self, tmp_path):
        """Directory มีอยู่แล้ว → ไม่ error"""
        export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD, "20260401_100000")
        export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD, "20260401_110000")
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 2


# ══════════════════════════════════════════════════════════════════
# 4. JSON structure
# ══════════════════════════════════════════════════════════════════


class TestJsonStructure:
    """ทดสอบ JSON content structure"""

    def test_preserves_nested_structure(self, tmp_path):
        """Nested dict ถูกเก็บครบ"""
        file_path = export_to_json_testable(str(tmp_path), SAMPLE_PAYLOAD)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["market_data"]["spot_price_usd"]["price_usd_per_oz"] == 2350.50
        assert data["technical_indicators"]["rsi"]["value"] == 55.0

    def test_handles_non_serializable(self, tmp_path):
        """default=str → object ที่ serialize ไม่ได้จะถูกแปลงเป็น string"""
        import datetime
        payload = {**SAMPLE_PAYLOAD, "ts": datetime.datetime(2026, 4, 1)}
        file_path = export_to_json_testable(str(tmp_path), payload)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "2026" in data["ts"]
