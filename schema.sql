
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    fullname TEXT NOT NULL,
    faculty TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    contact_phone TEXT,
    is_admin INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK (item_type IN ('found', 'lost')),
    faculty_location TEXT NOT NULL,
    incident_date TEXT NOT NULL,
    incident_time TEXT NOT NULL,
    description TEXT,
    verification_question TEXT,
    item_image TEXT,
    found_spot_image TEXT,
    custody_type TEXT DEFAULT 'keep_self' CHECK (custody_type IN ('dropped', 'keep_self')),
    drop_location_detail TEXT,
    drop_spot_image TEXT,
    contact_info TEXT,
    views_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'returned')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS submissions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    item_id INTEGER,
    PRIMARY KEY (user_id, token)
);
CREATE TABLE IF NOT EXISTS login_attempts (
    attempt_key VARCHAR(64) PRIMARY KEY,
    started DOUBLE PRECISION NOT NULL,
    attempts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS verified_emails (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS items_feed_idx ON items (incident_date DESC, incident_time DESC, id DESC);
CREATE INDEX IF NOT EXISTS items_user_idx ON items (user_id);
