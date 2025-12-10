import base64
import requests
import json

# =====================================================
# 1. Load & Encode CSV Once
# =====================================================
CSV_PATH = r"data\synthetic_data_all_feat_rajendra_monthly.csv"

with open(CSV_PATH, "rb") as f:
    csv_bytes = f.read()

csv_b64 = base64.b64encode(csv_bytes).decode()

# =====================================================
# 2. Common Parameters
# =====================================================
API_BASE = "http://127.0.0.1:8000"

def pretty(obj):
    return json.dumps(obj, indent=4, default=str)


# =====================================================
# 3. Test /inventory_health with TIME FILTERS
# =====================================================
def test_inventory_health_with_filters():
    """Test /inventory_health with different time filters and multiple SKUs."""
    
    time_filters = ["1_week", "2_weeks", "1_month", "3_months", "6_months", "12_months"]
    
    # Get first 5 SKUs for testing (or all if fewer)
    test_sku_count = 3
    
    for time_filter in time_filters:
        print("\n" + "="*70)
        print(f"Testing /inventory_health with TIME_FILTER: {time_filter}")
        print("="*70)
        
        payload = {
            "data": csv_b64,
            "sku_ids": None,  # None means all SKUs
            "time_filter": time_filter,
            "session_id": "test_session",
            "filename": "synthetic_data.csv"
        }
        
        try:
            response = requests.post(f"{API_BASE}/inventory_health", json=payload)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Print summary
                if "summary" in result:
                    print("\n SUMMARY:")
                    print(pretty(result["summary"]))
                
                # Print first 3 items
                if "data" in result and len(result["data"]) > 0:
                    print(f"\n SAMPLE SKUs (first 3 of {len(result['data'])}):")
                    for item in result["data"][:3]:
                        print(f"\n  SKU: {item['sku_id']}")
                        print(f"    Historical Demand: {item['historical_demand']}")
                        print(f"    Forecasted Demand: {item['forecasted_demand']}")
                        print(f"    Revenue: {item['revenue']}")
                        print(f"    Health: {item['health']}")
                        print(f"    Action: {item['action_replenishment']}")
                        print(f"    Days Until Stockout: {item['days_until_stockout']}")
                        print(f"    Current Stock: {item['current_stock']}")
                        print(f"    Avg Daily Sales: {item['avg_daily_sales']}")
                        print(f"    Time Filter: {item['time_filter']}")
                        print(f"    Historical Days Used: {item['historical_days']}")
            else:
                print(f" Error Response: {response.text}")
                
        except Exception as e:
            print(f" Exception: {str(e)}")


# =====================================================
# 4. Test with specific SKU list
# =====================================================
def test_inventory_health_with_sku_list():
    """Test /inventory_health with a specific list of SKUs."""
    
    print("\n" + "="*70)
    print("Testing /inventory_health with SPECIFIC SKU LIST")
    print("="*70)
    
    # Test with a specific set of SKUs
    test_skus = ["1023-003/0212-83/BISQUE","807-021H/FROSTWHITE", "970-076-4260/WILLOW"]  # Adjust based on your data
    
    payload = {
        "data": csv_b64,
        "sku_ids": test_skus,
        "time_filter": "1_month",
        "session_id": "test_session",
        "filename": "synthetic_data.csv"
    }
    
    try:
        response = requests.post(f"{API_BASE}/inventory_health", json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n SUMMARY:")
            print(pretty(result["summary"]))
            
            print("\n REQUESTED SKUs:")
            for item in result["data"]:
                print(f"\n  SKU: {item['sku_id']}")
                print(f"    Historical Demand: {item['historical_demand']}")
                print(f"    Forecasted Demand: {item['forecasted_demand']}")
                print(f"    Revenue: ${item['revenue']}")
                print(f"    Health: {item['health']} | Action: {item['action_replenishment']}")
                print(f"    Days Until Stockout: {item['days_until_stockout']}")
        else:
            print(f" Error Response: {response.text}")
            
    except Exception as e:
        print(f" Exception: {str(e)}")


# =====================================================
# 5. Run All Tests
# =====================================================
if __name__ == "__main__":
    print("\n STARTING INVENTORY HEALTH API TESTS\n")
    
    test_inventory_health_with_filters()
    test_inventory_health_with_sku_list()
    
    print("\n ALL TESTS COMPLETED!")
