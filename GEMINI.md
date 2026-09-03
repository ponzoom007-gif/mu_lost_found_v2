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
