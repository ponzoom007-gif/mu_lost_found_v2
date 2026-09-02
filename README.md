# MU Lost & Found v2.0 (Secure & University-Specific Edition)

ศูนย์แจ้งและติดตามของหาย มหาวิทยาลัยมหิดล (ฉบับอัปเกรดความปลอดภัยระดับโครงงานมหาวิทยาลัย)

## จุดเด่นด้านความปลอดภัยและการปรับปรุงใหม่:
1. **Mahidol Email Only:** บังคับสมัครสมาชิกและเข้าใช้งานเฉพาะอีเมลมหิดล (`@student.mahidol.ac.th`, `@mahidol.edu`, `@mahidol.ac.th`)
2. **Strict File Upload Validation & 5MB Limit:**
   - จำกัดขนาดไฟล์ไม่เกิน 5 MB ป้องกันเซิร์ฟเวอร์ล่ม (`MAX_CONTENT_LENGTH`)
   - ตรวจสอบ MIME Type และนามสกุลไฟล์รูปภาพจริง
3. **ระบบป้องกันการสวมรอยรับของ (Anti-Spoofing Verification):**
   - มีช่อง "จุดสังเกตเฉพาะ / คำถามยืนยันความเป็นเจ้าของ" (Secret Proof / Claim Question) เพื่อให้เจ้าของตัวจริงตอบก่อนรับของ
4. **ระบบลบโพสต์ (Delete Item):** เจ้าของโพสต์สามารถลบข้อมูล พร้อมระบบลบไฟล์รูปภาพออกจากเซิร์ฟเวอร์อัตโนมัติ (`os.remove`)

---

## ขั้นตอนการรันระบบ:
```bash
pip install -r requirements.txt
python app.py
```
เปิดใช้งานที่: `http://127.0.0.1:5001`
# mu_lost_found_v2
