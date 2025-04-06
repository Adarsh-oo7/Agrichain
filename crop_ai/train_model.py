# train_model.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

# Load your dataset (CSV with 100+ rows)
df = pd.read_csv('kerala_crop_data.csv')

# Features and target
X = df[['area', 'ph', 'rainfall', 'elevation', 'climate_code', 'soil_code']]
y = df['recommended_crop']

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Train model
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# Save the model
joblib.dump(model, 'crop_model.pkl')
