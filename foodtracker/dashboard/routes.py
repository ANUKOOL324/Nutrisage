from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from datetime import date, timedelta
from collections import defaultdict
import logging

from . import bp_dashboard
from foodtracker.extensions import db

from foodtracker.models import Log, Food, LogFoodItem 

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]: %(message)s:')

@bp_dashboard.route('/')
@login_required
def dashboard_page():
    return render_template('dashboard.html')

@bp_dashboard.route('/calories_chart_data')
@login_required
def get_calories_chart_data():
    logging.info(f"Fetching calories chart data for user: {current_user.username} (ID: {current_user.id})")

    user_id = current_user.id
    time_range_str = request.args.get('range', '3weeks')
    day_type_str = request.args.get('dayType', 'all')
    unit_str = request.args.get('unit', 'kcal')

    weeks = 3
    if time_range_str == '1week':
        weeks = 1
    elif time_range_str == '2weeks':
        weeks = 2
    elif time_range_str == '3weeks':
        weeks = 3
    elif time_range_str == '4weeks' or time_range_str == 'lastmonth':
        weeks = 4

    end_date = date.today()
    start_date = end_date - timedelta(weeks=weeks)

    daily_macro_data = defaultdict(lambda: {'Protein': 0, 'Carbs': 0, 'Fat': 0})

    all_dates_in_range = []
    current_date_iter = start_date
    while current_date_iter <= end_date:
        # Day type filtering filtering
        if day_type_str == 'weekdays' and current_date_iter.weekday() >= 5:
            current_date_iter += timedelta(days=1)
            continue
        if day_type_str == 'weekends' and current_date_iter.weekday() < 5:
            current_date_iter += timedelta(days=1)
            continue
            
        all_dates_in_range.append(current_date_iter)
        current_date_iter += timedelta(days=1)

    logs_in_range = db.session.query(Log).filter(
        Log.date.between(start_date, end_date),
        Log.user_id == user_id
    ).all()

    for log_entry in logs_in_range:
        log_date_str = log_entry.date.strftime('%Y-%m-%d')
       
        for log_food_item in log_entry.log_food_items: 
            food_item = log_food_item.food 
            
            if unit_str == 'kcal':
                protein_val = food_item.proteins * 4
                carbs_val = food_item.carbs * 4
                fat_val = food_item.fats * 9
            else:
                # Calculate strictly in grams
                protein_val = food_item.proteins
                carbs_val = food_item.carbs
                fat_val = food_item.fats

            daily_macro_data[log_date_str]['Protein'] += protein_val
            daily_macro_data[log_date_str]['Carbs'] += carbs_val
            daily_macro_data[log_date_str]['Fat'] += fat_val

    labels = []
    protein_series = []
    carbs_series = []
    fat_series = []

    for dt in all_dates_in_range:
        date_key = dt.strftime('%Y-%m-%d')
        display_label = dt.strftime('%b %d')

        labels.append(display_label)
        daily_macros = daily_macro_data[date_key]
        protein_series.append(round(daily_macros['Protein'], 2))
        carbs_series.append(round(daily_macros['Carbs'], 2))
        fat_series.append(round(daily_macros['Fat'], 2))

    chart_data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Protein',
                'backgroundColor': '#8BC34A',
                'data': protein_series
            },
            {
                'label': 'Carbs',
                'backgroundColor': '#03A9F4',
                'data': carbs_series
            },
            {
                'label': 'Fat',
                'backgroundColor': '#FF5722',
                'data': fat_series
            }
        ]
    }
    logging.info("Calories chart data prepared and sent.")
    return jsonify(chart_data)


@bp_dashboard.route('/summary_chart_data')
@login_required
def get_summary_chart_data():
    logging.info(f"Fetching summary chart data for user: {current_user.username} (ID: {current_user.id})")

    user = current_user
    today = date.today()
    calories_consumed_today = 0
    protein_consumed_today = 0
    carbs_consumed_today = 0
    fat_consumed_today = 0

    today_log = db.session.query(Log).filter(
        Log.date == today,
        Log.user_id == user.id
    ).first()

    if today_log:
       
        for log_food_item in today_log.log_food_items: 
            food_item = log_food_item.food 
            
            calories_consumed_today += food_item.calories
            protein_consumed_today += food_item.proteins
            carbs_consumed_today += food_item.carbs
            fat_consumed_today += food_item.fats

    daily_cal_target = user.daily_cal_target
    protein_target = user.protein_target
    carbs_target = user.carbs_target
    fat_target = user.fat_target

    remaining_calories = max(0, daily_cal_target - calories_consumed_today)
    remaining_protein = max(0, protein_target - protein_consumed_today)
    remaining_carbs = max(0, carbs_target - carbs_consumed_today)
    remaining_fat = max(0, fat_target - fat_consumed_today)

    summary_data = {
        'consumed_calories': calories_consumed_today,
        'target_calories': daily_cal_target,
        'remaining_calories': remaining_calories,
        'consumed_protein': protein_consumed_today,
        'target_protein': protein_target,
        'consumed_carbs': carbs_consumed_today,
        'target_carbs': carbs_target,
        'consumed_fat': fat_consumed_today,
        'target_fat': fat_target,
    }
    logging.info("Summary chart data prepared and sent.")
    return jsonify(summary_data)