import os
from datetime import timedelta
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder

from foodtracker import create_app
from foodtracker.ai.routes import FEATURE_COLUMNS
from foodtracker.models import Log, LogFoodItem


TARGET_COLUMN = 'total_calories_for_day'
MODEL_OUTPUT_PATH = 'foodtracker/models/user_calories_prediction_model.pkl'
NUMERIC_FEATURES = [
    'calories_consumed_so_far',
    'protein_so_far',
    'carbs_so_far',
    'fat_so_far',
    'meal_count_so_far',
    'hours_passed_today',
    'avg_calories_past_7_days_so_far',
    'avg_total_calories_past_7_days',
    'avg_calories_same_day_of_week_so_far',
    'avg_total_calories_same_day_of_week',
    'daily_target_kcal',
]
CATEGORICAL_FEATURES = ['day_of_week']
PASSTHROUGH_FEATURES = ['is_weekend']


def is_valid_log_date(log_date):
    return 2000 <= log_date.year <= 2100


def ordered_log_items(log_entry):
    return list(log_entry.log_food_items.order_by(LogFoodItem.timestamp.asc()).all())


def calculate_totals_until(log_entry, cutoff_time=None):
    calories = 0
    protein = 0
    carbs = 0
    fat = 0
    meal_count = 0

    for item in ordered_log_items(log_entry):
        if cutoff_time is not None and item.timestamp > cutoff_time:
            continue
        food = item.food
        quantity = item.quantity or 1
        calories += food.calories * quantity
        protein += food.proteins * quantity
        carbs += food.carbs * quantity
        fat += food.fats * quantity
        meal_count += quantity

    return {
        'calories': calories,
        'protein': protein,
        'carbs': carbs,
        'fat': fat,
        'meal_count': meal_count,
    }


def partial_calories_for_hour(log_entry, hour_fraction):
    calories = 0
    for item in ordered_log_items(log_entry):
        candidate_hour = item.timestamp.hour + (item.timestamp.minute / 60.0)
        if candidate_hour <= hour_fraction:
            calories += item.food.calories * (item.quantity or 1)
    return calories


def average(values):
    return round(sum(values) / len(values), 2) if values else 0.0


def build_training_rows():
    logs = [
        log for log in Log.query.order_by(Log.user_id.asc(), Log.date.asc(), Log.id.asc()).all()
        if is_valid_log_date(log.date) and ordered_log_items(log)
    ]

    rows = []
    logs_by_user = {}
    for log in logs:
        logs_by_user.setdefault(log.user_id, []).append(log)

    for user_id, user_logs in logs_by_user.items():
        for index, log_entry in enumerate(user_logs):
            user = log_entry.user
            items = ordered_log_items(log_entry)
            history_logs = user_logs[:index]
            final_totals = calculate_totals_until(log_entry)

            if not items or final_totals['calories'] <= 0:
                continue

            snapshots = []
            running_totals = {
                'calories': 0,
                'protein': 0,
                'carbs': 0,
                'fat': 0,
                'meal_count': 0,
            }

            for item in items:
                food = item.food
                quantity = item.quantity or 1
                running_totals = {
                    'calories': running_totals['calories'] + (food.calories * quantity),
                    'protein': running_totals['protein'] + (food.proteins * quantity),
                    'carbs': running_totals['carbs'] + (food.carbs * quantity),
                    'fat': running_totals['fat'] + (food.fats * quantity),
                    'meal_count': running_totals['meal_count'] + quantity,
                }
                snapshots.append((item.timestamp, running_totals.copy()))

            end_of_day_time = datetime_for_log(log_entry, 23, 30)
            snapshots.append((end_of_day_time, final_totals.copy()))

            for snapshot_time, partial_totals in snapshots:
                hour_fraction = snapshot_time.hour + (snapshot_time.minute / 60.0)
                recent_logs = [candidate for candidate in history_logs if candidate.date >= log_entry.date - timedelta(days=7)]
                same_weekday_logs = [candidate for candidate in history_logs if candidate.date.weekday() == log_entry.date.weekday()]

                rows.append({
                    'calories_consumed_so_far': partial_totals['calories'],
                    'protein_so_far': partial_totals['protein'],
                    'carbs_so_far': partial_totals['carbs'],
                    'fat_so_far': partial_totals['fat'],
                    'meal_count_so_far': partial_totals['meal_count'],
                    'hours_passed_today': round(hour_fraction, 2),
                    'day_of_week': log_entry.date.strftime('%A'),
                    'is_weekend': 1 if log_entry.date.weekday() >= 5 else 0,
                    'avg_calories_past_7_days_so_far': average([
                        partial_calories_for_hour(candidate, hour_fraction)
                        for candidate in recent_logs
                    ]),
                    'avg_total_calories_past_7_days': average([
                        calculate_totals_until(candidate)['calories']
                        for candidate in recent_logs
                    ]),
                    'avg_calories_same_day_of_week_so_far': average([
                        partial_calories_for_hour(candidate, hour_fraction)
                        for candidate in same_weekday_logs
                    ]),
                    'avg_total_calories_same_day_of_week': average([
                        calculate_totals_until(candidate)['calories']
                        for candidate in same_weekday_logs
                    ]),
                    'daily_target_kcal': user.daily_cal_target,
                    TARGET_COLUMN: final_totals['calories'],
                })

    return rows


def datetime_for_log(log_entry, hour, minute):
    return log_entry.log_food_items.order_by(LogFoodItem.timestamp.asc()).first().timestamp.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )


def build_fallback_rows():
    base_rows = [
        (320, 16.0, 'Monday', 0, 1, 450, 1850, 420, 1780, 2000, 1850),
        (540, 13.5, 'Tuesday', 0, 2, 600, 1900, 560, 1880, 2000, 1960),
        (860, 15.0, 'Wednesday', 0, 3, 720, 2050, 700, 1980, 2000, 2140),
        (720, 14.0, 'Thursday', 0, 2, 680, 1980, 650, 1930, 2000, 2010),
        (930, 18.0, 'Friday', 0, 4, 810, 2100, 780, 2050, 2000, 2260),
        (1150, 19.0, 'Saturday', 1, 4, 980, 2320, 1010, 2400, 2000, 2580),
        (980, 17.5, 'Sunday', 1, 3, 910, 2240, 940, 2300, 2000, 2410),
    ]

    rows = []
    for calories_so_far, hour, day_name, weekend, meals, avg_partial_recent, avg_total_recent, avg_partial_weekday, avg_total_weekday, target, total in base_rows:
        rows.append({
            'calories_consumed_so_far': calories_so_far,
            'protein_so_far': round(calories_so_far * 0.22 / 4),
            'carbs_so_far': round(calories_so_far * 0.43 / 4),
            'fat_so_far': round(calories_so_far * 0.35 / 9),
            'meal_count_so_far': meals,
            'hours_passed_today': hour,
            'day_of_week': day_name,
            'is_weekend': weekend,
            'avg_calories_past_7_days_so_far': avg_partial_recent,
            'avg_total_calories_past_7_days': avg_total_recent,
            'avg_calories_same_day_of_week_so_far': avg_partial_weekday,
            'avg_total_calories_same_day_of_week': avg_total_weekday,
            'daily_target_kcal': target,
            TARGET_COLUMN: total,
        })

    return rows


def train_model():
    app = create_app()

    with app.app_context():
        rows = build_training_rows()

    if len(rows) < 25:
        rows.extend(build_fallback_rows())

    df = pd.DataFrame(rows)
    print(f"Training rows prepared: {len(df)}")

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    numeric_pipeline = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_pipeline, NUMERIC_FEATURES),
            ('cat', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL_FEATURES),
        ],
        remainder='passthrough',
    )

    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(
            n_estimators=220,
            max_depth=10,
            min_samples_leaf=2,
            random_state=42,
        )),
    ])

    metrics = {}
    if len(df) >= 10:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42
        )
        model_pipeline.fit(X_train, y_train)
        predictions = model_pipeline.predict(X_test)
        metrics = {
            'mae': round(float(mean_absolute_error(y_test, predictions)), 2),
            'r2': round(float(r2_score(y_test, predictions)), 4),
        }
    else:
        model_pipeline.fit(X, y)

    model_pipeline.fit(X, y)

    os.makedirs(os.path.dirname(MODEL_OUTPUT_PATH), exist_ok=True)
    joblib.dump({
        'model': model_pipeline,
        'metrics': metrics,
        'trained_samples': int(len(df)),
        'trained_at': pd.Timestamp.utcnow().isoformat(),
    }, MODEL_OUTPUT_PATH)

    print(f"Model saved to: {MODEL_OUTPUT_PATH}")
    print(f"Metrics: {metrics if metrics else 'Not enough holdout data for evaluation'}")


if __name__ == '__main__':
    train_model()
