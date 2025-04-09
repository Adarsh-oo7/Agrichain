# crop_ai/train_model.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# Load the dataset
data = pd.read_csv("Crop_recommendation.csv")  # Ensure this file is in crop_ai/

# Features and target
X = data[["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]]
y = data["label"]

# Train the model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X, y)

# Save the model to the maps app directory (adjusted path)
joblib.dump(model, "../maps/crop_recommendation_model.pkl")  # Go up one level to agrichain/, then into maps/
print("Model trained and saved as '../maps/crop_recommendation_model.pkl'")