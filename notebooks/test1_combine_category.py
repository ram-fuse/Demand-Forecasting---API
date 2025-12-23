"""
Demand Forecasting Script for Braxton Daily Data (Category-Based)

This script performs time series forecasting using Prophet, ARIMA, and SARIMA models
to predict daily unit sales for a CATEGORY.

Key fixes included:
- Uses `category` instead of `sku_id`
- Filters ONLY rows where category is present (handles true NaN and string "nan"/"null"/etc.)
- Normalizes category values (strip + lowercase) for robust matching
- Drops rows where Day or unit_sold are NaN
- Raises a helpful error if a category name isn't found (shows sample of actual categories)
"""

# =============================================================================
# IMPORTS
# =============================================================================
import warnings
warnings.filterwarnings("ignore")

import re
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

# ===== SINGLE CATEGORY MODE =====
SINGLE_CATEGORY = "Sofas"

MULTI_CATEGORY_LIST = [
    "Beds",
    "Dressers & Chests",
    "Nightstands"
]

TOP_N_CATEGORIES = 10

# ===== GENERAL SETTINGS =====
FILE_PATH = "C:\\Users\\ramme\\OneDrive\\Desktop\\Demand-Forecasting\\notebooks\\Braxton_data_May07_2024_dec16_2025_complete_category_included.csv"
GEO_FILE_PATH = "C:\\Users\\ramme\\OneDrive\\Desktop\\Demand-Forecasting\\notebooks\\Braxton_data_jan_2024_dec16_2025_category_included.csv"  # Contains postal code and city data
TEST_PERIOD = 5          # days for testing
FORECAST_PERIOD = 30     # 30 days forecast
SEASONAL_PERIOD = 7      # weekly seasonality

# (Optional AI integration)
OLLAMA_MODEL = "gemma:7b"
OLLAMA_URL = "http://localhost:11434/api/generate"


# =============================================================================
# HELPERS
# =============================================================================
def resolve_categories(requested, top_n_fallback=10):
    """Keep only requested categories that exist; if none exist, fallback to top N."""
    df = pd.read_csv(FILE_PATH)
    df = filter_category_present(df)
    df["category_norm"] = df["category"].apply(normalize_category)

    valid_map = {}  # norm -> original (first seen)
    for orig, norm in zip(df["category"].astype(str).str.strip(), df["category_norm"]):
        valid_map.setdefault(norm, orig)

    resolved = []
    for c in (requested or []):
        norm = normalize_category(c)
        if norm in valid_map:
            resolved.append(valid_map[norm])

    resolved = list(dict.fromkeys(resolved))  # de-dup preserve order

    if len(resolved) == 0:
        print(f"\n⚠️ None of the provided categories exist in the data. Falling back to top {top_n_fallback} categories.")
        resolved = get_top_categories(top_n_fallback)

    return resolved


def sanitize_filename(text: str) -> str:
    """Make a safe filename token from category names."""
    text = str(text)
    text = re.sub(r"\s+", "_", text.strip())
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", text)


def normalize_category(s) -> str:
    """Normalize category values for safe matching."""
    return str(s).strip().lower()


def filter_category_present(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only rows where category is truly present:
    - Not NaN
    - Not blank
    - Not 'nan', 'none', 'null', 'na', 'n/a' as strings
    """
    if "category" not in df.columns:
        raise KeyError("Expected a column named 'category' in the dataset.")

    cat_str = df["category"].astype(str).str.strip()
    bad = cat_str.str.lower().isin({"", "nan", "none", "null", "na", "n/a"})
    keep = df["category"].notna() & (~bad)
    return df.loc[keep].copy()


def debug_categories(top_n: int = 30):
    """
    Quick diagnostic tool: prints the most common categories present in FILE_PATH,
    after cleaning (strip + removing NaN-like entries).
    """
    df = pd.read_csv(FILE_PATH)
    print("\n" + "="*80)
    print("DEBUG: CATEGORY CHECK")
    print("="*80)
    print("Columns:", df.columns.tolist())

    if "category" not in df.columns:
        print("❌ No 'category' column found. Check spelling/case in your CSV.")
        return

    df = filter_category_present(df)
    cat_clean = df["category"].astype(str).str.strip()

    print(f"\nTop {top_n} categories by row count (cleaned):")
    print(cat_clean.value_counts().head(top_n))


# =============================================================================
# CUSTOM METRICS
# =============================================================================
def rmse(y_true, y_pred):
    return np.sqrt(mean_squared_error(y_true, y_pred))


# =============================================================================
# OLLAMA GEMMA AI INTEGRATION (OPTIONAL)
# =============================================================================
def query_ollama_gemma(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Query Ollama Gemma for AI insights."""
    try:
        payload = {"model": model, "prompt": prompt, "stream": False}
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


# =============================================================================
# DATA LOADING & PREPROCESSING (CATEGORY-BASED)
# =============================================================================
def load_and_prepare_data(category: str):
    """
    Load and preprocess Braxton data with geographic information (by category).

    IMPORTANT:
    - Forecasting does NOT require GEO_FILE_PATH, but geographic charts do.
    - If GEO_FILE_PATH does not contain 'category', geo merge will fail.
    """
    # Load main sales data
    df = pd.read_csv(FILE_PATH)
    df.rename(columns={"Date": "Day"}, inplace=True)
    df["Day"] = pd.to_datetime(df["Day"], errors="coerce")
    df["unit_sold"] = pd.to_numeric(df["unit_sold"], errors="coerce")

    # Filter rows where category is truly present
    df = filter_category_present(df)

    # Normalize category for matching
    df["category_norm"] = df["category"].apply(normalize_category)

    # Drop invalid Day/unit_sold
    df = df.dropna(subset=["Day", "unit_sold"])

    # Select requested category (robust match)
    cat_key = normalize_category(category)
    df_cat_base = df[df["category_norm"] == cat_key].copy()

    if df_cat_base.empty:
        # Show a helpful sample of actual categories in the dataset
        sample = df["category"].astype(str).str.strip().value_counts().head(15)
        raise ValueError(
            f"No rows found for category '{category}'. "
            f"Check spelling/case. Sample categories in file: {list(sample.index)}"
        )

    # Load geographic data (optional for location analytics)
    geo_df = pd.read_csv(GEO_FILE_PATH)
    geo_df.rename(columns={"Date": "Day"}, inplace=True)
    geo_df["Day"] = pd.to_datetime(geo_df["Day"], errors="coerce")

    geo_df = filter_category_present(geo_df)
    geo_df["category_norm"] = geo_df["category"].apply(normalize_category)
    geo_df = geo_df.dropna(subset=["Day"])

    # Merge to get location info (category-level)
    # Note: This assumes GEO_FILE_PATH includes customer_city/postal/type columns.
    df_merged = pd.merge(
        df_cat_base,
        geo_df[["Day", "category_norm", "customer_city", "customer_postal_code", "customer_type"]],
        on=["Day", "category_norm"],
        how="left"
    )

    # Aggregate daily demand for category
    daily_df = (
        df_merged.groupby("Day", as_index=False)["unit_sold"]
        .sum()
        .sort_values("Day")
        .reset_index(drop=True)
    )

    # If sum produced NaNs (rare), drop them
    daily_df = daily_df.dropna(subset=["unit_sold"])

    location_data = df_merged.copy()
    return daily_df, location_data


def get_top_categories(n=10):
    """Get top N categories by total sales volume (unit_sold)."""
    df = pd.read_csv(FILE_PATH)
    df.rename(columns={"Date": "Day"}, inplace=True)
    df["unit_sold"] = pd.to_numeric(df["unit_sold"], errors="coerce")

    df = filter_category_present(df)
    df = df.dropna(subset=["unit_sold"])

    top = df.groupby("category")["unit_sold"].sum().sort_values(ascending=False).head(n)
    return top.index.tolist()


# =============================================================================
# TRAIN/TEST SPLIT
# =============================================================================
def split_train_test(daily_df):
    train = daily_df.iloc[:-TEST_PERIOD]
    test = daily_df.iloc[-TEST_PERIOD:]
    print(f"\nTrain size: {len(train)}, Test size: {len(test)}")
    return train, test


# =============================================================================
# PROPHET MODEL
# =============================================================================
def train_prophet_model(train, test):
    """
    Train and evaluate Prophet model.
    Prophet requires at least 2 non-NaN rows for y.
    """
    prophet_train = train.rename(columns={"Day": "ds", "unit_sold": "y"})
    prophet_train = prophet_train.dropna(subset=["ds", "y"])

    model_prophet = Prophet(yearly_seasonality=True)
    model_prophet.fit(prophet_train)

    prophet_test = test.rename(columns={"Day": "ds", "unit_sold": "y"}).dropna(subset=["ds", "y"])
    prophet_pred = model_prophet.predict(prophet_test)

    prophet_mae = mean_absolute_error(prophet_test["y"], prophet_pred["yhat"]) if len(prophet_test) else np.nan
    prophet_rmse = rmse(prophet_test["y"], prophet_pred["yhat"]) if len(prophet_test) else np.nan
    print(f"Prophet  → MAE: {prophet_mae:.2f}, RMSE: {prophet_rmse:.2f}")

    return model_prophet, prophet_pred, prophet_mae, prophet_rmse


# =============================================================================
# 30-DAY FORECAST
# =============================================================================
def generate_30day_forecast(daily_df, model_prophet):
    future_dates = pd.date_range(
        start=daily_df["Day"].max() + pd.Timedelta(days=1),
        periods=FORECAST_PERIOD,
        freq="D"
    )

    future_prophet = pd.DataFrame({"ds": future_dates})
    prophet_30 = model_prophet.predict(future_prophet)

    return future_dates, prophet_30


def plot_geographic_histogram(location_data, category):
    """Plot geographic distribution histogram for a category."""
    if "customer_city" not in location_data.columns:
        print("⚠️ customer_city not found in merged data. Skipping geo chart.")
        return

    city_demand = (
        location_data.dropna(subset=["customer_city"])
        .groupby("customer_city")["unit_sold"]
        .sum()
        .sort_values(ascending=False)
        .head(20)
    )

    if city_demand.empty:
        print("⚠️ No geographic info available for this category. Skipping geo chart.")
        return

    plt.figure(figsize=(14, 8))
    colors = plt.cm.YlOrRd(np.linspace(0.4, 0.9, len(city_demand)))
    plt.barh(range(len(city_demand)), city_demand.values, color=colors, edgecolor='black', linewidth=1.5)
    plt.yticks(range(len(city_demand)), city_demand.index, fontsize=11)
    plt.xlabel("Total Units Sold", fontsize=12, fontweight='bold')
    plt.ylabel("City", fontsize=12, fontweight='bold')
    plt.title(f"Geographic Distribution: Top 20 Cities by Demand - Category {category}",
              fontsize=14, fontweight='bold', pad=20)
    plt.gca().invert_yaxis()

    for i, (city, value) in enumerate(city_demand.items()):
        plt.text(value, i, f'  {value:.0f}', va='center', fontsize=10, fontweight='bold')

    plt.grid(axis='x', alpha=0.3, linestyle='--')
    plt.tight_layout()

    safe = sanitize_filename(category)
    plt.savefig(f'geographic_distribution_category_{safe}.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Saved: geographic_distribution_category_{safe}.png")
    plt.show()


def plot_30day_forecast_histogram(future_dates, prophet_30, category):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    ax1.bar(future_dates, prophet_30["yhat"], alpha=0.7, edgecolor='black')
    ax1.set_xlabel("Date", fontsize=12)
    ax1.set_ylabel("Predicted Units Sold", fontsize=12)
    ax1.set_title(f"30-Day Demand Forecast - Category {category}", fontsize=14, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    total_forecast = prophet_30["yhat"].sum()
    avg_daily = prophet_30["yhat"].mean()
    ax1.text(
        0.02, 0.98,
        f"Total Forecast: {total_forecast:.0f} units\nDaily Average: {avg_daily:.1f} units",
        transform=ax1.transAxes,
        verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8),
        fontsize=11, fontweight='bold'
    )

    forecast_df = pd.DataFrame({'Date': future_dates, 'Forecast': prophet_30["yhat"]})
    forecast_df['Week'] = forecast_df['Date'].dt.isocalendar().week
    weekly_forecast = forecast_df.groupby('Week')['Forecast'].sum()

    weeks = [f"Week {i+1}" for i in range(len(weekly_forecast))]
    ax2.bar(weeks, weekly_forecast.values, alpha=0.7, edgecolor='black')
    ax2.set_xlabel("Week", fontsize=12)
    ax2.set_ylabel("Predicted Units Sold", fontsize=12)
    ax2.set_title(f"Weekly Forecast Aggregation - Category {category}", fontsize=14, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)

    for i, v in enumerate(weekly_forecast.values):
        ax2.text(i, v, f'{v:.0f}', ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()

    safe = sanitize_filename(category)
    plt.savefig(f'30day_forecast_category_{safe}.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Saved: 30day_forecast_category_{safe}.png")
    plt.show()

    return total_forecast, avg_daily


# =============================================================================
# FORECAST RUNNERS
# =============================================================================
def forecast_single_category(category: str):
    print(f"\n{'='*80}")
    print(f"FORECASTING CATEGORY: {category}")
    print(f"{'='*80}")

    print("\n[1/3] Loading data...")
    daily_df, location_data = load_and_prepare_data(category)
    print(f"  - Historical data: {len(daily_df)} days")
    print(f"  - Date range: {daily_df['Day'].min().date()} to {daily_df['Day'].max().date()}")

    # Guard: need at least 2 points for Prophet
    if len(daily_df) < 2:
        raise ValueError(f"Not enough data for category '{category}' after cleaning. Need >= 2 days, got {len(daily_df)}.")

    print("\n[2/3] Training model and generating forecast...")
    train, test = split_train_test(daily_df)

    # Guard: training data must also have at least 2 rows
    if len(train) < 2:
        raise ValueError(
            f"Not enough training data for category '{category}'. "
            f"Train size={len(train)}, Test size={len(test)}. "
            f"Reduce TEST_PERIOD or ensure more history."
        )

    model_prophet, prophet_pred, prophet_mae, prophet_rmse = train_prophet_model(train, test)
    future_dates, prophet_30 = generate_30day_forecast(daily_df, model_prophet)
    print(f"  - Model accuracy (MAE): {prophet_mae:.2f}")

    print("\n[3/3] Creating visualizations...")
    print("\n  → Geographic Distribution:")
    plot_geographic_histogram(location_data, category)

    print("\n  → 30-Day Forecast:")
    total_forecast, avg_daily = plot_30day_forecast_histogram(future_dates, prophet_30, category)

    # Top city (if available)
    if "customer_city" in location_data.columns and location_data["customer_city"].notna().any():
        city_demand = (
            location_data.dropna(subset=["customer_city"])
            .groupby("customer_city")["unit_sold"]
            .sum()
            .sort_values(ascending=False)
        )
        top_city = city_demand.index[0]
        top_city_demand = float(city_demand.values[0])
        total_cities = int(location_data["customer_city"].nunique())
    else:
        top_city = "UNKNOWN"
        top_city_demand = 0.0
        total_cities = 0

    return {
        'category': category,
        'total_forecast': float(total_forecast),
        'avg_daily': float(avg_daily),
        'top_city': top_city,
        'top_city_demand': top_city_demand,
        'future_dates': future_dates,
        'forecast_values': prophet_30["yhat"].values,
        'total_cities': total_cities
    }


def forecast_multi_category(category_list):
    print(f"\n{'='*80}")
    print("MULTI-CATEGORY FORECAST MODE")
    print(f"Analyzing {len(category_list)} categories")
    print(f"{'='*80}")

    results = {}
    for idx, cat in enumerate(category_list, 1):
        print(f"\n[{idx}/{len(category_list)}] Processing {cat}...")
        try:
            res = forecast_single_category(cat)
            results[cat] = res
            print(f"  ✅ {cat} completed")
        except Exception as e:
            print(f"  ❌ Error processing {cat}: {str(e)}")
            continue

    return results


# =============================================================================
# CATEGORY SUMMARY GRAPH (PRINT INFO INSIDE GRAPH)
# =============================================================================
def plot_category_summary_graph(results: dict):
    """
    One graph that shows:
    - Category
    - 30-day total forecast
    - Avg daily demand
    - Top city
    - Total cities
    """

    if not results:
        print("⚠️ No results to plot.")
        return

    categories = list(results.keys())
    totals = [results[c]["total_forecast"] for c in categories]

    plt.figure(figsize=(14, 7))
    bars = plt.bar(categories, totals, edgecolor="black")

    plt.title("Category-Level Demand Forecast Summary (30 Days)",
              fontsize=15, fontweight="bold")
    plt.ylabel("Total Units Sold (30 Days)")
    plt.xlabel("Category")
    plt.xticks(rotation=30, ha="right")
    plt.grid(axis="y", alpha=0.3)

    # --------------------------------------------------
    # ADD PRINT-LIKE INFO INSIDE GRAPH
    # --------------------------------------------------
    for bar, cat in zip(bars, categories):
        data = results[cat]

        label_text = (
            f"{cat}\n"
            f"Total: {data['total_forecast']:.0f} units\n"
            f"Avg/day: {data['avg_daily']:.1f}\n"
            f"Top city: {data['top_city']}\n"
            f"Cities: {data['total_cities']}"
        )

        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            label_text,
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold"
        )

    plt.tight_layout()
    plt.savefig("category_forecast_summary_graph.png", dpi=300)
    plt.show()

    print("✅ Saved: category_forecast_summary_graph.png")

# =============================================================================
# MAIN
# =============================================================================
def main():
    print("\n" + "="*80)
    print("CATEGORY-LEVEL DEMAND FORECASTING WITH GEOGRAPHIC INTELLIGENCE")
    print("="*80)
    print(f"\nMode: {FORECAST_MODE}")
    print(f"Forecast Period: {FORECAST_PERIOD} days")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Optional: helpful debug output to verify category names exist
    debug_categories(top_n=30)

    if FORECAST_MODE == "SINGLE":
        result = forecast_single_category(SINGLE_CATEGORY)

        safe = sanitize_filename(result["category"])
        print(f"\n{'='*80}")
        print("FORECASTING SUMMARY")
        print(f"{'='*80}")
        print(f"Category: {result['category']}")
        print(f"30-Day Total Forecast: {result['total_forecast']:.0f} units")
        print(f"Daily Average: {result['avg_daily']:.1f} units/day")
        print(f"Top Geographic Location: {result['top_city']} ({result['top_city_demand']:.0f} units)")
        print(f"Total Cities: {result['total_cities']}")
        print(f"\nGenerated Files:")
        print(f"  1. geographic_distribution_category_{safe}.png")
        print(f"  2. 30day_forecast_category_{safe}.png")
        print(f"{'='*80}")

        return result

    elif FORECAST_MODE == "MULTI":
        if MULTI_CATEGORY_LIST:
            category_list = resolve_categories(MULTI_CATEGORY_LIST, top_n_fallback=TOP_N_CATEGORIES)
        else:
            category_list = get_top_categories(TOP_N_CATEGORIES)

        results = forecast_multi_category(category_list)
        print("\nCreating category summary graph...")
        plot_category_summary_graph(results)


        print(f"\n{'='*80}")
        print("MULTI-CATEGORY FORECASTING SUMMARY")
        print(f"{'='*80}")
        print(f"Total Categories Analyzed: {len(results)}")

        if results:
            print("\nForecast Summary:")
            for cat, data in results.items():
                print(f"  {cat}: {data['total_forecast']:.0f} units (avg: {data['avg_daily']:.1f}/day)")

            print("\nGenerated Files:")
            for cat in results.keys():
                safe = sanitize_filename(cat)
                print(f"  - geographic_distribution_category_{safe}.png")
                print(f"  - 30day_forecast_category_{safe}.png")
        else:
            print("\nNo categories were successfully analyzed. Likely causes:")
            print("- Category names in MULTI_CATEGORY_LIST do not match values in CSV")
            print("- After cleaning, categories have too few valid (Day, unit_sold) rows")

        print(f"{'='*80}")
        return results

    else:
        print(f"\n❌ Invalid FORECAST_MODE: {FORECAST_MODE}")
        print("Please set FORECAST_MODE to either 'SINGLE' or 'MULTI'")
        return None


if __name__ == "__main__":
    results = main()
