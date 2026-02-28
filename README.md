# Khalq Certificate Automation System

A full-stack web application that automates generating and emailing personalized certificates to volunteers. Built for Khalq Organization's HR department.

**Stack:** Python FastAPI · Google OAuth · Gmail SMTP · Vanilla JS frontend · Deployed on Render (free)

---

## Project Structure

```
khalq-cert-app/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Environment variables template
├── frontend/
│   └── index.html           # Single-page frontend app
└── render.yaml              # Render deployment config
```

---

## Deployment Guide (Step by Step)

### Step 1 — Set up Google OAuth

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project → name it **"Khalq Certificate App"**
3. Go to **APIs & Services → OAuth consent screen**
   - User Type: **External**
   - App name: `Khalq Certificate Automation`
   - Support email: `khalqq.pk@gmail.com`
   - Add scope: `email`, `profile`, `openid`
   - Add test user: `khalqq.pk@gmail.com`
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Name: `Khalq Cert App`
   - Authorized redirect URIs — add these (you'll fill in the Render URL in Step 3):
     ```
     http://localhost:8000/auth/callback
     https://YOUR-RENDER-URL.onrender.com/auth/callback
     ```
5. Copy your **Client ID** and **Client Secret** — you'll need them in Step 3.

---

### Step 2 — Get a Gmail App Password

1. Go to your Google Account: [https://myaccount.google.com](https://myaccount.google.com)
2. Go to **Security → 2-Step Verification** (must be enabled)
3. Go to **Security → App Passwords**
4. Select app: **Mail**, device: **Other** → name it `Khalq Cert App`
5. Copy the 16-character password shown.

---

### Step 3 — Deploy Backend on Render (Free)

1. Push this project to a **GitHub repository**
2. Go to [https://render.com](https://render.com) and sign up (free)
3. Click **New → Web Service**
4. Connect your GitHub repo
5. Set these settings:
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
6. Add **Environment Variables**:

   | Key | Value |
   |-----|-------|
   | `GOOGLE_CLIENT_ID` | From Step 1 |
   | `GOOGLE_CLIENT_SECRET` | From Step 1 |
   | `GMAIL_USER` | `khalqq.pk@gmail.com` |
   | `GMAIL_APP_PASSWORD` | From Step 2 |
   | `FRONTEND_URL` | Your frontend URL (set after Step 4) |
   | `SESSION_SECRET` | Click "Generate" in Render |

7. Deploy. Your backend URL will be: `https://khalq-certificate-api.onrender.com`

8. **Go back to Google Cloud Console** and add your Render URL to the OAuth redirect URIs:
   ```
   https://khalq-certificate-api.onrender.com/auth/callback
   ```

---

### Step 4 — Deploy Frontend

**Option A — GitHub Pages (free, good for portfolio)**

1. Create a new GitHub repo or use the same one
2. Put `frontend/index.html` in a `/docs` folder or use GitHub Pages from root
3. Open `frontend/index.html` and update line:
   ```js
   const API_BASE = 'https://khalq-certificate-api.onrender.com';
   ```
4. Go to repo **Settings → Pages → Source: main branch**
5. Your frontend URL will be: `https://yourusername.github.io/khalq-cert-app`
6. Update `FRONTEND_URL` in Render environment variables to this URL.

**Option B — Netlify (also free)**

1. Drag and drop the `frontend/` folder to [https://netlify.com/drop](https://netlify.com/drop)
2. Update `API_BASE` in `index.html` first.

---

### Step 5 — Final Check

Visit your frontend URL. You should see the Khalq login page.

- Click **Sign in with Google**
- Sign in with `khalqq.pk@gmail.com`
- You'll be redirected to the app dashboard

If you see "Access denied" — make sure the email matches `ALLOWED_EMAIL` in `main.py`.

---

## How to Use

1. **Upload Template** — Upload your blank certificate PNG/JPG
2. **Position Name** — Click on the certificate to set where names go; adjust font, size, color
3. **Add Volunteers** — Enter names + emails, or import a CSV file
4. **Send** — Preview each certificate, then send all with one click

---

## Local Development

```bash
# Clone the repo
git clone https://github.com/yourname/khalq-cert-app
cd khalq-cert-app/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the server
uvicorn main:app --reload --port 8000
```

Then open `frontend/index.html` in a browser (or serve with `python -m http.server 3000` in the frontend folder).

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login` | Redirect to Google OAuth |
| GET | `/auth/callback` | OAuth callback |
| GET | `/auth/logout` | Clear session |
| GET | `/auth/me` | Check auth status |
| GET | `/api/health` | Health check |
| POST | `/api/preview` | Preview a certificate |
| POST | `/api/send` | Send all certificates |
| POST | `/api/download-single` | Get single certificate as base64 |

---

## Security

- Google OAuth restricts access to `khalqq.pk@gmail.com` only
- Gmail App Password is stored as a server-side environment variable (never exposed to browser)
- Sessions are server-side and expire on logout
- No volunteer data is stored anywhere (fully stateless)

---

## Portfolio Notes

This project demonstrates:
- **FastAPI** REST API with OAuth 2.0 authentication
- **Server-side image processing** with Pillow
- **SMTP email automation** with attachments
- **Google OAuth** integration with Authlib
- **Free cloud deployment** on Render
- **Stateless architecture** (no database needed)
