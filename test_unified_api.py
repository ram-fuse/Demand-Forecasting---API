import base64
import requests
import json
import os
from datetime import datetime

# =====================================================
# Load & Encode CSV
# =====================================================
CSV_PATH = r"data\synthetic_data_all_feat_rajendra_monthly.csv"

with open(CSV_PATH, "rb") as f:
    csv_bytes = f.read()

csv_b64 = base64.b64encode(csv_bytes).decode()

# =====================================================
# API Configuration
# =====================================================
API_BASE = "http://127.0.0.1:8000"

def pretty(obj):
    return json.dumps(obj, indent=2, default=str)


# =====================================================
# Test Unified /forecast Endpoint
# =====================================================
def test_unified_forecast():
    """Test unified /forecast endpoint with all time ranges"""
    
    time_ranges = ["1_week", "2_weeks", "1_month", "3_months", "6_months", "12_months"]
    
    for data_range in time_ranges:
        print("\n" + "="*80)
        print(f"Testing /forecast with DATA_RANGE: {data_range}")
        print("="*80)
        
        # Test with all SKUs
        payload = {
            "data": csv_b64,
            "skus": None,  # None means all SKUs
            "data_range": data_range,
            "session_id": "test_session",
            "filename": "synthetic_data.csv"
        }
        
        try:
            response = requests.post(f"{API_BASE}/forecast", json=payload)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                # Persist full response to JSON file for this data_range
                os.makedirs("output", exist_ok=True)
                out_path = os.path.join("output", f"unified_forecast_{data_range}.json")
                with open(out_path, "w", encoding="utf-8") as fh:
                    json.dump(result, fh, indent=2, default=str)
                print(f"Saved response to: {out_path}")
                
                # Print summary
                if "summary" in result:
                    print("\n📊 AGGREGATED SUMMARY:")
                    print(json.dumps(result["summary"], indent=2, default=str))
                
                # Print first 3 SKUs with all fields
                if "forecast" in result:
                    skus = list(result["forecast"].keys())[:3]
                    print(f"\n📈 SAMPLE SKUs (first 3 of {len(result['forecast'])}):")
                    
                    for sku in skus:
                        detail = result["forecast"][sku]
                        print(f"\n  SKU: {sku}")
                        print(f"    Health Status: {detail['health_status']}")
                        print(f"    Action: {detail['action_replenishment']}")
                        print(f"    Historical Demand: {detail['historical_demand']}")
                        print(f"    Forecasted Demand: {detail['forecasted_demand']}")
                        print(f"    Revenue: {detail['revenue']}")
                        print(f"    Days Until Stockout: {detail['days_until_stockout']}")
                        print(f"    Current Stock: {detail['current_stock']}")
                        print(f"    Avg Daily Sales: {detail['avg_daily_sales']}")
                        
                        # Show first 5 historical dates and values
                        print(f"    Historical Data (first 5 dates):")
                        hist_dates = detail['historical']['dates'][:5]
                        hist_values = detail['historical']['values'][:5]
                        for date, value in zip(hist_dates, hist_values):
                            print(f"      {date}: {value}")
                        
                        # Show first 5 forecast dates and values
                        print(f"    Forecast Data (first 5 dates):")
                        fc_dates = detail['forecast']['dates'][:5]
                        fc_values = detail['forecast']['values'][:5]
                        for date, value in zip(fc_dates, fc_values):
                            print(f"      {date}: {value}")
            else:
                print(f"❌ Error Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")


# =====================================================
# Test with Specific SKU List
# =====================================================
def test_unified_forecast_with_sku_list():
    """Test unified /forecast endpoint with specific SKU list"""
    
    print("\n" + "="*80)
    print("Testing /forecast with SPECIFIC SKU LIST")
    print("="*80)
    
    # Test with specific SKUs
    test_skus = ["1023-003/0212-83/BISQUE", "807-021H/FROSTWHITE"]
    
    payload = {
        "data": csv_b64,
        "skus": test_skus,
        "data_range": "1_month",
        "session_id": "test_session",
        "filename": "synthetic_data.csv"
    }
    
    try:
        response = requests.post(f"{API_BASE}/forecast", json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Persist specific-SKU response to JSON
            os.makedirs("output", exist_ok=True)
            out_path = os.path.join("output", "unified_forecast_specific.json")
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2, default=str)
            print(f"Saved response to: {out_path}")

            # Print summary
            if "summary" in result:
                print("\n📊 AGGREGATED SUMMARY (2 SKUs):")
                print(json.dumps(result["summary"], indent=2, default=str))
            
            # Print details for each SKU
            if "forecast" in result:
                print(f"\n📈 DETAILED FORECAST FOR {len(result['forecast'])} SKUs:")
                for sku, detail in result["forecast"].items():
                    print(f"\n  SKU: {sku}")
                    print(f"    Health Status: {detail['health_status']}")
                    print(f"    Forecasted Demand: {detail['forecasted_demand']}")
                    print(f"    Historical Demand: {detail['historical_demand']}")
                    print(f"    Revenue: {detail['revenue']}")
                    print(f"    Forecast Dates: {detail['forecast']['dates']}")
                    print(f"    Forecast Values: {detail['forecast']['values']}")
        else:
            print(f"❌ Error Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")


# =====================================================
# Test Health Check
# =====================================================
def test_health_check():
    """Test health check endpoint"""
    print("\n" + "="*80)
    print("Testing /health endpoint")
    print("="*80)
    
    try:
        response = requests.get(f"{API_BASE}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {pretty(response.json())}")
    except Exception as e:
        print(f"❌ Exception: {str(e)}")


if __name__ == "__main__":
    print("🚀 STARTING UNIFIED FORECAST API TESTS\n")
    
    # Test health check first
    test_health_check()
    
    # Test unified forecast with all time ranges
    test_unified_forecast()
    
    # Test with specific SKU list
    test_unified_forecast_with_sku_list()
    
    print("\n✅ ALL TESTS COMPLETED!")
