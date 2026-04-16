# engine/directive_builder.py

class DirectiveBuilder:
    @staticmethod
    def build_session_directive(portfolio, quota_ctx: dict) -> str:
        """สร้างข้อความ Prompt บังคับพฤติกรรม LLM ตามสถานะพอร์ตและโควตาเวลา"""
        
        # 1. ดึงข้อมูล Session
        session_id      = quota_ctx.get("session_id") or "DEAD"
        trades_done     = quota_ctx.get("trades_done", 0)
        min_trades      = quota_ctx.get("min_trades", 2)
        remaining       = quota_ctx.get("remaining_quota", 0)
        session_end     = quota_ctx.get("session_end_time", "")
        quota_urgent    = quota_ctx.get("quota_urgent", False)

        quota_line = (
            f"Session {session_id} | Trades: {trades_done}/{min_trades} | "
            f"Remaining quota: {remaining} | Session ends: {session_end}"
        )
        if quota_urgent:
            quota_line += f" ⚠ QUOTA URGENT — must complete {remaining} more trade(s) before {session_end}!"

        # 2. สร้างคำสั่งตามสถานะถือครองทอง (Portfolio State)
        if portfolio.gold_grams <= 1e-4:
            # กรณีไม่มีทอง (รอจังหวะซื้อ)
            min_conf = "0.65" if not quota_urgent else "0.55"
            directive = (
                f"{quota_line}\n"
                f"STATE: No gold held. You may BUY if technicals are bullish (confidence >= {min_conf}). "
                f"Otherwise HOLD. Do NOT SELL (no position to sell)."
            )
        else:
            # กรณีมีทอง (รอจังหวะขาย)
            tp_price = portfolio._open_trade.take_profit_price if getattr(portfolio, "_open_trade", None) else 0.0
            sl_price = portfolio._open_trade.stop_loss_price   if getattr(portfolio, "_open_trade", None) else 0.0
            directive = (
                f"{quota_line}\n"
                f"STATE: Holding gold. BUY is FORBIDDEN. Focus on SELL signal only. "
                f"TP={tp_price:,.0f} THB | SL={sl_price:,.0f} THB. "
                f"SELL if technicals break down, TP/SL hit, or session ending soon."
            )
            
        return directive