from pydantic import BaseModel, Field
from typing import Optional

class HealthRequest(BaseModel):
    forecast_timeline: int = Field(..., description="Days to forecast")
    sku_id: Optional[str] = Field(None, description="If provided, compute for single SKU; otherwise for all SKUs")
    session_id: Optional[str] = Field(None, description="Optional session id")
    filename: Optional[str] = Field(None, description="Optional filename")
    data: str  # base64 encoded CSV
