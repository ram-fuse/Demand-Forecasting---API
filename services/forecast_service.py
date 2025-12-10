import base64
import io
import pandas as pd
from prophet import Prophet

class ForecastService:

    @staticmethod
    def decode_csv(base64_string: str) -> pd.DataFrame:
        """Decode base64 CSV into DataFrame."""
        try:
            decoded_bytes = base64.b64decode(base64_string)
            df = pd.read_csv(io.BytesIO(decoded_bytes))
            return df
        except Exception as e:
            raise ValueError(f"Failed to decode CSV: {e}")

    @staticmethod
    def preprocess(df: pd.DataFrame, sku_id: str) -> pd.DataFrame:
        """Prepare SKU-specific data for Prophet."""
        
        # Filter specific SKU
        df = df[df["sku_id"] == sku_id]
        if df.empty:
            raise ValueError(f"No data found for SKU: {sku_id}")

        # Rename required columns
        df = df.rename(columns={
            "Date": "ds",
            "units sold": "y"
        })

        # Convert ds to datetime
        df["ds"] = pd.to_datetime(df["ds"])

        # Convert promotions column to numeric
        if "promotions" in df.columns:
            df["promotions"] = df["promotions"].map({
                "On Promotion": 1,
                "Off Promotion": 0
            }).fillna(0)

        # Identify regressors
        regressors = []
        for col in ["promotions","is_holiday", "Customer Visits"]:
            if col in df.columns:
                regressors.append(col)

        return df, regressors

    @staticmethod
    def train_and_forecast(df: pd.DataFrame, regressors: list, periods: int):
        """Train prophet model and forecast future periods."""

        model = Prophet()

        # Add regressors
        for reg in regressors:
            model.add_regressor(reg)

        model.fit(df)

        # Create future DF
        future = model.make_future_dataframe(periods=periods, freq="D")

        # For regressors: repeat last known value
        for reg in regressors:
            future[reg] = df[reg].iloc[-1]

        forecast = model.predict(future)

        return forecast


# Backwards-compatible module-level functions for direct imports
def decode_csv(base64_string: str) -> pd.DataFrame:
    """Decode base64 CSV into DataFrame (module-level wrapper)."""
    return ForecastService.decode_csv(base64_string)


def preprocess(df: pd.DataFrame, sku_id: str):
    """Prepare SKU-specific data for Prophet (module-level wrapper)."""
    return ForecastService.preprocess(df, sku_id)


def train_and_forecast(df: pd.DataFrame, regressors: list, periods: int):
    """Train prophet model and forecast future periods (module-level wrapper)."""
    return ForecastService.train_and_forecast(df, regressors, periods)
