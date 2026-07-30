# Aarohi Inframe Creator Dashboard

A public media kit and private creator operations platform for collaboration CRM, content proof, invoices, email delivery, reminders, and manager workflows.

## Local development

### Backend

```powershell
cd D:\creator-dashboard\creator-dashboard\backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Copy `.env.example` to `.env` and configure the admin email, bcrypt password hash, secret key, and Resend values. Local development uses SQLite and local image storage automatically.

API documentation: <http://localhost:8000/docs>

### Frontend

```powershell
cd D:\creator-dashboard\creator-dashboard\frontend
npm install
npm run dev
```

Application: <http://localhost:5173>

### Tests

```powershell
cd D:\creator-dashboard\creator-dashboard\backend
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q
```

```powershell
cd D:\creator-dashboard\creator-dashboard\frontend
npm run build
```

## Production environment

Set these values on Render:

- `ENVIRONMENT=production`
- `DATABASE_URL`: Neon direct Postgres connection string (used by both the app and Alembic)
- `SECRET_KEY`: random value of at least 32 characters
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD_HASH`: bcrypt hash, never a plain password
- `CORS_ORIGINS`: deployed Vercel URL, without a trailing slash
- `FRONTEND_URL`: deployed Vercel URL
- `RESEND_API_KEY`
- `EMAIL_FROM`: verified Resend sender
- `ADMIN_NOTIFICATION_EMAIL`
- `REPLY_TO_EMAIL`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `AUTOMATION_ENABLED=true`
- `INVOICE_REMINDER_INTERVAL_DAYS=3`
- `CRON_SECRET`: random value of at least 24 characters
- Creator and payment values from `.env.example`

The backend deliberately refuses to boot in production when Postgres, bcrypt authentication, CORS, Resend, or Cloudinary is unsafe or incomplete.

### Render commands

Root directory:

```text
backend
```

Build:

```text
pip install -r requirements.txt && alembic upgrade head
```

Start:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Vercel

Use `frontend` as the project root and set:

```text
VITE_API_URL=https://your-render-service.onrender.com
```

## Scheduled automation

The GitHub workflow `.github/workflows/daily-automation.yml` runs at 10:00 AM IST. Add repository secrets:

- `AUTOMATION_URL`: Render backend URL
- `CRON_SECRET`: same value configured on Render

It sends overdue invoice reminders at the configured interval and emails the manager a digest of unanswered inquiries and due follow-ups.

## Encrypted database backups

The workflow `.github/workflows/database-backup.yml` creates a weekly encrypted Postgres dump retained for 30 days. Add:

- `DATABASE_URL`: Neon Postgres URL
- `BACKUP_ENCRYPTION_KEY`: strong backup-only passphrase

To decrypt and restore a downloaded backup:

```powershell
openssl enc -d -aes-256-cbc -pbkdf2 -in creator-dashboard.dump.enc -out creator-dashboard.dump -pass pass:YOUR_BACKUP_KEY
pg_restore --clean --if-exists --no-owner --dbname YOUR_RESTORE_DATABASE_URL creator-dashboard.dump
```

Restore into a temporary database first and verify it before replacing production data.

## Media storage

Development uploads are written to `backend/uploads`. Production uploads go to Cloudinary. Local filesystem fallback is disabled when `ENVIRONMENT=production` because Render storage is temporary.

## Deferred integration

Instagram Graph API connection is intentionally deferred. Manual Instagram figures remain available, and the cached social-stat architecture is ready for credentials later.
