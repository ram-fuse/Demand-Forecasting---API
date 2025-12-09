from fastapi import FastAPI, HTTPException
from schema import ForecastRequest, ForecastResponse
from services.forecast_service import ForecastService
from services.forecast_service import decode_csv, preprocess, train_and_forecast

from prophet import Prophet
import traceback
app = FastAPI(title="Demand Forecasting API", version="1.0")


@app.post("/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):

    try:
        # Decode CSV
        df = ForecastService.decode_csv(request.data)

        # Preprocess SKU-specific data
        df_sku, regressors = ForecastService.preprocess(df, request.sku_id)

        # Run Prophet model
        forecast = ForecastService.train_and_forecast(
            df=df_sku,
            regressors=regressors,
            periods=request.forecast_timeline
        )

        # Prepare response
        result = forecast.tail(request.forecast_timeline)

        return ForecastResponse(
            sku_id=request.sku_id,
            date=result["ds"].dt.strftime("%Y-%m-%d").tolist(),
            demand=result["yhat"].round(2).tolist(),
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
