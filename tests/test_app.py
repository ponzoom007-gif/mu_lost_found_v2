"""Regression tests: only temporary databases, mocked cloud services."""
import io
from contextlib import closing
import json
import time
from urllib.parse import urlparse
import os
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch, MagicMock

with patch.dict(os.environ, {'APP_ENV': 'development', 'DATABASE_URL': '', 'SECRET_KEY': 'test-only-key'}), patch('dotenv.load_dotenv'):
    import app as module
from PIL import Image
from werkzeug.security import generate_password_hash
from werkzeug.test import EnvironBuilder


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        module.app.config.update(TESTING=True, PRODUCTION=False, DATABASE_URL=None,
                                 DATABASE_PATH=str(Path(self.tmp.name)/'test.db'),
                                 UPLOAD_FOLDER=str(Path(self.tmp.name)/'uploads'), SESSION_COOKIE_SECURE=False)
        self.cloud = patch.multiple(module, SUPABASE_URL=None, SUPABASE_KEY=None)
        self.cloud.start()
        self.pg_schema = None
        test_dsn = os.environ.get('TEST_POSTGRES_URL')
        if test_dsn:
            parsed = urlparse(test_dsn)
            if parsed.hostname not in {'localhost', '127.0.0.1'} or parsed.path != '/mu_lost_found_test':
                raise RuntimeError('PostgreSQL tests require a dedicated loopback test database')
            self.pg_schema = 'test_' + uuid.uuid4().hex
            self.pg_admin = module.psycopg2.connect(test_dsn)
            self.pg_admin.autocommit = True
            with self.pg_admin.cursor() as cursor:
                cursor.execute('CREATE SCHEMA ' + self.pg_schema)
            original_connect = module.psycopg2.connect
            self.pg_patch = patch.object(module.psycopg2, 'connect', side_effect=lambda *args, **kwargs: original_connect(test_dsn, cursor_factory=module.DictCursor, options='-c search_path=' + self.pg_schema))
            self.pg_patch.start()
            module.app.config['DATABASE_URL'] = test_dsn
        module.init_db()
        conn = module.get_db_connection()
        for email in ('one@student.mahidol.ac.th', 'two@student.mahidol.ac.th'):
            conn.execute('INSERT INTO users (email, fullname, faculty, password_hash) VALUES (?, ?, ?, ?)',
                         (email, 'Student', 'Engineering', generate_password_hash('correct-password', method='pbkdf2:sha256')))
        conn.execute('INSERT INTO verified_emails (user_id) VALUES (1)')
        conn.commit(); conn.close()
        self.client = self.make_client()

    def tearDown(self):
        if self.pg_schema:
            self.pg_patch.stop()
            with self.pg_admin.cursor() as cursor:
                cursor.execute('DROP SCHEMA ' + self.pg_schema + ' CASCADE')
            self.pg_admin.close()
        self.cloud.stop()
        self.tmp.cleanup()

    def make_client(self, user=1):
        client = module.app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=user, csrf_token='test-csrf', email='one@student.mahidol.ac.th')
        return client

    def form(self, **kwargs):
        data = dict(csrf_token='test-csrf', post_token=uuid.uuid4().hex, title='Wallet',
                    category=module.CATEGORIES[0], item_type='lost', faculty_location='MLC',
                    incident_date='2026-01-01', incident_time='12:00', contact_info='Contact')
        data.update(kwargs)
        return data

    def count(self, table):
        conn = module.get_db_connection()
        result = conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
        conn.close()
        return result

    def picture(self):
        data = io.BytesIO()
        Image.new('RGB', (10, 10), 'red').save(data, format='PNG')
        data.seek(0)
        return data

    def test_csrf_and_logout(self):
        self.assertEqual(self.client.post('/report', data={}).status_code, 400)
        self.assertEqual(self.client.get('/logout').status_code, 405)
        self.assertEqual(self.client.post('/logout', data={'csrf_token':'test-csrf'}).status_code, 302)

    def test_duplicate_and_new_same_title(self):
        data = self.form()
        self.assertEqual(self.client.post('/report', data=data).status_code, 302)
        self.assertEqual(self.client.post('/report', data=data).status_code, 302)
        self.assertEqual(self.count('items'), 1)
        self.assertEqual(self.client.post('/report', data=dict(data,title='Different')).status_code,409)
        self.client.post('/report', data=self.form())
        self.assertEqual(self.count('items'), 2)

    def test_concurrent_duplicate(self):
        data = self.form()
        clients = [self.make_client(), self.make_client()]
        with ThreadPoolExecutor(2) as pool:
            statuses = list(pool.map(lambda c:c.post('/report', data=data).status_code,clients))
        self.assertEqual(statuses,[302,302])
        self.assertEqual(self.count('items'),1)

    def test_fake_image_and_limit(self):
        self.assertEqual(self.client.post('/report', data=self.form(item_image=(io.BytesIO(b'fake'),'fake.jpg'))).status_code,400)
        self.assertEqual(self.count('items'),0)
        self.assertEqual(self.count('submissions'),0)
        with closing(EnvironBuilder(path='/report', method='POST', data=self.form(item_image=(io.BytesIO(b'x'*(5*1024*1024+1)), 'large.jpg')))) as builder:
            environment = builder.get_environ()
            try:
                result = self.client.open(environment)
                self.assertEqual(result.status_code, 413)
                result.close()
            finally:
                environment['wsgi.input'].close()
        self.assertEqual(self.count('items'),0)

    def test_image_cleanup_on_failure(self):
        original = module.DBWrapper.execute
        def fail_insert(conn, sql, params=()):
            if 'INSERT INTO items' in sql:
                raise RuntimeError('simulated failure')
            return original(conn,sql,params)
        with patch.object(module.DBWrapper,'execute',fail_insert):
            with self.assertRaises(RuntimeError):
                self.client.post('/report',data=self.form(item_image=(self.picture(),'image.png')))
        self.assertEqual(list(Path(module.app.config['UPLOAD_FOLDER']).glob('*')),[])
        self.assertEqual(self.count('submissions'),0)

    def test_image_is_reencoded(self):
        response=self.client.post('/report',data=self.form(item_image=(self.picture(),'image.png')))
        self.assertEqual(response.status_code,302)
        files=list(Path(module.app.config['UPLOAD_FOLDER']).glob('*'))
        self.assertEqual(len(files),1)
        with Image.open(files[0]) as image:
            self.assertEqual(image.format,'JPEG')
            self.assertFalse(image.getexif())

    def test_ownership_and_admin(self):
        self.client.post('/report',data=self.form())
        other=self.make_client(2)
        for action in ('delete','mark-returned','edit'):
            other.post('/item/1/'+action,data=self.form(title='Changed'))
        conn=module.get_db_connection()
        row=conn.execute('SELECT title,status FROM items WHERE id=1').fetchone()
        conn.close()
        self.assertEqual(tuple(row),('Wallet','active'))
        with other.session_transaction() as session:
            session['is_admin']=1
        self.assertEqual(other.get('/admin').status_code,302)
        self.assertEqual(other.get('/db-status').status_code,302)

    def test_cloud_failure_does_not_fallback(self):
        module.app.config.update(PRODUCTION=True,DATABASE_URL='postgresql://invalid')
        with patch.object(module.psycopg2,'connect',side_effect=RuntimeError('secret')):
            result=self.client.get('/')
        self.assertEqual(result.status_code,503)
        self.assertNotIn(b'secret',result.data)

    def test_oauth_state_rejected_before_network(self):
        with patch.object(module.urllib.request,'urlopen') as network:
            self.assertEqual(self.client.get('/login/google/callback?code=x&state=bad').status_code,400)
            network.assert_not_called()

    def test_pagination_and_search(self):
        for i in range(12):
            self.client.post('/report',data=self.form(title='Unique old item' if i==0 else 'Wallet '+str(i)))
        first=self.client.get('/')
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.data.count(b'class="item-card '),9)
        result=self.client.get('/?q=Unique')
        self.assertIn(b'Unique old item',result.data)
        self.assertEqual(result.data.count(b'class="item-card '),1)
        self.assertEqual(self.client.get('/?page=2').data.count(b'class="item-card '),3)

    def test_login_verification_and_rate_limit(self):
        client=self.make_client()
        with client.session_transaction() as session:
            session.pop('user_id')
        result=client.post('/login',data={'csrf_token':'test-csrf','email':'one@student.mahidol.ac.th','password':'correct-password'})
        self.assertEqual(result.status_code,302)
        client=self.make_client()
        with client.session_transaction() as session:
            session.pop('user_id')
        for i in range(11):
            result=client.post('/login',data={'csrf_token':'test-csrf','email':'two@student.mahidol.ac.th','password':'correct-password'})
        self.assertEqual(result.status_code,429)
        with client.session_transaction() as session:
            self.assertNotIn('user_id',session)

    def test_templates_render(self):
        self.client.post('/report',data=self.form())
        for path in ('/','/report','/item/1','/item/1/edit','/my-posts'):
            self.assertEqual(self.client.get(path).status_code,200,path)
        conn=module.get_db_connection();conn.execute('UPDATE users SET is_admin=1 WHERE id=1');conn.commit();conn.close()
        self.assertEqual(self.client.get('/admin').status_code,200)
        anonymous=module.app.test_client()
        for path in ('/login','/register'):
            result=anonymous.get(path)
            self.assertEqual(result.status_code,200)
            self.assertIn(b'name="csrf_token"',result.data)

    def test_edit_failure_preserves_original_image(self):
        self.client.post('/report', data=self.form(item_image=(self.picture(), 'old.png')))
        original_files = list(Path(module.app.config['UPLOAD_FOLDER']).glob('*'))
        execute = module.DBWrapper.execute
        def fail_update(conn, sql, params=()):
            if 'UPDATE items SET' in sql:
                raise RuntimeError('simulated update failure')
            return execute(conn, sql, params)
        with patch.object(module.DBWrapper, 'execute', fail_update):
            with self.assertRaises(RuntimeError):
                self.client.post('/item/1/edit', data=self.form(item_image=(self.picture(), 'new.png')))
        self.assertEqual(list(Path(module.app.config['UPLOAD_FOLDER']).glob('*')), original_files)

    def test_storage_outage_has_no_local_fallback(self):
        with patch.multiple(module, SUPABASE_URL='https://example.invalid', SUPABASE_KEY='test-only'), patch.object(module, 'upload_to_supabase_storage', return_value=None):
            result = self.client.post('/report', data=self.form(item_image=(self.picture(), 'image.png')))
        self.assertEqual(result.status_code, 503)
        self.assertEqual(self.count('items'), 0)
        self.assertFalse(Path(module.app.config['UPLOAD_FOLDER']).exists())

    def test_init_does_not_reset_admin_password(self):
        conn = module.get_db_connection()
        conn.execute('UPDATE users SET is_admin=1 WHERE id=1')
        previous = conn.execute('SELECT password_hash FROM users WHERE id=1').fetchone()[0]
        conn.commit(); conn.close()
        module.init_db()
        conn = module.get_db_connection()
        self.assertEqual(conn.execute('SELECT password_hash FROM users WHERE id=1').fetchone()[0], previous)
        conn.close()

    def test_google_verification_replaces_untrusted_password(self):
        client = module.app.test_client()
        with client.session_transaction() as session:
            session.update(oauth_state='good-state', oauth_started=time.time())
        def response(payload):
            mocked = MagicMock()
            mocked.__enter__.return_value.read.return_value = json.dumps(payload).encode()
            return mocked
        with patch.object(module.urllib.request, 'urlopen', side_effect=[response({'access_token':'test-token'}), response({'email':'two@student.mahidol.ac.th', 'name':'Owner', 'email_verified':True})]):
            result = client.get('/login/google/callback?state=good-state&code=test-code')
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.location.endswith('/account/password'))
        conn = module.get_db_connection()
        user = conn.execute('SELECT password_hash FROM users WHERE id=2').fetchone()
        self.assertFalse(module.check_password_hash(user[0], 'correct-password'))
        conn.close()
        self.assertEqual(client.get('/account/password').status_code, 200)
        with client.session_transaction() as session:
            token = session['csrf_token']
        self.assertEqual(client.post('/account/password', data={'csrf_token':token, 'password':'new-safe-password', 'confirm_password':'new-safe-password'}).status_code, 302)
        self.assertEqual(client.get('/login/google/callback?state=good-state&code=test-code').status_code, 400)

    def test_google_unverified_email_rejected(self):
        client = module.app.test_client()
        with client.session_transaction() as session:
            session.update(oauth_state='good-state', oauth_started=time.time())
        token_response = MagicMock()
        token_response.__enter__.return_value.read.return_value = b'{"access_token":"test"}'
        user_response = MagicMock()
        user_response.__enter__.return_value.read.return_value = b'{"email":"two@student.mahidol.ac.th","email_verified":false}'
        with patch.object(module.urllib.request, 'urlopen', side_effect=[token_response, user_response]):
            self.assertEqual(client.get('/login/google/callback?state=good-state&code=test').status_code, 403)

if __name__=='__main__':
    unittest.main()
