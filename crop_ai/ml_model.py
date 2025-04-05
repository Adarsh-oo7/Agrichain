import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# --------------------------
# 🧪 1. Create training dataset
# --------------------------
training_data = pd.DataFrame({
    "area": [1, 2, 3, 5, 10, 15, 20],
    "climate": ["hot", "humid", "dry", "humid", "cold", "hot", "cold"],
    "soil_type": ["loamy", "clay", "sandy", "clay", "loamy", "sandy", "clay"],
    "nearby_crop": ["wheat", "rice", "maize", "wheat", "barley", "rice", "maize"],
    "preferred_crop": ["rice", "rice", "wheat", "wheat", "barley", "maize", "barley"],
    "recommended_crop": ["rice", "rice", "wheat", "wheat", "barley", "maize", "barley"]
})

# --------------------------
# 🔤 2. Encode categorical variables
# --------------------------
le_climate = LabelEncoder()
le_soil = LabelEncoder()
le_nearby = LabelEncoder()
le_preferred = LabelEncoder()
le_recommend = LabelEncoder()

training_data['climate_enc'] = le_climate.fit_transform(training_data['climate'])
training_data['soil_type_enc'] = le_soil.fit_transform(training_data['soil_type'])
training_data['nearby_crop_enc'] = le_nearby.fit_transform(training_data['nearby_crop'])
training_data['preferred_crop_enc'] = le_preferred.fit_transform(training_data['preferred_crop'])
training_data['target'] = le_recommend.fit_transform(training_data['recommended_crop'])

# --------------------------
# 🤖 3. Train the model
# --------------------------
X = training_data[["area", "climate_enc", "soil_type_enc", "nearby_crop_enc", "preferred_crop_enc"]]
y = training_data["target"]

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X, y)

# --------------------------
# 🧠 4. Main prediction function
# --------------------------
def recommend_crop_ml(area, climate, soil_type, nearby_crop, preferred_crop):
    """
    area: float or int
    climate, soil_type, nearby_crop, preferred_crop: str
    returns: str (recommended crop)
    """
    try:
        climate_enc = le_climate.transform([climate])[0]
        soil_type_enc = le_soil.transform([soil_type])[0]
        nearby_crop_enc = le_nearby.transform([nearby_crop])[0]
        preferred_crop_enc = le_preferred.transform([preferred_crop])[0]
    except ValueError as e:
        print(f"Encoding error: {e}")
        return "Generic Crop"  # Return fallback for unknown labels

    input_data = np.array([[area, climate_enc, soil_type_enc, nearby_crop_enc, preferred_crop_enc]])
    pred_encoded = model.predict(input_data)[0]
    return le_recommend.inverse_transform([pred_encoded])[0]
