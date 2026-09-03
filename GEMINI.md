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
