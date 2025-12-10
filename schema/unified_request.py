from pydantic import BaseModel, Field
from typing import Optional, List

class UnifiedForecastRequest(BaseModel):
    """Unified request for /forecast endpoint"""
    data: str  # base64 encoded CSV
    skus: Optional[List[str]] = Field(None, description="List of SKU IDs. If None, compute for all SKUs in data")
    data_range: str = Field("1_week", description="Time filter: 1_week, 2_weeks, 1_month, 3_months, 6_months, 12_months")
    session_id: Optional[str] = Field(None, description="Optional session id")
    filename: Optional[str] = Field(None, description="Optional filename")
