# CostPilot Security & Consistency Audit

**Date:** 2026-03-14  
**Scope:** Full-stack audit of frontend, backend, infrastructure, and feature parity

---

## 🔴 CRITICAL — Secrets & Credentials

### 1. Cloud credentials stored unencrypted in the database

- `backend/app/cloud_accounts/service.py` stores AWS secret keys, Azure client secrets, and GCP service account JSON as **plain JSON text** in a PostgreSQL `Text` column (`config=json.dumps(data.config)`)
- **No encryption at rest** — no Fernet, AES, or any cipher is used. Anyone with DB access can read all cloud provider secrets.
- **Fix:** Encrypt the `config` field before writing to DB (e.g., using `cryptography.fernet` with a key from env).

### 2. JWT secret is hardcoded as a default

- `backend/app/config.py` line 15: `JWT_SECRET = "change-me-in-production-use-a-long-random-string"`
- `docker-compose.yml` line 13: same string is **hardcoded** in the compose file
- The `.env` file also has this same placeholder value
- **Fix:** Remove the default value entirely (force it from env), and **never** commit the docker-compose JWT secret.

### 3. Database credentials are hardcoded and exposed

- `docker-compose.yml` lines 9, 39-41: `costpilot:costpilot` as PostgreSQL user/password
- `backend/.env` line 2: `postgresql+asyncpg://costpilot:costpilot@localhost:5432/costpilot`
- MongoDB has **no authentication at all** (lines 53-58)
- Redis has **no password** (lines 60-64)
- All three services bind to **host ports** (5432, 27017, 6379) — accessible from any local process.
- **Fix:** Use env vars for all DB credentials, add MongoDB auth, add Redis password, remove host port bindings for production.

### 4. `.gitignore` covers `.env` but `docker-compose.yml` still leaks secrets

- `.env` is gitignored, but `docker-compose.yml` is **not** gitignored and contains hardcoded DB creds and the JWT secret.

---

## 🟠 HIGH — Authentication & Session Security

### 5. JWT tokens stored in localStorage (XSS vulnerable)

- `frontend/src/store/authStore.ts` uses Zustand `persist` middleware with key `costpilot-auth`, storing tokens in `localStorage`.
- Any XSS attack can steal the JWT. There's **no httpOnly cookie** option, no CSRF protection.
- **Fix:** Move tokens to httpOnly cookies with `Secure` and `SameSite=Strict` flags.

### 6. No token revocation / logout invalidation

- The `logout()` function only clears the frontend store — the JWT remains valid until expiry.
- JWT expiry is set to **7 days** (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7`), which is excessively long.
- **Fix:** Add a token blacklist (Redis-backed) and reduce token lifetime. Add a refresh token flow.

### 7. Password change requires no old password verification

- `backend/app/auth/router.py` PATCH `/me`: user can set a new password without confirming the current one.
- **Fix:** Require `current_password` field for password changes.

### 8. No rate limiting on auth endpoints

- No `slowapi` or any rate limiter found on `/login` or `/register` endpoints.
- Vulnerable to brute-force attacks.
- **Fix:** Add rate limiting (e.g., `slowapi`) to auth endpoints.

### 9. Users auto-verified on registration

- `backend/app/auth/service.py`: `verified=True` set by default. Email verification is bypassed.
- **Fix:** Default to `verified=False` and require email confirmation.

---

## 🟡 MEDIUM — Data Exposure in Frontend

### 10. GCP service account JSON displayed in plaintext

- `frontend/src/pages/ConnectCloudAccount.tsx`: GCP credentials are entered in a plain `TextArea` (not masked). The full private key is visible on screen.
- AWS and Azure correctly use `Input.Password` for secret fields.
- **Fix:** Use a file upload for GCP service account JSON, or mask the textarea.

## 🟡 MEDIUM — Frontend ↔ Backend Discrepancies

### 12. Disconnected features — Backend exists, no frontend page

| Backend Feature | Backend Route | Frontend Page |
| --- | --- | --- |
| **Notifications** | `/api/v1/notifications/*` (preferences, history, test) | ❌ No page |
| **Rules** (assignment rules) | `/api/v1/organizations/{org_id}/rules/*` | ❌ No page |
| **Enterprise stubs** | 14 endpoints returning 501 (`/chargeback`, `/audit-logs`, `/forecasting`, etc.) | ❌ No pages |

### 13. Disconnected features — Frontend page exists, backend incomplete

| Frontend Page | Issue |
| --- | --- |
| **Settings** (`/settings`) | Calls auth profile endpoint only. No dedicated `/settings` backend. Organization settings have no save endpoint. |
| **Users** (`/users`) | Delegates to `/organizations/{org_id}/employees` — works but the mapping is indirect. |

### 14. Notifications endpoints called from frontend but no UI page

- `frontend/src/api/notifications.ts` defines full API bindings (preferences, history, test) but there's **no `/notifications` route** in `App.tsx`.

---

## 🔵 LOW — Architecture & Best Practices

### 15. Inconsistent URL path patterns

- Some routes are org-scoped: `/organizations/{org_id}/resources`
- Detail routes are **unscoped**: `/resources/{id}`, `/pools/{id}`, `/rules/{rule_id}`
- This means the backend **does not validate** that the requesting user belongs to the organization that owns the resource on detail endpoints — potential **authorization bypass** if only user auth is checked but not org membership.

### 16. CORS allows all methods and headers

- `main.py` line 57-59: `allow_methods=["*"]`, `allow_headers=["*"]` — overly permissive. Should be restricted to actual methods used.

### 17. No HTTPS enforcement

- Docker compose and backend have no TLS configuration. Cloud credentials and JWT tokens travel over plain HTTP between frontend and backend.

### 18. DEBUG=true in .env and config defaults

- `config.py` defaults `DEBUG=True`, `.env` sets `DEBUG=true`. SQLAlchemy query echo is enabled, which logs all SQL including potentially sensitive data.

---

## Summary Scorecard

| Category | Rating | Issues |
| --- | --- | --- |
| **Credential Storage** | 🔴 Critical | Cloud creds unencrypted in DB, hardcoded JWT secret |
| **Authentication** | 🟠 High | localStorage JWT, no revocation, no rate limit, 7-day expiry |
| **Data Exposure** | 🟡 Medium | GCP key plaintext, API key display |
| **Feature Parity** | 🟡 Medium | Notifications, Rules have no UI; Settings incomplete |
| **Infrastructure** | 🟡 Medium | No DB auth on Mongo/Redis, ports exposed, no TLS |
| **API Design** | 🔵 Low | Inconsistent URL patterns, org-membership not validated on detail endpoints |
