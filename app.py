from fastapi import FastAPI, HTTPException
from schema import ForecastRequest, ForecastResponse
from schema.inventory_health_request import HealthRequest
from schema.inventory_health_response import HealthResponse

from services.forecast_service import ForecastService
from services.inventory_service import InventoryService

import traceback

app = FastAPI(title="Demand Forecasting API", version="1.0")


#  FORECAST ENDPOINT
@app.post("/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):

    try:
        df = ForecastService.decode_csv(request.data)
        df_sku, regressors = ForecastService.preprocess(df, request.sku_id)

        forecast = ForecastService.train_and_forecast(
            df=df_sku,
            regressors=regressors,
            periods=request.forecast_timeline
        )

        result = forecast.tail(request.forecast_timeline)

        return ForecastResponse(
            sku_id=request.sku_id,
            date=result["ds"].dt.strftime("%Y-%m-%d").tolist(),
            forecast_demand=result["yhat"].round(2).tolist()
        )

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


#  INVENTORY HEALTH ENDPOINT
@app.post("/inventory_health", response_model=HealthResponse)
def inventory_health(request: HealthRequest):
    try:
        df = ForecastService.decode_csv(request.data)

        required_cols = ["Date", "sku_id", "units sold", "stock_in_hand"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"CSV missing required column: {col}")

        result = InventoryService.compute_inventory_health(
            df=df,
            periods=request.forecast_timeline,   # REQUIRED ARGUMENT
            sku_id=request.sku_id
        )

        return HealthResponse(data=result)

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))
