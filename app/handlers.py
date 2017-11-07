import logging
import traceback

import peewee

from flask import request
from east.exceptions import *

from app import app, db

logger = logging.getLogger(__name__)


@app.errorhandler(BaseAPIException)
def handle_api_errors(e):
    logger.error('API Exception <%s>:: %s', e.name, e.description)
    db.rollback()
    return e.make_response()


@app.errorhandler(peewee.DoesNotExist)
def handle_peewee_doesnotexist(e):
    logger.error('DoesNotExist: %s' % e)
    db.rollback()
    return DoesNotExistError(str(e)).make_response()


@app.errorhandler(404)
def handle_404_error(e):
    logger.error(str(e))
    return APIRouteDoesNotExist().make_response()


@app.errorhandler(405)
def handle_405_error(e):
    logger.error(str(e))
    return APIMethodNotAllowed('Requested route does not support this method [%s].' % request.method).make_response()


@app.errorhandler(Exception)
def handle_generic_exception(e):
    logger.error('Generic <%s>:: %s', e.__class__.__name__, e)
    logger.error(traceback.format_exc())
    db.rollback()
    return BaseAPIException(e.__class__.__name__, str(e)).make_response()
