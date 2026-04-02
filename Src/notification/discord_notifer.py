"""
notification/discord_notifier.py
GoldTrader v3.3 — Discord Webhook Notification

Sends formatted trading signal alerts to Discord before DB save.
Supports per-interval results + weighted voting summary.

Toggle via .env:
    DISCORD_NOTIFY_ENABLED=true
    DISCORD_NOTIFY_HOLD=true     ← เปิด/ปิด HOLD notifications
"""

import os
import httpx
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Signal config
# ─────────────────────────────────────────────

_SIGNAL_EMOJI = {
    "BUY":  "🟢",
    "SELL": "🔴",
    "HOLD": "🟡",
}

_SIGNAL_COLOR = {
    "BUY":  0x1D9E75,   # teal green
    "SELL": 0xD85A30,   # coral red
    "HOLD": 0x888780,   # gray
}

_CONFIDENCE_BAR_FILLED   = "█"
_CONFIDENCE_BAR_EMPTY    = "░"
_CONFIDENCE_BAR_LENGTH   = 10


def _confidence_bar(confidence: float) -> str:
    """Render a simple text progress bar for confidence level"""
    filled = round(confidence * _CONFIDENCE_BAR_LENGTH)
    bar    = _CONFIDENCE_BAR_FILLED * filled + _CONFIDENCE_BAR_EMPTY * (_CONFIDENCE_BAR_LENGTH - filled)
    return f"`{bar}` {confidence:.0%}"


def _fmt_price(value, fallback: str = "N/A") -> str:
    """Format price with comma separator"""
    if value is None:
        return fallback
    try:
        return f"฿{float(value):,.0f}"
    except (ValueError, TypeError):
        return fallback


def _fmt_usd(value, fallback: str = "N/A") -> str:
    """Format USD price"""
    if value is None:
        return fallback
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return fallback


# ─────────────────────────────────────────────
# Embed Builder
# ─────────────────────────────────────────────

def build_embed(
    voting_result:    dict,
    interval_results: dict,
    market_state:     dict,
    provider:         str,
    period:           str,
    run_id:           Optional[int] = None,
) -> dict:
    """
    Build a Discord Rich Embed from analysis result.

    Field layout:
      Row 1: Signal | Confidence
      Row 2: Entry  | Stop Loss | Take Profit
      Row 3: Provider | Intervals | Run ID
      ---
      Per-interval breakdown (inline)
      ---
      Rationale (full width)
    """
    final_signal = voting_result.get("final_signal", "HOLD")
    confidence   = voting_result.get("weighted_confidence", 0.0)
    emoji        = _SIGNAL_EMOJI.get(final_signal, "⚪")
    color        = _SIGNAL_COLOR.get(final_signal, 0x888780)

    # Best interval — highest confidence
    best_iv = max(interval_results.items(), key=lambda x: x[1].get("confidence", 0))[0]
    best    = interval_results[best_iv]

    # Market prices
    md        = market_state.get("market_data", {})
    sell_thb  = md.get("thai_gold_thb", {}).get("sell_price_thb")
    buy_thb   = md.get("thai_gold_thb", {}).get("buy_price_thb")
    usd_thb   = md.get("forex", {}).get("usd_thb", 0)
    spot_usd  = md.get("spot_price_usd", {}).get("price_usd_per_oz")
    spot_conf = md.get("spot_price_usd", {}).get("confidence", 1.0)

    # Data quality warning
    quality       = market_state.get("data_quality", {}).get("quality_score", "good")
    quality_badge = "⚠️ Degraded data" if quality == "degraded" else "✅ Good data"

    # Timestamp (Bangkok UTC+7)
    now_utc = datetime.now(timezone.utc)
    ts_iso  = now_utc.isoformat()

    # ── Fields ──────────────────────────────────────────────────────────────

    fields = []

    # Row 1: Signal + Confidence
    fields.append({
        "name":   "Signal",
        "value":  f"{emoji} **{final_signal}**",
        "inline": True,
    })
    fields.append({
        "name":   "Confidence",
        "value":  _confidence_bar(confidence),
        "inline": True,
    })
    fields.append({"name": "\u200b", "value": "\u200b", "inline": True})  # spacer

    # Row 2: Price levels (from best interval)
    entry    = best.get("entry_price")
    sl       = best.get("stop_loss")
    tp       = best.get("take_profit")

    fields.append({
        "name":   "Entry",
        "value":  _fmt_price(entry),
        "inline": True,
    })
    fields.append({
        "name":   "Stop Loss",
        "value":  _fmt_price(sl),
        "inline": True,
    })
    fields.append({
        "name":   "Take Profit",
        "value":  _fmt_price(tp),
        "inline": True,
    })

    # Row 3: Market reference prices
    if sell_thb or buy_thb:
        fields.append({
            "name":   "ออม NOW (Sell)",
            "value":  _fmt_price(sell_thb),
            "inline": True,
        })
        fields.append({
            "name":   "ออม NOW (Buy)",
            "value":  _fmt_price(buy_thb),
            "inline": True,
        })
        usd_str = f"{usd_thb:.2f}" if usd_thb else "N/A"
        fields.append({
            "name":   "USD/THB",
            "value":  f"`{usd_str}`",
            "inline": True,
        })

    # Row 4: Spot price + data quality
    if spot_usd:
        fields.append({
            "name":   "Spot (XAU/USD)",
            "value":  _fmt_usd(spot_usd) + (f" _(conf {spot_conf:.0%})_" if spot_conf < 0.95 else ""),
            "inline": True,
        })
        fields.append({
            "name":   "Data Quality",
            "value":  quality_badge,
            "inline": True,
        })
        fields.append({"name": "\u200b", "value": "\u200b", "inline": True})

    # Per-interval breakdown
    if len(interval_results) > 1:
        breakdown_lines = []
        for iv, ir in sorted(interval_results.items()):
            iv_sig   = ir.get("signal", "HOLD")
            iv_conf  = ir.get("confidence", 0.0)
            iv_emoji = _SIGNAL_EMOJI.get(iv_sig, "⚪")
            is_best  = "◀" if iv == best_iv else ""
            breakdown_lines.append(
                f"`{iv:4s}` {iv_emoji} {iv_sig:4s} — {iv_conf:.0%} {is_best}"
            )
        fields.append({
            "name":   "📊 Per-Interval Breakdown",
            "value":  "\n".join(breakdown_lines),
            "inline": False,
        })

    # Voting breakdown
    vb = voting_result.get("voting_breakdown", {})
    if vb:
        vb_lines = []
        for sig in ["BUY", "SELL", "HOLD"]:
            data = vb.get(sig, {})
            if data.get("count", 0) > 0:
                vb_lines.append(
                    f"{_SIGNAL_EMOJI.get(sig,'⚪')} {sig}: "
                    f"{data['count']} vote(s) — "
                    f"weighted {data.get('weighted_score', 0):.3f}"
                )
        if vb_lines:
            fields.append({
                "name":   "🗳️ Voting Summary",
                "value":  "\n".join(vb_lines),
                "inline": False,
            })

    # Rationale (from best interval)
    rationale = best.get("rationale") or best.get("reasoning", "")
    if rationale:
        # Truncate to Discord limit (1024 chars per field)
        if len(rationale) > 900:
            rationale = rationale[:900] + "…"
        fields.append({
            "name":   "🧠 Rationale",
            "value":  rationale,
            "inline": False,
        })

    # Meta footer
    meta_parts = [f"Provider: `{provider}`", f"Period: `{period}`"]
    if run_id:
        meta_parts.append(f"Run ID: `#{run_id}`")
    fields.append({
        "name":   "ℹ️ Meta",
        "value":  " | ".join(meta_parts),
        "inline": False,
    })

    # ── Build embed ──────────────────────────────────────────────────────────

    return {
        "title":       f"{emoji} GoldTrader — {final_signal}",
        "description": f"Weighted confidence: **{confidence:.1%}** across {len(interval_results)} interval(s)",
        "color":       color,
        "fields":      fields,
        "footer":      {"text": "GoldTrader v3.3 | ออม NOW Platform"},
        "timestamp":   ts_iso,
    }


# ─────────────────────────────────────────────
# Notifier
# ─────────────────────────────────────────────

class DiscordNotifier:
    """
    Sends trading signal embeds to a Discord channel via Webhook.

    Config via environment variables:
        DISCORD_WEBHOOK_URL       required
        DISCORD_NOTIFY_ENABLED    true/false (default: true)
        DISCORD_NOTIFY_HOLD       true/false (default: true)
        DISCORD_NOTIFY_MIN_CONF   float 0-1  (default: 0.0 — send all)
    """

    def __init__(self):
        self.webhook_url  = os.environ.get("DISCORD_WEBHOOK_URL", "")
        self.enabled      = os.environ.get("DISCORD_NOTIFY_ENABLED", "true").lower() == "true"
        self.notify_hold  = os.environ.get("DISCORD_NOTIFY_HOLD", "true").lower() == "true"
        self.min_conf     = float(os.environ.get("DISCORD_NOTIFY_MIN_CONF", "0.0"))
        self._last_error: Optional[str] = None

    # ── Public API ───────────────────────────────────────────────────────────

    def notify(
        self,
        voting_result:    dict,
        interval_results: dict,
        market_state:     dict,
        provider:         str,
        period:           str,
        run_id:           Optional[int] = None,
    ) -> bool:
        """
        Send notification. Returns True if sent, False if skipped/failed.

        Called BEFORE DB save — run_id may be None at this point,
        pass it in after save if you want it in the embed.
        """
        # ── Guard: enabled? ──────────────────────────────────────────────────
        if not self.enabled:
            return False

        if not self.webhook_url:
            self._last_error = "DISCORD_WEBHOOK_URL not set"
            return False

        final_signal = voting_result.get("final_signal", "HOLD")
        confidence   = voting_result.get("weighted_confidence", 0.0)

        # ── Guard: HOLD filter ───────────────────────────────────────────────
        if final_signal == "HOLD" and not self.notify_hold:
            return False

        # ── Guard: confidence threshold ──────────────────────────────────────
        if confidence < self.min_conf:
            return False

        # ── Build + send ─────────────────────────────────────────────────────
        try:
            embed   = build_embed(
                voting_result=voting_result,
                interval_results=interval_results,
                market_state=market_state,
                provider=provider,
                period=period,
                run_id=run_id,
            )
            payload = {
                "username":   "GoldTrader 🟡",
                "avatar_url": "https://em-content.zobj.net/source/twitter/376/bar-chart_1f4ca.png",
                "embeds":     [embed],
            }
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            self._last_error = None
            return True

        except httpx.HTTPStatusError as e:
            self._last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            return False
        except Exception as e:
            self._last_error = str(e)
            return False

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def update_hold_toggle(self, enabled: bool):
        """Runtime toggle — called from Dashboard UI without restart"""
        self.notify_hold = enabled
        # Persist to env so it survives restart (best-effort)
        os.environ["DISCORD_NOTIFY_HOLD"] = "true" if enabled else "false"

    def update_enabled(self, enabled: bool):
        """Runtime toggle for entire notification system"""
        self.enabled = enabled
        os.environ["DISCORD_NOTIFY_ENABLED"] = "true" if enabled else "false"

    def status(self) -> dict:
        """Return current config status (for Dashboard display)"""
        return {
            "enabled":      self.enabled,
            "notify_hold":  self.notify_hold,
            "min_conf":     self.min_conf,
            "webhook_set":  bool(self.webhook_url),
            "last_error":   self._last_error,
        }