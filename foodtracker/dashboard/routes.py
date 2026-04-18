from collections import defaultdict
from datetime import date, timedelta
import logging

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from . import bp_dashboard
from foodtracker.extensions import db
from foodtracker.models import Log

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]: %(message)s:')

RANGE_TO_DAYS = {
    '7d': 7,
    '14d': 14,
    '30d': 30,
    '90d': 90,
}


def _is_in_day_type(candidate_date, day_type):
    if day_type == 'weekdays':
        return candidate_date.weekday() < 5
    if day_type == 'weekends':
        return candidate_date.weekday() >= 5
    return True


def _normalize_range(range_key):
    return range_key if range_key in RANGE_TO_DAYS else '30d'


def _normalize_unit(unit_key):
    return unit_key if unit_key in {'kcal', 'g'} else 'kcal'


def _normalize_group_by(group_by):
    return group_by if group_by in {'day', 'week'} else 'day'


def _normalize_coverage(coverage):
    return coverage if coverage in {'logged', 'all'} else 'logged'


def _start_of_week(candidate_date):
    return candidate_date - timedelta(days=candidate_date.weekday())


def _format_bucket_label(group_by, bucket_start, bucket_dates):
    if group_by == 'day':
        return bucket_start.strftime('%b %d')

    bucket_end = max(bucket_dates)
    if bucket_start == bucket_end:
        return bucket_start.strftime('%b %d')
    return f"{bucket_start.strftime('%b %d')} - {bucket_end.strftime('%b %d')}"


def build_dashboard_chart_payload(
    user,
    range_key='30d',
    day_type='all',
    unit='kcal',
    group_by='day',
    coverage='logged',
):
    range_key = _normalize_range(range_key)
    unit = _normalize_unit(unit)
    group_by = _normalize_group_by(group_by)
    coverage = _normalize_coverage(coverage)

    end_date = date.today()
    days = RANGE_TO_DAYS[range_key]
    start_date = end_date - timedelta(days=days - 1)

    logs_in_range = db.session.query(Log).filter(
        Log.date.between(start_date, end_date),
        Log.user_id == user.id,
    ).all()

    daily_macro_data = defaultdict(lambda: {
        'Protein': 0,
        'Carbs': 0,
        'Fat': 0,
        'items': 0,
    })

    for log_entry in logs_in_range:
        date_key = log_entry.date
        for log_food_item in log_entry.log_food_items:
            food_item = log_food_item.food
            quantity = log_food_item.quantity or 1
            protein_value = food_item.proteins * quantity
            carbs_value = food_item.carbs * quantity
            fat_value = food_item.fats * quantity

            if unit == 'kcal':
                protein_value *= 4
                carbs_value *= 4
                fat_value *= 9

            daily_macro_data[date_key]['Protein'] += protein_value
            daily_macro_data[date_key]['Carbs'] += carbs_value
            daily_macro_data[date_key]['Fat'] += fat_value
            daily_macro_data[date_key]['items'] += quantity

    visible_dates = []
    current_date_iter = start_date
    while current_date_iter <= end_date:
        if _is_in_day_type(current_date_iter, day_type):
            visible_dates.append(current_date_iter)
        current_date_iter += timedelta(days=1)

    if coverage == 'logged':
        source_dates = [dt for dt in visible_dates if dt in daily_macro_data]
    else:
        source_dates = visible_dates

    bucket_map = {}

    for candidate_date in source_dates:
        bucket_key = candidate_date if group_by == 'day' else _start_of_week(candidate_date)
        bucket = bucket_map.setdefault(bucket_key, {
            'dates': [],
            'Protein': 0,
            'Carbs': 0,
            'Fat': 0,
            'items': 0,
            'logged_days': 0,
        })

        bucket['dates'].append(candidate_date)
        bucket['Protein'] += daily_macro_data[candidate_date]['Protein']
        bucket['Carbs'] += daily_macro_data[candidate_date]['Carbs']
        bucket['Fat'] += daily_macro_data[candidate_date]['Fat']
        bucket['items'] += daily_macro_data[candidate_date]['items']
        if candidate_date in daily_macro_data:
            bucket['logged_days'] += 1

    bucket_keys = sorted(bucket_map.keys())
    labels = []
    protein_series = []
    carbs_series = []
    fat_series = []
    total_series = []
    target_series = []
    average_line_series = []
    bucket_details = []

    daily_target_total = (
        user.daily_cal_target if unit == 'kcal' else user.protein_target + user.carbs_target + user.fat_target
    )

    for bucket_key in bucket_keys:
        bucket = bucket_map[bucket_key]
        total_value = bucket['Protein'] + bucket['Carbs'] + bucket['Fat']
        visible_day_count = max(len(bucket['dates']), 1)
        target_value = daily_target_total * visible_day_count
        average_value = round(total_value / visible_day_count, 2)
        label = _format_bucket_label(group_by, bucket_key, bucket['dates'])

        labels.append(label)
        protein_series.append(round(bucket['Protein'], 2))
        carbs_series.append(round(bucket['Carbs'], 2))
        fat_series.append(round(bucket['Fat'], 2))
        total_series.append(round(total_value, 2))
        target_series.append(round(target_value, 2))
        average_line_series.append(average_value)
        bucket_details.append({
            'label': label,
            'dates': [dt.isoformat() for dt in sorted(bucket['dates'])],
            'protein': round(bucket['Protein'], 2),
            'carbs': round(bucket['Carbs'], 2),
            'fat': round(bucket['Fat'], 2),
            'total': round(total_value, 2),
            'target': round(target_value, 2),
            'logged_days': bucket['logged_days'],
            'visible_days': visible_day_count,
            'items': bucket['items'],
        })

    total_consumed = round(sum(total_series), 2)
    visible_bucket_count = len(bucket_keys)
    logged_day_count = len([dt for dt in visible_dates if dt in daily_macro_data])
    average_per_bucket = round(total_consumed / visible_bucket_count, 2) if visible_bucket_count else 0
    average_per_logged_day = round(
        sum(
            daily_macro_data[dt]['Protein'] + daily_macro_data[dt]['Carbs'] + daily_macro_data[dt]['Fat']
            for dt in visible_dates
            if dt in daily_macro_data
        ) / logged_day_count,
        2,
    ) if logged_day_count else 0

    if bucket_details:
        peak_bucket = max(bucket_details, key=lambda bucket: bucket['total'])
    else:
        peak_bucket = {'label': 'No data', 'total': 0}

    chart_data = {
        'meta': {
            'range': range_key,
            'dayType': day_type,
            'unit': unit,
            'groupBy': group_by,
            'coverage': coverage,
            'startDate': start_date.isoformat(),
            'endDate': end_date.isoformat(),
            'hasData': logged_day_count > 0,
        },
        'labels': labels,
        'datasets': [
            {
                'label': 'Protein',
                'backgroundColor': '#84cc16',
                'borderColor': '#65a30d',
                'data': protein_series,
            },
            {
                'label': 'Carbs',
                'backgroundColor': '#0ea5e9',
                'borderColor': '#0284c7',
                'data': carbs_series,
            },
            {
                'label': 'Fat',
                'backgroundColor': '#f97316',
                'borderColor': '#ea580c',
                'data': fat_series,
            },
        ],
        'totals': {
            'label': 'Total intake',
            'data': total_series,
        },
        'targets': {
            'label': 'Target',
            'data': target_series,
        },
        'averages': {
            'label': 'Average per visible period',
            'data': average_line_series,
        },
        'summary': {
            'totalConsumed': total_consumed,
            'loggedDays': logged_day_count,
            'visibleDays': len(visible_dates),
            'visibleBuckets': visible_bucket_count,
            'averagePerBucket': average_per_bucket,
            'averagePerLoggedDay': average_per_logged_day,
            'peakLabel': peak_bucket['label'],
            'peakValue': peak_bucket['total'],
        },
        'buckets': bucket_details,
    }

    return chart_data


@bp_dashboard.route('/')
@login_required
def dashboard_page():
    return render_template('dashboard.html')


@bp_dashboard.route('/calories_chart_data')
@login_required
def get_calories_chart_data():
    logging.info(f"Fetching calories chart data for user: {current_user.username} (ID: {current_user.id})")

    chart_data = build_dashboard_chart_payload(
        current_user,
        range_key=request.args.get('range', '30d'),
        day_type=request.args.get('dayType', 'all'),
        unit=request.args.get('unit', 'kcal'),
        group_by=request.args.get('groupBy', 'day'),
        coverage=request.args.get('coverage', 'logged'),
    )

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
            quantity = log_food_item.quantity or 1

            calories_consumed_today += food_item.calories * quantity
            protein_consumed_today += food_item.proteins * quantity
            carbs_consumed_today += food_item.carbs * quantity
            fat_consumed_today += food_item.fats * quantity

    daily_cal_target = user.daily_cal_target
    protein_target = user.protein_target
    carbs_target = user.carbs_target
    fat_target = user.fat_target

    remaining_calories = max(0, daily_cal_target - calories_consumed_today)

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
