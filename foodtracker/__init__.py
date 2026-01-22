from flask import Flask
from .main.routes import main
from .extensions import db
from flask_login import LoginManager
from flask_migrate import Migrate
import os
from .ai.routes import load_ai_prediction_model

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'my_strong_secret_key_here_anukoolbhul'

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate = Migrate(app, db)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(main)
    from .auth.routes import auth_bp
    app.register_blueprint(auth_bp)
    from .dashboard import bp_dashboard
    app.register_blueprint(bp_dashboard , url_prefix='/dashboard')
    
    from .ai import bp_ai_tracker
    app.register_blueprint(bp_ai_tracker, url_prefix='/ai-tracker') 

    with app.app_context():
        load_ai_prediction_model() 

    return app