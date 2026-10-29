# HRMS API and Portal

FastAPI, PostgreSQL and React HRMS with encrypted employee PII, soft deletion, JWT authentication and Admin, Employee and Query roles.

## Backend

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirement.txt
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Copy `.env.example` to `.env` and replace every placeholder before starting the API. API documentation is available at `http://127.0.0.1:8000/docs`.

Create the first administrator with:

```powershell
python -m app.bootstrap_admin
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

The portal runs at `http://localhost:5173`. Set `VITE_API_BASE_URL` in `frontend/.env` when the API uses another address.

## Roles

- Admin manages masters, employees, users and role assignments.
- Employee accesses their linked employee profile.
- Query has read-only employee access with PII hidden.

New Employee and Query registrations remain pending until an Admin approves them from the dashboard. Passwords must contain 7-15 characters, at least one digit and at least one special character. Password recovery uses the verification question and hashed answer created during registration.

Passwords and verification answers are Argon2 hashed. Employee PII, including optional profile photos, uses AES-256-GCM envelopes with a key ID, nonce, ciphertext and authentication tag. Photos accept JPEG, PNG or WebP data up to 2 MB. Keep `.env` private and use `.env.example` only as a template.


## Production security settings

Terminate TLS at a trusted reverse proxy, then set these values in the production `.env`:

```env
AUTH_COOKIE_SECURE=true
ENFORCE_HTTPS=true
TRUST_PROXY_HEADERS=true
ALLOWED_FRONTEND_ORIGINS=https://your-portal.example
```

Run Uvicorn without its identifying server header:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --no-server-header
```

The API applies CSP, frame protection, MIME-sniffing protection, private no-store caching for protected responses, restricted CORS methods and headers, JSON media-type checks, and a five-attempt/15-minute login lockout. The lockout store is in-process for one API instance; move it to Redis before scaling to multiple instances.
