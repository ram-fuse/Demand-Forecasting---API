from pydantic import BaseModel, Field

class ForecastRequest(BaseModel):
    session_id: str
    filename: str
    sku_id: str = Field(..., description="SKU ID to forecast")
    data: str  # base64 encoded CSV
    forecast_timeline: int = Field(..., description="Number of days to forecast")
