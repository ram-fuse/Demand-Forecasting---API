import warnings
warnings.filterwarnings("ignore")

import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from prophet import Prophet

# =============================================================================
# CONFIGURATION
# =============================================================================
FORECAST_MODE = "MULTI"  
MULTI_CATEGORY_LIST = ["Beds", "Accent Chairs", "Coffee & Cocktail Tables", "Bar Stools","Ottomans" ]
TOP_N_CATEGORIES = 5
FILE_PATH = "C:\\Users\\ramme\\OneDrive\\Desktop\\Demand-Forecasting\\notebooks\\Braxton_data_May07_2024_dec16_2025_complete_category_included.csv"
GEO_FILE_PATH = "C:\\Users\\ramme\\OneDrive\\Desktop\\Demand-Forecasting\\notebooks\\Braxton_data_jan_2024_dec16_2025_category_included.csv"
TEST_PERIOD = 5
FORECAST_PERIOD = 30

# =============================================================================
# DATA HELPERS
# =============================================================================
def normalize_category(s):
    return str(s).strip().lower()

def filter_category_present(df):
    cat_str = df["category"].astype(str).str.strip()
    bad = cat_str.str.lower().isin({"", "nan", "none", "null", "na", "n/a"})
    return df.loc[df["category"].notna() & (~bad)].copy()

def load_and_prepare_data(category):
    # Load sales
    df = pd.read_csv(FILE_PATH)
    df.rename(columns={"Date": "Day"}, inplace=True)
    df["Day"] = pd.to_datetime(df["Day"], errors="coerce")
    df["unit_sold"] = pd.to_numeric(df["unit_sold"], errors="coerce")
    df = filter_category_present(df)
    df["cat_norm"] = df["category"].apply(normalize_category)
    df = df.dropna(subset=["Day", "unit_sold"])
    
    df_cat = df[df["cat_norm"] == normalize_category(category)].copy()
    
    # Load Geo
    geo_df = pd.read_csv(GEO_FILE_PATH)
    geo_df.rename(columns={"Date": "Day"}, inplace=True)
    geo_df["Day"] = pd.to_datetime(geo_df["Day"], errors="coerce")
    geo_df = filter_category_present(geo_df)
    geo_df["cat_norm"] = geo_df["category"].apply(normalize_category)
    
    df_merged = pd.merge(
        df_cat, 
        geo_df[["Day", "cat_norm", "customer_city"]], 
        on=["Day", "cat_norm"], how="left"
    )
    
    daily_df = df_merged.groupby("Day")["unit_sold"].sum().reset_index()
    return daily_df, df_merged

# =============================================================================
# DASHBOARD PLOTTING (NEW)
# =============================================================================
def plot_multi_category_dashboard(results):
    """
    Creates a side-by-side dashboard: 
    Left: Total 30-Day Forecast by Category
    Right: Top Geographic City for each Category
    """
    if not results:
        print("No results to plot.")
        return

    categories = list(results.keys())
    forecast_vals = [results[c]['total_forecast'] for c in categories]
    top_cities = [results[c]['top_city'] for c in categories]
    city_vals = [results[c]['top_city_demand'] for c in categories]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    plt.subplots_adjust(wspace=0.3)
    
    # Define a color palette
    colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(categories)))

    # LEFT GRAPH: 30-Day Demand Forecast
    bars1 = ax1.barh(categories, forecast_vals, color=colors, edgecolor='black')
    ax1.set_title("30-Day Total Demand Forecast by Category", fontsize=14, fontweight='bold')
    ax1.set_xlabel("Total Predicted Units", fontsize=12)
    ax1.grid(axis='x', linestyle='--', alpha=0.6)
    
    for bar in bars1:
        ax1.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                 f'{int(bar.get_width())}', va='center', fontweight='bold')

    # RIGHT GRAPH: Top Geographic Locations
    # We display City Name + (Category Name) for clarity
    city_labels = [f"{city} ({cat})" for city, cat in zip(top_cities, categories)]
    bars2 = ax2.barh(city_labels, city_vals, color=colors, edgecolor='black')
    ax2.set_title("Top Geographic Location per Category (Historical)", fontsize=14, fontweight='bold')
    ax2.set_xlabel("Total Units Sold", fontsize=12)
    ax2.grid(axis='x', linestyle='--', alpha=0.6)

    for bar in bars2:
        ax2.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                 f'{int(bar.get_width())}', va='center', fontweight='bold')

    plt.suptitle("MULTI-CATEGORY FORECAST COMPARISON DASHBOARD", fontsize=18, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig("multi_category_dashboard.png", dpi=300, bbox_inches='tight')
    plt.show()
    print("✅ Dashboard saved as 'multi_category_dashboard.png'")

# =============================================================================
# CORE LOGIC
# =============================================================================
def run_forecast(category):
    daily_df, geo_data = load_and_prepare_data(category)
    
    # Prophet logic
    m = Prophet(yearly_seasonality=True, daily_seasonality=False)
    m.fit(daily_df.rename(columns={"Day": "ds", "unit_sold": "y"}))
    
    future = m.make_future_dataframe(periods=FORECAST_PERIOD)
    forecast = m.predict(future)
    total_f = forecast.iloc[-FORECAST_PERIOD:]["yhat"].sum()
    
    # Geo logic
    top_city_info = geo_data.groupby("customer_city")["unit_sold"].sum().sort_values(ascending=False)
    top_city = top_city_info.index[0] if not top_city_info.empty else "Unknown"
    top_city_val = top_city_info.values[0] if not top_city_info.empty else 0
    
    return {
        'total_forecast': max(0, total_f),
        'top_city': top_city,
        'top_city_demand': top_city_val
    }

def main():
    print("Starting Multi-Category Forecast Analysis...")
    results = {}
    
    # Resolve which categories to run
    # (Simplified for the rewrite; uses MULTI_CATEGORY_LIST)
    for cat in MULTI_CATEGORY_LIST:
        try:
            print(f"Processing: {cat}")
            results[cat] = run_forecast(cat)
        except Exception as e:
            print(f"Error on {cat}: {e}")

    # Generate the unified dashboard
    plot_multi_category_dashboard(results)

if __name__ == "__main__":
    main()