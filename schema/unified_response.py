from pydantic import BaseModel
from typing import List, Dict, Optional, Any

# ============================================================================
# Individual SKU Data Models
# ============================================================================

class SKUHistoricalData(BaseModel):
    """Historical demand data"""
    dates: List[str]
    values: List[float]


class SKUInventoryData(BaseModel):
    """Inventory/stock data"""
    dates: List[str]
    values: List[Optional[float]]  # allow None if stock data missing


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
    forecast_avg_daily: Optional[float] = None  
    days_until_stockout: Optional[float] = None
    forecasted_demand: int
    historical_demand: int
    revenue: float


# ============================================================================
# Aggregated Summary Models
# ============================================================================

class SummaryMetrics(BaseModel):
    """Aggregated summary metrics across all SKUs"""
    total_skus: int
    total_forecasted_demand: int  # integer units
    total_historical_demand: int  # integer units
    total_revenue: float
    avg_days_until_stockout: float
    # health_breakdown maps each category to {count, percent}
    health_breakdown: Dict[str, Dict[str, float]]
    replenishment_need_total: int  # integer units needed
    revenue_at_risk: float


class UnifiedForecastResponse(BaseModel):
    """Unified response for /forecast endpoint"""
    summary: SummaryMetrics
    forecast: Dict[str, SKUForecastDetail]  # Key: SKU ID, Value: forecast details
