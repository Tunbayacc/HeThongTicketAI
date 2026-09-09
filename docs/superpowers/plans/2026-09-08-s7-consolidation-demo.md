# S7 — Củng cố & Demo (Consolidation & End-to-End Demo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Inline execution only. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the S7 slice of the AI-integrated customer-support system per design spec §10 S7, §11, §13 and SRS §11.3 (AC-SEC-01..06), §13.3 (System Test), §13.4 (Security Test): comprehensive security test suite & hardening (rate limiting, XSS/SQLi defense, IDOR cross-team isolation, file upload guards), full-lifecycle system smoke testing, frontend responsive 360px & theme/accessibility sweep, and an end-to-end demo scenario guide (`docs/demo-scenario.md`).

**Architecture:**
- Backend security hardening adds rate limiting to `POST /api/auth/login` (SlowAPI) with standard error envelopes, and a sanitization utility for input text fields.
- Two dedicated integration test suites:
  - `backend/tests/integration/test_security_s7.py` validating AC-SEC-01 through AC-SEC-06 and rate limiting.
  - `backend/tests/integration/test_system_smoke_s7.py` running the complete business lifecycle from public submission through AI review, resolution, and closed states.
- Frontend styling sweep adds a complete dark-mode design token palette (`[data-theme="dark"]`), a theme switcher in `AppShell`, responsive drawer/hamburger navigation for mobile viewports down to 360px, table overflow protection, and consistent 4-state rendering (loading, empty, error, ready).
- Detailed documentation: `docs/demo-scenario.md` providing a turnkey demonstration script for stakeholders and evaluators.

**Tech Stack:** FastAPI + Pydantic v2 · PostgreSQL + SQLAlchemy 2.0 async · SlowAPI · React 18 + Vite + Vanilla CSS (Design Tokens, no external UI library) · Pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-09-02-ai-customer-support-design.md` (§10 S7), `documents/SRS.md` (§11.3, §13.3, §13.4), and `docs/requirements.md`.

---

## Global Constraints (bind every task)

- **Preserve existing functionality:** S0 through S6 tests (101 passed) must remain 100% green at all times.
- **No new DB migrations (NFR-MAI-04):** The existing 11 tables fully support all S7 requirements. `docker compose exec backend alembic check` must remain clean.
- **Standard error envelope (SRS §5.2, §10.2):** All API errors adhere to `{"error_code": "...", "message": "...", "details": ...}`.
- **Security criteria compliance (SRS §11.3):**
  - `AC-SEC-01`: Ticket access outside user scope returns 404 anti-leak or 403.
  - `AC-SEC-02`: Non-admin users attempting admin API calls receive 403 `ACCESS_DENIED`.
  - `AC-SEC-03`: XSS payloads in inputs render as safe text, never executing in browser.
  - `AC-SEC-04`: SQL injection payloads do not alter database query semantics.
  - `AC-SEC-05`: Secrets, tokens, passwords, and PII are never leaked in logs or error bodies.
  - `AC-SEC-06`: Executable files or files > 10MB are rejected with 400 `VALIDATION_ERROR`.
- **Frontend constraints:** Pure Vanilla CSS, zero Tailwind or heavy component libraries. Responsive down to 360px width. Strict adherence to `tokens.css`.

---

## File Structure

### Backend — New Files
- `backend/app/core/sanitizer.py` — Input sanitization helper for text fields (HTML tag removal / escape).
- `backend/tests/integration/test_security_s7.py` — Comprehensive security test suite (AC-SEC-01..06, rate limiting).
- `backend/tests/integration/test_system_smoke_s7.py` — Complete end-to-end system smoke test suite.

### Backend — Modified Files
- `backend/app/core/config.py` — Add `auth_login_rate: str = "10/minute"`.
- `backend/app/api/auth.py` — Apply `@limiter.limit(_settings.auth_login_rate)` on `POST /login`.
- `backend/app/core/rate_limit.py` — Ensure 429 handler formats response using standard `AppError` schema.
- `backend/app/services/ticket_service.py` — Integrate text sanitizer on create/update/comment.

### Frontend — Modified Files
- `frontend/src/styles/tokens.css` — Complete dark mode variables (`[data-theme="dark"]` and `@media (prefers-color-scheme: dark)`).
- `frontend/src/styles/shell.css` — Mobile drawer navigation and responsive breakpoints (<= 768px, <= 480px, 360px).
- `frontend/src/styles/tickets.css` — Responsive table scroll and mobile ticket detail cards.
- `frontend/src/styles/admin.css` — Responsive table containers and admin filter wrapping.
- `frontend/src/styles/portal.css` — Mobile padding and form optimization for 360px.
- `frontend/src/app/AppShell.jsx` — Add theme toggle (Dark/Light) and mobile menu toggle state.

### Documentation — New Files
- `docs/demo-scenario.md` — Turnkey end-to-end demonstration script.

---

## Tasks

### Task 1: Rate Limiting & Auth Hardening (AC-SEC-01..06, SRS §8.3)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/core/rate_limit.py`

- [ ] **Step 1: Add auth_login_rate config to Settings**
Add `auth_login_rate: str = "10/minute"` to `Settings` class in `backend/app/core/config.py`.

- [ ] **Step 2: Ensure rate limit handler outputs standard AppError envelope**
In `backend/app/core/rate_limit.py`, verify `_rate_limit_exceeded_handler` returns JSON:
`{"error_code": "RATE_LIMIT_EXCEEDED", "message": "Quá nhiều yêu cầu. Vui lòng thử lại sau.", "details": None}` with HTTP 429.

- [ ] **Step 3: Attach limiter to POST /api/auth/login**
In `backend/app/api/auth.py`, import `limiter` and apply `@limiter.limit(_settings.auth_login_rate)` to the `login` endpoint.

- [ ] **Step 4: Verify existing auth tests still pass**
Run: `.\backend\.venv\Scripts\pytest.exe backend/tests/integration/test_auth.py -v`
Expected: PASS.

---

### Task 2: Input Sanitization & XSS Defense-in-Depth (AC-SEC-03, NFR-SEC-08)

**Files:**
- Create: `backend/app/core/sanitizer.py`
- Modify: `backend/app/services/ticket_service.py`
- Create: `backend/tests/unit/test_sanitizer.py`

- [ ] **Step 1: Write unit test for sanitizer**
In `backend/tests/unit/test_sanitizer.py`, test that `<script>alert(1)</script>`, `<img src=x onerror=...>`, and HTML tags are safely stripped or sanitized while preserving plain text, Vietnamese accents, and legitimate punctuation.

- [ ] **Step 2: Implement sanitizer utility**
Create `backend/app/core/sanitizer.py` using Python's standard library `re` and `html` to sanitize text:
```python
def sanitize_text(text: str | None) -> str | None:
    ...
```

- [ ] **Step 3: Integrate sanitizer into Ticket Service**
In `backend/app/services/ticket_service.py`, sanitize `title`, `description`, and `content` of comments and internal notes upon ingestion.

- [ ] **Step 4: Run unit tests**
Run: `.\backend\.venv\Scripts\pytest.exe backend/tests/unit/test_sanitizer.py -v`
Expected: PASS.

---

### Task 3: Focused Security Integration Test Suite (AC-SEC-01..06)

**Files:**
- Create: `backend/tests/integration/test_security_s7.py`

- [ ] **Step 1: Write AC-SEC-01 test (IDOR & cross-team ticket isolation)**
Test Agent A belonging to Team 1 cannot fetch or update a ticket assigned to Team 2 (returns 404 anti-leak or 403).

- [ ] **Step 2: Write AC-SEC-02 test (Admin API role boundary)**
Test Agent and Manager tokens receive `403 ACCESS_DENIED` on `/api/users`, `/api/teams`, `/api/sla-policies`, `/api/audit-logs`.

- [ ] **Step 3: Write AC-SEC-03 test (XSS prevention)**
Submit ticket with XSS payload `<script>alert('xss')</script>` and verify fetched ticket has sanitized content and does not execute raw HTML.

- [ ] **Step 4: Write AC-SEC-04 test (SQL Injection smoke test)**
Send SQL injection payloads in ticket query (`' OR '1'='1`, `'; DROP TABLE tickets; --`), ticket tracking code, and filter parameters; verify queries execute safely via parameterized SQLAlchemy.

- [ ] **Step 5: Write AC-SEC-05 test (Secret & Credential leak check)**
Verify that `password_hash`, `jwt_secret_key`, and `gemini_api_key` are never returned in any response, error detail, or audit log.

- [ ] **Step 6: Write AC-SEC-06 test (Malicious file & size rejection)**
Verify file upload rejects `.exe`, `.bat`, `.sh`, oversized files (>10MB), and path traversal filenames (`../../evil.png`).

- [ ] **Step 7: Run security test suite**
Run: `.\backend\.venv\Scripts\pytest.exe backend/tests/integration/test_security_s7.py -v`
Expected: PASS.

---

### Task 4: Full-Lifecycle System Smoke Test Suite (SRS §13.3)

**Files:**
- Create: `backend/tests/integration/test_system_smoke_s7.py`

- [ ] **Step 1: Implement full lifecycle system test**
Simulate complete flow:
1. Public user submits ticket via `/api/public/tickets` with attachment.
2. Public user tracks ticket progress via `/api/public/track`.
3. Manager logs in, views unassigned ticket, and assigns it to Team / Agent.
4. Agent logs in, runs AI classification & draft response.
5. Agent reviews/edits draft, approves, and posts public comment.
6. Public user checks tracking again, sees public comment (internal notes excluded).
7. Status transitions: `OPEN` -> `IN_PROGRESS` -> `PENDING` -> `IN_PROGRESS` -> `RESOLVED` -> `CLOSED`.
8. Ticket reopen with reason.
9. Dashboard metrics verify ticket counts and SLA compliance.

- [ ] **Step 2: Run system smoke test**
Run: `.\backend\.venv\Scripts\pytest.exe backend/tests/integration/test_system_smoke_s7.py -v`
Expected: PASS.

---

### Task 5: Frontend Responsive 360px & Theme/Accessibility Sweep

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles/shell.css`
- Modify: `frontend/src/styles/tickets.css`
- Modify: `frontend/src/styles/admin.css`
- Modify: `frontend/src/styles/portal.css`
- Modify: `frontend/src/app/AppShell.jsx`

- [ ] **Step 1: Add dark theme palette and theme toggle in tokens.css & AppShell.jsx**
Define `[data-theme="dark"]` tokens in `tokens.css` (dark backgrounds `#090d16`, surface `#111827`, border `#1f293d`, text `#f1f5f9`).
Add a Theme Toggle button in `AppShell.jsx` header/sidebar persisting to `localStorage.getItem('app-theme')` and setting `document.documentElement.setAttribute('data-theme', theme)`.

- [ ] **Step 2: Add mobile drawer / hamburger navigation in AppShell & shell.css**
Provide toggleable navigation on screens <= 768px down to 360px so navigation items are easily accessible without clipping or overflowing.

- [ ] **Step 3: Responsive table containers & cards for tickets and admin**
Ensure all data tables have `overflow-x: auto` wrappers and responsive card layouts where appropriate, preventing horizontal body scroll at 360px width.

- [ ] **Step 4: Verify 4 UI states (Loading, Empty, Error, Ready) across pages**
Ensure consistent spinners, empty state illustrations/text, error banners, and clean action buttons.

- [ ] **Step 5: Test frontend build**
Run: `npm --prefix frontend run build`
Expected: Build succeeds with 0 errors.

---

### Task 6: Comprehensive End-to-End Demo Scenario Document

**Files:**
- Create: `docs/demo-scenario.md`

- [ ] **Step 1: Write demo scenario document**
Include:
1. Prerequisites & quick start commands (`docker compose up`, seed accounts).
2. Test accounts table (Admin, Manager, Agent, Public).
3. 6-step guided walkthrough:
   - Step 1: Public ticket submission & tracking.
   - Step 2: Manager triage & assignment.
   - Step 3: Agent AI assistant (classify, draft, human review/edit/reject).
   - Step 4: Resolution & SLA tracking.
   - Step 5: Customer verification on portal.
   - Step 6: Admin SLA policies, Audit Log, and Dashboard KPIs.
4. Traceability matrix to AC-01..10, AC-AI-01..11, AC-SEC-01..06.

---

## Verification Plan

### Automated Tests
```bash
# 1. Run all unit tests
.\backend\.venv\Scripts\pytest.exe backend/tests/unit -v

# 2. Run all integration tests including S7 security and smoke tests
.\backend\.venv\Scripts\pytest.exe backend/tests/integration -v

# 3. Verify frontend builds cleanly
npm --prefix frontend run build
```

### Manual Verification
1. Open browser to `http://localhost:5173`.
2. Toggle Dark/Light mode, verify theme transition across all components.
3. Switch browser viewport to 360px width, verify mobile navigation and zero horizontal page overflow.
4. Perform demo steps following `docs/demo-scenario.md`.
