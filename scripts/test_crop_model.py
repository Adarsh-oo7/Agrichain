import pandas as pd
from sklearn.metrics import accuracy_score
import joblib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = joblib.load('crop_ai/crop_recommendation_model.pkl')
data = pd.read_csv('data/crop_data.csv')
X_test = data[['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']]
y_test = data['crop']
y_pred = model.predict(X_test)
logger.info(f"Test accuracy: {accuracy_score(y_test, y_pred):.2f}")

sample = [[0.8, 40, 50, 25, 70, 6.5, 1200]]
probs = model.predict_proba(sample)[0]
logger.info(f"Sample predictions: {dict(zip(model.classes_, probs * 100))}")