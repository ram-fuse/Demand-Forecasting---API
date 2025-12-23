"""
Demand Forecasting Script for Braxton Monthly Data
Converted from forecast_braxton_monthly.ipynb

This script performs time series forecasting using Prophet, ARIMA, and SARIMA models
to predict monthly unit sales for SKU BXCM5157.
"""

# =============================================================================
# IMPORTS
# =============================================================================
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import STL
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

from prophet import Prophet
import requests


# =============================================================================
# CONFIGURATION
# =============================================================================

# ===== CHOOSE FORECAST MODE =====
FORECAST_MODE = "MULTI"  # Options: "SINGLE" or "MULTI"

# ===== SINGLE SKU MODE =====
SINGLE_SKU_ID = "BXCM5157"  # SKU to analyze in single mode

# ===== MULTI SKU MODE =====
# MULTI_SKU_LIST = ["BXCM5157", "BXCM1783", "BXCL1785", "BXCM3934", "BXCM5353"]  # List of SKUs for multi mode
MULTI_SKU_LIST = ["BXCM5157", "BXCM3765", "BXCM1634", "BXCM5776", "BXCM4486"]
# MULTI_SKU_LIST = ["BXCM5157"]
# Set to None to auto-select top N SKUs by total sales
TOP_N_SKUS = 10  # Used if MULTI_SKU_LIST is None

# ===== GENERAL SETTINGS =====
FILE_PATH = "C:\\Users\\ramme\\OneDrive\\Desktop\\Demand-Forecasting\\notebooks\\Braxton_data_May07_2024_dec16_2025_complete.csv"
GEO_FILE_PATH = "C:\\Users\\ramme\\OneDrive\\Desktop\\Demand-Forecasting\\notebooks\\Braxton_data_jan_2024_dec16_2025.csv"  # Contains postal code and city data
TEST_PERIOD = 5  # days for testing
FORECAST_PERIOD = 30  # 30 days forecast
SEASONAL_PERIOD = 7  # weekly seasonality
OLLAMA_MODEL = "gemma:7b"
OLLAMA_URL = "http://localhost:11434/api/generate"


# =============================================================================
# CUSTOM METRICS
# =============================================================================
def mape(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    return np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-8))) * 100

def mase(y_true, y_pred, y_train):
    naive_error = np.mean(np.abs(y_train[1:] - y_train[:-1]))
    model_error = np.mean(np.abs(y_true - y_pred))
    return model_error / naive_error

def rmse(y_true, y_pred):
    return np.sqrt(mean_squared_error(y_true, y_pred))


# =============================================================================
# OLLAMA GEMMA AI INTEGRATION
# =============================================================================
def query_ollama_gemma(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Query Ollama Gemma for AI insights."""
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "No response generated")
    
    except requests.exceptions.ConnectionError:
        return "ERROR: Cannot connect to Ollama. Ensure Ollama is running (ollama serve)"
    except requests.exceptions.Timeout:
        return "ERROR: Request timed out. Gemma may be processing."
    except Exception as e:
        return f"ERROR: {str(e)}"


def get_ai_forecast_insights(metrics_df: pd.DataFrame, monthly_df: pd.DataFrame,
                             future_dates: pd.DatetimeIndex,
                             prophet_6: pd.DataFrame, arima_6: pd.Series, sarima_6: np.ndarray) -> str:
    """Generate AI insights about forecasts using Gemma."""
    
    best_model = metrics_df.loc[metrics_df['MAE'].idxmin(), 'Model']
    best_mae = metrics_df['MAE'].min()
    best_rmse = metrics_df.loc[metrics_df['MAE'].idxmin(), 'RMSE']
    
    hist_mean = monthly_df['unit_sold'].mean()
    hist_std = monthly_df['unit_sold'].std()
    hist_trend = "increasing" if monthly_df['unit_sold'].iloc[-1] > monthly_df['unit_sold'].iloc[0] else "decreasing"
    
    prophet_avg = prophet_6['yhat'].mean()
    arima_avg = arima_6.mean()
    sarima_avg = sarima_6.mean()
    
    # Total forecast demand
    prophet_total = prophet_6['yhat'].sum()
    arima_total = arima_6.sum()
    sarima_total = sarima_6.sum()
    
    summary = f"""DEMAND FORECAST ANALYSIS - SKU {SKU_ID}
{'='*60}

HISTORICAL DATA:
- Observations: {len(monthly_df)} days
- Average daily demand: {hist_mean:.1f} units/day
- Volatility (std): {hist_std:.1f}
- Trend: {hist_trend}
- Latest demand: {monthly_df['unit_sold'].iloc[-1]:.0f} units

MODEL PERFORMANCE:
{metrics_df.to_string(index=False)}

Best: {best_model} (MAE={best_mae:.2f}, RMSE={best_rmse:.2f})

30-DAY FORECAST SUMMARY:
- Prophet: {prophet_total:.0f} units total ({prophet_avg:.1f}/day avg)
- ARIMA: {arima_total:.0f} units total ({arima_avg:.1f}/day avg)
- SARIMA: {sarima_total:.0f} units total ({sarima_avg:.1f}/day avg)

Forecast Period: {future_dates[0].strftime('%Y-%m-%d')} to {future_dates[-1].strftime('%Y-%m-%d')}

First 7 days breakdown:"""
    
    for i in range(min(7, len(future_dates))):
        date = future_dates[i]
        summary += f"\n{date.strftime('%Y-%m-%d')}: Prophet={prophet_6['yhat'].iloc[i]:.0f}, ARIMA={arima_6.iloc[i]:.0f}, SARIMA={sarima_6[i]:.0f}"
    
    if len(future_dates) > 7:
        summary += f"\n... (showing first 7 of {len(future_dates)} days)"
    
    prompt = f"""You are a demand forecasting expert for SKU-level inventory management. Analyze this 30-day forecast.

{summary}

Provide:
1. Model Recommendation: Which model to trust for daily forecasting?
2. Demand Outlook: Expected demand patterns over next 30 days
3. Inventory Strategy: Daily/weekly stocking recommendations
4. Business Action: Procurement and replenishment strategy
5. Risks: Key uncertainties (stockouts, overstocking)
6. Top 3 Actions: Immediate next steps

Be concise and actionable."""
    
    print("\n" + "="*60)
    print("🤖 Querying Gemma 7B for AI insights...")
    print("="*60 + "\n")
    
    return query_ollama_gemma(prompt)


# =============================================================================
# DATA LOADING & PREPROCESSING
# =============================================================================
def load_and_prepare_data(sku_id):
    """Load and preprocess the Braxton data with geographic information"""
    # Load main sales data
    df = pd.read_csv(FILE_PATH)
    df.rename(columns={"Date": "Day", "unit_sold": "unit_sold"}, inplace=True)
    df["Day"] = pd.to_datetime(df["Day"])
    df["unit_sold"] = pd.to_numeric(df["unit_sold"], errors="coerce")
    
    # Load geographic data
    geo_df = pd.read_csv(GEO_FILE_PATH)
    geo_df.rename(columns={"Date": "Day"}, inplace=True)
    geo_df["Day"] = pd.to_datetime(geo_df["Day"])
    
    # Merge datasets to get location information
    df_merged = pd.merge(
        df,
        geo_df[["Day", "sku_id", "customer_city", "customer_postal_code", "customer_type"]],
        on=["Day", "sku_id"],
        how="left"
    )
    
    # Select specific SKU
    df_sku = df_merged[df_merged["sku_id"] == sku_id].copy()
    
    # Aggregate daily data (keeping location info)
    daily_df = df_sku.groupby("Day").agg({
        "unit_sold": "sum"
    }).reset_index()
    daily_df = daily_df.sort_values("Day").reset_index(drop=True)
    
    # Get location distribution for this SKU
    location_data = df_sku.copy()
    
    return daily_df, location_data


def get_top_skus(n=10):
    """Get top N SKUs by total sales volume"""
    df = pd.read_csv(FILE_PATH)
    df.rename(columns={"Date": "Day", "unit_sold": "unit_sold"}, inplace=True)
    df["unit_sold"] = pd.to_numeric(df["unit_sold"], errors="coerce")
    
    top_skus = df.groupby("sku_id")["unit_sold"].sum().sort_values(ascending=False).head(n)
    return top_skus.index.tolist()


# =============================================================================
# EXPLORATORY DATA ANALYSIS
# =============================================================================
def plot_histogram(monthly_df):
    """Plot histogram of daily unit_sold"""
    plt.figure()
    plt.hist(monthly_df["unit_sold"], bins=30)
    plt.title(f"Histogram: Daily Demand - SKU {SKU_ID}")
    plt.xlabel("unit_sold")
    plt.ylabel("Frequency")
    plt.show()


def plot_trend(monthly_df, sku_id):
    """Plot daily trend"""
    plt.figure(figsize=(10, 5))
    plt.plot(monthly_df["Day"], monthly_df["unit_sold"])
    plt.title(f"Daily Demand Trend - SKU {sku_id}", fontsize=14, fontweight='bold')
    plt.xlabel("Date")
    plt.ylabel("Units Sold")
    plt.show()


def plot_rolling_mean(monthly_df):
    """Plot rolling mean"""
    plt.figure()
    plt.plot(monthly_df["Day"], monthly_df["unit_sold"], label="Daily")
    plt.plot(monthly_df["Day"], monthly_df["unit_sold"].rolling(7).mean(), label="7-day MA")
    plt.legend()
    plt.title("Trend & Smoothing")
    plt.show()


def plot_stl_decomposition(monthly_df):
    """Perform and plot STL decomposition"""
    stl = STL(monthly_df.set_index("Day")["unit_sold"], period=SEASONAL_PERIOD)
    res = stl.fit()

    res.trend.plot(title="STL Trend")
    plt.show()

    res.seasonal.plot(title="STL Seasonality")
    plt.show()

    res.resid.plot(title="STL Residuals")
    plt.show()


def analyze_day_of_week(monthly_df):
    """Analyze demand patterns by day of week"""
    tmp = monthly_df.copy()
    tmp["dow_name"] = tmp["Day"].dt.day_name()
    tmp["dow"] = tmp["Day"].dt.dayofweek  # Monday=0 ... Sunday=6

    # Order Monday → Sunday
    order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    # 1) Average demand by day of week
    dow_mean = (tmp.groupby("dow_name")["unit_sold"]
                  .mean()
                  .reindex(order))

    plt.figure()
    plt.bar(dow_mean.index, dow_mean.values)
    plt.title("Average Daily Demand by Day of Week")
    plt.xlabel("Day of Week")
    plt.ylabel("Avg unit_sold")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()

    # Print best day
    best_day = dow_mean.idxmax()
    print(f"Highest average demand: {best_day} ({dow_mean.max():.2f})")

    # 3) Distribution view: boxplot by day of week
    data = [tmp.loc[tmp["dow_name"] == d, "unit_sold"].dropna().values for d in order]

    plt.figure()
    plt.boxplot(data, labels=order, showfliers=False)
    plt.title("Demand Distribution by Day of Week (Boxplot)")
    plt.xlabel("Day of Week")
    plt.ylabel("unit_sold")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()

def plot_category_demand_bar(df):
    """
    Plot total units sold per category
    """
    category_demand = (
        df.groupby("category")["unit_sold"]
          .sum()
          .sort_values(ascending=False)
    )

    plt.figure(figsize=(14, 7))
    bars = plt.bar(
        category_demand.index,
        category_demand.values,
        edgecolor="black",
        linewidth=1.5
    )

    plt.xlabel("Category", fontsize=12, fontweight="bold")
    plt.ylabel("Total Units Sold", fontsize=12, fontweight="bold")
    plt.title("Historical Sales by Category", fontsize=15, fontweight="bold")
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", alpha=0.3)

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            height,
            f"{height:.0f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold"
        )

    plt.tight_layout()
    plt.savefig("category_demand_bar.png", dpi=300, bbox_inches="tight")
    print("  ✅ Saved: category_demand_bar.png")
    plt.show()



def plot_geographic_histogram(location_data, sku_id):
    """Plot geographic distribution histogram"""
    
    # Top cities by total demand
    city_demand = location_data.groupby("customer_city")["unit_sold"].sum().sort_values(ascending=False).head(20)
    
    plt.figure(figsize=(14, 8))
    
    # Create color gradient
    colors = plt.cm.YlOrRd(np.linspace(0.4, 0.9, len(city_demand)))
    
    bars = plt.barh(range(len(city_demand)), city_demand.values, color=colors, edgecolor='black', linewidth=1.5)
    plt.yticks(range(len(city_demand)), city_demand.index, fontsize=11)
    plt.xlabel("Total Units Sold", fontsize=12, fontweight='bold')
    plt.ylabel("City", fontsize=12, fontweight='bold')
    plt.title(f"Geographic Distribution: Top 20 Cities by Demand - SKU {sku_id}", 
             fontsize=14, fontweight='bold', pad=20)
    plt.gca().invert_yaxis()
    
    # Add value labels on bars
    for i, (city, value) in enumerate(city_demand.items()):
        plt.text(value, i, f'  {value:.0f}', 
                va='center', fontsize=10, fontweight='bold')
    
    # Add grid
    plt.grid(axis='x', alpha=0.3, linestyle='--')
    
    # Add summary text box
    total_cities = location_data['customer_city'].nunique()
    total_postal = location_data['customer_postal_code'].nunique()
    total_demand = location_data['unit_sold'].sum()
    top_city_pct = (city_demand.values[0] / total_demand) * 100
    
    summary_text = f"""Total Cities: {total_cities}
Total Postal Codes: {total_postal}
Top City: {city_demand.index[0]} ({top_city_pct:.1f}% of demand)"""
    
    plt.text(0.98, 0.02, summary_text,
            transform=plt.gca().transAxes,
            verticalalignment='bottom',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9, edgecolor='black', linewidth=2),
            fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(f'geographic_distribution_{sku_id}.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Saved: geographic_distribution_{sku_id}.png")
    plt.show()
    
    # Print summary
    print(f"\n  Geographic Summary for {sku_id}:")
    print(f"  - Total cities: {total_cities}")
    print(f"  - Top city: {city_demand.index[0]} ({city_demand.values[0]:.0f} units)")


def plot_acf_pacf(monthly_df):
    """Plot ACF and PACF"""
    plot_acf(monthly_df["unit_sold"], lags=7)
    plt.show()

    plot_pacf(monthly_df["unit_sold"], lags=7)
    plt.show()


# =============================================================================
# TRAIN/TEST SPLIT
# =============================================================================
def split_train_test(monthly_df):
    """Split data into train and test sets"""
    train = monthly_df.iloc[:-TEST_PERIOD]
    test = monthly_df.iloc[-TEST_PERIOD:]

    print(f"\nTrain size: {len(train)}, Test size: {len(test)}")
    
    return train, test


# =============================================================================
# PROPHET MODEL
# =============================================================================
def train_prophet_model(train, test):
    """Train and evaluate Prophet model"""
    prophet_train = train.rename(
        columns={"Day": "ds", "unit_sold": "y"}
    )

    model_prophet = Prophet(
        yearly_seasonality=True
    )

    model_prophet.fit(prophet_train)
    
    # Predict on test
    prophet_test = test.rename(columns={"Day": "ds", "unit_sold": "y"})
    prophet_pred = model_prophet.predict(prophet_test)

    print("\nProphet predictions:")
    print(prophet_pred)

    # Evaluate
    prophet_mae = mean_absolute_error(prophet_test["y"], prophet_pred["yhat"])
    prophet_rmse = rmse(prophet_test["y"], prophet_pred["yhat"])

    print(f"Prophet  → MAE: {prophet_mae:.2f}, RMSE: {prophet_rmse:.2f}")
    
    return model_prophet, prophet_pred, prophet_mae, prophet_rmse


# =============================================================================
# ARIMA MODEL
# =============================================================================
def train_arima_model(train, test):
    """Train and evaluate ARIMA model"""
    y_train = train["unit_sold"].astype(float).values
    y_test  = test["unit_sold"].astype(float).values
    
    arima_order = (1, 1, 1)

    arima = ARIMA(
        train["unit_sold"],
        order=arima_order,
    )

    arima_fit = arima.fit()

    arima_test_pred = arima_fit.forecast(
        steps=TEST_PERIOD,
    )
    
    # Evaluate
    arima_mae = mean_absolute_error(y_test, arima_test_pred)
    arima_rmse = rmse(y_test, arima_test_pred)

    print(f"\nARIMA{arima_order} → MAE: {arima_mae:.2f}, RMSE: {arima_rmse:.2f}")
    
    return arima_fit, arima_test_pred, arima_mae, arima_rmse, y_test


# =============================================================================
# SARIMA MODEL
# =============================================================================
def train_sarima_model(train, test, y_test):
    """Train and evaluate SARIMA model"""
    y_train = train["unit_sold"].astype(float).values
    
    sarima_order = (1, 1, 1)
    seasonal_order = (1, 1, 1, 7)

    sarima_model = SARIMAX(
        y_train,
        order=sarima_order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False
    )

    sarima_fit = sarima_model.fit()

    # Forecast for test window
    sarima_test_pred = sarima_fit.forecast(steps=TEST_PERIOD)
    
    # Evaluate
    sarima_mae = mean_absolute_error(y_test, sarima_test_pred)
    sarima_rmse = rmse(y_test, sarima_test_pred)

    print("\nSARIMA MODEL PERFORMANCE")
    print("------------------------------------")
    print(f"SARIMA{sarima_order}{seasonal_order} → "
          f"MAE: {sarima_mae:.2f},"
          f"RMSE: {sarima_rmse:.2f}")
    
    return sarima_fit, sarima_test_pred, sarima_mae, sarima_rmse


# =============================================================================
# VISUALIZATION: TEST PREDICTIONS
# =============================================================================
def plot_test_predictions(monthly_df, test, arima_test_pred, prophet_pred, sarima_test_pred):
    """Plot historical data vs test predictions"""
    plt.figure()

    # Plot full actual series (continuous)
    plt.plot(monthly_df["Day"], monthly_df["unit_sold"], label="Actual", color="black")

    # Highlight test period
    plt.axvspan(
        test["Day"].min(),
        test["Day"].max(),
        color="gray",
        alpha=0.2,
        label="Test Window"
    )

    # Plot forecasts
    plt.plot(test["Day"], arima_test_pred, label="ARIMA Forecast", linestyle="--")
    plt.plot(test["Day"], prophet_pred["yhat"], label="Prophet Forecast", linestyle="--")
    plt.plot(test["Day"], sarima_test_pred, label="SARIMA Forecast", linestyle="--")

    plt.title("Historical vs Forecast (No Gap)")
    plt.xlabel("Day")
    plt.ylabel("unit_sold")
    plt.legend()
    plt.tight_layout()
    plt.show()


# =============================================================================
# 30-DAY FORECAST
# =============================================================================
def generate_6month_forecast(monthly_df, model_prophet, arima_fit=None, sarima_fit=None):
    """Generate 30-day forecasts"""
    future_dates = pd.date_range(
        start=monthly_df["Day"].max() + pd.Timedelta(days=1),
        periods=FORECAST_PERIOD,
        freq="D"  # Daily frequency
    )

    # Prophet
    future_prophet = pd.DataFrame({
        "ds": future_dates,
    })
    prophet_6 = model_prophet.predict(future_prophet)

    # ARIMA (optional)
    arima_6 = arima_fit.forecast(steps=FORECAST_PERIOD) if arima_fit else None

    # SARIMA (optional)
    sarima_6 = sarima_fit.forecast(steps=FORECAST_PERIOD) if sarima_fit else None
    
    return future_dates, prophet_6, arima_6, sarima_6


def plot_30day_forecast_histogram(future_dates, prophet_6, sku_id):
    """Plot 30-day forecast as histogram"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Left: Daily forecast histogram
    ax1.bar(future_dates, prophet_6["yhat"], color='steelblue', alpha=0.7, edgecolor='black')
    ax1.set_xlabel("Date", fontsize=12)
    ax1.set_ylabel("Predicted Units Sold", fontsize=12)
    ax1.set_title(f"30-Day Demand Forecast - SKU {sku_id}", fontsize=14, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add total forecast text
    total_forecast = prophet_6["yhat"].sum()
    avg_daily = prophet_6["yhat"].mean()
    ax1.text(0.02, 0.98, f"Total Forecast: {total_forecast:.0f} units\nDaily Average: {avg_daily:.1f} units",
            transform=ax1.transAxes,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8),
            fontsize=11, fontweight='bold')
    
    # Right: Weekly aggregated forecast
    forecast_df = pd.DataFrame({
        'Date': future_dates,
        'Forecast': prophet_6["yhat"]
    })
    forecast_df['Week'] = forecast_df['Date'].dt.isocalendar().week
    weekly_forecast = forecast_df.groupby('Week')['Forecast'].sum()
    
    weeks = [f"Week {i+1}" for i in range(len(weekly_forecast))]
    ax2.bar(weeks, weekly_forecast.values, color='coral', alpha=0.7, edgecolor='black')
    ax2.set_xlabel("Week", fontsize=12)
    ax2.set_ylabel("Predicted Units Sold", fontsize=12)
    ax2.set_title(f"Weekly Forecast Aggregation - SKU {sku_id}", fontsize=14, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for i, v in enumerate(weekly_forecast.values):
        ax2.text(i, v, f'{v:.0f}', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(f'30day_forecast_{sku_id}.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Saved: 30day_forecast_{sku_id}.png")
    plt.show()
    
    return total_forecast, avg_daily


def plot_multi_sku_comparison(sku_forecasts):
    """Plot comparison of multiple SKU forecasts"""
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], width_ratios=[1, 1], 
                          hspace=0.3, wspace=0.3)
    
    ax1 = fig.add_subplot(gs[0, 0])  # Top left
    ax2 = fig.add_subplot(gs[0, 1])  # Top right
    ax3 = fig.add_subplot(gs[1, :])  # Bottom spanning both columns
    
    # Extract data
    sku_ids = list(sku_forecasts.keys())
    total_forecasts = [sku_forecasts[sku]['total_forecast'] for sku in sku_ids]
    
    # 1. Total 30-Day Forecast Comparison (Top Left)
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(sku_ids)))
    bars1 = ax1.barh(sku_ids, total_forecasts, color=colors, edgecolor='black', linewidth=1.5)
    ax1.set_xlabel('Total 30-Day Forecast (Units)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('SKU', fontsize=12, fontweight='bold')
    ax1.set_title('30-Day Total Demand Forecast by SKU', fontsize=14, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)
    ax1.invert_yaxis()
    
    # Add value labels
    for i, (sku, value) in enumerate(zip(sku_ids, total_forecasts)):
        ax1.text(value, i, f'  {value:.0f}', va='center', fontweight='bold', fontsize=10)
    
    # 2. Top Geographic Locations Histogram (Top Right)
    # Combine all top cities with SKU labels
    all_city_data = []
    for sku in sku_ids:
        city = sku_forecasts[sku]['top_city']
        city_demand = sku_forecasts[sku]['top_city_demand']
        all_city_data.append({
            'city': city,
            'demand': city_demand,
            'sku': sku
        })
    
    # Sort by demand
    all_city_data_sorted = sorted(all_city_data, key=lambda x: x['demand'], reverse=True)
    
    cities = [d['city'] for d in all_city_data_sorted]
    demands = [d['demand'] for d in all_city_data_sorted]
    sku_labels = [d['sku'] for d in all_city_data_sorted]
    
    # Create color map for SKUs
    sku_color_map = {sku: colors[i] for i, sku in enumerate(sku_ids)}
    bar_colors = [sku_color_map[sku] for sku in sku_labels]
    
    bars2 = ax2.barh(range(len(cities)), demands, color=bar_colors, edgecolor='black', linewidth=1.5)
    ax2.set_yticks(range(len(cities)))
    ax2.set_yticklabels(cities, fontsize=10)
    ax2.set_xlabel('Total Units Sold (Historical)', fontsize=12, fontweight='bold')
    ax2.set_title('Top Geographic Locations by SKU', fontsize=14, fontweight='bold')
    ax2.grid(axis='x', alpha=0.3)
    ax2.invert_yaxis()
    
    # Add value labels and SKU tags
    for i, (city, demand, sku) in enumerate(zip(cities, demands, sku_labels)):
        ax2.text(demand, i, f'  {demand:.0f} ({sku})', va='center', fontweight='bold', fontsize=9)
    
    # 3. 30-Day Forecast Timeline Comparison (Bottom Middle - spanning full width)
    for i, sku in enumerate(sku_ids):
        future_dates = sku_forecasts[sku]['future_dates']
        forecast_values = sku_forecasts[sku]['forecast_values']
        ax3.plot(future_dates, forecast_values, marker='o', markersize=4, 
                label=sku, linewidth=2.5, color=colors[i])
    
    ax3.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Predicted Units', fontsize=12, fontweight='bold')
    ax3.set_title('30-Day Forecast Timeline Comparison', fontsize=14, fontweight='bold')
    ax3.legend(loc='best', fontsize=10, framealpha=0.9)
    ax3.grid(alpha=0.3)
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.suptitle('MULTI-SKU FORECAST COMPARISON DASHBOARD', fontsize=16, fontweight='bold', y=0.995)
    plt.savefig('multi_sku_comparison.png', dpi=300, bbox_inches='tight')
    print("\n  ✅ Saved: multi_sku_comparison.png")
    plt.show()


# =============================================================================
# MAIN EXECUTION
# =============================================================================
def forecast_single_sku(sku_id):
    """Forecast for a single SKU"""
    print(f"\n{'='*80}")
    print(f"FORECASTING SKU: {sku_id}")
    print(f"{'='*80}")
    
    # Load data
    print("\n[1/3] Loading data...")
    monthly_df, location_data = load_and_prepare_data(sku_id)
    print(f"  - Historical data: {len(monthly_df)} days")
    print(f"  - Date range: {monthly_df['Day'].min().date()} to {monthly_df['Day'].max().date()}")
    
    # Train model and forecast
    print("\n[2/3] Training model and generating forecast...")
    train, test = split_train_test(monthly_df)
    model_prophet, prophet_pred, prophet_mae, prophet_rmse = train_prophet_model(train, test)
    future_dates, prophet_6, _, _ = generate_6month_forecast(monthly_df, model_prophet)
    print(f"  - Model accuracy (MAE): {prophet_mae:.2f}")
    
    # Create visualizations
    print("\n[3/3] Creating visualizations...")
    print("\n  → Geographic Distribution:")
    plot_geographic_histogram(location_data, sku_id)
    
    print("\n  → 30-Day Forecast:")
    total_forecast, avg_daily = plot_30day_forecast_histogram(future_dates, prophet_6, sku_id)
    
    # Get top city
    city_demand = location_data.groupby("customer_city")["unit_sold"].sum().sort_values(ascending=False)
    top_city = city_demand.index[0]
    top_city_demand = city_demand.values[0]
    
    return {
        'sku_id': sku_id,
        'total_forecast': total_forecast,
        'avg_daily': avg_daily,
        'top_city': top_city,
        'top_city_demand': top_city_demand,
        'future_dates': future_dates,
        'forecast_values': prophet_6["yhat"].values,
        'total_cities': location_data['customer_city'].nunique()
    }


def forecast_multi_sku(sku_list):
    """Forecast for multiple SKUs"""
    print(f"\n{'='*80}")
    print(f"MULTI-SKU FORECAST MODE")
    print(f"Analyzing {len(sku_list)} SKUs")
    print(f"{'='*80}")
    
    sku_forecasts = {}
    
    for idx, sku in enumerate(sku_list, 1):
        print(f"\n[{idx}/{len(sku_list)}] Processing {sku}...")
        try:
            result = forecast_single_sku(sku)
            sku_forecasts[sku] = result
            print(f"  ✅ {sku} completed")
        except Exception as e:
            print(f"  ❌ Error processing {sku}: {str(e)}")
            continue
    
    # Create multi-SKU comparison dashboard
    if sku_forecasts:
        print(f"\n{'='*80}")
        print("Creating Multi-SKU Comparison Dashboard...")
        print(f"{'='*80}")
        plot_multi_sku_comparison(sku_forecasts)
    
    return sku_forecasts


def main():
    """Main execution function"""
    print("\n" + "="*80)
    print("SKU-LEVEL DEMAND FORECASTING WITH GEOGRAPHIC INTELLIGENCE")
    print("="*80)
    print(f"\nMode: {FORECAST_MODE}")
    print(f"Forecast Period: {FORECAST_PERIOD} days")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if FORECAST_MODE == "SINGLE":
        # Single SKU mode
        result = forecast_single_sku(SINGLE_SKU_ID)
        
        # Summary
        print(f"\n{'='*80}")
        print("FORECASTING SUMMARY")
        print(f"{'='*80}")
        print(f"SKU: {result['sku_id']}")
        print(f"30-Day Total Forecast: {result['total_forecast']:.0f} units")
        print(f"Daily Average: {result['avg_daily']:.1f} units/day")
        print(f"Top Geographic Location: {result['top_city']} ({result['top_city_demand']:.0f} units)")
        print(f"Total Cities: {result['total_cities']}")
        print(f"\nGenerated Files:")
        print(f"  1. geographic_distribution_{result['sku_id']}.png")
        print(f"  2. 30day_forecast_{result['sku_id']}.png")
        print(f"{'='*80}")
        
        return result
        
    elif FORECAST_MODE == "MULTI":
        # Multi SKU mode
        if MULTI_SKU_LIST:
            sku_list = MULTI_SKU_LIST
        else:
            print(f"\nAuto-selecting top {TOP_N_SKUS} SKUs by sales volume...")
            sku_list = get_top_skus(TOP_N_SKUS)
            print(f"Selected SKUs: {', '.join(sku_list)}")
        
        results = forecast_multi_sku(sku_list)
        
        # Summary
        print(f"\n{'='*80}")
        print("MULTI-SKU FORECASTING SUMMARY")
        print(f"{'='*80}")
        print(f"Total SKUs Analyzed: {len(results)}")
        print(f"\nForecast Summary:")
        for sku, data in results.items():
            print(f"  {sku}: {data['total_forecast']:.0f} units (avg: {data['avg_daily']:.1f}/day)")
        print(f"\nGenerated Files:")
        for sku in results.keys():
            print(f"  - geographic_distribution_{sku}.png")
            print(f"  - 30day_forecast_{sku}.png")
        print(f"  - multi_sku_comparison.png")
        print(f"{'='*80}")
        
        return results
    
    else:
        print(f"\n❌ Invalid FORECAST_MODE: {FORECAST_MODE}")
        print("Please set FORECAST_MODE to either 'SINGLE' or 'MULTI'")
        return None
    
    print("\n✅ Forecasting complete! Files ready for client presentation.")
    print("="*80)


if __name__ == "__main__":
    results = main()
