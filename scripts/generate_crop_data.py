import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load combined_data.csv
data = pd.read_csv("data/combined_data.csv")
tavg = data["tavg_Kochi"].values
prcp = data["prcp_Kochi"].values

# Crop conditions
crop_conditions = {
    'rice': {'N': (0.5, 1.5), 'P': (30, 60), 'K': (30, 60), 'humidity': (70, 100), 'ph': (5.0, 7.0)},
    'coconut': {'N': (0.8, 2.0), 'P': (40, 80), 'K': (50, 100), 'humidity': (70, 100), 'ph': (5.5, 8.0)},
    'pepper': {'N': (0.6, 1.8), 'P': (30, 70), 'K': (40, 90), 'humidity': (60, 90), 'ph': (5.5, 7.0)},
    'rubber': {'N': (0.7, 1.9), 'P': (35, 75), 'K': (45, 95), 'humidity': (70, 100), 'ph': (5.0, 7.0)},
    'tapioca': {'N': (0.5, 1.5), 'P': (25, 55), 'K': (30, 60), 'humidity': (60, 90), 'ph': (5.5, 7.5)},
    'turmeric': {'N': (0.6, 1.6), 'P': (30, 60), 'K': (35, 65), 'humidity': (60, 90), 'ph': (5.5, 7.5)}
}

data_list = []
for crop, ranges in crop_conditions.items():
    for i in range(60):
        sample = {
            'N': np.random.uniform(ranges['N'][0], ranges['N'][1]),
            'P': np.random.uniform(ranges['P'][0], ranges['P'][1]),
            'K': np.random.uniform(ranges['K'][0], ranges['K'][1]),
            'temperature': tavg[i],
            'humidity': np.random.uniform(ranges['humidity'][0], ranges['humidity'][1]),
            'ph': np.random.uniform(ranges['ph'][0], ranges['ph'][1]),
            'rainfall': prcp[i] * 30,
            'crop': crop
        }
        data_list.append(sample)

df = pd.DataFrame(data_list)
df.to_csv('data/crop_data.csv', index=False)
logger.info("Crop data saved to data/crop_data.csv")