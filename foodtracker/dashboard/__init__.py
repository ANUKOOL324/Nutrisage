from flask import Blueprint

bp_dashboard = Blueprint('dashboard', __name__, template_folder='templates', static_folder='static')

from . import routes