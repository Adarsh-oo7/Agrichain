import pandas as pd
import numpy as np
import os

# Generate 36 monthly dates (2021–2023)
dates = pd.date_range(start="2021-01-01", end="2023-12-31", freq="ME").tolist()

# Define crops and markets
crops = [
    "banana", "cardamom", "coconut", "cotton", "gram", "groundnut", "maize",
    "mustard", "pepper", "rice", "rubber", "soybean", "tapioca", "turmeric", "wheat"
]
markets = ["Chennai", "Delhi", "Kochi", "Ludhiana", "Mumbai", "Bangalore"]

# Base prices for each crop (in rupees per ton)
base_prices = {
    "banana": 5000, "cardamom": 20000, "coconut": 3000, "cotton": 6000,
    "gram": 4500, "groundnut": 5500, "maize": 2000, "mustard": 5000,
    "pepper": 30000, "rice": 4000, "rubber": 15000, "soybean": 4500,
    "tapioca": 2500, "turmeric": 10000, "wheat": 3500
}

# Generate data with realistic price variations
np.random.seed(42)  # For reproducibility
data = []
for crop in crops:
    for market in markets:
        base_price = base_prices[crop]
        market_factor = {
            "Chennai": 1.0, "Delhi": 1.1, "Kochi": 0.95,
            "Ludhiana": 1.05, "Mumbai": 1.15, "Bangalore": 1.0
        }[market]
        prices = (
            base_price * market_factor
            + 500 * np.sin(np.linspace(0, 6 * np.pi, 36))  # Seasonal (3 cycles)
            + np.linspace(0, 1500, 36)  # Linear trend
            + np.random.normal(0, 100, 36)  # Noise
        )
        production = np.random.randint(100, 200, 36)  # Tons
        farm_count = np.random.randint(10, 30, 36)  # Farms

        for i in range(36):
            data.append({
                "date": dates[i],
                "crop": crop,
                "market": market,
                "production_tons": production[i],
                "price_per_ton": round(prices[i], 2),
                "farm_count": farm_count[i]
            })

# Create DataFrame
prod_data = pd.DataFrame(data)

# Ensure data/ directory exists
os.makedirs("data", exist_ok=True)

# Save to CSV
prod_data.to_csv("data/production_data.csv", index=False)

# Verify
print("Unique crops:", prod_data["crop"].unique())
print("Unique markets:", prod_data["market"].unique())
print("Row counts by crop and market:")
print(prod_data.groupby(["crop", "market"]).size())
print("\nSample data for banana_Kochi:")
print(prod_data[(prod_data["crop"] == "banana") & (prod_data["market"] == "Kochi")][["date", "price_per_ton"]].head())
print("\nData quality checks:")
print("Missing price_per_ton:", prod_data["price_per_ton"].isnull().any())
print("Non-numeric price_per_ton:", not pd.api.types.is_numeric_dtype(prod_data["price_per_ton"]))
print("Duplicate dates:", prod_data.duplicated(subset=["date", "crop", "market"]).any())