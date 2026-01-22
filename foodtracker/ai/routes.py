from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from collections import defaultdict
import joblib
import pandas as pd
import numpy as np 
import logging
from . import bp_ai_tracker
from foodtracker.extensions import db
from foodtracker.models import Log, Food, User, LogFoodItem


logging.basicConfig(level=logging.INFO, format='[%(asctime)s]: %(message)s:')

ai_prediction_model = None


def load_ai_prediction_model():
    global ai_prediction_model
    model_path = 'foodtracker/models/user_calories_prediction_model.pkl'
    try:
        ai_prediction_model = joblib.load(model_path)
        logging.info(f"AI Prediction model loaded successfully from {model_path}.")
    except FileNotFoundError:
        logging.warning(f"AI Prediction model file not found at {model_path}. Prediction feature will be unavailable.")
    except Exception as e:
        logging.error(f"Error loading AI Prediction model: {e}")


@bp_ai_tracker.route('/') 
@login_required
def ai_tracker_page():
    return render_template('ai_tracker.html')

@bp_ai_tracker.route('/predict_calories')
@login_required
def get_calorie_prediction_data():
    logging.info(f"Fetching calorie prediction data for user: {current_user.username} (ID: {current_user.id})")

    user = current_user
    now = datetime.now()
    today = now.date()
    current_hour = now.hour 
    current_minute = now.minute
    time_feature = current_hour + (current_minute / 60.0)


    calories_so_far = 0
    protein_so_far = 0
    carbs_so_far = 0
    fat_so_far = 0

    today_log_entry = Log.query.filter_by(date=today, user_id=user.id).first()

    if today_log_entry:
        for lfi in today_log_entry.log_food_items.filter(LogFoodItem.timestamp <= now).all():
            food_item = lfi.food
            calories_so_far += food_item.calories
            protein_so_far += food_item.proteins
            carbs_so_far += food_item.carbs
            fat_so_far += food_item.fats

    
    # These will be replaced by actual DB queries 
    avg_calories_past_7_days_so_far = calories_so_far + 50 # Dummy
    avg_calories_same_day_of_week_so_far = calories_so_far + 100 # Dummy

    day_of_week = today.strftime('%A')
    is_weekend = 1 if today.weekday() >= 5 else 0

    # Features for ML Model 
    features_data = [[
        calories_so_far,
        time_feature,
        day_of_week,
        is_weekend,
        avg_calories_past_7_days_so_far,
        avg_calories_same_day_of_week_so_far
    ]]

    feature_columns = [
        'calories_consumed_so_far',
        'hours_passed_today',
        'day_of_week',
        'is_weekend',
        'avg_calories_past_7_days_so_far',
        'avg_calories_same_day_of_week_so_far'
    ]

    input_features_df = pd.DataFrame(features_data, columns=feature_columns)

    predicted_total_calories = None
    prediction_status = "Prediction N/A (Model not loaded)"

    if ai_prediction_model is not None:
        try:
            predicted_total_calories = ai_prediction_model.predict(input_features_df)[0]
            predicted_total_calories = round(predicted_total_calories)

            daily_target = user.daily_cal_target
            deviation = predicted_total_calories - daily_target

            if deviation > 200:
                prediction_status = "Likely to Exceed Goal"
            elif deviation < -200:
                prediction_status = "Likely to be Below Goal"
            else:
                prediction_status = "On Track"

        except Exception as e:
            logging.error(f"Error during ML prediction for user {user.username}: {e}")
            prediction_status = f"Prediction Error: {e}"

    return jsonify({
        "predicted_total_calories": predicted_total_calories,
        "prediction_status": prediction_status,
        "current_consumed_kcal": calories_so_far,
        "daily_target_kcal": user.daily_cal_target
    })