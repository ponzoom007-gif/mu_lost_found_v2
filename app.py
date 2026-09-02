import os
import re
import sqlite3
import uuid
import urllib.request
import urllib.error
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

# Try importing PostgreSQL / Supabase adapter library (psycopg2)
try:
    import psycopg2
    from psycopg2.extras import DictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
SCHEMA_POSTGRES_PATH = os.path.join(BASE_DIR, "schema_postgres.sql")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

# Cloud Environment Variables (Railway / Vercel / Supabase)
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "item-images")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mu_lost_and_found_secure_production_key_2026")

# 1. จำกัดขนาดไฟล์อัปโหลดไม่เกิน 5 MB ป้องกัน Denial of Service (DoS)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 Megabytes
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_MIME_TYPES = {
    "image/png", "image/jpeg", "image/pjpeg", "image/webp",
    "image/jpg", "image/x-png", "image/jfif"
}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Regex ตรวจสอบโดเมนอีเมลมหิดลเท่านั้น
MAHIDOL_EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+\.)*mahidol\.(ac\.th|edu)$"

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

ADMIN_EMAILS = {
    "ponpong.bum@student.mahidol.ac.th"
}

def is_admin():
    if "user_id" not in session:
        return False
    email = session.get("email", "").lower()
    return email in ADMIN_EMAILS or session.get("is_admin") == 1

@app.template_filter("image_url")
def image_url_filter(filename):
    """Jinja filter to resolve image URL for both Cloud Storage and local static files"""
    if not filename:
        return ""
    if filename.startswith("http://") or filename.startswith("https://"):
        return filename
    return url_for("static", filename=f"uploads/{filename}")

@app.context_processor
def inject_global_data():
    return {
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

    def execute(self, sql, params=()):
        if self.is_postgres:
            # Convert SQLite placeholder '?' to PostgreSQL '%s'
            sql = sql.replace("?", "%s")
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            return cursor
        else:
            return self.conn.execute(sql, params)

    def executescript(self, sql_script):
        if self.is_postgres:
            cursor = self.conn.cursor()
            cursor.execute(sql_script)
            return cursor
        else:
            return self.conn.executescript(sql_script)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_db_connection():
    if DATABASE_URL and HAS_PSYCOPG2:
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
            return DBWrapper(conn, is_postgres=True)
        except Exception as e:
            print(f"PostgreSQL connection failed ({e}), falling back to SQLite.")
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return DBWrapper(conn, is_postgres=False)

def check_and_init_db():
    try:
        conn = get_db_connection()
        if conn.is_postgres:
            # Check if users table exists in PostgreSQL
            cursor = conn.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users')")
            exists_row = cursor.fetchone()
            exists = exists_row[0] if exists_row else False
            if not exists:
                if os.path.exists(SCHEMA_POSTGRES_PATH):
                    with open(SCHEMA_POSTGRES_PATH, "r", encoding="utf-8") as f:
                        conn.executescript(f.read())
                        conn.commit()
                print("Initialized PostgreSQL database tables.")
            else:
                # Ensure admin flag for default admin emails
                for email in ADMIN_EMAILS:
                    conn.execute("UPDATE users SET is_admin = 1 WHERE LOWER(email) = LOWER(?)", (email,))
                conn.commit()
        else:
            # SQLite initialization
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                if os.path.exists(SCHEMA_PATH):
                    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                        conn.executescript(f.read())
                        conn.commit()
                print("Initialized SQLite database tables.")
            else:
                # Auto-migrate SQLite
                cursor = conn.execute("PRAGMA table_info(items)")
                item_cols = [col[1] for col in cursor.fetchall()]
                if "views_count" not in item_cols:
                    conn.execute("ALTER TABLE items ADD COLUMN views_count INTEGER DEFAULT 0")

                cursor = conn.execute("PRAGMA table_info(users)")
                user_cols = [col[1] for col in cursor.fetchall()]
                if "is_admin" not in user_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

                for email in ADMIN_EMAILS:
                    conn.execute("UPDATE users SET is_admin = 1 WHERE LOWER(email) = LOWER(?)", (email,))

                conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error checking/initializing database: {e}")

check_and_init_db()

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

def allowed_file(filename, mimetype):
    if not filename or not isinstance(filename, str) or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    has_allowed_ext = ext in ALLOWED_EXTENSIONS
    mimetype_clean = mimetype.split(";")[0].strip().lower() if mimetype else ""
    is_allowed_mime = mimetype_clean in ALLOWED_MIME_TYPES
    return has_allowed_ext and is_allowed_mime

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
        print(f"Supabase Storage Upload Error: {e}")
    return None

def save_image(file_storage):
    """Saves image either to Supabase Cloud Storage (if configured) or local disk."""
    if file_storage and getattr(file_storage, "filename", None) and file_storage.filename.strip():
        if allowed_file(file_storage.filename, getattr(file_storage, "mimetype", "")):
            ext = file_storage.filename.rsplit(".", 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            
            # If Supabase Cloud Storage is configured, upload to cloud
            if SUPABASE_URL and SUPABASE_KEY:
                cloud_url = upload_to_supabase_storage(file_storage, unique_filename)
                if cloud_url:
                    return cloud_url
            
            # Fallback to local storage
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
            file_storage.seek(0)
            file_storage.save(filepath)
            return unique_filename
        else:
            flash("ประเภทไฟล์ไม่ถูกต้อง! อนุญาตเฉพาะไฟล์รูปภาพ (JPG, PNG, WEBP) เท่านั้น", "danger")
    return None

def remove_image_file(filename):
    """Deletes image file from either Supabase Cloud Storage or local disk."""
    if not filename or not isinstance(filename, str):
        return
    
    # If image is stored in Supabase
    if filename.startswith("http://") or filename.startswith("https://"):
        if SUPABASE_URL and SUPABASE_KEY and SUPABASE_BUCKET in filename:
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
                print(f"Supabase Storage Delete Error: {e}")
        return

    # If image is stored locally
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_filename)
    if os.path.exists(filepath) and os.path.isfile(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Error removing local file {safe_filename}: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("กรุณาเข้าสู่ระบบด้วยอีเมลมหาวิทยาลัยมหิดลก่อนทำรายการ", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# จัดการ Error 413 เมื่ออัปโหลดไฟล์เกิน 5MB
@app.errorhandler(413)
def file_too_large(e):
    flash("ขนาดไฟล์รูปภาพเกินขีดจำกัด (สูงสุด 5 MB ต่อไฟล์) กรุณาลดขนาดรูปภาพก่อนอัปโหลด", "danger")
    return redirect(request.referrer or url_for("index"))

@app.errorhandler(404)
def page_not_found(e):
    flash("ไม่พบหน้าที่คุณต้องการ", "warning")
    return redirect(url_for("index"))

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

        if len(password) < 6:
            flash("รหัสผ่านต้องมีความยาวอย่างน้อย 6 ตัวอักษร เพื่อความปลอดภัย", "danger")
            return render_template("register.html", form_data=request.form)

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (email, fullname, faculty, password_hash, contact_phone) VALUES (?, ?, ?, ?, ?)",
                (email, fullname, faculty, hashed_password, contact_phone)
            )
            conn.commit()
            flash("สมัครสมาชิกสำเร็จ! เข้าสู่ระบบด้วยอีเมลมหิดลของคุณได้ทันที", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("อีเมลมหิดลนี้ถูกลงทะเบียนไว้ในระบบแล้ว", "danger")
            return render_template("register.html", form_data=request.form)
        finally:
            conn.close()

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
            return render_template("login.html", email=email)

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["fullname"] = user["fullname"]
            session["faculty"] = user["faculty"]
            is_adm = 1 if (user["email"].lower() in ADMIN_EMAILS or ("is_admin" in user.keys() and user["is_admin"] == 1)) else 0
            session["is_admin"] = is_adm
            flash(f"ยินดีต้อนรับคุณ {user['fullname']} ({user['email']})", "success")
            return redirect(url_for("index"))
        else:
            flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง", "danger")
            return render_template("login.html", email=email)

    return render_template("login.html", email="")

@app.route("/logout")
def logout():
    session.clear()
    flash("ออกจากระบบเรียบร้อยแล้ว", "info")
    return redirect(url_for("index"))

# ----------------- ITEM ACTIONS ----------------- #

@app.route("/")
def index():
    conn = get_db_connection()
    items = conn.execute("""
        SELECT items.*, users.fullname as poster_name, users.faculty as poster_faculty 
        FROM items 
        LEFT JOIN users ON items.user_id = users.id 
        ORDER BY incident_date DESC, incident_time DESC, items.id DESC
    """).fetchall()
    conn.close()

    return render_template("index.html", items=items)

@app.route("/report", methods=["GET", "POST"])
@login_required
def report():
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
            flash("กรุณาระบุชื่อสิ่งของ", "danger")
            return render_template("report.html", form_data=request.form)

        if not faculty_location:
            flash("กรุณาระบุสถานที่หรือคณะ", "danger")
            return render_template("report.html", form_data=request.form)

        if not incident_date or not incident_time:
            flash("กรุณาระบุวันที่และเวลาที่เกิดเหตุ", "danger")
            return render_template("report.html", form_data=request.form)

        if item_type == "lost":
            custody_type = "keep_self"
            drop_location_detail = ""
            drop_spot_image = None
            contact_info = request.form.get("contact_info", "").strip()
            if not contact_info:
                flash("กรุณาระบุช่องทางการติดต่อสำหรับผู้ที่พบเห็นสิ่งของ", "danger")
                return render_template("report.html", form_data=request.form)
        else:
            custody_type = request.form.get("custody_type", "dropped").strip()
            if custody_type == "dropped":
                drop_location_detail = request.form.get("drop_location_detail", "").strip()
                if not drop_location_detail:
                    flash("กรุณาระบุจุดที่นำของไปฝากไว้อย่างละเอียด", "danger")
                    return render_template("report.html", form_data=request.form)
                drop_spot_image = save_image(request.files.get("drop_spot_image"))
                contact_info = ""
            else:
                drop_location_detail = ""
                drop_spot_image = None
                contact_info = request.form.get("contact_info", "").strip()
                if not contact_info:
                    flash("กรุณาระบุช่องทางการติดต่อของคุณสำหรับเจ้าของสิ่งของ", "danger")
                    return render_template("report.html", form_data=request.form)

        item_image = save_image(request.files.get("item_image"))
        found_spot_image = save_image(request.files.get("found_spot_image"))

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO items (
                user_id, title, category, item_type, faculty_location,
                incident_date, incident_time, description, verification_question,
                item_image, found_spot_image, custody_type,
                drop_location_detail, drop_spot_image, contact_info
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"], title, category, item_type, faculty_location,
            incident_date, incident_time, description, verification_question,
            item_image, found_spot_image, custody_type,
            drop_location_detail, drop_spot_image, contact_info
        ))
        conn.commit()
        conn.close()

        flash("ลงประกาศเรียบร้อยแล้ว!", "success")
        return redirect(url_for("index"))

    return render_template("report.html", form_data={})

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
    conn.close()

    if item is None:
        flash("ไม่พบข้อมูลรายการสิ่งของนี้", "danger")
        return redirect(url_for("index"))
    return render_template("detail.html", item=item)

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

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
