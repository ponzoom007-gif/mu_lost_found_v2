-- =========================================================================
-- MU Lost & Found - PostgreSQL Schema (For Supabase)
-- สามารถคัดลอกไปวางและกด Run ในหน้า Supabase -> SQL Editor ได้ทันที
-- =========================================================================

-- 1. ตารางสมาชิกผู้ใช้งาน (Users Table)
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

-- 2. ตารางรายการสิ่งของ (Items Table)
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
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

-- 3. กำหนดสิทธิ์ Admin ให้บัญชีหลักอัตโนมัติ
-- UPDATE users SET is_admin = 1 WHERE email = 'ponpong.bum@student.mahidol.ac.th';
