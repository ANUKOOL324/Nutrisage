from flask import Blueprint, render_template, request, redirect, url_for, flash,abort
from flask_login import login_required, current_user 


from foodtracker.models import Food, Log, User, LogFoodItem 
from foodtracker.extensions import db

from datetime import datetime 

main = Blueprint('main', __name__)


from foodtracker.auth.routes import admin_required

@main.route('/')
def landing():
    return render_template('landing.html')

@main.route('/dashboard')
@login_required
def dashboard():
   
    logs = Log.query.filter_by(user_id=current_user.id).order_by(Log.date.desc()).all()

    log_dates = []

    
    for log in logs:
        proteins = 0
        carbs = 0
        fats = 0
        calories = 0

        for log_food_item in log.log_food_items:
            proteins += log_food_item.line_protein
            carbs += log_food_item.line_carbs
            fats += log_food_item.line_fat
            calories += log_food_item.line_calories

        log_dates.append({
            'log_date' : log,
            'proteins' : proteins,
            'carbs' : carbs,
            'fats' : fats,
            'calories' : calories
        })

    return render_template('index.html', log_dates=log_dates)


@main.route('/admin')
@login_required
@admin_required 
def admin():
    our_users = User.query.order_by(User.id).all()
    return render_template('admin.html' , our_users=our_users)


@main.route('/create_log', methods=['POST'])
@login_required
def create_log():
    date_str = request.form.get('date')

    if (date_str==''):
        flash("Date is required.", "error")
        return redirect(url_for('main.dashboard'))

    try:
        log_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "error")
        return redirect(url_for('main.dashboard'))

    existing_log = Log.query.filter_by(date=log_date, user_id=current_user.id).first()
    if existing_log:
        flash("A log for that date already exists. Opening it instead.", "info")
        return redirect(url_for('main.view', log_id=existing_log.id))

    log = Log(date=log_date)
    log.user_id = current_user.id

    db.session.add(log)
    db.session.commit()

    return redirect(url_for('main.view', log_id=log.id))


@main.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_log(log_id):
  
    log_to_delete = Log.query.get_or_404(log_id)

    
    if log_to_delete.user_id != current_user.id:
        abort(403) 

    try:
        db.session.delete(log_to_delete)
        db.session.commit()
       # flash('Log has been successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting log: {e}', 'danger')
    
    return redirect(url_for('main.dashboard'))


#i will work on it !!
@main.route('/log/<int:log_id>/edit', methods=['POST'])


@main.route('/add')
@login_required
def add():
    foods = Food.query.all()
    return render_template('add.html', foods=foods, food=None)


@main.route('/add', methods=['POST'])
@login_required
def add_post():
    food_name = request.form.get('food-name')
    proteins = int(request.form.get('protein'))
    carbs = int(request.form.get('carbohydrates'))
    fats = int(request.form.get('fat'))

    food_id = request.form.get('food-id')

    if food_id:
        food = Food.query.get_or_404(food_id)
        food.name = food_name
        food.proteins = proteins
        food.carbs = carbs
        food.fats = fats

    else:
        new_food = Food(
            name=food_name,
            proteins=proteins,
            carbs=carbs,
            fats=fats
          
        )
        db.session.add(new_food)

    db.session.commit()
    return redirect(url_for('main.add'))

@main.route('/delete_food/<int:food_id>')
@login_required
def delete_food(food_id):
    food = Food.query.get_or_404(food_id)
    db.session.delete(food)
    db.session.commit()

    return redirect(url_for('main.add'))

@main.route('/edit_food/<int:food_id>')
@login_required
def edit_food(food_id):
    food = Food.query.get_or_404(food_id)
    foods = Food.query.all() 

    return render_template('add.html', food=food, foods=foods)

@main.route('/view/<int:log_id>')
@login_required
def view(log_id):
    log = Log.query.get_or_404(log_id)
    if log.user_id != current_user.id:
        flash("You do not have permission to view that log!", 'danger')
        return redirect(url_for('main.dashboard'))

    foods = Food.query.all()

    totals = {
        'protein' : 0,
        'carbs' : 0,
        'fat' : 0,
        'calories' : 0
    }

    
    for log_food_item in log.log_food_items: 
        totals['protein'] += log_food_item.line_protein
        totals['carbs'] += log_food_item.line_carbs
        totals['fat'] += log_food_item.line_fat
        totals['calories'] += log_food_item.line_calories

    return render_template('view.html', foods=foods, log=log, totals=totals)


@main.route('/add_food_to_log/<int:log_id>', methods=['POST'])
@login_required
def add_food_to_log(log_id):
    log = Log.query.get_or_404(log_id)
    if log.user_id != current_user.id:  
        flash("You cannot modify another user's log!", 'danger')
        return redirect(url_for('main.dashboard'))

    selected_food_id = request.form.get('food-select')
    quantity_raw = request.form.get('quantity', '1')

    try:
        food_id = int(selected_food_id)
        quantity = max(1, int(quantity_raw))
    except (TypeError, ValueError):
        flash("Please choose a valid food and quantity.", 'danger')
        return redirect(url_for('main.view', log_id=log_id))

    food = Food.query.get_or_404(food_id)
    existing_log_food_item = LogFoodItem.query.filter_by(
        log_id=log.id,
        food_id=food.id
    ).first()

    if existing_log_food_item:
        existing_log_food_item.quantity += quantity
        existing_log_food_item.timestamp = datetime.now()
    else:
        new_log_food_item = LogFoodItem(
            log=log,
            food=food,
            quantity=quantity,
            timestamp=datetime.now()
        )
        db.session.add(new_log_food_item)

    db.session.commit()

    return redirect(url_for('main.view', log_id=log_id))


@main.route('/remove_food_from_log/<int:log_id>/<int:food_id>')
@login_required
def remove_food_from_log(log_id, food_id):
    log = Log.query.get_or_404(log_id)
    if log.user_id != current_user.id:
        flash("You cannot modify another user's log!", 'danger')
        return redirect(url_for('main.dashboard'))

    
    
    log_food_item_to_delete = LogFoodItem.query.filter_by(
        log_id=log_id,
        food_id=food_id
    ).first()

    if log_food_item_to_delete: 
        if log_food_item_to_delete.quantity > 1:
            log_food_item_to_delete.quantity -= 1
        else:
            db.session.delete(log_food_item_to_delete)
        db.session.commit()

    return redirect(url_for('main.view', log_id=log_id))
