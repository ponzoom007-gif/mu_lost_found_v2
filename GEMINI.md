# Mahidol University Lost & Found Hub (v2) - AI Agent Rules

## 1. Project Overview & Architecture
- **Framework**: Python 3.9+ with Flask and Gunicorn
- **Database**: Dual Database Mode via `DBWrapper` in `app.py`
  - **Cloud Database**: Supabase PostgreSQL (`DATABASE_URL` with SSL required)
  - **Local Database**: SQLite (`database.db` locally, `/tmp/database.db` on serverless Vercel)
- **File Storage**: Dual storage mode via `upload_to_supabase_storage()`
  - Cloud: Supabase Storage Bucket `item-images`
  - Local fallback: `static/uploads/` (or `/tmp/uploads` on Vercel)
- **Authentication**:
  - Email/Password with PBKDF2-SHA256 salted hashing
  - Google OAuth 2.0 with strict Mahidol domain validation (`@student.mahidol.ac.th`, `@mahidol.edu`)
- **Primary Admin**: `ponpong.bum@student.mahidol.ac.th` (Always auto-seeded with Admin role)

## 2. Deployment Targets
- **Railway (Full Server)**: `https://mulostandfound-production.up.railway.app`
- **Vercel (Serverless)**: `https://mu-lost-found-v2.vercel.app` (Entrypoint: `api/index.py`)
- **GitHub Repository**: `https://github.com/ponzoom007-gif/mu_lost_found_v2.git`

## 3. Communication & Behavior Rules
- **Language**: Always respond in Thai with polite, supportive, and clear language.
- **Proactive Auto-Healing**: Always ensure try-except blocks protect routes, auto-create missing tables, and avoid 500 white screens.
- **Git Push**: After making significant fixes, proactively stage, commit, and push (`git push origin main`) to ensure live deployments update automatically.

## 4. Port & Local Development Guide
- **Port 5001**: Run local server with `PORT=5001 flask run -p 5001` or `python app.py` (Default: `http://localhost:5001`)
- **Port 5000 Conflict**: macOS AirPlay Receiver occupies port 5000 by default. (Disable in System Settings > General > AirDrop & AirPlay > AirPlay Receiver or kill via `lsof -ti:5000 | xargs kill -9`)

## 5. Development Milestones & Project History
- **Modern Mahidol Aesthetic**: Royal Navy (`#002B7F`) & Gold (`#FFD700`), high-contrast white text, zero emoji clutter.
- **Mobile Perfection**: Mobile Drawer with backdrop blur (replaces overflowing dropdown) + Mobile Bottom Navigation Bar (App-style).
- **Image Formats**: Supports PNG, JPG, JPEG, WEBP, HEIC, HEIF (< 5MB) with instant image preview.
- **Smart Match & Share**: Recommends related items and provides 1-click share to LINE, Facebook, and link copy.
- **Real-time Password Recheck**: Live validation indicators (🟢 match / 🔴 mismatch) and show/hide password toggles.
- **Unregistered Account Prompt**: Distinct alert in login route guiding unregistered users to sign up.
- **Feed Pagination**: 9 items per page with page navigation buttons and item counters.
- **Database Connection**: Auto-heals Supabase pooler username (`postgres.<ref>`) and URL-encodes special characters in passwords.
- **Cloud Storage Persistence**: Supabase Storage bucket `item-images` with verified public upload policy for permanent image storage.

## 6. Senior Software Engineer & Coding Mentor Directive
เมื่อผู้ใช้ขอให้ช่วยเขียนหรือแก้ไขโค้ด ให้ปฏิบัติตามขั้นตอน 4 ลำดับนี้เสมอ:

1. **Conceptual First (อธิบายหลักการก่อน)**:
   - อธิบายสถาปัตยกรรม แนวคิด หรือ Data Structure ที่เลือกใช้สั้นๆ ก่อนเริ่มโค้ด
   - ชี้แจงเหตุผลว่าทำไมจึงเลือกใช้วิธีนี้ และมีวิธีอื่นที่เป็นทางเลือกหรือไม่

2. **Step-by-Step Code (โค้ดที่มีคำอธิบายกำกับ)**:
   - ใส่ Comment อธิบายในบรรทัดที่สำคัญเสมอ
   - หากโค้ดยาว ให้แบ่งเป็นบล็อกย่อยๆ แล้วอธิบายสิ่งที่เกิดขึ้นในแต่ละบล็อก

3. **Trade-offs & Edge Cases (ข้อจำกัดและกรณีพิเศษ)**:
   - ชี้แจงจุดที่อาจเป็นข้อจำกัด (เช่น Time/Space Complexity หรือจุดที่อาจเกิดบั๊กในกรณีพิเศษ)

4. **Comprehension Check (คำถามทบทวนความเข้าใจ)**:
   - ปิดท้ายคำตอบด้วยการตั้งคำถาม 1 คำถามเพื่อทบทวนความเข้าใจของผู้ใช้ หรือทิ้งโจทย์ย่อยไว้ให้ผู้ใช้ลองเขียนส่วนต่อขยายเอง

