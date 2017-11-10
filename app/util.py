import re

from east.exceptions import *
from east.data import ResponseType


class StringValidator:
    """String input parameters validator object"""

    def __init__(self, min_length=None, max_length=None, pattern=None):
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = re.compile(pattern) if pattern is not None else None

    def __call__(self, parameter):
        if not isinstance(parameter, str):
            raise TypeError('Wrong parameter type, should be <str>.')
        elif self.min_length is not None and len(parameter) < self.min_length:
            raise ValueError('Parameter is too short.')
        elif self.max_length is not None and len(parameter) > self.max_length:
            raise ValueError('Parameter is too long.')
        elif self.pattern is not None and self.pattern.match(parameter) is None:
            raise ValueError('Parameter value does not match a predefined pattern.')


class Success(ResponseType):
    """Simple success response"""

    content_type = 'application/json'
    description = 'Success response'
    status = 200

    @classmethod
    def format(cls, obj):
        return jsonify({'success': obj})

    @classmethod
    def document(cls):
        return {
            'content_type': cls.content_type,
            'description': cls.description,
            'format': '```js\n{\n\t"success": string\n}```',
            'status': cls.status
        }

class NoResponse(ResponseType):
    """Empty response"""

    content_type = 'application/json'
    description = 'Empty response'
    status = 204

    @classmethod
    def format(cls, obj):
        return ''

    @classmethod
    def document(cls):
        return {
            'content_type': cls.content_type,
            'description': cls.description,
            'format': '',
            'status': cls.status
        }