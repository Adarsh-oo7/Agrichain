# scripts/generate_crop_prices.py
import pandas as pd
from datetime import datetime

crops = [
    "wheat", "rice", "maize", "gram", "cotton", "soybean", "groundnut", "mustard",
    "coconut", "rubber", "pepper", "cardamom", "banana", "tapioca", "turmeric"
]
markets = ["Delhi", "Kochi", "Chennai", "Ludhiana"]
dates = pd.date_range("2020-01-01", "2024-12-01", freq="MS")

base_prices = {
    "wheat": 2000, "rice": 2600, "maize": 1400, "gram": 3800, "cotton": 5500,
    "soybean": 3200, "groundnut": 4000, "mustard": 3500, "coconut": 2300,
    "rubber": 14000, "pepper": 48000, "cardamom": 85000, "banana": 2000,
    "tapioca": 1500, "turmeric": 6000
}
growth = {
    "wheat": 0.05, "rice": 0.05, "maize": 0.06, "gram": 0.07, "cotton": 0.06,
    "soybean": 0.07, "groundnut": 0.05, "mustard": 0.04, "coconut": 0.06,
    "rubber": 0.05, "pepper": 0.07, "cardamom": 0.08, "banana": 0.05,
    "tapioca": 0.04, "turmeric": 0.05
}

data = []
for date in dates:
    year_diff = (date.year - 2020)
    for crop in crops:
        for market in markets:
            price = base_prices[crop] * (1 + growth[crop]) ** year_diff
            if market == "Kochi" and crop in ["coconut", "rubber", "pepper", "cardamom"]:
                price *= 1.1
            elif market == "Chennai" and crop == "turmeric":
                price *= 1.05
            elif market != "Delhi":
                price *= 0.98  # Slight variation for other markets
            data.append([date, crop, market, round(price)])

df = pd.DataFrame(data, columns=["date", "crop", "market", "price"])
df.to_csv("data/crop_prices.csv", index=False)
print("Generated crop_prices.csv!")