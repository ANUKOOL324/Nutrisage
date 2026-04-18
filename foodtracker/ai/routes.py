from datetime import datetime, time, timedelta
import logging

import joblib
import pandas as pd
from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from . import bp_ai_tracker
from foodtracker.models import Log, LogFoodItem


logging.basicConfig(level=logging.INFO, format='[%(asctime)s]: %(message)s:')

MODEL_PATH = 'foodtracker/models/user_calories_prediction_model.pkl'
FEATURE_COLUMNS = [
    'calories_consumed_so_far',
    'protein_so_far',
    'carbs_so_far',
    'fat_so_far',
    'meal_count_so_far',
    'hours_passed_today',
    'day_of_week',
    'is_weekend',
    'avg_calories_past_7_days_so_far',
    'avg_total_calories_past_7_days',
    'avg_calories_same_day_of_week_so_far',
    'avg_total_calories_same_day_of_week',
    'daily_target_kcal',
]

ai_prediction_model = None
ai_model_metadata = {}


def _model_is_reliable():
    metrics = ai_model_metadata.get('metrics') or {}
    if not metrics:
        return True

    mae = metrics.get('mae')
    r2 = metrics.get('r2')

    if mae is None or r2 is None:
        return True

    return mae <= 450 and r2 >= -0.25


def load_ai_prediction_model():
    global ai_prediction_model, ai_model_metadata
    try:
        loaded = joblib.load(MODEL_PATH)
        if isinstance(loaded, dict):
            ai_prediction_model = loaded.get('model')
            ai_model_metadata = {
                'metrics': loaded.get('metrics', {}),
                'trained_samples': loaded.get('trained_samples', 0),
                'trained_at': loaded.get('trained_at'),
            }
        else:
            ai_prediction_model = loaded
            ai_model_metadata = {}
        logging.info(f"AI Prediction model loaded successfully from {MODEL_PATH}.")
    except FileNotFoundError:
        ai_prediction_model = None
        ai_model_metadata = {}
        logging.warning(f"AI Prediction model file not found at {MODEL_PATH}. Prediction feature will be unavailable.")
    except Exception as error:
        ai_prediction_model = None
        ai_model_metadata = {}
        logging.error(f"Error loading AI Prediction model: {error}")


def _is_valid_log_date(log_date):
    return 2000 <= log_date.year <= 2100


def _ordered_log_items(log_entry):
    return list(log_entry.log_food_items.order_by(LogFoodItem.timestamp.asc()).all())


def _valid_logs_for_user(user):
    return sorted(
        [
            log for log in user.logs
            if _is_valid_log_date(log.date) and _ordered_log_items(log)
        ],
        key=lambda log: log.date,
    )


def _calculate_partial_totals(log_entry, cutoff_time=None):
    calories = 0
    protein = 0
    carbs = 0
    fat = 0
    meal_count = 0

    for item in _ordered_log_items(log_entry):
        if cutoff_time is not None and item.timestamp > cutoff_time:
            continue

        food_item = item.food
        quantity = item.quantity or 1
        calories += food_item.calories * quantity
        protein += food_item.proteins * quantity
        carbs += food_item.carbs * quantity
        fat += food_item.fats * quantity
        meal_count += quantity

    return {
        'calories': calories,
        'protein': protein,
        'carbs': carbs,
        'fat': fat,
        'meal_count': meal_count,
    }


def _partial_calories_for_hour(log_entry, hour_fraction):
    calories = 0

    for item in _ordered_log_items(log_entry):
        item_hour = item.timestamp.hour + (item.timestamp.minute / 60.0)
        if item_hour <= hour_fraction:
            calories += item.food.calories * (item.quantity or 1)

    return calories


def _average(values):
    return round(sum(values) / len(values), 2) if values else 0.0


def _historical_features_for_user(user, reference_date, hour_fraction, candidate_logs=None):
    valid_logs = candidate_logs if candidate_logs is not None else _valid_logs_for_user(user)
    valid_logs = [log for log in valid_logs if log.date < reference_date]

    recent_logs = [log for log in valid_logs if log.date >= reference_date - timedelta(days=7)]
    same_weekday_logs = [log for log in valid_logs if log.date.weekday() == reference_date.weekday()]

    return {
        'avg_calories_past_7_days_so_far': _average([
            _partial_calories_for_hour(log, hour_fraction)
            for log in recent_logs
        ]),
        'avg_total_calories_past_7_days': _average([
            _calculate_partial_totals(log)['calories']
            for log in recent_logs
        ]),
        'avg_calories_same_day_of_week_so_far': _average([
            _partial_calories_for_hour(log, hour_fraction)
            for log in same_weekday_logs
        ]),
        'avg_total_calories_same_day_of_week': _average([
            _calculate_partial_totals(log)['calories']
            for log in same_weekday_logs
        ]),
        'history_days_used': len(recent_logs),
        'weekday_history_used': len(same_weekday_logs),
    }


def _build_feature_frame(user, reference_date, snapshot_time, log_entry=None, candidate_logs=None):
    time_feature = snapshot_time.hour + (snapshot_time.minute / 60.0)

    totals = {
        'calories': 0,
        'protein': 0,
        'carbs': 0,
        'fat': 0,
        'meal_count': 0,
    }
    if log_entry:
        totals = _calculate_partial_totals(log_entry, cutoff_time=snapshot_time)

    historical = _historical_features_for_user(
        user,
        reference_date,
        time_feature,
        candidate_logs=candidate_logs,
    )

    features = {
        'calories_consumed_so_far': totals['calories'],
        'protein_so_far': totals['protein'],
        'carbs_so_far': totals['carbs'],
        'fat_so_far': totals['fat'],
        'meal_count_so_far': totals['meal_count'],
        'hours_passed_today': round(time_feature, 2),
        'day_of_week': reference_date.strftime('%A'),
        'is_weekend': 1 if reference_date.weekday() >= 5 else 0,
        'avg_calories_past_7_days_so_far': historical['avg_calories_past_7_days_so_far'],
        'avg_total_calories_past_7_days': historical['avg_total_calories_past_7_days'],
        'avg_calories_same_day_of_week_so_far': historical['avg_calories_same_day_of_week_so_far'],
        'avg_total_calories_same_day_of_week': historical['avg_total_calories_same_day_of_week'],
        'daily_target_kcal': user.daily_cal_target,
    }

    return pd.DataFrame([[features[column] for column in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS), totals, historical


def _heuristic_prediction(user, totals, historical, snapshot_time):
    progress = max(0.2, min((snapshot_time.hour + (snapshot_time.minute / 60.0)) / 24.0, 0.95))
    pace_projection = totals['calories'] / progress if totals['calories'] > 0 else 0

    anchors = [
        user.daily_cal_target,
        historical['avg_total_calories_past_7_days'],
        historical['avg_total_calories_same_day_of_week'],
    ]
    anchors = [anchor for anchor in anchors if anchor > 0]
    anchor_value = _average(anchors) if anchors else user.daily_cal_target

    if totals['meal_count'] == 0:
        return round(anchor_value)

    weighted_projection = (pace_projection * 0.55) + (anchor_value * 0.45)
    return round(max(totals['calories'], weighted_projection))


def _predict_total_from_context(user, feature_frame, totals, historical, snapshot_time):
    heuristic_prediction = _heuristic_prediction(user, totals, historical, snapshot_time)
    model_prediction = None
    model_used = False

    if ai_prediction_model is not None and _model_is_reliable():
        try:
            model_prediction = float(ai_prediction_model.predict(feature_frame)[0])
            model_prediction = max(model_prediction, float(totals['calories']))
            model_used = True
        except Exception as error:
            logging.error(f"Error during prediction for user {user.username}: {error}")

    if model_prediction is None:
        return heuristic_prediction, model_used

    blend_weight = 0.7 if totals['meal_count'] >= 1 else 0.45
    blended_prediction = round(
        max(
            totals['calories'],
            (model_prediction * blend_weight) + (heuristic_prediction * (1 - blend_weight))
        )
    )
    return blended_prediction, model_used


def _forecast_status(deviation, meal_count, history_days_used):
    if meal_count == 0 and history_days_used == 0:
        return "Need more food history", "neutral"
    if deviation > 250:
        return "Likely above goal", "danger"
    if deviation > 75:
        return "Slightly above goal", "warning"
    if deviation < -250:
        return "Likely below goal", "info"
    return "On track", "success"


def _normalize_reference_date(value, fallback_date):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return fallback_date


def _format_forecast_window_label(hour_value):
    candidate = datetime.combine(datetime.today().date(), time(hour=hour_value))
    return candidate.strftime('%I %p').lstrip('0') + ' snapshot'


def _build_recent_prediction_history(user, valid_logs, reference_date, limit=6, forecast_hour=14):
    history_cards = []
    candidate_logs = [log for log in valid_logs if log.date <= reference_date]
    if not candidate_logs:
        return history_cards, None

    candidate_logs = candidate_logs[-limit:]
    resolved_reference_date = candidate_logs[-1].date

    for log_entry in candidate_logs:
        forecast_time = datetime.combine(log_entry.date, time(hour=forecast_hour, minute=0))
        feature_frame, partial_totals, historical = _build_feature_frame(
            user,
            log_entry.date,
            forecast_time,
            log_entry=log_entry,
            candidate_logs=valid_logs,
        )
        predicted_total, _ = _predict_total_from_context(
            user,
            feature_frame,
            partial_totals,
            historical,
            forecast_time,
        )
        actual_total = _calculate_partial_totals(log_entry)['calories']
        variance = int(round(predicted_total - actual_total))
        absolute_error = abs(variance)

        if absolute_error <= 90:
            hindsight_label = "Very close"
        elif absolute_error <= 180:
            hindsight_label = "Close"
        else:
            hindsight_label = "Wide gap"

        history_cards.append({
            'dateLabel': log_entry.date.strftime('%b %d'),
            'forecastWindowLabel': _format_forecast_window_label(forecast_hour),
            'forecastedCalories': int(round(predicted_total)),
            'actualCalories': int(round(actual_total)),
            'partialCalories': int(round(partial_totals['calories'])),
            'variance': variance,
            'varianceAbs': int(round(absolute_error)),
            'mealCountByForecast': partial_totals['meal_count'],
            'hindsightLabel': hindsight_label,
        })

    return history_cards, resolved_reference_date


def build_prediction_payload(user, now=None, history_reference_date=None):
    now = now or datetime.now()
    today = now.date()
    valid_logs = _valid_logs_for_user(user)
    completed_logs = [log for log in valid_logs if log.date < today]
    today_log_entry = Log.query.filter_by(date=today, user_id=user.id).first()

    feature_frame, totals, historical = _build_feature_frame(
        user,
        today,
        now,
        log_entry=today_log_entry,
        candidate_logs=valid_logs,
    )
    predicted_total_calories, model_used = _predict_total_from_context(
        user,
        feature_frame,
        totals,
        historical,
        now,
    )

    daily_target = user.daily_cal_target
    deviation = predicted_total_calories - daily_target
    projected_remaining = max(0, predicted_total_calories - totals['calories'])
    prediction_status, status_tone = _forecast_status(
        deviation,
        totals['meal_count'],
        historical['history_days_used'],
    )
    default_reference_date = completed_logs[-1].date if completed_logs else today - timedelta(days=1)
    selected_reference_date = history_reference_date or default_reference_date
    recent_prediction_history, resolved_reference_date = _build_recent_prediction_history(
        user,
        completed_logs,
        reference_date=selected_reference_date,
    )
    progress_ratio = 0 if predicted_total_calories <= 0 else min(100, round((totals['calories'] / predicted_total_calories) * 100))
    target_progress_ratio = 0 if daily_target <= 0 else min(100, round((totals['calories'] / daily_target) * 100))
    consistency_score = max(
        0,
        min(100, 100 - int(_average([entry['varianceAbs'] for entry in recent_prediction_history]) / 4))
    ) if recent_prediction_history else 0

    return {
        "predicted_total_calories": int(round(predicted_total_calories)),
        "prediction_status": prediction_status,
        "status_tone": status_tone,
        "current_consumed_kcal": totals['calories'],
        "current_protein_g": totals['protein'],
        "current_carbs_g": totals['carbs'],
        "current_fat_g": totals['fat'],
        "meal_count_so_far": totals['meal_count'],
        "daily_target_kcal": daily_target,
        "projected_remaining_kcal": int(round(projected_remaining)),
        "deviation_from_target_kcal": int(round(deviation)),
        "hours_passed_today": round(now.hour + (now.minute / 60.0), 2),
        "avg_recent_day_kcal": historical['avg_total_calories_past_7_days'],
        "avg_same_day_kcal": historical['avg_total_calories_same_day_of_week'],
        "history_days_used": historical['history_days_used'],
        "weekday_history_used": historical['weekday_history_used'],
        "model_used": model_used,
        "model_sample_count": int(ai_model_metadata.get('trained_samples') or 0),
        "model_metrics": ai_model_metadata.get('metrics', {}),
        "model_quality_note": "adaptive forecasting active" if model_used else "history-based forecasting active",
        "forecast_window_label": "Live day forecast",
        "progress_ratio": progress_ratio,
        "target_progress_ratio": target_progress_ratio,
        "consistency_score": consistency_score,
        "recent_prediction_history": recent_prediction_history,
        "history_filters": {
            "reference_date": resolved_reference_date.isoformat() if resolved_reference_date else selected_reference_date.isoformat(),
            "reference_label": resolved_reference_date.strftime('%b %d, %Y') if resolved_reference_date else selected_reference_date.strftime('%b %d, %Y'),
            "display_limit": 6,
        },
    }


@bp_ai_tracker.route('/')
@login_required
def ai_tracker_page():
    return render_template('ai_tracker.html')


@bp_ai_tracker.route('/predict_calories')
@login_required
def get_calorie_prediction_data():
    logging.info(f"Fetching calorie prediction data for user: {current_user.username} (ID: {current_user.id})")
    today = datetime.now().date()
    history_reference_date = _normalize_reference_date(
        request.args.get('historyDate'),
        today - timedelta(days=1),
    )
    return jsonify(build_prediction_payload(
        current_user,
        history_reference_date=history_reference_date,
    ))
