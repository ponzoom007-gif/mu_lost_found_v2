import os
import re
import sqlite3
import uuid
import urllib.request
import urllib.parse
import urllib.error
import json
import math
import secrets
import hmac
import time
import hashlib
import io
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException
from datetime import datetime
import click
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, g, abort, has_request_context
from werkzeug.security import generate_password_hash, check_password_hash

# Try loading .env automatically if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try importing PostgreSQL / Supabase adapter library (psycopg2)
try:
    import psycopg2
    from psycopg2.extras import DictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
SCHEMA_POSTGRES_PATH = os.path.join(BASE_DIR, "schema_postgres.sql")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

# Cloud Environment Variables (Railway / Vercel / Supabase)
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Vercel Serverless environment detection & read-only filesystem handling
IS_VERCEL = os.environ.get("VERCEL") == "1" or os.environ.get("NOW_REGION") is not None
PRODUCTION = os.environ.get("APP_ENV", "production" if IS_VERCEL or os.environ.get("RAILWAY_ENVIRONMENT") or DATABASE_URL else "development") == "production"
DATABASE_PATH = os.environ.get("SQLITE_PATH", os.path.join(BASE_DIR, "database.db"))

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "item-images")

# Google OAuth 2.0 Credentials
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
# Enable ProxyFix to properly forward HTTPS scheme and host headers from Vercel/Railway
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
handler = app  # WSGI Handler export for Vercel
app.secret_key = os.environ.get("SECRET_KEY")
if PRODUCTION and not app.secret_key:
    raise RuntimeError("SECRET_KEY must be configured in production")
app.secret_key = app.secret_key or secrets.token_hex(32)
app.config.update(PRODUCTION=PRODUCTION, DATABASE_URL=DATABASE_URL, DATABASE_PATH=DATABASE_PATH,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=PRODUCTION)

# 1. จำกัดขนาดไฟล์อัปโหลดไม่เกิน 16 MB รองรับภาพถ่ายความละเอียดสูงจากสมาร์ตโฟนหลายภาพ
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 Megabytes
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Regex ตรวจสอบโดเมนอีเมลมหิดลเท่านั้น
MAHIDOL_EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+\.)*mahidol\.(ac\.th|edu)$"

# 1. รายชื่อคณะ / วิทยาลัย / สถาบัน ของมหาวิทยาลัยมหิดล ครบทุกแห่ง (สำหรับหน้าสมัครสมาชิก)
MAHIDOL_FACULTIES = [
    "คณะแพทยศาสตร์ศิริราชพยาบาล",
    "คณะแพทยศาสตร์โรงพยาบาลรามาธิบดี",
    "คณะทันตแพทยศาสตร์",
    "คณะเภสัชศาสตร์",
    "คณะเทคนิคการแพทย์",
    "คณะพยาบาลศาสตร์",
    "คณะสาธารณสุขศาสตร์",
    "คณะกายภาพบำบัด",
    "คณะวิทยาศาสตร์",
    "คณะวิศวกรรมศาสตร์",
    "คณะเทคโนโลยีสารสนเทศและการสื่อสาร (ICT)",
    "คณะสัตวแพทยศาสตร์",
    "คณะสิ่งแวดล้อมและทรัพยากรศาสตร์",
    "คณะสังคมศาสตร์และมนุษยศาสตร์",
    "คณะศิลปศาสตร์",
    "วิทยาลัยนานาชาติ (MUIC)",
    "วิทยาลัยดุริยางคศิลป์ (MS)",
    "วิทยาลัยศาสนศึกษา (CRS)",
    "วิทยาลัยวิทยาศาสตร์และเทคโนโลยีการกีฬา (SS)",
    "วิทยาลัยการจัดการ (CMMU)",
    "สถาบันนวัตกรรมการเรียนรู้",
    "สถาบันโภชนาการ",
    "สถาบันวิจัยประชากรและสังคม",
    "สถาบันพัฒนาสุขภาพอาเซียน",
    "สถาบันชีววิทยาศาสตร์โมเลกุล",
    "สถาบันวิจัยภาษาและวัฒนธรรมเอเชีย",
    "วิทยาเขตกาญจนบุรี",
    "วิทยาเขตนครสวรรค์",
    "วิทยาเขตอำนาจเจริญ",
    "บัณฑิตวิทยาลัย",
    "บุคลากร / หน่วยงานส่วนกลาง / อื่นๆ"
]

# 2. รายชื่อสถานที่ / จุดเกิดเหตุ ภายในมหาวิทยาลัยมหิดล (สำหรับหน้าลงประกาศและค้นหา)
MAHIDOL_LOCATIONS = [
    "คณะวิศวกรรมศาสตร์", "คณะ ICT", "คณะวิทยาศาสตร์", 
    "คณะกายภาพบำบัด", "คณะพยาบาลศาสตร์", "คณะสาธารณสุขศาสตร์",
    "คณะแพทยศาสตร์ศิริราชพยาบาล", "คณะแพทยศาสตร์โรงพยาบาลรามาธิบดี", "คณะทันตแพทยศาสตร์",
    "ศูนย์การเรียนรู้มหิดล (MLC)", "หอสมุดกลาง (Central Library)", 
    "อาคารสิริวิทยา", "วิทยาลัยนานาชาติ (MUIC)", "วิทยาลัยดุริยางคศิลป์",
    "อาคารศูนย์กีฬาและกิจกรรมนักศึกษา", "หอพักนักศึกษา (บ้านศรีตรัง/หอใน)", 
    "โรงอาหารกลาง (SC/MLC)", "อื่นๆ"
]

CATEGORIES = [
    "อุปกรณ์อิเล็กทรอนิกส์",
    "กระเป๋า / กระเป๋าสตางค์",
    "บัตรประชาชน / บัตรนักศึกษา",
    "กุญแจ / พวงกุญแจ",
    "เอกสาร / ตำราเรียน",
    "เครื่องแต่งกาย / เครื่องประดับ",
    "อื่นๆ"
]

def is_admin():
    if "user_id" not in session:
        return False
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT is_admin FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        return bool(user and user["is_admin"] == 1)
    finally:
        conn.close()

@app.template_filter("image_url")
def image_url_filter(filename):
    """Jinja filter to resolve image URL for both Cloud Storage and local static files"""
    if not filename:
        return ""
    if filename.startswith("http://") or filename.startswith("https://"):
        return filename
    return url_for("serve_uploads", filename=filename)

@app.route("/static/uploads/<path:filename>")
def serve_uploads(filename):
    safe_name = os.path.basename(filename)
    tmp_path = os.path.join("/tmp/uploads", safe_name)
    if os.path.exists(tmp_path):
        return send_from_directory("/tmp/uploads", safe_name)
    local_path = os.path.join(BASE_DIR, "static", "uploads", safe_name)
    if os.path.exists(local_path):
        return send_from_directory(os.path.join(BASE_DIR, "static", "uploads"), safe_name)
    return "", 404

@app.context_processor
def inject_global_data():
    return {
        "faculties": MAHIDOL_FACULTIES,
        "locations": MAHIDOL_LOCATIONS,
        "categories": CATEGORIES,
        "is_admin": is_admin(),
        "db_mode": "PostgreSQL (Supabase/Railway)" if (DATABASE_URL and HAS_PSYCOPG2) else "SQLite (Local)",
        "storage_mode": "Supabase Cloud Storage" if (SUPABASE_URL and SUPABASE_KEY) else "Local Disk"
    }

class DBWrapper:
    """Unified wrapper supporting both SQLite and PostgreSQL connections seamlessly."""
    def __init__(self, raw_conn, is_postgres=False):
        self.conn = raw_conn
        self.is_postgres = is_postgres
        self.closed = False

    def execute(self, sql, params=()):
        try:
            if self.is_postgres:
                cursor = self.conn.cursor()
                cursor.execute(sql.replace("?", "%s"), params)
                return cursor
            return self.conn.execute(sql, params)
        except Exception as error:
            if isinstance(error, sqlite3.OperationalError) or (HAS_PSYCOPG2 and isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError))):
                raise DatabaseUnavailable() from None
            raise

    def executescript(self, sql_script):
        if self.is_postgres:
            cursor = self.conn.cursor()
            cursor.execute(sql_script)
            return cursor
        else:
            return self.conn.executescript(sql_script)

    def commit(self):
        try:
            self.conn.commit()
        except Exception as error:
            if isinstance(error, sqlite3.OperationalError) or (HAS_PSYCOPG2 and isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError))):
                raise DatabaseUnavailable() from None
            raise
        if has_request_context():
            g.uploads = []
            for filename in g.pop("pending_image_deletes", []):
                remove_image_file(filename, immediate=True)

    def close(self):
        if not self.closed:
            self.conn.close()
            self.closed = True

class DatabaseUnavailable(Exception):
    pass


def get_db_connection():
    """Never switch data stores when the configured database is unavailable."""
    try:
        if app.config["PRODUCTION"] or app.config.get("DATABASE_URL"):
            if not HAS_PSYCOPG2 or not app.config.get("DATABASE_URL"):
                raise DatabaseUnavailable()
            raw = psycopg2.connect(app.config["DATABASE_URL"], sslmode="require",
                                   cursor_factory=DictCursor, connect_timeout=4)
            conn = DBWrapper(raw, True)
        else:
            raw = sqlite3.connect(app.config["DATABASE_PATH"], timeout=10)
            raw.row_factory = sqlite3.Row
            raw.execute("PRAGMA foreign_keys = ON")
            conn = DBWrapper(raw)
        if has_request_context():
            g.setdefault("connections", []).append(conn)
        return conn
    except Exception:
        raise DatabaseUnavailable() from None


@app.teardown_request
def close_connections(error):
    for filename in g.pop("uploads", []):
        remove_image_file(filename, immediate=True)
    for conn in g.pop("connections", []):
        conn.close()


@app.errorhandler(DatabaseUnavailable)
def database_unavailable(error):
    return "ระบบฐานข้อมูลไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง", 503


def init_db():
    # Explicit setup only: never run migrations while importing or handling a request.
    conn = get_db_connection()
    try:
        with open(SCHEMA_POSTGRES_PATH if conn.is_postgres else SCHEMA_PATH, encoding="utf-8") as source:
            conn.executescript(source.read())
        # Upgrade the two columns absent from early versions without rewriting user data.
        for table, column in (("users", "is_admin"), ("items", "views_count")):
            if conn.is_postgres:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} INTEGER DEFAULT 0")
            else:
                columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                if column not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER DEFAULT 0")
        conn.commit()
    finally:
        conn.close()


@app.cli.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database schema ready")


@app.cli.command("set-admin")
@click.argument("email")
@click.password_option(confirmation_prompt=True)
def set_admin(email, password):
    """Create or reset an administrator explicitly; never reset on startup."""
    if not is_valid_mahidol_email(email) or len(password) < 12:
        raise click.ClickException("Use a Mahidol email and a password of at least 12 characters")
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO users (email, fullname, faculty, password_hash, is_admin) VALUES (?, ?, ?, ?, 1) ON CONFLICT(email) DO UPDATE SET password_hash = excluded.password_hash, is_admin = 1",
                     (email.strip().lower(), "Administrator", "มหาวิทยาลัยมหิดล", generate_password_hash(password, method="pbkdf2:sha256")))
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        conn.execute("INSERT INTO verified_emails (user_id) VALUES (?) ON CONFLICT DO NOTHING", (user["id"],))
        conn.commit()
    finally:
        conn.close()
    click.echo("Administrator updated")


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]

app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def protect_requests():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        if not expected or not hmac.compare_digest(expected, supplied):
            abort(400, "คำขอหมดอายุ กรุณาเปิดหน้าใหม่แล้วลองอีกครั้ง")
    if request.endpoint in {"report", "edit_item"} and request.method == "POST":
        form = request.form
        if form.get("item_type") not in {"lost", "found"} or form.get("category") not in CATEGORIES:
            abort(400, "ประเภทหรือหมวดหมู่สิ่งของไม่ถูกต้อง")
        if form.get("item_type") == "found" and form.get("custody_type") not in {"dropped", "keep_self"}:
            abort(400, "วิธีเก็บสิ่งของไม่ถูกต้อง")
        for key, limit in (("title", 255), ("faculty_location", 255), ("contact_info", 255), ("description", 10000), ("verification_question", 1000), ("drop_location_detail", 2000)):
            if len(form.get(key, "")) > limit:
                abort(400, "ข้อความยาวเกินกำหนด")
        try:
            datetime.strptime(form.get("incident_date", ""), "%Y-%m-%d")
            datetime.strptime(form.get("incident_time", ""), "%H:%M")
        except ValueError:
            abort(400, "วันที่หรือเวลาไม่ถูกต้อง")
    if request.endpoint == "login" and request.method == "POST":
        # Database-backed counters also work across server workers.
        conn = get_db_connection()
        now = time.time()
        for identity in ("ip:" + (request.remote_addr or "unknown"), "email:" + request.form.get("email", "").strip().lower()):
            key = hashlib.sha256(identity.encode()).hexdigest()
            conn.execute("INSERT INTO login_attempts (attempt_key, started, attempts) VALUES (?, ?, 1) ON CONFLICT(attempt_key) DO UPDATE SET attempts = CASE WHEN login_attempts.started < ? THEN 1 ELSE login_attempts.attempts + 1 END, started = CASE WHEN login_attempts.started < ? THEN excluded.started ELSE login_attempts.started END", (key, now, now - 900, now - 900))
            attempts = conn.execute("SELECT attempts FROM login_attempts WHERE attempt_key = ?", (key,)).fetchone()[0]
            conn.commit()
            if attempts > 10:
                conn.close()
                return "ลองเข้าสู่ระบบบ่อยเกินไป กรุณารอ 15 นาที", 429, {"Retry-After": "900"}
        conn.execute("DELETE FROM login_attempts WHERE started < ?", (now - 86400,))
        conn.commit()
        conn.close()


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("กรุณาเข้าสู่ระบบด้วยบัญชีผู้ดูแลระบบก่อนเข้าใช้งาน", "warning")
            return redirect(url_for("login"))
        if not is_admin():
            flash("คุณไม่มีสิทธิ์เข้าถึงส่วนผู้ดูแลระบบ (Admin Only)", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

def is_valid_mahidol_email(email):
    if not email or not isinstance(email, str):
        return False
    return re.match(MAHIDOL_EMAIL_REGEX, email.strip().lower(), re.IGNORECASE) is not None

def upload_to_supabase_storage(file_storage, unique_filename):
    """Uploads file to Supabase Storage bucket via REST API."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        return None
    try:
        file_storage.seek(0)
        file_bytes = file_storage.read()
        mimetype = getattr(file_storage, "mimetype", "image/jpeg") or "image/jpeg"
        
        endpoint = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}/{unique_filename}"
        req = urllib.request.Request(
            endpoint,
            data=file_bytes,
            headers={
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "apikey": SUPABASE_KEY,
                "Content-Type": mimetype
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201):
                return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{unique_filename}"
    except Exception as e:
        app.logger.error("Operation failed (%s)", type(e).__name__)
    return None

def save_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    payload = file_storage.read(5 * 1024 * 1024 + 1)
    if len(payload) > 5 * 1024 * 1024:
        abort(413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as picture:
                if picture.format not in {"PNG", "JPEG", "WEBP"} or picture.width * picture.height > 20_000_000:
                    abort(400, "รองรับ JPG, PNG, WEBP ไม่เกิน 20 ล้านพิกเซล")
                picture.verify()
            with Image.open(io.BytesIO(payload)) as picture:
                picture = ImageOps.exif_transpose(picture).convert("RGB")
                # New encoding discards EXIF/GPS and any appended non-image bytes.
                clean = Image.new("RGB", picture.size)
                clean.paste(picture)
                output = io.BytesIO()
                clean.save(output, format="JPEG", quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        abort(400, "ไฟล์ไม่ใช่รูปภาพที่รองรับหรือเสียหาย")
    output.seek(0)
    name = uuid.uuid4().hex + ".jpg"
    upload = FileStorage(stream=output, filename=name, content_type="image/jpeg")
    if SUPABASE_URL and SUPABASE_KEY:
        stored = upload_to_supabase_storage(upload, name)
        if not stored:
            abort(503, "บันทึกรูปภาพไม่ได้ กรุณาลองใหม่ภายหลัง")
    elif app.config["PRODUCTION"]:
        abort(503, "ระบบจัดเก็บรูปภาพไม่พร้อมใช้งาน")
    else:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        upload.save(os.path.join(app.config["UPLOAD_FOLDER"], name))
        stored = name
    g.setdefault("uploads", []).append(stored)
    return stored

def remove_image_file(filename, immediate=False):
    if has_request_context() and not immediate:
        g.setdefault("pending_image_deletes", []).append(filename)
        return
    """Deletes image file from either Supabase Cloud Storage or local disk."""
    if not filename or not isinstance(filename, str):
        return
    
    # If image is stored in Supabase
    if filename.startswith("http://") or filename.startswith("https://"):
        if SUPABASE_URL and SUPABASE_KEY and filename.startswith(f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/"):
            try:
                obj_name = filename.rsplit("/", 1)[-1]
                endpoint = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}/{obj_name}"
                req = urllib.request.Request(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY
                    },
                    method="DELETE"
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                app.logger.error("Operation failed (%s)", type(e).__name__)
        return

    # If image is stored locally
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_filename)
    if os.path.exists(filepath) and os.path.isfile(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            app.logger.error("Operation failed (%s)", type(e).__name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("กรุณาเข้าสู่ระบบด้วยอีเมลมหาวิทยาลัยมหิดลก่อนทำรายการ", "warning")
            return redirect(url_for("login"))
        conn = get_db_connection()
        user = conn.execute("SELECT id FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        conn.close()
        if not user:
            session.clear()
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# จัดการ Error 413 เมื่ออัปโหลดไฟล์เกิน 5MB
@app.errorhandler(413)
def file_too_large(e):
    return "รูปภาพต้องไม่เกิน 5 MB ต่อไฟล์ และ 16 MB รวมทั้งคำขอ", 413

# จัดการ Error 500 ให้แสดงผลสวยงามและแจ้งเตือนผู้ใช้แทนหน้าขาว
@app.errorhandler(500)
def internal_server_error(e):
    return "เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่ภายหลัง", 500

# ----------------- AUTHENTICATION ----------------- #

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        fullname = request.form.get("fullname", "").strip()
        faculty = request.form.get("faculty", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # ตรวจสอบข้อมูลบังคับ
        if not is_valid_mahidol_email(email):
            flash("ระบบอนุญาตเฉพาะอีเมลมหาวิทยาลัยมหิดลเท่านั้น (เช่น @student.mahidol.ac.th หรือ @mahidol.edu)", "danger")
            return render_template("register.html", form_data=request.form)

        if not fullname:
            flash("กรุณากรอกชื่อ-นามสกุล", "danger")
            return render_template("register.html", form_data=request.form)

        if not faculty:
            flash("กรุณาเลือกคณะ / สังกัด", "danger")
            return render_template("register.html", form_data=request.form)

        if password != confirm_password:
            flash("รหัสผ่านและการยืนยันรหัสผ่านไม่ตรงกัน", "danger")
            return render_template("register.html", form_data=request.form)

        if len(password) < 12:
            flash("รหัสผ่านต้องมีความยาวอย่างน้อย 12 ตัวอักษร เพื่อความปลอดภัย", "danger")
            return render_template("register.html", form_data=request.form)

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            conn = get_db_connection()
            # ตรวจสอบว่ามีอีเมลนี้อยู่แล้วหรือไม่
            existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
            if existing:
                conn.close()
                flash("อีเมลมหิดลนี้ถูกลงทะเบียนไว้ในระบบแล้ว สามารถเข้าสู่ระบบได้ทันที", "warning")
                return redirect(url_for("login"))

            is_adm = 0
            conn.execute(
                "INSERT INTO users (email, fullname, faculty, password_hash, contact_phone, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
                (email, fullname, faculty, hashed_password, contact_phone, is_adm)
            )
            conn.commit()
            conn.close()
            flash("สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบด้วย Google อีเมลเดียวกันหนึ่งครั้งเพื่อยืนยันอีเมล แล้วตั้งรหัสผ่านใหม่", "success")
            return redirect(url_for("login"))
        except DatabaseUnavailable:
            raise
        except Exception as e:
            app.logger.error("Operation failed (%s)", type(e).__name__)
            flash("เกิดข้อผิดพลาดในการลงทะเบียน กรุณาลองใหม่อีกครั้ง", "danger")
            return render_template("register.html", form_data=request.form)

    return render_template("register.html", form_data={})

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not is_valid_mahidol_email(email):
            flash("กรุณากรอกอีเมลของมหาวิทยาลัยมหิดลให้ถูกต้อง (เช่น @student.mahidol.ac.th, @mahidol.edu)", "danger")
            return render_template("login.html", email=email, unregistered=False)

        try:
            conn = get_db_connection()
            user = conn.execute("SELECT users.* FROM users JOIN verified_emails ON verified_emails.user_id = users.id WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
            conn.close()

            # 6. ถ้าไม่มีอีเมลนี้ในระบบ ให้แจ้งเตือนว่ายังไม่ได้สมัครสมาชิก
            if not user:
                flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง หรือยังไม่ได้ยืนยันอีเมลผ่าน Google", "warning")
                return render_template("login.html", email=email, unregistered=True)

            user_dict = dict(user)
            is_match = False
            try:
                is_match = check_password_hash(user_dict["password_hash"], password)
            except Exception:
                pass
            if is_match:
                session.clear()
                session["user_id"] = user_dict["id"]
                session["email"] = user_dict["email"]
                session["fullname"] = user_dict["fullname"]
                session["faculty"] = user_dict["faculty"]
                user_email = str(user_dict.get("email") or "").lower().strip()
                is_adm = 1 if user_dict.get("is_admin") == 1 else 0
                session["is_admin"] = is_adm
                flash(f"ยินดีต้อนรับคุณ {user_dict['fullname']} ({user_dict['email']})", "success")
                return redirect(url_for("index"))
            
            # กรณีมีอีเมลแต่รหัสผ่านผิด
            flash("รหัสผ่านไม่ถูกต้อง กรุณาตรวจสอบตัวพิมพ์เล็ก-ใหญ่และลองใหม่อีกครั้ง", "danger")
            return render_template("login.html", email=email, unregistered=False)

        except DatabaseUnavailable:
            raise
        except Exception as e:
            app.logger.error("Operation failed (%s)", type(e).__name__)
            flash("เกิดข้อผิดพลาดในการเข้าสู่ระบบ กรุณาลองใหม่อีกครั้ง", "danger")
            return render_template("login.html", email=email, unregistered=False)

    return render_template("login.html", email="", unregistered=False)

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("ออกจากระบบเรียบร้อยแล้ว", "info")
    return redirect(url_for("index"))

# ----------------- GOOGLE OAUTH 2.0 ----------------- #

def get_google_redirect_uri():
    explicit_uri = os.environ.get("GOOGLE_REDIRECT_URI")
    if explicit_uri:
        return explicit_uri.strip()
    
    scheme = "https"
    host = request.headers.get("X-Forwarded-Host") or request.host or "127.0.0.1:5001"
    if host.startswith("127.0.0.1") or host.startswith("localhost"):
        scheme = "http"
    elif request.headers.get("X-Forwarded-Proto"):
        scheme = request.headers.get("X-Forwarded-Proto")
        
    return f"{scheme}://{host}/login/google/callback"

@app.route("/login/google")
def login_google():
    if "user_id" in session:
        return redirect(url_for("index"))

    client_id = (os.environ.get("GOOGLE_CLIENT_ID") or GOOGLE_CLIENT_ID or "").strip()
    client_secret = (os.environ.get("GOOGLE_CLIENT_SECRET") or GOOGLE_CLIENT_SECRET or "").strip()

    if not (client_id and client_secret):
        flash("⚙️ ระบบ Google OAuth พร้อมใช้งาน! (กรุณาระบุ GOOGLE_CLIENT_ID และ GOOGLE_CLIENT_SECRET ใน Environment Variables เพื่อเปิดใช้งานบัญชีจริง)", "info")
        return redirect(url_for("login"))
    
    redirect_uri = get_google_redirect_uri()

    session["oauth_state"] = secrets.token_urlsafe(32)
    session["oauth_started"] = time.time()
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={urllib.parse.quote(client_id)}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"state={session['oauth_state']}&"
        "response_type=code&"
        "scope=openid%20email%20profile&"
        "prompt=select_account"
    )
    return redirect(google_auth_url)

@app.route("/login/google/callback")
def login_google_callback():
    expected = session.pop("oauth_state", "")
    started = session.pop("oauth_started", 0)
    if not expected or not hmac.compare_digest(expected, request.args.get("state", "")) or not 0 <= time.time() - started <= 600:
        abort(400, "คำขอเข้าสู่ระบบไม่ถูกต้องหรือหมดอายุ")
    code = request.args.get("code")
    error = request.args.get("error")
    
    if error or not code:
        flash("การเข้าสู่ระบบด้วย Google ถูกยกเลิกหรือไม่สำเร็จ", "warning")
        return redirect(url_for("login"))
    
    try:
        redirect_uri = get_google_redirect_uri()

        client_id = (os.environ.get("GOOGLE_CLIENT_ID") or GOOGLE_CLIENT_ID or "").strip()
        client_secret = (os.environ.get("GOOGLE_CLIENT_SECRET") or GOOGLE_CLIENT_SECRET or "").strip()

        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }).encode("utf-8")
        
        token_req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        
        with urllib.request.urlopen(token_req, timeout=10) as token_resp:
            token_json = json.loads(token_resp.read().decode("utf-8"))
            access_token = token_json.get("access_token")
        
        # Fetch user info from Google
        userinfo_req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(userinfo_req, timeout=10) as userinfo_resp:
            userinfo = json.loads(userinfo_resp.read().decode("utf-8"))
        
        email = userinfo.get("email", "").strip().lower()
        fullname = userinfo.get("name", "").strip() or email.split("@")[0]

        if userinfo.get("email_verified") is not True:
            abort(403, "กรุณายืนยันอีเมลกับ Google ก่อน")

        # Verify Mahidol email domain
        if not is_valid_mahidol_email(email):
            flash(f"อีเมล {email} ไม่ใช่อีเมลของมหาวิทยาลัยมหิดล! ระบบอนุญาตเฉพาะบัญชี @student.mahidol.ac.th หรือ @mahidol.edu เท่านั้น", "danger")
            return redirect(url_for("login"))

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
        
        if not user:
            # Auto-register Google Mahidol user
            dummy_hash = generate_password_hash(uuid.uuid4().hex, method="pbkdf2:sha256")
            is_adm = 0
            conn.execute(
                "INSERT INTO users (email, fullname, faculty, password_hash, contact_phone, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
                (email, fullname, "มหาวิทยาลัยมหิดล (Google Sign-In)", dummy_hash, "", is_adm)
            )
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
        
        first_verification = conn.execute("SELECT user_id FROM verified_emails WHERE user_id = ?", (user["id"],)).fetchone() is None
        if first_verification:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(secrets.token_urlsafe(32), method="pbkdf2:sha256"), user["id"]))
        conn.execute("INSERT INTO verified_emails (user_id) VALUES (?) ON CONFLICT DO NOTHING", (user["id"],))
        conn.commit()
        user_dict = dict(user)
        conn.close()
        session.clear()

        user_email = str(user_dict.get("email") or "").lower().strip()
        is_adm = 1 if user_dict.get("is_admin") == 1 else 0

        session["user_id"] = user_dict["id"]
        session["email"] = user_dict["email"]
        session["fullname"] = user_dict["fullname"]
        session["faculty"] = user_dict["faculty"]
        session["is_admin"] = is_adm
        session["google_verified_at"] = time.time()
        if first_verification:
            return redirect(url_for("set_password"))

        flash(f"เข้าสู่ระบบด้วย Google สำเร็จ! ยินดีต้อนรับคุณ {user_dict['fullname']}", "success")
        return redirect(url_for("index"))

    except (DatabaseUnavailable, HTTPException):
        raise
    except Exception as e:
        app.logger.error("Operation failed (%s)", type(e).__name__)
        flash("เกิดข้อผิดพลาดในการเชื่อมต่อกับ Google", "danger")
        return redirect(url_for("login"))

@app.route("/account/password", methods=["GET", "POST"])
@login_required
def set_password():
    if time.time() - session.get("google_verified_at", 0) > 600:
        flash("กรุณาออกจากระบบและเข้าสู่ระบบด้วย Google อีกครั้งก่อนตั้งรหัสผ่าน", "warning")
        return redirect(url_for("index"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 12 or password != request.form.get("confirm_password"):
            flash("ใช้รหัสผ่านอย่างน้อย 12 ตัวอักษร และยืนยันให้ตรงกัน", "danger")
            return render_template("set_password.html"), 400
        conn = get_db_connection()
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password, method="pbkdf2:sha256"), session["user_id"]))
        conn.commit()
        conn.close()
        session.pop("google_verified_at", None)
        flash("ตั้งรหัสผ่านเรียบร้อยแล้ว", "success")
        return redirect(url_for("index"))
    return render_template("set_password.html")


# ----------------- ITEM ACTIONS ----------------- #

@app.route("/")
def index():
    conn = get_db_connection()
    filters = {key: request.args.get(key, "").strip() for key in ("q", "category", "location", "item_type", "date")}
    clauses, params = [], []
    if filters["q"]:
        clauses.append("(LOWER(items.title) LIKE ? OR LOWER(COALESCE(items.description, '')) LIKE ? OR LOWER(items.faculty_location) LIKE ?)")
        params.extend(["%" + filters["q"].lower() + "%"] * 3)
    for key, column in (("category", "category"), ("location", "faculty_location"), ("item_type", "item_type")):
        if filters[key]:
            clauses.append(f"items.{column} = ?")
            params.append(filters[key])
    if filters["date"]:
        clauses.append("items.incident_date >= ?")
        params.append(filters["date"])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    total = conn.execute("SELECT COUNT(*) FROM items" + where, params).fetchone()[0]
    pages = max(1, math.ceil(total / 9))
    page = min(pages, max(1, request.args.get("page", 1, type=int)))
    items = conn.execute("SELECT items.*, users.fullname as poster_name, users.faculty as poster_faculty FROM items LEFT JOIN users ON items.user_id = users.id" + where + " ORDER BY incident_date DESC, incident_time DESC, items.id DESC LIMIT ? OFFSET ?", params + [9, (page - 1) * 9]).fetchall()
    stats = {"returned_count": conn.execute("SELECT COUNT(*) FROM items WHERE status = 'returned'").fetchone()[0], "active_count": conn.execute("SELECT COUNT(*) FROM items WHERE status = 'active'").fetchone()[0], "member_count": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]}
    conn.close()
    pagination = dict(page=page, total_pages=pages, total_items=total, has_prev=page > 1, has_next=page < pages, prev_num=page-1, next_num=page+1, start_count=(page-1)*9+1 if total else 0, end_count=min(page*9,total))
    return render_template("index.html", items=items, pagination=pagination, stats=stats, filters=filters)

@app.route("/report", methods=["GET", "POST"])
@login_required
def report():
    if request.method == "POST":
        post_token = request.form.get("post_token", "").strip()
        if not re.fullmatch(r"[a-f0-9]{32}", post_token):
            abort(400, "กรุณาเปิดฟอร์มใหม่")
        fingerprint_data = sorted((k, v) for k, v in request.form.items() if k not in {"csrf_token", "post_token"})
        file_hashes = []
        for key, file in request.files.items():
            data = file.stream.read(5 * 1024 * 1024 + 1)
            if len(data) > 5 * 1024 * 1024:
                abort(413)
            file_hashes.append((key, hashlib.sha256(data).hexdigest()))
            file.stream.seek(0)
        fingerprint = hashlib.sha256(json.dumps([fingerprint_data, sorted(file_hashes)], ensure_ascii=False).encode()).hexdigest()
        conn = get_db_connection()
        claimed = conn.execute("INSERT INTO submissions (user_id, token, fingerprint) VALUES (?, ?, ?) ON CONFLICT DO NOTHING", (session["user_id"], post_token, fingerprint)).rowcount
        if not claimed:
            existing = conn.execute("SELECT fingerprint, item_id FROM submissions WHERE user_id = ? AND token = ?", (session["user_id"], post_token)).fetchone()
            conn.close()
            if existing["fingerprint"] != fingerprint:
                abort(409, "รหัสคำขอนี้ถูกใช้กับข้อมูลอื่นแล้ว กรุณาเปิดฟอร์มใหม่")
            return redirect(url_for("detail", item_id=existing["item_id"]))

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        item_type = request.form.get("item_type", "found").strip()
        faculty_location = request.form.get("faculty_location", "").strip()
        incident_date = request.form.get("incident_date", "").strip()
        incident_time = request.form.get("incident_time", "").strip()
        description = request.form.get("description", "").strip()
        verification_question = request.form.get("verification_question", "").strip()

        if not title:
            flash("กรุณาระบุชื่อสิ่งของ", "danger")
            return render_template("report.html", form_data=request.form, post_token=post_token)

        if not faculty_location:
            flash("กรุณาระบุสถานที่หรือคณะ", "danger")
            return render_template("report.html", form_data=request.form, post_token=post_token)

        if not incident_date or not incident_time:
            flash("กรุณาระบุวันที่และเวลาที่เกิดเหตุ", "danger")
            return render_template("report.html", form_data=request.form, post_token=post_token)

        if item_type == "lost":
            custody_type = "keep_self"
            drop_location_detail = ""
            drop_spot_image = None
            contact_info = request.form.get("contact_info", "").strip()
            if not contact_info:
                flash("กรุณาระบุช่องทางการติดต่อสำหรับผู้ที่พบเห็นสิ่งของ", "danger")
                return render_template("report.html", form_data=request.form, post_token=post_token)
        else:
            custody_type = request.form.get("custody_type", "dropped").strip()
            if custody_type == "dropped":
                drop_location_detail = request.form.get("drop_location_detail", "").strip()
                if not drop_location_detail:
                    flash("กรุณาระบุจุดที่นำของไปฝากไว้อย่างละเอียด", "danger")
                    return render_template("report.html", form_data=request.form, post_token=post_token)
                drop_spot_image = save_image(request.files.get("drop_spot_image"))
                contact_info = ""
            else:
                drop_location_detail = ""
                drop_spot_image = None
                contact_info = request.form.get("contact_info", "").strip()
                if not contact_info:
                    flash("กรุณาระบุช่องทางการติดต่อของคุณสำหรับเจ้าของสิ่งของ", "danger")
                    return render_template("report.html", form_data=request.form, post_token=post_token)

        item_image = save_image(request.files.get("item_image"))
        found_spot_image = save_image(request.files.get("found_spot_image"))

        inserted = conn.execute("""
            INSERT INTO items (
                user_id, title, category, item_type, faculty_location,
                incident_date, incident_time, description, verification_question,
                item_image, found_spot_image, custody_type,
                drop_location_detail, drop_spot_image, contact_info
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
        """, (
            session["user_id"], title, category, item_type, faculty_location,
            incident_date, incident_time, description, verification_question,
            item_image, found_spot_image, custody_type,
            drop_location_detail, drop_spot_image, contact_info
        ))
        new_id = inserted.fetchone()[0]
        conn.execute("UPDATE submissions SET item_id = ? WHERE user_id = ? AND token = ?", (new_id, session["user_id"], post_token))
        conn.commit()
        conn.close()

        flash("ลงประกาศเรียบร้อยแล้ว!", "success")
        return redirect(url_for("index"))

    return render_template("report.html", form_data={}, post_token=uuid.uuid4().hex)

@app.route("/item/<int:item_id>")
def detail(item_id):
    conn = get_db_connection()
    # เพิ่มจำนวนการเข้าชม (View Count)
    conn.execute("UPDATE items SET views_count = COALESCE(views_count, 0) + 1 WHERE id = ?", (item_id,))
    conn.commit()

    item = conn.execute("""
        SELECT items.*, users.fullname as poster_name, users.email as poster_email, users.faculty as poster_faculty
        FROM items 
        LEFT JOIN users ON items.user_id = users.id 
        WHERE items.id = ?
    """, (item_id,)).fetchone()

    if item is None:
        conn.close()
        flash("ไม่พบข้อมูลรายการสิ่งของนี้", "danger")
        return redirect(url_for("index"))

    # 4. Smart Match: ค้นหารายการของที่ใกล้เคียงกัน (หมวดหมู่เดียวกัน หรือสถานที่เดียวกัน)
    related_items = conn.execute("""
        SELECT items.*, users.fullname as poster_name, users.faculty as poster_faculty
        FROM items
        LEFT JOIN users ON items.user_id = users.id
        WHERE items.id != ? AND (items.category = ? OR items.faculty_location = ?) AND items.status = 'active'
        ORDER BY items.id DESC
        LIMIT 3
    """, (item_id, item["category"], item["faculty_location"])).fetchall()
    conn.close()

    return render_template("detail.html", item=item, related_items=related_items)

@app.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

    if item is None:
        conn.close()
        flash("ไม่พบข้อมูลรายการที่ต้องการแก้ไข", "danger")
        return redirect(url_for("index"))

    if item["user_id"] != session["user_id"]:
        conn.close()
        flash("คุณไม่มีสิทธิ์แก้ไขโพสต์ของผู้อื่น", "danger")
        return redirect(url_for("detail", item_id=item_id))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        item_type = request.form.get("item_type", "found").strip()
        faculty_location = request.form.get("faculty_location", "").strip()
        incident_date = request.form.get("incident_date", "").strip()
        incident_time = request.form.get("incident_time", "").strip()
        description = request.form.get("description", "").strip()
        verification_question = request.form.get("verification_question", "").strip()

        if not title:
            conn.close()
            flash("กรุณาระบุชื่อสิ่งของ", "danger")
            return render_template("edit.html", item=item)

        if not faculty_location:
            conn.close()
            flash("กรุณาระบุสถานที่หรือคณะ", "danger")
            return render_template("edit.html", item=item)

        if not incident_date or not incident_time:
            conn.close()
            flash("กรุณาระบุวันที่และเวลาที่เกิดเหตุ", "danger")
            return render_template("edit.html", item=item)

        if item_type == "lost":
            custody_type = "keep_self"
            drop_location_detail = ""
            if item["drop_spot_image"]:
                remove_image_file(item["drop_spot_image"])
            drop_spot_image = None
            contact_info = request.form.get("contact_info", "").strip()
            if not contact_info:
                conn.close()
                flash("กรุณาระบุช่องทางการติดต่อ", "danger")
                return render_template("edit.html", item=item)
        else:
            custody_type = request.form.get("custody_type", "dropped").strip()
            if custody_type == "dropped":
                drop_location_detail = request.form.get("drop_location_detail", "").strip()
                if not drop_location_detail:
                    conn.close()
                    flash("กรุณาระบุจุดที่นำของไปฝากไว้อย่างละเอียด", "danger")
                    return render_template("edit.html", item=item)
                contact_info = ""
                new_drop_spot_img = save_image(request.files.get("drop_spot_image"))
                if new_drop_spot_img and item["drop_spot_image"]:
                    remove_image_file(item["drop_spot_image"])
                drop_spot_image = new_drop_spot_img if new_drop_spot_img else item["drop_spot_image"]
            else:
                drop_location_detail = ""
                if item["drop_spot_image"]:
                    remove_image_file(item["drop_spot_image"])
                drop_spot_image = None
                contact_info = request.form.get("contact_info", "").strip()
                if not contact_info:
                    conn.close()
                    flash("กรุณาระบุช่องทางการติดต่อ", "danger")
                    return render_template("edit.html", item=item)

        new_item_img = save_image(request.files.get("item_image"))
        if new_item_img and item["item_image"]:
            remove_image_file(item["item_image"])
        item_image = new_item_img if new_item_img else item["item_image"]

        new_found_spot_img = save_image(request.files.get("found_spot_image"))
        if new_found_spot_img and item["found_spot_image"]:
            remove_image_file(item["found_spot_image"])
        found_spot_image = new_found_spot_img if new_found_spot_img else item["found_spot_image"]

        conn.execute("""
            UPDATE items SET
                title = ?, category = ?, item_type = ?, faculty_location = ?,
                incident_date = ?, incident_time = ?, description = ?, verification_question = ?,
                item_image = ?, found_spot_image = ?, custody_type = ?,
                drop_location_detail = ?, drop_spot_image = ?, contact_info = ?
            WHERE id = ? AND user_id = ?
        """, (
            title, category, item_type, faculty_location,
            incident_date, incident_time, description, verification_question,
            item_image, found_spot_image, custody_type,
            drop_location_detail, drop_spot_image, contact_info,
            item_id, session["user_id"]
        ))
        conn.commit()
        conn.close()

        flash("อัปเดตข้อมูลสิ่งของเรียบร้อยแล้ว!", "success")
        return redirect(url_for("detail", item_id=item_id))

    conn.close()
    return render_template("edit.html", item=item)

@app.route("/item/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

    if item is None:
        conn.close()
        flash("ไม่พบรายการที่ต้องการลบ", "danger")
        return redirect(url_for("index"))

    if item["user_id"] != session["user_id"]:
        conn.close()
        flash("คุณไม่มีสิทธิ์ลบโพสต์ของผู้อื่น", "danger")
        return redirect(url_for("detail", item_id=item_id))

    # ลบไฟล์รูปภาพจริงทั้งหมดที่เกี่ยวข้อง
    remove_image_file(item["item_image"])
    remove_image_file(item["found_spot_image"])
    remove_image_file(item["drop_spot_image"])

    # ลบข้อมูลออกจากฐานข้อมูล
    conn.execute("DELETE FROM items WHERE id = ? AND user_id = ?", (item_id, session["user_id"]))
    conn.commit()
    conn.close()

    flash("ลบประกาศและไฟล์รูปภาพที่เกี่ยวข้องเรียบร้อยแล้ว", "info")
    return redirect(url_for("my_posts"))

@app.route("/my-posts")
@login_required
def my_posts():
    conn = get_db_connection()
    items = conn.execute("""
        SELECT * FROM items 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("my_posts.html", items=items)

@app.route("/item/<int:item_id>/mark-returned", methods=["POST"])
@login_required
def mark_returned(item_id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    
    if item is None:
        conn.close()
        flash("ไม่พบรายการสิ่งของนี้", "danger")
        return redirect(url_for("index"))

    if item["user_id"] == session["user_id"]:
        conn.execute("UPDATE items SET status = 'returned' WHERE id = ?", (item_id,))
        conn.commit()
        if item["item_type"] == "lost":
            flash("อัปเดตสถานะ: ได้รับของคืนเรียบร้อยแล้ว", "success")
        else:
            flash("อัปเดตสถานะ: ส่งคืนเจ้าของเรียบร้อยแล้ว", "success")
    else:
        flash("คุณไม่มีสิทธิ์แก้ไขรายการนี้", "danger")
        
    conn.close()
    return redirect(url_for("detail", item_id=item_id))

# ----------------- ADMIN DASHBOARD & MANAGEMENT ----------------- #

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    
    # 1. รวบรวมสถิติภาพรวม
    total_views_row = conn.execute("SELECT SUM(views_count) FROM items").fetchone()
    total_views = total_views_row[0] if total_views_row and total_views_row[0] is not None else 0
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    active_items = conn.execute("SELECT COUNT(*) FROM items WHERE status = 'active'").fetchone()[0]
    returned_items = conn.execute("SELECT COUNT(*) FROM items WHERE status = 'returned'").fetchone()[0]

    # 2. ข้อมูลสมาชิกพร้อมจำนวนโพสต์
    users = conn.execute("""
        SELECT users.*, COUNT(items.id) as post_count 
        FROM users 
        LEFT JOIN items ON users.id = items.user_id 
        GROUP BY users.id 
        ORDER BY users.created_at DESC
    """).fetchall()

    # 3. ข้อมูลประกาศทั้งหมดในระบบ
    items = conn.execute("""
        SELECT items.*, users.fullname as poster_name, users.email as poster_email, users.faculty as poster_faculty
        FROM items 
        LEFT JOIN users ON items.user_id = users.id 
        ORDER BY items.created_at DESC
    """).fetchall()
    conn.close()

    stats = {
        "total_views": total_views,
        "total_users": total_users,
        "total_items": total_items,
        "active_items": active_items,
        "returned_items": returned_items
    }

    return render_template("admin.html", stats=stats, users=users, items=items)

@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("ไม่สามารถลบบัญชีผู้ดูแลระบบที่คุณกำลังใช้งานอยู่ได้", "danger")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if target_user:
        # ลบรูปภาพของประกาศทั้งหมดของผู้ใช้คนนี้
        user_items = conn.execute("SELECT item_image, found_spot_image, drop_spot_image FROM items WHERE user_id = ?", (user_id,)).fetchall()
        for it in user_items:
            remove_image_file(it["item_image"])
            remove_image_file(it["found_spot_image"])
            remove_image_file(it["drop_spot_image"])
        
        # ลบข้อมูลโพสต์และผู้ใช้
        conn.execute("DELETE FROM items WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        flash(f"ลบผู้ใช้งาน: {target_user['fullname']} ({target_user['email']}) และประกาศที่เกี่ยวข้องเรียบร้อยแล้ว", "success")
    else:
        flash("ไม่พบข้อมูลผู้ใช้งานที่ต้องการลบ", "danger")

    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/items/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_item(item_id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    
    if item:
        remove_image_file(item["item_image"])
        remove_image_file(item["found_spot_image"])
        remove_image_file(item["drop_spot_image"])
        
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        flash(f"แอดมินลบประกาศ '{item['title']}' และรูปภาพที่เกี่ยวข้องเรียบร้อยแล้ว", "info")
    else:
        flash("ไม่พบรายการประกาศที่ต้องการลบ", "danger")

    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/items/<int:item_id>/toggle-status", methods=["POST"])
@admin_required
def admin_toggle_status(item_id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    
    if item:
        new_status = "active" if item["status"] == "returned" else "returned"
        conn.execute("UPDATE items SET status = ? WHERE id = ?", (new_status, item_id))
        conn.commit()
        status_label = "ส่งคืนสำเร็จ/ปิดรายการ" if new_status == "returned" else "กำลังติดตาม"
        flash(f"เปลี่ยนสถานะประกาศ '{item['title']}' เป็น: {status_label}", "success")
    else:
        flash("ไม่พบรายการประกาศ", "danger")

    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/health")
def health():
    conn = get_db_connection()
    conn.execute("SELECT 1")
    conn.close()
    return {"status": "ok"}


@app.route("/db-status")
@admin_required
def db_status():
    conn = get_db_connection()
    is_pg = conn.is_postgres
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    item_count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    conn.close()
    return {
        "is_cloud_postgres": is_pg,
        "database_engine": "PostgreSQL" if is_pg else "SQLite",
        "is_data_persistent": is_pg or app.config["DATABASE_PATH"] != ":memory:",
        "total_users": user_count,
        "total_items": item_count,
        "database_url_configured": bool(os.environ.get("DATABASE_URL")),


    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=False, host="0.0.0.0", port=port)

