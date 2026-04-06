from playwright.sync_api import sync_playwright
import json
import csv
import os

# Configuration
csv_file = "gold_prices_dataset.csv"

# Professional Header Names
headers = [
    "timestamp", "bid_99", "ask_99", "bid_96", "ask_96", 
    "gold_spot", "fx_usd_thb", "assoc_bid", "assoc_ask"
]

# Initialize CSV with professional headers
if not os.path.exists(csv_file):
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)


def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    print("🚀 Opening browser to intercept WebSocket stream...")

    def on_websocket(ws):
        ws.on("framereceived", lambda payload: process_message(payload))

    def process_message(payload):
        if payload.startswith("42"):
            try:
                data_list = json.loads(payload[2:])
                event_name = data_list[0]

                if event_name == "updateGoldRateData":
                    gold = data_list[1]
                    t_stamp = gold.get("createDate", "Unknown")

                    # Extract Raw Data
                    bid_99 = gold.get("bidPrice99")
                    ask_99 = gold.get("offerPrice99")
                    bid_96 = gold.get("bidPrice96")
                    ask_96 = gold.get("offerPrice96")
                    spot = gold.get("AUXBuy")
                    fx = gold.get("usdBuy")
                    a_bid = gold.get("bidCentralPrice96")
                    a_ask = gold.get("offerCentralPrice96")

                    # Log to CSV
                    with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(
                            [
                                t_stamp,
                                bid_99,
                                ask_99,
                                bid_96,
                                ask_96,
                                spot,
                                fx,
                                a_bid,
                                a_ask,
                            ]
                        )

                    # Formatting for Display
                    def fmt(val):
                        return f"{val:,}" if isinstance(val, (int, float)) else "N/A"

                    # Professional English Console Output
                    print(
                        f"🌟 [99.99% LBMA] {t_stamp} | Buy: {fmt(bid_99)} | Sell: {fmt(ask_99)}"
                    )
                    print(
                        f"✅ [96.5% THAI]  {t_stamp} | Buy: {fmt(bid_96)} | Sell: {fmt(ask_96)}"
                    )
                    print(f"🏛️ [ASSOC.]       Buy: {fmt(a_bid)} | Sell: {fmt(a_ask)}")
                    print(
                        f"🌐 [GLOBAL]      Spot: {spot} | USD/THB: {fx} | [Status: Logged]"
                    )
                    print("-" * 75)

            except Exception:
                pass

    page.on("websocket", on_websocket)
    page.goto("https://www.intergold.co.th/curr-price/", wait_until="networkidle")

    print(f"📡 Intercepting live prices to {csv_file}... (Press Ctrl+C to stop)")

    try:
        page.wait_for_timeout(9999999)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down and closing browser...")
        browser.close()


with sync_playwright() as playwright:
    run(playwright)
