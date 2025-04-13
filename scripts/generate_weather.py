# scripts/generate_weather.py
import pandas as pd
from datetime import datetime

locations = ["Delhi", "Kochi", "Chennai", "Ludhiana"]
dates = pd.date_range("2020-01-01", "2024-12-01", freq="MS")

# Base weather (Delhi, adjust for others)
base_weather = {
    "Delhi": {"tavg": [14, 16, 22, 28, 32, 33, 30, 29, 28, 25, 20, 16], "prcp": [50, 40, 20, 10, 15, 80, 200, 180, 150, 50, 10, 20]},
    "Kochi": {"tavg": [26.5, 27, 28, 29, 29.5, 28.5, 27.5, 27, 27.5, 28, 27.5, 27], "prcp": [60, 50, 70, 100, 200, 400, 500, 450, 300, 200, 100, 60]},
    "Chennai": {"tavg": [25, 25.5, 27, 29, 30, 29.5, 28.5, 28, 28, 27.5, 26.5, 25.5], "prcp": [40, 30, 20, 50, 100, 150, 200, 180, 200, 250, 150, 80]},
    "Ludhiana": {"tavg": [13.5, 14, 20, 26, 30, 31, 29, 28, 27, 24, 19, 14.5], "prcp": [55, 45, 30, 15, 20, 90, 220, 200, 160, 60, 15, 30]}
}

data = []
for date in dates:
    month = date.month - 1
    for loc in locations:
        tavg = base_weather[loc]["tavg"][month] + (date.year - 2020) * 0.1
        prcp = base_weather[loc]["prcp"][month] * (1 + (date.year - 2020) * 0.05)
        data.append([date, loc, round(tavg, 1), round(prcp, 1)])

df = pd.DataFrame(data, columns=["time", "location", "tavg", "prcp"])
df.to_csv("../data/weather_data.csv", index=False)
print("Generated weather_data.csv!")