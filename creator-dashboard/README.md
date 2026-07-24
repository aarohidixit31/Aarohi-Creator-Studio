# Creator Dashboard

Your media kit, collab CRM, and invoice generator — one platform, one link to send brands.

## What's in here

```
creator-dashboard/
├── backend/          FastAPI app (API, database, PDF generation)
└── frontend/         React + Vite app (public media kit, collab form, admin dashboard)
```

## What's working right now

- **Public media kit page** (`/`) — pulls from the database, shows your stats, rate card, past collabs, testimonials
- **Collab inquiry form** (`/collab`) — brands fill this out, it lands straight in your CRM
- **Admin login** (`/admin/login`)
- **Admin dashboard** (`/admin`) — see all collab inquiries, move them through your pipeline (New inquiry → In discussion → Negotiating → Confirmed → Content live → Invoiced → Paid → Closed)
- **Invoice generator** (`/admin/invoices/new`) — pick a brand, add line items, generate a branded PDF instantly

## What's NOT built yet (next steps, in order of what I'd tackle first)

1. **Media kit content editor UI** — right now you'd update your bio/rates/testimonials via a direct API call (or I can build you a simple settings form next)
2. **Instagram + YouTube live stat sync** — the stat cards currently just show your handle; wiring up the real follower/engagement numbers is the next big piece
3. **Email notifications** — when someone submits a collab inquiry, you don't get pinged yet (I'd recommend Resend or a simple SMTP setup)
4. **Invoice status tracking UI** — the backend supports draft/sent/paid/overdue, just needs a small UI

None of this is hard — it all builds on what's already here. Just say the word on what to do next.

---

## Local setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Generate your admin password hash and paste it into `.env`:

```bash
python3 -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('your-password-here'))"
```

Also generate a `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Then run it:

```bash
uvicorn app.main:app --reload
```

API docs (auto-generated, useful for testing): http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173 — the Vite dev server proxies `/api` calls to your local backend automatically.

---

## Deploying (free tier: Vercel + Render + Neon)

### 1. Database — Neon (free Postgres)
- Create a project at neon.tech
- Copy the connection string

### 2. Backend — Render
- Push this repo to GitHub
- New Web Service on render.com, point it at `backend/`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Add environment variables: `DATABASE_URL` (from Neon), `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`, `CREATOR_NAME`, `CREATOR_TAGLINE`, `PAYMENT_DETAILS`

Note: Render's free tier spins down after 15 min of inactivity — the first request after idle takes ~30s. Fine for personal use; if a brand hits your form cold it'll just feel slightly slow on the first load.

### 3. Frontend — Vercel
- Import the repo, set root directory to `frontend/`
- Add environment variable `VITE_API_URL` = your Render backend URL (e.g. `https://your-app.onrender.com`)
- Deploy

Once both are live, `yourproject.vercel.app` is the link you send to brands.

---

## Connecting your socials (when you're ready)

- **Instagram**: needs a Business/Creator account linked to a Facebook Page, then Meta Graph API access via a Meta Developer App. Some insight endpoints need app review.
- **YouTube**: YouTube Data API v3 — just needs an API key from Google Cloud Console, no review process.
- **LinkedIn**: personal profile analytics API access is very restricted (Marketing Partner program only) — plan on updating those numbers manually via the media kit settings.

I can walk you through any of these when you're ready to wire them up.
