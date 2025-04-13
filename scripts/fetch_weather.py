from meteostat import Monthly, Point
from datetime import datetime
import pandas as pd

# Delhi coordinates (lat, lon)
location = Point(28.6139, 77.2090)
start = datetime(2022, 1, 1)
end = datetime(2025, 4, 30)
data = Monthly(location, start, end)
data = data.fetch()
weather = data[["tavg", "prcp"]]  # Temp (°C), rainfall (mm)
weather.reset_index().to_csv("../data/weather_data.csv", index=False)
print("Weather saved!")