import datetime
import os


APPLICATION_ROOT = '/'

DEBUG = True
TESTING = False

BASE_API_URL = '/'

SECRET_KEY = 'gup%48qsvw+&d4ck4*il-t#-5)*%wn)e$xm+)nmn*es=22q(2d'
STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), './static')
JWT_EXPIRATION_DELTA = datetime.timedelta(days=30)

DATABASE = 'store.db'

EAST_GENERATE_API_DOCS = False
EAST_API_DOCS_LOCATION = 'docs/docs.html'
