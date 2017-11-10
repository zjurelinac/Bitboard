from datetime import datetime
from flask import Blueprint

from east.data import JSON
from east.security import *

from app import app, east
from app.models import User, Note, Category
from app.util import StringValidator, Success, NoResponse


east.register_validator('fullname', StringValidator(min_length=3, max_length=255))
east.register_validator('email', StringValidator(max_length=256, pattern=r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'))
east.register_validator('password', StringValidator(min_length=6))

east.register_validator('title', StringValidator(min_length=1, max_length=255))
east.register_validator('name', StringValidator(min_length=1, max_length=64))

api = Blueprint('api', __name__)

@east.route(api, '/auth', method='POST')
def obtain_access_token(email: str, password: str) -> JSON:
    """
    Authenticate user

    Authenticates user by his email/password combination and returns a JWT
    API access token (long-term, lasting 30 days), which should be sent in the
    Authorization HTTP header with each subsequent request.

    @exceptions: AuthenticationError, BadParameterError, DoesNotExistError,
                 MissingParameterError
    @response_description: JSON response containing API `access_token` and
                           `user_id`
    @response_format:
    ```js
    {
        "data": {
            "access_token": string,
            "user_id": integer
        }
    }
    ```
    """
    return generate_access_token(User.authenticate(email, password).id)


@east.route(api, '/users', method='POST')
def register_user(fullname: str, email: str, password: str) -> Success:
    """
    Register new user

    Creates a new user with given account data. When using the API in the future,
    the user should be authenticated with the API by his username/password
    combination.

    @exceptions: BadParameterError, MissingParameterError, IntegrityViolationError
    @response_status: 201
    """
    user = User.create(fullname=fullname, email=email,
                       password_hash=make_password_hash(password))
    return 'User successfully created.', 201, {'Location': '/api/users/%d' % user.id}


@east.route(api, '/users/self', method='GET', auth='JWT')
def get_profile() -> JSON(User, view='profile'):
    """
    Get user profile

    Returns active user's profile informations, some of which are considered
    private *(eg. email)* and should not be shared  other users.

    @exceptions:
    @response_description: User profile data
    """
    return active_user()


@east.route(api, '/users/self', method='PUT', auth='JWT')
def edit_profile(fullname: str = None, email: str = None,
                 password: str = None) -> JSON(User, view='profile'):
    """
    Edit user profile

    Modifies user's account data and returns the modified profile informations.

    **If any of the user's account properties is unchanged, it can be left out
    from the request**.

    @exceptions: BadParameterError, IntegrityViolationError
    @response_description: User profile data (after modifications).
    """
    new_values = {
        'fullname': fullname, 'email': email,
        'password_hash': (make_password_hash(password) if password is not None
                          else None)
    }
    (User.update(**{k: v for k, v in new_values.items() if v is not None})
     .where(User.id == active_user().id).execute())
    return User.get(User.id == active_user().id)


@east.route(api, '/users/self', method='DELETE', auth='JWT')
def delete_profile() -> NoResponse:
    """
    Delete user profile

    Permanently deletes user's profile, together with all of his notes and
    categories.

    @response_status: 204
    """
    User.delete().where(User.id == active_user().id).execute()
    return '', 204


@east.route(api, '/notes', method='GET', auth='JWT')
def list_all_notes(start: int = 0, limit: int = 20) -> JSON([Note], view='excerpt'):
    """
    List notes

    Returns a paginated list of user's own notes.

    @response_description: User's notes
    """
    return Note.select().where(Note._author == active_user()).offset(start).limit(limit)


@east.route(api, '/categories', method='GET', auth='JWT')
def list_categories() -> JSON([Category], view='extended'):
    """
    List categories

    Returns a list of all user's categories.

    @response_description: User's categories
    """
    return Category.select().where(Category.owner == active_user())


@east.route(api, '/categories', method='POST', auth='JWT')
def add_category(name: str, parent: str = None) -> Success:
    """
    Create new category

    Creates a new category for the user, can be either top-level or nested.
    **Has to have a unique name.**

    @exceptions: BadParameterError, DoesNotExistError, MissingParameterError
    @response_status: 201
    """
    if parent is not None:
        parent = Category.get(Category.name == parent)

    category = Category.create(name=name, parent=parent, owner=active_user())
    return 'Category successfuly created.', 201, {'Location': '/api/categories/%d' % category.id}


@east.route(api, '/categories/<string:category_name>', method='GET', auth='JWT')
def get_category(category_name) -> JSON(Category, view='full'):
    """
    Get category

    Returns basic category info together with the number of notes present in the
    category.

    @exceptions: AuthorizationError, DoesNotExistError
    @response_description: Category info
    """
    category = Category.get(Category.name == category_name)

    if category.owner != active_user():
        raise AuthorizationError('Not allowed to access this category.')

    return category


@east.route(api, '/categories/<string:category_name>', method='PUT', auth='JWT')
def edit_category(category_name, name: str = None,
                  parent: str = None) -> JSON(Category, view='full'):
    """
    Edit category

    Modifies category info and returns the updated representation.

    @exceptions: AuthorizationError, BadParameterError, DoesNotExistError
    @response_description: Updated category info
    """
    category = Category.get(Category.name == category_name)

    if category.owner != active_user():
        raise AuthorizationError('Not allowed to access this category.')

    new_values = {
        'name': name,
        '_parent': Category.get(Category.name == parent)
                  if parent is not None else None
    }

    (Category.update(**{k: v for k, v in new_values.items() if v is not None})
     .where(Category.id == category.id).execute())

    return Category.get(Category.id == category.id)


@east.route(api, '/categories/<string:category_name>', method='DELETE', auth='JWT')
def delete_category(category_name) -> NoResponse:
    """
    Delete category

    Deletes existing category and returns an empty response.

    @exceptions: AuthorizationError
    @response_status: 204
    """
    category = Category.get(Category.name == category_name)

    if category.owner != active_user():
        raise AuthorizationError('Not allowed to access this category.')

    Category.delete().where(Category.id == category.id).execute()

    return '', 204


@east.route(api, '/categories/<string:category_name>/notes', method='GET', auth='JWT')
def list_category_notes(category_name, start: int = 0, limit: int = 20) -> JSON([Note], view='excerpt'):
    """
    List category notes

    Returns a paginated list of notes belonging to the category.

    @exceptions: AuthorizationError, DoesNotExistError
    @response_description: Notes belonging to the category
    """
    category = Category.get(Category.name == category_name)

    if category.owner != active_user():
        raise AuthorizationError('Not allowed to access this category.')

    return Note.select().where((Note._author == active_user()) & (Note._category == category))


@east.route(api, '/categories/<string:category_name>/notes', method='POST', auth='JWT')
def add_note(category_name, title: str, content: str) -> Success:
    """
    Create new note

    Adds a new note to the user's board. Note's `content` can be Markdown-formatted.

    @exceptions: BadParameterError, DoesNotExistError, MissingParameterError
    @response_status: 201
    """
    category = Category.get(Category.name == category_name)
    note = Note.create(title=title, content=content, _category=category,
                       _author=active_user(), date_created=datetime.now(),
                       date_modified=datetime.now())
    return 'Note successfully added', 201, {'Location': '/api/notes/%d' % note.id}


@east.route(api, '/categories/<string:category_name>/notes/<int:note_id>', method='GET', auth='JWT')
def get_note(category_name, note_id) -> JSON(Note, view='full'):
    """
    Get note

    Returns note contents and metadata. Contents, if in Markdown format, are
    returned raw, so that the client can parse them at will.

    @exceptions: AuthorizationError, DoesNotExistError
    @response_description: Note content and info
    """
    note = Note.get(Note.id == note_id)

    if note._author != active_user():
        raise AuthorizationError('Not allowed to access this note.')

    return note


@east.route(api, '/categories/<string:category_name>/notes/<int:note_id>', method='PUT', auth='JWT')
def edit_note(category_name, note_id, title: str = None, content: str = None,
              category: str = None) -> JSON(Note, view='full'):
    """
    Edit note

    Edits note content, title or category, and returns the updated
    representation.

    @exceptions: AuthorizationError, BadParameterError, DoesNotExistError
    @response_description: Updated note content
    """
    note = Note.get(Note.id == note_id)

    if note._author != active_user():
        raise AuthorizationError('Not allowed to access this note.')

    new_values = {
        'title': title, 'content': content,
        '_category': Category.get(Category.name == category)
                    if category is not None else None,
        'date_modified': datetime.now()
    }

    (Note.update(**{k: v for k, v in new_values.items() if v is not None})
     .where(Note.id == note_id).execute())

    return Note.get(Note.id == note_id)


@east.route(api, '/categories/<string:category_name>/notes/<int:note_id>', method='DELETE', auth='JWT')
def delete_note(category_name, note_id) -> NoResponse:
    """
    Delete existing note

    Deletes an existing note and returns an empty response.

    @exceptions: AuthorizationError, DoesNotExistError
    @response_status: 204
    """
    note = Note.get(Note.id == note_id)

    if note._author != active_user():
        raise AuthorizationError('Not allowed to access this note.')

    Note.delete().where(Note.id == note_id).execute()

    return '', 204

################################################################################

app.register_blueprint(api, url_prefix='/api')

################################################################################

if app.config['EAST_GENERATE_API_DOCS']:
    api_descr = open('app/static/general.md', 'r').read()
    api_descr = ('_**Last generated:** %s_' % datetime.now()) + '\n\n' + api_descr

    east.document_api('Bitboard', '1.0', api_descr)
    east.document_region(api, 'API', '/api', 'Below are listed all available API routes together with detailed explanations of their purpose, parameters, response types and statuses, as well as potential errors.')

    east.document_parameter('query', str, 'Query string containing a term to be searched for among the items.', example='abc')
    east.document_parameter('start', int, 'Index of the first requested item.')
    east.document_parameter('limit', int, 'Amount of requested items to be returned in the response.')

    east.document_parameter('fullname', str, 'User\'s full name, first and last names combined.', example='John Doe')
    east.document_parameter('user_id', int, 'User\'s ID, allows unique identification of each user.', location='path', example='7324')
    east.document_parameter('email', str, 'User\'s email address, used for password recovery, important communications and sending notifications about interesting updates.\n\n**Must be unique**.', example='johndoe@mail.com')
    east.document_parameter('password', str, 'User\'s password, used together with username for API access authentication.\n\n**Minimum length: 6 characters.**')

    east.document_parameter('note_id', int, 'Unique note ID, used to identify it among all the others.', location='path', example='3241')
    east.document_parameter('title', str, 'Note\'s title, limited to **255** characters', example='Shopping list')
    east.document_parameter('content', str, 'Note\'s content, either plain text or Markdown-formatted. Unlimited length.')
    east.document_parameter('category', str, 'Name of note\'s category', example='Household')

    east.document_parameter('category_name', int, 'Unique category name', location='path', example='School')
    east.document_parameter('name', str, 'Category name, visible to the user. **Maximum length: 64 characters.**', example='Programming Tips & Tricks')
    east.document_parameter('parent', str, 'Parent category\'s name, can be left empty if the category has no parent.', example='Computer Science')

    east.register_exceptions([IntegrityViolationError, ValueNotUniqueError,
                              DoesNotExistError, ImpossibleRelationshipError,
                              MalformedTokenError, AuthenticationError,
                              UnknownUserError, APIFeatureNotImplemented,
                              FileSystemError, BadParameterError,
                              MissingParameterError, RemoteOperationError,
                              AuthorizationError])

    east.generate_docs()
