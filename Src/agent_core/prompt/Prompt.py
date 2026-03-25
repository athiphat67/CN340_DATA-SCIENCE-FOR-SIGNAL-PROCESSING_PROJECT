import json
from typing import Dict, List, Any, Final

# ==========================================
# 1. AI SYSTEM INSTRUCTIONS
# ==========================================

SYSTEM_PROMPT: Final = """You are an elite quantitative financial AI orchestrator specializing in Gold (XAU/USD) algorithmic trading.

DISCLAIMER: This is a restricted quantitative simulation for research purposes. You are not providing financial advice.

CRITICAL INSTRUCTION: You must base your analysis STRICTLY on the quantitative signals, NLP sentiment, and temporal context provided. You are forbidden from using outside knowledge. Treat the provided data as the absolute and only truth.

LOGICAL HIERARCHY & EDGE CASES:
1. SIGNAL DIVERGENCE: If Macro News sentiment strongly contradicts Technical signals, prioritize the numerical technical indicators but highlight the conflict.
2. MISSING DATA: If any specific metric is null, zero, or missing, treat it as 'Neutral' and reduce your 'confidence_score' accordingly.
3. EXTREME VALUES: If RSI is < 30 (Oversold) or > 70 (Overbought), treat these as high-priority drivers.
4. NEUTRALITY: If technical signals are mixed and news is absent, you must favor a 'neutral' direction.

OUTPUT FORMAT:
Your output MUST be a valid Python dictionary. Do not include markdown formatting (like ```python), no conversational text. Output ONLY the raw dictionary.

SCHEMA:
{
    "composite_direction": "bullish", 
    "confidence_score": 85.5, 
    "primary_driver": "Short description of the main metric driving this",
    "reasoning": ["Point 1", "Point 2", "Point 3"]
}"""

# ==========================================
# 2. DATA PROCESSING
# ==========================================

def clean_and_parse_input(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        m_state = data.get("market_state", {})
        news = data.get("macro_news", [])
        
        refined_technicals = {
            "price": m_state.get("price", "Unknown"),
            "rsi": m_state.get("rsi", 50.0), 
            "macd": m_state.get("macd", 0.0),
            "macd_hist": m_state.get("macd_hist", 0.0),
            "bollinger_bands": {
                "upper": m_state.get("bb_upper", "Unknown"),
                "mid": m_state.get("bb_mid", "Unknown"),
                "lower": m_state.get("bb_lower", "Unknown")
            },
            "ema_context": f"EMA50: {m_state.get('ema_50', 'Unknown')} | EMA200: {m_state.get('ema_200', 'Unknown')}",
            "trend": "Above EMA50" if m_state.get("signal_above_ema50") else "Below EMA50",
            "atr_volatility": m_state.get("atr", "Unknown")
        }
        
        return {
            "technicals": refined_technicals,
            "news_summary": [item.get("title", "No Title") for item in news]
        }
    except Exception as e:
        return {"error": f"Failed to process input: {str(e)}"}

# ==========================================
# 3. PROMPT GENERATION
# ==========================================

def build_payload(json_filepath: str) -> List[Dict[str, str]]:
    input_data = clean_and_parse_input(json_filepath)
    
    if "error" in input_data:
        user_content = f"ERROR: The input file is corrupted or missing: {input_data['error']}"
    else:
        user_content = f"""
### DATA SNAPSHOT
* Technicals: {json.dumps(input_data['technicals'], indent=2)}
* Recent News: {json.dumps(input_data['news_summary'], indent=2)}

Analyze the convergence of these signals and provide the prediction dictionary."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]