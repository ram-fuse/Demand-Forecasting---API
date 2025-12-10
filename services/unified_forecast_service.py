"""
Unified Forecast Service - Complete consolidated forecasting and inventory analysis.
Combines all forecasting logic, inventory health analysis, and unified response generation.
"""

import base64
import io
import pandas as pd
from prophet import Prophet
from typing import List, Dict, Tuple, Any, Optional
from schema.unified_response import (
    SKUHistoricalData, SKUInventoryData, SKUForecastData,
    SKUForecastDetail, SummaryMetrics, UnifiedForecastResponse
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
# INTERNAL INVENTORY ITEM (for intermediate calculations)
# ============================================================================

class InventoryItem:
    """Internal inventory analysis result"""
    def __init__(self, sku_id: str, forecasted_demand: float, historical_demand: float,
                 revenue: float, health: str, action_replenishment: str,
                 days_until_stockout: Optional[float], current_stock: Optional[float],
                 avg_daily_sales: float, time_filter: str, historical_days: int):
        self.sku_id = sku_id
        self.forecasted_demand = forecasted_demand
        self.historical_demand = historical_demand
        self.revenue = revenue
        self.health = health
        self.action_replenishment = action_replenishment
        self.days_until_stockout = days_until_stockout
        self.current_stock = current_stock
        self.avg_daily_sales = avg_daily_sales
        self.time_filter = time_filter
        self.historical_days = historical_days


# ============================================================================
# FORECASTING ENGINE (Prophet-based)
# ============================================================================

class ForecastingEngine:
    """Core forecasting using Facebook Prophet"""

    @staticmethod
    def decode_csv(base64_string: str) -> pd.DataFrame:
        """Decode base64-encoded CSV into DataFrame"""
        try:
            decoded_bytes = base64.b64decode(base64_string)
            df = pd.read_csv(io.BytesIO(decoded_bytes))
            return df
        except Exception as e:
            raise ValueError(f"Failed to decode CSV: {e}")

    @staticmethod
    def preprocess(df: pd.DataFrame, sku_id: str) -> Tuple[pd.DataFrame, list]:
        """
        Prepare SKU-specific data for Prophet forecasting.
        Returns: (preprocessed_df, list_of_regressors)
        """
        # Filter to specific SKU
        df = df[df["sku_id"] == sku_id].copy()
        if df.empty:
            raise ValueError(f"No data found for SKU: {sku_id}")

        # Rename columns to Prophet format
        df = df.rename(columns={
            "Date": "ds",
            "units sold": "y"
        })

        # Convert datetime
        df["ds"] = pd.to_datetime(df["ds"])

        # Convert promotions to numeric
        if "promotions" in df.columns:
            df["promotions"] = df["promotions"].map({
                "On Promotion": 1,
                "Off Promotion": 0
            }).fillna(0)

        # Identify available regressors
        regressors = []
        for col in ["promotions", "is_holiday", "Customer Visits", "unit_price"]:
            if col in df.columns:
                regressors.append(col)

        return df, regressors

    @staticmethod
    def train_and_forecast(df: pd.DataFrame, regressors: list, periods: int) -> pd.DataFrame:
        """
        Train Prophet model and generate forecast for specified periods.
        Returns: DataFrame with forecast predictions
        """
        model = Prophet()

        # Add regressors to model
        for reg in regressors:
            model.add_regressor(reg)

        # Fit model
        model.fit(df)

        # Create future dataframe
        future = model.make_future_dataframe(periods=periods, freq="D")

        # Fill regressor values (repeat last known values)
        for reg in regressors:
            future[reg] = df[reg].iloc[-1]

        # Generate forecast
        forecast = model.predict(future)
        return forecast


# ============================================================================
# INVENTORY HEALTH SERVICE
# ============================================================================

class InventoryService:
    """Compute inventory health metrics and status classification"""

    @staticmethod
    def _get_time_filter_config(time_filter: str) -> Dict[str, int]:
        """Get historical and forecast days for a given time filter"""
        return TIME_FILTER_CONFIG.get(time_filter, TIME_FILTER_CONFIG["1_week"])

    @staticmethod
    def compute_for_sku(df: pd.DataFrame, sku_id: str, time_filter: str) -> Tuple[InventoryItem, int, int]:
        """
        Compute inventory health metrics for a single SKU.
        
        Args:
            df: Full DataFrame with sales data
            sku_id: SKU identifier
            time_filter: Time range filter
            
        Returns:
            (InventoryItem with health metrics, historical_days_used, forecast_days)
        """
        config = InventoryService._get_time_filter_config(time_filter)
        historical_days = config["historical_days"]
        forecast_days = config["forecast_days"]

        # Preprocess SKU data
        df_sku, regressors = ForecastingEngine.preprocess(df, sku_id)

        # Keep only last N historical days
        df_sku = df_sku.sort_values("ds")
        if len(df_sku) > historical_days:
            df_sku = df_sku.tail(historical_days)

        # Generate forecast
        forecast = ForecastingEngine.train_and_forecast(df_sku, regressors, forecast_days)
        future = forecast.tail(forecast_days)

        # Calculate demand metrics
        forecasted_demand = float(future["yhat"].sum())
        historical_demand = float(df_sku["y"].sum()) if "y" in df_sku.columns else 0.0

        # Calculate financial metrics
        avg_price = float(df_sku["unit_price"].mean()) if "unit_price" in df_sku.columns else 0.0
        revenue = forecasted_demand * avg_price

        # Calculate sales metrics
        avg_daily_sales = float(df_sku["y"].mean()) if "y" in df_sku.columns else 0.0

        # Get current stock
        current_stock = float(df_sku["stock_in_hand"].iloc[-1]) if "stock_in_hand" in df_sku.columns else None

        # Calculate days until stockout
        if current_stock and avg_daily_sales > 0:
            days_until_stockout = current_stock / avg_daily_sales
        else:
            days_until_stockout = None

        # Health status rules (evaluated in order)
        if days_until_stockout is None:
            health = "Unknown"
            action = "Investigate"
        elif days_until_stockout <= 7:
            health = "Shortage Risk"
            action = "Accelerate Purchase Orders"
        elif days_until_stockout <= 30:
            health = "Replenish"
            action = "Replenish"
        elif days_until_stockout >= 90:
            health = "Overstock"
            action = "Pause Ordering"
        elif avg_daily_sales < 5:
            health = "Slow Movers"
            action = "Pause Ordering"
        else:
            health = "Healthy"
            action = "No Action"

        return InventoryItem(
            sku_id=sku_id,
            forecasted_demand=round(forecasted_demand, 2),
            historical_demand=round(historical_demand, 2),
            revenue=round(revenue, 2),
            health=health,
            action_replenishment=action,
            days_until_stockout=round(days_until_stockout, 2) if days_until_stockout else None,
            current_stock=current_stock,
            avg_daily_sales=round(avg_daily_sales, 4),
            time_filter=time_filter,
            historical_days=historical_days
        ), historical_days, forecast_days



# ============================================================================
# UNIFIED FORECAST SERVICE (Orchestrator)
# ============================================================================

class UnifiedForecastService:
    """
    Orchestrates complete forecast and inventory analysis.
    Combines forecasting, inventory health, and generates unified response.
    """

    @staticmethod
    def compute_unified_forecast(
        df: pd.DataFrame,
        sku_ids: Optional[List[str]] = None,
        data_range: str = "1_week"
    ) -> Tuple[Dict[str, SKUForecastDetail], Dict[str, Any]]:
        """
        Compute unified forecast for multiple SKUs with complete time-series data.
        
        Args:
            df: DataFrame with all sales data
            sku_ids: List of specific SKU IDs to analyze (None = all SKUs)
            data_range: Time filter for historical/forecast windows
        
        Returns:
            Tuple of (per_sku_forecasts, aggregated_summary)
        """
        # Get list of SKUs to process
        sku_list = sku_ids if sku_ids else sorted(df["sku_id"].dropna().unique().tolist())

        forecast_results = {}
        inventory_results = []

        # Process each SKU
        for sku in sku_list:
            try:
                # Get inventory health data
                inventory_item, hist_days, fc_days = InventoryService.compute_for_sku(
                    df, sku, data_range
                )

                # Get time filter config
                config = InventoryService._get_time_filter_config(data_range)
                historical_days = config["historical_days"]
                forecast_days = config["forecast_days"]

                # Prepare SKU data for forecasting
                df_sku, regressors = ForecastingEngine.preprocess(df, sku)

                # Extract historical period (last N days)
                df_sku = df_sku.sort_values("ds")
                if len(df_sku) > historical_days:
                    df_sku_hist = df_sku.tail(historical_days)
                else:
                    df_sku_hist = df_sku

                # Generate forecast
                forecast = ForecastingEngine.train_and_forecast(df_sku_hist, regressors, forecast_days)
                future = forecast.tail(forecast_days)

                # Extract time-series data
                # Historical demand
                historical_dates = df_sku_hist["ds"].dt.strftime("%Y-%m-%d").tolist()
                historical_values = df_sku_hist["y"].round(2).tolist()

                # Inventory levels
                inventory_dates = (
                    df_sku_hist["ds"].dt.strftime("%Y-%m-%d").tolist()
                    if "stock_in_hand" in df_sku_hist.columns
                    else []
                )
                inventory_values = (
                    df_sku_hist["stock_in_hand"].round(2).tolist()
                    if "stock_in_hand" in df_sku_hist.columns
                    else []
                )

                # Forecasted demand
                forecast_dates = future["ds"].dt.strftime("%Y-%m-%d").tolist()
                forecast_values = future["yhat"].round(2).tolist()

                # Build SKU forecast detail
                sku_detail = SKUForecastDetail(
                    historical=SKUHistoricalData(
                        dates=historical_dates,
                        values=historical_values
                    ),
                    inventory=SKUInventoryData(
                        dates=inventory_dates,
                        values=inventory_values
                    ),
                    forecast=SKUForecastData(
                        dates=forecast_dates,
                        values=forecast_values
                    ),
                    health_status=inventory_item.health,
                    action_replenishment=inventory_item.action_replenishment,
                    current_stock=inventory_item.current_stock,
                    avg_daily_sales=inventory_item.avg_daily_sales,
                    days_until_stockout=inventory_item.days_until_stockout,
                    forecasted_demand=inventory_item.forecasted_demand,
                    historical_demand=inventory_item.historical_demand,
                    revenue=inventory_item.revenue
                )

                forecast_results[sku] = sku_detail
                inventory_results.append(inventory_item)

            except Exception as e:
                print(f"Error processing SKU {sku}: {e}")

        # Calculate aggregated summary
        summary = UnifiedForecastService._calculate_summary(inventory_results)

        return forecast_results, summary

    @staticmethod
    def _calculate_summary(inventory_items: List[InventoryItem]) -> Dict[str, Any]:
        """
        Calculate aggregated summary metrics across all SKUs.
        
        Args:
            inventory_items: List of InventoryItem objects
            
        Returns:
            Dictionary with aggregated metrics
        """
        if not inventory_items:
            return {
                "total_skus": 0,
                "total_forecasted_demand": 0.0,
                "total_historical_demand": 0.0,
                "total_revenue": 0.0,
                "avg_days_until_stockout": 0.0,
                "health_breakdown": {
                    "Healthy": 0,
                    "Replenish": 0,
                    "Shortage Risk": 0,
                    "Slow Movers": 0,
                    "Overstock": 0,
                    "Unknown": 0
                }
            }

        return {
            "total_skus": len(inventory_items),
            "total_forecasted_demand": round(sum(r.forecasted_demand for r in inventory_items), 2),
            "total_historical_demand": round(sum(r.historical_demand for r in inventory_items), 2),
            "total_revenue": round(sum(r.revenue for r in inventory_items), 2),
            "avg_days_until_stockout": round(
                sum([r.days_until_stockout for r in inventory_items if r.days_until_stockout])
                / len([r for r in inventory_items if r.days_until_stockout])
                if any(r.days_until_stockout for r in inventory_items)
                else 0,
                2
            ),
            "health_breakdown": {
                "Healthy": len([r for r in inventory_items if r.health == "Healthy"]),
                "Replenish": len([r for r in inventory_items if r.health == "Replenish"]),
                "Shortage Risk": len([r for r in inventory_items if r.health == "Shortage Risk"]),
                "Slow Movers": len([r for r in inventory_items if r.health == "Slow Movers"]),
                "Overstock": len([r for r in inventory_items if r.health == "Overstock"]),
                "Unknown": len([r for r in inventory_items if r.health == "Unknown"])
            }
        }

