"""
Unified Forecast Service - Complete consolidated forecasting and inventory analysis.
Combines forecasting, inventory health, and unified response generation.
"""
import math
import base64
import io
import pandas as pd
from prophet import Prophet
from typing import List, Dict, Optional, Tuple, Any
from schema.unified_response import (
    SKUHistoricalData, SKUInventoryData, SKUForecastData,
    SKUForecastDetail, UnifiedForecastResponse
)

# ============================================================================
# TIME FILTER CONFIGURATION
# ============================================================================
TIME_FILTER_CONFIG = {
    "1_week": {"historical_days": 30, "forecast_days": 7},
    "2_weeks": {"historical_days": 20, "forecast_days": 14},
    "1_month": {"historical_days": 56, "forecast_days": 30},
    "3_months": {"historical_days": 56, "forecast_days": 90},
    "6_months": {"historical_days": 365, "forecast_days": 180},
    "12_months": {"historical_days": 365, "forecast_days": 365},
}

# ============================================================================
# INTERNAL INVENTORY ITEM
# ============================================================================
class InventoryItem:
    """Internal inventory analysis result"""
    def __init__(
        self, sku_id: str, forecasted_demand: float, historical_demand: float,
        revenue: float, avg_price: float, health: str, action_replenishment: str,
        days_until_stockout: Optional[float], current_stock: Optional[float],
        forecast_avg_daily: float, time_filter: str, historical_days: int
    ):
        self.sku_id = sku_id
        self.forecasted_demand = forecasted_demand
        self.historical_demand = historical_demand
        self.revenue = revenue
        self.avg_price = avg_price
        self.health = health
        self.action_replenishment = action_replenishment
        self.days_until_stockout = days_until_stockout
        self.current_stock = current_stock
        self.forecast_avg_daily = forecast_avg_daily
        self.time_filter = time_filter
        self.historical_days = historical_days

# ============================================================================
# FORECASTING ENGINE
# ============================================================================
class ForecastingEngine:
    """Core Prophet-based forecasting"""

    @staticmethod
    def decode_csv(base64_string: str) -> pd.DataFrame:
        """Decode base64 CSV into DataFrame"""
        try:
            decoded_bytes = base64.b64decode(base64_string)
            return pd.read_csv(io.BytesIO(decoded_bytes))
        except Exception as e:
            raise ValueError(f"Failed to decode CSV: {e}")

    @staticmethod
    def preprocess(df: pd.DataFrame, sku_id: str) -> Tuple[pd.DataFrame, List[str]]:
        """Prepare SKU-specific data for Prophet"""
        df_sku = df[df["sku_id"] == sku_id].copy()
        if df_sku.empty:
            raise ValueError(f"No data found for SKU: {sku_id}")

        df_sku = df_sku.rename(columns={"Date": "ds", "units sold": "y"})
        df_sku["ds"] = pd.to_datetime(df_sku["ds"])

        # Convert promotions to numeric
        if "promotions" in df_sku.columns:
            df_sku["promotions"] = df_sku["promotions"].map({"On Promotion": 1, "Off Promotion": 0}).fillna(0)

        # Identify available regressors
        regressors = [col for col in ["promotions", "is_holiday", "Customer Visits", "unit_price"] if col in df_sku.columns]
        return df_sku, regressors

    @staticmethod
    def train_and_forecast(df: pd.DataFrame, regressors: List[str], periods: int) -> pd.DataFrame:
        """Train Prophet model and forecast for given periods"""
        model = Prophet()
        for reg in regressors:
            model.add_regressor(reg)
        model.fit(df)

        future = model.make_future_dataframe(periods=periods, freq="D")
        # selects the last available value of the regressor in historical data.
        for reg in regressors:
            future[reg] = df[reg].iloc[-1]  # fill with last known value

        return model.predict(future)

# ============================================================================
# INVENTORY HEALTH SERVICE
# ============================================================================
class InventoryService:
    """Compute inventory health metrics for a SKU"""

    @staticmethod
    def _get_time_filter_config(time_filter: str) -> Dict[str, int]:
        return TIME_FILTER_CONFIG.get(time_filter, TIME_FILTER_CONFIG["1_week"])

    @staticmethod
    def compute_for_sku(df: pd.DataFrame, sku_id: str, time_filter: str) -> InventoryItem:
        config = InventoryService._get_time_filter_config(time_filter)
        hist_days = config["historical_days"]
        fc_days = config["forecast_days"]

        df_sku, regressors = ForecastingEngine.preprocess(df, sku_id)
        df_sku = df_sku.sort_values("ds")

        # Train forecast
        forecast = ForecastingEngine.train_and_forecast(df_sku, regressors, fc_days)
        future = forecast.tail(fc_days)

        # Slice historical data for display
        df_sku_display = df_sku.tail(hist_days) if len(df_sku) > hist_days else df_sku

        # Metrics
        forecasted_demand = int(future["yhat"].sum())
        historical_demand = int(df_sku_display["y"].sum())
        latest_price = float(df_sku_display["unit_price"].iloc[-1]) if "unit_price" in df_sku_display.columns else 0.0
        revenue = forecasted_demand * latest_price

        # Keep forecast_avg_daily
        forecast_avg_daily_raw = future["yhat"].mean() if not future.empty else 0.0
        forecast_avg_daily = round(float(forecast_avg_daily_raw), 4) if not pd.isna(forecast_avg_daily_raw) else 0.0

        current_stock = int(df_sku_display["stock_in_hand"].iloc[-1]) if "stock_in_hand" in df_sku_display.columns else None
        days_until_stockout = current_stock / forecast_avg_daily if current_stock and forecast_avg_daily > 0 else None

        # Health logic
        if days_until_stockout is None:
            health = "Unknown"; action = "Investigate"
        elif days_until_stockout <= 7:
            health = "Shortage Risk"; action = "Accelerate Purchase Orders"
        elif days_until_stockout <= 30:
            health = "Healthy"; action = "Replenish"
        elif days_until_stockout >= 90:
            health = "Overstock"; action = "Pause Ordering"
        elif forecast_avg_daily < 5:
            health = "Slow Movers"; action = "Pause Ordering"
        else:
            health = "Healthy"; action = "No Action"

        return InventoryItem(
            sku_id=sku_id,
            forecasted_demand=math.floor(forecasted_demand),
            historical_demand=math.floor(historical_demand),
            revenue=round(revenue,2),
            avg_price=round(latest_price,2),
            health=health,
            action_replenishment=action,
            days_until_stockout=math.floor(days_until_stockout) if days_until_stockout else None,
            current_stock=current_stock,
            forecast_avg_daily=math.floor(forecast_avg_daily),
            time_filter=time_filter,
            historical_days=hist_days
        )

# ============================================================================
# UNIFIED FORECAST SERVICE
# ============================================================================
class UnifiedForecastService:
    """Orchestrator for multiple SKUs"""

    @staticmethod
    def compute_unified_forecast(df: pd.DataFrame, sku_ids: Optional[List[str]] = None, data_range: str = "1_week") -> Tuple[Dict[str, SKUForecastDetail], Dict[str, Any]]:
        sku_list = sku_ids if sku_ids else sorted(df["sku_id"].dropna().unique().tolist())
        forecast_results = {}
        inventory_results = []

        for sku in sku_list:
            try:
                # Compute inventory + forecast
                inventory_item = InventoryService.compute_for_sku(df, sku, data_range)
                inventory_results.append(inventory_item)

                # Prepare time-series for response
                df_sku, _ = ForecastingEngine.preprocess(df, sku)
                df_sku = df_sku.sort_values("ds")

                hist_days = inventory_item.historical_days
                fc_days = TIME_FILTER_CONFIG[data_range]["forecast_days"]

                df_sku_hist = df_sku.tail(hist_days) if len(df_sku) > hist_days else df_sku
                forecast = ForecastingEngine.train_and_forecast(df_sku, [], fc_days)
                future = forecast.tail(fc_days)

                sku_detail = SKUForecastDetail(
                    historical=SKUHistoricalData(
                        dates=df_sku_hist["ds"].dt.strftime("%Y-%m-%d").tolist(),
                        values=df_sku_hist["y"].round(2).tolist()
                    ),
                    inventory=SKUInventoryData(
                        dates=df_sku_hist["ds"].dt.strftime("%Y-%m-%d").tolist() if "stock_in_hand" in df_sku_hist.columns else [],
                        values=df_sku_hist["stock_in_hand"].round(2).tolist() if "stock_in_hand" in df_sku_hist.columns else []
                    ),
                    forecast=SKUForecastData(
                        dates=future["ds"].dt.strftime("%Y-%m-%d").tolist(),
                        values=future["yhat"].round(2).tolist()
                    ),
                    health_status=inventory_item.health,
                    action_replenishment=inventory_item.action_replenishment,
                    current_stock=inventory_item.current_stock,
                    avg_daily_sales=inventory_item.forecast_avg_daily,
                    days_until_stockout=inventory_item.days_until_stockout,
                    forecasted_demand=inventory_item.forecasted_demand,
                    historical_demand=inventory_item.historical_demand,
                    revenue=inventory_item.revenue
                )

                forecast_results[sku] = sku_detail

            except Exception as e:
                print(f"Error processing SKU {sku}: {e}")

        # Aggregated summary
        summary = UnifiedForecastService._calculate_summary(inventory_results)
        return forecast_results, summary

    @staticmethod
    def _calculate_summary(inventory_items: List[InventoryItem]) -> Dict[str, Any]:
        if not inventory_items:
            return {
                "total_skus": 0,
                "total_forecasted_demand": 0.0,
                "total_historical_demand": 0.0,
                "total_revenue": 0.0,
                "avg_days_until_stockout": 0.0,
                "health_breakdown": {},
                "replenishment_need_total": 0.0,
                "revenue_at_risk": 0.0
            }

        total_skus = len(inventory_items)
        total_forecasted_demand = int(round(sum(r.forecasted_demand for r in inventory_items)))
        total_historical_demand = int(round(sum(r.historical_demand for r in inventory_items)))
        total_revenue = round(sum(r.revenue for r in inventory_items), 2)

        days = [r.days_until_stockout for r in inventory_items if r.days_until_stockout is not None]
        avg_days_until_stockout = round(sum(days)/len(days), 2) if days else 0.0

        # Health breakdown
        health_counts = {
            "Healthy": len([r for r in inventory_items if r.health == "Healthy"]),
            "Shortage Risk": len([r for r in inventory_items if r.health == "Shortage Risk"]),
            "Slow Movers": len([r for r in inventory_items if r.health == "Slow Movers"]),
            "Overstock": len([r for r in inventory_items if r.health == "Overstock"])
        }
        health_breakdown = {cat: {"count": cnt, "percent": round(cnt/total_skus*100,2)} for cat, cnt in health_counts.items()}

        replenishment_need_total = round(sum(max(0.0, r.forecasted_demand - (r.current_stock or 0.0)) for r in inventory_items), 2)
        revenue_at_risk = round(sum(max(0.0, r.forecasted_demand - (r.current_stock or 0.0)) * (r.avg_price or 0.0) for r in inventory_items), 2)

        return {
            "total_skus": total_skus,
            "total_forecasted_demand": total_forecasted_demand,
            "total_historical_demand": total_historical_demand,
            "total_revenue": total_revenue,
            "avg_days_until_stockout": avg_days_until_stockout,
            "health_breakdown": health_breakdown,
            "replenishment_need_total": int(round(replenishment_need_total)),
            "revenue_at_risk": revenue_at_risk
        }
