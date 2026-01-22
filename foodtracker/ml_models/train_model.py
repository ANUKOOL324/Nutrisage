import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib 
import numpy as np 

print("--- Starting ML Model Training Script ---")

# Here, i am creating a small, fake dataset that mimics what we need.

data = {
    'calories_consumed_so_far': [500, 800, 600, 1000, 700, 1200, 900,
                                550, 850, 650, 1050, 750, 1250, 950], 
    'hours_passed_today':       [14.0, 14.0, 14.0, 14.0, 14.0, 14.0, 14.0, 
                                14.0, 14.0, 14.0, 14.0, 14.0, 14.0, 14.0],
    'day_of_week':              ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
                                'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    'is_weekend':               [0, 0, 0, 0, 0, 1, 1,
                                0, 0, 0, 0, 0, 1, 1],
    'avg_calories_past_7_days_so_far': [700, 700, 700, 700, 700, 700, 700, 
                                       750, 750, 750, 750, 750, 750, 750],
    'avg_calories_same_day_of_week_so_far': [600, 600, 600, 600, 600, 1100, 1000, 
                                            620, 620, 620, 620, 620, 1120, 1020],
    'total_calories_for_day':   [1800, 2000, 1900, 2200, 2000, 2800, 2500, 
                                1850, 2050, 1950, 2250, 2050, 2850, 2550]
}
df = pd.DataFrame(data)

print("Simulated historical data created.")
print(df.head())


X = df[['calories_consumed_so_far', 'hours_passed_today', 'day_of_week', 'is_weekend',
        'avg_calories_past_7_days_so_far', 'avg_calories_same_day_of_week_so_far']]
y = df['total_calories_for_day']


# This handles scaling numbers and converting day_of_week into numbers 
numeric_features = ['calories_consumed_so_far', 'hours_passed_today',
                    'avg_calories_past_7_days_so_far', 'avg_calories_same_day_of_week_so_far']
categorical_features = ['day_of_week']

preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numeric_features),
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
    ],
    remainder='passthrough' # Keep 'is_weekend' as is
)

#Create and Train the ML Model Pipeline
model_pipeline = Pipeline(steps=[('preprocessor', preprocessor),
                                 ('regressor', LinearRegression())])

model_pipeline.fit(X, y)
print("\nML Model training complete.")

model_filename = 'user_calories_prediction_model.pkl'

save_path = 'foodtracker/models/' + model_filename 

import os
os.makedirs(os.path.dirname(save_path), exist_ok=True)

joblib.dump(model_pipeline, save_path)
print(f"Trained ML model saved to: {save_path}")
#for just checking it 
test_data = pd.DataFrame([{
    'calories_consumed_so_far': 700,
    'hours_passed_today': 15.0,
    'day_of_week': 'Monday',
    'is_weekend': 0,
    'avg_calories_past_7_days_so_far': 800,
    'avg_calories_same_day_of_week_so_far': 750
}])
loaded_model = joblib.load(save_path)
prediction = loaded_model.predict(test_data)[0]
print(f"Test prediction for 700 calories so far on Monday: {round(prediction)} kcal")

print("ML Model Training Finished ")