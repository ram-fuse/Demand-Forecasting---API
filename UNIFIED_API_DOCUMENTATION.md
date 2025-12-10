# 🎯 Unified Forecast API Documentation

## Version 2.0 - Single Endpoint Architecture

### Overview

The Unified Forecast API combines forecasting and inventory health analysis into a **single `/forecast` endpoint**. This endpoint accepts a list of SKUs and returns comprehensive data including historical demand, inventory levels, forecasted demand, and health metrics.

---

## 📡 Endpoints

### 1. POST `/forecast` - Unified Forecast & Inventory Analysis

**Description**: Analyze demand forecasts and inventory health for multiple SKUs with comprehensive historical and forecast data.

#### Request

```json
{
  "data": "base64_encoded_csv",
  "skus": ["SKU1", "SKU2", "SKU3"],
  "data_range": "1_month",
  "session_id": "optional_session_id",
  "filename": "optional_filename"
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data` | string | ✓ | Base64-encoded CSV file containing sales data |
| `skus` | array | ✗ | List of SKU IDs to analyze. If `null`, analyzes all SKUs |
| `data_range` | string | ✓ | Time filter for analysis: `1_week`, `2_weeks`, `1_month`, `3_months`, `6_months`, `12_months` |
| `session_id` | string | ✗ | Optional session identifier for tracking |
| `filename` | string | ✗ | Original filename of uploaded CSV |

**Data Range Specifications:**

| Range | Historical Days | Forecast Days | Use Case |
|-------|-----------------|---------------|----------|
| `1_week` | 30 | 7 | Weekly planning |
| `2_weeks` | 20 | 14 | Bi-weekly review |
| `1_month` | 56 | 30 | Monthly planning |
| `3_months` | 56 | 90 | Quarterly analysis |
| `6_months` | 365 | 180 | Semi-annual planning |
| `12_months` | 365 | 365 | Annual forecast |

**CSV Requirements:**

Your CSV file must contain these columns:

```
Date, sku_id, units sold, stock_in_hand, unit_price, [optional: promotions, is_holiday, Customer Visits]
```

---

#### Response

```json
{
  "summary": {
    "total_skus": 2,
    "total_forecasted_demand": 125.45,
    "total_historical_demand": 250.0,
    "total_revenue": 34868.38,
    "avg_days_until_stockout": 12.54,
    "health_breakdown": {
      "Healthy": 0,
      "Replenish": 1,
      "Shortage Risk": 0,
      "Slow Movers": 1,
      "Overstock": 0,
      "Unknown": 0
    }
  },
  "forecast": {
    "SKU1": {
      "historical": {
        "dates": ["2024-10-01", "2024-10-02", ...],
        "values": [10.0, 12.5, ...]
      },
      "inventory": {
        "dates": ["2024-10-01", "2024-10-02", ...],
        "values": [100.0, 95.0, ...]
      },
      "forecast": {
        "dates": ["2024-11-01", "2024-11-02", ...],
        "values": [11.2, 13.4, ...]
      },
      
      "health_status": "Replenish",
      "action_replenishment": "Replenish",
      "current_stock": 18.0,
      "avg_daily_sales": 2.04,
      "days_until_stockout": 8.84,
      "forecasted_demand": 399.03,
      "historical_demand": 743.0,
      "revenue": 128887.46
    },
    "SKU2": {
      ...same structure...
    }
  }
}
```

**Response Structure Details:**

- **`summary`**: Aggregated metrics across all analyzed SKUs
  - `total_skus`: Number of SKUs analyzed
  - `total_forecasted_demand`: Sum of forecasted demand across all SKUs
  - `total_historical_demand`: Sum of historical demand across all SKUs
  - `total_revenue`: Sum of revenue (forecasted_demand × unit_price) across all SKUs
  - `avg_days_until_stockout`: Average days until stockout across all SKUs
  - `health_breakdown`: Count of SKUs in each health category

- **`forecast`**: Dictionary with SKU ID as key, contains:
  - **`historical`**: Actual demand data from the historical period
    - `dates`: Array of dates in YYYY-MM-DD format
    - `values`: Array of units sold on each date
  
  - **`inventory`**: Stock levels during historical period
    - `dates`: Array of dates in YYYY-MM-DD format
    - `values`: Array of stock_in_hand values
  
  - **`forecast`**: Predicted demand for future period
    - `dates`: Array of future dates in YYYY-MM-DD format
    - `values`: Array of forecasted units
  
  - **Health Metrics**:
    - `health_status`: Status category (see Health Status Rules below)
    - `action_replenishment`: Recommended action
  
  - **Demand Metrics**:
    - `forecasted_demand`: Sum of forecasted units for next N days
    - `historical_demand`: Sum of actual units sold in last N days
    - `revenue`: forecasted_demand × average unit_price
  
  - **Inventory Metrics**:
    - `current_stock`: Most recent stock level
    - `avg_daily_sales`: Average daily sales during historical period
    - `days_until_stockout`: Estimated days before running out (current_stock / avg_daily_sales)

---

### 2. GET `/health` - Health Check

**Description**: Check if the API is running and operational.

#### Response

```json
{
  "status": "ok",
  "version": "2.0",
  "message": "Unified Forecast API is running"
}
```

---

## 🏥 Health Status Rules

The API evaluates each SKU's inventory health based on these rules (evaluated in order):

| Condition | Status | Score | Action | Reason |
|-----------|--------|-------|--------|--------|
| days_until_stockout ≤ 7 | Shortage Risk | 25 | Accelerate Purchase Orders | Stock critically low |
| days_until_stockout ≤ 30 | Replenish | 75 | Replenish | Needs ordering soon |
| days_until_stockout ≥ 90 | Overstock | 60 | Pause Ordering | Excess inventory |
| avg_daily_sales < 5 | Slow Movers | 50 | Pause Ordering | Low sales velocity |
| days_until_stockout is null | Unknown | 10 | Investigate | Data quality issue |
| All others | Healthy | 100 | No Action | All good |

---

## 📊 Example Usage

### Python Example

```python
import base64
import requests
import json

# Load and encode CSV
with open("sales_data.csv", "rb") as f:
    csv_b64 = base64.b64encode(f.read()).decode()

# Prepare request
payload = {
    "data": csv_b64,
    "skus": ["SKU001", "SKU002", "SKU003"],
    "data_range": "1_month",
    "session_id": "my_session_123"
}

# Call API
response = requests.post(
    "http://localhost:8000/forecast",
    json=payload
)

if response.status_code == 200:
    result = response.json()
    
    # Access summary
    print(f"Total Revenue: ${result['summary']['total_revenue']:,.2f}")
    print(f"Health Breakdown: {result['summary']['health_breakdown']}")
    
    # Access per-SKU data
    for sku, detail in result['forecast'].items():
        print(f"\n{sku}:")
        print(f"  Status: {detail['health_status']}")
        print(f"  Forecast: {detail['forecasted_demand']} units")
        print(f"  Next 5 days: {detail['forecast']['values'][:5]}")
else:
    print(f"Error: {response.text}")
```

### cURL Example

```bash
# 1. Encode CSV
CSV_B64=$(base64 < sales_data.csv | tr -d '\n')

# 2. Create request
curl -X POST http://localhost:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "data": "'$CSV_B64'",
    "skus": ["SKU001", "SKU002"],
    "data_range": "1_month"
  }'
```

---

## ⚙️ Configuration

### Time Filter Configuration

The time filters are configured in `services/inventory_service.py`:

```python
TIME_FILTER_CONFIG = {
    "1_week": {"historical_days": 30, "forecast_days": 7},
    "2_weeks": {"historical_days": 20, "forecast_days": 14},
    "1_month": {"historical_days": 56, "forecast_days": 30},
    "3_months": {"historical_days": 56, "forecast_days": 90},
    "6_months": {"historical_days": 365, "forecast_days": 180},
    "12_months": {"historical_days": 365, "forecast_days": 365},
}
```

### Health Score Calculation

Health scores are calculated in `services/unified_forecast_service.py`:

```python
score_map = {
    "Healthy": 100.0,
    "Replenish": 75.0,
    "Slow Movers": 50.0,
    "Shortage Risk": 25.0,
    "Overstock": 60.0,
    "Unknown": 10.0
}
```

---

## 🔧 Error Handling

### Common Error Responses

**400 Bad Request - Missing Column:**
```json
{
  "detail": "CSV missing required column: Date"
}
```

**400 Bad Request - Invalid Base64:**
```json
{
  "detail": "Failed to decode CSV: ..."
}
```

**400 Bad Request - No Data for SKU:**
```json
{
  "detail": "No data found for SKU: INVALID_SKU"
}
```

---

## 📈 Output Data Format

### Historical Data Array

Each date-value pair represents actual demand during the lookback period:

```json
"historical": {
  "dates": ["2024-09-01", "2024-09-02", "2024-09-03"],
  "values": [10.5, 12.3, 11.8]
}
```

### Inventory Data Array

Each date-value pair represents stock level at end of day:

```json
"inventory": {
  "dates": ["2024-09-01", "2024-09-02", "2024-09-03"],
  "values": [100.0, 97.7, 85.9]
}
```

### Forecast Data Array

Each date-value pair represents predicted demand:

```json
"forecast": {
  "dates": ["2024-10-01", "2024-10-02", "2024-10-03"],
  "values": [11.2, 13.1, 10.9]
}
```

---

## 🚀 Getting Started

### Installation

```bash
# Clone repository
git clone <repo>
cd Demand-Forecasting

# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the API

```bash
# Start the server
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Server will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
# ReDoc at http://localhost:8000/redoc
```

### Testing

```bash
# Run comprehensive tests
python test_unified_api.py
```

---

## 📝 Version History

- **v2.0** (Current): Single unified `/forecast` endpoint combining forecasting and inventory analysis
- **v1.0**: Separate `/forecast` and `/inventory_health` endpoints

---

## 🎓 Key Concepts

### Historical Demand
Sum of actual units sold during the historical period (e.g., last 56 days). Used as baseline to compare against forecasts.

### Forecasted Demand
Predicted units to be sold during the forecast period (e.g., next 30 days). Generated using Facebook Prophet time-series model.

### Revenue
Financial projection: `forecasted_demand × average_unit_price`. Useful for revenue planning.

### Health Score
Composite score (0-100) indicating inventory health. Combines stockout risk, sales velocity, and stock levels.

### Days Until Stockout
Estimate of when inventory will deplete: `current_stock / average_daily_sales`. Critical for procurement planning.

---

## 💡 Best Practices

1. **Use specific time ranges** for different planning horizons (weekly vs annual)
2. **Monitor health scores** - act when status changes
3. **Compare historical vs forecasted** demand to understand trends
4. **Review aggregated summary** for portfolio-level insights
5. **Keep CSV data fresh** - more recent data = better forecasts
6. **Include optional columns** (promotions, holidays) for more accurate forecasts

---

## 📞 Support

For issues or questions:
1. Check CSV format (all required columns present?)
2. Verify base64 encoding of CSV
3. Check API logs for detailed error messages
4. Test with `/health` endpoint to confirm API is running

---

Generated: December 10, 2025
API Version: 2.0
Status: Production Ready ✅
