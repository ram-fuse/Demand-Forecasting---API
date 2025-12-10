from fastapi import FastAPI, HTTPException
from schema.unified_request import UnifiedForecastRequest
from schema.unified_response import UnifiedForecastResponse, SummaryMetrics

from services.unified_forecast_service import ForecastingEngine, UnifiedForecastService

import traceback
import pandas as pd

app = FastAPI(title="Demand Forecasting API", version="2.0")


# ============================================================
# UNIFIED FORECAST ENDPOINT
# ============================================================
@app.post("/forecast", response_model=UnifiedForecastResponse)
def unified_forecast(request: UnifiedForecastRequest):
    """
    Unified forecast endpoint combining forecasting and inventory health analysis.
    
    Request:
    {
        "data": "base64_encoded_csv",
        "skus": ["SKU1", "SKU2"] or null for all SKUs,
        "data_range": "1_week|2_weeks|1_month|3_months|6_months|12_months",
        "session_id": "optional",
        "filename": "optional"
    }
    
    Response includes per-SKU forecast data with historical, inventory, and forecast time series.
    """

    try:
        # Decode CSV
        df = ForecastingEngine.decode_csv(request.data)

        # Validate required columns
        required_cols = ["Date", "sku_id", "units sold", "stock_in_hand"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"CSV missing required column: {col}")

        # Convert Date to datetime
        df["Date"] = pd.to_datetime(df["Date"])

        # Compute unified forecast
        forecast_results, summary = UnifiedForecastService.compute_unified_forecast(
            df=df,
            sku_ids=request.skus,
            data_range=request.data_range
        )

        # Return unified response
        return UnifiedForecastResponse(
            summary=SummaryMetrics(**summary),
            forecast=forecast_results
        )

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# HEALTH CHECK ENDPOINT
# ============================================================
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "2.0",
        "message": "Unified Forecast API is running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
