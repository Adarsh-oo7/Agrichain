from prophet import Prophet
import pandas as pd
import joblib
import os
import logging
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('prophet')
logger.setLevel(logging.DEBUG)

# Directory setup
os.makedirs("maps", exist_ok=True)
os.makedirs("data", exist_ok=True)

def load_and_preprocess_data():
    """Load and validate the production data"""
    data_path = "data/production_data.csv"
    try:
        df = pd.read_csv(data_path)
        df["date"] = pd.to_datetime(df["date"])
        df["crop"] = df["crop"].str.lower().str.strip()
        df["market"] = df["market"].str.title().str.strip()
        
        # Data validation
        if df["price_per_ton"].isnull().any():
            raise ValueError("Missing values in price_per_ton")
        if not pd.api.types.is_numeric_dtype(df["price_per_ton"]):
            raise ValueError("price_per_ton contains non-numeric values")
            
        return df
    except Exception as e:
        logger.error(f"Data loading failed: {str(e)}")
        raise

def train_prophet_models(prod_data):
    """Train Prophet models for each crop-market combination"""
    results = {}
    
    for (crop, market), group in prod_data.groupby(['crop', 'market']):
        crop_key = f"{crop}_{market}"
        
        # Skip if insufficient data
        if len(group) < 12:
            logger.info(f"Skipping {crop_key}: insufficient data ({len(group)} rows)")
            continue
            
        # Prepare Prophet format
        df = group[['date', 'price_per_ton']].copy()
        df.columns = ['ds', 'y']
        df = df.sort_values('ds').drop_duplicates('ds')
        
        try:
            # Configure model with conservative settings
            model = Prophet(
                growth='linear',
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=10.0,
                mcmc_samples=0  # Disable MCMC for faster fitting
            )
            
            # Fit with L-BFGS instead of Newton
            model.fit(df, algorithm='LBFGS', iter=1000)
            
            # Generate forecast
            future = model.make_future_dataframe(periods=6, freq='ME')
            forecast = model.predict(future)
            
            # Save results
            output = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
            output_path = f"data/prophet_{crop_key}.pkl"
            joblib.dump(output, output_path)
            
            results[crop_key] = {
                'status': 'success',
                'path': output_path,
                'last_actual': df['y'].iloc[-1],
                'next_forecast': forecast['yhat'].iloc[-6:].mean()
            }
            
            logger.info(f"Successfully processed {crop_key}")
            
        except Exception as e:
            results[crop_key] = {
                'status': 'failed',
                'error': str(e)
            }
            logger.error(f"Failed on {crop_key}: {str(e)}")
    
    return results

if __name__ == "__main__":
    try:
        # Load and validate data
        prod_data = load_and_preprocess_data()
        
        # Debug info
        logger.info(f"Unique crops: {prod_data['crop'].unique()}")
        logger.info(f"Unique markets: {prod_data['market'].unique()}")
        logger.info("Data counts:\n" + 
                   str(prod_data.groupby(["crop", "market"]).size()))
        
        # Train models
        results = train_prophet_models(prod_data)
        
        # Print summary
        success = sum(1 for r in results.values() if r['status'] == 'success')
        logger.info(f"\nCompleted with {success} successes out of {len(results)} models")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)