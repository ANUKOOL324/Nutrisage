from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import date, datetime 

class LogFoodItem(db.Model):
    __tablename__ = 'log_food' 

    log_id = db.Column(db.Integer, db.ForeignKey('log.id'), primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    #for revising !!!
    # Relationships from the association object back to Log and Food
    # These create attributes like log_food_item.log (gets the Log object)
    # and log_food_item.food (gets the Food object).
    # The backrefs (log_food_items on Log and Food) make the relationship navigable from either end.
    log = db.relationship('Log', backref=db.backref('log_food_items', cascade="all, delete-orphan", lazy='dynamic'))
    food = db.relationship('Food', backref=db.backref('log_food_items', cascade="all, delete-orphan", lazy=True))

    def __repr__(self):
        return f'<LogFoodItem Log:{self.log_id} Food:{self.food_id} @{self.timestamp.strftime("%Y-%m-%d %H:%M:%S")}>'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer , primary_key=True)
    username = db.Column(db.String(80), unique=True , nullable=False)
    email = db.Column(db.String(120), unique=True , nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean,default=False)
    daily_cal_target = db.Column(db.Integer, default=2000)
    protein_target = db.Column(db.Integer, default=125)
    carbs_target = db.Column(db.Integer, default=225)
    fat_target = db.Column(db.Integer, default=65)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self,password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self , password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User{self.username}>'


class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    proteins = db.Column(db.Integer, nullable=False)
    carbs = db.Column(db.Integer, nullable=False)
    fats = db.Column(db.Integer, nullable=False)

    @property
    def calories(self):
        return self.proteins * 4 + self.carbs * 4 + self.fats * 9

    def __repr__(self):
        return f'<Food{self.name}>'


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer , db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User' , backref='logs' , lazy=True)

    
    def __repr__(self):
        return f'<Log {self.date} by User {self.user_id}>'
        