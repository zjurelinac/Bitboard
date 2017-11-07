from flask import Flask
from east.database import EastSqliteDatabase

app = Flask(__name__)
app.config.from_pyfile('config.py')

db = EastSqliteDatabase('store.db')

from east import East
from east.security import JWT
from app.models import User

jwt = JWT(app, lambda payload: User.get(User.id == payload['user_id']))
east = East(app)

from app.handlers import *
from app.views import *