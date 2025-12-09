
import base64
import requests

# 1. Read your CSV file
file_path = r"data\\synthetic_data_all_feat_ram_monthly.csv"

with open(file_path, "rb") as f:
    csv_bytes = f.read()

# 2. Convert CSV to Base64
csv_b64 = base64.b64encode(csv_bytes).decode()

# 3. Prepare the request payload
payload = {
    "session_id": "test_session",
    "filename": "improved_Version-1-synthetic_data.csv",
    "data": csv_b64,
    "forecast_timeline": "7",  # forecast next 7 days
    "sku_id": "807-021H/FROSTWHITE"  # REQUIRED for SKU-wise forecast
}

# 4. Send the POST request
url = "http://127.0.0.1:8000/forecast"
response = requests.post(url, json=payload)

# 5. Print response
print("Status Code:", response.status_code)
print("Response:")

try:
    print(response.json())
except:
    print(response.text)
