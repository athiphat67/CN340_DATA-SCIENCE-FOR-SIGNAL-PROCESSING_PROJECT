# Skill: macro_news

## Trigger Conditions
Load and call this skill **only** when the agent's current state is missing
news context, i.e. when the ReAct loop emits:

```
Action: get_macro_news("<query>")
```

Do **not** call this skill on every cycle — only when the Thought step
determines that news sentiment is needed to reach a confident decision.

---

## Purpose
Retrieve recent macro-economic and geopolitical headlines that affect gold
prices, then summarise their directional impact (Bullish / Bearish / Neutral)
for the LLM to incorporate into its final trade decision.

---

## Instructions for the Agent

1. **When to call**  
   Call `get_macro_news(topic)` if ANY of the following is true:  
   - No news data is present in the current market state.  
   - RSI and MACD give conflicting signals (one bullish, one bearish).  
   - Unusual ATR spike suggests an unpriced macro event.

2. **How to call**  
   ```
   Action: get_macro_news("gold Fed rate cut inflation 2025")
   ```
   Keep the query concise (5–10 words). Focus on: Fed, inflation, DXY,
   geopolitics, central bank buying.

3. **How to interpret the Observation**  
   | Keyword in headline          | Gold impact |
   |------------------------------|-------------|
   | rate cut / dovish / QE       | Bullish ↑   |
   | rate hike / hawkish / strong dollar | Bearish ↓ |
   | war / tension / sanctions    | Bullish ↑   |
   | ceasefire / deal / calm      | Bearish ↓   |
   | recession / risk-off         | Bullish ↑   |
   | strong jobs / GDP beat       | Bearish ↓   |

4. **After the Observation**  
   Write a one-sentence sentiment summary, then proceed to the final
   JSON decision. Example:
   ```
   Thought: News is bullish (Fed dovish + Middle East risk). Combined with
            RSI oversold, I will BUY.
   {"action": "BUY", "quantity": 3, "reasoning": "..."}
   ```

---

## Output Contract
`get_macro_news(topic: str) -> str`  
Returns a plain-text summary of the top headlines and their estimated
directional impact on gold. No JSON — the agent interprets the text.
