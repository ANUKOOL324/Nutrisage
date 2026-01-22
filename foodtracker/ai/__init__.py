from flask import Blueprint

bp_ai_tracker = Blueprint('ai', __name__, template_folder='templates', static_folder='static')

from . import routes