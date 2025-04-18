import pandas as pd
import xgboost as xgb
import joblib
import os

# Ensure maps/ directory exists for model outputs
os.makedirs("maps", exist_ok=True)

# Load data
prod_data_path = "data/production_data.csv"
combined_data_path = "data/combined_data.csv"
try:
    prod_data = pd.read_csv(prod_data_path)
    combined_data = pd.read_csv(combined_data_path)
except FileNotFoundError as e:
    print(f"Error: {e}. Please create {prod_data_path} and {combined_data_path} in data/.")
    exit(1)

# Convert date columns
prod_data["date"] = pd.to_datetime(prod_data["date"])
combined_data["date"] = pd.to_datetime(combined_data["date"])

# Since combined_data has wide format (e.g., prcp_Kochi), no need to merge — just use it to add weather info
data = prod_data.copy()

# Merge weather and temperature data from combined_data
data = data.merge(combined_data, on="date", how="left")

# Mock forecasts (replace with ARIMA/Prophet outputs)
data["forecast_prod"] = data["production_tons"] * 1.1
data["forecast_price"] = data["price_per_ton"] * 0.9

# Label oversupply
data["oversupply"] = (
    (data["forecast_prod"] > data["production_tons"].quantile(0.9)) |
    (data["forecast_price"].pct_change() < -0.2)
).astype(int)

# Add weather-related features dynamically based on the market
data["prcp"] = data.apply(lambda x: x.get(f"prcp_{x['market']}", 0), axis=1)
data["tavg"] = data.apply(lambda x: x.get(f"tavg_{x['market']}", 25), axis=1)

# Add yield estimate
data["yield_estimate"] = data["production_tons"] / data["farm_count"].replace(0, 1)

# Features for model
features = ["forecast_prod", "forecast_price", "farm_count", "prcp", "tavg", "yield_estimate"]
X = data[features].fillna(0)
y = data["oversupply"]

# Train XGBoost
try:
    model = xgb.XGBClassifier(n_estimators=50, max_depth=5, learning_rate=0.1, random_state=42)
    model.fit(X, y)
    joblib.dump(model, "data/oversupply_model.pkl")
    print("✅ XGBoost model saved to maps/oversupply_model.pkl")
except Exception as e:
    print(f"❌ Error training XGBoost: {e}")
