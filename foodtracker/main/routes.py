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
          
            food = log_food_item.food 
            
            proteins += food.proteins
            carbs += food.carbs
            fats += food.fats
            calories += food.calories 

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
        food = log_food_item.food

        totals['protein'] += food.proteins
        totals['carbs'] += food.carbs
        totals['fat'] += food.fats
        totals['calories'] += food.calories

    return render_template('view.html', foods=foods, log=log, totals=totals)


@main.route('/add_food_to_log/<int:log_id>', methods=['POST'])
@login_required
def add_food_to_log(log_id):
    log = Log.query.get_or_404(log_id)
    if log.user_id != current_user.id:  
        flash("You cannot modify another user's log!", 'danger')
        return redirect(url_for('main.dashboard'))

    selected_food_id = request.form.get('food-select')
    food = Food.query.get(int(selected_food_id))

    
    new_log_food_item = LogFoodItem(
        log=log,          
        food=food,        
        timestamp=datetime.now() # Store the current timestamp!
    )
    db.session.add(new_log_food_item)
    db.session.commit() # Save it

    return redirect(url_for('main.view', log_id=log_id))


@main.route('/remove_food_from_log/<int:log_id>/<int:food_id>')
@login_required
def remove_food_from_log(log_id, food_id):
    log = Log.query.get(log_id)
    if log.user_id != current_user.id:
        flash("You cannot modify another user's log!", 'danger')
        return redirect(url_for('main.dashboard'))

    
    
    log_food_item_to_delete = LogFoodItem.query.filter_by(
        log_id=log_id,
        food_id=food_id
    ).first()

    if log_food_item_to_delete: 
        db.session.delete(log_food_item_to_delete)
        db.session.commit() # Save the change

    return redirect(url_for('main.view', log_id=log_id))