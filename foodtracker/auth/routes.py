from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from foodtracker.models import User # Import your User model
from foodtracker.extensions import db


auth_bp = Blueprint('auth', __name__, template_folder='templates', static_folder='static')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password') 

       
        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return render_template('register.html') 
        if User.query.filter_by(username=username).first():
            flash('Username already taken! Please choose a different one.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered! Please use a different email.', 'danger')
            return render_template('register.html')

       
        new_user = User(username=username, email=email)
        new_user.password = password
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

   
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
   
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

       
        user = User.query.filter_by(username=username).first()

        
        if user and user.verify_password(password):
            login_user(user) 
           # flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'danger') 

    
    return render_template('login.html')

@auth_bp.route('/logout',methods=['GET', 'POST'])
@login_required 
def logout():
    logout_user() 
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


from functools import wraps
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
       
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access that page.', 'warning')
            return redirect(url_for('main.dashboard')) 
        return f(*args, **kwargs)
    return decorated_function
