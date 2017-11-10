import json
import random
import string
import unittest

from datetime import datetime

from east.exceptions import *
from east.helpers import get_class_plural_name
from east.security import generate_access_token, make_password_hash

from app import app as base_app, db
import app.models as models


# Utilities

def rand_str(n):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


def _validate_format(form, obj):
    if isinstance(form, list):
        if not isinstance(obj, list):
            return False
        return all(_validate_format(form[0], item) for item in obj)
    elif isinstance(form, dict):
        if not isinstance(obj, dict): return False
        return all((key in obj) and (obj[key] is None or _validate_format(form[key], obj[key])) for key in form)
    return True


def _send_request(app, url, method='GET', data={}, headers={}, jwt_token=None):
    if jwt_token is not None:
        headers['Authorization'] = 'Bearer %s' % jwt_token
    response = getattr(app, method.lower())(url, data=data, headers=headers)
    data = json.loads(response.get_data(as_text=True)) if response.status_code != 204 else None
    return response, data


class API:
    MODELS = [models.User, models.Note, models.Category]

    def __init__(self):
        self.app = base_app
        self.test_app = self.app.test_client()
        self.user = None
        self.token = None

        db.create_tables(self.MODELS, safe=True)

    def send_request(self, url, method='GET', data={}, headers={}, jwt_token=None):
        if jwt_token is None and self.token is not None:
            jwt_token = self.token
        return _send_request(self.test_app, url, method, data, headers, jwt_token)

    # Utilities

    def set_user(self, user):
        self.user = user
        with self.app.app_context():
            self.token = generate_access_token(user.id)['access_token']

    def clear_user(self):
        self.user = None
        self.token = None

    def clear_db(self):
        db.truncate_tables(self.MODELS)

    def create_user(self, fullname):
        return models.User.create(fullname=fullname, email=('%s@mail.com' % fullname.replace(' ', '.').lower()),
                                  password_hash=make_password_hash('lozinka'))

    def create_user_note(self, user, title, content, category):
        return models.Note.create(title=title, content=content, _category=category,
                                  _author=user, date_created=datetime.now(),
                                  date_modified=datetime.now())

    def create_user_category(self, user, name, parent=None):
        return models.Category.create(name=name, _parent=parent, owner=user)


_TEST_API = API()

# Tests

class APITest(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.api = _TEST_API
        self.app = _TEST_API.test_app

    def setUp(self):
        self.api.clear_db()
        self.api.clear_user()

    def tearDown(self):
        pass

    def check_success(self, url, method='GET', data={}, headers={},
                      jwt_token=None, expected_status=200):
        resp, _ = self.api.send_request(url, method, data, headers, jwt_token)
        self.assertEqual(resp.status_code, expected_status)
        return resp

    def check_error(self, url, method='GET', data={}, headers={},
                    jwt_token=None, error=None):
        resp, data = self.api.send_request(url, method, data, headers, jwt_token)
        self.assertEqual(resp.status_code, error.status_code)
        self.assertEqual(data['error']['name'], error.__name__)
        return resp

    def check_data(self, url, method='GET', data={}, headers={},
                   jwt_token=None, expected_status=200, model=None, is_list=False, view=None):
        resp, data = self.api.send_request(url, method, data, headers, jwt_token)
        self.assertEqual(resp.status_code, expected_status)
        self.assertIn('data', data)
        if is_list:
            expected_format = {get_class_plural_name(model): [model.document_response(view=view)]}
        else:
            expected_format = model.document_response(view=view)
        self.assertTrue(_validate_format({'data': expected_format}, data))
        return data['data']


class UserRegistrationTest(APITest):
    def test_registration_ok(self):
        self.check_success('/api/users', 'POST',
                           data={'fullname': 'Mirko Slavkovic', 'email': 'mslavkovic@mail.com', 'password': 'lozinka'},
                           expected_status=201)

    def test_registration_missing_param(self):
        self.check_error('/api/users', 'POST',
                         data={'email': 'mslavkovic@mail.com', 'password': 'lozinka'},
                         error=MissingParameterError)

    def test_registration_bad_param(self):
        self.check_error('/api/users', 'POST',
                         data={'fullname': 'Mirko Slavkovic', 'email': 'mslavkovic.at.mail.com', 'password': 'lozinka'},
                         error=BadParameterError)

    def test_registration_integrity_violation(self):
        self.api.create_user('Marko Markovic')
        self.check_error('/api/users', 'POST',
                         data={'fullname': 'Mirko Slavkovic', 'email': 'marko.markovic@mail.com', 'password': 'lozinka'},
                         error=IntegrityViolationError)


class UserAuthTest(APITest):
    def test_auth_ok(self):
        self.api.create_user('Mirko Mirkovic')
        resp, data = self.api.send_request('/api/auth', 'POST', {'email': 'mirko.mirkovic@mail.com', 'password': 'lozinka'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(_validate_format({'data':{'user_id': 'int', 'access_token': 'string'}}, data))

    def test_auth_bad_credentials(self):
        self.api.create_user('Mirko Mirkovic')
        self.check_error('/api/auth', 'POST', {'email': 'mirko.mirkovic@mail.com', 'password': 'kriva_lozinka'}, error=AuthenticationError)

    def test_auth_missing_credentials(self):
        self.api.create_user('Mirko Mirkovic')
        self.check_error('/api/auth', 'POST', {'email': 'mirko.mirkovic@mail.com'}, error=MissingParameterError)

    def test_auth_bad_email(self):
        self.api.create_user('Mirko Mirkovic')
        self.check_error('/api/auth', 'POST', {'email': 'MARKO.mirkovic@mail.com', 'password': 'lozinka'}, error=DoesNotExistError)


class UserProfileTest(APITest):
    def test_get_ok(self):
        user = self.api.create_user('Mirko Mirkovic')
        self.api.set_user(user)
        self.check_data('/api/users/self', model=models.User, view='profile')

    def test_edit_ok(self):
        user = self.api.create_user('Mirko Mirkovic')
        self.api.set_user(user)
        self.check_data('/api/users/self', 'PUT', data={'fullname': 'Marko Mirkovic'}, model=models.User, view='profile')

    def test_edit_bad_param(self):
        user = self.api.create_user('Mirko Mirkovic')
        self.api.set_user(user)
        self.check_error('/api/users/self', 'PUT', data={'email': 'mirko.mail.com'}, error=BadParameterError)

    def test_edit_integrity_violation(self):
        self.api.create_user('Slavko')
        user = self.api.create_user('Mirko Mirkovic')
        self.api.set_user(user)
        self.check_error('/api/users/self', 'PUT', data={'email': 'slavko@mail.com'}, error=IntegrityViolationError)

    def test_delete_ok(self):
        user = self.api.create_user('Mirko Mirkovic')
        self.api.set_user(user)
        self.check_success('/api/users/self', 'DELETE', expected_status=204)
        self.check_error('/api/users/self', error=UnknownUserError)


class NoteTest(APITest):
    def setUp(self):
        super().setUp()

        self.user = self.api.create_user('Mirko Mirkovic')
        self.api.set_user(self.user)
        self.category = self.api.create_user_category(self.user, 'stuff')

    def test_list_ok(self):
        for i in range(10):
            self.api.create_user_note(self.user, 'Note %d' % i, rand_str(100), self.category)

        data = self.check_data('/api/notes', model=models.Note, is_list=True, view='excerpt')
        self.assertEqual(len(data['notes']), 10)

    def test_paginate_ok(self):
        for i in range(10):
            self.api.create_user_note(self.user, 'Note %d' % i, rand_str(100), self.category)

        data = self.check_data('/api/notes', data={'limit': 5, 'start': 3}, model=models.Note, is_list=True, view='excerpt')
        self.assertEqual(len(data['notes']), 5)
        min_title = min(n['title'] for n in data['notes'])
        self.assertEqual(min_title, 'Note 3')

    def test_add_ok(self):
        resp = self.check_success('/api/categories/stuff/notes', 'POST', data={'title': 'Test note', 'content': rand_str(100)}, expected_status=201)
        self.assertIn('Location', resp.headers)

    def test_add_bad_param(self):
        self.check_error('/api/categories/stuff/notes', 'POST', data={'title': rand_str(256), 'content': rand_str(100)}, error=BadParameterError)

    def test_add_missing_param(self):
        self.check_error('/api/categories/stuff/notes', 'POST', data={'title': 'T'}, error=MissingParameterError)

    def test_add_no_category(self):
        self.check_error('/api/categories/nonexistent/notes', 'POST', data={'title': 'T', 'content': rand_str(100)}, error=DoesNotExistError)

    def test_get_ok(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        data = self.check_data('/api/categories/stuff/notes/%d' % note.id, model=models.Note, view='full')
        self.assertEqual(data['title'], 'Test note')

    def test_get_unauthorized(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        user2 = self.api.create_user('Slavko Slavkovic')
        self.api.set_user(user2)
        self.check_error('/api/categories/stuff/notes/%d' % note.id, error=AuthorizationError)

    def test_get_doesnt_exist(self):
        self.check_error('/api/categories/stuff/notes/172', error=DoesNotExistError)

    def test_edit_ok(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        data = self.check_data('/api/categories/stuff/notes/%d' % note.id, 'PUT', data={'content': rand_str(150)}, model=models.Note, view='full')
        self.assertEqual(note.title, data['title'])
        self.assertNotEqual(note.content, data['content'])
        self.assertNotEqual(data['date_created'], data['date_modified'])

    def test_edit_doesnt_exist(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        self.check_error('/api/categories/stuff/notes/172', 'PUT', data={'content': rand_str(100)}, error=DoesNotExistError)

    def test_edit_unauthorized(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        user2 = self.api.create_user('Slavko Slavkovic')
        self.api.set_user(user2)
        self.check_error('/api/categories/stuff/notes/%d' % note.id, 'PUT', data={'content': rand_str(100)}, error=AuthorizationError)

    def test_edit_no_category(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        self.check_error('/api/categories/stuff/notes/%d' % note.id, 'PUT', data={'category': 'nonexistent'}, error=DoesNotExistError)

    def test_edit_bad_param(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        self.check_error('/api/categories/stuff/notes/%d' % note.id, 'PUT', data={'title': rand_str(256)}, error=BadParameterError)

    def test_delete_ok(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        self.check_success('/api/categories/stuff/notes/%d' % note.id, 'DELETE', expected_status=204)

    def test_delete_unauthorized(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        user2 = self.api.create_user('Slavko Slavkovic')
        self.api.set_user(user2)
        self.check_error('/api/categories/stuff/notes/%d' % note.id, 'DELETE', error=AuthorizationError)

    def test_delete_doesnt_exist(self):
        note = self.api.create_user_note(self.user, 'Test note', rand_str(100), self.category)
        self.check_error('/api/categories/stuff/notes/172', 'PUT', error=DoesNotExistError)


class CategoryTest(APITest):
    def setUp(self):
        super().setUp()

        self.user = self.api.create_user('Mirko Mirkovic')
        self.api.set_user(self.user)
        self.category = self.api.create_user_category(self.user, 'base')

    def test_list_ok(self):
        for i in range(10):
            self.api.create_user_category(self.user, 'Category %d' % i)

        data = self.check_data('/api/categories', model=models.Category, is_list=True, view='extended')
        self.assertEqual(len(data['categories']), 11)

    def test_new_ok(self):
        resp = self.check_success('/api/categories', 'POST', data={'name': 'stuff'}, expected_status=201)
        self.assertIn('Location', resp.headers)

    def test_new_missing_param(self):
        self.check_error('/api/categories', 'POST', data={'parent': 'base'}, error=MissingParameterError)

    def test_new_bad_param(self):
        self.check_error('/api/categories', 'POST', data={'name': rand_str(65)}, error=BadParameterError)

    def test_new_no_parent(self):
        self.check_error('/api/categories', 'POST', data={'name': 'test', 'parent': 'nonexistent'}, error=DoesNotExistError)

    def test_get_ok(self):
        data = self.check_data('/api/categories/base', model=models.Category, view='full')
        self.assertEqual(data['name'], 'base')
        self.assertEqual(data['parent'], None)

    def test_get_unauthorized(self):
        user2 = self.api.create_user('Slavko Slavkovic')
        self.api.set_user(user2)
        self.check_error('/api/categories/base', error=AuthorizationError)

    def test_get_doesnt_exist(self):
        self.check_error('/api/categories/nonexistent', error=DoesNotExistError)

    def test_edit_ok(self):
        data = self.check_data('/api/categories/base', 'PUT', data={'name': 'base_edited'}, model=models.Category, view='full')
        self.assertEqual(data['name'], 'base_edited')

    def test_edit_doesnt_exist(self):
        self.check_error('/api/categories/nonexistent', 'PUT', data={'name': 'base_edited'}, error=DoesNotExistError)

    def test_edit_unauthorized(self):
        user2 = self.api.create_user('Slavko Slavkovic')
        self.api.set_user(user2)
        self.check_error('/api/categories/base', 'PUT', data={'name': 'base_edited'}, error=AuthorizationError)

    def test_edit_no_parent(self):
        self.check_error('/api/categories/base', 'PUT', data={'parent': 'nonexistent'}, error=DoesNotExistError)

    def test_edit_bad_param(self):
        self.check_error('/api/categories/nonexistent', 'PUT', data={'name': rand_str(65)}, error=BadParameterError)

    def test_notes_ok(self):
        alt_cat = self.api.create_user_category(self.user, 'alt_category')
        for i in range(10):
            self.api.create_user_note(self.user, 'Note %d' % i, rand_str(100), self.category if i % 2 == 0 else alt_cat)

        data = self.check_data('/api/categories/base/notes', model=models.Note, is_list=True, view='excerpt')
        self.assertEqual(len(data['notes']), 5)

    def test_notes_unauthorized(self):
        user2 = self.api.create_user('Slavko Slavkovic')
        self.api.set_user(user2)
        self.check_error('/api/categories/base/notes', error=AuthorizationError)

    def test_notes_doesnt_exist(self):
        self.check_error('/api/categories/nonexistent/notes', error=DoesNotExistError)


if __name__ == '__main__':
    unittest.main()


# Test workflow:
#   1. create test app
#   2. initialize DB
#   3. prepare for request testing (get token, create needed model instances and setup system state)
#   4. send the request and collect results
#   5. test results
#   6. cleanup system state
