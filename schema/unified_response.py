from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class SKUHistoricalData(BaseModel):
    """Historical demand data"""
    dates: List[str]
    values: List[float]


class SKUInventoryData(BaseModel):
    """Inventory/stock data"""
    dates: List[str]
    values: List[float]


class SKUForecastData(BaseModel):
    """Forecasted demand data"""
    dates: List[str]
    values: List[float]


class SKUForecastDetail(BaseModel):
    """Individual SKU forecast details"""
    historical: SKUHistoricalData
    inventory: SKUInventoryData
    forecast: SKUForecastData
    health_status: str
    action_replenishment: str
    current_stock: Optional[float] = None
    avg_daily_sales: Optional[float] = None
    days_until_stockout: Optional[float] = None
    forecasted_demand: float
    historical_demand: float
    revenue: float


class SummaryMetrics(BaseModel):
    """Aggregated summary metrics"""
    total_skus: int
    total_forecasted_demand: float
    total_historical_demand: float
    total_revenue: float
    avg_days_until_stockout: float
    health_breakdown: Dict[str, int]
    replenishment_need_total: float
    revenue_at_risk: float
    healthy_supply_count: int
    healthy_supply_coverage: float


class UnifiedForecastResponse(BaseModel):
    """Unified response for /forecast endpoint"""
    summary: SummaryMetrics
    forecast: Dict[str, SKUForecastDetail]  # Key: SKU ID, Value: forecast details
