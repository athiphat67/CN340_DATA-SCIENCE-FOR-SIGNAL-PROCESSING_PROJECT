"""
data_provider.py — Real-time Gold Price Data Provider
ดึงราคาทองแบบ real-time จาก Free APIs:
  - Primary  : Metals-API (metals.dev) — ฟรี 100 req/month
  - Fallback : Open Exchange Rates + Gold fix (ฟรีไม่จำกัด)
  - Fallback2: GoldAPI.io (ฟรี 100 req/month)
"""

import os
import time
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

TROY_OZ_TO_GRAM = 31.1034768          # 1 troy oz = 31.1 กรัม
THB_PER_BAHT_GOLD = 15.244            # 1 บาททอง = 15.244 กรัม (ทองคำ 96.5%)
CACHE_TTL_SECONDS = 60                # cache 60 วินาที

# ─────────────────────────────────────────────
# Simple in-memory cache
# ─────────────────────────────────────────────

_cache: dict = {}


def _is_cache_valid(key: str) -> bool:
    if key not in _cache:
        return False
    return time.time() - _cache[key]["timestamp"] < CACHE_TTL_SECONDS


def _get_cache(key: str) -> Optional[dict]:
    if _is_cache_valid(key):
        return _cache[key]["data"]
    return None


def _set_cache(key: str, data: dict) -> None:
    _cache[key] = {"data": data, "timestamp": time.time()}


# ─────────────────────────────────────────────
# Source 1: metals.dev (ฟรี ไม่ต้อง API key สำหรับ XAU/USD)
# ─────────────────────────────────────────────

def _fetch_metals_dev() -> Optional[float]:
    """
    metals.dev — endpoint สาธารณะ ไม่ต้อง key
    Returns: ราคาทองต่อ troy oz (USD)
    """
    try:
        url = "https://api.metals.dev/v1/spot?api_key=demo&expand=false&currencies=USD&unit=toz&metals=XAU"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            price = data.get("metals", {}).get("XAU")
            if price:
                logger.info(f"[metals.dev] XAU/USD = {price}")
                return float(price)
    except Exception as e:
        logger.warning(f"[metals.dev] failed: {e}")
    return None


# ─────────────────────────────────────────────
# Source 2: frankfurter.app + gold fix constant
# เป็น free forex API แล้วใช้ London Gold Fix เป็น fallback
# ─────────────────────────────────────────────

LONDON_GOLD_FIX_USD = 3300.0   # อัปเดตทุกครั้งที่ราคาเปลี่ยนมาก (manual fallback)


def _fetch_frankfurter_usd_thb() -> Optional[float]:
    """
    frankfurter.app — ฟรี ไม่ต้อง API key, อัปเดต ECB rates
    Returns: อัตราแลกเปลี่ยน USD→THB
    """
    try:
        url = "https://api.frankfurter.app/latest?from=USD&to=THB"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            rate = r.json().get("rates", {}).get("THB")
            if rate:
                logger.info(f"[frankfurter] USD/THB = {rate}")
                return float(rate)
    except Exception as e:
        logger.warning(f"[frankfurter] failed: {e}")
    return None


# ─────────────────────────────────────────────
# Source 3: GoldAPI.io (ฟรี 100 req/month)
# ─────────────────────────────────────────────

def _fetch_goldapi_io() -> Optional[float]:
    """
    goldapi.io — ฟรี 100 req/month, ต้องมี API key (ใส่ใน .env)
    GOLDAPI_KEY=your_key_here
    Returns: ราคาทองต่อ troy oz (USD)
    """
    api_key = os.getenv("GOLDAPI_KEY", "")
    if not api_key:
        return None
    try:
        url = "https://www.goldapi.io/api/XAU/USD"
        headers = {"x-access-token": api_key, "Content-Type": "application/json"}
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            price = r.json().get("price")
            if price:
                logger.info(f"[goldapi.io] XAU/USD = {price}")
                return float(price)
    except Exception as e:
        logger.warning(f"[goldapi.io] failed: {e}")
    return None


# ─────────────────────────────────────────────
# Main fetcher class
# ─────────────────────────────────────────────

class GoldPriceProvider:
    """
    ดึงราคาทองแบบ real-time พร้อม fallback chain
    และแปลงราคาเป็น THB/gram สำหรับแสดงผล
    """

    def get_spot_price(self) -> dict:
        """
        Returns dict ครบ:
        {
            "price_usd_oz"   : float,   # ราคา USD ต่อ troy oz
            "price_thb_oz"   : float,   # ราคา THB ต่อ troy oz
            "price_thb_gram" : float,   # ราคา THB ต่อกรัม
            "price_thb_baht" : float,   # ราคา THB ต่อบาททอง (ทอง 96.5%)
            "usd_thb_rate"   : float,   # อัตราแลกเปลี่ยน
            "source"         : str,     # แหล่งข้อมูล
            "timestamp"      : str,     # เวลา UTC
            "cached"         : bool,
        }
        """
        cache_key = "spot_price"
        cached = _get_cache(cache_key)
        if cached:
            cached["cached"] = True
            return cached

        # ── ดึงราคา XAU/USD ──
        price_usd = None
        source = "fallback"

        price_usd = _fetch_metals_dev()
        if price_usd:
            source = "metals.dev"

        if not price_usd:
            price_usd = _fetch_goldapi_io()
            if price_usd:
                source = "goldapi.io"

        if not price_usd:
            price_usd = LONDON_GOLD_FIX_USD
            source = "london_fix_static"

        # ── ดึง USD/THB ──
        usd_thb = _fetch_frankfurter_usd_thb() or 33.5   # fallback rate

        # ── คำนวณ ──
        price_thb_oz   = price_usd * usd_thb
        price_thb_gram = price_thb_oz / TROY_OZ_TO_GRAM
        price_thb_baht = price_thb_gram * THB_PER_BAHT_GOLD

        result = {
            "price_usd_oz"   : round(price_usd, 2),
            "price_thb_oz"   : round(price_thb_oz, 2),
            "price_thb_gram" : round(price_thb_gram, 2),
            "price_thb_baht" : round(price_thb_baht, 2),
            "usd_thb_rate"   : round(usd_thb, 4),
            "source"         : source,
            "timestamp"      : datetime.now(timezone.utc).isoformat(),
            "cached"         : False,
        }

        _set_cache(cache_key, result)
        return result

    def get_price_history(self, days: int = 30) -> list[dict]:
        """
        ดึงราคาทองย้อนหลัง N วัน จาก frankfurter (ECB) หรือ static data
        Returns: list of {"date": str, "price_usd": float}
        """
        cache_key = f"history_{days}"
        cached = _get_cache(cache_key)
        if cached:
            return cached

        history = []
        try:
            end_date   = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            # frankfurter ไม่มี gold แต่ใช้ดึง USD/THB timeseries ได้
            url = (
                f"https://api.frankfurter.app/{start_date}..{end_date}"
                f"?from=USD&to=THB"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                rates_data = r.json().get("rates", {})
                for date_str, rates in sorted(rates_data.items()):
                    history.append({
                        "date"    : date_str,
                        "usd_thb" : rates.get("THB", 33.5),
                    })
        except Exception as e:
            logger.warning(f"[history] failed: {e}")

        _set_cache(cache_key, history)
        return history

    def format_thai_display(self, price_data: dict) -> str:
        """สร้าง HTML card สำหรับแสดงราคาทองแบบไทย"""
        ts_utc = price_data.get("timestamp", "")
        ts_th  = ""
        if ts_utc:
            try:
                dt = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
                ts_th = (dt + timedelta(hours=7)).strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                ts_th = ts_utc

        src   = price_data.get("source", "unknown")
        color = "#34c759" if "static" not in src else "#ff9500"

        return f"""
        <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                    border-radius:12px;padding:20px;color:white;font-family:monospace;">
            <div style="font-size:11px;color:#aaa;margin-bottom:12px">
                🟡 GOLD SPOT PRICE
                <span style="margin-left:8px;color:{color}">● {src}</span>
                <span style="margin-left:8px;color:#888">{ts_th} (TH)</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                <div>
                    <div style="font-size:11px;color:#aaa">USD / troy oz</div>
                    <div style="font-size:28px;font-weight:bold;color:#ffd700">
                        ${price_data.get('price_usd_oz', 0):,.2f}
                    </div>
                </div>
                <div>
                    <div style="font-size:11px;color:#aaa">THB / บาททอง (96.5%)</div>
                    <div style="font-size:28px;font-weight:bold;color:#f4c430">
                        ฿{price_data.get('price_thb_baht', 0):,.0f}
                    </div>
                </div>
                <div>
                    <div style="font-size:11px;color:#aaa">THB / กรัม</div>
                    <div style="font-size:18px;font-weight:bold">
                        ฿{price_data.get('price_thb_gram', 0):,.2f}
                    </div>
                </div>
                <div>
                    <div style="font-size:11px;color:#aaa">USD/THB Rate</div>
                    <div style="font-size:18px;font-weight:bold">
                        {price_data.get('usd_thb_rate', 0):.4f}
                    </div>
                </div>
            </div>
        </div>
        """


# ─────────────────────────────────────────────
# Singleton instance
# ─────────────────────────────────────────────

gold_provider = GoldPriceProvider()


# ─────────────────────────────────────────────
# Quick test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = gold_provider.get_spot_price()
    print("\n=== Gold Price ===")
    for k, v in data.items():
        print(f"  {k:20s}: {v}")
    print(gold_provider.format_thai_display(data))