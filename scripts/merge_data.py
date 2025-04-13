# scripts/merge_data.py
import pandas as pd

prices = pd.read_csv("../data/crop_prices.csv")
weather = pd.read_csv("../data/weather_data.csv")

# Prepare weather
weather["date"] = pd.to_datetime(weather["time"])
weather_pivot = weather.pivot_table(
    index="date",
    columns="location",
    values=["tavg", "prcp"],
    aggfunc="first"
).reset_index()
weather_pivot.columns = [
    "date" if col[0] == "date" else f"{col[0]}_{col[1]}" for col in weather_pivot.columns
]

# Prepare prices
prices["date"] = pd.to_datetime(prices["date"])
prices_pivot = prices.pivot_table(
    index="date",
    columns=["crop", "market"],
    values="price",
    aggfunc="first"
).reset_index()
prices_pivot.columns = [
    "date" if col[0] == "date" else f"{col[0]}_{col[1]}" for col in prices_pivot.columns
]

# Merge
data = prices_pivot.merge(weather_pivot, on="date", how="inner")
data.to_csv("../data/combined_data.csv", index=False)
print("Merged!")