
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    fullname VARCHAR(255) NOT NULL,
    faculty VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(50),
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    item_type VARCHAR(20) NOT NULL CHECK (item_type IN ('found', 'lost')),
    faculty_location VARCHAR(255) NOT NULL,
    incident_date VARCHAR(50) NOT NULL,
    incident_time VARCHAR(50) NOT NULL,
    description TEXT,
    verification_question TEXT,
    item_image VARCHAR(500),
    found_spot_image VARCHAR(500),
    custody_type VARCHAR(50) DEFAULT 'keep_self' CHECK (custody_type IN ('dropped', 'keep_self')),
    drop_location_detail TEXT,
    drop_spot_image VARCHAR(500),
    contact_info VARCHAR(255),
    views_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'returned')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
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

-- Only the trusted server connection may access authentication/request metadata.
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE login_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE verified_emails ENABLE ROW LEVEL SECURITY;
