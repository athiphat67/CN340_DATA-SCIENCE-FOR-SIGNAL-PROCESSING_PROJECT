"""
backtest/prepare_backtest_data.py
เตรียมข้อมูลสำหรับ Walk-forward Validation Backtest

- โหลด XAUUSD และ USDTHB daily data
- Merge ตามวันที่
- คำนวณราคาทองคำไทย (THB per gram)
- สร้าง Walk-forward windows (ทดสอบช่วง เม.ย. ของแต่ละปี)

Usage (จาก Src/):
    python -m backtest.prepare_backtest_data
"""

import pandas as pd
import os
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
DATA_DIR = os.path.join(src_dir, "..", "Data", "Raw")

XAUUSD_CSV = os.path.join(DATA_DIR, "XAUUSD_Daily_200406110000_202512310000.csv")
USDTHB_CSV = os.path.join(DATA_DIR, "USDTHB_Daily_201106020000_202512310000.csv")

# ─── Gold conversion constants ───────────────────────────────────────────────
# 1 troy ounce = 31.1035 grams
# ราคาทอง THB/gram = (XAUUSD USD/oz) * (USDTHB THB/USD) / 31.1035 (g/oz)
GRAMS_PER_TROY_OZ = 31.1035


def load_and_merge() -> pd.DataFrame:
    """
    โหลด XAUUSD + USDTHB แล้ว merge ตามวันที่
    คำนวณราคาทอง THB/gram สำหรับแอปออม Now

    Returns
    -------
    pd.DataFrame
        columns: date, xau_open, xau_high, xau_low, xau_close,
                 usdthb, price_per_gram (THB)
    """
    # ── Load XAUUSD ──────────────────────────────────────────────────────
    xau = pd.read_csv(XAUUSD_CSV, sep="\t")
    xau.columns = [c.strip("<>").lower() for c in xau.columns]
    xau["date"] = pd.to_datetime(xau["date"], format="mixed")
    xau = xau[["date", "open", "high", "low", "close"]].copy()
    xau = xau.rename(
        columns={
            "open": "xau_open",
            "high": "xau_high",
            "low": "xau_low",
            "close": "xau_close",
        }
    )

    # ── Load USDTHB ──────────────────────────────────────────────────────
    thb = pd.read_csv(USDTHB_CSV, sep="\t")
    thb.columns = [c.strip("<>").lower() for c in thb.columns]
    thb["date"] = pd.to_datetime(thb["date"], format="mixed")
    thb = thb[["date", "close"]].copy()
    thb = thb.rename(columns={"close": "usdthb"})

    # ── Merge (inner join — เฉพาะวันที่ตรงกันเท่านั้น) ────────────────
    df = pd.merge(xau, thb, on="date", how="inner")
    df = df.sort_values("date").reset_index(drop=True)

    # ── คำนวณราคาทอง THB/gram ────────────────────────────────────────
    # price_per_gram = XAUUSD * USDTHB / 31.1035
    df["price_per_gram"] = (df["xau_close"] * df["usdthb"]) / GRAMS_PER_TROY_OZ

    return df


def create_walk_forward_windows(
    df: pd.DataFrame,
    test_years: list[int] = None,
    test_months: list[int] = None,
    test_end_day: int = 27,
) -> list[dict]:
    """
    สร้าง Walk-forward validation windows

    แต่ละ window ประกอบด้วย:
    - train_data: ข้อมูลตั้งแต่เริ่มต้นจนถึงวันก่อน test period
    - test_data:  ข้อมูลช่วง 1-{test_end_day} ของเดือนที่ทดสอบ

    Parameters
    ----------
    df : pd.DataFrame
        ข้อมูลทั้งหมดจาก load_and_merge()
    test_years : list[int]
        ปีที่ต้องการทดสอบ (default: [2022, 2023, 2024, 2025])
    test_months : list[int]
        เดือนที่ทดสอบในแต่ละปี (default: [3, 6, 9, 12] สำหรับทุกสิ้น Quarter)
    test_end_day : int
        วันสุดท้ายของช่วงทดสอบ (default: 27)
    """
    if test_years is None:
        test_years = [2022, 2023, 2024, 2025]
    if test_months is None:
        test_months = [3, 6, 9, 12]  # March, June, September, December

    windows = []
    for year in test_years:
        for month in test_months:
            test_start = pd.Timestamp(year, month, 1)
            test_end = pd.Timestamp(year, month, test_end_day)
            train_end = test_start - pd.Timedelta(days=1)

            train_data = df[df["date"] <= train_end].copy()
            test_data = df[(df["date"] >= test_start) & (df["date"] <= test_end)].copy()

            if test_data.empty:
                continue

            # กำหนดชื่อ Quarter
            q_names = {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}
            quarter = q_names.get(month, f"M{month}")

            windows.append(
                {
                    "year": year,
                    "month": month,
                    "quarter": quarter,
                    "train_start": str(train_data["date"].iloc[0].date())
                    if len(train_data) > 0
                    else None,
                    "train_end": str(train_end.date()),
                    "test_start": str(test_start.date()),
                    "test_end": str(test_end.date()),
                    "train_bars": len(train_data),
                    "test_bars": len(test_data),
                    "train_data": train_data,
                    "test_data": test_data,
                }
            )

    return windows


def main():
    print("Loading and merging XAUUSD + USDTHB data...")
    df = load_and_merge()
    print(f"  Merged data: {len(df)} bars")
    print(f"  Date range: {df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()}")
    print()

    print("Creating Walk-forward validation windows...")
    windows = create_walk_forward_windows(df)

    output_dir = os.path.join(current_dir, "Input")
    os.makedirs(output_dir, exist_ok=True)

    summary = []
    for w in windows:
        print(f"  Window {w['year']}:")
        print(
            f"    Train: {w['train_start']} → {w['train_end']} ({w['train_bars']} bars)"
        )
        print(f"    Test:  {w['test_start']} → {w['test_end']} ({w['test_bars']} bars)")

        # Save test data
        test_csv = os.path.join(output_dir, f"test_data_{w['year']}_april.csv")
        w["test_data"].to_csv(test_csv, index=False)

        summary.append(
            {
                "year": w["year"],
                "train_start": w["train_start"],
                "train_end": w["train_end"],
                "test_start": w["test_start"],
                "test_end": w["test_end"],
                "train_bars": w["train_bars"],
                "test_bars": w["test_bars"],
            }
        )

    # Save summary
    summary_path = os.path.join(output_dir, "walk_forward_windows.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Save full merged dataset
    full_path = os.path.join(output_dir, "gold_thb_daily.csv")
    df.to_csv(full_path, index=False)

    print(f"\nSaved {len(windows)} walk-forward windows to {output_dir}")
    print(f"Full merged dataset: {full_path}")


if __name__ == "__main__":
    main()
