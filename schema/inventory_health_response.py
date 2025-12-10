from pydantic import BaseModel
from typing import List, Optional

class InventoryItem(BaseModel):
    sku_id: str
    forecasted_demand: float
    revenue: float
    health: str
    action_replenishment: str
    days_until_stockout: Optional[float] = None
    current_stock: Optional[float] = None
    avg_daily_sales: Optional[float] = None

class HealthResponse(BaseModel):
    data: List[InventoryItem]
