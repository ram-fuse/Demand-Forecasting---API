import base64
import requests

API_URL = "http://127.0.0.1:8000/inventory_health"
CSV_PATH = "data\\synthetic_data_all_feat_rajendra_monthly.csv"  # Replace with your actual CSV file path

with open(CSV_PATH, "rb") as f:
    csv_bytes = f.read()
csv_b64 = base64.b64encode(csv_bytes).decode()

payload = {
    "sku_id": "1023-003/0212-83/BISQUE",  # Replace with a valid SKU from your data
    "data": csv_b64,
    "forecast_timeline": 7  # Or any integer for periods
}

response = requests.post(API_URL, json=payload)
print("Status Code:", response.status_code)
print("Response:", response.json())