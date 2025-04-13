import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load dataset
try:
    data = pd.read_csv('data/crop_data.csv')
    logger.info(f"Dataset loaded: {data.shape}")
except FileNotFoundError:
    logger.error("crop_data.csv not found")
    raise

# Features and target
X = data[['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']]
y = data['crop']

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
logger.info(f"Training set: {X_train.shape}, Test set: {X_test.shape}")

# Train model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
logger.info("Model training completed")

# Evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
logger.info(f"Model accuracy: {accuracy:.2f}")
logger.info("\nClassification Report:\n" + classification_report(y_test, y_pred))

# Save model
os.makedirs('crop_ai', exist_ok=True)
joblib.dump(model, 'crop_ai/crop_recommendation_model.pkl')
logger.info("Model saved to crop_ai/crop_recommendation_model.pkl")