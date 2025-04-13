# scripts/price_prediction_fallback.py
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import logging
import os
import sys
import django
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
    logger.warning(f"Django setup failed: {e}. Saving to CSV only.")
    use_django = False

# Load data
try:
    data = pd.read_csv("data/combined_data.csv")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in data.columns[1:]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna()
    data["days"] = (data["date"] - data["date"].min()).dt.days
    logger.info("Data loaded and cleaned")
except Exception as e:
    logger.error(f"Error loading data: {e}")
    raise

crops = ["coconut_Kochi", "pepper_Kochi", "rubber_Kochi", "tapioca_Kochi", "turmeric_Kochi"]
predictions = []

# Clear old predictions
if use_django:
    PricePrediction.objects.all().delete()
    logger.info("Old predictions cleared")

for crop in crops:
    logger.info(f"Training {crop}...")
    df = data[["days", crop]].copy()
    df = df.dropna()
    if df.empty:
        logger.warning(f"No data for {crop}")
        continue

    X = df[["days"]].values
    y = df[crop].values

    model = LinearRegression()
    model.fit(X, y)

    # Predict for next 3 months
    last_day = X[-1][0]
    future_days = np.array([[last_day + 30 * i] for i in range(1, 4)])
    future_dates = [data["date"].max() + pd.Timedelta(days=30 * i) for i in range(1, 4)]
    preds = model.predict(future_days)

    for date, pred in zip(future_dates, preds):
        pred = max(0, pred)
        pred_entry = {
            "crop": crop,
            "date": date,
            "predicted_price": pred
        }
        predictions.append(pred_entry)
        if use_django:
            PricePrediction.objects.create(**pred_entry)
    
    logger.info(f"Predictions generated for {crop}")

# Save to CSV
if predictions:
    pd.DataFrame(predictions).to_csv("data/price_predictions.csv", index=False)
    logger.info("Price predictions saved to data/price_predictions.csv")

logger.info("Price prediction completed!")