from flask import Blueprint

urls_blueprint = Blueprint('urls', __name__,)

@urls_blueprint.route('/',methods = ['GET'])
def index():
    return 'urls index route'

