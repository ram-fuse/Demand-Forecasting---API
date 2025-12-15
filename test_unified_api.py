import base64
import requests
import json
import os
from typing import Optional, List

# =====================================================
# CONFIGURATION
# =====================================================
API_BASE = "http://127.0.0.1:8000"
CSV_PATH = r"data\\synthetic_data_all_feat_ram_weekly_shifted.csv"
OUTPUT_DIR = "output"

TIME_RANGES = ["1_week", "2_weeks", "1_month", "3_months", "6_months", "12_months"]

os.makedirs(OUTPUT_DIR, exist_ok=True)


# =====================================================
# UTILITIES
# =====================================================
def encode_csv_to_base64(csv_path: str) -> str:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with open(csv_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def save_json(filename: str, data: dict):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"💾 Saved response → {path}")


def print_summary(summary: dict):
    print("\n📊 AGGREGATED SUMMARY")
    print(json.dumps(summary, indent=2, default=str))


def print_sku_sample(forecast: dict, max_skus: int = 3):
    skus = list(forecast.keys())[:max_skus]
    print(f"\n📈 SAMPLE SKU OUTPUT (showing {len(skus)} of {len(forecast)})")

    for sku in skus:
        d = forecast[sku]
        print(f"\n  SKU: {sku}")
        print(f"    Health Status      : {d['health_status']}")
        print(f"    Action             : {d['action_replenishment']}")
        print(f"    Historical Demand  : {d['historical_demand']}")
        print(f"    Forecasted Demand  : {d['forecasted_demand']}")
        print(f"    Revenue            : {d['revenue']}")
        print(f"    Days Until Stockout: {d['days_until_stockout']}")
        print(f"    Current Stock      : {d['current_stock']}")

        print("    Historical (first 5):")
        for dt, val in zip(d["historical"]["dates"][:5], d["historical"]["values"][:5]):
            print(f"      {dt}: {val}")

        print("    Forecast (first 5):")
        for dt, val in zip(d["forecast"]["dates"][:5], d["forecast"]["values"][:5]):
            print(f"      {dt}: {val}")


def call_forecast_api(
    csv_b64: str,
    data_range: str,
    skus: Optional[List[str]] = None
) -> dict:
    payload = {
        "data": csv_b64,
        "skus": skus,
        "data_range": data_range,
        "session_id": "test_session",
        "filename": os.path.basename(CSV_PATH)
    }

    response = requests.post(f"{API_BASE}/forecast", json=payload)

    print(f"Status Code: {response.status_code}")

    if response.status_code != 200:
        raise RuntimeError(f"API Error: {response.text}")

    return response.json()


# =====================================================
# TEST CASES
# =====================================================
def test_health_check():
    print("\n" + "=" * 80)
    print("🔍 Testing /health endpoint")
    print("=" * 80)

    response = requests.get(f"{API_BASE}/health")
    print("Status Code:", response.status_code)
    print(json.dumps(response.json(), indent=2))


def test_forecast_all_time_ranges(csv_b64: str):
    for data_range in TIME_RANGES:
        print("\n" + "=" * 80)
        print(f"🚀 Testing /forecast | DATA_RANGE = {data_range}")
        print("=" * 80)

        result = call_forecast_api(csv_b64, data_range)

        save_json(f"unified_forecast_{data_range}.json", result)

        print_summary(result["summary"])
        print_sku_sample(result["forecast"])


def test_forecast_specific_skus(csv_b64: str):
    print("\n" + "=" * 80)
    print("🎯 Testing /forecast | SPECIFIC SKUs")
    print("=" * 80)

    test_skus = [
        "1023-003/0212-83/BISQUE",
        "807-021H/FROSTWHITE"
    ]

    result = call_forecast_api(csv_b64, "1_month", test_skus)

    save_json("unified_forecast_specific_skus.json", result)

    print_summary(result["summary"])
    print_sku_sample(result["forecast"], max_skus=len(test_skus))


# =====================================================
# MAIN RUNNER
# =====================================================
if __name__ == "__main__":
    print("🚀 STARTING UNIFIED FORECAST API TESTS")

    csv_b64 = encode_csv_to_base64(CSV_PATH)

    test_health_check()
    test_forecast_all_time_ranges(csv_b64)
    test_forecast_specific_skus(csv_b64)

    print("\n✅ ALL TESTS COMPLETED SUCCESSFULLY")
