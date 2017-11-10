from peewee import *
from werkzeug.security import check_password_hash

from east.database import EastModel
from east.exceptions import *

from app import db


class BBModel(EastModel):
    """Base model, specifies which database is to be used"""

    class Meta:
        database = db


class User(BBModel):
    fullname = CharField(max_length=255)
    email = CharField(max_length=256, unique=True)
    password_hash = CharField()

    __serialization__ = {
        'basic': ['id', 'fullname'],
        'profile': ['id', 'fullname', 'email'],
    }

    @classmethod
    def authenticate(cls, email, password):
        """Return user identified by given `email` and `password`"""
        try:
            user = cls.get(cls.email == email)
            if not check_password_hash(user.password_hash, password):
                raise AuthenticationError('Incorrect password provided.')
            return user
        except DoesNotExist as e:
            raise DoesNotExistError('User with email `%s` does not exist: [%s].'
                                    % (email, e))


DeferredCategory = DeferredRelation()

class Category(BBModel):
    name = CharField(max_length=64, unique=True)
    _parent = ForeignKeyField(DeferredCategory, related_name='children', null=True)
    owner = ForeignKeyField(User, related_name='categories', on_delete='CASCADE')

    __serialization__ = {
        'basic': ['id', 'name'],
        'extended': ['id', 'name', 'parent'],
        'full': ['id', 'name', 'parent', 'notes_count']
    }

    def notes_count(self, view=None) -> int:
        return self.notes.count()


def _category_parent(self, view=None) -> (Category, 'basic'):
    return self._parent.to_jsondict(view='basic') if self._parent is not None else None


DeferredCategory.set_model(Category)
Category.parent = _category_parent


class Note(BBModel):
    title = CharField(max_length=255)
    content = TextField()
    _author = ForeignKeyField(User, related_name='notes', on_delete='CASCADE')
    _category = ForeignKeyField(Category, related_name='notes', on_delete='CASCADE')
    date_created = DateTimeField()
    date_modified = DateTimeField()

    __serialization__ = {
        'excerpt': ['id', 'title', 'category', 'date_modified'],
        'full': ['id', 'title', 'category', 'content', 'date_created', 'date_modified']
    }

    def category(self, view=None) -> (Category, 'basic'):
        return self._category.to_jsondict(view='basic')
