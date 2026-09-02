-- ตารางข้อมูลผู้ใช้งาน (ล็อกสิทธิ์เฉพาะอีเมลมหิดล)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,              -- เช่น somchai.suk@student.mahidol.ac.th
    fullname TEXT NOT NULL,                  -- ชื่อ-นามสกุล
    faculty TEXT NOT NULL,                   -- คณะ/ส่วนงานของผู้ใช้
    password_hash TEXT NOT NULL,             -- รหัสผ่านเข้ารหัส
    contact_phone TEXT,                      -- เบอร์โทรศัพท์
    is_admin INTEGER DEFAULT 0,              -- 1 = ผู้ดูแลระบบ, 0 = ผู้ใช้งานทั่วไป
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตารางข้อมูลสิ่งของ
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    item_type TEXT NOT NULL,                 -- 'found' หรือ 'lost'
    faculty_location TEXT NOT NULL,
    incident_date TEXT NOT NULL,             -- YYYY-MM-DD
    incident_time TEXT NOT NULL,             -- HH:MM
    description TEXT,
    
    -- ระบบป้องกันการสวมรอย (Anti-Spoofing Claim Question / Secret Clue)
    verification_question TEXT,              -- เช่น "เคสข้างในมีสติ๊กเกอร์รูปอะไร?" หรือ "วอลเปเปอร์หน้าจอคือรูปอะไร?"
    
    item_image TEXT,                         -- รูปของ
    found_spot_image TEXT,                   -- รูปจุดที่พบ
    custody_type TEXT NOT NULL,              -- 'dropped' หรือ 'keep_self'
    drop_location_detail TEXT,               -- รายละเอียดจุดรับฝาก
    drop_spot_image TEXT,                    -- รูปจุดรับฝาก
    contact_info TEXT,                       -- ช่องทางติดต่อ
    views_count INTEGER DEFAULT 0,           -- จำนวนครั้งที่ถูกเปิดเข้าชม
    status TEXT DEFAULT 'active',            -- 'active' หรือ 'returned'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
