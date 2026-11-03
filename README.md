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

The API applies CSP, frame protection, MIME-sniffing protection, private no-store caching for protected responses, restricted CORS methods and headers, JSON media-type checks, Redis-backed login lockouts, token revocation, 15-minute idle sessions, and Redis-backed chatbot session memory. Redis must be running before users log in or use the chatbot; the API fails closed if the security-state store is unavailable.


## Redis for local development

Redis is required for authentication sessions, login lockouts, token revocation, and chatbot sessions. Start it before running the API, then use the REDIS_URL value in .env.example. Docker example:

    docker run --name hrms-redis -p 6379:6379 -d redis:7-alpine

Stop and remove the local container when finished:

    docker stop hrms-redis
    docker rm hrms-redis
