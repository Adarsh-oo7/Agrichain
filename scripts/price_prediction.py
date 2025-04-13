# scripts/price_prediction.py
import pandas as pd
import numpy as np
from prophet import Prophet
import logging
import os
import sys
import django
import matplotlib.pyplot as plt
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup Django
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agrichain.settings')
    django.setup()
    from maps.models import PricePrediction
    logger.info("Django setup successful")
    use_django = True
except (ImportError, ModuleNotFoundError) as e:
    logger.warning(f"Django setup failed: {e}. Saving predictions to CSV instead.")
    use_django = False

# Load data
try:
    data = pd.read_csv("data/combined_data.csv")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in data.columns[1:]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna()
    logger.info("Data loaded and cleaned")
except Exception as e:
    logger.error(f"Error loading data: {e}")
    raise

# Focus on Kochi crops
crops = ["coconut_Kochi", "pepper_Kochi", "rubber_Kochi", "tapioca_Kochi", "turmeric_Kochi"]
predictions = []

# Clear old predictions
if use_django:
    PricePrediction.objects.all().delete()
    logger.info("Old predictions cleared")

for crop in crops:
    logger.info(f"Training {crop}...")
    df = data[["date", crop]].copy()
    df = df.rename(columns={"date": "ds", crop: "y"})
    df = df.dropna()
    if df.empty:
        logger.warning(f"No data for {crop}")
        continue

    logger.info(f"{crop} summary:\n{df['y'].describe()}")

    # Log-transform for high-variance crops
    is_pepper = crop == "pepper_Kochi"
    if is_pepper:
        df["y"] = np.log1p(df["y"])

    # Minimal scaling to prevent overflow
    y_mean = df["y"].mean()
    y_std = df["y"].std() or 1
    df["y"] = (df["y"] - y_mean) / y_std
    df["y"] = df["y"].clip(-5, 5)  # Prevent extreme values

    model = Prophet(
        yearly_seasonality=5,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.01,
        interval_width=0.95
    )

    try:
        model.fit(df)
        future = model.make_future_dataframe(periods=3, freq="MS")
        forecast = model.predict(future)
        
        # Unscale predictions
        forecast["yhat"] = forecast["yhat"] * y_std + y_mean
        if is_pepper:
            forecast["yhat"] = np.expm1(forecast["yhat"])

        for _, row in forecast.tail(3).iterrows():
            pred = {
                "crop": crop,
                "date": row["ds"],
                "predicted_price": max(0, row["yhat"])
            }
            predictions.append(pred)
            if use_django:
                PricePrediction.objects.create(**pred)
        
        logger.info(f"Predictions saved for {crop}")

        # Plot forecast
        fig = model.plot(forecast)
        plt.title(f"{crop} Price Prediction (₹/quintal)")
        plt.savefig(f"data/{crop}_forecast.png")
        plt.close()

    except Exception as e:
        logger.error(f"Error training {crop}: {e}")
        continue

# Save to CSV as fallback
if predictions:
    pd.DataFrame(predictions).to_csv("data/price_predictions.csv", index=False)
    logger.info("Predictions saved to data/price_predictions.csv")

logger.info("Price prediction completed!")