import sys
import ast
import time
import os

# 1. Add the prompt folder to Python's path so we can import from it
sys.path.append(os.path.join(os.path.dirname(__file__), "prompt"))

try:
    from Prompt import build_payload
except ImportError:
    print("CRITICAL ERROR: Could not find 'prompt/Prompt.py'. Make sure this script is in the agent_core folder.")
    sys.exit(1)

# ==========================================
# MOCK AI & FORMATTING UTILITIES
# ==========================================

def mock_ai_agent(payload: list) -> str:
    """Simulates an AI agent responding with some markdown pollution."""
    return """```python
{
    'composite_direction': 'bullish', 
    'confidence_score': 78.5, 
    'primary_driver': 'MACD histogram crossing above zero combined with cooling inflation news.', 
    'reasoning': [
        'RSI is neutral at 44.74, leaving room for upside.', 
        'Price is holding above the Bollinger Band lower threshold.', 
        'News sentiment strongly supports safe-haven demand.'
    ]
}
```"""

def extract_dict_from_response(response_text: str) -> dict:
    """Cleans common AI formatting 'pollution' before parsing."""
    clean_text = response_text.replace("```python", "").replace("```json", "").replace("```", "").strip()
    
    start = clean_text.find("{")
    end = clean_text.rfind("}") + 1
    
    if start == -1 or end == 0:
        raise ValueError("No valid dictionary structure found in agent response.")
        
    return ast.literal_eval(clean_text[start:end])

# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    # Get the file path from the terminal command
    target_file = sys.argv[1] if len(sys.argv) > 1 else "Input/mock_state.json"
    
    print("\n[1/4] Starting Output Receiver...")
    print(f"[2/4] Instructing Prompt.py to process: {target_file}")
    
    # Use Prompt.py to build the payload
    payload = build_payload(target_file)
    
    print("[3/4] Transmitting payload to AI Agent (Mocking)...")
    time.sleep(1) # Simulating API latency
    raw_ai_response = mock_ai_agent(payload)
    
    print("[4/4] Formatting Output...")
    try:
        # Clean and parse the string into a real dictionary
        prediction = extract_dict_from_response(raw_ai_response)
        
        # --- THE FORMATTED DASHBOARD ---
        print("\n" + "="*50)
        print(" 🤖 AGENT CORE: PREDICTION RESULTS ".center(50, "="))
        print("="*50)
        print(f"📈 DIRECTION:   {prediction.get('composite_direction', 'UNKNOWN').upper()}")
        print(f"🎯 CONFIDENCE:  {prediction.get('confidence_score', 0.0)}%")
        print(f"🔑 DRIVER:      {prediction.get('primary_driver', 'None')}")
        print("-" * 50)
        print("🧠 REASONING:")
        for i, point in enumerate(prediction.get('reasoning', []), 1):
            print(f"   {i}. {point}")
        print("="*50 + "\n")
            
    except Exception as e:
        print(f"\n❌ CRITICAL PIPELINE FAILURE: {e}")