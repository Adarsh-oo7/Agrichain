import pandas as pd
import joblib
import os
from statsmodels.tsa.arima.model import ARIMA
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

# Ensure data/ directory exists
os.makedirs("data", exist_ok=True)

# Load data
data_path = "data/production_data.csv"
try:
    prod_data = pd.read_csv(data_path)
    prod_data["date"] = pd.to_datetime(prod_data["date"])
    prod_data["crop"] = prod_data["crop"].str.lower()
    prod_data["market"] = prod_data["market"].str.title()
except FileNotFoundError:
    print(f"Error: {data_path} not found. Please create production_data.csv in data/.")
    exit(1)

# Debug: Print dataset summary
print("Unique crops:", prod_data["crop"].unique())
print("Unique markets:", prod_data["market"].unique())
print("Row counts by crop and market:")
print(prod_data.groupby(["crop", "market"]).size())

# Use only crops and markets in the dataset
crops = prod_data["crop"].unique().tolist()
markets = prod_data["market"].unique().tolist()

for crop in crops:
    for market in markets:
        crop_key = f"{crop}_{market}"
        df = prod_data[(prod_data["crop"] == crop) & (prod_data["market"] == market)][["date", "price_per_ton"]]
        if len(df) < 12:
            print(f"Skipping {crop_key}: insufficient data ({len(df)} rows)")
            continue
        if df["price_per_ton"].isnull().any():
            print(f"Skipping {crop_key}: missing values in price_per_ton")
            continue
        if not pd.api.types.is_numeric_dtype(df["price_per_ton"]):
            print(f"Skipping {crop_key}: price_per_ton is not numeric")
            continue
        if df["date"].duplicated().any():
            print(f"Skipping {crop_key}: duplicate dates found")
            continue

        print(f"Processing {crop_key}:\n{df.head()}")
        df = df.set_index("date")["price_per_ton"]

        try:
            # Fit ARIMA (order can be tuned; using (1,1,1) for simplicity)
            model = ARIMA(df, order=(1, 1, 1), freq="ME")
            model_fit = model.fit()

            # Forecast 6 months
            forecast = model_fit.forecast(steps=6)
            forecast_dates = pd.date_range(start=df.index[-1] + pd.offsets.MonthEnd(1), periods=6, freq="ME")
            forecast_df = pd.DataFrame({"ds": forecast_dates, "yhat": forecast.values})

            # Save forecast
            joblib.dump(forecast_df, f"data/arima_{crop_key}.pkl")
            print(f"Saved ARIMA model for {crop_key}")
        except Exception as e:
            print(f"Error training ARIMA for {crop_key}: {e}")