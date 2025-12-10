from typing import List, Dict, Any
import pandas as pd
from .forecast_service import ForecastService
from schema.inventory_health_response import InventoryItem


class InventoryService:

    @staticmethod
    def compute_for_sku(df: pd.DataFrame, sku_id: str, periods: int) -> InventoryItem:

        # Prepare DF
        df, regressors = ForecastService.preprocess(df, sku_id)

        # Forecast
        forecast = ForecastService.train_and_forecast(df, regressors, periods)

        future = forecast.tail(periods)
        forecasted_demand = float(future["yhat"].sum())

        # Price
        avg_price = float(df["unit_price"].mean()) if "unit_price" in df.columns else 0.0
        revenue = forecasted_demand * avg_price

        # Sales
        avg_daily_sales = float(df["y"].mean()) if "y" in df.columns else 0.0

        # Stock
        current_stock = float(df["stock_in_hand"].iloc[-1]) if "stock_in_hand" in df.columns else None

        if current_stock and avg_daily_sales > 0:
            days_until_stockout = current_stock / avg_daily_sales
        else:
            days_until_stockout = None

        # Health rules
        if days_until_stockout is None:
            health = "Unknown"
            action = "Investigate"
        elif avg_daily_sales < 1:
            health = "Slow Movers"
            action = "Pause Ordering"
        elif days_until_stockout <= 7:
            health = "Shortage Risk"
            action = "Accelerate Purchase Orders"
        elif days_until_stockout <= 30:
            health = "Replenish"
            action = "Replenish"
        elif days_until_stockout >= 90:
            health = "Overstock"
            action = "Pause Ordering"
        else:
            health = "Healthy"
            action = "No Action"

        return InventoryItem(
            sku_id=sku_id,
            forecasted_demand=round(forecasted_demand, 2),
            revenue=round(revenue, 2),
            health=health,
            action_replenishment=action,
            days_until_stockout=round(days_until_stockout, 2) if days_until_stockout else None,
            current_stock=current_stock,
            avg_daily_sales=round(avg_daily_sales, 4)
        )

    @staticmethod
    def compute_inventory_health(df: pd.DataFrame, periods: int, sku_id: str = None) -> List[InventoryItem]:
        results = []
        sku_list = [sku_id] if sku_id else sorted(df["sku_id"].dropna().unique().tolist())

        for sku in sku_list:
            try:
                results.append(InventoryService.compute_for_sku(df, sku, periods))
            except Exception as e:
                print(f"Error computing SKU {sku}: {e}")

        return results
